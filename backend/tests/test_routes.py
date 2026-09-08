async def _fake_stream(*args, **kwargs):
    for token in ["Hello", " world"]:
        yield token


def test_create_repo_inserts_and_schedules_ingest(client, fake_pool, monkeypatch):
    ingest_calls = []

    async def fake_ingest_repo(pool, repo_id, url):
        ingest_calls.append((repo_id, url))

    monkeypatch.setattr("app.api.routes.ingest_repo", fake_ingest_repo)
    fake_pool.fetchrow.return_value = {
        "id": 1,
        "url": "https://github.com/pallets/flask.git",
        "name": "flask",
        "status": "pending",
        "error_message": None,
    }

    response = client.post("/api/repos", json={"url": "https://github.com/pallets/flask.git"})

    assert response.status_code == 200
    assert response.json()["status"] == "pending"
    assert ingest_calls == [(1, "https://github.com/pallets/flask.git")]


def test_get_repo_not_found(client, fake_pool):
    fake_pool.fetchrow.return_value = None
    response = client.get("/api/repos/999")
    assert response.status_code == 404


def test_get_repo_found(client, fake_pool):
    fake_pool.fetchrow.return_value = {
        "id": 1,
        "url": "https://example.com/repo.git",
        "name": "repo",
        "status": "ready",
        "error_message": None,
    }
    response = client.get("/api/repos/1")
    assert response.status_code == 200
    assert response.json()["name"] == "repo"


def test_chat_repo_not_found(client, fake_pool):
    fake_pool.fetchrow.return_value = None
    response = client.post("/api/repos/1/chat", json={"question": "how does this work?"})
    assert response.status_code == 404


def test_chat_repo_not_ready(client, fake_pool):
    fake_pool.fetchrow.return_value = {"status": "ingesting"}
    response = client.post("/api/repos/1/chat", json={"question": "how does this work?"})
    assert response.status_code == 409


def test_chat_streams_citations_then_tokens(client, fake_pool, monkeypatch):
    fake_pool.fetchrow.return_value = {"status": "ready"}

    chunk = {
        "file_path": "app/main.py",
        "start_line": 1,
        "end_line": 5,
        "symbol_name": "handler",
    }

    async def fake_hybrid_search(pool, repo_id, question, k=8):
        return [chunk]

    monkeypatch.setattr("app.api.routes.hybrid_search", fake_hybrid_search)
    monkeypatch.setattr("app.api.routes.stream_answer", lambda question, chunks: _fake_stream())

    response = client.post("/api/repos/1/chat", json={"question": "how does this work?"})

    assert response.status_code == 200
    body = response.text
    assert "event: citations" in body
    assert "app/main.py" in body
    assert "event: token" in body
    assert "Hello" in body
    assert "event: done" in body


def test_get_summary(client, fake_pool):
    fake_pool.fetchrow.return_value = {"summary": "A project.", "status": "ready"}
    fake_pool.fetch.return_value = [{"path": "app/main.py", "summary": "Entry point."}]

    response = client.get("/api/repos/1/summary")

    assert response.status_code == 200
    data = response.json()
    assert data["repo_summary"] == "A project."
    assert data["files"] == [{"path": "app/main.py", "summary": "Entry point."}]


def test_get_summary_repo_not_found(client, fake_pool):
    fake_pool.fetchrow.return_value = None
    response = client.get("/api/repos/1/summary")
    assert response.status_code == 404


def test_get_chunk_source_not_found(client, fake_pool):
    fake_pool.fetchrow.return_value = None
    response = client.get(
        "/api/repos/1/chunk", params={"file_path": "a.py", "start_line": 1, "end_line": 2}
    )
    assert response.status_code == 404


def test_get_chunk_source_found(client, fake_pool):
    fake_pool.fetchrow.return_value = {"code": "def f(): pass"}
    response = client.get(
        "/api/repos/1/chunk", params={"file_path": "a.py", "start_line": 1, "end_line": 2}
    )
    assert response.status_code == 200
    assert response.json() == {"code": "def f(): pass"}


def test_diagnose_repo_not_ready(client, fake_pool):
    fake_pool.fetchrow.return_value = {"status": "pending"}
    response = client.post("/api/repos/1/diagnose", json={"error_text": "NameError: x"})
    assert response.status_code == 409


def test_diagnose_streams_citations_findings_and_tokens(client, fake_pool, monkeypatch):
    fake_pool.fetchrow.return_value = {"status": "ready"}

    chunk = {
        "file_id": 7,
        "file_path": "app/main.py",
        "start_line": 1,
        "end_line": 5,
        "symbol_name": "handler",
    }
    finding = {"file_path": "app/main.py", "tool": "pylint", "severity": "error", "line": 3, "message": "boom"}

    async def fake_hybrid_search(pool, repo_id, error_text, k=6):
        return [chunk]

    fake_pool.fetch.return_value = [finding]
    monkeypatch.setattr("app.api.routes.hybrid_search", fake_hybrid_search)
    monkeypatch.setattr(
        "app.api.routes.stream_diagnosis", lambda error_text, chunks, findings: _fake_stream()
    )

    response = client.post("/api/repos/1/diagnose", json={"error_text": "NameError: x"})

    assert response.status_code == 200
    body = response.text
    assert "event: citations" in body
    assert "event: findings" in body
    assert "boom" in body
    assert "event: token" in body
    assert "event: done" in body
