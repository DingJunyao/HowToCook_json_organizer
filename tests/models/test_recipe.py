from src.models.recipe import Recipe, IngredientEntry, StepEntry


def test_recipe_from_dict():
    data = {
        "name": "番茄炒蛋",
        "source_file": "dishes/vegetable_dish/番茄炒蛋.md",
        "category": "素菜",
        "difficulty": "easy",
        "total_time_minutes": 15,
        "servings": 1,
        "original_servings": 2,
        "images": [],
        "ingredients": [
            {
                "ingredient_name": "番茄",
                "quantity": 2.0,
                "unit": "个",
                "quantity_range": None,
                "is_optional": False,
                "note": "",
                "original_quantity": "",
                "is_estimated": False,
            }
        ],
        "steps": [
            {"step": 1, "content": "番茄切块", "duration_minutes": 3, "tips": ""}
        ],
        "tips": ["热锅冷油"],
    }
    recipe = Recipe.from_dict(data)
    assert recipe.name == "番茄炒蛋"
    assert recipe.difficulty == "easy"
    assert len(recipe.ingredients) == 1
    assert recipe.ingredients[0].ingredient_name == "番茄"
    assert len(recipe.steps) == 1


def test_recipe_to_dict():
    recipe = Recipe(
        name="番茄炒蛋",
        source_file="dishes/vegetable_dish/番茄炒蛋.md",
        category="素菜",
        difficulty="easy",
        total_time_minutes=15,
        servings=1,
        original_servings=2,
        images=[],
        ingredients=[
            IngredientEntry(ingredient_name="番茄", quantity=2.0, unit="个")
        ],
        steps=[StepEntry(step=1, content="番茄切块", duration_minutes=3)],
        tips=["热锅冷油"],
    )
    d = recipe.to_dict()
    assert d["name"] == "番茄炒蛋"
    assert d["ingredients"][0]["ingredient_name"] == "番茄"
