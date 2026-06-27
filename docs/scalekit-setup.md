# Scalekit Setup For ShopFloor

Use this to set up the real delegated-auth demo path: Sara sends Gmail through Scalekit, and Theo cannot send customer email.

## 1. Create Or Confirm The Gmail Connection

1. Open the Scalekit dashboard.
2. Select the same development environment used by this app.
3. Go to the Connections area.
4. Create or confirm a Gmail connection.
5. Set the connection slug/name to `gmail`, or copy the actual slug into:

```text
SCALEKIT_GMAIL_CONNECTION_NAME=<actual slug>
```

The app defaults to `gmail`.

## 2. Copy API Credentials

In the Scalekit dashboard, go to Developers or Settings, then API credentials.

Copy these into local `.env` or Render env vars:

```text
SCALEKIT_ENV_URL=<your Scalekit env URL>
SCALEKIT_CLIENT_ID=<client id>
SCALEKIT_CLIENT_SECRET=<client secret>
```

Do not commit real values.

## 3. Authorize Sara's Gmail

Use identifier `sales_sara`. That must match `Actor.scalekit_identifier` in `app/actors.py`.

Temporary local helper:

```bash
.venv/bin/python - <<'PY'
import os
from scalekit import ScalekitClient

client = ScalekitClient(
    env_url=os.environ["SCALEKIT_ENV_URL"],
    client_id=os.environ["SCALEKIT_CLIENT_ID"],
    client_secret=os.environ["SCALEKIT_CLIENT_SECRET"],
)

link = client.actions.get_authorization_link(
    identifier="sales_sara",
    connection_name=os.environ.get("SCALEKIT_GMAIL_CONNECTION_NAME", "gmail"),
)
print(link.link)
PY
```

Open the printed link and authorize the demo Gmail account for Sara.

## 4. Decide Theo's Denial Mechanism

Preferred:

- Theo has a Scalekit connected account, but scoped tools do not include the configured Gmail customer-email send tool.

Acceptable fallback:

- Theo has no Gmail connected account, so Scalekit cannot execute Gmail as `tech_theo`.

Do not leave Theo with a Gmail send tool that can send customer email. The hero demo requires Theo's email attempt to deny.

## 5. Discover The Gmail Send Tool Name

Run this after Sara authorizes Gmail:

```bash
.venv/bin/python - <<'PY'
import os
from scalekit import ScalekitClient

client = ScalekitClient(
    env_url=os.environ["SCALEKIT_ENV_URL"],
    client_id=os.environ["SCALEKIT_CLIENT_ID"],
    client_secret=os.environ["SCALEKIT_CLIENT_SECRET"],
)

response = client.actions.tools.list_scoped_tools(
    identifier="sales_sara",
    page_size=100,
)

for tool in response.tools:
    name = getattr(tool, "name", "")
    description = getattr(tool, "description", "")
    if "gmail" in name.lower() or "mail" in name.lower() or "email" in description.lower():
        print(name, "-", description)
PY
```

Pick the tool that sends an email. Set:

```text
SCALEKIT_GMAIL_SEND_TOOL_NAME=<exact tool name from output>
```

Do not guess this value.

## 6. Confirm Theo Does Not Have The Send Tool

Run:

```bash
.venv/bin/python - <<'PY'
import os
from scalekit import ScalekitClient

client = ScalekitClient(
    env_url=os.environ["SCALEKIT_ENV_URL"],
    client_id=os.environ["SCALEKIT_CLIENT_ID"],
    client_secret=os.environ["SCALEKIT_CLIENT_SECRET"],
)

send_tool = os.environ["SCALEKIT_GMAIL_SEND_TOOL_NAME"]
response = client.actions.tools.list_scoped_tools(
    identifier="tech_theo",
    page_size=100,
)
names = [getattr(tool, "name", "") for tool in response.tools]
print("Theo tool count:", len(names))
print("Has Gmail send:", send_tool in names)
for name in names:
    if "gmail" in name.lower() or "mail" in name.lower():
        print(name)
PY
```

Expected:

```text
Has Gmail send: False
```

If it prints `True`, remove or narrow Theo's Gmail delegation before demoing.

## 7. Local Real-Mode Env

Set:

```text
SCALEKIT_MODE=real
SCALEKIT_ENV_URL=<your Scalekit env URL>
SCALEKIT_CLIENT_ID=<client id>
SCALEKIT_CLIENT_SECRET=<client secret>
SCALEKIT_GMAIL_CONNECTION_NAME=gmail
SCALEKIT_GMAIL_SEND_TOOL_NAME=<exact discovered send tool>
SHOPFLOOR_FROM_EMAIL=<Sara demo Gmail address if the tool schema requires it>
SHOPFLOOR_DEMO_TO_EMAIL=<safe recipient you control>
```

Use a recipient the team controls. Do not send test messages to the actual customer fixture email.

## 8. Local Verification

Start the app:

```bash
SCALEKIT_MODE=real .venv/bin/uvicorn app.main:app --reload
```

Verify:

1. Open `http://127.0.0.1:8000`.
2. Select Sara.
3. Draft quote.
4. Send quote.
5. Confirm audit row:

```text
Actor: Sara Patel
Provider: gmail
Decision: scalekit_execute_tool
Outcome: succeeded
Detail starts with REAL Gmail send via Scalekit
```

Then:

1. Select Theo.
2. Click `Theo tries customer email`.
3. Confirm audit row:

```text
Actor: Theo Ruiz
Provider: gmail
Decision: scalekit_tool_scope
Outcome: denied
Detail says Theo has not delegated or does not have the Gmail customer-email tool
```

## 9. Render Verification

Set the same real-mode env vars in Render.

After deploy:

1. Visit `/healthz`; it must return `{"ok": true}`.
2. Run Sara send on the live URL.
3. Run Theo denial on the live URL.
4. Keep the audit table visible for the judges.

Do not claim the hero denial is done until it works on Render.

## References

- Scalekit Python SDK docs: `ScalekitClient`, connected accounts, `actions.execute_tool`, `actions.tools.list_scoped_tools`.
- Scalekit tool-calling docs: connector, connection, connected account, and user authorization are all prerequisites before tool calls.

