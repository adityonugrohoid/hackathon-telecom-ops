from google.adk.agents import LlmAgent, SequentialAgent

from .prompts import (
    CDR_ANALYZER_INSTRUCTION,
    CLASSIFIER_INSTRUCTION,
    NETWORK_INVESTIGATOR_INSTRUCTION,
    RESPONSE_FORMATTER_INSTRUCTION,
)
from .tools import (
    cdr_tools,
    classify_issue,
    network_tools,
    save_incident_ticket,
)
from .vertex_failover import RegionFailoverGemini

MODEL_FAST = "gemini-3.1-flash-lite-preview"
"""Speed-tier model for all four agents (classifier, network_investigator,
cdr_analyzer, response_formatter). Each runs a tool call + small reasoning
step (or, for the formatter, a save_incident_ticket call + synthesis),
which Flash-Lite handles cheaply and quickly. Reverted 2026-04-29 from
the 2.5 GA lane (`gemini-2.5-flash-lite`) back to the 3.1 preview after a
production trace showed the network_investigator stuck "running" with no
final text event under 2.5-flash-lite — suspected to be a model behavior
where the second LLM call after the BigQuery tool result emits only a
function_call (or empty text) rather than the bulleted summary the prompt
asks for. The failover ladder retains `gemini-2.5-flash` (GA standard) as
the persistent-pressure fallback."""

MODEL_SYNTHESIS = MODEL_FAST
"""Synthesis tier collapsed onto MODEL_FAST. Phase 9 round 2 (2026-04-26)
verified that Flash-Lite-preview produces clean incident-ticket synthesis
on the response_formatter step, and keeping a single primary model means
the failover ladder behaves identically across all four agents (no
separate global-only region whitelist to maintain). Re-split this constant
if production traces show synthesis quality drops and a higher-tier model
is needed (e.g., `MODEL_SYNTHESIS = "gemini-2.5-pro"`)."""


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
    description=(
        "Queries call_records via parameterized SQL (fast path) or AlloyDB AI "
        "NL2SQL (fallback) to find evidence supporting the complaint."
    ),
    instruction=CDR_ANALYZER_INSTRUCTION,
    tools=cdr_tools,
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
