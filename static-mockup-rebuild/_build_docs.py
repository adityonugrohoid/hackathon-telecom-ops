"""One-off generator for docs.html.

Reads canonical header/footer from index.html, assembles a single
long-form docs page with sticky TOC + 8 content sections.
After this script runs, docs.html can be hand-edited independently —
re-running it would overwrite hand edits.
"""

from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).parent
INDEX = ROOT / "index.html"

src = INDEX.read_text()
HEADER = re.search(r'<header class="nav".*?</header>', src, re.DOTALL).group(0)
FOOTER = re.search(r'<footer class="foot">.*?</footer>', src, re.DOTALL).group(0)

TOC = [
    ("01", "About",            "about"),
    ("02", "Architecture",     "architecture"),
    ("03", "Tech stack",       "stack"),
    ("04", "Data schema",      "data"),
    ("05", "Bring your own data", "byod"),
    ("06", "Phase history",    "phases"),
    ("07", "Roadmap",          "roadmap"),
]

STACK = [
    ("ORCHESTRATION", "Google ADK · SequentialAgent", "Coordinates four LlmAgents in order, threading session state forward through <code>output_key</code> handoffs."),
    ("MODELS",        "Vertex AI · Gemini",            "All four agents run on <code>gemini-3.1-flash-lite-preview</code> at the <code>global</code> endpoint, with a 3-attempt model ladder failing over to <code>gemini-2.5-flash</code> under quota pressure."),
    ("NETWORK DATA",  "BigQuery",                      "<code>network_events</code> table — DAY-partitioned on <code>started_at</code>, clustered by <code>(region, severity)</code>. 50,000 events across 10 metros, 6-month rolling window."),
    ("CDR DATA",      "AlloyDB AI · NL2SQL",           "<code>call_records</code> queried in plain English via <code>execute_nl_query</code>. A registered Gemini model translates the question; a structurally read-only role executes the SQL."),
    ("TICKET SINK",   "AlloyDB Postgres",              "<code>incident_tickets</code> — append-only writes via the native ADK tool <code>save_incident_ticket</code>. Connection pool refreshed every 5 minutes to dodge silent-death sockets."),
    ("TOOL TRANSPORT","MCP Toolbox",                   "Two universal BigQuery tools + one AlloyDB AI tool live in a separate Cloud Run service. Agents reach the data via the toolbox; the toolbox reaches the warehouses via service accounts."),
    ("FRONT END",     "Flask + SSE",                   "<code>netpulse-ui</code> wraps the same <code>root_agent</code> in a hero landing + workspace timeline. Each request runs its own asyncio loop in a worker thread; events stream out incrementally via Server-Sent Events."),
    ("DEPLOY",        "Cloud Run · 2 services",        "<code>netpulse-ui</code> serves the chat surface; <code>network-toolbox</code> hosts the MCP toolbox. Both built from a Dockerfile in the project root, deployed from <code>main</code>."),
]

DATA_CARDS = [
    ("BIGQUERY", "Network events", "50,000 rows · DAY-partitioned",  "network-events.html"),
    ("ALLOYDB · NL", "Call records",   "5,000 rows · NL2SQL access", "call-records.html"),
    ("ALLOYDB · W",  "Incident tickets","append-only · agent writes", "tickets.html"),
]

BYOD_STEPS = [
    "Replace the seed CSVs in <code>docs/seed-data/</code> with your own <code>network_events.csv</code> and <code>call_records.csv</code>. Keep the column shapes intact — see <a href=\"network-events.html#schema\">network events schema</a> and <a href=\"call-records.html#schema\">call records schema</a> for column-by-column descriptions.",
    "Re-run <code>scripts/setup_bigquery.py --seed --recreate</code> to drop and rebuild the BQ table with your data, then <code>setup_alloydb.py --seed</code> to load CDRs into AlloyDB. The <code>--recreate</code> flag is destructive but is the only way to reapply the partition + cluster spec.",
    "Adjust the region whitelist in <code>telecom_ops/tools.py</code> (<code>VALID_REGIONS</code>) and the toolbox config in <code>tools.yaml</code> if your cities diverge from the Indonesian-metro defaults. The agents will pick up the new vocabulary on next deploy.",
]

PHASES = [
    ("April 29, 2026", "Engineering",  "Phase 12 — Vertex model-ladder failover replaces region ladder",  "#phases"),
    ("April 28, 2026", "Architecture", "Phase 11 — AlloyDB AI NL2SQL replaces hand-written CDR SQL",      "#phases"),
    ("April 27, 2026", "Refactor",     "Phase 10 — MCP toolbox refactor 8 tools → 2 universal tools",     "#phases"),
    ("April 26, 2026", "Engineering",  "Phase 9 — Flash-Lite collapse + observer pill model unification", "#phases"),
    ("April 25, 2026", "Ship",         "Phase 8 — Single consolidated Cloud Run redeploy",                "#phases"),
    ("April 24, 2026", "Foundation",   "Phases 1–7 — Refinement runway: audit → tokens → region failover → visual redesign → UX fixes → reproducibility → story polish", "#phases"),
    ("April 23, 2026", "Milestone",    "Top 100 — APAC GenAI Academy 2026 selection",                     "#phases"),
]

ROADMAP = [
    ("tone-ink",   "NEXT", "Custom-schema BYO data",
     "Today, swapping in your own data needs CSV reshaping. Next: a schema-mapping config so any telecom-shaped feed (CDR + events + ticket sink) plugs in without touching code."),
    ("tone-pandan","SOON", "Hourly cron + drift detection",
     "Re-poll BigQuery on an hourly cadence; surface schema drift, row-count anomalies, and unfamiliar regions to the operator before they reach an agent."),
    ("",           "MAYBE","React rewrite of the workspace",
     "The current workspace is server-rendered Flask + a single inline JS handler. A SPA would unlock streaming-state inspection (per-agent JSON view, replay, diffing)."),
]

# ---------- Render helpers ----------
def li_phase(date, cat, title, href):
    return (
        f'<li><span class="date">{date}</span>'
        f'<span class="cat">{cat}</span>'
        f'<a class="title" href="{href}">{title}</a>'
        f'<span class="arrow">&rarr;</span></li>'
    )

def render_toc():
    items = "".join(
        f'<li><a href="#{anchor}"><span class="num">{num}</span><span>{label}</span></a></li>'
        for num, label, anchor in TOC
    )
    return f'<aside class="docs-toc"><div class="docs-toc-title">On this page</div><ol>{items}</ol></aside>'

def render_stack():
    cards = "".join(
        f'<div class="docs-stack-card">'
        f'<div class="docs-stack-card-eyebrow">{eb}</div>'
        f'<div class="docs-stack-card-title">{title}</div>'
        f'<div class="docs-stack-card-role">{role}</div>'
        f'</div>'
        for eb, title, role in STACK
    )
    return f'<div class="docs-stack-grid">{cards}</div>'

def render_data_cards():
    cards = "".join(
        f'<a class="docs-data-card" href="{href}">'
        f'<div class="docs-data-card-eyebrow">{eb}</div>'
        f'<div class="docs-data-card-title">{title}</div>'
        f'<div class="docs-data-card-meta">{meta}</div>'
        f'<div class="docs-data-card-arrow">Open viewer &rarr;</div>'
        f'</a>'
        for eb, title, meta, href in DATA_CARDS
    )
    return f'<div class="docs-data-grid">{cards}</div>'

def render_byod():
    items = "".join(f'<li>{step}</li>' for step in BYOD_STEPS)
    return f'<ol class="docs-steps">{items}</ol>'

def render_phases():
    items = "".join(li_phase(*p) for p in PHASES)
    return f'<ul class="docs-news">{items}</ul>'

def render_roadmap():
    cards = "".join(
        f'<div class="docs-roadmap-card {tone}">'
        f'<div class="docs-roadmap-card-eyebrow">{eb}</div>'
        f'<div class="docs-roadmap-card-title">{title}</div>'
        f'<div class="docs-roadmap-card-body">{body}</div>'
        f'</div>'
        for tone, eb, title, body in ROADMAP
    )
    return f'<div class="docs-roadmap-grid">{cards}</div>'

# ---------- Body sections ----------
SECTION_BODY = {
    "about": """
<p>NetPulse AI is a multi-agent telecom operations assistant built for the
APAC GenAI Academy 2026 hackathon. A natural-language complaint goes in;
a structured incident ticket comes out — complete with the related
network events the operator should know about, the CDR findings that
back up the customer's account of what happened, and a recommended NOC
action plan.</p>
<p>Built collaboratively with <a href="https://claude.com/claude-code">Claude Code</a>,
Anthropic's CLI agent for software engineering. Acknowledging that
up-front rather than hiding it.</p>
""",
    "architecture": """
<p>The core ADK package <code>telecom_ops</code> exposes a
<code>SequentialAgent</code> that runs four <code>LlmAgent</code> sub-agents
in order: classifier, network investigator, CDR analyzer, response
formatter. Each agent reads the previous one's session-state notes,
queries the right data store through the MCP toolbox, and hands forward
an enriched state. The fourth writes a structured ticket to AlloyDB and
the run ends.</p>
<div class="docs-arch-figure">
  <img src="img/architecture.png" alt="NetPulse AI architecture diagram">
  <div class="docs-arch-caption">User &rarr; UI &rarr; SequentialAgent (4 LlmAgents on Gemini) &rarr; MCP Toolbox &rarr; BigQuery + AlloyDB</div>
</div>
<h3>Why a SequentialAgent</h3>
<p>The four steps have strict data dependencies — the network
investigator can't run until the classifier has tagged a region; the CDR
analyzer joins on the time window the network investigator returned;
the formatter needs all three to write a coherent ticket. A
<code>SequentialAgent</code> models this as code rather than encoding it
into a prompt, so the dependency stays correct under prompt churn.</p>
<h3>Why MCP Toolbox in front of the warehouses</h3>
<p>Direct BigQuery MCP endpoints returned 403 / connection-closed on
Cloud Run during early integration. The toolbox-as-intermediary pattern
works reliably and gives one place to evolve tool definitions without
redeploying the agent service.</p>
""",
    "stack": """
<p>The complete list of moving parts. Everything is Google Cloud (the
hackathon track requires it); the LLM-side work is Vertex AI Gemini.</p>
""" + render_stack() + """
""",
    "data": """
<p>Three data surfaces feed the run. Each viewer page describes its
schema and filter dimensions in detail.</p>
""" + render_data_cards() + """
""",
    "byod": """
<p>NetPulse AI ships with seed data for ten Indonesian metros. Adapting
to a different telecom dataset is a three-step exercise:</p>
""" + render_byod() + """
<p>The agents themselves are dataset-agnostic — what changes is the
data, the region whitelist, and the natural-language prompt examples in
<code>tools.yaml</code> that ground AlloyDB AI's NL-to-SQL translation.</p>
""",
    "phases": """
<p>NetPulse AI shipped to production through a series of timeboxed
phases. Each phase landed in a single PR (in most cases) and was
visually verified end-to-end before the next began.</p>
""" + render_phases() + """
""",
    "roadmap": """
<p>The hackathon scope is a refined prototype, not a product. These are
the next directions if the project continues past 2026-04-30.</p>
""" + render_roadmap() + """
""",
}

def render_section(num, label, anchor):
    body = SECTION_BODY[anchor]
    return f"""
<section id="{anchor}" class="docs-section">
  <span class="eyebrow accent">/ {num} — {label}</span>
  <h2 class="serif">{label.replace(' ', ' ', 1) if label != 'About' else 'About'} <em>{ {'About':'NetPulse AI.', 'Architecture':'in detail.', 'Tech stack':'on Google Cloud.', 'Data schema':'three surfaces.', 'Bring your own data':'in three steps.', 'Phase history':'over time.', 'Roadmap':'next.'}[label] }</em></h2>
  {body}
</section>
"""

SECTIONS_HTML = "\n".join(render_section(*item) for item in TOC)

CROSS = """
<nav class="dv-cross" aria-label="Other surfaces">
  <span class="dv-cross-eyebrow">see also</span>
  <a href="network-events.html">Network events &rarr;</a>
  <a href="call-records.html">Call records &rarr;</a>
  <a href="tickets.html">Incident tickets &rarr;</a>
  <a href="https://github.com/" target="_blank" rel="noopener">GitHub repo &rarr;</a>
</nav>
"""

PAGE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>Documentation — NetPulse AI</title>
<meta name="description" content="The build behind NetPulse AI — architecture, stack, data, BYOD." />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,500;1,9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
  rel="stylesheet"
/>
<link rel="stylesheet" href="css/site.css">
</head>
<body>

{HEADER}

<!-- Page hero -->
<section class="dv-hero">
  <div class="wrap">
    <span class="eyebrow accent">/ 03 — Resources · Documentation</span>
    <h1 class="display">The build behind <em>NetPulse AI.</em></h1>
    <p class="lede">Architecture, data, and what it took to ship — from the four-agent SequentialAgent down to the partition keys on the BigQuery table.</p>
    <div class="dv-meta-row">
      <span class="dv-meta-pill"><b>phase</b> Top 100 · refinement</span>
      <span class="dv-meta-pill"><b>due</b> 2026-04-30</span>
      <span class="dv-meta-pill"><b>stack</b> ADK · Vertex · AlloyDB · BigQuery</span>
      <span class="dv-meta-pill"><b>code</b> github / hackathon-telecom-ops</span>
    </div>
  </div>
</section>

<div class="wrap">
  <div class="docs-shell">
    {render_toc()}
    <div class="docs-body">
      {SECTIONS_HTML}
    </div>
  </div>

  {CROSS}
</div>

{FOOTER}

<script src="js/site.js"></script>
</body>
</html>
"""

out = ROOT / "docs.html"
out.write_text(PAGE)
print(f"wrote {out}  {len(PAGE):,} bytes")
