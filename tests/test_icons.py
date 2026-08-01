"""Tests for generated BUSY Bar device icons."""

import io
from unittest.mock import AsyncMock

import pytest
from PIL import Image

from custom_components.busybar.const import SUPPORTED_DOMAINS
from custom_components.busybar.icons import async_upload_icons, icon_png


@pytest.mark.parametrize("domain", [*SUPPORTED_DOMAINS, "device"])
@pytest.mark.parametrize("size", [10, 14, 16, 40])
def test_every_supported_domain_renders_a_transparent_icon(domain: str, size: int) -> None:
    with Image.open(io.BytesIO(icon_png(domain, size, "#63E6BE"))) as image:
        assert image.mode == "RGBA"
        assert image.size == (size, size)
        assert image.getbbox() is not None
        assert image.getpixel((0, 0))[3] == 0


@pytest.mark.asyncio
async def test_uploads_front_and_back_assets_for_configured_domains() -> None:
    client = AsyncMock()

    await async_upload_icons(client, {"light", "fan"}, "#63E6BE")

    assert client.assets_upload.await_count == 13
    filenames = {
        call.kwargs["filename"] for call in client.assets_upload.await_args_list
    }
    assert filenames == {
        "ha_blank.png",
        "ha_back_device.png",
        "ha_front_active_device.png",
        "ha_front_inactive_device.png",
        "ha_front_control_device.png",
        "ha_back_fan.png",
        "ha_front_active_fan.png",
        "ha_front_inactive_fan.png",
        "ha_front_control_fan.png",
        "ha_back_light.png",
        "ha_front_active_light.png",
        "ha_front_inactive_light.png",
        "ha_front_control_light.png",
    }
    assert all(
        call.kwargs["application_name"] == "home_assistant"
        for call in client.assets_upload.await_args_list
    )
