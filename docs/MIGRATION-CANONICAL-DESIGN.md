# Migration — static-mockup-rebuild → netpulse-ui (production)

> **Status (locked 2026-04-28):** `static-mockup-rebuild/` is the canonical
> design surface for NetPulse AI. The old `static-mockup/` folder is
> deleted. The next move is the **full LIVE migration**: port the rebuild
> design into the Flask production app at `netpulse-ui/templates/` and
> redeploy to Cloud Run.
>
> User signals when to start. Until signalled, do not begin migration.

## What ships

The whole rebuild package — six pages — moves into production:

| Rebuild source | Production target | Notes |
|---|---|---|
| `static-mockup-rebuild/index.html`           | `netpulse-ui/templates/landing.html`        | Hero CTA-band, How-it-works strip, Data Viewer + Resources card grids, footer. Sample-prompt chips already have `?seed=…&autorun=1` handoff in production — preserve. |
| `static-mockup-rebuild/app.html`             | `netpulse-ui/templates/chat.html`           | Workspace: two-pane prompt + dark ticket form on top, four agent cards with terminal-feel reasoning panels, impact card, NOC chips, see-also strip. SSE handler in inline JS must keep working — it drives all live state. |
| `static-mockup-rebuild/docs.html`            | new route + `templates/docs.html`           | Single comprehensive docs page (sticky TOC + 7 sections). Add `/docs` route in `netpulse-ui/app.py`. |
| `static-mockup-rebuild/network-events.html`  | `netpulse-ui/templates/network_events.html` | Existing data viewer; reskin to rebuild template. |
| `static-mockup-rebuild/call-records.html`    | `netpulse-ui/templates/call_records.html`   | Existing data viewer; reskin. |
| `static-mockup-rebuild/tickets.html`         | `netpulse-ui/templates/incident_tickets.html` | Existing data viewer; reskin. |

Static assets (`css/site.css`, `js/site.js`, `img/*`, fonts via Google Fonts link) move to `netpulse-ui/static/`. The single shared stylesheet is the lever — every template links it.

## Why now

- Top-100 → Top-10 prototype refinement deadline **2026-04-30**.
- Phase 8 (Ship) was completed 2026-04-26 on the old design; the live URL
  is currently serving pre-rebuild visuals.
- Phases 9 / 10 / 11 / 12 backend work is already in production — no
  backend churn required for this migration. Pure presentation.
- Freeze A operational restrictions on `plated-complex-491512-n6` were
  lifted 2026-04-26; Cloud Run redeploys proceed without per-change
  confirmation.

## Migration order (suggested)

1. **Static assets first** — copy `css/site.css` + `js/site.js` + `img/*` into `netpulse-ui/static/`. Wire the Google Fonts link in `templates/base.html` (or each template if no base exists).
2. **Landing page** — port `index.html` markup into `templates/landing.html`. Preserve all existing `?seed=…&autorun=1` chip handoff. Verify locally with `flask run`.
3. **Workspace** — port `app.html` markup into `templates/chat.html`. Preserve the inline SSE handler that drives streaming agent updates, the impact card extractor, and the NOC action chip rendering. Test against a live agent run before redeploying.
4. **Data viewers** — three near-identical reskins. Preserve the existing query/filter form actions and the Flask context variables that populate the table.
5. **Docs** — new `/docs` route. Static page; no backend wiring beyond the route.
6. **Cloud Run redeploy** — single `gcloud run deploy netpulse-ui …` from project root with `--clear-base-image` to keep Dockerfile build (Buildpacks strips `telecom_ops/` from the image).

## What must not break in this migration

- **SSE chat streaming** in `chat.html` — the thread+queue async-to-sync bridge in `agent_runner.py` is load-bearing. Markup changes only; JS handler logic stays.
- **Customer-impact card extractor** in `chat.html` — the recursive `JSON.parse` walk through `tool_response.result` (string-encoded MCP toolbox output). Documented constraint in project `CLAUDE.md`.
- **Sample-prompt chips on landing** — `?seed=…&autorun=1` handoff to `/app` must continue to work end-to-end.
- **Three data-viewer query forms** — Flask `data_queries.py` returns context dicts that the templates render; preserve variable names.
- **`#82` removal** — already edited in `templates/landing.html` but never deployed; landing port carries this forward automatically.

## Verification (post-deploy)

1. Hit `https://netpulse-ui-486319900424.us-central1.run.app/` — landing renders in rebuild design.
2. Click a sample chip → workspace opens with seed prompt prefilled and autorun=1 fires the agent run. Watch SSE stream populate the four agent cards.
3. After completion: impact card populates with real numbers, ticket card renders with badges, NOC chips appear by category, see-also strip resolves.
4. Visit `/docs`, `/network-events`, `/call-records`, `/tickets` — all rebuild design.
5. Check Cloud Run logs for `ModuleNotFoundError` or template-not-found errors.

## Rollback

If anything breaks: redeploy the previous Cloud Run revision (`gcloud run services update-traffic netpulse-ui --to-revisions=netpulse-ui-00010-mqc=100`) — instant rollback to the last known-healthy pre-rebuild revision.

## Out of scope for this migration

- No backend / agent changes.
- No schema changes.
- No font self-hosting — Google Fonts CDN link continues for the
  hackathon timeframe. Self-hosting is a post-hackathon polish item.
- The orphan CSS in `css/site.css` (~250 lines for unused `.hero-*`,
  `.products-grid`, `.pcard`, `.marquee`, `.manifesto`, `.quote-band`,
  `.watermark`) ships as-is. Pruning is a follow-up.
