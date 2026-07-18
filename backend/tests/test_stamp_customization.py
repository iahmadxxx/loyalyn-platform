from types import SimpleNamespace

from app.api.routes.stamps import STAMP_ICON_LIBRARY, _program_settings
from app.schemas.common import StampProgramCreate


def test_icon_library_has_multiple_categories_and_custom_choice():
    categories = {row["category"] for row in STAMP_ICON_LIBRARY}
    values = {item["value"] for row in STAMP_ICON_LIBRARY for item in row["items"]}
    assert {"coffee", "dessert", "food", "general"}.issubset(categories)
    assert {"coffee", "cake", "cookie", "custom"}.issubset(values)


def test_stamp_program_settings_defaults_are_production_safe():
    settings = _program_settings(SimpleNamespace(settings={}))
    assert settings["display_mode"] == "icons_and_count"
    assert settings["max_per_action"] == 5
    assert settings["allow_multiple"] is True
    assert settings["carry_over"] is True


def test_stamp_program_schema_accepts_advanced_customization():
    payload = StampProgramCreate(
        brand_id="11111111-1111-1111-1111-111111111111",
        name="قهوة وحلى",
        slug="coffee-sweet",
        settings={
            "display_mode": "progress",
            "stamp_shape": "rounded",
            "allow_multiple": False,
            "max_per_action": 1,
            "daily_limit": 3,
        },
    )
    assert payload.settings["display_mode"] == "progress"
    assert payload.settings["daily_limit"] == 3
