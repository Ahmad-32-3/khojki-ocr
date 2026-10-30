"""Khojki labels: canonical code-point order and the letter / signs split.

A label is the code points of one glyph unit, e.g. MA + vowel sign II = (0x11224, 0x1122E).
"""
import unicodedata

NUKTA, VIRAMA, ANUSVARA, SHADDA = 0x11236, 0x11235, 0x11234, 0x11237
SEPARATOR = 0x1123A
# marks after the last letter, in the order Unicode's Indic model writes them:
# nukta straight after its consonant, then the vowel sign, then anusvara / shadda.
# NFC leaves vowel sign + nukta alone (the vowel sign has combining class 0), so this has to be explicit (log 66).
_RANK = {NUKTA: 0, VIRAMA: 1, ANUSVARA: 3, SHADDA: 3}


def is_mark(cp):
    return unicodedata.category(chr(cp)) in ("Mn", "Mc")


def canonical(cps):
    """Reorder the trailing marks of a label into Unicode's order. Letters and conjunct order are kept."""
    cps = tuple(cps)
    i = len(cps)
    while i and is_mark(cps[i - 1]) and cps[i - 1] != VIRAMA:
        i -= 1
    return cps[:i] + tuple(sorted(cps[i:], key=lambda c: _RANK.get(c, 2)))


def parts(cps):
    """Split a label into (letter, signs). The letter keeps its nukta, which changes which letter it is;
    signs are the vowel sign, anusvara and shadda."""
    cps = canonical(cps)
    signs = tuple(c for c in cps if is_mark(c) and c not in (NUKTA, VIRAMA))
    letter = tuple(c for c in cps if c not in signs)
    return letter, signs


def from_hex(strs):
    """['U+11224', 'U+1122E'] -> (0x11224, 0x1122E)"""
    return tuple(int(s[2:], 16) for s in strs)


def name(cps):
    """Short readable name: MA+II, SA+NUKTA, DOUBLE DANDA, SEP."""
    short = lambda c: "SEP" if c == SEPARATOR else unicodedata.name(chr(c)).replace("KHOJKI ", "").replace(
        "LETTER ", "").replace("VOWEL SIGN ", "").replace("SIGN ", "")
    return "+".join(short(c) for c in cps)


def demo():
    JA, E, AA, SA, MA, II = 0x11210, 0x11230, 0x1122C, 0x11229, 0x11224, 0x1122E
    assert canonical((JA, E, NUKTA)) == (JA, NUKTA, E)                      # the GT's line 5 g19 order
    assert canonical((SA, AA, ANUSVARA, NUKTA)) == (SA, NUKTA, AA, ANUSVARA)
    tra = (0x11219, VIRAMA, 0x11226)
    assert canonical(tra) == tra                                            # conjuncts untouched
    assert parts((JA, E, NUKTA)) == ((JA, NUKTA), (E,))
    assert parts((MA, II, ANUSVARA)) == ((MA,), (II, ANUSVARA))
    assert parts((SEPARATOR,)) == ((SEPARATOR,), ())
    assert name((MA, II)) == "MA+II"
    assert name((0x11239,)) == "DOUBLE DANDA"


if __name__ == "__main__":
    demo()
    print("ok")
