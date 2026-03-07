"""Coffee Company MCP Server — Phase 1 read-only tools.

Maps 1:1 to real HTTP Open Platform APIs (openapi.coffeecompany.com).
In production this service sits behind Kong; auth/rate-limiting/ACL are
handled by Kong before requests reach here.  In demo mode, mock data is used.
"""

from mcp.server.fastmcp import FastMCP

from . import formatters, mock_data

mcp = FastMCP(
    "Coffee Company",
    instructions=(
        "Coffee Company MCP Server（B2B 开放平台）。\n"
        "提供会员查询、券码查询、权益查询、资产查询、支付状态查询等能力。\n"
        "所有接口映射自 openapi.coffeecompany.com 现有 HTTP API。\n"
        "鉴权由 Kong 网关处理，MCP 层不涉及签名逻辑。"
    ),
)

# ---------------------------------------------------------------------------
# Tool 1: member_query  →  POST /crmadapter/account/query
# ---------------------------------------------------------------------------

@mcp.tool()
def member_query(
    mobile: str | None = None,
    open_id: str | None = None,
    member_id: str | None = None,
) -> str:
    """查询Coffee Company会员信息。通过手机号、openId 或会员ID查询。

    对应 HTTP API: POST /crmadapter/account/query

    Args:
        mobile: 手机号（模糊匹配，如 "138****1234"）
        open_id: 第三方平台 openId
        member_id: Coffee Company会员ID
    """
    if not any([mobile, open_id, member_id]):
        return "请提供 mobile、open_id 或 member_id 中的至少一个。"
    m = mock_data.member_query(mobile, open_id, member_id)
    if not m:
        return "未找到匹配的会员信息。请检查查询参数。"
    return formatters.format_member(m)


# ---------------------------------------------------------------------------
# Tool 2: member_tier  →  POST /crmadapter/account/memberTier
# ---------------------------------------------------------------------------

@mcp.tool()
def member_tier(member_id: str) -> str:
    """查询会员等级详情，包括当前星星数、等级有效期、距下一级的差距。

    对应 HTTP API: POST /crmadapter/account/memberTier

    Args:
        member_id: Coffee Company会员ID
    """
    t = mock_data.member_tier(member_id)
    if not t:
        return f"未找到会员 {member_id} 的等级信息。"
    return formatters.format_member_tier(t)


# ---------------------------------------------------------------------------
# Tool 3: member_benefits  →  POST /crmadapter/customers/getBenefits
# ---------------------------------------------------------------------------

@mcp.tool()
def member_benefits(member_id: str) -> str:
    """查询会员 8 项权益状态（新人礼、生日奖励、升级奖励等）。

    对应 HTTP API: POST /crmadapter/customers/getBenefits

    状态说明: 0=隐藏, 1=未解锁, 2=可使用, 3=已使用/已过期

    Args:
        member_id: Coffee Company会员ID
    """
    b = mock_data.member_benefits(member_id)
    if not b:
        return f"未找到会员 {member_id} 的权益信息。"
    return formatters.format_member_benefits(member_id, b)


# ---------------------------------------------------------------------------
# Tool 4: member_benefit_list  →  POST /crmadapter/asset/coupon/getBenefitList
# ---------------------------------------------------------------------------

@mcp.tool()
def member_benefit_list(member_id: str) -> str:
    """查询会员的优惠券和权益券列表。

    对应 HTTP API: POST /crmadapter/asset/coupon/getBenefitList

    Args:
        member_id: Coffee Company会员ID
    """
    items = mock_data.member_benefit_list(member_id)
    return formatters.format_benefit_list(items)


# ---------------------------------------------------------------------------
# Tool 5: coupon_query  →  POST /coupon/query
# ---------------------------------------------------------------------------

@mcp.tool()
def coupon_query(order_id: str) -> str:
    """查询订单关联的券码生成状态。

    对应 HTTP API: POST /coupon/query

    Args:
        order_id: 订单号
    """
    coupons = mock_data.coupon_query(order_id)
    return formatters.format_coupon_query(coupons, order_id)


# ---------------------------------------------------------------------------
# Tool 6: coupon_detail  →  POST /coupon/detail
# ---------------------------------------------------------------------------

@mcp.tool()
def coupon_detail(coupon_code: str) -> str:
    """查询单张券码的详细信息，包括状态、面值、有效期、核销次数。

    对应 HTTP API: POST /coupon/detail

    券码状态: 4=未使用, 10=已使用, 20=已过期, 30=已作废

    Args:
        coupon_code: 券码（如 "CC20260301A001"）
    """
    c = mock_data.coupon_detail(coupon_code)
    if not c:
        return f"未找到券码 {coupon_code}。请检查券码是否正确。"
    return formatters.format_coupon_detail(c)


# ---------------------------------------------------------------------------
# Tool 7: equity_query  →  POST /equity/query
# ---------------------------------------------------------------------------

@mcp.tool()
def equity_query(order_id: str) -> str:
    """查询权益发放状态（电子券是否发放成功）。

    对应 HTTP API: POST /equity/query

    Args:
        order_id: 权益订单号
    """
    e = mock_data.equity_query(order_id)
    if not e:
        return f"未找到权益订单 {order_id}。"
    return formatters.format_equity_detail(e)


# ---------------------------------------------------------------------------
# Tool 8: equity_detail  →  POST /equity/detail
# ---------------------------------------------------------------------------

@mcp.tool()
def equity_detail(order_id: str) -> str:
    """查询权益详情，包括券码、状态、金额、核销次数等完整信息。

    对应 HTTP API: POST /equity/detail

    Args:
        order_id: 权益订单号
    """
    e = mock_data.equity_detail(order_id)
    if not e:
        return f"未找到权益订单 {order_id}。"
    return formatters.format_equity_detail(e)


# ---------------------------------------------------------------------------
# Tool 9: assets_list  →  POST /assets/list
# ---------------------------------------------------------------------------

@mcp.tool()
def assets_list(member_id: str) -> str:
    """查询客户全部资产（优惠券 + 权益券），一览式展示。

    对应 HTTP API: POST /assets/list

    Args:
        member_id: Coffee Company会员ID
    """
    a = mock_data.assets_list(member_id)
    if not a:
        return f"未找到会员 {member_id} 的资产信息。"
    return formatters.format_assets(member_id, a)


# ---------------------------------------------------------------------------
# Tool 10: cashier_pay_query  →  POST /cashier/payQuery
# ---------------------------------------------------------------------------

@mcp.tool()
def cashier_pay_query(pay_token: str) -> str:
    """查询支付状态（收银台下单后的支付结果）。

    对应 HTTP API: POST /cashier/payQuery

    状态: 0=支付中, 1=支付成功, 2=支付失败

    Args:
        pay_token: 支付令牌（收银下单接口返回的 payToken）
    """
    p = mock_data.cashier_pay_query(pay_token)
    if not p:
        return f"未找到支付令牌 {pay_token} 对应的支付记录。"
    return formatters.format_pay_query(p, pay_token)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("coffee://api/catalog")
def api_catalog() -> str:
    """Coffee Company MCP 开放平台接口目录"""
    return (
        "Coffee Company MCP 开放平台 — 接口目录\n\n"
        "Phase 1 只读 Tools（当前可用）：\n"
        "  1. member_query        → POST /crmadapter/account/query\n"
        "  2. member_tier         → POST /crmadapter/account/memberTier\n"
        "  3. member_benefits     → POST /crmadapter/customers/getBenefits\n"
        "  4. member_benefit_list → POST /crmadapter/asset/coupon/getBenefitList\n"
        "  5. coupon_query        → POST /coupon/query\n"
        "  6. coupon_detail       → POST /coupon/detail\n"
        "  7. equity_query        → POST /equity/query\n"
        "  8. equity_detail       → POST /equity/detail\n"
        "  9. assets_list         → POST /assets/list\n"
        "  10. cashier_pay_query  → POST /cashier/payQuery\n\n"
        "Phase 2 写入 Tools（规划中）：\n"
        "  - member_register, member_bind\n"
        "  - coupon_create, coupon_claim\n"
        "  - equity_send, benefit_issue, srkit_send\n\n"
        "Phase 3 交易闭环（规划中）：\n"
        "  - cashier_checkout, order_push\n"
        "  - stars_lock, stars_redeem\n"
        "  - coupon_cancel, equity_cancel, order_refund\n"
    )


@mcp.resource("coffee://auth/guide")
def auth_guide() -> str:
    """鉴权说明"""
    return (
        "Coffee Company MCP 鉴权说明\n\n"
        "MCP Server 部署在 Kong 网关后面，鉴权由 Kong 处理：\n\n"
        "1. B2B 客户使用已有的 appKey + appSecret\n"
        "2. 按 HMAC-SHA256 规范签名请求\n"
        "3. Kong 验签 → 注入 Consumer 身份 → 转发到 MCP Adapter\n"
        "4. MCP Adapter 根据 Consumer Groups 过滤可用 Tool\n\n"
        "Demo 模式下无需签名，直接可用。\n"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
