# Changelog

## 0.1.3

- Accept the button-event shape emitted by physical BUSY firmware, where a
  press omits the optional `action` field. This restores Select and Start.
- Explicitly take over the displays when Home Assistant opens so an app such
  as Spotify cannot leave the dashboard active but invisible.

## 0.1.2

- Follow the physical BUSY Bar mode selector: Apps opens Home Assistant
  automatically, while leaving Apps closes it so built-in screens cannot
  compete for the display.
- Raise the hardware-safe default display priority from 95 to 100 and migrate
  existing entries that still use the old default.
- Let Start toggle the highlighted accessory directly from browse mode; Select
  still enters adjustment mode for dial-based brightness and level control.
- Make `SELECT` / `ADJUST` visible on the front display and speed long-name
  scrolling from 25 to 70 pixels per second with a shorter startup delay.
- Register the input WebSocket as a Home Assistant background task so it no
  longer delays startup.

## 0.1.1

- Use the supplied BUSY / Home Assistant artwork as transparent local HACS
  brand assets at 1× and 2× resolutions.
- Construct the BUSY API client in Home Assistant's executor to avoid blocking
  the event loop while its TLS context is initialized.
- Keep the empty-accessory setup hint stable instead of repeatedly scheduling
  temporary messages.
- Yield cleanly when another BUSY app owns the displays at a higher priority.
- Add controller coverage for every supported Start-button action, all
  dial-adjustable domains, navigation wraparound, and brand assets.

## 0.1.0

- Initial HACS integration with local-push BUSY input, accessory control,
  front/rear pixel dashboard, entities, events, and display actions.
