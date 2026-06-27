from dataclasses import asdict, dataclass
from statistics import mean


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


def draft_quote(vehicle: str, symptom: str, concern: str) -> QuoteDraft:
    comparables = (
        ComparableJob(
            "hist_001",
            "2018 Honda Civic",
            "Grinding noise when braking",
            ("front brake pads", "front rotors"),
            2.5,
            480,
            "Customer approved ceramic pad upgrade.",
        ),
        ComparableJob(
            "hist_002",
            "2017 Toyota Camry",
            "Squealing brakes at low speed",
            ("brake pads",),
            1.7,
            330,
            "Rotors were within spec.",
        ),
        ComparableJob(
            "hist_003",
            "2019 Mazda 3",
            "Front-end vibration and brake grinding",
            ("front brake pads", "front rotors", "caliper service"),
            3.0,
            570,
            "Caliper pins cleaned and lubricated.",
        ),
    )
    quote_amount = round(mean(job.final_price for job in comparables))
    quote_text = (
        f"Based on similar repair history for {vehicle}, we estimate ${quote_amount} "
        f"to diagnose and address: {symptom or concern}."
    )
    return QuoteDraft(
        quote_amount=quote_amount,
        quote_text=quote_text,
        comparables=comparables,
        detail="STUBBED Actian retrieval: returned 3 stubbed comparables.",
    )
