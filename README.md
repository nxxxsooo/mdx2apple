# mdx2apple

[中文文档](README_CN.md)

Convert MDict (.mdx) dictionaries to macOS Dictionary.app format.

## Why?

MDict dictionaries have complex HTML structures that Apple Dictionary can't render properly. This tool:

1. Converts MDX → AppleDict XML (via pyglossary)
2. **Cleans and simplifies HTML** to work with Dictionary.app
3. Generates optimized CSS and plist
4. Builds and installs the dictionary

## Requirements

- macOS
- Python 3.8+
- Dictionary Development Kit (auto-installed from GitHub mirror)

## Installation

```bash
# Clone repo
git clone https://github.com/nxxxsooo/mdx2apple.git
cd mdx2apple

# Install dependencies
pip install pyglossary lxml beautifulsoup4 html5lib

# Install DDK (if not already installed)
git clone https://github.com/ikey4u/macddk.git ~/Library/Developer/Dictionary-Development-Kit
```

## Usage

### Basic

```bash
python mdx2apple.py /path/to/dictionary.mdx
```

### With options

```bash
python mdx2apple.py /path/to/dictionary.mdx \
    --name "Oxford Dictionary" \
    --output ./my_dict \
    --install
```

### Options

| Option | Description |
|--------|-------------|
| `--name` | Display name in Dictionary.app |
| `--output`, `-o` | Output directory (default: `./output`) |
| `--identifier` | Bundle ID (e.g., `com.example.dict`) |
| `--install` | Build and install after conversion |
| `--keep-resources` | Include audio/images (large files) |

## Manual Build

After conversion:

```bash
cd output
make          # Build dictionary
make install  # Install to ~/Library/Dictionaries
```

To add audio/image resources:

```bash
rsync -a OtherResources/ ~/Library/Dictionaries/DICT_NAME.dictionary/Contents/Resources/
```

## Limitations

- **No audio playback**: Apple Dictionary doesn't support JavaScript audio
- **Simplified styling**: Complex CSS from MDict is stripped
- **Large dictionaries**: May take several minutes to process

## How it works

1. **pyglossary** converts MDX to AppleDict XML format
2. **BeautifulSoup** parses and cleans each entry:
   - Extracts: headword, pronunciation, definitions, examples
   - Removes: custom attributes, JavaScript, complex nesting
   - Escapes: XML special characters (`&`, `<`, `>`)
3. Generates simplified **CSS** with `d|entry { display: block; }` (critical!)
4. Creates minimal **plist** (complex plists can cause issues)
5. **DDK** compiles to `.dictionary` bundle

## Troubleshooting

### Dictionary shows entries but content is blank

- Check CSS has `d|entry { display: block; }`
- Use simplified plist (see `mdx2apple.py`)
- Try building a smaller test dictionary first

### Build fails with "Argument list too long"

- Move `OtherResources/` folder before building
- Add resources back with `rsync` after install

### Dictionary not appearing

```bash
rm -rf ~/Library/Caches/com.apple.Dictionary
killall Dictionary
killall DictionaryWorkerService
```

## Credits

- [pyglossary](https://github.com/ilius/pyglossary) - Dictionary format conversion
- [macddk](https://github.com/ikey4u/macddk) - DDK GitHub mirror

## License

MIT
