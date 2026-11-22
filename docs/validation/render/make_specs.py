# 렌더 경로 전후 비교용 합성 SceneSpec(v2.1)을 만든다. 참여자 데이터가 아니다(합성 대사·합성 값).
# 실행: chatbot\.venv\Scripts\python.exe docs/validation/render/make_specs.py  (스키마 검사까지 한다)
# 값은 손으로 고른 합성 값이다. 매퍼 출력이 아니며 매퍼를 부르지 않는다.
import hashlib
import json
import pathlib

import jsonschema

ROOT = pathlib.Path(__file__).resolve().parents[3]
OUT = pathlib.Path(__file__).resolve().parent / "specs"
SCHEMA = json.loads((ROOT / "shared/schemas/scene-spec.v2.1.json").read_text(encoding="utf-8"))


def spec(session_id, slots, shape_word=None):
    """slots: [(경로, 값, 합성 트리거)] — 트리거를 이어 붙인 합성 문장으로 charSpan을 만든다."""
    text, prov = "", {}
    doc = {
        "meta": {
            "specVersion": "2.1.0", "participantId": "SYNRENDER", "sessionId": session_id, "condition": "static",
            "sourceTextHash": "", "pipeline": {"builder": "synthetic-render-check/1.0.0", "analyzer": "kiwi", "lexicons": {}},
        },
        "form": {"type": None, "posture": None},
        "material": {"color": None, "brightness": None, "saturation": None, "roughness": None, "opacity": None, "erosion": None},
        "layout": {"size": None, "distance": None, "verticalOffset": None},
        "motion": {"type": None, "speed": None},
        "body": {"part": None, "layer": None},
        "_provenance": {}, "_unmatched": [], "_unmapped": [], "_negated": [], "_alternatives": [], "_inferred": {},
        "_context": [], "_parts": [], "_uncertain": [], "_measurements": [], "_direction": [], "_needsConfirmation": [],
        "_clauses": [],
    }

    def span(trigger):
        nonlocal text
        if text:
            text += " "
        start = len(text)
        text += trigger
        return [start, start + len(trigger)]

    for path, value, trigger in slots:
        group, key = path.split(".")
        doc[group][key] = value
        prov[path] = [{"source": "explicit_lexicon", "trigger": trigger, "charSpan": span(trigger),
                       "rule": "synthetic." + trigger + ">" + path}]
    if shape_word:
        shape, trigger = shape_word
        doc["_unmapped"].append({
            "lemma": trigger, "category": "shape", "value": {"shape": shape}, "reason": "no_scene_param",
            "_provenance": {"source": "explicit_lexicon", "trigger": trigger, "charSpan": span(trigger),
                            "rule": "shapeLexicon." + trigger},
        })
    doc["_provenance"] = prov
    doc["meta"]["sourceTextHash"] = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
    return doc


BLUE = {"h": 0.6, "s": 0.45, "l": 0.6}
SPECS = {
    # 안개 3개: 색·크기 같고 opacity만 다르다
    "R01_mist_op100": spec("R01", [("form.type", "mist", "안개"), ("material.color", BLUE, "파란"), ("material.opacity", 1.0, "짙은")]),
    "R02_mist_op060": spec("R02", [("form.type", "mist", "안개"), ("material.color", BLUE, "파란"), ("material.opacity", 0.6, "흐릿한")]),
    "R03_mist_op015": spec("R03", [("form.type", "mist", "안개"), ("material.color", BLUE, "파란"), ("material.opacity", 0.15, "투명한")]),
    # 조각 2개: 크기가 다르고 큰 쪽은 거칠기·침식·색이 있다
    "R04_frag_small": spec("R04", [("form.type", "fragments", "조각"), ("layout.size", 0.4, "작은")]),
    "R05_frag_large": spec("R05", [("form.type", "fragments", "조각"), ("layout.size", 0.7, "큰"),
                                   ("material.color", {"h": 0.02, "s": 0.6, "l": 0.45}, "붉은"),
                                   ("material.roughness", 0.8, "거친"), ("material.erosion", 0.3, "삭은")]),
    "R06_shell": spec("R06", [("form.type", "shell", "껍질")]),
    "R07_blob_default": spec("R07", [("form.type", "blob", "덩어리")]),
    "R08_blob_green_bright": spec("R08", [("form.type", "blob", "덩어리"), ("material.color", {"h": 0.33, "s": 0.5, "l": 0.5}, "초록"),
                                          ("material.brightness", 0.8, "밝은")]),
    "R09_form_null": spec("R09", [("material.color", {"h": 0.1, "s": 0.3, "l": 0.5}, "갈색")]),
    "R10_shape_round": spec("R10", [("material.brightness", 0.3, "어두운")], ("round", "동그란")),
    "R11_shape_square": spec("R11", [("form.type", "blob", "덩어리")], ("square", "네모난")),
    "R12_shape_flat": spec("R12", [("material.color", {"h": 0.75, "s": 0.4, "l": 0.5}, "보라")], ("flat", "납작한")),
    "R13_shape_pointed": spec("R13", [], ("pointed", "뾰족한")),
}

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for name, doc in SPECS.items():
        jsonschema.validate(doc, SCHEMA)
        (OUT / (name + ".json")).write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"{len(SPECS)}개 작성·스키마 통과 → {OUT}")
