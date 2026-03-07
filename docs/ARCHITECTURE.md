# Coffee Company MCP 开放平台 — 架构分析与 Tool 映射

## 1. 核心思路

```
一句话：MCP Server 是现有 HTTP 开放平台的 "AI 协议皮肤"，不新增业务逻辑。
```

```
┌──────────────────────────────────────────────────────┐
│            B2B 客户的 AI Agent                        │
│                                                      │
│   蔚来车机 Agent   千问 Agent   企业自研 Agent  ...   │
│        └────────────┴────────────┴──────────┘        │
│                   MCP Protocol                       │
└──────────────────────┬───────────────────────────────┘
                       │
             SSE / Streamable HTTP
             https://mcp.coffeecompany.com
                       │
┌──────────────────────▼───────────────────────────────┐
│             MCP Adapter Layer（新建）                  │
│                                                      │
│  ┌─────────────┬──────────────┬────────────────────┐ │
│  │ Tool        │  语义化      │  权限过滤          │ │
│  │ Registry    │  转换层      │  (Kong Consumer)   │ │
│  └─────────────┴──────────────┴────────────────────┘ │
│                                                      │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐        │
│  │ 会员   │ │ 券码   │ │ 收银台 │ │ 权益   │ ...    │
│  │ Tools  │ │ Tools  │ │ Tools  │ │ Tools  │        │
│  └────────┘ └────────┘ └────────┘ └────────┘        │
└──────────────────────┬───────────────────────────────┘
                       │
          HTTPS + HMAC-SHA256/SM2 签名（不变）
                       ▼
           openapi.coffeecompany.com
           （现有 HTTP 开放平台，零改造）
```

### 与原提案的关键修正

| 维度 | 原提案 | 修正后 |
|------|--------|--------|
| **Tool 来源** | 假设 C 端接口（门店/菜单/库存） | 严格映射现有 HTTP 开放平台接口 |
| **鉴权** | 简单 Bearer Token 透传 | HMAC-SHA256 / SM2 签名（Kong 处理，MCP 层不涉及） |
| **面向客户** | 泛 C 端用户 | B2B 合作伙伴（蔚来、千问、企业客户） |
| **核心价值** | 信息查询 | 会员管理 + 权益发放 + 交易闭环 |

---

## 2. 鉴权体系：复用现有 HMAC/SM2

### 现有 HTTP 开放平台鉴权流程

```
B2B 客户申请 → 邮件获取 appKey + appSecret → IP 白名单 + 接口授权清单
每次请求构造：
  1. X-Date: GMT 时间戳
  2. Digest: SHA-256(请求体) → Base64（有 body 时）
  3. Authorization: hmac username="appKey", algorithm="hmac-sha256",
                    headers="x-date digest", signature="HMAC-SHA256(签名串, appSecret)"
```

### MCP 层如何复用（最终方案：Kong 处理鉴权）

```
方案：MCP Adapter 部署在 Kong 后面，Kong 复用现有 B2B 客户凭证做 HMAC 验签。
Adapter 不接触 appKey/appSecret，只收到 Kong 注入的 Consumer 身份信息。

┌──────────────────────────────────────────────┐
│  B2B 客户 AI Agent                            │
│                                              │
│  MCP 配置:                                    │
│  {                                           │
│    "url": "https://mcp.coffeecompany.com/sse",│
│    "headers": {                              │
│      "X-Date": "...",                        │
│      "Authorization": "hmac ..."             │  ← 标准 HMAC 签名
│    }                                         │
│  }                                           │
└──────────────────┬───────────────────────────┘
                   │ MCP Protocol (SSE)
                   ▼
┌──────────────────────────────────────────────┐
│  Kong Gateway                                │
│                                              │
│  1. HMAC Auth 插件验签 → 识别 Consumer         │
│  2. IP 白名单 / 限流 / ACL 检查               │
│  3. 注入 Consumer 信息头:                      │
│     X-Consumer-Username / X-Consumer-Groups   │
│  4. 转发到 MCP Adapter                        │
└──────────────────┬───────────────────────────┘
                   ▼
┌──────────────────────────────────────────────┐
│  MCP Adapter (本项目)                         │
│                                              │
│  1. 从 Kong 注入头获取 Consumer 身份和权限      │
│  2. 根据 Consumer Groups 过滤可用 Tool         │
│  3. Tool 调用 → 内网直连后端                    │
│  4. 语义化转换响应 → 返回 AI Agent              │
└──────────────────────────────────────────────┘
```

**核心原则**：
- **appKey/appSecret 不作为 Tool 参数**（避免每次调用暴露，也避免 LLM 幻觉填错）
- **鉴权由 Kong 统一处理**，Adapter 只做协议转换 + 语义化
- 现有开放平台的 IP 白名单、接口授权清单、限流策略 **全部生效，零改造**
- 详见 [部署决策文档](DEPLOY_DECISION.md)

---

## 3. 现有 HTTP 接口 → MCP Tool 完整映射

### 3.1 会员服务（Member）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `member_register` | 会员注册 | POST | `/crmadapter/account/register` | "帮这个用户注册Coffee Company会员" |
| `member_query` | 会员查询 | POST | `/crmadapter/account/query` | "查一下这个手机号有没有Coffee Company会员" |
| `member_bind` | 三方绑定 | POST | `/crmadapter/account/3pp/bind` | "把蔚来账号和Coffee Company会员绑定" |
| `member_tier` | 等级查询 | POST | `/crmadapter/account/memberTier` | "这个会员现在是什么等级" |
| `member_benefits` | 权益状态 | POST | `/crmadapter/customers/getBenefits` | "这个会员的 8 项权益开通了吗" |
| `member_benefit_list` | 权益列表 | POST | `/crmadapter/asset/coupon/getBenefitList` | "列出这个会员的所有优惠券" |
| `member_login_url` | 登录链接 | POST | `/crmadapter/account/3pp/getLoginUrl` | "生成Coffee Company会员登录页面链接" |

### 3.2 券码服务（Coupon）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `coupon_create` | 生成券码 | POST | `/coupon/create` | "为这个活动批量生成 5 张券" |
| `coupon_cancel` | 取消券码 | POST | `/coupon/cancel` | "作废这张券" |
| `coupon_query` | 查询状态 | POST | `/coupon/query` | "券码生成成功了吗" |
| `coupon_detail` | 券码详情 | POST | `/coupon/detail` | "查一下这张券的状态和使用情况" |
| `coupon_claim` | 领取权益 | POST | `/coupon/get` | "用户领取渠道权益" |
| `coupon_claim_status` | 领取进度 | POST | `/coupon/state` | "权益到账了吗" |

### 3.3 收银台服务（Cashier / Payment）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `cashier_checkout` | 收银下单 | POST | `/cashier/doCheckStand` | "发起一笔支付" |
| `cashier_pay_query` | 支付查询 | POST | `/cashier/payQuery` | "支付成功了吗" |

### 3.4 权益服务（Equity / Benefits）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `equity_send` | 发放电子券 | POST | `/equity/send` | "给用户发一张Coffee Company券" |
| `equity_cancel` | 取消/退款 | POST | `/equity/cancel` | "退掉这张券" |
| `equity_query` | 发放查询 | POST | `/equity/query` | "券发出去了吗" |
| `equity_detail` | 券详情 | POST | `/equity/detail` | "这张券什么状态，用了几次" |
| `equity_bind` | 绑卡 | POST | `/equity/bind` | "把这张卡绑到会员账户" |

### 3.5 权益服务 2.0（Benefits v2）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `benefit_issue` | 活动权益发放 | POST | `/api/v1/benefit/issue` | "给飞猪/亚朵渠道用户发权益" |
| `benefit_send` | 非货币权益 | POST | `/benefit/send` | "发放三方权益券码" |
| `benefit_cancel` | 权益取消 | POST | `/benefit/cancel` | "取消未使用的权益" |
| `srkit_send` | 权益发放(v2) | POST | `/srkit/send` | "发放Coffee Company权益，未注册会员自动挂起" |
| `srkit_status` | 发放状态 | POST | `/srkit/state` | "权益到账了吗" |
| `srkit_cancel` | 取消发放 | POST | `/srkit/cancel` | "取消未注册用户的挂起权益" |

### 3.6 订单服务（Order）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `order_list` | 批量查询 | POST | `/order/list` | "拉取这段时间的订单" |
| `order_status_update` | 状态更新 | POST | `/order/status` | "把订单标记为已支付/取消" |
| `order_push` | 全渠道推单 | POST | `/order/order_info/omni` | "推送一笔订单到Coffee Company" |
| `order_refund` | 退款推送 | POST | `/order/refund_info/omni` | "推送退款信息" |

### 3.7 客户资产（Assets）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `assets_list` | 全部资产 | POST | `/assets/list` | "查看用户所有券和权益" |
| `assets_coupons` | 券资产列表 | POST | `/assets/coupons/list` | "查看用户的优惠券列表" |
| `assets_sync` | 同步资产 | POST | `/assets/coupons/channel/binding` | "同步券资产到渠道" |

### 3.8 星星核销（Stars Redemption）

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `stars_lock` | 锁定星星 | POST | `/staradapter/lockForRedeem` | "锁定 50 颗星准备兑换" |
| `stars_redeem` | 星星核销 | POST | `/staradapter/redeemLocked` | "执行星星兑换" |
| `stars_cancel` | 取消核销 | POST | `/staradapter/cancelRedemption` | "撤销兑换，恢复星星" |
| `stars_unlock` | 解锁星星 | POST | `/staradapter/unlock` | "取消锁定，释放星星" |

### 3.9 其他服务

| MCP Tool | HTTP API | 方法 | 路径 | 场景 |
|----------|----------|------|------|------|
| `dqr_get_token` | OTP 动态码 | POST | `/base/dqr/otp/token/get` | "获取动态码种子" |
| `dqr_get_web` | Web 动态码 | POST | `/base/dqr/otp/token/get/web` | "获取展示用动态码" |
| `sms_send` | 发送短信 | POST | `/nc/api/sms/send` | "给用户发短信通知" |
| `promotion_enroll` | 注册双倍积星 | POST | `/le/member/enrollPromotion` | "注册参加双倍积星活动" |

---

## 4. MCP Tool 分级开放策略

### Phase 1（2 周）—— 只读查询，最低风险

**10 个 Tool，全部只读，适合快速验证：**

| Tool | 分类 | 风险 |
|------|------|------|
| `member_query` | 会员 | 只读 |
| `member_tier` | 会员 | 只读 |
| `member_benefits` | 会员 | 只读 |
| `member_benefit_list` | 会员 | 只读 |
| `coupon_query` | 券码 | 只读 |
| `coupon_detail` | 券码 | 只读 |
| `cashier_pay_query` | 收银台 | 只读 |
| `equity_query` | 权益 | 只读 |
| `equity_detail` | 权益 | 只读 |
| `assets_list` | 资产 | 只读 |

### Phase 2（第 3-5 周）—— 写入操作

| Tool | 分类 | 风险 | 需人工确认 |
|------|------|------|-----------|
| `member_register` | 会员 | 中 | 否 |
| `member_bind` | 会员 | 中 | 否 |
| `coupon_create` | 券码 | 高 | 是 |
| `coupon_claim` | 券码 | 中 | 否 |
| `equity_send` | 权益 | 高 | 是 |
| `benefit_issue` | 权益 | 高 | 是 |
| `srkit_send` | 权益 | 高 | 是 |

### Phase 3（第 6-8 周）—— 交易闭环 + 核销

| Tool | 分类 | 风险 | 需人工确认 |
|------|------|------|-----------|
| `cashier_checkout` | 支付 | 极高 | 是 |
| `order_push` | 订单 | 高 | 是 |
| `stars_lock` / `stars_redeem` | 核销 | 高 | 是 |
| `coupon_cancel` / `equity_cancel` | 取消 | 高 | 是 |
| `order_refund` | 退款 | 极高 | 是 |

---

## 5. B2B 客户接入场景

### 蔚来车机 Agent

```
车主对蔚来 AI 说："到目的地前帮我在Coffee Company下单一杯拿铁"

蔚来 Agent MCP 调用链：
  1. member_query(mobile=车主手机号)     → 确认有Coffee Company会员
  2. member_benefit_list()               → 检查有没有可用优惠券
  3. assets_list()                       → 查看券资产
  4. cashier_checkout(payLoad=...)       → 发起支付（需车主确认）
  5. cashier_pay_query(payToken=...)     → 确认支付成功

蔚来 MCP 配置:
{
  "mcpServers": {
    "coffee-company": {
      "url": "https://mcp.coffeecompany.com/sse",
      "headers": {
        "X-CC-App-Key": "nio_partner_key",
        "X-CC-App-Secret": "nio_partner_secret"
      }
    }
  }
}
```

### 千问 Agent（企业员工福利）

```
HR 对千问说："给市场部 50 人每人发一张Coffee Company中杯券"

千问 Agent MCP 调用链：
  1. coupon_create(campaignId=xxx, quantity=50)  → 批量生成券码
  2. coupon_query(orderId=xxx)                   → 确认生成成功
  3. equity_send(orderId=xxx, ...)               → 逐一发放给员工
  4. srkit_status(orderId=xxx)                   → 确认到账

千问 MCP 配置:
{
  "mcpServers": {
    "coffee-company": {
      "url": "https://mcp.coffeecompany.com/sse",
      "headers": {
        "X-CC-App-Key": "qwen_enterprise_key",
        "X-CC-App-Secret": "qwen_enterprise_secret"
      }
    }
  }
}
```

---

## 6. 语义化转换层设计

每个 Tool 的响应不直接返回原始 JSON，而是转换为 LLM 友好的自然语言：

```
原始 HTTP 响应:
{
  "code": 200,
  "data": {
    "memberTier": "GOLD",
    "starBalance": 142,
    "tierExpireDate": "2026-12-31"
  }
}

MCP Tool 语义化响应:
"该会员当前为金星级(Gold)，拥有 142 颗星星，
 等级有效期至 2026-12-31。距下一级（黑金）还需 108 颗星。"
```

```
原始 HTTP 响应:
{
  "code": 200,
  "status": 1,
  "stateMsg": "支付成功"
}

MCP Tool 语义化响应:
"支付已完成。订单状态：支付成功。"
```

---

## 7. 总结：一张图看清全局

```
                    现有 HTTP 开放平台                    MCP Adapter（新建）
                    ─────────────────                    ──────────────────
接入方式            appKey+appSecret 邮件发放             复用，MCP 连接头传入
鉴权                HMAC-SHA256 / SM2                    Adapter 层实现签名
传输                HTTPS POST JSON                      MCP Protocol (SSE/Streamable HTTP)
响应格式            原始 JSON                             语义化自然语言
接口数量            ~60+ 个 HTTP 接口                      ~40 个 MCP Tool（分 3 期）
面向对象            B2B 合作伙伴开发者                     B2B 合作伙伴的 AI Agent
新增业务逻辑        无                                    无（纯协议转换 + 语义化）
开放平台改造量      零                                    零
```
