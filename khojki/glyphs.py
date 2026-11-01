"""Stage B: line image -> glyph boxes (atoms), left to right.

Connected components; marks (dots, strokes) joined to the nearest letter; word separators found as
a pair of small dots. A letter may come out as 2-3 boxes (SA, a split-off AA upright, a double danda):
that is allowed, because stage C tries joining neighbouring boxes. Two glyphs in one box is not, because
nothing later can split it. So when in doubt this stage splits rather than merges.

Section marks and abbreviation signs are found by shape first and come out as 'mark' boxes, already read (log 98).

Ported from gt/segment.py (which made the ground-truth boxes and stays frozen), with the separator fix.
"""
import cv2
import numpy as np

from khojki.lines import binarise

SECTION, DOUBLE_SECTION, ABBREVIATION = 0x1123B, 0x1123C, 0x1123D
MAX_CONTACTS = 2  # contacts between ring and letter: 1 finds 19% of pasted rings, 2 finds 71% with no false alarms, any finds 100% with 1 (dev)


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


def ring_in(mask, tall, line_h, y_off=0):
    """An abbreviation sign (a small ring) in one piece's ink (uint8 0/1, cropped).
    -> (ring mask, 'alone' | 'attached') or None.

    A round hole 0.16-0.30 letter heights across, its ring under 0.75 letter heights, centred at 35-85% of the
    line height. Joined to a letter it still counts when the ring is the piece's right end, what's left is
    letter-sized, and the two touch in at most MAX_CONTACTS places. Rules from the shapes (Pandey L2/11-021
    sections 4.11-4.14, the two rings on p10 l6), not fit to a score."""
    cs, hier = cv2.findContours(mask, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    if hier is None:
        return None
    for c, h in zip(cs, hier[0]):
        if h[3] < 0:
            continue                                     # an outer edge, not a hole
        x, y, w, hh = cv2.boundingRect(c)
        if not (0.16 * tall <= max(w, hh) <= 0.30 * tall and 0.6 <= w / hh <= 1.6
                and cv2.contourArea(c) >= 0.3 * w * hh):     # heavy print leaves a ragged hole (p10 l6: 35% filled)
            continue                                     # not a small round hole
        hole = np.zeros_like(mask)
        cv2.drawContours(hole, [c], -1, 1, -1)
        r = max(2, round(0.2 * tall))
        ring = mask & cv2.dilate(hole, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * r + 1, 2 * r + 1)))
        ys, xs = np.nonzero(ring)
        if not len(ys) or np.ptp(ys) + 1 > 0.75 * tall or not 0.35 <= (y_off + ys.mean()) / line_h <= 0.85:
            continue
        rest = mask & ~ring.astype(bool)
        rys, rxs = np.nonzero(rest)
        if rest.sum() <= 0.15 * mask.sum():
            if max(mask.shape) > 0.75 * tall:
                continue                                 # letter-sized: VA's round loop, not a sign
            return ring, "alone"
        # a gap inside a curved stroke (heavy ink) has the stroke running in and out: two contacts or more
        contacts = cv2.connectedComponents((cv2.dilate(ring, np.ones((3, 3), np.uint8)) & rest).astype(np.uint8))[0] - 1
        if (xs.max() >= mask.shape[1] - 1 - 0.15 * tall and len(rys) and np.ptp(rys) + 1 >= 0.6 * tall
                and contacts <= MAX_CONTACTS):
            return ring, "attached"
    return None


def marks(comps, labels, tall, line_h):
    """Section marks and abbreviation signs. -> (mark boxes, the other components).

    Without this a section rule is thin, so it joined the nearest letter as a small mark (p11 l6: the double
    section mark and the digit before it became one 88 px box). A section mark is at least 1.5 letter heights
    wide and at most 0.35 tall, mid-line; two stacked are a double section mark. An attached ring is cut off its
    letter: its pixels get a label id of their own in `labels` (changed in place)."""
    rules = [c for c in comps if c["x1"] - c["x0"] >= 1.5 * tall and c["y1"] - c["y0"] <= 0.35 * tall
             and 0.2 * line_h <= (c["y0"] + c["y1"]) / 2 <= 0.8 * line_h]
    out, used = [], set()
    for i, a in enumerate(rules):
        if i in used:
            continue
        pair = [j for j, b in enumerate(rules) if j != i and j not in used
                and min(a["x1"], b["x1"]) - max(a["x0"], b["x0"]) >= 0.5 * min(a["x1"] - a["x0"], b["x1"] - b["x0"])
                and abs((a["y0"] + a["y1"]) - (b["y0"] + b["y1"])) / 2 <= 0.7 * tall]
        group = [a] + [rules[j] for j in pair[:1]]
        used |= {i, *pair[:1]}
        out.append(dict(x0=min(g["x0"] for g in group), x1=max(g["x1"] for g in group), y0=min(g["y0"] for g in group),
                        y1=max(g["y1"] for g in group), kind="mark", cps=(DOUBLE_SECTION if pair else SECTION,),
                        ids=[i for g in group for i in g["ids"]]))
    rule_ids = {i for m in out for i in m["ids"]}
    rest = []
    for c in comps:
        if c["ids"][0] in rule_ids:
            continue
        crop = labels[c["y0"]:c["y1"], c["x0"]:c["x1"]]
        own = np.isin(crop, c["ids"])
        hit = ring_in(own.astype(np.uint8), tall, line_h, c["y0"])
        if not hit:
            rest.append(c)
            continue
        ring, how = hit
        ys, xs = np.nonzero(ring)
        box = dict(x0=c["x0"] + int(xs.min()), x1=c["x0"] + int(xs.max()) + 1, y0=c["y0"] + int(ys.min()),
                   y1=c["y0"] + int(ys.max()) + 1, kind="mark", cps=(ABBREVIATION,))
        if how == "alone":
            out.append(dict(box, ids=list(c["ids"])))
            continue
        new = int(labels.max()) + 1
        crop[ring.astype(bool)] = new
        out.append(dict(box, ids=[new]))
        ly, lx = np.nonzero(own & (crop != new))
        rest.append(dict(c, x0=c["x0"] + int(lx.min()), x1=c["x0"] + int(lx.max()) + 1,
                         y0=c["y0"] + int(ly.min()), y1=c["y0"] + int(ly.max()) + 1))
    return out, rest


def glyph_boxes(gray, method="otsu"):
    """Return [[x0, x1, y0, y1, kind], ...] left to right. kind: 'glyph', 'sep' or 'mark'."""
    return glyph_atoms(gray, method)["boxes"]


def glyph_atoms(gray, method="otsu"):
    """Boxes plus what's needed to cut out each box's own ink:
    {'boxes': [[x0, x1, y0, y1, kind]], 'members': [[label ids]], 'labels': label image, 'tall': median letter height,
     'cps': per box, the code points of a mark box (None for the others)}."""
    ink = binarise(gray, method)
    comps, labels = components(ink)
    if not comps:
        return dict(boxes=[], members=[], labels=labels, tall=0.0, cps=[])
    H, W = gray.shape
    # typical letter height; pieces cut by the crop's top/bottom edge belong to neighbouring lines (a taller
    # crop holds more of them) and would shift it, which changed splits and readings (log 76)
    whole = [c["y1"] - c["y0"] for c in comps if c["area"] > 80 and c["y0"] > 0 and c["y1"] < H]
    tall = float(np.median(whole or [c["y1"] - c["y0"] for c in comps if c["area"] > 80] or [H / 2]))
    # the printed frame: a thin rule, full height, touching either side, or cut by the top/bottom edge and taller
    # than 1.5 letters (p11 l6: a broken rule 6 px in from the side, 0.6 H tall, log 83). On pages 9-11 that last
    # case only ever fires within 25 px of a side.
    rule = lambda c: (c["x1"] - c["x0"]) < 0.2 * (c["y1"] - c["y0"]) and (
        c["y1"] - c["y0"] >= 0.85 * H or c["x1"] >= W - 3 or c["x0"] <= 2
        or (c["y0"] == 0 or c["y1"] >= H) and c["y1"] - c["y0"] >= 1.5 * tall)
    # ink cut by the crop's top or bottom edge belongs to the neighbouring line (stage A grows lines into the
    # gaps, so its crops hold their descenders and marks); joined to a letter here it changed the reading (log 76).
    # A real glyph can graze the edge of a tight crop (GT crops have 6 px padding), so only pieces centred in the
    # outer quarter of the crop count as the neighbour's.
    neighbour = lambda c: (c["y0"] == 0 or c["y1"] >= H) and not 0.25 * H <= (c["y0"] + c["y1"]) / 2 <= 0.75 * H
    comps = [c for c in comps if not rule(c) and not neighbour(c)]
    found, comps = marks(comps, labels, tall, H)
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

    out = sorted(merged + seps + found, key=lambda c: c["x0"])
    return dict(boxes=[[int(c["x0"]), int(c["x1"]), int(c["y0"]), int(c["y1"]), c["kind"]] for c in out],
                members=[c["ids"] for c in out], labels=labels, tall=tall, cps=[c.get("cps") for c in out])
