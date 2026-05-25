# src/managers/file_manager.py
from __future__ import annotations

import json
from pathlib import Path


class FileManager:
    def __init__(self, source_dir: Path, output_dir: Path):
        self.source_dir = Path(source_dir)
        self.output_dir = Path(output_dir)

    def save_recipe(self, relative_path: str, data: dict) -> None:
        path = self.output_dir / "out" / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        # If the file already exists, merge to preserve field order
        if path.exists():
            try:
                existing = json.loads(path.read_text(encoding="utf-8"))
                merged = self._merge_preserve_order(existing, data)
                data = merged
            except Exception:
                pass  # fall through to plain save
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    @staticmethod
    def _merge_preserve_order(existing: dict, new: dict) -> dict:
        """Update `existing` in-place with values from `new`, preserving key order."""
        for key in existing:
            if key in new:
                existing[key] = new[key]
        # Add any new keys that weren't in existing (at the end)
        for key in new:
            if key not in existing:
                existing[key] = new[key]
        return existing

    def load_recipe(self, relative_path: str) -> dict:
        path = self.output_dir / "out" / relative_path
        return json.loads(path.read_text(encoding="utf-8"))

    def load_ingredients(self) -> dict:
        path = self.output_dir / "out" / "ingredients.json"
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def save_ingredients(self, data: dict) -> None:
        path = self.output_dir / "out" / "ingredients.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def list_source_files(self) -> list[Path]:
        dishes_dir = self.source_dir / "dishes"
        if not dishes_dir.exists():
            return []
        return sorted(p for p in dishes_dir.rglob("*.md") if p.is_file())

    def load_markdown(self, relative_path: str) -> str:
        path = self.source_dir / relative_path
        return path.read_text(encoding="utf-8")

    def list_output_recipes(self) -> list[Path]:
        out_dir = self.output_dir / "out"
        if not out_dir.exists():
            return []
        skip = {
            "ingredients.json",
            "nutritions.json",
            "ingredients_raw.json",
            "matched_ingredients.json",
        }
        return sorted(p for p in out_dir.glob("*.json") if p.name not in skip)

    def get_images_dir(self) -> Path:
        """返回 out/images 目录路径（不保证存在）。"""
        return self.output_dir / "out" / "images"
