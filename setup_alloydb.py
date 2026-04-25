"""Idempotent DDL: ensure NetPulse's two AlloyDB tables exist, optionally seeded.

Reads:
  - DATABASE_URL    (required)
  - AL_CALL_TABLE   (default: call_records)
  - AL_TICKET_TABLE (default: incident_tickets)

Always-on behavior:
  - Create AL_TICKET_TABLE  (the table the agent writes to)
  - Create AL_CALL_TABLE    (the table the agent reads from)

Pass --seed to also TRUNCATE both tables and load:
  - docs/seed-data/call_records.csv      → AL_CALL_TABLE
  - docs/seed-data/incident_tickets.csv  → AL_TICKET_TABLE  (10 sample rows)

After loading, the SERIAL sequences are advanced past MAX(id) so subsequent
inserts via `save_incident_ticket` don't collide with the seeded IDs.

--seed is intended for fresh BYO bootstraps, not for production data preservation.
Run once before launching the telecom_ops agent.
"""

import argparse
import csv
import logging
import os
import sys
from pathlib import Path

import sqlalchemy

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent
SEED_DIR = PROJECT_ROOT / "docs" / "seed-data"

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set, e.g. "
        "postgresql+pg8000://postgres:<password>@<alloydb-host>:5432/postgres"
    )

AL_CALL_TABLE = os.environ.get("AL_CALL_TABLE", "call_records")
AL_TICKET_TABLE = os.environ.get("AL_TICKET_TABLE", "incident_tickets")

CALL_RECORDS_COLUMNS: list[str] = [
    "call_id",
    "caller_number",
    "receiver_number",
    "call_type",
    "duration_seconds",
    "data_usage_mb",
    "call_date",
    "region",
    "cell_tower_id",
    "call_status",
]
INCIDENT_TICKETS_COLUMNS: list[str] = [
    "category",
    "region",
    "description",
    "related_events",
    "cdr_findings",
    "recommendation",
    "status",
    "created_at",
]


def create_tables(conn: sqlalchemy.Connection) -> None:
    """Create both tables (idempotent CREATE TABLE IF NOT EXISTS)."""
    logger.info("Creating %s (IF NOT EXISTS)", AL_TICKET_TABLE)
    conn.execute(sqlalchemy.text(f"""
        CREATE TABLE IF NOT EXISTS {AL_TICKET_TABLE} (
            ticket_id SERIAL PRIMARY KEY,
            category TEXT,
            region TEXT,
            description TEXT,
            related_events TEXT,
            cdr_findings TEXT,
            recommendation TEXT,
            status TEXT DEFAULT 'open',
            created_at TIMESTAMP DEFAULT NOW()
        );
    """))
    logger.info("Creating %s (IF NOT EXISTS)", AL_CALL_TABLE)
    conn.execute(sqlalchemy.text(f"""
        CREATE TABLE IF NOT EXISTS {AL_CALL_TABLE} (
            call_id SERIAL PRIMARY KEY,
            caller_number TEXT NOT NULL,
            receiver_number TEXT NOT NULL,
            call_type TEXT NOT NULL,
            duration_seconds INT NOT NULL,
            data_usage_mb NUMERIC NOT NULL,
            call_date TIMESTAMP NOT NULL,
            region TEXT NOT NULL,
            cell_tower_id TEXT NOT NULL,
            call_status TEXT NOT NULL
        );
    """))


def load_csv(path: Path) -> list[dict[str, str]]:
    """Read a UTF-8 CSV with a header row into a list of dicts."""
    if not path.is_file():
        raise FileNotFoundError(
            f"Seed CSV not found at {path}. Check that the docs/seed-data/ "
            f"directory is committed to your checkout."
        )
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def truncate_and_load(
    conn: sqlalchemy.Connection,
    table: str,
    columns: list[str],
    rows: list[dict[str, str]],
) -> None:
    """TRUNCATE the target then bulk-insert rows. Caller advances the sequence."""
    logger.info("TRUNCATE %s and reload %d rows", table, len(rows))
    conn.execute(sqlalchemy.text(f"TRUNCATE TABLE {table} RESTART IDENTITY"))
    if not rows:
        return
    placeholders = ", ".join(f":{c}" for c in columns)
    insert_sql = sqlalchemy.text(
        f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})"
    )
    payload = [{c: (r.get(c) or None) for c in columns} for r in rows]
    conn.execute(insert_sql, payload)


def restart_sequence(
    conn: sqlalchemy.Connection, table: str, pk_column: str
) -> None:
    """Advance the SERIAL sequence past the loaded MAX(pk) so future inserts succeed."""
    seq_name = f"{table}_{pk_column}_seq"
    next_val = conn.execute(
        sqlalchemy.text(f"SELECT COALESCE(MAX({pk_column}), 0) + 1 FROM {table}")
    ).scalar_one()
    conn.execute(
        sqlalchemy.text("SELECT setval(:seq, :n, false)"),
        {"seq": seq_name, "n": int(next_val)},
    )
    logger.info("Sequence %s advanced to %s", seq_name, next_val)


def seed_tables(conn: sqlalchemy.Connection) -> None:
    """Load both seed CSVs and reset the SERIAL sequences past their new MAX."""
    call_rows = load_csv(SEED_DIR / "call_records.csv")
    truncate_and_load(conn, AL_CALL_TABLE, CALL_RECORDS_COLUMNS, call_rows)
    restart_sequence(conn, AL_CALL_TABLE, "call_id")

    ticket_rows = load_csv(SEED_DIR / "incident_tickets.csv")
    truncate_and_load(conn, AL_TICKET_TABLE, INCIDENT_TICKETS_COLUMNS, ticket_rows)
    restart_sequence(conn, AL_TICKET_TABLE, "ticket_id")


def main() -> None:
    """Run DDL; optionally truncate-and-load the seed CSVs."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        action="store_true",
        help=(
            "After creating tables, TRUNCATE both and reload from "
            "docs/seed-data/*.csv. Destroys existing rows — fresh-bootstrap only."
        ),
    )
    args = parser.parse_args()

    engine = sqlalchemy.create_engine(DATABASE_URL)
    with engine.begin() as conn:
        create_tables(conn)
        if args.seed:
            seed_tables(conn)
        for table in (AL_TICKET_TABLE, AL_CALL_TABLE):
            count = conn.execute(
                sqlalchemy.text(f"SELECT COUNT(*) FROM {table}")
            ).scalar()
            logger.info("Done: %s has %s rows", table, count)
    sys.exit(0)


if __name__ == "__main__":
    main()
