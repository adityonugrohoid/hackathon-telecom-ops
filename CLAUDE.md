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

## Architecture in one paragraph

The core ADK package `telecom_ops/` exposes a `SequentialAgent` that runs
four `LlmAgent` sub-agents in order: classifier, network investigator
(BigQuery via MCP Toolbox), CDR analyzer (AlloyDB), and response formatter
(writes the final ticket back to AlloyDB). The sibling Flask service
`netpulse-ui/` wraps the same `root_agent` in a custom chat UI with three
read-only data viewer tabs and Server-Sent-Events streaming. Both deploy
to Cloud Run; both target Vertex AI Gemini 2.5 Flash in `asia-southeast1`.

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

- **Vertex AI region pinned to `asia-southeast1`** via
  `GOOGLE_CLOUD_LOCATION`. Vertex's Dynamic Shared Quota on the Gemini 2.5
  GA models triggered `RESOURCE_EXHAUSTED` 429s in `us-central1` for APAC
  traffic during the hackathon window. APAC region was the verified fix.
  Don't switch back without checking quota state.

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
- `netpulse-ui/app.py` — Flask routes, SSE plumbing, stdlib `.env` loader
- `Dockerfile` (parent) — Cloud Run image for the Flask UI; copies both packages so the cross-package import resolves
- `setup_alloydb.py` — idempotent DDL for the `incident_tickets` table
