# ShopFloor

FastAPI demo for the Scalekit x Actian x Render Agents in Production build day.

## Getting Started

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open `http://127.0.0.1:8000`.

Run tests:

```bash
.venv/bin/pytest -v
```

## Demo Shape

The dashboard is server-rendered by FastAPI. It has four hardcoded actors:

- Sara Patel, Sales
- Maya Chen, Manager
- Theo Ruiz, Technician assigned to Job A
- Jordan Lee, Technician not assigned to Job A

Identity is resolved only from the `demo_actor_id` cookie. The browser and the model never submit Scalekit identifiers, connected account IDs, roles, provider credentials, or tenant data.

## Scalekit Setup

For the final sponsor proof, use real Scalekit connected accounts for the capabilities each person needs:

- Sara: connect a real Gmail account for identifier `sales_sara`.
- Maya: connect a real Notion account for identifier `manager_maya`, or Slack if Notion is unreliable.
- Theo: connect a real Notion or Slack account for identifier `tech_theo`.
- Jordan: optional for P0. His key proof is a backend trusted-state denial before any external tool call.

Do not connect Theo to Gmail unless Scalekit scoped tools ensure the customer-email tool is unavailable to him. The demo needs Theo's email attempt to fail at the Scalekit/tool layer. Record the exact failure shape your teammate observes: missing scoped tool, no active connected account, or execution denial.

Keep `SCALEKIT_MODE=stub` while building locally. Switch to `SCALEKIT_MODE=real` only after the real adapter is implemented and the connected accounts above are `ACTIVE`.

## Actian Setup

Keep `ACTIAN_MODE=stub` while building locally. The quote route already uses an Actian-shaped service boundary. Real mode should replace the seeded comparable jobs with Actian VectorAI retrieval and keep returning the top 3 comparables for display.

## Render

`render.yaml` defines a single Python web service:

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

Required health check:

```text
/healthz
```

Set secrets in Render environment variables instead of committing them.
