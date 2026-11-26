"""스펙 2.3(G61 ①) 화면 검증용 spec 만들기 — 윤곽(form.roundness × form.aspect)과 발광(material.emission) 대표 조합.

  python docs\validation\scene-spec-2.3\make_specs.py <출력 폴더>

뼈대는 매퍼 v2(builder 2.5.0, ext_lexicon 켬)가 합성 문장 '불안하고 답답해요.'로 만든 2.3.0 문서
(unity/Assets/StreamingAssets/IFS/examples/v2.3/EX23-unstated.json, 세 슬롯 모두 null)이고, 슬롯 값과 근거만 바꿔 넣는다.
neutral 단계는 사전이 내지 않으므로(8.2절) 문장으로는 만들 수 없어 이렇게 만든다. 근거(_provenance)는 합성 표시(rule synthetic.*)다.
참여자 자료가 아니다(AGENTS.md 6).
  A_<둥긂>_<길쭉함>: 둥긂 null·R0(angular)…R4(rounded) × 길쭉함 E(elongated)·-(null)·F(flattened), 발광·색 없음(기본 회색)
  B_<발광>_<둥긂>_<색>: 발광 none·faint·glowing × 둥긂 R0·R4 × 색 blue(말함)·gray(기본색), 길쭉함 null
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
TEMPLATE = REPO / "unity" / "Assets" / "StreamingAssets" / "IFS" / "examples" / "v2.3" / "EX23-unstated.json"
ROUND = ["angular", "slightly_angular", "neutral", "slightly_rounded", "rounded"]
ASPECT = {"E": "elongated", "-": None, "F": "flattened"}
BLUE = {"h": 0.6, "s": 0.5, "l": 0.4}


def prov(trigger: str, path: str, value) -> list:
    return [{"source": "explicit_lexicon", "trigger": trigger, "charSpan": [0, len(trigger)],
             "rule": f"synthetic.validation>{path}:{value}"}]


def spec(sid: str, roundness=None, aspect=None, emission=None, color=None) -> dict:
    s = json.loads(TEMPLATE.read_text(encoding="utf-8"))
    s["meta"]["sessionId"] = sid
    s["form"]["roundness"], s["form"]["aspect"], s["material"]["emission"] = roundness, aspect, emission
    s["material"]["color"] = color
    p = s["_provenance"]
    for path, v, trig in (("form.roundness", roundness, "윤곽"), ("form.aspect", aspect, "길이"),
                          ("material.emission", emission, "빛"), ("material.color", color and "blue", "파란")):
        if v is not None:
            p[path] = prov(trig, path, v)
    return s


def main() -> None:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    items = []
    for ri, r in enumerate([None] + ROUND):
        for ak, a in ASPECT.items():
            rid = "Rn" if r is None else f"R{ri - 1}"
            items.append((f"A_{rid}_{ak}", dict(roundness=r, aspect=a)))
    for e in ("none", "faint", "glowing"):
        for ri in (0, 4):
            for cname, c in (("blue", BLUE), ("gray", None)):
                items.append((f"B_{e}_R{ri}_{cname}", dict(roundness=ROUND[ri], emission=e, color=c)))
    for sid, kw in items:
        (out / f"{sid}.json").write_text(json.dumps(spec("SYN-23-" + sid, **kw), ensure_ascii=False, indent=2) + "\n",
                                         encoding="utf-8", newline="\n")
        rows.append({"id": sid, "roundness": kw.get("roundness"), "aspect": kw.get("aspect"),
                     "emission": kw.get("emission"), "color": "blue(said)" if kw.get("color") else "default"})
    (out / "_index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(len(rows), "specs →", out)


if __name__ == "__main__":
    main()
