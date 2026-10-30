"""Labelled sheet of a line's glyph boxes, 3x, for reading against gt/combos.html.
usage: python -X utf8 gt/box_sheet.py gt/lines/p09_l02.png out.png"""
import sys
import cv2, numpy as np
from segment import glyph_boxes

im = cv2.imread(sys.argv[1]); B = glyph_boxes(sys.argv[1]); tiles = []
for k, (x0, x1, y0, y1, kind) in enumerate(B):
    c = cv2.resize(im[:, max(0, x0 - 3):x1 + 3], None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    t = np.full((c.shape[0] + 30, max(c.shape[1], 70) + 10, 3), 255, np.uint8); t[30:, 5:5 + c.shape[1]] = c
    cv2.putText(t, f"{k}{'s' if kind == 'sep' else ''}", (5, 22), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 200), 2); tiles.append(t)
H = max(t.shape[0] for t in tiles); rows, cur, w = [], [], 0
for t in tiles:
    if w + t.shape[1] > 1100 and cur: rows.append(cur); cur, w = [], 0
    cur.append(np.pad(t, ((0, H - t.shape[0]), (0, 0), (0, 0)), constant_values=255)); w += t.shape[1]
rows.append(cur); rows = [np.hstack(r) for r in rows]; W = max(r.shape[1] for r in rows)
cv2.imwrite(sys.argv[2], np.vstack([np.pad(r, ((0, 0), (0, W - r.shape[1]), (0, 0)), constant_values=255) for r in rows]))
print(len(B), "boxes")
