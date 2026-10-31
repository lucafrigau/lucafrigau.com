"""Map of the visiting positions and conference presentations (About page).

Usage:
    python3 scripts/travel_map.py

Reads data/academic_travel.yml and writes _travel-map.md, included by
about.qmd: a legend, a world map, an enlarged map of Europe and, in a closed
block below them, the list of every activity (visiting positions; conference
presentations by year). Run it after editing the data file and commit both
files: the tests check that _travel-map.md matches the data.

Maps: Equal Earth projection; land from Natural Earth (public domain), 1:110m
for the world and 1:50m for Europe, downloaded once into .cache/. The
positions of the cities are in the data file (OpenStreetMap). Places of the
same kind whose markers would be too close share one marker (for example
Naples, Caserta and Salerno); markers of different kinds are moved apart.
Each map has two layers of markers: one for wide maps and one, with larger
markers grouped more, for maps narrower than NARROW pixels (theme.scss shows
one of them). In each layer, markers are at least 24 CSS pixels apart at the
smallest width at which the layer is shown, as WCAG 2.5.8 asks of small
targets.

Each marker has a panel with the details of its activities (role="tooltip",
hidden until needed). assets/js/travel-map.js shows it when the pointer is over
the marker, when the marker has the keyboard focus, or after a tap, and gives
the markers their keyboard access. Without JavaScript the markers keep a
native tooltip (<title>) and the list gives the same details. The page loads
nothing from other sites.

Needs PyYAML, like the tests (pip install pyyaml).
"""
import hashlib
import math
import json
import os
import sys
import urllib.request

import yaml

from citation_map import CACHE, HEADERS, ROOT, TLS, equal_earth, esc

DATA = os.path.join(ROOT, "data", "academic_travel.yml")
OUT = os.path.join(ROOT, "_travel-map.md")
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
          "geojson/ne_{}_land.geojson")
W = 760                      # width of both maps, in SVG units
EUROPE = (-7, 33, 35, 55.5)  # lon min, lon max, lat min, lat max of the enlarged map
R = 9                        # radius of a circle on wide maps; diamonds have the same area
RING = 5                     # the ring around a marker (highlight, area that responds to the pointer)
GAP = 3                      # minimum space between two markers
NARROW = 600                 # maps narrower than this, in CSS pixels, use the narrow layer
SMALLEST = 235               # the narrowest map: 235 px wide on a screen 320 pixels wide
# Layers: name, size of the markers (times R), minimum distance between the
# centres of two markers in SVG units (24 CSS pixels at the smallest width).
LAYERS = (("wide", 1.0, 24 * W / NARROW), ("narrow", 1.4, 24 * W / SMALLEST))
KINDS = {"visit": ("Visiting position", "Visiting positions"),
         "talk": ("Conference presentation", "Conference presentations")}
REQUIRED = {"visit": ("name", "host", "topic", "city", "country", "year", "dates", "lat", "lon", "source"),
            "talk": ("name", "event", "city", "country", "year", "dates", "lat", "lon", "source")}
SCRIPT = '<script src="assets/js/travel-map.js" defer></script>'


class View:
    """Equal Earth projection scaled to W units of width, for a range of
    longitudes and latitudes."""

    def __init__(self, lon0, lon1, lat0, lat1):
        edge = ([(lon, lat0) for lon in frange(lon0, lon1)] + [(lon, lat1) for lon in frange(lon0, lon1)]
                + [(lon0, lat) for lat in frange(lat0, lat1)] + [(lon1, lat) for lat in frange(lat0, lat1)])
        xs, ys = zip(*(equal_earth(lon, lat) for lon, lat in edge))
        self.x0, self.y1 = min(xs), max(ys)
        self.scale = W / (max(xs) - self.x0)
        self.h = round((self.y1 - min(ys)) * self.scale)
        self.bounds = (lon0, lon1, lat0, lat1)

    def project(self, lon, lat):
        x, y = equal_earth(lon, lat)
        return (x - self.x0) * self.scale, (self.y1 - y) * self.scale

    def contains(self, lon, lat):
        lon0, lon1, lat0, lat1 = self.bounds
        return lon0 <= lon <= lon1 and lat0 <= lat <= lat1

    def outline(self):
        """The edge of the view's range of longitudes and latitudes."""
        lon0, lon1, lat0, lat1 = self.bounds
        ring = ([(lon, lat1) for lon in frange(lon0, lon1)] + [(lon1, lat) for lat in frange(lat1, lat0)]
                + [(lon, lat0) for lon in frange(lon1, lon0)] + [(lon0, lat) for lat in frange(lat0, lat1)])
        return ring


def frange(a, b, step=0.5):
    n = max(1, round(abs(b - a) / step))
    return [a + (b - a) * i / n for i in range(n + 1)]


WORLD = View(-180, 180, -58, 84)
DETAIL = View(*EUROPE)


def load():
    with open(DATA, "rb") as f:
        raw = f.read()
    acts = (yaml.safe_load(raw) or {}).get("activities") or []
    problems = []
    for i, a in enumerate(acts, 1):
        kind = a.get("type")
        if kind not in REQUIRED:
            problems.append(f"entry {i}: type '{kind}' (visit or talk)")
            continue
        missing = [f for f in REQUIRED[kind] if a.get(f) in (None, "")]
        if missing:
            problems.append(f"entry {i} ({a.get('name')}): no {', '.join(missing)}")
        elif not (-90 <= float(a["lat"]) <= 90 and -180 <= float(a["lon"]) <= 180):
            problems.append(f"entry {i} ({a.get('name')}): lat/lon out of range")
        empty = [f for f in ("role", "unit", "title") if f in a and not str(a[f] or "").strip()]
        if empty:
            problems.append(f"entry {i} ({a.get('name')}): empty {', '.join(empty)} (leave the field out)")
    places = {}
    for a in acts:
        key = (a.get("city"), a.get("country"))
        if key in places and places[key] != (a.get("lat"), a.get("lon")):
            problems.append(f"{key[0]}: different positions in different entries")
        places[key] = (a.get("lat"), a.get("lon"))
    if problems:
        sys.exit("data/academic_travel.yml:\n  " + "\n  ".join(problems))
    return acts, hashlib.sha256(raw).hexdigest()


def download(res):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"ne_{res}_land.geojson")
    if not os.path.exists(path):
        req = urllib.request.Request(NE_URL.format(res), headers=HEADERS)
        with urllib.request.urlopen(req, timeout=120, context=TLS) as r, open(path, "wb") as f:
            f.write(r.read())
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def clip(ring, x0, y0, x1, y1):
    """Sutherland-Hodgman clipping of a polygon to a rectangle."""
    def at_x(x):
        return lambda a, b: (x, a[1] + (b[1] - a[1]) * (x - a[0]) / (b[0] - a[0]))

    def at_y(y):
        return lambda a, b: (a[0] + (b[0] - a[0]) * (y - a[1]) / (b[1] - a[1]), y)

    for inside, cross in ((lambda p: p[0] >= x0, at_x(x0)), (lambda p: p[0] <= x1, at_x(x1)),
                          (lambda p: p[1] >= y0, at_y(y0)), (lambda p: p[1] <= y1, at_y(y1))):
        out = []
        for i, p in enumerate(ring):
            q = ring[i - 1]
            if inside(p):
                if not inside(q):
                    out.append(cross(q, p))
                out.append(p)
            elif inside(q):
                out.append(cross(q, p))
        ring = out
        if not ring:
            break
    return ring


def land(view, res, step):
    """SVG path of the land in the view, from the outer rings of Natural Earth
    polygons (lakes are not needed at these scales)."""
    parts = []
    for feat in download(res)["features"]:
        g = feat["geometry"]
        for poly in (g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]):
            ring = poly[0]
            if max(lat for _, lat in ring) < -58:  # Antarctica
                continue
            pts = clip([view.project(lon, max(-58, min(84, lat))) for lon, lat in ring],
                       -2, -2, W + 2, view.h + 2)
            kept, last = [], None
            for x, y in pts:
                p = (round(x), round(y))
                if last is None or abs(p[0] - last[0]) + abs(p[1] - last[1]) >= step:
                    kept.append(p)
                    last = p
            if len(kept) > 2:
                parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in kept) + "Z")
    return "".join(parts)


def markers(acts, view, only, need):
    """Markers of the view: one per place and kind, then merged or moved apart
    where their centres would be closer than `need`."""
    marks = {}
    for a in acts:
        if not only(a):
            continue
        m = marks.setdefault((a["type"], a["city"], a["country"]),
                             {"type": a["type"], "places": [(a["city"], a["country"])], "acts": []})
        m["x"], m["y"] = view.project(float(a["lon"]), float(a["lat"]))
        m["acts"].append(a)
    marks = list(marks.values())
    while True:  # merge the closest pair of markers of the same kind that are too close
        pairs = [(math.dist((a["x"], a["y"]), (b["x"], b["y"])), i, j)
                 for i, a in enumerate(marks) for j, b in enumerate(marks)
                 if i < j and a["type"] == b["type"]]
        close = [p for p in pairs if p[0] < need]
        if not close:
            break
        _, i, j = min(close)
        a, b = marks[i], marks.pop(j)
        na, nb = len(a["places"]), len(b["places"])
        a["x"] = (a["x"] * na + b["x"] * nb) / (na + nb)
        a["y"] = (a["y"] * na + b["y"] * nb) / (na + nb)
        a["places"] += b["places"]
        a["acts"] += b["acts"]
    for _ in range(50):  # move apart markers of different kinds
        moved = False
        for i, a in enumerate(marks):
            for b in marks[i + 1:]:
                d = math.dist((a["x"], a["y"]), (b["x"], b["y"]))
                if d < need:
                    ux, uy = ((b["x"] - a["x"]) / d, (b["y"] - a["y"]) / d) if d else (1, 0)
                    push = (need - d) / 2
                    a["x"], a["y"] = a["x"] - ux * push, a["y"] - uy * push
                    b["x"], b["y"] = b["x"] + ux * push, b["y"] + uy * push
                    moved = True
        if not moved:
            break
    return sorted(marks, key=lambda m: (m["x"], m["y"]))  # keyboard order: west to east


def shape(kind, x, y, r=R):
    if kind == "talk":
        return f'<circle class="tm-talk" cx="{x:.1f}" cy="{y:.1f}" r="{r:g}"/>'
    d = r * math.sqrt(math.pi / 2)
    return (f'<path class="tm-visit" d="M{x:.1f},{y - d:.1f}L{x + d:.1f},{y:.1f}'
            f'L{x:.1f},{y + d:.1f}L{x - d:.1f},{y:.1f}Z"/>')


def key(kind):
    s = 16 / (2 * R + 6)
    return (f'<svg class="tm-key" viewBox="0 0 16 16" aria-hidden="true" focusable="false">'
            f'<g transform="translate(8 8) scale({s:.3f})">{shape(kind, 0, 0)}</g></svg>')


# --- Words ------------------------------------------------------------------

def series(words):
    """'a', 'a and b', 'a, b and c'."""
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def months(a):
    """The dates of an activity without the year, e.g. '8–10 September'."""
    return str(a["dates"]).replace(str(a["year"]), "").strip(" ,")


def by_place(m):
    """(city, country, activities) of a marker: the place with the most recent
    activity first, and the most recent activity first in each place."""
    groups = []
    for city, country in m["places"]:
        here = sorted((a for a in m["acts"] if (a["city"], a["country"]) == (city, country)),
                      key=lambda a: -int(a["year"]))
        groups.append((city, country, here))
    return sorted(groups, key=lambda g: -int(g[2][0]["year"]))


def where(places):
    """'Naples, Caserta and Salerno, Italy', or 'city, country; city, country'."""
    if len({country for _, country in places}) == 1:
        return f"{series(city for city, _ in places)}, {places[0][1]}"
    return "; ".join(f"{city}, {country}" for city, country in places)


def label(m):
    """Accessible name of a marker: places, kind and years."""
    groups = by_place(m)
    kind = KINDS[m["type"]][len(m["acts"]) > 1].lower()
    years = sorted({str(a["year"]) for a in m["acts"]})
    return f"{where([(city, country) for city, country, _ in groups])}: {kind}, {series(years)}"


def describe(a):
    """One activity in the native tooltip (<title>), used without JavaScript."""
    if a["type"] == "visit":
        return f"{(a.get('role') or 'visiting position').lower()}, {a['name']}, {a['dates']}"
    return (f"{a['name']} {a['year']}" + (f", “{a['title']}”" if a.get("title") else "")
            + (", invited session" if a.get("invited") else ""))


# --- Panels -----------------------------------------------------------------

def tip_item(a):
    """One activity in the panel of a marker: year and name, then the details."""
    out = [f'<p class="tm-tip__event"><span class="tm-tip__year">{a["year"]}</span> {esc(a["name"])}</p>']
    if a["type"] == "visit":
        if a.get("unit"):
            out.append(f'<p class="tm-tip__text">{esc(a["unit"])}</p>')
        out.append(f'<p class="tm-tip__meta">{esc(" · ".join(x for x in (a.get("role"), months(a)) if x))}</p>')
        out.append(f'<p class="tm-tip__text">Invited by {esc(a["host"])} to collaborate on {esc(a["topic"])}.</p>')
    else:
        if a.get("title"):
            out.append(f'<p class="tm-tip__text">“{esc(a["title"])}”</p>')
        meta = (months(a), "invited session" if a.get("invited") else None)
        out.append(f'<p class="tm-tip__meta">{esc(" · ".join(x for x in meta if x))}</p>')
    return "<li>" + "".join(out) + "</li>"


def tip(m, tid):
    kind = KINDS[m["type"]][len(m["acts"]) > 1]
    out = [f'<div class="tm-tip" id="{tid}" role="tooltip" hidden>',
           f'<p class="tm-tip__kind">{key(m["type"])}{kind}</p>']
    for city, country, acts in by_place(m):
        out.append(f'<div class="tm-tip__place"><p class="tm-tip__city">{esc(city)}, {esc(country)}</p>'
                   f'<ul>{"".join(tip_item(a) for a in acts)}</ul></div>')
    out.append("</div>")
    return "".join(out)


def stage(view, acts, only, text, prefix, extra=""):
    """A map, with its two layers of markers, and the panels of the markers.
    The markers become focusable buttons in travel-map.js, which also removes
    their <title>."""
    res, step = ("110m", 2) if view is WORLD else ("50m", 1.5)
    out = [f'<div class="tm-stage"><svg class="tm-svg" viewBox="0 0 {W} {view.h}" role="group" '
           f'aria-label="{esc(text)}">',
           f'<path class="map-land" aria-hidden="true" d="{land(view, res, step)}"/>', extra]
    tips = []
    for name, size, need in LAYERS:
        r = R * size
        assert need >= 2 * r * math.sqrt(math.pi / 2) + GAP, "markers of the same layer could overlap"
        out.append(f'<g class="tm-layer tm-layer--{name}">')
        for i, m in enumerate(markers(acts, view, only, need), 1):
            tid = f"{prefix}{name[0]}{i}"
            lines = [f"{city}, {country}: " + "; ".join(describe(a) for a in here)
                     for city, country, here in by_place(m)]
            out.append(f'<g class="tm-mark" data-tip="{tid}" data-label="{esc(label(m))}">'
                       f'<title>{esc(chr(10).join(lines))}</title>'
                       f'<circle class="tm-ring" cx="{m["x"]:.1f}" cy="{m["y"]:.1f}" r="{r + RING * size:g}"/>'
                       f'{shape(m["type"], m["x"], m["y"], r)}</g>')
            tips.append(tip(m, tid))
        out.append("</g>")
    out.append("</svg>")
    return "".join(out + tips) + "</div>"


# --- The list ---------------------------------------------------------------

def visit_text(a):
    place = ", ".join(x for x in (a.get("unit"), a["name"], None if a["city"] in a["name"] else a["city"],
                                  a["country"]) if x)
    return (f"{a.get('role') or 'Visiting position'}, {place}, {months(a)}. "
            f"Invited by {a['host']} to collaborate on {a['topic']}.")


def talk_text(a):
    title = f"“{a['title']}”. " if a.get("title") else ""
    return (f"{title}{a['event']}. {a['city']}, {a['country']}, {months(a)}"
            + ("; invited session" if a.get("invited") else "") + ".")


def by_year(acts, text):
    """Definition list: the year, then the activities of that year."""
    years = []
    for a in acts:
        if a["year"] not in years:
            years.append(a["year"])
    out = ["<dl>"]
    for y in years:
        group = [esc(text(a)) for a in acts if a["year"] == y]
        out.append(f"<dt>{y}</dt><dd>" + (group[0] if len(group) == 1 else
                                          "<ul>" + "".join(f"<li>{g}</li>" for g in group) + "</ul>") + "</dd>")
    out.append("</dl>")
    return "".join(out)


def render(acts, digest):
    visits = [a for a in acts if a["type"] == "visit"]
    talks = [a for a in acts if a["type"] == "talk"]
    frame = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in (WORLD.project(*p) for p in DETAIL.outline())) + "Z"

    def in_europe(a):
        return DETAIL.contains(float(a["lon"]), float(a["lat"]))

    world = stage(WORLD, acts, lambda a: not in_europe(a),
                  "World map of the places of my visiting positions (diamonds) and conference presentations "
                  "(circles) outside Europe. A dashed outline marks Europe, shown enlarged in the next map. "
                  "The list below the maps gives every activity.", "tm-w",
                  f'<path class="tm-frame" aria-hidden="true" d="{frame}">'
                  "<title>Area enlarged in the map of Europe</title></path>")
    europe = stage(DETAIL, acts, in_europe,
                   "Map of Europe with the places of my visiting positions (diamonds) and conference "
                   "presentations (circles). The list below the maps gives every activity.", "tm-e")
    html = [
        '<ul class="tm-legend" aria-label="Map legend">',
        f'<li>{key("visit")}Visiting positions</li>',
        f'<li>{key("talk")}Conference presentations</li>',
        "</ul>",
        '<p class="tm-hint" hidden>Hover over or tap a marker to see what took place there.</p>',
        f'<figure class="tm-figure">{world}<figcaption>World. The dashed outline marks the area '
        "enlarged below.</figcaption></figure>",
        f'<figure class="tm-figure">{europe}<figcaption>Europe, enlarged.</figcaption></figure>',
        '<p class="chart-note">Visiting positions and conference presentations given in person, as listed in my '
        "CV; online events are not shown. Places of the same kind that are close together share a marker. "
        "Base map: Natural Earth (public domain), Equal Earth projection. Positions of the cities: "
        '<a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>.</p>',
        '<details class="chart-details tm-list">',
        "<summary>All visiting positions and conference presentations</summary>",
        '<h3 id="visiting-positions">Visiting positions</h3>',
        by_year(visits, visit_text),
        '<h3 id="conference-presentations">Conference presentations</h3>',
        by_year(talks, talk_text),
        "</details>",
        SCRIPT,
    ]
    md = [
        f"<!-- Generated by scripts/travel_map.py from data/academic_travel.yml "
        f"(sha256 {digest}): do not edit by hand. -->",
        "",
        "::: {.chart .travel-map}",
        "```{=html}",
        "\n".join(html),
        "```",
        ":::",
        "",
    ]
    return "\n".join(md)


if __name__ == "__main__":
    activities, sha = load()
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(render(activities, sha))
    n_visit = sum(a["type"] == "visit" for a in activities)
    print(f"_travel-map.md: {n_visit} visiting positions, {len(activities) - n_visit} conference presentations")
