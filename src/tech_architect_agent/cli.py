from __future__ import annotations

import fnmatch
import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import chromadb
import typer
import yaml
from dotenv import load_dotenv
from openai import OpenAI
from rich.console import Console
from rich.panel import Panel

app = typer.Typer(help="Read-only Tech Architect Agent helper.")
console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "knowledge_sources.yaml"
DEFAULT_INDEX_DIR = PROJECT_ROOT / ".cache" / "chroma"
DEFAULT_PROMPT = PROJECT_ROOT / "prompts" / "tech_architect_agent.md"
DEFAULT_PROJECT_RULE = PROJECT_ROOT / "rules" / "houram-project-rule.mdc"
DEFAULT_PROJECT_CONTEXT_TEMPLATE = PROJECT_ROOT / "templates" / "PROJECT_CONTEXT.md"

@dataclass(frozen=True)
class Chunk:
    id: str
    text: str
    metadata: dict[str, str]


def load_config(config_path: Path) -> dict[str, Any]:
    with config_path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file)


def should_exclude(path: Path, root: Path, patterns: list[str]) -> bool:
    rel = path.relative_to(root).as_posix()
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def iter_source_files(config: dict[str, Any]) -> list[Path]:
    files: list[Path] = []

    for source in config["sources"]:
        root = Path(source["root"]).expanduser()
        excludes = source.get("exclude", [])

        for pattern in source["globs"]:
            for path in root.glob(pattern):
                if path.is_file() and not should_exclude(path, root, excludes):
                    files.append(path)

    return sorted(set(files))


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return None


def make_chunks(path: Path, text: str, chunk_chars: int = 3200, overlap: int = 350) -> list[Chunk]:
    chunks: list[Chunk] = []
    start = 0
    ordinal = 0

    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            digest = hashlib.sha256(f"{path}:{ordinal}:{chunk_text}".encode("utf-8")).hexdigest()[:24]
            chunks.append(
                Chunk(
                    id=digest,
                    text=chunk_text,
                    metadata={
                        "path": str(path),
                        "chunk": str(ordinal),
                    },
                )
            )

        if end == len(text):
            break

        start = max(end - overlap, start + 1)
        ordinal += 1

    return chunks


def embed_texts(client: OpenAI, texts: list[str]) -> list[list[float]]:
    model = os.getenv("TECH_ARCHITECT_EMBEDDING_MODEL", "text-embedding-3-small")
    response = client.embeddings.create(model=model, input=texts)
    return [item.embedding for item in response.data]


def get_collection(config: dict[str, Any], index_dir: Path):
    chroma = chromadb.PersistentClient(path=str(index_dir))
    return chroma.get_or_create_collection(name=config["index_name"])


def require_openai_client() -> OpenAI:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise typer.BadParameter("OPENAI_API_KEY is required for embeddings or local answer generation.")
    return OpenAI()


def resolve_index_dir(config_path: Path, index_dir: Path | None) -> Path:
    if index_dir:
        return index_dir
    if config_path.resolve() == DEFAULT_CONFIG.resolve():
        return DEFAULT_INDEX_DIR
    return config_path.parent / "chroma"


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def write_file(path: Path, content: str, force: bool) -> bool:
    ensure_parent(path)
    if path.exists() and not force:
        return False
    path.write_text(content, encoding="utf-8")
    return True


def render_project_knowledge_config(project_path: Path) -> dict[str, Any]:
    docs_dir = project_path / "docs"
    project_docs_root = docs_dir if docs_dir.exists() else project_path

    return {
        "index_name": f"{project_path.name.lower().replace(' ', '_')}_technical_knowledge",
        "sources": [
            {
                "name": "houram_context",
                "root": str(PROJECT_ROOT),
                "globs": ["AGENTS.md", "prompts/*.md", "knowledge/*.md"],
            },
            {
                "name": "project_docs",
                "root": str(project_docs_root),
                "globs": ["**/*.md", "**/*.txt"],
            },
            {
                "name": "project_source",
                "root": str(project_path),
                "globs": [
                    "**/*.py",
                    "**/*.ts",
                    "**/*.tsx",
                    "**/*.js",
                    "**/*.go",
                    "**/*.java",
                    "**/*.rs",
                    "**/*.yaml",
                    "**/*.yml",
                    "**/*.toml",
                    "**/*.json",
                    "README.md",
                ],
                "exclude": [
                    ".git/**",
                    ".venv/**",
                    "venv/**",
                    "node_modules/**",
                    ".next/**",
                    "dist/**",
                    "build/**",
                    "__pycache__/**",
                ],
            },
        ],
    }


@app.command("init-project")
def init_project(
    project_path: Path = typer.Argument(..., help="Absolute path to the target project."),
    force: bool = typer.Option(False, "--force", help="Overwrite generated Houram files if they exist."),
) -> None:
    """Initialize Houram advisor files inside a project."""

    target = project_path.expanduser().resolve()
    if not target.exists() or not target.is_dir():
        raise typer.BadParameter("project_path must be an existing directory.")

    houram_dir = target / ".houram"
    cursor_rule = target / ".cursor" / "rules" / "houram-advisor.mdc"
    project_context = houram_dir / "PROJECT_CONTEXT.md"
    project_config = houram_dir / "knowledge_sources.yaml"

    project_rule_content = DEFAULT_PROJECT_RULE.read_text(encoding="utf-8")
    project_context_content = DEFAULT_PROJECT_CONTEXT_TEMPLATE.read_text(encoding="utf-8")
    project_config_content = yaml.safe_dump(render_project_knowledge_config(target), sort_keys=False)

    created = []
    skipped = []

    for path, content in (
        (cursor_rule, project_rule_content),
        (project_context, project_context_content),
        (project_config, project_config_content),
    ):
        if write_file(path, content, force):
            created.append(path)
        else:
            skipped.append(path)

    if created:
        console.print("[green]Created Houram project files:[/green]")
        for path in created:
            console.print(f"- {path}")
    if skipped:
        console.print("[yellow]Skipped existing files (use --force to overwrite):[/yellow]")
        for path in skipped:
            console.print(f"- {path}")

    console.print("\nNext steps:")
    console.print(f"1) Fill project context: {project_context}")
    console.print(f"2) Build index: tech-architect build-index --config \"{project_config}\"")
    console.print(f"3) Ask Houram in Cursor: Houram, review this architecture.")


@app.command("build-index")
def build_index(
    config_path: Path = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "--config-path",
        help="Knowledge source config.",
    ),
    index_dir: Path | None = typer.Option(None, help="Local Chroma persistence directory."),
    batch_size: int = typer.Option(64, help="Embedding batch size."),
) -> None:
    """Build or refresh the local advisor knowledge index."""

    config = load_config(config_path)
    client = require_openai_client()
    resolved_index_dir = resolve_index_dir(config_path, index_dir)
    collection = get_collection(config, resolved_index_dir)

    source_files = iter_source_files(config)
    chunks: list[Chunk] = []

    for path in source_files:
        text = read_text(path)
        if text:
            chunks.extend(make_chunks(path, text))

    console.print(f"Indexing {len(chunks)} chunks from {len(source_files)} files...")

    for offset in range(0, len(chunks), batch_size):
        batch = chunks[offset : offset + batch_size]
        embeddings = embed_texts(client, [chunk.text for chunk in batch])
        collection.upsert(
            ids=[chunk.id for chunk in batch],
            documents=[chunk.text for chunk in batch],
            metadatas=[chunk.metadata for chunk in batch],
            embeddings=embeddings,
        )
        console.print(f"Indexed {min(offset + batch_size, len(chunks))}/{len(chunks)} chunks")

    console.print("[green]Knowledge index is ready.[/green]")


def retrieve(question: str, config_path: Path, index_dir: Path | None, top_k: int) -> list[dict[str, str]]:
    config = load_config(config_path)
    client = require_openai_client()
    resolved_index_dir = resolve_index_dir(config_path, index_dir)
    collection = get_collection(config, resolved_index_dir)
    query_embedding = embed_texts(client, [question])[0]

    result = collection.query(query_embeddings=[query_embedding], n_results=top_k)
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]

    return [
        {
            "path": metadata.get("path", "unknown"),
            "chunk": metadata.get("chunk", "unknown"),
            "text": document,
        }
        for document, metadata in zip(documents, metadatas, strict=False)
    ]


@app.command("context")
def context(
    question: str = typer.Argument(..., help="Technical question to retrieve context for."),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "--config-path",
        help="Knowledge source config.",
    ),
    index_dir: Path | None = typer.Option(None, help="Local Chroma persistence directory."),
    top_k: int = typer.Option(6, help="Number of context chunks to return."),
) -> None:
    """Print relevant project context for a question."""

    chunks = retrieve(question, config_path, index_dir, top_k)
    for index, chunk in enumerate(chunks, start=1):
        title = f"{index}. {chunk['path']}#chunk-{chunk['chunk']}"
        console.print(Panel(chunk["text"], title=title, expand=False))


@app.command("ask")
def ask(
    question: str = typer.Argument(..., help="Technical question for the advisor."),
    config_path: Path = typer.Option(
        DEFAULT_CONFIG,
        "--config",
        "--config-path",
        help="Knowledge source config.",
    ),
    index_dir: Path | None = typer.Option(None, help="Local Chroma persistence directory."),
    prompt_path: Path = typer.Option(DEFAULT_PROMPT, help="Advisor system prompt."),
    top_k: int = typer.Option(6, help="Number of context chunks to use."),
) -> None:
    """Answer using retrieved project context and the advisor prompt."""

    client = require_openai_client()
    chunks = retrieve(question, config_path, index_dir, top_k)
    prompt = prompt_path.read_text(encoding="utf-8")
    context_block = "\n\n".join(
        f"Source: {chunk['path']}#chunk-{chunk['chunk']}\n{chunk['text']}" for chunk in chunks
    )

    response = client.chat.completions.create(
        model=os.getenv("TECH_ARCHITECT_MODEL", "gpt-4.1"),
        temperature=0.2,
        messages=[
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Question:\n{question}\n\nRelevant project context:\n{context_block}",
            },
        ],
    )

    answer = response.choices[0].message.content or ""
    console.print(answer)


if __name__ == "__main__":
    app()
