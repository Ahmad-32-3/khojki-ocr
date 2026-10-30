"""Labels, chart rendering and the example bank's normalisation."""
import numpy as np

from khojki import labels
from khojki.bank import normalise
from khojki.render import render


def test_label_rules():
    labels.demo()


def test_shaping_draws_the_ii_tail():
    # MA + II is a ligature with a long tail (log 37); without shaping it would be MA plus a separate sign
    ma, ma_ii = render((0x11224,)), render((0x11224, 0x1122E))
    width = lambda m: np.ptp(np.nonzero(m)[1]) + 1
    assert width(ma_ii) > 1.3 * width(ma)


def test_missing_glyph_renders_empty():
    assert render((0x11241,), "NotoSansKhojki-Regular.ttf").size == 0  # Sans has no VOCALIC R (log 14)


def test_normalise_keeps_relative_size():
    letter = np.zeros((60, 60), np.uint8); letter[10:40, 20:40] = 255
    dot = np.zeros((60, 60), np.uint8); dot[10:15, 20:25] = 255
    (a, ma), (b, mb) = normalise(letter, 30), normalise(dot, 30)
    assert a.shape == b.shape == (48, 48)
    assert ma[0] == 1.0 and mb[0] < 0.2  # same 48x48 image size, but the meta still says which is small
