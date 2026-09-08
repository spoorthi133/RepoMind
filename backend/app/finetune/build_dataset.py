"""Phase 5 dataset builder: (docstring, code) pairs for contrastive fine-tuning.

Docstrings stand in as a proxy for natural-language questions about a chunk
of code — the same role a user's real question plays at query time. Sourced
directly from the AST chunks we already extracted and stored (repo_id=1,
pallets/flask), no new data collection needed.

Usage (from backend/, with Postgres running):
    python -m app.finetune.build_dataset
"""

import asyncio
import json
from pathlib import Path

from app.db import close_pool, get_pool, init_pool

OUTPUT_PATH = Path(__file__).parent / "data" / "pairs.jsonl"
MIN_DOCSTRING_LEN = 5
MIN_CODE_LEN = 20


async def main() -> None:
    await init_pool()
    pool = get_pool()
    try:
        rows = await pool.fetch(
            """
            SELECT symbol_name, docstring, code
            FROM chunks
            WHERE repo_id = 1
              AND docstring IS NOT NULL
              AND length(trim(docstring)) >= $1
              AND length(code) >= $2
            """,
            MIN_DOCSTRING_LEN,
            MIN_CODE_LEN,
        )
    finally:
        await close_pool()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"symbol_name": r["symbol_name"], "docstring": r["docstring"].strip(), "code": r["code"]}) + "\n")

    print(f"Wrote {len(rows)} (docstring, code) pairs to {OUTPUT_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
