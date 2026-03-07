# Starbucks China MCP Server

AI Agent 通过 MCP 协议查询星巴克门店、浏览菜单、检查库存、获取促销活动。

> **MCP (Model Context Protocol)** 是 AI Agent 与外部服务交互的开放协议。本项目让 Claude Code、Cursor、Claude Desktop 等 AI 工具可以直接"对话"星巴克服务。

## Quick Start

```bash
# 安装依赖 (需要 uv + Python 3.13)
uv sync

# 运行完整 Demo（6 步流程演示）
uv run sbux demo

# 交互式模式
uv run sbux interactive
```

## 可用 Tools

| Tool | 功能 | 示例场景 |
|------|------|----------|
| `search_nearby_stores` | 搜索附近门店 | "帮我找上海陆家嘴附近的星巴克" |
| `get_store_detail` | 门店详情 | "这家店几点关门，有没有座位" |
| `get_menu` | 浏览菜单 | "最近有什么新品" |
| `get_product_detail` | 产品详情 | "馥芮白能加燕麦奶吗" |
| `check_store_inventory` | 库存查询 | "这杯今天有没有货" |
| `get_promotions` | 促销活动 | "现在有什么买一送一" |

## CLI 命令

```bash
uv run sbux stores 上海              # 搜索上海门店
uv run sbux stores 北京 三里屯       # 按关键词搜索
uv run sbux store SH-LJZ-001        # 门店详情
uv run sbux menu                     # 全部菜单
uv run sbux menu seasonal            # 当季限定
uv run sbux product 馥芮白           # 产品详情
uv run sbux inventory SH-LJZ-001    # 库存查询
uv run sbux promos                   # 促销活动
```

## 接入 AI 工具

### Claude Code / Cursor

在配置文件中添加：

```json
{
  "mcpServers": {
    "starbucks": {
      "command": "uv",
      "args": ["--directory", "/path/to/starbucks-mcp", "run", "starbucks-mcp"]
    }
  }
}
```

然后直接对话：

```
> 帮我查一下上海来福士附近的星巴克，今天有没有燕麦拿铁

Claude 自动调用:
  search_nearby_stores → get_product_detail → check_store_inventory
```

## 架构

```
AI Agent (Claude Code / Cursor / Claude Desktop)
         │  MCP Protocol
         ▼
   MCP Adapter Layer
   ├── Tool Registry        — 6 个只读 Tool
   ├── 语义化转换层          — JSON → 自然语言
   └── Auth Passthrough     — API Key / HMAC 签名透传
         │
         ▼
   openapi.starbucks.com.cn (现有开放平台)
```

## Demo API Keys

演示模式下可用的 Key：`demo-key-001`、`sbux-test-2026`、`starbucks-dev`

## License

MIT
