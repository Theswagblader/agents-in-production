def test_healthz_returns_ok(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"ok": True}


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


def test_sara_can_draft_quote_with_stubbed_comparables(client):
    client.cookies.set("demo_actor_id", "sales_sara")

    response = client.post("/quote/draft", data={"job_id": "job_a"}, follow_redirects=False)

    assert response.status_code == 303
    jobs = client.get("/jobs").json()["jobs"]
    job_a = next(job for job in jobs if job["job_id"] == "job_a")
    assert job_a["quote_amount"] == 529  # mean(480, 330, 570) * 1.15 risk multiplier (grinding)
    assert job_a["quote_status"] == "drafted"
    events = client.get("/audit").json()["events"]
    assert events[-1]["decision_source"] == "actian_retrieval"
    assert events[-1]["outcome"] == "succeeded"
    assert "Stub mode" in events[-1]["detail"]


def test_sara_can_send_quote_email_in_stub_mode(client):
    client.cookies.set("demo_actor_id", "sales_sara")
    client.post("/quote/draft", data={"job_id": "job_a"})

    response = client.post(
        "/quote/send",
        data={"actor_id": "tech_jordan", "role": "technician"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "sales_sara"
    assert events[-1]["provider"] == "gmail"
    assert events[-1]["tool_name"] == "gmail.send_email"
    assert events[-1]["outcome"] == "succeeded"


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

    response = client.post(
        "/jobs/job_a/complete",
        data={"summary": "Replaced front brake pads."},
        follow_redirects=False,
    )

    assert response.status_code == 303
    job_a = next(job for job in client.get("/jobs").json()["jobs"] if job["job_id"] == "job_a")
    assert job_a["job_status"] == "completed"
    assert job_a["completion_summary"] == "Replaced front brake pads."
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_theo"
    assert events[-1]["outcome"] == "succeeded"


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
    assert job_a["job_status"] == "awaiting_request"
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_jordan"
    assert events[-1]["provider"] is None
    assert events[-1]["tool_name"] is None
    assert events[-1]["decision_source"] == "backend_trusted_job_state"
    assert events[-1]["outcome"] == "denied"


def test_tech_email_attack_requires_theo(client):
    client.cookies.set("demo_actor_id", "sales_sara")

    response = client.post("/attack/tech-email-customer", follow_redirects=False)

    assert response.status_code == 303
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "sales_sara"
    assert events[-1]["provider"] is None
    assert events[-1]["tool_name"] is None
    assert events[-1]["decision_source"] == "backend_policy"
    assert events[-1]["outcome"] == "denied"


def test_wrong_job_attack_requires_jordan_and_does_not_complete_as_theo(client):
    client.cookies.set("demo_actor_id", "tech_theo")

    response = client.post("/attack/complete-wrong-job", follow_redirects=False)

    assert response.status_code == 303
    job_a = next(job for job in client.get("/jobs").json()["jobs"] if job["job_id"] == "job_a")
    assert job_a["job_status"] == "awaiting_request"
    events = client.get("/audit").json()["events"]
    assert events[-1]["actor_id"] == "tech_theo"
    assert events[-1]["provider"] is None
    assert events[-1]["tool_name"] is None
    assert events[-1]["decision_source"] == "backend_policy"
    assert events[-1]["outcome"] == "denied"


def test_dashboard_renders_identity_workflow_and_audit(client):
    # Unauthenticated: login screen shows all four actors
    response = client.get("/")
    assert response.status_code == 200
    assert "Sara Patel" in response.text
    assert "Maya Chen" in response.text

    # Logged in as Theo before approval: empty queue, attack section still visible
    response = client.get("/", cookies={"demo_actor_id": "tech_theo"})
    assert response.status_code == 200
    assert "No jobs assigned yet" in response.text
    assert "Audit" in response.text
    assert "email customer" in response.text

    # After approval Theo sees the job card
    client.cookies.set("demo_actor_id", "manager_maya")
    client.post("/jobs/job_a/approve", cookies={"demo_actor_id": "manager_maya"}, follow_redirects=False)
    response = client.get("/", cookies={"demo_actor_id": "tech_theo"})
    assert "Job A" in response.text

    # Logged in as Jordan: wrong-job attack visible
    response = client.get("/", cookies={"demo_actor_id": "tech_jordan"})
    assert "Theo" in response.text


from app.services import scalekit as scalekit_service


class WorkflowFakeTools:
    def list_scoped_tools(self, identifier: str, **kwargs):
        definition_fields = {"name": type("StringValue", (), {"string_value": "gmail_create_draft"})()}
        tool_obj = type("Tool", (), {"definition": type("Definition", (), {"fields": definition_fields})()})()
        scoped_tool = type("ScopedTool", (), {"tool": tool_obj})()
        return type("ToolsResponse", (), {"tools": [scoped_tool]})()


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
    monkeypatch.setenv("SCALEKIT_GMAIL_SEND_TOOL_NAME", "gmail_create_draft")
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
    last = events[-1]
    assert last["actor_id"] == "sales_sara"
    assert last["decision_source"] == "scalekit_execute_tool"
    assert last["external_request_id"] == "exec_route_123"
