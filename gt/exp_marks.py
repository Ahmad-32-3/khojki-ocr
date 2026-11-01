"""Checks for the section marks and abbreviation signs that stage B finds by shape (khojki/glyphs.py, log 98).

usage: python -X utf8 gt/exp_marks.py [--pages]      --pages also runs on whole pages 9-11 and saves crops to look at

The gap before: a section rule is thin, so stage B treats it as a small mark and joins it to the nearest letter
(p11 l6: the double section mark and the digit before it became one 88 px box). An abbreviation sign is a small
ring; when it touches the letter before it, nothing can split it off again.
  SECTION MARK (U+1123B)         a piece at least 1.5 letter heights wide and at most 0.35 tall, in the middle of
                                 the line. Two of them stacked (overlapping in x, less than 0.7 letter heights
                                 apart) are a DOUBLE SECTION MARK (U+1123C).
  ABBREVIATION SIGN (U+1123D)    a round hole 0.16-0.30 letter heights across, with the ink ring around it under
                                 0.75 letter heights, centred at 35-85% of the line height. Alone it is a sign.
                                 Joined to a letter it is still a sign when the ring is the piece's right end,
                                 what's left is letter-sized (at least 0.6 letter heights tall) and touches the ring
                                 in at most two places: the ring is cut off and the rest is read as the letter.
Rules come from the shapes (Pandey L2/11-021 sections 4.11-4.14, and the two marks measured on p10 l6 and p11 l6),
not fit to any score. Checks: the two test lines (the only labelled marks), false alarms on the 9 dev lines,
real rings pasted onto every real dev glyph so they touch (the attached case), and whole pages 9-11 by eye.
"""
import json, sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import GT_FILE, atoms_in, load, normalise, unit_mask  # noqa: E402
from khojki.glyphs import ABBREVIATION, DOUBLE_SECTION, SECTION, components, glyph_atoms, ring_in  # noqa: E402
from khojki.labels import canonical, from_hex, name, parts  # noqa: E402
from khojki.lines import binarise  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows  # noqa: E402


def find_marks(gray):
    """-> list of {'cps', 'x0', 'x1', 'y0', 'y1'} in line coordinates, left to right (stage B's mark boxes)."""
    atoms = glyph_atoms(gray)
    return [dict(cps=c, x0=b[0], x1=b[1], y0=b[2], y1=b[3]) for b, c in zip(atoms["boxes"], atoms["cps"]) if c]


def gt_lines(split=None):
    gt = json.loads(GT_FILE.read_text(encoding="utf-8"))
    return [l for l in gt["lines"] if split is None or l.get("split", "dev") == split]


def overlap(a, b):
    return max(0, min(a[1], b[1]) - max(a[0], b[0])) / max(1, min(a[1] - a[0], b[1] - b[0]))


def check_labelled():
    print("Labelled marks (both on the blind test lines; the rules were not fit to them):")
    found = missed = wrong = 0
    for line in gt_lines("test"):
        gray = cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE)
        marks = find_marks(gray)
        truth = [u for u in line["units"] if u["status"] == "ok" and set(from_hex(u["cps"])) & {SECTION, DOUBLE_SECTION, ABBREVIATION}]
        for u in truth:
            want = tuple(c for c in from_hex(u["cps"]) if c in (SECTION, DOUBLE_SECTION, ABBREVIATION))
            hit = [m for m in marks if m["cps"] == want and overlap((m["x0"], m["x1"]), u["bbox"][:2]) > 0.5]
            found += bool(hit); missed += not hit
            print(f"  {line['file'][6:13]} {name(want):20} x {u['bbox'][0]}-{u['bbox'][1]}: "
                  + (f"found at x {hit[0]['x0']}-{hit[0]['x1']}" if hit else "MISSED"))
        for m in marks:
            if not any(overlap((m["x0"], m["x1"]), u["bbox"][:2]) > 0.5 for u in truth):
                wrong += 1
                print(f"  {line['file'][6:13]} false alarm: {name(m['cps'])} at x {m['x0']}-{m['x1']}")
    print(f"  found {found} of {found + missed}, false alarms {wrong}")
    fa = Counter()
    for line in gt_lines("dev"):
        for m in find_marks(cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE)):
            fa[name(m["cps"])] += 1
            print(f"  dev {line['file'][6:13]}: {name(m['cps'])} at x {m['x0']}-{m['x1']}")
    print(f"False alarms on the 9 dev lines (they hold no labelled marks): {sum(fa.values())} {dict(fa)}")


def check_attached():
    """Real rings from p10 l6 pasted so they touch every real dev glyph (the attached case), and the same glyphs
    without a ring (false alarms). For each: is the ring found, and is the letter left over still read right?"""
    gray = cv2.imread(str(ROOT / "gt" / "lines" / "p10_l06.png"), cv2.IMREAD_GRAYSCALE)
    ink = binarise(gray)
    comps, labels = components(ink)
    rings = [np.isin(labels[c["y0"]:c["y1"], c["x0"]:c["x1"]], c["ids"]).astype(np.uint8)
             for c in comps if c["x0"] in (295, 315)]
    bank = load()
    stats = Counter()
    for line in gt_lines("dev"):
        gray = cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE)
        atoms = glyph_atoms(gray)
        tall, H = atoms["tall"], gray.shape[0]
        index = R.Index(bank, "pixels", bank_rows(bank, {line["file"]}))
        for u in line["units"]:
            idx = atoms_in(u, atoms)
            if u["status"] != "ok" or not idx or u["cps"] == ["U+1123A"]:
                continue
            truth = parts(canonical(from_hex(u["cps"])))[0]
            m = (unit_mask(atoms, idx) > 0).astype(np.uint8)
            stats["glyphs"] += 1
            ys, xs = np.nonzero(m)
            m = m[:, xs.min():xs.max() + 1]
            stats["false alarm"] += bool(any(ring_in(p, tall, H, 0) for p in pieces(m)))
            ring = cv2.resize(rings[stats["glyphs"] % 2], None, fx=tall / 27, fy=tall / 27, interpolation=cv2.INTER_NEAREST)
            # the ring goes at the height of the letter's rightmost ink (kept to the middle of the line, where the
            # signs sit), then slides left until letter and ring are one piece
            ry = np.nonzero(m[:, -3:].any(1))[0]
            cy = int(np.clip(ry.mean() if len(ry) else 0.6 * H, 0.4 * H, 0.8 * H))
            y = max(0, min(H - ring.shape[0], cy - ring.shape[0] // 2))
            n0 = cv2.connectedComponents(m, connectivity=8)[0]
            touching = False
            for shift in range(0, ring.shape[1] // 2):
                big = np.zeros((H, m.shape[1] + ring.shape[1]), np.uint8)
                big[:, :m.shape[1]] = m
                x = m.shape[1] - shift
                big[y:y + ring.shape[0], x:x + ring.shape[1]] |= ring
                big = big[:, :x + ring.shape[1]]
                if cv2.connectedComponents(big, connectivity=8)[0] == n0:   # the ring joined a piece
                    touching = True
                    break
            if not touching:
                stats["could not touch"] += 1
                continue
            stats["attached"] += 1
            read = lambda mk: R.part_scores(*index.votes(*normalise(mk * 255, tall)))["letter"][0][0]
            stats["read right, no ring"] += read(m) == truth
            stats["read right, ring attached, no detector"] += read(big) == truth
            hit = ring_in(big, tall, H, 0)
            if hit and hit[1] == "attached":
                stats["ring found"] += 1
                rest = big & ~hit[0].astype(bool)
                stats["read right, ring cut off"] += read(rest.astype(np.uint8)) == truth
            else:
                stats["read right, ring cut off"] += read(big) == truth
    g, a = stats["glyphs"], stats["attached"]
    print(f"\nAttached rings (real rings from p10 l6 pasted onto {a} real dev glyphs so they touch; {stats['could not touch']} could not be made to touch):")
    print(f"  ring found as an attached ABBREVIATION SIGN: {stats['ring found']} of {a} ({stats['ring found'] / a:.1%})")
    print(f"  letter read right: no ring {stats['read right, no ring']}, ring attached and no detector "
          f"{stats['read right, ring attached, no detector']}, ring cut off by the detector {stats['read right, ring cut off']} (of {a})")
    print(f"  false alarms on the same {g} glyphs without a ring: {stats['false alarm']} ({stats['false alarm'] / g:.1%})")


def pieces(mask):
    """Each connected piece of a mask, as its own full-size mask."""
    n, lab = cv2.connectedComponents(mask, connectivity=8)
    return [(lab == k).astype(np.uint8) for k in range(1, n)]


def check_pages(out_dir):
    from khojki.lines import find_lines
    from khojki.pipeline import pdf_page
    pdf = ROOT / "khojki-scans" / "sample_khojki_script_vatiations.pdf"
    crops = []
    print("\nWhole pages 9-11 (unlabelled; every hit saved for checking by eye):")
    for page in (9, 10, 11):
        gray = pdf_page(pdf, page)
        hits = Counter()
        for x0, y0, x1, y1 in find_lines(gray):
            for m in find_marks(gray[y0:y1, x0:x1]):
                hits[name(m["cps"])] += 1
                c = gray[y0:y1, x0 + max(0, m["x0"] - 30):x0 + m["x1"] + 30]
                crops.append(cv2.resize(c, (int(c.shape[1] * 60 / c.shape[0]), 60)))
        print(f"  page {page}: {dict(hits)}")
    if crops:
        rows, row, wsum = [], [], 0
        for c in crops:
            if wsum + c.shape[1] > 900 and row:
                rows.append(np.hstack(row + [np.full((60, 900 - wsum), 255, np.uint8)])); row, wsum = [], 0
            row.append(np.pad(c, ((0, 0), (0, 6)), constant_values=255)); wsum += c.shape[1] + 6
        rows.append(np.hstack(row + [np.full((60, max(0, 900 - wsum)), 255, np.uint8)])[:, :900])
        cv2.imwrite(str(Path(out_dir) / "marks_found.png"), np.vstack([r[:, :900] for r in rows]))


if __name__ == "__main__":
    check_labelled()
    check_attached()
    if "--pages" in sys.argv:
        check_pages(sys.argv[sys.argv.index("--pages") + 1] if len(sys.argv) > sys.argv.index("--pages") + 1 else ".")
