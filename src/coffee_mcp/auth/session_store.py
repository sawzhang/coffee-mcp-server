"""Session state machine for OAuth 2.1 Stage 1.

Holds session_id → (auth_level, member_id, scope, token) mapping.
In-memory only; the SessionStore ABC keeps Redis as a drop-in option.

TTL/cleanup pattern lifted from src/coffee_mcp/utils.py:28-38.
"""

from __future__ import annotations

import secrets
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import Enum


class AuthLevel(str, Enum):
    ANONYMOUS = "anonymous"
    OTP_VERIFIED = "otp_verified"
    STEP_UP_VERIFIED = "step_up_verified"


@dataclass
class Session:
    session_id: str
    auth_level: AuthLevel = AuthLevel.ANONYMOUS
    member_id: str | None = None
    scope: set[str] = field(default_factory=set)
    member_token: str | None = None
    token_expires_at: float = 0.0          # monotonic
    step_up_expires_at: float = 0.0        # monotonic
    pkce_verifier: str | None = None
    pkce_state: str | None = None
    requested_scope: str | None = None     # scope being requested in current flow
    created_at: float = field(default_factory=time.monotonic)
    last_active_at: float = field(default_factory=time.monotonic)


class SessionStore(ABC):
    """Interface kept narrow so a Redis backend can drop in."""

    @abstractmethod
    def create(self, *, short_ttl: bool = False) -> Session: ...

    @abstractmethod
    def get(self, session_id: str) -> Session | None: ...

    @abstractmethod
    def find_by_state(self, state: str) -> Session | None: ...

    @abstractmethod
    def find_by_token(self, token: str) -> Session | None: ...

    @abstractmethod
    def attach_pkce(self, session_id: str, verifier: str, state: str,
                    requested_scope: str | None = None) -> None: ...

    @abstractmethod
    def upgrade(self, session_id: str, member_id: str, scope: set[str],
                member_token: str, token_expires_in: int) -> Session: ...

    @abstractmethod
    def mark_step_up(self, session_id: str, ttl: int = 300) -> None: ...

    @abstractmethod
    def expire_token(self, session_id: str) -> None: ...

    @abstractmethod
    def clear(self, session_id: str) -> None: ...


class InMemorySessionStore(SessionStore):
    """Process-local session store.

    Cleanup runs lazily on every mutating call, at most once per 60s,
    using the same window-based eviction as utils.py.

    `short_ttl` sessions (anonymous, minted by tool guard to carry a session_id
    in continue_url) expire in 10 minutes by default. Authenticated sessions
    use the regular TTL. An LRU cap on anonymous sessions prevents the
    "every call mints a session" path from being a DoS vector.
    """

    def __init__(self, ttl_seconds: int = 3600,
                 anonymous_ttl_seconds: int = 600,
                 max_anonymous: int = 5000):
        self._sessions: dict[str, Session] = {}
        # FIFO of anonymous-only ids. deque for O(1) popleft (was list.pop(0)).
        self._anonymous_sids: deque[str] = deque()
        self._ttl = ttl_seconds
        self._anonymous_ttl = anonymous_ttl_seconds
        self._max_anonymous = max_anonymous
        self._last_cleanup: float = 0.0
        self._cleanup_interval: float = 60.0

    # ---- lifecycle ----

    def create(self, *, short_ttl: bool = False) -> Session:
        self._maybe_cleanup()
        sid = f"sess_{uuid.uuid4().hex}"
        session = Session(session_id=sid)
        if short_ttl:
            self._anonymous_sids.append(sid)
            while len(self._anonymous_sids) > self._max_anonymous:
                evict = self._anonymous_sids.popleft()
                self._sessions.pop(evict, None)
        self._sessions[sid] = session
        return session

    def get(self, session_id: str) -> Session | None:
        s = self._sessions.get(session_id)
        if s is None:
            return None
        if self._is_expired(s):
            del self._sessions[session_id]
            return None
        s.last_active_at = time.monotonic()
        return s

    def find_by_state(self, state: str) -> Session | None:
        for s in self._sessions.values():
            if s.pkce_state and s.pkce_state == state and not self._is_expired(s):
                return s
        return None

    def find_by_token(self, token: str) -> Session | None:
        for s in self._sessions.values():
            if s.member_token and s.member_token == token and not self._is_expired(s):
                return s
        return None

    def attach_pkce(self, session_id: str, verifier: str, state: str,
                    requested_scope: str | None = None) -> None:
        s = self._sessions.get(session_id)
        if not s:
            return
        s.pkce_verifier = verifier
        s.pkce_state = state
        s.requested_scope = requested_scope
        s.last_active_at = time.monotonic()

    def upgrade(self, session_id: str, member_id: str, scope: set[str],
                member_token: str, token_expires_in: int) -> Session:
        s = self._sessions.get(session_id)
        if not s:
            raise KeyError(session_id)
        # Merge new scope into existing (incremental authorization)
        s.scope = (s.scope or set()) | set(scope)
        s.member_id = member_id
        s.member_token = member_token
        s.token_expires_at = time.monotonic() + max(token_expires_in, 1)
        s.auth_level = AuthLevel.OTP_VERIFIED
        s.last_active_at = time.monotonic()
        # PKCE consumed
        s.pkce_verifier = None
        s.pkce_state = None
        s.requested_scope = None
        # Session has graduated from anonymous → drop from LRU list.
        try:
            self._anonymous_sids.remove(session_id)
        except ValueError:
            pass
        return s

    def mark_step_up(self, session_id: str, ttl: int = 300) -> None:
        s = self._sessions.get(session_id)
        if not s:
            return
        s.auth_level = AuthLevel.STEP_UP_VERIFIED
        s.step_up_expires_at = time.monotonic() + ttl
        s.last_active_at = time.monotonic()

    def expire_token(self, session_id: str) -> None:
        """Test helper: force token to be expired without dropping the session."""
        s = self._sessions.get(session_id)
        if s:
            s.token_expires_at = 0.0

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)
        try:
            self._anonymous_sids.remove(session_id)
        except ValueError:
            pass

    # ---- internals ----

    def _is_expired(self, s: Session) -> bool:
        now = time.monotonic()
        if s.member_id:
            return (now - s.last_active_at) > self._ttl
        # Anonymous sessions also enforce an absolute max-age from creation —
        # otherwise a polling client could keep one alive forever and starve the
        # LRU cap.
        if (now - s.created_at) > self._anonymous_ttl:
            return True
        return (now - s.last_active_at) > self._anonymous_ttl

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        if now - self._last_cleanup < self._cleanup_interval:
            return
        stale = [sid for sid, s in self._sessions.items() if self._is_expired(s)]
        for sid in stale:
            del self._sessions[sid]
            try:
                self._anonymous_sids.remove(sid)
            except ValueError:
                pass
        self._last_cleanup = now

    # ---- diagnostics (used in tests) ----

    def stats(self) -> dict:
        anon = sum(1 for s in self._sessions.values() if not s.member_id)
        authed = len(self._sessions) - anon
        return {"total": len(self._sessions), "anonymous": anon, "authenticated": authed}


def generate_pkce_pair() -> tuple[str, str]:
    """Return (verifier, S256_challenge) per RFC 7636."""
    import base64
    import hashlib
    # token_urlsafe(64) returns ~86 chars (within RFC 7636's 43-128 char range).
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


def generate_state() -> str:
    return secrets.token_urlsafe(24)
