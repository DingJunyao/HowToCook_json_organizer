# src/parsers/markdown_parser.py
from __future__ import annotations
import re
from typing import Optional

CATEGORY_MAP = {
    "aquatic": "水产",
    "breakfast": "早餐",
    "condiment": "调料",
    "dessert": "甜品",
    "drink": "饮料",
    "meat_dish": "荤菜",
    "semi-finished": "半成品",
    "soup": "汤与粥",
    "staple": "主食",
    "vegetable_dish": "素菜",
}

DIFFICULTY_MAP = {1: "simple", 2: "easy", 3: "medium", 4: "hard", 5: "expert"}


class MarkdownParser:
    @staticmethod
    def _parse_servings(content: str) -> int:
        """Try to extract servings from patterns like （一人份）（二人份）."""
        m = re.search(r"（([一二三四五六七八九十]+)人份）", content)
        if m:
            chinese_to_int = {
                "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
                "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
            }
            return chinese_to_int.get(m.group(1), 1)
        return 1

    @staticmethod
    def parse(content: str, source_path: str = "") -> dict:
        lines = content.split("\n")
        name = MarkdownParser._parse_name(lines)
        difficulty = MarkdownParser._parse_difficulty(lines)
        category = MarkdownParser._parse_category(source_path)
        servings = MarkdownParser._parse_servings(content)
        ingredients = MarkdownParser._parse_ingredients(content)
        steps = MarkdownParser._parse_steps(content)
        tips = MarkdownParser._parse_tips(content)

        return {
            "name": name,
            "source_file": source_path,
            "category": category,
            "difficulty": difficulty,
            "total_time_minutes": None,
            "servings": servings,
            "images": [],
            "ingredients": ingredients,
            "steps": steps,
            "tips": tips,
        }

    @staticmethod
    def _parse_name(lines: list[str]) -> str:
        for line in lines:
            m = re.match(r"^#\s+(.+?)(?:的做法)?$", line.strip())
            if m:
                return m.group(1).strip()
        return ""

    @staticmethod
    def _parse_difficulty(lines: list[str]) -> str:
        for line in lines:
            m = re.search(r"难度[：:]\s*(★+)", line)
            if m:
                count = len(m.group(1))
                return DIFFICULTY_MAP.get(count, "")
        return ""

    @staticmethod
    def _parse_category(source_path: str) -> str:
        parts = source_path.replace("\\", "/").split("/")
        for part in parts:
            if part in CATEGORY_MAP:
                return CATEGORY_MAP[part]
        return ""

    @staticmethod
    def _get_section(content: str, header: str) -> str:
        sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
        for sec in sections:
            if sec.strip().startswith(header):
                body = sec[len(header):].strip()
                next_h2 = re.search(r"^##\s+", body, re.MULTILINE)
                if next_h2:
                    body = body[: next_h2.start()]
                return body
        return ""

    @staticmethod
    def _parse_ingredients(content: str) -> list[dict]:
        section = MarkdownParser._get_section(content, "必备原料和工具")
        if not section:
            return []
        ingredients = []
        for line in section.split("\n"):
            line = line.strip().lstrip("-•* ").strip()
            if not line or line.startswith("#"):
                continue
            parsed = MarkdownParser._parse_ingredient_line(line)
            ingredients.append(parsed)
        return ingredients

    @staticmethod
    def _parse_ingredient_line(line: str) -> dict:
        # Pattern 1: name（quantity unit）
        m = re.match(r"^(.+?)（(\d+(?:\.\d+)?)\s*(\S*?)）$", line)
        if m:
            return {
                "ingredient_name": m.group(1).strip(),
                "quantity": float(m.group(2)),
                "unit": m.group(3) or "",
                "quantity_range": None,
                "is_optional": False,
                "note": "",
                "original_quantity": line,
                "is_estimated": False,
            }

        # Pattern 2: name min-max unit
        m = re.match(
            r"^(.+?)\s+(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*(\S*)$", line
        )
        if m:
            return {
                "ingredient_name": m.group(1).strip(),
                "quantity": None,
                "unit": m.group(4) or "",
                "quantity_range": {"min": float(m.group(2)), "max": float(m.group(3))},
                "is_optional": False,
                "note": "",
                "original_quantity": line,
                "is_estimated": False,
            }

        # Pattern 3: name quantity unit
        m = re.match(r"^(.+?)\s+(\d+(?:\.\d+)?)\s*(\S*)$", line)
        if m and not m.group(1).strip().startswith("#"):
            return {
                "ingredient_name": m.group(1).strip(),
                "quantity": float(m.group(2)),
                "unit": m.group(3) or "",
                "quantity_range": None,
                "is_optional": False,
                "note": "",
                "original_quantity": line,
                "is_estimated": False,
            }

        # Pattern 4: name + fuzzy amount
        m = re.match(r"^(.+?)\s+(适量|少许|微量|若干)$", line)
        if m:
            return {
                "ingredient_name": m.group(1).strip(),
                "quantity": None,
                "unit": "",
                "quantity_range": None,
                "is_optional": False,
                "note": m.group(2),
                "original_quantity": line,
                "is_estimated": False,
            }

        # Fallback: just name
        return {
            "ingredient_name": line,
            "quantity": None,
            "unit": "",
            "quantity_range": None,
            "is_optional": False,
            "note": "",
            "original_quantity": line,
            "is_estimated": False,
        }

    @staticmethod
    def _parse_steps(content: str) -> list[dict]:
        section = MarkdownParser._get_section(content, "操作")
        if not section:
            return []
        steps = []
        idx = 1
        for line in section.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^\d+[.、．)\s]+(.+)$", line)
            text = m.group(1).strip() if m else line.lstrip("-* ").strip()
            if not text:
                continue
            duration = None
            dm = re.search(r"（约?\s*(\d+)\s*分钟?）", text)
            if dm:
                duration = float(dm.group(1))
            dm = re.search(r"(\d+)\s*分钟", text)
            if not duration and dm:
                duration = float(dm.group(1))
            steps.append(
                {
                    "step": idx,
                    "content": text,
                    "duration_minutes": duration,
                    "tips": "",
                }
            )
            idx += 1
        return steps

    @staticmethod
    def _parse_tips(content: str) -> list[str]:
        section = MarkdownParser._get_section(content, "附加内容")
        if not section:
            return []
        tips = []
        for line in section.split("\n"):
            line = line.strip().lstrip("-* ").strip()
            if line:
                tips.append(line)
        return tips
