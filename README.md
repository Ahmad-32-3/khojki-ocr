# Khojki OCR: Reading an 1896 Khojki Print

A take-home project for Karim Tharani (University of Saskatchewan). It turns scanned pages of an 1896 printed Khojki
book into Unicode text, measures how accurate that text is, and explains what limits it.

## Start Here

| What the brief asks for | Where |
|---|---|
| **Technical retro** (1 page) | [RETRO.md](RETRO.md) |
| **Walkthrough website** | [m48ahmad.com/ocr-walkthrough](https://m48ahmad.com/ocr-walkthrough) |
| **Pipeline output** for pages 9 to 11 (text, JSON, PAGE-XML) | [results/](results/) |
| **Test lines with their Unicode transcriptions** | [gt/gt.txt](gt/gt.txt) (one line per labelled line, `?` = unreadable) and [gt/gt.json](gt/gt.json) (with positions and dev/test split) |
| **Results** (CER and most common errors) | below, and `python -X utf8 gt/eval_cer.py` |
| **How to run it** | below |
| Every decision as it was made | [PROCESS_LOG.md](PROCESS_LOG.md) (95 entries) |

The live demo (the **Try the Demo** button) needs the small Python server in this repo, so it runs locally:
see step 5 below. The scans aren't in the repository or on the website, because the pages are for this exercise only.

## Results in Brief

- On 2 test lines kept aside until the end, the program's best guesses had **about 4 in 10 characters wrong**
  (a 40.8% character error rate). On the 9 development lines it was 38.8%. 11 lines were labelled in all.
- Most common errors: small marks (an extra vowel sign II, E read as a nukta, an extra anusvara) and look-alike
  letters (MA read as BA).
- Of 81 errors on the development lines, 64 come from recognizing characters, 19 from cutting lines into
  characters, and none from finding lines.
- A character counts as certain only when the program is at least 95% sure. No letter reaches that yet, so the text
  holds the best guesses, marked as guesses in the JSON for a person to confirm. Word separators do reach it.
- About 20 model changes, including neural networks, didn't beat simple pixel matching. More hand-checked examples
  did: four times as many raised first-guess accuracy from 46% to 69%.

## How to Run It

You need Python 3.11 or newer. Each page takes 15 to 18 seconds on a laptop.

**1. Install**

```bash
pip install -e ".[dev]"
```

**2. Add the scans.** Put the sample PDF (*sample_khojki_script_vatiations.pdf*) in the **khojki-scans** folder. The
scans aren't in this repository, because the pages are for this exercise only. Use pages **9, 10 or 11**, the 1896
print the program was built on. Pages 1 to 6 and 12 to 14 are handwritten and won't work.

**3. Run it on a page**

```bash
python -X utf8 -m khojki.pipeline khojki-scans/sample_khojki_script_vatiations.pdf --page 9 --out out/
```

It prints a summary of the page (lines, and how many characters are certain, best guesses, or without a good guess) and saves three files in the
**out** folder: a *.txt* with the text, a *.json* with every character and its top guesses, and a *.xml* in PAGE-XML,
a format archive tools can open.

**4. Check the accuracy.** This compares the output with the lines I labelled by hand.

```bash
python -X utf8 gt/eval_cer.py
```

It ends with the results in plain words. To check the code itself, run the 29 tests:

```bash
python -X utf8 -m pytest -q
```

**5. Run the website and demo locally**

```bash
python -X utf8 demo/server.py
```

Then open http://localhost:8000. The **Try the Demo** button opens the demo, where you can pick a sample page or
upload one and watch each stage: the lines, the character boxes, and what was recognized.

## How It Works

1. **Find the lines.** The page is turned into black ink on white, and each band of ink inside the printed frame
   becomes a line. *khojki/lines.py*
2. **Cut each line into characters.** Connected pieces of ink are boxed, and pieces stacked on top of each other are
   grouped into one character. *khojki/glyphs.py*
3. **Recognize each character.** It is compared with 150 characters I labelled from the book and 2,666 drawn from
   Khojki fonts, and the 7 most similar vote. *khojki/recognise.py*
4. **Decide and check.** A character counts as certain only at 95% confidence; otherwise its best guess is written, or &#xFFFD; if there's no good guess, and the text is checked against
   Khojki's Unicode rules. *khojki/validate.py*
5. **Measure.** The output is compared with the answer key, stage by stage. *gt/eval_cer.py*

## Folders

- **khojki** the pipeline
- **results** the pipeline output for pages 9 to 11
- **gt** the answer key, the labelling tools, the accuracy checks and the experiments
- **demo** the demo page and the small local server that runs the pipeline for it
- **site** the walkthrough website
- **khojki-scans** where the scans go (not committed)
- **tests** 29 tests
