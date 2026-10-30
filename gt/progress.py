"""Progress pictures: a small visual sample of each chunk's results.

usage: python -X utf8 gt/progress.py 1 2      -> gt/progress/chunkN.png (gitignored: contains scan pixels)
  1  line finding: each page shrunk, red box per line found, green tick per line marked by eye
  2  glyph boxes on two lines: green = glyph, orange = separator, red bracket = one glyph in 2-3 boxes
  3a example bank: one label as a real 1896 glyph and as both chart fonts
  3b recognition on a held-out line: solid green = recognised, dashed grey = suggestion with its top 3 letters
  4  the whole pipeline on page 10: each line, and under it the text file's content drawn glyph by glyph
"""
import json, sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.glyphs import glyph_boxes  # noqa: E402
from khojki.lines import find_lines  # noqa: E402
from eval_glyphs import score  # noqa: E402
from eval_lines import score as line_score  # noqa: E402

OUT = ROOT / "gt" / "progress"
FONT = cv2.FONT_HERSHEY_SIMPLEX


def caption(img, text, h=34):
    bar = np.full((h, img.shape[1], 3), 255, np.uint8)
    cv2.putText(bar, text, (8, h - 11), FONT, 0.6, (0, 0, 0), 1, cv2.LINE_AA)
    return np.vstack([bar, img])


def stack(imgs, axis):
    if axis == 1:
        h = max(i.shape[0] for i in imgs)
        imgs = [np.pad(i, ((0, h - i.shape[0]), (0, 8), (0, 0)), constant_values=255) for i in imgs]
        return np.hstack(imgs)
    w = max(i.shape[1] for i in imgs)
    return np.vstack([np.pad(i, ((0, 8), (0, w - i.shape[1]), (0, 0)), constant_values=255) for i in imgs])


def chunk1():
    gt = json.loads((ROOT / "gt" / "lines_gt.json").read_text(encoding="utf-8"))
    panels = []
    for page in ("p09", "p10", "p11"):
        gray = cv2.imread(str(ROOT / "data" / "pages" / f"{page}.png"), cv2.IMREAD_GRAYSCALE)
        found = find_lines(gray)
        s = line_score(found, gt[page]["text"], gt[page]["skip"])
        img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
        for x0, y0, x1, y1 in found:
            cv2.rectangle(img, (x0, y0), (x1, y1), (0, 0, 220), 3)
        for y in gt[page]["text"]:
            cv2.line(img, (0, y), (35, y), (0, 170, 0), 6)
        img = cv2.resize(img, None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
        panels.append(caption(img, f"{page}: {s['right']}/{len(gt[page]['text'])} lines right"))
    return caption(stack(panels, 1), "Chunk 1 - line finding. Red box = line found. Green tick = line marked by eye.", 40)


def chunk2(files=("lines/p09_l01.png", "lines/p09_l09.png")):
    gt = {l["file"]: l for l in json.loads((ROOT / "gt" / "gt.json").read_text(encoding="utf-8"))["lines"]}
    panels = []
    for f in files:
        gray = cv2.imread(str(ROOT / "gt" / f), cv2.IMREAD_GRAYSCALE)
        boxes = glyph_boxes(gray)
        k = 2
        img = cv2.resize(cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR), None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        img = np.pad(img, ((0, 24), (0, 0), (0, 0)), constant_values=255)
        for x0, x1, y0, y1, kind in boxes:
            cv2.rectangle(img, (x0 * k, y0 * k), (x1 * k, y1 * k), (0, 140, 255) if kind == "sep" else (0, 160, 0), 2)
        for u in gt[f]["units"]:  # glyphs that came out in several boxes: bracket underneath
            inside = [b for b in boxes if b[4] == "glyph" and u["cps"] != ["U+1123A"] and u["bbox"][0] <= (b[0] + b[1]) / 2 < u["bbox"][1]]
            if len(inside) > 1:
                x0, x1, yb = inside[0][0] * k, inside[-1][1] * k, img.shape[0] - 14
                cv2.line(img, (x0, yb), (x1, yb), (0, 0, 220), 3)
                cv2.line(img, (x0, yb - 8), (x0, yb), (0, 0, 220), 3)
                cv2.line(img, (x1, yb - 8), (x1, yb), (0, 0, 220), 3)
        s = score(gt[f]["units"], boxes)
        seps = sum(v for (kd, _), v in s.items() if kd == "sep")
        panels.append(caption(img, f"{f[6:13]}: separators {s[('sep', 'ok')]}/{seps}, glyphs in one box {s[('glyph', 'ok')]}, "
                                   f"in 2-3 boxes {s[('glyph', 'split')]}, merges {s[('glyph', 'merge')]}"))
    return caption(stack(panels, 0), "Chunk 2 - glyph boxes. Green = glyph. Orange = separator. Red bracket = one glyph in several boxes (joined in chunk 3).", 40)


def chunk3a():
    """Same label as a real 1896 glyph and as both chart fonts, after the same size normalisation."""
    from khojki.bank import load
    from khojki.labels import name
    b = load()
    wanted = [(0x11226,), (0x11224, 0x1122E), (0x1122A,), (0x1122A, 0x1122F), (0x11229, 0x11236),
              (0x11211, 0x1122C), (0x11239,), (0x1123A,)]
    cols = []
    for lab in wanted:
        tiles = []
        for src in ("real", "NotoSansKhojki-Regular.ttf", "NotoSerifKhojki-Regular.ttf"):
            i = next(i for i, (l, s, ln) in enumerate(zip(b["label"], b["source"], b["line"]))
                     if l == lab and (s == src or ln == src))
            tile = cv2.resize(255 - b["img"][i], None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
            tiles.append(np.pad(cv2.cvtColor(tile, cv2.COLOR_GRAY2BGR), ((4, 4), (4, 4), (0, 0)), constant_values=200))
        cols.append(caption(stack(tiles, 0), name(lab), 26))
    legend = np.full((cols[0].shape[0], 120, 3), 255, np.uint8)
    for k, t in enumerate(("", "real 1896", "Noto Sans", "Noto Serif")):
        cv2.putText(legend, t, (4, 26 + k * 104 - 50 if k else 20), FONT, 0.5, (0, 0, 0), 1, cv2.LINE_AA)
    return caption(stack([legend] + cols, 1), "Chunk 3a - example bank. Each column: one label as a real 1896 glyph, then drawn by the two chart fonts.", 40)


def chunk3b(file="lines/p09_l09.png"):
    """Line 9 recognised with its own examples removed from the bank (a fair test), as a reviewer would see it."""
    from khojki.bank import load
    from khojki.glyphs import glyph_atoms
    from khojki.labels import from_hex, parts, canonical
    from khojki.recognise import Index, load_model, recognise_atoms
    from khojki.render import render
    from eval_recognise import bank_rows
    bank, model = load(), load_model()
    gray = cv2.imread(str(ROOT / "gt" / file), cv2.IMREAD_GRAYSCALE)
    atoms = glyph_atoms(gray)
    out = recognise_atoms(atoms, Index(bank, model["description"], bank_rows(bank, {file})), model)
    gt = next(l for l in json.loads((ROOT / "gt" / "gt.json").read_text(encoding="utf-8"))["lines"] if l["file"] == file)
    truth = {}
    for u in gt["units"]:
        if u["status"] == "ok":
            for k, b in enumerate(atoms["boxes"]):
                if u["bbox"][0] <= (b[0] + b[1]) / 2 < u["bbox"][1] and (b[4] == "sep") == (u["cps"] == ["U+1123A"]):
                    truth[k] = parts(canonical(from_hex(u["cps"])))[0]
    cols, hits, n_sugg = [], 0, 0
    for u in out["units"]:
        x0 = min(atoms["boxes"][i][0] for i in u["boxes"])
        x1 = max(atoms["boxes"][i][1] for i in u["boxes"])
        crop = cv2.resize(cv2.cvtColor(gray[:, max(0, x0 - 2):x1 + 2], cv2.COLOR_GRAY2BGR), None, fx=1.6, fy=1.6)
        col = np.full((crop.shape[0] + 3 * 44 + 30, max(crop.shape[1], 78) + 12, 3), 255, np.uint8)
        col[22:22 + crop.shape[0], 6:6 + crop.shape[1]] = crop
        recognised = u["letter"]["status"] == "recognised"
        if recognised:
            cv2.rectangle(col, (2, 20), (col.shape[1] - 3, 24 + crop.shape[0]), (0, 160, 0), 3)
            cv2.putText(col, "recognised", (4, 14), FONT, 0.38, (0, 130, 0), 1, cv2.LINE_AA)
        else:
            n_sugg += 1
            for x in range(2, col.shape[1] - 3, 8):  # dashed: a suggestion, not an answer
                for y in (20, 24 + crop.shape[0]):
                    cv2.line(col, (x, y), (min(x + 4, col.shape[1] - 3), y), (110, 110, 110), 2)
            cv2.putText(col, "suggestion", (4, 14), FONT, 0.38, (90, 90, 90), 1, cv2.LINE_AA)
            want = truth.get(u["boxes"][0]) if all(truth.get(i) == truth.get(u["boxes"][0]) for i in u["boxes"]) else None
            for r, o in enumerate(u["letter"]["options"][:3]):
                cps = from_hex(o["cps"])
                m = render(cps)
                if not m.any():
                    continue
                ys, xs = np.nonzero(m)
                g = 255 - cv2.resize(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], None, fx=0.4, fy=0.4, interpolation=cv2.INTER_AREA)
                g = cv2.cvtColor(np.clip(g.astype(int) + 100, 0, 255).astype(np.uint8), cv2.COLOR_GRAY2BGR)  # grey ink
                yy = 30 + crop.shape[0] + r * 44
                h, w = min(g.shape[0], 38), min(g.shape[1], col.shape[1] - 40)
                col[yy:yy + h, 6:6 + w] = g[:h, :w]
                hit = want is not None and tuple(cps) == want
                hits += hit
                cv2.putText(col, f"{o['conf']:.0%}" + ("*" if hit else ""), (10 + w, yy + 22), FONT, 0.38,
                            (0, 120, 0) if hit else (90, 90, 90), 1, cv2.LINE_AA)
        cols.append(col)
    rows, cur, width = [], [], 0
    for c in cols:
        if width + c.shape[1] > 1300 and cur:
            rows.append(stack(cur, 1)); cur, width = [], 0
        cur.append(c); width += c.shape[1] + 8
    rows.append(stack(cur, 1))
    rec = sum(u["letter"]["status"] == "recognised" for u in out["units"])
    head = (f"{file[6:13]}, its own examples removed from the bank: {rec} separators recognised, {n_sugg} glyphs as suggestions. "
            f"* = the right letter is among the 3 shown ({hits} of {n_sugg}).")
    return caption(caption(stack(rows, 0), head),
                   "Chunk 3b - recognition. Suggestions (dashed) list the top 3 letters in grey with calibrated confidence; nothing is committed for them.", 40)


def chunk4(page=10, n_lines=4):
    """What out/<page>.txt holds, drawn under each line: black = committed character, dashed ? = not recognised."""
    from khojki.pipeline import pdf_page, run_page
    from khojki.render import render
    gray = pdf_page(ROOT / "data" / "sample_khojki_script_vatiations.pdf", page)
    result = run_page(gray, f"p{page:02d}")
    panels = []
    for l in result["lines"][:n_lines]:
        x0, y0, x1, y1 = l["bbox"]
        crop = cv2.cvtColor(gray[y0:y1, x0:x1], cv2.COLOR_GRAY2BGR)
        strip = np.full((60, crop.shape[1], 3), 255, np.uint8)
        for u in l["units"]:
            ux0, ux1 = u["bbox"][0] - x0, u["bbox"][2] - x0
            if u["letter"]["status"] == "recognised" and u["signs"]["status"] == "recognised":
                m = render(tuple(ord(c) for c in u["text"]))
                ys, xs = np.nonzero(m)
                g = 255 - cv2.resize(m[ys.min():ys.max() + 1, xs.min():xs.max() + 1], None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
                h, w = min(g.shape[0], 50), min(g.shape[1], strip.shape[1] - ux0)
                strip[5:5 + h, ux0:ux0 + w] = cv2.cvtColor(g[:h, :w], cv2.COLOR_GRAY2BGR)
            else:
                for x in range(ux0 + 1, ux1 - 1, 6):
                    cv2.line(strip, (x, 6), (min(x + 3, ux1 - 2), 6), (120, 120, 120), 1)
                    cv2.line(strip, (x, 52), (min(x + 3, ux1 - 2), 52), (120, 120, 120), 1)
                cv2.putText(strip, "?", ((ux0 + ux1) // 2 - 6, 38), FONT, 0.8, (120, 120, 120), 2, cv2.LINE_AA)
        panels.append(np.vstack([crop, strip]))
    parts = [u[p] for l in result["lines"] for u in l["units"] for p in ("letter", "signs")]
    rec = sum(p["status"] == "recognised" for p in parts)
    bad = sum(len(l["problems"]) for l in result["lines"])
    head = (f"page {page}: {len(result['lines'])} lines found, {rec} of {len(parts)} parts recognised (the separators), "
            f"{bad} validation problems. First {n_lines} lines shown.")
    panels.append(np.full((1, 1160, 3), 255, np.uint8))  # widen so the captions fit
    return caption(caption(stack(panels, 0), head),
                   "Chunk 4 - whole pipeline, PDF page in, text out. Under each line: black = committed character, dashed ? = not recognised (U+FFFD).", 40)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for n in sys.argv[1:] or ["1", "2"]:
        path = OUT / f"chunk{n}.png"
        cv2.imwrite(str(path), {"1": chunk1, "2": chunk2, "3a": chunk3a, "3b": chunk3b, "4": chunk4}[n]())
        print("wrote", path.relative_to(ROOT))
