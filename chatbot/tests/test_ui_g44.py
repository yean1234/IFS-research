"""G44 화면 개선: 조절 견본 API(읽기 전용)와 웹 화면 계약. 합성 문장만 쓴다(AGENTS.md 6).

- 견본 API는 화면 표현 전용이다: 조절 기록·selection.json·현재 상태를 바꾸지 않는다.
- 값 목록과 덮어쓰기는 조절(adjust)과 같은 규칙(_validate)으로 만든다(표 밖 값·표 밖 항목 없음).
"""
import copy
import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ifs_chatbot.controller import Runtime
from ifs_chatbot.server import create_app
from test_selection_flow import REPO_ROOT, T_FEEL, T_SCATTER, done_session, started, v4_cfg

WEB = REPO_ROOT / "chatbot" / "ifs_chatbot" / "web"


def sel_bytes(f) -> bytes:
    p = Path(f.dir) / "selection.json"
    return p.read_bytes() if p.exists() else b""


@pytest.fixture
def rt4(tmp_path):
    return Runtime(v4_cfg(tmp_path))


@pytest.mark.parametrize("item", ["form", "motion"])
def test_adjust_samples_follow_adjust_rules_and_record_nothing(rt4, item):
    _, f = started(rt4, f"SYN-G44-{item}")
    f.adjust("color", "h07")
    before_cur, before_data, before_file = dict(f.current), copy.deepcopy(f.data), sel_bytes(f)
    samples = f.adjust_samples(item)
    assert [s["value"] for s in samples] == f.item_values(item)
    for s in samples:
        want = dict(before_cur)
        want.update(f._validate(item, s["value"]))
        assert s["overrides"] == want
        assert s["overrides"]["material.color.h"] == before_cur["material.color.h"]   # 다른 항목(색)은 지금 상태 그대로
    assert f.current == before_cur and f.data == before_data and sel_bytes(f) == before_file


def test_adjust_samples_include_said_value_outside_table(rt4):
    _, f = started(rt4, "SYN-G44-EXTRA", T_SCATTER)
    vals = [s["value"] for s in f.adjust_samples("motion")]
    assert vals[-1] == "scattering" and vals == f.item_values("motion")


def test_adjust_samples_refuse_other_items_and_stages(tmp_path):
    rt = Runtime(v4_cfg(tmp_path))
    c = TestClient(create_app(runtime=rt, warmup=False))
    done_session(rt, "SYN-G44-HTTP", T_FEEL)
    v = c.post("/api/sessions/SYN-G44-HTTP/candidates").json()
    assert v["stage"] == "selecting"
    assert c.get("/api/sessions/SYN-G44-HTTP/adjust/samples/form").status_code == 409      # 조절 단계 전
    c.post("/api/sessions/SYN-G44-HTTP/selection", json={"candidateId": "none"})
    r = c.get("/api/sessions/SYN-G44-HTTP/adjust/samples/form")
    assert r.status_code == 200 and r.json()["item"] == "form" and len(r.json()["samples"]) >= 4
    for bad in ("color", "size", "layout.distance", "hue"):
        assert c.get(f"/api/sessions/SYN-G44-HTTP/adjust/samples/{bad}").status_code == 422
    # none 모드에서는 견본 PNG를 그리지 않음(409)
    assert c.get("/api/sessions/SYN-G44-HTTP/preview/sample/form/0.png").status_code == 409


def test_image_sample_png_over_http_records_nothing(tmp_path):
    rt = Runtime(v4_cfg(tmp_path, **{"preview.mode": "image", "preview.image_player": "fake"}))
    c = TestClient(create_app(runtime=rt, warmup=False))
    s = done_session(rt, "SYN-G44-IMG", T_FEEL)
    c.post("/api/sessions/SYN-G44-IMG/candidates")
    c.post("/api/sessions/SYN-G44-IMG/selection", json={"candidateId": "none"})
    f = s.selection()
    before_data, before_file = copy.deepcopy(f.data), sel_bytes(f)
    n = len(c.get("/api/sessions/SYN-G44-IMG/adjust/samples/form").json()["samples"])
    pngs = []
    for k in range(n):
        r = c.get(f"/api/sessions/SYN-G44-IMG/preview/sample/form/{k}.png")
        assert r.status_code == 200 and r.content.startswith(b"\x89PNG")
        pngs.append(r.content)
    assert len(set(pngs)) >= 4                            # 형태 네 값은 그림이 다르다(가짜 플레이어는 기본 형상을 구별하지 않음)
    assert c.get(f"/api/sessions/SYN-G44-IMG/preview/sample/form/{n}.png").status_code == 404
    assert f.data == before_data and sel_bytes(f) == before_file


# ── 웹 화면 계약(정적 검사) ──────────────────────────────────────────────────
def test_web_participant_view_and_progress_without_new_words():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    app = (WEB / "app.js").read_text(encoding="utf-8")
    assert 'data-view="researcher"' in html and 'id="progress"' in html
    assert '.get("view")' in app and "e.ctrlKey && e.altKey" in app
    # 진행 표시는 "n / N"과 칸뿐(단계 이름 문구를 새로 만들지 않음)
    prog = app[app.index("function updateProgress()"):app.index("// ── 시작")]
    assert re.search(r"`\$\{pos\} / \$\{total\}`", prog)
    assert not re.search(r"[가-힣]", re.sub(r"//.*", "", prog))


def test_stage_js_g44_contract():
    web = (WEB / "stage.js").read_text(encoding="utf-8")
    live = web[web.index("liveSlot(overrides) {"):web.index("place() {")]
    # 첫 시작이 조절 화면이어도 미리보기 자리를 잃지 않음(start()가 teardown으로 slot을 비운 뒤에 slot을 정함)
    assert live.index("this.start()") < live.index("this.slot = slot")
    assert "/adjust/samples/" in web and "/preview/sample/" in web
    # 범주 버튼에는 값 이름을 쓰지 않음(번호·견본 그림·낭독기용 "항목 이름 n"만)
    cat = web[web.index("function categoryOpts("):web.index("async function fillThumbs(")]
    assert "String(val)" not in cat and "${val}" not in cat
    assert '"aria-pressed"' in web and "data-swatch" in web
    # 사전 측정은 한 화면에 모든 문항(넘기기 없음)
    pm = web[web.index("async function drawPremeasure("):]
    assert "for (const it of pm.items)" in pm and "아직 고르지 않은 문항이" in pm
    assert "MOTION_PREVIEW_ON_DWELL" in web and "prefers-reduced-motion" in web


def test_style_css_tokens_and_reduced_motion():
    css = (WEB / "style.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion: reduce" in css and ":focus-visible" in css
    assert "--target: 44px" in css and "--fs-body: 16px" in css
    assert not re.search(r"https?://|@import|url\(", css)
