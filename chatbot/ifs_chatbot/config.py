"""설정 읽기. config/*.toml → Config 데이터클래스. CLI 인자로 일부를 덮어쓸 수 있다."""
from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from .paths import CHATBOT_DIR, CONFIG_DIR


@dataclass(frozen=True)
class InterviewConfig:
    condition: str = "chatbot"                     # chatbot(조건 2) | static(조건 1)
    protocol: str = "elicitation_protocol.v1.json"  # shared/protocol/ 아래
    prompt_version: str = "1.0.0"                  # chatbot/prompts/v<버전>/


@dataclass(frozen=True)
class LLMConfig:
    backend: str = "ollama"        # ollama | offline(개발용 템플릿 대역)
    model: str = "gemma4:e4b"
    host: str = "http://127.0.0.1:11434"
    timeout_s: float = 300.0
    temperature: float = 0.2
    top_p: float = 0.9
    seed: int = 7
    think: bool = False
    num_ctx: int = 8192
    keep_alive: str = "30m"
    max_regenerations: int = 2
    retry_feedback: bool = True


@dataclass(frozen=True)
class GuardConfig:
    keyword: bool = True
    model_backend: str = "none"    # none | ollama
    model: str = "hf.co/mradermacher/kanana-safeguard-8b-GGUF:Q4_K_M"
    format: str = "kanana"         # kanana | qwen3guard
    check_output: bool = True      # V8
    required: bool = False         # True면 가드 모델이 없을 때 시작하지 않는다


@dataclass(frozen=True)
class ValidatorConfig:
    strict_novel_content: bool = True
    l5_depth: str = "present_focus"   # present_focus | anchor_block_only | off
    max_anchor_eojeol: int = 3        # (확장) 인용은 3어절 이하, 문장 통째 인용 금지. 0이면 끔


@dataclass(frozen=True)
class SessionConfig:
    log_dir: str = "logs"
    researcher_contact: str = "(연구자 연락처를 config에 입력하세요)"


@dataclass(frozen=True)
class Config:
    interview: InterviewConfig = field(default_factory=InterviewConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    source: str = "defaults"

    @property
    def log_dir(self) -> Path:
        p = Path(self.session.log_dir)
        return p if p.is_absolute() else CHATBOT_DIR / p

    def to_dict(self) -> dict:
        return asdict(self)

    def with_overrides(self, **dotted: object) -> "Config":
        """with_overrides(**{"llm.model": "gemma4:31b"}) — None 값은 무시."""
        cfg = self
        for key, value in dotted.items():
            if value is None:
                continue
            section, name = key.split(".", 1)
            sub = getattr(cfg, section)
            cfg = replace(cfg, **{section: replace(sub, **{name: value})})
        return cfg


_SECTIONS = {
    "interview": InterviewConfig, "llm": LLMConfig, "guard": GuardConfig,
    "validator": ValidatorConfig, "session": SessionConfig,
}


def load_config(path: str | Path | None = None) -> Config:
    """path가 없으면 config/default.toml. 'pilot'처럼 이름만 주면 config/pilot.toml."""
    if path is None:
        path = CONFIG_DIR / "default.toml"
    path = Path(path)
    if not path.suffix and not path.exists():
        path = CONFIG_DIR / f"{path}.toml"
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    kwargs = {}
    for name, cls in _SECTIONS.items():
        raw = data.get(name, {})
        known = {f.name for f in fields(cls)}
        unknown = set(raw) - known
        if unknown:
            raise ValueError(f"{path.name} [{name}]에 모르는 키가 있습니다: {sorted(unknown)}")
        kwargs[name] = cls(**raw)
    return Config(**kwargs, source=str(path))
