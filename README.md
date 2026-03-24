# Coffee MCP

**The MCP platform that connects beverage brands to every AI assistant.**

When a customer says _"help me order a latte"_ to ChatGPT, Claude, Doubao, or any AI assistant — only brands connected via MCP get discovered. This platform is how you get connected.

[![Tests](https://img.shields.io/badge/tests-122%20passing-brightgreen)]()
[![Python](https://img.shields.io/badge/python-3.13-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## The Problem

AI assistants are becoming the new storefront. Hundreds of millions of users already ask AI to help them shop, order food, and make decisions. But most brands have **zero presence** in this channel — no way to be discovered, recommended, or ordered from.

Traditional APIs don't solve this. AI assistants speak [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) — the open standard for connecting AI to external tools and data.

## The Solution

Coffee MCP is an **open-source, multi-brand MCP platform** that lets any coffee, tea, juice, or bakery brand plug into the AI ecosystem — with a YAML config and a brand adapter.

```
Customer → AI Assistant → MCP Protocol → Coffee MCP → Your Brand's Backend API
```

**What you get:**
- 21 consumer-facing tools (browse menu, find stores, order, pay, track)
- 10 B2B enterprise tools (member query, coupons, loyalty, payments)
- 4-tier security model (L0-L3) with rate limiting and transaction safety
- Multi-brand support — one platform, unlimited brands
- Category presets for coffee, tea, juice, and bakery
- Brand onboarding in as little as 5 minutes (CLI) or 30 minutes (AI-assisted)

**What it costs:** Nothing. MIT licensed. Self-host or extend as you wish.

## Who Is This For?

| Audience | Value |
|----------|-------|
| **Brand CTOs / Digital Leaders** | Ship AI ordering for your brand in 2-3 weeks, not 6 months |
| **AI/MCP Developers** | Production-grade reference for multi-tenant MCP server design |
| **Retail Tech Teams** | Battle-tested security model (L0-L3) for AI-to-commerce flows |
| **Founders** | Fork this to build your own vertical MCP platform |

## Quick Start

```bash
# Install (requires uv + Python 3.13)
uv sync

# Run consumer ordering server (default brand)
uv run coffee-company-toc

# Run with a different brand
BRAND=tea_house uv run coffee-company-toc

# Run B2B enterprise server
uv run coffee-company-mcp

# Run all tests (122 passing)
uv run python tests/test_toc_mcp.py     # 89 ToC tests
uv run python tests/test_mcp_real.py     # 33 B2B tests

# Initialize a new brand (interactive)
uv run brand-init
```

## Architecture

```
                    ┌──────────────────────────────┐
                    │   AI Assistants (MCP Clients) │
                    │   ChatGPT / Claude / Doubao   │
                    │   OpenClaw / Cursor / Custom   │
                    └──────────────┬───────────────┘
                                   │ MCP Protocol
                    ┌──────────────▼───────────────┐
                    │     Gateway (Kong/CloudFlare)  │
                    │   OAuth · Rate Limit · WAF     │
                    └──────────────┬───────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                                         │
     ┌────────▼─────────┐                  ┌────────────▼───────────┐
     │   B2B Server      │                  │    ToC Server (factory) │
     │   10 read tools   │                  │    21 tools · L0-L3    │
     │   Kong HMAC auth  │                  │    Multi-brand YAML    │
     └──────────────────┘                  └────────────┬───────────┘
                                                        │
                                           ┌────────────▼───────────┐
                                           │    BrandAdapter (ABC)   │
                                           │    21 abstract methods  │
                                           ├────────────────────────┤
                                           │  DemoAdapter (mock)     │
                                           │  YourBrandAdapter (HTTP)│
                                           └────────────────────────┘
```

## Brand Onboarding

Three paths, pick what fits your team:

**1. CLI Init (5 min)** — Zero-code, YAML-driven:

```bash
uv run brand-init
# → Select: coffee / tea / juice / bakery
# → Generates brands/<your_brand>/brand.yaml
# → Done. Run the server.
```

**2. AI-Assisted (30 min)** — Give your API docs to Claude:

```
/brand-onboard https://api.yourbrand.com/docs
# → Generates adapter.py + brand.yaml + integration tests
```

**3. Full Custom (1-2 weeks)** — Implement `BrandAdapter` with 21 methods:

```python
class MyBrandAdapter(BrandAdapter):
    def nearby_stores(self, city=None, keyword=None):
        resp = httpx.get(f"{self.api}/stores", params={"city": city})
        return resp.json()["stores"]
    # ... 20 more methods
```

See [Brand Integration Guide](docs/BRAND_INTEGRATION_GUIDE.md) for the complete walkthrough.

### Category Presets

| Preset | Sizes | Extras | Sweetness |
|--------|-------|--------|-----------|
| **Coffee** | tall / grande / venti | espresso shots, syrups | 4 levels |
| **Tea** | regular / large | boba, pudding, taro | 5 levels |
| **Juice** | regular / large | chia seeds, nata | 3 levels |
| **Bakery** | single / combo | gift box | — |

## Consumer Tools (ToC Server — 21 Tools)

The full ordering journey, from discovery to delivery:

| Group | Tools | Security |
|-------|-------|----------|
| **Utility** | `now_time_info` | L0 |
| **Discovery** | `campaign_calendar` · `available_coupons` · `claim_all_coupons` | L1-L2 |
| **Account** | `my_account` · `my_coupons` · `my_orders` | L1 |
| **Menu** | `nearby_stores` · `store_detail` · `browse_menu` · `drink_detail` · `nutrition_info` | L0 |
| **Points** | `stars_mall_products` · `stars_product_detail` · `stars_redeem` | L1-L3 |
| **Order** | `delivery_addresses` · `create_address` · `store_coupons` · `calculate_price` · `create_order` · `order_status` | L1-L3 |

### Security Model

Four tiers designed for AI-to-commerce, where the AI acts on behalf of the user:

- **L0** (60/min) — Public data: menus, stores, nutrition
- **L1** (30/min) — User data: account, coupons, orders
- **L2** (5/hour) — Write ops: claim coupons, add address
- **L3** (10/day) — Transactions: create order, redeem points
  - Requires `confirmation_token` from `calculate_price`
  - Requires `idempotency_key` to prevent duplicate operations

## Enterprise Tools (B2B Server — 10 Tools)

For partner integrations (delivery platforms, loyalty aggregators, payment providers):

| Tool | HTTP API | Description |
|------|----------|-------------|
| `member_query` | POST /crmadapter/account/query | Query member by mobile/openId/memberId |
| `member_tier` | POST /crmadapter/account/memberTier | Tier details + stars balance |
| `member_benefits` | POST /crmadapter/customers/getBenefits | 8 benefit statuses |
| `member_benefit_list` | POST /crmadapter/asset/coupon/getBenefitList | Coupon list |
| `coupon_query` | POST /coupon/query | Order coupon status |
| `coupon_detail` | POST /coupon/detail | Coupon details |
| `equity_query` | POST /equity/query | Equity distribution status |
| `equity_detail` | POST /equity/detail | Equity details |
| `assets_list` | POST /assets/list | All customer assets |
| `cashier_pay_query` | POST /cashier/payQuery | Payment status |

## Connect to AI Assistants

**Claude Desktop / Cursor (stdio):**
```json
{
  "mcpServers": {
    "coffee-toc": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/coffee-mcp", "coffee-company-toc"],
      "env": { "BRAND": "coffee_company" }
    }
  }
}
```

**OpenClaw / Agent SDK (Streamable HTTP):**
```python
coffee = McpServer.http(
    url="https://mcp.yourbrand.com/mcp",
    headers={"Authorization": f"Bearer {token}"}
)
agent.add_mcp_server(coffee)
```

## Project Structure

```
brands/                          # Brand configs (zero-code onboarding)
├── coffee_company/brand.yaml    #   Default demo brand
└── tea_house/brand.yaml         #   Example: tea chain

src/coffee_mcp/
├── toc_server.py                # ToC server factory (21 tools)
├── brand_config.py              # YAML config loader
├── brand_adapter.py             # BrandAdapter ABC (21 methods)
├── demo_adapter.py              # Mock data adapter
├── brand_init.py                # CLI brand initializer
├── presets/catalog.py           # Category presets
├── server.py                    # B2B server (10 tools)
└── cli.py                       # CLI + REPL

docs/
├── BRAND_INTEGRATION_GUIDE.md   # Step-by-step brand onboarding
├── TOC_MCP_PLATFORM_DESIGN.md   # Platform design & competitive analysis
├── TOC_SECURITY.md              # Security architecture (L0-L3)
└── MCP_API_DESIGN_GUIDE.md      # MCP tool design principles
```

## Docs

- [Brand Integration Guide](docs/BRAND_INTEGRATION_GUIDE.md) — Connect your brand step by step
- [Platform Design](docs/TOC_MCP_PLATFORM_DESIGN.md) — Architecture, competitive analysis, roadmap
- [Security Model](docs/TOC_SECURITY.md) — L0-L3 threat model for AI-commerce
- [API Design Guide](docs/MCP_API_DESIGN_GUIDE.md) — MCP tool design principles

## Roadmap

- [ ] Hosted multi-tenant mode (brands self-register, zero-deploy)
- [ ] Payment provider integrations (Alipay, WeChat Pay, Stripe)
- [ ] Analytics dashboard (AI ordering funnel, conversion tracking)
- [ ] More verticals beyond beverage (fast food, convenience stores)

## Contributing

PRs welcome. See the [Brand Integration Guide](docs/BRAND_INTEGRATION_GUIDE.md) if you want to add support for a new brand or category.

## License

MIT
