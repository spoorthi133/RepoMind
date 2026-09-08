from app.chunking import CodeChunk

WINDOW_LINES = 40
OVERLAP_LINES = 10


def chunk_naive(source: bytes, language: str | None = None) -> list[CodeChunk]:
    """Baseline chunker: fixed-size sliding line windows, no AST awareness.

    Used only by the eval harness to measure how much AST-aware chunking
    (app.chunking.chunk_source) improves retrieval recall@k over this naive
    approach, on the same file set.
    """
    text = source.decode("utf-8", "replace")
    lines = text.split("\n")
    n = len(lines)
    if n == 0:
        return []

    step = WINDOW_LINES - OVERLAP_LINES
    chunks: list[CodeChunk] = []
    i = 0
    while True:
        end = min(i + WINDOW_LINES, n)
        chunks.append(
            CodeChunk(
                symbol_name=None,
                symbol_type="block",
                start_line=i + 1,
                end_line=end,
                code="\n".join(lines[i:end]),
                docstring=None,
            )
        )
        if end >= n:
            break
        i += step

    return chunks
