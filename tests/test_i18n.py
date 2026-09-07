"""Unit tests for tools/i18n.py; everything runs against synthetic trees in a temp dir."""
import contextlib
import gettext
import io
import importlib.util
from pathlib import Path
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('i18n', ROOT / 'tools/i18n.py')
i18n = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(i18n)

PHP_SOURCE = """<?php
namespace OPNsense\\IPv6HA;

use OPNsense\\IPv6HA\\I18n;

class Demo
{
    public function run($state)
    {
        echo gettext('Plain call');
        echo I18n::gettext('Qualified call');
        echo \\OPNsense\\IPv6HA\\I18n::gettext('Fully qualified call');
        echo dgettext('os-ipv6-ha', 'Domain call');
        echo dgettext('OPNsense', 'Foreign domain');
        echo gettext("Double quoted");
        echo gettext('It\\'s escaped');
        echo gettext("Escaped \\"quotes\\" here");
        echo gettext($state);
        echo $this->gettext('Method call');
        echo ngettext('One', 'Many', 2);
        echo gettext("Interpolated $state");
    }
}
"""

VOLT_SOURCE = """<div>
  <p>{{ lang._('Volt string') }}</p>
  <p>{{ lang._('It\\'s escaped too') }}</p>
  <script>
    var tx = { plain: '{{ lang._('Plain call') }}' };
  </script>
</div>
"""

FORM_XML = """<form>
  <field>
    <id>demo.enabled</id>
    <label>Form label</label>
    <help>Form help</help>
    <hint>Form hint</hint>
  </field>
  <tab id="general" description="Tab description"/>
</form>
"""

MODEL_XML = """<model>
  <mount>//OPNsense/Demo</mount>
  <items>
    <mode type="OptionField">
      <BlankDesc>Nothing selected</BlankDesc>
      <ValidationMessage>Pick a mode</ValidationMessage>
      <OptionValues>
        <auto>Automatic</auto>
        <group value="Grouped modes">
          <off>Disabled</off>
        </group>
      </OptionValues>
    </mode>
  </items>
</model>
"""

MENU_XML = """<menu>
  <Services>
    <Demo VisibleName="Menu entry" url="/ui/demo/"/>
    <Hidden VisibleName="Hidden entry" visibility="hidden"/>
  </Services>
</menu>
"""

ACL_XML = """<acl>
  <page-demo>
    <name>Acl name</name>
    <description>Acl description</description>
    <patterns>
      <pattern>ui/demo/*</pattern>
    </patterns>
  </page-demo>
</acl>
"""


def build_tree(root):
    """Write a miniature plugin tree covering every extraction rule."""
    files = {
        'src/opnsense/mvc/app/controllers/OPNsense/Demo/Api/DemoController.php': PHP_SOURCE,
        'src/opnsense/mvc/app/views/OPNsense/Demo/index.volt': VOLT_SOURCE,
        'src/opnsense/mvc/app/controllers/OPNsense/Demo/forms/general.xml': FORM_XML,
        'src/opnsense/mvc/app/models/OPNsense/Demo/Demo.xml': MODEL_XML,
        'src/opnsense/mvc/app/models/OPNsense/Demo/Menu/Menu.xml': MENU_XML,
        'src/opnsense/mvc/app/models/OPNsense/Demo/ACL/ACL.xml': ACL_XML,
    }
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8')
    return root


class TempTreeTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = build_tree(Path(self._temp.name))

    def messages(self):
        return i18n.collect_messages(self.root)


class ExtractTests(TempTreeTests):
    def test_php_call_forms_are_recognised(self):
        found = self.messages()
        for msgid in ('Plain call', 'Qualified call', 'Fully qualified call', 'Domain call',
                      'Double quoted', "It's escaped", 'Escaped "quotes" here'):
            self.assertIn(msgid, found)

    def test_php_non_literals_and_other_domains_are_ignored(self):
        found = self.messages()
        for msgid in ('Foreign domain', 'Method call', 'One', 'Many', 'Interpolated $state'):
            self.assertNotIn(msgid, found)

    def test_volt_strings_are_recognised(self):
        found = self.messages()
        self.assertIn('Volt string', found)
        self.assertIn("It's escaped too", found)

    def test_xml_rules(self):
        found = self.messages()
        for msgid in ('Form label', 'Form help', 'Form hint', 'Tab description', 'Nothing selected',
                      'Pick a mode', 'Automatic', 'Grouped modes', 'Disabled', 'Menu entry',
                      'Acl name', 'Acl description'):
            self.assertIn(msgid, found)
        # Menu entries carrying a visibility attribute and plain ACL patterns stay out.
        self.assertNotIn('Hidden entry', found)
        self.assertNotIn('ui/demo/*', found)

    def test_references_point_at_the_right_lines(self):
        found = self.messages()
        php = 'src/opnsense/mvc/app/controllers/OPNsense/Demo/Api/DemoController.php'
        volt = 'src/opnsense/mvc/app/views/OPNsense/Demo/index.volt'
        self.assertEqual(found['Plain call'], [(php, 10), (volt, 5)])
        self.assertEqual(found['Volt string'], [(volt, 2)])

    def test_template_is_deterministic_and_timestamp_free(self):
        first = i18n.render_template(self.root)
        second = i18n.render_template(self.root)
        self.assertEqual(first, second)
        self.assertNotIn('POT-Creation-Date', first)
        self.assertNotIn('PO-Revision-Date', first)
        self.assertIn('charset=UTF-8', first)

    def test_entries_are_ordered_by_first_reference(self):
        entries = i18n.build_entries(self.messages())
        order = [(entry.refs[0][0], entry.refs[0][1]) for entry in entries]
        self.assertEqual(order, sorted(order))

    def test_extract_writes_only_when_content_changes(self):
        target = self.root / 'locale/demo.pot'
        self.assertTrue(i18n.write_if_changed(target, i18n.render_template(self.root)))
        self.assertFalse(i18n.write_if_changed(target, i18n.render_template(self.root)))


class LiteralTests(unittest.TestCase):
    def test_single_quotes_only_escape_quote_and_backslash(self):
        self.assertEqual(i18n._read_literal(r"'a\'b'", 0)[0], "a'b")
        self.assertEqual(i18n._read_literal(r"'a\nb'", 0)[0], 'a\\nb')
        self.assertEqual(i18n._read_literal(r"'a\\b'", 0)[0], 'a\\b')

    def test_double_quotes_resolve_c_escapes(self):
        self.assertEqual(i18n._read_literal(r'"a\nb"', 0)[0], 'a\nb')
        self.assertEqual(i18n._read_literal(r'"say \"hi\""', 0)[0], 'say "hi"')
        self.assertEqual(i18n._read_literal(r'"\x41"', 0)[0], 'A')

    def test_unterminated_literal_is_rejected(self):
        self.assertEqual(i18n._read_literal("'open", 0), (None, 0))


class CatalogTests(unittest.TestCase):
    SAMPLE = (
        'msgid ""\n'
        'msgstr ""\n'
        '"Project-Id-Version: os-ipv6-ha\\n"\n'
        '"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '"Language: zh_CN\\n"\n'
        '\n'
        '# translator note\n'
        '#: src/a.php:1\n'
        'msgid "Kept"\n'
        'msgstr "\\u4fdd\\u7559"\n'
        '\n'
        '#: src/a.php:2\n'
        '#, fuzzy\n'
        'msgid "Fuzzy"\n'
        'msgstr "Not sure"\n'
        '\n'
        '#: src/a.php:3\n'
        'msgid "Gone"\n'
        'msgstr "Removed later"\n'
        '\n'
        '#~ msgid "Obsolete"\n'
        '#~ msgstr "Old"\n'
    ).replace('\\u4fdd\\u7559', '保留')

    def test_parse_keeps_msgstr_flags_and_comments(self):
        header, entries = i18n.parse_catalog(self.SAMPLE)
        self.assertIn('Language: zh_CN', header)
        self.assertEqual([entry.msgid for entry in entries], ['Kept', 'Fuzzy', 'Gone'])
        self.assertEqual(entries[0].msgstr, '保留')
        self.assertEqual(entries[0].comments, ['translator note'])
        self.assertEqual(entries[0].refs, [('src/a.php', 1)])
        self.assertEqual(entries[1].flags, ['fuzzy'])

    def test_render_parse_round_trip(self):
        entries = [i18n.Entry(msgid='Multi\nline', msgstr='Zeile\n', refs=[('src/a.php', 1)]),
                   i18n.Entry(msgid='Quote " and \\ backslash', msgstr='ok', refs=[('src/b.volt', 9)],
                              flags=['fuzzy'], comments=['note'])]
        text = i18n.render_catalog(entries, i18n.POT_HEADER)
        _, again = i18n.parse_catalog(text)
        self.assertEqual([(e.msgid, e.msgstr, e.refs, e.flags) for e in again],
                         [(e.msgid, e.msgstr, e.refs, e.flags) for e in entries])

    def test_merge_keeps_translations_adds_and_drops(self):
        template = [i18n.Entry(msgid='Kept', refs=[('src/a.php', 1)]),
                    i18n.Entry(msgid='Fresh', refs=[('src/a.php', 7)])]
        header, entries = i18n.parse_catalog(self.SAMPLE)
        merged, added, removed = i18n.merge(template, header, entries, 'zh_CN')
        _, result = i18n.parse_catalog(merged)
        self.assertEqual([entry.msgid for entry in result], ['Kept', 'Fresh'])
        self.assertEqual(result[0].msgstr, '保留')
        self.assertEqual(result[1].msgstr, '')
        self.assertEqual((added, removed), (1, 2))
        self.assertNotIn('Obsolete', merged)

    def test_plurals_and_contexts_fail_loudly(self):
        with self.assertRaises(i18n.CatalogError):
            i18n.parse_catalog('msgid "One"\nmsgid_plural "Many"\nmsgstr[0] "Ein"\n')
        with self.assertRaises(i18n.CatalogError):
            i18n.parse_catalog('msgctxt "menu"\nmsgid "Open"\nmsgstr "Open"\n')

    def test_header_normalisation_fills_in_the_empty_template_language(self):
        header = i18n.normalize_header(i18n.POT_HEADER, 'zh_CN')
        self.assertIn('Language: zh_CN\n', header)
        self.assertNotIn('Language: \n', header)

    def test_header_normalisation_forces_utf8(self):
        header = i18n.normalize_header('Content-Type: text/plain; charset=ISO-8859-1\n', 'zh_CN')
        self.assertIn('Content-Type: text/plain; charset=UTF-8\n', header)
        self.assertNotIn('ISO-8859-1', header)
        self.assertIn('Language: zh_CN\n', header)


class CompileTests(unittest.TestCase):
    def setUp(self):
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.root = Path(self._temp.name)
        (self.root / 'locale').mkdir()
        (self.root / 'locale/zh_CN.po').write_text(
            'msgid ""\n'
            'msgstr ""\n'
            '"Content-Type: text/plain; charset=UTF-8\\n"\n'
            '\n'
            'msgid "Save and apply"\n'
            'msgstr "保存并应用"\n'
            '\n'
            'msgid "Untranslated"\n'
            'msgstr ""\n'
            '\n'
            '#, fuzzy\n'
            'msgid "Unsure"\n'
            'msgstr "不确定"\n', encoding='utf-8')

    def compiled(self):
        path = i18n.mo_path(self.root, 'zh_CN')
        i18n.write_if_changed(path, i18n.mo_bytes(i18n.catalog_for(self.root / 'locale/zh_CN.po')))
        return path

    def test_gnutranslations_loads_the_mo(self):
        with open(self.compiled(), 'rb') as handle:
            catalog = gettext.GNUTranslations(handle)
        self.assertEqual(catalog.gettext('Save and apply'), '保存并应用')

    def test_untranslated_and_fuzzy_entries_are_skipped(self):
        with open(self.compiled(), 'rb') as handle:
            catalog = gettext.GNUTranslations(handle)
        self.assertEqual(catalog.gettext('Untranslated'), 'Untranslated')
        self.assertEqual(catalog.gettext('Unsure'), 'Unsure')

    def test_mo_layout_is_little_endian_and_sorted(self):
        data = self.compiled().read_bytes()
        self.assertEqual(data[:4], b'\xde\x12\x04\x95')
        self.assertEqual(int.from_bytes(data[8:12], 'little'), 2)  # header + one translation
        self.assertEqual(int.from_bytes(data[20:24], 'little'), 0)  # no hash table

    def test_compile_is_reproducible(self):
        first = i18n.mo_bytes(i18n.catalog_for(self.root / 'locale/zh_CN.po'))
        second = i18n.mo_bytes(i18n.catalog_for(self.root / 'locale/zh_CN.po'))
        self.assertEqual(first, second)


class CheckTests(TempTreeTests):
    def run_tool(self, *arguments):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = i18n.main(['--root', str(self.root), *arguments])
        self.assertEqual(code, 0, output.getvalue())
        return output.getvalue()

    def write_catalogs(self):
        """Produce a consistent locale/ + .mo pair for the synthetic tree."""
        (self.root / 'locale').mkdir(exist_ok=True)
        i18n.pot_path(self.root).write_text(i18n.render_template(self.root), encoding='utf-8')
        self.run_tool('update', '--locale', 'zh_CN')
        self.run_tool('compile')

    def test_missing_locale_directory_passes(self):
        self.assertEqual(i18n.check(self.root), [])

    def test_empty_locale_directory_passes(self):
        (self.root / 'locale').mkdir()
        self.assertEqual(i18n.check(self.root), [])

    def test_catalog_without_template_is_reported(self):
        (self.root / 'locale').mkdir()
        (self.root / 'locale/zh_CN.po').write_text('msgid ""\nmsgstr ""\n', encoding='utf-8')
        self.assertTrue(any('is missing' in problem for problem in i18n.check(self.root)))

    def test_consistent_tree_passes(self):
        self.write_catalogs()
        self.assertEqual(i18n.check(self.root), [])

    def test_stale_template_is_reported(self):
        self.write_catalogs()
        volt = self.root / 'src/opnsense/mvc/app/views/OPNsense/Demo/index.volt'
        volt.write_text(volt.read_text() + "<p>{{ lang._('Brand new') }}</p>\n", encoding='utf-8')
        self.assertTrue(any('out of date' in problem for problem in i18n.check(self.root)))

    def test_catalog_missing_a_message_is_reported(self):
        self.write_catalogs()
        po = self.root / 'locale/zh_CN.po'
        po.write_text(po.read_text().replace('msgid "Form label"\nmsgstr ""\n', ''), encoding='utf-8')
        self.assertTrue(any('missing 1 message' in problem for problem in i18n.check(self.root)))

    def test_stale_mo_is_reported(self):
        self.write_catalogs()
        i18n.mo_path(self.root, 'zh_CN').write_bytes(b'\xde\x12\x04\x95stale')
        problems = i18n.check(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn('os-ipv6-ha.mo is out of date', problems[0])

    def test_missing_mo_is_reported(self):
        self.write_catalogs()
        i18n.mo_path(self.root, 'zh_CN').unlink()
        problems = i18n.check(self.root)
        self.assertEqual(len(problems), 1)
        self.assertIn('os-ipv6-ha.mo is missing', problems[0])

    def test_update_then_compile_round_trip_translates(self):
        self.write_catalogs()
        po = self.root / 'locale/zh_CN.po'
        po.write_text(po.read_text().replace('msgid "Form label"\nmsgstr ""',
                                             'msgid "Form label"\nmsgstr "表单标签"'),
                      encoding='utf-8')
        self.run_tool('compile')
        with open(i18n.mo_path(self.root, 'zh_CN'), 'rb') as handle:
            catalog = gettext.GNUTranslations(handle)
        self.assertEqual(catalog.gettext('Form label'), '表单标签')
        self.assertEqual(i18n.check(self.root), [])


class RealTreeTests(unittest.TestCase):
    """The repository itself must stay extractable and consistent."""

    def test_extract_runs_against_the_repository(self):
        template = i18n.render_template(ROOT)
        self.assertIn('Content-Type: text/plain; charset=UTF-8', template)

    def test_repository_check_passes(self):
        self.assertEqual(i18n.check(ROOT), [])


if __name__ == '__main__':
    unittest.main()
