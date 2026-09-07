import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('build', ROOT / 'tools/build.py')
build = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(build)


class BuildTests(unittest.TestCase):
    def test_version_comes_from_makefile(self):
        # Compare against a fresh read instead of a hardcoded literal so this test
        # keeps working across PLUGIN_VERSION bumps unrelated to build.py itself.
        self.assertEqual(build.VERSION, build.make_variable('PLUGIN_VERSION'))

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


class ComposeScriptsRealTreeTests(unittest.TestCase):
    """Exercise compose_scripts() against the actual repo tree (pure Python, no pkg)."""

    @classmethod
    def setUpClass(cls):
        cls.scripts = build.compose_scripts(ROOT)

    def test_returns_the_four_pkg_script_names(self):
        self.assertEqual(set(self.scripts), {'pre-install', 'post-install', 'pre-deinstall', 'post-deinstall'})

    def test_pre_install_is_just_the_dot_pre_file(self):
        expected = (ROOT / '+PRE_INSTALL.pre').read_text()
        self.assertEqual(self.scripts['pre-install'], expected)

    def test_pre_deinstall_is_just_the_dot_pre_file(self):
        expected = (ROOT / '+PRE_DEINSTALL.pre').read_text()
        self.assertEqual(self.scripts['pre-deinstall'], expected)

    def test_post_install_runs_auto_snippets_before_the_dot_post_file(self):
        content = self.scripts['post-install']
        actions_d = content.index('if [ -f /usr/local/etc/rc.d/configd ]')
        migrations = content.index('run_migrations.php OPNsense/IPv6HA')
        configure = content.index('rc.configure_plugins POST_INSTALL')
        templates = content.index('configctl template reload OPNsense/Syslog')
        post_file = content.index((ROOT / '+POST_INSTALL.post').read_text())
        self.assertLess(actions_d, migrations)
        self.assertLess(migrations, configure)
        self.assertLess(configure, templates)
        self.assertLess(templates, post_file)
        # No .pre file exists for +POST_INSTALL, so nothing precedes the auto section.
        self.assertEqual(actions_d, 0)

    def test_post_install_does_not_touch_carp_syshook(self):
        # src/etc/rc.syshook.d/carp/95-ipv6-ha has neither an .early nor a .start
        # suffix, so scripts-auto never registers it for reload-on-install.
        self.assertNotIn('rc.syshook.d/carp', self.scripts['post-install'])

    def test_post_deinstall_only_gets_the_configure_snippet(self):
        content = self.scripts['post-deinstall']
        self.assertIn('rc.configure_plugins POST_DEINSTALL', content)
        self.assertNotIn('run_migrations.php', content)
        self.assertNotIn('configctl template reload', content)
        self.assertNotIn('/usr/local/etc/rc.d/configd restart', content)
        post_file = (ROOT / '+POST_DEINSTALL.post').read_text()
        self.assertTrue(content.endswith(post_file))


class ComposeScriptsSyntheticTreeTests(unittest.TestCase):
    """Exercise the generic composition algorithm against a minimal synthetic tree."""

    def test_empty_tree_yields_empty_scripts(self):
        with tempfile.TemporaryDirectory() as scratch:
            scripts = build.compose_scripts(Path(scratch))
        self.assertEqual(scripts, {'pre-install': '', 'post-install': '', 'pre-deinstall': '', 'post-deinstall': ''})

    def test_models_dir_drives_migrations_and_configure_snippets(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / 'src/opnsense/mvc/app/models/Vendor/Module').mkdir(parents=True)
            scripts = build.compose_scripts(root)
        self.assertIn('run_migrations.php Vendor/Module', scripts['post-install'])
        self.assertIn('rc.configure_plugins POST_INSTALL', scripts['post-install'])
        self.assertIn('rc.configure_plugins POST_DEINSTALL', scripts['post-deinstall'])
        self.assertNotIn('run_migrations.php', scripts['post-deinstall'])

    def test_templates_dir_only_affects_post_install(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / 'src/opnsense/service/templates/Vendor/Module').mkdir(parents=True)
            scripts = build.compose_scripts(root)
        self.assertIn('configctl template reload Vendor/Module', scripts['post-install'])
        self.assertEqual(scripts['post-deinstall'], '')

    def test_actions_d_dir_only_affects_post_install(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / 'src/opnsense/service/conf/actions.d').mkdir(parents=True)
            scripts = build.compose_scripts(root)
        self.assertIn('/usr/local/etc/rc.d/configd restart', scripts['post-install'])
        self.assertEqual(scripts['post-deinstall'], '')

    def test_early_and_start_syshooks_are_registered_for_post_install(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            syshook = root / 'src/etc/rc.syshook.d/carp'
            syshook.mkdir(parents=True)
            (syshook / '10-example.early').write_text('# early hook\n')
            (syshook / '20-example.start').write_text('# start hook\n')
            (syshook / '30-example').write_text('# not a hook\n')
            scripts = build.compose_scripts(root)
        self.assertIn('rc.syshook.d/carp/10-example.early', scripts['post-install'])
        self.assertIn('rc.syshook.d/carp/20-example.start', scripts['post-install'])
        self.assertNotIn('30-example\n', scripts['post-install'])

    def test_pre_and_post_fragments_are_concatenated_in_order(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            (root / '+PRE_INSTALL.pre').write_text('pre-part\n')
            scripts = build.compose_scripts(root)
        self.assertEqual(scripts['pre-install'], 'pre-part\n')


if __name__ == '__main__':
    unittest.main()
