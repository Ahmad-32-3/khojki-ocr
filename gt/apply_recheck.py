"""Apply the letter recheck (gt/review/recheck.json) to the review decisions.

usage: python -X utf8 gt/apply_recheck.py      then freeze_gt.py
Button answers are applied as given. Answers you wrote only as notes (the page lost them, log 85) are in
FROM_NOTES, each with its note, so the reading of the note is on record. The old answer is kept as "was".
"""
import datetime, json
from pathlib import Path

GT = Path(__file__).resolve().parent
OUT = GT / "review"

FROM_NOTES = {  # key -> (cps, your note)
    "lines/p09_l03.png#15": (["U+1121E", "U+1122E"], "Na + II"),
    "lines/p09_l04.png#1": (["U+11219", "U+1122E"], "Ta + II"),
    "lines/p09_l05.png#19": (["U+1122A"], "Ha (95%) or Ha + E (5%)"),
    "lines/p10_l03.png#16": (["U+11219"], "Ta"),
    "lines/p11_l03.png#1": (["U+1121E", "U+1122E"], "Na + II"),
    "lines/p09_l04.png#17": (["?"], "No, if this was flipped along a vertical line such that the line goes through the "
                                    "middle of the 2 characters, then BA + I would be valid"),
}


def main():
    rc = json.loads((OUT / "recheck.json").read_text(encoding="utf-8"))["answers"]
    todo = {k: (a["cps"], a.get("note", "")) for k, a in rc.items() if a.get("cps")}
    todo.update(FROM_NOTES)
    now = datetime.datetime.now().isoformat(timespec="seconds")
    changed = 0
    for key, (cps, note) in sorted(todo.items()):
        file, span = key.split("#")
        path = OUT / f"{Path(file).stem}.json"
        rev = json.loads(path.read_text(encoding="utf-8"))
        old = rev["decisions"].get(span) or {}
        if old.get("cps") == cps:
            continue
        rev["decisions"][span] = {**old, "cps": cps, "rank": 0, "was": old.get("cps"), "recheck": now,
                                  "comment": (old.get("comment", "") + f"\nrecheck: {note}").strip() if note else old.get("comment", "")}
        path.write_text(json.dumps(rev, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"{key}: {old.get('cps')} -> {cps}")
        changed += 1
    print(f"{changed} answers changed")


if __name__ == "__main__":
    main()
