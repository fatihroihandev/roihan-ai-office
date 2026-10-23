# Autonomous SEO: repository audit and implementation status

## Repository audit

- The application already has a FastAPI API, Next.js UI, SQLAlchemy/Alembic persistence, token authentication, task worker, model routing and global provider budget controls.
- `seo_specialist` already runs deterministic HTML/site audits and AI keyword research/content briefs through the existing task engine. Results are stored as `MarketingArtifact` rows. SEO tasks cannot publish or edit production.
- Project sites are stored as `Site`; their source is copied into an Engineering project workspace and audited read-only. Engineering handoff creates a draft task that a human must queue.
- Approval, task checkpoints, retry limits and audit logging exist elsewhere in the application and remain separate from SEO campaign status.
- SEO KPI snapshots are manually recorded today. There is no Search Console OAuth/property integration, Analytics adapter, external crawler for arbitrary campaign URLs, campaign scheduler, or SEO-specific cost ledger.

## This implementation phase

- Added `SeoCampaign`, `SeoKeyword`, `SeoRecommendation`, and append-only `SeoCampaignEvent` persistence, with Alembic revision `0014`.
- Added authenticated campaign CRUD/read APIs, domain-locked website configuration, campaign status transitions, task-engine handoff for project-site audits and keyword/content-plan tasks, manual keyword creation/deletion, and explicit keyword approval decisions.
- SEO task suggestions are saved as pending campaign keywords with their AI source and grounded evidence. Search volume and competition remain null unless the existing source-grounding check verifies them.
- Campaign audits create persisted recommendations from observed findings, ordered by severity. Potential impact, effort, and risk stay unknown until supported by data. Recommendations have explicit approval states.
- SEO AI calls are logged under their campaign purpose. Before a paid model call, the executor checks model pricing metadata and the campaign's remaining API budget; unknown pricing or an over-budget estimate blocks the call. Campaign task APIs prevent a second active task for the same campaign.
- Added the campaign UI to the existing SEO page. It shows stored campaigns, status, keywords, provenance, manual and bulk approval controls, task actions, audit backlog, history, and JSON report export. New campaigns default to read-only.
- Campaign external integrations are returned as `not_connected`; no production writes, publication, arbitrary URL fetch, or ranking promise was added.

## Remaining phases and constraints

1. Add a campaign-scoped secure crawler for externally hosted websites, with DNS/redirect revalidation, robots handling, rate limits, page/depth/byte caps, and test fixtures. Current campaign audits only work for a registered project `Site`.
2. Build issue/recommendation records and auditable priority fields from crawler evidence; add CSV/report export.
3. Add a source adapter for Search Console OAuth (minimum scopes), then Analytics only if authorized. Until connected, performance values stay unavailable unless entered through existing manual KPI recording.
4. Add external-service cost accounting and concurrency-safe budget reservations. The per-call model budget check uses recorded actual costs plus a pre-call model estimate; provider pricing accuracy remains an external dependency. The global AI budget is also enforced.
5. Add controlled workspace change proposals, diffs, QA and human approval. There is no autonomous website editing or publishing in this phase.
6. Add a bounded scheduler loop only after campaign data, cost accounting, deduplication, pause/resume and approval invariants can be tested together.

No SEO rank, traffic uplift, search-volume, competition, or competitor metric is fabricated. Approval is required before production or external actions.
