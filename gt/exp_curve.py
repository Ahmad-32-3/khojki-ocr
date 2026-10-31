"""Learning curve: how recognition moves with the number of real labelled glyphs (log 90). Dev lines only.

usage: python -X utf8 gt/exp_curve.py

Same scoring as gt/exp_vision.py (105 GT glyphs, leave one line out, current pixels kNN). In each fold a random
share of the real examples is kept (the chart renders always stay), 5 random draws per share. The fit
error = a * n^-b on the mean top-3 error gives a rough projection, not a promise: 4 points over a 4x range.
"""
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import lines_and_truth  # noqa: E402
from exp_vision import score  # noqa: E402

SHARES, DRAWS = (0.25, 0.5, 0.75, 1.0), 5
PER_LINE = 19  # glyphs per line, as in the retro


def subsample(share, rng):
    def make(b, rows):
        real = [i for i in rows if b["source"][i] == "real"]
        keep = set(rng.choice(real, round(share * len(real)), replace=False).tolist())
        return R.Index(b, "pixels", [i for i in rows if b["source"][i] != "real" or i in keep])
    return make


if __name__ == "__main__":
    lines, bank = lines_and_truth(), load()
    n_real = sum(s == "real" for s in bank["source"])
    pts = []
    for share in SHARES:
        rng = np.random.default_rng(0)
        runs = [score(lines, bank, subsample(share, rng)) for _ in range(DRAWS if share < 1 else 1)]
        t1, t3 = [r[:, 0].mean() for r in runs], [r[:, 1].mean() for r in runs]
        n = share * n_real * (len(lines) - 1) / len(lines)  # real examples a fold actually learns from
        pts.append((n, 1 - np.mean(t3)))
        print(f"{share:>4.0%} real (~{n:.0f} glyphs): top-1 {np.mean(t1):.1%} +- {np.std(t1):.1%}"
              f"  top 3 {np.mean(t3):.1%} +- {np.std(t3):.1%}", flush=True)
    b, log_a = np.polyfit(np.log([p[0] for p in pts]), np.log([p[1] for p in pts]), 1)
    print(f"fit: top-3 error = {np.exp(log_a):.2f} * n^{b:.2f}")
    for target in (0.90, 0.95):
        if b < 0:
            n = ((1 - target) / np.exp(log_a)) ** (1 / b)
            print(f"  top 3 {target:.0%} at ~{n:.0f} real glyphs (~{n / PER_LINE:.0f} lines)")
