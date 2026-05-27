# mdx2apple

## Overview
Converter tool: MDict .mdx dictionary files → Apple Dictionary format (.dictionary). Enables using MDict dictionaries in macOS Dictionary.app.

## Architecture
- Python-based converter
- Reads .mdx via mdict-utils → generates Apple Dictionary XML → compiles via Dictionary Development Kit

## Key Files
- Main converter script (root)
- `README.md` + `README_CN.md` — Bilingual docs

## Current Status
- ✅ Published on GitHub
- ✅ Initial commit with working converter

## Next Steps
- Polish documentation
- Handle edge cases in .mdx parsing
