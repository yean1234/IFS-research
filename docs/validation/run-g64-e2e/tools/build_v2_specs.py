"""run-g64-e2e 이음매: bridge 설정(매핑 v1) 세션 기록의 확정 텍스트 → v4 설정의 매퍼 v2(SceneSpecBuilderV2) SceneSpec.

bridge.toml은 [mapping] mode = "v1"이라 세션 안에서는 v1 spec(2.1.0)만 만든다. v4 흐름(후보·조절·미리보기)이 쓰는 것은
v2 spec(2.2.0, form.base 포함)이므로, 같은 확정 텍스트를 v4 설정의 v2 매퍼에 넣는다. 매퍼 입력은 확정 텍스트뿐이라
(controller._write_scene) 면담 쪽 설정과 상관없이 같은 텍스트 → 같은 spec이다. 세션 안의 v1 spec도 <id>.v1.json으로 복사한다.
LLM을 부르지 않는다(Runtime은 offline·가드 없음으로 만들고 매퍼만 쓴다).

  cd chatbot
  .venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/build_v2_specs.py <세션 기록 폴더> <spec 출력 폴더>
"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "chatbot"))
from ifs_chatbot import candidates as cand  # noqa: E402
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.scene_builder import normalize_confirmed, write_spec  # noqa: E402
from ifs_chatbot.scene_spec import check_principles  # noqa: E402

import jsonschema  # noqa: E402

src, out = Path(sys.argv[1]), Path(sys.argv[2])
out.mkdir(parents=True, exist_ok=True)
rt = Runtime(load_config("v4").with_overrides(**{"llm.backend": "offline", "guard.model_backend": "none"}), persist_logs=False)
b2 = rt.scene_builders["v2"]
summary = {}
for f in sorted(src.glob("*__r*.json")):
    d = json.loads(f.read_text(encoding="utf-8"))
    sid = d["sessionId"].split("__")[0]
    text = d["confirmedText"]
    spec = b2.build(text, session_id=sid, participant_id=None, condition=d["elicitationCondition"])
    write_spec(spec, out / f"{sid}.v2.json")
    if d.get("sceneSpec", {}).get("path") and Path(d["sceneSpec"]["path"]).exists():
        shutil.copy(d["sceneSpec"]["path"], out / f"{sid}.v1.json")
    major = spec["meta"]["specVersion"].rsplit(".", 1)[0]
    schema = json.loads((REPO / f"shared/schemas/scene-spec.v{major}.json").read_text(encoding="utf-8"))
    errs = [e.message[:120] for e in jsonschema.validators.validator_for(schema)(schema).iter_errors(spec)]
    c = cand.generate(spec, sid)
    summary[sid] = {"specVersion": spec["meta"]["specVersion"], "builder": spec["meta"]["pipeline"]["builder"],
                    "principleProblems": check_principles(spec, normalize_confirmed(text)), "schemaErrors": errs,
                    "nCandidates": len(c.get("candidates", [])), "selectionStep": c.get("selectionStep"),
                    "candidateAxes": [a.get("dimension") or a.get("slot") for a in c.get("axes", [])]}
print(json.dumps(summary, ensure_ascii=False, indent=1))
