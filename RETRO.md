# Retro: Teaching a Computer to Read 1896 Khojki

**The task.** Khojki is a script used by the Khoja community of South Asia, mostly for religious texts. I was given scans of an 1896 printed book and asked to turn them into digital text, measure how accurate that text is, and explain what goes wrong.

**What I built.** A program that reads a page in three steps: it finds the lines, cuts each line into characters, and recognizes each character by comparing it with 150 characters I labelled by hand and 2,666 drawn from Khojki fonts.

**How well it works.** On 2 lines I kept aside until the very end, the program's best guesses had **about 4 in 10 characters wrong** (a 40.8% character error rate). It only marks a character as certain when it is at least 95% sure. No letter reaches that yet, so the text holds its best guesses, marked as guesses for a person to confirm.

## 1. Error Breakdown by Stage
To find out which step causes the errors, I gave the program the correct answer for one step at a time and counted what was left. Of 81 errors, **64 come from recognizing characters**, 19 from cutting lines into characters, and none from finding lines. The most common mistakes are small marks and look-alike letters, like MA and BA.

## 2. Failed Experiments
I started with the simplest way to recognize a character: compare its pixels with characters I already knew, and let the closest ones vote. I expected to replace it quickly with something smarter. I never did.

**First, I tried describing shapes the way a person would.** Instead of raw pixels, I counted each character's holes, stroke ends and crossings. It sounded smarter, but it was right on the first guess only 27% of the time. Raw pixels were right 52% of the time.

**Next, I tried a better way to clean the page.** Old scans have yellowed, uneven paper, and there's a method called Sauvola built for exactly that. It cut 56 of 80 characters correctly. The simple method I already had cut 59.

**Then I turned to recent research.** Papers from 2026 on reading rare scripts recommended neural networks, including ones trained to treat font images and real print as the same thing. I built three versions, and all of them did worse than comparing pixels. The most promising one got 15 more of my 105 test characters wrong. When I looked into why, the cause was the data, not the network: the fonts show every letter once, while the book uses some letters far more than others. Once I fixed that mix, it got only 3 more wrong. Better, but still not better than pixels.

In all, I tried about 20 changes to the program. The best one got 6 more characters right out of 105, and with a test that small, that could have been luck.

**The one thing that clearly worked wasn't a change to the program.** I ran the same simple version with a quarter, half, three quarters and all of my hand-checked characters. Accuracy rose every time, from 46% to 69%. That told me where the real problem was, and section 4 explains it.

## 3. Encoding Decisions
Digital text needs exact codes, so I set four rules. Word separators use Khojki's own code, not a colon. Marks always follow their letter in the same order, so a word is always stored the same way. Numbers use Gujarati digits, as the Unicode standard says. And a character with no good guess is written as a placeholder (�), so a blank is never mistaken for a reading.

## 4. Bottleneck and How Many Labelled Lines
The program learns by comparison: it looks at a new character and finds the most similar ones it already knows the answer to. So it can only be as good as those known characters. I call each one a *labelled example*: a picture of one character cut from the book, with the correct answer attached by a person. Four things limit it, in order of impact:

1. **Too few real examples, spread thin.** I have 150 from the book, shared across dozens of letter-and-mark combinations, so most have only one to three examples and some have none. Quadrupling them raised accuracy from 46% to 69%. No change to the program itself gained more than 6 points.
2. **The rest of the data has the wrong shape.** The 2,666 font images fill the gaps, but they make up 18 of every 19 examples and they don't match the book: printed strokes are about 40% thicker, and the fonts show every letter once while the book uses common letters far more often. When I made the fonts follow the book's letter mix, one model went from 54% to 66%. More data only helps if it looks and counts like the book.
3. **The test is too small to show progress.** I test on 105 characters, so only differences of about 9 points are clearly real. A 6-point gain could be luck.
4. **Look-alike letters need a Khojki reader.** I don't read the script, and rechecking MA, BA, JA and TA changed 15 of my answers.

**How many lines it would take.** At about 19 characters a line, a rough projection from my results says about 14 labelled lines would put the right letter in the top three suggestions 90% of the time, and about 45 lines would reach 95%. Reading whole lines without cutting them into characters, the way tools like Kraken do, needs about 800 labelled lines.

## 5. Cost and Time per Page
The program takes 15 to 18 seconds a page on a laptop and costs nothing to run: 45 pages would take about 12 minutes. Labelling is the slow part. The labelling tool timed me at 153 minutes for 11 lines, about 44 seconds a character. That's an upper bound: the timer kept running while I did schoolwork between characters, so the real time was less. Even at that pace, 800 lines would take at most about 190 hours.

## 6. Where an AI Tool Was Wrong
I used Claude, an AI assistant, to help write the code and suggest readings. Engineers who review AI work watch for three kinds of mistakes, and I ran into all three.

- **It sounded sure, and it was wrong.** Claude read one character as two letters, MA and DHA. It was one letter with a long vowel sign, and the program's own cutting step had it right. I spent seven and a half minutes checking it against a chart before flagging it. Its suggestions also kept leaning toward MA, and I sometimes went along with them. When I rechecked every look-alike letter, 15 of my answers changed.
- **The number looked perfect, but the result was broken.** One version of the line finder scored 35 out of 35 lines, but a picture of its output showed it was cutting text off the edge of a page. In another case, a 96% accuracy figure hid that characters, the hard part, were only at 86%.
- **It reported things it hadn't checked.** A draft said 109 of 122 characters were labelled; the files said 98 of 111. It stated a run time of 12 seconds; when I measured, it was 15 to 18. The install steps it wrote had never been run: when I tried them, the install failed and the instructions pointed to the wrong folder.

**What I do now.** These habits follow Anthropic's own advice for working with Claude Code, and each one answers a mistake above.
- **Plan before code.** For anything that could be built more than one way, the AI writes down what will be built and how we'll know it's done, and I approve it first. Jumping straight to code solves the wrong problem.
- **Give it a way to check itself.** Tests, plus a check that runs before every save to the project history: it blocks scans, runs the tests, and scores the real pages. It caught a rule of mine that looked perfect on 14 cases and was right 5 times out of 12 on new lines.
- **Check every number a second way.** A count is recomputed from the raw files, not copied from the code that produced it.
- **Look at the output, not just the score.** I draw the boxes on the page and look.
- **Keep the judgement calls.** The AI suggests; I decide every character, and its questions come to me as pictures.
- **Work in small, recorded steps.** One piece at a time, each decision written in a project log (94 entries), so mistakes are easy to find and undo.
- **Write the rules down.** Repeated corrections go into files the AI reads every session, so it doesn't make the same mistake twice.
