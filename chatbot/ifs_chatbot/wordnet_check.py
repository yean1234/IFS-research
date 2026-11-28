"""G85: 영어 대상 명사의 WordNet 상위어 검사(로컬 파일만, 실행 중 외부 호출 없음).

데이터: WordNet 3.0(nltk 말뭉치 wordnet.zip). 구현 때 한 번 chatbot/.venv/nltk_data에 내려받았다(git 밖). 라이선스는 WordNet 3.0
license(Princeton University, BSD 꼴 허용 라이선스 — 말뭉치 안 wordnet/LICENSE). nltk가 없거나 말뭉치가 없으면 status
"unavailable"(사유)로 기록하고 검사를 건너뛴다 — 그 경우 목록(shape_english_*)과 그림·메시 관문만 남는다(사실을 기록에 남김).

규칙(shared/lexicon/shape_english_rewrite_block.v0.json wordnetHypernymCheck): 대상 명사구의 낱말마다(그리고 밑줄로 이은 합성어가
WordNet에 있으면 그것도) 명사 **첫 뜻**만 본다. 그 뜻의 상위어 닫힘(hypernym + instance hypernym)에 금지 뿌리(사람·동물·몸의 부분·
불·구름(안개·연기)·영적 존재·상상의 존재)가 있으면 wordnet_forbidden. 같은 낱말 → 언제나 같은 결과(고정 파일).
"""
from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path

from .paths import CHATBOT_DIR, shared

CHECK_FILE = "shape_english_rewrite_block.v0.json"
DATA_DIR = CHATBOT_DIR / ".venv" / "nltk_data"
_lock = threading.RLock()
_state: dict | None = None


def _sha256_file(p: Path) -> str | None:
    try:
        h = hashlib.sha256()
        with open(p, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def _load(data_dir: Path = DATA_DIR) -> dict:
    cfg = json.loads(shared("lexicon", CHECK_FILE).read_text(encoding="utf-8"))["wordnetHypernymCheck"]
    st = {"version": cfg["version"], "roots": list(cfg["forbiddenRoots"]), "placeRoots": list(cfg.get("placeRoots") or []),
          "status": "unavailable", "reason": None, "placeRootSet": None,
          "wordnetVersion": None, "nltkVersion": None, "dataFile": None, "dataSha256": None,
          "license": "WordNet 3.0 license (Princeton University)", "wn": None, "rootSet": None}
    try:
        import nltk  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001
        st["reason"] = f"nltk_missing: {type(exc).__name__}"
        return st
    z = Path(data_dir) / "corpora" / "wordnet.zip"
    if not z.is_file() and not (Path(data_dir) / "corpora" / "wordnet").is_dir():
        st["reason"] = "wordnet_corpus_missing"
        return st
    try:
        nltk.data.path[:] = [str(data_dir)]            # 이 폴더만 본다(다른 곳의 말뭉치·내려받기 없음)
        from nltk.corpus import wordnet as wn  # noqa: PLC0415
        wn.ensure_loaded()
        roots = {wn.synset(r) for r in st["roots"]}
        st["placeRootSet"] = {wn.synset(r) for r in st["placeRoots"]}
        st.update(status="available", wordnetVersion=wn.get_version(), nltkVersion=nltk.__version__,
                  dataFile="nltk_data/corpora/wordnet.zip" if z.is_file() else "nltk_data/corpora/wordnet",
                  dataSha256=_sha256_file(z) if z.is_file() else None, wn=wn, rootSet=roots)
    except Exception as exc:  # noqa: BLE001
        st["reason"] = f"wordnet_load_failed: {type(exc).__name__}: {exc}"[:200]
    return st


def state() -> dict:
    global _state
    with _lock:
        if _state is None:
            _state = _load()
        return _state


def info() -> dict:
    """기록용(판·데이터 해시·사용 가능 여부)."""
    s = state()
    return {k: s[k] for k in ("version", "status", "reason", "wordnetVersion", "nltkVersion", "dataFile", "dataSha256",
                              "license", "roots", "placeRoots")}


def first_sense(word: str):
    s = state()
    if s["status"] != "available":
        return None
    ss = s["wn"].synsets(word, pos="n")
    return ss[0] if ss else None


def word_verdict(word: str) -> dict:
    """낱말 하나 → {word, sense, roots(걸린 금지 뿌리)}. WordNet에 없으면 sense None."""
    s = state()
    out = {"word": word, "sense": None, "roots": [], "placeRoots": []}
    if s["status"] != "available":
        return out
    with _lock:
        syn = first_sense(word)
        if syn is None:
            return out
        closure = set(syn.closure(lambda x: x.hypernyms() + x.instance_hypernyms())) | {syn}
        out.update(sense=syn.name(), roots=sorted(r.name() for r in s["rootSet"] if r in closure),
                   placeRoots=sorted(r.name() for r in (s["placeRootSet"] or ()) if r in closure))
    return out


def reasons(phrase: str) -> tuple[list[str], dict]:
    """대상 명사구(영어 소문자 1–3낱말) → (기각 사유, 기록). 사유는 wordnet_forbidden(금지 범주)·wordnet_place(장소, CP21-1).
    WordNet을 쓸 수 없으면 ([], {"status": "unavailable", ...})."""
    s = state()
    rec = {"version": s["version"], "status": s["status"], "words": []}
    if s["status"] != "available" or not isinstance(phrase, str):
        return [], rec
    words = phrase.split()
    if not words:
        return [], rec
    # 머리 명사(마지막 낱말)와, 두 낱말 이상이면 밑줄로 이은 합성어만 본다. 앞 낱말(꾸밈 자리)은 보지 않는다 —
    # 형용사의 드문 명사 뜻이 걸리는 과차단을 막으려는 규칙(heavy의 첫 명사 뜻 'villain 배우' → person)
    cands = [words[-1]] + (["_".join(words)] if len(words) >= 2 else [])
    for w in cands:
        v = word_verdict(w)
        if v["sense"] is not None or w == words[-1]:
            rec["words"].append(v)
    why = ["wordnet_forbidden"] if any(v["roots"] for v in rec["words"]) else []
    if any(v["placeRoots"] for v in rec["words"]):
        why.append("wordnet_place")                      # (CP21-1) 장소·지형·물(금지 범주가 아님 → 대상 근거 없음으로 다룸)
    return why, rec
