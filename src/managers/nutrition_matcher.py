# src/managers/nutrition_matcher.py
from __future__ import annotations
import re
from src.models.nutrition import USDAEntry, NutritionFact


# ---------------------------------------------------------------------------
# 营养素中英文翻译对照表（运行时补丁，用于修补已有数据中未翻译的营养素）
# ---------------------------------------------------------------------------
_NUTRIENT_ZH_PATCH: dict[str, str] = {
    # 生育酚和生育三烯酚（维生素E家族）
    "Tocopherol, beta": "β-生育酚",
    "Tocopherol, delta": "δ-生育酚",
    "Tocopherol, gamma": "γ-生育酚",
    "Tocotrienol, alpha": "α-生育三烯酚",
    "Tocotrienol, beta": "β-生育三烯酚",
    "Tocotrienol, delta": "δ-生育三烯酚",
    "Tocotrienol, gamma": "γ-生育三烯酚",
    # 维生素D补充
    "Vitamin D (D2 + D3), International Units": "维生素D (IU)",
    "Vitamin D4": "维生素D4",
    "25-hydroxycholecalciferol": "25-羟基维生素D3",
    "Vitamin K (Dihydrophylloquinone)": "维生素K（二氢叶绿醌）",
    "Vitamin K (Menaquinone-4)": "维生素K2（甲萘醌-4）",
    "Vitamin B-12, added": "维生素B12（添加）",
    "Vitamin E, added": "维生素E（添加）",
    # 类胡萝卜素补充
    "Carotene, gamma": "γ-胡萝卜素",
    "Cryptoxanthin, alpha": "α-隐黄素",
    "Lutein": "叶黄素",
    "Zeaxanthin": "玉米黄质",
    "cis-Lutein/Zeaxanthin": "顺式叶黄素/玉米黄质",
    "cis-Lycopene": "顺式番茄红素",
    "cis-beta-Carotene": "顺式β-胡萝卜素",
    "trans-Lycopene": "反式番茄红素",
    "trans-beta-Carotene": "反式β-胡萝卜素",
    "Phytoene": "八氢番茄红素",
    "Phytofluene": "六氢番茄红素",
    # 氨基酸补充
    "Hydroxyproline": "羟脯氨酸",
    # 胆碱补充
    "Choline, free": "游离胆碱",
    "Choline, from glycerophosphocholine": "甘油磷胆碱来源胆碱",
    "Choline, from phosphocholine": "磷酸胆碱来源胆碱",
    "Choline, from phosphotidyl choline": "磷脂酰胆碱来源胆碱",
    "Choline, from sphingomyelin": "鞘磷脂来源胆碱",
    # 膳食纤维补充
    "Total dietary fiber (AOAC 2011.25)": "总膳食纤维 (AOAC 2011.25)",
    "High Molecular Weight Dietary Fiber (HMWDF)": "高分子量膳食纤维",
    "Low Molecular Weight Dietary Fiber (LMWDF)": "低分子量膳食纤维",
    # 碳水化合物/能量补充
    "Carbohydrate, by summation": "碳水化合物（求和法）",
    "Energy (Atwater General Factors)": "热量（Atwater 通用系数）",
    "Energy (Atwater Specific Factors)": "热量（Atwater 特定系数）",
    "Total fat (NLEA)": "总脂肪 (NLEA)",
    "Specific Gravity": "比重",
    # 有机酸补充
    "Pyruvic acid": "丙酮酸",
    "Quinic acid": "奎宁酸",
    # 矿物质补充
    "Cobalt, Co": "钴",
    "Nickel, Ni": "镍",
    "Boron, B": "硼",
    # 植物甾醇
    "Beta-sitosterol": "β-谷固醇",
    "Beta-sitostanol": "β-谷烷醇",
    "Brassicasterol": "菜籽固醇",
    "Campestanol": "菜烷醇",
    "Campesterol": "菜固醇",
    "Stigmasterol": "豆固醇",
    "Stigmastadiene": "豆甾二烯",
    "Phytosterols, other": "其他植物固醇",
    "Delta-5-avenasterol": "Δ5-燕麦固醇",
    "Delta-7-Stigmastenol": "Δ7-豆甾烷醇",
    "Ergosta-5,7-dienol": "麦角甾-5,7-二烯醇",
    "Ergosta-7,22-dienol": "麦角甾-7,22-二烯醇",
    "Ergosta-7-enol": "麦角甾-7-烯醇",
    "Ergosterol": "麦角固醇",
    # 大豆异黄酮
    "Daidzein": "大豆苷元",
    "Daidzin": "大豆苷",
    "Genistein": "染料木黄酮",
    "Genistin": "染料木苷",
    "Glycitin": "黄豆黄苷",
    # 其他
    "Beta-glucan": "β-葡聚糖",
    "Glutathione": "谷胱甘肽",
    "Ergothioneine": "麦角硫因",
    "Raffinose": "棉子糖",
    "Stachyose": "水苏糖",
    "Verbascose": "毛蕊花糖",
    "Resistant starch": "抗性淀粉",
    "Galactose": "半乳糖",
    "Maltodextrins": "麦芽糊精",
    "Fatty acids, total trans-dienoic": "反式二烯脂肪酸",
    # 叶酸补充
    "10-Formyl folic acid (10HCOFA)": "10-甲酰叶酸",
    "5-Formyltetrahydrofolic acid (5-HCOH4": "5-甲酰四氢叶酸",
    "5-methyl tetrahydrofolate (5-MTHF)": "5-甲基四氢叶酸",
    # 额外矿物质
    "Silicon, Si": "硅",
    "Vanadium, V": "钒",
    # 糖补充
    "Sugars, added": "添加糖",
    "Alcohol, ethyl": "酒精",
    "Fatty acids, total trans-monoenoic": "反式单烯脂肪酸",
    "Fatty acids, total trans-polyenoic": "反式多烯脂肪酸",
}


def _translate_fatty_acid_zh(name: str) -> str | None:
    """为脂肪酸名称生成中文翻译。"""
    m = re.match(r"^SFA (\d+:\d+)$", name)
    if m:
        return f"饱和脂肪酸 {m.group(1)}"
    m = re.match(r"^MUFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"单不饱和脂肪酸 {m.group(1)}{suffix}"
    m = re.match(r"^PUFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"多不饱和脂肪酸 {m.group(1)}{suffix}"
    m = re.match(r"^TFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"反式脂肪酸 {m.group(1)}{suffix}"
    return None


def _patch_nutrient_translations(entries: list[USDAEntry]) -> None:
    """修补已有数据中未翻译的营养素名称（name_zh == name 的条目）。

    在加载 USDA 数据时调用，确保即使数据文件未重建，营养素名称也能显示为中文。
    """
    patched = 0
    for entry in entries:
        for fact in entry.nutrients:
            if fact.name_zh == fact.name:
                zh = _NUTRIENT_ZH_PATCH.get(fact.name)
                if zh is None:
                    zh = _translate_fatty_acid_zh(fact.name)
                if zh is not None:
                    fact.name_zh = zh
                    patched += 1
    return patched


class NutritionMatcher:
    def __init__(self, usda_data: list[dict] | None = None):
        entries_data = usda_data or []
        self._entries: list[USDAEntry] = [USDAEntry.from_dict(d) for d in entries_data]
        # 运行时修补未翻译的营养素名称
        _patch_nutrient_translations(self._entries)
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
            _patch_nutrient_translations(self._entries)
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
        tier_substr: list[USDAEntry] = []   # 3. all keywords in desc_zh
        tier_en: list[USDAEntry] = []       # 4. all keywords in desc_en
        tier_fuzzy: list[USDAEntry] = []    # 5. all keywords in combined

        for entry in self._entries:
            desc_en = entry.description.lower()
            desc_zh = entry.description_zh.lower()

            if desc_zh == q_lower:
                tier_exact.append(entry)
            elif desc_zh.startswith(q_lower):
                tier_prefix.append(entry)
            elif all(w in desc_zh for w in words):
                tier_substr.append(entry)
            elif all(w in desc_en for w in words):
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
