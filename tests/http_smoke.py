#!/usr/local/bin/python3
"""Run locally as root over SSH; use and destroy an isolated local test session."""
import json
from pathlib import Path
import re
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

BOOTSTRAP = r'''<?php
session_id('ipv6hatest' . bin2hex(random_bytes(20)));
session_start();
$_SESSION['Username'] = 'root';
$_SESSION['last_access'] = time();
$_SESSION['$PHALCON/CSRF$'] = bin2hex(random_bytes(32));
$_SESSION['$PHALCON/CSRF/KEY$'] = bin2hex(random_bytes(16));
$result = ['name' => session_name(), 'id' => session_id(),
    'csrf' => $_SESSION['$PHALCON/CSRF$'], 'path' => session_save_path() . '/sess_' . session_id()];
session_write_close();
chown($result['path'], 'www');
chmod($result['path'], 0600);
echo json_encode($result);
'''


def main():
    session = json.loads(subprocess.check_output(['/usr/local/bin/php'], input=BOOTSTRAP, text=True))
    changed = False
    token = session['csrf']
    context = ssl._create_unverified_context()
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None
    opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=context), NoRedirect())

    def request(path, payload=None, authenticated=True, csrf=True):
        headers = {}
        if authenticated:
            headers['Cookie'] = session['name'] + '=' + session['id']
        if csrf:
            headers['X-CSRFToken'] = token
        if payload is not None:
            headers['Content-Type'] = 'application/json'
        req = urllib.request.Request('https://127.0.0.1' + path,
            data=json.dumps(payload).encode() if payload is not None else None, headers=headers)
        try:
            with opener.open(req, timeout=40) as response:
                body = response.read().decode()
                return response.status, json.loads(body) if 'application/json' in response.headers.get('Content-Type', '') else body
        except urllib.error.HTTPError as error:
            return error.code, error.read().decode()

    def selected(value):
        if isinstance(value, dict):
            return next((key for key, item in value.items() if isinstance(item, dict) and item.get('selected')), None)
        return value

    def wait_status(predicate, timeout=15):
        deadline = time.time() + timeout
        latest = None
        while time.time() < deadline:
            code, latest = request('/api/ipv6ha/service/status')
            if code == 200 and predicate(latest):
                return latest
            time.sleep(0.5)
        raise AssertionError(latest)

    try:
        code, page = request('/ui/ipv6ha/')
        assert code == 200 and 'frm_IPv6HA' in page and 'frm_RadvdManaged' in page, (code, str(page)[:300])
        assert ('保存并应用' in page) != ('Save and apply' in page), 'Expected one active UI locale'
        assert 'var tx = {' in page and 'var tx = {&quot;' not in page, 'Translation JSON was HTML-escaped'
        assert 'Fatal error' not in page and 'Traceback' not in page
        assert 'grid-ipv6ha-log' in page and '/api/diagnostics/log/core/ipv6ha' in page
        assert 'function backendMessage(value)' in page and 'xhr.responseJSON || {}' in page
        assert 'function decodeLogEntities(value)' in page and 'value = decodeLogEntities(value);' in page
        assert 'IPv6 高可用服务的系统日志。' not in page and 'System log entries for the IPv6 HA service.' not in page
        assert '当前路由通告参数（只读）' not in page and 'Current Router Advertisement parameters (read-only)' not in page
        assert '动态 PD 故障接管 ·' not in page and "join(' · ')" not in page
        assert 'id="ha-node"' not in page and "data.node || ''" not in page
        assert '<h2 style="margin-top:0">IPv6 HA' not in page
        assert "updateServiceControlUI('ipv6ha')" in page
        assert '<pre id="ha-logs">' not in page and '/api/ipv6ha/service/logs' not in page
        assert '原生模型' not in page and 'native Radvd model' not in page
        assert 'IPv6 探测' not in page and 'probe targets' not in page
        # Save only the plugin section, which contains no authentication tokens.
        start = page.index('<style>\n  .ha-summary')
        end = page.index('</script>', start) + len('</script>')
        Path('/tmp/ipv6ha-rendered-section.html').write_text(page[start:end])
        print('PASS: MVC page renders localized HA, Router Advertisements and native log table')
        if '--page-only' in sys.argv:
            return
        code, settings = request('/api/ipv6ha/settings/get')
        assert code == 200 and 'ipv6ha' in settings, (code, settings)
        original = settings['ipv6ha']['general']
        assert len(original) == 3 and 'mtu' not in original and 'vip' not in original, original
        assert 'id="ipv6ha.general.mtu"' not in page
        print('PASS: HA form has 3 fields and no probe or duplicate Router Advertisement settings')
        help_text = re.search(
            r'data-for="help_for_entries\.MinRtrAdvInterval">\s*<small>(.*?)</small>', page, re.S)
        assert help_text and re.sub(r'<[^>]+>', '', help_text.group(1)).strip(), 'System Router Advertisement help is missing'
        assert 'id="entries.enabled"' not in page and 'id="entries.interface"' not in page and 'id="entries.Base6Interface"' not in page
        print('PASS: system Router Advertisement form, help and visibility rules are reused')
        assert original['maintenance'] == '0', 'Run this smoke test outside maintenance'
        print('PASS: authenticated settings and status endpoints')
        code, state = request('/api/ipv6ha/service/status')
        assert code == 200 and state['status'] == 'running' and state['fresh'], (code, state)
        if '--service-controls' in sys.argv:
            assert state['runtime']['carp'] == 'BACKUP', 'Service controls must be tested on BACKUP'
            code, result = request('/api/ipv6ha/service/stop', {})
            assert code == 200 and result.get('status') == 'ok', (code, result)
            wait_status(lambda item: item['status'] == 'stopped' and not item['service_running'])
            code, result = request('/api/ipv6ha/service/start', {})
            assert code == 200 and result.get('status') == 'ok', (code, result)
            state = wait_status(lambda item: item['status'] == 'running' and item['fresh'])
            assert state['runtime']['carp'] == 'BACKUP' and not state['runtime']['ra_running'], state
            print('PASS: title bar stop and start controls operate only the standby plugin service')
        code, managed_ra = request('/api/ipv6ha/radvd/get')
        assert code == 200 and managed_ra['status'] == 'ok' and managed_ra['uuid'], (code, managed_ra)
        assert managed_ra['managed']['native_enabled'] is False, managed_ra
        assert selected(managed_ra['entries']['interface']) == selected(original['lan_interface'])
        print('PASS: managed Router Advertisements API exposes only the selected disabled system entry')
        original_ra_max = managed_ra['entries']['MaxRtrAdvInterval']
        code, rejected = request('/api/ipv6ha/radvd/set/' + managed_ra['uuid'],
            {'entries': {'MaxRtrAdvInterval': '601'}})
        assert code >= 400 or not isinstance(rejected, dict) or rejected.get('result') != 'saved', (code, rejected)
        code, unchanged_ra = request('/api/ipv6ha/radvd/get')
        assert unchanged_ra['entries']['MaxRtrAdvInterval'] == original_ra_max, unchanged_ra
        print('PASS: HA-specific Router Advertisement limits reject invalid settings without saving')
        code, result = request('/api/ipv6ha/service/status', authenticated=False, csrf=False)
        assert code in (302, 401, 403), (code, str(result)[:100])
        code, result = request('/api/ipv6ha/settings/set', {'ipv6ha': {'general': {'lan_interface': '../wan'}}}, csrf=False)
        assert code in (400, 401, 403), (code, result)
        print('PASS: unauthenticated access and missing CSRF rejected')
        code, result = request('/api/ipv6ha/settings/set', {'ipv6ha': {'general': {'lan_interface': '../wan'}}})
        assert result.get('result') != 'saved' and result.get('validations'), (code, result)
        code, unchanged = request('/api/ipv6ha/settings/get')
        assert selected(unchanged['ipv6ha']['general']['lan_interface']) == selected(original['lan_interface'])
        print('PASS: invalid settings rejected without altering saved configuration')
        code, result = request('/api/ipv6ha/service/check', {})
        assert result['status'] == 'ok', (code, result)
        if '--native-roundtrip' in sys.argv:
            assert state['runtime']['carp'] == 'BACKUP'
            uid = managed_ra['uuid']
            entry = managed_ra['entries']
            previous = entry['AdvPreferredLifetime']
            try:
                code, result = request('/api/ipv6ha/radvd/set/' + uid,
                    {'entries': {'AdvPreferredLifetime': '75', 'enabled': '1',
                                 'interface': 'wan', 'Base6Interface': 'wan'}})
                assert result.get('result') == 'saved', result
                code, protected = request('/api/ipv6ha/radvd/get')
                assert protected['managed']['native_enabled'] is False, protected
                assert selected(protected['entries']['interface']) == selected(original['lan_interface']), protected
                assert selected(protected['entries']['Base6Interface']) in (None, ''), protected
                code, result = request('/api/ipv6ha/service/reconfigure', {})
                assert result.get('status') == 'ok', result
                result = wait_status(lambda item: item['inherited']['preferred_lifetime'] == 75 and item['applied'])
                print('PASS: managed Router Advertisements Save/Apply changes system data while protected fields stay locked')
            finally:
                code, result = request('/api/ipv6ha/radvd/set/' + uid, {'entries': {'AdvPreferredLifetime': previous}})
                assert result.get('result') == 'saved', result
                code, result = request('/api/ipv6ha/service/reconfigure', {})
                assert result.get('status') == 'ok', result
                wait_status(lambda item: item['inherited']['preferred_lifetime'] == int(previous) and item['applied'])
        # A BACKUP-only maintenance round trip exercises the same save/apply actions as the UI.
        if '--no-maintenance' in sys.argv:
            code, result = request('/api/diagnostics/log/core/ipv6ha', {'current': 1, 'rowCount': 50})
            assert code == 200 and isinstance(result.get('rows'), list) and result['rows'], (code, result)
            assert all(row.get('process_name') == 'ipv6-ha' for row in result['rows']), result['rows'][:3]
            print('PASS: OPNsense diagnostics log endpoint; maintenance round trip skipped')
            return
        assert state['runtime']['carp'] == 'BACKUP', 'Maintenance smoke test must run on BACKUP'
        changed = True
        code, result = request('/api/ipv6ha/settings/set', {'ipv6ha': {'general': {'maintenance': '1'}}})
        assert result['result'] == 'saved', (code, result)
        code, result = request('/api/ipv6ha/service/reconfigure', {})
        assert result['status'] == 'ok', (code, result)
        time.sleep(2)
        code, result = request('/api/ipv6ha/service/status')
        assert result['maintenance'] and result['applied'] and not result['runtime']['ra_running'], result
        print('PASS: UI save/apply enables persistent node maintenance and silences Router Advertisements')
        code, result = request('/api/diagnostics/log/core/ipv6ha', {'current': 1, 'rowCount': 50})
        assert code == 200 and isinstance(result.get('rows'), list) and result['rows'], (code, result)
        assert all(row.get('process_name') == 'ipv6-ha' for row in result['rows']), result['rows'][:3]
        print('PASS: OPNsense diagnostics log endpoint')
    finally:
        try:
            if changed:
                code, result = request('/api/ipv6ha/settings/set', {'ipv6ha': {'general': {'maintenance': '0'}}})
                assert code == 200 and result.get('result') == 'saved', 'Failed to restore maintenance setting'
                code, result = request('/api/ipv6ha/service/reconfigure', {})
                assert code == 200 and result.get('status') == 'ok', 'Failed to reapply normal configuration'
        finally:
            Path(session['path']).unlink(missing_ok=True)
            print('Temporary test session destroyed')


if __name__ == '__main__':
    main()
