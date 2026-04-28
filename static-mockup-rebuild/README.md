# NetPulse AI — Static Mockup Rebuild

A clean-room rebuild of the NetPulse AI marketing surface, built from
scratch on top of `landing-trial.html` (the canonical design reference
promoted 2026-04-27). Replaces the earlier `static-mockup/` folder,
which was abandoned after a frustrating iteration loop.

Currently five pages: landing + docs + three data viewers.

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
├── _build_dv.py               ← one-off generator for the 3 data viewer pages
├── _build_docs.py             ← one-off generator for docs.html
├── css/site.css               ← shared stylesheet, ~2,650 lines (extracted from inline)
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
- **Old `static-mockup/`** folder still exists at the repo root. Has
  uncommitted WIP edits from the abandoned iteration loop. Decide:
  delete it, leave as historical reference, or archive.
- **Live UI not yet redeployed** — I removed `(#82)` from
  `netpulse-ui/templates/landing.html` but the production Cloud Run
  revision still serves the old text. Redeploy when ready.
- **Not yet ported to Flask.** The `netpulse-ui/templates/landing.html`
  + `chat.html` in production are unchanged from before the rebuild
  iteration began. Porting is a separate decision ("design approved"
  vs. "ship to prod").

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

1. **The page surface is complete** for landing + docs + 3 data viewers.
   The dropdown nav resolves end-to-end (Documentation → docs.html,
   Architecture → docs.html#architecture, BYOD → docs.html#byod).
2. **Likely next moves**, in priority order:
   - Pick a final wordmark, remove the temp specimen strip from `index.html`.
   - Prune the orphan CSS (~250 lines) in `css/site.css`.
   - Decide the fate of the old `static-mockup/` folder (delete vs.
     archive).
   - Port the rebuild design to `netpulse-ui/templates/` so the
     production Cloud Run service inherits the new look. This is a
     larger task; do it after the static mockup is signed off.
   - Redeploy `netpulse-ui` to push the `#82` removal live.
3. **Hackathon Top-10 prototype refinement deadline** is **2026-04-30**.
