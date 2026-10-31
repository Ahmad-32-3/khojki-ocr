"""Experiments to improve glyph recognition (log 88). Held-out dev lines only; the test lines are never touched.

usage: python -X utf8 gt/exp_vision.py [variant ...]      default: all; the baseline always runs first

Metric: leave one line out, letter of each GT glyph group (105 glyphs, separators left out): top-1 and in top 3.
Each variant is compared with the baseline glyph by glyph (exact McNemar test), because 105 glyphs can't show
small gains: one glyph is ~1 point. Variants change the bank (augmented copies keep their source line, so a
held-out line's own examples and their copies are always removed together), the description or the voting.
Result (log 88): nothing beat the baseline significantly; the best, pixels + HOG ensemble, +6 glyphs top-1, p=0.11.
"""
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load, normalise, unit_mask  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows, lines_and_truth  # noqa: E402

RNG = np.random.default_rng(0)


# ---------- augmentation: make the font renders look like the 1896 print ----------

def thicken(img, k=2):
    """Real strokes are ~3.7 px wide at the 48 px scale, Noto renders ~2.6 px (measured, log 88)."""
    return cv2.dilate(img, np.ones((k, k), np.uint8))


def degrade(img, rng):
    """One random print-like copy: stroke width, slight rotation / shear / squash, blurred-and-rethresholded edges."""
    h, w = img.shape
    a = np.deg2rad(rng.uniform(-4, 4))
    sh, sy = rng.uniform(-0.12, 0.12), rng.uniform(0.9, 1.1)
    M = np.array([[np.cos(a), -np.sin(a) + sh, 0], [np.sin(a), np.cos(a) * sy, 0]], np.float32)
    M[:, 2] = np.array([w / 2, h / 2]) - M[:, :2] @ np.array([w / 2, h / 2]) + rng.uniform(-1.5, 1.5, 2)
    out = cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR)
    k = int(rng.choice([1, 2, 2, 3]))
    out = cv2.dilate(out, np.ones((k, k), np.uint8)) if k > 1 else out
    out = cv2.GaussianBlur(out, (0, 0), rng.uniform(0.5, 1.2))
    return np.where(out > rng.uniform(90, 160), 255, 0).astype(np.uint8)


def with_rows(bank, extra):
    """bank + extra rows (dicts of img/meta/label/source/line)."""
    if not extra:
        return {k: v for k, v in bank.items() if k != "_feat"}
    return dict(img=np.concatenate([bank["img"], np.stack([e["img"] for e in extra])]),
                meta=np.concatenate([bank["meta"], np.stack([e["meta"] for e in extra])]),
                label=bank["label"] + [e["label"] for e in extra], source=bank["source"] + [e["source"] for e in extra],
                line=bank["line"] + [e["line"] for e in extra], gt_sha=bank["gt_sha"])


def map_chart(bank, fn):
    b = with_rows(bank, [])
    b["img"] = np.stack([fn(im) if s == "chart" else im for im, s in zip(bank["img"], bank["source"])])
    return b


def copies(bank, source, n, fn):
    return [dict(img=fn(bank["img"][i]), meta=bank["meta"][i], label=bank["label"][i], source=source, line=bank["line"][i])
            for i, s in enumerate(bank["source"]) if s == source for _ in range(n)]


# ---------- a small trained network as the shape description ----------

def cnn_description(bank, rows, epochs=12, seed=0):
    """Train a small CNN to name the label of each bank row in `rows`, then use its 128-d penultimate layer
    as the description for nearest-neighbour matching (metric learning by classification)."""
    import torch
    import torch.nn as nn
    torch.manual_seed(seed)
    labs = sorted({bank["label"][i] for i in rows})
    y = torch.tensor([labs.index(bank["label"][i]) for i in rows])
    x = torch.tensor(bank["img"][rows], dtype=torch.float32)[:, None] / 255
    block = lambda i, o: nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))
    body = nn.Sequential(block(1, 32), block(32, 64), block(64, 128), nn.Conv2d(128, 128, 3, padding=1),
                         nn.AdaptiveAvgPool2d(1), nn.Flatten())
    net = nn.Sequential(body, nn.Dropout(0.2), nn.Linear(128, len(labs)))
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    loss = nn.CrossEntropyLoss(label_smoothing=0.1)
    for _ in range(epochs):
        net.train()
        for b in torch.randperm(len(y)).split(128):
            opt.zero_grad()
            loss(net(x[b]), y[b]).backward()
            opt.step()
    net.eval()

    def describe(img):
        with torch.no_grad():
            return body(torch.tensor(img, dtype=torch.float32)[None, None] / 255)[0].numpy()
    return describe


# ---------- scoring ----------

class RealWeighted(R.Index):
    """Votes as R.Index, but a real 1896 example counts `w` times a font render: the renders outnumber the
    real examples 18 to 1, and a render is a weaker witness of how the print looks."""
    w = 3.0

    def votes(self, img, meta, kind="glyph"):
        d = self.distances(img, meta)
        d[self.is_sep != (kind == "sep")] = np.inf
        nearest = [i for i in np.argsort(d, kind="stable")[:R.K] if np.isfinite(d[i])]
        sim = np.exp(-(d[nearest] / self.d0) ** 2) * np.where(self.real[nearest], self.w, 1.0)
        total = sim.sum() + 0.5
        share, real = {}, set()
        for i, s in zip(nearest, sim):
            share[self.labels[i]] = share.get(self.labels[i], 0.0) + s / total
            if self.real[i]:
                real.add(self.labels[i])
        return share, real


class Ensemble:
    """Average of the label shares of several descriptions."""
    def __init__(self, bank, descriptions, rows):
        self.parts = [R.Index(bank, d, rows) for d in descriptions]

    def votes(self, img, meta, kind="glyph"):
        share, real = {}, set()
        for ix in self.parts:
            s, r = ix.votes(img, meta, kind)
            real |= r
            for k, v in s.items():
                share[k] = share.get(k, 0.0) + v / len(self.parts)
        return share, real


def score(lines, bank, make):
    """Leave one line out, letters of the GT glyph groups (not separators). Scoring on the GT groups keeps the
    same 105 glyphs for every variant; with the program's own split the count moved (114-124 letters) with the
    variant. make(bank, rows) -> an object with .votes(), built without the held-out line.
    Returns per-glyph (top-1 right, in top 3), in a fixed order, so variants can be compared glyph by glyph."""
    hits = []
    for line in lines:
        index, atoms = make(bank, bank_rows(bank, {line["file"]})), line["atoms"]
        for idx, truth in sorted(line["truth"].items()):
            if truth is None or truth[0] == (R.SEPARATOR,):
                continue
            img, meta = normalise(unit_mask(atoms, list(idx)), atoms["tall"])
            letters = [o[0] for o in R.part_scores(*index.votes(img, meta, "glyph"))["letter"]]
            hits.append((letters[:1] == [truth[0]], truth[0] in letters[:3]))
    return np.array(hits)


def mcnemar(a, b):
    """Exact two-sided McNemar test: glyphs only one of the two gets right. Small n needs this, not % gaps."""
    from math import comb
    x, y = int((a & ~b).sum()), int((~a & b).sum())
    n, k = x + y, min(x, y)
    p = min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    return y - x, p


def per_fold_cnn(b, rows):
    R.DESCRIPTIONS["_fold"] = cnn_description(b, rows)
    b.pop("_feat", None)
    return R.Index(b, "_fold", rows)


def variants(bank):
    thick = map_chart(bank, thicken)
    aug = with_rows(thick, copies(bank, "chart", 4, lambda im: degrade(im, RNG)))
    aug_real = with_rows(aug, copies(bank, "real", 4, lambda im: degrade(thicken(im, 1), RNG)))
    keep = [i for i, ln in enumerate(bank["line"]) if ln != "NotoSerifKhojki-Regular.ttf"]
    sans = dict(img=bank["img"][keep], meta=bank["meta"][keep], label=[bank["label"][i] for i in keep],
                source=[bank["source"][i] for i in keep], line=[bank["line"][i] for i in keep], gt_sha=bank["gt_sha"])
    ix = lambda d: lambda b, rows: R.Index(b, d, rows)
    return {
        "baseline pixels": (bank, ix("pixels")),
        "baseline hog": (bank, ix("hog")),
        "thicker renders, pixels": (thick, ix("pixels")),
        "thicker renders, hog": (thick, ix("hog")),
        "thicker + 4 degraded copies, pixels": (aug, ix("pixels")),
        "thicker + 4 degraded copies, hog": (aug, ix("hog")),
        "+ 4 jittered real copies, pixels": (aug_real, ix("pixels")),
        "+ 4 jittered real copies, hog": (aug_real, ix("hog")),
        "Sans renders only, pixels": (sans, ix("pixels")),
        "real examples weighted x3, pixels": (bank, lambda b, rows: RealWeighted(b, "pixels", rows)),
        "ensemble pixels + hog": (bank, lambda b, rows: Ensemble(b, ("pixels", "hog"), rows)),
        "cnn, trained per fold on augmented bank": (aug_real, per_fold_cnn),
    }


if __name__ == "__main__":
    lines, bank = lines_and_truth(), load()
    base = None
    for name, (b, make) in variants(bank).items():
        if base is not None and len(sys.argv) > 1 and not any(a in name for a in sys.argv[1:]):
            continue
        h = score(lines, b, make)
        base = h if base is None else base
        (g1, p1), (g3, p3) = mcnemar(base[:, 0], h[:, 0]), mcnemar(base[:, 1], h[:, 1])
        print(f"{name:42} top-1 {h[:, 0].mean():.1%} ({g1:+d}, p={p1:.2f})  top 3 {h[:, 1].mean():.1%} ({g3:+d}, p={p3:.2f})  n={len(h)}", flush=True)
