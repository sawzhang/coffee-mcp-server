"""Starlette ASGI app composing OAuth routes + FastMCP streamable HTTP.

Entry point: `coffee-company-toc-oauth` (defined in pyproject.toml).
"""

from __future__ import annotations

import contextlib
import os

from starlette.applications import Starlette
from starlette.routing import Mount

from ..brand_config import load_brand_adapter, load_brand_config
from ..toc_server import create_toc_server
from .mock_as import MockAS
from .oauth_routes import build_oauth_routes
from .session_store import InMemorySessionStore


def build_app(config=None, adapter=None) -> Starlette:
    """Build the composite ASGI app for a single brand."""
    if config is None:
        brand = os.environ.get("BRAND", "coffee_company")
        config = load_brand_config(brand)
    if adapter is None:
        adapter = load_brand_adapter(config)

    store = InMemorySessionStore()
    mock_as = None
    if config.oauth and config.oauth.use_mock_as:
        mock_as = MockAS(
            issuer=config.oauth.issuer,
            canned_member_id=config.default_user_id,
        )

    mcp = create_toc_server(config, adapter,
                            session_store=store,
                            mock_as=mock_as)
    mcp_app = mcp.streamable_http_app()

    # The streamable_http_app uses a lifespan to start the session manager
    # task group. When we mount it inside another Starlette app, we must
    # forward its lifespan ourselves, otherwise tools/call returns 500
    # ("Task group is not initialized").
    @contextlib.asynccontextmanager
    async def lifespan(app):  # noqa: ANN001
        async with mcp_app.router.lifespan_context(app):
            yield

    routes = build_oauth_routes(config, store, mock_as)
    routes.append(Mount("/", app=mcp_app))

    app = Starlette(routes=routes, lifespan=lifespan)
    app.state.session_store = store
    app.state.mock_as = mock_as
    app.state.brand_config = config
    return app


def run() -> None:
    """uvicorn entry point — `coffee-company-toc-oauth`."""
    import uvicorn
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8765"))
    uvicorn.run(build_app(), host=host, port=port)


if __name__ == "__main__":
    run()
