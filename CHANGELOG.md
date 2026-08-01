# Changelog

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
