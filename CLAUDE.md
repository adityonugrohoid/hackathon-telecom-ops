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
ladder) all rode the same Phase 9 polish loop. Live URL:
https://netpulse-ui-486319900424.us-central1.run.app.

Phase 9 in-flight workstreams:

1. **Heliodoron visual identity v1** — `tokens.css` swapped to sand
   neutrals (oklch hue 85), surya warm-gold brand, Geist + Newsreader +
   JetBrains Mono via jsdelivr `@fontsource-variable`. Hero "in seconds."
   accent + all data-source badges unified on `--np-pandan` deep green.
   Footer trimmed of "with Claude Code" link.
2. **Region-failover hardening** — `RegionFailoverGemini` gained a 5s
   `asyncio.wait_for` per region attempt (covers silent hangs that don't
   raise `RESOURCE_EXHAUSTED`). Region ladder swapped from APAC-heavy
   (`asia-southeast2 → asia-southeast1 → us-central1`) to multi-continent
   (`global → us-central1 → europe-west4 → asia-northeast1`) after the
   APAC entries returned `400 FAILED_PRECONDITION` on `gemini-3.1-pro-
   preview`. New `_self_test_failover_on_timeout` mocks `asyncio.Future()`
   in region 0; runtime ~5s.
3. **Per-agent model selection** — `agent.py` now takes a model arg per
   agent. `MODEL_FAST = "gemini-3.1-flash-lite-preview"` for classifier +
   network_investigator + cdr_analyzer (validated 7/7 calls successful in
   production). `MODEL_SYNTHESIS = "gemini-3.1-pro-preview"` for
   response_formatter — but Pro-preview is **`global`-only for this
   project** (us-central1 returns 404 NOT_FOUND), so the ladder collapses
   to a single point of failure for synthesis. Open question: bump
   timeout to 8s + revert MODEL_SYNTHESIS to `gemini-2.5-pro` (GA, multi-
   region) so failover is structurally usable.

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
  call + small reasoning step, which Flash-Lite handles in ~0.6-1.9s
  per call); `MODEL_SYNTHESIS = "gemini-3.1-pro-preview"` for the
  user-visible response_formatter. Caveat: as of 2026-04-26, Pro-preview
  is `global`-only for `plated-complex-491512-n6` (us-central1 returns
  404 NOT_FOUND), so the failover ladder is structurally a no-op for
  the synthesis step. Revert option for stability: `MODEL_SYNTHESIS =
  "gemini-2.5-pro"` (GA, multi-region addressable). One-line change
  isolated to `agent.py`.

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
