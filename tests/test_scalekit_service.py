import pytest

from app.actors import ACTORS
from app.services.scalekit import send_customer_email_as_actor


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
