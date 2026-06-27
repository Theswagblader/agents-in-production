# ShopFloor FastAPI Spine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a server-rendered FastAPI dashboard that proves trusted identity, job authorization, audit logging, and stubbed integration boundaries for ShopFloor.

**Architecture:** One FastAPI monolith serves the dashboard, owns demo session identity, persists jobs and audit events in SQLite, and calls service adapters for Scalekit and Actian. The adapters default to deterministic stub mode and expose stable interfaces for real integrations.

**Tech Stack:** Python 3.11+, FastAPI, Jinja2, Uvicorn, SQLite via the standard library, pytest, FastAPI TestClient.

## Global Constraints

- FastAPI-only backend with a server-rendered dashboard.
- No React or separate frontend build.
- Identity is resolved only from `demo_actor_id` and backend actor config.
- Routes must not accept browser-supplied actor id, role, Scalekit identifier, connected account id, tenant, or provider credentials.
- Stub integration rows must be visibly marked as stubbed in audit details.
- Jordan wrong-job denial must happen before any external tool call.
- Real integrations will use Gmail for Sara and Notion or Slack as the CRM/job-log for Maya and Theo.

---

## File Structure

- `requirements.txt`: Runtime and test dependencies.
- `.env.example`: Local and Render environment variable reference.
- `render.yaml`: Render web service scaffold.
- `app/__init__.py`: Package marker.
- `app/actors.py`: Actor dataclass and hardcoded actor map.
- `app/auth.py`: Cookie-based trusted actor resolver.
- `app/db.py`: SQLite connection, schema, and seed data.
- `app/repositories.py`: Job and audit repository functions.
- `app/services/actian.py`: Quote comparable adapter with stub mode.
- `app/services/scalekit.py`: Tool execution adapter with stub mode.
- `app/main.py`: FastAPI routes and workflow orchestration.
- `app/templates/index.html`: Server-rendered dashboard.
- `app/static/styles.css`: Dashboard styles.
- `tests/conftest.py`: Isolated app test client.
- `tests/test_workflow.py`: Workflow, denial, audit, and health tests.
- `README.md`: Setup, run, and Scalekit integration notes.

---

### Task 1: Project Scaffold And Health Check

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `tests/conftest.py`
- Create: `tests/test_workflow.py`

**Interfaces:**
- Produces: `app.main.app: FastAPI`
- Produces: `GET /healthz -> {"ok": true}`

- [ ] **Step 1: Write the failing health test**

```python
def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py::test_healthz_returns_ok -v`

Expected: FAIL because `app.main` or `/healthz` does not exist.

- [ ] **Step 3: Write minimal implementation**

Create `requirements.txt`:

```text
fastapi==0.115.6
uvicorn[standard]==0.32.1
jinja2==3.1.4
python-multipart==0.0.19
pytest==8.3.4
httpx==0.28.1
```

Create `app/__init__.py` as an empty package marker.

Create `app/main.py`:

```python
from fastapi import FastAPI

app = FastAPI(title="ShopFloor")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}
```

Create `tests/conftest.py`:

```python
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow.py::test_healthz_returns_ok -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add requirements.txt app tests
git commit -m "Add FastAPI health check scaffold"
```

---

### Task 2: Trusted Actors And Session Login

**Files:**
- Create: `app/actors.py`
- Create: `app/auth.py`
- Modify: `app/main.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `Actor` dataclass with `actor_id`, `display_name`, `role`, `scalekit_identifier`, `allowed_connections`.
- Produces: `get_actor_from_cookie(actor_id: str | None) -> Actor | None`
- Produces: `POST /demo/login` sets `demo_actor_id`.
- Produces: `POST /demo/logout` clears `demo_actor_id`.
- Produces: `GET /me` returns the backend-resolved actor or `{"actor": None}`.

- [ ] **Step 1: Write failing login and resolver tests**

```python
def test_login_sets_trusted_actor_cookie(client):
    response = client.post("/demo/login", data={"actor_id": "sales_sara"}, follow_redirects=False)

    assert response.status_code == 303
    assert response.cookies.get("demo_actor_id") == "sales_sara"


def test_me_resolves_actor_from_cookie(client):
    client.cookies.set("demo_actor_id", "tech_theo")

    response = client.get("/me")

    assert response.status_code == 200
    assert response.json()["actor"]["actor_id"] == "tech_theo"
    assert response.json()["actor"]["display_name"] == "Theo Ruiz"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workflow.py::test_login_sets_trusted_actor_cookie tests/test_workflow.py::test_me_resolves_actor_from_cookie -v`

Expected: FAIL because login and actor resolver routes do not exist.

- [ ] **Step 3: Implement actors, auth, and routes**

`app/actors.py`:

```python
from dataclasses import asdict, dataclass
from typing import Literal

Role = Literal["sales", "manager", "technician"]


@dataclass(frozen=True)
class Actor:
    actor_id: str
    display_name: str
    role: Role
    scalekit_identifier: str
    allowed_connections: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["allowed_connections"] = list(self.allowed_connections)
        return data


ACTORS: dict[str, Actor] = {
    "sales_sara": Actor("sales_sara", "Sara Patel", "sales", "sales_sara", ("gmail",)),
    "manager_maya": Actor("manager_maya", "Maya Chen", "manager", "manager_maya", ("notion", "slack")),
    "tech_theo": Actor("tech_theo", "Theo Ruiz", "technician", "tech_theo", ("notion", "slack")),
    "tech_jordan": Actor("tech_jordan", "Jordan Lee", "technician", "tech_jordan", ("notion", "slack")),
}
```

`app/auth.py`:

```python
from app.actors import ACTORS, Actor


def get_actor_from_cookie(actor_id: str | None) -> Actor | None:
    if not actor_id:
        return None
    return ACTORS.get(actor_id)
```

Update `app/main.py`:

```python
from fastapi import Cookie, FastAPI, Form
from fastapi.responses import RedirectResponse

from app.auth import get_actor_from_cookie

app = FastAPI(title="ShopFloor")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.post("/demo/login")
def login(actor_id: str = Form(...)) -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    if get_actor_from_cookie(actor_id) is not None:
        response.set_cookie("demo_actor_id", actor_id, httponly=True, samesite="lax")
    return response


@app.post("/demo/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse("/", status_code=303)
    response.delete_cookie("demo_actor_id")
    return response


@app.get("/me")
def me(demo_actor_id: str | None = Cookie(default=None)) -> dict[str, object | None]:
    actor = get_actor_from_cookie(demo_actor_id)
    return {"actor": actor.to_dict() if actor else None}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workflow.py::test_login_sets_trusted_actor_cookie tests/test_workflow.py::test_me_resolves_actor_from_cookie -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add trusted demo actor sessions"
```

---

### Task 3: SQLite Jobs And Audit Repositories

**Files:**
- Create: `app/db.py`
- Create: `app/repositories.py`
- Modify: `app/main.py`
- Modify: `tests/conftest.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `init_db(database_url: str | None = None, reset: bool = False) -> None`
- Produces: `get_job(job_id: str) -> dict[str, object] | None`
- Produces: `update_job(job_id: str, **fields: object) -> None`
- Produces: `list_jobs() -> list[dict[str, object]]`
- Produces: `record_audit(...) -> None`
- Produces: `list_audit_events() -> list[dict[str, object]]`
- Produces: `GET /jobs`
- Produces: `GET /audit`

- [ ] **Step 1: Write failing repository route tests**

```python
def test_seeded_jobs_are_available(client):
    response = client.get("/jobs")

    assert response.status_code == 200
    jobs = response.json()["jobs"]
    assert [job["job_id"] for job in jobs] == ["job_a", "job_b"]
    assert jobs[0]["assigned_tech_id"] == "tech_theo"


def test_audit_starts_empty(client):
    response = client.get("/audit")

    assert response.status_code == 200
    assert response.json() == {"events": []}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workflow.py::test_seeded_jobs_are_available tests/test_workflow.py::test_audit_starts_empty -v`

Expected: FAIL because repositories and routes do not exist.

- [ ] **Step 3: Implement SQLite schema, seed, and routes**

Use SQLite from the standard library. Store `DATABASE_URL` as a filesystem path; default to `.data/shopfloor.db`. The test fixture sets a temporary database path and calls `init_db(reset=True)` before each test.

Tables:

```sql
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY,
  customer_name TEXT NOT NULL,
  customer_email TEXT NOT NULL,
  vehicle TEXT NOT NULL,
  symptom TEXT NOT NULL,
  quote_amount INTEGER,
  quote_text TEXT,
  quote_status TEXT NOT NULL,
  job_status TEXT NOT NULL,
  assigned_tech_id TEXT,
  manager_id TEXT,
  sales_id TEXT,
  completion_summary TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE audit_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  created_at TEXT NOT NULL,
  actor_id TEXT NOT NULL,
  actor_name TEXT NOT NULL,
  actor_role TEXT NOT NULL,
  action TEXT NOT NULL,
  target_type TEXT NOT NULL,
  target_id TEXT,
  provider TEXT,
  tool_name TEXT,
  decision_source TEXT NOT NULL,
  outcome TEXT NOT NULL,
  detail TEXT,
  external_request_id TEXT
);
```

Seed Job A and Job B exactly once after schema creation.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workflow.py::test_seeded_jobs_are_available tests/test_workflow.py::test_audit_starts_empty -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add job and audit persistence"
```

---

### Task 4: Stub Actian Quote Draft

**Files:**
- Create: `app/services/actian.py`
- Modify: `app/main.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `ComparableJob` dataclass.
- Produces: `draft_quote(vehicle: str, symptom: str, concern: str) -> QuoteDraft`
- Produces: `POST /quote/draft`

- [ ] **Step 1: Write failing quote draft test**

```python
def test_sara_can_draft_quote_with_stubbed_comparables(client):
    client.cookies.set("demo_actor_id", "sales_sara")

    response = client.post("/quote/draft", data={"job_id": "job_a"}, follow_redirects=False)

    assert response.status_code == 303
    jobs = client.get("/jobs").json()["jobs"]
    job_a = next(job for job in jobs if job["job_id"] == "job_a")
    assert job_a["quote_amount"] == 460
    assert job_a["quote_status"] == "drafted"
    events = client.get("/audit").json()["events"]
    assert events[-1]["decision_source"] == "actian_retrieval"
    assert events[-1]["outcome"] == "succeeded"
    assert "stubbed comparables" in events[-1]["detail"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py::test_sara_can_draft_quote_with_stubbed_comparables -v`

Expected: FAIL because `/quote/draft` does not exist.

- [ ] **Step 3: Implement stub quote service and route**

Stub comparables final prices are `480`, `330`, and `570`. The default risk multiplier is `1.0`, so `round(mean) == 460`.

The route loads the job, calls `draft_quote(job["vehicle"], job["symptom"], job["symptom"])`, updates `quote_amount`, `quote_text`, and `quote_status`, records an `actian_retrieval` audit event, then redirects to `/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow.py::test_sara_can_draft_quote_with_stubbed_comparables -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add stubbed Actian quote drafting"
```

---

### Task 5: Stub Scalekit Workflow Actions

**Files:**
- Create: `app/services/scalekit.py`
- Modify: `app/main.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `ToolResult` dataclass with `ok`, `outcome`, `provider`, `tool_name`, `decision_source`, `detail`, `external_request_id`.
- Produces: `send_customer_email_as_actor(actor, job) -> ToolResult`
- Produces: `write_crm_record_as_actor(actor, job, action) -> ToolResult`
- Produces: `POST /quote/send`
- Produces: `POST /jobs/{job_id}/approve`
- Produces: `POST /jobs/{job_id}/complete`

- [ ] **Step 1: Write failing happy-path tests**

```python
def test_sara_can_send_quote_email_in_stub_mode(client):
    client.cookies.set("demo_actor_id", "sales_sara")
    client.post("/quote/draft", data={"job_id": "job_a"})

    response = client.post("/quote/send", data={"actor_id": "tech_jordan", "role": "technician"}, follow_redirects=False)

    assert response.status_code == 303
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "sales_sara"
    assert events[-1]["provider"] == "gmail"
    assert events[-1]["tool_name"] == "gmail.send_email"
    assert events[-1]["outcome"] == "succeeded"
    assert "STUBBED" in events[-1]["detail"]


def test_maya_can_approve_job_in_stub_mode(client):
    client.cookies.set("demo_actor_id", "manager_maya")

    response = client.post("/jobs/job_a/approve", follow_redirects=False)

    assert response.status_code == 303
    job_a = next(job for job in client.get("/jobs").json()["jobs"] if job["job_id"] == "job_a")
    assert job_a["job_status"] == "approved"
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "manager_maya"
    assert events[-1]["provider"] in {"notion", "slack"}
    assert events[-1]["outcome"] == "succeeded"


def test_theo_can_complete_assigned_job_in_stub_mode(client):
    client.cookies.set("demo_actor_id", "tech_theo")

    response = client.post("/jobs/job_a/complete", data={"summary": "Replaced front brake pads."}, follow_redirects=False)

    assert response.status_code == 303
    job_a = next(job for job in client.get("/jobs").json()["jobs"] if job["job_id"] == "job_a")
    assert job_a["job_status"] == "completed"
    assert job_a["completion_summary"] == "Replaced front brake pads."
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_theo"
    assert events[-1]["outcome"] == "succeeded"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workflow.py::test_sara_can_send_quote_email_in_stub_mode tests/test_workflow.py::test_maya_can_approve_job_in_stub_mode tests/test_workflow.py::test_theo_can_complete_assigned_job_in_stub_mode -v`

Expected: FAIL because Scalekit routes do not exist.

- [ ] **Step 3: Implement stub Scalekit service and routes**

Stub service behavior:

- Sara Gmail succeeds with provider `gmail`, tool `gmail.send_email`, source `scalekit_execute_tool`.
- Maya CRM succeeds with provider `notion`, tool `notion.pages.create`, source `scalekit_execute_tool`.
- Theo completion succeeds with provider `notion`, tool `notion.pages.update`, source `scalekit_execute_tool`.
- All stub success details start with `STUBBED`.

Route behavior:

- `/quote/send` allows only Sara; browser-supplied actor fields are ignored because only the cookie actor is used.
- `/jobs/{job_id}/approve` allows only Maya.
- `/jobs/{job_id}/complete` allows only assigned technician.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workflow.py::test_sara_can_send_quote_email_in_stub_mode tests/test_workflow.py::test_maya_can_approve_job_in_stub_mode tests/test_workflow.py::test_theo_can_complete_assigned_job_in_stub_mode -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add stubbed Scalekit workflow actions"
```

---

### Task 6: Denial Paths

**Files:**
- Modify: `app/main.py`
- Modify: `app/services/scalekit.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `POST /attack/tech-email-customer`
- Produces: `POST /attack/complete-wrong-job`

- [ ] **Step 1: Write failing denial tests**

```python
def test_theo_customer_email_attack_records_scalekit_scope_denial(client):
    client.cookies.set("demo_actor_id", "tech_theo")

    response = client.post("/attack/tech-email-customer", follow_redirects=False)

    assert response.status_code == 303
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_theo"
    assert events[-1]["provider"] == "gmail"
    assert events[-1]["tool_name"] == "gmail.send_email"
    assert events[-1]["decision_source"] == "scalekit_tool_scope"
    assert events[-1]["outcome"] == "denied"


def test_jordan_wrong_job_attack_records_backend_denial_without_tool_call(client):
    client.cookies.set("demo_actor_id", "tech_jordan")

    response = client.post("/attack/complete-wrong-job", follow_redirects=False)

    assert response.status_code == 303
    job_a = next(job for job in client.get("/jobs").json()["jobs"] if job["job_id"] == "job_a")
    assert job_a["job_status"] == "quoted"
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_jordan"
    assert events[-1]["provider"] is None
    assert events[-1]["tool_name"] is None
    assert events[-1]["decision_source"] == "backend_trusted_job_state"
    assert events[-1]["outcome"] == "denied"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_workflow.py::test_theo_customer_email_attack_records_scalekit_scope_denial tests/test_workflow.py::test_jordan_wrong_job_attack_records_backend_denial_without_tool_call -v`

Expected: FAIL because attack routes do not exist.

- [ ] **Step 3: Implement denial routes**

Theo email attack calls the Scalekit adapter as Theo, receives a stubbed Gmail denial, and records the denial with source `scalekit_tool_scope`.

Jordan wrong-job attack loads Job A, compares `job["assigned_tech_id"]` to `actor.actor_id`, records `backend_trusted_job_state` denial, and redirects without calling Scalekit.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_workflow.py::test_theo_customer_email_attack_records_scalekit_scope_denial tests/test_workflow.py::test_jordan_wrong_job_attack_records_backend_denial_without_tool_call -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add delegated auth denial paths"
```

---

### Task 7: Server-Rendered Dashboard

**Files:**
- Create: `app/templates/index.html`
- Create: `app/static/styles.css`
- Modify: `app/main.py`
- Modify: `tests/test_workflow.py`

**Interfaces:**
- Produces: `GET /` HTML dashboard.

- [ ] **Step 1: Write failing dashboard test**

```python
def test_dashboard_renders_identity_workflow_and_audit(client):
    response = client.get("/")

    assert response.status_code == 200
    assert "Sara Patel" in response.text
    assert "Job A" in response.text
    assert "Audit" in response.text
    assert "Theo tries customer email" in response.text
    assert "Jordan tries Theo's job" in response.text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_workflow.py::test_dashboard_renders_identity_workflow_and_audit -v`

Expected: FAIL because `/` does not render the dashboard.

- [ ] **Step 3: Implement template, CSS, and route**

Mount `/static`, configure Jinja2 templates, and render:

- Login tiles for all four actors.
- Current actor and allowed connections.
- Job A lifecycle panel.
- Quote draft/send, approve, complete forms.
- Attack forms.
- Audit table.
- Stub marker language in audit details.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_workflow.py::test_dashboard_renders_identity_workflow_and_audit -v`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app tests
git commit -m "Add server rendered demo dashboard"
```

---

### Task 8: Render And Documentation

**Files:**
- Create: `.env.example`
- Create: `render.yaml`
- Modify: `README.md`

**Interfaces:**
- Produces: documented local setup and Scalekit setup checklist.

- [ ] **Step 1: Write deployment files**

`.env.example`:

```text
DATABASE_URL=.data/shopfloor.db
SCALEKIT_MODE=stub
SCALEKIT_CLIENT_ID=
SCALEKIT_CLIENT_SECRET=
SCALEKIT_ENV_URL=
SCALEKIT_GMAIL_CONNECTION_NAME=gmail
SCALEKIT_NOTION_CONNECTION_NAME=notion
SCALEKIT_SLACK_CONNECTION_NAME=slack
ACTIAN_MODE=stub
ACTIAN_HOST=
ACTIAN_PORT=
ACTIAN_USERNAME=
ACTIAN_PASSWORD=
```

`render.yaml`:

```yaml
services:
  - type: web
    name: shopfloor
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: uvicorn app.main:app --host 0.0.0.0 --port $PORT
    healthCheckPath: /healthz
```

- [ ] **Step 2: Update README**

Include commands:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
pytest
```

Include Scalekit setup:

- Create Gmail, Notion, and optionally Slack connections in Scalekit.
- Connect Sara to Gmail.
- Connect Maya to Notion or Slack.
- Connect Theo to Notion or Slack.
- Do not connect Theo to Gmail, or configure scoped tools so Gmail customer email is unavailable to Theo.
- Record the exact denial behavior for Theo Gmail.
- Set Render env vars and change `SCALEKIT_MODE=real` only after the real adapter is implemented.

- [ ] **Step 3: Run full verification**

Run: `pytest -v`

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add .env.example render.yaml README.md
git commit -m "Document ShopFloor setup and deployment"
```

