from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IngredientEntry:
    ingredient_name: str
    quantity: Optional[float] = None
    unit: str = ""
    quantity_range: Optional[dict] = None  # {"min": float, "max": float}
    is_optional: bool = False
    note: str = ""
    original_quantity: str = ""
    is_estimated: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> IngredientEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "ingredient_name": self.ingredient_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "quantity_range": self.quantity_range,
            "is_optional": self.is_optional,
            "note": self.note,
            "original_quantity": self.original_quantity,
            "is_estimated": self.is_estimated,
        }


@dataclass
class StepEntry:
    step: int
    content: str
    duration_minutes: Optional[float] = None
    tips: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> StepEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "content": self.content,
            "duration_minutes": self.duration_minutes,
            "tips": self.tips,
        }


@dataclass
class Recipe:
    name: str
    source_file: str = ""
    category: str = ""
    difficulty: str = ""
    total_time_minutes: Optional[float] = None
    servings: int = 1
    images: list[str] = field(default_factory=list)
    ingredients: list[IngredientEntry] = field(default_factory=list)
    steps: list[StepEntry] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Recipe:
        ingredients = [IngredientEntry.from_dict(i) for i in data.get("ingredients", [])]
        steps = [StepEntry.from_dict(s) for s in data.get("steps", [])]
        return cls(
            name=data.get("name", ""),
            source_file=data.get("source_file", ""),
            category=data.get("category", ""),
            difficulty=data.get("difficulty", ""),
            total_time_minutes=data.get("total_time_minutes"),
            servings=data.get("servings", 1),
            images=data.get("images", []),
            ingredients=ingredients,
            steps=steps,
            tips=data.get("tips", []),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source_file": self.source_file,
            "category": self.category,
            "difficulty": self.difficulty,
            "total_time_minutes": self.total_time_minutes,
            "servings": self.servings,
            "images": self.images,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "steps": [s.to_dict() for s in self.steps],
            "tips": self.tips,
        }
