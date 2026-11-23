"""SceneSpec v2 형식 — 슬롯 경로, 스키마 검증, 원칙 검사.

형식 자체는 shared/schemas/scene-spec.v2.json이 정한다. 이 모듈은 그 형식을 코드에서 쓰기 위한 도우미다.
- validate(spec): JSON Schema 검사. 스키마의 if/then 규칙이 원칙 3·4(말하지 않은 값은 null,
  값이 있으면 _provenance가 있다)를 이미 강제한다.
- check_principles(spec, text): 스키마로 못 보는 것 — 근거(trigger)가 정말 확정 텍스트의 그 구간인지,
  sourceTextHash가 그 텍스트의 해시인지 — 를 확인한다.
만드는 쪽은 scene_builder.py.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache

from .paths import shared

SPEC_VERSION = "2.0.0"
SCHEMA_FILE = "scene-spec.v2.json"
SPEC_VERSION_V21 = "2.1.0"                 # 개선 매핑 v1 출력(상위 호환 확장)
SCHEMA_FILE_V21 = "scene-spec.v2.1.json"
SPEC_VERSION_V22 = "2.2.0"                 # 기본 형상 경로(form.base·form.baseVariant, 결정 G21·G30). 매핑 v2만 쓴다
SCHEMA_FILE_V22 = "scene-spec.v2.2.json"
# 2.2.0에서 더한 슬롯. SLOT_PATHS(2.0 슬롯)에는 넣지 않는다 — 그 목록을 쓰는 v0·v1·평가 코드의 출력이 바뀌지 않게
BASE_SLOT_PATHS: tuple[str, ...] = ("form.base", "form.baseVariant")
BASE_SHAPES: tuple[str, ...] = ("container", "line", "sheet", "flame", "drop")
V21_FIELDS: tuple[str, ...] = ("_context", "_parts", "_uncertain", "_measurements", "_direction",
                               "_needsConfirmation", "_clauses")
SLOT_PATHS: tuple[str, ...] = (
    "form.type", "form.posture",
    "material.color", "material.brightness", "material.saturation", "material.roughness", "material.opacity",
    "material.erosion",
    "layout.size", "layout.distance", "layout.verticalOffset",
    "motion.type", "motion.speed",
    "body.part", "body.layer",
)
GROUPS: tuple[str, ...] = ("form", "material", "layout", "motion", "body")
TOP_KEYS: tuple[str, ...] = ("meta", *GROUPS, "_provenance", "_unmatched", "_unmapped", "_negated", "_alternatives",
                             "_inferred")


def text_hash(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


# 스키마 2.1의 meta.mapping.used는 v0 | v1만 허용한다. 매핑 v2(scene_builder_v2.py)는 스키마를 바꾸지 않고
# requested = "v2", used = "v1"로 적는다(v2는 v1 위의 수정). 요청 매핑별 정상 used 값.
MAPPING_USED_FOR: dict[str, str] = {"v2": "v1"}


def is_mapping_fallback(mp) -> bool:
    """spec.meta.mapping이 '요청한 매핑 대신 v0로 대체됨'을 뜻하는가. v0·v1에서는 기존 판정
    (used ≠ requested 또는 fallbackReason 있음)과 같다. v2는 used = "v1"이 정상 값이다."""
    if not isinstance(mp, dict):
        return False
    req = mp.get("requested")
    return mp.get("used") != MAPPING_USED_FOR.get(req, req) or bool(mp.get("fallbackReason"))


_SCHEMA_FILES = {SPEC_VERSION_V21: SCHEMA_FILE_V21, SPEC_VERSION_V22: SCHEMA_FILE_V22}


@lru_cache(maxsize=4)
def schema(version: str = SPEC_VERSION) -> dict:
    name = _SCHEMA_FILES.get(version, SCHEMA_FILE)
    return json.loads(shared("schemas", name).read_text(encoding="utf-8"))


@lru_cache(maxsize=4)
def _validator(version: str = SPEC_VERSION):
    from jsonschema import Draft202012Validator
    return Draft202012Validator(schema(version))


def schema_errors(spec: dict) -> list[str]:
    """스키마 위반 목록(없으면 빈 목록). meta.specVersion이 2.1.0이면 v2.1 스키마, 2.2.0이면 v2.2 스키마, 아니면 v2.0 스키마로 검사한다."""
    sv = (spec.get("meta") or {}).get("specVersion")
    version = sv if sv in _SCHEMA_FILES else SPEC_VERSION
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
            for e in sorted(_validator(version).iter_errors(spec), key=lambda e: list(map(str, e.absolute_path)))]


def get_slot(spec: dict, path: str):
    group, key = path.split(".")
    return spec[group][key]


def _all_provenance(spec: dict):
    for path, provs in spec.get("_provenance", {}).items():
        for p in provs:
            yield f"_provenance.{path}", p
    for i, alt in enumerate(spec.get("_alternatives", [])):
        for p in alt["_provenance"]:
            yield f"_alternatives[{i}]", p
    for name in ("_unmapped", "_negated"):
        for i, item in enumerate(spec.get(name, [])):
            yield f"{name}[{i}]", item["_provenance"]
    for path, inf in spec.get("_inferred", {}).items():
        for p in inf["_provenance"]:
            yield f"_inferred.{path}", p


def check_principles(spec: dict, text: str) -> list[str]:
    """원칙 3·4 위반 목록. text는 확정 텍스트(정규화된 것)."""
    problems = schema_errors(spec)
    if spec.get("meta", {}).get("sourceTextHash") != text_hash(text):
        problems.append("meta.sourceTextHash가 확정 텍스트의 해시와 다르다")
    for path in SLOT_PATHS + BASE_SLOT_PATHS:  # 스키마와 같은 규칙을 코드로도 확인(스키마를 고칠 때 안전망). 2.2 슬롯은 없으면 건너뜀
        try:
            value = get_slot(spec, path)
        except (KeyError, TypeError):
            continue
        if path in BASE_SLOT_PATHS and (spec.get("meta") or {}).get("specVersion") != SPEC_VERSION_V22:
            problems.append(f"{path}: specVersion {(spec.get('meta') or {}).get('specVersion')} 문서에는 없어야 한다(2.2.0 전용)")
        has_prov = path in spec.get("_provenance", {})
        if value is None and has_prov:
            problems.append(f"{path}: 값이 null인데 _provenance가 있다")
        if value is not None and not has_prov:
            problems.append(f"{path}: 값이 있는데 _provenance가 없다(원칙 4)")
        if value is not None and path in spec.get("_inferred", {}):
            problems.append(f"{path}: 값이 있는데 _inferred도 있다")
        if value is not None and any(p.get("source") == "fuzzy_lexicon" or p.get("needsConfirmation")
                                     for p in spec.get("_provenance", {}).get(path) or []):
            problems.append(f"{path}: 퍼지 일치(확인 필요) 근거로 값을 만들었다(원칙 2)")
    for where, p in _all_provenance(spec):
        s, e = p["charSpan"]
        if text[s:e] != p["trigger"]:
            problems.append(f"{where}: trigger '{p['trigger']}'가 확정 텍스트 [{s},{e}) '{text[s:e]}'와 다르다")
    for i, u in enumerate(spec.get("_unmatched", [])):
        s, e = u["charSpan"]
        if text[s:e] != u["surface"]:
            problems.append(f"_unmatched[{i}]: surface '{u['surface']}'가 확정 텍스트 [{s},{e})와 다르다")
    for name in V21_FIELDS:                       # v2.1 보존 필드: 원문 그대로(구간 포함)여야 한다
        for i, item in enumerate(spec.get(name) or []):
            s, e = item["charSpan"]
            got = item.get("text", item.get("trigger"))
            if text[s:e] != got:
                problems.append(f"{name}[{i}]: '{got}'가 확정 텍스트 [{s},{e}) '{text[s:e]}'와 다르다")
    return problems
