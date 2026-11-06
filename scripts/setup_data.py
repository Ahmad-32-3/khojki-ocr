"""Rebuild the files cut from the scans, which aren't in the repo: page images, labelled line crops, example bank.

usage: python -X utf8 scripts/setup_data.py      (needs khojki-scans/sample_khojki_script_vatiations.pdf)
Writes data/pages/p09-p11.png, gt/lines/*.png and data/bank.npz, then checks the bank matches data/model.json.
Every crop is cut at the page position recorded in gt/lines_index.json, so the files come out pixel-identical.
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np
import pymupdf
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from khojki import bank as B  # noqa: E402
from khojki.recognise import load_model  # noqa: E402

PDF = ROOT / "khojki-scans" / "sample_khojki_script_vatiations.pdf"


def page_rgb(doc, page):
    pix = pymupdf.Pixmap(doc, doc[page - 1].get_images()[0][0])  # the native scan, as gt/prep_gt.py saved it
    if pix.n - pix.alpha > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    return np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width, pix.n)[:, :, :3]


def main():
    if not PDF.is_file():
        sys.exit(f"Put the sample PDF at {PDF.relative_to(ROOT)} first.")
    doc = pymupdf.open(PDF)
    pages = {p: page_rgb(doc, p) for p in (9, 10, 11)}
    (ROOT / "data" / "pages").mkdir(parents=True, exist_ok=True)
    for p, rgb in pages.items():
        Image.fromarray(rgb).save(ROOT / "data" / "pages" / f"p{p:02d}.png")

    # the first 6 crops were saved in colour (gt/prep_gt.py), later ones in grey (gt/prep_lines.py)
    (ROOT / "gt" / "lines").mkdir(parents=True, exist_ok=True)
    index = json.loads((ROOT / "gt" / "lines_index.json").read_text(encoding="utf-8"))
    for file, c in index.items():
        crop = pages[c["page"]][c["y"]:c["y"] + c["h"], c["x"]:c["x"] + c["w"]]
        Image.fromarray(crop if c.get("rgb") else cv2.cvtColor(crop, cv2.COLOR_RGB2GRAY)).save(ROOT / "gt" / file)
    print(f"wrote 3 pages and {len(index)} line crops")

    real, chart = B.real_examples(), B.chart_examples()
    B.save(real + chart, gt_sha=B.file_sha(B.GT_FILE))
    model = load_model()
    if model is None or model.get("bank_fp") != B.fingerprint(B.load()):
        sys.exit("The rebuilt bank doesn't match data/model.json, so the pipeline will refuse to run.")
    print(f"bank: {len(real)} real + {len(chart)} font examples, matches data/model.json. Ready.")


if __name__ == "__main__":
    main()
