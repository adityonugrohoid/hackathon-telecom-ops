# Configuration

All NetPulse AI configuration is via environment variables. There is no
`python-dotenv` dependency — the agent package auto-loads
`telecom_ops/.env` and the Flask app uses a stdlib `_load_dotenv_stdlib`
parser. Anything already in the shell wins over the file (`os.environ.setdefault`).

## Environment variables

| Variable | Purpose | Default / example |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project for Vertex AI + BQ + AlloyDB (required) | `plated-complex-491512-n6` |
| `GOOGLE_CLOUD_LOCATION` | Vertex AI inference region | `global` |
| `GOOGLE_GENAI_USE_VERTEXAI` | Force Vertex AI (vs Google AI Studio API key) | `TRUE` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to ADC JSON for local runs | `~/.config/gcloud/legacy_credentials/<account>/adc.json` |
| `DATABASE_URL` | AlloyDB SQLAlchemy URL (required) | `postgresql+pg8000://postgres:<pwd>@<host>:5432/postgres` |
| `TOOLBOX_URL` | MCP Toolbox endpoint (required by the ADK agent) | `https://network-toolbox-486319900424.us-central1.run.app` |
| `BQ_DATASET` | BigQuery dataset that owns `network_events` | `telecom_network` |
| `BQ_NETWORK_TABLE` | BigQuery table the network investigator reads | `network_events` |
| `AL_CALL_TABLE` | AlloyDB table the CDR analyzer reads | `call_records` |
| `AL_TICKET_TABLE` | AlloyDB table the response formatter writes | `incident_tickets` |
| `NL_READER_PASSWORD` | Password for the read-only `netpulse_nl_reader` role (only required when running `setup_alloydb_nl.py` or `setup_byo.sh --nl-setup`) | strong password meeting AlloyDB complexity rules |

The `BQ_*` and `AL_*` overrides exist so a fork can point NetPulse at any
GCP project + AlloyDB cluster that matches the [data contract in
`SCHEMA.md`](SCHEMA.md). Defaults preserve the hackathon wiring.

For local development, use the AlloyDB instance's public IP. For Cloud
Run, override `DATABASE_URL` with the private IP and add VPC connector
flags so the container can reach AlloyDB through the VPC.

## Bring your own data

NetPulse is dataset-driven. Match the [data contract in
`SCHEMA.md`](SCHEMA.md), override the `BQ_*` / `AL_*` env vars, and the
agents work against your infrastructure with no code changes.

The repo ships with the canonical schema in code
(`scripts/setup_bigquery.py` for BigQuery, `scripts/setup_alloydb.py` for
AlloyDB) and the original hackathon sample data in
`docs/seed-data/{network_events,call_records,incident_tickets}.csv` so a
fresh clone can stand up an end-to-end working demo against any GCP
project + AlloyDB instance.

### Bootstrap a fresh project

```bash
export GOOGLE_CLOUD_PROJECT=your-project
export GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/legacy_credentials/<account>/adc.json
export DATABASE_URL='postgresql+pg8000://postgres:<pwd>@<alloydb-host>:5432/postgres'
export NL_READER_PASSWORD='<strong-password-meeting-complexity>'  # only for --nl-setup
bash scripts/setup_byo.sh --seed --nl-setup
```

What each flag does:

- **No flags** — creates the dataset + tables only (idempotent, safe to
  re-run on an existing deployment).
- **`--seed`** — also TRUNCATE+RELOADs the seeded tables from the CSVs,
  restoring the canonical demo state.
- **`--nl-setup`** — installs the AlloyDB AI NL2SQL stack: the
  `alloydb_ai_nl` extension, an LLM model registration, the
  `netpulse_cdr_config` configuration with `call_records` registered,
  schema-context generation (blocking 3–5 min), and the
  `netpulse_nl_reader` read-only role used by the MCP Toolbox.

The NL setup requires the `alloydb_ai_nl.enabled=on` instance flag on
AlloyDB:

```bash
gcloud alloydb instances update <instance> \
  --cluster=<cluster> --region=<region> \
  --database-flags=password.enforce_complexity=on,alloydb_ai_nl.enabled=on
```

### Run the chained orchestrator manually

If you don't want the orchestrator, the underlying scripts are idempotent
and can be run directly:

```bash
python scripts/setup_bigquery.py --seed              # BQ table + load 50 000 rows
python scripts/setup_alloydb.py --seed               # AlloyDB tables + load CDRs/tickets
python scripts/setup_alloydb_nl.py                   # NL2SQL config (3–5 min blocking)
```

Pass `--recreate` to `setup_bigquery.py` if you need to reapply the
DAY-partition + `(region, severity)` cluster spec to an existing
unpartitioned table — BigQuery does not allow partition changes in
place, so the flag is destructive.

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
