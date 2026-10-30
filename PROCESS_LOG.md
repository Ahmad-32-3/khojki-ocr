# Process log (the aside)

Where we went wrong, what we assumed, how we caught it, what we changed.
Newest at the bottom. Feeds the retro's "AI tools" section.

Format: **Assumption / error → How caught → Fix**

---

## 2026-10-27 — planning round 1

1. **Claude assumed the PDFs could be read directly.** The Read tool needs poppler, which isn't installed; the first attempt returned nothing.
   → Caught by the tool error. → Installed PyMuPDF and extracted text and images with a script.

2. **Claude assumed the Windows console handles UTF-8.** Printing the design doc's box-drawing characters crashed (cp1252). The `PYTHONIOENCODING` workaround failed silently because `python -I` ignores environment variables.
   → Caught by the traceback, then by noticing the fix had no effect. → Used `python -X utf8`. Relevant later: every script that prints Khojki needs this flag on this machine.

3. **"The yellow printed page" was ambiguous.** Two groups qualify: p9–p11 (1896 Narsi Mehta, tan paper) and p42–p47 (cream paper, very clean print).
   → Caught by building a contact sheet of all 47 pages instead of guessing. → Zoomed in: p42–p47 look like Gujarati script, not Khojki. Chose p9–p11; flagged for you to confirm.

4. **Design doc error: anusvara at U+1122C.** That code point is VOWEL SIGN AA; anusvara is U+11234.
   → Caught by listing the whole block from Python's `unicodedata` (Unicode 15.1). → Rule: the code-point table is generated from `unicodedata`, never typed from memory, including by Claude.

5. **Design doc assumption: NFC merges base + vowel sign into one code point.** Wrong. Claude's first guess was that NFC is a complete no-op on Khojki; that was *also* wrong.
   → Caught by brute-forcing every pair of Khojki code points through NFC: one pair changes, VIRAMA+NUKTA gets reordered to NUKTA+VIRAMA. → Keep NFC, add a separate mark-after-letter check.

6. **Design doc: CER against LLM-made ground truth.** Circular if the LLM is also a recogniser.
   → Caught by reading the take-home brief side by side with the design doc: the brief asks us to transcribe ourselves and time it. → Human transcription, LLM as proposer only.

7. **Design doc's Unicode allowlist would delete digits and spaces.**
   → Caught when checking what the brief means by "digits" in the encoding section; Unicode spec says Khojki uses Gujarati digits. → New allowlist (PLAN.md §2 row 3).

8. **AI-generated disclaimer left in the design doc** ("For medical advice or diagnosis, consult a professional").
   → Caught on full-text extraction. → Remove before sharing.

## 2026-10-28 — ground-truth method (round 2)

9. **Claude's round-1 plan had the same flaw as the proposed screenshot flow.** PLAN.md §2 said "LLM may propose a reading; a human confirms each glyph". That anchors you to the model's answer, and it makes the model's own baseline CER look better than it is.
   → Caught when you proposed the screenshot-and-confirm flow and asked whether it was robust; working through that answer showed round 1 had the same problem. → Blind double transcription plus adjudication (PLAN.md §4a).

10. **Choosing a GT tool by features alone.** Transkribus looks easiest, but it means uploading the scans to a third-party cloud service, and the brief limits the pages to this exercise.
   → Caught by re-reading the brief's materials section. → Local tools only.

## 2026-10-28 — building the picker (round 3)

11. **Assumed we'd have "full-resolution" crops.** The image embedded in the sample PDF is only 825×1200 px; body text lines are 56–67 px tall *including* marks, and the dots above letters are a few pixels across.
   → Caught when extracting the page's native image instead of a rendered one. → Recorded as a hard limit on accuracy. Ask whether the brief's "download" link has higher-resolution originals.

12. **NFC made the text box and the saved text disagree.** The picker normalised on save, so typing VIRAMA then NUKTA showed one order on screen and stored the other.
   → Caught by the browser test that clicked those two signs in a row (the reorder found in entry 5). → The text box now shows the normalised text.

13. **Claude's font-coverage test was itself wrong.** A canvas width comparison reported *every* Khojki glyph missing from Noto, including ones plainly visible on screen.
   → Caught by comparing the result with the screenshot. → Dropped the automated test; checked by rendering each sign at 56 px and looking.

14. **Assumed Noto Sans Khojki covers the whole block.** The Google Fonts build has no glyph for U+11241 VOWEL SIGN VOCALIC R (Unicode 15); it shows as a box. QA and SHORT I render fine.
   → Caught by the render test. → Synthetic data can't use U+11241 with this font; the picker still inserts it, shown as a box.

15. **Resolved: vowel-sign placement.** In Noto, no vowel sign is drawn to the left of the consonant (KA + each sign, rendered at 56 px). KA+I is a reshaped ligature, so it's worth a human look. The 1896 type still needs checking against this.

## 2026-10-28 — Claude's blind pass (round 4)

16. **Claude changed the browser tab you were transcribing in.** To screenshot the palette, it hid the picker's header in that tab without first checking whether you were using it.
   → Caught by the browser's notice that you had clicked in the page 10 times. → Restored at once. From now on Claude doesn't touch your tab.

17. **Nearly broke blindness through shared storage.** Opening the picker in a second tab on the same localhost origin would have loaded your saved lines into Claude's view.
   → Caught before doing it, when choosing where to render the reference chart. → Rendered the Noto chart with Pillow from the TTF instead of in the browser.

18. **Confirmed entry 14 properly.** The TTF's character map has every assigned Khojki code point except U+11241. That's stronger evidence than the earlier visual check.

19. **Language prior pulling on the reading.** Words 1–2 of line 1 are the same shape repeated, and there was a pull to read them as a familiar devotional word instead of matching the shapes. That is the failure GlotOCR Bench describes.
   → Noticed while reading. → Transcribed by shape only. The note on line 1 records where this happened, so adjudication can check it.

20. **Blind pass result:** 136 code points, 18 of them `?` (13%). Confidence low for most glyphs; Claude's look-alike groups were E/RA/PA, DHA/JJA, and the MA/BA/BHA family. Saved to `gt/gt_claude.json` as `\u` escapes so it can't anchor you by glance. The hex codes do appear in the session transcript, so don't decode them before your pass.

## 2026-10-28 — first comparison (round 5)

21. **Claude assumed a non-reader could blind-transcribe 5 lines inside the budget.** In round 2 Claude rejected your review-my-guesses flow on robustness grounds without costing the alternative.
   → Caught by your result: 388 s for 10 code points, and you said it was a struggle. → Kept your partial line as a blind control; moved the rest to glyph-level assisted review with top-3 candidates (PLAN.md §4a revision). Your instinct was right about cost; the mitigations are there for the anchoring risk.

22. **Agreement result:** on the overlap, the two blind readings match on 6 of 10 code points (HA E : HA E :). Word 3 disagrees in a revealing way: you read 4 letters (RA RA DA CHA); Claude read RA + vowel sign I + TA + TA with marks. The disagreement is partly **segmentation**: is the tall hooked stroke a vowel sign or part of a letter? Claude also noticed a dot *inside* the bowl of the last glyph that matches nothing in Noto. Unresolved; see `gt/adjudicate_l01_w3.png`.

23. **Labelling-cost number for the retro:** blind, non-reader: about 39 s per code point, about 13 min per line. At Kraken's ~800-line guide, that's ~170 hours. That's the case for cluster labelling plus an expert reviewer.

## 2026-10-28 — confidence scores (round 6)

24. **Risk taken on deliberately: Claude's self-rated confidence.** You asked for a score per character and explicit toss-ups. That's useful for ordering review, but a model's own confidence is often miscalibrated, and treating "0.8" as an 80% chance would be an untested assumption.
   → Raised while designing the score format. → Scores are coarse (steps of 0.05) and add up to 1 including `?`. A calibration table is built from your review decisions, and a second confidence comes from the pipeline's clusters (PLAN.md §4b).

## 2026-10-28 — ligatures (round 7)

25. **Claude compared page glyphs only against bare letters.** Its reference sheet was drawn with Pillow, and this Pillow build has no complex-text shaping (raqm), so it can't form consonant + vowel-sign ligatures. Claude never saw what RA+I or TA+II look like, so it forced ligatures onto bare letters. The "MA/BA/BHA confusion" in entry 20 was partly this.
   → Caught by you, pointing to a consonant × sign matrix (khojki-demo.netlify.app). Claude checked that it uses the same font, Noto Sans Khojki. → Generated our own matrix, `gt/combos.html`, shaped by the browser. Re-read line 1: four spans changed their top reading (words 1–3 now RA+I / NNA / TA+E+ANUSVARA candidates).

26. **Lesson for the pipeline:** any synthetic rendering or template step must use a shaping engine (HarfBuzz: Pillow with raqm, or a browser). Plain Pillow on Windows silently draws unshaped sequences, with no error. The test: render KA + VOWEL SIGN I and compare with the matrix cell.

27. **Language-prior check on the new reading.** Words 1–2 now score HA + RA+I highest, which spells a familiar word. The shape argument (RA's loop plus a flag at the top right) is written next to it in the lattice so you can judge the shape, not the word.

## 2026-10-28 — segmenter and review page (round 8)

28. **First segmenter run found 3 of 6 separators.** The two-dot rule required "no letter overlapping in x", but a neighbouring letter's hook often reaches over the dots. It also counted the page's frame rule as a glyph.
   → Caught by drawing numbered boxes on line 1 and looking. → Separators now = two small stacked dots in the text body; tall thin rules are dropped. Now 5 of 6; one is still merged into the 6-shaped glyph (box 15). Kept as a known **segmentation-stage error** for the retro, and the page has a "box is wrong" flag.

29. **Touching letters stay merged** (box 10 = MA + DHA). Not fixed in the segmenter; the reading for that box covers two letters instead. Counted as a segmentation error.

30. **Kept the scans off hosted pages.** You asked for an artifact; the review page runs locally (`gt/review.html` via the localhost server) because a published artifact would put Harvard's scans on a hosted page, against the brief's "use the pages for this exercise only".

## 2026-10-28 — chart port (round 9)

31. **Claude's own builder was harder to use than the reference chart.** It split "pick letter" and "pick sign" into two grids, so you never saw all the shapes at once. You asked for the khojki-demo chart to be ported exactly.
   → Ported its sections, columns, colours, hover crosshair, filter and glyph-size slider into the review page. Lists come from `unicodedata`, not copied by hand. Two changes: clicking selects instead of copying, and a cell can take an extra mark (e.g. TA+E then + anusvara).

32. **Bug caught in test: every cell showed only the bare consonant.** The helper `cp()` took one code point, so `cp(...[TA, E])` drew TA alone. That would have made the chart look like the old bare-letter sheet, the exact problem from entry 25.
   → Caught by reading the inspector's code points after a click (one code point where three were expected). → Fixed. The test now checks the code points inside matrix cells.

33. **Invalid clusters offered.** The "add a mark" row let you add a second vowel sign, which Noto draws with dotted circles. → Now one vowel sign per cluster; only non-vowel marks can be added after it.

## 2026-10-28 — saving and hand-off (round 10)

34. **Progress lived only in the browser.** localStorage can be wiped, isn't visible to Claude, and has a small size limit that pictures would hit.
   → You asked for saved progress and pictures. → `gt/server.py` (stdlib, localhost only) saves each line to `gt/review/<line>.json` and pictures to `gt/review/img/`. The browser copy stays as a fallback and moves to disk on first load.

35. **"Send it to you" needs a real hand-off.** Claude can't receive pushes from a web page. → On a finished line the page saves, then appends to `gt/review/inbox.log`. A background job of Claude's waits on that file and wakes Claude when it changes.

36. **Testing without touching your data.** The end-to-end test ran on `127.0.0.1` (a different browser origin from your `localhost` tab, so separate storage). Its files were deleted afterwards. Your tab's progress was never read or changed.

## 2026-10-28 — vowel sign II (round 11)

37. **Claude read the II tail as a separate letter.** In Noto, VOWEL SIGN II (U+1122E) is a long tail sweeping down on the right of the letter. Claude saw "MA + a hump with a long tail" and split it into MA + DHA. The segmenter had box 10 as one glyph; it was right, and Claude overrode it with a "touching letters" story (**entry 29 was wrong**).
   → Caught by you: box 10 is clearly MA+II (U+11224 U+1122E), matching the chart's MA row. You spent 452 s on that glyph before flagging it. → Root cause: in round 7 Claude used the matrix to fix only the spans it was already unsure about, and never re-checked every box against every cell. v2 re-reads all 19 boxes against the full matrix.

38. **v2 changes beyond box 10:**
   - Box 8: the "unexplained dot inside the bowl" is most likely MA's closed loop filled with ink, so MA+E+anusvara (0.50) now outranks TA+E+anusvara (0.25).
   - Box 15: independent U + anusvara.
   - Boxes 16–17: SA or unclear.
   - 21 spans → 18.

39. **Possible anchoring, to check in the retro.** For box 8 you picked TA+E+anusvara, which was Claude's v1 top reading; v2 now prefers MA. Your earlier decisions are tagged `lattice: 1`, so calibration and anchoring can be measured per version. Box 8 is worth a second look.

## 2026-10-28 — line 1 reviewed (round 12)

40. **Line 1 result:** 16 of 18 glyphs answered (glyph 15, U + anusvara, and glyph 17, SA, left open) in ~25 min of review time, 1,514 s in total. Most of it went on four glyphs: HA (293 s, the first), RA+I (267 s), MA+II (464 s), and the separator merged into box 15 (223 s).
   - **Every concrete answer (13 of 13) matched Claude's v2 top reading.** That's either good readings or anchoring; review alone can't tell them apart. The blind control can: your blind pass read word 3 as RA RA DA CHA, and the reviewed answer is RA NNA MA+E+anusvara. That's the clearest anchoring-vs-learning question for the retro.
   - Glyphs 2 and 5 (Claude: RA+I) you marked unreadable without a comment. That's the one place reviewed and blind disagree in kind: blind you read them as letter E.

41. **The hand-off didn't say whether it was manual.** The line was sent with 16 of 18 answered, so it was probably the manual button, but the log couldn't tell. → The inbox entry now records manual/complete and the answered count.

## 2026-10-28 — lines 2–5 (round 13)

42. **Lines 2–5 read with the v2 method from the start.** Every box was compared with the full matrix: 75 readings across 4 lines, 9 toss-ups.
   - Recurring shapes got the same reading each time: HA, RA+I, MA+II, and the two-stroke mark between separators.
   - The two-stroke mark (lines 2, 4, 5) is scored as DOUBLE DANDA at only 0.35. It doesn't match the chart well; it may be a refrain or abbreviation mark. A question for a Khojki reader.

43. **New segmentation pattern:** the segmenter often splits SA (two joined P-shapes) into two boxes: line 1 glyph 17, and lines 2, 3, 4. Each case is one reading covering both boxes, scored low because the split hides the shape. This is a segmentation-stage error for the retro.

44. **The frame rule slipped through on lines 3–5.** The filter wanted a rule taller than 1.3× a letter, but these crops cut the rule to the crop height, and its width (6–10 px) was above the width cut.
   → Caught when reading box 21 of line 3 (a plain vertical line). → Rules are now judged by shape: thin relative to their own height, and either spanning ≥85% of the crop or touching its right edge. Verified that only the 4 frame boxes were dropped and every other box index stayed the same, because the readings point at box numbers. Also checked that every box belongs to at least one reading.

## 2026-10-28 — lines 2–5 reviewed (round 14)

45. **Lines 2–5 result:** 64 of 75 glyphs answered, sent manually. 57 of the 64 matched Claude's top reading (89%). Of the 7 changes, 5 picked Claude's second or third candidate and 2 came from the chart:
   - Line 2 glyph 3: KHA+AA → **JJA+AA** (chart, with a note). Not in Claude's top 3.
   - Line 5 glyph 6: RA → **CHA** (chart). Not in Claude's top 3.
   - Line 4 glyph 9: VA+AA+anusvara → NA+AA+anusvara (2nd).
   - Line 5 glyph 10: KHA → LA (2nd).
   - Line 3 glyph 4 and line 4 glyph 14: SA+anusvara → **SA+nukta** (2nd), both times.
   - Line 5 glyph 19: JA+E → JA+E+nukta (2nd).
   - The two chart picks are the cases a candidate list can never get right on its own. For the retro, that's 2 of 64 (3%) outside the lattice.

46. **Every RA+I was left unanswered: 4 of 4 here, plus 2 of 2 on line 1.** That's a consistent signal, not chance. Either Claude's RA+I reading is wrong for this shape, or the shape isn't readable at this resolution. Your blind pass read it as letter E. → It goes in the retro as the biggest open disagreement. The other 7 skips: DHA, SA+AA+anusvara, MA+E, MA+II, HA+E, U+anusvara, JA+E.

47. **Anchoring warning signs in the timing.** 34 of 64 decisions took 2 s or less, and line 4's median was 1 s. All 3 DOUBLE DANDA readings (scored only 0.35) were accepted in 1–2 s. Fast accepts of low-confidence readings are the pattern anchoring predicts, so the 89% agreement is an upper bound, not a measured accuracy.
   - Two timings are idle time, not reading time (line 2 glyph 9: 2,661 s; glyph 5: 503 s). The per-glyph cost estimate must drop outliers, e.g. by using medians.
   - **Nukta vs anusvara isn't settled.** Line 3 box 5 (the second half of SA) has two dots above *and* one below, so neither SA+nukta nor SA+anusvara alone covers it. It may be SA+nukta+anusvara, or the dots may be noise. Needs a closer look before it counts as ground truth.

## 2026-10-28 — a sixth line chosen for new shapes (round 15)

48. **The sixth line is p9 line 9, not line 6.** Lines 6–9 were cropped and compared. Line 9 has the most shapes not yet seen: a 3-curl with a long tail, a v-bowl with a tall rising stroke, a 6-shape with dots, two loop-and-arch variants, and a three-dot HA. Lines 6 and 8 mostly repeat known shapes, and line 7 is half ornament (`====`).
   - The file keeps the page's own line number (`p09_l09`), so ground truth always points at the right place in the scan.
   - **Line 6 is the next candidate.** It has two small circles that may be Gujarati digit zero (U+0AE6). That would be our first digit, which the encoding rules (§5) already allow for.
   - 18 readings. New shapes are scored low (0.25–0.35) on purpose. SA is split again (boxes 6–7), and the two-stroke mark is split into 2 boxes this time. That confirms both segmentation patterns from entry 43.
   - Expect more of my readings to need the chart on this line, since several shapes had no earlier review to learn from.

49. **Line 9 result:** 18 of 18 answered in 407 s, sent automatically when complete. 14 of 18 matched my top reading (78%, down from 89% on lines 2–5). That drop is what we picked this line for. All 4 changes came from the chart, and none was in my top 3:
   - Glyph 2: KA+II → **HA+U**
   - Glyph 7: BA → **MA+II**
   - Glyph 9: HA+I+anusvara → **DHA+nukta**
   - Glyph 18: BA → **NNA+II**
   - **I missed the II tail again, twice** (glyphs 7 and 18), even though I'd been corrected on exactly this in round 11 (entry 37). I read the long right-hand tail as part of a new letter shape instead of as the vowel sign. So entry 37's fix didn't stick, and this shows how the model fails on new shapes. For the retro: a stored list of known confusions (tail → II) should be checked before scoring, rather than relying on memory.
   - **Coding slip:** on glyph 9 the "why" text says HA+U+anusvara, but the code points say HA+**I** (U+1122D; U is U+1122F). The reading was wrong anyway, but the lattice files need an automatic check that the "why" text matches the code points. Lines 2–5 were checked and are fine.
   - **Calibration:** of the 7 readings I scored 0.35 or less, 3 were right (43%). The new shapes I flagged as uncertain really were uncertain, so the low scores were honest. Ground truth is now 6 lines.

## 2026-10-29 — second research pass (round 16)

50. **"No prior Khojki OCR work" was too strong.** A deeper search found a GitHub project that used Qwen2.5-VL-3B few-shot on the same 1896 pages. It now returns 404, so it's probably another take-home submission. It's not available, it wouldn't be ours to use, and it doesn't change the plan. → PLAN §3 corrected.

51. **We were reading the script from a font chart instead of the script's own documentation.** Pandey's encoding proposal explains several things we had to learn by being corrected:
   - Vowel sign II has a long-tail variant after letters with right descenders (entries 37 and 49).
   - Vowel sign U is drawn as an extension of the letter's last stroke (line 9 glyph 2, corrected to HA+U).
   - There is an anusvara variant centred above the letter and an inverted nukta (the nukta-vs-anusvara question in entry 47).
   - Noto's two-stroke U+11239 DOUBLE DANDA looks like the mark between separators, so our 0.35 score was probably too low.
   - The circles on page line 6 (`००`) are more likely ABBREVIATION SIGN U+1123D, which Pandey says marks verse repetition, than Gujarati zero as I guessed in entry 48.
   - The `====` on page line 7 may be SECTION MARK U+1123C rather than an ornament. If so, RULES.md's "ornaments are out of scope" is wrong for it.
   → Should have been read in round 1. It is now the reference for a confusion checklist.

## 2026-10-29 — confusion checklist (round 17)

52. **`gt/CONFUSIONS.md`:** 18 rules from Pandey plus our own corrections, covering vowel-sign forms, dot counts, punctuation, conjuncts, look-alike letters and segmenter splits. Readings now cite the rule number in their `why`.

53. **What it would have caught.** Checked after the fact against your 11 corrections on lines 2–5 and 9:
   - **6 fully caught:**
     - SA+nukta, twice (C7).
     - JA+E+nukta (C7).
     - HA+U (C4).
     - MA+II and NNA+II (C1).
   - **1 partly caught:** DHA+nukta. The checklist gets the nukta (C7) but not the letter.
   - **4 not caught:** KHA→JJA, VA→NA, RA→CHA, KHA→LA. All four are wrong **base letters**.
   - **For the retro:** a written rule list fixes vowel-sign and dot errors. Telling look-alike consonants apart needs more examples of each letter (clusters), not more rules. That's the bottleneck the brief asks about.

54. **Open glyphs re-scored (lattice v3), with only the open glyphs and the two-stroke marks changed:**
   - RA+I: 0.50–0.55 → **0.65** on all 6. Noto's RA+I has the same arch, and Pandey says RA takes that form of I (C3). Your blind "E" reading is now the outside option: E goes up-left, and these arches go right.
   - DOUBLE DANDA: 0.35 → 0.70 on all 4 (C10).
   - U+anusvara: 0.45 → 0.55 (C6).
   - Line 2 g13: → SA+nukta+AA (three dots, C7).
   - Line 2 g4: DHA vs JJA is now a toss-up (C14).
   - Line 9 g9's code points fixed to HA+U+anusvara, to match its `why` (entry 49).
   - Your decisions weren't touched. Every reviewed answer stays as you gave it.

55. **`gt/check_lattice.py`:**
   - Errors fail the run: scores that don't sum to 1, scores off the 0.05 grid, unknown code points, and boxes with no reading.
   - It warns when a `why` names a letter or sign that's missing from that reading's code points.
   - Run on the old files, it flagged exactly the line 9 glyph 9 slip and nothing else.
   - It runs a built-in self-test first.

56. **Second pass on the open glyphs:** 2 more answered, and both were the checklist's top pick. Line 1 g17 is SA (C17). Line 2 g13 is SA+nukta+AA (C7 three dots, C16 upright). **13 stay open**: all 6 RA+I, plus DHA/JJA, MA+E, MA+II, HA+E, U+anusvara ×2 and JA+E. These are the limit of what a non-reader can settle at this resolution. They'll be frozen as `?` and reported as unresolved, not guessed. Nothing new was sent; the answers were saved to disk.

## 2026-10-29 — recognition vs suggestion (round 18)

57. **Your requirement: the system commits only when it's confident; otherwise it suggests, and the two must look different.** Until now every reading of mine was effectively a suggestion shown like a recognition: a rendered glyph with a score. That's the presentation that invites anchoring. → PLAN §7a:
   - **Recognition** = calibrated confidence ≥ τ (set for 95% precision on held-out lines) **and** a clear winner (gap ≥ 0.15). Anything else is a **suggestion**.
   - Suggestions write U+FFFD to the text, never a Khojki character.
   - On screen they are a dashed `?` with options under a "not recognised" heading, distinguished by shape and wording, not just colour.
   - This follows the selective prediction literature (Chow 1970; Geifman & El-Yaniv 2017).
   - PAGE-XML can carry both kinds of output with confidences.

## 2026-10-29 — repository setup (round 19)

58. **Git set up, with scans kept out by two separate guards.**
   - `.gitignore` excludes the PDF, page images, line crops, overlays, review pictures and generated HTML.
   - A `pre-commit` hook also refuses any staged image or PDF (even with `git add -f`) and runs `pytest`.
   - Checked with `git status --ignored`: every scan-derived path is ignored, and only scripts, rules, lattices and your review JSONs are left to commit.
   - The test suite is `pytest` (2 tests: the lattice checker's self-test, and every saved lattice validated).
   - The commit-blocking hook from the skills bundle was rewritten in Python, because `jq` isn't installed. Tested both ways: a passing suite lets the commit through, and a failing one returns `deny`.
   - uv isn't installed, so it was skipped; `pyproject.toml` works with pip.

### Still unverified (don't build on these yet)

- That the 1896 type differs enough from Noto Sans Khojki to break template matching. Step 0 tests it.
- Whether the brief's original download has higher-resolution scans than the 825×1200 PDF images.
- That p36–p38 and p42–p47 are Gujarati. Needs your eye or a closer crop.
- That Keyman's Khojki Inscript keyboard covers every code point we need.
- That a Gujarati or romanised edition of the p9–p11 text exists.
- That the colon-like marks on p9 are all word separators and not, in some places, a different sign.
