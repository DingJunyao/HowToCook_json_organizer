from __future__ import annotations
import json
from pathlib import Path

from src.models.ingredient import Ingredient


class IngredientManager:
    def __init__(self):
        self._ingredients: dict[str, Ingredient] = {}  # key -> Ingredient
        self._name_index: dict[str, str] = {}  # name/alias -> key

    def add(self, name: str, aliases: list[str] | None = None, category: str = "其他") -> Ingredient:
        aliases = aliases or []
        key = name.lower().replace(" ", "_")
        ing = Ingredient(key=key, name=name, aliases=aliases, category=category)
        self._ingredients[key] = ing
        self._rebuild_index()
        return ing

    def get_by_name(self, name: str) -> Ingredient | None:
        key = self._name_index.get(name)
        if key:
            return self._ingredients.get(key)
        return None

    def merge(self, keep: str, remove: str) -> None:
        keep_key = self._name_index.get(keep)
        remove_key = self._name_index.get(remove)
        if not keep_key or not remove_key:
            return
        keep_ing = self._ingredients[keep_key]
        remove_ing = self._ingredients[remove_key]
        all_aliases = set(keep_ing.aliases) | set(remove_ing.aliases)
        all_aliases.discard(keep_ing.name)
        all_aliases.add(remove_ing.name)
        for alias in remove_ing.aliases:
            all_aliases.add(alias)
        keep_ing.aliases = sorted(all_aliases)
        if keep_ing.usda_id is None and remove_ing.usda_id is not None:
            keep_ing.usda_id = remove_ing.usda_id
            keep_ing.usda_match_status = remove_ing.usda_match_status
        del self._ingredients[remove_key]
        self._rebuild_index()
        self._name_index.pop(remove, None)

    def search(self, query: str) -> list[Ingredient]:
        keywords = query.lower().split()
        if not keywords:
            return list(self._ingredients.values())
        results = []
        for ing in self._ingredients.values():
            name = ing.name.lower()
            aliases = [a.lower() for a in ing.aliases]
            if all(kw in name or any(kw in a for a in aliases) for kw in keywords):
                results.append(ing)
        return results

    def get_by_category(self, category: str) -> list[Ingredient]:
        return [ing for ing in self._ingredients.values() if ing.category == category]

    def get_all(self) -> list[Ingredient]:
        return list(self._ingredients.values())

    def update(self, key: str, name: str | None = None,
               aliases: list[str] | None = None, category: str | None = None) -> None:
        """Update an existing ingredient's fields and rebuild the index."""
        ing = self._ingredients.get(key)
        if ing is None:
            return
        if name is not None:
            ing.name = name
            new_key = name.lower().replace(" ", "_")
            if new_key != key:
                del self._ingredients[key]
                ing.key = new_key
                self._ingredients[new_key] = ing
        if aliases is not None:
            ing.aliases = aliases
        if category is not None:
            ing.category = category
        self._rebuild_index()

    def remove(self, key: str) -> None:
        """Remove an ingredient by key."""
        if key in self._ingredients:
            del self._ingredients[key]
            self._rebuild_index()

    def _rebuild_index(self):
        self._name_index.clear()
        for key, ing in self._ingredients.items():
            self._name_index[ing.name] = key
            for alias in ing.aliases:
                self._name_index[alias] = key

    def update_all_recipes(self, recipe_files: list[Path],
                           replacements: dict[str, str]) -> int:
        """Replace ingredient names across all recipe JSON files.

        Args:
            recipe_files: List of recipe JSON file paths.
            replacements: Mapping of old_name -> new_name.

        Returns:
            Number of files modified.
        """
        if not replacements:
            return 0

        modified_count = 0
        for fp in recipe_files:
            if not fp.is_file():
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                changed = False
                for ing in data.get("ingredients", []):
                    old_name = ing.get("ingredient_name", "")
                    if old_name in replacements:
                        ing["ingredient_name"] = replacements[old_name]
                        changed = True
                if changed:
                    fp.write_text(
                        json.dumps(data, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    modified_count += 1
            except Exception:
                pass
        return modified_count
