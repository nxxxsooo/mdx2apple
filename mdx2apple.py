#!/usr/bin/env python3
"""Convert complete MDict records to macOS Dictionary.app bundles."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
from html import unescape as unescape_html
import json
import os
from pathlib import Path, PurePosixPath
import plistlib
import re
import shutil
import subprocess
import sys
from urllib.parse import quote, unquote, urlsplit

from lxml import etree, html


DCS = "http://www.apple.com/DTDs/DictionaryService-1.0.rng"
XHTML = "http://www.w3.org/1999/xhtml"
ASSETS = Path(__file__).resolve().parent / "assets"
DEFAULT_CREDITS = "macOS conversion: mdx2apple."
XML_CONTROLS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
STYLE_EXTENSIONS = {".css", ".ttf", ".otf", ".woff", ".woff2"}
RESERVED_RESOURCES = {
    "body.data", "keytext.data", "keytext.index", "entryid.data",
    "entryid.index", "defaultstyle.css",
}


def check_dependencies():
    """Fail before conversion if the parser or native build tool is missing."""
    from pyglossary.plugin_lib.readmdict import MDX, MDD  # noqa: F401

    for path in (
        Path.home() / "Library/Developer/Dictionary-Development-Kit",
        Path("/Applications/Utilities/Dictionary Development Kit"),
    ):
        if (path / "bin/build_dict.sh").is_file():
            return path
    raise FileNotFoundError(
        "Dictionary Development Kit not found. Install it in "
        "~/Library/Developer/Dictionary-Development-Kit."
    )


def mdx_records(path):
    """Use PyGlossary's format reader, without its lossy output transforms."""
    from pyglossary.plugin_lib.readmdict import MDX

    for key, definition in MDX(str(path), substyle=True).items():
        yield key.decode("utf-8"), definition.decode("utf-8").rstrip("\x00")


def normalized_key(key):
    if "<" in key and ">" in key:
        key = html.fragment_fromstring(key, create_parent="span").text_content()
    return " ".join(unescape_html(key).split())


def resource_name(value):
    """MDict resource roots are virtual; never let them escape the output root."""
    value = unquote(value).replace("\\", "/")
    for prefix in ("sound://", "file://"):
        if value.startswith(prefix):
            value = value[len(prefix):]
    value = value.lstrip("/")
    path = PurePosixPath(value)
    if not value or ".." in path.parts or "\x00" in value:
        raise ValueError(f"Invalid dictionary resource path: {value!r}")
    if str(path).casefold() in RESERVED_RESOURCES:
        raise ValueError(f"Resource would overwrite an Apple Dictionary build file: {value!r}")
    return str(path)


def drop_element(node):
    """Remove non-content markup without losing the following text."""
    node.drop_tree()


class Catalog:
    """Resolve records and redirect chains before writing any entry bodies."""

    def __init__(self, records):
        self.entries = []
        self.keys = defaultdict(list)
        self.aliases = defaultdict(list)
        self.anchors = defaultdict(list)
        self.diagnostics = defaultdict(set)
        self.source_keys = set()
        self.source_records = 0
        redirects = defaultdict(list)
        for key, body in records:
            self.source_keys.add(key)
            self.source_records += 1
            target = body.strip()
            if target.startswith("@@@LINK="):
                redirects[key].append(target[8:].strip())
                continue
            entry_id = f"entry{len(self.entries) + 1:06d}"
            self.entries.append((key, entry_id))
            self.keys[key].append(entry_id)
            self.aliases[entry_id].append(key)
            # Source DOM ids let website-style cross-references select the
            # correct homograph instead of blindly removing suffixes.
            for anchor in re.findall(r'''(?<![-\w])id\s*=\s*["']([^"']+)["']''', body):
                if entry_id not in self.anchors[anchor]:
                    self.anchors[anchor].append(entry_id)

        resolved_keys = {}

        def resolve(key, visiting):
            if key in resolved_keys:
                return resolved_keys[key]
            if key in visiting:
                self.diagnostics["redirect_cycles"].add(key)
                return self.keys.get(key, [])
            if key not in redirects and key not in self.keys:
                self.diagnostics["missing_redirect_targets"].add(key)
                return []
            result = list(self.keys.get(key, []))
            for target in redirects.get(key, []):
                result.extend(resolve(target, visiting | {key}))
            result = list(dict.fromkeys(result))
            resolved_keys[key] = result
            return result

        for key in redirects:
            ids = resolve(key, set())
            if ids:
                self.keys[key] = ids
            for entry_id in ids:
                self.aliases[entry_id].append(key)
        # Retain the actual source spelling, and add convenient whitespace
        # normalization. Do not overwrite another entry's literal key.
        for key, ids in list(self.keys.items()):
            normalized = normalized_key(key)
            if normalized and normalized != key:
                for entry_id in ids:
                    if normalized not in self.aliases[entry_id]:
                        self.aliases[entry_id].append(normalized)
                self.keys.setdefault(normalized, ids)
        self.casefolded = {}
        for key, ids in self.keys.items():
            folded = key.casefold()
            current = self.casefolded.get(folded, ids)
            self.casefolded[folded] = list(dict.fromkeys(current + ids))

    def find(self, key):
        return self.keys.get(key) or self.keys.get(normalized_key(key)) or []

    def reference(self, target, entry_id, local_ids, identifier):
        """Translate actual keys and known DOM anchors to native references."""
        target = unquote(target)
        if target.startswith("#"):
            return target if target[1:] in local_ids else None
        for prefix in ("entry://", "bword://", "x-dictionary:d:", "x-dictionary:r:"):
            if target.startswith(prefix):
                target = target[len(prefix):]
                break
        key, _, fragment = target.partition("#")
        if fragment and fragment in local_ids:
            return "#" + fragment
        ids = self.find(key)
        if not ids:
            if key in local_ids:
                return "#" + key
            ids = self.anchors.get(fragment or key, [])
        if not ids and key.startswith("/definition/"):
            slug = key.rstrip("/").rsplit("/", 1)[-1]
            ids = self.find(slug) or self.anchors.get(slug, [])
            if not ids:
                # Oxford's website uses word1, while its DOM uses word_1.
                dom_id = re.sub(r"(?<=[a-z-])(\d+)$", r"_\1", slug)
                ids = self.anchors.get(dom_id, [])
            if not ids:
                ids = self.casefolded.get(slug.casefold(), [])
            if not ids:
                base = re.sub(r"\d+$", "", slug)
                ids = self.find(base) or self.find(base.replace("-", " "))
        if len(ids) == 1:
            return f"x-dictionary:r:{ids[0]}:{identifier}"
        if ids:
            return f"x-dictionary:d:{quote(key, safe='')}:{identifier}"
        return None


class EntryAdapter:
    def __init__(self, catalog, identifier):
        self.catalog = catalog
        self.identifier = identifier
        self.stylesheets = set()
        self.inline_styles = set()
        self.resources = set()
        self.counts = Counter()
        self.unresolved_links = set()

    def adapt(self, body, entry_id):
        # HTML recovery is confined to the source boundary. XML output is
        # serialized strictly and compilation errors are never skipped.
        body = XML_CONTROLS.sub("", body)
        root = html.fragment_fromstring(body, create_parent="div")
        root.set("class", "mdx-entry")
        for node in list(root.iter("script", "style", "link", "meta", "base")):
            if node.tag == "link" and "stylesheet" in node.get("rel", "").lower():
                href = node.get("href", "")
                if href and not urlsplit(href).scheme:
                    self.stylesheets.add(resource_name(href))
            elif node.tag == "style" and node.text:
                self.inline_styles.add(node.text)
            drop_element(node)
        original_text = root.text_content()
        local_ids = {n.get("id") for n in root.iter() if n.get("id")}
        for node in root.iter():
            if not isinstance(node.tag, str):
                continue
            for attr in list(node.attrib):
                if attr.lower().startswith("on"):
                    del node.attrib[attr]
            if node.get("src") and (not urlsplit(node.get("src")).scheme
                                    or node.get("src").startswith("file://")):
                name = resource_name(node.get("src"))
                node.set("src", quote(name, safe="/"))
                self.resources.add(name)
            if node.tag == "img":
                self.counts["images"] += 1
            if node.tag == "audio":
                node.set("controls", "controls")
                node.set("preload", "none")
            if node.tag != "a" or not node.get("href"):
                continue
            href = node.get("href")
            if href.startswith("sound://"):
                name = resource_name(href)
                classes = node.get("class", "").split()
                label = ("UK pronunciation" if "pron-uk" in classes else
                         "US pronunciation" if "pron-us" in classes else "Pronunciation")
                node.tag = "audio"
                node.attrib.clear()
                node.set("src", quote(name, safe="/"))
                node.set("controls", "controls")
                node.set("preload", "none")
                node.set("class", "mdx-audio")
                node.set("aria-label", label)
                node.set("title", label)
                self.resources.add(name)
                self.counts["audio"] += 1
            elif href.startswith(("http://", "https://", "mailto:")):
                continue
            else:
                resolved = self.catalog.reference(
                    href, entry_id, local_ids, self.identifier
                )
                if resolved:
                    node.set("href", resolved)
                    self.counts["resolved_links"] += 1
                else:
                    # Retain the label and all descendants. A broken source
                    # reference should not navigate to an unrelated dictionary.
                    node.attrib.pop("href")
                    node.set("data-unresolved-reference", href)
                    self.unresolved_links.add(href)
                    self.counts["unresolved_links"] += 1
        # Standard HTML disclosure works without the original MDict JavaScript.
        for pic in root.xpath(".//div[contains(concat(' ', @class, ' '), ' pic ')]"):
            thumb = pic.find("div[@class='pic_thumb']")
            large = pic.find("div[@class='big_pic']")
            if thumb is not None and large is not None:
                pic.tag = "details"
                pic.set("class", "mdx-picture")
                thumb.tag = "summary"
                thumb.attrib.clear()
                thumb.set("aria-label", "Enlarge illustration")
                large.set("class", "mdx-picture-full")
        if root.text_content() != original_text:
            raise ValueError(f"Content changed while adapting {entry_id}")
        self.counts["text_preservation_checks"] += 1
        return root


def write_entries(records, catalog, adapter, output_path):
    count = 0
    with etree.xmlfile(str(output_path), encoding="UTF-8") as output:
        output.write_declaration()
        with output.element(f"{{{DCS}}}dictionary", nsmap={None: XHTML, "d": DCS}):
            for key, body in records:
                if body.strip().startswith("@@@LINK="):
                    continue
                expected_key, entry_id = catalog.entries[count]
                if key != expected_key:
                    raise ValueError("MDX records changed during conversion")
                title = normalized_key(key)
                if not title:
                    raise ValueError("MDX contains an entry with an empty headword")
                node = adapter.adapt(body, entry_id)
                with output.element(f"{{{DCS}}}entry", {"id": entry_id, f"{{{DCS}}}title": title}):
                    for alias in dict.fromkeys(catalog.aliases[entry_id]):
                        if not alias.strip():
                            catalog.diagnostics["empty_index_keys"].add(alias)
                            continue
                        with output.element(f"{{{DCS}}}index", {
                            f"{{{DCS}}}value": alias, f"{{{DCS}}}title": title,
                        }):
                            pass
                    output.write(node)
                count += 1
                output.write("\n")
                if count % 5000 == 0:
                    print(f"  Converted {count:,}/{len(catalog.entries):,} entries", flush=True)
    if count != len(catalog.entries):
        raise ValueError("MDX record count changed during conversion")
    return count


def extract_resources(mdx_path, destination, adapter, keep_resources):
    from pyglossary.plugin_lib.readmdict import MDD

    destination.mkdir(parents=True, exist_ok=True)
    archives = [mdx_path.with_suffix(".mdd"), mdx_path.with_suffix(".1.mdd")]
    number = 2
    while mdx_path.with_suffix(f".{number}.mdd").exists():
        archives.append(mdx_path.with_suffix(f".{number}.mdd"))
        number += 1
    saved = set()
    for archive in archives:
        if not archive.is_file():
            continue
        print(f"Extracting {archive.name}...", flush=True)
        for key, data in MDD(str(archive)).items():
            name = resource_name(key.decode("utf-8"))
            if not keep_resources and Path(name).suffix.lower() not in STYLE_EXTENSIONS:
                continue
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            saved.add(name)
    # Sidecar styles/assets may customize or supplement the archive. Copy only
    # referenced paths, never unrelated databases or other neighboring files.
    pending = deque(sorted(adapter.stylesheets))
    if keep_resources:
        pending.extend(sorted(adapter.resources))
    visited = set()
    while pending:
        name = pending.popleft()
        if name in visited:
            continue
        visited.add(name)
        src = mdx_path.parent / name
        if src.is_file():
            resolved = src.resolve()
            resolved.relative_to(mdx_path.parent.resolve())
            dest = destination / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            saved.add(name)
        dest = destination / name
        if dest.is_file() and dest.suffix.lower() == ".css":
            css = dest.read_text(encoding="utf-8-sig")
            for value in re.findall(r'''url\(\s*["']?([^\)"']+)["']?\s*\)''', css):
                if urlsplit(value).scheme or value.startswith("#"):
                    continue
                # CSS paths are relative to the stylesheet, not the entry.
                relative = os.path.normpath(str(Path(name).parent / unquote(value)))
                pending.append(resource_name(relative))
    return saved


def create_css(output_path, stylesheets=(), inline_styles=()):
    # @import must precede @namespace and ordinary rules in CSS.
    imports = "".join(f'@import url("{quote(name, safe="/")}");\n'
                      for name in sorted(stylesheets))
    base = (ASSETS / "dictionary.css").read_text()
    output_path.write_text(
        '@charset "UTF-8";\n' + imports
        + f'@namespace d url({DCS});\n'
        + "\n".join(sorted(inline_styles)) + "\n" + base,
        encoding="utf-8",
    )


def create_plist(output_path, name, identifier, copyright_text="", *,
                 short_name=None, publisher="", credits=DEFAULT_CREDITS):
    """Keep the full title, toolbar label, content owner and tool credit distinct."""
    data = {
        "CFBundleDevelopmentRegion": "English",
        "CFBundleIdentifier": identifier,
        "CFBundleDisplayName": name,
        "CFBundleName": short_name or name,
        "CFBundleShortVersionString": "2.0",
        "DCSDictionaryCopyright": "\n".join(
            part.strip() for part in (copyright_text, credits) if part.strip()
        ),
        "DCSDictionaryManufacturerName": publisher,
    }
    output_path.write_bytes(plistlib.dumps(data))


def create_makefile(output_path, ddk_path, dict_name):
    # Build from an empty working directory so DDK's OtherResources/* glob
    # cannot exceed ARG_MAX. ditto copies the resource tree afterwards.
    output_path.write_text(f'''DICT_NAME = {dict_name}
DICT_BUILD_TOOL_DIR = {ddk_path}
DESTINATION_FOLDER = $(HOME)/Library/Dictionaries

all:
\tmkdir -p .build
\tcd .build && DICT_DEV_KIT_OBJ_DIR=../objects "$(DICT_BUILD_TOOL_DIR)/bin/build_dict.sh" -v 10.11 "$(DICT_NAME)" "../$(DICT_NAME).xml" "../$(DICT_NAME).css" "../$(DICT_NAME).plist"
\tditto --noextattr --norsrc OtherResources "objects/$(DICT_NAME).dictionary/Contents/Resources"

install:
\tmkdir -p "$(DESTINATION_FOLDER)"
\tditto --noextattr --norsrc "objects/$(DICT_NAME).dictionary" "$(DESTINATION_FOLDER)/$(DICT_NAME).dictionary"
\ttouch "$(DESTINATION_FOLDER)"

clean:
\trm -rf objects .build
''', encoding="utf-8")


def convert_mdx(mdx_path, output_dir, identifier, keep_resources=False):
    print("Indexing original MDX records and aliases...", flush=True)
    catalog = Catalog(mdx_records(mdx_path))
    adapter = EntryAdapter(catalog, identifier)
    base_name = bundle_name(mdx_path)
    xml_path = output_dir / f"{base_name}.xml"
    count = write_entries(mdx_records(mdx_path), catalog, adapter, xml_path)
    resource_dir = output_dir / "OtherResources"
    if resource_dir.exists():
        raise FileExistsError(f"Resource directory already exists: {resource_dir}; use a fresh output directory")
    saved = extract_resources(mdx_path, resource_dir, adapter, keep_resources)
    missing_styles = adapter.stylesheets - saved
    if missing_styles:
        raise FileNotFoundError(f"Missing source stylesheets: {sorted(missing_styles)}")
    create_css(output_dir / f"{base_name}.css", adapter.stylesheets, adapter.inline_styles)
    report = {
        "entries": count,
        "source_records": catalog.source_records,
        "source_keys": len(catalog.source_keys),
        "indexed_keys": len(catalog.keys),
        "adapted": dict(adapter.counts),
        "unresolved_links": sorted(adapter.unresolved_links),
        "redirect_diagnostics": {key: sorted(values) for key, values in catalog.diagnostics.items()},
        "resources_included": keep_resources,
        "resources_written": len(saved),
        "missing_resources": sorted(adapter.resources - saved) if keep_resources else [],
    }
    (output_dir / "conversion-report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Converted {count:,} complete entries; report: {output_dir / 'conversion-report.json'}", flush=True)
    return report


def bundle_name(mdx_path):
    name = re.sub(r"[^A-Za-z0-9_]", "_", mdx_path.stem).strip("_")
    return name or "dictionary_" + hashlib.sha256(mdx_path.stem.encode()).hexdigest()[:12]


def run_make(ddk_path, target=None, cwd=None):
    cmd = ["make", f"DICT_BUILD_TOOL_DIR={ddk_path}"]
    if target:
        cmd.append(target)
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", help="Input .mdx file")
    parser.add_argument("--name", help="Full dictionary name in Settings")
    parser.add_argument("--short-name", help="Compact dictionary name for toolbar tabs")
    parser.add_argument("--copyright", default="", help="Original dictionary copyright notice")
    parser.add_argument("--publisher", default="", help="Original dictionary publisher")
    parser.add_argument("--credits", default=DEFAULT_CREDITS, help="Conversion credit below the copyright")
    parser.add_argument("--output", "-o", default="./output", help="Fresh output directory")
    parser.add_argument("--identifier", help="Bundle identifier (e.g., com.example.dict)")
    parser.add_argument("--install", action="store_true", help="Build and install after conversion")
    parser.add_argument("--keep-resources", action="store_true", help="Include audio/image resources")
    args = parser.parse_args()
    try:
        mdx_path = Path(args.input).expanduser().resolve(strict=True)
        ddk = check_dependencies()
        output_dir = Path(args.output).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        if any(output_dir.iterdir()):
            raise FileExistsError(f"Output directory is not empty: {output_dir}; choose a fresh directory")
        base_name = bundle_name(mdx_path)
        identifier = args.identifier or f"com.mdx2apple.{base_name.lower().replace('_', '-')}"
        if not re.fullmatch(r"[A-Za-z0-9.-]+", identifier):
            raise ValueError("Bundle identifier must contain only ASCII letters, digits, dots or hyphens")
        convert_mdx(mdx_path, output_dir, identifier, args.keep_resources)
        create_plist(
            output_dir / f"{base_name}.plist", args.name or mdx_path.stem, identifier,
            args.copyright, short_name=args.short_name, publisher=args.publisher,
            credits=args.credits,
        )
        create_makefile(output_dir / "Makefile", ddk, base_name)
        if args.install:
            for target in (None, "install"):
                result = run_make(ddk, target, output_dir)
                (output_dir / f"{target or 'build'}.log").write_text(result.stdout + result.stderr)
                if result.returncode:
                    raise RuntimeError(f"{target or 'Build'} failed; see {output_dir / (target or 'build')}.log")
            subprocess.run(["killall", "Dictionary"], capture_output=True)
            subprocess.run(["killall", "DictionaryWorkerService"], capture_output=True)
            print(f"Installed: {Path.home() / 'Library/Dictionaries' / (base_name + '.dictionary')}")
        else:
            print(f'Build: make -C "{output_dir}"\nInstall: make -C "{output_dir}" install')
    except (OSError, ValueError, ImportError, RuntimeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
