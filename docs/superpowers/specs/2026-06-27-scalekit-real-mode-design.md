# Scalekit Real Mode Design

Date: 2026-06-27

## Goal

Replace the current stub-only Scalekit boundary with a real mode that proves the central ShopFloor delegated-auth claim: the backend resolves the actor from trusted state, Scalekit executes external tools as that specific actor, and Theo's customer-email attempt is denied by Scalekit/tool availability or by the absence of Theo's delegated Gmail connection.

The first real-mode milestone is intentionally narrow:

- Sara can send one real customer quote email through Gmail via Scalekit.
- Theo's attempt to send the same customer email fails through the Scalekit layer and records a `scalekit_tool_scope` audit event.
- Existing stub mode remains deterministic and keeps all current tests green.

## Scope

In scope:

- Add `scalekit-sdk-python` as an optional runtime dependency used only when `SCALEKIT_MODE=real`.
- Keep `SCALEKIT_MODE=stub` as the default.
- Add a configuration object that validates real-mode environment variables.
- Add one client factory wrapper so tests can inject a fake Scalekit client without network calls.
- Use backend-owned actor identifiers: `sales_sara`, `manager_maya`, `tech_theo`, `tech_jordan`.
- Use `actions.tools.list_scoped_tools(identifier=..., page_size=100)` before customer-email execution.
- Use `actions.execute_tool(tool_name=..., tool_input=..., identifier=...)` for the actual Gmail send when the tool is available.
- Map real Scalekit successes and failures into the existing `ToolResult` audit shape.
- Add a setup runbook with exact human steps for the Scalekit dashboard.

Out of scope for this slice:

- Real Notion or Slack writes for Maya and Theo.
- Actian real retrieval.
- OAuth callback routes inside ShopFloor.
- Browser-supplied connected account IDs or provider credentials.
- LLM-generated email copy.

## Architecture

The app keeps one stable integration boundary in `app/services/scalekit.py`. Route handlers continue calling:

```python
send_customer_email_as_actor(actor, job)
write_crm_record_as_actor(actor, job, action)
```

`send_customer_email_as_actor` becomes mode-aware:

```text
SCALEKIT_MODE=stub
  -> current deterministic stub behavior

SCALEKIT_MODE=real
  -> validate env
  -> create ScalekitClient
  -> list scoped tools for actor.scalekit_identifier
  -> if Gmail send tool unavailable, return ToolResult denied
  -> execute Gmail send tool as actor.scalekit_identifier
  -> return ToolResult succeeded or failure
```

`write_crm_record_as_actor` remains stubbed in this slice. That keeps the hero proof focused on the highest-risk path: Sara Gmail success and Theo Gmail denial.

## Environment

Required in real mode:

```text
SCALEKIT_MODE=real
SCALEKIT_ENV_URL=<dashboard environment URL>
SCALEKIT_CLIENT_ID=<dashboard API credential client id>
SCALEKIT_CLIENT_SECRET=<dashboard API credential client secret>
SCALEKIT_GMAIL_CONNECTION_NAME=gmail
SCALEKIT_GMAIL_SEND_TOOL_NAME=<actual Gmail send tool name from scoped tool listing>
SHOPFLOOR_FROM_EMAIL=<Sara's authorized Gmail address, if required by tool schema>
SHOPFLOOR_DEMO_TO_EMAIL=<safe test recipient controlled by the team>
```

`SCALEKIT_GMAIL_SEND_TOOL_NAME` must be copied from Scalekit scoped tool discovery, not guessed. The docs show example tool names such as `gmail_fetch_emails`, but the exact Gmail send name must come from the configured connection.

## Trusted Identity

The browser still submits no actor, role, Scalekit identifier, connected account ID, tenant, provider credential, or token in action requests.

The route resolves the current actor from:

```text
Cookie: demo_actor_id=sales_sara
```

Then the service uses:

```python
actor.scalekit_identifier
```

This is the only value passed to Scalekit as the connected-account identifier. The model never chooses whose token is used.

## Tool Discovery And Denial

Before sending customer email, real mode asks Scalekit which tools are scoped to the actor:

```python
tools_response = actions.tools.list_scoped_tools(
    identifier=actor.scalekit_identifier,
    page_size=100,
)
```

If `SCALEKIT_GMAIL_SEND_TOOL_NAME` is absent, return:

```text
provider=gmail
tool_name=<configured send tool>
decision_source=scalekit_tool_scope
outcome=denied
detail=REAL Scalekit denial: <actor> does not have the Gmail customer-email tool in scoped tools.
```

For Theo this is the preferred hero denial. If Theo has no active Gmail connected account and Scalekit returns an exception instead of an empty scoped list, catch it and return a `scalekit_tool_scope` denial with honest text:

```text
Theo has not delegated this customer-email capability, so Scalekit cannot execute it as Theo.
```

## Gmail Execution

When the Gmail send tool is present for Sara, call:

```python
result = actions.execute_tool(
    tool_name=config.gmail_send_tool_name,
    tool_input={
        "to": config.demo_to_email,
        "subject": f"Repair quote for {job['vehicle']}",
        "body": job["quote_text"] or fallback_body,
    },
    identifier=actor.scalekit_identifier,
)
```

The exact `tool_input` keys may need adjustment after inspecting the Gmail tool schema in Scalekit. The code should keep this mapping isolated in one helper so schema changes do not leak into routes.

Success maps to:

```text
provider=gmail
tool_name=<configured send tool>
decision_source=scalekit_execute_tool
outcome=succeeded
external_request_id=<execution_id if returned>
detail=REAL Gmail send via Scalekit as Sara Patel to <safe test recipient>.
```

## Error Handling

Configuration errors:

- If `SCALEKIT_MODE=real` and required env vars are missing, return a failed `ToolResult`; do not raise into the dashboard.
- Audit source: `scalekit_config`.
- Detail must name the missing env vars without printing secret values.

Scoped tool denial:

- Missing send tool in scoped tools means denied, not failed.
- Audit source: `scalekit_tool_scope`.

Execution failure:

- Exceptions during `actions.execute_tool` after the tool is present mean failed.
- Audit source: `scalekit_execute_tool`.
- Detail should include exception class and a sanitized message.

Import failure:

- If `scalekit-sdk-python` is not installed in real mode, return a failed `ToolResult`.
- Audit source: `scalekit_config`.
- Detail says to install `scalekit-sdk-python`.

## Testing

Tests must follow TDD:

- Write one failing test.
- Run it and verify the failure is due to missing behavior.
- Implement the smallest production change.
- Run the targeted test.
- Run the full suite.

Required tests:

- Stub behavior remains unchanged when `SCALEKIT_MODE` is unset or `stub`.
- Real mode returns config failure when required env vars are missing.
- Real mode denies Theo when the configured Gmail send tool is absent from scoped tools.
- Real mode executes Sara's Gmail send when the configured tool is present.
- Real mode maps Scalekit execution exceptions to a failed `ToolResult`.
- Route-level audit rows preserve actor attribution and never use browser-supplied identity fields.

## Scalekit Setup Instructions

Human setup is documented in `docs/scalekit-setup.md`. The short version:

1. Create or confirm a Gmail connection in the Scalekit dashboard.
2. Get API credentials from Developers or Settings.
3. Generate an authorization link for `sales_sara` and complete OAuth with Sara's demo Gmail.
4. Do not authorize Gmail for `tech_theo` unless using scoped tools that remove customer-email send.
5. Run scoped tool discovery for Sara and Theo.
6. Copy the actual Gmail send tool name into `SCALEKIT_GMAIL_SEND_TOOL_NAME`.
7. Verify Sara succeeds and Theo denies locally.
8. Repeat both checks on Render after deployment.

## Acceptance Criteria

- `SCALEKIT_MODE=stub .venv/bin/pytest -v` passes.
- In real mode with missing env vars, `/quote/send` records a visible `scalekit_config` failure instead of crashing.
- In real mode with a fake client, tests prove Sara success and Theo denial.
- With real Scalekit credentials, Sara's send produces a real external execution ID or response detail.
- With real Scalekit credentials, Theo's attack produces a `scalekit_tool_scope` denial.
- The audit table shows named people for both outcomes.
- No route accepts Scalekit identity, connected account, role, provider credential, or tenant from the browser.

