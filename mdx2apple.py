#!/usr/bin/env python3
"""
mdx2apple - Convert MDict (.mdx) dictionaries to Apple Dictionary format

This tool converts MDict dictionaries to macOS Dictionary.app format,
handling the complex HTML structures that cause display issues.

Usage:
    python mdx2apple.py input.mdx [--name "Dictionary Name"] [--output ./output]
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("Error: beautifulsoup4 required. Run: pip install beautifulsoup4")
    sys.exit(1)


def check_dependencies():
    """Check if required tools are installed."""
    # Check pyglossary
    try:
        import pyglossary
    except ImportError:
        print("Error: pyglossary required. Run: pip install pyglossary lxml html5lib")
        sys.exit(1)
    
    # Check DDK
    ddk_paths = [
        os.path.expanduser("~/Library/Developer/Dictionary-Development-Kit"),
        "/Applications/Utilities/Dictionary Development Kit",
    ]
    
    for path in ddk_paths:
        if os.path.exists(os.path.join(path, "bin", "build_dict.sh")):
            return path
    
    print("Error: Dictionary Development Kit not found.")
    print("Install with: git clone https://github.com/ikey4u/macddk.git ~/Library/Developer/Dictionary-Development-Kit")
    sys.exit(1)


def escape_xml(text):
    """Escape special XML characters."""
    if not text:
        return ""
    text = str(text)
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    return text


def clean_entry(entry):
    """Clean a single dictionary entry, simplifying HTML structure."""
    # Extract entry tag
    entry_tag_match = re.match(r'<d:entry[^>]*>', entry)
    if not entry_tag_match:
        return None
    entry_tag = entry_tag_match.group(0)
    
    # Extract d:index tags (must keep all of them!)
    indexes = re.findall(r'<d:index[^>]*/>', entry)
    if not indexes:
        return None
    indexes_str = "\n".join(indexes)
    
    # Get content after indexes
    last_index = entry.rfind('<d:index')
    if last_index > 0:
        end_of_last_index = entry.find('/>', last_index) + 2
        inner_html = entry[end_of_last_index:entry.rfind('</d:entry>')]
    else:
        inner_html = entry[entry_tag_match.end():entry.rfind('</d:entry>')]
    
    try:
        soup = BeautifulSoup(inner_html, 'html.parser')
        clean_parts = []
        
        # Get headword
        headword = soup.find('h1', class_='headword') or soup.find('h1')
        if headword:
            clean_parts.append(f"<h1>{escape_xml(headword.get_text())}</h1>")
        
        # Get part of speech
        pos = soup.find('span', class_='pos')
        if pos:
            clean_parts.append(f"<p><i>{escape_xml(pos.get_text())}</i></p>")
        
        # Get pronunciation
        phons = soup.find_all('span', class_='phon')
        if phons:
            pron_text = ' '.join([p.get_text() for p in phons[:2]])
            clean_parts.append(f"<p>{escape_xml(pron_text)}</p>")
        
        # Get definitions and examples
        senses = soup.find_all('li', class_='sense')
        if senses:
            clean_parts.append("<ol>")
            for sense in senses[:10]:
                clean_parts.append("<li>")
                
                # Definition (English)
                defn = sense.find('span', class_='def')
                if defn:
                    clean_parts.append(f"<p><b>{escape_xml(defn.get_text())}</b></p>")
                
                # Chinese definition
                for chn_tag in ['deft', 'chn']:
                    chn_container = sense.find(chn_tag)
                    if chn_container:
                        chn = chn_container.find('chn') if chn_tag == 'deft' else chn_container
                        if chn:
                            clean_parts.append(f"<p>{escape_xml(chn.get_text())}</p>")
                            break
                
                # Examples (limit to 2)
                examples_found = 0
                for ex in sense.find_all('span', class_='x'):
                    if examples_found >= 2:
                        break
                    ex_text = escape_xml(ex.get_text())
                    
                    # Find Chinese translation
                    parent = ex.find_parent('li')
                    chn_text = ""
                    if parent:
                        xt = parent.find('xt')
                        if xt:
                            chn_el = xt.find('chn')
                            if chn_el:
                                chn_text = escape_xml(chn_el.get_text())
                    
                    if chn_text:
                        clean_parts.append(f"<p class='ex'>• {ex_text} {chn_text}</p>")
                    else:
                        clean_parts.append(f"<p class='ex'>• {ex_text}</p>")
                    examples_found += 1
                
                clean_parts.append("</li>")
            clean_parts.append("</ol>")
        
        # Fallback: if no structured content, get plain text
        if len(clean_parts) <= 1:
            text = escape_xml(soup.get_text(separator=' ', strip=True)[:500])
            if text:
                clean_parts.append(f"<p>{text}</p>")
        
        return f"{entry_tag}\n{indexes_str}\n" + "\n".join(clean_parts) + "\n</d:entry>"
        
    except Exception as e:
        print(f"Warning: Error processing entry: {e}")
        return None


def clean_xml(input_path, output_path):
    """Clean the entire XML file."""
    print(f"Reading {input_path}...")
    with open(input_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Extract header
    header_end = content.find('<d:entry')
    header = content[:header_end]
    
    # Find all entries
    entries = re.findall(r'<d:entry[^>]*>.*?</d:entry>', content, re.DOTALL)
    print(f"Found {len(entries)} entries")
    
    # Clean entries
    print("Cleaning entries...")
    clean_entries = []
    for i, entry in enumerate(entries):
        if i % 5000 == 0:
            print(f"  Progress: {i}/{len(entries)}")
        cleaned = clean_entry(entry)
        if cleaned:
            clean_entries.append(cleaned)
    
    print(f"Writing {len(clean_entries)} cleaned entries...")
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(header)
        f.write("\n".join(clean_entries))
        f.write("\n</d:dictionary>\n")
    
    return len(clean_entries)


def create_css(output_path):
    """Create optimized CSS for Apple Dictionary."""
    css = """@charset "UTF-8";
@namespace d url(http://www.apple.com/DTDs/DictionaryService-1.0.rng);

@media (prefers-color-scheme: dark) {
    html { -apple-color-filter: apple-invert-lightness(); }
}

d|entry {
    display: block;
}

h1 {
    font-size: 150%;
    font-weight: bold;
    margin-bottom: 0.3em;
}

p {
    margin: 0.3em 0;
}

ol {
    margin-left: 1em;
    padding-left: 0.5em;
}

li {
    margin: 0.5em 0;
}

.ex {
    color: #666;
    margin-left: 1em;
}

@media (prefers-color-scheme: dark) {
    .ex { color: #aaa; }
}
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(css)


def create_plist(output_path, name, identifier, copyright_text=""):
    """Create simplified plist for Apple Dictionary."""
    plist = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleDevelopmentRegion</key>
    <string>English</string>
    <key>CFBundleIdentifier</key>
    <string>{identifier}</string>
    <key>CFBundleDisplayName</key>
    <string>{name}</string>
    <key>CFBundleName</key>
    <string>{identifier.split('.')[-1]}</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>DCSDictionaryCopyright</key>
    <string>{copyright_text or 'Converted by mdx2apple'}</string>
    <key>DCSDictionaryManufacturerName</key>
    <string>mdx2apple</string>
</dict>
</plist>
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(plist)


def create_makefile(output_path, ddk_path, dict_name):
    """Create Makefile for building the dictionary."""
    makefile = f"""#
# Makefile for {dict_name}
#

DICT_NAME = "{dict_name}"
DICT_SRC_PATH = "{dict_name}.xml"
CSS_PATH = "{dict_name}.css"
PLIST_PATH = "{dict_name}.plist"

DICT_BUILD_OPTS = -v 10.11
DICT_BUILD_TOOL_DIR = "{ddk_path}"
DICT_BUILD_TOOL_BIN = "$(DICT_BUILD_TOOL_DIR)/bin"

DICT_DEV_KIT_OBJ_DIR = ./objects
export DICT_DEV_KIT_OBJ_DIR

DESTINATION_FOLDER = ~/Library/Dictionaries
RM = /bin/rm

all:
\t"$(DICT_BUILD_TOOL_BIN)/build_dict.sh" $(DICT_BUILD_OPTS) $(DICT_NAME) $(DICT_SRC_PATH) $(CSS_PATH) $(PLIST_PATH)
\t@echo "Done."

install:
\t@echo "Installing into $(DESTINATION_FOLDER)"
\tmkdir -p $(DESTINATION_FOLDER)
\tditto --noextattr --norsrc $(DICT_DEV_KIT_OBJ_DIR)/$(DICT_NAME).dictionary $(DESTINATION_FOLDER)/$(DICT_NAME).dictionary
\ttouch $(DESTINATION_FOLDER)
\t@echo "Done. Restart Dictionary.app to use."

clean:
\t$(RM) -rf $(DICT_DEV_KIT_OBJ_DIR)
"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(makefile)


def convert_mdx(mdx_path, output_dir):
    """Convert MDX to AppleDict source using PyGlossary's Python entrypoint."""
    print(f"Converting {mdx_path} to AppleDict format...")

    # PyGlossary does not expose a pyglossary.__main__ module, so invoke its
    # CLI entrypoint with the same interpreter running this script.
    inline_code = "from pyglossary.ui.main import main; main()"

    cmd = [
        sys.executable,
        "-c",
        inline_code,
        str(mdx_path),
        str(output_dir / "temp.apple"),
        "--write-format=AppleDict",
        "-v3"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error: pyglossary failed:\n{result.stderr}")
        sys.exit(1)

    return output_dir / "temp.apple"


def run_make(ddk_path, target=None):
    """Run Make with the discovered Dictionary Development Kit path."""
    cmd = ["make", f"DICT_BUILD_TOOL_DIR={ddk_path}"]
    if target:
        cmd.append(target)
    return subprocess.run(cmd, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(
        description="Convert MDict (.mdx) to Apple Dictionary format"
    )
    parser.add_argument("input", help="Input .mdx file")
    parser.add_argument("--name", help="Dictionary display name")
    parser.add_argument("--output", "-o", default="./output", help="Output directory")
    parser.add_argument("--identifier", help="Bundle identifier (e.g., com.example.dict)")
    parser.add_argument("--install", action="store_true", help="Install after building")
    parser.add_argument("--keep-resources", action="store_true", 
                        help="Include audio/image resources (large)")
    
    args = parser.parse_args()
    
    # Validate input
    mdx_path = Path(args.input)
    if not mdx_path.exists():
        print(f"Error: {mdx_path} not found")
        sys.exit(1)
    
    # Check dependencies
    ddk_path = check_dependencies()
    print(f"Using DDK: {ddk_path}")
    
    # Setup output
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Determine names
    base_name = mdx_path.stem.replace(" ", "_").replace("-", "_")
    dict_name = args.name or base_name
    identifier = args.identifier or f"com.mdx2apple.{base_name.lower()}"
    
    print(f"\nConverting: {mdx_path.name}")
    print(f"Output: {output_dir}")
    print(f"Name: {dict_name}")
    
    # Step 1: Convert MDX to AppleDict source
    apple_dir = convert_mdx(mdx_path, output_dir)
    
    # Find the generated XML
    xml_files = list(apple_dir.glob("*.xml"))
    if not xml_files:
        print("Error: No XML file generated")
        sys.exit(1)
    
    orig_xml = xml_files[0]
    
    # Step 2: Clean XML
    clean_xml_path = output_dir / f"{base_name}.xml"
    entry_count = clean_xml(orig_xml, clean_xml_path)
    
    # Step 3: Create CSS
    css_path = output_dir / f"{base_name}.css"
    create_css(css_path)
    
    # Step 4: Create plist
    plist_path = output_dir / f"{base_name}.plist"
    create_plist(plist_path, dict_name, identifier)
    
    # Step 5: Create Makefile
    makefile_path = output_dir / "Makefile"
    create_makefile(makefile_path, ddk_path, base_name)
    
    # Step 6: Handle resources
    resources_dir = apple_dir / "OtherResources"
    if resources_dir.exists() and args.keep_resources:
        target_resources = output_dir / "OtherResources"
        if target_resources.exists():
            shutil.rmtree(target_resources)
        shutil.move(str(resources_dir), str(target_resources))
        print(f"Resources moved to {target_resources}")
    
    # Clean up temp
    shutil.rmtree(apple_dir)
    
    print(f"\n✅ Conversion complete!")
    print(f"   Entries: {entry_count}")
    print(f"\nNext steps:")
    print(f"   cd {output_dir}")
    print(f"   make          # Build dictionary")
    print(f"   make install  # Install to ~/Library/Dictionaries")
    
    if args.keep_resources:
        print(f"\nTo add resources after install:")
        print(f"   rsync -a OtherResources/ ~/Library/Dictionaries/{base_name}.dictionary/Contents/Resources/")
    
    # Build if requested
    if args.install:
        print("\nBuilding...")
        os.chdir(output_dir)
        
        # Move resources temporarily if they exist
        resources_moved = False
        if (output_dir / "OtherResources").exists():
            shutil.move(str(output_dir / "OtherResources"), "/tmp/mdx2apple_resources")
            resources_moved = True
        
        result = run_make(ddk_path)
        if result.returncode != 0:
            print(f"Build failed:\n{result.stderr}")
            sys.exit(1)

        result = run_make(ddk_path, "install")
        if result.returncode != 0:
            print(f"Install failed:\n{result.stderr}")
            sys.exit(1)
        
        # Add resources
        if resources_moved:
            shutil.move("/tmp/mdx2apple_resources", str(output_dir / "OtherResources"))
            dict_resources = Path.home() / "Library/Dictionaries" / f"{base_name}.dictionary/Contents/Resources"
            subprocess.run(["rsync", "-a", str(output_dir / "OtherResources") + "/", str(dict_resources) + "/"])
        
        # Clear cache
        cache_dir = Path.home() / "Library/Caches/com.apple.Dictionary"
        if cache_dir.exists():
            shutil.rmtree(cache_dir)
        
        subprocess.run(["killall", "Dictionary"], capture_output=True)
        subprocess.run(["killall", "DictionaryWorkerService"], capture_output=True)
        
        print("\n✅ Dictionary installed! Open Dictionary.app to use.")


if __name__ == "__main__":
    main()
