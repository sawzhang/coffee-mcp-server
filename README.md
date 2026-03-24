# Coffee MCP

Multi-brand MCP platform for coffee & tea ordering — let any AI assistant discover, order from, and interact with your beverage brand.

> **B2B Server** (10 tools) — Enterprise partner integrations via Kong HMAC auth
> **ToC Server** (21 tools) — Consumer-facing, multi-brand, L0-L3 security, YAML-driven
> **122 tests** passing (33 B2B + 89 ToC)

## What Is This?

When a user says _"help me order a latte"_ to any AI assistant (ChatGPT, Claude, OpenClaw, Doubao), only brands connected via MCP can be discovered and ordered from.

This platform lets coffee & tea brands plug into the AI ecosystem **in 2-3 weeks** — without building anything from scratch.

```
User → AI Assistant → MCP Protocol → Your Brand's MCP Server → Your Backend API
                                          ↑
                                    This platform
```

## Quick Start

```bash
# Install (requires uv + Python 3.13)
uv sync

# Run ToC server (consumer ordering, default brand)
uv run coffee-company-toc

# Run with a different brand
BRAND=tea_house uv run coffee-company-toc

# Run B2B server (enterprise partners)
uv run coffee-company-mcp

# Run tests
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

## ToC Tools (Consumer Journey)

| Group | Tools | Risk |
|-------|-------|------|
| **Utility** | `now_time_info` | L0 |
| **Discovery** | `campaign_calendar` · `available_coupons` · `claim_all_coupons` | L1-L2 |
| **Account** | `my_account` · `my_coupons` · `my_orders` | L1 |
| **Menu** | `nearby_stores` · `store_detail` · `browse_menu` · `drink_detail` · `nutrition_info` | L0 |
| **Points** | `stars_mall_products` · `stars_product_detail` · `stars_redeem` | L1-L3 |
| **Order** | `delivery_addresses` · `create_address` · `store_coupons` · `calculate_price` · `create_order` · `order_status` | L1-L3 |

### Security Model

- **L0** (60/min): Public data — menus, stores, nutrition
- **L1** (30/min): User data — account, coupons, orders
- **L2** (5/hour): Write ops — claim coupons, add address
- **L3** (10/day): Transactions — create order, redeem points
  - Requires `confirmation_token` from `calculate_price`
  - Requires `idempotency_key` to prevent duplicate operations

## Brand Onboarding

### Three ways to get started:

**1. CLI Init (5 min)** — Choose a category preset, answer a few questions:

```bash
uv run brand-init
# → Select: coffee / tea / juice / bakery
# → Generates brands/<your_brand>/brand.yaml
```

**2. AI-Assisted API Mapping (30 min)** — Give your API docs to Claude:

```
/brand-onboard https://api.yourbrand.com/docs
# → Generates adapter.py + brand.yaml + integration tests
```

**3. Manual (1-2 weeks)** — Implement `BrandAdapter` with 21 methods:

```python
class MyBrandAdapter(BrandAdapter):
    def nearby_stores(self, city=None, keyword=None):
        resp = httpx.get(f"{self.api}/stores", params={"city": city})
        return resp.json()["stores"]
    # ... 20 more methods
```

See [Brand Integration Guide](docs/BRAND_INTEGRATION_GUIDE.md) for complete instructions.

### Category Presets

| Preset | Sizes | Extras | Sweetness |
|--------|-------|--------|-----------|
| **Coffee** | tall / grande / venti | espresso shots, syrups | 4 levels |
| **Tea** | regular / large | boba, pudding, taro | 5 levels (七分糖 etc.) |
| **Juice** | regular / large | chia seeds, nata | 3 levels |
| **Bakery** | single / combo | gift box | — |

## B2B Tools (Enterprise Partners)

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

**OpenClaw (Streamable HTTP):**
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
└── tea_house/brand.yaml         #   Example: 茶语轩

src/coffee_mcp/
├── toc_server.py                # ToC server factory (21 tools)
├── brand_config.py              # YAML config loader
├── brand_adapter.py             # BrandAdapter ABC (21 methods)
├── demo_adapter.py              # Mock data adapter
├── brand_init.py                # CLI brand initializer
├── presets/catalog.py           # Category presets (coffee/tea/juice/bakery)
├── utils.py                     # Shared utilities
├── toc_mock_data.py             # ToC mock data
├── toc_formatters.py            # ToC markdown formatters
├── server.py                    # B2B server (10 tools)
├── mock_data.py                 # B2B mock data
├── formatters.py                # B2B formatters
└── cli.py                       # CLI + REPL

docs/
├── BRAND_INTEGRATION_GUIDE.md   # Step-by-step brand onboarding
├── TOC_MCP_PLATFORM_DESIGN.md   # Platform design & competitive analysis
├── TOC_SECURITY.md              # Security architecture (L0-L3)
└── MCP_API_DESIGN_GUIDE.md      # MCP tool design principles
```

## Docs

- [Brand Integration Guide](docs/BRAND_INTEGRATION_GUIDE.md) — How to connect your brand
- [Platform Design](docs/TOC_MCP_PLATFORM_DESIGN.md) — Architecture, security, competitive analysis
- [Security Model](docs/TOC_SECURITY.md) — L0-L3 threat model
- [API Design Guide](docs/MCP_API_DESIGN_GUIDE.md) — MCP tool design principles

## License

MIT
