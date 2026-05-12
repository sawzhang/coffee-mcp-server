"""Starlette routes for OAuth 2.1 + mock-AS H5 demo pages.

Mounted by auth/http_app.py alongside FastMCP's streamable_http_app().
"""

from __future__ import annotations

import json
import urllib.parse
from typing import Any

import httpx
from starlette.requests import Request
from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)
from starlette.routing import Route

from ..brand_config import BrandConfig
from .scopes import DEFAULT_SCOPES, ALL_SCOPES
from .session_store import (
    SessionStore,
    generate_pkce_pair,
    generate_state,
)


def build_oauth_routes(config: BrandConfig,
                       store: SessionStore,
                       mock_as: Any | None) -> list[Route]:
    """Build Starlette routes from the brand's OAuth config + optional mock AS."""

    oauth = config.oauth
    if oauth is None:
        return []

    base_audience = oauth.audience

    # ---------------- well-known metadata ----------------

    async def prm_metadata(request: Request) -> JSONResponse:
        """RFC 9728 — Protected Resource Metadata."""
        resource = base_audience or str(request.url_for("mcp_root_placeholder")
                                        if False else _base_url(request) + "/mcp")
        return JSONResponse({
            "resource": resource,
            "authorization_servers": [oauth.issuer],
            "scopes_supported": oauth.scopes_supported or sorted(ALL_SCOPES),
            "bearer_methods_supported": ["header"],
        })

    async def as_metadata(request: Request) -> JSONResponse:
        """RFC 8414 — Authorization Server Metadata. For mock AS we return inline."""
        if mock_as is not None:
            return JSONResponse(mock_as.well_known(_base_url(request)))
        # Real brand AS — minimal passthrough hint
        return JSONResponse({
            "issuer": oauth.issuer,
            "authorization_endpoint": oauth.authorization_endpoint,
            "token_endpoint": oauth.token_endpoint,
            "code_challenge_methods_supported": ["S256"],
            "grant_types_supported": ["authorization_code"],
            "response_types_supported": ["code"],
            "scopes_supported": oauth.scopes_supported or sorted(ALL_SCOPES),
        })

    # ---------------- session bootstrap (test/dev helper) ----------------

    async def session_new(request: Request) -> JSONResponse:
        session = store.create()
        return JSONResponse({"session_id": session.session_id})

    async def session_token(request: Request) -> JSONResponse:
        sid = request.path_params["session_id"]
        s = store.get(sid)
        if not s or not s.member_token:
            return JSONResponse({"error": "no_token"}, status_code=404)
        return JSONResponse({
            "access_token": s.member_token,
            "scope": " ".join(sorted(s.scope)),
            "auth_level": s.auth_level.value,
        })

    # ---------------- /oauth/login_start ----------------

    async def login_start(request: Request) -> Response:
        sid = request.query_params.get("session_id")
        if not sid:
            return _bad_request("missing session_id")
        session = store.get(sid)
        if not session:
            session = store.create()
            sid = session.session_id

        scope_req = request.query_params.get("scope")
        scope_str = scope_req or " ".join(sorted(DEFAULT_SCOPES))

        verifier, challenge = generate_pkce_pair()
        state = generate_state()
        store.attach_pkce(sid, verifier, state, requested_scope=scope_str)

        params = {
            "response_type": "code",
            "client_id": "coffee-mcp-rs",
            "redirect_uri": oauth.redirect_uri,
            "scope": scope_str,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if base_audience:
            params["resource"] = base_audience
        url = f"{oauth.authorization_endpoint}?{urllib.parse.urlencode(params)}"
        return RedirectResponse(url, status_code=302)

    # ---------------- /oauth/callback ----------------

    async def oauth_callback(request: Request) -> Response:
        code = request.query_params.get("code")
        state = request.query_params.get("state")
        if not code or not state:
            return _bad_request("missing code or state")
        session = store.find_by_state(state)
        if not session:
            return _bad_request("unknown state")

        # Exchange code -> token
        if mock_as is not None:
            token_resp = mock_as.exchange_code(code, session.pkce_verifier or "")
            if token_resp is None:
                return _bad_request("code exchange failed")
        else:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(oauth.token_endpoint, data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": oauth.redirect_uri,
                    "client_id": "coffee-mcp-rs",
                    "code_verifier": session.pkce_verifier or "",
                })
            if resp.status_code != 200:
                return _bad_request(f"token endpoint returned {resp.status_code}")
            token_resp = resp.json()

        access_token = token_resp["access_token"]
        scope_str = token_resp.get("scope", "") or session.requested_scope or ""
        scope_set = set(scope_str.split()) if scope_str else set(DEFAULT_SCOPES)
        expires_in = int(token_resp.get("expires_in", 3600))

        # For mock AS we already know the member; for real AS the access token
        # introspection in toc_server resolves member_id from JWT sub claim.
        member_id = (
            mock_as.canned_member_id
            if mock_as is not None
            else token_resp.get("member_id") or token_resp.get("sub", "unknown")
        )
        store.upgrade(session.session_id, member_id, scope_set, access_token,
                      expires_in)

        done_url = f"{_base_url(request)}/h5/done?session_id={session.session_id}"
        return RedirectResponse(done_url, status_code=302)

    # ---------------- H5 demo pages (mock AS only) ----------------

    async def h5_login(request: Request) -> HTMLResponse:
        state = request.query_params.get("state", "")
        scope = request.query_params.get("scope", " ".join(sorted(DEFAULT_SCOPES)))
        challenge = request.query_params.get("code_challenge", "")
        redirect_uri = request.query_params.get("redirect_uri", oauth.redirect_uri)
        scope_list_html = "".join(
            f"<li>✓ {_scope_label(s)}</li>" for s in scope.split()
        )
        agent_hint = request.query_params.get("client_id", "coffee-mcp client")
        html = _LOGIN_PAGE_TEMPLATE.format(
            brand_name=config.brand_name,
            agent=agent_hint,
            state=state,
            scope=scope,
            challenge=challenge,
            redirect_uri=redirect_uri,
            scope_list=scope_list_html or "<li>read-only</li>",
        )
        return HTMLResponse(html)

    async def h5_login_submit(request: Request) -> Response:
        form = await request.form()
        state = form.get("state") or ""
        scope = (form.get("scope") or "").split()
        challenge = form.get("code_challenge") or ""
        redirect_uri = form.get("redirect_uri") or oauth.redirect_uri
        if not mock_as:
            return _bad_request("mock AS not enabled")
        if not state or not challenge:
            return _bad_request("missing state or challenge")
        code = mock_as.issue_code(state=state, code_challenge=challenge,
                                  scope=set(scope))
        url = f"{redirect_uri}?code={code}&state={state}"
        return RedirectResponse(url, status_code=302)

    async def h5_step_up(request: Request) -> Response:
        sid = request.query_params.get("session_id")
        tool = request.query_params.get("tool", "")
        confirm = request.query_params.get("confirm")
        if not sid:
            return _bad_request("missing session_id")
        if confirm == "yes":
            store.mark_step_up(sid, ttl=300)
            return HTMLResponse(
                f"<h2>已确认 step-up</h2><p>5 分钟内可执行高敏操作：<code>{tool}</code></p>"
                f"<p>回到对话再次发起即可。</p>"
            )
        html = f"""
        <!doctype html><html><body style="font-family:sans-serif;max-width:480px;margin:40px auto">
        <h2>{config.brand_name} · 二次确认</h2>
        <p>即将执行高敏操作：<b>{tool}</b></p>
        <p>请确认这是你本人的操作。</p>
        <p>
          <a href="?session_id={sid}&tool={tool}&confirm=yes"
             style="display:inline-block;padding:10px 24px;background:#0a7;color:#fff;text-decoration:none;border-radius:4px">
            确认
          </a>
          &nbsp;
          <a href="/h5/done?session_id={sid}"
             style="display:inline-block;padding:10px 24px;border:1px solid #ccc;text-decoration:none;border-radius:4px">
            取消
          </a>
        </p>
        <p style="color:#888;font-size:12px;margin-top:24px">⚠️ 本对话由 AI 协助完成,请核对订单信息</p>
        </body></html>
        """
        return HTMLResponse(html)

    async def h5_done(request: Request) -> HTMLResponse:
        return HTMLResponse(
            "<h2>授权完成</h2><p>请回到对话窗口,重新询问即可。</p>"
            "<p style='color:#888;font-size:12px'>⚠️ 本对话由 AI 协助完成,请核对订单信息后再支付</p>"
        )

    routes = [
        Route("/.well-known/oauth-protected-resource", prm_metadata, methods=["GET"]),
        Route("/.well-known/oauth-authorization-server", as_metadata, methods=["GET"]),
        Route("/oauth/session/new", session_new, methods=["GET", "POST"]),
        Route("/oauth/session/{session_id}/token", session_token, methods=["GET"]),
        Route("/oauth/login_start", login_start, methods=["GET"]),
        Route("/oauth/callback", oauth_callback, methods=["GET"]),
        Route("/h5/done", h5_done, methods=["GET"]),
        Route("/h5/step_up", h5_step_up, methods=["GET"]),
    ]

    if mock_as is not None:
        async def mock_authorize(request: Request) -> Response:
            """Mock AS /authorize — just bounces to the H5 login page."""
            qs = urllib.parse.urlencode(dict(request.query_params))
            return RedirectResponse(f"{_base_url(request)}/h5/login?{qs}",
                                    status_code=302)

        async def mock_token(request: Request) -> JSONResponse:
            form = await request.form()
            grant_type = form.get("grant_type")
            if grant_type != "authorization_code":
                return JSONResponse({"error": "unsupported_grant_type"}, status_code=400)
            code = form.get("code") or ""
            verifier = form.get("code_verifier") or ""
            resp = mock_as.exchange_code(code, verifier)
            if resp is None:
                return JSONResponse({"error": "invalid_grant"}, status_code=400)
            return JSONResponse(resp)

        async def mock_well_known(request: Request) -> JSONResponse:
            return JSONResponse(mock_as.well_known(_base_url(request)))

        routes.extend([
            Route("/mock-as/authorize", mock_authorize, methods=["GET"]),
            Route("/mock-as/token", mock_token, methods=["POST"]),
            Route("/mock-as/.well-known/openid-configuration",
                  mock_well_known, methods=["GET"]),
            Route("/h5/login", h5_login, methods=["GET"]),
            Route("/h5/login/submit", h5_login_submit, methods=["POST"]),
        ])

    return routes


# ---------------- helpers ----------------

def _base_url(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


def _bad_request(msg: str) -> JSONResponse:
    return JSONResponse({"error": "bad_request", "message": msg}, status_code=400)


_SCOPE_LABELS = {
    "read:account":    "查看会员等级、星星余额",
    "read:orders":     "查看历史订单",
    "read:rewards":    "查看可用优惠券与活动",
    "write:addresses": "新增配送地址",
    "write:orders":    "下单(支付仍走 App)",
    "redeem:stars":    "兑换星礼包/积分商品",
}


def _scope_label(scope: str) -> str:
    return _SCOPE_LABELS.get(scope, scope)


_LOGIN_PAGE_TEMPLATE = """\
<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{brand_name} · 授权登录</title>
  <style>
    body {{ font-family: -apple-system, sans-serif; max-width: 420px; margin: 24px auto; padding: 0 16px; }}
    h2 {{ margin: 0 0 8px; }}
    .hint {{ color: #666; font-size: 13px; margin-bottom: 16px; }}
    .binding {{ background: #fff7e6; border: 1px solid #ffd591; padding: 12px; border-radius: 6px; margin-bottom: 16px; }}
    label {{ display: block; margin-top: 12px; font-size: 13px; color: #444; }}
    input[type=text], input[type=tel] {{ width: 100%; padding: 10px; border: 1px solid #ccc; border-radius: 4px; box-sizing: border-box; }}
    button {{ width: 100%; padding: 12px; background: #0a7; color: #fff; border: 0; border-radius: 4px; font-size: 15px; margin-top: 16px; cursor: pointer; }}
    ul {{ padding-left: 20px; color: #444; font-size: 13px; }}
    .footer {{ color: #999; font-size: 11px; margin-top: 24px; line-height: 1.6; }}
    .domain {{ color: #0a7; font-weight: 600; }}
  </style>
</head>
<body>
  <div class="hint">🟢 <span class="domain">auth.coffee.example</span> (mock)</div>
  <h2>{brand_name} · 授权登录</h2>
  <div class="binding">正在为 <b>[{agent}]</b> 授权</div>

  <form method="post" action="/h5/login/submit">
    <input type="hidden" name="state" value="{state}">
    <input type="hidden" name="scope" value="{scope}">
    <input type="hidden" name="code_challenge" value="{challenge}">
    <input type="hidden" name="redirect_uri" value="{redirect_uri}">

    <label>手机号</label>
    <input type="tel" name="phone" value="13800001234" placeholder="11 位手机号" required>

    <label>短信验证码</label>
    <input type="text" name="otp" value="000000" placeholder="6 位验证码" required>

    <p style="font-size:13px;color:#666;margin-top:16px">将共享:</p>
    <ul>{scope_list}<li>✗ 不共享支付密码</li></ul>

    <button type="submit">同意并登录</button>
  </form>

  <div class="footer">
    ⚠️ 本对话由 AI 协助完成,请核对订单信息后再支付 (GB 45438-2025)<br>
    有效期 30 天 · Demo 模式·不会发送真实短信
  </div>
</body>
</html>
"""
