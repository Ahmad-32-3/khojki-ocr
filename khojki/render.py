"""Chart examples: every label the netlify chart shows, drawn offline with HarfBuzz shaping.

HarfBuzz is the shaper browsers use, so the joined forms (II tail, I arch, ligatures) match the chart.
Pillow here has no shaping (log 25), so glyphs are shaped by uharfbuzz and drawn by FreeType.
"""
import unicodedata
from functools import lru_cache
from pathlib import Path

import freetype
import numpy as np
import uharfbuzz as hb

from khojki.labels import ANUSVARA, NUKTA, VIRAMA, canonical

FONTS = Path(__file__).resolve().parents[1] / "data" / "fonts"
FONT_FILES = ("NotoSansKhojki-Regular.ttf", "NotoSerifKhojki-Regular.ttf")
VOWEL_SIGNS = tuple(range(0x1122C, 0x11234))                    # AA I II U E AI O AU
CONJUNCTS = ((0x11208, VIRAMA, 0x11229, NUKTA),                 # ksa  (Pandey 4.7)
             (0x11210, VIRAMA, 0x11213),                        # jna
             (0x11219, VIRAMA, 0x11226),                        # tra
             (0x1121B, VIRAMA, 0x11226))                        # dra


def chart_labels():
    """Consonant x (nothing / nukta) x (no vowel sign / 8 signs) x (no anusvara / anusvara),
    plus independent vowels, punctuation and the four conjuncts. Unassigned U+11212 is skipped."""
    named = lambda c: unicodedata.name(chr(c), "")
    consonants = [c for c in range(0x11208, 0x1122C) if named(c)] + [0x1123F]
    vowels = list(range(0x11200, 0x11208)) + [0x11240]
    out = set()
    for c in consonants:
        for nk in ((), (NUKTA,)):
            for v in ((),) + tuple((s,) for s in VOWEL_SIGNS):
                for an in ((), (ANUSVARA,)):
                    out.add(canonical((c,) + nk + v + an))
    out |= {(v,) for v in vowels} | {(v, ANUSVARA) for v in vowels}
    out |= {(v, NUKTA) for v in vowels}                         # nukta on vowel letters too (Pandey 4.10; A+NUKTA in GT)
    out |= {(p,) for p in range(0x11238, 0x1123E)}
    out |= set(CONJUNCTS)
    return sorted(out)


@lru_cache(maxsize=None)
def _font(file, size):
    blob = hb.Blob.from_file_path(str(FONTS / file))
    hbfont = hb.Font(hb.Face(blob))
    face = freetype.Face(str(FONTS / file))
    face.set_pixel_sizes(0, size)
    return hbfont, face


def render(cps, file=FONT_FILES[0], size=64):
    """Ink mask (uint8, 255 = ink) of one label, shaped like the chart. Empty array if the font can't draw it."""
    hbfont, face = _font(file, size)
    buf = hb.Buffer()
    buf.add_str("".join(map(chr, cps)))
    buf.guess_segment_properties()
    hb.shape(hbfont, buf)
    if any(g.codepoint == 0 for g in buf.glyph_infos):          # .notdef: the font lacks a glyph
        return np.zeros((0, 0), np.uint8)
    scale = size / hbfont.face.upem
    canvas = np.zeros((size * 3, size * 4), np.uint8)
    pen_x, base_y = size, size * 2
    for info, pos in zip(buf.glyph_infos, buf.glyph_positions):
        face.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        g = face.glyph
        bmp = np.array(g.bitmap.buffer, np.uint8).reshape(g.bitmap.rows, g.bitmap.width)
        x = int(round(pen_x + pos.x_offset * scale)) + g.bitmap_left
        y = int(round(base_y - pos.y_offset * scale)) - g.bitmap_top
        if bmp.size and 0 <= x and 0 <= y and x + bmp.shape[1] <= canvas.shape[1] and y + bmp.shape[0] <= canvas.shape[0]:
            canvas[y:y + bmp.shape[0], x:x + bmp.shape[1]] |= bmp
        pen_x += pos.x_advance * scale
    return np.where(canvas > 96, 255, 0).astype(np.uint8)
