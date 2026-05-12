"""JWT validation for real brand Authorization Servers.

Used when `BrandConfig.oauth.jwks_uri` is set (i.e. `use_mock_as=False`).
Fetches the AS's JWKS, caches it in process memory with a 1 hour TTL, and
validates the access token via authlib.

Returns the same dict shape as MockAS.introspect() so toc_server.py's
auth path is uniform: {member_id, scope: set[str], exp: float}.
"""

from __future__ import annotations

import json
import threading
import time
from typing import Any

import httpx
from authlib.jose import JsonWebKey, JoseError, jwt

from ..brand_config import OAuthConfig


_JWKS_CACHE: dict[str, tuple[float, Any]] = {}
_JWKS_LOCK = threading.Lock()
_JWKS_TTL = 3600.0       # 1 hour
_FETCH_TIMEOUT = 5.0


def _get_jwks(jwks_uri: str) -> Any:
    """Return a cached JsonWebKey set for jwks_uri.

    Cache is process-local with 1h TTL. A failed refresh falls back to the
    last-known-good entry if available, so a transient AS hiccup doesn't
    immediately deny every authenticated request.
    """
    now = time.monotonic()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(jwks_uri)
        if cached and (now - cached[0]) < _JWKS_TTL:
            return cached[1]

    try:
        resp = httpx.get(jwks_uri, timeout=_FETCH_TIMEOUT, trust_env=False)
        resp.raise_for_status()
        jwks = JsonWebKey.import_key_set(resp.json())
    except Exception:
        # Fall back to stale cache if available.
        with _JWKS_LOCK:
            cached = _JWKS_CACHE.get(jwks_uri)
            if cached:
                return cached[1]
        raise

    with _JWKS_LOCK:
        _JWKS_CACHE[jwks_uri] = (now, jwks)
    return jwks


def validate_jwt(token: str, oauth: OAuthConfig) -> dict | None:
    """Validate `token` against the brand's AS. Returns introspection dict or None.

    Validates issuer, audience, and expiration. Scope is read from either
    `scope` (space-separated) or `scp` (array) claims — common conventions.
    `sub` becomes the member_id.
    """
    if not oauth.jwks_uri:
        return None

    try:
        jwks = _get_jwks(oauth.jwks_uri)
    except Exception:
        return None

    claims_options = {
        "iss": {"essential": True, "value": oauth.issuer},
    }
    if oauth.audience:
        claims_options["aud"] = {"essential": True, "value": oauth.audience}

    try:
        claims = jwt.decode(token, jwks, claims_options=claims_options)
        claims.validate()
    except JoseError:
        return None
    except Exception:
        return None

    member_id = claims.get("sub") or claims.get("member_id")
    if not member_id:
        return None

    scope_claim = claims.get("scope") or claims.get("scp") or ""
    if isinstance(scope_claim, list):
        scope_set: set[str] = set(scope_claim)
    elif isinstance(scope_claim, str):
        scope_set = set(scope_claim.split()) if scope_claim else set()
    else:
        scope_set = set()

    exp = claims.get("exp")
    if exp is None:
        return None
    # Convert wall-clock exp → monotonic-ish; we just need a deadline relative
    # to time.monotonic() that's roughly correct. The store treats exp as
    # monotonic; ok to approximate because token TTLs are bounded.
    monotonic_exp = time.monotonic() + max(int(exp) - int(time.time()), 1)

    return {
        "member_id": str(member_id),
        "scope": scope_set,
        "exp": monotonic_exp,
    }


def clear_cache() -> None:
    """Test helper — drop the JWKS cache."""
    with _JWKS_LOCK:
        _JWKS_CACHE.clear()
