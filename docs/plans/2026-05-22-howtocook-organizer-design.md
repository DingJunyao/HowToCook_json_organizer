# HowToCook JSON Organizer 设计文档

## 概述

桌面工具，辅助将 HowToCook 仓库的 Markdown 菜谱手动整理为 JSON 格式，输出到 HowToCook_json 仓库。包含食材库管理和 USDA 营养素匹配功能。

## 技术栈

- Python 3.10+
- PySide6
- 本地文件存储为主（JSON 文件直接读写仓库目录）
- 不自动 git commit，手动控制提交

## 整体架构

```
HowToCook 仓库 (MD)  →  MarkdownParser  →  编辑界面  →  JSON 文件输出
                                                  ↕
                                          食材库 (ingredients.json)
                                                  ↕
                                          USDA 离线数据集 → 营养匹配
```

## 界面设计

### 两个主 Tab

#### Tab 1 — 菜谱编辑（固定三栏布局）

**左栏 — 数据源（1/3）：**
- 源仓库 `dishes/` 目录树，按分类文件夹组织
- 已处理的文件标记 ✓
- 双击加载 Markdown 预览 + 触发解析

**中栏 — 编辑区（1/3）：**
- 菜谱名称
- 难度（simple/easy/medium/hard/expert）
- 分类（荤菜/素菜/水产/早餐/主食/汤与粥/调料/甜品/饮料/半成品）
- 份数
- 原料列表：每项包含名称（带下拉补全）、数量（确定值/范围/模糊量）、单位、是否可选、备注
- 步骤列表：每项包含序号、描述、用时、备注
- 图片路径
- 全局备注

**右栏 — 参考区（1/3）：**
- 食材库搜索和浏览
- 按分类折叠显示
- 查看已有食材的别名、匹配状态

#### Tab 2 — 食材营养管理（固定三栏布局）

**左栏 — 食材列表：**
- 按分类分组显示
- 匹配状态标识（✓ 已匹配 / ○ 未匹配）
- 筛选：全部 / 已匹配 / 未匹配
- 搜索框实时过滤

**中栏 — 食材详情 + 匹配操作：**
- 标准名、别名列表、分类
- 已匹配：显示当前 USDA 条目，可更换
- 未匹配：显示 USDA 搜索入口
- 输入关键词模糊搜索离线数据集（英文 + 中文翻译名）
- 候选列表点击选中即匹配

**右栏 — 营养素详情：**
- 选中 USDA 条目的营养成分表（中文翻译）
- 主要指标：热量、蛋白质、脂肪、碳水化合物、膳食纤维、钠等
- 数据来源标注（每100g为基准）

## 核心模块

### 1. MarkdownParser — Markdown 解析引擎

按段落解析，字段映射：

| 字段 | 来源 | 解析方式 |
|------|------|----------|
| 名称 | `# XXX的做法` 或 `# XXX` | 正则提取标题 |
| 难度 | `预估烹饪难度：★★★☆☆` | 数星号个数映射 |
| 分类 | 文件所在目录 | 目录名映射表 |
| 原料 | `## 必备原料和工具` 段落 | 逐行正则匹配 |
| 步骤 | `## 操作` 段落 | 按序号或换行拆分 |
| 备注 | `## 附加内容` 段落 | 整段收集 |

**原料解析策略：** 按正则模式逐个尝试匹配常见格式：
- `番茄 2 个` — 名称 + 数量 + 单位
- `盐 适量` — 名称 + 模糊量
- `生抽 1-2 勺` — 名称 + 范围 + 单位
- `大蒜（3瓣）` — 名称 + 括号内数量

匹配不上的整行保留在 `original_quantity` 字段，编辑区标红提示手动处理。

### 2. RecipeEditor — 菜谱编辑表单

- 解析结果自动填入表单，逐字段可编辑
- 三种工作模式：逐个处理新 MD、批量导入后逐个修正、编辑已有 JSON
- 食材输入框带下拉补全，匹配标准名和别名
- 输入新食材名提示创建

### 3. IngredientManager — 食材库管理

**数据结构：**

```json
{
  "tomato": {
    "name": "番茄",
    "aliases": ["西红柿", "tomato"],
    "category": "蔬菜",
    "usda_id": null,
    "usda_match_status": "unmatched"
  }
}
```

**食材分类预设：** 蔬菜、肉类、水产、禽蛋、豆制品、主食/谷物、调料、饮品、干货、其他

**合并操作流程：**
1. 选中两个食材
2. 选择保留哪个作为标准名
3. 别名合并、分类取主食材的、USDA 匹配取有值的
4. 扫描所有菜谱 JSON，替换被合并食材名为标准名
5. 合并可撤销（操作日志）

**分类管理：** 按分类折叠显示，支持拖拽改分类，支持自定义分类。

### 4. NutritionMatcher — USDA 匹配

- 离线数据集：预筛选 500-800 条常用食材相关条目
- 包含字段：`fdc_id`、英文名、中文翻译名、营养成分（每100g）
- 营养成分中文翻译对照表
- 匹配结果写入 `ingredients.json` 的 `usda_id` 字段
- 营养数据写入 `nutritions.json`

### 5. FileManager — 文件管理

**首次启动配置：**
- 源仓库路径（HowToCook，只读）
- 输出仓库路径（HowToCook_json，读写）
- 配置保存至 `~/.howtocook_organizer/config.json`

**保存逻辑：**
- JSON 写入输出仓库对应路径
- 食材增删改自动同步 `ingredients.json`
- 不自动 git commit

## 输出 JSON 格式

菜谱 JSON 结构：

```json
{
  "name": "菜名",
  "source_file": "原始 markdown 文件路径",
  "category": "分类",
  "difficulty": "难度等级",
  "total_time_minutes": 0,
  "servings": 1,
  "original_servings": 1,
  "images": [],
  "ingredients": [
    {
      "ingredient_name": "食材名称",
      "quantity": 0,
      "unit": "单位",
      "quantity_range": { "min": 0, "max": 0 },
      "is_optional": false,
      "note": "",
      "original_quantity": "",
      "is_estimated": false
    }
  ],
  "steps": [
    {
      "step": 1,
      "content": "步骤描述",
      "duration_minutes": 0,
      "tips": ""
    }
  ],
  "tips": []
}
```
