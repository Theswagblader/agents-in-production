import pytest

from app.actors import ACTORS
from app.services.scalekit import send_customer_email_as_actor
from app.services import scalekit as scalekit_service


@pytest.fixture
def quoted_job() -> dict[str, object]:
    return {
        "job_id": "job_a",
        "customer_email": "avery@example.com",
        "vehicle": "2018 Honda Civic",
        "symptom": "Grinding noise when braking",
        "quote_text": "Estimated brake repair: $460.",
    }


def test_real_mode_reports_missing_scalekit_config(monkeypatch, quoted_job):
    monkeypatch.setenv("SCALEKIT_MODE", "real")
    for name in (
        "SCALEKIT_ENV_URL",
        "SCALEKIT_CLIENT_ID",
        "SCALEKIT_CLIENT_SECRET",
        "SCALEKIT_GMAIL_SEND_TOOL_NAME",
        "SHOPFLOOR_DEMO_TO_EMAIL",
    ):
        monkeypatch.delenv(name, raising=False)

    result = send_customer_email_as_actor(ACTORS["sales_sara"], quoted_job)

    assert result.ok is False
    assert result.outcome == "failed"
    assert result.provider == "gmail"
    assert result.tool_name is None
    assert result.decision_source == "scalekit_config"
    assert "Missing required Scalekit env vars" in result.detail
    assert "SCALEKIT_CLIENT_SECRET" in result.detail


class FakeTools:
    def __init__(self, tool_names: list[str]):
        self.tool_names = tool_names
        self.calls: list[dict] = []

    def list_scoped_tools(self, identifier: str, **kwargs):
        self.calls.append({"identifier": identifier})

        def make_tool(name: str):
            definition_fields = {"name": type("StringValue", (), {"string_value": name})()}
            tool_obj = type("Tool", (), {"definition": type("Definition", (), {"fields": definition_fields})()})()
            return type("ScopedTool", (), {"tool": tool_obj})()

        tools = [make_tool(name) for name in self.tool_names]
        return type("ToolsResponse", (), {"tools": tools})()


class FakeActions:
    def __init__(self, tool_names: list[str]):
        self.tools = FakeTools(tool_names)
        self.execute_calls: list[dict] = []

    def execute_tool(self, **kwargs):
        self.execute_calls.append(kwargs)
        return type("Execution", (), {"execution_id": "exec_fake_123", "data": {"ok": True}})()


def configure_real_mode(monkeypatch):
    monkeypatch.setenv("SCALEKIT_MODE", "real")
    monkeypatch.setenv("SCALEKIT_ENV_URL", "https://example.scalekit.dev")
    monkeypatch.setenv("SCALEKIT_CLIENT_ID", "client_123")
    monkeypatch.setenv("SCALEKIT_CLIENT_SECRET", "secret_123")
    monkeypatch.setenv("SCALEKIT_GMAIL_SEND_TOOL_NAME", "gmail_create_draft")
    monkeypatch.setenv("SHOPFLOOR_DEMO_TO_EMAIL", "demo-recipient@example.com")


def test_real_mode_denies_theo_when_gmail_tool_not_in_scoped_tools(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FakeActions(tool_names=["notion.pages.update"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["tech_theo"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.tools.calls == [{"identifier": "tech_theo"}]
    assert fake_actions.execute_calls == []
    assert result.ok is False
    assert result.outcome == "denied"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail_create_draft"
    assert result.decision_source == "scalekit_tool_scope"
    assert "does not have the Gmail customer-email tool" in result.detail


def test_real_mode_executes_sara_gmail_create_draft(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FakeActions(tool_names=["gmail_create_draft"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["sales_sara"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.tools.calls == [{"identifier": "sales_sara"}]
    assert len(fake_actions.execute_calls) == 1
    call = fake_actions.execute_calls[0]
    assert call["tool_name"] == "gmail_create_draft"
    assert call["identifier"] == "sales_sara"
    assert "to" in call["tool_input"]
    assert "subject" in call["tool_input"]
    assert "body" in call["tool_input"]
    assert result.ok is True
    assert result.outcome == "succeeded"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail_create_draft"
    assert result.decision_source == "scalekit_execute_tool"
    assert result.external_request_id == "exec_fake_123"
    assert "REAL Gmail draft via Scalekit as Sara" in result.detail


class FailingExecuteActions(FakeActions):
    def execute_tool(self, **kwargs):
        self.execute_calls.append(kwargs)
        raise RuntimeError("upstream gmail rejected request")


def test_real_mode_maps_execution_failure_to_failed_result(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FailingExecuteActions(tool_names=["gmail_create_draft"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["sales_sara"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.execute_calls
    assert result.ok is False
    assert result.outcome == "failed"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail_create_draft"
    assert result.decision_source == "scalekit_execute_tool"
    assert "RuntimeError" in result.detail
    assert "upstream gmail rejected request" in result.detail
