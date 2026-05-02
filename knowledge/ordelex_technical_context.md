# Ordelex Technical Context

This file is a compact context brief for the Tech Architect Agent. Treat the product documents in the Ordelex monorepo `Documents/` tree as the canonical source when more detail is needed.

## Product Identity

Ordelex is a multi-book expert assistant for owned/internal books. It helps users understand book content through grounded answers, citations, navigation, and reading guidance.

Ordelex must not behave like a generic chatbot. It should not invent unsupported opinions, summarize without grounding, or answer outside the provided book/library content when evidence is missing.

## Current Repository Shape

The Ordelex monorepo contains:

- `ordelex-core`: FastAPI backend, ingestion, APIs, agents, policies, workers, tests
- `ordelex-admin`: internal Next.js admin panel
- `ordelex-ui`: product reader UI scaffold
- `Documents`: PRD, product plan, taxonomy, and planning material

Related repositories:

- `ordelex-evals`: evaluation suite
- `ordelex-evals-review`: review workflow for eval outputs

## Architecture Direction

Target architecture from the product plan:

- Chunk index with per-book semantic chunks and citation metadata
- Book index with topical fingerprints and chapter summaries
- Category index from subject taxonomy paths
- Query pipeline:
  - Intent detection
  - Category routing
  - Book shortlist
  - Diversity reranking
  - Chunk retrieval
  - Perspective clustering
  - Grounded synthesis with clickable citations

The long-term architecture uses hierarchical agents:

- Orchestrator supervisor
- Category supervisors
- Per-book subgraphs

For MVP work, keep the implementation smaller while preserving interfaces that can grow into that architecture.

## Phase Priorities

Phase 0: ingestion and grounding foundation.

- PDF/EPUB parsing
- chapter/page/citable-unit anchors
- chunk embeddings
- book fingerprints
- taxonomy mapping
- local-first quality gates

Phase 0-E: evaluation foundation.

- citation correctness
- grounding discipline
- PRD transcript reproduction
- router recall later
- perspective diversity later

Phase 1: single-book RAG core.

- hybrid retrieval and reranking
- strict book-grounded answer generation
- clickable citations
- streaming answer UX

Phase 2: library UX, summaries, continuity, reading-start journeys.

Phase 3: multi-book topic understanding across a user's library.

Phase 4: 10k+ book scaling through bounded routing and synthesis.

Later phases: personalization, gap discovery, voice, mobile, multilingual support.

## Technical Decision Bias

The advisor should usually recommend:

- local-first proof before production infrastructure
- deterministic checks before LLM judges when possible
- interfaces that allow future scale without implementing the whole future now
- bounded top-N retrieval and synthesis
- explicit evaluation gates before release
- minimal moving parts for the MVP

The advisor should usually avoid:

- building the full 10k-book architecture too early
- adding personalization before grounded answer quality is reliable
- using summaries as a substitute for cited evidence
- letting routing decisions bypass evaluation
- hardcoding commerce/admin rules into product code
- implementing voice or multilingual support before text quality is stable

## Quality Bar

Every substantive Ordelex answer should be evaluated against:

- Is the answer grounded in retrieved book content?
- Are citations correct and clickable?
- Does the response refuse or narrow when evidence is insufficient?
- Does retrieval find the right chapter/passage?
- Does the architecture preserve user trust?
- Can this be tested locally before production?
