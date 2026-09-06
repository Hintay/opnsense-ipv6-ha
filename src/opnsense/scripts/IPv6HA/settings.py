"""Validate exported settings again at the privileged process boundary."""
import hashlib
import ipaddress
import json
import re

BOUNDS = {
    'vhid': (1, 255), 'normal_skew': (0, 254), 'mtu': (1280, 9000),
    'min_interval': (3, 450), 'max_interval': (4, 600),
    'router_lifetime': (4, 1800), 'preferred_lifetime': (4, 3600), 'valid_lifetime': (4, 7200),
}


def validate_config(c):
    if c.get('enabled') is False:
        if type(c.get('maintenance')) is not bool:
            raise ValueError('Invalid maintenance setting')
        return c
    for name, (low, high) in BOUNDS.items():
        if type(c.get(name)) is not int or not low <= c[name] <= high:
            raise ValueError(f'Invalid {name}: expected {low}..{high}')
    for name in ('enabled', 'maintenance'):
        if type(c.get(name)) is not bool:
            raise ValueError(f'Invalid {name}')
    for name in ('lan', 'wan', 'lan_interface', 'wan_interface'):
        if not isinstance(c.get(name), str) or not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_.-]{0,31}', c[name]):
            raise ValueError(f'Invalid interface {name}')
    if c['lan'] == c['wan']:
        raise ValueError('LAN and WAN interfaces must differ')
    if '%' in c['vip'] or not ipaddress.IPv6Address(c['vip']).is_link_local:
        raise ValueError('CARP VIP must be link-local')
    if c['min_interval'] > 0.75 * c['max_interval'] or c['router_lifetime'] < c['max_interval']:
        raise ValueError('Invalid Router Advertisement intervals or router lifetime')
    if not c['max_interval'] <= c['preferred_lifetime'] <= c['valid_lifetime']:
        raise ValueError('Invalid prefix lifetimes')
    if 'ra' in c:
        ra = c['ra']
        if ra['mode'] not in ('unmanaged', 'stateless', 'managed', 'assist', 'router'):
            raise ValueError('Invalid Router Advertisement mode')
        if type(ra['hop_limit']) is not int or not 0 <= ra['hop_limit'] <= 255 or ra['preference'] not in ('low', 'medium', 'high'):
            raise ValueError('Invalid Router Advertisement hop limit or preference')
        for key in ('route_lifetime', 'rdnss_lifetime', 'dnssl_lifetime'):
            if type(ra[key]) is not int or not 1 <= ra[key] <= 4294967295:
                raise ValueError('Invalid Router Advertisement lifetime')
        if type(ra['remove_route']) is not bool:
            raise ValueError('Invalid route withdrawal setting')
        for key in ('rdnss', 'routes', 'dnssl'):
            if not isinstance(ra[key], list) or len(ra[key]) > 64:
                raise ValueError('Invalid Router Advertisement list')
        for value in ra['rdnss']:
            if '%' in value:
                raise ValueError('Scoped DNS address is not supported')
            ipaddress.IPv6Address(value)
        for value in ra['routes']:
            ipaddress.IPv6Network(value)
        for value in ra['dnssl']:
            if not re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9.-]{0,251}[a-zA-Z0-9])?\.?', value):
                raise ValueError('Invalid DNS search domain')
        if ra['nat64prefix']:
            prefix = ipaddress.IPv6Network(ra['nat64prefix'])
            if prefix.prefixlen not in (32, 40, 48, 56, 64, 96):
                raise ValueError('Invalid NAT64 prefix length')
    return c


def config_hash(c):
    return hashlib.sha256(json.dumps(c, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
