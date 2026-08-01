"""Basic package metadata tests."""

import json
from pathlib import Path


def test_manifest_is_hacs_ready() -> None:
    root = Path(__file__).parents[1]
    manifest = json.loads((root / "custom_components" / "busybar" / "manifest.json").read_text())

    assert manifest["domain"] == "busybar"
    assert manifest["config_flow"] is True
    assert manifest["iot_class"] == "local_push"
    assert manifest["version"]
    assert manifest["requirements"] == ["busylib==1.0.0"]
