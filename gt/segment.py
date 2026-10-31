"""Split a line crop into glyph boxes: connected components, marks merged into their letter.

usage: python -X utf8 gt/segment.py gt/lines/p09_l01.png [...]   -> prints boxes, writes gt/overlays/*.png
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np


def glyph_boxes(path):
    """Return [[x0, x1, y0, y1, kind], ...] left to right. kind: 'glyph' or 'sep' (the two-dot word separator)."""
    gray = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, _, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    comps = [dict(x0=x, x1=x + w, y0=y, y1=y + h, area=a) for x, y, w, h, a in stats[1:] if a >= 6]  # drop speckle
    tall = np.median([c["y1"] - c["y0"] for c in comps if c["area"] > 80])
    # the printed frame: a thin rule taller than any letter
    H, W = gray.shape
    rule = lambda c: (c["x1"] - c["x0"]) < 0.2 * (c["y1"] - c["y0"]) and (c["y1"] - c["y0"] >= 0.85 * H or c["x1"] >= W - 3)
    comps = [c for c in comps if not rule(c)]
    # ponytail: fixed size cut between letters and marks; revisit for other pages / resolutions
    big = [c for c in comps if c["y1"] - c["y0"] >= 0.45 * tall]
    small = [c for c in comps if c not in big]

    def xov(a, b):
        return min(a["x1"], b["x1"]) - max(a["x0"], b["x0"])

    # a letter broken into pieces: merge big components that mostly overlap in x
    big.sort(key=lambda c: c["x0"])
    merged = []
    for c in big:
        if merged and xov(merged[-1], c) > 0.6 * min(c["x1"] - c["x0"], merged[-1]["x1"] - merged[-1]["x0"]):
            m = merged[-1]
            m.update(x0=min(m["x0"], c["x0"]), x1=max(m["x1"], c["x1"]), y0=min(m["y0"], c["y0"]), y1=max(m["y1"], c["y1"]))
        else:
            merged.append(dict(c, kind="glyph"))

    # separators: two similar dots stacked vertically inside the text body (marks above letters sit higher)
    h = gray.shape[0]
    dot = lambda c: c["y1"] - c["y0"] < 0.3 * tall and c["x1"] - c["x0"] < 0.3 * tall and c["y0"] > 0.3 * h
    used = set()
    seps = []
    for i, a in enumerate(small):
        for j, b in enumerate(small):
            if i < j and i not in used and j not in used and dot(a) and dot(b) and xov(a, b) > 0 \
                    and abs(a["y0"] - b["y0"]) > 0.15 * tall:
                seps.append(dict(x0=min(a["x0"], b["x0"]), x1=max(a["x1"], b["x1"]), y0=min(a["y0"], b["y0"]), y1=max(a["y1"], b["y1"]), kind="sep"))
                used |= {i, j}

    # every other mark (dots, vowel strokes) joins the letter nearest in x
    for i, s in enumerate(small):
        if i in used:
            continue
        cx = (s["x0"] + s["x1"]) / 2
        g = min(merged, key=lambda g: 0 if g["x0"] <= cx <= g["x1"] else min(abs(cx - g["x0"]), abs(cx - g["x1"])))
        g.update(x0=min(g["x0"], s["x0"]), x1=max(g["x1"], s["x1"]), y0=min(g["y0"], s["y0"]), y1=max(g["y1"], s["y1"]))

    out = sorted(merged + seps, key=lambda c: c["x0"])
    return [[int(c["x0"]), int(c["x1"]), int(c["y0"]), int(c["y1"]), c["kind"]] for c in out]


def boxes_for(lat, root=Path(__file__).parent):
    """Boxes a lattice's span indices refer to. Lines prepared before chunk 7 used this file's segmenter
    (frozen, so their indices stay valid); lines from gt/prep_lines.py store the pipeline's boxes from when they
    were prepared, so a later stage B change can't shift the indices under a review (log 83)."""
    if "boxes" in lat:
        return lat["boxes"]
    if lat.get("segmenter") == "pipeline":
        import sys
        sys.path.insert(0, str(root.parent))
        from khojki.glyphs import glyph_boxes as pipeline_boxes
        return pipeline_boxes(cv2.imread(str(root / lat["file"]), cv2.IMREAD_GRAYSCALE))
    return glyph_boxes(root / lat["file"])


def overlay(path, boxes, out):
    img = cv2.imread(str(path))
    img = cv2.resize(img, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    for k, (x0, x1, y0, y1, kind) in enumerate(boxes):
        col = (0, 140, 255) if kind == "sep" else (200, 60, 0)
        cv2.rectangle(img, (x0 * 3, y0 * 3), (x1 * 3, y1 * 3), col, 2)
        cv2.putText(img, str(k), (x0 * 3 + 2, 22 if k % 2 else img.shape[0] - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.7, col, 2)
    cv2.imwrite(str(out), img)


if __name__ == "__main__":
    od = Path(__file__).parent / "overlays"
    od.mkdir(exist_ok=True)
    for p in map(Path, sys.argv[1:]):
        b = glyph_boxes(p)
        overlay(p, b, od / p.name)
        print(p.name, len(b), "boxes,", sum(k == "sep" for *_, k in b), "separators")
        print(json.dumps(b))
