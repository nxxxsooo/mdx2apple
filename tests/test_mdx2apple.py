import json
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

import mdx2apple as m


class Mdx2AppleTests(unittest.TestCase):
    def render(self, records):
        catalog = m.Catalog(records)
        adapter = m.EntryAdapter(catalog, "com.example.test")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dictionary.xml"
            m.write_entries(iter(records), catalog, adapter, path)
            data = path.read_bytes()
        return etree.fromstring(data), adapter, data

    def test_complete_long_entry_and_bilingual_examples_survive(self):
        senses = "".join(
            f'<li class="sense"><span class="def">definition {i}</span>'
            '<deft><chn>中文释义</chn></deft>'
            + "".join(f'<span class="x">example {i}/{j}</span><xt><chn>例句 {j}</chn></xt>'
                      for j in range(5)) + '</li>' for i in range(25)
        )
        body = '<h1>sample</h1><span class="pos">noun</span><ol>' + senses + '</ol>'
        body += '<h2>another part of speech</h2><span class="pos">verb</span>'
        body += '<span class="idm">an idiom</span><p>' + "long fallback text " * 200 + '</p>'
        root, _, data = self.render([("sample", body)])
        ns = {"h": m.XHTML}
        self.assertEqual(len(root.xpath('.//h:li[@class="sense"]', namespaces=ns)), 25)
        self.assertEqual(len(root.xpath('.//h:span[@class="x"]', namespaces=ns)), 125)
        text = ''.join(root.itertext())
        self.assertIn('definition 24', text)
        self.assertIn('example 24/4', text)
        self.assertIn('another part of speech', text)
        self.assertIn('an idiom', text)
        self.assertEqual(text.count('long fallback text'), 200)
        self.assertEqual(data.count(b'xmlns:d='), 1)

    def test_plain_redirect_definition_and_tail_are_not_discarded(self):
        root, _, _ = self.render([('went', '<h1>went</h1><script>discard()</script>past tense of <a href="entry://go">go</a>'), ('go', '<h1>go</h1><p>move</p>')])
        self.assertIn('past tense of go', ''.join(root.itertext()))
        self.assertNotIn('discard', ''.join(root.itertext()))
        self.assertIn('x-dictionary:r:entry000002:com.example.test', etree.tostring(root).decode())

    def test_chained_aliases_and_homographs_preserve_all_records(self):
        records = [('verb', '<p>first</p>'), ('verb', '<p>second</p>'),
                   ('inflected', '@@@LINK=verb'), ('alias', '@@@LINK=inflected')]
        root, _, _ = self.render(records)
        entries = root.findall(f'{{{m.DCS}}}entry')
        self.assertEqual(len(entries), 2)
        for entry in entries:
            keys = [n.get(f'{{{m.DCS}}}value') for n in entry.findall(f'{{{m.DCS}}}index')]
            self.assertEqual(set(keys), {'verb', 'inflected', 'alias'})

    def test_broken_aliases_are_reported_without_recursion(self):
        c = m.Catalog([('a', '@@@LINK=b'), ('b', '@@@LINK=a'), ('c', '@@@LINK=missing')])
        self.assertTrue(c.diagnostics['redirect_cycles'])
        self.assertEqual(c.diagnostics['missing_redirect_targets'], {'missing'})

    def test_key_can_be_both_an_entry_and_a_redirect(self):
        c = m.Catalog([('resume', '<p>verb</p>'), ('résumé', '<p>noun</p>'),
                       ('resume', '@@@LINK=résumé')])
        self.assertEqual(c.find('resume'), ['entry000001', 'entry000002'])

    def test_literal_keys_and_readable_html_headwords_are_both_indexed(self):
        root, _, _ = self.render([('dip<sup>&#x00B3;</sup>', '<h1>dip³</h1>'),
                                  ('&amp;c.', '<p>etcetera</p>')])
        entries = root.findall(f'{{{m.DCS}}}entry')
        self.assertEqual(entries[0].get(f'{{{m.DCS}}}title'), 'dip³')
        keys = {n.get(f'{{{m.DCS}}}value') for n in root.iter(f'{{{m.DCS}}}index')}
        self.assertTrue({'dip<sup>&#x00B3;</sup>', 'dip³', '&amp;c.', '&c.'} <= keys)

    def test_picture_expansion_uses_native_disclosure(self):
        root, _, _ = self.render([('image', '<div class="pic"><div class="pic_thumb" onclick="original()"><img src="thumb.png"></div><div class="big_pic"><img src="large.png"></div></div>')])
        details = root.find('.//{'+m.XHTML+'}details')
        self.assertIsNotNone(details.find('{'+m.XHTML+'}summary'))
        self.assertEqual(details.find('{'+m.XHTML+'}div').get('class'), 'mdx-picture-full')
        self.assertNotIn('onclick', etree.tostring(root).decode())

    def test_native_media_paths_and_missing_reference_labels(self):
        root, adapter, _ = self.render([('word', '<link rel="stylesheet" href="style.css"><h1>word</h1>'
            '<a href="sound://audio/test &amp; one.mp3"> </a><img src="/images/picture.png">'
            '<a href="entry://absent">keep this label</a>')])
        ns = {'h': m.XHTML}
        audio = root.find('.//h:audio', ns)
        self.assertEqual(audio.get('src'), 'audio/test%20%26%20one.mp3')
        self.assertEqual(audio.get('preload'), 'none')
        self.assertIsNotNone(audio.get('controls'))
        self.assertEqual(root.find('.//h:img', ns).get('src'), 'images/picture.png')
        self.assertIn('keep this label', ''.join(root.itertext()))
        self.assertEqual(adapter.unresolved_links, {'entry://absent'})
        self.assertEqual(adapter.stylesheets, {'style.css'})

    def test_media_use_absolute_resource_url_for_all_results_view(self):
        records = [('word', '<a href="sound://a b.mp3"> </a><img src="pic.png">')]
        catalog = m.Catalog(records)
        base = m.installed_resource_url("My_Dict")
        self.assertTrue(base.startswith("dict-resource:///"))
        self.assertTrue(base.endswith("/Dictionaries/My_Dict.dictionary/Contents/Resources/"))
        adapter = m.EntryAdapter(catalog, "com.example.test", base)
        root = adapter.adapt(records[0][1], "entry000001")
        self.assertEqual(root.find('.//audio').get('src'), base + 'a%20b.mp3')
        self.assertEqual(root.find('.//img').get('src'), base + 'pic.png')
        self.assertEqual(adapter.resources, {'a b.mp3', 'pic.png'})

    def test_website_reference_uses_known_homograph_anchor(self):
        records = [('bank', '<div id="bank_1">noun</div><div id="bank_2">verb</div>'),
                   ('word', '<a href="entry:///definition/english/bank2">bank</a>')]
        root, adapter, _ = self.render(records)
        self.assertFalse(adapter.unresolved_links)
        self.assertEqual(root.find('.//{'+m.XHTML+'}a').get('href'),
                         'x-dictionary:r:entry000001:com.example.test')

    def test_local_anchor_stays_local(self):
        root, _, _ = self.render([('word', '<a href="#idioms">Idioms</a><div id="idioms">all idioms</div>')])
        self.assertEqual(root.find('.//{'+m.XHTML+'}a').get('href'), '#idioms')

    def test_resource_paths_cannot_escape_output(self):
        for path in ['../outside', '%2e%2e/outside', '\\..\\outside']:
            with self.assertRaises(ValueError):
                m.resource_name(path)

    def test_source_assets_cannot_overwrite_native_indexes_or_styles(self):
        for name in ['Body.data', 'KeyText.index', 'DEFAULTSTYLE.CSS']:
            with self.assertRaises(ValueError):
                m.resource_name(name)
        self.assertEqual(m.resource_name('nested/DefaultStyle.css'), 'nested/DefaultStyle.css')

    def test_css_import_order_and_plist_escaping(self):
        with tempfile.TemporaryDirectory() as directory:
            css = Path(directory) / 'test.css'
            m.create_css(css, ['nested/style.css'])
            text = css.read_text()
            self.assertLess(text.index('@import'), text.index('@namespace'))
            self.assertIn('d|entry { display: block; }', text)
            p = Path(directory) / 'test.plist'
            m.create_plist(p, 'English & 中文 <test>', 'com.example.test')
            self.assertEqual(plistlib.loads(p.read_bytes())['CFBundleDisplayName'], 'English & 中文 <test>')

    def test_makefile_builds_outside_resource_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Makefile'
            m.create_makefile(path, '/path with spaces/DDK', 'test')
            text = path.read_text()
            self.assertIn('cd .build && DICT_DEV_KIT_OBJ_DIR=../objects', text)
            self.assertIn('ditto --noextattr --norsrc OtherResources', text)
            self.assertNotIn('OtherResources/*', text)

    @patch('mdx2apple.subprocess.run')
    def test_run_make_keeps_explicit_working_directory(self, run):
        run.return_value = subprocess.CompletedProcess([], 0, '', '')
        m.run_make(Path('/path with spaces/DDK'), 'install', Path('/output path'))
        run.assert_called_once_with(
            ['make', 'DICT_BUILD_TOOL_DIR=/path with spaces/DDK', 'install'],
            cwd=Path('/output path'), capture_output=True, text=True,
        )


class TestdataFixtures(unittest.TestCase):
    """Synthetic regression fixtures for real-dictionary shapes.

    Fixture text is written for the tests; only common headwords and
    structural patterns come from the real corpora in materials/
    (git-ignored, never published). Bodies use the post-repair form:
    literal angle brackets arrive as &lt;, because the LITERAL_ANGLE
    repair lives in per-dictionary local prepare scripts, not in the
    shared converter.
    """
    DATA = Path(__file__).resolve().parent / "testdata"

    def render_file(self, name):
        cases = json.loads((self.DATA / name).read_text(encoding="utf-8"))
        records = [(case["key"], case["body"]) for case in cases]
        catalog = m.Catalog(records)
        adapter = m.EntryAdapter(catalog, "com.example.testdata")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dictionary.xml"
            m.write_entries(iter(records), catalog, adapter, path)
            data = path.read_bytes()
        return cases, etree.fromstring(data), adapter, data.decode("utf-8")

    def check(self, name):
        cases, root, adapter, serial = self.render_file(name)
        searchable = "".join(root.itertext()) + "\n" + serial
        for case in cases:
            for needle in case.get("must_contain", []):
                self.assertIn(needle, searchable, f"{name}:{case['id']}")
            for needle in case.get("must_not_contain", []):
                self.assertNotIn(needle, serial, f"{name}:{case['id']}")
            for link in case.get("expect_unresolved", []):
                self.assertIn(link, adapter.unresolved_links, f"{name}:{case['id']}")

    def test_xindehan_edge_cases(self):
        self.check("xindehan-edge-cases.json")

    def test_bilingual_edge_cases(self):
        self.check("bilingual-edge-cases.json")


if __name__ == '__main__':
    unittest.main()
