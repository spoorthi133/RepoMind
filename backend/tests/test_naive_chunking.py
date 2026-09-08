from app.eval.naive_chunking import OVERLAP_LINES, WINDOW_LINES, chunk_naive


def test_source_shorter_than_window_is_one_chunk():
    source = "\n".join(f"line{i}" for i in range(10)).encode()
    chunks = chunk_naive(source)

    assert len(chunks) == 1
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 10


def test_source_longer_than_window_overlaps():
    n = WINDOW_LINES + WINDOW_LINES - OVERLAP_LINES + 5
    source = "\n".join(f"line{i}" for i in range(n)).encode()
    chunks = chunk_naive(source)

    assert chunks[0].start_line == 1
    assert chunks[0].end_line == WINDOW_LINES

    step = WINDOW_LINES - OVERLAP_LINES
    assert chunks[1].start_line == step + 1

    assert chunks[-1].end_line == n

    for c in chunks:
        assert c.symbol_name is None
        assert c.symbol_type == "block"


def test_empty_source_produces_single_empty_chunk():
    chunks = chunk_naive(b"")
    assert len(chunks) == 1
    assert chunks[0].code == ""
