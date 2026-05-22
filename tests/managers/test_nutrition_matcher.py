# tests/managers/test_nutrition_matcher.py
from src.managers.nutrition_matcher import NutritionMatcher

SAMPLE_DATA = [
    {
        "fdc_id": 1001,
        "description": "Tomatoes, raw",
        "description_zh": "番茄，生",
        "nutrients": [
            {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"},
        ],
    },
    {
        "fdc_id": 1002,
        "description": "Potatoes, raw",
        "description_zh": "土豆，生",
        "nutrients": [],
    },
]

def test_search_by_chinese():
    matcher = NutritionMatcher(SAMPLE_DATA)
    results = matcher.search("番茄")
    assert len(results) == 1
    assert results[0].fdc_id == 1001

def test_search_by_english():
    matcher = NutritionMatcher(SAMPLE_DATA)
    results = matcher.search("tomato")
    assert len(results) == 1

def test_get_nutrition():
    matcher = NutritionMatcher(SAMPLE_DATA)
    nutrients = matcher.get_nutrition(1001)
    assert len(nutrients) == 1
    assert nutrients[0].name_zh == "热量"
