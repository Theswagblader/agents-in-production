import json
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

import json

from fastapi import Cookie, FastAPI, Form, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.actors import ACTORS
from app.auth import get_actor_from_cookie
from app.db import init_db
from app.repositories import (
    create_job, get_job, get_inventory_item, get_part_order,
    list_audit_events, list_jobs, list_inventory, list_part_orders,
    record_audit, update_job, update_inventory_item,
    create_part_order, update_part_order,
)
from app.services.actian import draft_quote, seed_collection, seed_inventory_collection
from app.services.agent import get_crm_schema, run_agent_step
from app.services.scalekit import ToolResult, create_notion_job, get_assigned_tech_from_crm, list_notion_jobs, send_customer_email_as_actor, send_supplier_email_as_actor, write_crm_record_as_actor


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.environ.get("ACTIAN_MODE", "stub").lower() == "real":
        try:
            seed_collection()
        except Exception as exc:
            print(f"[actian] seed failed (continuing in stub fallback): {exc}")
        try:
            seed_inventory_collection()
        except Exception as exc:
            print(f"[actian] inventory seed failed (continuing in stub fallback): {exc}")
    yield


app = FastAPI(title="ShopFloor", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")


@app.get("/healthz")
def healthz() -> dict[str, bool]:
    return {"ok": True}







@app.get("/debug/tool-schema")
def debug_tool_schema(tool: str = "notion_data_source_insert_row", connection: str = "notion") -> dict:
    import json as _json
    from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
    from app.services.scalekit import ScalekitConfig, _get_scalekit_actions_client
    config = ScalekitConfig.from_env()
    actor = ACTORS["manager_maya"]
    try:
        actions = _get_scalekit_actions_client(config)
        resp = actions.tools.list_scoped_tools(
            identifier=actor.scalekit_identifier,
            filter=ScopedToolFilter(connection_names=[connection]),
        )
        if isinstance(resp, tuple):
            resp = resp[0]
        for scoped in resp.tools:
            t = scoped.tool
            fields = t.definition.fields
            name = fields.get("name")
            if name and name.string_value == tool:
                # serialize the whole definition to a readable form
                from google.protobuf.json_format import MessageToDict
                return {"tool": tool, "definition": MessageToDict(t.definition)}
        return {"error": f"{tool} not found in scoped tools"}
    except Exception as exc:
        return {"error": str(exc)}



def _build_template_context(request: Request, demo_actor_id: str | None) -> dict:
    actor = get_actor_from_cookie(demo_actor_id)

    # SQLite jobs (Job A + any locally-created sim jobs)
    sqlite_jobs = {job["job_id"]: dict(job) for job in list_jobs()}

    # Notion jobs — only in real mode, only for authenticated actors
    notion_jobs: list[dict] = []
    if actor:
        notion_jobs = list_notion_jobs(ACTORS["manager_maya"])

    # Merge: Notion jobs that aren't already in SQLite get added to view
    merged: dict[str, dict] = dict(sqlite_jobs)
    for nj in notion_jobs:
        jid = nj.get("job_id", "")
        if jid and jid not in merged:
            merged[jid] = nj

    jobs_for_view = []
    for job in merged.values():
        view_job = dict(job)
        view_job.setdefault("source", "sqlite")
        jobs_for_view.append(view_job)
    jobs_for_view.sort(key=lambda j: j.get("job_id", ""))

    job_a_data = merged.get("job_a", {})
    job_a_comparables = []
    raw = job_a_data.get("comparables_json")
    if raw:
        try:
            job_a_comparables = json.loads(raw)
        except Exception:
            pass

    return {
        "actors": list(ACTORS.values()),
        "actor": actor,
        "jobs": jobs_for_view,
        "job_a": job_a_data,
        "job_a_comparables": job_a_comparables,
        "audit_events": list_audit_events(),
        "inventory": list_inventory(),
        "part_orders": list_part_orders(),
    }


@app.get("/")
def dashboard(request: Request, demo_actor_id: str | None = Cookie(default=None)):
    return templates.TemplateResponse(
        request,
        "index.html",
        _build_template_context(request, demo_actor_id),
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


@app.post("/demo/reset")
def demo_reset() -> RedirectResponse:
    init_db(reset=True)
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


@app.post("/jobs/simulate-request")
def simulate_request(demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.actor_id != "sales_sara":
        return RedirectResponse("/", status_code=303)

    agent_result = run_agent_step({}, "simulate_request")
    inputs = agent_result.tool_input

    # resolve assigned tech name → actor_id
    tech_name = inputs.get("assigned_technician", "Theo Ruiz")
    tech_actor = next((a for a in ACTORS.values() if a.display_name == tech_name), None)
    tech_id = tech_actor.actor_id if tech_actor else "tech_theo"

    import re, time
    job_id = "sim_" + re.sub(r"[^a-z0-9]", "", inputs.get("vehicle", "vehicle").lower())[:12] + "_" + str(int(time.time()))[-4:]

    job_data = {
        "job_id": job_id,
        "customer_name": inputs.get("customer_name", ""),
        "customer_email": inputs.get("customer_email", ""),
        "vehicle": inputs.get("vehicle", ""),
        "symptom": inputs.get("symptom", ""),
        "assigned_tech_id": tech_id,
        "assigned_tech_name": tech_name,
        "job_status": "pending",
        "priority": inputs.get("priority", "Normal"),
    }

    # Write to Notion via Maya (CRM owner — Sara has no Notion scope)
    notion_result = create_notion_job(ACTORS["manager_maya"], job_data)

    # Also mirror to SQLite so existing routes work
    create_job(
        job_id=job_id,
        customer_name=job_data["customer_name"],
        customer_email=job_data["customer_email"],
        vehicle=job_data["vehicle"],
        symptom=job_data["symptom"],
        assigned_tech_id=tech_id,
        job_status="pending",
    )

    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="simulate_request",
        target_type="job",
        target_id=job_id,
        provider=notion_result.provider,
        tool_name=notion_result.tool_name,
        decision_source=notion_result.decision_source,
        outcome=notion_result.outcome,
        detail=f"AI generated: {inputs.get('vehicle')} / {inputs.get('symptom')} → assigned to {tech_name} ({inputs.get('priority')} priority). {agent_result.explanation}",
    )
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/receive-request")
def receive_request(job_id: str, demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.actor_id != "sales_sara":
        return RedirectResponse("/", status_code=303)
    update_job(job_id, job_status="pending")
    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="receive_customer_request",
        target_type="job",
        target_id=job_id,
        provider=None,
        tool_name=None,
        decision_source="backend_policy",
        outcome="succeeded",
        detail="Inbound customer request logged.",
    )
    return RedirectResponse("/", status_code=303)


@app.post("/quote/draft")
def quote_draft(job_id: str = Form(...), demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    draft = draft_quote(str(job["vehicle"]), str(job["symptom"]), str(job["symptom"]))
    comparables = draft.comparables_for_display()
    agent_result = run_agent_step(dict(job), "draft_quote", comparables=comparables)
    quote_text = agent_result.tool_input.get("quote_text", draft.quote_text)
    update_job(
        job_id,
        quote_amount=draft.quote_amount,
        quote_text=quote_text,
        quote_status="drafted",
        job_status="quoted",
        comparables_json=json.dumps(comparables),
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
        detail=f"{draft.detail} Comparables: {', '.join(c.job_id for c in draft.comparables)}. {agent_result.explanation}",
    )
    return RedirectResponse("/", status_code=303)


@app.post("/quote/send")
def quote_send(
    demo_actor_id: str | None = Cookie(default=None),
    job_id: str = Form(default="job_a"),
    subject: str | None = Form(default=None),
    body: str | None = Form(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "sales_sara":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="send_quote",
            target_type="job",
            target_id=job_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Sara can send customer quotes.",
        )
        return RedirectResponse("/", status_code=303)

    agent_result = run_agent_step(dict(job), "send_quote_email")
    result = send_customer_email_as_actor(
        actor,
        job,
        subject_override=subject or agent_result.tool_input.get("subject"),
        body_override=body or agent_result.tool_input.get("body"),
    )
    if result.outcome in ("succeeded", "allowed"):
        update_job(job_id, job_status="quote_sent")
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="send_quote",
        target_type="job",
        target_id=job_id,
        result=result,
    )
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/submit")
def submit_job(job_id: str, demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.actor_id != "sales_sara":
        return RedirectResponse("/", status_code=303)
    update_job(job_id, job_status="submitted")
    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="submit_job_to_crm",
        target_type="job",
        target_id=job_id,
        provider=None,
        tool_name=None,
        decision_source="backend_policy",
        outcome="succeeded",
        detail="Job formally submitted to CRM for manager review.",
    )
    return RedirectResponse("/", status_code=303)


@app.post("/jobs/{job_id}/send-completion")
def send_completion(job_id: str, demo_actor_id: str | None = Cookie(default=None)) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    job = get_job(job_id)
    if actor is None or job is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "sales_sara":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="send_completion_email",
            target_type="job",
            target_id=job_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Sara can send completion emails to customers.",
        )
        return RedirectResponse("/", status_code=303)

    agent_result = run_agent_step(dict(job), "send_completion_email")
    result = send_customer_email_as_actor(
        actor,
        job,
        subject_override=agent_result.tool_input.get("subject"),
        body_override=agent_result.tool_input.get("body"),
    )
    if result.outcome in ("succeeded", "allowed"):
        update_job(job_id, job_status="closed")
    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="send_completion_email",
        target_type="job",
        target_id=job_id,
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
    crm_schema = get_crm_schema(actor)
    agent_result = run_agent_step(dict(updated_job), "write_crm_approval", crm_schema=crm_schema)
    result = write_crm_record_as_actor(actor, updated_job, "approved", record=agent_result.tool_input)
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

    crm_assigned = get_assigned_tech_from_crm(actor, job_id)
    if crm_assigned is not None:
        # CRM is authoritative — check name from Notion record written by Maya
        if crm_assigned != actor.display_name:
            record_audit(
                actor_id=actor.actor_id,
                actor_name=actor.display_name,
                actor_role=actor.role,
                action="complete_job",
                target_type="job",
                target_id=job_id,
                provider="notion",
                tool_name="notion_data_source_query",
                decision_source="notion_crm_trusted_state",
                outcome="denied",
                detail=f"Denied: CRM assigns this job to '{crm_assigned}', not '{actor.display_name}'.",
            )
            return RedirectResponse("/", status_code=303)
    elif job["assigned_tech_id"] != actor.actor_id:
        # fallback to local DB if CRM unavailable
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

    agent_result = run_agent_step(dict(job), "complete_job")
    completion_summary = agent_result.tool_input.get("summary", summary)
    update_job(job_id, job_status="completed", completion_summary=completion_summary)
    updated_job = get_job(job_id) or job
    result = write_crm_record_as_actor(actor, updated_job, "completed", record=agent_result.tool_input)
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
    if actor is None:
        return RedirectResponse("/", status_code=303)

    if actor.actor_id != "tech_jordan":
        record_audit(
            actor_id=actor.actor_id,
            actor_name=actor.display_name,
            actor_role=actor.role,
            action="attack_complete_wrong_job",
            target_type="job",
            target_id=None,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Demo attack route requires Jordan Lee as the current actor.",
        )
        return RedirectResponse("/", status_code=303)

    # Find any job assigned to Theo that Jordan has no right to complete
    theo_job = next(
        (j for j in list_jobs() if j["assigned_tech_id"] == "tech_theo"),
        None,
    )
    if theo_job is None:
        return RedirectResponse("/", status_code=303)

    target_job_id = theo_job["job_id"]
    return complete_job(target_job_id, "Completed through attack route.", demo_actor_id)


# ── Inventory management ──────────────────────────────────────────────────────

def _inventory_template_context(request: Request, demo_actor_id: str | None) -> dict:
    actor = get_actor_from_cookie(demo_actor_id)
    inventory = list_inventory()
    orders = list_part_orders()
    return {
        "actors": list(ACTORS.values()),
        "actor": actor,
        "inventory": inventory,
        "part_orders": orders,
        "audit_events": list_audit_events(),
    }


@app.get("/inventory")
def inventory_page(request: Request, demo_actor_id: str | None = Cookie(default=None)):
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.role not in ("manager", "technician"):
        return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse(
        request,
        "inventory.html",
        _inventory_template_context(request, demo_actor_id),
    )


@app.post("/inventory/item/{item_id}/update-stock")
def update_stock(
    item_id: str,
    quantity: int = Form(...),
    mode: str = Form(default="set"),
    demo_actor_id: str | None = Cookie(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.role not in ("manager", "technician"):
        return RedirectResponse("/inventory", status_code=303)

    item = get_inventory_item(item_id)
    if item is None:
        return RedirectResponse("/inventory", status_code=303)

    old_qty = int(item["quantity"])
    if mode == "add":
        new_qty = old_qty + quantity
    elif mode == "subtract":
        new_qty = max(0, old_qty - quantity)
    else:
        new_qty = max(0, quantity)

    update_inventory_item(item_id, quantity=new_qty)
    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="update_stock",
        target_type="inventory_item",
        target_id=item_id,
        provider=None,
        tool_name=None,
        decision_source="backend_policy",
        outcome="succeeded",
        detail=f"{item['name']}: {old_qty} → {new_qty} (mode: {mode}).",
    )
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/order/create")
def create_order(
    item_id: str = Form(...),
    quantity_ordered: int = Form(...),
    notes: str = Form(default=""),
    email_subject: str = Form(default=""),
    email_body: str = Form(default=""),
    demo_actor_id: str | None = Cookie(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.role not in ("manager", "technician"):
        record_audit(
            actor_id=actor.actor_id if actor else "unknown",
            actor_name=actor.display_name if actor else "Unknown",
            actor_role=actor.role if actor else "unknown",
            action="create_part_order",
            target_type="part_order",
            target_id=None,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only managers and technicians can create part orders.",
        )
        return RedirectResponse("/inventory", status_code=303)

    item = get_inventory_item(item_id)
    if item is None:
        return RedirectResponse("/inventory", status_code=303)

    import uuid
    order_id = f"po_{uuid.uuid4().hex[:8]}"

    # Manager orders skip approval; technician orders need manager approval
    status = "approved" if actor.role == "manager" else "pending_approval"

    create_part_order(
        order_id=order_id,
        item_id=item_id,
        quantity_ordered=quantity_ordered,
        requested_by_id=actor.actor_id,
        requested_by_name=actor.display_name,
        status=status,
        notes=notes or None,
        email_subject=email_subject or None,
        email_body=email_body or None,
    )

    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="create_part_order",
        target_type="part_order",
        target_id=order_id,
        provider=None,
        tool_name=None,
        decision_source="backend_policy",
        outcome="succeeded",
        detail=f"Part order {order_id} for {quantity_ordered}x {item['name']} — status: {status}.",
    )

    # Manager auto-sends email immediately after creating the order
    if actor.role == "manager":
        order = get_part_order(order_id)
        if order:
            result = send_supplier_email_as_actor(
                actor, order,
                subject_override=email_subject or None,
                body_override=email_body or None,
            )
            if result.outcome in ("succeeded", "allowed"):
                update_part_order(order_id, status="email_sent")
            _record_tool_result(
                actor_id=actor.actor_id,
                actor_name=actor.display_name,
                actor_role=actor.role,
                action="send_part_order_email",
                target_type="part_order",
                target_id=order_id,
                result=result,
            )

    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/order/{order_id}/approve")
def approve_order(
    order_id: str,
    demo_actor_id: str | None = Cookie(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.actor_id != "manager_maya":
        record_audit(
            actor_id=actor.actor_id if actor else "unknown",
            actor_name=actor.display_name if actor else "Unknown",
            actor_role=actor.role if actor else "unknown",
            action="approve_part_order",
            target_type="part_order",
            target_id=order_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Maya can approve part orders submitted by technicians.",
        )
        return RedirectResponse("/inventory", status_code=303)

    order = get_part_order(order_id)
    if order is None or order["status"] != "pending_approval":
        return RedirectResponse("/inventory", status_code=303)

    update_part_order(order_id, status="approved", approved_by_id=actor.actor_id)
    record_audit(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="approve_part_order",
        target_type="part_order",
        target_id=order_id,
        provider=None,
        tool_name=None,
        decision_source="backend_policy",
        outcome="succeeded",
        detail=f"Part order {order_id} approved by {actor.display_name}.",
    )
    return RedirectResponse("/inventory", status_code=303)


@app.post("/inventory/order/{order_id}/send-email")
def send_order_email(
    order_id: str,
    subject: str = Form(default=""),
    body: str = Form(default=""),
    demo_actor_id: str | None = Cookie(default=None),
) -> RedirectResponse:
    actor = get_actor_from_cookie(demo_actor_id)
    if actor is None or actor.actor_id != "manager_maya":
        record_audit(
            actor_id=actor.actor_id if actor else "unknown",
            actor_name=actor.display_name if actor else "Unknown",
            actor_role=actor.role if actor else "unknown",
            action="send_part_order_email",
            target_type="part_order",
            target_id=order_id,
            provider=None,
            tool_name=None,
            decision_source="backend_policy",
            outcome="denied",
            detail="Only Maya can send part order emails to suppliers.",
        )
        return RedirectResponse("/inventory", status_code=303)

    order = get_part_order(order_id)
    if order is None or order["status"] not in ("approved",):
        return RedirectResponse("/inventory", status_code=303)

    result = send_supplier_email_as_actor(
        actor, order,
        subject_override=subject or None,
        body_override=body or None,
    )
    if result.outcome in ("succeeded", "allowed"):
        update_part_order(order_id, status="email_sent")

    _record_tool_result(
        actor_id=actor.actor_id,
        actor_name=actor.display_name,
        actor_role=actor.role,
        action="send_part_order_email",
        target_type="part_order",
        target_id=order_id,
        result=result,
    )
    return RedirectResponse("/inventory", status_code=303)
