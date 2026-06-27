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
    assert job_a["quote_amount"] == 460
    assert job_a["quote_status"] == "drafted"
    events = client.get("/audit").json()["events"]
    assert events[-1]["decision_source"] == "actian_retrieval"
    assert events[-1]["outcome"] == "succeeded"
    assert "stubbed comparables" in events[-1]["detail"]
