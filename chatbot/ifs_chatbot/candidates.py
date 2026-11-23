"""후보 생성기 (D3, 결정 G14–G20, G31·G32·G34). 확정 텍스트로 만든 SceneSpec 하나에서 형상 후보 여러 개를 만든다.

- 후보 하나 = "원본 spec + 덮어쓰기 목록". 덮어쓰기는 Unity SceneOverrideJson이 받는 평평한 객체
  ({"form.type": "mist", "layout.size": 0.7}). 원본 spec은 바꾸지 않는다(G14).
- 후보끼리 다른 것은 말하지 않아 비어 있던 자리(값이 null인 슬롯)와, 닫힌 표에 등록된 낱말 해석 갈림뿐이다(G9·G18).
  말한 슬롯은 어떤 후보에서도 바뀌지 않는다.
- 규칙(G16·G34): 빈 자리 가운데 우선순위(형태 > 크기 > 투명도 > 질감 > 움직임) 위 두 차원으로 2×2.
  빈 자리가 한 차원뿐이면 그 차원의 표 값만큼(최대 4), 없으면 후보 1개. 갈림 축이 있으면 빈 차원보다 먼저(G18).
  색상(hue, G17·G31)과 밝기(G34)는 벌리지 않는다. 0번 후보는 언제나 "후보 단계가 없었다면 그려졌을 형상"(덮어쓰기 없음).
- 모양어(G32, G29 대체): 모형이 있는 모양어(표 shapeModels.mapped — Unity ShapeMapping과 같음)를 말했으면 형태 자리는
  말한 자리로 고정한다. 모형이 없는 모양어만 말했으면 형태 자리를 벌린다(축 reason said_unrendered, 말한 낱말은 축에 남김).
- 구별 규칙(G34, 표 distinctness): 덮어쓰기를 얹은 최종 값에서 화면에 보이지 않는 키(정지 미리보기의 움직임 등)를 뺀
  "보이는 값"이 같은 후보는 index가 작은 것 하나만 남긴다. 남은 후보가 하나면 selectionStep = "skip"(선택 단계 없이 조절로).
- 화면 순서는 sessionId 해시로 순환시킨다(G20). 후보 내용은 sessionId와 무관하고 순서만 바뀐다.
- LLM·난수·시각을 쓰지 않는다. 같은 spec(정규화 해시)·같은 sessionId → 바이트까지 같은 출력(원칙 1).
"""
from __future__ import annotations

import copy
import hashlib
import json
from functools import lru_cache
from pathlib import Path

from .paths import shared

GENERATOR_VERSION = "ifs-candidates/0.2.0"   # 0.2.0(2026-11-23): G32 모형 없는 모양어, G34 밝기 제외·구별 규칙·선택 건너뜀
TABLE_FILE = "candidate_values.v1.json"
MAX_CANDIDATES = 4          # 지시문 6절 임시값(⚠ 사람이 정할 것). G19에서 상한

# spec 슬롯(경로) — 출처 표의 행 순서
SLOTS = (
    "form.type", "form.posture",
    "material.color", "material.brightness", "material.saturation", "material.roughness",
    "material.opacity", "material.erosion",
    "layout.size", "layout.distance", "layout.verticalOffset",
    "motion.type", "motion.speed",
    "body.part", "body.layer",
)
# spec 수치 슬롯 → SceneParams 키(SceneParams.FromSpec과 같은 대응)
_NUM_SLOT_KEY = {
    "material.brightness": "material.brightness", "material.roughness": "material.roughness",
    "material.opacity": "material.opacity", "material.erosion": "material.erosion",
    "layout.size": "layout.size", "layout.distance": "layout.distance",
    "layout.verticalOffset": "layout.verticalOffset", "motion.speed": "motion.speed",
}


def canonical(obj) -> str:
    """해시·바이트 비교용 JSON(키 정렬, 공백 없음, 한글 그대로)."""
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── 값 표 ────────────────────────────────────────────────────────────────────
@lru_cache(maxsize=4)
def _load_table(path: str) -> tuple[dict, str]:
    raw = Path(path).read_text(encoding="utf-8")
    return json.loads(raw), sha256_text(raw)


def load_table(path: str | Path | None = None) -> dict:
    """값 표(dict 사본)와 그 파일 해시를 '_sha256'에 담아 돌려준다."""
    p = Path(path) if path else shared("lexicon", TABLE_FILE)
    data, sha = _load_table(str(p))
    out = copy.deepcopy(data)
    out["_sha256"] = sha
    out["_file"] = p.name
    return out


# ── spec 읽기 ────────────────────────────────────────────────────────────────
def slot_value(spec: dict, slot: str):
    group, name = slot.split(".", 1)
    return (spec.get(group) or {}).get(name)


def shape_words(spec: dict) -> list[dict]:
    """매퍼가 _unmapped(category shape)에 남긴 모양어. Unity ShapeMapping이 읽는 것과 같은 목록."""
    return [u for u in spec.get("_unmapped") or [] if u.get("category") == "shape"]


def _mapped_shapes(table: dict | None) -> set[str] | None:
    """표의 모형 있는 모양 값. 표에 shapeModels가 없으면(0.1.0 표) None = 모든 모양어를 '모형 있음'으로 본다(G29 때 동작)."""
    t = table if table is not None else load_table()
    sm = t.get("shapeModels")
    return None if sm is None else set(sm["mapped"])


def rendered_shape_words(spec: dict, table: dict | None = None) -> list[dict]:
    """모형이 있는 모양어(value.shape가 shapeModels.mapped에 있음). 하나라도 있으면 Unity가 그 모형을 그린다(form.type이 null·blob일 때)."""
    mapped = _mapped_shapes(table)
    return [u for u in shape_words(spec) if mapped is None or (u.get("value") or {}).get("shape") in mapped]


def unrendered_shape_words(spec: dict, table: dict | None = None) -> list[dict]:
    """모형이 없는 모양어(G32). 말했지만 그릴 모형이 없어 기본 형태로 그려진다."""
    mapped = _mapped_shapes(table)
    return [u for u in shape_words(spec) if mapped is not None and (u.get("value") or {}).get("shape") not in mapped]


def said_words(words: list[dict]) -> list[dict]:
    """기록용 모양어 요약(원래 말한 낱말이 기록에 남게): lemma·shape·trigger·charSpan, charSpan 순서."""
    out = [{"lemma": u.get("lemma"), "shape": (u.get("value") or {}).get("shape"),
            "trigger": (u.get("_provenance") or {}).get("trigger"),
            "charSpan": list((u.get("_provenance") or {}).get("charSpan") or [])} for u in words]
    return sorted(out, key=lambda w: (w["charSpan"][:1] or [10 ** 9], w["lemma"] or ""))


def form_said_unrendered(spec: dict, table: dict | None = None) -> bool:
    """G32: form.type을 말하지 않았고, 모형이 없는 모양어만 말했다(모형이 있는 모양어는 없음)."""
    return (slot_value(spec, "form.type") is None and not rendered_shape_words(spec, table)
            and bool(unrendered_shape_words(spec, table)))


def slot_is_open(spec: dict, slot: str, table: dict | None = None) -> bool:
    """후보가 벌릴 수 있는 빈 자리인가. 값이 null이어야 하고, 형태는 모형이 있는 모양어도 없어야 한다
    (모형이 있는 모양어를 말했으면 형태를 말한 것으로 본다 — form.type을 mist 등으로 바꾸면 말한 모양이 그려지지 않게 됨).
    모형이 없는 모양어만 말했으면 형태 자리는 열린다(G32, G29 대체)."""
    if slot_value(spec, slot) is not None:
        return False
    if slot == "form.type" and rendered_shape_words(spec, table):
        return False
    return True


def normalized_spec(spec: dict) -> dict:
    """후보 결정에 쓰는 spec 사본: 사람·세션을 가리키는 meta(sessionId·participantId·condition)만 뺀다.
    같은 확정 텍스트를 같은 매퍼로 만든 spec은 세션이 달라도 같은 해시가 된다."""
    s = copy.deepcopy(spec)
    meta = dict(s.get("meta") or {})
    for k in ("sessionId", "participantId", "condition"):
        meta.pop(k, None)
    s["meta"] = meta
    return s


def spec_sha256(spec: dict) -> str:
    return sha256_text(canonical(normalized_spec(spec)))


def effective_params(spec: dict, defaults: dict, overrides: dict | None = None) -> dict:
    """SceneParams.FromSpec(useInferred=false)과 같은 규칙으로 렌더에 쓰일 값(SceneParams 키)을 만든 뒤 덮어쓰기를 얹는다."""
    def clamp(v):
        return 0.0 if v < 0 else (1.0 if v > 1 else float(v))

    p: dict = {}
    p["form.type"] = slot_value(spec, "form.type") or defaults["form.type"]
    p["form.posture"] = slot_value(spec, "form.posture") or defaults["form.posture"]
    c = slot_value(spec, "material.color") or {}
    sat = slot_value(spec, "material.saturation")
    p["material.color.h"] = clamp(c["h"] if c.get("h") is not None else defaults["material.color.h"])
    s_val = sat if sat is not None else c.get("s")
    p["material.color.s"] = clamp(s_val if s_val is not None else defaults["material.color.s"])
    p["material.color.l"] = clamp(c["l"] if c.get("l") is not None else defaults["material.color.l"])
    for slot, key in _NUM_SLOT_KEY.items():
        v = slot_value(spec, slot)
        p[key] = clamp(v if v is not None else defaults[key])
    p["motion.type"] = slot_value(spec, "motion.type") or defaults["motion.type"]
    for k, v in (overrides or {}).items():
        p[k] = v
    return p


# ── 생성 ────────────────────────────────────────────────────────────────────
def _split_axis(spec: dict, table: dict) -> tuple[dict | None, list[dict]]:
    """등록된 갈림 가운데 charSpan이 가장 앞선 것 하나. (축, 건너뛴 것 목록)."""
    found, skipped = [], []
    for entry in table["interpretationSplits"]["entries"]:
        m = entry["match"]
        for item in spec.get(m["in"]) or []:
            if item.get("category") != m["category"]:
                continue
            if (item.get("value") or {}).get(m["valueKey"]) != m["value"]:
                continue
            span = ((item.get("_provenance") or {}).get("charSpan")) or [10 ** 9, 10 ** 9]
            hit = {"id": entry["id"], "lemma": item.get("lemma"), "charSpan": list(span), "entry": entry}
            if not slot_is_open(spec, entry["slot"], table):
                skipped.append({"id": entry["id"], "lemma": item.get("lemma"), "slot": entry["slot"],
                                "reason": "대상 슬롯을 말했거나 모형이 있는 모양어가 있음(G9: 말한 슬롯은 바꾸지 않음)"})
                continue
            found.append(hit)
    if not found:
        return None, skipped
    found.sort(key=lambda h: (h["charSpan"][0], h["id"]))
    hit = found[0]
    entry = hit["entry"]
    return ({"slot": entry["slot"], "key": entry["slot"], "reason": "ambiguous", "values": list(entry["readings"]),
             "split": {"id": entry["id"], "lemma": hit["lemma"], "charSpan": hit["charSpan"]}}, skipped)


def _display_offset(session_id: str, n: int) -> int:
    if n <= 1:
        return 0
    return int(sha256_text(session_id or "")[:8], 16) % n


def _num(v):
    return round(float(v), 4) if isinstance(v, (int, float)) and not isinstance(v, bool) else v


def visible_signature(spec: dict, defaults: dict, overrides: dict, table: dict) -> tuple[tuple, list[str]]:
    """G34: 후보 화면에서 보이는 값(compareKeys에서 구별 규칙 ignoreKey가 걸린 키를 뺀 최종 값)과, 뺀 규칙 id 목록.
    표에 distinctness가 없으면(0.1.0 표) 모든 덮어쓰기 키를 본다."""
    dist = table.get("distinctness")
    eff = effective_params(spec, defaults, overrides)
    if dist is None:
        keys = sorted(set(table["overrideKeys"]["numeric"]) | set(table["overrideKeys"]["categorical"]))
        return tuple((k, _num(eff[k])) for k in keys), []
    ignored: dict[str, str] = {}
    for r in dist["rules"]:
        if r["kind"] != "ignoreKey":
            continue
        when = r.get("when") or {}
        if all(eff.get(k) in vals for k, vals in when.items()):
            ignored.setdefault(r["key"], r["id"])
    sig = tuple((k, _num(eff[k])) for k in dist["compareKeys"] if k not in ignored)
    return sig, [ignored[k] for k in dist["compareKeys"] if k in ignored]


def generate(spec: dict, session_id: str, table: dict | None = None) -> dict:
    """spec(dict)과 sessionId로 후보 묶음을 만든다. 출력은 JSON 직렬화 가능한 dict."""
    table = table or load_table()
    defaults = table["defaults"]
    dims = table["candidateAxes"]["dimensions"]
    priority = table["candidateAxes"]["priority"]
    base = effective_params(spec, defaults)
    unrendered = form_said_unrendered(spec, table)
    words = said_words(unrendered_shape_words(spec, table)) if unrendered else []
    rendered = slot_value(spec, "form.type") is None and bool(rendered_shape_words(spec, table))

    split, split_skipped = _split_axis(spec, table)
    open_dims = [d for d in priority if slot_is_open(spec, dims[d]["slot"], table)]
    if split is not None:
        open_dims = [d for d in open_dims if dims[d]["slot"] != split["slot"]]

    def dim_axis(d: str, values: list) -> dict:
        ax = {"slot": dims[d]["slot"], "key": dims[d]["key"], "reason": "empty", "values": list(values)}
        if ax["slot"] == "form.type" and unrendered:
            ax["reason"] = "said_unrendered"      # G32: 모형이 없는 모양어를 말한 형태 자리
            ax["saidWords"] = words
        return ax

    axes: list[dict] = []
    if split is not None:
        if split["slot"] == "form.type" and unrendered:
            split = dict(split, saidWords=words)
        if open_dims:
            axes = [dict(split, values=split["values"][:2]), dim_axis(open_dims[0], dims[open_dims[0]]["pair"])]
        else:
            axes = [dict(split, values=split["values"][:MAX_CANDIDATES])]
    elif len(open_dims) >= 2:
        axes = [dim_axis(d, dims[d]["pair"]) for d in open_dims[:2]]
    elif len(open_dims) == 1:
        axes = [dim_axis(open_dims[0], dims[open_dims[0]]["levels"][:MAX_CANDIDATES])]

    # 격자: 첫 축이 바깥, 둘째 축이 안쪽 → (a0,b0)=0, (a0,b1)=1, (a1,b0)=2, (a1,b1)=3
    combos: list[dict] = [{}]
    for ax in axes:
        combos = [dict(c, **{ax["slot"]: v}) for c in combos for v in ax["values"]]
    combos = combos[:MAX_CANDIDATES]

    s_sha = spec_sha256(spec)
    axis_by_slot = {ax["slot"]: ax for ax in axes}
    grid = []
    for i, combo in enumerate(combos):
        overrides = {}
        for slot, v in combo.items():
            key = axis_by_slot[slot]["key"]
            if base.get(key) != v:
                overrides[key] = _num(v)
        sources = {}
        for slot in SLOTS:
            if slot in combo:
                sources[slot] = "offered"
            elif slot_value(spec, slot) is not None:
                sources[slot] = "said"
            elif slot == "form.type" and rendered:
                sources[slot] = "said"                 # 모형이 있는 모양어: 형태 자리는 말한 자리(G32)
            elif slot == "form.type" and unrendered:
                sources[slot] = "said_unrendered"      # 축이 아닌 경우(지금 규칙에서는 생기지 않음)
            else:
                sources[slot] = "default"
        cid = "c-" + sha256_text(f"{GENERATOR_VERSION}|{s_sha}|{i}")[:12]
        grid.append({"id": cid, "index": i, "overrides": dict(sorted(overrides.items())),
                     "axisValues": {k: _num(v) for k, v in combo.items()}, "sources": sources})

    # G34: 서로 구별되지 않는 후보는 내밀지 않는다(index가 작은 것 하나만 남김. 0번은 언제나 남음)
    kept, removed, seen = [], [], {}
    for c in grid:
        sig, ignored_by = visible_signature(spec, defaults, c["overrides"], table)
        if sig in seen:
            first = seen[sig]
            raw_same = (effective_params(spec, defaults, c["overrides"])
                        == effective_params(spec, defaults, first["overrides"]))
            removed.append({"id": c["id"], "index": c["index"], "sameAs": first["index"],
                            "rules": ["same_final_values"] if raw_same else ignored_by})
            continue
        seen[sig] = c
        kept.append(c)
    candidates = kept
    collapsed = [ax["slot"] for ax in axes if len({c["axisValues"][ax["slot"]] for c in candidates}) <= 1]

    n = len(candidates)
    off = _display_offset(session_id, n)
    display = [candidates[(k + off) % n]["id"] for k in range(n)]
    step = "skip" if n == 1 else "choose"

    if split is not None:
        note = f"낱말 해석 갈림('{split['split']['lemma']}' → {split['slot']})" + \
               (f" × 빈 자리 {axes[1]['slot']}로 2×2" if len(axes) == 2 else f" 한 축으로 {len(grid)}개")
    elif len(axes) == 2:
        note = f"빈 자리 {len(open_dims)}개 가운데 위 두 차원({axes[0]['slot']}, {axes[1]['slot']})으로 2×2"
    elif len(axes) == 1:
        note = f"빈 자리가 한 차원({axes[0]['slot']})뿐이라 그 차원의 표 값 {len(grid)}개"
    else:
        note = "빈 자리가 없어 후보 1개"
    if unrendered:
        note += f". 모형이 없는 모양어({', '.join(w['lemma'] or '?' for w in words)})를 말해 형태 자리를 벌림(G32)"
    if removed:
        note += f". 구별되지 않는 후보 {len(removed)}개를 뺌({', '.join(sorted({r for x in removed for r in x['rules']}))})"
    if step == "skip":
        note += ". 남은 후보가 하나라 선택 단계 없이 조절로(G34)"
    note += ". 색상(hue)·밝기는 벌리지 않음(G17·G31·G34)."

    dist = table.get("distinctness") or {}
    return {
        "generatorVersion": GENERATOR_VERSION,
        "tableVersion": table["tableVersion"],
        "tableSha256": table["_sha256"],
        "specSha256": s_sha,
        "sessionId": session_id,
        "axes": [{k: v for k, v in ax.items() if k != "key"} | {"key": ax["key"]} for ax in axes],
        "candidates": candidates,
        "displayOrder": display,
        "orderRule": f"sha256(sessionId)[:8] mod {n} = {off} 만큼 순환",
        "splitSkipped": split_skipped,
        "distinct": {"ruleVersion": dist.get("ruleVersion"), "gridCount": len(grid), "kept": n,
                     "removed": removed, "collapsedAxes": collapsed},
        "selectionStep": step,
        "note": note,
    }


def candidates_bytes(out: dict) -> bytes:
    """파일로 쓰는 바이트(정렬된 키, 들여쓰기 2, UTF-8). 출력 해시 고정 테스트가 이 바이트를 본다."""
    return (json.dumps(out, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
