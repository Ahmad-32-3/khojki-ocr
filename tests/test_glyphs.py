"""Stage B on synthetic lines (the real crops aren't in the repo)."""
import cv2
import numpy as np

from khojki.glyphs import glyph_boxes


def line(*draw):
    img = np.full((70, 300), 230, np.uint8)
    for f in draw:
        f(img)
    return img


def letter(x):
    return lambda img: cv2.ellipse(img, (x, 40), (12, 16), 0, 0, 360, 20, 4)


def dot(x, y):
    return lambda img: cv2.circle(img, (x, y), 3, 20, -1)


def test_slanted_dot_pair_is_a_separator():
    # the lower dot 7 px right, so the dots share no column, as printed on p9 (log 63)
    boxes = glyph_boxes(line(letter(40), letter(80), dot(110, 34), dot(117, 46), letter(150)))
    assert [b[4] for b in boxes] == ["glyph", "glyph", "sep", "glyph"]


def test_dot_above_a_letter_is_a_mark_not_a_separator():
    boxes = glyph_boxes(line(letter(40), dot(40, 8), dot(46, 16), letter(80)))
    assert [b[4] for b in boxes] == ["glyph", "glyph"]
    assert boxes[0][2] <= 5  # the dots joined the first letter's box


def test_neighbouring_letters_are_never_merged():
    boxes = glyph_boxes(line(*(letter(x) for x in (30, 66, 102, 138))))
    assert len(boxes) == 4


def test_broken_frame_rule_near_the_side_is_dropped():
    # p11 l6: a 3 px rule 6 px in from the right edge, cut by the top edge, taller than 1.5 letters but under the full-height cut (log 83)
    rule = lambda img: cv2.rectangle(img, (290, 0), (292, 58), 20, -1)
    assert len(glyph_boxes(line(letter(40), letter(80), rule))) == 2


def test_tall_thin_letter_in_mid_line_is_kept():
    # the same shape in mid-line, not cut by an edge (a danda-like stroke), stays text
    stroke = lambda img: cv2.rectangle(img, (150, 14), (152, 60), 20, -1)
    assert len(glyph_boxes(line(letter(40), letter(80), stroke))) == 3
