"""run-g64-e2e gen3d 절: v4-gen3d 설정으로 세션마다 형태 후보(절차 + 생성)를 만들고 기본 후보 판정을 기록한다.
선택 흐름(selection.SelectionFlow.start)과 같은 순서로 부른다: candidates.generate → FormAssetStore.lookup_for_spec
→ judge_default(auto, G62-i) → add_generated. 미리보기 모드 none 규칙은 건너뛴다(그림은 Windows 미리보기 플레이어로 따로 찍음).
그다음 (--render) 같은 플레이어(PreviewQueue)로 0번 절차 후보와 생성 후보 각각을 그린다(색·크기 등은 spec 값, 생성 메시는
가장 긴 변 1.0 정규화 GLB). 저장소 코드는 바꾸지 않는다. LLM을 부르지 않는다.

  cd chatbot
  .venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/gen3d_candidates.py [--render <미리보기 플레이어 exe> --queue <임시 폴더>]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "chatbot"))
from ifs_chatbot import candidates as cand  # noqa: E402
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.form_assets import add_generated  # noqa: E402
from ifs_chatbot.scene_builder import normalize_confirmed  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--render", default="")
ap.add_argument("--queue", default="")
ap.add_argument("--size", default="640x480")
a = ap.parse_args()

rt = Runtime(load_config("v4-gen3d").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none"}),
             persist_logs=False)
store = rt.form_assets
table = cand.load_table()
out_dir = HERE / "gen3d"
img_dir = HERE / "images" / "gen3d"
img_dir.mkdir(parents=True, exist_ok=True)
renderer = None
if a.render:
    from ifs_chatbot.preview import UnityQueueRenderer
    w, h = (int(x) for x in a.size.split("x"))
    renderer = UnityQueueRenderer([a.render], Path(a.queue), width=w, height=h, start_timeout_s=120, request_timeout_s=60)

summary = {"storeInfo": store.info(), "sessions": {}}
for f in sorted((HERE / "sessions" / "live").glob("g64_*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    sid = d["sessionId"].split("__")[0]
    spec = json.loads((HERE / "specs" / f"{sid}.v2.json").read_text(encoding="utf-8"))
    norm = normalize_confirmed(d["confirmedText"])
    c = cand.generate(spec, sid, table)
    lookup = store.lookup_for_spec(spec)
    basis = store.judge_default(lookup, spec, norm)
    full = add_generated(c, lookup, sid, store.max_candidates, store.default_form_source, basis)
    g = full["generation"]
    rec = {"lookupKey": g["lookupKey"], "offered": g["offered"],
           "rejected": [{k: r.get(k) for k in ("assetId", "status", "reason", "detail")} for r in g["rejected"]],
           "defaultFormSource": g["defaultFormSource"], "defaultCandidateId": g["defaultCandidateId"],
           "defaultFormRule": g["defaultFormRule"], "defaultFormBasis": g["defaultFormBasis"],
           "nCandidates": len(full["candidates"]), "displayOrder": full.get("displayOrder"), "renders": {}}
    if renderer is not None:
        spec_json = json.dumps(spec, ensure_ascii=False)
        png = renderer.render(spec_json, {})
        (img_dir / f"{sid}.proc.png").write_bytes(png)
        rec["renders"]["procedural0"] = f"images/gen3d/{sid}.proc.png"
        for k, asset in enumerate(lookup["offered"]):
            png = renderer.render(spec_json, {}, {"assetId": asset["assetId"], "glbPath": asset["_glbPath"],
                                                  "glbSha256": asset["glbSha256"]})
            (img_dir / f"{sid}.gen{k}.png").write_bytes(png)
            rec["renders"][f"generated{k}"] = f"images/gen3d/{sid}.gen{k}.png"
    summary["sessions"][sid] = rec
    print(sid, rec["defaultFormRule"], rec["defaultFormSource"], [o["assetId"] for o in rec["offered"]],
          [(r["assetId"], r["reason"]) for r in rec["rejected"]])
if renderer is not None:
    summary["renderer"] = {k: v for k, v in renderer.info().items() if k not in ("queueDir", "pid")}
    renderer.close()
s = json.dumps(summary, ensure_ascii=False, indent=1)
for base, tag in ((str(REPO.parent), "<repo>/.."),):
    s = s.replace(base.replace("\\", "\\\\"), tag).replace(base.replace("\\", "/"), tag)
(out_dir / "candidates.json").write_text(s + "\n", encoding="utf-8")
