"""생성 형태 메시 자산 조회 계층 (결정 G62, 설계 바탕 docs/codex-reviews/D8_claude.md).

챗봇 서버는 형태 생성 모델을 부르지 않는다. 생성 도구(tools/gen3d, 저장소 밖 실행)가 자산 폴더([gen3d] assets_dir, 기본
저장소 밖 gen3d-out)에 GLB + 사이드카(shared/schemas/form-asset.v0.json)를 두면, 여기서는 그 사이드카를 확정 텍스트의
sha256(사이드카 sourceTextSha256 = spec meta.sourceTextHash에서 "sha256:"을 뺀 값)으로 찾기만 한다. torch 등 모델 의존이 없다.

- 쓸 수 있는 자산: status "ok", gate.passed = true, GLB 파일이 있고 그 바이트의 sha256이 사이드카 glbSha256과 같음,
  normalization이 가장 긴 변 1.0·피벗 bottom-center. 나머지는 사유와 함께 rejected에 남긴다(차단·실패·관문 탈락·파일 없음 등).
- 쓸 수 있는 자산이 여럿이면 (seed, assetId) 순으로 앞에서 max_candidates개만 낸다. 넘친 것은 rejected(over_limit).
- 생성 후보는 후보의 한 출처다: 절차 메시 후보(candidates.generate)는 그대로 두고 그 뒤에 더한다. 생성 후보의 다른 값(색·크기 등)은
  0번 후보(덮어쓰기 없음)와 같다. 화면 순서는 전체 후보에 같은 규칙(sha256(sessionId) 순환)을 다시 적용한다.
  생성 후보가 있으면 G34의 "구별되는 후보 하나뿐이면 건너뜀"을 쓰지 않는다(생성 후보는 참여자가 골라야만 쓴다).
- 생성 메시 결과를 spec 슬롯 값으로 되돌려 쓰지 않는다(원칙 1). scene-spec 2.3은 바꾸지 않는다.
- 같은 폴더 내용·같은 spec·같은 sessionId → 같은 출력(난수·시각을 쓰지 않음).
- 기본 후보(G62-h·G62-i): [gen3d] default_form_source = procedural | generated(고정) | auto. auto는 말한 형태 낱말(사이드카
  prompt.tokens)이 모두 단순 도형 목록(shared/lexicon/primitive_forms.v0.json)에 있고 절차 메시가 그 문장에서 그 형상을 그리면
  절차 메시를, 아니면(섞인 경우 포함) 생성 메시를 기본으로 한다(judge_default_form). 근거는 generation.defaultFormRule·defaultFormBasis.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path

from .candidates import GENERATOR_VERSION, _display_offset, form_blocks, sha256_text, shape_words, slot_value
from .paths import shared

FORM_ASSETS_VERSION = "ifs-form-assets/0.1.0"
SIDECAR_MARK = "form-asset"            # 사이드카 schema 값에 이 글자가 들어 있어야 사이드카로 본다(예 "ifs-form-asset/0")
MAX_SIDECAR_BYTES = 2 * 1024 * 1024
GENERATED_SOURCE = "generated"         # 후보 sources의 form.type 값(생성 후보)
# 생성하지 않는 형태(D8 2절): 안개·불꽃은 메시가 아니라 절차·입자 경로. Unity도 mist 계획에는 생성 메시를 쓰지 않는다
NO_MESH_FORM_TYPES = ("mist",)
NO_MESH_BASES = ("flame",)
# 기본 형태 후보 설정([gen3d] default_form_source)
DEFAULT_PROCEDURAL, DEFAULT_GENERATED = "procedural", "generated"
# G62-i: auto = 말한 형태 낱말이 모두 단순 도형(shared/lexicon/primitive_forms.v0.json)이고 절차 메시가 그 문장에서 그대로 그리면
# 절차 메시가 기본, 아니면 생성 메시가 기본(judge_default_form). 같은 spec·확정 텍스트·사이드카 → 같은 판정(사전·규칙만)
DEFAULT_AUTO = "auto"
DEFAULT_SOURCES = (DEFAULT_PROCEDURAL, DEFAULT_GENERATED, DEFAULT_AUTO)
NO_GENERATED_CANDIDATE = "no_generated_candidate"     # 생성 기본 설정인데 쓸 수 있는 생성 후보가 없음(사유는 rejected)
PRIMITIVE_FORMS_FILE = "primitive_forms.v0.json"      # shared/lexicon 아래 단순 도형 목록(auto만 읽음)
# 기본이 왜 그렇게 정해졌는가(generation.defaultFormRule)
RULE_SETTING_PROCEDURAL = "setting_procedural"        # 설정이 procedural(고정)
RULE_SETTING_GENERATED = "setting_generated"          # 설정이 generated(고정)
RULE_PRIMITIVE = "primitive_stated"                   # auto: 말한 형태 낱말이 모두 단순 도형 → 절차 기본
RULE_NON_PRIMITIVE = "non_primitive_stated"           # auto: 단순 도형이 아닌 형태 낱말이 하나라도 있음 → 생성 기본
RULE_NO_GENERATED = "no_generated_candidate"          # auto: 쓸 수 있는 생성 후보가 없음(형태를 말하지 않았거나 막힘·실패) → 절차
RULE_UNTRACEABLE = "form_words_untraceable"           # auto: 형태 낱말을 확정 텍스트로 거슬러 갈 수 없음 → 절차(fail closed)
RULE_NO_FORM_WORDS = "no_form_words"                  # auto: 생성 후보는 있는데 사이드카에 형태 낱말이 없음 → 절차(fail closed)
DEFAULT_FORM_RULES = (RULE_SETTING_PROCEDURAL, RULE_SETTING_GENERATED, RULE_PRIMITIVE, RULE_NON_PRIMITIVE,
                      RULE_NO_GENERATED, RULE_UNTRACEABLE, RULE_NO_FORM_WORDS)
# Unity ShapeMapping.Shapes(모형이 있는 모양 값, docs/shape-mapping.md 표). 다른 모양 값은 기본 형태로 그려진다
SHAPE_MODEL_VALUES = ("round", "square", "flat", "pointed")
TYPES_DRAWING_SHAPE_OR_BASE = (None, "blob")          # 모양 모형·기본 형상을 그리는 form.type(규칙 4·9, candidates.BASE_FORM_TYPES)

# rejected 사유
R_BLOCKED = "blocked"
R_FAILED = "failed"
R_GATE = "gate_not_passed"
R_GLB_MISSING = "glb_missing"
R_GLB_SHA = "glb_sha256_mismatch"
R_INVALID = "sidecar_invalid"
R_OVER_LIMIT = "over_limit"
R_FORM_BLOCKED = "form_blocked_G50"
R_NO_MESH_FORM = "no_mesh_form"
R_GLB_UNREADABLE = "glb_unreadable"           # GLB 형식을 미리보기·러너 읽기 규칙으로 읽지 못함
R_PREVIEW_FAILED = "preview_failed"           # 미리보기(WebGL·image)가 그 GLB를 그리지 못함 → 후보에서 뺌
R_NO_SHAPE_PREVIEW = "no_shape_preview"       # 미리보기가 글 요약(none)이라 형태를 보일 수 없음 → 후보에서 뺌


class GlbError(ValueError):
    """GLB를 읽지 못함(Unity GlbMeshReader가 받지 않는 형식과 같은 규칙)."""


def read_glb_positions(data: bytes) -> tuple[list[tuple[float, float, float]], int]:
    """GLB → (glTF 좌표의 정점 위치 목록, 삼각형 수). Unity GlbMeshReader와 같은 조건만 받는다: glTF 2.0 바이너리, BIN 버퍼 하나,
    extensionsRequired 없음, 프리미티브 mode 4, POSITION float VEC3(sparse 아님), indices u8·u16·u32 또는 없음.
    노드 변환은 곱하지 않는다(받을지만 보고, 가짜 렌더러의 대략적인 윤곽용). 실패하면 GlbError."""
    import struct
    if len(data) < 20 or data[:4] != b"glTF":
        raise GlbError("GLB 매직(glTF)이 아님")
    version, total = struct.unpack_from("<II", data, 4)
    if version != 2 or total > len(data):
        raise GlbError("glTF 2.0 바이너리가 아니거나 길이가 맞지 않음")
    off, js, binary = 12, None, None
    while off + 8 <= total:
        ln, typ = struct.unpack_from("<II", data, off)
        if off + 8 + ln > total:
            raise GlbError("청크가 파일 밖으로 나감")
        chunk = data[off + 8:off + 8 + ln]
        if typ == 0x4E4F534A and js is None:
            js = chunk
        elif typ == 0x004E4942 and binary is None:
            binary = chunk
        off += 8 + ln
    if js is None or binary is None:
        raise GlbError("JSON 또는 BIN 청크가 없음")
    try:
        g = json.loads(js.decode("utf-8"))
    except ValueError as exc:
        raise GlbError(f"JSON 청크를 읽지 못함: {exc}") from exc
    if g.get("extensionsRequired"):
        raise GlbError(f"필수 확장을 지원하지 않음: {g['extensionsRequired']}")
    if any("uri" in b for b in g.get("buffers") or []):
        raise GlbError("외부 버퍼(uri)는 받지 않음")
    acc, views = g.get("accessors") or [], g.get("bufferViews") or []

    def view_of(ai: int, size: int):
        a = acc[ai]
        if "sparse" in a or "bufferView" not in a:
            raise GlbError("sparse 접근자·bufferView 없는 접근자는 받지 않음")
        v = views[a["bufferView"]]
        start = v.get("byteOffset", 0) + a.get("byteOffset", 0)
        stride = v.get("byteStride", size)
        n = a["count"]
        if n and start + stride * (n - 1) + size > min(v.get("byteOffset", 0) + v["byteLength"], len(binary)):
            raise GlbError("접근자가 버퍼 밖으로 나감")
        return a, start, stride, n

    pos: list[tuple[float, float, float]] = []
    tris = 0
    try:
        for mesh in g.get("meshes") or []:
            for p in mesh.get("primitives") or []:
                if p.get("mode", 4) != 4:
                    raise GlbError("삼각형(mode 4)이 아닌 프리미티브")
                a, start, stride, n = view_of(p["attributes"]["POSITION"], 12)
                if a.get("componentType") != 5126 or a.get("type") != "VEC3":
                    raise GlbError("POSITION은 float VEC3여야 함")
                pos.extend(struct.unpack_from("<3f", binary, start + i * stride) for i in range(n))
                if "indices" in p:
                    ct = acc[p["indices"]].get("componentType")
                    size = {5121: 1, 5123: 2, 5125: 4}.get(ct)
                    if size is None:
                        raise GlbError(f"indices componentType {ct}는 받지 않음")
                    _, istart, istride, icount = view_of(p["indices"], size)
                    fmt = {1: "<B", 2: "<H", 4: "<I"}[size]
                    idx = [struct.unpack_from(fmt, binary, istart + i * istride)[0] for i in range(icount)]
                else:
                    idx = list(range(n))
                if len(idx) % 3 or any(i >= n for i in idx):
                    raise GlbError("삼각형 번호가 잘못됨")
                tris += len(idx) // 3
    except (KeyError, IndexError, TypeError, struct.error) as exc:
        raise GlbError(f"GLB 구조를 읽지 못함: {type(exc).__name__}: {exc}") from exc
    if not tris:
        raise GlbError("삼각형이 없음")
    return pos, tris


def bare_sha(h) -> str | None:
    """'sha256:ABC…' 또는 'abc…' → 'abc…'(소문자). 문자열이 아니면 None."""
    if not isinstance(h, str):
        return None
    h = h.strip().lower()
    return h[7:] if h.startswith("sha256:") else h


def source_key(spec: dict) -> str | None:
    """조회 키: 확정 텍스트의 sha256(spec meta.sourceTextHash)."""
    return bare_sha((spec.get("meta") or {}).get("sourceTextHash"))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def _is_hex64(v) -> bool:
    return isinstance(v, str) and len(v) == 64 and all(c in "0123456789abcdef" for c in v.lower())


def _rej(asset_id, status, reason: str, sidecar: Path | None, detail: str | None = None) -> dict:
    out = {"assetId": asset_id if isinstance(asset_id, str) else None, "status": status if isinstance(status, str) else None,
           "reason": reason, "sidecar": sidecar.name if sidecar else None}
    if detail:
        out["detail"] = detail[:300]
    return out


def public_asset(a: dict) -> dict:
    """후보·기록에 남기는 자산 정보(로컬 절대 경로는 넣지 않음)."""
    return {k: copy.deepcopy(a[k]) for k in ("assetId", "glb", "glbSha256", "sidecarSha256", "pipeline", "seed", "models",
                                             "promptText", "lexiconVersion", "covariates", "normalization", "gate")}


def check_sidecar(path: Path, data: dict) -> tuple[dict | None, dict | None]:
    """사이드카 하나 → (쓸 수 있는 자산, None) 또는 (None, 거부 기록). 자산에는 '_glbPath'·'_sidecarPath'(기록에 쓰지 않음)."""
    aid, status = data.get("assetId"), data.get("status")
    if not isinstance(aid, str) or not aid.strip():
        return None, _rej(aid, status, R_INVALID, path, "assetId 없음")
    if status == "blocked":
        return None, _rej(aid, status, R_BLOCKED, path, data.get("blockReason") if isinstance(data.get("blockReason"), str) else None)
    if status == "failed":
        return None, _rej(aid, status, R_FAILED, path, data.get("blockReason") if isinstance(data.get("blockReason"), str) else None)
    if status != "ok":
        return None, _rej(aid, status, R_INVALID, path, f"status {status!r}")
    gate = data.get("gate")
    if not isinstance(gate, dict) or gate.get("passed") is not True:
        return None, _rej(aid, status, R_GATE, path)
    norm = data.get("normalization")
    if not isinstance(norm, dict) or norm.get("pivot") != "bottom-center" or not isinstance(norm.get("longestEdge"), (int, float)) \
            or abs(float(norm["longestEdge"]) - 1.0) > 1e-6:
        return None, _rej(aid, status, R_INVALID, path, "normalization은 longestEdge 1.0·pivot bottom-center여야 함")
    glb, want = data.get("glb"), bare_sha(data.get("glbSha256"))
    if not isinstance(glb, str) or not glb or os.path.isabs(glb) or ".." in Path(glb).parts:
        return None, _rej(aid, status, R_INVALID, path, "glb는 사이드카 기준 상대 파일 이름")
    if not _is_hex64(want):
        return None, _rej(aid, status, R_INVALID, path, "glbSha256은 16진 64자")
    prompt = data.get("prompt") if isinstance(data.get("prompt"), dict) else {}
    seed = data.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        return None, _rej(aid, status, R_INVALID, path, "seed는 정수")
    gp = path.parent / glb
    if not gp.is_file():
        return None, _rej(aid, status, R_GLB_MISSING, path)
    raw = gp.read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != want:
        return None, _rej(aid, status, R_GLB_SHA, path, f"사이드카 {want[:12]}…, 파일 {got[:12]}…")
    try:
        read_glb_positions(raw)          # 미리보기·러너가 읽을 수 있는 GLB만 후보로(못 읽으면 절차 메시 모습으로 보이게 됨)
    except GlbError as exc:
        return None, _rej(aid, status, R_GLB_UNREADABLE, path, str(exc))
    asset = {
        "assetId": aid, "glb": Path(glb).name, "glbSha256": want,
        "sidecarSha256": file_sha256(path),
        "pipeline": data.get("pipeline") if isinstance(data.get("pipeline"), str) else None,
        "seed": seed,
        "models": copy.deepcopy(data.get("models")) if isinstance(data.get("models"), list) else [],
        "promptText": prompt.get("text") if isinstance(prompt.get("text"), str) else None,
        "lexiconVersion": prompt.get("lexiconVersion") if isinstance(prompt.get("lexiconVersion"), str) else None,
        "covariates": copy.deepcopy(data.get("covariates")) if isinstance(data.get("covariates"), dict) else None,
        "normalization": {"longestEdge": float(norm["longestEdge"]), "pivot": norm["pivot"]},
        "gate": copy.deepcopy(gate),
        "_glbPath": gp, "_sidecarPath": path,
        # G62-i 기본 판정용(기록에는 defaultFormBasis.words로만 남김): 사이드카 prompt.tokens 가운데 형태 낱말
        "_formWords": [t for t in (prompt.get("tokens") or []) if isinstance(t, dict) and t.get("slot") != "template"],
    }
    return asset, None


# ── G62-i: 기본 형태 후보 판정(단순 도형 → 절차, 그 밖의 사물 → 생성) ────────────────
def load_primitive_forms(path: Path | None = None) -> dict:
    """단순 도형 목록 → {file, version, sha256, entries{lexiconKey: entry}}. 형식이 틀리면 ValueError."""
    p = Path(path) if path is not None else shared("lexicon", PRIMITIVE_FORMS_FILE)
    raw = p.read_bytes()
    data = json.loads(raw.decode("utf-8"))
    entries = {}
    for e in data.get("entries") or []:
        key, proc = e.get("lexiconKey"), e.get("procedural") or {}
        if not isinstance(key, str) or proc.get("check") not in ("form.type", "form.base", "shape") \
                or not isinstance(proc.get("value"), str):
            raise ValueError(f"{p.name}: 항목 형식이 틀림: {e!r}")
        if proc["check"] == "shape" and proc["value"] not in SHAPE_MODEL_VALUES:
            raise ValueError(f"{p.name}: 모형이 없는 모양 값은 단순 도형이 아님: {e!r}")
        entries[key] = e
    if not isinstance(data.get("lexiconVersion"), str) or not entries:
        raise ValueError(f"{p.name}: lexiconVersion·entries가 필요함")
    return {"file": p.name, "version": data["lexiconVersion"], "sha256": hashlib.sha256(raw).hexdigest(),
            "entries": entries}


def _overlaps(span, other) -> bool:
    return (isinstance(other, (list, tuple)) and len(other) == 2 and isinstance(span, (list, tuple))
            and other[0] < span[1] and span[0] < other[1])


def _prov_spans(spec: dict, slot: str) -> list:
    items = (spec.get("_provenance") or {}).get(slot) or []
    if isinstance(items, dict):
        items = [items]
    return [it.get("charSpan") for it in items if isinstance(it, dict)]


def procedural_draws(spec: dict, proc: dict, span) -> bool:
    """절차 사전이 그 낱말(span)을 proc 형상으로 옮겼고 렌더러가 그 형상을 그리는가(docs/shape-mapping.md 규칙 1·2·4·9).
    - form.type: spec form.type = 값, 그 근거가 span과 겹침, 기본 형상(form.base)이 없음(있으면 기본 형상이 그려짐).
    - form.base: spec form.base = 값(변형값 포함), 근거가 span과 겹침, form.type이 null·blob(기본 형상이 그려짐).
    - shape: 그 span의 모양어가 값이고, form.type null·blob·form.base 없음, 표 모양어 가운데 처음 나온 것(충돌 아님).
      form.base가 그려지면 그 모양어가 기본 형상 변형값(form.baseVariant)의 근거로 쓰였을 때만."""
    ftype, fbase = slot_value(spec, "form.type"), slot_value(spec, "form.base")
    check, value = proc["check"], proc["value"]
    if check == "form.type":
        return ftype == value and fbase is None and any(_overlaps(span, s) for s in _prov_spans(spec, "form.type"))
    if check == "form.base":
        variant = slot_value(spec, "form.baseVariant") or {}
        return (fbase == value and ftype in TYPES_DRAWING_SHAPE_OR_BASE
                and all(variant.get(k) == v for k, v in (proc.get("variant") or {}).items())
                and any(_overlaps(span, s) for s in _prov_spans(spec, "form.base")))
    # shape
    if ftype not in TYPES_DRAWING_SHAPE_OR_BASE:
        return False
    if fbase is not None:
        # 기본 형상이 그려지면 모양 모형은 쓰지 않는다(규칙 9). 그 모양어가 기본 형상의 변형값 단서로 쓰였을 때만('네모난 상자' → 네모 단면)
        return any(_overlaps(span, s) for s in _prov_spans(spec, "form.baseVariant"))
    words = sorted(shape_words(spec), key=lambda u: tuple(((u.get("_provenance") or {}).get("charSpan") or [0, 0])[:2]))
    table = [u for u in words if (u.get("value") or {}).get("shape") in SHAPE_MODEL_VALUES]
    if not table or (table[0].get("value") or {}).get("shape") != value:
        return False
    return any((u.get("value") or {}).get("shape") == value and _overlaps(span, (u.get("_provenance") or {}).get("charSpan"))
               for u in table)


def judge_default_form(offered: list, spec: dict, confirmed_text: str | None, prim: dict) -> dict:
    """[gen3d] default_form_source = auto의 기본 판정(결정 G62-i). 입력: 쓸 수 있는 생성 자산(seed 순), spec, 정규화한 확정 텍스트,
    단순 도형 목록. 형태 낱말 = 사이드카 prompt.tokens 가운데 slot이 template이 아닌 것(중심 명사·비유 원천·꾸밈말). 규칙:
      생성 후보 없음 → no_generated_candidate(절차). 확정 텍스트가 없거나 해시가 다르거나 낱말 글자가 charSpan과 다름
      → form_words_untraceable(절차). 형태 낱말 없음 → no_form_words(절차). 모두 단순 도형이고 절차 메시가 그 문장에서 그대로
      그림 → primitive_stated(절차). 하나라도 아님(섞인 경우 포함) → non_primitive_stated(생성).
    같은 입력 → 같은 출력(난수·시각 없음)."""
    basis = {"listFile": prim["file"], "listVersion": prim["version"], "listSha256": prim["sha256"],
             "assetIds": [a["assetId"] for a in offered], "words": []}

    def done(rule: str, source: str) -> dict:
        basis.update(rule=rule, source=source)
        return basis

    if not offered:
        return done(RULE_NO_GENERATED, DEFAULT_PROCEDURAL)
    seen, words = set(), []
    for a in offered:                         # 같은 확정 텍스트의 사이드카는 보통 같은 낱말 — 겹치면 한 번만
        for t in a.get("_formWords") or []:
            k = (t.get("lexiconKey"), t.get("ko"), tuple(t.get("charSpan") or ()))
            if k not in seen:
                seen.add(k)
                words.append(t)
    words.sort(key=lambda t: tuple(t.get("charSpan") or (0, 0)))
    text_ok = isinstance(confirmed_text, str) and hashlib.sha256(confirmed_text.encode("utf-8")).hexdigest() == source_key(spec)
    untraceable = False
    for t in words:
        span, ko, key = t.get("charSpan"), t.get("ko"), t.get("lexiconKey")
        traced = (text_ok and isinstance(ko, str) and isinstance(span, list) and len(span) == 2
                  and all(isinstance(x, int) for x in span) and 0 <= span[0] < span[1] <= len(confirmed_text)
                  and confirmed_text[span[0]:span[1]] == ko)
        entry = prim["entries"].get(key) if isinstance(key, str) else None
        if not traced:
            reason, primitive = "untraceable", False
            untraceable = True
        elif entry is None:
            reason, primitive = "not_listed", False
        elif not procedural_draws(spec, entry["procedural"], span):
            reason, primitive = "procedural_not_drawn", False
        else:
            reason, primitive = "listed_and_drawn", True
        basis["words"].append({"ko": ko if isinstance(ko, str) else None, "charSpan": span if traced else None,
                               "lexiconKey": key if isinstance(key, str) else None,
                               "slot": t.get("slot") if isinstance(t.get("slot"), str) else None,
                               "primitive": primitive, "reason": reason,
                               "procedural": copy.deepcopy(entry["procedural"]) if entry is not None else None})
    if not text_ok or untraceable:
        return done(RULE_UNTRACEABLE, DEFAULT_PROCEDURAL)
    if not words:
        return done(RULE_NO_FORM_WORDS, DEFAULT_PROCEDURAL)
    if all(w["primitive"] for w in basis["words"]):
        return done(RULE_PRIMITIVE, DEFAULT_PROCEDURAL)
    return done(RULE_NON_PRIMITIVE, DEFAULT_GENERATED)


class FormAssetStore:
    """자산 폴더 하나. lookup(키)은 부를 때마다 폴더를 다시 읽는다(세션의 후보 단계에서 한 번)."""

    def __init__(self, root: Path, max_candidates: int = 2, default_form_source: str = DEFAULT_PROCEDURAL):
        if default_form_source not in DEFAULT_SOURCES:
            raise ValueError(f"[gen3d] default_form_source는 {' | '.join(DEFAULT_SOURCES)}: {default_form_source!r}")
        self.root = Path(root)
        self.max_candidates = max(0, int(max_candidates))
        self.default_form_source = default_form_source
        # auto일 때만 단순 도형 목록을 읽는다(없거나 깨졌으면 시작 시 오류 — 조용히 다른 규칙으로 돌지 않음)
        self.primitive_forms = load_primitive_forms() if default_form_source == DEFAULT_AUTO else None

    def info(self) -> dict:
        out = {"enabled": True, "version": FORM_ASSETS_VERSION, "assetsDirExists": self.root.is_dir(),
               "maxCandidates": self.max_candidates, "defaultFormSource": self.default_form_source}
        if self.primitive_forms is not None:
            out["primitiveForms"] = {k: self.primitive_forms[k] for k in ("file", "version", "sha256")}
        return out

    def judge_default(self, lookup: dict, spec: dict, confirmed_text: str | None) -> dict | None:
        """auto 설정의 기본 판정(judge_default_form). auto가 아니면 None."""
        if self.primitive_forms is None:
            return None
        return judge_default_form(lookup["offered"], spec, confirmed_text, self.primitive_forms)

    def _sidecars(self):
        """(경로, dict) — schema에 SIDECAR_MARK가 든 JSON만. 경로 순서로(결정적)."""
        if not self.root.is_dir():
            return
        paths = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames.sort()
            paths.extend(Path(dirpath) / f for f in sorted(filenames) if f.lower().endswith(".json"))
        for p in paths:
            try:
                if p.stat().st_size > MAX_SIDECAR_BYTES:
                    continue
                data = json.loads(p.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if isinstance(data, dict) and isinstance(data.get("schema"), str) and SIDECAR_MARK in data["schema"]:
                yield p, data

    def lookup(self, key: str | None) -> dict:
        """키(확정 텍스트 sha256)에 맞는 사이드카 → {key, offered[자산], rejected[{assetId,status,reason,sidecar}]}."""
        key = bare_sha(key)
        ok, rejected = [], []
        if key:
            for p, data in self._sidecars():
                if bare_sha(data.get("sourceTextSha256")) != key:
                    continue
                a, r = check_sidecar(p, data)
                if a is not None:
                    ok.append(a)
                else:
                    rejected.append(r)
        ok.sort(key=lambda a: (a["seed"], a["assetId"], a["glbSha256"]))
        seen, uniq = set(), []
        for a in ok:                                   # 같은 GLB(같은 sha256)는 한 번만
            if a["glbSha256"] in seen:
                continue
            seen.add(a["glbSha256"])
            uniq.append(a)
        offered = uniq[:self.max_candidates]
        for a in uniq[self.max_candidates:]:
            rejected.append(_rej(a["assetId"], "ok", R_OVER_LIMIT, a["_sidecarPath"]))
        return {"key": key, "offered": offered, "rejected": rejected}

    def lookup_for_spec(self, spec: dict) -> dict:
        """spec의 확정 텍스트 키로 찾고, 생성 메시를 쓰지 않는 spec이면 모두 rejected로 옮긴다
        (G50 넷째 범주 — 형태 후보를 내지 않음, 말한 안개·불꽃 — 메시로 만들지 않음)."""
        res = self.lookup(source_key(spec))
        why = None
        if form_blocks(spec):
            why = R_FORM_BLOCKED
        elif slot_value(spec, "form.type") in NO_MESH_FORM_TYPES or slot_value(spec, "form.base") in NO_MESH_BASES:
            why = R_NO_MESH_FORM
        if why is not None and res["offered"]:
            res["rejected"] = [_rej(a["assetId"], "ok", why, a["_sidecarPath"]) for a in res["offered"]] + res["rejected"]
            res["offered"] = []
        return res


def generated_candidate_id(spec_sha: str, asset: dict) -> str:
    return "g-" + sha256_text(f"{GENERATOR_VERSION}|{FORM_ASSETS_VERSION}|{spec_sha}|{asset['assetId']}|{asset['glbSha256']}")[:12]


def add_generated(cands: dict, lookup: dict, session_id: str, limit: int,
                  default_form_source: str = DEFAULT_PROCEDURAL, basis: dict | None = None) -> dict:
    """절차 후보 묶음(candidates.generate 출력)에 생성 후보를 더한 새 묶음. lookup = FormAssetStore.lookup_for_spec 결과.
    생성 후보가 없어도 candidates.generation(조회 기록: 키·거부 사유·기본 형태 후보)을 더한다.
    default_form_source = "generated"이고 생성 후보가 있으면 첫 생성 후보(seed 순 첫째)가 기본: 화면 맨 앞에 두고(나머지는 같은
    순환 순서) 미리 선택한다. "procedural"이면 지금처럼 전체를 순환하고 미리 선택하지 않는다(defaultCandidateId = null).
    "auto"(G62-i)면 basis(judge_default_form 결과)의 source가 그 세션의 generated | procedural을 정하고, 그 뒤는 위와 같다.
    판정 근거(규칙·낱말·charSpan)는 generation.defaultFormRule·defaultFormBasis에 남는다."""
    if default_form_source == DEFAULT_AUTO:
        if basis is None:
            raise ValueError("default_form_source = auto에는 판정(basis)이 필요함")
        effective, rule = basis["source"], basis["rule"]
    else:
        effective = default_form_source
        rule = RULE_SETTING_GENERATED if default_form_source == DEFAULT_GENERATED else RULE_SETTING_PROCEDURAL
        basis = None
    out = copy.deepcopy(cands)
    base = out["candidates"][0]                     # 0번 후보 = 덮어쓰기 없음(후보 단계가 없었다면 그려졌을 형상)
    start = out["distinct"]["gridCount"]
    gens = []
    for k, a in enumerate(lookup["offered"]):
        sources = dict(base["sources"])
        sources["form.type"] = GENERATED_SOURCE
        gens.append({"id": generated_candidate_id(out["specSha256"], a), "index": start + k,
                     "overrides": dict(base["overrides"]), "axisValues": {}, "sources": sources,
                     "origin": "generated", "asset": public_asset(a)})
    procedural_step = out["selectionStep"]
    default_id = gens[0]["id"] if effective == DEFAULT_GENERATED and gens else None
    if gens:
        out["candidates"] = out["candidates"] + gens
        n = len(out["candidates"])
        off = _display_offset(session_id, n)
        order = [out["candidates"][(k + off) % n]["id"] for k in range(n)]
        if default_id is not None:
            order = [default_id] + [c for c in order if c != default_id]
            out["orderRule"] = (f"기본(생성 후보 {default_id})을 맨 앞에, 나머지는 sha256(sessionId)[:8] mod {n} = {off} 만큼 "
                                "순환한 순서(절차 후보 + 생성 후보)")
        else:
            out["orderRule"] = f"sha256(sessionId)[:8] mod {n} = {off} 만큼 순환(절차 후보 + 생성 후보)"
        out["displayOrder"] = order
        out["selectionStep"] = "choose"
        out["note"] += (f" 생성 형태 후보 {len(gens)}개를 더함(G62, 고른 경우에만 장면에 씀)"
                        + (" — 생성 후보가 있어 선택 단계를 건너뛰지 않음." if procedural_step == "skip" else ".")
                        + (" 생성 후보가 기본(맨 앞·미리 선택, 확정해야 씀)." if default_id else "")
                        + (" 말한 형태 낱말이 모두 단순 도형이라 절차 메시가 기본(G62-i)." if rule == RULE_PRIMITIVE else ""))
    used = DEFAULT_GENERATED if default_id is not None else DEFAULT_PROCEDURAL
    out["generation"] = {
        "version": FORM_ASSETS_VERSION, "lookupKey": lookup["key"], "limit": limit,
        "offered": [{"candidateId": g["id"], "assetId": g["asset"]["assetId"]} for g in gens],
        "rejected": copy.deepcopy(lookup["rejected"]),
        "proceduralSelectionStep": procedural_step,
        "defaultFormSourceSetting": default_form_source,
        "defaultFormSource": used,
        "defaultCandidateId": default_id,
        # 생성 기본 설정인데 절차 메시가 기본이 된 이유(차단·실패·관문 탈락 등 자세한 것은 rejected)
        "defaultFallbackReason": NO_GENERATED_CANDIDATE if effective == DEFAULT_GENERATED and default_id is None else None,
        # G62-i: 기본이 왜 그렇게 정해졌는가(설정 고정 | auto 판정)와 auto 판정 근거(고정 설정이면 null)
        "defaultFormRule": rule,
        "defaultFormBasis": copy.deepcopy(basis),
    }
    return out
