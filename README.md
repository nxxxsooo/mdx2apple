# mdx2apple

[English](README.md) · [简体中文](README_CN.md) · [Website](https://mjshao.fun/mdx2apple/)

Convert MDict (`.mdx` / `.mdd`) dictionaries into native macOS Dictionary.app
bundles, preserving complete entries.

## What it preserves

- All definitions, examples, translations, parts of speech, idioms and usage notes.
- Original headwords and aliases, including redirect chains and homographs.
- Source CSS, fonts, illustrations and pronunciation files.
- Internal links adapted to native dictionary references.

The converter uses PyGlossary's MDX/MDD reader and writes Apple Dictionary XML
directly. It removes source scripts and event handlers, replaces sound links
with standard audio controls, exposes Oxford's collapsed reference sections,
and uses native HTML disclosure for Oxford illustration enlargement.

**Verified with OALD 10:** all 62,137 complete entry texts and 279,100 original
lookup keys passed native-engine checks. The old ten-sense, two-example and
500-character limits have been removed. [Validation details](docs/oald-native-audit.md).

## Install

Requirements: macOS, Python 3.12+, and Apple's Dictionary Development Kit.

```bash
git clone https://github.com/nxxxsooo/mdx2apple.git
cd mdx2apple
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt

# Install DDK separately if it is not already present:
git clone https://github.com/ikey4u/macddk.git \
  "$HOME/Library/Developer/Dictionary-Development-Kit"
```

Some older MDX dictionaries use LZO compression and require the optional
`python-lzo` dependency. OALD 10 uses zlib and does not require it.

## Convert and install

Use a fresh output directory. Matching `.mdd`, `.1.mdd`, `.2.mdd`, etc. archives
are discovered beside the MDX. Referenced sidecar styles and assets take
precedence over the archive copies.

```bash
python mdx2apple.py /path/to/dictionary.mdx \
  --name "My Dictionary" \
  --output ./output/my-dictionary \
  --keep-resources \
  --install
```

Open Dictionary.app → Settings and enable the new dictionary. A successful
installation does not automatically change your selected dictionaries.

| Option | Meaning |
|---|---|
| `--name` | Full dictionary name in Settings |
| `--short-name` | Compact toolbar/tab name; defaults to the full name |
| `--copyright` | Original dictionary copyright notice |
| `--publisher` | Original dictionary publisher |
| `--credits` | Conversion attribution shown below the copyright |
| `--output`, `-o` | Fresh output directory; defaults to `./output` |
| `--identifier` | Unique bundle ID, such as `com.example.dictionary` |
| `--keep-resources` | Include images, audio and other archive resources |
| `--resource-url` | Base URL for entry media; defaults to the installed bundle's `dict-resource://` URL |
| `--install` | Build and install into `~/Library/Dictionaries/` |

CSS and fonts are kept even without `--keep-resources`; use the flag for a
complete media-enabled dictionary. Conversion itself does not alter the source
MDX, MDD or neighboring files.

Without `--install`, build and install later:

```bash
make -C output/my-dictionary
make -C output/my-dictionary install
```

DDK runs from an isolated build directory, then `ditto` adds `OtherResources`.
This avoids shell argument limits with large resource collections. No manual
resource moves or post-install `rsync` are required.

## Diagnostics and limits

- `conversion-report.json` records entries, text-preservation checks, adapted
  links/media, unresolved source references, redirect cycles and missing files.
- Unsupported or missing dictionary references retain their text but become
  non-clickable. The converter does not invent missing dictionary articles.
- MP3/WAV playback uses native HTML audio controls. Other codecs depend on the
  macOS WebKit version; the converter does not transcode them.
- Dictionary.app's **All** tab resolves relative paths against its own app bundle,
  so audio shows "Error" and images vanish there. Entry media therefore point to
  the absolute `dict-resource://` URL of the installed bundle
  (`~/Library/Containers/com.apple.Dictionary/Data/Library/Dictionaries/<Name>.dictionary`).
  Install the bundle under its generated name; to keep relative paths for a
  bundle installed elsewhere, pass `--resource-url ""`.
- Original dictionary scripts are not executed. Highly interactive dictionaries
  may need additional format-specific adapters.
- Source styling is imported before the converter's compatibility adaptations.
  Dictionary.app and system Look Up may render differently; native interaction
  checks remain important.
- Oxford entries have an explicit dark palette for text, pronunciation,
  examples and reference boxes. Illustrations retain their original colors.

## Per-dictionary typography

Personal font and reading-layout choices belong in a dictionary-specific override.
`assets/dictionary.css` is the shared compatibility layer; a preference from one
dictionary should not become the default for every conversion.

Dictionary.app can skip a user-installed font even when an isolated WebKit preview
uses it. A tested alternative is a local `@font-face` URL pointing to a font inside
that dictionary's `OtherResources`, with its license. Preserve Chinese and IPA
fallbacks and relative font sizes. A computed CSS family name does not prove which
font rendered the glyphs; verify the actual app or its Accessibility font runs.
The [OALD audit](docs/oald-native-audit.md#typography-customization-and-native-verification)
records the native evidence and the current customization split.

## Update an existing installation

This is a source-installed tool. Updates are manual:

```bash
git pull --ff-only
source .venv/bin/activate
python -m pip install -r requirements.txt
python mdx2apple.py /path/to/dictionary.mdx \
  --output ./output/my-dictionary-updated \
  --keep-resources --install
```

Run these commands in your existing `mdx2apple` checkout. Use a fresh output
directory and repeat any custom `--name`, `--short-name`, `--identifier`,
`--copyright`, `--publisher` and `--credits` options. Pulling new code alone
does not update an installed dictionary: it must be converted and installed
again. Quit and reopen Dictionary.app afterwards.

To remove a converted dictionary, quit Dictionary.app and move its generated
`.dictionary` bundle out of `~/Library/Dictionaries/`. Keep a copy of the previous
bundle if you want a local rollback.

See the [OALD audit](docs/oald-native-audit.md) for corpus-level verification and
the distinction between engine, WebKit and Dictionary.app UI checks.

## Verification

```bash
python -m unittest discover -s tests -v

# Read-only check against a locally owned dictionary:
python tests/audit_native_dictionary.py \
  --source /path/to/reference-appledict.xml \
  --converted output/my-dictionary/dictionary.xml \
  --dictionary "$HOME/Library/Dictionaries/dictionary.dictionary" \
  --mdx /path/to/dictionary.mdx \
  --compare-all \
  --output output/native-audit/report.json
```

The native audit uses an undocumented dictionary-selection API and compares
all matching records to account for homographs. Prefer `--mdx` for authoritative
source keys; existing SQLite indexes can contain synthetic aliases. Reports
contain dictionary text and should stay outside published fixtures.

`tests/probe_webkit.swift` renders extracted native HTML and tests media in an
isolated WebKit instance. Its optional `--secondary-display` mode creates a
nonactivating window only when a secondary display exists; audio tests are muted.
Use `--width=480`, `--height=900` and `--font-size=20` to check narrow layouts and
enlarged text. Its JSON reports computed typography and horizontally clipped text.

## Credits and license

- [PyGlossary](https://github.com/ilius/pyglossary): MDX/MDD format reader.
- [macddk](https://github.com/ikey4u/macddk): Dictionary Development Kit mirror.

MIT. Dictionary content remains owned by its respective rights holders.
