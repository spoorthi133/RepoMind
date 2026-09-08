from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def fake_pool(monkeypatch):
    pool = AsyncMock()
    monkeypatch.setattr("app.api.routes.get_pool", lambda: pool)
    return pool


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr("app.main.init_pool", AsyncMock())
    monkeypatch.setattr("app.main.close_pool", AsyncMock())

    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
