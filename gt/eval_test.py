"""CER on the held-out test lines (p10 l6, p11 l6): the number the retro reports.

usage: python -X utf8 gt/eval_test.py [--log]     (--log appends the numbers to gt/results.jsonl)

Run it once, after the labelling rounds (PLAN chunk 7): looking at it earlier would let it steer choices.
The model is data/model.json as committed (fitted on dev lines only); the bank never holds test lines (bank.py),
which is checked here. Same three setups and two CERs as eval_cer.py. Caveat for the retro: the test truth was
made with Claude's suggestions shown (log 80-81), so it is held-out but not independent of Claude's reading.
"""
import datetime, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import file_sha, fingerprint, load, GT_FILE  # noqa: E402
from khojki.recognise import Index, check_model, load_model  # noqa: E402
import eval_cer as EC  # noqa: E402
import eval_recognise as ER  # noqa: E402


def run():
    lines, bank, model = ER.lines_and_truth("test"), load(), load_model()
    check_model(model, bank)
    test_files = {l["file"] for l in lines}
    assert len(ER.bank_rows(bank, test_files)) == len(bank["label"]), "a test line is in the bank"
    index = Index(bank, model["description"])
    rows = []
    for line in lines:
        hyp = {"units": EC.oracle_units(line, index, model), "lines": EC.own_split(line, index, model)}
        hyp["pipeline"] = EC.own_split(line, index, model, *EC.pipeline_line(line))
        rows.append({"file": line["file"], "ref": EC.reference(line), "hyp": hyp})
    return rows


def main(log=False):
    rows = run()
    results = {}
    for setup in EC.SETUPS:
        for k, kind in ((0, "strict"), (1, "top-1")):
            c, d, n = EC.totals(rows, setup, k)
            results[f"test_cer_{setup}_{kind}"] = round(c, 4)
            print(f"{setup:9} {kind:6} {c:6.1%} ({d}/{n})")
    for r in rows:
        print(f"{r['file']}: pipeline top-1 {EC.totals([r], 'pipeline', 1)[0]:.1%}")
    if log:
        row = {"time": datetime.datetime.now().isoformat(timespec="seconds"),
               "commit": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
               "what": "eval_test", "gt_sha": file_sha(GT_FILE)[:16], "bank_fp": fingerprint(load()), **results}
        with open(ROOT / "gt" / "results.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    return rows, results


if __name__ == "__main__":
    main("--log" in sys.argv)
