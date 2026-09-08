from app.retrieval import hybrid_search


class FakePool:
    def __init__(self, vector_rows, keyword_rows):
        self.vector_rows = vector_rows
        self.keyword_rows = keyword_rows

    async def fetch(self, sql, *args):
        if "c.embedding <=>" in sql:
            return self.vector_rows
        return self.keyword_rows


async def test_hybrid_search_fuses_vector_and_keyword_ranks_via_rrf(monkeypatch):
    monkeypatch.setattr("app.retrieval.embed_text", lambda query: [0.0] * 384)

    vector_rows = [{"id": 1}, {"id": 2}, {"id": 3}]
    keyword_rows = [{"id": 2}, {"id": 4}]
    pool = FakePool(vector_rows, keyword_rows)

    results = await hybrid_search(pool, repo_id=1, query="anything", k=3)

    # id 2 appears in both lists (rank 1 in vector, rank 0 in keyword) so it
    # should out-rank ids that only appear in one list.
    assert [r["id"] for r in results] == [2, 1, 4]


async def test_hybrid_search_respects_k(monkeypatch):
    monkeypatch.setattr("app.retrieval.embed_text", lambda query: [0.0] * 384)

    pool = FakePool(vector_rows=[{"id": i} for i in range(1, 6)], keyword_rows=[])
    results = await hybrid_search(pool, repo_id=1, query="anything", k=2)

    assert len(results) == 2
