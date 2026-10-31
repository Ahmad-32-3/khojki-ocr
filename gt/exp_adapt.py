"""Domain adaptation for glyph recognition (log 89). Dev lines only; the test lines are never touched.

usage: python -X utf8 gt/exp_adapt.py [--steps N] [variant ...]      default: all; the baseline always runs first

The gap (log 88): real strokes are ~40% thicker than the font renders, and 18 of 19 bank examples are renders,
so a real glyph's nearest neighbours are often renders of the wrong letter. This learns a description in which
a render and a real glyph of the same letter land close together. Three parts, each switchable:
  supervised   a small CNN learns to name the label of each bank example (metric learning by classification)
  contrastive  SimCLR (Chen et al. 2020): two random print-like views of one glyph should embed close, views of
               different glyphs far. It runs on glyphs from the 24 page lines that are NOT ground truth, without
               their labels, so the network sees how the real print varies.
  adversarial  DANN (Ganin et al. 2016): a small head tries to tell render from real from the embedding; a
               gradient reversal layer trains the encoder to make that impossible.
The combination follows arXiv 2609.07159 (SimCLR + DANN, font renders vs real manuscript crops).
The trained embedding is then the kNN description, scored as gt/exp_vision.py: 105 GT glyphs, leave one line out
(the network is retrained per fold without the held-out line's labels), compared glyph by glyph (exact McNemar).
The unlabelled pool holds no GT line at all, so no fold ever sees its held-out line, labelled or not.
Result (log 89): every learned variant did worse than plain pixels; DANN alone significantly so (-15, p<0.01).
"""
import argparse, json, math, sys, time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load, normalise, unit_mask  # noqa: E402
from khojki.glyphs import glyph_atoms  # noqa: E402
from khojki.labels import parts  # noqa: E402
from khojki.lines import find_lines  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows, lines_and_truth  # noqa: E402
from exp_vision import mcnemar  # noqa: E402

torch.set_num_threads(8)


# ---------- unlabelled real glyphs ----------

def unlabelled_glyphs():
    """Single glyph boxes and neighbouring pairs from page lines that are not ground truth (no labels).
    find_lines gives 11 / 12 / 12 lines on p9 / p10 / p11, in the same order as the hand-marked centres the
    GT files are numbered by (checked, log 89), so line i of page p is gt/lines/p_l{i}.png if that exists."""
    gt = {l["file"] for l in json.loads((ROOT / "gt" / "gt.json").read_text(encoding="utf-8"))["lines"]}
    out, kept = [], 0
    for p in ("p09", "p10", "p11"):
        gray = cv2.imread(str(ROOT / "data" / "pages" / f"{p}.png"), cv2.IMREAD_GRAYSCALE)
        for i, (x0, y0, x1, y1) in enumerate(find_lines(gray), 1):
            if f"lines/{p}_l{i:02d}.png" in gt:
                continue
            kept += 1
            atoms = glyph_atoms(gray[y0:y1, x0:x1])
            boxes = atoms["boxes"]
            for k in range(len(boxes)):
                for n in (1, 2):
                    idx = list(range(k, k + n))
                    if idx[-1] < len(boxes) and all(boxes[j][4] == "glyph" for j in idx):
                        out.append(normalise(unit_mask(atoms, idx), atoms["tall"])[0])
    return np.stack(out), kept


# ---------- the network ----------

def augment(x, thicken):
    """Batch of random print-like views (x: N,1,48,48 in [0, 1]): rotate +-4 deg, shear +-0.12, squash 0.9-1.1,
    shift +-1.5 px, thicken the rows marked in `thicken` (renders are thinner than the print), soften the edges
    and re-threshold. Same ranges as exp_vision.degrade, done on the whole batch at once."""
    n = len(x)
    a = torch.empty(n).uniform_(-4, 4) * math.pi / 180
    sh, sy = torch.empty(n).uniform_(-0.12, 0.12), torch.empty(n).uniform_(0.9, 1.1)
    t = torch.empty(n, 2).uniform_(-1.5, 1.5) / 24  # px -> [-1, 1] grid units
    theta = torch.stack([torch.stack([a.cos(), -a.sin() + sh, t[:, 0]], 1),
                         torch.stack([a.sin(), a.cos() * sy, t[:, 1]], 1)], 1)
    out = F.grid_sample(x, F.affine_grid(theta, x.shape, align_corners=False), align_corners=False)
    out = torch.where(thicken[:, None, None, None], F.max_pool2d(out, 3, 1, 1), out)
    out = F.avg_pool2d(out, 3, 1, 1)
    return (out > torch.empty(n, 1, 1, 1).uniform_(0.35, 0.6)).float()


class Reverse(torch.autograd.Function):
    """Gradient reversal: identity going forward, gradient times -lam going back (DANN)."""
    @staticmethod
    def forward(ctx, x, lam):
        ctx.lam = lam
        return x.view_as(x)

    @staticmethod
    def backward(ctx, g):
        return -ctx.lam * g, None


class Net(nn.Module):
    def __init__(self, n_labels):
        super().__init__()
        block = lambda i, o: nn.Sequential(nn.Conv2d(i, o, 3, padding=1), nn.BatchNorm2d(o), nn.ReLU(), nn.MaxPool2d(2))
        # half the width of exp_vision's CNN: twice as fast on this CPU (0.25 s per step with all three losses)
        self.body = nn.Sequential(block(1, 16), block(16, 32), block(32, 64), nn.Conv2d(64, 128, 3, padding=1),
                                  nn.AdaptiveAvgPool2d(1), nn.Flatten())           # 128-d embedding = the description
        self.classify = nn.Sequential(nn.Dropout(0.2), nn.Linear(128, n_labels))
        self.project = nn.Sequential(nn.Linear(128, 128), nn.ReLU(), nn.Linear(128, 64))  # SimCLR head, thrown away
        self.domain = nn.Sequential(nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))      # render (0) or real (1)


def nt_xent(z1, z2, temp=0.2):
    """SimCLR loss: each view must pick its partner out of the 2N-1 other views in the batch."""
    z = F.normalize(torch.cat([z1, z2]), dim=1)
    sim = z @ z.T / temp
    sim.fill_diagonal_(-float("inf"))
    n = len(z1)
    return F.cross_entropy(sim, torch.cat([torch.arange(n) + n, torch.arange(n)]))


def train(bank, rows, unl, contrastive, adversarial, steps, batch=128, seed=0, reweight=False):
    """Train on the bank rows (labels) and the unlabelled pool; returns img -> 128-d description.
    reweight: draw renders at the letter mix of this fold's real labels instead of one per label (log 90).
    The renders hold every letter equally; the print doesn't. DANN matches the two mixes as wholes, so with
    that label shift it also pulls wrong letters together (Zhao et al. 2019)."""
    torch.manual_seed(seed)
    labs = sorted({bank["label"][i] for i in rows})
    y = torch.tensor([labs.index(bank["label"][i]) for i in rows])
    x = torch.tensor(bank["img"][rows], dtype=torch.float32)[:, None] / 255
    real = torch.tensor([bank["source"][i] == "real" for i in rows])
    xu = torch.tensor(unl, dtype=torch.float32)[:, None] / 255
    net = Net(len(labs))
    opt = torch.optim.AdamW(net.parameters(), 2e-3, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-3, total_steps=steps)
    # a quarter of each labelled batch is real: 150 real among 2,800 would otherwise be ~7 per batch
    w = torch.where(real, 0.25 / real.sum(), 0.75 / (~real).sum())
    if reweight:
        letter = [parts(bank["label"][i])[0] for i in rows]
        freq = {}
        for l, r in zip(letter, real.tolist()):
            freq[l] = freq.get(l, 0) + r
        mix = torch.tensor([freq.get(l, 0) + 0.5 for l in letter])  # +0.5: a letter not yet seen in print still appears
        w = torch.where(real, w, 0.75 * mix / mix[~real].sum())
    net.train()
    for step in range(steps):
        b = torch.multinomial(w, batch, replacement=True)
        f = net.body(augment(x[b], ~real[b] & (torch.rand(batch) < 0.6)))
        loss = F.cross_entropy(net.classify(f), y[b], label_smoothing=0.1)
        if contrastive or adversarial:
            u = xu[torch.randint(len(xu), (batch,))]
            no = torch.zeros(batch, dtype=torch.bool)
            fu = net.body(augment(u, no))
        if contrastive:
            loss = loss + nt_xent(net.project(fu), net.project(net.body(augment(u, no))))
        if adversarial:
            lam = 2 / (1 + math.exp(-10 * step / steps)) - 1  # ramp 0 -> 1, as in the DANN paper
            src = f[~real[b]]  # renders in this batch vs real glyphs (unlabelled)
            d = net.domain(Reverse.apply(torch.cat([src, fu]), lam))[:, 0]
            loss = loss + 0.3 * F.binary_cross_entropy_with_logits(d, torch.cat([torch.zeros(len(src)), torch.ones(batch)]))
        opt.zero_grad()
        loss.backward()
        opt.step()
        sched.step()
    net.eval()

    def describe(img):
        """One image (H, W) or a stack (N, H, W) -> description(s)."""
        with torch.no_grad():
            t = torch.tensor(img, dtype=torch.float32) / 255
            return net.body(t.reshape(-1, 1, *t.shape[-2:])).numpy().reshape(*t.shape[:-2], -1)
    return describe


# ---------- scoring ----------

def score(lines, bank, make):
    """As exp_vision.score (same 105 glyphs, same order), plus a gap measure: how many of each glyph's
    7 nearest neighbours are font renders of its true label (renders that actually help)."""
    hits, helpful = [], []
    for line in lines:
        index, atoms = make(bank, bank_rows(bank, {line["file"]})), line["atoms"]
        for idx, truth in sorted(line["truth"].items()):
            if truth is None or truth[0] == (R.SEPARATOR,):
                continue
            img, meta = normalise(unit_mask(atoms, list(idx)), atoms["tall"])
            letters = [o[0] for o in R.part_scores(*index.votes(img, meta, "glyph"))["letter"]]
            hits.append((letters[:1] == [truth[0]], truth[0] in letters[:3]))
            d = index.distances(img, meta)
            d[index.is_sep] = np.inf
            near = np.argsort(d, kind="stable")[:R.K]
            helpful.append(sum(not index.real[i] and parts(index.labels[i])[0] == truth[0] for i in near))
    return np.array(hits), float(np.mean(helpful))


def learned(unl, contrastive, adversarial, steps, reweight=False):
    def make(b, rows):
        R.DESCRIPTIONS["_fold"] = describe = train(b, rows, unl, contrastive, adversarial, steps, reweight=reweight)
        b.setdefault("_feat", {})["_fold"] = describe(b["img"])  # this fold's network, whole bank in one pass
        return R.Index(b, "_fold", rows)
    return make


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--steps", type=int, default=800)
    ap.add_argument("only", nargs="*")
    a = ap.parse_args()
    lines, bank = lines_and_truth(), load()
    unl, kept = unlabelled_glyphs()
    print(f"unlabelled pool: {len(unl)} glyph crops from {kept} non-GT lines; {len(lines)} dev lines", flush=True)
    variants = {
        "baseline pixels": lambda b, rows: R.Index(b, "pixels", rows),
        "supervised CNN": learned(unl, False, False, a.steps),
        "+ contrastive (SimCLR)": learned(unl, True, False, a.steps),
        "+ adversarial (DANN)": learned(unl, False, True, a.steps),
        "+ contrastive + adversarial": learned(unl, True, True, a.steps),
        "+ DANN, renders at real letter mix": learned(unl, False, True, a.steps, reweight=True),
        "+ SimCLR + DANN, real letter mix": learned(unl, True, True, a.steps, reweight=True),
    }
    base = None
    for name, make in variants.items():
        if base is not None and a.only and not any(o in name for o in a.only):
            continue
        t0 = time.time()
        h, helpful = score(lines, bank, make)
        base = h if base is None else base
        (g1, p1), (g3, p3) = mcnemar(base[:, 0], h[:, 0]), mcnemar(base[:, 1], h[:, 1])
        print(f"{name:30} top-1 {h[:, 0].mean():.1%} ({g1:+d}, p={p1:.2f})  top 3 {h[:, 1].mean():.1%} ({g3:+d}, p={p3:.2f})"
              f"  right-label renders in 7 nearest {helpful:.2f}  n={len(h)}  {time.time() - t0:.0f}s", flush=True)
