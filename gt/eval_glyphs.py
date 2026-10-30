"""Score stage B (glyph boxes) against ground truth v1.

usage: python -X utf8 gt/eval_glyphs.py [--old | --pipeline]
  default     stage B on the ground-truth line crops (stage A taken as perfect)
  --old       the frozen gt/segment.py on the same crops, as a baseline
  --pipeline  stage A + B: lines found by khojki.lines on the page, boxes shifted into GT crop coordinates

Per ground-truth unit, count predicted boxes of the matching kind whose centre falls in its x-range:
ok = 1, split = 2+ (recoverable: stage C tries joining neighbours), missed = 0. A predicted box holding
the centres of 2+ units of the same kind is a merge (not recoverable). A sep box outside every separator
unit is a false separator. Separator units (U+1123A) match 'sep' boxes, all others 'glyph' boxes.
"""
import json, sys
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.glyphs import glyph_boxes  # noqa: E402
from khojki.lines import find_lines  # noqa: E402
from prep_gt import BODY_BOX, line_bands  # noqa: E402

SEP = ["U+1123A"]


def score(units, boxes):
    """units: [{'bbox': [x0, x1, ...], 'cps': [...] or None}]; boxes: [[x0, x1, y0, y1, kind]]."""
    kind = lambda u: "sep" if u["cps"] == SEP else "glyph"
    centre = lambda b: (b[0] + b[1]) / 2
    c = Counter()
    for u in units:
        n = sum(1 for b in boxes if b[4] == kind(u) and u["bbox"][0] <= centre(b) < u["bbox"][1])
        c[(kind(u), "ok" if n == 1 else "missed" if n == 0 else "split")] += 1
    for b in boxes:
        same = {tuple(u["bbox"][:2]) for u in units if kind(u) == b[4] and b[0] <= (u["bbox"][0] + u["bbox"][1]) / 2 < b[1]}
        if len(same) > 1:
            c[(b[4], "merge")] += 1
        if b[4] == "sep" and not any(kind(u) == "sep" and u["bbox"][0] <= centre(b) < u["bbox"][1] for u in units):
            c[("sep", "false")] += 1  # a mark taken for a separator
    return c


def gt_crop_origin(file):
    """Page (x, y) of a GT line crop's top-left, recomputed the way prep_gt.py made it (checked by template match, log 64)."""
    page_no, n = int(file[7:9]), int(file[11:13])
    page = cv2.imread(str(ROOT / "data" / "pages" / f"p{page_no:02d}.png"), cv2.IMREAD_GRAYSCALE)
    h, w = page.shape
    x0, y0, x1, y1 = (int(f * s) for f, s in zip(BODY_BOX, (w, h, w, h)))
    a, _ = line_bands(page[y0:y1, x0:x1].astype(float))[n - 1]
    return page, x0, y0 + max(0, a - 6)


def pipeline_boxes(file, method):
    """Boxes from stage A's line on the page, moved into the GT crop's coordinates."""
    page, gx, gy = gt_crop_origin(file)
    gh = cv2.imread(str(ROOT / "gt" / file), cv2.IMREAD_GRAYSCALE).shape[0]
    mid = gy + gh / 2
    lx0, ly0, lx1, ly1 = next(l for l in find_lines(page, method) if l[1] <= mid < l[3])
    boxes = glyph_boxes(page[ly0:ly1, lx0:lx1], method)
    return [[x0 + lx0 - gx, x1 + lx0 - gx, y0 + ly0 - gy, y1 + ly0 - gy, k] for x0, x1, y0, y1, k in boxes]


def main(mode="crops"):
    gt = json.loads((ROOT / "gt" / "gt_v1.json").read_text(encoding="utf-8"))
    from segment import glyph_boxes as old_boxes
    results = {}
    for method in (["otsu"] if mode == "old" else ["otsu", "sauvola"]):
        total = Counter()
        for line in gt["lines"]:
            path = ROOT / "gt" / line["file"]
            if mode == "old":
                boxes = old_boxes(path)
            elif mode == "pipeline":
                boxes = pipeline_boxes(line["file"], method)
            else:
                boxes = glyph_boxes(cv2.imread(str(path), cv2.IMREAD_GRAYSCALE), method)
            total += score(line["units"], boxes)
        results[method] = total
        print(f"{mode:9} {method:8}", dict(sorted(total.items())))
    return results


if __name__ == "__main__":
    main("old" if "--old" in sys.argv else "pipeline" if "--pipeline" in sys.argv else "crops")
