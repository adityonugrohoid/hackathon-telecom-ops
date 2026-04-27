# NetPulse AI — Homepage Redesign Spec (Anthropic-Inspired)

Source of inspiration: <https://www.anthropic.com/> (extracted via Playwright MCP, 2026-04-27, viewports 1440×900 + 390×844).

**Scope of this document.** Reusable design *system* — colors, typography
scale, spacing rhythm, layout grid, component anatomy. NOT a copy of
Anthropic's brand assets, copy, or proprietary fonts. Every proprietary
element is called out below in §6 with an original NetPulse substitution.

Captured screenshots:
- `.playwright-mcp/anthropic-hero.png` — desktop hero (1440 wide)
- `.playwright-mcp/anthropic-full.png` — full desktop scroll
- `.playwright-mcp/anthropic-mobile.png` — full mobile scroll (390 wide)
- `.playwright-mcp/anthropic-snapshot.md` — DOM accessibility snapshot

---

## 1. Design philosophy

Three observations summarise the look:

1. **Editorial restraint.** Off-white "ivory" background, near-black
   "slate" text, almost no chrome. The page reads like the front matter
   of a printed essay, not a SaaS landing page.
2. **Sans/serif duet.** A bold, condensed-feeling sans for the hero
   headline (display); a warm transitional serif for body copy and
   sub-headlines. The two carry distinct jobs and never trade places.
3. **One feature, one scroll.** The page advertises a single hero idea,
   then a single feature card on a black canvas, then a 3-card "latest"
   row, then a footnote rail, then footer. No carousels, no dense feature
   grids, no testimonial scroller.

NetPulse can adopt all three without copying a single proprietary asset.

---

## 2. Design tokens (extracted from live CSS)

These are functional values pulled from the site's `:root` custom
properties. Reuse the *scale* and *role* — the swatch hex values are also
generic enough to be safely adopted (warm-neutral palette is a common
editorial style, not a trademark).

### 2.1 Colour palette

| Token name                | Hex                  | Role on Anthropic              | NetPulse mapping                  |
|---------------------------|----------------------|--------------------------------|-----------------------------------|
| `--np-ivory-light`        | `#faf9f5`            | Page background                | Page background                   |
| `--np-ivory-medium`       | `#f0eee6`            | Section secondary bg           | Card hover bg / banded section bg |
| `--np-ivory-dark`         | `#e8e6dc`            | Hover on secondary             | Stronger card hover               |
| `--np-slate-dark`         | `#141413`            | Body text + dark surfaces      | Body text + dark feature bg       |
| `--np-slate-medium`       | `#3d3d3a`            | Button hover                   | Button hover                      |
| `--np-slate-light`        | `#5e5d59`            | Link hover / muted text        | Muted text                        |
| `--np-cloud-medium`       | `#b0aea5`            | Disabled / faded label         | Disabled label                    |
| `--np-cloud-light`        | `#d1cfc5`            | Hairline borders               | Hairline borders                  |
| `--np-clay`               | `#d97757`            | Brand accent (warm coral)      | **REPLACE** with NetPulse accent  |
| `--np-accent`             | `#c6613f`            | Brand accent darker            | **REPLACE** with NetPulse accent  |
| `--np-olive`              | `#788c5d`            | Secondary accent               | Reuse for `success`/health        |
| `--np-cactus`             | `#bcd1ca`            | Tag pastel                     | Reuse for `info` chip             |
| `--np-sky`                | `#6a9bcc`            | Tag pastel                     | Reuse for `info-2` chip           |
| `--np-fig`                | `#c46686`            | Tag pastel                     | Reuse for `warn`/`major` chip     |
| `--np-coral`              | `#ebcece`            | Tag pastel                     | Reuse for `minor` chip            |
| `--np-manilla`            | `#ebdbbc`            | Tag pastel                     | Reuse for `pending` chip          |

> **Brand accent decision.** Anthropic's `--swatch--clay` (`#d97757`)
> is a warm orange that ties to their visual identity. NetPulse already
> uses `--np-pandan` (existing house accent) — keep `--np-pandan` as the
> brand accent and adopt only the neutral ivory/slate scaffold from the
> Anthropic palette.

### 2.2 Typography

#### Font families

| Role               | Anthropic uses             | License | NetPulse substitute (free)             |
|--------------------|----------------------------|---------|-----------------------------------------|
| Display sans       | "Anthropic Sans"           | Custom / proprietary | **Inter** (700) or **Geist Sans** (700) |
| Body / sub-display serif | "Anthropic Serif"    | Custom / proprietary | **Source Serif 4** or **Newsreader**    |
| Detail / mono      | "Anthropic Sans" (smaller) | Custom               | Inter (400/500)                         |

Both Anthropic faces are commissioned proprietary typefaces and **must
not be downloaded or self-hosted by NetPulse**. The substitutes above
preserve the contrast (geometric-grotesque sans + warm-transitional
serif) and are SIL OFL / open-source.

```html
<!-- In netpulse-ui/templates/base.html <head> -->
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,400;8..60,500;8..60,600&display=swap" rel="stylesheet">
```

#### Type scale (reuse exactly as-is)

| Token                          | Value (clamped) | NetPulse usage                    |
|--------------------------------|-----------------|------------------------------------|
| `--np-fs-display-xxxl` (hero)  | `clamp(3.5rem, 2.73rem + 3.27vw, 6rem)` (mobile 56px → desktop ~96px) | Landing hero `<h1>` |
| `--np-fs-display-xxl`          | `clamp(2.75rem, 2.21rem + 2.29vw, 4.5rem)` | Section `<h2>` (e.g. on dark feature card) |
| `--np-fs-display-xl`           | `clamp(2.5rem, 2.04rem + 1.96vw, 4rem)`    | Mid-section `<h2>` |
| `--np-fs-display-l`            | `clamp(2.25rem, 2.02rem + 0.98vw, 3rem)`   | Sub-section `<h3>` |
| `--np-fs-display-m`            | `clamp(1.75rem, 1.67rem + 0.33vw, 2rem)`   | Card title `<h3>` |
| `--np-fs-paragraph-l`          | `1.5rem` (24px)  | Hero supporting copy               |
| `--np-fs-paragraph-m`          | `1.25rem` (20px) | Body                               |
| `--np-fs-paragraph-s`          | `1.125rem` (18px)| Small body / list                  |
| `--np-fs-paragraph-xs`         | `1rem` (16px)    | Detail copy / nav links            |
| `--np-fs-detail-m`             | `1rem` (16px)    | UI labels, button text             |
| `--np-fs-detail-s`             | `0.875rem` (14px)| Card metadata ("DATE", "CATEGORY") |
| `--np-fs-detail-xs`            | `0.75rem` (12px) | Footnotes                          |

Hero headline observed at desktop 1440: **`60.87px / 66.95px line-height,
weight 700`**. At mobile 390: **`40.29px / 44.32px line-height`**.
The `clamp(...)` formula reproduces this curve fluidly.

**Body line-height:** body paragraphs use ~1.4 (`28px` on `20px` body
copy, `33.6px` on `24px` hero supporting copy).

**Letter-spacing:** display text uses `-0.005em` for tightening at
size; body text uses `0`.

### 2.3 Spacing scale

A `1`–`12` token scale, all derived from a `--size--Nrem` base. Most are
fluid via `clamp()` so they shrink on mobile.

| Token  | Desktop value | Use                                |
|--------|---------------|-------------------------------------|
| `--np-space-1` | 0.25rem  | Inline gaps, tight icon spacing |
| `--np-space-2` | 0.5rem   | Chip padding, icon-to-text     |
| `--np-space-3` | 0.75rem  | Compact button padding          |
| `--np-space-4` | 1rem     | Default block gap (text)        |
| `--np-space-5` | 1.5rem   | Card inner padding              |
| `--np-space-6` | 2rem (clamps to 1.75rem mobile) | Section gutter      |
| `--np-space-7` | 2.5rem   | Card-to-card gap                |
| `--np-space-8` | 3rem (clamps to 2.25rem)        | Section vertical pad|
| `--np-space-9` | 4rem (clamps to 2.5rem)         | Section divider gap |
| `--np-space-10`| 5rem (clamps to 3rem)           | Hero top pad        |
| `--np-space-11`| 6rem (clamps to 3.5rem)         | Hero-to-section pad |
| `--np-space-12`| 10rem (clamps to 5.5rem)        | Page-bottom rest    |

**Page side gutter:** observed `64px` on desktop, named `--site--margin`.
NetPulse should use `clamp(1.5rem, 4vw, 4rem)` so it scales smoothly.

### 2.4 Radius

| Token | Value   | Use                       |
|-------|---------|----------------------------|
| `--np-radius-small` | `0.25rem` | Pills, tag chips |
| `--np-radius-main`  | `0.5rem`  | Buttons, inline cards |
| `--np-radius-large` | `1rem`    | Feature card on dark canvas (the "Project Glasswing" container) |
| `--np-radius-round` | `100vw`   | Pill buttons (the white CTA inside the dark feature card) |

### 2.5 Layout

- **Max content width**: `1440px` (`--site--width`). Above that, content
  centres with auto margin.
- **Inner small container**: `56.25rem` (~900px) for hero headline +
  long-form text columns.
- **Side gutter**: 64px desktop, ~24px mobile.
- **Grid columns**: hero is a 2-column ratio ~`5fr 3fr` (headline left,
  supporting right). The "Latest releases" row is a 3-column equal grid
  (`grid-template-columns: repeat(3, 1fr); gap: var(--np-space-7);`).
- **Footer columns**: 5-column grid (`logo | products | solutions |
  resources | company`) collapsing to single-column on mobile.

### 2.6 Breakpoints

The site relies on **fluid typography + spacing** (`clamp()`) rather
than discrete breakpoints, but the layout itself flips at:

| Width  | Behaviour                                               |
|--------|---------------------------------------------------------|
| ≥1024  | Full desktop: 5-col footer, 3-col "Latest releases", 2-col hero |
| 768–1023 | 3-col footer, 3-col release cards, 1-col hero  |
| <768   | All single-column, hamburger nav (the desktop `nav_component is-desktop` class is hidden, replaced by a mobile drawer) |

---

## 3. Component anatomy

### 3.1 Header / nav (`height: 68px`, transparent background)

```
┌────────────────────────────────────────────────────────────────────────┐
│  [LOGO/WORDMARK]            Research  Economic Futures  Commitments ▾  │
│                              Learn ▾  News                  [Try Claude ▾] │
└────────────────────────────────────────────────────────────────────────┘
```

- Background: transparent (page background bleeds through).
- Logo left, nav links centre-right, CTA button far-right.
- Nav links: 16px sans, weight 400, slate-dark colour, no underline.
  Submenus indicated by ▾ chevron, opening on hover (desktop) / tap (mobile).
- Primary CTA button: split-button — main label `Try Claude` (slate-dark
  bg, ivory text, 8px radius) + dropdown chevron rail (same colour, 0
  radius on the inner edge). On Anthropic this links to Claude product
  variants; on NetPulse it should be a single solid button (no dropdown)
  reading `Open Workspace` and routing to `/app`.

### 3.2 Hero section

```
┌──────────────────────────────────────────────────────────────────────┐
│                                                                      │
│  [BIG HEADLINE]                              [Supporting paragraph]  │
│  3-line bold sans (96/72/56px),              3 short serif sentences │
│  with 1-2 underlined keywords as             at paragraph-l (24px),  │
│  inline link affordances.                    no underlines.          │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

- Block height: ~390px on desktop (no padding-top on the hero element
  itself; the rest comes from the previous header gap).
- Headline split into ~5–8 words across 3 lines. **Inline underlined
  words act as actual links** (e.g. one underlined noun + one underlined
  verb-noun phrase) — a subtle, editorial CTA pattern.
- Right column contains 3–4 line supporting paragraph in serif. No CTA
  button in the hero — the CTA lives in the header.

### 3.3 Feature card (dark canvas)

```
┌──────────────────────────────────────────────────────────────────┐
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │ ← bg #141413, radius 1rem
│ ░                                                                ░ │
│ ░  [BIG SERIF TITLE]               ┌────────────────────────┐    ░ │
│ ░  Sub-title in small serif        │                        │    ░ │
│ ░  centred under title             │     [VISUAL ARTWORK]   │    ░ │
│ ░                                  │       (50% width)      │    ░ │
│ ░  ⬤ White pill button            │                        │    ░ │
│ ░                                  └────────────────────────┘    ░ │
│ ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░ │
└──────────────────────────────────────────────────────────────────┘
```

- Container: `border-radius: 1rem`, background `--np-slate-dark`, full
  page-content width with side-gutter inset.
- Title typography: serif display, `display-xxl` (~64-72px).
- Pill CTA: white bg, slate-dark text, ~24px radius (`--np-radius-round`),
  16px sans label.
- Right-side visual: 50% width, decorative — Anthropic uses bespoke
  artwork ("Project Glasswing"). NetPulse should use a **generated SVG
  diagram** of the agent topology (see §6 for the substitute).

### 3.4 "Latest releases" row (3 cards, same width)

```
┌──────────┐  ┌──────────┐  ┌──────────┐
│ Title    │  │ Title    │  │ Title    │  bg = ivory-medium #f0eee6
│          │  │          │  │          │  radius = 0.5rem
│ Lede 2-3 │  │ Lede 2-3 │  │ Lede 2-3 │  padding = 1.5rem (--np-space-5)
│ lines    │  │ lines    │  │ lines    │
│          │  │          │  │          │
│ ─ DATE   │  │ ─ DATE   │  │ ─ DATE   │  hairline border above metadata
│ ─ CATGRY │  │ ─ CATGRY │  │ ─ CATGRY │  detail-s 14px, label slate-light
│          │  │          │  │          │
│ [Btn →]  │  │ [Btn →]  │  │ [Btn →]  │  slate-dark pill button
└──────────┘  └──────────┘  └──────────┘
```

- Section title `Latest releases` left-aligned, detail-m (16px), weight 500.
- Cards: 3 equal columns with `gap: 2.5rem`, single row.
- Inside each card:
  - Title (display-m, 28-32px, serif)
  - Lede paragraph (paragraph-s, 18px, serif, 3-line clamp)
  - Hairline divider, then 2 label/value rows (`DATE` + `CATEGORY`)
    rendered as `<dl>` with label in detail-s upper-case grey + value
    right-aligned
  - Single primary button at the bottom-left (`Read announcement →`)

### 3.5 Footnote / link rail

```
At Anthropic, we build              Core views on AI safety       — Announcements
AI to serve humanity's              Anthropic's Responsible…      — Alignment Science
long-term well-being.               Anthropic Academy: …          — Education
                                    Anthropic's Economic Index    — Economic Research
                                    Claude's Constitution         — Announcements
```

- 2-column block: left is a 2–3 line mission statement at paragraph-m
  (20px) serif, weight 500. Right is a stacked list of 5 links, each
  formatted `[Link title] ──────── [Category right-aligned]` with a
  hairline border between rows.

### 3.6 Footer (dark)

```
┌──────────────────────────────────────────────────────────────────────────┐
│ [⬛ logo]  Products    Solutions    Resources    Company                 │
│           Claude       Agents       Blog         About                   │
│           Claude Code  Coding       Community    Careers                 │
│           ...          ...          ...          ...                     │
│                                                                          │
│           Models       Help & Security                                   │
│           Opus         Availability                                      │
│           Sonnet       Status                                            │
│           Haiku        Support center                                    │
│                                                                          │
│ © 2026 Anthropic PBC                          [li] [x] [yt]              │
└──────────────────────────────────────────────────────────────────────────┘
```

- Background: `--np-slate-dark` (#141413), text `--np-ivory-light`.
- 5 columns (logo + 4 link sections) on desktop, 1 column stacked on mobile.
- Section labels (`Products`, `Solutions`...) in detail-m (16px), weight 600.
- Link labels in detail-s (14px), weight 400, `rgb(176, 174, 165)` muted.
- Bottom strip: copyright left, social icons right, separated by 1px
  hairline `#1414131a → ivory-faded-10` on dark.

---

## 4. Motion & micro-interactions (observed)

- Submenu chevron expands on hover with no perceptible easing override
  (default browser ~150ms).
- CTA button hover swaps `--np-slate-dark` → `--np-slate-medium`
  (background) — a very subtle lift.
- Feature card pill button hover: white → translucent ivory; preserves
  text colour.
- No parallax, no scroll-jacking. The page scrolls natively.

---

## 5. Accessibility notes from the snapshot

- Text on ivory background (`#141413` on `#faf9f5`) — contrast ratio ~17:1, AAA.
- Slate-light muted text (`#5e5d59` on `#faf9f5`) — ~7.4:1, AA Large+.
- Cloud-medium disabled (`#b0aea5` on `#faf9f5`) — ~2.4:1, **fails AA** —
  use only for non-essential, non-text decoration.
- Inline links in the headline use underline-only (no colour
  differentiation) — relies on consistent treatment across the page.
- All nav links and buttons are real `<a>` / `<button>` elements with
  hit-targets ≥44px.

---

## 6. Proprietary elements & NetPulse substitutions

This is the section that matters most: a 1-to-1 mapping of every element
that is Anthropic-specific, with an original NetPulse replacement. Do
not reuse these assets verbatim.

| # | Anthropic element                              | Why proprietary                          | NetPulse substitution                                                                   |
|---|------------------------------------------------|------------------------------------------|------------------------------------------------------------------------------------------|
| 1 | `ANTHROP\C` wordmark logo                      | Trademarked brand mark                   | `NetPulse AI` wordmark in Inter 700, slate-dark, all-caps, letter-spacing `0.05em`. The existing pulse-rings SVG glyph in `static/img/np-glyph.svg` (or generate one) sits left of the wordmark at 24×24px. |
| 2 | "Anthropic Sans" custom typeface               | Commissioned, not licensable             | **Inter** (Google Fonts, SIL OFL). Weights 400/500/600/700.                              |
| 3 | "Anthropic Serif" custom typeface              | Commissioned, not licensable             | **Source Serif 4** (Google Fonts, SIL OFL). Weights 400/500/600.                         |
| 4 | Hero headline copy ("AI research and products that put safety at the frontier") | Brand voice + positioning | Original NetPulse headline: **"Telecom incidents that ticket themselves"**, with `incidents` and `themselves` as the underlined inline link words (linking to `/app?seed=…&autorun=1` demo runs). |
| 5 | Hero supporting paragraph (3 sentences about Anthropic's PBC mission) | Brand voice | Original NetPulse paragraph: **"NetPulse AI watches Indonesian telecom networks and turns customer complaints into structured incident tickets in under 15 seconds. Built on Google ADK, AlloyDB AI, and Vertex Gemini for the APAC GenAI Academy 2026."** |
| 6 | "Project Glasswing" feature card title + sub + artwork | Branded campaign + commissioned visual | Replace with **"NetPulse Live Demo"** title, sub `Pick a complaint, watch four agents handle it`, and a custom SVG of the agent topology (classifier → network_investigator → cdr_analyzer → response_formatter). The SVG can render the same hexagonal-mesh aesthetic using NetPulse's existing house palette (`#0f3460` `#16213e` `#533483` from `~/projects/_shared/mermaid.md`). Pill CTA reads `Run a demo →` and links to `/app`. |
| 7 | "Latest releases" 3 cards with model names (`Claude Opus 4.7`, `Claude is a space to think`, `Claude on Mars`) | Product launches | Replace with NetPulse's 3 launch chips: **(1) "Phase 12 — Vertex model-ladder failover"** dated 2026-04-27, category `Engineering`; **(2) "Phase 11 — AlloyDB AI NL2SQL"** dated 2026-04-26, category `Architecture`; **(3) "Top 100 — APAC GenAI Academy"** dated 2026-04-23, category `Milestone`. Each card's CTA links to the matching commit / PR / submission deck. |
| 8 | "At Anthropic, we build AI to serve humanity's long-term well-being" mission rail | Brand voice | Replace with NetPulse mission: **"NetPulse AI is built to give Indonesian network operators a single pane of glass — from raw customer complaint to actionable NOC ticket — in seconds, not hours."** |
| 9 | 5 footnote links (`Core views on AI safety`, `Responsible Scaling Policy`, etc.) | Editorial linking | Replace with 5 NetPulse cross-links: `Architecture overview` → `README.md#architecture`; `Refinement audit` → `REFINEMENT-AUDIT.md`; `AlloyDB AI setup` → `docs/SCHEMA.md`; `Sample data` → `/data/network` viewer tab; `GitHub repo` → external link. Right-column categories: `Documentation`, `Documentation`, `Architecture`, `Live Data`, `Source`. |
| 10 | Footer 5-column link tree (Products / Solutions / Resources / Company + Models / Claude Platform / Help & Security) | Catalogue of Anthropic offerings | Collapse to a 3-column NetPulse footer: **(A) NetPulse**: Workspace, Network Events, Call Records, Incident Tickets. **(B) Build**: Architecture, Refinement Audit, Refinement Phases, AlloyDB Schema. **(C) Project**: GitHub repo, Submission deck, Author (link to LinkedIn), APAC GenAI Academy. |
| 11 | Footer copyright line (`© 2026 Anthropic PBC`) + social icons (LinkedIn, X, YouTube) | Org-specific | Replace with `© 2026 Adityo Nugroho · Built for the APAC GenAI Academy 2026 with Claude Code` and a single GitHub-icon link to the repo. |
| 12 | "Try Claude" split-button CTA (with dropdown for Claude variants) | Product router | Replace with single-action `Open Workspace →` button (slate-dark bg, ivory text, 8px radius, no dropdown rail) routing to `/app`. |
| 13 | Submenu structure on `Commitments ▾` and `Learn ▾` | Multi-product nav | Flatten to 4 single-link nav items: `Architecture`, `Live Data`, `Refinement`, `GitHub`. No submenus needed for a single-app demo site. |
| 14 | Coral-accent (`#d97757`, `#c6613f`) treated as brand colour | Anthropic brand identity | Keep these only as part of the *neutral palette*, but never use them as the primary CTA / link colour. Brand accent stays `--np-pandan` (existing house token). |

---

## 7. Implementation playbook (NetPulse-specific)

The current `netpulse-ui/templates/landing.html` already exists. Treat
this redesign as a **rewrite of `landing.html` and a stylesheet pass on
`static/style.css`**, leaving routes and the workspace (`/app`) untouched.

### Order of operations

1. **Add fonts to `base.html`.** Inter + Source Serif 4 from Google Fonts
   preconnect block (snippet in §2.2).
2. **Extend `static/style.css`** with the token block at the top of the
   file (a `:root { --np-… }` declaration with all tokens from §2.1–§2.5).
   Reuse the existing `--np-pandan` and `--np-status-*` tokens already in
   the stylesheet.
3. **Rewrite `landing.html`** following the section order:
   1. Header (already exists in `base.html` — only the CTA button text
      changes from whatever it is today to `Open Workspace →`).
   2. Hero (§3.2) — 2-column with bold sans headline + serif supporting copy.
   3. Feature card (§3.3) on dark canvas — drop in the agent-topology SVG.
   4. Latest releases row (§3.4) — 3 cards using the substitution copy from §6 #7.
   5. Mission rail (§3.5) using NetPulse mission copy from §6 #8.
   6. Footer (§3.6) collapsed to 3 columns from §6 #10.
4. **Generate the agent-topology SVG.** Hand-roll a static SVG (no JS)
   showing the four ADK agents in a left-to-right pipeline with
   hexagonal-mesh background. Place at `static/img/agent-topology.svg`.
   Use only the existing house palette (`#0f3460` `#16213e` `#533483`).
5. **Generate the NetPulse logo glyph.** A 24×24 SVG of concentric pulse
   rings (matching the existing favicon if present). Place at
   `static/img/np-glyph.svg`.
6. **Add 3 new image-free release-card cover slots.** Cards in §3.4 are
   text-only — no cover images. This avoids needing 3 new pieces of
   commissioned art.
7. **Verify mobile** at 390×844 — single-column, hero stacks, feature
   card visual stacks below title, 3 release cards stack to 1 column,
   footer collapses.
8. **Lighthouse pass.** Aim for ≥95 perf / 100 a11y on the new landing.

### Files to touch

| File | Change |
|------|--------|
| `netpulse-ui/templates/base.html` | Add Google Fonts `<link>` block in `<head>`; update header CTA text. |
| `netpulse-ui/templates/landing.html` | Full rewrite of body sections following §3 anatomy. |
| `netpulse-ui/static/style.css` | Add token block (§2.1–§2.5) at top; add new component classes (`np-hero`, `np-feature-card`, `np-release-card`, `np-mission-rail`, `np-footer-grid`). |
| `netpulse-ui/static/img/np-glyph.svg` | NEW — 24×24 pulse-ring logo glyph. |
| `netpulse-ui/static/img/agent-topology.svg` | NEW — feature-card visual (4-agent pipeline on hex-mesh bg). |

### What stays unchanged

- `/app` workspace template (`chat.html`)
- All viewer tabs (`network_events.html`, `call_records.html`, `tickets.html`)
- Flask routes, SSE plumbing, agent_runner.py
- All `telecom_ops/` Python code
- All `.playwright-mcp/` extraction artifacts (kept for reference)

---

## 8. Risk / decision log

1. **Inter vs Geist Sans.** Inter is the safer choice — wider weight
   coverage, more familiar to users, same SIL OFL licence. Geist would
   match Vercel-era aesthetics more closely but adds a less common
   typeface. **Decision: Inter.**
2. **Source Serif 4 vs Newsreader.** Source Serif 4 has variable-font
   support and a transitional / Caslon-derived feel close to Anthropic's
   serif. Newsreader is more contemporary / Pelago-inspired. **Decision:
   Source Serif 4.**
3. **Keeping warm-coral accents (`--np-clay`, `--np-accent`).** Reusing
   the hex values is fine (warm orange isn't a trademark), but treating
   them as the primary brand colour would be misleading. **Decision:
   include in palette as `--np-clay` for use in tag chips only; primary
   accent stays `--np-pandan`.**
4. **Replacing the feature-card artwork.** The hexagonal-mesh aesthetic
   is generic enough to recreate without copying ("Project Glasswing"'s
   specific artwork is bespoke, but a hex-mesh rendered behind any
   diagram is a common visual idiom). **Decision: original SVG, hex-mesh
   background, agent pipeline foreground, house palette.**
5. **Inline-underlined headline links.** This is the most distinctive
   single design choice on the Anthropic page. Worth adopting because it
   eliminates the need for a separate hero CTA button and gives the page
   its editorial voice. **Decision: keep the pattern; underline two
   words in the NetPulse hero headline as inline links to demo seeds.**
6. **Split-button CTA in header.** Anthropic's `Try Claude ▾` lets users
   route to multiple Claude surfaces. NetPulse has only one workspace,
   so the split is unnecessary chrome. **Decision: single-action button.**

---

## 9. Verification checklist

After the rewrite, confirm all of these before merging:

- [ ] No file references `Anthropic Sans` or `Anthropic Serif` as a font family.
- [ ] No Anthropic logo or wordmark in any image, SVG, or text.
- [ ] No copy from §6 column 2 ("Anthropic element") appears verbatim in any template.
- [ ] All NetPulse substitution copy (§6 column 4) is used as written.
- [ ] Lighthouse a11y ≥95 on the new landing.
- [ ] Mobile (390px) renders all sections single-column with no overflow.
- [ ] Hero headline `<h1>` size scales smoothly via `clamp()` from 56px → 96px.
- [ ] Header `Open Workspace →` button routes to `/app`.
- [ ] Feature card pill CTA `Run a demo →` routes to `/app` (or to `/app?seed=…&autorun=1` if a default seed is chosen).
- [ ] All 5 mission-rail links resolve (3 internal MD anchors + 1 viewer tab + 1 GitHub link).

---

## 10. Source artifacts

Kept in `.playwright-mcp/` (gitignored by default — add to git only if
needed for traceability):

- `anthropic-snapshot.md` — full DOM accessibility snapshot
- `anthropic-hero.png` — desktop viewport (1440×900) capture
- `anthropic-full.png` — full desktop scroll capture
- `anthropic-mobile.png` — full mobile scroll (390×844) capture

Extraction performed via Playwright MCP `browser_navigate` +
`browser_snapshot` + `browser_take_screenshot` + `browser_evaluate`
against live computed styles. All numeric tokens above are the actual
values returned by `getComputedStyle()` — not eyeballed from
screenshots.
