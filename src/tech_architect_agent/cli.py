from __future__ import annotations

import fnmatch
import hashlib
import math
import os
import random
import re
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import chromadb
import typer
import yaml
from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, BadRequestError, OpenAI, RateLimitError
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


def max_embed_chars() -> int:
    """Conservative max chars per embedding input to stay under OpenAI 8192-token limit."""
    raw = os.getenv("TECH_ARCHITECT_EMBED_MAX_CHARS", "6000")
    try:
        value = int(raw)
    except ValueError:
        value = 6000
    return max(2000, min(value, 24000))


def split_text_by_max_chars(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]

    parts: list[str] = []
    cursor = 0
    while cursor < len(text):
        end = min(cursor + limit, len(text))
        segment = text[cursor:end].strip()
        if segment:
            parts.append(segment)
        cursor = end
    return parts or [text[:limit]]


def make_chunks(path: Path, text: str, chunk_chars: int | None = None, overlap: int = 250) -> list[Chunk]:
    """Chunk text for embeddings; sizes are conservative vs OpenAI per-input token limits."""
    if chunk_chars is None:
        try:
            chunk_chars = int(os.getenv("TECH_ARCHITECT_EMBED_CHUNK_CHARS", "6000"))
        except ValueError:
            chunk_chars = 6000

    embed_limit = max_embed_chars()
    chunk_chars = max(1000, min(chunk_chars, embed_limit))
    overlap = max(0, min(overlap, chunk_chars // 4))

    chunks: list[Chunk] = []
    start = 0
    ordinal = 0

    while start < len(text):
        end = min(start + chunk_chars, len(text))
        chunk_text = text[start:end].strip()

        if chunk_text:
            for part_index, part in enumerate(split_text_by_max_chars(chunk_text, embed_limit)):
                digest = hashlib.sha256(
                    f"{path}:{ordinal}:{part_index}:{part}".encode("utf-8")
                ).hexdigest()[:24]
                chunks.append(
                    Chunk(
                        id=digest,
                        text=part,
                        metadata={
                            "path": str(path),
                            "chunk": str(ordinal),
                            "part": str(part_index),
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


def _is_embedding_length_error(error: BadRequestError) -> bool:
    message = str(error).lower()
    return "maximum input length" in message or "8192" in message


def _split_text_in_half(text: str) -> tuple[str, str]:
    if len(text) <= 1:
        return text, ""
    midpoint = len(text) // 2
    left = text[:midpoint]
    right = text[midpoint:]
    return left.strip(), right.strip()


def _average_embeddings(vectors: list[list[float]]) -> list[float]:
    if not vectors:
        raise ValueError("No embeddings to average.")
    dimension = len(vectors[0])
    totals = [0.0] * dimension
    for vector in vectors:
        if len(vector) != dimension:
            raise ValueError("Embedding dimension mismatch while averaging.")
        for index, value in enumerate(vector):
            totals[index] += value
    count = float(len(vectors))
    return [value / count for value in totals]


def _l2_normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return list(vector)
    return [value / norm for value in vector]


def _max_api_attempts() -> int:
    raw = os.getenv("TECH_ARCHITECT_API_MAX_ATTEMPTS", "10")
    try:
        value = int(raw)
    except ValueError:
        value = 10
    return max(3, min(value, 50))


def _connection_retry_delay(attempt: int) -> float:
    base = min(30.0, 1.0 * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, 0.5)
    return base + jitter


def _openai_network_hint(error: Exception) -> str:
    msg = str(error).lower()
    lines = [
        "Could not complete the request. Check the following:",
        "  • Network / VPN is up (offline causes connection errors).",
        "  • OPENAI_BASE_URL is unset for api.openai.com, or a full URL "
        "(e.g. https://api.openai.com/v1). A bare hostname or typo breaks DNS.",
        "  • Corporate proxy/firewall: you may need proxy env vars or a reachable endpoint.",
    ]
    if (
        "nodename nor servname" in msg
        or "name or service not known" in msg
        or "failed to resolve" in msg
        or "could not resolve host" in msg
    ):
        lines.insert(
            1,
            "  • DNS failed to resolve the API host — fix OPENAI_BASE_URL or DNS/VPN.",
        )
    return "\n".join(lines)


def _exit_api_unreachable(error: Exception) -> None:
    console.print("[bold red]OpenAI API unreachable after repeated retries.[/bold red]")
    console.print(_openai_network_hint(error))
    raise typer.Exit(code=1) from error


def embed_chunk_texts_with_retry(client: OpenAI, texts: list[str]) -> list[list[float]]:
    """Embed many strings in as few API calls as possible; retry rate limits and outages."""

    if not texts:
        return []

    max_attempts = _max_api_attempts()
    attempt = 1
    while True:
        try:
            return embed_texts(client, texts)
        except RateLimitError as error:
            if attempt >= max_attempts:
                raise
            delay = _retry_delay_seconds(error, attempt)
            console.print(
                f"[yellow]Rate limited on embeddings (attempt {attempt}/{max_attempts}). "
                f"Retrying in {delay:.2f}s...[/yellow]"
            )
            time.sleep(delay)
            attempt += 1
        except (APIConnectionError, APITimeoutError) as error:
            if attempt >= max_attempts:
                _exit_api_unreachable(error)
            delay = _connection_retry_delay(attempt)
            console.print(
                f"[yellow]API connection issue on embeddings ({attempt}/{max_attempts}): "
                f"{error!s}. Retrying in {delay:.1f}s...[/yellow]"
            )
            time.sleep(delay)
            attempt += 1


def embed_single_text_with_retry(client: OpenAI, text: str) -> list[float]:
    """Embed one string (wrapper around batched API)."""

    return embed_chunk_texts_with_retry(client, [text])[0]


def chat_completions_create_with_retry(client: OpenAI, **kwargs: Any):
    """chat.completions.create with retries for rate limits and connection errors."""

    max_attempts = _max_api_attempts()
    attempt = 1
    while True:
        try:
            return client.chat.completions.create(**kwargs)
        except RateLimitError as error:
            if attempt >= max_attempts:
                raise
            delay = _retry_delay_seconds(error, attempt)
            console.print(
                f"[yellow]Rate limited on chat completion ({attempt}/{max_attempts}). "
                f"Retrying in {delay:.2f}s...[/yellow]"
            )
            time.sleep(delay)
            attempt += 1
        except (APIConnectionError, APITimeoutError) as error:
            if attempt >= max_attempts:
                _exit_api_unreachable(error)
            delay = _connection_retry_delay(attempt)
            console.print(
                f"[yellow]API connection issue on chat ({attempt}/{max_attempts}): "
                f"{error!s}. Retrying in {delay:.1f}s...[/yellow]"
            )
            time.sleep(delay)
            attempt += 1


def embed_text_as_single_vector(client: OpenAI, text: str) -> list[float]:
    """Return one embedding vector for arbitrary-length text by splitting and merging if needed."""

    stripped = text.strip()
    if not stripped:
        raise ValueError("Cannot embed empty text.")

    try:
        return embed_single_text_with_retry(client, stripped)
    except BadRequestError as error:
        if not _is_embedding_length_error(error):
            raise

    left, right = _split_text_in_half(stripped)
    if not right:
        raise typer.BadParameter(
            "Embedding input exceeded model limits and could not be split smaller. "
            "Try lowering TECH_ARCHITECT_EMBED_MAX_CHARS / TECH_ARCHITECT_EMBED_CHUNK_CHARS, "
            "or exclude extremely dense files from knowledge_sources.yaml."
        ) from error

    console.print(
        f"[yellow]Embedding input too long; splitting one segment ({len(stripped)} chars) "
        f"into {len(left)} + {len(right)} chars...[/yellow]"
    )

    left_vector = embed_text_as_single_vector(client, left) if left else None
    right_vector = embed_text_as_single_vector(client, right) if right else None
    pieces = [vector for vector in (left_vector, right_vector) if vector is not None]
    if not pieces:
        raise typer.BadParameter(
            "Embedding split produced no embeddable segments. "
            "Try lowering TECH_ARCHITECT_EMBED_MAX_CHARS / TECH_ARCHITECT_EMBED_CHUNK_CHARS."
        )
    return _l2_normalize(_average_embeddings(pieces))


def embed_vectors_for_chunks(client: OpenAI, chunks: list[Chunk]) -> list[list[float]]:
    """One embedding per chunk: batched API calls; split batch or text on token-limit errors."""

    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    try:
        return embed_chunk_texts_with_retry(client, texts)
    except BadRequestError as error:
        if not _is_embedding_length_error(error):
            raise
        if len(chunks) == 1:
            return [embed_text_as_single_vector(client, chunks[0].text)]
        mid = max(1, len(chunks) // 2)
        return embed_vectors_for_chunks(client, chunks[:mid]) + embed_vectors_for_chunks(client, chunks[mid:])


def _retry_delay_seconds(error: Exception, attempt: int) -> float:
    # Try to use server hint ("Please try again in 373ms"), else exponential backoff.
    message = str(error)
    match = re.search(r"try again in\s+(\d+)ms", message, flags=re.IGNORECASE)
    if match:
        base = max(0.2, int(match.group(1)) / 1000.0)
    else:
        base = min(8.0, 0.5 * (2 ** (attempt - 1)))
    jitter = random.uniform(0.0, 0.25)
    return base + jitter


def get_collection(config: dict[str, Any], index_dir: Path):
    chroma = chromadb.PersistentClient(path=str(index_dir))
    return chroma.get_or_create_collection(name=config["index_name"])


def _validate_openai_base_url() -> None:
    raw = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if not raw:
        return
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise typer.BadParameter(
            f"OPENAI_BASE_URL must be a full URL with scheme and host (got {raw!r}). "
            "Example: https://api.openai.com/v1"
        )
    if not parsed.hostname:
        raise typer.BadParameter(
            f"OPENAI_BASE_URL has no hostname (got {raw!r}). Example: https://api.openai.com/v1"
        )


def _openai_target_hostname() -> str:
    raw = (os.getenv("OPENAI_BASE_URL") or "").strip()
    if raw:
        hostname = urlparse(raw).hostname
        if hostname:
            return hostname
    return "api.openai.com"


def _verify_openai_host_resolves() -> None:
    if os.getenv("TECH_ARCHITECT_SKIP_OPENAI_DNS_CHECK", "").strip().lower() in (
        "1",
        "true",
        "yes",
    ):
        return
    host = _openai_target_hostname()
    try:
        socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except socket.gaierror as error:
        raise typer.BadParameter(
            f"DNS could not resolve OpenAI API host {host!r} ({error}). "
            "Fix OPENAI_BASE_URL, reconnect network/VPN, or set DNS. "
            "To skip this check (not recommended): TECH_ARCHITECT_SKIP_OPENAI_DNS_CHECK=1"
        ) from error


def require_openai_client() -> OpenAI:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        raise typer.BadParameter("OPENAI_API_KEY is required for embeddings or local answer generation.")
    _validate_openai_base_url()
    _verify_openai_host_resolves()
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
    batch_size: int = typer.Option(64, help="Embedding batch size (many chunks per API request)."),
    skip_existing: bool = typer.Option(
        True,
        "--skip-existing/--reindex-all",
        help="Skip chunks already in the index (fast resume). Use --reindex-all to re-embed everything.",
    ),
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
    if skip_existing:
        console.print("[dim]Skipping chunk IDs already stored (--reindex-all to force full rebuild).[/dim]")

    skipped_total = 0
    offset = 0
    current_batch_size = max(1, batch_size)
    while offset < len(chunks):
        batch = chunks[offset : offset + current_batch_size]
        skipped_here = 0
        pending = list(batch)
        if skip_existing:
            found = collection.get(ids=[chunk.id for chunk in batch])
            have = set(found.get("ids") or [])
            pending = [c for c in batch if c.id not in have]
            skipped_here = len(batch) - len(pending)
            if not pending:
                skipped_total += skipped_here
                offset += len(batch)
                console.print(
                    f"Progress {offset}/{len(chunks)} (skipped {skipped_here} already in index)..."
                )
                continue

        try:
            embeddings = embed_vectors_for_chunks(client, pending)
        except RateLimitError:
            if current_batch_size == 1:
                raise
            current_batch_size = max(1, current_batch_size // 2)
            console.print(
                f"[yellow]Rate limit persisted; reducing batch size to {current_batch_size} and retrying...[/yellow]"
            )
            continue

        collection.upsert(
            ids=[chunk.id for chunk in pending],
            documents=[chunk.text for chunk in pending],
            metadatas=[chunk.metadata for chunk in pending],
            embeddings=embeddings,
        )
        offset += len(batch)
        if skip_existing:
            skipped_total += skipped_here
        new_count = len(pending)
        if skip_existing and new_count < len(batch):
            console.print(
                f"Progress {offset}/{len(chunks)} (embedded {new_count} new, {len(batch) - new_count} skipped)..."
            )
        else:
            console.print(f"Progress {offset}/{len(chunks)} (embedded {new_count} chunk(s) this step)...")

    console.print("[green]Knowledge index is ready.[/green]")
    if skip_existing and skipped_total:
        console.print(
            f"[cyan]Resume: skipped {skipped_total} chunk(s) that were already indexed.[/cyan]"
        )


def retrieve(question: str, config_path: Path, index_dir: Path | None, top_k: int) -> list[dict[str, str]]:
    config = load_config(config_path)
    client = require_openai_client()
    resolved_index_dir = resolve_index_dir(config_path, index_dir)
    collection = get_collection(config, resolved_index_dir)
    query_embedding = embed_text_as_single_vector(client, question)

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

    response = chat_completions_create_with_retry(
        client,
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
