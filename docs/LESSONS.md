# Lessons & Trade-offs

A handful of non-obvious decisions worth surfacing for anyone reading the
code or forking the project.

## MCP Toolbox vs direct BigQuery MCP

The endpoint `https://bigquery.googleapis.com/mcp` returns 403 /
connection-closed when called from a Cloud Run-hosted ADK agent. The MCP
Toolbox for Databases (a small Cloud Run service that wraps a
`tools.yaml` of parameterized SQL queries) is the proven workaround.

We use 2 universal parameterized toolset entries on the network side:

- `query_network_events(region, severity, event_type, days_back, limit)`
- `query_affected_customers_summary(region, days_back)`

Plus one analytical rollup that exploits BigQuery partitioning:

- `weekly_outage_trend(region, weeks_back)` — partition-prunes the scan
  to ~25 KB for a 12-week window

Sentinel defaults (`"*"` for strings, `36500` for `days_back`, `50` for
`limit`) skip a filter without nullable binds — toolbox v0.23 + the
BigQuery Go client both reject null parameter binds at different
validation steps.

**Phase 10 collapsed the network side from 8 hardcoded per-city tools**
into the 2 universal tools above, so adding a new region is now a CSV
change, not a `tools.yaml` edit + toolbox redeploy.

## Vertex AI failover that actually relieves quota pressure

The first iteration was a static `us-central1` pin (most-contested DSQ
pool — 429s at peak APAC hours). Iteration 2 added a multi-continent
region ladder (`global → us-central1 → europe-west4 → asia-northeast1`)
on 429 / 10s timeout.

**Phase 12 replaced the region ladder with a model ladder** because
preview models like `gemini-3.1-flash-lite-preview` are gated to
`global` only on this project — the region ladder always 404'd on the
first failover hop, surfacing every 429 as a hard demo failure.

The new shape: single `global` endpoint, 4-attempt schedule across
**models**:

| # | model                     | timeout | pre-sleep |
|---|---------------------------|---------|-----------|
| 1 | primary                   | 10s     | 0s        |
| 2 | primary                   | 20s     | 0.5s      |
| 3 | `gemini-3-flash-preview`  | 20s     | 0s        |
| 4 | `gemini-2.5-flash`        | 30s     | 0s        |

Worst-case per agent: 80.5s. Attempts 1–2 give the same-model retry a
fair shake (Vertex's dynamic shared quota pool typically replenishes
within a second). Attempt 3 swaps to a sibling preview-tier flash model
with its own quota bucket before collapsing to attempt 4's GA fallback,
so a single contested DSQ pool doesn't sink the run. The 10s attempt-1
timeout is critical — without it a stuck TCP socket hangs the full
Cloud Run 300s window.

The lesson: failover is only as good as the **destination's
availability for your model** — across regions when the model is
multi-region, across models when the model is regionally gated.

See [`telecom_ops/vertex_failover.py`](../telecom_ops/vertex_failover.py)
`ATTEMPT_SCHEDULE`.

## Two-tier CDR analyzer: parameterized SQL primary, NL2SQL fallback

The CDR analyzer was originally a single-tool agent calling `query_cdr_nl`,
which routes through `alloydb_ai_nl.execute_nl_query` to translate English
into SQL. It worked, but production traces showed wide latency variance:

| run | preset window | total e2e | NL2SQL gap |
|---|---|---|---|
| 81 | Makassar last 7 days   | 75 s  | 67 s |
| 82 | Yogyakarta this week   | 15 s  | 4 s  |
| 83 | Bandung last 7 days    | 75 s  | 67 s |
| 84 | Balikpapan this week   | 140 s | 131 s |
| 85 | Jakarta last 14 days   | 16 s  | 7 s |

The 4–131 s spread isn't ours to fix. AlloyDB AI calls Vertex from the
AlloyDB instance's own region (`us-central1`) using `gemini-2.5-flash`, and
Vertex's dynamic shared quota retries inside the translator are invisible
to our `RegionFailoverGemini` wrapper. The slow tail is the whole reason
the path is unsuitable as the hot path.

**The fix isn't to optimize NL2SQL — it's to box it.** Two parameterized
tools cover the structured shape the demo presets produce:

- `query_cdr_summary(region, days_back)` — row-count breakdown grouped by
  `(call_type, call_status)`.
- `query_cdr_worst_towers(region, days_back, limit)` — top-N towers by
  `(dropped + failed) / total`.

`CDR_ANALYZER_INSTRUCTION` encodes a window-mapping table ("this week" →
`days_back=7`, "last 14 days" → `days_back=14`, etc.) so the agent extracts
args deterministically and `query_cdr_nl` is reached only when the prompt
shape requires it (weekend-vs-weekday comparisons, duration thresholds,
custom joins).

After the change, the same five preset runs land in 9.8–20.8 s with
max-gap 1.1–2.0 s — pure SQL execution, no LLM-in-AlloyDB. The two slower
runs are environmental (Vertex 429 storms hitting the agent's *own*
`gemini-3.1-flash-lite-preview`), not CDR-related.

The lesson: when you rely on a managed AI service whose internal retry
behavior is opaque, **measure the tail, not the median**. NL2SQL is a
real capability; using it as the hot path makes you ship the tail. The
two-tier design preserves the capability while shipping the median.

## NL2SQL on AlloyDB AI: native adapter avoided

Toolbox v0.23.0's native `kind: alloydb-ai-nl` adapter always emits
`param_names => ARRAY[]::TEXT[], param_values => ARRAY[]::TEXT[]` when
no `nlConfigParameters:` are declared, and AlloyDB AI rejects empty
text-arrays with `SQLSTATE P0001 — Invalid PSV named parameters`.

The workaround is to drop the native adapter and call `execute_nl_query`
directly via `kind: postgres-sql`:

```sql
SELECT alloydb_ai_nl.execute_nl_query('netpulse_cdr_config', $1) AS result
```

Function-default NULLs land where they should and PSV is bypassed.

Two related gotchas that bit during setup:

- **AlloyDB AI silently ignores `default_llm_model`** unless the model
  ID also appears in `google_ml.model_info_view`. We register
  `gemini-2.5-flash:generateContent` via `google_ml.create_model` and
  bind via `g_manage_configuration(operation => 'change_model', ...)`.
  Both steps live in
  [`scripts/setup_alloydb_nl.py`](../scripts/setup_alloydb_nl.py).
- **Don't use `gemini-3.1-flash-lite-preview` as the NL2SQL backend** —
  it's `global`-only on this project, and AlloyDB AI calls Vertex from
  the AlloyDB instance's own region (us-central1).

## Read-only NL2SQL is structural, not prompt-based

The toolbox connects to AlloyDB as `netpulse_nl_reader` (created by
`setup_alloydb_nl.py:create_reader_role`), which has only `SELECT` on
`public.call_records` and `EXECUTE` on the `alloydb_ai_nl` helper
functions.

Even if the LLM emits `DROP TABLE`, the role lacks the privilege so
the call errors out cleanly. The `alloydb-cdr` source in `tools.yaml`
carries an explicit comment forbidding the `postgres` superuser bypass
— that bypass would defeat the protection and is the kind of "fix" that
silently re-opens the door.

## Async ADK Runner ↔ sync Flask

`runner.run_async()` is async-only, but Flask is sync. The naive
`asyncio.run()` wrapper buffers all events into a list before yielding
the first byte, breaking the chat-card animation.

The fix in
[`netpulse-ui/agent_runner.py`](../netpulse-ui/agent_runner.py) is a
per-request worker thread running its own asyncio loop and pushing
converted events onto a `queue.Queue` that the SSE generator drains in
real time.

## Eager-init singletons + degradation under partial failure

The agent's `tools.py` instantiates the MCP Toolbox client and the
AlloyDB engine at module import. The toolbox client is wrapped in
`try/except` (so the agent boots even if the toolbox is cold). The
AlloyDB engine uses `pool_pre_ping=True` + `pool_recycle=300` to
survive connection-pool staleness when the dev box goes idle for 30+
minutes between demos.

Both engines (`telecom_ops/tools.py`, `netpulse-ui/data_queries.py`)
need `pool_recycle=300` — without it, idle connections silently die
after ~30 minutes and the next query hangs forever on a half-dead
socket.

## Defensive prompt substitution

All cross-agent state references in `prompts.py` use ADK's `{key?}`
optional syntax. If an upstream agent fails before populating its
`output_key`, downstream agents still get a graceful empty string
instead of crashing on a `KeyError` during instruction formatting.

## Two frontends, one engine

The ADK Dev UI gives free `/events` and `/trace` tabs. Building a
custom UI doesn't replace it; it complements it.

- The **NetPulse UI** is the *demo* surface (branded, animated, narrated).
- The **ADK Dev UI** is the *debug* surface (every span, every value).

Both call the same `Runner + InMemorySessionService + root_agent`. One
engine, two views, no duplicated orchestration.
