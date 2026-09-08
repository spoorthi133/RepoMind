import asyncpg

from app.embeddings import embed_text

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
    rows = await pool.fetch(
        f"""
        SELECT {_SELECT_FIELDS}
        FROM chunks c
        JOIN files f ON f.id = c.file_id
        WHERE c.repo_id = $1 AND c.content_tsv @@ plainto_tsquery('english', $2)
        ORDER BY ts_rank(c.content_tsv, plainto_tsquery('english', $2)) DESC
        LIMIT $3
        """,
        repo_id,
        query,
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
