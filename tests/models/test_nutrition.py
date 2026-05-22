from src.models.nutrition import USDAEntry, NutritionFact


def test_usda_entry_from_dict():
    data = {
        "fdc_id": 12345,
        "description": "Tomatoes, raw",
        "description_zh": "番茄，生",
        "nutrients": [
            {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"},
            {"name": "Protein", "name_zh": "蛋白质", "amount": 0.88, "unit": "g"},
        ],
    }
    entry = USDAEntry.from_dict(data)
    assert entry.fdc_id == 12345
    assert entry.description_zh == "番茄，生"
    assert len(entry.nutrients) == 2
    assert entry.nutrients[0].name_zh == "热量"
