"""Two other ways to tell look-alike letters apart, after the font-trained guards failed on the print (log 98).

usage: python -X utf8 gt/exp_similar.py [--test]

Both act only when today's pixel matcher's best letter is in a problem group (gt/exp_guards.py), and both may only
pick among the group letters in the matcher's top 3, so they can't invent a letter the matcher never considered.
  specialist     A linear SVM on the guard measurements (thinned 6 x 6 ink grid, width / height, holes, stroke
                 ends, left 40%), trained on the book's own glyphs: the real examples of the group's letters from
                 the other dev lines (leave one line out), plus the font drawings at a tenth of the weight. The
                 research lead: confusable-pair classifiers work when trained on the document itself, because each
                 old print has its own shapes (arXiv 0907.0418; IEICE PRMU2008-208).
  shape context  Belongie, Malik & Puzicha (2002): 60 outline points per glyph, each described by a log-polar
                 histogram of where the other points lie; two glyphs are matched point to point (Hungarian method)
                 and the mean matching cost is their distance. Each candidate letter's score is its nearest real
                 or font example. It tolerates shape variation that pixel overlap punishes.
Scored as gt/exp_vision.py: the 105 dev glyphs, each line held out, letter top-1, exact McNemar vs today.
"""
import sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load, normalise, unit_mask  # noqa: E402
from khojki.labels import NUKTA, SEPARATOR, name, parts  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows, lines_and_truth  # noqa: E402
from exp_guards import GROUPS, measure, prf  # noqa: E402
from exp_vision import mcnemar  # noqa: E402

GROUP_OF = {c: g for g, cs in GROUPS.items() for c in cs}
N_POINTS, R_BINS, A_BINS = 60, 5, 12


# ---------- shape context ----------

def outline_points(img, n=N_POINTS):
    edges = cv2.Canny((img > 127).astype(np.uint8) * 255, 50, 150)
    ys, xs = np.nonzero(edges)
    if len(xs) < 3:
        return np.zeros((1, 2), np.float32)
    pts = np.stack([xs, ys], 1).astype(np.float32)
    idx = np.linspace(0, len(pts) - 1, min(n, len(pts))).astype(int)  # spread evenly along the scan order
    return pts[idx]


def shape_context(pts):
    d = pts[:, None] - pts[None]
    r = np.hypot(d[..., 0], d[..., 1])
    a = np.arctan2(d[..., 1], d[..., 0]) % (2 * np.pi)
    r = r / (r[r > 0].mean() + 1e-6)                       # scale-free
    rb = np.digitize(np.log(r + 1e-6), np.linspace(np.log(0.125), np.log(2.0), R_BINS)) - 1
    ab = (a / (2 * np.pi / A_BINS)).astype(int) % A_BINS
    h = np.zeros((len(pts), R_BINS, A_BINS), np.float32)
    ok = (rb >= 0) & (rb < R_BINS) & ~np.eye(len(pts), dtype=bool)
    for i in range(len(pts)):
        np.add.at(h[i], (rb[i][ok[i]], ab[i][ok[i]]), 1)
    h = h.reshape(len(pts), -1)
    return h / (h.sum(1, keepdims=True) + 1e-6)


def sc_distance(ha, hb):
    """Mean chi-squared cost of the best one-to-one matching of the two point sets."""
    num = (ha[:, None] - hb[None]) ** 2
    cost = 0.5 * (num / (ha[:, None] + hb[None] + 1e-6)).sum(-1)
    i, j = linear_sum_assignment(cost)
    return float(cost[i, j].mean())


# ---------- running both on the dev lines ----------

def strip(letter):
    return tuple(c for c in letter if c != NUKTA)


def run(lines, bank, held_out=True):
    """Per glyph in a group: truth, today's reading, specialist's and shape context's."""
    feats = np.stack([measure(im, m) for im, m in zip(bank["img"], bank["meta"])])
    scs = [shape_context(outline_points(im)) for im in bank["img"]]
    base_letter = [strip(parts(l)[0])[:1] for l in bank["label"]]
    rows = []
    for line in lines:
        keep = bank_rows(bank, {line["file"]}) if held_out else list(range(len(bank["label"])))
        ix = R.Index(bank, "pixels", keep)
        specialists = {}
        for idx, truth in sorted(line["truth"].items()):
            if truth is None or truth[0] == (SEPARATOR,):
                continue
            img, meta = normalise(unit_mask(line["atoms"], list(idx)), line["atoms"]["tall"])
            opts = R.part_scores(*ix.votes(img, meta, "glyph"))["letter"]
            before = opts[0][0]
            row = dict(truth=truth[0], before=before, specialist=before, sc=before)
            g = GROUP_OF.get(strip(before)[0]) if strip(before) else None
            if g:
                members = GROUPS[g]
                top3 = [strip(o[0])[0] for o in opts[:3] if strip(o[0]) and strip(o[0])[0] in members]
                nk = tuple(c for c in before if c == NUKTA)
                rows_g = [i for i in keep if base_letter[i] and base_letter[i][0] in members]
                if g not in specialists:
                    w = np.array([1.0 if bank["source"][i] == "real" else 0.1 for i in rows_g])
                    y = np.array([base_letter[i][0] for i in rows_g])
                    specialists[g] = make_pipeline(StandardScaler(), LinearSVC(C=0.1, max_iter=20000)).fit(
                        feats[rows_g], y, linearsvc__sample_weight=w) if len(set(y)) > 1 else None
                svm = specialists[g]
                if svm is not None and len(top3) > 1:
                    df = np.atleast_1d(svm.decision_function(measure(img, meta)[None])[0])
                    df = np.array([-df[0], df[0]]) if len(svm.classes_) == 2 else df   # two classes: one signed score
                    score = dict(zip(svm.classes_, df))
                    row["specialist"] = (max(top3, key=lambda c: score.get(c, -np.inf)),) + nk
                if len(top3) > 1:
                    q = shape_context(outline_points(img))
                    best = defaultdict(lambda: np.inf)
                    for i in rows_g:
                        c = base_letter[i][0]
                        if c in top3:
                            best[c] = min(best[c], sc_distance(q, scs[i]))
                    row["sc"] = (min(top3, key=lambda c: best[c]),) + nk
            row["group"] = g
            rows.append(row)
    return rows


def report(rows, title):
    print(f"\n{title}: {len(rows)} glyphs")
    base = np.array([r["before"] == r["truth"] for r in rows])
    for key, label in (("before", "today's matcher"), ("specialist", "specialist (book-trained SVM)"), ("sc", "shape context")):
        h = np.array([r[key] == r["truth"] for r in rows])
        g1, p = mcnemar(base, h)
        fixed = int((~base & h).sum()); broke = int((base & ~h).sum())
        print(f"  {label:30} letters right {h.sum()}/{len(h)} ({h.mean():.1%}), {g1:+d} vs today (p={p:.2f}); fixed {fixed}, broke {broke}")
        for g, members in GROUPS.items():
            n, acc, pp, rr, f = prf([dict(r, after=r[key]) for r in rows], members, "after")
            if n:
                print(f"      {g:14} n={n:2}  acc {acc:.1%}  P/R/F1 {pp:.2f} / {rr:.2f} / {f:.2f}")


if __name__ == "__main__":
    bank = load()
    report(run(lines_and_truth(), bank), "1896 dev lines, each line held out")
    if "--test" in sys.argv:
        report(run(lines_and_truth("test"), bank, held_out=False), "Blind test lines (bank = all dev lines)")
