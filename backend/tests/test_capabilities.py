from types import SimpleNamespace

from app.services.capabilities import brand_capabilities, loyalty_program_type, normalized_mode


def brand(mode="full", flags=None):
    return SimpleNamespace(program_mode=mode, feature_flags=flags or {})


def test_stamp_only_profile_hides_points_and_keeps_scan_wallet():
    caps = brand_capabilities(brand("stamps_only"))
    assert caps["stamps"] and caps["multi_stamp_cards"] and caps["fast_scan"] and caps["wallet"]
    assert not caps["points"] and not caps["cashback"] and not caps["tiers"]
    assert loyalty_program_type("stamps_only", caps) == "stamps"


def test_full_profile_keeps_all_existing_features():
    caps = brand_capabilities(brand("full"))
    assert all(caps.values())
    assert loyalty_program_type("full", caps) == "hybrid"


def test_custom_flags_are_per_brand_and_dependencies_are_safe():
    caps = brand_capabilities(brand("custom", {"stamps": False, "multi_stamp_cards": True, "points": True, "campaigns": False}))
    assert caps["stamps"] is False
    assert caps["multi_stamp_cards"] is False
    assert caps["points"] is True
    assert caps["campaigns"] is False


def test_unknown_mode_falls_back_to_full():
    assert normalized_mode("unknown") == "full"
