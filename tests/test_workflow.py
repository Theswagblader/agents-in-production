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
