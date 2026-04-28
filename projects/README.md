# Project knowledge branches

This repository stores **Houram / Tech Architect** advisor code on **`main`**.

For **each product**, keep a durable, versioned Houram snapshot on a **long-lived branch** named after the product. Knowledge files live under:

```text
projects/<ProductName>/.houram/
```

| Branch    | Path                                                                 |
|-----------|----------------------------------------------------------------------|
| `LibZone` | [`projects/LibZone/.houram/`](https://github.com/SanazSlm/Tech-Architect-Agent/tree/LibZone/projects/LibZone/.houram) |

Commit only **text** assets (`PROJECT_CONTEXT.md`, `knowledge_sources.yaml`). Do **not** commit `chroma/`, API keys, or `.env` (use each project’s `.houram/.gitignore`).

To add another product: create branch `YourProduct` from `main`, add `projects/YourProduct/.houram/`, push `origin YourProduct`.
