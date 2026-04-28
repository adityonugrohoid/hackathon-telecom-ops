# NetPulse AI — Static Mockup Rebuild

A clean-room rebuild of the NetPulse AI landing page, built from scratch
on top of `landing-trial.html` (the canonical design reference promoted
2026-04-27). Replaces the earlier `static-mockup/` folder, which was
abandoned after a frustrating iteration loop.

Open `index.html` in a browser; nothing else to install. All CSS, SVG,
and JS are inlined — only external dep is Google Fonts.

## How to view

```bash
# Serve from the project root so /static-mockup-rebuild/ + the master
# logo at /netpulse-ui/static/netpulse-logo-only.svg both resolve:
cd /home/adityonugrohoid/projects/hackathon-telecom-ops
python3 -m http.server 8765 --directory .
# → http://localhost:8765/static-mockup-rebuild/
```

Or just open `index.html` directly in a browser (file://) — Google
Fonts is the only network dep.

## Page structure (top → bottom)

| # | Section | id | Status |
|---|---|---|---|
| — | Sticky nav | `#nav` | NetPulse logo + 4-link centered nav (How it works · Data Viewer ▾ · Resources ▾ · GitHub) + Try NetPulse AI CTA |
| — | Type-specimen strip | — | **Temporary** — 12 wordmark variants for picking copy treatments. Remove after final wordmark commits. |
| — | Hero (dark CTA band) | `.cta-band` | "Telecom incident / ticketing / *in seconds.*" + lede + meta + CTAs. Right column: mini wireframe diagram of the 4-agent flow (replaces orbiting rings). |
| 02 | How it works | `#how-it-works` | Premium editorial agent flow: top-in / bottom-out, 4 agent cards with hairline connectors and data-delta chips between them. |
| 03 | Data Viewer | `#data-viewer` | **Placeholder** — 3 paper cards linking to `network-events.html` / `call-records.html` / `tickets.html` (none built yet). |
| 04 | Resources | `#resources` | **Placeholder** — 3 paper cards linking to `docs.html` / `architecture.html` / `byod.html` (none built yet). |
| — | Footer | `.foot` | NetPulse logo + tagline + 4-column nav (Product · Data Viewer · Resources · Project) + GitHub social. |

There is no `01 — Products` section. The hero takes that visual slot.
Numbering starts at 02.

## Key design decisions

- **Brand wordmark** — Inter 700 with letter-spacing −0.035em. Picked
  from the 12 specimen variants in the temp strip (specimen #07).
- **Logo** — Vectorized from `netpulse-ui/static/netpulse-logo-only.png`
  via vtracer + SVGO (35 KB → 10.5 KB). Inlined in header and footer.
  Tightened `viewBox="172 164 682 658"` to crop ~17% internal whitespace.
- **Palette** — Cream paper `#F4F0E6` + deep ink `#141413` + clay coral
  `#CC785C` accent. NO pandan green here (canonical reference uses
  coral; the live Flask app keeps pandan).
- **Typography** — Fraunces (display, opsz 9..144 + SOFT axis + ss01
  italic alternates) for headlines; Inter for body; JetBrains Mono for
  technical labels and metadata.
- **Hero mini diagram** — hybrid layout: IN pill top-left, 4 agent
  cells horizontal middle, source labels hanging vertically below
  agents, OUT pill bottom-right. Cells stretch to fill the right
  column's height (matches text column via `align-items: stretch`).
- **`02 — How it works`** — same diagonal IN top-left / OUT bottom-right
  geometry as the mini, scaled up. 7-col × 5-row grid: IN pill (row 1),
  vertical drop "prompt" (row 2), 4 agent cards + 3 horizontal edges
  (row 3), vertical drop "complete state" (row 4), OUT pill (row 5).
- **Data-delta chips** — `+ category, region` / `+ network_findings` /
  `+ cdr_findings` between adjacent agents. Mono small caps, paper bg
  breaking the hairline they float above.

## Outstanding / known issues

- **Type-specimen strip is still in place** above the hero. Remove after
  final wordmark direction commits — it's marked TEMP in the markup.
- **Dropdown links don't resolve.** `network-events.html`, `docs.html`,
  `architecture.html`, `byod.html` etc. are all 404 — those pages
  aren't built yet in this rebuild.
- **Orphan CSS** in `<style>` — rules for `.hero-*`, `.products-grid`,
  `.pcard`, `.marquee`, `.manifesto`, `.quote-band`, `.watermark` are
  still defined but no longer have markup that uses them (~250 lines
  of dead CSS). Doesn't render anything; bloats the file. Can prune
  on a clean-up pass.
- **Hero-blot parallax script** at the bottom of `<script>` queries
  `.hero-blot` which no longer exists. The `if (blot && ...)` guard
  makes it a safe no-op, but it's dead code.
- **Old `static-mockup/`** folder still exists at the repo root. It has
  uncommitted WIP edits from the earlier abandoned iteration loop.
  Decide: delete it, leave as historical reference, or archive.
- **Not yet ported to Flask.** The `netpulse-ui/templates/landing.html`
  + `chat.html` in production are unchanged. Porting is a separate
  decision ("design approved" vs. "ship to prod").

## Files of note

- `index.html` — the entire mockup (~100 KB, all inlined)
- `../netpulse-ui/static/netpulse-logo-only.svg` — master logo, 10.5 KB,
  `fill="currentColor"` for theming. Used inline in header + footer.
- `../docs/architecture.mmd` + `architecture.png` — compact 9-node
  architecture diagram (vs. 13-node original). Phase 12 model ladder
  baked in.
- `../landing-trial.html` — canonical design reference. Don't edit;
  calibrate against it.

## Resume notes

If you're picking this up in a fresh session, the page is fully
self-contained — open `index.html` in a browser and you should see
the current state. The next likely moves are (1) commit to a final
wordmark and remove the temp specimen strip, (2) build out the 3 data
viewer pages + 3 resource pages so the dropdown links resolve, or
(3) prune the orphan CSS. Order is whichever matches your priority.
