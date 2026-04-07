"""Idempotent DDL: add the incident_tickets table to the existing AlloyDB instance.

Reads the connection string from the DATABASE_URL environment variable.
Run once before launching the telecom_ops agent.
"""

import logging
import os

import sqlalchemy

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set, e.g. "
        "postgresql+pg8000://postgres:<password>@<alloydb-host>:5432/postgres"
    )


def main() -> None:
    """Create the incident_tickets table if it does not yet exist."""
    engine = sqlalchemy.create_engine(DATABASE_URL)
    with engine.begin() as conn:
        logger.info("Creating incident_tickets table (IF NOT EXISTS)")
        conn.execute(sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS incident_tickets (
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
        count = conn.execute(
            sqlalchemy.text("SELECT COUNT(*) FROM incident_tickets")
        ).scalar()
        logger.info("Done: incident_tickets has %s rows", count)


if __name__ == "__main__":
    main()
