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
- Stable, completed utility maintained on demand
- Published on GitHub with a working converter and regression tests
- A generated Apple Dictionary is still installed and used on the current Mac

## Maintenance
- Preserve the working conversion contract and existing CLI behavior
- Address compatibility or parsing edge cases when real dictionaries expose them; no speculative feature roadmap
