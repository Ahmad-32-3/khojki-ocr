"""Stage B on synthetic lines (the real crops aren't in the repo)."""
import cv2
import numpy as np

from khojki.glyphs import ABBREVIATION, DOUBLE_SECTION, glyph_atoms, glyph_boxes


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


def ring(x, y):
    return lambda img: cv2.circle(img, (x, y), 5, 20, 2)


def test_double_rule_is_a_double_section_mark():
    # p11 l6: the two rules joined the digit before them as small marks, one 88 px box (log 98)
    rules = lambda img: (cv2.rectangle(img, (150, 33), (220, 35), 20, -1), cv2.rectangle(img, (150, 45), (220, 47), 20, -1))
    atoms = glyph_atoms(line(letter(40), letter(110), rules))
    assert [b[4] for b in atoms["boxes"]] == ["glyph", "glyph", "mark"]
    assert atoms["cps"][2] == (DOUBLE_SECTION,)


def test_ring_alone_is_an_abbreviation_sign_not_a_dot():
    atoms = glyph_atoms(line(letter(40), ring(70, 45), letter(110)))
    assert [b[4] for b in atoms["boxes"]] == ["glyph", "mark", "glyph"]
    assert atoms["cps"][1] == (ABBREVIATION,)


def test_ring_touching_a_letter_is_cut_off():
    atoms = glyph_atoms(line(letter(40), ring(59, 45), letter(110)))
    assert [b[4] for b in atoms["boxes"]] == ["glyph", "mark", "glyph"]
    bare = glyph_boxes(line(letter(40)))[0]
    assert atoms["boxes"][0][0] == bare[0] and abs(atoms["boxes"][0][1] - bare[1]) <= 1  # the letter keeps its width
    assert atoms["boxes"][1][1] >= 64                                     # the whole ring is in the mark
