# NetPulse AI — Vertex AI region failover

## Context

The NetPulse AI hackathon submission currently pins `GOOGLE_CLOUD_LOCATION=asia-southeast1` as a static fix for the `RESOURCE_EXHAUSTED` 429 errors that hit Gemini 2.5 Flash in `us-central1` due to Vertex AI's Dynamic Shared Quota (DSQ) contention. That fix works but is fragile: a single region with a single trial-billing project has no headroom if `asia-southeast1` ever spikes.

A read-only audit of the user's `heliodoron-interio` production codebase (a separate GCP project under `adityonugroho@heliodoron.com`) surfaced two new pieces of information:

1. **Vertex AI exposes a `locations/global` endpoint** — Google's multi-region routing pool that draws from any region with capacity. `heliodoron-interio` uses this as its default (`docs/SPEC.md:472,878`, `vertex-test/04-render-pipeline.py:27`). Trade-off: no per-region quota guarantee, but a much larger shared pool.
2. **`asia-southeast2` (Jakarta) is the geographic and quota-contention optimum for Indonesian traffic** — heliodoron's battery-invoicing research (`verticals/battery-invoicing/research/01-findings-battery-invoicing.md:5-7`) cites GR71 data-residency, 15-30ms Surabaya→Jakarta latency, and lower commercial contention than Singapore.

Goal of this change: switch the default to `global`, then add a retry layer that falls back through a ranked list of regions on `RESOURCE_EXHAUSTED`. Failure becomes degradation (one extra hop) instead of a hard 500.

Per-agent failover state is the key correctness property: if `classifier` succeeds in `global`, that does not commit `network_investigator` to `global` — each `LlmAgent` independently walks the ranked list as needed.

## Goal

1. Default Vertex AI location → `global`.
2. Catch `RESOURCE_EXHAUSTED` on each LlmAgent's model call and retry with the next region in a ranked fallback list.
3. Per-LlmAgent failover state, fresh per request.
4. Zero functional change to the chat UX, the SSE event stream contract, or the existing AlloyDB / BigQuery / MCP code paths.

## Approach (one paragraph)

Subclass ADK's `google.adk.models.google_llm.Gemini` with a new `RegionFailoverGemini` that (a) overrides `api_client` to build the underlying `genai.Client` with an explicit `location=` argument that we control, and (b) overrides `generate_content_async` to wrap the upstream call in a try/except loop over the ranked region list, catching `RESOURCE_EXHAUSTED` and rebuilding the client for the next region. Each `LlmAgent` in `telecom_ops/agent.py` switches from `model="gemini-2.5-flash"` (string) to `model=RegionFailoverGemini(model="gemini-2.5-flash")` so each agent owns an independent failover state. Update `telecom_ops/.env` and the README's Cloud Run deploy snippet to set `GOOGLE_CLOUD_LOCATION=global` as the new entry-point default. The retry is safe because `generate_content_async` is a single HTTP call with no tool execution inside it — there is no risk of duplicate `save_incident_ticket` writes from a retry.

## Files to modify

### NEW — `telecom_ops/vertex_failover.py`

A small module (~80 lines) wrapping ADK's `Gemini`. Skeleton with the load-bearing details:

```python
"""Vertex AI region failover wrapper for ADK Gemini.

Default region is `global`; on RESOURCE_EXHAUSTED, walks a ranked fallback
list. State is per-instance, so each LlmAgent fails over independently.
"""

import logging
import os
from typing import AsyncGenerator

from google.adk.models.google_llm import Gemini
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse
from google.genai import Client
from google.genai import errors as genai_errors
from google.genai import types

logger = logging.getLogger(__name__)

RANKED_REGIONS: tuple[str, ...] = (
    "global",
    "asia-southeast2",
    "asia-southeast1",
    "us-central1",
)


def _is_quota_error(exc: Exception) -> bool:
    """True iff exc represents Vertex AI quota exhaustion (429)."""
    msg = str(exc).upper()
    return "RESOURCE_EXHAUSTED" in msg or " 429" in msg or "QUOTA" in msg


class RegionFailoverGemini(Gemini):
    """ADK Gemini that fails over through ranked Vertex AI regions on 429.

    Each request starts at `RANKED_REGIONS[0]`. On `RESOURCE_EXHAUSTED`, the
    underlying `genai.Client` is rebuilt with the next region and the call
    is retried. Region state is per-instance — each `LlmAgent` owns its own.

    The retry happens before any tool call, so there is no duplicate-write
    risk for tools like `save_incident_ticket`.
    """

    # Use Pydantic PrivateAttr (or a class-level instance dict workaround) for
    # mutable failover state — see "Implementation notes" below.

    def _build_client(self, region: str) -> Client:
        """Build a fresh Vertex AI Client pinned to a specific region."""
        return Client(
            vertexai=True,
            project=os.environ["GOOGLE_CLOUD_PROJECT"],
            location=region,
            http_options=types.HttpOptions(
                headers=self._tracking_headers,
                retry_options=self.retry_options,
            ),
        )

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        """Call Gemini with region failover on RESOURCE_EXHAUSTED."""
        last_exc: Exception | None = None
        for region in RANKED_REGIONS:
            self._set_active_region(region)  # rebuilds api_client on next access
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
                return  # success
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
```

Implementation notes for the implementer:

- **ADK's `Gemini` is a Pydantic v2 `BaseModel`.** Mutable per-instance state (`_active_region`, `_cached_client`) must be declared via `PrivateAttr` or stored in the instance `__dict__` with a small property shim. The base class declares `api_client` as `@cached_property`; the subclass needs to either invalidate the cache between attempts or override with a plain `@property` that consults the active region. Both are workable; pick whichever is cleaner once Pydantic constraints are nailed down.
- **`generate_content_async` is one HTTP call** (no tool execution between yields), so retrying after the first iteration of the for-loop is side-effect-free — confirmed by reading `google_llm.py:99-163`.
- **Do not mutate `os.environ`.** Pass `location=` explicitly to `Client(...)`. The Flask app is multi-threaded; env mutation would race.
- **`genai_errors.ClientError`** is the SDK's catch-all for HTTP 4xx (including 429). String-match `RESOURCE_EXHAUSTED` / `QUOTA` / ` 429` to distinguish quota errors from other client errors. Add a regression test for the matcher when the implementer touches it.
- **Logging**: use Python `logging`, not `print` (per global Python rules at `~/.claude/rules/python.md`). Each attempt logs a single INFO line with `region`; a failover logs a WARN with the previous region.
- **Python rules compliance**: native type hints (`tuple[str, ...]`, `Exception | None`), Google-style docstrings, constants UPPER_SNAKE_CASE, dataclass for any structured config (none needed here), `if __name__ == "__main__"` if a CLI entry point is added (none planned).

### MODIFY — `telecom_ops/agent.py`

Replace the four `LlmAgent(model=MODEL, ...)` calls so each agent gets its own `RegionFailoverGemini` instance:

```python
from .vertex_failover import RegionFailoverGemini

MODEL_NAME = "gemini-2.5-flash"


def _failover_model() -> RegionFailoverGemini:
    """Build a fresh failover-enabled Gemini wrapper for one LlmAgent."""
    return RegionFailoverGemini(model=MODEL_NAME)


classifier = LlmAgent(
    model=_failover_model(),
    name="classifier",
    ...  # rest unchanged
)
# same for network_investigator, cdr_analyzer, response_formatter
```

This keeps `gemini-2.5-flash` as the model name in one place and gives each agent an independent `RegionFailoverGemini` instance (so failover state is per-agent). The `SequentialAgent` root composition does not change.

### MODIFY — `telecom_ops/.env`

```
GOOGLE_GENAI_USE_VERTEXAI=TRUE
GOOGLE_CLOUD_PROJECT=plated-complex-491512-n6
GOOGLE_CLOUD_LOCATION=global
```

(Single line change: `asia-southeast1` → `global`.)

### MODIFY — `README.md`

Update the Cloud Run deploy snippet (currently around line 377) to:

```bash
--set-env-vars="GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=plated-complex-491512-n6,GOOGLE_CLOUD_LOCATION=global"
```

If there's any narrative text near it that says "pinned to asia-southeast1 to avoid DSQ", replace with a brief note about the new default + failover ladder.

### MODIFY — `CLAUDE.md` (project-level)

The "Non-obvious choices to preserve" section currently says:

> **Vertex AI region pinned to `asia-southeast1`** via `GOOGLE_CLOUD_LOCATION`. Vertex's Dynamic Shared Quota on the Gemini 2.5 GA models triggered `RESOURCE_EXHAUSTED` 429s in `us-central1` for APAC traffic during the hackathon window. APAC region was the verified fix. Don't switch back without checking quota state.

Replace with a paragraph that documents (a) the new `global` default, (b) the ranked failover ladder in `vertex_failover.py`, and (c) the residual note that `us-central1` alone (no failover) is the failure mode to avoid.

### NO CHANGE — files explicitly verified independent

- `netpulse-ui/agent_runner.py` — the Runner sees the same async generator from `LlmAgent.generate_content_async`; the failover is invisible at this layer.
- `netpulse-ui/data_queries.py` — BigQuery + AlloyDB calls do not consume `GOOGLE_CLOUD_LOCATION` (project-scoped).
- `telecom_ops/tools.py` — same; project-scoped only.
- `Dockerfile` (parent) — runtime env vars come from Cloud Run `--set-env-vars`, not the image.
- Cloud Run service deploy regions (us-central1) — Cloud Run service location is independent of Vertex AI inference location.

## Region ranking rationale

| # | Region | Rationale |
|---|---|---|
| 1 | `global` | Google's multi-region routing pool. Witnessed in `heliodoron-interio` (`docs/SPEC.md:472,878`) as their default. Pulls from the broadest capacity pool. No per-region quota guarantee, but the largest shared pool. |
| 2 | `asia-southeast2` (Jakarta) | Geographic optimum for Indonesian users (15-30ms from Surabaya per `heliodoron/verticals/battery-invoicing/research/01-findings-battery-invoicing.md:5-7`). Lower commercial contention than Singapore. Satisfies GR71 residency. |
| 3 | `asia-southeast1` (Singapore) | The original verified DSQ fix on this hackathon project. Proven to work for our exact workload. APAC alternative if Jakarta is also exhausted. |
| 4 | `us-central1` (Iowa) | The original failing region. Last resort — but a degraded response is better than a hard 500. Default Cloud Run region for the codebase, so co-location latency from the deployed services is best here. |

## Verification

Three layers, in order:

### 1. Unit-level — `_is_quota_error` matcher

Quick standalone Python test (can sit in `telecom_ops/vertex_failover.py` under `if __name__ == "__main__":` or a `tests/` file):

```python
from telecom_ops.vertex_failover import _is_quota_error

assert _is_quota_error(Exception("RESOURCE_EXHAUSTED: quota"))
assert _is_quota_error(Exception("HTTP 429 Too Many Requests"))
assert _is_quota_error(Exception("Quota exceeded"))
assert not _is_quota_error(Exception("INVALID_ARGUMENT: bad model"))
assert not _is_quota_error(Exception("PERMISSION_DENIED"))
```

### 2. Integration-level — forced failover via injected bad regions

Temporarily monkeypatch `RANKED_REGIONS` (or expose it as a class attribute the test can override) to put an obviously-invalid region first, then a valid one. Run a single LlmAgent call and confirm:

- The first region attempt logs a WARN with `falling over`.
- The second region attempt succeeds.
- The final response is identical to the success-without-failover baseline.

```python
# Conceptual; implementer fills in
from telecom_ops.vertex_failover import RegionFailoverGemini
RegionFailoverGemini.RANKED_REGIONS = ("us-east-99", "global")  # noqa
# ... drive one LlmAgent call ...
```

### 3. End-to-end — chat invocation

Run the Flask app locally:

```bash
cd /home/adityonugrohoid/projects/hackathon-telecom-ops/netpulse-ui
/home/adityonugrohoid/projects/hackathon-telecom-ops/.venv/bin/python app.py
```

Open `http://localhost:8080`, run an example complaint, watch:

- 4 cards transition `waiting → running → done` as before (no UX regression).
- Server logs include `Vertex AI attempt: agent_model=gemini-2.5-flash region=global` for each agent on the happy path.
- Final ticket lands in AlloyDB.

Cross-check independent of UI:

```bash
curl -N -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Customer reports failed calls in Jakarta"}'
```

Events stream incrementally; logs show one INFO per agent at `region=global`.

### 4. Sanity — health-check the deployed services after deploy

After applying the env-var change to Cloud Run (manual step, user runs):

```bash
for u in \
  https://telecom-classifier-486319900424.us-central1.run.app \
  https://network-status-agent-486319900424.us-central1.run.app \
  https://telecom-cdr-app-486319900424.us-central1.run.app \
  https://netpulse-ui-486319900424.us-central1.run.app; do
  curl -s -o /dev/null -w "%{http_code} %s\n" --max-time 75 "$u"; done
```

All four should return 2xx/3xx.

## Known limitations & risks

1. **Streaming retries.** `generate_content_async(stream=True)` would yield partial responses before the 429 hits, and a retry would replay from the start — duplicate output. NetPulse uses `stream=False` for the SequentialAgent flow, so this is not a hackathon concern, but the wrapper should refuse to retry under `stream=True` (or document it as unsupported and only use the wrapper for non-streaming agents).
2. **Region cold-start.** First call to `global` (or any new region) may add 2-5s cold-start latency. Subsequent calls amortize. The chat UX already tolerates 5-10s per agent, so this is within the existing latency envelope.
3. **Quota-error detection via string matching.** Relies on `RESOURCE_EXHAUSTED` / `QUOTA` / ` 429` substrings in the exception message. Brittle across SDK upgrades — pin a regression test that asserts current ADK 1.14.0 / google-genai 1.70.0 raise messages match. Revisit on any `google-genai` version bump.
4. **Per-agent ladder traversal.** Each agent independently walks the full ladder. If `global` is broadly out, every agent eats one 429 + cold-start before settling on the next region (4 agents × 1 wasted call = ~5-10s extra). Acceptable for hackathon demo. Future work: a "sticky" region cache keyed by (project, model) that all agents consult.
5. **Pydantic v2 mutable state.** ADK's `Gemini` is a `pydantic.BaseModel`. Adding mutable per-instance state (`_active_region`, `_cached_client`) needs `PrivateAttr` or `model_config = ConfigDict(arbitrary_types_allowed=True, frozen=False)`. Implementer should test this works before wiring into agent.py.
6. **Process-global env mutation forbidden.** The wrapper passes `location=` directly to `Client(...)`. We do NOT mutate `os.environ` mid-flight. Multi-threaded Flask is safe.
7. **The `cached_property` override.** ADK's base class declares `api_client` as `@cached_property`. The subclass must either override with a plain `@property` (slight overhead, always rebuilds — acceptable) or invalidate the descriptor cache by `del self.__dict__['api_client']` between attempts. Pick one in implementation.
8. **`global` endpoint behavior under sustained load.** Untested in our own infra. heliodoron-interio uses it but has no production traffic yet. Could regress vs. `asia-southeast1` static pin under sustained chat load. Mitigation: the failover ladder catches it.
9. **Frozen-resource compliance.** All edits are within `telecom_ops/` source code and `telecom_ops/.env`. No `gcloud services enable`, no IAM changes, no Cloud Run service `delete` / `update` outside the `--set-env-vars` redeploy that the user runs manually. Freeze A is preserved as long as the redeploy happens via the user's hand, not an assistant-issued command.

## Out of scope

- `netpulse-ui/data_queries.py` (BigQuery / AlloyDB are location-independent).
- Telemetry: emitting per-attempt region as a UI event for demo storytelling. Optional polish — could be added by extending `AgentEvent` with an optional `region` field and emitting on each attempt.
- Idempotency keys on `save_incident_ticket`. Not needed because retries occur before tool execution.
- Auto-deploy. The user redeploys manually via the existing `gcloud run deploy ... --set-env-vars=...` flow.
- Memory updates to `~/.claude/memory/reference_vertex_ai_dsq.md` to capture the new ranked-list strategy. Separate task — should run alongside this implementation.
- Multi-region support for non-Vertex services (BigQuery dataset, AlloyDB cluster). Both stay in `us-central1` / Iowa as today; only Vertex AI inference gets the failover.

## Implementation order

1. Write `telecom_ops/vertex_failover.py` with the matcher unit-test under `if __name__ == "__main__":`.
2. Run `python -m telecom_ops.vertex_failover` to validate the matcher.
3. Wire `RegionFailoverGemini` into `telecom_ops/agent.py`.
4. Update `telecom_ops/.env` to `GOOGLE_CLOUD_LOCATION=global`.
5. Run integration test (forced failover with bad first region).
6. Run end-to-end via Flask UI.
7. Update `README.md` and project `CLAUDE.md` text.
8. Hand back to the user for the manual Cloud Run redeploy.

## Critical files reference

- **NEW:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/telecom_ops/vertex_failover.py`
- **MODIFY:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/telecom_ops/agent.py` (lines 16-52)
- **MODIFY:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/telecom_ops/.env` (line 3)
- **MODIFY:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/README.md` (~line 377 deploy snippet)
- **MODIFY:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/CLAUDE.md` (Vertex AI region paragraph in "Non-obvious choices to preserve")
- **REFERENCE (read, don't modify):** `/home/adityonugrohoid/projects/hackathon-telecom-ops/.venv/lib/python3.12/site-packages/google/adk/models/google_llm.py` (lines 54-177 — base `Gemini` class)
- **REFERENCE:** `/home/adityonugrohoid/projects/hackathon-telecom-ops/netpulse-ui/agent_runner.py` (no change; the wrapper is invisible here)
