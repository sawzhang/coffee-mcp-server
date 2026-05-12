"""JWT validation for real brand Authorization Servers.

Used when `BrandConfig.oauth.jwks_uri` is set (i.e. `use_mock_as=False`).
Fetches the AS's JWKS, caches it in process memory with a 1 hour TTL, and
validates the access token via joserfc.

Returns the same dict shape as MockAS.introspect() so toc_server.py's
auth path is uniform: {member_id, scope: set[str], exp: float}.
"""

from __future__ import annotations

import ipaddress
import socket
import threading
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from joserfc import jwt
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
# Per-uri singleflight locks so that N concurrent requests crossing the cache
# expiry only fire one JWKS refresh (rather than stampeding the AS).
_JWKS_FETCH_LOCKS: dict[str, threading.Lock] = {}
_JWKS_FETCH_LOCKS_GUARD = threading.Lock()
_JWKS_TTL = 3600.0       # 1 hour
_FETCH_TIMEOUT = 5.0


def _fetch_lock_for(jwks_uri: str) -> threading.Lock:
    with _JWKS_FETCH_LOCKS_GUARD:
        lock = _JWKS_FETCH_LOCKS.get(jwks_uri)
        if lock is None:
            lock = threading.Lock()
            _JWKS_FETCH_LOCKS[jwks_uri] = lock
        return lock


def _is_blocked_address(host: str) -> bool:
    """Return True if `host` resolves to an SSRF-sensitive range.

    Blocks link-local (169.254/16 — covers AWS/GCP/Alibaba metadata IPs) and
    other unspecified/reserved ranges. Loopback (127.0.0.0/8, ::1) is allowed
    because brand AS may legitimately run on the same host in dev/preview
    deployments — operators control brand.yaml.
    """
    try:
        infos = socket.getaddrinfo(host, None)
    except OSError:
        # Unresolvable host — let the actual HTTP fetch error out cleanly.
        return False
    for info in infos:
        try:
            addr = ipaddress.ip_address(info[4][0])
        except ValueError:
            continue
        if addr.is_link_local or addr.is_multicast or addr.is_unspecified \
                or addr.is_reserved:
            return True
    return False


def _check_jwks_uri_safe(jwks_uri: str) -> bool:
    """Reject obviously unsafe jwks_uri values to limit the SSRF surface.

    Brand yaml is operator-controlled and therefore trusted, but a careless
    paste of an internal URL (cloud metadata, file://) shouldn't fetch.
    """
    parsed = urlparse(jwks_uri)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    return not _is_blocked_address(parsed.hostname)


def _get_jwks(jwks_uri: str) -> KeySet:
    """Return a cached KeySet for jwks_uri.

    Cache is process-local with 1h TTL. A failed refresh falls back to the
    last-known-good entry if available, so a transient AS hiccup doesn't
    immediately deny every authenticated request. Refreshes are serialized
    per-URI to prevent a stampede when the cache expires.
    """
    if not _check_jwks_uri_safe(jwks_uri):
        raise ValueError(f"jwks_uri rejected by SSRF filter: {jwks_uri}")

    now = time.monotonic()
    with _JWKS_LOCK:
        cached = _JWKS_CACHE.get(jwks_uri)
        if cached and (now - cached[0]) < _JWKS_TTL:
            return cached[1]

    fetch_lock = _fetch_lock_for(jwks_uri)
    with fetch_lock:
        # Double-check: another thread may have refreshed while we waited.
        with _JWKS_LOCK:
            cached = _JWKS_CACHE.get(jwks_uri)
            if cached and (time.monotonic() - cached[0]) < _JWKS_TTL:
                return cached[1]

        try:
            resp = httpx.get(jwks_uri, timeout=_FETCH_TIMEOUT, trust_env=False)
            resp.raise_for_status()
            key_set = KeySet.import_key_set(resp.json())
        except Exception:
            # Fall back to stale cache if available.
            with _JWKS_LOCK:
                cached = _JWKS_CACHE.get(jwks_uri)
                if cached:
                    return cached[1]
            raise

        with _JWKS_LOCK:
            _JWKS_CACHE[jwks_uri] = (time.monotonic(), key_set)
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
    except Exception:
        # joserfc raises JoseError (and ValueError on malformed tokens); both
        # are subclasses of Exception. One except clause is sufficient.
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
    # `exp` from the JWT is wall-clock seconds; the session store treats the
    # value as monotonic. Approximate by anchoring "now" in both clocks — close
    # enough for the bounded token TTLs we accept.
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
