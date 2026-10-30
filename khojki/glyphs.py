"""Stage B: line image -> glyph boxes (atoms), left to right.

Connected components; marks (dots, strokes) joined to the nearest letter; word separators found as
a pair of small dots. A letter may come out as 2-3 boxes (SA, a split-off AA upright, a double danda):
that is allowed, because stage C tries joining neighbouring boxes. Two glyphs in one box is not, because
nothing later can split it. So when in doubt this stage splits rather than merges.

Ported from gt/segment.py (which made the ground-truth boxes and stays frozen), with the separator fix.
"""
import cv2
import numpy as np

from khojki.lines import binarise


def components(ink, min_area=6):
    """Components as dicts; `ids` holds the label id(s) in the returned label image, so a box knows its own ink."""
    n, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    comps = [dict(x0=x, x1=x + w, y0=y, y1=y + h, area=a, ids=[i]) for i, (x, y, w, h, a) in enumerate(stats) if i and a >= min_area]
    return comps, labels


def _xov(a, b):
    return min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])


def separators(small, tall, line_h):
    """Pair small dots into word separators. Returns (pairs as boxes, indices used).

    The two dots are stacked but slanted: the lower one sits 4-7 px to the right (log 63), so the
    test is on centre distance, not on x-overlap. Dots in the top 30% of the line are marks
    (anusvara, nukta), never separators. Dot size < 0.375 x letter height: on the 6 GT lines, 0.3 misses
    2 separators and 0.45 takes a mark for one (Sauvola); 0.35-0.4 is clean (log 63).
    """
    dot = lambda c: c["y1"] - c["y0"] < 0.375 * tall and c["x1"] - c["x0"] < 0.375 * tall and c["y0"] > 0.3 * line_h
    cx = lambda c: (c["x0"] + c["x1"]) / 2
    cy = lambda c: (c["y0"] + c["y1"]) / 2
    used, seps = set(), []
    order = sorted(range(len(small)), key=lambda i: cx(small[i]))
    for i in order:
        if i in used or not dot(small[i]):
            continue
        a = small[i]
        best = None
        for j in order:
            b = small[j]
            if j == i or j in used or not dot(b):
                continue
            dx, dy = abs(cx(a) - cx(b)), abs(cy(a) - cy(b))
            if dx <= 0.3 * tall and 0.2 * tall <= dy <= 0.6 * tall and (best is None or dx < best[0]):
                best = (dx, j)
        if best:
            b = small[best[1]]
            used |= {i, best[1]}
            seps.append(dict(x0=min(a["x0"], b["x0"]), x1=max(a["x1"], b["x1"]),
                             y0=min(a["y0"], b["y0"]), y1=max(a["y1"], b["y1"]), kind="sep", ids=a["ids"] + b["ids"]))
    return seps, used


def glyph_boxes(gray, method="otsu"):
    """Return [[x0, x1, y0, y1, kind], ...] left to right. kind: 'glyph' or 'sep'."""
    return glyph_atoms(gray, method)["boxes"]


def glyph_atoms(gray, method="otsu"):
    """Boxes plus what's needed to cut out each box's own ink:
    {'boxes': [[x0, x1, y0, y1, kind]], 'members': [[label ids]], 'labels': label image, 'tall': median letter height}."""
    ink = binarise(gray, method)
    comps, labels = components(ink)
    if not comps:
        return dict(boxes=[], members=[], labels=labels, tall=0.0)
    H, W = gray.shape
    tall = float(np.median([c["y1"] - c["y0"] for c in comps if c["area"] > 80] or [H / 2]))
    # the printed frame: a thin rule, full height or touching the right edge
    rule = lambda c: (c["x1"] - c["x0"]) < 0.2 * (c["y1"] - c["y0"]) and (c["y1"] - c["y0"] >= 0.85 * H or c["x1"] >= W - 3)
    comps = [c for c in comps if not rule(c)]
    # ponytail: fixed size cut between letters and marks; revisit for other pages / resolutions
    big = sorted((c for c in comps if c["y1"] - c["y0"] >= 0.45 * tall), key=lambda c: c["x0"])
    small = [c for c in comps if c["y1"] - c["y0"] < 0.45 * tall]

    # a letter broken into pieces: merge big components that mostly overlap in x
    merged = []
    for c in big:
        if merged and _xov(merged[-1], c) > 0.6 * min(c["x1"] - c["x0"], merged[-1]["x1"] - merged[-1]["x0"]):
            m = merged[-1]
            m.update(x0=min(m["x0"], c["x0"]), x1=max(m["x1"], c["x1"]), y0=min(m["y0"], c["y0"]), y1=max(m["y1"], c["y1"]), ids=m["ids"] + c["ids"])
        else:
            merged.append(dict(c, kind="glyph", ids=list(c["ids"])))

    seps, used = separators(small, tall, H)

    # every other mark (dots, vowel strokes) joins the letter nearest in x
    for i, s in enumerate(small):
        if i in used or not merged:
            continue
        cx = (s["x0"] + s["x1"]) / 2
        g = min(merged, key=lambda g: 0 if g["x0"] <= cx <= g["x1"] else min(abs(cx - g["x0"]), abs(cx - g["x1"])))
        g.update(x0=min(g["x0"], s["x0"]), x1=max(g["x1"], s["x1"]), y0=min(g["y0"], s["y0"]), y1=max(g["y1"], s["y1"]), ids=g["ids"] + s["ids"])

    out = sorted(merged + seps, key=lambda c: c["x0"])
    return dict(boxes=[[int(c["x0"]), int(c["x1"]), int(c["y0"]), int(c["y1"]), c["kind"]] for c in out],
                members=[c["ids"] for c in out], labels=labels, tall=tall)
