"""Guards for look-alike letters (log 98). Built on clean font glyphs first, then scored on the 1896 scans.

usage: python -X utf8 gt/exp_guards.py [--test]      --test also scores the 2 blind test lines (nothing is fit on them)

Stage 1, clean: every letter of a problem group is drawn in Noto Sans and Noto Serif Khojki at 3 sizes, 3 small
rotations and 3 stroke weights (27 clean copies per font, no noise). A guard is a linear rule (logistic regression)
on a 6 x 6 ink-density grid of the thinned glyph plus named shape measurements (width / height, holes, stroke ends,
the left 40%), with one explicit check: TA vs BA by width / height. The nukta guard is a depth-3 tree on the
small pieces above the letter. Each guard is fit on one font and checked on the other, both ways, so "clean
accuracy" is always on a font the guard never saw.
Stage 2, noisy: the guards, now fit on both fonts and never on a scan, are applied after today's pixel matcher.
When the matcher's best letter is in a group, the guard picks among the group letters in the matcher's top 3; if
the guard is less than GUARD_SURE sure, the glyph is flagged "unknown" for review instead.
The nukta guard decides dots or no dots for any letter. Dev lines are scored leaving one line out, as everywhere.
"""
import sys, time
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, export_text

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load, normalise, unit_mask  # noqa: E402
from khojki.labels import NUKTA, SEPARATOR, name  # noqa: E402
from khojki.render import FONT_FILES, render  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows, lines_and_truth  # noqa: E402

# Problem groups: from the chart audit at 4rem, the closest other letter between Noto renders, and the matcher's
# real confusions on the dev lines (log 98).
GROUPS = {
    "arch letters": [0x11210, 0x11224, 0x1121E, 0x11221, 0x11219, 0x11223, 0x1120A],  # JA MA NA BA TA BHA GA
    "curl + arches": [0x11216, 0x11218],                                             # DDA NNA
    "3-curl": [0x1121D, 0x11211, 0x11208],                                           # DHA JJA KA
    "colon dots": [0x1120D, 0x11213],                                                # NGA NYA
    "P-shapes": [0x11229, 0x1121A, 0x11228],                                         # SA THA VA
    "round": [0x11214, 0x11215],                                                     # TTA TTHA
}
GUARD_SURE = 0.6
TA, BA = 0x11219, 0x11221
BA_WIDER_THAN = 1.25  # width / height: TA 0.90-1.14, BA 1.37-1.96 over both fonts and all clean copies
SIZES, ANGLES, WEIGHTS = (48, 64, 96), (-3, 0, 3), (-1, 0, 1)


# ---------- shape measurements ----------

def thin(u8):
    """Skeleton redrawn 3 px wide: print strokes are ~40% thicker than the font's (log 88)."""
    return cv2.dilate(R._skeleton(np.where(u8 > 127, 255, 0).astype(np.uint8)) * 255, np.ones((3, 3), np.uint8))


FEATURES = ["aspect"] + [f"ink {r}{c}" for r in "tmb" for c in "lcr"] + [
    "holes", "hole x", "hole y", "stroke ends", "ends x", "ends y", "left-zone crossings", "left-zone height",
    "pieces"] + [f"left ink {r}" for r in ("top", "upper", "lower", "bottom")] + [
    "left hole", "left ends", "left ends y"]
N_NAMED = len(FEATURES)
FEATURES += [f"zone {r}{c}" for r in range(6) for c in range(6)]


def measure(img, meta):
    """img: 48 x 48 normalised glyph (khojki.bank.normalise), meta: [height, width] / line letter height."""
    ink = (img > 127).astype(np.uint8)
    t = (thin(img) > 0).astype(np.uint8)
    ys, xs = np.nonzero(ink)
    if not len(ys):
        return np.zeros(len(FEATURES), np.float32)
    y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
    box = t[y0:y1, x0:x1]
    h, w = box.shape
    grid = [box[r * h // 3:(r + 1) * h // 3, c * w // 3:(c + 1) * w // 3].sum() for r in range(3) for c in range(3)]
    grid = np.array(grid, np.float32) / max(1, box.sum())
    # holes: background regions not touching the border (a closed loop: NA's left, TTHA's bowl, LLA's two)
    n, lab, st, cen = cv2.connectedComponentsWithStats(1 - ink, connectivity=4)
    inner = [k for k in range(1, n) if st[k, 0] > 0 and st[k, 1] > 0 and st[k, 0] + st[k, 2] < 48
             and st[k, 1] + st[k, 3] < 48 and st[k, 4] >= 6]
    big = max(inner, key=lambda k: st[k, 4]) if inner else None
    hx, hy = ((cen[big][0] - x0) / w, (cen[big][1] - y0) / h) if big is not None else (-1.0, -1.0)
    # stroke ends on the skeleton
    sk = R._skeleton(img)
    nb = cv2.filter2D(sk, -1, np.ones((3, 3), np.float32)) - sk
    ey, ex = np.nonzero((sk == 1) & (nb == 1))
    # left zone (first 35% of the width): how many strokes a vertical scan crosses, and how tall the ink is there
    lz = box[:, :max(1, int(0.35 * w))]
    col = lz[:, lz.shape[1] // 2]
    crossings = int(((col[1:] == 1) & (col[:-1] == 0)).sum() + col[0])
    lys = np.nonzero(lz.any(1))[0]
    pieces = cv2.connectedComponents(ink, connectivity=8)[0] - 1
    # the left 40%: where JA's hook, MA's small loop, NA's closed loop and BA's first arch differ (log 96)
    lw = max(1, int(0.4 * w))
    lband = [box[r * h // 4:(r + 1) * h // 4, :lw].sum() for r in range(4)]
    lband = np.array(lband, np.float32) / max(1, sum(lband))
    lhole = float(big is not None and hx < 0.4)
    lend = (ex - x0) < lw
    zone = cv2.resize(box.astype(np.float32), (6, 6), interpolation=cv2.INTER_AREA).ravel()
    zone /= max(zone.sum(), 1e-6)
    return np.array([meta[1] / max(meta[0], 1e-6), *grid, len(inner), hx, hy, len(ey),
                     (ex.mean() - x0) / w if len(ex) else -1, (ey.mean() - y0) / h if len(ey) else -1,
                     crossings, (np.ptp(lys) + 1) / h if len(lys) else 0, pieces, *lband,
                     lhole, int(lend.sum()), (ey[lend].mean() - y0) / h if lend.any() else -1, *zone], np.float32)


def dots_above(img):
    """Small separate pieces in the top 40% of the glyph: the nukta's three dots (an anusvara is one)."""
    ink = (img > 127).astype(np.uint8)
    ys = np.nonzero(ink)[0]
    if not len(ys):
        return np.zeros(3, np.float32)
    n, _, st, cen = cv2.connectedComponentsWithStats(ink, connectivity=8)
    top = ys.min() + 0.4 * (ys.max() - ys.min())
    biggest = st[1:, 4].max()
    small = [k for k in range(1, n) if st[k, 4] <= 0.3 * biggest]   # a dot is ~15% of the letter's main piece
    above = [k for k in small if cen[k][1] <= top]
    return np.array([len(small), len(above), sum(st[k, 4] for k in above) / ink.sum()], np.float32)


# ---------- clean glyphs ----------

def clean_copies(label, font):
    """27 noise-free variants of one label in one font: size x small rotation x stroke weight."""
    bare = [render((c,), font) for c in range(0x11208, 0x1122C) if c != 0x11212]
    ref = float(np.median([np.ptp(np.nonzero(m)[0]) + 1 for m in bare if m.any()]))  # letter height at size 64
    out = []
    for size in SIZES:
        m0 = render(label, font, size=size)
        if not m0.any():
            continue
        for a in ANGLES:
            M = cv2.getRotationMatrix2D((m0.shape[1] / 2, m0.shape[0] / 2), a, 1.0)
            m = cv2.warpAffine(m0, M, m0.shape[::-1], flags=cv2.INTER_NEAREST)
            for wgt in WEIGHTS:
                k = np.ones((2, 2), np.uint8)
                mm = cv2.dilate(m, k) if wgt > 0 else cv2.erode(m, k) if wgt < 0 and size > 48 else m
                out.append(normalise(mm, ref * size / 64))
    return out


def clean_set(labels_by_class):
    """{class: [labels]} -> {font: (X, y)} of shape measurements."""
    out = {}
    for f in FONT_FILES:
        X, y = [], []
        for cls, labs in labels_by_class.items():
            for lab in labs:
                for img, meta in clean_copies(lab, f):
                    X.append(measure(img, meta))
                    y.append(cls)
        out[f] = (np.array(X), np.array(y))
    return out


def nukta_set():
    """Clean bare letters and letter + nukta, every consonant (the dots look the same on any letter)."""
    out = {}
    for f in FONT_FILES:
        X, y = [], []
        for c in [c for c in range(0x11208, 0x1122C) if c != 0x11212]:
            for lab, cls in (((c,), 0), ((c, NUKTA), 1)):
                for img, meta in clean_copies(lab, f)[::3]:  # 9 per font is plenty for a 3-number rule
                    X.append(dots_above(img))
                    y.append(cls)
        out[f] = (np.array(X), np.array(y))
    return out


def tree():
    return DecisionTreeClassifier(max_depth=3, min_samples_leaf=5, random_state=0)


class NamedTree(DecisionTreeClassifier):
    """Depth-3 tree on the named measurements only (not the grid): readable rules, and on the grid it overfits."""
    def __init__(self):
        super().__init__(max_depth=3, min_samples_leaf=5, random_state=0)

    def fit(self, X, y):
        return super().fit(X[:, :N_NAMED], y)

    def predict_proba(self, X, check_input=True):
        return super().predict_proba(X[:, :N_NAMED], check_input)

    def predict(self, X, check_input=True):
        return super().predict(X[:, :N_NAMED], check_input)


class Guard:
    """Linear rule on the measurements, then the TA / BA width check (the linear rule mixed them up 40 times
    across fonts; width alone never does)."""
    def fit(self, X, y):
        self.m = make_pipeline(StandardScaler(), LogisticRegression(C=0.03, max_iter=3000)).fit(X, y)
        self.classes_ = self.m.classes_
        return self

    def predict_proba(self, X):
        p = self.m.predict_proba(X)
        k = {c: i for i, c in enumerate(self.classes_)}
        if TA in k and BA in k:
            for row, x in zip(p, X):
                if row.argmax() in (k[TA], k[BA]):          # the rule says TA or BA: width decides which
                    tb = row[k[TA]] + row[k[BA]]
                    row[k[BA]], row[k[TA]] = (tb, 0.0) if x[0] >= BA_WIDER_THAN else (0.0, tb)
        return p

    def predict(self, X):
        return self.classes_[self.predict_proba(X).argmax(1)]


def cross_font(data, make=Guard):
    """Fit on one font, score on the other, both ways: accuracy on glyphs the guard never saw."""
    (a, b) = FONT_FILES
    right = total = 0
    for fit, test in ((a, b), (b, a)):
        t = make().fit(*data[fit])
        right += int((t.predict(data[test][0]) == data[test][1]).sum())
        total += len(data[test][1])
    return right / total


# ---------- noisy: the 1896 scans ----------

def strip(letter):
    return tuple(c for c in letter if c != NUKTA)


ONLY = None        # --only "nukta,P-shapes": guards kept after the noisy dev check (None = all)
BARE_ONLY = False  # --bare-only: a group guard acts only when the matcher sees no vowel sign (the guards learned bare letters)


def apply_guards(opts, img, meta, guards, nukta_guard, signs=()):
    """opts: matcher's letter options, best first; signs: matcher's best signs. -> (letter, flagged?, guards used)."""
    letter = opts[0][0]
    base, flagged, used = strip(letter), False, []
    for g, (members, t) in guards.items():
        if ONLY is not None and g not in ONLY or BARE_ONLY and signs:
            continue
        if base and base[0] in members:
            top3 = {strip(o[0])[0] for o in opts[:3] if strip(o[0])} & set(members)
            p = t.predict_proba(measure(img, meta)[None])[0]
            ranked = [c for _, c in sorted(zip(-p, t.classes_)) if c in top3]
            if p.max() < GUARD_SURE:
                flagged = True
            elif ranked:
                base = (int(ranked[0]),)
            used.append(g)
            break
    if base and base[0] in range(0x11208, 0x1122C) and (ONLY is None or "nukta" in ONLY):
        dots = nukta_guard.predict(dots_above(img)[None])[0]
        letter = base + ((NUKTA,) if dots else ())
        used.append("nukta")
    else:
        letter = base + tuple(c for c in letter if c == NUKTA)
    return letter, flagged, used


def noisy(lines, bank, guards, nukta_guard, held_out=True):
    """Per glyph: truth letter, matcher's letter, guarded letter, flagged?"""
    rows = []
    for line in lines:
        ix = R.Index(bank, "pixels", bank_rows(bank, {line["file"]}) if held_out else None)
        for idx, truth in sorted(line["truth"].items()):
            if truth is None or truth[0] == (SEPARATOR,):
                continue
            img, meta = normalise(unit_mask(line["atoms"], list(idx)), line["atoms"]["tall"])
            ps = R.part_scores(*ix.votes(img, meta, "glyph"))
            opts = ps["letter"]
            got, flagged, used = apply_guards(opts, img, meta, guards, nukta_guard, ps["signs"][0][0] if ps["signs"] else ())
            rows.append(dict(truth=truth[0], before=opts[0][0], after=got, flagged=flagged, used=used,
                             signs=bool(truth[1])))
    return rows


def prf(rows, members, key):
    """Accuracy on glyphs of the group, and macro precision / recall / F1 over the group's letters."""
    inside = [r for r in rows if strip(r["truth"])[:1] and strip(r["truth"])[0] in members]
    acc = sum(r[key] == r["truth"] for r in inside) / len(inside) if inside else float("nan")
    p, rc, f = [], [], []
    for c in members:
        tp = sum(r[key] == (c,) and r["truth"] == (c,) for r in rows)
        fp = sum(r[key] == (c,) and r["truth"] != (c,) for r in rows)
        fn = sum(r[key] != (c,) and r["truth"] == (c,) for r in rows)
        if tp + fp + fn == 0:
            continue
        pp, rr = tp / (tp + fp) if tp + fp else 0.0, tp / (tp + fn) if tp + fn else 0.0
        p.append(pp), rc.append(rr), f.append(2 * pp * rr / (pp + rr) if pp + rr else 0.0)
    m = lambda v: sum(v) / len(v) if v else float("nan")
    return len(inside), acc, m(p), m(rc), m(f)


def report(rows, groups, title):
    print(f"\n{title}: {len(rows)} glyphs")
    print(f"  {'group':14} {'n':>3}  {'acc before':>10} {'after':>6}   {'P / R / F1 before':>18}   {'after':>18}")
    for g, members in list(groups.items()) + [("nukta", None)]:
        if members is None:
            tb = [(NUKTA in r["truth"], NUKTA in r["before"]) for r in rows]
            ta = [(NUKTA in r["truth"], NUKTA in r["after"]) for r in rows]
            def bin_(pairs):
                tp = sum(t and p for t, p in pairs); fp = sum(p and not t for t, p in pairs)
                fn = sum(t and not p for t, p in pairs); acc = sum(t == p for t, p in pairs) / len(pairs)
                pp = tp / (tp + fp) if tp + fp else 0.0; rr = tp / (tp + fn) if tp + fn else 0.0
                return acc, pp, rr, 2 * pp * rr / (pp + rr) if pp + rr else 0.0
            (a0, p0, r0, f0), (a1, p1, r1, f1) = bin_(tb), bin_(ta)
            print(f"  {'nukta dots':14} {sum(t for t, _ in tb):>3}  {a0:>10.1%} {a1:>6.1%}   "
                  f"{p0:.2f} / {r0:.2f} / {f0:.2f}   {p1:.2f} / {r1:.2f} / {f1:.2f}")
            continue
        n0, a0, p0, r0, f0 = prf(rows, members, "before")
        n1, a1, p1, r1, f1 = prf(rows, members, "after")
        if n0:
            print(f"  {g:14} {n0:>3}  {a0:>10.1%} {a1:>6.1%}   {p0:.2f} / {r0:.2f} / {f0:.2f}   {p1:.2f} / {r1:.2f} / {f1:.2f}")
    fixed = sum(r["before"] != r["truth"] and r["after"] == r["truth"] for r in rows)
    broke = sum(r["before"] == r["truth"] and r["after"] != r["truth"] for r in rows)
    right0 = sum(r["before"] == r["truth"] for r in rows)
    right1 = sum(r["after"] == r["truth"] and not r["flagged"] for r in rows)
    flag = sum(r["flagged"] for r in rows)
    print(f"  all letters: right {right0} -> {right1} of {len(rows)} ({right0 / len(rows):.1%} -> {right1 / len(rows):.1%}); "
          f"confusions resolved {fixed}, newly wrong {broke}; flagged unknown {flag} ({flag / len(rows):.1%})")
    for part in (False, True):
        sub = [r for r in rows if r["signs"] == part]
        if sub:
            print(f"    {'with vowel signs' if part else 'bare letters'}: {sum(r['before'] == r['truth'] for r in sub)} -> "
                  f"{sum(r['after'] == r['truth'] and not r['flagged'] for r in sub)} of {len(sub)}")


if __name__ == "__main__":
    t0 = time.time()
    print("Stage 1, clean (fit on one Noto font, scored on the other):")
    guards = {}
    for g, members in GROUPS.items():
        data = clean_set({c: [(c,)] for c in members})
        # the clean stage picks the guard type per group: whichever does better on the font it wasn't fit on
        acc, make = max(((cross_font(data, m), i, m) for i, m in enumerate((Guard, NamedTree))))[::2]
        X = np.vstack([data[f][0] for f in FONT_FILES]); y = np.concatenate([data[f][1] for f in FONT_FILES])
        guards[g] = (members, make().fit(X, y))
        print(f"  {g:14} {', '.join(name((c,)) for c in members):32} {acc:.1%}  "
              f"({'linear + width' if make is Guard else 'tree'}, n={len(y)})")
    nd = nukta_set()
    nacc = cross_font(nd, tree)
    nukta_guard = tree().fit(np.vstack([nd[f][0] for f in FONT_FILES]), np.concatenate([nd[f][1] for f in FONT_FILES]))
    print(f"  {'nukta dots':14} {'every consonant, with / without':32} {nacc:.1%}")
    print(f"  (clean stage {time.time() - t0:.0f} s)")
    if "--rules" in sys.argv:
        for g, (members, t) in guards.items():
            if isinstance(t, DecisionTreeClassifier):
                print(f"\n{g}:\n" + export_text(t, feature_names=FEATURES[:N_NAMED], class_names=[name((int(c),)) for c in t.classes_]))
        print("nukta:\n" + export_text(nukta_guard, feature_names=["small pieces", "small pieces above", "share above"]))

    if "--only" in sys.argv:
        ONLY = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    BARE_ONLY = "--bare-only" in sys.argv
    if "--clean" in sys.argv:
        sys.exit()
    bank = load()
    rows = noisy(lines_and_truth(), bank, guards, nukta_guard)
    report(rows, GROUPS, "Stage 2, noisy: 1896 dev lines, each line held out")
    if "--test" in sys.argv:
        report(noisy(lines_and_truth("test"), bank, guards, nukta_guard, held_out=False), GROUPS,
               "Blind test lines (bank = all dev lines)")
    img = np.zeros((48, 48), np.uint8); cv2.circle(img, (24, 24), 14, 255, 3)
    n, t1 = 2000, time.perf_counter()
    for _ in range(n):
        measure(img, np.array([1.0, 1.0])); dots_above(img)
    print(f"\nguard cost: {(time.perf_counter() - t1) / n * 1000:.2f} ms per glyph")
