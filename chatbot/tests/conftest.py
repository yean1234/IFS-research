import json

import pytest

from ifs_chatbot.config import load_config
from ifs_chatbot.controller import Runtime
from ifs_chatbot.llm import ScriptedBackend
from ifs_chatbot.safety import ModelVerdict


@pytest.fixture(scope="session")
def offline_cfg(tmp_path_factory):
    logs = tmp_path_factory.mktemp("logs")
    return load_config().with_overrides(**{
        "llm.backend": "offline", "guard.model_backend": "none", "session.log_dir": str(logs),
    })


@pytest.fixture(scope="session")
def rt(offline_cfg):
    return Runtime(offline_cfg)


def turn(stage="flesh_out", template="what_kind", anchor="덩어리", utterance="그 '덩어리'는 어떤 '덩어리'인가요?",
         move="ask", risk="none") -> str:
    return json.dumps({"stage": stage, "risk_signal": risk, "move": move, "template": template,
                       "anchor_quote": anchor, "utterance": utterance}, ensure_ascii=False)


@pytest.fixture
def scripted(offline_cfg):
    """make(outputs, guard_model=None) -> (Runtime, ScriptedBackend). LLM 대신 정해 둔 출력을 차례로 낸다."""
    def make(outputs, guard_model=None, **overrides):
        cfg = offline_cfg.with_overrides(**overrides) if overrides else offline_cfg
        backend = ScriptedBackend(outputs)
        return Runtime(cfg, backend=backend, guard_model=guard_model), backend
    return make


class FakeGuardModel:
    """표에 적은 (사람, AI) 쌍만 위험으로 판정하는 가짜 가드 모델."""

    def __init__(self, table=None):
        self.table = table or {}
        self.model = "fake-guard"
        self.digest = None
        self.calls = []

    def classify(self, human, ai=""):
        self.calls.append((human, ai))
        label, cat = self.table.get((human, ai), ("SAFE", None))
        return ModelVerdict(self.model, label, cat)

    def info(self):
        return {"name": self.model, "format": "fake", "digest": None, "runtime": "test"}


@pytest.fixture
def fake_guard():
    return FakeGuardModel
