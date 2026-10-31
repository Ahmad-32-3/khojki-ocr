"""Held-out evaluation of stage C, and fitting the model the pipeline uses.

usage: python -X utf8 gt/eval_recognise.py          compare the 3 shape descriptions, leave one line out
       python -X utf8 gt/eval_recognise.py --fit    also write data/model.json for the chosen description

Leave one line out, nested (SPEC criterion 5): for held-out line f, the calibration and threshold tau are fitted
on predictions for the other lines, each predicted without itself and without f. Line f is never used to fit.
Ground-truth line crops are used (stage A taken as perfect); end-to-end scoring is chunk 5.
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np
from sklearn.isotonic import IsotonicRegression

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from khojki.bank import atoms_in, fingerprint, load  # noqa: E402
from khojki.glyphs import glyph_atoms  # noqa: E402
from khojki.labels import SEPARATOR, canonical, from_hex, parts  # noqa: E402
from khojki.recognise import DESCRIPTIONS, MARGIN, MODEL, Index, best_split, calibrate, candidates, group, part_scores  # noqa: E402

TARGET = 0.95
MIN_SUPPORT = 10  # a threshold counts only if >= 10 calibration recognitions back it (3/3 right proves nothing)
PARTS = ("letter", "signs")


def lines_and_truth(split="dev"):
    """GT lines of one split. 'dev' lines are for learning and tuning; 'test' lines (blind, chunk 7) are scored
    only by gt/eval_test.py and never used to fit or choose anything."""
    gt = json.loads((ROOT / "gt" / "gt.json").read_text(encoding="utf-8"))
    out = []
    for line in gt["lines"]:
        if line.get("split", "dev") != split:
            continue
        atoms = glyph_atoms(cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE))
        truth = {}  # atom indices of a GT unit -> (letter, signs), or None if nobody could read it
        for u in line["units"]:
            idx = tuple(atoms_in(u, atoms))
            if not idx:
                continue
            t = None if u["status"] != "ok" else parts(canonical(from_hex(u["cps"])))
            if truth.get(idx) and t:  # several answers on one box (p11 l6: digit, separator, section mark):
                t = (truth[idx][0] + truth[idx][1] + t[0] + t[1], ())  # keep all, in order (log 83)
            truth[idx] = t or truth.get(idx)
        out.append(dict(file=line["file"], atoms=atoms, truth=truth))
    return out


def bank_rows(bank, exclude):
    """Rows of the bank to learn from: all chart examples, real examples from lines not in `exclude`."""
    return [i for i, (s, ln) in enumerate(zip(bank["source"], bank["line"])) if s == "chart" or ln not in exclude]


def predict(line, index):
    """Raw part predictions for one line: list of dicts with part, value, raw, margin, real, truth (or 'seg' / None)."""
    cands = candidates(line["atoms"], index)
    recs = []
    for idx in best_split(len(line["atoms"]["boxes"]), cands):
        opts = part_scores(*cands[(idx[0], len(idx))])
        key = tuple(idx)
        truth = line["truth"].get(key, "seg") if key in line["truth"] else "seg"
        if truth is None:
            continue  # an open GT unit: no truth to score against
        sep = (truth[0] if truth != "seg" else opts["letter"][0][0]) == (SEPARATOR,)
        for k, part in enumerate(PARTS):
            (v, raw, real), *rest = opts[part]
            in_top3 = truth != "seg" and truth[k] in [o[0] for o in opts[part][:3]]
            recs.append(dict(part=part, value=v, raw=raw, margin=raw - (rest[0][1] if rest else 0.0), real=real, in_top3=in_top3,
                             correct=truth != "seg" and truth[k] == v, file=line["file"], sep=sep, kind=group(opts)))
    return recs


def fit(recs):
    """Isotonic calibration and tau per part and per group (predicted sep / glyph), from out-of-fold records.
    tau = lowest threshold whose recognitions (also passing margin and real-example rules) are >= TARGET
    precise, with at least MIN_SUPPORT of them; 2.0 = recognise nothing."""
    model = {}
    for part in PARTS:
        model[part] = {}
        for kind in ("sep", "glyph"):
            model[part][kind] = _fit_one([x for x in recs if x["part"] == part and x["kind"] == kind])
    return model


def _fit_one(r):
    if len(r) < 5:
        return {"calib": None, "tau": 2.0}
    iso = IsotonicRegression(y_min=0, y_max=1, out_of_bounds="clip").fit([x["raw"] for x in r], [x["correct"] for x in r])
    xs = np.unique([x["raw"] for x in r])
    calib = {"x": xs.tolist(), "y": iso.predict(xs).tolist()}
    for t in sorted({calibrate(x["raw"], calib) for x in r}):
        chosen = [x for x in r if calibrate(x["raw"], calib) >= t and x["margin"] >= MARGIN and x["real"]]
        if len(chosen) >= MIN_SUPPORT and sum(x["correct"] for x in chosen) / len(chosen) >= TARGET:
            return {"calib": calib, "tau": t}
    return {"calib": calib, "tau": 2.0}


def recognised(rec, model):
    m = model[rec["part"]][rec["kind"]]
    return calibrate(rec["raw"], m["calib"]) >= m["tau"] and rec["margin"] >= MARGIN and rec["real"]


def folds(lines):
    """(held-out file, [inner files]) for every line."""
    files = [l["file"] for l in lines]
    return [(f, [g for g in files if g != f]) for f in files]


def evaluate(lines, bank, description):
    by_file = {l["file"]: l for l in lines}
    held_out = []
    for f, inner in folds(lines):
        calib_recs = []
        for g in inner:
            calib_recs += predict(by_file[g], Index(bank, description, bank_rows(bank, {f, g})))
        model = fit(calib_recs)
        for r in predict(by_file[f], Index(bank, description, bank_rows(bank, {f}))):
            r["recognised"] = recognised(r, model)
            held_out.append(r)
    return held_out


def bootstrap(values, n=2000, seed=0):
    if not values:
        return (float("nan"), float("nan"))
    rng = np.random.default_rng(seed)
    means = [np.mean(rng.choice(values, len(values))) for _ in range(n)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def report(description, recs, n_truth_parts, n_sep_parts):
    glyph = [r for r in recs if not r["sep"]]
    g_rec = [r for r in glyph if r["recognised"]]
    g_n = n_truth_parts - n_sep_parts
    rec = [r for r in recs if r["recognised"]]
    right = [r["correct"] for r in rec]
    prec = np.mean(right) if rec else float("nan")
    lo, hi = bootstrap(right)
    top1 = np.mean([r["correct"] for r in recs if r["part"] == "letter"])
    line = (f"{description:7} letter top-1 {top1:.0%} | recognised {len(rec)}/{n_truth_parts} parts "
            f"(coverage {len(rec) / n_truth_parts:.0%}) | precision {prec:.0%} [95% CI {lo:.0%}-{hi:.0%}], {sum(right)} right")
    gp = np.mean([r["correct"] for r in g_rec]) if g_rec else float("nan")
    glo, ghi = bootstrap([r["correct"] for r in g_rec])
    g_top1 = np.mean([r["correct"] for r in glyph if r["part"] == "letter"])
    g_top3 = np.mean([r["in_top3"] for r in glyph if r["part"] == "letter"])
    line += (f"\n        glyphs only (no separators): letter top-1 {g_top1:.0%}, in top 3 {g_top3:.0%} | recognised {len(g_rec)}/{g_n} parts "
             f"(coverage {len(g_rec) / g_n:.0%}) | precision {gp:.0%} [95% CI {glo:.0%}-{ghi:.0%}]")
    if rec and prec < TARGET:
        line += f"\n        PRECISION IS BELOW THE {TARGET:.0%} TARGET on held-out lines."
    if g_rec and gp < TARGET:
        line += f"\n        GLYPH PRECISION IS BELOW THE {TARGET:.0%} TARGET on held-out lines."
    print(line)
    return dict(description=description, top1=top1, recognised=len(rec), right=int(sum(right)), coverage=len(rec) / n_truth_parts,
                precision=prec, glyph_coverage=len(g_rec) / g_n, glyph_precision=gp, glyph_top3=g_top3, wrong=[r for r in rec if not r["correct"]])


def main(do_fit=False):
    lines, bank = lines_and_truth(), load()
    readable = [t for l in lines for t in l["truth"].values() if t is not None]
    n_truth = 2 * len(readable)  # letter + signs per readable unit
    n_sep = 2 * sum(1 for t in readable if t[0] == (SEPARATOR,))
    results = [report(d, evaluate(lines, bank, d), n_truth, n_sep) for d in DESCRIPTIONS]
    # must meet the target overall and on glyphs (no glyph recognitions = nothing claimed, which passes);
    # then the best suggestions win: glyphs are mostly suggestions, so "is the answer among the 3 shown" matters most
    ok = [r for r in results if r["precision"] >= TARGET and not r["glyph_precision"] < TARGET]
    best = max(ok or results, key=lambda r: (r["glyph_top3"], r["glyph_coverage"]))
    print(f"chosen: {best['description']}" + ("" if ok else " (none met the precision target)"))
    if do_fit:
        d = best["description"]
        recs = []
        for l in lines:  # every line predicted without itself: out-of-fold records for the final calibration
            recs += predict(l, Index(bank, d, bank_rows(bank, {l["file"]})))
        model = fit(recs)
        model["description"] = d
        model["bank_fp"], model["gt_sha"] = fingerprint(bank), bank["gt_sha"]
        MODEL.write_text(json.dumps(model, indent=1), encoding="utf-8")
        taus = ", ".join(f"{p}/{k} {model[p][k]['tau']:.2f}" for p in PARTS for k in ("sep", "glyph"))
        print(f"wrote {MODEL.relative_to(ROOT)}: tau {taus}")
    return results


if __name__ == "__main__":
    main("--fit" in sys.argv)
