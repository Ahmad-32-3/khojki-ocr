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

## 2026-10-29 — chunk 0: ground truth frozen (round 20)

59. **The draft commit message said "109 of 122 glyphs decided". The real figure is 98 of 111.** I wrote it from memory, not from the files. It was caught when freezing GT v1 and checking the counts by independent routes:
   - 111 units, both from a raw count of spans and from the freeze script.
   - 98 settled, counted from the review files alone.
   - 13 `?` in the text file, and 13 open units in the JSON.
   - Two glyphs checked by hand: line 9 g2 is HA+U, and line 2 g3 is JJA+AA.
   → From now on, every number in a commit message or the retro gets recounted first (verifying-output skill).
   - GT v1 stores each unit's pixel box, so a future segmenter change can't silently shift the truth.

## 2026-10-29 — chunk 1: line finding (round 21)

60. **Line ground truth was marked by eye before any code was written.** I read line centres off a pixel-ruler image of each page into `gt/lines_gt.json`. That gives 35 text lines: p9 11 (a 2-line heading + 9 body), p10 12 and p11 12. I'd said 13 for p10 and p11 earlier. That was wrong: I counted from a small thumbnail.

61. **Experiments (text lines right out of 35, scored by `gt/eval_lines.py`):**

    | # | Approach | Otsu | Sauvola | What went wrong |
    |---|---|---|---|---|
    | 0 | Old rule (mean − 2σ) with no hand-tuned crop box | 10 | — | Needs the crop box tuned for p9; fails on p10/p11, where the page sits elsewhere |
    | 1 | Frame = biggest ink component | 0 | 0 | The biggest component was the dark scan border |
    | 2 | …excluding components touching the image edge | 0 | 4 | p9's frame touches the border at a corner, so no frame was found |
    | 3 | Frame from its vertical rules | 12 | 18 | The left rules sit against the spine and merge into it |
    | 4 | Frame from its horizontal rules (rows **and** sides) | 35 | 35 | **The score was perfect but the crop was wrong.** The rules fade near the spine, so p9's left edge came out at x=129 and cut off text starting at x≈60. The score only checks rows, so it couldn't see this. Caught by checking the x-range by eye. |
    | 5 | Rows from the rules, sides from the widest run of inked columns | 17 | — | Fragments of the side rules and page edge made every row look inked |
    | 6 | …dropping tall or edge-touching pieces | 33 | — | p9's last two lines joined through a descender |
    | 7 | …splitting over-tall bands at their emptiest row; dropping bands under 0.6× a line height | **35** | **35** | — |
    | 8 | …growing lines into the gaps (capped, never into a dropped band) | **35** | **35** | Two specks on p11 (7 px and 26 px; possibly dots) had been dropped between lines. They're kept now. |

    - **Otsu and Sauvola tie at this stage.** Otsu stays the default because it's simpler. The real comparison happens in stage B, where small dots matter.
    - **Caveat for the retro:** every parameter was tuned while looking at these same 3 pages. There is no held-out page for stage A, so 35/35 is a fit, not a generalisation result.
    - **Known gap:** the line score checks rows only. Horizontal crop errors (as in #4) need the overlay check.

62. **Test strength checked by breaking the code.** With frame detection disabled, the first synthetic test still passed, because other steps covered for it. A page number above the frame was added to the synthetic page. Now the tests fail when the frame step is broken.

## 2026-10-29 — chunk 2: glyph boxes (round 22)

63. **All 9 "separator inside a letter's box" errors had one cause.** The two dots of a word separator are slanted: the lower dot sits 4–7 px to the right, and the two often share no column. The old rule paired dots only if they overlapped horizontally. So each lone dot was joined to the nearest letter.
   - Found by listing the components inside each box that two glyphs shared.
   - → Dots are now paired by centre distance (≤ 0.3 × letter height across, 0.2–0.6 × down).
   - Two separators were still missed because their dots were just over the size limit (9 px vs 9.0; 8 px vs 7.95). A sweep of the limit on the 6 GT lines:
     - 0.3 → 29/31 separators.
     - 0.35–0.4 → 31/31.
     - 0.45 → a false separator (Sauvola).
     - Set to 0.375, halfway between the two failure points.

64. **Stage B results** (`gt/eval_glyphs.py`; 111 GT units = 80 glyphs + 31 separators; every row sums to 111):

    | Segmenter | Glyph right | Glyph split | Separator found | Merges | False separators |
    |---|---|---|---|---|---|
    | Old (`gt/segment.py`, frozen) | 59 | 21 | 22 | 0 | 0 |
    | New, Otsu | 59 | 21 | **31** | 0 | 0 |
    | New, Sauvola | 56 | 24 | 31 | 0 | 0 |
    | Stage A + B (Otsu, the line finder's own crops) | 59 | 21 | 31 | 0 | 0 |

   - **Otsu is the default from here.** It ties Sauvola at stage A and splits 3 fewer glyphs here.
   - Running on the line finder's crops gives the same numbers as the hand-made GT crops. The two crops were lined up by recomputing prep_gt's crop position and by template matching, and the two agreed on all 6 lines.

65. **Splits are left for stage C on purpose. Merges are not allowed.**
   - Gaps between boxes can't separate the two cases. Boxes of one glyph sit −3 to +10 px apart, and boxes of different glyphs sit −11 px and up. Any gap threshold would merge some real neighbours, and a merge can't be undone later.
   - All 21 splits are 2–3 boxes in a row: 18 of 2, 3 of 3, never with another glyph's box between. So stage C will try joining up to 3 neighbouring boxes, which is the standard over-segment-then-recognise approach (Casey & Lecolinet 1996).
   - The splits are: an AA upright cut off (9), SA in two halves (7), double danda in two strokes (4), and VA+AA (1).
   - **Caveat:** the dot-size limit was chosen on the same 6 lines that CER will be measured on. It's one parameter, but it's still tuned on test data.
   - The first separator test passed under the old rule too: my synthetic dots overlapped by 1 px, unlike the real ones. The dots were moved apart so the test fails under the old rule.

## 2026-10-29 — chunk 3a: spec and example bank (round 23)

66. **Ground-truth encoding issue: vowel sign before nukta.** You recorded line 5 g19 as JA + E + NUKTA. Unicode's Indic model puts the nukta straight after its consonant (JA + NUKTA + E). NFC doesn't fix this: vowel sign E has combining class 0, so nothing gets reordered past it. The two spellings would count as different, and CER would mark a correct reading as wrong.
   → The frozen GT is unchanged. `khojki/labels.canonical()` puts trailing marks in Unicode order (nukta, then vowel sign, then anusvara) wherever labels are compared. Chunk 4's validator will enforce it on output. This is an encoding decision for the retro.

67. **Example bank** (`khojki/bank.py` → `data/bank.npz`, gitignored because the real examples are scan pixels):
   - **98 real examples.** That's one per settled GT unit, so the counts match.
   - **2,666 chart examples:** 1,333 labels × 2 fonts. Both fonts draw every label, so the counts match.
   - Each real example contains only its own ink. Stage B now records which ink pieces make up each box, so overlapping neighbours are left out. That refactor left stage B's scores unchanged.
   - Chart renders are shaped by HarfBuzz. A test checks that MA+II comes out with its tail.
   - **The data is thin:** 40 distinct labels, 24 of them with only one example.
   - **The ceiling on real-example recognition:** in leave-one-line-out, only 70 of 98 units have their label on another line, and 31 of those are separators. So at most **39 of 67 non-separator glyphs** can be recognised from real examples. The other 28 can only be suggestions, unless chart examples prove reliable. Counted from the bank, and again straight from `gt_v1.json`.
   - A+NUKTA was in the GT but missing from the chart set. Nukta on vowel letters was added (Pandey 4.10).
   - The comparison picture shows the domain gap. RA, HA, HA+U and SA+NUKTA look close to Noto. MA+II and JJA+AA differ a lot in the 1896 type. The real SA+NUKTA also has a dot below (Pandey's inverted-nukta variant).

## 2026-10-30 — ground truth v2 (round 24)

68. **The ground truth itself is now in Unicode order (your call).** In entry 66 I only reordered labels at comparison time. You wanted the ground truth fixed.
   - `freeze_gt.py` now writes marks in Unicode order: nukta straight after its letter, then the vowel sign, then anusvara.
   - The output is `gt/gt.json` and `gt/gt.txt`, with the version inside the file (now 2). The `gt_v1.*` files are deleted; v1 stays in git history.
   - Checked against v1 from git, unit by unit: **exactly one unit changed**, line 5 g19, from JA+E+NUKTA to JA+NUKTA+E. Unit counts are the same, and the text holds the same characters, only reordered.
   - Glyph scores and the example bank were re-run on v2. The numbers are unchanged.
   - **Root cause:** the review page's "Add a mark" button added marks in the order clicked. It now sorts them into Unicode order, using the same rule as `khojki/labels.py`. Checked that both give the same results in 3 cases.

69. **My fix broke the review page for a few minutes.** The page already had a function called `isMark`. Declaring a second one stopped the whole script from loading, so the line list came up empty.
   - Caught in a test tab on 127.0.0.1, by reading the console errors, before telling you the change was done.
   - → Renamed to `isMarkCp`. A fresh tab loads with no errors and all 6 lines.
   - Your review files weren't touched (their timestamps are unchanged).
   - Lesson: grep the template for a name before adding one.

## 2026-10-30 — chunk 3b: recognition (round 25)

70. **A single threshold hid that glyphs fail the target.** The first held-out run looked fine: HOG recognised 79/196 parts at 96% precision. Splitting the result by kind showed separators carrying it. On glyphs alone it was 21/134 parts at **86%** (95% CI 71–100%).
   - → Calibration and τ are now fitted separately for predicted separators and predicted glyphs.
   - **That exposed a real bug.** A vowel-sign AA upright that came out as its own box matched a separator. It was then recognised under the separator threshold: 3 wrong "separators" on line 5.
   - → Stage B's separator decision (31/31 right) is now binding. Glyph boxes are compared only with non-separator examples, and separator boxes only with separators.
   - Also: the "glyph precision below target" warning didn't print at first. My text replacement hadn't matched, so the check was never added. Spec criterion 6 requires the warning, so it was fixed and checked in the output.

71. **Thresholds need evidence behind them.** With separate groups, the glyph threshold was being set from 3–5 calibration recognitions. It then failed on held-out lines (33–83%). → τ now needs ≥ 10 calibration recognitions behind it.

72. **Result: separators are recognised, glyphs are only suggested at 6 lines.** Leave one line out, nested calibration, ground-truth line crops:

    | Description | Parts recognised | Precision | Glyph letter: top 1 / in top 3 |
    |---|---|---|---|
    | Pixels | 62/196 (all separators) | 100% | 33% / 46% |
    | **HOG (chosen)** | 62/196 (all separators) | 100% | **35% / 49%** |
    | Shape counts | 62/196 (all separators) | 100% | 15% / 19% |

   - **Risk–coverage for HOG glyph letters:** top 10 by score are 90% right, top 15 are 93%, top 20 are 70%, all 77 are 35%. Even the 3 highest-scored are only 2/3 right. So no threshold can reach 95% today, and the 10-example rule isn't what's blocking glyphs. They are close, which gives chunk 7's learning curve a clear target.
   - **Second route:** the shipped code path (`recognise_atoms` + `model.json`), with each line removed from the bank and counted from the output *text* against `gt.json`, gives 31/31 separators in the right lines and 0 glyph characters committed. That matches the evaluation.
   - **Choosing the description:** HOG and Pixels tie on separators. HOG gives better suggestions (49% vs 46% in the top 3). Shape counts give poor suggestions. A description is only eligible if it meets the target on glyphs too; having no glyph recognitions counts as meeting it.
   - **Calibration is coarse.** Most top options show 24% or 0%, because isotonic regression on ~60 glyph points gives a few steps. That's honest, but it doesn't say much. It will sharpen with more labelled lines.
   - **Other build notes:** OpenCV 5 dropped `HOGDescriptor`, so HOG is written in NumPy (my plan had wrongly said OpenCV covers it). Identical examples made the "typical close distance" 0, which made scores NaN. It now has a floor; a synthetic test found this.
   - SPEC.md was updated with what the build changed. 20 tests pass, including the schema check on all 6 real lines.

## 2026-10-30 — chunk 4: whole pipeline and validation (round 26)

73. **The pipeline runs end to end from the PDF:** `python -m khojki.pipeline <pdf> --page N`. It writes `.txt`, `.json` and PAGE-XML to `out/`, which is gitignored like the scans.
   - Pages 9–11: 35 lines, 340 of 1,428 parts recognised (all of them separators), **0 validation problems**.
   - **Checked by second routes:**
     - Page 9's output has the same number of separators as the GT on all 6 GT lines.
     - The PAGE-XML parses on all 3 pages. Glyph elements equal JSON units (211 / 251 / 252). No suggestion ever sits in the answer slot (index 1).
     - The validator flags GT v1 at exactly line 5, character 21: the JA+E+NUKTA case from log 66.
   - **Not verified:** separator counts on p10–p11. Those pages have no glyph ground truth yet; that's chunk 7.

74. **The validator's first version missed a mark straight after a separator.** It only flagged marks with no base at all, and a separator counts as a base. Caught by its own self-check before it ran on any data. → Marks are now valid only after a letter or a placeholder (U+FFFD, or `?` in GT).

## 2026-10-30 — robustness fixes (round 27)

75. **Four checks that fail on their own instead of relying on me to read output** (from the 8 suggestions; your call to build 3–6 now):
   - **`gt/check_real.py`, the real-data tier.** It exits 1 on any regression. Checked: the PDF's SHA-256, the GT is valid Unicode, the bank was built from this GT, the model was fitted on this bank, 35/35 lines, 31/31 separators, no merges, ≥59 glyphs in one box, separators recognised with no errors, glyph precision ≥95% (or no glyph recognitions), suggestion top-3 ≥49%, and the whole pipeline on p9–p11 with 0 validation problems. It takes 18 s, and skips cleanly when the scans aren't on the machine.
   - **Every GT glyph must lie inside a found line.** This closes the blind spot from log 61, where the line score checked rows only.
   - **`gt/results.jsonl`.** Each run appends its numbers, commit, whether there were uncommitted changes, GT version and SHA, and bank fingerprint. Commit messages and the retro copy numbers from here, not from memory (log 59).
   - **Stale-model guard.** The bank stores the SHA of the `gt.json` it was built from, and the model stores the fingerprint of the bank it was fitted on. The pipeline refuses to run on a mismatch and says how to fix it.
   - **Pre-commit hook.** It now runs pytest, then `check_real.py --no-log`. It's moved to a tracked `hooks/` folder, enabled with `git config core.hooksPath hooks`, so it survives a fresh clone.
   - **Each check proved able to fail** by breaking one thing at a time:
     - A stale model → refused, and reported.
     - Line crops shifted 30 px right, as in log 61 → "8 GT glyphs fall outside every found line". The old row-only score would have passed this.
     - Separator detection disabled → fails on separators.
     - An injected validation problem → fails on the pipeline.
     - The unbroken code passes.
     - The 4 failing rows those break tests wrote to `results.jsonl` were removed, because they weren't real runs.
   - **Two slips caught along the way:**
     - `check_real` crashed on the stale model instead of reporting it. Now it catches the error and reports it.
     - The `--no-log` switch first didn't apply, because my text replacement failed. A `&&` chain then silently ran the *old* hook. Caught because the hook's output lacked the check_real lines.
   - My comment said the .npz file's bytes change on every rebuild. They don't: a rebuild gave an identical file hash. The comment was corrected. The content fingerprint is kept anyway, because it doesn't depend on how the file is written.

## 2026-10-30 — chunk 5: CER and per-stage errors (round 28)

76. **Line finding first added 15 errors, though chunk 1 scored it 35/35 and chunk 2 found identical box positions.** The box scorer checks *where* boxes are, not *what ink is in them*. Traced unit by unit:
   - My first guess was wrong. I thought Otsu thresholds differed between crops; they were identical, and no pixel flipped.
   - **Real cause 1: letter height.** The "typical letter height" was a median over all pieces in the crop. Stage A's taller crops include fragments of the neighbouring lines, which shifted it by 0.5–2 px. That alone changed splits and readings (line 2, where it didn't shift, gave identical output). → Measured only from pieces not cut by the crop's top or bottom edge.
   - **Real cause 2: edge ink.** Thin frame-rule slivers touched the *left* edge, and the rule filter only knew the right edge. Neighbour-line descenders were attached to letters as marks. → Side-rule pieces are dropped. So are pieces cut by the top or bottom edge, but only if centred in the outer quarter of the crop: GT crops have 6 px padding, so dropping all edge pieces lost 2 real glyphs. That was caught by the box score, and fixed.
   - Result: line finding adds **1** top-1 error instead of 15. Box scores are unchanged on both crop types. **Recognition also improved** (held-out glyph letter top-1 35%→39%, in top 3 49%→56%), because a steady letter height makes the size features consistent.

77. **CER, leave one line out, nested calibration, 142 reference characters** (`gt/eval_cer.py`; numbers from `results.jsonl`):

    | Setup | Top-1 CER | Strict CER |
    |---|---|---|
    | Recognition only (GT glyph groups) | 45.8% (65) | 97.2% |
    | + own glyph split | 49.3% (70) | 110.6% |
    | + line finding = whole pipeline | **50.0% (71)**, 95% CI 42–57% | 112.0% |

   - **Per-stage tally of top-1 errors:** recognition 65, segmentation 5, line finding 1. Recognition is the bottleneck by far, which is what more labelled lines (chunk 7) address.
   - **Strict CER is over 100%** by design: each unrecognised glyph writes two U+FFFD (letter and signs), even when it has no sign. The retro must explain this rather than quote it bare.
   - **Most common recognition errors:** E read as AI (4), and missing or extra nukta / anusvara (dots, 4+3+2). Dots at this resolution are the weak point, as predicted in PLAN §4.
   - **Second routes:**
     - The reference length counted straight from `gt.txt` is 142.
     - An independent edit-distance implementation gives all six distances exactly. It's kept as a test.
     - Line 9's alignment was checked by hand. It shows a split-off AA upright read as DANDA, and DHA read as MA.
   - **`check_real.py` now also fails if CER rises.** The baselines are top-1 0.500 and strict 1.120, and the suggestion baseline is raised to 0.558.
   - **My slip:** I rounded 0.558 to 0.56 in the baseline, so the check failed on correct code. → Exact value set, and the failed row removed from `results.jsonl`.
   - **Unexplained:** two runs (check_real, and the picture) stalled for more than 10 minutes with almost no CPU, then finished. Re-runs took 18–25 s. They happened at 4–6 a.m., so the machine sleeping is likely, but not confirmed.

## 2026-10-30 — chunk 7 step 1: blind test set (round 29)

78. **Order decided: blind test set first, then the labelling rounds, then the vision-model baseline (chunk 6).** You asked for whatever's best for the pipeline. Every number so far comes from the 6 page-9 lines that every setting was tuned on, so a fair score needs lines nothing has been tuned on. Both the pipeline and the baseline will be scored on those same lines.
   - **The test lines were picked by a rule fixed in advance, to avoid choosing easy ones:** the middle line of each new page, p10 line 6 and p11 line 6 (line finder's order). They have 21 and 22 spans.
   - **Blind:** every span shows only "?", with no candidate and no confidence. You build each glyph from the chart. The grouping of boxes comes from the pipeline's own split; that's grouping, not content, and "box is wrong" is still available.
   - **They can never leak into learning or tuning:**
     - The lattice and GT line carry `split: "test"`.
     - The example bank skips test lines.
     - `lines_and_truth()`, the glyph scorer and `check_real` read dev lines only.
     - Test lines will be scored only by a separate `eval_test.py`, after the rounds.
   - **Tooling for new lines:**
     - `gt/prep_lines.py` crops with the pipeline's line finder (prep_gt's fixed crop box doesn't fit p10/p11) and records each crop's page position in `gt/lines_index.json`.
     - The lattice states which segmenter made its boxes. Old lines keep the frozen one, so their span indices stay valid; new lines use the pipeline's.
     - `freeze_gt.py` skips lines not yet reviewed.
   - **Checked:**
     - Refreezing leaves the 6 existing lines' units identical to the committed GT, and `gt.txt` unchanged. Each line only gains `split: "dev"`.
     - The stale-bank guard correctly fired, because `gt.json`'s bytes changed. After the rebuild, the bank's content fingerprint was unchanged, so the model stayed valid.
     - `check_real` passes with the same numbers. 26 tests pass.
     - The review page shows both blind lines with no candidates and no console errors. The test tab created no review file.

79. **"The page is empty": my first diagnosis was wrong.** The empty line list and broken image matched the `isMark` crash from log 69, so I guessed a cached copy of that broken page and added no-cache headers to the server. The preview tab list showed the real cause: the open tab was `file:///…/gt/review_template.html`, the **template** with its `__LINES__` placeholder unfilled, not the served `localhost:8765/review.html`. → Reverted the server change, since it was built on a wrong cause, and opened the right page in a new tab. Lesson: check *which page* is open before theorising about *why* it's broken.

80. **Protocol change, your call: the test lines are assisted, not blind.** On the first glyph you couldn't tell which vowel letter a shape was without knowing how independent vowels work, and you decided suggestions were worth the bias ("I will handle that"). Recorded as is:
   - p10 l6 and p11 l6 are still **test** lines. They're never learned from and never used for tuning, so the scores stay *held-out*.
   - But their truth was made **with my suggestions shown**, so the scores aren't *independent of my reading*. The retro must say this.
   - **The pipeline's own suggestions are never shown on test lines.** A system that shapes its own answer key is a worse bias than an outside reader.
   - First case (p11 l6 g1): I showed the candidate vowel letters drawn in Noto, plus your two earlier decisions on similar shapes. The p9 l5 g1 plain 6-shape (you chose O) is a different family. The p9 l1 g15 crescent-plus-dot (still open) is the same family.

81. **The test lines now have my scored readings, as on page 9 (your call: "I need to save time").** They're still `split: "test"`, never learned from and never tuned on, but reviewed with my suggestions (`assisted: true` in the lattice).
   - **Chart builder bug:** "Add a mark" only worked on consonants, so a vowel letter could never take anusvara and U+anusvara couldn't be built. → Vowel letters now take anusvara and nukta only (Pandey 4.9–4.10). Consonants are unchanged, and punctuation takes nothing. Tested in a test tab: U → +anusvara gives U+11203 U+11234.
   - **I regrouped the pipeline's boxes while reading.** It had joined two letters (p10 boxes 0+1) and split SA, MA and O in several places. A single box holding a digit, a separator and a section mark (p11 box 20) became 3 readings on the same box, as was done on page 9.
   - **New in the data:** Gujarati digit 2 twice (a verse number, "22") before a separator and a **double section mark** (p11). Two **abbreviation signs** then a danda (p10). That's the pattern log 51 predicted for page-9 line 6.
   - **Stage B bug the dev checks couldn't see:** on p11 l6, the page frame's vertical rule survived as a "glyph" (box 22). The rule filter needs a thin piece that's near full-height or touching a side, and this crop's rule did neither. The p9 checks pass because p9 crops don't hit it. To fix after the test lines are frozen, and to be measured on dev lines only, so the test stays clean.

82. **Test lines reviewed; GT v3 frozen. My top reading was right on 32 of 41.**
   - **p10 l6:** 16 of 21 matched my first reading. You took my second reading on 2 (JA, not HA: the C-rule pair again). 3 are left open with notes.
   - **p11 l6:** 16 of 20 matched my first reading. **Glyph 7 is QA + U** (U+1123F U+1122F), which I didn't offer at all. QA is a Unicode 15 letter that page 9 never showed. **Glyph 15 is a danda**, where I read a Gujarati 2. Glyph 16 (my second "2") and glyph 11 are open. The frame rule (glyph 20) is open, as planned.
   - **Where I was wrong:** I read a loop joined to a letter as MA + II. You saw a separate piece: an abbreviation-like loop or QA's loop. My readings went to the nearest whole letter I knew, not to the parts.
   - **Your idea, built: describe unknown glyphs by their parts.** When a unit of 2–3 boxes has no confident reading as a whole, the pipeline now also reads each box alone. It gives "components: A + B" as one more suggestion: in the `.json`, as a PAGE-XML TextEquiv with `comments="suggestion: components …"`, and in pre-filled review lattices. On p10 l6, boxes 15+16 now come out as **ABBREVIATION SIGN + DA**, which is the split you saw.
   - **Limit:** it only splits where stage B already found separate boxes. A loop *joined* in ink to its letter (p11 glyph 11) is one box, so it gets no components. That needs stroke-level splitting, which isn't built.
   - **Second-route checks on the freeze.** v2→v3 diff: all 6 dev lines byte-identical, 2 new test lines. Units: 111 + 21 + 20 = 152. Confirmed: 98 + 18 + 17 = 133. Bank still 98 real (test excluded). `check_real` gives identical numbers to the baseline. 27 tests pass.

83. **Frame-rule fix, test-line scorer, and two bugs the second route caught.**
   - **Frame rule (log 81).** The p11 l6 frame piece was 3 px wide, 48 px tall, cut by the crop's top edge, 6 px in from the side. The filter wanted it nearly full height (68 px) or within 3 px of a side, so it missed on both. → A thin piece cut by the top or bottom edge and taller than 1.5 letters now counts as a rule too. Before changing anything, I listed every piece that rule would catch on all 35 lines of pages 9–11: every one was within 25 px of a side, so it's always the frame. **Measured on page-9 lines only:** pipeline CER top-1 50.0% → 48.6%, strict 112.0% → 110.6% (a p9 line had a broken frame piece too). Baselines updated. The new test failed before the fix and passes after it. A danda-like stroke in mid-line stays text.
   - **My first version of that test was wrong:** its synthetic rule was shorter than 1.5 letters, so it failed with the fix as well. I fixed the test, not the code.
   - **Bug 1, found by the second route: answers sharing a box were lost.** The scorer's reference for p11 l6 had 23 characters, but gt.json has 24. The truth was keyed by box, and box 20 holds three answers (an open digit, a separator, a section mark), so only the last one was kept. → Answers sharing a box are joined in order. Dev lines never had shared boxes (6/6 matched before and after), so the dev numbers don't move.
   - **Bug 2: the stage B fix broke the test lines' box numbers.** Lines from `prep_lines.py` recomputed their boxes from the *current* glyph code. Dropping the frame piece removed box 22, and the refreeze crashed. → Lattices now store their boxes when prepared. The two test lines got theirs back from the committed (pre-fix) code. The refreeze is **byte-identical** to v3.
   - **`gt/eval_test.py`:** scores the test lines with the committed dev-only model, asserts no test line is in the bank, and uses the same three setups as `eval_cer.py`. Smoke-run without printing scores. Reference lengths match a direct count from gt.json (23, 24). **Not run for real until the rounds end.**
   - **Chunk 7 round 1 prepared:** p9 l6, p10 l3, p11 l3, one per page, so learning isn't page-9 only. Pre-filled with the pipeline's own suggestions plus components. Round 0 (now): 6 dev lines; page-9 CER top-1 48.6%; glyphs recognised 0; glyph top-3 55.8%. The test lines took 694 s (11.6 min) of review for 41 glyphs.

84. **Round 1, first two lines; a recheck page for MA / DHA / JA (your call).**
   - **p11 l3** (6.5 min): the pipeline's first suggestion was right on 14 of 17 answered glyphs. CHA ×2 and JA came from the chart. 2 open, 1 not answered.
   - **p10 l3** (10.4 min): right first on 12 of 15 answered. 5 left open **as a flag**, with notes. JA was read as MA twice: glyph 3 "very obviously a Ja", glyph 13 "Ja + II". Glyph 12: "Ma + U + anusvara", with the question why the chart's MA+U didn't match. **These suggestions came from the pipeline, not from my readings.** That's the point of this round, and it's what's failing.
   - **Why the chart doesn't rescue it.** (1) By design, a chart drawing alone can never make a *recognition*, only a suggestion (SPEC criterion 7): Noto's shapes aren't the 1896 type. (2) The matcher compares the whole 48×48 glyph with HOG. MA and JA share the right-hand arch and differ in the small left part, so the arch dominates the distance. (3) There are few real examples: JA+II has very few, MA+II many, so the vote leans to MA. More reviewed lines fix (3). (2) may need a description that weighs the left part. To be decided on the learning curve, not guessed.
   - **Recheck page** (`gt/build_recheck.py`, `recheck.html`): every reviewed glyph whose answer **or** pipeline guess is MA, DHA or JA (34). Each shows the crop next to Noto drawings of the three letters, alone and with II/U/AA/O. Answers save to `gt/review/recheck.json` and change nothing until applied. Tested in my own tab: a save of JA + II with the old anusvara kept wrote the right code points. The test file and log line were removed afterwards.

85. **Recheck applied, GT v4 frozen, round 1 measured.**
   - **The recheck page lost 8 of your answers.** It saved a note only on cards where a letter button was also pressed. You wrote 8 answers as notes alone. I read them from the open page. → A note alone now saves. Five notes were clear and are applied (NA+II ×2, TA+II, TA, HA). Their wording is kept in `gt/apply_recheck.py` with the note text.
   - **Three notes I couldn't read for sure:** p09_l09 g18 "NNA" (was NNA+II: keep the II?); p11_l06 g7 (test) "Na" (was QA+U: NA+U or NA?); p09_l04 g18 "not BA+I, unless flipped" (set to open). None of the first two are applied yet.
   - **15 answers changed** (9 buttons + 6 notes). Mostly MA → BA (5) and MA → TA/JA. One test-line answer went JA → MA (p10 l6 g4). Old answers are kept as `was`. Backup taken before applying.
   - **GT v4:** 11 lines, 210 units (152 + 18 + 20 + 20), 186 confirmed. Bank: 150 real (98 + 51 new + 2 notes from open − 1 to open).
   - **Round 1 on the learning curve** (dev, leave one line out; 6 → 9 lines; 98 → 150 real examples):
     - suggestion top-3: 55.8% → **64.8%**
     - pipeline CER top-1: 48.6% → **40.2%**
     - glyphs recognised: 0 → 0. Nothing passes the 95% bar yet.
     - review time: 32.4 min for 3 lines (p9 l6 15.5, p10 l3 10.4, p11 l3 6.5), plus the recheck.
     - The refit now prefers raw pixels to HOG.
     - **Caveat:** each round is scored on its own dev set, so the two rounds aren't measured on the same lines. The test lines give the fixed comparison, at the end.
   - **The strict CER gate failed (1.106 → 1.206), and I reset it rather than fixing code.** Strict writes 2 U+FFFD per unrecognised glyph. The new lines have more glyphs per separator, and no glyph is recognised yet, so strict rises on a bigger set without any code changing. Baselines now say which GT they were measured on, and are reset when the GT grows.

86. **The three unclear notes, answered in chat; GT v5.**
   - You asked me to put the glyph, your note and the question in chat instead of making you open a page. I sent one picture of the 4 crops next to font drawings of the options.
   - Your answers: p09_l04 g18 is no character we can identify (stays open). p09_l09 g18 is plain NNA (the II is dropped). p10_l03 g13 is JA+II (the recheck button had saved plain JA). p11_l06 g7 (test) stays QA+U.
   - **2 answers changed.** Backup taken before applying. Bank still 150 real examples.
   - suggestion top-3 64.8% (same). Pipeline CER top-1 40.2% → **38.8%**. Strict 120.6% (same). check_real passed. 29 tests pass.

87. **Labelling stopped; test lines scored once; retro written (your call).**
   - Test lines (p10 l6, p11 l6, 49 reference characters): pipeline top-1 CER **40.8%** (20/49), strict 120.4%. Per line: p10 l6 21.7%, p11 l6 57.7%. Run once, on GT v5 and the v5 model, logged to `results.jsonl`.
   - Dev refresh (209 characters): top-1 38.8%, strict 120.6%. Errors by stage: recognition 64, segmentation 19, line finding −2.
   - Pipeline time: 11.2 / 13.1 / 12.2 s for p9 / p10 / p11 on this laptop's CPU.
   - Review time: 9,204 s (153 min) over 11 lines, from the `seconds` field of every decision.
   - **Second routes:** reference lengths recounted from `gt.json` (209 dev, 49 test). Review time summed again with a regex over the raw files. Both match.

88. **Tried recent techniques to improve recognition; none helped significantly (your request).** `gt/exp_vision.py`, dev lines only, test lines untouched.
   - **Diagnosis first.** Real print strokes are 3.67 px wide at the 48 px scale; the Noto renders are 2.59 px. Relative glyph size matches once labels are matched (MA+II's II tail is shorter in print).
   - **Harness fix.** Scoring on the program's own split changed the glyph count per variant (114-124), so the first comparison was apples to oranges. Now scored on the 105 GT glyph groups, compared glyph by glyph (exact McNemar). Baseline reproduces eval_recognise's numbers through the old route (52.5% / 64.8% on its own split).
   - **Results** (letter, held-out, baseline pixels 68.6% top-1 / 85.7% top 3):

     | Variant | Top-1 | Top 3 | p (top-1) |
     |---|---|---|---|
     | Thicker renders (2x2 dilate) | +1 | -4 | 1.00 |
     | Thicker + 4 degraded copies each | -4 | -4 | 0.39 |
     | + 4 jittered copies of each real glyph | +4 | -5 | 0.34 |
     | Sans renders only | +2 | -3 | 0.69 |
     | Real examples weighted x3 in the vote | +3 | 0 | 0.45 |
     | Ensemble pixels + HOG | **+6** | 0 | 0.11 |
     | Small CNN trained per fold on the augmented bank | +4 | -1 | 0.50 |

   - **Reading:** with 105 glyphs, nothing reaches significance, and 11 variants were tried, so the best one (+6) is what chance alone would often produce. Nothing is adopted into the pipeline. Degraded copies hurt: they outnumber the real examples among the 7 neighbours.
   - **Compare:** labelling 3 more lines (+52 real glyphs) moved top 3 by 9 points (log 85). More real examples is the lever; the model is not.
   - **Not tried:** frozen pretrained features (CLIP / DINOv2). They need a weights download. A 2026 study on 64 px manuscript glyphs found frozen DINOv2 weak and frozen CLIP best (P@1 0.40), and domain adaptation on unlabeled real glyphs (SimCLR + DANN) best of all (0.59).

89. **Built a domain-adaptation recognizer (SimCLR + DANN); it lost to plain pixels (your request: a showcase technique).** `gt/exp_adapt.py`, dev lines only, test lines untouched.
   - **What it is.** A small CNN trained per fold with up to three losses: name the label of each bank example (supervised), match two random print-like views of the same glyph (SimCLR, on 722 unlabelled crops from the 24 page lines that are not GT), and fool a render-vs-real head through gradient reversal (DANN). The embedding is the kNN description. Method follows arXiv 2609.07159.
   - **No leakage.** The unlabelled pool excludes all 11 GT lines (find_lines' order matches the hand-marked centres: 11/12/12 lines). Labels of the held-out line are removed per fold, as before.
   - **Results** (same 105 glyphs as log 88, baseline pixels 68.6% / 85.7%; 800 steps, 1 seed, CPU, 16-58 min per variant):

     | Variant | Top-1 | Top 3 | p (top-1) | Right-label renders in 7 nearest |
     |---|---|---|---|---|
     | Baseline pixels | 0 | 0 | | 0.75 |
     | Supervised CNN | -8 | -5 | 0.13 | 0.91 |
     | + SimCLR | -3 | -8 | 0.68 | 1.02 |
     | + DANN | **-15** | -7 | **0.00** | 0.92 |
     | + SimCLR + DANN | -4 | -10 | 0.50 | 0.91 |

   - **Reading:** the adaptation did what it is for: renders of the right letter became more frequent neighbours (0.75 -> up to 1.02 of 7). But accuracy fell. Pixels wins through its real neighbours; a learned space pulls in more renders and so dilutes them. DANN alone is significantly worse: with 722 unlabelled glyphs and no labels on the real side, matching the two domains as wholes also matches wrong letters (known negative transfer). SimCLR softens that (-3 vs -8 for supervised alone).
   - **Limits:** one seed per fold, 800 steps, no tuning of the loss weights (tuning on 9 lines would overfit). Seeds alone can move a CNN by a few glyphs.
   - **Second route:** the baseline row reproduces log 88's 68.6% / 85.7% through this file's own scoring loop. 29 tests pass.

90. **Learning curve: recognition climbs steadily with real labels (your request).** `gt/exp_curve.py`, dev lines only, 2 min on CPU.
   - Same 105 glyphs and pixels kNN as log 88. In each fold a random share of the real examples is kept (renders always stay), 5 draws per share.

     | Real examples kept | Real glyphs per fold | Top-1 | Top 3 |
     |---|---|---|---|
     | 25% | ~33 | 45.9% +- 1.6 | 65.7% +- 2.5 |
     | 50% | ~67 | 58.1% +- 1.8 | 76.2% +- 1.6 |
     | 75% | ~100 | 65.1% +- 2.3 | 80.6% +- 3.1 |
     | 100% | ~133 | 68.6% | 85.7% |

   - **Reading:** every step up in real labels helps, and the gap between steps is many times the spread between draws. This is the evidence behind "data is the lever": quadrupling the real labels moved top-1 by 23 points; the best model change in log 88 moved it by 6.
   - **Projection (rough):** a power-law fit, top-3 error = 2.92 n^-0.60, puts top 3 at 90% near ~270 real glyphs (~14 lines) and 95% near ~850 (~45 lines). Four points over a 4x range, on top-3 letters only: a planning guess, not a promise, and much lower than Kraken's ~800 lines for a whole line recognizer.
   - **Second route:** the 100% row reproduces log 88's baseline exactly (68.6% / 85.7%).
   - Re-weighted DANN (renders drawn at the real letter mix, to test the label-shift diagnosis of log 89) is running; results go in the next entry.

91. **Trusted glyphs committed by rule; re-weighted DANN; README (your request).**
   - **Your rule:** glyphs you labelled at a glance and that are always read right should be recognised. Built as: median labelling time <= 5 s, never changed by a recheck, and right every time the recognizer picked it on held-out lines (at least twice). Tested on the pick, not the truth: DANDA took 1 s and was always found, but 19 of 22 picks of it were wrong.
   - **Trusted list (all dev lines):** A+NUKTA, AA+ANUSVARA, SA+AA, SA+NUKTA, HA+U+ANUSVARA. 14 of 14 right when picked. They are recognised whatever their score, marked `"rule": "trusted glyph"`, with the other options still listed. On pages 9-11 the pipeline now commits 21 of them (11 / 9 / 1).
   - **Second route, and it disagrees.** Choosing the list without each held-out line, then scoring that line: 12 glyph parts recognised, 5 right (**42%**). The folds trusted RA (10 of 10 without p11 l3, wrong on it), MA, NA, HA+U, DOUBLE DANDA. "Right every time" on 2-10 picks is weak evidence. So the list is your judgement, kept because you asked; it is not a measured 95%. Dev and test CER are unchanged (eval_cer fits its own nested model without the rule).
   - **Re-weighted DANN** (renders drawn at the fold's real letter mix): -3 glyphs top-1 (p=0.63), -4 top 3, vs -15 / -7 for DANN alone. Supports the label-shift diagnosis of log 89; still not better than pixels. SimCLR + DANN re-weighted: -4 top-1 (p=0.50), -8 top 3, the same as without re-weighting (-4 / -10): SimCLR had already absorbed most of the damage.
   - `tests/test_recognise.py` now allows a recognition below tau only for a glyph on the model's trusted list. 29 tests pass. `README.md` written.

92. **Trusted glyphs removed (your call); install and run fixed.**
   - The commit hook's real-data check blocked a commit: with the trusted-glyph rule on, committed glyphs were right 5 of 12 times (42%) on held-out lines, against the 95% bar. That's the weakness log 91 found. You chose to drop the rule rather than loosen the check, because the site promises 95% for every accepted character.
   - Removed from `recognise.py`, `eval_recognise.py` and the test; model refit with no trusted list. eval_recognise now meets the target again ("chosen: pixels", no warning).
   - The hook had also been blocking every commit since the hero image was staged: it rejected any image file. It now allows images under `site/` (generated artwork, no scan pixels) and still blocks images everywhere else.
   - `pip install -e ".[dev]"` failed: setuptools found six top-level folders. `pyproject.toml` now names only `khojki`, and uses headless OpenCV (the one already installed; the pipeline opens no windows).
   - The run docs pointed to the PDF in the project folder; it's in `data/`. Fixed in README and site. Bad input (missing file, PDF without `--page`, unreadable image) now prints one line instead of a traceback.
   - **Second route:** every documented command run as written: install, PDF page 9 (11 lines, 0 validation problems), a page image, 29 tests, eval_cer (64 + 19 - 2 = 81 errors, unchanged).
   - The pipeline now prints a plain summary per page (lines, separators, characters written vs left as suggestions, files) and eval_cer ends with an "In plain terms" block. Scans moved to `khojki-scans/` (only its README is committed). Measured run time: 14.8 / 18.1 / 16.4 s per page including start-up, 10.8 s of processing on p9; the site's "about 12 s" is corrected to 15-18 s. Pages 9-11 are the yellow 1896 print; 1-6 and 12-14 are handwritten.

93. **Live demo built (your request).** `demo/server.py` (stdlib, localhost only) serves the site at `/`, the demo at `/demo/`, and `/api/samples`, `/api/run`, `/api/image/<id>.png`. One pipeline run at a time (the bank's feature cache isn't thread-safe); paths can't escape `site/` or `demo/`; uploads over 25 MB, unreadable files and PDFs without a page get a plain 400.
   - Samples: Figures 1-3 = pages 9-11 (the 1896 print), Figures 4-5 = pages 18 and 23 (other prints, never tested; Figure 4 comes out mostly red, which is honest).
   - Colours: green = written as text (95%+), orange = suggestion, red = suggestion whose best guess is under 30%. Your definition of red (glyphs repeatedly missed in the ground truth) needs per-letter error stats; not built in the time left, and the legend says exactly what red means.
   - Checked in the browser: connection (samples, run 8.9-9.9 s, image, bad upload 400, `../` blocked), all three stages draw in order, glyph clicks and arrow keys move the inspector, upload of a page image gives the same result as the sample, phone width has no sideways scroll. Fixed on the way: Run enabled before samples loaded; boxes drawn as faint dots (Chrome ignores pathLength on rect); zoom box filled solid.

94. **Threshold check; kept 95%; best-guess line in the demo (your call).**
   - Held-out letters committed at lower bars: 95% none of 122; 90% 2 (1 right; the wrong one was a badly cut box); 80% 4 (3 right); 70% 37 (19 right, 51%). At 90% the full fit still commits no glyph letters, because no threshold has the required 10 recognitions behind it, and model selection switched to "shape" (it meets 90% by committing nothing). Reverted to pixels at 95%; model unchanged.
   - Your notes: every correction is in GT v5 and the bank. Checked: the bank's 150 real examples equal those built from gt.json now, and both carry gt sha 6d8fc96a.
   - Demo: under the coloured boxes, the line's best guess as Khojki text in the same colours; click a character to inspect it.

95. **Figure 5 removed from the demo (your call).** Page 23 is a different print with ornamental vine borders: a band of ornaments between every line and a column down each side. The line finder (built for the 1896 print's plain ruled frame) took each ornament band as a text line and the side ornaments as glyphs, and the recognizer has no "not text" answer, so it guessed letters for ornaments. Fixing it means teaching line finding to skip ornament bands; not done in the time left. Figure 4 (page 18, another print, 62 of 101 glyphs red) was removed too, so the demo shows only the 1896 print it was built for: Figures 1-3.

### Still unverified (don't build on these yet)

- That the 1896 type differs enough from Noto Sans Khojki to break template matching. Step 0 tests it.
- Whether the brief's original download has higher-resolution scans than the 825×1200 PDF images.
- That p36–p38 and p42–p47 are Gujarati. Needs your eye or a closer crop.
- That Keyman's Khojki Inscript keyboard covers every code point we need.
- That a Gujarati or romanised edition of the p9–p11 text exists.
- That the colon-like marks on p9 are all word separators and not, in some places, a different sign.
