"""Read-only data access for the NetPulse AI viewer tabs.

Owns its own SQLAlchemy engine (separate from telecom_ops.tools._engine) and its
own BigQuery client. Filter values are validated against whitelists so the only
strings ever interpolated into SQL are tokens we control.
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Any

import sqlalchemy
from google.cloud import bigquery

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set, e.g. "
        "postgresql+pg8000://postgres:<password>@<alloydb-host>:5432/postgres"
    )
GCP_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
if not GCP_PROJECT:
    raise RuntimeError(
        "GOOGLE_CLOUD_PROJECT must be set; pick a GCP project that owns the "
        "BigQuery dataset NetPulse reads from."
    )
BQ_DATASET = os.environ.get("BQ_DATASET", "telecom_network")
BQ_NETWORK_TABLE = os.environ.get("BQ_NETWORK_TABLE", "network_events")
AL_CALL_TABLE = os.environ.get("AL_CALL_TABLE", "call_records")
AL_TICKET_TABLE = os.environ.get("AL_TICKET_TABLE", "incident_tickets")

ALLOWED_REGIONS = {
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
    "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan",
}
ALLOWED_SEVERITIES = {"critical", "major", "minor"}
ALLOWED_EVENT_TYPES = {"outage", "maintenance", "degradation", "restoration"}
ALLOWED_CALL_STATUSES = {"completed", "dropped", "failed"}
ALLOWED_CALL_TYPES = {"voice", "sms", "data"}

_engine: sqlalchemy.Engine | None = None
_bq_client: bigquery.Client | None = None


@dataclass
class QueryResult:
    """Generic table-shaped query result for a Jinja template."""

    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    error: str | None = None


def _engine_or_none() -> sqlalchemy.Engine | None:
    """Lazily build the AlloyDB SQLAlchemy engine. Returns None on failure."""
    global _engine
    if _engine is None:
        try:
            _engine = sqlalchemy.create_engine(
                DATABASE_URL,
                pool_pre_ping=True,
                pool_recycle=300,  # retire conns >5min old; AlloyDB drops idle TCP
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("AlloyDB engine init failed: %s", exc)
            _engine = None
    return _engine


def _bq_or_none() -> bigquery.Client | None:
    """Lazily build the BigQuery client. Returns None on failure."""
    global _bq_client
    if _bq_client is None:
        try:
            _bq_client = bigquery.Client(project=GCP_PROJECT)
        except Exception as exc:  # noqa: BLE001
            logger.warning("BigQuery client init failed: %s", exc)
            _bq_client = None
    return _bq_client


def _stringify(v: Any) -> Any:
    """Coerce datetime / Decimal / None into JSON/template-safe values."""
    if v is None:
        return ""
    if hasattr(v, "isoformat"):
        return v.isoformat(sep=" ")
    return v


def bq_network_events(
    region: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    limit: int = 200,
) -> QueryResult:
    """Reads filtered network events from BigQuery.

    Args:
        region: Optional region filter; ignored if not in ALLOWED_REGIONS.
        severity: Optional severity filter; ignored if not in ALLOWED_SEVERITIES.
        event_type: Optional event_type filter; ignored if not in ALLOWED_EVENT_TYPES.
        limit: Max rows to return (cast through int() before interpolation).

    Returns:
        QueryResult with columns from the BQ schema and rows as dicts.
    """
    client = _bq_or_none()
    if client is None:
        return QueryResult(error="BigQuery client unavailable - check ADC")

    where = ["1=1"]
    params: list[bigquery.ScalarQueryParameter] = []
    if region in ALLOWED_REGIONS:
        where.append("region = @region")
        params.append(bigquery.ScalarQueryParameter("region", "STRING", region))
    if severity in ALLOWED_SEVERITIES:
        where.append("severity = @severity")
        params.append(bigquery.ScalarQueryParameter("severity", "STRING", severity))
    if event_type in ALLOWED_EVENT_TYPES:
        where.append("event_type = @event_type")
        params.append(bigquery.ScalarQueryParameter("event_type", "STRING", event_type))

    sql = (
        f"SELECT * FROM `{GCP_PROJECT}.{BQ_DATASET}.{BQ_NETWORK_TABLE}` "
        f"WHERE {' AND '.join(where)} "
        f"ORDER BY started_at DESC LIMIT {int(limit)}"
    )

    try:
        job = client.query(
            sql,
            job_config=bigquery.QueryJobConfig(query_parameters=params),
        )
        result = job.result()
        cols = [field.name for field in result.schema]
        rows = [{c: _stringify(row[c]) for c in cols} for row in result]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.exception("bq_network_events failed")
        return QueryResult(error=f"BigQuery error: {exc}")


def alloydb_call_records(
    region: str | None = None,
    call_status: str | None = None,
    call_type: str | None = None,
    limit: int = 200,
) -> QueryResult:
    """Reads filtered call_records from AlloyDB.

    Same whitelist pattern as bq_network_events.

    Args:
        region: Optional region filter.
        call_status: Optional call_status filter.
        call_type: Optional call_type filter.
        limit: Max rows to return.

    Returns:
        QueryResult with the 10 columns of call_records.
    """
    eng = _engine_or_none()
    if eng is None:
        return QueryResult(error="AlloyDB engine unavailable")

    cols = [
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
    sql = f"SELECT {', '.join(cols)} FROM {AL_CALL_TABLE} WHERE 1=1"
    params: dict[str, str] = {}
    if region in ALLOWED_REGIONS:
        sql += " AND region = :region"
        params["region"] = region
    if call_status in ALLOWED_CALL_STATUSES:
        sql += " AND call_status = :call_status"
        params["call_status"] = call_status
    if call_type in ALLOWED_CALL_TYPES:
        sql += " AND call_type = :call_type"
        params["call_type"] = call_type
    sql += f" ORDER BY call_date DESC LIMIT {int(limit)}"

    try:
        with eng.connect() as conn:
            result = conn.execute(sqlalchemy.text(sql), params)
            rows = [
                {c: _stringify(getattr(row, c)) for c in cols} for row in result
            ]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.exception("alloydb_call_records failed")
        return QueryResult(error=f"AlloyDB error: {exc}")


def alloydb_incident_tickets(limit: int = 100) -> QueryResult:
    """Reads recent rows from incident_tickets ordered by ticket_id desc."""
    eng = _engine_or_none()
    if eng is None:
        return QueryResult(error="AlloyDB engine unavailable")

    cols = [
        "ticket_id",
        "category",
        "region",
        "description",
        "related_events",
        "cdr_findings",
        "recommendation",
        "status",
        "created_at",
    ]
    sql = (
        f"SELECT {', '.join(cols)} FROM {AL_TICKET_TABLE} "
        f"ORDER BY ticket_id DESC LIMIT {int(limit)}"
    )

    try:
        with eng.connect() as conn:
            result = conn.execute(sqlalchemy.text(sql))
            rows = [
                {c: _stringify(getattr(row, c)) for c in cols} for row in result
            ]
        return QueryResult(columns=cols, rows=rows, row_count=len(rows))
    except Exception as exc:  # noqa: BLE001
        logger.exception("alloydb_incident_tickets failed")
        return QueryResult(error=f"AlloyDB error: {exc}")
