"""Semantic formatters: API JSON → natural language for LLM consumption.

Each formatter transforms a raw backend response dict into a human-readable
string that an LLM can directly use in conversation.
"""

from . import mock_data


def format_member(m: dict) -> str:
    tier = mock_data.TIER_NAMES.get(m["member_tier"], m["member_tier"])
    return (
        f"**会员信息**\n\n"
        f"- 姓名：{m['name']}\n"
        f"- 手机：{m['mobile']}\n"
        f"- 会员ID：{m['member_id']}\n"
        f"- 等级：{tier}（{m['member_tier']}）\n"
        f"- 星星余额：{m['star_balance']} 颗\n"
        f"- 等级有效期：至 {m['tier_expire_date']}\n"
        f"- 注册时间：{m['registration_date']}\n"
        f"- 渠道：{m['channel']}"
    )


def format_member_tier(t: dict) -> str:
    lines = [
        f"**会员等级详情**\n",
        f"- 当前等级：{t['tier_name']}（{t['member_tier']}）",
        f"- 星星余额：{t['star_balance']} 颗",
        f"- 等级有效期：至 {t['tier_expire_date']}",
    ]
    if t.get("next_tier"):
        lines.append(f"- 下一等级：{t['next_tier_name']}（{t['next_tier']}）")
        lines.append(f"- 距升级还需：{t['stars_to_next']} 颗星")
    else:
        lines.append("- 已达最高等级")
    return "\n".join(lines)


def format_member_benefits(member_id: str, benefits: dict) -> str:
    lines = [f"**会员权益状态**（{member_id}）\n"]
    for key, status in benefits.items():
        name = mock_data.BENEFIT_NAMES.get(key, key)
        status_name = mock_data.BENEFIT_STATUS_NAMES.get(status, str(status))
        icon = {0: "  ", 1: "🔒", 2: "✅", 3: "⬜"}.get(status, "  ")
        lines.append(f"- {icon} {name}：{status_name}")
    active = sum(1 for v in benefits.values() if v == 2)
    lines.append(f"\n共 {active} 项权益可使用。")
    return "\n".join(lines)


def format_benefit_list(items: list[dict]) -> str:
    if not items:
        return "该会员暂无可用券。"
    lines = [f"**会员券列表**（共 {len(items)} 张）\n"]
    for c in items:
        value = f"面值 ¥{c['face_value']:.0f}" if c.get("face_value") else "无面值"
        lines.append(
            f"- **{c['name']}**（{c['type']}）\n"
            f"  券号：{c['coupon_no']} | {c['status']} | 有效期至 {c['valid_end']} | {value}"
        )
    return "\n".join(lines)


def format_coupon_query(coupons: list[dict], order_id: str) -> str:
    if not coupons:
        return f"订单 {order_id} 未找到关联券码。"
    lines = [f"**订单 {order_id} 关联券码**（共 {len(coupons)} 张）\n"]
    for c in coupons:
        lines.append(
            f"- 券码：{c['coupon_code']}\n"
            f"  {c['product_name']} | {c['status_name']} | "
            f"有效期 {c['valid_start'][:10]} 至 {c['valid_end'][:10]}"
        )
    return "\n".join(lines)


def format_coupon_detail(c: dict) -> str:
    return (
        f"**券码详情**\n\n"
        f"- 券码：{c['coupon_code']}\n"
        f"- 券号：{c['coupon_no']}\n"
        f"- 产品：{c['product_name']}\n"
        f"- 状态：{c['status_name']}（代码 {c['status']}）\n"
        f"- 面值：¥{c['face_value']:.0f}\n"
        f"- 有效期：{c['valid_start'][:10]} 至 {c['valid_end'][:10]}\n"
        f"- 已核销：{c['redeem_times']} / {c['max_redeem_times']} 次\n"
        f"- 活动ID：{c['campaign_id']}\n"
        f"- 订单号：{c['order_id']}"
    )


def format_equity_detail(e: dict) -> str:
    status_icon = "✅" if e["status_code"] == 100 else "❌"
    return (
        f"**权益详情**\n\n"
        f"- 订单号：{e['order_id']}\n"
        f"- 状态：{status_icon} {e['status_name']}（代码 {e['status_code']}）\n"
        f"- 活动ID：{e['campaign_id']}\n"
        f"- 券码：{e['coupon_code']}\n"
        f"- 金额：¥{e['total_amount']:.0f}\n"
        f"- 有效期：{e['valid_start'][:10]} 至 {e['valid_end'][:10]}\n"
        f"- 发放时间：{e['binding_time']}\n"
        f"- 已核销：{e['redeem_times']} 次"
    )


def format_assets(member_id: str, assets: dict) -> str:
    upp = assets.get("upp_coupons", [])
    ben = assets.get("benefit_coupons", [])
    total = len(upp) + len(ben)
    lines = [f"**客户资产总览**（{member_id}）\n"]
    lines.append(f"优惠券 {len(upp)} 张 + 权益券 {len(ben)} 张 = 共 {total} 张\n")

    if upp:
        lines.append("**优惠券：**")
        for c in upp:
            val = f"¥{c['face_value']:.0f}" if c.get("face_value") else "无面值"
            lines.append(f"- {c['name']}（{c['coupon_no']}）| {c['status']} | 至 {c['valid_end']} | {val}")
    if ben:
        lines.append("\n**权益券：**")
        for c in ben:
            val = f"¥{c['face_value']:.0f}" if c.get("face_value") else "无面值"
            lines.append(f"- {c['name']}（{c['coupon_no']}）| {c['status']} | 至 {c['valid_end']} | {val}")
    return "\n".join(lines)


def format_pay_query(p: dict, pay_token: str) -> str:
    status_icon = {0: "⏳", 1: "✅", 2: "❌"}.get(p["status"], "?")
    return (
        f"**支付状态查询**\n\n"
        f"- 支付令牌：{pay_token}\n"
        f"- 状态：{status_icon} {p['state_msg']}\n"
        f"- 订单号：{p['order_id']}\n"
        f"- 金额：¥{p['amount']:.0f}\n"
        f"- 支付方式：{p['method']}"
    )
