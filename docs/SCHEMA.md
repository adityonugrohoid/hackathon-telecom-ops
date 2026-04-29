# NetPulse data contract

NetPulse is dataset-driven. Point environment variables at any dataset matching
this contract and the agents work against your data — no code changes required.

The contract surface is **three tables across two stores**: one BigQuery table
of network events (read by the network investigator agent), one AlloyDB table
of call-detail records (read by the CDR analyzer agent), and one AlloyDB table
of incident tickets (written by the response formatter agent).

## Environment variables that point at this contract

| Variable | Default | What it controls |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | *(required)* | GCP project that owns the BigQuery dataset |
| `BQ_DATASET` | `telecom_network` | BigQuery dataset name |
| `BQ_NETWORK_TABLE` | `network_events` | BigQuery table name (within the dataset) |
| `AL_CALL_TABLE` | `call_records` | AlloyDB / PostgreSQL table the CDR analyzer reads |
| `AL_TICKET_TABLE` | `incident_tickets` | AlloyDB / PostgreSQL table the response formatter writes |

The agents and the read-only data-viewer tabs both consume the same env-driven
names, so a single set of overrides retargets the entire stack.

## BigQuery — `<GOOGLE_CLOUD_PROJECT>.<BQ_DATASET>.<BQ_NETWORK_TABLE>`

Network events the investigator agent searches for context (recent outages,
maintenance windows, regional impact). Read by `network_investigator` via the
MCP Toolbox `telecom_network_toolset` tools.

| Column | Type | Required | Notes |
|---|---|---|---|
| `event_id` | STRING | yes | Stable identifier, e.g. `EVT001` |
| `event_type` | STRING | yes | One of: `outage`, `degradation`, `restoration`, `maintenance` |
| `region` | STRING | yes | One of the values shared with `call_records.region` (the hackathon dataset uses `Jakarta`, `Surabaya`, `Bandung`, `Medan`, `Semarang`) |
| `severity` | STRING | yes | One of: `critical`, `major`, `minor` |
| `description` | STRING | yes | One-sentence event summary, e.g. `Major fiber cut affecting central Jakarta` |
| `started_at` | TIMESTAMP | yes | When the event began (UTC). Drives `ORDER BY started_at DESC` queries |
| `resolved_at` | TIMESTAMP | no | NULL while ongoing |
| `affected_customers` | INTEGER | yes | Headcount, e.g. `45000`. Summed by the customer-impact card in the workspace UI |

Loadable from `docs/seed-data/network_events.csv` via `scripts/setup_bigquery.py`.

## AlloyDB / PostgreSQL — `<AL_CALL_TABLE>`

Call-detail records the CDR analyzer agent reads. Connection is via
SQLAlchemy + `pg8000`; the table lives in whatever PostgreSQL database the
`DATABASE_URL` env var points at.

| Column | Type | Required | Notes |
|---|---|---|---|
| `call_id` | SERIAL PRIMARY KEY | yes | Auto-assigned |
| `caller_number` | TEXT | yes | E.164-ish, e.g. `08121234001` |
| `receiver_number` | TEXT | yes | Same convention |
| `call_type` | TEXT | yes | One of: `voice`, `sms`, `data` |
| `duration_seconds` | INT | yes | `0` for failed/dropped calls |
| `data_usage_mb` | NUMERIC | yes | `0` for voice/sms calls |
| `call_date` | TIMESTAMP | yes | When the call started (UTC) |
| `region` | TEXT | yes | Must use the same vocabulary as `network_events.region` so the agents can correlate |
| `cell_tower_id` | TEXT | yes | E.g. `JKT-001` — used in the response formatter's NOC ticket |
| `call_status` | TEXT | yes | One of: `completed`, `dropped`, `failed` |

Loadable from `docs/seed-data/call_records.csv` via `setup_alloydb.py --seed`.

## AlloyDB / PostgreSQL — `<AL_TICKET_TABLE>`

NetPulse-written incident tickets. The response formatter agent inserts one
row per chat session via the `save_incident_ticket` tool. The data-viewer
"Incident Tickets" tab reads the same table.

This is the only table NetPulse provisions itself — `setup_alloydb.py`'s
`CREATE TABLE IF NOT EXISTS` is the canonical DDL.

| Column | Type | Required | Notes |
|---|---|---|---|
| `ticket_id` | SERIAL PRIMARY KEY | yes | Returned to the chat UI for display |
| `category` | TEXT | yes | One of: `billing`, `network`, `hardware`, `service`, `general` (enforced by `VALID_CATEGORIES` in `telecom_ops/tools.py`) |
| `region` | TEXT | yes | Same vocabulary as `network_events.region` / `call_records.region` |
| `description` | TEXT | yes | One-sentence summary of the customer complaint |
| `related_events` | TEXT | yes | Concise list of related network events (or `none`) |
| `cdr_findings` | TEXT | yes | Concise list of CDR findings (or `none`) |
| `recommendation` | TEXT | yes | Suggested next action for the NOC |
| `status` | TEXT | no | Default `open`. Workflow column the data-viewer renders as a badge |
| `created_at` | TIMESTAMP | no | Default `NOW()` |

Optionally seedable from `docs/seed-data/incident_tickets.csv` via
`setup_alloydb.py --seed` for testing the data-viewer tab in a fresh project.

## Cross-table invariants

Two invariants matter for the agents to produce coherent output:

1. **Region vocabulary is shared.** `network_events.region`,
   `call_records.region`, and `incident_tickets.region` must all use the same
   set of strings. The classifier agent extracts a `region` from the user's
   complaint; the network investigator and CDR analyzer agents filter by it;
   the response formatter agent persists it. A mismatch silently returns
   zero rows and the final ticket loses its operational context.

2. **Category vocabulary is fixed by the agent contract.** The five
   `VALID_CATEGORIES` (`billing`, `network`, `hardware`, `service`, `general`)
   are enforced in `telecom_ops/tools.py:VALID_CATEGORIES`. A row in
   `incident_tickets` with a category outside this set will write, but the
   data-viewer's category-badge styling will fall back to the unstyled state.

## Bring your own data

`scripts/setup_byo.sh` orchestrates a one-shot bootstrap:

```bash
export GOOGLE_CLOUD_PROJECT=your-project
export DATABASE_URL=postgresql+pg8000://postgres:<pwd>@<host>:5432/postgres
bash scripts/setup_byo.sh --seed
```

It runs `scripts/setup_bigquery.py` (creates `<BQ_DATASET>.<BQ_NETWORK_TABLE>`
and loads the network-events CSV) followed by `setup_alloydb.py --seed`
(creates `<AL_CALL_TABLE>` + `<AL_TICKET_TABLE>` and optionally loads the
call-records and incident-tickets CSVs).

Override any `BQ_*` / `AL_*` env var before invoking to retarget the names.
