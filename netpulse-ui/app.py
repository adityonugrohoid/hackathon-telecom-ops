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
    ALLOWED_CALL_STATUSES,
    ALLOWED_CALL_TYPES,
    ALLOWED_EVENT_TYPES,
    ALLOWED_REGIONS,
    ALLOWED_SEVERITIES,
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


@app.route("/")
def root():
    """Redirect to the chat tab."""
    return redirect(url_for("chat"))


@app.route("/chat")
def chat():
    """Render the chat UI with example query chips."""
    examples = [
        "Major dropped calls in Surabaya",
        "Slow internet in Jakarta during peak hours",
        "Customer charged twice for international calls",
        "Router keeps disconnecting in Bandung",
    ]
    return render_template("chat.html", active_tab="chat", examples=examples)


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


if __name__ == "__main__":
    # Cloud Run injects PORT later; locally we hardcode 8080.
    app.run(host="0.0.0.0", port=8080, debug=True)
