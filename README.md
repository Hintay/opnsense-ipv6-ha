# OPNsense IPv6 High Availability

[简体中文](README.zh-CN.md)

OPNsense IPv6 HA coordinates Router Advertisements on a CARP pair that receives dynamic DHCPv6 Prefix Delegation (PD). The active node advertises its current delegated prefix, while the standby node remains silent and learns prefixes that may need to be withdrawn after a role change.

This is a community plugin and is not part of the official OPNsense plugin collection.

Release 1.1 targets OPNsense 26.7 on FreeBSD 15 amd64.

## Features

- Follows CARP role changes and local dynamic-uplink events.
- Supports PPPoE and other uplinks that provide DHCPv6-PD to OPNsense.
- Reuses the Router Advertisements configuration already provided by OPNsense.
- Withdraws recently observed prefixes after a role change.
- Provides an OPNsense MVC page, service controls, API endpoints, ACLs, and native log tables.
- Includes English and Simplified Chinese interface text.
- Does not probe public IPv6 hosts or manage dial-up sessions.

## Scope and limitations

Dynamic PD cannot provide connection-preserving failover. A replacement uplink may receive a different prefix, so existing IPv6 connections can break and clients may need time to adopt the new prefix.

The plugin controls Router Advertisements only. CARP, DHCPv6-PD, firewall rules, state synchronization, routing, and uplink connectivity must already work on both nodes. A network partition can still produce two CARP masters unless the deployment has suitable external safeguards.

## Requirements

- Two OPNsense nodes in a working CARP configuration.
- A dynamic uplink on each node that can obtain DHCPv6-PD after takeover.
- LAN IPv6 configured to track that upstream interface.
- A dedicated link-local IPv6 CARP address on the LAN.
- A Router Advertisements entry for the LAN with its **Enable** option turned off.
- Router Advertisements excluded from XMLRPC configuration synchronization.
- `radvd`, installed automatically as a package dependency.

When PPPoE should connect or disconnect with the CARP role, configure that behavior in OPNsense. The plugin does not create, retain, or terminate PPPoE sessions.

## Installation

Download `os-ipv6-ha-1.1.pkg` from the GitHub release and copy it to the firewall. The matching `os-ipv6-ha-1.1.pkg.dgst` file is optional and can be used to verify the download:

```sh
FILE=os-ipv6-ha-1.1.pkg
for METHOD in md5 sha1 sha256 sha512; do
  openssl dgst "-${METHOD}" "$FILE" | sed 's/([^)]*)//g'
done | diff -u "$FILE.dgst" -
```

Install the package:

```sh
pkg add -f ./os-ipv6-ha-1.1.pkg
```

Install the package on both nodes. Configure the standby node first, then the active node.

## Configuration

1. Open **Services → IPv6 HA**.
2. Select the LAN that tracks the delegated prefix.
3. Review the Router Advertisements settings shown on the same page.
4. Save the configuration on each node separately.
5. Enable IPv6 HA after both nodes pass **Check configuration**.

The plugin deliberately keeps its configuration local to each node. It does not add its own settings to XMLRPC synchronization.

At runtime, Router Advertisements are sent only when all of the following are true:

- the selected IPv6 CARP address is `MASTER`;
- the upstream interface is available;
- the LAN has exactly one usable `/64` from the current delegated prefix;
- the IPv6 default route uses that upstream interface;
- maintenance mode is off.

The service responds immediately to CARP and uplink events. A 30-second watchdog covers missed local events; it is not a public-connectivity probe.

Prefix lifetimes are capped: the preferred lifetime may not exceed 3600 seconds and the valid lifetime may not exceed 7200 seconds. RFC 4862 lets hosts ignore a shorter valid lifetime while more than two hours remain, so longer values would make prefix withdrawal after a takeover ineffective. Empty lifetime fields default to 1800 and 3600 seconds.

## Operation

```sh
configctl ipv6ha status
configctl ipv6ha check
configctl ipv6ha apply
pkg check -s os-ipv6-ha
```

Saving or applying settings reloads the running service in place. The service is restarted only when the LAN, the uplink, the CARP address or the VHID changes.

The service answers status queries on `/var/run/ipv6-ha.sock`. The plugin page and `configctl ipv6ha status` use this socket, so a stopped service is reported as stopped rather than as stale data.

Logs are available from the plugin page and in `/var/log/ipv6ha/`. Messages from the plugin's own `radvd` instance appear in the system log under the program name `radvd`.

Maintenance mode stops Router Advertisements on the current node without changing CARP or uplink settings. Stopping the plugin service has the same network scope.

## Upgrade and removal

Install a newer package with `pkg add -f`. Existing plugin and Router Advertisements settings are retained.

Before removing the package, make sure another router is providing the required IPv6 service. Removal stops the plugin and leaves the OPNsense Router Advertisements entry disabled:

```sh
pkg delete -y os-ipv6-ha
```

## Building

The standard OPNsense plugin build system is the preferred build environment. Place this repository in the OPNsense plugins tree and run the plugin package target, or run the standalone builder on FreeBSD/OPNsense:

```sh
python3 tools/build.py
```

The generated package is written to `dist/`. On stock FreeBSD builders, set `OPNSENSE_VERSION` so the package manifest records its target OPNsense dependency.

## Development

Generic tests are in `tests/`. Some integration tests require an installed OPNsense MVC framework and must run directly on an isolated OPNsense test system.

Interface text uses gettext with the plugin's own text domain `os-ipv6-ha`, because strings of community plugins are not part of the OPNsense language packages. Source strings are English; translations live in `locale/`. After changing user-visible text:

```sh
python3 tools/i18n.py extract
python3 tools/i18n.py update
python3 tools/i18n.py compile
```

Edit `locale/<language>.po` between `update` and `compile`. The compiled `.mo` files under `src/share/locale/` are committed so that both build paths ship them; `python3 tools/i18n.py check` fails when they are out of date. Any PO editor or a Weblate project pointed at `locale/` can be used for translation.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines and [SECURITY.md](SECURITY.md) for vulnerability reports.

## License

BSD 2-Clause. See [LICENSE](LICENSE).

## References

- [OPNsense High Availability](https://docs.opnsense.org/manual/hacarp.html)
- [OPNsense plugin development](https://docs.opnsense.org/development/plugins.html)
- [OPNsense configd](https://docs.opnsense.org/development/backend/configd.html)
