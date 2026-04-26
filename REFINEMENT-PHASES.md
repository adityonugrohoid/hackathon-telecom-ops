# NetPulse AI — Refinement Execution Phases

Sequential runbook for the prototype refinement workstream. Each phase is grouped by execution order and dependency, not by impact tier. For per-item detail (rationale, file diffs, test plans, risks), see **`REFINEMENT-AUDIT.md`**.

**Deadline:** 2026-04-30 EOD
**Last updated:** 2026-04-26
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
| **5. Critical UX fixes** | ✅ **DONE** (2026-04-25) | ~3h est · ~1h actual | source only | Error states, button disable, input validation |
| **6. Reproducibility + portability** | ✅ **DONE** (2026-04-25) | ~4h est · ~1.5h actual | source only | BYO-data foundation (env-driven, schema, seed pipeline) |
| **7. Story polish** | ✅ **DONE** (2026-04-25) | ~3h est · ~1.5h actual | source + docs | Region telemetry chip + README Quick Demo + architectural callouts |
| **8. Ship** | ✅ **DONE** (2026-04-26) | ~1.5h | Cloud Run deploy | First production deploy of Phases 2-7 (rev `00004-sfn`); revs `00005-ns6` (env-typo fix), `00006-7v8` (heliodoron tokens), `00007-x7t` (pandan unification), `00008-kzk` (5s timeout + 3.1 previews), `00009-f2c` (multi-continent ladder), `00010-mqc` (Phase 9 round 2) carried Phase 9 polish |
| **9. Post-deploy polish + robustness** | ✅ **DONE** (2026-04-26) | ~5h | source + deploys | Heliodoron identity v1 + round 2 (header darker, done-state pandan unification, impact-card extractor + layout fix), 5s hang timeout, region failover hardening, multi-continent ladder, Flash-Lite collapse for all 4 agents (resolves Pro-preview region-whitelist surprise) |
| **10. Toolbox refactor + seed enrichment** | ✅ **DONE** (2026-04-26) | ~5h | source + 2 deploys + BQ/AlloyDB writes | 8 MCP tools collapsed to 2 universal parameterized (`network-toolbox-00005-...`); query_cdr parameterized (days_back/call_type/limit); seed extended to 10 cities (132 events, 500 CDRs); ALLOWED_SEVERITIES vocab bug fixed; setup_alloydb.py bulk-insert patched |

**Single redeploy principle held for Phases 2-7** (one redeploy carried everything). Phase 9 ran in iterative polish-and-redeploy mode against a warm `min-instances=1` service — each iteration ~3-5 min, settling on revision `00010-mqc`. Phase 10 will redeploy two services (`network-toolbox` + `netpulse-ui`).

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

## Phase 5 — Critical UX fixes ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source changes inside `netpulse-ui/`.
**Outcome:** Tool errors now surface as agent-scoped sticky red state on the matching timeline entry; the submit button locks + spins while a request is in flight; empty/whitespace submits show an inline hint instead of failing silently.

- [x] **§1.1** Surface tool errors as agent-scoped chat card error state — new `_extract_tool_error()` helper in `netpulse-ui/agent_runner.py` detects two response shapes (NetPulse-native `{"status":"error","message":...}` like `save_incident_ticket`'s enum guard, and ADK's exception-wrapping `{"error":"<str>"}` shape from uncaught tool exceptions); `_convert_event` emits an additional `AgentEvent(type='error', agent, tool, message)` after the underlying `tool_response`. `chat.html` `npHandle` routes `ev.type==='error'` with an `agent` to `npRenderAgentError()` (red dot, red border-left, error status badge, inline `.np-error-msg` block placed above the handoff footer); `agent`-less catastrophic errors still flow through `npRenderGlobalError()` which now sets a tinted `.np-final-error` modifier on the report card. The `text` event branch was hardened so trailing model commentary on a failed agent does not clobber the sticky `.error` state.
- [x] **§1.2** Disable Investigate button + spinner during request — new `npSetBusy(on)` helper locks `#np-input` + `#np-submit`, swaps the button label to "Investigating", and toggles a `.np-busy` class that drives a CSS-only `::before` spinner. `npSubmit` wraps the SSE stream loop in `try/finally` so the busy state always clears — including on network errors mid-stream (caught and routed through `npRenderGlobalError`). Disabled tones derive from `--np-neutral-100/300/650`; the busy background uses `--np-primary-dark` so the disabled-but-active affordance reads as "working" not "broken".
- [x] **§1.3** Empty/whitespace input validation client-side — new persistent `<div id="np-input-hint" hidden>` element next to the form; `npSubmit` calls `npFlashInputHint('Type a complaint first — empty queries are not investigated.')` and bails before the network round-trip when `.trim()` produces an empty string. The hint clears automatically on the next keystroke via an `input` listener wired in `npOnLoad()`. `role="alert"` + `aria-live="polite"` for screen-reader users. The server-side guard in `app.py` (`'empty query'` SSE event) is preserved as a defense-in-depth check.

**Verifications run locally:**
- AST parse of `agent_runner.py` and a 4-case synthetic `_convert_event` test (NetPulse `status='error'` shape, ADK `{error:str}` shape, success shape, `AgentEvent.to_dict` shape) — all pass.
- `node -e "new Function(<chat.html script>)"` JS syntax probe + symbol grep for the 9 new identifiers (`npSetBusy`, `npFlashInputHint`, `npClearInputHint`, `npRenderAgentError`, `npRenderGlobalError`, `np-busy`, `np-input-hint`, `np-error-msg`, `np-final-error`) — all present.
- `flask test_client()` smoke against `/`, `/app`, `/chat` (still 200/200/301), plus `POST /api/query` with empty body confirming the existing server-side guard fires.
- CSS token sanity scan: 0 unresolved `var(--*)` references introduced by Phase 5 (the 5 pre-existing inline-defined `--c-*-fg` tokens are detection-method false positives, present in tokens.css since Phase 2).

**Verifications deferred to Phase 8 live deploy:**
- Real-API forced tool error (e.g., monkey-patch `query_cdr` to raise) end-to-end through the SSE stream into the timeline entry — needs AlloyDB credentials + Vertex AI traffic, both inside Freeze A.
- Visual regression: confirm the spinner, error-tinted timeline entry, and inline input hint all render with the live tokens against the production background.

---

## Phase 6 — Reproducibility + portability ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source-only. Seed extraction was read-only against current BQ + AlloyDB (Freeze A allows). Bootstrap scripts only mutate destinations the user explicitly supplies — they were NOT executed against `plated-complex-491512-n6`.
**Note:** §2.7 + §2.12 landed together — they touch the same files and share the BYO contract surface.
**Outcome:** A fresh `git clone` plus `bash scripts/setup_byo.sh --seed` against a new GCP project + AlloyDB cluster now stands up an end-to-end working NetPulse stack with the canonical sample data. The data layer is fully relocatable; only the contract documented in `docs/SCHEMA.md` is load-bearing.

- [x] **§2.7** Make hardcoded URLs/IDs env-driven — `TOOLBOX_URL` is now a required env var in `telecom_ops/tools.py` (raises with an actionable message if missing), `GOOGLE_CLOUD_PROJECT` is required in `netpulse-ui/data_queries.py` (was silently defaulting to the hackathon project ID — removed so a fork fails fast instead of pointing at the wrong project). The four hardcoded `plated-complex-491512-n6.telecom_network.network_events` / `call_records` / `incident_tickets` strings in `templates/{chat,network_events,call_records,tickets}.html` are now Jinja-driven via a new `inject_dataset_names` Flask context processor in `app.py`. README env-vars table and local-dev export snippet updated to document `TOOLBOX_URL`, `BQ_DATASET`, `BQ_NETWORK_TABLE`, `AL_CALL_TABLE`, `AL_TICKET_TABLE`. Phase 8 deploy snippet now sets `TOOLBOX_URL=...` so the redeploy carries the env-driven contract to production.
- [x] **§2.12a** Env-driven dataset/table names — `BQ_DATASET`, `BQ_NETWORK_TABLE`, `AL_CALL_TABLE`, `AL_TICKET_TABLE` added in `data_queries.py` (defaults preserve current behavior); `AL_CALL_TABLE`, `AL_TICKET_TABLE` mirrored in `telecom_ops/tools.py` and substituted into the two SQL strings (`FROM {AL_CALL_TABLE}`, `INSERT INTO {AL_TICKET_TABLE}`). Pyright caught a real reference orphan during the rename (`BQ_TABLE` → `BQ_NETWORK_TABLE` in the BigQuery FROM clause); fixed before commit.
- [x] **§2.12b** `docs/SCHEMA.md` authored — column-by-column contract for the three tables (BQ `network_events`, AlloyDB `call_records`, AlloyDB `incident_tickets`), including the shared `region` vocabulary and the `VALID_CATEGORIES` enum invariant. Enum values for `event_type`, `severity`, and `region` taken from a live `bq query` against the production dataset (read-only, Freeze A allows).
- [x] **§2.12c** Seed CSVs extracted to `docs/seed-data/` — `network_events.csv` (30 rows, via `bq query --format=csv`), `call_records.csv` (50 rows, via SQLAlchemy + pg8000 against the AlloyDB public IP `35.225.53.8`), `incident_tickets.csv` (10 sample rows of the 68 in source, ordered by `ticket_id`). All extraction was read-only and used the project venv's `pg8000`; no `psql` client was needed. Verified row counts via `csv.DictReader`.
- [x] **§2.12d** `scripts/setup_bigquery.py` authored — argparse-driven, idempotent dataset + table creation via `google.cloud.bigquery`, optional `--seed` loads `network_events.csv` with `WRITE_TRUNCATE` so re-runs restore the canonical state. `setup_alloydb.py` extended to also create `AL_CALL_TABLE` (with the full 10-column DDL inferred from `data_queries.py`'s SELECT list), with optional `--seed` that TRUNCATEs both tables and reloads from the CSVs. After loading, both SERIAL sequences (`call_records_call_id_seq`, `incident_tickets_ticket_id_seq`) are advanced via `setval(..., MAX(id) + 1, false)` so the next agent insert doesn't collide with seeded IDs.
- [x] **§2.12e** `scripts/setup_byo.sh` orchestrator + README "Bring your own data" section — bash script runs `setup_bigquery.py` then `setup_alloydb.py` in sequence, validates `GOOGLE_CLOUD_PROJECT` and `DATABASE_URL` are exported, prefers the project's `.venv/bin/python` when present, propagates the optional `--seed` flag to both scripts. README gained a top-level "Bring your own data" subsection between the data-viewer table and the Project Structure tree, plus updated Project Structure to list the new `scripts/` and `docs/SCHEMA.md` / `docs/seed-data/` paths. README "Configure the AlloyDB schema" snippet updated to mention `--seed` and the second table the script now creates.

**Verifications run locally:**
- AST parse of all 5 modified Python files (`telecom_ops/tools.py`, `netpulse-ui/data_queries.py`, `netpulse-ui/app.py`, `scripts/setup_bigquery.py`, `setup_alloydb.py`) — all OK.
- Module-import smoke against env-driven defaults — all 8 env-driven constants load correctly with the hackathon's existing values.
- BYO-override propagation test via `flask test_client()` — set `GOOGLE_CLOUD_PROJECT=customer-acme`, `BQ_DATASET=acme_telecom`, `BQ_NETWORK_TABLE=outage_events`, `AL_CALL_TABLE=cdr_v2`, `AL_TICKET_TABLE=noc_tickets`; rendered `/app` HTML contains `customer-acme.acme_telecom.outage_events`, `<code>cdr_v2</code>`, `<code>noc_tickets</code>`.
- Required-env failure-path test — confirmed `RuntimeError` with actionable messages when `TOOLBOX_URL`, `GOOGLE_CLOUD_PROJECT`, or `DATABASE_URL` are missing.
- `flask test_client()` smoke against `/`, `/app`, `/chat` (still 200/200/301), `/network-events` (200, env-driven banner present).
- `bash -n scripts/setup_byo.sh` (syntax OK), `--foo` arg → "Unknown argument" exit 64, no-env → "ERROR: GOOGLE_CLOUD_PROJECT must be exported".
- `--help` text on both Python setup scripts renders with the env-var contract.
- Symbol grep — 0 surviving hardcoded `plated-complex-491512-n6.telecom_network.*` strings in source (only 3 surviving mentions are in narrative comments / context-processor docstring explaining what was replaced).

**Verifications deferred to Phase 8 live deploy + post-hackathon BYO test:**
- `scripts/setup_byo.sh --seed` against a *throwaway* GCP project — explicitly NOT run against `plated-complex-491512-n6` per Freeze A. Source is structurally complete; the only remaining unknown is whether the BigQuery `bigquery.LoadJobConfig` schema matches a freshly-created table's accept-list (the schema was lifted directly from a `bq show` of the live table, so structurally it should match).
- End-to-end Cloud Run redeploy with the new `TOOLBOX_URL=...` env var in `--set-env-vars`.
- Visual confirmation that the workspace data-source banner and the four data-viewer tab banners render the env-driven dataset path against the live tokens.

---

## Phase 7 — Story polish ✅ DONE

**Completed:** 2026-04-25
**Authorization:** Source + doc updates inside `telecom_ops/`, `netpulse-ui/`, and `README.md`.
**Outcome:** Per-attempt Vertex AI region telemetry now surfaces on every timeline entry as a `🌐 via global` chip (with a `⤳ asia-southeast2` extension on failover); README gained a 5-step Quick Demo walkthrough and a 6-bullet "What's load-bearing in the diagram" callouts block above the mermaid; the `region_attempt` SSE event shape is now documented so external integrators can subscribe. SSE GIF (§2.11) explicitly deferred — see verifications log.

- [x] **§3.2** Per-attempt region telemetry on chat cards — `RegionFailoverGemini` got two new `PrivateAttr`s (`_owner_name`, `_active_region` was already present) plus a `set_owner_name(name)` method so each wrapper instance carries the owning `LlmAgent.name`. A new module-level `set_attempt_observer(callback)` API stores the observer in a `ContextVar`, so concurrent Flask request threads each install their own callback in isolation. The wrapper's `generate_content_async` calls `_notify_attempt(self._owner_name, region, "ok"|"failover", err_msg)` after each attempt outcome, on both branches (failover loop AND streaming-bypass). `agent.py`'s `_failover_model(owner_name)` factory now takes the owner name and tags it on the wrapper before returning. `agent_runner.py` gained: (a) two new optional fields on `AgentEvent` (`region`, `outcome`); (b) docstring updates for the new `region_attempt` event type; (c) an `_on_region_attempt` closure inside `_agent_worker` that pushes `region_attempt` events onto the SSE queue, registered before `asyncio.run(_drain())` and unregistered in the `finally` block. `chat.html` got: (a) a `<span class="np-region-trace" hidden>` element appended to each of the 4 timeline entry headers; (b) a new `npRenderRegionAttempt(ev)` JS helper that progressively builds `via global` → `via global ⤳ asia-southeast2` → ... segments using nested spans (prefix + region + sep), guards against duplicate events on the streaming-bypass branch, and toggles a `np-region-trace-failover` modifier mid-walk; (c) wiring in `npHandle` to dispatch `region_attempt` events; (d) `npReset` clearing the trace chip on each new run. `style.css` got a new `.np-region-trace` block (compact pill, monospace, tokens-only — `--surface-sunken`, `--text-secondary/tertiary`, `--np-primary-dark`, `--np-status-major` for the failover tint). *(~2h est · ~50 min actual)*
- [x] **§2.9** Quick Demo section in `README.md` — new 5-step walkthrough between Overview and the existing heavy Demo section (which keeps the screenshots + observability tabs). Each step names a specific surface in the live UI: launch chip handoff, timeline animation with the new region chip, customer-impact card, saved ticket badges + NOC actions, persistence in the Incident Tickets tab. Closes with a pointer to the ADK Dev UI fallback for trace-level inspection. Also added Quick Demo to the Table of Contents. *(~30 min est · ~15 min actual)*
- [x] **§2.10** Architectural callouts above the mermaid diagram — new "What's load-bearing in the diagram" block of 6 bullets directly above the `\`\`\`mermaid` fence: (1) SequentialAgent + 4 LlmAgents not 1 big agent; (2) MCP Toolbox vs direct BigQuery MCP; (3) Vertex AI region failover-ranked not pinned (with the new per-attempt UI telemetry mention); (4) two frontends one engine; (5) async-to-sync thread+queue rationale; (6) AlloyDB read+write. The callouts make the diagram readable without having to reverse-engineer the design choices from the picture. *(~30 min est · ~15 min actual)*
- [x] Bonus polish landed in the same PR: (a) the existing region-failover Features bullet now mentions the visible-in-UI chip; (b) the Observability section's SSE event-shape sample now shows a `region_attempt` event with explanation of the failover variant. Total surface area for "what's new in Phase 7" reads consistently across hero → quick demo → features → architecture callouts → observability.
- [ ] **§2.11** SSE streaming GIF in README *(deferred)* — recording a screen-capture GIF of the live pipeline animation requires running the Flask UI in a real browser against the live AlloyDB instance, which is inside the Freeze A boundary (no source-only path to record this from Claude Code). The static screenshot at `docs/screenshots/net-pulse-ai-app_chat_adk_sequential.png` already covers the pipeline narrative for the deck; the live URL gives judges the real animation. Moved to post-deploy follow-up — should be recorded by the user after the Phase 8 redeploy lands, since the new region chip is a visual addition the GIF should capture too.

**Verifications run locally:**
- AST parse of all 3 modified Python files (`telecom_ops/vertex_failover.py`, `telecom_ops/agent.py`, `netpulse-ui/agent_runner.py`) — all OK.
- `.venv/bin/python telecom_ops/vertex_failover.py` — matcher 5/5 + mocked failover-loop walked `["global", "asia-southeast2"]`, yielded the sentinel, AND the registered observer fired exactly twice with shapes `("test_agent", "global", "failover", "<429 detail>")` then `("test_agent", "asia-southeast2", "ok", None)`.
- `agent.py` Pydantic instantiation smoke — 4 distinct `RegionFailoverGemini` instances, each `_owner_name` matching its `LlmAgent.name` (classifier / network_investigator / cdr_analyzer / response_formatter), all defaulting to `_active_region='global'`.
- `AgentEvent` round-trip — `region_attempt` events with both `outcome='ok'` (no message) and `outcome='failover'` (with upstream error string in `message`) round-trip cleanly through `to_dict()`; existing event types still strip `region`/`outcome` as None.
- Synthetic `_convert_event` regression test — confirmed `tool_call`, `tool_response`, `text` events still emit unchanged from a fake ADK event with FunctionCall/FunctionResponse/Content parts; `region`/`outcome` fields stay stripped when None.
- `node -e "(function(){<chat.html script>})"` — JS parses cleanly with the new `npRenderRegionAttempt` helper, the `npReset` chip cleanup, and the `npHandle` dispatch addition.
- `flask test_client()` smoke against `/`, `/app`, `/chat` — still 200 / 200 / 301; `/app` HTML now ships all 7 new symbols (`np-region-trace`, `npRenderRegionAttempt`, `region_attempt`, `np-region-trace-failover`, `np-region-trace-prefix`, `np-region-trace-region`, `np-region-trace-sep`) with 27 total matches across 4 chip elements (one per agent timeline entry).
- CSS token sanity — every token referenced by the new `.np-region-trace*` rules (`--surface-sunken`, `--text-secondary`, `--text-tertiary`, `--border-default`, `--np-primary-dark`, `--np-status-major`, `--font-mono`, `--weight-semibold`, `--weight-regular`, `--radius-pill`) resolves in `tokens.css`.
- Symbol grep across `telecom_ops/` + `netpulse-ui/` (Python + HTML + CSS) — `region_attempt` (14), `np-region-trace` (24), `set_attempt_observer` (7), `_notify_attempt` (4), `set_owner_name` (4), `_owner_name` (10), `npRenderRegionAttempt` (3), `_attempt_observer` (11), `AttemptCallback` (3) — all new identifiers ship to the right surfaces.

**Verifications deferred to Phase 8 live deploy:**
- Real-API end-to-end SSE chat run that emits `region_attempt` for each of the 4 agents on the happy path, plus a forced quota miss (e.g., a region monkeypatched to a known-bad value) to confirm the chip grows into `🌐 via global ⤳ asia-southeast2` visually. Both paths need AlloyDB credentials + Vertex AI traffic, both inside Freeze A.
- §2.11 SSE streaming GIF — the live UI is the only place to record it now that the new region chip is in the timeline.
- Visual sanity of the new chip against the live tokens — color-mix tints render correctly in modern browsers but the actual production Cloud Run static-asset cache needs the new `style.css` deployed.

---

## Phase 8 — Ship 🚀 ✅ DONE

**Completed:** 2026-04-26
**Authorization:** Single consolidated Cloud Run redeploy by user (Freeze A boundary).

The one redeploy that carried every source change from phases 2-7 to production.

- [x] User ran the deploy command (cleaned-up version, dropping the placeholder `DATABASE_URL=<unchanged>` segment so the existing AlloyDB URI rode through untouched via `--update-env-vars` merge semantics).
  ```bash
  gcloud run deploy netpulse-ui \
    --source . \
    --region us-central1 \
    --project plated-complex-491512-n6 \
    --min-instances=1 --max-instances=10 \
    --no-cpu-throttling --cpu-boost \
    --update-env-vars="GOOGLE_CLOUD_LOCATION=global,GOOGLE_GENAI_USE_VERTEXAI=TRUE,GOOGLE_CLOUD_PROJECT=plated-complex-491512-n6,BQ_PROJECT=plated-complex-491512-n6,TOOLBOX_URL=https://network-toolbox-486319900424.us-central1.run.app,BQ_DATASET=telecom_network,BQ_NETWORK_TABLE=network_events,AL_CALL_TABLE=call_records,AL_TICKET_TABLE=incident_tickets"
  ```
  - Result: revision **`netpulse-ui-00004-sfn`** serving 100% traffic.
  - **Two env vars got mangled** by terminal line-wrapping during paste: `BQ_PROJECT=plated-complex-4\n  91512-n6` and `AL_CALL_TABLE=cal\n  l_records`. Caught immediately via `gcloud run services describe ... --format='value(spec.template.spec.containers[0].env)'`. Fixed via `gcloud run services update --update-env-vars="BQ_PROJECT=plated-complex-491512-n6,AL_CALL_TABLE=call_records"` → revision **`netpulse-ui-00005-ns6`**.
- [x] Health-checked the 4 submitted URLs:
  - `telecom-classifier`: 307 (IAM-protected redirect to login, healthy)
  - `network-status-agent`: 307 (same)
  - `telecom-cdr-app`: 200 (public)
  - `netpulse-ui`: 200 (public)
- [x] Smoke-test on deployed UI — Phase 9 polish loop began.

**Verification finding logged for posterity:**
The first chat run on revision `00005-ns6` at 05:48:22 UTC ran for **exactly 301 seconds** (Cloud Run's default 300s request timeout) and was killed mid-pipeline. Trace showed `network_investigator`'s second LLM call (after the BigQuery MCP tool call) sent at 05:48:34.703 and **never received a response** — silent Vertex AI hang. The region-failover wrapper had no `asyncio.wait_for` at this point, so it waited forever. This finding drove Phase 9 §9.4 (the 5s hang timeout).

---

## Phase 9 — Post-deploy polish + robustness ✅ DONE

**Started:** 2026-04-26 · **Settled:** 2026-04-26 on revision `netpulse-ui-00010-mqc`
**Authorization:** Source changes inside `netpulse-ui/`, `telecom_ops/`, plus iterative Cloud Run redeploys. From 2026-04-26 the user explicitly lifted Freeze A operational restrictions on `plated-complex-491512-n6` (kept project-billing link frozen) — see global `~/.claude/CLAUDE.md` §Protected Resources.

Each iteration is one redeploy. Warm `min-instances=1` keeps the service responsive between iterations.

- [x] **§9.1** Heliodoron visual identity v1 — `tokens.css` swapped from cool-gray + Material Blue to heliodoron sand neutrals (oklch hue 85) + surya warm-gold brand. Three font @imports added: `@fontsource-variable/geist`, `newsreader`, `jetbrains-mono` from jsdelivr CDN. Heliodoron Indonesian accent palette (`--np-santan`, `--np-pandan`, `--np-tebu`, `--np-laut`, `--np-batik`, `--np-rosella`, `--np-terakota`) added to tokens.css for future iteration. Identity tokens curated from `~/projects/heliodoron-ui-identity/tokens/heliodoron.css` (commit `0923dfb`). Status ladder + category badges + backend palettes intentionally NOT touched in v1 (semantic distinctness preserved). **Revision `00006-7v8`.**
- [x] **§9.2** Footer trim — removed "with Claude Code" link from `landing.html` footer. Now reads: `APAC GenAI Academy 2026 · Top 100 (#82) · Built by Adityo Nugroho.`. Rationale: "Claude Code" is too obvious for the hackathon context. **Rode revision `00006-7v8`.**
- [x] **§9.3** Pandan accent unification — replaced the `linear-gradient(--np-primary → --np-accent)` text-clip on `.np-hero-accent` ("in seconds.") with a solid `var(--np-pandan)`. Replaced per-backend `.np-source-tag.{adk,local,mcp,bq,alloydb,alloydb-write}` color overrides with one unified `color-mix(in oklab, var(--np-pandan) 14%, transparent)` bg + `var(--np-pandan)` fg on the base `.np-source-tag, .np-tool-tag` selector. Backend `--c-*-bg/fg/accent` tokens preserved because they still drive workspace banner backgrounds via `color-mix()` derivations. **Revision `00007-x7t`.**
- [x] **§9.4** 5s per-attempt Vertex AI timeout in `RegionFailoverGemini` — `asyncio.wait_for(_drain_one_attempt(), timeout=PER_ATTEMPT_TIMEOUT_S=5.0)` wraps each region attempt. On `TimeoutError`, the wrapper notifies the observer with `"failover"` + `"timeout after 5.0s"` message, advances to the next region. Only one HTTP call ever in flight per wrapper (cancellation propagates → aiohttp closes socket). New `_self_test_failover_on_timeout` mocks `asyncio.Future()` in region 0 (never resolves; only torn down by `wait_for`'s cancellation); test runtime ~5s. Three self-tests pass: matcher 5/5, quota-error failover (existing), hang failover (new). **Rode revision `00008-kzk`.**
- [x] **§9.5** Per-agent model selection — `agent.py` `_failover_model(owner, model_name)` factory. `MODEL_FAST = "gemini-3.1-flash-lite-preview"` for classifier + network_investigator + cdr_analyzer (validated 7/7 calls successful in production trace). `MODEL_SYNTHESIS = "gemini-3.1-pro-preview"` for response_formatter — but see §9.7 below. **Rode revision `00008-kzk`.**
- [x] **§9.6** Multi-continent region ladder — `RANKED_REGIONS` swapped from `("global", "asia-southeast2", "asia-southeast1", "us-central1")` to `("global", "us-central1", "europe-west4", "asia-northeast1")`. Self-tests pass against the new ladder (region 2 is now `us-central1` in both quota + hang test traces). **Revision `00009-f2c`.**
- [x] **§9.7** Pro-preview region-whitelist finding — **resolved by collapsing `MODEL_SYNTHESIS = MODEL_FAST`** in revision `00010-mqc` (see §9.13 below). Pro-preview no longer in the synthesis path; the failover ladder is structurally usable end-to-end on Flash-Lite (multi-region addressable).
- [x] **§9.8** Post-deploy doc polish (Phase 9 round 1 commit) — CLAUDE.md (project), REFINEMENT-PHASES.md, README.md region paragraph + lessons + deploy resource tables, memory files (`reference_vertex_ai_dsq.md`, new `reference_vertex_ai_preview_models.md`, update `MEMORY.md` index, update `project_top100_refinement.md`). Shipped as commit `61f06ca` PR #10.
- [ ] **§9.9** SSE streaming GIF in README (still deferred from §2.11) — the new region chip + heliodoron palette make this a richer demo asset; should be recorded after Phase 10 settles so the GIF captures the final state.

**Round 2 — settled on revision `netpulse-ui-00010-mqc`:**

- [x] **§9.10** Header darker token — added `--np-brand-deep: oklch(38% 0.110 55)` to `tokens.css` (deep amber-bronze, retains warm-gold hue while reading as substantial structural surface). `.np-header` gradient swapped from `--np-primary-dark → --np-primary` to `--np-brand-deep → --np-brand-interactive`. White text + white logo plate clear WCAG AA easily on the new anchor.
- [x] **§9.11** Done-state pandan unification — `.np-timeline-entry.done` dot, content border-left, and status pill all switched from teal `--np-accent` (#00bfa5 leftover) to `--np-pandan` (oklch 60% 0.085 135). Now the "DONE" pill, dot, and source-tag badges read as one green family instead of two visually-dissonant greens.
- [x] **§9.12** Customer-impact card extractor + layout fix. Root cause traced through `toolbox_core/itransport.py:51` (`tool_invoke -> str`) + `google.adk.flows.llm_flows.functions.__build_response_event` line 700 (`if not isinstance(function_result, dict): function_result = {'result': function_result}`): MCP toolbox tools return JSON-encoded strings, ADK wraps as `{"result": "<string>"}`, so `tool_response.result.result` arrives at the chat UI as a STRING not an Array. Fix: `npExtractRows` now `JSON.parse`s strings recursively before checking `Array.isArray`. Layout redesign: grid (icon-left + body-right) with headline row (big affected count) + meta row (events · elapsed · sev badges); each meta wrapper hides itself when its data is missing (no more dangling `--` placeholder for `since onset`). `npComputeImpact` also tolerates `total_affected` (aggregate-summary tool output) and parses `event_time`/`timestamp` columns alongside `started_at`.
- [x] **§9.13** `MODEL_SYNTHESIS = MODEL_FAST` collapse — all 4 agents on `gemini-3.1-flash-lite-preview`. Resolves §9.7 (Pro-preview was `global`-only for this project, which made the failover ladder a structural no-op for synthesis). Failover self-tests (`telecom_ops/vertex_failover.py`) still pass: matcher 5/5 + quota failover + hang failover. `PER_ATTEMPT_TIMEOUT_S` stays at 5s.

**Verifications (round 2):**
- §9.10/§9.11/§9.12: deployed CSS confirmed serving 200 from live URL post-`gcloud run deploy`. Visual sanity on `https://netpulse-ui-486319900424.us-central1.run.app/app`.
- §9.12: `npExtractRows` mental walk through the toolbox payload shape + selector cross-check between `chat.html` HTML / JS / `style.css`.
- §9.13: production trace 2026-04-26 09:58 UTC — all 4 agents serving `gemini-3.1-flash-lite-preview`, all attempts settle in `global` first-try, run e2e in 10.5s, ticket #74 issued. No failovers, no timeouts.

---

## Phase 10 — Toolbox refactor + seed enrichment ✅ DONE

**Started + Settled:** 2026-04-26
**Authorization:** Source + Cloud Run deploys + BigQuery + AlloyDB writes — all within post-2026-04-26 Freeze A operational lift, no per-change confirmation needed.

Five deliverables (Phase 10 grew from 4 to 5 once a pre-existing severity-vocab bug surfaced during seed prep).

- [x] **§10.1** Universal-tools refactor of `~/projects/genai-hackathon/track2-network-status/toolbox-service/tools.yaml` — collapsed 8 hardcoded tools (5 per-city + `query_network_events` catch-all + `query_critical_outages` + `query_affected_customers_summary`) to **2 universal parameterized tools**: `query_network_events(region, severity, event_type, days_back, limit)` + `query_affected_customers_summary(region, days_back)`. Two non-obvious BigQuery findings drove the final shape (captured in `~/.claude/memory/reference_mcp_toolbox_universal_tools.md`): (a) BigQuery's dry-run validator REJECTS null INT64 parameter binds (`Bad int64 value: <nil>`), forcing INTEGER nullable params to use server-side `default:` sentinels (`days_back: default 36500` = 100-year no-op, `limit: default 50`); (b) BigQuery `LIMIT` accepts only integer literal or single parameter — no expressions, so `LIMIT IFNULL(@limit, 50)` is rejected. STRING nullable params (region, severity, event_type) use the clean `@p IS NULL OR col = @p` pattern. Deployed `network-toolbox-00005-...`.
- [x] **§10.2** Native CDR tool optimization — `telecom_ops/tools.py:query_cdr` now takes `(region, status_filter, call_type, days_back, limit)`. `LIMIT` parameterized (was hardcoded 20, now defaults to 50, clamped 1..200). `days_back` filters via `NOW() - INTERVAL 'N days'` (validated 1..365). `call_type` adds optional `voice|sms|data` filter. `CDR_ANALYZER_INSTRUCTION` in `prompts.py` rewritten to enumerate the new params with usage hints.
- [x] **§10.3** Richer seed data — `docs/seed-data/network_events.csv` extended from 30 → **132 events** spanning 10 cities (existing Jakarta/Surabaya/Bandung/Medan/Semarang + new Yogyakarta/Denpasar/Makassar/Palembang/Balikpapan), date range 2026-01-08 → 2026-05-12 (incl. 5 future-scheduled maintenance windows). `docs/seed-data/call_records.csv` extended from 50 → **500 CDRs** with realistic distribution (320 completed / 118 dropped / 62 failed; failed/dropped clustered around outage anchors per city for storytelling). Severity strictly `critical|major|minor` per `docs/SCHEMA.md` (not `low/medium/high`). Cell tower IDs use IATA airport codes for new cities (YOG, DPS, MKS, PLM, BPN). `NETWORK_INVESTIGATOR_INSTRUCTION` + `CLASSIFIER_INSTRUCTION` city list extended. `netpulse-ui/data_queries.py:ALLOWED_REGIONS` extended to 10 cities. **Reseeded BigQuery (WRITE_TRUNCATE) + AlloyDB (TRUNCATE+reload)** — see verification below for the lock-cleanup detour.
- [x] **§10.4** `setup_alloydb.py:truncate_and_load` rewritten — old code did `conn.execute(insert_sql, payload_list_of_500_dicts)` which SQLAlchemy + pg8000 turn into 500 round-trips and silently times out over WAN. New code builds a **single multi-row `INSERT ... VALUES (..), (..), ...` statement** with all 500 rows in one network round-trip. Reseed dropped from "indefinite hang" to <120s. Necessary fix for any BYO seed >100 rows.
- [x] **§10.5** Pre-existing severity-vocab bug fixed — `netpulse-ui/data_queries.py:36` had `ALLOWED_SEVERITIES = {"low","medium","high","critical"}` but live BQ + `docs/SCHEMA.md:35` use `{"critical","major","minor"}`. The `/network-events` viewer's severity dropdown silently filtered to nothing for `major`/`minor` rows. Surfaced during Phase 10 prep when verifying the canonical seed vocabulary; corrected to match the schema.

**Verifications run locally:**
- §10.1 toolbox smoke-test (Python `toolbox_core.ToolboxSyncClient`): all 6 invocation shapes pass — no params, region only, region+severity, days_back filter, aggregate no-args, aggregate region-scoped. **First deploy revealed both BQ findings** (caught at runtime, not source-time); fixed with default-sentinel pattern + redeployed as `network-toolbox-00005-...`.
- §10.2 AST parse + import smoke on `tools.py` and `prompts.py`.
- §10.3 distribution audit: events by region (10-17 each), severity (19/49/64 critical/major/minor), event_type (50/48/30/4 outage/maintenance/degradation/restoration); CDR by region (~50 each), status (320/118/62).
- §10.4 single-INSERT-VALUES round-trip benchmark: full 500-row reseed in <120s vs. previous 180s+ timeout. AlloyDB `pg_stat_activity` showed clean post-reseed (0 active client backends).
- §10.5 `data_queries.py` AST parse; vocabulary aligned with live BQ severities (verified via `bq query "SELECT severity, COUNT(*) FROM ... GROUP BY severity"` returning only `minor/major/critical`).

**Operational lessons captured:**
- pg8000 + SQLAlchemy `executemany` is unsuitable for >100-row WAN seeds — use single multi-row VALUES instead.
- Forcibly-killed Python connections leave PostgreSQL transactions in `idle in transaction` for ~15min until TCP timeout drops the connection. If multiple seed attempts conflict on TRUNCATE locks, terminate them server-side via `SELECT pg_terminate_backend(pid)` from a fresh AUTOCOMMIT session before retrying.
- BigQuery dry-run validation is stricter than the actual query — a pattern that "looks correct" by SQL semantics may still fail at the dry-run step (specifically: nullable INT64 binds, expression-form LIMIT). The MCP Toolbox runs dry-run before every invocation, so design must be validated against runtime, not source code.

- [x] **§10.6** Redeployed `netpulse-ui` (revision `00011-5ct`) to pick up the new prompts + ALLOWED_REGIONS. **E2E smoke test PASSED** with complaint *"Customer reports failed calls in Denpasar"* (one of the 5 new cities): classifier → `category=network, region=Denpasar`; network_investigator → `query_network_events(region='Denpasar', severity='*', event_type='*', days_back=36500, limit=10)` returns 10 Denpasar events including 3 critical submarine cable damage incidents (EVT069, EVT064, EVT061); cdr_analyzer → `query_cdr(region='Denpasar', status_filter='')` returns 50 CDRs; LLM correctly correlates 22 dropped/failed calls clustered around March-19 + April-17 outage anchors (matching the generator's intentional clustering); response_formatter saves ticket #11 to AlloyDB. All 4 agents first-try in `global`, no failovers, no timeouts, total runtime well under the 5s per-attempt budget. Sentinel pattern (`*`/36500/50) confirmed end-to-end.

**Verifications run locally (Phase 9):**
- §9.1: deployed `tokens.css` + `style.css` confirmed serving 200 from live URL; `tokens.css` references in `base.html` confirmed via curl.
- §9.4: `.venv/bin/python telecom_ops/vertex_failover.py` — matcher 5/5 + quota failover + hang failover. Hang test runtime exactly `PER_ATTEMPT_TIMEOUT_S` (~5s).
- §9.5: 4 distinct `RegionFailoverGemini` instances confirmed via `id()`; `_owner_name` matches each `LlmAgent.name`; first 3 wrappers use `MODEL_FAST`, formatter uses `MODEL_SYNTHESIS`.
- §9.6: self-tests adjusted for new ladder ordering — both walk `["global", "us-central1"]` instead of `["global", "asia-southeast2"]`.

**Verifications surfaced from production logs:**
- §9.4 timeout fired in production (`2026-04-26 07:14:52,238 WARNING telecom_ops.vertex_failover Vertex AI silent hang in region=global after 5.0s; falling over.`) — proves the new code path runs.
- §9.5 Flash-Lite preview latencies measured: 0.6s, 1.4s, 1.7s, 1.9s, 4.3s (cold-start TLS handshake first call). All under the 5s budget except first call near 86%.
- §9.7 Pro-preview unavailable in `us-central1`: `Publisher Model .../locations/us-central1/.../gemini-3.1-pro-preview was not found or your project does not have access to it.` — confirms global-only access for this project.

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
