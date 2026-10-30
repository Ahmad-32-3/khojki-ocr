"""CER on the 6 ground-truth lines, leave one line out, split by stage.

usage: python -X utf8 gt/eval_cer.py [--log]     (--log appends the numbers to gt/results.jsonl)

Three setups, each with the held-out line's own examples removed from the bank, and with calibration and tau
fitted on the other lines only (nested, as in eval_recognise.py):
  units     recognition on the ground-truth glyph groups      -> recognition errors only
  lines     + the program's own box split, on GT line crops   -> adds segmentation errors
  pipeline  + lines found on the PDF page                     -> adds line-finding errors
Two CERs each:
  strict    the text file as written: every U+FFFD counts as an error
  top-1     the best guess for every part, ignoring the confidence bar (comparable to other OCR systems)
GT glyphs nobody could read ('?') are left out of both sides: the output units on them are dropped.
"""
import datetime, json, subprocess, sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import file_sha, fingerprint, load, normalise, unit_mask, GT_FILE  # noqa: E402
from khojki.cer import align  # noqa: E402
from khojki.glyphs import glyph_atoms  # noqa: E402
from khojki.labels import SEPARATOR, name  # noqa: E402
from khojki.lines import find_lines  # noqa: E402
from khojki.recognise import REPLACEMENT, Index, decide, group, load_model, part_scores, recognise_atoms  # noqa: E402
import eval_glyphs  # noqa: E402
import eval_recognise as ER  # noqa: E402

SETUPS = ("units", "lines", "pipeline")


def as_text(cps):
    return "".join(map(chr, cps))


def unit_texts(unit):
    """(strict, top-1) text of one recognise_atoms() unit."""
    top1 = ""
    for part in ("letter", "signs"):
        d = unit[part]
        cps = d["cps"] if d["status"] == "recognised" else d["options"][0]["cps"]
        top1 += "".join(chr(int(c[2:], 16)) for c in cps)
    return unit["text"], top1


def oracle_units(line, index, model):
    """Recognition on the GT glyph groups themselves (segmentation taken as perfect)."""
    strict = top1 = ""
    for idx, truth in sorted(line["truth"].items()):
        if truth is None:
            continue
        atoms = line["atoms"]
        img, meta = normalise(unit_mask(atoms, list(idx)), atoms["tall"])
        opts = part_scores(*index.votes(img, meta, atoms["boxes"][idx[0]][4]))
        for part in ("letter", "signs"):
            m = model[part][group(opts)]
            d = decide(opts[part], m["calib"], m["tau"])
            strict += as_text(int(c[2:], 16) for c in d["cps"]) if d["status"] == "recognised" else REPLACEMENT
            top1 += as_text(opts[part][0][0])
    return strict, top1


def open_ranges(line, atoms_boxes):
    """x-ranges (GT crop coordinates) of GT glyphs nobody could read."""
    return [(min(atoms_boxes[i][0] for i in idx), max(atoms_boxes[i][1] for i in idx)) for idx, t in line["truth"].items() if t is None]


def own_split(line, index, model, atoms=None, shift=0):
    """Recognition with the program's own split. atoms/shift: a different crop of the same line (pipeline),
    shifted into GT crop x-coordinates. Units centred on an unreadable GT glyph are dropped."""
    atoms = atoms or line["atoms"]
    drop = open_ranges(line, line["atoms"]["boxes"])
    strict = top1 = ""
    for u in recognise_atoms(atoms, index, model)["units"]:
        cx = shift + (min(atoms["boxes"][i][0] for i in u["boxes"]) + max(atoms["boxes"][i][1] for i in u["boxes"])) / 2
        if any(a <= cx < b for a, b in drop):
            continue
        s, t = unit_texts(u)
        strict, top1 = strict + s, top1 + t
    return strict, top1


def pipeline_line(line, method="otsu"):
    """Atoms of stage A's own crop of this line, and the x-shift into GT crop coordinates."""
    page, gx, gy = eval_glyphs.gt_crop_origin(line["file"])
    gh = cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE).shape[0]
    lx0, ly0, lx1, ly1 = next(l for l in find_lines(page, method) if l[1] <= gy + gh / 2 < l[3])
    return glyph_atoms(page[ly0:ly1, lx0:lx1], method), lx0 - gx


def reference(line):
    return "".join(as_text(t[0] + t[1]) for _, t in sorted(line["truth"].items()) if t is not None)


def run(description=None):
    lines, bank = ER.lines_and_truth(), load()
    description = description or (load_model() or {}).get("description", "hog")
    by_file = {l["file"]: l for l in lines}
    out = []  # per line: reference and the six hypotheses
    for f, inner in ER.folds(lines):
        recs = []
        for g in inner:
            recs += ER.predict(by_file[g], Index(bank, description, ER.bank_rows(bank, {f, g})))
        model = ER.fit(recs)
        index = Index(bank, description, ER.bank_rows(bank, {f}))
        line = by_file[f]
        hyp = {"units": oracle_units(line, index, model), "lines": own_split(line, index, model)}
        p_atoms, shift = pipeline_line(line)
        hyp["pipeline"] = own_split(line, index, model, p_atoms, shift)
        out.append({"file": f, "ref": reference(line), "hyp": hyp})
    return out


def totals(rows, setup, k, keep=lambda c: True):
    """Summed edit distance / summed reference length. k = 0 strict, 1 top-1. keep filters characters."""
    dist = n = 0
    for r in rows:
        ref = "".join(c for c in r["ref"] if keep(c))
        hyp = "".join(c for c in r["hyp"][setup][k] if keep(c))
        dist += align(ref, hyp)[0]
        n += len(ref)
    return dist / n, dist, n


def bootstrap(rows, setup, k, n=2000, seed=0):
    rng = np.random.default_rng(seed)
    vals = [totals([rows[i] for i in rng.integers(0, len(rows), len(rows))], setup, k)[0] for _ in range(n)]
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main(log=False):
    rows = run()
    no_sep = lambda c: c != chr(SEPARATOR)
    results = {}
    print(f"{'setup':9} {'':6} {'CER':>6} {'(errors/chars)':>15}  95% CI (lines resampled)   letters only (no separators)")
    for setup in SETUPS:
        for k, kind in ((0, "strict"), (1, "top-1")):
            c, d, n = totals(rows, setup, k)
            lo, hi = bootstrap(rows, setup, k)
            cl, dl, nl = totals(rows, setup, k, no_sep)
            results[f"cer_{setup}_{kind}"] = round(c, 4)
            results[f"cer_{setup}_{kind}_letters"] = round(cl, 4)
            print(f"{setup:9} {kind:6} {c:6.1%} {f'({d}/{n})':>15}  {lo:5.1%}-{hi:5.1%}                {cl:6.1%} ({dl}/{nl})")
    # per-stage share of the top-1 errors: what each stage adds
    u, l, p = (totals(rows, s, 1)[1] for s in SETUPS)
    print(f"\ntop-1 errors by stage: recognition {u}, + segmentation {l - u}, + line finding {p - l} (total {p})")
    results.update(stage_recognition=u, stage_segmentation=l - u, stage_lines=p - l)
    conf = Counter()
    for r in rows:
        for op, a, b in align(r["ref"], r["hyp"]["units"][1])[1]:
            if op != "ok":
                conf[(op, a, b)] += 1
    fmt = lambda ch: name((ord(ch),)) if ch else "-"
    print("most common top-1 recognition errors (true -> read):",
          ", ".join(f"{fmt(a)}->{fmt(b)} x{n}" for (op, a, b), n in conf.most_common(8)))
    if log:
        row = {"time": datetime.datetime.now().isoformat(timespec="seconds"),
               "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
               "what": "eval_cer", "gt_sha": file_sha(GT_FILE)[:16], "bank_fp": fingerprint(load()), **results}
        with open(ROOT / "gt" / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return rows, results


if __name__ == "__main__":
    main("--log" in sys.argv)
