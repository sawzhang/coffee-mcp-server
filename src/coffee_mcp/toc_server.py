"""Coffee Company ToC MCP Server — consumer-facing self-service tools.

21 tools covering the full consumer journey:
  Discovery → My Account → Menu → Stores → Points Mall → Order Flow

Multi-brand support: Loads brand config from YAML and adapter from plugin.
Default brand: coffee_company (demo mode with mock data).

Security: Tools are classified into risk levels L0-L3.
See docs/TOC_SECURITY.md for the full threat model.

OAuth (Stage 1): when `session_store` is provided, tools enforce scope-gated
access via _require_auth. When no HTTP request is in flight (stdio mode) or
no session store is wired (raw streamable-http), the guard falls back to
`default_user` for backward compatibility.
"""

from __future__ import annotations

import json
import os
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

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

def create_toc_server(config: BrandConfig, adapter: BrandAdapter,
                      *,
                      session_store: Any | None = None,
                      mock_as: Any | None = None) -> FastMCP:
    """Create a configured ToC MCP server for a specific brand.

    `session_store` and `mock_as` are wired by auth/http_app.py to enable
    Stage 1 OAuth. Leaving them None preserves the existing stdio / raw-http
    behavior (every tool falls back to `default_user`).
    """

    # Local imports keep auth deps optional for stdio-only users.
    from .auth import audit
    from .auth.scopes import (
        DEFAULT_SCOPES,
        STEP_UP_REQUIRED,
        TOOL_SCOPES,
    )
    from .auth.session_store import AuthLevel, Session

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

    # ---------------- auth helpers (Stage 1) ----------------

    def _continue_url_json(session: Session | None, scope: str | None,
                           reason: str = "需要登录") -> str:
        """Tool result for "not authenticated" — JSON dict per spec §3.2.

        The `session_id` field tells the client which session to echo back via
        the `X-Session-Id` header on retry — required for the anonymous flow
        not to leak a new session per call.
        """
        sid = session.session_id if session else ""
        params = []
        if sid:
            params.append(f"session_id={sid}")
        if scope:
            params.append(f"scope={scope}")
        qs = ("?" + "&".join(params)) if params else ""
        url = f"/oauth/login_start{qs}" if config.oauth is not None else ""
        return json.dumps({
            "authenticated": False,
            "session_id": sid,
            "continue_url": url,
            "message": f"{reason},请在浏览器中完成后,再次问我即可。",
            "expires_in": 600,
            "required_scope": scope,
            "retry_hint": "下次调用请在请求头 X-Session-Id 中带上 session_id,避免重复创建会话。",
        }, ensure_ascii=False)

    def _scope_elevation_json(session: Session, missing_scope: str) -> str:
        sid = session.session_id
        url = f"/oauth/login_start?session_id={sid}&scope={missing_scope}"
        return json.dumps({
            "authenticated": True,
            "continue_url": url,
            "message": f"当前权限不足,需要授予 '{missing_scope}',请在浏览器中确认。",
            "missing_scope": missing_scope,
            "expires_in": 600,
        }, ensure_ascii=False)

    def _step_up_json(session: Session, tool_name: str) -> str:
        sid = session.session_id
        url = f"/h5/step_up?session_id={sid}&tool={tool_name}"
        return json.dumps({
            "authenticated": True,
            "step_up_required": True,
            "continue_url": url,
            "message": f"操作 '{tool_name}' 需要二次确认,请在浏览器中确认后再次发起。",
            "expires_in": 300,
        }, ensure_ascii=False)

    def _resolve_session_from_request(ctx: Context | None) -> Session | None:
        """Return the Session for the bearer token / X-Session-Id, or None.

        Never creates a new session here — that's `_require_auth`'s job, and
        only when it needs to emit a continue_url. This keeps the anonymous
        path from leaking one session per tool call.
        """
        if session_store is None or ctx is None:
            return None
        try:
            req = ctx.request_context.request  # Starlette Request for HTTP transport
        except Exception:
            return None
        if req is None:
            return None

        auth_header = ""
        sid_header = ""
        try:
            auth_header = req.headers.get("authorization", "") or ""
            sid_header = req.headers.get("x-session-id", "") or ""
        except Exception:
            pass

        token = auth_header[7:].strip() if auth_header.lower().startswith("bearer ") else ""

        if token:
            info = _validate_token(token)
            if info is None:
                return None
            sess = session_store.find_by_token(token)
            if sess is None:
                sess = session_store.create()
                session_store.upgrade(
                    sess.session_id,
                    member_id=info["member_id"],
                    scope=info["scope"],
                    member_token=token,
                    token_expires_in=max(int(info["exp"] - time.monotonic()), 1),
                )
                sess = session_store.get(sess.session_id)
            elif sess.token_expires_at <= time.monotonic():
                return None
            return sess

        if sid_header:
            existing = session_store.get(sid_header)
            if existing:
                return existing
        return None

    def _validate_token(token: str) -> dict | None:
        """Resolve a bearer token to {member_id, scope, exp}.

        Mock AS path uses introspection; real-AS path validates JWT via the
        brand's jwks_uri (see auth.jwt_validator).
        """
        if mock_as is not None:
            return mock_as.introspect(token)
        if config.oauth and config.oauth.jwks_uri:
            from .auth.jwt_validator import validate_jwt
            return validate_jwt(token, config.oauth)
        return None

    def _request_metadata(ctx: Context | None) -> dict:
        """Pull IP / UA / mcp-client headers for audit logging."""
        if ctx is None:
            return {}
        try:
            req = ctx.request_context.request
        except Exception:
            return {}
        if req is None:
            return {}
        try:
            return {
                "ip": (req.headers.get("x-forwarded-for") or
                       (req.client.host if req.client else None)),
                "user_agent": req.headers.get("user-agent"),
                "mcp_client": (req.headers.get("x-mcp-client") or
                               req.headers.get("user-agent")),
                "agent_id": req.headers.get("x-agent-id"),
            }
        except Exception:
            return {}

    def _require_auth(ctx: Context | None,
                      tool_name: str) -> tuple[str | None, str | None]:
        """Resolve (user_id, error_json). Exactly one of them is None.

        Falls back to `default_user` when no HTTP request is in flight (stdio).
        Every decision is mirrored to the audit log (PIPL §55).
        """
        required_scope = TOOL_SCOPES.get(tool_name)
        meta = _request_metadata(ctx)
        # L0 public tool — short-circuit, audit as public access.
        if required_scope is None:
            audit.record(tool=tool_name, result="granted_l0_public",
                         scope_used=None, **meta)
            return default_user, None

        session = _resolve_session_from_request(ctx)
        if session is None:
            if session_store is None:
                audit.record(tool=tool_name, result="granted_stdio_fallback",
                             member_id=default_user, scope_used=required_scope, **meta)
                return default_user, None
            session = session_store.create(short_ttl=True)
            audit.record(tool=tool_name, result="denied_anonymous",
                         session_id=session.session_id,
                         scope_used=required_scope, **meta)
            return None, _continue_url_json(session, required_scope, reason="需要登录")

        sid = session.session_id

        if session.auth_level == AuthLevel.ANONYMOUS or session.member_id is None:
            audit.record(tool=tool_name, result="denied_anonymous",
                         session_id=sid, scope_used=required_scope, **meta)
            return None, _continue_url_json(session, required_scope, reason="需要登录")

        if session.token_expires_at and session.token_expires_at <= time.monotonic():
            audit.record(tool=tool_name, result="denied_token_expired",
                         session_id=sid, member_id=session.member_id,
                         scope_used=required_scope, **meta)
            return None, _continue_url_json(session, required_scope, reason="登录已过期")

        if required_scope not in session.scope:
            audit.record(tool=tool_name, result="denied_scope_insufficient",
                         session_id=sid, member_id=session.member_id,
                         scope_used=required_scope, **meta,
                         extra={"granted": sorted(session.scope)})
            return None, _scope_elevation_json(session, required_scope)

        if tool_name in STEP_UP_REQUIRED:
            if (session.auth_level != AuthLevel.STEP_UP_VERIFIED
                    or session.step_up_expires_at <= time.monotonic()):
                audit.record(tool=tool_name, result="denied_step_up_needed",
                             session_id=sid, member_id=session.member_id,
                             scope_used=required_scope, **meta)
                return None, _step_up_json(session, tool_name)

        audit.record(tool=tool_name, result="granted",
                     session_id=sid, member_id=session.member_id,
                     scope_used=required_scope, **meta)
        return session.member_id, None

    def _check_rate_limit(tool_name: str, user_id: str) -> str | None:
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
    def now_time_info(ctx: Context) -> str:
        """返回当前日期时间和星期，供判断活动有效期、门店营业时间等。[风险等级: L0]

        When:
        - 在查询活动日历、判断优惠券有效期之前调用
        - 判断门店是否在营业时间内
        """
        user_id, err = _require_auth(ctx, "now_time_info")
        if err: return err
        return fmt.format_now_time_info()

    @mcp.tool()
    def campaign_calendar(ctx: Context, month: str | None = None) -> str:
        """查询活动日历，发现当前和即将开始的优惠活动。

        When:
        - 用户问"有什么活动"、"最近有什么优惠"
        Next:
        - 引导用户查看可领取的优惠券

        Args:
            month: 可选，查询指定月份 (格式: yyyy-MM)，默认当月
        """
        user_id, err = _require_auth(ctx, "campaign_calendar")
        if err: return err
        campaigns = adapter.campaign_calendar(month)
        return fmt.format_campaigns(campaigns)

    @mcp.tool()
    def available_coupons(ctx: Context) -> str:
        """查询当前可领取的优惠券列表。

        When:
        - 用户问"有什么券可以领"、"券中心"
        Next:
        - 用户想全部领取时，引导使用 claim_all_coupons
        """
        user_id, err = _require_auth(ctx, "available_coupons")
        if err: return err
        coupons = adapter.available_coupons()
        return fmt.format_available_coupons(coupons)

    @mcp.tool()
    def claim_all_coupons(ctx: Context) -> str:
        """一键领取所有可领取的优惠券。[风险等级: L2]

        安全限制: 每用户每小时最多 5 次
        When:
        - 用户说"帮我领券"、"一键领取"、"全部领了"
        """
        user_id, err = _require_auth(ctx, "claim_all_coupons")
        if err: return err
        if rerr := _check_rate_limit("claim_all_coupons", user_id):
            return rerr
        result = adapter.claim_all_coupons(user_id)
        return fmt.format_claim_result(result)

    @mcp.tool()
    def my_account(ctx: Context) -> str:
        """查询我的账户信息：等级、星星余额、可用权益、优惠券数量。

        When:
        - 用户问"我的等级"、"我有多少星星"、"我的账户"
        """
        user_id, err = _require_auth(ctx, "my_account")
        if err: return err
        info = adapter.my_account(user_id)
        if not info:
            return "未能获取账户信息，请确认登录状态。"
        return fmt.format_my_account(info)

    @mcp.tool()
    def my_coupons(ctx: Context, status: str | None = None) -> str:
        """查询我已有的优惠券列表。

        When:
        - 用户问"我有什么券"、"我的优惠券"

        Args:
            status: 可选筛选 "valid"(可用) / "used"(已使用)
        """
        user_id, err = _require_auth(ctx, "my_coupons")
        if err: return err
        items = adapter.my_coupons(user_id, status=status)
        return fmt.format_my_coupons(items)

    @mcp.tool()
    def my_orders(ctx: Context, limit: int = 5) -> str:
        """查询我的最近订单。

        When:
        - 用户问"我的订单"、"最近点了什么"

        Args:
            limit: 返回最近几笔订单，默认5
        """
        user_id, err = _require_auth(ctx, "my_orders")
        if err: return err
        orders = adapter.my_orders(user_id, limit=limit)
        return fmt.format_my_orders(orders)

    @mcp.tool()
    def browse_menu(ctx: Context, store_id: str, compact: bool = False) -> str:
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
        user_id, err = _require_auth(ctx, "browse_menu")
        if err: return err
        menu = adapter.browse_menu(store_id)
        if compact:
            return fmt.format_menu_compact(menu, config.size_options)
        return fmt.format_menu(menu, config.size_options)

    @mcp.tool()
    def drink_detail(ctx: Context, product_code: str) -> str:
        """查看饮品详情和自定义选项（杯型/奶类/温度/甜度/加料）。当用户想了解某个饮品有哪些定制选项时使用。

        Args:
            product_code: 商品编号（如 D003），从 browse_menu 获取
        """
        user_id, err = _require_auth(ctx, "drink_detail")
        if err: return err
        item = adapter.drink_detail(product_code)
        if not item:
            return f"未找到商品 {product_code}。请检查商品编号。"
        return fmt.format_drink_detail(item)

    @mcp.tool()
    def nutrition_info(ctx: Context, product_code: str, compact: bool = False) -> str:
        """查询饮品营养成分（热量、蛋白质、脂肪等）。当用户问"多少卡"、"热量高吗"时使用。

        Args:
            product_code: 商品编号（如 D001），从 browse_menu 获取
            compact: 紧凑模式，单行输出
        """
        user_id, err = _require_auth(ctx, "nutrition_info")
        if err: return err
        info = adapter.nutrition_info(product_code)
        if not info:
            return f"未找到商品 {product_code} 的营养信息。"
        if compact:
            return fmt.format_nutrition_compact(info)
        return fmt.format_nutrition(info)

    @mcp.tool()
    def nearby_stores(ctx: Context, city: str | None = None, keyword: str | None = None) -> str:
        """搜索附近门店，按城市或关键词筛选。

        When:
        - 用户说"附近有什么店"、"找一家店"

        Args:
            city: 可选，城市名
            keyword: 可选，关键词搜索
        """
        user_id, err = _require_auth(ctx, "nearby_stores")
        if err: return err
        stores = adapter.nearby_stores(city=city, keyword=keyword)
        return fmt.format_nearby_stores(stores)

    @mcp.tool()
    def store_detail(ctx: Context, store_id: str) -> str:
        """查看门店详情：地址、营业时间、电话（脱敏显示）、服务。当用户问"这家店在哪"、"几点关门"时使用。

        Args:
            store_id: 门店ID，从 nearby_stores 获取
        """
        user_id, err = _require_auth(ctx, "store_detail")
        if err: return err
        store = adapter.store_detail(store_id)
        if not store:
            return f"未找到门店 {store_id}。"
        return fmt.format_store_detail(store)

    @mcp.tool()
    def stars_mall_products(ctx: Context, category: str | None = None) -> str:
        """浏览积分商城，查看可兑换商品。

        When:
        - 用户问"积分能换什么"、"星星商城"

        Args:
            category: 可选分类筛选
        """
        user_id, err = _require_auth(ctx, "stars_mall_products")
        if err: return err
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        products = adapter.stars_mall_products(category)
        user = adapter.get_current_user(user_id)
        user_stars = user["star_balance"] if user else 0
        return fmt.format_stars_mall(products, user_stars)

    @mcp.tool()
    def stars_product_detail(ctx: Context, product_code: str) -> str:
        """查看积分商品详情。当用户想了解某个积分商品的兑换条件时使用。

        Args:
            product_code: 积分商品编号，从 stars_mall_products 获取
        """
        user_id, err = _require_auth(ctx, "stars_product_detail")
        if err: return err
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        product = adapter.stars_product_detail(product_code)
        if not product:
            return f"未找到积分商品 {product_code}。"
        user = adapter.get_current_user(user_id)
        user_stars = user["star_balance"] if user else 0
        return fmt.format_stars_product_detail(product, user_stars)

    @mcp.tool()
    def stars_redeem(ctx: Context, product_code: str, idempotency_key: str) -> str:
        """用星星兑换积分商城商品。[风险等级: L3]

        安全限制: 每用户每天最多 10 次
        Preconditions:
        - 先查看 stars_product_detail 确认商品
        - 用户确认后才可调用

        Args:
            product_code: 积分商品编号
            idempotency_key: 幂等键，防重复兑换
        """
        user_id, err = _require_auth(ctx, "stars_redeem")
        if err: return err
        if not features.get("stars_mall", True):
            return _FEATURE_NOT_AVAILABLE
        if rerr := _check_rate_limit("stars_redeem", user_id):
            return rerr
        result = adapter.stars_redeem(product_code, user_id,
                                      idempotency_key=idempotency_key)
        return fmt.format_stars_redeem_result(result)

    @mcp.tool()
    def delivery_addresses(ctx: Context) -> str:
        """查询我的配送地址列表。

        When:
        - 用户选择外送时，先查看/选择配送地址
        """
        user_id, err = _require_auth(ctx, "delivery_addresses")
        if err: return err
        addrs = adapter.delivery_addresses(user_id)
        return fmt.format_delivery_addresses(addrs)

    @mcp.tool()
    def create_address(ctx: Context, city: str, address: str, address_detail: str,
                       contact_name: str, phone: str) -> str:
        """创建新的配送地址。[风险等级: L2]

        Args:
            city: 城市
            address: 详细地址
            address_detail: 门牌号
            contact_name: 联系人
            phone: 手机号（11位）
        """
        user_id, err = _require_auth(ctx, "create_address")
        if err: return err
        if rerr := _check_rate_limit("create_address", user_id):
            return rerr
        if not phone_re.match(phone):
            return "手机号格式无效，请输入11位手机号。"
        existing = adapter.delivery_addresses(user_id)
        if len(existing) >= val.max_addresses:
            return f"最多保存 {val.max_addresses} 个地址，请先删除不用的地址。"
        if not all([city.strip(), address.strip(), address_detail.strip(),
                    contact_name.strip()]):
            return "地址信息不完整，请填写所有必填项。"
        addr = adapter.create_address(user_id, city, address,
                                      address_detail, contact_name, phone)
        return fmt.format_new_address(addr)

    @mcp.tool()
    def store_coupons(ctx: Context, store_id: str) -> str:
        """查询在指定门店可使用的优惠券。

        Preconditions:
        - 必须先调用 nearby_stores 获取门店信息

        Args:
            store_id: 门店ID
        """
        user_id, err = _require_auth(ctx, "store_coupons")
        if err: return err
        store = adapter.store_detail(store_id)
        store_name = store["name"] if store else store_id
        coupons = adapter.store_coupons(store_id, user_id)
        return fmt.format_store_coupons(coupons, store_name)

    @mcp.tool()
    def calculate_price(ctx: Context, store_id: str, items: list[dict],
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
        user_id, err = _require_auth(ctx, "calculate_price")
        if err: return err
        if verr := _validate_cart_items(items):
            return verr
        result = adapter.calculate_price(store_id, items, coupon_code)
        return fmt.format_price_calculation(result)

    @mcp.tool()
    def create_order(ctx: Context, store_id: str, items: list[dict], pickup_type: str,
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
        user_id, err = _require_auth(ctx, "create_order")
        if err: return err
        if rerr := _check_rate_limit("create_order", user_id):
            return rerr
        if verr := _validate_cart_items(items):
            return verr
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
                                      user_id=user_id,
                                      idempotency_key=idempotency_key,
                                      coupon_code=coupon_code,
                                      address_id=address_id)
        return fmt.format_order_created(result)

    @mcp.tool()
    def order_status(ctx: Context, order_id: str) -> str:
        """查询订单状态详情。当用户问"我的订单怎么样了"、"做好了吗"时使用。

        Args:
            order_id: 订单号，从 create_order 或 my_orders 获取
        """
        user_id, err = _require_auth(ctx, "order_status")
        if err: return err
        order = adapter.order_status(order_id, user_id)
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
