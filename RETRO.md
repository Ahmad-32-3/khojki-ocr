# Retro: Khojki OCR on the 1896 Narsi Mehta print (pages 9–11)

**Result.** The pipeline turns page images into Unicode Khojki with no network and no LLM at runtime. On 2 held-out test lines (49 characters) its top-1 CER is **40.8%**. With only 2 lines the uncertainty is wide, roughly 28–55%. On the 9 dev lines, scored leaving one line out, it is **38.8%** (209 characters). It commits a glyph only at 95% measured precision. No glyph passes that bar yet, so every letter is written as U+FFFD, with its suggestions in the JSON and PAGE-XML. Word separators are committed (88 of 90). Strict CER counts every U+FFFD as an error and is 120.6%. It goes over 100% because each unknown glyph writes two U+FFFD, one for the letter and one for its signs.

## 1. Errors by stage
Each stage writes its own output, so I swapped in ground truth one stage at a time (dev lines, top-1, 81 errors in 209 characters):

| Stage | Errors added | Stage score |
|---|---|---|
| Line finding | −2 | 35 of 35 lines found |
| Glyph boxes | 19 | 45 of 45 separators, 92 glyph boxes right |
| Recognition | 64 | right letter in the top 3 for 64.8% of glyphs |

Line finding comes out at −2 because the pipeline's own crops did slightly better than my hand crops on two glyphs. Recognition is the bottleneck. Its most common errors are small marks and look-alikes: an extra II (4), E read as nukta (3), an extra anusvara (3), MA read as BA (2), an extra nukta (2), AA read as II (2).

## 2. Failed experiments
- **Line finding took 8 tries.** Taking the biggest ink blob as the frame found the scan border (0 of 35 lines). Using the frame's vertical rules failed where they merge into the book's spine (12 of 35). The horizontal rules scored 35 of 35, but cut text off p9's left edge. The score only checked rows, and an overlay picture caught it. Every setting was tuned on these 3 pages, so 35 of 35 is a fit, not proof it generalises.
- **Otsu vs Sauvola.** They tied on lines (35 of 35 each). On glyph boxes Sauvola was worse (56 vs 59 of 80 glyphs right), so I kept Otsu.
- **Shape descriptions** (nearest neighbour, held-out lines, glyph letter top-1): shape counts 27%, HOG 51%, raw pixels 52%. HOG led at 6 lines; pixels lead at 9.
- **One confidence threshold for everything** showed 96% precision, but separators carried it. Glyphs alone were at 86%. I split the thresholds by kind.
- **No VLM baseline.** It was planned, but the time went to labelling instead.

## 3. Encoding decisions
- The word separator is U+1123A KHOJKI WORD SEPARATOR, not a colon.
- Marks follow logical order: the letter, then nukta, vowel sign, anusvara. NFC doesn't enforce this for Khojki, because the vowel signs have combining class 0. `labels.canonical()` sets the order and `validate.py` checks it.
- Digits are Gujarati (U+0AE6–0AEF), per the Unicode core spec.
- An unknown part is written as U+FFFD, never as a guessed letter. In ground truth, a glyph nobody could read is `?` and is left out of CER.
- Code-point tables are generated from Python's `unicodedata`. The design doc had put anusvara at U+1122C, which is actually vowel sign AA.

## 4. Bottleneck and lines needed
The bottleneck is labelled examples for recognition. Going from 6 to 9 dev lines (98 to 150 real glyphs) moved top-3 from 55.8% to 64.8% and CER from 48.6% to 40.2%. That's two points, each on a different dev set, so it's not a curve to extrapolate from. Kraken suggests about 800 lines for a printed script. VOLTAGE reached 4% CER on Takri, a related script, from about 14k labelled glyphs, which is about 740 lines at 19 glyphs per line. That's the range I'd plan for. The second bottleneck is the labeller. A non-reader can't reliably tell MA, BA, JA and TA apart, so a Khojki reader has to review.

## 5. Cost and time
- **Pipeline:** about 12 s per page on a laptop CPU (11.2, 13.1 and 12.2 s), with no GPU and no API. That's about 9 minutes and $0 for 45 pages.
- **Transcription:** 153 minutes of review for 11 lines (210 glyphs). That's about 44 s per glyph and 14 min per line, with suggestions shown. Lines ranged from 2 to 60 minutes. Working blind, without suggestions, took 39 s per code point. At 14 min per line, 800 lines would take a non-reader about 190 hours. The timer counts the time a glyph was open, idle time included.

## 6. Where the AI was wrong
Claude, the AI that helped build this and suggested readings, read MA+II as two letters, MA + DHA. It took the vowel sign's long tail for a second letter and overrode the segmenter, which had it right as one box. I caught it after 452 s on that glyph, by comparing it with the chart. The same family kept coming back: the pipeline's suggestions defaulted to MA, and I accepted them. A recheck of every MA, DHA, JA and BA reading changed 15 answers, mostly MA that was really BA, TA, JA or NA. The lesson: assisted labelling pulls the labeller toward the AI's mistakes. Look-alike families need a targeted recheck against reference drawings.

*Caveat:* the test-line truth was made with suggestions shown. It is held out from training, but not independent of the AI's reading.
