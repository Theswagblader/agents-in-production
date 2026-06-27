from dataclasses import dataclass
from typing import Any

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


def send_customer_email_as_actor(actor: Actor, job: dict[str, Any]) -> ToolResult:
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


def write_crm_record_as_actor(actor: Actor, job: dict[str, Any], action: str) -> ToolResult:
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
