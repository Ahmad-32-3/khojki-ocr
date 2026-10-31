"""Recheck page for one confusion family: every glyph whose answer or pipeline guess has one of the given letters.

usage: python -X utf8 gt/build_recheck.py [hex ...]     default 11224 1121D 11210 11221 (MA, DHA, JA, BA)  -> gt/recheck.html
Open http://localhost:8765/recheck.html (gt/server.py). Saving writes gt/review/recheck.json; nothing changes
the review files until those answers are applied (log 84).
"""
import json, sys, unicodedata
from pathlib import Path

GT = Path(__file__).resolve().parent
sys.path.insert(0, str(GT.parent))
from freeze_gt import answer  # noqa: E402
from khojki.labels import from_hex, name  # noqa: E402
from khojki.render import render  # noqa: E402
from segment import boxes_for  # noqa: E402
import base64, cv2  # noqa: E402

LETTERS = [int(h, 16) for h in sys.argv[1:]] or [0x11224, 0x1121D, 0x11210, 0x11221]
SIGNS = [(), (0x1122E,), (0x1122F,), (0x1122C,), (0x11232,)]  # alone, +II, +U, +AA, +O: the forms seen so far


def png64(img):
    return base64.b64encode(cv2.imencode(".png", 255 - img if img.mean() < 128 else img)[1]).decode()


def items():
    out = []
    for f in sorted(GT.glob("claude_lattice_*.json")):
        lat = json.loads(f.read_text(encoding="utf-8"))
        review = GT / "review" / f"{Path(lat['file']).stem}.json"
        if not review.exists():
            continue
        decisions = json.loads(review.read_text(encoding="utf-8"))["decisions"]
        boxes = boxes_for(lat)
        for i, span in enumerate(lat["spans"]):
            d = decisions.get(str(i)) or {}
            text = answer(d)
            guess = next((r["cps"] for r in span["readings"] if r["cps"] != ["?"]), None)
            mine = text and ord(text[0]) in LETTERS
            theirs = guess and from_hex(guess)[0] in LETTERS
            if not (mine or theirs):
                continue
            bb = [boxes[b] for b in span["boxes"]]
            out.append({"file": lat["file"], "span": i, "split": lat.get("split", "dev"),
                        "box": [min(b[0] for b in bb), max(b[1] for b in bb), min(b[2] for b in bb), max(b[3] for b in bb)],
                        "answer": name([ord(c) for c in text]) if text else "open",
                        "answer_cps": [f"U+{ord(c):04X}" for c in text] if text else ["?"],
                        "guess": name(from_hex(guess)) if guess else "-", "comment": d.get("comment", "")})
    return out


def main():
    refs = [{"name": name((l,) + s), "png": png64(render([l, *s]))} for s in SIGNS for l in LETTERS]
    data = items()
    page = (GT / "recheck_template.html").read_text(encoding="utf-8")
    page = page.replace("__REFS__", json.dumps(refs)).replace("__ITEMS__", json.dumps(data, ensure_ascii=False))
    page = page.replace("__LETTERS__", json.dumps([[f"U+{l:04X}", unicodedata.name(chr(l)).split()[-1]] for l in LETTERS]))
    (GT / "recheck.html").write_text(page, encoding="utf-8")
    print(f"recheck.html: {len(data)} glyphs, {len(refs)} reference drawings")


if __name__ == "__main__":
    main()
