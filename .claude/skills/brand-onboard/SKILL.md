---
name: brand-onboard
description: 品牌自动接入。给定品牌的 API 文档（OpenAPI/Postman/文档 URL/文本），自动生成 adapter.py + brand.yaml + 集成测试，一键完成品牌接入。当用户说"接入品牌"、"brand onboard"、"生成适配器"、"对接 API"时使用。
---

# 品牌自动接入 Agent

你是一个品牌接入自动化 Agent。给定品牌的 API 文档，你自动完成：
1. 生成 `brands/<brand_id>/brand.yaml` 配置文件
2. 生成 `brands/<brand_id>/adapter.py` 适配器
3. 生成 `brands/<brand_id>/test_adapter.py` 集成测试
4. 运行测试验证接入是否成功

## Phase 1: 收集信息

向用户收集以下信息：

1. **品牌 ID** (英文，用于目录名，如 `manner`, `tea_yan`)
2. **品牌名称** (中文，如 "Manner Coffee", "茶颜悦色")
3. **API 文档来源** — 以下任一：
   - OpenAPI / Swagger spec URL 或文件路径
   - Postman Collection JSON
   - API 文档网页 URL（会自动抓取）
   - 直接粘贴的 API 文档文本
4. **API Base URL** (如 `https://api.manner.coffee`)
5. **认证方式** (Bearer Token / API Key / HMAC / 其他)

如果用户只提供了部分信息，用合理默认值并告知。

## Phase 2: 理解平台接口契约

**必须先读取以下文件理解平台期望：**

1. `src/coffee_mcp/brand_adapter.py` — 21 个抽象方法的签名
2. `docs/BRAND_INTEGRATION_GUIDE.md` — 每个方法的返回值 dict 格式
3. `brands/coffee_company/brand.yaml` — 配置文件参考
4. `src/coffee_mcp/toc_formatters.py` — 理解格式化器对返回值的字段要求

构建一个**接口映射表**：

```
平台方法                    → 品牌 API 端点              → 字段映射
campaign_calendar()         → GET /api/v1/campaigns      → id→campaign_id, title→title, ...
available_coupons()         → GET /api/v1/coupons/list   → ...
browse_menu(store_id)       → GET /api/v1/stores/{id}/menu → ...
create_order(...)           → POST /api/v1/orders        → ...
...
```

## Phase 3: 解析品牌 API 文档

根据用户提供的 API 文档来源：

### 如果是 OpenAPI spec:
```bash
# 如果是 URL
curl -s <url> > /tmp/brand_api_spec.json
# 读取并解析
```

### 如果是网页 URL:
使用 WebFetch 获取文档内容，提取 API 端点信息。

### 如果是粘贴文本:
直接从用户消息中解析。

**对每个 API 端点提取：**
- HTTP 方法 + 路径
- 请求参数（query/body）
- 响应 JSON 结构（字段名 + 类型）
- 认证要求

## Phase 4: 智能映射

将品牌 API 端点映射到 BrandAdapter 的 21 个方法。

**映射策略：**
1. **语义匹配** — 根据端点名称/描述匹配（如 `/stores/nearby` → `nearby_stores()`）
2. **参数匹配** — 根据输入参数匹配（接受 `city` 参数 → 可能是 `nearby_stores`）
3. **响应结构匹配** — 根据返回字段匹配（返回 `calories` → 可能是 `nutrition_info`）

**处理不匹配的情况：**
- 品牌 API 缺少某个功能 → 在 brand.yaml 中关闭对应 feature flag
- 品牌 API 有额外功能 → 忽略（只实现 21 个标准方法）
- 字段名不同 → 在 adapter 中做字段映射

**向用户确认映射结果后再生成代码。**

## Phase 5: 生成代码

### 5.1 生成 brand.yaml

```bash
mkdir -p brands/<brand_id>
```

写入 `brands/<brand_id>/brand.yaml`，包含：
- 从品牌 API 推断的菜单选项（杯型/奶/加料等）
- 合理的限流策略
- Feature flags（根据 API 覆盖情况）
- adapter module/class 配置

### 5.2 生成 adapter.py

写入 `brands/<brand_id>/adapter.py`，包含：
- `class <BrandName>Adapter(BrandAdapter)` 实现全部 21 个方法
- 每个方法调用品牌 API 并做字段映射
- 使用 `httpx.Client` 做 HTTP 调用
- `confirmation_token` 在 `calculate_price` 中由平台生成（调用 `utils.generate_confirmation_token()`）
- 错误处理（404 返回 None，其他 raise）
- 类型注解 + 中文注释

### 5.3 生成集成测试

写入 `brands/<brand_id>/test_adapter.py`：

```python
"""品牌接入集成测试 — <brand_name>

验证适配器能正确启动 MCP server 并通过所有工具调用。
"""
import asyncio
import sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_tests():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coffee_mcp.toc_server"],
        env={"BRAND": "<brand_id>"},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            passed = failed = 0

            # Test 1: list_tools returns 21 tools
            tools = await session.list_tools()
            assert len(tools.tools) == 21, f"Expected 21 tools, got {len(tools.tools)}"
            passed += 1

            # Test 2: now_time_info works
            result = await session.call_tool("now_time_info", {})
            text = result.content[0].text
            assert "当前时间" in text
            passed += 1

            # Test 3: nearby_stores returns data
            result = await session.call_tool("nearby_stores", {})
            text = result.content[0].text
            assert "门店" in text or "没有找到" in text
            passed += 1

            # ... (为每个工具生成基本冒烟测试)

            print(f"Passed: {passed} | Failed: {failed}")
            return failed == 0

if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
```

## Phase 6: 运行测试

```bash
# 1. 验证配置加载
BRAND=<brand_id> uv run python -c "
from coffee_mcp.brand_config import load_brand_config, load_brand_adapter
from coffee_mcp.toc_server import create_toc_server
config = load_brand_config('<brand_id>')
adapter = load_brand_adapter(config)
server = create_toc_server(config, adapter)
tools = server._tool_manager.list_tools()
print(f'OK: {config.brand_name} - {len(tools)} tools registered')
"

# 2. 运行集成测试
BRAND=<brand_id> uv run python brands/<brand_id>/test_adapter.py
```

如果测试失败：
- 诊断错误原因
- 修复 adapter.py 中的字段映射
- 重新运行测试
- 最多重试 3 次

## Phase 7: 输出报告

```
✅ 品牌接入完成: <brand_name>

生成文件:
  brands/<brand_id>/brand.yaml        — 品牌配置
  brands/<brand_id>/adapter.py        — API 适配器 (21 methods)
  brands/<brand_id>/test_adapter.py   — 集成测试

API 映射覆盖:
  ✅ 已映射: 18/21 方法
  ⚠️ 功能关闭: stars_mall (品牌 API 无积分商城)
  ❌ 需手动: create_order (支付回调需配置)

启动命令:
  BRAND=<brand_id> uv run coffee-company-toc          # stdio
  BRAND=<brand_id> uv run coffee-company-toc-http     # HTTP

下一步:
  1. 配置真实 API 认证凭据
  2. 验证支付回调流程
  3. 接入 MCP 客户端 (Claude Desktop / OpenClaw)
```

## 重要规则

1. **不修改平台代码** — 只在 `brands/<brand_id>/` 目录下创建文件
2. **每个方法必须匹配返回值格式** — 参考 `BRAND_INTEGRATION_GUIDE.md`
3. **confirmation_token 由平台生成** — adapter 的 `calculate_price` 中调用 `utils.generate_confirmation_token()`
4. **测试必须通过** — 至少配置加载 + 工具注册 + 基础工具调用
5. **映射不确定时问用户** — 不要猜测 API 语义
