# Tech Architect Agent

This is a separate advisor workspace for Houram, a reusable technical architect agent. It is not part of any product and should not modify product code unless explicitly asked.

The agent acts as an on-demand CTO, software architect, and senior AI engineer. Use it to answer technical questions, compare options, explain trade-offs, review architecture, debug issues, and guide implementation inside Cursor.

## How To Use In Cursor

1. Open this folder in Cursor:

   ```bash
   cursor "/Users/sanazslm/Documents/LibZone.ca/Tech Architect Agent"
   ```

2. Add Houram as a global Cursor User Rule so it works in every project:

   - Open `Cursor Settings -> Rules`
   - Create a new **User Rule**
   - Paste the contents of `rules/houram-user-rule.md`

3. Use `Houram, ...` for standard mode, or `Houram-team, ...` for dual-view team mode:

   ```text
   Houram, what is the best answer for this architecture question?
   ```

   ```text
   Houram-team, should we implement this now or defer it?
   ```

4. If you need code-specific advice, attach the relevant project file or paste the error. The advisor should not invent current implementation details.

## Use Houram In Any New Project

Initialize a project once to add project-local Houram files:

```bash
tech-architect init-project "/absolute/path/to/your-project"
```

This adds:

- `.cursor/rules/houram-advisor.mdc`
- `.houram/PROJECT_CONTEXT.md`
- `.houram/knowledge_sources.yaml`

Then fill `.houram/PROJECT_CONTEXT.md` and build the project index:

```bash
tech-architect build-index --config "/absolute/path/to/your-project/.houram/knowledge_sources.yaml"
```

## Knowledge Sources

Current default knowledge sources are LibZone-specific:

- `/Users/sanazslm/Documents/LibZone.ca/LibZone/Documents`
- `/Users/sanazslm/Documents/LibZone.ca/LibZone/libzone-core`
- `/Users/sanazslm/Documents/LibZone.ca/LibZone/libzone-admin`
- `/Users/sanazslm/Documents/LibZone.ca/libzone-evals`
- `/Users/sanazslm/Documents/LibZone.ca/libzone-evals-review`

The default source list is configured in `config/knowledge_sources.yaml`.
For a future project, prefer `tech-architect init-project` and then edit that project's `.houram/knowledge_sources.yaml`.

## Keep the learning hub current (company architecture)

Houram stays aligned with your products when **three** things move together:

1. **`.houram/PROJECT_CONTEXT.md`** — decisions, stack, priorities (edit when something important changes).
2. **`.houram/knowledge_sources.yaml`** — which repos and doc trees are indexed (add new products or ADR roots here).
3. **`tech-architect build-index --config ".../.houram/knowledge_sources.yaml"`** — refresh the local index after substantive doc/code changes (default skips chunks already stored; use `--reindex-all` only when you need a full re-embed).

## Mac automation (weekly index refresh)

Your Mac can re-run **`build-index`** on a schedule so the learning hub stays warm without manual steps.

1. In this repo, set **`TECH_ARCHITECT_KNOWLEDGE_CONFIG`** in **`.env`** to the absolute path of your `knowledge_sources.yaml` (for example LibZone’s `.houram/knowledge_sources.yaml`). Keep **`OPENAI_API_KEY`** there too.
2. Ensure the venv exists and the CLI is installed: `source .venv/bin/activate && pip install -e .`
3. Install a **LaunchAgent** (default: **Sunday 06:00**). Optional env vars when installing: `HOURAM_LAUNCH_WEEKDAY`, `HOURAM_LAUNCH_HOUR`, `HOURAM_LAUNCH_MINUTE` (`Weekday` **0** or **7** = Sunday in `launchd`).

```bash
cd "/Users/sanazslm/Documents/LibZone.ca/Tech Architect Agent"
./scripts/mac/install_launch_agent.sh
```

Logs: **`~/Library/Logs/com.houram.refresh-index.out.log`** and **`.err.log`**.

Test one run immediately:

```bash
launchctl kickstart -k "gui/$(id -u)/com.houram.refresh-index"
```

Remove automation:

```bash
./scripts/mac/uninstall_launch_agent.sh
```

## Optional Local Knowledge Index

The project includes an optional retrieval helper. It indexes configured project docs/code read-only into a local Chroma collection and can return relevant context for a question.

```bash
cd "/Users/sanazslm/Documents/LibZone.ca/Tech Architect Agent"
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Add your real OPENAI_API_KEY to .env. Do not put secrets in README.md.
# If you change the CLI code, reinstall so `tech-architect` picks up updates:
# pip install -e .
tech-architect build-index
tech-architect context "Should Phase 1 use hybrid retrieval immediately?"
tech-architect ask "Should we add Redis now or defer it?"
```

For project-specific indexing:

```bash
tech-architect build-index --config "/absolute/path/to/project/.houram/knowledge_sources.yaml"
tech-architect ask --config "/absolute/path/to/project/.houram/knowledge_sources.yaml" "Houram, what is the biggest technical risk?"
```

Use `context` when you want retrieved evidence to paste into Cursor. Use `ask` when you want the local CLI to answer with the same advisor structure.

Embedding limits: OpenAI embeddings reject any single input longer than **8192 tokens**. Chunk sizing is **character-based** (see `TECH_ARCHITECT_EMBED_CHUNK_CHARS` / `TECH_ARCHITECT_EMBED_MAX_CHARS` in `.env.example`), which is only a rough proxy for tokens. The indexer also **auto-splits** any specific embedding input that still trips the model limit.

## Houram-team Mode

`Houram-team` is a collaboration phrase that produces:

- `Primary View` (default architecture recommendation, OpenAI perspective)
- `Challenger View` (counter-arguments and risks, Claude Sonnet perspective when available)
- `Final Call` (one resolved recommendation)

## Operating Rules

- Advise first; do not jump straight to code.
- Answer shortly by default until you ask for further details.
- Prefer MVP-friendly, maintainable decisions.
- Tie technical choices to the active project's product behavior.
- Be explicit about architecture layer: Ingestion, Retrieval, Agent Routing, Answer Generation, API, Frontend, Evaluation, or Operations.
- For LibZone, treat it as a grounded, citation-first book expert assistant, not a generic chatbot.
- For future projects, learn from the provided project docs before making project-specific recommendations.
- Never modify product code unless the owner explicitly asks in that project workspace.
