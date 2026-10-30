"""Build gt/review.html from Claude's lattices + segmenter boxes.

usage: python -X utf8 gt/build_review.py      (then open http://localhost:8765/review.html)
"""
import json
from pathlib import Path

from prep_gt import khojki_table
from segment import boxes_for

GT = Path(__file__).resolve().parent

lines = []
for f in sorted(GT.glob("claude_lattice_*.json")):
    lat = json.loads(f.read_text(encoding="utf-8"))
    lat["boxes"] = boxes_for(lat)
    lines.append(lat)

html = (GT / "review_template.html").read_text(encoding="utf-8")
html = html.replace("__LINES__", json.dumps(lines)).replace("__GLYPHS__", json.dumps(khojki_table()))
(GT / "review.html").write_text(html, encoding="utf-8")
print("review.html:", [(l["file"], len(l["spans"]), "spans", len(l["boxes"]), "boxes") for l in lines])
