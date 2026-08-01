# Standalone BUSY UI studies

These three demos use local fake accessories. They never call Home Assistant:

- `grid`: four accessories stay visible; the dial moves the highlight, Select
  opens the device, Start toggles it, and the dial changes brightness.
- `capabilities`: Select opens a property list for Brightness, Color, and Color
  temperature. Dial chooses a property, Select edits it, and Dial changes it.
- `focus`: one accessory and a 56-pixel icon dominate the OLED; Dial moves the
  carousel, Select enters dimming, and Start toggles power.

All layouts use stable Canvas element IDs, so ordinary input never reveals or
controls the app underneath. BUSY firmware reserves Back for closing Canvas,
so Back exits each demo. Select moves back up within a demo.

Temporarily disable the Home Assistant BUSY Bar integration before interactive
hardware testing, because both clients otherwise receive the same input stream.
Then keep the physical selector on Apps and run:

```bash
export BUSY_BAR_ADDR="192.168.1.227"
export BUSY_HTTP_PASSWORD="your-local-api-key"

uv run python -m demos.busybar_ui --demo grid
uv run python -m demos.busybar_ui --demo capabilities
uv run python -m demos.busybar_ui --demo focus
```

For visual work while another input client is running, open a deeper screen
without touching the hardware controls:

```bash
uv run python -m demos.busybar_ui --demo grid --view control
uv run python -m demos.busybar_ui --demo capabilities --view properties
uv run python -m demos.busybar_ui --demo capabilities --view edit
```

After the first launch, add `--skip-assets` to reuse the uploaded icon set and
make layout iterations start almost immediately.

The first launch uploads bold icons in 14, 16, 32, and 56 pixel sizes. Assets
are isolated under the `home_ui_demo` namespace and the runner clears only that
namespace when it exits.
