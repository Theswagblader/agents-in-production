# Scalekit Real Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a real Scalekit mode that sends Gmail as Sara and records a real Scalekit/tool-scope denial for Theo while preserving deterministic stub mode.

**Architecture:** Keep route handlers stable and make `app/services/scalekit.py` mode-aware. Add configuration parsing, dependency injection for the Scalekit client, scoped tool discovery before Gmail execution, and explicit `ToolResult` mapping for config errors, denials, successes, and failures.

**Tech Stack:** Python 3.11+, FastAPI, pytest, Scalekit Python SDK (`scalekit-sdk-python`), SQLite audit through existing repository functions.

## Global Constraints

- Use TDD for every production-code change: write failing test, verify red, implement minimal code, verify green, then refactor.
- `SCALEKIT_MODE=stub` remains the default.
- Real mode must not crash the dashboard when config, SDK import, credentials, connection, or tool execution fails.
- Browser requests must not supply actor id, role, Scalekit identifier, connected account id, tenant, provider credentials, or tokens to action routes.
- Scalekit identity comes only from `actor.scalekit_identifier`.
- `SCALEKIT_GMAIL_SEND_TOOL_NAME` must be copied from scoped tool discovery.
- Theo's email denial must be recorded as `decision_source="scalekit_tool_scope"` when the send tool is unavailable or the delegated Gmail capability is absent.
- Existing stub tests must remain green.

---

## File Structure

- `requirements.txt`: add `scalekit-sdk-python`.
- `.env.example`: add `SCALEKIT_GMAIL_SEND_TOOL_NAME`, `SHOPFLOOR_FROM_EMAIL`, `SHOPFLOOR_DEMO_TO_EMAIL`.
- `app/services/scalekit.py`: add real-mode config, fake-client injection seam, scoped tool discovery, and execution mapping.
- `tests/test_scalekit_service.py`: focused service tests for real mode and preserved stub behavior.
- `tests/test_workflow.py`: one route-level regression that browser-supplied identity is ignored in real mode too.
- `docs/scalekit-setup.md`: exact dashboard and local verification instructions.

---

### Task 1: Real-Mode Config Failure

**Files:**
- Modify: `app/services/scalekit.py`
- Create: `tests/test_scalekit_service.py`

**Interfaces:**
- Consumes: `send_customer_email_as_actor(actor: Actor, job: dict[str, Any]) -> ToolResult`
- Produces: `ScalekitConfig.from_env() -> ScalekitConfig`
- Produces: `ToolResult(decision_source="scalekit_config", outcome="failed")` when real-mode env is incomplete.

- [ ] **Step 1: Write the failing test**

Add `tests/test_scalekit_service.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_reports_missing_scalekit_config -v
```

Expected: FAIL because `SCALEKIT_MODE=real` is ignored and the existing stub returns a success for Sara.

- [ ] **Step 3: Write minimal implementation**

In `app/services/scalekit.py`, add imports and config:

```python
import os
from dataclasses import dataclass
from typing import Any, Protocol
```

Keep `ToolResult`, then add:

```python
@dataclass(frozen=True)
class ScalekitConfig:
    mode: str
    env_url: str | None
    client_id: str | None
    client_secret: str | None
    gmail_connection_name: str
    gmail_send_tool_name: str | None
    demo_to_email: str | None
    from_email: str | None

    @classmethod
    def from_env(cls) -> "ScalekitConfig":
        return cls(
            mode=os.environ.get("SCALEKIT_MODE", "stub").lower(),
            env_url=os.environ.get("SCALEKIT_ENV_URL"),
            client_id=os.environ.get("SCALEKIT_CLIENT_ID"),
            client_secret=os.environ.get("SCALEKIT_CLIENT_SECRET"),
            gmail_connection_name=os.environ.get("SCALEKIT_GMAIL_CONNECTION_NAME", "gmail"),
            gmail_send_tool_name=os.environ.get("SCALEKIT_GMAIL_SEND_TOOL_NAME"),
            demo_to_email=os.environ.get("SHOPFLOOR_DEMO_TO_EMAIL"),
            from_email=os.environ.get("SHOPFLOOR_FROM_EMAIL"),
        )

    def missing_real_mode_vars(self) -> list[str]:
        required = {
            "SCALEKIT_ENV_URL": self.env_url,
            "SCALEKIT_CLIENT_ID": self.client_id,
            "SCALEKIT_CLIENT_SECRET": self.client_secret,
            "SCALEKIT_GMAIL_SEND_TOOL_NAME": self.gmail_send_tool_name,
            "SHOPFLOOR_DEMO_TO_EMAIL": self.demo_to_email,
        }
        return [name for name, value in required.items() if not value]
```

At the top of `send_customer_email_as_actor`, before current stub logic:

```python
    config = ScalekitConfig.from_env()
    if config.mode == "real":
        missing = config.missing_real_mode_vars()
        if missing:
            return ToolResult(
                ok=False,
                outcome="failed",
                provider="gmail",
                tool_name=None,
                decision_source="scalekit_config",
                detail=f"Missing required Scalekit env vars for real mode: {', '.join(missing)}.",
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_reports_missing_scalekit_config -v
```

Expected: PASS.

- [ ] **Step 5: Run current suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/scalekit.py tests/test_scalekit_service.py
git commit -m "Add Scalekit real-mode config validation"
```

---

### Task 2: Fake Client Injection And Theo Scoped-Tool Denial

**Files:**
- Modify: `app/services/scalekit.py`
- Modify: `tests/test_scalekit_service.py`

**Interfaces:**
- Produces: `set_scalekit_client_factory(factory: Callable[[], ScalekitActionsClient] | None) -> None`
- Produces: `actions.tools.list_scoped_tools(identifier: str, page_size: int)` usage.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_scalekit_service.py`:

```python
from app.services import scalekit as scalekit_service


class FakeTools:
    def __init__(self, tool_names: list[str]):
        self.tool_names = tool_names
        self.calls: list[dict[str, object]] = []

    def list_scoped_tools(self, *, identifier: str, page_size: int):
        self.calls.append({"identifier": identifier, "page_size": page_size})
        tools = [type("Tool", (), {"name": name})() for name in self.tool_names]
        return type("ToolsResponse", (), {"tools": tools})()


class FakeActions:
    def __init__(self, tool_names: list[str]):
        self.tools = FakeTools(tool_names)
        self.execute_calls: list[dict[str, object]] = []

    def execute_tool(self, **kwargs):
        self.execute_calls.append(kwargs)
        return type("Execution", (), {"execution_id": "exec_fake_123", "data": {"ok": True}})()


def configure_real_mode(monkeypatch):
    monkeypatch.setenv("SCALEKIT_MODE", "real")
    monkeypatch.setenv("SCALEKIT_ENV_URL", "https://example.scalekit.dev")
    monkeypatch.setenv("SCALEKIT_CLIENT_ID", "client_123")
    monkeypatch.setenv("SCALEKIT_CLIENT_SECRET", "secret_123")
    monkeypatch.setenv("SCALEKIT_GMAIL_SEND_TOOL_NAME", "gmail.send_email")
    monkeypatch.setenv("SHOPFLOOR_DEMO_TO_EMAIL", "demo-recipient@example.com")


def test_real_mode_denies_theo_when_gmail_send_tool_is_not_scoped(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FakeActions(tool_names=["notion.pages.update"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["tech_theo"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.tools.calls == [{"identifier": "tech_theo", "page_size": 100}]
    assert fake_actions.execute_calls == []
    assert result.ok is False
    assert result.outcome == "denied"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail.send_email"
    assert result.decision_source == "scalekit_tool_scope"
    assert "does not have the Gmail customer-email tool" in result.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_denies_theo_when_gmail_send_tool_is_not_scoped -v
```

Expected: FAIL because there is no `set_scalekit_client_factory` and no scoped-tool check.

- [ ] **Step 3: Write minimal implementation**

In `app/services/scalekit.py`, add protocol and factory near config:

```python
from collections.abc import Callable


class ScalekitActionsClient(Protocol):
    tools: Any

    def execute_tool(self, *, tool_name: str, tool_input: dict[str, Any], identifier: str) -> Any:
        ...


_scalekit_client_factory: Callable[[], ScalekitActionsClient] | None = None


def set_scalekit_client_factory(factory: Callable[[], ScalekitActionsClient] | None) -> None:
    global _scalekit_client_factory
    _scalekit_client_factory = factory


def _get_scalekit_actions_client(config: ScalekitConfig) -> ScalekitActionsClient:
    if _scalekit_client_factory is not None:
        return _scalekit_client_factory()
    try:
        from scalekit import ScalekitClient
    except ImportError as exc:
        raise RuntimeError("scalekit-sdk-python is not installed.") from exc

    client = ScalekitClient(
        env_url=config.env_url,
        client_id=config.client_id,
        client_secret=config.client_secret,
    )
    return client.actions
```

Add helper:

```python
def _tool_names(tools_response: Any) -> set[str]:
    return {str(tool.name) for tool in getattr(tools_response, "tools", [])}
```

In `send_customer_email_as_actor`, after missing config check:

```python
        try:
            actions = _get_scalekit_actions_client(config)
            tools_response = actions.tools.list_scoped_tools(
                identifier=actor.scalekit_identifier,
                page_size=100,
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="gmail",
                tool_name=config.gmail_send_tool_name,
                decision_source="scalekit_tool_scope",
                detail=(
                    "REAL Scalekit denial: "
                    f"{actor.display_name} has not delegated this customer-email capability "
                    f"({exc.__class__.__name__}: {exc})."
                ),
            )

        if config.gmail_send_tool_name not in _tool_names(tools_response):
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="gmail",
                tool_name=config.gmail_send_tool_name,
                decision_source="scalekit_tool_scope",
                detail=(
                    "REAL Scalekit denial: "
                    f"{actor.display_name} does not have the Gmail customer-email tool "
                    "in scoped tools."
                ),
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_denies_theo_when_gmail_send_tool_is_not_scoped -v
```

Expected: PASS.

- [ ] **Step 5: Run current suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/scalekit.py tests/test_scalekit_service.py
git commit -m "Add Scalekit scoped-tool denial"
```

---

### Task 3: Sara Real Gmail Execute Path

**Files:**
- Modify: `app/services/scalekit.py`
- Modify: `tests/test_scalekit_service.py`

**Interfaces:**
- Consumes: `ScalekitConfig.gmail_send_tool_name`
- Produces: `actions.execute_tool(tool_name=..., tool_input=..., identifier=...)`
- Produces: `ToolResult(decision_source="scalekit_execute_tool", outcome="succeeded")`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_real_mode_executes_sara_gmail_send_with_backend_identifier(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FakeActions(tool_names=["gmail.send_email"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["sales_sara"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.tools.calls == [{"identifier": "sales_sara", "page_size": 100}]
    assert fake_actions.execute_calls == [
        {
            "tool_name": "gmail.send_email",
            "tool_input": {
                "to": "demo-recipient@example.com",
                "subject": "Repair quote for 2018 Honda Civic",
                "body": "Estimated brake repair: $460.",
            },
            "identifier": "sales_sara",
        }
    ]
    assert result.ok is True
    assert result.outcome == "succeeded"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail.send_email"
    assert result.decision_source == "scalekit_execute_tool"
    assert result.external_request_id == "exec_fake_123"
    assert "REAL Gmail send via Scalekit as Sara Patel" in result.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_executes_sara_gmail_send_with_backend_identifier -v
```

Expected: FAIL because real mode currently denies or returns before execution.

- [ ] **Step 3: Write minimal implementation**

Add helper:

```python
def _gmail_tool_input(config: ScalekitConfig, job: dict[str, Any]) -> dict[str, str]:
    body = str(job.get("quote_text") or f"Repair quote for {job['vehicle']}: diagnosis pending.")
    return {
        "to": str(config.demo_to_email),
        "subject": f"Repair quote for {job['vehicle']}",
        "body": body,
    }
```

After the scoped tool presence check:

```python
        try:
            execution = actions.execute_tool(
                tool_name=str(config.gmail_send_tool_name),
                tool_input=_gmail_tool_input(config, job),
                identifier=actor.scalekit_identifier,
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="failed",
                provider="gmail",
                tool_name=config.gmail_send_tool_name,
                decision_source="scalekit_execute_tool",
                detail=f"REAL Scalekit Gmail execution failed ({exc.__class__.__name__}: {exc}).",
            )

        return ToolResult(
            ok=True,
            outcome="succeeded",
            provider="gmail",
            tool_name=config.gmail_send_tool_name,
            decision_source="scalekit_execute_tool",
            detail=(
                "REAL Gmail send via Scalekit as "
                f"{actor.display_name} to {config.demo_to_email}."
            ),
            external_request_id=getattr(execution, "execution_id", None),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_executes_sara_gmail_send_with_backend_identifier -v
```

Expected: PASS.

- [ ] **Step 5: Run current suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/scalekit.py tests/test_scalekit_service.py
git commit -m "Execute real Scalekit Gmail send"
```

---

### Task 4: Real Execution Failure Mapping

**Files:**
- Modify: `tests/test_scalekit_service.py`
- Modify: `app/services/scalekit.py`

**Interfaces:**
- Consumes: `actions.execute_tool(...)`
- Produces: failure `ToolResult` with sanitized exception class and message.

- [ ] **Step 1: Write the failing test**

Append:

```python
class FailingExecuteActions(FakeActions):
    def execute_tool(self, **kwargs):
        self.execute_calls.append(kwargs)
        raise RuntimeError("upstream gmail send rejected request")


def test_real_mode_maps_scalekit_execution_exception_to_failed_result(monkeypatch, quoted_job):
    configure_real_mode(monkeypatch)
    fake_actions = FailingExecuteActions(tool_names=["gmail.send_email"])
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)

    try:
        result = send_customer_email_as_actor(ACTORS["sales_sara"], quoted_job)
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert fake_actions.execute_calls
    assert result.ok is False
    assert result.outcome == "failed"
    assert result.provider == "gmail"
    assert result.tool_name == "gmail.send_email"
    assert result.decision_source == "scalekit_execute_tool"
    assert "RuntimeError" in result.detail
    assert "upstream gmail send rejected request" in result.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_maps_scalekit_execution_exception_to_failed_result -v
```

Expected: If Task 3 already added the exception mapping, this test may pass. If it passes immediately, keep it as a regression and proceed to Step 5.

- [ ] **Step 3: Write minimal implementation**

If needed, add the `except Exception as exc` block shown in Task 3 around `actions.execute_tool`.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/pytest tests/test_scalekit_service.py::test_real_mode_maps_scalekit_execution_exception_to_failed_result -v
```

Expected: PASS.

- [ ] **Step 5: Run current suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/scalekit.py tests/test_scalekit_service.py
git commit -m "Map Scalekit Gmail execution failures"
```

---

### Task 5: Route-Level Audit In Real Mode

**Files:**
- Modify: `tests/test_workflow.py`
- Modify: `app/services/scalekit.py`

**Interfaces:**
- Consumes: `set_scalekit_client_factory(...)`
- Produces: audit row from `/quote/send` using cookie actor, not submitted form identity.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_workflow.py`:

```python
from app.services import scalekit as scalekit_service


class WorkflowFakeTools:
    def list_scoped_tools(self, *, identifier: str, page_size: int):
        tools = [type("Tool", (), {"name": "gmail.send_email"})()]
        return type("ToolsResponse", (), {"tools": tools})()


class WorkflowFakeActions:
    def __init__(self):
        self.tools = WorkflowFakeTools()
        self.execute_calls = []

    def execute_tool(self, **kwargs):
        self.execute_calls.append(kwargs)
        return type("Execution", (), {"execution_id": "exec_route_123", "data": {}})()


def test_quote_send_real_mode_audits_cookie_actor_not_form_identity(client, monkeypatch):
    monkeypatch.setenv("SCALEKIT_MODE", "real")
    monkeypatch.setenv("SCALEKIT_ENV_URL", "https://example.scalekit.dev")
    monkeypatch.setenv("SCALEKIT_CLIENT_ID", "client_123")
    monkeypatch.setenv("SCALEKIT_CLIENT_SECRET", "secret_123")
    monkeypatch.setenv("SCALEKIT_GMAIL_SEND_TOOL_NAME", "gmail.send_email")
    monkeypatch.setenv("SHOPFLOOR_DEMO_TO_EMAIL", "demo-recipient@example.com")
    fake_actions = WorkflowFakeActions()
    scalekit_service.set_scalekit_client_factory(lambda: fake_actions)
    client.cookies.set("demo_actor_id", "sales_sara")
    client.post("/quote/draft", data={"job_id": "job_a"})

    try:
        response = client.post(
            "/quote/send",
            data={
                "actor_id": "tech_jordan",
                "role": "technician",
                "scalekit_identifier": "tech_jordan",
                "connected_account_id": "ca_attacker",
            },
            follow_redirects=False,
        )
    finally:
        scalekit_service.set_scalekit_client_factory(None)

    assert response.status_code == 303
    assert fake_actions.execute_calls[0]["identifier"] == "sales_sara"
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "sales_sara"
    assert events[-1]["decision_source"] == "scalekit_execute_tool"
    assert events[-1]["external_request_id"] == "exec_route_123"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
.venv/bin/pytest tests/test_workflow.py::test_quote_send_real_mode_audits_cookie_actor_not_form_identity -v
```

Expected: PASS if Tasks 2 and 3 already completed correctly. If it fails, the failure should identify the missing service injection or execution path.

- [ ] **Step 3: Write minimal implementation**

Only change production code if the test fails. The expected implementation is already created in Tasks 2 and 3.

- [ ] **Step 4: Run test to verify it passes**

Run:

```bash
.venv/bin/pytest tests/test_workflow.py::test_quote_send_real_mode_audits_cookie_actor_not_form_identity -v
```

Expected: PASS.

- [ ] **Step 5: Run current suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/services/scalekit.py tests/test_workflow.py
git commit -m "Verify real Scalekit audit attribution"
```

---

### Task 6: Dependency, Env, And Scalekit Setup Docs

**Files:**
- Modify: `requirements.txt`
- Modify: `.env.example`
- Create: `docs/scalekit-setup.md`

**Interfaces:**
- Produces: installable real-mode dependency.
- Produces: exact human runbook for Scalekit dashboard and local verification.

- [ ] **Step 1: Write the failing dependency check**

Run:

```bash
.venv/bin/python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("scalekit") else 1)
PY
```

Expected: FAIL with exit code `1` because `scalekit-sdk-python` is not in `requirements.txt`.

- [ ] **Step 2: Add dependency and env keys**

Add to `requirements.txt`:

```text
scalekit-sdk-python
```

Add to `.env.example`:

```text
SCALEKIT_GMAIL_SEND_TOOL_NAME=
SHOPFLOOR_FROM_EMAIL=
SHOPFLOOR_DEMO_TO_EMAIL=
```

- [ ] **Step 3: Add setup runbook**

Create `docs/scalekit-setup.md` using the contents from the companion runbook created with this plan.

- [ ] **Step 4: Install and verify dependency**

Run:

```bash
.venv/bin/pip install -r requirements.txt
.venv/bin/python - <<'PY'
import importlib.util
raise SystemExit(0 if importlib.util.find_spec("scalekit") else 1)
PY
```

Expected: PASS with exit code `0`.

- [ ] **Step 5: Run full suite**

Run:

```bash
.venv/bin/pytest -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add requirements.txt .env.example docs/scalekit-setup.md
git commit -m "Document Scalekit real-mode setup"
```

---

## Self-Review

- Spec coverage: Tasks cover config validation, SDK seam, scoped tool denial, Sara execution, execution failure mapping, route attribution, dependency, env, and human setup docs.
- Placeholder scan: No task uses TBD, TODO, or unspecified error handling.
- Type consistency: All tasks use `ToolResult`, `ScalekitConfig`, `set_scalekit_client_factory`, and `send_customer_email_as_actor` consistently.
- Scope check: Notion, Slack, Actian, OAuth callback routes, and LLM copy are intentionally excluded.

## Execution Choice

Plan complete and saved to `docs/superpowers/plans/2026-06-27-scalekit-real-mode.md`.

Two execution options:

1. Subagent-Driven: dispatch a fresh worker per task and review between tasks.
2. Inline Execution: execute tasks in this session with TDD checkpoints.

