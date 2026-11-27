"""chatbot/scenarios/*.json의 기대(expect)를 오프라인 대역으로 확인한다.
안전 분기(위기·확인 문구·L5·중단)는 LLM과 무관하게 결정론적이어야 한다.
시나리오에 "config"(예: "bridge", D9)가 있으면 그 설정의 런타임으로 돈다. 없으면 기본 설정(예전 그대로)."""
import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.simulate import check_expect, drive, load_scenarios, scenario_matches_config, session_metrics

SCENARIOS = load_scenarios([])


@pytest.fixture(scope="module")
def runtimes(rt, tmp_path_factory):
    cache = {None: rt}

    def get(name):
        if name not in cache:
            cfg = load_config(name).with_overrides(**{
                "llm.backend": "offline", "guard.model_backend": "none",
                "session.log_dir": str(tmp_path_factory.mktemp(f"logs_{name}"))})
            cache[name] = Runtime(cfg, persist_logs=False)
        return cache[name]
    return get


@pytest.mark.parametrize("sc", SCENARIOS, ids=[s["id"] for s in SCENARIOS])
def test_scenario(runtimes, sc):
    r = runtimes(sc.get("config"))
    assert scenario_matches_config(sc, r.cfg)
    s = r.new_session(sc.get("condition", "chatbot"))
    drive(s, sc)
    fails = check_expect(sc, session_metrics(s), s)
    assert fails == []
