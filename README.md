# Khojki OCR: 1896 Narsi Mehta print to Unicode

A take-home for Karim Tharani (USask): turn page images of printed Khojki into Unicode text, score it with CER,
and report what it would take to do the whole book.

The pipeline is plain Python (NumPy, OpenCV, scikit-learn). It runs offline on a laptop CPU, about 15 to 18 s a page including start-up,
with no API and no language model at runtime.

## Results

| | CER (best guess) | Lines | Characters |
|---|---|---|---|
| Test (held out, scored once) | **40.8%** | 2 | 49 |
| Dev (leave one line out) | **38.8%** | 9 | 209 |

Errors by stage on dev, found by swapping in ground truth one stage at a time:

| Stage | Errors added | Score |
|---|---|---|
| A. Line finding | -2 | 35 of 35 lines |
| B. Glyph boxes | 19 | 45 of 45 separators |
| C. Recognition | 64 | right letter in top 3 for 64.8% of glyphs |

The program commits a letter only when it is measured to be right 95% of the time. Everything else is written
as U+FFFD with its top 3 suggestions in the JSON and PAGE-XML, so a reviewer never copies a guess as an answer.

## How it works

1. **Lines (A).** Binarise, find the printed frame, split the text block into ink bands. `khojki/lines.py`
2. **Glyph boxes (B).** Connected ink blobs, grouped when stacked, word separators flagged. `khojki/glyphs.py`
3. **Recognition (C).** Each glyph is scaled to 48x48 and compared with a bank of 150 real labelled glyphs and
   2,666 font renders. The 7 nearest vote; letter and vowel signs are voted on separately. Dynamic programming
   picks how boxes join into glyphs. `khojki/recognise.py`
4. **Commit or suggest.** Calibrated on held-out lines (isotonic regression). A part is recognised if it reaches
   95% precision, beats the runner-up by 0.15 and a real example voted for it.
5. **Validate and write (D).** Unicode order checks; output as `.txt`, `.json` and PAGE-XML. `khojki/validate.py`
6. **Score (E).** CER against the ground truth, split by stage. `gt/eval_cer.py`

## Run it

```bash
pip install -e ".[dev]"
python -X utf8 -m khojki.pipeline khojki-scans/sample_khojki_script_vatiations.pdf --page 9 --out out/
python -X utf8 -m pytest -q
```

**Live demo:** `python -X utf8 demo/server.py`, then open http://localhost:8000. It serves the showcase page; its
*Try the Demo* button runs the pipeline on a sample page (Figures 1-5) or an upload and shows each stage. Local only,
because the scans are for this exercise only.

The scans and everything cut from them stay local (the brief: "use the pages for this exercise only"), so the
PDF, the line crops and `data/bank.npz` are not in this repository. With them in place,
`python -X utf8 -m khojki.bank` rebuilds the bank and `python -X utf8 gt/eval_recognise.py --fit` refits the model.

## Experiments

All on held-out dev glyphs (105), compared glyph by glyph with an exact McNemar test. Test lines never used.

| Idea | Change in glyphs right first time | File |
|---|---|---|
| HOG, shape counts vs raw pixels | pixels best (52% vs 51% vs 27%) | `gt/eval_recognise.py` |
| Thicker renders, worn copies, jittered real copies | -4 to +4, none significant | `gt/exp_vision.py` |
| Real examples weighted x3; pixels + HOG ensemble | +3, +6 (p = 0.11) | `gt/exp_vision.py` |
| Small CNN as the description | -8 | `gt/exp_adapt.py` |
| + SimCLR on 722 unlabelled page glyphs | -3 | `gt/exp_adapt.py` |
| + DANN (render vs real adversary) | -15 (p < 0.01) | `gt/exp_adapt.py` |
| + DANN with renders at the real letter mix | -3 | `gt/exp_adapt.py` |
| + SimCLR + DANN, real letter mix | -4 | `gt/exp_adapt.py` |
| **Fewer real labels (learning curve)** | 25% of labels: -23 points | `gt/exp_curve.py` |

The model changes didn't beat plain pixels; the number of real labels moved results every time. DANN failed
from label shift (renders hold every letter equally, the print doesn't); drawing renders at the real letter mix
cut its loss from 15 glyphs to 3.

**Trusted glyphs (tried, then dropped).** I tried always committing five glyphs I knew at a glance and that the
recognizer had got right every time it picked them (14 of 14). Chosen fairly, without each held-out line, the same
rule was right only 5 times out of 12. The commit hook's real-data check blocked it for breaking the 95% bar, so the
rule is gone. A perfect score on a few examples wasn't proof.

## Ground truth

11 lines (210 glyph units) from pages 9-11, labelled in a local review tool with suggestions shown: 9 dev lines,
2 test lines. Encoding decisions (separator U+1123A, logical mark order, Gujarati digits) are in `RETRO.md`.

## Files

- `khojki/` the pipeline
- `gt/` ground truth, review tools, evaluation and experiments
- `tests/` 29 tests
- `RETRO.md` one-page retro; `PROCESS_LOG.md` every decision as it was made; `SPEC.md` recognition spec
