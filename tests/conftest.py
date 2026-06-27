from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db import init_db
from app.main import app
from app.services import agent as agent_module


def _make_stub_anthropic():
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "stub_tool"
    tool_block.input = {
        "quote_text": "Stub quote text.",
        "customer_note": "Stub note.",
        "subject": "Stub subject",
        "body": "Stub body.",
        "title": "Stub",
        "status": "stub",
        "summary": "Stub summary.",
        "vehicle": "Stub vehicle",
        "quote_amount": 100,
        "parts_used": "none",
        "labor_notes": "none",
    }
    response = MagicMock()
    response.content = [tool_block]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = response
    mock_cls = MagicMock(return_value=mock_client)
    return mock_cls


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("DATABASE_URL", str(tmp_path / "shopfloor-test.db"))
    monkeypatch.setenv("SCALEKIT_MODE", "stub")
    agent_module._crm_schema_cache = None
    with patch("anthropic.Anthropic", _make_stub_anthropic()):
        init_db(reset=True)
        with TestClient(app) as test_client:
            yield test_client
    agent_module._crm_schema_cache = None
