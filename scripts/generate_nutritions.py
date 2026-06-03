#!/usr/bin/env python3
"""
为 JSON 仓库中已匹配 USDA 的食材生成营养信息，输出到 out/nutritions.json。

用法:
    python scripts/generate_nutritions.py --output-dir /path/to/output_repo
    python scripts/generate_nutritions.py --output-dir /path/to/output_repo --usda-data /path/to/usda_nutrition.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.managers.nutrition_generator import NutritionGenerator


def main() -> None:
    parser = argparse.ArgumentParser(
        description="为已匹配 USDA 的食材生成营养信息 (out/nutritions.json)"
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="输出仓库的根目录路径（包含 out/ 子目录）",
    )
    parser.add_argument(
        "--usda-data",
        default=str(PROJECT_ROOT / "data" / "usda_nutrition.json"),
        help="USDA 营养数据 JSON 文件路径（默认: data/usda_nutrition.json）",
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    if not output_dir.is_dir():
        print(f"错误: 输出目录不存在: {output_dir}")
        sys.exit(1)

    # 1. 加载 USDA 营养数据
    usda_path = Path(args.usda_data)
    if not usda_path.exists():
        print(f"错误: USDA 数据文件不存在: {usda_path}")
        sys.exit(1)

    print(f"加载 USDA 数据: {usda_path}")
    usda_raw = json.loads(usda_path.read_text(encoding="utf-8"))
    if not isinstance(usda_raw, list):
        print("错误: USDA 数据文件格式不正确（应为 JSON 数组）")
        sys.exit(1)
    print(f"  已加载 {len(usda_raw)} 条 USDA 条目")

    # 2. 构建 FileManager 和加载食材
    fm = FileManager(source_dir=output_dir, output_dir=output_dir)
    ingredients_data = fm.load_ingredients()

    im = IngredientManager()
    if ingredients_data:
        items = (
            ingredients_data.values()
            if isinstance(ingredients_data, dict)
            else ingredients_data
        )
        for item in items:
            name = item.get("name") or item.get("ingredient_name", "")
            aliases = item.get("aliases", [])
            category = item.get("category", "其他")
            if name:
                ing = im.add(name=name, aliases=aliases, category=category)
                usda_id = item.get("usda_id")
                if usda_id is not None:
                    ing.usda_id = usda_id
                ing.usda_match_status = item.get("usda_match_status", "unmatched")

    all_ingredients = im.get_all()
    matched_count = sum(
        1 for ing in all_ingredients if ing.usda_match_status == "matched"
    )
    print(f"已加载 {len(all_ingredients)} 个食材，其中 {matched_count} 个已匹配 USDA")

    if matched_count == 0:
        print("没有已匹配的食材，跳过生成。")
        sys.exit(0)

    # 3. 构建 NutritionMatcher 和 NutritionGenerator
    nm = NutritionMatcher(usda_raw)
    generator = NutritionGenerator(nm)

    # 4. 生成营养信息
    print("正在生成营养信息...")
    results = generator.generate_all(all_ingredients)

    # 5. 保存
    generator.save(fm, results)
    output_path = output_dir / "out" / "nutritions.json"
    print(f"已保存到: {output_path}")
    print(f"共生成 {len(results)} 条营养信息")


if __name__ == "__main__":
    main()
