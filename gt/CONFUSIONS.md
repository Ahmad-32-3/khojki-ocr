# Confusion checklist

Check every reading against this list **before** scoring it. Each item names the shape, what it usually is, the rule, and where the rule comes from.

Sources:
- **P** = Pandey, *Final Proposal to Encode the Khojki Script* (L2/11-021), section number.
- **Log** = PROCESS_LOG entry where we were corrected.

Noto's glyphs follow Devraj's 1903 metal type (P §3.3). This book is from 1896, so Noto is an approximation, not the reference type.

## Vowel signs (the most corrections so far)

| # | Shape in the scan | Usually | Rule | Source |
|---|---|---|---|---|
| C1 | A **long tail sweeping down to the right** from the letter's last stroke | **Vowel sign II** (U+1122E), in its variant form | Read it as II before calling the shape a new letter. The tail form is used after letters with a right descender (CA, NA) or a last stroke ending at the baseline (KA, PHA, HA). | P §4.6; Log 37, 49 (line 1 g11, line 9 g7 and g18) |
| C2 | A **tall stroke rising** to the upper right | **Vowel sign I** (U+1122D), regular form | Used after letters with a right descender (CA, VA) or a baseline-final stroke (KA, DA, HA). | P §4.6 |
| C3 | A **short arch over the top**, rising from the letter and curling down on the right | **Vowel sign I**, contextual form | Same code point as C2. Used after letters with rounded right edges: CHA, NGA, TTA, DDDA, **RA**. RA + I always looks like this. Don't read the arch as E: E is a stroke going up and to the **left**. | P §4.6; Log 46 (all 6 RA+I open) |
| C4 | The letter's last stroke **continues into an extra curl** at the bottom or right | **Vowel sign U** (U+1122F) | Check +U before calling it a new letter. U goes on the end of the last stroke (KA, CHA, HA), on the end of the descender (CA, GHA, YA), or under round letters (TTHA). | P §4.6; Log 49 (line 9 g2, HA+U) |
| C5 | A **stroke above going to the upper left** | **Vowel sign E** (U+11230) | O = AA upright + the E stroke. AI and AU can be drawn as E/O plus a second stroke above. | P §4.4 |

## Dots

| # | Shape | Usually | Rule | Source |
|---|---|---|---|---|
| C6 | **One** dot above, to the right or centred | **ANUSVARA** (U+11234) | A centred-above variant appears in lithographs. Both are U+11234. | P §4.9 |
| C7 | **Three** dots in a small triangle above (sometimes inverted, below) | **NUKTA** (U+11236) | Count the dots before choosing. Three means nukta, not anusvara. SA + nukta (śa) is common, and so are nukta letters for Arabic sounds. NFC order is letter, nukta, then vowel sign. | P §4.10; Log 45 (2 × SA+nukta), 47 |
| C8 | A **small ω or arc** above | **SHADDA** (U+11237), a doubled consonant | Rare. Placed right of an E/AI sign, or stacked over nukta. | P §4.8 |
| C9 | **Two dots stacked** vertically between words | **WORD SEPARATOR** (U+1123A), never a colon | The segmenter often merges it into the next letter's box. Read it as its own span. | P §4.11 |

## Punctuation and marks

| # | Shape | Usually | Rule | Source |
|---|---|---|---|---|
| C10 | **Two short strokes** (ıı) | **DOUBLE DANDA** (U+11239) | Noto draws exactly this shape. It marks the end of a verse section, often as `: ıı :`. One stroke is DANDA (U+11238). Don't read it as the AA sign of the letter before. | P §4.11; Log 51 |
| C11 | **Small circle(s)** after a word | **ABBREVIATION SIGN** (U+1123D), marking verse repetition | Don't read them as Gujarati digit zero (U+0AE6). Digits come in groups, usually as verse numbers with an overline, which isn't encoded. | P §4.12–4.14; Log 51 (page line 6) |
| C12 | **Long horizontal rule(s)** running to the margin | **SECTION MARK** (U+1123B single, U+1123C double) | Not an ornament. In scope for transcription. | P §4.11; Log 51 (page line 7) |

## Letters and letter forms

| # | Shape | Usually | Rule | Source |
|---|---|---|---|---|
| C13 | An **unfamiliar compact glyph** that isn't in the matrix | Could be one of the four **conjunct ligatures** | tra = TA+VIRAMA+RA, dra = DA+VIRAMA+RA, kṣa = KA+VIRAMA+SA+NUKTA, jña = JA+VIRAMA+NYA. A reduced RA can also hang under another letter (gr is the GGA glyph). Check these before scoring "new letter". The chart builder has no conjuncts. | P §4.7 |
| C14 | **DHA vs JJA**: both are a 3-curl with a left hook | Toss-up | Noto draws them almost the same. Always list both. | Noto rendering; Log 45 (line 2 g3, JJA) |
| C15 | **Loop plus one or two arches** (m-shapes) | MA, BA, BHA, NNA, DDA | Glyph-to-letter assignment varied between printers (Asani's table, P figs 16–19: the BA shape was also used for BHA). Transcribe the shape by its Unicode assignment (diplomatic). Never "correct" the spelling. List at least 3 of these as candidates. | P §4.5, figs 16–19; Log 49 |
| C16 | A thin **upright right after a letter** | **Vowel sign AA** of that letter | The segmenter often splits AA off into its own box (LA + AA, SA + AA). Read it with the letter before. Don't read it as DANDA unless it stands alone between separators. | Log 43 |
| C17 | **SA** (two joined P-shapes) | SA | The segmenter splits it into two boxes. One reading covers both. | Log 43 |
| C18 | Letter A plus a sign, used as a vowel letter (A + E-stroke, A + O) | The **independent vowel letter** (E U+11204, O U+11206, AI, AU) | Encode as the independent letter, never as A + sign. | P §4.3 |

## How to use it when scoring

1. Name the base letter first, then go through C1–C8 for anything attached to it.
2. If the shape seems new, check C13, C14 and C15 before scoring a new letter.
3. A rule that fits raises the reading's score. A rule that's broken caps it at 0.30.
4. Put the rule number in the reading's `why` text (e.g. "C3: arch form of I after RA"), so later analysis can count which rules helped.
