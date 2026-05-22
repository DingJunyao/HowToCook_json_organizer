"""
从 USDA FoodData Central 下载并准备离线营养数据集。
需要先从 https://fdc.nal.usda.gov/download-datasets.html 下载 Foundation Foods 数据。
或者通过 API: https://api.nal.usda.gov/fdc/v1/foods/list
"""
import json
from pathlib import Path

# 中国菜常用食材的关键词列表（英文）
COMMON_FOODS = [
    "chicken", "pork", "beef", "tofu", "rice", "noodle",
    "tomato", "potato", "onion", "garlic", "ginger", "carrot",
    "cabbage", "mushroom", "egg", "soy sauce", "vinegar",
    "sesame oil", "pepper", "salt", "sugar", "cornstarch",
    "peanut", "shrimp", "fish", "lamb", "duck",
    "bok choy", "spinach", "celery", "cucumber", "eggplant",
    "green onion", "cilantro", "star anise", "cinnamon",
    "chili", "oyster sauce", "hoisin sauce", "rice wine",
    "starch", "flour", "bread", "milk", "butter",
]

# 营养素中英文对照
NUTRIENT_TRANSLATIONS = {
    "Energy": "热量",
    "Protein": "蛋白质",
    "Total lipid (fat)": "脂肪",
    "Carbohydrate, by difference": "碳水化合物",
    "Fiber, total dietary": "膳食纤维",
    "Sodium, Na": "钠",
    "Cholesterol": "胆固醇",
    "Calcium, Ca": "钙",
    "Iron, Fe": "铁",
    "Potassium, K": "钾",
    "Vitamin A, IU": "维生素A",
    "Vitamin C, total ascorbic acid": "维生素C",
}


def prepare_dataset(input_path: str, output_path: str):
    """从 USDA 原始数据生成精简的离线数据集"""
    # This function needs to be adapted based on actual USDA data format
    # Output format:
    # [
    #   {
    #     "fdc_id": 12345,
    #     "description": "Tomatoes, raw",
    #     "description_zh": "番茄，生",
    #     "nutrients": [
    #       {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"}
    #     ]
    #   }
    # ]
    pass


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="USDA 原始 JSON 文件路径")
    parser.add_argument("--output", default="data/usda_nutrition.json")
    args = parser.parse_args()
    prepare_dataset(args.input, args.output)
