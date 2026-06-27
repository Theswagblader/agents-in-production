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


def create_job(
    job_id: str,
    customer_name: str,
    customer_email: str,
    vehicle: str,
    symptom: str,
    assigned_tech_id: str,
    manager_id: str = "manager_maya",
    sales_id: str = "sales_sara",
    job_status: str = "pending",
    quote_status: str = "needed",
) -> None:
    init_db()
    with connect() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO jobs (
              job_id, customer_name, customer_email, vehicle, symptom,
              quote_status, job_status, assigned_tech_id, manager_id,
              sales_id, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
            """,
            (job_id, customer_name, customer_email, vehicle, symptom,
             quote_status, job_status, assigned_tech_id, manager_id, sales_id),
        )


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


# ── Inventory ──────────────────────────────────────────────────────────────────

def list_inventory() -> list[dict[str, Any]]:
    init_db()
    with connect() as connection:
        rows = connection.execute(
            "SELECT * FROM inventory_items ORDER BY category, name"
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_inventory_item(item_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as connection:
        row = connection.execute(
            "SELECT * FROM inventory_items WHERE item_id = ?", (item_id,)
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_inventory_item(item_id: str, **fields: Any) -> None:
    if not fields:
        return
    init_db()
    fields["updated_at"] = datetime.now(UTC).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), item_id]
    with connect() as connection:
        connection.execute(
            f"UPDATE inventory_items SET {assignments} WHERE item_id = ?", values
        )


# ── Part orders ────────────────────────────────────────────────────────────────

def create_part_order(
    order_id: str,
    item_id: str,
    quantity_ordered: int,
    requested_by_id: str,
    requested_by_name: str,
    status: str,
    notes: str | None = None,
    email_subject: str | None = None,
    email_body: str | None = None,
) -> None:
    init_db()
    now = datetime.now(UTC).isoformat()
    with connect() as connection:
        connection.execute(
            """
            INSERT INTO part_orders (
              order_id, item_id, quantity_ordered, requested_by_id,
              requested_by_name, status, notes, email_subject, email_body,
              created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_id, item_id, quantity_ordered, requested_by_id,
                requested_by_name, status, notes, email_subject, email_body,
                now, now,
            ),
        )


def list_part_orders() -> list[dict[str, Any]]:
    init_db()
    with connect() as connection:
        rows = connection.execute(
            """
            SELECT po.*, ii.name AS item_name, ii.part_number,
                   ii.supplier_name, ii.supplier_email
            FROM part_orders po
            JOIN inventory_items ii ON po.item_id = ii.item_id
            ORDER BY po.created_at DESC
            """
        ).fetchall()
    return [_row_to_dict(row) for row in rows]


def get_part_order(order_id: str) -> dict[str, Any] | None:
    init_db()
    with connect() as connection:
        row = connection.execute(
            """
            SELECT po.*, ii.name AS item_name, ii.part_number,
                   ii.supplier_name, ii.supplier_email
            FROM part_orders po
            JOIN inventory_items ii ON po.item_id = ii.item_id
            WHERE po.order_id = ?
            """,
            (order_id,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def update_part_order(order_id: str, **fields: Any) -> None:
    if not fields:
        return
    init_db()
    fields["updated_at"] = datetime.now(UTC).isoformat()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = [*fields.values(), order_id]
    with connect() as connection:
        connection.execute(
            f"UPDATE part_orders SET {assignments} WHERE order_id = ?", values
        )
