"""Failover ladder tests for `telecom_ops/vertex_failover.py`.

Gemini is mocked at `Gemini.generate_content_async`, so no test touches the
network or needs Vertex credentials. The module is imported as a top-level
module from `telecom_ops/` (the same way the former in-file self-tests ran),
so importing it does not pull in `telecom_ops/__init__.py`, the agent, or the
MCP Toolbox client.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "telecom_ops"))

from google.adk.models.google_llm import Gemini  # noqa: E402
from google.genai import errors as genai_errors  # noqa: E402

from vertex_failover import (  # noqa: E402
    FALLBACK_MODEL,
    INTERMEDIATE_MODEL,
    RegionFailoverGemini,
    _is_model_gone_error,
    _is_quota_error,
    set_attempt_observer,
)

logger = logging.getLogger(__name__)


def test_is_quota_error_matcher() -> None:
    """The quota matcher accepts 429 / RESOURCE_EXHAUSTED shapes only."""
    assert _is_quota_error(Exception("RESOURCE_EXHAUSTED: quota"))
    assert _is_quota_error(Exception("HTTP 429 Too Many Requests"))
    assert _is_quota_error(Exception("Quota exceeded"))
    assert not _is_quota_error(Exception("INVALID_ARGUMENT: bad model"))
    assert not _is_quota_error(Exception("PERMISSION_DENIED"))


def test_is_model_gone_error_matcher() -> None:
    """The model-gone matcher accepts 404 NOT_FOUND shapes only."""
    assert _is_model_gone_error(Exception("404 NOT_FOUND: Publisher model"))
    assert _is_model_gone_error(
        Exception("Publisher Model `x` was not_found")
    )
    assert not _is_model_gone_error(Exception("INVALID_ARGUMENT: bad model"))
    assert not _is_model_gone_error(Exception("HTTP 429 Too Many Requests"))


async def _self_test_quota_retry_same_model() -> None:
    """Verify attempt 1 quota-fails and attempt 2 succeeds on the SAME primary.

    Mocks `Gemini.generate_content_async` so the first call raises a 429
    and the second yields a sentinel. Asserts the wrapper called the
    primary model twice, yielded the sentinel, and the observer fired
    twice (failover-on-primary then ok-on-primary). Verifies the no-swap
    behavior of attempts 1 to 2.

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


async def _self_test_retired_primary_404_swaps_to_intermediate() -> None:
    """Verify a 404-retired primary walks the ladder instead of hard-failing.

    Mocks `Gemini.generate_content_async` to raise 404 NOT_FOUND whenever
    the request targets the primary (simulating Google retiring the model
    id under a deployed image) and yield a sentinel for any other model.
    Asserts the wrapper walked [primary, primary, INTERMEDIATE_MODEL],
    yielded the sentinel from the intermediate, and the observer fired
    three times (two failovers on the primary, one ok). This is the
    2026-07-23 outage path: model retirement degrades to a failover hop.

    Runtime: ~0.5s (inter-attempt sleep on attempt 2).
    """
    from types import SimpleNamespace
    from unittest.mock import patch

    primary = "gemini-3.1-flash-lite"
    call_log: list[str] = []
    fake_request = SimpleNamespace(model=primary)

    async def mock_parent_call(self, llm_request, _stream=False):
        call_log.append(llm_request.model)
        if llm_request.model == primary:
            raise genai_errors.ClientError(
                404,
                {
                    "error": {
                        "code": 404,
                        "status": "NOT_FOUND",
                        "message": (
                            f"Publisher Model `{llm_request.model}` was "
                            "not found or your project does not have "
                            "access to it."
                        ),
                    }
                },
            )
        yield "FAKE_RESPONSE_FROM_INTERMEDIATE"

    os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "test-project")

    observer_log: list[tuple[str, str, str, str | None]] = []

    def observer(owner: str, model: str, outcome: str, err: str | None) -> None:
        observer_log.append((owner, model, outcome, err))

    set_attempt_observer(observer)
    try:
        with patch.object(Gemini, "generate_content_async", mock_parent_call):
            wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
            wrapper.set_owner_name("test_agent_gone")
            responses: list = []
            async for response in wrapper.generate_content_async(
                llm_request=fake_request
            ):
                responses.append(response)
    finally:
        set_attempt_observer(None)

    assert call_log == [primary, primary, INTERMEDIATE_MODEL], (
        f"expected primary x2 then intermediate, got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE_FROM_INTERMEDIATE"], (
        f"expected sentinel from intermediate, got {responses}"
    )
    assert len(observer_log) == 3, f"expected 3 observer calls, got {observer_log}"
    assert (
        observer_log[0][1] == primary and observer_log[0][2] == "failover"
        and observer_log[1][1] == primary and observer_log[1][2] == "failover"
        and "NOT_FOUND" in (observer_log[0][3] or "")
    ), f"expected two 404 failovers on primary, got {observer_log[:2]}"
    assert observer_log[2] == (
        "test_agent_gone", INTERMEDIATE_MODEL, "ok", None
    ), f"expected ok on intermediate, got {observer_log[2]}"
    logger.info(
        "OK: retired-primary 404 walked %s, fired observer %d times",
        call_log,
        len(observer_log),
    )


def test_quota_retry_same_model() -> None:
    """Attempt 1 quota-fails, attempt 2 succeeds on the same primary."""
    asyncio.run(_self_test_quota_retry_same_model())


def test_timeout_retry_same_model() -> None:
    """Attempt 1 hangs past its timeout, attempt 2 succeeds on the primary."""
    asyncio.run(_self_test_timeout_retry_same_model())


def test_persistent_429_swaps_to_fallback() -> None:
    """Sustained 429s walk the full ladder to the fallback model."""
    asyncio.run(_self_test_persistent_429_swaps_to_fallback())


def test_retired_primary_404_swaps_to_intermediate() -> None:
    """A 404-retired primary advances to the intermediate model."""
    asyncio.run(_self_test_retired_primary_404_swaps_to_intermediate())
