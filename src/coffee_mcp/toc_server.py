"""Coffee Company ToC MCP Server — consumer-facing self-service tools.

21 tools covering the full consumer journey:
  Discovery → My Account → Menu → Stores → Points Mall → Order Flow

Multi-brand support: Loads brand config from YAML and adapter from plugin.
Default brand: coffee_company (demo mode with mock data).

Security: Tools are classified into risk levels L0-L3.
See docs/TOC_SECURITY.md for the full threat model.
"""

from __future__ import annotations

import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum

from mcp.server.fastmcp import FastMCP

from . import toc_formatters as fmt
from .brand_adapter import BrandAdapter
from .brand_config import BrandConfig, RateLimitConfig, load_brand_config, load_brand_adapter


# =========================================================================
# Security: Tool risk levels + rate limiting
# =========================================================================

class RiskLevel(IntEnum):
    """Tool risk classification. See docs/TOC_SECURITY.md §3.1."""
    L0_PUBLIC_READ = 0
    L1_AUTH_READ = 1
    L2_AUTH_WRITE = 2
    L3_HIGH_RISK = 3


_RISK_LEVEL_MAP = {
    "L0": RiskLevel.L0_PUBLIC_READ,
    "L1": RiskLevel.L1_AUTH_READ,
    "L2": RiskLevel.L2_AUTH_WRITE,
    "L3": RiskLevel.L3_HIGH_RISK,
}

# Tool → risk level mapping (static, same for all brands)
_TOOL_RISK: dict[str, RiskLevel] = {
    "now_time_info": RiskLevel.L0_PUBLIC_READ,
    "browse_menu": RiskLevel.L0_PUBLIC_READ,
    "drink_detail": RiskLevel.L0_PUBLIC_READ,
    "nutrition_info": RiskLevel.L0_PUBLIC_READ,
    "nearby_stores": RiskLevel.L0_PUBLIC_READ,
    "store_detail": RiskLevel.L0_PUBLIC_READ,
    "campaign_calendar": RiskLevel.L1_AUTH_READ,
    "available_coupons": RiskLevel.L1_AUTH_READ,
    "my_account": RiskLevel.L1_AUTH_READ,
    "my_coupons": RiskLevel.L1_AUTH_READ,
    "my_orders": RiskLevel.L1_AUTH_READ,
    "delivery_addresses": RiskLevel.L1_AUTH_READ,
    "stars_mall_products": RiskLevel.L1_AUTH_READ,
    "stars_product_detail": RiskLevel.L1_AUTH_READ,
    "store_coupons": RiskLevel.L1_AUTH_READ,
    "order_status": RiskLevel.L1_AUTH_READ,
    "calculate_price": RiskLevel.L1_AUTH_READ,
    "claim_all_coupons": RiskLevel.L2_AUTH_WRITE,
    "create_address": RiskLevel.L2_AUTH_WRITE,
    "stars_redeem": RiskLevel.L3_HIGH_RISK,
    "create_order": RiskLevel.L3_HIGH_RISK,
}


@dataclass
class _RateLimit:
    max_calls: int
    window_seconds: int
    calls: dict = field(default_factory=lambda: defaultdict(list))
    _last_cleanup: float = field(default_factory=time.monotonic)
    _cleanup_interval: float = 300.0  # full cleanup every 5 minutes

    def check(self, user_id: str) -> bool:
        now = time.monotonic()
        # Periodic full cleanup: remove users with no recent calls
        if now - self._last_cleanup > self._cleanup_interval:
            stale = [uid for uid, ts in self.calls.items()
                     if not ts or now - ts[-1] > self.window_seconds]
            for uid in stale:
                del self.calls[uid]
            self._last_cleanup = now
        # Per-user window eviction
        user_calls = self.calls[user_id]
        self.calls[user_id] = [t for t in user_calls if now - t < self.window_seconds]
        if len(self.calls[user_id]) >= self.max_calls:
            return False
        self.calls[user_id].append(now)
        return True


def _build_rate_limits(config: BrandConfig) -> dict[RiskLevel, _RateLimit]:
    """Build rate limiters from brand config."""
    result = {}
    for level_name, rl_config in config.rate_limits.items():
        risk_level = _RISK_LEVEL_MAP.get(level_name)
        if risk_level is not None:
            result[risk_level] = _RateLimit(
                max_calls=rl_config.max_calls,
                window_seconds=rl_config.window_seconds,
            )
    return result


# =========================================================================
# Server factory
# =========================================================================

def create_toc_server(config: BrandConfig, adapter: BrandAdapter) -> FastMCP:
    """Create a configured ToC MCP server for a specific brand."""

    rate_limits = _build_rate_limits(config)
    val = config.validation
    features = config.features
    phone_re = re.compile(val.phone_pattern)
    valid_sizes = set(val.valid_sizes)
    valid_milks = set(val.valid_milks)
    valid_extras = set(val.valid_extras)
    valid_pickup = set(val.valid_pickup)
    default_user = config.default_user_id

    _FEATURE_NOT_AVAILABLE = "该品牌暂未开通此功能。"

    def _check_rate_limit(tool_name: str, user_id: str = default_user) -> str | None:
        level = _TOOL_RISK.get(tool_name, RiskLevel.L1_AUTH_READ)
        limiter = rate_limits.get(level)
        if limiter and not limiter.check(f"{user_id}:{tool_name}"):
            return "操作过于频繁，请稍后再试。"
        return None

    def _validate_cart_items(items: list[dict]) -> str | None:
        if not items:
            return "商品列表不能为空。"
        if len(items) > val.max_items_per_order:
            return f"单次最多 {val.max_items_per_order} 件商品。"
        for i, item in enumerate(items):
            if "product_code" not in item:
                return f"第 {i+1} 件商品缺少 product_code。"
            qty = item.get("quantity", 1)
            if not isinstance(qty, int) or qty < 1 or qty > val.max_quantity:
                return f"商品数量须在 1-{val.max_quantity} 之间。"
            size = item.get("size")
            if size and size not in valid_sizes:
                return f"杯型 '{size}' 无效，可选: {', '.join(sorted(valid_sizes))}。"
            milk = item.get("milk")
            if milk and milk not in valid_milks:
                return f"奶类 '{milk}' 无效，可选: {', '.join(sorted(valid_milks))}。"
            for extra in item.get("extras", []):
                if extra not in valid_extras:
                    return f"加料 '{extra}' 无效，可选: {', '.join(sorted(valid_extras))}。"
        return None

    # --- Create MCP server instance ---
    mcp = FastMCP(config.server_name, instructions=config.instructions)

    # =====================================================================
    # Tool registrations
    # =====================================================================

    @mcp.tool()
    def now_time_info() -> str:
        """返回当前日期时间和星期，供判断活动有效期、门店营业时间等。[风险等级: L0]

        When:
        - 在查询活动日历、判断优惠券有效期之前调用
        - 判断门店是否在营业时间内
        """
        return fmt.format_now_time_info()

    @mcp.tool()
    def campaign_calendar(month: str | None = None) -> str:
        """查询活动日历，发现当前和即将开始的优惠活动。

        When:
        - 用户问"有什么活动"、"最近有什么优惠"
        Next:
        - 引导用户查看可领取的优惠券

        Args:
            month: 可选，查询指定月份 (格式: yyyy-MM)，默认当月
        """
        campaigns = adapter.campaign_calendar(month)
        return fmt.format_campaigns(campaigns)

    @mcp.tool()
    def available_coupons() -> str:
        """查询当前可领取的优惠券列表。

        When:
        - 用户问"有什么券可以领"、"券中心"
        Next:
        - 用户想全部领取时，引导使用 claim_all_coupons
        """
        coupons = adapter.available_coupons()
        return fmt.format_available_coupons(coupons)

    @mcp.tool()
    def claim_all_coupons() -> str:
        """一键领取所有可领取的优惠券。[风险等级: L2]

        安全限制: 每用户每小时最多 5 次
        When:
        - 用户说"帮我领券"、"一键领取"、"全部领了"
        """
        if err := _check_rate_limit("claim_all_coupons"):
            return err
        result = adapter.claim_all_coupons(default_user)
        return fmt.format_claim_result(result)

    @mcp.tool()
    def my_account() -> str:
        """查询我的账户信息：等级、星星余额、可用权益、优惠券数量。

        When:
        - 用户问"我的等级"、"我有多少星星"、"我的账户"
        """
        info = adapter.my_account(default_user)
        if not info:
            return "未能获取账户信息，请确认登录状态。"
        return fmt.format_my_account(info)

    @mcp.tool()
    def my_coupons(status: str | None = None) -> str:
        """查询我已有的优惠券列表。

        When:
        - 用户问"我有什么券"、"我的优惠券"

        Args:
            status: 可选筛选 "valid"(可用) / "used"(已使用)
        """
        items = adapter.my_coupons(default_user, status=status)
        return fmt.format_my_coupons(items)

    @mcp.tool()
    def my_orders(limit: int = 5) -> str:
        """查询我的最近订单。

        When:
        - 用户问"我的订单"、"最近点了什么"

        Args:
            limit: 返回最近几笔订单，默认5
        """
        orders = adapter.my_orders(default_user, limit=limit)
        return fmt.format_my_orders(orders)

    @mcp.tool()
    def browse_menu(store_id: str, compact: bool = False) -> str:
        """浏览门店菜单，查看饮品和食品列表。

        Preconditions:
        - 必须先调用 nearby_stores 获取门店信息
        When:
        - 用户说"看看菜单"、"有什么喝的"
        Next:
        - 选中商品后 → drink_detail / calculate_price

        Args:
            store_id: 门店ID，从 nearby_stores 获取
            compact: 紧凑模式，减少 token 消耗
        """
        menu = adapter.browse_menu(store_id)
        if compact:
            return fmt.format_menu_compact(menu, config.size_options)
        return fmt.format_menu(menu, config.size_options)

    @mcp.tool()
    def drink_detail(product_code: str) -> str:
        """查看饮品详情和自定义选项（杯型/奶类/温度/甜度/加料）。当用户想了解某个饮品有哪些定制选项时使用。

        Args:
            product_code: 商品编号（如 D003），从 browse_menu 获取
        """
        item = adapter.drink_detail(product_code)
        if not item:
            return f"未找到商品 {product_code}。请检查商品编号。"
        return fmt.format_drink_detail(item)

    @mcp.tool()
    def nutrition_info(product_code: str, compact: bool = False) -> str:
        """查询饮品营养成分（热量、蛋白质、脂肪等）。当用户问"多少卡"、"热量高吗"时使用。

        Args:
            product_code: 商品编号（如 D001），从 browse_menu 获取
            compact: 紧凑模式，单行输出
        """
        info = adapter.nutrition_info(product_code)
        if not info:
            return f"未找到商品 {product_code} 的营养信息。"
        if compact:
            return fmt.format_nutrition_compact(info)
        return fmt.format_nutrition(info)

    @mcp.tool()
    def nearby_stores(city: str | None = None, keyword: str | None = None) -> str:
        """搜索附近门店，按城市或关键词筛选。

        When:
        - 用户说"附近有什么店"、"找一家店"

        Args:
            city: 可选，城市名
            keyword: 可选，关键词搜索
        """
        stores = adapter.nearby_stores(city=city, keyword=keyword)
        return fmt.format_nearby_stores(stores)

    @mcp.tool()
    def store_detail(store_id: str) -> str:
        """查看门店详情：地址、营业时间、电话（脱敏显示）、服务。当用户问"这家店在哪"、"几点关门"时使用。

        Args:
            store_id: 门店ID，从 nearby_stores 获取
        """
        store = adapter.store_detail(store_id)
        if not store:
            return f"未找到门店 {store_id}。"
        return fmt.format_store_detail(store)

    @mcp.tool()
    def stars_mall_products(category: str | None = None) -> str:
        """浏览积分商城，查看可兑换商品。

        When:
        - 用户问"积分能换什么"、"星星商城"

        Args:
            category: 可选分类筛选
        """
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        products = adapter.stars_mall_products(category)
        user = adapter.get_current_user(default_user)
        user_stars = user["star_balance"] if user else 0
        return fmt.format_stars_mall(products, user_stars)

    @mcp.tool()
    def stars_product_detail(product_code: str) -> str:
        """查看积分商品详情。当用户想了解某个积分商品的兑换条件时使用。

        Args:
            product_code: 积分商品编号，从 stars_mall_products 获取
        """
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        product = adapter.stars_product_detail(product_code)
        if not product:
            return f"未找到积分商品 {product_code}。"
        user = adapter.get_current_user(default_user)
        user_stars = user["star_balance"] if user else 0
        return fmt.format_stars_product_detail(product, user_stars)

    @mcp.tool()
    def stars_redeem(product_code: str, idempotency_key: str) -> str:
        """用星星兑换积分商城商品。[风险等级: L3]

        安全限制: 每用户每天最多 10 次
        Preconditions:
        - 先查看 stars_product_detail 确认商品
        - 用户确认后才可调用

        Args:
            product_code: 积分商品编号
            idempotency_key: 幂等键，防重复兑换
        """
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        if err := _check_rate_limit("stars_redeem"):
            return err
        result = adapter.stars_redeem(product_code, default_user,
                                      idempotency_key=idempotency_key)
        return fmt.format_stars_redeem_result(result)

    @mcp.tool()
    def delivery_addresses() -> str:
        """查询我的配送地址列表。

        When:
        - 用户选择外送时，先查看/选择配送地址
        """
        addrs = adapter.delivery_addresses(default_user)
        return fmt.format_delivery_addresses(addrs)

    @mcp.tool()
    def create_address(city: str, address: str, address_detail: str,
                       contact_name: str, phone: str) -> str:
        """创建新的配送地址。[风险等级: L2]

        Args:
            city: 城市
            address: 详细地址
            address_detail: 门牌号
            contact_name: 联系人
            phone: 手机号（11位）
        """
        if err := _check_rate_limit("create_address"):
            return err
        if not phone_re.match(phone):
            return "手机号格式无效，请输入11位手机号。"
        existing = adapter.delivery_addresses(default_user)
        if len(existing) >= val.max_addresses:
            return f"最多保存 {val.max_addresses} 个地址，请先删除不用的地址。"
        if not all([city.strip(), address.strip(), address_detail.strip(),
                    contact_name.strip()]):
            return "地址信息不完整，请填写所有必填项。"
        addr = adapter.create_address(default_user, city, address,
                                      address_detail, contact_name, phone)
        return fmt.format_new_address(addr)

    @mcp.tool()
    def store_coupons(store_id: str) -> str:
        """查询在指定门店可使用的优惠券。

        Preconditions:
        - 必须先调用 nearby_stores 获取门店信息

        Args:
            store_id: 门店ID
        """
        store = adapter.store_detail(store_id)
        store_name = store["name"] if store else store_id
        coupons = adapter.store_coupons(store_id, default_user)
        return fmt.format_store_coupons(coupons, store_name)

    @mcp.tool()
    def calculate_price(store_id: str, items: list[dict],
                        coupon_code: str | None = None) -> str:
        """计算订单价格（含优惠），返回确认令牌用于下单。当用户选好商品准备下单时使用。

        Preconditions:
        - 必须先调用 nearby_stores 获取门店 store_id
        - 商品 product_code 从 browse_menu 获取（格式如 D001, D002, F001，不要用英文名）
        Next:
        - 用户确认后将 confirmation_token 传入 create_order

        Args:
            store_id: 门店ID，从 nearby_stores 获取
            items: 商品列表，每项包含:
                - product_code: 商品编号（如 D001），必须从 browse_menu 返回的编号中获取
                - quantity: 数量（默认1）
                - size: 杯型 tall(中杯) / grande(大杯) / venti(超大杯)，注意星巴克中杯=tall
                - milk: 奶型 whole / skim / oat / almond / soy / coconut
                - temperature: 温度 hot / iced / blended
                - extras: 加料列表，可选值: extra_shot / vanilla_syrup / caramel_syrup / hazelnut_syrup / whipped_cream / chocolate_sauce
            coupon_code: 优惠券编号（可选），从 my_coupons 或 store_coupons 获取
        """
        if err := _validate_cart_items(items):
            return err
        result = adapter.calculate_price(store_id, items, coupon_code)
        return fmt.format_price_calculation(result)

    @mcp.tool()
    def create_order(store_id: str, items: list[dict], pickup_type: str,
                     idempotency_key: str,
                     confirmation_token: str,
                     coupon_code: str | None = None,
                     address_id: str | None = None) -> str:
        """创建订单。[风险等级: L3] 当用户确认价格后说"下单"、"确认"时使用。

        Preconditions:
        - 必须先调用 calculate_price 获取 confirmation_token，不可跳过
        - 外送订单必须提供 address_id（从 delivery_addresses 获取）
        - items 格式与 calculate_price 相同

        Args:
            store_id: 门店ID，从 nearby_stores 获取
            items: 商品列表，与 calculate_price 中传入的一致
            pickup_type: "自提" / "外送" / "堂食"
            idempotency_key: 幂等键（UUID 格式），防重复下单
            confirmation_token: 确认令牌，必须从 calculate_price 返回值中获取
            coupon_code: 优惠券编号（可选）
            address_id: 配送地址ID，外送必填，从 delivery_addresses 获取
        """
        if err := _check_rate_limit("create_order"):
            return err
        if err := _validate_cart_items(items):
            return err
        if pickup_type not in valid_pickup:
            return f"取餐方式 '{pickup_type}' 无效，可选: {', '.join(sorted(valid_pickup))}。"
        if pickup_type == "外送" and not address_id:
            return "外送订单必须提供配送地址ID。请先调用 delivery_addresses 获取。"
        # Check store exists and is open
        store = adapter.store_detail(store_id)
        if not store:
            return f"门店 {store_id} 不存在，请先调用 nearby_stores 获取门店。"
        if store.get("status") != "营业中":
            return f"门店 {store['name']} 当前{store.get('status', '未知状态')}，无法下单。"
        # Validate confirmation token
        from .utils import validate_confirmation_token
        token_err = validate_confirmation_token(confirmation_token)
        if token_err:
            return token_err
        result = adapter.create_order(store_id, items, pickup_type,
                                      user_id=default_user,
                                      idempotency_key=idempotency_key,
                                      coupon_code=coupon_code,
                                      address_id=address_id)
        return fmt.format_order_created(result)

    @mcp.tool()
    def order_status(order_id: str) -> str:
        """查询订单状态详情。当用户问"我的订单怎么样了"、"做好了吗"时使用。

        Args:
            order_id: 订单号，从 create_order 或 my_orders 获取
        """
        order = adapter.order_status(order_id, default_user)
        if not order:
            return f"未找到订单 {order_id}。请检查订单号。"
        return fmt.format_order_status(order)

    return mcp


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _resolve_brand() -> str:
    """Resolve brand from env or CLI args."""
    return os.environ.get("BRAND", "coffee_company")


def main():
    """stdio transport (default for Claude Desktop / Cursor)."""
    brand = _resolve_brand()
    config = load_brand_config(brand)
    adapter = load_brand_adapter(config)
    server = create_toc_server(config, adapter)
    server.run()


def main_http():
    """Streamable HTTP transport (for OpenClaw / remote clients)."""
    brand = _resolve_brand()
    config = load_brand_config(brand)
    adapter = load_brand_adapter(config)
    server = create_toc_server(config, adapter)
    server.run(transport="streamable-http")


if __name__ == "__main__":
    main()
