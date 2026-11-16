"""전 과정 실행 검증(E2E, 작업 5) — 코퍼스 → 실제 컨트롤러(정적 조건, 조건 1) → 확정 텍스트 → v0·v1 SceneSpec 파일
→ 스키마 검증 → 채점 요약 → (선택) Unity 배치 캡처 report.json과 spec 값의 적용값 대조. LLM·네트워크를 쓰지 않는다.

  cd chatbot
  python -m ifs_chatbot.eval.e2e --corpus tests/fixtures/imagery_corpus/heldout.json --out ../docs/validation/e2e
  # Unity: -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run -specDir <out>/specs -outDir <out>/unity ...
  python -m ifs_chatbot.eval.e2e --corpus ... --out ../docs/validation/e2e --unity-out ../docs/validation/e2e/unity \
         --unity-log <capture.log>

출력(<out> 아래, 결과 파일에 절대 경로를 남기지 않는다):
  specs/<id>.<매핑>.json   컨트롤러가 장면 폴더에 쓴 파일의 바이트 그대로(Unity -specDir로 그대로 쓴다)
  score/                  fidelity.compare와 같은 배치: runs.json·report.*(A = 첫 매핑), compare/(B), paired.*
  schema.json             spec마다 스키마 버전·오류·원칙 검사(check_principles) 결과
  drift.json              세션 로그 drift(판정·DI) 항목별(참고 수치, AC-2 집계 아님)
  applied_values.json/md  (--unity-out을 줄 때) Unity가 기록한 params와 spec 값 대조(AC-5.7)
  summary.json, results.md, pipeline.log

동결 규칙(docs/decisions.md D04): 이 스크립트는 매핑·채점·drift·컨트롤러를 부르기만 하고 바꾸지 않는다.
채점은 fidelity.score_runs·paired_compare를 그대로 쓴다(같은 코퍼스면 fidelity --compare와 같은 report.json·paired.json).

## 적용값 대조(AC-5.7)
Unity BatchCapture는 SceneParams.ToRecord()(소수 4자리, Math.Round = 짝수 반올림)만 report.json params에 남긴다.
반올림 전 런타임 값 기록이 없으므로 비교 원천은 (나)다: spec 원값을 Unity와 같은 규칙으로 반올림한 뒤 비교한다.
같은 규칙 = .NET Math.Round(double, 4)의 계산 방식(값 × 10⁴ → 짝수 반올림 → ÷ 10⁴, 배정밀도)을 그대로 따른다.
십진 정확 반올림(Python round(v, 4))과 결과가 다른 반올림 경계 사례는 따로 센다.
spec → params 대응은 SceneParams.FromSpec과 같다: material.color.s = material.saturation ?? material.color.s, 0–1로 자름.
값이 null인 슬롯은 대조하지 않고(기본값), 대신 Unity defaultsUsed에 들어 있는지 확인한다(말한 값과 기본값을 섞지 않음).
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

from ..config import Config, load_config
from ..scene_builder import normalize_confirmed
from ..scene_spec import SCHEMA_FILE, SCHEMA_FILE_V21, SPEC_VERSION_V21, check_principles, schema_errors
from . import fidelity
from .corpus_run import RUNNER_VERSION, make_runtime, mapping_fallbacks, run_items

E2E_VERSION = "0.1.0"
DEFAULT_MAPPERS = ("v0", "v1")
TOLERANCE = 1e-6

# Unity SceneParams.NumericKeys / CategoricalKeys (unity/Assets/IFS/Runtime/SceneSpec/SceneParams.cs)
UNITY_NUMERIC = ("material.color.h", "material.color.s", "material.color.l", "material.brightness",
                 "material.roughness", "material.opacity", "material.erosion", "layout.size", "layout.distance",
                 "layout.verticalOffset", "motion.speed")
UNITY_CATEGORICAL = ("form.type", "form.posture", "motion.type")
# Unity 로그에서 오류로 세는 패턴(docs/acceptance.md AC-4 확인 방법과 같음)
LOG_ERROR_RE = re.compile(r"error CS|Shader error|^\w*Exception:|\[Exception\]", re.M)
LOG_EXCLUDE = "UnityLogCheckDelegatingCommand:CaptureException"


# ── 도우미 ──────────────────────────────────────────────────────────────────
def _dump(o) -> str:
    return json.dumps(o, ensure_ascii=False, indent=2) + "\n"


def _sid(item_id) -> str:
    """corpus_run.run_items와 같은 세션 ID 규칙."""
    return "".join(ch if ch.isalnum() or ch in "_-" else "-" for ch in str(item_id))[:40]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dotnet_round4(v: float) -> float:
    """.NET Math.Round(double, 4)(MidpointRounding.ToEven)의 계산을 그대로 따른다: v × 10⁴ → 짝수 반올림 → ÷ 10⁴."""
    v = float(v)
    if abs(v) >= 1e16:
        return v
    return float(round(v * 10000.0)) / 10000.0


def clamp01(v: float) -> float:
    return 0.0 if v < 0 else (1.0 if v > 1 else float(v))


def _get(spec: dict, path: str):
    group, key = path.split(".")
    return ((spec or {}).get(group) or {}).get(key)


def expected_params(spec: dict) -> tuple[dict, dict]:
    """spec → Unity SceneParams가 쓸 값 중 spec이 값을 정한 것만(SceneParams.FromSpec과 같은 대응).
    (수치 {key: spec 원값(0–1로 자르기 전)}, 범주 {key: 값}). null이면 넣지 않는다(Unity 기본값)."""
    num: dict = {}
    cat: dict = {}
    color = _get(spec, "material.color")
    if isinstance(color, dict):
        num["material.color.h"] = color.get("h")
        num["material.color.l"] = color.get("l")
    sat = _get(spec, "material.saturation")
    if sat is not None:
        num["material.color.s"] = sat
    elif isinstance(color, dict):
        num["material.color.s"] = color.get("s")
    for k in ("material.brightness", "material.roughness", "material.opacity", "material.erosion",
              "layout.size", "layout.distance", "layout.verticalOffset", "motion.speed"):
        v = _get(spec, k)
        if v is not None:
            num[k] = v
    for k in UNITY_CATEGORICAL:
        v = _get(spec, k)
        if v is not None:
            cat[k] = v
    return {k: v for k, v in num.items() if v is not None}, cat


# ── AC-3.9: LLM·HTTP·소켓 차단 ────────────────────────────────────────────────
@contextlib.contextmanager
def network_guard():
    """재생·매핑하는 동안 LLM 호출 함수와 HTTP·소켓 클라이언트를 호출 즉시 예외를 내도록 바꾼다(AC-3.9).
    tests/test_scene_builder_v1.py의 no_network 고정 장치와 같은 대상. 시도한 호출 이름을 목록으로 돌려준다."""
    import socket
    import urllib.request

    import httpx

    from .. import llm
    calls: list[str] = []

    def boom(name):
        def _f(*a, **k):
            calls.append(name)
            raise AssertionError(f"매핑 경로에서 {name} 호출")
        return _f

    targets = [(socket.socket, "connect"), (httpx, "get"), (httpx, "post"), (httpx.Client, "send"),
               (urllib.request, "urlopen"), (llm.OllamaBackend, "generate"), (llm.OllamaBackend, "_post"),
               (llm.OfflineTemplateBackend, "generate")]
    try:
        import ollama
        targets += [(ollama, n) for n in ("chat", "generate") if hasattr(ollama, n)]
    except ImportError:
        pass
    try:
        import requests
        targets.append((requests.Session, "request"))
    except ImportError:
        pass
    missing = object()
    saved = [(obj, name, vars(obj).get(name, missing)) for obj, name in targets]
    labels = [f"{getattr(o, '__name__', type(o).__name__)}.{n}" for o, n in targets]
    try:
        for (obj, name), label in zip(targets, labels):
            setattr(obj, name, boom(label))
        yield {"targets": labels, "calls": calls}
    finally:
        for obj, name, orig in reversed(saved):
            if orig is missing:
                delattr(obj, name)                    # 상속받던 속성이면 덮어쓴 것만 지운다
            else:
                setattr(obj, name, orig)


# ── 1–3. 재생 → spec 파일 ─────────────────────────────────────────────────────
def replay(corpus: dict, mapper: str, work_dir: Path, base: Config | None = None) -> tuple[dict, dict, dict]:
    """한 매핑으로 코퍼스 전체를 실제 컨트롤러(정적 조건)에 재생한다.
    (runs — corpus_run.run_corpus와 같은 형식, {id: 장면 파일 바이트}, {id: 세션 로그 drift})"""
    rt, label = make_runtime(work_dir, mapper, base)
    builder_info = rt.scene_builder.info() if hasattr(rt.scene_builder, "info") else {}
    items = run_items(rt, corpus["items"])
    runs = {"runner": f"corpus-run/{RUNNER_VERSION}", "corpusId": corpus.get("corpusId"),
            "corpusVersion": corpus.get("version"), "condition": "static", "mapper": label,
            "builder": builder_info, "analyzer": rt.analyzer.info(),
            "mappingFallback": mapping_fallbacks(items), "items": items}
    files: dict = {}
    drift: dict = {}
    for item in corpus["items"]:
        s = rt.sessions[_sid(item["id"])]
        path = s.scene_path
        files[item["id"]] = path.read_bytes() if path.exists() else None
        d = s.log.data.get("drift") or {}
        a = d.get("assessment") or {}
        drift[item["id"]] = {"enabled": d.get("enabled"), "decision": a.get("decision"), "DI": a.get("DI"),
                             "reason": a.get("reason"), "maxAdjacentDI": a.get("maxAdjacentDI"),
                             "summary": d.get("summary"), "error": d.get("error"),
                             "sceneSpecProblems": (s.log.data.get("sceneSpec") or {}).get("problems")}
    info = {"builder": builder_info, "drift": rt.drift.info() if rt.drift else None}
    return runs, files, {"info": info, "items": drift}


def check_specs(runs: dict, files: dict, mapper: str) -> list[dict]:
    """spec마다: 파일이 있는가, 파일 = runs의 spec인가, 해당 버전 스키마 오류, 원칙 검사(근거 구간·해시)."""
    rows = []
    for it in runs["items"]:
        raw = files.get(it["id"])
        spec = json.loads(raw.decode("utf-8")) if raw is not None else None
        version = ((spec or {}).get("meta") or {}).get("specVersion")
        errs = schema_errors(spec) if spec is not None else ["장면 파일 없음"]
        principles = check_principles(spec, normalize_confirmed(it.get("confirmedText") or "")) if spec else []
        mp = ((spec or {}).get("meta") or {}).get("mapping")
        rows.append({"id": it["id"], "mapper": mapper, "file": f"specs/{it['id']}.{mapper}.json",
                     "specVersion": version,
                     "schema": SCHEMA_FILE_V21 if version == SPEC_VERSION_V21 else SCHEMA_FILE,
                     "fileEqualsRunSpec": spec == it.get("spec"),
                     "schemaErrors": errs, "principleProblems": principles,
                     "valid": spec is not None and not errs,
                     "mapping": mp, "fallback": bool(isinstance(mp, dict) and (mp.get("used") != mp.get("requested")
                                                                               or mp.get("fallbackReason")))})
    return rows


# ── 6. Unity 적용값 대조 ──────────────────────────────────────────────────────
def compare_applied(specs: dict[str, dict], unity_report: dict) -> dict:
    """specs: {파일 이름: spec}. unity_report: BatchCapture report.json. 비교 원천 (나)."""
    entries = {e.get("spec"): e for e in unity_report.get("specs") or []}
    rows, cats, defaults_bad, missing, boundary = [], [], [], [], []
    for name in sorted(specs):
        spec = specs[name]
        e = entries.get(name)
        if e is None or not e.get("loaded"):
            missing.append({"spec": name, "inReport": e is not None, "loaded": bool(e and e.get("loaded"))})
            continue
        params = e.get("params") or {}
        num, cat = expected_params(spec)
        for k in UNITY_NUMERIC:
            if k not in num:
                if k not in (e.get("defaultsUsed") or []):
                    defaults_bad.append({"spec": name, "key": k, "issue": "spec null인데 defaultsUsed에 없음"})
                continue
            raw = float(num[k])
            clamped = clamp01(raw)
            exp = dotnet_round4(clamped)
            dec = round(clamped, 4)
            got = params.get(k)
            if got is None:
                rows.append({"spec": name, "key": k, "specValue": raw, "expected": exp, "unity": None,
                             "absDelta": None, "ok": False})
                continue
            got = float(got)
            d = abs(got - exp)
            row = {"spec": name, "key": k, "specValue": raw, "expected": exp, "unity": got, "absDelta": d,
                   "absDeltaRaw": abs(got - raw), "ok": d <= TOLERANCE}
            if raw != clamped:
                row["clamped"] = True
            if dec != exp:
                row["decimalRound"] = dec
                boundary.append(row)
            if k in (e.get("defaultsUsed") or []):
                defaults_bad.append({"spec": name, "key": k, "issue": "spec 값이 있는데 defaultsUsed에 있음"})
            rows.append(row)
        for k in UNITY_CATEGORICAL:
            if k in cat:
                cats.append({"spec": name, "key": k, "expected": cat[k], "unity": params.get(k),
                             "ok": params.get(k) == cat[k]})
                if k in (e.get("defaultsUsed") or []):
                    defaults_bad.append({"spec": name, "key": k, "issue": "spec 값이 있는데 defaultsUsed에 있음"})
            elif k not in (e.get("defaultsUsed") or []):
                defaults_bad.append({"spec": name, "key": k, "issue": "spec null인데 defaultsUsed에 없음"})
    deltas = [r["absDelta"] for r in rows if r["absDelta"] is not None]
    raw_deltas = [r["absDeltaRaw"] for r in rows if r.get("absDeltaRaw") is not None]
    fails = [r for r in rows if not r["ok"]]
    return {
        "source": "나",
        "sourceNote": "Unity report.json params = SceneParams.ToRecord()(소수 4자리, Math.Round 짝수 반올림). "
                      "반올림 전 런타임 값 기록이 없어 spec 원값을 같은 규칙(.NET Math.Round(double, 4) 계산 방식)으로 "
                      "반올림한 뒤 비교했다(docs/acceptance.md AC-5.7 (나)).",
        "tolerance": TOLERANCE,
        "specsCompared": len(specs) - len(missing),
        "specsMissingOrNotLoaded": missing,
        "numericCompared": len(rows),
        "maxAbsDelta": max(deltas) if deltas else None,
        "maxAbsDeltaVsUnroundedSpec": max(raw_deltas) if raw_deltas else None,
        "failures": fails,
        "roundingBoundaryCases": boundary,
        "clampedValues": [r for r in rows if r.get("clamped")],
        "categoricalCompared": len(cats),
        "categoricalMismatches": [c for c in cats if not c["ok"]],
        "defaultsUsedMismatches": defaults_bad,
        "rows": rows,
    }


def applied_markdown(cmp: dict) -> str:
    L = ["# Unity 적용값 대조(AC-5.7)", "", "입력은 전부 합성 대사에서 만든 spec이다.", "",
         f"- 비교 원천: ({cmp['source']}) — {cmp['sourceNote']}",
         f"- 허용 오차: |Δ| ≤ {cmp['tolerance']:g}",
         f"- 대조한 spec: {cmp['specsCompared']}개 · 누락·로드 실패: {len(cmp['specsMissingOrNotLoaded'])}개",
         f"- 수치 값 대조: {cmp['numericCompared']}개 · max |Δ| = {cmp['maxAbsDelta']!r} · 미달 {len(cmp['failures'])}건",
         f"- 참고: 반올림 전 spec 원값과의 max |Δ| = {cmp['maxAbsDeltaVsUnroundedSpec']!r}(4자리 반올림 오차, 판정에 쓰지 않음)",
         f"- 십진 정확 반올림과 .NET 방식 결과가 다른 반올림 경계 사례: {len(cmp['roundingBoundaryCases'])}건",
         f"- 0–1 밖이라 잘린 spec 값: {len(cmp['clampedValues'])}건",
         f"- 범주 값 대조: {cmp['categoricalCompared']}개 · 불일치 {len(cmp['categoricalMismatches'])}건",
         f"- defaultsUsed 불일치(null 슬롯인데 기본값 표시 없음, 또는 그 반대): {len(cmp['defaultsUsedMismatches'])}건", ""]
    if cmp["failures"]:
        L += ["## 미달 사례", "", "| spec | 키 | spec 원값 | 기대(반올림) | Unity | |Δ| |", "| --- | --- | --- | --- | --- | --- |"]
        for r in cmp["failures"]:
            L.append(f"| {r['spec']} | {r['key']} | {r.get('specValue')!r} | {r['expected']!r} | {r['unity']!r} | {r['absDelta']!r} |")
        L.append("")
    if cmp["roundingBoundaryCases"]:
        L += ["## 반올림 경계 사례", "", "| spec | 키 | spec 원값 | .NET 방식 | 십진 반올림 | Unity |", "| --- | --- | --- | --- | --- | --- |"]
        for r in cmp["roundingBoundaryCases"]:
            L.append(f"| {r['spec']} | {r['key']} | {r['specValue']!r} | {r['expected']!r} | {r['decimalRound']!r} | {r['unity']!r} |")
        L.append("")
    by_key = Counter(r["key"] for r in cmp["rows"])
    L += ["## 키별 대조 수", "", "| 키 | 대조 수 | max |Δ| |", "| --- | --- | --- |"]
    for k in UNITY_NUMERIC:
        ds = [r["absDelta"] for r in cmp["rows"] if r["key"] == k and r["absDelta"] is not None]
        L.append(f"| {k} | {by_key.get(k, 0)} | {max(ds)!r} |" if ds else f"| {k} | 0 | – |")
    return "\n".join(L) + "\n"


def unity_log_check(text: str) -> dict:
    hits = [m.group(0) for m in LOG_ERROR_RE.finditer(text)
            if LOG_EXCLUDE not in text[text.rfind("\n", 0, m.start()) + 1:text.find("\n", m.end())]]
    ends = re.findall(r"\[BatchCapture\] 끝: ok=(\w+)", text)
    loaded = sorted(set(re.findall(r"\[SceneLoader\] (\S+\.json) 로드:", text)))
    return {"errorPatternHits": len(hits), "hits": hits[:20], "batchCaptureEnd": ends,
            "batchCaptureFailed": "[BatchCapture] 실패" in text,
            "loadedLines": len(loaded), "loadedFiles": loaded,
            "readFailures": text.count("SceneSpec을 읽지 못했습니다"),
            "formatWarnings": text.count("[SceneLoader] 형식 경고")}


def sanitize_text(text: str, roots: list[tuple[str, str]], log: bool = False) -> str:
    """로컬 절대 경로를 <repo>\\…·<home>\\… 로, 계정·컴퓨터 이름을 <user>·<host>로 바꾼다(docs/decisions.md D06).
    log=True(Unity 로그)면 라이선스 Machine Id와 IPv4 주소도 가린다."""
    for root, label in roots:
        if label in ("<user>", "<host>"):
            text = re.sub(rf"(?<![A-Za-z0-9]){re.escape(root)}(?![A-Za-z0-9])", label, text)
            continue
        for variant in {root, root.replace("\\", "/"), root.replace("/", "\\"), root.replace("\\", "\\\\")}:
            text = text.replace(variant, label)
    if log:
        text = re.sub(r"(Machine Id:\s*)\S+", r"\1<masked>", text)
        # 사설·링크 로컬 IPv4만(버전 문자열 1.0.0.0 등은 건드리지 않는다)
        text = re.sub(r"(?<![\d.])(?:10|172|192|169)(?:\.\d{1,3}){3}(?![\d.])", "<ip>", text)
    return text


def path_roots() -> list[tuple[str, str]]:
    """(바꿀 문자열, 표기). 경로를 먼저(긴 것부터), 그다음 계정·컴퓨터 이름."""
    import os

    from ..paths import REPO_ROOT
    roots = [(str(REPO_ROOT.resolve()), "<repo>")]
    home = str(Path.home())
    if home and home not in roots[0][0]:
        roots.append((home, "<home>"))
    roots.sort(key=lambda r: -len(r[0]))
    for env, label in (("USERNAME", "<user>"), ("USER", "<user>"), ("COMPUTERNAME", "<host>")):
        v = os.environ.get(env)
        if v and len(v) >= 3 and (v, label) not in roots:
            roots.append((v, label))
    return roots


# ── 결과 쓰기 ────────────────────────────────────────────────────────────────
def _metric_rows(paired: dict) -> list[str]:
    L = ["| 지표 | v0 | v1 | 차이(v1 − v0) | 차이 95% CI |", "| --- | --- | --- | --- | --- |"]
    for m, v in paired["metrics"].items():
        L.append(f"| {m} | {fidelity._fmt(v['a'])} | {fidelity._fmt(v['b'])} | {fidelity._fmt(v['diff'])} | {fidelity._ci(v)} |")
    return L


def results_markdown(summary: dict, reports: dict, paired: dict | None) -> str:
    s = summary
    L = ["# 전 과정 실행 검증(E2E) 결과", "",
         "> 입력은 전부 **합성 대사**다(AI 에이전트가 쓰고 라벨을 붙인 합성 코퍼스). 참여자 데이터가 아니다. "
         "수치는 이 합성 코퍼스에서의 공학 회귀 지표이며 심상 구현의 타당도 증거가 아니다(docs/acceptance.md 머리말).", "",
         f"- 코퍼스: {s['corpus']['corpusId']}@{s['corpus']['version']} · {s['corpus']['file']} · sha256 {s['corpus']['sha256']}",
         f"- 형식 검사(--check-corpus): 오류 {s['corpus']['checkErrors']} · 경고 {s['corpus']['checkWarnings']}",
         f"- 입력 수: {s['items']} · 매핑: {', '.join(s['mappers'])} · 조건: 정적(조건 1), LLM 없음",
         "- LLM·네트워크 차단(AC-3.9): " + (f"켬 — {len(s['network']['targets'])}개 함수({', '.join(s['network']['targets'])})를 "
                                         f"호출 즉시 예외로 바꾼 상태에서 재생·매핑, 시도된 호출 {len(s['network']['calls'])}건"
                                         if s["network"].get("guard") else "끔"),
         f"- 도구: {s['tool']} · 채점기 {s['scorer']} · 빌더 " + ", ".join(f"{m} = {b}" for m, b in s['builders'].items())
         + f" · drift {s['drift'].get('version')}", "",
         "## 스키마·파일", "", "| 매핑 | spec 파일 | 스키마 | 스키마 유효 | 원칙 검사 문제 | 파일 = 재생 spec | 매핑 대체(폴백) |",
         "| --- | --- | --- | --- | --- | --- | --- |"]
    for m, v in s["schema"].items():
        L.append(f"| {m} | {v['files']} | {', '.join(v['schemaFiles'])} | {v['valid']}/{v['files']} | {v['principleProblems']} | "
                 f"{v['fileEqualsRunSpec']}/{v['files']} | {v['fallbacks']} |")
    L += ["", "## 채점 요약(속성 단위, phrase_missing 제외)", ""]
    if paired:
        L += _metric_rows(paired)
    L += ["", "| 매핑 | 속성 | 슬롯 속성 | 슬롯 상태 | 미반영 | 절 색인으로만 남은 손실 | 퍼지 경로 값 | 근거 없는 값(근거/경로/값 있는 슬롯) | 근거 없는 값 사유 | 매핑 대체 |",
          "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for m, r in reports.items():
        o = r["summary"]["overall"]
        L.append(f"| {m} | {o['attributes']} | {o['slotAttributes']} | "
                 + ", ".join(f"{k} {v}" for k, v in o["slotStatus"].items())
                 + f" | {o['unreflected']} | {o['lostClauseIndexOnly']} | {o['fuzzyValues']} | "
                 f"{o['unsupportedValues']}/{o['spuriousValues']}/{o['valuesFilled']} | "
                 + ", ".join(f"{k} {v}" for k, v in o["unsupportedReasons"].items())
                 + f" | {r['summary']['mappingFallback']['count']} |")
    L += ["", "## 매핑별 신뢰구간(항목 단위 군집 부트스트랩 95%)", "", "| 지표 | " + " | ".join(reports) + " |",
          "| --- | " + " | ".join("---" for _ in reports) + " |"]
    for m in fidelity.METRICS:
        cells = []
        for r in reports.values():
            b = r["summary"]["bootstrap"]["metrics"][m]
            cells.append(f"{fidelity._fmt(b['estimate'])} {fidelity._ci(b)}")
        L.append(f"| {m} | " + " | ".join(cells) + " |")
    L += ["", "## drift(세션 로그, 참고 수치 — AC-2 집계 아님)", "", "| 매핑 | drift | no_drift | undecidable | 오류 |",
          "| --- | --- | --- | --- | --- |"]
    for m, v in s["drift"]["byMapper"].items():
        L.append(f"| {m} | {v['predictedDrift']} | {v['noDrift']} | {v['undecidable']} | {v['errors']} |")
    if s.get("unity"):
        u = s["unity"]
        L += ["", "## Unity", "",
              f"- report.json: {u['report']} · ok = {u['ok']} · spec 파일 {u['specFiles']} · 로드 {u['loaded']} · 캡처 실패 {u['captureFailures']}",
              f"- Console 오류 {u['consoleErrors']} · 예외 {u['consoleExceptions']} · 스크린샷(장면 PNG) {u['screenshots']}/{u['expectedScreenshots']}"
              f" · 상세 PNG {u['detailScreenshots']}",
              f"- Unity 로그: 오류 패턴(error CS·Shader error·Exception) {u.get('log', {}).get('errorPatternHits')}건 · "
              f"'[SceneLoader] … 로드:' 줄 {u.get('log', {}).get('loadedLines')}개 · 읽기 실패 {u.get('log', {}).get('readFailures')} · "
              f"형식 경고 {u.get('log', {}).get('formatWarnings')} · 끝 표시 {u.get('log', {}).get('batchCaptureEnd')}",
              f"- 적용값 대조: 원천 ({u['applied']['source']}) · 수치 {u['applied']['numericCompared']}개 · max |Δ| = {u['applied']['maxAbsDelta']!r}"
              f" · 미달 {u['applied']['failures']} · 반올림 경계 {u['applied']['roundingBoundaryCases']} · 범주 불일치 "
              f"{u['applied']['categoricalMismatches']} · defaultsUsed 불일치 {u['applied']['defaultsUsedMismatches']}",
              f"- 프레임 시간 p95 최댓값(데스크톱 대리 측정): {u['frameMsP95Max']} ms"]
    L += ["", "## 실패·오류 목록", ""]
    for m, r in reports.items():
        L += [f"### {m}", "", "| 항목 | 유형 | 속성/경로 | phrase | 기대 | 실제 | 근거 |", "| --- | --- | --- | --- | --- | --- | --- |"]
        for f in r["failures"]:
            if f["type"] not in ("distorted", "lost", "dropped_by_controller", "unsupported", "spurious", "fuzzy_value",
                                 "negation_error"):
                continue
            ev = f.get("valueTriggers") or f.get("triggers") or f.get("trigger") or f.get("negationError") or f.get("crossSlot")
            extra = f"/{f['reason']}" if f.get("reason") else ""
            L.append(f"| {f['id']} | {f['type']}{extra} | {f.get('attr') or f.get('path')} | {f.get('phrase', '')} | "
                     f"{fidelity._fmt(f.get('expect'))} | {fidelity._fmt(f.get('actual', f.get('value')))} | {fidelity._fmt(ev)} |")
        L.append("")
    L += ["## 미반영 원문 보존 실패(AC-3.5 분자에서 빠진 속성)", "",
          "반영·포착·컨트롤러 탈락이 아닌 속성 중 phrase가 속성 단위 보존 필드에 원문 그대로 없는 것. "
          "'절 색인만'은 _clauses로만 남은 것(판정에서 인정하지 않음).", "",
          "| 매핑 | 항목 | 속성 | kind | 상태 | phrase | 절 색인만 |", "| --- | --- | --- | --- | --- | --- | --- |"]
    for m, r in reports.items():
        for it in r["items"]:
            for a in it["attributes"]:
                if a["status"] in ("reflected", "captured", "dropped_by_controller", "phrase_missing"):
                    continue
                if not a.get("verbatimPreserved"):
                    L.append(f"| {m} | {it['id']} | {a['attr']} | {a['kind']} | {a['status']}"
                             f"{'/' + a['reason'] if a.get('reason') else ''} | {a['phrase']} | "
                             f"{'예' if a.get('verbatimWithClauseIndex') else '아니오'} |")
    L += ["", "보존·손실의 상세(preserved 포함)와 배경 오염은 score/report.md·score/compare/report.md의 「실패 사례」에 있다."]
    return "\n".join(L) + "\n"


class _Log:
    def __init__(self):
        self.lines: list[str] = []

    def __call__(self, msg: str = "") -> None:
        print(msg)
        self.lines.append(msg)


def run(corpus_path: str | Path, out_dir: str | Path, mappers: tuple[str, ...] = DEFAULT_MAPPERS,
        unity_out: str | Path | None = None, unity_log: str | Path | None = None,
        B: int = fidelity.BOOTSTRAP_B, seed: int = fidelity.BOOTSTRAP_SEED, base: Config | None = None,
        no_network: bool = False) -> dict:
    log = _Log()
    out = Path(out_dir)
    corpus_path = Path(corpus_path)
    corpus = json.loads(corpus_path.read_text(encoding="utf-8"))
    chk = fidelity.check_corpus(corpus)
    log(f"[e2e {E2E_VERSION}] 코퍼스 {corpus.get('corpusId')}@{corpus.get('version')} · 항목 {chk['items']} · 정답 {chk['gold']}"
        f" · 형식 오류 {len(chk['errors'])} · 경고 {len(chk['warnings'])}")
    if chk["errors"]:
        raise ValueError("코퍼스 정답 라벨 형식 오류:\n" + "\n".join(chk["errors"]))
    base = base or load_config()
    spec_dir = out / "specs"
    spec_dir.mkdir(parents=True, exist_ok=True)
    runs_by, files_by, drift_by, rows_by, reports = {}, {}, {}, {}, {}
    guard_cm = network_guard() if no_network else contextlib.nullcontext(None)
    with guard_cm as guard, tempfile.TemporaryDirectory(prefix="ifs-e2e-") as tmp:
        for m in mappers:
            runs, files, drift = replay(corpus, m, Path(tmp) / m, base)
            runs_by[m], files_by[m], drift_by[m] = runs, files, drift
            log(f"[재생] 매핑 {m}: {len(runs['items'])}개 · 장면 파일 {sum(1 for v in files.values() if v is not None)}개"
                f" · 매핑 대체 {runs['mappingFallback']['count']}건")
        network = ({"guard": True, "targets": guard["targets"], "calls": list(guard["calls"])} if guard is not None
                   else {"guard": False})
    if no_network:
        log(f"[차단] LLM·HTTP·소켓 {len(network['targets'])}개 함수를 호출 즉시 예외로 바꾼 상태에서 재생·매핑 · 시도된 호출 "
            f"{len(network['calls'])}건")
        if network["calls"]:
            raise RuntimeError("재생·매핑 중 LLM·네트워크 호출 시도: " + ", ".join(network["calls"]))
    # spec 파일: Unity 캡처 뒤 다시 돌릴 때 바이트가 달라졌으면 멈춘다(캡처한 파일 = 지금 만든 파일이어야 대조가 뜻이 있다)
    changed = []
    for m in mappers:
        for iid, raw in files_by[m].items():
            if raw is None:
                continue
            p = spec_dir / f"{iid}.{m}.json"
            if unity_out is not None and p.exists() and p.read_bytes() != raw:
                changed.append(p.name)
            elif not p.exists() or p.read_bytes() != raw:
                p.write_bytes(raw)
    if changed:
        raise RuntimeError("Unity가 캡처한 spec 파일과 지금 만든 spec이 다릅니다: " + ", ".join(changed[:10]))
    stale = sorted(p.name for p in spec_dir.glob("*.json")
                   if not any(p.name == f"{iid}.{m}.json" for m in mappers for iid in files_by[m]))
    log(f"[spec] {spec_dir.name}/ 에 {sum(1 for m in mappers for v in files_by[m].values() if v is not None)}개"
        + (f" · 코퍼스에 없는 파일 {len(stale)}개: {', '.join(stale[:5])}" if stale else ""))
    for m in mappers:
        rows_by[m] = check_specs(runs_by[m], files_by[m], m)
        v = rows_by[m]
        log(f"[스키마] {m}: 유효 {sum(r['valid'] for r in v)}/{len(v)} · 원칙 검사 문제 {sum(len(r['principleProblems']) for r in v)}"
            f" · 파일 = 재생 spec {sum(r['fileEqualsRunSpec'] for r in v)}/{len(v)} · 폴백 {sum(r['fallback'] for r in v)}")
    # 채점(fidelity.compare와 같은 계산·같은 파일 배치)
    for m in mappers:
        reports[m] = fidelity.score_runs(corpus, runs_by[m], B, seed)   # fidelity.compare와 같게(corpusCheck 없음)
    score = out / "score"
    paired = None
    first = mappers[0]
    fidelity._write(score, runs_by[first], reports[first])
    if len(mappers) >= 2:
        second = mappers[1]
        fidelity._write(score / "compare", runs_by[second], reports[second])
        paired = fidelity.paired_compare(reports[first], reports[second], runs_by[first], runs_by[second], B, seed)
        (score / "paired.json").write_text(_dump(paired), encoding="utf-8")
        (score / "paired.md").write_text(fidelity.paired_markdown(paired), encoding="utf-8")
    for m in mappers:
        o = reports[m]["summary"]["overall"]
        log(f"[채점] {m}: 반영률 {o['reflectRate']} · 왜곡률 {o['distortRate']} · 보존률 {o['preserveRate']} · "
            f"미반영 원문 보존률 {o['unreflectedVerbatimRate']}(절 색인 포함 {o['unreflectedVerbatimRateWithClauseIndex']}) · "
            f"탈락률 {o['droppedRate']} · 퍼지 경로 값 {o['fuzzyValues']} · 근거 없는 값 비율 {o['unsupportedRate']}")
    if paired:
        c = paired["metrics"]
        log(f"[비교] 반영률 차이 {c['reflectRate']['diff']} {fidelity._ci(c['reflectRate'])} · 왜곡률 차이 "
            f"{c['distortRate']['diff']} {fidelity._ci(c['distortRate'])}")
    # drift(참고)
    drift_summary = {}
    for m in mappers:
        ds = list(drift_by[m]["items"].values())
        drift_summary[m] = {"predictedDrift": sum(d["decision"] == "drift" for d in ds),
                            "noDrift": sum(d["decision"] == "no_drift" for d in ds),
                            "undecidable": sum(d["decision"] == "undecidable" for d in ds),
                            "other": sum(d["decision"] not in ("drift", "no_drift", "undecidable") for d in ds),
                            "errors": sum(1 for d in ds if d.get("error")),
                            "undecidableReasons": dict(Counter(d.get("reason") for d in ds if d["decision"] == "undecidable"))}
        log(f"[drift] {m}: drift {drift_summary[m]['predictedDrift']} · no_drift {drift_summary[m]['noDrift']} · "
            f"undecidable {drift_summary[m]['undecidable']}")
    (out / "drift.json").write_text(_dump({m: drift_by[m] for m in mappers}), encoding="utf-8")
    (out / "schema.json").write_text(_dump({m: rows_by[m] for m in mappers}), encoding="utf-8")

    from ..paths import REPO_ROOT
    try:
        corpus_rel = corpus_path.resolve().relative_to(REPO_ROOT.resolve()).as_posix()
    except ValueError:
        corpus_rel = corpus_path.name
    summary = {
        "tool": f"e2e/{E2E_VERSION}", "scorer": f"fidelity/{fidelity.SCORER_VERSION}",
        "corpus": {"corpusId": corpus.get("corpusId"), "version": corpus.get("version"), "file": corpus_rel,
                   "sha256": sha256_file(corpus_path), "synthetic": corpus.get("synthetic"),
                   "checkErrors": len(chk["errors"]), "checkWarnings": len(chk["warnings"])},
        "items": len(corpus["items"]), "mappers": list(mappers), "condition": "static", "network": network,
        "builders": {m: (runs_by[m]["builder"] or {}).get("builder") for m in mappers},
        "analyzer": runs_by[first].get("analyzer"),
        "drift": {"version": (drift_by[first]["info"]["drift"] or {}).get("driftVersion"),
                  "info": drift_by[first]["info"]["drift"], "byMapper": drift_summary},
        "schema": {m: {"files": len(rows_by[m]), "valid": sum(r["valid"] for r in rows_by[m]),
                       "schemaFiles": sorted({r["schema"] for r in rows_by[m]}),
                       "principleProblems": sum(len(r["principleProblems"]) for r in rows_by[m]),
                       "fileEqualsRunSpec": sum(r["fileEqualsRunSpec"] for r in rows_by[m]),
                       "fallbacks": sum(r["fallback"] for r in rows_by[m]),
                       "fallbackIds": [r["id"] for r in rows_by[m] if r["fallback"]]} for m in mappers},
        "scores": {m: {k: reports[m]["summary"]["overall"][k] for k in (
            "attributes", "slotAttributes", "slotStatus", "reflectRate", "distortRate", "lostRate", "droppedRate",
            "preserveRate", "unreflectedVerbatimRate", "unreflectedVerbatimRateWithClauseIndex", "unreflected",
            "lostClauseIndexOnly", "fuzzyValues", "spuriousRate", "unsupportedRate", "spuriousValues",
            "unsupportedValues", "unsupportedReasons", "valuesFilled")} | {
            "bootstrap": {k: reports[m]["summary"]["bootstrap"]["metrics"][k] for k in fidelity.METRICS},
            "mappingFallback": reports[m]["summary"]["mappingFallback"]["count"]} for m in mappers},
        "paired": ({k: {x: v[x] for x in ("a", "b", "diff", "lo", "hi")} for k, v in paired["metrics"].items()}
                   if paired else None),
    }

    if unity_out is not None:
        summary["unity"] = unity_section(Path(unity_out), out, files_by, mappers, unity_log, log)

    (out / "summary.json").write_text(_dump(summary), encoding="utf-8")
    (out / "results.md").write_text(results_markdown(summary, reports, paired), encoding="utf-8")
    (out / "pipeline.log").write_text("\n".join(log.lines) + "\n", encoding="utf-8")
    return summary


def unity_section(unity_out: Path, out: Path, files_by: dict, mappers, unity_log, log) -> dict:
    roots = path_roots()
    rep_path = unity_out / "report.json"
    raw = rep_path.read_text(encoding="utf-8")
    clean = sanitize_text(raw, roots)
    if clean != raw:                                           # 로컬 절대 경로를 <repo>\… 로(D06)
        rep_path.write_text(clean, encoding="utf-8")
        log("[unity] report.json의 로컬 절대 경로를 <repo>/<home> 표기로 바꿈")
    rep = json.loads(clean)
    specs = {f"{iid}.{m}.json": json.loads(b.decode("utf-8")) for m in mappers for iid, b in files_by[m].items()
             if b is not None}
    cmp = compare_applied(specs, rep)
    (out / "applied_values.json").write_text(_dump(cmp), encoding="utf-8")
    (out / "applied_values.md").write_text(applied_markdown(cmp), encoding="utf-8")
    names = [Path(n).stem for n in specs]
    shots = sum(1 for n in names if (unity_out / f"{n}.png").exists())
    details = sum(1 for n in names if (unity_out / f"{n}_detail.png").exists())
    s = rep.get("summary") or {}
    entries = rep.get("specs") or []
    sec = {"report": unity_out.name + "/report.json", "ok": rep.get("ok"), "specFiles": s.get("specFiles"),
           "loaded": s.get("loaded"), "captureFailures": s.get("captureFailures"),
           "consoleErrors": s.get("consoleErrors"), "consoleExceptions": s.get("consoleExceptions"),
           "specsWithConsoleWarnings": sum(1 for e in entries if (e.get("console") or {}).get("warnings")),
           "screenshots": shots, "expectedScreenshots": len(specs), "detailScreenshots": details,
           "frameMsP95Max": s.get("frameMsP95Max"), "unityVersion": (rep.get("system") or {}).get("unityVersion"),
           "graphicsDevice": (rep.get("system") or {}).get("graphicsDevice"),
           "applied": {"source": cmp["source"], "numericCompared": cmp["numericCompared"], "maxAbsDelta": cmp["maxAbsDelta"],
                       "maxAbsDeltaVsUnroundedSpec": cmp["maxAbsDeltaVsUnroundedSpec"],
                       "failures": len(cmp["failures"]), "roundingBoundaryCases": len(cmp["roundingBoundaryCases"]),
                       "categoricalCompared": cmp["categoricalCompared"],
                       "categoricalMismatches": len(cmp["categoricalMismatches"]),
                       "defaultsUsedMismatches": len(cmp["defaultsUsedMismatches"]),
                       "specsMissingOrNotLoaded": len(cmp["specsMissingOrNotLoaded"])}}
    if unity_log is not None:
        text = Path(unity_log).read_text(encoding="utf-8", errors="replace")
        sec["log"] = unity_log_check(text)
        dst = out / "logs" / Path(unity_log).name
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(sanitize_text(text, roots, log=True), encoding="utf-8")
        sec["logFile"] = f"logs/{dst.name}"
    log(f"[unity] 로드 {sec['loaded']}/{sec['specFiles']} · 예외 {sec['consoleExceptions']} · 오류 {sec['consoleErrors']}"
        f" · 스크린샷 {shots}/{len(specs)} · 적용값 max |Δ| {cmp['maxAbsDelta']!r} · 미달 {len(cmp['failures'])}")
    return sec


def main(argv: list[str] | None = None) -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass
    ap = argparse.ArgumentParser(prog="python -m ifs_chatbot.eval.e2e", description="전 과정 실행 검증(E2E)")
    ap.add_argument("--corpus", required=True)
    ap.add_argument("--out", required=True, help="결과 폴더(specs/, score/, summary.json, results.md, pipeline.log)")
    ap.add_argument("--mappers", default=",".join(DEFAULT_MAPPERS), help="쉼표로 구분(기본 v0,v1). 첫째가 비교 기준 A")
    ap.add_argument("--unity-out", help="BatchCapture -outDir(report.json과 PNG). 주면 적용값 대조까지 한다")
    ap.add_argument("--unity-log", help="BatchCapture -logFile. 주면 오류 패턴을 세고 경로를 가린 사본을 <out>/logs/에 둔다")
    ap.add_argument("--bootstrap", type=int, default=fidelity.BOOTSTRAP_B)
    ap.add_argument("--seed", type=int, default=fidelity.BOOTSTRAP_SEED)
    ap.add_argument("--no-network", action="store_true",
                    help="재생·매핑 동안 LLM 호출 함수·HTTP·소켓을 호출 즉시 예외로 바꾼다(AC-3.9). 시도가 있으면 실패")
    args = ap.parse_args(argv)
    mappers = tuple(m.strip() for m in args.mappers.split(",") if m.strip())
    run(args.corpus, args.out, mappers, args.unity_out, args.unity_log, args.bootstrap, args.seed,
        no_network=args.no_network)


if __name__ == "__main__":
    main()
