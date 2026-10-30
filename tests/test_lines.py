"""Stage A on a synthetic page (the real scans aren't in the repo)."""
import cv2
import numpy as np

from khojki.lines import find_lines


def synthetic_page():
    """3 text lines inside a double frame, with a dark scan border, a page number, an ornament and a detached dot."""
    page = np.full((700, 500), 230, np.uint8)
    page[:, :12] = 40                                    # dark scan border touching the image edge
    for inset in (40, 50):                               # double-rule frame
        cv2.rectangle(page, (inset, inset), (500 - inset, 700 - inset), 30, 2)
    rng = np.random.default_rng(0)
    for y in (150, 300, 450):                            # "letters": blobs 30 px tall
        for x in range(80, 420, 30):
            cv2.ellipse(page, (x, y), (10, 15), 0, 0, 360, 20, int(rng.integers(3, 6)))
    cv2.line(page, (180, 225), (320, 225), 20, 6)        # thin ornament between lines 1 and 2
    cv2.circle(page, (80, 422), 3, 20, -1)               # dot 13 px above line 3's first letter
    cv2.ellipse(page, (250, 20), (10, 14), 0, 0, 360, 20, 4)  # page number above the frame
    return page


def test_finds_three_lines_and_skips_ornament():
    found = find_lines(synthetic_page())
    assert len(found) == 3
    for (x0, y0, x1, y1), y in zip(found, (150, 300, 450)):
        assert y0 < y < y1                               # each line holds its own centre
        assert not (y0 <= 225 <= y1)                     # the ornament isn't inside any line


def test_detached_dot_stays_in_its_line():
    *_, (x0, y0, x1, y1) = find_lines(synthetic_page())
    assert y0 <= 419                                     # top of the dot


def test_border_and_frame_are_outside_lines():
    for x0, y0, x1, y1 in find_lines(synthetic_page()):
        assert x0 > 50 and x1 < 450                      # inside the inner frame rule
