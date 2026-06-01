# src/managers/nutrition_matcher.py
from __future__ import annotations
from src.models.nutrition import USDAEntry, NutritionFact


class NutritionMatcher:
    def __init__(self, usda_data: list[dict] | None = None):
        entries_data = usda_data or []
        self._entries: list[USDAEntry] = [USDAEntry.from_dict(d) for d in entries_data]
        self._index: dict[int, USDAEntry] = {e.fdc_id: e for e in self._entries}

    @property
    def has_data(self) -> bool:
        """Whether any USDA data has been loaded."""
        return len(self._entries) > 0

    def reload_from_file(self, file_path: str) -> bool:
        """从 JSON 文件重新加载数据（用于 USDA 数据构建完成后刷新）。

        Returns:
            True if data was loaded successfully.
        """
        import json
        from pathlib import Path

        p = Path(file_path)
        if not p.exists():
            return False
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(raw, list):
                return False
            self._entries = [USDAEntry.from_dict(d) for d in raw]
            self._index = {e.fdc_id: e for e in self._entries}
            return True
        except Exception:
            return False

    def search(self, query: str) -> list[USDAEntry]:
        """Search USDA entries by Chinese or English description.

        Matching priority (within each tier, entries with more nutrients rank higher):
        1. Exact Chinese description match (desc_zh == query)
        2. Chinese description prefix match (desc_zh starts with query)
        3. Chinese description substring match (query in desc_zh)
        4. English description substring match (query in desc_en)
        5. Fuzzy: each query word matches any word in combined descriptions

        Duplicate entries (same description + description_zh from different USDA
        data sources) are deduplicated, keeping the entry with the most nutrient data.
        """
        q = query.strip()
        if not q:
            return []
        # 单个 ASCII 字符搜索无意义，但单个汉字是有效搜索词
        if len(q) < 2 and q.isascii():
            return []

        q_lower = q.lower()
        words = q_lower.split()

        tier_exact: list[USDAEntry] = []    # 1. desc_zh == q
        tier_prefix: list[USDAEntry] = []   # 2. desc_zh.startswith(q)
        tier_substr: list[USDAEntry] = []   # 3. q in desc_zh
        tier_en: list[USDAEntry] = []       # 4. q in desc_en
        tier_fuzzy: list[USDAEntry] = []    # 5. all words match

        for entry in self._entries:
            desc_en = entry.description.lower()
            desc_zh = entry.description_zh.lower()

            if desc_zh == q_lower:
                tier_exact.append(entry)
            elif desc_zh.startswith(q_lower):
                tier_prefix.append(entry)
            elif q_lower in desc_zh:
                tier_substr.append(entry)
            elif q_lower in desc_en:
                tier_en.append(entry)
            elif len(words) > 1:
                combined = f"{desc_en} {desc_zh}"
                if all(w in combined for w in words):
                    tier_fuzzy.append(entry)

        # Sort each tier by nutrient count descending: prefer more complete data
        for tier in (tier_exact, tier_prefix, tier_substr, tier_en, tier_fuzzy):
            tier.sort(key=lambda e: len(e.nutrients), reverse=True)

        # Deduplicate across tiers by (description, description_zh) key:
        # the first occurrence (highest tier) wins
        seen: set[tuple[str, str]] = set()
        results: list[USDAEntry] = []
        for tier in (tier_exact, tier_prefix, tier_substr, tier_en, tier_fuzzy):
            for entry in tier:
                key = (entry.description.lower(), entry.description_zh.lower())
                if key not in seen:
                    seen.add(key)
                    results.append(entry)

        return results[:500]

    def get_nutrition(self, fdc_id: int) -> list[NutritionFact]:
        entry = self._index.get(fdc_id)
        return entry.nutrients if entry else []

    def get_entry(self, fdc_id: int) -> USDAEntry | None:
        return self._index.get(fdc_id)

    def get_all(self) -> list[USDAEntry]:
        return self._entries
