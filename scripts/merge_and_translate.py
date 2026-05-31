"""
合并所有 USDA 数据源并自动翻译食物描述。

数据源:
  - Foundation Foods (365 条, 手动翻译)
  - SR Legacy (7793 条, 模式翻译)
  - FNDDS (5432 条, 模式翻译)

输出: data/usda_nutrition.json
"""
import json
import re
from pathlib import Path

# =====================================================================
# 食物名称中英文词典
# =====================================================================
FOOD_NAMES: dict[str, str] = {
    # 肉类
    "beef": "牛肉", "pork": "猪肉", "chicken": "鸡肉", "lamb": "羊肉",
    "mutton": "羊肉", "turkey": "火鸡肉", "duck": "鸭肉", "goose": "鹅肉",
    "veal": "小牛肉", "venison": "鹿肉", "bison": "野牛肉", "rabbit": "兔肉",
    "boar": "野猪肉",

    # 部位
    "breast": "胸肉", "thigh": "腿肉", "drumstick": "鸡腿", "wing": "翅",
    "leg": "腿", "loin": "里脊", "tenderloin": "柳", "rib": "肋骨",
    "chuck": "肩肉", "round": "臀肉", "flank": "腹肉", "sirloin": "西冷",
    "brisket": "胸肉", "shank": "腿骨", "plate": "腹板", "belly": "五花肉",
    "bacon": "培根", "ham": "火腿", "steak": "牛排", "roast": "烤肉",
    "chop": "排骨", "ribeye": "肋眼", "porterhouse": "T骨", "t-bone": "T骨",
    "ground": "肉馅", "stew": "炖肉", "short": "短", "back": "背",
    "rack": "排", "shoulder": "肩", "neck": "颈",

    # 水产
    "fish": "鱼", "salmon": "三文鱼", "tuna": "金枪鱼", "cod": "鳕鱼",
    "haddock": "黑线鳕", "pollock": "狭鳕鱼", "tilapia": "罗非鱼",
    "catfish": "鲶鱼", "trout": "鳟鱼", "sardine": "沙丁鱼",
    "mackerel": "鲭鱼", "herring": "鲱鱼", "anchov": "凤尾鱼",
    "swordfish": "旗鱼", "halibut": "大比目鱼", "snapper": "红鲷",
    "mahimahi": "鲯鳅", "perch": "鲈鱼", "bass": "鲈鱼",
    "sole": "比目鱼", "flounder": "比目鱼", "pike": "狗鱼",
    "shrimp": "虾", "prawn": "对虾", "crab": "蟹", "lobster": "龙虾",
    "scallop": "扇贝", "squid": "鱿鱼", "calamari": "鱿鱼",
    "oyster": "牡蛎", "clam": "蛤蜊", "mussel": "贻贝",
    "crustacean": "甲壳类", "crustaceans": "甲壳类",

    # 蛋奶
    "egg": "鸡蛋", "eggs": "鸡蛋", "yolk": "蛋黄", "white": "蛋白",
    "milk": "牛奶", "cream": "奶油", "butter": "黄油", "cheese": "奶酪",
    "yogurt": "酸奶", "buttermilk": "酪乳", "whey": "乳清",
    "cheddar": "切达", "mozzarella": "莫扎瑞拉", "parmesan": "帕玛森",
    "ricotta": "里科塔", "cottage cheese": "茅屋奶酪", "feta": "菲达",
    "swiss": "瑞士", "cream cheese": "奶油奶酪", "brie": "布里",
    "gouda": "高达", "provolone": "波罗伏洛", "colby": "科尔比",
    "monterey": "蒙特利", " Monterey jack": "蒙特利杰克",
    "whip": "打发", "sour": "酸", "skim": "脱脂", "nonfat": "脱脂",
    "lowfat": "低脂", "whole": "全脂", "half": "半",
    "pasteurized": "巴氏杀菌", "evaporated": "炼乳", "condensed": "炼乳",
    "dry": "干", "dried": "干", "dehydrated": "脱水",

    # 蔬菜
    "tomato": "番茄", "tomatoes": "番茄", "potato": "土豆", "potatoes": "土豆",
    "onion": "洋葱", "onions": "洋葱", "garlic": "大蒜", "carrot": "胡萝卜",
    "carrots": "胡萝卜", "celery": "芹菜", "lettuce": "生菜", "cabbage": "甘蓝",
    "broccoli": "西兰花", "cauliflower": "花椰菜", "spinach": "菠菜",
    "pepper": "辣椒", "peppers": "辣椒", "cucumber": "黄瓜",
    "eggplant": "茄子", "zucchini": "西葫芦", "squash": "南瓜",
    "pumpkin": "南瓜", "mushroom": "蘑菇", "mushrooms": "蘑菇",
    "corn": "玉米", "pea": "豌豆", "peas": "豌豆", "bean": "豆",
    "beans": "豆", "lentil": "扁豆", "lentils": "扁豆",
    "sweet potato": "红薯", "kale": "羽衣甘蓝", "collard": "羽衣甘蓝",
    "asparagus": "芦笋", "artichoke": "朝鲜蓟", "beet": "甜菜",
    "turnip": "芜菁", "radish": "萝卜", "radishes": "萝卜",
    "rutabaga": "芜菁甘蓝", "parsnip": "欧防风",
    "brussels sprout": "球芽甘蓝", "bok choy": "小白菜",
    "cabbage, napa": "大白菜", "napa cabbage": "大白菜",
    "leek": "韭葱", "shallot": "红葱头", "scallion": "小葱",
    "green onion": "小葱", "fennel": "茴香", "okra": "秋葵",
    "avocado": "牛油果", "olive": "橄榄", "olives": "橄榄",
    "pickle": "酸黄瓜", "pickles": "酸黄瓜",
    "cassava": "木薯", "taro": "芋头", "yam": "山药",
    "plantain": "大蕉", "arugula": "芝麻菜", "endive": "苦苣",

    # 水果
    "apple": "苹果", "apples": "苹果", "banana": "香蕉", "bananas": "香蕉",
    "orange": "橙子", "grape": "葡萄", "grapes": "葡萄",
    "strawberr": "草莓", "blueberr": "蓝莓", "raspberr": "覆盆子",
    "blackberr": "黑莓", "cranberr": "蔓越莓",
    "peach": "桃", "pear": "梨", "cherry": "樱桃", "plum": "李子",
    "apricot": "杏", "mango": "芒果", "pineapple": "菠萝",
    "watermelon": "西瓜", "melon": "甜瓜", "cantaloupe": "哈密瓜",
    "kiwifruit": "猕猴桃", "kiwi": "猕猴桃", "lemon": "柠檬",
    "lime": "青柠", "grapefruit": "西柚", "pomegranate": "石榴",
    "fig": "无花果", "date": "椰枣", "coconut": "椰子",
    "papaya": "木瓜", "guava": "番石榴", "passion fruit": "百香果",
    "persimmon": "柿子", "nectarine": "油桃", "mandarin": "橘子",
    "tangerine": "橘子", "tomatillo": "绿番茄",

    # 谷物粮食
    "rice": "米", "wheat": "小麦", "flour": "面粉", "bread": "面包",
    "oat": "燕麦", "oats": "燕麦", "barley": "大麦", "rye": "黑麦",
    "cornmeal": "玉米面", "cornmeal": "玉米面", "cornflour": "玉米粉",
    "noodle": "面条", "noodles": "面条", "pasta": "意面",
    "spaghetti": "意面", "macaroni": "通心粉", "couscous": "古斯米",
    "tortilla": "玉米饼", "cracker": "饼干", "crackers": "饼干",
    "cookie": "曲奇", "cookies": "曲奇", "cake": "蛋糕",
    "muffin": "松饼", "pancake": "煎饼", "waffle": "华夫饼",
    "granola": "格兰诺拉", "cereal": "谷物", "biscuit": "饼干",
    "buckwheat": "荞麦", "millet": "小米", "quinoa": "藜麦",
    "sorghum": "高粱", "amaranth": "苋菜", "bulgur": "布格麦",
    "semolina": "粗麦粉", "couscous": "古斯米", "spelt": "斯佩尔特",
    "wild rice": "野生稻", "brown rice": "糙米", "white rice": "白米",

    # 坚果种子
    "almond": "杏仁", "walnut": "核桃", "peanut": "花生",
    "cashew": "腰果", "pecan": "碧根果", "pistachio": "开心果",
    "hazelnut": "榛子", "macadamia": "夏威夷果", "brazil nut": "巴西坚果",
    "pine nut": "松子", "sunflower seed": "葵花籽",
    "pumpkin seed": "南瓜子", "sesame": "芝麻", "flaxseed": "亚麻籽",
    "chia seed": "奇亚籽", "coconut": "椰子",

    # 油脂
    "oil": "油", "olive oil": "橄榄油", "coconut oil": "椰子油",
    "vegetable oil": "植物油", "canola oil": "菜籽油",
    "soybean oil": "大豆油", "corn oil": "玉米油",
    "peanut oil": "花生油", "sunflower oil": "葵花籽油",
    "safflower oil": "红花油", "lard": "猪油", "shortening": "起酥油",
    "margarine": "人造黄油",

    # 调味品
    "salt": "盐", "sugar": "糖", "honey": "蜂蜜", "syrup": "糖浆",
    "molasses": "糖蜜", "vinegar": "醋", "soy sauce": "酱油",
    "mustard": "芥末", "ketchup": "番茄酱", "mayonnaise": "蛋黄酱",
    "salsa": "萨尔萨酱", "hot sauce": "辣酱", "worcestershire": "辣酱油",
    "spice": "香料", "herb": "香草", "ginger": "姜",
    "cinnamon": "肉桂", "cumin": "孜然", "turmeric": "姜黄",
    "paprika": "红椒粉", "nutmeg": "肉豆蔻", "clove": "丁香",
    "cumin": "孜然", "coriander": "香菜", "basil": "罗勒",
    "oregano": "牛至", "thyme": "百里香", "rosemary": "迷迭香",
    "parsley": "欧芹", "dill": "莳萝", "sage": "鼠尾草",
    "bay leaf": "月桂叶", "pepper": "胡椒", "vanilla": "香草",
    "cocoa": "可可", "chocolate": "巧克力",

    # 饮品
    "water": "水", "tea": "茶", "coffee": "咖啡", "juice": "汁",
    "wine": "葡萄酒", "beer": "啤酒", "soda": "汽水",
    "lemonade": "柠檬水", "soy milk": "豆奶", "almond milk": "杏仁奶",
    "oat milk": "燕麦奶", "rice milk": "米浆", "coconut milk": "椰奶",

    # 加工状态
    "raw": "生", "cooked": "熟", "fried": "炸", "baked": "烤",
    "boiled": "煮", "steamed": "蒸", "grilled": "烤", "roasted": "烤",
    "braised": "炖", "stewed": "炖", "broiled": "烤",
    "canned": "罐装", "frozen": "冷冻", "fresh": "新鲜",
    "smoked": "熏", "cured": "腌制", "pickled": "腌",
    "fermented": "发酵", "refined": "精炼", "unrefined": "未精炼",
    "enriched": "强化", "unenriched": "未强化", "bleached": "漂白",
    "unbleached": "未漂白", "fortified": "强化", "whole grain": "全谷物",
    "all-purpose": "中筋", "bread flour": "面包粉", "cake flour": "蛋糕粉",
    "pastry flour": "糕点粉", "self-rising": "自发粉",

    # 大豆和豆制品
    "tofu": "豆腐", "soybean": "大豆", "soy": "大豆",
    "tempeh": "天贝", "miso": "味噌", "edamame": "毛豆",
    "chickpea": "鹰嘴豆", "garbanzo": "鹰嘴豆",

    # 其他
    "soup": "汤", "sauce": "酱", "gravy": "肉汁",
    "dressing": "调味汁", "marinade": "腌料", "dip": "蘸酱",
    "salad": "沙拉", "sandwich": "三明治", "pizza": "披萨",
    "hummus": "鹰嘴豆泥", "tahini": "芝麻酱",
    "nut butter": "坚果酱", "peanut butter": "花生酱",
    "almond butter": "杏仁酱", "seed butter": "种子酱",
}

# =====================================================================
# 状态/处理方式翻译
# =====================================================================
STATE_PATTERNS: list[tuple[str, str]] = [
    (r',?\s*raw\b', '（生）'),
    (r',?\s*cooked\b', '（熟）'),
    (r',?\s*fried\b', '（炸）'),
    (r',?\s*baked\b', '（烤）'),
    (r',?\s*boiled\b', '（煮）'),
    (r',?\s*steamed\b', '（蒸）'),
    (r',?\s*grilled\b', '（烤制）'),
    (r',?\s*roasted\b', '（烤）'),
    (r',?\s*braised\b', '（炖）'),
    (r',?\s*stewed\b', '（炖）'),
    (r',?\s*broiled\b', '（烤）'),
    (r',?\s*pan-fried\b', '（煎）'),
    (r',?\s*stir[- ]?fried\b', '（炒）'),
    (r',?\s*deep[- ]?fried\b', '（油炸）'),
    (r',?\s*sauteed\b', '（炒）'),
    (r',?\s*microwaved\b', '（微波）'),
    (r',?\s*smoked\b', '（熏制）'),
    (r',?\s*cured\b', '（腌制）'),
    (r',?\s*dried\b', '（干）'),
    (r',?\s*dehydrated\b', '（脱水）'),
    (r',?\s*frozen\b', '（冷冻）'),
    (r',?\s*canned\b', '（罐装）'),
    (r',?\s*bottled\b', '（瓶装）'),
    (r',?\s*fresh\b', '（鲜）'),
    (r',?\s*ripe\b', '（成熟）'),
    (r',?\s*unripe\b', '（未熟）'),
    (r',?\s*overripe\b', '（过熟）'),
    (r',?\s*immature\b', '（未成熟）'),
    (r',?\s*mature\b', '（成熟）'),
    (r',?\s*prepared\b', '（制备好的）'),
    (r',?\s*unprepared\b', '（未加工的）'),
    (r',?\s*commercial\b', '（商业制作）'),
    (r',?\s*restaurant\b', '（餐厅）'),
    (r',?\s*homeprepare\b', '（家庭制作）'),
    (r',?\s*home prepared\b', '（家庭制作）'),
    (r',?\s*instant\b', '（速食）'),
    (r',?\s*ready-to-serve\b', '（即食）'),
    (r',?\s*ready-to-eat\b', '（即食）'),
    (r',?\s*ready to eat\b', '（即食）'),
    (r',?\s*from concentrate\b', '（浓缩还原）'),
    (r',?\s*not from concentrate\b', '（非浓缩还原）'),
    (r',?\s*shelf[- ]?stable\b', '（常温保存）'),
    (r',?\s*refrigerated\b', '（冷藏）'),
    (r',?\s*drained\b', '（沥干）'),
    (r',?\s*undrained\b', '（未沥干）'),
    (r',?\s*solids and liquids\b', '（带汁）'),
    (r',?\s*with salt\b', '（加盐）'),
    (r',?\s*without salt\b', '（不加盐）'),
    (r',?\s*with added salt\b', '（加盐）'),
    (r',?\s*unsalted\b', '（无盐）'),
    (r',?\s*salted\b', '（加盐）'),
    (r',?\s*sweetened\b', '（加糖）'),
    (r',?\s*unsweetened\b', '（无糖）'),
    (r',?\s*unfortified\b', '（未强化）'),
    (r',?\s*fortified\b', '（强化）'),
    (r',?\s*enriched\b', '（强化）'),
    (r',?\s*unenriched\b', '（未强化）'),
    (r',?\s*bleached\b', '（漂白）'),
    (r',?\s*unbleached\b', '（未漂白）'),
    (r',?\s*whole (?:grain|milk)\b', ''),
    (r',?\s*lowfat\b', '（低脂）'),
    (r',?\s*nonfat\b', '（脱脂）'),
    (r',?\s*fat free\b', '（脱脂）'),
    (r',?\s*skinless\b', '（去皮）'),
    (r',?\s*boneless\b', '（去骨）'),
    (r',?\s*meat only\b', '（纯肉）'),
    (r',?\s*meat and (?:skin|fat)\b', '（带皮）'),
    (r',?\s*with skin\b', '（带皮）'),
    (r',?\s*without skin\b', '（去皮）'),
    (r',?\s*peeled\b', '（去皮）'),
    (r',?\s*unpeeled\b', '（带皮）'),
    (r',?\s*includes skin\b', '（带皮）'),
    (r',?\s*with peel\b', '（带皮）'),
    (r',?\s*seeded\b', '（去籽）'),
    (r',?\s*seedless\b', '（无籽）'),
    (r',?\s*with added vitamin \w+\b', ''),
    (r',?\s*with added .*\b', ''),
    (r',?\s*regular pack\b', ''),
    (r',?\s*solid\b', ''),
    (r',?\s*solids\b', ''),
    (r',?\s* drained solids\b', '（沥干）'),
    (r',?\s*\(.*?\)', ''),
    (r',?\s*0% moisture\)', ''),
    (r',?\s*\d+% (?:lean|fat)\b', ''),
    (r',?\s*select\b', ''),
    (r',?\s*choice\b', ''),
    (r',?\s*prime\b', ''),
    (r',?\s*grade [a-z]+\b', ''),
    (r',?\s*large\b', ''),
    (r',?\s*small\b', ''),
    (r',?\s*medium\b', ''),
    (r',?\s*whole\b', ''),
    (r',?\s*halves\b', ''),
    (r',?\s*pieces\b', '（块）'),
    (r',?\s*chopped\b', '（切碎）'),
    (r',?\s*diced\b', '（切丁）'),
    (r',?\s*sliced\b', '（切片）'),
    (r',?\s*shredded\b', '（切丝）'),
    (r',?\s*grated\b', '（磨碎）'),
    (r',?\s*ground\b', '（磨碎/碎）'),
    (r',?\s*crushed\b', '（压碎）'),
    (r',?\s*mashed\b', '（捣碎）'),
    (r',?\s*pureed\b', '（泥）'),
    (r',?\s*creamy\b', '（细腻型）'),
    (r',?\s*chunky\b', '（颗粒型）'),
    (r',?\s*creamed\b', '（奶油）'),
    (r',?\s*whipped\b', '（打发）'),
    (r',?\s*blanched\b', '（焯）'),
    (r',?\s*battered\b', '（裹面糊）'),
    (r',?\s*breaded\b', '（裹面包糠）'),
    (r',?\s*coated\b', '（裹粉）'),
    (r',?\s*par boiled\b', '（半煮）'),
    (r',?\s*par[- ]?fried\b', '（半炸）'),
    (r',?\s*heated in (?:the )?(?:oven|microwave)\b', '（加热）'),
    (r',?\s*not heated\b', '（未加热）'),
    (r',?\s*unheated\b', '（未加热）'),
    (r',?\s*heated\b', '（加热）'),
    (r',?\s*uncooked\b', ''),
    (r',?\s*thawed\b', '（解冻）'),
    (r',?\s*thawing\b', '（解冻中）'),
    (r',?\s* drained\b', '（沥干）'),
    (r',?\s*rinsed\b', '（冲洗）'),
    (r',?\s*sodium added\b', ''),
    (r',?\s*sugar added\b', ''),
    (r',?\s*added sugar\b', ''),
    (r',?\s*sodium\b', ''),
    (r',?\s*\d+%"? fat\b', ''),
    (r',?\s*\d+% milkfat\b', ''),
    (r',?\s*\d+\.?\d*% milkfat\b', ''),
    (r',?\s*\d+\.?\d*% fat\b', ''),
    (r',?\s*lean only\b', ''),
    (r',?\s*separable lean\b', ''),
    (r',?\s*separable lean and fat\b', ''),
    (r',?\s*trimmed to .*"? fat\b', ''),
    (r',?\s*lip-on\b', ''),
    (r',?\s*bone-in\b', '（带骨）'),
    (r',?\s*yield from\b', ''),
    (r',?\s* NFS\b', ''),
    (r',?\s*NFS\b', ''),
    (r',?\s*NS as to\b', ''),
    (r',?\s*not specified as to\b', ''),
    (r',?\s*type\b', ''),
    (r',?\s*fat not specified\b', ''),
    (r',?\s*fat added\b', ''),
    (r',?\s*part skim\b', '（部分脱脂）'),
    (r',?\s*low moisture\b', '（低水分）'),
    (r',?\s*made from\b', ''),
    (r',?\s*yellow\b', '（黄）'),
    (r',?\s*green\b', '（绿）'),
    (r',?\s*red\b', '（红）'),
    (r',?\s*white\b', '（白）'),
    (r',?\s*dark\b', '（深色）'),
    (r',?\s*light\b', '（浅色）'),
    (r',?\s*extra (?:light|virgin)\b', '（特级）'),
]

# =====================================================================
# 手动翻译（优先级最高，用于精确匹配）
# =====================================================================
MANUAL_TRANSLATIONS: dict[int, str] = {}

def _load_manual_translations() -> dict[int, str]:
    """加载已有的 Foundation Foods 手动翻译。"""
    ff_path = Path("data/usda_nutrition.json")
    if ff_path.exists():
        with open(ff_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {item["fdc_id"]: item["description_zh"] for item in data if item["description_zh"]}
    return {}


def translate_description(desc: str, manual: dict[int, str] | None = None, fdc_id: int = 0) -> str:
    """将 USDA 食物描述翻译为中文。

    策略:
    1. 精确手动翻译（fdc_id 匹配）
    2. 模式翻译（词典匹配 + 状态替换）
    """
    # 1) 手动翻译优先
    if manual and fdc_id in manual:
        return manual[fdc_id]

    text = desc

    # 2) 提取状态信息
    states = []
    remaining = text
    for pattern, zh_state in STATE_PATTERNS:
        m = re.search(pattern, remaining, re.IGNORECASE)
        if m:
            if zh_state:
                states.append(zh_state)
            remaining = remaining[:m.start()] + remaining[m.end():]

    # 清理剩余文本
    remaining = re.sub(r'\s*,\s*$', '', remaining).strip()
    remaining = re.sub(r'\s+', ' ', remaining)
    remaining = re.sub(r'^,\s*', '', remaining)

    # 3) 翻译食物名称
    # 从长到短匹配，避免部分匹配
    sorted_names = sorted(FOOD_NAMES.keys(), key=len, reverse=True)
    zh_parts = []
    matched_span = set()

    lower_remaining = remaining.lower()
    for name in sorted_names:
        idx = lower_remaining.find(name)
        while idx >= 0:
            end = idx + len(name)
            # 检查是否已被更长匹配覆盖
            if not any(s <= idx < e or s < end <= e for s, e in matched_span):
                zh_parts.append((idx, FOOD_NAMES[name]))
                matched_span.add((idx, end))
            idx = lower_remaining.find(name, end)

    if zh_parts:
        # 按位置排序
        zh_parts.sort(key=lambda x: x[0])
        name_zh = ''.join(p[1] for p in zh_parts)
    else:
        # 无法翻译，保留英文
        name_zh = remaining

    # 4) 组合
    result = name_zh
    if states:
        # 去重
        seen = set()
        unique_states = []
        for s in states:
            if s not in seen:
                seen.add(s)
                unique_states.append(s)
        result += ''.join(unique_states)

    return result if result != desc else desc


def main():
    manual = _load_manual_translations()
    print(f"加载 {len(manual)} 条手动翻译")

    # 加载所有数据源
    all_data: list[dict] = []

    # Foundation Foods (已翻译)
    ff_path = Path("data/usda_nutrition.json")
    if ff_path.exists():
        with open(ff_path, "r", encoding="utf-8") as f:
            ff_data = json.load(f)
        all_data.extend(ff_data)
        print(f"Foundation Foods: {len(ff_data)} 条")

    # SR Legacy
    sr_path = Path("data/sr_legacy_raw.json")
    if sr_path.exists():
        with open(sr_path, "r", encoding="utf-8") as f:
            sr_data = json.load(f)
        all_data.extend(sr_data)
        print(f"SR Legacy: {len(sr_data)} 条")

    # FNDDS
    fn_path = Path("data/fndds_raw.json")
    if fn_path.exists():
        with open(fn_path, "r", encoding="utf-8") as f:
            fn_data = json.load(f)
        all_data.extend(fn_data)
        print(f"FNDDS: {len(fn_data)} 条")

    print(f"\n总计 {len(all_data)} 条，开始翻译...")

    # 翻译
    translated = 0
    manual_used = 0
    pattern_used = 0
    for item in all_data:
        if item.get("description_zh"):
            translated += 1
            continue

        fdc_id = item["fdc_id"]
        result = translate_description(item["description"], manual, fdc_id)

        if result != item["description"]:
            pattern_used += 1
        item["description_zh"] = result
        translated += 1

    print(f"翻译完成: {translated}/{len(all_data)}")
    print(f"  手动翻译: {len(manual)}")
    print(f"  模式翻译: {pattern_used}")
    print(f"  保留英文: {len(all_data) - len(manual) - pattern_used}")

    # 按数据源排序（Foundation Foods → SR Legacy → FNDDS）
    def _sort_key(item):
        desc = item.get("description", "")
        # Foundation Foods entries are typically shorter descriptions
        return len(desc)

    all_data.sort(key=_sort_key)

    # 去重（按 fdc_id）
    seen_ids = set()
    unique_data = []
    for item in all_data:
        if item["fdc_id"] not in seen_ids:
            seen_ids.add(item["fdc_id"])
            unique_data.append(item)

    # 写入输出
    out_path = Path("data/usda_nutrition.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(unique_data, f, ensure_ascii=False, indent=2)

    print(f"\n输出: {out_path}")
    print(f"  条目: {len(unique_data)} 条 (去重后)")
    print(f"  文件大小: {out_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
