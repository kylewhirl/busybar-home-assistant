"""Tests for Home Assistant MDI assets rendered for BUSY Bar."""

import io
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import State
from PIL import Image

from custom_components.busybar.const import SUPPORTED_DOMAINS
from custom_components.busybar.icons import (
    async_icon_name_for_state,
    async_upload_icons,
    default_icon_name,
    icon_asset_name,
    icon_png,
    normalize_icon_name,
)


@pytest.mark.parametrize(
    "icon_name",
    ["mdi:lightbulb", "mdi:desk-lamp", "mdi:floor-lamp", "mdi:ceiling-light"],
)
def test_real_home_assistant_mdi_icons_render(icon_name: str) -> None:
    image = Image.open(io.BytesIO(icon_png(icon_name, 14, "#FFD518")))

    assert image.mode == "RGBA"
    assert image.size == (14, 14)
    assert image.getbbox() is not None
    assert image.getpixel((0, 0))[3] == 0


def test_home_assistant_fixture_shapes_remain_distinct_at_matrix_size() -> None:
    rendered = {
        icon_png(icon_name, 14, "#FFD518")
        for icon_name in (
            "mdi:lightbulb",
            "mdi:desk-lamp",
            "mdi:floor-lamp",
            "mdi:ceiling-light",
        )
    }

    assert len(rendered) == 4


@pytest.mark.parametrize("domain", [*SUPPORTED_DOMAINS, "device"])
def test_every_supported_domain_has_a_renderable_home_assistant_fallback(domain: str) -> None:
    icon_name = default_icon_name(domain)
    image = Image.open(io.BytesIO(icon_png(icon_name, 14, "#63E6BE")))

    assert icon_name.startswith("mdi:")
    assert image.getbbox() is not None


def test_only_supported_mdi_names_are_used_as_assets() -> None:
    assert normalize_icon_name("mdi:floor-lamp") == "mdi:floor-lamp"
    assert normalize_icon_name("custom:lamp") == "mdi:help-circle"
    assert normalize_icon_name("mdi:not-a-real-icon") == "mdi:help-circle"
    assert icon_asset_name("mdi:floor-lamp") == "mdi_floor-lamp"


@pytest.mark.asyncio
async def test_entity_registry_custom_icon_wins_over_state_and_domain_default() -> None:
    state = State("light.desk", "on", {"icon": "mdi:lightbulb"})
    registry = MagicMock()
    registry.async_get.return_value = SimpleNamespace(icon="mdi:desk-lamp")

    with patch("custom_components.busybar.icons.er.async_get", return_value=registry):
        assert await async_icon_name_for_state(MagicMock(), state) == "mdi:desk-lamp"


@pytest.mark.asyncio
async def test_home_assistant_component_icon_is_used_as_domain_fallback() -> None:
    state = State("light.desk", "on")
    registry = MagicMock()
    registry.async_get.return_value = None

    with (
        patch("custom_components.busybar.icons.er.async_get", return_value=registry),
        patch(
            "custom_components.busybar.icons.async_get_icons",
            new=AsyncMock(
                return_value={
                    "light": {"_": {"default": "mdi:lightbulb"}}
                }
            ),
        ),
    ):
        assert await async_icon_name_for_state(MagicMock(), state) == "mdi:lightbulb"


@pytest.mark.asyncio
async def test_uploads_front_and_back_assets_for_actual_mdi_icons() -> None:
    client = AsyncMock()

    await async_upload_icons(
        client, {"mdi:lightbulb", "mdi:desk-lamp"}, "#63E6BE"
    )

    assert client.assets_upload.await_count == 13
    filenames = {
        call.kwargs["filename"] for call in client.assets_upload.await_args_list
    }
    assert filenames == {
        "ha_blank.png",
        "ha_back_mdi_help-circle.png",
        "ha_front_active_mdi_help-circle.png",
        "ha_front_inactive_mdi_help-circle.png",
        "ha_front_control_mdi_help-circle.png",
        "ha_back_mdi_desk-lamp.png",
        "ha_front_active_mdi_desk-lamp.png",
        "ha_front_inactive_mdi_desk-lamp.png",
        "ha_front_control_mdi_desk-lamp.png",
        "ha_back_mdi_lightbulb.png",
        "ha_front_active_mdi_lightbulb.png",
        "ha_front_inactive_mdi_lightbulb.png",
        "ha_front_control_mdi_lightbulb.png",
    }
    assert all(
        call.kwargs["application_name"] == "home_assistant"
        for call in client.assets_upload.await_args_list
    )
