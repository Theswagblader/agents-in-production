from fastapi import Cookie, FastAPI, Form
from fastapi.responses import RedirectResponse

from app.auth import get_actor_from_cookie
from app.repositories import list_audit_events, list_jobs

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


@app.get("/jobs")
def jobs() -> dict[str, object]:
    return {"jobs": list_jobs()}


@app.get("/audit")
def audit() -> dict[str, object]:
    return {"events": list_audit_events()}
