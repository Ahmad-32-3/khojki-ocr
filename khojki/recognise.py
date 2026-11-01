"""Stage C: glyph boxes -> recognitions and suggestions (see SPEC.md).

usage: python -X utf8 -m khojki.recognise <line image>     -> JSON on stdout
Needs data/bank.npz (python -m khojki.bank) and data/model.json (python gt/eval_recognise.py --fit).
Without model.json every part is a suggestion: the program never commits without a measured threshold.
No network, no language model: shapes are matched against stored examples only.
"""
import json, sys
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np

from khojki.bank import BANK, fingerprint, load, normalise, unit_mask
from khojki.glyphs import glyph_atoms
from khojki.labels import SEPARATOR, name, parts

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "data" / "model.json"
MAX_JOIN = 3      # a glyph comes out in at most 3 boxes (log 65)
K = 7             # neighbours that vote
MARGIN = 0.15     # a recognised part must beat the next option by this much (SPEC step 7)
META_WEIGHT = 0.5  # how much relative height / width count next to shape
REPLACEMENT = "�"
RED_BELOW = 0.30  # a glyph whose best letter guess is under 30% is "no good guess": written as one REPLACEMENT


# ---------- shape descriptions ----------

def _hog(img, cell=8, bins=9):
    """Histogram of stroke directions (Dalal & Triggs 2005), per 8 x 8 cell, 9 unsigned orientation bins.
    Written here because OpenCV 5 dropped cv2.HOGDescriptor. No block normalisation: Index L2-normalises the vector."""
    g = img.astype(np.float32)
    gx, gy = cv2.Sobel(g, cv2.CV_32F, 1, 0), cv2.Sobel(g, cv2.CV_32F, 0, 1)
    mag, ang = np.hypot(gx, gy), np.rad2deg(np.arctan2(gy, gx)) % 180
    b = np.minimum((ang / (180 / bins)).astype(int), bins - 1)
    n = img.shape[0] // cell
    hist = np.zeros((n, n, bins), np.float32)
    for i in range(n):
        for j in range(n):
            sl = (slice(i * cell, (i + 1) * cell), slice(j * cell, (j + 1) * cell))
            hist[i, j] = np.bincount(b[sl].ravel(), mag[sl].ravel(), bins)
    return hist.ravel()


def _skeleton(img):
    ink = (img > 127).astype(np.uint8)
    skel = np.zeros_like(ink)
    kernel = cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))
    while ink.any():
        opened = cv2.morphologyEx(ink, cv2.MORPH_OPEN, kernel)
        skel |= ink - opened
        ink = cv2.erode(ink, kernel)
    return skel


def _shape_counts(img):
    """Holes, stroke ends, junctions, aspect, ink share in 3 horizontal and 3 vertical bands."""
    ink = (img > 127).astype(np.uint8)
    contours, hier = cv2.findContours(ink, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
    holes = sum(1 for h in (hier[0] if hier is not None else []) if h[3] >= 0)
    skel = _skeleton(img)
    nb = cv2.filter2D(skel, -1, np.ones((3, 3), np.float32)) - skel
    ends = int(((skel == 1) & (nb == 1)).sum())
    junctions = int(((skel == 1) & (nb >= 3)).sum())
    ys, xs = np.nonzero(ink)
    aspect = (np.ptp(xs) + 1) / (np.ptp(ys) + 1) if len(ys) else 0.0
    total = max(1, int(ink.sum()))
    bands = [ink[i * 16:(i + 1) * 16].sum() / total for i in range(3)] + [ink[:, i * 16:(i + 1) * 16].sum() / total for i in range(3)]
    return np.array([holes, ends, junctions, aspect, *bands], np.float32)


DESCRIPTIONS = {
    "pixels": lambda img: cv2.GaussianBlur(img.astype(np.float32) / 255, (0, 0), 1.5).ravel(),
    "hog": _hog,
    "shape": _shape_counts,
}


class Index:
    """The example bank, described one way, ready for nearest-neighbour search."""

    def __init__(self, bank, description="pixels", keep=None):
        keep = np.arange(len(bank["label"])) if keep is None else np.asarray(keep)
        self.description = description
        self.labels = [bank["label"][i] for i in keep]
        self.real = np.array([bank["source"][i] == "real" for i in keep])
        self.meta = bank["meta"][keep]
        cache = bank.setdefault("_feat", {})  # describe the whole bank once; folds only pick rows
        if description not in cache:
            cache[description] = np.stack([DESCRIPTIONS[description](im) for im in bank["img"]])
        f = cache[description][keep]
        self.mean, self.std = (f.mean(0), f.std(0) + 1e-6) if description == "shape" else (0.0, 1.0)
        self.feat = self._scale(f)
        self.is_sep = np.array([l == (SEPARATOR,) for l in self.labels])
        self.d0 = self._typical_same_label_distance()

    def _scale(self, f):
        f = (f - self.mean) / self.std
        return f / (np.linalg.norm(f, axis=-1, keepdims=True) + 1e-9)

    def distances(self, img, meta):
        q = self._scale(DESCRIPTIONS[self.description](img)[None])[0]
        # rows and q are unit length, so |f - q|^2 = 2 - 2 f.q: one matrix-vector product, ~8x faster than subtracting
        d = np.sqrt(np.maximum(2 - 2 * (self.feat @ q), 0))
        return d + META_WEIGHT * np.linalg.norm(self.meta - meta, axis=1)

    def _typical_same_label_distance(self):
        """Median distance from a real example to its nearest other example of the same label: the scale of 'close'."""
        ds = []
        for i in np.flatnonzero(self.real):
            same = [j for j, l in enumerate(self.labels) if l == self.labels[i] and j != i]
            if same:
                d = np.linalg.norm(self.feat[same] - self.feat[i], axis=1) + META_WEIGHT * np.linalg.norm(self.meta[same] - self.meta[i], axis=1)
                ds.append(d.min())
        return max(float(np.median(ds)), 0.05) if ds else 1.0  # floor: identical examples would make it 0

    def votes(self, img, meta, kind="glyph"):
        """Label -> share of similarity among the K nearest, plus which labels had a real example among them.
        Shares don't sum to 1: some mass is kept back for 'none of these', so far-away matches score low.
        Stage B already decided separator or not (31/31 right, log 64), so a glyph box is only compared with
        non-separator examples and a separator box only with separators. Without this, a split-off AA upright
        matched a separator and was recognised under the separator threshold (log 70)."""
        d = self.distances(img, meta)
        d[self.is_sep != (kind == "sep")] = np.inf
        nearest = [i for i in np.argsort(d, kind="stable")[:K] if np.isfinite(d[i])]
        sim = np.exp(-(d[nearest] / self.d0) ** 2)
        total = sim.sum() + 0.5  # 0.5 = the 'none of these' mass (a moderately close example is worth ~0.4-0.8)
        share, real = defaultdict(float), set()
        for i, s in zip(nearest, sim):
            share[self.labels[i]] += s / total
            if self.real[i]:
                real.add(self.labels[i])
        return dict(share), real


# ---------- one unit: letter and signs decided separately ----------

def part_scores(share, real):
    """From label shares to per-part options: {'letter': [(value, score, has_real)], 'signs': [...]}, best first."""
    out = {}
    for k, which in (("letter", 0), ("signs", 1)):
        agg, has_real = defaultdict(float), defaultdict(bool)
        for lab, s in share.items():
            v = parts(lab)[which]
            agg[v] += s
            has_real[v] |= lab in real
        out[k] = sorted(((v, s, has_real[v]) for v, s in agg.items()), key=lambda t: (-t[1], t[0]))
    return out


def group(opts):
    """'sep' or 'glyph', from the *predicted* letter: separators are far easier, so they get their own
    calibration and threshold, or they'd carry a threshold that glyphs don't meet (log 70)."""
    return "sep" if opts["letter"][0][0] == (SEPARATOR,) else "glyph"


def decide(options, calib, tau):
    """One part -> recognised (calibrated score >= tau, margin >= MARGIN, backed by a real example) or suggestion.
    A recognition still lists the next options."""
    (top, raw, real), *rest = options
    second = rest[0][1] if rest else 0.0
    conf = calibrate(raw, calib)
    shown = [{"cps": [f"U+{c:04X}" for c in v], "conf": round(calibrate(s, calib), 3)} for v, s, _ in options[:3]]
    if conf >= tau and raw - second >= MARGIN and real:
        return {"status": "recognised", "cps": shown[0]["cps"], "conf": round(conf, 3), "others": shown[1:]}
    return {"status": "suggestion", "options": shown}



def calibrate(raw, calib):
    """Piecewise-linear map from raw score to probability of being right (isotonic fit, see eval_recognise.py)."""
    if not calib:
        return 0.0  # no fitted model: nothing is trusted
    return float(np.interp(raw, calib["x"], calib["y"]))


# ---------- a whole line ----------

def candidates(atoms, index):
    """Every run of 1..MAX_JOIN neighbouring glyph boxes (separators and marks stand alone) -> label votes.
    A mark box was already read by its shape in stage B: it gets that label, fully sure."""
    boxes = atoms["boxes"]
    out = {}
    for i in range(len(boxes)):
        if boxes[i][4] == "mark":
            out[(i, 1)] = ({atoms["cps"][i]: 1.0}, {atoms["cps"][i]})
            continue
        for n in range(1, MAX_JOIN + 1):
            idx = list(range(i, i + n))
            if idx[-1] >= len(boxes) or (n > 1 and any(boxes[k][4] != "glyph" for k in idx)):
                break
            img, meta = normalise(unit_mask(atoms, idx), atoms["tall"])
            out[(i, n)] = index.votes(img, meta, boxes[i][4])
    return out


def best_split(n_boxes, cands):
    """Dynamic programming: split the boxes into units so that every box is explained as well as possible.
    A unit's score counts once per box it covers, so joining is neither favoured nor penalised by itself."""
    best = [(0.0, None)] + [(-np.inf, None)] * n_boxes
    for end in range(1, n_boxes + 1):
        for n in range(1, MAX_JOIN + 1):
            start = end - n
            if start < 0 or (start, n) not in cands:
                continue
            share, _ = cands[(start, n)]
            top = max(share.values()) if share else 0.0
            score = best[start][0] + n * np.log(top + 1e-6)
            if score > best[end][0]:
                best[end] = (score, n)
    units, end = [], n_boxes
    while end:
        n = best[end][1]
        units.append(list(range(end - n, end)))
        end -= n
    return units[::-1]


def _component(cand, model):
    """One box of an unknown unit, read on its own: its best letter + signs. A shape we have no example for as a
    whole (e.g. a loop joined to MA) can still be described by the parts we do know."""
    share, real = cand
    opts = part_scores(share, real)
    m = (model or {}).get("letter", {}).get(group(opts), {})
    cps = opts["letter"][0][0] + opts["signs"][0][0]
    return {"cps": [f"U+{c:04X}" for c in cps], "name": name(cps), "conf": round(calibrate(opts["letter"][0][1], m.get("calib")), 3)}


def colour(letter):
    """green: recognised; red: no good guess (best letter guess under RED_BELOW); orange: everything else."""
    if letter["status"] == "recognised":
        return "green"
    return "red" if (letter["options"][0]["conf"] if letter["options"] else 0.0) < RED_BELOW else "orange"


def unit_text(letter, signs):
    """What a glyph writes to the text: the answer when recognised, the best guess when there is one (orange),
    and a single REPLACEMENT only when there's no good guess (red)."""
    if colour(letter) == "red":
        return REPLACEMENT
    pick = lambda d: d["cps"] if d["status"] == "recognised" else (d["options"][0]["cps"] if d["options"] else [])
    return "".join(chr(int(c[2:], 16)) for c in pick(letter) + pick(signs))


def recognise_atoms(atoms, index, model):
    cands = candidates(atoms, index)
    units = []
    for idx in best_split(len(atoms["boxes"]), cands):
        share, real = cands[(idx[0], len(idx))]
        opts = part_scores(share, real)
        unit = {"boxes": idx}
        if atoms.get("cps") and atoms["cps"][idx[0]]:  # a mark, read by shape in stage B: no calibration applies
            sure = lambda cps: {"status": "recognised", "cps": [f"U+{c:04X}" for c in cps], "conf": 1.0, "others": []}
            unit.update(letter=sure(atoms["cps"][idx[0]]), signs=sure(()), colour="green")
            unit["text"] = unit_text(unit["letter"], unit["signs"])
            units.append(unit)
            continue
        kind = group(opts)
        for part in ("letter", "signs"):
            m = (model or {}).get(part, {}).get(kind, {})
            unit[part] = decide(opts[part], m.get("calib"), m.get("tau", 2.0))
        unit["colour"] = colour(unit["letter"])
        unit["text"] = unit_text(unit["letter"], unit["signs"])
        if len(idx) > 1 and unit["letter"]["status"] != "recognised":
            unit["components"] = [_component(cands[(i, 1)], model) for i in idx]
        units.append(unit)
    return {"units": units, "text": "".join(u["text"] for u in units)}


def load_model(path=MODEL):
    return json.loads(Path(path).read_text(encoding="utf-8")) if Path(path).exists() else None


def check_model(model, bank):
    """A model's thresholds were measured on one bank. Used with another (e.g. after a GT refreeze and bank
    rebuild without refitting), they no longer mean 95%. So refuse, rather than run with stale thresholds."""
    want = (model or {}).get("bank_fp")
    if want and want != fingerprint(bank):
        raise RuntimeError(f"data/model.json was fitted on bank {want}, but data/bank.npz is {fingerprint(bank)}. "
                           "Refit: python -X utf8 gt/eval_recognise.py --fit")


def recognise_line(gray, bank=None, model=None, description=None):
    model = model if model is not None else load_model()
    bank = bank if bank is not None else load(BANK)
    check_model(model, bank)
    index = Index(bank, description or (model or {}).get("description", "pixels"))
    return recognise_atoms(glyph_atoms(gray), index, model)


if __name__ == "__main__":
    gray = cv2.imread(sys.argv[1], cv2.IMREAD_GRAYSCALE)
    print(json.dumps(recognise_line(gray), ensure_ascii=False, indent=1))
