#!/usr/bin/env python3
"""
一键构建 USDA 营养数据库：下载 → 提取 → AI翻译 → 合并。

用法:
    python scripts/build_usda_data.py              # 完整构建
    python scripts/build_usda_data.py --skip-download  # 跳过下载，使用已有文件
    python scripts/build_usda_data.py --skip-translate # 跳过翻译

输出: data/usda_nutrition.json（~78 MB，紧凑 JSON）

要求:
    - claude CLI 已安装: npm install -g @anthropic-ai/claude-code
    - 或设置环境变量 CLAUDE_BIN 指向 claude 可执行文件
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
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
        req = urllib.request.Request(USDA_DOWNLOADS_URL, headers={"User-Agent": "Mozilla/5.0"})
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

    # 按关键词匹配到 dataset
    matched: dict[str, str] = {}
    for url in sorted(set(zip_urls)):
        url_lower = url.lower()
        for pattern, name in DATASET_PATTERNS:
            if pattern in url_lower:
                if name not in matched:
                    matched[name] = url
                    log(f"[INFO]   找到 {name}: {Path(url).name}")

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


def extract_from_zip(zip_path: Path, dataset_name: str) -> list[dict]:
    """从 ZIP 文件中提取 USDA JSON 数据并抽取营养素。"""
    log(f"[STEP] 提取 {dataset_name} 营养素数据")

    with zipfile.ZipFile(zip_path, "r") as zf:
        # 找到 JSON 文件
        json_files = [n for n in zf.namelist() if n.endswith(".json")]
        if not json_files:
            log(f"[ERROR]   ZIP 文件中没有 JSON 文件")
            return []

        log(f"[INFO]   读取: {json_files[0]}")
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

    log(f"[INFO]   共 {len(foods)} 条食物条目")

    results = []
    skipped = 0
    for i, food in enumerate(foods):
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
# AI 翻译
# ============================================================================


def _check_claude_available() -> bool:
    """检查 claude CLI 是否可用。"""
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--version"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _translate_batch(batch: list[dict], batch_num: int, total_batches: int) -> list[dict]:
    """用 claude -p 翻译一批食物描述。

    Args:
        batch: [{"fdc_id": ..., "description": ...}, ...]
        batch_num: 当前批次号 (1-based)
        total_batches: 总批次数

    Returns:
        同 batch，但 description_zh 字段已填入翻译
    """
    input_json = json.dumps(batch, ensure_ascii=False)

    prompt = f"""你是 USDA 食物数据库翻译专家。请将以下食物描述翻译为中文，填入 description_zh 字段。

翻译规则：
1. 食材名称要准确（Chicken→鸡肉, Salmon→三文鱼, Broccoli→西兰花, Cheddar→切达奶酪）
2. 加工方式用中文括号标注（raw→（生）, cooked→（熟）, canned→（罐装）, frozen→（冷冻）, dried→（干）, baked→（烤）, fried→（炸）, boiled→（煮）, steamed→（蒸）, smoked→（熏制）, pickled→（腌）, fermented→（发酵））
3. 部位准确（breast→胸肉, thigh→腿肉, tenderloin→里脊, loin→里脊, wing→翅, leg→腿, belly→五花肉, rib→肋骨, shoulder→肩肉）
4. 状态标注（boneless→（去骨）, skinless→（去皮）, lowfat→（低脂）, nonfat→（脱脂）, salted→（加盐）, unsalted→（无盐）, sweetened→（加糖）, unsweetened→（无糖）, fortified→（强化）, enriched→（强化）, whole grain→（全谷物））
5. 去除 USDA 元数据标记（NFS, NS as to type, UPC:xxx, "contains x and y" 等冗余信息），不要翻译这些标记，直接省略
6. 如果无法确定翻译，保留英文原文
7. 翻译结果应该简洁、自然、符合中文表达习惯

请输出纯 JSON 数组（不要用 markdown 代码块包裹，直接输出 [{{ 开头的 JSON）：

{input_json}"""

    log(f"[TRANSLATE] 批次 {batch_num}/{total_batches} ({len(batch)} 条)...", end="")

    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", prompt],
            capture_output=True, text=True,
            timeout=300,  # 5 分钟超时
            encoding="utf-8",
        )

        if result.returncode != 0:
            log(f" 失败: claude 返回码 {result.returncode}")
            if result.stderr:
                log(f"           {result.stderr[:200]}")
            return batch

        output = result.stdout.strip()

        # 尝试解析 JSON
        translated = _parse_claude_output(output, batch)
        if translated:
            log(f" 完成 ({sum(1 for t in translated if t.get('description_zh') and t['description_zh'] != t.get('description', ''))} 条已翻译)")
            return translated
        else:
            log(" 失败: 无法解析输出 JSON")
            # 保存失败输出以便调试
            debug_path = DATA_DIR / f"translation_debug_batch_{batch_num}.txt"
            debug_path.write_text(output[:5000], encoding="utf-8")
            log(f"           调试输出已保存到 {debug_path}")
            return batch

    except subprocess.TimeoutExpired:
        log(" 超时")
        return batch
    except Exception as e:
        log(f" 错误: {e}")
        return batch


def _parse_claude_output(output: str, fallback_batch: list[dict]) -> list[dict] | None:
    """解析 claude 输出，提取 JSON 数组。"""
    # 方法1: 直接解析整个输出
    try:
        data = json.loads(output)
        if isinstance(data, list) and len(data) > 0 and "fdc_id" in data[0]:
            return data
    except json.JSONDecodeError:
        pass

    # 方法2: 提取 ```json ... ``` 代码块
    m = re.search(r"```(?:json)?\s*\n?(\[.*?\])\s*```", output, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(1))
            if isinstance(data, list) and len(data) > 0:
                return data
        except json.JSONDecodeError:
            pass

    # 方法3: 提取最外层 [ ... ] 数组
    m = re.search(r"\[.*\]", output, re.DOTALL)
    if m:
        try:
            data = json.loads(m.group(0))
            if isinstance(data, list) and len(data) > 0:
                return data
        except json.JSONDecodeError:
            pass

    return None


def translate_with_claude(
    all_data: list[dict],
    progress_cb: Callable[[int, int], None] | None = None,
    batch_size: int = BATCH_SIZE,
) -> list[dict]:
    """使用 Claude AI 批量翻译所有食物描述。

    Args:
        all_data: 食物数据列表
        progress_cb: 进度回调 (current, total)

    Returns:
        已翻译的数据（原地修改 all_data 中的 description_zh）
    """
    if not _check_claude_available():
        log("[ERROR] claude CLI 不可用。请先安装: npm install -g @anthropic-ai/claude-code")
        log("[INFO] 跳过翻译，description_zh 将留空")
        return all_data

    log(f"[STEP] AI 翻译食物描述 (使用 {CLAUDE_BIN} -p)")

    # 只翻译尚未翻译的条目
    to_translate = [item for item in all_data if not item.get("description_zh")]
    already_translated = len(all_data) - len(to_translate)

    if already_translated > 0:
        log(f"[INFO]   {already_translated} 条已有翻译，跳过")

    if not to_translate:
        log("[INFO]   所有条目已翻译，无需翻译")
        return all_data

    total_batches = (len(to_translate) + batch_size - 1) // batch_size
    log(f"[INFO]   需要翻译 {len(to_translate)} 条，分为 {total_batches} 批，每批 {batch_size} 条")

    translated_count = 0
    for batch_num in range(1, total_batches + 1):
        start = (batch_num - 1) * batch_size
        end = min(start + batch_size, len(to_translate))
        batch = to_translate[start:end]

        # 调用 claude 翻译
        translated_batch = _translate_batch(batch, batch_num, total_batches)

        # 将翻译结果写回
        for item in translated_batch:
            if item.get("description_zh") and item["description_zh"] != item.get("description", ""):
                translated_count += 1
            # 更新原始数据
            for orig_item in to_translate:
                if orig_item["fdc_id"] == item["fdc_id"]:
                    orig_item["description_zh"] = item.get("description_zh", "")
                    break

        if progress_cb:
            progress_cb(batch_num, total_batches)

    log(f"[INFO]   AI 翻译完成: {translated_count}/{len(to_translate)} 条")
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
) -> bool:
    """主入口：一键构建 USDA 营养数据库。

    Args:
        skip_download: 跳过下载步骤
        skip_translate: 跳过翻译步骤
        progress_cb: 翻译进度回调 (current_batch, total_batches)

    Returns:
        是否成功
    """
    log("=" * 60)
    log("  USDA 营养数据库构建工具")
    log("=" * 60)

    # ---- 1. 下载 ----
    all_data: list[dict] = []

    if skip_download:
        log("[STEP] 跳过下载，使用已有数据文件")
        # 查找已有的提取结果（data/*_raw.json 或 usda_nutrition.json）
        existing_output = DATA_DIR / "usda_nutrition.json"
        if existing_output.exists():
            log(f"[INFO]   发现已有输出: {existing_output}")
            log(f"[INFO]   如需重新构建，请删除该文件或使用 --force")
            return True

        # 查找 ZIP 文件
        zip_files = list(DATA_DIR.glob("*.zip"))
        if not zip_files:
            # 查找 raw JSON 文件
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

    # ---- 2. 提取营养素 ----
    if not all_data:
        if skip_download:
            zip_files_for_extract = list(DATA_DIR.glob("*.zip"))
            if not zip_files_for_extract:
                log("[ERROR] data/ 目录中未找到 ZIP 文件")
                log("[INFO] 请运行: python scripts/build_usda_data.py")
                return False
            for zf in zip_files_for_extract:
                # 推断数据集名称
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

    # ---- 3. AI 翻译 ----
    if skip_translate:
        log("[STEP] 跳过 AI 翻译")
    else:
        all_data = translate_with_claude(all_data, progress_cb, batch_size)

    # ---- 4. 合并输出 ----
    merge_and_output(all_data)
    return True


def main():
    parser = argparse.ArgumentParser(
        description="一键构建 USDA 营养数据库：下载 → 提取 → AI翻译 → 合并"
    )
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
    args = parser.parse_args()

    success = build_usda_data(
        skip_download=args.skip_download,
        batch_size=args.batch_size,
        skip_translate=args.skip_translate,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
