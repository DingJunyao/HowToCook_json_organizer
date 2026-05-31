"""
从 USDA FoodData Central 下载并准备离线营养数据集。

需要先从 https://fdc.nal.usda.gov/download-datasets.html 下载 Foundation Foods 数据。

用法:
    python scripts/prepare_usda_data.py --input FoundationFoods.json --output data/usda_nutrition_raw.json

输出格式:
    [
      {
        "fdc_id": 12345,
        "description": "Tomatoes, raw",
        "description_zh": "",
        "nutrients": [
          {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"}
        ]
      }
    ]
"""
import json
import argparse
from pathlib import Path

# ---------------------------------------------------------------------------
# 营养素中英文对照表（全量覆盖）
# ---------------------------------------------------------------------------
NUTRIENT_TRANSLATIONS: dict[str, str] = {
    # 宏量营养素
    "Energy": "热量",
    "Protein": "蛋白质",
    "Total lipid (fat)": "脂肪",
    "Carbohydrate, by difference": "碳水化合物",
    "Fiber, total dietary": "膳食纤维",
    "Sugars, total including NLEA": "糖",
    "Sugars, added": "添加糖",
    "Water": "水分",
    "Ash": "灰分",
    "Alcohol, ethyl": "酒精",

    # 脂肪酸
    "Fatty acids, total saturated": "饱和脂肪酸",
    "Fatty acids, total monounsaturated": "单不饱和脂肪酸",
    "Fatty acids, total polyunsaturated": "多不饱和脂肪酸",
    "Fatty acids, total trans": "反式脂肪酸",
    "Fatty acids, total trans-monoenoic": "反式单烯脂肪酸",
    "Fatty acids, total trans-polyenoic": "反式多烯脂肪酸",

    # 矿物质
    "Sodium, Na": "钠",
    "Cholesterol": "胆固醇",
    "Calcium, Ca": "钙",
    "Iron, Fe": "铁",
    "Potassium, K": "钾",
    "Phosphorus, P": "磷",
    "Magnesium, Mg": "镁",
    "Zinc, Zn": "锌",
    "Selenium, Se": "硒",
    "Copper, Cu": "铜",
    "Manganese, Mn": "锰",
    "Iodine, I": "碘",
    "Fluoride, F": "氟",
    "Chromium, Cr": "铬",
    "Molybdenum, Mo": "钼",
    "Cobalt, Co": "钴",
    "Nickel, Ni": "镍",
    "Silicon, Si": "硅",
    "Vanadium, V": "钒",
    "Boron, B": "硼",

    # 脂溶性维生素
    "Vitamin A, IU": "维生素A (IU)",
    "Vitamin A, RAE": "维生素A (RAE)",
    "Retinol": "视黄醇",
    "Carotene, beta": "β-胡萝卜素",
    "Carotene, alpha": "α-胡萝卜素",
    "Cryptoxanthin, beta": "β-隐黄素",
    "Lycopene": "番茄红素",
    "Lutein + zeaxanthin": "叶黄素+玉米黄质",
    "Vitamin D (D2 + D3), IU": "维生素D (IU)",
    "Vitamin D (D2 + D3)": "维生素D",
    "Vitamin D2 (ergocalciferol)": "维生素D2",
    "Vitamin D3 (cholecalciferol)": "维生素D3",
    "Vitamin E (alpha-tocopherol)": "维生素E",
    "Vitamin K (phylloquinone)": "维生素K",

    # 水溶性维生素
    "Thiamin": "维生素B1（硫胺素）",
    "Riboflavin": "维生素B2（核黄素）",
    "Niacin": "维生素B3（烟酸）",
    "Pantothenic acid": "维生素B5（泛酸）",
    "Vitamin B-6": "维生素B6",
    "Folate, total": "叶酸",
    "Folate, food": "食物叶酸",
    "Folic acid": "叶酸（合成）",
    "Folate, DFE": "叶酸 (DFE)",
    "Vitamin B-12": "维生素B12",
    "Vitamin C, total ascorbic acid": "维生素C",
    "Choline, total": "胆碱",
    "Betaine": "甜菜碱",
    "Biotin": "生物素",
    "Vitamin B-12, added": "维生素B12（添加）",
    "Vitamin E, added": "维生素E（添加）",
    "Vitamin K, added": "维生素K（添加）",
    "Vitamin B-12, added": "维生素B12（添加）",

    # 氨基酸
    "Tryptophan": "色氨酸",
    "Threonine": "苏氨酸",
    "Isoleucine": "异亮氨酸",
    "Leucine": "亮氨酸",
    "Lysine": "赖氨酸",
    "Methionine": "蛋氨酸",
    "Cystine": "胱氨酸",
    "Phenylalanine": "苯丙氨酸",
    "Tyrosine": "酪氨酸",
    "Valine": "缬氨酸",
    "Arginine": "精氨酸",
    "Histidine": "组氨酸",
    "Alanine": "丙氨酸",
    "Aspartic acid": "天冬氨酸",
    "Glutamic acid": "谷氨酸",
    "Glycine": "甘氨酸",
    "Proline": "脯氨酸",
    "Serine": "丝氨酸",
    "Hydroxyproline": "羟脯氨酸",

    # 其他
    "Caffeine": "咖啡因",
    "Theobromine": "可可碱",
    "Starch": "淀粉",
    "Sucrose": "蔗糖",
    "Glucose": "葡萄糖",
    "Fructose": "果糖",
    "Lactose": "乳糖",
    "Maltose": "麦芽糖",
    "Galactose": "半乳糖",
    "Maltodextrins": "麦芽糊精",

    # 补充：常见但之前遗漏的营养素
    "Sugars, Total": "总糖",
    "Total Sugars": "总糖",
    "Total dietary fiber (AOAC 2011.25)": "总膳食纤维 (AOAC 2011.25)",
    "High Molecular Weight Dietary Fiber (HMWDF)": "高分子量膳食纤维",
    "Low Molecular Weight Dietary Fiber (LMWDF)": "低分子量膳食纤维",
    "Fiber, insoluble": "不溶性膳食纤维",
    "Fiber, soluble": "可溶性膳食纤维",
    "Carbohydrate, by summation": "碳水化合物（求和法）",
    "Energy (Atwater General Factors)": "热量（Atwater 通用系数）",
    "Energy (Atwater Specific Factors)": "热量（Atwater 特定系数）",
    "Total fat (NLEA)": "总脂肪 (NLEA)",
    "Nitrogen": "氮",
    "Specific Gravity": "比重",
    "Sulfur, S": "硫",

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
    "Cysteine": "半胱氨酸",

    # 胆碱补充
    "Choline, free": "游离胆碱",
    "Choline, from glycerophosphocholine": "甘油磷胆碱来源胆碱",
    "Choline, from phosphocholine": "磷酸胆碱来源胆碱",
    "Choline, from phosphotidyl choline": "磷脂酰胆碱来源胆碱",
    "Choline, from sphingomyelin": "鞘磷脂来源胆碱",

    # 有机酸
    "Citric acid": "柠檬酸",
    "Malic acid": "苹果酸",
    "Oxalic acid": "草酸",
    "Pyruvic acid": "丙酮酸",
    "Quinic acid": "奎宁酸",

    # 植物固醇
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

    # 叶酸补充
    "Folate, food": "食物叶酸",
    "Folic acid": "叶酸（合成）",
    "10-Formyl folic acid (10HCOFA)": "10-甲酰叶酸",
    "5-Formyltetrahydrofolic acid (5-HCOH4": "5-甲酰四氢叶酸",
    "5-methyl tetrahydrofolate (5-MTHF)": "5-甲基四氢叶酸",
}


def _translate_fatty_acid(name: str) -> str | None:
    """为特定脂肪酸名称生成中文翻译。"""
    import re

    # 饱和脂肪酸 SFA XX:0
    m = re.match(r'^SFA (\d+:\d+)$', name)
    if m:
        return f"饱和脂肪酸 {m.group(1)}"

    # 单不饱和脂肪酸 MUFA XX:X ...
    m = re.match(r'^MUFA (\d+:\d+)\s*(.*)$', name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"单不饱和脂肪酸 {m.group(1)}{suffix}"

    # 多不饱和脂肪酸 PUFA XX:X ...
    m = re.match(r'^PUFA (\d+:\d+)\s*(.*)$', name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"多不饱和脂肪酸 {m.group(1)}{suffix}"

    # 反式脂肪酸 TFA XX:X ...
    m = re.match(r'^TFA (\d+:\d+)\s*(.*)$', name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"反式脂肪酸 {m.group(1)}{suffix}"

    # 反式二烯脂肪酸
    if "trans-dienoic" in name:
        return "反式二烯脂肪酸"

    return None


def _extract_nutrient(food_nutrient: dict) -> dict | None:
    """从 USDA foodNutrients 条目中提取营养素信息。

    USDA 下载文件格式有两种变体:
    1. 嵌套格式: {"nutrient": {"name": ..., "unitName": ...}, "amount": ...}
    2. 扁平格式: {"nutrientName": ..., "unitName": ..., "value": ...}
    """
    # 尝试嵌套格式（Foundation Foods 下载文件的标准格式）
    if "nutrient" in food_nutrient and isinstance(food_nutrient["nutrient"], dict):
        nt = food_nutrient["nutrient"]
        name = nt.get("name", "")
        unit = nt.get("unitName", "")
        amount = food_nutrient.get("amount")
    # 扁平格式（API 响应格式）
    else:
        name = food_nutrient.get("nutrientName", "")
        unit = food_nutrient.get("unitName", "")
        amount = food_nutrient.get("value") or food_nutrient.get("amount")

    if not name or amount is None:
        return None

    # 翻译优先级：对照表 → 脂肪酸模式匹配 → 英文原名
    name_zh = NUTRIENT_TRANSLATIONS.get(name)
    if name_zh is None:
        name_zh = _translate_fatty_acid(name)
    if name_zh is None:
        name_zh = name

    return {
        "name": name,
        "name_zh": name_zh,
        "amount": round(amount, 4) if isinstance(amount, float) else amount,
        "unit": unit,
    }


def prepare_dataset(input_path: str, output_path: str) -> None:
    """从 USDA 原始数据生成精简的离线数据集。"""
    raw_path = Path(input_path)
    if not raw_path.exists():
        raise FileNotFoundError(f"USDA 数据文件不存在: {raw_path}")

    print(f"读取 USDA 数据: {raw_path} ...")
    with open(raw_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # USDA 下载文件可能是数组，也可能是 {"FoundationFoods": [...]} 格式
    if isinstance(data, list):
        foods = data
    elif isinstance(data, dict):
        # 尝试常见的键名（支持所有 USDA 数据集类型）
        for key in (
            "FoundationFoods", "foundationFoods",
            "SRLegacyFoods", "srLegacyFoods",
            "SurveyFoods", "surveyFoods",
            "BrandedFoods", "brandedFoods",
            "foods",
        ):
            if key in data and isinstance(data[key], list):
                foods = data[key]
                break
        else:
            foods = []
    else:
        raise ValueError(f"无法识别的 USDA 数据格式: {type(data)}")

    print(f"共 {len(foods)} 条食物条目，开始处理...")

    results = []
    skipped = 0
    for i, food in enumerate(foods):
        # 提取基本信息
        fdc_id = food.get("fdcId") or food.get("fdc_id")
        description = food.get("description", "")
        if not fdc_id or not description:
            skipped += 1
            continue

        # 提取营养素
        raw_nutrients = food.get("foodNutrients", [])
        nutrients = []
        for fn in raw_nutrients:
            n = _extract_nutrient(fn)
            if n is not None:
                nutrients.append(n)

        results.append({
            "fdc_id": fdc_id,
            "description": description,
            "description_zh": "",
            "nutrients": nutrients,
        })

        # 进度报告
        if (i + 1) % 1000 == 0:
            print(f"  已处理 {i + 1}/{len(foods)} 条...")

    # 写入输出
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    # 统计报告
    total_nutrients = sum(len(r["nutrients"]) for r in results)
    translated_count = sum(
        1 for r in results for n in r["nutrients"]
        if n["name_zh"] != n["name"]
    )
    untranslated_nutrient_names = set()
    for r in results:
        for n in r["nutrients"]:
            if n["name_zh"] == n["name"]:
                untranslated_nutrient_names.add(n["name"])

    print(f"\n处理完成!")
    print(f"  输出文件: {out_path}")
    print(f"  食物条目: {len(results)} 条 (跳过 {skipped} 条)")
    print(f"  营养素记录: {total_nutrients} 条")
    print(f"  已翻译营养素: {translated_count} 条")
    print(f"  未翻译营养素名称 ({len(untranslated_nutrient_names)} 种):")
    for name in sorted(untranslated_nutrient_names):
        print(f"    - {name}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="从 USDA FoodData Central 原始数据生成精简的离线营养数据集"
    )
    parser.add_argument(
        "--input", required=True,
        help="USDA 原始 JSON 文件路径（Foundation Foods）"
    )
    parser.add_argument(
        "--output", default="data/usda_nutrition_raw.json",
        help="输出文件路径（默认: data/usda_nutrition_raw.json）"
    )
    args = parser.parse_args()
    prepare_dataset(args.input, args.output)
