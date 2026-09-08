"""Integration test that exercises the real pgvector SQL in app.retrieval.

Unlike test_retrieval.py (which mocks pool.fetch entirely and only checks the
Python-side RRF merge), this test inserts real rows with real `vector(384)`
embeddings into Postgres and lets hybrid_search() run its actual
`ORDER BY c.embedding <=> $2` (pgvector cosine distance) and
`content_tsv @@ plainto_tsquery(...)` (full-text) queries.

Requires the docker-compose Postgres (with the pgvector extension and
db/init.sql schema already applied) to be reachable at settings.database_url.
Skips automatically if it isn't -- this test never touches CI or a dev's
machine that doesn't have `docker compose up -d db` running.
"""

import uuid

import asyncpg
import pytest
from pgvector.asyncpg import register_vector

from app.config import settings
from app.retrieval import hybrid_search

EMBED_DIM = settings.embedding_dim


def _unit_vector(index: int) -> list[float]:
    vec = [0.0] * EMBED_DIM
    vec[index] = 1.0
    return vec


@pytest.fixture
async def pg_conn():
    try:
        conn = await asyncpg.connect(settings.database_url, timeout=3)
    except (OSError, asyncpg.PostgresError) as exc:
        pytest.skip(f"Postgres not reachable at DATABASE_URL ({exc}); run `docker compose up -d db` to enable this test")
        return

    try:
        await register_vector(conn)
        table_exists = await conn.fetchval(
            "SELECT to_regclass('public.chunks') IS NOT NULL"
        )
        if not table_exists:
            pytest.skip("chunks table not found; apply db/init.sql to the running Postgres first")
        yield conn
    finally:
        await conn.close()


@pytest.fixture
async def seeded_repo(pg_conn):
    """Insert one repo with two chunks that have distinguishable embeddings
    and distinguishable text, so we can tell vector search and keyword search
    apart from a plain "return everything" query.
    """
    url = f"test://pgvector-integration-{uuid.uuid4()}"
    await pg_conn.execute("DELETE FROM repos WHERE url = $1", url)

    repo_id = await pg_conn.fetchval(
        "INSERT INTO repos (url, name, status) VALUES ($1, $2, 'ready') RETURNING id",
        url,
        "pgvector-integration-test",
    )
    file_id = await pg_conn.fetchval(
        """
        INSERT INTO files (repo_id, path, language, content_hash)
        VALUES ($1, $2, 'python', 'deadbeef')
        RETURNING id
        """,
        repo_id,
        "math_ops.py",
    )
    await pg_conn.executemany(
        """
        INSERT INTO chunks
            (file_id, repo_id, symbol_name, symbol_type, start_line, end_line, code, docstring, embedding)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        """,
        [
            (
                file_id, repo_id, "add_two", "function", 1, 2,
                "def add_two(a, b):\n    return a + b",
                "adds two numbers together",
                _unit_vector(0),
            ),
            (
                file_id, repo_id, "subtract_two", "function", 4, 5,
                "def subtract_two(a, b):\n    return a - b",
                "subtracts one number from another",
                _unit_vector(1),
            ),
        ],
    )

    try:
        yield repo_id
    finally:
        await pg_conn.execute("DELETE FROM repos WHERE id = $1", repo_id)


async def test_hybrid_search_ranks_by_real_cosine_distance(pg_conn, seeded_repo, monkeypatch):
    # Pretend the query embeds to exactly add_two's vector, so pgvector's
    # `<=>` cosine-distance operator -- not our RRF code -- is what decides
    # add_two ranks first.
    monkeypatch.setattr("app.retrieval.embed_text", lambda query: _unit_vector(0))

    results = await hybrid_search(pg_conn, seeded_repo, "irrelevant text with no keyword overlap", k=2)

    assert len(results) >= 1
    assert results[0]["symbol_name"] == "add_two"
    assert results[0]["file_path"] == "math_ops.py"


async def test_hybrid_search_matches_via_real_fulltext_index(pg_conn, seeded_repo, monkeypatch):
    # Point the (fake) query embedding at the *other* chunk so a top keyword
    # match for "subtract" can only come from the real tsvector/GIN index,
    # not from vector similarity.
    monkeypatch.setattr("app.retrieval.embed_text", lambda query: _unit_vector(0))

    results = await hybrid_search(pg_conn, seeded_repo, "subtracts one number from another", k=2)

    symbol_names = [r["symbol_name"] for r in results]
    assert "subtract_two" in symbol_names
