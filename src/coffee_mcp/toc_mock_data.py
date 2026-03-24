"""Mock data for Coffee Company ToC (consumer-facing) MCP Server.

Simulates the consumer app backend. In production, these functions are
replaced by HTTP calls to the consumer API behind user OAuth authentication.

The default mock user is CC_M_100001 (张三, 金星级).
"""

import time
import uuid

# Default mock user (simulates logged-in consumer)
DEFAULT_USER_ID = "CC_M_100001"

# ---------------------------------------------------------------------------
# ToC User Data (decoupled from B2B mock_data)
# In production: consumer backend resolves user from OAuth token
# ---------------------------------------------------------------------------

TIER_NAMES = {"GREEN": "银星级", "GOLD": "金星级", "DIAMOND": "钻星级"}
TIER_THRESHOLDS = {"GREEN": 0, "GOLD": 125, "DIAMOND": 500}

TOC_USERS = {
    "CC_M_100001": {
        "member_id": "CC_M_100001",
        "name": "张三",
        "member_tier": "GOLD",
        "star_balance": 142,
        "tier_expire_date": "2026-12-31",
        "registration_date": "2024-06-15",
    },
}

TOC_USER_BENEFITS = {
    "CC_M_100001": {
        "welcome_coupon": 3, "birthday_reward": 2, "tier_upgrade_reward": 3,
        "free_drink_coupon": 2, "food_coupon": 1, "customization_coupon": 2,
        "refill_benefit": 2, "early_access": 2,
    },
}

TOC_USER_COUPONS = {
    "CC_M_100001": [
        {"coupon_no": "CN_100001_001", "name": "中杯饮品券", "type": "优惠券",
         "status": "未使用", "valid_end": "2026-04-30", "face_value": 35.0},
        {"coupon_no": "BEN_100001_001", "name": "生日免费饮品", "type": "权益券",
         "status": "可使用", "valid_end": "2026-03-31", "face_value": 0.0},
        {"coupon_no": "BEN_100001_002", "name": "好友邀请奖励", "type": "权益券",
         "status": "可使用", "valid_end": "2026-12-31", "face_value": 30.0},
    ],
}


# ---------------------------------------------------------------------------
# Randomized ID generation (replaces sequential IDs for security)
# ---------------------------------------------------------------------------

def _random_id(prefix: str) -> str:
    """Generate a randomized ID like 'ord_a7f3b2e9' to prevent enumeration."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# Confirmation Token Store (prevents skipping price confirmation)
# ---------------------------------------------------------------------------

# Confirmation token functions delegated to utils (protocol-level security)
from .utils import generate_confirmation_token as _generate_confirmation_token
from .utils import validate_confirmation_token  # re-export for backward compat


# ---------------------------------------------------------------------------
# Idempotency Store (prevents duplicate L3 operations)
# ---------------------------------------------------------------------------

_IDEMPOTENCY_STORE: dict[str, dict] = {}  # key → {result, created_at}
_IDEMPOTENCY_TTL = 86400  # 24 hours
_IDEMPOTENCY_LAST_CLEANUP: float = 0.0


def _cleanup_expired_idempotency() -> None:
    """Remove expired idempotency entries to prevent memory accumulation."""
    global _IDEMPOTENCY_LAST_CLEANUP
    now = time.monotonic()
    if now - _IDEMPOTENCY_LAST_CLEANUP < 300:  # cleanup at most every 5min
        return
    stale = [k for k, v in _IDEMPOTENCY_STORE.items()
             if isinstance(v, dict) and v.get("_created_at")
             and now - v["_created_at"] > _IDEMPOTENCY_TTL]
    for k in stale:
        del _IDEMPOTENCY_STORE[k]
    _IDEMPOTENCY_LAST_CLEANUP = now


def _check_idempotency(key: str) -> dict | None:
    """Check if an operation was already performed. Returns cached result or None."""
    _cleanup_expired_idempotency()
    entry = _IDEMPOTENCY_STORE.get(key)
    if entry is None:
        return None
    # Return a copy without internal metadata
    return {k: v for k, v in entry.items() if not k.startswith("_")}


def _save_idempotency(key: str, result: dict) -> None:
    """Save result for idempotency deduplication with TTL metadata."""
    _IDEMPOTENCY_STORE[key] = {**result, "_created_at": time.monotonic()}


# ---------------------------------------------------------------------------
# PII Masking
# ---------------------------------------------------------------------------

def mask_phone(phone: str) -> str:
    """Mask phone number for list views: 138****1234"""
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[7:]}"
    return phone


# ---------------------------------------------------------------------------
# Stores (门店)
# ---------------------------------------------------------------------------

STORES = [
    {
        "store_id": "ST_SH_001",
        "name": "Coffee Company 南京西路旗舰店",
        "city": "上海",
        "district": "静安区",
        "address": "南京西路1266号恒隆广场B1层",
        "latitude": 31.2286,
        "longitude": 121.4480,
        "phone": "021-62888001",
        "hours": "07:00-22:00",
        "services": ["堂食", "自提", "外送"],
        "features": ["WiFi", "充电", "宠物友好"],
        "status": "营业中",
    },
    {
        "store_id": "ST_SH_002",
        "name": "Coffee Company 陆家嘴中心店",
        "city": "上海",
        "district": "浦东新区",
        "address": "陆家嘴环路1000号上海中心B2层",
        "latitude": 31.2355,
        "longitude": 121.5055,
        "phone": "021-68888002",
        "hours": "07:30-21:30",
        "services": ["堂食", "自提"],
        "features": ["WiFi", "充电"],
        "status": "营业中",
    },
    {
        "store_id": "ST_NJ_001",
        "name": "Coffee Company 新街口德基店",
        "city": "南京",
        "district": "玄武区",
        "address": "中山路18号德基广场1F",
        "latitude": 32.0481,
        "longitude": 118.7882,
        "phone": "025-84888001",
        "hours": "08:00-22:00",
        "services": ["堂食", "自提", "外送"],
        "features": ["WiFi", "充电", "停车场"],
        "status": "营业中",
    },
    {
        "store_id": "ST_SH_003",
        "name": "Coffee Company 徐汇滨江店",
        "city": "上海",
        "district": "徐汇区",
        "address": "龙腾大道2350号西岸梦中心1F",
        "latitude": 31.1710,
        "longitude": 121.4530,
        "phone": "021-64888003",
        "hours": "08:00-21:00",
        "services": ["堂食", "自提", "外送"],
        "features": ["WiFi", "江景座位", "露天区域"],
        "status": "休息中",
    },
]

# ---------------------------------------------------------------------------
# Menu (咖啡菜单)
# ---------------------------------------------------------------------------

MENU_CATEGORIES = [
    {"code": "espresso", "name": "经典浓缩", "sort": 1},
    {"code": "latte", "name": "拿铁系列", "sort": 2},
    {"code": "special", "name": "季节特调", "sort": 3},
    {"code": "tea", "name": "茶饮系列", "sort": 4},
    {"code": "food", "name": "轻食甜点", "sort": 5},
]

SIZE_OPTIONS = {
    "tall": {"name": "中杯", "extra_price": 0},
    "grande": {"name": "大杯", "extra_price": 4},
    "venti": {"name": "超大杯", "extra_price": 7},
}

MILK_OPTIONS = {
    "whole": {"name": "全脂牛奶", "extra_price": 0},
    "skim": {"name": "脱脂牛奶", "extra_price": 0},
    "oat": {"name": "燕麦奶", "extra_price": 5},
    "almond": {"name": "杏仁奶", "extra_price": 5},
    "soy": {"name": "豆奶", "extra_price": 4},
    "coconut": {"name": "椰奶", "extra_price": 5},
}

TEMP_OPTIONS = {
    "hot": {"name": "热"},
    "iced": {"name": "冰"},
    "blended": {"name": "冰沙"},
}

SWEETNESS_OPTIONS = {
    "normal": {"name": "标准糖"},
    "less": {"name": "少糖"},
    "half": {"name": "半糖"},
    "none": {"name": "无糖"},
}

EXTRA_OPTIONS = {
    "extra_shot": {"name": "浓缩+1份", "price": 6},
    "vanilla_syrup": {"name": "香草糖浆", "price": 4},
    "caramel_syrup": {"name": "焦糖糖浆", "price": 4},
    "hazelnut_syrup": {"name": "榛果糖浆", "price": 4},
    "whipped_cream": {"name": "奶油顶", "price": 3},
    "cocoa_powder": {"name": "可可粉", "price": 0},
}

MENU_ITEMS = [
    # -- 经典浓缩 --
    {
        "product_code": "D001",
        "name": "美式咖啡",
        "category": "espresso",
        "base_price": 28,
        "description": "浓缩咖啡加水，纯粹的咖啡风味",
        "customizable": True,
        "available_sizes": ["tall", "grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": [],
        "calories_tall": 10,
        "stars_earn": 3,
        "image": "americano.jpg",
    },
    {
        "product_code": "D002",
        "name": "浓缩咖啡",
        "category": "espresso",
        "base_price": 24,
        "description": "经典意式浓缩，醇厚浓郁",
        "customizable": True,
        "available_sizes": ["tall"],
        "available_temps": ["hot"],
        "available_milks": [],
        "calories_tall": 5,
        "stars_earn": 2,
        "image": "espresso.jpg",
    },
    # -- 拿铁系列 --
    {
        "product_code": "D003",
        "name": "拿铁",
        "category": "latte",
        "base_price": 32,
        "description": "浓缩咖啡与丝滑牛奶的经典组合",
        "customizable": True,
        "available_sizes": ["tall", "grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": ["whole", "skim", "oat", "almond", "soy", "coconut"],
        "calories_tall": 150,
        "stars_earn": 3,
        "image": "latte.jpg",
    },
    {
        "product_code": "D004",
        "name": "香草拿铁",
        "category": "latte",
        "base_price": 35,
        "description": "经典拿铁搭配香草风味，甜蜜丝滑",
        "customizable": True,
        "available_sizes": ["tall", "grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": ["whole", "skim", "oat", "almond", "soy", "coconut"],
        "calories_tall": 190,
        "stars_earn": 4,
        "image": "vanilla_latte.jpg",
    },
    {
        "product_code": "D005",
        "name": "焦糖玛奇朵",
        "category": "latte",
        "base_price": 36,
        "description": "香浓焦糖与浓缩咖啡的层次碰撞",
        "customizable": True,
        "available_sizes": ["tall", "grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": ["whole", "skim", "oat"],
        "calories_tall": 210,
        "stars_earn": 4,
        "image": "caramel_macchiato.jpg",
    },
    # -- 季节特调 --
    {
        "product_code": "D006",
        "name": "樱花白巧拿铁",
        "category": "special",
        "base_price": 42,
        "description": "限定春季！樱花风味白巧克力拿铁，浪漫春日",
        "customizable": True,
        "available_sizes": ["grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": ["whole", "oat"],
        "calories_tall": 280,
        "stars_earn": 5,
        "is_new": True,
        "image": "sakura_latte.jpg",
    },
    {
        "product_code": "D007",
        "name": "生椰冷萃",
        "category": "special",
        "base_price": 38,
        "description": "24小时冷萃咖啡搭配清爽椰奶，清新顺滑",
        "customizable": True,
        "available_sizes": ["grande", "venti"],
        "available_temps": ["iced"],
        "available_milks": ["coconut"],
        "calories_tall": 160,
        "stars_earn": 4,
        "is_new": True,
        "image": "coconut_cold_brew.jpg",
    },
    # -- 茶饮系列 --
    {
        "product_code": "T001",
        "name": "抹茶拿铁",
        "category": "tea",
        "base_price": 34,
        "description": "日式抹茶与牛奶的清新融合",
        "customizable": True,
        "available_sizes": ["tall", "grande", "venti"],
        "available_temps": ["hot", "iced"],
        "available_milks": ["whole", "oat", "almond"],
        "calories_tall": 200,
        "stars_earn": 3,
        "image": "matcha_latte.jpg",
    },
    # -- 轻食甜点 --
    {
        "product_code": "F001",
        "name": "经典可颂",
        "category": "food",
        "base_price": 18,
        "description": "法式黄油可颂，外酥内软",
        "customizable": False,
        "available_sizes": [],
        "available_temps": [],
        "available_milks": [],
        "calories_tall": 280,
        "stars_earn": 2,
        "image": "croissant.jpg",
    },
    {
        "product_code": "F002",
        "name": "蛋黄酥",
        "category": "food",
        "base_price": 15,
        "description": "手工蛋黄酥，咸甜交织",
        "customizable": False,
        "available_sizes": [],
        "available_temps": [],
        "available_milks": [],
        "calories_tall": 220,
        "stars_earn": 2,
        "image": "egg_yolk_pastry.jpg",
    },
]

# ---------------------------------------------------------------------------
# Campaigns (活动日历)
# ---------------------------------------------------------------------------

CAMPAIGNS = [
    {
        "campaign_id": "CAMP_SPRING_2026",
        "title": "春日樱花季",
        "description": "春季限定樱花系列饮品上新，购买任意樱花饮品可获双倍星星",
        "start_date": "2026-03-01",
        "end_date": "2026-04-15",
        "status": "进行中",
        "tags": ["限定", "双倍积星"],
        "image": "spring_sakura.jpg",
    },
    {
        "campaign_id": "CAMP_BOGO_0320",
        "title": "周四买一送一",
        "description": "每周四全场手工饮品买一送一（限大杯及以上）",
        "start_date": "2026-03-01",
        "end_date": "2026-03-31",
        "status": "进行中",
        "tags": ["买一送一"],
        "image": "bogo_thursday.jpg",
    },
    {
        "campaign_id": "CAMP_NEW_MEMBER",
        "title": "新会员注册礼",
        "description": "新注册会员可免费领取中杯饮品券一张",
        "start_date": "2026-01-01",
        "end_date": "2026-12-31",
        "status": "进行中",
        "tags": ["新人"],
        "image": "new_member.jpg",
    },
    {
        "campaign_id": "CAMP_EASTER_2026",
        "title": "复活节彩蛋杯",
        "description": "复活节限定彩蛋杯，购买指定饮品获赠限量杯套",
        "start_date": "2026-04-01",
        "end_date": "2026-04-06",
        "status": "未开始",
        "tags": ["限定", "周边"],
        "image": "easter_cup.jpg",
    },
    {
        "campaign_id": "CAMP_CNY_2026",
        "title": "新年红包雨",
        "description": "新年期间下单随机获得最高66元优惠券红包",
        "start_date": "2026-01-28",
        "end_date": "2026-02-15",
        "status": "已结束",
        "tags": ["红包", "优惠券"],
        "image": "cny_red_packet.jpg",
    },
]

# ---------------------------------------------------------------------------
# Available Coupons (可领取的优惠券)
# ---------------------------------------------------------------------------

AVAILABLE_COUPONS = [
    {
        "coupon_id": "AVL_001",
        "name": "拿铁系列立减5元",
        "description": "拿铁系列任意饮品立减5元",
        "discount_value": 5.0,
        "min_order": 30.0,
        "valid_days": 7,
        "status": "可领取",
        "applicable": ["D003", "D004", "D005"],
        "image": "coupon_latte_5off.jpg",
    },
    {
        "coupon_id": "AVL_002",
        "name": "满50减10元",
        "description": "订单满50元立减10元",
        "discount_value": 10.0,
        "min_order": 50.0,
        "valid_days": 14,
        "status": "可领取",
        "applicable": [],
        "image": "coupon_50off10.jpg",
    },
    {
        "coupon_id": "AVL_003",
        "name": "免费升杯券",
        "description": "中杯免费升大杯",
        "discount_value": 4.0,
        "min_order": 0.0,
        "valid_days": 7,
        "status": "可领取",
        "applicable": [],
        "image": "coupon_upgrade.jpg",
    },
    {
        "coupon_id": "AVL_004",
        "name": "春日特调9折券",
        "description": "季节特调系列享9折优惠",
        "discount_value": 0.0,
        "discount_rate": 0.9,
        "min_order": 0.0,
        "valid_days": 14,
        "status": "已领取",
        "applicable": ["D006", "D007"],
        "image": "coupon_special_90.jpg",
    },
]

# ---------------------------------------------------------------------------
# Stars Mall (积分商城)
# ---------------------------------------------------------------------------

STARS_MALL = [
    {
        "product_code": "SM_001",
        "name": "中杯饮品兑换券",
        "description": "可兑换任意中杯手工饮品一杯",
        "stars_cost": 100,
        "category": "饮品券",
        "stock": 999,
        "image": "stars_tall_drink.jpg",
    },
    {
        "product_code": "SM_002",
        "name": "经典可颂兑换券",
        "description": "可兑换经典可颂一个",
        "stars_cost": 50,
        "category": "食品券",
        "stock": 200,
        "image": "stars_croissant.jpg",
    },
    {
        "product_code": "SM_003",
        "name": "品牌随行杯",
        "description": "Coffee Company 限量联名随行杯 355ml",
        "stars_cost": 300,
        "category": "周边",
        "stock": 50,
        "image": "stars_tumbler.jpg",
    },
    {
        "product_code": "SM_004",
        "name": "升杯券 x3",
        "description": "三张免费升杯券，中杯升大杯",
        "stars_cost": 30,
        "category": "饮品券",
        "stock": 999,
        "image": "stars_upgrade_x3.jpg",
    },
    {
        "product_code": "SM_005",
        "name": "双倍积星卡（7天）",
        "description": "激活后7天内所有消费获双倍星星",
        "stars_cost": 150,
        "category": "权益卡",
        "stock": 100,
        "image": "stars_double.jpg",
    },
]

# ---------------------------------------------------------------------------
# Orders (订单)
# ---------------------------------------------------------------------------

ORDERS = {
    "CC_M_100001": [
        {
            "order_id": "TOC_ORD_20260318001",
            "store_id": "ST_SH_001",
            "store_name": "Coffee Company 南京西路旗舰店",
            "items": [
                {"name": "拿铁", "size": "大杯", "milk": "燕麦奶",
                 "temp": "冰", "price": 41.0, "quantity": 1},
                {"name": "经典可颂", "price": 18.0, "quantity": 1},
            ],
            "original_price": 59.0,
            "discount": 5.0,
            "coupon_used": "拿铁系列立减5元",
            "final_price": 54.0,
            "stars_earned": 5,
            "pickup_type": "自提",
            "status": "已完成",
            "status_code": 5,
            "order_time": "2026-03-18 09:15:00",
            "complete_time": "2026-03-18 09:28:00",
            "pay_method": "微信支付",
        },
        {
            "order_id": "TOC_ORD_20260320002",
            "store_id": "ST_SH_001",
            "store_name": "Coffee Company 南京西路旗舰店",
            "items": [
                {"name": "樱花白巧拿铁", "size": "超大杯", "milk": "燕麦奶",
                 "temp": "冰", "price": 54.0, "quantity": 1},
            ],
            "original_price": 54.0,
            "discount": 0.0,
            "coupon_used": None,
            "final_price": 54.0,
            "stars_earned": 10,
            "pickup_type": "外送",
            "delivery_address": "南京西路1515号静安嘉里中心2号楼15F",
            "delivery_fee": 5.0,
            "status": "制作中",
            "status_code": 2,
            "order_time": "2026-03-20 14:30:00",
            "complete_time": None,
            "pay_method": "支付宝",
        },
    ],
}

ORDER_STATUS_NAMES = {
    0: "待支付", 1: "已支付", 2: "制作中", 3: "待自提",
    4: "配送中", 5: "已完成", 6: "已取消", 7: "已退款",
}

# ---------------------------------------------------------------------------
# Delivery Addresses (配送地址) — uses randomized IDs
# ---------------------------------------------------------------------------

DELIVERY_ADDRESSES = {
    "CC_M_100001": [
        {
            "address_id": "addr_f7a3c1e2",
            "contact_name": "张三",
            "phone": "13812341234",
            "city": "上海",
            "address": "南京西路1515号静安嘉里中心",
            "address_detail": "2号楼15F",
            "is_default": True,
        },
        {
            "address_id": "addr_b5d9e4f8",
            "contact_name": "张三",
            "phone": "13812341234",
            "city": "上海",
            "address": "陆家嘴环路958号华能联合大厦",
            "address_detail": "20F",
            "is_default": False,
        },
    ],
}


# ---------------------------------------------------------------------------
# ToC Query Functions
# ---------------------------------------------------------------------------

def get_current_user(user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Resolve logged-in user. In production: from OAuth token."""
    return TOC_USERS.get(user_id)


def my_account(user_id: str = DEFAULT_USER_ID) -> dict | None:
    """User's account summary: tier + stars + benefits count."""
    user = get_current_user(user_id)
    if not user:
        return None
    # Build tier info from ToC-local data
    current_tier = user["member_tier"]
    tiers = list(TIER_THRESHOLDS.keys())
    idx = tiers.index(current_tier)
    next_tier = tiers[idx + 1] if idx + 1 < len(tiers) else None
    stars_to_next = (TIER_THRESHOLDS[next_tier] - user["star_balance"]) if next_tier else 0
    tier_info = {
        "member_tier": current_tier,
        "tier_name": TIER_NAMES[current_tier],
        "star_balance": user["star_balance"],
        "tier_expire_date": user["tier_expire_date"],
        "next_tier": next_tier,
        "next_tier_name": TIER_NAMES.get(next_tier, ""),
        "stars_to_next": max(0, stars_to_next),
    }
    benefits = TOC_USER_BENEFITS.get(user_id, {})
    active_benefits = sum(1 for v in benefits.values() if v == 2)
    coupons = TOC_USER_COUPONS.get(user_id, [])
    return {
        "name": user["name"],
        "tier_info": tier_info,
        "active_benefits": active_benefits,
        "coupon_count": len(coupons),
        "registration_date": user["registration_date"],
    }


def my_coupons(user_id: str = DEFAULT_USER_ID, status: str | None = None) -> list[dict]:
    """User's coupon list from ToC-local data."""
    items = TOC_USER_COUPONS.get(user_id, [])
    if status == "valid":
        items = [i for i in items if i["status"] in ("未使用", "可使用")]
    elif status == "used":
        items = [i for i in items if i["status"] in ("已使用", "已使用/已过期")]
    return items


def my_orders(user_id: str = DEFAULT_USER_ID, limit: int = 10) -> list[dict]:
    """User's recent orders."""
    return ORDERS.get(user_id, [])[:limit]


def campaign_calendar(month: str | None = None) -> list[dict]:
    """Current campaigns. In production: filters by month."""
    return CAMPAIGNS


def available_coupons() -> list[dict]:
    """Coupons available to claim."""
    return AVAILABLE_COUPONS


def claim_all_coupons(user_id: str = DEFAULT_USER_ID) -> dict:
    """Claim all available coupons. Returns summary."""
    claimable = [c for c in AVAILABLE_COUPONS if c["status"] == "可领取"]
    return {
        "claimed_count": len(claimable),
        "already_claimed": sum(1 for c in AVAILABLE_COUPONS if c["status"] == "已领取"),
        "claimed_coupons": [{"name": c["name"], "valid_days": c["valid_days"]} for c in claimable],
    }


def nearby_stores(city: str | None = None, keyword: str | None = None) -> list[dict]:
    """Search stores by city or keyword."""
    results = STORES
    if city:
        results = [s for s in results if city in s["city"]]
    if keyword:
        results = [s for s in results if keyword in s["name"] or keyword in s["address"]]
    return results


def store_detail(store_id: str) -> dict | None:
    """Single store detail."""
    for s in STORES:
        if s["store_id"] == store_id:
            return s
    return None


def browse_menu(store_id: str) -> dict:
    """Menu for a specific store. Returns categories + items."""
    store = store_detail(store_id)
    if not store:
        return {"error": f"门店 {store_id} 不存在"}
    # In production: menu varies by store. Mock returns full menu.
    available = [item for item in MENU_ITEMS if store["status"] == "营业中"]
    return {
        "store_name": store["name"],
        "categories": MENU_CATEGORIES,
        "items": available,
    }


def drink_detail(product_code: str) -> dict | None:
    """Single menu item with full customization options."""
    for item in MENU_ITEMS:
        if item["product_code"] == product_code:
            result = {**item}
            if item["customizable"]:
                result["size_options"] = {
                    k: v for k, v in SIZE_OPTIONS.items()
                    if k in item.get("available_sizes", [])
                }
                result["milk_options"] = {
                    k: v for k, v in MILK_OPTIONS.items()
                    if k in item.get("available_milks", [])
                }
                result["temp_options"] = {
                    k: v for k, v in TEMP_OPTIONS.items()
                    if k in item.get("available_temps", [])
                }
                result["sweetness_options"] = SWEETNESS_OPTIONS
                result["extra_options"] = EXTRA_OPTIONS
            return result
    return None


def nutrition_info(product_code: str) -> dict | None:
    """Nutrition info for a menu item."""
    for item in MENU_ITEMS:
        if item["product_code"] == product_code:
            base_cal = item.get("calories_tall", 0)
            return {
                "name": item["name"],
                "serving": "中杯 (Tall)",
                "calories": base_cal,
                "protein": round(base_cal * 0.06, 1),
                "fat": round(base_cal * 0.04, 1),
                "carbs": round(base_cal * 0.12, 1),
                "sugar": round(base_cal * 0.08, 1),
                "sodium": round(base_cal * 0.3, 0),
                "caffeine": 150 if item["category"] in ("espresso", "latte", "special") else 30,
            }
    return None


def stars_mall_products(category: str | None = None) -> list[dict]:
    """Stars mall product listing."""
    products = STARS_MALL
    if category:
        products = [p for p in products if category in p["category"]]
    return products


def stars_product_detail(product_code: str) -> dict | None:
    """Single stars mall product detail."""
    for p in STARS_MALL:
        if p["product_code"] == product_code:
            return p
    return None


def stars_redeem(product_code: str, user_id: str = DEFAULT_USER_ID,
                 idempotency_key: str | None = None) -> dict:
    """Redeem stars for a product. Supports idempotency."""
    # Check idempotency
    if idempotency_key:
        idem_key = f"stars_redeem:{user_id}:{idempotency_key}"
        cached = _check_idempotency(idem_key)
        if cached:
            return cached

    product = stars_product_detail(product_code)
    if not product:
        return {"success": False, "message": f"商品 {product_code} 不存在"}
    user = get_current_user(user_id)
    if not user:
        return {"success": False, "message": "用户不存在"}
    if user["star_balance"] < product["stars_cost"]:
        return {
            "success": False,
            "message": f"星星不足，需要 {product['stars_cost']} 颗，当前仅 {user['star_balance']} 颗",
        }
    result = {
        "success": True,
        "redeem_id": _random_id("rdm"),
        "product_name": product["name"],
        "stars_cost": product["stars_cost"],
        "stars_remaining": user["star_balance"] - product["stars_cost"],
        "message": f"兑换成功！已消耗 {product['stars_cost']} 颗星星",
    }

    # Save idempotency
    if idempotency_key:
        _save_idempotency(f"stars_redeem:{user_id}:{idempotency_key}", result)

    return result


def calculate_price(store_id: str, items: list[dict],
                    coupon_code: str | None = None) -> dict:
    """Calculate order price with optional coupon. Returns confirmation_token."""
    store = store_detail(store_id)
    if not store:
        return {"error": f"门店 {store_id} 不存在"}

    total = 0
    item_details = []
    for cart_item in items:
        menu_item = drink_detail(cart_item["product_code"])
        if not menu_item:
            return {"error": f"商品 {cart_item['product_code']} 不存在"}
        price = menu_item["base_price"]
        size = cart_item.get("size", "tall")
        if size in SIZE_OPTIONS:
            price += SIZE_OPTIONS[size]["extra_price"]
        milk = cart_item.get("milk")
        if milk and milk in MILK_OPTIONS:
            price += MILK_OPTIONS[milk]["extra_price"]
        for extra in cart_item.get("extras", []):
            if extra in EXTRA_OPTIONS:
                price += EXTRA_OPTIONS[extra]["price"]
        qty = cart_item.get("quantity", 1)
        line_total = price * qty
        total += line_total
        item_details.append({
            "name": menu_item["name"],
            "size": SIZE_OPTIONS.get(size, {}).get("name", size),
            "unit_price": price,
            "quantity": qty,
            "line_total": line_total,
        })

    discount = 0.0
    coupon_name = None
    if coupon_code:
        for c in AVAILABLE_COUPONS:
            if c["coupon_id"] == coupon_code and total >= c["min_order"]:
                if c.get("discount_value"):
                    discount = c["discount_value"]
                elif c.get("discount_rate"):
                    discount = round(total * (1 - c["discount_rate"]), 2)
                coupon_name = c["name"]
                break

    delivery_fee = 5.0 if "外送" in store.get("services", []) else 0.0
    packing_fee = len(items) * 1.0

    # Generate confirmation token for create_order
    confirmation_token = _generate_confirmation_token()

    return {
        "items": item_details,
        "original_price": total,
        "discount": discount,
        "coupon_name": coupon_name,
        "delivery_fee": delivery_fee,
        "packing_fee": packing_fee,
        "final_price": total - discount + delivery_fee + packing_fee,
        "confirmation_token": confirmation_token,
    }


def create_order(store_id: str, items: list[dict], pickup_type: str,
                 coupon_code: str | None = None,
                 address_id: str | None = None,
                 user_id: str = DEFAULT_USER_ID,
                 idempotency_key: str | None = None) -> dict:
    """Create an order. Returns order confirmation. Supports idempotency."""
    # Check idempotency
    if idempotency_key:
        idem_key = f"create_order:{user_id}:{idempotency_key}"
        cached = _check_idempotency(idem_key)
        if cached:
            return cached

    price_result = calculate_price(store_id, items, coupon_code)
    if "error" in price_result:
        return price_result

    store = store_detail(store_id)
    order_id = _random_id("ord")

    result = {
        "order_id": order_id,
        "store_name": store["name"] if store else store_id,
        "pickup_type": pickup_type,
        "items": price_result["items"],
        "final_price": price_result["final_price"],
        "discount": price_result["discount"],
        "status": "待支付",
        "stars_will_earn": sum(
            (drink_detail(i["product_code"]) or {}).get("stars_earn", 0) * i.get("quantity", 1)
            for i in items
        ),
        "pay_url": f"https://pay.coffeecompany.com/order/{order_id}",
        "message": "请在15分钟内完成支付",
    }

    if pickup_type == "外送" and address_id:
        addrs = DELIVERY_ADDRESSES.get(user_id, [])
        addr = next((a for a in addrs if a["address_id"] == address_id), None)
        if addr:
            result["delivery_address"] = f"{addr['address']} {addr['address_detail']}"
            result["delivery_fee"] = price_result["delivery_fee"]

    # Save idempotency
    if idempotency_key:
        _save_idempotency(f"create_order:{user_id}:{idempotency_key}", result)

    return result


def order_status(order_id: str, user_id: str = DEFAULT_USER_ID) -> dict | None:
    """Query single order status."""
    for order in ORDERS.get(user_id, []):
        if order["order_id"] == order_id:
            return order
    return None


def delivery_addresses(user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """User's delivery addresses."""
    return DELIVERY_ADDRESSES.get(user_id, [])


def create_address(city: str, address: str, address_detail: str,
                   contact_name: str, phone: str,
                   user_id: str = DEFAULT_USER_ID) -> dict:
    """Create a new delivery address with randomized ID."""
    addr_list = DELIVERY_ADDRESSES.setdefault(user_id, [])
    new_addr = {
        "address_id": _random_id("addr"),
        "contact_name": contact_name,
        "phone": phone,
        "city": city,
        "address": address,
        "address_detail": address_detail,
        "is_default": len(addr_list) == 0,
    }
    addr_list.append(new_addr)
    return new_addr


def store_coupons(store_id: str, user_id: str = DEFAULT_USER_ID) -> list[dict]:
    """Coupons usable at a specific store. Combines user coupons with store menu."""
    user_coupons = my_coupons(user_id, status="valid")
    store = store_detail(store_id)
    if not store or store["status"] != "营业中":
        return []
    return [
        {**c, "usable_at_store": True}
        for c in user_coupons
    ]
