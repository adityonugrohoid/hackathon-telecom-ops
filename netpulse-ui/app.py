"""NetPulse AI Flask web UI.

Wraps the existing telecom_ops ADK SequentialAgent in a streaming chat UI plus
three read-only data viewer tabs (BigQuery network events, AlloyDB call records,
AlloyDB incident tickets). Loads telecom_ops/.env via stdlib (no python-dotenv).
"""

import json
import logging
import os
from pathlib import Path

from flask import (
    Flask,
    Response,
    redirect,
    render_template,
    request,
    url_for,
)

from agent_runner import run_agent
from data_queries import (
    AL_CALL_TABLE,
    AL_TICKET_TABLE,
    ALLOWED_CALL_STATUSES,
    ALLOWED_CALL_TYPES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_REGIONS,
    ALLOWED_SEVERITIES,
    BQ_DATASET,
    BQ_NETWORK_TABLE,
    GCP_PROJECT,
    alloydb_call_records,
    alloydb_incident_tickets,
    bq_network_events,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TELECOM_ENV = PROJECT_ROOT / "telecom_ops" / ".env"


def _load_dotenv_stdlib(path: Path) -> None:
    """Read KEY=VALUE lines from path and set them in os.environ if not already set.

    Minimal .env parsing using only stdlib (no python-dotenv per CLAUDE.md).
    Lines starting with # and blank lines are ignored. Uses setdefault so any
    value already in the shell environment wins.
    """
    if not path.is_file():
        logger.warning("No .env at %s; relying on shell env", path)
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(
            key.strip(), value.strip().strip('"').strip("'")
        )


_load_dotenv_stdlib(TELECOM_ENV)

app = Flask(__name__)


@app.context_processor
def inject_dataset_names() -> dict[str, str]:
    """Expose env-driven project + dataset + table names to every template.

    Lets data-source banners and lineage labels render the current target
    instead of hardcoded `plated-complex-491512-n6.telecom_network.*` strings,
    so a fork pointing at a different GCP project shows the right path.
    """
    return {
        "gcp_project": GCP_PROJECT,
        "bq_dataset": BQ_DATASET,
        "bq_network_table": BQ_NETWORK_TABLE,
        "al_call_table": AL_CALL_TABLE,
        "al_ticket_table": AL_TICKET_TABLE,
        # Mirrors telecom_ops/agent.py:MODEL_FAST. Hardcoded here to avoid
        # the heavy ADK import chain at Flask boot — keep in sync if the
        # primary model changes.
        "active_model": "gemini-3.1-flash-lite-preview",
    }


EXAMPLE_COMPLAINTS: list[str] = [
    "Major dropped calls in Surabaya",
    "Slow internet in Jakarta during peak hours",
    "Customer charged twice for international calls",
    "Router keeps disconnecting in Bandung",
]


@app.route("/")
def landing():
    """Render the hero landing page (product-marketing entry point)."""
    return render_template(
        "landing.html",
        active_tab="landing",
        examples=EXAMPLE_COMPLAINTS,
    )


@app.route("/app")
def app_workspace():
    """Render the chat workspace UI with example query chips."""
    return render_template(
        "chat.html", active_tab="chat", examples=EXAMPLE_COMPLAINTS
    )


@app.route("/chat")
def chat():
    """Backwards-compat 301 to the new /app workspace URL."""
    return redirect(url_for("app_workspace"), code=301)


@app.route("/api/query", methods=["POST"])
def api_query():
    """SSE endpoint streaming agent_runner events as JSON-encoded SSE messages."""
    payload = request.get_json(silent=True) or {}
    query = (payload.get("query") or "").strip()
    if not query:
        return Response(
            f"data: {json.dumps({'type': 'error', 'message': 'empty query'})}\n\n",
            mimetype="text/event-stream",
        )

    def gen():
        try:
            for event in run_agent(query):
                yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:  # noqa: BLE001
            logger.exception("SSE stream failed")
            yield (
                f"data: {json.dumps({'type': 'error', 'message': str(exc)})}\n\n"
            )

    return Response(
        gen(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/network-events", methods=["GET", "POST"])
def network_events():
    """Render network events tab; POST applies filters."""
    region = request.form.get("region") or request.args.get("region") or ""
    severity = request.form.get("severity") or request.args.get("severity") or ""
    event_type = (
        request.form.get("event_type") or request.args.get("event_type") or ""
    )
    result = bq_network_events(
        region or None, severity or None, event_type or None
    )
    return render_template(
        "network_events.html",
        active_tab="network",
        result=result,
        regions=sorted(ALLOWED_REGIONS),
        severities=sorted(ALLOWED_SEVERITIES),
        event_types=sorted(ALLOWED_EVENT_TYPES),
        selected={
            "region": region,
            "severity": severity,
            "event_type": event_type,
        },
    )


@app.route("/call-records", methods=["GET", "POST"])
def call_records():
    """Render call records tab; POST applies filters."""
    region = request.form.get("region") or request.args.get("region") or ""
    call_status = (
        request.form.get("call_status") or request.args.get("call_status") or ""
    )
    call_type = (
        request.form.get("call_type") or request.args.get("call_type") or ""
    )
    result = alloydb_call_records(
        region or None, call_status or None, call_type or None
    )
    return render_template(
        "call_records.html",
        active_tab="cdr",
        result=result,
        regions=sorted(ALLOWED_REGIONS),
        statuses=sorted(ALLOWED_CALL_STATUSES),
        call_types=sorted(ALLOWED_CALL_TYPES),
        selected={
            "region": region,
            "call_status": call_status,
            "call_type": call_type,
        },
    )


@app.route("/tickets")
def tickets():
    """Render incident tickets tab (newest first)."""
    return render_template(
        "tickets.html",
        active_tab="tickets",
        result=alloydb_incident_tickets(),
    )


@app.route("/docs")
def docs():
    """Render the single-page documentation page."""
    return render_template("docs.html", active_tab="docs")


if __name__ == "__main__":
    # Cloud Run injects PORT later; locally we hardcode 8080.
    app.run(host="0.0.0.0", port=8080, debug=True)
