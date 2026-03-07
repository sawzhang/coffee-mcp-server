"""Mock data simulating Coffee Company B2B Open Platform (openapi.coffeecompany.com) responses.

All data structures mirror the real HTTP API response schemas.
In production, these functions are replaced by actual HTTP calls to the backend
(internal network, behind Kong).
"""

# ---------------------------------------------------------------------------
# B2B Partners (Kong Consumers)
# ---------------------------------------------------------------------------

CONSUMERS = {
    "nio": {
        "username": "nio",
        "custom_id": "NIO_PARTNER_001",
        "groups": ["member-read", "coupon-read", "assets-read", "cashier-read"],
        "display_name": "蔚来汽车",
    },
    "qwen": {
        "username": "qwen",
        "custom_id": "QWEN_ENT_001",
        "groups": ["member-read", "member-write", "coupon-read", "coupon-write",
                   "equity-read", "equity-write", "assets-read"],
        "display_name": "通义千问(企业版)",
    },
    "fliggy": {
        "username": "fliggy",
        "custom_id": "FLIGGY_3PP",
        "groups": ["member-read", "member-write", "equity-read", "equity-write",
                   "benefit-write", "assets-read"],
        "display_name": "飞猪旅行",
    },
    "demo": {
        "username": "demo",
        "custom_id": "DEMO_001",
        "groups": ["member-read", "coupon-read", "equity-read", "assets-read",
                   "cashier-read"],
        "display_name": "Demo Partner",
    },
}

# ---------------------------------------------------------------------------
# Members (会员服务 2.0)
# ---------------------------------------------------------------------------

MEMBERS = [
    {
        "member_id": "CC_M_100001",
        "open_id": "oABC123456789",
        "mobile": "138****1234",
        "name": "张三",
        "channel": "NIO",
        "member_tier": "GOLD",
        "star_balance": 142,
        "tier_expire_date": "2026-12-31",
        "registration_date": "2024-06-15",
        "birthday": "1990-03-15",
        "gender": "M",
    },
    {
        "member_id": "CC_M_100002",
        "open_id": "oDEF987654321",
        "mobile": "139****5678",
        "name": "李四",
        "channel": "FLIGGY",
        "member_tier": "GREEN",
        "star_balance": 28,
        "tier_expire_date": "2026-09-30",
        "registration_date": "2025-11-20",
        "birthday": "1995-08-22",
        "gender": "F",
    },
    {
        "member_id": "CC_M_100003",
        "open_id": "oGHI456789012",
        "mobile": "137****9012",
        "name": "王五",
        "channel": "QWEN",
        "member_tier": "DIAMOND",
        "star_balance": 520,
        "tier_expire_date": "2027-03-31",
        "registration_date": "2023-01-10",
        "birthday": "1988-12-01",
        "gender": "M",
    },
]

TIER_THRESHOLDS = {"GREEN": 0, "GOLD": 125, "DIAMOND": 500}
TIER_NAMES = {"GREEN": "银星级", "GOLD": "金星级", "DIAMOND": "钻星级"}

MEMBER_BENEFITS = {
    "CC_M_100001": {
        "welcome_coupon": 3,       # 3=grayed (已领取)
        "birthday_reward": 2,      # 2=active (可领取)
        "tier_upgrade_reward": 3,
        "free_drink_coupon": 2,
        "food_coupon": 1,          # 1=locked (未解锁)
        "customization_coupon": 2,
        "refill_benefit": 2,
        "early_access": 2,
    },
    "CC_M_100002": {
        "welcome_coupon": 2,
        "birthday_reward": 1,
        "tier_upgrade_reward": 1,
        "free_drink_coupon": 1,
        "food_coupon": 1,
        "customization_coupon": 1,
        "refill_benefit": 1,
        "early_access": 1,
    },
    "CC_M_100003": {
        "welcome_coupon": 3,
        "birthday_reward": 2,
        "tier_upgrade_reward": 3,
        "free_drink_coupon": 2,
        "food_coupon": 2,
        "customization_coupon": 2,
        "refill_benefit": 2,
        "early_access": 2,
    },
}

BENEFIT_STATUS_NAMES = {0: "隐藏", 1: "未解锁", 2: "可使用", 3: "已使用/已过期"}
BENEFIT_NAMES = {
    "welcome_coupon": "新人礼券",
    "birthday_reward": "生日奖励",
    "tier_upgrade_reward": "升级奖励",
    "free_drink_coupon": "免费饮品券",
    "food_coupon": "食品优惠券",
    "customization_coupon": "定制优惠券",
    "refill_benefit": "续杯权益",
    "early_access": "新品优先体验",
}

# ---------------------------------------------------------------------------
# Coupons (券码服务)
# ---------------------------------------------------------------------------

COUPONS = [
    {
        "coupon_code": "CC20260301A001",
        "coupon_no": "CN_100001_001",
        "order_id": "ORD_2026030100001",
        "campaign_id": "CAMP_SPRING_2026",
        "status": 4,   # 4=未使用
        "status_name": "未使用",
        "product_name": "中杯饮品券",
        "valid_start": "2026-03-01 00:00:00",
        "valid_end": "2026-04-30 23:59:59",
        "redeem_times": 0,
        "max_redeem_times": 1,
        "face_value": 35.0,
        "member_id": "CC_M_100001",
    },
    {
        "coupon_code": "CC20260301A002",
        "coupon_no": "CN_100001_002",
        "order_id": "ORD_2026030100001",
        "campaign_id": "CAMP_SPRING_2026",
        "status": 10,  # 10=已使用
        "status_name": "已使用",
        "product_name": "中杯饮品券",
        "valid_start": "2026-03-01 00:00:00",
        "valid_end": "2026-04-30 23:59:59",
        "redeem_times": 1,
        "max_redeem_times": 1,
        "face_value": 35.0,
        "member_id": "CC_M_100001",
    },
    {
        "coupon_code": "CC20260215B001",
        "coupon_no": "CN_100002_001",
        "order_id": "ORD_2026021500001",
        "campaign_id": "CAMP_CNY_2026",
        "status": 4,
        "status_name": "未使用",
        "product_name": "买一送一券",
        "valid_start": "2026-02-15 00:00:00",
        "valid_end": "2026-03-31 23:59:59",
        "redeem_times": 0,
        "max_redeem_times": 1,
        "face_value": 0.0,
        "member_id": "CC_M_100002",
    },
    {
        "coupon_code": "CC20260101C001",
        "coupon_no": "CN_100003_001",
        "order_id": "ORD_2026010100001",
        "campaign_id": "CAMP_VIP_2026",
        "status": 4,
        "status_name": "未使用",
        "product_name": "大杯饮品免费券",
        "valid_start": "2026-01-01 00:00:00",
        "valid_end": "2026-06-30 23:59:59",
        "redeem_times": 0,
        "max_redeem_times": 3,
        "face_value": 40.0,
        "member_id": "CC_M_100003",
    },
]

COUPON_STATUS_NAMES = {
    4: "未使用", 10: "已使用", 20: "已过期", 30: "已作废",
}

# ---------------------------------------------------------------------------
# Equity / Benefits (权益服务)
# ---------------------------------------------------------------------------

EQUITIES = [
    {
        "order_id": "EQ_2026030100001",
        "campaign_id": "CAMP_SPRING_2026",
        "coupon_code": "CC20260301A001",
        "coupon_no_with_enc": "ENC_CN_100001_001_xxxxx",
        "status_code": 100,
        "status_name": "发放成功",
        "valid_start": "2026-03-01 00:00:00",
        "valid_end": "2026-04-30 23:59:59",
        "binding_time": "2026-03-01 10:30:00",
        "redeem_times": 0,
        "total_amount": 35.0,
        "member_id": "CC_M_100001",
    },
    {
        "order_id": "EQ_2026030100002",
        "campaign_id": "CAMP_SPRING_2026",
        "coupon_code": "CC20260301A002",
        "coupon_no_with_enc": "ENC_CN_100001_002_xxxxx",
        "status_code": 100,
        "status_name": "发放成功",
        "valid_start": "2026-03-01 00:00:00",
        "valid_end": "2026-04-30 23:59:59",
        "binding_time": "2026-03-01 10:30:05",
        "redeem_times": 1,
        "total_amount": 35.0,
        "member_id": "CC_M_100001",
    },
    {
        "order_id": "EQ_2026021500001",
        "campaign_id": "CAMP_CNY_2026",
        "coupon_code": "CC20260215B001",
        "coupon_no_with_enc": "ENC_CN_100002_001_xxxxx",
        "status_code": 100,
        "status_name": "发放成功",
        "valid_start": "2026-02-15 00:00:00",
        "valid_end": "2026-03-31 23:59:59",
        "binding_time": "2026-02-15 14:00:00",
        "redeem_times": 0,
        "total_amount": 0.0,
        "member_id": "CC_M_100002",
    },
]

EQUITY_STATUS_NAMES = {
    100: "发放成功", 104: "发放失败",
}

# ---------------------------------------------------------------------------
# Customer Assets (客户资产)
# ---------------------------------------------------------------------------

ASSETS = {
    "CC_M_100001": {
        "upp_coupons": [
            {"coupon_no": "CN_100001_001", "name": "中杯饮品券", "status": "未使用",
             "valid_end": "2026-04-30", "face_value": 35.0},
        ],
        "benefit_coupons": [
            {"coupon_no": "BEN_100001_001", "name": "生日免费饮品", "status": "可使用",
             "valid_end": "2026-03-31", "face_value": 0.0},
            {"coupon_no": "BEN_100001_002", "name": "好友邀请奖励", "status": "可使用",
             "valid_end": "2026-12-31", "face_value": 30.0},
        ],
    },
    "CC_M_100002": {
        "upp_coupons": [
            {"coupon_no": "CN_100002_001", "name": "买一送一券", "status": "未使用",
             "valid_end": "2026-03-31", "face_value": 0.0},
        ],
        "benefit_coupons": [],
    },
    "CC_M_100003": {
        "upp_coupons": [
            {"coupon_no": "CN_100003_001", "name": "大杯饮品免费券", "status": "未使用",
             "valid_end": "2026-06-30", "face_value": 40.0},
        ],
        "benefit_coupons": [
            {"coupon_no": "BEN_100003_001", "name": "钻星专属定制券", "status": "可使用",
             "valid_end": "2026-12-31", "face_value": 0.0},
            {"coupon_no": "BEN_100003_002", "name": "续杯半价券", "status": "可使用",
             "valid_end": "2026-06-30", "face_value": 20.0},
            {"coupon_no": "BEN_100003_003", "name": "免费升杯券", "status": "已使用",
             "valid_end": "2026-03-31", "face_value": 0.0},
        ],
    },
}

# ---------------------------------------------------------------------------
# Payment status (收银台)
# ---------------------------------------------------------------------------

PAYMENTS = {
    "PAY_TOKEN_001": {"status": 1, "state_msg": "支付成功", "amount": 37.0,
                      "order_id": "CASH_2026030700001", "method": "微信支付"},
    "PAY_TOKEN_002": {"status": 0, "state_msg": "支付中", "amount": 42.0,
                      "order_id": "CASH_2026030700002", "method": "支付宝"},
    "PAY_TOKEN_003": {"status": 2, "state_msg": "支付失败", "amount": 35.0,
                      "order_id": "CASH_2026030700003", "method": "微信支付"},
}

PAYMENT_STATUS_NAMES = {0: "支付中", 1: "支付成功", 2: "支付失败"}


# ---------------------------------------------------------------------------
# Query functions (simulating backend HTTP calls)
# ---------------------------------------------------------------------------

def get_consumer(username: str) -> dict | None:
    return CONSUMERS.get(username)


def member_query(mobile: str | None = None, open_id: str | None = None,
                 member_id: str | None = None) -> dict | None:
    for m in MEMBERS:
        if mobile and mobile in m["mobile"]:
            return m
        if open_id and m["open_id"] == open_id:
            return m
        if member_id and m["member_id"] == member_id:
            return m
    return None


def member_tier(member_id: str) -> dict | None:
    m = member_query(member_id=member_id)
    if not m:
        return None
    current = m["member_tier"]
    tiers = list(TIER_THRESHOLDS.keys())
    idx = tiers.index(current)
    next_tier = tiers[idx + 1] if idx + 1 < len(tiers) else None
    stars_to_next = (TIER_THRESHOLDS[next_tier] - m["star_balance"]) if next_tier else 0
    return {
        "member_tier": current,
        "tier_name": TIER_NAMES[current],
        "star_balance": m["star_balance"],
        "tier_expire_date": m["tier_expire_date"],
        "next_tier": next_tier,
        "next_tier_name": TIER_NAMES.get(next_tier, ""),
        "stars_to_next": max(0, stars_to_next),
    }


def member_benefits(member_id: str) -> dict | None:
    return MEMBER_BENEFITS.get(member_id)


def member_benefit_list(member_id: str) -> list[dict]:
    assets = ASSETS.get(member_id, {})
    result = []
    for c in assets.get("upp_coupons", []):
        result.append({**c, "type": "优惠券"})
    for c in assets.get("benefit_coupons", []):
        result.append({**c, "type": "权益券"})
    return result


def coupon_query(order_id: str) -> list[dict]:
    return [c for c in COUPONS if c["order_id"] == order_id]


def coupon_detail(coupon_code: str) -> dict | None:
    for c in COUPONS:
        if c["coupon_code"] == coupon_code:
            return c
    return None


def equity_query(order_id: str) -> dict | None:
    for e in EQUITIES:
        if e["order_id"] == order_id:
            return e
    return None


def equity_detail(order_id: str) -> dict | None:
    return equity_query(order_id)


def assets_list(member_id: str) -> dict | None:
    return ASSETS.get(member_id)


def cashier_pay_query(pay_token: str) -> dict | None:
    return PAYMENTS.get(pay_token)
