from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Ingredient:
    key: str
    name: str
    aliases: list[str] = field(default_factory=list)
    category: str = "其他"
    usda_id: Optional[int] = None
    usda_match_status: str = "unmatched"  # unmatched, matched

    @classmethod
    def from_dict(cls, key: str, data: dict) -> Ingredient:
        return cls(
            key=key,
            name=data.get("name", key),
            aliases=data.get("aliases", []),
            category=data.get("category", "其他"),
            usda_id=data.get("usda_id"),
            usda_match_status=data.get("usda_match_status", "unmatched"),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "aliases": self.aliases,
            "category": self.category,
            "usda_id": self.usda_id,
            "usda_match_status": self.usda_match_status,
        }
