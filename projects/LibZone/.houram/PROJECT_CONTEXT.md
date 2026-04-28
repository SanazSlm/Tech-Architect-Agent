# Project Context Template

Use this file to onboard Houram into a new project quickly.

## Project Identity

- Project name: LibZone
- Product one-liner: A grounded, citation-first multi-book expert assistant that guides users through owned/internal books.
- Target users: Learners/readers who want deep, trustworthy book guidance; LibZone owner and ops/admin team managing catalog and quality.
- Current stage (idea/MVP/growth/scale): MVP build in phased execution (Phase 0/0-E foundations through ver00 milestone plan).

## Product Goals

- Primary user outcomes:
  - Get grounded answers tied to exact book passages.
  - Navigate quickly to the right chapter/page/citable unit.
  - Compare perspectives across books without losing source traceability.
- Business goals:
  - Ship web-first MVP with strong trust and citation quality.
  - Build architecture that scales from single-book chat to 10k+ archive routing.
  - Support hybrid commerce model (book sales + AI subscription) with admin-configurable contracts.
- Non-goals:
  - Generic chatbot behavior or unsupported model opinions.
  - Voice, native mobile, and multilingual shipping in current MVP scope.
  - Full algorithmic personalization before baseline quality is proven.

## Technical Landscape

- Core architecture:
  - LangGraph-based hierarchical multi-agent architecture (orchestrator, routing, retrieval/synthesis/citation/linter agents).
  - Retrieval pipeline target: category routing -> shortlist -> diversity rerank -> chunk retrieval -> grounded synthesis.
- Main services/modules:
  - `libzone-core`: FastAPI SUT backend, ingestion, agents, policies, workers.
  - `libzone-admin`: Next.js internal admin panel.
  - `libzone-ui`: product/reader UI scaffold.
  - `libzone-evals` and `libzone-evals-review`: isolated evaluation and review flow.
- Primary data stores:
  - Chunk/book/category indexes (vector + metadata; local and qdrant-compatible path).
  - Ingestion artifacts and phase data in `libzone-core/data/phase0`.
  - Taxonomy index from Amazon subject paths.
- Key frameworks/libraries:
  - FastAPI, Python 3.11, LangGraph.
  - Next.js for admin UI.
  - Vector index backend (local or qdrant), embeddings and reranking stack as configured per phase.
- Deployment/runtime environment:
  - Local-first implementation with explicit production split for infra-bearing phases.
  - Web-first MVP; production hardening deferred per phase gates.

## Current Priorities

- Top 3 engineering priorities:
  - Close out Phase 0 + 0-E gates on launch corpus (anchors, taxonomy agreement, vector consistency, eval bridge).
  - Deliver Phase 1 single-book grounded chat with strict citations and hybrid retrieval.
  - Progress ver00 milestones (M1-M5) with release-gate discipline.
- Active constraints (time, team size, budget, compliance):
  - Solo/lean execution style; prioritize maintainable MVP over enterprise complexity.
  - English-first and web-first scope constraints.
  - Quality and trust constraints are strict: no unsupported claims, no citation drift.
- Decisions currently blocked:
  - Exact production infra promotion timing vs local-first baseline stability.
  - Depth/timing of personalization after baseline parity gates.
  - Rollout cadence from limited launch corpus to larger category/book coverage.

## Quality and Evaluation

- Definition of done:
  - Features are considered done only when product behavior and evaluation gates pass together.
  - For ver00, all milestone gates must be green simultaneously on launch corpus/category set.
- Critical quality metrics:
  - Citation correctness and deep-link validity.
  - Book-grounded discipline (no unsupported claims).
  - Router recall@k (as routing phases activate).
  - Perspective diversity quality for multi-book answers.
  - Personalization quality parity when enabled.
- Required tests/evaluation gates:
  - Phase 0: anchors, taxonomy agreement, vector index consistency, corpus audit.
  - Phase 0-E and beyond: isolated eval subsystem + gate bridge checks.
  - PRD transcript reproduction regression checks (as specified in product plan).
- Reliability/performance targets:
  - Bounded top-N retrieval/synthesis path for predictable runtime/cost at scale.
  - Local-first determinism before production hardening/SLO promotion.

## Source of Truth

- Product docs:
  - `Documents/libzone_product_plan_001.plan.md`
  - `Documents/libzone_product_plan_ver00.plan.md`
  - `Documents/libzone_product_plan_feature_checklist.md`
  - `Documents/Final LibZone Product Plan.md`
- Architecture docs:
  - `Documents/libzone_product_plan_ver00.plan.md` (architecture and milestones by inheritance from final plan).
  - `libzone-core/README.md` for current implemented backend layout and phase scripts.
- API contracts:
  - FastAPI routes under `libzone-core/api/routes`.
  - Admin OpenAPI and generated types under `libzone-admin` (when relevant to admin workflows).
- Issue tracker:
  - GitHub issues per repo (not centrally documented in this file).
- Repositories:
  - `LibZone` (monorepo: core/admin/ui/docs)
  - `libzone-evals`
  - `libzone-evals-review`

## Risks and Known Gaps

- Top technical risks:
  - Retrieval misses leading to weak or incorrect grounding.
  - Citation formatting/linking drift across heterogeneous book structures.
  - Premature complexity (personalization/scale features) before baseline quality stability.
- Known debt:
  - `agents/graph.py` and advanced orchestration are still staged for later phases compared to target architecture.
  - Some ver00 scope items are inherited-by-reference and require careful cross-repo consistency to avoid drift.
- Known unknowns:
  - Real-world behavior at broader corpus scales before full Phase 4 activation.
  - Optimal model/cost mix for routing vs synthesis as traffic and catalog expand.
  - User behavior signals and how they should safely feed adaptive ranking/personalization later.
