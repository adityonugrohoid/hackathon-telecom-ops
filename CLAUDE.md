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
`LlmAgent` sub-agents in order: classifier (native ADK `classify_issue` tool),
network investigator (MCP Toolbox over the bundled SQLite store —
`query_network_events`, `query_affected_customers_summary`,
`weekly_outage_trend`), CDR analyzer (two parameterized SQL tools over the same
SQLite store — `query_cdr_summary` for call_type × call_status breakdown,
`query_cdr_worst_towers` for per-tower failure ranking), and response formatter
(native ADK `save_incident_ticket` tool that writes the final ticket back to
the same SQLite file via stdlib `sqlite3`). The sibling Flask service
`netpulse-ui/` wraps the same `root_agent` in a hero landing page (`/`) plus a
workspace (`/app`) that renders the agent run as a vertical timeline, with three
read-only data viewer tabs and Server-Sent-Events streaming. Both deploy to
Cloud Run; the SQLite file is baked into the container image. Each sub-agent
picks its own model through the `RegionFailoverGemini` wrapper in
`telecom_ops/vertex_failover.py` — all four currently share
`MODEL_FAST = "gemini-3.1-flash-lite-preview"`. The wrapper targets the single
`global` Vertex endpoint and walks a 4-attempt model ladder on
`RESOURCE_EXHAUSTED` 429 or per-attempt `asyncio.TimeoutError`: primary 10s →
primary +0.5s sleep 20s → `gemini-3-flash-preview` intermediate 20s →
`gemini-2.5-flash` GA fallback 30s. Each attempt cancels the prior in-flight
call so only one HTTP request is ever live per agent.

## Non-obvious choices to preserve

These look optional but each one is load-bearing:

- **Thread + queue async-to-sync bridge** in `netpulse-ui/agent_runner.py`. Do
  NOT replace with `asyncio.run()`. The naive wrapper drains the entire async
  generator into a list before yielding, which buffers all SSE events and
  breaks the streaming chat UI. Each request runs its own asyncio loop in a
  worker thread and pushes events onto a `queue.Queue`; the Flask SSE
  generator pulls and yields incrementally.

- **SQLite is bundled in the container, not a managed backend.** The data
  substrate is a single `data/netpulse.sqlite` file produced by
  `scripts/build_sqlite.py` from `docs/seed-data/*.csv`. The container build
  bakes the file into the image; runtime opens it via stdlib `sqlite3` (for
  the `save_incident_ticket` write path) and via `genai-toolbox v0.23.0`'s
  `kind: sqlite` source (for the 5 read tools). One file holds all three
  tables — `network_events`, `call_records`, `incident_tickets` — and the
  toolbox-as-intermediary pattern keeps the agent code agnostic of the
  substrate (swap `tools.yaml` `sources:` from `kind: sqlite` to
  `kind: alloydb-postgres` / `kind: bigquery` and the agent code does not
  change). Cloud Run scale-to-zero loses agent-written tickets across cold
  starts; that is acceptable for the demo, not for production.

- **Toolbox SQL uses SQLite `?N` numbered placeholders.** Each sentinel
  filter referenced twice (`(?1 = '*' OR region = ?1)`) needs a single
  parameter slot, which standard `?` positional binding does not give you.
  SQLite supports `?N` (where N is the 1-based index of the parameter in
  the declared `parameters:` list). The toolbox Go driver
  (`modernc.org/sqlite`) passes this through unchanged. Don't use `:name`
  or `@name`; the toolbox `kind: sqlite-sql` only resolves positional.

- **`datetime()` arithmetic for time windows.** SQLite has no
  `TIMESTAMP_SUB` or `make_interval`. The toolbox SQL uses
  `datetime('now', '-' || ?N || ' days')` to build a string modifier from
  the integer `days_back` parameter. String concatenation via `||` is the
  whole trick — SQLite auto-coerces the integer. Same pattern handles
  `weeks_back` via `(?N * 7)`.

- **`network_events` is indexed on `(region, severity, started_at)`.**
  The seed has 50 000 events; without the index a full scan dominates the
  3 network tools. There's a secondary index on `started_at` alone for
  the recent-time-window scans. `call_records` is indexed on
  `(region, call_date)`. All three indexes are created idempotently by
  `scripts/build_sqlite.py` after the bulk INSERT.

- **`save_incident_ticket` writes via stdlib `sqlite3`, not the toolbox.**
  Keeping the write path inside the agent's Python process avoids a
  round-trip and makes ticket persistence transactional with the rest of
  `response_formatter`. AUTOINCREMENT on `ticket_id` picks up past the
  seed's MAX so agent-written rows don't collide with seed rows. SQLite's
  single-writer model is fine here — the agent chain is serialized
  end-to-end.

- **Seed-data window slides with `datetime.now()`.**
  `scripts/generate_network_events.py` and `generate_call_records.py`
  anchor `WINDOW_END` at today's date and `WINDOW_START` at today minus
  180 days. So a regenerated CSV always covers the most recent 6 months
  and the agent's "last 7 days" default lands on populated data. The seed
  is otherwise deterministic (fixed `SEED = 20260426`).

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
  under the model ladder since attempt 4's `gemini-2.5-flash` GA fallback
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

- **Toolbox parameters use sentinel defaults, not nullable binds.** Every
  param declares `required: true` with a `default:` sentinel — strings
  default to `"*"`, `days_back` defaults to `36500`, `limit` defaults to
  `50`. The SQL uses sentinel comparison (`?N = '*' OR region = ?N`) not
  nullable binds. `required: false` + `default:` doesn't work because
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

## Local development

Two terminals at the repo root:

```bash
# Terminal A — MCP Toolbox (downloads v0.23.0 binary on first run, caches at .toolbox/)
scripts/run_toolbox_local.sh

# Terminal B — Flask UI
cd netpulse-ui
TOOLBOX_URL=http://127.0.0.1:5000 \
GOOGLE_CLOUD_PROJECT=<your-project-with-vertex-enabled> \
GOOGLE_CLOUD_LOCATION=global \
GOOGLE_GENAI_USE_VERTEXAI=TRUE \
  ../.venv/bin/python app.py
```

`data/netpulse.sqlite` is generated on first run of `run_toolbox_local.sh`
if missing; manual rebuild is `python scripts/build_sqlite.py --recreate`.

ADC must be authenticated (`gcloud auth application-default login`); the
genai-toolbox Vertex client uses `GOOGLE_CLOUD_PROJECT` for attribution.

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
  Toolbox; stdlib `sqlite3` write path
- [`telecom_ops/prompts.py`](telecom_ops/prompts.py) — sub-agent instruction
  templates
- [`telecom_ops/vertex_failover.py`](telecom_ops/vertex_failover.py) —
  `RegionFailoverGemini` model ladder + escalating timeouts
- [`netpulse-ui/agent_runner.py`](netpulse-ui/agent_runner.py) —
  async-to-sync bridge for the SSE chat
- [`netpulse-ui/data_queries.py`](netpulse-ui/data_queries.py) — read-only
  stdlib `sqlite3` queries for the three data-viewer tabs
- [`netpulse-ui/app.py`](netpulse-ui/app.py) — Flask routes (`/` landing,
  `/app` workspace, three data-viewer tabs), SSE plumbing, stdlib `.env`
  loader
- [`netpulse-ui/templates/landing.html`](netpulse-ui/templates/landing.html)
  — hero, "How it works" 4-step grid, launch chips
- [`netpulse-ui/templates/chat.html`](netpulse-ui/templates/chat.html) —
  workspace timeline, impact card, badges, NOC action chips, streaming SSE
  handler
- [`Dockerfile`](Dockerfile) — Cloud Run image for the Flask UI; copies
  both packages so the cross-package import resolves; runs `build_sqlite.py`
  at image build time to bake the data file
- [`scripts/build_sqlite.py`](scripts/build_sqlite.py) — idempotent build of
  `data/netpulse.sqlite` from `docs/seed-data/*.csv`; `--recreate` wipes +
  rebuilds. Replaces the deleted AlloyDB / BigQuery setup scripts.
- [`scripts/run_toolbox_local.sh`](scripts/run_toolbox_local.sh) — downloads
  genai-toolbox v0.23.0 binary on first run, launches it bound to
  `127.0.0.1:5000` against the local `tools.yaml`
- [`scripts/generate_network_events.py`](scripts/generate_network_events.py),
  [`scripts/generate_call_records.py`](scripts/generate_call_records.py) —
  deterministic seed generators anchored at `datetime.now()`
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
- [`toolbox-service/`](toolbox-service/) — MCP Toolbox image source:
  `tools.yaml` (5 SQLite-SQL tools split across `telecom_network_toolset`
  and `cdr_toolset`) and `Dockerfile` (genai-toolbox v0.23.0 binary on
  debian-slim). Deploy: `gcloud run deploy network-toolbox --source
  toolbox-service --region <region>`.
