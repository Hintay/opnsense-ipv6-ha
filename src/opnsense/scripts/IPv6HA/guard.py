#!/usr/local/bin/python3
"""Node-local dynamic-PD failover for OPNsense/FreeBSD; radvd owns the wire format."""

import ctypes
import fcntl
import ipaddress
import json
import os
from pathlib import Path
import re
import select
import signal
import socket
import struct
import subprocess
import sys
import syslog
import time

from settings import validate_config, config_hash

CONFIG = Path('/usr/local/etc/ipv6-ha.json')
STATUS = Path('/var/run/ipv6-ha-status.json')
HISTORY = Path('/conf/ipv6-ha-prefixes.json')
RA_CONFIG = Path('/var/run/ipv6-ha-radvd.conf')
RA_PID = '/var/run/ipv6-ha-radvd.pid'
SCRIPT = '/usr/local/opnsense/scripts/IPv6HA/guard.py'
WATCHDOG_INTERVAL = 30


def run(*args, timeout=4):
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout)


def path_signature(path):
    try:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size
    except OSError:
        return None


def atomic_json(path, value):
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    os.chmod(temp, 0o600)
    temp.replace(path)


def log(message):
    syslog.syslog(syslog.LOG_NOTICE, message)
    print(time.strftime('%Y-%m-%d %H:%M:%S'), message, flush=True)


def carp_state(text, vhid):
    match = re.search(r'(MASTER|BACKUP|INIT) vhid ' + str(vhid)
                      + r' advbase (\d+) advskew (\d+)', text)
    return (match[1], int(match[3])) if match else ('MISSING', None)


def pd_address(text, delegated):
    pd = ipaddress.IPv6Network(delegated.strip())
    if not pd.subnet_of(ipaddress.IPv6Network('2000::/3')):
        raise ValueError('PD is not global unicast')
    found = []
    for line in text.splitlines():
        match = re.search(r'inet6 ([0-9a-f:]+) prefixlen 64(?: |$)', line)
        if match and not any(flag in line for flag in ('tentative', 'duplicated', 'deprecated', 'pltime 0 ')):
            addr = ipaddress.IPv6Address(match[1])
            if addr in pd:
                found.append((str(addr), str(ipaddress.IPv6Network(str(addr) + '/64', strict=False))))
    if len(found) != 1:
        raise ValueError('Expected exactly one live LAN /64 inside current PD')
    return found[0]


def parse_ra(data):
    """Only learn preferred global /64s; never relearn our withdrawals."""
    if len(data) < 16 or data[0:2] != b'\x86\x00':
        return []
    prefixes = []
    offset = 16
    while offset + 2 <= len(data):
        kind, units = data[offset:offset + 2]
        length = units * 8
        if not length or offset + length > len(data):
            return []
        option = data[offset:offset + length]
        if kind == 3 and length == 32 and option[2] == 64 and option[3] & 0x40:
            valid, preferred = struct.unpack('!II', option[4:12])
            net = ipaddress.IPv6Network((ipaddress.IPv6Address(option[16:32]), 64), strict=False)
            if 0 < preferred <= valid and net.subnet_of(ipaddress.IPv6Network('2000::/3')):
                prefixes.append((str(net), min(valid, 7200)))
        offset += length
    return prefixes


def render(c, current, old):
    ra = c.get('ra', {})
    mode = ra.get('mode', 'unmanaged')
    lines = [
        '# Managed by ipv6-ha.py; the system Router Advertisements entry must remain disabled.',
        f'interface {c["lan"]} {{',
        ' AdvSendAdvert on;',
        f' MinRtrAdvInterval {c.get("min_interval", 3)};',
        f' MaxRtrAdvInterval {c.get("max_interval", 10)};',
        f' AdvDefaultLifetime {c.get("router_lifetime", 30)};',
        f' AdvLinkMTU {c["mtu"]};',
        f' AdvCurHopLimit {ra.get("hop_limit", 64)};',
        f' AdvDefaultPreference {ra.get("preference", "medium")};',
        f' AdvRASrcAddress {{ {c["vip"]}; }};',
        ' AdvSourceLLAddress off;',
        ' RemoveAdvOnExit off;',
    ]
    if mode in ('managed', 'assist'):
        lines += [' AdvManagedFlag on;', ' AdvOtherConfigFlag on;']
    elif mode == 'stateless':
        lines += [' AdvManagedFlag off;', ' AdvOtherConfigFlag on;']
    for prefix in [current] + sorted(set(old) - {current}):
        active = prefix == current
        lines += [f' prefix {prefix} {{',
                  f'  AdvOnLink {"off" if mode == "router" else "on"};',
                  f'  AdvAutonomous {"off" if mode in ("router", "managed") else "on"};',
                  '  DeprecatePrefix off;',
                  f'  AdvPreferredLifetime {c.get("preferred_lifetime", 60) if active else 0};',
                  f'  AdvValidLifetime {c.get("valid_lifetime", 300) if active else 0};', ' };']
    for route in ra.get('routes', []):
        lines += [f' route {route} {{', f'  RemoveRoute {"on" if ra.get("remove_route") else "off"};',
                  f'  AdvRouteLifetime {ra["route_lifetime"]};', ' };']
    if ra.get('nat64prefix'):
        lines += [f' nat64prefix {ra["nat64prefix"]} {{ }};']
    for field, directive, lifetime in [('rdnss', 'RDNSS', 'AdvRDNSSLifetime'), ('dnssl', 'DNSSL', 'AdvDNSSLLifetime')]:
        if ra.get(field):
            lines += [f' {directive} {" ".join(ra[field])} {{', f'  {lifetime} {ra[field + "_lifetime"]};', ' };']
    return '\n'.join(lines + ['};', ''])


class Guard:
    def __init__(self, c):
        self.c = c
        self.identity = None
        self.ra = None
        self.rendered = None
        self.running = True
        self.last_status = None
        self.last_history_save = 0
        self.last_ra_seen = None
        self.last_solicit = 0
        self.started = time.monotonic()
        try:
            self.history = json.loads(HISTORY.read_text())
        except FileNotFoundError:
            self.history = {}
        self.sock = socket.socket(socket.AF_INET6, socket.SOCK_RAW, socket.IPPROTO_ICMPV6)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVPKTINFO, 1)
        self.sock.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_RECVHOPLIMIT, 1)
        self.sock.setblocking(False)
        self.index = socket.if_nametoindex(c['lan'])
        # These files provide fast wakeups when OPNsense updates a dynamic uplink.
        # Readiness is determined from the interface, delegated prefix and route.
        self.uplink_marker = Path('/tmp/' + c['wan'] + '_uptime')
        self.prefix_file = Path('/tmp/' + c['wan'] + '_prefixv6')

    def receive(self):
        for _ in range(128):
            try:
                data, ancillary, flags, src = self.sock.recvmsg(4096, 256)
            except BlockingIOError:
                break
            meta = {kind: value for level, kind, value in ancillary if level == socket.IPPROTO_IPV6}
            idx = meta.get(socket.IPV6_PKTINFO, b'')
            hop = meta.get(socket.IPV6_HOPLIMIT, b'')
            if (src[0].split('%')[0] != self.c['vip'] or len(idx) != 20 or len(hop) != 4
                    or struct.unpack('=I', idx[16:20])[0] != self.index
                    or struct.unpack('=i', hop)[0] != 255):
                continue
            for prefix, valid in parse_ra(data):
                self.last_ra_seen = time.monotonic()
                if prefix not in self.history:
                    log('Learned advertised prefix ' + prefix)
                self.history[prefix] = time.time() + valid

    def solicit(self, now):
        # A restarting BACKUP may have missed the peer's initial unsolicited RA.
        if now - self.last_solicit < 3:
            return
        self.last_solicit = now
        lan = run('/sbin/ifconfig', self.c['lan']).stdout
        addresses = re.findall(r'inet6 (fe80:[0-9a-f:]+)(?:%\S+)? ', lan)
        source = next((a for a in addresses if a != self.c['vip']), None)
        if source is None:
            return
        packet_info = ipaddress.IPv6Address(source).packed + struct.pack('=I', self.index)
        self.sock.sendmsg([b'\x85' + b'\x00' * 7], [
            (socket.IPPROTO_IPV6, socket.IPV6_PKTINFO, packet_info),
            (socket.IPPROTO_IPV6, socket.IPV6_HOPLIMIT, struct.pack('=i', 255))],
            0, ('ff02::2', 0, 0, self.index))

    def snapshot(self):
        c = self.c
        lan = run('/sbin/ifconfig', c['lan']).stdout
        state, skew = carp_state(lan, c['vhid'])
        result = {'carp': state, 'skew': skew, 'uplink_up': None, 'ready': False}
        try:
            if 'status: active' not in lan or state == 'MISSING':
                raise ValueError('LAN or CARP unavailable')
            if run('/sbin/sysctl', '-n', 'net.inet.carp.allow').stdout.strip() != '1':
                raise ValueError('CARP administratively disabled')
            if c.get('maintenance', False) or Path('/var/run/ipv6-ha-maintenance').exists():
                raise ValueError('IPv6 HA maintenance enabled')
        except (ValueError, OSError) as exc:
            result['reason'] = str(exc)
            return result
        if state != 'MASTER':
            result['reason'] = ('Standby; waiting for CARP takeover' if state == 'BACKUP'
                                else 'Waiting for a stable CARP role')
            return result
        try:
            wan = run('/sbin/ifconfig', c['wan']).stdout
            result['uplink_up'] = bool(re.search(r'<UP,[^>]*RUNNING', wan))
            if not result['uplink_up']:
                raise ValueError('Uplink is not running')
            addr, prefix = pd_address(lan, self.prefix_file.read_text())
            route = run('/sbin/route', '-n', 'get', '-inet6', 'default').stdout
            if not re.search(r'interface:\s+' + re.escape(c['wan']) + r'\s', route):
                raise ValueError('IPv6 default route is not the tracked uplink')
            result.update(ready=True, address=addr, prefix=prefix, reason='Uplink, PD and route ready')
        except (ValueError, OSError) as exc:
            result['reason'] = str(exc)
        return result

    def stop_ra(self):
        if self.ra is not None:
            if self.ra.poll() is None:
                self.ra.terminate()
                try:
                    self.ra.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.ra.kill()
                    self.ra.wait()
            self.ra = None
            self.rendered = None

    def tick(self):
        self.receive()
        s = self.snapshot()
        identity = (s.get('address'), s.get('prefix')) if s['ready'] else None
        if identity != self.identity:
            self.stop_ra()
            self.identity = identity
        now = time.monotonic()
        learning = (s['carp'] == 'BACKUP' and self.last_ra_seen is None
                    and now - self.started < max(2 * self.c.get('max_interval', 10), 6))
        if learning:
            self.solicit(now)
        if not s['ready']:
            self.stop_ra()
        # Re-read ownership immediately before starting Router Advertisements.
        state, actual = carp_state(run('/sbin/ifconfig', self.c['lan']).stdout, self.c['vhid'])
        if state != s['carp']:
            s['carp'] = state
            if state != 'MASTER':
                s.update(ready=False, reason=('Standby; waiting for CARP takeover' if state == 'BACKUP'
                                               else 'Waiting for a stable CARP role'))
        if s['ready'] and state == 'MASTER':
            self.history[s['prefix']] = time.time() + self.c.get('valid_lifetime', 300)
            old = [p for p, expiry in self.history.items() if expiry > time.time() and p != s['prefix']]
            config = render(self.c, s['prefix'], old)
            if self.ra is not None and self.ra.poll() is not None:
                self.stop_ra()
            if config != self.rendered:
                self.stop_ra()
                RA_CONFIG.write_text(config)
                tested = run('/usr/local/sbin/radvd', '-c', '-C', str(RA_CONFIG))
                if tested.returncode:
                    raise RuntimeError('Invalid radvd configuration: ' + tested.stderr)
                self.ra = subprocess.Popen([sys.executable, SCRIPT, '--radvd'])
                self.rendered = config
        else:
            self.stop_ra()
        self.history = dict(sorted(((p, expiry) for p, expiry in self.history.items() if expiry > time.time()),
                                   key=lambda item: item[1], reverse=True)[:16])
        if now - self.last_history_save >= 60:
            atomic_json(HISTORY, self.history)
            self.last_history_save = now
        status = {**s, 'carp': state, 'skew': actual,
                  'ra_running': self.ra is not None and self.ra.poll() is None}
        key = (state, status['uplink_up'], status['ready'], status['ra_running'], identity, s['reason'])
        if key != self.last_status:
            uplink = 'standby' if status['uplink_up'] is None else ('ready' if status['uplink_up'] else 'down')
            log('State changed: CARP {carp}; uplink {uplink}; Router Advertisements {advertisements}; '
                'prefix {prefix}; advskew {skew}; {reason}'.format(
                    carp=state or 'UNKNOWN', uplink=uplink,
                    advertisements='active' if status['ra_running'] else 'silent',
                    prefix=s.get('prefix') or 'none', skew=actual, reason=s['reason']))
            self.last_status = key
        atomic_json(STATUS, {**status, 'updated': time.time(), 'monotonic_updated': time.monotonic(),
                            'process_pid': os.getpid(), 'config_hash': config_hash(self.c),
                            'maintenance': self.c.get('maintenance', False), 'learned_prefixes': self.history})

    def close(self):
        self.stop_ra()
        self.sock.close()
        atomic_json(HISTORY, self.history)


def exec_radvd():
    # FreeBSD PROC_PDEATHSIG_CTL makes a crashed supervisor fail closed.
    parent = os.getppid()
    libc = ctypes.CDLL('libc.so.7', use_errno=True)
    sig = ctypes.c_int(signal.SIGKILL)
    if libc.procctl(0, 0, 11, ctypes.byref(sig)) != 0:
        raise OSError(ctypes.get_errno(), 'Cannot install parent-death signal')
    if os.getppid() != parent or parent == 1:
        sys.exit(1)
    os.execv('/usr/local/sbin/radvd', ['radvd', '-n', '-d', '1', '-m', 'syslog',
                                    '-p', RA_PID, '-C', str(RA_CONFIG)])


def main():
    if '--radvd' in sys.argv:
        exec_radvd()
        return
    if '--status' in sys.argv:
        print(STATUS.read_text())
        return
    c = validate_config(json.loads(CONFIG.read_text()))
    if not c['enabled']:
        raise SystemExit('IPv6 HA is disabled')
    if '--check' in sys.argv:
        guard = Guard(c)
        print(json.dumps(guard.snapshot(), indent=2))
        guard.sock.close()
        return
    lock = open('/var/run/ipv6-ha.lock', 'w')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    syslog.openlog('ipv6-ha')
    guard = Guard(c)
    wake_read, wake_write = os.pipe2(os.O_NONBLOCK | os.O_CLOEXEC)
    watch_fd = os.open('/tmp', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    event_queue = select.kqueue()
    event_queue.control([
        select.kevent(wake_read, filter=select.KQ_FILTER_READ,
                      flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
        select.kevent(guard.sock.fileno(), filter=select.KQ_FILTER_READ,
                      flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR),
        select.kevent(watch_fd, filter=select.KQ_FILTER_VNODE,
                      flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_CLEAR,
                      fflags=select.KQ_NOTE_WRITE | select.KQ_NOTE_EXTEND | select.KQ_NOTE_RENAME),
    ], 0, 0)
    signal.set_wakeup_fd(wake_write)
    signal.signal(signal.SIGTERM, lambda *_: setattr(guard, 'running', False))
    signal.signal(signal.SIGINT, lambda *_: setattr(guard, 'running', False))
    signal.signal(signal.SIGUSR1, lambda *_: None)
    try:
        needs_tick = True
        watched_uplink = (path_signature(guard.uplink_marker), path_signature(guard.prefix_file))
        watched_radvd = None
        watchdog_due = time.monotonic()
        while guard.running:
            if needs_tick:
                guard.tick()
                watchdog_due = time.monotonic() + WATCHDOG_INTERVAL
            if guard.ra is not None and guard.ra.poll() is None and guard.ra.pid != watched_radvd:
                try:
                    event_queue.control([
                        select.kevent(guard.ra.pid, filter=select.KQ_FILTER_PROC,
                                      flags=select.KQ_EV_ADD | select.KQ_EV_ENABLE | select.KQ_EV_ONESHOT,
                                      fflags=select.KQ_NOTE_EXIT)
                    ], 0, 0)
                    watched_radvd = guard.ra.pid
                except OSError:
                    needs_tick = True
                    continue
            events = event_queue.control(None, 32, max(0, watchdog_due - time.monotonic()))
            needs_tick = time.monotonic() >= watchdog_due
            for event in events:
                if event.ident == wake_read:
                    try:
                        os.read(wake_read, 4096)
                    except BlockingIOError:
                        pass
                    needs_tick = True
                elif event.ident == guard.sock.fileno():
                    guard.receive()
                elif event.ident == watch_fd:
                    current = (path_signature(guard.uplink_marker), path_signature(guard.prefix_file))
                    if current != watched_uplink:
                        watched_uplink = current
                        needs_tick = True
                elif event.filter == select.KQ_FILTER_PROC and event.ident == watched_radvd:
                    watched_radvd = None
                    needs_tick = True
    finally:
        signal.set_wakeup_fd(-1)
        event_queue.close()
        os.close(watch_fd)
        os.close(wake_read)
        os.close(wake_write)
        guard.close()


if __name__ == '__main__':
    main()
