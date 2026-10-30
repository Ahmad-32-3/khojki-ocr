# Khojki OCR take-home: working plan

Status: planning, round 1. Target: the 1896 Narsi Mehta printed pages (sample PDF p9–p11, tan/yellow paper).
Budget from the brief: 2–4 hours. Everything below is sized to that.

---

## 1. What the brief actually asks for

Deliverables, in the order a reviewer will check them:

1. A pipeline that runs end to end on page images: find lines → recognise → output UTF-8 Khojki. At least 5 real lines.
2. Our own hand transcription of those lines (no ground truth is provided), CER on them, most common errors.
3. A one-page retro with six fixed sections: error breakdown **by stage**, failed experiments **with numbers**, encoding decisions, bottleneck + how many labelled lines, cost/time per page, one place an AI tool was wrong.
4. Note how long our transcription took.

Two of those shape the design before we write any code:

- **"Error breakdown by stage"** means each stage must leave an inspectable artifact: line crops on disk, recogniser output in an intermediate label space, then a separate mapping to code points. If recognition writes code points directly, we can't separate "recognition error" from "mapping error".
- **"Experiments with numbers"** means we need at least two recognisers measured on the same lines. A VLM baseline is the cheap second one.

## 2. Critique of the backend design document

| # | Claim in the design doc | Problem | Fix |
|---|---|---|---|
| 1 | Anusvara is U+1122C | U+1122C is **VOWEL SIGN AA**. Anusvara is **U+11234**. Checked against Python's Unicode 15.1 database. | Generate the code-point table from `unicodedata`, never hand-type it. |
| 2 | NFC "collapses multi-byte base-and-accent splits into clean single code blocks" | Khojki has no precomposed characters. NFC does nothing to Khojki except one thing: it reorders VIRAMA+NUKTA into NUKTA+VIRAMA (canonical combining classes 9 and 7). A consonant + vowel sign stays two code points. "Multi-byte" also mixes up UTF-8 bytes (4 per Khojki char) with code points. | Keep NFC (harmless, standard), but validate with a grapheme-level check instead: every mark (Mn/Mc) must follow a letter. |
| 3 | Regex keeps only U+11200–1124F and U+A830–A83F | That deletes spaces, newlines, and **digits**. Unicode says Khojki uses **Gujarati digits U+0AE6–0AEF**; the page numbers on p9–p11 look Gujarati. Also U+11242–1124F are unassigned and should be rejected, not allowed. | Allowlist = assigned Khojki (U+11200–11241 minus U+11212) + Gujarati digits + space + newline + ZWJ/ZWNJ if needed. Log rejects; never drop silently. |
| 4 | CER computed against "LLM-assisted geometric ground truth" | Circular if the same LLM is also a recogniser: we'd be measuring agreement with ourselves. The brief says *we* transcribe and time it. | Blind double transcription, then adjudication (§4a). The LLM never sees the human's version first, and the human never sees the LLM's. |
| 5 | Track A: SSIM against Noto Sans Khojki templates | (a) Template matching needs characters cut out, but Stage 2 says the line is the atomic unit; the two conflict. (b) Noto is a modern design; the 1896 type may differ. **Unverified — test it in step 0.** | Harvest templates from the page itself (cluster-and-label, §4). Use Noto only for synthetic data. |
| 6 | Track C: "CTC sequence transformer analysing word waveforms"; TrOCR "handles cursive easily" | TrOCR is encoder–decoder, not CTC. "Waveforms" isn't a thing in HTR. Neither model handles anything without labelled lines. | Out of scope for this round. If we train, it's a small CRNN+CTC (Kraken) on synthetic + real lines. |
| 7 | Three recognition tracks, routing gate, active-learning backplane, weekly anomaly sweeps | Far beyond 2–4 hours. The brief says a small working pipeline beats an ambitious one. | Build one track. Keep the rest as "future work" lines in the retro. |
| 8 | Projection profiles "fail completely" at 2° skew; Surya needs "massive" memory | Both overstated. Deskew before projection is standard. Surya runs on CPU, just slowly. | Try projection + deskew first; switch only if it fails on our 5 lines. |
| 9 | Footer: "This is for informational purposes only. For medical advice or diagnosis, consult a professional." | A chatbot disclaimer pasted into the doc. | Delete before this doc is shown to anyone. |

What the doc gets right: line-level processing for recognition, adaptive thresholding to keep small marks, synthetic data from Noto, a confidence threshold that routes doubtful glyphs to review. We keep those.

## 3. What the research says (short)

- **No usable prior Khojki OCR work.** (Corrected in round 16.) A search found a GitHub "khojki-ocr" project, which used Qwen2.5-VL-3B few-shot on the same 1896 Narsi Mehta pages. The repository now returns 404, so it's probably another take-home submission. It isn't available, and it wouldn't be ours to use. No published Khojki OCR model or dataset exists.
- **Pandey's proposal (L2/11-021) is our script reference**, not just the chart. Key points:
  - §4.6: vowel signs I and II have contextual forms. The long right-hand tail is II after letters with right descenders. U is drawn as an extension of the letter's last stroke.
  - §4.9–4.10: there is an anusvara variant centred above the letter, and an inverted nukta variant. This bears on our dots-above versus dots-below question.
  - §4.11–4.12: DOUBLE DANDA marks verse sections. The ABBREVIATION SIGN U+1123D (a small circle) marks verse repetition. SECTION MARKS U+1123B/C are long rules out to the margin.
  - §3.3: Noto's glyphs follow Devraj's 1903 metal type. **Our book is from 1896, so it predates that type.** Expect differences from Noto.
- **A second font exists for synthetic data: Noto Serif Khojki.** It has a different design from Noto Sans, which cuts the one-font domain gap.
- **VOLTAGE (EACL 2024)** is the closest published match to our plan: segment, recommend glyph features, cluster and label, augment, then train. It reached 4% CER on Takri, a script in the same family as Khojki, from about 14k labelled symbols. It also found that fine-tuning models from other Indic scripts gave only 39–87% accuracy.
- **Few-shot Kraken (Kiessling 2026):** fine-tuning a *pretrained* model improves with only 20 lines. But the scripts were already in the pretraining data. Khojki isn't in any pretraining data, so that result is an upper bound for us.
- **VLMs fail on rare scripts in a specific way**: they output noise or invent characters from scripts they know (GlotOCR Bench, 2026). For Khojki the likely neighbours are Gujarati and Devanagari. So the VLM is a baseline to measure, and its output must be checked against the chart.
- **Labelled lines needed**: Kraken's docs suggest about 800 lines for a printed script with a small character set; manuscripts need more. Pretrained encoders have been reported to help with as few as ~30 lines. This gives us a defensible number for the "bottleneck" section.
- **Synthetic data recipe that works elsewhere**: render many fonts, match ink and scale to a real line, add degradations, pretrain, then fine-tune on a small real set (Indic HTR work, UniLipi 2026). For Khojki we have one font (Noto), so the domain gap is the main risk.
- **Binarisation choice mattered more than other image cleanup** in a 19th-century print study with Kraken. Worth trying two binarisers and reporting both.

## 4. Proposed pipeline for the 1896 print

```
page image (p9–p11)
  → crop to text frame, deskew            [OpenCV]
  → binarise (Sauvola vs Otsu, compare)   [scikit-image / OpenCV]
  → line split by horizontal projection   → lines/*.png          (stage 1 artifact)
  → connected components per line, merge marks into their base glyph
  → cluster glyph images (size-normalised, k-means or agglomerative)
  → human labels each cluster once        → clusters.json         (stage 2 artifact: cluster ids)
  → cluster id → code points, logical order → out/*.txt          (stage 3 artifact: Unicode)
  → validate (allowlist, mark-after-letter, NFC)
  → CER vs our transcription, per stage
```

Why cluster-and-label instead of per-glyph templates or training:
movable type repeats the same glyph shapes. Labelling ~50–100 clusters once is less work than transcribing every character, and it labels the real 1896 typeface rather than Noto's. It also makes the "time spent labelling" number meaningful.

Hard limit: the sample PDF stores p9 at 825×1200 px. Body lines are 56–67 px tall including marks, so the dots above letters are a few pixels. Any CER we report is for this resolution.

Known weak points we'll measure, not assume away:
- Touching glyphs (some words in the crop look joined) → merged components → wrong cluster.
- Small marks (dots above, the word separator's two dots) → may get split off or lost in binarisation.
- Vowel signs drawn on the left of the consonant, if Khojki has any → visual order ≠ logical order. **Check by rendering each vowel sign with Noto before deciding.**

Baseline for comparison: the same 5 lines sent to a VLM with the code chart, output scored with the same CER script.

Stretch (only if time is left): Kraken CRNN trained on Noto synthetic lines, scored on the same lines. Kraken is Linux/macOS first, so this needs WSL on this machine.

## 4a. Ground-truth protocol

Rejected flow (round 2): Claude reads a line screenshot and proposes code points, you confirm each one against the chart. Problems:
- **Anchoring.** Checking a suggestion is easier than producing one, so plausible wrong answers get accepted. A VLM confuses look-alike glyphs, and a non-reader checking against the chart gets confused by the same pairs, so the errors line up instead of cancelling.
- **It contaminates the baseline.** If Claude helped write the ground truth, Claude's CER as a recogniser is inflated and the "AI was wrong" section has nothing honest to report.
- **Screenshots lose detail.** Small marks (dots, the separator) blur. Use crops cut from the source image at full resolution.
- **The chart shows Noto, not the 1896 type.** Matching against a modern font can mislead on exactly the glyphs that differ.
- **No record of doubt.** Each character is either confirmed or not; nothing says "unsure".

Adopted flow:
1. **Write the rules first** (`gt/RULES.md`, one page): diplomatic transcription (what is printed, no spelling fixes); U+1123A for the separator; logical order; unreadable glyph → `?` plus a note; ornaments and page numbers excluded or included, decided once.
2. **You transcribe blind**, with a glyph picker (click a glyph, it inserts the code point) and a live Noto rendering of your text under the crop. Time it.
3. **Claude transcribes blind**, from the same full-res crop plus the chart, without seeing yours. This doubles as the VLM baseline.
4. **Diff by code point.** Every disagreement is shown as a zoomed crop with both readings rendered in Noto. You decide; record who was right and why in `gt/adjudication.csv`.
5. **Report agreement** (raw agreement and CER between the two blind readings). That number is our estimate of how reliable the ground truth is.
6. **Consistency check, later:** once glyph clusters exist (§4), any cluster whose members carry different labels in the ground truth is flagged for review.

**Revision (round 5): full blind transcription by a non-reader doesn't fit the budget.** Your blind pass took 388 s for the first 10 code points of line 1, about 13 min per line. So:
- **Blind control (kept):** your 10 code points stay as an independent check. 6 of 10 match Claude's blind read exactly (HA E : HA E :). The other 4 are word 3, where the two readings even split the word into glyphs differently.
- **Rest of the lines: assisted review, built to limit anchoring:**
  1. Review **glyphs, not lines**. The tool draws a box around every glyph, so you confirm how the word is split before labelling it. Word 3 shows the split itself can be wrong.
  2. Show the **top 3 candidates** (Noto renders next to the crop), plus "none of these" and `?`. Choosing among three is less anchoring than confirming one.
  3. **Label by cluster.** Glyphs that look alike are grouped, and labelling one group labels every occurrence. Fewer decisions, and consistent by construction. This is the same grouping step the pipeline needs.
  4. **Disclose it.** The retro says the ground truth is "model-proposed, human-verified by a non-reader". Claude's error rate is reported twice: against the blind segment, and against the reviewed lines (biased low, labelled as such).
- **Known ceiling:** a non-reader can't catch places where the 1896 type differs from Noto. Only a Khojki reader can. That goes in the retro's bottleneck section.

### 4b. Review tool spec (round 6)

**What Claude outputs per line: a lattice, not a string.** Each line is a sequence of *spans*. A span covers one or more glyph boxes from the segmenter, and lists every reading Claude thinks is plausible, with a confidence score. When the split itself is uncertain (word 3 of line 1), the alternative splits are separate readings of the same span.

```json
{"file": "lines/p09_l01.png",
 "boxes": [[12,40,8,52], ...],                       // x0,x1,y0,y1 per glyph component, from the segmenter
 "spans": [
   {"boxes": [0], "readings": [
      {"cps": ["U+1122A"], "conf": 0.6, "why": "hooked top, bar, descender like Noto HA"},
      {"cps": ["U+11208"], "conf": 0.2, "why": "KA has similar top hook"},
      {"cps": ["?"],       "conf": 0.2}]},
   {"boxes": [6,7], "readings": [                    // a split ambiguity: 1 glyph + sign, or 2 letters
      {"cps": ["U+1122D","U+11219"], "conf": 0.4},
      {"cps": ["U+11226","U+1121B"], "conf": 0.25},
      {"cps": ["?"], "conf": 0.35}]}]}
```

Rules for the scores:
- **Confidences in a span add up to 1, including `?`.** The `?` share is "none of my candidates", so it's never hidden.
- **Steps of 0.05.** Finer numbers would claim precision Claude doesn't have.
- **Toss-ups are explicit.** If the top two readings are within 0.15 of each other, the span is marked `tossup: true` and the tool shows both side by side, neither pre-selected.
- **Every reading has a "why"**, a shape-based reason ("closed bowl + stem"), so you can check the argument against the crop, not only the label.

**Claude's numbers are not probabilities until we check them.** Language models are known to be poorly calibrated about their own guesses. After review, we bin Claude's scores (0.0–0.3, 0.3–0.6, 0.6–0.8, 0.8–1.0) and count how often the top reading in each bin was accepted. That table goes in the retro. If "0.8" turns out right 40% of the time, we say so.

**A second, independent confidence from the pipeline.** The cluster stage measures how close each glyph is to its cluster centre, and how close the second-nearest cluster is. When Claude is confident and the pipeline isn't (or the reverse), the span is flagged for a closer look.

**What the review page does:**
1. Shows the line crop with numbered boxes. Step 1: confirm or fix the split (merge or split boxes) before any labelling.
2. For each span, in order of lowest confidence first: the zoomed crop, each reading rendered in Noto with its score and "why", plus "none of these" and a free pick from the full palette.
3. Toss-ups: two readings shown with equal weight, no default.
4. Spans above 0.8 that also agree with the pipeline's cluster can be accepted in bulk, but a random 1 in 5 of them is still shown for review (spot check).
5. Every decision saves which reading was chosen, its rank, and the score Claude gave it. That data drives the calibration table.
6. Labels propagate by cluster: deciding one glyph fills in the same cluster elsewhere, marked "propagated" so it can be reviewed.

**Candidates are consonant + sign combinations, not bare letters (round 7).** Vowel signs I and II, and some others, reshape the consonant into a ligature. TA+II looks like an M shape; RA+I adds a flag at the top right. So:
- The reference is `gt/combos.html`: every consonant × every sign, generated from `unicodedata` and shaped by the browser in Noto Sans Khojki. It's built by `prep_gt.py`, so it's reproducible and doesn't depend on a third-party site. It mirrors the matrix at khojki-demo.netlify.app, which you found and which uses the same font.
- Every reading lists its **code points** (`"cps": ["U+11226", "U+1122D"]`). The tool renders each reading as the shaped cluster next to the crop, so you compare ligature to ligature.
- A cluster reading (consonant + signs) counts as one candidate, so "RA" and "RA+I" compete directly in the same span.
- First filled example: `gt/claude_lattice_l01.json` (21 spans, scores summing to 1, toss-ups flagged). Boxes get filled in once the segmenter exists.

Order of building: segmenter (boxes) → Claude reads per box and writes the lattice → clustering → review page.

Optional third, independent source: if a Gujarati or romanised edition of the same Narsi Mehta text exists, convert it to Khojki and use it to check the adjudicated lines. Not yet checked whether one exists.

Tools:
- **For this take-home (5–20 lines):** `gt/picker.html`, built by `gt/prep_gt.py` (done, round 3). A small local HTML page (line crop, Khojki glyph palette, live Noto render, export to `.txt` + `.json`). Keyman's Khojki Inscript web keyboard is an alternative input, but it targets Sindhi; check it covers every code point we need before relying on it.
- **For scaling (hundreds of lines, the "bottleneck" answer):** eScriptorium, self-hosted with Docker (needs WSL on Windows for Kraken). It has custom virtual keyboards, Kraken segmentation and training, and PAGE XML export.
- **Not Transkribus:** it's cloud-hosted and credit-based, and the brief says to use these pages for this exercise only. Uploading Harvard's scans to a third-party platform goes against that.
- CER tool: one we write (≈10 lines, Levenshtein over code points after NFC), so normalisation is fixed and stated. Published CER tools normalise differently.

## 5. Encoding decisions (draft, to confirm against the chart)

- Word separator (the colon-like two dots between words on p9): **U+1123A KHOJKI WORD SEPARATOR**. Not U+003A colon. Khojki has no visarga, so it can't be that either.
- Digits: **Gujarati U+0AE6–0AEF**, per the Unicode core spec.
- Vowel signs: logical order (consonant first, then sign), whatever the visual position.
- Output: UTF-8, NFC, one line per text line, validated by the allowlist in §2 row 3.
- **Marks after a letter in Unicode order: nukta, then vowel sign, then anusvara/shadda.** NFC doesn't do this for Khojki, because a vowel sign has combining class 0. It's enforced by `khojki/labels.canonical()` and checked by `khojki/validate.py` (log 66, 68).
- **An unrecognised part is written as U+FFFD,** one per part, never a guessed Khojki character. Options go in the JSON and PAGE-XML, not the text (SPEC.md).
- **Ground truth writes an unreadable glyph as `?`.** It's left out of CER. Only the GT validator accepts it.
- **PAGE-XML:** each glyph's TextEquiv index 1 holds the committed text. Suggestions are further TextEquiv entries marked `comments="suggestion: …"`.

## 6. Order of work

0. **Step 0, 20 min — check assumptions before building**: crop 5 lines from p9 (skip the heading and ornament). Render a few Khojki words in Noto next to them. Answer: does the type match Noto? Are glyphs mostly separate? Which vowel signs sit left?
1. Ground truth per §4a: rules, picker page, your blind pass (timed), Claude's blind pass, adjudication.
2. Line segmentation; eyeball all line crops; count line-stage errors.
3. Components → clusters → label clusters. Time the labelling.
4. Map to Unicode, validate, score CER. Write the per-stage tally.
5. VLM baseline on the same lines; score it.
6. Retro.

### Build chunks (round 20). Each ends with a commit you make.

| Chunk | Builds | Done when | Skill |
|---|---|---|---|
| 0 ✓ | Freeze GT (`gt/gt.json`, `.txt`; v2 = marks in Unicode order) | Counts match by a second route | verifying-output |
| 1 ✓ | Stage A: lines (`khojki/lines.py`). Otsu vs Sauvola, p9–p11 | 35/35 lines right with both; see log 61 | verifying-output |
| 2 ✓ | Stage B: glyph boxes (`khojki/glyphs.py`) scored against GT | Separators 22→31 of 31, no merges, splits ≤3 boxes; see log 63–65 | verifying-output |
| 3 ✓ | Spec for recognition, then stage C: example bank from GT + chart renders (uharfbuzz), features, nearest neighbour, calibration, recognition vs suggestion | Spec's acceptance criteria pass; runs offline | writing-specs first; `/checking-divergence` once (you type it) |
| 4 ✓ | Stage D: encoding, validation, `.txt` + JSON + PAGE-XML output (`khojki/validate.py`, `khojki/pipeline.py`) | Validator rejects bad sequences in tests; 0 problems on p9–p11 output and on GT v2, flags GT v1 | — |
| 5 ✓ | Stage E: CER (`khojki/cer.py`, `gt/eval_cer.py`), leave one line out, GT-box comparison, per-stage tally, bootstrap | Top-1 CER 50.0% (recognition 65, segmentation 5, lines 1 errors); all numbers recomputed independently; see log 76–77 | verifying-output |
| 6 | Baselines (VLM optional) and numbers for the retro | Same scorer, same lines | verifying-output |
| 7 | Labelling loop: run the pipeline on new p10–p11 lines, review its output, freeze GT vN+1, rebuild the bank, re-score. A fixed blind test set (1 line each from p10 and p11) never enters the bank | A learning curve: lines labelled and minutes spent vs coverage, precision and CER, per round | verifying-output |

## 7. Open questions for you

1. The brief says "about 45 pages"; the PDF has 47, and p42–p47 (probably p36–p38 too) look like **Gujarati script**, not Khojki. Do you agree? If so, they're out of scope for recognition, but if they're Gujarati transcriptions of the same ginans, they're a text source for synthetic data.
2. Are you on WSL, or should we stay pure-Windows Python (rules out Kraken training this round)?
3. Which VLM for the baseline: Claude via API (needs a key, kept out of the repo) or manual paste into claude.ai?

## 7a. Recognition design (round 18)

### Two kinds of output, never mixed up

| | **Recognition** | **Suggestion** |
|---|---|---|
| Meaning | The system commits to these code points | The system doesn't know. These are candidates for a person to check |
| When | Passes the confidence test below | Everything else |
| In the output `.txt` | The code points | **U+FFFD** (�), one per unknown unit. Never a Khojki character |
| In the sidecar JSON | `{"status":"recognised","cps":[...],"conf":0.97}` | `{"status":"suggestion","options":[{"cps":[...],"conf":0.41}, ...]}` |
| On screen | Solid Noto glyph, solid border, "Recognised · 97%" | No glyph inserted in the reading. A dashed outline with a `?` in the reading row, and options listed under a **"Suggestions — not recognised"** heading in grey italics. They differ by shape and wording, not only colour, so colour-blind users can tell them apart. |
| Counted in CER | Yes | Yes, as an error: U+FFFD never matches the ground truth. Coverage and CER on recognised units are reported separately too. |

A unit can be **part recognised**, e.g. letter MA certain, vowel sign unsure. The confident part is a recognition, and only the unsure part becomes a suggestion (letter + U+FFFD). This follows the zone design below: each zone is decided on its own.

### The confidence test (selective prediction)

A unit is recognised only if **both** hold. Otherwise it is a suggestion.
1. **Calibrated confidence ≥ τ.** Raw similarity scores are mapped to probabilities, using held-out predictions only (Guo et al. 2017). With ~100 glyphs that means a few bins, not a fitted curve. τ is the smallest threshold whose recognitions reach the **target precision** (default 95%) on held-out lines. This is Chow's reject option (1970). We report the risk–coverage curve (Geifman & El-Yaniv 2017) so the trade-off is visible.
2. **A clear winner:** the gap between the top candidate and the runner-up is ≥ 0.15, the same toss-up rule as in §4b.

Stretch: conformal prediction sets (Angelopoulos & Bates 2021) give the same split with a coverage guarantee. A set with one member is a recognition, and a set with several members is a suggestion. With only ~100 calibration glyphs the guarantee is loose, so it's reported as an add-on, not used instead.

Cluster consistency (from the GMM glyph-clustering work): metal type repeats exact shapes. If most members of a tight cluster are recognised as X, a low-confidence member gets X as its **top suggestion**. It does **not** become a recognition, because the evidence is indirect.

### Where each source goes into the pipeline

| Stage | Practice we adopt | Source |
|---|---|---|
| Ground truth | Diplomatic transcription, a written rules file, a frozen versioned GT file, open glyphs kept as `?` rather than guessed | OCR-D GT guidelines; `gt/RULES.md` |
| Ground truth | Disclose anchoring; do a blind spot-check of fast accepts | Log 22, 47 |
| A. Lines | Compare Otsu with Sauvola binarisation and report both | Binarisation study on 19th-c. print with Kraken (JDMDH) |
| B. Glyphs | Connected components, marks joined to their letter, split into upper/middle/lower zones | VOLTAGE §3 (zone-wise symbols) |
| B. Glyphs | Measure segmentation against the GT spans (we already have them) | Our review data |
| C. Recognition | Glyph features plus nearest neighbour to labelled exemplars. Middle zone = letter; upper/lower/right zones = marks. Mark rules from the checklist (dot count, II tail, U curl, I arch) | VOLTAGE (feature recommendation, cluster labelling); Pandey §4.6–4.10; `gt/CONFUSIONS.md` |
| C. Recognition | Augmentation (small rotation/shear/ink changes) to stretch scarce exemplars. No GANs: too little data | VOLTAGE §3.3 |
| C. Recognition | Optional second exemplar source: Noto Sans and Noto Serif Khojki renders, flagged as synthetic. They follow 1903 type, so they never outrank real exemplars | UniLipi / synthetic Indic HTR; Pandey §3.3 |
| D. Encoding | Logical order, NFC, Khojki-only allowlist, one vowel sign per unit, marks after the letter | Unicode core spec ch. 15; Pandey §4 |
| D. Output | Plain `.txt` plus a JSON sidecar. Optionally **PAGE-XML**, whose `TextEquiv` takes `conf` and multiple ranked alternatives at `Glyph` level, so recognition vs suggestion maps cleanly and the output imports into eScriptorium | PAGE-XML schema (OCR-D) |
| E. Scoring | **Leave one line out** (6 folds). τ and calibration come only from the training lines inside each fold (nested), never from the test line | Standard held-out evaluation; benchmark-methodology skill |
| E. Scoring | **Oracle ablation:** run C with GT boxes, then with predicted boxes. The difference is the segmentation share of the CER. Per-stage tally: segmentation / letter / mark / encoding | Per-stage requirement in the brief |
| E. Scoring | CER over NFC code points, with a bootstrap 95% interval because n is tiny. Report coverage, CER on recognised units, and overall CER | — |
| F. Baselines | VLM given the chart, same lines, same scorer. Treated as a **comparison point, not a reference**: VLMs invent characters on rare scripts. A recognition/suggestion split is only possible if we ask it for confidences, and those aren't calibrated | GlotOCR Bench; the 2026 GitHub "khojki-ocr" project (Qwen2.5-VL-3B few-shot on these pages; repository gone, so we cite the approach only) |
| F. Scale path | Kraken CTC line model once ~800 lines exist. Fine-tuning a pretrained model works from ~20 lines only for scripts seen in pretraining, so for Khojki that is an upper bound. Label more lines in eScriptorium | Kraken training docs; Kiessling 2026 §4.3 |
| Retro | Labelling cost from median seconds per glyph; lines needed compared with Kraken (~800 lines) and VOLTAGE (~14k symbols) | Log 23, 47 |

### Robustness changes to the process

- Freeze GT v1 and record its SHA-256 in the results, so every CER points at an exact GT file.
- Make one config file per run and append each run's results to `results.jsonl`. Results are never overwritten.
- Run `check_lattice.py` and the output validator before every scoring run.
- The VLM never produces or corrects ground truth (§4a).
- An open GT glyph (`?`) is left out of CER and counted separately. A system output is never "right" on a glyph we couldn't read ourselves.

## 8. Claude skills worth using here

- `anthropic-skills:pdf` — page extraction (we already used PyMuPDF directly; poppler isn't installed).
- `agent-skills:doubt-driven-development` — fits a project where most "facts" about the script need checking.
- `ecc:benchmark-methodology` / `ecc:eval-harness` — keep the CER measurement honest (same lines, same script, every run logged).
- `llm-council` — for the one real decision with stakes: cluster-and-label vs. synthetic-trained CRNN as the main recogniser.
- `ecc:architecture-decision-records` — encoding decisions go straight into the retro.
- `ecc:pytorch-patterns` + the `ecc:mle-reviewer` agent — only if we reach the Kraken stretch.
- `avoid-ai-writing` — final pass on README and retro.

## Sources

- [Unicode core spec ch. 15 (Khojki: word separator, Gujarati digits)](https://www.unicode.org/versions/Unicode17.0.0/core-spec/chapter-15/)
- [Final proposal to encode Khojki (Pandey, 2011)](https://www.unicode.org/L2/L2011/11021-khojki.pdf)
- [GlotOCR Bench: OCR models still struggle beyond a handful of scripts](https://arxiv.org/abs/2604.12978)
- [Kraken training tutorial (line counts)](https://kraken.re/main/tutorials/training.html)
- [VOLTAGE: contrastive OCR for ultra-low-resource scripts (Takri), EACL 2024](https://aclanthology.org/2024.eacl-long.53)
- [Kiessling, A Free Lunch? Adapting PP-OCRv6 for Historical Text Recognition (few-shot §4.3)](https://arxiv.org/abs/2609.20064)
- Chow, C. K. (1970). On optimum recognition error and reject tradeoff. IEEE Trans. Information Theory 16(1).
- [Guo et al. (2017), On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599)
- [Geifman & El-Yaniv (2017), Selective Classification for Deep Neural Networks](https://arxiv.org/abs/1705.08500)
- [Angelopoulos & Bates (2021), A Gentle Introduction to Conformal Prediction](https://arxiv.org/abs/2107.07511)
- [PAGE-XML schema (TextEquiv with conf and alternatives)](https://github.com/PRImA-Research-Lab/PAGE-XML)
- [Noto Serif Khojki (second font)](https://fontsource.org/fonts/noto-serif-khojki/about)
- [Ginan Central, USask (catalogue of the Harvard Khojki collection, no transcriptions)](https://ginans.usask.ca/library/search/?id=10)
- [UniLipi: multi-script OCR for historical Indic manuscripts](https://arxiv.org/pdf/2608.28195)
- [Synthetic data for Indic HTR](https://arxiv.org/pdf/1804.06254)
- [Desenrollando el cordel (binarisation and Kraken on 19th-c. print)](https://jdmdh.episciences.org/volume/view/id/656)
- [YALTAi vs Kraken segmentation on small datasets](https://web3.arxiv.org/abs/2207.11230)
