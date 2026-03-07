# Starbucks China MCP Server

星巴克中国 B2B 开放平台 MCP Server —— 让 AI Agent 通过 MCP 协议调用星巴克现有 HTTP 开放平台能力。

> 所有 MCP Tool **严格 1:1 映射** `openapi.starbucks.com.cn` 现有 HTTP 接口，不新增业务逻辑。
> 鉴权由 Kong 网关处理，MCP 层只做协议转换 + 语义化格式化。

## Quick Start

```bash
# 安装依赖 (需要 uv + Python 3.13)
uv sync

# 运行完整 Demo（9 步流程演示）
uv run sbux demo

# 交互式模式
uv run sbux interactive
```

## Architecture

```
B2B Agent (蔚来/千问/飞猪)
    │  MCP Protocol (SSE / Streamable HTTP)
    ▼
┌──────────── Kong ────────────┐
│  HMAC Auth ✓  ACL ✓  限流 ✓  │  ← 复用现有 B2B 客户凭证
│                              │
│  /sse, /mcp → MCP Adapter   │  ← 新增 2 条路由
│  /coupon/*  → 现有后端       │  ← 不动
└──────────────┬───────────────┘
               ▼
         MCP Adapter (本项目)
         ├── MCP 协议处理
         ├── Tool 权限过滤
         ├── 参数映射
         └── 语义化转换
               │  内网直连
               ▼
         openapi-platform 后端 (不动)
```

## Phase 1 Tools（10 个只读，当前可用）

| MCP Tool | HTTP API | 功能 |
|----------|----------|------|
| `member_query` | `POST /crmadapter/account/query` | 查询会员信息 |
| `member_tier` | `POST /crmadapter/account/memberTier` | 会员等级详情 |
| `member_benefits` | `POST /crmadapter/customers/getBenefits` | 8 项权益状态 |
| `member_benefit_list` | `POST /crmadapter/asset/coupon/getBenefitList` | 券列表 |
| `coupon_query` | `POST /coupon/query` | 订单券码查询 |
| `coupon_detail` | `POST /coupon/detail` | 券码详情 |
| `equity_query` | `POST /equity/query` | 权益发放查询 |
| `equity_detail` | `POST /equity/detail` | 权益详情 |
| `assets_list` | `POST /assets/list` | 客户全部资产 |
| `cashier_pay_query` | `POST /cashier/payQuery` | 支付状态查询 |

## CLI 命令

```bash
uv run sbux member 138****1234          # 查会员（手机号）
uv run sbux member SBUX_M_100001       # 查会员（会员ID）
uv run sbux tier SBUX_M_100001         # 等级详情
uv run sbux benefits SBUX_M_100001     # 权益状态
uv run sbux assets SBUX_M_100001       # 全部资产
uv run sbux coupon SBX20260301A001     # 券码详情
uv run sbux equity EQ_2026030100001    # 权益详情
uv run sbux pay PAY_TOKEN_001          # 支付状态
```

## 接入 Claude Code / Cursor

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

## B2B 场景示例

**蔚来车机 Agent**：
```
车主: "帮我查一下我的星巴克会员等级和可用优惠券"

Agent 调用链:
  member_query(mobile="138****1234") → 确认金星会员
  member_tier(sbux_id="SBUX_M_100001") → 142 颗星，距钻星差 358 颗
  assets_list(sbux_id="SBUX_M_100001") → 3 张可用券
```

## Docs

- [Architecture](docs/ARCHITECTURE.md) — 完整 API 映射表 + 分期开放策略
- [Deploy Decision](docs/DEPLOY_DECISION.md) — Kong 架构下的部署方案分析

## License

MIT
