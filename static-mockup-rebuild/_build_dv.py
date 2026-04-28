"""One-off generator for the 3 data-viewer pages.

Reads the canonical header/footer markup out of index.html and assembles
network-events.html, call-records.html, tickets.html from a shared template.
After this script runs, the 3 pages can be hand-edited independently — re-running
this script will OVERWRITE them, so don't touch it once pages diverge.
"""

from __future__ import annotations
from pathlib import Path
import re

ROOT = Path(__file__).parent
INDEX = ROOT / "index.html"

# ---------- Pull header + footer from index.html ----------
src = INDEX.read_text()
HEADER = re.search(r'<header class="nav".*?</header>', src, re.DOTALL).group(0)
FOOTER = re.search(r'<footer class="foot">.*?</footer>', src, re.DOTALL).group(0)

# ---------- Page configs ----------
PAGES: list[dict] = [
    {
        "file": "network-events.html",
        "title": "Network events — NetPulse AI",
        "source_short": "BigQuery",
        "h1_pre": "Network",
        "h1_em": "events.",
        "lede": (
            "Outages, maintenance windows, degradations, and restorations across "
            "ten Indonesian metro regions — six months of telemetry feeding the "
            "Network Investigator agent."
        ),
        "meta_pills": [
            ("table", "telecom_network.network_events"),
            ("partition", "DAY · started_at"),
            ("cluster", "region, severity"),
            ("rows", "50,000"),
        ],
        "banner": (
            "BigQuery is the source of truth for network-side incidents. "
            "The Network Investigator agent prunes by partition + cluster keys "
            "to find the few outages that match a complaint&rsquo;s region and timeframe."
        ),
        "filters": [
            ("region", "Region", ["", "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan"]),
            ("severity", "Severity", ["", "critical", "major", "minor"]),
            ("event_type", "Event type", ["", "outage", "maintenance", "degradation", "restoration"]),
        ],
        "table_cols": ["event_id", "event_type", "region", "severity", "description", "started_at", "resolved_at", "affected_customers"],
        "table_rows": [
            ["evt_48201", '<span class="dv-chip evt-outage">outage</span>',      "Jakarta",   '<span class="dv-chip sev-critical">critical</span>', "Backbone fiber cut on east-west trunk",                "2026-04-26 08:14:02", "2026-04-26 11:42:18", "182,400"],
            ["evt_48202", '<span class="dv-chip evt-degradation">degradation</span>', "Jakarta",   '<span class="dv-chip sev-major">major</span>',       "Authentication backhaul slowdown on PoP-J03",          "2026-04-26 08:22:51", "2026-04-26 10:08:33", "44,120"],
            ["evt_48203", '<span class="dv-chip evt-restoration">restoration</span>', "Jakarta",   '<span class="dv-chip sev-minor">minor</span>',       "Failover path active; primary path under repair",      "2026-04-26 11:42:18", "2026-04-26 11:42:18", "0"],
            ["evt_48168", '<span class="dv-chip evt-maintenance">maintenance</span>', "Surabaya",  '<span class="dv-chip sev-minor">minor</span>',       "Scheduled core router OS upgrade — window 02:00&ndash;04:00", "2026-04-25 02:00:00", "2026-04-25 03:48:11", "12,808"],
            ["evt_48155", '<span class="dv-chip evt-outage">outage</span>',      "Bandung",   '<span class="dv-chip sev-major">major</span>',       "Power feed B failure at Cikutra POP",                  "2026-04-24 19:33:08", "2026-04-24 22:12:44", "67,322"],
            ["evt_48140", '<span class="dv-chip evt-degradation">degradation</span>', "Medan",     '<span class="dv-chip sev-minor">minor</span>',       "Latency spike to upstream peering 39 ms &rarr; 188 ms",      "2026-04-24 14:08:00", "2026-04-24 15:01:22", "8,440"],
            ["evt_48133", '<span class="dv-chip evt-outage">outage</span>',      "Yogyakarta",'<span class="dv-chip sev-critical">critical</span>', "Optical transport ring fault, ring B in degraded state", "2026-04-23 22:14:17", "2026-04-24 02:55:09", "94,118"],
            ["evt_48127", '<span class="dv-chip evt-maintenance">maintenance</span>', "Denpasar",  '<span class="dv-chip sev-minor">minor</span>',       "Submarine cable landing-station scheduled patch",       "2026-04-23 03:00:00", "2026-04-23 04:32:55", "0"],
            ["evt_48119", '<span class="dv-chip evt-restoration">restoration</span>', "Makassar",  '<span class="dv-chip sev-minor">minor</span>',       "Cell-site B402 power restored, alarms cleared",         "2026-04-22 18:48:30", "2026-04-22 18:48:30", "0"],
            ["evt_48104", '<span class="dv-chip evt-outage">outage</span>',      "Palembang", '<span class="dv-chip sev-major">major</span>',       "Backhaul microwave path dispersed by storm front",      "2026-04-22 09:11:55", "2026-04-22 12:24:08", "31,045"],
        ],
        "schema": [
            ("event_id",            "Stable event identifier (PK). Matches the value carried forward in saved tickets&rsquo; <code>related_events</code> field."),
            ("event_type",          "One of <code>outage</code>, <code>maintenance</code>, <code>degradation</code>, <code>restoration</code>. Restorations close out a prior outage and inherit its <code>started_at</code> as their resolution time."),
            ("region",              "City-level metro identifier from a fixed 10-region whitelist. Cluster key — most queries filter here first."),
            ("severity",            "<code>critical</code> · <code>major</code> · <code>minor</code>. Cluster key. Critical events always escalate to a NOC page even if no customer complaint arrives."),
            ("description",         "Free-text operator note. Read by the Network Investigator when summarising findings in the saved ticket."),
            ("started_at",          "UTC timestamp the event was first observed. Partition key — DAY-partitioned so multi-week scans prune cheaply."),
            ("resolved_at",         "UTC timestamp the event cleared. Equal to <code>started_at</code> for instantaneous events like restorations."),
            ("affected_customers",  "Best-effort impact estimate at the time of the event. Drives the customer-impact rollup card on the workspace."),
        ],
    },
    {
        "file": "call-records.html",
        "title": "Call records — NetPulse AI",
        "source_short": "AlloyDB · NL2SQL",
        "h1_pre": "Call",
        "h1_em": "records.",
        "lede": (
            "Anonymised customer call detail records (CDRs) for the same ten metros, "
            "queried in plain English by the CDR Analyzer agent through AlloyDB AI."
        ),
        "meta_pills": [
            ("table", "public.call_records"),
            ("access", "AlloyDB AI · NL2SQL"),
            ("role", "netpulse_nl_reader"),
            ("rows", "5,000"),
        ],
        "banner": (
            "The CDR Analyzer poses one English question to <code>alloydb_ai_nl.execute_nl_query</code>. "
            "Reads run under a structurally read-only role, so even a hallucinated <code>DROP TABLE</code> "
            "from the LLM hits a permission error long before it touches data."
        ),
        "filters": [
            ("region", "Region", ["", "Jakarta", "Surabaya", "Bandung", "Medan", "Semarang", "Yogyakarta", "Denpasar", "Makassar", "Palembang", "Balikpapan"]),
            ("call_status", "Status", ["", "completed", "dropped", "failed"]),
            ("call_type", "Type", ["", "voice", "sms", "data"]),
        ],
        "table_cols": ["call_id", "caller_number", "receiver_number", "call_type", "duration_seconds", "data_usage_mb", "call_date", "region", "cell_tower_id", "call_status"],
        "table_rows": [
            ["cdr_902817", "+62 812-4421-3309", "+62 877-1108-9920", "voice", "12",    "0.0",   "2026-04-26 08:24:11", "Jakarta",   "JKT-T0042", '<span class="dv-chip cs-dropped">dropped</span>'],
            ["cdr_902816", "+62 813-9981-7720", "+62 813-7762-0114", "voice", "0",     "0.0",   "2026-04-26 08:24:08", "Jakarta",   "JKT-T0042", '<span class="dv-chip cs-failed">failed</span>'],
            ["cdr_902815", "+62 814-2210-4456", "+62 818-7714-0080", "data",  "184",   "44.7",  "2026-04-26 08:23:55", "Jakarta",   "JKT-T0029", '<span class="dv-chip cs-completed">completed</span>'],
            ["cdr_902814", "+62 819-9981-1102", "+62 821-2245-7708", "voice", "302",   "0.0",   "2026-04-26 08:23:41", "Jakarta",   "JKT-T0017", '<span class="dv-chip cs-completed">completed</span>'],
            ["cdr_902813", "+62 812-4998-6612", "+62 813-2244-1809", "sms",   "0",     "0.001", "2026-04-26 08:23:18", "Jakarta",   "JKT-T0042", '<span class="dv-chip cs-failed">failed</span>'],
            ["cdr_902765", "+62 877-3300-1182", "+62 819-2210-7708", "voice", "0",     "0.0",   "2026-04-26 07:14:00", "Surabaya",  "SBY-T0008", '<span class="dv-chip cs-failed">failed</span>'],
            ["cdr_902708", "+62 813-7782-9911", "+62 814-1109-3340", "voice", "47",    "0.0",   "2026-04-25 19:55:22", "Bandung",   "BDG-T0011", '<span class="dv-chip cs-dropped">dropped</span>'],
            ["cdr_902612", "+62 818-1142-7700", "+62 821-2210-3398", "data",  "812",   "210.4", "2026-04-25 14:08:30", "Yogyakarta","YGY-T0019", '<span class="dv-chip cs-completed">completed</span>'],
            ["cdr_902504", "+62 813-9981-3340", "+62 877-3398-1102", "voice", "0",     "0.0",   "2026-04-24 22:14:42", "Yogyakarta","YGY-T0027", '<span class="dv-chip cs-failed">failed</span>'],
            ["cdr_902487", "+62 812-1102-9981", "+62 819-9920-1108", "voice", "256",   "0.0",   "2026-04-24 18:01:55", "Makassar",  "MKS-T0003", '<span class="dv-chip cs-completed">completed</span>'],
        ],
        "schema": [
            ("call_id",          "Synthetic CDR identifier (PK). Stable across reseeds via deterministic generator."),
            ("caller_number",    "Originating MSISDN. Anonymised &mdash; safe to display in viewers."),
            ("receiver_number",  "Terminating MSISDN. Same anonymisation."),
            ("call_type",        "<code>voice</code> · <code>sms</code> · <code>data</code>. Drives volumetric rollups in the analyzer."),
            ("duration_seconds", "Voice / data session length. Zero for failed setups and SMS messages."),
            ("data_usage_mb",    "Data volume for <code>data</code> calls; zero otherwise."),
            ("call_date",        "Session start in UTC. CDR Analyzer joins this against <code>started_at</code> windows from the Network Investigator."),
            ("region",           "City-level metro derived from the originating cell tower."),
            ("cell_tower_id",    "Identifier of the originating tower. Useful for narrowing post-incident root-cause analysis."),
            ("call_status",      "<code>completed</code> · <code>dropped</code> · <code>failed</code>. Failed/dropped clusters around outage windows by design in the seed."),
        ],
    },
    {
        "file": "tickets.html",
        "title": "Incident tickets — NetPulse AI",
        "source_short": "AlloyDB · Write",
        "h1_pre": "Incident",
        "h1_em": "tickets.",
        "lede": (
            "Where every agent run lands. The Response Formatter writes a structured "
            "ticket back to AlloyDB; the NOC dispatches against it."
        ),
        "meta_pills": [
            ("table", "public.incident_tickets"),
            ("access", "agent · INSERT"),
            ("ordering", "ticket_id desc"),
            ("rows", "74+"),
        ],
        "banner": (
            "The terminal output of every agent run. Tickets are append-only "
            "&mdash; the workspace card the operator sees is rendered from the same "
            "row you&rsquo;re looking at here."
        ),
        "filters": [
            ("limit", "Limit", "input"),
        ],
        "table_cols": ["ticket_id", "category", "region", "description", "related_events", "cdr_findings", "recommendation", "status", "created_at"],
        "table_rows": [
            ["35", '<span class="dv-chip">network</span>', "Jakarta",  "Slow internet in Jakarta during peak hours",         "evt_48201, evt_48202, evt_48203", "5 dropped / 3 failed in window",  "Monitor backbone stability after recent failover; conduct post-incident review.", '<span class="dv-chip st-open">open</span>',     "2026-04-26 08:30:14"],
            ["34", '<span class="dv-chip">network</span>', "Surabaya", "No signal on multiple devices",                       "evt_48168",                       "12 failed in maintenance window", "Inform affected customers of completed maintenance; verify cell-site KPIs.",      '<span class="dv-chip st-resolved">resolved</span>', "2026-04-25 04:12:08"],
            ["33", '<span class="dv-chip">billing</span>',  "Bandung",  "Charged for service during outage",                   "evt_48155",                       "&mdash;",                                  "Issue prorated credit; route to billing-ops for review.",                          '<span class="dv-chip st-open">open</span>',     "2026-04-24 22:50:31"],
            ["32", '<span class="dv-chip">network</span>', "Medan",    "Streaming buffers constantly during evening",         "evt_48140",                       "8 dropped data sessions",         "Watch upstream peering until latency normalises; consider re-route to alt peer.", '<span class="dv-chip st-resolved">resolved</span>', "2026-04-24 15:33:12"],
            ["31", '<span class="dv-chip">network</span>', "Yogyakarta","Calls failing across the city since 10pm",            "evt_48133",                       "23 failed / 8 dropped",            "Page transport-on-call; activate ring B failover plan; notify status page.",      '<span class="dv-chip st-open">open</span>',     "2026-04-23 22:25:00"],
            ["30", '<span class="dv-chip">network</span>', "Denpasar", "Internet down briefly overnight",                     "evt_48127",                       "&mdash;",                                  "Customer notice for completed submarine-landing patch window.",                    '<span class="dv-chip st-resolved">resolved</span>', "2026-04-23 04:40:18"],
        ],
        "schema": [
            ("ticket_id",       "Auto-incrementing PK. Mirrored into the workspace UI as &ldquo;Ticket #N&rdquo;."),
            ("category",        "Coarse classification &mdash; <code>network</code>, <code>billing</code>, <code>device</code>, &hellip; &mdash; emitted by the Classifier agent."),
            ("region",          "City-level metro inferred by the Classifier from the complaint text."),
            ("description",     "Verbatim customer complaint. Persisted exactly as received."),
            ("related_events",  "Comma-separated <code>event_id</code> values surfaced by the Network Investigator. Joins back into BigQuery for forensic context."),
            ("cdr_findings",    "Free-text rollup of what the CDR Analyzer found in AlloyDB &mdash; counts of failed / dropped calls in the window of interest."),
            ("recommendation",  "Final NOC-facing action plan synthesised by the Response Formatter. Drives the workspace action-chip strip."),
            ("status",          "<code>open</code> &middot; <code>resolved</code>. Currently set by the agent on insert; manual transitions are out of scope."),
            ("created_at",      "UTC insert time. Default ordering for the viewer."),
        ],
    },
]

# ---------- Render helpers ----------
def render_meta_pills(pills):
    return "\n        ".join(
        f'<span class="dv-meta-pill"><b>{label}</b> {value}</span>'
        for label, value in pills
    )

def render_filters(filters):
    parts = []
    for f in filters:
        if isinstance(f, tuple) and len(f) == 3 and f[2] == "input":
            name, label, _ = f
            parts.append(
                f'<div class="dv-field">\n'
                f'          <label for="{name}">{label}</label>\n'
                f'          <input id="{name}" name="{name}" type="number" min="1" max="500" value="50">\n'
                f'        </div>'
            )
        else:
            name, label, options = f
            opts = "\n            ".join(
                f'<option value="{v}"{" selected" if v == "" else ""}>{v if v else "All"}</option>'
                for v in options
            )
            parts.append(
                f'<div class="dv-field">\n'
                f'          <label for="{name}">{label}</label>\n'
                f'          <select id="{name}" name="{name}">\n'
                f'            {opts}\n'
                f'          </select>\n'
                f'        </div>'
            )
    # Always include limit if not already present
    if not any(isinstance(f, tuple) and f[0] == "limit" for f in filters):
        parts.append(
            '<div class="dv-field">\n'
            '          <label for="limit">Limit</label>\n'
            '          <input id="limit" name="limit" type="number" min="1" max="500" value="50">\n'
            '        </div>'
        )
    return "\n        ".join(parts)

def render_table(cols, rows):
    head = "".join(f"<th>{c}</th>" for c in cols)
    body = "\n        ".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return head, body

def render_schema(items):
    return "\n      ".join(f"<dt>{k}</dt>\n      <dd>{v}</dd>" for k, v in items)

CROSS_LINKS = {
    "network-events.html": ('Call records', 'call-records.html', 'Incident tickets', 'tickets.html'),
    "call-records.html":   ('Network events', 'network-events.html', 'Incident tickets', 'tickets.html'),
    "tickets.html":        ('Network events', 'network-events.html', 'Call records', 'call-records.html'),
}

# ---------- Template ----------
TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{title}</title>
<meta name="description" content="NetPulse AI data viewer — {source_short}." />
<link rel="preconnect" href="https://fonts.googleapis.com" />
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
<link
  href="https://fonts.googleapis.com/css2?family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,400;0,9..144,500;0,9..144,600;0,9..144,700;1,9..144,400;1,9..144,500;1,9..144,600&family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap"
  rel="stylesheet"
/>
<link rel="stylesheet" href="css/site.css">
</head>
<body>

{header}

<!-- Page hero -->
<section class="dv-hero">
  <div class="wrap">
    <span class="eyebrow accent">/ 02 — Data Viewer · {source_short}</span>
    <h1 class="display">{h1_pre} <em>{h1_em}</em></h1>
    <p class="lede">{lede}</p>
    <div class="dv-meta-row">
        {meta_pills}
    </div>
  </div>
</section>

<div class="wrap">

  <!-- Source banner -->
  <div class="dv-source-banner" role="note">
    <span class="dv-source-banner-eyebrow">about this data</span>
    <p>{banner}</p>
  </div>

  <!-- Filter bar -->
  <form class="dv-filter" method="get" action="">
    <span class="dv-cross-eyebrow" style="flex-basis:100%">filters</span>
    {filters}
    <div class="dv-filter-actions">
      <button type="submit" class="dv-btn">Apply</button>
      <a href="" class="dv-btn dv-btn-ghost" role="button">Reset</a>
    </div>
  </form>

  <!-- Table card -->
  <div class="dv-table-card" role="region" aria-label="Result rows">
    <div class="dv-table-meta">
      <span>Showing <b>{n_rows}</b> of <b>—</b> rows · sample data</span>
      <span>last loaded · just now</span>
    </div>
    <div class="dv-table-scroll">
      <table class="dv-table">
        <thead><tr>{thead}</tr></thead>
        <tbody>
        {tbody}
        </tbody>
      </table>
    </div>
  </div>

  <!-- Schema callout -->
  <section class="dv-schema">
    <h2 class="serif">What you&rsquo;re looking <em>at.</em></h2>
    <dl class="dv-schema-list">
      {schema}
    </dl>
  </section>

  <!-- Cross-link strip -->
  <nav class="dv-cross" aria-label="Other data viewers">
    <span class="dv-cross-eyebrow">see also</span>
    <a href="{cross_a_href}">{cross_a_label} &rarr;</a>
    <a href="{cross_b_href}">{cross_b_label} &rarr;</a>
  </nav>

</div>

{footer}

<script src="js/site.js"></script>
</body>
</html>
"""

for cfg in PAGES:
    head_cells, body_cells = render_table(cfg["table_cols"], cfg["table_rows"])
    cross = CROSS_LINKS[cfg["file"]]
    rendered = TEMPLATE.format(
        title=cfg["title"],
        source_short=cfg["source_short"],
        h1_pre=cfg["h1_pre"],
        h1_em=cfg["h1_em"],
        lede=cfg["lede"],
        meta_pills=render_meta_pills(cfg["meta_pills"]),
        banner=cfg["banner"],
        filters=render_filters(cfg["filters"]),
        n_rows=len(cfg["table_rows"]),
        thead=head_cells,
        tbody=body_cells,
        schema=render_schema(cfg["schema"]),
        cross_a_label=cross[0], cross_a_href=cross[1],
        cross_b_label=cross[2], cross_b_href=cross[3],
        header=HEADER,
        footer=FOOTER,
    )
    out = ROOT / cfg["file"]
    out.write_text(rendered)
    print(f"wrote {out}  {len(rendered):,} bytes")
