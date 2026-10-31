"""Static map of the department for the Contact page, drawn from OpenStreetMap.

Usage:
    python3 scripts/contact_map.py                # download the map data, then draw
    python3 scripts/contact_map.py --render-only  # redraw from the downloaded data

The point is the address of the Department of Economics and Business
Sciences, University of Cagliari, given on the department's web pages (SOURCE
below): Via Sant'Ignazio 17, 09123 Cagliari. Its position is the OpenStreetMap
address point "17, Via Sant'Ignazio da Laconi" (node 4229022829, found with
Nominatim in October 2026); Luca Frigau confirmed this position in October
2026. No building is singled out.

Map data (c) OpenStreetMap contributors, Open Database License
(https://www.openstreetmap.org/copyright): the attribution is shown under the
map. The data are downloaded once from the Overpass API and kept in .cache/
(not versioned); the map is saved in _contact-map.md, included by
contact.qmd, so visitors' browsers make no request to OpenStreetMap or any
other service. Uses only the Python standard library.
"""
import json
import math
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, ".cache", "contact-map-osm.json")
SOURCE = "https://web.unica.it/unica/it/dip_scienzeecoaziend_s1_ss3_0.page"
LAT, LON = 39.2234711, 9.1113352        # OpenStreetMap node 4229022829 (address above)
NAME = ("Department of Economics", "and Business Sciences")
W, H = 760, 420                          # drawing size; 1 px = METERS_PER_PX metres
LABEL_X = (W / 2 - H / 2 + 12, W / 2 + H / 2 - 12)   # visible in the square crop too
METERS_PER_PX = 1.15
SERVERS = ["https://overpass-api.de/api/interpreter",
           "https://overpass.kumi.systems/api/interpreter",
           "https://overpass.private.coffee/api/interpreter"]
HEADERS = {"User-Agent": "personal-website-contact-map/1.0"}

KY = 110574.0 / METERS_PER_PX                          # px per degree of latitude
KX = 111320.0 * math.cos(math.radians(LAT)) / METERS_PER_PX
LAT_HALF, LON_HALF = (H / 2 + 40) / KY, (W / 2 + 40) / KX   # a margin around the view

# Shorter names for the labels: the form of the department's address, and the
# usual name of the botanical garden.
LABEL_NAMES = {"Via Sant'Ignazio da Laconi": "Via Sant'Ignazio",
               "Orto Botanico dell'Università degli Studi di Cagliari": "Orto Botanico"}

STREET_CLASS = {
    "major": {"primary", "secondary", "tertiary", "trunk", "primary_link", "secondary_link", "tertiary_link"},
    "minor": {"residential", "unclassified", "living_street", "pedestrian", "road"},
    "service": {"service"},
}


def tls_context():
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(bundle):
                return ssl.create_default_context(cafile=bundle)
    return ctx


def download():
    s, w, n, e = LAT - LAT_HALF, LON - LON_HALF, LAT + LAT_HALF, LON + LON_HALF
    box = f"{s:.6f},{w:.6f},{n:.6f},{e:.6f}"
    query = (f'[out:json][timeout:90];('
             f'way["highway"]({box});way["building"]({box});relation["building"]({box});'
             f'way["leisure"~"^(park|garden)$"]({box});relation["leisure"~"^(park|garden)$"]({box});'
             f'way["landuse"~"^(grass|recreation_ground|cemetery)$"]({box});'
             f'way["historic"]({box});relation["historic"]({box});'
             f');out geom;')
    data = urllib.parse.urlencode({"data": query}).encode()
    for url in SERVERS:
        try:
            req = urllib.request.Request(url, data=data, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=120, context=tls_context()) as r:
                return json.load(r)
        except Exception as err:  # busy or unreachable server: try the next one
            print(f"{url}: {err}", file=sys.stderr)
            time.sleep(2)
    sys.exit("No Overpass server answered: try again later.")


def xy(lat, lon):
    return W / 2 + (lon - LON) * KX, H / 2 + (LAT - lat) * KY


def path(points, closed):
    """Coordinates -> SVG path data, rounded, without points closer than 1 px."""
    out, last = [], None
    for lat, lon in points:
        x, y = xy(lat, lon)
        p = (round(x * 2) / 2, round(y * 2) / 2)
        if last is None or abs(p[0] - last[0]) + abs(p[1] - last[1]) >= 1:
            out.append(p)
            last = p
    if len(out) < (3 if closed else 2):
        return None
    d = "M" + "L".join(f"{x:g},{y:g}" for x, y in out)
    return d + ("Z" if closed else "")


def visible(points):
    return any(-60 <= x <= W + 60 and -60 <= y <= H + 60 for x, y in (xy(la, lo) for la, lo in points))


def rings(el):
    """Outer rings of a way or of a multipolygon relation, as (lat, lon) lists."""
    if el["type"] == "way":
        return [[(p["lat"], p["lon"]) for p in el.get("geometry", [])]]
    return [[(p["lat"], p["lon"]) for p in m.get("geometry", [])]
            for m in el.get("members", []) if m.get("role") == "outer" and m.get("geometry")]


def inside(lat, lon, ring):
    """Point in polygon (ray casting) on longitude/latitude."""
    hit = False
    for (la1, lo1), (la2, lo2) in zip(ring, ring[1:] + ring[:1]):
        if (la1 > lat) != (la2 > lat) and lon < lo1 + (lat - la1) * (lo2 - lo1) / (la2 - la1):
            hit = not hit
    return hit


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render(osm):
    green, buildings, streets, labels = [], [], {k: [] for k in STREET_CLASS}, []
    named = {}
    for el in osm["elements"]:
        tags = el.get("tags", {})
        if "building" in tags:
            for ring in rings(el):
                if len(ring) > 2 and visible(ring):
                    d = path(ring, True)
                    if d:
                        buildings.append(d)
        elif tags.get("leisure") in ("park", "garden") or tags.get("landuse") in (
                "grass", "recreation_ground", "cemetery") or (tags.get("historic") and el["type"] != "node"
                                                               and "highway" not in tags):
            for ring in rings(el):
                if len(ring) > 2 and visible(ring):
                    d = path(ring, True)
                    if d:
                        green.append(d)
                        name = LABEL_NAMES.get(tags.get("name"), tags.get("name"))
                        if name and len(ring) > 8:
                            xs, ys = zip(*(xy(la, lo) for la, lo in ring))
                            area = abs(sum(xs[i] * ys[i - 1] - xs[i - 1] * ys[i] for i in range(len(xs)))) / 2
                            if area > 9000:
                                labels.append((sum(xs) / len(xs), sum(ys) / len(ys), name, area))
        elif "highway" in tags:
            cls = next((k for k, v in STREET_CLASS.items() if tags["highway"] in v), None)
            pts = [(p["lat"], p["lon"]) for p in el.get("geometry", [])]
            if cls and visible(pts):
                d = path(pts, False)
                if d:
                    streets[cls].append(d)
                    if tags.get("name") and cls in ("major", "minor"):
                        named.setdefault(LABEL_NAMES.get(tags["name"], tags["name"]), []).append(pts)

    # Labels stay in the middle band, which phones also show (the map is
    # cropped to a square there), and away from the marker and its name.
    def free(x, y):
        return (LABEL_X[0] <= x <= LABEL_X[1] and 25 <= y <= H - 25
                and not (W / 2 - 130 <= x <= W / 2 + 130 and H / 2 - 78 <= y <= H / 2 + 16))

    # Street names: the longest free stretch of the named streets.
    street_labels = []
    for name, ways in named.items():
        best, best_len = None, 0
        for pts in ways:
            runs, run = [], []
            for q in (xy(la, lo) for la, lo in pts):
                if free(*q):
                    run.append(q)
                else:
                    runs.append(run)
                    run = []
            runs.append(run)
            for r in runs:
                length = sum(math.dist(r[i], r[i + 1]) for i in range(len(r) - 1))
                if length > best_len:
                    best, best_len = r, length
        if best and best_len > 6 * len(name) + 16:
            if best[-1][0] < best[0][0]:
                best = best[::-1]
            street_labels.append((best_len, name, best))
    street_labels = sorted(street_labels, reverse=True)[:3]

    svg = [f'<svg class="contact-map-svg" viewBox="0 0 {W} {H}" preserveAspectRatio="xMidYMid slice" role="img" '
           f'aria-label="{esc("Map of the streets around the Department of Economics and Business Sciences, Viale Sant’Ignazio 17, Cagliari; the department building is marked.")}">',
           f'<rect class="cm-bg" width="{W}" height="{H}"/>']
    if green:
        svg.append(f'<path class="cm-green" d="{"".join(green)}"/>')
    if buildings:
        svg.append(f'<path class="cm-building" d="{"".join(buildings)}"/>')
    for cls in ("service", "minor", "major"):
        if streets[cls]:
            d = "".join(streets[cls])
            svg.append(f'<path class="cm-casing cm-casing--{cls}" d="{d}"/>')
    for cls in ("service", "minor", "major"):
        if streets[cls]:
            svg.append(f'<path class="cm-street cm-street--{cls}" d="{"".join(streets[cls])}"/>')
    for i, (_, name, pts) in enumerate(street_labels):
        d = "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        svg.append(f'<path id="cm-street-{i}" d="{d}" fill="none"/>'
                   f'<text class="cm-street-label" dy="4"><textPath href="#cm-street-{i}" startOffset="50%" '
                   f'text-anchor="middle">{esc(name)}</textPath></text>')
    placed = 0
    for x, y, name, _ in sorted(labels, key=lambda l: -l[3]):
        half = 3.4 * len(name)              # about half the width of the label, in px
        if placed < 2 and free(x - half, y) and free(x + half, y) and free(x, y):
            svg.append(f'<text class="cm-place-label" x="{x:.0f}" y="{y:.0f}" text-anchor="middle">{esc(name)}</text>')
            placed += 1
    # Marker and its label, at the centre of the map.
    cx, cy = W / 2, H / 2
    svg.append(f'<path class="cm-pin" d="M{cx},{cy}c-6-8-11-13-11-19a11 11 0 0 1 22 0c0 6-5 11-11 19z"/>'
               f'<circle class="cm-pin-dot" cx="{cx}" cy="{cy - 19}" r="4"/>')
    svg.append(f'<text class="cm-name" x="{cx}" y="{cy - 50}" text-anchor="middle">'
               f'<tspan x="{cx}">{esc(NAME[0])}</tspan><tspan x="{cx}" dy="16">{esc(NAME[1])}</tspan></text>')
    svg.append("</svg>")

    osm_url = f"https://www.openstreetmap.org/?mlat={LAT}&amp;mlon={LON}#map=18/{LAT}/{LON}"
    gmaps_url = f"https://www.google.com/maps/search/?api=1&amp;query={LAT}%2C{LON}"
    return "\n".join([
        "<!-- Generated by scripts/contact_map.py: do not edit by hand. -->",
        "",
        "```{=html}",
        '<figure class="contact-map">' + "".join(svg) + "</figure>",
        '<p class="contact-map-links">'
        f'<a href="{osm_url}">Open in OpenStreetMap</a> · <a href="{gmaps_url}">Open in Google Maps</a></p>',
        '<p class="chart-note">Map data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap '
        'contributors</a>. The marker shows Via Sant’Ignazio 17, the address of the department; room 29 is on '
        'the first floor.</p>',
        "```",
        "",
    ])


if __name__ == "__main__":
    os.makedirs(os.path.dirname(CACHE), exist_ok=True)
    if "--render-only" in sys.argv[1:] and os.path.exists(CACHE):
        with open(CACHE, encoding="utf-8") as f:
            osm = json.load(f)
    else:
        osm = download()
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(osm, f)
    text = render(osm)
    with open(os.path.join(ROOT, "_contact-map.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(f"{len(osm['elements'])} OpenStreetMap elements; _contact-map.md: {len(text) // 1024} KB")
