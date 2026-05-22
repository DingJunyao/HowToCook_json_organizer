# tests/managers/test_file_manager.py
import json
import pytest
from pathlib import Path
from src.managers.file_manager import FileManager


@pytest.fixture
def tmp_env(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (output / "out").mkdir()
    (output / "out" / "ingredients.json").write_text("{}", encoding="utf-8")
    return source, output


def test_save_and_load_recipe(tmp_env):
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)
    recipe_data = {"name": "番茄炒蛋", "category": "素菜"}
    fm.save_recipe("vegetable_dish/番茄炒蛋.json", recipe_data)
    loaded = fm.load_recipe("vegetable_dish/番茄炒蛋.json")
    assert loaded["name"] == "番茄炒蛋"


def test_ingredients_roundtrip(tmp_env):
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)
    ingredients = {
        "tomato": {
            "name": "番茄",
            "aliases": ["西红柿"],
            "category": "蔬菜",
            "usda_id": None,
            "usda_match_status": "unmatched",
        }
    }
    fm.save_ingredients(ingredients)
    loaded = fm.load_ingredients()
    assert "tomato" in loaded


def test_list_source_files(tmp_env):
    source, output = tmp_env
    dishes = source / "dishes" / "vegetable_dish"
    dishes.mkdir(parents=True)
    (dishes / "番茄炒蛋.md").write_text("# 番茄炒蛋", encoding="utf-8")
    fm = FileManager(source_dir=source, output_dir=output)
    files = fm.list_source_files()
    assert len(files) == 1
    assert "番茄炒蛋.md" in files[0].name
