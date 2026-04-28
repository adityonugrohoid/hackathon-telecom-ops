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
2026 (announced 2026-04-23). The hackathon is now in the **Prototype
Refinement Phase** — refined prototype due **2026-04-30**.

**Static mockup LOCKED 2026-04-28.** `static-mockup-rebuild/` is the
canonical design surface for all six NetPulse AI pages (landing, docs,
3 data viewers, workspace). The old `static-mockup/` folder has been
**deleted** — rebuild is the single source of truth. Iteration was
scaffolded clean from `landing-trial.html` (PR #19, 2026-04-27),
expanded to six pages in PR #20 (merge `fc9f10f`, 2026-04-28), and
finalised same day with a workspace redesign: top split-pane (1fr
prompt / 2fr dark ticket form with skeleton-shimmer + Compiling pill),
four agent cards each carrying a Claude-Code-style terminal panel
(`$ tool_call` + populated mono output + Inter prose summary),
unified pandan-green source badges, and a `dv-cross` see-also strip.
**Next move: full LIVE migration to `netpulse-ui/templates/` — see
`docs/MIGRATION-CANONICAL-DESIGN.md`. User will signal start.**

Reference layout while migration is pending:

- `landing-trial.html` (project root) — **canonical design reference**
  (promoted 2026-04-27, PR #18). Single self-contained page establishing
  the warm editorial direction: cream paper `#F4F0E6` + deep ink
  `#141413` + clay coral `#CC785C` palette; Fraunces display + Inter
  body + JetBrains Mono labels. Calibrate every change in
  `static-mockup-rebuild/` against this page.
- `static-mockup-rebuild/` — six pages:
  - `index.html` — landing (hero CTA-band with sample IN prompt + sample
    OUT ticket; horizontal How-it-works strip with 6 cards + 5 chevrons;
    Data Viewer + Resources card grids; footer)
  - `docs.html` — single comprehensive docs page (sticky TOC + 7
    sections: about, architecture, stack, data, byod, phases, roadmap).
    The Resources dropdown's `architecture` and `byod` items resolve to
    `docs.html#architecture` / `docs.html#byod`.
  - `network-events.html`, `call-records.html`, `tickets.html` — three
    data viewer pages sharing an 8-section template (header → page hero →
    source banner → filter card → table card → schema callout → cross
    links → footer). Source banners name-check real repo entities
    (`query_network_events`, `alloydb_ai_nl.execute_nl_query`,
    `save_incident_ticket`, etc.).
  - `app.html` — workspace mockup (final form 2026-04-28). Top
    **two-pane** at 1fr/2fr: left = prompt (textarea + sample chips,
    Investigate button anchored bottom-right), right = **dark/ink
    ticket form** with skeleton-shimmer rows, coral "Compiling" pill +
    spinner, and a pulsing progress dot ("response_formatter is
    writing the ticket to AlloyDB…"). Below: four agent cards on a
    left-rail timeline. Each card carries a **Claude-Code-style
    terminal panel** (paper-2 bar with traffic-light dots + agent
    name + model meta on the right; paper-white body with three
    tiers — Inter prose pull on a coral left-rule, mono `$ tool_call`,
    mono output rows preserving alignment with bolded `affected:`
    totals / KVP keys / table-style ratio columns). Cards 1–3 are
    `is-done` (green pill, coral-filled dot, populated terminals);
    card 4 is `is-running` (coral pill, animated cursor on the
    trailing `→` line). All source badges unified to pandan green.
    Bottom: populated impact card (558,789 customers · 6 events ·
    3 days · 581 dropped calls) + 5 NOC action chips + `dv-cross`
    see-also strip (Network events · Call records · Incident
    tickets · GitHub repo). Deterministic tool-tone — no italic
    Fraunces in the workspace surface (Fraunces upright stays in
    the header brand and footer tagline only).
- `static-mockup-rebuild/css/site.css` — shared stylesheet (~3,000
  lines). Extracted from the originally-inline `<style>` in `index.html`
  on 2026-04-28 so all 6 pages link a single source of truth.
- `static-mockup-rebuild/js/site.js` — sticky-nav border handler.
- `static-mockup-rebuild/img/architecture.png` — NetPulse-palette
  Mermaid render. Source: `docs/architecture.mmd` (also repainted
  2026-04-28). Re-render with
  `mmdc -i docs/architecture.mmd -o docs/architecture.png -b "#F4F0E6" --scale 2`
  then copy into `static-mockup-rebuild/img/`.
- `static-mockup-rebuild/_build_dv.py` and `_build_docs.py` — one-off
  generators that scaffolded the data-viewer + docs pages by reading
  the canonical header / footer out of `index.html`. The HTML files
  have since diverged via hand edits (elaborated banners, phase-history
  dates); re-running the scripts would overwrite hand changes.
  `app.html` was generated similarly (inline Python in the chat, not
  saved as a script) — the file is hand-editable from here.
- `static-mockup-rebuild/README.md` — file map, page structure tables
  (incl. an `app.html` section), outstanding issues, resume notes.
  **Read this first** when picking the iteration up after compaction.

**Local preview workflow:** serve from project root with
`python3 -m http.server 8765 --directory .`, open
http://localhost:8765/static-mockup-rebuild/, screenshot via Playwright
MCP. Rebuild is locked — design changes here are minor polish only;
substantive change goes through the migration plan.

**Migration gate:** do not auto-port mockup changes to
`netpulse-ui/templates/`. The static mockup is the design sandbox; the
Flask app is production. Two separate decisions: "design approved"
(static mockup is locked — done 2026-04-28) and "ship to prod" (full
LIVE migration per `docs/MIGRATION-CANONICAL-DESIGN.md` — pending user
signal).

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

**Phase 11 ✅ DONE 2026-04-26** — three deliverables shipped same day,
ahead of the 2026-04-30 Top-10 cut: (1) AlloyDB AI NL2SQL replaces the
hand-written `query_cdr` SQL — `cdr_analyzer` now poses a single English
question to `query_cdr_nl` and the toolbox translates it via
`alloydb_ai_nl.execute_nl_query` against the new `netpulse_cdr_config`;
read-only enforcement is structural via the `netpulse_nl_reader` Postgres
role with `SELECT` on `call_records` only. (2) BigQuery seed grown 132 →
50,000 events over 6 months, table re-created DAY-partitioned on
`started_at` and clustered by `(region, severity)`, with a new
`weekly_outage_trend` analytical tool that exploits both. (3) CDR seed
grown 500 → 5,000 rows clustered around per-city anchor windows so NL
queries return non-trivial counts. Live URL unchanged
(`netpulse-ui-00012-z6n`); network-toolbox at `network-toolbox-00010-cmd`.
Five new gotchas captured in
`~/.claude/memory/reference_alloydb_ai_nl_setup.md` (toolbox v0.23
alloydb-ai-nl adapter sends bad PSV; `default_llm_model` flag silently
ignored without `google_ml.create_model`; `add_template` always validates
SQL; `associate_concept_type` requires pre-existing concept; BQ
`TIMESTAMP_SUB` rejects WEEK on TIMESTAMP).

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

**Phase 12 ✅ DONE 2026-04-27** — Vertex failover redesign: region ladder
swapped for a model ladder. Production trace on rev `00015-24q` showed
the structural break: `global` 429 RESOURCE_EXHAUSTED → wrapper failed
over to `us-central1` → 404 NOT_FOUND because Flash-Lite-preview is
global-only on this project. The new `ATTEMPT_SCHEDULE` in
`vertex_failover.py` walks 3 attempts at the single `global` endpoint:
attempt 1 (primary, 10s), attempt 2 (primary after 0.5s sleep, 20s),
attempt 3 (`gemini-2.5-flash` GA fallback, 30s). Each model has its own
quota bucket so the GA fallback is a real escape hatch — the demo never
hard-fails on quota pressure. Three self-tests pass: quota-retry stays
on primary, timeout-retry stays on primary, persistent-429 swaps to
fallback. Live on rev `netpulse-ui-00017-…` (Cloud Run redeploy from
project root with `--clear-base-image` to flip Buildpacks → Dockerfile;
the prior buildpacks deploys had been stripping `telecom_ops/` from the
image, surfacing as `ModuleNotFoundError: No module named 'telecom_ops'`
on every `/api/query` call). Observer payload field `region` now carries
the model name (semantic abuse kept to minimize SSE/frontend diff); the
chat 'via' chip renders model names instead of region names — same CSS,
same dedupe behavior, retries on the same model collapse to one hop.

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
(BigQuery via MCP Toolbox — `query_network_events`,
`query_affected_customers_summary`, and the partition-pruning
`weekly_outage_trend` analytical rollup), CDR analyzer (AlloyDB AI
NL2SQL via MCP Toolbox — `query_cdr_nl` posts a single English question
that `alloydb_ai_nl.execute_nl_query` translates against the
`netpulse_cdr_config`), and response formatter (writes the final ticket
back to AlloyDB). The sibling Flask service
`netpulse-ui/` wraps the same `root_agent` in a hero landing page (`/`)
plus a workspace (`/app`) that renders the agent run as a vertical
timeline, with three read-only data viewer tabs and Server-Sent-Events
streaming. The workspace surfaces a customer-impact rollup, a category /
region / severity badge set on the saved ticket, and a static
category → recommended-NOC-actions chip panel — all driven client-side
from the existing SSE event stream. Both deploy to Cloud Run. Each
sub-agent picks its own model through the `RegionFailoverGemini` wrapper
in `telecom_ops/vertex_failover.py` — all four agents currently share
`MODEL_FAST = "gemini-3.1-flash-lite-preview"`. The wrapper targets the
single `global` Vertex endpoint and walks a 3-attempt **model ladder**
on `RESOURCE_EXHAUSTED` 429 *or* per-attempt `asyncio.TimeoutError`:
attempt 1 (primary, 10s), attempt 2 (primary after 0.5s sleep, 20s),
attempt 3 (`gemini-2.5-flash` GA fallback, 30s). Each attempt cancels
the prior in-flight call so only one HTTP request is ever live per agent.
The model ladder replaced the prior multi-continent region ladder, which
became structurally unusable once preview models shipped with per-project
regional gating: `global` 429 → `us-central1` always 404'd because
Flash-Lite-preview is global-only on this project.

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

- **Vertex AI model-ladder failover + escalating timeouts** in
  `telecom_ops/vertex_failover.py`. All requests target the single
  `REGION = "global"` Vertex endpoint. On `RESOURCE_EXHAUSTED` 429 *or*
  `asyncio.TimeoutError`, the wrapper walks `ATTEMPT_SCHEDULE`:
  | # | model              | timeout | pre-sleep |
  |---|--------------------|---------|-----------|
  | 1 | primary self.model | 10s     | 0s        |
  | 2 | primary self.model | 20s     | 0.5s      |
  | 3 | `gemini-2.5-flash` | 30s     | 0s        |
  Worst-case wall clock per agent: 60.5s (well under Cloud Run's 300s).
  The hybrid retry-then-swap shape means most 429s clear by attempt 2
  on the same headline preview model (Vertex's dynamic shared quota
  pool typically replenishes within a second), and only sustained
  pressure forces the swap to the GA fallback. The 10s attempt-1 timeout
  is critical: a previously frozen run on 2026-04-26 hung for Cloud Run's
  full 300s request timeout because the wrapper had no way to detect a
  TCP socket that never returned a response. Now `wait_for` cancels the
  in-flight coroutine on timeout, the SDK's aiohttp client closes the
  socket, and the next attempt fires — only one HTTP call is ever in
  flight per wrapper. 5s was tried first but a Phase 11 production trace
  (network_investigator summarising a 15.5 KB weekly_outage_trend
  response) false-positive-timed-out at 5.05s; 10s was raised to give
  legitimate-slow responses headroom. The escalating ceiling (10→20→30s)
  on retries grants progressively more slack since the previous attempt
  proved the call wasn't a fast hang. The ladder swaps **models**, not
  regions, because preview models are gated to specific regions per
  project — `gemini-3.1-flash-lite-preview` is `global`-only here, so
  the previous region ladder advanced from `global` 429 to `us-central1`
  404 NOT_FOUND every time. Each model has its own quota bucket, so the
  GA fallback is a real escape hatch. `agent.py` builds a fresh wrapper
  per `LlmAgent` so the four agents own independent failover state.
  Streaming (`stream=True`) bypasses both ladder AND timeout because
  partial yields cannot be safely replayed; NetPulse uses `stream=False`
  so this is not a hot-path concern.

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
  404 NOT_FOUND), making the prior region-failover ladder a structural
  no-op. Under the new model ladder, re-splitting this constant is safe
  since the ladder no longer assumes multi-region addressability —
  attempt 3's `gemini-2.5-flash` fallback covers any global-only primary.
  Revert option: `MODEL_SYNTHESIS = "gemini-2.5-pro"` (GA + multi-region)
  if production traces show synthesis quality is insufficient.

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

- **`query_cdr_nl` uses `kind: postgres-sql`, not `kind: alloydb-ai-nl`.**
  Toolbox v0.23.0's native alloydb-ai-nl adapter always emits
  `param_names => ARRAY[]::TEXT[], param_values => ARRAY[]::TEXT[]` when no
  `nlConfigParameters:` are declared, and AlloyDB AI rejects the empty
  text-array with `SQLSTATE P0001 — Invalid PSV named parameters`. The
  workaround is to drop the native adapter and call `execute_nl_query`
  directly via `kind: postgres-sql`:
  `SELECT alloydb_ai_nl.execute_nl_query('netpulse_cdr_config', $1) AS result`.
  The function-default NULLs land where they should and PSV is bypassed.
  See `~/.claude/memory/reference_alloydb_ai_nl_setup.md` finding #1.

- **AlloyDB AI NL2SQL needs the model registered via `google_ml.create_model`,
  not just `default_llm_model` instance flag.** The flag is silently ignored
  unless the model id appears in `google_ml.model_info_view`. We register
  `gemini-2.5-flash:generateContent` (GA, accessible in us-central1) and
  bind it to the `netpulse_cdr_config` via
  `g_manage_configuration(operation => 'change_model', ...)`. Both steps
  live in `scripts/setup_alloydb_nl.py`. Don't use `gemini-3.1-flash-lite-preview`
  here — it's `global`-only on this project, and AlloyDB AI calls Vertex
  from the AlloyDB instance's own region (us-central1).

- **Read-only NL2SQL role is structural, not prompt-based.** The toolbox
  connects to AlloyDB as `netpulse_nl_reader` (created by
  `setup_alloydb_nl.py:create_reader_role`), which has only `SELECT` on
  `public.call_records` and `EXECUTE` on the `alloydb_ai_nl` helper
  functions. Even if the LLM emits a `DROP TABLE`, the role lacks the
  privilege so the call errors out cleanly. The `alloydb-cdr` source in
  `tools.yaml` carries an explicit comment forbidding the use of the
  `postgres` superuser for convenience — that bypass would defeat the
  protection.

- **`network_events` is DAY-partitioned on `started_at` and clustered by
  `(region, severity)`.** Phase 11 grew the seed 132 → 50,000 events so
  the partition gates have something to prune. The `weekly_outage_trend`
  tool relies on partition pruning to keep a 12-week / 26-week scan cheap;
  without partitioning the table the rollup would scan the full 6-month
  history every call. `setup_bigquery.py --recreate` is the only way to
  apply the partition spec to a pre-Phase-11 unpartitioned table — BigQuery
  does not allow partition changes in place. The flag is destructive
  (drops + recreates the table); pair it with `--seed` to reload data.

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
- `landing-trial.html` — canonical design reference for static-mockup-rebuild work; warm editorial direction (cream paper + deep ink + clay coral) with Fraunces display + Inter body + JetBrains Mono labels; all CSS / SVG / JS inlined
- `static-mockup-rebuild/` — **locked** design surface (6 HTML pages incl. `app.html` workspace mockup + shared `css/site.css` + `js/site.js`); see `static-mockup-rebuild/README.md` for the full file map and resume notes
- `docs/MIGRATION-CANONICAL-DESIGN.md` — plan for porting the rebuild into `netpulse-ui/templates/` and redeploying to Cloud Run; gated on user signal
- `telecom_ops/agent.py` — the four sub-agents and the SequentialAgent root
- `telecom_ops/tools.py` — `classify_issue` + `save_incident_ticket` (native ADK tools); `network_tools` and `cdr_nl_tools` toolset loaders for the MCP Toolbox
- `telecom_ops/prompts.py` — sub-agent instruction templates
- `netpulse-ui/agent_runner.py` — async-to-sync bridge for the SSE chat
- `netpulse-ui/data_queries.py` — read-only BigQuery + AlloyDB queries for the data viewer tabs
- `netpulse-ui/app.py` — Flask routes (`/` landing, `/app` workspace, `/chat` 301 → `/app`, three data-viewer tabs), SSE plumbing, stdlib `.env` loader
- `netpulse-ui/templates/landing.html` — hero, "How it works" 4-step grid, launch chips (`?seed=...&autorun=1` handoff), data-viewer cards, footer
- `netpulse-ui/templates/chat.html` — workspace timeline, impact card, badges, NOC action chips, plus the streaming SSE handler in inline JS
- `Dockerfile` (parent) — Cloud Run image for the Flask UI; copies both packages so the cross-package import resolves
- `setup_alloydb.py` — idempotent DDL for both `incident_tickets` and `call_records`; `--seed` reloads CSVs via single multi-row INSERT (one round-trip even for 5 000 rows)
- `scripts/setup_alloydb_nl.py` — Phase 11: idempotent 10-step setup for AlloyDB AI NL2SQL on `call_records` — extension, model registration, config + table view, schema-context generation (3-5 min blocking step), value index, templates, and the `netpulse_nl_reader` read-only role
- `scripts/setup_bigquery.py` — idempotent dataset+table creation; `--seed` reloads `network_events.csv` via WRITE_TRUNCATE; `--recreate` drops + recreates the table to apply DAY-partition + region/severity clustering (Phase 11)
- `scripts/generate_network_events.py` — Phase 11: deterministic 50 000-row generator (180-day window, 70/22/5/3 mix, paired restorations) for `docs/seed-data/network_events.csv`
- `scripts/generate_call_records.py` — Phase 11: deterministic 5 000-row CDR generator with anchor-clustered dropped/failed calls per city for `docs/seed-data/call_records.csv`
- `docs/seed-data/` — canonical sample data: `network_events.csv` (50 000 events, 10 cities, 2025-11-01 → 2026-04-30), `call_records.csv` (5 000 CDRs), `incident_tickets.csv` (10 sample rows)
- `~/projects/genai-hackathon/track2-network-status/toolbox-service/tools.yaml` — MCP Toolbox config: 3 BQ tools (`query_network_events`, `query_affected_customers_summary`, `weekly_outage_trend`) + 1 NL tool (`query_cdr_nl` via `kind: postgres-sql` against the `alloydb-cdr` source)
