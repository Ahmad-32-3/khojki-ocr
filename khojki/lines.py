"""Stage A: page image -> text line boxes.

Steps: binarise -> frame rows and outer sides (from its horizontal rules) -> text block columns
-> erase rules and non-text pieces -> horizontal projection -> bands -> split over-tall bands, drop thin ones.
Runs offline on a grayscale page; no fixed crop box, so it works wherever the page sits in the scan.
"""
import cv2
import numpy as np

SAUVOLA_WINDOW, SAUVOLA_K, SAUVOLA_R = 31, 0.2, 128


def binarise(gray, method="otsu"):
    """Return ink mask (uint8, 255 = ink). Methods: otsu (global), sauvola (local), meanstd (old prep_gt rule)."""
    if method == "otsu":
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        return ink
    if method == "sauvola":  # T = m * (1 + k * (s / R - 1)), Sauvola & Pietikainen 2000
        g = gray.astype(np.float64)
        win = (SAUVOLA_WINDOW, SAUVOLA_WINDOW)
        m = cv2.boxFilter(g, -1, win)
        s = np.sqrt(np.maximum(cv2.boxFilter(g * g, -1, win) - m * m, 0))
        return np.where(g < m * (1 + SAUVOLA_K * (s / SAUVOLA_R - 1)), 255, 0).astype(np.uint8)
    if method == "meanstd":
        return np.where(gray < gray.mean() - 2 * gray.std(), 255, 0).astype(np.uint8)
    raise ValueError(method)


def _horizontal_rules(ink):
    """[(y, x0, x1)] for thin (<= 12 rows) straight horizontal rules spanning >= half the page width."""
    h, w = ink.shape
    runs = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (w // 8, 1))) > 0
    counts = runs.sum(1)
    out, start = [], None
    for y, on in enumerate(np.append(counts > w // 20, False)):
        if on and start is None:
            start = y
        elif not on and start is not None:
            cols = np.flatnonzero(runs[start:y].any(0))
            if y - start <= 12 and len(cols) and cols[-1] - cols[0] >= 0.5 * w:
                out.append(((start + y) // 2, int(cols[0]), int(cols[-1])))
            start = None
    return out


def text_frame(ink):
    """(x0, y0, x1, y1) of the area inside the printed frame; the whole page if no frame is found.

    The frame can touch the dark scan border, and its side rules sit against the spine, so neither
    the frame as one component nor its side rules are reliable. Its horizontal rules are. The frame is a
    double rule: the two rules nearest the text at top and bottom give the rows, and their widest extent
    bounds the sides. (Rules fade near the spine, so the sides are only an outer limit; see text_columns.)
    """
    h, w = ink.shape
    rules = _horizontal_rules(ink)
    top = sorted(r for r in rules if r[0] < 0.3 * h)[-2:]
    bottom = sorted(r for r in rules if r[0] > 0.7 * h)[:2]
    if not top or not bottom:
        return 0, 0, w, h
    frame = top + bottom
    return min(r[1] for r in frame), top[-1][0] + 4, max(r[2] for r in frame), bottom[0][0] - 4


def drop_non_text(ink, max_frac=0.1):
    """Remove components taller than max_frac of the strip (side rules, spine, their fragments)
    or touching its left/right edge (scan border, the facing page). Letters are ~65 px; a strip is ~1000."""
    h, w = ink.shape
    _, labels, stats, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    drop = [i for i, (x, y, cw, ch, _) in enumerate(stats) if i and (ch > max_frac * h or x == 0 or x + cw >= w)]
    out = ink.copy()
    out[np.isin(labels, drop)] = 0
    return out


def text_columns(ink, max_gap=15):
    """(x0, x1) of the text block: the widest run of inked columns once non-text pieces are dropped.
    A gap > max_gap px separates the block from stray marks."""
    cols = np.flatnonzero(drop_non_text(ink).any(0))
    if not len(cols):
        return 0, ink.shape[1]
    runs, start = [], cols[0]
    for a, b in zip(cols, cols[1:]):
        if b - a > max_gap:
            runs.append((start, a + 1))
            start = b
    runs.append((start, cols[-1] + 1))
    x0, x1 = max(runs, key=lambda r: r[1] - r[0])
    return int(x0), int(x1)


def erase_rules(ink):
    """Remove long straight horizontal and vertical strokes (frame rules), keep letters."""
    h, w = ink.shape
    rules = cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (w // 3, 1)))
    rules |= cv2.morphologyEx(ink, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_RECT, (1, h // 3)))
    return cv2.subtract(ink, cv2.dilate(rules, np.ones((3, 3), np.uint8)))


def bands(ink, min_h=12, merge_gap=6, min_ink=0.01):
    """Horizontal projection: runs of rows with ink -> (y0, y1). Gaps <= merge_gap are joined (marks above letters)."""
    rows = (ink > 0).sum(1) > max(2, min_ink * ink.shape[1])
    out, start = [], None
    for y, on in enumerate(np.append(rows, False)):
        if on and start is None:
            start = y
        elif not on and start is not None:
            if out and start - out[-1][1] <= merge_gap:
                out[-1] = (out[-1][0], y)
            else:
                out.append((start, y))
            start = None
    return [b for b in out if b[1] - b[0] >= min_h]


def split_tall(ink, found, ratio=1.6):
    """Split a band taller than ratio x the median at its emptiest row (two lines joined by a descender)."""
    if not found:
        return found
    med = float(np.median([b - a for a, b in found]))
    counts = (ink > 0).sum(1)
    out = []
    for a, b in found:
        if b - a > ratio * med:
            lo, hi = a + int(0.3 * (b - a)), a + int(0.7 * (b - a))
            cut = lo + int(np.argmin(counts[lo:hi]))
            out += split_tall(ink, [(a, cut), (cut, b)], ratio) if (b - a) > 2.2 * med else [(a, cut), (cut, b)]
        else:
            out.append((a, b))
    return out


def find_lines(gray, method="otsu", min_frac=0.6):
    """Page -> [(x0, y0, x1, y1)] line boxes in page coordinates, top to bottom.
    Bands thinner than min_frac x the median (an ornament, a stray rule) are dropped."""
    ink = binarise(gray, method)
    fx0, y0, fx1, y1 = text_frame(ink)
    cx0, cx1 = text_columns(ink[y0:y1, fx0:fx1])
    x0, x1 = fx0 + cx0, fx0 + cx1
    inner = drop_non_text(erase_rules(ink[y0:y1, x0:x1]))
    found = split_tall(inner, bands(inner))
    if not found:
        return []
    med = float(np.median([b - a for a, b in found]))
    dropped = [(a, b) for a, b in found if b - a < min_frac * med]
    found = [(a, b) for a, b in found if b - a >= min_frac * med]
    # Grow each line into the gaps around it, so a dot sitting apart from its letter is never cut off:
    # at most halfway to the next line, at most 0.4 x a line height, and never into a dropped band (ornament).
    cap = int(0.4 * med)
    grown = []
    for i, (a, b) in enumerate(found):
        top = max(a - cap, (found[i - 1][1] + a) // 2 if i else 0, *[e for s, e in dropped if e <= a])
        bot = min(b + cap, (b + found[i + 1][0]) // 2 if i + 1 < len(found) else inner.shape[0],
                  *[s for s, e in dropped if s >= b])
        grown.append((top, bot))
    return [(x0, y0 + a, x1, y0 + b) for a, b in grown]
