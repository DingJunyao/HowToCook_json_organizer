# 食材营养数据匹配 — 完善设计

**日期**: 2026-05-31
**状态**: 已确认

## 背景

项目已有完整的营养数据匹配 UI 和数据模型，但缺少：
1. USDA 数据的实际获取和提取方式
2. 食物描述的中文翻译机制
3. 离线营养数据文件

## 决策记录

| 决策项 | 选择 | 理由 |
|--------|------|------|
| 数据来源 | 离线数据包 + 预处理脚本 | 无运行时网络依赖 |
| 翻译方式 | Claude Code 直接翻译 | 已在 Claude Code 环境中工作，无需额外 API |
| 数据范围 | USDA Foundation Foods 全量 | 覆盖最全面 |
| 营养素覆盖 | 保留全部营养素数据 | 不丢失任何可用信息 |

## 三阶段流水线

```
USDA 原始数据 → [阶段1: 提取精简] → 中间 JSON → [阶段2: 翻译] → 最终 JSON
                  prepare_usda_data.py                Claude Code 直接处理
```

### 阶段 1: 数据提取 (`scripts/prepare_usda_data.py`)

**输入**: USDA Foundation Foods JSON 文件
**输出**: `data/usda_nutrition_raw.json`

处理逻辑：
1. 读取全量 JSON 文件
2. 提取每个条目的 `fdcId`、`description`、全部营养素数据
3. 用 `NUTRIENT_TRANSLATIONS` 映射表翻译已知的营养素名称
4. 未知营养素保留英文名作为 `name_zh`
5. `description_zh` 留空（由阶段 2 填充）

输出格式：
```json
[
  {
    "fdc_id": 323294,
    "description": "Tomatoes, raw, year round average",
    "description_zh": "",
    "nutrients": [
      {"name": "Energy", "name_zh": "热量", "amount": 18.0, "unit": "kcal"}
    ]
  }
]
```

### 阶段 2: 中文翻译

- 由 Claude Code 批量翻译所有食物描述
- 翻译规则：保留食材名 + 烹饪状态（生/熟/干等）
- 增量更新：已有翻译的条目跳过
- 输出最终 `data/usda_nutrition.json`

### 阶段 3: 集成

现有代码几乎无需改动，仅：
- 确认数据加载路径正确
- 空数据时 UI 优雅降级

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `scripts/prepare_usda_data.py` | 重写 | 完整的数据提取管道 |
| `data/usda_nutrition.json` | 新增 | 离线营养数据文件 |
| `src/managers/nutrition_matcher.py` | 微调 | 搜索优化（模糊匹配） |
| `src/ui/nutrition_panel.py` | 微调 | 无数据时空状态提示 |

## 数据来源

USDA FoodData Central Foundation Foods:
https://fdc.nal.usda.gov/download-datasets.html

预计数据量：8000+ 条目，最终 JSON 约 5-15MB。
