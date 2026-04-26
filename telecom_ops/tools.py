"""Native ADK tools and module-level singletons for the telecom_ops agent."""

import logging
import os

import sqlalchemy
from google.adk.tools.tool_context import ToolContext
from toolbox_core import ToolboxSyncClient

logger = logging.getLogger(__name__)

# --- Module-level singletons ----------------------------------------------

TOOLBOX_URL = os.environ.get("TOOLBOX_URL")
if not TOOLBOX_URL:
    raise RuntimeError(
        "TOOLBOX_URL must be set, e.g. "
        "https://network-toolbox-<project-number>.<region>.run.app"
    )
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set, e.g. "
        "postgresql+pg8000://postgres:<password>@<alloydb-host>:5432/postgres"
    )

AL_CALL_TABLE = os.environ.get("AL_CALL_TABLE", "call_records")
AL_TICKET_TABLE = os.environ.get("AL_TICKET_TABLE", "incident_tickets")

try:
    _toolbox = ToolboxSyncClient(TOOLBOX_URL)
    network_tools = _toolbox.load_toolset("telecom_network_toolset")
except Exception as exc:  # noqa: BLE001 - keep adk web bootable on toolbox outage
    logger.warning("MCP Toolbox unreachable; network_tools disabled: %s", exc)
    network_tools = []

_engine = sqlalchemy.create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,  # retire conns >5min old; AlloyDB drops idle TCP
)

VALID_CATEGORIES: frozenset[str] = frozenset(
    {"billing", "network", "hardware", "service", "general"}
)


# --- Native ADK tools ------------------------------------------------------

def classify_issue(
    tool_context: ToolContext,
    complaint: str,
    category: str,
    region: str,
    reasoning: str,
) -> dict[str, str]:
    """Records the classifier's structured decision into session state.

    Args:
        tool_context: ADK tool context (provides session state access).
        complaint: Verbatim user complaint text.
        category: One of billing, network, hardware, service, general.
        region: City mentioned (Jakarta, Surabaya, Bandung, Medan, Semarang) or 'unknown'.
        reasoning: One-sentence rationale for the chosen category.

    Returns:
        Dict with status, category, and region for confirmation.
    """
    tool_context.state["complaint"] = complaint
    tool_context.state["category"] = category
    tool_context.state["region"] = region
    tool_context.state["reasoning"] = reasoning
    logger.info("[classify_issue] category=%s region=%s", category, region)
    return {"status": "success", "category": category, "region": region}


def query_cdr(
    tool_context: ToolContext,
    region: str,
    status_filter: str = "",
    call_type: str = "",
    days_back: int = 0,
    limit: int = 50,
) -> dict:
    """Queries the AlloyDB call_records table for matching call detail records.

    Args:
        tool_context: ADK tool context (provides session state access).
        region: City name (e.g. Jakarta, Denpasar). Empty string for all regions.
        status_filter: Optional call_status filter: 'completed', 'dropped', 'failed'. Empty for all.
        call_type: Optional call_type filter: 'voice', 'sms', 'data'. Empty for all.
        days_back: Limit to calls within the last N days. 0 (default) = no time filter.
        limit: Max rows to return. Clamped to 1..200; default 50.

    Returns:
        Dict with status, row_count, and a list of records.
    """
    sql = (
        "SELECT call_id, caller_number, receiver_number, call_type, "
        "duration_seconds, data_usage_mb, call_date, region, "
        f"cell_tower_id, call_status FROM {AL_CALL_TABLE} WHERE 1=1"
    )
    params: dict[str, str | int] = {}
    if region:
        sql += " AND region = :region"
        params["region"] = region
    if status_filter:
        sql += " AND call_status = :status"
        params["status"] = status_filter
    if call_type:
        sql += " AND call_type = :call_type"
        params["call_type"] = call_type
    if days_back and days_back > 0:
        days_int = max(1, min(int(days_back), 365))
        sql += f" AND call_date >= NOW() - INTERVAL '{days_int} days'"
    bounded_limit = max(1, min(int(limit) if limit else 50, 200))
    sql += f" ORDER BY call_date DESC LIMIT {bounded_limit}"

    with _engine.connect() as conn:
        rows = [
            dict(row._mapping)
            for row in conn.execute(sqlalchemy.text(sql), params)
        ]

    # Stringify timestamps so the result is JSON-serializable for the LLM.
    for row in rows:
        if row.get("call_date") is not None:
            row["call_date"] = str(row["call_date"])

    tool_context.state["cdr_results"] = rows
    logger.info(
        "[query_cdr] region=%s status=%s call_type=%s days_back=%s row_count=%d",
        region,
        status_filter,
        call_type,
        days_back,
        len(rows),
    )
    return {"status": "success", "row_count": len(rows), "records": rows}


def save_incident_ticket(
    tool_context: ToolContext,
    category: str,
    region: str,
    description: str,
    related_events: str,
    cdr_findings: str,
    recommendation: str,
) -> dict:
    """Inserts a new row into incident_tickets and returns the assigned ticket_id.

    Args:
        tool_context: ADK tool context.
        category: Issue category (billing, network, hardware, service, general).
        region: Affected region.
        description: One-sentence summary of the customer complaint.
        related_events: Concise list of related network events (or 'none').
        cdr_findings: Concise list of CDR findings (or 'none').
        recommendation: Suggested next action for the NOC.

    Returns:
        Dict with status and ticket_id, or status='error' with a message
        if the category is not one of the canonical values.
    """
    if category not in VALID_CATEGORIES:
        msg = (
            f"Invalid category {category!r}; must be one of "
            f"{sorted(VALID_CATEGORIES)}"
        )
        logger.warning("[save_incident_ticket] %s", msg)
        return {"status": "error", "message": msg}

    sql = sqlalchemy.text(
        f"INSERT INTO {AL_TICKET_TABLE} "
        "(category, region, description, related_events, cdr_findings, recommendation) "
        "VALUES (:category, :region, :description, :related_events, :cdr_findings, :recommendation) "
        "RETURNING ticket_id"
    )
    with _engine.begin() as conn:
        ticket_id = conn.execute(
            sql,
            {
                "category": category,
                "region": region,
                "description": description,
                "related_events": related_events,
                "cdr_findings": cdr_findings,
                "recommendation": recommendation,
            },
        ).scalar_one()

    tool_context.state["ticket_id"] = int(ticket_id)
    logger.info("[save_incident_ticket] ticket_id=%s", ticket_id)
    return {"status": "success", "ticket_id": int(ticket_id)}
