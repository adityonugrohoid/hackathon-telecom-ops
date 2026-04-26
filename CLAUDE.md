# CLAUDE.md

Project context for AI coding assistants (and humans browsing the source).

## What this is

NetPulse AI is a multi-agent telecom operations assistant built for the
APAC GenAI Academy 2026 hackathon. A natural-language complaint goes in,
a structured incident ticket comes out. See `README.md` for the full
walkthrough, architecture diagram, screenshots, and deployment notes.

This project was built collaboratively with [Claude Code](https://claude.com/claude-code),
Anthropic's CLI agent for software engineering. Acknowledging that up-front
rather than hiding it.

## Current phase: Prototype Refinement (Top 100 → Top 10)

NetPulse AI was selected into the **Top 100** of the APAC GenAI Academy
2026 (ranked #82, announced 2026-04-23). The hackathon is now in the
**Prototype Refinement Phase** — refined prototype due **2026-04-30**.

**Phase 8 (Ship) shipped 2026-04-26** — single consolidated Cloud Run
redeploy carried Phases 2-7 to production (rev `00004-sfn`); subsequent
revisions `00005-ns6` (env-var typo fix), `00006-7v8` (heliodoron tokens
+ footer trim), `00007-x7t` (pandan accent unification), `00008-kzk`
(5s timeout + 3.1 preview models), `00009-f2c` (multi-continent region
ladder), `00010-mqc` (Phase 9 round 2: header darker, done-state pandan
unification, impact-card extractor + layout fix, Flash-Lite collapse for
all 4 agents) all rode the same iterative polish loop. **Live URL:**
https://netpulse-ui-486319900424.us-central1.run.app.

**Phase 9 ✅ DONE 2026-04-26** — last healthy production run on `00010-mqc`:
10.5s end-to-end, all 4 agents on `gemini-3.1-flash-lite-preview` first-try
in `global`, ticket #74 issued. Pro-preview region-whitelist fragility
resolved by collapsing `MODEL_SYNTHESIS = MODEL_FAST` so the failover
ladder is structurally usable end-to-end.

**Phase 10 ✅ DONE 2026-04-26** — five deliverables shipped same day:
(1) MCP Toolbox refactor 8 tools → 2 universal parameterized tools
(`network-toolbox-00006-bsm`); (2) `query_cdr` parameterized (added
`days_back`, `call_type`, configurable `LIMIT`); (3) seed enriched to
10 cities (added Yogyakarta, Denpasar, Makassar, Palembang, Balikpapan),
132 events spanning 2026-01-08 → 2026-05-12 incl. 5 future maintenance
windows, 500 CDRs with realistic dropped/failed clustering around outage
anchors; (4) `setup_alloydb.py:truncate_and_load` rewritten to use a
single multi-row `INSERT VALUES` statement (was timing out on pg8000
`executemany` of 500 rows over WAN); (5) pre-existing `ALLOWED_SEVERITIES`
vocab bug fixed (`low/medium/high/critical` → `critical/major/minor` to
match `docs/SCHEMA.md`). The toolbox refactor needed three deploy
iterations to discover four real BigQuery + toolbox-core runtime
constraints (captured in
`~/.claude/memory/reference_mcp_toolbox_universal_tools.md`): (a) the
SDK ignores backend `default:` for `required: false` params, (b) BQ
rejects null INT64 binds at dry-run, (c) BQ rejects null STRING binds
at execute, (d) BQ `LIMIT` accepts only an integer literal or a single
parameter — no expressions. Final shape: every param `required: true`
+ `default:` sentinel (`"*"` for strings, `36500` for days_back, `50`
for limit), SQL uses sentinel comparison instead of nullable binds.

**Freeze A operational lift (2026-04-26).** User explicitly lifted all
Freeze A operational restrictions on `plated-complex-491512-n6`, keeping
only the project-billing link to `018C72-72D309-CBD42A` frozen. Cloud Run
deploys, BigQuery + AlloyDB writes, IAM on the project, services
enable/disable, Artifact Registry — all proceed without per-change
confirmation. Full scope in global `~/.claude/CLAUDE.md` §Protected
Resources + project memory `protected_hackathon_deployment.md` §"Freeze A
— operational lift, 2026-04-26".

## Architecture in one paragraph

The core ADK package `telecom_ops/` exposes a `SequentialAgent` that runs
four `LlmAgent` sub-agents in order: classifier, network investigator
(BigQuery via MCP Toolbox), CDR analyzer (AlloyDB), and response formatter
(writes the final ticket back to AlloyDB). The sibling Flask service
`netpulse-ui/` wraps the same `root_agent` in a hero landing page (`/`)
plus a workspace (`/app`) that renders the agent run as a vertical
timeline, with three read-only data viewer tabs and Server-Sent-Events
streaming. The workspace surfaces a customer-impact rollup, a category /
region / severity badge set on the saved ticket, and a static
category → recommended-NOC-actions chip panel — all driven client-side
from the existing SSE event stream. Both deploy to Cloud Run. Each
sub-agent picks its own model through the `RegionFailoverGemini` wrapper
in `telecom_ops/vertex_failover.py` — three upstream agents on a fast
Flash-class variant, the synthesis agent on a Pro-class variant — and
the wrapper walks a multi-continent region ladder
(`global → us-central1 → europe-west4 → asia-northeast1`) on
`RESOURCE_EXHAUSTED` 429 *or* a 5s silent-hang timeout, with the next
attempt cancelling the prior in-flight call so only one HTTP request
is ever live per agent.

## Non-obvious choices to preserve

These look optional but each one is load-bearing for a reason:

- **Thread + queue async-to-sync bridge** in `netpulse-ui/agent_runner.py` —
  do NOT replace with a direct `asyncio.run()` wrapper. The naive wrapper
  drains the entire async generator into a list before yielding, which
  buffers all SSE events to the end of the run and breaks the streaming
  chat UI. Each request runs its own asyncio loop in a worker thread and
  pushes converted events onto a `queue.Queue`; the Flask SSE generator
  pulls from the queue and yields incrementally.

- **`pool_recycle=300` on every SQLAlchemy engine** that points at
  AlloyDB / Cloud SQL (not just `pool_pre_ping=True`). Without it, idle
  connections silently die after ~30 minutes and the next query hangs
  forever waiting on a half-dead socket. We hit this during a demo gap.
  Both `telecom_ops/tools.py` and `netpulse-ui/data_queries.py` set it.

- **Vertex AI region failover + 5s hang timeout** in
  `telecom_ops/vertex_failover.py`. Default region is `global` (Google's
  multi-region routing pool); on `RESOURCE_EXHAUSTED` 429 *or* on
  `asyncio.TimeoutError` from the per-attempt 5s `wait_for`, each
  `LlmAgent` independently rebuilds its `genai.Client` against the next
  region in `RANKED_REGIONS` (`global → us-central1 → europe-west4 →
  asia-northeast1`). The ladder is **multi-continent** — APAC entries
  were swapped for a non-SE-Asia region (Tokyo) after asia-southeast1/2
  returned 400 FAILED_PRECONDITION on `gemini-3.1-pro-preview`. The 5s
  timeout is critical: a previously frozen run on 2026-04-26 hung for
  Cloud Run's full 300s request timeout because the wrapper had no way
  to detect a TCP socket that never returned a response. Now `wait_for`
  cancels the in-flight coroutine on timeout, the underlying aiohttp
  client closes the socket, and the next region attempt fires — only one
  HTTP call is ever in flight per wrapper. `agent.py` builds a fresh
  wrapper per `LlmAgent` so the four agents own independent failover
  state. Streaming (`stream=True`) bypasses both failover AND timeout
  because partial yields cannot be safely replayed; NetPulse uses
  `stream=False` so this is not a hot-path concern.

- **Per-agent model selection** in `telecom_ops/agent.py`. Two named
  constants split the four agents by cognitive role: `MODEL_FAST =
  "gemini-3.1-flash-lite-preview"` for the three upstream agents
  (classifier, network_investigator, cdr_analyzer — each does a tool
  call + small reasoning step, which Flash-Lite handles in ~0.6-1.9s per
  call). As of Phase 9 round 2 (2026-04-26 rev `00010-mqc`),
  `MODEL_SYNTHESIS = MODEL_FAST` — the synthesis step also runs on
  Flash-Lite. Earlier rev `00009-f2c` ran synthesis on
  `gemini-3.1-pro-preview` for higher instruction-following fidelity, but
  Pro-preview proved `global`-only for this project (us-central1 returned
  404 NOT_FOUND), making the failover ladder a structural no-op for
  synthesis. Flash-Lite is multi-region addressable, so the ladder works
  end-to-end. Re-split this constant if production traces show synthesis
  quality is insufficient (revert option: `MODEL_SYNTHESIS =
  "gemini-2.5-pro"`, GA + multi-region).

- **Customer-impact card consumes a JSON-encoded string from MCP toolbox.**
  `netpulse-ui/templates/chat.html:npExtractRows` recurses through both
  `Array` and `string` shapes when walking `tool_response.result`. Reason:
  `toolbox_core/itransport.py:51` declares `tool_invoke -> str`, and
  `google.adk.flows.llm_flows.functions.__build_response_event` wraps any
  non-dict tool return as `{"result": "<string>"}`. So `result.result` on
  the SSE payload is a JSON-encoded string of the row array, not the
  array itself. Without the recursive `JSON.parse` step, the impact-card
  rollup silently degrades to `[]` and the card never populates correctly.

- **MCP Toolbox in front of BigQuery**, not the direct BigQuery MCP
  endpoint. The direct endpoint returns 403 / Connection-closed on
  Cloud Run; the toolbox-as-intermediary pattern works.

- **Toolbox parameters use sentinel defaults, not nullable binds.** The
  2 universal tools in `~/projects/genai-hackathon/track2-network-status/toolbox-service/tools.yaml`
  declare every param `required: true` with a `default:` sentinel — strings
  default to `"*"`, `days_back` defaults to `36500`, `limit` defaults to
  `50`. The SQL uses sentinel comparison (`@region = '*' OR region = @region`)
  not nullable binds (`@region IS NULL OR ...`). This is load-bearing because
  toolbox v0.23 + BigQuery's high-level Go client both reject null parameter
  binds — STRING null fails at execute time, INT64 null fails at the dry-run
  validator, and BigQuery `LIMIT` doesn't accept expressions like
  `IFNULL(@limit, 50)`. `required: false` + `default:` does NOT work either:
  `toolbox_core/protocol.py:113-118` overrides backend defaults with `None`
  in the Python signature for required:false params. See
  `~/.claude/memory/reference_mcp_toolbox_universal_tools.md` for the full
  finding chain. `NETWORK_INVESTIGATOR_INSTRUCTION` in `prompts.py` is the
  matching prompt — it tells the agent to ALWAYS pass all 5 params using
  sentinels for "no filter".

- **Cross-package import via `sys.path.insert`** at the top of
  `netpulse-ui/agent_runner.py`, plus a parent-level `Dockerfile` that
  copies both `netpulse-ui/` and `telecom_ops/` into the image. This is
  how the Flask UI imports `from telecom_ops.agent import root_agent`
  without packaging gymnastics.

- **Stdlib `.env` parsing** in `netpulse-ui/app.py`, not `python-dotenv`.
  Uses `os.environ.setdefault` so anything already in the shell wins.

- **Defensive `{key?}` substitution** in `telecom_ops/prompts.py`. ADK
  `LlmAgent` instructions reference upstream `output_key` state from
  earlier sub-agents; the trailing `?` prevents a `KeyError` when the
  state isn't populated yet (first run, error path, etc.).

## Code conventions

Python 3.12+, native type hints (`list[dict]`, `X | None`), `pathlib` for
paths, dataclasses for structured data containers, module-level singletons
for shared clients (wrapped in `try/except` so an unreachable backend
degrades the affected feature instead of crashing the whole app), no
emojis in code or docs unless explicitly requested.

## Where to look

- `README.md` — full project overview, architecture diagram, screenshots, deployment commands
- `telecom_ops/agent.py` — the four sub-agents and the SequentialAgent root
- `telecom_ops/tools.py` — `classify_issue`, `query_cdr`, `save_incident_ticket`
- `telecom_ops/prompts.py` — sub-agent instruction templates
- `netpulse-ui/agent_runner.py` — async-to-sync bridge for the SSE chat
- `netpulse-ui/data_queries.py` — read-only BigQuery + AlloyDB queries for the data viewer tabs
- `netpulse-ui/app.py` — Flask routes (`/` landing, `/app` workspace, `/chat` 301 → `/app`, three data-viewer tabs), SSE plumbing, stdlib `.env` loader
- `netpulse-ui/templates/landing.html` — hero, "How it works" 4-step grid, launch chips (`?seed=...&autorun=1` handoff), data-viewer cards, footer
- `netpulse-ui/templates/chat.html` — workspace timeline, impact card, badges, NOC action chips, plus the streaming SSE handler in inline JS
- `Dockerfile` (parent) — Cloud Run image for the Flask UI; copies both packages so the cross-package import resolves
- `setup_alloydb.py` — idempotent DDL for both `incident_tickets` and `call_records`; `--seed` reloads CSVs via single multi-row INSERT (one round-trip even for 500 rows)
- `scripts/setup_bigquery.py` — idempotent dataset+table creation; `--seed` reloads `network_events.csv` via WRITE_TRUNCATE
- `docs/seed-data/` — canonical sample data: `network_events.csv` (132 events, 10 cities, 2026-01-08 → 2026-05-12), `call_records.csv` (500 CDRs), `incident_tickets.csv` (10 sample rows)
- `~/projects/genai-hackathon/track2-network-status/toolbox-service/tools.yaml` — MCP Toolbox config: 2 universal parameterized tools with sentinel defaults
