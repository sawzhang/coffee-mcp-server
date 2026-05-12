"""Tool → OAuth scope mapping for the 21 ToC tools.

Mirrors the L0-L3 risk partition at src/coffee_mcp/toc_server.py:49-71.
"""

from __future__ import annotations


# None = L0 public tool (no scope required)
TOOL_SCOPES: dict[str, str | None] = {
    # L0 — public, no auth
    "now_time_info":        None,
    "browse_menu":          None,
    "drink_detail":         None,
    "nutrition_info":       None,
    "nearby_stores":        None,
    "store_detail":         None,
    # L1 — authenticated read
    "campaign_calendar":    "read:rewards",
    "available_coupons":    "read:rewards",
    "my_account":           "read:account",
    "my_coupons":           "read:rewards",
    "my_orders":            "read:orders",
    "delivery_addresses":   "read:account",
    "stars_mall_products":  "read:rewards",
    "stars_product_detail": "read:rewards",
    "store_coupons":        "read:rewards",
    "order_status":         "read:orders",
    "calculate_price":      "read:orders",
    # L2 — authenticated write
    "claim_all_coupons":    "write:orders",
    "create_address":       "write:addresses",
    # L3 — step-up required
    "create_order":         "write:orders",
    "stars_redeem":         "redeem:stars",
}

# L3 tools that require a fresh step-up confirmation (max 5 min after step-up).
STEP_UP_REQUIRED: set[str] = {"create_order", "stars_redeem"}

# Scopes granted by default on first OAuth login (covers ~80% of high-frequency tools).
DEFAULT_SCOPES: set[str] = {
    "read:account",
    "read:orders",
    "read:rewards",
}

# All scopes the server understands.
ALL_SCOPES: set[str] = {
    "read:account",
    "read:orders",
    "read:rewards",
    "write:addresses",
    "write:orders",
    "redeem:stars",
}
