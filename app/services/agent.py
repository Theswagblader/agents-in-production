import logging
from dataclasses import dataclass
from typing import Literal

import anthropic

from app.actors import Actor

log = logging.getLogger(__name__)

AgentStep = Literal[
    "draft_quote",
    "send_quote_email",
    "write_crm_approval",
    "complete_job",
    "send_completion_email",
    "simulate_request",
]


@dataclass
class AgentStepResult:
    tool_name: str
    tool_input: dict
    explanation: str


_crm_schema_cache: dict | None = None


def get_crm_schema(actor: Actor) -> dict:
    global _crm_schema_cache
    if _crm_schema_cache is not None:
        return _crm_schema_cache
    _crm_schema_cache = {"title": "string", "status": "string", "summary": "string", "vehicle": "string", "quote_amount": "number"}
    return _crm_schema_cache


_TOOL_DEFS: dict[str, list[dict]] = {
    "simulate_request": [
        {
            "name": "create_job_request",
            "description": (
                "Generate a realistic inbound automotive repair request and assign it to the right technician. "
                "Theo Ruiz specialises in Asian imports, brake systems, and suspension. "
                "Jordan Lee specialises in domestic vehicles, electrical faults, and engine diagnostics. "
                "Pick the technician whose skills best match the job."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "vehicle": {"type": "string", "description": "Year, make, and model. e.g. '2019 Toyota Camry'"},
                    "symptom": {"type": "string", "description": "What the customer is experiencing."},
                    "customer_name": {"type": "string", "description": "Realistic full name."},
                    "customer_email": {"type": "string", "description": "Realistic email address."},
                    "assigned_technician": {
                        "type": "string",
                        "enum": ["Theo Ruiz", "Jordan Lee"],
                        "description": "Pick based on technician speciality and job type.",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["Normal", "High", "Urgent"],
                        "description": "Urgency based on the described symptom.",
                    },
                },
                "required": ["vehicle", "symptom", "customer_name", "customer_email", "assigned_technician", "priority"],
            },
        }
    ],
    "draft_quote": [
        {
            "name": "draft_repair_quote",
            "description": "Draft a repair quote for the customer based on the job details and comparable repairs.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "quote_text": {
                        "type": "string",
                        "description": "Human-readable repair quote with cost breakdown and explanation.",
                    },
                    "customer_note": {
                        "type": "string",
                        "description": "A brief personalised note to accompany the quote.",
                    },
                },
                "required": ["quote_text", "customer_note"],
            },
        }
    ],
    "send_quote_email": [
        {
            "name": "send_email",
            "description": "Send the repair quote to the customer via email.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body with the repair quote details."},
                },
                "required": ["subject", "body"],
            },
        }
    ],
    "write_crm_approval": [
        {
            "name": "write_crm_record",
            "description": "Write the approved job to the CRM system.",
            "input_schema": {
                "type": "object",
                "properties": {},
                "additionalProperties": True,
            },
        }
    ],
    "complete_job": [
        {
            "name": "complete_job",
            "description": "Record the completion of a repair job with a technician summary.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string", "description": "Summary of work performed."},
                    "parts_used": {"type": "string", "description": "Parts or materials used."},
                    "labor_notes": {"type": "string", "description": "Notes about labor performed."},
                },
                "required": ["summary", "parts_used", "labor_notes"],
            },
        }
    ],
    "send_completion_email": [
        {
            "name": "send_email",
            "description": "Send a job completion notification to the customer.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Email subject line."},
                    "body": {"type": "string", "description": "Email body describing the completed repair."},
                },
                "required": ["subject", "body"],
            },
        }
    ],
}

_FALLBACKS: dict[str, AgentStepResult] = {
    "simulate_request": AgentStepResult(
        tool_name="create_job_request",
        tool_input={
            "vehicle": "2020 Honda Accord",
            "symptom": "Check engine light on, rough idle",
            "customer_name": "Alex Rivera",
            "customer_email": "alex.rivera@example.com",
            "assigned_technician": "Theo Ruiz",
            "priority": "Normal",
        },
        explanation="LLM unavailable — used fallback content",
    ),
    "draft_quote": AgentStepResult(
        tool_name="draft_repair_quote",
        tool_input={"quote_text": "Repair quote pending review.", "customer_note": "We will follow up shortly."},
        explanation="LLM unavailable — used fallback content",
    ),
    "send_quote_email": AgentStepResult(
        tool_name="send_email",
        tool_input={"subject": "Your repair quote", "body": "Please find your repair quote attached."},
        explanation="LLM unavailable — used fallback content",
    ),
    "write_crm_approval": AgentStepResult(
        tool_name="write_crm_record",
        tool_input={"title": "Job approved", "status": "approved", "summary": "Approved for repair."},
        explanation="LLM unavailable — used fallback content",
    ),
    "complete_job": AgentStepResult(
        tool_name="complete_job",
        tool_input={"summary": "Repair completed.", "parts_used": "See invoice.", "labor_notes": "Standard labor."},
        explanation="LLM unavailable — used fallback content",
    ),
    "send_completion_email": AgentStepResult(
        tool_name="send_email",
        tool_input={"subject": "Your vehicle is ready", "body": "Your repair has been completed. Please collect your vehicle."},
        explanation="LLM unavailable — used fallback content",
    ),
}


def _build_system_prompt(job: dict, step: AgentStep, comparables: list[dict] | None, crm_schema: dict | None) -> str:
    if step == "simulate_request":
        return (
            "You are simulating inbound customer requests for an automotive repair shop. "
            "Generate a realistic, varied request each time — different makes, models, symptoms. "
            "Theo Ruiz specialises in Asian imports, brake systems, and suspension work. "
            "Jordan Lee specialises in domestic vehicles, electrical faults, and engine diagnostics. "
            "Assign the technician whose skills best match the job you generate. "
            "Do not include actor names, system identifiers, or internal shop details in the output."
        )
    lines = [
        "You are an assistant for an automotive repair shop. Generate content for the requested step.",
        "",
        f"Job ID: {job.get('job_id')}",
        f"Vehicle: {job.get('vehicle')}",
        f"Symptom: {job.get('symptom')}",
        f"Customer email: {job.get('customer_email')}",
    ]
    if job.get("quote_amount"):
        lines.append(f"Quote amount: ${job['quote_amount']}")
    if job.get("quote_text"):
        lines.append(f"Quote text: {job['quote_text']}")
    if job.get("completion_summary"):
        lines.append(f"Completion summary: {job['completion_summary']}")

    if comparables:
        lines.append("")
        lines.append("Comparable repairs from historical data:")
        for c in comparables[:5]:
            lines.append(f"  - {c.get('job_id')}: {c.get('vehicle')} / {c.get('symptom')} — ${c.get('quote_amount')}")

    if crm_schema:
        lines.append("")
        lines.append("CRM record schema (field names and types you must use):")
        for field, ftype in crm_schema.items():
            lines.append(f"  - {field}: {ftype}")

    lines.append("")
    lines.append("Call the provided tool to complete your task. Do not include actor names, system names, or identity information.")
    return "\n".join(lines)


def run_agent_step(
    job: dict,
    step: AgentStep,
    comparables: list[dict] | None = None,
    crm_schema: dict | None = None,
) -> AgentStepResult:
    try:
        client = anthropic.Anthropic()
        system = _build_system_prompt(job, step, comparables, crm_schema)
        tools = _TOOL_DEFS[step]

        # For write_crm_approval, inject actual schema fields into the tool definition
        if step == "write_crm_approval" and crm_schema:
            props = {k: {"type": "string" if v == "string" else "number" if v == "number" else "string"} for k, v in crm_schema.items()}
            tools = [
                {
                    **tools[0],
                    "input_schema": {
                        "type": "object",
                        "properties": props,
                        "required": list(props.keys()),
                    },
                }
            ]

        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=system,
            tool_choice={"type": "any"},
            tools=tools,
            messages=[{"role": "user", "content": f"Execute step: {step}"}],
        )

        tool_use_block = next((b for b in response.content if b.type == "tool_use"), None)
        if tool_use_block is None:
            log.warning("run_agent_step(%s): no tool_use block in response, using fallback", step)
            return _FALLBACKS[step]

        text_block = next((b for b in response.content if b.type == "text"), None)
        explanation = text_block.text if text_block else f"Agent completed step: {step}"

        return AgentStepResult(
            tool_name=tool_use_block.name,
            tool_input=dict(tool_use_block.input),
            explanation=explanation,
        )

    except Exception as exc:
        log.error("run_agent_step(%s) failed: %s", step, exc)
        return _FALLBACKS[step]
