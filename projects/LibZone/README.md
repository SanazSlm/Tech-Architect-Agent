# LibZone — Houram knowledge (branch `LibZone`)

This folder is the **canonical copy** of LibZone Houram knowledge for [Tech-Architect-Agent](https://github.com/SanazSlm/Tech-Architect-Agent) on the **`LibZone`** branch.

Contents:

- `.houram/PROJECT_CONTEXT.md` — product and architecture narrative
- `.houram/knowledge_sources.yaml` — what to index for retrieval (paths may be machine-specific; adjust after clone)

The local Chroma index is **not** tracked (see `.houram/.gitignore`). Build it with:

```bash
tech-architect build-index --config "/absolute/path/to/this/repo/projects/LibZone/.houram/knowledge_sources.yaml"
```

Or point `TECH_ARCHITECT_KNOWLEDGE_CONFIG` in the advisor `.env` at that file when automating on your Mac.
