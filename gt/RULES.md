# Transcription rules (v1)

Both blind passes (human and Claude) follow these. Change them only between passes, and log the change in PROCESS_LOG.md.

1. **Diplomatic.** Transcribe what is printed. No spelling fixes, no expanding abbreviations, no adding missing marks.
2. **One crop = one line of text.** Use the crops in `gt/lines/` only, not screenshots.
3. **Logical order.** Consonant first, then its vowel sign, then any anusvara or other mark, whatever their position on the page. The picker enforces NFC.
4. **Word separator.** The colon-like two dots between words → U+1123A KHOJKI WORD SEPARATOR. Never U+003A colon.
5. **No spaces.** Printed Khojki separates words with U+1123A, not spaces. Add a space only for a visible gap with no separator, and note it.
6. **Unreadable or unsure.** Type `?` for each glyph you can't identify, and say why in the line's notes. A `?` is better than a guess; guesses become false ground truth.
7. **Marks you can't place** (a dot or stroke you can't assign to a letter) → `?` plus a note, not a best-fit sign.
8. **Out of scope:** page number, running header, the ornament, the frame. Anything at the line's edge that isn't a letter (e.g. a trailing dash) → note it and leave it out.
9. **Digits** → Gujarati digits U+0AE6–0AEF.
10. **Timing.** Leave the picker's timer running only while you work on a line; tick "done" when finished.

After both passes: diff, adjudicate in `gt/adjudication.csv` (line, position, human, claude, final, who_right, reason).
