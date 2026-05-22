from src.models.ingredient import Ingredient


def test_ingredient_from_dict():
    data = {
        "name": "番茄",
        "aliases": ["西红柿", "tomato"],
        "category": "蔬菜",
        "usda_id": None,
        "usda_match_status": "unmatched",
    }
    ing = Ingredient.from_dict("tomato", data)
    assert ing.key == "tomato"
    assert ing.name == "番茄"
    assert "西红柿" in ing.aliases


def test_ingredient_to_dict():
    ing = Ingredient(key="tomato", name="番茄", aliases=["西红柿", "tomato"], category="蔬菜")
    d = ing.to_dict()
    assert d["name"] == "番茄"
    assert d["usda_id"] is None
