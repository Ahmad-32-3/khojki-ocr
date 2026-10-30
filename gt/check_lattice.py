"""Sanity checks for claude_lattice_l*.json, run before build_review.py.

usage: python -X utf8 gt/check_lattice.py            -> exit 1 on errors; warnings are printed but don't fail
errors:   scores don't sum to 1, a score isn't a multiple of 0.05, unknown code point, a box no reading covers
warnings: a `why` names a letter/sign (e.g. "HA+U+anusvara") that isn't in that reading's code points (PROCESS_LOG #49)
"""
import json, re, sys, unicodedata
from pathlib import Path

from segment import glyph_boxes

GT = Path(__file__).resolve().parent
MARKS = {"ANUSVARA", "NUKTA", "VIRAMA", "SHADDA", "SUKUN"}


def short(cp):
    """U+1122F -> 'U', U+11229 -> 'SA', U+11234 -> 'ANUSVARA'."""
    return unicodedata.name(chr(int(cp[2:], 16))).split(" ")[-1]


def check(lat, boxes):
    errors, warnings = [], []
    covered = set()
    for i, s in enumerate(lat["spans"]):
        covered |= set(s["boxes"])
        total = sum(r["conf"] for r in s["readings"])
        if abs(total - 1) > 1e-6:
            errors.append(f"glyph {i + 1}: scores sum to {total:.2f}")
        for r in s["readings"]:
            if abs(r["conf"] * 20 - round(r["conf"] * 20)) > 1e-6:
                errors.append(f"glyph {i + 1}: score {r['conf']} isn't a multiple of 0.05")
            cps = [c for c in r["cps"] if c != "?"]
            try:
                names = {short(c) for c in cps}
            except (ValueError, KeyError):
                errors.append(f"glyph {i + 1}: unknown code point in {r['cps']}")
                continue
            # only the first X+Y group: later ones usually describe another line ("like line 4's ...")
            m = re.search(r"\b[A-Za-z]+(?:\+[A-Za-z]+)+\b", r["why"])
            if m and cps:
                want = {t.upper() for t in m.group().split("+")}
                missing = {t for t in want if t not in names and (t in MARKS or len(t) <= 4)}
                if missing:
                    warnings.append(f"glyph {i + 1}: why says {m.group()} but code points are {'+'.join(sorted(names))}")
    orphans = set(range(len(boxes))) - covered
    if orphans:
        errors.append(f"boxes no reading covers: {sorted(orphans)}")
    return errors, warnings


def demo():
    lat = {"spans": [{"boxes": [0], "readings": [{"cps": ["U+1122A", "U+1122D"], "conf": 0.3, "why": "HA+U+anusvara"},
                                                 {"cps": ["?"], "conf": 0.7, "why": ""}]}]}
    e, w = check(lat, [[0, 1, 0, 1, "glyph"]])
    assert not e and len(w) == 1, (e, w)  # the line 9 glyph 9 slip
    lat["spans"][0]["readings"][0]["cps"] = ["U+1122A", "U+1122F", "U+11234"]
    assert check(lat, [[0, 1, 0, 1, "glyph"]]) == ([], [])
    e, _ = check(lat, [[0, 1, 0, 1, "glyph"]] * 2)
    assert e == ["boxes no reading covers: [1]"]


if __name__ == "__main__":
    demo()
    bad = 0
    for f in sorted(GT.glob("claude_lattice_l*.json")):
        lat = json.loads(f.read_text(encoding="utf-8"))
        e, w = check(lat, glyph_boxes(GT / lat["file"]))
        bad += len(e)
        for msg in e:
            print(f"ERROR {f.name}: {msg}")
        for msg in w:
            print(f"warn  {f.name}: {msg}")
    print("ok" if not bad else f"{bad} errors")
    sys.exit(1 if bad else 0)
