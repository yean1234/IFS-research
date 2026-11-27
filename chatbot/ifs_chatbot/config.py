"""설정 읽기. config/*.toml → Config 데이터클래스. CLI 인자로 일부를 덮어쓸 수 있다."""
from __future__ import annotations

import tomllib
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from .paths import CHATBOT_DIR, CONFIG_DIR


@dataclass(frozen=True)
class InterviewConfig:
    condition: str = "chatbot"                     # chatbot(조건 2) | static(조건 1)
    protocol: str = "elicitation_protocol.v1.4.json"  # shared/protocol/ 아래
    prompt_version: str = "1.0.0"                  # chatbot/prompts/v<버전>/
    # D9(감정어 → 심상 다리, config/bridge.toml). 둘 다 기본 꺼짐 — 켜지 않으면 기존 설정의 동작·기록은 그대로다.
    # lexicon_overlay: 면담용 1층 사전 v0에 더하는 오버레이(shared/lexicon/ 아래, 예 "layer1_interview.v0.json": 감정어 '기대')
    lexicon_overlay: str = ""
    # anchor_doe_root: 인용 후보에 '-되' 어근 규칙('기대되/VV' → '기대')을 더한다. '-하' 어근 규칙과 같은 꼴
    anchor_doe_root: bool = False
    # lock_condition: 면담 조건을 위 condition 값으로 고정한다. 켜면 시작 화면에 조건 선택이 없고(설정 조건을 한 줄로만 표시),
    # 세션 만들기 요청의 condition이 설정과 다르면 받지 않는다(409). 세션 기록 헤더에 conditionLocked: true가 남는다.
    # 기본 꺼짐 — 끄면 화면·서버·기록이 예전과 같다. 본 실험 설정(experiment.toml)만 켠다
    lock_condition: bool = False


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
    # L1 키워드 사전 파일(shared/lexicon/ 아래). D9 설정은 safety_ko.v0.2.json(은유 '숨막혀·막힌'을 잡음)을 쓴다
    safety_lexicon: str = "safety_ko.v0.json"


@dataclass(frozen=True)
class ValidatorConfig:
    strict_novel_content: bool = True
    l5_depth: str = "present_focus"   # present_focus | anchor_block_only | off
    max_anchor_eojeol: int = 3        # (확장) 인용은 3어절 이하, 문장 통째 인용 금지. 0이면 끔
    # (확장, D9) V7 predicate_as_noun: what_kind·where·like_what 틀의 X가 활용형('설레요')이면 막는다. 기본 꺼짐
    predicate_as_noun: bool = False


@dataclass(frozen=True)
class SessionConfig:
    log_dir: str = "logs"
    scenes_dir: str = ""          # 확정 텍스트 → SceneSpec v2 저장 폴더. 비우면 <log_dir>/scenes
    researcher_contact: str = "(연구자 연락처를 config에 입력하세요)"


@dataclass(frozen=True)
class MappingConfig:
    mode: str = "v1"              # 확정 텍스트 → SceneSpec 매핑. v1(개선 매핑) | v0(규칙 기반 기준선) | v2(D1·D2 수정, 선택)
    save_both: bool = True        # scenes/{sid}.v0.json · {sid}.v1.json도 저장(같은 텍스트를 두 매핑으로 — 비교 설계)
    clarify_loop: bool = False    # 확정 직후 what_kind 틀 확인 질문. 확증 비교에서는 끈다(research-design 3.2)
    clarify_max: int = 2          # 확인 질문 최대 횟수
    # True면 mode = "v1"인데 v1 빌더를 만들지 못할 때(시작 시점) v0로 넘어가지 않고 Runtime 생성에서 예외로 멈춘다.
    # 세션 도중 확정 시점의 v1 build 예외는 strict여도 v0 대체 + meta.mapping + 연구자 알림(참여자 세션을 끊지 않음).
    strict: bool = False
    # G61(매퍼 v2에서만, mode = "v2"). 비우면 끔 — 기본 출력은 builder 2.4.0·스펙 2.2.0과 바이트 단위로 같다.
    # ext_lexicon: 1층 사전 v2 오버레이(shared/lexicon/ 아래, 예 "layer1_lexicon.v2.json") → 스펙 2.3.0(윤곽·발광).
    #   ⚠ Unity가 2.3.0을 읽게 되기 전에는 켜지 않는다(헤드셋 러너·WebGL 미리보기의 엄격 파서가 모르는 버전을 거부)
    ext_lexicon: str = ""
    ext_params: str = "scene_params.v3.json"     # ext_lexicon을 켰을 때 읽는 대응표(서수 단계·정도·렌더 수치)
    # variant_rules: 형태 변이 규칙층(예 "variant_rules.v0.json"). 사전에 직접 없는 의태어 변이형의 뿌리를 규칙으로 찾는다
    variant_rules: str = ""
    # G72: 너비·높이·깊이 비율(layout.proportions, 스펙 2.4.0). 비율 표가 든 파일(shared/lexicon/ 아래, 예 "scene_params.v2.json" —
    #   그 proportions 표). 비우면 끔 — 출력은 그대로(스펙 2.2.0·2.3.0). Unity 러너·미리보기가 2.4.0을 읽는 빌드에서만 켠다
    proportions: str = ""


@dataclass(frozen=True)
class DriftConfig:
    enabled: bool = True          # 확정 직후 단계별 스냅샷으로 심상 유지(표류) 판정을 계산해 로그에 남긴다(참여자에게 안 보임)
    recall_check: bool = False    # Flesh out 뒤 회상 확인 고정 문구. 확증 비교에서는 끈다(심상을 다시 보게 해 비교를 교란)
    self_report: bool = False     # 확정 직후 자기보고 1–7 고정 문구. 문구가 draft라 IRB·팀 검토 뒤 켠다
    # 프로토콜에서 status = "draft"인 문구(recall_check·self_report_drift)를 쓰는 기능을 켜도 되는지.
    # False면 위 두 기능을 켜도 문구가 draft일 때 끄고 경고를 남긴다(원칙 7: IRB·팀 검토 전 문구). 개발·시연에서만 True
    allow_draft_phrases: bool = False


@dataclass(frozen=True)
class SelectionConfig:
    """면담 뒤 데스크톱 단계(4 후보 선택 · 5 조절 · 6 사전 측정). 기본은 꺼 둔다(기존 데모·파일럿 동작 그대로).
    새 흐름 프로필 config/v4.toml이 켠다."""
    enabled: bool = False
    protocol: str = "selection_protocol.v0.json"   # shared/protocol/ 아래
    table: str = "candidate_values.v2.json"        # shared/lexicon/ 아래(2.0.0: D6 기본 형상. 1.0.0·0.1.0 표는 v1·v0 파일)
    # 문구가 status = draft면 후보 단계를 시작하지 않는다(X35의 requireSpecPhrases와 같은 뜻). 기본 false: 시작하되 화면·기록에 알림
    require_spec_phrases: bool = False
    # 참여자 화면 맨 위 초안 문구 경고 줄(X35)을 참여자 보기에서도 보일지. false면 연구자 보기에서만 보임(기록의 draftCount·
    # draftKeys와 서버 경고는 그대로). 기본 true(지금과 같음). 숨길지는 사람이 정한다(G59)
    participant_draft_banner: bool = True
    # 사후 면담 기록 화면(/?view=postinterview&session=<ID>)이 읽는 문항 파일(shared/protocol/ 아래, G59). [selection] enabled일 때만 열림
    post_interview: str = "post_interview.v0.json"


@dataclass(frozen=True)
class PreviewConfig:
    """형상 미리보기 어댑터(preview.py). webgl | image | none."""
    mode: str = "none"
    webgl_dir: str = ""            # Unity WebGL 빌드 폴더(index.html). 상대 경로는 chatbot/ 기준. 없으면 none
    image_player: str = ""         # 상주 미리보기 플레이어(IFSPreview.exe, 저장소 밖). "fake" = 테스트용 가짜 렌더러. 없으면 none
    queue_dir: str = ""            # 플레이어 요청 폴더. 비우면 <log_dir>/preview-queue (git 밖)
    start_on_launch: bool = False  # true면 서버 시작 때 플레이어를 띄운다. false면 첫 요청 때
    width: int = 320
    height: int = 240
    start_timeout_s: float = 60.0
    request_timeout_s: float = 20.0
    # webgl 모드에서 브라우저 쪽 기다림 한도(stage.js). 넘으면 그 세션은 image(없으면 글 요약)로 내려간다
    webgl_ready_timeout_s: float = 30.0
    webgl_request_timeout_s: float = 15.0


@dataclass(frozen=True)
class Gen3DConfig:
    """G62: 형태 메시 후보를 로컬 생성 모델 산출물에서 더한다(form_assets.py). 기본은 꺼 둔다 — 꺼져 있으면 후보·selection.json·
    화면 출력이 G62 전과 바이트 단위로 같다. 챗봇은 모델을 부르지 않고, 생성 도구(tools/gen3d)가 assets_dir에 둔 GLB + 사이드카
    (form-asset.v0)를 확정 텍스트의 sha256으로 찾기만 한다. 켜는 설정: config/v4-gen3d.toml."""
    enabled: bool = False
    # 사이드카·GLB 폴더(저장소 밖 gen3d-out 관례, docs/gen3d-feasibility.md). 상대 경로는 chatbot/ 기준. 하위 폴더까지 찾는다
    assets_dir: str = "../../gen3d-out"
    max_candidates: int = 2        # 절차 메시 후보에 더할 생성 후보 최대 수(status ok + gate.passed만)
    # 어느 형태 후보가 기본(맨 앞에 보이고 미리 선택됨)인가. "procedural"(키가 없을 때) = 지금처럼 순환 순서·미리 선택 없음.
    # "generated" = 쓸 수 있는 생성 후보가 있으면 그 첫 후보가 기본(절차 후보는 대안으로 남김), 없으면 절차 메시가 기본(사유 기록).
    # "auto"(G62-i) = 말한 형태 낱말이 모두 단순 도형(shared/lexicon/primitive_forms.v0.json)이고 절차 메시가 그대로 그리면
    # procedural처럼, 그 밖의 사물 낱말이 하나라도 있으면 generated처럼(판정 근거는 generation.defaultFormRule·defaultFormBasis).
    # 기본이어도 참여자가 확정해야 장면에 쓴다(selection 0.3 defaultFormSource·selection.acceptedDefault)
    default_form_source: str = "procedural"


@dataclass(frozen=True)
class Config:
    interview: InterviewConfig = field(default_factory=InterviewConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    guard: GuardConfig = field(default_factory=GuardConfig)
    validator: ValidatorConfig = field(default_factory=ValidatorConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    mapping: MappingConfig = field(default_factory=MappingConfig)
    drift: DriftConfig = field(default_factory=DriftConfig)
    selection: SelectionConfig = field(default_factory=SelectionConfig)
    preview: PreviewConfig = field(default_factory=PreviewConfig)
    gen3d: Gen3DConfig = field(default_factory=Gen3DConfig)
    source: str = "defaults"

    @property
    def log_dir(self) -> Path:
        p = Path(self.session.log_dir)
        return p if p.is_absolute() else CHATBOT_DIR / p

    @property
    def scenes_dir(self) -> Path:
        """장면 파일(scenes/{sessionId}.json) 폴더. 참여자 데이터라 기본은 git 밖의 logs/scenes."""
        if not self.session.scenes_dir:
            return self.log_dir / "scenes"
        p = Path(self.session.scenes_dir)
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
    "validator": ValidatorConfig, "session": SessionConfig, "mapping": MappingConfig,
    "drift": DriftConfig, "selection": SelectionConfig, "preview": PreviewConfig, "gen3d": Gen3DConfig,
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
