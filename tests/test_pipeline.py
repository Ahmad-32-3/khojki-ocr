"""Stage D and the whole pipeline, on synthetic data (the scans aren't in the repo)."""
import socket
import xml.etree.ElementTree as ET

from khojki import validate
from khojki.pipeline import PAGE_NS, run_page, to_page_xml, to_txt
from test_lines import synthetic_page
from test_recognise import MODEL, synthetic_bank, synthetic_line


def test_validator_rules():
    validate.demo()


def test_whole_page_offline(monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("network used")
    monkeypatch.setattr(socket, "socket", no_network)
    result = run_page(synthetic_page(), "synthetic", bank=synthetic_bank(synthetic_line()), model=MODEL)
    assert len(result["lines"]) == 3
    assert to_txt(result).count("\n") == 3
    assert all(not l["problems"] for l in result["lines"])
    for l in result["lines"]:  # unit boxes are in page coordinates, inside their line
        for u in l["units"]:
            assert l["bbox"][0] <= u["bbox"][0] and u["bbox"][2] <= l["bbox"][2]


def test_page_xml_structure():
    result = run_page(synthetic_page(), "synthetic", bank=synthetic_bank(synthetic_line()), model={})
    root = ET.fromstring(to_page_xml(result))
    ns = {"p": PAGE_NS}
    glyphs = root.findall(".//p:Glyph", ns)
    assert len(root.findall(".//p:TextLine", ns)) == 3
    assert len(glyphs) == sum(len(l["units"]) for l in result["lines"])
    for g in glyphs:  # with no model everything is a suggestion: never in the answer slot, always as alternatives
        first, *alts = g.findall("p:TextEquiv", ns)
        assert first.get("index") == "1" and "suggestion" not in (first.get("comments") or "")
        assert set(first.find("p:Unicode", ns).text) == {"�"}
        assert alts and all(a.get("comments", "").startswith("suggestion") for a in alts)
