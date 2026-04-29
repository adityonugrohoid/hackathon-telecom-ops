"""Vertex AI model-ladder failover wrapper for ADK Gemini.

All requests target the single `global` endpoint. On `RESOURCE_EXHAUSTED`
429 or a per-attempt `asyncio.TimeoutError`, the wrapper walks
`ATTEMPT_SCHEDULE` — a hybrid retry-then-swap ladder where the first
two attempts retry the agent's primary model (the second after a brief
sleep so Vertex's dynamic shared quota pool can replenish), the third
attempt swaps to a sibling preview-tier flash model with its own quota
bucket, and the fourth attempt swaps to a universally-addressable GA
fallback so the demo never hard-fails under sustained pressure.

The original design walked across regions on quota errors. That ladder
became structurally unusable once preview models like
`gemini-3.1-flash-lite-preview` shipped with per-project regional
gating — global 429 → us-central1 always 404'd. Failing over across
*models* at the same global endpoint sidesteps the gate: each model has
its own quota bucket, and the GA fallback is universally addressable.

Each wrapper carries an `_owner_name` (the LlmAgent's `name`) so observer
callbacks can route per-attempt telemetry back to a specific agent in the
chat UI without needing extra correlation. Observers register through
`set_attempt_observer`, which is backed by a `ContextVar` so concurrent
Flask requests can each install their own callback in isolation.
"""

import asyncio
import logging
import os
from collections.abc import AsyncGenerator, Callable
from contextvars import ContextVar
from typing import NamedTuple

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import Client
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)

REGION: str = "global"
"""Single Vertex AI endpoint. Google's multi-region routing pool — broadest
preview-model coverage and the only region that addresses
`gemini-3.1-flash-lite-preview` on this project. The legacy multi-region
ladder (us-central1 / europe-west4 / asia-northeast1) is gone because
falling over to those regions returned 404 NOT_FOUND on the preview model
the upstream agents actually use, surfacing as a hard agent failure
instead of a successful failover."""

INTERMEDIATE_MODEL: str = "gemini-3-flash-preview"
"""Sibling preview-tier flash model used as the second-to-last attempt.
Bridges the primary preview pool (gemini-3.1-flash-lite-preview) and the
GA fallback so a sustained 429 on the headline model gets a chance at
another preview-tier model with its own independent quota bucket before
swapping all the way down to GA. Biases the ladder toward "newer model
preferred even under primary-pool load." Verified addressable on `global`
for this project on 2026-04-29 via a generateContent probe; if a future
probe returns 404, the wrapper would propagate that without retry (404
is non-quota per `_is_quota_error`) and the agent would fail visibly —
at that point swap this constant to a known-addressable preview model
or remove the intermediate row from `ATTEMPT_SCHEDULE`."""

FALLBACK_MODEL: str = "gemini-2.5-flash"
"""GA model used as the last-resort attempt. 2.5 Flash is multi-region,
addressable everywhere, and carries its own quota bucket independent of
both the 3.1-preview and 3-flash-preview pools — so a sustained 429 on
either preview pool doesn't imply this fallback is throttled too. Quality
is comparable for the NetPulse 4-agent telecom flow."""


class Attempt(NamedTuple):
    """One row of the failover schedule.

    Attributes:
        model: Override model name for this attempt, or `None` to keep
            whatever `llm_request.model` was on entry (the agent's primary).
        timeout_s: `asyncio.wait_for` ceiling for the upstream HTTP call.
            Only fires on a true silent hang; fast responses return at the
            real latency with no overhead.
        pre_sleep_s: Optional `asyncio.sleep` before issuing this attempt.
            Used between primary retries so Vertex's dynamic shared quota
            pool has a moment to replenish; zero when the previous failure
            already consumed wall-clock (TimeoutError) or for the first
            attempt.
    """

    model: str | None
    timeout_s: float
    pre_sleep_s: float


ATTEMPT_SCHEDULE: tuple[Attempt, ...] = (
    Attempt(model=None,               timeout_s=10.0, pre_sleep_s=0.0),
    Attempt(model=None,               timeout_s=20.0, pre_sleep_s=0.5),
    Attempt(model=INTERMEDIATE_MODEL, timeout_s=20.0, pre_sleep_s=0.0),
    Attempt(model=FALLBACK_MODEL,     timeout_s=30.0, pre_sleep_s=0.0),
)
"""Hybrid retry-then-swap schedule (all on `global`).

| # | model              | timeout | pre-sleep |
|---|--------------------|---------|-----------|
| 1 | primary self.model | 10s     | 0s        |
| 2 | primary self.model | 20s     | 0.5s      |
| 3 | INTERMEDIATE_MODEL | 20s     | 0s        |
| 4 | FALLBACK_MODEL     | 30s     | 0s        |

Attempt 1 catches obvious silent hangs fast on the headline model.
Attempt 2 retries the same preview model after 0.5s — most 429s on
Vertex's shared global pool clear within a second, so the user gets
the headline-model answer the vast majority of the time. Attempt 3
swaps to a sibling preview-tier flash model with its own independent
quota bucket — biases the ladder toward keeping a newer-model answer
under sustained primary-pool pressure before falling all the way back
to GA. Attempt 4 swaps to the GA fallback (universally addressable,
quota independent of both preview pools) so the demo never hard-fails
under sustained pressure on every preview lane simultaneously.

`model=None` means "leave `llm_request.model` as-is" — i.e., the
agent's configured primary. The wrapper mutates `llm_request.model`
in-place per attempt because ADK's parent `Gemini.generate_content_async`
reads from there, not from `self.model`.

Worst-case wall clock per agent: 10 + 0.5 + 20 + 20 + 30 = 80.5s,
well under Cloud Run's 300s request timeout."""

_QUOTA_MARKERS: tuple[str, ...] = ("RESOURCE_EXHAUSTED", " 429", "QUOTA")

AttemptCallback = Callable[[str, str, str, str | None], None]
"""(owner_name, model, outcome, error_message) — outcome is "ok" | "failover".

The `model` field carries the model name the attempt actually ran on (the
fallback name when the schedule swapped, the primary name otherwise). The
chat-UI 'via' chip dedupes consecutive identical strings so retries on
the same model collapse into a single hop and only the model swap
surfaces as a visible transition."""

_attempt_observer: ContextVar[AttemptCallback | None] = ContextVar(
    "_attempt_observer", default=None
)


def set_attempt_observer(callback: AttemptCallback | None) -> None:
    """Register a callback invoked on each attempt outcome.

    The callback receives `(owner_name, model, outcome, error_message)`
    where `outcome` is `"ok"` when the attempt returned a usable response
    and `"failover"` when the attempt 429'd or timed out and the wrapper
    advanced to the next entry in `ATTEMPT_SCHEDULE`. `error_message` is
    the upstream error string on `"failover"` and `None` on `"ok"`.

    Pass `None` to unregister. State is held in a `ContextVar` so concurrent
    callers — e.g., separate Flask request threads, each spawning its own
    `_agent_worker` asyncio loop — install isolated observers without racing.

    Args:
        callback: Observer callable, or `None` to unregister.
    """
    _attempt_observer.set(callback)


def _notify_attempt(
    owner_name: str, model: str, outcome: str, err_msg: str | None
) -> None:
    """Best-effort notify the current observer, swallowing any callback error.

    The observer must never break the Vertex AI call: a misbehaving callback
    is logged and ignored so failover continues normally.

    Args:
        owner_name: The LlmAgent name that owns this wrapper instance.
        model: The model name the attempt targeted.
        outcome: `"ok"` on success, `"failover"` on quota error or timeout.
        err_msg: Upstream error string when `outcome == "failover"`, else None.
    """
    callback = _attempt_observer.get()
    if callback is None:
        return
    try:
        callback(owner_name, model, outcome, err_msg)
    except Exception:  # noqa: BLE001
        logger.exception("attempt observer raised; suppressing")


def _is_quota_error(exc: Exception) -> bool:
    """Decide whether an exception represents Vertex AI quota exhaustion.

    Detection is a case-insensitive substring match against `str(exc)` for
    `RESOURCE_EXHAUSTED`, ` 429`, or `QUOTA`. This is the SDK-stable surface
    as of `google-genai` 1.70.0; revisit if the upstream raise messages change.

    Args:
        exc: The exception raised by the upstream Vertex AI call.

    Returns:
        True when the exception represents a quota error, False otherwise.
    """
    msg = str(exc).upper()
    return any(marker in msg for marker in _QUOTA_MARKERS)


class RegionFailoverGemini(Gemini):
    """ADK Gemini wrapper that fails over across MODELS on 429 / TimeoutError.

    Each call to `generate_content_async` walks `ATTEMPT_SCHEDULE` in order.
    On a quota error or `asyncio.TimeoutError`, the wrapper sleeps the next
    attempt's `pre_sleep_s`, swaps `llm_request.model` if the attempt
    specifies an override, and retries. The single underlying `genai.Client`
    points at `REGION = "global"` and is built once per instance.

    Streaming (`stream=True`) bypasses the schedule entirely: partial
    yielded responses cannot be safely replayed on retry, and a timeout
    mid-stream would lose chunks. NetPulse uses `stream=False` for the
    SequentialAgent flow, so this is not a hot-path concern.

    The retry happens before any tool execution — `generate_content_async`
    is a single HTTP round-trip per attempt — so there is no duplicate-write
    risk for tools like `save_incident_ticket`.

    The class name is preserved from the prior region-failover design to
    keep the import surface and agent.py wiring stable.
    """

    _owner_name: str = PrivateAttr(default="")

    def set_owner_name(self, name: str) -> None:
        """Tag this wrapper with the LlmAgent name that owns it.

        Used by attempt observers to route per-attempt telemetry to the
        right chat-UI timeline entry. Set once at agent-construction time.

        Args:
            name: The owning `LlmAgent.name` (e.g., "classifier").
        """
        self._owner_name = name

    def _build_client(self) -> Client:
        """Construct the single Vertex AI Client pinned to `REGION`.

        `GOOGLE_CLOUD_PROJECT` is read from the process environment but
        `os.environ` is never mutated; the region travels through the
        explicit `location=` argument so multi-threaded callers do not race.

        Returns:
            A `google.genai.Client` configured for the global endpoint.
        """
        return Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=REGION,
            http_options=types.HttpOptions(
                headers=self._tracking_headers,
                retry_options=self.retry_options,
            ),
        )

    @property
    def api_client(self) -> Client:
        """Return the singleton Vertex AI Client for `REGION`.

        Overrides the base class `cached_property` so the wrapper owns the
        client lifecycle. With model failover (not region failover), the
        client never needs to rebuild within a wrapper instance.
        """
        cached = self.__dict__.get("api_client")
        if cached is not None:
            return cached
        client = self._build_client()
        self.__dict__["api_client"] = client
        return client

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Send a request to Gemini, walking `ATTEMPT_SCHEDULE` on failure.

        Each attempt is wrapped in `asyncio.wait_for(timeout=attempt.timeout_s)`.
        On `RESOURCE_EXHAUSTED` 429 or `asyncio.TimeoutError`, the wrapper
        applies the next attempt's `pre_sleep_s`, mutates `llm_request.model`
        if the attempt specifies a `model` override (else keeps the primary),
        and retries. `wait_for` cancels the in-flight coroutine on timeout
        so the SDK's aiohttp client closes the socket — only one HTTP call
        is ever live per wrapper instance.

        Args:
            llm_request: The ADK LlmRequest to send. Mutated in-place per
                attempt: `llm_request.model` is rewritten when the schedule
                row carries a `model` override.
            stream: When True, the schedule is bypassed and the upstream
                call is made directly (partial responses cannot be safely
                replayed; timeouts mid-stream would lose chunks).

        Yields:
            LlmResponse: Each response from the upstream call.

        Raises:
            RuntimeError: When every entry in `ATTEMPT_SCHEDULE` has been
                exhausted (quota or timeout).
            genai.errors.ClientError: When the upstream call raises a
                non-quota client error (re-raised immediately, no retry).
        """
        if stream:
            logger.info(
                "Vertex AI streaming bypass: agent_model=%s region=%s",
                llm_request.model,
                REGION,
            )
            async for response in super().generate_content_async(
                llm_request, stream
            ):
                yield response
            _notify_attempt(self._owner_name, llm_request.model, "ok", None)
            return

        primary_model = llm_request.model
        last_exc: Exception | None = None

        for attempt in ATTEMPT_SCHEDULE:
            if attempt.pre_sleep_s > 0:
                await asyncio.sleep(attempt.pre_sleep_s)

            active_model = attempt.model or primary_model
            llm_request.model = active_model
            logger.info(
                "Vertex AI attempt: agent_model=%s region=%s timeout=%ss",
                active_model,
                REGION,
                attempt.timeout_s,
            )

            async def _drain_one_attempt() -> list[LlmResponse]:
                """Drain the parent's async generator into a list under one timeout.

                With `stream=False` the parent yields exactly one response, so
                draining is just one item. Wrapping the whole drain in
                `asyncio.wait_for` lets a single timeout cover the entire
                upstream HTTP round-trip cleanly.
                """
                out: list[LlmResponse] = []
                async for r in Gemini.generate_content_async(
                    self, llm_request, stream
                ):
                    out.append(r)
                return out

            try:
                responses = await asyncio.wait_for(
                    _drain_one_attempt(), timeout=attempt.timeout_s
                )
                for r in responses:
                    yield r
                _notify_attempt(self._owner_name, active_model, "ok", None)
                return
            except TimeoutError as exc:
                logger.warning(
                    "Vertex AI silent hang on model=%s after %ss; falling over.",
                    active_model,
                    attempt.timeout_s,
                )
                _notify_attempt(
                    self._owner_name,
                    active_model,
                    "failover",
                    f"timeout after {attempt.timeout_s}s",
                )
                last_exc = exc
            except genai_errors.ClientError as exc:
                if not _is_quota_error(exc):
                    raise
                logger.warning(
                    "Vertex AI 429 on model=%s; falling over. detail=%s",
                    active_model,
                    exc,
                )
                _notify_attempt(
                    self._owner_name, active_model, "failover", str(exc)
                )
                last_exc = exc
        raise RuntimeError(
            "All Vertex AI attempts exhausted: "
            f"{[a.model or '<primary>' for a in ATTEMPT_SCHEDULE]}"
        ) from last_exc


# --- Self-tests ------------------------------------------------------------

async def _self_test_quota_retry_same_model() -> None:
    """Verify attempt 1 quota-fails and attempt 2 succeeds on the SAME primary.

    Mocks `Gemini.generate_content_async` so the first call raises a 429
    and the second yields a sentinel. Asserts the wrapper called the
    primary model twice, yielded the sentinel, and the observer fired
    twice (failover-on-primary then ok-on-primary). Verifies the no-swap
    behavior of attempts 1 → 2.

    Runtime: ~0.5s (the inter-attempt sleep on attempt 2).
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    primary = "gemini-3.1-flash-lite-preview"
    call_log: list[str] = []
    fake_request = SimpleNamespace(model=primary)

    async def mock_parent_call(self, llm_request, _stream=False):
        call_log.append(llm_request.model)
        if len(call_log) == 1:
            raise genai_errors.ClientError(
                429,
                {
                    "error": {
                        "code": 429,
                        "status": "RESOURCE_EXHAUSTED",
                        "message": f"Quota exceeded for model {llm_request.model}",
                    }
                },
            )
        yield "FAKE_RESPONSE"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, model: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, model, outcome, err))

    set_attempt_observer(observer)
    try:
        with patch.object(Gemini, "generate_content_async", mock_parent_call):
            wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
            wrapper.set_owner_name("test_agent_quota")
            responses: list = []
            async for response in wrapper.generate_content_async(
                llm_request=fake_request
            ):
                responses.append(response)
    finally:
        set_attempt_observer(None)

    assert call_log == [primary, primary], (
        f"expected primary twice, got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE"], f"expected sentinel, got {responses}"
    assert len(observer_log) == 2, f"expected 2 observer calls, got {observer_log}"
    assert observer_log[0] == ("test_agent_quota", primary, "failover", observer_log[0][3]), (
        f"expected first event=failover on primary, got {observer_log[0]}"
    )
    assert "RESOURCE_EXHAUSTED" in (observer_log[0][3] or ""), (
        f"expected first failover msg to mention RESOURCE_EXHAUSTED, got {observer_log[0][3]}"
    )
    assert observer_log[1] == ("test_agent_quota", primary, "ok", None), (
        f"expected second event=ok on primary with no err, got {observer_log[1]}"
    )
    logger.info(
        "OK: quota-retry stayed on primary, walked %s, fired observer %d times",
        call_log,
        len(observer_log),
    )


async def _self_test_timeout_retry_same_model() -> None:
    """Verify attempt 1 hangs and attempt 2 succeeds on the SAME primary.

    Mocks `Gemini.generate_content_async` so the first call awaits
    `asyncio.Future()` (never resolves; only torn down by `wait_for`'s
    cancellation), then the second yields a sentinel. Asserts the wrapper
    times out after `ATTEMPT_SCHEDULE[0].timeout_s`, advances to attempt 2
    on the same primary, yields the sentinel, and the observer fires
    twice (timeout-failover then ok).

    Runtime: roughly equal to `ATTEMPT_SCHEDULE[0].timeout_s` (~10s).
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    primary = "gemini-3.1-flash-lite-preview"
    call_log: list[str] = []
    fake_request = SimpleNamespace(model=primary)

    async def mock_parent_call_hang(self, llm_request, _stream=False):
        call_log.append(llm_request.model)
        if len(call_log) == 1:
            await asyncio.Future()
        yield "FAKE_RESPONSE_AFTER_HANG"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, model: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, model, outcome, err))

    set_attempt_observer(observer)
    try:
        with patch.object(Gemini, "generate_content_async", mock_parent_call_hang):
            wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
            wrapper.set_owner_name("test_agent_hang")
            responses: list = []
            async for response in wrapper.generate_content_async(
                llm_request=fake_request
            ):
                responses.append(response)
    finally:
        set_attempt_observer(None)

    assert call_log == [primary, primary], (
        f"expected primary twice (hang then ok), got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE_AFTER_HANG"], (
        f"expected sentinel from attempt 2, got {responses}"
    )
    assert len(observer_log) == 2, f"expected 2 observer calls, got {observer_log}"
    assert (
        observer_log[0][0] == "test_agent_hang"
        and observer_log[0][1] == primary
        and observer_log[0][2] == "failover"
        and "timeout" in (observer_log[0][3] or "").lower()
    ), f"expected first event=failover with timeout msg, got {observer_log[0]}"
    assert observer_log[1] == ("test_agent_hang", primary, "ok", None), (
        f"expected second event=ok on primary with no err, got {observer_log[1]}"
    )
    logger.info(
        "OK: timeout-retry stayed on primary, walked %s, fired observer %d times",
        call_log,
        len(observer_log),
    )


async def _self_test_persistent_429_swaps_to_fallback() -> None:
    """Verify primary 429s + intermediate 429 escalate to the GA fallback.

    Mocks `Gemini.generate_content_async` to raise 429 whenever the request
    targets the primary OR the intermediate preview model, and yield a
    sentinel for the GA fallback. Asserts the wrapper walked
    [primary, primary, INTERMEDIATE_MODEL, FALLBACK_MODEL], yielded the
    sentinel, and the observer fired four times (three failovers, one ok
    on the fallback). This is the demo-reliability path: under sustained
    pressure on BOTH preview pools, the user still gets an answer from
    the GA fallback.

    Runtime: ~0.5s (inter-attempt sleep on attempt 2 only; attempts 3 and
    4 have none).
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    primary = "gemini-3.1-flash-lite-preview"
    call_log: list[str] = []
    fake_request = SimpleNamespace(model=primary)

    async def mock_parent_call(self, llm_request, _stream=False):
        call_log.append(llm_request.model)
        if llm_request.model in (primary, INTERMEDIATE_MODEL):
            raise genai_errors.ClientError(
                429,
                {
                    "error": {
                        "code": 429,
                        "status": "RESOURCE_EXHAUSTED",
                        "message": f"Quota exceeded for model {llm_request.model}",
                    }
                },
            )
        yield "FAKE_RESPONSE_FROM_FALLBACK"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, model: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, model, outcome, err))

    set_attempt_observer(observer)
    try:
        with patch.object(Gemini, "generate_content_async", mock_parent_call):
            wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
            wrapper.set_owner_name("test_agent_swap")
            responses: list = []
            async for response in wrapper.generate_content_async(
                llm_request=fake_request
            ):
                responses.append(response)
    finally:
        set_attempt_observer(None)

    assert call_log == [primary, primary, INTERMEDIATE_MODEL, FALLBACK_MODEL], (
        f"expected primary x2 then intermediate then fallback, got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE_FROM_FALLBACK"], (
        f"expected sentinel from fallback, got {responses}"
    )
    assert len(observer_log) == 4, f"expected 4 observer calls, got {observer_log}"
    assert (
        observer_log[0][1] == primary and observer_log[0][2] == "failover"
        and observer_log[1][1] == primary and observer_log[1][2] == "failover"
        and observer_log[2][1] == INTERMEDIATE_MODEL
        and observer_log[2][2] == "failover"
    ), f"expected three failovers (primary x2 then intermediate), got {observer_log[:3]}"
    assert observer_log[3] == ("test_agent_swap", FALLBACK_MODEL, "ok", None), (
        f"expected ok on fallback, got {observer_log[3]}"
    )
    logger.info(
        "OK: persistent 429 walked %s, fired observer %d times",
        call_log,
        len(observer_log),
    )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    assert _is_quota_error(Exception("RESOURCE_EXHAUSTED: quota"))
    assert _is_quota_error(Exception("HTTP 429 Too Many Requests"))
    assert _is_quota_error(Exception("Quota exceeded"))
    assert not _is_quota_error(Exception("INVALID_ARGUMENT: bad model"))
    assert not _is_quota_error(Exception("PERMISSION_DENIED"))
    logger.info("OK: _is_quota_error matcher passes 5/5 cases")

    asyncio.run(_self_test_quota_retry_same_model())
    asyncio.run(_self_test_timeout_retry_same_model())
    asyncio.run(_self_test_persistent_429_swaps_to_fallback())
