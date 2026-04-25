from google.adk.agents import LlmAgent, SequentialAgent

from .prompts import (
    CDR_ANALYZER_INSTRUCTION,
    CLASSIFIER_INSTRUCTION,
    NETWORK_INVESTIGATOR_INSTRUCTION,
    RESPONSE_FORMATTER_INSTRUCTION,
)
from .tools import (
    classify_issue,
    network_tools,
    query_cdr,
    save_incident_ticket,
)
from .vertex_failover import RegionFailoverGemini

MODEL_NAME = "gemini-2.5-flash"


def _failover_model(owner_name: str) -> RegionFailoverGemini:
    """Build a fresh failover-enabled Gemini wrapper tagged with its owner.

    Each LlmAgent gets its own instance so the per-instance failover state
    (active region, cached genai.Client) is isolated — one agent's failover
    does not bind the others to the same region. The wrapper is tagged with
    the owning agent's name so the region-attempt observer in
    `netpulse-ui/agent_runner.py` can route per-attempt telemetry back to
    the right chat-UI timeline entry.

    Args:
        owner_name: The owning `LlmAgent.name` (must match the `name=` arg
            on the LlmAgent so chat-UI selectors line up).
    """
    wrapper = RegionFailoverGemini(model=MODEL_NAME)
    wrapper.set_owner_name(owner_name)
    return wrapper


classifier = LlmAgent(
    model=_failover_model("classifier"),
    name="classifier",
    description="Classifies the telecom complaint into a category and identifies the region.",
    instruction=CLASSIFIER_INSTRUCTION,
    tools=[classify_issue],
    output_key="classification",
)

network_investigator = LlmAgent(
    model=_failover_model("network_investigator"),
    name="network_investigator",
    description="Queries the BigQuery network events database for outages relevant to the region.",
    instruction=NETWORK_INVESTIGATOR_INSTRUCTION,
    tools=network_tools,
    output_key="network_findings",
)

cdr_analyzer = LlmAgent(
    model=_failover_model("cdr_analyzer"),
    name="cdr_analyzer",
    description="Queries AlloyDB call_records for evidence supporting the complaint.",
    instruction=CDR_ANALYZER_INSTRUCTION,
    tools=[query_cdr],
    output_key="cdr_findings",
)

response_formatter = LlmAgent(
    model=_failover_model("response_formatter"),
    name="response_formatter",
    description="Synthesizes findings into a final incident report and persists it to AlloyDB.",
    instruction=RESPONSE_FORMATTER_INSTRUCTION,
    tools=[save_incident_ticket],
    output_key="final_report",
)

root_agent = SequentialAgent(
    name="telecom_ops",
    description=(
        "Multi-agent telecom operations assistant: classify the complaint, "
        "investigate network events, analyze call records, and synthesize "
        "an incident ticket."
    ),
    sub_agents=[classifier, network_investigator, cdr_analyzer, response_formatter],
)
