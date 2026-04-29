# Chat SSE → DOM Mapping

> **Purpose.** Single source of truth for the Step 4 workspace port. Maps every SSE
> event the backend can emit to the exact DOM mutation it must drive against the
> locked rebuild markup in `static-mockup-rebuild/app.html`. Reference doc only —
> nothing here is implementation. Read this end-to-end before touching `chat.html`.

> **Scope.** Backend producer (`netpulse-ui/agent_runner.py`) is held constant.
> Frontend consumer (`netpulse-ui/templates/chat.html` and its inline `<script>`)
> is what gets rewritten on top of the new markup. Where the new markup lacks a
> slot, this doc names the gap and proposes the smallest possible additive change.

---

## 1. SSE event inventory

Source: `netpulse-ui/agent_runner.py` `AgentEvent` dataclass + `_drain()` /
`_convert_event()` / `_on_region_attempt()`.

Each event arrives as one `data: <json>\n\n` SSE frame; `npHandle()` JSON-parses
and dispatches by `ev.type`. **Seven types** — listed in the order they appear
during a healthy run:

| # | type            | when emitted                                                                 | dispatch arity |
|---|-----------------|------------------------------------------------------------------------------|----------------|
| 1 | `region_attempt`| once per Vertex AI attempt (zero or more per LLM call, two LLM calls/agent) | 2N–8N+        |
| 2 | `agent_start`   | first time `event.author` is observed in the ADK stream                     | exactly 4     |
| 3 | `tool_call`     | per `event.get_function_calls()` entry                                      | 4–6           |
| 4 | `tool_response` | per `event.get_function_responses()` entry                                  | 4–6           |
| 5 | `text`          | per non-partial event with non-empty `content.parts[].text`                 | 4–8           |
| 6 | `error`         | tool-scoped (with `agent`, `tool`) **or** top-level (no `agent`)            | 0–N           |
| 7 | `complete`      | exactly once, last frame before the SSE stream closes                       | 1             |

### 1.1 Field-by-field shape

`AgentEvent.to_dict()` strips `None`s; only fields actually populated arrive on
the wire. Shape per type:

```jsonc
// region_attempt — per-attempt Vertex telemetry from RegionFailoverGemini
{ "type": "region_attempt", "agent": "classifier",
  "region": "gemini-3.1-flash-lite-preview", // NB: field carries MODEL NAME post-Phase-12
  "outcome": "ok" | "failover",
  "message": "RESOURCE_EXHAUSTED ..." }      // present iff outcome=failover

// agent_start — boundary marker; first time author is seen
{ "type": "agent_start", "agent": "classifier" }

// tool_call — function_call from the LLM
{ "type": "tool_call", "agent": "classifier",
  "tool": "classify_issue",
  "args": { "complaint": "...", "category": "network", "region": "Semarang", "reasoning": "..." } }

// tool_response — function_response back to the LLM
{ "type": "tool_response", "agent": "network_investigator",
  "tool": "query_network_events",
  "result": { /* ADK-wrapped — see §4.2 for the JSON-string-of-rows quirk */ } }

// text — model output text (non-streaming; one chunk per event)
{ "type": "text", "agent": "response_formatter",
  "text": "INCIDENT REPORT\n=======...\nTicket ID : 35\n..." }

// error — agent-scoped (tool failure or ADK-wrapped exception)
{ "type": "error", "agent": "response_formatter",
  "tool": "save_incident_ticket",       // present when error originated in a tool
  "message": "category 'foo' not in VALID_CATEGORIES" }

// error — top-level (catastrophic; no agent)
{ "type": "error", "message": "Agent unavailable: ..." }

// complete — final summary frame
{ "type": "complete",
  "ticket_id": 35,                      // null if save_incident_ticket never ran or errored
  "final_report": "INCIDENT REPORT\n...\nRecommendation : ..." }
```

### 1.2 Authors observed in `event.agent`

Hard-coded by the four `LlmAgent.name` values in `telecom_ops/agent.py`:
`classifier`, `network_investigator`, `cdr_analyzer`, `response_formatter`. The
SequentialAgent root (`telecom_ops`) never authors a UI event because
`agent_runner._drain()` filters on `author and author != "user"`.

### 1.3 Tool universe (drives the source-tag and terminal `.label` rendering)

| tool name                            | agent                  | backend kind              |
|--------------------------------------|------------------------|---------------------------|
| `classify_issue`                     | classifier             | NATIVE PYTHON TOOL        |
| `query_network_events`               | network_investigator   | MCP TOOLBOX (BigQuery)    |
| `query_affected_customers_summary`   | network_investigator   | MCP TOOLBOX (BigQuery)    |
| `weekly_outage_trend`                | network_investigator   | MCP TOOLBOX (BigQuery)    |
| `query_cdr_nl`                       | cdr_analyzer           | MCP TOOLBOX (AlloyDB AI NL2SQL) |
| `save_incident_ticket`               | response_formatter     | NATIVE PYTHON TOOL → ALLOYDB WRITE |

Existing `npToolBackend()` covers cases 1, 2, 6 and treats anything starting
`query_` as MCP TOOLBOX (covers 3–5 in one regex). The NL one (`query_cdr_nl`)
matches the same pattern, so the helper is correct as-is — but the new
markup distinguishes ALLOYDB NL2SQL from generic MCP TOOLBOX visually
(`app.html` line 167 carries `<span class="app-source-tag alloydb">ALLOYDB&nbsp;NL2SQL</span>`).
**Action:** extend `npToolBackend()` to return `{label: 'ALLOYDB NL2SQL', cls:
'alloydb'}` for `tool === 'query_cdr_nl'` specifically.

---

## 2. Target DOM map

Source: `static-mockup-rebuild/app.html` + `static-mockup-rebuild/css/site.css`
(state classes confirmed at lines 2911–3609).

### 2.1 Top-level layout

```
main.wrap
├── div.app-greeting           (h1: "What did the customer report?")
├── section.app-prompt-section
│   ├── div.app-prompt
│   │   ├── textarea.app-prompt-input         ← user types here
│   │   └── div.app-prompt-foot
│   │       └── button.app-prompt-submit.app-prompt-submit-coral  ← Investigate
│   └── div.app-chips                          ← sample-prompt buttons
│       └── button.app-chip × 4
├── div.app-run-head           (h2 "Agent run" + .meta "3 of 4 agents complete")
├── ol.app-timeline
│   └── li.app-step[data-agent="..."]  × 4    ← see §2.2
├── span.eyebrow + aside.app-impact-card       ← see §2.3
├── article.app-ticket-form                    ← see §2.4
└── section.app-noc                            ← see §2.5
```

### 2.2 Per-agent timeline card (`.app-step`)

The card carries `data-agent="<llm-agent-name>"` so a single
`querySelector('.app-step[data-agent="<name>"]')` can target any one of the four
agents. Inner structure:

```
li.app-step[data-agent].{is-running|is-done|??}
├── span.app-step-dot                           (the rail dot, "1"/"2"/"3"/"4")
└── div.app-step-card
    ├── div.app-step-head
    │   ├── div.app-step-label
    │   │   ├── span.app-step-num               ("01" — static, prefix "AGENT · " from CSS ::before)
    │   │   └── span.app-step-name              ("Classifier" etc. — static)
    │   ├── span.app-step-status.{is-running|is-done}   ← TEXT toggles between "Running" and "Done"
    │   └── span.app-step-time                  ("+0.7s" or "streaming…" — currently text)
    ├── div.app-step-source                     (static source-tag pills; mirror existing chat.html)
    ├── div.app-step-terminal
    │   ├── div.app-step-terminal-bar
    │   │   ├── span.app-step-terminal-dots     (3× <i> traffic-lights — purely decorative)
    │   │   ├── span.label                      ("classifier · classify_issue" — DYNAMIC, see §3.4)
    │   │   │   └── span.agent (active tool name)
    │   │   └── span.meta                       (model meta — DYNAMIC, see §3.4)
    │   └── div.app-step-terminal-body          ← three populator targets (see §2.2.1)
    └── div.app-step-handoff                    (static `passes to next` chips per agent)
```

#### 2.2.1 Terminal-body content tiers (load-bearing)

Three sibling `<span>`s, **rendering order is meaningful** (CSS uses
`white-space: pre` and `display: contents` on the body to preserve column
alignment). The order in the mockup varies per card:

- **Classifier (card 1):** prose → cmd → out
- **Network / CDR (cards 2–3):** cmd → out → prose
- **Response Formatter (card 4):** cmd → out (no prose; out ends with cursor)

Tier classes:

| class                         | font          | semantic                                    |
|-------------------------------|---------------|---------------------------------------------|
| `.app-step-terminal-prose`    | Inter         | the agent's reasoning summary (coral left-rule pull) |
| `.app-step-terminal-cmd`      | JetBrains Mono| `$ tool_call(...)` invocation               |
| `.app-step-terminal-out`      | JetBrains Mono| output rows; nested `<span class="line">`s  |

Inside `.app-step-terminal-out`, each row is `<span class="line">...</span>`.
Inline spans inside a line carry semantic colour:
- `<span class="dim">…</span>` — muted (timestamps, prefixes, status arrows)
- `<span class="k">…</span>` — key (column headers, totals row prefix `→`)
- `<span class="v">…</span>` — value (numbers, ratios)
- `<span class="app-step-terminal-cursor" aria-hidden="true"></span>` —
  animated caret (`@keyframes app-cursor`, line 3609); present only on the
  `is-running` card's last line.

### 2.3 Impact rollup (`.app-impact-card`)

```
aside.app-impact-card
├── span.app-impact-icon                        (static "!")
└── div.app-impact-card-body
    ├── div.app-impact-headline
    │   ├── span.app-impact-headline-num        ← npFormatNum(npImpact.affected)
    │   └── span.app-impact-headline-label      ("customers affected")
    └── div.app-impact-substats                 ← N events · M days since onset · K dropped calls
        └── span × 5 (with " · " spacers)
```

Note: the rebuild `app.html` lays substats as a **flat list** of spans with
inline " · " separators, *not* as nested wrapper spans like
`np-impact-events-wrap` / `np-impact-elapsed-wrap`. Hide-when-empty is achieved
by **omitting the span entirely** instead of toggling `[hidden]`.

### 2.4 Ticket form (`.app-ticket-form`)

The dark-ink right-hand pane that **starts as a skeleton-shimmer** and **flips
to populated** when `complete` arrives.

Two visual states (both already in the mockup CSS):

**Compiling state (initial):**
- `.app-ticket-form` carries no extra class; CSS provides the background sweep
  (`@keyframes app-ticket-shimmer`, line 3378).
- `.app-ticket-form-pill` displays `Compiling` + spinner (`@keyframes
  app-ticket-spin`, line 3428).
- `<dl class="app-ticket-form-rows">` contains `.app-skeleton-line.is-{short,
  medium,long}` placeholders (`@keyframes app-skeleton`, line 3478).
- A pulsing progress dot (`@keyframes app-progress-pulse`, line 3503) fronts
  the "response_formatter is writing the ticket to AlloyDB…" caption.

**Populated state (post-`complete`):**
- `.app-ticket-form-pill` text → `Saved · AlloyDB`; inline style flipped to
  green (mockup line 245–248). Recommend extracting to `.is-saved` modifier.
- `.app-ticket-form-rows` replaced with six populated `.app-ticket-form-row`
  blocks:

| dt label          | dd source                                                |
|-------------------|----------------------------------------------------------|
| Class ID          | `TKT-{ticket_id zero-padded to 3}`                       |
| Classification    | `{category} · {severity}`                                |
| Region            | `{region}`                                               |
| Network Events    | `tool_response.result` rollup from `network_investigator`|
| CDR Findings      | `tool_response.result` rollup from `cdr_analyzer`        |
| Recommendation    | parsed out of `response_formatter`'s `tool_call.args.recommendation` |

### 2.5 NOC chips (`.app-noc`)

```
section.app-noc
├── span.app-noc-head     ("Recommended NOC actions for category: <strong>{cat}</strong>")
└── div.app-noc-chips
    └── span.app-noc-chip[.is-primary] × N      ← rendered from CATEGORY_ACTIONS[npState.category]
```

The first chip in each category gets `.is-primary` (coral-filled). All others
are plain.

---

## 3. Event → DOM mapping (the actual map)

Read this table top-to-bottom; that is the order events arrive on a healthy
run. Selectors are jQuery-style for brevity; in code use `querySelector`.

### 3.1 `region_attempt`

| field      | use                                                                              |
|------------|----------------------------------------------------------------------------------|
| `agent`    | scopes the chip to `.app-step[data-agent="<agent>"]`                             |
| `region`   | the **model name** (post-Phase-12 SSE field re-purpose) to display in the chip   |
| `outcome`  | `"ok"` settles the chip; `"failover"` adds the `failover` modifier               |
| `message`  | currently unused in the UI; could power a hover title in future                  |

**Target slot (gap):** the new markup has **no `.np-region-trace` equivalent**.
Recommend slotting into the terminal-bar `.meta` span on the matching card —
its job is exactly "active model id" already (mockup currently hardcodes
`gemini-3.1-flash-lite`).

**Mutation:** keep the existing `npRenderRegionAttempt()` chip-building logic
intact; rename the host selector from
`.np-timeline-entry .np-region-trace` to
`.app-step .app-step-terminal-bar .meta`. The collapse-on-same-region and
dataset.settled flag are still needed verbatim (ADK runs 2 LLM calls per
agent, so the chip must reset between walks — see chat.html lines 547–598).

**One regression risk:** the `.meta` span in the new markup is purely text,
no children. The chip-builder writes a structured tree (prefix span +
region spans + separator spans). That tree must replace the static text
node, not append to it. Add a `.app-step-terminal-bar .meta:empty` cleanup
pass on first entry.

### 3.2 `agent_start`

| field   | use                                            |
|---------|------------------------------------------------|
| `agent` | scope                                          |

**Mutations on `.app-step[data-agent="<agent>"]`:**

1. Add class `is-running`.
2. Inside `.app-step-status`, swap class `is-done` → `is-running` and set
   `textContent = "Running"`.
3. Inside `.app-step-time`, set `textContent = "streaming…"` (or `--:--:--`-
   style; the mockup uses `+0.7s` for done cards and `streaming…` for the
   running card — pick one convention).
4. Clear any prior populated terminal-body content (see §3.6 for ordering).

### 3.3 `tool_call`

| field   | use                                                                  |
|---------|----------------------------------------------------------------------|
| `agent` | scope                                                                |
| `tool`  | populates the terminal-bar `.label .agent` text (active tool name)   |
| `args`  | populates the `.app-step-terminal-cmd` body                          |

**Mutations:**

1. Inside `.app-step-terminal-bar .label .agent`, set `textContent = ev.tool`.
2. Append a new `.app-step-terminal-cmd` line under `.app-step-terminal-body`,
   formatted as `${ev.tool}(${JSON.stringify(ev.args)})`. *Format note:* the
   mockup uses pretty-printed argument formatting on long calls (mockup line
   212 wraps `save_incident_ticket(...)` across 4 lines using `<br>` +
   `&nbsp;` indents). Match this for `save_incident_ticket` only — it has a
   long arg list. Single-line is fine for the others.
3. **Sticky state for downstream rendering** — cache the args we need later:
   - if `ev.tool === 'classify_issue'` and `ev.args.{category,region}`, write
     to `npState.{category,region}` (preserves existing chat.html lines
     663–666 logic). Drives §3.7 ticket-form Classification + Region cells
     and §3.8 NOC chips.
   - if `ev.tool === 'save_incident_ticket'`, cache `ev.args` into a new
     `npTicketDraft` global so §3.7 can populate the ticket-form rows on
     `complete`. The args are the *only* place the recommendation, the
     related_events list, and the cdr_findings string actually live; the
     `tool_response` only carries the new ticket_id.

### 3.4 `tool_response`

| field    | use                                                                       |
|----------|---------------------------------------------------------------------------|
| `agent`  | scope                                                                     |
| `tool`   | logging only                                                              |
| `result` | drives the `.app-step-terminal-out` rendering AND the impact card        |

**Mutations:**

1. Append a new `.app-step-terminal-out` block under `.app-step-terminal-body`.
   Render rows using the `<span class="line">…</span>` shape (see §2.2.1).
   The mockup hand-rendered example for `network_investigator` looks like:
   ```
   <span class="line"><span class="dim">[1571398]</span> [outage] [minor] [2026-04-26 06:51:43+00] affected:<span class="v">21,342</span></span>
   ```
   Real rows come from `npExtractRows(ev.result)` (see §4.2). For each row,
   format as `[event_id] [event_type] [severity] [started_at] affected:<v>{n}</v>`
   for network, `<tower> <dropped> <baseline> <ratio>` for CDR, and one row
   per saved-ticket field for response_formatter (only one tool_call there).
2. **Hide the cursor** that may still be in the previous out block — but only
   if any partial cursor was added. (In practice, the cursor only renders
   when a card flips to running and stays until the first text/done event.)
3. **For `network_investigator` only:** run `npExtractRows(ev.result)`, then:
   - `npMaxSeverity(rows)` → `npState.topSeverity` (drives ticket badge).
   - `npComputeImpact(rows)` → if `events > 0`, replace `npImpact` and call
     `npRenderImpact()` against the new selectors:
     - `.app-impact-card` → no longer hide/show via `[hidden]`; recommend
       toggling `.is-empty` for hidden, or just inserting/removing the
       whole `<aside>` from the DOM. Easier: set `aside.hidden = false` on
       first populate and leave it visible.
     - `.app-impact-headline-num` ← `npFormatNum(npImpact.affected)`
     - `.app-impact-substats` ← rebuild children from scratch (clear, then
       append `<span>{events} events</span>`, `<span>·</span>`,
       `<span>{elapsed} since onset</span>`, `<span>·</span>`,
       `<span>{droppedCalls} dropped calls (vs {baseline} baseline)</span>`).
     - **Note:** the mockup substats include `581 dropped calls (vs 60
       baseline)` which comes from `cdr_analyzer`, not `network_investigator`.
       The current chat.html `npImpact` only has network-events fields. To
       populate the dropped-calls substat we need a *parallel* impact merge
       on the `cdr_analyzer` tool_response too — gap, see §5.5.

### 3.5 `text`

| field   | use                                                                          |
|---------|------------------------------------------------------------------------------|
| `agent` | scope                                                                        |
| `text`  | populates the prose tier (`.app-step-terminal-prose`) AND, for response_formatter, captures into `final_report` for the ticket form |

**Mutations:**

1. Find the matching card. **Replace** (not append) `.app-step-terminal-prose`
   `textContent` with `ev.text`. Rationale: ADK fires `text` once per non-
   partial event; for our agents this is a single deterministic block per
   agent (the formatted prompt output). Appending would interleave with
   debug fragments.
2. Flip the card from `is-running` → `is-done`:
   - `entry.classList.remove('is-running')`, `add('is-done')`
   - `entry.querySelector('.app-step-status').classList.replace('is-running', 'is-done')`
   - `entry.querySelector('.app-step-status').textContent = 'Done'`
   - `entry.querySelector('.app-step-time').textContent` → use the existing
     `npNowHHMMSS()` or compute `+{elapsed}s` from a per-agent start
     timestamp captured at `agent_start`. The mockup uses `+0.7s`-style
     deltas; recommend implementing via a per-agent `Date.now()` stamp
     captured at `agent_start`.
3. **For `response_formatter` only:** parse `ev.text` for the final report's
   structured fields (see §3.7) — actually, the cleaner path is to populate
   from the cached `npTicketDraft` (§3.3) on `complete`, not from the prose
   text. The prose tier on this card is empty anyway in the mockup (mockup
   lines 211–215 have only cmd + out, no prose); rendering the formatted
   report in the prose tier is fine but the **ticket form** below is the
   authoritative renderer.

### 3.6 Ordering subtlety: `agent_start` clears, then events repopulate

ADK fires events in this order per agent: `agent_start`, then 1 or more
`tool_call` / `tool_response` pairs, then 1 `text` event. The card flips
through three visual states:

```
(initial: no class)
   │  agent_start
   ▼
.app-step.is-running                 (status pill "Running", cursor visible)
   │  tool_call → tool_response (× N)
   │  (terminal-body fills; cursor stays on the trailing "→ " line)
   ▼
.app-step.is-running                 (still running until text arrives)
   │  text
   ▼
.app-step.is-done                    (status pill "Done", cursor removed,
                                      timing pill flips from "streaming…" to "+Ns")
```

`npReset()` (called by `npSubmit()` before each new run) must walk all four
cards, remove `is-running` and `is-done`, restore the status pill text to
empty/"waiting", clear all three terminal-body tiers, and remove any
`region_attempt` chip child structure from the bar `.meta`.

### 3.7 `complete`

| field          | use                                                                  |
|----------------|----------------------------------------------------------------------|
| `ticket_id`    | populates the ticket-form title + Class ID row                       |
| `final_report` | currently rendered into `.np-final-text`; in the new markup, becomes the source-of-truth for the right-pane ticket form **only if `npTicketDraft` is unset** (defensive) |

**Mutations on `.app-ticket-form`:**

1. Replace `.app-ticket-form-pill` content:
   - text → `Saved · AlloyDB`
   - icon → green check (already in mockup HTML)
   - class → add `.is-saved`, remove `.is-compiling` (gap — see §5.4)
2. Replace `.app-ticket-form-rows` skeleton placeholders with six populated
   `.app-ticket-form-row` blocks:

   | dt              | dd value source (preferring `npTicketDraft`, falling back to parsed `final_report`) |
   |-----------------|------------------------------------------------------------------------------------|
   | Class ID        | `TKT-{ticket_id.padStart(3,'0')}`                                                  |
   | Classification  | `${npState.category} · ${npState.topSeverity}`                                     |
   | Region          | `${npState.region}`                                                                |
   | Network Events  | rebuilt from `npImpact` (events count + first headline) OR from `npTicketDraft.related_events` |
   | CDR Findings    | from `npTicketDraft.cdr_findings`                                                  |
   | Recommendation  | from `npTicketDraft.recommendation`                                                |

3. Replace the `.app-ticket-form-title` content from `Ticket #{n placeholder}`
   to `Ticket #{ev.ticket_id}`.

**Mutations on `.app-noc`:**

1. Replace `.app-noc-head <strong>` text with `npState.category`.
2. Rebuild `.app-noc-chips` from `CATEGORY_ACTIONS[npState.category]`. First
   chip carries `.is-primary`.

### 3.8 `error`

Two paths, dispatched by presence of `ev.agent`:

**Agent-scoped (`ev.agent` present):**

The current chat.html flips the card to `.error`, replaces the status text
with `error`, and inserts an `.np-error-msg` block before the handoff footer.
The new markup has **no `.is-error` state class and no error-message slot**
(gap — see §5.1). Proposed mutations:

1. `entry.classList.add('is-error')`. Remove `is-running` / `is-done`.
2. `entry.querySelector('.app-step-status').classList.replace('is-running','is-error')`
   (or `.replace('is-done', 'is-error')`); set text → `Error`.
3. Insert (or update) `.app-step-error-msg` block between `.app-step-source`
   and `.app-step-terminal`. Content: `[{ev.tool}] {ev.message}` if `tool`
   present, else `{ev.message}`.

**Top-level (`ev.agent` absent):**

The whole right pane (the ticket form) is the synthesis target. On global
error:

1. `.app-ticket-form-pill` → text `Error`, class `.is-error`.
2. `.app-ticket-form-rows` skeleton stays *or* replaced with a single error
   block (recommend: replace with a one-cell `<div class="app-ticket-form-error">{ev.message}</div>`).
3. Stop the shimmer/spinner animations by adding `.is-error` to
   `.app-ticket-form` (gap — see §5.4 — needs CSS that disables the
   `app-ticket-shimmer` keyframe under `.is-error`).

---

## 4. Load-bearing pieces (must NOT break)

These are subtle and have already burned production runs once; preserve
verbatim during the port.

### 4.1 `pool_recycle=300` and async-to-sync bridge

Out of scope for this doc — but reminder: don't replace `agent_runner.py`'s
thread+queue bridge with a naive `asyncio.run()` wrapper, and don't drop the
SQLAlchemy `pool_recycle=300` on the data-viewer engines. These have nothing
to do with the SSE port and should stay untouched.

### 4.2 `npExtractRows()` — the recursive Array | string parser

Source: `chat.html` lines 246–264.

**Why it exists.** `toolbox_core/itransport.py:51` declares
`tool_invoke -> str`; ADK then wraps any non-dict tool return as
`{"result": "<json-string>"}`. So `tool_response.result` arrives as **a
JSON-encoded string of the row array, not the array itself.** Without
recursive `JSON.parse`, the impact card silently degrades to `[]`.

**Port verbatim.** Do not "simplify" this function. The four key fallback
keys (`rows`, `records`, `events`, `result`, `data`) cover every shape MCP
toolbox + ADK produces today. The recursion handles the doubly-encoded
case (`result.result` as a JSON string of `{rows: [...]}`).

### 4.3 `region_attempt` chip — same-model collapse + settled flag

Source: `chat.html` lines 547–598.

**Why it exists.** ADK makes **2 LLM calls per agent** (tool selection +
tool-result interpretation), so each agent run produces **two independent
walks** of `ATTEMPT_SCHEDULE`. Without the `dataset.settled` flag, the
chip reads as one giant chain (`primary ↪ fallback ↪ primary ↪ fallback`),
falsely suggesting the wrapper bounced back. Also: retries on the *same*
model collapse silently (no separator inserted) so a single 429 retry that
clears doesn't visually scream "failover".

**Port verbatim.** The only change is the host selector (see §3.1). Keep
the dataset flag, keep the same-region-de-dupe check, keep the U+21AA
separator.

### 4.4 `tool_call` / `tool_response` arity is unbounded

`network_investigator` has 3 tools available and the prompt may invoke 1
or 2 of them per run. `cdr_analyzer` is constrained to exactly 1
`query_cdr_nl` call by the prompt's "EXACTLY ONE" rule. `response_formatter`
makes exactly 1 `save_incident_ticket` call.

**Implication:** the `.app-step-terminal-body` content must **append**
multiple cmd/out pairs in order, not overwrite. The mockup shows one of
each per card — but a real run on `network_investigator` may produce two.
Plan the renderer to handle N tool_call/tool_response pairs per card.

### 4.5 `final_report` capture from response_formatter

Source: `agent_runner.py` lines 240–244.

The `complete` event carries `final_report` only because the worker
captures the *last* `text` event from `response_formatter` mid-stream and
hands it back at end-of-stream. If the response_formatter agent errors
before emitting text, `final_report` is `null` — `complete` still fires
(line 245). The renderer must handle `final_report = null` gracefully —
fall back to `npTicketDraft` only.

---

## 5. Gaps in the rebuild markup (proposed minimal additions)

Each gap names the missing slot, the smallest additive change, and the CSS
side-effect. None of these require structural rework.

### 5.1 `.is-error` state on `.app-step` and `.app-step-status`

**Missing.** Mockup only has `is-running` and `is-done`.

**Proposal.** Add CSS:
```css
.app-step.is-error .app-step-card { border-color: rgba(185, 78, 58, .55); }
.app-step-status.is-error {
  background: rgba(185, 78, 58, .12);
  color: #b94e3a;
  border: 1px solid rgba(185, 78, 58, .25);
}
```
Mirror existing `.is-running` / `.is-done` rule shapes (CSS lines 3214–3236).

**Markup slot.** Insert one element inside `.app-step-card`, after
`.app-step-source`, before `.app-step-terminal`:
```html
<div class="app-step-error-msg" hidden></div>
```
Default `display: none` via the `[hidden]` attribute; populator removes the
attribute and writes `[{tool}] {message}` text.

### 5.2 Region-attempt chip slot

**Missing.** No equivalent of `.np-region-trace`. The nearest analogue is
the `.app-step-terminal-bar .meta` span which today is a static text node.

**Proposal.** Repurpose the existing `.meta` span. The chip-builder in
§3.1 replaces its children. CSS already targets it (`color: var(--ink-2)`,
mockup line 26 inline style); add a modifier:
```css
.app-step-terminal-bar .meta.np-trace-failover { color: #b94e3a; }
.app-step-terminal-bar .meta .np-region-trace-prefix { color: var(--ink-3); }
.app-step-terminal-bar .meta .np-region-trace-region { color: var(--ink-2); }
.app-step-terminal-bar .meta .np-region-trace-sep { margin: 0 4px; color: var(--ink-3); }
```

### 5.3 Per-attempt timing

**Missing.** Mockup shows static `+0.7s` / `+2.3s` / `+3.1s` / `streaming…`
in `.app-step-time`. The current chat.html shows wall-clock
`HH:MM:SS` from `npNowHHMMSS()`, not a delta.

**Proposal.** Capture `agentStarts[agent] = Date.now()` on `agent_start`;
on flip to `is-done`, compute `((Date.now() - agentStarts[agent]) /
1000).toFixed(1)` and write `+{n}s`. While running, write `streaming…`.

This is purely cosmetic but matches the mockup exactly and reads better
than wall-clock time on a 10-second run.

### 5.4 Ticket-form pill states

**Missing.** Pill currently uses inline-style colours (`Saved · AlloyDB` is
green inline at mockup lines 245–248; the Compiling state is rendered
inline elsewhere via the same `<span class="app-ticket-form-pill">`). No
semantic state class.

**Proposal.** Replace inline styles with three state classes:
```css
.app-ticket-form-pill.is-compiling { /* coral background, spinner visible */ }
.app-ticket-form-pill.is-saved { background: rgba(74,140,94,.18); color: #c8e8d4; border-color: rgba(74,140,94,.45); }
.app-ticket-form-pill.is-error { background: rgba(185,78,58,.18); color: #f3b8a4; border-color: rgba(185,78,58,.45); }
```
And one toggle on `.app-ticket-form` itself for the shimmer:
```css
.app-ticket-form.is-saved::before { animation: none; opacity: 0; }
.app-ticket-form.is-error::before { animation: none; opacity: 0; }
```
(`::before` is currently the shimmer overlay per CSS lines 3370+.)

### 5.5 Dropped-calls substat — needs a CDR-side impact merge

**Missing.** The mockup substat list includes "581 dropped calls (vs 60
baseline)" — that data lives in the `cdr_analyzer` tool response, not the
`network_investigator` one. Current `npComputeImpact()` only knows about
network rows.

**Proposal.** Extend the impact pipeline:

1. Hook `cdr_analyzer.tool_response` (`tool === 'query_cdr_nl'`) → run
   `npExtractRows(ev.result)` → collect rows.
2. Sum a new `npImpact.droppedCalls` from rows where `call_status` is
   `dropped` or `failed`. Sum a parallel `npImpact.baselineDropped` if the
   schema returns a baseline column (currently it does — the mockup
   example shows `baseline` and `ratio` columns from a NL query).
3. Render the third substat only if `droppedCalls > 0`.

If the NL2SQL response shape is variable (different per question), gate
this gracefully — `droppedCalls === undefined` skips the substat
rendering. **Important:** do not let the NL2SQL parser failure hide the
network-impact substats. Keep the two impact merges independent.

### 5.6 Sample chips behaviour

**Missing.** `.app-chip` buttons in the new markup carry no event handler.
Existing chat.html `.np-chip` calls `npFill(this)` which writes the chip
text into `#np-input`.

**Proposal.** Wire `.app-chip` to a new `appFill()` helper that targets
`.app-prompt-input` (the textarea) instead of `#np-input` (text input).
Otherwise identical to the existing helper.

### 5.7 Empty-input hint

**Missing.** No `.np-input-hint` analogue. The mockup has no inline hint
slot at all.

**Proposal.** Insert one `<div class="app-prompt-hint" role="alert"
aria-live="polite" hidden></div>` between the `.app-prompt` and
`.app-chips` blocks. Style it to match the existing `.np-input-hint`.

### 5.8 "New run" button (`.nav-cta`)

**Missing behaviour.** The mockup nav has a `New run` button (line 36); the
existing chat.html has only the `npReset()` function called inside
`npSubmit()`. The new button has no handler.

**Proposal.** Wire `.nav-cta button` onclick → `npReset(); document
.querySelector('.app-prompt-input').focus()`.

### 5.9 `?seed=...&autorun=1` deep-link

**Behaviour to preserve.** Existing `npOnLoad()` reads URL params and
either fills the input (and submits if `autorun=1`) or focuses. The
landing-page chips depend on this contract.

**Proposal.** No change; the helper just needs the new target selector
(`.app-prompt-input` instead of `#np-input`).

### 5.10 Handoff chips on the running card

**Cosmetic.** The mockup's `.app-step-handoff` shows on done cards (`passes
to next`) but is suppressed on the running card 4 in the mockup (it has no
handoff because it's the last agent). Cards 1–3 keep the handoff visible
even when `is-running`. Mirror this — no special hiding logic needed.

---

## 6. Selector rename quick-reference (chat.html → app.html)

| concern                          | chat.html selector                        | new app.html selector                                  |
|----------------------------------|-------------------------------------------|--------------------------------------------------------|
| Prompt input                     | `#np-input` (input[type=text])            | `.app-prompt-input` (textarea)                         |
| Submit button                    | `#np-submit`                              | `.app-prompt-submit`                                   |
| Empty-input hint                 | `#np-input-hint`                          | `.app-prompt-hint` *(new — see §5.7)*                  |
| Sample chips                     | `.np-chip`                                | `.app-chip`                                            |
| Per-agent card                   | `.np-timeline-entry[data-agent="..."]`    | `.app-step[data-agent="..."]`                          |
| Card running state               | `.np-timeline-entry.running`              | `.app-step.is-running`                                 |
| Card done state                  | `.np-timeline-entry.done`                 | `.app-step.is-done`                                    |
| Card error state                 | `.np-timeline-entry.error`                | `.app-step.is-error` *(new — see §5.1)*                |
| Status pill                      | `.np-status`                              | `.app-step-status`                                     |
| Time stamp                       | `.np-timeline-time`                       | `.app-step-time`                                       |
| Tool list                        | `ul.np-tools` (list-of-li)                | `.app-step-terminal-body` (append `.app-step-terminal-cmd` / `.app-step-terminal-out` siblings) |
| Tool-call line                   | `li.np-tool-call`                         | `span.app-step-terminal-cmd`                           |
| Tool-response line               | `li.np-tool-resp`                         | `span.app-step-terminal-out`                           |
| Reasoning text block             | `pre.np-text`                             | `span.app-step-terminal-prose`                         |
| Region-attempt chip              | `.np-region-trace`                        | `.app-step-terminal-bar .meta` *(repurposed — see §5.2)* |
| Active model meta                | (n/a; lived in trace chip)                | `.app-step-terminal-bar .meta`                         |
| Active tool meta                 | (n/a; lived in tool-line tag)             | `.app-step-terminal-bar .label .agent`                 |
| Per-agent error msg              | `.np-error-msg`                           | `.app-step-error-msg` *(new — see §5.1)*               |
| Impact card                      | `.np-impact-card`                         | `.app-impact-card`                                     |
| Impact affected count            | `.np-impact-affected`                     | `.app-impact-headline-num`                             |
| Impact substats                  | `.np-impact-events-wrap` + `.np-impact-elapsed-wrap` + `.np-impact-sevs` | `.app-impact-substats` (flat children, see §2.3) |
| Final ticket card                | `.np-final`                               | `.app-ticket-form` (note: persistent in DOM, state-toggled, not show/hide) |
| Final ticket id                  | `.np-ticket`                              | `.app-ticket-form-title`                               |
| Final ticket status pill         | (n/a)                                     | `.app-ticket-form-pill` *(new states — see §5.4)*      |
| Final report text                | `.np-final-text`                          | (parse into `.app-ticket-form-rows` `.dd`s, see §3.7)  |
| Ticket category/region badges    | `.np-ticket-badges`                       | (rendered inline into `.app-ticket-form-row` `dd`s)    |
| NOC actions panel                | `.np-actions-panel`                       | `.app-noc`                                             |
| NOC chips                        | `.np-action-chip`                         | `.app-noc-chip` (first one carries `.is-primary`)      |

---

## 7. Recommended port order (Step 4 plan, not implementation)

Sequenced to keep the build green at every commit. **Do not start until
explicit user signal.**

1. **Markup port.** Replace the `{% block content %}` body of `chat.html`
   with the rebuild app.html structure. Keep the `<script>` block
   intact at the bottom — it still references the old selectors and will
   throw, but that is expected. Update `base.html`'s `<link>` to load
   `site.css` (already in `static/`). Smoke-test: page loads, looks
   right, JS errors in console.

2. **Add the §5.1 / §5.2 / §5.4 / §5.7 markup additions** with their CSS.
   No JS yet. Smoke-test: page still looks identical to the mockup.

3. **Rewire submit + chips.** Update `npSubmit()`, `npFill()`,
   `npFlashInputHint()`, `npClearInputHint()`, `npSetBusy()`, `npOnLoad()`
   to point at the new selectors. The whole agent run is still broken at
   this point, but the form itself works. Smoke-test: typing in the
   textarea, clicking a chip, submitting.

4. **Rewire `npReset()`.** Walk all four cards, clear all states, restore
   the ticket form to compiling state, hide impact + NOC. Smoke-test:
   submit a query, watch the page reset properly between runs.

5. **Rewire `npHandle()` per §3.** Tackle the events in order:
   `agent_start` → `tool_call` → `tool_response` → `text` → `complete` →
   `error` → `region_attempt`. After each event type lands, run an
   end-to-end query and confirm the relevant DOM mutation. The first
   four events get you a working timeline; `complete` gets you the
   ticket form; `error` and `region_attempt` are polish.

6. **Validate the load-bearing pieces.** Run a real query:
   - Confirm `npExtractRows` extracts 6 events from the
     `query_network_events` response (not `[]`).
   - Confirm `region_attempt` events on a 429 retry collapse onto one
     model name (don't render `primary ↪ primary`).
   - Confirm `tool_call` for `save_incident_ticket` cached args populate
     the ticket form on `complete` (not the `tool_response` which only
     has `{ticket_id: N}`).
   - Confirm impact card fills both `affected` count and dropped-calls
     substat (the latter requires the §5.5 CDR-side merge).

7. **Then deploy** via the same gcloud command as Phase B. No SSE backend
   changes, so the redeploy carries only the template + static asset
   changes.

---

## Appendix A. Untouched files

These are referenced upstream of the SSE chain but **must not be modified**
during the port:

- `netpulse-ui/agent_runner.py` — backend producer; SSE event shape is the
  contract.
- `netpulse-ui/data_queries.py` — read-only data viewer queries; shares
  `pool_recycle=300` settings with the agent path.
- `telecom_ops/agent.py` — agent definitions; `name=` values are how the
  data-agent attribute matches.
- `telecom_ops/prompts.py` — agent instructions; tool names referenced
  here drive the source-tag rendering.
- `telecom_ops/tools.py` — `classify_issue` + `save_incident_ticket` +
  toolset loaders. `save_incident_ticket`'s VALID_CATEGORIES guard
  (raises `status='error'`) is what produces tool-scoped error events.
- `telecom_ops/vertex_failover.py` — model-ladder logic; the
  `region_attempt` observer hooks here.

## Appendix B. Things deliberately NOT in scope

- **Chat history.** The current UI shows one query at a time and resets
  on submit; the rebuild does the same. No session/history feature work.
- **Tool-call argument editing / re-runs.** No interactive replay.
- **Multi-tenant session IDs.** `agent_runner.py` uses a per-request
  `uuid.uuid4().hex`; no cookie-based sessions.
- **WebSockets / bi-directional updates.** SSE is unidirectional and
  that's fine; no upgrade path.
- **The 4 agent labels.** Agent count, names, and order are fixed by
  `telecom_ops/agent.py` and reflected in 4 hard-coded
  `data-agent="..."` cards. Don't try to render the agent list
  dynamically — there's no event in the SSE stream that names them up
  front.
