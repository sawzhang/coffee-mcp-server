# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

Multi-brand MCP platform for coffee & tea ordering, providing **B2B** and **ToC** servers:

- **B2B Server** (`server.py`, 10 tools) — 面向合作伙伴，通过 Kong 鉴权，客服/运营视角
- **ToC Server** (`toc_server.py`, 21 tools) — 面向消费者，多品牌配置化，自助点单/领券/积分兑换

**Multi-brand support:** Add a new brand by creating `brands/<brand_id>/brand.yaml` — zero code changes needed.
Default brand: `coffee_company` (demo mode with mock data).

## Commands

```bash
uv sync                                    # install deps
uv run coffee-company-mcp                  # B2B MCP server (stdio)
uv run coffee-company-toc                  # ToC MCP server (stdio, default brand)
BRAND=tea_house uv run coffee-company-toc  # ToC server for another brand
uv run coffee-company-toc-http             # ToC MCP server (Streamable HTTP)
uv run coffee demo                         # 9-step B2B demo
uv run coffee interactive                  # B2B REPL mode
uv run coffee member CC_M_100001           # single B2B tool call
```

Run the full test suites:
```bash
uv run python tests/test_mcp_real.py       # B2B: 33 cases
uv run python tests/test_toc_mcp.py        # ToC: 89 cases
```

## Architecture

```
B2B Server (server.py)           ToC Server (toc_server.py)
10 @mcp.tool() + 2 resources     21 @mcp.tool() — multi-brand
    │                                 │
    ├── mock_data.py                  ├── brand_config.py (YAML loader)
    └── formatters.py                 ├── brand_adapter.py (ABC interface)
                                      ├── demo_adapter.py (mock data adapter)
                                      ├── toc_mock_data.py (mock data store)
                                      ├── toc_formatters.py (markdown output)
                                      └── utils.py (shared utilities)
```

**B2B data flow:** MCP request → `server.py` → `mock_data.query_fn()` → `formatters.format_fn()` → markdown
**ToC data flow:** MCP request → `toc_server.py` → `BrandAdapter.method()` → `toc_formatters.format_fn()` → markdown

**Multi-brand flow:**
1. `brand_config.py` loads `brands/<brand_id>/brand.yaml`
2. `create_toc_server(config, adapter)` builds a configured FastMCP server
3. Validation rules, rate limits, menu options all come from YAML
4. `DemoAdapter` wraps `toc_mock_data.py` for demo mode; production brands implement `BrandAdapter`

**Key difference:** B2B tools require explicit `member_id`; ToC tools auto-resolve user from token (no ID params).

**B2B production:** Agent → Kong (HMAC auth) → B2B adapter → backend
**ToC production:** Consumer app → OAuth → ToC adapter → consumer backend

## Tool ↔ HTTP API Mapping

| Tool | HTTP Endpoint |
|------|--------------|
| `member_query` | POST /crmadapter/account/query |
| `member_tier` | POST /crmadapter/account/memberTier |
| `member_benefits` | POST /crmadapter/customers/getBenefits |
| `member_benefit_list` | POST /crmadapter/asset/coupon/getBenefitList |
| `coupon_query` | POST /coupon/query |
| `coupon_detail` | POST /coupon/detail |
| `equity_query` | POST /equity/query |
| `equity_detail` | POST /equity/detail |
| `assets_list` | POST /assets/list |
| `cashier_pay_query` | POST /cashier/payQuery |

## Demo Test Data IDs

Members: `CC_M_100001` (Gold/NIO), `CC_M_100002` (Green/Fliggy), `CC_M_100003` (Diamond/Qwen)
Coupons: `CC20260301A001`, `CC20260301A002`, `CC20260215B001`
Orders: `ORD_2026030100001`, `ORD_2026021500001`
Equity: `EQ_2026030100001`, `EQ_2026030100002`, `EQ_2026021500001`
Pay tokens: `PAY_TOKEN_001` (success), `PAY_TOKEN_002` (pending), `PAY_TOKEN_003` (failed)

## Claude Code Skills + Commands (体验层)

MCP Server 提供能力，Skills + Commands 提供体验。

### MCP Client 集成（`.mcp.json`）

```json
{
  "mcpServers": {
    "coffee-mcp": { "command": "uv", "args": ["run", ".", "coffee-company-mcp"] },
    "coffee-toc": { "command": "uv", "args": ["run", ".", "coffee-company-toc"] }
  }
}
```

### B2B Slash Commands + Skills

| Command / Skill | Description |
|---------|-------------|
| `/coffee` / `coffee` | B2B 通用助手，路由 10 个工具 |
| `/coffee-member` / `coffee-member` | 会员查询 |
| `/coffee-coupons` / `coffee-coupons` | 券码查询 |
| `/coffee-assets` / `coffee-assets` | 客户资产 |
| `/coffee-payment` / `coffee-payment` | 支付查询 |

### ToC Slash Commands + Skills

| Command / Skill | Description |
|---------|-------------|
| `/coffee-toc` / `coffee-toc` | ToC 通用助手，路由 18 个工具 |
| `/coffee-discover` / `coffee-discover` | 活动发现 + 领券 |
| `/coffee-order` / `coffee-order` | 点单流程 (选店→菜单→定制→下单) |
| `/coffee-menu` / `coffee-menu` | 菜单浏览 + 营养查询 |
| `/coffee-stars` / `coffee-stars` | 积分商城 + 兑换 |

### 工程工具

| Command / Skill | Description |
|---------|-------------|
| `/mcp-review` / `mcp-review` | MCP Tool 设计审查（10 条准则 checklist） |
| `/brand-onboard` / `brand-onboard` | 品牌自动接入（API 文档 → adapter.py + brand.yaml + 测试） |

### ToC 消费者旅程 (21 tools)

```
时间感知: now_time_info (LLM 获取当前时间)
发现优惠: campaign_calendar → available_coupons → claim_all_coupons
我的账户: my_account / my_coupons / my_orders
门店菜单: nearby_stores → browse_menu(compact?) → drink_detail → nutrition_info(compact?)
积分兑换: stars_mall_products → stars_product_detail → stars_redeem(idempotency_key)
下单闭环: store_coupons → calculate_price(→confirmation_token) → create_order(idempotency_key, confirmation_token) → order_status
配送地址: delivery_addresses / create_address
```

### 安全增强特性

- **确认令牌**: calculate_price 返回 confirmation_token，create_order 必须传入，防止跳过确认
- **幂等键**: L3 操作(create_order, stars_redeem)需要 idempotency_key，防止 LLM 重试导致重复操作
- **ID 随机化**: 订单/地址 ID 使用 UUID 前缀格式(ord_xxx, addr_xxx)，防止枚举攻击
- **PII 脱敏**: 地址列表中手机号自动脱敏(138****1234)
- **紧凑模式**: browse_menu 和 nutrition_info 支持 compact=True 减少 token 消耗

## Project Structure

```
.mcp.json                          # MCP client config (B2B + ToC servers)
.claude/
├── commands/                      # Slash commands
│   ├── coffee.md                  #   B2B general
│   ├── coffee-member.md           #   B2B member
│   ├── coffee-coupons.md          #   B2B coupons
│   ├── coffee-assets.md           #   B2B assets
│   ├── coffee-payment.md          #   B2B payment
│   ├── coffee-toc.md              #   ToC general
│   ├── coffee-discover.md         #   ToC discovery
│   ├── coffee-order.md            #   ToC order
│   ├── coffee-stars.md            #   ToC stars mall
│   └── mcp-review.md             #   MCP tool design review
└── skills/                        # Natural language auto-trigger
    ├── coffee/                    #   B2B skills...
    ├── coffee-toc/                #   ToC general
    ├── coffee-discover/           #   ToC discovery
    ├── coffee-order/              #   ToC order flow
    ├── coffee-menu/               #   ToC menu browse
    ├── coffee-stars/              #   ToC stars mall
    └── mcp-review/               #   MCP tool design review
brands/                                # Brand configs (YAML-driven, zero code)
├── coffee_company/
│   └── brand.yaml                     #   Default demo brand
└── tea_house/
    └── brand.yaml                     #   Example second brand (茶语轩)
docs/
├── MCP_API_DESIGN_GUIDE.md            # MCP 接口设计准则（完整版）
└── TOC_MCP_PLATFORM_DESIGN.md         # ToC 平台商业化方案
src/coffee_mcp/
├── server.py                          # B2B MCP Server (10 tools)
├── toc_server.py                      # ToC MCP Server (21 tools, multi-brand factory)
├── brand_config.py                    # BrandConfig dataclass + YAML loader
├── brand_adapter.py                   # BrandAdapter ABC interface
├── demo_adapter.py                    # DemoAdapter (mock data adapter)
├── utils.py                           # Shared utilities (mask_phone, random_id)
├── mock_data.py                       # B2B mock data
├── toc_mock_data.py                   # ToC mock data store
├── formatters.py                      # B2B formatters
├── toc_formatters.py                  # ToC formatters
├── cli.py                             # Click CLI + REPL
└── __init__.py
```

## Code Conventions

- Chinese user-facing strings in tool responses; English in code/comments
- Python 3.13 union syntax (`str | None`, not `Optional[str]`)
- Every tool returns a formatted markdown string, never raw JSON
- `mock_data.py` functions mirror the real API response shapes — when replacing with real HTTP calls, keep the same return types
- New brands: create `brands/<brand_id>/brand.yaml` with menu/validation/rate limits; no Python code needed
- Production brands: implement `BrandAdapter` ABC in `brands/<brand_id>/adapter.py` for real HTTP calls
