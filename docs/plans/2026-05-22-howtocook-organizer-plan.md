# HowToCook JSON Organizer 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 构建一个 PySide6 桌面工具，辅助将 Markdown 菜谱手动整理为标准化 JSON，包含食材库管理和 USDA 营养素匹配。

**Architecture:** Python 单体应用，核心业务逻辑与 UI 分离。数据模型用 dataclass，文件操作直接读写本地 JSON。Markdown 解析器独立于 UI，便于单独测试。UI 采用 PySide6 三栏固定布局，两个主 Tab。

**Tech Stack:** Python 3.10+, PySide6, pytest, dataclasses

---

## Task 1: 项目脚手架

**Files:**
- Create: `pyproject.toml`
- Create: `src/__init__.py`
- Create: `src/models/__init__.py`
- Create: `src/parsers/__init__.py`
- Create: `src/managers/__init__.py`
- Create: `src/ui/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

**Step 1: 创建项目结构**

```bash
mkdir -p src/models src/parsers src/managers src/ui tests
```

**Step 2: 编写 pyproject.toml**

```toml
[project]
name = "howtocook-organizer"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = [
    "PySide6>=6.6",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-qt>=4.2",
]

[project.scripts]
howtocook-organizer = "src.ui.main:main"

[tool.pytest.ini_options]
testpaths = ["tests"]
```

**Step 3: 验证环境**

Run: `pip install -e ".[dev]"`
Expected: 安装成功，无报错

**Step 4: 提交**

```bash
git add -A
git commit -m "feat: init project scaffold"
```

---

## Task 2: 数据模型定义

**Files:**
- Create: `src/models/recipe.py`
- Create: `src/models/ingredient.py`
- Create: `src/models/nutrition.py`
- Create: `tests/models/test_recipe.py`
- Create: `tests/models/test_ingredient.py`

**Step 1: 编写 Recipe 模型测试**

```python
# tests/models/test_recipe.py
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
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/models/test_recipe.py -v`
Expected: FAIL — 模块不存在

**Step 3: 编写 Recipe 数据模型**

```python
# src/models/recipe.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class IngredientEntry:
    ingredient_name: str
    quantity: Optional[float] = None
    unit: str = ""
    quantity_range: Optional[dict] = None  # {"min": float, "max": float}
    is_optional: bool = False
    note: str = ""
    original_quantity: str = ""
    is_estimated: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> IngredientEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "ingredient_name": self.ingredient_name,
            "quantity": self.quantity,
            "unit": self.unit,
            "quantity_range": self.quantity_range,
            "is_optional": self.is_optional,
            "note": self.note,
            "original_quantity": self.original_quantity,
            "is_estimated": self.is_estimated,
        }

@dataclass
class StepEntry:
    step: int
    content: str
    duration_minutes: Optional[float] = None
    tips: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> StepEntry:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "content": self.content,
            "duration_minutes": self.duration_minutes,
            "tips": self.tips,
        }

@dataclass
class Recipe:
    name: str
    source_file: str = ""
    category: str = ""
    difficulty: str = ""
    total_time_minutes: Optional[float] = None
    servings: int = 1
    original_servings: int = 1
    images: list[str] = field(default_factory=list)
    ingredients: list[IngredientEntry] = field(default_factory=list)
    steps: list[StepEntry] = field(default_factory=list)
    tips: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> Recipe:
        ingredients = [IngredientEntry.from_dict(i) for i in data.get("ingredients", [])]
        steps = [StepEntry.from_dict(s) for s in data.get("steps", [])]
        return cls(
            name=data.get("name", ""),
            source_file=data.get("source_file", ""),
            category=data.get("category", ""),
            difficulty=data.get("difficulty", ""),
            total_time_minutes=data.get("total_time_minutes"),
            servings=data.get("servings", 1),
            original_servings=data.get("original_servings", 1),
            images=data.get("images", []),
            ingredients=ingredients,
            steps=steps,
            tips=data.get("tips", []),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "source_file": self.source_file,
            "category": self.category,
            "difficulty": self.difficulty,
            "total_time_minutes": self.total_time_minutes,
            "servings": self.servings,
            "original_servings": self.original_servings,
            "images": self.images,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "steps": [s.to_dict() for s in self.steps],
            "tips": self.tips,
        }
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/models/test_recipe.py -v`
Expected: PASS

**Step 5: 编写 Ingredient 模型测试**

```python
# tests/models/test_ingredient.py
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
```

**Step 6: 编写 Ingredient 数据模型**

```python
# src/models/ingredient.py
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional

@dataclass
class Ingredient:
    key: str
    name: str
    aliases: list[str] = field(default_factory=list)
    category: str = "其他"
    usda_id: Optional[int] = None
    usda_match_status: str = "unmatched"  # unmatched, matched

    @classmethod
    def from_dict(cls, key: str, data: dict) -> Ingredient:
        return cls(
            key=key,
            name=data.get("name", key),
            aliases=data.get("aliases", []),
            category=data.get("category", "其他"),
            usda_id=data.get("usda_id"),
            usda_match_status=data.get("usda_match_status", "unmatched"),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "aliases": self.aliases,
            "category": self.category,
            "usda_id": self.usda_id,
            "usda_match_status": self.usda_match_status,
        }
```

**Step 7: 运行全部模型测试**

Run: `pytest tests/models/ -v`
Expected: 全部 PASS

**Step 8: 提交**

```bash
git add src/models/ tests/models/
git commit -m "feat: add data models for Recipe, Ingredient"
```

---

## Task 3: Nutrition 数据模型

**Files:**
- Create: `src/models/nutrition.py`
- Create: `tests/models/test_nutrition.py`

**Step 1: 编写测试**

```python
# tests/models/test_nutrition.py
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
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/models/test_nutrition.py -v`
Expected: FAIL

**Step 3: 编写 Nutrition 模型**

```python
# src/models/nutrition.py
from __future__ import annotations
from dataclasses import dataclass, field

@dataclass
class NutritionFact:
    name: str
    name_zh: str
    amount: float
    unit: str

    @classmethod
    def from_dict(cls, data: dict) -> NutritionFact:
        return cls(
            name=data["name"],
            name_zh=data.get("name_zh", data["name"]),
            amount=data["amount"],
            unit=data["unit"],
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "name_zh": self.name_zh,
            "amount": self.amount,
            "unit": self.unit,
        }

@dataclass
class USDAEntry:
    fdc_id: int
    description: str
    description_zh: str = ""
    nutrients: list[NutritionFact] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> USDAEntry:
        nutrients = [NutritionFact.from_dict(n) for n in data.get("nutrients", [])]
        return cls(
            fdc_id=data["fdc_id"],
            description=data["description"],
            description_zh=data.get("description_zh", ""),
            nutrients=nutrients,
        )

    def to_dict(self) -> dict:
        return {
            "fdc_id": self.fdc_id,
            "description": self.description,
            "description_zh": self.description_zh,
            "nutrients": [n.to_dict() for n in self.nutrients],
        }
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/models/test_nutrition.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/models/nutrition.py tests/models/test_nutrition.py
git commit -m "feat: add Nutrition data model"
```

---

## Task 4: FileManager — 配置与文件读写

**Files:**
- Create: `src/managers/file_manager.py`
- Create: `tests/managers/test_file_manager.py`

**Step 1: 编写测试**

```python
# tests/managers/test_file_manager.py
import json
import pytest
from pathlib import Path
from src.managers.file_manager import FileManager

@pytest.fixture
def tmp_env(tmp_path):
    source = tmp_path / "source"
    output = tmp_path / "output"
    source.mkdir()
    output.mkdir()
    (output / "ingredients.json").write_text("{}", encoding="utf-8")
    return source, output

def test_save_and_load_recipe(tmp_env):
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)
    recipe_data = {"name": "番茄炒蛋", "category": "素菜"}
    fm.save_recipe("vegetable_dish/番茄炒蛋.json", recipe_data)
    loaded = fm.load_recipe("vegetable_dish/番茄炒蛋.json")
    assert loaded["name"] == "番茄炒蛋"

def test_ingredients_roundtrip(tmp_env):
    source, output = tmp_env
    fm = FileManager(source_dir=source, output_dir=output)
    ingredients = {"tomato": {"name": "番茄", "aliases": ["西红柿"], "category": "蔬菜", "usda_id": None, "usda_match_status": "unmatched"}}
    fm.save_ingredients(ingredients)
    loaded = fm.load_ingredients()
    assert "tomato" in loaded

def test_list_source_files(tmp_env):
    source, output = tmp_env
    dishes = source / "dishes" / "vegetable_dish"
    dishes.mkdir(parents=True)
    (dishes / "番茄炒蛋.md").write_text("# 番茄炒蛋", encoding="utf-8")
    fm = FileManager(source_dir=source, output_dir=output)
    files = fm.list_source_files()
    assert len(files) == 1
    assert "番茄炒蛋.md" in files[0].name
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/managers/test_file_manager.py -v`
Expected: FAIL

**Step 3: 编写 FileManager**

```python
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
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

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
        return sorted(p for p in out_dir.glob("*.json") if p.name not in ("ingredients.json", "nutritions.json", "ingredients_raw.json", "matched_ingredients.json"))
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/managers/test_file_manager.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/managers/file_manager.py tests/managers/test_file_manager.py
git commit -m "feat: add FileManager for config and JSON read/write"
```

---

## Task 5: MarkdownParser — 解析引擎

**Files:**
- Create: `src/parsers/markdown_parser.py`
- Create: `tests/parsers/test_markdown_parser.py`
- Create: `tests/fixtures/`

**Step 1: 创建测试用 Markdown 文件**

```python
# tests/conftest.py 中添加（或创建 fixtures 目录后写入文件）
```

测试用 MD 内容：

```markdown
# 可乐鸡翅的做法

预估烹饪难度：★★★☆☆

## 必备原料和工具

鸡翅中
可乐 1 瓶
生抽 2 勺
老抽 1 勺
生姜（3片）
葱 适量

## 计算

鸡翅中 500g（一人份）

## 操作

1. 鸡翅中洗净，两面划刀。
2. 冷水下锅焯水，捞出沥干。
3. 锅中少许油，放入鸡翅煎至两面金黄（约 5 分钟）。
4. 倒入可乐，加生抽、老抽，大火烧开。
5. 转小火炖煮 20 分钟。
6. 大火收汁即可。

## 附加内容

- 可乐要没过鸡翅。
```

**Step 2: 编写解析器测试**

```python
# tests/parsers/test_markdown_parser.py
from src.parsers.markdown_parser import MarkdownParser

SAMPLE_MD = """# 可乐鸡翅的做法

预估烹饪难度：★★★☆☆

## 必备原料和工具

鸡翅中
可乐 1 瓶
生抽 2 勺
老抽 1 勺
生姜（3片）
葱 适量

## 计算

鸡翅中 500g（一人份）

## 操作

1. 鸡翅中洗净，两面划刀。
2. 冷水下锅焯水，捞出沥干。
3. 锅中少许油，放入鸡翅煎至两面金黄（约 5 分钟）。
4. 倒入可乐，加生抽、老抽，大火烧开。
5. 转小火炖煮 20 分钟。
6. 大火收汁即可。

## 附加内容

- 可乐要没过鸡翅。
"""

def test_parse_name():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    assert result["name"] == "可乐鸡翅"

def test_parse_difficulty():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    assert result["difficulty"] == "medium"

def test_parse_category():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    assert result["category"] == "荤菜"

def test_parse_ingredients():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    names = [i["ingredient_name"] for i in result["ingredients"]]
    assert "可乐" in names
    assert "生抽" in names
    # 检查数量解析
    cola = next(i for i in result["ingredients"] if i["ingredient_name"] == "可乐")
    assert cola["quantity"] == 1.0
    assert cola["unit"] == "瓶"

def test_parse_steps():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    assert len(result["steps"]) >= 5
    assert "洗净" in result["steps"][0]["content"]

def test_parse_tips():
    result = MarkdownParser.parse(SAMPLE_MD, "dishes/meat_dish/可乐鸡翅.md")
    assert len(result["tips"]) >= 1
```

**Step 3: 运行测试验证失败**

Run: `pytest tests/parsers/test_markdown_parser.py -v`
Expected: FAIL

**Step 4: 编写 MarkdownParser**

```python
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
    def parse(content: str, source_path: str = "") -> dict:
        lines = content.split("\n")
        name = MarkdownParser._parse_name(lines)
        difficulty = MarkdownParser._parse_difficulty(lines)
        category = MarkdownParser._parse_category(source_path)
        ingredients = MarkdownParser._parse_ingredients(content)
        steps = MarkdownParser._parse_steps(content)
        tips = MarkdownParser._parse_tips(content)

        return {
            "name": name,
            "source_file": source_path,
            "category": category,
            "difficulty": difficulty,
            "total_time_minutes": None,
            "servings": 1,
            "original_servings": 1,
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
        pattern = rf"^##\s+{re.escape(header)}\s*$"
        sections = re.split(r"^##\s+", content, flags=re.MULTILINE)
        for sec in sections:
            if sec.strip().startswith(header):
                # 去掉标题行
                body = sec[len(header):].strip()
                # 截取到下一个 ## 标题
                next_h2 = re.search(r"^##\s+", body, re.MULTILINE)
                if next_h2:
                    body = body[:next_h2.start()]
                return body
        return ""

    @staticmethod
    def _parse_ingredients(content: str) -> list[dict]:
        section = MarkdownParser._get_section(content, "必备原料和工具")
        if not section:
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
        # 模式1: 名称（数量单位） 如 "生姜（3片）"
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

        # 模式2: 名称 范围范围 单位 如 "生抽 1-2 勺"
        m = re.match(r"^(.+?)\s+(\d+(?:\.\d+)?)\s*[-–—]\s*(\d+(?:\.\d+)?)\s*(\S*)$", line)
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

        # 模式3: 名称 数量 单位 如 "可乐 1 瓶"
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

        # 模式4: 名称 模糊量 如 "葱 适量"
        m = re.match(r"^(.+?)\s+(适量|少许|少许|微量|少许|若干)$", line)
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

        # 兜底：只有名称
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
            # 去掉序号前缀
            m = re.match(r"^\d+[.、．)\s]+(.+)$", line)
            text = m.group(1).strip() if m else line.lstrip("-* ").strip()
            if not text:
                continue

            duration = None
            # 提取用时信息
            dm = re.search(r"（约?\s*(\d+)\s*分钟?）", text)
            if dm:
                duration = float(dm.group(1))
            dm = re.search(r"(\d+)\s*分钟", text)
            if not duration and dm:
                duration = float(dm.group(1))

            steps.append({
                "step": idx,
                "content": text,
                "duration_minutes": duration,
                "tips": "",
            })
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
```

**Step 5: 运行测试验证通过**

Run: `pytest tests/parsers/test_markdown_parser.py -v`
Expected: PASS

**Step 6: 提交**

```bash
git add src/parsers/ tests/parsers/
git commit -m "feat: add MarkdownParser with ingredient and step parsing"
```

---

## Task 6: IngredientManager — 食材库管理

**Files:**
- Create: `src/managers/ingredient_manager.py`
- Create: `tests/managers/test_ingredient_manager.py`

**Step 1: 编写测试**

```python
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
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/managers/test_ingredient_manager.py -v`
Expected: FAIL

**Step 3: 编写 IngredientManager**

```python
# src/managers/ingredient_manager.py
from __future__ import annotations
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

        # 合并别名
        all_aliases = set(keep_ing.aliases) | set(remove_ing.aliases)
        all_aliases.discard(keep_ing.name)
        all_aliases.add(remove_ing.name)
        for alias in remove_ing.aliases:
            all_aliases.add(alias)
        keep_ing.aliases = sorted(all_aliases)

        # USDA 匹配取有值的
        if keep_ing.usda_id is None and remove_ing.usda_id is not None:
            keep_ing.usda_id = remove_ing.usda_id
            keep_ing.usda_match_status = remove_ing.usda_match_status

        del self._ingredients[remove_key]
        self._rebuild_index()

    def search(self, query: str) -> list[Ingredient]:
        query = query.lower()
        results = []
        for ing in self._ingredients.values():
            if query in ing.name.lower() or any(query in a.lower() for a in ing.aliases):
                results.append(ing)
        return results

    def get_by_category(self, category: str) -> list[Ingredient]:
        return [ing for ing in self._ingredients.values() if ing.category == category]

    def get_all(self) -> list[Ingredient]:
        return list(self._ingredients.values())

    def _rebuild_index(self):
        self._name_index.clear()
        for key, ing in self._ingredients.items():
            self._name_index[ing.name] = key
            for alias in ing.aliases:
                self._name_index[alias] = key
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/managers/test_ingredient_manager.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/managers/ingredient_manager.py tests/managers/test_ingredient_manager.py
git commit -m "feat: add IngredientManager with alias, merge, search"
```

---

## Task 7: USDA 离线数据集准备

**Files:**
- Create: `scripts/prepare_usda_data.py`
- Create: `data/usda_nutrition.json`（运行脚本生成）

**Step 1: 编写数据准备脚本**

此脚本用于从 USDA FoodData Central 下载 Foundation Foods 数据，筛选中国菜常用食材，翻译后生成离线数据集。

```python
# scripts/prepare_usda_data.py
"""
从 USDA FoodData Central 下载并准备离线营养数据集。
需要先从 https://fdc.nal.usda.gov/download-datasets.html 下载 Foundation Foods 数据。
或者通过 API: https://api.nal.usda.gov/fdc/v1/foods/list
"""
import json
from pathlib import Path

# 中国菜常用食材的关键词列表（英文）
COMMON_FOODS = [
    "chicken", "pork", "beef", "tofu", "rice", "noodle",
    "tomato", "potato", "onion", "garlic", "ginger", "carrot",
    "cabbage", "mushroom", "egg", "soy sauce", "vinegar",
    "sesame oil", "pepper", "salt", "sugar", "cornstarch",
    "peanut", "shrimp", "fish", "lamb", "duck",
    "bok choy", "spinach", "celery", "cucumber", "eggplant",
    "green onion", "cilantro", "star anise", "cinnamon",
    "chili", "oyster sauce", "hoisin sauce", "rice wine",
    "starch", "flour", "bread", "milk", "butter",
    # ... 扩展到 500-800 条
]

# 营养素中英文对照
NUTRIENT_TRANSLATIONS = {
    "Energy": "热量",
    "Protein": "蛋白质",
    "Total lipid (fat)": "脂肪",
    "Carbohydrate, by difference": "碳水化合物",
    "Fiber, total dietary": "膳食纤维",
    "Sodium, Na": "钠",
    "Cholesterol": "胆固醇",
    "Calcium, Ca": "钙",
    "Iron, Fe": "铁",
    "Potassium, K": "钾",
    "Vitamin A, IU": "维生素A",
    "Vitamin C, total ascorbic acid": "维生素C",
}

def prepare_dataset(input_path: str, output_path: str):
    """从 USDA 原始数据生成精简的离线数据集"""
    # 此函数需要根据实际下载的 USDA 数据格式来适配
    # 输出格式:
    # [
    #   {
    #     "fdc_id": 12345,
    #     "description": "Tomatoes, raw",
    #     "description_zh": "番茄，生",
    #     "nutrients": [
    #       {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"}
    #     ]
    #   }
    # ]
    pass

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, help="USDA 原始 JSON 文件路径")
    parser.add_argument("--output", default="data/usda_nutrition.json")
    args = parser.parse_args()
    prepare_dataset(args.input, args.output)
```

**Step 2: 提交**

```bash
git add scripts/prepare_usda_data.py
git commit -m "feat: add USDA data preparation script (placeholder)"
```

> 注：此 Task 的实际数据准备需要手动下载 USDA 数据后执行脚本。脚本逻辑在后续根据实际数据格式完善。

---

## Task 8: NutritionMatcher — USDA 匹配逻辑

**Files:**
- Create: `src/managers/nutrition_matcher.py`
- Create: `tests/managers/test_nutrition_matcher.py`

**Step 1: 编写测试**

```python
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
```

**Step 2: 运行测试验证失败**

Run: `pytest tests/managers/test_nutrition_matcher.py -v`
Expected: FAIL

**Step 3: 编写 NutritionMatcher**

```python
# src/managers/nutrition_matcher.py
from __future__ import annotations
from src.models.nutrition import USDAEntry, NutritionFact

class NutritionMatcher:
    def __init__(self, usda_data: list[dict]):
        self._entries: list[USDAEntry] = [USDAEntry.from_dict(d) for d in usda_data]
        self._index: dict[int, USDAEntry] = {e.fdc_id: e for e in self._entries}

    def search(self, query: str) -> list[USDAEntry]:
        q = query.lower()
        results = []
        for entry in self._entries:
            if q in entry.description.lower() or q in entry.description_zh:
                results.append(entry)
        return results[:20]  # 限制候选数量

    def get_nutrition(self, fdc_id: int) -> list[NutritionFact]:
        entry = self._index.get(fdc_id)
        return entry.nutrients if entry else []

    def get_entry(self, fdc_id: int) -> USDAEntry | None:
        return self._index.get(fdc_id)

    def get_all(self) -> list[USDAEntry]:
        return self._entries
```

**Step 4: 运行测试验证通过**

Run: `pytest tests/managers/test_nutrition_matcher.py -v`
Expected: PASS

**Step 5: 提交**

```bash
git add src/managers/nutrition_matcher.py tests/managers/test_nutrition_matcher.py
git commit -m "feat: add NutritionMatcher for USDA search and lookup"
```

---

## Task 9: 主窗口框架 — 双 Tab 布局

**Files:**
- Create: `src/ui/main.py`
- Create: `src/ui/recipe_tab.py`
- Create: `src/ui/nutrition_tab.py`

**Step 1: 编写主窗口入口**

```python
# src/ui/main.py
import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMainWindow, QTabWidget, QStatusBar
from PySide6.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("HowToCook JSON Organizer")
        self.resize(1400, 900)

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # 延迟初始化各 Tab（需要配置后才能加载）
        self.recipe_tab = None
        self.nutrition_tab = None
        self._init_tabs()

    def _init_tabs(self):
        from src.ui.recipe_tab import RecipeTab
        from src.ui.nutrition_tab import NutritionTab

        self.recipe_tab = RecipeTab()
        self.nutrition_tab = NutritionTab()

        self.tabs.addTab(self.recipe_tab, "菜谱编辑")
        self.tabs.addTab(self.nutrition_tab, "食材营养管理")

        self.statusBar().showMessage("就绪")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

**Step 2: 编写 Tab 占位组件**

```python
# src/ui/recipe_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

class RecipeTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("左栏 - 数据源"))
        layout.addWidget(QLabel("中栏 - 编辑区"))
        layout.addWidget(QLabel("右栏 - 参考区"))
```

```python
# src/ui/nutrition_tab.py
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel

class NutritionTab(QWidget):
    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("左栏 - 食材列表"))
        layout.addWidget(QLabel("中栏 - 匹配操作"))
        layout.addWidget(QLabel("右栏 - 营养详情"))
```

**Step 3: 验证启动**

Run: `python -m src.ui.main`
Expected: 窗口正常显示，两个 Tab 可切换，三栏占位文字可见

**Step 4: 提交**

```bash
git add src/ui/
git commit -m "feat: add main window with dual-tab layout"
```

---

## Task 10: Tab 1 左栏 — 目录树与 Markdown 预览

**Files:**
- Modify: `src/ui/recipe_tab.py`

**Step 1: 实现左栏**

左栏包含：
- 源仓库目录树（QTreeWidget），只显示 `dishes/` 下的 `.md` 文件
- 已处理文件名旁边显示 ✓（检查输出目录是否有对应 JSON）
- 双击文件触发解析并加载到中栏
- 目录树下方是 Markdown 预览（QTextBrowser，只读渲染）

**Step 2: 验证**

Run: `python -m src.ui.main`
Expected: 左栏显示目录树，双击 MD 文件显示预览内容

**Step 3: 提交**

```bash
git commit -am "feat: add directory tree and markdown preview in recipe tab left panel"
```

---

## Task 11: Tab 1 中栏 — 菜谱编辑表单

**Files:**
- Modify: `src/ui/recipe_tab.py`
- Create: `src/ui/recipe_form.py`

**Step 1: 实现编辑表单**

中栏表单组件：
- 顶部：菜谱名称（QLineEdit）、难度（QComboBox）、分类（QComboBox）、份数（QSpinBox）
- 原料区域（QTableWidget 或自定义列表）：
  - 每行：食材名称（QComboBox 可编辑，带自动补全）、数量、单位、是否可选（QCheckBox）、备注
  - 数量支持三种模式：确定值 / 范围（min-max）/ 模糊量（如"适量"）
  - 添加/删除原料按钮
- 步骤区域（QTableWidget 或自定义列表）：
  - 每行：序号（自动）、描述（QTextEdit）、用时（QSpinBox 分钟）、备注
  - 添加/删除步骤按钮
- 底部：图片路径列表、全局备注、保存按钮

**Step 2: 验证**

Run: `python -m src.ui.main`
Expected: 中栏显示完整表单，解析结果自动填入，所有字段可编辑

**Step 3: 提交**

```bash
git commit -am "feat: add recipe editing form in center panel"
```

---

## Task 12: Tab 1 右栏 — 食材库参考

**Files:**
- Modify: `src/ui/recipe_tab.py`
- Create: `src/ui/ingredient_panel.py`

**Step 1: 实现参考面板**

右栏组件：
- 搜索框（QLineEdit + QCompleter）
- 食材列表按分类折叠（QTreeWidget，分类作为父节点）
- 点击食材显示详情：标准名、别名列表、分类、USDA 匹配状态
- 食材名输入时，中栏的食材名称输入框共享此数据源做自动补全

**Step 2: 验证**

Run: `python -m src.ui.main`
Expected: 右栏显示食材分类列表，搜索可用，点击显示详情

**Step 3: 提交**

```bash
git commit -am "feat: add ingredient reference panel in recipe tab right panel"
```

---

## Task 13: Tab 2 左栏 — 食材列表

**Files:**
- Modify: `src/ui/nutrition_tab.py`

**Step 1: 实现食材列表**

左栏组件：
- 筛选按钮组：全部 / 已匹配 / 未匹配
- 搜索框
- 食材列表（QTreeWidget），按分类分组
- 每项显示匹配状态图标
- 点击食材更新中栏

**Step 2: 验证**

Expected: 列表按分类分组，筛选和搜索可用

**Step 3: 提交**

```bash
git commit -am "feat: add ingredient list in nutrition tab left panel"
```

---

## Task 14: Tab 2 中栏 + 右栏 — 匹配操作与营养详情

**Files:**
- Modify: `src/ui/nutrition_tab.py`
- Create: `src/ui/nutrition_panel.py`

**Step 1: 实现匹配操作面板（中栏）**

- 食材详情：标准名、别名（可编辑）、分类（可修改）
- USDA 匹配区域：
  - 已匹配：显示当前匹配的 USDA 条目，可取消匹配或更换
  - 未匹配：搜索框 + 候选列表（QListWidget）
  - 候选列表显示英文名 + 中文名
  - 点击选中即确认匹配

**Step 2: 实现营养详情面板（右栏）**

- USDA 条目的营养成分表（QTableWidget）
- 列：营养素名称（中文）、含量、单位
- 数据来源标注

**Step 3: 验证**

Expected: 搜索 USDA 候选，点击匹配，右栏显示营养详情

**Step 4: 提交**

```bash
git commit -am "feat: add USDA matching and nutrition detail panels"
```

---

## Task 15: 食材合并操作 UI

**Files:**
- Modify: `src/ui/ingredient_panel.py`
- Modify: `src/ui/nutrition_tab.py`

**Step 1: 实现合并对话框**

- 在食材列表中支持多选（Ctrl+点击）
- 右键菜单或工具栏按钮："合并食材"
- 弹出对话框：选择保留的标准名，预览合并结果
- 确认后执行合并，更新所有关联的菜谱 JSON

**Step 2: 验证**

Expected: 选中两个食材，合并后别名合并，关联 JSON 更新

**Step 3: 提交**

```bash
git commit -am "feat: add ingredient merge UI with recipe JSON update"
```

---

## Task 16: 配置与首选项

**Files:**
- Create: `src/ui/settings_dialog.py`
- Modify: `src/ui/main.py`

**Step 1: 实现配置对话框**

- 首次启动自动弹出
- 设置项：源仓库路径、输出仓库路径
- 路径选择使用 QFileDialog
- 配置保存到 `~/.howtocook_organizer/config.json`

**Step 2: 集成到主窗口**

- 菜单栏添加 "设置" 入口
- 启动时检查配置，未配置则弹窗

**Step 3: 提交**

```bash
git commit -am "feat: add settings dialog with repo path configuration"
```

---

## Task 17: 保存与文件同步

**Files:**
- Modify: `src/ui/recipe_tab.py`
- Modify: `src/managers/file_manager.py`

**Step 1: 实现保存流程**

- 中栏保存按钮点击 → 从表单收集数据 → FileManager.save_recipe()
- 食材变更自动同步 ingredients.json
- 保存后更新目录树状态（✓ 标记）
- 未保存变更提醒（关闭时弹窗确认）

**Step 2: 验证**

Expected: 保存后 JSON 文件正确写入，食材库同步更新

**Step 3: 提交**

```bash
git commit -am "feat: add save workflow with ingredient sync"
```

---

## Task 18: 批量导入模式

**Files:**
- Modify: `src/ui/recipe_tab.py`

**Step 1: 实现批量导入**

- 工具栏按钮："批量导入"
- 选择源仓库目录后，自动解析所有 MD 文件
- 左栏目录树标记解析状态：✓ 已解析 / ○ 未解析 / ⚠ 解析失败
- 点击任意条目在中栏加载解析结果供修正

**Step 2: 提交**

```bash
git commit -am "feat: add batch import mode for all MD files"
```

---

## Task 19: 编辑已有 JSON 模式

**Files:**
- Modify: `src/ui/recipe_tab.py`

**Step 1: 支持加载已有 JSON**

- 左栏目录树同时显示源 MD 和输出 JSON
- 点击已有 JSON 文件直接加载到中栏编辑
- 关联显示对应的源 MD（左栏预览区）

**Step 2: 提交**

```bash
git commit -am "feat: add edit existing JSON mode"
```

---

## Task 20: 集成测试与打包

**Files:**
- Create: `tests/test_integration.py`

**Step 1: 编写集成测试**

测试完整流程：加载 MD → 解析 → 编辑表单 → 保存 JSON → 食材库更新

**Step 2: 运行全部测试**

Run: `pytest tests/ -v`
Expected: 全部 PASS

**Step 3: 最终提交**

```bash
git commit -am "feat: add integration tests"
```
