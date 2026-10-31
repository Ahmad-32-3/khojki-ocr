"""Local server for the review page: serves gt/, saves progress and pictures to gt/review/.

usage: python -X utf8 gt/server.py [port=8765]      (localhost only)
  GET  /api/state            -> saved decisions for every line
  POST /api/save             {file, decisions}         -> gt/review/<line>.json
  POST /api/image            {file, span, dataUrl}     -> gt/review/img/<line>_s<span>_<n>.png, returns {path}
  POST /api/complete         {file}                    -> appends to gt/review/inbox.log (Claude watches this)
  POST /api/recheck          {answers}                 -> gt/review/recheck.json (gt/build_recheck.py page)
"""
import base64, binascii, datetime, json, re, sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GT = Path(__file__).resolve().parent
OUT = GT / "review"
IMG = OUT / "img"
MAX_BODY = 15 * 1024 * 1024
LINE = re.compile(r"^lines/(p\d{2}_l\d{2})\.png$")  # only our own crops, so names can't escape the folder


class Handler(SimpleHTTPRequestHandler):
    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/state":
            state = {}
            for f in OUT.glob("p*_l*.json"):
                d = json.loads(f.read_text(encoding="utf-8"))
                state[d["file"]] = d["decisions"]
            return self._json(200, state)
        super().do_GET()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        if not 0 < n <= MAX_BODY:
            return self._json(413, {"error": "body too large or empty"})
        try:
            req = json.loads(self.rfile.read(n))
            if self.path == "/api/recheck":
                if not isinstance(req.get("answers"), dict):
                    return self._json(400, {"error": "answers must be an object"})
                now = datetime.datetime.now().isoformat(timespec="seconds")
                (OUT / "recheck.json").write_text(json.dumps({"saved": now, "answers": req["answers"]}, indent=1, ensure_ascii=False), encoding="utf-8")
                with open(OUT / "inbox.log", "a", encoding="utf-8") as f:
                    f.write(f"{now} recheck answers={len(req['answers'])} -> review/recheck.json\n")
                return self._json(200, {"saved": now})
            m = LINE.match(req.get("file", ""))
            if not m:
                return self._json(400, {"error": "unknown line"})
            stem = m.group(1)
            now = datetime.datetime.now().isoformat(timespec="seconds")
            if self.path == "/api/save":
                if not isinstance(req.get("decisions"), dict):
                    return self._json(400, {"error": "decisions must be an object"})
                tmp = OUT / f"{stem}.json.tmp"  # write then rename, so a crash never leaves half a file
                tmp.write_text(json.dumps({"file": req["file"], "saved": now, "decisions": req["decisions"]}, indent=1, ensure_ascii=False), encoding="utf-8")
                tmp.replace(OUT / f"{stem}.json")
                return self._json(200, {"saved": now})
            if self.path == "/api/image":
                head, _, data = req.get("dataUrl", "").partition(",")
                if head not in ("data:image/png;base64", "data:image/jpeg;base64", "data:image/webp;base64"):
                    return self._json(400, {"error": "png, jpeg or webp only"})
                ext = head.split("/")[1].split(";")[0]
                span = int(req.get("span", 0))
                k = len(list(IMG.glob(f"{stem}_s{span:02d}_*"))) + 1
                p = IMG / f"{stem}_s{span:02d}_{k}.{ext}"
                p.write_bytes(base64.b64decode(data, validate=True))
                return self._json(200, {"path": p.relative_to(GT).as_posix()})
            if self.path == "/api/complete":
                with open(OUT / "inbox.log", "a", encoding="utf-8") as f:
                    how = "manual" if req.get("manual") else "complete"
                    f.write(f"{now} {how} {req['file']} reviewed={int(req.get('reviewed', 0))} -> review/{stem}.json\n")
                return self._json(200, {"sent": now})
            return self._json(404, {"error": "no such endpoint"})
        except (ValueError, binascii.Error) as e:
            return self._json(400, {"error": str(e)})


if __name__ == "__main__":
    IMG.mkdir(parents=True, exist_ok=True)
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    print(f"serving {GT} on http://127.0.0.1:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), partial(Handler, directory=str(GT))).serve_forever()
