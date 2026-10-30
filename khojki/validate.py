"""Stage D: check that output text is well-formed Khojki Unicode.

Rules (Unicode core spec ch. 15, Pandey L2/11-021, our encoding decisions in PLAN.md §5):
  1. only allowed characters: assigned Khojki (U+11200-1124F), Gujarati digits (U+0AE6-0AEF),
     U+FFFD for a part the program didn't recognise, newline; plus '?' in ground truth for an open glyph
  2. a mark (vowel sign, nukta, anusvara, ...) must follow a letter, a virama conjunct, or a placeholder
  3. at most one vowel sign per letter
  4. the marks after a letter are in Unicode order: nukta, vowel sign, anusvara (log 66, 68)
  5. the text is NFC
"""
import unicodedata

from khojki.labels import VIRAMA, canonical, is_mark

REPLACEMENT, OPEN = 0xFFFD, ord("?")
VOWEL_SIGNS = set(range(0x1122C, 0x11234)) | {0x11241}


def allowed(cp):
    if cp in (REPLACEMENT, ord("\n")):
        return True
    if 0x11200 <= cp <= 0x1124F:
        return bool(unicodedata.name(chr(cp), ""))
    return 0x0AE6 <= cp <= 0x0AEF


def problems(text, open_marker=False):
    """List of (position, message). Empty = valid. open_marker=True also allows '?' (ground truth only)."""
    out = []
    cps = [ord(c) for c in text]
    for i, c in enumerate(cps):
        if not allowed(c) and not (open_marker and c == OPEN):
            out.append((i, f"U+{c:04X} is not allowed in Khojki output"))
    # walk clusters: a base followed by its marks (and, after a virama, the next letter of a conjunct)
    i = 0
    while i < len(cps):
        c = cps[i]
        j = i + 1
        while j < len(cps) and (is_mark(cps[j]) or cps[j - 1] == VIRAMA):
            j += 1
        cluster = cps[i:j]
        if is_mark(c):
            out.append((i, f"mark U+{c:04X} has no letter before it"))
        elif len(cluster) > 1 and not is_letterlike(c):
            out.append((i, f"mark after U+{c:04X}, which is not a letter (separator, digit, punctuation)"))
        if sum(m in VOWEL_SIGNS for m in cluster) > 1:
            out.append((i, "more than one vowel sign on one letter"))
        if is_letterlike(c) and tuple(cluster) != canonical(cluster):
            out.append((i, "marks are not in Unicode order (nukta, vowel sign, anusvara)"))
        i = j
    if unicodedata.normalize("NFC", text) != text:
        out.append((0, "text is not NFC"))
    return out


def is_letterlike(c):
    return c in (REPLACEMENT, OPEN) or unicodedata.category(chr(c)).startswith("L")


def demo():
    JA, NUKTA, E, AA, SA, MA, II, ANUS, SEP = 0x11210, 0x11236, 0x11230, 0x1122C, 0x11229, 0x11224, 0x1122E, 0x11234, 0x1123A
    t = lambda *cps: "".join(map(chr, cps))
    assert problems(t(JA, NUKTA, E, SEP, MA, II, ANUS)) == []
    assert problems(t(JA, E, NUKTA))                                     # wrong order (log 66)
    assert problems(t(SEP, E))                                           # mark after a separator
    assert problems(t(MA, II, E))                                        # two vowel signs
    assert problems(t(MA) + "a")                                         # Latin letter
    assert problems(t(REPLACEMENT, II)) == []                            # unknown letter, recognised sign
    assert problems(t(0x11219, 0x11235, 0x11226, E)) == []               # conjunct tra + E
    assert problems(t(OPEN, AA), open_marker=True) == [] and problems(t(OPEN, AA))
    assert problems(t(0x0AE7, 0x0AE8)) == []                             # Gujarati digits


if __name__ == "__main__":
    demo()
    print("ok")
