# CLAUDE.md

Project context for AI assistants working on NetPulse AI.

## What this is

NetPulse AI is a multi-agent telecom operations assistant. A natural-language
complaint goes in, a structured incident ticket comes out. Built for the APAC
GenAI Academy 2026 hackathon. See [`README.md`](README.md) for the user-facing
walkthrough.

This repo was built with [Claude Code](https://claude.com/claude-code) — pairing
notes for that work live in this file.

## Architecture in one paragraph

The core ADK package `telecom_ops/` exposes a `SequentialAgent` that runs four
`LlmAgent` sub-agents in order: classifier, network investigator (BigQuery via
MCP Toolbox — `query_network_events`, `query_affected_customers_summary`,
`weekly_outage_trend`), CDR analyzer (AlloyDB via MCP Toolbox in two tiers —
parameterized SQL primary `query_cdr_summary` / `query_cdr_worst_towers`
return in <2s, with `query_cdr_nl` retained as an NL2SQL fallback for
off-script prompts via `alloydb_ai_nl.execute_nl_query` against the
`netpulse_cdr_config`), and response formatter (writes the final ticket
back to AlloyDB). The sibling
Flask service `netpulse-ui/` wraps the same `root_agent` in a hero landing
page (`/`) plus a workspace (`/app`) that renders the agent run as a vertical
timeline, with three read-only data viewer tabs and Server-Sent-Events
streaming. Both deploy to Cloud Run. Each sub-agent picks its own model
through the `RegionFailoverGemini` wrapper in `telecom_ops/vertex_failover.py`
— all four agents currently share `MODEL_FAST = "gemini-3.1-flash-lite-preview"`.
The wrapper targets the single `global` Vertex endpoint and walks a 4-attempt
model ladder on `RESOURCE_EXHAUSTED` 429 or per-attempt `asyncio.TimeoutError`:
primary 10s → primary +0.5s sleep 20s → `gemini-3-flash-preview` intermediate
20s → `gemini-2.5-flash` GA fallback 30s. Each attempt cancels the prior
in-flight call so only one HTTP request is ever live per agent.

## Non-obvious choices to preserve

These look optional but each one is load-bearing:

- **Thread + queue async-to-sync bridge** in `netpulse-ui/agent_runner.py`. Do
  NOT replace with `asyncio.run()`. The naive wrapper drains the entire async
  generator into a list before yielding, which buffers all SSE events and
  breaks the streaming chat UI. Each request runs its own asyncio loop in a
  worker thread and pushes events onto a `queue.Queue`; the Flask SSE
  generator pulls and yields incrementally.

- **`pool_recycle=300` on every SQLAlchemy engine** that points at AlloyDB
  (not just `pool_pre_ping=True`). Without it, idle connections silently die
  after ~30 minutes and the next query hangs forever on a half-dead socket.
  Both `telecom_ops/tools.py` and `netpulse-ui/data_queries.py` set it.

- **Vertex AI model-ladder failover** in `telecom_ops/vertex_failover.py`. All
  requests target `REGION = "global"`. On `RESOURCE_EXHAUSTED` 429 or
  `asyncio.TimeoutError`, the wrapper walks `ATTEMPT_SCHEDULE`:

  | # | model                     | timeout | pre-sleep |
  |---|---------------------------|---------|-----------|
  | 1 | primary                   | 10s     | 0s        |
  | 2 | primary                   | 20s     | 0.5s      |
  | 3 | `gemini-3-flash-preview`  | 20s     | 0s        |
  | 4 | `gemini-2.5-flash`        | 30s     | 0s        |

  Worst-case per agent: 80.5s. The 10s attempt-1 timeout is critical — without
  it a stuck TCP socket hangs the full Cloud Run 300s window. The ladder swaps
  **models**, not regions, because preview models are gated to specific
  regions per project (`gemini-3.1-flash-lite-preview` is `global`-only here,
  so the previous region ladder always 404'd on the first failover hop). The
  intermediate (`gemini-3-flash-preview`) gives a same-tier swap before
  collapsing to GA; each model has its own quota bucket so the GA fallback
  remains a real escape hatch. `agent.py` builds a fresh wrapper per
  `LlmAgent` so the four agents own independent failover state. Streaming
  (`stream=True`) bypasses both ladder AND timeout because partial yields
  cannot be safely replayed; NetPulse uses `stream=False`.

- **Per-agent model selection** in `telecom_ops/agent.py`. Two named
  constants: `MODEL_FAST = "gemini-3.1-flash-lite-preview"` and
  `MODEL_SYNTHESIS = MODEL_FAST` (currently collapsed). Re-splitting is safe
  under the new model ladder since attempt 4's `gemini-2.5-flash` GA fallback
  covers any global-only primary. Revert option:
  `MODEL_SYNTHESIS = "gemini-2.5-pro"` (GA + multi-region) if traces show
  synthesis quality is insufficient.

- **Customer-impact card consumes a JSON-encoded string from MCP toolbox.**
  `netpulse-ui/templates/chat.html:npExtractRows` recurses through both
  `Array` and `string` shapes when walking `tool_response.result`. Reason:
  `toolbox_core/itransport.py` declares `tool_invoke -> str`, and ADK wraps
  non-dict tool returns as `{"result": "<string>"}`. So `result.result` on
  the SSE payload is a JSON-encoded string of the row array, not the array
  itself. Without the recursive `JSON.parse`, the impact card silently
  degrades to `[]`.

- **MCP Toolbox in front of BigQuery**, not the direct BigQuery MCP endpoint.
  The direct endpoint returns 403 / Connection-closed on Cloud Run; the
  toolbox-as-intermediary pattern works.

- **CDR analyzer is two-tier: parameterized SQL primary, NL2SQL fallback.**
  `query_cdr_summary(region, days_back)` and
  `query_cdr_worst_towers(region, days_back, limit)` execute fixed-shape
  aggregations against `call_records` in <2s. `query_cdr_nl(question)` is
  kept as a fallback for off-script prompts the parameterized tools can't
  express (weekend-vs-weekday, duration thresholds, custom joins). The
  agent's prompt encodes the dispatch in `prompts.CDR_ANALYZER_INSTRUCTION`
  with a window-mapping table ("last 7 days" → `days_back=7`, etc.) so the
  fast path is deterministic when the prompt has a clear region + window.
  Reason for the split: NL2SQL tail latency was 30–130s in observed runs
  (Vertex us-central1 retries inside `alloydb_ai_nl.execute_nl_query`
  using `gemini-2.5-flash`), with no visibility from our side. Boxing it
  as fallback bounds the demo path to ~10–15s while keeping NL2SQL as a
  capability for free-form prompts.

- **`query_cdr_nl` uses `kind: postgres-sql`, not `kind: alloydb-ai-nl`.**
  Toolbox v0.23's native alloydb-ai-nl adapter emits
  `param_names => ARRAY[]::TEXT[], param_values => ARRAY[]::TEXT[]` when no
  `nlConfigParameters:` are declared, and AlloyDB AI rejects empty
  text-arrays with `SQLSTATE P0001 — Invalid PSV named parameters`.
  Workaround: drop the native adapter, call `execute_nl_query` directly via
  `kind: postgres-sql`:
  `SELECT alloydb_ai_nl.execute_nl_query('netpulse_cdr_config', $1) AS result`.

- **AlloyDB AI NL2SQL needs the model registered via
  `google_ml.create_model`**, not just `default_llm_model` instance flag. The
  flag is silently ignored unless the model id appears in
  `google_ml.model_info_view`. We register `gemini-2.5-flash:generateContent`
  (GA, accessible in us-central1) and bind via
  `g_manage_configuration(operation => 'change_model', ...)`. Both steps live
  in `scripts/setup_alloydb_nl.py`. Don't use
  `gemini-3.1-flash-lite-preview` here — it's `global`-only and AlloyDB AI
  calls Vertex from the AlloyDB instance's own region (us-central1).

- **Read-only NL2SQL role is structural, not prompt-based.** The toolbox
  connects to AlloyDB as `netpulse_nl_reader` (created by
  `setup_alloydb_nl.py:create_reader_role`), which has only `SELECT` on
  `public.call_records` and `EXECUTE` on the `alloydb_ai_nl` helper
  functions. Even if the LLM emits `DROP TABLE`, the role lacks the
  privilege so the call errors out cleanly. The `alloydb-cdr` source in
  `tools.yaml` carries an explicit comment forbidding the `postgres`
  superuser bypass.

- **`network_events` is DAY-partitioned on `started_at` and clustered by
  `(region, severity)`.** The seed has 50 000 events so the partition gates
  have something to prune. `weekly_outage_trend` relies on partition
  pruning. `setup_bigquery.py --recreate` is the only way to apply the
  partition spec to a pre-existing unpartitioned table — BigQuery does not
  allow partition changes in place. The flag is destructive (drops +
  recreates); pair with `--seed`.

- **Toolbox parameters use sentinel defaults, not nullable binds.** The 2
  universal tools in `tools.yaml` declare every param `required: true` with
  a `default:` sentinel — strings default to `"*"`, `days_back` defaults to
  `36500`, `limit` defaults to `50`. The SQL uses sentinel comparison
  (`@region = '*' OR region = @region`) not nullable binds. Toolbox v0.23 +
  BigQuery's Go client both reject null parameter binds at different
  validation steps; `required: false` + `default:` doesn't work because
  `toolbox_core/protocol.py` overrides backend defaults with `None` for
  required:false params.

- **Cross-package import via `sys.path.insert`** at the top of
  `netpulse-ui/agent_runner.py`, plus a parent-level `Dockerfile` that
  copies both packages. This is how the Flask UI imports
  `from telecom_ops.agent import root_agent` without packaging gymnastics.

- **Stdlib `.env` parsing** in `netpulse-ui/app.py`, not `python-dotenv`.
  Uses `os.environ.setdefault` so anything already in the shell wins.

- **Defensive `{key?}` substitution** in `telecom_ops/prompts.py`. The
  trailing `?` prevents a `KeyError` when an upstream `output_key` isn't
  populated yet (first run, error path).

## Code conventions

Python 3.12+, native type hints (`list[dict]`, `X | None`), `pathlib` for
paths, dataclasses for structured containers, module-level singletons for
shared clients (wrapped in `try/except` so an unreachable backend degrades
the affected feature instead of crashing the whole app), no emojis in code
or docs unless explicitly requested.

## Where to look

- [`README.md`](README.md) — project overview, features, deployment
- [`telecom_ops/agent.py`](telecom_ops/agent.py) — the four sub-agents and
  the SequentialAgent root
- [`telecom_ops/tools.py`](telecom_ops/tools.py) — `classify_issue` +
  `save_incident_ticket` (native ADK tools); toolset loaders for the MCP
  Toolbox
- [`telecom_ops/prompts.py`](telecom_ops/prompts.py) — sub-agent instruction
  templates
- [`telecom_ops/vertex_failover.py`](telecom_ops/vertex_failover.py) —
  `RegionFailoverGemini` model ladder + escalating timeouts
- [`netpulse-ui/agent_runner.py`](netpulse-ui/agent_runner.py) —
  async-to-sync bridge for the SSE chat
- [`netpulse-ui/data_queries.py`](netpulse-ui/data_queries.py) — read-only
  BigQuery + AlloyDB queries for the data viewer tabs
- [`netpulse-ui/app.py`](netpulse-ui/app.py) — Flask routes (`/` landing,
  `/app` workspace, three data-viewer tabs), SSE plumbing, stdlib `.env`
  loader
- [`netpulse-ui/templates/landing.html`](netpulse-ui/templates/landing.html)
  — hero, "How it works" 4-step grid, launch chips
  (`?seed=...&autorun=1` handoff)
- [`netpulse-ui/templates/chat.html`](netpulse-ui/templates/chat.html) —
  workspace timeline, impact card, badges, NOC action chips, streaming SSE
  handler
- [`Dockerfile`](Dockerfile) — Cloud Run image for the Flask UI; copies
  both packages so the cross-package import resolves
- [`scripts/setup_alloydb.py`](scripts/setup_alloydb.py) — idempotent DDL
  for `incident_tickets` and `call_records`; `--seed` reloads CSVs via
  single multi-row INSERT
- [`scripts/setup_alloydb_nl.py`](scripts/setup_alloydb_nl.py) — idempotent
  10-step setup for AlloyDB AI NL2SQL on `call_records`
- [`scripts/setup_bigquery.py`](scripts/setup_bigquery.py) — idempotent
  dataset+table creation; `--recreate` reapplies the partition + cluster
  spec
- [`scripts/generate_network_events.py`](scripts/generate_network_events.py),
  [`scripts/generate_call_records.py`](scripts/generate_call_records.py) —
  deterministic seed generators
- [`docs/seed-data/`](docs/seed-data/) — canonical sample data:
  `network_events.csv` (50 000 events, 10 cities), `call_records.csv`
  (5 000 CDRs), `incident_tickets.csv` (10 sample rows)
- [`docs/SCHEMA.md`](docs/SCHEMA.md) — column-by-column data contract for
  the 3 tables
- `docs/internal/` — phase journals, SSE wiring reference, design spec,
  migration plan (build notes; gitignored — local-only)
- [`static-mockup-rebuild/`](static-mockup-rebuild/) — locked design surface
  (6 HTML pages + shared `css/site.css` + `js/site.js`);
  `_canonical-reference.html` is the original anchor
- [`toolbox-service/`](toolbox-service/) — MCP Toolbox image source: `tools.yaml`
  (3 BQ tools `telecom_network_toolset` + 3 CDR tools `cdr_toolset`: 2
  parameterized SQL + 1 NL2SQL fallback) and `Dockerfile` (genai-toolbox v0.23.0
  binary on debian-slim). Deployed as `network-toolbox` in `us-central1` —
  rebuild from this directory with `gcloud run deploy network-toolbox --source
  toolbox-service --region us-central1`.
