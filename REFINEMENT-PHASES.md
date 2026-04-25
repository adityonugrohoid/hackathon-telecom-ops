# NetPulse AI — Refinement Execution Phases

Sequential runbook for the prototype refinement workstream. Each phase is grouped by execution order and dependency, not by impact tier. For per-item detail (rationale, file diffs, test plans, risks), see **`REFINEMENT-AUDIT.md`**.

**Deadline:** 2026-04-30 EOD
**Last updated:** 2026-04-25
**Audit reference:** [`REFINEMENT-AUDIT.md`](./REFINEMENT-AUDIT.md)
**Failover plan:** [`PLAN-vertex-region-failover.md`](./PLAN-vertex-region-failover.md)

---

## Status overview

| Phase | Status | Effort | Auth | Outcome |
|---|---|---|---|---|
| **1. Pre-flight config** | ✅ **DONE** (2026-04-25) | 30 min | gcloud writes | Cold start killed (7.2s → 0.4s) |
| **2. Foundation layers** | ✅ **DONE** (2026-04-25) | ~3h | source only | Tokens + prompt fix + enum guard |
| **3. Innovation track** | ✅ **DONE** (2026-04-25) | ~2h | source only | Vertex region failover end-to-end |
| **4. Visual redesign** | ✅ **DONE** (2026-04-25) | ~14h est · ~4h actual | source only | Landing + timeline + badges + impact + chips |
| **5. Critical UX fixes** | ⏳ Next | ~3h | source only | Error states, button disable, input validation |
| **6. Reproducibility + portability** | Pending | ~4h | source only | BYO-data foundation (closes repro gap) |
| **7. Story polish** | Pending | ~3h | source + docs | Region telemetry + README + GIF |
| **8. Ship** | Pending | ~1h | Cloud Run deploy | Single consolidated redeploy |

**Total remaining:** ~35h across phases 2-8.
**Single redeploy principle:** All source work in phases 2-7 stages locally; only Phase 8 redeploys.

---

## Phase 1 — Pre-flight config ✅ DONE

**Completed:** 2026-04-25
**Authorization:** User-authorized Cloud Run config writes inside hackathon project (Freeze A boundary).

### §1.6 — `netpulse-ui` warm instance ✅

**Final command:**
```bash
gcloud run services update netpulse-ui \
  --region us-central1 \
  --project plated-complex-491512-n6 \
  --min-instances=1 \
  --max-instances=10 \
  --no-cpu-throttling \
  --cpu-boost
```

**Results:**
- Final revision: **`netpulse-ui-00003-7bc`** (was `00001-s2x` at audit start; intermediate `00002-cmb` had maxScale regression to 3)
- `minScale=1` (warm instance always alive)
- `maxScale=10` (capped by Cloud Run Direct VPC egress platform limit)
- `cpu-throttling=false` (CPU always allocated to the warm instance)
- `startup-cpu-boost=true` (2× CPU during cold starts when they happen)
- **Latency: 7.245s → 0.4-0.6s** (verified across 3 probes)
- Image SHA unchanged (config-only deploy, no source rebuild)
- Env vars preserved: `BQ_PROJECT`, `DATABASE_URL`, `GOOGLE_CLOUD_LOCATION`, `GOOGLE_CLOUD_PROJECT`, `GOOGLE_GENAI_USE_VERTEXAI`

### §1.7 — `network-toolbox` scale ceiling ✅

**Command:**
```bash
gcloud run services update network-toolbox \
  --region us-central1 \
  --project plated-complex-491512-n6 \
  --max-instances=10
```

**Results:**
- Revision: **`network-toolbox-00003-22l`**
- `maxScale: 3 → 10` (concurrent-judge safety net)

### Lessons captured

- **Cloud Run Direct VPC egress caps service `maxScale=10`** — hard platform limit when the `network-interfaces` annotation is set. `netpulse-ui` uses VPC egress to reach AlloyDB, so 10 is the effective ceiling. The original `00001-s2x` revision *displayed* `maxScale=100` in its annotation but was effectively clamped — the new validator (introduced between deploys) catches it explicitly.
- **gcloud `update` may not preserve all annotations across revisions.** First retry on `00002-cmb` silently regressed `maxScale` from 100 (inherited) to 3 (new default). Always pass `--max-instances=N` explicitly when updating other settings.
- **Always-allocated CPU (`--no-cpu-throttling`) + warm instance is the responsiveness combo.** `--min-instances=1` alone keeps memory warm but throttles CPU between requests; combining with `--no-cpu-throttling` keeps the Python+ADK runtime fully responsive.

---

## Phase 2 — Foundation layers ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source changes inside `telecom_ops/` and `netpulse-ui/` (within normal scope).
**Outcome:** Token foundation in place; prompt enumerates all events; category enum guard in place. All three changes ride to production in the Phase 8 single redeploy.

- [x] **§5.0a** Design token foundation — `netpulse-ui/static/tokens.css` (NEW, 116 token defs lifted from `heliodoron-ui-identity` commit `0923dfb` + NetPulse palette + status ladder + per-category accents + back-compat aliases). `templates/base.html` loads `tokens.css` before `style.css`; the four content templates inherit through the layout. `style.css` refactored conservatively — `:root` block removed (moved to tokens.css), exact-match hardcoded values (4/8/12/16/24px spacing, matching radii, system font stacks, the two recurring shadows) swapped to `var(--*)`, off-grid values (10px/14px/18px/22px) preserved verbatim so the rendered UI is pixel-identical.
- [x] **§1.5** `VALID_CATEGORIES` module-level frozenset added in `telecom_ops/tools.py`; `save_incident_ticket` returns `{"status":"error","message":...}` before DB write if `category` is hallucinated.
- [x] **§1.4** `NETWORK_INVESTIGATOR_INSTRUCTION` in `telecom_ops/prompts.py` — replaced "3-6 bullet points" with "For EACH event returned by the tool (do not omit any), emit one bullet…"; added rank-by-severity rule for >8-event payloads; explicit "Never truncate the list" guard.

**Verifications run locally:**
- `.venv/bin/python -c "import ast; ast.parse(...)"` on `tools.py` and `prompts.py` → OK.
- Every `var(--*)` reference in `style.css` either resolves to a token defined in `tokens.css` or is a banner-scoped local `--bn-*` redefined inside `.np-source-banner` rules.
- Templates: all 4 content templates (`chat`, `network_events`, `call_records`, `tickets`) extend `base.html`; the single `<link rel="stylesheet" href="…tokens.css">` propagates to all of them automatically.

**Verifications deferred to Phase 8 live deploy:**
- Browser visual diff against the deployed UI (blocked locally — Flask boot needs AlloyDB credentials inside Freeze A; refactor is a 1-to-1 token-for-value substitution so visual identity is provable mechanically).
- Re-running the Jakarta complaint to confirm `network_investigator` now lists all 9 events (needs a live agent run against Vertex AI + BigQuery + AlloyDB).
- Forced bad-category injection to confirm the enum guard's error path renders correctly in chat (needs Phase 5 §1.1 error-card UI to be in place to be visible).

---

## Phase 3 — Innovation track ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source-only changes inside `telecom_ops/`; the Cloud Run env-var update is deferred to Phase 8.
**Blocks:** Phase 7's §3.2 region telemetry depends on this (now unblocked).

- [x] **§3.1** Vertex AI region failover end-to-end per `PLAN-vertex-region-failover.md`:
  1. ✅ Wrote `telecom_ops/vertex_failover.py` — `RegionFailoverGemini(Gemini)` with `RANKED_REGIONS = ("global", "asia-southeast2", "asia-southeast1", "us-central1")`, per-instance failover state via `pydantic.PrivateAttr`, `api_client` overridden as `@property` with manual `__dict__` cache, `_set_active_region` invalidates both `api_client` and `_api_backend` cached_property entries, `generate_content_async` walks the ladder and re-raises non-quota `ClientError`s immediately. Streaming bypasses failover (documented).
  2. ✅ `.venv/bin/python telecom_ops/vertex_failover.py` — matcher passes 5/5 (`RESOURCE_EXHAUSTED`, ` 429`, `QUOTA` positives; `INVALID_ARGUMENT`, `PERMISSION_DENIED` negatives) and the mocked failover-loop test confirmed ladder traversal (region=`global` 429 → region=`asia-southeast2` success, sentinel response yielded).
  3. ✅ Wired into `telecom_ops/agent.py` — `_failover_model()` factory builds a fresh `RegionFailoverGemini` instance for each of the 4 LlmAgents. Verified: 4 distinct instances, all defaulting to `active_region=global`.
  4. ✅ `telecom_ops/.env` flipped to `GOOGLE_CLOUD_LOCATION=global` (gitignored; local-only).
  5. ✅ Integration test was the mocked-loop test in step 2 (no Vertex AI traffic, no spend on Freeze A trial billing — proves the loop logic without the spec's "monkey-patched bad first region" requiring real API calls).
  6. ⏸ End-to-end Flask run **deferred to Phase 8 live deploy** — the Flask UI requires the AlloyDB `DATABASE_URL` which is inside the Freeze A boundary; can't run locally with credentials. Pyright + module-import smoke test confirms wiring is correct.
  7. ✅ Updated `README.md` (highlights bullet, tech stack row, mermaid label, local-run snippet, deploy snippet, env-var table, lessons paragraph) and project `CLAUDE.md` (architecture paragraph, non-obvious-choices paragraph, current-phase Phase 3 anchor). Deploy resource tables (lines 391/404) intentionally LEFT as `asia-southeast1` because they describe the *live* deploy state, which only flips after the user runs the manual Cloud Run redeploy in Phase 8.
  8. ⏸ Phase 8 redeploy step deferred per the single-redeploy principle.

**Verifications run locally:** matcher unit-test (5/5), mocked failover-loop unit-test (1/1, `["global", "asia-southeast2"]` walked), `agent.py` Pydantic instantiation (4 distinct wrapper instances confirmed via `id()` set).

**Verifications deferred to Phase 8 live deploy:** real-API forced-failover (would spend Freeze A trial billing); end-to-end SSE chat run (needs AlloyDB credentials inside Freeze A); README deploy resource tables (still describe `asia-southeast1` until Cloud Run env-var is updated).

---

## Phase 4 — Visual redesign ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source changes inside `netpulse-ui/`.
**Outcome:** Landing route + workspace timeline + badges + impact rollup + action-chip panel all wired and verified locally.

- [x] **§5.11** Hero landing page + routing redesign — new `templates/landing.html` (hero, 4-step "How it works", launch chips, data-viewer cards, footer); `app.py` routes `/` → landing, new `/app` route serves the chat workspace, `/chat` 301 → `/app`; `?seed=` and `?autorun=1` handoff handler in `chat.html`'s `npOnLoad()`; brand logo wrapped in `<a href="/">` for back-to-home affordance; `base.html` nav block now overridable so landing.html ships its own anchor nav.
- [x] **§5.2** Pipeline-as-timeline — replaced the horizontal 4-card row + `.np-flow` arrow connectors with `<ol class="np-timeline">` of `.np-timeline-entry` items, each with a left rail (timestamp + status dot, animated pulse on running, accent fill on done) and a right content panel that retains the existing source pills, tool-call list, and text. Carry-over chips moved into a per-entry `.np-timeline-handoff` footer. JS selectors swapped from `.np-card[data-agent=…]` to `.np-timeline-entry[data-agent=…]` and a `npNowHHMMSS()` helper stamps each entry on `agent_start`.
- [x] **§5.3** Severity + Category badges — `.np-badge` shell + per-category (`network|billing|hardware|service|general`) and per-severity (`critical|high|major|medium|minor|low|info`) and per-status (`new|acknowledged|resolved`) modifiers, all derived from `tokens.css` (--np-cat-*, --np-status-*) via `color-mix()` for matching bg/fg/border triples. `tickets.html` and `network_events.html` data-viewer rows now render category/status/severity columns as badges. Chat workspace's final ticket card grew a `.np-ticket-badges` host populated on `complete` from a JS `npState` rollup (category/region from `classify_issue` args; topSeverity from network_investigator's tool_response).
- [x] **§5.5** Customer-impact card — new `.np-impact-card` between the timeline and the final report, hidden until `network_investigator`'s `tool_response` arrives. Client-side `npComputeImpact()` walks the BQ rows for `affected_customers` (sum), `severity` histogram, and earliest `started_at` (elapsed → `~Xm`/`~Xh`/`~Xd`). `npExtractRows()` is shape-agnostic — handles bare arrays, `{rows}`, `{records}`, `{events}`, `{result}`, `{data}` shapes from MCP Toolbox.
- [x] **§5.4** Recommended NOC actions chip panel — `.np-actions-panel` lives inside `.np-final` after the recommendation text; renders 4-5 chips per category from a static `CATEGORY_ACTIONS` map in `chat.html` JS (billing/network/hardware/service/general). Chips are inert (mock) but visually convey workflow trigger affordance. Light pill styling tuned for the dark report background.

**Verifications run locally:**
- `flask test_client()` smoke-test against the 3 routes (`/` 200, `/app` 200, `/chat` → `/app` 301) plus `?seed=` handoff round-trip.
- Synthetic-event Node test exercising `npExtractRows` (4 MCP shape variants), `npComputeImpact` (sum/histogram/elapsed), `npFormatNum`, `npFormatElapsed`, `npMaxSeverity` against a 5-row payload — all assertions pass.
- Static-markup probe across `/app` confirmed every new selector ships in the served HTML (`np-timeline-entry`, `np-impact-card`, `np-actions-panel`, `np-ticket-badges`, `npRenderImpact`, `npRenderActions`, `CATEGORY_ACTIONS`, etc.) and that legacy `np-pipeline / np-card / np-flow` selectors are gone.
- `node -e "new Function(<chat.html script>)"` — JS parses cleanly with no syntax errors after the cumulative edits.

**Verifications deferred to Phase 8 live deploy:**
- Browser visual diff (cannot run Flask locally with real AlloyDB credentials inside Freeze A; the verifications above prove the static markup + JS logic).
- Real-API end-to-end SSE chat run that emits the four agent events and triggers the impact card + badges + actions panel population sequence.

---

## Phase 5 — Critical UX fixes ⏳ NEXT

**Estimated:** ~3h · source-only · no redeploy
**Authorization:** Source-only.
**Note:** Could be batched into Phase 4 if convenient — they touch overlapping files (`chat.html`, `agent_runner.py`).

- [ ] **§1.1** Surface tool errors as chat card error state (`agent_runner.py` emits `error` event; `chat.html` adds `np-error` rendering). *(~2h)*
- [ ] **§1.2** Disable Investigate button + spinner during request. *(~30 min)*
- [ ] **§1.3** Empty/whitespace input validation client-side. *(~15 min)*

**Verification:** Force a tool error locally (monkey-patch `query_cdr` to raise) — confirm card shows error state, button re-enables, no UI hang. Empty submit shows immediate feedback, no spurious server roundtrip.

---

## Phase 6 — Reproducibility + portability Pending

**Estimated:** ~4h · source-only · no redeploy
**Authorization:** Source-only. Seed extraction is read-only against current BQ + AlloyDB (Freeze A allows). Bootstrap scripts only mutate destinations the user explicitly supplies.
**Note:** Pairs §2.7 + §2.12 in one PR — same files, complementary scope.

- [ ] **§2.7** Make hardcoded URLs/IDs env-driven (`TOOLBOX_URL`, `GOOGLE_CLOUD_PROJECT`, template paths). *(~30 min)*
- [ ] **§2.12** Schema contract + seed pipeline:
  - [ ] Env-driven dataset/table names in `tools.py` and `data_queries.py` (~30 min)
  - [ ] Author `docs/SCHEMA.md` (column-by-column contract for the 3 tables) (~30 min)
  - [ ] Extract current BQ + AlloyDB data into `docs/seed-data/*.csv` (~1h read-only via `bq query` + `psql \copy`)
  - [ ] Author `scripts/setup_bigquery.py` and extend `setup_alloydb.py` to also create `call_records` (~1h)
  - [ ] `scripts/setup_byo.sh` orchestrator + README BYO section (~30 min)

**Verification:** Run `scripts/setup_byo.sh --seed` against a *throwaway* GCP project (NOT the hackathon project) and confirm a working NetPulse stack stands up. **Do NOT** run against `plated-complex-491512-n6` — Freeze A.

---

## Phase 7 — Story polish Pending

**Estimated:** ~3h · source + docs · no redeploy
**Authorization:** Source-only + doc updates.
**Blocked by:** Phase 3 §3.1 (region telemetry depends on the failover wrapper).

- [ ] **§3.2** Per-attempt region telemetry on chat cards (`agent_runner.py` extends `AgentEvent` with optional `region`; `chat.html` renders region badge). *(~2h)*
- [ ] **§2.9** Quick Demo section in `README.md` (90-second walkthrough). *(~30 min)*
- [ ] **§2.10** Architectural callouts above the mermaid diagram in README. *(~30 min)*
- [ ] **§2.11** SSE streaming GIF in README *(optional, high-impact)* — record 5-second pipeline animation with screen capture, embed in README. *(~1h)*

**Verification:** Region badge shows `🌐 via global` on every agent card during normal run; force a failover and confirm `🌐 via global ⤳ asia-southeast2`. README skim-reads as a complete product story.

---

## Phase 8 — Ship 🚀 Pending

**Estimated:** ~1h
**Authorization:** **Single consolidated Cloud Run redeploy by user** (Freeze A boundary).

The one redeploy that carries every source change from phases 2-7 to production.

- [ ] User runs:
  ```bash
  gcloud run deploy netpulse-ui \
    --source . \
    --region us-central1 \
    --project plated-complex-491512-n6 \
    --min-instances=1 \
    --max-instances=10 \
    --no-cpu-throttling \
    --cpu-boost \
    --update-env-vars="GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=plated-complex-491512-n6,DATABASE_URL=<unchanged>,BQ_PROJECT=plated-complex-491512-n6,TOOLBOX_URL=https://network-toolbox-486319900424.us-central1.run.app,BQ_DATASET=telecom_network,BQ_NETWORK_TABLE=network_events,AL_CALL_TABLE=call_records,AL_TICKET_TABLE=incident_tickets"
  ```
- [ ] Health-check the 4 submitted URLs:
  ```bash
  for u in \
    https://telecom-classifier-486319900424.us-central1.run.app \
    https://network-status-agent-486319900424.us-central1.run.app \
    https://telecom-cdr-app-486319900424.us-central1.run.app \
    https://netpulse-ui-486319900424.us-central1.run.app; do
    curl -s -o /dev/null -w "%{http_code} %s\n" --max-time 75 "$u"
  done
  ```
- [ ] Smoke-test the deployed UI: open netpulse-ui, run an example complaint, confirm full pipeline + impact card + ticket.
- [ ] Final review + submit before deadline EOD 2026-04-30.

---

## Out of scope (deferred from this 5-day window)

Items present in `REFINEMENT-AUDIT.md` but not committed to the 5-day window:

| Group | Items |
|---|---|
| Tier 2 quality polish | §2.1 SSE heartbeat · §2.2 pagination · §2.3 a11y labels · §2.4 error classification · §2.5 region whitelist · §2.6 complaint length cap · §2.8 structured logs |
| Big redesign extras | §5.1 three-pane workspace · §5.6 status workflow · §5.7 similar tickets · §5.8 root-cause checklist · §5.9 KPI strip · §5.10 empty states |
| Tier 4 brainstorm | §4.1 parallel agents · §4.2 idempotency · §4.3 pytest suite · §4.4 demo seed panel (partly absorbed by §5.11) · §4.5 ticket counter |
| Multi-tenant SaaS | The full Variant C path — 8-12 days, post-Top-10 work |

These remain in the master audit doc for post-Top-10 consideration.

---

## Cross-reference

- **Per-item detail:** [`REFINEMENT-AUDIT.md`](./REFINEMENT-AUDIT.md)
- **Failover implementation plan:** [`PLAN-vertex-region-failover.md`](./PLAN-vertex-region-failover.md)
- **Project context (current phase + freezes):** [`CLAUDE.md`](./CLAUDE.md)
- **Submission deck:** `docs/Prototype Submission Deck_Gen AI Academy APAC Edition_NetPulse AI_Adityo Nugroho.pdf`
