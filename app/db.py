import os
import sqlite3
from pathlib import Path

DEFAULT_DATABASE_URL = ".data/shopfloor.db"


def database_path() -> Path:
    return Path(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))


def connect() -> sqlite3.Connection:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def init_db(reset: bool = False) -> None:
    path = database_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if reset and path.exists():
        path.unlink()

    with connect() as connection:
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS jobs (
              job_id TEXT PRIMARY KEY,
              customer_name TEXT NOT NULL,
              customer_email TEXT NOT NULL,
              vehicle TEXT NOT NULL,
              symptom TEXT NOT NULL,
              quote_amount INTEGER,
              quote_text TEXT,
              quote_comparables TEXT,
              quote_status TEXT NOT NULL,
              job_status TEXT NOT NULL,
              assigned_tech_id TEXT,
              manager_id TEXT,
              sales_id TEXT,
              completion_summary TEXT,
              comparables_json TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS audit_events (
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
            """
        )
        row = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()
        if row["count"] == 0:
            connection.executemany(
                """
                INSERT INTO jobs (
                  job_id, customer_name, customer_email, vehicle, symptom,
                  quote_status, job_status, assigned_tech_id, manager_id,
                  sales_id, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                [
                    (
                        "job_a",
                        "Avery Johnson",
                        "avery@example.com",
                        "2018 Honda Civic",
                        "Grinding noise when braking",
                        "needed",
                        "awaiting_request",
                        "tech_theo",
                        "manager_maya",
                        "sales_sara",
                    ),
                    (
                        "job_b",
                        "Morgan Lee",
                        "morgan@example.com",
                        "2017 Toyota Camry",
                        "Squealing brakes at low speed",
                        "needed",
                        "queued",
                        "tech_jordan",
                        "manager_maya",
                        "sales_sara",
                    ),
                ],
            )
