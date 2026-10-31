"""Checks on the real scans that FAIL (exit 1) on a regression, and log every run to gt/results.jsonl.

usage: python -X utf8 gt/check_real.py [--no-log]   (skips cleanly, exit 0, if the scans aren't on this machine)
  --no-log  don't append to results.jsonl (the pre-commit hook uses this, so a commit doesn't leave the log modified)
The unit tests use synthetic data because the scans aren't in the repo; this is the real-data tier.
Baselines are the results measured so far (PROCESS_LOG 61, 64, 72, 73, 77): a change may improve them, never worsen them.
"""
import datetime, json, subprocess, sys
from collections import Counter
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
PDF = ROOT / "data" / "sample_khojki_script_vatiations.pdf"
PDF_SHA = "99f373777e13ad01ccc7ff1ae067cb80a3de2bc22d96df6c7ab0a558f8d11f23"
RESULTS = ROOT / "gt" / "results.jsonl"

BASELINE = {
    "lines_right": 35,          # of 35 marked by eye on p9-p11, and nothing else kept
    "seps_found": 31,           # of 31 GT separators, with no false ones
    "glyph_boxes_ok": 59,       # GT glyphs in exactly one box (the rest are splits, recoverable)
    "sep_parts_recognised": 62,  # 31 separators x (letter, signs), all right
    "glyph_top3": 0.558,        # right letter among the 3 suggestions, held-out (0.494 before log 76)
    "cer_pipeline_top1": 0.486,  # whole pipeline, best guess per glyph, held-out (log 77, 83); may only go down
    "cer_pipeline_strict": 1.106,  # the text file as written, U+FFFD counted as errors
    "pipeline_lines": {"09": 11, "10": 12, "11": 12},
}
TARGET = 0.95


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def main(log=True):
    if not PDF.exists() or not (ROOT / "data" / "pages" / "p09.png").exists() or not (ROOT / "data" / "bank.npz").exists():
        print("check_real: scans or bank not on this machine, skipped")
        return 0
    from khojki.bank import file_sha, fingerprint, load, GT_FILE
    from khojki.lines import find_lines
    from khojki.pipeline import pdf_page, run_page
    from khojki.recognise import load_model
    from khojki.validate import problems
    import eval_glyphs, eval_lines, eval_recognise

    fails, m = [], {}

    def need(ok, what):
        if not ok:
            fails.append(what)

    # inputs: the right PDF, a valid GT, a bank built from this GT, a model fitted on this bank
    need(file_sha(PDF) == PDF_SHA, "PDF is not the expected file (SHA-256 differs)")
    gt = json.loads(GT_FILE.read_text(encoding="utf-8"))
    gt_problems = sum(len(problems(l, open_marker=True)) for l in (GT_FILE.with_suffix(".txt")).read_text(encoding="utf-8").splitlines())
    need(gt_problems == 0, f"ground truth has {gt_problems} Unicode problems")
    bank, model = load(), load_model()
    need(bank["gt_sha"] == file_sha(GT_FILE), "bank.npz was built from a different gt.json: rebuild with python -m khojki.bank")
    need(model is not None and model.get("bank_fp") == fingerprint(bank), "model.json was fitted on a different bank: refit")

    # stage A: lines, and every GT glyph inside a found line (the row-only score missed a crop error, log 61)
    lgt = json.loads((ROOT / "gt" / "lines_gt.json").read_text(encoding="utf-8"))
    right = 0
    for page in ("p09", "p10", "p11"):
        gray = cv2.imread(str(ROOT / "data" / "pages" / f"{page}.png"), cv2.IMREAD_GRAYSCALE)
        s = eval_lines.score(find_lines(gray), lgt[page]["text"], lgt[page]["skip"])
        right += s["right"]
        need(s["missed"] == s["merged"] == s["nontext_kept"] == s["stray"] == 0, f"{page} lines: {s}")
    m["lines_right"] = right
    need(right >= BASELINE["lines_right"], f"lines right {right} < {BASELINE['lines_right']}")
    outside = 0
    for line in (l for l in gt["lines"] if l.get("split", "dev") == "dev"):
        page, gx, gy = eval_glyphs.gt_crop_origin(line["file"])
        boxes = find_lines(page)
        for u in line["units"]:
            x0, x1, y0, y1 = u["bbox"]
            if not any(b[0] <= gx + x0 and gx + x1 <= b[2] and b[1] <= gy + y0 and gy + y1 <= b[3] for b in boxes):
                outside += 1
    m["gt_glyphs_outside_lines"] = outside
    need(outside == 0, f"{outside} GT glyphs fall outside every found line (a crop cuts text)")

    # stage B: glyph boxes
    c = Counter()
    for line in (l for l in gt["lines"] if l.get("split", "dev") == "dev"):
        c += eval_glyphs.score(line["units"], eval_glyphs.glyph_boxes(cv2.imread(str(ROOT / "gt" / line["file"]), cv2.IMREAD_GRAYSCALE)))
    m["seps_found"], m["glyph_boxes_ok"] = c[("sep", "ok")], c[("glyph", "ok")]
    need(c[("sep", "ok")] >= BASELINE["seps_found"] and c[("sep", "false")] == 0, f"separators: {dict(c)}")
    need(c[("glyph", "merge")] == c[("sep", "merge")] == 0, f"merges: {dict(c)}")
    need(c[("glyph", "ok")] >= BASELINE["glyph_boxes_ok"], f"glyph boxes ok {c[('glyph', 'ok')]} < {BASELINE['glyph_boxes_ok']}")

    # stage C: held-out recognition with the chosen description
    lines = eval_recognise.lines_and_truth()
    recs = eval_recognise.evaluate(lines, bank, model["description"])
    sep_rec = [r for r in recs if r["sep"] and r["recognised"]]
    gly = [r for r in recs if not r["sep"]]
    gly_rec = [r for r in gly if r["recognised"]]
    m["sep_parts_recognised"] = sum(r["correct"] for r in sep_rec)
    m["glyph_parts_recognised"] = len(gly_rec)
    m["glyph_precision"] = sum(r["correct"] for r in gly_rec) / len(gly_rec) if gly_rec else None
    m["glyph_top3"] = round(sum(r["in_top3"] for r in gly if r["part"] == "letter") / sum(r["part"] == "letter" for r in gly), 3)
    need(all(r["correct"] for r in sep_rec) and m["sep_parts_recognised"] >= BASELINE["sep_parts_recognised"], "separator recognition regressed")
    need(not gly_rec or m["glyph_precision"] >= TARGET, f"glyph precision {m['glyph_precision']} below {TARGET}")
    need(m["glyph_top3"] >= BASELINE["glyph_top3"], f"suggestion quality {m['glyph_top3']} < {BASELINE['glyph_top3']}")

    # CER on the 6 GT lines, leave one line out (eval_cer.py)
    import eval_cer
    rows = eval_cer.run(model["description"])
    m["cer_pipeline_top1"] = round(eval_cer.totals(rows, "pipeline", 1)[0], 4)
    m["cer_pipeline_strict"] = round(eval_cer.totals(rows, "pipeline", 0)[0], 4)
    need(m["cer_pipeline_top1"] <= BASELINE["cer_pipeline_top1"] + 1e-9, f"top-1 CER {m['cer_pipeline_top1']} > {BASELINE['cer_pipeline_top1']}")
    need(m["cer_pipeline_strict"] <= BASELINE["cer_pipeline_strict"] + 1e-9, f"strict CER {m['cer_pipeline_strict']} > {BASELINE['cer_pipeline_strict']}")

    # stage D: the whole pipeline from the PDF
    for p, n in BASELINE["pipeline_lines"].items():
        try:
            r = run_page(pdf_page(PDF, int(p)), f"p{p}", bank, model)
        except RuntimeError as e:  # e.g. the stale-model guard: report it, don't crash the check
            need(False, f"pipeline p{p} refused to run: {e}")
            continue
        bad = sum(len(l["problems"]) for l in r["lines"])
        need(len(r["lines"]) == n and bad == 0, f"pipeline p{p}: {len(r['lines'])} lines (want {n}), {bad} validation problems")

    row = {"time": datetime.datetime.now().isoformat(timespec="seconds"), "commit": git("rev-parse", "--short", "HEAD"),
           "uncommitted_changes": bool(git("status", "--porcelain", "--untracked-files=no")),
           "gt_version": gt["version"], "gt_sha": file_sha(GT_FILE)[:16], "bank_fp": fingerprint(bank),
           "description": model["description"], **m, "passed": not fails, "failures": fails}
    if log:
        with open(RESULTS, "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    print(json.dumps(m))
    print("check_real: PASSED" if not fails else "check_real: FAILED\n  " + "\n  ".join(fails))
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main(log="--no-log" not in sys.argv))
