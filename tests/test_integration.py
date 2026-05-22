# tests/test_integration.py
"""Integration tests for the full workflow:
load MD -> parse -> edit -> save JSON -> ingredients update.
"""
import json
from pathlib import Path

import pytest

from src.managers.file_manager import FileManager
from src.managers.ingredient_manager import IngredientManager
from src.managers.nutrition_matcher import NutritionMatcher
from src.models.recipe import Recipe
from src.parsers.markdown_parser import MarkdownParser

# Re-use the same sample MD from test_markdown_parser.py
SAMPLE_MD = """# 可乐鸡翅的做法

预估烹饪难度：★★★☆☆

## 必备原料和工具

鸡翅中
可乐 1 瓶
生抽 2 勺
老抽 1 勺
生姜（3片）
葱 适量

## 计算

鸡翅中 500g（一人份）

## 操作

1. 鸡翅中洗净，两面划刀。
2. 冷水下锅焯水，捞出沥干。
3. 锅中少许油，放入鸡翅煎至两面金黄（约 5 分钟）。
4. 倒入可乐，加生抽、老抽，大火烧开。
5. 转小火炖煮 20 分钟。
6. 大火收汁即可。

## 附加内容

- 可乐要没过鸡翅。
"""

SAMPLE_RELATIVE_PATH = "dishes/meat_dish/可乐鸡翅.md"

SAMPLE_USDA_DATA = [
    {
        "fdc_id": 1001,
        "description": "Chicken wing, raw",
        "description_zh": "鸡翅，生",
        "nutrients": [
            {"name": "Energy", "name_zh": "热量", "amount": 203.0, "unit": "kcal"},
            {"name": "Protein", "name_zh": "蛋白质", "amount": 17.5, "unit": "g"},
        ],
    },
    {
        "fdc_id": 1002,
        "description": "Cola",
        "description_zh": "可乐",
        "nutrients": [
            {"name": "Energy", "name_zh": "热量", "amount": 42.0, "unit": "kcal"},
            {"name": "Sugars", "name_zh": "糖", "amount": 10.6, "unit": "g"},
        ],
    },
    {
        "fdc_id": 1003,
        "description": "Soy sauce",
        "description_zh": "酱油",
        "nutrients": [
            {"name": "Sodium", "name_zh": "钠", "amount": 5500.0, "unit": "mg"},
        ],
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_env(tmp_path):
    """Create a temp directory with source MD file and output dir."""
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (output / "out").mkdir()
    (output / "out" / "ingredients.json").write_text("{}", encoding="utf-8")

    # Write sample MD into the source tree
    md_path = source / SAMPLE_RELATIVE_PATH
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(SAMPLE_MD, encoding="utf-8")

    return source, output


# ---------------------------------------------------------------------------
# 1. Full parse -> save -> reload workflow
# ---------------------------------------------------------------------------


def test_full_parse_save_workflow(tmp_env):
    """End-to-end: create FileManager, parse MD, save JSON, reload, verify."""
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)

    # 1. Read MD from source
    md_text = fm.load_markdown(SAMPLE_RELATIVE_PATH)

    # 2. Parse with MarkdownParser
    parsed = MarkdownParser.parse(md_text, SAMPLE_RELATIVE_PATH)

    # 3. Verify parsed data has expected fields
    assert parsed["name"] == "可乐鸡翅"
    assert parsed["difficulty"] == "medium"
    assert parsed["category"] == "荤菜"
    assert len(parsed["ingredients"]) >= 5
    assert len(parsed["steps"]) >= 5
    assert len(parsed["tips"]) >= 1

    ingredient_names = [i["ingredient_name"] for i in parsed["ingredients"]]
    assert "可乐" in ingredient_names
    assert "生抽" in ingredient_names

    # 4. Save recipe via FileManager
    fm.save_recipe(SAMPLE_RELATIVE_PATH.replace(".md", ".json"), parsed)

    # 5. Load it back and verify it matches
    loaded = fm.load_recipe(SAMPLE_RELATIVE_PATH.replace(".md", ".json"))
    assert loaded["name"] == parsed["name"]
    assert loaded["difficulty"] == parsed["difficulty"]
    assert loaded["category"] == parsed["category"]
    assert len(loaded["ingredients"]) == len(parsed["ingredients"])
    assert loaded["steps"][0]["content"] == parsed["steps"][0]["content"]

    # 6. Build ingredients from parsed recipe and save ingredients.json
    ingredients_data = {}
    for ing in parsed["ingredients"]:
        name = ing["ingredient_name"]
        key = name.lower().replace(" ", "_")
        ingredients_data[key] = {
            "name": name,
            "aliases": [],
            "category": parsed["category"],
            "usda_id": None,
            "usda_match_status": "unmatched",
        }
    fm.save_ingredients(ingredients_data)

    # 7. Check ingredients.json was updated
    saved_ingredients = fm.load_ingredients()
    assert len(saved_ingredients) > 0
    assert "可乐" in [v["name"] for v in saved_ingredients.values()]

    # Verify the recipe JSON file actually exists on disk
    recipe_path = output / "out" / SAMPLE_RELATIVE_PATH.replace(".md", ".json")
    assert recipe_path.exists()
    disk_data = json.loads(recipe_path.read_text(encoding="utf-8"))
    assert disk_data["name"] == "可乐鸡翅"


# ---------------------------------------------------------------------------
# 2. IngredientManager integration with FileManager
# ---------------------------------------------------------------------------


def test_ingredient_manager_integration(tmp_env):
    """Add ingredients through IngredientManager, save via FileManager, reload."""
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)

    # Add ingredients through IngredientManager
    mgr = IngredientManager()
    mgr.add("可乐", aliases=["cola"], category="饮料")
    mgr.add("鸡翅中", aliases=["鸡翅"], category="肉类")
    mgr.add("生抽", aliases=["酱油", "soy sauce"], category="调料")

    # Verify lookup works
    assert mgr.get_by_name("可乐") is not None
    assert mgr.get_by_name("cola") is not None  # alias
    assert mgr.get_by_name("鸡翅") is not None  # alias

    # Convert to saveable dict and persist via FileManager
    ingredients_dict = {}
    for ing in mgr.get_all():
        ingredients_dict[ing.key] = ing.to_dict()
    fm.save_ingredients(ingredients_dict)

    # Load back from disk
    loaded = fm.load_ingredients()
    assert len(loaded) == 3
    assert "可乐" in loaded["可乐"]["name"]
    assert "鸡翅" in loaded["鸡翅中"]["aliases"]

    # Test merge: merge "酱油" (alias of 生抽) into a new "老抽" entry
    mgr.add("老抽", aliases=["dark soy sauce"], category="调料")
    # Merge 老抽 into 生抽
    mgr.merge(keep="生抽", remove="老抽")
    assert mgr.get_by_name("老抽") is None  # removed
    shengchou = mgr.get_by_name("生抽")
    assert "老抽" in shengchou.aliases
    assert "dark soy sauce" in shengchou.aliases

    # Save merged result and reload
    ingredients_dict2 = {}
    for ing in mgr.get_all():
        ingredients_dict2[ing.key] = ing.to_dict()
    fm.save_ingredients(ingredients_dict2)

    loaded2 = fm.load_ingredients()
    # After merge, should have 3 entries (可乐, 鸡翅中, 生抽) — not 4
    assert len(loaded2) == 3
    assert "老抽" in loaded2["生抽"]["aliases"]


# ---------------------------------------------------------------------------
# 3. NutritionMatcher integration
# ---------------------------------------------------------------------------


def test_nutrition_matcher_integration():
    """Create NutritionMatcher with sample data, search, get nutrition."""
    matcher = NutritionMatcher(SAMPLE_USDA_DATA)

    # Search by Chinese
    results = matcher.search("鸡翅")
    assert len(results) == 1
    assert results[0].fdc_id == 1001
    assert results[0].description_zh == "鸡翅，生"

    # Search by English
    results_en = matcher.search("cola")
    assert len(results_en) == 1
    assert results_en[0].fdc_id == 1002

    # Get nutrition by fdc_id
    nutrients = matcher.get_nutrition(1001)
    assert len(nutrients) == 2
    nutrient_names = [n.name_zh for n in nutrients]
    assert "热量" in nutrient_names
    assert "蛋白质" in nutrient_names

    # Get entry
    entry = matcher.get_entry(1002)
    assert entry is not None
    assert entry.description == "Cola"

    # Nonexistent fdc_id
    assert matcher.get_entry(9999) is None
    assert matcher.get_nutrition(9999) == []

    # Cross-check: get all entries
    all_entries = matcher.get_all()
    assert len(all_entries) == 3


# ---------------------------------------------------------------------------
# 4. Recipe model roundtrip
# ---------------------------------------------------------------------------


def test_recipe_model_roundtrip():
    """Create Recipe from dict, convert back to dict, verify lossless."""
    original_data = {
        "name": "可乐鸡翅",
        "source_file": SAMPLE_RELATIVE_PATH,
        "category": "荤菜",
        "difficulty": "medium",
        "total_time_minutes": None,
        "servings": 1,
        "images": [],
        "ingredients": [
            {
                "ingredient_name": "可乐",
                "quantity": 1.0,
                "unit": "瓶",
                "quantity_range": None,
                "is_optional": False,
                "note": "",
                "original_quantity": "可乐 1 瓶",
                "is_estimated": False,
            },
            {
                "ingredient_name": "生抽",
                "quantity": 2.0,
                "unit": "勺",
                "quantity_range": None,
                "is_optional": False,
                "note": "",
                "original_quantity": "生抽 2 勺",
                "is_estimated": False,
            },
        ],
        "steps": [
            {"step": 1, "content": "鸡翅中洗净，两面划刀。", "duration_minutes": None, "tips": ""},
            {"step": 2, "content": "冷水下锅焯水，捞出沥干。", "duration_minutes": None, "tips": ""},
            {
                "step": 3,
                "content": "锅中少许油，放入鸡翅煎至两面金黄（约 5 分钟）。",
                "duration_minutes": 5.0,
                "tips": "",
            },
        ],
        "tips": ["可乐要没过鸡翅。"],
    }

    # Forward: dict -> Recipe
    recipe = Recipe.from_dict(original_data)
    assert recipe.name == "可乐鸡翅"
    assert recipe.category == "荤菜"
    assert len(recipe.ingredients) == 2
    assert recipe.ingredients[0].ingredient_name == "可乐"
    assert recipe.ingredients[1].quantity == 2.0
    assert len(recipe.steps) == 3
    assert recipe.steps[2].duration_minutes == 5.0
    assert recipe.tips == ["可乐要没过鸡翅。"]

    # Reverse: Recipe -> dict
    result_dict = recipe.to_dict()

    # Verify roundtrip is lossless
    assert result_dict == original_data
