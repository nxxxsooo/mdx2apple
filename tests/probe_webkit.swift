// Headless rendering/media probe for HTML returned by DictionaryServices.
// swift tests/probe_webkit.swift entry.html output-prefix resource-root [dark|light]
//   [--skip-media] [--width=480] [--height=900] [--font-size=20]
import AppKit
import WebKit

let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
if CommandLine.arguments.contains("dark") {
    app.appearance = NSAppearance(named: .darkAqua)
} else if CommandLine.arguments.contains("light") {
    app.appearance = NSAppearance(named: .aqua)
}
let input = URL(fileURLWithPath: CommandLine.arguments[1]).standardizedFileURL
let output = URL(fileURLWithPath: CommandLine.arguments[2]).standardizedFileURL
let access = URL(fileURLWithPath: CommandLine.arguments[3]).standardizedFileURL
func numericOption(_ name: String, default value: Double) -> Double {
    guard let argument = CommandLine.arguments.first(where: { $0.hasPrefix(name + "=") }) else { return value }
    guard let number = Double(argument.dropFirst(name.count + 1)), number.isFinite, number > 0 else {
        fputs("Invalid \(name)\n", stderr); exit(1)
    }
    return number
}
let viewportWidth = numericOption("--width", default: 1100)
let viewportHeight = numericOption("--height", default: 900)
let fontSize = numericOption("--font-size", default: 16)
let config = WKWebViewConfiguration()
config.websiteDataStore = .nonPersistent()
config.mediaTypesRequiringUserActionForPlayback = []
let view = WKWebView(frame: NSRect(x: 0, y: 0, width: viewportWidth, height: viewportHeight), configuration: config)
var panel: NSPanel?
if CommandLine.arguments.contains("--secondary-display") {
    guard let screen = NSScreen.screens.dropFirst().first else {
        fputs("No secondary display; refusing to show a probe on the primary display\n", stderr)
        exit(1)
    }
    app.setActivationPolicy(.accessory)
    let frame = NSRect(x: screen.visibleFrame.minX + 40, y: screen.visibleFrame.minY + 40,
                       width: min(viewportWidth, screen.visibleFrame.width - 80),
                       height: min(viewportHeight, screen.visibleFrame.height - 80))
    panel = NSPanel(contentRect: frame, styleMask: [.titled, .nonactivatingPanel], backing: .buffered, defer: false)
    panel!.title = "Dictionary rendering test"
    panel!.contentView = view
    panel!.setFrame(frame, display: false)
    panel!.orderFrontRegardless()
}

class Probe: NSObject, WKNavigationDelegate {
    func webView(_ webView: WKWebView, didFinish navigation: WKNavigation!) {
        webView.callAsyncJavaScript("""
        document.documentElement.style.fontSize = fontSize + 'px';
        await document.fonts.ready;
        const results = [];
        for (const audio of (testMedia ? Array.from(document.querySelectorAll('audio')).slice(0, 2) : [])) {
          audio.muted = true;
          audio.load();
          const result = {src: audio.getAttribute('src'), label: audio.getAttribute('aria-label')};
          try {
            await Promise.race([
              audio.play(),
              new Promise((_, reject) => setTimeout(() => reject(new Error('media timeout')), 6000))
            ]);
            await new Promise(resolve => setTimeout(resolve, 150));
            result.duration = audio.duration;
            result.currentTime = audio.currentTime;
            result.played = audio.currentTime > 0;
            audio.pause();
            audio.currentTime = 0;
          } catch (error) { result.error = String(error); }
          result.readyState = audio.readyState;
          result.networkState = audio.networkState;
          result.mediaError = audio.error ? audio.error.code : null;
          results.push(result);
        }
        const picture = document.querySelector('details.mdx-picture');
        let expansion = null;
        if (picture) {
          const closed = picture.getBoundingClientRect().height;
          picture.open = true;
          const opened = picture.getBoundingClientRect().height;
          expansion = {closed, opened, expanded: opened > closed};
          picture.open = false;
        }
        // Inspect actual rendered text, including source CSS and nested boxes.
        function rgba(value) {
          const parts = value.match(/[0-9.]+/g)?.map(Number) || [0, 0, 0, 0];
          return [parts[0], parts[1], parts[2], parts.length > 3 ? parts[3] : 1];
        }
        function luminance(rgb) {
          const linear = rgb.slice(0, 3).map(v => {
            v /= 255;
            return v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
          });
          return linear[0] * 0.2126 + linear[1] * 0.7152 + linear[2] * 0.0722;
        }
        function background(element) {
          const layers = [];
          for (let e = element; e; e = e.parentElement) layers.unshift(rgba(getComputedStyle(e).backgroundColor));
          return layers.reduce((rgb, layer) => rgb.map((v, i) => layer[i] * layer[3] + v * (1 - layer[3])), [255, 255, 255]);
        }
        const failures = [];
        const clippedText = [];
        let measured = 0, minimumContrast = Infinity;
        const walker = document.createTreeWalker(document.querySelector('.mdx-entry') || document.body, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) {
          const node = walker.currentNode;
          if (!node.textContent.trim()) continue;
          const element = node.parentElement;
          if (!element || element.closest('script, style, audio')) continue;
          const style = getComputedStyle(element);
          if (style.visibility !== 'visible' || style.opacity === '0') continue;
          const range = document.createRange();
          range.selectNode(node);
          const rects = Array.from(range.getClientRects()).filter(r => r.width && r.height);
          if (!rects.length) continue;
          if (rects.some(r => r.left < -1 || r.right > document.documentElement.clientWidth + 1)) {
            clippedText.push(node.textContent.trim().slice(0, 60));
          }
          const paint = style.webkitTextFillColor || style.color;
          const bg = background(element), fg = rgba(paint);
          const color = fg.slice(0, 3).map((v, i) => v * fg[3] + bg[i] * (1 - fg[3]));
          const a = luminance(color), b = luminance(bg);
          const ratio = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
          const large = parseFloat(style.fontSize) >= 24 || (parseFloat(style.fontSize) >= 18.66 && parseInt(style.fontWeight) >= 700);
          measured++;
          minimumContrast = Math.min(minimumContrast, ratio);
          if (ratio < (large ? 3 : 4.5)) failures.push({text: node.textContent.trim().slice(0, 60), color: paint, background: bg, ratio});
        }
        return JSON.stringify({
          text: document.body.innerText,
          dark: matchMedia('(prefers-color-scheme: dark)').matches,
          visibility: document.visibilityState,
          viewportWidth: document.documentElement.clientWidth,
          width: document.documentElement.scrollWidth,
          height: document.documentElement.scrollHeight,
          clippedText,
          images: Array.from(document.images, i => ({src: i.getAttribute('src'), width: i.naturalWidth, height: i.naturalHeight})),
          definitions: document.querySelectorAll('.def').length,
          visibleDefinitions: Array.from(document.querySelectorAll('.def')).filter(e => e.getBoundingClientRect().height > 0).length,
          examples: document.querySelectorAll('.x, .unx').length,
          visibleExamples: Array.from(document.querySelectorAll('.x, .unx')).filter(e => e.getBoundingClientRect().height > 0).length,
          links: document.querySelectorAll('a[href]').length,
          audioCount: document.querySelectorAll('audio').length,
          audio: results,
          expansion,
          typography: Object.fromEntries(['.mdx-entry', '.headword', '.phon', '.def', '.examples .x', '.examples chn', '.box_title'].map(selector => {
            const element = document.querySelector(selector);
            if (!element) return [selector, null];
            const style = getComputedStyle(element);
            return [selector, {family: style.fontFamily, size: style.fontSize, weight: style.fontWeight, lineHeight: style.lineHeight}];
          })),
          contrast: {measured, minimum: minimumContrast, failureCount: failures.length, failures: failures.slice(0, 30)}
        });
        """, arguments: ["testMedia": !CommandLine.arguments.contains("--skip-media"), "fontSize": fontSize], in: nil, in: .page) { result in
            switch result {
            case .failure(let error):
                fputs("Probe error: \(error)\n", stderr); exit(1)
            case .success(let value):
                do {
                    try (value as! String).write(to: output.appendingPathExtension("json"), atomically: true, encoding: .utf8)
                } catch { fputs("Write error: \(error)\n", stderr); exit(1) }
                let snapshot = WKSnapshotConfiguration()
                snapshot.rect = webView.bounds
                webView.takeSnapshot(with: snapshot) { image, error in
                    if let error { fputs("Snapshot error: \(error)\n", stderr); exit(1) }
                    do {
                        let rep = NSBitmapImageRep(data: image!.tiffRepresentation!)!
                        try rep.representation(using: .png, properties: [:])!.write(to: output.appendingPathExtension("png"))
                        print("Rendered \(input.lastPathComponent) -> \(output.path)")
                        exit(0)
                    } catch { fputs("Image error: \(error)\n", stderr); exit(1) }
                }
            }
        }
    }
    func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: Error) {
        fputs("Navigation error: \(error)\n", stderr); exit(1)
    }
}

let probe = Probe()
view.navigationDelegate = probe
view.loadFileURL(input, allowingReadAccessTo: access)
DispatchQueue.main.asyncAfter(deadline: .now() + 25) { fputs("Timed out\n", stderr); exit(1) }
app.run()
