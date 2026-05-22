# tests/managers/test_ingredient_manager.py
from src.managers.ingredient_manager import IngredientManager

def test_add_ingredient():
    mgr = IngredientManager()
    mgr.add("番茄", aliases=["西红柿", "tomato"], category="蔬菜")
    assert mgr.get_by_name("番茄") is not None
    assert mgr.get_by_name("西红柿") is not None  # alias lookup

def test_merge_ingredients():
    mgr = IngredientManager()
    mgr.add("番茄", aliases=["tomato"], category="蔬菜")
    mgr.add("西红柿", aliases=[], category="蔬菜")
    mgr.merge(keep="番茄", remove="西红柿")
    assert mgr.get_by_name("西红柿") is None
    ing = mgr.get_by_name("番茄")
    assert "西红柿" in ing.aliases

def test_search():
    mgr = IngredientManager()
    mgr.add("番茄", category="蔬菜")
    mgr.add("土豆", category="蔬菜")
    mgr.add("牛肉", category="肉类")
    results = mgr.search("牛")
    assert len(results) == 1
    assert results[0].name == "牛肉"

def test_get_by_category():
    mgr = IngredientManager()
    mgr.add("番茄", category="蔬菜")
    mgr.add("土豆", category="蔬菜")
    mgr.add("牛肉", category="肉类")
    vegs = mgr.get_by_category("蔬菜")
    assert len(vegs) == 2
