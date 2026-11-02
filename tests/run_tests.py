"""Regression tests for the site's shortcodes and data.

Usage:
    python3 tests/run_tests.py              # render the test project, then check
    python3 tests/run_tests.py --no-render  # check the last rendering only (Quarto not needed)

1. Component tests. tests/fixture is a small, separate Quarto project that
   uses the site's extension (through the symbolic link _extensions) on
   sample data (tests/fixture/data/sample.bib: not real publications). The
   rendered page is checked for order, selections, author highlighting,
   links, summaries, the Cite box, languages, counts and the timeline; the
   links to other sites; the links to the sections of a research story.
2. Data checks. The site's own data files are checked for consistency:
   BibTeX keys, types and keywords; the keys and research areas used by the
   pages and by data/research.yml; the files of the research stories and
   the journal articles cited in them; the map of visiting positions and
   conference presentations (data, panels of the markers, list, spacing of
   the markers, script); news and software entries; the visit statistics
   (GoatCounter's script and the note in the footer).

Needs Quarto and PyYAML (pip install pyyaml). Exits with status 1 if a check
fails.
"""
import argparse
import base64
import glob
import hashlib
import html.parser
import json
import math
import os
import re
import shutil
import subprocess
import sys

import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE = os.path.join(ROOT, "tests", "fixture")
OUTPUT = os.path.join(FIXTURE, "_output", "index.html")
DOI_OUTPUT = os.path.join(FIXTURE, "_output", "dois.html")
LINKS_OUTPUT = os.path.join(FIXTURE, "_output", "links.html")
NEW_TAB = ("_blank", "noopener noreferrer", " (opens in a new tab)")
DOI_PATTERN = r"10\.\d{4,9}(\.\d+)*/\S+"
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
NBSP = " "

failures = []
skipped = []
checks = 0


def check(name, ok, detail=""):
    global checks
    checks += 1
    print(("  ok    " if ok else "  FAIL  ") + name + ("" if ok or not detail else "\n          " + detail))
    if not ok:
        failures.append(name)


def expect(name, got, want):
    check(name, got == want, f"expected {want!r}, got {got!r}")


# --- A minimal HTML tree -------------------------------------------------

class Node:
    def __init__(self, tag, attrs):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    @property
    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        """Visible text with white space collapsed, as a browser shows it."""
        return re.sub(r"[ \t\r\n\f]+", " ", self._raw_text(visible=True))

    def _raw_text(self, visible=False):
        return "".join(c if isinstance(c, str) else
                       ("" if visible and "visually-hidden" in c.classes else c._raw_text(visible))
                       for c in self.children)

    def all(self, tag=None, cls=None):
        """Descendants in document order, optionally filtered by tag and class."""
        out = []
        for c in self.children:
            if isinstance(c, Node):
                if (tag is None or c.tag == tag) and (cls is None or cls in c.classes):
                    out.append(c)
                out.extend(c.all(tag, cls))
        return out

    def first(self, tag=None, cls=None):
        found = self.all(tag, cls)
        return found[0] if found else None


class Tree(html.parser.HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.root, self.by_id = Node("#document", []), {}
        self.stack = [self.root]
        self.feed(text)
        self.close()

    def _add(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if "id" in node.attrs:
            self.by_id[node.attrs["id"]] = node
        return node

    def handle_starttag(self, tag, attrs):
        node = self._add(tag, attrs)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self._add(tag, attrs)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def titles(node):
    return [li.first("p", "pub-title").text() for li in node.all("li", "pub")]


# --- 1. Component tests ----------------------------------------------------

def component_tests(render):
    print("Component tests (tests/fixture, sample data)")
    if render:
        r = subprocess.run(["quarto", "render", FIXTURE], capture_output=True, text=True)
        log = r.stdout + r.stderr
        check("the test project renders", r.returncode == 0, log.strip()[-2000:])
        # Quarto prints warnings as "WARN" and the shortcodes' warnings as "(W)".
        warnings = [line for line in log.splitlines() if "WARN" in line or line.lstrip().startswith(("(W)", "(E)"))]
        expected = [w for w in warnings if "invalid2020 has an invalid DOI" in w]
        check("rendering warns about the invalid DOI of the sample data", len(expected) == 1,
              "\n          ".join(warnings))
        check("rendering gives no other warnings", len(warnings) == len(expected), "\n          ".join(warnings))
        if r.returncode != 0:
            return
    if not os.path.isfile(OUTPUT):
        check("rendered page exists", False, OUTPUT + " not found: run without --no-render")
        return
    with open(OUTPUT, encoding="utf-8") as f:
        tree = Tree(f.read())
    page = tree.by_id

    # Publication lists
    articles = page["articles"]
    items = articles.all("li", "pub")
    expect("articles: newest first, same year in file order",
           [li.attrs.get("id") for li in items],
           ["pub-alpha2025", "pub-beta2024", "pub-gamma2024", "pub-delta2020"])
    expect("articles: grouped by year, with anchors",
           [(h.text(), h.attrs.get("id")) for h in articles.all("h3", "pub-year")],
           [("2025", "article-2025"), ("2024", "article-2024"), ("2020", "article-2020")])
    alpha, beta, gamma, delta = (page["pub-" + k] for k in ("alpha2025", "beta2024", "gamma2024", "delta2020"))
    expect("titles keep the capitalisation of the file",
           alpha.first("p", "pub-title").text(), "Heaping Effects in GAITD Models of Airbnb Data")
    expect("title links to the DOI", alpha.first("p", "pub-title").first("a").attrs.get("href"),
           "https://doi.org/10.0000/alpha")
    expect("title links to the URL when there is no DOI",
           gamma.first("p", "pub-title").first("a").attrs.get("href"), "https://example.org/gamma")
    check("no title link without DOI or URL", delta.first("p", "pub-title").first("a") is None)
    expect("authors with initials", alpha.first("p", "pub-authors").text(), f"M.{NBSP}Rossi, L.{NBSP}Frigau")
    expect("given names reduced to initials", beta.first("p", "pub-authors").text(),
           f"L.{NBSP}Frigau, A.{NBSP}Bianchi")
    expect("the site's author is highlighted in each entry",
           [s.text() for s in articles.all("strong", "pub-me")], [f"L.{NBSP}Frigau"] * 3)
    expect("source of an article", alpha.first("p", "pub-source").text(), "Journal One, 3(2): 10–20")
    doi = alpha.first("a", "pub-doi")
    expect("DOI shown as a link", (doi.attrs.get("href"), doi.text().strip()) if doi else None,
           ("https://doi.org/10.0000/alpha", "doi:10.0000/alpha"))
    expect("summary (annote)", alpha.first("p", "pub-note").text(), "A one-sentence summary of alpha.")
    check("no summary without annote", beta.first("p", "pub-note") is None)
    code = alpha.first("a", "pub-action")
    expect("Code link", (code.attrs.get("href"), code.text().strip()) if code else None,
           ("https://example.org/alpha-code", "Code"))
    check("no 'Selected' badge on the entries (the selection is editorial)",
          not any(li.first("span", "pub-badge") or "Selected" in li.text() for li in items))
    cite = alpha.first("details", "pub-cite").first("code")._raw_text()
    check("Cite box: the entry as written in the file",
          cite.startswith("@article{alpha2025,") and "doi       = {10.0000/alpha}" in cite
          and cite.rstrip().endswith("}"), cite)
    check("Cite box: without the site-only fields",
          not any(field in cite for field in ("keywords", "annote", "alpha-code")), cite)
    check("no language attribute on English entries", all("lang" not in li.attrs for li in items))

    selected = page["selected"]
    expect("selected: selected entries only, newest first", titles(selected),
           ["Heaping Effects in GAITD Models of Airbnb Data", "Third Article, Also of 2024"])
    check("selected: year shown in each entry",
          all(li.first("span", "pub-year-inline") for li in selected.all("li", "pub")))

    area = page["area"]
    expect("research area: works in the order of research.yml", titles(area),
           ["Oldest Article", "Heaping Effects in GAITD Models of Airbnb Data"])
    check("research area: compact style", all("pub--compact" in li.classes for li in area.all("li", "pub")))

    chapters = page["chapters"]
    expect("chapters: book chapters only", titles(chapters), ["Un capitolo in italiano"])
    chapter = chapters.first("li", "pub")
    expect("language of an Italian entry", chapter.attrs.get("lang"), "it")
    expect("source of a chapter", chapter.first("p", "pub-source").text(), "In Volume Collettaneo, pp. 5–9. Editore")

    expect("publication count", page["count"].text().strip(), "4")

    # Timeline
    timeline = page["timeline"]
    svg = timeline.first("svg", "timeline")
    if svg is None:
        check("timeline is drawn", False)
        return
    expect("timeline: accessible name", svg.attrs.get("aria-label"),
           "Timeline of 6 publications from 2020 to 2025 by research line. The table below gives the numbers.")
    marks = svg.all("g", "tl-mark")
    expect("timeline: one mark per publication", len(marks), 6)
    kinds = sorted(c for m in marks for c in m.first("circle", "tl-dot").classes if c.startswith("tl-dot--"))
    expect("timeline: marks by type of publication", kinds,
           ["tl-dot--article"] * 4 + ["tl-dot--chapter", "tl-dot--proceedings"])
    check("timeline: each mark has a tooltip with year, type, title and source",
          "2025 · Journal article: Heaping Effects in GAITD Models of Airbnb Data (Journal One)"
          in [m.first("title").text() for m in marks])
    expect("timeline: research lines in the order of research.yml",
           [t.text() for t in svg.all("text", "tl-label")], ["Clustering", "Applications"])
    expect("timeline: entries without an area keyword go to the last line",
           [t.text() for t in svg.all("text", "tl-count")], ["2 publications", "4 publications"])
    rows = [[c.text() for c in tr.children if isinstance(c, Node)] for tr in timeline.first("tbody").all("tr")]
    expect("timeline: table view, newest year first", rows,
           [["2025", "1", "–", "1"], ["2024", "–", "2", "2"], ["2023", "–", "1", "1"],
            ["2022", "–", "1", "1"], ["2021", "–", "–", "0"], ["2020", "1", "–", "1"]])
    scroll = timeline.first("div", "table-scroll")
    expect("timeline: the table, which may scroll sideways, can take the keyboard focus",
           (scroll.attrs.get("tabindex"), scroll.attrs.get("role"), bool(scroll.attrs.get("aria-label")))
           if scroll else None, ("0", "group", True))

    lines = page["lines"]
    expect("by research line: one row per line, in the order of research.yml",
           [s.text() for s in lines.all("span", "lb-label")], ["Clustering", "Applications"])
    expect("by research line: totals", [s.text() for s in lines.all("span", "lb-total")], ["2", "4"])
    widths = [re.search(r"\* ([\d.]+)\)", s.attrs.get("style", "")).group(1) for s in lines.all("span", "lb-seg")]
    expect("by research line: bar lengths proportional to the counts (largest = 1)", widths,
           ["0.5000", "0.5000", "0.2500", "0.2500"])
    rows = [[c.text() for c in tr.children if isinstance(c, Node)] for tr in lines.first("tbody").all("tr")]
    expect("by research line: table view, with the totals by type", rows,
           [["Clustering", "2", "–", "–", "2"], ["Applications", "2", "1", "1", "4"],
            ["All publications", "4", "1", "1", "6"]])

    apps = page["applications"]
    methods = apps.all("li", "apps-method")
    expect("applications: the research lines with a story, linking to it",
           [(li.first("a").text(), li.first("a").attrs.get("href")) for li in methods], [("Clustering", "story.html")])
    expect("applications: the fields in the order of the data", [li.text() for li in apps.all("li", "apps-field")],
           ["Tourism", "Health"])
    curves = [p.attrs.get("d") for li in methods for p in li.all("path", "apps-curve")]
    expect("applications: one curve per line and field with a publication of the line (works outside the lines "
           "are left out), from the line to the row of the field", curves,
           ["M0 100C50 100 50 50 100 50", "M0 100C50 100 50 150 100 150"])
    check("applications: the curves are hidden from screen readers and keep their stroke width",
          all(s.attrs.get("aria-hidden") == "true" and s.attrs.get("preserveaspectratio") == "none"
              for li in methods for s in li.all("svg", "apps-paths")))
    expect("applications: the publications behind each curve, oldest first, linking to their entries",
           [(dd.text(), [a.attrs.get("href") for a in dd.all("a")]) for dd in apps.all("dd")],
           [("Clustering: Oldest Article (2020); Heaping Effects in GAITD Models of Airbnb Data (2025)",
             ["publications.html#pub-delta2020", "publications.html#pub-alpha2025"]),
            ("Clustering: Heaping Effects in GAITD Models of Airbnb Data (2025)",
             ["publications.html#pub-alpha2025"])])

    bars = page["bars"]
    rows = bars.all("li")
    expect("result bars: labels and values in the given order",
           [(r.first("span", "lb-label").text(), r.first("span", "lb-total").text()) for r in rows],
           [("Ours", "10"), ("Other", "4"), ("Third", "0")])
    expect("result bars: the highlighted bar in the accent colour, the others in grey, none for zero",
           [[c for c in s.classes if c.startswith("lb-seg--")] for r in rows for s in r.all("span", "lb-seg")],
           [["lb-seg--accent"], ["lb-seg--muted"]])
    expect("result bars: lengths proportional to the values (largest = 1)",
           [re.search(r"\* ([\d.]+)\)", s.attrs.get("style", "")).group(1) for s in bars.all("span", "lb-seg")],
           ["1.0000", "0.4000"])
    expect("result bars: the caption, as plain text", bars.first("figcaption").text(), "Counted from <Table 1> & co.")

    doi_tests()
    link_tests()
    story_tests()


def story_tests():
    """In-text references, the list of a research line and the links to the
    sections of a story (tests/fixture/story.qmd)."""
    with open(os.path.join(FIXTURE, "_output", "story.html"), encoding="utf-8") as f:
        page = f.read()
    tree = Tree(page)
    nav = tree.root.first("nav", "story-contents")
    expect("story: 'Explore this story' links to the sections, with their years, but not to 'The question' "
           "or the other stories",
           [(li.first("a").attrs.get("href"), li.first("a").text(), (li.first("span", "period") or Node("span", [])).text())
            for li in nav.all("li")] if nav else None,
           [("#first", "First phase", "2010–2012"), ("#second", "Second phase & more", "2013"),
            ("#publications", "Publications in this line", "")])
    check("story: the links come after the 'At a glance' box and are named by their title",
          nav is not None and page.find('class="story-contents"') > page.find("glance") > 0
          and nav.attrs.get("aria-labelledby") in tree.by_id)
    refs = [(a.text().strip(), a.attrs.get("href")) for a in tree.by_id["text"].all("a")]
    expect("cite: journal and year, linked to the DOI; else to the entry in the list", refs,
           [("Journal One, 2025", "https://doi.org/10.0000/alpha"), ("Journal Four, 2020", "#pub-delta2020"),
            ("the 2020 paper", "#pub-delta2020")])
    check("cite: the journal is in italics", tree.by_id["text"].first("a").first("em") is not None)
    line = tree.by_id["line"]
    expect("line: all the works of the research line, newest first, with anchors",
           [li.attrs.get("id") for li in line.all("li", "pub")], ["pub-alpha2025", "pub-delta2020"])


def new_tab(a):
    """target, rel and hidden note of a link (None when there is no link)."""
    if a is None:
        return None
    note = a.first("span", "visually-hidden")
    return (a.attrs.get("target"), a.attrs.get("rel"), note._raw_text() if note else None)


def link_tests():
    """External links open in a new tab (tests/fixture/links.qmd)."""
    with open(LINKS_OUTPUT, encoding="utf-8") as f:
        tree = Tree(f.read())
    md = {a.text().strip(): a for a in tree.by_id["md"].all("a")}
    raw = {a.text().strip(): a for a in tree.by_id["raw"].all("a")}
    expect("new tab: external Markdown link", new_tab(md.get("External")), NEW_TAB)
    expect("same tab: internal, anchor, email and own-domain links",
           [new_tab(md.get(k)) for k in ("Internal", "Anchor", "Email", "Own domain")], [(None, None, None)] * 4)
    expect("Markdown: an existing rel is kept and extended",
           new_tab(md.get("Markdown with rel")), ("_blank", "me noopener noreferrer", " (opens in a new tab)"))
    expect("new tab: external link in raw HTML", new_tab(raw.get("Raw external")), NEW_TAB)
    expect("raw HTML: an explicit target is kept", new_tab(raw.get("Kept")), ("_self", None, None))
    expect("raw HTML: an existing rel is extended",
           new_tab(raw.get("With rel")), ("_blank", "me noopener noreferrer", " (opens in a new tab)"))
    expect("raw HTML: values of rel are not repeated", new_tab(raw.get("Not repeated")), NEW_TAB)
    expect("raw HTML: anchors are not changed", new_tab(raw.get("Raw anchor")), (None, None, None))
    with open(DOI_OUTPUT, encoding="utf-8") as f:
        dois = Tree(f.read())
    links = [a for li in dois.by_id["full"].all("li", "pub") for a in li.all("a")
             if a.attrs.get("href", "").startswith("https://")]
    check("new tab: links written by the publications shortcode (titles, DOIs)",
          links and all(new_tab(a) == NEW_TAB for a in links),
          ", ".join(f"{a.attrs.get('href')}: {new_tab(a)}" for a in links if new_tab(a) != NEW_TAB))


def doi_tests():
    """DOI links (tests/fixture/dois.qmd, sample data/dois.bib)."""
    with open(DOI_OUTPUT, encoding="utf-8") as f:
        tree = Tree(f.read())
    full, compact = tree.by_id["full"], tree.by_id["compact"]

    def doi_link(key):
        a = tree.by_id["pub-" + key].first("a", "pub-doi")
        return (a.attrs.get("href"), a.text().strip()) if a else None

    expect("DOI link: plain DOI", doi_link("plain2020"), ("https://doi.org/10.0000/plain.1", "doi:10.0000/plain.1"))
    expect("DOI link: 'doi:' prefix removed", doi_link("prefixed2020"),
           ("https://doi.org/10.0000/prefixed", "doi:10.0000/prefixed"))
    expect("DOI link: DOI written as a URL, not doubled", doi_link("https2020"),
           ("https://doi.org/10.0000/HTTPS-Upper", "doi:10.0000/HTTPS-Upper"))
    expect("DOI link: old dx.doi.org URL", doi_link("dx2020"), ("https://doi.org/10.0000/dx", "doi:10.0000/dx"))
    expect("DOI link: doi.org address in the url field", doi_link("urlfield2020"),
           ("https://doi.org/10.0000/url-field", "doi:10.0000/url-field"))
    expect("DOI link: special characters encoded in the address, shown as written", doi_link("special2020"),
           ("https://doi.org/10.1002/(SICI)1097-0258(19980430)17:8%3C857::AID-SIM777%3E3.0.CO;2-E",
            "doi:10.1002/(SICI)1097-0258(19980430)17:8<857::AID-SIM777>3.0.CO;2-E"))
    expect("no DOI link for an invalid DOI", doi_link("invalid2020"), None)
    check("no title link for an invalid DOI without URL",
          tree.by_id["pub-invalid2020"].first("p", "pub-title").first("a") is None)
    expect("no DOI link without DOI; the title links to the URL",
           (doi_link("nodoi2020"), tree.by_id["pub-nodoi2020"].first("p", "pub-title").first("a").attrs.get("href")),
           (None, "https://example.org/page"))
    links = [a.attrs.get("href", "") for a in full.all("a", "pub-doi")]
    check("every DOI link is a well-formed doi.org address",
          len(links) == 6 and all(re.fullmatch(r"https://doi\.org/10\.\d{4,9}/[^\s<>\"#?]+", h) for h in links),
          ", ".join(links))
    titles = {li.attrs.get("id"): li.first("p", "pub-title").first("a") for li in full.all("li", "pub")}
    check("the title of each entry with a DOI links to the same address",
          all(titles["pub-" + k] is not None and titles["pub-" + k].attrs.get("href") == doi_link(k)[0]
              for k in ("plain2020", "prefixed2020", "https2020", "dx2020", "urlfield2020", "special2020")))
    check("no link inside another link", not any(a.all("a") for a in tree.root.all("a")))
    check("DOI links can be reached with the keyboard (href, no negative tabindex)",
          all(a.attrs.get("href") and a.attrs.get("tabindex", "0") != "-1" for a in full.all("a", "pub-doi")))
    check("DOI link icons are hidden from screen readers",
          all(svg.attrs.get("aria-hidden") == "true" for a in full.all("a", "pub-doi") for svg in a.all("svg")))
    expect("compact lists: the title links to the DOI, no separate DOI line",
           (len(compact.all("a", "pub-doi")), sum(1 for li in compact.all("li", "pub")
                                                  if (li.first("p", "pub-title").first("a") or Node("a", [])).attrs.get("href", "").startswith("https://doi.org/"))),
           (0, 6))


# --- 2. Data checks --------------------------------------------------------

def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as f:
        return f.read()


def load_yaml(path):
    return yaml.safe_load(read(path)) or {}


def bib_entries(text):
    """(type, key, text) of each entry; fields are written one per line."""
    starts = [m for m in re.finditer(r"^@(\w+)\s*\{\s*([^,\s]+)\s*,", text, re.M)]
    out = []
    for i, m in enumerate(starts):
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        out.append((m.group(1).lower(), m.group(2), text[m.start():end]))
    return out


def field(entry, name):
    m = re.search(r"^\s*" + name + r"\s*=\s*\{(.*)\},?\s*$", entry, re.M | re.I)
    return m.group(1) if m else None


def exists(path):
    return os.path.isfile(os.path.join(ROOT, path))


def project_files(pattern):
    """Files matching a pattern, relative to the project folder (glob's
    root_dir needs Python 3.10; macOS comes with 3.9)."""
    return sorted(os.path.relpath(p, ROOT) for p in glob.glob(os.path.join(ROOT, pattern)))


def data_checks():
    print("Data checks (site data and configuration)")
    # Folders synchronized by iCloud Drive or similar services may get copies
    # such as "publications 2.html" while files are rewritten.
    copies = []
    for folder, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != ".git"]
        copies += [os.path.relpath(os.path.join(folder, n), ROOT) for n in dirs + files
                   if re.search(r" \d+(\.\w+)?$", n)]
    check("no duplicate copies left by file synchronization (e.g. 'page 2.html')", not copies, ", ".join(copies))
    # Only the pages of the site: not the test project, nor copies of the code
    # (for example in the local review/ folder). Needs Quarto; with
    # --no-render the other checks also run without it.
    name = "site pages are only the top-level pages and research/ (no test project, no copies)"
    if shutil.which("quarto"):
        r = subprocess.run(["quarto", "inspect", ROOT], capture_output=True, text=True)
        pages = [os.path.relpath(p, ROOT) for p in json.loads(r.stdout)["files"]["input"]] if r.returncode == 0 else []
        stray = [p for p in pages if os.sep in p and not re.fullmatch(r"research[/\\][^/\\]+\.qmd", p)]
        check(name, pages and not stray, ", ".join(stray))
    else:
        print("  skip  " + name + " (Quarto not found)")
        skipped.append(name)
    resources = (load_yaml("_quarto.yml").get("project") or {}).get("resources") or []
    check("_quarto.yml: resources start with '/', so that files with the same names in sub-folders "
          "(e.g. a copy of the code in review/) are not published",
          resources and all(str(r).startswith("/") for r in resources), ", ".join(map(str, resources)))
    entries = bib_entries(read("data/publications.bib"))
    keys = [k for _, k, _ in entries]
    check("publications.bib has entries", len(entries) > 0)
    dupes = sorted({k for k in keys if keys.count(k) > 1})
    check("BibTeX keys are unique", not dupes, "duplicated: " + ", ".join(dupes))
    odd = [f"{k} (@{t})" for t, k, _ in entries if t not in ("article", "incollection", "inproceedings")]
    check("entry types are article, incollection or inproceedings", not odd, ", ".join(odd))
    incomplete = [k for _, k, e in entries if not all(field(e, f) for f in ("author", "title", "year"))]
    check("every entry has author, title and year (one field per line)", not incomplete, ", ".join(incomplete))
    dois = [(k, field(e, "doi")) for _, k, e in entries if field(e, "doi")]
    bad = [f"{k}: {d}" for k, d in dois if not re.fullmatch(DOI_PATTERN, d)]
    check("DOIs are written as 10.xxxx/... (no URL, no 'doi:' prefix)", not bad, "; ".join(bad))
    values = [d.lower() for _, d in dois]
    dupes = sorted({d for d in values if values.count(d) > 1})
    check("each DOI belongs to one entry only", not dupes, ", ".join(dupes))

    research = load_yaml("data/research.yml").get("research", {})
    areas = research.get("areas") or []
    ids = [str(a.get("id")) for a in areas]
    check("research areas: ids are unique and well formed",
          len(set(ids)) == len(ids) and all(re.fullmatch(r"[a-z0-9-]+", i) for i in ids), ", ".join(ids))
    problems = []
    for a in areas:
        name = a.get("id")
        if not a.get("title"):
            problems.append(f"{name}: no title")
        if a.get("story"):
            for f in ("question", "short", "image"):
                if not a.get(f):
                    problems.append(f"{name}: story without {f}")
            for f in ("story", "image"):
                if a.get(f) and not exists(a[f]):
                    problems.append(f"{name}: {a[f]} not found")
        elif not a.get("description"):
            problems.append(f"{name}: no story and no description")
        for k in a.get("publications") or []:
            if k not in keys:
                problems.append(f"{name}: no BibTeX entry '{k}'")
    check("research areas: fields, files and BibTeX keys", not problems, "; ".join(problems))
    # Each story tells how its line developed: every journal article of the
    # line is cited in the text ({{< cite key >}}), and the story ends with
    # the complete list of the line.
    uncited, odd = [], []
    for a in areas:
        if not (a.get("story") and exists(a["story"])):
            continue
        text = read(a["story"])
        cited = set(re.findall(r"\{\{<\s*cite\s+([^\s>]+)", text))
        odd += [f"{a['story']}: no BibTeX entry '{k}'" for k in sorted(cited - set(keys))]
        if f'publications line="{a.get("id")}"' not in text:
            odd.append(f"{a['story']}: no {{{{< publications line=\"{a.get('id')}\" >}}}}")
        for t, k, e in entries:
            words = [w.strip().lower() for w in (field(e, "keywords") or "").split(",")]
            if t == "article" and a.get("id") in words and k not in cited:
                uncited.append(f"{a['story']}: {k}")
    check("research stories: every journal article of the line is cited in the text", not uncited,
          ", ".join(uncited))
    check("research stories: cited keys exist; each story lists the publications of its line", not odd,
          "; ".join(odd))
    # The narrative does not name co-authors, who are named in the At a glance
    # box and in the list of publications: no surname of an author in
    # publications.bib appears outside the box and the shortcodes.
    surnames = set()
    for _, _, e in entries:
        for person in re.split(r"\s+and\s+", field(e, "author") or ""):
            surname = person.split(",")[0].strip().strip("{}")
            if surname not in ("", "Frigau", "others"):
                surnames.add(surname)
    named = []
    for a in areas:
        if not (a.get("story") and exists(a["story"])):
            continue
        text = re.sub(r"^::: \{\.column-margin \.glance\}.*?^:::\s*$", "", read(a["story"]), flags=re.S | re.M)
        text = re.sub(r"\{\{<.*?>\}\}", "", text, flags=re.S)
        found = sorted(s for s in surnames if re.search(r"(?<![\w-])" + re.escape(s) + r"(?![\w-])", text))
        if found:
            named.append(f"{a['story']}: {', '.join(found)}")
    check("research stories: the narrative does not name co-authors (only the At a glance box does)",
          surnames and not named, "; ".join(named))
    # In the At a glance box, "Co-authors" names all the co-authors of the
    # line; "Selected collaborators" names some of them and links to the
    # publications, which list all authors. Both name only co-authors of the
    # line.
    def same(name, surname):
        return name == surname or name.endswith(" " + surname)

    wrong = []
    for a in areas:
        if not (a.get("story") and exists(a["story"])):
            continue
        box = re.search(r"^::: \{\.column-margin \.glance\}(.*?)^:::\s*$", read(a["story"]), flags=re.S | re.M)
        people = next((m for m in re.finditer(r"^(\S.*)\n:   ((?:.+\n?)+)", box.group(1) if box else "", flags=re.M)
                       if m.group(1) in ("Co-authors", "Selected collaborators", "With")), None)
        if not people:
            continue
        label, listed = people.group(1), " ".join(people.group(2).split())
        line = set()
        for _, _, e in entries:
            if a.get("id") in [w.strip().lower() for w in (field(e, "keywords") or "").split(",")]:
                for person in re.split(r"\s+and\s+", field(e, "author") or ""):
                    surname = person.split(",")[0].strip().strip("{}")
                    if surname not in ("", "Frigau", "others"):
                        line.add(surname)
        pointer = re.search(r"\s*All authors are listed \[[^\]]+\]\(#publications\)\.$", listed)
        names = [n.strip() for n in re.sub(r"\(.*?\)", "", listed[:pointer.start()] if pointer else listed)
                 .rstrip(".").split(",") if n.strip()]
        found = {s for s in line if any(same(n, s) for n in names)}
        others = [n for n in names if not any(same(n, s) for s in line)]
        if label == "With":
            wrong.append(f"{a['story']}: 'With' instead of 'Co-authors' or 'Selected collaborators'")
        if others:
            wrong.append(f"{a['story']}: not a co-author of the line: {', '.join(others)}")
        if label == "Co-authors" and found != line:
            wrong.append(f"{a['story']}: 'Co-authors' but {', '.join(sorted(line - found))} missing")
        if label == "Selected collaborators" and (found == line or not pointer):
            wrong.append(f"{a['story']}: " + ("all co-authors named: use 'Co-authors'" if found == line
                                               else "no link to the publications with all authors"))
    check("research stories: At a glance names co-authors of the line, as 'Co-authors' (all) or "
          "'Selected collaborators' (some, with a link to the full author lists)", not wrong, "; ".join(wrong))
    stories = {a.get("story") for a in areas if a.get("story")}
    orphans = [p for p in project_files("research/*.qmd") if p not in stories]
    check("every page in research/ is the story of an area", not orphans, ", ".join(orphans))

    # Fields of application (data/applications.yml, diagram on the Research
    # page): each field lists publications of the research lines with a story;
    # every such line reaches at least one field.
    fields = (load_yaml("data/applications.yml").get("applications") or {}).get("fields") or []
    lines_with_story = [str(a.get("id")) for a in areas if a.get("story")]
    line_of = {}
    for _, k, e in entries:
        words = [w.strip().lower() for w in (field(e, "keywords") or "").split(",")]
        line_of[k] = next((w for w in words if w in lines_with_story), None)
    problems, reached, seen_ids = [], set(), set()
    for f in fields:
        fid, listed = f.get("id"), f.get("publications") or []
        if not (isinstance(fid, str) and re.fullmatch(r"[a-z0-9-]+", fid)) or fid in seen_ids:
            problems.append(f"bad or repeated id {fid!r}")
        seen_ids.add(fid)
        if not f.get("label") or not listed:
            problems.append(f"{fid}: no label or no publications")
        if len(set(listed)) != len(listed):
            problems.append(f"{fid}: a publication listed twice")
        for k in listed:
            if k not in line_of:
                problems.append(f"{fid}: no BibTeX entry '{k}'")
            elif not line_of[k]:
                problems.append(f"{fid}: '{k}' is not in a research line with a story")
            else:
                reached.add(line_of[k])
    check("fields of application: ids, labels and publications of the research lines with a story",
          fields and not problems, "; ".join(problems))
    check("fields of application: every research line with a story reaches a field",
          set(lines_with_story) <= reached, ", ".join(sorted(set(lines_with_story) - reached)))
    metadata = load_yaml("_quarto.yml").get("metadata-files") or []
    check("fields of application: data/applications.yml is read by the site (metadata-files in _quarto.yml)",
          "data/applications.yml" in metadata)

    vocabulary = set(ids) | {"selected"}
    unknown, not_one = [], []
    for _, k, e in entries:
        words = [w.strip().lower() for w in (field(e, "keywords") or "").split(",") if w.strip()]
        unknown += [f"{k}: {w}" for w in words if w not in vocabulary]
        if len([w for w in words if w in ids]) != 1:
            not_one.append(k)
    check("BibTeX keywords are 'selected' or ids of research areas", not unknown, "; ".join(unknown))
    check("each entry has exactly one research area (its primary category)", not not_one, ", ".join(not_one))

    used, bad = [], []
    for page in project_files("*.qmd") + project_files("research/*.qmd"):
        text = read(page)
        for m in re.finditer(r'\{\{<\s*publications\b[^>]*?keys="([^"]*)"', text):
            used += [(page, k.strip()) for k in m.group(1).split(",") if k.strip()]
        for m in re.finditer(r'\{\{<\s*publications\b[^>]*?area="([^"]*)"', text):
            if m.group(1) not in ids:
                bad.append(f"{page}: area '{m.group(1)}'")
        for m in re.finditer(r'\{\{<\s*story-figure\b[^>]*?files="([^"]*)"', text):
            bad += [f"{page}: {f}" for f in m.group(1).split(",") if not exists(f.strip())]
        for line in text.splitlines():
            if line.startswith("#") and "{{< icon" in line and "{#" not in line:
                bad.append(f"{page}: heading with an icon and no explicit id ({line.strip()})")
    missing = [f"{p}: {k}" for p, k in used if k not in keys]
    check("pages: listed BibTeX keys exist", used and not missing, "; ".join(missing))
    check("pages: research areas and story figures exist", not bad, "; ".join(bad))

    cmap = read("_citation-map.md")
    circles = [(float(r), int(n)) for r, n in
               re.findall(r'<circle class="map-point"[^>]*r="([\d.]+)"><title>[^<]*: (\d+) citing work', cmap)]
    if circles:
        r_max, n_max = max(circles, key=lambda c: c[1])
        k = r_max / n_max ** 0.5
        off = [(r, n) for r, n in circles if abs(r - k * n ** 0.5) > 0.06]
    check("citation map: circle areas proportional to the number of citing works",
          circles and not off, f"{len(circles)} circles, not proportional: {off[:5] if circles else ''}")
    check("citation map: no tables, links or data files to download",
          "<table" not in cmap and "<a " not in cmap
          and not any(os.path.exists(os.path.join(ROOT, "data", f)) for f in ("citations.json", "citation-map.json")))

    contact = read("_contact-map.md")
    check("contact map: OpenStreetMap attribution, no iframe, script or third-party resource",
          "openstreetmap.org/copyright" in contact and "OpenStreetMap" in contact
          and not re.search(r"<(iframe|script|img|link)\b|\bsrc=", contact))

    travel_tests()
    analytics_tests()

    news = load_yaml("data/news.yml").get("news") or []
    dates = [str(n.get("date", "")) for n in news]
    check("news: every item has a date (YYYY-MM) and a text",
          news and all(re.fullmatch(r"\d{4}-(0[1-9]|1[0-2])", d) for d in dates)
          and all(n.get("text") for n in news), ", ".join(dates))
    check("news: newest first", dates == sorted(dates, reverse=True), ", ".join(dates))

    software = load_yaml("data/software.yml").get("software") or []
    kinds = {"shiny-app", "r-package", "research-code", "dataset", "tool"}
    links = {"app", "download", "docs", "repo", "cran", "data", "paper"}
    problems = []
    sw_ids = [str(p.get("id")) for p in software]
    if len(set(sw_ids)) != len(sw_ids):
        problems.append("ids are not unique")
    for p in software:
        name = p.get("id")
        if not (p.get("title") and p.get("summary")):
            problems.append(f"{name}: no title or summary")
        if p.get("kind") not in kinds:
            problems.append(f"{name}: kind '{p.get('kind')}'")
        if p.get("status", "active") not in ("active", "archived", "draft"):
            problems.append(f"{name}: status '{p.get('status')}'")
        for k, v in (p.get("links") or {}).items():
            if k not in links or not str(v).startswith("https://"):
                problems.append(f"{name}: link {k}: {v}")
    check("software: ids, fields, kinds and links", not problems, "; ".join(problems))


def travel_tests():
    """Map of visiting positions and conference presentations (About page)."""
    raw = read("data/academic_travel.yml")
    acts = (yaml.safe_load(raw) or {}).get("activities") or []
    tmap = read("_travel-map.md")
    m = re.search(r"sha256 ([0-9a-f]{64})", tmap)
    with open(os.path.join(ROOT, "data", "academic_travel.yml"), "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    check("travel map: _travel-map.md is up to date with data/academic_travel.yml "
          "(run python3 scripts/travel_map.py)", m and m.group(1) == digest)
    required = {"visit": ("name", "host", "topic", "city", "country", "year", "dates", "lat", "lon", "source"),
                "talk": ("name", "event", "city", "country", "year", "dates", "lat", "lon", "source")}
    problems = []
    for a in acts:
        kind = a.get("type")
        if kind not in required:
            problems.append(f"{a.get('name')}: type '{kind}'")
            continue
        problems += [f"{a.get('name')} {a.get('year')}: no {f}" for f in required[kind] if a.get(f) in (None, "")]
        if not re.fullmatch(r"(19|20)\d\d", str(a.get("year"))) or str(a.get("year")) not in str(a.get("dates")):
            problems.append(f"{a.get('name')}: year {a.get('year')} / dates {a.get('dates')}")
    check("travel map: every activity has a type, place, year, dates, position and source",
          acts and not problems, "; ".join(problems))
    check("travel map: no online events",
          not any("online" in str(v).lower() for a in acts for v in a.values()))
    empty = [f"{a.get('name')} {a.get('year')}: {f}" for a in acts for f in ("role", "unit", "title")
             if f in a and not str(a[f] or "").strip()]
    check("travel map: optional fields (role, unit, title) are left out rather than empty", not empty,
          ", ".join(empty))
    script ='<script src="assets/js/travel-map.js" defer></script>'
    check("travel map: Natural Earth and OpenStreetMap credited; only the local script; no image, iframe "
          "or other site",
          "Natural Earth" in tmap and "openstreetmap.org/copyright" in tmap and tmap.count(script) == 1
          and not re.search(r"<(iframe|script|img|link)\b|\bsrc=", tmap.replace(script, ""))
          and set(re.findall(r'href="(https?://[^"]+)"', tmap)) == {"https://www.openstreetmap.org/copyright"})
    tree = Tree(tmap)
    tips = {t.attrs.get("id"): t for t in tree.root.all("div", "tm-tip")}
    marks = tree.root.all("g", "tm-mark")
    check("travel map: each marker has an accessible name and its own panel (role tooltip, hidden until needed)",
          marks and sorted(m.attrs.get("data-tip") for m in marks) == sorted(tips)
          and all(m.attrs.get("data-label") for m in marks)
          and all(t.attrs.get("role") == "tooltip" and "hidden" in t.attrs for t in tips.values()))
    layers = {}
    for layer in tree.root.all("g", "tm-layer"):
        layers.setdefault(layer.classes[-1], []).extend(layer.all("g", "tm-mark"))
    listing = tree.root.first("details", "tm-list")
    listing = listing.text() if listing else ""
    missing = []
    for name, layer_marks in layers.items():
        panels = " ".join(tips[m.attrs.get("data-tip")].text() for m in layer_marks if m.attrs.get("data-tip") in tips)
        for a in acts:
            details = [f"{a.get('city')}, {a.get('country')}", f"{a.get('year')} {a.get('name')}"]
            details += [str(a[f]) for f in ("title", "role", "unit", "host", "topic") if a.get(f)]
            if not all(d in panels for d in details):
                missing.append(f"{name}: {a.get('name')} {a.get('year')}")
    for a in acts:
        if not all(str(a.get(f)) in listing for f in ("year", "city", "country", "title" if a.get("title") else "name")):
            missing.append(f"list: {a.get('name')} {a.get('year')}")
    check("travel map: every activity is in a marker's panel, in both layers of markers, and in the list",
          len(layers) == 2 and not missing, ", ".join(missing))
    # In each layer, markers do not overlap and, at the smallest width of the
    # map at which the layer is shown (theme.scss), are at least 24 CSS pixels
    # apart, as WCAG 2.5.8 asks of small targets.
    smallest = {"tm-layer--wide": 600, "tm-layer--narrow": 235}  # map widths in CSS px (on a 320 px screen: 235)
    problems, layers_ok = [], []
    for k, svg in enumerate(re.findall(r'<svg class="tm-svg".*?</svg>', tmap, re.S)):
        width = float(re.search(r'viewBox="0 0 ([\d.]+)', svg).group(1))
        parts = re.split(r'<g class="tm-layer (tm-layer--\w+)">', svg)
        for name, body in zip(parts[1::2], parts[2::2]):
            points = [(float(x), float(y), float(r)) for x, y, r in
                      re.findall(r'<circle class="tm-talk" cx="([\d.]+)" cy="([\d.]+)" r="([\d.]+)"', body)]
            points += [(float(x), (float(y1) + float(y2)) / 2, (float(y2) - float(y1)) / 2) for x, y1, y2 in
                       re.findall(r'<path class="tm-visit" d="M([\d.]+),([\d.-]+)L[\d.]+,[\d.]+L[\d.]+,([\d.]+)L', body)]
            layers_ok.append(name in smallest and len(points) == body.count('<g class="tm-mark"'))
            scale = smallest.get(name, 0) / width
            for i, p in enumerate(points):
                for q in points[i + 1:]:
                    d = math.dist(p[:2], q[:2])
                    if d < p[2] + q[2] or d * scale < 24:
                        problems.append(f"map {k + 1} {name}: {p[:2]} {q[:2]}, {d * scale:.1f} px")
    check("travel map: two maps, each with two layers of markers that do not overlap and are 24 px apart",
          len(layers_ok) == 4 and all(layers_ok) and not problems, "; ".join(problems))
    check("travel map: the narrow layer replaces the wide one when the map is narrower than 600 px",
          "@container (max-width: 599.98px)" in read("assets/scss/theme.scss"))
    js = read("assets/js/travel-map.js")
    check("travel map: the script is small and uses no network, storage or cookies",
          len(js.encode()) < 10000 and not re.search(
              r"fetch|XMLHttpRequest|sendBeacon|WebSocket|cookie|Storage|indexedDB|https?://", js))
    check("travel map: included in the About page", "{{< include _travel-map.md >}}" in read("about.qmd"))


def analytics_tests():
    """Visit statistics with GoatCounter (README.md, "Statistiche delle visite")."""
    # SRI hash of https://gc.zgo.at/count.v5.js, published by GoatCounter at
    # https://www.goatcounter.com/help/countjs-versions
    sri = "sha384-atnOLvQb9t+jTSipvd75X2yginT4PjVbqDdlJAmxMm+wYElFmeR6EmLP5bYeoRVQ"
    with open(os.path.join(ROOT, "assets/js/goatcounter.v5.js"), "rb") as f:
        got = "sha384-" + base64.b64encode(hashlib.sha384(f.read()).digest()).decode()
    expect("visit statistics: assets/js/goatcounter.v5.js is GoatCounter's count.v5.js, unchanged", got, sri)
    tag = read("assets/html/goatcounter.html").strip()
    check("visit statistics: one script, served by the site itself, sending to a goatcounter.com address",
          re.fullmatch(r'<script data-goatcounter="https://[a-z0-9-]+\.goatcounter\.com/count" async '
                       r'src="/assets/js/goatcounter\.v5\.js"></script>', tag) is not None, tag)
    config = load_yaml("_quarto.yml")
    check("visit statistics: the script is in the head of every page",
          "assets/html/goatcounter.html" in (config["format"]["html"].get("include-in-header") or []))
    footer = (config["website"].get("page-footer") or {}).get("right", "")
    check("footer: says that visits are counted with GoatCounter (link to its privacy policy), not 'No analytics'",
          'href="https://www.goatcounter.com/privacy"' in footer and "analytics" not in footer.lower(), footer)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-render", action="store_true", help="check the last rendering of tests/fixture")
    args = ap.parse_args()
    component_tests(render=not args.no_render)
    data_checks()
    print(f"\n{checks - len(failures)} of {checks} checks passed."
          + (f" {len(skipped)} skipped (Quarto not found)." if skipped else ""))
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
