"""Local demo server: the showcase site at /, the live demo at /demo/, and a small JSON API that runs the pipeline.

usage: python -X utf8 demo/server.py [port]        then open http://localhost:8000/
Stdlib only. Runs on this machine, because the scans are for this exercise only and must not go on a hosted page.

API
  GET  /api/samples              the sample pages (Figure 1, 2, ...)
  POST /api/run                  JSON {"sample": "fig1"}  -> pipeline result for that page
  POST /api/run?page=N           raw body = an uploaded PNG / JPEG / TIFF, or a PDF with ?page=N
  GET  /api/image/<id>.png       the page image a result refers to
  GET  /api/thumb/<sample>.jpg   a small colour preview of a sample page
"""
import json, sys, threading, time, uuid
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from khojki.bank import load  # noqa: E402
from khojki.labels import name  # noqa: E402
from khojki.pipeline import pdf_page, run_page  # noqa: E402
from khojki.recognise import load_model  # noqa: E402

PDF = ROOT / "khojki-scans" / "sample_khojki_script_vatiations.pdf"
SAMPLES = [  # (id, label, PDF page)
    ("fig1", "Figure 1", 9),
    ("fig2", "Figure 2", 10),
    ("fig3", "Figure 3", 11),
    ("fig4", "Figure 4", 18),
    ("fig5", "Figure 5", 23),
]
RED_BELOW = 0.30   # a suggestion whose best guess is under 30% is shown red: the program has no real idea
MAX_UPLOAD = 25 * 1024 * 1024
BANK, MODEL = load(), load_model()
IMAGES = {}        # result id -> PNG bytes (kept in memory only; this is a local demo)
THUMBS = {}        # sample id -> small colour JPEG of the page, so the reader can see each kind of page
LOCK = threading.Lock()  # one pipeline run at a time: the example bank's feature cache isn't thread-safe


def option(o):
    cps = [int(c[2:], 16) for c in o["cps"]]
    return {"name": name(tuple(cps)) if cps else "no mark", "text": "".join(map(chr, cps)), "conf": o["conf"]}


def describe(unit):
    """One glyph for the page: colour, the chosen reading or the guesses, each with a name and a percentage."""
    out = {"bbox": unit["bbox"]}
    for part in ("letter", "signs"):
        d = unit[part]
        if d["status"] == "recognised":
            out[part] = {"sure": True, "options": [option({"cps": d["cps"], "conf": d["conf"]})] + [option(o) for o in d.get("others", [])]}
        else:
            out[part] = {"sure": False, "options": [option(o) for o in d["options"]]}
    top = out["letter"]["options"][0]["conf"] if out["letter"]["options"] else 0.0
    out["colour"] = "green" if out["letter"]["sure"] else ("red" if top < RED_BELOW else "orange")
    return out


def run(gray, title):
    t0 = time.perf_counter()
    with LOCK:
        result = run_page(gray, title, BANK, MODEL)
    rid = uuid.uuid4().hex[:12]
    IMAGES[rid] = cv2.imencode(".png", gray)[1].tobytes()
    lines = [{"bbox": l["bbox"], "units": [describe(u) for u in l["units"]]} for l in result["lines"]]
    units = [u for l in lines for u in l["units"]]
    count = lambda c: sum(u["colour"] == c for u in units)
    return {"title": title, "image": f"/api/image/{rid}.png", "width": result["width"], "height": result["height"],
            "seconds": round(time.perf_counter() - t0, 1), "lines": lines,
            "counts": {"lines": len(lines), "green": count("green"), "orange": count("orange"), "red": count("red")}}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=str(ROOT), **k)

    def translate_path(self, path):
        # / is the showcase site; /demo/ is the demo. Nothing else in the project is served.
        p = urlparse(path).path
        base, rest = (ROOT / "demo", p[len("/demo/"):]) if p.startswith("/demo/") or p == "/demo" else (ROOT / "site", p.lstrip("/"))
        target = (base / (rest or "index.html")).resolve()
        return str(target) if target.is_relative_to(base) else str(base / "__missing__")  # no ../ escapes

    def send_json(self, obj, code=200):
        body = json.dumps(obj, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = urlparse(self.path).path
        if p == "/api/samples":
            return self.send_json([{"id": i, "label": l, "page": pg} for i, l, pg in SAMPLES])
        if p.startswith("/api/thumb/"):
            sid = p.rsplit("/", 1)[-1].removesuffix(".jpg")
            hit = [s for s in SAMPLES if s[0] == sid]
            if not hit or not PDF.is_file():
                return self.send_error(404)
            if sid not in THUMBS:
                import pymupdf
                THUMBS[sid] = pymupdf.open(PDF)[hit[0][2] - 1].get_pixmap(dpi=40).tobytes("jpeg")
            self.send_response(200)
            self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(THUMBS[sid])))
            self.end_headers()
            return self.wfile.write(THUMBS[sid])
        if p.startswith("/api/image/"):
            png = IMAGES.get(p.rsplit("/", 1)[-1].removesuffix(".png"))
            if png is None:
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(png)))
            self.end_headers()
            return self.wfile.write(png)
        return super().do_GET()

    def do_POST(self):
        u = urlparse(self.path)
        if u.path != "/api/run":
            return self.send_error(404)
        size = int(self.headers.get("Content-Length") or 0)
        if size > MAX_UPLOAD:
            return self.send_json({"error": "That file is over 25 MB."}, 413)
        body = self.rfile.read(size)
        try:
            if self.headers.get("Content-Type", "").startswith("application/json"):
                sid = json.loads(body or b"{}").get("sample")
                hit = [s for s in SAMPLES if s[0] == sid]
                if not hit:
                    return self.send_json({"error": "Unknown sample."}, 400)
                if not PDF.is_file():
                    return self.send_json({"error": "The sample PDF isn't in the khojki-scans folder."}, 500)
                _, label, page = hit[0]
                return self.send_json(run(pdf_page(PDF, page), label))
            gray = read_upload(body, parse_qs(u.query).get("page", [None])[0])
            if gray is None:
                return self.send_json({"error": "Couldn't read that file. Upload a PNG, JPEG or TIFF page, or a PDF "
                                                "with a page number."}, 400)
            return self.send_json(run(gray, "Your upload"))
        except Exception as ex:  # a bad upload must not take the server down
            return self.send_json({"error": f"The pipeline couldn't process this page ({type(ex).__name__})."}, 500)

    def log_message(self, fmt, *args):
        if "/api/" in str(args[0] if args else ""):
            sys.stderr.write("%s\n" % (fmt % args))


def read_upload(body, page):
    if body[:4] == b"%PDF":
        if not page or not page.isdigit():
            return None
        import pymupdf
        tmp = ROOT / "out" / f"upload_{uuid.uuid4().hex[:8]}.pdf"
        tmp.parent.mkdir(exist_ok=True)
        tmp.write_bytes(body)
        try:
            return pdf_page(tmp, int(page))
        finally:
            tmp.unlink(missing_ok=True)
    return cv2.imdecode(np.frombuffer(body, np.uint8), cv2.IMREAD_GRAYSCALE)


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000
    print(f"Khojki demo: http://localhost:{port}/   (site)   http://localhost:{port}/demo/   (live demo)")
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
