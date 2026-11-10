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


@lru_cache(maxsize=1)
def schema() -> dict:
    return json.loads(shared("schemas", SCHEMA_FILE).read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _validator():
    from jsonschema import Draft202012Validator
    return Draft202012Validator(schema())


def schema_errors(spec: dict) -> list[str]:
    """스키마 위반 목록(없으면 빈 목록)."""
    return [f"{'/'.join(map(str, e.absolute_path)) or '(root)'}: {e.message}"
            for e in sorted(_validator().iter_errors(spec), key=lambda e: list(map(str, e.absolute_path)))]


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
    for path in SLOT_PATHS:  # 스키마와 같은 규칙을 코드로도 확인(스키마를 고칠 때 안전망)
        try:
            value = get_slot(spec, path)
        except (KeyError, TypeError):
            continue
        has_prov = path in spec.get("_provenance", {})
        if value is None and has_prov:
            problems.append(f"{path}: 값이 null인데 _provenance가 있다")
        if value is not None and not has_prov:
            problems.append(f"{path}: 값이 있는데 _provenance가 없다(원칙 4)")
        if value is not None and path in spec.get("_inferred", {}):
            problems.append(f"{path}: 값이 있는데 _inferred도 있다")
    for where, p in _all_provenance(spec):
        s, e = p["charSpan"]
        if text[s:e] != p["trigger"]:
            problems.append(f"{where}: trigger '{p['trigger']}'가 확정 텍스트 [{s},{e}) '{text[s:e]}'와 다르다")
    for i, u in enumerate(spec.get("_unmatched", [])):
        s, e = u["charSpan"]
        if text[s:e] != u["surface"]:
            problems.append(f"_unmatched[{i}]: surface '{u['surface']}'가 확정 텍스트 [{s},{e})와 다르다")
    return problems
