"""테스트용 가짜 Unity 미리보기 플레이어. PreviewQueue(unity/Assets/IFS/Runtime/Preview/PreviewQueue.cs)와 같은 폴더 규약만 흉내 낸다.
  python fake_preview_player.py -batchmode -ifsPreviewQueue <폴더> -logFile <파일>
환경변수 FAKE_PLAYER_MODE: ok(기본) | die_on_request(요청을 받으면 응답 없이 종료) | never_ready(ready.json을 쓰지 않음) | error(ok:false 응답)
PNG에는 받은 덮어쓰기를 tEXt로 넣어, 덮어쓰기가 다르면 바이트가 달라지게 한다."""
import json
import os
import struct
import sys
import time
import zlib


def png(text: str) -> bytes:
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"tEXt", b"overrides\x00" + text.encode("utf-8")) + chunk(b"IDAT", zlib.compress(b"\x00\x80\x80\x80"))
            + chunk(b"IEND", b""))


def main():
    args = sys.argv[1:]
    q = args[args.index("-ifsPreviewQueue") + 1]
    mode = os.environ.get("FAKE_PLAYER_MODE", "ok")
    os.makedirs(q, exist_ok=True)
    if mode == "never_ready":
        time.sleep(30)
        return
    with open(os.path.join(q, "ready.json"), "w") as f:
        json.dump({"pid": os.getpid()}, f)
    served = 0
    t_end = time.time() + 60
    while time.time() < t_end:
        reqs = sorted(n for n in os.listdir(q) if n.endswith(".req.json"))
        for n in reqs:
            name = n[: -len(".req.json")]
            path = os.path.join(q, n)
            if name == "quit":
                os.remove(path)
                return
            try:
                with open(path, encoding="utf-8") as f:
                    body = json.load(f)
            except (OSError, ValueError):
                continue
            os.remove(path)
            if mode == "die_on_request":
                return
            done = {"request": name}
            if mode == "error":
                done.update(ok=False, error="ArgumentException: 가짜 오류")
            else:
                json.loads(body["specJson"])
                out = (body.get("out") or os.path.join(q, name)) + "_scene.png"
                with open(out, "wb") as f:
                    f.write(png(json.dumps(body.get("overrides") or {}, sort_keys=True)))
                done.update(ok=True, renders={"scene": {"png": out}})
            tmp = os.path.join(q, name + ".done.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(done, f)
            os.replace(tmp, os.path.join(q, name + ".done.json"))
            served += 1
        time.sleep(0.005)


if __name__ == "__main__":
    main()
