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

MODEL = "gemini-2.5-flash"

classifier = LlmAgent(
    model=MODEL,
    name="classifier",
    description="Classifies the telecom complaint into a category and identifies the region.",
    instruction=CLASSIFIER_INSTRUCTION,
    tools=[classify_issue],
    output_key="classification",
)

network_investigator = LlmAgent(
    model=MODEL,
    name="network_investigator",
    description="Queries the BigQuery network events database for outages relevant to the region.",
    instruction=NETWORK_INVESTIGATOR_INSTRUCTION,
    tools=network_tools,
    output_key="network_findings",
)

cdr_analyzer = LlmAgent(
    model=MODEL,
    name="cdr_analyzer",
    description="Queries AlloyDB call_records for evidence supporting the complaint.",
    instruction=CDR_ANALYZER_INSTRUCTION,
    tools=[query_cdr],
    output_key="cdr_findings",
)

response_formatter = LlmAgent(
    model=MODEL,
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
