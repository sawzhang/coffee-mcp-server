"""Starbucks MCP Server - Phase 1 read-only tools demo."""

from mcp.server.fastmcp import FastMCP

from . import formatters, mock_data

mcp = FastMCP(
    "Starbucks China",
    instructions=(
        "星巴克中国 MCP Server。"
        "可查询附近门店、浏览菜单、查看产品详情、检查库存、获取促销活动。"
        "所有工具需要有效的 API Key（demo 可用：demo-key-001）。"
    ),
)

# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

def _check_key(api_key: str | None) -> None:
    """Validate API key, raise if invalid."""
    if not api_key or not mock_data.validate_api_key(api_key):
        raise ValueError(
            "API Key 无效或缺失。请使用有效的 API Key。"
            "（Demo 可用 key：demo-key-001 / sbux-test-2026 / starbucks-dev）"
        )


# ---------------------------------------------------------------------------
# Tool 1: search_nearby_stores
# ---------------------------------------------------------------------------

@mcp.tool()
def search_nearby_stores(
    api_key: str,
    city: str | None = None,
    keyword: str | None = None,
    latitude: float | None = None,
    longitude: float | None = None,
    radius: float = 3000,
) -> str:
    """搜索附近的星巴克门店。支持按城市、地标关键词或坐标查询。

    Args:
        api_key: 开放平台 API Key（demo 可用：demo-key-001）
        city: 城市名，如"上海"、"北京"
        keyword: 地标或区域关键词，如"陆家嘴"、"静安"
        latitude: 用户纬度（与 longitude 一起使用）
        longitude: 用户经度（与 latitude 一起使用）
        radius: 搜索半径，单位米，默认 3000
    """
    _check_key(api_key)
    stores = mock_data.search_stores(city, keyword, latitude, longitude, radius)
    return formatters.format_stores(stores)


# ---------------------------------------------------------------------------
# Tool 2: get_store_detail
# ---------------------------------------------------------------------------

@mcp.tool()
def get_store_detail(api_key: str, store_id: str) -> str:
    """获取星巴克门店详情，包括地址、营业时间、可用服务等。

    Args:
        api_key: 开放平台 API Key
        store_id: 门店编号，如"SH-LJZ-001"
    """
    _check_key(api_key)
    store = mock_data.get_store(store_id)
    if not store:
        return f"未找到门店编号为 {store_id} 的门店。请检查门店编号是否正确。"
    return formatters.format_store_detail(store)


# ---------------------------------------------------------------------------
# Tool 3: get_menu
# ---------------------------------------------------------------------------

@mcp.tool()
def get_menu(api_key: str, category: str | None = None) -> str:
    """获取星巴克菜单。可按分类筛选。

    Args:
        api_key: 开放平台 API Key
        category: 可选分类筛选。可选值：espresso(浓缩咖啡)、cold_brew(冷萃)、frappuccino(星冰乐)、tea(茶饮)、seasonal(当季限定)、food(轻食)
    """
    _check_key(api_key)
    category_name = mock_data.MENU_CATEGORIES.get(category) if category else None
    products = mock_data.get_menu(category)
    return formatters.format_menu(products, category_name)


# ---------------------------------------------------------------------------
# Tool 4: get_product_detail
# ---------------------------------------------------------------------------

@mcp.tool()
def get_product_detail(
    api_key: str,
    product_id: str | None = None,
    name: str | None = None,
) -> str:
    """获取单个产品的详细信息，包括杯型价格、热量、定制选项。

    Args:
        api_key: 开放平台 API Key
        product_id: 产品编号，如"ESP-001"
        name: 产品名称关键词，如"馥芮白"、"拿铁"
    """
    _check_key(api_key)
    if not product_id and not name:
        return "请提供 product_id 或 name 来查询产品详情。"
    product = mock_data.get_product(product_id, name)
    if not product:
        return f"未找到匹配的产品。请尝试其他关键词或产品编号。"
    return formatters.format_product_detail(product)


# ---------------------------------------------------------------------------
# Tool 5: check_store_inventory
# ---------------------------------------------------------------------------

@mcp.tool()
def check_store_inventory(
    api_key: str,
    store_id: str,
    product_id: str | None = None,
) -> str:
    """查询指定门店的产品库存情况。

    Args:
        api_key: 开放平台 API Key
        store_id: 门店编号
        product_id: 可选，指定产品编号查询单个产品库存
    """
    _check_key(api_key)
    store = mock_data.get_store(store_id)
    store_name = store["name"] if store else store_id
    items = mock_data.check_inventory(store_id, product_id)
    if not items:
        return f"未找到门店 {store_id} 的库存信息。"
    return formatters.format_inventory(items, store_name)


# ---------------------------------------------------------------------------
# Tool 6: get_promotions
# ---------------------------------------------------------------------------

@mcp.tool()
def get_promotions(api_key: str) -> str:
    """获取当前星巴克促销活动信息。

    Args:
        api_key: 开放平台 API Key
    """
    _check_key(api_key)
    promos = mock_data.get_promotions()
    return formatters.format_promotions(promos)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------

@mcp.resource("starbucks://menu/seasonal")
def seasonal_menu() -> str:
    """当季限定菜单"""
    products = mock_data.get_menu("seasonal")
    return formatters.format_menu(products, "当季限定")


@mcp.resource("starbucks://promotions/current")
def current_promotions() -> str:
    """当前促销活动"""
    return formatters.format_promotions(mock_data.get_promotions())


@mcp.resource("starbucks://customization/guide")
def customization_guide() -> str:
    """饮品定制选项说明"""
    return (
        "星巴克饮品定制指南：\n\n"
        "1. 杯型：中杯(Tall) / 大杯(Grande) / 超大杯(Venti)\n"
        "2. 奶类：全脂奶(默认) / 脱脂奶 / 燕麦奶(+5元) / 椰奶(+5元) / 杏仁奶(+5元)\n"
        "3. 温度：热 / 冰 / 温（部分饮品限选）\n"
        "4. 甜度：标准 / 少糖 / 半糖 / 无糖\n"
        "5. 加浓：可额外添加一份浓缩（extra shot），+4元\n"
        "6. 糖浆：香草 / 焦糖 / 榛果 / 太妃，+4元/泵\n"
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    mcp.run()


if __name__ == "__main__":
    main()
