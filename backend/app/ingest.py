import hashlib
import logging
import os
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

import asyncpg

from app.chunking import CodeChunk, chunk_source
from app.clone import clone_repo
from app.config import settings
from app.embeddings import embed_texts
from app.ignore_list import detect_language, should_ignore_dir, should_ignore_file
from app.static_analysis import run_static_analysis
from app.summarize import find_readme, summarize_file, summarize_project

logger = logging.getLogger(__name__)

ChunkFn = Callable[[bytes, str], list[CodeChunk]]


def _iter_source_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if not should_ignore_dir(d)]
        for filename in filenames:
            if should_ignore_file(filename):
                continue
            language = detect_language(filename)
            if language is None:
                continue
            yield Path(dirpath) / filename, language


async def _set_status(pool: asyncpg.Pool, repo_id: int, status: str, error_message: str | None = None) -> None:
    await pool.execute(
        "UPDATE repos SET status=$2, error_message=$3, updated_at=now() WHERE id=$1",
        repo_id,
        status,
        error_message,
    )


async def ingest_local_repo(
    pool: asyncpg.Pool,
    repo_id: int,
    cloned_path: Path,
    chunk_fn: ChunkFn = chunk_source,
    generate_summaries: bool = False,
) -> int:
    """Walk an already-cloned repo, chunk it with chunk_fn, embed, and store.

    Shared by production ingestion (AST chunking) and the eval harness, which
    swaps in a naive fixed-size chunker to compare recall@k against the same
    file set.

    A file is only re-chunked/re-embedded if its content hash changed, or if
    the configured embedding model changed since it was last embedded — this
    is what makes Feature D's "regenerate only on change" caching correct
    even when someone swaps in a fine-tuned embedding model (Phase 5).
    """
    kept_paths: list[str] = []

    for file_path, language in _iter_source_files(cloned_path):
        relative_path = file_path.relative_to(cloned_path).as_posix()
        kept_paths.append(relative_path)

        source_bytes = file_path.read_bytes()
        content_hash = hashlib.sha256(source_bytes).hexdigest()

        existing = await pool.fetchrow(
            "SELECT id, content_hash, summary, embedding_model FROM files WHERE repo_id=$1 AND path=$2",
            repo_id,
            relative_path,
        )
        content_unchanged = existing is not None and existing["content_hash"] == content_hash
        embeddings_unchanged = content_unchanged and existing["embedding_model"] == settings.embedding_model_name

        if embeddings_unchanged:
            continue  # content and embedding model both match what's already stored

        chunks = chunk_fn(source_bytes, language)
        if not chunks:
            if existing is not None:
                await pool.execute("DELETE FROM files WHERE id=$1", existing["id"])
            continue

        if generate_summaries:
            summary = existing["summary"] if (content_unchanged and existing["summary"]) else await summarize_file(
                relative_path, language, chunks
            )
        else:
            summary = existing["summary"] if (existing is not None and content_unchanged) else None

        file_id = await pool.fetchval(
            """
            INSERT INTO files (repo_id, path, language, content_hash, summary, embedding_model)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (repo_id, path)
            DO UPDATE SET
                language = EXCLUDED.language,
                content_hash = EXCLUDED.content_hash,
                summary = EXCLUDED.summary,
                embedding_model = EXCLUDED.embedding_model
            RETURNING id
            """,
            repo_id,
            relative_path,
            language,
            content_hash,
            summary,
            settings.embedding_model_name,
        )

        await pool.execute("DELETE FROM chunks WHERE file_id=$1", file_id)

        texts = [f"{c.docstring or ''}\n{c.code}".strip() for c in chunks]
        vectors = embed_texts(texts)

        rows = [
            (file_id, repo_id, c.symbol_name, c.symbol_type, c.start_line, c.end_line, c.code, c.docstring, vec)
            for c, vec in zip(chunks, vectors)
        ]
        await pool.executemany(
            """
            INSERT INTO chunks
                (file_id, repo_id, symbol_name, symbol_type, start_line, end_line, code, docstring, embedding)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
            """,
            rows,
        )

    if kept_paths:
        await pool.execute("DELETE FROM files WHERE repo_id=$1 AND path <> ALL($2::text[])", repo_id, kept_paths)
    else:
        await pool.execute("DELETE FROM files WHERE repo_id=$1", repo_id)

    return await pool.fetchval("SELECT count(*) FROM chunks WHERE repo_id=$1", repo_id)


async def _store_static_findings(pool: asyncpg.Pool, repo_id: int, findings: list[dict]) -> None:
    await pool.execute("DELETE FROM static_findings WHERE repo_id=$1", repo_id)
    if not findings:
        return

    file_rows = await pool.fetch("SELECT id, path FROM files WHERE repo_id=$1", repo_id)
    path_to_id = {r["path"]: r["id"] for r in file_rows}

    rows = []
    for f in findings:
        file_id = path_to_id.get(f["file_path"])
        if file_id is None:
            continue  # finding on a file we didn't end up chunking/storing
        rows.append((file_id, repo_id, f["tool"], f["severity"], f["line"], f["message"], f["rule_id"]))

    if rows:
        await pool.executemany(
            """
            INSERT INTO static_findings (file_id, repo_id, tool, severity, line, message, rule_id)
            VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
            rows,
        )


async def ingest_repo(pool: asyncpg.Pool, repo_id: int, url: str) -> None:
    try:
        await _set_status(pool, repo_id, "ingesting")

        storage_dir = Path(settings.repo_storage_dir)
        cloned_path = clone_repo(url, storage_dir)
        await pool.execute("UPDATE repos SET cloned_path=$2 WHERE id=$1", repo_id, str(cloned_path))

        total_chunks = await ingest_local_repo(
            pool, repo_id, cloned_path, chunk_fn=chunk_source, generate_summaries=True
        )

        # Feature E: static analysis, independent of the chunk/embedding cache above.
        files_by_language: dict[str, list[Path]] = defaultdict(list)
        for file_path, language in _iter_source_files(cloned_path):
            files_by_language[language].append(file_path)
        findings = run_static_analysis(cloned_path, files_by_language)
        await _store_static_findings(pool, repo_id, findings)

        # Feature D: roll up a project-level summary from the README + entry points + file summaries.
        readme_text = find_readme(cloned_path)
        file_rows = await pool.fetch(
            "SELECT path, summary FROM files WHERE repo_id=$1 AND summary IS NOT NULL ORDER BY path", repo_id
        )
        file_summaries = [(r["path"], r["summary"]) for r in file_rows]
        repo_row = await pool.fetchrow("SELECT name FROM repos WHERE id=$1", repo_id)
        project_summary = await summarize_project(repo_row["name"], url, readme_text, file_summaries)
        if project_summary:
            await pool.execute("UPDATE repos SET summary=$2 WHERE id=$1", repo_id, project_summary)

        await _set_status(pool, repo_id, "ready")
        logger.info("Ingested repo %s (%d chunks, %d static findings)", url, total_chunks, len(findings))
    except Exception as exc:  # noqa: BLE001 - surface any failure as repo status
        logger.exception("Ingestion failed for repo %s", url)
        await _set_status(pool, repo_id, "error", str(exc))
