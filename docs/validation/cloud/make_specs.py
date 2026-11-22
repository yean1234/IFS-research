# 구름 수정(D7) 검증용 합성 SceneSpec(v2.1) 2개를 만든다. 참여자 데이터가 아니다(합성 트리거·손으로 고른 합성 값).
# 실행: chatbot\.venv\Scripts\python.exe docs/validation/cloud/make_specs.py  (스키마 검사까지 한다)
# "구름" 문장(흰 구름, 잿빛 구름)을 mist로 그렸을 때 구름으로 읽히는지 보기 위한 것이다. 평서 명사 "구름"이 사전에서 mist로 가지 않는 문제(M03, G4)는
# 고치지 않았으므로 매퍼 출력이 아니라 form.type=mist를 손으로 넣었다. 색 값은 목업 v1 매퍼가 "하양"(M03)·"잿빛"(M01)에 낸 값과 같다.
import json
import pathlib
import sys

import jsonschema

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "render"))
from make_specs import SCHEMA, spec  # noqa: E402  (렌더 비교의 합성 spec 틀을 그대로 쓴다)

SPECS = {
    "C01_cloud_white": spec("C01", [("form.type", "mist", "구름"), ("material.color", {"h": 0.0, "s": 0.0, "l": 0.95}, "흰")]),
    "C02_cloud_gray": spec("C02", [("form.type", "mist", "구름"), ("material.color", {"h": 0.0, "s": 0.03, "l": 0.55}, "잿빛")]),
    # 카메라가 안개 안에 있을 때의 비용(화면 대부분이 안개): 가장 큰 크기, 가장 가까운 거리, 눈높이
    "C03_cloud_inside": spec("C03", [("form.type", "mist", "구름"), ("material.color", {"h": 0.0, "s": 0.03, "l": 0.55}, "잿빛"),
                                     ("layout.size", 1.0, "아주 큰"), ("layout.distance", 0.0, "바로 앞"), ("layout.verticalOffset", 1.0, "눈높이")]),
}

if __name__ == "__main__":
    out = HERE / "specs"
    out.mkdir(exist_ok=True)
    for name, doc in SPECS.items():
        doc["meta"]["participantId"] = "SYNCLOUD"
        doc["meta"]["pipeline"]["builder"] = "synthetic-cloud-check/1.0.0"
        jsonschema.validate(doc, SCHEMA)
        (out / f"{name}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("wrote", name)
