"""Append-only JSONL audit log for PIPL §55 compliance.

Every tool invocation goes through `record()`. Fields:
  ts, session_id, mcp_client, agent_id, member_id_hash, tool,
  scope_used, step_up_id, result, ip, user_agent, error

`member_id` is hashed with a salt — plaintext member_id never lands on disk.
Configure via env:
  COFFEE_AUDIT_LOG  — output path (default: ./audit.jsonl, gitignored)
  COFFEE_AUDIT_SALT — hash salt (REQUIRED for production; defaults to a
                       constant in demo mode with a stderr warning)
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any

# RLock so that record() (which holds the lock) can call hash_member_id
# (which acquires the lock for lazy salt init) without deadlocking.
_LOCK = threading.RLock()
_FH: Any = None
_PATH: str | None = None
_SALT: bytes | None = None
_WARNED_DEFAULT_SALT = False


def _resolve_path() -> str:
    return os.environ.get("COFFEE_AUDIT_LOG", "audit.jsonl")


def _resolve_salt() -> bytes:
    global _WARNED_DEFAULT_SALT
    env_salt = os.environ.get("COFFEE_AUDIT_SALT")
    if env_salt:
        return env_salt.encode("utf-8")
    if not _WARNED_DEFAULT_SALT:
        print("[audit] WARNING: COFFEE_AUDIT_SALT not set — using insecure "
              "demo default. Set it in production.", file=sys.stderr)
        _WARNED_DEFAULT_SALT = True
    return b"coffee-mcp-demo-salt-do-not-use-in-prod"


def _ensure_open() -> None:
    global _FH, _PATH, _SALT
    if _FH is not None and _PATH == _resolve_path():
        return
    if _FH is not None:
        try:
            _FH.close()
        except Exception:
            pass
    _PATH = _resolve_path()
    parent = os.path.dirname(_PATH)
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    _FH = open(_PATH, "a", encoding="utf-8")
    _SALT = _resolve_salt()


def hash_member_id(member_id: str | None) -> str | None:
    if not member_id:
        return None
    # Lazy salt init must be lock-protected: two concurrent callers could each
    # observe _SALT is None, both enter _ensure_open(), and the second one
    # reopens the file handle the first one is writing to.
    with _LOCK:
        if _SALT is None:
            _ensure_open()
        salt = _SALT or b""
    h = hashlib.sha256()
    h.update(salt)
    h.update(b":")
    h.update(member_id.encode("utf-8"))
    return h.hexdigest()


def record(*, tool: str, result: str,
           session_id: str | None = None,
           member_id: str | None = None,
           mcp_client: str | None = None,
           agent_id: str | None = None,
           scope_used: str | None = None,
           step_up_id: str | None = None,
           ip: str | None = None,
           user_agent: str | None = None,
           error: str | None = None,
           extra: dict | None = None) -> None:
    """Append a single audit record. Never raises."""
    try:
        with _LOCK:
            _ensure_open()
            entry = {
                "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "session_id": session_id,
                "mcp_client": mcp_client or "unknown",
                "agent_id": agent_id,
                "member_id_hash": hash_member_id(member_id),
                "tool": tool,
                "scope_used": scope_used,
                "step_up_id": step_up_id,
                "result": result,
                "ip": ip,
                "user_agent": user_agent,
                "error": error,
            }
            if extra:
                entry["extra"] = extra
            _FH.write(json.dumps(entry, ensure_ascii=False) + "\n")
            _FH.flush()
    except Exception as e:
        # Audit must never break the actual tool call.
        print(f"[audit] write failed: {e}", file=sys.stderr)


def close() -> None:
    global _FH
    with _LOCK:
        if _FH is not None:
            try:
                _FH.close()
            except Exception:
                pass
            _FH = None


def current_path() -> str | None:
    return _PATH
