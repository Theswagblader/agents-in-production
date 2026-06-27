import os
from dataclasses import asdict, dataclass
from statistics import mean

COLLECTION_NAME = "repair_jobs"
INVENTORY_COLLECTION_NAME = "inventory_items"
VECTOR_SIZE = 384  # all-MiniLM-L6-v2 output dimension

_SEED_JOBS = [
    {
        "job_id": "hist_001",
        "vehicle": "2018 Honda Civic",
        "symptom": "Grinding noise when braking",
        "parts": ["front brake pads", "front rotors"],
        "labor_hours": 2.5,
        "final_price": 480,
        "notes": "Customer approved ceramic pad upgrade.",
    },
    {
        "job_id": "hist_002",
        "vehicle": "2017 Toyota Camry",
        "symptom": "Squealing brakes at low speed",
        "parts": ["brake pads"],
        "labor_hours": 1.7,
        "final_price": 330,
        "notes": "Rotors were within spec.",
    },
    {
        "job_id": "hist_003",
        "vehicle": "2019 Mazda 3",
        "symptom": "Front-end vibration and brake grinding",
        "parts": ["front brake pads", "front rotors", "caliper service"],
        "labor_hours": 3.0,
        "final_price": 570,
        "notes": "Caliper pins cleaned and lubricated.",
    },
    {
        "job_id": "hist_004",
        "vehicle": "2020 Ford F-150",
        "symptom": "Engine oil leak under vehicle",
        "parts": ["valve cover gasket", "oil drain plug washer"],
        "labor_hours": 2.0,
        "final_price": 320,
        "notes": "Valve cover gasket replaced, no further leaks.",
    },
    {
        "job_id": "hist_005",
        "vehicle": "2016 Chevrolet Malibu",
        "symptom": "Check engine light on, rough idle",
        "parts": ["spark plugs", "ignition coils"],
        "labor_hours": 1.5,
        "final_price": 280,
        "notes": "Misfires cleared after coil replacement.",
    },
    {
        "job_id": "hist_006",
        "vehicle": "2021 Toyota RAV4",
        "symptom": "AC not blowing cold air",
        "parts": ["refrigerant recharge", "cabin air filter"],
        "labor_hours": 1.0,
        "final_price": 190,
        "notes": "No leaks detected, system held pressure.",
    },
    {
        "job_id": "hist_007",
        "vehicle": "2015 Honda Accord",
        "symptom": "Battery dead, car won't start",
        "parts": ["battery", "battery terminal connectors"],
        "labor_hours": 0.5,
        "final_price": 210,
        "notes": "Alternator output verified normal.",
    },
    {
        "job_id": "hist_008",
        "vehicle": "2019 Subaru Outback",
        "symptom": "Transmission slipping, delayed engagement",
        "parts": ["transmission fluid", "transmission filter"],
        "labor_hours": 2.5,
        "final_price": 450,
        "notes": "Customer advised on fluid change interval.",
    },
    {
        "job_id": "hist_009",
        "vehicle": "2018 Nissan Altima",
        "symptom": "Steering wheel shakes at highway speed",
        "parts": ["tire balance", "front wheel alignment"],
        "labor_hours": 1.0,
        "final_price": 160,
        "notes": "Road force balance performed.",
    },
    {
        "job_id": "hist_010",
        "vehicle": "2022 Honda CR-V",
        "symptom": "Rear brake pads worn, squealing noise",
        "parts": ["rear brake pads", "rear rotors"],
        "labor_hours": 2.0,
        "final_price": 420,
        "notes": "Rear calipers inspected and lubricated.",
    },
    {
        "job_id": "hist_011",
        "vehicle": "2017 Ford Escape",
        "symptom": "Coolant leak, engine overheating",
        "parts": ["coolant hose", "thermostat", "coolant"],
        "labor_hours": 3.5,
        "final_price": 620,
        "notes": "Pressure test confirmed hose as source.",
    },
    {
        "job_id": "hist_012",
        "vehicle": "2020 Jeep Wrangler",
        "symptom": "Front suspension noise over bumps",
        "parts": ["sway bar links", "control arm bushings"],
        "labor_hours": 3.0,
        "final_price": 540,
        "notes": "Customer reported immediate improvement.",
    },
]


@dataclass(frozen=True)
class ComparableJob:
    job_id: str
    vehicle: str
    symptom: str
    parts: tuple[str, ...]
    labor_hours: float
    final_price: int
    notes: str

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["parts"] = list(self.parts)
        return data


@dataclass(frozen=True)
class QuoteDraft:
    quote_amount: int
    quote_text: str
    comparables: tuple[ComparableJob, ...]
    detail: str

    def comparables_for_display(self) -> list[dict[str, object]]:
        return [comparable.to_dict() for comparable in self.comparables]


def _is_live() -> bool:
    return os.environ.get("ACTIAN_MODE", "stub").lower() == "real"


def _get_client():
    from actian_vectorai import VectorAIClient
    url = os.environ.get("ACTIAN_VECTORAI_URL", "vectorai-latest:10000")
    token = os.environ.get("ACTIAN_VECTORAI_ACCESS_TOKEN", "")
    if token:
        return VectorAIClient(url, access_token=token)
    return VectorAIClient(url)


def _embed(text: str) -> list[float]:
    """Embed text using a lightweight local model (no API key needed)."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer("all-MiniLM-L6-v2")
    return model.encode(text).tolist()


def seed_collection() -> None:
    """Create the collection and upsert seed jobs. Safe to call multiple times."""
    from actian_vectorai import Distance, PointStruct, VectorParams

    with _get_client() as client:
        existing = [c["name"] for c in (client.collections.list() or [])]
        if COLLECTION_NAME not in existing:
            client.collections.create(
                name=COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.Cosine),
            )

        points = []
        for i, job in enumerate(_SEED_JOBS):
            embedding_text = f"{job['vehicle']} {job['symptom']} {' '.join(job['parts'])}"
            points.append(
                PointStruct(
                    id=i + 1,
                    vector=_embed(embedding_text),
                    payload={
                        "job_id": job["job_id"],
                        "vehicle": job["vehicle"],
                        "symptom": job["symptom"],
                        "parts": job["parts"],
                        "labor_hours": job["labor_hours"],
                        "final_price": job["final_price"],
                        "notes": job["notes"],
                    },
                )
            )
        client.points.upsert(collection_name=COLLECTION_NAME, points=points)


def _query_actian(query_text: str, limit: int = 3) -> list[ComparableJob]:
    with _get_client() as client:
        results = client.points.search(
            collection_name=COLLECTION_NAME,
            vector=_embed(query_text),
            limit=limit,
        )
        jobs = []
        for r in results:
            p = r["payload"] if isinstance(r, dict) else r.payload
            jobs.append(
                ComparableJob(
                    job_id=p["job_id"],
                    vehicle=p["vehicle"],
                    symptom=p["symptom"],
                    parts=tuple(p["parts"]),
                    labor_hours=p["labor_hours"],
                    final_price=p["final_price"],
                    notes=p["notes"],
                )
            )
        return jobs


def _stub_comparables() -> tuple[ComparableJob, ...]:
    return (
        ComparableJob("hist_001", "2018 Honda Civic", "Grinding noise when braking",
                      ("front brake pads", "front rotors"), 2.5, 480,
                      "Customer approved ceramic pad upgrade."),
        ComparableJob("hist_002", "2017 Toyota Camry", "Squealing brakes at low speed",
                      ("brake pads",), 1.7, 330, "Rotors were within spec."),
        ComparableJob("hist_003", "2019 Mazda 3", "Front-end vibration and brake grinding",
                      ("front brake pads", "front rotors", "caliper service"), 3.0, 570,
                      "Caliper pins cleaned and lubricated."),
    )


_SEED_INVENTORY = [
    {"item_id": "inv_001", "part_number": "BP-CER-F-001", "name": "Ceramic Front Brake Pads", "category": "Brakes", "quantity": 12, "reorder_threshold": 8, "unit_cost": 4200, "supplier_name": "BrakePro Supply Co.", "supplier_email": "orders@brakepro.example.com", "monthly_usage_rate": 6.5},
    {"item_id": "inv_002", "part_number": "BR-ROT-F-001", "name": "Front Brake Rotors (pair)", "category": "Brakes", "quantity": 6, "reorder_threshold": 4, "unit_cost": 8900, "supplier_name": "BrakePro Supply Co.", "supplier_email": "orders@brakepro.example.com", "monthly_usage_rate": 4.0},
    {"item_id": "inv_003", "part_number": "BP-CER-R-001", "name": "Ceramic Rear Brake Pads", "category": "Brakes", "quantity": 3, "reorder_threshold": 6, "unit_cost": 3800, "supplier_name": "BrakePro Supply Co.", "supplier_email": "orders@brakepro.example.com", "monthly_usage_rate": 5.0},
    {"item_id": "inv_004", "part_number": "BR-ROT-R-001", "name": "Rear Brake Rotors (pair)", "category": "Brakes", "quantity": 4, "reorder_threshold": 4, "unit_cost": 7600, "supplier_name": "BrakePro Supply Co.", "supplier_email": "orders@brakepro.example.com", "monthly_usage_rate": 3.2},
    {"item_id": "inv_005", "part_number": "OIL-5W30-5L", "name": "Motor Oil 5W-30 (5qt jug)", "category": "Fluids", "quantity": 24, "reorder_threshold": 12, "unit_cost": 2800, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 18.0},
    {"item_id": "inv_006", "part_number": "OIL-FLT-OEM", "name": "OEM Oil Filter (universal)", "category": "Filters", "quantity": 30, "reorder_threshold": 15, "unit_cost": 850, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 17.5},
    {"item_id": "inv_007", "part_number": "SPK-PLG-IRD", "name": "Iridium Spark Plugs (set/4)", "category": "Ignition", "quantity": 8, "reorder_threshold": 6, "unit_cost": 3200, "supplier_name": "AutoSpark Parts", "supplier_email": "parts@autospark.example.com", "monthly_usage_rate": 3.8},
    {"item_id": "inv_008", "part_number": "IGN-COIL-OEM", "name": "Ignition Coil Pack", "category": "Ignition", "quantity": 5, "reorder_threshold": 4, "unit_cost": 6500, "supplier_name": "AutoSpark Parts", "supplier_email": "parts@autospark.example.com", "monthly_usage_rate": 2.1},
    {"item_id": "inv_009", "part_number": "AIR-FLT-UNI", "name": "Engine Air Filter (universal)", "category": "Filters", "quantity": 14, "reorder_threshold": 8, "unit_cost": 1200, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 9.0},
    {"item_id": "inv_010", "part_number": "CAB-FLT-UNI", "name": "Cabin Air Filter (universal)", "category": "Filters", "quantity": 11, "reorder_threshold": 8, "unit_cost": 1100, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 8.5},
    {"item_id": "inv_011", "part_number": "BAT-12V-AGM", "name": "12V AGM Battery (group 35)", "category": "Electrical", "quantity": 4, "reorder_threshold": 3, "unit_cost": 14500, "supplier_name": "PowerCell Auto Batteries", "supplier_email": "orders@powercell.example.com", "monthly_usage_rate": 1.8},
    {"item_id": "inv_012", "part_number": "ALT-OEM-UNI", "name": "Alternator (reman, universal)", "category": "Electrical", "quantity": 2, "reorder_threshold": 2, "unit_cost": 21000, "supplier_name": "PowerCell Auto Batteries", "supplier_email": "orders@powercell.example.com", "monthly_usage_rate": 0.9},
    {"item_id": "inv_013", "part_number": "TRN-FLD-ATF", "name": "ATF Transmission Fluid (1qt)", "category": "Fluids", "quantity": 18, "reorder_threshold": 10, "unit_cost": 1400, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 12.0},
    {"item_id": "inv_014", "part_number": "TRN-FLT-OEM", "name": "Transmission Filter Kit", "category": "Filters", "quantity": 5, "reorder_threshold": 4, "unit_cost": 3600, "supplier_name": "FluidTech Distributors", "supplier_email": "supply@fluidtech.example.com", "monthly_usage_rate": 2.5},
    {"item_id": "inv_015", "part_number": "SUS-SBL-UNI", "name": "Sway Bar End Links (pair)", "category": "Suspension", "quantity": 6, "reorder_threshold": 4, "unit_cost": 5200, "supplier_name": "SuspensionPro Parts", "supplier_email": "parts@suspensionpro.example.com", "monthly_usage_rate": 2.8},
    {"item_id": "inv_016", "part_number": "SUS-CAB-UNI", "name": "Control Arm Bushings (set)", "category": "Suspension", "quantity": 4, "reorder_threshold": 3, "unit_cost": 4800, "supplier_name": "SuspensionPro Parts", "supplier_email": "parts@suspensionpro.example.com", "monthly_usage_rate": 2.0},
    {"item_id": "inv_017", "part_number": "CLT-HSE-UPP", "name": "Upper Coolant Hose", "category": "Cooling", "quantity": 5, "reorder_threshold": 4, "unit_cost": 2200, "supplier_name": "CoolSys Auto Parts", "supplier_email": "supply@coolsys.example.com", "monthly_usage_rate": 2.3},
    {"item_id": "inv_018", "part_number": "CLT-THR-OEM", "name": "Thermostat + Housing Kit", "category": "Cooling", "quantity": 6, "reorder_threshold": 4, "unit_cost": 3100, "supplier_name": "CoolSys Auto Parts", "supplier_email": "supply@coolsys.example.com", "monthly_usage_rate": 2.6},
    {"item_id": "inv_019", "part_number": "REF-R134A-L", "name": "R-134a Refrigerant (12oz can)", "category": "AC", "quantity": 9, "reorder_threshold": 6, "unit_cost": 1800, "supplier_name": "CoolSys Auto Parts", "supplier_email": "supply@coolsys.example.com", "monthly_usage_rate": 4.5},
    {"item_id": "inv_020", "part_number": "VCG-OEM-UNI", "name": "Valve Cover Gasket Kit", "category": "Engine", "quantity": 3, "reorder_threshold": 3, "unit_cost": 2900, "supplier_name": "BrakePro Supply Co.", "supplier_email": "orders@brakepro.example.com", "monthly_usage_rate": 1.2},
]


def seed_inventory_collection() -> None:
    """Create the inventory collection in Actian and upsert seed items. Safe to call multiple times."""
    from actian_vectorai import Distance, PointStruct, VectorParams

    with _get_client() as client:
        existing = [c["name"] for c in (client.collections.list() or [])]
        if INVENTORY_COLLECTION_NAME not in existing:
            client.collections.create(
                name=INVENTORY_COLLECTION_NAME,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.Cosine),
            )

        points = []
        for i, item in enumerate(_SEED_INVENTORY):
            embedding_text = f"{item['name']} {item['category']} {item['part_number']}"
            points.append(
                PointStruct(
                    id=i + 1,
                    vector=_embed(embedding_text),
                    payload=item,
                )
            )
        client.points.upsert(collection_name=INVENTORY_COLLECTION_NAME, points=points)


def draft_quote(vehicle: str, symptom: str, concern: str) -> QuoteDraft:
    query = f"{vehicle} {symptom} {concern}".strip()

    risk_keywords = {"noise", "leak", "warning light", "intermittent", "grinding", "squealing"}
    risk_multiplier = 1.15 if any(k in query.lower() for k in risk_keywords) else 1.0

    if _is_live():
        try:
            comparables = tuple(_query_actian(query, limit=3))
            detail = "Actian VectorAI retrieval: top 3 semantic matches from repair history."
        except Exception as exc:
            comparables = _stub_comparables()
            detail = f"Actian retrieval failed ({exc}); showing cached comparables."
    else:
        comparables = _stub_comparables()
        detail = "Stub mode: showing seeded comparables (set ACTIAN_MODE=real on Render)."

    quote_amount = round(mean(job.final_price for job in comparables) * risk_multiplier)
    quote_text = (
        f"Based on {len(comparables)} similar repairs for {vehicle}, "
        f"we estimate ${quote_amount} to address: {symptom or concern}."
    )
    return QuoteDraft(
        quote_amount=quote_amount,
        quote_text=quote_text,
        comparables=comparables,
        detail=detail,
    )
