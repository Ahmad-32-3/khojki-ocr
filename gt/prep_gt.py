"""Cut text lines from a sample-PDF page and build the blind-transcription picker.

usage: python -X utf8 gt/prep_gt.py <sample.pdf> [page=9] [n_lines=5]
writes: data/pages/pNN.png, gt/lines/pNN_lMM.png, gt/picker.html
"""
import json, sys, unicodedata
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
# p9 body text sits inside the printed frame, below the ornament. Fractions of page size.
# ponytail: hand-set box per page; replace with frame detection when we do more pages.
BODY_BOX = (0.06, 0.32, 0.87, 0.93)  # x0, y0, x1, y1


def page_image(pdf, page):
    doc = pymupdf.open(pdf)
    pix = pymupdf.Pixmap(doc, doc[page - 1].get_images()[0][0])  # native scan, no resampling
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    out = ROOT / "data" / "pages" / f"p{page:02d}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    pix.save(out)
    return Image.open(out).convert("RGB")


def line_bands(gray, min_h=12, merge_gap=6):
    """Horizontal projection: rows with ink -> bands; merge bands split by a small gap (marks above letters)."""
    ink = gray < gray.mean() - 2 * gray.std()
    rows = ink.sum(1) > max(2, 0.01 * ink.shape[1])
    bands, start = [], None
    for y, on in enumerate(np.append(rows, False)):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if bands and start - bands[-1][1] <= merge_gap:
                bands[-1] = (bands[-1][0], y)
            else:
                bands.append((start, y))
            start = None
    return [b for b in bands if b[1] - b[0] >= min_h]


def khojki_table():
    # generated from the Unicode database, never typed by hand (PROCESS_LOG #4)
    cps = [c for c in range(0x11200, 0x11250) if unicodedata.name(chr(c), None)]
    cps += list(range(0x0AE6, 0x0AF0))  # Gujarati digits, used by Khojki
    return [{"cp": c, "name": unicodedata.name(chr(c)), "cat": unicodedata.category(chr(c))} for c in cps]


def combos_html():
    """Consonant x sign matrix, shaped by the browser (Pillow here has no raqm, so it can't form the ligatures)."""
    t = khojki_table()
    cons = [g for g in t if g["cat"] == "Lo" and g["cp"] >= 0x11208 and "SHORT I" not in g["name"]]
    signs = [g for g in t if g["cat"] in ("Mn", "Mc") and g["cp"] != 0x11241]  # U+11241 has no glyph in Noto
    short = lambda g: g["name"].split(" ", 2)[-1].replace("SIGN ", "")
    head = "".join(f"<th>{short(s)}<br>{s['cp']:X}</th>" for s in signs)
    rows = "".join(
        f"<tr><th>{short(c)}<br>{c['cp']:X}</th><td>{chr(c['cp'])}</td>"
        + "".join(f"<td>{chr(c['cp'])}{chr(s['cp'])}</td>" for s in signs) + "</tr>"
        for c in cons)
    return f"""<!doctype html><meta charset="utf-8"><title>Khojki Combinations</title>
<link href="https://fonts.googleapis.com/css2?family=Noto+Sans+Khojki&display=swap" rel="stylesheet">
<style>body{{margin:8px;background:#fff;color:#000;font:11px system-ui}}table{{border-collapse:collapse}}
td,th{{border:1px solid #ccc;padding:0 4px;text-align:center}}td{{font:34px/1.3 "Noto Sans Khojki"}}th{{font-weight:600}}</style>
<table><tr><th></th><th>bare</th>{head}</tr>{rows}</table>"""


def main(pdf, page=9, n_lines=5):
    img = page_image(pdf, page)
    w, h = img.size
    x0, y0, x1, y1 = (int(f * s) for f, s in zip(BODY_BOX, (w, h, w, h)))
    body = img.crop((x0, y0, x1, y1))
    bands = line_bands(np.asarray(body.convert("L"), dtype=float))
    print(f"page {page}: {w}x{h}px, {len(bands)} lines found, heights {[b - a for a, b in bands]}")

    out_dir = ROOT / "gt" / "lines"
    out_dir.mkdir(parents=True, exist_ok=True)
    pad = 6
    lines = []
    for i, (a, b) in enumerate(bands[:n_lines], 1):
        name = f"p{page:02d}_l{i:02d}.png"
        body.crop((0, max(0, a - pad), body.width, min(body.height, b + pad))).save(out_dir / name)
        lines.append(f"lines/{name}")

    html = (ROOT / "gt" / "picker_template.html").read_text(encoding="utf-8")
    html = html.replace("__LINES__", json.dumps(lines)).replace("__GLYPHS__", json.dumps(khojki_table()))
    (ROOT / "gt" / "picker.html").write_text(html, encoding="utf-8")
    (ROOT / "gt" / "combos.html").write_text(combos_html(), encoding="utf-8")
    print("wrote", lines, "and gt/picker.html")


if __name__ == "__main__":
    main(sys.argv[1], *(int(a) for a in sys.argv[2:]))
