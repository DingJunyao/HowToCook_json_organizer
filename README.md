# HowToCook JSON Organizer

将 [HowToCook](https://github.com/Anduin2017/HowToCook) 仓库的 Markdown 菜谱整理为标准化 JSON 格式，输出到 [HowToCook_json](https://github.com/DingJunyao/HowToCook_json)。

## 功能

- **Markdown 解析** — 自动提取菜名、难度、分类、原料、步骤、备注，解析失败的部分标红留给你手动修正
- **菜谱编辑** — 结构化表单，支持三种原料数量模式（精确值 / 范围 / 模糊量如"适量"）
- **食材库管理** — 标准名 + 别名 + 分类，支持食材合并（自动更新所有关联 JSON）
- **USDA 营养匹配** — 食材级别匹配 USDA 数据库，中英文搜索，营养素中文翻译
- **三种工作模式** — 从 MD 新建、批量导入、编辑已有 JSON

## 安装

要求 Python 3.10+。

```bash
git clone https://github.com/DingJunyao/HowToCook_json_organizer.git
cd HowToCook_json_organizer
pip install -e .
```

开发模式（含测试）：

```bash
pip install -e ".[dev]"
```

## 使用

### 1. 准备仓库

分别克隆源仓库和输出仓库到本地：

```bash
git clone https://github.com/Anduin2017/HowToCook.git /path/to/HowToCook
git clone https://github.com/DingJunyao/HowToCook_json.git /path/to/HowToCook_json
```

### 2. 启动工具

```bash
python -m src.ui.main
```

或安装后直接运行：

```bash
howtocook-organizer
```

### 3. 首次配置

启动后会自动弹出设置对话框，填入：

- **源仓库路径** — HowToCook 本地目录（只读）
- **输出仓库路径** — HowToCook_json 本地目录（读写）

后续可通过菜单 **工具 → 设置** 修改。

### 4. 工作流程

#### 模式 A：逐个处理新菜谱

1. 左栏目录树中双击一个 `.md` 文件
2. 工具自动解析并填入中间的编辑表单
3. 检查并修正解析结果（红色标记的行需要手动处理）
4. 点击 **保存**

#### 模式 B：批量导入

1. 点击工具栏的 **批量导入** 按钮
2. 工具自动解析所有 MD 文件，目录树中显示状态标记：
   - ✓ 已有 JSON 输出
   - ○ 解析成功，待编辑
   - ⚠ 解析失败，需手动处理
3. 逐个点击文件，在表单中检查修正后保存

#### 模式 C：编辑已有 JSON

1. 左栏切换到 **已输出** 标签页
2. 显示所有已有的 JSON 菜谱
3. 双击加载到表单中编辑
4. 保存覆盖原文件

### 5. 食材营养匹配（Tab 2）

1. 切换到 **食材营养管理** 标签页
2. 左栏选择一个未匹配的食材
3. 在中栏搜索 USDA 数据库（支持中英文关键词）
4. 从候选列表中选择匹配项，点击 **确认匹配**
5. 右栏显示该食材的营养成分详情

### 6. 食材合并

1. 在食材营养管理标签页，按住 Ctrl 多选两个食材
2. 点击 **合并选中食材**
3. 选择保留哪个作为标准名，预览合并结果
4. 确认后自动更新所有关联的 JSON 文件

## USDA 离线数据

USDA 营养数据需要预先准备：

1. 从 [USDA FoodData Central](https://fdc.nal.usda.gov/download-datasets.html) 下载 Foundation Foods 数据
2. 运行准备脚本：

```bash
python scripts/prepare_usda_data.py --input path/to/foundation_foods.json --output data/usda_nutrition.json
```

> 该脚本目前为占位实现，需根据实际下载的数据格式适配。

## 运行测试

```bash
pytest tests/ -v
```

## 项目结构

```
src/
├── models/          # 数据模型 (Recipe, Ingredient, Nutrition)
├── parsers/         # Markdown 解析器
├── managers/        # 文件管理、食材管理、营养匹配
└── ui/              # PySide6 界面
    ├── main.py           # 主窗口入口
    ├── recipe_tab.py     # 菜谱编辑标签页
    ├── nutrition_tab.py  # 食材营养管理标签页
    ├── source_panel.py   # 目录树 + Markdown 预览
    ├── recipe_form.py    # 菜谱编辑表单
    ├── ingredient_panel.py    # 食材库参考面板
    ├── nutrition_ingredient_list.py  # 食材列表
    ├── nutrition_panel.py     # USDA 匹配 + 营养详情
    ├── settings_dialog.py     # 配置对话框
    └── merge_dialog.py        # 食材合并对话框
scripts/
└── prepare_usda_data.py    # USDA 数据准备脚本
data/                       # 离线数据目录 (git 忽略)
```

## 数据格式

菜谱 JSON 示例：

```json
{
  "name": "可乐鸡翅",
  "source_file": "dishes/meat_dish/可乐鸡翅.md",
  "category": "荤菜",
  "difficulty": "medium",
  "servings": 1,
  "original_servings": 2,
  "ingredients": [
    {
      "ingredient_name": "可乐",
      "quantity": 1.0,
      "unit": "瓶",
      "is_optional": false
    }
  ],
  "steps": [
    {
      "step": 1,
      "content": "鸡翅中洗净，两面划刀。",
      "duration_minutes": null
    }
  ],
  "tips": ["可乐要没过鸡翅。"]
}
```
