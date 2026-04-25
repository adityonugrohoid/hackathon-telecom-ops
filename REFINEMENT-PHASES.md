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
| **2. Foundation layers** | ⏳ Next | ~5h | source only | Tokens + prompt fix + enum guard |
| **3. Innovation track** | Pending | ~6h | source only | Vertex region failover end-to-end |
| **4. Visual redesign** | Pending | ~14h | source only | Landing + timeline + badges + impact + chips |
| **5. Critical UX fixes** | Pending | ~3h | source only | Error states, button disable, input validation |
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

## Phase 2 — Foundation layers ⏳ NEXT

**Estimated:** ~5h · source-only · no redeploy
**Authorization:** Source changes inside `telecom_ops/` and `netpulse-ui/` are within normal scope.
**Blocks:** Phase 4 (all UI redesign work consumes the token layer from §5.0a).

- [ ] **§5.0a** Design token foundation — drop `static/tokens.css` from `heliodoron-ui-identity` curated subset, refactor `style.css` Phase 1+2 to consume tokens. *(~4h)*
- [ ] **§1.5** Validate `category` enum in `save_incident_ticket` (`telecom_ops/tools.py`). *(~30 min)*
- [ ] **§1.4** Tighten `network_investigator` prompt to enumerate ALL events returned (`telecom_ops/prompts.py`). *(~1h)*

**Verification before moving on:** Local Flask UI renders identically to current deployed version (token refactor is a no-op visually); `network_investigator` lists all 9 Jakarta events for the audit complaint instead of 4; `save_incident_ticket` rejects non-enum `category` strings with a clear error.

---

## Phase 3 — Innovation track Pending

**Estimated:** ~6h · source-only · no redeploy
**Authorization:** Source changes inside `telecom_ops/` are within normal scope; the Cloud Run env-var update lives in Phase 8.
**Blocks:** Phase 7's §3.2 region telemetry depends on this.

- [ ] **§3.1** Vertex AI region failover end-to-end per `PLAN-vertex-region-failover.md` 8-step order:
  1. Write `telecom_ops/vertex_failover.py` (`RegionFailoverGemini` subclass) with matcher unit-test under `if __name__ == "__main__":`.
  2. Run `python -m telecom_ops.vertex_failover` to validate the matcher.
  3. Wire `RegionFailoverGemini` into `telecom_ops/agent.py` (each `LlmAgent` gets its own instance for per-agent failover state).
  4. Update `telecom_ops/.env` to `GOOGLE_CLOUD_LOCATION=global`.
  5. Run integration test with forced failover (monkey-patched bad first region).
  6. Run end-to-end via Flask UI; confirm logs show `Vertex AI attempt: region=global` for each agent.
  7. Update `README.md` deploy snippet and project `CLAUDE.md` "Non-obvious choices" paragraph.
  8. Phase 8 redeploy step (deferred).

**Verification before moving on:** Forced-failover test shows ladder traversal (`global` 429 → `asia-southeast2` success); end-to-end chat still produces a clean ticket.

---

## Phase 4 — Visual redesign Pending

**Estimated:** ~14h · source-only · no redeploy
**Authorization:** Source changes inside `netpulse-ui/`.
**Blocked by:** Phase 2 §5.0a (tokens).
**Order within phase:** Land §5.11 first (defines routing for the rest); other items independent.

- [ ] **§5.11** Hero landing page + routing redesign — new `templates/landing.html`, route `/` to landing, `/app` to workspace, `/chat` 301 → `/app`, `?seed=` handoff. *(~3-4h)*
- [ ] **§5.2** Pipeline-as-timeline — convert horizontal 4-card row into vertical activity stream (PagerDuty-style). *(~3h)*
- [ ] **§5.3** Severity + Category badges with color coding (consumes tokens). *(~1h)*
- [ ] **§5.5** Customer-impact card (X affected · Y min · Z events) — computed from `network_investigator` output. *(~3h)*
- [ ] **§5.4** Recommended NOC actions chip panel — static category→actions map version. *(~3h)*

**Verification before moving on:** Local UI shows landing page on `/`, app on `/app`, vertical timeline animates, badges colored, impact card prominent above ticket, action chips render below recommendation. Existing chat function unchanged.

---

## Phase 5 — Critical UX fixes Pending

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
