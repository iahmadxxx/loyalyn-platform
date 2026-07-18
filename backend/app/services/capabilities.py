from __future__ import annotations

from typing import Any


PROGRAM_MODES = {"stamps_only", "points_only", "stamps_points", "full", "custom"}

MODE_FEATURES: dict[str, dict[str, bool]] = {
    "stamps_only": {
        "stamps": True,
        "multi_stamp_cards": True,
        "fast_scan": True,
        "points": False,
        "cashback": False,
        "tiers": False,
        "rewards": True,
        "coupons": False,
        "wallet": True,
        "campaigns": True,
    },
    "points_only": {
        "stamps": False,
        "multi_stamp_cards": False,
        "fast_scan": True,
        "points": True,
        "cashback": False,
        "tiers": True,
        "rewards": True,
        "coupons": True,
        "wallet": True,
        "campaigns": True,
    },
    "stamps_points": {
        "stamps": True,
        "multi_stamp_cards": True,
        "fast_scan": True,
        "points": True,
        "cashback": False,
        "tiers": True,
        "rewards": True,
        "coupons": True,
        "wallet": True,
        "campaigns": True,
    },
    "full": {
        "stamps": True,
        "multi_stamp_cards": True,
        "fast_scan": True,
        "points": True,
        "cashback": True,
        "tiers": True,
        "rewards": True,
        "coupons": True,
        "wallet": True,
        "campaigns": True,
    },
    "custom": {
        "stamps": True,
        "multi_stamp_cards": True,
        "fast_scan": True,
        "points": True,
        "cashback": False,
        "tiers": True,
        "rewards": True,
        "coupons": True,
        "wallet": True,
        "campaigns": True,
    },
}


def normalized_mode(value: str | None) -> str:
    value = (value or "full").strip().lower()
    return value if value in PROGRAM_MODES else "full"


def brand_capabilities(brand: Any) -> dict[str, bool]:
    mode = normalized_mode(getattr(brand, "program_mode", None))
    result = dict(MODE_FEATURES[mode])
    custom = getattr(brand, "feature_flags", None) or {}
    for key, value in custom.items():
        if key in result and isinstance(value, bool):
            result[key] = value
    # Dependencies: a disabled parent capability must hide dependent features.
    if not result.get("stamps"):
        result["multi_stamp_cards"] = False
    if not result.get("stamps") and not result.get("points"):
        result["rewards"] = False
    return result


def loyalty_program_type(mode: str, capabilities: dict[str, bool]) -> str:
    mode = normalized_mode(mode)
    if mode == "stamps_only":
        return "stamps"
    if mode == "points_only":
        return "points"
    if mode == "stamps_points":
        return "hybrid"
    if mode == "full" and capabilities.get("cashback") and not capabilities.get("points"):
        return "cashback"
    if capabilities.get("stamps") and capabilities.get("points"):
        return "hybrid"
    if capabilities.get("stamps"):
        return "stamps"
    if capabilities.get("points"):
        return "points"
    return "points"
