# Retro: Teaching a Computer to Read 1896 Khojki

I built a program that reads scanned pages of the 1896 Narsi Mehta print in three steps: it finds the lines, cuts each line into characters, and recognizes each character by comparing it with 150 characters I labelled by hand and 2,666 drawn from the Noto Sans Khojki font. On 2 lines I kept aside until the end, its best guesses had **about 4 in 10 characters wrong** (40.8% character error rate; 38.8% on 9 development lines).

## 1. Error Breakdown by Stage
I gave the program the correct answer for one stage at a time and counted what was left. Of 81 errors: **line detection 0** (all 35 lines found), **cutting lines into characters 19**, **character recognition 64**, **Unicode mapping 0** (every output passes the validator). The most common mistakes are small marks (an extra vowel sign) and look-alike letters, like MA read as BA.

## 2. Experiments That Didn't Work
I started with the simplest recognizer, comparing pixels, and expected to replace it. I never did. Describing shapes by hand (holes, stroke ends) got 27% of first guesses right; pixels got 52%. A cleaning method built for old scans cut 56 of 80 characters correctly; the simple one cut 59. Neural networks from 2026 research all did worse; the best-rated one got 15 more of my 105 test characters wrong, because the fonts show every letter once while the book repeats common ones. Across about 20 changes, the best gained 6 of 105, within luck. What worked was more hand-checked examples: four times as many raised accuracy from 46% to 69%.

## 3. Encoding Decisions
Vowel signs use the Khojki block's own code points (U+1122C–U+11233, U+11241), and marks always follow their letter in one order: nukta (U+11236), then vowel sign, then anusvara (U+11234). Word separators use KHOJKI WORD SEPARATOR (U+1123A), not a colon. Digits are Gujarati (U+0AE6–U+0AEF), as the Unicode standard says. A character with no good guess is written as U+FFFD. Every output line is checked before export: only allowed code points, and marks in the right order after a letter.

## 4. Bottleneck
The program recognizes a character by finding the most similar characters it already knows the answer to. Those known characters come from **labelled lines**: lines from the book where a person has written down the correct character under every shape. Each labelled line gives the program about 19 more real examples to compare against.

**The single biggest improvement is more labelled lines from the book itself, checked by a Khojki reader.** I labelled 11 lines; the 9 used for learning gave 150 real examples, spread across dozens of letter-and-mark combinations, so most have only one to three. The font images can't fill that gap: their strokes are about 40% thinner than the print, and they show every letter equally. A rough projection says **about 14 labelled lines** would put the right letter in the top three suggestions 90% of the time, and about 45 would reach 95%. Reading whole lines at once, as tools like Kraken do, needs about 800.

## 5. Scale
The program takes 15 to 18 seconds a page and costs nothing to run, so all 45 pages would take about 12 minutes. Labelling took at most 44 seconds a character (the timer ran while I did schoolwork); 800 lines would take at most about 190 hours. **Handwritten pages change everything:** characters join and vary by writer, so cutting a line into characters stops working. They need a model that reads whole lines and labelled lines from each hand.

## 6. Where an AI Tool Was Wrong About Khojki
Claude read one character as two letters, MA and DHA. It was one letter, MA, with the long tail of the vowel sign II, and the program's own cutting step had it right. I caught it by comparing the glyph with the MA row of the script chart, after seven and a half minutes on that one character. Its suggestions also kept leaning toward MA, so I rechecked every look-alike letter against the chart, and 15 of my answers changed. Since then, I treat the AI's readings as suggestions and verify every number and output myself.
