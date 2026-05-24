# src/models/unit.py
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

_DEFAULT_UNITS_PATH = Path(__file__).resolve().parent.parent / "data" / "default_units.json"


def load_default_units() -> list[dict]:
    """Load default cooking units from ``src/data/default_units.json``."""
    try:
        return json.loads(_DEFAULT_UNITS_PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return []


@dataclass
class Unit:
    key: str
    name: str
    aliases: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, key: str, data: dict) -> Unit:
        return cls(
            key=key,
            name=data.get("name", key),
            aliases=data.get("aliases", []),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "aliases": self.aliases,
        }
