# OALD 10 conversion validation

The full-content conversion was checked on 2026-10-23 with macOS 27.0.1,
Python 3.12.15, PyGlossary 5.4.2 and the locally installed Dictionary Development
Kit. The source was a locally owned OALD 10 MDX/MDD pair. The corpus, extracted
entry text and generated bundles are not distributed with this report.

## Results

| Check | Result |
|---|---:|
| Original MDX records | 283,816 |
| Complete entry bodies | 62,137 |
| Redirect records | 221,679 |
| Original unique lookup keys | 279,100 / 279,100 resolve |
| Generated lookup keys, including readable variants | 279,103 / 279,103 resolve |
| Compiled entry text compared against complete XML | 62,137 / 62,137 match |
| Definition spans retained | 112,043 |
| Main and extra examples retained | 221,227 |
| Idiom headings retained | 11,420 |

Text comparisons ignore whitespace only and inspect every matching native record
so that homographs are not mistaken for missing entries. The adapter separately
checks that each body's text remains unchanged while it adapts links and media,
after removing source scripts and styles. All 15 regression tests passed at the
time; the suite now has 18.

These are corpus-specific results, not a guarantee for every MDX dictionary.

## What changed from the earlier converter

The previous cleaner kept at most ten senses and two examples per sense, with a
500-character fallback for unstructured content. It retained only 93,869 of the
source's 221,227 examples and removed image, link and idiom-heading markup.

For example, `run` had been reduced from 63 definitions and 164 examples to ten
definitions and 18 examples. `went` lost its “past tense of go” relationship.
The full-content pipeline retains those structures and uses direct MDX/MDD
reading instead of selective extraction from an intermediate conversion.

Coverage must be measured against the MDX itself. A pre-existing SQLite index
contained generated spelling variants; its 337,069 keys were not an authoritative
count of original source keys. Direct MDX inspection corrected that earlier
audit assumption.

## Rendering, links and media

- HTML returned by macOS DictionaryServices was rendered in isolated WebKit.
  All six definitions and 12 examples of `apple`, and all 63 definitions and
  164 examples of `run`, remained visible without horizontal overflow.
- British and American pronunciation MP3s for `apple` and `run` decoded and
  played with native audio controls. The verification was muted.
- All four referenced `apple` images decoded. Native HTML disclosure expanded
  the illustration without the original dictionary JavaScript.
- Dark-mode text, IPA, translations, links and reference boxes passed the
  rendered text-contrast checks for `hi`, `apple` and `run`; the lowest measured
  ratio across those dark samples was 7.02:1. Light-mode `hi` also passed.
- Full display name, compact toolbar name, publisher, copyright and conversion
  credits were verified through the installed bundle and DictionaryServices.
- A native Dictionary.app user check confirmed that the full entries displayed.

## Typography customization and native verification

**Scope decision (2026-10-23):** JetBrains Mono Nerd Font and the accompanying
reading-layout choices are a personal OALD customization, not converter-wide
defaults. The user confirmed the native result, then explicitly corrected the
scope. Shared compatibility fixes and per-dictionary preferences have different
owners; the local split was still unfinished when Save was requested.

The tested preset uses 1.65 line height, a bounded reading width, translations
below their examples, aligned pronunciation groups and padded reference sections.
IPA keeps a separate system font, and text size remains relative to the host.

Six isolated WebKit checks covered `colleague` in light/dark themes and a narrow
enlarged-text view, `apple` in dark mode, `run` at 480 px with 20 px body text,
and `hi` at 320 px in light mode. All sampled definitions and examples remained
visible, with no horizontal overflow or clipped text. The lowest measured text
contrast was 4.77:1 in light mode and 7.02:1 in dark mode. Headwords scaled from
24 px to 30 px when body text increased from 16 px to 20 px.

Headless media playback timed out; the same two `apple` pronunciation files
played muted in an isolated, nonactivating WebKit panel on the secondary display.
Illustration expansion also passed. This is WebKit evidence, not a new automated
Dictionary.app interaction check.

### Native font mismatch and fix

Those WebKit checks did **not** establish the native font. The user's screenshot
showed the spacing changes but a proportional font. Accessibility font runs from
Dictionary.app confirmed that both the headword and English prose used
`PingFangSC-Regular` / `PingFangSC-Semibold`, despite installed JetBrains families
being named in CSS. The app's shipped default stylesheet did not reveal a rule
that forced this fallback; the precise internal font-access policy is unverified.

Copying `JetBrainsMonoNerdFont-Regular.ttf` into this OALD bundle's
`Contents/Resources/mdx-fonts/` and loading it through `@font-face` with the alias
`MDX JetBrains Mono` worked. Native Accessibility then reported
`JetBrainsMonoNF-Regular` for English; IPA still used the system face. The user
confirmed that the change was visible in Dictionary.app. This verifies the
bundled-font workaround in this installation, not a universal font-policy claim.

The read-only diagnostic is `tests/probe_dictionary_fonts.swift`. It uses
`AXTextMarkerRangeForUIElement` and `AXAttributedStringForTextMarkerRange` within
the native `AXWebArea`; sidebar and toolbar fonts are deliberately excluded.
Computed `font-family` alone is insufficient evidence of the actual glyph font.

### Recovery state at Save (2026-10-23)

**Superseded for local font packaging on 2026-10-26:** the personal preset now
embeds the complete WOFF-compressed font in CSS, includes its license, and has
been applied to source/build/installed styles. Native Accessibility confirmed
JetBrainsMonoNF-Regular in both the OALD tab and All Results; the latter fell
back with the earlier external TTF URL. The three local German dictionaries now
use the same font-loading method and 1.65 body line height. All core text/index
files and metadata remain unchanged. Eight light/dark WebKit cases and the 15
converter tests pass. Current local evidence is under
`output/typography-audit/20261026-all-results/`; the operational owner is
`.local/dictionary-typography/README.md`. System Look Up and full All Results
resource/layout parity remain outside this font verification. The shared-style
cleanup described below is still unfinished; this does not make the personal
font a shared default. The following bullets record the historical save state.

- **Working installation:** OALD uses the bundled regular TTF through its installed
  `DefaultStyle.css`. This is the version the user accepted. The initial build
  copy had only the family-name preference; the direct-font fix was applied to
  the installed bundle during diagnosis.
- **Unfinished shared/local split:** `assets/dictionary.css` still contains the
  uncommitted personal font and spacing draft, including a font URL. No font is
  bundled by the converter. This working-tree state must not be presented as a
  finished common default or shipped as-is.
- **Local preset draft:** `.local/oald10-style/` contains `dictionary.css`,
  `apply.py` and its README. Its `mdx-fonts/` directory has not yet been populated,
  and the apply script has not been run or validated. `.local/` is ignored in the
  pending `.gitignore` change. The source TTF remains in the user's installed
  fonts and the accepted OALD bundle; the license is available in the installed
  Homebrew Nerd Fonts 3.5.1 package.
- **Converter implementation:** attempted common font-packaging changes were
  removed from `mdx2apple.py` and `tests/test_mdx2apple.py`; both match HEAD.
  Probe improvements and documentation remain uncommitted. No commit, push or
  release was completed; HEAD remains `2a870ea`.
- **Verification boundary:** 15 converter tests and the six earlier WebKit cases
  passed before the split. Native bundled-font evidence and user acceptance are
  recorded. The incomplete local preset has no successful apply verification.

Local evidence: `output/typography-audit/final-pass.json`,
`installed-verification.json`, `native-font-before.json`, and
`native-font-bundled-test.json`. The last records the user's later `other` lookup,
not the earlier `colleague` query. `font-fix-before.css` is the installed style
before the direct-font fix; `default-style-before.css` predates all typography
changes. The local source register records acceptance and the scope correction.

## Source defects and verification boundary

The source references 35 audio files absent from its MDD. It also contains
12,653 unique unresolved link targets, primarily supplemental `collocations/...`
articles not included in the source. Their text is retained without a broken
click target. A self-referential `resume` alias is reported while its actual
entries remain searchable.

### All-tab media fix (2026-10-28)

The user reported silent pronunciation buttons in Dictionary.app's **All** tab
only. That page uses `file:///System/Applications/Dictionary.app/Contents/Resources/`
as its base, so relative `src` values resolve into the app bundle. A three-variant
probe dictionary confirmed it: in the All tab the relative player read "Error" and
its image was missing, while absolute `dict-resource://` and `data:` URIs loaded.
All three worked in the dictionary's own tab. OALD's 44 px button hid the error
label. The converter now writes absolute `dict-resource://` URLs for the installed
bundle path; `data:` URIs were rejected because they would inline about 2.2 GB of
MP3 audio. Verification reads player states through Accessibility without
clicking or moving the pointer.

Dictionary.app's own playback policy, every possible click path, and system
Look Up have not been exhaustively automated. WebKit playback is useful evidence
but does not establish identical behavior in every native host. Other audio
codecs depend on the macOS WebKit version.

## Reproduce with your own files

```bash
python -m unittest discover -s tests -v

python tests/audit_native_dictionary.py \
  --source /path/to/reference-appledict.xml \
  --converted /path/to/generated-dictionary.xml \
  --dictionary "$HOME/Library/Dictionaries/example.dictionary" \
  --mdx /path/to/original.mdx \
  --compare-all \
  --output output/validation.json
```

The reference XML supports before/after content counts. `--compare-all` compares
the generated XML against native compiled records, and `--mdx` checks the actual
source keys. If only generated XML is available, pass it to both XML arguments;
that verifies compilation, not an independent source-to-XML comparison.

The audit uses an undocumented dictionary-selection API. Reports contain entry
text and belong in local output, not published test fixtures. The converter's
`conversion-report.json` separately records text-preservation checks, aliases,
resource counts and unresolved source data.

Apple's [Dictionary Services Programming Guide](https://developer.apple.com/library/archive/documentation/UserExperience/Conceptual/DictionaryServicesProgGuide/schema/schema.html)
documents images, sounds and the `x-dictionary:` reference scheme.
