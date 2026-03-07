# CLAUDE.md - Starbucks MCP Server

## Project Overview

Starbucks China B2B MCP Server — maps AI Agent requests (via MCP protocol) to existing HTTP Open Platform APIs at `openapi.starbucks.com.cn`. Deployed behind Kong gateway which handles all auth/rate-limiting/ACL.

## Tech Stack

- **Language**: Python 3.13
- **Package Manager**: uv
- **MCP SDK**: `mcp[cli]` (FastMCP)
- **HTTP Client**: httpx
- **CLI**: click + rich

## Project Structure

```
starbucks-mcp/
├── pyproject.toml
├── src/starbucks_mcp/
│   ├── server.py        # MCP Server — 10 Phase-1 tools + 2 resources
│   ├── mock_data.py     # Mock data simulating real API responses
│   ├── formatters.py    # Semantic formatters (JSON → natural language)
│   └── cli.py           # CLI client (interactive + demo + single commands)
└── docs/
    ├── index.html        # GitHub Pages site
    ├── ARCHITECTURE.md   # Full API mapping & phased rollout
    └── DEPLOY_DECISION.md # Kong-based deployment analysis
```

## Key Commands

```bash
uv sync                            # Install dependencies
uv run sbux demo                   # Run 9-step demo flow
uv run sbux interactive            # Interactive REPL
uv run sbux member SBUX_M_100001   # Query member
uv run starbucks-mcp               # Run MCP server (stdio)
```

## Architecture

MCP Adapter sits behind Kong as a new upstream:
- **Kong**: HMAC auth, IP whitelist, rate limiting, ACL (existing infra, 2 new routes)
- **MCP Adapter** (this project): protocol conversion + semantic formatting only
- **Backend**: existing openapi-platform services (zero changes)

## 10 Phase-1 Tools (all read-only)

All map 1:1 to real HTTP APIs:
- `member_query` → POST /crmadapter/account/query
- `member_tier` → POST /crmadapter/account/memberTier
- `member_benefits` → POST /crmadapter/customers/getBenefits
- `member_benefit_list` → POST /crmadapter/asset/coupon/getBenefitList
- `coupon_query` → POST /coupon/query
- `coupon_detail` → POST /coupon/detail
- `equity_query` → POST /equity/query
- `equity_detail` → POST /equity/detail
- `assets_list` → POST /assets/list
- `cashier_pay_query` → POST /cashier/payQuery

## Code Conventions

- Tools have NO auth parameters (Kong handles auth before traffic reaches adapter)
- Chinese user-facing strings, English code/comments
- All tool functions return formatted natural language strings
- Mock data mirrors real API response schemas
- Type hints everywhere (Python 3.13 union syntax)
