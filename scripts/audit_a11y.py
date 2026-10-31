"""Automated accessibility checks of the built site in Chrome (WCAG 2.2 AA).

Usage:
    python3 scripts/audit_a11y.py [--base http://127.0.0.1:4321] [--page about]
                                  [--axe path/to/axe.min.js]

Serve the built site first, as for scripts/screenshots.py. Every page is
loaded with all <details> open and the mobile menu expanded, in these modes:

    desktop        1280 px wide, light and dark theme
    mobile         320 px wide, light and dark theme
    zoom-200       640 px wide: the layout of 1280 px at 200 % browser zoom
    text-200       1280 px wide with the text size doubled

and checked for: contrast of text (also in SVG charts) and of links within
text; accessible names (from Chrome's accessibility tree); one h1 and no
skipped heading levels; duplicate ids; images without alt; language of the
page; horizontal scrolling of the page (reflow) and clipped text; size of
small targets (2.5.8). On desktop the page is also crossed with the Tab key:
every focused element must show a visible change and must not be hidden
under other content. The theme switch is checked once, with the mouse and
with the keyboard.

With --axe, axe-core also runs on every page in every mode, with its rules
for WCAG 2.0, 2.1 and 2.2 (levels A and AA) and its best practices. axe-core
is not included: take axe.min.js from the axe-core package on npm
(https://www.npmjs.com/package/axe-core, MPL-2.0 license). WCAG violations
count as issues; best practices and the results that axe cannot decide by
itself ("needs review") are listed apart and do not fail the audit. The
exception is the contrast of text that axe cannot decide (text in SVG charts,
very short text, text partly hidden in a scrolling table): it is measured on
the rendered page, from two screenshots with and without the text. The pixels
that change and are at least half covered by a letter are the letters, and the
screenshot without the text gives the background under each of them; 98% of
those pixels must reach 4.5:1, or 3:1 for large text.

Uses only the Python standard library and the DevTools client of
scripts/screenshots.py. Neither these checks nor axe replace a test with a
screen reader.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from screenshots import PAGES, Page, WebSocket, find_chrome  # noqa: E402

MODES = [
    ("desktop", 1280, 800, 1, False, "light"),
    ("desktop", 1280, 800, 1, False, "dark"),
    ("mobile", 320, 640, 2, True, "light"),
    ("mobile", 320, 640, 2, True, "dark"),
    ("zoom-200", 640, 800, 2, False, "light"),
    ("text-200", 1280, 800, 1, False, "light"),
]
NAMED_ROLES = {"link", "button", "image", "img", "checkbox", "textbox", "combobox", "switch",
               "tab", "menuitem", "searchbox", "radio", "listbox", "slider", "spinbutton"}

# Runs in the page; returns a list of [rule, element, detail].
CHECKS_JS = r"""
(() => {
  const out = [];
  const add = (rule, el, detail) => out.push([rule, describe(el), detail || ""]);
  function describe(el) {
    if (!el || !el.tagName) return "";
    let s = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "");
    const cls = (el.getAttribute("class") || "").trim().split(/\s+/).filter(Boolean).slice(0, 2);
    if (cls.length) s += "." + cls.join(".");
    const t = (el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 50);
    return t ? s + ' "' + t + '"' : s;
  }
  function parse(c) {
    let m = c && c.match(/^rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    m = c && c.match(/^color\(srgb ([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s\/]+/).filter(Boolean).map(parseFloat);
      return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1];
    }
    return null;
  }
  const over = (top, bottom) => [0, 1, 2].map(i => top[i] * top[3] + bottom[i] * (1 - top[3])).concat([1]);
  function lum(c) {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  }
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  // Background behind an element: its own and its ancestors' backgrounds,
  // composed; null when an image or a gradient is involved.
  function background(el) {
    const layers = [];
    for (let e = el; e; e = e.parentElement) {
      const cs = getComputedStyle(e);
      if (cs.backgroundImage && cs.backgroundImage !== "none") return null;
      const c = parse(cs.backgroundColor);
      if (c && c[3] > 0) { layers.push(c); if (c[3] >= 1) break; }
    }
    let base = [255, 255, 255, 1];
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  }
  // Background of SVG text: the shapes painted under the middle of the text
  // (from document.elementsFromPoint), over the page background.
  function svgBackground(el) {
    let base = background(el);
    if (!base) return null;
    el.scrollIntoView({ block: "center", inline: "center" });
    const r = el.getBoundingClientRect();
    const stack = document.elementsFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const layers = [];
    for (const e of stack.slice(stack.indexOf(el) + 1)) {
      if (!(e instanceof SVGElement) || e.tagName === "svg") break;
      if (!/^(rect|circle|ellipse|path|polygon)$/.test(e.tagName)) continue;
      const cs = getComputedStyle(e), c = parse(cs.fill);
      if (!c) continue;
      const a = c[3] * parseFloat(cs.fillOpacity) * opacity(e);
      if (a > 0) { layers.push([c[0], c[1], c[2], a]); if (a >= 1) break; }
    }
    for (let i = layers.length - 1; i >= 0; i--) base = over(layers[i], base);
    return base;
  }
  function opacity(el) {
    let o = 1;
    for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity);
    return o;
  }
  function shown(el) {
    const cs = getComputedStyle(el);
    if (cs.display === "none" || cs.visibility === "hidden") return false;
    const r = el.getBoundingClientRect();
    return r.width > 1 && r.height > 1;
  }

  // Text contrast (1.4.3), also for SVG text, whose colour is its fill.
  const seen = new Set();
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let unknown = 0;
  while (walker.nextNode()) {
    const el = walker.currentNode.parentElement;
    if (!walker.currentNode.nodeValue.trim() || !el || seen.has(el)) continue;
    seen.add(el);
    if (el.closest("script, style, noscript, template, title, desc") || !shown(el)) continue;
    const op = opacity(el);
    if (op === 0) continue;
    const cs = getComputedStyle(el);
    const svg = el instanceof SVGElement;
    let fg = parse(svg ? cs.fill : cs.color);
    const bg = svg ? svgBackground(el) : background(el);
    if (!fg) continue;
    if (!bg) { unknown++; continue; }
    fg = over([fg[0], fg[1], fg[2], fg[3] * op], bg);
    let px = parseFloat(cs.fontSize);
    if (svg && el.getScreenCTM) px *= el.getScreenCTM().a;
    const large = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
    const r = ratio(fg, bg);
    if (r < (large ? 3 : 4.5)) add("contrast", el, r.toFixed(2) + ":1 at " + px.toFixed(1) + "px");
  }
  if (unknown) add("contrast-unknown", document.body, unknown + " text elements on images or gradients");

  // Links inside text must be underlined or differ from the text by 3:1 (1.4.1).
  document.querySelectorAll("p a[href], li a[href], dd a[href], td a[href]").forEach(a => {
    if (!shown(a)) return;
    const parent = a.parentElement;
    const own = (a.textContent || "").trim().length;
    const all = (parent.textContent || "").trim().length;
    if (all <= own + 2) return;
    if ([a, ...a.querySelectorAll("*")].some(e => getComputedStyle(e).textDecorationLine.includes("underline"))) return;
    const fa = parse(getComputedStyle(a).color), fp = parse(getComputedStyle(parent).color);
    if (fa && fp && ratio(fa, fp) < 3) add("link-in-text", a, "not underlined, " + ratio(fa, fp).toFixed(2) + ":1 to the text");
  });

  // Headings: one h1, no skipped levels.
  const hs = [...document.querySelectorAll("h1, h2, h3, h4, h5, h6")].filter(shown);
  const h1 = hs.filter(h => h.tagName === "H1").length;
  if (h1 !== 1) add("h1", document.body, h1 + " h1 elements");
  let prev = 0;
  hs.forEach(h => {
    const level = +h.tagName[1];
    if (prev && level > prev + 1) add("heading-skip", h, "h" + prev + " then h" + level);
    prev = level;
  });

  // Duplicate ids (in the body: Quarto repeats the ids of the light and dark
  // style sheets in the head), images, language.
  const ids = {};
  document.body.querySelectorAll("[id]").forEach(e => { ids[e.id] = (ids[e.id] || 0) + 1; });
  Object.keys(ids).filter(k => ids[k] > 1).forEach(k => add("duplicate-id", document.getElementById(k), k));
  document.querySelectorAll("img:not([alt])").forEach(i => add("img-alt", i));
  if (!document.documentElement.lang) add("lang", document.documentElement);

  // Reflow (1.4.10): no horizontal scrolling of the page; clipped text.
  const vw = document.documentElement.clientWidth;
  if (document.documentElement.scrollWidth > vw + 1) {
    const wide = [...document.body.querySelectorAll("*")].filter(e => {
      const r = e.getBoundingClientRect();
      if (r.right <= vw + 1 || !shown(e)) return false;
      for (let p = e.parentElement; p; p = p.parentElement) {
        if (/(auto|scroll|hidden|clip)/.test(getComputedStyle(p).overflowX) && p.getBoundingClientRect().right <= vw + 1) return false;
      }
      return true;
    });
    add("reflow", wide[0] || document.body, "page " + document.documentElement.scrollWidth + "px wide for " + vw + "px");
  }
  document.querySelectorAll("body *").forEach(e => {
    const cs = getComputedStyle(e);
    if (!/(hidden|clip)/.test(cs.overflowX + cs.overflowY) || !shown(e) || !(e.textContent || "").trim()) return;
    if (e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1) {
      // An ellipsis shows the cut, but it is drawn only in a block container:
      // in a flex or grid container the text is cut without one.
      if (cs.textOverflow === "ellipsis" && !/flex|grid/.test(cs.display)) return;
      add("clipped", e, e.scrollWidth + "x" + e.scrollHeight + " in " + e.clientWidth + "x" + e.clientHeight);
    }
  });

  // Target size (2.5.8): 24 x 24 px, or enough space around; links in text are exempt.
  const targets = [...document.querySelectorAll("a[href], button, summary, [role=button], input, select, [tabindex='0']")]
    .filter(shown).map(e => ({ e, r: e.getBoundingClientRect() }));
  const inText = e => {
    const p = e.parentElement;
    return p && (p.textContent || "").trim().length > (e.textContent || "").trim().length + 2
      && getComputedStyle(e).display === "inline";
  };
  const small = targets.filter(t => (t.r.width < 24 || t.r.height < 24) && !inText(t.e));
  const dist = (x, y, r) => Math.hypot(Math.max(r.left - x, 0, x - r.right), Math.max(r.top - y, 0, y - r.bottom));
  small.forEach(t => {
    const cx = t.r.left + t.r.width / 2, cy = t.r.top + t.r.height / 2;
    const clash = targets.find(o => o.e !== t.e && !o.e.contains(t.e) && !t.e.contains(o.e)
      && (dist(cx, cy, o.r) < 12 || (small.includes(o)
        && Math.hypot(cx - (o.r.left + o.r.width / 2), cy - (o.r.top + o.r.height / 2)) < 24)));
    if (clash) add("target-size", t.e, Math.round(t.r.width) + "x" + Math.round(t.r.height) + ", near " + describe(clash.e));
  });
  return out;
})()
"""

# Prepares the page: details open, mobile menu expanded, no transitions.
PREPARE_JS = r"""
(() => {
  const s = document.createElement("style");
  s.textContent = "*, *::before, *::after { transition: none !important; animation: none !important; }";
  document.head.appendChild(s);
  document.querySelectorAll("details").forEach(d => { d.open = true; });
  document.querySelectorAll(".navbar-collapse").forEach(n => n.classList.add("show"));
  return document.body.classList.contains("quarto-dark") ? "dark" : "light";
})()
"""

# After a Tab key press: the focused element, and whether focus is visible.
FOCUS_JS = r"""
(() => {
  const el = document.activeElement;
  if (!el || el === document.body || el === document.documentElement) return null;
  const again = !!el.__audited;
  el.__audited = true;
  const desc = el.tagName.toLowerCase() + (el.id ? "#" + el.id : "")
    + ((el.getAttribute("class") || "").trim() ? "." + el.getAttribute("class").trim().split(/\s+/).slice(0, 2).join(".") : "")
    + ' "' + ((el.getAttribute("aria-label") || el.textContent || "").trim().replace(/\s+/g, " ").slice(0, 40)) + '"';
  const props = ["outline-style", "outline-width", "outline-color", "box-shadow", "background-color",
                 "border-color", "text-decoration-line", "color"];
  const look = () => {
    const parts = [];
    // The element, its pseudo-elements (a focus ring may be drawn on
    // ::after) and two ancestors (a card may change with :focus-within).
    const styles = [getComputedStyle(el, "::before"), getComputedStyle(el, "::after")];
    for (let e = el, i = 0; e && i < 3; e = e.parentElement, i++) styles.push(getComputedStyle(e));
    styles.forEach(cs => props.forEach(p => parts.push(cs.getPropertyValue(p))));
    return parts.join("|");
  };
  const focused = look();
  el.blur();
  const unfocused = look();
  el.focus({ preventScroll: true });
  const r = el.getBoundingClientRect();
  const x0 = Math.max(r.left, 0), x1 = Math.min(r.right, innerWidth);
  const y0 = Math.max(r.top, 0), y1 = Math.min(r.bottom, innerHeight);
  let hidden = x1 <= x0 || y1 <= y0;
  if (!hidden) {
    const hit = document.elementFromPoint((x0 + x1) / 2, (y0 + y1) / 2);
    hidden = !(hit && (hit === el || el.contains(hit) || hit.contains(el)));
  }
  return { desc, again, visible: focused !== unfocused, hidden };
})()
"""

TOGGLE_JS = r"""
(async () => {
  const sw = [...document.querySelectorAll(".quarto-color-scheme-toggle")]
    .find(e => e.getBoundingClientRect().width > 0);
  if (!sw) return ["no visible theme switch"];
  const problems = [];
  const state = () => [document.body.classList.contains("quarto-dark"), sw.getAttribute("aria-pressed")];
  const wait = () => new Promise(r => setTimeout(r, 50));
  if (sw.getAttribute("role") !== "button") problems.push("role is not button");
  if (!sw.getAttribute("aria-label")) problems.push("no accessible name");
  let [dark, pressed] = state();
  if (String(dark) !== pressed) problems.push("aria-pressed " + pressed + " with dark=" + dark);
  sw.click(); await wait();
  [dark, pressed] = state();
  if (!dark || pressed !== "true") problems.push("after a click: dark=" + dark + ", aria-pressed=" + pressed);
  sw.focus();
  sw.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true, cancelable: true }));
  await wait();
  [dark, pressed] = state();
  if (dark || pressed !== "false") problems.push("after the space bar: dark=" + dark + ", aria-pressed=" + pressed);
  try { localStorage.clear(); } catch (e) {}
  return problems;
})()
"""


# Runs axe-core (see --axe): violations and results to review, by rule.
AXE_JS = r"""
axe.run(document, {
  runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa", "best-practice"] },
  resultTypes: ["violations", "incomplete"]
}).then(r => {
  const pick = list => list.map(v => ({
    id: v.id, help: v.help, wcag: v.tags.some(t => /^wcag2\d?a{1,2}$/.test(t)),
    nodes: v.nodes.map(n => n.target.join(" "))
  }));
  return { violations: pick(r.violations), incomplete: pick(r.incomplete) };
})
"""


# Contrast that axe cannot decide (text in SVG charts, very short text, text
# partly hidden in a scrolling table...) is measured on the rendered page:
# the pixels that change when the text is hidden are those of its letters, and
# the page without the text gives the background under them.

# Scrolls the first element into view and returns, for every selector, the
# visible boxes of its text with their colour and size; "complete" is false
# when part of the text is outside the window, cut by a scrolling box or under
# the navigation bar.
TEXT_BOXES_JS = r"""
async sels => {
  // The page at rest: no focused element (after the Tab key, the skip link
  // stays visible over the site title).
  if (document.activeElement && document.activeElement !== document.body) document.activeElement.blur();
  // The mobile menu is open only to measure its own items.
  const first = document.querySelector(sels[0]);
  const inMenu = !!(first && first.closest(".navbar-collapse"));
  document.querySelectorAll(".navbar-collapse").forEach(n => n.classList.toggle("show", inMenu));
  // The navigation bar hides and reappears as the page scrolls (headroom):
  // keep it in place, so that it does not move between the screenshots.
  if (!document.getElementById("audit-pin-header")) {
    const st = document.createElement("style");
    st.id = "audit-pin-header";
    st.textContent = "#quarto-header, .headroom { transform: none !important; }";
    document.head.appendChild(st);
  }
  const settle = () => new Promise(r => setTimeout(r, 100));
  if (first) first.scrollIntoView({ block: "center", inline: "center", behavior: "instant" });
  await settle();
  function parse(c) {
    let m = c && c.match(/^rgba?\(([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s,\/]+/).filter(Boolean).map(parseFloat);
      return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1];
    }
    m = c && c.match(/^color\(srgb ([^)]+)\)/);
    if (m) {
      const p = m[1].split(/[\s\/]+/).filter(Boolean).map(parseFloat);
      return [p[0] * 255, p[1] * 255, p[2] * 255, p.length > 3 ? p[3] : 1];
    }
    return null;
  }
  const opacity = el => { let o = 1; for (let e = el; e; e = e.parentElement) o *= parseFloat(getComputedStyle(e).opacity); return o; };
  // Fixed or sticky content at the top of the window (the navigation bar):
  // it covers the page, but not its own text.
  let top = 0;
  const bars = [...document.querySelectorAll("header, nav, .fixed-top, .sticky-top")].filter(e => {
    const r = e.getBoundingClientRect();
    return /fixed|sticky/.test(getComputedStyle(e).position) && r.top <= 1 && r.bottom < innerHeight / 2;
  });
  bars.forEach(e => { top = Math.max(top, e.getBoundingClientRect().bottom); });
  const inBar = el => bars.some(b => b.contains(el));
  // Near the end of a page the element may stay under the bar: scroll back.
  if (first && !inBar(first) && first.getBoundingClientRect().top < top + 8) {
    window.scrollBy({ top: first.getBoundingClientRect().top - top - 16, behavior: "instant" });
    await settle();
  }
  const out = {};
  for (const sel of sels) {
    const el = document.querySelector(sel);
    const boxes = [];
    let complete = !!el;
    const walker = el ? document.createTreeWalker(el, NodeFilter.SHOW_TEXT) : null;
    while (walker && walker.nextNode()) {
      const t = walker.currentNode, p = t.parentElement;
      if (!t.nodeValue.trim() || !p) continue;
      const cs = getComputedStyle(p);
      if (cs.display === "none" || cs.visibility === "hidden") continue;
      const svg = p instanceof SVGElement;
      const fg = parse(svg ? cs.fill : cs.color);
      if (!fg) continue;
      fg[3] *= opacity(p) * (svg ? parseFloat(cs.fillOpacity) : 1);
      let px = parseFloat(cs.fontSize);
      if (svg && p.getScreenCTM) px *= p.getScreenCTM().a;
      const large = px >= 24 || (px >= 18.66 && parseInt(cs.fontWeight, 10) >= 700);
      const range = document.createRange();
      range.selectNodeContents(t);
      let rects = [...range.getClientRects()];
      if (!rects.length && svg) rects = [p.getBoundingClientRect()];
      for (const r of rects) {
        let x0 = Math.max(r.left, 0), y0 = Math.max(r.top, inBar(p) ? 0 : top);
        let x1 = Math.min(r.right, innerWidth), y1 = Math.min(r.bottom, innerHeight);
        for (let a = p.parentElement; a; a = a.parentElement) {
          const acs = getComputedStyle(a);
          if (!/(auto|scroll|hidden|clip)/.test(acs.overflowX + acs.overflowY)) continue;
          const ar = a.getBoundingClientRect();
          x0 = Math.max(x0, ar.left); y0 = Math.max(y0, ar.top); x1 = Math.min(x1, ar.right); y1 = Math.min(y1, ar.bottom);
        }
        if (x1 - x0 < r.width - 1 || y1 - y0 < r.height - 1) complete = false;
        // Text under opaque content does not change in the screenshots, so
        // it is not counted; transparent layers (a link stretched over a
        // card) do not matter.
        if (x1 - x0 < 1 || y1 - y0 < 1) continue;
        boxes.push({ x0, y0, x1, y1, fg, large, px });
      }
    }
    out[sel] = { boxes, complete };
  }
  return { scroll: [scrollX, scrollY], items: out };
}
"""

# Hides the letters of all text, and nothing else (borders, lines, the
# halo of map labels stay).
HIDE_TEXT_JS = r"""
(() => {
  const s = document.createElement("style");
  s.id = "audit-hide-text";
  s.textContent = "*, *::before, *::after { -webkit-text-fill-color: transparent !important; }"
    + " svg text, svg tspan, svg textPath { fill: transparent !important; }";
  document.head.appendChild(s);
  void document.body.offsetHeight;
  return new Promise(r => setTimeout(() => r(true), 100));
})()
"""

# Compares the screenshots with and without text; for every selector, the
# contrast between the text colour and the background under its letters that
# 98% of their pixels reach, with what WCAG asks (4.5:1, or 3:1 for large
# text).
COMPARE_JS = r"""
async (withText, withoutText, boxes, clip) => {
  async function pixels(data) {
    const img = new Image();
    img.src = "data:image/png;base64," + data;
    await img.decode();
    const c = document.createElement("canvas");
    c.width = img.naturalWidth; c.height = img.naturalHeight;
    const g = c.getContext("2d", { willReadFrequently: true });
    g.drawImage(img, 0, 0);
    return g;
  }
  const lum = c => {
    const f = v => { v /= 255; return v <= 0.04045 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
  };
  const ratio = (a, b) => { const x = lum(a), y = lum(b); return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05); };
  const a = await pixels(withText), b = await pixels(withoutText);
  const k = a.canvas.width / clip.width;
  const out = {};
  for (const [sel, list] of Object.entries(boxes)) {
    const seen = [];
    for (const bx of list) {
      const X = Math.floor((bx.x0 - clip.x) * k), Y = Math.floor((bx.y0 - clip.y) * k);
      const W = Math.ceil((bx.x1 - clip.x) * k) - X, H = Math.ceil((bx.y1 - clip.y) * k) - Y;
      if (W < 1 || H < 1) continue;
      const da = a.getImageData(X, Y, W, H).data, db = b.getImageData(X, Y, W, H).data;
      const need = bx.large ? 3 : 4.5, f = bx.fg;
      for (let i = 0; i < da.length; i += 4) {
        if (Math.abs(da[i] - db[i]) + Math.abs(da[i + 1] - db[i + 1]) + Math.abs(da[i + 2] - db[i + 2]) < 24) continue;
        const bg = [db[i], db[i + 1], db[i + 2]];
        const fg = [0, 1, 2].map(j => f[j] * f[3] + bg[j] * (1 - f[3]));
        // Only pixels at least half covered by a letter: the smoothed edges
        // blend text and background and do not show what is under the text.
        const c = [0, 1, 2].reduce((m, j) => Math.abs(fg[j] - bg[j]) > Math.abs(fg[m] - bg[m]) ? j : m, 0);
        if (Math.abs(fg[c] - bg[c]) < 1 || (da[i + c] - bg[c]) / (fg[c] - bg[c]) < 0.5) continue;
        seen.push({ ratio: ratio(fg, bg), need, px: bx.px });
      }
    }
    // 98% of the letter pixels must reach the threshold: a single pixel where
    // a letter touches a darker line does not decide.
    seen.sort((p, q) => p.ratio / p.need - q.ratio / q.need);
    out[sel] = seen.length ? Object.assign(seen[Math.floor(seen.length * 0.02)], { letters: seen.length }) : null;
  }
  return out;
}
"""


def measure_contrast(page, selectors, retry=True):
    """Contrast of the given elements' text, measured on the rendered page:
    {selector: {"ratio", "need", "px", "letters"} or None when no letter of
    the text could be seen}. Text that could not be seen is tried once more
    (the page may still have been settling after a scroll)."""
    results, pending = {}, list(dict.fromkeys(selectors))
    while pending:
        found = evaluate(page, f"({TEXT_BOXES_JS})({json.dumps(pending)})")
        info = found["items"]
        # The first element is in view: measure it, and every other element
        # whose text is all visible at the same time.
        ready = [s for i, s in enumerate(pending) if i == 0 or info[s]["complete"]]
        boxes = {s: info[s]["boxes"] for s in ready}
        every = [b for s in ready for b in boxes[s]]
        pending = [s for s in pending if s not in ready]
        if not every:
            results.update({s: None for s in ready})
            continue
        # Only the area of the text, in whole CSS pixels (window coordinates
        # here, page coordinates for Chrome).
        x, y = math.floor(min(b["x0"] for b in every)), math.floor(min(b["y0"] for b in every))
        clip = {"x": x, "y": y, "width": math.ceil(max(b["x1"] for b in every)) - x,
                "height": math.ceil(max(b["y1"] for b in every)) - y}
        area = dict(clip, x=x + found["scroll"][0], y=y + found["scroll"][1], scale=1)
        shots = []
        for script in (None, HIDE_TEXT_JS):
            if script:
                evaluate(page, script)
            shots.append(page.call("Page.captureScreenshot", format="png", captureBeyondViewport=True,
                                   clip=area)["data"])
        evaluate(page, "document.getElementById('audit-hide-text').remove()")
        results.update(evaluate(page, f"({COMPARE_JS})({json.dumps(shots[0])}, {json.dumps(shots[1])},"
                                      f" {json.dumps(boxes)}, {json.dumps(clip)})"))
    missing = [s for s, m in results.items() if m is None]
    if retry and missing:
        results.update(measure_contrast(page, missing, retry=False))
    return results


def evaluate(page, expression):
    r = page.call("Runtime.evaluate", expression=expression, returnByValue=True, awaitPromise=True)
    if "exceptionDetails" in r:
        raise RuntimeError(r["exceptionDetails"].get("exception", {}).get("description", "script error"))
    return r["result"].get("value")


def press_tab(page):
    for kind in ("keyDown", "keyUp"):
        page.call("Input.dispatchKeyEvent", type=kind, key="Tab", code="Tab",
                  windowsVirtualKeyCode=9, nativeVirtualKeyCode=9)


def unnamed(page):
    """Controls and images without an accessible name, from the accessibility tree."""
    out = []
    for node in page.call("Accessibility.getFullAXTree").get("nodes", []):
        role = node.get("role", {}).get("value")
        if node.get("ignored") or role not in NAMED_ROLES or (node.get("name") or {}).get("value", "").strip():
            continue
        html = ""
        if node.get("backendDOMNodeId"):
            try:
                obj = page.call("DOM.resolveNode", backendNodeId=node["backendDOMNodeId"])["object"]
                html = page.call("Runtime.callFunctionOn", objectId=obj["objectId"], returnByValue=True,
                                 functionDeclaration="function () { return this.outerHTML.slice(0, 120); }"
                                 )["result"].get("value", "")
            except RuntimeError:
                pass
        out.append(["name", role, html])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:4321")
    ap.add_argument("--page", action="append", help="check only this page (repeatable)")
    ap.add_argument("--axe", metavar="FILE", help="also run axe-core: path to axe.min.js")
    args = ap.parse_args()
    pages = args.page or PAGES
    axe_source = None
    if args.axe:
        with open(args.axe, encoding="utf-8") as f:
            axe_source = f.read()
    port = 9334
    profile = tempfile.mkdtemp(prefix="audit-")
    proc = subprocess.Popen([find_chrome(), "--headless=new", f"--remote-debugging-port={port}",
                             f"--user-data-dir={profile}", "--no-first-run", "--hide-scrollbars",
                             "--disable-extensions", "about:blank"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    total = advice = 0
    review = {}  # axe "needs review": rule -> [help, set of page/mode, nodes]
    measured = []  # contrast axe could not decide, measured: (margin, ratio, needed, element, page, mode)
    below = 0
    try:
        for _ in range(50):
            try:
                targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json/list"))
                ws_url = next(t["webSocketDebuggerUrl"] for t in targets if t["type"] == "page")
                break
            except Exception:
                time.sleep(0.2)
        page = Page(WebSocket(ws_url))
        for domain in ("Page", "Runtime", "DOM", "Accessibility"):
            page.call(f"{domain}.enable")
        toggle_checked = False
        for mode, width, height, scale, mobile, scheme in MODES:
            page.call("Emulation.setDeviceMetricsOverride", width=width, height=height,
                      deviceScaleFactor=scale, mobile=mobile)
            page.call("Emulation.setEmulatedMedia", features=[
                {"name": "prefers-color-scheme", "value": scheme},
                {"name": "prefers-reduced-motion", "value": "reduce"}])
            for name in pages:
                url = f"{args.base}/{'' if name == 'index' else name + '.html'}"
                page.events.clear()
                page.call("Page.navigate", url=url)
                page.wait_for("Page.loadEventFired")
                evaluate(page, "document.fonts.ready.then(() => true)")
                issues = []
                if mode == "desktop":
                    # Tab through the page before anything is changed in it.
                    seen = 0
                    for _ in range(600):
                        press_tab(page)
                        f = evaluate(page, FOCUS_JS)
                        if f is None or f["again"]:
                            break
                        seen += 1
                        if not f["visible"]:
                            issues.append(["focus-visible", f["desc"], "no visible change on focus"])
                        if f["hidden"]:
                            issues.append(["focus-obscured", f["desc"], "hidden by other content"])
                    if seen == 0:
                        issues.append(["focus", "", "Tab reaches no element"])
                    if not toggle_checked and scheme == "light":
                        issues += [["theme-switch", "", p] for p in evaluate(page, TOGGLE_JS)]
                        toggle_checked = True
                        page.call("Page.reload")
                        page.wait_for("Page.loadEventFired")
                if mode == "text-200":
                    evaluate(page, "document.documentElement.style.fontSize = "
                                   "2 * parseFloat(getComputedStyle(document.documentElement).fontSize) + 'px'")
                applied = evaluate(page, PREPARE_JS)
                if applied != scheme:
                    issues.append(["theme", "", f"page shown in {applied} theme, {scheme} expected"])
                time.sleep(0.1)
                issues += evaluate(page, CHECKS_JS)
                if scheme == "light" and mode in ("desktop", "mobile"):
                    issues += unnamed(page)
                label = f"{mode}/{scheme}"
                notes = []
                if axe_source:
                    evaluate(page, axe_source + "\n;typeof axe")
                    result = evaluate(page, AXE_JS)
                    for v in result["violations"]:
                        where = ", ".join(v["nodes"][:3]) + (f" and {len(v['nodes']) - 3} more" if len(v["nodes"]) > 3 else "")
                        (issues if v["wcag"] else notes).append([f"axe {v['id']}", where, "- " + v["help"]])
                    for v in result["incomplete"]:
                        nodes = v["nodes"]
                        if v["id"] == "color-contrast":
                            found = measure_contrast(page, nodes)
                            nodes = [s for s, m in found.items() if m is None]
                            for s, m in found.items():
                                if m and m["ratio"] < m["need"]:
                                    issues.append(["contrast", s, f"{m['ratio']:.2f}:1 measured, {m['need']}:1 needed"])
                                    below += 1
                                elif m:
                                    measured.append((m["ratio"] / m["need"], m["ratio"], m["need"], s, name, label))
                            if not nodes:
                                continue
                        entry = review.setdefault(v["id"], [v["help"], set(), set()])
                        entry[1].add(f"{name} {label}")
                        entry[2].update(nodes)
                total += len(issues)
                advice += len(notes)
                print(f"{label:15s} {name:24s} " + ("ok" if not issues else f"{len(issues)} issue(s)")
                      + (f", {len(notes)} best-practice note(s)" if notes else ""))
                for rule, where, detail in issues:
                    print(f"    ! {rule}: {where} {detail}".rstrip())
                for rule, where, detail in notes:
                    print(f"    ~ {rule}: {where} {detail}".rstrip())
    finally:
        proc.terminate()
        shutil.rmtree(profile, ignore_errors=True)
    if measured:
        low = min(measured)
        print(f"\nContrast that axe could not decide, measured on the rendered page: {len(measured)} measurement(s)"
              f" of {len({(m[4], m[3]) for m in measured})} text element(s) in"
              f" {len({(m[4], m[5]) for m in measured})} page/mode combinations reach the threshold"
              f" (lowest: {low[1]:.2f}:1, {low[2]}:1 needed, {low[3]} on {low[4]} {low[5]})"
              + (f"; {below} below it, listed above." if below else "."))
    if review:
        print("\naxe could not decide these by itself (needs review):")
        for rule, (help_text, where, nodes) in sorted(review.items()):
            print(f"  {rule}: {help_text}; {len(nodes)} element(s) in {len(where)} page/mode combinations"
                  + (f" ({', '.join(sorted(where))})" if len(where) <= 3 else "")
                  + f", e.g. {', '.join(sorted(nodes)[:3])}")
    print(f"\n{total} issue(s) found." + (f" {advice} best-practice note(s)." if axe_source else ""))
    sys.exit(1 if total else 0)


if __name__ == "__main__":
    main()
