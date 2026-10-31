"""Check the links of the built site.

Usage:
    python3 scripts/check_links.py _site              # internal links only
    python3 scripts/check_links.py _site --external   # also external links

Internal links (pages, files and #anchors) must resolve inside the built site;
any broken internal link makes the script exit with status 1. Links to other
sites must open in a new tab (target="_blank", rel="noopener noreferrer" and
a hidden "(opens in a new tab)" for screen readers); links within the site
must not. External links
are requested over the network: some publishers and databases refuse
automated requests (HTTP 403/429) or need cookies, so those are reported as
"not verifiable" rather than as errors. Links to doi.org are checked with the
DOI system's own service (https://doi.org/api/handles/...), which says
whether the DOI exists without contacting the publisher. Uses only the Python
standard library.
"""
import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

USER_AGENT = "Mozilla/5.0 (compatible; site-link-check/1.0)"


def tls_context():
    """Default certificates, or the system bundle when Python has none (python.org builds on macOS)."""
    ctx = ssl.create_default_context()
    if not ctx.get_ca_certs():
        for bundle in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
            if os.path.exists(bundle):
                return ssl.create_default_context(cafile=bundle)
    return ctx


TLS = tls_context()


class Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.ids, self.anchors, self.current = [], set(), [], None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "a" and attrs.get("href"):
            self.current = {"href": attrs["href"], "target": attrs.get("target"),
                            "rel": attrs.get("rel") or "", "text": ""}
            self.anchors.append(self.current)
        if attrs.get("id"):
            self.ids.add(attrs["id"])
        if tag == "a" and attrs.get("name"):
            self.ids.add(attrs["name"])
        for key in ("href", "src"):
            value = attrs.get(key)
            if value and not (tag == "link" and attrs.get("rel") in ("canonical", "preconnect")):
                self.links.append(value)


    def handle_endtag(self, tag):
        if tag == "a":
            self.current = None

    def handle_data(self, data):
        if self.current is not None:
            self.current["text"] += data


def own_domains(site):
    """Domains of the site, from `own-domains` in _quarto.yml (next to the site folder)."""
    path = os.path.join(os.path.dirname(os.path.abspath(site)), "_quarto.yml")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("own-domains:"):
                return {d.strip().strip("'\"").lower() for d in line.split("[", 1)[1].split("]")[0].split(",")}
    return set()


def new_tab_problems(pages, root, own):
    """Links to other sites must open in a new tab, links within the site must not."""
    problems = []
    for page, c in pages.items():
        for a in c.anchors:
            parts = urllib.parse.urlsplit(a["href"])
            external = parts.scheme in ("http", "https") and parts.hostname not in own
            new_tab = a["target"] == "_blank"
            if external and not (new_tab and {"noopener", "noreferrer"} <= set(a["rel"].split())
                                 and "(opens in a new tab)" in a["text"]):
                problems.append((os.path.relpath(page, root), a["href"], "external link without new-tab attributes"))
            elif not external and new_tab:
                problems.append((os.path.relpath(page, root), a["href"], "link within the site (or email) opening a new tab"))
    return problems


def parse(path):
    c = Collector()
    with open(path, encoding="utf-8") as f:
        c.feed(f.read())
    return c


def check_external(url):
    for method in ("HEAD", "GET"):
        req = urllib.request.Request(url, method=method, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=20, context=TLS) as r:
                return url, r.status, ""
        except urllib.error.HTTPError as e:
            if method == "HEAD" and e.code in (403, 405, 400, 404, 429, 500, 501):
                continue
            return url, e.code, ""
        except Exception as e:  # network errors, redirect loops, timeouts
            if method == "HEAD":
                continue
            return url, None, str(e)[:80]
    return url, None, "no response"


def check_doi(url):
    """A doi.org link: ask the DOI system whether the DOI is registered."""
    api = "https://doi.org/api/handles/" + url.split("doi.org/", 1)[1]
    req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20, context=TLS) as r:
            found = json.load(r).get("responseCode") == 1
        return url, 200 if found else 404, "DOI" if found else "DOI not found"
    except urllib.error.HTTPError as e:
        return url, e.code, "DOI not found" if e.code == 404 else ""
    except Exception as e:  # network errors, timeouts
        return url, None, str(e)[:80]


def check_link(url):
    return check_doi(url) if url.startswith("https://doi.org/") else check_external(url)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("site", nargs="?", default="_site")
    ap.add_argument("--external", action="store_true", help="also check external links")
    args = ap.parse_args()
    root = os.path.abspath(args.site)
    if not os.path.isdir(root):
        sys.exit(f"Error: {args.site} is not a directory. Build the site first (quarto render).")
    if not os.path.isfile(os.path.join(root, "index.html")):
        sys.exit(f"Error: {args.site} has no index.html. Build the site first (quarto render).")

    pages = {}
    for d, _, files in os.walk(root):
        for f in files:
            if f.endswith(".html"):
                pages[os.path.join(d, f)] = parse(os.path.join(d, f))

    broken, external, n_internal = [], {}, 0
    for page, c in pages.items():
        rel_page = os.path.relpath(page, root)
        for link in c.links:
            parts = urllib.parse.urlsplit(link)
            if parts.scheme in ("http", "https"):
                external.setdefault(link, set()).add(rel_page)
                continue
            if parts.scheme or link.startswith("//"):
                continue  # mailto:, tel:, data:
            n_internal += 1
            if link.startswith("/"):  # root-relative, e.g. in 404.html
                target = os.path.join(root, urllib.parse.unquote(parts.path).lstrip("/"))
            else:
                target = os.path.normpath(os.path.join(os.path.dirname(page), urllib.parse.unquote(parts.path)))
            if parts.path == "":
                target = page
            if os.path.isdir(target):
                target = os.path.join(target, "index.html")
            if not os.path.exists(target):
                broken.append((rel_page, link, "missing file"))
            elif parts.fragment and target.endswith(".html"):
                ids = pages[target].ids if target in pages else parse(target).ids
                if urllib.parse.unquote(parts.fragment) not in ids:
                    broken.append((rel_page, link, "missing anchor"))

    if len(pages) < 2:
        sys.exit(f"Error: only {len(pages)} page found in {args.site}: the build looks incomplete.")
    broken += new_tab_problems(pages, root, own_domains(args.site))
    print(f"{len(pages)} pages, {n_internal} internal links, {len(external)} distinct external links")
    for page, link, why in broken:
        print(f"  BROKEN  {page}: {link} ({why})")

    failed = 0
    if args.external:
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = sorted(pool.map(check_link, external))
        for url, status, err in results:
            where = ", ".join(sorted(external[url]))
            if status and status < 400:
                print(f"  ok      {err or status}  {url}")
            elif status in (401, 403, 429) or (status is None and ("redirect" in err.lower() or "CERTIFICATE" in err)):
                print(f"  not verifiable ({status or err})  {url}  [{where}]")
            else:
                failed += 1
                print(f"  FAILED  {status or err}  {url}  [{where}]")

    if broken or failed:
        print(f"{len(broken)} broken internal links, {failed} failed external links")
        sys.exit(1)
    print("No broken links found.")


if __name__ == "__main__":
    main()
