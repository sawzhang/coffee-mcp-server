"""Mock data simulating Starbucks Open Platform API responses."""

import math
import random

STORES = [
    {
        "store_id": "SH-LJZ-001",
        "name": "星巴克(陆家嘴中心店)",
        "city": "上海",
        "district": "浦东新区",
        "address": "陆家嘴环路1000号恒生银行大厦1层",
        "latitude": 31.2397,
        "longitude": 121.4998,
        "open_time": "07:00",
        "close_time": "22:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "021-50471234",
    },
    {
        "store_id": "SH-LFS-002",
        "name": "星巴克(来福士广场店)",
        "city": "上海",
        "district": "黄浦区",
        "address": "西藏中路268号来福士广场1层",
        "latitude": 31.2322,
        "longitude": 121.4737,
        "open_time": "07:30",
        "close_time": "22:30",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "021-63401234",
    },
    {
        "store_id": "SH-JAT-003",
        "name": "星巴克(静安寺店)",
        "city": "上海",
        "district": "静安区",
        "address": "南京西路1788号久光百货B1层",
        "latitude": 31.2248,
        "longitude": 121.4448,
        "open_time": "08:00",
        "close_time": "22:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "021-62881234",
    },
    {
        "store_id": "BJ-GML-001",
        "name": "星巴克(国贸商城店)",
        "city": "北京",
        "district": "朝阳区",
        "address": "建国门外大街1号国贸商城B1层",
        "latitude": 39.9087,
        "longitude": 116.4594,
        "open_time": "07:00",
        "close_time": "22:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "010-65051234",
    },
    {
        "store_id": "BJ-SLT-002",
        "name": "星巴克(三里屯太古里店)",
        "city": "北京",
        "district": "朝阳区",
        "address": "三里屯路19号三里屯太古里南区1层",
        "latitude": 39.9340,
        "longitude": 116.4537,
        "open_time": "07:30",
        "close_time": "23:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "010-64171234",
    },
    {
        "store_id": "GZ-TH-001",
        "name": "星巴克(天河城店)",
        "city": "广州",
        "district": "天河区",
        "address": "天河路208号天河城B1层",
        "latitude": 23.1317,
        "longitude": 113.3290,
        "open_time": "08:00",
        "close_time": "22:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "020-85501234",
    },
    {
        "store_id": "SZ-FT-001",
        "name": "星巴克(福田COCO Park店)",
        "city": "深圳",
        "district": "福田区",
        "address": "福华三路与金田路交汇处COCO Park 1层",
        "latitude": 22.5332,
        "longitude": 114.0546,
        "open_time": "07:30",
        "close_time": "22:30",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "0755-83201234",
    },
    {
        "store_id": "HZ-XH-001",
        "name": "星巴克(西湖银泰店)",
        "city": "杭州",
        "district": "上城区",
        "address": "延安路98号银泰百货1层",
        "latitude": 30.2592,
        "longitude": 120.1690,
        "open_time": "07:30",
        "close_time": "22:00",
        "has_seating": True,
        "drivethru": False,
        "delivery": True,
        "mobile_order": True,
        "phone": "0571-87801234",
    },
]

MENU_CATEGORIES = {
    "espresso": "浓缩咖啡饮品",
    "cold_brew": "冷萃咖啡",
    "frappuccino": "星冰乐",
    "tea": "茶饮",
    "seasonal": "当季限定",
    "food": "轻食糕点",
}

PRODUCTS = [
    {
        "product_id": "ESP-001",
        "name": "馥芮白",
        "name_en": "Flat White",
        "category": "espresso",
        "description": "以 Ristretto 浓缩为基底，融合绵密的蒸奶，口感顺滑醇厚",
        "sizes": {
            "tall": {"name": "中杯", "price": 36.0},
            "grande": {"name": "大杯", "price": 40.0},
            "venti": {"name": "超大杯", "price": 44.0},
        },
        "customizations": {
            "milk": ["全脂奶", "脱脂奶", "燕麦奶(+5元)", "椰奶(+5元)", "杏仁奶(+5元)"],
            "temperature": ["热", "冰", "温"],
            "sweetness": ["标准", "少糖", "半糖", "无糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 120, "grande": 170, "venti": 220},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "ESP-002",
        "name": "拿铁",
        "name_en": "Caffè Latte",
        "category": "espresso",
        "description": "浓缩咖啡与蒸奶的经典搭配，温润柔和",
        "sizes": {
            "tall": {"name": "中杯", "price": 33.0},
            "grande": {"name": "大杯", "price": 37.0},
            "venti": {"name": "超大杯", "price": 41.0},
        },
        "customizations": {
            "milk": ["全脂奶", "脱脂奶", "燕麦奶(+5元)", "椰奶(+5元)", "杏仁奶(+5元)"],
            "temperature": ["热", "冰", "温"],
            "sweetness": ["标准", "少糖", "半糖", "无糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 150, "grande": 190, "venti": 250},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "ESP-003",
        "name": "美式咖啡",
        "name_en": "Caffè Americano",
        "category": "espresso",
        "description": "浓缩咖啡加水，简单纯粹的咖啡风味",
        "sizes": {
            "tall": {"name": "中杯", "price": 28.0},
            "grande": {"name": "大杯", "price": 32.0},
            "venti": {"name": "超大杯", "price": 36.0},
        },
        "customizations": {
            "milk": [],
            "temperature": ["热", "冰"],
            "sweetness": ["标准", "无糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 10, "grande": 15, "venti": 20},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "ESP-004",
        "name": "焦糖玛奇朵",
        "name_en": "Caramel Macchiato",
        "category": "espresso",
        "description": "香草风味糖浆、蒸奶，淋上浓缩咖啡与焦糖酱",
        "sizes": {
            "tall": {"name": "中杯", "price": 36.0},
            "grande": {"name": "大杯", "price": 40.0},
            "venti": {"name": "超大杯", "price": 44.0},
        },
        "customizations": {
            "milk": ["全脂奶", "脱脂奶", "燕麦奶(+5元)", "椰奶(+5元)"],
            "temperature": ["热", "冰"],
            "sweetness": ["标准", "少糖", "半糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 190, "grande": 250, "venti": 310},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "CB-001",
        "name": "冷萃咖啡",
        "name_en": "Cold Brew",
        "category": "cold_brew",
        "description": "精选咖啡豆经低温长时间萃取，口感柔顺低酸",
        "sizes": {
            "tall": {"name": "中杯", "price": 34.0},
            "grande": {"name": "大杯", "price": 38.0},
            "venti": {"name": "超大杯", "price": 42.0},
        },
        "customizations": {
            "milk": ["全脂奶", "燕麦奶(+5元)"],
            "temperature": ["冰"],
            "sweetness": ["标准", "无糖"],
            "extra_shot": False,
        },
        "calories": {"tall": 5, "grande": 5, "venti": 10},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "FRAP-001",
        "name": "摩卡星冰乐",
        "name_en": "Mocha Frappuccino",
        "category": "frappuccino",
        "description": "浓缩咖啡、摩卡酱与牛奶冰沙的完美融合",
        "sizes": {
            "tall": {"name": "中杯", "price": 37.0},
            "grande": {"name": "大杯", "price": 41.0},
            "venti": {"name": "超大杯", "price": 45.0},
        },
        "customizations": {
            "milk": ["全脂奶", "脱脂奶", "燕麦奶(+5元)"],
            "temperature": ["冰"],
            "sweetness": ["标准", "少糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 280, "grande": 370, "venti": 460},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "TEA-001",
        "name": "抹茶拿铁",
        "name_en": "Matcha Latte",
        "category": "tea",
        "description": "日式抹茶与蒸奶的细腻结合，茶香浓郁",
        "sizes": {
            "tall": {"name": "中杯", "price": 35.0},
            "grande": {"name": "大杯", "price": 39.0},
            "venti": {"name": "超大杯", "price": 43.0},
        },
        "customizations": {
            "milk": ["全脂奶", "脱脂奶", "燕麦奶(+5元)", "椰奶(+5元)"],
            "temperature": ["热", "冰"],
            "sweetness": ["标准", "少糖", "半糖", "无糖"],
            "extra_shot": False,
        },
        "calories": {"tall": 190, "grande": 240, "venti": 320},
        "is_new": False,
        "is_seasonal": False,
    },
    {
        "product_id": "SEA-001",
        "name": "樱花初绽拿铁",
        "name_en": "Sakura Blossom Latte",
        "category": "seasonal",
        "description": "2026春季限定 | 樱花风味糖浆与蒸奶的浪漫邂逅，入口花香清甜",
        "sizes": {
            "tall": {"name": "中杯", "price": 39.0},
            "grande": {"name": "大杯", "price": 43.0},
            "venti": {"name": "超大杯", "price": 47.0},
        },
        "customizations": {
            "milk": ["全脂奶", "燕麦奶(+5元)", "椰奶(+5元)"],
            "temperature": ["热", "冰"],
            "sweetness": ["标准", "少糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 210, "grande": 270, "venti": 350},
        "is_new": True,
        "is_seasonal": True,
    },
    {
        "product_id": "SEA-002",
        "name": "生椰拿铁",
        "name_en": "Coconut Latte",
        "category": "seasonal",
        "description": "2026春季限定 | 椰浆与浓缩咖啡的热带风情，清爽回甘",
        "sizes": {
            "tall": {"name": "中杯", "price": 38.0},
            "grande": {"name": "大杯", "price": 42.0},
            "venti": {"name": "超大杯", "price": 46.0},
        },
        "customizations": {
            "milk": [],
            "temperature": ["热", "冰"],
            "sweetness": ["标准", "少糖", "无糖"],
            "extra_shot": True,
        },
        "calories": {"tall": 180, "grande": 230, "venti": 300},
        "is_new": True,
        "is_seasonal": True,
    },
    {
        "product_id": "FOOD-001",
        "name": "芝士牛肉可颂",
        "name_en": "Cheese Beef Croissant",
        "category": "food",
        "description": "酥脆可颂搭配芝士与牛肉，香气四溢",
        "sizes": {
            "single": {"name": "单份", "price": 28.0},
        },
        "customizations": {"milk": [], "temperature": ["加热", "常温"], "sweetness": [], "extra_shot": False},
        "calories": {"single": 380},
        "is_new": False,
        "is_seasonal": False,
    },
]

PROMOTIONS = [
    {
        "promo_id": "P2026-SPRING-001",
        "title": "樱花季买一送一",
        "description": "每周三14:00-17:00，购买任意春季限定饮品即享买一送一",
        "valid_from": "2026-03-01",
        "valid_to": "2026-04-15",
        "applicable_products": ["SEA-001", "SEA-002"],
        "conditions": "限堂食和自取，不与其他优惠叠加",
    },
    {
        "promo_id": "P2026-SPRING-002",
        "title": "早安咖啡半价",
        "description": "工作日7:00-9:00，任意中杯浓缩咖啡饮品半价",
        "valid_from": "2026-03-01",
        "valid_to": "2026-03-31",
        "applicable_products": ["ESP-001", "ESP-002", "ESP-003", "ESP-004"],
        "conditions": "仅限中杯，需出示星享俱乐部会员码",
    },
    {
        "promo_id": "P2026-SPRING-003",
        "title": "新会员首杯免费",
        "description": "新注册星享俱乐部会员，首杯中杯饮品免费",
        "valid_from": "2026-01-01",
        "valid_to": "2026-12-31",
        "applicable_products": [],
        "conditions": "仅限中杯，每位新会员限享一次",
    },
]

# Valid demo API keys
VALID_API_KEYS = {"demo-key-001", "sbux-test-2026", "starbucks-dev"}


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance between two points in meters."""
    R = 6371000
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def search_stores(
    city: str | None = None,
    keyword: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius: float = 3000,
) -> list[dict]:
    results = []
    for store in STORES:
        if city and city not in store["city"]:
            continue
        if keyword and keyword not in store["name"] and keyword not in store["address"] and keyword not in store["district"]:
            continue
        s = dict(store)
        if latitude is not None and longitude is not None:
            s["distance"] = round(haversine_distance(latitude, longitude, store["latitude"], store["longitude"]))
            if s["distance"] > radius:
                continue
        else:
            s["distance"] = random.randint(200, 2500)
        results.append(s)
    results.sort(key=lambda x: x["distance"])
    return results


def get_store(store_id: str) -> dict | None:
    for store in STORES:
        if store["store_id"] == store_id:
            return store
    return None


def get_menu(category: str | None = None) -> list[dict]:
    if category:
        return [p for p in PRODUCTS if p["category"] == category]
    return PRODUCTS


def get_product(product_id: str | None = None, name: str | None = None) -> dict | None:
    for p in PRODUCTS:
        if product_id and p["product_id"] == product_id:
            return p
        if name and (name in p["name"] or name in p["name_en"].lower()):
            return p
    return None


def check_inventory(store_id: str, product_id: str | None = None) -> list[dict]:
    """Simulate inventory check. Randomly mark ~10% as out of stock."""
    products = PRODUCTS if not product_id else [p for p in PRODUCTS if p["product_id"] == product_id]
    results = []
    for p in products:
        random.seed(f"{store_id}-{p['product_id']}")
        in_stock = random.random() > 0.1
        results.append({
            "product_id": p["product_id"],
            "name": p["name"],
            "in_stock": in_stock,
            "note": "" if in_stock else "今日原料不足，暂时售罄",
        })
    return results


def get_promotions() -> list[dict]:
    return PROMOTIONS


def validate_api_key(key: str | None) -> bool:
    return key in VALID_API_KEYS
