"""전 과정 실행 검증 스크립트(eval/e2e.py) — dev 코퍼스 일부와 손으로 쓴 작은 합성 입력만 쓴다(held-out 기대값 없음)."""
import json
import socket
from pathlib import Path

import pytest

from ifs_chatbot.eval import e2e, fidelity
from ifs_chatbot.paths import REPO_ROOT

DEV = Path(__file__).parent / "fixtures" / "imagery_corpus" / "dev.json"
B = 50


@pytest.fixture(scope="module")
def small_corpus(tmp_path_factory):
    """dev 코퍼스 앞 3개 항목(합성)."""
    data = json.loads(DEV.read_text(encoding="utf-8"))
    data["items"] = data["items"][:3]
    p = tmp_path_factory.mktemp("corpus") / "dev_small.json"
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.fixture(scope="module")
def e2e_out(small_corpus, tmp_path_factory):
    out = tmp_path_factory.mktemp("e2e")
    summary = e2e.run(small_corpus, out, B=B, no_network=True)
    return out, summary


def _files(root: Path) -> dict[str, bytes]:
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_pipeline_writes_specs_schema_and_scores(e2e_out):
    out, s = e2e_out
    assert s["items"] == 3 and s["mappers"] == ["v0", "v1"]
    assert sorted(p.name for p in (out / "specs").glob("*.json")) == sorted(
        f"{i}.{m}.json" for i in ("D01", "D02", "D03") for m in ("v0", "v1"))
    for m in ("v0", "v1"):
        assert s["schema"][m]["valid"] == s["schema"][m]["files"] == 3
        assert s["schema"][m]["fileEqualsRunSpec"] == 3 and s["schema"][m]["principleProblems"] == 0
        assert s["schema"][m]["fallbacks"] == 0
    assert s["schema"]["v0"]["schemaFiles"] == ["scene-spec.v2.json"]
    assert s["schema"]["v1"]["schemaFiles"] == ["scene-spec.v2.1.json"]
    assert s["network"]["guard"] is True and s["network"]["calls"] == []
    for name in ("summary.json", "results.md", "pipeline.log", "schema.json", "drift.json", "score/paired.json"):
        assert (out / name).exists(), name
    assert set(s["drift"]["byMapper"]) == {"v0", "v1"}


def test_scores_equal_fidelity_compare(e2e_out, small_corpus, tmp_path):
    """채점은 fidelity --compare와 같은 계산·같은 파일이다(바이트 비교)."""
    out, _ = e2e_out
    fidelity.compare(small_corpus, "v0", "v1", tmp_path / "fid", B=B)
    for name in ("runs.json", "report.json", "report.md", "compare/runs.json", "compare/report.json", "paired.json",
                 "paired.md"):
        assert (out / "score" / name).read_bytes() == (tmp_path / "fid" / name).read_bytes(), name


def test_spec_files_are_controller_scene_files(e2e_out):
    """specs/의 파일은 컨트롤러가 장면 폴더에 쓴 바이트 그대로이고 runs.json의 spec과 같다."""
    out, _ = e2e_out
    runs = json.loads((out / "score" / "compare" / "runs.json").read_text(encoding="utf-8"))
    for it in runs["items"]:
        raw = (out / "specs" / f"{it['id']}.v1.json").read_text(encoding="utf-8")
        assert json.loads(raw) == it["spec"]
        assert raw.endswith("\n") and raw.startswith("{\n")


def test_deterministic_and_no_absolute_paths(e2e_out, small_corpus, tmp_path):
    out, _ = e2e_out
    e2e.run(small_corpus, tmp_path / "again", B=B, no_network=True)
    first, second = _files(out), _files(tmp_path / "again")
    assert first.keys() == second.keys()
    for k in first:
        assert first[k] == second[k], k
    needles = [str(REPO_ROOT.resolve()), str(Path.home()), str(out), str(small_corpus.parent)]
    for k, v in first.items():
        text = v.decode("utf-8")
        for n in needles:
            assert n not in text and n.replace("\\", "/") not in text and n.replace("\\", "\\\\") not in text, (k, n)


def test_rerun_refuses_changed_spec_after_unity(e2e_out, small_corpus, tmp_path):
    """Unity가 캡처한 spec 파일과 다시 만든 spec이 다르면 대조하지 않고 멈춘다."""
    out, _ = e2e_out
    work = tmp_path / "w"
    for k, v in _files(out).items():
        (work / k).parent.mkdir(parents=True, exist_ok=True)
        (work / k).write_bytes(v)
    (work / "specs" / "D01.v0.json").write_text("{}\n", encoding="utf-8")
    (work / "unity").mkdir()
    (work / "unity" / "report.json").write_text(json.dumps({"specs": []}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="D01.v0.json"):
        e2e.run(small_corpus, work, B=B, unity_out=work / "unity")


def test_network_guard_blocks_and_restores():
    import httpx
    orig_connect, orig_get = socket.socket.connect, httpx.get
    with e2e.network_guard() as g:
        with pytest.raises(AssertionError):
            socket.socket().connect(("127.0.0.1", 9))
        with pytest.raises(AssertionError):
            httpx.get("http://127.0.0.1:9")
        assert g["calls"] == ["socket.connect", "httpx.get"]
    assert socket.socket.connect is orig_connect and httpx.get is orig_get
    assert "connect" not in vars(socket.socket)


# ── 적용값 대조(AC-5.7) — 손으로 쓴 합성 spec·Unity 기록 ─────────────────────────────
def test_dotnet_round4_matches_math_round_and_flags_decimal_boundaries():
    assert e2e.dotnet_round4(0.12345) == 0.1234            # .NET: 0.12345 × 10⁴ = 1234.4999… → 1234
    assert round(0.12345, 4) == 0.1235                     # 십진 정확 반올림은 다르다(경계 사례)
    assert e2e.dotnet_round4(0.5) == 0.5 and e2e.dotnet_round4(0.33335) == 0.3334
    assert e2e.dotnet_round4(2.5e-05) == 0.0


SPEC = {"form": {"type": "blob", "posture": None},
        "material": {"color": {"h": 0.12345, "s": 0.5, "l": 0.4}, "brightness": None, "saturation": 0.8,
                     "roughness": 0.25, "opacity": None, "erosion": None},
        "layout": {"size": 1.2, "distance": None, "verticalOffset": None},
        "motion": {"type": None, "speed": None}, "body": {"part": None, "layer": None}}


def _unity_entry(**over):
    params = {"material.color.h": 0.1234, "material.color.s": 0.8, "material.color.l": 0.4, "material.brightness": 0.5,
              "material.roughness": 0.25, "material.opacity": 1.0, "material.erosion": 0.0, "layout.size": 1.0,
              "layout.distance": 0.33, "layout.verticalOffset": 0.75, "motion.speed": 0.5,
              "form.type": "blob", "form.posture": "none", "motion.type": "still"}
    params.update(over)
    return {"spec": "X01.v1.json", "loaded": True, "params": params,
            "defaultsUsed": ["form.posture", "material.brightness", "material.opacity", "material.erosion",
                             "layout.distance", "layout.verticalOffset", "motion.type", "motion.speed"]}


def test_compare_applied_source_b_exact_match():
    c = e2e.compare_applied({"X01.v1.json": SPEC}, {"specs": [_unity_entry()]})
    assert c["source"] == "나" and c["failures"] == [] and c["maxAbsDelta"] == 0.0
    assert c["numericCompared"] == 5                        # h·s(채도어)·l·roughness·size. null 슬롯은 대조하지 않음
    assert [r["key"] for r in c["roundingBoundaryCases"]] == ["material.color.h"]
    assert [r["key"] for r in c["clampedValues"]] == ["layout.size"]
    assert c["categoricalCompared"] == 1 and c["categoricalMismatches"] == [] and c["defaultsUsedMismatches"] == []


def test_compare_applied_counts_1e4_difference_as_failure():
    c = e2e.compare_applied({"X01.v1.json": SPEC}, {"specs": [_unity_entry(**{"material.color.h": 0.1235})]})
    assert len(c["failures"]) == 1 and c["failures"][0]["key"] == "material.color.h"
    assert c["maxAbsDelta"] == pytest.approx(1e-4)


def test_compare_applied_reports_missing_and_default_mismatch():
    entry = _unity_entry(**{"form.type": "mist"})
    entry["defaultsUsed"] = [k for k in entry["defaultsUsed"] if k != "motion.speed"]
    c = e2e.compare_applied({"X01.v1.json": SPEC, "X02.v1.json": SPEC}, {"specs": [entry]})
    assert [m["spec"] for m in c["specsMissingOrNotLoaded"]] == ["X02.v1.json"]
    assert [m["key"] for m in c["categoricalMismatches"]] == ["form.type"]
    assert [(m["key"], m["issue"]) for m in c["defaultsUsedMismatches"]] == [("motion.speed", "spec null인데 defaultsUsed에 없음")]


def test_unity_section_sanitizes_paths_and_counts_screenshots(e2e_out, small_corpus, tmp_path):
    out, _ = e2e_out
    work = tmp_path / "w"
    for k, v in _files(out).items():
        (work / k).parent.mkdir(parents=True, exist_ok=True)
        (work / k).write_bytes(v)
    unity = work / "unity"
    unity.mkdir()
    names = sorted(p.stem for p in (work / "specs").glob("*.json"))
    entries = []
    for n in names:
        spec = json.loads((work / "specs" / f"{n}.json").read_text(encoding="utf-8"))
        num, cat = e2e.expected_params(spec)
        params = {k: e2e.dotnet_round4(e2e.clamp01(float(num[k]))) if k in num else 0.5 for k in e2e.UNITY_NUMERIC}
        params.update({k: cat.get(k, "x") for k in e2e.UNITY_CATEGORICAL})
        defaults = [k for k in (*e2e.UNITY_NUMERIC, *e2e.UNITY_CATEGORICAL) if k not in num and k not in cat]
        entries.append({"spec": f"{n}.json", "loaded": True, "params": params, "defaultsUsed": defaults,
                        "console": {"errors": 0, "exceptions": 0, "warnings": 0}})
    for n in names[:-1]:                                     # 마지막 하나는 스크린샷 없음
        (unity / f"{n}.png").write_bytes(b"\x89PNG")
    repo = str(REPO_ROOT.resolve())
    report = {"ok": True, "options": {"specDir": repo + "\\docs\\x"}, "system": {"unityVersion": "test"},
              "summary": {"specFiles": len(names), "loaded": len(names), "captureFailures": 0, "consoleErrors": 0,
                          "consoleExceptions": 0, "frameMsP95Max": 1.0}, "specs": entries}
    (unity / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
    log = tmp_path / "capture.log"
    log.write_text(f"Loading {repo}\n" + "".join(f"[SceneLoader] {n}.json 로드: form=blob\n" for n in names)
                   + "[BatchCapture] 끝: ok=True\n", encoding="utf-8")
    s = e2e.run(small_corpus, work, B=B, unity_out=unity, unity_log=log)
    u = s["unity"]
    assert u["screenshots"] == len(names) - 1 and u["expectedScreenshots"] == len(names)
    assert u["applied"]["maxAbsDelta"] == 0.0 and u["applied"]["failures"] == 0
    assert u["log"]["loadedLines"] == len(names) and u["log"]["errorPatternHits"] == 0
    assert u["log"]["batchCaptureEnd"] == ["True"]
    assert repo not in (unity / "report.json").read_text(encoding="utf-8")
    assert "<repo>" in (unity / "report.json").read_text(encoding="utf-8")
    copied = (work / "logs" / "capture.log").read_text(encoding="utf-8")
    assert repo not in copied and "<repo>" in copied
