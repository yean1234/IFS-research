"""구별 프로파일 언어 지표 — 한국어 발화에서 규칙으로 세는 표지 K1–K7과 L-B 태도 낱말.

정의: docs/rq-v4-differentiation-measure.md 3.3 「표지의 조작적 정의」(Kiwi 품사 태그 기준). LLM 없음, 결정적
(같은 입력 → 같은 출력). 결과에 Kiwi(kiwipiepy)·모델 판본을 적는다. 각 표지가 잡힌 토큰 구간(근거)을 함께 낸다.

  python -m ifs_chatbot.eval.language_markers --text "나는 불안 덩어리다."
  python -m ifs_chatbot.eval.language_markers --file utter.jsonl [--format json|csv] [--out 결과파일]
    (jsonl 한 줄: {"id": …, "when": …, "text": …}. 다른 키(session_id, prompt, participant)는 그대로 옮겨 적는다)

합성 점수(identification_index 따위)는 만들지 않는다. 표지별 원 개수와 절 수, 절당 비율만 낸다.

절(clause) 나누기 — 문서가 정하지 않아 이 모듈이 정한 규칙
- 토큰 열을 다음 자리에서 끊는다: 종결어미 `EF` 뒤, 문장부호 `SF` 뒤, 연결어미 `EC` 뒤.
  단 `EC` 다음이 보조용언 `VX`(예: 내고 있다, 알고 싶다, 무섭지 않다)이거나 `보이/VV`("~아 보이다")이면 끊지 않는다.
  관형형 `ETM`("불안한 게", "있는 것 같아요")에서는 끊지 않는다(안긴 절은 바깥 절에 포함).
- 서술어 토큰(`VV`·`VA`·`VX`·`VCP`·`VCN`·`XSV`·`XSA`)이 하나라도 있는 조각만 절로 센다. 없는 조각은 fragment로 따로 센다.
- 한 절 안의 "서술어"는 절에 들어 있는 서술어 전부다(마지막 서술어만 보지 않음). 그래서 "내가 그 돌인 것 같아요"도 K2이고,
  "내가 본 게 그 돌이에요"도 K2로 잡힌다(오탐 가능 — known_limitations).

표지(문서 3.3을 그대로 옮김. 문서와 다르게 정한 점은 ★)
- K1 명시 1인칭: 형태 `나`·`저` + 태그 `NP` 토큰 수("내"=나/NP+의/JKG, "제"=저/NP+의/JKG 포함).
- K2 동일시 틀(절 단위): (a) 1인칭 NP 바로 뒤가 `JX`/`JKS`이고 절에 `VCP`가 있음 또는 (b) `VCP` 바로 앞 토큰이 1인칭 NP.
- K3 존재 틀(절 단위): 절에 `있/VA` 또는 `있/VV`(`VX` 제외)가 있고, 절에 1인칭 NP + `JKS`가 없으며,
  1인칭 NP + `JKB`(에게·한테·에·께…) 또는 1인칭 NP + `JKG` + `안`·`속`(NNG)이 있음.
  K3b: 같은 `있` 조건이지만 자기 위치어가 없음(1인칭 주어가 있는 절은 K3·K3b 어느 쪽도 아님).
- K4 지시어 대상 지칭: `이것`·`그것`·`저것`/NP ★(Kiwi가 "그거"를 `그거/NP`로 내므로 `이거`·`그거`·`저거`도 받음) 토큰 수,
  더하기 `이`·`그`·`저`/MM 다음 체언(들) 뒤에 `JKS`/`JX`가 오는 경우 수. NP 쪽에는 자리 조건을 걸지 않는다(문서 문장 그대로 읽음).
- K5 지각 술어: `보이/VV`이고 바로 앞 토큰이 `EC`가 아님.
- K6 과거시제(절 단위): 절에 `EP`(형태 었·았·였)가 있음. 비율 = K6 / 절 수.
- K7 주어 미지정(절 단위): `JKS`/`JX`가 바로 붙은 체언(`NNG`·`NNP`·`NNB`·`NP`·`NR`, 접미사 `XSN` 허용)이 절에 없음.
  1인칭으로 채워 넣지 않는다(AGENTS.md 원칙 2). 조사가 빠진 "나 무서워"도 K7이다(K1은 따로 1).
- 비율(rates): 절 단위 표지(K2·K3·K3b·K6·K7)와 토큰 단위 표지(K1·K4·K5) 모두 개수 / 절 수. 절이 0이면 null.

L-B 태도 낱말 — ★ 문서의 범주(열림·너그러움·차분 / 밀어냄·두려움·짜증)는 사전이 아직 없어 만들지 않는다.
- 기존 1층 사전(shared/lexicon/layer1_lexicon.v0.json)의 `emotion` 범주(감정어 49개, 하위 범주 없음)를 그대로 써서
  일치한 표제어와 사전 값(value.emotion, 영어 낱말)을 나열한다. 부정 판정은 그 사전 모듈의 규칙(lexicon.Lexicon._negated:
  앞의 안/못, 뒤 6토큰 안의 않·없·아니·못하·말)을 쓴다 ★(문서는 "두 토큰 안").
- 사전에 없는 말(예: "싫다", "괜찮다")을 위해 용언 원형(`VV`·`VA`·`XR` 형태)을 분류하지 않고 그대로 나열한다.
- 사전은 연구자 코딩용이며 참여자에게 보이지 않는다.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import sys
from functools import lru_cache
from pathlib import Path

from ..korean import Analyzer, Token, normalize

VERSION = "language-markers/0.1"
MARKERS = ("K1", "K2", "K3", "K3b", "K4", "K5", "K6", "K7")
CLAUSE_MARKERS = ("K2", "K3", "K3b", "K6", "K7")     # 절마다 참/거짓
TOKEN_MARKERS = ("K1", "K4", "K5")                    # 토큰(구간)마다 1

FIRST_PERSON = {"나", "저"}
PREDICATE_TAGS = {"VV", "VA", "VX", "VCP", "VCN", "XSV", "XSA"}
NOMINAL_TAGS = {"NNG", "NNP", "NNB", "NP", "NR"}
SUBJECT_PARTICLES = {"JKS", "JX"}
DEMONSTRATIVE_NP = {"이것", "그것", "저것", "이거", "그거", "저거"}
DEMONSTRATIVE_MM = {"이", "그", "저"}
MM_HEAD_TAGS = {"NNG", "NNP", "NNB", "NR", "XSN"}   # 지시 관형사 뒤 체언(복합 명사·접미사 허용)
PAST_EP = {"었", "았", "였"}
SELF_INSIDE = {"안", "속"}
LEXICON_FILE = ("lexicon", "layer1_lexicon.v0.json")
ATTITUDE_TAGS = {"VV", "VA", "XR"}

NOTE = ("규칙 기반 표지 개수다. 합성 점수를 만들지 않고, 개수를 심리 상태의 측정값으로 해석하지 않는다"
        "(docs/rq-v4-differentiation-measure.md 3.3 한계: 짧은 발화, 주어 생략, '저'의 중의성, '있다' 태그 흔들림, 과거시제 혼입).")

# 규칙·Kiwi 때문에 생기는 알려진 한계(테스트 tests/test_language_markers.py가 실제 동작을 고정)
KNOWN_LIMITATIONS = [
    {"id": "jeo_mm", "example": "그냥 저 자체가 무거운 거예요.",
     "what": "1인칭 '저'를 Kiwi가 지시 관형사 저/MM으로 태그 → K1을 놓치고 K4로 잘못 잡음(문서 3.3 오분석 예)"},
    {"id": "gong_nr", "example": "저 공이 저기 보였어요.",
     "what": "'공이'를 숫자 공/NR + 이/NR로 태그(문맥에 따라 다름 — '저 공이 나예요'에서는 공/NNG 이/JKS) → K4를 놓치고 K7 오탐"},
    {"id": "maeumsok", "example": "제 마음속에 작은 돌이 있어요.",
     "what": "'마음속'이 한 낱말(마음속/NNG)이라 1인칭 NP + JKG + 안·속 조건에 안 맞음 → K3이 아니라 K3b"},
    {"id": "dropped_particle", "example": "나 무서워.",
     "what": "조사가 생략된 1인칭 주어는 JKS/JX가 없어 K7(미지정)으로 셈. K1은 1로 따로 잡힘"},
    {"id": "coordinated_subject", "example": "나는 무섭고 싫어요.",
     "what": "연결어미로 이어진 둘째 절은 주어를 물려받지 않아 K7. 원칙 2에 따라 채워 넣지 않음"},
    {"id": "topic_adverbial", "example": "아까는 무거웠어요.",
     "what": "'아까는'(NNG+JX)도 주어 자리로 보아 K7이 아님(문서 규칙이 JX를 받으므로)"},
    {"id": "embedded_vcp", "example": "내가 본 게 그 돌이에요.",
     "what": "1인칭 주어가 안긴 절의 주어인데도 절에 VCP가 있어 K2로 잡힘(오탐)"},
    {"id": "jkc_identity", "example": "그건 제가 아니에요.",
     "what": "'제가'가 보격 JKC, 서술어 VCN이라 K2가 아님(부정 동일시는 세지 않음)"},
]


@lru_cache(maxsize=1)
def _analyzer() -> Analyzer:
    return Analyzer(use_kiwi=True)


@lru_cache(maxsize=1)
def _lexicon():
    from ..lexicon import Lexicon
    from ..paths import shared
    path = shared(*LEXICON_FILE)
    if not path.is_file():
        return None
    return Lexicon(path, _analyzer())


def analyzer_info() -> dict:
    a = _analyzer()
    model = None
    try:
        import kiwipiepy_model  # noqa: WPS433
        model = getattr(kiwipiepy_model, "__version__", None)
    except Exception:  # pragma: no cover - 설치 환경에 따라 다름
        pass
    return {"backend": a.backend, "kiwipiepy": a.version, "kiwipiepy_model": model}


# ---------------------------------------------------------------- 절 나누기

def _is_fp(t: Token) -> bool:
    return t.form in FIRST_PERSON and t.base_tag == "NP"


def split_clauses(toks: list[Token]) -> list[tuple[int, int]]:
    """토큰 색인 구간 [시작, 끝) 목록(서술어가 없는 조각 포함)."""
    out, start = [], 0
    for i, t in enumerate(toks):
        cut = False
        if t.base_tag in ("EF", "SF"):
            cut = True
        elif t.base_tag == "EC":
            nxt = toks[i + 1] if i + 1 < len(toks) else None
            cut = not (nxt is not None and (nxt.base_tag == "VX" or (nxt.form == "보이" and nxt.base_tag == "VV")))
        if cut:
            if i + 1 > start:
                out.append((start, i + 1))
            start = i + 1
    if start < len(toks):
        out.append((start, len(toks)))
    # 문장부호만 있는 조각은 앞 조각에 붙인다(구간 표시만 바뀌고 절 수에는 영향 없음)
    merged: list[tuple[int, int]] = []
    for s, e in out:
        if merged and all(toks[k].base_tag in ("SF", "SP", "SS", "SE", "SO", "SW") for k in range(s, e)):
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    return merged


def _subject_nominals(toks: list[Token], s: int, e: int) -> list[tuple[int, int]]:
    """절 [s, e) 안에서 JKS/JX가 바로 붙은 체언 구간(체언 시작, 조사 끝+1) 목록. 체언과 조사 사이 XSN 허용."""
    out = []
    for i in range(s, e):
        if toks[i].base_tag not in SUBJECT_PARTICLES:
            continue
        j = i - 1
        while j >= s and toks[j].base_tag == "XSN":
            j -= 1
        if j >= s and toks[j].base_tag in NOMINAL_TAGS:
            out.append((j, i + 1))
    return out


def _span(toks: list[Token], i0: int, i1: int, text: str) -> dict:
    s, e = toks[i0].start, toks[i1 - 1].end
    return {"tokens": [i0, i1], "chars": [s, e], "text": text[s:e]}


# ---------------------------------------------------------------- 분석

def analyze_text(text: str | None) -> dict:
    """문자열 하나 → 표지 개수·절·근거. text가 비면 개수 0·절 0·비율 null."""
    norm = normalize(text)
    a = _analyzer()
    flags: list[str] = []
    result = {
        "version": VERSION, "analyzer": analyzer_info(), "text": norm,
        "tokens": [], "clauses": [], "n_clauses": 0, "n_fragments": 0,
        "counts": {m: 0 for m in MARKERS}, "rates": {m: None for m in MARKERS},
        "evidence": {m: [] for m in MARKERS}, "attitude": _empty_attitude(), "flags": flags,
    }
    if not a.available:
        flags.append("kiwi_unavailable")
        result["counts"] = {m: None for m in MARKERS}
        return result
    if not norm:
        flags.append("empty_text")
        return result
    toks = a.tokens(norm)
    result["tokens"] = [[t.form, t.tag, t.start, t.end] for t in toks]
    counts, ev = result["counts"], result["evidence"]

    def add(marker: str, i0: int, i1: int, **extra) -> None:
        counts[marker] += 1
        ev[marker].append({**_span(toks, i0, i1, norm), **extra})

    # 토큰 단위 표지
    for i, t in enumerate(toks):
        if _is_fp(t):
            add("K1", i, i + 1)
        if t.base_tag == "NP" and t.form in DEMONSTRATIVE_NP:
            add("K4", i, i + 1, rule="demonstrative_np")
        if t.base_tag == "MM" and t.form in DEMONSTRATIVE_MM:
            j = i + 1
            while j < len(toks) and toks[j].base_tag in MM_HEAD_TAGS:
                j += 1
            if j > i + 1 and j < len(toks) and toks[j].base_tag in SUBJECT_PARTICLES:
                add("K4", i, j + 1, rule="mm_noun_subject")
        if t.form == "보이" and t.base_tag == "VV":
            prev = toks[i - 1] if i > 0 else None
            if prev is None or prev.base_tag != "EC":
                add("K5", i, i + 1)

    # 절 단위 표지
    for ci, (s, e) in enumerate(split_clauses(toks)):
        preds = [k for k in range(s, e) if toks[k].base_tag in PREDICATE_TAGS]
        clause = {"index": ci, **_span(toks, s, e, norm), "has_predicate": bool(preds), "markers": []}
        result["clauses"].append(clause)
        if not preds:
            result["n_fragments"] += 1
            continue
        result["n_clauses"] += 1
        subj = _subject_nominals(toks, s, e)
        fp_subject = any(_is_fp(toks[k]) and toks[k + 1].base_tag in SUBJECT_PARTICLES for k in range(s, e - 1))
        fp_jks = any(_is_fp(toks[k]) and toks[k + 1].base_tag == "JKS" for k in range(s, e - 1))
        vcp = [k for k in range(s, e) if toks[k].base_tag == "VCP"]

        def mark(m: str, i0: int, i1: int, **extra) -> None:
            clause["markers"].append(m)
            add(m, i0, i1, clause=ci, **extra)

        # K2
        if vcp and fp_subject:
            mark("K2", s, e, rule="a_fp_subject_vcp")
        elif any(k > s and _is_fp(toks[k - 1]) for k in vcp):
            mark("K2", s, e, rule="b_fp_before_vcp")
        # K3 / K3b
        iss = [k for k in range(s, e) if toks[k].form == "있" and toks[k].base_tag in ("VA", "VV")]
        if iss and not fp_jks:
            locus = None
            for k in range(s, e - 1):
                if not _is_fp(toks[k]):
                    continue
                if toks[k + 1].base_tag == "JKB":
                    locus = "fp_jkb"
                    break
                if toks[k + 1].base_tag == "JKG" and k + 2 < e and toks[k + 2].form in SELF_INSIDE \
                        and toks[k + 2].base_tag == "NNG":
                    locus = "fp_jkg_inside"
                    break
            if locus:
                mark("K3", s, e, rule=locus)
            else:
                mark("K3b", s, e)
        # K6
        if any(toks[k].base_tag == "EP" and toks[k].form in PAST_EP for k in range(s, e)):
            mark("K6", s, e)
        # K7
        if not subj:
            mark("K7", s, e)

    n = result["n_clauses"]
    result["rates"] = {m: (round(counts[m] / n, 4) if n else None) for m in MARKERS}
    result["attitude"] = attitude_words(norm, toks)
    return result


def _empty_attitude() -> dict:
    return {"lexicon": None, "emotion_hits": [], "predicate_lemmas": [],
            "note": "L-B 범주(열림·너그러움·차분/밀어냄·두려움·짜증) 사전이 없어 분류하지 않음. "
                    "emotion_hits는 기존 1층 사전 emotion 범주와 일치한 말, predicate_lemmas는 분류 없는 용언 원형 목록."}


def attitude_words(norm: str, toks: list[Token]) -> dict:
    out = _empty_attitude()
    lex = _lexicon()
    if lex is not None:
        out["lexicon"] = lex.info()
        for h in lex.hits(norm):
            if h.entry.category != "emotion":
                continue
            out["emotion_hits"].append({"lemma": h.entry.lemma, "emotion": h.entry.value.get("emotion"),
                                        "trigger": h.trigger, "chars": list(h.char_span), "negated": h.negated})
    from ..lexicon import Lexicon
    for i, t in enumerate(toks):
        if t.base_tag in ATTITUDE_TAGS:
            out["predicate_lemmas"].append({"lemma": t.form, "tag": t.tag, "chars": [t.start, t.end],
                                            "negated": Lexicon._negated(toks, i)})
    return out


# ---------------------------------------------------------------- 여러 발화

def flat_row(item: dict, res: dict) -> dict:
    """CSV용 평평한 행. 근거는 '표지:문자구간' 목록 문자열."""
    row = {k: item.get(k) for k in ("id", "participant", "session_id", "when", "prompt")}
    row["text"] = res["text"]
    row["n_clauses"] = res["n_clauses"]
    row["n_fragments"] = res["n_fragments"]
    for m in MARKERS:
        row[m] = res["counts"][m]
    for m in MARKERS:
        row[f"rate_{m}"] = res["rates"][m]
    att = res["attitude"]
    row["emotion_hits"] = ";".join(("~" if h["negated"] else "") + h["lemma"] for h in att["emotion_hits"])
    row["predicate_lemmas"] = ";".join(("~" if p["negated"] else "") + p["lemma"] for p in att["predicate_lemmas"])
    row["evidence"] = ";".join(f"{m}:{e['text']}" for m in MARKERS for e in res["evidence"][m])
    row["flags"] = ";".join(res["flags"])
    return row


CSV_COLUMNS = (["id", "participant", "session_id", "when", "prompt", "text", "n_clauses", "n_fragments"]
               + list(MARKERS) + [f"rate_{m}" for m in MARKERS]
               + ["emotion_hits", "predicate_lemmas", "evidence", "flags"])


def read_jsonl(path: str | Path) -> list[dict]:
    items = []
    for ln, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        if not isinstance(obj, dict):
            raise ValueError(f"{path}:{ln}: JSON 객체가 아님")
        items.append(obj)
    return items


def analyze_items(items: list[dict]) -> list[dict]:
    return [{"item": it, "result": analyze_text(it.get("text"))} for it in items]


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    return str(v)


def to_csv(rows: list[dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(CSV_COLUMNS)
    for r in rows:
        w.writerow([_cell(r.get(c)) for c in CSV_COLUMNS])
    return buf.getvalue()


def check_cases(doc: dict) -> dict:
    """검증 문장 세트: cases[*] = {id, sentence, expected{표지: 개수, n_clauses}, basis, cause_if_mismatch, note}.
    expected는 사람이 문서 3.3 정의를 (올바른 품사로) 적용했을 때 기대하는 값이다. actual·match를 다시 계산하고
    표지별 맞음/전체와 틀린 사례 목록을 붙인다. 숨기지 않는다."""
    keys = list(MARKERS) + ["n_clauses"]
    per = {k: {"correct": 0, "total": 0} for k in keys}
    cases, wrong = [], []
    for c in doc.get("cases", []):
        res = analyze_text(c["sentence"])
        actual = {**{m: res["counts"][m] for m in MARKERS}, "n_clauses": res["n_clauses"]}
        exp = {k: c["expected"].get(k, 0) for k in keys}
        diff = {k: {"expected": exp[k], "actual": actual[k]} for k in keys if exp[k] != actual[k]}
        for k in keys:
            per[k]["total"] += 1
            per[k]["correct"] += int(exp[k] == actual[k])
        row = {**{k: v for k, v in c.items() if k not in ("actual", "match", "diff", "tokens")},
               "expected": exp, "actual": actual, "match": not diff, "diff": diff,
               "tokens": " ".join(f"{t[0]}/{t[1]}" for t in res["tokens"])}
        cases.append(row)
        if diff:
            wrong.append({"id": c["id"], "sentence": c["sentence"], "diff": diff,
                          "cause_if_mismatch": c.get("cause_if_mismatch")})
    return {**{k: v for k, v in doc.items() if k not in ("cases", "accuracy", "mismatches", "analyzer")},
            "analyzer": analyzer_info(),
            "accuracy": {"cases_all_match": sum(1 for c in cases if c["match"]), "cases_total": len(cases),
                         "per_marker": {k: f"{v['correct']}/{v['total']}" for k, v in per.items()}},
            "mismatches": wrong, "cases": cases}


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.language_markers",
                                 description="한국어 발화의 언어 표지 K1–K7·태도 낱말(규칙, LLM 없음)")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--text", help="발화 한 개(한두 문장)")
    src.add_argument("--file", help='jsonl: 한 줄에 {"id", "when", "text"}')
    src.add_argument("--cases", help="검증 문장 세트 JSON(expected 포함) → actual·match·정확도를 다시 계산")
    ap.add_argument("--format", choices=("json", "csv"), default="json")
    ap.add_argument("--out", help="결과 파일(없으면 표준 출력)")
    args = ap.parse_args(argv)
    if args.cases:
        doc = check_cases(json.loads(Path(args.cases).read_text(encoding="utf-8-sig")))
        body = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(body, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(body)
        acc = doc["accuracy"]
        print(f"모두 맞은 문장 {acc['cases_all_match']}/{acc['cases_total']} · " +
              ", ".join(f"{k} {v}" for k, v in acc["per_marker"].items()), file=sys.stderr)
        return
    items = [{"id": "text", "text": args.text}] if args.text is not None else read_jsonl(args.file)
    done = analyze_items(items)
    if args.format == "csv":
        body = to_csv([flat_row(d["item"], d["result"]) for d in done])
    else:
        body = json.dumps({"version": VERSION, "analyzer": analyzer_info(), "note": NOTE,
                           "known_limitations": KNOWN_LIMITATIONS,
                           "results": [{**{k: v for k, v in d["item"].items() if k != "text"}, **d["result"]}
                                       for d in done]},
                          ensure_ascii=False, indent=2) + "\n"
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(body, encoding="utf-8")
        print(f"결과: {args.out} ({len(done)}개)")
    else:
        sys.stdout.write(body)


if __name__ == "__main__":
    main()
