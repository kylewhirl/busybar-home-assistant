"""Resolve Home Assistant MDI icons and upload them to BUSY displays."""

from __future__ import annotations

import asyncio
import contextlib
import io
from typing import Any

import resvg_py
from busylib import AsyncBusyBar, types
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons
from material_design_icons_pack import get_icon
from PIL import Image

from .const import APPLICATION_NAME
from .dashboard import icon_asset_path

_DEFAULT_MDI_ICONS = {
    "button": "mdi:gesture-tap-button",
    "climate": "mdi:thermostat",
    "cover": "mdi:window-shutter",
    "fan": "mdi:fan",
    "input_boolean": "mdi:checkbox-marked-circle",
    "input_number": "mdi:ray-vertex",
    "light": "mdi:lightbulb",
    "lock": "mdi:lock",
    "media_player": "mdi:speaker",
    "number": "mdi:ray-vertex",
    "scene": "mdi:palette",
    "script": "mdi:script-text-play",
    "switch": "mdi:toggle-switch",
}

def default_icon_name(domain: str) -> str:
    """Return a stable MDI fallback for a supported Home Assistant domain."""
    return _DEFAULT_MDI_ICONS.get(domain, "mdi:help-circle")


def normalize_icon_name(icon_name: str) -> str:
    """Return a renderable MDI name, falling back when a custom set is unavailable."""
    candidate = icon_name.lower().strip()
    if candidate.startswith("mdi:") and get_icon(candidate.removeprefix("mdi:")):
        return candidate
    return "mdi:help-circle"


def _icon_from_spec(spec: Any) -> str | None:
    """Read the stable default from a Home Assistant icon translation spec."""
    if isinstance(spec, str):
        return spec
    if isinstance(spec, dict) and isinstance(spec.get("default"), str):
        return spec["default"]
    return None


async def async_icon_name_for_state(hass: HomeAssistant, state: State) -> str:
    """Resolve the same explicit and translated MDI metadata Home Assistant uses."""
    registry = er.async_get(hass)
    entry = registry.async_get(state.entity_id)

    for candidate in (
        getattr(entry, "icon", None),
        state.attributes.get("icon"),
    ):
        if isinstance(candidate, str) and candidate.startswith("mdi:"):
            return normalize_icon_name(candidate)

    if entry and (translation_key := getattr(entry, "translation_key", None)):
        platform = getattr(entry, "platform", None)
        if platform:
            with contextlib.suppress(Exception):
                resources = await async_get_icons(hass, "entity", {platform})
                spec = (
                    resources.get(platform, {})
                    .get(state.domain, {})
                    .get(translation_key)
                )
                if icon_name := _icon_from_spec(spec):
                    return normalize_icon_name(icon_name)

    with contextlib.suppress(Exception):
        resources = await async_get_icons(hass, "entity_component", {state.domain})
        component = resources.get(state.domain, {})
        device_class = (
            getattr(entry, "device_class", None)
            or state.attributes.get("device_class")
        )
        spec = component.get(device_class) or component.get("_")
        if icon_name := _icon_from_spec(spec):
            return normalize_icon_name(icon_name)

    return default_icon_name(state.domain)


def _active_color(icon_name: str, accent_color: str) -> str:
    slug = normalize_icon_name(icon_name).removeprefix("mdi:")
    if any(word in slug for word in ("light", "lamp", "ceiling")):
        return "#FFD518"
    if "fan" in slug:
        return "#39CDE6"
    if any(word in slug for word in ("plug", "power", "switch")):
        return "#A78BFA"
    if any(word in slug for word in ("cover", "shade", "shutter", "blind")):
        return "#4A90E2"
    return accent_color


def icon_png(icon_name: str, size: int, color: str) -> bytes:
    """Rasterize an actual Material Design Icon to a transparent PNG."""
    normalized = normalize_icon_name(icon_name)
    icon = get_icon(normalized.removeprefix("mdi:"))
    if icon is None:  # normalize_icon_name guarantees this, but keep a safe boundary.
        icon = get_icon("help-circle")
    assert icon is not None
    svg = icon.svg.replace("<path ", f'<path fill="{color[:7]}" ')
    return resvg_py.svg_to_bytes(svg_string=svg, width=size, height=size)


async def async_upload_icons(
    client: AsyncBusyBar, icon_names: set[str], accent_color: str
) -> None:
    """Rasterize and upload only the MDI icons used by the configured entities."""
    blank = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(blank, "PNG")
    await client.assets_upload(
        application_name=APPLICATION_NAME,
        filename="ha_blank.png",
        data=blank.getvalue(),
    )
    for icon_name in sorted(icon_names | {"mdi:help-circle"}):
        active_color = _active_color(icon_name, accent_color)
        variants = (
            (types.DisplayName.FRONT, "active", 14, active_color),
            (types.DisplayName.FRONT, "inactive", 14, "#7080A0"),
            (types.DisplayName.FRONT, "control", 14, active_color),
            (types.DisplayName.BACK, None, 40, "#FFFFFF"),
        )
        rendered = await asyncio.gather(
            *(asyncio.to_thread(icon_png, icon_name, size, color) for _, _, size, color in variants)
        )
        for (display, variant, _, _), data in zip(variants, rendered, strict=True):
            await client.assets_upload(
                application_name=APPLICATION_NAME,
                filename=icon_asset_path(display, icon_name, variant),
                data=data,
            )
