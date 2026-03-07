"""Starbucks MCP CLI — interactive client for the Starbucks MCP Server."""

import asyncio
import json
import sys

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

console = Console()


async def _create_session():
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "starbucks_mcp.server"],
    )
    return stdio_client(server_params)


async def _call_tool(session: ClientSession, tool_name: str, arguments: dict) -> str:
    result = await session.call_tool(tool_name, arguments=arguments)
    parts = []
    for block in result.content:
        if hasattr(block, "text"):
            parts.append(block.text)
    return "\n".join(parts)


async def _run_single(tool_name: str, arguments: dict):
    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await _call_tool(session, tool_name, arguments)
            console.print(Markdown(result))


async def _interactive():
    console.print(Panel.fit(
        "[bold green]Starbucks MCP CLI[/bold green] (B2B Open Platform)\n"
        "基于真实 openapi.starbucks.com.cn 接口映射\n"
        "输入 help 查看命令，quit 退出",
        title="sbux",
    ))

    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            console.print(f"[dim]已连接，可用 Tools ({len(tool_names)}): {', '.join(tool_names)}[/dim]\n")

            commands = {
                "member": ("member_query", "查询会员 - member <手机号/openId/sbuxId>"),
                "tier": ("member_tier", "会员等级 - tier <sbuxId>"),
                "benefits": ("member_benefits", "权益状态 - benefits <sbuxId>"),
                "coupons": ("member_benefit_list", "券列表 - coupons <sbuxId>"),
                "coupon-query": ("coupon_query", "订单券码 - coupon-query <orderId>"),
                "coupon": ("coupon_detail", "券码详情 - coupon <couponCode>"),
                "equity": ("equity_query", "权益查询 - equity <orderId>"),
                "equity-detail": ("equity_detail", "权益详情 - equity-detail <orderId>"),
                "assets": ("assets_list", "客户资产 - assets <sbuxId>"),
                "pay": ("cashier_pay_query", "支付查询 - pay <payToken>"),
            }

            while True:
                try:
                    user_input = console.input("[bold cyan]sbux>[/bold cyan] ").strip()
                except (EOFError, KeyboardInterrupt):
                    console.print("\n[dim]再见！[/dim]")
                    break

                if not user_input:
                    continue
                if user_input in ("quit", "exit", "q"):
                    console.print("[dim]再见！[/dim]")
                    break

                if user_input == "help":
                    table = Table(title="可用命令")
                    table.add_column("命令", style="cyan")
                    table.add_column("说明")
                    for cmd, (_, desc) in commands.items():
                        table.add_row(cmd, desc)
                    table.add_row("tools", "列出所有 MCP Tools")
                    table.add_row("data", "查看 Demo 测试数据")
                    table.add_row("help", "显示此帮助")
                    table.add_row("quit", "退出")
                    console.print(table)
                    continue

                if user_input == "tools":
                    for t in tools_result.tools:
                        desc = t.description or ""
                        first_line = desc.split("\n")[0]
                        console.print(f"[cyan]{t.name}[/cyan]: {first_line}")
                    console.print()
                    continue

                if user_input == "data":
                    console.print(Panel(
                        "[bold]Demo 测试数据[/bold]\n\n"
                        "[cyan]会员:[/cyan]\n"
                        "  SBUX_M_100001 (张三, 金星, 138****1234)\n"
                        "  SBUX_M_100002 (李四, 银星, 139****5678)\n"
                        "  SBUX_M_100003 (王五, 钻星, 137****9012)\n\n"
                        "[cyan]券码:[/cyan]\n"
                        "  SBX20260301A001 (未使用, 中杯饮品券)\n"
                        "  SBX20260301A002 (已使用)\n"
                        "  SBX20260215B001 (买一送一券)\n\n"
                        "[cyan]订单号:[/cyan]\n"
                        "  ORD_2026030100001 (春季活动)\n"
                        "  ORD_2026021500001 (新年活动)\n\n"
                        "[cyan]权益订单:[/cyan]\n"
                        "  EQ_2026030100001, EQ_2026030100002, EQ_2026021500001\n\n"
                        "[cyan]支付令牌:[/cyan]\n"
                        "  PAY_TOKEN_001 (成功) PAY_TOKEN_002 (处理中) PAY_TOKEN_003 (失败)",
                        title="Test Data",
                    ))
                    continue

                parts = user_input.split()
                cmd = parts[0]
                args = parts[1:]

                if cmd not in commands:
                    console.print(f"[red]未知命令: {cmd}[/red]，输入 help 查看帮助。")
                    continue

                tool_name = commands[cmd][0]
                arguments: dict = {}

                try:
                    if cmd == "member":
                        if not args:
                            console.print("[red]请提供手机号/openId/sbuxId[/red]")
                            continue
                        v = args[0]
                        if v.startswith("SBUX_"):
                            arguments["sbux_id"] = v
                        elif v.startswith("o"):
                            arguments["open_id"] = v
                        else:
                            arguments["mobile"] = v
                    elif cmd in ("tier", "benefits", "coupons", "assets"):
                        if not args:
                            console.print(f"[red]请提供 sbuxId，如: {cmd} SBUX_M_100001[/red]")
                            continue
                        arguments["sbux_id"] = args[0]
                    elif cmd in ("coupon-query", "equity", "equity-detail"):
                        if not args:
                            console.print(f"[red]请提供订单号[/red]")
                            continue
                        arguments["order_id"] = args[0]
                    elif cmd == "coupon":
                        if not args:
                            console.print("[red]请提供券码，如: coupon SBX20260301A001[/red]")
                            continue
                        arguments["coupon_code"] = args[0]
                    elif cmd == "pay":
                        if not args:
                            console.print("[red]请提供 payToken，如: pay PAY_TOKEN_001[/red]")
                            continue
                        arguments["pay_token"] = args[0]

                    result = await _call_tool(session, tool_name, arguments)
                    console.print()
                    console.print(Markdown(result))
                    console.print()
                except Exception as e:
                    console.print(f"[red]错误: {e}[/red]")


async def _demo():
    console.print(Panel.fit(
        "[bold green]Starbucks MCP Server Demo[/bold green]\n"
        "模拟 B2B 场景：会员查询 → 等级 → 权益 → 券码 → 资产 → 支付",
        title="Demo",
    ))

    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            steps = [
                ("member_query", {"mobile": "138****1234"},
                 "Step 1: 查询会员 (POST /crmadapter/account/query)"),
                ("member_tier", {"sbux_id": "SBUX_M_100001"},
                 "Step 2: 查询等级详情 (POST /crmadapter/account/memberTier)"),
                ("member_benefits", {"sbux_id": "SBUX_M_100001"},
                 "Step 3: 查询 8 项权益状态 (POST /crmadapter/customers/getBenefits)"),
                ("member_benefit_list", {"sbux_id": "SBUX_M_100001"},
                 "Step 4: 查询券列表 (POST /crmadapter/asset/coupon/getBenefitList)"),
                ("coupon_query", {"order_id": "ORD_2026030100001"},
                 "Step 5: 查询订单券码 (POST /coupon/query)"),
                ("coupon_detail", {"coupon_code": "SBX20260301A001"},
                 "Step 6: 查询券码详情 (POST /coupon/detail)"),
                ("equity_detail", {"order_id": "EQ_2026030100001"},
                 "Step 7: 查询权益详情 (POST /equity/detail)"),
                ("assets_list", {"sbux_id": "SBUX_M_100001"},
                 "Step 8: 查询客户全部资产 (POST /assets/list)"),
                ("cashier_pay_query", {"pay_token": "PAY_TOKEN_001"},
                 "Step 9: 查询支付状态 (POST /cashier/payQuery)"),
            ]

            for tool_name, arguments, description in steps:
                console.print(f"\n[bold yellow]{'='*60}[/bold yellow]")
                console.print(f"[bold]{description}[/bold]")
                console.print(f"[dim]Tool: {tool_name}({json.dumps(arguments, ensure_ascii=False)})[/dim]")
                console.print(f"[bold yellow]{'='*60}[/bold yellow]\n")

                result = await _call_tool(session, tool_name, arguments)
                console.print(Markdown(result))
                console.print()

    console.print("[bold green]Demo 完成！所有 Phase 1 只读 Tool 均已验证。[/bold green]")


@click.group()
def cli():
    """Starbucks MCP CLI — 星巴克 B2B 开放平台 MCP 客户端"""
    pass


@cli.command()
def interactive():
    """启动交互式命令行"""
    asyncio.run(_interactive())


@cli.command()
def demo():
    """运行完整 Demo 流程（9 步）"""
    asyncio.run(_demo())


@cli.command()
@click.argument("identifier")
def member(identifier):
    """查询会员信息（手机号/openId/sbuxId）"""
    if identifier.startswith("SBUX_"):
        args = {"sbux_id": identifier}
    elif identifier.startswith("o"):
        args = {"open_id": identifier}
    else:
        args = {"mobile": identifier}
    asyncio.run(_run_single("member_query", args))


@cli.command()
@click.argument("sbux_id")
def tier(sbux_id):
    """查询会员等级"""
    asyncio.run(_run_single("member_tier", {"sbux_id": sbux_id}))


@cli.command()
@click.argument("sbux_id")
def benefits(sbux_id):
    """查询会员权益状态"""
    asyncio.run(_run_single("member_benefits", {"sbux_id": sbux_id}))


@cli.command()
@click.argument("sbux_id")
def assets(sbux_id):
    """查询客户资产"""
    asyncio.run(_run_single("assets_list", {"sbux_id": sbux_id}))


@cli.command()
@click.argument("coupon_code")
def coupon(coupon_code):
    """查询券码详情"""
    asyncio.run(_run_single("coupon_detail", {"coupon_code": coupon_code}))


@cli.command()
@click.argument("order_id")
def equity(order_id):
    """查询权益详情"""
    asyncio.run(_run_single("equity_detail", {"order_id": order_id}))


@cli.command()
@click.argument("pay_token")
def pay(pay_token):
    """查询支付状态"""
    asyncio.run(_run_single("cashier_pay_query", {"pay_token": pay_token}))


if __name__ == "__main__":
    cli()
