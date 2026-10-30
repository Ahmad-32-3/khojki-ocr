import json
from pathlib import Path

import check_lattice

GT = Path(__file__).resolve().parents[1] / "gt"


def test_demo_cases():
    check_lattice.demo()


def test_saved_lattices_are_valid():
    # box coverage needs the line crops, which aren't in the repo; check scores and code points only
    for f in sorted(GT.glob("claude_lattice_l*.json")):
        lat = json.loads(f.read_text(encoding="utf-8"))
        n = 1 + max(b for s in lat["spans"] for b in s["boxes"])
        errors, _ = check_lattice.check(lat, [[0, 0, 0, 0, "glyph"]] * n)
        assert not errors, (f.name, errors)
