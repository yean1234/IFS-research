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


def _copy_out(out: Path, work: Path) -> Path:
    for k, v in _files(out).items():
        (work / k).parent.mkdir(parents=True, exist_ok=True)
        (work / k).write_bytes(v)
    return work


def _fake_unity(work: Path, specs_dir: Path | None = None) -> tuple[Path, dict, list[str]]:
    """specs/의 spec마다 합성 Unity 기록(적용값 = spec 값을 Unity 규칙으로 반올림)·PNG·report.json을 만든다."""
    specs_dir = specs_dir or work / "specs"
    unity = work / "unity"
    unity.mkdir(exist_ok=True)
    names = sorted(p.stem for p in specs_dir.glob("*.json"))
    entries = []
    for n in names:
        spec = json.loads((specs_dir / f"{n}.json").read_text(encoding="utf-8"))
        num, cat = e2e.expected_params(spec)
        params = {k: e2e.dotnet_round4(e2e.clamp01(float(num[k]))) if k in num else 0.5 for k in e2e.UNITY_NUMERIC}
        params.update({k: cat.get(k, "x") for k in e2e.UNITY_CATEGORICAL})
        defaults = [k for k in (*e2e.UNITY_NUMERIC, *e2e.UNITY_CATEGORICAL) if k not in num and k not in cat]
        entries.append({"spec": f"{n}.json", "loaded": True, "params": params, "defaultsUsed": defaults,
                        "png": f"{n}.png", "console": {"errors": 0, "exceptions": 0, "warnings": 0}})
        (unity / f"{n}.png").write_bytes(b"\x89PNG")
    report = {"ok": True, "system": {"unityVersion": "test"},
              "summary": {"specFiles": len(names), "loaded": len(names), "captureFailures": 0, "consoleErrors": 0,
                          "consoleExceptions": 0, "frameMsP95Max": 1.0}, "specs": entries}
    return unity, report, names


def _write_report(unity: Path, report: dict) -> None:
    (unity / "report.json").write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")


def _capture_log(path: Path, names, head: str = "") -> Path:
    path.write_text(head + "".join(f"[SceneLoader] {n}.json 로드: form=blob\n" for n in names)
                    + "[BatchCapture] 끝: ok=True\n", encoding="utf-8")
    return path


def test_unity_section_sanitizes_paths_and_counts_screenshots(e2e_out, small_corpus, tmp_path):
    out, _ = e2e_out
    work = _copy_out(out, tmp_path / "w")
    unity, report, names = _fake_unity(work)
    repo = str(REPO_ROOT.resolve())
    report["options"] = {"specDir": repo + "\\docs\\x"}
    _write_report(unity, report)
    log = _capture_log(tmp_path / "capture.log", names, head=f"Loading {repo}\n")
    s = e2e.run(small_corpus, work, B=B, unity_out=unity, unity_log=log)
    u = s["unity"]
    assert s["ok"] is True and s["failures"] == [] and u["failures"] == []
    assert u["screenshots"] == len(names) and u["expectedScreenshots"] == len(names)
    assert u["applied"]["maxAbsDelta"] == 0.0 and u["applied"]["failures"] == 0
    assert u["log"]["loadedLines"] == len(names) and u["log"]["errorPatternHits"] == 0
    assert u["log"]["batchCaptureEnd"] == ["True"]
    assert repo not in (unity / "report.json").read_text(encoding="utf-8")
    assert "<repo>" in (unity / "report.json").read_text(encoding="utf-8")
    copied = (work / "logs" / "capture.log").read_text(encoding="utf-8")
    assert repo not in copied and "<repo>" in copied
    # 실행 검사를 통과하면 종료 코드 0
    e2e.main(["--corpus", str(small_corpus), "--out", str(work), "--unity-out", str(unity),
              "--unity-log", str(log), "--bootstrap", str(B)])


# ── CP3 지적 1: specs/의 잔여 spec 파일 ────────────────────────────────────────────
def _stale_script_spec(work: Path, sid: str = "Z99") -> Path:
    """이전 실행이 남긴 것처럼 보이는 합성 spec(이 스크립트 형식: <id>.<매핑>.json, sessionId = id)."""
    spec = json.loads((work / "specs" / "D01.v0.json").read_text(encoding="utf-8"))
    spec["meta"]["sessionId"] = sid
    p = work / "specs" / f"{sid}.v0.json"
    p.write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def test_rerun_fails_on_stale_spec_files_without_deleting(e2e_out, small_corpus, tmp_path):
    """같은 --out에 다시 돌릴 때 이번 실행이 만들지 않는 spec이 남아 있으면 멈추고(종료 코드 2) 지우지 않는다."""
    out, _ = e2e_out
    work = _copy_out(out, tmp_path / "w")
    stale = _stale_script_spec(work)
    user = work / "specs" / "notes.JSON"                      # Unity GetFiles("*.json")는 대소문자를 가리지 않는다
    user.write_text("{}\n", encoding="utf-8")
    before = (work / "summary.json").read_bytes()
    with pytest.raises(e2e.E2EError, match=r"Z99\.v0\.json.*notes\.JSON|notes\.JSON.*Z99\.v0\.json"):
        e2e.run(small_corpus, work, B=B)
    assert stale.exists() and user.exists()
    assert (work / "summary.json").read_bytes() == before     # 결과 파일을 쓰기 전에 멈춘다
    with pytest.raises(SystemExit) as ei:
        e2e.main(["--corpus", str(small_corpus), "--out", str(work), "--bootstrap", str(B)])
    assert ei.value.code == 2
    assert stale.exists() and user.exists()


def test_clean_specs_removes_only_script_format_files(e2e_out, small_corpus, tmp_path):
    out, _ = e2e_out
    work = _copy_out(out, tmp_path / "w")
    stale = _stale_script_spec(work)
    user = work / "specs" / "notes.json"                      # 이 스크립트 형식이 아님 → 지우지 않고 멈춤
    user.write_text('{"meta": {"specVersion": "2.0.0"}}\n', encoding="utf-8")
    foreign = work / "specs" / "Z98.v0.json"                  # 이름은 맞지만 sessionId가 이름과 다름 → 지우지 않음
    spec = json.loads((work / "specs" / "D01.v0.json").read_text(encoding="utf-8"))
    foreign.write_text(json.dumps(spec), encoding="utf-8")
    with pytest.raises(e2e.E2EError, match="notes.json") as ei:
        e2e.run(small_corpus, work, B=B, clean_specs=True)
    assert "Z98.v0.json" in str(ei.value) and "Z99.v0.json" not in str(ei.value)
    assert not stale.exists() and user.exists() and foreign.exists()
    user.unlink()
    foreign.unlink()
    _stale_script_spec(work, "Z97")
    s = e2e.run(small_corpus, work, B=B, clean_specs=True)
    assert s["ok"] is True
    assert sorted(p.name for p in (work / "specs").iterdir()) == sorted(
        f"{i}.{m}.json" for i in ("D01", "D02", "D03") for m in ("v0", "v1"))


def test_clean_specs_refused_with_unity_out(small_corpus, tmp_path):
    with pytest.raises(e2e.E2EError, match="--clean-specs"):
        e2e.run(small_corpus, tmp_path / "o", B=B, unity_out=tmp_path / "u", clean_specs=True)
    assert not (tmp_path / "o").exists()


# ── CP3 지적 2: Unity report.json 검증 ─────────────────────────────────────────────
EXPECTED = {"A01.v0.json", "A01.v1.json", "A02.v0.json"}


def _synthetic_report(tmp_path: Path) -> tuple[Path, dict]:
    unity = tmp_path / "unity"
    unity.mkdir()
    entries = []
    for n in sorted(EXPECTED):
        (unity / f"{Path(n).stem}.png").write_bytes(b"\x89PNG")
        entries.append({"spec": n, "loaded": True, "png": f"{Path(n).stem}.png", "params": {}, "defaultsUsed": []})
    rep = {"ok": True, "summary": {"specFiles": 3, "loaded": 3, "captureFailures": 0, "consoleErrors": 0,
                                   "consoleExceptions": 0}, "specs": entries}
    return unity, rep


def test_report_failures_empty_when_one_to_one(tmp_path):
    unity, rep = _synthetic_report(tmp_path)
    assert e2e.unity_report_failures(rep, EXPECTED, unity) == []


@pytest.mark.parametrize("mutate, needle", [
    (lambda r, u: r["specs"].pop(), "report.json에 없는 spec 1개: A02.v0.json"),
    (lambda r, u: r["specs"].append({"spec": "Z99.v0.json", "loaded": True, "png": "Z99.v0.png"}),
     "이번 실행의 spec이 아닌 항목 1개: Z99.v0.json"),
    (lambda r, u: r["specs"].append(dict(r["specs"][0])), "두 번 이상 나온 spec 1개: A01.v0.json"),
    (lambda r, u: r["specs"][1].update(loaded=False), "로드되지 않은 spec 1개: A01.v1.json"),
    (lambda r, u: r["specs"][2].update(captureFailed=True), "캡처 실패(captureFailed) spec 1개: A02.v0.json"),
    (lambda r, u: r.update(ok=False), "report.json ok = False"),
    (lambda r, u: r["summary"].update(captureFailures=1), "summary.captureFailures = 1"),
    (lambda r, u: r["summary"].update(consoleExceptions=2), "summary.consoleExceptions = 2"),
    (lambda r, u: (u / "A01.v1.png").unlink(), "장면 PNG가 없는 spec 1개: A01.v1.json"),
])
def test_report_failures_catch_missing_extra_and_failed_specs(tmp_path, mutate, needle):
    unity, rep = _synthetic_report(tmp_path)
    mutate(rep, unity)
    fails = e2e.unity_report_failures(rep, EXPECTED, unity)
    assert any(needle in f for f in fails), fails


def test_report_failures_include_applied_and_log_problems(tmp_path):
    unity, rep = _synthetic_report(tmp_path)
    cmp = e2e.compare_applied({"X01.v1.json": SPEC}, {"specs": [_unity_entry(**{"material.color.h": 0.1235})]})
    log_check = e2e.unity_log_check("[SceneLoader] A01.v0.json 로드: x\nSystem.Exception: 합성\n[BatchCapture] 끝: ok=False\n")
    fails = e2e.unity_report_failures(rep, EXPECTED, unity, cmp, log_check)
    assert any(f.startswith("적용값 대조 미달 1건") and "X01.v1.json material.color.h" in f for f in fails), fails
    assert any(f.startswith("Unity 로그 오류 패턴 1건") for f in fails), fails
    assert any("ok=…' = ['False']" in f for f in fails), fails
    assert any("로드:' 파일이 spec 목록과 다름(빠짐 2" in f for f in fails), fails


@pytest.mark.parametrize("case", ["missing_entry", "stale_entry", "capture_failed", "applied_delta"])
def test_unity_check_failure_sets_summary_and_exit_code_1(e2e_out, small_corpus, tmp_path, case):
    out, _ = e2e_out
    work = _copy_out(out, tmp_path / "w")
    unity, report, names = _fake_unity(work)
    if case == "missing_entry":
        report["specs"].pop(0)
        report["summary"]["loaded"] -= 1
        needle = "report.json에 없는 spec 1개: D01.v0.json"
    elif case == "stale_entry":                              # 이전 실행의 잔여 spec까지 캡처한 보고서
        report["specs"].append(dict(report["specs"][0], spec="Z99.v0.json", png="Z99.v0.png"))
        report["summary"].update(specFiles=len(names) + 1, loaded=len(names) + 1)
        needle = "이번 실행의 spec이 아닌 항목 1개: Z99.v0.json"
    elif case == "capture_failed":
        report["specs"][1]["captureFailed"] = True
        report["summary"]["captureFailures"] = 1
        report["ok"] = False
        needle = "캡처 실패(captureFailed) spec 1개: D01.v1.json"
    else:                                                    # Unity 값이 1e-4 어긋남 → |Δ| > 1e-6
        p = report["specs"][0]["params"]
        k = next(k for k in e2e.UNITY_NUMERIC if k not in report["specs"][0]["defaultsUsed"])
        p[k] = round(p[k] + 1e-4, 4) if p[k] < 0.5 else round(p[k] - 1e-4, 4)
        needle = "적용값 대조 미달 1건"
    _write_report(unity, report)
    s = e2e.run(small_corpus, work, B=B, unity_out=unity)
    assert s["ok"] is False and any(needle in f for f in s["failures"]), s["failures"]
    assert s["unity"]["failures"] == s["failures"]
    saved = json.loads((work / "summary.json").read_text(encoding="utf-8"))
    assert saved["ok"] is False and saved["failures"] == s["failures"]
    assert "실행 검사" in (work / "results.md").read_text(encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        e2e.main(["--corpus", str(small_corpus), "--out", str(work), "--unity-out", str(unity), "--bootstrap", str(B)])
    assert ei.value.code == 1


def test_scores_below_ac_do_not_change_exit_code(e2e_out):
    """채점 지표는 실행 검사에 넣지 않는다(Unity 없이 돌리면 failures는 비어 있다)."""
    _, s = e2e_out
    assert s["ok"] is True and s["failures"] == [] and "unity" not in s


# ── CP3 지적 3: Unity 로그 예외 패턴 ───────────────────────────────────────────────
def test_log_check_catches_namespaced_exceptions_but_not_capture_frame():
    text = "\n".join([
        "System.Exception: 합성 예외",
        "System.IO.DirectoryNotFoundException: Could not find a part of the path",
        "NullReferenceException: Object reference not set",
        "UnityEngine.TestRunner.NUnitExtensions.Runner.UnityLogCheckDelegatingCommand:CaptureException "
        "(NUnit.Framework.Internal.TestResult,System.Action) (at ./Library/x.cs:72)",
        "  at Foo.Bar () [0x00000] in <x>:0",
        "Exceptions handled: 0",
        "[SceneLoader] A01.v0.json 로드: form=blob",
    ]) + "\n"
    r = e2e.unity_log_check(text)
    assert r["errorPatternHits"] == 3
    assert r["hits"] == ["System.Exception:", "System.IO.DirectoryNotFoundException:", "NullReferenceException:"]
    assert e2e.unity_log_check("UnityEngine.TestRunner.NUnitExtensions.Runner.UnityLogCheckDelegatingCommand:"
                               "CaptureException (NUnit.Framework.Internal.TestResult,System.Action)\n")["errorPatternHits"] == 0
