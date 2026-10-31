"""Full-page screenshots of the built site, for visual review.

Usage:
    python3 scripts/screenshots.py [--base http://127.0.0.1:4321] [--out review/screenshots] [--scheme dark]

Serve the built site first, for example:
    python3 -m http.server 4321 --bind 127.0.0.1 --directory _site

Needs Chrome or Chromium; set CHROME=/path/to/browser if it is not found.
Uses only the Python standard library (Chrome DevTools Protocol over a
minimal WebSocket client). Also reports JavaScript errors, failed requests and
any request to a server other than the local one (the pages should load
nothing from third parties).
"""
import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

PAGES = ["index", "about", "research", "publications", "software", "teaching", "contact", "news", "404",
         "research/clustering", "research/oblique-trees", "research/text-mining",
         "research/heaping", "research/image-analysis"]
VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900, "deviceScaleFactor": 1, "mobile": False},
    "mobile": {"width": 390, "height": 844, "deviceScaleFactor": 2, "mobile": True},
}
CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "google-chrome", "chromium", "chromium-browser",
]


class WebSocket:
    """Just enough of RFC 6455 for a local DevTools connection."""

    def __init__(self, url):
        host_port, path = url[len("ws://"):].split("/", 1)
        host, port = host_port.split(":")
        self.sock = socket.create_connection((host, int(port)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f"GET /{path} HTTP/1.1\r\nHost: {host_port}\r\nUpgrade: websocket\r\n"
                           f"Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\n"
                           "Sec-WebSocket-Version: 13\r\n\r\n").encode())
        response = b""
        while b"\r\n\r\n" not in response:
            response += self.sock.recv(1024)
        if b" 101 " not in response.split(b"\r\n", 1)[0]:
            raise RuntimeError("WebSocket handshake failed")

    def _read(self, n):
        data = b""
        while len(data) < n:
            chunk = self.sock.recv(n - len(data))
            if not chunk:
                raise ConnectionError("connection closed")
            data += chunk
        return data

    def send(self, text):
        payload = text.encode()
        header = bytes([0x81])
        n = len(payload)
        if n < 126:
            header += bytes([0x80 | n])
        elif n < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", n)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", n)
        mask = os.urandom(4)
        self.sock.sendall(header + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def recv(self):
        message = b""
        while True:
            b1, b2 = self._read(2)
            n = b2 & 0x7F
            if n == 126:
                n = struct.unpack(">H", self._read(2))[0]
            elif n == 127:
                n = struct.unpack(">Q", self._read(8))[0]
            message += self._read(n)
            if b1 & 0x80:
                return message.decode()


class Page:
    def __init__(self, ws):
        self.ws, self.next_id, self.events = ws, 0, []

    def call(self, method, **params):
        self.next_id += 1
        self.ws.send(json.dumps({"id": self.next_id, "method": method, "params": params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == self.next_id:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})
            self.events.append(msg)

    def wait_for(self, event, timeout=30):
        end = time.time() + timeout
        while time.time() < end:
            for i, e in enumerate(self.events):
                if e.get("method") == event:
                    del self.events[i]
                    return e
            self.events.append(json.loads(self.ws.recv()))
        raise TimeoutError(event)


def find_chrome():
    for c in [os.environ.get("CHROME")] + CANDIDATES:
        if c and (os.path.exists(c) or shutil.which(c)):
            return c
    sys.exit("Chrome/Chromium not found: set CHROME=/path/to/browser")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:4321")
    ap.add_argument("--out", default="review/screenshots")
    ap.add_argument("--scheme", choices=["light", "dark"], default="light",
                    help="colour scheme preferred by the emulated browser")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    local = urllib.parse.urlsplit(args.base).netloc
    port = 9333
    profile = tempfile.mkdtemp(prefix="shots-")
    proc = subprocess.Popen([find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "--no-first-run", "--hide-scrollbars",
                             "--disable-extensions", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    problems = 0
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        page = Page(WebSocket(ws_url))
        for domain in ("Page", "Runtime", "Network", "Log"):
            page.call(f"{domain}.enable")
        for vp_name, vp in VIEWPORTS.items():
            page.call("Emulation.setDeviceMetricsOverride", **vp)
            page.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-reduced-motion", "value": "reduce"},
                                                              {"name": "prefers-color-scheme", "value": args.scheme}])
            for name in PAGES:
                url = f"{args.base}/{'' if name == 'index' else name + '.html'}"
                page.events.clear()
                page.call("Page.navigate", url=url)
                page.wait_for("Page.loadEventFired")
                page.call("Runtime.evaluate", expression="document.fonts.ready", awaitPromise=True)
                time.sleep(0.3)
                size = page.call("Page.getLayoutMetrics")["cssContentSize"]
                # Chrome cannot capture more than about 16,384 device pixels in
                # height: beyond that the image starts again from the top. Long
                # pages are captured at a reduced scale instead.
                scale = min(1, 16000 / (size["height"] * vp["deviceScaleFactor"]))
                shot = page.call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                 clip={"x": 0, "y": 0, "width": vp["width"],
                                       "height": size["height"], "scale": scale})
                suffix = "" if args.scheme == "light" else "-" + args.scheme
                path = os.path.join(args.out, f"{name.replace('/', '-')}-{vp_name}{suffix}.png")
                with open(path, "wb") as f:
                    f.write(base64.b64decode(shot["data"]))
                issues = []
                for e in page.events:
                    m, p = e.get("method"), e.get("params", {})
                    if m == "Runtime.exceptionThrown":
                        issues.append("JS exception: " + p["exceptionDetails"].get("text", ""))
                    elif m == "Log.entryAdded" and p["entry"]["level"] == "error":
                        issues.append("console error: " + p["entry"].get("text", ""))
                    elif m == "Network.loadingFailed":
                        issues.append("request failed: " + p.get("errorText", ""))
                    elif m == "Network.responseReceived" and p["response"]["status"] >= 400 and name != "404":
                        issues.append(f"HTTP {p['response']['status']}: {p['response']['url']}")
                    elif m == "Network.requestWillBeSent":
                        target = urllib.parse.urlsplit(p["request"]["url"])
                        if target.scheme in ("http", "https") and target.netloc != local:
                            issues.append("external request: " + p["request"]["url"])
                problems += len(issues)
                print(f"{vp_name:8s} {name:13s} {int(size['height']):6d}px  {path}"
                      + ("".join("\n    ! " + i for i in issues)))
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
