"""Read-only data access for the NetPulse AI viewer tabs.

All three viewer tabs read from the bundled SQLite file at SQLITE_PATH.
Filter values are validated against whitelists so the only strings ever
interpolated into SQL are tokens we control; bound parameters carry the
user-supplied filter values.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parent.parent
SQLITE_PATH = Path(
    os.environ.get("SQLITE_PATH", REPO_ROOT / "data" / "netpulse.sqlite")
).resolve()
NETWORK_EVENTS_TABLE = os.environ.get("NETWORK_EVENTS_TABLE", "network_events")
CALL_RECORDS_TABLE = os.environ.get("CALL_RECORDS_TABLE", "call_records")
TICKET_TABLE = os.environ.get("TICKET_TABLE", "incident_tickets")

ALLOWED_REGIONS = {
    "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang",
    "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan",
}
ALLOWED_SEVERITIES = {"critical", "major", "minor"}
ALLOWED_EVENT_TYPES = {"outage", "maintenance", "degradation", "restoration"}
ALLOWED_CALL_STATUSES = {"completed", "dropped", "failed"}
ALLOWED_CALL_TYPES = {"voice", "sms", "data"}


@dataclass
class QueryResult:
    """Generic table-shaped query result for a Jinja template.

    Attributes:
        columns: Ordered column names matching keys in each row dict.
        rows: List of row dicts (already template-safe via _stringify).
        row_count: Length of `rows` (rows actually returned, post-LIMIT).
        total_count: Total matching rows in the source table (pre-LIMIT,
            post-filters). Lets templates render "Showing N of TOTAL"
            so users know when LIMIT truncated the result.
        limit: The LIMIT applied to this query, surfaced for the same
            "showing N of TOTAL — increase limit or refine filters" UX hint.
        error: Populated only when the query failed; rows + counts are empty.
    """

    columns: list[str] = field(default_factory=list)
    rows: list[dict[str, Any]] = field(default_factory=list)
    row_count: int = 0
    total_count: int = 0
    limit: int = 0
    error: str | None = None
    visible_min: str = ""
    visible_max: str = ""


def _connect() -> sqlite3.Connection | None:
    """Open a SQLite connection or return None if the DB file is missing.

    A missing file is treated as a soft failure so the data-viewer tabs
    render a friendly error instead of crashing the Flask process — the
    rest of the app (chat / agent runs) still works as long as the
    toolbox-side data path is healthy.
    """
    if not SQLITE_PATH.is_file():
        logger.warning("SQLite file missing at %s", SQLITE_PATH)
        return None
    try:
        conn = sqlite3.connect(str(SQLITE_PATH))
        conn.row_factory = sqlite3.Row
        return conn
    except sqlite3.Error as exc:
        logger.warning("SQLite connect failed: %s", exc)
        return None


def _stringify(v: Any) -> Any:
    """Coerce None / non-printable values into template-safe strings."""
    if v is None:
        return ""
    return v


def _iso_date(s: str | None) -> str | None:
    """Validate a YYYY-MM-DD string and return it, else None.

    Uses ``datetime.fromisoformat`` so any malformed input (e.g., the user
    pasting non-ISO text into the date field) is rejected cleanly. The SQLite
    columns are TEXT in ISO-8601, so string comparisons on a validated
    YYYY-MM-DD bound are chronologically correct.
    """
    if not s:
        return None
    try:
        datetime.fromisoformat(s)
        return s
    except ValueError:
        return None


def _row_range(rows: list[dict[str, Any]], col: str) -> tuple[str, str]:
    """Return the min/max value of ``col`` across rows (already stringified).

    Used to surface the visible date window in the dv-meta pill so the user
    sees which slice of the underlying table is on screen (the SQL is
    ``ORDER BY <col> DESC LIMIT N``, so ``rows[-1]`` is the oldest and
    ``rows[0]`` the newest, but min/max is robust to either ordering).
    """
    if not rows:
        return ("", "")
    values = [r.get(col, "") for r in rows if r.get(col)]
    if not values:
        return ("", "")
    return (min(values), max(values))


def read_network_events(
    region: str | None = None,
    severity: str | None = None,
    event_type: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    limit: int = 200,
) -> QueryResult:
    """Reads filtered network events from the bundled SQLite file.

    Args:
        region: Optional region filter; ignored if not in ALLOWED_REGIONS.
        severity: Optional severity filter; ignored if not in ALLOWED_SEVERITIES.
        event_type: Optional event_type filter; ignored if not in ALLOWED_EVENT_TYPES.
        started_after: Optional ISO-8601 date (YYYY-MM-DD) lower bound on
            started_at (inclusive). Invalid input is silently ignored.
        started_before: Optional ISO-8601 date upper bound on started_at
            (exclusive of the next day so the whole picked day is included).
            Invalid input is silently ignored.
        limit: Max rows to return.

    Returns:
        QueryResult with columns from the table schema and rows as dicts.
    """
    conn = _connect()
    if conn is None:
        return QueryResult(error=f"SQLite database not found at {SQLITE_PATH}")

    where_parts = ["1=1"]
    params: list[str] = []
    if region in ALLOWED_REGIONS:
        where_parts.append("region = ?")
        params.append(region)
    if severity in ALLOWED_SEVERITIES:
        where_parts.append("severity = ?")
        params.append(severity)
    if event_type in ALLOWED_EVENT_TYPES:
        where_parts.append("event_type = ?")
        params.append(event_type)
    after = _iso_date(started_after)
    if after:
        where_parts.append("started_at >= ?")
        params.append(after)
    before = _iso_date(started_before)
    if before:
        # Include the entire picked day by comparing against next-day 00:00.
        where_parts.append("started_at < datetime(?, '+1 day')")
        params.append(before)

    where_clause = " AND ".join(where_parts)
    cols = [
        "event_id", "event_type", "region", "severity",
        "description", "started_at", "resolved_at", "affected_customers",
    ]
    count_sql = f"SELECT COUNT(*) FROM {NETWORK_EVENTS_TABLE} WHERE {where_clause}"
    select_sql = (
        f"SELECT {', '.join(cols)} FROM {NETWORK_EVENTS_TABLE} "
        f"WHERE {where_clause} "
        f"ORDER BY started_at DESC LIMIT {int(limit)}"
    )

    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = [
            {c: _stringify(row[c]) for c in cols}
            for row in conn.execute(select_sql, params)
        ]
        vmin, vmax = _row_range(rows, "started_at")
        return QueryResult(
            columns=cols,
            rows=rows,
            row_count=len(rows),
            total_count=int(total),
            limit=int(limit),
            visible_min=vmin,
            visible_max=vmax,
        )
    except sqlite3.Error as exc:
        logger.exception("network_events query failed")
        return QueryResult(error=f"SQLite error: {exc}")
    finally:
        conn.close()


def read_call_records(
    region: str | None = None,
    call_status: str | None = None,
    call_type: str | None = None,
    started_after: str | None = None,
    started_before: str | None = None,
    limit: int = 200,
) -> QueryResult:
    """Reads filtered call_records from the bundled SQLite file.

    Args:
        region: Optional region filter.
        call_status: Optional call_status filter.
        call_type: Optional call_type filter.
        started_after: Optional ISO-8601 date lower bound on call_date.
        started_before: Optional ISO-8601 date upper bound on call_date
            (inclusive of the picked day).
        limit: Max rows to return.

    Returns:
        QueryResult with the 10 columns of call_records.
    """
    conn = _connect()
    if conn is None:
        return QueryResult(error=f"SQLite database not found at {SQLITE_PATH}")

    cols = [
        "call_id", "caller_number", "receiver_number", "call_type",
        "duration_seconds", "data_usage_mb", "call_date",
        "region", "cell_tower_id", "call_status",
    ]
    where_parts = ["1=1"]
    params: list[str] = []
    if region in ALLOWED_REGIONS:
        where_parts.append("region = ?")
        params.append(region)
    if call_status in ALLOWED_CALL_STATUSES:
        where_parts.append("call_status = ?")
        params.append(call_status)
    if call_type in ALLOWED_CALL_TYPES:
        where_parts.append("call_type = ?")
        params.append(call_type)
    after = _iso_date(started_after)
    if after:
        where_parts.append("call_date >= ?")
        params.append(after)
    before = _iso_date(started_before)
    if before:
        where_parts.append("call_date < datetime(?, '+1 day')")
        params.append(before)
    where_clause = " AND ".join(where_parts)

    count_sql = f"SELECT COUNT(*) FROM {CALL_RECORDS_TABLE} WHERE {where_clause}"
    select_sql = (
        f"SELECT {', '.join(cols)} FROM {CALL_RECORDS_TABLE} "
        f"WHERE {where_clause} "
        f"ORDER BY call_date DESC LIMIT {int(limit)}"
    )

    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = [
            {c: _stringify(row[c]) for c in cols}
            for row in conn.execute(select_sql, params)
        ]
        vmin, vmax = _row_range(rows, "call_date")
        return QueryResult(
            columns=cols,
            rows=rows,
            row_count=len(rows),
            total_count=int(total),
            limit=int(limit),
            visible_min=vmin,
            visible_max=vmax,
        )
    except sqlite3.Error as exc:
        logger.exception("call_records query failed")
        return QueryResult(error=f"SQLite error: {exc}")
    finally:
        conn.close()


def read_incident_tickets(
    started_after: str | None = None,
    started_before: str | None = None,
    limit: int = 100,
) -> QueryResult:
    """Reads recent rows from incident_tickets ordered by ticket_id desc.

    Args:
        started_after: Optional ISO-8601 date lower bound on created_at.
        started_before: Optional ISO-8601 date upper bound on created_at
            (inclusive of the picked day).
        limit: Max rows to return.
    """
    conn = _connect()
    if conn is None:
        return QueryResult(error=f"SQLite database not found at {SQLITE_PATH}")

    cols = [
        "ticket_id", "category", "region", "description",
        "related_events", "cdr_findings", "recommendation",
        "status", "created_at",
    ]
    where_parts = ["1=1"]
    params: list[str] = []
    after = _iso_date(started_after)
    if after:
        where_parts.append("created_at >= ?")
        params.append(after)
    before = _iso_date(started_before)
    if before:
        where_parts.append("created_at < datetime(?, '+1 day')")
        params.append(before)
    where_clause = " AND ".join(where_parts)

    count_sql = f"SELECT COUNT(*) FROM {TICKET_TABLE} WHERE {where_clause}"
    select_sql = (
        f"SELECT {', '.join(cols)} FROM {TICKET_TABLE} WHERE {where_clause} "
        f"ORDER BY ticket_id DESC LIMIT {int(limit)}"
    )

    try:
        total = conn.execute(count_sql, params).fetchone()[0]
        rows = [
            {c: _stringify(row[c]) for c in cols}
            for row in conn.execute(select_sql, params)
        ]
        vmin, vmax = _row_range(rows, "created_at")
        return QueryResult(
            columns=cols,
            rows=rows,
            row_count=len(rows),
            total_count=int(total),
            limit=int(limit),
            visible_min=vmin,
            visible_max=vmax,
        )
    except sqlite3.Error as exc:
        logger.exception("incident_tickets query failed")
        return QueryResult(error=f"SQLite error: {exc}")
    finally:
        conn.close()
