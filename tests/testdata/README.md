# tests/testdata

Synthetic regression fixtures for the shapes exposed by real dictionaries.
No dictionary text is copied here: headwords are common words or invented
placeholders, and every definition line is written for the fixture.

- `xindehan-edge-cases.json` — 新德汉 shapes: literal angle-bracket grammar
  notes (`<Int.>`), unclosed usage notes (`<Fotografie`), JS restyling
  remnants, inflection redirects.
- `bilingual-edge-cases.json` — Duden / Langenscheidt shapes: Chinese reverse
  keys, verbatim trailer text, unresolved `entry://` labels, literal usage
  notes (`<umg.>`).
- `manifest.json` — what each fixture covers and where the real logic lives.

Bodies use the **post-repair** form (`&lt;` for literal brackets). The
`LITERAL_ANGLE` repair is per-dictionary logic in the local prepare scripts
(`.local/`, git-ignored), not part of the shared converter. Likewise,
promotional-footer stripping is a local prepare step: the converter must keep
trailer text verbatim, and the bilingual fixture locks that in.

The real `.mdx` corpora stay in `materials/` (git-ignored, machine-local) and
are never committed to this public repo. OALD shapes (senses, examples,
illustrations, audio, collapsed sections) are already covered by
`tests/test_mdx2apple.py` unit tests, so no OALD fixture is needed here.
