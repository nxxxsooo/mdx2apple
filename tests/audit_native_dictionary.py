"""Opt-in, read-only audit of a real Apple Dictionary against its source XML.

Run on macOS with --source, --converted, --dictionary and --output. The licensed
dictionary files and the generated report stay outside the test fixtures.
"""

import argparse
import ctypes as C
import json
import re
import sqlite3
import statistics
import time
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path


DCS_NS = "{http://www.apple.com/DTDs/DictionaryService-1.0.rng}"
SAMPLE_WORDS = {
    "apple", "bank", "better", "children", "color", "colour", "get", "give",
    "hello", "ice cream", "look up", "résumé", "run", "set", "take", "went",
    "zebra", "zygote",
}


class CFRange(C.Structure):
    _fields_ = [("location", C.c_long), ("length", C.c_long)]


class NativeDictionary:
    """Use Apple's actual DictionaryServices engine, without opening a window.

    Dictionary creation is an undocumented diagnostic API; definition retrieval
    uses DCSCopyTextDefinition. Fail explicitly if this macOS no longer has it.
    Signatures: NSHipster/DictionaryKit, DictionaryKit/TTTDictionary.m.
    """

    def __init__(self, path):
        self.cf = C.CDLL(
            "/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation"
        )
        self.dcs = C.CDLL(
            "/System/Library/Frameworks/CoreServices.framework/Frameworks/"
            "DictionaryServices.framework/DictionaryServices"
        )
        ptr = C.c_void_p
        signatures = [
            (self.cf, "CFStringCreateWithCString", ptr, [ptr, C.c_char_p, C.c_uint32]),
            (self.cf, "CFStringGetLength", C.c_long, [ptr]),
            (self.cf, "CFStringGetCString", C.c_bool,
             [ptr, ptr, C.c_long, C.c_uint32]),
            (self.cf, "CFURLCreateFromFileSystemRepresentation", ptr,
             [ptr, C.c_char_p, C.c_long, C.c_bool]),
            (self.cf, "CFRelease", None, [ptr]),
            (self.dcs, "DCSDictionaryCreate", ptr, [ptr]),
            (self.dcs, "DCSDictionaryGetName", ptr, [ptr]),
            (self.dcs, "DCSCopyTextDefinition", ptr, [ptr, ptr, CFRange]),
            (self.dcs, "DCSCopyRecordsForSearchString", ptr, [ptr, ptr, ptr, ptr]),
            (self.dcs, "DCSRecordCopyData", ptr, [ptr, C.c_long]),
            (self.cf, "CFArrayGetCount", C.c_long, [ptr]),
            (self.cf, "CFArrayGetValueAtIndex", ptr, [ptr, C.c_long]),
        ]
        for lib, name, result, args in signatures:
            fn = getattr(lib, name)
            fn.restype = result
            fn.argtypes = args
        encoded = bytes(Path(path).resolve())
        url = self.cf.CFURLCreateFromFileSystemRepresentation(
            None, encoded, len(encoded), True
        )
        try:
            self.dictionary = self.dcs.DCSDictionaryCreate(url)
        finally:
            self.cf.CFRelease(url)
        if not self.dictionary:
            raise RuntimeError(f"DictionaryServices could not open {path}")
        self.name = self.string(self.dcs.DCSDictionaryGetName(self.dictionary))

    def string(self, value):
        if not value:
            return None
        buf = C.create_string_buffer(self.cf.CFStringGetLength(value) * 4 + 1)
        if not self.cf.CFStringGetCString(value, buf, len(buf), 0x08000100):
            raise ValueError("Cannot decode CoreFoundation string")
        return buf.value.decode("utf-8")

    def lookup(self, word):
        value = self.cf.CFStringCreateWithCString(None, word.encode(), 0x08000100)
        try:
            result = self.dcs.DCSCopyTextDefinition(
                self.dictionary, value,
                CFRange(0, self.cf.CFStringGetLength(value)),
            )
            try:
                return self.string(result)
            finally:
                if result:
                    self.cf.CFRelease(result)
        finally:
            self.cf.CFRelease(value)

    def close(self):
        self.cf.CFRelease(self.dictionary)

    def records(self, word, version=3):
        """Return every matching record (3=text, 1=Dictionary.app HTML/CSS)."""
        value = self.cf.CFStringCreateWithCString(None, word.encode(), 0x08000100)
        records = self.dcs.DCSCopyRecordsForSearchString(self.dictionary, value, None, None)
        try:
            if not records:
                return []
            result = []
            for index in range(self.cf.CFArrayGetCount(records)):
                record = self.cf.CFArrayGetValueAtIndex(records, index)
                data = self.dcs.DCSRecordCopyData(record, version)
                try:
                    result.append(self.string(data) or "")
                finally:
                    if data:
                        self.cf.CFRelease(data)
            return result
        finally:
            if records:
                self.cf.CFRelease(records)
            self.cf.CFRelease(value)


def normalized(text):
    return re.sub(r"\s+", "", text)


def inspect_xml(path, converted=False):
    totals = Counter()
    samples = {}
    keys = set()
    headwords = set()
    entries = {}
    for _, entry in ET.iterparse(path, events=("end",)):
        if entry.tag != DCS_NS + "entry":
            continue
        indexes = [i.get(DCS_NS + "value") for i in entry.findall(DCS_NS + "index")]
        keys.update(indexes)
        if indexes:
            headwords.add(indexes[0])
        counts = Counter()
        for node in entry.iter():
            tag = node.tag.split("}")[-1]
            classes = set(node.get("class", "").split())
            counts["definitions"] += "def" in classes or (converted and tag == "b")
            counts["senses"] += "sense" in classes
            counts["examples"] += bool(classes & {"x", "unx", "ex"}) or (
                converted and tag == "p" and "".join(node.itertext()).lstrip().startswith("•")
            )
            counts["links"] += tag == "a" and bool(node.get("href"))
            counts["images"] += tag == "img"
            counts["audio_links"] += tag == "a" and ".mp3" in node.get("href", "")
            counts["idiom_labels"] += "idm" in classes
            counts["pos_labels"] += "pos" in classes or (converted and tag == "i")
        text = "".join(entry.itertext())
        counts["text_chars"] = len(normalized(text))
        totals.update(counts)
        totals["entries"] += 1
        totals["indexes"] += len(indexes)
        entries[entry.get("id")] = dict(counts)
        for word in SAMPLE_WORDS.intersection(indexes):
            samples[word] = {"id": entry.get("id"), **counts, "text": text}
        entry.clear()
    return {"totals": dict(totals), "samples": samples}, keys, headwords, entries


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--converted", type=Path, required=True)
    parser.add_argument("--dictionary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mdx-index", type=Path,
                        help="Optional existing MDX_INDEX database; may include synthetic keys")
    parser.add_argument("--mdx", type=Path, help="Original MDX for authoritative source-key coverage")
    parser.add_argument("--compare-all", action="store_true",
                        help="Compare every compiled entry's full text, including homographs")
    args = parser.parse_args()
    source, source_keys, _, original_entries = inspect_xml(args.source)
    converted, keys, heads, converted_entries = inspect_xml(args.converted, True)
    print(f"Source: {len(original_entries):,} entries; {len(source_keys):,} unique keys", flush=True)
    native = NativeDictionary(args.dictionary)
    missing = []
    timings = []
    started = time.perf_counter()
    raw_lookup = None
    full_text = None
    try:
        for number, word in enumerate(sorted(keys), 1):
            start = time.perf_counter()
            text = native.lookup(word)
            timings.append((time.perf_counter() - start) * 1000)
            if not text or not text.strip():
                missing.append(word)
            if number % 25000 == 0:
                print(f"Lookups: {number:,}/{len(keys):,}; missing: {len(missing)}", flush=True)
        sample_results = {}
        for word in sorted(SAMPLE_WORDS):
            text = native.lookup(word) or ""
            expected = converted["samples"].get(word, {}).get("text", "")
            sample_results[word] = {
                "native_chars": len(text),
                "matches_converted_text": normalized(text) == normalized(expected),
                "native_text": text,
            }
        negative = {word: native.lookup(word) for word in ["zzzxqvnotaword", ""]}
        lookup_seconds = time.perf_counter() - started
        if args.mdx:
            from pyglossary.plugin_lib.readmdict import MDX

            raw_keys = {key.decode("utf-8") for key in MDX(str(args.mdx)).keys()}
        elif args.mdx_index:
            with sqlite3.connect(args.mdx_index.resolve().as_uri() + "?mode=ro", uri=True) as db:
                raw_keys = {row[0] for row in db.execute("SELECT DISTINCT key_text FROM MDX_INDEX")}
        if args.mdx or args.mdx_index:
            additional_keys = raw_keys - keys
            raw_missing = [word for word in sorted(additional_keys)
                           if not (native.lookup(word) or "").strip()]
            raw_missing.extend(raw_keys.intersection(missing))
            raw_lookup = {
                "source": str((args.mdx or args.mdx_index).resolve()),
                "authoritative_mdx_keys": bool(args.mdx),
                "tested_unique_keys": len(raw_keys),
                "additional_keys_tested": len(additional_keys),
                "missing_count": len(raw_missing),
                "missing_keys": sorted(raw_missing),
            }
        if args.compare_all:
            count = 0
            misses = []
            for _, entry in ET.iterparse(args.converted, events=("end",)):
                if entry.tag != DCS_NS + "entry":
                    continue
                count += 1
                key = entry.find(DCS_NS + "index").get(DCS_NS + "value")
                expected = normalized("".join(entry.itertext()))
                if expected not in {normalized(text) for text in native.records(key)}:
                    misses.append({"key": key, "id": entry.get("id")})
                entry.clear()
            full_text = {"entries_compared": count, "unmatched_count": len(misses), "unmatched": misses}
    finally:
        native.close()
    missing_set = set(missing)
    report = {
        "source": str(args.source.resolve()),
        "converted": str(args.converted.resolve()),
        "dictionary": str(args.dictionary.resolve()),
        "dictionary_name": native.name,
        "source_stats": source,
        "converted_stats": converted,
        "missing_entry_ids": sorted(original_entries.keys() - converted_entries.keys()),
        "missing_source_keys": sorted(source_keys - keys),
        "entries_losing_definitions": sum(
            counts["definitions"] > converted_entries.get(id_, {}).get("definitions", 0)
            for id_, counts in original_entries.items()
        ),
        "entries_losing_examples": sum(
            counts["examples"] > converted_entries.get(id_, {}).get("examples", 0)
            for id_, counts in original_entries.items()
        ),
        "lookup": {
            "tested_unique_keys": len(keys),
            "missing_count": len(missing),
            "missing_keys": missing,
            "tested_headwords": len(heads),
            "missing_headwords": sorted(heads & missing_set),
            "elapsed_seconds": lookup_seconds,
            "median_ms": statistics.median(timings),
            "p95_ms": sorted(timings)[int(len(timings) * 0.95)],
            "max_ms": max(timings),
        },
        "samples": sample_results,
        "negative_controls": negative,
        "raw_mdx_lookup": raw_lookup,
        "full_text_comparison": full_text,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print(json.dumps({key: value for key, value in report["lookup"].items()
                      if key != "missing_keys"}, ensure_ascii=False, indent=2))
    print(f"Report: {args.output.resolve()}")


if __name__ == "__main__":
    main()
