# 部署架构决策：Kong 网关下的 MCP 接入方案

## 0. 关键前提

现有开放平台架构：

```
B2B 客户 ──HTTPS + HMAC──▶ Kong ──▶ 后端服务
                            │
                     Kong 负责:
                     ├── HMAC / SM2 签名验证
                     ├── IP 白名单
                     ├── 限流 (per Consumer)
                     ├── ACL / 接口级授权
                     └── 日志审计
```

**这一条信息改变了整个决策。**

之前推荐"在现有平台内部加 MCP 模块"的核心理由是：
独立服务需要重写 HMAC 签名和鉴权逻辑。

但如果鉴权在 Kong 层，后端服务本身并不做签名验证——
那 MCP Adapter 也不需要做，**只要它也挂在 Kong 后面**。

---

## 1. 推翻之前结论，重新给三个方案

### 方案 A：MCP Adapter 作为 Kong 的新 Upstream（推荐）

```
                        ┌─ /coupon/*  ─▶ openapi-platform (现有, 不动)
B2B Agent ──▶ Kong ─────┤
                        └─ /mcp, /sse ─▶ MCP Adapter (新服务)
                                              │
                                              │ 内网直连
                                              ▼
                                        openapi-platform (后端)
```

### 方案 B：在现有后端服务内部加 MCP 模块

```
B2B Agent ──▶ Kong ── /mcp ──▶ openapi-platform (改造, 加 MCP 端点)
```

### 方案 C：Kong Plugin 直接做协议转换

```
B2B Agent ──▶ Kong (MCP Plugin) ──▶ openapi-platform (不动)
```

---

## 2. 为什么方案 A 现在变成了最优解

### 之前方案 A 的致命问题——全部被 Kong 解决了

| 之前的问题 | 有 Kong 之后 |
|---|---|
| Adapter 需要重写 HMAC 签名逻辑 | **Kong 做验签**，Adapter 收到的是已认证的请求 |
| B2B 客户的 Secret 暴露给 Adapter | **Secret 只在 Kong 中**，Adapter 永远不接触 |
| 客户独立的权限隔离丢失 | Kong Consumer + ACL 保持**每客户独立权限** |
| 客户独立的限流丢失 | Kong Rate Limiting 插件保持**每客户独立限流** |
| IP 白名单失效 | Kong IP Restriction 插件照常生效 |
| 审计日志断裂 | Kong 日志插件统一记录 HTTP + MCP 流量 |

**鉴权、权限、限流、审计——全部由 Kong 承担，MCP Adapter 完全不碰。**

### 方案 A 在 Kong 架构下的完整数据流

```
Step 1: B2B Agent 连接 MCP
────────────────────────────
Agent 发起 SSE 连接:
  GET https://mcp.starbucks.com.cn/sse
  Headers:
    X-Date: Mon, 07 Mar 2026 10:00:00 GMT
    Authorization: hmac username="nio_app_key", algorithm="hmac-sha256",
                   headers="x-date", signature="xxx"

Step 2: Kong 处理
────────────────────────────
  ✅ HMAC Auth 插件: 验证签名 → 识别 Consumer = "nio"
  ✅ IP Restriction: 检查来源 IP 在蔚来白名单内
  ✅ Rate Limiting: 检查蔚来的 QPS 配额
  ✅ ACL: 检查蔚来有权访问 /sse 路由
  ✅ 注入 Consumer 信息头:
       X-Consumer-Username: nio
       X-Consumer-Custom-ID: nio_partner_id
       X-Consumer-Groups: member-read, coupon-read, cashier-write
  → 转发到 MCP Adapter upstream

Step 3: MCP Adapter 收到已认证请求
────────────────────────────
  从 Kong 注入的头中获取:
    who:  X-Consumer-Username = "nio"
    can:  X-Consumer-Groups = ["member-read", "coupon-read", "cashier-write"]

  建立 SSE 长连接，注册 Tool 列表
  根据 Consumer Groups 决定暴露哪些 Tool（蔚来看不到短信发送 Tool）

Step 4: Agent 调用 Tool
────────────────────────────
  Agent → MCP Adapter: call member_query(mobile="138xxxx")

  Adapter 内部:
    POST http://openapi-platform.internal:8080/crmadapter/account/query
    Headers:
      X-Consumer-Username: nio           ← 传递调用者身份
      X-Internal-Request: true           ← 标记内网调用
      Content-Type: application/json
    Body: {"mobile": "138xxxx", "channel": "NIO"}

  → openapi-platform 后端处理，返回 JSON
  → Adapter 做语义化转换
  → 返回给 Agent: "该手机号已注册星巴克会员，金星级，142颗星。"
```

### Adapter 里面到底有什么

```
MCP Adapter 的职责（有 Kong 之后）：

  ① MCP 协议处理     SSE/Streamable HTTP 连接管理
                     Tool 注册、参数解析、结果封装

  ② 权限过滤         根据 Kong 传入的 Consumer Groups
                     动态决定暴露哪些 Tool

  ③ 参数映射         MCP Tool 参数 → HTTP API 请求体

  ④ 语义化转换       JSON 响应 → 自然语言

  ⑤ 没有的：
     × HMAC 签名          Kong 做了
     × 限流               Kong 做了
     × IP 白名单          Kong 做了
     × 接口授权判断        Kong 做了
     × 业务逻辑           后端做了
```

**Adapter 变成了一个纯粹的"协议转换器 + 语义格式化器"，这才是 "薄适配" 的真正含义。**

---

## 3. Kong 路由配置

```yaml
# Kong 新增 MCP 相关路由（声明式配置）

services:
  # 现有 HTTP 服务 (不动)
  - name: openapi-platform
    url: http://openapi-platform.internal:8080
    routes:
      - name: member-api
        paths: ["/crmadapter"]
      - name: coupon-api
        paths: ["/coupon"]
      - name: cashier-api
        paths: ["/cashier"]
      # ... 其余现有路由不动

  # 新增 MCP 服务
  - name: mcp-adapter
    url: http://mcp-adapter.internal:9000
    routes:
      - name: mcp-sse
        paths: ["/sse"]
        protocols: ["https"]
        strip_path: false
      - name: mcp-streamable
        paths: ["/mcp"]
        protocols: ["https"]
        strip_path: false

plugins:
  # MCP 路由复用现有的 HMAC Auth 插件（同一套 Consumer）
  - name: hmac-auth
    route: mcp-sse
    config:
      hide_credentials: true    # 不把签名头传给 Adapter
      enforce_on_admin: true

  - name: hmac-auth
    route: mcp-streamable
    config:
      hide_credentials: true

  # SSE 路由需要关闭代理缓冲
  - name: response-transformer
    route: mcp-sse
    config:
      add:
        headers:
          - "X-Accel-Buffering: no"    # 关闭 Nginx 缓冲, SSE 必需

  # 复用现有 Consumer + ACL（零配置）
  # 蔚来的 Consumer 已经有 hmac-auth credential
  # 只需在 ACL 中给蔚来加上 "mcp" group 即可访问 MCP 路由
```

**Kong 侧改动量：加 2 条路由 + 2 个插件配置。零代码改动。**

---

## 4. 三方案终极对比

| 维度 | A: Adapter behind Kong | B: 改造现有平台 | C: Kong Plugin |
|------|----------------------|----------------|----------------|
| **鉴权** | Kong 做（零重写） | Kong 做（零重写） | Kong 做（零重写） |
| **权限隔离** | Kong Consumer/ACL | Kong Consumer/ACL | Kong Consumer/ACL |
| **对现有平台风险** | **零**（不碰现有代码） | 中（要改 Java 代码） | 低 |
| **技术栈** | 自由（Python/TS） | 受限（Java） | Lua/Go（Kong 插件语言） |
| **MCP SDK 成熟度** | Python/TS 最成熟 | Java 较新 | 无现成 SDK |
| **开发速度** | 快（2周） | 中（3-4周） | 慢（需写 Kong 插件） |
| **独立部署/回滚** | 独立服务，秒级回滚 | 跟平台一起发版 | 跟 Kong 一起发版 |
| **接口同步** | 需手动同步 | 同代码库 | 需手动同步 |
| **SSE 长连接** | Adapter 原生支持 | Java 需额外适配 | Kong 需额外适配 |
| **语义化转换** | 独立迭代，快速调优 | 跟平台一起发版 | 在 Lua 中写，痛苦 |
| **团队依赖** | MCP 团队独立搞定 | 需现有平台团队配合 | 需 Kong 运维团队配合 |

---

## 5. 最终推荐：方案 A

```
推荐理由（按优先级）：

1. 鉴权零重写     Kong 全部搞定，Adapter 只做协议转换
2. 零风险         不碰现有平台一行代码，不碰 Kong 核心配置
3. 技术栈最优     Python FastMCP，MCP 生态最成熟的 SDK
4. 团队独立       不依赖现有平台团队排期，2 周可交付
5. 独立演进       MCP 协议变更时 Adapter 独立升级，不影响 HTTP 平台
6. 薄适配真谛     Adapter 里只有协议转换 + 语义化，没有鉴权/业务逻辑

Kong 侧改动：
  - 加 2 条路由（/mcp, /sse → mcp-adapter upstream）
  - 加 HMAC Auth 插件（复用现有 Consumer）
  - SSE 路由关闭代理缓冲
  - 给需要 MCP 接入的 Consumer 加 ACL group
  → 半天搞定
```

```
                                    ┌──────────────────────────┐
                                    │   Kong 改动量             │
                                    │                          │
                                    │   新路由:     2 条        │
                                    │   新插件配置: 2 个        │
                                    │   新代码:     0 行        │
                                    │   现有配置改动: 0         │
                                    └──────────────────────────┘

                                    ┌──────────────────────────┐
                                    │   现有平台改动量          │
                                    │                          │
                                    │   代码改动:   0 行        │
                                    │   配置改动:   0           │
                                    │   发版:       不需要      │
                                    └──────────────────────────┘

                                    ┌──────────────────────────┐
                                    │   MCP Adapter（全新服务）  │
                                    │                          │
                                    │   职责:                   │
                                    │   ├── MCP 协议处理        │
                                    │   ├── Tool 权限过滤       │
                                    │   ├── 参数映射            │
                                    │   └── 语义化转换          │
                                    │                          │
                                    │   不包含:                 │
                                    │   ├── × 鉴权签名          │
                                    │   ├── × 限流              │
                                    │   ├── × IP 白名单         │
                                    │   └── × 业务逻辑          │
                                    └──────────────────────────┘
```
