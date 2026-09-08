"""Phase 5: fine-tune a small sentence-transformer on (docstring, code) pairs.

Contrastive training via MultipleNegativesRankingLoss (in-batch negatives) —
the standard, honest way to do this with a small dataset: no hand-constructed
negative pairs needed, every other example in a batch acts as a negative.

This is a small, real fine-tune (a few hundred pairs) — not something to
oversell as large-scale training. Its value is measured externally: see
app/eval/run_eval.py, re-run with EMBEDDING_MODEL_NAME pointed at this
model's output directory, compared against the off-the-shelf baseline on the
same held-out 25-question eval set (the eval questions were never used here).

Usage (from backend/, with the venv active):
    python -m app.finetune.train
"""

import json
from pathlib import Path

from sentence_transformers import InputExample, SentenceTransformer, losses
from torch.utils.data import DataLoader

from app.config import settings

DATA_PATH = Path(__file__).parent / "data" / "pairs.jsonl"
OUTPUT_DIR = Path(__file__).parent / "output" / "finetuned-code-embedder"

BASE_MODEL = settings.embedding_model_name
BATCH_SIZE = 16
EPOCHS = 4


def main() -> None:
    pairs = [json.loads(line) for line in DATA_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    print(f"Loaded {len(pairs)} training pairs from {DATA_PATH}")

    examples = [InputExample(texts=[p["docstring"], p["code"]]) for p in pairs]

    model = SentenceTransformer(BASE_MODEL)
    train_dataloader = DataLoader(examples, shuffle=True, batch_size=BATCH_SIZE)
    train_loss = losses.MultipleNegativesRankingLoss(model)

    warmup_steps = max(1, int(len(train_dataloader) * EPOCHS * 0.1))
    model.fit(
        train_objectives=[(train_dataloader, train_loss)],
        epochs=EPOCHS,
        warmup_steps=warmup_steps,
        show_progress_bar=True,
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    model.save(str(OUTPUT_DIR))
    print(f"Saved fine-tuned model to {OUTPUT_DIR}")
    print(f"\nTo use it: set EMBEDDING_MODEL_NAME={OUTPUT_DIR} in backend/.env")


if __name__ == "__main__":
    main()
