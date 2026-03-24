"""Shared utilities for Coffee Company MCP platform."""

import time
import uuid


def random_id(prefix: str) -> str:
    """Generate a randomized ID like 'ord_a7f3b2e9' to prevent enumeration."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def mask_phone(phone: str) -> str:
    """Mask phone number for list views: 13812341234 → 138****1234"""
    if len(phone) == 11:
        return f"{phone[:3]}****{phone[7:]}"
    return phone


# ---------------------------------------------------------------------------
# Confirmation Token Store (protocol-level security, not data-layer)
# ---------------------------------------------------------------------------

_CONFIRMATION_TOKENS: dict[str, dict] = {}
_CONFIRMATION_TOKEN_TTL = 300  # 5 minutes
_CONFIRMATION_LAST_CLEANUP: float = 0.0


def _cleanup_expired_tokens() -> None:
    """Remove expired/used tokens to prevent memory accumulation."""
    global _CONFIRMATION_LAST_CLEANUP
    now = time.monotonic()
    if now - _CONFIRMATION_LAST_CLEANUP < 60:
        return
    stale = [k for k, v in _CONFIRMATION_TOKENS.items()
             if v["used"] or now - v["created_at"] > _CONFIRMATION_TOKEN_TTL * 2]
    for k in stale:
        del _CONFIRMATION_TOKENS[k]
    _CONFIRMATION_LAST_CLEANUP = now


def generate_confirmation_token() -> str:
    """Generate a one-time confirmation token for L3 operations."""
    _cleanup_expired_tokens()
    token = f"cfm_{uuid.uuid4().hex[:12]}"
    _CONFIRMATION_TOKENS[token] = {"created_at": time.monotonic(), "used": False}
    return token


def validate_confirmation_token(token: str) -> str | None:
    """Validate a confirmation token. Returns error message or None if valid."""
    record = _CONFIRMATION_TOKENS.get(token)
    if not record:
        return "确认令牌无效，请先调用 calculate_price 获取新的确认令牌。"
    if record["used"]:
        return "确认令牌已使用，请重新调用 calculate_price 获取新的确认令牌。"
    elapsed = time.monotonic() - record["created_at"]
    if elapsed > _CONFIRMATION_TOKEN_TTL:
        return "确认令牌已过期（有效期5分钟），请重新调用 calculate_price。"
    record["used"] = True
    return None
