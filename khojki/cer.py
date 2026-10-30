"""Character error rate over Unicode code points (NFC), with the edit operations that explain it.

CER = (substitutions + deletions + insertions) / length of the reference (Levenshtein 1966).
"""
import unicodedata


def align(ref, hyp):
    """Minimum edit alignment. Returns (distance, ops); ops are ('ok'|'sub'|'del'|'ins', ref_char, hyp_char)."""
    r = unicodedata.normalize("NFC", ref)
    h = unicodedata.normalize("NFC", hyp)
    d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
    for i in range(len(r) + 1):
        d[i][0] = i
    for j in range(len(h) + 1):
        d[0][j] = j
    for i in range(1, len(r) + 1):
        for j in range(1, len(h) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (r[i - 1] != h[j - 1]))
    ops, i, j = [], len(r), len(h)
    while i or j:  # walk back; prefer match/substitution, then deletion, then insertion (deterministic)
        if i and j and d[i][j] == d[i - 1][j - 1] + (r[i - 1] != h[j - 1]):
            ops.append(("ok" if r[i - 1] == h[j - 1] else "sub", r[i - 1], h[j - 1]))
            i, j = i - 1, j - 1
        elif i and d[i][j] == d[i - 1][j] + 1:
            ops.append(("del", r[i - 1], ""))
            i -= 1
        else:
            ops.append(("ins", "", h[j - 1]))
            j -= 1
    return d[len(r)][len(h)], ops[::-1]


def cer(ref, hyp):
    dist, _ = align(ref, hyp)
    return dist / max(1, len(unicodedata.normalize("NFC", ref)))


def demo():
    assert align("abc", "abc")[0] == 0
    assert align("abc", "axc")[0] == 1 and ("sub", "b", "x") in align("abc", "axc")[1]
    assert align("abc", "ac")[1] == [("ok", "a", "a"), ("del", "b", ""), ("ok", "c", "c")]
    assert align("", "ab")[0] == 2 and cer("ab", "") == 1.0
    assert cer("\U00011224\U0001122E", "\U00011224�") == 0.5  # MA+II read as MA + unknown: 1 of 2 wrong


if __name__ == "__main__":
    demo()
    print("ok")
