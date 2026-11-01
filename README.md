# Khojki OCR: Reading an 1896 Khojki Print

Khojki is a script used by the Khoja community of South Asia, mostly for religious texts, and almost no tools exist to
read it. I built a pipeline that turns scanned pages of an 1896 Khojki print into Unicode text, so they can be searched,
copied and preserved. It also measures how accurate that text is, and shows where the errors come from.

## Start Here

| What the brief asks for | Where |
|---|---|
| **Technical retro** (1 page) | [RETRO.md](RETRO.md) |
| **Walkthrough website** | [m48ahmad.com/ocr-walkthrough](https://m48ahmad.com/ocr-walkthrough) |
| **Live demo** | [m48ahmad.com/ocr-demo](https://m48ahmad.com/ocr-demo/) |
| **Pipeline output** for pages 9 to 11 (text, JSON, PAGE-XML) | [results/](results/) |
| **Test lines with their Unicode transcriptions** | [gt/gt.txt](gt/gt.txt) (one line per labelled line, `?` = unreadable) and [gt/gt.json](gt/gt.json) (with positions and dev/test split) |
| **Results** (CER and most common errors) | below, and `python -X utf8 gt/eval_cer.py` |
| **How to run it** | below |
| Every decision as it was made | [PROCESS_LOG.md](PROCESS_LOG.md) (99 entries) |

The demo reads pages through a small Python server in this repo, so to run a page yourself, start it locally (step 5
below). The scans aren't in the repository, because the pages are for this exercise only.

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

You need Python 3.11 or newer. Run every command from the project folder. Each page takes 15 to 18 seconds.

**1. Install**

```bash
pip install -e ".[dev]"
```

You should see it finish with *Successfully installed khojki-ocr*.

**2. Add the scans.** Put the sample PDF (*sample_khojki_script_vatiations.pdf*) in the folder called **khojki-scans**.
The scans aren't in this repository, because the pages are for this exercise only. Use pages **9, 10 or 11**, the
1896 print the program was built on. Pages 1 to 6 and 12 to 14 are handwritten and won't work.

**3. Run it on a page**

```bash
python -X utf8 -m khojki.pipeline khojki-scans/sample_khojki_script_vatiations.pdf --page 9 --out out/
```

When it finishes, it prints a summary like this:

```
sample_khojki_script_vatiations_p09  (11.3 s)
  Lines found              11
  Word separators found    52  (written as text)
  Characters found         158
    certain (green)        0  (95% sure or more)
    best guess (orange)    127  (written as the best guess; top 3 in the .json)
    no good guess (red)    31  (best guess under 30%, written as �)
  Unicode order problems   0
```

How to read it: the program found 11 lines on the page. It is sure of the word separators, so they're written as
text. No letter is 95% certain yet, so 127 characters are written as the program's best guess, and 31 that it had no
good guess for are written as �. *Unicode order problems 0* means every line passed the Unicode check.

It saves three files in the folder called **out**, named after the page:

- *…_p09.txt*: the page as Khojki text, one line per printed line. Open it in any editor with a Khojki font.
- *…_p09.json*: every line and character, with its position on the page and its top three guesses with confidence.
- *…_p09.xml*: the same in PAGE-XML, a format that archive and transcription tools can open.

Running the same page again replaces its three files. The output for all three pages is already in **results**.

**4. Check the accuracy**

```bash
python -X utf8 gt/eval_cer.py
```

This runs the pipeline on the 9 lines I labelled for development and compares the result with my answers. It takes
about a minute and ends like this:

```
In plain terms (whole pipeline, 9 development lines, each scored by a model that never saw it):
  Best guess for every character: 38.8% character error rate, about 4 in 10 characters wrong.
  The .txt as written: 40.7%. It holds the best guesses too; only glyphs with no good guess
  (best guess under 30%) are written as �, and those count as wrong.
  Where the errors come from: recognition 64, glyph boxes 19, line finding -2.
```

The character error rate is the share of characters that are wrong, missing or extra. Line finding shows -2 because
the program's own line crops did slightly better than my hand crops on two characters, so it adds no errors.

To check the code itself, run the tests. You should see *32 passed*.

```bash
python -X utf8 -m pytest -q
```

**5. Run the website and demo locally**

```bash
python -X utf8 demo/server.py
```

It prints the two addresses. Open http://localhost:8000 for the walkthrough, and click **Try the Demo** (or open
http://localhost:8000/demo/). Pick Figure 1, 2 or 3, click **Run the pipeline**, and after about 15 seconds the demo
shows the lines it found, the character boxes in one line, and what it recognized in each box, coloured green
(certain), orange (best guess) or red (no good guess). Click any box to see its top guesses.

## How It Works

1. **Find the lines.** The page is turned into black ink on white, and each band of ink inside the printed frame
   becomes a line. *khojki/lines.py*
2. **Cut each line into characters.** Connected pieces of ink are boxed, and pieces stacked on top of each other are
   grouped into one character. Section marks and abbreviation signs are found by their shape first, so they're never
   joined to a letter. *khojki/glyphs.py*
3. **Recognize each character.** It is compared with 150 characters I labelled from the book and 2,666 drawn from
   Khojki fonts, and the 7 most similar vote. *khojki/recognise.py*
4. **Decide and check.** A character counts as certain only at 95% confidence. Otherwise its best guess is written,
   or � if there's no good guess. The text is then checked against Khojki's Unicode rules. *khojki/validate.py*
5. **Measure.** The output is compared with the answer key, stage by stage. *gt/eval_cer.py*

## Folders

- **khojki** the pipeline
- **results** the pipeline output for pages 9 to 11
- **gt** the answer key, the labelling tools, the accuracy checks and the experiments
- **demo** the demo page and the small local server that runs the pipeline for it
- **site** the walkthrough website
- **khojki-scans** where the scans go (not committed)
- **tests** 32 tests
