"""Checks the panels of the map of international activities (About page) in
Chrome, with the mouse, the keyboard and taps, in the light and dark themes.

Usage:
    python3 scripts/check_travel_map.py [--base http://127.0.0.1:4321] [--shots DIR]

Serve the built site first, as for scripts/screenshots.py. At four widths
(desktop 1280 px, tablet 768 px, phones 390 and 320 px, the last three with a
touch screen) every marker shown is opened, with the mouse or with a tap, and
its panel must:
  - be the only panel open, with the marker highlighted;
  - lie inside the map horizontally, inside the window, below the navigation
    bar, and not cover the marker;
  - point to the marker with its arrow;
  - have text with a contrast of at least 4.5:1 against its background.
Then the behaviour: with the mouse, the panel stays while the pointer moves
onto it and closes when the pointer leaves; a click keeps it open until a
click elsewhere. With the keyboard, Tab moves from marker to marker (each
opens its panel), Escape closes the panel and keeps the focus, Enter opens it
again. With taps, a tap near a marker opens it, a second tap closes it and a
tap elsewhere on the page closes it. Every marker is a button with a name and
is described by its panel. JavaScript errors and requests to other sites are
reported.

With --shots, saves screenshots of open panels in DIR (PNG).
Uses only the Python standard library and the DevTools client of
scripts/screenshots.py.
"""
import argparse
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screenshots import Page, WebSocket, find_chrome  # noqa: E402

WIDTHS = [("desktop", 1280, 900, False), ("tablet", 768, 1024, True),
          ("phone", 390, 844, True), ("small-phone", 320, 640, True)]

# Markers shown at the current width, with their panels, in document order.
MARKERS = r"""
[...document.querySelectorAll(".tm-mark")]
  .filter(m => getComputedStyle(m.parentNode).display !== "none")
  .map(m => ({ id: m.getAttribute("data-tip"), label: m.getAttribute("aria-label"),
               role: m.getAttribute("role"), tabindex: m.getAttribute("tabindex"),
               described: m.getAttribute("aria-describedby"),
               tooltip: (document.getElementById(m.getAttribute("data-tip")) || {}).getAttribute
                        && document.getElementById(m.getAttribute("data-tip")).getAttribute("role"),
               title: !!m.querySelector("title") }))
"""

# State of the panel of a marker: geometry and contrast of its text.
STATE = r"""
(id => {
  const mark = document.querySelector('.tm-mark[data-tip="' + id + '"]');
  const tip = document.getElementById(id);
  const box = r => ({ left: r.left, top: r.top, right: r.right, bottom: r.bottom });
  const m = mark.querySelector(".tm-talk, .tm-visit").getBoundingClientRect();
  const header = document.getElementById("quarto-header");
  const lum = c => {
    const v = c.match(/[\d.]+/g).slice(0, 3).map(x => {
      x /= 255;
      return x <= 0.03928 ? x / 12.92 : Math.pow((x + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * v[0] + 0.7152 * v[1] + 0.0722 * v[2];
  };
  const ratio = (a, b) => {
    const x = lum(a), y = lum(b);
    return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
  };
  const bg = getComputedStyle(tip).backgroundColor;
  const texts = [...tip.querySelectorAll("p, span")].filter(e => e.textContent.trim());
  return {
    open: [...document.querySelectorAll(".tm-tip")].filter(t => !t.hidden).map(t => t.id),
    active: mark.classList.contains("is-active"),
    ring: (c => c !== "none" && c !== "transparent" && !/,\s*0\)$/.test(c))(getComputedStyle(mark.querySelector(".tm-ring")).stroke),
    focused: document.activeElement === mark,
    tip: box(tip.getBoundingClientRect()), mark: box(m),
    stage: box(tip.parentNode.getBoundingClientRect()),
    arrow: parseFloat(tip.style.getPropertyValue("--tm-arrow")), side: tip.getAttribute("data-side"),
    width: document.documentElement.clientWidth,
    height: window.visualViewport ? visualViewport.offsetTop + visualViewport.height : innerHeight,
    header: header ? Math.max(0, header.getBoundingClientRect().bottom) : 0,
    contrast: Math.min(...texts.map(e => ratio(getComputedStyle(e).color, bg))),
    text: tip.innerText,
  };
})
"""


def evaluate(page, expression):
    r = page.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in r:
        raise RuntimeError(r["exceptionDetails"].get("text", "") + " " + expression[:80])
    return r["result"].get("value")


def centre(page, mid, scroll=True):
    """Scrolls the marker to the middle of the window; its centre in the window."""
    if scroll:
        evaluate(page, f'document.querySelector(\'.tm-mark[data-tip="{mid}"]\').scrollIntoView({{block: "center"}})')
        time.sleep(0.05)
    r = evaluate(page, f'(r => [r.left + r.width / 2, r.top + r.height / 2, r.width])(document.querySelector'
                       f'(\'.tm-mark[data-tip="{mid}"]\').querySelector(".tm-talk, .tm-visit").getBoundingClientRect())')
    return r[0], r[1], r[2]


def mouse(page, kind, x, y):
    params = {"type": kind, "x": x, "y": y}
    if kind != "mouseMoved":
        params.update(button="left", clickCount=1)
    page.call("Input.dispatchMouseEvent", **params)


def click(page, x, y):
    mouse(page, "mouseMoved", x, y)
    mouse(page, "mousePressed", x, y)
    mouse(page, "mouseReleased", x, y)


def key(page, name):
    codes = {"Tab": 9, "Enter": 13, "Escape": 27}
    for kind in ("keyDown", "keyUp"):
        page.call("Input.dispatchKeyEvent", type=kind, key=name, code=name, windowsVirtualKeyCode=codes[name],
                  **({"text": "\r"} if name == "Enter" and kind == "keyDown" else {}))
    time.sleep(0.05)


def tap(page, x, y):
    # Two taps in quick succession would count as a double tap (zoom).
    page.call("Input.synthesizeTapGesture", x=x, y=y, gestureSourceType="touch")
    time.sleep(0.4)
    settle(page)


def settle(page, timeout=2):
    """Waits until the page stops scrolling (a tap may scroll it to show a
    panel; some versions of Chrome take a while)."""
    last, end = None, time.time() + timeout
    while time.time() < end:
        y = evaluate(page, "scrollY")
        if y == last:
            return
        last = y
        time.sleep(0.1)


def outside(page):
    """A point of the page outside the maps: the note under them."""
    evaluate(page, 'document.querySelector(".travel-map .chart-note").scrollIntoView({block: "center"})')
    r = evaluate(page, '(r => [r.left + 20, r.top + r.height / 2])'
                       '(document.querySelector(".travel-map .chart-note").getBoundingClientRect())')
    return r[0], r[1]


def placement(s, mid):
    """Problems with the placement of an open panel (s = STATE)."""
    out = []
    t, m, st = s["tip"], s["mark"], s["stage"]
    if s["open"] != [mid]:
        return [f"open panels {s['open']} instead of {mid}"]
    if not s["active"] or not s["ring"]:
        out.append("marker not highlighted")
    # Inside the map, unless the panel is wider than the map allows (phones):
    # then inside the window.
    if (t["right"] - t["left"] <= st["right"] - st["left"] - 12
            and (t["left"] < st["left"] + 5 or t["right"] > st["right"] - 5)):
        out.append(f"outside the map horizontally ({t['left']:.0f}-{t['right']:.0f} in {st['left']:.0f}-{st['right']:.0f})")
    if t["left"] < 0 or t["right"] > s["width"] or t["top"] < s["header"] or t["bottom"] > s["height"]:
        out.append(f"outside the window ({t['top']:.0f}-{t['bottom']:.0f} for {s['header']:.0f}-{s['height']})")
    if t["left"] < m["right"] and m["left"] < t["right"] and t["top"] < m["bottom"] and m["top"] < t["bottom"]:
        out.append("covers the marker")
    if s["side"] in ("above", "below"):
        here, there, size = t["left"] + s["arrow"], (m["left"] + m["right"]) / 2, t["right"] - t["left"]
    else:
        here, there, size = t["top"] + s["arrow"], (m["top"] + m["bottom"]) / 2, t["bottom"] - t["top"]
    if abs(here - there) > 1.5 and 15 < s["arrow"] < size - 15:
        out.append(f"arrow at {here:.0f}, marker at {there:.0f} ({s['side']})")
    if s["contrast"] < 4.5:
        out.append(f"contrast {s['contrast']:.2f}")
    return out


def shot(page, path, mid):
    """Screenshot of the map and of the open panel of a marker."""
    s = evaluate(page, STATE + f'("{mid}")')
    top = max(0, min(s["tip"]["top"], s["stage"]["top"]) - 12)
    bottom = min(s["height"], max(s["tip"]["bottom"], s["stage"]["bottom"]) + 12)
    y = evaluate(page, "scrollY")
    data = page.call("Page.captureScreenshot", format="png",
                     clip={"x": 0, "y": y + top, "width": s["width"], "height": bottom - top, "scale": 1})
    with open(path, "wb") as f:
        f.write(base64.b64decode(data["data"]))


def new_page(port):
    """A new tab, so that each device starts from a clean state: switching the
    emulation of the same tab from mouse to touch confuses some versions of
    Chrome."""
    request = urllib.request.Request(f"http://127.0.0.1:{port}/json/new?about:blank", method="PUT")
    target = json.load(urllib.request.urlopen(request))
    page = Page(WebSocket(target["webSocketDebuggerUrl"]))
    for domain in ("Page", "Runtime", "Network"):
        page.call(f"{domain}.enable")
    return page, target["id"]


def run(port, base, scheme, shots):
    problems = []
    for name, width, height, touch in WIDTHS:
        page, tab = new_page(port)
        page.call("Emulation.setDeviceMetricsOverride", width=width, height=height, deviceScaleFactor=2 if touch else 1,
                  mobile=touch)
        page.call("Emulation.setTouchEmulationEnabled", enabled=touch, maxTouchPoints=5 if touch else 1)
        page.call("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme", "value": scheme},
                                                          {"name": "prefers-reduced-motion", "value": "reduce"}])
        page.events.clear()
        page.call("Page.navigate", url=base + "/about.html")
        page.wait_for("Page.loadEventFired")
        evaluate(page, "document.fonts.ready")
        where = f"{scheme} {name}"
        marks = evaluate(page, MARKERS)
        bad = [m["id"] for m in marks if m["role"] != "button" or m["tabindex"] != "0" or not m["label"]
               or m["described"] != m["id"] or m["tooltip"] != "tooltip" or m["title"]]
        if len(marks) not in (19, 13) or bad:  # 6 + 13 markers on wide maps, 5 + 8 on narrow ones
            problems.append(f"{where}: {len(marks)} markers; not buttons described by their panel: {bad}")
        # The markers of the hidden layer must not be buttons or reachable
        # with Tab (some browsers let hidden SVG elements take the focus).
        hidden = evaluate(page, '[...document.querySelectorAll(".tm-mark")]'
                                '.filter(m => getComputedStyle(m.parentNode).display === "none")'
                                '.filter(m => m.hasAttribute("tabindex") || m.hasAttribute("role")'
                                ' || m.getAttribute("aria-hidden") !== "true").map(m => m.getAttribute("data-tip"))')
        if hidden:
            problems.append(f"{where}: markers of the hidden layer are still buttons: {hidden}")
        if evaluate(page, '[...document.querySelectorAll(".tm-tip")].some(t => !t.hidden)'):
            problems.append(f"{where}: a panel is open before any action")
        if evaluate(page, 'document.querySelector(".travel-map .tm-hint").hidden'):
            problems.append(f"{where}: the hint is not shown")
        for m in marks:
            mid = m["id"]
            x, y, size = centre(page, mid)
            if touch:
                tap(page, x, y)
            else:
                mouse(page, "mouseMoved", x, y)
                time.sleep(0.05)
            s = evaluate(page, STATE + f'("{mid}")')
            problems += [f"{where} {mid}: {p}" for p in placement(s, mid)]
            if touch:
                # The page may have scrolled to show the panel: tap the marker
                # where it is now.
                x, y, _ = centre(page, mid, scroll=False)
                tap(page, x, y)
                if evaluate(page, f'!document.getElementById("{mid}").hidden'):
                    problems.append(f"{where} {mid}: a second tap does not close the panel")
            else:
                ox, oy = outside(page)
                mouse(page, "mouseMoved", ox, oy)
                time.sleep(0.4)
                if evaluate(page, f'!document.getElementById("{mid}").hidden'):
                    problems.append(f"{where} {mid}: the panel stays open after the pointer leaves")
        first, last = marks[0]["id"], marks[-1]["id"]
        if touch:
            # A tap a little away from the marker, on the side away from its
            # nearest neighbour, still opens it; a tap elsewhere closes it.
            for m in marks:
                x, y, size = centre(page, m["id"])
                others = [centre(page, o["id"], scroll=False) for o in marks if o["id"] != m["id"]]
                nx, ny, _ = min(others, key=lambda o: (o[0] - x) ** 2 + (o[1] - y) ** 2)
                d = max(1e-6, ((nx - x) ** 2 + (ny - y) ** 2) ** 0.5)
                step = min(size / 2 + 8, d / 2 - 2)
                tap(page, x - (nx - x) / d * step, y - (ny - y) / d * step)
                opened = evaluate(page, '[...document.querySelectorAll(".tm-tip")].filter(t => !t.hidden).map(t => t.id)')
                if opened != [m["id"]]:
                    problems.append(f"{where} {m['id']}: a tap {step:.0f} px from the marker opens {opened}")
                ox, oy = outside(page)
                tap(page, ox, oy)
                if evaluate(page, '[...document.querySelectorAll(".tm-tip")].some(t => !t.hidden)'):
                    problems.append(f"{where} {m['id']}: a tap elsewhere does not close the panel")
        else:
            # Hover, then move onto the panel: it stays; leave it: it closes.
            x, y, _ = centre(page, last)
            mouse(page, "mouseMoved", x, y)
            s = evaluate(page, STATE + f'("{last}")')
            tx = (s["tip"]["left"] + s["tip"]["right"]) / 2
            ty = s["tip"]["top"] + 8 if s["tip"]["top"] > s["mark"]["bottom"] else s["tip"]["bottom"] - 8
            for k in range(1, 6):
                mouse(page, "mouseMoved", x + (tx - x) * k / 5, y + (ty - y) * k / 5)
                time.sleep(0.03)
            time.sleep(0.4)
            if evaluate(page, f'document.getElementById("{last}").hidden'):
                problems.append(f"{where}: the panel closes when the pointer moves onto it")
            ox, oy = outside(page)
            mouse(page, "mouseMoved", ox, oy)
            time.sleep(0.4)
            if evaluate(page, f'!document.getElementById("{last}").hidden'):
                problems.append(f"{where}: the panel stays open after the pointer leaves it")
            # A click keeps the panel open; a click elsewhere closes it.
            x, y, _ = centre(page, first)
            click(page, x, y)
            ox, oy = outside(page)
            mouse(page, "mouseMoved", ox, oy)
            time.sleep(0.4)
            if evaluate(page, f'document.getElementById("{first}").hidden'):
                problems.append(f"{where}: a click does not keep the panel open")
            click(page, ox, oy)
            if evaluate(page, '[...document.querySelectorAll(".tm-tip")].some(t => !t.hidden)'):
                problems.append(f"{where}: a click elsewhere does not close the panel")
            # Keyboard: Tab from marker to marker; on the last one, whose panel
            # the focus has opened, Enter keeps it open and a second Enter
            # closes it; Enter opens it again and Escape closes it.
            evaluate(page, f'document.querySelector(\'.tm-mark[data-tip="{first}"]\').focus()')
            for i, m in enumerate(marks):
                if i:
                    key(page, "Tab")
                s = evaluate(page, STATE + f'("{m["id"]}")')
                if not s["focused"]:
                    problems.append(f"{where}: Tab does not reach {m['id']}")
                    break
                problems += [f"{where} {m['id']} (keyboard): {p}" for p in placement(s, m["id"])]
            panel_open = f'!document.getElementById("{last}").hidden'
            key(page, "Enter")
            if not evaluate(page, panel_open):
                problems.append(f"{where}: Enter closes the panel opened by the focus")
            key(page, "Enter")
            if evaluate(page, panel_open):
                problems.append(f"{where}: a second Enter does not close the panel")
            key(page, "Enter")
            if not evaluate(page, panel_open):
                problems.append(f"{where}: Enter does not open the panel")
            key(page, "Escape")
            s = evaluate(page, STATE + f'("{last}")')
            if s["open"] or not s["focused"] or not s["ring"]:
                problems.append(f"{where}: Escape does not close the panel, or the focus is lost or not shown")
        if shots:
            os.makedirs(shots, exist_ok=True)
            evaluate(page, "document.activeElement && document.activeElement.blur()")
            # Panels with several places and activities, and markers near the edges.
            names = {m["label"].split(":")[0]: m["id"] for m in marks}
            for label in names:
                if any(k in label for k in ("Naples", "Prague", "Auckland", "Kuala Lumpur")):
                    mid = names[label]
                    x, y, _ = centre(page, mid)
                    if touch:
                        tap(page, x, y)
                    else:
                        mouse(page, "mouseMoved", x, y)
                        time.sleep(0.05)
                    city = label.split(",")[0].lower().replace(" ", "-")
                    shot(page, os.path.join(shots, f"map-{city}-{name}-{scheme}.png"), mid)
                    if touch:
                        x, y, _ = centre(page, mid, scroll=False)
                        tap(page, x, y)
                    else:
                        ox, oy = outside(page)
                        mouse(page, "mouseMoved", ox, oy)
                        time.sleep(0.4)
        for e in page.events:
            method, p = e.get("method"), e.get("params", {})
            if method == "Runtime.exceptionThrown":
                problems.append(f"{where}: JavaScript error: " + p["exceptionDetails"].get("text", ""))
            elif method == "Network.requestWillBeSent":
                target = urllib.parse.urlsplit(p["request"]["url"])
                if target.scheme in ("http", "https") and target.netloc != urllib.parse.urlsplit(base).netloc:
                    problems.append(f"{where}: request to another site: " + p["request"]["url"])
        print(f"{where:20s} {len(marks):2d} markers checked")
        urllib.request.urlopen(f"http://127.0.0.1:{port}/json/close/{tab}")
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:4321")
    ap.add_argument("--shots", metavar="DIR", help="save screenshots of open panels")
    args = ap.parse_args()
    port = 9334
    profile = tempfile.mkdtemp(prefix="map-")
    proc = subprocess.Popen([find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "--no-first-run", "--hide-scrollbars",
                             "--disable-extensions", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        for _ in range(50):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version")
                break
            except Exception:
                time.sleep(0.2)
        problems = []
        for scheme in ("light", "dark"):
            problems += run(port, args.base.rstrip("/"), scheme, args.shots)
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    for p in problems:
        print("  ! " + p)
    print(f"\n{len(problems)} problem(s) found.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
