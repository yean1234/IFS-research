"""G82 첫 단계 오프라인 평가: [맞는 게 없어요] 뒤 LLM 형태 이름(chatbot/ifs_chatbot/llm_shape.py)을 실제 로컬 Ollama 면담 모델로 돌린다.
합성 대사만 쓴다(참여자 자료 아님). 실험 경로(selection.py·none_gen.py)에는 잇지 않았고, 이 스크립트가 llm_shape.run을 직접 부른다.

  - Runtime(experiment 설정 + [gen3d] on_none_llm_shape = true, 가드 모델 끔·미리보기 끔·G77 끔·조건 고정 끔) + static 세션
    + simulate.drive로 확정 텍스트를 넣는다(매퍼 v2 spec은 세션이 만든 그대로).
  - 같은 문장 전체를 두 번 돌린다(회차마다 세션 캐시를 비움). 원시 출력·채택값이 같은지 본다.
  - 기대값(CASES)은 결과를 보기 전에 적었다. enOk = 뜻이 맞는다고 미리 정한 영어 이름. 그 밖의 이름은 judgements.json에
    사람이 결과를 본 뒤 판정과 근거 한 마디를 적고, 사후 판정이라고 표시한다.
결과: 이 폴더의 results.json(로컬 절대 경로 없음). 서버를 새로 띄우지 않는다. 모델을 내리지 않는다(떠 있는 8000번 서버가 같은 모델을 씀).

실행(저장소 chatbot 폴더에서): .venv\\Scripts\\python ..\\docs\\validation\\run-g82-llm-shape-offline\\run_g82.py
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "chatbot"))

import httpx  # noqa: E402

from ifs_chatbot import llm_fill as lf  # noqa: E402
from ifs_chatbot import llm_shape as ls  # noqa: E402
from ifs_chatbot.config import load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402

# 갈래: P = 사전 밖 형태(채워야 함), N = 형태 없음, F = 부정·과거·타인·가정, B = 금지 범주(사람·동물·안개·불꽃),
#       W = 첫 질문 걱정 이야기 속 사물(형태로 잡으면 안 됨), R = 규칙이 형태를 잡는 대조(LLM을 부르지 않아야 함, 기준 밖)
# expect: fill = 채택돼야 함 · none = 채택되면 오통과. ko = 인용에 들어 있어야 할 한국어 형태 낱말. enOk = 미리 정한 뜻 맞는 영어 이름
CASES = [
    ("P01", "P", "조약돌이 하나 있어요.", "fill", "조약돌", ["pebble", "stone", "small stone", "pebble stone"]),
    ("P02", "P", "판때기예요. 겨자색이고 반지르르해요.", "fill", "판때기", ["board", "plank", "slab", "panel", "wooden board"]),
    ("P03", "P", "돌덩이 같은 게 있어요.", "fill", "돌덩이", ["rock", "stone", "boulder", "lump", "stone lump", "rock lump", "chunk"]),
    ("P04", "P", "유리구슬 같은 게 가슴 앞에 있어요.", "fill", "유리구슬", ["marble", "bead", "glass bead", "glass marble", "orb", "sphere"]),
    ("P05", "P", "나무상자예요.", "fill", "나무상자", ["box", "crate", "wooden box", "chest", "wood box"]),
    ("P06", "P", "털실타래 같은 게 뭉쳐 있어요.", "fill", "털실타래", ["yarn ball", "ball of yarn", "yarn", "skein", "wool ball", "yarn skein"]),
    ("P07", "P", "자갈이에요. 회색이고 거칠어요.", "fill", "자갈", ["gravel", "pebble", "stone", "pebbles"]),
    ("P08", "P", "가슴 한가운데에 벽돌 같은 게 박혀 있는데 꽤 단단하고 어두운 색이에요.", "fill", "벽돌", ["brick"]),
    ("P09", "P", "널빤지 같은 게 등에 붙어 있어요.", "fill", "널빤지", ["plank", "board", "wooden board", "slab"]),
    ("P10", "P", "쇳덩이예요. 차갑고 무거워요.", "fill", "쇳덩이", ["iron lump", "lump", "ingot", "chunk", "iron block", "metal lump", "block"]),
    ("P11", "P", "베개처럼 생겼어요.", "fill", "베개", ["pillow", "cushion"]),
    ("P12", "P", "찌그러진 깡통 같은 게 굴러다녀요.", "fill", "깡통", ["can", "tin can", "tin"]),
    ("P13", "P", "단추 같은 게 있어요. 동그래요.", "fill", "단추", ["button"]),
    ("P14", "P", "동전이 하나 놓여 있는 것 같아요.", "fill", "동전", ["coin"]),
    ("P15", "P", "솔방울이에요.", "fill", "솔방울", ["pine cone", "pinecone", "cone"]),
    ("P16", "P", "눈덩이 같은 게 점점 커져요.", "fill", "눈덩이", ["snowball", "snow ball", "snow lump"]),
    ("P17", "P", "방석 같은 거예요. 납작하고 푹신해요.", "fill", "방석", ["cushion", "floor cushion", "seat cushion", "mat"]),
    ("P18", "P", "양동이예요. 안이 비어 있어요.", "fill", "양동이", ["bucket", "pail"]),
    ("P19", "P", "발표 자료 준비가 걱정이에요.\n가슴에 돌덩이 같은 게 있어요.", "fill", "돌덩이",
     ["rock", "stone", "boulder", "lump", "stone lump", "rock lump", "chunk"]),
    ("R01", "R", "예전엔 공이었는데 지금은 조약돌 같아요.", "rule", None, []),
    ("N01", "N", "쑥색이고 차가워요.", "none", None, []),
    ("N02", "N", "그냥 답답하고 무거운 느낌이에요.", "none", None, []),
    ("N03", "N", "잘 모르겠어요.", "none", None, []),
    ("N04", "N", "뭔가 있는데 뭔지 모르겠어요.", "none", None, []),
    ("N05", "N", "어둡고 흐릿해요. 조금씩 흔들려요.", "none", None, []),
    ("N06", "N", "속이 울렁거리고 따끔따끔해요.", "none", None, []),
    ("F01", "F", "조약돌은 아니에요.", "none", None, []),
    ("F02", "F", "판때기 같은 건 없어요.", "none", None, []),
    ("F03", "F", "예전에는 돌덩이였어요.", "none", None, []),
    ("F04", "F", "처음엔 벽돌 같았어요.", "none", None, []),
    ("F05", "F", "친구가 조약돌 같대요.", "none", None, []),
    ("F06", "F", "다들 그게 판때기라고 했어요.", "none", None, []),
    ("F07", "F", "벽돌이면 좋겠어요.", "none", None, []),
    ("F08", "F", "아마 자갈일 거예요.", "none", None, []),
    ("B01", "B", "참새 같은 게 앉아 있어요.", "none", None, []),
    ("B02", "B", "다람쥐 같은 게 웅크리고 있어요.", "none", None, []),
    ("B03", "B", "허수아비 같은 게 서 있어요.", "none", None, []),
    ("B04", "B", "꼬마 같은 게 웅크리고 있어요.", "none", None, []),
    ("B05", "B", "물안개가 자욱하게 껴 있어요.", "none", None, []),
    ("B06", "B", "횃불 같은 게 타오르고 있어요.", "none", None, []),
    ("B07", "B", "해골 같은 게 보여요.", "none", None, []),
    ("W01", "W", "회사 보고서 마감 때문에 걱정이에요.\n가슴이 답답해요.\n어둡고 무거워요.", "none", None, []),
    ("W02", "W", "휴대폰 알림이 계속 와서 신경 쓰여요.\n배 쪽이 묵직해요.\n쑥색이에요.", "none", None, []),
    ("W03", "W", "시험 공부하느라 책상 앞에 오래 앉아 있어요.\n어깨가 뻐근해요.\n흐릿한 회색이에요.", "none", None, []),
    ("W04", "W", "통장 잔고가 줄어서 불안해요.\n목이 꽉 조이는 느낌이에요.", "none", None, []),
]
REPLIES = {"replies": ["뭔가 있어요"], "defaultReply": "없어요"}


def nvsmi() -> str | None:
    try:
        return subprocess.run(["nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader"],
                              capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:  # noqa: BLE001
        return None


def ollama(host: str, path: str):
    try:
        return httpx.get(f"{host}{path}", timeout=10).json()
    except Exception:  # noqa: BLE001
        return None


def slim(rec: dict) -> dict:
    keys = ("status", "skipReason", "error", "called", "candidate", "cached", "ruleRoute", "rawText", "rawItem", "item",
            "rejectReasons", "adopted", "shapePromptText", "llmSeconds", "seconds", "inputTextSha256", "validatorTextSha256",
            "userSha256", "cacheKey")
    return {k: rec.get(k) for k in keys}


def outcome(rec: dict) -> str:
    """기록 → 갈래: adopted · rejected(LLM 후보를 검증기가 버림) · null(LLM이 없다고 함) · skipped:<사유> · error:<status>"""
    st = rec.get("status")
    if st == "ok":
        return "adopted"
    if st == "rejected":
        return "rejected"
    if st == "null":
        return "null"
    if st == "skipped":
        return f"skipped:{rec.get('skipReason')}"
    return f"error:{st}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=2)
    ap.add_argument("--out", default=str(HERE / "results.json"))
    ap.add_argument("--prompt", default=None, help="chatbot/prompts/llm_shape/ 아래 파일 이름(비우면 설정 기본값)")
    a = ap.parse_args()

    tmp = Path(tempfile.mkdtemp(prefix="g82-offline-"))
    cfg = load_config("experiment").with_overrides(**{
        "guard.model_backend": "none", "guard.required": False,         # 가드 모델은 이 평가 대상이 아님(키워드 가드는 켜 둠)
        "session.log_dir": str(tmp / "logs"), "preview.mode": "none",
        "interview.lock_condition": False,                               # static 조건으로 확정 텍스트를 바로 넣기 위함
        "mapping.llm_fill": False,                                       # G77 호출은 이 평가 대상이 아님(spec은 G77과 무관)
        "gen3d.on_none_llm_shape": True, "gen3d.on_none_llm_shape_prompt": a.prompt})                                # G82 — 이 평가 안에서만 켬(experiment.toml은 끈 그대로)
    host = cfg.llm.host
    rt = Runtime(cfg, persist_logs=False)
    assert rt.backend_ok, rt.backend_msg
    assert rt.llm_shape_prompt is not None
    ver = ollama(host, "/api/version") or {}
    out = {"what": "G82 llm_shape offline evaluation (synthetic texts only)", "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
           "config": "experiment + gen3d.on_none_llm_shape=true (in-process only), guard model none, preview none, "
                     "mapping.llm_fill=false, lock_condition=false, persist_logs=false",
           "model": rt.backend.info(), "ollamaVersion": ver.get("version"), "prompt": rt.llm_shape_prompt.info(),
           "validatorRules": ls.VALIDATOR_RULES, "g77ValidatorRules": lf.VALIDATOR_RULES,
           "seed": cfg.gen3d.on_none_llm_shape_seed, "timeoutS": cfg.gen3d.on_none_llm_shape_timeout_s,
           "gpuBefore": nvsmi(), "ollamaPsBefore": [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])],
           "cases": []}
    sessions = {}
    for cid, group, text, expect, ko, en_ok in CASES:
        s = rt.new_session("static", f"SYN-G82-{cid}")
        drive(s, {"id": cid, **REPLIES, "confirm": {"edit": text}})
        sessions[cid] = s
    for cid, group, text, expect, ko, en_ok in CASES:
        s = sessions[cid]
        norm = s.log.data["confirmedText"]
        runs = []
        for r in range(a.runs):
            s.llm_shape_cache = {}                       # 회차마다 캐시를 비워 실제로 다시 부른다
            rec = ls.run(s, s.scene_spec, norm)
            runs.append(slim(rec))
        same = all(x.get("rawText") == runs[0].get("rawText") and x.get("adopted") == runs[0].get("adopted") for x in runs)
        form = (s.scene_spec or {}).get("form") or {}
        out["cases"].append({
            "id": cid, "group": group, "text": text, "expect": expect, "expectKo": ko, "enOk": en_ok,
            "confirmedTextSha256": ls.sha256_text(norm), "sessionFlag": lf.session_flag(s),
            "mapperForm": {k: form.get(k) for k in ("type", "base")},
            "outcome": outcome(runs[0]), "runsIdentical": same, "runs": runs})
        print(cid, outcome(runs[0]), (runs[0].get("adopted") or {}).get("en"), runs[0].get("rejectReasons"),
              "same" if same else "DIFF", flush=True)
    out["gpuAfter"] = nvsmi()
    out["ollamaPsAfter"] = [m.get("name") for m in (ollama(host, "/api/ps") or {}).get("models", [])]
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
