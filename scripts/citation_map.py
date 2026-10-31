"""Map of where the authors of the works citing Luca Frigau's publications are.

Usage:
    python3 scripts/citation_map.py                # new data from OpenAlex
    python3 scripts/citation_map.py --render-only  # redraw the map from the saved data

Data: OpenAlex (https://openalex.org, open data under CC0). The script finds
the works of the author through the ORCID iD and matches them with the
entries of data/publications.bib:

  - by DOI, the only automatic match;
  - by the OpenAlex id written in the entry (openalex = {W...}), for works
    without a DOI whose match has been checked by hand.

Works that only have a similar title are recorded as uncertain matches and
are not used. The script then collects the works that cite the matched
publications, excludes self-citations (citing works with Luca Frigau among
the authors) and counts, for each city and country, the citing works with
at least one author affiliated there (a work with authors in several places
counts once in each). All the numbers in the caption come from these counts.

Base map: Natural Earth 1:110m countries (public domain), downloaded once.

Writes:
    _citation-map.md                 map and caption, included by publications.qmd
    .cache/citation-map.json         aggregated counts used by the map (local, not versioned)
    .cache/citation-matching.json    how the publications were matched (local, for checking)

Only the map is published: no list of citing works, institutions or other
raw data. Re-run it from time to time (for example every few months) and
commit _citation-map.md. Uses only the Python standard library.
"""
import datetime
import json
import math
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request

ORCID = "0000-0002-6316-4040"
ROOT = os.path.join(os.path.dirname(__file__), "..")
CACHE = os.path.join(ROOT, ".cache")
NE_URL = ("https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
          "geojson/ne_110m_admin_0_countries.geojson")
API = "https://api.openalex.org"
HEADERS = {"User-Agent": "personal-website-citation-map/1.0"}


def tls_context():
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(bundle):
                return ssl.create_default_context(cafile=bundle)
    return ctx


TLS = tls_context()


def get_json(url):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60, context=TLS) as r:
                return json.load(r)
        except Exception as e:  # rate limits and transient errors
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))


def works(filter_expr, select):
    """All works matching an OpenAlex filter, following the cursor."""
    out, cursor = [], "*"
    while cursor:
        url = (f"{API}/works?filter={urllib.parse.quote(filter_expr, safe=':|,')}"
               f"&per-page=200&select={select}&cursor={urllib.parse.quote(cursor)}")
        data = get_json(url)
        out.extend(data["results"])
        cursor = data["meta"].get("next_cursor")
        time.sleep(0.1)
    return out


def short_id(url):
    return url.rsplit("/", 1)[-1] if url else None


# ---------------------------------------------------------------------------
# Citation data
# ---------------------------------------------------------------------------
def norm_title(t):
    import re
    import unicodedata
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", re.sub(r"\\[a-z]+|[{}]", "", t)).strip()


def norm_doi(d):
    import re
    d = (d or "").strip().lower()
    d = re.sub(r"^https?://([a-z.]*\.)?doi\.org/", "", d)
    return re.sub(r"^doi:\s*", "", d) or None


def bib_entries():
    """Key, DOI, normalized title and confirmed OpenAlex id of each entry."""
    import re
    text = open(os.path.join(ROOT, "data", "publications.bib"), encoding="utf-8").read()
    out = []
    for m in re.finditer(r"^@\w+\{([^,\s]+),(.*?)^\}", text, re.S | re.M):
        body = m.group(2)
        field = lambda name: (re.search(r"^\s*" + name + r"\s*=\s*\{(.*)\},?\s*$", body, re.M | re.I) or [None, None])[1]
        out.append({"key": m.group(1), "doi": norm_doi(field("doi")), "title": norm_title(field("title")),
                    "openalex": (field("openalex") or "").strip() or None})
    return out


def match(found, entries):
    """OpenAlex works of the author -> matched works and a matching report."""
    from difflib import SequenceMatcher
    by_doi = {norm_doi(w.get("doi")): w for w in found if w.get("doi")}
    by_id = {short_id(w["id"]): w for w in found}
    used, report = {}, {"doi": [], "confirmed": [], "uncertain": [], "unmatched": []}
    for e in entries:
        w = by_doi.get(e["doi"]) if e["doi"] else None
        if w:
            used[short_id(w["id"])] = w
            report["doi"].append(e["key"])
            continue
        if e["openalex"] and e["openalex"] in by_id:
            used[e["openalex"]] = by_id[e["openalex"]]
            report["confirmed"].append(e["key"])
            continue
        candidates = []
        for w in found:
            if w.get("doi") and norm_doi(w["doi"]) in {x["doi"] for x in entries if x["doi"]}:
                continue  # already the match of another entry
            ratio = SequenceMatcher(None, e["title"], norm_title(w.get("title"))).ratio()
            if ratio >= 0.85:
                candidates.append({"openalex": short_id(w["id"]), "title": w.get("title"),
                                   "year": w.get("publication_year"), "doi": w.get("doi"),
                                   "similarity": round(ratio, 2)})
        if candidates:
            report["uncertain"].append({"key": e["key"], "candidates": candidates})
        else:
            report["unmatched"].append(e["key"])
    return used, report


def collect():
    author = get_json(f"{API}/authors/orcid:{ORCID}")
    aid = short_id(author["id"])
    entries = bib_entries()
    found = works(f"author.id:{aid}", "id,doi,title,publication_year,cited_by_count")
    own, report = match(found, entries)
    print(f"author {aid}: {len(found)} works in OpenAlex; {len(entries)} publications on the site: "
          f"{len(report['doi'])} matched by DOI, {len(report['confirmed'])} confirmed by hand, "
          f"{len(report['uncertain'])} uncertain (not used), {len(report['unmatched'])} not found", file=sys.stderr)
    citing = {}
    for w in own.values():
        if not w.get("cited_by_count"):
            continue
        for c in works(f"cites:{short_id(w['id'])}", "id,authorships"):
            citing[c["id"]] = c

    def by_author(c):
        for a in c.get("authorships", []):
            person = a.get("author") or {}
            name = (person.get("display_name") or "") + " " + (a.get("raw_author_name") or "")
            if short_id(person.get("id")) == aid or "frigau" in name.lower():
                return True
        return False

    self_cites = {k for k, c in citing.items() if by_author(c)}
    per_work, geo, country_count = {}, {}, {}
    for k, c in citing.items():
        if k in self_cites:
            continue
        insts, countries = set(), set()
        for a in c.get("authorships", []):
            for i in a.get("institutions") or []:
                if i.get("id"):
                    insts.add(short_id(i["id"]))
                    geo.setdefault(short_id(i["id"]), {"name": i.get("display_name"), "country": i.get("country_code")})
            countries.update(a.get("countries") or [])
        per_work[k] = insts
        for cc in countries:
            country_count[cc] = country_count.get(cc, 0) + 1
    ids = list(geo)
    for start in range(0, len(ids), 50):
        batch = "|".join(ids[start:start + 50])
        data = get_json(f"{API}/institutions?filter=openalex:{batch}&per-page=50&select=id,geo")
        for r in data["results"]:
            g = r.get("geo") or {}
            info = geo.get(short_id(r["id"]))
            if info is not None:
                info.update({"city": g.get("city"), "lat": g.get("latitude"), "lon": g.get("longitude")})
        time.sleep(0.1)

    # Distinct citing works per city; works whose affiliations have no location.
    cities, unplaced = {}, 0
    for k, insts in per_work.items():
        here = set()
        for iid in insts:
            info = geo[iid]
            if info.get("lat") is None:
                continue
            key = (info.get("city") or info["name"], info.get("country"))
            cities.setdefault(key, {"city": key[0], "country": key[1], "lat": round(info["lat"], 3),
                                    "lon": round(info["lon"], 3), "works": 0})
            here.add(key)
        for key in here:
            cities[key]["works"] += 1
        if not here:
            unplaced += 1
    data = {
        "source": "OpenAlex (https://openalex.org)",
        "updated": datetime.date.today().isoformat(),
        "publications": len(entries),
        "matched_doi": len(report["doi"]),
        "matched_confirmed": len(report["confirmed"]),
        "uncertain": len(report["uncertain"]),
        "citing_works": len(citing) - len(self_cites),
        "self_citations_excluded": len(self_cites),
        "not_placed": unplaced,
        "countries": dict(sorted(country_count.items(), key=lambda kv: (-kv[1], kv[0]))),
        "cities": sorted(cities.values(), key=lambda c: (-c["works"], c["city"])),
    }
    return data, report


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------
A1, A2, A3, A4 = 1.340264, -0.081106, 0.000893, 0.003796
SQ3 = math.sqrt(3)


def equal_earth(lon, lat):
    lam, phi = math.radians(lon), math.radians(lat)
    theta = math.asin(SQ3 / 2 * math.sin(phi))
    t2 = theta * theta
    t6 = t2 * t2 * t2
    x = 2 * SQ3 * lam * math.cos(theta) / (3 * (9 * A4 * t6 * t2 + 7 * A3 * t6 + 3 * A2 * t2 + A1))
    y = theta * (A4 * t6 * t2 + A3 * t6 + A2 * t2 + A1)
    return x, y


W = 760
X_MAX = equal_earth(180, 0)[0]
Y_TOP, Y_BOTTOM = equal_earth(0, 84)[1], equal_earth(0, -58)[1]
SCALE = W / (2 * X_MAX)
H = round((Y_TOP - Y_BOTTOM) * SCALE)


def project(lon, lat):
    x, y = equal_earth(lon, lat)
    return (x + X_MAX) * SCALE, (Y_TOP - y) * SCALE


# Usual short names, and the names that take "the" in a sentence.
SHORT_NAMES = {"US": "United States"}
WITH_THE = {"US", "GB", "NL", "AE", "PH"}


def land_paths():
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, "ne_110m_admin_0_countries.geojson")
    if not os.path.exists(path):
        req = urllib.request.Request(NE_URL, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=120, context=TLS) as r, open(path, "wb") as f:
            f.write(r.read())
    geo = json.load(open(path, encoding="utf-8"))
    names, parts = {}, []
    for feat in geo["features"]:
        props = feat["properties"]
        code = props.get("ISO_A2_EH") or props.get("ISO_A2")
        names[code] = SHORT_NAMES.get(code) or props.get("NAME") or props.get("NAME_EN")
        if code == "AQ":
            continue
        g = feat["geometry"]
        polys = g["coordinates"] if g["type"] == "MultiPolygon" else [g["coordinates"]]
        for poly in polys:
            for ring in poly[:1]:  # outer ring only: lakes are not needed at this scale
                pts, last = [], None
                for lon, lat in ring:
                    x, y = project(lon, max(-58, min(84, lat)))
                    p = (round(x), round(y))
                    if last is None or abs(p[0] - last[0]) + abs(p[1] - last[1]) >= 2:
                        pts.append(p)
                        last = p
                if len(pts) > 2:
                    parts.append("M" + "L".join(f"{x:g},{y:g}" for x, y in pts) + "Z")
    return "".join(parts), names


def esc(s):
    return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;"))


# Circle area proportional to the number of citing works: r = K * sqrt(n).
K = 2.3


def radius(n):
    return K * math.sqrt(n)


def series(items):
    """["a", "b", "c"] -> "a, b and c"."""
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def render(data):
    land, names = land_paths()
    svg = [f'<svg class="citation-map-svg" viewBox="0 0 {W} {H}" role="img" aria-label="'
           f'{esc("World map of the cities where the authors of the works citing the publications of Luca Frigau were affiliated. The text below the map summarizes it.")}">',
           f'<path class="map-land" d="{land}"/>']
    for c in sorted(data["cities"], key=lambda p: -p["works"]):
        x, y = project(c["lon"], c["lat"])
        country = names.get(c.get("country"), c.get("country") or "")
        n = c["works"]
        svg.append(f'<circle class="map-point" cx="{x:.0f}" cy="{y:.0f}" r="{radius(n):.1f}"><title>'
                   f'{esc(c["city"])} ({esc(country)}): {n} citing work{"s" if n != 1 else ""}</title></circle>')
    # Legend: circles drawn with the same scale as the map.
    lx, ly = 18, H - 22
    for n in (1, 10, 50):
        r = radius(n)
        svg.append(f'<circle class="map-point" cx="{lx + r:.1f}" cy="{ly - r + 8:.1f}" r="{r:.1f}"/>')
        svg.append(f'<text class="map-legend-text" x="{lx + 2 * r + 5:.1f}" y="{ly + 4}">{n}</text>')
        lx += 2 * r + 26
    svg.append(f'<text class="map-legend-text" x="{lx - 4:.1f}" y="{ly + 4}">citing works</text>')
    svg.append("</svg>")

    date = datetime.date.fromisoformat(data["updated"])
    matched = data["matched_doi"] + data["matched_confirmed"]
    how = ("by their DOI" if not data["matched_confirmed"] else
           f"by their DOI ({data['matched_doi']}) or by a match checked by hand ({data['matched_confirmed']})")
    countries = list(data["countries"].items())
    top = [("the " if cc in WITH_THE else "") + f"{names.get(cc, cc)} ({n})" for cc, n in countries[:5]]
    lead = (f'Each circle is a city where authors of works citing my publications were affiliated, with area '
            f'proportional to the number of citing works. The map counts {data["citing_works"]} citing works, with '
            f'authors in {len(countries)} countries; the countries with the most citing works are {series(top)}. '
            f'Source: OpenAlex, {date.day} {date.strftime("%B %Y")}; the map is indicative.')
    # The method and its limits, in an element that opens on request.
    method = (f'Only the {matched} of the {data["publications"]} publications on this site that OpenAlex '
              f'identifies {how} are included; matches by title alone are not used. Places are the institutional '
              f'affiliations of the authors of the citing works, and a work with authors in several places counts '
              f'once in each. Self-citations ({data["self_citations_excluded"]} works) are excluded')
    method += (f', and {data["not_placed"]} citing works with no affiliation with a known location are not shown. '
               if data["not_placed"] else ". ")
    method += ("Coverage and affiliations in OpenAlex differ from Google Scholar and Scopus. "
               "Base map: Natural Earth (public domain), Equal Earth projection.")
    md = [
        "<!-- Generated by scripts/citation_map.py: do not edit by hand. -->",
        "",
        "::: {.chart .citation-map}",
        "```{=html}",
        '<p class="scroll-hint" aria-hidden="true">Swipe or scroll sideways to see the whole map</p>',
        '<div class="chart-scroll" tabindex="0" role="group" aria-label="Citation map, scrollable">' + "".join(svg) + "</div>",
        f'<p class="chart-note">{esc(lead)}</p>',
        '<details class="chart-details"><summary>Data sources and limitations</summary>',
        f'<p class="chart-note">{esc(method)}</p>',
        "</details>",
        "```",
        ":::",
        "",
    ]
    return "\n".join(md)


if __name__ == "__main__":
    os.makedirs(CACHE, exist_ok=True)
    saved = os.path.join(CACHE, "citation-map.json")
    if "--render-only" in sys.argv[1:]:
        if not os.path.exists(saved):
            sys.exit(f"No saved data in {saved}: run the script without --render-only first.")
        with open(saved, encoding="utf-8") as f:
            data = json.load(f)
    else:
        data, report = collect()
        with open(saved, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
        with open(os.path.join(CACHE, "citation-matching.json"), "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=1)
        for u in report["uncertain"]:
            best = max(u["candidates"], key=lambda c: c["similarity"])
            print(f"  uncertain: {u['key']} ~ {best['openalex']} \"{best['title']}\" ({best['year']}), "
                  f"similarity {best['similarity']}: add openalex = {{{best['openalex']}}} to the entry to use it",
                  file=sys.stderr)
    with open(os.path.join(ROOT, "_citation-map.md"), "w", encoding="utf-8") as f:
        f.write(render(data))
    print(f"{data['citing_works']} citing works ({data['self_citations_excluded']} self-citations excluded), "
          f"{len(data['countries'])} countries, {len(data['cities'])} cities; "
          f"{data['matched_doi'] + data['matched_confirmed']} of {data['publications']} publications used")
