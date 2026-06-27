from datetime import UTC, datetime
from typing import Any

from app.db import connect, init_db


def _row_to_dict(row: Any) -> dict[str, Any]:
    return dict(row)


def list_jobs() -> list[dict[str, Any]]:
    init_db()
    with connect() as connection:
        rows = connection.execute("SELECT * FROM jobs ORDER BY job_id").fetchall()
    return [_row_to_dict(row) for row in rows]


def get_job(job_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as connection:
        row = connection.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def update_job(job_id: str, **fields: Any) -> None:
    if not fields:
        return
    init_db()
    fields["updated_at"] = datetime.now(UTC).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), job_id]
    with connect() as connection:
        connection.execute(f"UPDATE jobs SET {assignments} WHERE job_id = ?", values)


def record_audit(
    *,
    actor_id: str,
    actor_name: str,
    actor_role: str,
    action: str,
    target_type: str,
    target_id: str | None,
    provider: str | None,
    tool_name: str | None,
    decision_source: str,
    outcome: str,
    detail: str | None = None,
    external_request_id: str | None = None,
) -> None:
    init_db()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO audit_events (
              created_at, actor_id, actor_name, actor_role, action, target_type,
              target_id, provider, tool_name, decision_source, outcome, detail,
              external_request_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                datetime.now(UTC).isoformat(),
                actor_id,
                actor_name,
                actor_role,
                action,
                target_type,
                target_id,
                provider,
                tool_name,
                decision_source,
                outcome,
                detail,
                external_request_id,
            ),
        )


def list_audit_events() -> list[dict[str, Any]]:
    init_db()
    with connect() as connection:
        rows = connection.execute("SELECT * FROM audit_events ORDER BY id").fetchall()
    return [_row_to_dict(row) for row in rows]
