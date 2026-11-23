"""기본 형상(D6) 검증용 spec 만들기 — 합성 문장 → 매퍼 v2 → SceneSpec JSON. 모든 문장은 연구자가 만든 합성 대사다(AGENTS.md 6).

  chatbot\\.venv\\Scripts\\python.exe docs\\validation\\base-forms\\make_specs.py shapes   <출력 폴더>
  chatbot\\.venv\\Scripts\\python.exe docs\\validation\\base-forms\\make_specs.py mock     <출력 폴더> [--chatbot <다른 작업 폴더의 chatbot>]

shapes: 형상별 합성 문장(SHAPES)을 v2로 만들어 <id>.json으로 쓴다(사전에 아직 없는 형상의 문장은 form.base가 null로 나온다).
mock:   목업 36개 가운데 기본 형상과 관련된 항목(MOCK_IDS)의 확정 텍스트를 코퍼스 재생(eval.corpus_run, 오프라인)으로 얻어
        v2로 만든다. --chatbot으로 D6 전 커밋의 작업 폴더(git worktree)를 주면 그 코드(builder 2.1.0)로 '전' spec을 만든다.
held-out 코퍼스는 쓰지 않는다(dev·목업만, decisions G24).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

SHAPES = {
    # 담는 것
    "C1": "가슴 앞에 그릇이 있어요.",
    "C2": "배 안에 유리병이 있어요.",
    "C3": "까만 네모난 상자예요.",
    "C4": "가슴 앞에 작은 화분이 있어요. 초록색이에요.",
    "C5": "컵 같은 게 있어요. 반쯤 투명해요.",
    # 선·끈
    "L1": "실이 한 가닥 있어요.",
    "L2": "엉킨 실타래가 있어요.",
    "L3": "매듭이요. 단단하게 묶여 있어요.",
    "L4": "굵은 밧줄이 있어요. 갈색이에요.",
    "L5": "가느다란 검은 실이 엉켜 있어요.",
    # 얇은 판
    "S1": "종이 한 장이 있어요.",
    "S2": "얇은 천이 있어요. 보라색이에요.",
    "S3": "막이요. 얇은 막.",
    "S4": "보자기 같은 게 있어요. 반투명해요.",
    # 불꽃
    "F1": "불꽃이 있어요.",
    "F2": "촛불 같은 게 있어요. 작아요.",
    "F3": "빨간 불꽃이 있어요. 밝아요.",
    # 물방울
    "D1": "물방울이 있어요.",
    "D2": "눈물 같은 게 맺혀 있어요. 파란색이에요.",
    "D3": "커다란 물방울이 있어요. 투명해요.",
}

# 목업 가운데 기본 형상과 닿는 항목(실·천·종이·상자·물방울·불꽃) + 그리면 안 되는 것(웅덩이·액체·빛·사람)
MOCK_IDS = ["M06", "M09", "M15", "M18", "M19", "M20", "M21", "M22", "M23", "M24", "M25", "M26", "M27", "M30"]


def write(out: Path, name: str, spec: dict, dumps) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{name}.json").write_text(dumps(spec), encoding="utf-8", newline="\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("what", choices=["shapes", "mock"])
    ap.add_argument("out")
    ap.add_argument("--chatbot", default=str(REPO / "chatbot"))
    a = ap.parse_args()
    sys.path.insert(0, a.chatbot)
    from ifs_chatbot.korean import Analyzer
    from ifs_chatbot.scene_builder import dumps
    from ifs_chatbot.scene_builder_v2 import SceneSpecBuilderV2
    out = Path(a.out)
    v2 = SceneSpecBuilderV2(Analyzer())
    rows = []
    if a.what == "shapes":
        for k, text in SHAPES.items():
            spec = v2.build(text, session_id=f"SYN-BASE-{k}")
            write(out, k, spec, dumps)
            rows.append({"id": k, "text": text, "base": (spec["form"] or {}).get("base"),
                         "variant": (spec["form"] or {}).get("baseVariant"), "formType": spec["form"]["type"]})
    else:
        from ifs_chatbot.eval.corpus_run import run_corpus
        corpus = json.loads((REPO / "docs/validation/mock-forms/mock_corpus.json").read_text(encoding="utf-8"))
        corpus["items"] = [it for it in corpus["items"] if it["id"] in MOCK_IDS]
        res = run_corpus(corpus, mapper="v0")         # 확정 텍스트만 쓴다(매퍼와 무관하게 같은 텍스트)
        for it in res["items"]:
            spec = v2.build(it["confirmedText"], session_id=it["id"])
            write(out, it["id"], spec, dumps)
            rows.append({"id": it["id"], "builder": spec["meta"]["pipeline"]["builder"],
                         "base": (spec["form"] or {}).get("base"), "variant": (spec["form"] or {}).get("baseVariant"),
                         "formType": spec["form"]["type"],
                         "excluded": [u["lemma"] for u in spec["_unmapped"] if u["reason"] == "excluded_shape"]})
    (out / "_index.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    for r in rows:
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    main()
