# Translation catalogs

The plugin ships its own gettext textdomain, `os-ipv6-ha`. Everything in this directory is managed
by `tools/i18n.py` (pure Python 3.11+, no gettext-tools needed):

| File | Role |
| --- | --- |
| `os-ipv6-ha.pot` | Extracted template, regenerated from the sources; never edited by hand |
| `<lang>.po` | One catalog per language, e.g. `zh_CN.po` — this is what translators edit |
| `../src/share/locale/<lang>/LC_MESSAGES/os-ipv6-ha.mo` | Compiled catalog, committed; installs to `/usr/local/share/locale/...` |

## Workflow

```sh
python3 tools/i18n.py extract                 # sources      -> locale/os-ipv6-ha.pot
python3 tools/i18n.py update                  # template     -> locale/*.po
python3 tools/i18n.py update --locale zh_CN   # ... creating locale/zh_CN.po when absent
$EDITOR locale/zh_CN.po                       # translate (fill in the empty msgstr values)
python3 tools/i18n.py compile                 # locale/*.po  -> src/share/locale/*/LC_MESSAGES/*.mo
python3 tools/i18n.py check                   # verify all three stages agree
```

Commit the `.pot`, the `.po` files and the compiled `.mo` files together; `check` runs in CI and from
`tools/check_repository.py`, and fails when they drift apart.

## What is extracted

- PHP: `gettext('...')`, `I18n::gettext('...')`, `dgettext('os-ipv6-ha', '...')`
- Volt: `lang._('...')`
- Form XML: `<label>`, `<help>`, `<hint>` and `description` attributes (tabs and subtabs)
- Model XML: `<ValidationMessage>`, `<BlankDesc>`, the children of `<OptionValues>`
- `Menu.xml`: `VisibleName` attributes (entries with a `visibility` attribute are skipped)
- `ACL.xml`: `<name>` and `<description>`

Only literal strings are extracted; a `gettext($variable)` call cannot be seen by the extractor.
Plural forms and message contexts are not supported and make the tool fail loudly.

## Rules the tool follows

- Output is deterministic: no timestamps, entries sorted by their first `#: path:line` reference, so
  re-running `extract` on an unchanged tree produces a byte-identical template.
- `update` keeps existing `msgstr` values, adds new messages with an empty `msgstr`, and **drops**
  messages that left the template (they are not kept as `#~` obsolete entries).
- `compile` skips fuzzy and untranslated entries and always writes a UTF-8 header.
- `check` passes when this directory holds no catalogs yet (nothing to verify); once
  `os-ipv6-ha.pot` exists it fails if `extract` would change it, if a `.po` lacks a message from the
  template, or if a `.mo` is missing or differs from what `compile` would write.
