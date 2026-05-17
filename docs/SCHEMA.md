# NetPulse data contract

NetPulse is dataset-driven. Drop your CSVs into `docs/seed-data/`, run
`python scripts/build_sqlite.py --recreate`, and the agents work against
your data — no code changes required.

The contract surface is **three tables inside a single bundled SQLite file**
(`data/netpulse.sqlite`): one of network events (read by the network
investigator agent), one of call-detail records (read by the CDR analyzer
agent), and one of incident tickets (written by the response formatter
agent).

## Environment variables that point at this contract

| Variable | Default | What it controls |
|---|---|---|
| `SQLITE_PATH` | `<repo>/data/netpulse.sqlite` | Absolute path to the bundled SQLite file |
| `NETWORK_EVENTS_TABLE` | `network_events` | Table the network investigator reads |
| `CALL_RECORDS_TABLE` | `call_records` | Table the CDR analyzer reads |
| `TICKET_TABLE` | `incident_tickets` | Table the response formatter writes |

The agents and the read-only data-viewer tabs both consume the same env-driven
names, so a single set of overrides retargets the entire stack.

## `network_events`

Network events the investigator agent searches for context (recent outages,
maintenance windows, regional impact). Read by `network_investigator` via the
MCP Toolbox `telecom_network_toolset` tools. Indexed on
`(region, severity, started_at)` plus a secondary index on `started_at` for
time-window scans.

| Column | Type | Required | Notes |
|---|---|---|---|
| `event_id` | TEXT PRIMARY KEY | yes | Stable identifier, e.g. `EVT01821` |
| `event_type` | TEXT | yes | One of: `outage`, `degradation`, `restoration`, `maintenance` |
| `region` | TEXT | yes | One of the values shared with `call_records.region` (the hackathon dataset uses 10 Indonesian metros) |
| `severity` | TEXT | yes | One of: `critical`, `major`, `minor` |
| `description` | TEXT | yes | One-sentence event summary, e.g. `Major fiber cut affecting central Jakarta` |
| `started_at` | TEXT (ISO 8601) | yes | When the event began. Drives `ORDER BY started_at DESC` queries |
| `resolved_at` | TEXT (ISO 8601) | no | NULL while ongoing |
| `affected_customers` | INTEGER | yes | Headcount, e.g. `45000`. Summed by the customer-impact card in the workspace UI |

Loaded from `docs/seed-data/network_events.csv` via `scripts/build_sqlite.py`.

## `call_records`

Call-detail records the CDR analyzer agent reads. Indexed on
`(region, call_date)` plus a secondary index on `call_status`.

| Column | Type | Required | Notes |
|---|---|---|---|
| `call_id` | INTEGER PRIMARY KEY | yes | Stable from the CSV |
| `caller_number` | TEXT | yes | E.164-ish, e.g. `08121234001` |
| `receiver_number` | TEXT | yes | Same convention |
| `call_type` | TEXT | yes | One of: `voice`, `sms`, `data` |
| `duration_seconds` | INTEGER | yes | `0` for failed/dropped calls |
| `data_usage_mb` | REAL | yes | `0` for voice/sms calls |
| `call_date` | TEXT (ISO 8601) | yes | When the call started |
| `region` | TEXT | yes | Must use the same vocabulary as `network_events.region` so the agents can correlate |
| `cell_tower_id` | TEXT | yes | E.g. `JKT-001` — used in the response formatter's NOC ticket |
| `call_status` | TEXT | yes | One of: `completed`, `dropped`, `failed` |

Loaded from `docs/seed-data/call_records.csv` via `scripts/build_sqlite.py`.

## `incident_tickets`

NetPulse-written incident tickets. The response formatter agent inserts one
row per chat session via the `save_incident_ticket` tool (stdlib `sqlite3`,
not the toolbox). The data-viewer "Incident Tickets" tab reads the same table.

| Column | Type | Required | Notes |
|---|---|---|---|
| `ticket_id` | INTEGER PRIMARY KEY AUTOINCREMENT | yes | Picks up from seed MAX(ticket_id)+1; returned to the chat UI for display |
| `category` | TEXT | yes | One of: `billing`, `network`, `hardware`, `service`, `general` (enforced by `VALID_CATEGORIES` in `telecom_ops/tools.py`) |
| `region` | TEXT | yes | Same vocabulary as `network_events.region` / `call_records.region` |
| `description` | TEXT | yes | One-sentence summary of the customer complaint |
| `related_events` | TEXT | yes | Concise list of related network events (or `none`) |
| `cdr_findings` | TEXT | yes | Concise list of CDR findings (or `none`) |
| `recommendation` | TEXT | yes | Suggested next action for the NOC |
| `status` | TEXT | no | Default `open`. Workflow column the data-viewer renders as a badge |
| `created_at` | TEXT | no | Default `datetime('now')` |

Optionally seedable from `docs/seed-data/incident_tickets.csv` via
`scripts/build_sqlite.py` for testing the data-viewer tab in a fresh checkout.

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

`scripts/build_sqlite.py` is the single bootstrap:

```bash
# Drop your CSVs into docs/seed-data/ matching the column shapes above
python scripts/build_sqlite.py --recreate
```

The script wipes any existing `data/netpulse.sqlite`, creates the three tables
plus all five indexes, and bulk-inserts your rows. Idempotent — re-running
without `--recreate` is a no-op when the file already exists.
