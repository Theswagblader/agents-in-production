# Updated Build Plan - ShopFloor

**Hackathon:** Scalekit x Actian x Render - Agents in Production Build Day SF  
**Date:** Saturday, June 27, 2026  
**Submission deadline:** 4:45 PM PDT  
**Planning timestamp:** 12:14 PM PDT  
**Working name:** ShopFloor  

---

## Executive Decision

Build the narrowest version that proves the hackathon thesis:

> One agent acts inside a car repair shop workflow as four specific people, each with different real permissions. Every action is attributed to the correct user, every identity is resolved by trusted backend state, and unauthorized attempts fail visibly.

The original plan is directionally strong and should keep the car repair shop scenario. The necessary correction is scope control. The winning project is not a complete repair-shop automation suite. The winning project is a clear delegated-auth proof that judges can understand in five minutes and inspect technically.

The project must show:

1. A live Render URL.
2. A quote generated with Actian retrieval.
3. At least one real Scalekit tool call as Sales.
4. At least one real Scalekit tool call as Manager.
5. At least one real Scalekit tool call as Technician.
6. One Scalekit/tool-scope denial.
7. One backend trusted-state denial.
8. A visible audit table tying every allowed and denied action to a specific person.

Do not spend time on a fully conversational interface, customer negotiation, photo attachments, multiple jobs beyond fixtures, or inbound Slack until the proof above is complete.

---

## One-Sentence Pitch

A single agent runs a car repair shop job lifecycle - quote, approve, dispatch, complete - but every action happens as the specific employee whose permissions allow it: Sara in Sales, Maya the Manager, Theo the assigned Technician, and Jordan the wrong Technician who gets denied.

---

## Why This Fits The Hackathon

The event theme is "build agents that act on behalf of users." The central problem is not calling APIs. The central problem is acting as the right person, with the right access, in the right tenant and context.

ShopFloor demonstrates that directly:

- The agent does not run as root.
- The agent does not use one shared service account.
- The LLM does not choose which user token to use.
- The backend resolves identity from trusted session and job state.
- Scalekit executes external tool calls with per-user connected accounts.
- Actian provides quote memory through retrieval over historical jobs.
- Render hosts the live, judge-accessible demo.

The demo should repeatedly use the phrase:

> "The model never gets a vote on whose token it uses."

That line is important because it shows awareness of the real security issue behind delegated agents.

---

## Corrected Demo Scope

### P0 - Must Ship

These are required for a credible submission.

1. Four hardcoded demo logins:
   - Sara Patel, Sales
   - Maya Chen, Manager
   - Theo Ruiz, Technician assigned to Job A
   - Jordan Lee, Technician assigned to Job B or unassigned

2. A live web dashboard on Render:
   - Login tiles for the four people.
   - Current actor shown in the top bar.
   - Workflow actions exposed as buttons.
   - Audit table always visible.

3. Quote draft:
   - User enters or selects a customer repair request.
   - Backend queries Actian for comparable historical jobs.
   - UI shows the comparable jobs and generated quote.

4. Sales action:
   - Sara sends or drafts a customer email through Scalekit Gmail.
   - Audit records Sara, the Gmail connection, the tool, and success.

5. Manager action:
   - Maya approves the job.
   - Maya writes or updates the CRM record through Scalekit Notion or whichever CRM-like connector is ready.
   - Audit records Maya, the connection, the tool, and success.

6. Technician action:
   - Theo completes Job A.
   - Theo updates the job record or sends a completion notification through a Scalekit-mediated tool.
   - Audit records Theo, the connection, the tool, and success.

7. Scalekit/tool-scope denial:
   - Theo attempts a customer-email action.
   - The system proves Theo does not have the scoped Gmail/customer-email tool or active connected account.
   - This denial should be surfaced as a Scalekit/tool availability or tool execution failure, not only as a local role check.

8. Backend trusted-state denial:
   - Jordan attempts to complete Theo's Job A.
   - Backend rejects it before any Scalekit call because `jobs.assigned_tech_id != session.actor_id`.
   - Audit records Jordan, attempted job, denial reason, and "no external tool call made."

9. Audit screen:
   - Show allowed and denied actions.
   - Every row must include a named person, not only a role.
   - Include timestamp, actor, role, action, target, provider/tool, source of decision, and outcome.

### P1 - Nice If P0 Is Done By 4:00 PM

1. Outbound Slack notification to technician.
2. One LLM-generated job summary.
3. Scalekit dashboard/audit tab open as secondary evidence.
4. Better UI styling and clearer demo copy.

### P2 - Cut Unless Everything Else Is Done

1. Inbound Slack command flow.
2. Photo attachments.
3. Customer email back-and-forth.
4. Multiple repair jobs beyond seeded fixtures.
5. Autonomous multi-step agent loop.
6. Complex CRM schema.

---

## Four Hardcoded Demo Logins

Use hardcoded logins. Do not build real authentication for the hackathon.

The login screen should present four tiles:

| Actor ID | Display name | Role | Purpose in demo |
|---|---|---|---|
| `sales_sara` | Sara Patel | Sales | Sends quote/customer email |
| `manager_maya` | Maya Chen | Manager | Approves job and writes CRM record |
| `tech_theo` | Theo Ruiz | Technician | Completes assigned Job A |
| `tech_jordan` | Jordan Lee | Technician | Attempts to touch Theo's job and gets denied |

When a tile is clicked, the backend sets a demo session cookie:

```text
demo_actor_id=sales_sara
```

The frontend may display the selected actor, but it must not submit the Scalekit identifier, connected account ID, provider credentials, or authorization role in action requests.

Correct:

```http
POST /jobs/job_a/complete
Cookie: demo_actor_id=tech_theo
Content-Type: application/json

{
  "summary": "Replaced front brake pads and resurfaced rotors."
}
```

Incorrect:

```json
{
  "role": "technician",
  "scalekit_identifier": "tech_theo",
  "connected_account_id": "ca_123",
  "job_id": "job_a",
  "summary": "Done"
}
```

The server owns the identity mapping.

---

## Corrected Access Model

This is the spine of the project. It must be reflected in code, UI, audit, and demo script.

| Person | Role | Can see | Can do through Scalekit | Cannot do |
|---|---|---|---|---|
| Sara Patel | Sales | Her customer and quote workflow | Send customer email, draft quote, create job draft | Approve jobs, complete jobs, touch technician-only records |
| Maya Chen | Manager | All jobs | Approve jobs, write CRM/Notion records, assign technicians | Pretend to be a technician completing work |
| Theo Ruiz | Technician | Job A only | Complete Job A, update Job A completion status, notify manager/sales if configured | Email customer, approve job, complete Jordan's job |
| Jordan Lee | Technician | Job B only or no assigned job | Complete only his assigned job if one exists | Complete Theo's Job A, email customer, approve job |

Important wording:

- Say "specific users," not just "roles."
- Say "Sara's connected Gmail account," not "the Sales Gmail account."
- Say "Theo cannot see or operate on Job B," not just "technicians have limited access."

---

## Two Different Denials

The original plan correctly identified that denial is the proof moment. It needs to be split into two denials so judges do not mistake backend RBAC for Scalekit delegation.

### Denial 1 - Scalekit / Tool-Scope Denial

Goal:

Show that Theo cannot send a customer email because Theo has not delegated Gmail/customer-email access.

Demo action:

1. Login as Theo.
2. Click "Try to email customer."
3. Backend resolves actor from session as `tech_theo`.
4. Backend asks Scalekit for Theo's scoped tools or tries the Gmail tool as Theo.
5. Scalekit/tool layer fails because Theo has no Gmail/customer-email scope or active connected account.
6. UI shows denial.
7. Audit records:
   - Actor: Theo Ruiz
   - Attempted action: email customer
   - Provider/tool: Gmail via Scalekit
   - Decision source: Scalekit/tool-scope
   - Outcome: denied

This must not be implemented only as:

```python
if actor.role != "sales":
    raise HTTPException(403)
```

That local check is useful, but it does not prove Scalekit value by itself.

> **HIGHEST-RISK ITEM IN THE BUILD — read before relying on this moment.**
> This is the hero beat of the demo, and *how* it fails decides whether it lands or fizzles. There are three possible mechanisms, and they are not equally strong:
>
> 1. **Strong:** Theo has Gmail connected, but his available tools are scoped (Scalekit `listScopedTools` / tool-name filter) so the customer-email tool is genuinely not in his set. The denial is visibly a delegated-scope boundary. **Aim for this.**
> 2. **Acceptable:** Theo has no Gmail connected account at all, so the call fails with "no connection." Real, but reads as missing setup rather than an enforced boundary. Usable as fallback; frame honestly (see Tool-Scope Denial Implementation below).
> 3. **Failure:** neither is configured, the call *succeeds*, and the hero moment evaporates.
>
> Therefore: **Person A must decide which mechanism produces Denial 1 and verify it actually denies — on the live Render URL, not just locally — as a named task in the first hour (see 12:15–1:15 block).** Do not treat this as something that will "just happen." It is the single most likely thing to quietly break the whole pitch.

### Denial 2 - Backend Trusted-State Denial

Goal:

Show that job ownership is enforced by trusted application state before tool execution.

Demo action:

1. Login as Jordan.
2. Try to complete Theo's Job A.
3. Backend loads Job A from the database.
4. Backend checks `job.assigned_tech_id == session.actor_id`.
5. Check fails.
6. Backend returns `403`.
7. No Scalekit tool call is made.
8. Audit records:
   - Actor: Jordan Lee
   - Attempted action: complete Job A
   - Decision source: backend trusted job state
   - Outcome: denied
   - External tool call: none

This distinction is a strength. Explain it in the demo:

> "Scalekit proves what external tools this person delegated. Our backend proves whether this specific business object belongs to this person. The model controls neither."

---

## Trusted Identity Rule

This rule should be in code comments, README, demo script, and spoken presentation:

> The identity the agent acts as is resolved by the backend from trusted session and database state. It is never chosen by the LLM, never parsed from user text, and never accepted from the browser request body.

Backend source of truth:

```python
ACTORS = {
    "sales_sara": {
        "name": "Sara Patel",
        "role": "sales",
        "scalekit_identifier": "sales_sara",
        "allowed_connections": ["gmail"],
    },
    "manager_maya": {
        "name": "Maya Chen",
        "role": "manager",
        "scalekit_identifier": "manager_maya",
        "allowed_connections": ["notion", "slack"],
    },
    "tech_theo": {
        "name": "Theo Ruiz",
        "role": "technician",
        "scalekit_identifier": "tech_theo",
        "allowed_connections": ["notion", "slack"],
    },
    "tech_jordan": {
        "name": "Jordan Lee",
        "role": "technician",
        "scalekit_identifier": "tech_jordan",
        "allowed_connections": ["notion", "slack"],
    },
}
```

The LLM can draft:

- quote text
- customer email copy
- job summary
- technician completion summary

The LLM must not decide:

- actor
- role
- tenant
- Scalekit identifier
- connected account ID
- tool permission
- whether to bypass approval gates

---

## Revised Architecture

```text
Browser on Render URL
    |
    | hardcoded login tile sets demo_actor_id cookie
    v
FastAPI backend
    |
    |-- session resolver
    |      reads demo_actor_id cookie
    |      maps to trusted actor config
    |
    |-- job repository
    |      SQLite or in-memory fixture state
    |      stores assigned_tech_id, status, quote, customer
    |
    |-- quote service
    |      queries Actian for comparable jobs
    |      optionally asks LLM to draft quote text
    |
    |-- policy checks
    |      human approval gates
    |      job ownership checks
    |
    |-- Scalekit tool wrapper
    |      executes Gmail/Notion/Slack as resolved actor
    |      logs successes and failures
    |
    |-- audit log
           local append-only table for demo visibility
```

External systems:

```text
Scalekit AgentKit
    - per-user connected accounts
    - scoped tool listing
    - tool execution

Actian VectorAI DB
    - historical repair jobs
    - semantic retrieval for quote comparables

Render
    - public web service URL
    - environment variables
    - deployment proof
```

---

## Data Model

### Actors

Can be hardcoded for the demo.

```python
@dataclass(frozen=True)
class Actor:
    actor_id: str
    display_name: str
    role: Literal["sales", "manager", "technician"]
    scalekit_identifier: str
    allowed_connections: list[str]
```

### Jobs

SQLite is fine. In-memory fixtures are acceptable if deployment persistence becomes a risk, but SQLite is better for audit and demo state.

```sql
CREATE TABLE jobs (
    job_id TEXT PRIMARY KEY,
    customer_name TEXT NOT NULL,
    customer_email TEXT NOT NULL,
    vehicle TEXT NOT NULL,
    symptom TEXT NOT NULL,
    quote_amount INTEGER,
    quote_status TEXT NOT NULL,
    job_status TEXT NOT NULL,
    assigned_tech_id TEXT,
    manager_id TEXT,
    sales_id TEXT,
    completion_summary TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
```

Seed:

| Job | Assigned tech | Purpose |
|---|---|---|
| `job_a` | `tech_theo` | Happy-path completion |
| `job_b` | `tech_jordan` or none | Wrong-job denial fixture |

### Audit Events

Local audit is mandatory even if Scalekit has dashboard logs. Local audit lets judges see the story without switching tabs.

```sql
CREATE TABLE audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    actor_id TEXT NOT NULL,
    actor_name TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    action TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT,
    provider TEXT,
    tool_name TEXT,
    decision_source TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT,
    external_request_id TEXT
);
```

Suggested `decision_source` values:

- `backend_policy`
- `backend_trusted_job_state`
- `scalekit_tool_scope`
- `scalekit_execute_tool`
- `actian_retrieval`
- `llm_generation`

Suggested `outcome` values:

- `allowed`
- `denied`
- `succeeded`
- `failed`

### Actian Historical Jobs

Do not use Qdrant-specific types such as `PointStruct` in the plan or demo unless Actian's actual docs use them. Keep this Actian-specific but API-neutral.

```python
@dataclass
class HistoricalRepairJob:
    job_id: str
    embedding_text: str
    vehicle: str
    symptom: str
    parts: list[str]
    labor_hours: float
    final_price: int
    notes: str
```

Seed 10 to 15 records, not 30. Enough to prove retrieval, small enough to debug.

Example records:

```json
[
  {
    "job_id": "hist_001",
    "embedding_text": "2018 Honda Civic grinding noise when braking front brake pads rotors",
    "vehicle": "2018 Honda Civic",
    "symptom": "Grinding noise when braking",
    "parts": ["front brake pads", "front rotors"],
    "labor_hours": 2.5,
    "final_price": 480,
    "notes": "Customer approved ceramic pad upgrade"
  },
  {
    "job_id": "hist_002",
    "embedding_text": "2017 Toyota Camry squealing brakes brake inspection pad replacement",
    "vehicle": "2017 Toyota Camry",
    "symptom": "Squealing brakes at low speed",
    "parts": ["brake pads"],
    "labor_hours": 1.7,
    "final_price": 330,
    "notes": "Rotors were within spec"
  }
]
```

UI must show the retrieved comparables. If judges cannot see the retrieved records, Actian will look bolted on.

---

## API Surface

Keep the API tiny and action-oriented.

```http
GET /                 -> dashboard
POST /demo/login      -> set demo_actor_id cookie
POST /demo/logout     -> clear cookie
GET /me               -> current actor and allowed demo actions

POST /quote/draft
GET /jobs
GET /jobs/{job_id}

POST /quote/send
POST /jobs/{job_id}/approve
POST /jobs/{job_id}/complete

POST /attack/tech-email-customer
POST /attack/complete-wrong-job

GET /audit
GET /healthz
```

### `POST /quote/draft`

Allowed:

- Sara, or any logged-in actor if quote drafting itself is harmless.

Behavior:

1. Query Actian for similar jobs.
2. Compute quote from comparable prices.
3. Optionally use LLM to draft human-readable quote.
4. Save quote to Job A.
5. Audit Actian retrieval.

### `POST /quote/send`

Allowed:

- Sara only.

Behavior:

1. Resolve actor from cookie.
2. Confirm actor is Sara/Sales.
3. Load quote.
4. Execute Scalekit Gmail tool as Sara.
5. Audit success or failure.

### `POST /jobs/{job_id}/approve`

Allowed:

- Maya only.

Behavior:

1. Resolve actor from cookie.
2. Confirm actor is Manager.
3. Update job status.
4. Execute Scalekit Notion or CRM-like tool as Maya.
5. Optionally send outbound Slack notification.
6. Audit success or failure.

### `POST /jobs/{job_id}/complete`

Allowed:

- Assigned technician only.

Behavior:

1. Resolve actor from cookie.
2. Load job from trusted database.
3. Check actor role is technician.
4. Check `job.assigned_tech_id == actor.actor_id`.
5. If false, audit denial and return `403`.
6. If true, execute Scalekit Notion/Slack tool as Theo.
7. Audit success or failure.

### `POST /attack/tech-email-customer`

Purpose:

Prove Scalekit/tool-scope denial.

Behavior:

1. Require current actor to be Theo for demo clarity.
2. Attempt to list or execute Gmail/customer-email tool for Theo through Scalekit.
3. Show denial if tool is unavailable or execution fails.
4. Audit with `decision_source = "scalekit_tool_scope"`.

### `POST /attack/complete-wrong-job`

Purpose:

Prove backend trusted-state denial.

Behavior:

1. Require current actor to be Jordan for demo clarity.
2. Attempt to complete Job A.
3. Backend denies before Scalekit.
4. Audit with `decision_source = "backend_trusted_job_state"`.

---

## Scalekit Integration Plan

### Required Connected Accounts

Use as few connectors as possible while still proving multiple identities.

Recommended:

| Person | Connection | Why |
|---|---|---|
| Sara Patel | Gmail | customer quote email |
| Maya Chen | Notion | manager writes approved job to CRM |
| Theo Ruiz | Notion or Slack | technician updates completion |
| Jordan Lee | Notion or Slack, or no active tool | wrong-job denial actor |

If Notion becomes difficult, use Slack for manager/technician actions and present it as the operational job log. The judging criterion is delegated tool execution, not Notion specifically.

### Wrapper Requirement

All Scalekit calls must go through one wrapper so audit is consistent.

```python
async def execute_tool_as_actor(
    actor: Actor,
    connection_name: str,
    tool_name: str,
    tool_input: dict,
    action: str,
    target_type: str,
    target_id: str | None,
) -> ToolResult:
    ...
```

The wrapper should:

1. Use `actor.scalekit_identifier`.
2. Pass the exact configured connection name.
3. Execute the tool.
4. Catch Scalekit exceptions.
5. Write audit event on success or failure.
6. Return a display-safe result to the UI.

Do not scatter raw Scalekit calls throughout route handlers.

### Tool-Scope Denial Implementation

Preferred proof:

1. Call Scalekit scoped tool listing for Theo.
2. Show Gmail/customer-email tool is not present.
3. Then attempt the Gmail tool as Theo, if safe, and show failure.

Fallback proof:

1. Try Gmail execution as Theo.
2. Catch the Scalekit error.
3. Display the error class/message in sanitized form.

Avoid overclaiming. If the denial is due to "no connected Gmail account" rather than a fine-grained scope policy, say:

> "Theo has not delegated this customer-email capability, so the agent cannot execute that tool as Theo."

That is still a valid delegated-auth proof.

---

## Actian Integration Plan

Actian must be visibly load-bearing. It cannot be a hidden lookup.

Quote flow:

1. Input:
   - vehicle
   - symptom
   - customer concern

2. Build retrieval query:

```text
{vehicle} {symptom} {customer concern}
```

3. Query Actian VectorAI DB for similar historical repair jobs.

4. Return top 3 comparables:
   - vehicle
   - symptom
   - parts
   - labor hours
   - final price
   - why it matched, if available

5. Compute quote:

```python
quote_amount = round(mean([job.final_price for job in comparables]) * risk_multiplier)
```

Suggested simple logic:

- `risk_multiplier = 1.0` by default.
- `risk_multiplier = 1.15` if symptom includes "noise", "leak", "warning light", or "intermittent".

6. Optional LLM prompt:

```text
Draft a concise repair quote for the customer using only these comparable jobs and the computed quote amount. Do not invent parts, discounts, or guarantees.
```

7. UI displays:
   - generated quote amount
   - quote text
   - three comparable jobs
   - "Powered by Actian retrieval" label

If Actian setup is blocked for more than 10 minutes, ask an Actian mentor immediately. Do not quietly replace it with local cosine search unless there is no other option, because sponsor-tool usage is part of technical complexity.

---

## Render Deployment Plan

Render is a required proof point because the event explicitly includes it and live URL demos score better.

Do not leave deployment until the end.

Target:

- Live Render URL working by 3:50 PM PDT.
- `/healthz` endpoint returns `200`.
- Dashboard loads without auth complexity.
- Environment variables are set in Render dashboard.

Recommended deployment shape:

1. One FastAPI web service on Render.
2. Dockerfile only if needed for dependencies.
3. SQLite database seeded at startup or pre-deploy.
4. Actian deployment confirmed early with mentor guidance.

Render supports Docker-based services and private services, but do not assume Docker Compose will run inside a single Render web service without confirming. If Actian requires a separate long-running container, treat it as a separate private service or use the event-provided recommended setup.

Required env vars:

```text
SCALEKIT_CLIENT_ID
SCALEKIT_CLIENT_SECRET
SCALEKIT_ENV_URL
SCALEKIT_GMAIL_CONNECTION_NAME
SCALEKIT_NOTION_CONNECTION_NAME
SCALEKIT_SLACK_CONNECTION_NAME
ANTHROPIC_API_KEY
ACTIAN_HOST
ACTIAN_PORT
ACTIAN_USERNAME
ACTIAN_PASSWORD
DATABASE_URL
```

Only include vars actually used. Do not block the demo on unused connectors.

---

## UI / Demo Surface

The UI should be operational, not a marketing landing page.

### Layout

Top bar:

- Current actor name.
- Role.
- Allowed capabilities.
- Logout/switch actor button.

Left column:

- Login tiles if no actor selected.
- If logged in, actor-specific actions.

Main column:

- Job lifecycle:
  - customer request
  - quote
  - comparables
  - approval state
  - assigned technician
  - completion summary

Right or bottom panel:

- Audit log, always visible.

Attack tests panel:

- "Theo tries to email customer"
- "Jordan tries to complete Theo's job"

### Login Screen

Four tiles:

```text
Sara Patel
Sales
Can send quote email

Maya Chen
Manager
Can approve and write CRM

Theo Ruiz
Technician
Assigned to Job A

Jordan Lee
Technician
Not assigned to Job A
```

### UI Copy

Use concrete, judge-friendly labels:

- "Send quote as Sara"
- "Approve job as Maya"
- "Complete Job A as Theo"
- "Attack: Theo tries customer email"
- "Attack: Jordan tries Theo's job"

Avoid vague labels:

- "Run agent"
- "Execute task"
- "Do workflow"
- "Use role"

The project is about identity, so the UI must foreground identity.

---

## Build Order From 12:14 PM

The deadline is 4:45 PM. This schedule assumes the team is starting from plan plus some setup, not from a finished app.

### 12:15 - 1:15: Scalekit Spine

Owner: Person A

Goals:

- Create or confirm Scalekit connections.
- Get one real `execute_tool` call working locally.
- Create connected accounts for Sara, Maya, Theo as needed.
- **Decide and lock the Denial 1 mechanism (see Denial 1 callout):** is Theo's email blocked by scoped-tool filtering (strong) or by having no Gmail connection (acceptable fallback)? Write down which one and why.
- **Verify Theo's email attempt actually denies**, with the chosen mechanism, and note the exact error/empty-tool-list shape the wrapper will catch.

Output:

- A script or endpoint that can execute a tool as Sara.
- A visible, reproducible failure when attempting Gmail as Theo, with the mechanism named.

If this is not working by 1:15, reduce connectors. One Sales Gmail success plus one Technician Gmail denial is more important than Notion polish.

> **Re-verify the denial on Render, not just locally.** Connected-account state and scoping live in Scalekit, so behavior is the same across environments in principle — but confirm it once the Render URL is up (3:20–3:50 block) before declaring the hero moment done. A denial that works locally and not on the live URL is the worst-case demo failure.

> **Connector single-threading risk.** Maya's CRM write and Theo's completion update both default to Notion. If Notion is flaky, two of your three "real Scalekit success" moments fail together, leaving only Sara-as-Gmail as a live external success. Either confirm Notion works in this block, or switch the manager/technician write target to Slack (a confirmed Scalekit connector) now so you are not single-threaded on one integration.


### 1:15 - 2:00: Identity Resolver And Audit

Owner: Person A with Person C

Goals:

- Implement hardcoded actors.
- Implement demo session cookie.
- Implement audit table.
- Route all tool calls through one wrapper.
- Implement wrong-job denial.

Output:

- Four login tiles or API equivalent.
- Audit rows for allowed and denied local actions.

### 2:00 - 2:40: Actian Retrieval

Owner: Person B

Goals:

- Seed 10 to 15 historical jobs.
- Query top 3 comparable jobs.
- Generate quote amount.
- Return comparables to UI/API.

Output:

- `/quote/draft` returns quote plus visible comparables.

If Actian is blocked for 10 minutes, ask a mentor. Do not silently burn the schedule.

### 2:40 - 3:20: Workflow UI

Owner: Person C

Goals:

- Build one dashboard.
- Wire login tiles.
- Wire quote, send, approve, complete buttons.
- Show job state and audit.

Output:

- Usable local demo from browser.

### 3:20 - 3:50: Render Deployment

Owner: Person C

Goals:

- Deploy FastAPI app.
- Set environment variables.
- Confirm `/healthz`.
- Confirm dashboard loads.
- Confirm at least one Scalekit success (Sara/Gmail) works from Render.
- Confirm the Denial 1 path actually denies from Render, with the mechanism chosen in the 12:15 block.

Output:

- Live URL ready for submission.

### 3:50 - 4:15: Proof And Polish

All

Goals:

- Run full happy path on live URL.
- Run both denial paths on live URL.
- Open audit screen and validate rows.
- Prepare fallback screenshots.

Output:

- Demo script locked.
- No new features after 4:15.

### 4:15 - 4:35: Rehearsal

All

Goals:

- Rehearse 5-minute script twice.
- Assign who speaks and who clicks.
- Keep fallback tabs ready.

### 4:35 - 4:45: Submit

No code changes except emergency fixes.

---

## Team Split

### Person A - Scalekit, Identity, Authorization

Owns the moat.

Files/modules:

- `identity.py`
- `scalekit_tools.py`
- `audit.py`
- denial endpoints

Responsibilities:

- Scalekit client setup.
- Connected account setup.
- Tool execution wrapper.
- Scoped tool listing.
- Scalekit denial proof.
- Trusted actor mapping.
- Job ownership check.
- Audit logging.

Definition of done:

- Can execute a tool as Sara.
- Can execute a manager/technician tool as the right person or has a credible fallback.
- Can show Theo denied from customer email through Scalekit/tool scope.
- Can show Jordan denied from Theo's job through backend trusted state.

### Person B - Actian, Quote Service, LLM Text

Owns the "what the agent knows" story.

Files/modules:

- `vector_store.py`
- `seed_jobs.py`
- `quote_service.py`
- `agent_text.py`

Responsibilities:

- Actian connection.
- Historical job seed data.
- Comparable job retrieval.
- Quote calculation.
- Optional LLM quote draft.

Definition of done:

- `/quote/draft` shows top 3 historical comparables.
- Quote amount is explainable from those comparables.
- No hallucinated quote details.

### Person C - UI, FastAPI Glue, Render, Demo

Owns the judge experience.

Files/modules:

- `main.py`
- `templates/index.html`
- `static/app.js`
- `static/styles.css`
- `render.yaml` or deployment config

Responsibilities:

- Hardcoded login UI.
- Workflow buttons.
- Audit panel.
- Attack tests panel.
- Render deployment.
- Demo script and fallback screenshots.

Definition of done:

- Live Render URL works.
- Judge can understand identity boundaries from the first screen.
- Full happy path and denial path can be clicked without terminal commands.

---

## Solid Coding Portions

These are implementation chunks that can be built mostly independently.

### Portion 1 - Demo Identity And Session

Build:

- `Actor` model.
- hardcoded actor registry.
- login endpoint.
- logout endpoint.
- `get_current_actor(request)`.
- `/me` endpoint.

Tests:

- login as each actor sets correct cookie.
- `/me` returns actor name and role.
- unknown actor cookie returns unauthenticated state.

### Portion 2 - Audit Log

Build:

- audit event schema.
- `record_audit_event(...)`.
- `/audit` endpoint.
- UI table.

Tests:

- allowed event is recorded.
- denied event is recorded.
- external request ID can be null.

### Portion 3 - Job Repository And Fixtures

Build:

- job schema.
- seed `job_a` assigned to Theo.
- seed `job_b` assigned to Jordan or unassigned.
- get/update job functions.

Tests:

- Job A loads with Theo assignment.
- Job B does not allow Theo/Jordan confusion.

### Portion 4 - Backend Trusted-State Denial

Build:

- `/jobs/{job_id}/complete`.
- ownership check.
- denial audit.

Tests:

- Theo can complete Job A.
- Jordan cannot complete Job A.
- Jordan denial creates audit row.
- Jordan denial does not call Scalekit wrapper.

### Portion 5 - Scalekit Tool Wrapper

Build:

- Scalekit client setup.
- execute tool as resolved actor.
- list scoped tools if SDK supports it.
- error capture and audit.

Tests:

- wrapper uses actor identifier from server config.
- wrapper never accepts identifier from request body.
- failed execution records audit row.

### Portion 6 - Sales Tool Call

Build:

- `/quote/send`.
- Sara-only policy.
- Gmail tool execution as Sara.
- success/failure display.

Tests:

- Sara can attempt send.
- Theo cannot pass local sales policy.
- actual Scalekit failure is displayed safely.

### Portion 7 - Manager Tool Call

Build:

- `/jobs/{job_id}/approve`.
- Maya-only policy.
- Notion/CRM update as Maya.

Tests:

- Maya can approve.
- Sara cannot approve.
- approval updates job state.
- audit row records Maya.

### Portion 8 - Scalekit Denial Attack

Build:

- `/attack/tech-email-customer`.
- current actor must be Theo for clear demo.
- call scoped tool listing or attempt Gmail execution as Theo.
- render denial result.

Tests:

- Theo attack produces denial.
- denial source is `scalekit_tool_scope` or `scalekit_execute_tool`.
- audit row records Theo.

### Portion 9 - Actian Retrieval

Build:

- seed historical repair jobs.
- retrieve comparable jobs.
- quote amount calculation.
- `/quote/draft`.

Tests:

- brake query returns brake-related jobs.
- quote amount comes from returned comparable prices.
- response includes comparables.

### Portion 10 - Dashboard UI

Build:

- login tiles.
- current actor top bar.
- job lifecycle panel.
- quote comparables panel.
- action buttons.
- attack test buttons.
- audit table.

Tests:

- each login tile changes current actor.
- buttons call correct endpoints.
- audit refreshes after action.

### Portion 11 - Render Deployment

Build:

- `/healthz`.
- deployment config.
- env var docs.
- seed-on-startup command or startup hook.

Tests:

- live URL loads.
- `/healthz` returns `200`.
- at least one Scalekit call works from Render.
- Actian retrieval works from Render or has a documented fallback.

---

## Test Plan

Prioritize high-signal tests. This is a hackathon, not a full production suite.

### Unit Tests

Required:

- actor resolution from session cookie.
- forbidden request body fields ignored or rejected.
- job ownership check.
- quote calculation from comparables.
- audit event creation.

### Integration Tests

Required if time allows:

- `/quote/draft` returns quote plus comparables.
- `/jobs/job_a/complete` succeeds for Theo.
- `/jobs/job_a/complete` fails for Jordan.
- `/attack/tech-email-customer` records denied audit event.

### Manual Live Tests

Must run on Render before submission:

1. Login as Sara.
2. Draft quote.
3. Send quote.
4. Confirm audit shows Sara.
5. Login as Maya.
6. Approve job.
7. Confirm audit shows Maya.
8. Login as Theo.
9. Complete Job A.
10. Confirm audit shows Theo.
11. Trigger Theo customer-email attack.
12. Confirm denial appears.
13. Login as Jordan.
14. Trigger wrong-job attack.
15. Confirm denial appears.

---

## Demo Script

### 0:00 - 0:30: Frame The Problem

"Most agent demos call APIs as one powerful backend account. That breaks the moment the agent needs to act as a real person with real permissions. ShopFloor is a repair-shop workflow where the same agent acts as Sara in Sales, Maya the Manager, Theo the assigned Technician, and Jordan the wrong Technician who gets denied."

### 0:30 - 1:30: Actian Quote

Click Sara.

"A customer says their 2018 Civic has grinding brakes. The agent drafts a quote, but it is not guessing. It retrieves comparable historical repairs from Actian VectorAI DB."

Show:

- top 3 comparable jobs
- quote amount
- generated quote text

### 1:30 - 2:15: Sales Sends Quote As Sara

Click "Send quote as Sara."

"Now the agent sends the quote as Sara. The browser did not send Sara's Scalekit identifier. The backend resolved Sara from the trusted session and executed the Gmail tool through Scalekit."

Show audit row:

```text
Sara Patel | Gmail | send quote | succeeded
```

### 2:15 - 3:00: Manager Approves As Maya

Switch to Maya.

Click "Approve job as Maya."

"Approval is a manager action. Maya writes the approved job to the CRM record through her connected account."

Show audit row:

```text
Maya Chen | Notion/CRM | approve job | succeeded
```

### 3:00 - 3:40: Technician Completes Assigned Job As Theo

Switch to Theo.

Click "Complete Job A as Theo."

"Theo is assigned to this job, so the backend lets the action proceed. The external update is performed as Theo."

Show audit row:

```text
Theo Ruiz | Notion/Slack | complete Job A | succeeded
```

### 3:40 - 4:35: Proof Of Denial

First denial:

"Now Theo tries to email the customer. This is not a technician capability. Scalekit does not have that delegated Gmail/customer-email tool for Theo, so the action fails."

Show:

```text
Theo Ruiz | Gmail | email customer | denied | Scalekit/tool-scope
```

Second denial:

"Now Jordan tries to complete Theo's Job A. This is a business-object authorization failure. Our backend checks trusted job state before any tool call and denies it."

Show:

```text
Jordan Lee | Job A | complete job | denied | backend trusted job state
```

### 4:35 - 5:00: Scale Line

"The important part is not the repair shop. It is the pattern: agents need delegated user authority, trusted identity resolution, scoped tools, and auditability. Today it is a repair shop. The same pattern applies to field service, healthcare ops, CRM workflows, finance back office, and any multi-tenant SaaS agent."

---

## Fallback Plan

### If Scalekit Gmail Works But Not Notion

Use Gmail for Sara success and Theo denial. Use local CRM state for manager approval, but be transparent:

"The manager CRM write is represented in our local job record; the delegated-auth proof is shown through the live Gmail tool execution and denial."

Still try to get one second Scalekit connector if possible.

### If Actian Deployment Fails On Render

Use Actian locally for a recorded screenshot or precomputed retrieval only as a last resort. Be honest:

"Actian retrieval is wired and visible locally; the Render demo uses seeded results if the database service is unreachable."

This is weaker. Ask mentors before accepting this fallback.

### If Inbound Slack Is Not Ready

Drop it. Use web buttons.

Say:

"For the demo, the technician action is triggered from the web UI so we can focus on delegated execution and audit. Slack notification is a straightforward trigger-layer extension."

### If LLM Is Flaky

Use deterministic quote text from comparables. The project is about delegated action, not prose generation.

---

## Risks And Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Too many connectors | Miss deadline | Use Gmail plus one CRM-like connector first |
| Scalekit denial looks like local RBAC | Weak sponsor story | Split denial into Scalekit/tool-scope and backend trusted-state |
| Actian looks bolted on | Lower technical complexity | Show comparable jobs directly in quote UI |
| Render deploy slips | No live demo | Deploy by 3:50, no new features after 4:15 |
| LLM chooses identity | Security critique | Backend-only identity resolver, no identity from prompts |
| Inbound Slack burns time | Scope failure | Make it P1/P2, web buttons are P0 |
| Audit API unavailable | Demo confusion | Maintain local audit table around every tool call |

---

## Exact Changes From Original Plan

1. Changed "three roles" to "four specific users" so the demo proves individual delegated identity, not just RBAC.
2. Added Jordan Lee as a second technician for the wrong-job denial.
3. Reframed the UI as hardcoded demo logins instead of real auth.
4. Removed any implication that the frontend or LLM can provide `role`, `identifier`, or `connected_account_id`.
5. Split the denial proof into:
   - Scalekit/tool-scope denial.
   - Backend trusted-state denial.
6. Replaced the Actian `PointStruct` example with API-neutral historical repair job records to avoid using Qdrant-specific language.
7. Reduced Actian seed target from 20-30 to 10-15 jobs.
8. Moved inbound Slack from required to optional.
9. Made local audit mandatory, regardless of whether Scalekit dashboard logs exist.
10. Added a precise time plan from 12:14 PM to the 4:45 PM deadline.
11. Added concrete coding portions with ownership boundaries.
12. Added a fallback plan for each high-risk sponsor integration.

### Revision pass (post-Codex review)

13. Flagged Denial 1 (Scalekit/tool-scope) as the highest-risk item: named its three possible mechanisms (scoped-tool filter = strong, no-connection = acceptable fallback, unconfigured = silent success/failure), and required Person A to decide and verify the mechanism in the first hour rather than assume it.
14. Required the Denial 1 path to be re-verified on the live Render URL (3:20-3:50 and 3:50-4:15 blocks), not just locally.
15. Surfaced the connector single-threading risk: Maya's and Theo's writes both default to Notion, so a Notion failure takes out two of three live Scalekit successes — confirm Notion early or move manager/technician writes to Slack.
16. Added "mechanism decided and verified on Render" to the Denial 1 non-negotiable.

---

## Final Non-Negotiables

Do not cut:

- named users
- trusted backend identity resolver
- one live Scalekit success
- one Scalekit/tool-scope denial, with its mechanism decided and verified on the live Render URL
- Actian comparables visible in quote UI
- live Render URL
- audit table

Cut first:

- inbound Slack
- photo attachments
- customer negotiation
- autonomous multi-step agent loop
- multiple jobs beyond fixtures
- UI polish beyond clarity

The winning version is simple, explicit, and inspectable. Judges should leave saying:

> "They did not build another API-calling agent. They built an agent that acts as the right user and fails safely as the wrong user."

