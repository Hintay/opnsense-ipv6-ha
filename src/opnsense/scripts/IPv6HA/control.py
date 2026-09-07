#!/usr/local/bin/python3
"""Fixed configd actions; accept no command strings or user-controlled paths.

Thin client of the guard's control socket. Prints one JSON object; exits 1 on failure so
rc.d precmds and hooks can rely on the exit code while configd still gets structured output.
"""
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

from settings import validate_config

ROOT = Path('/usr/local/opnsense/scripts/IPv6HA')
CONFIG = Path('/usr/local/etc/ipv6-ha.json')
RC = Path('/etc/rc.conf.d/ipv6_ha')
SOCKET = '/var/run/ipv6-ha.sock'
LOCK = '/var/run/ipv6-ha-apply.lock'
INHERITED = ('lan_interface', 'wan_interface', 'vip', 'vhid', 'normal_skew', 'mtu', 'min_interval',
             'max_interval', 'router_lifetime', 'preferred_lifetime', 'valid_lifetime')
STOPPED = {'ready': False, 'ra_running': False, 'reason': 'Service stopped'}


def run(*args, timeout=30):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def ask(command, timeout=3):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(SOCKET)
        sock.sendall(json.dumps({'command': command}).encode() + b'\n')
        data = b''
        while not data.endswith(b'\n'):
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
    reply = json.loads(data.decode() or 'null')
    return reply if isinstance(reply, dict) else None


def query(command):
    """Return the guard's reply, or None when the service is not running."""
    try:
        return ask(command)
    except (OSError, ValueError):
        return None


def exported():
    result = run('/usr/local/bin/php', str(ROOT / 'export.php'))
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Configuration export failed')
    return validate_config(json.loads(result.stdout))


def applied_config():
    try:
        return validate_config(json.loads(CONFIG.read_text()))
    except (OSError, ValueError):
        return None


def validate_ra(c):
    # Let the installed radvd validate inherited options before touching the running service.
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


def service(verb, tolerated):
    result = run('/usr/sbin/service', 'ipv6_ha', verb)
    output = result.stdout + result.stderr
    if result.returncode and tolerated not in output:
        raise RuntimeError(verb.capitalize() + ' failed: ' + output)


def status():
    runtime = query('status')
    running = runtime is not None
    result = {'status': 'ok', 'service_running': running, 'node': os.uname().nodename,
              'runtime': runtime if running else dict(STOPPED), 'inherited': {}}
    c = applied_config()
    if c is not None:
        result.update(enabled=c['enabled'], maintenance=c['maintenance'],
                      inherited={k: c[k] for k in INHERITED if k in c})
    return result


def apply(force_restart=False):
    # Validate before touching a healthy running service.
    c = exported()
    if c['enabled']:
        validate_ra(c)
    previous = CONFIG.read_bytes() if CONFIG.exists() else None
    previous_rc = RC.read_bytes() if RC.exists() else None
    prepare(c)
    running = query('status') is not None
    if not c['enabled']:
        if running:
            service('onestop', 'not running')
        return {'status': 'ok', 'message': 'Service disabled.'}
    if running and not force_restart:
        reply = query('reload')
        if reply is not None and reply.get('status') == 'ok' and not reply.get('restart'):
            return {'status': 'ok', 'message': 'Configuration applied.'}
    if running:
        service('onestop', 'not running')
    try:
        service('onestart', 'already running')
    except RuntimeError:
        # Preserve the old runtime configuration for an explicit recovery.
        if previous is not None:
            write(CONFIG, previous.decode())
        if previous_rc is not None:
            write(RC, previous_rc.decode())
        raise
    return {'status': 'ok', 'message': 'Configuration applied; service restarted.'}


def start():
    c = exported()
    if not c['enabled']:
        raise ValueError('IPv6 HA is disabled')
    validate_ra(c)
    prepare(c)
    service('onestart', 'already running')
    return {'status': 'ok', 'message': 'Service started.'}


def stop():
    service('onestop', 'not running')
    return {'status': 'ok', 'message': 'Service stopped.'}


def wake():
    if query('wake') is None:
        raise ValueError('Service is not running.')
    return {'status': 'ok'}


def locked(action):
    with open(LOCK, 'w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError('Another operation is in progress.') from None
        return action()


def main():
    action = sys.argv[1] if len(sys.argv) == 2 else ''
    if action == 'status':
        return status()
    if action == 'wake':
        return wake()
    if action == 'check':
        exported()
        return {'status': 'ok', 'message': 'Configuration check passed.'}
    if action == 'prepare':
        c = prepare()
        if not c['enabled']:
            raise ValueError('IPv6 HA is disabled')
        return {'status': 'ok'}
    if action == 'apply':
        return locked(apply)
    if action == 'restart':
        return locked(lambda: apply(force_restart=True))
    if action == 'start':
        return locked(start)
    if action == 'stop':
        return locked(stop)
    raise ValueError('Unknown action')


if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except Exception as exc:
        # Configd needs structured output even when a requested operation is rejected.
        print(json.dumps({'status': 'failed', 'message': str(exc)}))
        sys.exit(1)
