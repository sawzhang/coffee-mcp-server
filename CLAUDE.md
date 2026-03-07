# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Is

MCP adapter for Coffee Company's B2B HTTP Open Platform (`openapi.coffeecompany.com`). Every MCP Tool maps 1:1 to an existing HTTP API endpoint. In production, this service sits behind Kong which handles all auth (HMAC-SHA256/SM2), rate limiting, IP whitelisting, and ACL. The adapter only does MCP protocol handling + semantic formatting.

Currently in demo mode with mock data. No real backend calls yet.

## Commands

```bash
uv sync                              # install deps
uv run coffee demo                     # 9-step B2B demo (starts MCP server internally)
uv run coffee interactive              # REPL mode (type 'data' for test IDs, 'help' for commands)
uv run coffee member CC_M_100001     # single tool call
uv run coffee-company-mcp                 # run MCP server (stdio mode, for client integration)
```

Run the full MCP protocol test suite (33 cases: tools + resources + edge cases):
```bash
uv run python tests/test_mcp_real.py
```

## Architecture

```
server.py          10 @mcp.tool() functions + 2 @mcp.resource() functions
    │                  Each tool docstring notes the corresponding HTTP API path
    │                  Tools have NO auth params (Kong handles auth upstream)
    ├── mock_data.py   Query functions that return dicts (swap for real httpx calls in prod)
    └── formatters.py  dict → markdown string (semantic formatting for LLM consumption)

cli.py             Click CLI that spawns server.py as a subprocess via MCP stdio_client
```

**Data flow per tool call:** MCP request → `server.py` tool function → `mock_data.query_fn()` → dict → `formatters.format_fn()` → markdown string → MCP response

**Production deployment:** Agent → Kong (`/sse`, `/mcp` routes, HMAC auth plugin) → this adapter → backend via internal network

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

## Code Conventions

- Chinese user-facing strings in tool responses; English in code/comments
- Python 3.13 union syntax (`str | None`, not `Optional[str]`)
- Every tool returns a formatted markdown string, never raw JSON
- `mock_data.py` functions mirror the real API response shapes — when replacing with real HTTP calls, keep the same return types
