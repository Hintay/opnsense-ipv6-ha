#!/usr/local/bin/python3
"""Fixed configd actions; accept no command strings or user-controlled paths."""
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from settings import validate_config, config_hash

ROOT = Path('/usr/local/opnsense/scripts/IPv6HA')
CONFIG = Path('/usr/local/etc/ipv6-ha.json')
STATUS = Path('/var/run/ipv6-ha-status.json')
RC = Path('/etc/rc.conf.d/ipv6_ha')


def run(*args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def exported():
    result = run('/usr/local/bin/php', str(ROOT / 'export.php'))
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Configuration export failed')
    return validate_config(json.loads(result.stdout))


def validate_ra(c):
    # Let the installed radvd validate inherited options before stopping the old service.
    import tempfile
    from guard import render
    with tempfile.NamedTemporaryFile(mode='w', suffix='.conf') as handle:
        handle.write(render(c, '2001:db8:ffff::/64', []))
        handle.flush()
        checked = run('/usr/local/sbin/radvd', '-c', '-C', handle.name)
        if checked.returncode:
            raise ValueError('Router Advertisement settings were rejected: ' + checked.stderr)


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.new')
    with open(temp, 'w', encoding='utf-8') as handle:
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
    temp.replace(path)


def prepare(c=None):
    c = exported() if c is None else c
    write(CONFIG, json.dumps(c, indent=2) + '\n')
    write(RC, 'ipv6_ha_enable="' + ('YES' if c['enabled'] else 'NO') + '"\n')
    return c


def process_alive(pid, needle):
    try:
        result = run('/bin/ps', '-p', str(int(pid)), '-o', 'command=', timeout=5)
        return result.returncode == 0 and needle in result.stdout
    except (ValueError, TypeError):
        return False


def status():
    try:
        data = json.loads(STATUS.read_text())
    except (OSError, ValueError):
        data = {}
    try:
        pid = int(Path('/var/run/ipv6_ha.child.pid').read_text())
    except (OSError, ValueError):
        pid = 0
    running = pid > 1 and process_alive(pid, str(ROOT / 'guard.py'))
    elapsed = time.monotonic() - data.get('monotonic_updated', -1e12)
    fresh = running and data.get('process_pid') == pid and 0 <= elapsed < 65
    result = {'status': 'ok', 'service_running': running, 'fresh': fresh,
              'age_seconds': round(elapsed, 1) if 0 <= elapsed < 1e9 else None, 'node': os.uname().nodename,
              'runtime': data, 'applied': False}
    try:
        c = exported()
        result.update(enabled=c['enabled'], maintenance=c['maintenance'],
                      applied=(data.get('config_hash') == config_hash(c)) if running else not c['enabled'],
                      configuration_valid=True)
        result['inherited'] = {k: c[k] for k in ('lan_interface', 'wan_interface', 'vip', 'vhid',
            'normal_skew', 'mtu', 'min_interval', 'max_interval', 'router_lifetime', 'preferred_lifetime', 'valid_lifetime') if k in c}
    except Exception as error:
        result.update(configuration_valid=False, configuration_error=str(error))
    if not fresh:
        result['runtime'] = {**data, 'ready': False, 'ra_running': False,
                             'reason': 'Service stopped or runtime status is stale'}
    return result


def apply():
    # Validate before stopping a healthy running service.
    c = exported()
    if c['enabled']:
        validate_ra(c)
    previous = CONFIG.read_bytes() if CONFIG.exists() else None
    previous_rc = RC.read_bytes() if RC.exists() else None
    stopped = run('/usr/sbin/service', 'ipv6_ha', 'onestop')
    if stopped.returncode and 'not running' not in stopped.stdout + stopped.stderr:
        raise RuntimeError(stopped.stdout + stopped.stderr)
    prepare(c)
    if c['enabled']:
        started = run('/usr/sbin/service', 'ipv6_ha', 'onestart')
        if started.returncode:
            # Preserve the old runtime configuration for an explicit recovery.
            if previous is not None:
                write(CONFIG, previous.decode())
            if previous_rc is not None:
                write(RC, previous_rc.decode())
            raise RuntimeError('Start failed: ' + started.stdout + started.stderr)
    return {'status': 'ok', 'message': 'Configuration applied; waiting for local events.' if c['enabled'] else 'Service disabled.'}


def start():
    c = exported()
    if not c['enabled']:
        raise ValueError('IPv6 HA is disabled')
    validate_ra(c)
    prepare(c)
    result = run('/usr/sbin/service', 'ipv6_ha', 'onestart')
    if result.returncode and 'already running' not in result.stdout + result.stderr:
        raise RuntimeError('Start failed: ' + result.stdout + result.stderr)
    return {'status': 'ok', 'message': 'Service started.'}


def stop():
    result = run('/usr/sbin/service', 'ipv6_ha', 'onestop')
    if result.returncode and 'not running' not in result.stdout + result.stderr:
        raise RuntimeError('Stop failed: ' + result.stdout + result.stderr)
    return {'status': 'ok', 'message': 'Service stopped.'}


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'status':
        return status()
    if action == 'check':
        exported()
        return {'status': 'ok', 'message': 'Configuration check passed.'}
    if action == 'prepare':
        c = prepare()
        if not c['enabled']:
            raise ValueError('IPv6 HA is disabled')
        return {'status': 'ok'}
    if action == 'apply':
        with open('/var/run/ipv6-ha-apply.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return apply()
    if action in ('start', 'restart', 'stop'):
        with open('/var/run/ipv6-ha-apply.lock', 'w') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            if action == 'start':
                return start()
            if action == 'restart':
                return apply()
            return stop()
    raise ValueError('Unknown action')


if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except Exception as exc:
        # Configd needs structured output even when a requested operation is rejected.
        print(json.dumps({'status': 'failed', 'message': str(exc)}))
