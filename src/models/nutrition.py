from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class NutritionFact:
    name: str
    name_zh: str
    amount: float
    unit: str

    @classmethod
    def from_dict(cls, data: dict) -> NutritionFact:
        return cls(
            name=data["name"],
            name_zh=data.get("name_zh", data["name"]),
            amount=data["amount"],
            unit=data["unit"],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "name_zh": self.name_zh,
            "amount": self.amount,
            "unit": self.unit,
        }


@dataclass
class USDAEntry:
    fdc_id: int
    description: str
    description_zh: str = ""
    nutrients: list[NutritionFact] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> USDAEntry:
        nutrients = [NutritionFact.from_dict(n) for n in data.get("nutrients", [])]
        return cls(
            fdc_id=data["fdc_id"],
            description=data["description"],
            description_zh=data.get("description_zh", ""),
            nutrients=nutrients,
        )

    def to_dict(self) -> dict:
        return {
            "fdc_id": self.fdc_id,
            "description": self.description,
            "description_zh": self.description_zh,
            "nutrients": [n.to_dict() for n in self.nutrients],
        }
