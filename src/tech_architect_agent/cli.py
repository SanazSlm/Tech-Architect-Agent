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


@app.command("build-index")
def build_index(
    config_path: Path = typer.Option(DEFAULT_CONFIG, help="Knowledge source config."),
    index_dir: Path = typer.Option(DEFAULT_INDEX_DIR, help="Local Chroma persistence directory."),
    batch_size: int = typer.Option(64, help="Embedding batch size."),
) -> None:
    """Build or refresh the local advisor knowledge index."""

    config = load_config(config_path)
    client = require_openai_client()
    collection = get_collection(config, index_dir)

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


def retrieve(question: str, config_path: Path, index_dir: Path, top_k: int) -> list[dict[str, str]]:
    config = load_config(config_path)
    client = require_openai_client()
    collection = get_collection(config, index_dir)
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
    config_path: Path = typer.Option(DEFAULT_CONFIG, help="Knowledge source config."),
    index_dir: Path = typer.Option(DEFAULT_INDEX_DIR, help="Local Chroma persistence directory."),
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
    config_path: Path = typer.Option(DEFAULT_CONFIG, help="Knowledge source config."),
    index_dir: Path = typer.Option(DEFAULT_INDEX_DIR, help="Local Chroma persistence directory."),
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
