import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from app.actors import Actor


@dataclass(frozen=True)
class ToolResult:
    ok: bool
    outcome: str
    provider: str | None
    tool_name: str | None
    decision_source: str
    detail: str
    external_request_id: str | None = None


@dataclass(frozen=True)
class ScalekitConfig:
    mode: str
    env_url: str | None
    client_id: str | None
    client_secret: str | None
    gmail_connection_name: str
    gmail_send_tool_name: str | None
    demo_to_email: str | None

    notion_connection_name: str
    notion_write_tool_name: str | None
    notion_database_id: str | None
    notion_datasource_id: str | None

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
            notion_connection_name=os.environ.get("SCALEKIT_NOTION_CONNECTION_NAME", "notion"),
            notion_write_tool_name=os.environ.get("SCALEKIT_NOTION_WRITE_TOOL_NAME"),
            notion_database_id=os.environ.get("SCALEKIT_NOTION_DATABASE_ID"),
            notion_datasource_id=os.environ.get("SCALEKIT_NOTION_DATASOURCE_ID"),
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


class ScalekitActionsClient(Protocol):
    tools: Any

    def execute_tool(self, **kwargs) -> Any: ...


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


def _tool_names(tools_response: Any) -> set[str]:
    names = set()
    # gRPC responses return (response, metadata) tuple
    if isinstance(tools_response, tuple):
        tools_response = tools_response[0]

    tools_list = getattr(tools_response, "tools", [])
    for tool in tools_list:
        if hasattr(tool, "tool") and hasattr(tool.tool, "definition"):
            fields = tool.tool.definition.fields
            if "name" in fields:
                names.add(str(fields["name"].string_value))
    return names


def _gmail_draft_input(
    config: ScalekitConfig,
    job: dict[str, Any],
    subject_override: str | None = None,
    body_override: str | None = None,
) -> dict[str, str]:
    body = body_override or str(job.get("quote_text") or f"Repair quote for {job['vehicle']}: diagnosis pending.")
    subject = subject_override or f"Repair quote for {job['vehicle']}"
    to = str(job.get("customer_email") or config.demo_to_email)
    return {
        "to": to,
        "subject": subject,
        "body": body,
    }


def send_customer_email_as_actor(
    actor: Actor,
    job: dict[str, Any],
    subject_override: str | None = None,
    body_override: str | None = None,
) -> ToolResult:
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

        try:
            from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
            actions = _get_scalekit_actions_client(config)
            tools_response = actions.tools.list_scoped_tools(
                identifier=actor.scalekit_identifier,
                filter=ScopedToolFilter(connection_names=[config.gmail_connection_name]),
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="gmail",
                tool_name=config.gmail_send_tool_name,
                decision_source="scalekit_tool_scope",
                detail=(
                    f"REAL Scalekit denial: {actor.display_name} has not delegated this "
                    f"customer-email capability ({exc.__class__.__name__}: {exc})."
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
                    f"REAL Scalekit denial: {actor.display_name} does not have the Gmail "
                    "customer-email tool in scoped tools."
                ),
            )

        try:
            execution = actions.execute_tool(
                tool_input=_gmail_draft_input(config, job, subject_override, body_override),
                tool_name=str(config.gmail_send_tool_name),
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
                f"REAL Gmail draft via Scalekit as Sara {actor.display_name} "
                f"to {config.demo_to_email}."
            ),
            external_request_id=getattr(execution, "execution_id", None),
        )

    if actor.actor_id != "sales_sara":
        return ToolResult(
            ok=False,
            outcome="denied",
            provider="gmail",
            tool_name="gmail.send_email",
            decision_source="scalekit_tool_scope",
            detail=f"STUBBED denial: {actor.display_name} has not delegated Gmail customer-email access.",
        )
    return ToolResult(
        ok=True,
        outcome="succeeded",
        provider="gmail",
        tool_name="gmail.send_email",
        decision_source="scalekit_execute_tool",
        detail=f"STUBBED Gmail send as {actor.display_name} for {job['customer_email']}.",
        external_request_id="stub-gmail-sales-sara",
    )


def send_supplier_email_as_actor(
    actor: Actor,
    order: dict[str, Any],
    subject_override: str | None = None,
    body_override: str | None = None,
) -> ToolResult:
    """Send a part order email to the supplier on behalf of the manager (Maya)."""
    config = ScalekitConfig.from_env()
    supplier_email = str(order.get("supplier_email", ""))
    supplier_name = str(order.get("supplier_name", "the supplier"))
    item_name = str(order.get("item_name", order.get("name", "the part")))
    part_number = str(order.get("part_number", ""))
    qty = int(order.get("quantity_ordered", 1))
    order_id = str(order.get("order_id", ""))

    default_subject = f"Part Order Request: {item_name} ({part_number})"
    default_body = (
        f"Dear {supplier_name},\n\n"
        f"We would like to place an order for the following part:\n\n"
        f"  Part: {item_name}\n"
        f"  Part Number: {part_number}\n"
        f"  Quantity: {qty}\n"
        f"  Order Reference: {order_id}\n\n"
        f"Please confirm availability and expected delivery timeline.\n\n"
        f"Thank you,\nMaya Chen\nClearance Manager"
    )

    subject = subject_override or default_subject
    body = body_override or default_body
    to = config.demo_to_email or supplier_email

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

        try:
            actions = _get_scalekit_actions_client(config)
            try:
                from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
                scoped_filter = ScopedToolFilter(connection_names=[config.gmail_connection_name])
            except ImportError:
                scoped_filter = None

            list_kwargs: dict[str, Any] = {"identifier": actor.scalekit_identifier}
            if scoped_filter is not None:
                list_kwargs["filter"] = scoped_filter

            tools_response = actions.tools.list_scoped_tools(**list_kwargs)
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="gmail",
                tool_name=config.gmail_send_tool_name,
                decision_source="scalekit_tool_scope",
                detail=(
                    f"REAL Scalekit denial: {actor.display_name} cannot send supplier email "
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
                detail=f"REAL Scalekit denial: {actor.display_name} does not have Gmail send in scoped tools.",
            )

        try:
            execution = actions.execute_tool(
                tool_input={"to": to, "subject": subject, "body": body},
                tool_name=str(config.gmail_send_tool_name),
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
            detail=f"REAL Gmail supplier order email via Scalekit as {actor.display_name} to {to}.",
            external_request_id=getattr(execution, "execution_id", None),
        )

    # Stub mode — only manager_maya can send supplier emails
    if actor.actor_id != "manager_maya":
        return ToolResult(
            ok=False,
            outcome="denied",
            provider="gmail",
            tool_name="gmail.send_email",
            decision_source="scalekit_tool_scope",
            detail=f"STUBBED denial: {actor.display_name} has not delegated Gmail supplier-email access.",
        )
    return ToolResult(
        ok=True,
        outcome="succeeded",
        provider="gmail",
        tool_name="gmail.send_email",
        decision_source="scalekit_execute_tool",
        detail=f"STUBBED Gmail supplier email as {actor.display_name} to {supplier_email} for order {order_id}.",
        external_request_id=f"stub-gmail-supplier-{order_id}",
    )


def _rt(value: str) -> dict:
    return {"rich_text": [{"text": {"content": str(value)[:2000]}}]}


def _select(value: str) -> dict:
    return {"select": {"name": str(value)}}


def _get_rich_text(prop: dict) -> str:
    items = prop.get("rich_text", [])
    return "".join(t.get("plain_text", "") for t in items) if items else ""


def _get_select(prop: dict) -> str:
    sel = prop.get("select") or {}
    return sel.get("name", "")


def _get_title(prop: dict) -> str:
    items = prop.get("title", [])
    return "".join(t.get("plain_text", "") for t in items) if items else ""


def _notion_row_to_job(page: dict) -> dict[str, Any]:
    from app.actors import ACTORS
    props = page.get("properties", {})
    tech_name = _get_select(props.get("Assigned Technician", {}))
    tech_id = next((a.actor_id for a in ACTORS.values() if a.display_name == tech_name), None)
    return {
        "job_id": _get_rich_text(props.get("Job ID", {})) or page.get("id", ""),
        "notion_page_id": page.get("id"),
        "customer_name": _get_rich_text(props.get("Customer Name", {})),
        "customer_email": props.get("Customer Email", {}).get("email", ""),
        "vehicle": _get_rich_text(props.get("Vehicle", {})),
        "symptom": _get_rich_text(props.get("Symptom", {})),
        "quote_amount": props.get("Quote Amount", {}).get("number"),
        "quote_text": None,
        "quote_status": _get_select(props.get("Quote Status", {})) or "needed",
        "job_status": _get_select(props.get("Job Status", {})) or "pending",
        "assigned_tech_id": tech_id,
        "assigned_tech_name": tech_name,
        "completion_summary": _get_rich_text(props.get("Completion Summary", {})),
        "comparables_json": None,
        "source": "notion",
    }


def create_notion_job(actor: Actor, job_data: dict[str, Any]) -> ToolResult:
    config = ScalekitConfig.from_env()
    if config.mode != "real" or not config.notion_datasource_id:
        return ToolResult(
            ok=True, outcome="succeeded", provider="notion", tool_name="notion_data_source_insert_row",
            decision_source="stub", detail="STUBBED notion job creation.",
        )
    try:
        from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
        actions = _get_scalekit_actions_client(config)
        tools_response = actions.tools.list_scoped_tools(
            identifier=actor.scalekit_identifier,
            filter=ScopedToolFilter(connection_names=[config.notion_connection_name]),
        )
        if config.notion_write_tool_name not in _tool_names(tools_response):
            return ToolResult(ok=False, outcome="denied", provider="notion",
                              tool_name=config.notion_write_tool_name, decision_source="scalekit_tool_scope",
                              detail=f"{actor.display_name} does not have Notion write access.")
        title = f"{job_data.get('job_id')} — {job_data.get('vehicle')} | {job_data.get('symptom', '')[:60]}"
        notion_input = {
            "data_source_id": config.notion_datasource_id,
            "properties": {
                "Name": {"title": [{"text": {"content": title[:2000]}}]},
                "Job ID": _rt(job_data.get("job_id", "")),
                "Job Status": _select(job_data.get("job_status", "pending")),
                "Vehicle": _rt(job_data.get("vehicle", "")),
                "Symptom": _rt(job_data.get("symptom", "")),
                "Customer Name": _rt(job_data.get("customer_name", "")),
                "Customer Email": {"email": job_data.get("customer_email", "")},
                "Priority": _select(job_data.get("priority", "Normal")),
                "Assigned Technician": _select(job_data.get("assigned_tech_name", "")),
                "Sales Rep": _select("Sara Patel"),
                "Manager": _select("Maya Chen"),
                "Demo Actor": _select("Sara Patel"),
            },
        }
        execution = actions.execute_tool(
            tool_input=notion_input,
            tool_name=str(config.notion_write_tool_name),
            identifier=actor.scalekit_identifier,
        )
        return ToolResult(
            ok=True, outcome="succeeded", provider="notion", tool_name=config.notion_write_tool_name,
            decision_source="scalekit_execute_tool",
            detail=f"REAL Notion job created as {actor.display_name}: {job_data.get('job_id')}.",
            external_request_id=getattr(execution, "execution_id", None),
        )
    except Exception as exc:
        return ToolResult(ok=False, outcome="failed", provider="notion", tool_name=config.notion_write_tool_name,
                          decision_source="scalekit_execute_tool",
                          detail=f"Notion job creation failed: {exc.__class__.__name__}: {exc}")


def list_notion_jobs(actor: Actor) -> list[dict[str, Any]]:
    config = ScalekitConfig.from_env()
    if config.mode != "real" or not config.notion_datasource_id or not config.notion_database_id:
        return []
    try:
        actions = _get_scalekit_actions_client(config)
        execution = actions.execute_tool(
            tool_name="notion_data_source_query",
            identifier=actor.scalekit_identifier,
            tool_input={"data_source_id": config.notion_datasource_id, "page_size": 50},
        )
        data = execution.data if hasattr(execution, "data") else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        jobs = []
        for page in results:
            job = _notion_row_to_job(page)
            if job.get("job_id") and job["job_id"] != "job_a":
                jobs.append(job)
        return jobs
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("list_notion_jobs failed: %s", exc)
        return []


def get_assigned_tech_from_crm(actor: Actor, job_id: str) -> str | None:
    """Query Notion via Scalekit as the given actor and return the assigned technician name, or None on failure."""
    config = ScalekitConfig.from_env()
    if config.mode != "real" or not config.notion_datasource_id:
        return None
    try:
        from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
        actions = _get_scalekit_actions_client(config)
        execution = actions.execute_tool(
            tool_name="notion_data_source_query",
            identifier=actor.scalekit_identifier,
            tool_input={
                "data_source_id": config.notion_datasource_id,
                "filter": {
                    "property": "Job ID",
                    "rich_text": {"equals": job_id},
                },
                "page_size": 1,
            },
        )
        data = execution.data if hasattr(execution, "data") else {}
        results = data.get("results", []) if isinstance(data, dict) else []
        if not results:
            return None
        props = results[0].get("properties", {})
        tech_prop = props.get("Assigned Technician", {})
        select = tech_prop.get("select") or {}
        return select.get("name") or None
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("CRM tech lookup failed: %s", exc)
        return None


def _build_notion_properties(title_text: str, record: dict, job: dict, action: str, actor: "Actor") -> dict:
    from app.actors import ACTORS
    summary = record.get("summary") or record.get("labor_notes") or str(job.get("completion_summary") or "")
    audit = f"{actor.display_name} performed '{action}' on {job.get('job_id')}"

    sales_rep = next((a.display_name for a in ACTORS.values() if a.role == "sales"), "")
    manager = next((a.display_name for a in ACTORS.values() if a.role == "manager"), "")
    tech_id = job.get("assigned_tech_id")
    technician = ACTORS[tech_id].display_name if tech_id and tech_id in ACTORS else ""

    props: dict[str, Any] = {
        "Name": {"title": [{"text": {"content": title_text[:2000]}}]},
        "Job ID": _rt(job.get("job_id", "")),
        "Job Status": _select(job.get("job_status", action)),
        "Vehicle": _rt(job.get("vehicle", "")),
        "Symptom": _rt(job.get("symptom", "")),
        "Quote Amount": {"number": float(job["quote_amount"]) if job.get("quote_amount") else None},
        "Quote Status": _select(job.get("quote_status") or "drafted"),
        "Customer Email": {"email": str(job.get("customer_email", ""))},
        "Customer Name": _rt(job.get("customer_name", "")),
        "Audit Trail": _rt(audit),
        "Demo Actor": _select(actor.display_name),
        "Priority": _select("Normal"),
    }
    if summary:
        props["Completion Summary"] = _rt(summary)
    if sales_rep:
        props["Sales Rep"] = _select(sales_rep)
    if manager:
        props["Manager"] = _select(manager)
    if technician:
        props["Assigned Technician"] = _select(technician)

    return props


def write_crm_record_as_actor(actor: Actor, job: dict[str, Any], action: str, record: dict | None = None) -> ToolResult:
    config = ScalekitConfig.from_env()

    if config.mode == "real":
        if not config.notion_write_tool_name:
            return ToolResult(
                ok=False,
                outcome="failed",
                provider="notion",
                tool_name=None,
                decision_source="scalekit_config",
                detail="Missing SCALEKIT_NOTION_WRITE_TOOL_NAME env var.",
            )

        try:
            from scalekit.v1.tools.tools_pb2 import ScopedToolFilter
            actions = _get_scalekit_actions_client(config)
            tools_response = actions.tools.list_scoped_tools(
                identifier=actor.scalekit_identifier,
                filter=ScopedToolFilter(connection_names=[config.notion_connection_name]),
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="notion",
                tool_name=config.notion_write_tool_name,
                decision_source="scalekit_tool_scope",
                detail=f"REAL Scalekit denial: {actor.display_name} has not delegated Notion access ({exc.__class__.__name__}: {exc}).",
            )

        if config.notion_write_tool_name not in _tool_names(tools_response):
            return ToolResult(
                ok=False,
                outcome="denied",
                provider="notion",
                tool_name=config.notion_write_tool_name,
                decision_source="scalekit_tool_scope",
                detail=f"REAL Scalekit denial: {actor.display_name} does not have the Notion write tool in scoped tools.",
            )

        r = dict(record) if record else {}
        title_text = r.get("title") or f"{job.get('job_id')} — {action}"
        notion_input = {
            "data_source_id": config.notion_datasource_id or config.notion_database_id,
            "properties": _build_notion_properties(title_text, r, job, action, actor),
        }

        try:
            execution = actions.execute_tool(
                tool_input=notion_input,
                tool_name=str(config.notion_write_tool_name),
                identifier=actor.scalekit_identifier,
            )
        except Exception as exc:
            return ToolResult(
                ok=False,
                outcome="failed",
                provider="notion",
                tool_name=config.notion_write_tool_name,
                decision_source="scalekit_execute_tool",
                detail=f"REAL Scalekit Notion execution failed ({exc.__class__.__name__}: {exc}).",
            )

        return ToolResult(
            ok=True,
            outcome="succeeded",
            provider="notion",
            tool_name=config.notion_write_tool_name,
            decision_source="scalekit_execute_tool",
            detail=f"REAL Notion CRM write via Scalekit as {actor.display_name}: {action} {job['job_id']}.",
            external_request_id=getattr(execution, "execution_id", None),
        )

    # stub mode
    if actor.actor_id == "manager_maya":
        return ToolResult(
            ok=True,
            outcome="succeeded",
            provider="notion",
            tool_name="notion.pages.create",
            decision_source="scalekit_execute_tool",
            detail=f"STUBBED Notion CRM write as {actor.display_name}: {action} {job['job_id']}.",
            external_request_id="stub-notion-manager-maya",
        )
    if actor.actor_id == "tech_theo":
        return ToolResult(
            ok=True,
            outcome="succeeded",
            provider="notion",
            tool_name="notion.pages.update",
            decision_source="scalekit_execute_tool",
            detail=f"STUBBED Notion completion update as {actor.display_name}: {job['job_id']}.",
            external_request_id="stub-notion-tech-theo",
        )
    return ToolResult(
        ok=False,
        outcome="denied",
        provider="notion",
        tool_name="notion.pages.update",
        decision_source="scalekit_tool_scope",
        detail=f"STUBBED denial: {actor.display_name} has no CRM tool for {action}.",
    )
