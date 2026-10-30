"""Score stage A (line finding) against gt/lines_gt.json for each binarisation method.

usage: python -X utf8 gt/eval_lines.py [--overlay DIR]
A text line is right when exactly one band contains its centre and that band holds no other centre.
"""
import json, sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from khojki.lines import find_lines  # noqa: E402

METHODS = ("meanstd", "otsu", "sauvola")


def score(found, text, skip):
    """Counts of right / missed / merged text lines, plus kept non-text and stray bands."""
    inside = lambda y, b: b[1] <= y <= b[3]
    per_band = [[y for y in text if inside(y, b)] for b in found]
    right = sum(1 for y in text if sum(inside(y, b) for b in found) == 1
                and len(next(c for c in per_band if y in c)) == 1)
    missed = sum(1 for y in text if not any(inside(y, b) for b in found))
    merged = sum(len(c) for c in per_band if len(c) > 1)
    empty = [b for b, c in zip(found, per_band) if not c]
    nontext = sum(1 for b in empty if any(inside(s["y"], b) for s in skip))
    return dict(right=right, missed=missed, merged=merged, nontext_kept=nontext, stray=len(empty) - nontext)


def main(overlay_dir=None):
    gt = json.loads((ROOT / "gt" / "lines_gt.json").read_text(encoding="utf-8"))
    results = {}
    for page in ("p09", "p10", "p11"):
        gray = cv2.imread(str(ROOT / "data" / "pages" / f"{page}.png"), cv2.IMREAD_GRAYSCALE)
        for m in METHODS:
            found = find_lines(gray, m)
            results[(page, m)] = s = score(found, gt[page]["text"], gt[page]["skip"])
            print(f"{page} {m:8} bands={len(found):2} of {len(gt[page]['text'])} lines  {s}")
            if overlay_dir:
                img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                for x0, y0, x1, y1 in found:
                    cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 255), 2)
                for y in gt[page]["text"]:
                    cv2.line(img, (0, y), (30, y), (0, 160, 0), 3)
                cv2.imwrite(str(Path(overlay_dir) / f"lines_{page}_{m}.png"), img)
    return results


if __name__ == "__main__":
    main(sys.argv[2] if len(sys.argv) > 2 and sys.argv[1] == "--overlay" else None)
