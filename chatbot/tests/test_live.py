"""실제 로컬 모델로 도는 테스트. 기본은 건너뛴다.
   IFS_LIVE=1 python -m pytest -m live
"""
import os

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.simulate import check_expect, drive, load_scenarios, session_metrics

pytestmark = [pytest.mark.live, pytest.mark.skipif(os.environ.get("IFS_LIVE") != "1", reason="IFS_LIVE=1일 때만")]


@pytest.fixture(scope="module")
def live_rt(tmp_path_factory):
    cfg = load_config().with_overrides(**{"session.log_dir": str(tmp_path_factory.mktemp("live_logs"))})
    rt = Runtime(cfg)
    if not rt.backend_ok:
        pytest.skip(rt.backend_msg)
    return rt


@pytest.mark.parametrize("sc", load_scenarios([]), ids=lambda s: s["id"])
def test_live_scenario_safety_expectations(live_rt, sc):
    s = live_rt.new_session(sc.get("condition", "chatbot"))
    drive(s, sc)
    assert check_expect(sc, session_metrics(s), s) == []
    # 참여자에게 나간 LLM 질문은 모두 검증기를 통과한 것이어야 한다
    for t in s.log.turns:
        if t.get("source") == "llm" and t.get("text"):
            assert t["checks"]["passed"]
