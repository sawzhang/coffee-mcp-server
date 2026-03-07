# CLAUDE.md - Starbucks MCP Server

## Project Overview

Starbucks China MCP (Model Context Protocol) Server — enables AI Agents (Claude Code, Cursor, Claude Desktop, etc.) to query Starbucks store info, browse menus, check inventory, and get promotions.

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
├── .env.example
├── src/starbucks_mcp/
│   ├── server.py        # MCP Server entry — 6 tools + 3 resources
│   ├── mock_data.py     # Mock data layer (8 stores, 10 products, 3 promos)
│   ├── formatters.py    # Semantic formatters (JSON → natural language)
│   └── cli.py           # CLI client (interactive + demo + single commands)
└── docs/                # GitHub Pages site
```

## Key Commands

```bash
uv sync                      # Install dependencies
uv run sbux demo             # Run full demo flow
uv run sbux interactive      # Interactive REPL
uv run sbux stores 上海      # Search stores in Shanghai
uv run sbux menu seasonal    # Browse seasonal menu
uv run starbucks-mcp         # Run MCP server (stdio)
```

## Architecture

Three-layer design:
1. **MCP Client Layer**: Claude Code / Cursor / Claude Desktop
2. **MCP Adapter Layer** (this project): Tool Registry + Semantic Formatter + Auth
3. **Backend**: Mock data (demo) or real `openapi.starbucks.com.cn` (production)

## Authentication

- Demo: use `demo-key-001`, `sbux-test-2026`, or `starbucks-dev`
- Production: HMAC-SHA256 signing with appKey/appSecret (per Starbucks OpenAPI spec)

## 6 Phase-1 Tools (read-only)

| Tool | Description |
|------|-------------|
| `search_nearby_stores` | Search stores by city/keyword/coordinates |
| `get_store_detail` | Store details (address, hours, services) |
| `get_menu` | Browse menu by category |
| `get_product_detail` | Product details (sizes, prices, customizations) |
| `check_store_inventory` | Check store product availability |
| `get_promotions` | Current promotions |

## Code Conventions

- Chinese user-facing strings, English code/comments
- All tool functions return formatted natural language strings
- Mock data is deterministic (seeded random for inventory)
- Type hints everywhere (Python 3.13 union syntax `X | None`)
