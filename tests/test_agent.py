from unittest.mock import MagicMock, patch

import pytest

from app.services import agent as agent_module
from app.services.agent import AgentStepResult, get_crm_schema, run_agent_step


def _make_tool_use_block(name: str, input: dict):
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = input
    return block


def _make_response(*blocks):
    response = MagicMock()
    response.content = list(blocks)
    return response


@pytest.fixture(autouse=True)
def reset_crm_cache():
    agent_module._crm_schema_cache = None
    yield
    agent_module._crm_schema_cache = None


def test_run_agent_step_returns_valid_result():
    tool_block = _make_tool_use_block("send_email", {"subject": "Your quote", "body": "Here is your quote."})
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = _make_response(tool_block)
        result = run_agent_step(
            {"job_id": "job_a", "vehicle": "Honda Civic", "symptom": "grinding brakes", "customer_email": "test@example.com"},
            "send_quote_email",
        )

    assert isinstance(result, AgentStepResult)
    assert result.tool_name == "send_email"
    assert result.tool_input["subject"] == "Your quote"


def test_run_agent_step_returns_fallback_on_exception():
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.side_effect = Exception("API down")
        result = run_agent_step(
            {"job_id": "job_a", "vehicle": "Honda Civic", "symptom": "grinding brakes", "customer_email": "test@example.com"},
            "send_quote_email",
        )

    assert isinstance(result, AgentStepResult)
    assert result.explanation == "LLM unavailable — used fallback content"
    assert "subject" in result.tool_input


def test_get_crm_schema_caches_on_second_call():
    from app.actors import ACTORS

    actor = ACTORS["manager_maya"]
    with patch("anthropic.Anthropic"):
        schema1 = get_crm_schema(actor)
        schema2 = get_crm_schema(actor)

    assert schema1 is schema2


def test_run_agent_step_fallback_when_no_tool_use_block():
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is a summary."
    with patch("anthropic.Anthropic") as mock_cls:
        mock_cls.return_value.messages.create.return_value = _make_response(text_block)
        result = run_agent_step(
            {"job_id": "job_a", "vehicle": "Honda Civic", "symptom": "noise", "customer_email": "x@x.com"},
            "draft_quote",
        )

    assert result.explanation == "LLM unavailable — used fallback content"
