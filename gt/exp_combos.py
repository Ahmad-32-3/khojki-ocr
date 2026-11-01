"""Which letter + vowel sign combinations look alike, and do the bare-letter problem groups predict them? (log 98)

usage: python -X utf8 gt/exp_combos.py

Every consonant with nothing, nukta, and each of the 8 vowel signs is drawn in Noto Sans and Noto Serif Khojki.
A combination is "confused" when its nearest drawing in the other font (thinned, blurred pixels: the description
that worked best in log 96) has a different base letter. Each confusion is then sorted:
  carried over   both base letters are in the same bare-letter problem group and the sign is the same
                 (JA+II read as MA+II): predicted from the bare letters alone.
  sign-made      anything else: the sign changes the shape enough to look like another letter or combination
                 (CHA+U vs DDDA vs HA+U). These are grouped by linking every confused pair.
Then the matcher's real confusions on the 1896 dev lines (each line held out) are sorted the same way.
"""
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "gt")]
from khojki.bank import load, normalise, unit_mask  # noqa: E402
from khojki.labels import NUKTA, SEPARATOR, canonical, name, parts  # noqa: E402
from khojki.render import FONT_FILES, VOWEL_SIGNS, render  # noqa: E402
from khojki import recognise as R  # noqa: E402
from eval_recognise import bank_rows, lines_and_truth  # noqa: E402
from exp_guards import GROUPS, thin  # noqa: E402

GROUP_OF = {c: g for g, cs in GROUPS.items() for c in cs}
CONSONANTS = [c for c in range(0x11208, 0x1122C) if c != 0x11212]


def describe(img):
    return cv2.GaussianBlur(thin(img).astype(np.float32) / 255, (0, 0), 1.5).ravel()


def drawings():
    labels = [canonical((c,) + nk + v) for c in CONSONANTS for nk in ((), (NUKTA,))
              for v in ((),) + tuple((s,) for s in VOWEL_SIGNS)]
    out = {}
    for f in FONT_FILES:
        bare = [render((c,), f) for c in CONSONANTS]
        ref = float(np.median([np.ptp(np.nonzero(m)[0]) + 1 for m in bare if m.any()]))
        rows = [(lab, render(lab, f)) for lab in labels]
        rows = [(lab, normalise(m, ref)) for lab, m in rows if m.any()]
        out[f] = ([lab for lab, _ in rows], np.stack([describe(im) for _, (im, _) in rows]),
                  np.stack([meta for _, (_, meta) in rows]))
    return out


def kind(a, b):
    """'same' (no confusion), 'carried over' or 'sign-made', for truth a and reading b (labels)."""
    (la, sa), (lb, sb) = parts(a), parts(b)
    ba, bb = la[0], lb[0]
    if ba == bb:
        return "same"
    if GROUP_OF.get(ba) and GROUP_OF.get(ba) == GROUP_OF.get(bb) and sa == sb:
        return "carried over"
    return "sign-made"


def clusters(pairs):
    """Join confused pairs into groups (connected components), biggest first."""
    link = defaultdict(set)
    for a, b in pairs:
        link[a].add(b), link[b].add(a)
    seen, out = set(), []
    for a in link:
        if a in seen:
            continue
        stack, comp = [a], set()
        while stack:
            x = stack.pop()
            if x not in comp:
                comp.add(x), stack.extend(link[x])
        seen |= comp
        out.append(sorted(comp, key=name))
    return sorted(out, key=len, reverse=True)


if __name__ == "__main__":
    d = drawings()
    (fa, fb) = FONT_FILES
    tally, pairs, signed = Counter(), Counter(), Counter()
    for src, dst in ((fa, fb), (fb, fa)):
        la, Xa, Ma = d[src]
        lb, Xb, Mb = d[dst]
        for lab, x, m in zip(la, Xa, Ma):
            dist = np.linalg.norm(Xb - x, axis=1) + R.META_WEIGHT * np.linalg.norm(Mb - m, axis=1)
            got = lb[int(np.argmin(dist))]
            k = kind(lab, got)
            tally[(bool(parts(lab)[1]), k)] += 1
            if k != "same":
                pairs[tuple(sorted((lab, got)))] += 1
                if k == "sign-made":
                    signed[tuple(sorted((lab, got)))] += 1
    n_bare = sum(v for (s, _), v in tally.items() if not s)
    n_sign = sum(v for (s, _), v in tally.items() if s)
    print("Font drawings, nearest drawing in the other font:")
    for s, n in ((False, n_bare), (True, n_sign)):
        c, o, m = (tally[(s, k)] for k in ("same", "carried over", "sign-made"))
        print(f"  {'with a vowel sign' if s else 'no vowel sign':18} {n:4}: right {c / n:.1%}, carried over {o / n:.1%}, sign-made {m / n:.1%}")
    print("\nCarried-over confusions per bare group (same sign, look-alike letters):")
    per = Counter(GROUP_OF[parts(a)[0][0]] for (a, b) in pairs if kind(a, b) == "carried over")
    for g, v in per.most_common():
        print(f"  {g:14} {v}")
    print("\nSign-made groups (confused combinations linked together), largest first:")
    for comp in clusters(signed)[:12]:
        print("  " + "  ~  ".join(name(x) for x in comp))
    same_sign = sum(v for (a, b), v in signed.items() if parts(a)[1] == parts(b)[1])
    print(f"\nSign-made confusions where both have the same vowel sign: {same_sign} of {sum(signed.values())} "
          f"({same_sign / sum(signed.values()):.1%}): the sign, not the letter, decides the match")

    print("\nYour example, CHA+U / DDDA / HA+U: where each ranks among all drawings in the other font, nearest first")
    la, Xa, Ma = d[fa]
    lb, Xb, Mb = d[fb]
    for a in ("CHA+U", "DDDA", "HA+U"):
        i = [name(l) for l in la].index(a)
        order = [name(lb[j]) for j in np.argsort(np.linalg.norm(Xb - Xa[i], axis=1) + R.META_WEIGHT * np.linalg.norm(Mb - Ma[i], axis=1))]
        print(f"  {a:6} -> " + ", ".join(f"{b} #{order.index(b) + 1}" for b in ("CHA+U", "DDDA", "HA+U") if b != a)
              + f"  (own label #{order.index(a) + 1}; nearest: {', '.join(order[:4])})")

    print("\nThe matcher's real confusions on the 1896 dev lines (each line held out):")
    bank, real = load(), Counter()
    for line in lines_and_truth():
        ix = R.Index(bank, "pixels", bank_rows(bank, {line["file"]}))
        for idx, t in line["truth"].items():
            if t is None or t[0] == (SEPARATOR,):
                continue
            img, meta = normalise(unit_mask(line["atoms"], list(idx)), line["atoms"]["tall"])
            ps = R.part_scores(*ix.votes(img, meta))
            got = ps["letter"][0][0] + ps["signs"][0][0]
            if t[0] and got and t[0][0] != got[0]:
                real[(bool(t[1]), kind(t[0] + t[1], got))] += 1
    for s in (False, True):
        tot = real[(s, "carried over")] + real[(s, "sign-made")]
        if tot:
            print(f"  {'with a vowel sign' if s else 'no vowel sign':18} {tot} wrong letters: carried over "
                  f"{real[(s, 'carried over')]}, sign-made {real[(s, 'sign-made')]}")
