# Changelog

All notable changes to this project will be documented in this file.

## 1.1

- Serve status, check, wake and reload requests on a Unix control socket; the status page no longer runs a configuration export on every poll.
- Apply reloads the running service in place and restarts it only when the LAN, uplink, CARP address or VHID changes.
- Report "applied" by comparing a hash of the relevant configuration sections with the one the running service carries.
- Use HA-compatible defaults for empty Router Advertisement lifetimes (1800/3600 seconds) instead of values that always failed validation.
- Accept LAN interfaces without a media status line (bridges) and uplinks with several delegated prefixes.
- Return a non-zero exit code from control.py on failure so rc.d and hooks can rely on it; friendlier message when an operation is already running.
- Keep the service alive while interfaces are still missing at boot; report command timeouts instead of crashing.
- Package scripts follow the official plugins.mk layout so both build paths install identically; private migration residue removed.
- Poll the status page every 10 seconds, pause while the tab is hidden and back off on errors.
- Translate the interface with gettext in the plugin's own text domain; translations are maintained as PO files under `locale/`.

## 1.0 - Initial public release

- Coordinate Router Advertisements with CARP and dynamic DHCPv6-PD state.
- Reuse the OPNsense Router Advertisements form and diagnostic log table.
- Withdraw recently observed prefixes after role changes.
- Provide English and Simplified Chinese interface text.
- Add FreeBSD-based continuous integration and tagged GitHub releases.
