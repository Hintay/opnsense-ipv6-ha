import importlib.util
import ipaddress
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src/opnsense/scripts/IPv6HA'))
spec = importlib.util.spec_from_file_location('ipv6_ha', Path(__file__).resolve().parents[1] / 'src/opnsense/scripts/IPv6HA/guard.py')
ha = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ha)


class FailoverTests(unittest.TestCase):
    def test_standby_does_not_query_the_uplink(self):
        guard = ha.Guard.__new__(ha.Guard)
        guard.c = {'lan': 'vtnet0', 'wan': 'pppoe0', 'vhid': 9, 'maintenance': False}
        lan = 'status: active\ncarp: BACKUP vhid 9 advbase 1 advskew 100\n'

        def fake_run(*args, **kwargs):
            if args[:2] == ('/sbin/ifconfig', 'vtnet0'):
                return type('Result', (), {'stdout': lan})()
            if args[:3] == ('/sbin/sysctl', '-n', 'net.inet.carp.allow'):
                return type('Result', (), {'stdout': '1\n'})()
            raise AssertionError('Standby queried active uplink state: ' + repr(args))

        with patch.object(ha, 'run', side_effect=fake_run):
            state = guard.snapshot()
        self.assertEqual(state['carp'], 'BACKUP')
        self.assertIsNone(state['uplink_up'])
        self.assertFalse(state['ready'])
        self.assertEqual(state['reason'], 'Standby; waiting for CARP takeover')

    def test_master_accepts_a_non_pppoe_dynamic_uplink(self):
        guard = ha.Guard.__new__(ha.Guard)
        guard.c = {'lan': 'vtnet0', 'wan': 'vtnet1', 'vhid': 9, 'maintenance': False}
        guard.prefix_file = type('Prefix', (), {'read_text': lambda self: '2001:db8:1200:3400::/60'})()
        lan = ('status: active\ncarp: MASTER vhid 9 advbase 1 advskew 0\n'
               '\tinet6 2001:db8:1200:3400::2 prefixlen 64 pltime 100 vltime 200\n')

        def fake_run(*args, **kwargs):
            if args[:2] == ('/sbin/ifconfig', 'vtnet0'):
                return type('Result', (), {'stdout': lan})()
            if args[:3] == ('/sbin/sysctl', '-n', 'net.inet.carp.allow'):
                return type('Result', (), {'stdout': '1\n'})()
            if args[:2] == ('/sbin/ifconfig', 'vtnet1'):
                return type('Result', (), {'stdout': 'flags=<UP,BROADCAST,RUNNING,MULTICAST>\n'})()
            if args[:5] == ('/sbin/route', '-n', 'get', '-inet6', 'default'):
                return type('Result', (), {'stdout': 'interface: vtnet1\n'})()
            raise AssertionError('Unexpected command: ' + repr(args))

        with patch.object(ha, 'run', side_effect=fake_run):
            state = guard.snapshot()
        self.assertTrue(state['uplink_up'])
        self.assertTrue(state['ready'])
        self.assertEqual(state['reason'], 'Uplink, PD and route ready')

    def test_pd_validation_rejects_stale_tentative_and_multiple_prefixes(self):
        live = '\tinet6 2001:db8:1200:3400::2 prefixlen 64 pltime 100 vltime 200'
        self.assertEqual(ha.pd_address(live, '2001:db8:1200:3400::/60')[1], '2001:db8:1200:3400::/64')
        for text in (live.replace('3400', '3300'), live + ' tentative', live + ' deprecated',
                     live + '\n' + live.replace('::2', '::3')):
            with self.assertRaises(ValueError):
                ha.pd_address(text, '2001:db8:1200:3400::/60')

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


if __name__ == '__main__':
    unittest.main()
