# Project Context Template

Use this file to onboard Houram into a new project quickly.

## Project Identity

- Project name:
- Product one-liner:
- Target users:
- Current stage (idea/MVP/growth/scale):

## Product Goals

- Primary user outcomes:
- Business goals:
- Non-goals:

## Technical Landscape

- Core architecture:
- Main services/modules:
- Primary data stores:
- Key frameworks/libraries:
- Deployment/runtime environment:

## Current Priorities

- Top 3 engineering priorities:
- Active constraints (time, team size, budget, compliance):
- Decisions currently blocked:

## Quality and Evaluation

- Definition of done:
- Critical quality metrics:
- Required tests/evaluation gates:
- Reliability/performance targets:

## Source of Truth

- Product docs:
- Architecture docs:
- API contracts:
- Issue tracker:
- Repositories:

## Keeping Houram current (learning hub)

Houram reads this file and the local index built from `.houram/knowledge_sources.yaml`. To keep **company / product architecture** advice accurate:

- Update **this file** when you make or reverse a significant technical decision.
- Add new roots (repos, `docs/`, ADRs) to **`knowledge_sources.yaml`** when a new surface should inform the advisor.
- Rebuild the index after batches of doc/code change:

  `tech-architect build-index --config <path>/.houram/knowledge_sources.yaml`

  (Omit `--reindex-all` unless you need a full re-embed.)

## Risks and Known Gaps

- Top technical risks:
- Known debt:
- Known unknowns:
