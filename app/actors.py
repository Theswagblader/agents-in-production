from dataclasses import asdict, dataclass
from typing import Literal

Role = Literal["sales", "manager", "technician"]


@dataclass(frozen=True)
class Actor:
    actor_id: str
    display_name: str
    role: Role
    scalekit_identifier: str
    allowed_connections: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        data = asdict(self)
        data["allowed_connections"] = list(self.allowed_connections)
        return data


ACTORS: dict[str, Actor] = {
    "sales_sara": Actor("sales_sara", "Sara Patel", "sales", "sales_sara", ("gmail",)),
    "manager_maya": Actor("manager_maya", "Maya Chen", "manager", "manager_maya", ("notion", "slack")),
    "tech_theo": Actor("tech_theo", "Theo Ruiz", "technician", "tech_theo", ("notion", "slack")),
    "tech_jordan": Actor("tech_jordan", "Jordan Lee", "technician", "tech_jordan", ("notion", "slack")),
}
