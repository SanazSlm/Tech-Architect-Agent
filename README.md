# Tech Architect Agent

This is a separate advisor workspace for Houram, a reusable technical architect agent. It is not part of any product and should not modify product code unless explicitly asked.

The agent acts as an on-demand CTO, software architect, and senior AI engineer. Use it to answer technical questions, compare options, explain trade-offs, review architecture, debug issues, and guide implementation inside Cursor.

## How To Use In Cursor

1. Open this folder in Cursor:

   ```bash
   cursor "/Users/sanazslm/Documents/LibZone.ca/Tech Architect Agent"
   ```

2. Ask technical questions normally. The workspace-level Cursor rule in `.cursor/rules/tech-architect-agent.mdc` tells the agent how to respond.

3. Use `Houram, ...` when you want to explicitly call the advisor, for example:

   ```text
   Houram, what is the best answer for this architecture question?
   ```

4. If you need code-specific advice, attach the relevant project file or paste the error. The advisor should not invent current implementation details.

## Knowledge Sources

Current knowledge sources are LibZone-specific:

- `/Users/sanazslm/Documents/LibZone.ca/LibZone/Documents`
- `/Users/sanazslm/Documents/LibZone.ca/LibZone/libzone-core`
- `/Users/sanazslm/Documents/LibZone.ca/LibZone/libzone-admin`
- `/Users/sanazslm/Documents/LibZone.ca/libzone-evals`
- `/Users/sanazslm/Documents/LibZone.ca/libzone-evals-review`

The source list is configured in `config/knowledge_sources.yaml`. For a future project, add that project's docs and source paths there.

## Optional Local Knowledge Index

The project includes an optional retrieval helper. It indexes configured project docs/code read-only into a local Chroma collection and can return relevant context for a question.

```bash
cd "/Users/sanazslm/Documents/LibZone.ca/Tech Architect Agent"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Add your real OPENAI_API_KEY to .env. Do not put secrets in README.md.
tech-architect build-index
tech-architect context "Should Phase 1 use hybrid retrieval immediately?"
tech-architect ask "Should we add Redis now or defer it?"
```

Use `context` when you want retrieved evidence to paste into Cursor. Use `ask` when you want the local CLI to answer with the same advisor structure.

## Operating Rules

- Advise first; do not jump straight to code.
- Answer shortly by default until you ask for further details.
- Prefer MVP-friendly, maintainable decisions.
- Tie technical choices to the active project's product behavior.
- Be explicit about architecture layer: Ingestion, Retrieval, Agent Routing, Answer Generation, API, Frontend, Evaluation, or Operations.
- For LibZone, treat it as a grounded, citation-first book expert assistant, not a generic chatbot.
- For future projects, learn from the provided project docs before making project-specific recommendations.
- Never modify product code unless the owner explicitly asks in that project workspace.
