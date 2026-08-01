"""Generate and upload small device-type icons for BUSY displays."""

from __future__ import annotations

import io
import math

from busylib import AsyncBusyBar, types
from PIL import Image, ImageColor, ImageDraw

from .const import APPLICATION_NAME
from .dashboard import icon_asset_path

_ALIASES = {
    "input_boolean": "switch",
    "input_number": "number",
}


def _star_points(center: float, outer: float, inner: float) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for index in range(10):
        angle = -math.pi / 2 + index * math.pi / 5
        radius = outer if index % 2 == 0 else inner
        points.append((center + math.cos(angle) * radius, center + math.sin(angle) * radius))
    return points


def icon_png(domain: str, size: int, color: str) -> bytes:
    """Render a crisp transparent PNG for one Home Assistant domain."""
    scale = 4
    canvas_size = size * scale
    image = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rgba = (*ImageColor.getrgb(color[:7]), 255)
    line = max(scale, round(size * scale / 9))
    pad = 2 * scale
    far = canvas_size - pad - 1
    center = canvas_size / 2
    kind = _ALIASES.get(domain, domain)

    if kind == "light":
        draw.ellipse((pad * 2, pad, far - pad, far - pad * 2), outline=rgba, width=line)
        draw.line(
            (center - 2 * scale, far - pad * 2, center - scale, far - pad),
            fill=rgba,
            width=line,
        )
        draw.line(
            (center + 2 * scale, far - pad * 2, center + scale, far - pad),
            fill=rgba,
            width=line,
        )
        draw.line(
            (center - 2 * scale, far - pad, center + 2 * scale, far - pad), fill=rgba, width=line
        )
    elif kind == "fan":
        blade = canvas_size * 0.30
        draw.ellipse((center - line, pad, center + line, pad + blade), fill=rgba)
        draw.ellipse((far - blade, center - line, far, center + line), fill=rgba)
        draw.ellipse((center - line, far - blade, center + line, far), fill=rgba)
        draw.ellipse((pad, center - line, pad + blade, center + line), fill=rgba)
        draw.ellipse((center - line, center - line, center + line, center + line), fill=rgba)
    elif kind == "cover":
        draw.rounded_rectangle((pad, pad, far, far), radius=line, outline=rgba, width=line)
        for row in (0.32, 0.50, 0.68):
            y = round(canvas_size * row)
            draw.line((pad + line, y, far - line, y), fill=rgba, width=line)
    elif kind == "switch":
        top = round(canvas_size * 0.30)
        bottom = round(canvas_size * 0.70)
        draw.rounded_rectangle(
            (pad, top, far, bottom), radius=(bottom - top) // 2, outline=rgba, width=line
        )
        knob_radius = round((bottom - top) * 0.30)
        knob_x = round(canvas_size * 0.37)
        draw.ellipse(
            (
                knob_x - knob_radius,
                center - knob_radius,
                knob_x + knob_radius,
                center + knob_radius,
            ),
            fill=rgba,
        )
    elif kind == "climate":
        stem_width = round(canvas_size * 0.20)
        draw.rounded_rectangle(
            (center - stem_width, pad, center + stem_width, far - 3 * scale),
            radius=stem_width,
            outline=rgba,
            width=line,
        )
        draw.line((center, center * 0.65, center, far - 2 * scale), fill=rgba, width=line)
        draw.ellipse((center - 3 * scale, far - 6 * scale, center + 3 * scale, far), fill=rgba)
    elif kind == "lock":
        draw.arc(
            (center - 4 * scale, pad, center + 4 * scale, center + 2 * scale),
            180,
            360,
            fill=rgba,
            width=line,
        )
        draw.line(
            (center - 4 * scale, center * 0.65, center - 4 * scale, center), fill=rgba, width=line
        )
        draw.line(
            (center + 4 * scale, center * 0.65, center + 4 * scale, center), fill=rgba, width=line
        )
        draw.rounded_rectangle((pad * 2, center, far - pad, far), radius=line, fill=rgba)
    elif kind == "media_player":
        draw.polygon(
            [(pad * 2, pad), (far, center), (pad * 2, far)],
            fill=rgba,
        )
    elif kind in ("number",):
        third = canvas_size / 3
        draw.line((third, pad, third - scale, far), fill=rgba, width=line)
        draw.line((2 * third + scale, pad, 2 * third, far), fill=rgba, width=line)
        draw.line((pad, third, far, third), fill=rgba, width=line)
        draw.line((pad, 2 * third, far, 2 * third), fill=rgba, width=line)
    elif kind in ("scene",):
        draw.polygon(_star_points(center, center - pad, center * 0.22), fill=rgba)
    elif kind in ("script", "button"):
        draw.rounded_rectangle((pad, pad, far, far), radius=2 * line, outline=rgba, width=line)
        draw.polygon(
            [
                (center - 2 * scale, center - 4 * scale),
                (center + 4 * scale, center),
                (center - 2 * scale, center + 4 * scale),
            ],
            fill=rgba,
        )
    else:
        draw.polygon(
            [
                (pad, center),
                (center, pad),
                (far, center),
                (far - pad, center),
                (far - pad, far),
                (pad * 2, far),
                (pad * 2, center),
            ],
            outline=rgba,
        )

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    image = image.resize((size, size), resampling)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


async def async_upload_icons(client: AsyncBusyBar, domains: set[str], accent_color: str) -> None:
    """Upload only the icons needed by this dashboard configuration."""
    for domain in sorted(domains | {"device"}):
        for display, size, color in (
            (types.DisplayName.FRONT, 12, accent_color),
            (types.DisplayName.BACK, 40, "#FFFFFF"),
        ):
            await client.assets_upload(
                application_name=APPLICATION_NAME,
                filename=icon_asset_path(display, domain),
                data=icon_png(domain, size, color),
            )
