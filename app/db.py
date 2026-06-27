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

            CREATE TABLE IF NOT EXISTS inventory_items (
              item_id TEXT PRIMARY KEY,
              part_number TEXT NOT NULL,
              name TEXT NOT NULL,
              category TEXT NOT NULL,
              quantity INTEGER NOT NULL DEFAULT 0,
              reorder_threshold INTEGER NOT NULL DEFAULT 5,
              unit_cost INTEGER NOT NULL,
              supplier_name TEXT NOT NULL,
              supplier_email TEXT NOT NULL,
              last_ordered TEXT,
              monthly_usage_rate REAL NOT NULL DEFAULT 0.0,
              location TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS part_orders (
              order_id TEXT PRIMARY KEY,
              item_id TEXT NOT NULL,
              quantity_ordered INTEGER NOT NULL,
              requested_by_id TEXT NOT NULL,
              requested_by_name TEXT NOT NULL,
              status TEXT NOT NULL,
              notes TEXT,
              email_subject TEXT,
              email_body TEXT,
              approved_by_id TEXT,
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              FOREIGN KEY (item_id) REFERENCES inventory_items(item_id)
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

        inv_row = connection.execute("SELECT COUNT(*) AS count FROM inventory_items").fetchone()
        if inv_row["count"] == 0:
            connection.executemany(
                """
                INSERT INTO inventory_items (
                  item_id, part_number, name, category, quantity, reorder_threshold,
                  unit_cost, supplier_name, supplier_email, last_ordered,
                  monthly_usage_rate, location, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                [
                    ("inv_001", "BP-CER-F-001", "Ceramic Front Brake Pads", "Brakes", 12, 8, 4200, "BrakePro Supply Co.", "orders@brakepro.example.com", "2026-05-15", 6.5, "Shelf A1"),
                    ("inv_002", "BR-ROT-F-001", "Front Brake Rotors (pair)", "Brakes", 6, 4, 8900, "BrakePro Supply Co.", "orders@brakepro.example.com", "2026-05-15", 4.0, "Shelf A2"),
                    ("inv_003", "BP-CER-R-001", "Ceramic Rear Brake Pads", "Brakes", 3, 6, 3800, "BrakePro Supply Co.", "orders@brakepro.example.com", "2026-04-20", 5.0, "Shelf A3"),
                    ("inv_004", "BR-ROT-R-001", "Rear Brake Rotors (pair)", "Brakes", 4, 4, 7600, "BrakePro Supply Co.", "orders@brakepro.example.com", "2026-04-20", 3.2, "Shelf A4"),
                    ("inv_005", "OIL-5W30-5L", "Motor Oil 5W-30 (5qt jug)", "Fluids", 24, 12, 2800, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-06-01", 18.0, "Shelf B1"),
                    ("inv_006", "OIL-FLT-OEM", "OEM Oil Filter (universal)", "Filters", 30, 15, 850, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-06-01", 17.5, "Shelf B2"),
                    ("inv_007", "SPK-PLG-IRD", "Iridium Spark Plugs (set/4)", "Ignition", 8, 6, 3200, "AutoSpark Parts", "parts@autospark.example.com", "2026-05-10", 3.8, "Shelf C1"),
                    ("inv_008", "IGN-COIL-OEM", "Ignition Coil Pack", "Ignition", 5, 4, 6500, "AutoSpark Parts", "parts@autospark.example.com", "2026-05-10", 2.1, "Shelf C2"),
                    ("inv_009", "AIR-FLT-UNI", "Engine Air Filter (universal)", "Filters", 14, 8, 1200, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-05-28", 9.0, "Shelf B3"),
                    ("inv_010", "CAB-FLT-UNI", "Cabin Air Filter (universal)", "Filters", 11, 8, 1100, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-05-28", 8.5, "Shelf B4"),
                    ("inv_011", "BAT-12V-AGM", "12V AGM Battery (group 35)", "Electrical", 4, 3, 14500, "PowerCell Auto Batteries", "orders@powercell.example.com", "2026-04-05", 1.8, "Shelf D1"),
                    ("inv_012", "ALT-OEM-UNI", "Alternator (reman, universal)", "Electrical", 2, 2, 21000, "PowerCell Auto Batteries", "orders@powercell.example.com", "2026-03-18", 0.9, "Shelf D2"),
                    ("inv_013", "TRN-FLD-ATF", "ATF Transmission Fluid (1qt)", "Fluids", 18, 10, 1400, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-06-01", 12.0, "Shelf B5"),
                    ("inv_014", "TRN-FLT-OEM", "Transmission Filter Kit", "Filters", 5, 4, 3600, "FluidTech Distributors", "supply@fluidtech.example.com", "2026-05-02", 2.5, "Shelf B6"),
                    ("inv_015", "SUS-SBL-UNI", "Sway Bar End Links (pair)", "Suspension", 6, 4, 5200, "SuspensionPro Parts", "parts@suspensionpro.example.com", "2026-04-15", 2.8, "Shelf E1"),
                    ("inv_016", "SUS-CAB-UNI", "Control Arm Bushings (set)", "Suspension", 4, 3, 4800, "SuspensionPro Parts", "parts@suspensionpro.example.com", "2026-04-15", 2.0, "Shelf E2"),
                    ("inv_017", "CLT-HSE-UPP", "Upper Coolant Hose", "Cooling", 5, 4, 2200, "CoolSys Auto Parts", "supply@coolsys.example.com", "2026-05-20", 2.3, "Shelf F1"),
                    ("inv_018", "CLT-THR-OEM", "Thermostat + Housing Kit", "Cooling", 6, 4, 3100, "CoolSys Auto Parts", "supply@coolsys.example.com", "2026-05-20", 2.6, "Shelf F2"),
                    ("inv_019", "REF-R134A-L", "R-134a Refrigerant (12oz can)", "AC", 9, 6, 1800, "CoolSys Auto Parts", "supply@coolsys.example.com", "2026-05-05", 4.5, "Shelf F3"),
                    ("inv_020", "VCG-OEM-UNI", "Valve Cover Gasket Kit", "Engine", 3, 3, 2900, "BrakePro Supply Co.", "orders@brakepro.example.com", None, 1.2, "Shelf G1"),
                ],
            )
