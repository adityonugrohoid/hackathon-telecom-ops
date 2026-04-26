"""Vertex AI region failover wrapper for ADK Gemini.

The default region is `global` (Google's multi-region routing pool); on a
`RESOURCE_EXHAUSTED` 429, the wrapper rebuilds its underlying `genai.Client`
against the next region in `RANKED_REGIONS` and retries. Failover state is
per-instance, so each `LlmAgent` walks the ladder independently.

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

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import Client
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)

RANKED_REGIONS: tuple[str, ...] = (
    "global",          # Google's multi-region routing pool — best chance of
                       # serving newer / preview models without per-region
                       # availability gates.
    "us-central1",     # Iowa — primary Vertex AI region, always carries the
                       # newest Gemini models and the largest capacity pool.
                       # Co-located with our Cloud Run service (~0ms hop).
    "europe-west4",    # Netherlands — primary EU Vertex region, broadest model
                       # coverage outside the US.
    "asia-northeast1", # Tokyo — primary APAC Vertex region for newer models;
                       # replaces the prior asia-southeast2/1 entries which
                       # 400'd FAILED_PRECONDITION on `gemini-3.1-pro-preview`
                       # in the 07:14 UTC 2026-04-26 production trace.
)

PER_ATTEMPT_TIMEOUT_S: float = 10.0
"""Per-attempt timeout for a single Vertex AI region. On TimeoutError, the
wrapper cancels the in-flight HTTP call (the SDK closes the socket on
asyncio.CancelledError) and advances to the next region in RANKED_REGIONS,
identical to a quota-error failover. Originally 5s, raised to 10s on
2026-04-26 after a Phase 11 production trace showed `network_investigator`
false-positive-timing-out on `global` while summarising a 15.5 KB
weekly_outage_trend response (the 50 000-row seed shifted the legitimate-
slow tail past the 5s mark). The failover ladder then 404'd because
`gemini-3.1-flash-lite-preview` is `global`-only on this project, so the
false positive surfaces as a hard agent failure — not as a successful
failover. 10s gives global-on-load enough headroom while still catching
true silent hangs (those don't return ever)."""

_QUOTA_MARKERS: tuple[str, ...] = ("RESOURCE_EXHAUSTED", " 429", "QUOTA")

AttemptCallback = Callable[[str, str, str, str | None], None]
"""(owner_name, region, outcome, error_message) — outcome is "ok" | "failover"."""

_attempt_observer: ContextVar[AttemptCallback | None] = ContextVar(
    "_attempt_observer", default=None
)


def set_attempt_observer(callback: AttemptCallback | None) -> None:
    """Register a callback invoked on each region attempt outcome.

    The callback receives `(owner_name, region, outcome, error_message)` where
    `outcome` is `"ok"` when the region returned a usable response and
    `"failover"` when the region 429'd and the wrapper advanced to the next
    entry in `RANKED_REGIONS`. `error_message` is the upstream error string on
    `"failover"` and `None` on `"ok"`.

    Pass `None` to unregister. State is held in a `ContextVar` so concurrent
    callers — e.g., separate Flask request threads, each spawning its own
    `_agent_worker` asyncio loop — install isolated observers without racing.

    Args:
        callback: Observer callable, or `None` to unregister.
    """
    _attempt_observer.set(callback)


def _notify_attempt(
    owner_name: str, region: str, outcome: str, err_msg: str | None
) -> None:
    """Best-effort notify the current observer, swallowing any callback error.

    The observer must never break the Vertex AI call: a misbehaving callback
    is logged and ignored so failover continues normally.

    Args:
        owner_name: The LlmAgent name that owns this wrapper instance.
        region: The Vertex AI region the attempt targeted.
        outcome: `"ok"` on success, `"failover"` on quota error.
        err_msg: Upstream error string when `outcome == "failover"`, else None.
    """
    callback = _attempt_observer.get()
    if callback is None:
        return
    try:
        callback(owner_name, region, outcome, err_msg)
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
    """ADK Gemini wrapper that fails over through ranked Vertex AI regions on 429.

    Each call to `generate_content_async` walks `RANKED_REGIONS` in order. On
    a quota error from the upstream Vertex AI call, the underlying
    `genai.Client` is rebuilt against the next region and the request is
    retried. Failover state is per-instance — each `LlmAgent` should
    construct its own wrapper, so one agent's failover does not bind the
    others to the same region.

    Streaming (`stream=True`) bypasses failover: partial yielded responses
    cannot be safely replayed on retry. NetPulse uses `stream=False` for the
    SequentialAgent flow, so this is not a hot-path concern.

    The retry happens before any tool execution — `generate_content_async` is
    a single HTTP round-trip per attempt — so there is no duplicate-write
    risk for tools like `save_incident_ticket`.
    """

    _active_region: str = PrivateAttr(default=RANKED_REGIONS[0])
    _owner_name: str = PrivateAttr(default="")

    def set_owner_name(self, name: str) -> None:
        """Tag this wrapper with the LlmAgent name that owns it.

        Used by attempt observers to route per-region telemetry to the right
        chat-UI timeline entry. Set once at agent-construction time.

        Args:
            name: The owning `LlmAgent.name` (e.g., "classifier").
        """
        self._owner_name = name

    def _build_client_for(self, region: str) -> Client:
        """Construct a Vertex AI Client pinned to a specific region.

        `GOOGLE_CLOUD_PROJECT` is read from the process environment but
        `os.environ` is never mutated; the region travels through the explicit
        `location=` argument so multi-threaded callers do not race.

        Args:
            region: A Vertex AI region name (e.g., "global", "asia-southeast1").

        Returns:
            A `google.genai.Client` configured for that region.
        """
        return Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=region,
            http_options=types.HttpOptions(
                headers=self._tracking_headers,
                retry_options=self.retry_options,
            ),
        )

    def _set_active_region(self, region: str) -> None:
        """Switch the active region and invalidate cached client/backend.

        The base class declares `api_client` and `_api_backend` as
        `cached_property`, both of which store their value in `self.__dict__`.
        Popping those keys forces the overridden `api_client` (below) to
        rebuild against the new region on the next access.

        Args:
            region: The region name to make active.
        """
        self._active_region = region
        self.__dict__.pop("api_client", None)
        self.__dict__.pop("_api_backend", None)

    @property
    def api_client(self) -> Client:
        """Return the Vertex AI Client for the currently active region.

        Overrides the base class `cached_property` so the client tracks the
        active region across failover. Within one attempt the result is
        memoised in `self.__dict__["api_client"]`, so downstream accesses
        within the same `super().generate_content_async()` call reuse it.
        """
        cached = self.__dict__.get("api_client")
        if cached is not None:
            return cached
        client = self._build_client_for(self._active_region)
        self.__dict__["api_client"] = client
        return client

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Send a request to Gemini, failing over on 429 OR silent hang.

        Each region attempt is wrapped in `asyncio.wait_for(timeout=
        PER_ATTEMPT_TIMEOUT_S)`. On `RESOURCE_EXHAUSTED` 429, the next region
        is tried (existing failover behavior). On `asyncio.TimeoutError` (a
        Vertex AI call that never returns), `wait_for` cancels the in-flight
        coroutine — the SDK's aiohttp client closes the socket on
        `CancelledError` — and the wrapper advances to the next region just
        as it would on a quota error. No two HTTP calls are ever in flight
        for the same wrapper instance.

        Args:
            llm_request: The ADK LlmRequest to send.
            stream: When True, failover and timeout are both bypassed and the
                upstream call is made directly (partial responses cannot be
                safely replayed; timeouts mid-stream would lose chunks).

        Yields:
            LlmResponse: Each response from the upstream call.

        Raises:
            RuntimeError: When every region in `RANKED_REGIONS` exhausts
                (quota or timeout).
            genai.errors.ClientError: When the upstream call raises a non-quota
                client error (re-raised immediately, no failover).
        """
        if stream:
            logger.info(
                "Vertex AI streaming bypass: agent_model=%s region=%s",
                llm_request.model,
                self._active_region,
            )
            async for response in super().generate_content_async(llm_request, stream):
                yield response
            _notify_attempt(self._owner_name, self._active_region, "ok", None)
            return

        last_exc: Exception | None = None
        for region in RANKED_REGIONS:
            self._set_active_region(region)
            logger.info(
                "Vertex AI attempt: agent_model=%s region=%s timeout=%ss",
                llm_request.model,
                region,
                PER_ATTEMPT_TIMEOUT_S,
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
                    _drain_one_attempt(), timeout=PER_ATTEMPT_TIMEOUT_S
                )
                for r in responses:
                    yield r
                _notify_attempt(self._owner_name, region, "ok", None)
                return
            except TimeoutError as exc:
                logger.warning(
                    "Vertex AI silent hang in region=%s after %ss; falling over.",
                    region,
                    PER_ATTEMPT_TIMEOUT_S,
                )
                _notify_attempt(
                    self._owner_name,
                    region,
                    "failover",
                    f"timeout after {PER_ATTEMPT_TIMEOUT_S}s",
                )
                last_exc = exc
            except genai_errors.ClientError as exc:
                if not _is_quota_error(exc):
                    raise
                logger.warning(
                    "Vertex AI 429 in region=%s; falling over. detail=%s",
                    region,
                    exc,
                )
                _notify_attempt(self._owner_name, region, "failover", str(exc))
                last_exc = exc
        raise RuntimeError(
            f"All Vertex AI regions exhausted: {RANKED_REGIONS}"
        ) from last_exc


async def _self_test_failover_loop() -> None:
    """Validate the failover loop by mocking the parent's upstream call.

    Patches `Gemini.generate_content_async` with a stub that raises a quota
    error in the first region and yields a sentinel response in the second.
    Asserts the wrapper walked exactly two regions, yielded the sentinel, and
    fired the registered attempt observer twice (failover then ok). No Vertex
    AI traffic, no GCP credentials required.
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    call_log: list[str] = []
    fake_request = SimpleNamespace(model="gemini-2.5-flash")

    async def mock_parent_call(self, _llm_request, _stream=False):
        call_log.append(self._active_region)
        if self._active_region == RANKED_REGIONS[0]:
            raise genai_errors.ClientError(
                429,
                {
                    "error": {
                        "code": 429,
                        "status": "RESOURCE_EXHAUSTED",
                        "message": "Quota exceeded for model gemini-2.5-flash",
                    }
                },
            )
        yield "FAKE_RESPONSE"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, region: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, region, outcome, err))

    set_attempt_observer(observer)
    try:
        with patch.object(Gemini, "generate_content_async", mock_parent_call):
            wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
            wrapper.set_owner_name("test_agent")
            responses: list = []
            async for response in wrapper.generate_content_async(
                llm_request=fake_request
            ):
                responses.append(response)
    finally:
        set_attempt_observer(None)

    assert call_log == [RANKED_REGIONS[0], RANKED_REGIONS[1]], (
        f"expected first two regions, got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE"], f"expected sentinel, got {responses}"
    assert len(observer_log) == 2, f"expected 2 observer calls, got {observer_log}"
    assert observer_log[0][0] == "test_agent" and observer_log[0][1] == RANKED_REGIONS[0] and observer_log[0][2] == "failover", (
        f"expected first event=failover on region[0], got {observer_log[0]}"
    )
    assert observer_log[1][0] == "test_agent" and observer_log[1][1] == RANKED_REGIONS[1] and observer_log[1][2] == "ok" and observer_log[1][3] is None, (
        f"expected second event=ok on region[1] with no err, got {observer_log[1]}"
    )
    logger.info(
        "OK: failover loop walked regions=%s, yielded sentinel, observer fired %d times",
        call_log,
        len(observer_log),
    )


async def _self_test_failover_on_timeout() -> None:
    """Validate the failover loop on a silent hang.

    Mocks `Gemini.generate_content_async` so the first region awaits
    `asyncio.Future()` (never resolves; only torn down by `wait_for`'s
    cancellation), then the second region yields a sentinel response.
    Asserts the wrapper times out after `PER_ATTEMPT_TIMEOUT_S`, advances,
    yields the sentinel, and the observer fires twice (timeout-failover
    then ok). No Vertex AI traffic, no GCP credentials required.

    Runtime: roughly equal to `PER_ATTEMPT_TIMEOUT_S` (~10s by default).
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    call_log: list[str] = []
    fake_request = SimpleNamespace(model="gemini-2.5-flash")

    async def mock_parent_call_hang(self, _llm_request, _stream=False):
        call_log.append(self._active_region)
        if self._active_region == RANKED_REGIONS[0]:
            await asyncio.Future()
        yield "FAKE_RESPONSE_AFTER_HANG"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, region: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, region, outcome, err))

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

    assert call_log == [RANKED_REGIONS[0], RANKED_REGIONS[1]], (
        f"expected two regions (hang then ok), got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE_AFTER_HANG"], (
        f"expected sentinel from region 1, got {responses}"
    )
    assert len(observer_log) == 2, f"expected 2 observer calls, got {observer_log}"
    assert (
        observer_log[0][0] == "test_agent_hang"
        and observer_log[0][1] == RANKED_REGIONS[0]
        and observer_log[0][2] == "failover"
        and "timeout" in (observer_log[0][3] or "").lower()
    ), f"expected first event=failover with timeout msg, got {observer_log[0]}"
    assert (
        observer_log[1][0] == "test_agent_hang"
        and observer_log[1][1] == RANKED_REGIONS[1]
        and observer_log[1][2] == "ok"
        and observer_log[1][3] is None
    ), f"expected second event=ok with no err, got {observer_log[1]}"
    logger.info(
        "OK: hang test walked regions=%s, yielded sentinel, observer fired %d times",
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

    asyncio.run(_self_test_failover_loop())
    asyncio.run(_self_test_failover_on_timeout())
