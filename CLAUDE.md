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

Until the deadline, refinement is the priority workstream. Anchor items:

1. **Vertex AI region failover** — implemented in
   `telecom_ops/vertex_failover.py`. Default region is `global`; on
   `RESOURCE_EXHAUSTED`, each `LlmAgent` independently walks
   `asia-southeast2` → `asia-southeast1` → `us-central1`. Source landed;
   the live deploy state still has the `asia-southeast1` static pin until
   the user runs the manual Cloud Run redeploy with the updated
   `--set-env-vars` flag (see `README.md` § Deployment).
2. **Visual redesign (Phase 4)** — landing page + workspace split is now
   live in source. `/` renders `templates/landing.html` (hero, "How it
   works" 4-step grid, launch chips, data-viewer cards, footer); `/app`
   renders the chat workspace; `/chat` 301s to `/app`. The workspace
   pipeline is now a vertical PagerDuty-style timeline (`<ol class="np-
   timeline">`), each agent's row tagged with status badges and a left-
   rail timestamp + status dot. A customer-impact card aggregates
   network_investigator's BQ rows on the fly; a static category →
   recommended-actions chip panel sits below the final ticket. All five
   §5.* items in `REFINEMENT-PHASES.md` Phase 4 are checked.
3. **Brainstorming queue** — further refinement candidates (architecture,
   performance, deeper Gen AI usage) to be scoped with the user before
   any code changes.

Deployed services in `plated-complex-491512-n6` remain under the freeze
documented in global `~/.claude/CLAUDE.md`. Source edits inside this
repo are within normal authorization; any Cloud Run redeploy still
requires explicit per-change confirmation from the user.

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
from the existing SSE event stream. Both deploy to Cloud Run; both
target Vertex AI Gemini 2.5 Flash through the `RegionFailoverGemini`
wrapper in `telecom_ops/vertex_failover.py`, which defaults to `global`
and fails over through ranked APAC + US regions on `RESOURCE_EXHAUSTED`.

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

- **Vertex AI region failover via `RegionFailoverGemini`** in
  `telecom_ops/vertex_failover.py`. Default region is `global` (Google's
  multi-region routing pool); on `RESOURCE_EXHAUSTED`, each `LlmAgent`
  independently rebuilds its `genai.Client` against the next region in
  `RANKED_REGIONS` (`asia-southeast2` → `asia-southeast1` →
  `us-central1`). `agent.py` builds a fresh wrapper per `LlmAgent` so the
  four agents own independent failover state. Do NOT replace with a
  single static `GOOGLE_CLOUD_LOCATION=us-central1` pin — that's the
  verified failure mode (DSQ contention from APAC traffic). The single-
  region `asia-southeast1` pin worked too but had no headroom on a
  trial-billing project; the failover ladder converts a quota miss into
  one extra hop instead of a hard 500. Streaming (`stream=True`) bypasses
  failover because partial yields cannot be safely replayed; NetPulse
  uses `stream=False` so this is not a hot-path concern.

- **MCP Toolbox in front of BigQuery**, not the direct BigQuery MCP
  endpoint. The direct endpoint returns 403 / Connection-closed on
  Cloud Run; the toolbox-as-intermediary pattern works.

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
- `setup_alloydb.py` — idempotent DDL for the `incident_tickets` table
