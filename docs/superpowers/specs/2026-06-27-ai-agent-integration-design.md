# AI Agent Integration Design — ShopFloor

**Date:** 2026-06-27  
**Status:** Approved  

---

## Problem

Every Scalekit tool call currently passes hardcoded template strings as content (email bodies, CRM records, completion summaries). The agent does not reason about the job — it just executes predetermined text. This misses the "agents in production" thesis: the model should decide what to do and generate the content; the backend should enforce who executes it.

---

## Approach

Step-by-step UI stays unchanged. Each button click that previously executed a Scalekit tool with a template string now first calls a per-step LLM agent (Anthropic tool use). The LLM receives the job context and abstract tool schemas, selects the right tool, and generates all content. The backend takes those generated inputs and executes the Scalekit call as the resolved actor. The model never sees actor identity, Scalekit identifiers, or connected account information.

---

## Architecture

### New module: `app/services/agent.py`

Single public function:

```python
def run_agent_step(
    job: dict,
    step: AgentStep,
    comparables: list[dict] | None = None,
    crm_schema: dict | None = None,
) -> AgentStepResult:
```

`AgentStep` is a string literal enum:

```
draft_quote | send_quote_email | write_crm_approval | complete_job | send_completion_email
```

`AgentStepResult`:

```python
@dataclass
class AgentStepResult:
    tool_name: str          # which tool the LLM called
    tool_input: dict        # LLM-generated inputs
    explanation: str        # LLM's plaintext summary of what it decided
```

The function:
1. Builds a system prompt with job context (vehicle, symptom, quote amount, comparables if relevant, CRM schema if relevant). No actor name, no Scalekit info.
2. Calls `anthropic.Anthropic().messages.create` with `model="claude-haiku-4-5-20251001"`, `tool_choice={"type": "any"}`, and step-scoped tool definitions.
3. Extracts the first tool-use block from the response.
4. Returns `AgentStepResult`. On any exception, returns a fallback result with template content and logs the error.

---

## Tool definitions per step

All tool schemas are abstract — no provider names, no identity.

| Step | Tool name | LLM generates |
|---|---|---|
| `draft_quote` | `draft_repair_quote` | `quote_text`, `customer_note` |
| `send_quote_email` | `send_email` | `subject`, `body` |
| `write_crm_approval` | `write_crm_record` | Fields matching fetched Notion schema |
| `complete_job` | `complete_job` | `summary`, `parts_used`, `labor_notes` |
| `send_completion_email` | `send_email` | `subject`, `body` |

For `write_crm_approval`, the Notion database schema is injected into the system prompt so the LLM formats the record to match actual property names and types (selects, dates, etc.).

---

## CRM schema cache

New module-level dict in `agent.py`:

```python
_crm_schema_cache: dict | None = None
```

`get_crm_schema(actor: Actor) -> dict` — fetches the Notion database schema via Scalekit on first call, stores in `_crm_schema_cache`, returns cached value on subsequent calls. If the fetch fails, returns a minimal fallback schema `{title, status, summary, vehicle, quote_amount}` and logs a warning. The app boots and works regardless.

---

## Changes to `main.py`

Each route that calls a Scalekit tool is updated:

**`/quote/draft`:**
```
actian retrieval → run_agent_step(job, "draft_quote", comparables=comparables)
→ update_job(quote_text=result.tool_input["quote_text"])
```

**`/quote/send`:**
```
run_agent_step(job, "send_quote_email")
→ send_customer_email_as_actor(actor, job, body_override=result.tool_input["body"], subject_override=result.tool_input["subject"])
```

**`/jobs/{job_id}/approve`:**
```
crm_schema = get_crm_schema(actor)
→ run_agent_step(job, "write_crm_approval", crm_schema=crm_schema)
→ write_crm_record_as_actor(actor, job, "approved", record=result.tool_input)
```

**`/jobs/{job_id}/complete`:**
```
run_agent_step(job, "complete_job")
→ update_job(completion_summary=result.tool_input["summary"])
→ write_crm_record_as_actor(actor, job, "completed", record=result.tool_input)
```

**`/jobs/{job_id}/send-completion`:**
```
run_agent_step(job, "send_completion_email")
→ send_customer_email_as_actor(actor, job, body_override=result.tool_input["body"], ...)
```

The `result.explanation` is stored as the `detail` field on every audit event, so judges can see what the model reasoned.

---

## Error handling

`run_agent_step` never raises. Any exception (API error, malformed response, timeout) is caught, logged, and returns a fallback `AgentStepResult` with template-generated content. The Scalekit call proceeds with fallback content and the audit `detail` notes `"LLM unavailable — used fallback content"`.

---

## Dependencies

Add to `requirements.txt`:
```
anthropic
```

`ANTHROPIC_API_KEY` env var — already set.

---

## Testing

Light coverage:
- `run_agent_step` with a mocked Anthropic client returns valid `AgentStepResult`
- `run_agent_step` returns fallback content when Anthropic raises
- Schema cache returns same object on second call without making a second network request
- Existing 20 workflow tests continue to pass (routes use stub Scalekit, LLM call mocked at `anthropic.Anthropic`)

---

## What the model controls vs. what the backend controls

| Decision | Owner |
|---|---|
| Email subject and body | LLM |
| CRM record content and field values | LLM |
| Completion summary text | LLM |
| Quote human-readable text | LLM |
| Which actor executes the tool | Backend (session cookie) |
| Which Scalekit connection to use | Backend (actor config) |
| Whether the actor is allowed to act | Backend (policy + job state) |
| Audit record | Backend |
