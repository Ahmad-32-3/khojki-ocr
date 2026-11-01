"""Stage C against SPEC.md's acceptance criteria."""
import json, socket
from pathlib import Path

import cv2
import numpy as np
import pytest

from khojki import recognise as R
from khojki.bank import normalise, unit_mask
from khojki.glyphs import glyph_atoms
from khojki.labels import SEPARATOR

ROOT = Path(__file__).resolve().parents[1]
MA, RA = (0x11224,), (0x11226,)
IDENTITY = {"calib": {"x": [0.0, 1.0], "y": [0.0, 1.0]}, "tau": 0.5}
MODEL = {"letter": {"sep": IDENTITY, "glyph": IDENTITY}, "signs": {"sep": IDENTITY, "glyph": IDENTITY}, "description": "pixels"}


def synthetic_line():
    img = np.full((70, 300), 230, np.uint8)
    cv2.ellipse(img, (40, 40), (12, 16), 0, 0, 360, 20, 4)       # "MA"
    cv2.rectangle(img, (80, 24), (100, 56), 20, 4)                # "RA"
    cv2.circle(img, (130, 34), 3, 20, -1)                         # separator, lower dot 7 px right
    cv2.circle(img, (137, 46), 3, 20, -1)
    cv2.ellipse(img, (170, 40), (12, 16), 0, 0, 360, 20, 4)       # "MA" again
    return img


def synthetic_bank(gray, labels=(MA, RA, (SEPARATOR,), MA)):
    atoms = glyph_atoms(gray)
    assert [b[4] for b in atoms["boxes"]] == ["glyph", "glyph", "sep", "glyph"]
    ex = [normalise(unit_mask(atoms, [k]), atoms["tall"]) for k in range(len(atoms["boxes"]))]
    return dict(img=np.stack([e[0] for e in ex]), meta=np.stack([e[1] for e in ex]), label=list(labels),
                source=["real"] * len(ex), line=["syn"] * len(ex))


def check_output(out, model):
    """Every part is a valid recognition or suggestion. Text: one U+FFFD per red glyph (best guess under RED_BELOW);
    every other character is a recognised answer or, for an orange glyph, its best guess."""
    reds, allowed = 0, set()
    for u in out["units"]:
        for part in ("letter", "signs"):
            d = u[part]
            assert d["status"] in ("recognised", "suggestion")
            if d["status"] == "recognised":
                assert d["conf"] >= min(model[part][k]["tau"] for k in ("sep", "glyph"))
                allowed |= {chr(int(c[2:], 16)) for c in d["cps"]}
            else:
                assert d["options"]
                allowed |= {chr(int(c[2:], 16)) for c in d["options"][0]["cps"]}
        assert u["colour"] == R.colour(u["letter"])
        reds += u["colour"] == "red"
    assert out["text"].count(R.REPLACEMENT) == reds
    assert set(out["text"]) - {R.REPLACEMENT} <= allowed


def test_runs_offline(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", no_network)
    gray = synthetic_line()
    out = R.recognise_line(gray, synthetic_bank(gray), MODEL)
    check_output(out, MODEL)
    assert chr(MA[0]) in out["text"] and chr(SEPARATOR) in out["text"]


def test_deterministic():
    gray = synthetic_line()
    bank = synthetic_bank(gray)
    a = json.dumps(R.recognise_line(gray, bank, MODEL), ensure_ascii=False)
    b = json.dumps(R.recognise_line(gray, synthetic_bank(gray), MODEL), ensure_ascii=False)
    assert a == b


def test_no_fitted_model_means_no_recognitions():
    gray = synthetic_line()
    out = R.recognise_line(gray, synthetic_bank(gray), model={})
    assert all(u[p]["status"] == "suggestion" for u in out["units"] for p in ("letter", "signs"))
    assert set(out["text"]) == {R.REPLACEMENT}


def test_chart_only_support_is_never_recognised():
    """Criterion 7: a letter only chart renders back stays a suggestion, however confident."""
    opts = [(MA, 0.95, False), (RA, 0.01, True)]
    assert R.decide(opts, IDENTITY["calib"], 0.0)["status"] == "suggestion"
    assert R.decide([(MA, 0.95, True), (RA, 0.01, True)], IDENTITY["calib"], 0.0)["status"] == "recognised"


def test_close_call_is_a_suggestion():
    """The margin rule: a clear winner is needed even above tau."""
    assert R.decide([(MA, 0.90, True), (RA, 0.80, True)], IDENTITY["calib"], 0.0)["status"] == "suggestion"


def test_glyph_box_never_becomes_a_separator():
    """Log 70: a split-off AA upright matched a separator. Stage B's kind now constrains matching."""
    gray = synthetic_line()
    bank = synthetic_bank(gray)
    atoms = glyph_atoms(gray)
    img, meta = normalise(unit_mask(atoms, [2]), atoms["tall"])         # the separator's own image...
    share, _ = R.Index(bank, "pixels").votes(img, meta, kind="glyph")  # ...looked up as if it were a glyph box
    assert (SEPARATOR,) not in share


def test_folds_never_fit_on_the_held_out_line():
    """Criterion 5."""
    import eval_recognise as E
    lines = [{"file": f} for f in ("a", "b", "c")]
    bank = {"source": ["real", "real", "real", "chart"], "line": ["a", "b", "c", "font"]}
    for held, inner in E.folds(lines):
        assert held not in inner
        rows = E.bank_rows(bank, {held})
        assert all(bank["line"][i] != held for i in rows) and 3 in rows  # chart rows always kept


@pytest.mark.skipif(not (ROOT / "gt" / "lines" / "p09_l01.png").exists() or not (ROOT / "data" / "bank.npz").exists(),
                    reason="needs the local scans and data/bank.npz")
def test_schema_on_ground_truth_lines():
    """Criterion 2 on all 6 GT lines with the fitted model."""
    model = R.load_model()
    if model is None:
        pytest.skip("no data/model.json")
    for f in sorted((ROOT / "gt" / "lines").glob("p09_l*.png")):
        check_output(R.recognise_line(cv2.imread(str(f), cv2.IMREAD_GRAYSCALE), model=model), model)


def test_stale_model_is_refused():
    """Fix 5 (log 75): a model fitted on another bank must not run with its old thresholds."""
    from khojki.bank import fingerprint
    gray = synthetic_line()
    bank = synthetic_bank(gray)
    R.check_model(dict(MODEL, bank_fp=fingerprint(bank)), bank)            # matching: fine
    with pytest.raises(RuntimeError, match="Refit"):
        R.recognise_line(gray, bank, dict(MODEL, bank_fp="0" * 16))
    assert fingerprint(bank) == fingerprint(synthetic_bank(synthetic_line()))  # same content, same value


def test_unknown_join_is_described_by_its_pieces(monkeypatch):
    """A two-box unit with no clear whole reading also gets each box read on its own ("components")."""
    cands = {(0, 1): ({MA: 0.3, RA: 0.1}, {MA, RA}), (1, 1): ({RA: 0.3, MA: 0.1}, {MA, RA}),
             (0, 2): ({MA: 0.4, RA: 0.35}, {MA, RA})}
    monkeypatch.setattr(R, "candidates", lambda atoms, index: cands)
    out = R.recognise_atoms({"boxes": [None, None]}, None, MODEL)
    (u,) = out["units"]
    assert u["letter"]["status"] == "suggestion"
    assert [c["name"] for c in u["components"]] == ["MA", "RA"]
