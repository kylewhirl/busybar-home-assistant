# BUSY Bar for Home Assistant

Turn a [BUSY Bar](https://busybar.app) into a tactile Home Assistant controller
and two-screen pixel dashboard. Everything runs locally: Home Assistant talks
directly to the bar's HTTP and WebSocket APIs through the official
[`busylib`](https://github.com/busy-app/busylib-py) Python client.

## The interaction

The bar behaves like a tiny, physical Home Assistant app:

1. Press **Select** (`OK`) to enter Home Assistant.
2. Turn the **dial** to browse your chosen accessories.
3. Press **Select** again to open an accessory.
4. Turn the **dial** to adjust it.
5. Press the large **Start** button to toggle or activate it.
6. Press **Back** to return to the accessory list, then Back again to exit.

Both BUSY displays update throughout the flow. The front RGB matrix gives you
an at-a-glance icon, state, and level; the rear OLED shows a larger device-type
icon, friendly name, state, position in the list, and contextual control hints.
The display also follows changes made elsewhere in Home Assistant.

## Accessory support

| Home Assistant domain | Dial in control view | Start button |
| --- | --- | --- |
| `light` | Brightness | Toggle |
| `fan` | Percentage | Toggle |
| `cover` | Position | Open / close |
| `media_player` | Volume | Play / pause |
| `number`, `input_number` | Value | — |
| `climate` | Target temperature in 0.5° steps | On / off |
| `switch`, `input_boolean` | — | Toggle |
| `lock` | — | Lock / unlock |
| `scene`, `script`, `button` | — | Activate |

The option picker is deliberately ordered: the order you choose accessories
is the order shown when turning the dial.

## Installation

### HACS custom repository

1. In HACS, open **Custom repositories**.
2. Add `https://github.com/kylewhirl/busybar-home-assistant` as an
   **Integration**.
3. Install **BUSY Bar**, restart Home Assistant, then clear the browser cache.

### Manual

Copy `custom_components/busybar` into your Home Assistant configuration's
`custom_components` directory and restart Home Assistant.

## Setup

1. On the BUSY Bar, enable its Wi-Fi HTTP API and set an access key.
2. In Home Assistant, go to **Settings → Devices & services → Add integration**.
3. Search for **BUSY Bar**.
4. Enter the bar's local IP address and HTTP API access key.
5. Open the integration's **Configure** dialog and select the accessories you
   want on the dial.

Use a DHCP reservation so the BUSY Bar keeps the same local IP. The access key
is stored in the Home Assistant config entry and is never sent to this project
or a cloud service.

## Home Assistant entities

The integration creates:

- Connectivity, battery, firmware, navigation-state, and selected-accessory
  sensors.
- A Dashboard switch for opening or closing the Home Assistant UI remotely.
- Display brightness control.
- Previous, next, and refresh buttons for automations and dashboards.

It also emits a `busybar_input` event for every button, dial, and mode-switch
input, so advanced automations can use the hardware directly.

## Actions

```yaml
action: busybar.show_message
data:
  text: Someone is at the front door
  color: "#FFB000"
  duration: 5
```

Also available:

- `busybar.clear_display`
- `busybar.refresh_dashboard`

If more than one bar is configured, pass `config_entry_id` to target one.

## Design notes

- Polling is used only for slow diagnostics such as battery and firmware.
- Dial and button input is local push over the BUSY WebSocket stream.
- Home Assistant remains authoritative: selected entity state changes trigger
  a display redraw.
- Display elements use the integration-owned `home_assistant` application
  namespace so exiting or unloading does not delete another app's assets.
- Device-type icons are generated in memory during setup and uploaded into the
  integration's own BUSY asset namespace; there are no external icon files to
  install or keep in sync.

## Development

```bash
uv sync --dev
uv run ruff check .
uv run pytest
```

The repository runs Ruff, tests, Hassfest, and HACS validation in GitHub
Actions. This project is not affiliated with Home Assistant or Flipper Devices.

## License

MIT
