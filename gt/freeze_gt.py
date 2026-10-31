"""Freeze the ground truth from the review decisions.

usage: python -X utf8 gt/freeze_gt.py      -> gt/gt.json, gt/gt.txt   (the version number is inside gt.json)
Each unit stores its pixel box, not just box numbers, so the truth doesn't change if the segmenter does.
A unit nobody could read is kept as status "open" (written "?" in the .txt) and left out of CER later.

Versions:
  1  first freeze (log 59)
  2  marks put in Unicode order: nukta straight after its letter (log 68). Changes one unit: line 5 glyph 19.
  3  adds the two blind test lines p10_l06 and p11_l06 (split "test", log 82). Dev lines unchanged.
"""
import json, sys, unicodedata
from pathlib import Path

GT = Path(__file__).resolve().parent
sys.path.insert(0, str(GT.parent))
from khojki.labels import canonical, from_hex  # noqa: E402
from segment import boxes_for  # noqa: E402

VERSION = 3


def answer(decision):
    """Code points as text, or None for open. Missing decision and "?" both mean open."""
    if not decision or decision["cps"] == ["?"]:
        return None
    cps = canonical(from_hex(decision["cps"]))
    return unicodedata.normalize("NFC", "".join(map(chr, cps)))


def main():
    lines = []
    for f in sorted(GT.glob("claude_lattice_*.json")):
        lat = json.loads(f.read_text(encoding="utf-8"))
        stem = Path(lat["file"]).stem
        review = GT / "review" / f"{stem}.json"
        if not review.exists():
            print(f"skipped {lat['file']}: not reviewed yet")
            continue
        decisions = json.loads(review.read_text(encoding="utf-8"))["decisions"]
        boxes = boxes_for(lat)
        units = []
        for i, span in enumerate(lat["spans"]):
            text = answer(decisions.get(str(i)))
            bb = [boxes[b] for b in span["boxes"]]
            units.append({
                "text": text,
                "cps": None if text is None else [f"U+{ord(c):04X}" for c in text],
                "status": "open" if text is None else "ok",
                "bbox": [min(b[0] for b in bb), max(b[1] for b in bb), min(b[2] for b in bb), max(b[3] for b in bb)],
            })
        lines.append({"file": lat["file"], "split": lat.get("split", "dev"), "units": units})

    (GT / "gt.json").write_text(json.dumps({"version": VERSION, "lines": lines}, ensure_ascii=False, indent=1), encoding="utf-8")
    (GT / "gt.txt").write_text(
        "".join("".join(u["text"] or "?" for u in l["units"]) + "\n" for l in lines), encoding="utf-8")
    n = sum(len(l["units"]) for l in lines)
    ok = sum(u["status"] == "ok" for l in lines for u in l["units"])
    print(f"version {VERSION}: {len(lines)} lines, {n} units, {ok} ok, {n - ok} open")


if __name__ == "__main__":
    main()
