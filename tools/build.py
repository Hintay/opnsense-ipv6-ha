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

# Auto-generated snippets, verbatim from OPNsense's Mk/plugins.mk `scripts-auto`
# target (see scratchpad/tpl/{actions.d,configure,models,templates}).
_ACTIONS_D_SNIPPET = 'if [ -f /usr/local/etc/rc.d/configd ]; then /usr/local/etc/rc.d/configd restart; fi\n'
_CONFIGURE_SNIPPET = ('if [ -f /usr/local/etc/rc.configure_plugins ]; then echo "Reloading plugin configuration"; '
                       '/usr/local/etc/rc.configure_plugins %%ARG%%; fi\n')
_MODELS_SNIPPET = ('if [ -f /usr/local/opnsense/mvc/script/run_migrations.php ]; then '
                    '/usr/local/opnsense/mvc/script/run_migrations.php %%ARG%%; fi\n')
_TEMPLATES_SNIPPET = ('if [ -f /usr/local/sbin/configctl ]; then echo -n "Reloading template %%ARG%%: "; '
                       '/usr/local/sbin/configctl template reload %%ARG%%; fi\n')

# pkg script stem (repo-root file prefix) -> manifest "scripts" key.
_SCRIPT_NAMES = {
    '+PRE_INSTALL': 'pre-install',
    '+POST_INSTALL': 'post-install',
    '+PRE_DEINSTALL': 'pre-deinstall',
    '+POST_DEINSTALL': 'post-deinstall',
}


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


def _depth_two_dirs(base):
    """Reproduce `find -s . -depth 2 -type d`: sorted grandchild dirs as 'parent/child'."""
    if not base.is_dir():
        return []
    pairs = []
    for parent in sorted(p for p in base.iterdir() if p.is_dir()):
        for child in sorted(c for c in parent.iterdir() if c.is_dir()):
            pairs.append(f'{parent.name}/{child.name}')
    return pairs


def compose_scripts(root):
    """Compose the four pkg lifecycle scripts exactly like Mk/plugins.mk's `scripts`
    target does: `.pre` content, then the scripts-auto generated snippets, then
    `.post` content. Pure function of the source tree; no pkg binary required, so it
    can run (and be tested) on any OS.
    """
    auto = {name: '' for name in _SCRIPT_NAMES}

    # rc.syshook.d/*.early and *.start files get registered for reload on install.
    # This plugin's src/etc/rc.syshook.d/carp/95-ipv6-ha has neither suffix, so it
    # never lands here (it is loaded by the carp syshook framework directly).
    syshook_dir = root / 'src/etc/rc.syshook.d'
    if syshook_dir.is_dir():
        for suffix in ('early', 'start'):
            for hook in sorted(p for p in syshook_dir.rglob(f'*.{suffix}') if p.is_file()):
                rel = hook.relative_to(syshook_dir).as_posix()
                auto['+POST_INSTALL'] += f'/usr/local/etc/rc.syshook.d/{rel}\n'

    # src/opnsense/service/conf/actions.d/* ships configd actions: restart configd.
    if (root / 'src/opnsense/service/conf/actions.d').is_dir():
        auto['+POST_INSTALL'] += _ACTIONS_D_SNIPPET

    # NOTE: src/etc/rc.loader.d and src/opnsense/scripts/firmware/repos are the two
    # remaining scripts-auto sources in plugins.mk; this plugin ships neither
    # directory, so those branches are intentionally not reproduced here.

    # src/opnsense/mvc/app/models/<Vendor>/<Module> -> run model migrations, then
    # reload plugin configuration (both +POST_INSTALL and +POST_DEINSTALL).
    models_dir = root / 'src/opnsense/mvc/app/models'
    if models_dir.is_dir():
        for arg in _depth_two_dirs(models_dir):
            auto['+POST_INSTALL'] += _MODELS_SNIPPET.replace('%%ARG%%', arg)
        for script in ('+POST_INSTALL', '+POST_DEINSTALL'):
            auto[script] += _CONFIGURE_SNIPPET.replace('%%ARG%%', script.lstrip('+'))

    # src/opnsense/service/templates/<Vendor>/<Module> -> reload that configd template.
    templates_dir = root / 'src/opnsense/service/templates'
    if templates_dir.is_dir():
        for arg in _depth_two_dirs(templates_dir):
            auto['+POST_INSTALL'] += _TEMPLATES_SNIPPET.replace('%%ARG%%', arg)

    scripts = {}
    for stem, key in _SCRIPT_NAMES.items():
        content = ''
        pre_file = root / f'{stem}.pre'
        if pre_file.is_file():
            content += pre_file.read_text()
        content += auto[stem]
        post_file = root / f'{stem}.post'
        if post_file.is_file():
            content += post_file.read_text()
        scripts[key] = content
    return scripts


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
        scripts = compose_scripts(ROOT)
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
