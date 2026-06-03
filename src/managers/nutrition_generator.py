# src/managers/nutrition_generator.py
"""为已匹配 USDA 的食材生成营养信息，包含 NRV/DV 百分比。"""
from __future__ import annotations

import json
from pathlib import Path

from src.managers.nutrition_matcher import NutritionMatcher
from src.models.ingredient import Ingredient
from src.models.nutrition import NutritionFact, USDAEntry

# ---------------------------------------------------------------------------
# USDA 单位 → UnitManager 主单位名 映射
# ---------------------------------------------------------------------------
_UNIT_MAP: dict[str, str] = {
    "g": "克",
    "mg": "毫克",
    "µg": "微克",
    "ug": "微克",
    "kg": "千克",
    "kJ": "千焦",
    "kcal": "千卡",
    "IU": "IU",
}

# ---------------------------------------------------------------------------
# 单位换算表（用于 NRV% 计算时统一单位）
# ---------------------------------------------------------------------------
_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    # ("from_unit", "to_unit") -> factor
    ("kcal", "kJ"): 4.184,
    ("千卡", "千焦"): 4.184,
    ("g", "mg"): 1000.0,
    ("g", "µg"): 1_000_000.0,
    ("mg", "µg"): 1000.0,
    ("mg", "g"): 0.001,
    ("µg", "mg"): 0.001,
    ("µg", "g"): 0.000_001,
    ("克", "毫克"): 1000.0,
    ("克", "微克"): 1_000_000.0,
    ("毫克", "微克"): 1000.0,
    ("毫克", "克"): 0.001,
    ("微克", "毫克"): 0.001,
    ("微克", "克"): 0.000_001,
}

# ---------------------------------------------------------------------------
# 营养素别名映射：USDA 变体名 → NRV 参考表中的标准名
# ---------------------------------------------------------------------------
_NUTRIENT_ALIASES: dict[str, str] = {
    "Carbohydrate, by summation": "Carbohydrate, by difference",
    "Total fat (NLEA)": "Total lipid (fat)",
    "Folate, total": "Folate, DFE",
    "Folate, food": "Folate, DFE",
    "Folic acid": "Folate, DFE",
    "Energy (Atwater General Factors)": "Energy",
    "Energy (Atwater Specific Factors)": "Energy",
    "Sugars, total including NLEA": "Total Sugars",
    "Sugars, added": "Total Sugars",
    "Vitamin A, IU": "Vitamin A, RAE",
    "Total dietary fiber (AOAC 2011.25)": "Fiber, total dietary",
    "High Molecular Weight Dietary Fiber (HMWDF)": "Fiber, total dietary",
}

# NRV 参考数据路径
_NRV_REFERENCE_PATH = Path(__file__).resolve().parent.parent / "data" / "nrv_reference.json"


def _convert_unit(value: float, from_unit: str, to_unit: str) -> float | None:
    """将 *value* 从 *from_unit* 换算为 *to_unit*。

    如果无法换算（单位相同或无换算因子），返回 None。
    """
    if from_unit == to_unit:
        return value
    key = (from_unit, to_unit)
    factor = _UNIT_CONVERSIONS.get(key)
    if factor is not None:
        return value * factor
    return None


class NutritionGenerator:
    """为已匹配 USDA 的食材生成包含 NRV/DV 百分比的营养信息。"""

    def __init__(
        self,
        matcher: NutritionMatcher,
        unit_manager=None,
    ):
        self._matcher = matcher
        self._unit_manager = unit_manager
        self._nrv_data: dict = {}
        self._load_nrv_reference()

    # ------------------------------------------------------------------
    # 加载参考数据
    # ------------------------------------------------------------------

    def _load_nrv_reference(self) -> None:
        """加载 NRV/DV 参考数据。"""
        try:
            raw = json.loads(_NRV_REFERENCE_PATH.read_text(encoding="utf-8"))
            self._nrv_data = raw.get("standards", {})
        except (FileNotFoundError, json.JSONDecodeError) as exc:
            print(f"[NutritionGenerator] Warning: could not load NRV reference: {exc}")
            self._nrv_data = {}

    # ------------------------------------------------------------------
    # 单位标准化
    # ------------------------------------------------------------------

    def _normalize_unit(self, usda_unit: str) -> str:
        """将 USDA 单位映射为 UnitManager 的主单位名。

        优先查找 UnitManager 中是否有匹配；如果映射表中有对应关系，
        则使用映射后的名称。
        """
        # 先查映射表
        mapped = _UNIT_MAP.get(usda_unit)
        if mapped:
            # 如果 UnitManager 可用且存在该单位，确认使用映射名
            if self._unit_manager is not None:
                existing = self._unit_manager.get_by_name(mapped)
                if existing is not None:
                    return existing.name
            return mapped
        # 再查 UnitManager 的别名索引
        if self._unit_manager is not None:
            existing = self._unit_manager.get_by_name(usda_unit)
            if existing is not None:
                return existing.name
        return usda_unit

    # ------------------------------------------------------------------
    # 查找每日参考值
    # ------------------------------------------------------------------

    def _find_daily_value(
        self, nutrient_name: str
    ) -> tuple[float | None, str, str | None]:
        """查找营养素的每日参考值。

        Returns:
            (daily_value, standard_name, note)
            - 找到时: (dv_value, "中国GB标准" 或 "美国FDA标准", None)
            - 未找到时: (None, "无标准", "该营养素无对应的NRV/DV标准值")
        """
        # 先解析别名
        resolved_name = _NUTRIENT_ALIASES.get(nutrient_name, nutrient_name)

        # 优先查找中国 GB 标准
        gb_nutrients = self._nrv_data.get("中国GB标准", {}).get("nutrients", {})
        if resolved_name in gb_nutrients:
            entry = gb_nutrients[resolved_name]
            return entry["daily_value"], "中国GB标准", None

        # 再查找美国 FDA 标准
        fda_nutrients = self._nrv_data.get("美国FDA标准", {}).get("nutrients", {})
        if resolved_name in fda_nutrients:
            entry = fda_nutrients[resolved_name]
            return entry["daily_value"], "美国FDA标准", None

        return None, "无标准", "该营养素无对应的NRV/DV标准值"

    def _get_dv_unit(self, nutrient_name: str) -> str | None:
        """获取营养素 DV 参考值的单位。"""
        resolved_name = _NUTRIENT_ALIASES.get(nutrient_name, nutrient_name)

        for std_name in ("中国GB标准", "美国FDA标准"):
            std_nutrients = self._nrv_data.get(std_name, {}).get("nutrients", {})
            if resolved_name in std_nutrients:
                return std_nutrients[resolved_name].get("unit")
        return None

    # ------------------------------------------------------------------
    # NRV% 计算
    # ------------------------------------------------------------------

    def _calculate_nrv_pct(
        self,
        amount: float,
        daily_value: float,
        nutrient_unit: str,
        dv_unit: str | None,
    ) -> float:
        """计算 NRV 百分比，处理单位换算。

        Returns:
            NRV% 保留两位小数
        """
        if daily_value <= 0:
            return 0.0

        effective_amount = amount

        # 尝试单位换算
        if dv_unit and nutrient_unit != dv_unit:
            # 标准化单位后再比较
            norm_nutrient = self._normalize_unit(nutrient_unit)
            norm_dv = self._normalize_unit(dv_unit)

            if norm_nutrient != norm_dv:
                # 尝试换算
                converted = _convert_unit(amount, norm_nutrient, norm_dv)
                if converted is not None:
                    effective_amount = converted
                else:
                    # 无法换算，回退尝试原始单位换算
                    converted = _convert_unit(amount, nutrient_unit, dv_unit)
                    if converted is not None:
                        effective_amount = converted
                    else:
                        # kcal ↔ kJ 特殊处理
                        if (nutrient_unit in ("kcal", "千卡") and dv_unit in ("kJ", "千焦")):
                            effective_amount = amount * 4.184
                        elif (nutrient_unit in ("kJ", "千焦") and dv_unit in ("kcal", "千卡")):
                            effective_amount = amount / 4.184
                        else:
                            # 无法换算，不计算百分比
                            return 0.0

        return round((effective_amount / daily_value) * 100, 2)

    # ------------------------------------------------------------------
    # 核心生成
    # ------------------------------------------------------------------

    def generate_for_ingredient(self, ingredient: Ingredient) -> dict | None:
        """为单个已匹配食材生成营养信息。

        Returns:
            符合目标输出格式的字典，或 None（如果未匹配）。
        """
        if ingredient.usda_match_status != "matched" or ingredient.usda_id is None:
            return None

        entry = self._matcher.get_entry(ingredient.usda_id)
        if entry is None:
            return None

        nutrients_out: list[dict] = []
        for fact in entry.nutrients:
            daily_value, standard, note = self._find_daily_value(fact.name)

            # 标准化单位
            normalized_unit = self._normalize_unit(fact.unit)

            # 计算 NRV%
            if daily_value is not None:
                dv_unit = self._get_dv_unit(fact.name)
                nrv_pct = self._calculate_nrv_pct(
                    fact.amount, daily_value, fact.unit, dv_unit
                )
            else:
                nrv_pct = 0

            nutrient_dict: dict = {
                "name": fact.name_zh if fact.name_zh != fact.name else fact.name,
                "name_en": fact.name,
                "value": fact.amount,
                "unit": normalized_unit,
                "nrp_pct": nrv_pct,
                "standard": standard,
            }
            if note is not None:
                nutrient_dict["note"] = note

            nutrients_out.append(nutrient_dict)

        return {
            "usda_id": str(ingredient.usda_id),
            "ingredient_name": ingredient.name,
            "usda_name": entry.description,
            "nutrients": nutrients_out,
        }

    def generate_all(self, ingredients: list[Ingredient]) -> list[dict]:
        """为所有已匹配的食材生成营养信息。

        Returns:
            列表，仅包含成功生成的条目。
        """
        results: list[dict] = []
        matched_count = 0
        for ing in ingredients:
            result = self.generate_for_ingredient(ing)
            if result is not None:
                results.append(result)
                matched_count += 1
        print(
            f"[NutritionGenerator] 生成完毕: "
            f"{matched_count}/{len(ingredients)} 个食材已匹配并生成"
        )
        return results

    def save(self, file_manager, data: list[dict]) -> None:
        """通过 FileManager 保存到 out/nutritions.json。"""
        file_manager.save_nutritions(data)
