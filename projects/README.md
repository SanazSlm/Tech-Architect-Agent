# Project knowledge branches

This repository stores **Houram / Tech Architect** advisor code on **`main`**.

For **each product**, you can keep a durable, versioned Houram snapshot on a **long-lived branch** named after the product. Knowledge files live under:

```text
projects/<ProductName>/.houram/
```

Example: branch **`Ordelex`** → [`projects/Ordelex/.houram/`](https://github.com/SanazSlm/Tech-Architect-Agent/tree/Ordelex/projects/Ordelex/.houram).

Commit only **text** assets (`PROJECT_CONTEXT.md`, `knowledge_sources.yaml`). Do **not** commit `chroma/`, API keys, or `.env` (use each project’s `.houram/.gitignore`).

To add another product: create branch `YourProduct` from `main`, add `projects/YourProduct/.houram/`, push `origin YourProduct`.
