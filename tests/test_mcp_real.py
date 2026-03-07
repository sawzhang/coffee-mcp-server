"""Real MCP protocol tests — connects to the server via stdio and exercises all tools + resources."""

import asyncio
import sys
import traceback

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_tests():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coffee_mcp.server"],
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            passed = 0
            failed = 0
            total = 0

            async def check(name: str, tool: str, args: dict, expect_in: list[str]):
                nonlocal passed, failed, total
                total += 1
                try:
                    result = await session.call_tool(tool, arguments=args)
                    text = "\n".join(b.text for b in result.content if hasattr(b, "text"))
                    missing = [e for e in expect_in if e not in text]
                    if missing:
                        print(f"  FAIL  {name}")
                        print(f"        missing: {missing}")
                        print(f"        got: {text[:200]}")
                        failed += 1
                    else:
                        print(f"  PASS  {name}")
                        passed += 1
                except Exception as exc:
                    print(f"  FAIL  {name} — exception: {exc}")
                    traceback.print_exc()
                    failed += 1

            # ── list_tools ──────────────────────────────────────
            print("\n=== list_tools ===")
            tools_result = await session.list_tools()
            tool_names = sorted(t.name for t in tools_result.tools)
            expected_tools = sorted([
                "member_query", "member_tier", "member_benefits",
                "member_benefit_list", "coupon_query", "coupon_detail",
                "equity_query", "equity_detail", "assets_list",
                "cashier_pay_query",
            ])
            total += 1
            if tool_names == expected_tools:
                print(f"  PASS  list_tools returned {len(tool_names)} tools")
                passed += 1
            else:
                print(f"  FAIL  expected {expected_tools}, got {tool_names}")
                failed += 1

            # ── list_resources ──────────────────────────────────
            print("\n=== list_resources ===")
            resources_result = await session.list_resources()
            resource_uris = sorted(str(r.uri) for r in resources_result.resources)
            total += 1
            if "coffee://api/catalog" in resource_uris and "coffee://auth/guide" in resource_uris:
                print(f"  PASS  list_resources returned {resource_uris}")
                passed += 1
            else:
                print(f"  FAIL  expected catalog+guide, got {resource_uris}")
                failed += 1

            # ── read_resource ───────────────────────────────────
            print("\n=== read_resource ===")
            for uri, expect in [
                ("coffee://api/catalog", ["Phase 1", "member_query", "coupon_detail"]),
                ("coffee://auth/guide", ["Kong", "HMAC-SHA256", "Demo"]),
            ]:
                total += 1
                try:
                    res = await session.read_resource(uri)
                    text = ""
                    for block in res.contents:
                        if hasattr(block, "text"):
                            text += block.text
                    missing = [e for e in expect if e not in text]
                    if missing:
                        print(f"  FAIL  read {uri} — missing: {missing}")
                        failed += 1
                    else:
                        print(f"  PASS  read {uri}")
                        passed += 1
                except Exception as exc:
                    print(f"  FAIL  read {uri} — {exc}")
                    failed += 1

            # ── Tool 1: member_query ────────────────────────────
            print("\n=== member_query ===")
            await check("by mobile", "member_query", {"mobile": "138****1234"}, ["张三", "CC_M_100001", "金星"])
            await check("by open_id", "member_query", {"open_id": "oDEF987654321"}, ["李四", "CC_M_100002"])
            await check("by member_id", "member_query", {"member_id": "CC_M_100003"}, ["王五", "钻星"])
            await check("not found", "member_query", {"member_id": "NONEXIST"}, ["未找到"])
            await check("no params", "member_query", {}, ["请提供"])

            # ── Tool 2: member_tier ─────────────────────────────
            print("\n=== member_tier ===")
            await check("gold tier", "member_tier", {"member_id": "CC_M_100001"}, ["金星", "142", "358"])
            await check("diamond (max)", "member_tier", {"member_id": "CC_M_100003"}, ["钻星", "最高"])
            await check("not found", "member_tier", {"member_id": "NONEXIST"}, ["未找到"])

            # ── Tool 3: member_benefits ─────────────────────────
            print("\n=== member_benefits ===")
            await check("gold benefits", "member_benefits", {"member_id": "CC_M_100001"}, ["生日奖励", "可使用", "5 项"])
            await check("green benefits", "member_benefits", {"member_id": "CC_M_100002"}, ["新人礼券", "可使用"])
            await check("not found", "member_benefits", {"member_id": "NONEXIST"}, ["未找到"])

            # ── Tool 4: member_benefit_list ─────────────────────
            print("\n=== member_benefit_list ===")
            await check("has coupons", "member_benefit_list", {"member_id": "CC_M_100001"}, ["共 3 张", "中杯饮品券", "生日免费饮品"])
            await check("empty", "member_benefit_list", {"member_id": "NONEXIST"}, ["暂无"])

            # ── Tool 5: coupon_query ────────────────────────────
            print("\n=== coupon_query ===")
            await check("found 2", "coupon_query", {"order_id": "ORD_2026030100001"}, ["共 2 张", "CC20260301A001", "CC20260301A002"])
            await check("not found", "coupon_query", {"order_id": "NONEXIST"}, ["未找到"])

            # ── Tool 6: coupon_detail ───────────────────────────
            print("\n=== coupon_detail ===")
            await check("unused coupon", "coupon_detail", {"coupon_code": "CC20260301A001"}, ["未使用", "¥35", "中杯饮品券"])
            await check("used coupon", "coupon_detail", {"coupon_code": "CC20260301A002"}, ["已使用", "1 / 1"])
            await check("not found", "coupon_detail", {"coupon_code": "NONEXIST"}, ["未找到"])

            # ── Tool 7: equity_query ────────────────────────────
            print("\n=== equity_query ===")
            await check("found", "equity_query", {"order_id": "EQ_2026030100001"}, ["发放成功", "CC20260301A001"])
            await check("not found", "equity_query", {"order_id": "NONEXIST"}, ["未找到"])

            # ── Tool 8: equity_detail ───────────────────────────
            print("\n=== equity_detail ===")
            await check("detail", "equity_detail", {"order_id": "EQ_2026030100002"}, ["发放成功", "CC20260301A002", "1 次"])
            await check("not found", "equity_detail", {"order_id": "NONEXIST"}, ["未找到"])

            # ── Tool 9: assets_list ─────────────────────────────
            print("\n=== assets_list ===")
            await check("gold assets", "assets_list", {"member_id": "CC_M_100001"}, ["共 3 张", "优惠券", "权益券"])
            await check("diamond assets", "assets_list", {"member_id": "CC_M_100003"}, ["共 4 张", "钻星专属"])
            await check("not found", "assets_list", {"member_id": "NONEXIST"}, ["未找到"])

            # ── Tool 10: cashier_pay_query ──────────────────────
            print("\n=== cashier_pay_query ===")
            await check("success", "cashier_pay_query", {"pay_token": "PAY_TOKEN_001"}, ["支付成功", "¥37", "微信支付"])
            await check("pending", "cashier_pay_query", {"pay_token": "PAY_TOKEN_002"}, ["支付中", "支付宝"])
            await check("failed", "cashier_pay_query", {"pay_token": "PAY_TOKEN_003"}, ["支付失败"])
            await check("not found", "cashier_pay_query", {"pay_token": "NONEXIST"}, ["未找到"])

            # ── Summary ────────────────────────────────────────
            print(f"\n{'='*50}")
            print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
            print(f"{'='*50}")
            return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
