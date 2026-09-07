#!/usr/bin/env python3
"""Run portable repository checks without requiring an OPNsense installation."""
import ast
import importlib.util
import os
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load_tool(name):
    """Import a sibling tool by path so this script works from any working directory."""
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(f'{name}.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_variable(name):
    for line in (ROOT / 'Makefile').read_text(encoding='utf-8').splitlines():
        key, separator, value = line.partition('=')
        if separator and key.strip() == name:
            return value.strip()
    raise ValueError(f'Missing {name} in Makefile')


def tracked_files():
    ignored = {'.git', 'dist', 'evidence', '__pycache__'}
    return [path for path in ROOT.rglob('*') if path.is_file() and not ignored.intersection(path.parts)]


def main():
    version = make_variable('PLUGIN_VERSION')
    if not re.fullmatch(r'[0-9]+\.[0-9]+(?:\.[0-9]+)?', version):
        raise ValueError(f'Invalid plugin version: {version}')

    tag = os.environ.get('GITHUB_REF_NAME', '')
    if tag and os.environ.get('GITHUB_REF_TYPE') == 'tag' and tag != f'v{version}':
        raise ValueError(f'Tag {tag} does not match plugin version {version}')

    for path in tracked_files():
        if path.suffix == '.py':
            ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
        elif path.suffix == '.xml':
            ET.parse(path)

    # Translation template, catalogs and compiled .mo files must be in sync (a locale/
    # directory without catalogs passes, see tools/i18n.py check).
    problems = load_tool('i18n').check(ROOT)
    if problems:
        raise ValueError('\n'.join(problems))

    model = ET.parse(ROOT / 'src/opnsense/mvc/app/models/OPNsense/IPv6HA/IPv6HA.xml')
    if model.getroot().findtext('version') != '1.0.0':
        raise ValueError('The initial public model version must be 1.0.0')

    public_text = '\n'.join(
        path.read_text(encoding='utf-8', errors='ignore')
        for path in tracked_files()
        if path.suffix.lower() in {'.md', '.py', '.php', '.sh', '.xml', '.volt', '.yml', '.yaml', ''}
    )
    forbidden = ('192' + '.168.', '240' + 'e:')
    for value in forbidden:
        if value in public_text:
            raise ValueError(f'Environment-specific value remains in public files: {value}')

    expected_package = f'os-ipv6-ha-{version}.pkg'
    expected_digest = f'{expected_package}.dgst'
    for readme in ('README.md', 'README.zh-CN.md'):
        readme_text = (ROOT / readme).read_text(encoding='utf-8')
        if expected_package not in readme_text:
            raise ValueError(f'{readme} does not reference {expected_package}')
        if expected_digest not in readme_text:
            raise ValueError(f'{readme} does not reference {expected_digest}')

    print(f'Repository checks passed for version {version}')


if __name__ == '__main__':
    try:
        main()
    except (OSError, SyntaxError, ValueError, ET.ParseError) as error:
        print(error, file=sys.stderr)
        raise SystemExit(1)
