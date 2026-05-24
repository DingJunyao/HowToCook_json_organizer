# src/managers/unit_manager.py
from __future__ import annotations

import json
from pathlib import Path

from src.models.unit import Unit, load_default_units


class UnitManager:
    def __init__(self):
        self._units: dict[str, Unit] = {}  # key -> Unit
        self._name_index: dict[str, str] = {}  # name/alias -> key

    def _load_defaults(self):
        """Load default common cooking units from external config."""
        for entry in load_default_units():
            name = entry["name"]
            key = name.lower().replace(" ", "_")
            aliases = entry.get("aliases", [])
            unit = Unit(key=key, name=name, aliases=aliases)
            self._units[key] = unit
        self._rebuild_index()

    def discover_from_recipes(self, recipe_files: list[Path]) -> set[str]:
        """Scan existing recipe JSON files and return all unique units found.

        Returns a set of unit strings extracted from recipe ingredients.
        """
        found: set[str] = set()
        for fp in recipe_files:
            if not fp.is_file():
                continue
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                for ing in data.get("ingredients", []):
                    unit = ing.get("unit", "")
                    if unit:
                        found.add(unit)
            except Exception:
                pass
        return found

    def add_discovered_units(self, units: set[str]) -> int:
        """Add units discovered from recipe files that don't already exist.

        Returns the number of newly added units.
        """
        added = 0
        for unit_name in sorted(units):
            existing = self.get_by_name(unit_name)
            if existing is None:
                self.add(unit_name)
                added += 1
        return added

    def normalize_aliases(self, recipe_files: list[Path],
                          unit_name: str) -> dict[str, str]:
        """Normalize all alias variants of a unit to its primary name across recipe files.

        For the given unit, find all its aliases and replace them with the primary name
        in all recipe JSON files.

        Returns:
            Mapping of old_name -> new_name for all aliases that were normalized.
        """
        unit = self.get_by_name(unit_name)
        if unit is None:
            return {}

        replacements = {}
        for alias in unit.aliases:
            if alias != unit.name:
                replacements[alias] = unit.name

        if not replacements:
            return {}

        self.update_all_recipes(recipe_files, replacements)
        return replacements

    def update_all_recipes(self, recipe_files: list[Path],
                           replacements: dict[str, str]) -> int:
        """Replace units across all recipe JSON files.

        Args:
            recipe_files: List of recipe JSON file paths.
            replacements: Mapping of old_unit -> new_unit.

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
                    old_unit = ing.get("unit", "")
                    if old_unit in replacements:
                        ing["unit"] = replacements[old_unit]
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

    def add(self, name: str, aliases: list[str] | None = None) -> Unit:
        """Add a new unit. Returns the created Unit."""
        key = name.lower().replace(" ", "_")
        if key in self._units:
            return self._units[key]
        aliases = aliases or []
        unit = Unit(key=key, name=name, aliases=aliases)
        self._units[key] = unit
        self._rebuild_index()
        return unit

    def get_by_name(self, name: str) -> Unit | None:
        """Look up a unit by name or alias."""
        key = self._name_index.get(name)
        if key:
            return self._units.get(key)
        return None

    def get_all(self) -> list[Unit]:
        return list(self._units.values())

    def get_display_names(self) -> list[str]:
        """Return all names + aliases sorted, for dropdown population."""
        names = []
        for unit in self._units.values():
            names.append(unit.name)
        return sorted(names, key=lambda s: s.lower())

    def update(self, key: str, name: str | None = None,
               aliases: list[str] | None = None) -> None:
        unit = self._units.get(key)
        if unit is None:
            return
        if name is not None:
            unit.name = name
            new_key = name.lower().replace(" ", "_")
            if new_key != key:
                del self._units[key]
                unit.key = new_key
                self._units[new_key] = unit
        if aliases is not None:
            unit.aliases = aliases
        self._rebuild_index()

    def remove(self, key: str) -> None:
        if key in self._units:
            del self._units[key]
            self._rebuild_index()

    def merge(self, keep_name: str, remove_name: str) -> None:
        """Merge remove unit into keep unit, combining aliases."""
        keep_key = self._name_index.get(keep_name)
        remove_key = self._name_index.get(remove_name)
        if not keep_key or not remove_key or keep_key == remove_key:
            return
        keep_unit = self._units[keep_key]
        remove_unit = self._units[remove_key]
        all_aliases = set(keep_unit.aliases) | set(remove_unit.aliases)
        all_aliases.discard(keep_unit.name)
        all_aliases.add(remove_unit.name)
        for a in remove_unit.aliases:
            all_aliases.add(a)
        keep_unit.aliases = sorted(all_aliases)
        del self._units[remove_key]
        self._rebuild_index()

    def rename_in_all(self, old_name: str, new_name: str) -> int:
        """Rename a unit. Returns number of display names changed."""
        unit = self.get_by_name(old_name)
        if unit is None:
            return 0
        if unit.name == old_name:
            old_key = unit.key
            unit.name = new_name
            unit.key = new_name.lower().replace(" ", "_")
            if unit.key != old_key:
                del self._units[old_key]
                self._units[unit.key] = unit
        else:
            # old_name is an alias
            if old_name in unit.aliases:
                unit.aliases.remove(old_name)
            if new_name not in unit.aliases and new_name != unit.name:
                unit.aliases.append(new_name)
        self._rebuild_index()
        return 1

    def _rebuild_index(self):
        self._name_index.clear()
        for key, unit in self._units.items():
            self._name_index[unit.name] = key
            for alias in unit.aliases:
                self._name_index[alias] = key

    def load_from_list(self, units_data: list[dict]) -> None:
        """Load units from a persisted list, merging with defaults."""
        for item in units_data:
            name = item.get("name", "")
            if not name:
                continue
            aliases = item.get("aliases", [])
            existing = self.get_by_name(name)
            if existing is None:
                self.add(name, aliases)
            else:
                # Merge aliases
                merged = set(existing.aliases) | set(aliases)
                existing.aliases = sorted(merged)
        self._rebuild_index()

    def to_list(self) -> list[dict]:
        """Serialize to list of dicts for JSON persistence."""
        return [unit.to_dict() for unit in self._units.values()]
