from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "shopfloor-test.db"))
    monkeypatch.setenv("SCALEKIT_MODE", "stub")
    init_db(reset=True)
    with TestClient(app) as test_client:
        yield test_client
