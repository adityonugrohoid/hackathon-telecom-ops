# NetPulse AI — Static Mockup Rebuild

A clean-room rebuild of the NetPulse AI surface, built from scratch on
top of `landing-trial.html` (the canonical design reference promoted
2026-04-27). The earlier `static-mockup/` folder has been deleted —
this rebuild is the single source of truth.

**Status: LOCKED 2026-04-28.** Six pages — landing + docs + three data
viewers + workspace (`app.html`). Next move is the full LIVE migration
to `netpulse-ui/templates/`; see
[`docs/MIGRATION-CANONICAL-DESIGN.md`](../docs/MIGRATION-CANONICAL-DESIGN.md)
for the porting plan. User triggers the migration explicitly.

## How to view

```bash
# Serve from the repo root so /static-mockup-rebuild/ + the master logo
# at /netpulse-ui/static/netpulse-logo-only.svg both resolve:
cd /home/adityonugrohoid/projects/hackathon-telecom-ops
python3 -m http.server 8765 --directory .
# → http://localhost:8765/static-mockup-rebuild/
```

Or open any `.html` directly in a browser (file://). All pages link a
single shared `css/site.css` + `js/site.js`; only external dep is Google
Fonts.

## File map

```
static-mockup-rebuild/
├── README.md                  ← this file
├── index.html                 ← landing (hero, How it works, Data Viewer, Resources, footer)
├── docs.html                  ← single comprehensive docs page (TOC + 7 sections)
├── network-events.html        ← / 02 — Data Viewer · BigQuery
├── call-records.html          ← / 02 — Data Viewer · AlloyDB · NL
├── tickets.html               ← / 02 — Data Viewer · AlloyDB · Write
├── app.html                   ← workspace mockup (matches live /app — empty/initial state)
├── _build_dv.py               ← one-off generator for the 3 data viewer pages
├── _build_docs.py             ← one-off generator for docs.html
├── css/site.css               ← shared stylesheet, ~3,000 lines (extracted from inline)
├── js/site.js                 ← sticky-nav handler, shared
└── img/
    ├── np-mark.svg            ← logo sprite (not in active use; pages still inline the SVG via header)
    └── architecture.png       ← NetPulse-palette mermaid render (re-rendered 2026-04-28)
```

## Page structure

### index.html (landing)

| # | Section | Status |
|---|---|---|
| — | Sticky nav | NetPulse logo + 4-link centered nav (How it works · Data Viewer ▾ · Resources ▾ · GitHub) + Try NetPulse AI CTA. Resources dropdown points `architecture` / `byod` to `docs.html#architecture` / `docs.html#byod`. |
| — | Type-specimen strip | **Temporary** — 12 wordmark variants. Remove after final wordmark commits. |
| — | Hero (dark CTA band) | "Telecom incident / ticketing / *in seconds.*" + lede + meta + CTAs. Right column: mini wireframe agent flow with **sample IN prompt** ("Slow internet in Jakarta during peak hours") and **sample OUT ticket** (Ticket #35 + chips + recommendation). |
| 01 | How it works | `#how-it-works` — single horizontal row: 6 cards (IN + 4 agents + OUT) separated by 5 big coral `›` chevrons. Each card has an `→ emits` footer naming the state it hands forward. |
| 02 | Data Viewer | `#data-viewer` — 3 paper cards linking to the data viewer pages. |
| 03 | Resources | `#resources` — 3 paper cards linking to `docs.html` (Documentation), `docs.html#architecture`, `docs.html#byod`. |
| — | Footer | NetPulse logo + tagline + 4-column nav + GitHub social. |

### docs.html (single comprehensive page, sticky TOC + content)

| Anchor | Section |
|---|---|
| `#about` | About NetPulse AI — what & why, Claude Code attribution. **No `#82` rank.** |
| `#architecture` | Embedded `img/architecture.png` + narrative. "Why a SequentialAgent" / "Why MCP toolbox" subheads. |
| `#stack` | 8-card grid covering Google ADK, Vertex Gemini, BigQuery, AlloyDB AI, AlloyDB write, MCP toolbox, Flask+SSE, Cloud Run. |
| `#data` | 3 paper cards linking to data viewer pages. |
| `#byod` | 3-step adaptation guide (CSV swap → re-run setup → adjust whitelist). |
| `#phases` | News-list of 7 milestones, dates spread one-per-day Apr 23–29: Top 100 → Phases 1–7 (Foundation) → Phase 8 (Ship) → 9 → 10 → 11 → 12. |
| `#roadmap` | 3 tone-coded paper cards (ink / pandan / default). |

### Data viewer pages (3)

Each follows the same 8-section template:

1. Header (mirror)
2. Page hero — eyebrow `/ 02 — Data Viewer · {Source}`, Fraunces title, Inter lede, 4 mono meta-pills
3. Source banner — paper-2 dashed-coral card with **Inter prose** (not Fraunces — switched 2026-04-28 for clarity); banner copy now name-checks real entities: `query_network_events` etc. for BigQuery; `query_cdr_nl` + `execute_nl_query` + `netpulse_nl_reader` for AlloyDB AI; `save_incident_ticket` + the `INSERT … RETURNING ticket_id` shape for tickets
4. Filter card — 2-3 selects + Limit + Apply / Reset
5. Table card — paper-white surface, mono headers, hairline rows, severity/status chips
6. Schema callout — `dt`/`dl` block describing each column briefly
7. Cross-link strip — links to the other 2 viewers
8. Footer (mirror)

### app.html (workspace mockup)

**Final form 2026-04-28.** Renders a mid-run snapshot of the live
NetPulse workspace: 3 of 4 agents complete, ticket form still
compiling. Deterministic tool-tone — Inter throughout the body,
JetBrains Mono on labels + code pills, **no italic Fraunces in the
workspace surface** (Fraunces upright is reserved for the header brand
and footer tagline only).

| # | Section | Notes |
|---|---|---|
| — | Header / footer | Same nav + foot as the other 5 pages. |
| 1 | **Top split-pane (1fr / 2fr)** | Left = `.app-prompt` card with `<textarea rows="4">` prefilled with sample complaint, Investigate button anchored bottom-right above a hairline; sample chips sit OUTSIDE the card in the spare left-column space below. Right = `.app-ticket-form` in **dark/ink** with skeleton-shimmer rows (Class ID / Classification / Region / Network Events / CDR Findings / Recommendation), coral "Compiling" pill + spinner, and a pulsing progress dot (`response_formatter is writing the ticket to AlloyDB…`). Coral shimmer overlay sweeps across the dark surface. Below 920 px the split collapses to one column. |
| 2 | **4-step `.app-timeline`** with terminal panels | Each `.app-step-card` carries name + status pill (`Done` green / `Running` coral) + timing + unified pandan-green source badges + a `.app-step-terminal` panel (paper-2 bar with traffic-light dots + `agent_name · tool_name` label + model meta on the right; paper-white body with 3 tiers). Cards 1–3 `is-done`, card 4 `is-running` with animated cursor. |
| 2a | Terminal-panel content tiers | (a) `.app-step-terminal-prose` — Inter, coral left-rule pull (the agent's reasoning summary). (b) `.app-step-terminal-cmd` — JetBrains Mono `$ tool_call(...)` with coral `$` prefix. (c) `.app-step-terminal-out` — JetBrains Mono output rows with `white-space: pre` to preserve column alignment; bolded `affected:` totals on network rows, KVP keys on classifier output, ratio columns on CDR table. |
| 3 | Populated impact card + NOC chips | Coral-bar `.app-impact-card` (558,789 customers · 6 events · 3 days · 581 dropped calls). Below: `.app-noc` chip strip, "Dispatch radio team" primary (ink-filled). |
| 4 | See-also strip | Reuses `.dv-cross` from the data viewer pages — mono "see also" eyebrow + 4 inline arrow links (Network events · Call records · Incident tickets · GitHub repo). Same markup pattern as the 3 data viewers. |

CSS for the workspace lives in two appended blocks at the bottom of
`css/site.css`: "WORKSPACE / APP PAGE" (original empty-state shapes,
~3,090 lines through here) and "WORKSPACE REDESIGN — top split pane
+ terminal-feel panels" plus "WORKSPACE REDESIGN v2 — 1/3 prompt ·
2/3 dark ticket · see-also" (the active iteration). Source-badge
variants (`.app-source-tag.adk` / `.mcp` / `.bq` / `.alloydb` /
`.local`) are all unified to a single pandan-green style.

CSS rules for ticket card / NOC chips / impact 3-cell grid (`.app-ticket`,
`.app-noc-chip`, `.app-impact`) survive in `site.css` even though they
are no longer rendered on `app.html` — they remain available for a
future "completed run" snapshot variant.

## Key design decisions (current state)

- **Brand wordmark** — Inter 700 with letter-spacing −0.035em.
- **Logo** — Vectorized from `netpulse-ui/static/netpulse-logo-only.png` via vtracer + SVGO (35 KB → 10.5 KB). Inlined in header + footer of every page (the `img/np-mark.svg` sprite was created but pages still inline the SVG since the headers were already cloned per page).
- **Palette** — Cream paper `#F4F0E6` + deep ink `#141413` + clay coral `#CC785C` accent. Pandan green `#4a8c5e` used only in the architecture diagram for the MCP-toolbox node and on landing hero badges where applicable.
- **Typography** — Fraunces (display, opsz 9..144 + SOFT axis + ss01 italic alternates) for headlines; Inter for body; JetBrains Mono for technical labels and code pills.
- **Section numbering** — `/ 01 — How it works` / `/ 02 — Data Viewer` / `/ 03 — Resources`.
- **Architecture diagram** — Mermaid file at `docs/architecture.mmd` repainted in NetPulse palette with Inter labels + JetBrains Mono metadata. Re-render with `mmdc -i docs/architecture.mmd -o docs/architecture.png -b "#F4F0E6" --scale 2`, then copy into `static-mockup-rebuild/img/`.

## Architecture diagram colour mapping

| Node | Treatment |
|---|---|
| NOC Operator + Vertex AI Gemini | deep-ink fill, cream text — terminal endpoints |
| NetPulse UI + AlloyDB read surfaces | cream paper, coral border |
| 4 LlmAgents (classifier, network, cdr, formatter) | cream paper, hairline border |
| MCP Toolbox | paper-2, pandan-green border + dark-green text |
| AlloyDB write (`incident_tickets`) | coral fill, cream text — write target |
| ADK orchestrator subgraph outline | dashed coral on near-paper-white |
| Backends subgraph outline | hairline on near-paper-white |

## Outstanding / known issues

- **Type-specimen strip** still in `index.html` above the hero. Remove
  after final wordmark direction commits (marked TEMP in the markup).
- **Orphan CSS** in `css/site.css` — rules for `.hero-*`, `.products-grid`,
  `.pcard`, `.marquee`, `.manifesto`, `.quote-band`, `.watermark` are
  still defined but no longer have markup that uses them (~250 lines
  of dead CSS). Doesn't render anything; bloats the file. Can prune
  on a clean-up pass.
- **Hero-blot parallax script** at the bottom of index.html's inline
  `<script>` queries `.hero-blot` which no longer exists. The
  `if (blot && ...)` guard makes it a safe no-op, but it's dead code.
- **`img/np-mark.svg` sprite** is created but unused — pages still inline
  the logo SVG via the duplicated header markup. If/when we want to slim
  the HTML, refactor to `<svg><use href="img/np-mark.svg#mark"/></svg>`.
- **Not yet ported to Flask.** The `netpulse-ui/templates/landing.html`
  + `chat.html` in production are unchanged from before the rebuild
  iteration began. The migration plan is captured in
  [`docs/MIGRATION-CANONICAL-DESIGN.md`](../docs/MIGRATION-CANONICAL-DESIGN.md);
  user triggers the LIVE migration explicitly.
- **`#82` removal** rides on the prod migration — already edited in
  `netpulse-ui/templates/landing.html` but never deployed; will land
  with the Cloud Run redeploy.

## Build scripts

`_build_dv.py` and `_build_docs.py` are **one-off generators**. They:

- Read the canonical header / footer out of `index.html`
- Assemble the target page(s) from typed dataclasses + a string template
- Write each output file once

The HTML files have since been **hand-edited** independently of these
scripts — re-running them would overwrite hand edits (in particular,
the elaborated About-this-data banners on the data viewer pages and the
phase-history dates / Phases 1–7 entry on docs.html). Treat the scripts
as scaffolders that have done their job; if you ever need to regenerate,
sync your hand-edits back into the script's content tables first.

Pyright will warn on `re.search(...).group(...)` lines in both scripts —
acceptable for known-good one-off generators against a known input file.

## Resume notes

If you're picking this up in a fresh session:

1. **Status: LOCKED 2026-04-28.** All six pages are complete and the
   surface is signed off — landing + docs + 3 data viewers + app
   workspace. The old `static-mockup/` folder has been deleted; this
   rebuild is the single source of truth.
2. **Next move: full LIVE migration to `netpulse-ui/templates/`.** Read
   [`../docs/MIGRATION-CANONICAL-DESIGN.md`](../docs/MIGRATION-CANONICAL-DESIGN.md)
   first — covers what ships, migration order, what must not break,
   verification, and rollback. **Do not start without explicit user
   signal.**
3. **Smaller polish items** that can land independently of the
   migration:
   - Pick a final wordmark, remove the temp specimen strip from `index.html`.
   - Prune the orphan CSS (~250 lines) in `css/site.css`.
4. **Hackathon Top-10 prototype refinement deadline** is **2026-04-30**.
