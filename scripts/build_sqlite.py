"""Build the bundled NetPulse SQLite file from the canonical seed CSVs.

Produces a single SQLite file at ``data/netpulse.sqlite`` (relative to
repo root) that holds all three tables the agent and UI talk to:

  - ``network_events``    (read by the network-investigator tools)
  - ``call_records``      (read by the CDR analyzer tools)
  - ``incident_tickets``  (written by ``save_incident_ticket``)

Idempotent: if the target file already exists, the script is a no-op.
Pass ``--recreate`` to wipe and rebuild from the CSVs.

Reads from:
  - ``docs/seed-data/network_events.csv``    (50_000 rows)
  - ``docs/seed-data/call_records.csv``      (5_000 rows)
  - ``docs/seed-data/incident_tickets.csv``  (~36 sample rows)

Env overrides:
  - ``SQLITE_PATH``  (default: ``<repo>/data/netpulse.sqlite``)

Indexes are created to match the access patterns of the 5 toolbox tools:
  - events:  (region, severity, started_at) for time-windowed lookups
  - CDR:     (region, call_date) for region+window aggregations
  - tickets: created_at desc for "latest ticket" reads

Run once during local dev or as a build-time step in the container image.
"""

import argparse
import csv
import logging
import os
import sqlite3
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SEED_DIR = REPO_ROOT / "docs" / "seed-data"
DEFAULT_DB_PATH = REPO_ROOT / "data" / "netpulse.sqlite"

DDL_NETWORK_EVENTS = """
CREATE TABLE network_events (
    event_id            TEXT    PRIMARY KEY,
    event_type          TEXT    NOT NULL,
    region              TEXT    NOT NULL,
    severity            TEXT    NOT NULL,
    description         TEXT    NOT NULL,
    started_at          TEXT    NOT NULL,
    resolved_at         TEXT,
    affected_customers  INTEGER NOT NULL
);
"""

DDL_CALL_RECORDS = """
CREATE TABLE call_records (
    call_id           INTEGER PRIMARY KEY,
    caller_number     TEXT    NOT NULL,
    receiver_number   TEXT    NOT NULL,
    call_type         TEXT    NOT NULL,
    duration_seconds  INTEGER NOT NULL,
    data_usage_mb     REAL    NOT NULL,
    call_date         TEXT    NOT NULL,
    region            TEXT    NOT NULL,
    cell_tower_id     TEXT    NOT NULL,
    call_status       TEXT    NOT NULL
);
"""

DDL_INCIDENT_TICKETS = """
CREATE TABLE incident_tickets (
    ticket_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    category        TEXT,
    region          TEXT,
    description     TEXT,
    related_events  TEXT,
    cdr_findings    TEXT,
    recommendation  TEXT,
    status          TEXT    DEFAULT 'open',
    created_at      TEXT    DEFAULT (datetime('now'))
);
"""

INDEX_STATEMENTS = (
    "CREATE INDEX idx_events_region_severity_started "
    "ON network_events(region, severity, started_at);",
    "CREATE INDEX idx_events_started_at "
    "ON network_events(started_at);",
    "CREATE INDEX idx_cdr_region_date "
    "ON call_records(region, call_date);",
    "CREATE INDEX idx_cdr_status "
    "ON call_records(call_status);",
    "CREATE INDEX idx_tickets_created "
    "ON incident_tickets(created_at DESC);",
)


def _load_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV with a header row into a list of dicts."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Seed CSV not found at {path}. Check that {SEED_DIR} is "
            f"committed to your checkout."
        )
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _bulk_insert(
    conn: sqlite3.Connection,
    table: str,
    columns: list[str],
    rows: list[dict[str, str]],
) -> int:
    """Bulk-insert rows into ``table`` using ``executemany``.

    Args:
        conn: Open SQLite connection.
        table: Target table name (validated by caller; not user input).
        columns: Column names in the order they appear in the VALUES tuple.
        rows: List of dicts whose keys are a superset of ``columns``.

    Returns:
        Count of rows inserted.
    """
    if not rows:
        return 0
    placeholders = ", ".join(["?"] * len(columns))
    sql = (
        f"INSERT INTO {table} ({', '.join(columns)}) "
        f"VALUES ({placeholders})"
    )
    payload = [tuple(r.get(c) or None for c in columns) for r in rows]
    conn.executemany(sql, payload)
    return len(payload)


def _seed_network_events(conn: sqlite3.Connection) -> None:
    """Load network_events from CSV."""
    rows = _load_csv(SEED_DIR / "network_events.csv")
    columns = [
        "event_id", "event_type", "region", "severity",
        "description", "started_at", "resolved_at", "affected_customers",
    ]
    n = _bulk_insert(conn, "network_events", columns, rows)
    logger.info("Loaded %d rows into network_events", n)


def _seed_call_records(conn: sqlite3.Connection) -> None:
    """Load call_records from CSV."""
    rows = _load_csv(SEED_DIR / "call_records.csv")
    columns = [
        "call_id", "caller_number", "receiver_number", "call_type",
        "duration_seconds", "data_usage_mb", "call_date",
        "region", "cell_tower_id", "call_status",
    ]
    n = _bulk_insert(conn, "call_records", columns, rows)
    logger.info("Loaded %d rows into call_records", n)


def _seed_incident_tickets(conn: sqlite3.Connection) -> None:
    """Load incident_tickets from CSV.

    The CSV's ``ticket_id`` column is used as the explicit PK so the seed
    rows preserve their canonical IDs (1..N). AUTOINCREMENT then resumes
    from MAX(ticket_id)+1 for agent-written tickets.
    """
    rows = _load_csv(SEED_DIR / "incident_tickets.csv")
    columns = [
        "ticket_id", "category", "region", "description",
        "related_events", "cdr_findings", "recommendation",
        "status", "created_at",
    ]
    n = _bulk_insert(conn, "incident_tickets", columns, rows)
    logger.info("Loaded %d rows into incident_tickets", n)


def build_database(db_path: Path) -> None:
    """Create the schema + seed all three tables in a fresh SQLite file.

    The caller is responsible for ensuring the path doesn't already exist
    (or for deleting it first under ``--recreate``).

    Args:
        db_path: Filesystem path to the SQLite file to create.
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    logger.info("Creating SQLite database at %s", db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.executescript(DDL_NETWORK_EVENTS)
        conn.executescript(DDL_CALL_RECORDS)
        conn.executescript(DDL_INCIDENT_TICKETS)

        _seed_network_events(conn)
        _seed_call_records(conn)
        _seed_incident_tickets(conn)

        for stmt in INDEX_STATEMENTS:
            conn.execute(stmt)
        logger.info("Created %d indexes", len(INDEX_STATEMENTS))

        conn.commit()
    finally:
        conn.close()


def main() -> None:
    """Entry point: build the SQLite file from CSVs, idempotent by default."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--recreate",
        action="store_true",
        help=(
            "Wipe the existing SQLite file (if any) and rebuild from the "
            "canonical CSVs. Destructive — any agent-written tickets in "
            "the existing file are lost."
        ),
    )
    args = parser.parse_args()

    db_path = Path(os.environ.get("SQLITE_PATH", DEFAULT_DB_PATH)).resolve()

    if db_path.exists() and not args.recreate:
        logger.info(
            "SQLite file already exists at %s — skipping. "
            "Pass --recreate to wipe + rebuild.",
            db_path,
        )
        sys.exit(0)

    if db_path.exists() and args.recreate:
        logger.warning("Removing existing SQLite file at %s", db_path)
        db_path.unlink()

    build_database(db_path)

    conn = sqlite3.connect(str(db_path))
    try:
        for table in ("network_events", "call_records", "incident_tickets"):
            count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            logger.info("Verified: %s has %d rows", table, count)
    finally:
        conn.close()

    logger.info("Done. SQLite file ready at %s", db_path)


if __name__ == "__main__":
    main()
