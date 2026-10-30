# Stage C: glyph recognition

## Problem

Stages A and B turn a page into glyph boxes. Nothing yet says which Khojki characters those boxes are.
Stage C must name each glyph from about 98 labelled examples (6 lines of page 9), with no language model at runtime.
It must also say how sure it is.

The person using the output is a reviewer. If the program shows a guess as if it were an answer, the reviewer copies the mistake into the record. So the program commits to an answer only when it has earned it. Otherwise it offers options that look clearly different from an answer.

## How it works

1. **Candidate units.** Stage B gives boxes in reading order, and a glyph may come out in 2–3 pieces (log 65). Every run of 1–3 neighbouring glyph boxes is a candidate unit. Separator boxes are units of their own and are never joined.
2. **Describe the shape.** Each candidate is cropped to its ink, kept in proportion, padded to a square and resized to 48 × 48. Three ways of describing it are compared, and the best is chosen by held-out results:
   - **Pixels:** the ink image blurred by a distance transform, compared by Euclidean distance.
   - **HOG:** histograms of stroke directions.
   - **Shape counts:** holes, stroke ends, junctions, aspect ratio, ink share by zone (upper / middle / lower), size relative to the line.
3. **Example bank.**
   - **Real examples** are cut from the ground-truth lines, using each unit's pixel box from `gt/gt_v1.json`.
   - **Chart examples** are rendered with HarfBuzz shaping in Noto Sans Khojki and Noto Serif Khojki. They cover every consonant × sign cell of the chart, the independent vowels, the punctuation, and the four conjuncts (tra, dra, kṣa, jña).
   - Each example is labelled `real` or `chart`.
4. **Match.** The k nearest examples vote, weighted by distance, which gives a score per label.
5. **Choose the split.** Dynamic programming picks the partition of the line's boxes into units with the best total log-score. This decides "one glyph in 2 pieces" versus "2 glyphs".
6. **Calibrate.** Raw scores become probabilities using isotonic regression, fitted only on predictions for lines the model didn't learn from.
7. **Decide, part by part.** A label is a letter plus signs. The probability of a **part** is the sum over all candidates that share that part: for example, P(letter = MA) adds up MA, MA+II and MA+E.
   - A part is **recognised** if its probability ≥ τ **and** it beats the next option for that part by ≥ 0.15.
   - τ is the lowest threshold that gives ≥ 95% precision on held-out lines.
   - Otherwise the part is a **suggestion**.
   - Parts that only chart examples support are always suggestions, unless the hidden-letter test (criterion 7) shows they reach the 95% bar.

## Output, per unit

```json
{"boxes": [3, 4],
 "letter": {"status": "recognised", "cps": ["U+11224"], "conf": 0.97},
 "signs":  {"status": "suggestion", "options": [{"cps": ["U+1122E"], "conf": 0.48}, {"cps": ["U+11230"], "conf": 0.31}]},
 "text": "𑈤�"}
```

- Text contains a recognised part's code points.
- Text contains **U+FFFD**, one per unknown part, for a suggestion. It never contains a Khojki character for a suggestion.

## In scope

- `khojki/recognise.py`: the example bank, the three descriptions, nearest-neighbour matching, choosing the split, calibration, and the recognition/suggestion decision.
- `khojki/render.py`: chart examples rendered offline with uharfbuzz + freetype-py and the two Noto fonts.
- `gt/eval_recognise.py`: leave one line out, with τ and calibration fitted inside each fold. It prints precision, coverage, the comparison of the three descriptions, and a risk–coverage table.
- A progress picture for this chunk.

## Out of scope

- **Any LLM or network call at runtime.** A vision-model baseline is chunk 6 and runs separately.
- **Training a neural network** (Omniglot prototypes, Kraken, TrOCR). These are later upgrades, named in the retro.
- **CER and the per-stage error tally.** Chunk 5.
- **Unicode validation and PAGE-XML output.** Chunk 4.
- **Recognition accuracy on p10–p11.** They have no glyph ground truth; only lines were marked there.
- **Joining across a separator, or across more than 3 boxes.** No ground-truth case needs it (log 65).
- **Language rules** (likely spellings). Glyphs are read by shape only, as in the transcription rules.

## Acceptance criteria

1. Running `python -m khojki.recognise <line image>` with all network access blocked gives the JSON above. A pytest sets `socket.socket` to raise and runs it on a synthetic line.
2. In every output unit, every part is `recognised` (with `cps`, `conf` ≥ τ and margin ≥ 0.15) or `suggestion` (with at least one option). Nothing else is allowed. A test checks the schema on all 6 GT lines.
3. The number of U+FFFD in the text equals the number of suggestion parts. No Khojki code point in the text comes from a suggestion. Tested.
4. Two runs on the same input give byte-identical JSON. Tested.
5. In `gt/eval_recognise.py`, each fold's τ and calibration come only from the other 5 lines. A unit test feeds a fold and asserts the held-out line's units were never used to fit.
6. The evaluation prints the following for the held-out lines, with counts: recognition precision with a 95% bootstrap interval, coverage (share of parts recognised), and the three-description comparison. **If precision is under 95%, the run says so in plain words.** It never silently lowers the bar.
7. Hidden-letter test: one letter's real examples are removed and the line is run. The letter is then supported only by chart examples, and it must come out as a suggestion. Tested.
8. Every number written to PROCESS_LOG or the retro is recomputed by a second route first (verifying-output skill).

## What to expect

Most labels have only 1–2 real examples. In leave-one-line-out, a glyph whose label appears only on the held-out line has no real example, so it can only be a suggestion. **Coverage will be low**, and that's the honest result: it measures how much labelling the script still needs. Precision is the number this stage is held to.

## Open questions

- **Precision target 95%.** Assumed, from the earlier discussion; you didn't confirm it.
- **Part-by-part status** (letter and signs decided separately). Assumed yes; not confirmed.
- **Chart examples:** I assumed they may only ever suggest unless criterion 7 shows otherwise. You might prefer them never to recognise at all.
