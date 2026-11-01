# Retro: Teaching a Computer to Read 1896 Khojki

**The task.** Khojki is a script used by the Khoja community of South Asia, mostly for religious texts. I was given scans of an 1896 printed book and asked to turn them into digital text, measure how accurate it is, and explain what goes wrong. I built a program that reads a page in three steps: it finds the lines, cuts each line into characters, and recognizes each character by comparing it with 150 characters I labelled by hand and 2,666 drawn from Khojki fonts.

**How well it works.** On 2 lines I kept aside until the very end, the program's best guesses had **about 4 in 10 characters wrong** (a 40.8% character error rate). It only marks a character as certain when it is at least 95% sure. No letter reaches that yet, so the text holds its best guesses, marked as guesses for a person to confirm.

## 1. Error Breakdown by Stage
To find out which step causes the errors, I gave the program the correct answer for one step at a time and counted what was left. Of 81 errors, **64 come from recognizing characters**, 19 from cutting lines into characters, and none from finding lines. The most common mistakes are small marks and look-alike letters, like MA and BA.

## 2. Failed Experiments
I started with the simplest way to recognize a character: compare its pixels with characters I already knew, and let the closest ones vote. I expected to replace it quickly with something smarter. I never did.

**First, I tried describing shapes the way a person would.** Instead of raw pixels, I counted each character's holes, stroke ends and crossings. It was right on the first guess only 27% of the time. Raw pixels were right 52% of the time.

**Next, I tried a cleaning method built for old, yellowed scans.** It cut 56 of 80 characters correctly. The simple method I already had cut 59.

**Then I turned to recent research.** Papers from 2026 on reading rare scripts recommended neural networks, including ones trained to treat font images and real print as the same thing. I built three versions, and all of them did worse than comparing pixels. The most promising one got 15 more of my 105 test characters wrong. The cause was the data, not the network: the fonts show every letter once, while the book uses some letters far more than others. Once I fixed that mix, it got only 3 more wrong. Across about 20 changes in total, the best gained 6 characters out of 105, and with a test that small, that could have been luck.

**The one thing that clearly worked wasn't a change to the program.** I ran the same simple version with a quarter, half, three quarters and all of my hand-checked characters. Accuracy rose every time, from 46% to 69%. That told me where the real problem was.

## 3. Encoding Decisions
Word separators use Khojki's own code, not a colon, and marks always follow their letter in the same order, so a word is always stored the same way. A character with no good guess is written as a placeholder (�), so a blank is never mistaken for a reading.

## 4. Bottleneck and How Many Labelled Lines
The program learns by comparison: it finds the known characters most similar to a new one. So it can only be as good as those known characters. I call each one a *labelled example*: a picture of one character cut from the book, with the correct answer attached by a person. Four things limit it, in order of impact:

1. **Too few real examples, spread thin.** My 150 are shared across dozens of letter-and-mark combinations, so most have one to three examples and some have none. Four times as many raised accuracy from 46% to 69%.
2. **The rest of the data has the wrong shape.** The 2,666 font images are 18 of every 19 examples, but printed strokes are about 40% thicker, and the fonts show every letter once while the book repeats common ones. Matching the book's letter mix took one model from 54% to 66%. More data only helps if it looks and counts like the book.
3. **The test is too small to show progress.** With 105 test characters, only differences of about 9 points are clearly real.
4. **Look-alike letters need a Khojki reader.** I don't read the script, and rechecking MA, BA, JA and TA changed 15 of my answers.

**How many lines it would take.** A rough projection from my results says about 14 labelled lines would put the right letter in the top three suggestions 90% of the time, and about 45 would reach 95%. Reading whole lines without cutting them into characters, the way tools like Kraken do, needs about 800.

## 5. Cost and Time per Page
The program takes 15 to 18 seconds a page and costs nothing to run: 45 pages would take about 12 minutes. Labelling took at most 44 seconds a character (153 minutes for 11 lines); the timer kept running while I did schoolwork, so the real time was less. At that pace, 800 lines would take at most about 190 hours.

## 6. Where an AI Tool Was Wrong
I used Claude, an AI assistant, to help write the code and suggest readings. Engineers who review AI work watch for three kinds of mistakes, and I ran into all three.

- **It sounded sure, and it was wrong.** Claude read one character as two letters, MA and DHA. It was one letter with a long vowel sign. I spent seven and a half minutes checking it against a chart before flagging it. When I later rechecked every look-alike letter, 15 of my answers changed.
- **The number looked perfect, but the result was broken.** The line finder scored 35 out of 35 lines, but a picture of its output showed it was cutting text off the edge of a page.
- **It reported things it hadn't checked.** The install steps it wrote had never been run: when I tried them, the install failed and pointed to the wrong folder.

**What I do now.** These follow Anthropic's advice for working with Claude Code, and each answers a mistake above.
- **Plan before code.** The AI writes down what it will build and how we'll know it's done, and I approve it first.
- **Give it a way to check itself.** Tests run before every save to the project history. They caught a rule that looked perfect on 14 cases and was right only 5 times out of 12 on new lines.
- **Verify, don't trust.** I recompute every number a second way and look at the actual output, not just the score.
- **Keep the judgement calls.** The AI suggests; I decide every character.
