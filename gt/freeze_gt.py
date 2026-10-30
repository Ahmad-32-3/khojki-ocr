"""Freeze ground truth v1 from the review decisions.

usage: python -X utf8 gt/freeze_gt.py      -> gt/gt_v1.json, gt/gt_v1.txt
Each unit stores its pixel box, not just box numbers, so the truth doesn't change if the segmenter does.
A unit nobody could read is kept as status "open" (written "?" in the .txt) and left out of CER later.
"""
import json, unicodedata
from pathlib import Path

from segment import glyph_boxes

GT = Path(__file__).resolve().parent


def answer(decision):
    """Code points as text, or None for open. Missing decision and "?" both mean open."""
    if not decision or decision["cps"] == ["?"]:
        return None
    return unicodedata.normalize("NFC", "".join(chr(int(c[2:], 16)) for c in decision["cps"]))


def main():
    lines = []
    for f in sorted(GT.glob("claude_lattice_l*.json")):
        lat = json.loads(f.read_text(encoding="utf-8"))
        stem = Path(lat["file"]).stem
        decisions = json.loads((GT / "review" / f"{stem}.json").read_text(encoding="utf-8"))["decisions"]
        boxes = glyph_boxes(GT / lat["file"])
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
        lines.append({"file": lat["file"], "units": units})

    (GT / "gt_v1.json").write_text(json.dumps({"version": 1, "lines": lines}, ensure_ascii=False, indent=1), encoding="utf-8")
    (GT / "gt_v1.txt").write_text(
        "".join("".join(u["text"] or "?" for u in l["units"]) + "\n" for l in lines), encoding="utf-8")
    n = sum(len(l["units"]) for l in lines)
    ok = sum(u["status"] == "ok" for l in lines for u in l["units"])
    print(f"{len(lines)} lines, {n} units, {ok} ok, {n - ok} open")


if __name__ == "__main__":
    main()
