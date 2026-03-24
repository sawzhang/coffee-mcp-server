# 品牌接入指南

> 从零开始接入 MCP 点单平台，让你的品牌被所有 AI 助手触达

---

## 接入总览

```
你需要做的                            我们已经做好的
──────────                           ──────────────
1. 创建 brand.yaml (30 min)          21 个 MCP 工具
2. 实现 BrandAdapter (1-2 周)        L0-L3 安全架构
3. 部署 & 测试 (1-2 天)              确认令牌 + 幂等性
                                     多品牌隔离
                                     Streamable HTTP
```

**最快路径：** 只写 `brand.yaml`，用 DemoAdapter 跑通全流程 → 再替换真实 API。

---

## Step 1: 创建品牌配置（30 分钟）

在 `brands/` 目录下创建你的品牌文件夹和配置：

```bash
mkdir -p brands/my_brand
```

创建 `brands/my_brand/brand.yaml`：

```yaml
# ===== 必填 =====
brand_id: my_brand
brand_name: "我的茶饮"
server_name: "我的茶饮 ToC"
default_user_id: "USER_001"    # 测试用户ID

instructions: |
  我的茶饮消费者自助 MCP Server。
  提供菜单浏览、门店查找、优惠券、积分兑换、下单点餐等能力。
  所有工具基于登录用户身份自动识别。

# ===== 菜单定制选项 =====
size_options:
  regular: { name: "常规",  extra_price: 0 }
  large:   { name: "大杯",  extra_price: 3 }

milk_options:
  whole: { name: "鲜奶",  extra_price: 0 }
  oat:   { name: "燕麦奶", extra_price: 4 }

temp_options:
  hot:  { name: "热" }
  iced: { name: "冰" }

sweetness_options:
  normal: { name: "正常糖" }
  seven:  { name: "七分糖" }
  half:   { name: "半糖" }
  none:   { name: "不加糖" }

extra_options:
  boba:    { name: "珍珠", price: 3 }
  pudding: { name: "布丁", price: 4 }

# ===== 验证规则 =====
validation:
  phone_pattern: "^1\\d{10}$"       # 中国手机号格式
  valid_sizes: ["regular", "large"]
  valid_milks: ["whole", "oat"]
  valid_temps: ["hot", "iced"]
  valid_extras: ["boba", "pudding"]
  valid_pickup: ["自提", "外送"]     # 你支持的取餐方式
  max_quantity: 50                   # 单品最大数量
  max_items_per_order: 10            # 每单最多商品数
  max_addresses: 5                   # 最多保存地址数

# ===== 限流策略 =====
rate_limits:
  L0: { max_calls: 60, window_seconds: 60 }     # 公开数据: 60次/分
  L1: { max_calls: 30, window_seconds: 60 }     # 用户数据: 30次/分
  L2: { max_calls: 5,  window_seconds: 3600 }   # 写操作: 5次/小时
  L3: { max_calls: 10, window_seconds: 86400 }  # 下单: 10次/天

# ===== 功能开关 =====
features:
  campaigns: true      # 活动日历
  coupons: true        # 优惠券
  stars_mall: false     # 积分商城（如不需要可关闭）
  delivery: true       # 外送
  nutrition: true       # 营养信息

# ===== 适配器（Step 2 完成后配置）=====
# adapter:
#   module: "brands.my_brand.adapter"
#   class: "MyBrandAdapter"
```

**验证配置：**

```bash
# 用 DemoAdapter 测试配置是否正确
BRAND=my_brand uv run python -c "
from coffee_mcp.brand_config import load_brand_config, load_brand_adapter
from coffee_mcp.toc_server import create_toc_server

config = load_brand_config('my_brand')
print(f'Brand: {config.brand_name}')
print(f'Sizes: {list(config.size_options.keys())}')
print(f'Extras: {list(config.extra_options.keys())}')

adapter = load_brand_adapter(config)
server = create_toc_server(config, adapter)
tools = server._tool_manager.list_tools()
print(f'Tools: {len(tools)} registered')
print('Config OK!')
"
```

---

## Step 2: 实现品牌适配器（1-2 周）

适配器是你的品牌后端 API 与 MCP 平台之间的桥梁。你需要实现 21 个方法，每个方法调用你自己的后端接口。

创建 `brands/my_brand/adapter.py`：

```python
"""我的茶饮 — 品牌适配器

将 MCP 工具调用转换为品牌后端 HTTP API 调用。
"""
import httpx
from coffee_mcp.brand_adapter import BrandAdapter
from coffee_mcp.brand_config import BrandConfig
from coffee_mcp.utils import random_id


class MyBrandAdapter(BrandAdapter):

    def __init__(self, config: BrandConfig):
        self.config = config
        self.base_url = "https://api.mybrand.com"
        self.client = httpx.Client(timeout=10.0)

    def _headers(self, user_id: str) -> dict:
        """构建请求头（生产环境从 OAuth token 提取）"""
        return {"Authorization": f"Bearer {user_id}"}

    # ─── Discovery ─────────────────────────────────────

    def campaign_calendar(self, month: str | None = None) -> list[dict]:
        """GET /api/campaigns?month=yyyy-MM"""
        params = {"month": month} if month else {}
        resp = self.client.get(f"{self.base_url}/api/campaigns", params=params)
        resp.raise_for_status()
        # 转换为平台期望的格式
        return [
            {
                "campaign_id": c["id"],
                "title": c["title"],
                "description": c["desc"],
                "start_date": c["start"],
                "end_date": c["end"],
                "status": c["status"],       # "进行中"/"未开始"/"已结束"
                "tags": c.get("tags", []),
                "image": c.get("image", ""),
            }
            for c in resp.json()["campaigns"]
        ]

    def available_coupons(self) -> list[dict]:
        """GET /api/coupons/available"""
        resp = self.client.get(f"{self.base_url}/api/coupons/available")
        resp.raise_for_status()
        return [
            {
                "coupon_id": c["id"],
                "name": c["name"],
                "description": c["desc"],
                "discount_value": c["discount"],
                "min_order": c.get("min_order", 0),
                "valid_days": c["valid_days"],
                "status": c["status"],       # "可领取"/"已领取"
                "applicable": c.get("products", []),
                "image": c.get("image", ""),
            }
            for c in resp.json()["coupons"]
        ]

    def claim_all_coupons(self, user_id: str) -> dict:
        """POST /api/coupons/claim-all"""
        resp = self.client.post(
            f"{self.base_url}/api/coupons/claim-all",
            headers=self._headers(user_id),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "claimed_count": data["claimed"],
            "already_claimed": data["already"],
            "claimed_coupons": [
                {"name": c["name"], "valid_days": c["valid_days"]}
                for c in data["items"]
            ],
        }

    # ─── Account ───────────────────────────────────────

    def get_current_user(self, user_id: str) -> dict | None:
        """GET /api/user/profile"""
        resp = self.client.get(
            f"{self.base_url}/api/user/profile",
            headers=self._headers(user_id),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        u = resp.json()
        return {
            "member_id": u["id"],
            "name": u["name"],
            "member_tier": u["tier"],
            "star_balance": u["points"],
            "tier_expire_date": u["tier_expire"],
            "registration_date": u["registered"],
        }

    def my_account(self, user_id: str) -> dict | None:
        """GET /api/user/account"""
        resp = self.client.get(
            f"{self.base_url}/api/user/account",
            headers=self._headers(user_id),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        return {
            "name": data["name"],
            "tier_info": {
                "member_tier": data["tier"],
                "tier_name": data["tier_name"],
                "star_balance": data["points"],
                "tier_expire_date": data["tier_expire"],
                "next_tier": data.get("next_tier"),
                "next_tier_name": data.get("next_tier_name", ""),
                "stars_to_next": data.get("points_to_next", 0),
            },
            "active_benefits": data.get("active_benefits", 0),
            "coupon_count": data.get("coupon_count", 0),
            "registration_date": data["registered"],
        }

    def my_coupons(self, user_id: str, status: str | None = None) -> list[dict]:
        """GET /api/user/coupons?status=valid"""
        params = {"status": status} if status else {}
        resp = self.client.get(
            f"{self.base_url}/api/user/coupons",
            headers=self._headers(user_id), params=params,
        )
        resp.raise_for_status()
        return [
            {
                "coupon_no": c["code"],
                "name": c["name"],
                "type": c["type"],           # "优惠券"/"权益券"
                "status": c["status"],       # "未使用"/"可使用"/"已使用"
                "valid_end": c["expire"],
                "face_value": c.get("value", 0),
            }
            for c in resp.json()["coupons"]
        ]

    def my_orders(self, user_id: str, limit: int = 10) -> list[dict]:
        """GET /api/user/orders?limit=N"""
        resp = self.client.get(
            f"{self.base_url}/api/user/orders",
            headers=self._headers(user_id),
            params={"limit": limit},
        )
        resp.raise_for_status()
        # 返回格式需匹配 toc_formatters.format_my_orders 期望的 dict 结构
        return resp.json()["orders"]

    # ─── Menu ──────────────────────────────────────────

    def nearby_stores(self, city: str | None = None,
                      keyword: str | None = None) -> list[dict]:
        """GET /api/stores?city=XX&keyword=XX"""
        params = {}
        if city:
            params["city"] = city
        if keyword:
            params["keyword"] = keyword
        resp = self.client.get(f"{self.base_url}/api/stores", params=params)
        resp.raise_for_status()
        return resp.json()["stores"]

    def store_detail(self, store_id: str) -> dict | None:
        """GET /api/stores/{store_id}"""
        resp = self.client.get(f"{self.base_url}/api/stores/{store_id}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def browse_menu(self, store_id: str) -> dict:
        """GET /api/stores/{store_id}/menu"""
        resp = self.client.get(f"{self.base_url}/api/stores/{store_id}/menu")
        resp.raise_for_status()
        data = resp.json()
        return {
            "store_name": data["store_name"],
            "categories": data["categories"],
            "items": data["items"],
        }

    def drink_detail(self, product_code: str) -> dict | None:
        """GET /api/products/{product_code}"""
        resp = self.client.get(
            f"{self.base_url}/api/products/{product_code}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def nutrition_info(self, product_code: str) -> dict | None:
        """GET /api/products/{product_code}/nutrition"""
        resp = self.client.get(
            f"{self.base_url}/api/products/{product_code}/nutrition")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    # ─── Stars Mall ────────────────────────────────────

    def stars_mall_products(self, category: str | None = None) -> list[dict]:
        """GET /api/stars-mall/products"""
        params = {"category": category} if category else {}
        resp = self.client.get(
            f"{self.base_url}/api/stars-mall/products", params=params)
        resp.raise_for_status()
        return resp.json()["products"]

    def stars_product_detail(self, product_code: str) -> dict | None:
        """GET /api/stars-mall/products/{product_code}"""
        resp = self.client.get(
            f"{self.base_url}/api/stars-mall/products/{product_code}")
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()

    def stars_redeem(self, product_code: str, user_id: str,
                     idempotency_key: str) -> dict:
        """POST /api/stars-mall/redeem"""
        resp = self.client.post(
            f"{self.base_url}/api/stars-mall/redeem",
            headers={
                **self._headers(user_id),
                "Idempotency-Key": idempotency_key,
            },
            json={"product_code": product_code},
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "success": data["success"],
            "redeem_id": data.get("redeem_id", random_id("rdm")),
            "product_name": data.get("product_name", ""),
            "stars_cost": data.get("stars_cost", 0),
            "stars_remaining": data.get("remaining", 0),
            "message": data.get("message", ""),
        }

    # ─── Order Flow ────────────────────────────────────

    def delivery_addresses(self, user_id: str) -> list[dict]:
        """GET /api/user/addresses"""
        resp = self.client.get(
            f"{self.base_url}/api/user/addresses",
            headers=self._headers(user_id),
        )
        resp.raise_for_status()
        return resp.json()["addresses"]

    def create_address(self, user_id: str, city: str, address: str,
                       address_detail: str, contact_name: str,
                       phone: str) -> dict:
        """POST /api/user/addresses"""
        resp = self.client.post(
            f"{self.base_url}/api/user/addresses",
            headers=self._headers(user_id),
            json={
                "city": city,
                "address": address,
                "address_detail": address_detail,
                "contact_name": contact_name,
                "phone": phone,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def store_coupons(self, store_id: str, user_id: str) -> list[dict]:
        """GET /api/stores/{store_id}/coupons"""
        resp = self.client.get(
            f"{self.base_url}/api/stores/{store_id}/coupons",
            headers=self._headers(user_id),
        )
        resp.raise_for_status()
        return resp.json()["coupons"]

    def calculate_price(self, store_id: str, items: list[dict],
                        coupon_code: str | None = None) -> dict:
        """POST /api/orders/calculate

        注意：confirmation_token 由平台生成，不需要后端参与。
        """
        from coffee_mcp.utils import generate_confirmation_token

        resp = self.client.post(
            f"{self.base_url}/api/orders/calculate",
            json={
                "store_id": store_id,
                "items": items,
                "coupon_code": coupon_code,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        # 平台自动注入 confirmation_token
        data["confirmation_token"] = generate_confirmation_token()
        return data

    def create_order(self, store_id: str, items: list[dict],
                     pickup_type: str, user_id: str,
                     idempotency_key: str,
                     coupon_code: str | None = None,
                     address_id: str | None = None) -> dict:
        """POST /api/orders"""
        resp = self.client.post(
            f"{self.base_url}/api/orders",
            headers={
                **self._headers(user_id),
                "Idempotency-Key": idempotency_key,
            },
            json={
                "store_id": store_id,
                "items": items,
                "pickup_type": pickup_type,
                "coupon_code": coupon_code,
                "address_id": address_id,
            },
        )
        resp.raise_for_status()
        return resp.json()

    def order_status(self, order_id: str, user_id: str) -> dict | None:
        """GET /api/orders/{order_id}"""
        resp = self.client.get(
            f"{self.base_url}/api/orders/{order_id}",
            headers=self._headers(user_id),
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json()
```

**关键点：**
- `confirmation_token` 由平台的 `utils.generate_confirmation_token()` 生成，**不需要你的后端参与**
- `idempotency_key` 由 MCP 客户端（AI 助手）生成，你的后端负责去重（或通过 `Idempotency-Key` header 传递）
- 每个方法的返回值格式必须匹配上面的 dict 结构，否则格式化器会出错

---

## Step 3: 启用适配器

在 `brand.yaml` 中取消注释 adapter 配置：

```yaml
adapter:
  module: "brands.my_brand.adapter"
  class: "MyBrandAdapter"
```

---

## Step 4: 测试

### 4.1 启动服务

```bash
# stdio 模式（本地测试）
BRAND=my_brand uv run coffee-company-toc

# HTTP 模式（远程接入）
BRAND=my_brand uv run coffee-company-toc-http
```

### 4.2 MCP 客户端配置

**Claude Desktop / Cursor (stdio):**

```json
{
  "mcpServers": {
    "my-brand-toc": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/coffee-company-mcp", "coffee-company-toc"],
      "env": { "BRAND": "my_brand" }
    }
  }
}
```

**OpenClaw (Streamable HTTP):**

```python
from openclaw_sdk import McpServer

my_brand = McpServer.http(
    url="https://mcp.mybrand.com/mcp",
    headers={"Authorization": f"Bearer {user_token}"}
)
agent.add_mcp_server(my_brand)
```

### 4.3 验证清单

| 测试项 | 命令 | 期望结果 |
|--------|------|---------|
| 配置加载 | `BRAND=my_brand python -c "from coffee_mcp.brand_config import load_brand_config; print(load_brand_config('my_brand').brand_name)"` | 你的品牌名 |
| 工具注册 | 在 MCP 客户端执行 `list_tools` | 21 个工具 |
| 门店搜索 | 调用 `nearby_stores` | 返回你的门店列表 |
| 菜单浏览 | 调用 `browse_menu` | 返回你的菜单 |
| 下单流程 | `calculate_price` → `create_order` | 确认令牌 + 订单创建 |
| 功能开关 | `stars_mall: false` 时调用 `stars_mall_products` | 返回"该品牌暂未开通此功能" |

---

## 返回值格式速查

每个适配器方法必须返回特定的 dict 结构。以下是最关键的几个：

### `browse_menu()` 返回格式

```python
{
    "store_name": "我的茶饮 南京西路店",
    "categories": [
        {"code": "milk_tea", "name": "奶茶系列", "sort": 1},
        {"code": "fruit_tea", "name": "果茶系列", "sort": 2},
    ],
    "items": [
        {
            "product_code": "MT001",
            "name": "珍珠奶茶",
            "category": "milk_tea",
            "base_price": 18,
            "description": "经典珍珠奶茶",
            "customizable": True,
            "available_sizes": ["regular", "large"],
            "available_temps": ["hot", "iced"],
            "available_milks": ["whole", "oat"],
            "calories_tall": 350,
            "stars_earn": 2,
            "is_new": False,
            "image": "pearl_milk_tea.jpg",
        },
    ],
}
```

### `calculate_price()` 返回格式

```python
{
    "items": [
        {"name": "珍珠奶茶", "size": "大杯", "unit_price": 21,
         "quantity": 1, "line_total": 21},
    ],
    "original_price": 21,
    "discount": 3.0,
    "coupon_name": "新人立减3元",
    "delivery_fee": 5.0,
    "packing_fee": 1.0,
    "final_price": 24.0,
    "confirmation_token": "cfm_xxx",  # 由平台自动生成
}
```

### `create_order()` 返回格式

```python
{
    "order_id": "ord_a7f3b2e9",      # 建议用 random_id("ord")
    "store_name": "我的茶饮 南京西路店",
    "pickup_type": "自提",
    "items": [...],                    # 同 calculate_price 的 items
    "final_price": 24.0,
    "discount": 3.0,
    "status": "待支付",
    "stars_will_earn": 2,
    "pay_url": "https://pay.mybrand.com/order/ord_a7f3b2e9",
    "message": "请在15分钟内完成支付",
}
```

---

## 安全机制（平台自动处理）

你的适配器**不需要**实现以下安全逻辑，平台会自动处理：

| 机制 | 说明 | 你需要做的 |
|------|------|-----------|
| **L0-L3 限流** | 按工具风险级别自动限流 | 无，YAML 配置即可 |
| **确认令牌** | `calculate_price` 自动生成，`create_order` 自动校验 | 在 `calculate_price` 中调用 `generate_confirmation_token()` |
| **幂等性** | `idempotency_key` 自动去重（内存存储） | 可选：后端也做去重（通过 Idempotency-Key header） |
| **参数校验** | 杯型/奶/加料白名单校验 | 无，YAML 配置 valid_sizes 等 |
| **PII 脱敏** | 地址列表手机号自动脱敏 | 无，格式化器自动处理 |
| **ID 随机化** | 订单/地址 ID 防枚举 | 建议后端也使用随机 ID |
| **Feature flag** | 未开通功能自动返回提示 | 在 YAML 中设置 features |

---

## 常见问题

### Q: 我的后端 API 格式和期望的 dict 结构不一样怎么办？

在适配器的每个方法中做字段映射。这就是适配器的价值——你的后端 API 格式不需要改变。

### Q: 我不需要所有 21 个功能怎么办？

通过 `features` 开关关闭不需要的功能（如 `stars_mall: false`）。对应的工具仍然注册但会返回"暂未开通"。

### Q: 我的品牌有特殊的定制选项（比如"加冰量"）怎么办？

目前支持的定制维度是 size/milk/temp/sweetness/extras。额外维度可以放在 `extras` 中扩展，或联系我们添加新维度。

### Q: 生产环境怎么获取用户身份？

生产环境中，用户身份由网关（Kong/CloudFlare）从 OAuth token 解析并注入 `X-User-Id` header。MCP 平台读取 header 作为 `user_id`，不再使用 `default_user_id`。

### Q: 支付怎么处理？

`create_order` 返回 `pay_url`，用户在 MCP 之外完成支付（微信支付/支付宝）。支付完成后用户说"支付完成"，AI 助手调用 `order_status` 查询最新状态。

---

## 接入时间线

| 阶段 | 时间 | 产出 |
|------|------|------|
| **配置 YAML** | 0.5 天 | brand.yaml + DemoAdapter 验证 |
| **实现适配器** | 1-2 周 | 21 个方法对接后端 API |
| **联调测试** | 2-3 天 | 全流程点单验证 |
| **上线** | 1 天 | 部署 + MCP 客户端配置 |
| **总计** | **2-3 周** | 品牌接入完成 |
