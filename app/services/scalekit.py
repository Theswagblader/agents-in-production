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
    return {
        "to": str(config.demo_to_email),
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
