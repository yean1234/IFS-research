"""WebGL 미리보기 빌드를 로컬(127.0.0.1)에서 내보내고, 비교 드라이버(driver.html)의 캡처를 받아 저장한다(D4).

⚠ 2026-11-23 기준 미실행: 이 PC의 Unity 6000.0.85f2에 WebGL 모듈이 없어 빌드를 만들지 못했다(README 참조).
   모듈을 설치하고 빌드한 뒤 이 순서로 돌린다.

  python -I serve.py <빌드 폴더> <출력 폴더> <spec.json ...> [--port 8765]
  → 브라우저(또는 헤드리스 Chrome)로 http://127.0.0.1:<port>/harness/driver.html 을 연다.
경로:
  /                 빌드 폴더(index.html, Build/*). 압축을 끈 빌드라 Content-Encoding 헤더가 필요 없다. .wasm만 application/wasm.
  /harness/...      이 tools 폴더(driver.html)
  /harness/specs.json  명령줄로 받은 spec 목록 [{name, url}], /harness/spec/<i> = i번째 spec 본문
  POST /save?name=<파일 이름>   본문 = PNG 바이트 → <출력>/<이름>
  POST /log         본문 = JSON 한 줄 → <출력>/console.jsonl
  POST /done        본문 = JSON(시간·오류) → <출력>/driver.json, 그리고 서버 종료
외부로 나가는 요청이 없다(127.0.0.1에만 묶음). 참여자 데이터를 다루지 않는다.
"""
import argparse
import json
import mimetypes
import os
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
mimetypes.add_type("application/wasm", ".wasm")
mimetypes.add_type("application/javascript", ".js")


def make_handler(build_dir, out_dir, specs, server_ref):
    class H(SimpleHTTPRequestHandler):
        def translate_path(self, path):
            p = urlparse(path).path
            if p.startswith("/harness/"):
                return os.path.join(HERE, os.path.normpath(p[len("/harness/"):]).lstrip("\\/"))
            return os.path.join(build_dir, os.path.normpath(p.lstrip("/")).lstrip("\\/"))

        def end_headers(self):
            self.send_header("Cache-Control", "no-store")
            super().end_headers()

        def do_GET(self):
            p = urlparse(self.path).path
            if p == "/harness/specs.json":
                return self._json([{"name": os.path.splitext(os.path.basename(s))[0], "url": f"/harness/spec/{i}"} for i, s in enumerate(specs)])
            if p.startswith("/harness/spec/"):
                i = int(p.rsplit("/", 1)[1])
                with open(specs[i], "rb") as f:
                    body = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            return super().do_GET()

        def do_POST(self):
            u = urlparse(self.path)
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            if u.path == "/save":
                name = os.path.basename(parse_qs(u.query)["name"][0])
                with open(os.path.join(out_dir, name), "wb") as f:
                    f.write(body)
            elif u.path == "/log":
                with open(os.path.join(out_dir, "console.jsonl"), "ab") as f:
                    f.write(body + b"\n")
            elif u.path == "/done":
                with open(os.path.join(out_dir, "driver.json"), "wb") as f:
                    f.write(body)
                threading.Thread(target=server_ref[0].shutdown, daemon=True).start()
            else:
                self.send_error(404)
                return
            self._json({"ok": True})

        def _json(self, obj):
            b = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def log_message(self, fmt, *args):
            pass

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("out_dir")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    os.makedirs(a.out_dir, exist_ok=True)
    ref = [None]
    srv = ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(os.path.abspath(a.build_dir), os.path.abspath(a.out_dir),
                                                                   [os.path.abspath(s) for s in a.specs], ref))
    ref[0] = srv
    print(f"http://127.0.0.1:{a.port}/harness/driver.html", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
