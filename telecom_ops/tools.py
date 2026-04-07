"""Native ADK tools and module-level singletons for the telecom_ops agent."""

import logging
import os

import sqlalchemy
from google.adk.tools.tool_context import ToolContext
from toolbox_core import ToolboxSyncClient

logger = logging.getLogger(__name__)

# --- Module-level singletons ----------------------------------------------

TOOLBOX_URL = "https://network-toolbox-486319900424.us-central1.run.app"
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL must be set, e.g. "
        "postgresql+pg8000://postgres:<password>@<alloydb-host>:5432/postgres"
    )

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
) -> dict:
    """Queries the AlloyDB call_records table for matching call detail records.

    Args:
        tool_context: ADK tool context (provides session state access).
        region: One of Jakarta, Surabaya, Bandung, Medan, Semarang. Empty for all regions.
        status_filter: Optional call_status filter: 'completed', 'dropped', 'failed'. Empty for all.

    Returns:
        Dict with status, row_count, and a list of records.
    """
    sql = (
        "SELECT call_id, caller_number, receiver_number, call_type, "
        "duration_seconds, data_usage_mb, call_date, region, "
        "cell_tower_id, call_status FROM call_records WHERE 1=1"
    )
    params: dict[str, str] = {}
    if region:
        sql += " AND region = :region"
        params["region"] = region
    if status_filter:
        sql += " AND call_status = :status"
        params["status"] = status_filter
    sql += " ORDER BY call_date DESC LIMIT 20"

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
        "[query_cdr] region=%s status_filter=%s row_count=%d",
        region,
        status_filter,
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
        Dict with status and ticket_id.
    """
    sql = sqlalchemy.text(
        "INSERT INTO incident_tickets "
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
