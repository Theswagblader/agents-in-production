from fastapi import Cookie, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.actors import ACTORS
from app.auth import get_actor_from_cookie
from app.repositories import get_job, list_audit_events, list_jobs, record_audit, update_job
from app.services.actian import draft_quote
from app.services.scalekit import ToolResult, send_customer_email_as_actor, write_crm_record_as_actor

app = FastAPI(title="ShopFloor")
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}


@app.get("/")
def dashboard(request: Request, demo_actor_id: str | None = Cookie(default=None)):
    actor = get_actor_from_cookie(demo_actor_id)
    jobs_for_view = []
    for job in list_jobs():
        view_job = dict(job)
        view_job["label"] = "Job A" if job["job_id"] == "job_a" else "Job B"
        jobs_for_view.append(view_job)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "actors": list(ACTORS.values()),
            "actor": actor,
            "jobs": jobs_for_view,
            "job_a": next(job for job in jobs_for_view if job["job_id"] == "job_a"),
            "audit_events": list_audit_events(),
        },
    )


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


def _record_tool_result(
    *,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str | None,
    result: ToolResult,
) -> None:
    record_audit(
        actor_id=actor_id,
        actor_name=actor_name,
        actor_role=actor_role,
        action=action,
        target_type=target_type,
        target_id=target_id,
        provider=result.provider,
        tool_name=result.tool_name,
        decision_source=result.decision_source,
        outcome=result.outcome,
        detail=result.detail,
        external_request_id=result.external_request_id,
    )


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


@app.post("/quote/send")
def quote_send(demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job("job_a")
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "sales_sara":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="send_quote",
            target_type="job",
            target_id="job_a",
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Sara can send customer quotes.",
        )
        return RedirectResponse("/", status_code=303)

    result = send_customer_email_as_actor(actor, job)
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="send_quote",
        target_type="job",
        target_id="job_a",
        result=result,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/approve")
def approve_job(job_id: str, demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "manager_maya":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="approve_job",
            target_type="job",
            target_id=job_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Maya can approve jobs.",
        )
        return RedirectResponse("/", status_code=303)

    update_job(job_id, job_status="approved")
    updated_job = get_job(job_id) or job
    result = write_crm_record_as_actor(actor, updated_job, "approved")
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="approve_job",
        target_type="job",
        target_id=job_id,
        result=result,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/complete")
def complete_job(
    job_id: str,
    summary: str = Form("Completed repair."),
    demo_actor_id: str | None = Cookie(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.role != "technician":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="complete_job",
            target_type="job",
            target_id=job_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only assigned technicians can complete jobs.",
        )
        return RedirectResponse("/", status_code=303)

    if job["assigned_tech_id"] != actor.actor_id:
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="complete_job",
            target_type="job",
            target_id=job_id,
            provider=None,
            tool_name=None,
            decision_source="backend_trusted_job_state",
            outcome="denied",
            detail="Denied before external tool call: job is assigned to another technician.",
        )
        return RedirectResponse("/", status_code=303)

    update_job(job_id, job_status="completed", completion_summary=summary)
    updated_job = get_job(job_id) or job
    result = write_crm_record_as_actor(actor, updated_job, "completed")
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="complete_job",
        target_type="job",
        target_id=job_id,
        result=result,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/attack/tech-email-customer")
def attack_tech_email_customer(demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job("job_a")
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "tech_theo":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="attack_tech_email_customer",
            target_type="job",
            target_id="job_a",
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Demo attack route requires Theo Ruiz as the current actor.",
        )
        return RedirectResponse("/", status_code=303)

    result = send_customer_email_as_actor(actor, job)
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="attack_tech_email_customer",
        target_type="job",
        target_id="job_a",
        result=result,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/attack/complete-wrong-job")
def attack_complete_wrong_job(demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job("job_a")
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "tech_jordan":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="attack_complete_wrong_job",
            target_type="job",
            target_id="job_a",
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Demo attack route requires Jordan Lee as the current actor.",
        )
        return RedirectResponse("/", status_code=303)

    if job["assigned_tech_id"] != actor.actor_id:
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="attack_complete_wrong_job",
            target_type="job",
            target_id="job_a",
            provider=None,
            tool_name=None,
            decision_source="backend_trusted_job_state",
            outcome="denied",
            detail="Denied before external tool call: Job A is assigned to Theo Ruiz.",
        )
        return RedirectResponse("/", status_code=303)

    return complete_job("job_a", "Completed through attack route.", demo_actor_id)
