import re

import asyncpg

from app.embeddings import embed_text

_WORD_RE = re.compile(r"[A-Za-z0-9_]+")


def _or_tsquery(query: str) -> str:
    """Turns free text into an OR-joined tsquery ('term1 | term2 | ...').

    plainto_tsquery/websearch_to_tsquery both AND every word together, which
    means a natural question like "what does X do?" needs every single word
    (including "what", "does") to appear in a chunk to match at all -- in
    practice that returns nothing for conversational queries. OR-ing lets
    ts_rank prefer chunks matching more terms without requiring all of them.
    """
    return " | ".join(_WORD_RE.findall(query))


_SELECT_FIELDS = """
    c.id, c.file_id, f.path AS file_path, c.symbol_name, c.symbol_type,
    c.start_line, c.end_line, c.code, c.docstring
"""


async def _vector_search(pool: asyncpg.Pool, repo_id: int, embedding: list[float], k: int) -> list[dict]:
    rows = await pool.fetch(
        f"""
        SELECT {_SELECT_FIELDS}
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        WHERE c.repo_id = $1
        ORDER BY c.embedding <=> $2
        LIMIT $3
        """,
        repo_id,
        embedding,
        k,
    )
    return [dict(r) for r in rows]


async def _keyword_search(pool: asyncpg.Pool, repo_id: int, query: str, k: int) -> list[dict]:
    tsquery_str = _or_tsquery(query)
    if not tsquery_str:
        return []

    rows = await pool.fetch(
        f"""
        SELECT {_SELECT_FIELDS}
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        WHERE c.repo_id = $1 AND c.content_tsv @@ to_tsquery('english', $2)
        ORDER BY ts_rank(c.content_tsv, to_tsquery('english', $2)) DESC
        LIMIT $3
        """,
        repo_id,
        tsquery_str,
        k,
    )
    return [dict(r) for r in rows]


async def hybrid_search(pool: asyncpg.Pool, repo_id: int, query: str, k: int = 8) -> list[dict]:
    """Vector + keyword search merged via reciprocal rank fusion."""
    fetch_k = max(k * 2, 10)
    embedding = embed_text(query)

    vector_rows = await _vector_search(pool, repo_id, embedding, fetch_k)
    keyword_rows = await _keyword_search(pool, repo_id, query, fetch_k)

    rrf_k = 60
    scores: dict[int, float] = {}
    records: dict[int, dict] = {}
    for result_set in (vector_rows, keyword_rows):
        for rank, row in enumerate(result_set):
            scores[row["id"]] = scores.get(row["id"], 0.0) + 1.0 / (rrf_k + rank)
            records[row["id"]] = row

    ranked_ids = sorted(scores, key=lambda i: scores[i], reverse=True)[:k]
    return [records[i] for i in ranked_ids]
