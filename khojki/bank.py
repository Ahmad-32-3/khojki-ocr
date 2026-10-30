"""The example bank stage C matches against: real glyphs cut from the ground truth, plus chart renders.

usage: python -X utf8 -m khojki.bank      -> data/bank.npz (gitignored: the real examples are scan pixels)
Every example is size-normalised the same way, so a real glyph and a font render can be compared.
"""
import json
from pathlib import Path

import cv2
import numpy as np

from khojki.glyphs import glyph_atoms
from khojki.labels import SEPARATOR, canonical, from_hex
from khojki.render import FONT_FILES, chart_labels, render

ROOT = Path(__file__).resolve().parents[1]
BANK = ROOT / "data" / "bank.npz"
SIZE, INNER = 48, 40  # ink scaled so its longer side is INNER px, centred in a SIZE x SIZE square


def normalise(mask, ref):
    """Ink mask -> (SIZE x SIZE uint8 image, [height / ref, width / ref]). ref = the line's letter height,
    so size relative to the line survives the rescale (a dot and a letter look alike once scaled up)."""
    ys, xs = np.nonzero(mask)
    if not len(ys):
        return np.zeros((SIZE, SIZE), np.uint8), np.zeros(2, np.float32)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    h, w = crop.shape
    s = INNER / max(h, w)
    small = cv2.resize(crop, (max(1, round(w * s)), max(1, round(h * s))), interpolation=cv2.INTER_AREA)
    out = np.zeros((SIZE, SIZE), np.uint8)
    y0, x0 = (SIZE - small.shape[0]) // 2, (SIZE - small.shape[1]) // 2
    out[y0:y0 + small.shape[0], x0:x0 + small.shape[1]] = small
    return out, np.array([h / ref, w / ref], np.float32)


def unit_mask(atoms, idx):
    """Ink of the given atoms only (not of neighbours whose boxes overlap them), cropped to their union box."""
    ids = [i for k in idx for i in atoms["members"][k]]
    x0 = min(atoms["boxes"][k][0] for k in idx)
    x1 = max(atoms["boxes"][k][1] for k in idx)
    lab = atoms["labels"][:, x0:x1]
    return np.where(np.isin(lab, ids), 255, 0).astype(np.uint8)


def atoms_in(unit, atoms):
    """Indices of atoms of the unit's kind whose centre falls in its x-range (same rule as gt/eval_glyphs.py)."""
    kind = "sep" if unit["cps"] == ["U+1123A"] else "glyph"
    return [k for k, b in enumerate(atoms["boxes"]) if b[4] == kind and unit["bbox"][0] <= (b[0] + b[1]) / 2 < unit["bbox"][1]]


def real_examples(gt_path=ROOT / "gt" / "gt.json"):
    gt = json.loads(gt_path.read_text(encoding="utf-8"))
    out = []
    for line in gt["lines"]:
        atoms = glyph_atoms(cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE))
        for u in line["units"]:
            idx = atoms_in(u, atoms)
            if u["status"] != "ok" or not idx:
                continue
            img, meta = normalise(unit_mask(atoms, idx), atoms["tall"])
            out.append(dict(img=img, meta=meta, label=canonical(from_hex(u["cps"])), source="real", line=line["file"]))
    return out


def chart_examples():
    out = []
    for f in FONT_FILES:
        bare = [render((c,), f) for c in range(0x11208, 0x1122C) if c != 0x11212]
        ref = float(np.median([np.ptp(np.nonzero(m)[0]) + 1 for m in bare if m.any()]))  # letter height in this font
        for lab in chart_labels():
            m = render(lab, f)
            if m.any():
                img, meta = normalise(m, ref)
                out.append(dict(img=img, meta=meta, label=lab, source="chart", line=f))
    return out


def save(examples, path=BANK):
    np.savez_compressed(path, img=np.stack([e["img"] for e in examples]), meta=np.stack([e["meta"] for e in examples]),
                        label=np.array([" ".join(f"{c:X}" for c in e["label"]) for e in examples]),
                        source=np.array([e["source"] for e in examples]), line=np.array([e["line"] for e in examples]))


def load(path=BANK):
    d = np.load(path)
    labels = [tuple(int(h, 16) for h in s.split()) for s in d["label"]]
    return dict(img=d["img"], meta=d["meta"], label=labels, source=list(d["source"]), line=list(d["line"]))


if __name__ == "__main__":
    real, chart = real_examples(), chart_examples()
    save(real + chart)
    print(f"bank: {len(real)} real + {len(chart)} chart = {len(real) + len(chart)} examples -> {BANK.relative_to(ROOT)}")
