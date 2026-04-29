"""Vertex AI region failover wrapper for ADK Gemini.

The default region is `global` (Google's multi-region routing pool); on a
`RESOURCE_EXHAUSTED` 429, the wrapper rebuilds its underlying `genai.Client`
against the next region in `RANKED_REGIONS` and retries. Failover state is
per-instance, so each `LlmAgent` walks the ladder independently.
"""

import logging
import os
from collections.abc import AsyncGenerator

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import Client
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import PrivateAttr

logger = logging.getLogger(__name__)

RANKED_REGIONS: tuple[str, ...] = (
    "global",
    "asia-southeast2",
    "asia-southeast1",
    "us-central1",
)

_QUOTA_MARKERS: tuple[str, ...] = ("RESOURCE_EXHAUSTED", " 429", "QUOTA")


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
        """Send a request to Gemini, failing over through ranked regions on 429.

        Args:
            llm_request: The ADK LlmRequest to send.
            stream: When True, failover is bypassed and the upstream call is
                made directly (partial responses cannot be safely replayed).

        Yields:
            LlmResponse: Each response from the upstream call.

        Raises:
            RuntimeError: When every region in `RANKED_REGIONS` returns a quota
                error.
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
            return

        last_exc: Exception | None = None
        for region in RANKED_REGIONS:
            self._set_active_region(region)
            logger.info(
                "Vertex AI attempt: agent_model=%s region=%s",
                llm_request.model,
                region,
            )
            try:
                async for response in super().generate_content_async(
                    llm_request, stream
                ):
                    yield response
                return
            except genai_errors.ClientError as exc:
                if not _is_quota_error(exc):
                    raise
                logger.warning(
                    "Vertex AI 429 in region=%s; falling over. detail=%s",
                    region,
                    exc,
                )
                last_exc = exc
        raise RuntimeError(
            f"All Vertex AI regions exhausted: {RANKED_REGIONS}"
        ) from last_exc


async def _self_test_failover_loop() -> None:
    """Validate the failover loop by mocking the parent's upstream call.

    Patches `Gemini.generate_content_async` with a stub that raises a quota
    error in the first region and yields a sentinel response in the second.
    Asserts the wrapper walked exactly two regions and yielded the sentinel.
    No Vertex AI traffic, no GCP credentials required.
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

    with patch.object(Gemini, "generate_content_async", mock_parent_call):
        wrapper = RegionFailoverGemini(model="gemini-2.5-flash")
        responses: list = []
        async for response in wrapper.generate_content_async(llm_request=fake_request):
            responses.append(response)

    assert call_log == [RANKED_REGIONS[0], RANKED_REGIONS[1]], (
        f"expected first two regions, got {call_log}"
    )
    assert responses == ["FAKE_RESPONSE"], f"expected sentinel, got {responses}"
    logger.info(
        "OK: failover loop walked regions=%s and yielded sentinel after one 429",
        call_log,
    )


if __name__ == "__main__":
    import asyncio

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    assert _is_quota_error(Exception("RESOURCE_EXHAUSTED: quota"))
    assert _is_quota_error(Exception("HTTP 429 Too Many Requests"))
    assert _is_quota_error(Exception("Quota exceeded"))
    assert not _is_quota_error(Exception("INVALID_ARGUMENT: bad model"))
    assert not _is_quota_error(Exception("PERMISSION_DENIED"))
    logger.info("OK: _is_quota_error matcher passes 5/5 cases")

    asyncio.run(_self_test_failover_loop())
