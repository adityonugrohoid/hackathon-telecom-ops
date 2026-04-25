"""Idempotent BigQuery bootstrap: create the network_events dataset + table.

Reads:
  - GOOGLE_CLOUD_PROJECT  (required)
  - BQ_DATASET            (default: telecom_network)
  - BQ_NETWORK_TABLE      (default: network_events)
  - BQ_LOCATION           (default: US)

Pass --seed to also load `docs/seed-data/network_events.csv` after the
schema is in place. Without --seed, only the dataset + table are created
(idempotent: re-running is safe and changes nothing if both already exist).

The seed CSV layout matches the contract in `docs/SCHEMA.md`.
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from google.cloud import bigquery

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SEED_CSV = PROJECT_ROOT / "docs" / "seed-data" / "network_events.csv"

NETWORK_EVENTS_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("event_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("event_type", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("region", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("severity", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("description", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("started_at", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("resolved_at", "TIMESTAMP", mode="NULLABLE"),
    bigquery.SchemaField("affected_customers", "INTEGER", mode="REQUIRED"),
]


def ensure_dataset(client: bigquery.Client, dataset_id: str, location: str) -> None:
    """Create the dataset if missing; no-op if it already exists."""
    ref = bigquery.Dataset(f"{client.project}.{dataset_id}")
    ref.location = location
    client.create_dataset(ref, exists_ok=True)
    logger.info("Dataset ready: %s.%s (%s)", client.project, dataset_id, location)


def ensure_table(
    client: bigquery.Client, dataset_id: str, table_id: str
) -> bigquery.Table:
    """Create the network_events table if missing; return the live reference."""
    fq = f"{client.project}.{dataset_id}.{table_id}"
    try:
        table = client.get_table(fq)
        logger.info("Table already exists: %s (%d rows)", fq, table.num_rows or 0)
        return table
    except Exception:  # noqa: BLE001 - NotFound is the happy create path
        table = bigquery.Table(fq, schema=NETWORK_EVENTS_SCHEMA)
        table = client.create_table(table)
        logger.info("Created table: %s", fq)
        return table


def load_seed(
    client: bigquery.Client, dataset_id: str, table_id: str, csv_path: Path
) -> None:
    """Load the network-events seed CSV via WRITE_TRUNCATE.

    WRITE_TRUNCATE is intentional: re-running --seed restores the canonical
    sample data even if the table has been edited locally.
    """
    if not csv_path.is_file():
        raise FileNotFoundError(
            f"Seed CSV not found at {csv_path}. Run without --seed or "
            f"check that docs/seed-data/network_events.csv is committed."
        )
    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV,
        skip_leading_rows=1,
        schema=NETWORK_EVENTS_SCHEMA,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )
    fq = f"{client.project}.{dataset_id}.{table_id}"
    with csv_path.open("rb") as f:
        job = client.load_table_from_file(f, fq, job_config=job_config)
    job.result()
    final = client.get_table(fq)
    logger.info("Loaded %s rows into %s", final.num_rows, fq)


def main() -> None:
    """Orchestrate dataset + table creation, optionally seeding from CSV."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--seed",
        action="store_true",
        help="Load docs/seed-data/network_events.csv after creating the table",
    )
    args = parser.parse_args()

    project = os.environ.get("GOOGLE_CLOUD_PROJECT")
    if not project:
        logger.error("GOOGLE_CLOUD_PROJECT must be set")
        sys.exit(1)
    dataset_id = os.environ.get("BQ_DATASET", "telecom_network")
    table_id = os.environ.get("BQ_NETWORK_TABLE", "network_events")
    location = os.environ.get("BQ_LOCATION", "US")

    client = bigquery.Client(project=project)
    ensure_dataset(client, dataset_id, location)
    ensure_table(client, dataset_id, table_id)
    if args.seed:
        load_seed(client, dataset_id, table_id, SEED_CSV)


if __name__ == "__main__":
    main()
