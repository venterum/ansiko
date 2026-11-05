# Changelog

## 0.2.0

- Bundled boards and widgets are now shipped inside the wheel, so
  `uv tool install ./server` works outside a checkout. A source checkout still
  uses the top-level `boards/` and `widgets/` directories.
- Android version aligned with the server (`0.2.0`), release signing reads an
  ignored `android/keystore.properties`, and the settings screen shows the
  installed version.
- Fixed reconnect at the same grid size leaving the phone blank: the daemon now
  asks the foreground process group to redraw after a display reset.
- A failed `ansiko run` no longer stops an active board first, and the CLI
  returns the remote program's exit code (including signal conventions).
- Bundled boards cannot be renamed or deleted in place from the dashboard; use
  Duplicate and edit the copy.
- Fixed the missing `currency` widget in the bundled `board` example, renamed
  the duplicate `demo` title, and replaced external-tool clocks in bundled
  boards with the dependency-free `clock`.
- `weather` now uses Open-Meteo with a cache and a configurable location instead
  of a static forecast. `music` and `music-art` explain missing `playerctl` or
  Pillow without marking the cell as an error.
- Night dimming checks the clock every minute while the display is visible, so
  it now switches at 22:00 and 08:00 without an activity restart. Added
  lock-screen display, screen wake, boot receiver and optional kiosk mode.
- Dashboard hides Rename/Delete for bundled boards and shows validation errors.
- Added server regression tests, bundled-resource checks, Android unit-test CI,
  wheel resource checks, release documentation and packaging metadata.

## 0.1.0

- Initial daemon, web dashboard, board editor and Android display client.
