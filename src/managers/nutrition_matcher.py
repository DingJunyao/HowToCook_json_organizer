# src/managers/nutrition_matcher.py
from __future__ import annotations
from src.models.nutrition import USDAEntry, NutritionFact


class NutritionMatcher:
    def __init__(self, usda_data: list[dict]):
        self._entries: list[USDAEntry] = [USDAEntry.from_dict(d) for d in usda_data]
        self._index: dict[int, USDAEntry] = {e.fdc_id: e for e in self._entries}

    def search(self, query: str) -> list[USDAEntry]:
        q = query.lower()
        results = []
        for entry in self._entries:
            if q in entry.description.lower() or q in entry.description_zh:
                results.append(entry)
        return results[:20]

    def get_nutrition(self, fdc_id: int) -> list[NutritionFact]:
        entry = self._index.get(fdc_id)
        return entry.nutrients if entry else []

    def get_entry(self, fdc_id: int) -> USDAEntry | None:
        return self._index.get(fdc_id)

    def get_all(self) -> list[USDAEntry]:
        return self._entries
