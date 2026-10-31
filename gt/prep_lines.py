"""Prepare new lines for review (chunk 7): crop with the pipeline's own line finder, write a lattice.

usage: python -X utf8 gt/prep_lines.py <page> <line> [<line> ...] [--test]
  --test   blind test line: no suggestions at all (every span shows only "?"); marked split "test", so it never
           enters the example bank and is never used to tune anything (PLAN chunk 7, log 78)
  default  a dev line pre-filled with the pipeline's own suggestions/recognitions, for the labelling rounds
Writes gt/lines/pNN_lMM.png (gitignored), gt/claude_lattice_pNN_lMM.json, and the crop's page position to
gt/lines_index.json. Line numbers are the line finder's order on the page (1 = top).
Spans follow the pipeline's own split of the boxes; a reviewer can still mark "box is wrong".
"""
import json, sys
from pathlib import Path

import cv2

GT = Path(__file__).resolve().parent
ROOT = GT.parent
sys.path.insert(0, str(ROOT))
from khojki.bank import load  # noqa: E402
from khojki.glyphs import glyph_atoms  # noqa: E402
from khojki.lines import find_lines  # noqa: E402
from khojki.pipeline import pdf_page  # noqa: E402
from khojki.recognise import Index, load_model, recognise_atoms  # noqa: E402

PDF = ROOT / "data" / "sample_khojki_script_vatiations.pdf"
INDEX = GT / "lines_index.json"


def readings(unit):
    """Lattice readings from one pipeline unit: up to 3 options (letter option + best signs), scores on the
    0.05 grid that check_lattice.py expects, '?' taking the rest."""
    sign = unit["signs"]
    sign_cps = sign["cps"] if sign["status"] == "recognised" else sign["options"][0]["cps"]
    letter = unit["letter"]
    opts = [(letter["cps"], letter["conf"])] if letter["status"] == "recognised" else [(o["cps"], o["conf"]) for o in letter["options"][:3]]
    out, total = [], 0.0
    for cps, conf in opts:
        c = min(round(conf * 20) / 20, round(1 - total - 0.05, 2))
        if c <= 0:
            continue
        why = "pipeline: recognised" if letter["status"] == "recognised" else "pipeline suggestion (calibrated)"
        out.append({"cps": cps + sign_cps, "conf": c, "why": why})
        total = round(total + c, 2)
    comps = unit.get("components")
    c = min(max(0.05, min(p["conf"] for p in comps) // 0.05 * 0.05), round(1 - total - 0.05, 2)) if comps else 0
    if c > 0:  # unknown as a whole: offer the pieces we can read, named
        out.append({"cps": [x for p in comps for x in p["cps"]], "conf": round(c, 2),
                    "why": "components: " + " + ".join(p["name"] for p in comps)})
        total = round(total + c, 2)
    out.append({"cps": ["?"], "conf": round(1 - total, 2), "why": ""})
    return out


def prepare(page, line_no, test=False, bank=None, model=None):
    gray = pdf_page(PDF, page)
    x0, y0, x1, y1 = find_lines(gray)[line_no - 1]
    name = f"p{page:02d}_l{line_no:02d}"
    crop = gray[y0:y1, x0:x1]
    (GT / "lines").mkdir(exist_ok=True)
    cv2.imwrite(str(GT / "lines" / f"{name}.png"), crop)
    atoms = glyph_atoms(crop)
    model = model if model is not None else (load_model() or {})
    units = recognise_atoms(atoms, Index(bank if bank is not None else load(), model.get("description", "hog")), model)["units"]
    if test:  # blind: keep the pipeline's grouping of boxes, show nothing about what they are
        spans = [{"boxes": u["boxes"], "readings": [{"cps": ["?"], "conf": 1.0, "why": "blind test line: no suggestions"}]} for u in units]
    else:
        spans = [{"boxes": u["boxes"], "readings": readings(u)} for u in units]
    lat = {"file": f"lines/{name}.png", "version": 3, "segmenter": "pipeline", "split": "test" if test else "dev",
           "blind": test, "spans": spans,
           "boxes": [list(map(int, b[:4])) + [b[4]] for b in atoms["boxes"]]}  # frozen: later stage B changes can't shift them
    (GT / f"claude_lattice_{name}.json").write_text(json.dumps(lat, indent=1), encoding="utf-8")
    index = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    index[lat["file"]] = {"page": page, "x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
    INDEX.write_text(json.dumps(index, indent=1, sort_keys=True), encoding="utf-8")
    print(f"{lat['file']}: {len(spans)} spans, {'blind test' if test else 'dev, pre-filled'}")
    return lat


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    page, lines = int(args[0]), [int(a) for a in args[1:]]
    for n in lines:
        prepare(page, n, test="--test" in sys.argv)
