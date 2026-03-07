"""Starbucks MCP CLI - interactive client for the Starbucks MCP Server."""

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

DEFAULT_API_KEY = "demo-key-001"
SERVER_CMD = [sys.executable, "-m", "starbucks_mcp.server"]


async def _create_session():
    """Create an MCP client session connected to the starbucks server."""
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
    """Connect, call one tool, print result, disconnect."""
    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await _call_tool(session, tool_name, arguments)
            console.print(Markdown(result))


async def _interactive(api_key: str):
    """Interactive REPL mode."""
    console.print(Panel.fit(
        "[bold green]Starbucks MCP CLI[/bold green]\n"
        f"API Key: {api_key}\n"
        "输入命令与星巴克 MCP Server 交互，输入 help 查看可用命令，输入 quit 退出。",
        title="sbux",
    ))

    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            # List available tools
            tools_result = await session.list_tools()
            tool_names = [t.name for t in tools_result.tools]
            console.print(f"[dim]已连接，可用 Tools: {', '.join(tool_names)}[/dim]\n")

            commands = {
                "stores": ("search_nearby_stores", "搜索门店 - stores [城市] [关键词]"),
                "store": ("get_store_detail", "门店详情 - store <门店编号>"),
                "menu": ("get_menu", "查看菜单 - menu [分类]"),
                "product": ("get_product_detail", "产品详情 - product <名称或ID>"),
                "inventory": ("check_store_inventory", "查库存 - inventory <门店编号> [产品ID]"),
                "promos": ("get_promotions", "促销活动 - promos"),
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
                    table.add_row("help", "显示此帮助")
                    table.add_row("quit", "退出")
                    console.print(table)
                    continue

                if user_input == "tools":
                    for t in tools_result.tools:
                        console.print(f"[cyan]{t.name}[/cyan]: {t.description[:80]}")
                    console.print()
                    continue

                parts = user_input.split()
                cmd = parts[0]
                args = parts[1:]

                if cmd not in commands:
                    console.print(f"[red]未知命令: {cmd}[/red]，输入 help 查看帮助。")
                    continue

                tool_name = commands[cmd][0]
                arguments: dict = {"api_key": api_key}

                try:
                    if cmd == "stores":
                        if args:
                            arguments["city"] = args[0]
                        if len(args) > 1:
                            arguments["keyword"] = args[1]
                    elif cmd == "store":
                        if not args:
                            console.print("[red]请提供门店编号，例如: store SH-LJZ-001[/red]")
                            continue
                        arguments["store_id"] = args[0]
                    elif cmd == "menu":
                        if args:
                            arguments["category"] = args[0]
                    elif cmd == "product":
                        if not args:
                            console.print("[red]请提供产品名称或ID，例如: product 拿铁[/red]")
                            continue
                        value = " ".join(args)
                        if value.startswith(("ESP-", "CB-", "FRAP-", "TEA-", "SEA-", "FOOD-")):
                            arguments["product_id"] = value
                        else:
                            arguments["name"] = value
                    elif cmd == "inventory":
                        if not args:
                            console.print("[red]请提供门店编号，例如: inventory SH-LJZ-001[/red]")
                            continue
                        arguments["store_id"] = args[0]
                        if len(args) > 1:
                            arguments["product_id"] = args[1]
                    # promos has no extra args

                    result = await _call_tool(session, tool_name, arguments)
                    console.print()
                    console.print(Markdown(result))
                    console.print()
                except Exception as e:
                    console.print(f"[red]错误: {e}[/red]")


async def _demo(api_key: str):
    """Run a scripted demo showing all tools."""
    console.print(Panel.fit(
        "[bold green]Starbucks MCP Server Demo[/bold green]\n"
        "模拟完整的门店查询 → 菜单浏览 → 产品详情 → 库存检查流程",
        title="Demo",
    ))

    async with (await _create_session()) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()

            steps = [
                ("search_nearby_stores", {"api_key": api_key, "city": "上海"}, "Step 1: 搜索上海的星巴克门店"),
                ("get_store_detail", {"api_key": api_key, "store_id": "SH-LJZ-001"}, "Step 2: 查看陆家嘴门店详情"),
                ("get_menu", {"api_key": api_key, "category": "seasonal"}, "Step 3: 浏览当季限定菜单"),
                ("get_product_detail", {"api_key": api_key, "name": "拿铁"}, "Step 4: 查看拿铁的详细信息"),
                ("check_store_inventory", {"api_key": api_key, "store_id": "SH-LJZ-001"}, "Step 5: 查询陆家嘴店库存"),
                ("get_promotions", {"api_key": api_key}, "Step 6: 查看当前促销活动"),
            ]

            for tool_name, arguments, description in steps:
                console.print(f"\n[bold yellow]{'='*60}[/bold yellow]")
                console.print(f"[bold]{description}[/bold]")
                console.print(f"[dim]Tool: {tool_name}({json.dumps({k:v for k,v in arguments.items() if k != 'api_key'}, ensure_ascii=False)})[/dim]")
                console.print(f"[bold yellow]{'='*60}[/bold yellow]\n")

                result = await _call_tool(session, tool_name, arguments)
                console.print(Markdown(result))
                console.print()

    console.print("[bold green]Demo 完成！[/bold green]")


@click.group()
def cli():
    """Starbucks MCP CLI - 星巴克 MCP 服务客户端"""
    pass


@cli.command()
@click.option("--key", default=DEFAULT_API_KEY, help="API Key (default: demo-key-001)")
def interactive(key):
    """启动交互式命令行"""
    asyncio.run(_interactive(key))


@cli.command()
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def demo(key):
    """运行完整 Demo 流程"""
    asyncio.run(_demo(key))


@cli.command()
@click.argument("city", required=False)
@click.argument("keyword", required=False)
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def stores(city, keyword, key):
    """搜索门店"""
    args = {"api_key": key}
    if city:
        args["city"] = city
    if keyword:
        args["keyword"] = keyword
    asyncio.run(_run_single("search_nearby_stores", args))


@cli.command()
@click.argument("store_id")
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def store(store_id, key):
    """查看门店详情"""
    asyncio.run(_run_single("get_store_detail", {"api_key": key, "store_id": store_id}))


@cli.command()
@click.argument("category", required=False)
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def menu(category, key):
    """查看菜单"""
    args = {"api_key": key}
    if category:
        args["category"] = category
    asyncio.run(_run_single("get_menu", args))


@cli.command()
@click.argument("name")
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def product(name, key):
    """查看产品详情"""
    asyncio.run(_run_single("get_product_detail", {"api_key": key, "name": name}))


@cli.command()
@click.argument("store_id")
@click.argument("product_id", required=False)
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def inventory(store_id, product_id, key):
    """查询门店库存"""
    args = {"api_key": key, "store_id": store_id}
    if product_id:
        args["product_id"] = product_id
    asyncio.run(_run_single("check_store_inventory", args))


@cli.command()
@click.option("--key", default=DEFAULT_API_KEY, help="API Key")
def promos(key):
    """查看促销活动"""
    asyncio.run(_run_single("get_promotions", {"api_key": key}))


if __name__ == "__main__":
    cli()
