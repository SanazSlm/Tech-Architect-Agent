# Project knowledge branches

This repository stores **Houram / Tech Architect** advisor code on **`main`**.

For **each product** you want a durable, versioned “learning hub” snapshot, use a **long-lived branch** named after the product and keep that product’s Houram files under:

```text
projects/<ProductName>/.houram/
```

Example:

| Branch    | Path                          |
|-----------|-------------------------------|
| `LibZone` | `projects/LibZone/.houram/`   |

Commit only **text** assets (`PROJECT_CONTEXT.md`, `knowledge_sources.yaml`). Do **not** commit `chroma/`, API keys, or `.env` (ignored per-project under `.houram/.gitignore`).

To add another product later: create branch `YourProduct` from `main`, add `projects/YourProduct/.houram/`, push `origin YourProduct`.
