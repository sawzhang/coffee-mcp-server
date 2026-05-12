"""In-process mock Authorization Server for demo / Stage-1 testing.

Mints opaque tokens (no JWT signing) and exposes the minimum OAuth surface
needed by oauth_routes.py and the H5 demo login page.

Real brand AS replaces this — the resource-server side validates tokens via
authlib + jwks_uri instead of MockAS.introspect().
"""

from __future__ import annotations

import secrets
import time
import uuid
from dataclasses import dataclass, field


@dataclass
class _MockGrant:
    code: str
    state: str
    code_challenge: str
    code_challenge_method: str
    member_id: str
    scope: set[str]
    expires_at: float


@dataclass
class _MockToken:
    access_token: str
    member_id: str
    scope: set[str]
    expires_at: float


class MockAS:
    """In-memory pseudo-IdP.

    Single canned member binds to the brand's default_user_id so that
    DemoAdapter / toc_mock_data continue to resolve to the same data.
    """

    def __init__(self, issuer: str, canned_member_id: str = "CC_M_100001"):
        self.issuer = issuer
        self.canned_member_id = canned_member_id
        self._grants: dict[str, _MockGrant] = {}    # code → grant
        self._tokens: dict[str, _MockToken] = {}    # token → token record
        self._grant_ttl = 60                        # auth code lifetime
        self._token_ttl = 3600                      # access token lifetime

    # ---- /h5/login → /h5/login/submit ----

    def issue_code(self, state: str, code_challenge: str,
                   scope: set[str],
                   code_challenge_method: str = "S256",
                   member_id: str | None = None) -> str:
        """Called when the user submits the demo H5 form."""
        self._cleanup()
        code = f"mock_code_{uuid.uuid4().hex[:16]}"
        self._grants[code] = _MockGrant(
            code=code,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
            member_id=member_id or self.canned_member_id,
            scope=set(scope),
            expires_at=time.monotonic() + self._grant_ttl,
        )
        return code

    # ---- /mock-as/token ----

    def exchange_code(self, code: str, code_verifier: str) -> dict | None:
        """PKCE code → opaque token. Returns RFC 6749 token response or None on failure."""
        self._cleanup()
        grant = self._grants.pop(code, None)
        if not grant:
            return None
        if time.monotonic() > grant.expires_at:
            return None
        if not self._verify_pkce(code_verifier, grant.code_challenge,
                                 grant.code_challenge_method):
            return None

        access_token = f"mock_at_{secrets.token_urlsafe(24)}"
        self._tokens[access_token] = _MockToken(
            access_token=access_token,
            member_id=grant.member_id,
            scope=grant.scope,
            expires_at=time.monotonic() + self._token_ttl,
        )
        return {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": self._token_ttl,
            "scope": " ".join(sorted(grant.scope)),
        }

    # ---- token introspection (used by the RS) ----

    def introspect(self, token: str) -> dict | None:
        """Returns {member_id, scope:set[str], exp:float} or None if invalid/expired."""
        rec = self._tokens.get(token)
        if not rec:
            return None
        if time.monotonic() > rec.expires_at:
            del self._tokens[token]
            return None
        return {
            "member_id": rec.member_id,
            "scope": set(rec.scope),
            "exp": rec.expires_at,
        }

    # ---- /mock-as/.well-known/openid-configuration ----

    def well_known(self, base_url: str) -> dict:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{base_url}/mock-as/authorize",
            "token_endpoint": f"{base_url}/mock-as/token",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code"],
            "code_challenge_methods_supported": ["S256"],
            "scopes_supported": [
                "read:account", "read:orders", "read:rewards",
                "write:addresses", "write:orders", "redeem:stars",
            ],
        }

    # ---- internals ----

    def _verify_pkce(self, verifier: str, challenge: str, method: str) -> bool:
        if method != "S256":
            return False
        import base64
        import hashlib
        digest = hashlib.sha256(verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return computed == challenge

    def _cleanup(self) -> None:
        now = time.monotonic()
        stale_grants = [c for c, g in self._grants.items() if g.expires_at < now]
        for c in stale_grants:
            del self._grants[c]
        stale_tokens = [t for t, r in self._tokens.items() if r.expires_at < now]
        for t in stale_tokens:
            del self._tokens[t]
