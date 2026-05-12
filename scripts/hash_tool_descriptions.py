"""Tool description hash baseline (spec R5 —防 Tool Poisoning).

Two subcommands:
  update   write the current hash to evals/tool_description_hash.txt
  check    compare current hash against the baseline, exit non-zero on mismatch

Hashes are computed deterministically over (name, description, inputSchema)
for every tool the ToC MCP server exposes. Any change to a tool's wire
metadata triggers a mismatch — the expected workflow is:
  1. propose the description change in a PR
  2. run `python scripts/hash_tool_descriptions.py update`
  3. reviewer signs off on both the change AND the new hash

Run via:
  uv run python scripts/hash_tool_descriptions.py [update|check]
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

# Make src/ importable when run directly.
_HERE = Path(__file__).resolve().parent
_REPO_ROOT = _HERE.parent
sys.path.insert(0, str(_REPO_ROOT / "src"))


_BASELINE_PATH = _REPO_ROOT / "evals" / "tool_description_hash.txt"


async def _compute_hash() -> tuple[str, list[dict]]:
    """Return (sha256_hex, ordered list of tool entries) for the current code."""
    from coffee_mcp.brand_config import load_brand_adapter, load_brand_config
    from coffee_mcp.toc_server import create_toc_server

    brand = os.environ.get("BRAND", "coffee_company")
    config = load_brand_config(brand)
    adapter = load_brand_adapter(config)
    server = create_toc_server(config, adapter)
    tools = await server.list_tools()

    entries = []
    for t in sorted(tools, key=lambda x: x.name):
        entries.append({
            "name": t.name,
            "description": (t.description or "").strip(),
            "inputSchema": t.inputSchema,
        })
    serialized = json.dumps(entries, ensure_ascii=False, sort_keys=True,
                            separators=(",", ":"))
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return digest, entries


def _read_baseline() -> str | None:
    if not _BASELINE_PATH.exists():
        return None
    for line in _BASELINE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            return line.split()[0]
    return None


def _write_baseline(digest: str, entries: list[dict]) -> None:
    _BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# Tool description hash — DO NOT EDIT manually.",
        f"# Update via: uv run python scripts/hash_tool_descriptions.py update",
        f"# Tool count: {len(entries)}",
        digest,
    ]
    for e in entries:
        lines.append(f"  # {e['name']}: {e['description'][:60]}…")
    _BASELINE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] not in {"update", "check"}:
        print(__doc__)
        return 2

    digest, entries = asyncio.run(_compute_hash())

    if argv[1] == "update":
        _write_baseline(digest, entries)
        print(f"baseline written: {digest}  ({len(entries)} tools)")
        return 0

    # check
    baseline = _read_baseline()
    if baseline is None:
        print(f"ERROR: no baseline at {_BASELINE_PATH}. Run "
              f"`hash_tool_descriptions.py update` first.", file=sys.stderr)
        return 2
    if baseline != digest:
        print(f"FAIL: tool descriptions changed.\n  expected: {baseline}\n"
              f"  current:  {digest}\n  ({len(entries)} tools)\n"
              f"  → if the change is intentional, run "
              f"`hash_tool_descriptions.py update` and review the diff.",
              file=sys.stderr)
        return 1
    print(f"OK: {digest}  ({len(entries)} tools)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
