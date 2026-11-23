"""병합 마무리(G44 화면 개선 + G45–G51 제외 낱말): 두 작업이 함께 닿는 곳. 합성 문장만 쓴다(AGENTS.md 6).

- 넷째 범주(G50): 형태 견본 API는 조절과 같은 값 목록을 내고(형태 바꾸기는 막지 않음), 견본은 기록하지 않으며,
  조절로 형태를 바꾸면 selection.json에 formBlocked(adjustFormAllowed true)가 남는다.
- 동물 중심 명사(G45·G51): 형태 축을 벌리고(said_unrendered) 견본 API가 그대로 돈다.
- G50 (4) 화면 연결: 연구자 응답(/log)에만 safetyFlags가 있고, 참여자 화면이 읽는 응답에는 표시·알림 문자열이 없다.
  웹 화면은 연구자 패널 맨 위에만 표시한다(정적 계약).
"""
import copy
import json
import re

import pytest
from fastapi.testclient import TestClient

from ifs_chatbot.controller import Runtime
from ifs_chatbot.server import create_app
from test_selection_flow import REPO_ROOT, done_session, started, v4_cfg
from test_ui_g44 import sel_bytes

WEB = REPO_ROOT / "chatbot" / "ifs_chatbot" / "web"
T_STRICT = "올가미 같은 끈이 있어요. 작아요."        # 넷째 범주(빗댄 낱말) → 형태 후보 없음
T_ANIMAL = "가슴 앞에 뱀이 있어요."                  # 동물이 중심 명사 → 형태 후보 + 맞는 것이 없다
SAFETY_MARKS = ("safetyFlags", "scene_safety_flag", "넷째 제외 범주", "death_self_harm_trauma")


@pytest.fixture
def rt4(tmp_path):
    return Runtime(v4_cfg(tmp_path))


def test_g50_form_samples_follow_adjust_and_form_change_is_recorded_as_blocked(rt4):
    s, f = started(rt4, "SYN-MRG-G50", T_STRICT)
    assert all(a["slot"] != "form.type" for a in f.cands["axes"])          # 형태 후보 없음
    before_cur, before_data, before_file = dict(f.current), copy.deepcopy(f.data), sel_bytes(f)
    samples = f.adjust_samples("form")
    assert [x["value"] for x in samples] == f.item_values("form") and len(samples) >= 4
    for x in samples:
        want = dict(before_cur)
        want.update(f._validate("form", x["value"]))
        assert x["overrides"] == want
    assert f.current == before_cur and f.data == before_data and sel_bytes(f) == before_file   # 견본은 기록하지 않음
    f.adjust("form", samples[1]["value"])
    f.finish()
    sel = json.loads((f.dir / "selection.json").read_text(encoding="utf-8"))
    d = sel["sourceDetails"]["form.type"]
    assert d["formBlocked"] == {"rule": "G50", "by": ["올가미"], "adjustFormAllowed": True}
    assert [x["lemma"] for x in sel["safetyFlags"]] == ["올가미"] and sel["safetyFlags"][0]["formBlock"] is True


def test_animal_head_noun_opens_form_axis_and_samples_work(rt4):
    s, f = started(rt4, "SYN-MRG-ANIMAL", T_ANIMAL)
    assert any(a["slot"] == "form.type" and a["reason"] == "said_unrendered" for a in f.cands["axes"])
    assert f.data["safetyFlags"] == [] and s.researcher_view()["safetyFlags"] == []
    assert [x["value"] for x in f.adjust_samples("form")] == f.item_values("form")
    f.finish()
    d = f.data["sourceDetails"]["form.type"]
    assert [(w["lemma"], w["unrenderedBy"]) for w in d["saidWords"]] == [("뱀", "no_asset")]
    assert "formBlocked" not in d


def test_participant_responses_carry_no_safety_marks_over_http(tmp_path):
    rt = Runtime(v4_cfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    done_session(rt, "SYN-MRG-HTTP", T_STRICT)
    participant = [c.get("/api/sessions/SYN-MRG-HTTP").json(), c.post("/api/sessions/SYN-MRG-HTTP/candidates").json(),
                   c.get("/api/sessions/SYN-MRG-HTTP/selection").json()]
    c.post("/api/sessions/SYN-MRG-HTTP/selection", json={"candidateId": "none"})
    participant += [c.get("/api/sessions/SYN-MRG-HTTP/selection").json(),
                    c.get("/api/sessions/SYN-MRG-HTTP/adjust/samples/form").json()]
    blob = json.dumps(participant, ensure_ascii=False)
    for mark in SAFETY_MARKS:
        assert mark not in blob, mark
    r = c.get("/api/sessions/SYN-MRG-HTTP/log").json()                      # 연구자 응답에만
    assert [x["lemma"] for x in r["safetyFlags"]] == ["올가미"]
    assert any(a["kind"] == "scene_safety_flag" for a in r["log"]["alerts"])


def test_web_safety_flags_render_only_in_researcher_panel():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    stage = (WEB / "stage.js").read_text(encoding="utf-8")
    aside = html[html.index('<aside class="panel researcher researcher-only" id="researcher"'):html.index("</aside>")]
    assert 'id="safety-flags"' in aside and html.count('id="safety-flags"') == 1
    # 그리는 함수는 refreshResearcher에서만 부르고, refreshResearcher는 참여자 보기에서 바로 돌아간다
    calls = [m.start() for m in re.finditer(r"renderSafetyFlags\(", app)]
    refresh = app[app.index("async function refreshResearcher()"):app.index("// G50 (4)")]
    assert len(calls) == 2 and "renderSafetyFlags(r.safetyFlags)" in refresh
    assert re.search(r"if \(!state\.sid \|\| !\$\(\"#toggle-researcher\"\)\.checked\) return;", refresh)
    assert "safety" not in stage.lower()                                     # 참여자 단계 화면(stage.js)은 읽지 않음
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert ".safety-flags" in css and 'body[data-view="participant"] .researcher-only { display: none !important; }' in css
