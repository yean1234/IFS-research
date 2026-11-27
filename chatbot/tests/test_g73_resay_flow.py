"""G73 CP13b: [맞는 게 없어요] 뒤 '다시 적기' — 화면 단계·고정 문구·selection 0.4 기록·서버 연결·덮어쓰기 처음 값.

꺼짐 = 0.3 그대로(키·출처·문구 판 불변), 켜짐 흐름(solid·mist·light·flame·blocked·위기·건너뛰기·시간 초과·회차 상한·생성기 실패·
생성기 없음), selection 0.4 스키마, 원문은 git 밖 resay.json에만, 두 면담 조건에서 같은 흐름. 모든 대사는 합성이다.
생성 모델·torch를 부르지 않는다(가짜 생성기: 작은 합성 GLB + form-asset 사이드카)."""
import json
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

pytest.importorskip("kiwipiepy")

from ifs_chatbot.config import Gen3DConfig, load_config  # noqa: E402
from ifs_chatbot.controller import Runtime  # noqa: E402
from ifs_chatbot.paths import REPO_ROOT, shared  # noqa: E402
from ifs_chatbot.resay_flow import (REQUIRED_PHRASES, STAGE, STAGE_CRISIS, ResayService, _gen3d_resay,  # noqa: E402
                                    missing_phrases)
from ifs_chatbot.selection import SelectionError, SelectionProtocol  # noqa: E402
from ifs_chatbot.server import create_app  # noqa: E402
from ifs_chatbot.simulate import drive  # noqa: E402
from test_g62_gen3d import T_FEEL, cfg, write_asset  # noqa: E402

V04 = Draft202012Validator(json.loads(shared("schemas", "selection.v0.4.json").read_text(encoding="utf-8")))
P08 = "selection_protocol.v0.8.json"
HANGUL = re.compile(r"[가-힣]{2,}")

T_SOLID = "길쭉하고 둥근 덩어리가 있어요. 반투명해요"
T_MIST = "옅은 연기 같은 게 있어요"
T_MIST2 = "넓게 퍼진 안개가 있어요"
T_LIGHT = "환한 빛이 있어요"
T_FLAME = "촛불 같은 게 있어요"
T_BLOCKED = "고양이가 있어요"
T_NOTHING = "그냥 그래요"
T_CRISIS = "죽고 싶은 마음이 둥근 공처럼 있어요"


# ── 가짜 생성기 ──────────────────────────────────────────────────────────────
class FakeGen:
    """generator(prompt, negative, seed, *, out_dir, timeout_s, cancel) → 합성 GLB + 사이드카. mode = ok | failed | slow | block."""
    info = {"kind": "fake-test"}

    def __init__(self, mode="ok", delay=0.0):
        self.mode, self.delay, self.calls = mode, delay, []
        self.release = threading.Event()

    def __call__(self, prompt, negative, seed, *, out_dir, timeout_s, cancel):
        self.calls.append({"prompt": prompt, "seed": seed, "timeout": timeout_s})
        if self.mode == "block":                     # 시간 제한을 지키지 않는 생성기(서버 쪽 감시가 끊어야 함)
            self.release.wait(5)
        elif self.delay:
            time.sleep(self.delay)
        if self.mode == "failed":
            return {"status": "failed", "sidecar": None, "detail": "synthetic failure"}
        if self.mode == "timeout":
            return {"status": "timeout", "sidecar": None, "detail": None}
        p = write_asset(Path(out_dir), "resay-key", f"fake-{seed}-{prompt}", seed=seed)
        return {"status": "ok", "sidecar": p, "detail": None}


def resay_cfg(tmp, **gen3d):
    over = {"gen3d.resay": True, "selection.protocol": P08, "selection.table": "candidate_values.v3.json"}
    over.update({f"gen3d.{k}": v for k, v in gen3d.items()})
    return cfg(tmp, True).with_overrides(**over)


@pytest.fixture(scope="module")
def rt(tmp_path_factory):
    r = Runtime(resay_cfg(tmp_path_factory.mktemp("resay")))
    assert r.resay is not None
    return r


@pytest.fixture(scope="module")
def pipeline(rt):
    """가짜 WordNet(빈 표)으로 결정적인 파이프라인 — 손 형태 사전 낱말만 프롬프트로 간다(nltk 유무와 무관)."""
    rs = _gen3d_resay()
    from wordnet_filter import TableWordNet, WordNetFilter
    from ifs_chatbot.resay import ResayMapper
    filt = rs.load_filter()
    return rs.ResayPipeline(rt.cfg.gen3d, mapper=ResayMapper(rt.analyzer), safety=rt.safety,
                            wordnet=WordNetFilter(filt, TableWordNet({})), filt=filt)


class Spy:
    def __init__(self, inner):
        self.inner, self.runs = inner, 0

    def run(self, *a, **k):
        self.runs += 1
        return self.inner.run(*a, **k)


def service(rt, pipeline, gen=None, **attrs):
    spy = Spy(pipeline)
    svc = ResayService(rt, generator=gen, pipeline=spy)
    for k, v in attrs.items():
        setattr(svc, k, v)
    rt.resay = svc
    return svc, spy


_n = [0]


def session(rt, condition="static", text=T_FEEL):
    _n[0] += 1
    sid = f"SYN-G73-{condition}-{_n[0]}"
    s = rt.new_session(condition, sid)
    drive(s, {"id": sid, "replies": ["뭔가 있어요", "가슴이요", "그대로예요", "없어요"], "defaultReply": "없어요",
              "confirm": {"edit": text}})
    assert s.state == "done"
    f = s.selection()
    f.start()
    return s, f


def none_then(f, text):
    v = f.select("none")
    assert v["stage"] == STAGE and v["resay"]["phase"] == "input"
    v = f.resay_action("submit", text)
    f.resay.join(10)
    return f.view()


def sel_json(f):
    return json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))


def valid(f):
    d = sel_json(f)
    errs = [f"{list(e.path)}: {e.message}" for e in V04.iter_errors(d)]
    assert not errs, errs[:3]
    return d


def no_raw_text(f, s, texts):
    """원문(과 2자 이상 조각)이 selection.json·candidates.json·세션 로그에 없고 resay.json에만 있다."""
    sel = (f.dir / "selection.json").read_text(encoding="utf-8")
    cands = (f.dir / "candidates.json").read_text(encoding="utf-8")
    log = json.dumps(s.log.data, ensure_ascii=False)
    raw = json.loads((f.dir / "resay.json").read_text(encoding="utf-8"))
    for t in texts:
        assert any(r.get("text") == t for r in raw["rounds"])
        for frag in HANGUL.findall(t):
            assert frag not in sel and frag not in cands, frag
        assert t not in log
    r = sel_json(f)["resay"]
    r["setting"].pop("seedRule")                                  # 고정 설명 글(코드가 쓴 것)만 빼고
    if r["renderVars"]:
        r["renderVars"].pop("mistDensityRule"), r["renderVars"].pop("measuredDimsNote")
    assert not HANGUL.search(json.dumps(r, ensure_ascii=False)), HANGUL.findall(json.dumps(r, ensure_ascii=False))[:5]


# ── 꺼짐: 0.3 그대로 ─────────────────────────────────────────────────────────
def test_off_by_default_and_only_v4_gen3d_turns_it_on():
    assert Gen3DConfig().resay is False
    for f in sorted((REPO_ROOT / "chatbot" / "config").glob("*.toml")):
        c = load_config(f)
        assert c.gen3d.resay is (f.name == "v4-gen3d.toml"), f.name
    assert load_config("experiment").selection.protocol == "selection_protocol.v0.7.json"   # 본 실험 설정 그대로(G73-g)
    on = load_config("v4-gen3d")
    assert on.selection.protocol == P08 and on.gen3d.resay_generator == ""


def test_off_records_stay_03_and_view_has_no_resay(tmp_path):
    r = Runtime(cfg(tmp_path, True).with_overrides(**{"selection.table": "candidate_values.v3.json"}))
    assert r.resay is None and "resay" not in r.info()
    s, f = session(r)
    assert f.resay is None
    v = f.select("none")
    assert v["stage"] == "adjusting" and "resay" not in v and "extraAdjustItems" not in v
    f.finish()
    d = sel_json(f)
    assert d["formatVersion"] == "ifs-selection/0.3" and "resay" not in d
    assert set(d["sourceCounts"]) == {"said", "chosen", "edited", "default", "said_unrendered_chosen",
                                      "said_unrendered_default", "generated_chosen"}
    assert not (f.dir / "resay.json").exists()


def test_resay_true_without_phrases_or_gen3d_stays_off(tmp_path):
    r = Runtime(cfg(tmp_path / "a", True).with_overrides(**{"gen3d.resay": True}))      # 문구 판 0.6.0(다시 적기 문구 없음)
    assert r.resay is None and any("다시 적기 문구가" in w for w in r.warnings)
    r2 = Runtime(cfg(tmp_path / "b", None).with_overrides(**{"gen3d.resay": True, "selection.protocol": P08}))
    assert r2.resay is None and any("enabled = false" in w for w in r2.warnings)


def test_protocol_08_new_phrases_are_draft_and_clean():
    p = SelectionProtocol(P08)
    assert p.version == "0.8.0" and not missing_phrases(p)
    old = SelectionProtocol("selection_protocol.v0.7.json")
    for k, v in old.data["phrases"].items():                     # 0.7 문구는 그대로
        assert p.data["phrases"][k]["text"] == v["text"]
    new = {k: v for k, v in p.data["phrases"].items() if k not in old.data["phrases"]}
    assert set(new) == set(REQUIRED_PHRASES)
    labels = {k: p.data["adjustItemLabels"][k] for k in ("density", "emission")}
    for k, v in {**new, **labels}.items():
        assert v["status"] == "draft" and "G73" in v["source"], k
        t = v["text"]
        # 원칙 3·8: 예시·선택지·감정 이름·치료 표현 없음
        assert not re.search(r"예를 들|예컨대|처럼요|같은 것|불안|슬픔|화가|우울|걱정|치료|상담|내담자|진단", t), (k, t)
    intro = new["resay_intro"]["text"]
    assert "모양과 모습(퍼짐·옅기·빛)" in intro and "기록" in intro and "고칠 수 있어요" in intro
    assert p.data["changes"][0]["version"] == "0.8.0"


# ── 켜짐: 갈래별 흐름 ────────────────────────────────────────────────────────
def test_solid_generates_new_candidates_first_and_choice_is_generated_resaid(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    before = list(f.cands["displayOrder"])
    v = none_then(f, T_SOLID)
    assert v["stage"] == "selecting"
    new = v["resay"]["newCandidateIds"]
    assert 1 <= len(new) <= 2 and [c["id"] for c in v["candidates"]][:len(new)] == new
    assert [c["id"] for c in v["candidates"]][len(new):] == before                 # 새 후보 + 앞서 본 후보
    assert all(c["resaid"] and c["new"] and c["asset"] for c in v["candidates"][:len(new)])
    assert not any(c["default"] for c in v["candidates"]) and v["defaultCandidateId"] is None
    assert [c["seed"] for c in gen.calls] == [10 + k for k in range(len(gen.calls))]    # seed 고정 순서
    v = f.select(new[0])
    assert v["stage"] == "adjusting"
    assert v["current"]["overrides"]["material.opacity"] == 0.5                         # 반투명 → 처음 값
    assert v["currentAsset"] is not None
    f.finish()
    d = valid(f)
    assert d["formatVersion"] == "ifs-selection/0.4"
    assert d["sources"]["form.type"] == "generated_resaid_chosen" and d["sources"]["material.opacity"] == "resaid"
    assert d["sources"]["layout.proportions"] == "resaid"
    assert d["form"]["asset"]["resayRound"] == 1 and d["form"]["asset"]["glb"].endswith(".glb")
    assert d["generation"]["outcome"] == "generated_resaid_chosen"
    r = d["resay"]
    assert r["outcome"] == "generated_resaid_chosen" and r["exposed"] is True
    assert [e["event"] for e in r["events"]] == ["screen_shown", "submitted"] + ["generation_attempt"] * len(gen.calls) + \
        ["candidates_shown", "chosen"]
    rd = r["rounds"][0]
    assert rd["branch"] == "solid" and rd["outcome"] == "candidates" and rd["candidateIds"] == new
    assert rd["prompt"]["status"] == "ok" and rd["prompt"]["prompts"][0]["text"].startswith("a single")
    op = next(o for o in r["overrides"] if o["slot"] == "material.opacity")
    assert op["edited"] is False and op["final"] == {"material.opacity": 0.5} and op["charSpans"]
    assert r["renderVars"]["opacity"] == 0.5
    no_raw_text(f, s, [T_SOLID])


def test_mist_values_go_to_adjust_and_density_reaches_overrides(rt, pipeline):
    gen = FakeGen()
    _, spy = service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_MIST)
    assert v["stage"] == "adjusting" and gen.calls == []                                 # 생성하지 않음
    ov = v["current"]["overrides"]
    assert ov["form.type"] == "mist" and ov["mist.density"] == 0.25
    assert [i["id"] for i in v["extraAdjustItems"]] == ["density"]
    assert v["extraAdjustItems"][0]["label"] == "짙기"
    assert "mist.density = 0.25 *" in v["current"]["summary"]
    assert f.overrides_for("current")["mist.density"] == 0.25                           # 미리보기 덮어쓰기에 들어감
    v = f.adjust("density", 0.65)
    assert v["current"]["items"]["density"] == 0.65
    f.finish()
    d = valid(f)
    assert d["finalOverrides"]["mist.density"] == 0.65 and d["finalOverrides"]["form.type"] == "mist"
    assert d["sources"]["form.type"] == "resaid"
    dens = next(o for o in d["resay"]["overrides"] if o["slot"] == "mist.density")
    assert dens["first"] == {"mist.density": 0.25} and dens["final"] == {"mist.density": 0.65} and dens["edited"] is True
    assert dens["rules"] and all("(" not in r for r in dens["rules"])
    assert d["resay"]["renderVars"]["mistDensity"] == 0.65
    assert d["resay"]["outcome"] == "values_applied" and spy.runs == 1
    no_raw_text(f, s, [T_MIST])


def test_mist_with_proportions_and_form_edit_hides_density(rt, pipeline):
    service(rt, pipeline, FakeGen())
    s, f = session(rt)
    v = none_then(f, T_MIST2)
    assert v["current"]["overrides"]["layout.proportions.y"] == 0.3
    v = f.adjust("form", "blob")
    assert "extraAdjustItems" not in v or all(i["id"] != "density" for i in v["extraAdjustItems"])
    f.finish()
    d = valid(f)
    assert d["sources"]["form.type"] == "edited" and d["sources"]["layout.proportions"] == "resaid"


def test_light_sets_emission_item(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_LIGHT)
    assert v["stage"] == "adjusting" and gen.calls == []
    assert v["current"]["overrides"]["material.emission"] == "glowing"
    assert [i["id"] for i in v["extraAdjustItems"]] == ["emission"]
    samples = f.adjust_samples("emission")
    assert [x["value"] for x in samples] == ["none", "faint", "glowing"]
    f.finish()
    d = valid(f)
    assert d["finalOverrides"]["material.emission"] == "glowing"
    em = d["resay"]["overrides"][0]
    assert em["slot"] == "material.emission" and em["source"] in ("mapper_v2", "lexicon_implied")


def test_flame_sets_flame_base_without_generation(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_FLAME)
    assert v["stage"] == "adjusting" and gen.calls == []
    assert v["current"]["overrides"]["form.base"] == "flame"
    f.finish()
    d = valid(f)
    assert d["sources"]["form.base"] == "resaid" and d["finalOverrides"]["form.base"] == "flame"
    assert d["resay"]["overrides"][0]["rules"] == ["resay.branchForm.flame>form:flame"]


def test_blocked_shows_neutral_notice_then_retry_then_continue(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_BLOCKED)
    assert v["stage"] == STAGE and v["resay"]["phase"] == "notice" and v["resay"]["canRetry"] is True
    assert v["resay"]["researcher"]["branch"] == "blocked"
    v = f.resay_action("retry", None)
    assert v["resay"]["phase"] == "input" and v["resay"]["round"] == 2
    v = f.resay_action("submit", T_NOTHING)
    f.resay.join(10)
    v = f.view()
    assert v["resay"]["phase"] == "notice" and v["resay"]["canRetry"] is False         # 2회 다 씀
    with pytest.raises(SelectionError):
        f.resay_action("retry", None)
    v = f.resay_action("continue", None)
    assert v["stage"] == "adjusting" and gen.calls == []
    assert v["current"]["overrides"] == dict(f.cands["candidates"][0]["overrides"])      # 기준 후보 0번, 값 없음
    f.finish()
    d = valid(f)
    assert d["resay"]["outcome"] == "exhausted" and d["selection"]["none"] is True
    assert [r["outcome"] for r in d["resay"]["rounds"]] == ["blocked", "nothing_read"]
    assert d["resay"]["rounds"][0]["blockDetail"] == ["animal:…"]                     # 종류만, 낱말은 지움
    no_raw_text(f, s, [T_BLOCKED, T_NOTHING])


def test_crisis_stops_with_fixed_phrase_and_no_model(rt, pipeline):
    gen = FakeGen()
    _, spy = service(rt, pipeline, gen)
    s, f = session(rt)
    f.select("none")
    v = f.resay_action("submit", T_CRISIS)
    assert v["stage"] == STAGE_CRISIS and v["resay"]["crisisPhrase"] == rt.protocol.phrase(
        "crisis", researcher_contact=rt.cfg.session.researcher_contact)
    assert spy.runs == 0 and gen.calls == [] and f.resay.thread is None
    assert any(a["kind"] == "resay_crisis" for a in s.log.data["alerts"])
    with pytest.raises(SelectionError):
        f.resay_action("skip", None)
    with pytest.raises(SelectionError):
        f.select("none")
    d = valid(f)
    assert d["resay"]["outcome"] == "crisis" and d["runnerReady"] is False
    assert d["resay"]["rounds"][0]["safety"]["level"] == "crisis"


def test_skip_on_input_screen_goes_to_base_candidate(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    f.select("none")
    v = f.resay_action("skip", None)
    assert v["stage"] == "adjusting" and v["selection"]["none"] is True and v["selection"]["resayRound"] == 1
    assert v["current"]["overrides"] == dict(f.cands["candidates"][0]["overrides"])
    f.finish()
    d = valid(f)
    assert d["resay"]["outcome"] == "skipped" and d["resay"]["rounds"][0]["outcome"] == "skipped"
    assert d["resay"]["exposed"] is True and not (f.dir / "resay.json").exists()        # 적지 않았으면 원문 파일 없음


def test_skip_while_waiting_discards_late_result(rt, pipeline):
    gen = FakeGen(mode="block")
    service(rt, pipeline, gen)
    s, f = session(rt)
    f.select("none")
    v = f.resay_action("submit", T_SOLID)
    assert v["resay"]["phase"] == "waiting"
    v = f.resay_action("skip", None)
    assert v["stage"] == "adjusting"
    gen.release.set()
    f.resay.join(10)
    v = f.view()
    assert v["stage"] == "adjusting" and not any(c["id"].startswith("r") for c in v["candidates"])
    f.finish()
    d = valid(f)
    assert d["resay"]["outcome"] == "skipped" and d["resay"]["rounds"][0]["outcome"] == "skipped_while_waiting"


def test_round_timeout_watchdog_and_generator_timeout(rt, pipeline):
    gen = FakeGen(mode="block")
    service(rt, pipeline, gen, round_timeout_s=0.3)
    s, f = session(rt)
    f.select("none")
    f.resay_action("submit", T_SOLID)
    time.sleep(0.5)
    v = f.view()                                                   # 생성기가 시간을 넘겨도 서버가 끊는다
    assert v["stage"] == "adjusting"
    gen.release.set()
    f.resay.join(10)
    assert f.view()["stage"] == "adjusting"
    d = valid(f)
    assert d["resay"]["outcome"] == "timeout" and d["resay"]["rounds"][0]["outcome"] == "timeout"
    # 시간 제한을 지키는 생성기가 timeout을 돌려주는 경우도 같은 경로
    gen2 = FakeGen(mode="timeout")
    service(rt, pipeline, gen2)
    s2, f2 = session(rt)
    v = none_then(f2, T_SOLID)
    assert v["stage"] == "adjusting" and sel_json(f2)["resay"]["outcome"] == "timeout"


def test_total_wait_cap_blocks_new_rounds(rt, pipeline):
    svc, _ = service(rt, pipeline, FakeGen(), total_wait_s=0.0)
    s, f = session(rt)
    v = f.select("none")                                           # 대기 상한 0 → 다시 적기 없이 지금 경로
    assert v["stage"] == "adjusting" and sel_json(f)["resay"]["exposed"] is False


def test_generator_failure_goes_to_base(rt, pipeline):
    gen = FakeGen(mode="failed")
    service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_SOLID)
    assert v["stage"] == "adjusting" and len(gen.calls) >= 1
    d = valid(f)
    assert d["resay"]["outcome"] == "generator_failed"
    assert all(g["status"] == "failed" and g["called"] for g in d["resay"]["rounds"][0]["generation"])


def test_no_generator_configured_solid_shows_notice(rt, pipeline):
    service(rt, pipeline, None)
    s, f = session(rt)
    v = none_then(f, T_SOLID)
    assert v["stage"] == STAGE and v["resay"]["phase"] == "notice"
    assert sel_json(f)["resay"]["rounds"][0]["outcome"] == "no_generator"


def test_round_limit_second_none_after_last_round_goes_to_base(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen, max_rounds=1)
    s, f = session(rt)
    v = none_then(f, T_SOLID)
    assert v["stage"] == "selecting"
    v = f.select("none")                                           # 1회 다 씀 → 기준 후보 0번, 다시 적은 값은 쓰지 않음
    assert v["stage"] == "adjusting" and "material.opacity" not in v["current"]["overrides"]
    f.finish()
    d = valid(f)
    assert d["resay"]["outcome"] == "exhausted" and d["form"]["asset"] is None
    assert d["sources"]["material.opacity"] != "resaid"


def test_two_rounds_then_choose_earlier_candidate_uses_no_values(rt, pipeline):
    gen = FakeGen()
    service(rt, pipeline, gen)
    s, f = session(rt)
    v = none_then(f, T_SOLID)
    first_new = v["resay"]["newCandidateIds"]
    v = f.select("none")
    assert v["stage"] == STAGE and v["resay"]["round"] == 2
    v = f.resay_action("submit", "둥근 덩어리가 있어요")
    f.resay.join(10)
    v = f.view()
    assert v["stage"] == "selecting" and all(c.startswith("r2-") for c in v["resay"]["newCandidateIds"])
    assert set(first_new) <= {c["id"] for c in v["candidates"]}
    proc = next(c["id"] for c in v["candidates"] if c["id"].startswith("c-"))
    v = f.select(proc)
    assert "material.opacity" not in v["current"]["overrides"]
    f.finish()
    d = valid(f)
    assert d["resay"]["outcome"] == "earlier_candidate_chosen" and d["form"]["asset"] is None
    r1, r2 = (d["resay"]["rounds"][i]["generation"] for i in (0, 1))
    assert [g["seed"] for g in r1] == [10 + k for k in range(len(r1))]                  # seed = 회차 × 10 + k
    assert [g["seed"] for g in r2] == [20 + k for k in range(len(r2))]
    assert [c["seed"] for c in gen.calls] == [g["seed"] for g in r1 + r2]


def test_raw_text_file_is_git_ignored(rt, pipeline):
    service(rt, pipeline, FakeGen())
    s, f = session(rt)
    none_then(f, T_MIST)
    rel = f"chatbot/logs/selection/{s.id}/resay.json"
    out = subprocess.run(["git", "check-ignore", "-q", rel], cwd=REPO_ROOT)
    assert out.returncode == 0, rel
    tracked = subprocess.run(["git", "ls-files", "chatbot/logs"], cwd=REPO_ROOT, capture_output=True, text=True).stdout
    assert tracked.strip() == ""


def test_withdraw_deletes_raw_text(rt, pipeline):
    service(rt, pipeline, FakeGen())
    s, f = session(rt)
    none_then(f, T_MIST)
    assert (f.dir / "resay.json").is_file()
    s.withdraw()
    assert not f.dir.exists()


def test_no_persist_writes_no_raw_text(tmp_path, pipeline):
    r = Runtime(resay_cfg(tmp_path), persist_logs=False)
    service(r, pipeline, FakeGen())
    s, f = session(r)
    v = none_then(f, T_SOLID)
    assert v["stage"] == "selecting"
    assert not (tmp_path / "logs" / "selection").exists() or not any((tmp_path / "logs" / "selection").rglob("resay.json"))


@pytest.mark.parametrize("text", [T_SOLID, T_MIST, T_BLOCKED])
def test_same_flow_in_both_interview_conditions(rt, pipeline, text):
    outs = []
    for cond in ("static", "chatbot"):
        service(rt, pipeline, FakeGen())
        s, f = session(rt, cond)
        v = none_then(f, text)
        r = sel_json(f)["resay"]["rounds"][0]
        outs.append((v["stage"], v["resay"]["phase"], r["branch"], r["outcome"], r["values"], r["prompt"],
                     [g["seed"] for g in r["generation"]], [e["slot"] for e in sel_json(f)["resay"]["overrides"]]))
    assert outs[0] == outs[1]


# ── 서버 ────────────────────────────────────────────────────────────────────
def test_api_resay_endpoint_and_ui_config(rt, pipeline):
    service(rt, pipeline, FakeGen())
    client = TestClient(create_app(rt.cfg, runtime=rt, warmup=False))
    ui = client.get("/api/selection/config").json()
    assert ui["phrases"]["resay_intro"].startswith("떠올리신 그것이")
    s, f = session(rt)
    sid = s.id
    assert client.post(f"/api/sessions/{sid}/resay", json={"action": "submit", "text": "x"}).status_code == 409
    v = client.post(f"/api/sessions/{sid}/selection", json={"candidateId": "none"}).json()
    assert v["stage"] == STAGE
    assert client.post(f"/api/sessions/{sid}/resay", json={"action": "submit", "text": "  "}).status_code == 422
    assert client.post(f"/api/sessions/{sid}/resay", json={"action": "nope"}).status_code == 422
    v = client.post(f"/api/sessions/{sid}/resay", json={"action": "submit", "text": T_MIST}).json()
    assert v["resay"]["phase"] in ("waiting", None)
    f.resay.join(10)
    v = client.get(f"/api/sessions/{sid}/selection").json()
    assert v["stage"] == "adjusting" and v["extraAdjustItems"][0]["id"] == "density"
    v = client.post(f"/api/sessions/{sid}/adjust", json={"item": "density", "value": 0.8}).json()
    assert v["current"]["overrides"]["mist.density"] == 0.8
    png = client.get(f"/api/sessions/{sid}/preview/current.png")                    # 미리보기(가짜 플레이어)에 덮어쓰기가 간다
    assert png.status_code == 200 and png.content[:4] == b"\x89PNG"
    assert client.post(f"/api/sessions/{sid}/adjust", json={"item": "density", "value": 0.33}).status_code == 422


def test_resay_off_endpoint_409(tmp_path):
    r = Runtime(cfg(tmp_path, True))
    client = TestClient(create_app(r.cfg, runtime=r, warmup=False))
    s, f = session(r)
    assert client.post(f"/api/sessions/{s.id}/resay", json={"action": "skip"}).status_code == 409


# ── 원칙 1: 챗봇은 모델을 부르지 않는다 ────────────────────────────────────────
def test_resay_flow_has_no_model_imports():
    src = (REPO_ROOT / "chatbot" / "ifs_chatbot" / "resay_flow.py").read_text(encoding="utf-8")
    assert not re.search(r"^\s*(import|from)\s+(torch|diffusers|transformers|httpx|requests|urllib)", src, re.M)
    assert "ollama" not in src.lower()


def test_unity_side_accepts_mist_density_and_04():
    base = REPO_ROOT / "unity" / "Assets" / "IFS" / "Runtime"
    sp = (base / "SceneSpec" / "SceneParams.cs").read_text(encoding="utf-8")
    so = (base / "SceneSpec" / "SceneOverride.cs").read_text(encoding="utf-8")
    plan = (base / "Rendering" / "FormRenderPlan.cs").read_text(encoding="utf-8")
    sel = (base / "Placement" / "PlacementSelection.cs").read_text(encoding="utf-8")
    assert 'MistDensityKey = "mist.density"' in sp and "SetMistDensity" in so and "current.MistDensity" in plan
    s04 = re.search(r"SourceValues04\s*=\s*\{([^}]*)\}", sel).group(1)
    schema = json.loads(shared("schemas", "selection.v0.4.json").read_text(encoding="utf-8"))
    assert re.findall(r'"([^"]+)"', s04) == schema["$defs"]["source"]["enum"]
    assert "mist.density" in schema["$defs"]["flatOverrides"]["propertyNames"]["enum"]
    assert sys.version_info >= (3, 10)
