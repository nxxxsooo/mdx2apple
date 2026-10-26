// Read actual glyph fonts from the open Dictionary.app's Accessibility tree.
// Requires macOS Accessibility permission. Does not launch, focus or edit the app.
// swift tests/probe_dictionary_fonts.swift > output/native-fonts.json
import AppKit
import ApplicationServices

guard AXIsProcessTrusted(),
      let app = NSRunningApplication.runningApplications(withBundleIdentifier: "com.apple.Dictionary").first else {
    fputs("Dictionary.app or Accessibility access unavailable\n", stderr)
    exit(1)
}
func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success else { return nil }
    return value
}
func parameterized(_ element: AXUIElement, _ name: String, _ parameter: CFTypeRef) -> CFTypeRef? {
    var value: CFTypeRef?
    guard AXUIElementCopyParameterizedAttributeValue(element, name as CFString, parameter, &value) == .success else { return nil }
    return value
}
let application = AXUIElementCreateApplication(app.processIdentifier)
var visited = 0
var samples: [[String: Any]] = []
func inspect(_ element: AXUIElement, depth: Int, inWeb: Bool = false) {
    guard depth < 30, visited < 2000 else { return }
    visited += 1
    let role = attribute(element, kAXRoleAttribute) as? String ?? ""
    let inWeb = inWeb || role == "AXWebArea"
    let value = attribute(element, kAXValueAttribute) as? String ?? ""
    if inWeb && role == "AXStaticText" && !value.isEmpty && value != "•" {
        if let range = parameterized(element, "AXTextMarkerRangeForUIElement", element),
           let attributed = parameterized(element, "AXAttributedStringForTextMarkerRange", range) as? NSAttributedString {
            var runs: [[String: Any]] = []
            attributed.enumerateAttributes(in: NSRange(location: 0, length: attributed.length)) { attributes, range, _ in
                let font = attributes[NSAttributedString.Key("AXFont")] as? [String: Any] ?? [:]
                runs.append(["text": (attributed.string as NSString).substring(with: range), "font": font])
            }
            samples.append(["text": value, "runs": runs])
        }
    }
    for child in attribute(element, kAXChildrenAttribute) as? [AXUIElement] ?? [] {
        inspect(child, depth: depth + 1, inWeb: inWeb)
    }
}
inspect(application, depth: 0)
guard !samples.isEmpty else {
    fputs("No native web-content font samples available\n", stderr)
    exit(1)
}
let data = try JSONSerialization.data(withJSONObject: ["pid": app.processIdentifier, "samples": samples, "truncated": visited >= 2000], options: [.prettyPrinted, .sortedKeys])
FileHandle.standardOutput.write(data)
print()
