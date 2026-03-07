"""Semantic formatters: JSON -> natural language for LLM consumption."""

import math


def format_stores(stores: list[dict]) -> str:
    if not stores:
        return "附近暂无星巴克门店。"
    lines = [f"为您找到 {len(stores)} 家星巴克门店：\n"]
    for s in stores:
        services = [
            label
            for key, label in [
                ("has_seating", "堂食"),
                ("drivethru", "得来速"),
                ("delivery", "外卖配送"),
                ("mobile_order", "移动点单"),
            ]
            if s.get(key)
        ]
        lines.append(
            f"**{s['name']}**（{s['district']}）\n"
            f"- 地址：{s['address']}\n"
            f"- 距您约 {s['distance']} 米，步行约 {math.ceil(s['distance'] / 80)} 分钟\n"
            f"- 营业时间：{s['open_time']} - {s['close_time']}\n"
            f"- 服务：{'、'.join(services)}\n"
            f"- 门店编号：{s['store_id']}"
        )
    return "\n\n".join(lines)


def format_store_detail(store: dict) -> str:
    services = [
        label
        for key, label in [
            ("has_seating", "堂食"),
            ("drivethru", "得来速"),
            ("delivery", "外卖配送"),
            ("mobile_order", "移动点单"),
        ]
        if store.get(key)
    ]
    return (
        f"**{store['name']}**\n\n"
        f"- 地址：{store['address']}（{store['district']}，{store['city']}）\n"
        f"- 营业时间：{store['open_time']} - {store['close_time']}\n"
        f"- 电话：{store['phone']}\n"
        f"- 可用服务：{'、'.join(services)}\n"
        f"- 门店编号：{store['store_id']}\n"
        f"- 坐标：({store['latitude']}, {store['longitude']})"
    )


def format_menu(products: list[dict], category_name: str | None = None) -> str:
    if not products:
        return "未找到相关菜单。"
    title = f"当前{'「' + category_name + '」' if category_name else ''}菜单（共 {len(products)} 款）：\n"
    lines = [title]
    for p in products:
        size_info = " / ".join(
            f"{v['name']} ¥{v['price']:.0f}" for v in p["sizes"].values()
        )
        tags = []
        if p.get("is_new"):
            tags.append("新品")
        if p.get("is_seasonal"):
            tags.append("限定")
        tag_str = f" 【{'｜'.join(tags)}】" if tags else ""
        lines.append(
            f"**{p['name']}** ({p['name_en']}){tag_str}\n"
            f"  {p['description']}\n"
            f"  价格：{size_info}"
        )
    return "\n\n".join(lines)


def format_product_detail(product: dict) -> str:
    size_lines = []
    for key, v in product["sizes"].items():
        cal = product["calories"].get(key, "")
        cal_str = f"，约 {cal} 大卡" if cal else ""
        size_lines.append(f"  - {v['name']}（{key}）：¥{v['price']:.0f}{cal_str}")

    custom = product["customizations"]
    custom_lines = []
    if custom.get("milk"):
        custom_lines.append(f"  - 奶类选择：{'、'.join(custom['milk'])}")
    if custom.get("temperature"):
        custom_lines.append(f"  - 温度选择：{'、'.join(custom['temperature'])}")
    if custom.get("sweetness"):
        custom_lines.append(f"  - 甜度选择：{'、'.join(custom['sweetness'])}")
    if custom.get("extra_shot"):
        custom_lines.append("  - 可加浓（extra shot）")

    tags = []
    if product.get("is_new"):
        tags.append("新品")
    if product.get("is_seasonal"):
        tags.append("当季限定")
    tag_str = f"  标签：{'、'.join(tags)}\n" if tags else ""

    return (
        f"**{product['name']}** ({product['name_en']})\n\n"
        f"  {product['description']}\n\n"
        f"{tag_str}"
        f"  杯型与价格：\n{''.join(l + chr(10) for l in size_lines)}\n"
        f"  定制选项：\n{''.join(l + chr(10) for l in custom_lines)}"
    )


def format_inventory(items: list[dict], store_name: str = "") -> str:
    if not items:
        return "未找到库存信息。"
    header = f"{'「' + store_name + '」' if store_name else ''}库存情况：\n"
    lines = [header]
    for item in items:
        status = "有货" if item["in_stock"] else "售罄"
        note = f"（{item['note']}）" if item.get("note") else ""
        lines.append(f"- {item['name']}：{status}{note}")
    return "\n".join(lines)


def format_promotions(promos: list[dict]) -> str:
    if not promos:
        return "当前暂无促销活动。"
    lines = ["当前促销活动：\n"]
    for p in promos:
        lines.append(
            f"**{p['title']}**\n"
            f"  {p['description']}\n"
            f"  有效期：{p['valid_from']} 至 {p['valid_to']}\n"
            f"  使用条件：{p['conditions']}"
        )
    return "\n\n".join(lines)
