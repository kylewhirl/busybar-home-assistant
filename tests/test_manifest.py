"""Basic package metadata tests."""

import json
from pathlib import Path

from PIL import Image


def test_manifest_is_hacs_ready() -> None:
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "custom_components" / "busybar" / "manifest.json").read_text())

    assert manifest["domain"] == "busybar"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "local_push"
    assert manifest["version"]
    assert manifest["requirements"] == [
        "busylib==1.0.0",
        "material-design-icons-pack==7.4.47",
        "resvg_py==0.3.3",
    ]


def test_local_brand_icons_have_transparent_background() -> None:
    brand = Path(__file__).parents[1] / "custom_components" / "busybar" / "brand"

    for filename, expected_size in (("icon.png", (256, 256)), ("icon@2x.png", (512, 512))):
        with Image.open(brand / filename) as image:
            assert image.mode == "RGBA"
            assert image.size == expected_size
            assert image.getpixel((0, 0))[3] == 0
            assert image.getbbox() != (0, 0, *expected_size)
