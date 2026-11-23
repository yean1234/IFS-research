"""대안 경로(G12) 측정: Windows 미리보기 플레이어를 상주 프로세스로 띄우고 폴더 요청(PreviewQueue)으로 spec마다 PNG를 받는다.

  python -I queue_client.py <IFSPreview.exe> <요청 폴더> <출력 폴더> <spec.json ...> [--width 800 --height 600] [--cases <cases.json>]
  --cases: serve.py와 같은 덮어쓰기 사례 파일. 사례마다 overridesSeq의 마지막 덮어쓰기만 넣어 세 장을 받는다
           (덮어쓰기는 누적되지 않고 원래 spec 위에 새로 얹히므로 마지막 상태가 같다).
1) 플레이어를 -batchmode로 띄우고 ready.json이 생길 때까지의 시간(시작 지연)을 잰다.
2) spec마다 scene·black·white 세 장을 요청해(비교용) <출력>/<spec>_<배경>.png로 받는다.
3) spec마다 scene 한 장만 다시 요청해 요청 파일을 쓴 순간부터 응답 파일이 생길 때까지(왕복 지연)를 잰다.
4) quit 요청으로 끝낸다. 결과는 <출력>/latency.json.
참여자 데이터를 쓰지 않는다(합성·held-out spec 파일만). 네트워크를 쓰지 않는다.
"""
import argparse
import json
import os
import statistics
import subprocess
import time


def wait_for(path, timeout):
    t0 = time.perf_counter()
    while not os.path.exists(path):
        if time.perf_counter() - t0 > timeout:
            raise TimeoutError(path)
        time.sleep(0.002)
    return time.perf_counter() - t0


def request(qdir, name, body, timeout=60):
    done = os.path.join(qdir, name + ".done.json")
    if os.path.exists(done):
        os.remove(done)
    tmp = os.path.join(qdir, name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(body, f)
    t0 = time.perf_counter()
    os.replace(tmp, os.path.join(qdir, name + ".req.json"))
    wait_for(done, timeout)
    rtt = time.perf_counter() - t0
    for _ in range(100):  # 응답 파일은 임시 파일을 옮겨 만들므로 보통 바로 읽힌다
        try:
            with open(done, encoding="utf-8") as f:
                return rtt, json.load(f)
        except (PermissionError, json.JSONDecodeError):
            time.sleep(0.005)
    raise RuntimeError("응답을 읽지 못함: " + done)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("qdir")
    ap.add_argument("out")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--height", type=int, default=600)
    ap.add_argument("--log", default=None)
    ap.add_argument("--cases", default=None)
    a = ap.parse_args()
    qdir, out = os.path.abspath(a.qdir), os.path.abspath(a.out)
    os.makedirs(qdir, exist_ok=True)
    os.makedirs(out, exist_ok=True)
    for f in os.listdir(qdir):
        os.remove(os.path.join(qdir, f))
    log = a.log or os.path.join(out, "player.log")
    t0 = time.perf_counter()
    proc = subprocess.Popen([a.exe, "-batchmode", "-ifsPreviewQueue", qdir, "-logFile", log])
    result = {"exe": os.path.basename(a.exe), "width": a.width, "height": a.height}
    try:
        result["startupSeconds"] = round(wait_for(os.path.join(qdir, "ready.json"), 120), 3)
        # 1) 비교용 세 장(첫 요청은 셰이더·메시 준비가 섞인다)
        full = []
        for spec in a.specs:
            name = os.path.splitext(os.path.basename(spec))[0]
            rtt, d = request(qdir, "full_" + name, {"spec": os.path.abspath(spec), "width": a.width, "height": a.height,
                                                   "backgrounds": ["scene", "black", "white"], "out": os.path.join(out, name)})
            full.append({"spec": name, "rttMs": round(rtt * 1000, 2), "ok": d.get("ok"), "loadMs": d.get("loadMs"),
                         "renderPath": d.get("renderPath"), "error": d.get("error"),
                         "renderMs": {k: v["renderMs"] for k, v in (d.get("renders") or {}).items()}})
        # 1b) 덮어쓰기 사례(선택)
        if a.cases:
            with open(a.cases, encoding="utf-8") as f:
                cases = json.load(f)
            base = os.path.dirname(os.path.abspath(a.cases))
            result["cases"] = []
            for c in cases:
                body = {"spec": os.path.abspath(os.path.join(base, c["spec"])), "width": a.width, "height": a.height,
                        "backgrounds": ["scene", "black", "white"], "out": os.path.join(out, c["name"])}
                if c["overridesSeq"] and c["overridesSeq"][-1]:
                    body["overrides"] = c["overridesSeq"][-1]
                rtt, d = request(qdir, "case_" + c["name"], body)
                result["cases"].append({"case": c["name"], "rttMs": round(rtt * 1000, 2), "ok": d.get("ok"), "renderPath": d.get("renderPath"),
                                        "error": d.get("error")})
        # 2) 지연: scene 한 장만
        lat = []
        for spec in a.specs:
            name = os.path.splitext(os.path.basename(spec))[0]
            rtt, d = request(qdir, "lat_" + name, {"spec": os.path.abspath(spec), "width": a.width, "height": a.height,
                                                  "backgrounds": ["scene"], "out": os.path.join(qdir, "lat_" + name)})
            lat.append({"spec": name, "rttMs": round(rtt * 1000, 2), "ok": d.get("ok"), "loadMs": d.get("loadMs"),
                        "renderMs": (d.get("renders") or {}).get("scene", {}).get("renderMs"),
                        "writeMs": (d.get("renders") or {}).get("scene", {}).get("writeMs"), "playerTotalMs": d.get("totalMs")})
        r = [x["rttMs"] for x in lat if x["ok"]]
        result["full"] = full
        result["sceneOnly"] = lat
        if r:
            result["sceneOnlySummary"] = {"n": len(r), "meanMs": round(statistics.mean(r), 2), "medianMs": round(statistics.median(r), 2),
                                          "maxMs": round(max(r), 2), "minMs": round(min(r), 2)}
        with open(os.path.join(qdir, "quit.req.json"), "w") as f:
            f.write("{}")
        proc.wait(timeout=30)
        result["exitCode"] = proc.returncode
    finally:
        if proc.poll() is None:
            proc.kill()
        result["wallSeconds"] = round(time.perf_counter() - t0, 2)
        with open(os.path.join(out, "latency.json"), "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    print(json.dumps({k: result.get(k) for k in ("startupSeconds", "sceneOnlySummary", "exitCode", "wallSeconds")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
