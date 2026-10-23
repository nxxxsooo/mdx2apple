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
after removing source scripts and styles. All 15 regression tests pass.

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

## Source defects and verification boundary

The source references 35 audio files absent from its MDD. It also contains
12,653 unique unresolved link targets, primarily supplemental `collocations/...`
articles not included in the source. Their text is retained without a broken
click target. A self-referential `resume` alias is reported while its actual
entries remain searchable.

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
