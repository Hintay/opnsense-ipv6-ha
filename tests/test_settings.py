import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'src/opnsense/scripts/IPv6HA'
sys.path.insert(0, str(ROOT))
from settings import validate_config
import control
from guard import render

BASE = dict(enabled=True, maintenance=False, lan='vtnet0', wan='pppoe0', lan_interface='lan',
            wan_interface='wan', vip='fe80::', vhid=9, normal_skew=100, mtu=1492,
            min_interval=3, max_interval=10, router_lifetime=30,
            preferred_lifetime=60, valid_lifetime=300, source_hash='0' * 64)
OK = type('Result', (), {'returncode': 0, 'stdout': '', 'stderr': ''})()


class SettingsTests(unittest.TestCase):
    def test_cli_rejection_is_structured_and_signals_failure(self):
        result = subprocess.run([sys.executable, str(ROOT / 'control.py'), 'invalid-action'],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'failed')

    def test_command_and_radvd_injection_rejected(self):
        for key, value in [('lan', 'vtnet0;id'), ('vip', 'fe80::; };'),
                           ('wan_interface', '../wan'), ('mtu', '1492'), ('enabled', '1'),
                           ('source_hash', 'not-a-hash'), ('source_hash', 42)]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                validate_config({**BASE, key: value})
        self.assertEqual(validate_config({**BASE, 'source_hash': None})['source_hash'], None)

    def test_cross_field_constraints(self):
        for change in [{'min_interval': 10}, {'router_lifetime': 5},
                       {'valid_lifetime': 30}, {'preferred_lifetime': 5}, {'lan': 'pppoe0'}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_config({**BASE, **change})
        self.assertEqual(validate_config(BASE), BASE)

    def test_custom_ra_values_reach_radvd(self):
        text = render({**BASE, 'preferred_lifetime': 120, 'valid_lifetime': 600},
                      '2001:db8:1::/64', ['2001:db8:2::/64'])
        self.assertIn('AdvPreferredLifetime 120;', text)
        self.assertIn('AdvValidLifetime 600;', text)
        self.assertEqual(text.count('AdvPreferredLifetime 0;'), 1)

    def test_invalid_apply_keeps_running_service(self):
        with patch.object(control, 'exported', side_effect=ValueError('native RA conflict')), patch.object(control, 'run') as run:
            with self.assertRaises(ValueError):
                control.apply()
            run.assert_not_called()

    def test_apply_reloads_a_running_service_in_place(self):
        replies = {'status': {'carp': 'BACKUP'}, 'reload': {'status': 'ok', 'restart': False}}
        with patch.object(control, 'exported', return_value=BASE), patch.object(control, 'validate_ra'), \
             patch.object(control, 'prepare'), patch.object(control, 'query', side_effect=replies.get), \
             patch.object(control, 'run') as run:
            self.assertEqual(control.apply()['message'], 'Configuration applied.')
            run.assert_not_called()

    def test_apply_restarts_when_the_guard_asks_or_is_stopped(self):
        replies = {'status': {'carp': 'BACKUP'}, 'reload': {'status': 'ok', 'restart': True}}
        with patch.object(control, 'exported', return_value=BASE), patch.object(control, 'validate_ra'), \
             patch.object(control, 'prepare'), patch.object(control, 'query', side_effect=replies.get), \
             patch.object(control, 'run', return_value=OK) as run:
            control.apply()
            self.assertEqual([call.args[2] for call in run.call_args_list], ['onestop', 'onestart'])
        with patch.object(control, 'exported', return_value=BASE), patch.object(control, 'validate_ra'), \
             patch.object(control, 'prepare'), patch.object(control, 'query', return_value=None), \
             patch.object(control, 'run', return_value=OK) as run:
            control.apply()
            self.assertEqual([call.args[2] for call in run.call_args_list], ['onestart'])

    def test_disabling_stops_a_running_service_only(self):
        disabled = {'enabled': False, 'maintenance': False}
        with patch.object(control, 'exported', return_value=disabled), patch.object(control, 'prepare'), \
             patch.object(control, 'query', return_value={'carp': 'BACKUP'}), patch.object(control, 'run', return_value=OK) as run:
            self.assertEqual(control.apply()['message'], 'Service disabled.')
            run.assert_called_once_with('/usr/sbin/service', 'ipv6_ha', 'onestop')
        with patch.object(control, 'exported', return_value=disabled), patch.object(control, 'prepare'), \
             patch.object(control, 'query', return_value=None), patch.object(control, 'run') as run:
            control.apply()
            run.assert_not_called()

    def test_service_controls_only_operate_the_plugin_service(self):
        with patch.object(control, 'exported', return_value=BASE), \
             patch.object(control, 'validate_ra'), patch.object(control, 'prepare'), \
             patch.object(control, 'run', return_value=OK) as run:
            self.assertEqual(control.start()['status'], 'ok')
            run.assert_called_once_with('/usr/sbin/service', 'ipv6_ha', 'onestart')
        with patch.object(control, 'run', return_value=OK) as run:
            self.assertEqual(control.stop()['status'], 'ok')
            run.assert_called_once_with('/usr/sbin/service', 'ipv6_ha', 'onestop')

    def test_status_without_a_socket_reports_a_stopped_service(self):
        with patch.object(control, 'query', return_value=None), patch.object(control, 'applied_config', return_value=BASE):
            result = control.status()
        self.assertFalse(result['service_running'])
        self.assertFalse(result['runtime']['ready'])
        self.assertEqual(result['runtime']['reason'], 'Service stopped')
        self.assertTrue(result['enabled'])
        self.assertEqual(result['inherited']['vhid'], 9)
        self.assertNotIn('source_hash', result['inherited'])
        with patch.object(control, 'query', return_value={'carp': 'MASTER', 'source_hash': '0' * 64}), \
             patch.object(control, 'applied_config', return_value=None):
            result = control.status()
        self.assertTrue(result['service_running'])
        self.assertEqual(result['runtime']['carp'], 'MASTER')
        self.assertNotIn('enabled', result)

    def test_concurrent_operations_get_a_readable_message(self):
        import fcntl
        with patch.object(control, 'LOCK', '/dev/null'), \
             patch.object(control.fcntl, 'flock', side_effect=BlockingIOError()), \
             self.assertRaisesRegex(ValueError, 'Another operation is in progress'):
            control.locked(lambda: None)

    def test_disabled_ha_does_not_require_a_working_ra_profile(self):
        self.assertFalse(validate_config({'enabled': False, 'maintenance': False})['enabled'])

    def test_native_dns_routes_and_modes_are_rendered(self):
        ra = dict(mode='stateless', hop_limit=63, preference='high', routes=['2001:db8:2::/64'],
                  route_lifetime=30, remove_route=False, nat64prefix='64:ff9b::/96',
                  rdnss=['fe80::'], dnssl=['home.arpa'], rdnss_lifetime=30, dnssl_lifetime=30)
        c = validate_config({**BASE, 'ra': ra})
        text = render(c, '2001:db8:1::/64', [])
        for expected in ['AdvCurHopLimit 63;', 'AdvDefaultPreference high;', 'AdvOtherConfigFlag on;',
                         'RDNSS fe80:: {', 'DNSSL home.arpa {', 'route 2001:db8:2::/64 {', 'nat64prefix 64:ff9b::/96']:
            self.assertIn(expected, text)
        for field, bad in [('dnssl', ['home.arpa; };']), ('rdnss', ['fe80::%bad']),
                           ('routes', ['::/0;']), ('preference', 'high;'), ('nat64prefix', '64:ff9b::/97')]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                validate_config({**c, 'ra': {**ra, field: bad}})


if __name__ == '__main__':
    unittest.main()
