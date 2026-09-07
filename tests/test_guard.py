import importlib.util
import ipaddress
import json
from pathlib import Path
import socket
import struct
import subprocess
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/opnsense/scripts/IPv6HA'))
spec = importlib.util.spec_from_file_location('ipv6_ha', Path(__file__).resolve().parents[1] / 'src/opnsense/scripts/IPv6HA/guard.py')
ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ha)

PD = '2001:db8:1200:3400::/60'
LIVE = '\tinet6 2001:db8:1200:3400::2 prefixlen 64 pltime 100 vltime 200'


class Result:
    def __init__(self, stdout):
        self.stdout = stdout


def guard_with(c, prefix=PD):
    guard = ha.Guard.__new__(ha.Guard)
    guard.c = c
    guard.prefix_file = type('Prefix', (), {'read_text': lambda self: prefix})()
    return guard


def master_run(lan, wan='flags=<UP,BROADCAST,RUNNING,MULTICAST>\n'):
    def fake_run(*args, **kwargs):
        if args[:2] == ('/sbin/ifconfig', 'vtnet0'):
            return Result(lan)
        if args[:3] == ('/sbin/sysctl', '-n', 'net.inet.carp.allow'):
            return Result('1\n')
        if args[:2] == ('/sbin/ifconfig', 'vtnet1'):
            return Result(wan)
        if args[:5] == ('/sbin/route', '-n', 'get', '-inet6', 'default'):
            return Result('interface: vtnet1\n')
        raise AssertionError('Unexpected command: ' + repr(args))
    return fake_run


class FailoverTests(unittest.TestCase):
    def test_standby_does_not_query_the_uplink(self):
        guard = guard_with({'lan': 'vtnet0', 'wan': 'pppoe0', 'vhid': 9, 'maintenance': False})
        lan = 'status: active\ncarp: BACKUP vhid 9 advbase 1 advskew 100\n'

        def fake_run(*args, **kwargs):
            if args[:2] == ('/sbin/ifconfig', 'vtnet0'):
                return Result(lan)
            if args[:3] == ('/sbin/sysctl', '-n', 'net.inet.carp.allow'):
                return Result('1\n')
            raise AssertionError('Standby queried active uplink state: ' + repr(args))

        with patch.object(ha, 'run', side_effect=fake_run):
            state = guard.snapshot()
        self.assertEqual(state['carp'], 'BACKUP')
        self.assertIsNone(state['uplink_up'])
        self.assertFalse(state['ready'])
        self.assertEqual(state['reason'], 'Standby; waiting for CARP takeover')

    def test_master_accepts_a_non_pppoe_dynamic_uplink(self):
        guard = guard_with({'lan': 'vtnet0', 'wan': 'vtnet1', 'vhid': 9, 'maintenance': False})
        lan = 'status: active\ncarp: MASTER vhid 9 advbase 1 advskew 0\n' + LIVE + '\n'
        with patch.object(ha, 'run', side_effect=master_run(lan)):
            state = guard.snapshot()
        self.assertTrue(state['uplink_up'])
        self.assertTrue(state['ready'])
        self.assertEqual(state['reason'], 'Uplink, PD and route ready')

    def test_bridge_without_media_status_is_usable(self):
        guard = guard_with({'lan': 'vtnet0', 'wan': 'vtnet1', 'vhid': 9, 'maintenance': False})
        bridge = 'groups: bridge\ncarp: MASTER vhid 9 advbase 1 advskew 0\n' + LIVE + '\n'
        with patch.object(ha, 'run', side_effect=master_run(bridge)):
            self.assertTrue(guard.snapshot()['ready'])
        with patch.object(ha, 'run', side_effect=master_run(bridge.replace('groups: bridge', 'status: no carrier'))):
            self.assertEqual(guard.snapshot()['reason'], 'LAN or CARP unavailable')

    def test_missing_prefix_file_and_command_timeouts_are_reported(self):
        guard = guard_with({'lan': 'vtnet0', 'wan': 'vtnet1', 'vhid': 9, 'maintenance': False})
        lan = 'status: active\ncarp: MASTER vhid 9 advbase 1 advskew 0\n' + LIVE + '\n'

        def missing(self):
            raise FileNotFoundError('/tmp/vtnet1_prefixv6')
        guard.prefix_file = type('Prefix', (), {'read_text': missing})()
        with patch.object(ha, 'run', side_effect=master_run(lan)):
            self.assertEqual(guard.snapshot()['reason'], 'No delegated prefix on the uplink')
        with patch.object(ha, 'run', side_effect=subprocess.TimeoutExpired('ifconfig', 4)):
            state = guard.snapshot()
        self.assertFalse(state['ready'])
        self.assertEqual(state['reason'], 'System command timed out')

    def test_pd_validation_rejects_stale_tentative_and_multiple_prefixes(self):
        self.assertEqual(ha.pd_address(LIVE, PD)[1], '2001:db8:1200:3400::/64')
        for text in (LIVE.replace('3400', '3300'), LIVE + ' tentative', LIVE + ' deprecated',
                     LIVE + '\n' + LIVE.replace('::2', '::3')):
            with self.assertRaises(ValueError):
                ha.pd_address(text, PD)

    def test_several_delegated_prefixes_are_accepted(self):
        self.assertEqual(ha.pd_address(LIVE, '2001:db8:aaaa::/56\n' + PD + '\n')[1], '2001:db8:1200:3400::/64')
        with self.assertRaisesRegex(ValueError, 'No delegated prefix'):
            ha.pd_address(LIVE, '\n')
        with self.assertRaisesRegex(ValueError, 'not global unicast'):
            ha.pd_address(LIVE, 'fd00::/48')

    def test_vhid_selection_is_exact(self):
        text = 'carp: MASTER vhid 8 advbase 1 advskew 0\n BACKUP vhid 9 advbase 1 advskew 100'
        self.assertEqual(ha.carp_state(text, 9), ('BACKUP', 100))
        self.assertEqual(ha.carp_state(text, 1), ('MISSING', None))

    def test_ra_parsing_ignores_withdrawals_and_malformed_options(self):
        head = b'\x86\x00' + b'\x00' * 14
        prefix = ipaddress.IPv6Address('2001:db8:1200:3400::').packed
        option = struct.pack('!BBBBIII', 3, 4, 64, 0xc0, 300, 60, 0) + prefix
        self.assertEqual(ha.parse_ra(head + option), [('2001:db8:1200:3400::/64', 300)])
        self.assertEqual(ha.parse_ra(head + option[:8] + b'\x00' * 4 + option[12:]), [])
        self.assertEqual(ha.parse_ra(head + b'\x03\x00'), [])
        self.assertEqual(ha.parse_ra(head + option[:-1]), [])

    def test_old_prefix_is_not_repreferred_or_created(self):
        config = ha.render({'lan': 'vtnet0', 'vip': 'fe80::', 'mtu': 1492},
                           '2001:db8:1200:3400::/64', ['2001:db8:1200:3410::/64'])
        self.assertEqual(config.count('AdvPreferredLifetime 60;'), 1)
        self.assertEqual(config.count('AdvPreferredLifetime 0;'), 1)
        self.assertIn('AdvValidLifetime 0;', config)
        self.assertIn('RemoveAdvOnExit off;', config)


BASE = dict(enabled=True, maintenance=False, lan='vtnet0', wan='pppoe0', lan_interface='lan',
            wan_interface='wan', vip='fe80::1:1', vhid=9, normal_skew=100, mtu=1492,
            min_interval=3, max_interval=10, router_lifetime=30,
            preferred_lifetime=60, valid_lifetime=300, source_hash='a' * 64)


class ControlSocketTests(unittest.TestCase):
    def test_reload_adopts_compatible_changes_and_requests_restart_otherwise(self):
        guard = guard_with(dict(BASE))
        for change, restart in [({'maintenance': True}, False), ({'valid_lifetime': 600, 'source_hash': 'b' * 64}, False),
                                ({'vip': 'fe80::1:2'}, True), ({'lan': 'vtnet2'}, True), ({'enabled': False}, True)]:
            with self.subTest(change=change), patch.object(ha.Path, 'read_text', return_value=json.dumps({**BASE, **change})):
                reply = guard.reload()
            self.assertEqual(reply, {'status': 'ok', 'restart': restart})
            if not restart:
                self.assertEqual(guard.c, {**BASE, **change})
        guard.c = dict(BASE)
        with patch.object(ha.Path, 'read_text', return_value=json.dumps({**BASE, 'mtu': 'broken'})), self.assertRaises(ValueError):
            guard.reload()
        self.assertEqual(guard.c, BASE)

    def test_status_reply_carries_source_hash_and_age(self):
        guard = guard_with(dict(BASE))
        guard.status = {'carp': 'BACKUP', 'ready': False, 'ra_running': False, 'reason': 'Standby; waiting for CARP takeover'}
        guard.last_tick = None
        reply = guard.status_reply()
        self.assertEqual(reply['source_hash'], 'a' * 64)
        self.assertIsNone(reply['age_seconds'])
        self.assertEqual(reply['carp'], 'BACKUP')

    def exchange(self, guard, payload):
        server, client = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        with client:
            client.sendall(payload)
            needs_tick = ha.handle_client(server, guard)
            reply = json.loads(client.recv(65536).decode())
        return reply, needs_tick

    def test_socket_protocol(self):
        class Stub:
            def status_reply(self):
                return {'carp': 'MASTER', 'source_hash': 'a' * 64}

            def snapshot(self):
                return {'carp': 'MASTER', 'ready': True}

            def reload(self):
                return {'status': 'ok', 'restart': False}

        stub = Stub()
        reply, tick = self.exchange(stub, b'{"command": "status"}\n')
        self.assertEqual(reply, {'status': 'ok', 'carp': 'MASTER', 'source_hash': 'a' * 64})
        self.assertFalse(tick)
        reply, tick = self.exchange(stub, b'{"command": "check"}\n')
        self.assertEqual(reply['ready'], True)
        self.assertFalse(tick)
        reply, tick = self.exchange(stub, b'{"command": "wake"}\n')
        self.assertEqual(reply, {'status': 'ok'})
        self.assertTrue(tick)
        reply, tick = self.exchange(stub, b'{"command": "reload"}\n')
        self.assertEqual(reply, {'status': 'ok', 'restart': False})
        self.assertTrue(tick)
        for payload in (b'{"command": "shutdown"}\n', b'not json\n', b'[1]\n'):
            reply, tick = self.exchange(stub, payload)
            self.assertEqual(reply['status'], 'failed')
            self.assertFalse(tick)


if __name__ == '__main__':
    unittest.main()
