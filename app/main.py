from fastapi import Cookie, FastAPI, Form
from fastapi.responses import RedirectResponse

from app.auth import get_actor_from_cookie
from app.repositories import get_job, list_audit_events, list_jobs, record_audit, update_job
from app.services.actian import draft_quote

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


@app.post("/quote/draft")
def quote_draft(job_id: str = Form(...), demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    draft = draft_quote(str(job["vehicle"]), str(job["symptom"]), str(job["symptom"]))
    update_job(
        job_id,
        quote_amount=draft.quote_amount,
        quote_text=draft.quote_text,
        quote_status="drafted",
    )
    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="draft_quote",
        target_type="job",
        target_id=job_id,
        provider="actian",
        tool_name="vector_retrieval",
        decision_source="actian_retrieval",
        outcome="succeeded",
        detail=f"{draft.detail} Comparables: {', '.join(job.job_id for job in draft.comparables)}",
    )
    return RedirectResponse("/", status_code=303)
