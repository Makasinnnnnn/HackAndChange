import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def engine():
    from app.catalog import load_catalog
    from app.engine import Engine

    materials, mode, version = load_catalog()
    return Engine(materials, mode, version)


@pytest.fixture
def client(monkeypatch):
    from app.main import app
    from fastapi.testclient import TestClient

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    with TestClient(app) as test_client:
        yield test_client
