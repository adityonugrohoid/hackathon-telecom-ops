"""Bridge sync Flask to async ADK Runner for the NetPulse AI chat tab.

Each /api/query request spawns a worker thread that runs its own asyncio event
loop, drives the SequentialAgent via runner.run_async, and pushes converted
events onto a thread-safe queue. The Flask SSE generator pulls from the queue
and yields incrementally so chat cards animate as the agent progresses.
"""

import asyncio
import dataclasses
import logging
import queue
import sys
import threading
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))  # cross-package import: telecom_ops/

APP_NAME = "netpulse_ui"
USER_ID = "local-user"

logger = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """One streamable event for the chat UI.

    Attributes:
        type: One of agent_start, tool_call, tool_response, text, complete,
            error, region_attempt.
        agent: Name of the LlmAgent that produced the event. For type='error',
            present iff the error originated inside a specific tool call;
            absent for catastrophic top-level failures. For type='region_attempt',
            this is the owning agent name from the RegionFailoverGemini wrapper.
        tool: Function name when type is tool_call/tool_response/error (tool-scoped).
        args: Tool call arguments when type is tool_call.
        result: Tool response payload when type is tool_response.
        text: Model text when type is text.
        ticket_id: Final incident ticket id when type is complete.
        final_report: Final response_formatter text when type is complete.
        message: Error message when type is error, or upstream quota error
            string when type is region_attempt + outcome is failover.
        region: Vertex AI region attempted when type is region_attempt
            (e.g., "global", "asia-southeast2").
        outcome: "ok" or "failover" when type is region_attempt.
    """

    type: str
    agent: str = ""
    tool: str | None = None
    args: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    text: str | None = None
    ticket_id: int | None = None
    final_report: str | None = None
    message: str | None = None
    region: str | None = None
    outcome: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Returns a dict with None fields stripped for compact SSE payloads."""
        return {k: v for k, v in dataclasses.asdict(self).items() if v is not None}


_runner_cache: dict[str, Any] = {"runner": None, "error": None}
_SENTINEL = object()


def _load_runner():
    """Lazily import telecom_ops + build a Runner. Caches success and failure.

    Returns:
        Tuple of (runner, None) on success or (None, error_message) if any
        singleton init failed at telecom_ops import time.
    """
    if _runner_cache["runner"] or _runner_cache["error"]:
        return _runner_cache["runner"], _runner_cache["error"]
    try:
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService

        from telecom_ops.agent import root_agent

        runner = Runner(
            app_name=APP_NAME,
            agent=root_agent,
            session_service=InMemorySessionService(),
        )
        _runner_cache["runner"] = runner
        return runner, None
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load telecom_ops.root_agent")
        _runner_cache["error"] = f"Agent unavailable: {exc}"
        return None, _runner_cache["error"]


def _extract_tool_error(response: dict[str, Any]) -> str | None:
    """Returns a human-readable error message if the tool response signals a failure.

    Detects two shapes:
      1. NetPulse native tools that explicitly return `{"status": "error", "message": ...}`
         (e.g., `save_incident_ticket`'s VALID_CATEGORIES guard in `telecom_ops/tools.py`).
      2. ADK's exception-wrapping shape `{"error": "<str>", ...}` produced when a
         tool raises an uncaught exception inside `runner.run_async`.

    Returns None when the response looks healthy. Non-string error values are
    coerced to str so the SSE payload is always JSON-serializable.

    Args:
        response: The raw `function_response` dict captured from an ADK event.

    Returns:
        Error message string for the chat UI, or None if no error was detected.
    """
    if response.get("status") == "error":
        return str(response.get("message") or "Tool returned status='error'")
    err = response.get("error")
    if isinstance(err, str) and err:
        return err
    return None


def _infer_failing_agent(runner, seen_authors: set[str]) -> str:
    """Best-effort attribution of which agent crashed when an exception
    bubbled out of `runner.run_async` before any event from the failing
    agent reached the drain loop.

    For SequentialAgent runs, the failing agent is the first sub-agent in
    pipeline order whose author hasn't yet appeared in `seen_authors` —
    i.e. the agent the SequentialAgent was about to run when the
    exception fired. When every sub-agent has already produced at least
    one event, the failure is mid-flight on the last one in the pipeline.

    Args:
        runner: The ADK Runner whose `agent.sub_agents` defines the
            pipeline order.
        seen_authors: Set of agent names that have already produced at
            least one event in the current run.

    Returns:
        The inferred failing agent name. Empty string when the runner
        isn't a SequentialAgent or `sub_agents` is otherwise unreadable —
        in that case the chat UI falls back to the global error card
        with no agent attribution.
    """
    sub_agents = getattr(runner.agent, "sub_agents", None) or []
    for sub in sub_agents:
        name = getattr(sub, "name", "")
        if name and name not in seen_authors:
            return name
    if sub_agents:
        return getattr(sub_agents[-1], "name", "")
    return ""


def _convert_event(event) -> list[AgentEvent]:
    """Translate one ADK Event into 0..N UI events."""
    out: list[AgentEvent] = []
    author = event.author or ""

    for fc in event.get_function_calls():
        out.append(
            AgentEvent(
                type="tool_call",
                agent=author,
                tool=fc.name or "",
                args=dict(fc.args) if fc.args else {},
            )
        )
    for fr in event.get_function_responses():
        response_dict = dict(fr.response) if fr.response else {}
        out.append(
            AgentEvent(
                type="tool_response",
                agent=author,
                tool=fr.name or "",
                result=response_dict,
            )
        )
        err_msg = _extract_tool_error(response_dict)
        if err_msg:
            out.append(
                AgentEvent(
                    type="error",
                    agent=author,
                    tool=fr.name or "",
                    message=err_msg,
                )
            )

    if not getattr(event, "partial", False) and event.content and event.content.parts:
        text_chunks = [
            p.text for p in event.content.parts if getattr(p, "text", None)
        ]
        joined = "".join(text_chunks).strip()
        if joined:
            out.append(AgentEvent(type="text", agent=author, text=joined))

    return out


def _agent_worker(query: str, q: queue.Queue, runner) -> None:
    """Run runner.run_async in its own asyncio loop and push events on q.

    Installs a per-request region-attempt observer on the
    `RegionFailoverGemini` wrappers so per-attempt Vertex AI region telemetry
    flows back into the SSE stream as `region_attempt` events. The observer
    is registered through a `ContextVar`, so concurrent worker threads
    register isolated callbacks without interfering with each other. The
    callback is unregistered in the `finally` block so a crashed run cannot
    leak a queue reference into a future request.
    """
    from google.genai import types

    from telecom_ops.vertex_failover import set_attempt_observer

    seen_authors: set[str] = set()
    final_report: str | None = None
    final_ticket: int | None = None

    def _on_region_attempt(
        owner: str, region: str, outcome: str, err_msg: str | None
    ) -> None:
        """Push a region_attempt event onto the SSE queue.

        Routed by `owner` (the LlmAgent name set via `set_owner_name` in
        `telecom_ops/agent.py:_failover_model`), so the chat UI can attach
        the chip to the right `.np-timeline-entry`.
        """
        q.put(
            AgentEvent(
                type="region_attempt",
                agent=owner,
                region=region,
                outcome=outcome,
                message=err_msg,
            ).to_dict()
        )

    async def _drain():
        nonlocal final_report, final_ticket
        session_id = uuid.uuid4().hex
        await runner.session_service.create_session(
            app_name=APP_NAME,
            user_id=USER_ID,
            session_id=session_id,
        )
        new_message = types.Content(
            role="user", parts=[types.Part(text=query)]
        )
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=session_id,
            new_message=new_message,
        ):
            author = event.author or ""
            if author and author != "user" and author not in seen_authors:
                seen_authors.add(author)
                q.put(AgentEvent(type="agent_start", agent=author).to_dict())
            for ui_event in _convert_event(event):
                q.put(ui_event.to_dict())
                if (
                    ui_event.tool == "save_incident_ticket"
                    and ui_event.type == "tool_response"
                ):
                    final_ticket = (ui_event.result or {}).get("ticket_id")
                if (
                    ui_event.agent == "response_formatter"
                    and ui_event.type == "text"
                ):
                    final_report = ui_event.text
        q.put(
            AgentEvent(
                type="complete",
                ticket_id=final_ticket,
                final_report=final_report,
            ).to_dict()
        )

    set_attempt_observer(_on_region_attempt)
    try:
        asyncio.run(_drain())
    except Exception as exc:  # noqa: BLE001
        logger.exception("Agent run failed")
        q.put(
            AgentEvent(
                type="error",
                agent=_infer_failing_agent(runner, seen_authors),
                message=str(exc),
            ).to_dict()
        )
    finally:
        set_attempt_observer(None)
        q.put(_SENTINEL)


def run_agent(query: str) -> Iterator[dict[str, Any]]:
    """Stream UI events for one user query.

    Args:
        query: Natural-language complaint from the chat textbox.

    Yields:
        Dicts shaped per the AgentEvent contract (agent_start, tool_call,
        tool_response, text, complete, error).
    """
    runner, err = _load_runner()
    if err:
        yield AgentEvent(type="error", message=err).to_dict()
        return

    q: queue.Queue = queue.Queue(maxsize=64)
    worker = threading.Thread(
        target=_agent_worker, args=(query, q, runner), daemon=True
    )
    worker.start()

    while True:
        item = q.get()
        if item is _SENTINEL:
            break
        yield item

    worker.join(timeout=1.0)
