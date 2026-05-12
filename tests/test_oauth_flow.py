"""End-to-end tests for Stage 1 OAuth flow.

Spins up the composite Starlette + FastMCP app via uvicorn on a random port,
drives the OAuth flow with httpx, then calls MCP tools via the real
streamable HTTP client. Covers the 8 scenarios from the plan §11.

Run:
    uv run python tests/test_oauth_flow.py
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys
import threading
import time
import traceback
from typing import Any

import httpx
import uvicorn
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from coffee_mcp.auth.http_app import build_app
from coffee_mcp.brand_config import load_brand_adapter, load_brand_config


# ---------------------------------------------------------------------------
# In-process uvicorn helper
# ---------------------------------------------------------------------------


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _ServerThread:
    def __init__(self, app, host: str, port: int):
        cfg = uvicorn.Config(app, host=host, port=port, log_level="warning",
                             lifespan="on")
        self.server = uvicorn.Server(cfg)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.host = host
        self.port = port

    def start(self) -> None:
        self.thread.start()
        deadline = time.time() + 5
        while time.time() < deadline:
            if self.server.started:
                return
            time.sleep(0.05)
        raise RuntimeError("uvicorn did not start in time")

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def _fresh_server() -> tuple[_ServerThread, dict]:
    """Per-test fresh server (new port, new app, new session store)."""
    port = _free_port()
    base = f"http://127.0.0.1:{port}"

    config = load_brand_config("coffee_company")
    assert config.oauth is not None
    oc = config.oauth
    oc.issuer = f"{base}/mock-as"
    oc.authorization_endpoint = f"{base}/mock-as/authorize"
    oc.token_endpoint = f"{base}/mock-as/token"
    oc.redirect_uri = f"{base}/oauth/callback"
    oc.h5_login_url = f"{base}/h5/login"

    adapter = load_brand_adapter(config)
    app = build_app(config, adapter)
    srv = _ServerThread(app, "127.0.0.1", port)
    srv.start()
    ctx = {
        "base": base,
        "app": app,
        "store": app.state.session_store,
        "mock_as": app.state.mock_as,
        "config": config,
    }
    return srv, ctx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_hidden(html: str, name: str) -> str:
    needle = f'name="{name}" value="'
    idx = html.find(needle)
    if idx < 0:
        return ""
    start = idx + len(needle)
    end = html.find('"', start)
    return html[start:end]


async def _walk_oauth_flow(base: str, scope: str | None = None) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        r = await client.get(f"{base}/oauth/session/new")
        r.raise_for_status()
        session_id = r.json()["session_id"]

        params = {"session_id": session_id}
        if scope:
            params["scope"] = scope
        r = await client.get(f"{base}/oauth/login_start",
                             params=params, follow_redirects=False)
        assert r.status_code == 302, r.text
        authorize_url = r.headers["location"]

        r = await client.get(authorize_url, follow_redirects=False)
        assert r.status_code == 302, r.text
        h5_url = r.headers["location"]

        r = await client.get(h5_url)
        r.raise_for_status()
        body = r.text
        form = {k: _extract_hidden(body, k) for k in
                ("state", "scope", "code_challenge", "redirect_uri")}

        r = await client.post(f"{base}/h5/login/submit", data={
            **form,
            "phone": "13800001234",
            "otp": "000000",
        }, follow_redirects=False)
        assert r.status_code == 302, r.text
        callback_url = r.headers["location"]

        r = await client.get(callback_url, follow_redirects=False)
        assert r.status_code == 302, r.text

        r = await client.get(f"{base}/oauth/session/{session_id}/token")
        r.raise_for_status()
        tok = r.json()
        return {
            "session_id": session_id,
            "access_token": tok["access_token"],
            "scope_str": tok["scope"],
        }


async def _step_up(base: str, session_id: str, tool: str) -> None:
    async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
        r = await client.get(f"{base}/h5/step_up",
                             params={"session_id": session_id,
                                     "tool": tool, "confirm": "yes"})
        r.raise_for_status()


async def _call_tool(base: str, name: str, args: dict | None = None,
                     token: str | None = None) -> str:
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    def _factory(*, headers=None, timeout=None, auth=None):
        kwargs = {"trust_env": False, "headers": headers}
        if timeout is not None:
            kwargs["timeout"] = timeout
        if auth is not None:
            kwargs["auth"] = auth
        return httpx.AsyncClient(**kwargs)
    async with streamablehttp_client(f"{base}/mcp", headers=headers,
                                     httpx_client_factory=_factory) as (
            read, write, _get_sid):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(name, args or {})
            parts = []
            for item in (result.content or []):
                if hasattr(item, "text"):
                    parts.append(item.text)
            return "\n".join(parts)


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------


class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.errors: list[tuple[str, str]] = []

    def report(self) -> int:
        total = self.passed + self.failed
        print(f"\n{'='*60}")
        print(f"  {self.passed}/{total} passed")
        if self.errors:
            print(f"\nFailures:")
            for name, err in self.errors:
                print(f"\n  ✗ {name}")
                for line in err.splitlines():
                    print(f"      {line}")
        print(f"{'='*60}")
        return 0 if self.failed == 0 else 1


async def run_one(name: str, coro_factory, result: TestResult) -> None:
    srv, ctx = _fresh_server()
    print(f"  • {name} ...", end=" ", flush=True)
    try:
        await coro_factory(ctx)
        print("OK")
        result.passed += 1
    except AssertionError as e:
        print("FAIL")
        result.failed += 1
        result.errors.append((name, traceback.format_exc()))
    except Exception:
        print("ERROR")
        result.failed += 1
        result.errors.append((name, traceback.format_exc()))
    finally:
        srv.stop()


# ---------------------------------------------------------------------------
# The 8 test cases
# ---------------------------------------------------------------------------


async def t_l0_tool_works_without_token(ctx):
    text = await _call_tool(ctx["base"], "now_time_info")
    assert "continue_url" not in text, f"unexpected continue_url: {text}"
    assert len(text) > 0


async def t_l1_missing_token_returns_continue_url(ctx):
    text = await _call_tool(ctx["base"], "my_account")
    body = json.loads(text)
    assert body["authenticated"] is False
    assert "/oauth/login_start" in body["continue_url"]
    assert body["required_scope"] == "read:account"


async def t_mock_as_happy_path(ctx):
    flow = await _walk_oauth_flow(ctx["base"])
    assert flow["access_token"].startswith("mock_at_")
    sess = ctx["store"].get(flow["session_id"])
    assert sess is not None
    assert sess.auth_level.value == "otp_verified"
    for s in ("read:account", "read:orders", "read:rewards"):
        assert s in sess.scope, f"missing default scope {s}: {sess.scope}"


async def t_l1_valid_token_succeeds(ctx):
    flow = await _walk_oauth_flow(ctx["base"])
    text = await _call_tool(ctx["base"], "my_account",
                            token=flow["access_token"])
    assert "continue_url" not in text, text
    assert len(text) > 20


async def t_l1_expired_token_returns_continue_url(ctx):
    flow = await _walk_oauth_flow(ctx["base"])
    ok = await _call_tool(ctx["base"], "my_account", token=flow["access_token"])
    assert "continue_url" not in ok

    # Expire the token in both the session and the mock AS
    sess = ctx["store"].get(flow["session_id"])
    sess.token_expires_at = 0.0
    ctx["mock_as"]._tokens.pop(flow["access_token"], None)

    text = await _call_tool(ctx["base"], "my_account", token=flow["access_token"])
    body = json.loads(text)
    assert body["authenticated"] is False


async def t_l3_without_step_up_returns_step_up_url(ctx):
    flow = await _walk_oauth_flow(
        ctx["base"], scope="read:account read:orders write:orders")
    sess = ctx["store"].get(flow["session_id"])
    assert "write:orders" in sess.scope, sess.scope

    text = await _call_tool(
        ctx["base"], "create_order",
        args={
            "store_id": "S001",
            "items": [{"product_code": "D001", "quantity": 1}],
            "pickup_type": "自提",
            "idempotency_key": "test-idem-001",
            "confirmation_token": "cfm_dummy",
        },
        token=flow["access_token"],
    )
    body = json.loads(text)
    assert body.get("step_up_required") is True, body
    assert "/h5/step_up" in body["continue_url"]


async def t_l3_after_step_up_passes_auth_guard(ctx):
    flow = await _walk_oauth_flow(
        ctx["base"], scope="read:account read:orders write:orders")
    await _step_up(ctx["base"], flow["session_id"], "create_order")
    sess = ctx["store"].get(flow["session_id"])
    assert sess.auth_level.value == "step_up_verified"

    text = await _call_tool(
        ctx["base"], "create_order",
        args={
            "store_id": "S001",
            "items": [{"product_code": "D001", "quantity": 1}],
            "pickup_type": "自提",
            "idempotency_key": "test-idem-002",
            "confirmation_token": "cfm_dummy",
        },
        token=flow["access_token"],
    )
    # Auth guard passed → we now see business-layer errors (not step-up JSON)
    assert "step_up_required" not in text, text
    assert "确认令牌" in text or "门店" in text or "订单" in text or "无效" in text


async def t_insufficient_scope_returns_elevation(ctx):
    flow = await _walk_oauth_flow(ctx["base"], scope="read:account")
    text = await _call_tool(ctx["base"], "my_orders",
                            token=flow["access_token"])
    body = json.loads(text)
    assert body.get("missing_scope") == "read:orders", body
    assert "/oauth/login_start" in body["continue_url"]
    assert "scope=read:orders" in body["continue_url"]


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


async def main() -> int:
    tests = [
        ("L0 tool works without token",            t_l0_tool_works_without_token),
        ("L1 missing token → continue_url",        t_l1_missing_token_returns_continue_url),
        ("Mock AS happy path",                     t_mock_as_happy_path),
        ("L1 valid token succeeds",                t_l1_valid_token_succeeds),
        ("L1 expired token → continue_url",        t_l1_expired_token_returns_continue_url),
        ("L3 without step-up → step_up url",       t_l3_without_step_up_returns_step_up_url),
        ("L3 after step-up passes guard",          t_l3_after_step_up_passes_auth_guard),
        ("Insufficient scope → elevation url",     t_insufficient_scope_returns_elevation),
    ]
    print(f"\nRunning {len(tests)} OAuth E2E tests against mock AS\n")
    result = TestResult()
    for name, fn in tests:
        await run_one(name, fn, result)
    return result.report()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
