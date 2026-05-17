# Configuration

All NetPulse AI configuration is via environment variables. There is no
`python-dotenv` dependency — the agent package auto-loads
`telecom_ops/.env` and the Flask app uses a stdlib `_load_dotenv_stdlib`
parser. Anything already in the shell wins over the file (`os.environ.setdefault`).

## Environment variables

| Variable | Purpose | Default / example |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI (required) | `velvety-transit-493310-q0` |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI inference region | `global` |
| `GOOGLE_GENAI_USE_VERTEXAI` | Force Vertex AI (vs Google AI Studio API key) | `TRUE` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to ADC JSON for local runs | `~/.config/gcloud/legacy_credentials/<account>/adc.json` |
| `TOOLBOX_URL` | MCP Toolbox endpoint (required by the ADK agent) | `http://127.0.0.1:5000` (local) / `https://network-toolbox-<n>.<region>.run.app` (Cloud Run) |
| `SQLITE_PATH` | Override the bundled SQLite path (optional) | `<repo>/data/netpulse.sqlite` |
| `NETWORK_EVENTS_TABLE` | Override the network-events table name (optional) | `network_events` |
| `CALL_RECORDS_TABLE` | Override the call-records table name (optional) | `call_records` |
| `TICKET_TABLE` | Override the incident-tickets table name (optional) | `incident_tickets` |

The only paid runtime dependency is Vertex AI. Everything else is local
(SQLite file, MCP Toolbox container, Flask app) or scale-to-zero on Cloud
Run.

## Bring your own data

NetPulse is dataset-driven. Match the [data contract in
`SCHEMA.md`](SCHEMA.md), replace the CSVs under `docs/seed-data/`, and
rebuild the SQLite file:

```bash
python3 scripts/build_sqlite.py --recreate
```

The three CSVs the script reads:

- `docs/seed-data/network_events.csv` — outage / maintenance / degradation
  / restoration rows, 8 columns matching the schema.
- `docs/seed-data/call_records.csv` — CDR rows, 10 columns.
- `docs/seed-data/incident_tickets.csv` — seed tickets the demo starts
  with; AUTOINCREMENT picks up from `MAX(ticket_id)+1`.

Indexes are created automatically after the bulk INSERT — `(region,
severity, started_at)` on events, `(region, call_date)` on CDRs, and
`created_at DESC` on tickets.

## Local development

Two terminals at the repo root:

```bash
# Terminal A — MCP Toolbox (downloads v0.23.0 binary on first run)
scripts/run_toolbox_local.sh

# Terminal B — Flask UI
cd netpulse-ui
TOOLBOX_URL=http://127.0.0.1:5000 \
GOOGLE_CLOUD_PROJECT=<your-project-with-vertex-enabled> \
GOOGLE_CLOUD_LOCATION=global \
GOOGLE_GENAI_USE_VERTEXAI=TRUE \
  ../.venv/bin/python app.py
```

`data/netpulse.sqlite` is built on first run of `run_toolbox_local.sh`
if missing; manual rebuild is `python3 scripts/build_sqlite.py --recreate`.

ADC must be authenticated:

```bash
gcloud auth application-default login
```

## Cloud Run deploy

Two services: the Flask UI and the MCP Toolbox. The SQLite file is baked
into both images at build time, so cold starts have data immediately and
nothing reaches outside the container at runtime except Vertex AI.

```bash
# UI service (root Dockerfile bakes SQLite during pip-install stage)
gcloud run deploy netpulse-ui \
  --source . \
  --region asia-southeast2 \
  --set-env-vars GOOGLE_CLOUD_PROJECT=<your-project>,GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,TOOLBOX_URL=<toolbox-cloud-run-url>

# Toolbox service (script stages SQLite into the build context, then deploys)
scripts/deploy_toolbox.sh asia-southeast2
```

## Observability

Two free observability surfaces come with the ADK Dev UI deployment:

- **`/events`** streams the sub-agent conversation, including every
  `LlmAgent` turn, every tool call, and every state mutation.
- **`/trace`** is a full timeline view with span timing for every LLM
  call and tool invocation.

The custom NetPulse UI also exposes the SSE event stream at
`POST /api/query` if you want to drive it programmatically. Each event is
JSON-encoded:

```
data: {"type": "agent_start", "agent": "classifier"}
data: {"type": "region_attempt", "agent": "classifier", "region": "global", "outcome": "ok"}
data: {"type": "tool_call", "agent": "classifier", "tool": "classify_issue", "args": {...}}
data: {"type": "tool_response", "agent": "classifier", "tool": "classify_issue", "result": {...}}
data: {"type": "text", "agent": "classifier", "text": "Category: network..."}
...
data: {"type": "complete", "ticket_id": 32, "final_report": "INCIDENT REPORT..."}
```

`region_attempt` events fire one per `RegionFailoverGemini` attempt. The
`region` field carries the **model name** the attempt ran on (the field
name is preserved from the prior region-failover design to minimize SSE
diff). On a 429 or TimeoutError you'll see an extra event with
`"outcome": "failover"` and the upstream error in `message`, immediately
followed by another attempt. The 4-attempt schedule walks: primary
(attempt 1) → primary again after 0.5s (attempt 2) →
`gemini-3-flash-preview` intermediate (attempt 3) → `gemini-2.5-flash`
GA fallback (attempt 4).
