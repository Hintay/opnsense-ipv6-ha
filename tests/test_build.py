import importlib.util
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build', ROOT / 'tools/build.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def test_version_comes_from_makefile(self):
        self.assertEqual(build.VERSION, '1.0')

    def test_stock_freebsd_builder_can_record_opnsense_dependency(self):
        missing = subprocess.CalledProcessError(1, ['pkg', 'query'])
        with patch.object(build, 'output', side_effect=missing):
            name, metadata = build.dependency('opnsense', '26.7', 'opnsense/opnsense')
        self.assertEqual(name, 'opnsense')
        self.assertEqual(metadata, {'version': '26.7', 'origin': 'opnsense/opnsense'})

    def test_missing_dependency_without_fallback_is_rejected(self):
        missing = subprocess.CalledProcessError(1, ['pkg', 'query'])
        with patch.object(build, 'output', side_effect=missing), self.assertRaises(RuntimeError):
            build.dependency('radvd')


if __name__ == '__main__':
    unittest.main()
