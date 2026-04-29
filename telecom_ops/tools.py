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

AL_TICKET_TABLE = os.environ.get("AL_TICKET_TABLE", "incident_tickets")

try:
    _toolbox = ToolboxSyncClient(TOOLBOX_URL)
    network_tools = _toolbox.load_toolset("telecom_network_toolset")
    # cdr_toolset bundles 2 parameterized fast-path tools (query_cdr_summary,
    # query_cdr_worst_towers) and 1 NL fallback (query_cdr_nl). The agent
    # picks parameterized first; NL only when the prompt cannot be expressed
    # by the structured tools. See prompts.CDR_ANALYZER_INSTRUCTION.
    cdr_tools = _toolbox.load_toolset("cdr_toolset")
except Exception as exc:  # noqa: BLE001 - keep adk web bootable on toolbox outage
    logger.warning("MCP Toolbox unreachable; tools disabled: %s", exc)
    network_tools = []
    cdr_tools = []

_engine = sqlalchemy.create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300,  # retire conns >5min old; AlloyDB drops idle TCP
)

VALID_CATEGORIES: frozenset[str] = frozenset(
    {"billing", "network", "hardware", "service", "general"}
)

MAX_COMPLAINT_CHARS = 2000


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
        Dict with status, category, and region for confirmation, or
        status='error' with a message when the complaint is empty.
    """
    cleaned = (complaint or "").strip()[:MAX_COMPLAINT_CHARS]
    if not cleaned:
        msg = "complaint is empty after stripping whitespace"
        logger.warning("[classify_issue] %s", msg)
        return {"status": "error", "message": msg}

    tool_context.state["complaint"] = cleaned
    tool_context.state["category"] = category
    tool_context.state["region"] = region
    tool_context.state["reasoning"] = reasoning
    logger.info(
        "[classify_issue] category=%s region=%s len=%d",
        category, region, len(cleaned),
    )
    return {"status": "success", "category": category, "region": region}


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
