# Standalone BUSY Home UI flow

This is one Home Assistant controller with local fake accessories. It never
calls Home Assistant. Its two screens form one navigation stack:

1. **Accessories:** four devices are visible at once. Turn the dial to move the
   mint highlight and press Select to open the selected accessory.
2. **Device controls:** a large device icon and Brightness, RGB color, and Color
   temperature remain visible together. Turn the dial to choose one, press
   Select to edit it, turn the dial to change its value, and press Select again
   to finish.

Start toggles the selected accessory at every depth. Back exits the standalone
Canvas app. Every screen uses the same Canvas element IDs, so normal input does
not reveal or control the app underneath.

Temporarily disable the Home Assistant BUSY Bar integration before interactive
hardware testing, because both clients otherwise receive the same input stream.
Then keep the physical selector on Apps and run:

```bash
export BUSY_BAR_ADDR="192.168.1.227"
export BUSY_HTTP_PASSWORD="your-local-api-key"

uv run python -m demos.busybar_ui
```

For visual development without sending device input, open directly to a screen:

```bash
uv run python -m demos.busybar_ui --view browse
uv run python -m demos.busybar_ui --view properties
uv run python -m demos.busybar_ui --view edit
```

After the first launch, add `--skip-assets` to reuse the uploaded icon set.
Assets are isolated under the `home_ui_demo` namespace and the runner clears
only that namespace when it exits.
