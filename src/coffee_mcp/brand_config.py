"""Brand configuration loader for ToC MCP platform.

Loads brand-specific config from YAML files in the brands/ directory.
Each brand has a brand.yaml with menu options, validation rules,
rate limits, and adapter configuration.

Usage:
    config = load_brand_config("coffee_company")
    adapter = load_brand_adapter(config)
    server = create_toc_server(config, adapter)
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .brand_adapter import BrandAdapter


# Default paths
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_BRANDS_DIR = _PROJECT_ROOT / "brands"


@dataclass
class ValidationConfig:
    """Brand-specific validation rules."""
    phone_pattern: str = r"^1\d{10}$"
    valid_sizes: list[str] = field(default_factory=lambda: ["tall", "grande", "venti"])
    valid_milks: list[str] = field(default_factory=lambda: [
        "whole", "skim", "oat", "almond", "soy", "coconut"])
    valid_temps: list[str] = field(default_factory=lambda: ["hot", "iced", "blended"])
    valid_extras: list[str] = field(default_factory=lambda: [
        "extra_shot", "vanilla_syrup", "caramel_syrup",
        "hazelnut_syrup", "whipped_cream", "cocoa_powder"])
    valid_pickup: list[str] = field(default_factory=lambda: ["自提", "外送", "堂食"])
    max_quantity: int = 99
    max_items_per_order: int = 20
    max_addresses: int = 10


@dataclass
class RateLimitConfig:
    """Per-level rate limit values."""
    max_calls: int
    window_seconds: int


@dataclass
class BrandConfig:
    """Complete brand configuration loaded from YAML."""
    brand_id: str
    brand_name: str
    server_name: str
    instructions: str
    default_user_id: str

    validation: ValidationConfig
    rate_limits: dict[str, RateLimitConfig]

    # Customization option lookup tables
    size_options: dict[str, dict]
    milk_options: dict[str, dict]
    temp_options: dict[str, dict]
    sweetness_options: dict[str, dict]
    extra_options: dict[str, dict]

    # Feature flags
    features: dict[str, bool] = field(default_factory=lambda: {
        "campaigns": True, "coupons": True, "stars_mall": True,
        "delivery": True, "nutrition": True,
    })

    # Adapter configuration (optional)
    adapter_module: str | None = None
    adapter_class: str | None = None

    # Brand directory for loading demo data
    brand_dir: Path | None = None


# Default rate limits
_DEFAULT_RATE_LIMITS = {
    "L0": RateLimitConfig(max_calls=60, window_seconds=60),
    "L1": RateLimitConfig(max_calls=30, window_seconds=60),
    "L2": RateLimitConfig(max_calls=5, window_seconds=3600),
    "L3": RateLimitConfig(max_calls=10, window_seconds=86400),
}


def _default_brand_config() -> BrandConfig:
    """Return the built-in Coffee Company config (no YAML needed)."""
    return BrandConfig(
        brand_id="coffee_company",
        brand_name="Coffee Company",
        server_name="Coffee Company ToC",
        instructions=(
            "Coffee Company 消费者自助 MCP Server。\n"
            "提供活动发现、优惠券领取、菜单浏览、门店查找、积分商城、下单点餐等能力。\n"
            "所有工具基于登录用户身份自动识别，无需传入会员ID。\n"
            "Demo 模式默认用户：张三（金星级，142颗星星）。\n\n"
            "安全说明：工具按风险分为 L0(公开只读) ~ L3(高危写入) 四级，\n"
            "高危操作有频率限制和参数校验，详见 docs/TOC_SECURITY.md。\n\n"
            "重要：下单前必须先调用 calculate_price 获取 confirmation_token，\n"
            "然后将 confirmation_token 传入 create_order。\n"
            "L3 操作（create_order, stars_redeem）需要 idempotency_key 防重复。"
        ),
        default_user_id="CC_M_100001",
        validation=ValidationConfig(),
        rate_limits=dict(_DEFAULT_RATE_LIMITS),
        size_options={
            "tall": {"name": "中杯", "extra_price": 0},
            "grande": {"name": "大杯", "extra_price": 4},
            "venti": {"name": "超大杯", "extra_price": 7},
        },
        milk_options={
            "whole": {"name": "全脂牛奶", "extra_price": 0},
            "skim": {"name": "脱脂牛奶", "extra_price": 0},
            "oat": {"name": "燕麦奶", "extra_price": 5},
            "almond": {"name": "杏仁奶", "extra_price": 5},
            "soy": {"name": "豆奶", "extra_price": 4},
            "coconut": {"name": "椰奶", "extra_price": 5},
        },
        temp_options={
            "hot": {"name": "热"},
            "iced": {"name": "冰"},
            "blended": {"name": "冰沙"},
        },
        sweetness_options={
            "normal": {"name": "标准糖"},
            "less": {"name": "少糖"},
            "half": {"name": "半糖"},
            "none": {"name": "无糖"},
        },
        extra_options={
            "extra_shot": {"name": "浓缩+1份", "price": 6},
            "vanilla_syrup": {"name": "香草糖浆", "price": 4},
            "caramel_syrup": {"name": "焦糖糖浆", "price": 4},
            "hazelnut_syrup": {"name": "榛果糖浆", "price": 4},
            "whipped_cream": {"name": "奶油顶", "price": 3},
            "cocoa_powder": {"name": "可可粉", "price": 0},
        },
    )


def load_brand_config(brand_id: str) -> BrandConfig:
    """Load brand config from brands/<brand_id>/brand.yaml.

    Falls back to built-in Coffee Company defaults if no YAML exists.
    """
    brand_dir = _BRANDS_DIR / brand_id
    yaml_path = brand_dir / "brand.yaml"

    if not yaml_path.exists():
        if brand_id == "coffee_company":
            return _default_brand_config()
        raise FileNotFoundError(
            f"Brand config not found: {yaml_path}\n"
            f"Create brands/{brand_id}/brand.yaml to configure a new brand."
        )

    with open(yaml_path) as f:
        raw = yaml.safe_load(f)

    if not raw or not isinstance(raw, dict):
        raise ValueError(f"Invalid brand config: {yaml_path} is empty or not a YAML mapping.")

    # Validate required fields
    required = ["brand_name", "server_name", "instructions"]
    missing = [f for f in required if f not in raw]
    if missing:
        raise ValueError(
            f"Brand config {yaml_path} missing required fields: {', '.join(missing)}\n"
            f"See brands/coffee_company/brand.yaml for a complete example."
        )

    # Parse validation config
    val_raw = raw.get("validation", {})
    validation = ValidationConfig(
        phone_pattern=val_raw.get("phone_pattern", r"^1\d{10}$"),
        valid_sizes=val_raw.get("valid_sizes", ["tall", "grande", "venti"]),
        valid_milks=val_raw.get("valid_milks", ["whole", "skim", "oat", "almond", "soy", "coconut"]),
        valid_temps=val_raw.get("valid_temps", ["hot", "iced", "blended"]),
        valid_extras=val_raw.get("valid_extras", [
            "extra_shot", "vanilla_syrup", "caramel_syrup",
            "hazelnut_syrup", "whipped_cream", "cocoa_powder"]),
        valid_pickup=val_raw.get("valid_pickup", ["自提", "外送", "堂食"]),
        max_quantity=val_raw.get("max_quantity", 99),
        max_items_per_order=val_raw.get("max_items_per_order", 20),
        max_addresses=val_raw.get("max_addresses", 10),
    )

    # Parse rate limits
    rl_raw = raw.get("rate_limits", {})
    rate_limits = dict(_DEFAULT_RATE_LIMITS)
    for level_name, vals in rl_raw.items():
        rate_limits[level_name] = RateLimitConfig(
            max_calls=vals["max_calls"],
            window_seconds=vals["window_seconds"],
        )

    # Parse adapter config
    adapter_raw = raw.get("adapter", {})

    config = BrandConfig(
        brand_id=raw.get("brand_id", brand_id),
        brand_name=raw.get("brand_name", brand_id),
        server_name=raw.get("server_name", f"{raw.get('brand_name', brand_id)} ToC"),
        instructions=raw.get("instructions", ""),
        default_user_id=raw.get("default_user_id", "CC_M_100001"),
        validation=validation,
        rate_limits=rate_limits,
        size_options=raw.get("size_options", {}),
        milk_options=raw.get("milk_options", {}),
        temp_options=raw.get("temp_options", {}),
        sweetness_options=raw.get("sweetness_options", {}),
        extra_options=raw.get("extra_options", {}),
        features=raw.get("features", {
            "campaigns": True, "coupons": True, "stars_mall": True,
            "delivery": True, "nutrition": True,
        }),
        adapter_module=adapter_raw.get("module"),
        adapter_class=adapter_raw.get("class"),
        brand_dir=brand_dir,
    )
    return config


def load_brand_adapter(config: BrandConfig) -> BrandAdapter:
    """Instantiate the brand adapter: custom module or DemoAdapter."""
    if config.adapter_module and config.adapter_class:
        module = importlib.import_module(config.adapter_module)
        cls = getattr(module, config.adapter_class)
        return cls(config)

    # Default: use DemoAdapter with mock data
    from .demo_adapter import DemoAdapter
    return DemoAdapter(config)
