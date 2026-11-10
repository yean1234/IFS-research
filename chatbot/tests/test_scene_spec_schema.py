"""1단계 점검: SceneSpec v2 정답 JSON이 스키마를 통과하고 원칙 3·4를 어기지 않는다."""
import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ifs_chatbot.scene_spec import SLOT_PATHS, TOP_KEYS, check_principles, schema, schema_errors

FIXTURES = Path(__file__).parent / "fixtures" / "scene_spec"
CASES = json.loads((FIXTURES / "cases.json").read_text(encoding="utf-8"))["cases"]


def load(case):
    return json.loads((FIXTURES / case["file"]).read_text(encoding="utf-8"))


def test_schema_itself_is_valid():
    Draft202012Validator.check_schema(schema())
    assert set(schema()["required"]) == set(TOP_KEYS)


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_fixture_passes_schema_and_principles(case):
    spec = load(case)
    assert schema_errors(spec) == []
    assert check_principles(spec, case["confirmedText"]) == []
    assert spec["meta"]["sessionId"] == case["sessionId"]
    assert list(spec) == list(TOP_KEYS)            # 키 순서도 고정(파일 비교가 쉽도록)


@pytest.mark.parametrize("case", CASES, ids=[c["file"] for c in CASES])
def test_unsaid_slots_are_null_not_defaults(case):
    """원칙 3: 말하지 않은 슬롯은 null. 값이 있는 슬롯은 모두 _provenance가 있다."""
    spec = load(case)
    stated = {p for p in SLOT_PATHS if spec[p.split(".")[0]][p.split(".")[1]] is not None}
    assert stated == set(spec["_provenance"])


def _broken(mutate):
    spec = load(CASES[0])
    mutate(spec)
    return schema_errors(spec)


def test_schema_rejects_value_without_provenance():
    assert _broken(lambda s: s["_provenance"].pop("material.color"))


def test_schema_rejects_provenance_for_null_slot():
    def m(s):
        s["_provenance"]["layout.size"] = copy.deepcopy(s["_provenance"]["form.type"])
    assert _broken(m)


def test_schema_rejects_inferred_over_a_stated_value():
    def m(s):
        s["_inferred"]["material.roughness"] = {"value": 0.5, "_provenance": s["_provenance"]["material.roughness"]}
    assert _broken(m)


def test_schema_rejects_out_of_range_and_unknown_fields():
    assert _broken(lambda s: s["material"].update(roughness=1.2))
    assert _broken(lambda s: s["layout"].update(scale=1.0))
    assert _broken(lambda s: s["form"].update(type="cube"))


def test_principle_check_catches_wrong_trigger_span():
    spec = load(CASES[0])
    spec["_provenance"]["form.type"][0]["charSpan"] = [0, 3]
    assert any("trigger" in p for p in check_principles(spec, CASES[0]["confirmedText"]))
