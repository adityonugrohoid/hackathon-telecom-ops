from google.adk.agents import LlmAgent, SequentialAgent

from .prompts import (
    CDR_ANALYZER_INSTRUCTION,
    CLASSIFIER_INSTRUCTION,
    NETWORK_INVESTIGATOR_INSTRUCTION,
    RESPONSE_FORMATTER_INSTRUCTION,
)
from .tools import (
    cdr_nl_tools,
    classify_issue,
    network_tools,
    save_incident_ticket,
)
from .vertex_failover import RegionFailoverGemini

MODEL_FAST = "gemini-3.1-flash-lite-preview"
"""Speed-tier model for the three upstream agents (classifier, network_
investigator, cdr_analyzer). Each runs a tool call + small reasoning step,
which Flash-Lite handles cheaply and quickly. Preview status is acceptable
because the failover ladder catches transient outages. Revert to
`gemini-2.5-flash` (GA) if the preview endpoint becomes unstable."""

MODEL_SYNTHESIS = MODEL_FAST
"""Synthesis model for response_formatter — currently pinned to MODEL_FAST.

Phase 9 collapsed this onto MODEL_FAST after `gemini-3.1-pro-preview` proved
to be `global`-only for `plated-complex-491512-n6` (us-central1 returned 404
NOT_FOUND), which made the failover ladder a structural no-op for synthesis.
Flash-Lite is multi-region addressable, so the ladder is now usable end-to-
end for all 4 agents under the same 5s per-attempt timeout. Re-split this
constant if production traces show synthesis quality is insufficient."""


def _failover_model(owner_name: str, model_name: str) -> RegionFailoverGemini:
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
        model_name: Vertex AI publisher model id (e.g., "gemini-2.5-flash").
            Use `MODEL_FAST` for upstream agents and `MODEL_SYNTHESIS` for
            the response_formatter.
    """
    wrapper = RegionFailoverGemini(model=model_name)
    wrapper.set_owner_name(owner_name)
    return wrapper


classifier = LlmAgent(
    model=_failover_model("classifier", MODEL_FAST),
    name="classifier",
    description="Classifies the telecom complaint into a category and identifies the region.",
    instruction=CLASSIFIER_INSTRUCTION,
    tools=[classify_issue],
    output_key="classification",
)

network_investigator = LlmAgent(
    model=_failover_model("network_investigator", MODEL_FAST),
    name="network_investigator",
    description="Queries the BigQuery network events database for outages relevant to the region.",
    instruction=NETWORK_INVESTIGATOR_INSTRUCTION,
    tools=network_tools,
    output_key="network_findings",
)

cdr_analyzer = LlmAgent(
    model=_failover_model("cdr_analyzer", MODEL_FAST),
    name="cdr_analyzer",
    description="Asks AlloyDB AI NL2SQL one question against call_records to find evidence supporting the complaint.",
    instruction=CDR_ANALYZER_INSTRUCTION,
    tools=cdr_nl_tools,
    output_key="cdr_findings",
)

response_formatter = LlmAgent(
    model=_failover_model("response_formatter", MODEL_SYNTHESIS),
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
