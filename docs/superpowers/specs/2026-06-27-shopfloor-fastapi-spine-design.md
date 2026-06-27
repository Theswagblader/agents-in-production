# ShopFloor FastAPI Spine Design

Date: 2026-06-27

## Goal

Build the first deployable spine for ShopFloor as one FastAPI service with a server-rendered dashboard. The spine must prove trusted actor resolution, job-state authorization, audit logging, and stable integration boundaries while teammates finish Scalekit, Render, and Actian setup.

The implementation should support deterministic local demo behavior immediately, then switch to real integrations through environment configuration without route or UI rewrites.

## Scope

In scope:

- One FastAPI app serving HTML, static CSS, and JSON endpoints where useful.
- Four hardcoded demo actors: Sara, Maya, Theo, and Jordan.
- Demo session cookie named `demo_actor_id`.
- SQLite-backed jobs and audit tables.
- Seeded Job A assigned to Theo and Job B assigned to Jordan.
- Server-rendered dashboard with login tiles, current actor, action buttons, job state, quote comparables, and audit table.
- Scalekit service boundary for Gmail, CRM, and technician update calls.
- Actian service boundary for quote comparable retrieval.
- Stub integration mode for local development.
- Real integration mode through env vars once credentials and connected accounts are ready.
- Tests for identity resolution, denial paths, audit rows, and happy-path state changes.

Out of scope for this first slice:

- Real user authentication.
- React or separate frontend build.
- Multi-job creation flows.
- Autonomous agent planning loops.
- Customer email reply handling.
- File uploads or photo attachments.

## Architecture

The service is a FastAPI monolith:

```text
Browser
  |
  v
FastAPI server
  |-- trusted session resolver
  |-- SQLite job repository
  |-- audit repository
  |-- quote service
  |     |-- Actian adapter or stub retrieval
  |-- tool service
        |-- Scalekit adapter or stub execution
```

Proposed files:

```text
app/
  main.py
  auth.py
  actors.py
  db.py
  repositories.py
  services/
    actian.py
    scalekit.py
  templates/
    index.html
  static/
    styles.css
tests/
  test_identity.py
  test_workflow.py
requirements.txt
render.yaml
.env.example
```

The dashboard is operational rather than promotional. It should show the proof artifacts directly: current actor, allowed actions, quote comparables, job lifecycle, attack buttons, and audit rows.

## Trusted Identity

The backend resolves identity only from `demo_actor_id` and the hardcoded actor map. Action routes must not accept actor id, role, Scalekit identifier, connected account id, tenant, or provider credentials from request bodies.

Actor map:

```text
sales_sara    Sara Patel    Sales        Gmail customer email
manager_maya  Maya Chen     Manager      CRM write
tech_theo     Theo Ruiz     Technician   Complete Job A
tech_jordan   Jordan Lee    Technician   Wrong-job denial fixture
```

The server owns `scalekit_identifier` and provider connection names. The model and browser never choose whose token is used.

## CRM And Real Integrations

The CRM target should be a real Scalekit-mediated integration for the final demo.

Primary plan:

- Sara uses Gmail via Scalekit to send or draft the quote email.
- Maya uses Notion via Scalekit as the CRM-like job record system.
- Theo uses Notion via Scalekit to update completion status, if Notion works for multiple actors.
- Jordan does not need a successful external call for P0 because his proof is a backend trusted-state denial.

Fallback plan:

- If Notion is not reliable by the integration checkpoint, use Slack via Scalekit as the operational CRM/job log for Maya and Theo.
- Keep UI language honest: "CRM/job log" or "operations record" instead of claiming a Notion CRM if Slack is used.

Implementation rule:

- Route handlers call internal methods such as `write_crm_record_as_actor(...)` and `send_customer_email_as_actor(...)`.
- Those methods call one Scalekit wrapper.
- The wrapper runs in `stub` mode by default for local development and `real` mode when `SCALEKIT_MODE=real`.
- Real mode must fail visibly if required env vars or connected accounts are missing.
- Stub mode must label audit rows as stubbed so it cannot be mistaken for sponsor-tool proof.

The real demo should use real Gmail for Sara and at least one real CRM/job-log write for Maya and Theo. Stub mode is only for building and testing the app before the external setup is ready.

### Stub Behavior

Stubs are local adapter responses behind the same functions used by real mode. They are for development speed, tests, and UI wiring only.

```text
Action                         Stub result                     Real result
Sara sends quote email          succeeds, marked stubbed        Gmail via Scalekit as Sara
Maya approves job               succeeds, marked stubbed        Notion or Slack via Scalekit as Maya
Theo completes Job A            succeeds, marked stubbed        Notion or Slack via Scalekit as Theo
Theo emails customer            denied, marked stubbed denial   Gmail denied by Scalekit/tool scope
Jordan completes Job A          backend denial, no tool call    same backend denial, no tool call
Quote draft                     seeded comparables              Actian retrieved comparables
```

Stub mode must be obvious in the UI and audit table. Real-mode integration proof requires audit rows without the stub marker plus any external request id or provider detail available from Scalekit or Actian.

## Actian Retrieval

The quote flow uses an Actian adapter with the same shape as the real integration:

```text
retrieve_comparable_jobs(vehicle, symptom, concern) -> top 3 comparables
```

Stub mode returns seeded historical repair jobs. Real mode queries Actian VectorAI DB. The UI must show the retrieved comparable records so Actian is visibly load-bearing.

Quote amount is computed from comparable final prices with a small risk multiplier. Quote text should be deterministic initially; optional LLM copy can be added later if time allows.

## Routes

Core routes:

```text
GET  /                  dashboard
POST /demo/login        set demo_actor_id cookie
POST /demo/logout       clear demo_actor_id cookie
GET  /healthz           deployment health check
POST /quote/draft       retrieve comparables and save quote
POST /quote/send        send quote as Sara through Gmail
POST /jobs/{id}/approve approve job as Maya and write CRM
POST /jobs/{id}/complete complete job as assigned technician
POST /attack/tech-email-customer
POST /attack/complete-wrong-job
```

All mutating routes should redirect back to `/` after recording state and audit events. Errors should be displayed on the dashboard, not only returned as raw JSON.

## Required Demo Paths

Happy paths:

- Sara drafts a quote from Actian comparables.
- Sara sends customer quote email through Gmail via Scalekit.
- Maya approves Job A and writes the CRM/job-log record through Scalekit.
- Theo completes Job A and writes a completion update through Scalekit.

Denials:

- Theo tries customer email. The Scalekit/tool layer denies Gmail/customer-email access or reports no delegated connection. Audit source: `scalekit_tool_scope`.
- Jordan tries to complete Job A. Backend denies before any external call because `assigned_tech_id != actor.actor_id`. Audit source: `backend_trusted_job_state`.

## Audit

Every allowed, denied, failed, and stubbed action writes an audit event with:

- timestamp
- actor id
- actor name
- role
- action
- target type
- target id
- provider
- tool name
- decision source
- outcome
- detail
- external request id when available

The audit table is always visible on the dashboard. Stubbed external calls must show `detail` text that says they are stubbed.

## Error Handling

- Missing session: show login tiles and disable action routes with a clear audit-free redirect.
- Unauthorized role: audit as `backend_policy` denial.
- Wrong assigned technician: audit as `backend_trusted_job_state` denial and make no external call.
- Scalekit missing tool, connection, or scope: audit as `scalekit_tool_scope` denial or `scalekit_execute_tool` failure.
- Actian unavailable in real mode: audit as `actian_retrieval` failure and display the error. Local stub mode remains available for development.

## Testing

Use pytest with FastAPI TestClient.

Required tests:

- Login sets only the trusted cookie.
- Routes ignore browser-supplied actor or role fields.
- Sara can draft and send quote in stub mode.
- Maya approval updates job state and audit.
- Theo can complete Job A.
- Theo customer email attack records a Scalekit/tool-scope denial.
- Jordan wrong-job attack records backend trusted-state denial and no external provider/tool request.
- `/healthz` returns 200.

## Deployment

Render should run the FastAPI app directly with Uvicorn. `render.yaml` should define the web service shape, while secrets stay in Render env vars.

Environment variables:

```text
DATABASE_URL
SCALEKIT_MODE
SCALEKIT_CLIENT_ID
SCALEKIT_CLIENT_SECRET
SCALEKIT_ENV_URL
SCALEKIT_GMAIL_CONNECTION_NAME
SCALEKIT_NOTION_CONNECTION_NAME
SCALEKIT_SLACK_CONNECTION_NAME
ACTIAN_MODE
ACTIAN_HOST
ACTIAN_PORT
ACTIAN_USERNAME
ACTIAN_PASSWORD
```

Only variables used by the current code should be required. Local defaults should choose SQLite plus stub integrations.

## Implementation Order

1. Scaffold FastAPI, settings, templates, static CSS, and health check.
2. Add actor map and trusted cookie login/logout.
3. Add SQLite schema, seed jobs, and audit repository.
4. Add stub Scalekit and Actian service interfaces.
5. Build dashboard and wire happy-path actions.
6. Add denial actions and audit display.
7. Add tests for the spine.
8. Add Render config and README setup instructions.
9. Switch adapters to real integrations as credentials and connected accounts become available.
