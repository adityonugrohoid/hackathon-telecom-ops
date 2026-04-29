# Chat SSE → DOM Mapping — Lite (Wrapper-only port)

> **Purpose.** Self-contained Step 4 brief. Wrapper-only port: existing
> `chat.html` JS keeps populating its own selectors as today; the rebuild's
> outer chrome wraps around it. Two CSS namespaces coexist (`.np-*` inside,
> `.app-*` outside). Aim for the mockup's overall feel, not pixel parity
> inside the cards.
>
> **Full reference:** `CHAT-SSE-MAPPING.md` (~520 lines, full reskin path) —
> consult only if a specific event or state question comes up; otherwise
> ignore.
>
> **Scope rule (load-bearing).** *Do not rewrite `npHandle()`, `npExtractRows()`,
> `npComputeImpact()`, `npRenderRegionAttempt()`, or `npRenderAgentError()`.*
> The five top-3 + secondary risks identified in the full doc are bypassed
> entirely by this approach.

---

## What ports from `static-mockup-rebuild/app.html`

| # | Concern | Approach |
|---|---|---|
| 1 | Page style — paper `#F4F0E6`, ink `#141413`, accent coral `#CC785C`, Fraunces / Inter / JetBrains Mono fonts | `static/site.css` (already shipped in Phase A) provides this. **Make `chat.html` standalone** — drop `{% extends "base.html" %}`, match the shape of `network_events.html` / `tickets.html` / `landing.html` / `docs.html` / `call_records.html`. Load `site.css` directly in `<head>`. |
| 2 | Header status bar (`BigQuery · AlloyDB · MCP toolbox · {{ active_model }}`) + footer stripe | Direct copy from `app.html` lines 18–44 (header) + 302–315 (footer). Use `{% include "_brand.html" %}` for the brand link (already shipped in Phase A). **Model name is dynamic** — `app.py` context processor exposes `active_model` (mirrors `telecom_ops/agent.py:MODEL_FAST`); the 3 data viewer templates already use `{{ active_model }}`. Match the pattern in chat.html. |
| 3 | Prompt box — `What did the customer report?` greeting + textarea + sample chips | Copy `app.html` lines 49–71 markup. Wire JS: `.app-prompt-input` (textarea) replaces `#np-input`; `.app-prompt-submit` replaces `#np-submit`; `.app-chip` replaces `.np-chip`. |
| 4 | Agent card outer/inner shell — timeline rail + numbered dot + `.app-step-card` + status pill + traffic-light terminal-bar | Wrap each existing `.np-timeline-entry` content in the `.app-step` shell. Inside `.app-step-terminal-body`, keep the existing `<ul class="np-tools">` + `<pre class="np-text">` rendering as-is. Small CSS converges fonts. |
| 5 | Customer impact + ticket form **wrappers** | `<aside class="app-impact-card">` outside, existing `.np-impact-*` content inside. `<article class="app-ticket-form">` (dark/ink) outside, existing `<pre class="np-final-text">` inside (just colour-inverted via CSS). |

## What does NOT port (deliberately)

- `.app-step-terminal-prose` / `-cmd` / `-out` three-tier inner styling — the existing `<ul class="np-tools">` + `<pre class="np-text">` pair stays.
- `.app-ticket-form-rows` `<dl>` six-row layout — keep existing `<pre class="np-final-text">{final_report}</pre>`. The Response Formatter prompt already emits a clean `Ticket ID : N / Classification : X / …` text block; styled `<pre>` reads as "code-block ticket".
- Compiling-state skeleton-shimmer + spinner + Compiling pill — ticket form simply hidden until `complete`, then rendered with a static "Saved · AlloyDB" pill.
- `.app-impact-substats` flat-sentence layout — existing impact card structure (big number + severity badges + events count + since-onset) is retained inside the new aside wrapper.
- `is-error` state class on `.app-step` — the existing `.np-timeline-entry.error` styling cascades through the wrapper. No new state class needed.
- Region-attempt chip relocation — keep where it lives (inline with status pill in `.np-timeline-entry` header). No move into the terminal-bar `.meta` span.
- CDR-side impact merge — no dropped-calls substat; the mockup's "vs 60 baseline" sub-line is dropped entirely.

## What stays untouched in JS (the load-bearing core)

`netpulse-ui/templates/chat.html` `<script>` block lines 149–687, intact:

- `npHandle()` 7-event-type dispatch.
- `npExtractRows()` recursive Array | string parser (load-bearing per CLAUDE.md).
- `npComputeImpact()` / `npRenderImpact()`.
- `npRenderRegionAttempt()` chip retry-collapse + settled flag (lines 547–598).
- `npRenderAgentError()` / `npRenderGlobalError()`.
- `npRenderTicketBadges()` / `npRenderActions()` / `CATEGORY_ACTIONS` catalog.
- `npComputeImpact()` and the `npAppendToolLine()` helpers.

## JS changes — selector-rewire only

Five touchpoints in the existing `<script>` block:

| Current | New |
|---|---|
| `document.getElementById('np-input')` | `document.querySelector('.app-prompt-input')` |
| `document.getElementById('np-submit')` | `document.querySelector('.app-prompt-submit')` |
| `document.getElementById('np-input-hint')` | `document.querySelector('.app-prompt-hint')` *(new slot — see care item)* |
| `document.getElementById('np-form')` (form submit handler) | Remove form wrapper; bind directly to `.app-prompt-submit` click + Cmd/Ctrl+Enter on textarea |
| `'.np-chip'` (in `npFill` callsites if any) | `'.app-chip'` |

`npFill()` itself is selector-agnostic — it reads `btn.textContent` and writes to whatever element variable holds it. Just point it at the textarea.

## CSS convergence (append to `static/site.css`)

```css
/* Agent card inner content uses Mono fonts inside the new wrapper */
.app-step-card .np-tools li {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
}
.app-step-card .np-text {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12.5px;
}

/* Hide the old in-header step number — the new rail-side dot replaces it */
.app-step .np-timeline-step,
.app-step .np-timeline-time,
.app-step .np-timeline-rail { display: none; }

/* Dark ticket form: invert final-report colours, wrap long lines */
.app-ticket-form .np-final-text {
  color: var(--paper);
  background: transparent;
  white-space: pre-wrap;
  word-break: break-word;
  max-width: 100%;
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  line-height: 1.5;
  margin: 0;
  padding: 0;
}

/* Hide ticket form until populated (no shimmer/compiling state) */
.app-ticket-form[hidden] { display: none; }
```

The existing `.np-timeline-entry.running` / `.done` / `.error` rules continue to drive card state visuals; the new `.app-step-card` wrapper is decoration.

## Markup shape — outer shell wrapping inner content

For each agent card:

```html
<li class="app-step" data-agent="classifier">
  <span class="app-step-dot">1</span>
  <div class="app-step-card">
    <div class="app-step-head">
      <div class="app-step-label">
        <span class="app-step-num">01</span>
        <span class="app-step-name">Classifier</span>
      </div>
      <span class="np-status app-step-status">waiting</span>
      <span class="np-region-trace app-step-region-trace" hidden></span>
    </div>
    <div class="app-step-source">
      <!-- existing .np-source-tag pills, copy verbatim per agent -->
    </div>
    <div class="app-step-terminal">
      <div class="app-step-terminal-bar">
        <span class="app-step-terminal-dots" aria-hidden="true">
          <i></i><i></i><i></i>
        </span>
        <span class="label">classifier</span>
        <span class="meta">{{ active_model }}</span>
      </div>
      <div class="app-step-terminal-body">
        <ul class="np-tools"></ul>     <!-- SSE-populated as today -->
        <pre class="np-text"></pre>    <!-- SSE-populated as today -->
      </div>
    </div>
    <footer class="app-step-handoff">
      <span class="app-step-handoff-label">passes to next</span>
      <code>category</code><code>region</code>
    </footer>
  </div>
</li>
```

The **status pill** and **region-trace chip** carry BOTH old and new class names so the existing JS finds them by `.np-status` / `.np-region-trace` while CSS targets `.app-step-status` / `.app-step-region-trace` for the new visual styling.

For the impact card and ticket form, identical pattern — outer rebuild wrapper, inside it the existing `.np-impact-*` / `.np-final-*` markup with all the existing JS-targeted classes preserved.

## Small care items

1. **Textarea + Enter behavior.** Old `<input type="text">` submitted on Enter; new `<textarea>` inserts newline. Bind `keydown`: Cmd/Ctrl+Enter → submit, plain Enter → newline. Match ChatGPT/Claude conventions.
2. **Long `final_report` overflow.** Covered by `white-space: pre-wrap` + `word-break: break-word` in the CSS block above.
3. **Hide the old in-header rail.** Existing `.np-timeline-rail` (with `.np-timeline-time` and `.np-timeline-step`) duplicates the new `.app-step-dot`. CSS hides them inside `.app-step` (covered above).
4. **Empty-input hint.** Insert one `<div class="app-prompt-hint" role="alert" aria-live="polite" hidden></div>` between `.app-prompt` and `.app-chips`. Wire existing `npFlashInputHint()` / `npClearInputHint()` to it. Or drop the feature; minor.
5. **`?seed=...&autorun=1` deep-link.** Critical — landing-page chips depend on it. `npOnLoad()` keeps working as long as it targets `.app-prompt-input`.
6. **`.nav-cta` "New run" button (optional).** Mockup header has it. Wire to `npReset()` + textarea focus, or replace with a back-to-landing link (`<a href="/">`) and skip JS.

## Implementation order

Each step is independently testable; build stays green at every commit.

1. **Markup port.** Rewrite `chat.html`: drop `{% extends "base.html" %}`, become standalone like the other 5 templates. Wire in `_brand.html`. Header + greeting + prompt + 4 agent shells + impact wrapper + ticket form wrapper + footer. Keep the existing `<script>` block unchanged. *Smoke test:* page loads, visual layout matches mockup at rest. JS console errors on submit are expected at this point.
2. **JS selector rewire.** Update the 5 selectors from the table. Rebind submit (button click + Cmd/Ctrl+Enter on textarea, no form). *Smoke test:* type in textarea, click submit, see SSE flow in. Cards render functionally inside the new wrappers.
3. **CSS convergence.** Append the small block above to `static/site.css`. *Smoke test:* card content reads as JetBrains Mono; ticket form `<pre>` is light-on-dark and wraps long lines.
4. **Care-item polish.** Textarea Enter binding, hint slot, hide old rail elements, deep-link rewire. *Smoke test:* end-to-end one canonical query (`Major dropped calls in Surabaya`) runs cleanly with all visual states intact.
5. **Deploy.** Same gcloud command as Phase B (`--source` from project root, `us-central1`, `--no-cpu-throttling --cpu-boost`). User triggers manually. No backend changes; only template + CSS.

## Files touched

- `netpulse-ui/templates/chat.html` — full markup rewrite of body; `<script>` block selector-rewires only (load-bearing core untouched).
- `netpulse-ui/static/site.css` — append small convergence block at end of file.

## Files NOT touched

- `netpulse-ui/templates/base.html` — becomes orphan after chat.html goes standalone. Leave for follow-up cleanup; do not delete in this PR.
- `netpulse-ui/static/style.css` / `tokens.css` / `netpulse-logo*.png` — also become orphans; same cleanup deferral.
- `netpulse-ui/agent_runner.py` — backend SSE producer; contract unchanged.
- `netpulse-ui/data_queries.py` — unrelated.
- `netpulse-ui/app.py` — `/app` route serves the same template; no route change.
- `telecom_ops/` — entire ADK package untouched.
- The five templates already shipped in Phase A (`landing.html` / `docs.html` / `network_events.html` / `call_records.html` / `tickets.html`) — untouched.

## When this approach breaks down

- If a future redesign reshapes the agent cards or ticket form structurally (different sub-elements, different state machine), the two-namespace coexistence creates technical debt to clean up.
- If you later want the inner `$ tool_call(...)` Mono-styled tier rendering, you'll need to either rewrite `npAppendToolLine()` or add a parallel renderer. The wrapper port doesn't preclude this — it just defers it.

For both cases, the original `CHAT-SSE-MAPPING.md` (full version) is the deep reference for the inner-content rewrite.

## Tradeoff named explicitly

You sacrifice a visual seam between the warm editorial wrapper and the existing functional inner rendering. Specifically:

- **Inside agent cards:** no `$ tool_call(...)` mono-styled lines with bolded `affected:` totals or coral-rule prose pulls. Tool list renders as the existing `<ul>` of `[BACKEND] → toolname({...})` rows — readable but utilitarian.
- **Inside ticket form:** styled `<pre>` instead of structured `<dl>` rows. Loses per-field row layout the mockup shows.
- **Impact card:** keeps existing shape (count + severity badges) instead of the mockup's flat substat sentence.
- **No shimmer / Compiling pill.** Ticket form hidden until `complete`, then static "Saved · AlloyDB" pill.

The mockup's main visual payoff is at the wrapper level — palette, typography, header status bar, dark ticket pane, timeline rail with numbered dots. Those carry the demo. The inner-card terminal styling is polish that costs ~80% of the implementation budget for ~20% of the visual impact.
