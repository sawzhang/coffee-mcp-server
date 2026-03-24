"""Real MCP protocol tests for ToC (consumer-facing) server.

Connects to toc_server via stdio and exercises all 21 tools,
covering happy paths, edge cases, and the full order flow.

New in this version:
  - now_time_info tool
  - idempotency_key on L3 operations
  - confirmation_token flow (calculate_price → create_order)
  - PII masking in address list
  - compact mode for menu and nutrition
  - randomized IDs (addr_xxx, ord_xxx)
"""

import asyncio
import sys
import traceback

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def run_tests():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "coffee_mcp.toc_server"],
    )

    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            passed = 0
            failed = 0
            total = 0

            async def check(name: str, tool: str, args: dict, expect_in: list[str],
                            expect_not_in: list[str] | None = None):
                nonlocal passed, failed, total
                total += 1
                try:
                    result = await session.call_tool(tool, arguments=args)
                    text = "\n".join(b.text for b in result.content if hasattr(b, "text"))
                    missing = [e for e in expect_in if e not in text]
                    unwanted = [e for e in (expect_not_in or []) if e in text]
                    if missing or unwanted:
                        print(f"  FAIL  {name}")
                        if missing:
                            print(f"        missing: {missing}")
                        if unwanted:
                            print(f"        unwanted: {unwanted}")
                        print(f"        got: {text[:300]}")
                        failed += 1
                    else:
                        print(f"  PASS  {name}")
                        passed += 1
                except Exception as exc:
                    print(f"  FAIL  {name} — exception: {exc}")
                    traceback.print_exc()
                    failed += 1

            def extract_text(result) -> str:
                return "\n".join(b.text for b in result.content if hasattr(b, "text"))

            # ── list_tools ──────────────────────────────────────
            print("\n=== list_tools ===")
            tools_result = await session.list_tools()
            tool_names = sorted(t.name for t in tools_result.tools)
            expected_tools = sorted([
                "now_time_info",
                "campaign_calendar", "available_coupons", "claim_all_coupons",
                "my_account", "my_coupons", "my_orders",
                "browse_menu", "drink_detail", "nutrition_info",
                "nearby_stores", "store_detail",
                "stars_mall_products", "stars_product_detail", "stars_redeem",
                "delivery_addresses", "create_address", "store_coupons",
                "calculate_price", "create_order", "order_status",
            ])
            total += 1
            if tool_names == expected_tools:
                print(f"  PASS  list_tools returned {len(tool_names)} tools")
                passed += 1
            else:
                extra = set(tool_names) - set(expected_tools)
                missing = set(expected_tools) - set(tool_names)
                print(f"  FAIL  tools mismatch — extra: {extra}, missing: {missing}")
                failed += 1

            # ════════════════════════════════════════════════════
            # Group 0: Utility
            # ════════════════════════════════════════════════════
            print("\n=== now_time_info ===")
            await check("returns current time", "now_time_info", {},
                        ["当前时间", "2026", "周"])

            # ════════════════════════════════════════════════════
            # Group 1: Discovery + Promotions
            # ════════════════════════════════════════════════════
            print("\n=== campaign_calendar ===")
            await check("all campaigns", "campaign_calendar", {},
                        ["活动日历", "春日樱花季", "进行中", "即将开始"])
            await check("with month param", "campaign_calendar", {"month": "2026-03"},
                        ["活动日历"])

            print("\n=== available_coupons ===")
            await check("list coupons", "available_coupons", {},
                        ["可领取优惠券", "拿铁系列立减5元", "满50减10元",
                         "免费升杯券", "可领取", "已领取"])
            await check("has claim hint", "available_coupons", {},
                        ["帮我全部领取"])

            print("\n=== claim_all_coupons ===")
            await check("claim all", "claim_all_coupons", {},
                        ["一键领券成功", "3 张", "拿铁系列立减5元", "卡包"])

            # ════════════════════════════════════════════════════
            # Group 2: My Account
            # ════════════════════════════════════════════════════
            print("\n=== my_account ===")
            await check("account info", "my_account", {},
                        ["张三", "金星级", "142", "358", "5 项", "3 张"])

            print("\n=== my_coupons ===")
            await check("all coupons", "my_coupons", {},
                        ["我的优惠券", "共 3 张", "中杯饮品券"])
            await check("valid only", "my_coupons", {"status": "valid"},
                        ["我的优惠券"])
            await check("used only (none for this user)", "my_coupons", {"status": "used"},
                        ["没有优惠券"])

            print("\n=== my_orders ===")
            await check("recent orders", "my_orders", {},
                        ["我的订单", "TOC_ORD_20260318001", "已完成",
                         "拿铁", "可颂"])
            await check("order with delivery", "my_orders", {},
                        ["TOC_ORD_20260320002", "制作中", "樱花白巧拿铁", "外送"])
            await check("limit param", "my_orders", {"limit": 1},
                        ["我的订单", "最近 1 笔"])

            # ════════════════════════════════════════════════════
            # Group 3: Menu + Drinks
            # ════════════════════════════════════════════════════
            print("\n=== browse_menu ===")
            await check("full menu", "browse_menu", {"store_id": "ST_SH_001"},
                        ["南京西路旗舰店 菜单", "经典浓缩", "拿铁系列",
                         "季节特调", "茶饮系列", "轻食甜点",
                         "美式咖啡", "拿铁", "樱花白巧拿铁", "🆕"])
            await check("compact menu", "browse_menu", {"store_id": "ST_SH_001", "compact": True},
                        ["南京西路旗舰店 菜单", "商品|价格|杯型|编号",
                         "拿铁", "D003"])
            await check("invalid store", "browse_menu", {"store_id": "NONEXIST"},
                        ["不存在"])
            await check("closed store no items", "browse_menu", {"store_id": "ST_SH_003"},
                        ["徐汇滨江店 菜单"])

            print("\n=== drink_detail ===")
            await check("latte customization", "drink_detail", {"product_code": "D003"},
                        ["拿铁", "¥32", "杯型", "中杯", "大杯(+¥4)", "超大杯(+¥7)",
                         "温度", "热", "冰",
                         "奶类", "全脂牛奶", "燕麦奶(+¥5)", "椰奶(+¥5)",
                         "甜度", "标准糖", "半糖", "无糖",
                         "加料", "浓缩+1份(+¥6)", "香草糖浆(+¥4)"])
            await check("food (no customization)", "drink_detail", {"product_code": "F001"},
                        ["经典可颂", "¥18"],
                        expect_not_in=["杯型", "奶类"])
            await check("seasonal new item", "drink_detail", {"product_code": "D006"},
                        ["樱花白巧拿铁", "限定春季", "¥42"])
            await check("not found", "drink_detail", {"product_code": "NONEXIST"},
                        ["未找到"])

            print("\n=== nutrition_info ===")
            await check("latte nutrition", "nutrition_info", {"product_code": "D003"},
                        ["拿铁", "营养信息", "150 kcal", "蛋白质", "脂肪",
                         "咖啡因", "150mg"])
            await check("compact nutrition", "nutrition_info",
                        {"product_code": "D003", "compact": True},
                        ["拿铁", "150kcal", "蛋白", "脂肪", "咖啡因150mg"])
            await check("tea caffeine", "nutrition_info", {"product_code": "T001"},
                        ["抹茶拿铁", "30mg"])
            await check("not found", "nutrition_info", {"product_code": "NONEXIST"},
                        ["未找到"])

            # ════════════════════════════════════════════════════
            # Group 4: Stores
            # ════════════════════════════════════════════════════
            print("\n=== nearby_stores ===")
            await check("all stores", "nearby_stores", {},
                        ["附近门店", "共 4 家"])
            await check("filter by city", "nearby_stores", {"city": "上海"},
                        ["共 3 家", "南京西路", "陆家嘴", "徐汇"],
                        expect_not_in=["新街口"])
            await check("filter by keyword", "nearby_stores", {"keyword": "陆家嘴"},
                        ["共 1 家", "陆家嘴中心店"])
            await check("no results", "nearby_stores", {"city": "北京"},
                        ["没有找到"])
            await check("store status shown", "nearby_stores", {},
                        ["营业中", "休息中"])

            print("\n=== store_detail ===")
            await check("detail", "store_detail", {"store_id": "ST_SH_001"},
                        ["南京西路旗舰店", "营业中", "07:00-22:00",
                         "堂食", "自提", "外送", "WiFi", "宠物友好"])
            await check("not found", "store_detail", {"store_id": "NONEXIST"},
                        ["未找到"])

            # ════════════════════════════════════════════════════
            # Group 5: Points Mall
            # ════════════════════════════════════════════════════
            print("\n=== stars_mall_products ===")
            await check("all products", "stars_mall_products", {},
                        ["积分商城", "142 颗星星", "中杯饮品兑换券", "100星",
                         "品牌随行杯", "300星", "✅", "🔒"])
            await check("filter by category", "stars_mall_products", {"category": "周边"},
                        ["品牌随行杯"],
                        expect_not_in=["中杯饮品兑换券"])

            print("\n=== stars_product_detail ===")
            await check("affordable", "stars_product_detail", {"product_code": "SM_001"},
                        ["中杯饮品兑换券", "100", "可兑换", "142"])
            await check("not affordable", "stars_product_detail", {"product_code": "SM_003"},
                        ["品牌随行杯", "300", "星星不足"])
            await check("not found", "stars_product_detail", {"product_code": "NONEXIST"},
                        ["未找到"])

            print("\n=== stars_redeem (with idempotency) ===")
            await check("success", "stars_redeem",
                        {"product_code": "SM_002", "idempotency_key": "test_idem_001"},
                        ["兑换成功", "经典可颂兑换券", "50", "92", "兑换单号"])
            await check("not enough stars", "stars_redeem",
                        {"product_code": "SM_003", "idempotency_key": "test_idem_002"},
                        ["不足", "300", "142"])
            await check("product not found", "stars_redeem",
                        {"product_code": "NONEXIST", "idempotency_key": "test_idem_003"},
                        ["不存在"])
            # Test idempotency: same key should return cached result
            await check("idempotency replay", "stars_redeem",
                        {"product_code": "SM_002", "idempotency_key": "test_idem_001"},
                        ["兑换成功", "经典可颂兑换券"])

            # ════════════════════════════════════════════════════
            # Group 6: Order Flow
            # ════════════════════════════════════════════════════
            print("\n=== delivery_addresses (PII masking) ===")
            await check("list addresses with masked phone", "delivery_addresses", {},
                        ["我的配送地址", "共 2 个", "张三", "138****1234",
                         "静安嘉里", "addr_", "[默认]"],
                        expect_not_in=["13812341234"])

            print("\n=== create_address (randomized ID) ===")
            await check("create new", "create_address", {
                "city": "上海",
                "address": "延安西路2299号世贸商城",
                "address_detail": "3F-301",
                "contact_name": "张三",
                "phone": "13812341234",
            }, ["地址创建成功", "世贸商城", "3F-301", "addr_"])

            print("\n=== store_coupons ===")
            await check("coupons at store", "store_coupons", {"store_id": "ST_SH_001"},
                        ["南京西路旗舰店", "可用优惠券"])
            await check("closed store", "store_coupons", {"store_id": "ST_SH_003"},
                        ["暂无可用"])

            print("\n=== calculate_price (with confirmation_token) ===")
            await check("single item + token", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "milk": "oat", "quantity": 1}],
            }, ["价格计算", "拿铁", "大杯", "¥41", "应付", "确认令牌", "cfm_"])

            await check("multiple items", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [
                    {"product_code": "D003", "size": "tall", "quantity": 1},
                    {"product_code": "F001", "quantity": 2},
                ],
            }, ["价格计算", "拿铁", "可颂", "应付", "确认令牌"])

            await check("with coupon", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                "coupon_code": "AVL_001",
            }, ["优惠减免", "-¥5", "拿铁系列立减5元", "确认令牌"])

            await check("invalid product", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "NONEXIST", "quantity": 1}],
            }, ["不存在"])

            await check("invalid store", "calculate_price", {
                "store_id": "NONEXIST",
                "items": [{"product_code": "D003", "quantity": 1}],
            }, ["不存在"])

            await check("with extras", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "milk": "oat",
                           "extras": ["extra_shot", "vanilla_syrup"], "quantity": 1}],
            }, ["价格计算", "¥51"])  # 32 + 4(grande) + 5(oat) + 6(shot) + 4(vanilla) = 51

            # ── create_order with confirmation_token flow ──
            print("\n=== create_order (confirmation_token + idempotency) ===")

            # Step 1: Get confirmation token from calculate_price
            total += 1
            calc_result = await session.call_tool("calculate_price", arguments={
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
            })
            calc_text = extract_text(calc_result)
            # Extract confirmation token
            token = None
            for line in calc_text.split("\n"):
                if "cfm_" in line:
                    import re
                    match = re.search(r"cfm_[a-f0-9]+", line)
                    if match:
                        token = match.group(0)
                        break
            if token:
                print(f"  PASS  got confirmation_token: {token}")
                passed += 1
            else:
                print(f"  FAIL  no confirmation_token in calculate_price output")
                print(f"        got: {calc_text[:200]}")
                failed += 1

            # Step 2: Create order with token
            if token:
                await check("pickup order with token", "create_order", {
                    "store_id": "ST_SH_001",
                    "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                    "pickup_type": "自提",
                    "idempotency_key": "test_order_001",
                    "confirmation_token": token,
                }, ["订单已创建", "南京西路旗舰店", "自提", "应付", "支付链接",
                    "15分钟", "ord_"])

            # Step 3: Try reusing the same token (should fail)
            if token:
                await check("reused token rejected", "create_order", {
                    "store_id": "ST_SH_001",
                    "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                    "pickup_type": "自提",
                    "idempotency_key": "test_order_002",
                    "confirmation_token": token,
                }, ["已使用", "重新"])

            # Step 4: Invalid token
            await check("invalid token rejected", "create_order", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                "pickup_type": "自提",
                "idempotency_key": "test_order_003",
                "confirmation_token": "cfm_invalid_token",
            }, ["无效", "calculate_price"])

            # Step 5: Test idempotency on create_order
            # Get a fresh token first
            calc_result2 = await session.call_tool("calculate_price", arguments={
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D004", "size": "tall", "quantity": 1}],
            })
            calc_text2 = extract_text(calc_result2)
            token2 = None
            for line in calc_text2.split("\n"):
                if "cfm_" in line:
                    import re
                    match = re.search(r"cfm_[a-f0-9]+", line)
                    if match:
                        token2 = match.group(0)
                        break

            if token2:
                await check("delivery order", "create_order", {
                    "store_id": "ST_SH_001",
                    "items": [{"product_code": "D004", "size": "tall", "quantity": 1}],
                    "pickup_type": "外送",
                    "address_id": "addr_f7a3c1e2",
                    "idempotency_key": "test_order_delivery",
                    "confirmation_token": token2,
                }, ["订单已创建", "外送", "配送至", "静安嘉里"])

            # Get another token for coupon order
            calc_result3 = await session.call_tool("calculate_price", arguments={
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                "coupon_code": "AVL_001",
            })
            calc_text3 = extract_text(calc_result3)
            token3 = None
            for line in calc_text3.split("\n"):
                if "cfm_" in line:
                    import re
                    match = re.search(r"cfm_[a-f0-9]+", line)
                    if match:
                        token3 = match.group(0)
                        break

            if token3:
                await check("order with coupon", "create_order", {
                    "store_id": "ST_SH_001",
                    "items": [{"product_code": "D003", "size": "grande", "quantity": 1}],
                    "pickup_type": "堂食",
                    "coupon_code": "AVL_001",
                    "idempotency_key": "test_order_coupon",
                    "confirmation_token": token3,
                }, ["订单已创建", "优惠", "-¥5"])

            await check("invalid store order", "create_order", {
                "store_id": "NONEXIST",
                "items": [{"product_code": "D003", "quantity": 1}],
                "pickup_type": "自提",
                "idempotency_key": "test_order_bad_store",
                "confirmation_token": "cfm_invalid",
            }, ["不存在"])

            print("\n=== order_status ===")
            await check("completed order", "order_status", {"order_id": "TOC_ORD_20260318001"},
                        ["已完成", "南京西路旗舰店", "拿铁", "¥54",
                         "自提", "+5"])
            await check("in-progress order", "order_status", {"order_id": "TOC_ORD_20260320002"},
                        ["制作中", "樱花白巧拿铁", "外送"])
            await check("not found", "order_status", {"order_id": "NONEXIST"},
                        ["未找到"])

            # ════════════════════════════════════════════════════
            # Integration: Full Order Flow (end-to-end with new features)
            # ════════════════════════════════════════════════════
            print("\n=== Integration: Full Order Flow ===")

            # Step 1: Check current time
            total += 1
            result = await session.call_tool("now_time_info", arguments={})
            text = extract_text(result)
            if "当前时间" in text and "周" in text:
                print(f"  PASS  flow step 1: check time")
                passed += 1
            else:
                print(f"  FAIL  flow step 1: check time")
                failed += 1

            # Step 2: Find stores in Shanghai
            total += 1
            result = await session.call_tool("nearby_stores", arguments={"city": "上海"})
            text = extract_text(result)
            if "ST_SH_001" in text and "营业中" in text:
                print(f"  PASS  flow step 2: find stores")
                passed += 1
            else:
                print(f"  FAIL  flow step 2: find stores")
                failed += 1

            # Step 3: Browse menu at selected store
            total += 1
            result = await session.call_tool("browse_menu", arguments={"store_id": "ST_SH_001"})
            text = extract_text(result)
            if "D003" in text and "拿铁" in text:
                print(f"  PASS  flow step 3: browse menu")
                passed += 1
            else:
                print(f"  FAIL  flow step 3: browse menu")
                failed += 1

            # Step 4: Get drink customization
            total += 1
            result = await session.call_tool("drink_detail", arguments={"product_code": "D003"})
            text = extract_text(result)
            if "杯型" in text and "奶类" in text and "甜度" in text:
                print(f"  PASS  flow step 4: drink customization")
                passed += 1
            else:
                print(f"  FAIL  flow step 4: drink customization")
                failed += 1

            # Step 5: Check store coupons
            total += 1
            result = await session.call_tool("store_coupons", arguments={"store_id": "ST_SH_001"})
            text = extract_text(result)
            if "可用优惠券" in text or "暂无" in text:
                print(f"  PASS  flow step 5: check store coupons")
                passed += 1
            else:
                print(f"  FAIL  flow step 5: check store coupons")
                failed += 1

            # Step 6: Calculate price and get confirmation token
            total += 1
            result = await session.call_tool("calculate_price", arguments={
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "venti", "milk": "oat",
                           "extras": ["extra_shot"], "quantity": 2}],
            })
            text = extract_text(result)
            # 32 + 7(venti) + 5(oat) + 6(shot) = 50 per cup, x2 = 100
            flow_token = None
            if "¥100" in text and "应付" in text and "cfm_" in text:
                import re
                match = re.search(r"cfm_[a-f0-9]+", text)
                if match:
                    flow_token = match.group(0)
                print(f"  PASS  flow step 6: calculate price (¥50 x 2 = ¥100 + fees)")
                passed += 1
            else:
                print(f"  FAIL  flow step 6: calculate price")
                print(f"        got: {text[:200]}")
                failed += 1

            # Step 7: Create order with token
            total += 1
            if flow_token:
                result = await session.call_tool("create_order", arguments={
                    "store_id": "ST_SH_001",
                    "items": [{"product_code": "D003", "size": "venti", "milk": "oat",
                               "extras": ["extra_shot"], "quantity": 2}],
                    "pickup_type": "自提",
                    "idempotency_key": "flow_test_order_001",
                    "confirmation_token": flow_token,
                })
                text = extract_text(result)
                if "订单已创建" in text and "支付链接" in text and "ord_" in text:
                    print(f"  PASS  flow step 7: create order with token")
                    passed += 1
                else:
                    print(f"  FAIL  flow step 7: create order")
                    print(f"        got: {text[:200]}")
                    failed += 1
            else:
                print(f"  FAIL  flow step 7: skipped (no token from step 6)")
                failed += 1

            # ════════════════════════════════════════════════════
            # Integration: Stars Redemption Flow
            # ════════════════════════════════════════════════════
            print("\n=== Integration: Stars Redemption Flow ===")

            # Step 1: Check balance
            total += 1
            result = await session.call_tool("my_account", arguments={})
            text = extract_text(result)
            if "142" in text and "金星级" in text:
                print(f"  PASS  stars step 1: check balance (142 stars)")
                passed += 1
            else:
                print(f"  FAIL  stars step 1: check balance")
                failed += 1

            # Step 2: Browse mall
            total += 1
            result = await session.call_tool("stars_mall_products", arguments={})
            text = extract_text(result)
            if "SM_001" in text and "✅" in text and "🔒" in text:
                print(f"  PASS  stars step 2: browse mall (shows affordable/locked)")
                passed += 1
            else:
                print(f"  FAIL  stars step 2: browse mall")
                failed += 1

            # Step 3: Check detail
            total += 1
            result = await session.call_tool("stars_product_detail", arguments={"product_code": "SM_001"})
            text = extract_text(result)
            if "可兑换" in text and "100" in text:
                print(f"  PASS  stars step 3: product detail (affordable)")
                passed += 1
            else:
                print(f"  FAIL  stars step 3: product detail")
                failed += 1

            # Step 4: Redeem with idempotency key
            total += 1
            result = await session.call_tool("stars_redeem", arguments={
                "product_code": "SM_004",
                "idempotency_key": "flow_redeem_001",
            })
            text = extract_text(result)
            if "兑换成功" in text and "30" in text:
                print(f"  PASS  stars step 4: redeem (30 stars spent)")
                passed += 1
            else:
                print(f"  FAIL  stars step 4: redeem")
                failed += 1

            # ════════════════════════════════════════════════════
            # Integration: Discovery + Claim Flow
            # ════════════════════════════════════════════════════
            print("\n=== Integration: Discovery + Claim Flow ===")

            # Step 1: Check campaigns
            total += 1
            result = await session.call_tool("campaign_calendar", arguments={})
            text = extract_text(result)
            if "进行中" in text and "春日樱花季" in text:
                print(f"  PASS  discover step 1: campaigns listed")
                passed += 1
            else:
                print(f"  FAIL  discover step 1")
                failed += 1

            # Step 2: View available coupons
            total += 1
            result = await session.call_tool("available_coupons", arguments={})
            text = extract_text(result)
            if "3 张可领" in text:
                print(f"  PASS  discover step 2: 3 claimable coupons")
                passed += 1
            else:
                print(f"  FAIL  discover step 2")
                failed += 1

            # Step 3: Claim all
            total += 1
            result = await session.call_tool("claim_all_coupons", arguments={})
            text = extract_text(result)
            if "3 张" in text and "成功" in text:
                print(f"  PASS  discover step 3: claimed all 3")
                passed += 1
            else:
                print(f"  FAIL  discover step 3")
                failed += 1

            # Step 4: Verify in my coupons
            total += 1
            result = await session.call_tool("my_coupons", arguments={})
            text = extract_text(result)
            if "我的优惠券" in text:
                print(f"  PASS  discover step 4: my coupons listed")
                passed += 1
            else:
                print(f"  FAIL  discover step 4")
                failed += 1

            # ════════════════════════════════════════════════════
            # Security: Input Validation Tests
            # ════════════════════════════════════════════════════
            print("\n=== Security: Input Validation ===")

            await check("invalid phone format", "create_address", {
                "city": "上海", "address": "测试路1号", "address_detail": "1F",
                "contact_name": "测试", "phone": "123",
            }, ["手机号格式无效"])

            await check("empty address fields", "create_address", {
                "city": "", "address": "测试路1号", "address_detail": "1F",
                "contact_name": "测试", "phone": "13800138000",
            }, ["不完整"])

            await check("invalid size in cart", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "size": "XXXL", "quantity": 1}],
            }, ["杯型", "无效"])

            await check("invalid milk in cart", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "milk": "beer", "quantity": 1}],
            }, ["奶类", "无效"])

            await check("invalid extras in cart", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "extras": ["rocket_fuel"], "quantity": 1}],
            }, ["加料", "无效"])

            await check("quantity too large", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "quantity": 999}],
            }, ["1-99"])

            await check("negative quantity", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "quantity": -1}],
            }, ["1-99"])

            await check("empty items list", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [],
            }, ["不能为空"])

            await check("missing product_code", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"quantity": 1}],
            }, ["缺少 product_code"])

            await check("invalid pickup type", "create_order", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "quantity": 1}],
                "pickup_type": "飞机送",
                "idempotency_key": "test_bad_pickup",
                "confirmation_token": "cfm_dummy",
            }, ["取餐方式", "无效"])

            await check("delivery without address", "create_order", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "quantity": 1}],
                "pickup_type": "外送",
                "idempotency_key": "test_no_addr",
                "confirmation_token": "cfm_dummy",
            }, ["配送地址"])

            await check("too many items", "calculate_price", {
                "store_id": "ST_SH_001",
                "items": [{"product_code": "D003", "quantity": 1}] * 21,
            }, ["最多"])

            # ── Summary ────────────────────────────────────────
            print(f"\n{'='*60}")
            print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")
            print(f"{'='*60}")
            return failed == 0


if __name__ == "__main__":
    ok = asyncio.run(run_tests())
    sys.exit(0 if ok else 1)
