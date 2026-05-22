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
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

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
