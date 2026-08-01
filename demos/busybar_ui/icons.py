"""Bold, large pixel-display assets for the standalone UI studies."""

from __future__ import annotations

import io
import math

from busylib import AsyncBusyBar
from PIL import Image, ImageColor, ImageDraw

APPLICATION_NAME = "home_ui_demo"
ICON_KINDS = ("light", "desk_lamp", "fan", "plug")
ICON_SIZES = (14, 16, 32, 56)
FRONT_ACCENT = "#63E6BE"


def asset_path(kind: str, size: int) -> str:
    return f"demo_{kind}_{size}.png"


def _scaled_icon(kind: str, size: int, color: str) -> bytes:
    """Draw an unmistakable filled silhouette with enough pixels to read."""
    scale = 4
    side = size * scale
    image = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    rgba = (*ImageColor.getrgb(color), 255)
    stroke = max(scale * 2, side // 12)
    center = side // 2
    margin = max(scale, side // 14)

    if kind == "light":
        radius = side * 0.27
        cy = side * 0.40
        if size >= 32:
            for angle in range(-150, 31, 45):
                radians = math.radians(angle)
                inner = side * 0.38
                outer = side * 0.47
                draw.line(
                    (
                        center + math.cos(radians) * inner,
                        cy + math.sin(radians) * inner,
                        center + math.cos(radians) * outer,
                        cy + math.sin(radians) * outer,
                    ),
                    fill=rgba,
                    width=stroke,
                )
        draw.ellipse(
            (center - radius, cy - radius, center + radius, cy + radius),
            fill=rgba,
        )
        neck_top = int(cy + radius * 0.55)
        draw.polygon(
            [
                (int(center - radius * 0.62), neck_top),
                (int(center + radius * 0.62), neck_top),
                (int(center + radius * 0.38), int(side * 0.77)),
                (int(center - radius * 0.38), int(side * 0.77)),
            ],
            fill=rgba,
        )
        draw.rounded_rectangle(
            (int(side * 0.36), int(side * 0.73), int(side * 0.64), int(side * 0.88)),
            radius=stroke // 2,
            fill=rgba,
        )
    elif kind == "desk_lamp":
        draw.polygon(
            [
                (margin, int(side * 0.40)),
                (int(side * 0.53), int(side * 0.22)),
                (int(side * 0.66), int(side * 0.48)),
                (int(side * 0.26), int(side * 0.58)),
            ],
            fill=rgba,
        )
        draw.line(
            (int(side * 0.55), int(side * 0.46), int(side * 0.72), int(side * 0.78)),
            fill=rgba,
            width=stroke,
        )
        draw.line(
            (int(side * 0.72), int(side * 0.78), int(side * 0.47), int(side * 0.88)),
            fill=rgba,
            width=stroke,
        )
        draw.rounded_rectangle(
            (int(side * 0.38), int(side * 0.83), int(side * 0.88), int(side * 0.94)),
            radius=stroke // 2,
            fill=rgba,
        )
    elif kind == "fan":
        blade = side * 0.34
        draw.ellipse((center - stroke, margin, center + stroke, margin + blade), fill=rgba)
        draw.ellipse(
            (side - margin - blade, center - stroke, side - margin, center + stroke), fill=rgba
        )
        draw.ellipse(
            (center - stroke, side - margin - blade, center + stroke, side - margin), fill=rgba
        )
        draw.ellipse((margin, center - stroke, margin + blade, center + stroke), fill=rgba)
        draw.ellipse(
            (
                center - stroke * 1.4,
                center - stroke * 1.4,
                center + stroke * 1.4,
                center + stroke * 1.4,
            ),
            fill=rgba,
        )
    else:
        body = (int(side * 0.22), int(side * 0.30), int(side * 0.78), int(side * 0.76))
        draw.rounded_rectangle(body, radius=stroke, fill=rgba)
        draw.rectangle(
            (int(side * 0.34), margin, int(side * 0.43), int(side * 0.34)), fill=rgba
        )
        draw.rectangle(
            (int(side * 0.57), margin, int(side * 0.66), int(side * 0.34)), fill=rgba
        )
        draw.line(
            (center, int(side * 0.72), center, side - margin), fill=rgba, width=stroke
        )

    resampling = getattr(Image, "Resampling", Image).LANCZOS
    image = image.resize((size, size), resampling)
    output = io.BytesIO()
    image.save(output, "PNG", optimize=True)
    return output.getvalue()


def blank_png() -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (1, 1), (0, 0, 0, 0)).save(output, "PNG")
    return output.getvalue()


async def upload_demo_assets(client: AsyncBusyBar) -> None:
    """Upload every size used by the three layouts."""
    await client.assets_upload(
        application_name=APPLICATION_NAME,
        filename="demo_blank.png",
        data=blank_png(),
    )
    for kind in ICON_KINDS:
        for size in ICON_SIZES:
            await client.assets_upload(
                application_name=APPLICATION_NAME,
                filename=asset_path(kind, size),
                data=_scaled_icon(kind, size, FRONT_ACCENT if size == 14 else "#FFFFFF"),
            )
