#!/usr/bin/env python3
"""
一键构建 USDA 营养数据库：下载 → 提取 → AI翻译 → 合并。

用法:
    python scripts/build_usda_data.py              # 完整构建 (默认 Claude Code)
    python scripts/build_usda_data.py --skip-download  # 跳过下载
    python scripts/build_usda_data.py --skip-translate # 跳过翻译
    python scripts/build_usda_data.py --translate-only # 仅翻译未完成条目（不重新下载）

翻译提供者:
    claude-code   Claude Code CLI (默认，需安装)
    openai        OpenAI API 及兼容接口 (DeepSeek / Ollama / vLLM)
    anthropic     Anthropic API 直接调用
    deepl         DeepL 翻译平台 (EN→ZH 质量最佳)
    baidu         百度翻译 API (标准版免费)

示例:
    # Claude Code
    python scripts/build_usda_data.py

    # OpenAI
    python scripts/build_usda_data.py --translator openai --translator-api-key sk-xxx

    # Anthropic
    python scripts/build_usda_data.py --translator anthropic --translator-api-key sk-ant-xxx

    # DeepSeek (OpenAI 兼容)
    python scripts/build_usda_data.py --translator openai --translator-base-url https://api.deepseek.com/v1 --translator-api-key sk-xxx --translator-model deepseek-chat

    # DeepL
    python scripts/build_usda_data.py --translator deepl --translator-api-key xxx

    # 百度翻译 (标准版免费, api-key 格式: APP_ID:SECRET_KEY)
    python scripts/build_usda_data.py --translator baidu --translator-api-key APP_ID:SECRET_KEY

    # 环境变量
    set TRANSLATOR=openai
    set TRANSLATOR_API_KEY=sk-xxx
    set TRANSLATOR_BASE_URL=https://api.deepseek.com/v1
    set TRANSLATOR_MODEL=deepseek-chat
    python scripts/build_usda_data.py

    # 百度翻译也可通过环境变量配置
    set TRANSLATOR=baidu
    set TRANSLATOR_API_KEY=APP_ID:SECRET_KEY
    python scripts/build_usda_data.py --translate-only

    # 列出提供者
    python scripts/build_usda_data.py --list-translators

输出: data/usda_nutrition.json（~78 MB，紧凑 JSON）
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

# ============================================================================
# 配置
# ============================================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
USDA_DOWNLOADS_URL = "https://fdc.nal.usda.gov/download-datasets.html"

# USDA 各数据集的识别关键词 → 内部名称
DATASET_PATTERNS = [
    ("foundation", "foundation"),
    ("sr_legacy", "sr_legacy"),
    ("survey", "fndds"),
]

# 每批翻译的食物数量
BATCH_SIZE = 400

# Claude CLI 命令
CLAUDE_BIN = os.environ.get("CLAUDE_BIN", "claude")

# ============================================================================
# 营养素翻译（内联一份，保持脚本独立）
# ============================================================================

NUTRIENT_TRANSLATIONS: dict[str, str] = {
    "Energy": "热量",
    "Protein": "蛋白质",
    "Total lipid (fat)": "脂肪",
    "Carbohydrate, by difference": "碳水化合物",
    "Fiber, total dietary": "膳食纤维",
    "Sugars, total including NLEA": "糖",
    "Sugars, added": "添加糖",
    "Water": "水分",
    "Ash": "灰分",
    "Alcohol, ethyl": "酒精",
    "Fatty acids, total saturated": "饱和脂肪酸",
    "Fatty acids, total monounsaturated": "单不饱和脂肪酸",
    "Fatty acids, total polyunsaturated": "多不饱和脂肪酸",
    "Fatty acids, total trans": "反式脂肪酸",
    "Fatty acids, total trans-monoenoic": "反式单烯脂肪酸",
    "Fatty acids, total trans-polyenoic": "反式多烯脂肪酸",
    "Sodium, Na": "钠",
    "Cholesterol": "胆固醇",
    "Calcium, Ca": "钙",
    "Iron, Fe": "铁",
    "Potassium, K": "钾",
    "Phosphorus, P": "磷",
    "Magnesium, Mg": "镁",
    "Zinc, Zn": "锌",
    "Selenium, Se": "硒",
    "Copper, Cu": "铜",
    "Manganese, Mn": "锰",
    "Iodine, I": "碘",
    "Fluoride, F": "氟",
    "Chromium, Cr": "铬",
    "Molybdenum, Mo": "钼",
    "Vitamin A, IU": "维生素A (IU)",
    "Vitamin A, RAE": "维生素A (RAE)",
    "Retinol": "视黄醇",
    "Carotene, beta": "β-胡萝卜素",
    "Carotene, alpha": "α-胡萝卜素",
    "Cryptoxanthin, beta": "β-隐黄素",
    "Lycopene": "番茄红素",
    "Lutein + zeaxanthin": "叶黄素+玉米黄质",
    "Vitamin D (D2 + D3), IU": "维生素D (IU)",
    "Vitamin D (D2 + D3)": "维生素D",
    "Vitamin D2 (ergocalciferol)": "维生素D2",
    "Vitamin D3 (cholecalciferol)": "维生素D3",
    "Vitamin E (alpha-tocopherol)": "维生素E",
    "Vitamin K (phylloquinone)": "维生素K",
    "Thiamin": "维生素B1（硫胺素）",
    "Riboflavin": "维生素B2（核黄素）",
    "Niacin": "维生素B3（烟酸）",
    "Pantothenic acid": "维生素B5（泛酸）",
    "Vitamin B-6": "维生素B6",
    "Folate, total": "叶酸",
    "Folate, food": "食物叶酸",
    "Folic acid": "叶酸（合成）",
    "Folate, DFE": "叶酸 (DFE)",
    "Vitamin B-12": "维生素B12",
    "Vitamin C, total ascorbic acid": "维生素C",
    "Choline, total": "胆碱",
    "Betaine": "甜菜碱",
    "Biotin": "生物素",
    "Tryptophan": "色氨酸",
    "Threonine": "苏氨酸",
    "Isoleucine": "异亮氨酸",
    "Leucine": "亮氨酸",
    "Lysine": "赖氨酸",
    "Methionine": "蛋氨酸",
    "Cystine": "胱氨酸",
    "Phenylalanine": "苯丙氨酸",
    "Tyrosine": "酪氨酸",
    "Valine": "缬氨酸",
    "Arginine": "精氨酸",
    "Histidine": "组氨酸",
    "Alanine": "丙氨酸",
    "Aspartic acid": "天冬氨酸",
    "Glutamic acid": "谷氨酸",
    "Glycine": "甘氨酸",
    "Proline": "脯氨酸",
    "Serine": "丝氨酸",
    "Caffeine": "咖啡因",
    "Theobromine": "可可碱",
    "Starch": "淀粉",
    "Sucrose": "蔗糖",
    "Glucose": "葡萄糖",
    "Fructose": "果糖",
    "Lactose": "乳糖",
    "Maltose": "麦芽糖",
    "Sugars, Total": "总糖",
    "Total Sugars": "总糖",
    "Fiber, insoluble": "不溶性膳食纤维",
    "Fiber, soluble": "可溶性膳食纤维",
    "Cysteine": "半胱氨酸",
    "Nitrogen": "氮",
    "Sulfur, S": "硫",
    "Citric acid": "柠檬酸",
    "Malic acid": "苹果酸",
    "Oxalic acid": "草酸",
    "Phytosterols": "植物甾醇",

    # ---- 生育酚和生育三烯酚（维生素E家族） ----
    "Tocopherol, beta": "β-生育酚",
    "Tocopherol, delta": "δ-生育酚",
    "Tocopherol, gamma": "γ-生育酚",
    "Tocotrienol, alpha": "α-生育三烯酚",
    "Tocotrienol, beta": "β-生育三烯酚",
    "Tocotrienol, delta": "δ-生育三烯酚",
    "Tocotrienol, gamma": "γ-生育三烯酚",

    # ---- 维生素D补充 ----
    "Vitamin D (D2 + D3), International Units": "维生素D (IU)",
    "Vitamin D4": "维生素D4",
    "25-hydroxycholecalciferol": "25-羟基维生素D3",
    "Vitamin K (Dihydrophylloquinone)": "维生素K（二氢叶绿醌）",
    "Vitamin K (Menaquinone-4)": "维生素K2（甲萘醌-4）",
    "Vitamin B-12, added": "维生素B12（添加）",
    "Vitamin E, added": "维生素E（添加）",

    # ---- 类胡萝卜素补充 ----
    "Carotene, gamma": "γ-胡萝卜素",
    "Cryptoxanthin, alpha": "α-隐黄素",
    "Lutein": "叶黄素",
    "Zeaxanthin": "玉米黄质",
    "cis-Lutein/Zeaxanthin": "顺式叶黄素/玉米黄质",
    "cis-Lycopene": "顺式番茄红素",
    "cis-beta-Carotene": "顺式β-胡萝卜素",
    "trans-Lycopene": "反式番茄红素",
    "trans-beta-Carotene": "反式β-胡萝卜素",
    "Phytoene": "八氢番茄红素",
    "Phytofluene": "六氢番茄红素",

    # ---- 氨基酸补充 ----
    "Hydroxyproline": "羟脯氨酸",

    # ---- 胆碱补充 ----
    "Choline, free": "游离胆碱",
    "Choline, from glycerophosphocholine": "甘油磷胆碱来源胆碱",
    "Choline, from phosphocholine": "磷酸胆碱来源胆碱",
    "Choline, from phosphotidyl choline": "磷脂酰胆碱来源胆碱",
    "Choline, from sphingomyelin": "鞘磷脂来源胆碱",

    # ---- 膳食纤维补充 ----
    "Total dietary fiber (AOAC 2011.25)": "总膳食纤维 (AOAC 2011.25)",
    "High Molecular Weight Dietary Fiber (HMWDF)": "高分子量膳食纤维",
    "Low Molecular Weight Dietary Fiber (LMWDF)": "低分子量膳食纤维",

    # ---- 碳水化合物/能量补充 ----
    "Carbohydrate, by summation": "碳水化合物（求和法）",
    "Energy (Atwater General Factors)": "热量（Atwater 通用系数）",
    "Energy (Atwater Specific Factors)": "热量（Atwater 特定系数）",
    "Total fat (NLEA)": "总脂肪 (NLEA)",
    "Specific Gravity": "比重",

    # ---- 有机酸补充 ----
    "Pyruvic acid": "丙酮酸",
    "Quinic acid": "奎宁酸",

    # ---- 矿物质补充 ----
    "Cobalt, Co": "钴",
    "Nickel, Ni": "镍",
    "Boron, B": "硼",

    # ---- 植物甾醇 ----
    "Beta-sitosterol": "β-谷固醇",
    "Beta-sitostanol": "β-谷烷醇",
    "Brassicasterol": "菜籽固醇",
    "Campestanol": "菜烷醇",
    "Campesterol": "菜固醇",
    "Stigmasterol": "豆固醇",
    "Stigmastadiene": "豆甾二烯",
    "Phytosterols, other": "其他植物固醇",
    "Delta-5-avenasterol": "Δ5-燕麦固醇",
    "Delta-7-Stigmastenol": "Δ7-豆甾烷醇",
    "Ergosta-5,7-dienol": "麦角甾-5,7-二烯醇",
    "Ergosta-7,22-dienol": "麦角甾-7,22-二烯醇",
    "Ergosta-7-enol": "麦角甾-7-烯醇",
    "Ergosterol": "麦角固醇",

    # ---- 大豆异黄酮 ----
    "Daidzein": "大豆苷元",
    "Daidzin": "大豆苷",
    "Genistein": "染料木黄酮",
    "Genistin": "染料木苷",
    "Glycitin": "黄豆黄苷",

    # ---- 其他 ----
    "Beta-glucan": "β-葡聚糖",
    "Glutathione": "谷胱甘肽",
    "Ergothioneine": "麦角硫因",
    "Raffinose": "棉子糖",
    "Stachyose": "水苏糖",
    "Verbascose": "毛蕊花糖",
    "Resistant starch": "抗性淀粉",
    "Galactose": "半乳糖",
    "Maltodextrins": "麦芽糊精",
    "Fatty acids, total trans-dienoic": "反式二烯脂肪酸",

    # ---- 叶酸补充 ----
    "10-Formyl folic acid (10HCOFA)": "10-甲酰叶酸",
    "5-Formyltetrahydrofolic acid (5-HCOH4": "5-甲酰四氢叶酸",
    "5-methyl tetrahydrofolate (5-MTHF)": "5-甲基四氢叶酸",
}

def _translate_fatty_acid(name: str) -> str | None:
    """为特定脂肪酸名称生成中文翻译。"""
    m = re.match(r"^SFA (\d+:\d+)$", name)
    if m:
        return f"饱和脂肪酸 {m.group(1)}"
    m = re.match(r"^MUFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"单不饱和脂肪酸 {m.group(1)}{suffix}"
    m = re.match(r"^PUFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"多不饱和脂肪酸 {m.group(1)}{suffix}"
    m = re.match(r"^TFA (\d+:\d+)\s*(.*)$", name)
    if m:
        detail = m.group(2).strip()
        suffix = f" ({detail})" if detail else ""
        return f"反式脂肪酸 {m.group(1)}{suffix}"
    return None

# ============================================================================
# 下载
# ============================================================================

def _scrape_download_urls() -> dict[str, str]:
    """从 USDA 下载页面抓取各数据集的最新下载链接。

    Returns:
        {"foundation": "https://...", "sr_legacy": "https://...", "fndds": "https://..."}
    """
    log("[INFO] 正在获取 USDA 下载页面...")
    try:
        req = urllib.request.Request(USDA_DOWNLOADS_URL, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36 Edg/148.0.0.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            html = resp.read().decode("utf-8")
    except Exception as e:
        log(f"[ERROR] 无法访问 USDA 下载页面: {e}")
        log("[INFO] 请手动从以下页面下载数据文件:")
        log(f"       {USDA_DOWNLOADS_URL}")
        return {}

    # 查找所有 .zip 下载链接
    zip_urls: list[str] = []
    for m in re.finditer(r'href="(https?://[^"]+\.zip)"', html):
        zip_urls.append(m.group(1))

    # 也匹配相对路径
    for m in re.finditer(r'href="(\/fdc-datasets\/[^"]+\.zip)"', html):
        zip_urls.append("https://fdc.nal.usda.gov" + m.group(1))

    # 按关键词匹配到 dataset，收集所有候选 URL
    candidates: dict[str, list[str]] = {name: [] for _, name in DATASET_PATTERNS}
    for url in sorted(set(zip_urls)):
        url_lower = url.lower()
        for pattern, name in DATASET_PATTERNS:
            if pattern in url_lower:
                if url not in candidates[name]:
                    candidates[name].append(url)

    # 对每个 dataset，优先选 JSON 格式，其次选最新（按文件名中的日期排序）
    matched: dict[str, str] = {}
    for name, urls in candidates.items():
        if not urls:
            log(f"[INFO]   未找到 {name} 的下载链接")
            continue

        # 分类：JSON vs 非 JSON
        json_urls = [u for u in urls if "json" in Path(u).name.lower()]
        csv_urls = [u for u in urls if u not in json_urls]

        # 优先 JSON，兜底 CSV
        preferred = json_urls if json_urls else csv_urls

        # 在同格式中选最新的（文件名含日期，如 2026-04-30）
        def _extract_date(u: str) -> str:
            m = re.search(r"(\d{4}-\d{2}-\d{2})", u)
            return m.group(1) if m else "0000-00-00"

        preferred.sort(key=_extract_date, reverse=True)
        best = preferred[0]
        matched[name] = best

        fmt = "JSON" if best in json_urls else "CSV"
        log(f"[INFO]   找到 {name} ({fmt}): {Path(best).name}")

    return matched

def _download_file(url: str, dest: Path) -> bool:
    """下载单个文件，带进度显示。"""
    dest.parent.mkdir(parents=True, exist_ok=True)

    # 检查是否已存在
    if dest.exists():
        log(f"[INFO]   文件已存在，跳过: {dest.name}")
        return True

    log(f"[INFO]   下载: {url}")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            buf = bytearray()
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                buf.extend(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    if pct % 10 == 0:
                        log(f"[INFO]      {pct}% ({downloaded // 1048576} MB / {total // 1048576} MB)")

            dest.write_bytes(buf)
            size_mb = len(buf) / 1048576
            log(f"[INFO]   下载完成: {size_mb:.1f} MB")
            return True
    except Exception as e:
        log(f"[ERROR]   下载失败: {e}")
        if dest.exists():
            dest.unlink()
        return False

def download_datasets() -> dict[str, Path]:
    """下载或定位所有 USDA 数据集。

    Returns:
        {"foundation": path, "sr_legacy": path, "fndds": path}
    """
    log("[STEP] 准备 USDA 数据集")

    # 抓取最新下载链接
    urls = _scrape_download_urls()
    if not urls:
        log("[ERROR] 未找到下载链接，请手动下载后放入 data/ 目录")
        log(f"       下载页面: {USDA_DOWNLOADS_URL}")
        return {}

    # 额外尝试：如果抓取不完整，补充已知文件
    # 检查 data/ 目录中是否已有 zip 文件
    existing_zips: dict[str, Path] = {}
    for pattern, name in DATASET_PATTERNS:
        candidates = sorted(
            DATA_DIR.glob(f"*{pattern}*.zip"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        if candidates:
            existing_zips[name] = candidates[0]
            log(f"[INFO]   发现已有文件: {candidates[0].name}")

    # 下载缺失的
    results: dict[str, Path] = {}
    for name, url in urls.items():
        dest_name = Path(url).name
        dest = DATA_DIR / dest_name
        if _download_file(url, dest):
            results[name] = dest

    # 补充已有文件
    for name, path in existing_zips.items():
        if name not in results:
            results[name] = path

    return results

# ============================================================================
# 营养素提取
# ============================================================================

def _extract_nutrient(food_nutrient: dict) -> dict | None:
    """从 USDA foodNutrients 条目中提取营养素信息。"""
    # 嵌套格式 (USDA 下载文件)
    if "nutrient" in food_nutrient and isinstance(food_nutrient["nutrient"], dict):
        nt = food_nutrient["nutrient"]
        name = nt.get("name", "")
        unit = nt.get("unitName", "")
        amount = food_nutrient.get("amount")
    # 扁平格式 (API 响应)
    else:
        name = food_nutrient.get("nutrientName", "")
        unit = food_nutrient.get("unitName", "")
        amount = food_nutrient.get("value") or food_nutrient.get("amount")

    if not name or amount is None:
        return None

    name_zh = NUTRIENT_TRANSLATIONS.get(name)
    if name_zh is None:
        name_zh = _translate_fatty_acid(name)
    if name_zh is None:
        name_zh = name

    return {
        "name": name,
        "name_zh": name_zh,
        "amount": round(amount, 4) if isinstance(amount, float) else amount,
        "unit": unit,
    }

def _extract_nutrients_from_json(zf: zipfile.ZipFile) -> list[dict]:
    """从 ZIP 中的 JSON 文件提取营养素数据。"""
    json_files = [n for n in zf.namelist() if n.endswith(".json")]
    if not json_files:
        return []

    log(f"[INFO]   读取 JSON: {json_files[0]}")
    with zf.open(json_files[0]) as f:
        data = json.loads(f.read().decode("utf-8"))

    # 定位食物数组
    if isinstance(data, list):
        foods = data
    elif isinstance(data, dict):
        for key in (
            "FoundationFoods", "foundationFoods",
            "SRLegacyFoods", "srLegacyFoods",
            "SurveyFoods", "surveyFoods",
            "BrandedFoods", "brandedFoods",
            "foods",
        ):
            if key in data and isinstance(data[key], list):
                foods = data[key]
                log(f"[INFO]   数据集键名: {key}")
                break
        else:
            foods = []
    else:
        foods = []

    return foods

def _extract_nutrients_from_csv(zf: zipfile.ZipFile) -> list[dict]:
    """从 ZIP 中的 CSV 文件提取营养素数据（兜底方案）。"""
    import csv as csv_module
    import io

    # 读取 nutrient.csv 建立营养素名称映射
    nutrient_map: dict[str, dict] = {}
    for csv_name in zf.namelist():
        if csv_name.lower().endswith("nutrient.csv"):
            with zf.open(csv_name) as f:
                reader = csv_module.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    nid = row.get("id", "")
                    nutrient_map[nid] = {
                        "name": row.get("name", ""),
                        "unit": row.get("unit_name", ""),
                    }
            log(f"[INFO]   加载 {len(nutrient_map)} 条营养素定义")
            break

    # 读取 food.csv 建立食物列表
    foods: dict[str, dict] = {}
    for csv_name in zf.namelist():
        if csv_name.lower().endswith("food.csv"):
            with zf.open(csv_name) as f:
                reader = csv_module.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    fid = row.get("fdc_id", "")
                    if fid:
                        foods[fid] = {
                            "fdc_id": int(fid),
                            "description": row.get("description", ""),
                            "nutrients": [],
                        }
            log(f"[INFO]   加载 {len(foods)} 条食物条目")
            break

    # 读取 food_nutrient.csv 关联营养素
    for csv_name in zf.namelist():
        if csv_name.lower().endswith("food_nutrient.csv"):
            with zf.open(csv_name) as f:
                reader = csv_module.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"))
                for row in reader:
                    fid = row.get("fdc_id", "")
                    nid = row.get("nutrient_id", "")
                    amount_str = row.get("amount", "")
                    if fid in foods and nid in nutrient_map and amount_str:
                        try:
                            amount = float(amount_str)
                        except ValueError:
                            continue
                        nm = nutrient_map[nid]
                        n = _extract_nutrient({
                            "nutrientName": nm["name"],
                            "unitName": nm["unit"],
                            "value": amount,
                        })
                        if n is not None:
                            foods[fid]["nutrients"].append(n)
            break

    return list(foods.values())

def extract_from_zip(zip_path: Path, dataset_name: str) -> list[dict]:
    """从 ZIP 文件中提取 USDA 数据并抽取营养素。

    优先解析 JSON 格式，兜底解析 CSV 格式。
    """
    log(f"[STEP] 提取 {dataset_name} 营养素数据")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # 优先尝试 JSON 格式
        foods = _extract_nutrients_from_json(zf)

        if not foods:
            log("[INFO]   ZIP 中无 JSON 文件，尝试解析 CSV 格式...")
            foods = _extract_nutrients_from_csv(zf)

        if not foods:
            log(f"[ERROR]   ZIP 文件中没有可解析的数据（JSON 或 CSV）")
            return []

    log(f"[INFO]   共 {len(foods)} 条食物条目")

    results = []
    skipped = 0
    for i, food in enumerate(foods):
        # 跳过 null 条目（新版 USDA JSON 末尾可能包含 null）
        if food is None:
            skipped += 1
            continue

        fdc_id = food.get("fdcId") or food.get("fdc_id")
        description = food.get("description", "")
        if not fdc_id or not description:
            skipped += 1
            continue

        raw_nutrients = food.get("foodNutrients", [])
        nutrients = []
        for fn in raw_nutrients:
            n = _extract_nutrient(fn)
            if n is not None:
                nutrients.append(n)

        # 如果 foodNutrients 不在顶层（CSV 解析已展开），直接使用
        if not nutrients and isinstance(food.get("nutrients"), list):
            nutrients = food["nutrients"]

        results.append({
            "fdc_id": fdc_id,
            "description": description,
            "description_zh": "",
            "nutrients": nutrients,
        })

        if (i + 1) % 2000 == 0:
            log(f"[INFO]     已处理 {i + 1}/{len(foods)} 条...")

    total_nutrients = sum(len(r["nutrients"]) for r in results)
    log(f"[INFO]   提取完成: {len(results)} 条, {total_nutrients} 条营养素记录, 跳过 {skipped} 条")
    return results

# ============================================================================
# AI 翻译 — 翻译提供者
# ============================================================================

from abc import ABC, abstractmethod

class TranslationProvider(ABC):
    """翻译提供者基类。"""

    name: str = ""          # 内部标识名
    description: str = ""   # 人类可读描述

    @abstractmethod
    def translate(self, prompt: str) -> str | None:
        """发送翻译请求，返回原始响应文本。失败返回 None。"""
        ...

    def check_available(self) -> bool:
        """检查提供者是否可用。"""
        return True

    def __repr__(self) -> str:
        return f"{self.name}"

# ---------------------------------------------------------------------------
# Claude Code CLI 提供者
# ---------------------------------------------------------------------------

class ClaudeCodeProvider(TranslationProvider):
    name = "claude-code"
    description = "Claude Code CLI (本地运行 claude -p)"

    def check_available(self) -> bool:
        try:
            result = subprocess.run(
                [CLAUDE_BIN, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            return result.returncode == 0
        except Exception:
            return False

    def translate(self, prompt: str) -> str | None:
        try:
            result = subprocess.run(
                [CLAUDE_BIN, "-p", "--allowedTools", "Read,Write"],
                input=prompt,
                capture_output=True, text=True,
                timeout=3600,
                encoding="utf-8",
            )
            if result.returncode != 0:
                return None
            return result.stdout.strip()
        except Exception:
            return None

# ---------------------------------------------------------------------------
# OpenAI 兼容 API 提供者
# ---------------------------------------------------------------------------

class OpenAICompatibleProvider(TranslationProvider):
    name = "openai"
    description = "OpenAI API 及兼容接口 (DeepSeek / Ollama / vLLM / 等)"

    def __init__(self, api_key: str = "", base_url: str = "",
                 model: str = "gpt-4o") -> None:
        self.api_key = api_key or os.environ.get("TRANSLATOR_API_KEY", "")
        self.base_url = (base_url or os.environ.get("TRANSLATOR_BASE_URL",
                         "https://api.openai.com/v1")).rstrip("/")
        self.model = model or os.environ.get("TRANSLATOR_MODEL", "gpt-4o")

    def check_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt: str) -> str | None:
        url = f"{self.base_url}/chat/completions"
        body = json.dumps({
            "model": self.model,
            "messages": [
                {"role": "system", "content": "你是一个精确的 JSON 翻译器。请严格按要求输出 JSON 数组，不要添加任何解释。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 64000,
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"Bearer {self.api_key}")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return content.strip() if content else None
        except Exception as e:
            log(f"[API ERROR] OpenAI 请求失败: {e}")
            return None

# ---------------------------------------------------------------------------
# Anthropic API 提供者
# ---------------------------------------------------------------------------

class AnthropicAPIProvider(TranslationProvider):
    name = "anthropic"
    description = "Anthropic API 直接调用"

    def __init__(self, api_key: str = "", model: str = "") -> None:
        self.api_key = api_key or os.environ.get("TRANSLATOR_API_KEY", "")
        self.model = (model or os.environ.get("TRANSLATOR_MODEL",
                      "claude-sonnet-4-6"))

    def check_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt: str) -> str | None:
        url = "https://api.anthropic.com/v1/messages"
        body = json.dumps({
            "model": self.model,
            "max_tokens": 64000,
            "system": "你是一个精确的 JSON 翻译器。请严格按要求输出 JSON 数组，不要添加任何解释。",
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }, ensure_ascii=False).encode("utf-8")

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("x-api-key", self.api_key)
        req.add_header("anthropic-version", "2023-06-01")
        req.add_header("Content-Type", "application/json")

        try:
            with urllib.request.urlopen(req, timeout=600) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            content = data.get("content", [{}])
            texts = [b.get("text", "") for b in content if b.get("type") == "text"]
            return "\n".join(texts).strip() or None
        except Exception as e:
            log(f"[API ERROR] Anthropic 请求失败: {e}")
            return None

# ---------------------------------------------------------------------------
# DeepL 翻译平台 API 提供者
# ---------------------------------------------------------------------------

class DeepLProvider(TranslationProvider):
    name = "deepl"
    description = "DeepL 翻译平台 (EN→ZH 质量最佳，按字符计费)"

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        self.api_key = api_key or os.environ.get("TRANSLATOR_API_KEY", "")
        self.base_url = (base_url or os.environ.get("TRANSLATOR_BASE_URL",
                         "https://api-free.deepl.com")).rstrip("/")

    def check_available(self) -> bool:
        return bool(self.api_key)

    def translate(self, prompt: str) -> str | None:
        """DeepL 不支持直接翻译 prompt，请使用 translate_texts 方法。"""
        return None

    def translate_texts(self, texts: list[str]) -> list[str] | None:
        """批量翻译纯文本列表，返回同序译文列表。"""
        from urllib.parse import urlencode
        url = f"{self.base_url}/v2/translate"
        params = [("target_lang", "ZH"), ("source_lang", "EN")]
        for t in texts:
            params.append(("text", t))
        body = urlencode(params).encode("utf-8")

        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Authorization", f"DeepL-Auth-Key {self.api_key}")
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            translations = data.get("translations", [])
            return [t.get("text", "") for t in translations]
        except Exception as e:
            log(f"[API ERROR] DeepL 请求失败: {e}")
            return None


class BaiduTranslateProvider(TranslationProvider):
    """百度翻译 API (https://fanyi-api.baidu.com)。

    使用标准版可免费调用（QPS 限制），需要 APP ID 和密钥。
    认证格式: --translator-api-key APP_ID:SECRET_KEY
    环境变量: BAIDU_TRANSLATE_APP_ID / BAIDU_TRANSLATE_SECRET_KEY

    参考文档: https://fanyi-api.baidu.com/doc/21
    签名: MD5(appid + q + salt + 密钥)，q 在签名时不做 URL encode
    """
    name = "baidu"
    description = "百度翻译 API (EN→ZH，标准版免费)"

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        # api_key 格式: "APP_ID:SECRET_KEY"
        raw = api_key or os.environ.get("TRANSLATOR_API_KEY", "")
        if ":" in raw:
            self.app_id, self.secret_key = raw.split(":", 1)
        else:
            # 也支持独立环境变量
            self.app_id = os.environ.get("BAIDU_TRANSLATE_APP_ID", raw)
            self.secret_key = os.environ.get("BAIDU_TRANSLATE_SECRET_KEY", "")
        self.base_url = (base_url or os.environ.get("TRANSLATOR_BASE_URL",
                         "https://fanyi-api.baidu.com")).rstrip("/")

    def check_available(self) -> bool:
        return bool(self.app_id and self.secret_key)

    def translate(self, prompt: str) -> str | None:
        return None

    def _call_api(self, q: str, max_retries: int = 5) -> list[dict] | None:
        """调用百度翻译 API，返回 trans_result 列表或 None。

        使用指数退避重试：5s → 8s → 13s → 21s → 29s
        """
        import hashlib
        import random
        import time
        from urllib.parse import urlencode
        url = f"{self.base_url}/api/trans/vip/translate"
        backoff_times = [5, 8, 13, 21, 29]

        for attempt in range(1, max_retries + 1):
            salt = str(random.randint(32768, 65536))
            sign_str = f"{self.app_id}{q}{salt}{self.secret_key}"
            sign = hashlib.md5(sign_str.encode("utf-8")).hexdigest()

            body = urlencode({
                "q": q,
                "from": "en",
                "to": "zh",
                "appid": self.app_id,
                "salt": salt,
                "sign": sign,
            }).encode("utf-8")

            req = urllib.request.Request(url, data=body, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                error_code = data.get("error_code")
                if error_code:
                    wait = backoff_times[min(attempt - 1, len(backoff_times) - 1)]
                    log(f"[API ERROR] 百度翻译错误 {error_code}: {data.get('error_msg', '')} (重试 {attempt}/{max_retries}, 等待 {wait}s)")
                    if attempt < max_retries:
                        time.sleep(wait)
                        continue
                    return None
                return data.get("trans_result", [])
            except Exception as e:
                wait = backoff_times[min(attempt - 1, len(backoff_times) - 1)]
                log(f"[API ERROR] 百度翻译请求失败: {e} (重试 {attempt}/{max_retries}, 等待 {wait}s)")
                if attempt < max_retries:
                    time.sleep(wait)

        return None

    def translate_texts(self, texts: list[str]) -> list[str] | None:
        """批量翻译文本列表。

        百度翻译支持用 \\n 分隔多条文本一次请求翻译（单次上限 6000 字符）。
        将文本按字符数分组，每组一次请求，大幅减少 API 调用次数。
        """
        import time

        # 按字符数分组，每组不超过 6000 字符（含 \\n 分隔符）
        MAX_CHARS = 6000
        groups: list[list[int]] = []  # 每组存放原文索引
        current_group: list[int] = []
        current_len = 0

        for i, text in enumerate(texts):
            needed = len(text.encode("utf-8")) + (1 if current_group else 0)
            if current_group and current_len + needed > MAX_CHARS:
                groups.append(current_group)
                current_group = []
                current_len = 0
            current_group.append(i)
            current_len += len(text.encode("utf-8")) + (1 if len(current_group) > 1 else 0)
        if current_group:
            groups.append(current_group)

        results: list[str] = [""] * len(texts)

        for gi, indices in enumerate(groups):
            group_texts = [texts[i] for i in indices]
            q = "\n".join(group_texts)

            trans_result = self._call_api(q)
            if trans_result is None:
                # 整组失败，保留原文
                for idx in indices:
                    results[idx] = texts[idx]
            else:
                dsts = [r["dst"] for r in trans_result]
                if len(dsts) == len(indices):
                    for idx, dst in zip(indices, dsts):
                        results[idx] = dst
                else:
                    # 结果数与输入不匹配，逐条回退翻译
                    for idx in indices:
                        single = self._call_api(texts[idx])
                        if single and len(single) >= 1:
                            results[idx] = "".join(r["dst"] for r in single)
                        else:
                            results[idx] = texts[idx]
                        time.sleep(10)

            # 标准版 QPS=1，组间间隔确保不触发限流
            if gi < len(groups) - 1:
                time.sleep(10)

        return results

# ---------------------------------------------------------------------------
# 阿里云机器翻译提供者
# ---------------------------------------------------------------------------

class AliyunMTProvider(TranslationProvider):
    """阿里云机器翻译 TranslateGeneral API。

    使用 AccessKey ID + AccessKey Secret 认证，V3 签名（ACS3-HMAC-SHA256）。
    认证格式: --translator-api-key AccessKeyId:AccessKeySecret
    环境变量: ALIYUN_ACCESS_KEY_ID / ALIYUN_ACCESS_KEY_SECRET

    参考文档: https://help.aliyun.com/zh/machine-translation/developer-reference/api-alimt-2018-10-12-translategeneral
    QPS 限制: 50，单次最大 5000 字符
    """
    name = "aliyun"
    description = "阿里云机器翻译 (EN→ZH，QPS 50)"

    def __init__(self, api_key: str = "", base_url: str = "") -> None:
        # api_key 格式: "AccessKeyId:AccessKeySecret"
        raw = api_key or os.environ.get("TRANSLATOR_API_KEY", "")
        if ":" in raw:
            self.access_key_id, self.access_key_secret = raw.split(":", 1)
        else:
            self.access_key_id = os.environ.get("ALIYUN_ACCESS_KEY_ID", raw)
            self.access_key_secret = os.environ.get("ALIYUN_ACCESS_KEY_SECRET", "")
        self.host = (base_url or os.environ.get("TRANSLATOR_BASE_URL",
                     "mt.cn-hangzhou.aliyuncs.com")).rstrip("/")

    def check_available(self) -> bool:
        return bool(self.access_key_id and self.access_key_secret)

    def translate(self, prompt: str) -> str | None:
        return None

    def _call_api(self, q: str, max_retries: int = 5) -> str | None:
        """调用阿里云 TranslateGeneral API，返回翻译文本或 None。

        使用 ACS3-HMAC-SHA256 V3 签名，参数通过查询字符串传递（RPC 风格）。
        """
        import hashlib
        import hmac
        import time
        import uuid
        from urllib.parse import quote

        endpoint = f"https://{self.host}"

        # RPC 风格：参数放在查询字符串
        query_params = {
            "Action": "TranslateGeneral",
            "Version": "2018-10-12",
            "FormatType": "text",
            "SourceLanguage": "en",
            "TargetLanguage": "zh",
            "SourceText": q,
            "Scene": "general",
        }

        backoff_times = [2, 4, 8, 16, 32]

        for attempt in range(1, max_retries + 1):
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            nonce = str(uuid.uuid4())
            hashed_payload = hashlib.sha256(b"").hexdigest()

            # 构造参与签名的 headers（小写键名）
            sign_headers = {
                "content-type": "application/json; charset=utf-8",
                "host": self.host,
                "x-acs-action": "TranslateGeneral",
                "x-acs-content-sha256": hashed_payload,
                "x-acs-date": now,
                "x-acs-signature-nonce": nonce,
                "x-acs-version": "2018-10-12",
            }

            # 规范化查询字符串
            canonical_qs = "&".join(
                f"{quote(k, safe='')}={quote(v, safe='')}"
                for k, v in sorted(query_params.items())
            )

            # 规范化请求
            sorted_keys = sorted(sign_headers.keys())
            signed_headers_str = ";".join(sorted_keys)
            canonical_headers = "".join(
                f"{k}:{sign_headers[k].strip()}\n" for k in sorted_keys
            )
            canonical_request = (
                f"POST\n/\n{canonical_qs}\n"
                f"{canonical_headers}\n{signed_headers_str}\n{hashed_payload}"
            )

            # 待签名字符串
            string_to_sign = (
                f"ACS3-HMAC-SHA256\n"
                f"{hashlib.sha256(canonical_request.encode('utf-8')).hexdigest()}"
            )

            # HMAC-SHA256 签名
            signature = hmac.new(
                self.access_key_secret.encode("utf-8"),
                string_to_sign.encode("utf-8"),
                hashlib.sha256,
            ).hexdigest()

            # Authorization 头
            authorization = (
                f"ACS3-HMAC-SHA256 "
                f"Credential={self.access_key_id},"
                f"SignedHeaders={signed_headers_str},"
                f"Signature={signature}"
            )

            qs = "&".join(
                f"{quote(k, safe='')}={quote(v, safe='')}"
                for k, v in query_params.items()
            )
            url = f"{endpoint}/?{qs}"

            req = urllib.request.Request(url, data=b"", method="POST")
            for k, v in sign_headers.items():
                req.add_header(k, v)
            req.add_header("Authorization", authorization)

            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read().decode("utf-8"))
                code = data.get("Code")
                # Code 可能是 int 200 或 str "200"
                if code is not None and str(code) != "200":
                    wait = backoff_times[min(attempt - 1, len(backoff_times) - 1)]
                    log(f"[API ERROR] 阿里云翻译错误 {code}: {data.get('Message', '')} (重试 {attempt}/{max_retries}, 等待 {wait}s)")
                    log(f"  URL: {url}")
                    log(f"  响应: {json.dumps(data, ensure_ascii=False)}")
                    if attempt < max_retries:
                        time.sleep(wait)
                        continue
                    return None
                translated = data.get("Data", {}).get("Translated", "")
                return translated or None
            except Exception as e:
                wait = backoff_times[min(attempt - 1, len(backoff_times) - 1)]
                log(f"[API ERROR] 阿里云翻译请求失败: {e} (重试 {attempt}/{max_retries}, 等待 {wait}s)")
                if attempt < max_retries:
                    time.sleep(wait)

        return None

    def translate_texts(self, texts: list[str]) -> list[str] | None:
        """并发翻译文本列表。

        阿里云 TranslateGeneral 无批量模式，QPS 限制 10。
        使用线程池并发请求，max_workers=8 留出余量避免触发限流。
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        results: list[str | None] = [None] * len(texts)

        def _do_translate(idx: int, text: str) -> tuple[int, str]:
            translated = self._call_api(text)
            return idx, translated if translated else text

        with ThreadPoolExecutor(max_workers=8) as pool:
            futures = {
                pool.submit(_do_translate, i, text): i
                for i, text in enumerate(texts)
            }
            for future in as_completed(futures):
                idx, result = future.result()
                results[idx] = result

        return list(results)

# ---------------------------------------------------------------------------
# 提供者注册表
# ---------------------------------------------------------------------------

PROVIDER_CLASSES: dict[str, type[TranslationProvider]] = {
    "claude-code": ClaudeCodeProvider,
    "openai": OpenAICompatibleProvider,
    "anthropic": AnthropicAPIProvider,
    "deepl": DeepLProvider,
    "baidu": BaiduTranslateProvider,
    "aliyun": AliyunMTProvider,
}

def create_provider(name: str, **kwargs) -> TranslationProvider | None:
    """根据名称创建翻译提供者实例。"""
    cls = PROVIDER_CLASSES.get(name)
    if cls is None:
        return None

    import inspect
    sig = inspect.signature(cls.__init__)
    accepted = set(sig.parameters.keys()) - {"self"}
    filtered = {k: v for k, v in kwargs.items() if k in accepted}
    return cls(**filtered)

def list_providers() -> list[dict]:
    """列出所有可用翻译提供者及其描述。"""
    return [
        {"name": name, "description": cls.description}
        for name, cls in PROVIDER_CLASSES.items()
    ]

# ---------------------------------------------------------------------------
# 批量翻译核心逻辑
# ---------------------------------------------------------------------------

def _build_translation_prompt(slim_batch: list[dict],
                               output_path: Path | None = None) -> str:
    """构建翻译 prompt。"""
    lines = [
        "你是 USDA 食物数据库翻译专家。请将以下食物描述的 description 字段翻译为中文，填入 description_zh 字段，输出完整的 JSON 数组。",
        "",
        "翻译规则：",
        "1. 食材名称要准确（Chicken→鸡肉, Salmon→三文鱼, Broccoli→西兰花, Cheddar→切达奶酪）",
        "2. 加工方式用中文括号标注（raw→（生）, cooked→（熟）, canned→（罐装）, frozen→（冷冻）, dried→（干）, baked→（烤）, fried→（炸）, boiled→（煮）, steamed→（蒸）, smoked→（熏制）, pickled→（腌）, fermented→（发酵））",
        "3. 部位准确（breast→胸肉, thigh→腿肉, tenderloin→里脊, loin→里脊, wing→翅, leg→腿, belly→五花肉, rib→肋骨, shoulder→肩肉）",
        "4. 状态标注（boneless→（去骨）, skinless→（去皮）, lowfat→（低脂）, nonfat→（脱脂）, salted→（加盐）, unsalted→（无盐）, sweetened→（加糖）, unsweetened→（无糖）, fortified→（强化）, enriched→（强化）, whole grain→（全谷物））",
        "5. 去除 USDA 元数据标记（NFS, NS as to type, UPC:xxx, \"contains x and y\" 等冗余信息），不要翻译这些标记，直接省略",
        "6. 如果无法确定翻译，保留英文原文",
        "7. 翻译结果应该简洁、自然、符合中文表达习惯",
        "8. 每个元素的 fdc_id 必须保持不变",
        f"9. 必须翻译全部 {len(slim_batch)} 条，不可省略任何条目",
        "",
    ]

    if output_path:
        lines.append(f"【重要】翻译结果必须使用 Write 工具写入文件 {output_path}，格式为纯 JSON 数组。")

    lines.append("--- 待翻译数据 ---")
    lines.append(json.dumps(slim_batch, ensure_ascii=False))

    return "\n".join(lines)

def _translate_batch(
    batch: list[dict],
    slim_batch: list[dict],
    batch_num: int,
    total_batches: int,
    provider: TranslationProvider,
) -> list[dict]:
    """用指定提供者翻译一批食物描述，带重试逻辑。"""
    MAX_RETRIES = 3

    # ---- 纯文本翻译提供者（DeepL / 百度翻译） ----
    if isinstance(provider, (DeepLProvider, BaiduTranslateProvider, AliyunMTProvider)):
        return _translate_batch_text(batch, slim_batch, batch_num, total_batches, provider)

    # ---- LLM 提供者 ----
    is_claude = isinstance(provider, ClaudeCodeProvider)
    input_path = DATA_DIR / f"_batch_{batch_num:04d}_input.json"
    output_path = DATA_DIR / f"_batch_{batch_num:04d}_output.json" if is_claude else None

    if is_claude:
        input_path.write_text(json.dumps(slim_batch, ensure_ascii=False), encoding="utf-8")

    prompt = _build_translation_prompt(slim_batch, output_path)

    for attempt in range(1, MAX_RETRIES + 1):
        if output_path and output_path.exists():
            output_path.unlink()

        label = f"[TRANSLATE] 批次 {batch_num}/{total_batches} ({len(batch)} 条)"
        if attempt > 1:
            label += f" [重试 {attempt}/{MAX_RETRIES}]"
        log(f"{label}...", end="")

        try:
            raw = provider.translate(prompt)

            if raw is None:
                log(" 失败: 无响应")
                if attempt < MAX_RETRIES:
                    continue
                break

            # Claude Code: 优先从输出文件读取
            if is_claude and output_path and output_path.exists():
                raw = output_path.read_text(encoding="utf-8").strip()

            translated = _parse_json_data(raw)
            if translated and len(translated) == len(slim_batch):
                count = sum(
                    1 for t in translated
                    if t.get("description_zh") and t["description_zh"] != t.get("description", "")
                )
                log(f" 完成 ({count} 条已翻译)")
                _cleanup_temp_files(input_path, output_path)
                return translated
            else:
                got = len(translated) if translated else 0
                log(f" 解析失败 (条目数: {got}, 期望: {len(slim_batch)})")
                debug_path = DATA_DIR / f"translation_debug_batch_{batch_num:04d}_attempt{attempt}.txt"
                debug_path.write_text(raw[:5000], encoding="utf-8")

        except Exception as e:
            log(f" 错误: {e}")

        if attempt < MAX_RETRIES:
            log(f"           即将重试...")

    _cleanup_temp_files(input_path, output_path)
    return batch

def _translate_batch_text(
    batch: list[dict],
    slim_batch: list[dict],
    batch_num: int,
    total_batches: int,
    provider: TranslationProvider,
) -> list[dict]:
    """使用纯文本翻译提供者（DeepL / 百度翻译）翻译一批食物描述。"""
    MAX_RETRIES = 3
    descriptions = [item["description"] for item in slim_batch]

    for attempt in range(1, MAX_RETRIES + 1):
        label = f"[TRANSLATE] 批次 {batch_num}/{total_batches} ({len(batch)} 条, {provider.name})"
        if attempt > 1:
            label += f" [重试 {attempt}/{MAX_RETRIES}]"
        log(f"{label}...", end="")

        try:
            translations = provider.translate_texts(descriptions)
            if translations is None or len(translations) != len(descriptions):
                log(f" 失败: 译文数量不匹配")
                if attempt < MAX_RETRIES:
                    continue
                break

            translated = []
            for item, zh_text in zip(slim_batch, translations):
                translated.append({
                    "fdc_id": item["fdc_id"],
                    "description": item["description"],
                    "description_zh": zh_text,
                })

            count = sum(
                1 for t in translated
                if t.get("description_zh") and t["description_zh"] != t.get("description", "")
            )
            log(f" 完成 ({count} 条已翻译)")
            return translated

        except Exception as e:
            log(f" 错误: {e}")

        if attempt < MAX_RETRIES:
            log(f"           即将重试...")

    return batch

def _cleanup_temp_files(*paths: Path | None) -> None:
    """清理临时文件。"""
    for p in paths:
        if p is None:
            continue
        try:
            if p.exists():
                p.unlink()
        except OSError:
            pass

def _parse_json_data(raw: str) -> list[dict] | None:
    """解析 JSON 数据，提取翻译结果数组。"""
    if not raw:
        return None

    # 方法1: 直接解析
    try:
        data = json.loads(raw)
        if isinstance(data, list) and len(data) > 0 and "fdc_id" in data[0]:
            return data
    except json.JSONDecodeError:
        pass

    # 方法2: 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*\n?(\[.*?\])\s*```", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list) and len(data) > 0 and "fdc_id" in data[0]:
                return data
        except json.JSONDecodeError:
            pass

    # 方法3: 提取最外层 [ ... ] 数组
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list) and len(data) > 0 and "fdc_id" in data[0]:
                return data
        except json.JSONDecodeError:
            pass

    return None

# ---------------------------------------------------------------------------
# 批量翻译主函数
# ---------------------------------------------------------------------------

def translate_descriptions(
    all_data: list[dict],
    provider: TranslationProvider,
    progress_cb: Callable[[int, int], None] | None = None,
    batch_size: int = BATCH_SIZE,
) -> list[dict]:
    """使用指定提供者批量翻译所有食物描述。

    内置收敛循环：每轮翻译未完成的条目，直到全部翻译完成
    或连续 3 轮未翻译数量不再减少为止。
    """
    MAX_STALLED_PASSES = 3

    if not provider.check_available():
        log(f"[ERROR] 翻译提供者 '{provider.name}' 不可用。")
        if isinstance(provider, ClaudeCodeProvider):
            log("[INFO] 请安装: npm install -g @anthropic-ai/claude-code")
        elif isinstance(provider, (OpenAICompatibleProvider, AnthropicAPIProvider, DeepLProvider)):
            log("[INFO] 请设置: --translator-api-key 或 环境变量 TRANSLATOR_API_KEY")
        log("[INFO] 跳过翻译，description_zh 将留空")
        return all_data

    provider_label = f"{provider.name}"
    if isinstance(provider, OpenAICompatibleProvider):
        provider_label += f" ({provider.model})"
    elif isinstance(provider, AnthropicAPIProvider):
        provider_label += f" ({provider.model})"

    log(f"[STEP] AI 翻译食物描述 (提供者: {provider_label})")

    total_all = len(all_data)
    already_done = sum(1 for item in all_data if item.get("description_zh") and item["description_zh"] != item.get("description", ""))
    if already_done > 0:
        log(f"[INFO]   {already_done}/{total_all} 条已有翻译")

    stalled_passes = 0
    last_untranslated_count: int | None = None
    total_round = 0

    while True:
        total_round += 1
        to_translate = [
            item for item in all_data
            if not item.get("description_zh") or item["description_zh"] == item.get("description", "")
        ]
        # 清除等于原文的无效翻译，以便重新翻译
        for item in to_translate:
            if item.get("description_zh") and item["description_zh"] == item.get("description", ""):
                item["description_zh"] = ""

        if not to_translate:
            log("[INFO]   所有条目已翻译完毕!")
            break

        current_untranslated = len(to_translate)

        # 检查收敛
        if last_untranslated_count is not None:
            if current_untranslated == last_untranslated_count:
                stalled_passes += 1
                if stalled_passes >= MAX_STALLED_PASSES:
                    log(f"[INFO]   连续 {MAX_STALLED_PASSES} 轮无进展（{current_untranslated} 条未翻译），停止翻译")
                    break
            else:
                stalled_passes = 0
        last_untranslated_count = current_untranslated

        if total_round > 1:
            log(f"[INFO]   === 第 {total_round} 轮翻译: {current_untranslated} 条待翻译 ===")

        total_batches = (len(to_translate) + batch_size - 1) // batch_size
        log(f"[INFO]   分为 {total_batches} 批，每批 {batch_size} 条")

        round_translated = 0
        for batch_num in range(1, total_batches + 1):
            start = (batch_num - 1) * batch_size
            end = min(start + batch_size, len(to_translate))
            batch = to_translate[start:end]

            slim_batch = [
                {"fdc_id": item["fdc_id"], "description": item["description"]}
                for item in batch
            ]

            translated_batch = _translate_batch(batch, slim_batch, batch_num, total_batches, provider)

            # 百度翻译 QPS=1：批次间加间隔，避免连续请求触发限流
            if isinstance(provider, BaiduTranslateProvider) and batch_num < total_batches:
                import time
                time.sleep(2.5)

            for item in translated_batch:
                if item.get("description_zh") and item["description_zh"] != item.get("description", ""):
                    round_translated += 1
                for orig_item in to_translate:
                    if orig_item["fdc_id"] == item["fdc_id"]:
                        orig_item["description_zh"] = item.get("description_zh", "")
                        break

            if progress_cb:
                progress_cb(batch_num, total_batches)

        log(f"[INFO]   第 {total_round} 轮完成: 翻译 {round_translated}/{len(to_translate)} 条")
        if stalled_passes == 0 and current_untranslated > 0:
            # 有进展但仍有余量，继续下一轮
            remaining = sum(
                1 for item in all_data
                if not item.get("description_zh") or item["description_zh"] == item.get("description", "")
            )
            if remaining > 0:
                log(f"[INFO]   仍有 {remaining} 条未翻译，继续下一轮...")

    total_translated = sum(1 for item in all_data if item.get("description_zh") and item["description_zh"] != item.get("description", ""))
    final_untranslated = total_all - total_translated
    log(f"[INFO]   AI 翻译完成: {total_translated}/{total_all} 条已翻译, {final_untranslated} 条仍未翻译")
    return all_data

# ============================================================================
# 合并与输出
# ============================================================================

def merge_and_output(all_data: list[dict]) -> Path:
    """合并去重并写入输出文件。"""
    log("[STEP] 合并去重")

    # 按 fdc_id 去重
    seen: set[int] = set()
    unique: list[dict] = []
    for item in all_data:
        fdc_id = item["fdc_id"]
        if fdc_id not in seen:
            seen.add(fdc_id)
            unique.append(item)

    log(f"[INFO]   去重: {len(all_data)} → {len(unique)} 条")

    # 统计
    total_nutrients = sum(len(item["nutrients"]) for item in unique)
    translated = sum(1 for item in unique if item.get("description_zh") and item["description_zh"] != item["description"])
    untranslated = len(unique) - translated

    log(f"[INFO]   营养素记录: {total_nutrients}")
    log(f"[INFO]   已翻译: {translated} ({100 * translated / max(len(unique), 1):.1f}%)")
    log(f"[INFO]   未翻译: {untranslated}")

    # 输出紧凑 JSON
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = DATA_DIR / "usda_nutrition.json"

    log(f"[STEP] 写入输出: {out_path}")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique, f, ensure_ascii=False, separators=(",", ":"))

    size_mb = out_path.stat().st_size / 1048576
    log(f"[OK] 完成! 文件: {out_path} ({size_mb:.1f} MB)")
    log(f"[OK] {len(unique)} 条食物, {total_nutrients} 条营养素")

    return out_path

# ============================================================================
# 进度日志
# ============================================================================

def log(msg: str, end: str = "\n") -> None:
    """输出进度日志（UI 通过 stdout 读取）。"""
    print(msg, end=end, flush=True)

# ============================================================================
# 主流程
# ============================================================================

def build_usda_data(
    skip_download: bool = False,
    skip_translate: bool = False,
    batch_size: int = BATCH_SIZE,
    progress_cb: Callable[[int, int], None] | None = None,
    translator: str = "claude-code",
    translator_kwargs: dict | None = None,
    translate_only: bool = False,
) -> bool:
    """主入口：一键构建 USDA 营养数据库。

    Args:
        skip_download: 跳过下载步骤
        skip_translate: 跳过翻译步骤
        batch_size: 每批翻译数量
        progress_cb: 翻译进度回调 (current_batch, total_batches)
        translator: 翻译提供者名称 (claude-code / openai / anthropic / deepl)
        translator_kwargs: 传递给翻译提供者的额外参数 (api_key, base_url, model 等)
        translate_only: 仅翻译模式：加载已有输出文件，只翻译未翻译的条目

    Returns:
        是否成功
    """
    log("=" * 60)
    log("  USDA 营养数据库构建工具")
    log("=" * 60)

    all_data: list[dict] = []
    existing_output = DATA_DIR / "usda_nutrition.json"
    old_translations: dict[int, str] = {}  # fdc_id → description_zh

    # ---- 0. 仅翻译模式 ----
    if translate_only:
        log("[STEP] 仅翻译模式：加载已有数据，只翻译未完成条目")
        if not existing_output.exists():
            log("[ERROR] 没有找到 usda_nutrition.json")
            log("[INFO] 请先运行完整构建: python scripts/build_usda_data.py")
            return False

        with open(existing_output, encoding="utf-8") as f:
            all_data = json.load(f)

        total = len(all_data)
        untranslated = sum(
            1 for item in all_data
            if not item.get("description_zh") or item["description_zh"] == item.get("description", "")
        )
        log(f"[INFO]   加载 {total} 条, 已翻译 {total - untranslated} 条, 未翻译 {untranslated} 条")

        if untranslated == 0:
            log("[OK] 所有条目已翻译，无需翻译")
            return True

        # 直接跳到翻译步骤
        if skip_translate:
            log("[STEP] 跳过 AI 翻译")
        else:
            provider = create_provider(translator, **(translator_kwargs or {}))
            if provider is None:
                log(f"[ERROR] 未知的翻译提供者: {translator}")
                return False
            all_data = translate_descriptions(all_data, provider, progress_cb, batch_size)

        merge_and_output(all_data)
        return True

    # ---- 1. 加载已有翻译（用于保留） ----
    if existing_output.exists():
        try:
            with open(existing_output, encoding="utf-8") as f:
                old_data = json.load(f)
            old_translations = {
                item["fdc_id"]: item.get("description_zh", "")
                for item in old_data
                if item.get("description_zh") and item["description_zh"] != item.get("description", "")
            }
            if old_translations:
                log(f"[INFO]   从已有输出保留 {len(old_translations)} 条翻译")
        except (json.JSONDecodeError, OSError, KeyError):
            pass

    # ---- 2. 下载 ----
    if skip_download:
        log("[STEP] 跳过下载，使用已有数据文件")
        zip_files = list(DATA_DIR.glob("*.zip"))
        if not zip_files:
            raw_files = list(DATA_DIR.glob("*raw*.json"))
            if raw_files:
                for rf in raw_files:
                    with open(rf, encoding="utf-8") as f:
                        raw = json.load(f)
                    if isinstance(raw, list):
                        all_data.extend(raw)
                        log(f"[INFO]   加载: {rf.name} ({len(raw)} 条)")
                if all_data:
                    log(f"[INFO]   共 {len(all_data)} 条，跳过提取")
    else:
        zip_paths = download_datasets()
        if not zip_paths:
            log("[ERROR] 没有可用的数据源，终止")
            return False

    # ---- 3. 提取营养素 ----
    if not all_data:
        if skip_download:
            zip_files_for_extract = list(DATA_DIR.glob("*.zip"))
            if not zip_files_for_extract:
                log("[ERROR] data/ 目录中未找到 ZIP 文件")
                log("[INFO] 请运行: python scripts/build_usda_data.py")
                return False
            for zf in zip_files_for_extract:
                name_lower = zf.name.lower()
                for pattern, label in DATASET_PATTERNS:
                    if pattern in name_lower:
                        ds_name = label
                        break
                else:
                    ds_name = zf.stem
                all_data.extend(extract_from_zip(zf, ds_name))
        else:
            for name, zip_path in zip_paths.items():
                all_data.extend(extract_from_zip(zip_path, name))

    if not all_data:
        log("[ERROR] 未提取到任何数据")
        return False

    log(f"[STEP] 提取完成，共 {len(all_data)} 条食物条目")

    # ---- 3.5 将已有翻译合并到新提取的数据 ----
    if old_translations:
        restored = 0
        for item in all_data:
            if (not item.get("description_zh") or item["description_zh"] == item.get("description", "")) and item["fdc_id"] in old_translations:
                item["description_zh"] = old_translations[item["fdc_id"]]
                restored += 1
        if restored:
            log(f"[INFO]   恢复 {restored} 条已有翻译到新数据")

    # ---- 4. AI 翻译 ----
    if skip_translate:
        log("[STEP] 跳过 AI 翻译")
    else:
        provider = create_provider(translator, **(translator_kwargs or {}))
        if provider is None:
            log(f"[ERROR] 未知的翻译提供者: {translator}")
            log(f"[INFO] 可用提供者: {', '.join(PROVIDER_CLASSES.keys())}")
            log("[INFO] 跳过翻译，description_zh 将留空")
        else:
            all_data = translate_descriptions(all_data, provider, progress_cb, batch_size)

    # ---- 5. 合并输出 ----
    merge_and_output(all_data)
    return True

def main():
    parser = argparse.ArgumentParser(
        description="一键构建 USDA 营养数据库：下载 → 提取 → AI翻译 → 合并"
    )

    # 流程控制
    parser.add_argument(
        "--skip-download", action="store_true",
        help="跳过下载步骤，使用 data/ 目录中已有的 ZIP 文件"
    )
    parser.add_argument(
        "--skip-translate", action="store_true",
        help="跳过 AI 翻译步骤（description_zh 将留空）"
    )
    parser.add_argument(
        "--batch-size", type=int, default=BATCH_SIZE,
        help=f"每批翻译的条目数 (默认: {BATCH_SIZE})"
    )
    parser.add_argument(
        "--translate-only", action="store_true",
        help="仅翻译模式：加载已有的 usda_nutrition.json，只翻译未完成的条目，不重新下载"
    )

    # 翻译提供者选择
    parser.add_argument(
        "--translator", type=str,
        default=os.environ.get("TRANSLATOR", "claude-code"),
        choices=list(PROVIDER_CLASSES.keys()),
        help="翻译提供者 (默认: claude-code, 环境变量: TRANSLATOR)"
    )
    parser.add_argument(
        "--translator-api-key", type=str,
        default=os.environ.get("TRANSLATOR_API_KEY", ""),
        help="翻译 API Key (环境变量: TRANSLATOR_API_KEY)"
    )
    parser.add_argument(
        "--translator-base-url", type=str,
        default=os.environ.get("TRANSLATOR_BASE_URL", ""),
        help="翻译 API 基础 URL (环境变量: TRANSLATOR_BASE_URL)。\n"
             "OpenAI 兼容: https://api.openai.com/v1 或自定义 (如 DeepSeek: https://api.deepseek.com/v1)\n"
             "DeepL: https://api-free.deepl.com (免费) 或 https://api.deepl.com (Pro)"
    )
    parser.add_argument(
        "--translator-model", type=str,
        default=os.environ.get("TRANSLATOR_MODEL", ""),
        help="翻译模型名称 (环境变量: TRANSLATOR_MODEL)。\n"
             "OpenAI: gpt-4o (默认); Anthropic: claude-sonnet-4-6 (默认); 自定义兼容: 按实际填写"
    )
    parser.add_argument(
        "--list-translators", action="store_true",
        help="列出所有可用的翻译提供者并退出"
    )

    args = parser.parse_args()

    if args.list_translators:
        print("\n可用的翻译提供者:")
        print("-" * 60)
        for p in list_providers():
            print(f"  {p['name']:<15} {p['description']}")
        print()
        print("推荐翻译平台 API:")
        print("  DeepL       https://www.deepl.com/pro-api  (EN→ZH 质量最佳)")
        print("  Google      https://cloud.google.com/translate")
        print("  Azure       https://azure.microsoft.com/zh-cn/services/cognitive-services/translator/")
        print("  DeepSeek    https://platform.deepseek.com/api-docs/  (OpenAI 兼容，中文友好)")
        print()
        print("用法示例:")
        print("  # Claude Code (默认)")
        print("  python scripts/build_usda_data.py")
        print()
        print("  # OpenAI")
        print("  python scripts/build_usda_data.py --translator openai --translator-api-key sk-xxx")
        print()
        print("  # Anthropic")
        print("  python scripts/build_usda_data.py --translator anthropic --translator-api-key sk-ant-xxx")
        print()
        print("  # DeepSeek (OpenAI 兼容)")
        print("  python scripts/build_usda_data.py --translator openai --translator-base-url https://api.deepseek.com/v1 --translator-api-key sk-xxx --translator-model deepseek-chat")
        print()
        print("  # DeepL 翻译平台")
        print("  python scripts/build_usda_data.py --translator deepl --translator-api-key xxx")
        print()
        print("  # 百度翻译 API (标准版免费)")
        print("  python scripts/build_usda_data.py --translator baidu --translator-api-key APP_ID:SECRET_KEY")
        print()
        print("  # 通过环境变量配置")
        print("  set TRANSLATOR=openai")
        print("  set TRANSLATOR_API_KEY=sk-xxx")
        print("  python scripts/build_usda_data.py")
        return

    translator_kwargs: dict[str, str] = {}
    if args.translator_api_key:
        translator_kwargs["api_key"] = args.translator_api_key
    if args.translator_base_url:
        translator_kwargs["base_url"] = args.translator_base_url
    if args.translator_model:
        translator_kwargs["model"] = args.translator_model

    success = build_usda_data(
        skip_download=args.skip_download,
        batch_size=args.batch_size,
        skip_translate=args.skip_translate,
        translator=args.translator,
        translator_kwargs=translator_kwargs or None,
        translate_only=args.translate_only,
    )
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
