# mdx2apple

## Overview
Converter tool: MDict .mdx dictionary files → Apple Dictionary format (.dictionary). Enables using MDict dictionaries in macOS Dictionary.app.

## Architecture
- Python-based converter
- Reads .mdx/.mdd via PyGlossary's format reader → preserves complete HTML and resolves aliases/media → generates Apple Dictionary XML → compiles via Dictionary Development Kit

## Key Files
- Main converter script (root)
- `README.md` + `README_CN.md` — Bilingual docs

## Current Status
- Full-content converter with aliases, native audio, illustrations and Oxford dark-mode styling
- Source-only distribution on GitHub; no versioned release or CI automation is configured
- Reproduce validation with `python -m unittest discover -s tests -v`; corpus checks use `tests/audit_native_dictionary.py`
- Validation scope and results: `docs/oald-native-audit.md`

## Maintenance
- Preserve the working conversion contract and existing CLI behavior
- Keep personal fonts and reading-layout presets in per-dictionary overrides; shared converter defaults must stay font-neutral
- Address compatibility or parsing edge cases when real dictionaries expose them; no speculative feature roadmap
- Entry media use the installed bundle's absolute `dict-resource://` URL: Dictionary.app's All tab resolves relative paths against its own bundle. Check media in the All tab, not only the dictionary's own tab
- Inspect the live Dictionary.app through Accessibility reads only; never synthesize clicks or move the user's pointer
