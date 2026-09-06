#!/usr/local/bin/python3
"""Build a local FreeBSD pkg from this source tree without changing the firewall."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def make_variable(name):
    for line in (ROOT / 'Makefile').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == name:
            return value.strip()
    raise RuntimeError(f'Missing {name} in Makefile')


VERSION = make_variable('PLUGIN_VERSION')


def output(*args):
    return subprocess.check_output(args, text=True).strip()


def dependency(name, fallback_version=None, fallback_origin=None):
    try:
        row = output('/usr/local/sbin/pkg', 'query', '%n|%v|%o', name)
        package_name, version, origin = row.split('|')
        return package_name, {'version': version, 'origin': origin}
    except (subprocess.CalledProcessError, ValueError):
        if fallback_version and fallback_origin:
            return name, {'version': fallback_version, 'origin': fallback_origin}
        raise RuntimeError(f'Required package is not installed: {name}') from None


def main():
    if os.uname().sysname != 'FreeBSD':
        raise SystemExit('Run this builder on OPNsense/FreeBSD')
    dist = ROOT / 'dist'
    dist.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='ipv6ha-pkg-') as scratch:
        stage = Path(scratch) / 'root'
        prefix = stage / 'usr/local'
        shutil.copytree(ROOT / 'src', prefix)
        files = {}
        for path in sorted(prefix.rglob('*')):
            if not path.is_file():
                continue
            if '__pycache__' in path.parts or path.suffix == '.pyc':
                path.unlink()
                continue
            executable = path.read_bytes().startswith(b'#!')
            path.chmod(0o755 if executable else 0o644)
            files['/' + path.relative_to(stage).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        deps = {}
        opnsense_version = os.environ.get('OPNSENSE_VERSION')
        name, metadata = dependency('opnsense', opnsense_version, 'opnsense/opnsense')
        deps[name] = metadata
        python_package = output('/usr/local/sbin/pkg', 'which', '-q', str(Path(sys.executable).resolve()))
        for package_name in ('radvd', python_package):
            name, metadata = dependency(package_name)
            deps[name] = metadata
        scripts = {name: (ROOT / 'pkg' / name).read_text() for name in ['pre-install', 'post-install', 'pre-deinstall', 'post-deinstall']}
        repository = os.environ.get('GITHUB_REPOSITORY')
        project_url = f'https://github.com/{repository}' if repository else 'https://docs.opnsense.org/development/plugins.html'
        manifest = {'name': 'os-ipv6-ha', 'version': VERSION, 'origin': 'opnsense/ipv6-ha',
                    'comment': 'Event-driven DHCPv6-PD failover for Router Advertisements',
                    'desc': 'IPv6 HA plugin for OPNsense. Router Advertisements follow CARP and dynamic uplink events, with node-local settings and prefix retirement.',
                    'maintainer': make_variable('PLUGIN_MAINTAINER'), 'www': project_url,
                    'prefix': '/usr/local', 'abi': output('/usr/local/sbin/pkg', 'config', 'ABI'),
                    'licenses': ['BSD2CLAUSE'], 'licenselogic': 'single', 'deps': deps,
                    'files': files, 'scripts': scripts}
        metadata = Path(scratch) / 'manifest.json'
        metadata.write_text(json.dumps(manifest))
        subprocess.run(['/usr/local/sbin/pkg', 'create', '-M', str(metadata), '-r', str(stage), '-o', str(dist)], check=True)
    print(dist / ('os-ipv6-ha-' + VERSION + '.pkg'))


if __name__ == '__main__':
    main()
