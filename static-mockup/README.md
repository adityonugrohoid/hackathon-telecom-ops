# NetPulse AI — Static Mockup

A self-contained, no-backend HTML/CSS mockup of the redesigned NetPulse
AI surface. Open any HTML file in a browser; nothing else to install.

The design follows the spec in
[`../docs/DESIGN-SPEC-ANTHROPIC-INSPIRED.md`](../docs/DESIGN-SPEC-ANTHROPIC-INSPIRED.md).
All Anthropic-proprietary elements (logo, custom typefaces, brand copy,
campaign artwork) are replaced with original NetPulse equivalents — see
§6 of that spec for the substitution table.

## Pages

| File                  | What it shows                                                              |
|-----------------------|-----------------------------------------------------------------------------|
| `index.html`          | Landing — hero, dark feature card with agent topology, 3 release cards, mission rail, footer |
| `chat.html`           | Workspace — mocked conversation with the 4-agent timeline, impact rollup, ticket card, NOC chips |
| `network-events.html` | Data viewer — BigQuery `network_events` table, 10 sample rows with severity / type pills |
| `call-records.html`   | Data viewer — AlloyDB `call_records` table, 10 sample CDRs with status pill |
| `tickets.html`        | Data viewer — AlloyDB `incident_tickets` table, 6 sample tickets with category + status pills |
| `docs.html`           | Single-page comprehensive documentation: about, how it works, architecture, tech stack, schema reference, BYO data guide, AlloyDB AI section, Vertex failover ladder, phase history, roadmap including custom-schema future work |

## How to view

```bash
# Pick any:
open static-mockup/index.html        # macOS
xdg-open static-mockup/index.html    # Linux
explorer static-mockup\index.html    # Windows

# Or serve with the stdlib so the relative paths resolve identically to a
# real deploy:
cd static-mockup && python3 -m http.server 8000
# then visit http://localhost:8000/
```

No build step. No npm. No Flask. The Google Fonts link in each page's
`<head>` requires internet access for the Inter + Source Serif 4 fonts;
without it, the pages fall back to system fonts (Georgia for serif,
Arial / Segoe UI for sans) and remain fully functional.

## File layout

```
static-mockup/
├── README.md                  ← you are here
├── index.html                 ← landing
├── chat.html                  ← workspace mockup
├── network-events.html        ← data viewer (BQ)
├── call-records.html          ← data viewer (AlloyDB read)
├── tickets.html               ← data viewer (AlloyDB write)
├── docs.html                  ← single-page documentation
├── css/
│   └── style.css              ← all design tokens + components
└── img/
    ├── np-glyph.svg           ← logo glyph (concentric pulse rings)
    └── agent-topology.svg     ← feature-card visual (4-agent pipeline on hex mesh)
```

## What's *not* here (intentionally)

- No JavaScript framework. The single inline `onsubmit="return false"`
  on the filter forms keeps them visual-only.
- No backend wiring. All buttons + links route between mockup pages or
  to anchors within them. The "Open Workspace →" CTA goes to
  `chat.html`. The data-viewer "Filter" buttons do nothing on submit.
- No links to the deployed Cloud Run service. This mockup is for design
  review, not for staging the live app.
- No real fetch from BigQuery or AlloyDB. Sample rows in the viewer
  pages are hand-curated to match the schema in
  [`../docs/SCHEMA.md`](../docs/SCHEMA.md).

## Design tokens at a glance

- **Background**: `#faf9f5` (ivory-light)
- **Text**: `#141413` (slate-dark)
- **Brand accent**: `#4a8c5e` (NetPulse pandan)
- **Typography**: Inter (sans, 400-700) + Source Serif 4 (400-600) from Google Fonts
- **Hero scale**: clamp(56px, fluid, 96px)
- **Layout**: max content 1280px, fluid gutter clamp(20px, 4vw, 64px)
- **Radius scale**: 4 / 8 / 16 / pill

Full token list in `css/style.css` under the `:root { ... }` block (§1
of the file).

## Font system — 3 layers, 3-line swap

The stylesheet uses the heliodoron token pattern: **raw stacks → semantic
aliases → role classes**. Components consume the aliases, never the raw
stacks, so flipping a typeface is a 3-line change in `:root` — no
component CSS edits.

### Layer 1 — raw stacks (the physical fonts you load)
```css
--np-stack-sans   /* Inter */
--np-stack-serif  /* Source Serif 4 */
--np-stack-mono   /* JetBrains Mono */
```

### Layer 2 — semantic aliases (the swap knobs)
```css
--np-font-display   /* big headlines, hero, big numbers */
--np-font-text      /* body prose, hero supporting copy */
--np-font-ui        /* chrome: nav, buttons, labels, tables, badges */
--np-font-mono      /* code, tool calls */
```

### Layer 3 — role classes (apply directly in HTML)
```html
<h1 class="np-type-display-hero">Big bold headline</h1>
<p  class="np-type-body-lg">Marketing-prose paragraph</p>
<span class="np-type-detail-sm">UPPERCASE METADATA LABEL</span>
<code class="np-type-mono">tool_call(arg)</code>
```

Eleven role classes total — see the `2b. TYPE ROLE CLASSES` block in
`css/style.css` for the full list. Each bundles family + size + weight
+ leading + tracking, so one class fully describes a text role.

### Swap recipe — flip headlines to serif while keeping nav sans
1. Drop the new typeface's `<link>` into each page's `<head>` (Google
   Fonts or self-hosted).
2. Add it to the relevant raw stack:
   ```css
   --np-stack-serif: "Newsreader Variable", "Newsreader",
                     Georgia, "Times New Roman", serif;
   ```
3. Re-bind one alias:
   ```css
   --np-font-display: var(--np-stack-serif);  /* was --np-stack-sans */
   ```

That's it. Every `<h1>`, `<h2>`, `<h3>`, `<h4>`, `.np-feature-title`,
`.np-impact-num`, `.np-ticket-id`, and any element using
`.np-type-display-*` flips to serif. Nav, buttons, badges, table
headers (which use `--np-font-ui`) stay where they are.

To verify the wiring before you swap for real, paste this into the
browser console on any page:
```js
document.documentElement.style.setProperty(
  '--np-font-display', 'var(--np-stack-serif)'
);
```

## Verifying the design before promoting to Flask

1. Resize the browser from 1440 → 1024 → 768 → 390 — every page should
   collapse cleanly to single-column at the breakpoints.
2. Tab through the landing page — focus should be visible on every link
   and button.
3. Compare side-by-side with `../netpulse-ui/templates/landing.html` to
   identify what needs to change in the live Flask templates.
4. Lighthouse a11y scan on `index.html` — target ≥95.

When ready, port the components from `css/style.css` into
`netpulse-ui/static/style.css` and rewrite the Jinja templates against
the same class names.
