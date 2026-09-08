"""Phase 2 evaluation harness: recall@k for AST chunking vs. naive fixed-size chunking.

Usage (from backend/, with the venv active and Postgres running):
    python -m app.eval.run_eval

Ingests the same already-cloned repo twice — once with the production
AST-aware chunker (app.chunking.chunk_source) and once with the naive
fixed-size-window baseline (app.eval.naive_chunking.chunk_naive) — into two
separate eval repo rows, then runs every hand-labeled question against both
via the real hybrid_search() and reports recall@k.
"""

import asyncio
import json
import re
from pathlib import Path

from app.chunking import chunk_source
from app.clone import clone_repo
from app.config import settings
from app.db import close_pool, get_pool, init_pool
from app.eval.naive_chunking import chunk_naive
from app.ingest import ingest_local_repo
from app.retrieval import hybrid_search

FLASK_URL = "https://github.com/pallets/flask.git"
K_VALUES = [1, 3, 5, 10]
QUESTIONS_PATH = Path(__file__).parent / "questions.json"


def _results_path() -> Path:
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "_", settings.embedding_model_name).strip("_")
    return Path(__file__).parent / f"results_{slug}.json"


async def _get_or_create_eval_repo(pool, url: str, name: str) -> int:
    row = await pool.fetchrow(
        """
        INSERT INTO repos (url, name, status)
        VALUES ($1, $2, 'ingesting')
        ON CONFLICT (url) DO UPDATE SET status = 'ingesting', updated_at = now()
        RETURNING id
        """,
        url,
        name,
    )
    return row["id"]


def _is_hit(chunk: dict, question: dict) -> bool:
    return (
        chunk["file_path"] == question["file_path"]
        and chunk["start_line"] <= question["target_line"] <= chunk["end_line"]
    )


async def _recall_for_strategy(pool, repo_id: int, questions: list[dict], max_k: int) -> dict:
    per_question = []
    hits_at_k = {k: 0 for k in K_VALUES}

    for q in questions:
        results = await hybrid_search(pool, repo_id, q["question"], k=max_k)
        first_hit_rank = None
        for rank, chunk in enumerate(results, start=1):
            if _is_hit(chunk, q):
                first_hit_rank = rank
                break

        for k in K_VALUES:
            if first_hit_rank is not None and first_hit_rank <= k:
                hits_at_k[k] += 1

        per_question.append(
            {
                "question": q["question"],
                "symbol": q["symbol"],
                "first_hit_rank": first_hit_rank,
            }
        )

    n = len(questions)
    recall = {k: hits_at_k[k] / n for k in K_VALUES}
    return {"recall_at_k": recall, "hits_at_k": hits_at_k, "num_questions": n, "per_question": per_question}


async def main() -> None:
    questions = json.loads(QUESTIONS_PATH.read_text())
    max_k = max(K_VALUES)

    await init_pool()
    pool = get_pool()

    try:
        storage_dir = Path(settings.repo_storage_dir)
        cloned_path = storage_dir / "flask"
        if not cloned_path.exists():
            print(f"Cloning {FLASK_URL} ...")
            cloned_path = clone_repo(FLASK_URL, storage_dir)

        ast_repo_id = await _get_or_create_eval_repo(pool, "eval://flask-ast-chunking", "flask (eval: AST chunking)")
        naive_repo_id = await _get_or_create_eval_repo(pool, "eval://flask-naive-chunking", "flask (eval: naive chunking)")

        print("Ingesting with AST-aware chunking...")
        ast_chunk_count = await ingest_local_repo(pool, ast_repo_id, cloned_path, chunk_fn=chunk_source)
        await pool.execute("UPDATE repos SET status='ready' WHERE id=$1", ast_repo_id)
        print(f"  {ast_chunk_count} chunks")

        print("Ingesting with naive fixed-size chunking...")
        naive_chunk_count = await ingest_local_repo(pool, naive_repo_id, cloned_path, chunk_fn=chunk_naive)
        await pool.execute("UPDATE repos SET status='ready' WHERE id=$1", naive_repo_id)
        print(f"  {naive_chunk_count} chunks")

        print(f"\nRunning {len(questions)} questions against both strategies...")
        ast_result = await _recall_for_strategy(pool, ast_repo_id, questions, max_k)
        naive_result = await _recall_for_strategy(pool, naive_repo_id, questions, max_k)

        print(f"\n=== Recall@k: AST-aware vs. naive chunking (embedding model: {settings.embedding_model_name}) ===")
        header = f"{'k':>4} | {'AST recall':>10} | {'Naive recall':>12}"
        print(header)
        print("-" * len(header))
        for k in K_VALUES:
            print(f"{k:>4} | {ast_result['recall_at_k'][k]:>10.2%} | {naive_result['recall_at_k'][k]:>12.2%}")

        report = {
            "repo": FLASK_URL,
            "embedding_model": settings.embedding_model_name,
            "num_questions": len(questions),
            "chunk_counts": {"ast": ast_chunk_count, "naive": naive_chunk_count},
            "ast": ast_result,
            "naive": naive_result,
        }
        results_path = _results_path()
        results_path.write_text(json.dumps(report, indent=2))
        print(f"\nFull report written to {results_path}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
