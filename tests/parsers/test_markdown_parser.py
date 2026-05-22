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
