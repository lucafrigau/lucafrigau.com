"""Draw the illustrations of the research stories as SVG files.

Usage: python3 scripts/make_figures.py   (writes assets/img/stories/*.svg)

The figures are schematic: they use simulated data (fixed random seeds, so
the output is reproducible) to explain an idea, and are labelled as
illustrations on the pages. Colours follow the palette of the site
(assets/scss/theme.scss). Uses only the Python standard library.
"""
import math
import os
import random

OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "img", "stories")

INK, INK3 = "#1C1B19", "#625E57"
RULE, RULE2, WHITE = "#E4DFD5", "#CFC8BB", "#FFFFFF"
ACCENT, WARM, SLATE = "#0B5563", "#8A4B0F", "#5B6C8F"
SEQ = ["#DCEBED", "#A9CBD0", "#6FA3AC", "#357987", "#0B5563"]       # low → high
BANDS = ["#EEF4F5", "#E2EDEF", "#D3E4E7"]                            # region fills
TOPICS = ["#0B5563", "#C08347", "#5B6C8F", "#7C9A6A", "#A05A6E"]     # categorical
SOFT = {ACCENT: "#E5EEEF", WARM: "#F4E9DC", SLATE: "#E8EBF1"}


def svg(name, w, h, label, body):
    """Write one SVG; `label` is the text alternative read by screen readers."""
    text = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" '
            f'role="img" aria-label="{label}" font-family="inherit">\n{body}\n</svg>\n')
    with open(os.path.join(OUT, name), "w", encoding="utf-8") as f:
        f.write(text)


def f(x):
    return f"{x:.1f}".rstrip("0").rstrip(".")


def lerp_color(c1, c2, t):
    a = [int(c1[i:i + 2], 16) for i in (1, 3, 5)]
    b = [int(c2[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# Oblique trees: the same data split by axis-parallel and by oblique cuts.
# ---------------------------------------------------------------------------
def oblique():
    rnd = random.Random(7)
    pts = [(rnd.random(), rnd.random()) for _ in range(80)]
    ys = [x1 + x2 + rnd.gauss(0, 0.12) for x1, x2 in pts]
    order = sorted(ys)
    cuts = [order[int(len(ys) * q)] for q in (0.2, 0.4, 0.6, 0.8)]
    level = [sum(y > c for c in cuts) for y in ys]
    X0, Y0, S = 34, 12, 236          # plot square
    thresholds = (0.75, 1.25)        # oblique cuts on x1 + x2

    def px(x1, x2):
        return X0 + x1 * S, Y0 + (1 - x2) * S

    def band(s):
        return sum(s > t for t in thresholds)

    def points():
        return "\n".join(
            f'<circle cx="{f(px(*p)[0])}" cy="{f(px(*p)[1])}" r="4.3" fill="{SEQ[l]}" stroke="{WHITE}" stroke-width="1"/>'
            for p, l in zip(pts, level))

    def frame():
        return (f'<rect x="{X0}" y="{Y0}" width="{S}" height="{S}" fill="none" stroke="{RULE2}"/>'
                f'<text x="{X0 + S}" y="{Y0 + S + 18}" text-anchor="end" font-size="13" fill="{INK3}">x₁</text>'
                f'<text x="{X0 - 10}" y="{Y0 + 12}" text-anchor="end" font-size="13" fill="{INK3}">x₂</text>')

    # Axis-parallel: a 6 x 6 grid whose cells take the band of their centre;
    # the borders between different bands form the staircase of splits.
    n, c = 6, S / 6
    cells, lines = [], []
    for i in range(n):
        for j in range(n):
            b = band((i + 0.5) / n + (j + 0.5) / n)
            x, y = X0 + i * c, Y0 + (n - 1 - j) * c
            cells.append(f'<rect x="{f(x)}" y="{f(y)}" width="{f(c)}" height="{f(c)}" fill="{BANDS[b]}"/>')
            if i + 1 < n and band((i + 1.5) / n + (j + 0.5) / n) != b:
                lines.append(f'<line x1="{f(x + c)}" y1="{f(y)}" x2="{f(x + c)}" y2="{f(y + c)}"/>')
            if j + 1 < n and band((i + 0.5) / n + (j + 1.5) / n) != b:
                lines.append(f'<line x1="{f(x)}" y1="{f(y)}" x2="{f(x + c)}" y2="{f(y)}"/>')
    body = "\n".join(cells) + f'\n<g stroke="{ACCENT}" stroke-width="2.2" stroke-linecap="square">' + "".join(lines) + "</g>\n"
    svg("oblique-axis.svg", 280, 284,
        "Illustration: points coloured by a response that increases along the diagonal; "
        "axis-parallel splits approximate the diagonal with a staircase of cuts.",
        body + points() + frame())

    # Oblique: three regions separated by two lines x1 + x2 = t.
    def poly(lo, hi):
        corners = [(0, 0), (1, 0), (1, 1), (0, 1)]
        out = []
        for k in range(4):
            a, b = corners[k], corners[(k + 1) % 4]
            for p in (a,):
                if lo <= p[0] + p[1] <= hi:
                    out.append(p)
            sa, sb = a[0] + a[1], b[0] + b[1]
            for t in (lo, hi):
                if (sa - t) * (sb - t) < 0:
                    r = (t - sa) / (sb - sa)
                    out.append((a[0] + r * (b[0] - a[0]), a[1] + r * (b[1] - a[1])))
        cx = sum(p[0] for p in out) / len(out)
        cy = sum(p[1] for p in out) / len(out)
        out.sort(key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        return " ".join(f"{f(px(*p)[0])},{f(px(*p)[1])}" for p in out)

    regions = "\n".join(f'<polygon points="{poly(lo, hi)}" fill="{BANDS[k]}"/>'
                        for k, (lo, hi) in enumerate([(-1, 0.75), (0.75, 1.25), (1.25, 3)]))
    cutlines = []
    for t in thresholds:
        a = (0, t) if t <= 1 else (t - 1, 1)
        b = (t, 0) if t <= 1 else (1, t - 1)
        (x1, y1), (x2, y2) = px(*a), px(*b)
        cutlines.append(f'<line x1="{f(x1)}" y1="{f(y1)}" x2="{f(x2)}" y2="{f(y2)}"/>')
    body = regions + f'\n<g stroke="{ACCENT}" stroke-width="2.2">' + "".join(cutlines) + "</g>\n"
    svg("oblique-oblique.svg", 280, 284,
        "Illustration: the same points split by two oblique lines that follow "
        "the direction in which the response changes.",
        body + points() + frame())


# ---------------------------------------------------------------------------
# Network-based semi-supervised clustering, in four steps.
# ---------------------------------------------------------------------------
def nessc():
    rnd = random.Random(11)
    centres = [(0.30, 0.62), (0.52, 0.40), (0.72, 0.66)]
    groups = [g for g in range(3) for _ in range(10)]
    feats = [(min(0.95, max(0.05, centres[g][0] + rnd.gauss(0, 0.11))),
              min(0.95, max(0.05, centres[g][1] + rnd.gauss(0, 0.11)))) for g in groups]
    outcome = [min(4, max(0, round([0.6, 2.0, 3.4][g] + rnd.gauss(0, 0.45)))) for g in groups]
    W, H = 240, 200

    # 1. Observations in feature space, coloured by the outcome.
    body = [f'<rect x="20" y="10" width="200" height="180" fill="none" stroke="{RULE2}"/>']
    for (x, y), o in zip(feats, outcome):
        body.append(f'<circle cx="{f(20 + x * 200)}" cy="{f(10 + (1 - y) * 180)}" r="5" '
                    f'fill="{SEQ[o]}" stroke="{WHITE}" stroke-width="1"/>')
    svg("nessc-1-data.svg", W, H, "Step 1: observations in the space of the predictors, "
        "coloured by the value of the outcome.", "\n".join(body))

    # 2. Pairwise affinity estimated with the outcome: block structure.
    rnd2 = random.Random(3)
    idx = [g for g in range(3) for _ in range(5)]
    cell, x0, y0 = 11, 37.5, 17.5
    body = []
    for i, gi in enumerate(idx):
        for j, gj in enumerate(idx):
            a = 1.0 if i == j else (rnd2.uniform(0.55, 0.95) if gi == gj else rnd2.uniform(0.0, 0.3))
            body.append(f'<rect x="{f(x0 + j * cell)}" y="{f(y0 + i * cell)}" width="{cell}" height="{cell}" '
                        f'fill="{lerp_color("#F7F5F0", ACCENT, a)}"/>')
    body.append(f'<rect x="{x0}" y="{y0}" width="{15 * cell}" height="{15 * cell}" fill="none" stroke="{RULE2}"/>')
    svg("nessc-2-affinity.svg", W, H, "Step 2: a matrix of pairwise affinities estimated by a "
        "classifier that uses the outcome; three blocks of high affinity appear.", "\n".join(body))

    # 3-4. The affinity matrix as a network, then its communities.
    rnd3 = random.Random(5)
    layout_c = [(66, 70), (176, 66), (120, 150)]
    nodes = []
    for g in groups:
        ang, rad = rnd3.uniform(0, 2 * math.pi), rnd3.uniform(8, 34)
        nodes.append((layout_c[g][0] + rad * math.cos(ang), layout_c[g][1] + rad * math.sin(ang) * 0.85))
    edges = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            p = 0.42 if groups[i] == groups[j] else 0.025
            if rnd3.random() < p:
                edges.append((i, j))

    def edge_svg(colour, width):
        return f'<g stroke="{colour}" stroke-width="{width}">' + "".join(
            f'<line x1="{f(nodes[i][0])}" y1="{f(nodes[i][1])}" x2="{f(nodes[j][0])}" y2="{f(nodes[j][1])}"/>'
            for i, j in edges) + "</g>"

    plain = [edge_svg(RULE2, 1)] + [f'<circle cx="{f(x)}" cy="{f(y)}" r="5" fill="{INK3}" stroke="{WHITE}" '
                                    f'stroke-width="1"/>' for x, y in nodes]
    svg("nessc-3-network.svg", W, H, "Step 3: the affinities become a network in which "
        "observations are nodes and strong affinities are links.", "\n".join(plain))

    colours = [ACCENT, WARM, SLATE]
    halos = [f'<circle cx="{c[0]}" cy="{c[1]}" r="47" fill="{SOFT[colours[k]]}"/>' for k, c in enumerate(layout_c)]
    comm = halos + [edge_svg(RULE, 1)] + [
        f'<circle cx="{f(x)}" cy="{f(y)}" r="5.2" fill="{colours[g]}" stroke="{WHITE}" stroke-width="1"/>'
        for (x, y), g in zip(nodes, groups)]
    svg("nessc-4-clusters.svg", W, H, "Step 4: a community detection algorithm finds groups of "
        "densely connected nodes, which are the clusters.", "\n".join(comm))


# ---------------------------------------------------------------------------
# Clustering: the same observations grouped from the predictors only, and
# grouped with the help of an outcome (semi-supervised clustering).
# ---------------------------------------------------------------------------
def clusters():
    rnd = random.Random(21)
    pts = []
    for cx in (0.29, 0.71):                     # two clouds in the predictors
        for k in range(16):                     # evenly spread from bottom to top
            x = cx + max(-0.15, min(0.15, rnd.gauss(0, 0.075)))
            y = 0.08 + (k + 0.5) / 16 * 0.84 + rnd.uniform(-0.018, 0.018)
            if abs(y - 0.5) < 0.035:            # keep the points off the band edges
                y = 0.5 + math.copysign(0.035, y - 0.5)
            pts.append((x, y))
    # The outcome grows from bottom to top, in both clouds.
    outcome = [min(4, max(0, round(4.6 * y - 0.3 + rnd.gauss(0, 0.3)))) for _, y in pts]
    W, H = 240, 200
    X = lambda x: 20 + x * 200
    Y = lambda y: 10 + (1 - y) * 180

    def band(x0, y0, x1, y1, col):
        return (f'<rect x="{f(X(x0))}" y="{f(Y(y1))}" width="{f(X(x1) - X(x0))}" height="{f(Y(y0) - Y(y1))}" '
                f'rx="10" fill="{SOFT[col]}" stroke="{col}" stroke-width="1.5" stroke-dasharray="5 4"/>')

    def panel(name, bands, label):
        body = [f'<rect x="20" y="10" width="200" height="180" fill="none" stroke="{RULE2}"/>'] + bands
        for (x, y), o in zip(pts, outcome):
            body.append(f'<circle cx="{f(X(x))}" cy="{f(Y(y))}" r="5" fill="{SEQ[o]}" stroke="{WHITE}" stroke-width="1"/>')
        svg(name, W, H, label, "\n".join(body))

    panel("clusters-predictors.svg", [band(0.05, 0.04, 0.485, 0.96, ACCENT), band(0.515, 0.04, 0.95, 0.96, WARM)],
          "Illustration: two groups found from the predictors only, on the left and on the right; each "
          "contains both low and high values of the outcome.")
    panel("clusters-outcome.svg", [band(0.04, 0.515, 0.96, 0.95, ACCENT), band(0.04, 0.05, 0.96, 0.485, WARM)],
          "Illustration: two groups found with the help of the outcome, at the top and at the bottom; each "
          "is homogeneous in the outcome.")


# ---------------------------------------------------------------------------
# Text mining: texts made of words; a topic model describes each text as a
# mixture of topics (groups of words that tend to occur together).
# ---------------------------------------------------------------------------
def topics():
    rnd = random.Random(8)
    mixes = [(0.75, 0.15, 0.10), (0.10, 0.80, 0.10), (0.15, 0.25, 0.60), (0.45, 0.10, 0.45)]
    W, H = 240, 200
    docs, shares = [], []
    for k, mix in enumerate(mixes):
        lines, counts = [], [0, 0, 0]
        for _ in range(5):
            words, x = [], 0
            while x < 74:
                w = rnd.randint(8, 22)
                topic = None
                if rnd.random() < 0.45:          # a word typical of a topic
                    topic = rnd.choices(range(3), weights=mix)[0]
                    counts[topic] += 1
                words.append((x, min(w, 80 - x), topic))
                x += w + 4
            lines.append(words)
        docs.append(lines)
        total = sum(counts)
        shares.append([c / total for c in counts])

    # 1. Four texts: grey words, and coloured words typical of a topic.
    body = []
    for k, lines in enumerate(docs):
        ox, oy = 22 + (k % 2) * 104, 14 + (k // 2) * 92
        body.append(f'<rect x="{ox}" y="{oy}" width="94" height="80" rx="4" fill="{WHITE}" stroke="{RULE2}"/>')
        for r, words in enumerate(lines):
            for x, w, t in words:
                colour = RULE2 if t is None else TOPICS[t]
                body.append(f'<rect x="{f(ox + 7 + x)}" y="{oy + 10 + r * 13}" width="{w}" height="5" rx="2.5" fill="{colour}"/>')
    svg("topics-1-texts.svg", W, H, "Illustration: four short texts drawn as lines of words; some words "
        "are coloured, one colour for each of three topics.", "\n".join(body))

    # 2. The share of each topic in each text.
    body = []
    for k, share in enumerate(shares):
        y, x = 26 + k * 42, 52
        body.append(f'<text x="44" y="{y + 12}" text-anchor="end" font-size="13" fill="{INK3}">Text {k + 1}</text>')
        for t, p in enumerate(share):
            w = p * 160
            body.append(f'<rect x="{f(x)}" y="{y}" width="{f(max(0.0, w - 2))}" height="16" fill="{TOPICS[t]}"/>')
            x += w
    svg("topics-2-mixtures.svg", W, H, "Illustration: the share of each of the three topics in each of "
        "the four texts, shown as a bar divided into colours.", "\n".join(body))


# ---------------------------------------------------------------------------
# Conference schedule: sessions on the same topic in the same time slot.
# ---------------------------------------------------------------------------
def schedule():
    rows, cols = 5, 5
    cw, ch, gap, x0, y0 = 48, 30, 6, 12, 12
    sessions = [t for t in range(5) for _ in range(5)]

    def grid(cells, name, label, mark_conflicts):
        body = []
        for r in range(rows):
            row = cells[r * cols:(r + 1) * cols]
            for c, t in enumerate(row):
                x, y = x0 + c * (cw + gap), y0 + r * (ch + gap)
                clash = mark_conflicts and row.count(t) > 1
                body.append(f'<rect x="{x}" y="{y}" width="{cw}" height="{ch}" rx="3" fill="{TOPICS[t]}"'
                            + (f' stroke="{INK}" stroke-width="2.5"' if clash else "") + "/>")
        svg(name, x0 * 2 + cols * cw + (cols - 1) * gap, y0 * 2 + rows * ch + (rows - 1) * gap, label, "\n".join(body))

    rnd = random.Random(2)
    before = sessions[:]
    rnd.shuffle(before)
    grid(before, "schedule-before.svg", "Illustration: a conference program with five parallel rooms "
         "(columns) and five time slots (rows), coloured by topic; outlined sessions share their topic "
         "with another session in the same time slot.", True)
    after = [(r + c) % 5 for r in range(rows) for c in range(cols)]
    grid(after, "schedule-after.svg", "Illustration: the same sessions rearranged so that every time "
         "slot offers five different topics.", False)


# ---------------------------------------------------------------------------
# Heaping: self-reported counts pile up on multiples of 5 and 10.
# ---------------------------------------------------------------------------
def heaping():
    vmax = 40
    shape, scale = 6.0, 3.0
    pdf = [v ** (shape - 1) * math.exp(-v / scale) if v > 0 else 0 for v in range(vmax + 1)]
    total = sum(pdf)
    under = [p / total for p in pdf]
    reported = under[:]
    for v in range(vmax + 1):
        if v % 5:
            target = 5 * round(v / 5)
            share = 0.5 if target % 10 == 0 else 0.3
            moved = under[v] * share
            reported[v] -= moved
            reported[min(vmax, target)] += moved
    W, H, base, x0, bw = 300, 220, 186, 16, 6.4
    top = max(reported)

    def bar(v, h0, h1, colour):
        y1, y0 = base - h1 / top * 160, base - h0 / top * 160
        return f'<rect x="{f(x0 + v * bw + 0.6)}" y="{f(y1)}" width="{f(bw - 1.2)}" height="{f(y0 - y1)}" fill="{colour}"/>'

    def axis():
        ticks = "".join(f'<text x="{f(x0 + v * bw + bw / 2)}" y="{base + 18}" text-anchor="middle" '
                        f'font-size="12" fill="{INK3}">{v}</text>' for v in range(0, vmax + 1, 10))
        return f'<line x1="{x0}" y1="{base}" x2="{f(x0 + (vmax + 1) * bw)}" y2="{base}" stroke="{RULE2}"/>' + ticks

    rep = [bar(v, 0, reported[v], WARM if v % 5 == 0 else "#B9B2A6") for v in range(vmax + 1)]
    svg("heaping-reported.svg", W, H, "Illustration with simulated data: a histogram of reported "
        "values with spikes at multiples of 5 and 10.", "\n".join(rep) + axis())

    sep = []
    for v in range(vmax + 1):
        sep.append(bar(v, 0, under[v], "#6FA3AC"))
        if reported[v] > under[v]:
            sep.append(bar(v, under[v], reported[v], WARM))
    svg("heaping-model.svg", W, H, "Illustration with simulated data: the underlying distribution "
        "of the values, with the excess of answers on round numbers stacked on top.", "\n".join(sep) + axis())


# ---------------------------------------------------------------------------
# PARSEG: validating a segmentation from a small sample of pixels.
# ---------------------------------------------------------------------------
def parseg():
    cols, rows, cell, x0, y0 = 30, 22, 8, 20, 12
    rnd = random.Random(13)

    def inside(c, r):
        dx, dy = (c + 0.5 - 15.5) / 10.5, (r + 0.5 - 11) / 7.2
        return dx * dx + dy * dy < 1 + 0.08 * math.sin(3 * math.atan2(dy, dx))

    def grid(fill):
        out = []
        for r in range(rows):
            for c in range(cols):
                out.append(f'<rect x="{x0 + c * cell}" y="{y0 + r * cell}" width="{cell}" height="{cell}" '
                           f'fill="{fill(c, r)}"/>')
        return "\n".join(out)

    W, H = x0 * 2 + cols * cell, y0 * 2 + rows * cell
    seed = ["#7A4A1E", "#8A5526", "#9A6430", "#6E421A"]
    back = ["#ECE7DC", "#E6E0D3", "#EFEAE0"]
    svg("parseg-1-image.svg", W, H, "Illustration: an image of a seed on a light background, "
        "made of pixels.", grid(lambda c, r: rnd.choice(seed) if inside(c, r) else rnd.choice(back)))

    # Segmentation partitioned into four subsets; random pixels drawn from one of them.
    body = [f'<rect x="{x0}" y="{y0}" width="{cols * cell}" height="{rows * cell}" fill="#E5EEEF"/>']
    body += [f'<rect x="{x0 + c * cell}" y="{y0 + r * cell}" width="{cell}" height="{cell}" fill="{ACCENT}"/>'
             for r in range(rows) for c in range(cols) if inside(c, r)]
    mid_c, mid_r = x0 + cols * cell / 2, y0 + rows * cell / 2
    body.append(f'<g stroke="{WARM}" stroke-width="2" stroke-dasharray="5 4">'
                f'<line x1="{mid_c}" y1="{y0}" x2="{mid_c}" y2="{y0 + rows * cell}"/>'
                f'<line x1="{x0}" y1="{mid_r}" x2="{x0 + cols * cell}" y2="{mid_r}"/></g>')
    rnd2 = random.Random(4)
    cells = [(c, r) for r in range(rows // 2) for c in range(cols // 2)]
    for c, r in rnd2.sample(cells, 18):
        body.append(f'<circle cx="{x0 + c * cell + cell / 2}" cy="{y0 + r * cell + cell / 2}" r="3.1" '
                    f'fill="{WHITE}" stroke="{WARM}" stroke-width="1.6"/>')
    body.append(f'<rect x="{x0}" y="{y0}" width="{cols * cell}" height="{rows * cell}" fill="none" stroke="{RULE2}"/>')
    svg("parseg-2-sample.svg", W, H, "Illustration: the segmented image is partitioned into four "
        "subsets, and a small random sample of pixels is drawn from one of them.", "\n".join(body))

    # Classifier performance against sample size: it stabilizes quickly.
    px0, py0, pw, ph = 34, 14, 230, 150
    sizes = [i / 20 for i in range(21)]
    perf = [0.62 + 0.3 * (1 - math.exp(-6 * s)) for s in sizes]
    pts = " ".join(f"{f(px0 + s * pw)},{f(py0 + ph - (p - 0.55) / 0.4 * ph)}" for s, p in zip(sizes, perf))
    full = py0 + ph - (0.92 - 0.55) / 0.4 * ph
    chosen = px0 + 0.45 * pw
    body = [f'<line x1="{px0}" y1="{py0 + ph}" x2="{px0 + pw}" y2="{py0 + ph}" stroke="{RULE2}"/>',
            f'<line x1="{px0}" y1="{py0}" x2="{px0}" y2="{py0 + ph}" stroke="{RULE2}"/>',
            f'<line x1="{px0}" y1="{f(full)}" x2="{px0 + pw}" y2="{f(full)}" stroke="{INK3}" stroke-dasharray="4 4"/>',
            f'<polyline points="{pts}" fill="none" stroke="{ACCENT}" stroke-width="2.4"/>',
            f'<line x1="{f(chosen)}" y1="{py0}" x2="{f(chosen)}" y2="{py0 + ph}" stroke="{WARM}" stroke-width="2"/>',
            f'<text x="{px0 + pw}" y="{py0 + ph + 18}" text-anchor="end" font-size="13" fill="{INK3}">pixels sampled</text>',
            f'<text x="{px0 - 8}" y="{py0 + 10}" text-anchor="end" font-size="13" fill="{INK3}" '
            f'transform="rotate(-90 {px0 - 8} {py0 + 10})">sensitivity</text>']
    svg("parseg-3-curve.svg", 280, 200, "Illustration: the sensitivity of the classifier grows with the "
        "number of sampled pixels and stabilizes; the smallest sufficient sample size is marked.", "\n".join(body))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    oblique()
    nessc()
    clusters()
    topics()
    schedule()
    heaping()
    parseg()
    for name in sorted(os.listdir(OUT)):
        print(f"{os.path.getsize(os.path.join(OUT, name)):6d}  assets/img/stories/{name}")
