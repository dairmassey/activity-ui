import AppKit
import WebKit

// Renders a page in real WebKit (the Safari engine) and saves a PNG.
// usage: webkit_shot <page url> <output png> <width> <height> <delay seconds>
let args = CommandLine.arguments
let app = NSApplication.shared
app.setActivationPolicy(.prohibited)
let w = Double(args[3])!, h = Double(args[4])!, delay = Double(args[5])!

final class Nav: NSObject, WKNavigationDelegate {
    func webView(_ v: WKWebView, didFinish n: WKNavigation!) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) {
            v.takeSnapshot(with: nil) { image, error in
                guard let image = image, let tiff = image.tiffRepresentation,
                      let rep = NSBitmapImageRep(data: tiff),
                      let png = rep.representation(using: .png, properties: [:]) else {
                    print("snapshot failed", error as Any); exit(1)
                }
                try! png.write(to: URL(fileURLWithPath: args[2]))
                print("ok", args[2]); exit(0)
            }
        }
    }
}

let cfg = WKWebViewConfiguration()
cfg.preferences.setValue(true, forKey: "allowFileAccessFromFileURLs")
let view = WKWebView(frame: NSRect(x: 0, y: 0, width: w, height: h), configuration: cfg)
let window = NSWindow(contentRect: view.frame, styleMask: [.borderless], backing: .buffered, defer: false)
window.contentView = view
window.orderBack(nil)
let nav = Nav()
view.navigationDelegate = nav
let url = URL(string: args[1])!
view.loadFileURL(url, allowingReadAccessTo: URL(fileURLWithPath: "/"))
DispatchQueue.main.asyncAfter(deadline: .now() + 20) { print("timeout"); exit(2) }
app.run()
