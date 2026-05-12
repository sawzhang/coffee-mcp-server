"""JWT validation for real brand Authorization Servers.

Used when `BrandConfig.oauth.jwks_uri` is set (i.e. `use_mock_as=False`).
Fetches the AS's JWKS, caches it in process memory with a 1 hour TTL, and
validates the access token via joserfc.

Returns the same dict shape as MockAS.introspect() so toc_server.py's
auth path is uniform: {member_id, scope: set[str], exp: float}.
"""

from __future__ import annotations

import threading
import time
from typing import Any

import httpx
from joserfc import jwt
from joserfc.errors import JoseError
from joserfc.jwk import KeySet
from joserfc.jwt import JWTClaimsRegistry

from ..brand_config import OAuthConfig


# Asymmetric algorithms only. HS256 is rejected because it implies a shared
# secret an AS would never publish via jwks_uri.
_ALLOWED_ALGS: list[str] = ["RS256", "RS384", "RS512",
                            "ES256", "ES384", "ES512",
                            "PS256", "PS384", "PS512",
                            "EdDSA"]

_JWKS_CACHE: dict[str, tuple[float, KeySet]] = {}
_JWKS_LOCK = threading.Lock()
_JWKS_TTL = 3600.0       # 1 hour
_FETCH_TIMEOUT = 5.0


def _get_jwks(jwks_uri: str) -> KeySet:
    """Return a cached KeySet for jwks_uri.

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
        key_set = KeySet.import_key_set(resp.json())
    except Exception:
        with _JWKS_LOCK:
            cached = _JWKS_CACHE.get(jwks_uri)
            if cached:
                return cached[1]
        raise

    with _JWKS_LOCK:
        _JWKS_CACHE[jwks_uri] = (now, key_set)
    return key_set


def validate_jwt(token: str, oauth: OAuthConfig) -> dict | None:
    """Validate `token` against the brand's AS. Returns introspection dict or None.

    Validates issuer, audience, exp, and signature with the AS's JWKS.
    `sub` (or `member_id`) → member_id; `scope` (space-separated) / `scp`
    (array) → scope set.
    """
    if not oauth.jwks_uri:
        return None

    try:
        key_set = _get_jwks(oauth.jwks_uri)
    except Exception:
        return None

    try:
        decoded = jwt.decode(token, key_set, algorithms=_ALLOWED_ALGS)
    except (JoseError, ValueError):
        return None
    except Exception:
        return None

    claims = decoded.claims
    claims_options: dict[str, Any] = {
        "iss": {"essential": True, "value": oauth.issuer},
        "exp": {"essential": True},
    }
    if oauth.audience:
        claims_options["aud"] = {"essential": True, "value": oauth.audience}
    registry = JWTClaimsRegistry(**claims_options)
    try:
        registry.validate(claims)
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
