# NetPulse AI — Refinement Audit

**Phase:** APAC GenAI Academy 2026 — Top 100 (#82) → Top 10
**Audit date:** 2026-04-25
**Refinement deadline:** 2026-04-30 (5 days)
**Source state:** all 6 deployed services healthy; live SSE chat verified end-to-end (ticket #66 generated during audit)
**Companion plan:** `PLAN-vertex-region-failover.md` (Tier 3 anchor work item, summarized in §3 below)

---

## Executive summary

NetPulse AI is functionally solid and the demo runs cleanly. Refinement is a polish-and-narrative push, not a rebuild. This audit consolidates 36 codebase findings, 6 Cloud Run config observations, 1 live-demo quality issue, the Vertex AI region failover plan, and 10 UI redesign proposals drawn from ServiceNow ITSM + PagerDuty conventions. Items are organized into four execution tiers, prioritized for what a hackathon judge will actually notice in a 5-minute walkthrough.

**Top three priorities for Top 10:**
1. Implement the Vertex AI region failover (the innovation story).
2. Surface tool errors and add a loading state in the chat UI (the demo robustness).
3. Re-orient the chat into a ticket workspace with timeline + impact card + recommended actions (the polish that elevates "demo" into "product").

---

## Status snapshot (2026-04-27)

**Refinement work has progressed past the original audit.** Phases 8-12 shipped between 2026-04-26 and 2026-04-27, settling on revisions `netpulse-ui-00019-t46` + `network-toolbox-00010-cmd`. The **Master summary table** (and its **Phase 9/10/11/12 extension**) below carries an inline **Status** column on every row — scan there for ✅/⏸/🔄 per item ID. This section is the tier/phase rollup. Per-item execution narrative + verifications live in [`REFINEMENT-PHASES.md`](./REFINEMENT-PHASES.md); per-item rationale lives in §1-§5 (original audit) and the new "Phase 9 / 10 / 11 / 12" sections at the bottom of *this* document.

**Status legend:**
- ✅ **DONE** — shipped to production (verified)
- ⏸ **DEFERRED** — tracked but not shipped in the 5-day window (post-Top-10 candidate)
- 🔄 **RESOLVED via §X** — fulfilled or obsoleted by another shipped item; no separate work needed

### Shipped vs deferred — by tier / phase

The "Satisfied" column = ✅ + 🔄 (items whose intent is met, whether by direct work or by coverage from another shipped item).

| Tier / Phase | Total | ✅ | 🔄 | ⏸ | Satisfied | Hit rate |
|---|---:|---:|---:|---:|---:|---:|
| Tier 1 — demo-blocking polish | 7 | 7 | 0 | 0 | 7 | 100% |
| Tier 2 — quality + storytelling (incl. §5 redesign Tier-2 items) | 19 | 13 | 1 | 5 | 14 | 74% |
| Tier 3 — innovation (Vertex AI region failover) | 2 | 2 | 0 | 0 | 2 | 100% |
| Tier 4 — brainstorming queue (incl. §5 redesign Tier-4 items) | 10 | 0 | 2 | 8 | 2 | 20% |
| **Original audit subtotal** | **38** | **22** | **3** | **13** | **25** | **66%** |
| Phase 9 — post-deploy polish + robustness | 14 | 12 | 1 | 1 | 13 | 93% |
| Phase 10 — toolbox refactor + seed enrichment | 6 | 6 | 0 | 0 | 6 | 100% |
| Phase 11 — AlloyDB AI NL2SQL + BigQuery analytical workload | 3 | 3 | 0 | 0 | 3 | 100% |
| Phase 12 — Vertex model-ladder failover + viewer UX polish | 5 | 5 | 0 | 0 | 5 | 100% |
| **Post-audit subtotal** | **28** | **26** | **1** | **1** | **27** | **96%** |
| **Grand total** | **66** | **48** | **4** | **14** | **52** | **79%** |

### Resolved-via — informational

These items were not directly implemented but are satisfied by other shipped work (or, in the case of §9.7, were findings rather than deliverables). All carry 🔄 in the Status column above.

- **§2.5 Region whitelist in `query_cdr`** — `query_cdr` was deleted in **§11.1**. Region validation now happens through AlloyDB AI's `city_name` concept-type binding registered in `setup_alloydb_nl.py:associate_region_concept` — a structural enforcement point that's stronger than a Python whitelist would have been.
- **§4.2 Idempotency keys on `save_incident_ticket`** — the original concern was retry-induced duplicates. **§3.1 / §9.4 / §9.14** failover design only retries *before* the underlying call returns success (cancellation-on-timeout), AND **§1.2** disables the Investigate button during a request. Duplicate writes from retries are now structurally impossible — no idempotency column needed.
- **§4.4 Demo seed panel — clickable example complaints** — fully absorbed by **§5.11 landing chips**. The launch chips on `/` use `?seed=...&autorun=1` to pre-populate `/app`, which is exactly the in-app seed panel concept with a better entry point (judges meet the chips before reaching the workspace).
- **§9.7 Pro-preview region-whitelist finding** — surfaced 2026-04-26 when `gemini-3.1-pro-preview` returned `404 NOT_FOUND` in non-`global` regions on this project, making the failover ladder a structural no-op for synthesis. **Resolved via §9.13** (collapse `MODEL_SYNTHESIS = MODEL_FAST` so all 4 agents run on `gemini-3.1-flash-lite-preview`, which is multi-region addressable end-to-end).

---

## Master summary table

Auth column legend:
- **src** = source change only (verifiable locally)
- **src+deploy** = source change + manual Cloud Run redeploy by user (Freeze A boundary)
- **config** = Cloud Run config write only (no source)
- **doc** = README / docs / screenshots only (no deploy)

**Status column legend:** ✅ DONE (shipped to production) · ⏸ DEFERRED (post-Top-10 candidate) · 🔄 RESOLVED via §X (fulfilled or obsoleted by another shipped item)

| ID | Status | Item | Tier | Category | Severity | Effort | Auth | Files |
|---|:-:|---|---|---|---|---|---|---|
| 1.1 | ✅ | Surface tool errors as chat card error state | 1 | UX | HIGH | M | src+deploy | `netpulse-ui/templates/chat.html`, `netpulse-ui/agent_runner.py` |
| 1.2 | ✅ | Disable Investigate button + spinner during request | 1 | UX | MEDIUM | S | src+deploy | `netpulse-ui/templates/chat.html` |
| 1.3 | ✅ | Client-side empty/whitespace input validation | 1 | UX | MEDIUM | S | src+deploy | `netpulse-ui/templates/chat.html` |
| 1.4 | ✅ | Tighten `network_investigator` output to enumerate ALL events | 1 | Prompt | HIGH | M | src+deploy | `telecom_ops/prompts.py` |
| 1.5 | ✅ | Validate `category` enum in `save_incident_ticket` | 1 | Tool | HIGH | S | src+deploy | `telecom_ops/tools.py` |
| 1.6 | ✅ | Set `minScale=1` on `netpulse-ui` (kill 7s cold start) | 1 | Config | HIGH | S | config | (Cloud Run) |
| 1.7 | ✅ | Raise `maxScale` on `network-toolbox` from 3 → 10 | 1 | Config | MEDIUM | S | config | (Cloud Run) |
| 2.1 | ⏸ | SSE heartbeat every 5s during long agent calls | 2 | Observability | MEDIUM | S | src+deploy | `netpulse-ui/app.py`, `agent_runner.py` |
| 2.2 | ✅ | Pagination context on data viewer tabs | 2 | UX | MEDIUM | M | src+deploy | `netpulse-ui/data_queries.py`, `templates/*.html` |
| 2.3 | ✅ | Form labels + ARIA attributes on filter selects | 2 | UX/A11y | MEDIUM | S | src+deploy | `netpulse-ui/templates/network_events.html` etc. |
| 2.4 | ⏸ | Error classification (network/LLM/DB) in card error state | 2 | UX | MEDIUM | M | src+deploy | `netpulse-ui/agent_runner.py`, `chat.html` |
| 2.5 | 🔄 | Region whitelist in `query_cdr` *(obsoleted by §11.1 — `query_cdr` deleted; AlloyDB AI `city_name` concept binds region validation)* | 2 | Tool | MEDIUM | S | src+deploy | `telecom_ops/tools.py` |
| 2.6 | ✅ | Complaint length cap + sanitization | 2 | Tool | MEDIUM | S | src+deploy | `telecom_ops/tools.py` |
| 2.7 | ✅ | Make hardcoded URLs env-driven (`TOOLBOX_URL`, project ID) | 2 | Tool/Config | HIGH | S | src+deploy | `telecom_ops/tools.py`, `netpulse-ui/data_queries.py` |
| 2.8 | ⏸ | Structured logs with session correlation ID | 2 | Observability | HIGH | M | src+deploy | `netpulse-ui/agent_runner.py`, `telecom_ops/tools.py` |
| 2.9 | ✅ | "Quick Demo" section in README with example queries | 2 | Doc | MEDIUM | S | doc | `README.md` |
| 2.10 | ✅ | Architectural callouts above mermaid diagram | 2 | Doc | MEDIUM | S | doc | `README.md` |
| 2.11 | ⏸ | SSE streaming GIF / animated screenshot in README | 2 | Doc | MEDIUM | M | doc | `README.md`, `docs/screenshots/` |
| 2.12 | ✅ | Schema contract + env-driven dataset names + reproducible seed pipeline (BYO-data foundation) | 2 | Tool/Doc/Reproducibility | HIGH | M | src+deploy | `docs/SCHEMA.md` (NEW), `docs/seed-data/*.csv` (NEW), `scripts/setup_bigquery.py` (NEW), `scripts/setup_byo.sh` (NEW), `setup_alloydb.py`, `telecom_ops/tools.py`, `netpulse-ui/data_queries.py`, `README.md` |
| 3.1 | ✅ | Vertex AI region failover (`global` default + ladder) | 3 | Innovation | HIGH | L | src+deploy+env | `telecom_ops/vertex_failover.py` (NEW), `agent.py`, `.env` |
| 3.2 | ✅ | Per-attempt region telemetry in chat cards | 3 | UX/Story | MEDIUM | M | src+deploy | `netpulse-ui/agent_runner.py`, `chat.html` |
| 4.1 | ⏸ | Parallelize `network_investigator` + `cdr_analyzer` | 4 | Architecture | MEDIUM | L | src+deploy | `telecom_ops/agent.py` |
| 4.2 | 🔄 | Idempotency keys on `save_incident_ticket` *(obsoleted by §3.1 / §9.4 / §9.14 pre-tool retry design + §1.2 button disable)* | 4 | Tool | LOW | M | src+deploy | `telecom_ops/tools.py`, `setup_alloydb.py` |
| 4.3 | ⏸ | Minimal pytest suite for `tools.py` | 4 | Tests | LOW | L | src | `telecom_ops/tests/` (NEW) |
| 4.4 | 🔄 | Demo seed panel — clickable example complaints *(absorbed by §5.11 landing chips with `?seed=…&autorun=1` handoff)* | 4 | UX | MEDIUM | S | src+deploy | `netpulse-ui/templates/chat.html`, `app.py` |
| 4.5 | ⏸ | Live ticket counter strip on chat page | 4 | UX | MEDIUM | M | src+deploy | `netpulse-ui/app.py`, `chat.html`, `data_queries.py` |
| 5.0a | ✅ | Design token foundation (curated from `heliodoron-ui-identity`) — prerequisite for the rest of §5 | 2 | UX/Foundation | HIGH | M | src+deploy | `static/tokens.css` (NEW), `static/style.css`, `templates/*.html` |
| 5.1 | ⏸ | Three-pane ticket workspace layout (ServiceNow-inspired) | 2 | UX/Redesign | HIGH | L | src+deploy | `chat.html`, `style.css`, `app.py` |
| 5.2 | ✅ | Pipeline-as-timeline (PagerDuty-style vertical activity stream) | 2 | UX/Redesign | HIGH | M | src+deploy | `chat.html`, `style.css` |
| 5.3 | ✅ | Severity + Category badges with color coding | 2 | UX/Redesign | MEDIUM | S | src+deploy | `chat.html`, `style.css`, `agent_runner.py` |
| 5.4 | ✅ | "Recommended NOC actions" chip panel on ticket | 2 | UX/Redesign | MEDIUM | M | src+deploy | `chat.html`, `prompts.py` |
| 5.5 | ✅ | Customer-impact card (X affected, Y min, Z events) | 2 | UX/Redesign | HIGH | M | src+deploy | `chat.html`, `prompts.py`, `agent_runner.py` |
| 5.6 | ⏸ | Acknowledge / Resolve action buttons + status workflow | 4 | UX/Redesign | MEDIUM | L | src+deploy | `chat.html`, `app.py`, `setup_alloydb.py` |
| 5.7 | ⏸ | Similar past tickets sidebar (last 7 days, same cat+region) | 4 | UX/Redesign | MEDIUM | M | src+deploy | `data_queries.py`, `chat.html` |
| 5.8 | ⏸ | Knowledge-base style "Likely root causes" checklist | 4 | UX/Redesign | MEDIUM | M | src+deploy | `prompts.py` or static map, `chat.html` |
| 5.9 | ⏸ | KPI strip header (tickets opened/resolved today) | 4 | UX/Redesign | LOW | M | src+deploy | `app.py`, `chat.html`, `data_queries.py` |
| 5.10 | ⏸ | Empty-state illustrations on data viewer tabs | 4 | UX/Redesign | LOW | S | src+deploy | `templates/*.html`, `style.css` |
| 5.11 | ✅ | Hero landing page + routing redesign (`/` → landing, `/app` → chat) | 2 | UX/Redesign | HIGH | M | src+deploy | `templates/landing.html` (NEW), `app.py`, `chat.html`, `style.css` |

**Counts:** Tier 1 = 7 (7 ✅ / 0 🔄 / 0 ⏸) · Tier 2 = 19 (13 ✅ / 1 🔄 / 5 ⏸) · Tier 3 = 2 (2 ✅ / 0 🔄 / 0 ⏸) · Tier 4 = 10 (0 ✅ / 2 🔄 / 8 ⏸) · **Original audit total = 38 (22 ✅ / 3 🔄 / 13 ⏸)**

**Effort budget:** Tier 1 = ~6h · Tier 2 = ~24h (incl. ~15h redesign + ~3.5h BYO-data foundation) · Tier 3 = ~6h · Tier 4 = ~16h. Realistic 5-day plan: Tier 1 + Tier 3 + UX-focused Tier 2 subset (token foundation + landing + timeline + badges + impact card + action chips) + BYO-data foundation (§2.7 env vars + §2.12 schema/seed) = ~30h work.

### Master table — Phase 9/10/11 extensions

Items below emerged during execution (post-2026-04-26 deploy) and are not in the original 2026-04-25 audit. Each shipped to production in the phase indicated. Per-item rationale + verification appears in the new Phase 9 / 10 / 11 sections below; the format here mirrors the master table for cross-referencing by ID.

| ID | Status | Item | Phase | Category | Severity | Effort | Auth | Files |
|---|:-:|---|---|---|---|---|---|---|
| 9.1 | ✅ | Heliodoron visual identity v1 (sand neutrals + warm-gold + 3 fonts) | 9 | UX | HIGH | M | src+deploy | `static/tokens.css`, `templates/base.html` |
| 9.2 | ✅ | Footer trim — remove "with Claude Code" link | 9 | Doc | LOW | XS | src+deploy | `templates/landing.html` |
| 9.3 | ✅ | Pandan accent unification (single hue for source/tool tags) | 9 | UX | MEDIUM | S | src+deploy | `static/style.css` |
| 9.4 | ✅ | 5s `asyncio.wait_for` per-attempt Vertex AI timeout (later 10s — see §9.14) | 9 | Robustness | HIGH | M | src+deploy | `telecom_ops/vertex_failover.py` |
| 9.5 | ✅ | Per-agent model selection (Flash-Lite upstream, Pro-preview synthesis) | 9 | Performance | HIGH | S | src+deploy | `telecom_ops/agent.py` |
| 9.6 | ✅ | Multi-continent region ladder (replace SE Asia with us-central1 / europe-west4 / asia-northeast1) | 9 | Robustness | HIGH | S | src+deploy | `telecom_ops/vertex_failover.py` |
| 9.7 | 🔄 | Pro-preview region-whitelist finding (RESOLVED via §9.13) | 9 | Finding | — | — | — | (n/a — diagnostic) |
| 9.8 | ✅ | Post-deploy doc polish (CLAUDE.md, README, REFINEMENT-PHASES.md, memory) | 9 | Doc | MEDIUM | S | doc | `CLAUDE.md`, `README.md`, `~/.claude/memory/*` |
| 9.9 | ⏸ | SSE streaming GIF in README (supersedes §2.11) | 9 | Doc | MEDIUM | M | doc | `README.md`, `docs/screenshots/` |
| 9.10 | ✅ | Header darker token (`--np-brand-deep` amber-bronze gradient anchor) | 9 | UX | MEDIUM | XS | src+deploy | `static/tokens.css`, `static/style.css` |
| 9.11 | ✅ | Done-state pandan unification (timeline entry single green family) | 9 | UX | MEDIUM | XS | src+deploy | `static/style.css` |
| 9.12 | ✅ | Customer-impact card extractor (recursive `JSON.parse`) + layout fix | 9 | UX | HIGH | S | src+deploy | `templates/chat.html` |
| 9.13 | ✅ | `MODEL_SYNTHESIS = MODEL_FAST` collapse — all 4 agents on Flash-Lite | 9 | Robustness | HIGH | XS | src+deploy | `telecom_ops/agent.py` |
| 9.14 | ✅ | `PER_ATTEMPT_TIMEOUT_S` 5s → 10s (Phase 11 false-positive fix) | 9 | Robustness | MEDIUM | XS | src+deploy | `telecom_ops/vertex_failover.py` |
| 10.1 | ✅ | Universal-tools refactor of toolbox (8 → 2 parameterized tools) | 10 | Architecture | HIGH | M | src+deploy | `tools.yaml` (toolbox repo) |
| 10.2 | ✅ | Native CDR tool optimization (parameterized `days_back`/`call_type`/`limit`) | 10 | Tool | HIGH | S | src+deploy | `telecom_ops/tools.py`, `prompts.py` *(later replaced by §11.1)* |
| 10.3 | ✅ | Richer seed data — 10 cities, 132 events, 500 CDRs | 10 | Data | HIGH | M | src+writes | `docs/seed-data/`, `prompts.py`, `data_queries.py` *(later grown by §11.2 / §11.3)* |
| 10.4 | ✅ | `setup_alloydb.py` multi-row INSERT VALUES (fix WAN executemany hang) | 10 | Tool | HIGH | S | src | `setup_alloydb.py` |
| 10.5 | ✅ | `ALLOWED_SEVERITIES` vocab bug fix (low/medium/high → critical/major/minor) | 10 | Tool | HIGH | XS | src+deploy | `netpulse-ui/data_queries.py` |
| 10.6 | ✅ | `netpulse-ui` redeploy + E2E smoke (Denpasar complaint, ticket #11) | 10 | Verification | MEDIUM | XS | deploy+test | (revision `netpulse-ui-00011-5ct`) |
| 11.1 | ✅ | AlloyDB AI NL2SQL on `cdr_analyzer` (replaces parameterized `query_cdr`) | 11 | Innovation | HIGH | L | src+deploy+DB | `scripts/setup_alloydb_nl.py` (NEW), `tools.yaml`, `tools.py`, `agent.py`, `prompts.py` |
| 11.2 | ✅ | BQ partition + cluster + 50k seed + `weekly_outage_trend` analytical tool | 11 | Innovation | HIGH | L | src+deploy+BQ writes | `scripts/setup_bigquery.py`, `scripts/generate_network_events.py` (NEW), `tools.yaml`, `prompts.py` |
| 11.3 | ✅ | 5k CDR seed with anchor-clustered failures (per-tower bias) | 11 | Data | MEDIUM | M | src+AlloyDB writes | `scripts/generate_call_records.py` (NEW), `setup_alloydb.py --seed` |
| 12.1 | ✅ | Vertex AI failover redesign — model ladder replaces region ladder | 12 | Robustness | HIGH | M | src+deploy | `telecom_ops/vertex_failover.py` |
| 12.2 | ✅ | Chip-reset for ADK 2-LLM-call-per-agent pattern | 12 | UX | MEDIUM | XS | src+deploy | `netpulse-ui/templates/chat.html` |
| 12.3 | ✅ | Failover chip separator `⤳` → `↪` (model-fallback semantic) | 12 | UX | LOW | XS | src+deploy | `netpulse-ui/templates/chat.html` |
| 12.4 | ✅ | Call-status pill on `call_records` viewer (matches severity / category pattern) | 12 | UX | MEDIUM | XS | src+deploy | `netpulse-ui/templates/call_records.html`, `static/style.css` |
| 12.5 | ✅ | Cloud Run deploy fix — Dockerfile build from project root (was Buildpacks from `netpulse-ui/`, stripped `telecom_ops/` from image) | 12 | Deploy | HIGH | XS | deploy | (no source change; deploy CWD + `--clear-base-image`) |

**Counts (extensions):** Phase 9 = 14 (12 ✅ + 1 🔄 + 1 ⏸) · Phase 10 = 6 (6 ✅) · Phase 11 = 3 (3 ✅) · Phase 12 = 5 (5 ✅) · **Extension total = 28 (27 ✅ / 1 ⏸ + 1 🔄)**.

**Combined catalog total:** 38 (original audit) + 28 (extensions) = **66 items** · **48 ✅ shipped** + **4 🔄 resolved-via** (§2.5 / §4.2 / §4.4 covered by other shipped items; §9.7 finding resolved by §9.13) + **14 ⏸ deferred** = **52 satisfied (79%)**.

---

## 1. Tier 1 — Demo-blocking polish

These are issues a judge **will** notice within 5 minutes. Resolve before any further work.

### 1.1 Surface tool errors as chat card error state

**Why it matters:** During the live SSE inspection, every card transitioned `waiting → running → done`. But if a tool call fails (e.g. AlloyDB timeout, BigQuery 403, MCP toolbox connection refused) the current frontend leaves the card in `running` indefinitely. A judge hitting a transient error sees a stuck demo with no signal that anything is wrong.

**Files:** `netpulse-ui/templates/chat.html` (lines ~193-206 — the `npHandle` event dispatch), `netpulse-ui/agent_runner.py` (event emission for tool_response).

**Change:**
1. In `agent_runner.py`, when emitting a `tool_response` event, inspect `result` for `{"status":"error",...}` or any non-success shape. If error, also enqueue an `error` event with `agent`, `tool`, and `message`.
2. In `chat.html` `npHandle`, add a case for `type === 'error'`: mark the corresponding card with an `np-error` class, show the error message inline, and stop the spinner.
3. Add a `.np-card.np-error` CSS rule (red border, error icon) in `static/style.css`.

**Test:** Locally, monkey-patch `query_cdr` to raise an exception, run a chat query, confirm the `cdr_analyzer` card shows error state and downstream cards mark "Skipped due to upstream error" (or similar).

---

### 1.2 Disable Investigate button + spinner during request

**Why it matters:** Right now the button stays clickable while SSE is streaming. Double-clicks spawn parallel async generators. Judges may click twice if the first click "feels slow" (especially during the 7s cold start).

**Files:** `netpulse-ui/templates/chat.html` (`npSubmit` function, button id `np-btn`).

**Change:**
```javascript
function npSubmit() {
  var input = document.getElementById('np-input');
  var btn = document.getElementById('np-btn');
  var query = (input.value || '').trim();
  if (!query) { input.focus(); return; }
  btn.disabled = true;
  btn.textContent = 'Investigating…';
  // ... existing fetch ...
}
// On 'complete' or 'error' event:
function npFinish() {
  btn.disabled = false;
  btn.textContent = 'Investigate';
}
```

**Test:** Click Investigate, confirm button greys out and shows "Investigating…", returns to normal on completion or error.

---

### 1.3 Client-side empty/whitespace input validation

**Why it matters:** Today an empty submit triggers a server-side 400 with no UI feedback — a confusing dead click for the judge.

**Files:** `netpulse-ui/templates/chat.html`.

**Change:** see `npSubmit` snippet in §1.2 — the early-return on empty query handles this. Also add a placeholder hint and a `maxlength` attribute (~2000 chars, paired with §2.6 server-side cap).

---

### 1.4 Tighten `network_investigator` output to enumerate ALL events

**Why it matters:** Live inspection caught the agent returning **9 events** from BigQuery but summarizing only **4** in user-facing text. The downstream `response_formatter` then references only those 4 in the ticket. A judge who clicks the Network Events data viewer tab will see 9 Jakarta events listed there, vs 4 in the chat — visible inconsistency.

**Files:** `telecom_ops/prompts.py` (the `NETWORK_INVESTIGATOR_INSTRUCTION` block).

**Change:** Replace the freeform "Summarize findings in 3-6 bullet points" with an explicit per-event row format and remove the count cap:
```
For EACH event returned by the tool (do not omit any), emit one bullet in this exact format:
- [EVENT_ID] [EVENT_TYPE] [SEVERITY] [REGION] [STARTED_AT] · affected=[N] · [DESCRIPTION]

If more than 8 events are returned, emit all of them but rank by severity then started_at (most recent critical/major first).
```

**Test:** Re-run the same Jakarta complaint, confirm the chat card now lists all 9 events. Confirm the response_formatter ticket includes the full set in `related_events`.

---

### 1.5 Validate `category` enum in `save_incident_ticket`

**Why it matters:** The Response Formatter LLM can hallucinate categories (`"networking_issue"` instead of `"network"`). Today these get inserted as-is into AlloyDB. Garbage tickets pollute the data viewer tab and break category-based filtering for any future feature (e.g., the "similar past tickets" sidebar in §5.7).

**Files:** `telecom_ops/tools.py` (`save_incident_ticket` function).

**Change:**
```python
VALID_CATEGORIES = {"billing", "network", "hardware", "service", "general"}

def save_incident_ticket(tool_context, category, region, description, related_events, cdr_findings, recommendation):
    if category not in VALID_CATEGORIES:
        return {"status": "error", "message": f"Invalid category {category!r}; must be one of {sorted(VALID_CATEGORIES)}"}
    # ... existing insert ...
```

**Test:** Run a complaint, then manually call the tool with an invalid category — confirm the error path triggers card error state from §1.1.

---

### 1.6 Set `minScale=1` on `netpulse-ui` (kill 7s cold start)

**Why it matters:** Audit measured 7.2s for the first hit (HTTP 302 → /chat). Warm hits = 0.4s. The judge's first impression is a 7-second blank tab. With `minScale=1`, one instance stays warm.

**Cost impact:** ~$5/month on trial billing. The `018C72-...` trial credit holds $1,000 with 11 months remaining. Negligible.

**Auth required:** Cloud Run config write — Freeze A boundary. **Needs explicit user confirmation.**

**Command (when authorized — user runs):**
```bash
gcloud run services update netpulse-ui \
  --region us-central1 \
  --project plated-complex-491512-n6 \
  --min-instances=1
```

**Test:** After update, hit the URL three times in succession; first hit should also be ~0.4s.

---

### 1.7 Raise `maxScale` on `network-toolbox` from 3 → 10

**Why it matters:** `network-toolbox` is on `maxScale=3`. If multiple judges hit the chat in parallel (unlikely but possible during a live demo with panel + spectators), each chat session opens its own MCP toolbox connection — three concurrent investigations could starve the fourth.

**Cost impact:** Pay-per-use. Trivial.

**Auth required:** Cloud Run config write — Freeze A boundary. **Needs explicit user confirmation.**

**Command (when authorized):**
```bash
gcloud run services update network-toolbox \
  --region us-central1 \
  --project plated-complex-491512-n6 \
  --max-instances=10
```

---

## 2. Tier 2 — Quality + storytelling polish

Items in this tier elevate the demo from "works" to "production-grade". UI redesign items (§5.1–5.5) are the highest-impact subset and live under §5 below.

### 2.1 SSE heartbeat every 5s

**Why:** During a 30s LLM call (no tool activity), the SSE stream is silent. Browser/proxy may close idle connections. Send a `:heartbeat\n\n` comment line every 5s.

**Files:** `netpulse-ui/agent_runner.py` (queue drain loop), `netpulse-ui/app.py` (SSE generator).

**Change:** Wrap `q.get(timeout=5)` and on `queue.Empty`, yield `: heartbeat\n\n` instead of breaking. Browsers ignore comment lines but the connection stays alive.

---

### 2.2 Pagination context on data viewer tabs

**Why:** All three data viewer queries silently `LIMIT 200`. If a user filters and gets exactly 200 rows, they don't know if more exist.

**Files:** `netpulse-ui/data_queries.py` (returns `QueryResult`), templates that render the tables.

**Change:** Add `total_count` field to `QueryResult` (run a second `COUNT(*)` with the same WHERE clause, no limit). Render "Showing 1–200 of N (filtered)" above the table. Optionally add a "Load more" button that re-queries with `OFFSET 200`.

---

### 2.3 Form labels + ARIA attributes on filter selects

**Why:** Bare `<select>` elements with no `<label>` fail basic accessibility. Judges from enterprise-product backgrounds (likely) will spot this.

**Files:** `netpulse-ui/templates/network_events.html`, `cdr_records.html`, `tickets.html` filter forms.

**Change:** Wrap each select in a `<label>` or use `aria-label`. Group with `<fieldset>` if multiple filters.

---

### 2.4 Error classification (network/LLM/DB) in card error state

**Why:** Builds on §1.1 — once errors surface, classify them so the user understands transience vs structural.

**Files:** `netpulse-ui/agent_runner.py`, `chat.html`.

**Change:** In the error-event emission, set `error_type` to one of `network|llm|database|tool_invalid`. Card displays icon + "Try again" button for `network|llm` (transient) but not for `tool_invalid` (programming error). Re-run via `npSubmit(originalQuery)`.

---

### 2.5 Region whitelist in `query_cdr`

**Status update (2026-04-27): 🔄 RESOLVED via §11.1.** The `query_cdr` Python function was deleted in Phase 11; the replacement (`query_cdr_nl` via AlloyDB AI NL2SQL) validates region values through the `city_name` concept-type binding registered in `setup_alloydb_nl.py:associate_region_concept`. AlloyDB AI rejects unknown city names structurally before SQL is generated — a stronger guarantee than a Python whitelist would have been. **No separate work needed.**

**Original rationale (preserved for context):**

**Why:** A typo like `region="Jakarti"` returns 0 rows silently. Confusing.

**Files:** `telecom_ops/tools.py` (`query_cdr`).

**Change:**
```python
ALLOWED_REGIONS = {"Jakarta", "Surabaya", "Bandung", "Medan", "Semarang"}
if region and region not in ALLOWED_REGIONS:
    logger.warning("query_cdr: region %r not in allowed list", region)
    return {"status":"error", "message": f"Unknown region {region!r}"}
```

---

### 2.6 Complaint length cap + sanitization

**Why:** `tools.py:57` stores raw complaint into session state. A 10KB paste (or accidental clipboard dump) will bloat the LLM prompt context and could blow the token budget.

**Files:** `telecom_ops/tools.py` (`classify_issue`).

**Change:**
```python
complaint = (complaint or "").strip()[:2000]
if not complaint:
    return {"status":"error", "message":"Complaint text is empty"}
```

---

### 2.7 Make hardcoded URLs/IDs env-driven

**Why:** `telecom_ops/tools.py:14` hardcodes the toolbox URL with the project number `486319900424` baked in. If a judge wants to fork the repo and run it in their own GCP project, nothing works. Same issue in `netpulse-ui/data_queries.py:24` (project ID default).

**Files:** `telecom_ops/tools.py`, `netpulse-ui/data_queries.py`, `netpulse-ui/templates/chat.html` and `network_events.html` (BigQuery dataset path strings).

**Change:**
```python
TOOLBOX_URL = os.environ["TOOLBOX_URL"]  # required, no fallback
GCP_PROJECT = os.environ["GOOGLE_CLOUD_PROJECT"]
```
Pass `GCP_PROJECT` to Jinja templates via `render_template(..., gcp_project=GCP_PROJECT)`. Add `TOOLBOX_URL` to the deployed env-vars set.

---

### 2.8 Structured logs with session correlation ID

**Why:** Two simultaneous chat sessions = interleaved logs in Cloud Run, impossible to debug. Judges who SSH into logs will see chaos.

**Files:** `netpulse-ui/agent_runner.py`, `telecom_ops/tools.py`.

**Change:** Generate a UUID per request in `app.py`, propagate to `run_agent(query, session_id=...)`, include in every log statement: `logger.info("session=%s tool=classify_issue category=%s", session_id, category)`.

---

### 2.9 "Quick Demo" section in README

**Why:** README jumps straight to architecture. A judge skimming the README in 90 seconds needs a "click here, type this, see this" path.

**Files:** `README.md`.

**Change:** Insert after the "Try it live" link:
```markdown
## Quick demo (90 seconds)

1. Open https://netpulse-ui-486319900424.us-central1.run.app/
2. In the chat, type: `Major dropped calls in Surabaya during morning peak`
3. Watch the four-stage agent pipeline animate (classifier → network → CDR → ticket).
4. The Incident Report card shows the auto-generated NOC ticket — including affected cell towers, related network events, and a recommended NOC action.
5. Switch to the Tickets tab to see the saved ticket persisted in AlloyDB.
```

---

### 2.10 Architectural callouts above mermaid diagram

**Why:** The mermaid diagram is clear but neutral. A side-by-side competing submission with annotations beats one without.

**Files:** `README.md`.

**Change:** Add a 3-bullet callout box above the diagram highlighting (a) APAC region pin / failover ladder, (b) MCP Toolbox in front of BigQuery as a Cloud-Run-friendly pattern, (c) async-to-sync bridge for incremental SSE.

---

### 2.11 SSE streaming GIF / animated screenshot

**Why:** Static screenshots can't convey the "watch the pipeline build live" effect. A 5-second animated GIF is the killer demo asset.

**Files:** `README.md`, `docs/screenshots/`.

**Change:** Record a short screen capture of one chat run (use macOS Cmd+Shift+5 with .mov → ffmpeg to .gif, or a Linux equivalent). Place in `docs/screenshots/pipeline.gif`, embed in README near the architecture section.

---

### 2.12 Schema contract + env-driven dataset names + reproducible seed pipeline (BYO-data foundation)

**Why this matters — closes a real gap, not just a feature ask.**

Audit-confirmed reproducibility gap: of the 3 tables NetPulse depends on, only **1 of 3** is provisioned by repo-tracked code:

| Table | Current provisioning | In repo? |
|---|---|---|
| `incident_tickets` | `setup_alloydb.py` (idempotent `CREATE TABLE IF NOT EXISTS`) | ✅ Yes |
| `call_records` (AlloyDB) | Out-of-repo — likely manual `psql` during the build | ❌ No DDL, no seed |
| `network_events` (BigQuery) | Out-of-repo — `bq load` or console upload during the build | ❌ No schema, no seed |

A fresh clone of this repo cannot recreate the demo state. Only the original author can — from local memory of the build. This is a real bug, not a hypothetical SaaS feature.

The fix simultaneously **closes the reproducibility gap** AND **gives NetPulse a credible "Bring Your Own Data" story** for the deck — without building actual multi-tenant SaaS (which is the 8-12 day Variant C path explicitly out of scope).

**Three pieces of work, one PR:**

#### a) Env-driven dataset/table names (~30 min)

Replace hardcoded names with env-var-driven ones. Defaults preserve current behavior; overrides allow pointing at custom datasets.

```python
# telecom_ops/tools.py
AL_CALL_TABLE   = os.environ.get("AL_CALL_TABLE",   "call_records")
AL_TICKET_TABLE = os.environ.get("AL_TICKET_TABLE", "incident_tickets")
# ...
sql = f"... FROM {AL_CALL_TABLE} WHERE 1=1"
sql = f"INSERT INTO {AL_TICKET_TABLE} ..."

# netpulse-ui/data_queries.py
BQ_DATASET       = os.environ.get("BQ_DATASET",       "telecom_network")
BQ_NETWORK_TABLE = os.environ.get("BQ_NETWORK_TABLE", "network_events")
AL_CALL_TABLE    = os.environ.get("AL_CALL_TABLE",    "call_records")
AL_TICKET_TABLE  = os.environ.get("AL_TICKET_TABLE",  "incident_tickets")
```

Touches `telecom_ops/tools.py` (lines ~83, 139) and `netpulse-ui/data_queries.py` (lines 25-26, 173, 216).

**Honest scope:** This parameterizes the *names*, not the *columns*. Agents and queries still assume specific column names (`region`, `call_status`, `event_type`, `severity`, etc.). A user bringing their own data must match the documented schema contract — see (b).

#### b) Schema contract documentation (~30 min)

NEW: `docs/SCHEMA.md` — the canonical "what NetPulse expects" contract. Sketch:

```markdown
# NetPulse data contract

NetPulse is dataset-driven. Point environment variables at any dataset
matching this contract and the agents work against your data.

## BigQuery: <BQ_DATASET>.<BQ_NETWORK_TABLE>

| Column | Type | Required | Notes / example |
|---|---|---|---|
| event_id           | STRING    | yes | "EVT001" |
| event_type         | STRING    | yes | one of: outage, degradation, restoration, maintenance |
| region             | STRING    | yes | one of: Jakarta, Surabaya, Bandung, Medan, Semarang |
| severity           | STRING    | yes | one of: critical, major, minor |
| description        | STRING    | yes | "Major fiber cut affecting central Jakarta" |
| started_at         | TIMESTAMP | yes | 2026-03-25 08:00:00 UTC |
| resolved_at        | TIMESTAMP | no  | NULL while ongoing |
| affected_customers | INT64     | yes | 45000 |

## AlloyDB: <AL_CALL_TABLE>

| Column | Type | Required | Notes |
|---|---|---|---|
| call_id           | SERIAL PRIMARY KEY | yes | |
| caller_number     | TEXT      | yes | "08121234001" |
| receiver_number   | TEXT      | yes | "08131234001" |
| call_type         | TEXT      | yes | one of: voice, data |
| duration_seconds  | INT       | yes | 0 for failed/dropped calls |
| data_usage_mb     | NUMERIC   | yes | 0 for voice calls |
| call_date         | TIMESTAMP | yes | |
| region            | TEXT      | yes | matches network_events.region values |
| cell_tower_id     | TEXT      | yes | "JKT-001" etc. |
| call_status       | TEXT      | yes | one of: completed, dropped, failed |

## AlloyDB: <AL_TICKET_TABLE>

(NetPulse-written; see existing setup_alloydb.py DDL.)
```

#### c) Reproducible seed pipeline (~2-3h)

NEW files:
- `docs/seed-data/network_events.csv` — extract today's 30 BQ rows
- `docs/seed-data/call_records.csv` — extract today's 60 AlloyDB rows
- `docs/seed-data/incident_tickets.csv` — optional 5-10 sample tickets for testing
- `scripts/setup_bigquery.py` — creates BQ dataset + table + loads `network_events.csv`
- `scripts/setup_byo.sh` — orchestrator: runs `setup_alloydb.py` and `setup_bigquery.py` in sequence

MODIFY:
- `setup_alloydb.py` — extend to also create `call_records` table (currently missing!) and optionally load `docs/seed-data/call_records.csv` when `--seed` flag passed.

Resulting `setup_byo.sh` API:
```bash
# Bootstrap a fresh GCP project against the NetPulse data contract
export GOOGLE_CLOUD_PROJECT=customer-project
export DATABASE_URL=postgresql+pg8000://...
export BQ_DATASET=customer_telecom        # optional override
bash scripts/setup_byo.sh --seed
```

#### d) README "BYO data" section (~15 min)

Single subsection in README.md:

```markdown
## Bring your own data

NetPulse is dataset-driven. Match the [data contract](docs/SCHEMA.md),
override the env vars (`BQ_DATASET`, `BQ_NETWORK_TABLE`, `AL_CALL_TABLE`,
`AL_TICKET_TABLE`), and the agents work against your infrastructure.

Bootstrap a fresh GCP project from the included sample data:
\`\`\`bash
export GOOGLE_CLOUD_PROJECT=your-project
export DATABASE_URL=postgresql+pg8000://...
bash scripts/setup_byo.sh --seed
\`\`\`

Multi-tenant SaaS UI (login, per-tenant dataset isolation) is roadmapped
for v2; the data layer is already deployable against any compatible infra.
```

**Files (NEW):** `docs/SCHEMA.md`, `docs/seed-data/network_events.csv`, `docs/seed-data/call_records.csv`, `docs/seed-data/incident_tickets.csv`, `scripts/setup_bigquery.py`, `scripts/setup_byo.sh`

**Files (MODIFY):** `setup_alloydb.py` (add `call_records` DDL + optional seed loader), `telecom_ops/tools.py` (env-driven `AL_CALL_TABLE`, `AL_TICKET_TABLE`), `netpulse-ui/data_queries.py` (env-driven `BQ_DATASET`, `BQ_NETWORK_TABLE`, `AL_CALL_TABLE`, `AL_TICKET_TABLE`), `README.md` (BYO section).

**Effort:** M = ~3.5h total
- Env-driven names: 30 min
- `docs/SCHEMA.md`: 30 min
- Extract seed data from current BQ + AlloyDB into CSVs (read-only `bq query` + `psql \copy`): 1h
- Author `scripts/setup_bigquery.py` + extend `setup_alloydb.py`: 1h
- `scripts/setup_byo.sh` + README section: 30 min

**Auth:** src+deploy. Seed extraction is read-only against the deployed infra (Freeze A allows). The bootstrap scripts only mutate destinations the user explicitly supplies — they do NOT touch the protected hackathon datasets.

**Synergy:** Pairs with §2.7 (env-driven URLs) — both are config-portability work; do them in the same PR. Together they make NetPulse fully relocatable: a fresh `gcloud run deploy` with the right env vars and a `setup_byo.sh --seed` produces a working stack against any GCP project.

**Risk to Freeze A:** None. Source changes are additive (env-var defaults preserve current behavior). Seed extraction reads from the current BQ + AlloyDB without modification. Bootstrap scripts target whatever destination the user supplies — by default, against a fresh non-protected project.

**Story payoff for the deck (one slide):**

> "NetPulse v1 was a single-tenant demo with manual data provisioning.
> v1.1 ships a documented schema contract, complete sample seed data,
> and a one-line bootstrap (`scripts/setup_byo.sh`) that provisions any
> GCP project to run NetPulse end-to-end. The data layer is now deployable
> against any compatible infrastructure; multi-tenant UI roadmapped for v2."

Two messages in one: closing a real reproducibility bug AND signalling SaaS readiness.

---

## 3. Tier 3 — Vertex AI region failover (anchor innovation)

This is the headline technical refinement. **Full implementation plan in `PLAN-vertex-region-failover.md`** — the summary below is for cross-referencing inside this audit.

### 3.1 Region failover (`global` default + ranked ladder)

**Goal:** Switch Vertex AI inference default from `asia-southeast1` (static pin) to `global` (Google's multi-region routing pool). On `RESOURCE_EXHAUSTED` 429, fail over through `asia-southeast2 → asia-southeast1 → us-central1`.

**Why it matters for Top 10:** Most submissions will hit the same `RESOURCE_EXHAUSTED` issue if they tested in `us-central1`. NetPulse's ability to articulate "we identified Vertex AI Dynamic Shared Quota as a class of problem and built a runtime failover" is a defensible technical narrative — the kind of story that distinguishes a thoughtful submission from a vibe-coded one.

**Files:**
- NEW: `telecom_ops/vertex_failover.py` (~80 lines: `RegionFailoverGemini` subclass of ADK `Gemini`).
- MODIFY: `telecom_ops/agent.py` — each `LlmAgent` gets its own `RegionFailoverGemini(model="gemini-2.5-flash")` instance for per-agent failover state.
- MODIFY: `telecom_ops/.env` — `GOOGLE_CLOUD_LOCATION=global`.
- MODIFY: `README.md` deploy snippet, `CLAUDE.md` "Non-obvious choices" paragraph (replace the `asia-southeast1` pin note).

**Region ranking rationale:**

| # | Region | Reason |
|---|---|---|
| 1 | `global` | Multi-region routing pool, broadest capacity. Witnessed working as default in `heliodoron-interio` production. |
| 2 | `asia-southeast2` (Jakarta) | Geographic optimum for Indonesian traffic (15-30ms from Surabaya), lower commercial contention than Singapore. |
| 3 | `asia-southeast1` (Singapore) | The original verified DSQ fix — proven to work for this exact workload. |
| 4 | `us-central1` (Iowa) | Last resort. Default Cloud Run region (best co-location latency) but the original failing region. |

**Verification (4 layers):**
1. Unit-level: `_is_quota_error` matcher table in `if __name__ == "__main__":` — `RESOURCE_EXHAUSTED`, `429`, `QUOTA` substrings should match; `INVALID_ARGUMENT`, `PERMISSION_DENIED` should not.
2. Forced failover: monkey-patch `RANKED_REGIONS = ("us-east-99", "global")` to confirm the loop walks past the bad region.
3. End-to-end via Flask UI: run a chat, confirm logs show `Vertex AI attempt: region=global` for each agent.
4. Post-deploy curl on the four submitted URLs.

**Implementation order (8 steps):** see `PLAN-vertex-region-failover.md` § "Implementation order".

**Auth required:** Source changes within normal scope. The Cloud Run redeploy with `--update-env-vars=GOOGLE_CLOUD_LOCATION=global` is the Freeze A boundary — user runs that step.

---

### 3.2 Per-attempt region telemetry in chat cards

**Why it matters:** The failover is currently invisible plumbing. Surfacing the active region as a chat-card label ("via global", "via asia-southeast2 ⤳ failover") turns it into a demo moment — judges *see* the resilience instead of reading about it.

**Files:** `netpulse-ui/agent_runner.py` (extend `AgentEvent` with optional `region` field), `chat.html` (render region badge in card header).

**Change:** Capture the active region from `RegionFailoverGemini` (e.g., a class attribute updated per attempt). Emit on the `agent_start` event. Render as a small badge: `🌐 via global` (success on first try) or `🌐 via global ⤳ asia-southeast2` (after failover).

**Dependency:** §3.1 must land first.

---

## 4. Tier 4 — Brainstorming queue (defer / discuss before committing)

Items here are scoped possibilities, not committed work. Promoted to higher tiers only by explicit user direction.

### 4.1 Parallelize `network_investigator` + `cdr_analyzer`

**Why:** They don't depend on each other — both only consume `{category}` and `{region}` from the classifier. `SequentialAgent` runs them serially (~30s wall-clock); ADK `ParallelAgent` could cut to ~20s.

**Why deferred:** Architectural change. Risk of subtle ADK state-passing edge cases. Belongs in post-Top-10 work.

---

### 4.2 Idempotency keys on `save_incident_ticket`

**Status update (2026-04-27): 🔄 RESOLVED via §3.1 / §9.4 / §9.14 + §1.2.** The original concern was retry-induced duplicate ticket writes. Two shipped guarantees make this structurally impossible: (a) the Vertex AI failover wrapper only retries *before* the underlying call returns success — `asyncio.wait_for` cancels the in-flight request on timeout (§9.4 / §9.14) and the next region attempt fires a fresh call, so a successful `save_incident_ticket` write can never be re-issued; (b) §1.2 disables the Investigate button during a request, eliminating the user-side double-click case. **No separate work needed.**

**Original rationale (preserved for context):**

**Why:** The failover plan currently retries pre-tool, so duplicate writes are impossible. But if streaming retries are ever enabled (out of scope today), a UUID idempotency column would prevent duplicates.

**Why deferred:** No present risk; preventive only.

---

### 4.3 Minimal pytest suite for `tools.py`

**Why:** Confirmed via `find` — repo has zero test files. A 5-test pytest suite (one per tool happy + one sad path) would establish a "we have tests" signal in the README.

**Why deferred:** Judges in a 5-min demo won't run tests. Useful for credibility but low immediate signal.

---

### 4.4 Demo seed panel — clickable example complaints

**Status update (2026-04-27): 🔄 RESOLVED via §5.11.** The hero landing page ships launch chips that use `?seed=...&autorun=1` query handoff to pre-populate `/app` with a complaint and (optionally) auto-submit. This is functionally identical to the originally-planned in-app seed panel, with a better entry point: judges meet the chips before reaching the workspace, removing the need to type or navigate. **No separate in-app panel needed.**

**Original rationale (preserved for context):**

**Why:** 3-4 pre-populated example complaints displayed as clickable cards above the input. Judges can one-click a demo without typing.

**Why considered:** High demo polish, low effort. Good Tier-4-to-Tier-2 promotion candidate if time permits.

**Files:** `netpulse-ui/templates/chat.html`, optional new `netpulse-ui/seed_complaints.py`.

**Sketch:**
```html
<div class="np-seeds">
  <button onclick="npSeed('Major dropped calls in Surabaya')">Surabaya dropped calls</button>
  <button onclick="npSeed('Billing dispute in Jakarta')">Jakarta billing</button>
  <button onclick="npSeed('Hardware failure in Medan')">Medan hardware</button>
</div>
```

---

### 4.5 Live ticket counter strip on chat page

**Why:** Header strip showing "12 tickets opened today, 8 resolved" turns the AlloyDB write side into a visible feedback loop. Borrowed from PagerDuty's incident counter UI (see §5.9).

**Why deferred:** Requires a `status` workflow column on `incident_tickets` (overlaps with §5.6).

---

## 5. UI redesign audit — ServiceNow + PagerDuty inspiration → NetPulse adaptations

The current chat UI is a clean 4-card horizontal pipeline followed by a single ticket card. It works, but it doesn't resemble a real telecom NOC operator's daily tool — and it has no front door. This section draws from **ServiceNow ITSM** (the de-facto enterprise incident management platform) and **PagerDuty** (the incident response specialist) — both direct analogues to what NetPulse is automating. **§5.11 additionally defines a hero landing page** that gates entry to the app and explains the product before judges interact with it.

### 5.0 Reference platform pattern extraction

**ServiceNow ITSM** (Incident Management module — what telco NOC operators actually use today):

| Pattern | Description | Why it works |
|---|---|---|
| Three-pane workspace | Navigator (left) · List (center) · Form (right) — or List → Form drill-down | Operators see the queue and the active incident at once |
| Activity Stream | Chronological timeline on the incident form: events, comments, automation steps | Single source of truth for "what happened when" |
| Related Lists | Sub-tables under the form: Affected CIs, Related Tasks, Approvals, KB articles | Surfaces relevant context without leaving the page |
| Status workflow visualization | New → Assigned → In Progress → Resolved → Closed (often shown as a stepper) | Operators always know where the incident is in its lifecycle |
| Priority/Severity badges | Color-coded chips (red P1 · orange P2 · yellow P3 · green P4) | Pre-attentive scanning of the incident queue |
| Quick action ribbon | Save / Update / Resolve / Close / Assign — large persistent buttons | Reduces clicks for the 80% common operations |
| Knowledge Base auto-suggest | KB articles auto-matched by category + symptoms | Operator gets templated diagnostic checklists in-context |
| SLA timer indicator | Countdown to breach with color escalation | Pressure / urgency signal |

**PagerDuty Incident Response** (the on-call incident management standard):

| Pattern | Description | Why it works |
|---|---|---|
| Incident timeline | Vertical chronological log: detection · ack · escalation · resolution · postmortem hooks | Reads like a story; obvious narrative |
| Affected services + impact | "Service X is degraded · Y customers affected · Z minutes since onset" prominently at top | Operators know stakes at a glance |
| Responder card | "Acknowledged by Alice 2 min ago" — who's on it and when | Coordination without separate chat |
| Runbook link | One-click access to the playbook for this alert type | Reduces mean time to repair |
| Acknowledge / Resolve actions | Two large buttons, always visible | Two-state simplification — no fiddly status menus |
| Status page integration | Incident status auto-publishes to subscriber-facing page | Outward-facing visibility loop |
| Incident grouping | Related alerts auto-group into a parent incident | Reduces alert fatigue |

---

### 5.0a Design token foundation (curated from `heliodoron-ui-identity`)

**Why this comes first:** Every §5 redesign item consumes design primitives (spacing, color, typography, radius, shadow, motion). Without an explicit token layer, each new component re-invents hardcoded values, drift accumulates, and visual coherence collapses. Adopting a token foundation now is cheaper than retrofitting later — and it's the single biggest "feels production-grade" signal a judge can scan in 3 seconds.

**Source:** `~/projects/heliodoron-ui-identity/tokens/heliodoron.css` (private design-system identity kit, commit `0923dfb`, snapshot 2026-04-25). Heliodoron was extracted from anthropic.com's structural patterns with distinct visual voice (warm OKLCH neutrals + Indonesian botanical/textile-anchored accent palette). The token *architecture* — how primitives nest into semantic mappings — is reusable; the brand-specific palette is not.

**Approach: hybrid — copy structural tokens verbatim, author NetPulse-specific palette + semantic mappings.**

| Category | Action | Rationale |
|---|---|---|
| Spacing (4px base, fluid 28+) | **Copy verbatim** | Generic utility; structure is universal |
| Layout (container, gutter, text column) | **Copy verbatim** | Industry-standard values; no brand signal |
| Radius scale (4/8/12/16/pill) | **Copy verbatim** | Craft convention, not identity |
| Shadow (3-tier "presence not depth") | **Copy verbatim** | Methodology is open; alpha ceiling proven (1–15%) |
| Motion (quartic + expo easing) | **Copy verbatim** | Mathematical primitives; Anthropic-derived |
| Breakpoints (Tailwind defaults 640/768/1024/1280/1536) | **Copy verbatim** | Industry standard |
| Typography scale + weights + leading + tracking | **Copy verbatim** | Numbers are reusable across brands |
| Typography families (Geist + Newsreader + JetBrains Mono) | **Adopt or substitute** | All three are OFL/free; safe to use as-is, or substitute (Inter / Georgia / Courier) per NetPulse preference |
| Color palette (sand + Indonesian accents) | **Author fresh** | Brand-specific — NetPulse needs its own neutrals + accent set |
| Semantic color tokens (`--text-*`, `--surface-*`, `--border-*`) | **Copy names + structure, remap values** | Names universally meaningful; values point to NetPulse palette |

#### Tokens to lift verbatim — drop into `netpulse-ui/static/tokens.css`

```css
/* netpulse-ui/static/tokens.css
 *
 * Curated from heliodoron-ui-identity/tokens/heliodoron.css (commit 0923dfb).
 * Structural tokens (spacing, radius, shadow, motion, layout, type scale) lifted
 * verbatim. Color palette and semantic mappings authored fresh for NetPulse.
 * Canonical source for future updates: ~/projects/heliodoron-ui-identity/
 */

:root {
  /* ─── Spacing (4px base; fluid above space-5) ─── */
  --space-1:  0.25rem;
  --space-2:  0.5rem;
  --space-3:  0.75rem;
  --space-4:  1rem;
  --space-5:  1.5rem;
  --space-6:  clamp(1.75rem, 2vw + 1rem, 2rem);
  --space-7:  clamp(2rem, 2.5vw + 1rem, 2.5rem);
  --space-8:  clamp(2.25rem, 3vw + 1rem, 3rem);
  --space-9:  clamp(2.5rem, 4vw + 1rem, 4rem);
  --space-10: clamp(3rem, 5vw + 1rem, 5rem);
  --space-11: clamp(3.5rem, 6vw + 1rem, 6rem);

  /* Section-level spacing (page rhythm) */
  --section-sm:  clamp(2rem, 4vw + 1rem, 4rem);
  --section-md:  clamp(3rem, 6vw + 1rem, 6rem);
  --section-lg:  clamp(5rem, 10vw + 1rem, 10rem);
  --section-top: clamp(6rem, 12vw + 1rem, 12rem);

  /* ─── Layout ─── */
  --container-max:    1400px;
  --page-margins:     clamp(16px, 3vw, 32px);
  --gutter:           24px;
  --text-column-max:  640px;
  --media-max-width:  880px;
  --media-max-height: 560px;
  --header-height:    64px;

  /* ─── Radius ─── */
  --radius-xs:   4px;
  --radius-sm:   8px;
  --radius-md:   12px;
  --radius-lg:   16px;
  --radius-pill: 1000px;

  /* ─── Shadow (presence, not depth — alpha ceiling 15%) ─── */
  --shadow-soft:   0 2px 2px rgba(0,0,0,0.01),
                   0 4px 4px rgba(0,0,0,0.02),
                   0 16px 24px rgba(0,0,0,0.04);
  --shadow-medium: 0 4px 24px rgba(0,0,0,0.05);
  --shadow-modal:  0 12px 24px rgba(0,0,0,0.15);

  /* ─── Motion (Anthropic-derived quartic + expo) ─── */
  --ease-in-quart:     cubic-bezier(0.895, 0.030, 0.685, 0.220);
  --ease-out-quart:    cubic-bezier(0.165, 0.840, 0.440, 1.000);
  --ease-in-out-quart: cubic-bezier(0.770, 0.000, 0.175, 1.000);
  --ease-in-out-expo:  cubic-bezier(1.000, 0.000, 0.000, 1.000);
  /* Durations: set per-component, typical UI 200–400ms */

  /* ─── Typography — sizes (fluid display, fixed body/detail) ─── */
  --type-display-hero: clamp(3rem, 4vw + 1rem, 5rem);
  --type-display-1:    clamp(2rem, 2vw + 1rem, 3rem);
  --type-display-2:    clamp(1.75rem, 1vw + 1rem, 2rem);
  --type-h1:           clamp(1.75rem, 1vw + 1rem, 2.25rem);
  --type-h2:           clamp(1.5rem, 0.5vw + 1rem, 1.75rem);
  --type-h3:           1.25rem;
  --type-h4:           1.0625rem;
  --type-body-lg:      1.25rem;
  --type-body:         1.0625rem;
  --type-body-sm:      0.9375rem;
  --type-detail:       0.875rem;
  --type-detail-sm:    0.75rem;
  --type-mono:         0.9375rem;

  --weight-regular:  400;
  --weight-medium:   500;
  --weight-semibold: 600;
  --weight-bold:     700;

  --leading-tight:   1.0;
  --leading-display: 1.1;
  --leading-heading: 1.2;
  --leading-body:    1.4;
  --leading-dense:   1.55;

  --tracking-tight: -0.015em;
  --tracking-body:   0em;
  --tracking-ui:    -0.0025em;

  /* ─── Typography — families (substitute if desired) ─── */
  /* Heliodoron uses Geist + Newsreader + JetBrains Mono (all OFL/Apache).
   * For NetPulse, either reuse those or substitute with system stacks below. */
  --font-sans:  'Geist Variable', 'Geist', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --font-serif: 'Newsreader Variable', 'Newsreader', Georgia, 'Times New Roman', serif;
  --font-mono:  'JetBrains Mono Variable', 'JetBrains Mono', ui-monospace, 'SF Mono', Menlo, monospace;
}

/* Breakpoints (Tailwind-default px values; for use in @media queries) */
/*  sm  640px   md  768px   lg 1024px   xl 1280px   2xl 1536px */
```

#### Tokens to author fresh for NetPulse — palette + semantic mappings

```css
/* Append to tokens.css after the block above */

:root {
  /* ─── NetPulse palette — TODO: choose values during implementation ─── */
  /* Suggestion: cool/blue neutrals to evoke signal/network/data;
   * accent emphasis on signal-strength colors (blue, cyan, green/red status). */

  --np-neutral-000: #ffffff;
  --np-neutral-050: /* near-white with cool tint */;
  --np-neutral-100: /* */;
  --np-neutral-200: /* */;
  --np-neutral-300: /* strong border tone */;
  --np-neutral-500: /* tertiary text */;
  --np-neutral-650: /* secondary text */;
  --np-neutral-950: /* dominant ink */;

  --np-brand:         /* primary CTA — suggest a confident telecom blue */;
  --np-brand-interactive: /* hover/active state, slightly darker */;

  --np-accent-network: /* cool blue — network agent */;
  --np-accent-data:    /* warm amber — CDR analyzer agent */;
  --np-accent-billing: /* violet */;
  --np-accent-hardware:/* terracotta/orange */;
  --np-accent-service: /* teal */;

  --np-status-critical: /* red */;
  --np-status-major:    /* orange */;
  --np-status-minor:    /* yellow */;
  --np-status-info:     /* grey-blue */;
  --np-status-resolved: /* green */;

  --np-focus: /* WCAG AA-compliant focus ring colour, often a saturated blue */;
  --np-error: /* error/validation */;

  /* ─── Semantic mappings (names from Heliodoron, values point to NetPulse palette) ─── */
  --surface-page:    var(--np-neutral-050);
  --surface-raised:  var(--np-neutral-000);
  --surface-sunken:  var(--np-neutral-100);
  --surface-inverse: var(--np-neutral-950);

  --text-primary:   var(--np-neutral-950);
  --text-secondary: var(--np-neutral-650);
  --text-tertiary:  var(--np-neutral-500);
  --text-inverse:   var(--np-neutral-050);
  --text-brand:     var(--np-brand-interactive);

  --border-default: color-mix(in oklab, var(--np-neutral-950) 10%, transparent);
  --border-hover:   color-mix(in oklab, var(--np-neutral-950) 20%, transparent);
  --border-strong:  var(--np-neutral-300);
}
```

#### File layout

```
netpulse-ui/static/
├── tokens.css      ← NEW: foundational layer
└── style.css       ← REFACTOR: replace hardcoded values with var(--*)
```

Each template loads tokens *before* the consuming stylesheet:
```html
<link rel="stylesheet" href="{{ url_for('static', filename='tokens.css') }}">
<link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
```

#### Adoption strategy (3 phases — keeps the demo live throughout)

1. **Phase 1 (~1h):** Drop `tokens.css` into `netpulse-ui/static/`, link it from every template before `style.css`. Existing UI is unchanged because nothing yet consumes the tokens. Zero risk.
2. **Phase 2 (~2h):** Refactor `style.css` to consume tokens — replace hardcoded `padding: 16px` → `padding: var(--space-4)`, hardcoded colors → semantic tokens. Verify visually that the existing UI still renders the same.
3. **Phase 3 (~1h, ongoing):** New components (§5.1, §5.2, §5.3, §5.4, §5.5, §5.11) are authored token-first by default.

#### Reference for canonical updates

If Heliodoron tokens evolve (palette revision, new spacing stop, easing tweaks), the NetPulse copy is **deliberately decoupled** — no auto-sync. Periodic check-in on `~/projects/heliodoron-ui-identity/tokens/heliodoron.css` is the way to pull updates. Any structural lift (spacing, radius, shadow, motion, layout, type scale) should remain in lockstep; brand-specific divergence (palette, semantic mappings) stays NetPulse-owned.

**Files:**
- NEW: `netpulse-ui/static/tokens.css` (the curated subset above + NetPulse palette/semantic mappings)
- MODIFY: `netpulse-ui/static/style.css` (refactor hardcoded values to consume tokens)
- MODIFY: `netpulse-ui/templates/landing.html` (NEW per §5.11), `chat.html`, `network_events.html`, `cdr_records.html`, `tickets.html` — add `<link>` for tokens.css before style.css

**Effort:** M (~4h total): copy structural tokens (~30min) + design NetPulse palette (~1.5h) + refactor `style.css` (~2h).

**Auth:** src+deploy. Manual Cloud Run redeploy by user once the token layer renders identically to current UI in local browser test.

**Dependencies:** None — fully self-contained foundational work.

**Blocks:** §5.1 three-pane workspace, §5.2 timeline, §5.3 badges, §5.4 action chips, §5.5 impact card, §5.11 landing page. All consume tokens defined here.

**Licensing note:** `heliodoron-ui-identity` is a private repo with no declared license. Lifting structural tokens (spacing, radius, shadow, motion) is treated as adopting an open methodology (akin to using Tailwind's defaults). The CSS comment header at the top of `tokens.css` provides attribution. User is the author of both repos, so internal copy is authorised; if NetPulse is ever open-sourced or contributed to a third party, revisit this with an explicit license statement on the Heliodoron side first.

---

### 5.1 Three-pane ticket workspace layout (ServiceNow-inspired)

**Today:** Single full-width chat with 4 stacked cards. No queue context, no history.

**Proposal:** Refactor the `/chat` route into a three-pane layout:

```
┌──────────────┬───────────────────────────────────────┬─────────────────────┐
│              │                                       │                     │
│  Recent      │   Active Triage / Active Ticket       │  Related Context    │
│  Tickets     │                                       │                     │
│  (left)      │   - chat input                        │  - Related events   │
│              │   - 4-card pipeline                   │  - CDR window       │
│  [#66 net    │   - generated ticket detail           │  - Similar tickets  │
│   Jakarta]   │                                       │    (last 7 days)    │
│  [#65 bill   │                                       │                     │
│   Surabaya]  │                                       │                     │
│  ...         │                                       │                     │
│              │                                       │                     │
└──────────────┴───────────────────────────────────────┴─────────────────────┘
```

**Why it elevates the demo:** Judges scanning the UI see "this is a real operator tool, not a toy chatbot." The left rail (recent tickets) demonstrates persistence + scale; the right rail (related context) demonstrates the agentic data integration.

**Files:** `netpulse-ui/templates/chat.html`, `netpulse-ui/static/style.css`, `netpulse-ui/app.py` (new endpoint to fetch recent tickets list for the left pane).

**Effort:** L (half-day). Core CSS work + 1 new Flask route + JS to swap the center pane on left-click.

**Mobile fallback:** Collapse to single-column with tab nav at <800px (data viewer tabs already establish this pattern).

---

### 5.2 Pipeline-as-timeline (PagerDuty-style vertical activity stream)

**Today:** 4 horizontal cards in a row, all visible simultaneously.

**Proposal:** Re-orient the pipeline as a **vertical timeline** that builds top-to-bottom as the SSE stream arrives. Each agent's contribution appears as a timeline entry with a left-edge timestamp, an icon, and the agent's output indented to the right. This mimics PagerDuty's incident timeline / activity log.

```
2026-04-25 14:32:01 ●─ classifier
                   │   Category: network · Region: Jakarta
                   │   "Connectivity problems → network category"
                   │
2026-04-25 14:32:08 ●─ network_investigator
                   │   Found 9 events in Jakarta:
                   │   - EVT001 outage critical fiber cut · 45000 affected
                   │   - EVT012 outage critical BGP loop · 52000 affected
                   │   - ...
                   │
2026-04-25 14:32:23 ●─ cdr_analyzer
                   │   11 records · 7 completed · 3 dropped (JKT-002) · 1 failed (JKT-003)
                   │
2026-04-25 14:32:34 ●─ response_formatter
                   │   ✓ Saved ticket #66
                   │   [view ticket detail card →]
```

**Why:** Tells a story. Judges' eyes track top-to-bottom naturally. The timeline format also makes the failover region badge (§3.2) visually obvious — a "via global ⤳ asia-southeast2" annotation on the timeline entry.

**Files:** `netpulse-ui/templates/chat.html`, `static/style.css`. The card component becomes a `<li class="np-timeline-entry">` inside an `<ol class="np-timeline">`.

**Effort:** M (~3h). Pure CSS + small DOM refactor; logic is identical.

---

### 5.3 Severity + Category badges with color coding

**Today:** Category and region appear as plain-text fields in the ticket. No visual hierarchy.

**Proposal:** Color-coded badges throughout the UI:

| Element | Coloring |
|---|---|
| Category | network=blue, billing=violet, hardware=amber, service=teal, general=grey |
| Severity (derived) | critical=red, major=orange, minor=yellow, info=grey |
| Status (future, §5.6) | new=blue, ack=amber, resolved=green |

Apply to: timeline entries, ticket header, recent tickets list (§5.1), data viewer ticket tab.

**Files:** `netpulse-ui/static/style.css` (badge components), `templates/chat.html`, `templates/tickets.html`. Optional: extend `agent_runner.py` to compute severity from network event maximum.

**Effort:** S (~1h).

---

### 5.4 "Recommended NOC actions" chip panel on ticket

**Today:** The `recommendation` field is free-text from the LLM, often a single sentence.

**Proposal:** Below the recommendation paragraph, render 3-5 quick-action chips drawn from a static catalog keyed on category. Mock for the demo (no real integration), but the visual sells the workflow story.

```
Recommended NOC actions:
[Open ServiceNow incident]  [Page on-call NOC engineer]
[View JKT-002 in CMDB]      [Subscribe customer to status page]
[Run BGP health check]
```

**Why:** Judges who've used real ITSM tools recognize the pattern instantly. Conveys "this isn't a generated paragraph, it's a workflow trigger."

**Files:** `netpulse-ui/templates/chat.html` (chip rendering), `telecom_ops/prompts.py` (have the response_formatter emit a `suggested_actions` JSON list — or maintain a static `category → actions[]` map in `netpulse-ui/`).

**Effort:** M (~3h) for static map version; L if we have the LLM emit structured actions.

---

### 5.5 Customer-impact card (X affected, Y min, Z events) — PagerDuty-style

**Today:** Customer impact is buried inside the network_investigator text bullets.

**Proposal:** A prominent card above the ticket detail showing computed impact:

```
┌─────────────────────────────────────────────────────────┐
│  ⚠  357,000 customers affected   |   ~6h since onset   │
│  9 active network events  ·  3 critical  ·  4 major    │
└─────────────────────────────────────────────────────────┘
```

Computed by summing `affected_customers` from network events + earliest `started_at` for elapsed time + counts by severity.

**Why:** Pre-attentive impact signal. The judge instantly understands the stakes. PagerDuty does this exact pattern at the top of every incident.

**Files:** `netpulse-ui/templates/chat.html`, `netpulse-ui/agent_runner.py` (compute the rollup once `network_investigator` completes — emit as a new event type `impact_summary`), or alternatively compute client-side from the existing `tool_response` payload.

**Effort:** M (~3h). Client-side computation from the existing SSE event is simpler.

---

### 5.6 Acknowledge / Resolve action buttons + status workflow

**Today:** Tickets are write-only. Once saved, they're inert rows in AlloyDB.

**Proposal:** Add `[Acknowledge]` and `[Resolve]` buttons to the generated ticket card. Persist a `status` enum (`new` → `acknowledged` → `resolved`) on `incident_tickets`. Show the status as a stepper visualization (ServiceNow pattern).

**Why:** Closes the loop. Demonstrates that NetPulse isn't just an LLM call — it's a state machine that can integrate into the operator's workflow. Also enables the §4.5 KPI strip.

**Files:** `setup_alloydb.py` (add `status` column with default `'new'`), `netpulse-ui/app.py` (POST `/api/tickets/<id>/ack`, `/resolve`), `netpulse-ui/templates/chat.html` and `tickets.html` (buttons + stepper).

**Effort:** L (~half-day). DB migration + 2 new endpoints + JS state handling.

**Why Tier 4 not Tier 2:** Adds DB schema change which complicates the deploy story. If pursuing, do AFTER Tier 1 is complete and stable.

---

### 5.7 Similar past tickets sidebar (last 7 days, same cat+region)

**Today:** No cross-ticket awareness. Each chat is stateless.

**Proposal:** In the right pane (§5.1), after the ticket is generated, show the 5 most-recent prior tickets matching the same `category + region` from the last 7 days. Click expands to show the prior recommendation. ServiceNow's "Related incidents" pattern.

**Why:** Demonstrates that NetPulse builds institutional memory. Judges see a system that learns from its own outputs, even passively.

**Files:** `netpulse-ui/data_queries.py` (new `recent_tickets_by_category_region(category, region, days=7, limit=5)`), `chat.html` right pane.

**Effort:** M (~3h).

---

### 5.8 Knowledge-base style "Likely root causes" checklist

**Today:** No category-specific diagnostic templates.

**Proposal:** For each `(category, region)` combination, surface a 3-5 item diagnostic checklist drawn from a static template. ServiceNow's KB-article-suggestion pattern.

Example for `network` + `Jakarta`:
```
Likely root causes (templated):
☐ Check active fiber cuts on south Jakarta backbone
☐ Verify cell tower load on JKT-001…JKT-004
☐ Inspect BGP routing health (recent EVT012 BGP loop)
☐ Check DDoS detection logs (recent EVT020)
☐ Confirm congestion thresholds during business hours
```

**Why:** Conveys domain expertise — judges see that NetPulse isn't generic; it knows what telcos actually look at.

**Files:** Static template map in `netpulse-ui/diagnostic_templates.py`, rendered in `chat.html`. Optionally have the response_formatter LLM produce these dynamically (richer but less reliable).

**Effort:** M (~3h) for static; L for LLM-generated.

---

### 5.9 KPI strip header (tickets opened/resolved today)

**Today:** No aggregate KPIs displayed.

**Proposal:** Persistent header strip on the chat page:

```
[NetPulse AI]   ●  12 tickets today   ●  8 resolved   ●  4 active   ●  Avg triage 24s
```

Computed from AlloyDB. Refreshes every 30s via background fetch.

**Why:** Conveys volume + product-thinking. Borrowed from PagerDuty's "incident dashboard" header.

**Files:** `netpulse-ui/data_queries.py` (new aggregate query), `app.py` (`/api/kpis` endpoint), `chat.html` header.

**Effort:** M (~2-3h). Depends on §5.6 status column for resolved counts.

---

### 5.10 Empty-state illustrations on data viewer tabs

**Today:** Filtering to no results probably shows an empty table or generic "No rows" string.

**Proposal:** Lightweight empty-state messaging with a hint: "No CDR records match. Try widening the date range or removing filters." Subtle visual (icon + text, no heavy illustration).

**Why:** Polish signal. ServiceNow / Linear / modern SaaS standard.

**Files:** `templates/network_events.html`, `cdr_records.html`, `tickets.html`, `static/style.css`.

**Effort:** S (~1h).

---

### 5.11 Hero landing page + routing redesign

**Today:** `/` 302-redirects straight to `/chat`. Judges land in the app with no intro, no context, no usage guide. The data viewer tabs are reachable only from inside the chat-context nav — there's no top-level "explore the data first" path.

**Proposal:** Make `/` a dedicated hero landing page. Move the full app to `/app` (keep `/chat` as a 301 alias for backwards compatibility). The landing page provides:

1. **Hero** — product name, one-line value prop, primary CTA, tech-strip below.
2. **"How it works" wireframe** — 4-step visual walkthrough mirroring the agent pipeline.
3. **Example complaint chips** — click to launch the app pre-loaded with that complaint (`/app?seed=...`).
4. **Data viewer cards** — direct entry into the BigQuery / AlloyDB tabs for judges who want to inspect data without typing first.
5. **Footer** — hackathon attribution + GitHub link + architecture doc link.

**Why for Top 10:** First impression. A judge who lands on a hero with "Telecom incident triage in seconds. Multi-agent. Built with Google ADK." gets the value prop in 3 seconds. A judge dropped straight into a chat input has to reverse-engineer what the product is. The landing page also sets the narrative ("this is a product, not a notebook") before any interaction. This is the highest-leverage UX change in the audit.

**Wireframe (ASCII — editor-portable, conveys layout for translation to HTML/CSS):**

```
┌─────────────────────────────────────────────────────────────────────┐
│  NetPulse AI    │ How it works │ Architecture │ GitHub │ [Launch ▶] │  ← top nav
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│            Telecom incident triage in seconds.                      │
│                                                                     │
│   A multi-agent assistant that turns a customer complaint into      │
│   a structured NOC incident ticket. Built with Google ADK.          │
│                                                                     │
│              [ Launch NetPulse AI → ]   [ View on GitHub ]          │  ← hero CTA
│                                                                     │
│   ●  4 sub-agents · BigQuery · AlloyDB · Vertex AI Gemini 2.5       │  ← tech strip
│   ●  Vertex AI failover ladder: global → asia-southeast2/1 → us     │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   How it works                                                      │
│                                                                     │
│   ┌─────────┐   ┌─────────┐   ┌─────────┐   ┌─────────┐             │
│   │ Step 1  │ → │ Step 2  │ → │ Step 3  │ → │ Step 4  │             │
│   │  ✏      │   │  🤖     │   │  🔍     │   │  🎫     │             │
│   │         │   │         │   │         │   │         │             │
│   │ You     │   │ Agents  │   │ Cross-  │   │ Get a   │             │
│   │ type a  │   │ classify│   │ check   │   │ ticket  │             │
│   │ complain│   │ + look  │   │ network │   │ saved   │             │
│   │         │   │ up data │   │ events  │   │ to NOC  │             │
│   │ "calls  │   │         │   │ + CDRs  │   │         │             │
│   │ failing │   │         │   │         │   │         │             │
│   │ in JKT" │   │         │   │         │   │         │             │
│   └─────────┘   └─────────┘   └─────────┘   └─────────┘             │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   Try one of these                                                  │
│                                                                     │
│   [Major dropped calls in Surabaya]   [Billing dispute in Jakarta]  │
│   [Hardware failure in Medan]         [Service degradation Bandung] │
│                                                                     │
│   ↓ click any to launch the app pre-loaded with that complaint      │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   What's inside  (data viewers — open without typing)               │
│                                                                     │
│   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│   │ Network      │  │ Call Detail  │  │ Incident     │              │
│   │ Events       │  │ Records      │  │ Tickets      │              │
│   │              │  │              │  │              │              │
│   │ BigQuery     │  │ AlloyDB      │  │ AlloyDB      │              │
│   │ → 30 events  │  │ → 60 records │  │ → 66 tickets │              │
│   │ across 5 cit │  │              │  │              │              │
│   └──────────────┘  └──────────────┘  └──────────────┘              │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│   APAC GenAI Academy 2026 · Top 100 (#82) · Adityo Nugroho          │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

**Routing change:**

| Path | Today | Proposed |
|---|---|---|
| `/` | 302 → `/chat` | Returns `landing.html` |
| `/app` | (does not exist) | Returns chat workspace template |
| `/chat` | Chat workspace | 301 → `/app` (backwards compat) |
| `/network-events` | Data viewer tab | unchanged; linked from landing card |
| `/cdr-records` | Data viewer tab | unchanged |
| `/tickets` | Data viewer tab | unchanged |

**Pre-load handoff (landing → app):**

Example chips link to `/app?seed=Major%20dropped%20calls%20in%20Surabaya`. The chat page reads `URLSearchParams` on load, populates `#np-input`, and optionally auto-submits when a `?autorun=1` flag is present. The same mechanism unifies with §4.4 (demo seed panel inside the app), so seed strings live in one source of truth.

**Files (NEW):**
- `netpulse-ui/templates/landing.html` (~150 lines: hero, steps, examples, viewer cards, footer)
- Optional: `netpulse-ui/templates/_nav.html` (top-nav fragment shared by landing + app via Jinja `{% include %}`)

**Files (MODIFY):**
- `netpulse-ui/app.py` — `/` returns landing render; new `/app` route; `/chat` becomes 301 redirect to `/app`
- `netpulse-ui/static/style.css` — landing-specific sections: `.np-hero`, `.np-steps`, `.np-step-card`, `.np-examples`, `.np-viewer-cards`
- `netpulse-ui/templates/chat.html` — top-nav link back to `/`; query-param seed handler in `npOnLoad()`

**Effort:** M (~3-4h). Mostly HTML + CSS + 1 route addition + small JS hook for the seed handoff. No new backend logic.

**Mobile:** Stack vertically below ~800px breakpoint. Steps wrap into 2×2 grid on small screens. Tech-strip becomes a single column.

**Accessibility:** All interactive elements get focus styles; example chips are `<button>` not `<div>`; viewer cards are `<a href>` with descriptive text; nav uses semantic `<nav>` + `<ul>`.

**Risk to Freeze A:** None at source level. Manual Cloud Run redeploy (Freeze A boundary) by user once tested locally with `python netpulse-ui/app.py` + browser.

**Synergies / dependencies:**
- **§4.4** (demo seed panel inside the app) — same chip data; one source.
- **§5.9** (KPI strip on chat page) — KPIs could also surface on the landing's tech strip ("66 tickets generated · avg triage 24s · 99.8% success rate").
- **§5.4** (action chips on ticket) — share the same `.np-chip` CSS class; define visual language once.
- **§3.1** (region failover) — the tech-strip mention of "global failover ladder" sells the §3 story without a click. Implement §3.1 first so the strip is accurate when landing ships.

**Variants for user decision:**
- A) Keep `/chat` URL, add `/landing` for the hero (less elegant but zero risk to existing bookmarks).
- B) Default proposal: `/` = landing, `/app` = workspace, `/chat` = 301 → `/app`.
- C) Auto-redirect `/` to `/app` if `?skip-landing=1` query param present (judges who already saw the hero).

Recommendation: B with C as a small additional flag.

---

## Phase 9 — Post-deploy polish + robustness

The first production deploy on 2026-04-26 (revision `00004-sfn`, carrying Phases 2-7) surfaced two classes of issue immediately: (a) visual identity v0 read as "generic Material" rather than something memorable, and (b) the chosen Gemini preview models exposed Vertex AI quirks (silent hangs in `global`, partial regional availability) that the original failover wrapper could not handle. Phase 9 ran as iterative polish-and-redeploy mode against the warm `min-instances=1` service across revisions `00006-7v8` → `00007-x7t` → `00008-kzk` → `00009-f2c` → `00010-mqc`. Items here capture each iteration as a discrete change so the rationale is preserved.

### 9.1 Heliodoron visual identity v1

**Why it matters:** §5.0a's default token palette was generic cool-gray + Material Blue. The hackathon brief rewards visual distinctness; switching to the curated Heliodoron sand-neutrals + warm-gold "surya" brand from `~/projects/heliodoron-ui-identity` gave NetPulse a recognizable visual voice without authoring an identity from scratch.

**Files:** `static/tokens.css`, `templates/base.html`. Three font @imports added (`@fontsource-variable/geist`, `newsreader`, `jetbrains-mono` from jsdelivr CDN) replacing the system stacks. Heliodoron Indonesian accent palette (`--np-santan`, `--np-pandan`, `--np-tebu`, `--np-laut`, `--np-batik`, `--np-rosella`, `--np-terakota`) added for downstream use. Status ladder + per-category badges + per-backend palettes intentionally untouched in v1 to preserve semantic distinctness.

**Test:** Live URL serves `tokens.css` 200 with the new palette; visual confirmation against Heliodoron tokens.css commit `0923dfb`. **Revision `00006-7v8`.**

---

### 9.2 Footer trim — remove "with Claude Code" link

**Why it matters:** The original landing footer included "with Claude Code" attribution. Subtle for a personal-blog post, too on-the-nose for a hackathon submission where the originality of the build is being judged.

**Files:** `templates/landing.html`. Now reads: `APAC GenAI Academy 2026 · Top 100 (#82) · Built by Adityo Nugroho.`

**Rode revision `00006-7v8`.**

---

### 9.3 Pandan accent unification

**Why it matters:** Two accent greens were leaking into the same UI surfaces (the heliodoron `--np-pandan` chosen in §9.1 next to leftover teal `#00bfa5` from earlier `--np-accent`). Per-backend `.np-source-tag.{adk,local,mcp,bq,alloydb,alloydb-write}` had drift-accumulated divergent colors.

**Files:** `static/style.css`. Replaced the `linear-gradient(--np-primary → --np-accent)` text-clip on `.np-hero-accent` ("in seconds.") with a solid `var(--np-pandan)`. Replaced per-backend source-tag color overrides with a unified `color-mix(in oklab, var(--np-pandan) 14%, transparent)` background + `var(--np-pandan)` foreground. Backend `--c-*-bg/fg/accent` tokens preserved (still drive workspace banner backgrounds via downstream `color-mix()`).

**Revision `00007-x7t`.**

---

### 9.4 5s `asyncio.wait_for` per-attempt Vertex AI timeout

**Why it matters:** Production trace from revision `00005-ns6` at 05:48:22 UTC ran for **exactly 301s** (Cloud Run's default 300s request timeout) and was killed mid-pipeline. `network_investigator`'s second LLM call sent at 05:48:34.703 and **never received a response** — silent Vertex AI hang in `global`. The region-failover wrapper had no per-attempt deadline so it waited indefinitely. Without this fix, every silent hang becomes a 5-minute demo failure.

**Files:** `telecom_ops/vertex_failover.py`. Added `PER_ATTEMPT_TIMEOUT_S = 5.0` and `asyncio.wait_for(_drain_one_attempt(), timeout=PER_ATTEMPT_TIMEOUT_S)` around each region attempt. On `TimeoutError`, the observer fires with `"failover"` + `"timeout after 5.0s"` and the wrapper advances to the next region. Cancellation propagates → aiohttp closes the socket so only one HTTP call is ever in flight per wrapper.

**Test:** New `_self_test_failover_on_timeout` mocks `asyncio.Future()` in region 0 (resolved only by `wait_for`'s cancellation); test runtime ~5s. **Rode revision `00008-kzk`.** *(Later updated to 10s by §9.14.)*

---

### 9.5 Per-agent model selection

**Why it matters:** Phase 8 deployed all 4 agents on `gemini-2.5-flash`. After §9.4 surfaced the cost of waiting (every silent hang = 5s lost), the upstream 3 agents were moved to `gemini-3.1-flash-lite-preview` (faster — 0.6-1.9s per call vs 2-4s on 2.5-flash) and the synthesis agent kept the more capable `gemini-3.1-pro-preview` for instruction-following fidelity on the final report. *Note: Pro-preview later proved `global`-only on this project — see §9.7 (resolved via §9.13).*

**Files:** `telecom_ops/agent.py`. Added `MODEL_FAST = "gemini-3.1-flash-lite-preview"` and `MODEL_SYNTHESIS = "gemini-3.1-pro-preview"`; `_failover_model(owner, model_name)` factory passes the right model per agent.

**Rode revision `00008-kzk`.**

---

### 9.6 Multi-continent region ladder

**Why it matters:** The original `RANKED_REGIONS = ("global", "asia-southeast2", "asia-southeast1", "us-central1")` was geographically optimal but `gemini-3.1-pro-preview` returned `400 FAILED_PRECONDITION` in both Singapore and Jakarta. With Pro-preview in the synthesis path (per §9.5), the failover ladder needed regions where it actually worked.

**Files:** `telecom_ops/vertex_failover.py`. Swapped to `("global", "us-central1", "europe-west4", "asia-northeast1")` — three continents, all known accessible for Gemini preview models on this project. Self-tests adjusted to match new ordering.

**Revision `00009-f2c`.**

---

### 9.7 🔄 Pro-preview region-whitelist finding (RESOLVED via §9.13)

**Finding:** Even after the multi-continent ladder swap (§9.6), `gemini-3.1-pro-preview` on `plated-complex-491512-n6` only returned 200 OK in `global` — `us-central1` returned `404 NOT_FOUND` ("Publisher Model not found or your project does not have access"). This made the failover ladder a structural no-op for the synthesis agent: any failover attempt would land on a 404 immediately. The 5s timeout would fire (real silent hang in `global`), the wrapper would advance to `us-central1`, and the 404 would propagate as a hard error rather than continuing the ladder.

**Status:** No code change made for §9.7 in isolation — captured here as the diagnostic that drove §9.13.

---

### 9.8 Post-deploy doc polish

**Why it matters:** Cumulative changes in §9.1-§9.6 made the existing CLAUDE.md / README / phase docs stale on multiple non-obvious choices (region failover details, preview model rationale, deploy resource tables).

**Files:** `CLAUDE.md` (project), `README.md` (region paragraph + lessons + deploy resource tables), `REFINEMENT-PHASES.md`, `~/.claude/memory/reference_vertex_ai_dsq.md`, NEW `~/.claude/memory/reference_vertex_ai_preview_models.md`, `~/.claude/memory/MEMORY.md` (index), `~/.claude/memory/project_top100_refinement.md`.

**Shipped as commit `61f06ca` PR #10.**

---

### 9.9 ⏸ SSE streaming GIF in README (DEFERRED)

**Why deferred:** Recording a screen-capture GIF of the live pipeline animation requires a live browser session against the deployed UI. No source-only path; needs the user's recording loop. The new region chip from §3.2 + heliodoron palette from §9.1 make this a richer asset, so this should be recorded after Phase 11 settles to capture the final state.

**Supersedes:** §2.11 — same ask, same blocker.

---

### 9.10 Header darker token

**Why it matters:** The hero header's gradient `--np-primary-dark → --np-primary` (warm-gold) was visually light against the white text and white logo plate. Needed a heavier anchor to read as "structural top-of-page surface."

**Files:** `static/tokens.css` — added `--np-brand-deep: oklch(38% 0.110 55)` (deep amber-bronze, retains warm-gold hue while ~30% darker L*). `static/style.css` — `.np-header` gradient swapped from `--np-primary-dark → --np-primary` to `--np-brand-deep → --np-brand-interactive`. White text + white logo plate clear WCAG AA easily on the new anchor.

**Rode revision `00010-mqc`.**

---

### 9.11 Done-state pandan unification

**Why it matters:** Sister polish to §9.3 — the `.np-timeline-entry.done` dot, content border-left, and status pill were still using leftover teal `--np-accent` (#00bfa5).

**Files:** `static/style.css`. Switched all three to `--np-pandan` (oklch 60% 0.085 135). Now the "DONE" pill, dot, and source-tag badges read as one green family instead of two visually-dissonant greens.

**Rode revision `00010-mqc`.**

---

### 9.12 Customer-impact card extractor + layout fix

**Why it matters:** §5.5 shipped the impact card but it silently degraded to `[]` rows on every run — only the headline count rendered, not the per-severity breakdown. Root cause traced through `toolbox_core/itransport.py:51` (`tool_invoke -> str`) + `google.adk.flows.llm_flows.functions.__build_response_event:700` (`if not isinstance(function_result, dict): function_result = {'result': function_result}`): MCP toolbox tools return JSON-encoded *strings*, ADK wraps as `{"result": "<string>"}`, so `tool_response.result.result` arrives at the chat UI as a STRING not an Array. The original `npExtractRows` only walked `Array.isArray` shapes.

**Files:** `templates/chat.html`. `npExtractRows` now `JSON.parse`s strings recursively before checking `Array.isArray`. Layout redesign: grid (icon-left + body-right) with headline row (big affected count) + meta row (events · elapsed · sev badges); each meta wrapper hides itself when its data is missing (no more dangling `--` placeholder for `since onset`). `npComputeImpact` also tolerates `total_affected` (aggregate-summary tool output) and parses `event_time`/`timestamp` columns alongside `started_at`.

**Rode revision `00010-mqc`.**

---

### 9.13 `MODEL_SYNTHESIS = MODEL_FAST` collapse

**Why it matters:** Resolves §9.7. Collapses all 4 agents onto `gemini-3.1-flash-lite-preview` (multi-region addressable). The earlier per-agent split from §9.5 was structurally sound but Pro-preview's `global`-only restriction on this project meant the failover ladder was a no-op for synthesis. Flash-Lite for synthesis sacrifices some instruction-following fidelity but keeps the failover ladder structurally usable end-to-end.

**Files:** `telecom_ops/agent.py`. Failover self-tests still pass (matcher 5/5 + quota failover + hang failover). Revert option documented in CLAUDE.md: `MODEL_SYNTHESIS = "gemini-2.5-pro"` (GA + multi-region) if production traces show synthesis quality is insufficient.

**Revision `00010-mqc`.**

---

### 9.14 `PER_ATTEMPT_TIMEOUT_S` 5s → 10s

**Why it matters:** Phase 11 production trace surfaced a false-positive: `network_investigator` summarising a 15.5 KB `weekly_outage_trend` response on `global` exceeded the 5s deadline at 5.05s, the wrapper marked it as a hang and failed over to `us-central1`, where Flash-Lite was unavailable (404 NOT_FOUND), surfacing as a hard demo failure. 5s was tight for the original Phase 9 workload but became insufficient once Phase 11 added the 50-row `weekly_outage_trend` rollup.

**Files:** `telecom_ops/vertex_failover.py` — `PER_ATTEMPT_TIMEOUT_S: float = 10.0`; updated docstring with the trace explanation; self-test docstring `~5s` → `~10s`. CLAUDE.md non-obvious-choice block + README current-tense references swept from "5s timeout" to "10s timeout".

**Test:** Re-ran the same complaint that triggered the false-positive → ticket #18 in 32s, no false-positive timeout. **Shipped as PR #14, revision `netpulse-ui-00013-5md`.**

---

## Phase 10 — Toolbox refactor + seed enrichment

After Phase 9 settled the deploy + visual identity layer, the next bottleneck was the MCP Toolbox surface area. The original toolbox carried 8 hand-written BigQuery tools (5 per-city outage queries + `query_network_events` catch-all + `query_critical_outages` + `query_affected_customers_summary`) and a hardcoded 20-row LIMIT on the AlloyDB CDR tool. Adding a city meant adding tools; widening the time window meant editing the hardcoded SQL. Phase 10 collapsed the toolbox to 2 universal parameterized tools, parameterized the CDR tool similarly, and grew the seed data 4× across 5 new cities. A pre-existing severity-vocab bug surfaced during seed prep and was fixed inline.

### 10.1 Universal-tools refactor (8 tools → 2 parameterized)

**Why it matters:** A judge inspecting the toolbox manifest sees the abstraction quality of the agent surface; 8 special-case tools reads as "demo wiring," 2 universal parameterized tools reads as "deployable platform." The refactor needed three deploy iterations to discover four real BigQuery + toolbox-core runtime constraints (captured in `~/.claude/memory/reference_mcp_toolbox_universal_tools.md`):
1. The SDK ignores backend `default:` for `required: false` params.
2. BQ rejects null INT64 binds at dry-run.
3. BQ rejects null STRING binds at execute.
4. BQ `LIMIT` accepts only an integer literal or a single parameter — no expressions like `IFNULL(@limit, 50)`.

**Final shape:** Every param `required: true` + `default:` sentinel (`"*"` for strings, `36500` for `days_back`, `50` for `limit`); SQL uses sentinel comparison (`@region = '*' OR region = @region`) instead of nullable binds.

**Files:** `~/projects/genai-hackathon/track2-network-status/toolbox-service/tools.yaml`. Two tools shipped: `query_network_events(region, severity, event_type, days_back, limit)` and `query_affected_customers_summary(region, days_back)`. `NETWORK_INVESTIGATOR_INSTRUCTION` updated to tell the agent to ALWAYS pass all params using sentinels for "no filter."

**Deployed:** `network-toolbox-00006-bsm`.

---

### 10.2 Native CDR tool optimization (parameterized)

**Why it matters:** The pre-Phase-11 `query_cdr` Python tool was hardcoded to `LIMIT 20` and only accepted `region` + `status_filter`. Real complaints reference time windows ("recent" / "last week" / "this month") and call types (voice vs sms vs data). Parameterizing exposed the surface the agent prompt could realistically exercise.

**Files:** `telecom_ops/tools.py:query_cdr` — added `days_back` (validated 1..365) and `call_type` (optional voice|sms|data) params; `LIMIT` defaults to 50 (clamped 1..200). `prompts.py:CDR_ANALYZER_INSTRUCTION` rewritten to enumerate the new params with usage hints. *Later replaced wholesale by §11.1 (NL2SQL).*

---

### 10.3 Richer seed data — 10 cities, 132 events, 500 CDRs

**Why it matters:** Phase 9 settled with 5 cities (Jakarta/Surabaya/Bandung/Medan/Semarang) × 30 events × 50 CDRs. The geographic narrative ("any Indonesian metro") needed more cities; the per-tower failure narrative ("which tower is failing in Denpasar?") needed more CDRs per region. Cell tower IDs use IATA airport codes for new cities (YOG, DPS, MKS, PLM, BPN).

**Files:** `docs/seed-data/network_events.csv` (30 → 132 events, date range 2026-01-08 → 2026-05-12 incl. 5 future maintenance windows); `docs/seed-data/call_records.csv` (50 → 500 CDRs, distribution 320 completed / 118 dropped / 62 failed; failed/dropped clustered around outage anchors per city for storytelling); `NETWORK_INVESTIGATOR_INSTRUCTION` + `CLASSIFIER_INSTRUCTION` city list extended; `netpulse-ui/data_queries.py:ALLOWED_REGIONS` extended to 10 cities. *Later grown by §11.2 (50k events) and §11.3 (5k CDRs).*

---

### 10.4 `setup_alloydb.py` multi-row INSERT VALUES

**Why it matters:** The CDR seed reload via `setup_alloydb.py --seed` hung indefinitely on the original `conn.execute(insert_sql, payload_list_of_500_dicts)`. SQLAlchemy + pg8000 turn that into 500 round-trips over the AlloyDB public-IP path; over WAN that consistently exceeded any reasonable timeout.

**Files:** `setup_alloydb.py:truncate_and_load`. Replaced with a single multi-row `INSERT ... VALUES (..), (..), ...` statement built from the payload list — one network round-trip for the entire batch.

**Test:** Reseed dropped from "indefinite hang" to <120s. Necessary fix for any BYO seed >100 rows.

---

### 10.5 `ALLOWED_SEVERITIES` vocab bug fix

**Why it matters:** Pre-existing bug surfaced during seed prep. `netpulse-ui/data_queries.py:36` had `ALLOWED_SEVERITIES = {"low","medium","high","critical"}` but live BigQuery + `docs/SCHEMA.md:35` use `{"critical","major","minor"}`. The `/network-events` viewer's severity dropdown silently filtered to nothing for `major`/`minor` rows.

**Files:** `netpulse-ui/data_queries.py:36`. Fixed inline with the seed enrichment.

**Test:** Verified via `bq query "SELECT severity, COUNT(*) FROM ... GROUP BY severity"` returning only `minor/major/critical` — vocab now matches.

---

### 10.6 `netpulse-ui` redeploy + E2E smoke (Denpasar complaint)

**Why it matters:** New prompts + ALLOWED_REGIONS + universal toolbox shape needed end-to-end validation against a freshly-seeded city not in the original 5.

**Files:** revision `netpulse-ui-00011-5ct`.

**Test:** Complaint *"Customer reports failed calls in Denpasar"* exercised:
- classifier → `category=network, region=Denpasar`
- network_investigator → `query_network_events(region='Denpasar', severity='*', event_type='*', days_back=36500, limit=10)` returns 10 events including 3 critical submarine cable damage incidents (EVT069, EVT064, EVT061)
- cdr_analyzer → `query_cdr(region='Denpasar', status_filter='')` returns 50 CDRs; LLM correctly correlates 22 dropped/failed calls clustered around March-19 + April-17 outage anchors (matching the generator's intentional clustering)
- response_formatter → ticket #11
- All 4 agents first-try in `global`, no failovers, no timeouts, total runtime well under the 5s per-attempt budget. Sentinel pattern (`*`/36500/50) confirmed end-to-end.

---

## Phase 11 — AlloyDB AI NL2SQL + BigQuery analytical workload

Phase 10 settled the toolbox refactor + seed enrichment, but two judged dimensions remained underexploited: **AlloyDB AI was on but unused** (the `alloydb_ai_nl` v1.0.9 extension was *available but not installed*; the `default_llm_model=gemini-2.5-flash-lite` instance flag was a no-op for the agents) and **BigQuery did not earn its store slot** (132 rows in 14 KB; both BQ tools were point lookups or tiny GROUP BYs that AlloyDB's row store would serve in single-digit ms). Phase 11 closed both gaps in a single 2026-04-26 push, ahead of the 2026-04-30 Top-10 cut. Plan: `~/.claude/plans/witty-giggling-clover.md`. Driven by user choices: Path B (Toolbox-native NL invocation) + grow CDR seed to 5000 rows.

### 11.1 AlloyDB AI NL2SQL on `cdr_analyzer`

**Why it matters:** The hand-written parameterized `query_cdr` from §10.2 worked but kept the AlloyDB AI surface entirely unused. Replacing it with NL2SQL exercises (a) the `alloydb_ai_nl` extension, (b) the `gemini-2.5-flash` model registered via `google_ml.create_model`, (c) Vertex AI from inside the AlloyDB instance's region. Demo narrative also improves: agents pose English questions and the data layer translates — a stronger "agentic platform" story than "agent calls a SQL string."

**Setup:** `scripts/setup_alloydb_nl.py` (NEW, ~330 lines, 10 idempotent steps): extension install (CASCADE), model registration via `google_ml.create_model`, configuration create + bind to model via `g_manage_configuration change_model`, `register_table_view` for `public.call_records`, `add_general_context` (5 lines: cities, enums, tower scheme, time hints), `generate_schema_context` (3-5 min blocking LLM step) + `apply_generated_schema_context`, `associate_concept_type` for the `region` column → built-in `city_name`, `create_value_index`, 4 templates (tolerated to fail because `add_template` always validates SQL), and the `netpulse_nl_reader` read-only role with `SELECT` on `call_records` + `EXECUTE` on the `alloydb_ai_nl` schema. **Toolbox** connects as that read-only role — destructive NL is blocked structurally, not by prompt.

**Tool wiring:**
- `tools.yaml` adds `alloydb-postgres` source `alloydb-cdr` + tool `query_cdr_nl` of `kind: postgres-sql` (NOT `kind: alloydb-ai-nl` — toolbox v0.23.0's native adapter sends `param_names => ARRAY[]::TEXT[]` even when no nlConfigParameters are declared, and AlloyDB AI rejects empty text-arrays with `Invalid PSV named parameters`; workaround calls `execute_nl_query('netpulse_cdr_config', $1)` directly via postgres-sql).
- `tools.py` deletes the 60-line `query_cdr` function and adds `cdr_nl_tools` loader.
- `agent.py` swaps `cdr_analyzer.tools` from `[query_cdr]` to `cdr_nl_tools`.
- `prompts.py` rewrites `CDR_ANALYZER_INSTRUCTION` for the NL question pattern with per-category examples.

**Five non-obvious gotchas** captured in `~/.claude/memory/reference_alloydb_ai_nl_setup.md`:
1. Toolbox v0.23.0 alloydb-ai-nl adapter PSV empty-array bug — workaround via postgres-sql.
2. `default_llm_model` instance flag silently ignored without `google_ml.create_model` registration.
3. `add_template` always validates SQL; `$1` placeholders fail. Templates are optional polish.
4. `associate_concept_type` requires pre-existing concept types (built-ins: `city_name`, `country_name`, `date`, `full_person_name`, `generic_entity_name`, `region_name`, `ssn`).
5. BigQuery `TIMESTAMP_SUB` rejects `WEEK` for TIMESTAMP arguments — multiply into days (`INTERVAL N * 7 DAY`).

**Files:** `scripts/setup_alloydb_nl.py` (NEW), `tools.yaml` (toolbox repo), `telecom_ops/tools.py`, `telecom_ops/agent.py`, `telecom_ops/prompts.py`, `setup_byo.sh` (added `--nl-setup` flag).

**Test:** Direct `SELECT alloydb_ai_nl.get_sql('netpulse_cdr_config', 'How many dropped calls in Denpasar in the last 14 days?')` returns clean SQL (`WHERE call_status='dropped' AND region='Denpasar'`) in 1.8s; `execute_nl_query` as `netpulse_nl_reader` returns `{'dropped_calls_count': 15}`.

---

### 11.2 BQ DAY-partition + clustering + 50k seed + `weekly_outage_trend`

**Why it matters:** Three coordinated changes that make BigQuery earn its slot:
1. Re-create `network_events` as **DAY-partitioned on `started_at` and clustered by `(region, severity)`** (BigQuery does not allow partition changes in place, so destructive `--recreate` flag).
2. Grow seed 132 → **50,000 events** over 6 months (2025-11-01 → 2026-04-30) with realistic time-series shape.
3. Add `weekly_outage_trend(region, weeks_back, limit)` analytical tool that returns per-week `event_count`, `critical_count`, `major_count`, `total_affected`, `avg_mttr_minutes` — the partition pruning keeps a 12-week scan at ~25 KB instead of 6 MB unfiltered.

**Generator:** `scripts/generate_network_events.py` (NEW, ~210 lines, deterministic `Random(20260426)`; 70/22/5/3 mix of maintenance / degradation / outage / restoration; final distribution `{maintenance: 35221, degradation: 10833, outage: 2446, restoration: 1500}`). Reload: `scripts/setup_bigquery.py --seed --recreate` (the new `--recreate` flag drops + recreates the table to apply the partition spec).

**Tool wiring:** `tools.yaml` adds `weekly_outage_trend` to `telecom_network_toolset`; `prompts.py:NETWORK_INVESTIGATOR_INSTRUCTION` extended with a third tool block. SQL: `WHERE event_type IN ('outage', 'degradation') AND started_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL @weeks_back * 7 DAY) AND (@region = '*' OR region = @region) GROUP BY week_start, region ORDER BY week_start DESC, total_affected DESC LIMIT @limit`.

**Files:** `scripts/setup_bigquery.py` (added `--recreate` flag, partition spec), `scripts/generate_network_events.py` (NEW), `tools.yaml` (toolbox repo), `telecom_ops/prompts.py`, `docs/seed-data/network_events.csv` (regenerated).

**Test:** `bq show ... | jq '{numRows, timePartitioning, clustering}'` confirms 50,000 rows, DAY partition on `started_at`, clustering on `(region, severity)`. `bq query --dry_run` for 7-day window reports 24,944 bytes processed (vs ~6 MB unfiltered) — partition pruning works.

---

### 11.3 5k CDR seed with anchor-clustered failures

**Why it matters:** 500 CDRs across 10 cities is ~50 per city — not enough for the per-tower failure narrative ("which tower in Denpasar is failing?") to produce statistically interesting answers. Grew seed 500 → **5,000 rows** with anchor-clustered failures so NL queries return non-trivial winners.

**Generator:** `scripts/generate_call_records.py` (NEW, ~200 lines, deterministic `Random(20260426)`; 60/25/15 mix of completed / dropped / failed; ~50% of dropped land on towers 1-2 per city; ~50% of failed land on towers 3-4; phone pool: 50 callers (`0812*`) × 50 receivers (`0813*`); final distribution `{completed: 3000, dropped: 1250, failed: 750}`). Reload via `setup_alloydb.py --seed` (the §10.4 multi-row INSERT handles 5k rows in <120s with no modification).

**Files:** `scripts/generate_call_records.py` (NEW), `docs/seed-data/call_records.csv` (regenerated).

**Test:** Per-region top-tower counts after reseed — DPS-002 has 41 dropped vs DPS-005's 11 (clustering bias landed). Three demo complaints on the live UI generated tickets #12 (Denpasar/network), #13 (Jakarta/network — used `weekly_outage_trend`), #14 (Surabaya/network/hardware). Per-run latency 16s / 15s / 16s — within the 15s ±1s demo budget.

---

## Phase 12 — Vertex model-ladder failover + viewer UX polish

A 2026-04-27 push driven by a production trace that exposed the structural break in the prior region-failover ladder, plus a sweep of three deferred Tier-2 viewer-UX items the audit had marked LOW-cost / HIGH-readability. Five items shipped across `netpulse-ui-00014-kc8` → `00019-t46`.

### 12.1 Vertex AI failover redesign — model ladder replaces region ladder

**Why it matters:** Production trace 2026-04-27 04:03:03 UTC on `netpulse-ui-00015-24q` showed the prior multi-continent region ladder hitting its structural limit: `global` 429 RESOURCE_EXHAUSTED → wrapper failed over to `us-central1` → `404 NOT_FOUND` because `gemini-3.1-flash-lite-preview` is `global`-only on this project. Every single quota error became a hard demo failure because the failover destination didn't have the model. The ladder advanced regions but the model pool stayed throttled.

**Files:** `telecom_ops/vertex_failover.py` (full rewrite, lines 1-481), `CLAUDE.md` (architecture + non-obvious-choices paragraphs).

**Change:**
1. Replaced `RANKED_REGIONS` constant with `REGION = "global"` (single endpoint).
2. Replaced `PER_ATTEMPT_TIMEOUT_S` (single 10s) with `ATTEMPT_SCHEDULE: tuple[Attempt, ...]` — a 3-row `NamedTuple` ladder: `Attempt(model=None, timeout_s=10.0, pre_sleep_s=0.0)` / `Attempt(model=None, timeout_s=20.0, pre_sleep_s=0.5)` / `Attempt(model=FALLBACK_MODEL, timeout_s=30.0, pre_sleep_s=0.0)` where `FALLBACK_MODEL = "gemini-2.5-flash"`.
3. Per-attempt loop mutates `llm_request.model` because ADK's parent `Gemini.generate_content_async` reads model from there, not from `self.model` (verified by `inspect.getsource`).
4. Stripped `_active_region`, `_set_active_region`, `_build_client_for(region)` machinery — single client cached for `global`.
5. Observer payload: the `region` field now carries the **model name** (semantic abuse kept to minimize SSE/frontend diff).
6. Three self-tests: `_self_test_quota_retry_same_model` (429 on attempt 1 → succeed on attempt 2, same primary), `_self_test_timeout_retry_same_model` (`asyncio.Future()` hang on attempt 1 → succeed on attempt 2), `_self_test_persistent_429_swaps_to_fallback` (429 on attempts 1+2 → succeed on attempt 3, fallback model).

**Verification:** All 3 self-tests pass locally. Production trace 2026-04-27 05:18:14 walked the full ladder in 543ms (`global 429 → 0.5s sleep → global 429 again → swap to gemini-2.5-flash → ok`); 05:31:10 ("Major dropped calls in Surabaya") swapped twice (both LLM calls of network_investigator) and the demo completed end-to-end with no user-visible failure. Worst-case wall clock per agent: 60.5s, well under Cloud Run's 300s.

### 12.2 Chip-reset for ADK 2-LLM-call-per-agent pattern

**Why it matters:** ADK's tool-calling pattern means each agent makes 2 LLM calls (tool selection + tool-result interpretation). Each call independently walks `ATTEMPT_SCHEDULE`. Without resetting between walks, the chat-UI 'via' chip read as a confusing chain like `via primary ⤳ fallback ⤳ primary ⤳ fallback`, falsely suggesting the wrapper bounced back to the primary. Captured visually in the Network Investigator entry on the Surabaya run.

**Files:** `netpulse-ui/templates/chat.html` (`npRenderRegionAttempt` function).

**Change:** Added `dataset.settled` flag — set to `'1'` on every `ok` event, reset to `'0'` on `failover`. On the next attempt event arriving after settle, the chip is cleared and rebuilt from scratch so it reflects the path of the **most recent** LLM call. Two same-model retries within one walk still collapse via the existing dedupe (`if last.textContent !== ev.region`); the new behavior only kicks in across ADK's call boundaries.

**Verification:** Manual replay of 4 scenarios (happy / single-retry-no-swap / model-swap / mixed) produces the expected single-walk chip every time.

### 12.3 Failover chip separator `⤳` → `↪` (model-fallback semantic)

**Why it matters:** `⤳` (U+2933 wave arrow) is visually vague — reads as "approximately" or "informal then". `↪` (U+21AA "rightwards arrow with hook") is the canonical UI glyph for "redirected to / fell back to" (Slack, GitHub, mail clients). Matches the model-fallback semantic exactly.

**Files:** `netpulse-ui/templates/chat.html` (`sep.textContent = ' ↪ '` + 3 doc-comment occurrences).

**Verification:** `curl -s /app | grep -oE '↪|⤳'` on `netpulse-ui-00019-t46` returns `↪` only; no leftover wave arrows.

### 12.4 Call-status pill on `call_records` viewer

**Why it matters:** The Call Records viewer rendered `call_status` as bare text while Network Events badged `severity` and Incident Tickets badged `category`. Visual inconsistency made the call-status column harder to scan in the demo.

**Files:** `netpulse-ui/templates/call_records.html` (table cell renderer), `netpulse-ui/static/style.css` (3 new modifier classes).

**Change:** Added `<span class="np-badge np-badge-call-{value}">` rendering pattern matching the existing severity/category pills, plus 3 modifier classes (`np-badge-call-completed` → `--np-status-resolved` emerald, `np-badge-call-dropped` → `--np-status-major` orange, `np-badge-call-failed` → `--np-status-critical` red) reusing semantic tokens — no new colors invented.

**Verification:** Live page on `netpulse-ui-00015-24q` rendered 130 completed (emerald) / 38 dropped (orange) / 32 failed (red) pills in the default unfiltered view (200 row LIMIT cap).

### 12.5 Cloud Run deploy fix — Dockerfile build from project root

**Why it matters:** Two consecutive deploys (`netpulse-ui-00014-kc8`, `00015-24q`) silently used **Buildpacks** instead of the root `Dockerfile`, because the deploy command was issued from inside `netpulse-ui/` so `--source .` resolved there — and Buildpacks built a Python image from netpulse-ui/ in isolation without `telecom_ops/`. Result: every `/api/query` call surfaced `ModuleNotFoundError: No module named 'telecom_ops'` from the cross-package import in `agent_runner.py`. Viewer routes worked (they don't import `telecom_ops`) so the regression was invisible to the smoke tests that hit `/network-events`, `/call-records`, `/tickets`.

**Files:** None (deploy procedure change only).

**Change:**
1. Compared zip uploads across revisions (`gs://run-sources-.../services/netpulse-ui/*.zip`): the last known-good `00010-mqc` zip contained the whole project root (`Dockerfile`, `telecom_ops/`, `netpulse-ui/`, `scripts/`); `00014` + `00015` zips contained only netpulse-ui/ contents. Confirmed Buildpacks ran by inspecting the Cloud Build steps: `serverless-runtimes/google-24-full/builder/universal` instead of a Dockerfile build.
2. Future deploys must use `--source /home/adityonugrohoid/projects/hackathon-telecom-ops` (absolute path) so source resolution doesn't depend on shell CWD.
3. Switching back from Buildpacks to Dockerfile required `--clear-base-image` once (the Buildpacks deploys had set a base-image annotation for auto security patches). Subsequent Dockerfile deploys don't need it.

**Captured as memory:** `~/.claude/memory/reference_gcloud_run_source_dockerfile.md` (NEW) — the auto-detect priority, the absolute-path fix, the `--clear-base-image` requirement.

**Verification:** `00016-qsq` redeploy banner read "Building using Dockerfile"; `/api/query` SSE stream emitted `region_attempt` events with `agent: classifier` etc. — confirming `from telecom_ops.agent import root_agent` resolved.

---

## 6. Out of scope (under freezes — do not propose)

| Item | Why |
|---|---|
| Switching `plated-complex-491512-n6` off trial billing onto paid `018A4E` | Freeze B (paid billing held at zero linked projects indefinitely) |
| Modifying `boon-explorer` Cloud Run service | Excluded from Freeze A but not part of NetPulse — no business reason to touch |
| AlloyDB cluster resize / region migration | Freeze A (production hackathon resource) |
| Closing, re-linking, or modifying `018A4E` billing | Freeze B |
| `gcloud projects update` / `services enable/disable` on hackathon project | Freeze A |
| Re-deploying any Cloud Run service without explicit user confirmation | Freeze A boundary — user runs all `gcloud run deploy/update` commands manually |

---

## 7. Decision points for the user

1. **Authorize Tier 1 source-only items?** (1.1, 1.2, 1.3, 1.4, 1.5 — total ~3h, no infra changes.)
2. **Authorize Tier 1 config items?** (1.6 minScale=1 on netpulse-ui, 1.7 maxScale on network-toolbox — both Cloud Run writes inside hackathon project.)
3. **Authorize Tier 3 implementation?** (Region failover per `PLAN-vertex-region-failover.md` — half-day source work + you trigger the redeploy.)
4. **Pick UI redesign subset:** which of §5.0a–§5.11 enter Tier 2 active scope vs stay deferred? Recommendation for the 5-day window: **§5.0a (token foundation, prerequisite) → §5.11 (landing page) + §5.2 (timeline) + §5.3 (badges) + §5.5 (impact card) + §5.4 (action chips, static version)**. These six items together = ~18h of work and produce the biggest visible-in-5-min judging signal — tokens give every component visual coherence, landing page sets the narrative, timeline + badges + impact card transform the chat into an operator workspace, action chips suggest workflow integration. **§5.0a must land first** because §5.3 (badges), §5.11 (landing typography), §5.2 (timeline spacing), and §5.5 (impact card surface colors) all consume tokens defined there.
5. **Defer §5.1 (three-pane workspace) and §5.6 (status workflow)** to post-Top-10 unless we're confident on the deadline math? Both are excellent but each is half-day-plus.
6. **Promote any §4 brainstorming items to Tier 1/2?** §4.4 (demo seed panel) is a strong Tier-2 candidate — small effort, high demo-friction reduction.
7. **Authorize §2.12 BYO-data foundation?** Closes the audit-confirmed reproducibility gap (`call_records` DDL + `network_events` schema currently out-of-repo) AND delivers the SaaS-ready story without building actual multi-tenancy. ~3.5h, fits Day 5 alongside §2.7. The repro gap is a real bug — recommend authorizing regardless of whether the BYO-data narrative is wanted in the deck, because the repo is otherwise un-cloneable.

---

## Appendix — verified state at audit time (2026-04-25)

### Cloud Run services — read-only describe
| Service | Image rev | CPU/Mem | minScale | maxScale | Concurrency | Source revisions |
|---|---|---|---|---|---|---|
| netpulse-ui | 00001-s2x | 1 vCPU / 512 MiB | 0 | 100 | 80 | 1 (never iterated) |
| telecom-classifier | 00003-8fb | 1 / 512 | 0 | 3 | 80 | 3 |
| network-status-agent | 00008-b5h | 1 / 512 | 0 | 3 | 80 | 8 |
| telecom-cdr-app | 00002-t45 | 1 / 512 | 0 | 3 | 80 | 2 |
| network-toolbox | 00002-7f7 | 1 / 512 | 0 | 3 | 80 | 2 |
| telecom-ops-assistant | 00001-v62 | 1 / 512 | 0 | 100 | 80 | 1 |

### Live URL probes
- Cold first hit: HTTP 302 in **7.245s** (redirect to /chat).
- Warm: 0.40s · 0.40s.
- POST /api/query (SSE) ran the full 4-agent pipeline cleanly, generated **ticket #66**, exit 0.

### Inconsistency caught during audit
- `network_investigator` returned 9 BigQuery events for Jakarta but summarized only 4 in the user-facing text — see §1.4.

### Repo state
- Confirmed via `find`: zero test files (no `test_*.py`, no `tests/` directory).
- `Dockerfile` confirmed `--workers 1 --threads 8` (Gunicorn).
- All 6 deployed services use `BQ_PROJECT`, `DATABASE_URL`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_GENAI_USE_VERTEXAI` env-var combinations as expected.
