# Voice rules for the showcase site

Taken from how I rewrote the "How it works" and "Comparison" sections. All site text follows these.

## Rule zero: clarity first
- Plain, direct English that says exactly what happened. Clear beats clever.
- No catchphrases or set-up lines ("I didn't just guess at this", "The book leans on common ones", "get a fair test").
- Every metric says what it counts and out of what. Prefer a percentage ("68.6% right first guess, of 105 glyphs") over a bare count ("-8 glyphs").

## Voice
1. **First person, like I'm walking someone through it.** "I built", "I tested", "I wanted to answer". Use "we" only for steps the reader follows along with ("First, we need to figure out where the writing is").
2. **Conversational, with contractions.** "isn't", "doesn't", "that's", "here's".
3. **Calm, not flashy.** No hype words, no dramatic metaphors, no "revolutionary", "powerful", "seamless". Let the numbers carry the weight.
4. **Honest about weak results.** Say the number and own it: "That's still a substantial error rate, and I'm not trying to hide it."
5. **Lessons are personal.** "That taught me to...", "That was another reminder that...", "Sometimes the simpler approach really does work better."

## Structure
6. **Open a section with the goal or a plain question.** "I wanted to answer a simple question: ..." / "The goal is simple: ..."
7. **Short paragraphs: 1 to 3 sentences.** A single short line on its own for emphasis is fine ("And the results surprised me.").
8. **Signpost the turns.** "But here's the problem:", "The challenge?", "Why not use a neural network?", "I investigated why and found something unexpected."
9. **Close a section with one short, firm line.** "For this project, it wasn't." / "The bottleneck was the data, and now I have the experiments to prove it."
10. **Headings in Title Case, short.** "Finding the Lines", "What About Neural Networks?"

## Numbers and terms
11. **Bold the key number or the one sentence that matters.** One or two bolds per section, not more.
12. **Numbers always with context.** "six extra correct guesses out of 105", "59 of 80 glyph boxes", "all 35 lines across three pages".
13. **Explain every technical term right after it, in plain words.** "HOG, which measures stroke directions." In lists: **Term:** one-line plain explanation.
14. **No unexplained statistics jargon.** Say what the test does ("checks whether the difference could be chance"), not just its name.
15. **Spelling as I write it:** "recognize" and "specialized" (z), but "labelled" and "neighbouring" (as I write them).

## Don't
- No em-dash chains, no "not just X, but Y", no lists of three adjectives.
- No claims the experiments don't support. Every number must match PROCESS_LOG.md.
