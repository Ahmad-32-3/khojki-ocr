"""The whole pipeline: page image (or a PDF page) -> Khojki Unicode, offline.

usage: python -X utf8 -m khojki.pipeline <page.png | file.pdf --page N> [--out out/]
  -> out/<name>.txt   one line of text per printed line; U+FFFD where a part wasn't recognised
     out/<name>.json  every line and unit with page coordinates, recognitions and suggestions, validation problems
     out/<name>.xml   PAGE-XML 2019 (opens in eScriptorium / Transkribus-style tools)
Stages: A lines (khojki.lines) -> B glyph boxes (khojki.glyphs) -> C recognition (khojki.recognise) -> D validation.
"""
import argparse, datetime, json, time
from pathlib import Path
from xml.sax.saxutils import escape

import cv2
import numpy as np

from khojki.bank import load
from khojki.glyphs import glyph_atoms
from khojki.labels import SEPARATOR
from khojki.lines import find_lines
from khojki.recognise import Index, check_model, load_model, recognise_atoms
from khojki.validate import problems

PAGE_NS = "http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15"


def run_page(gray, name, bank=None, model=None):
    model = model if model is not None else (load_model() or {})
    bank = bank if bank is not None else load()
    check_model(model, bank)
    index = Index(bank, model.get("description", "hog"))
    lines = []
    for x0, y0, x1, y1 in find_lines(gray):
        atoms = glyph_atoms(gray[y0:y1, x0:x1])
        rec = recognise_atoms(atoms, index, model)
        for u in rec["units"]:  # unit boxes in page coordinates
            bb = [atoms["boxes"][i] for i in u["boxes"]]
            u["bbox"] = [x0 + min(b[0] for b in bb), y0 + min(b[2] for b in bb), x0 + max(b[1] for b in bb), y0 + max(b[3] for b in bb)]
        lines.append({"bbox": [x0, y0, x1, y1], "text": rec["text"], "units": rec["units"],
                      "problems": [{"at": i, "what": m} for i, m in problems(rec["text"])]})
    h, w = gray.shape
    return {"page": name, "width": w, "height": h, "lines": lines}


def to_txt(result):
    return "".join(l["text"] + "\n" for l in result["lines"])


def _points(x0, y0, x1, y1):
    return f"{x0},{y0} {x1},{y0} {x1},{y1} {x0},{y1}"


def to_page_xml(result):
    """PAGE-XML. Per glyph, TextEquiv index 1 holds the committed text (U+FFFD where unrecognised) with the
    lowest confidence of its recognised parts (0 if any part is a suggestion). Suggestions follow as further
    TextEquiv entries, index 2+, comments="suggestion: letter|signs", so a tool never mistakes one for the answer.
    A glyph unknown as a whole but made of readable pieces adds one more, comments="suggestion: components A + B"."""
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat()
    out = [f'<?xml version="1.0" encoding="UTF-8"?>',
           f'<PcGts xmlns="{PAGE_NS}">',
           f'  <Metadata><Creator>khojki pipeline</Creator><Created>{now}</Created><LastChange>{now}</LastChange></Metadata>',
           f'  <Page imageFilename="{escape(result["page"])}" imageWidth="{result["width"]}" imageHeight="{result["height"]}">']
    if result["lines"]:
        xs = [l["bbox"] for l in result["lines"]]
        region = (min(b[0] for b in xs), min(b[1] for b in xs), max(b[2] for b in xs), max(b[3] for b in xs))
        out.append(f'    <TextRegion id="r1"><Coords points="{_points(*region)}"/>')
        for li, l in enumerate(result["lines"], 1):
            out.append(f'      <TextLine id="r1_l{li}"><Coords points="{_points(*l["bbox"])}"/>')
            for gi, u in enumerate(l["units"], 1):
                parts = [u["letter"], u["signs"]]
                conf = min(p["conf"] for p in parts) if all(p["status"] == "recognised" for p in parts) else 0
                out.append(f'        <Glyph id="r1_l{li}_g{gi}"><Coords points="{_points(*u["bbox"])}"/>')
                out.append(f'          <TextEquiv index="1" conf="{conf}"><Unicode>{escape(u["text"])}</Unicode></TextEquiv>')
                k = 2
                for part in ("letter", "signs"):
                    for o in u[part].get("options", []):
                        txt = "".join(chr(int(c[2:], 16)) for c in o["cps"])
                        out.append(f'          <TextEquiv index="{k}" conf="{o["conf"]}" comments="suggestion: {part}"><Unicode>{escape(txt)}</Unicode></TextEquiv>')
                        k += 1
                if u.get("components"):  # unknown as a whole: the pieces we can read, joined
                    txt = "".join(chr(int(c[2:], 16)) for p in u["components"] for c in p["cps"])
                    conf = min(p["conf"] for p in u["components"])
                    names = " + ".join(p["name"] for p in u["components"])
                    out.append(f'          <TextEquiv index="{k}" conf="{conf}" comments="suggestion: components {escape(names)}"><Unicode>{escape(txt)}</Unicode></TextEquiv>')
                out.append('        </Glyph>')
            out.append(f'        <TextEquiv><Unicode>{escape(l["text"])}</Unicode></TextEquiv>')
            out.append('      </TextLine>')
        out.append(f'      <TextEquiv><Unicode>{escape(to_txt(result).rstrip())}</Unicode></TextEquiv>')
        out.append('    </TextRegion>')
    out += ['  </Page>', '</PcGts>', '']
    return "\n".join(out)


def pdf_page(pdf, page):
    """The PDF page's own scan image (no resampling), as grayscale."""
    import pymupdf
    doc = pymupdf.open(pdf)
    pix = pymupdf.Pixmap(doc, doc[page - 1].get_images()[0][0])
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)
    return cv2.cvtColor(img[:, :, :3], cv2.COLOR_RGB2GRAY) if pix.n >= 3 else img[:, :, 0].copy()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("input")
    ap.add_argument("--page", type=int, help="page number, when the input is a PDF")
    ap.add_argument("--out", default="out")
    a = ap.parse_args(argv)
    start = time.perf_counter()
    src = Path(a.input)
    # bad input gets one plain line, not a traceback
    if not src.is_file():
        ap.error(f"no such file: {src} (put the scans in khojki-scans/)")
    if src.suffix.lower() == ".pdf":
        if a.page is None:
            ap.error("a PDF needs --page N")
        gray, name = pdf_page(src, a.page), f"{src.stem}_p{a.page:02d}"
    else:
        gray, name = cv2.imread(str(src), cv2.IMREAD_GRAYSCALE), src.stem
        if gray is None:
            ap.error(f"can't read {src} as an image (use a PNG, JPEG or TIFF page, or a PDF with --page)")
    result = run_page(gray, name)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.txt").write_text(to_txt(result), encoding="utf-8")
    (out / f"{name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / f"{name}.xml").write_text(to_page_xml(result), encoding="utf-8")
    print(summary(result, out / name, time.perf_counter() - start))
    return result


def summary(result, stem, seconds):
    """What the run found and how sure it was, in plain words. Accuracy needs an answer key, so it points to that."""
    units = [u for l in result["lines"] for u in l["units"]]
    sure = lambda u: u["letter"]["status"] == "recognised"
    seps = [u for u in units if sure(u) and u["letter"]["cps"] == [f"U+{SEPARATOR:04X}"]]
    glyphs = [u for u in units if u not in seps]
    bad = sum(len(l["problems"]) for l in result["lines"])
    return "\n".join([
        f"{result['page']}  ({seconds:.1f} s)",
        f"  Lines found              {len(result['lines'])}",
        f"  Word separators found    {len(seps)}  (written as text)",
        f"  Characters found         {len(glyphs)}",
        f"    written as text        {sum(sure(u) for u in glyphs)}  (95% sure or more)",
        f"    left as suggestions    {sum(not sure(u) for u in glyphs)}  (written as �; top 3 guesses in the .json)",
        f"  Unicode order problems   {bad}",
        f"  Files                    {stem}.txt / .json / .xml",
        "  Accuracy: only pages 9-11 have an answer key. To score against it, run: python -X utf8 gt/eval_cer.py",
    ])


if __name__ == "__main__":
    main()
