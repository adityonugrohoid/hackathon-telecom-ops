<div align="center">

# NetPulse AI

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Google ADK 1.14](https://img.shields.io/badge/Google%20ADK-1.14.0-4285F4.svg)](https://google.github.io/adk-docs/)
[![Vertex AI Gemini 3.1](https://img.shields.io/badge/Vertex%20AI-Gemini%203.1%20Flash--Lite-34A853.svg)](https://cloud.google.com/vertex-ai)
[![Cloud Run](https://img.shields.io/badge/Cloud%20Run-live-34A853.svg)](https://netpulse-ui-670100779564.asia-southeast2.run.app/)

**A multi-agent AI assistant that turns a telecom customer's natural-language complaint into a structured incident ticket — in 25–30 seconds, end-to-end.**

### → [**Try it live**](https://netpulse-ui-670100779564.asia-southeast2.run.app/) ←

_Two Cloud Run services backed by a single bundled SQLite file (no managed DB). The original hackathon architecture on BigQuery + AlloyDB is one [`tools.yaml`](toolbox-service/tools.yaml) `sources:` swap away — see [Architecture](#architecture)._

[Features](#features) · [Architecture](#architecture) · [Tech stack](#tech-stack) · [Run it locally](#run-it-locally) · [Deploy](#deploy)

</div>

---

## Overview

Built for the **Gen AI Academy APAC Edition 2026** hackathon as a working
prototype of how multi-agent orchestration replaces the manual cross-system
lookups that NOC engineers do dozens of times a day.

When a customer reports something like *"Major dropped calls in Surabaya"*,
a NOC operator today has to query at least three independent systems — a
network event database, a call detail records (CDR) database, and a
ticketing system — and manually correlate the results. NetPulse AI does all
of that in a single natural-language step:

1. **Classifies** the complaint into a category (network / billing / hardware / service / general) and a region.
2. **Investigates** live network events from the bundled SQLite store via MCP Toolbox.
3. **Analyzes** matching call detail records via two parameterized SQL tools served by the same MCP Toolbox.
4. **Synthesizes** an incident ticket with a NOC recommendation, persisted to SQLite and surfaced to the operator.

The whole workflow runs as a Google ADK `SequentialAgent` orchestrating four
`LlmAgent` sub-agents, each backed by Gemini on Vertex AI. End-to-end latency
is **25–30 seconds** including all four LLM calls and three live database
round-trips.

## Features

- **Multi-agent orchestration.** Four specialized ADK `LlmAgent` sub-agents
  chained by a `SequentialAgent`, each owning one responsibility, one tool
  (or one toolset), and one `output_key` written into `session.state`.
  Downstream agents read upstream state via defensive `{key?}` substitution
  so a partial chain still produces a graceful report.
- **Two parameterized SQL tools cover the CDR analyzer's prompt surface.**
  `query_cdr_summary(region, days_back)` returns the call_type × call_status
  breakdown; `query_cdr_worst_towers(region, days_back, limit)` ranks
  cell towers by (dropped + failed) / total. Both run as fixed-shape
  aggregations against the SQLite `call_records` table in under 50 ms.
  The agent's prompt encodes a window-mapping table ("last 7 days" →
  `days_back=7`) so dispatch is deterministic.
- **Indexed lookups on the bundled SQLite store.** `network_events` is
  indexed on `(region, severity, started_at)` across 50 000 events / 10
  cities / 6 months of seed data; `call_records` is indexed on
  `(region, call_date)`. Time-windowed scans complete in under 50 ms
  end-to-end. Seed data slides with `datetime.now()` so the demo never
  goes stale.
- **Vertex AI failover that's visible in the UI.** Every LLM call routes
  through `RegionFailoverGemini`, which targets the single `global` Vertex
  endpoint and walks a 4-attempt **model ladder** on `RESOURCE_EXHAUSTED`
  429 or `asyncio.TimeoutError`: primary `gemini-3.1-flash-lite-preview`
  10s → primary again after 0.5s sleep 20s → `gemini-3-flash-preview`
  intermediate 20s → `gemini-2.5-flash` GA fallback 30s. Each model has
  its own quota bucket, so the GA fallback is a real escape hatch under
  preview-pool pressure. The chat workspace renders the walk as a
  `via gemini-3.1-flash-lite-preview ↪ gemini-3-flash-preview ↪ gemini-2.5-flash`
  chip on each timeline entry — failure visible as model-swap hops, not
  a hard 500.
- **Streaming SSE chat with collapsible per-agent terminal panels.** The
  Flask workspace renders the agent run as a four-card vertical timeline
  with a Claude-Code-style terminal panel inside each card (traffic-light
  bar + populated mono output below). Each panel collapses by default and
  expands on click. Live timer + status pill + model-failover chip stay
  visible without expanding.
- **Persistent structured output.** Every run inserts an auditable row in
  the SQLite `incident_tickets` table with category, region, related events,
  CDR findings, and a NOC recommendation. AUTOINCREMENT picks up from the
  seed's MAX(ticket_id)+1 so agent-written rows don't collide with seeds.
  The workspace surfaces the saved ticket back to the operator with a
  category-keyed chip panel of recommended NOC actions.
- **Two frontends, one engine.** A custom NetPulse UI (Flask + SSE) for
  the branded demo, plus the built-in ADK Dev UI (`/events` + `/trace`
  tabs) for free observability. Both call the same
  `Runner + InMemorySessionService + root_agent`.
- **Boot-resilient by design.** MCP Toolbox client wrapped in `try/except`
  so the agent boots even when the toolbox is cold. SQLite reads from the
  data viewer tabs degrade to a friendly error if the file is missing,
  rather than crashing the Flask process. Agent runner is lazy-loaded so
  frontend tabs that don't need the agent stay functional even if the
  toolbox is unreachable.
- **Validated end-to-end.** 70+ incident tickets created across 5
  Indonesian regions and 3 issue categories during pre-submission and
  refinement-phase testing. Zero unrecovered demo failures — every
  preview-model 429 either clears on the same-model retry (most cases)
  or surfaces visibly as a model-swap chip and still produces a complete
  ticket.

## Architecture

![Architecture](docs/architecture.png)

What's load-bearing in this picture:

- **`SequentialAgent` over four `LlmAgent`s, not one big agent with four
  tools.** Each sub-agent owns one responsibility, one tool, and one
  `output_key`. Carry-over flows through `session.state`.
- **MCP Toolbox is the substrate-agnostic data gateway.** Five
  parameterized SQL tools (three network, two CDR) declared in
  `toolbox-service/tools.yaml` run against `kind: sqlite` today; flipping
  the source to `kind: alloydb-postgres` / `kind: bigquery` is a YAML edit
  with no agent-code changes. The original hackathon submission ran on
  the BigQuery + AlloyDB variants; the SQLite mode is a zero-idle-cost
  reconstitution of the same design with the agent layer untouched.
- **Vertex AI uses a model ladder at a single endpoint, not a region
  ladder.** Preview models are gated to specific regions per project, so
  the prior region ladder always 404'd on the first failover hop. Each
  model has its own quota bucket — the GA fallback is a real escape
  hatch.
- **Async ADK Runner ↔ sync Flask via thread + queue.** The Flask SSE
  generator pulls from a `queue.Queue` populated by a per-request worker
  thread that runs its own asyncio loop. The naive `asyncio.run()` wrapper
  buffers events into a list before yielding, which breaks the chat-card
  animation.

For the full design rationale, see [`docs/LESSONS.md`](docs/LESSONS.md).

## Tech stack

| Component | Technology |
|---|---|
| Agent framework | Google ADK 1.14 (`SequentialAgent` + `LlmAgent`) |
| LLM | Gemini 3.1 Flash-Lite preview (primary) + Gemini 2.5 Flash (GA fallback) on Vertex AI |
| Tool gateway | MCP Toolbox for Databases (Cloud Run) |
| Data store | SQLite bundled in the container (`data/netpulse.sqlite`) — 3 tables, 5 indexes |
| Driver | stdlib `sqlite3` (write path); MCP Toolbox `kind: sqlite-sql` (read path) |
| Custom UI | Flask 3 + Server-Sent Events |
| Hosting | Cloud Run (both services) |
| Auth | Application Default Credentials |

## Run it locally

```bash
git clone https://github.com/adityonugrohoid/hackathon-telecom-ops.git
cd hackathon-telecom-ops

python3 -m venv .venv
source .venv/bin/activate
pip install -r netpulse-ui/requirements.txt

# Build the bundled SQLite store from the seed CSVs (idempotent; <2s)
python scripts/build_sqlite.py

# Authenticate against a GCP project with Vertex AI enabled
gcloud auth application-default login

# Terminal A — MCP Toolbox over the SQLite store (downloads the v0.23.0 binary on first run)
scripts/run_toolbox_local.sh

# Terminal B — Flask UI
cd netpulse-ui
TOOLBOX_URL=http://127.0.0.1:5000 \
GOOGLE_CLOUD_PROJECT=<your-project> \
GOOGLE_CLOUD_LOCATION=global \
GOOGLE_GENAI_USE_VERTEXAI=TRUE \
  python app.py
```

Open `http://localhost:8080`. The workspace is at `/app`; three read-only
data-viewer tabs at `/network-events`, `/call-records`, `/tickets`.

To run the ADK Dev UI (events + trace tabs) instead: `adk web` from the repo
root and select `telecom_ops`.

**Bring your own data:** match the contract in
[`docs/SCHEMA.md`](docs/SCHEMA.md), drop your CSVs into
`docs/seed-data/`, and re-run `python scripts/build_sqlite.py --recreate`
to wipe and rebuild.

## Deploy

Both services run on Cloud Run. SQLite is baked into each image at build
time, so cold starts have data immediately and the runtime never reaches
outside the container except to Vertex AI.

```bash
# 1. Toolbox — scripts/deploy_toolbox.sh rebuilds SQLite from CSVs, stages
#    it into the build context, deploys, and cleans up via trap. The script
#    resolves PROJECT_ID from $PROJECT_ID or the active gcloud config.
scripts/deploy_toolbox.sh asia-southeast2
# Capture the printed Service URL — needed for step 2 as TOOLBOX_URL.

# 2. UI — the root Dockerfile re-bakes data/netpulse.sqlite during
#    `pip install` so the Flask container has its own copy for the
#    data-viewer tabs and the save_incident_ticket write path.
gcloud run deploy netpulse-ui \
  --source . \
  --project <your-project> \
  --region asia-southeast2 \
  --allow-unauthenticated \
  --max-instances=10 \
  --cpu-boost \
  --set-env-vars=GOOGLE_CLOUD_PROJECT=<your-project>,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,TOOLBOX_URL=<toolbox-url-from-step-1>
```

Scale-to-zero is intentional — no `--min-instances`, no `--no-cpu-throttling`.
The only paid runtime line item is Vertex Gemini per query (~$0.001/run on
Flash-Lite); Cloud Run + Artifact Registry sit inside the free tier for
demo cadence. Cold starts are 2–3 s; warm with a `curl` 30 s before a live
demo if first-question latency matters.

Tickets written by the agent persist for the container instance's lifetime —
Cloud Run scale-to-zero loses them across cold starts, which is acceptable
for the demo, not for production. The fix is a one-line `tools.yaml`
substrate swap to a durable backend; see [Architecture](#architecture).

## Repo layout

```
hackathon-telecom-ops/
├── telecom_ops/             # ADK agent package (4 LlmAgents + SequentialAgent)
├── netpulse-ui/             # Flask UI + SSE chat + 3 data viewer tabs
├── toolbox-service/         # MCP Toolbox image — Go binary + tools.yaml + baked SQLite
├── scripts/                 # build_sqlite.py + deploy_toolbox.sh + run_toolbox_local.sh + seed generators
├── docs/                    # SCHEMA.md, CONFIG.md, LESSONS.md, architecture.png/.mmd
│   └── seed-data/           # Canonical CSVs (network_events, call_records, incident_tickets)
├── data/                    # Generated SQLite file (gitignored; rebuilt by scripts/build_sqlite.py)
├── static-mockup-rebuild/   # Locked design sandbox (6 HTML pages, shared CSS)
├── Dockerfile               # Cloud Run image for netpulse-ui (parent-level so both packages get copied)
├── CLAUDE.md                # Project context for AI assistants
└── README.md
```

## Author & license

**Adityo Nugroho** ([@adityonugrohoid](https://github.com/adityonugrohoid))

Built for the **Gen AI Academy APAC Edition 2026** hackathon, paired with
[Claude Code](https://claude.com/claude-code).

Released under the MIT License — see [`LICENSE`](LICENSE).

## Acknowledgments

- [Google Agent Development Kit](https://google.github.io/adk-docs/) — the orchestration framework that made the four-agent chain expressible in ~50 lines of Python
- [MCP Toolbox for Databases](https://googleapis.github.io/genai-toolbox/) — the bridge that serves five parameterized SQL tools over SQLite (`kind: sqlite-sql`) from a single Go binary
- [Vertex AI Gemini](https://cloud.google.com/vertex-ai)
