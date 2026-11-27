"""확정 텍스트 → SceneSpec v2.2 — 매핑 v2 (화이트박스. 학습·LLM·임베딩 없음).

v1(scene_builder_v1.py)을 상속해 아래 차이만 더한다. v0·v1 코드·설정 파일은 바꾸지 않으므로 v0·v1 출력은 그대로다.
같은 확정 텍스트(+ 같은 meta 인자)는 언제나 같은 dict, 같은 파일 바이트가 된다(시각·난수·빌드 사이 상태 없음).
설정: shared/lexicon/scene_params.v2.json(규칙·수치), shared/lexicon/noun_stoplist.v2.json(불용 명사).
근거 문서: docs/prompts/prototype-v4-build.md 단계 D의 D1·D2, docs/validation/mock-forms/README.md 7절,
docs/mapping-audit.md A06·A14. 비교 결과: docs/validation/mapper-v2/README.md.

D1  사전에 없는 명사 기록
    확정 텍스트의 명사(NNG·NNP) 중 1층 사전에 없고, 값·보존 기록이 덮지 않았고, 불용 명사가 아닌 것을 _unmapped에
    category unlisted_noun으로 남긴다. value.role(조사로 본 문장 성분)과 value.scope(main | context: 회상·상황절)를 붙인다.
    배경 사물 목록(backgroundNouns)에 있는 낱말이 '있다'의 주어면 형상 자체로 보고 배경 판정에서 뺀다
    ('가슴 앞에 작은 화분이 있어요'의 '작은'이 v1에서는 배경 사물 속성으로 빠졌다).
D2  형상이 보이지 않게 되는 오류
    (a) '거의 투명' · '투명에 가까운' → opacity 0이 아니라 nearlyTransparent(0.15). '완전히 투명'은 말한 대로 0.
        '반쯤 투명' → 0.5. 그 밖의 강한 정도 부사로 0이 되면 하한 0.05. 부분 한정('끝은 거의 투명')은 _parts로.
    (b) layout.distance 하한 0.1('코앞'과 같은 값). 신체 부위에 '붙어'는 거리가 아니라 몸 위치 → _unmapped.
        G33(builder 2.1.0): 하한을 적용하면 provenance rule 끝에 '+floor(0.1;said=<말한 값>)'를 붙여 말한 값과 그려진 값
        (슬롯 값)을 둘 다 남긴다. floor_record()가 이 기록을 읽는다(selection.json distanceFloor).
        '머리 위 한 뼘쯤 높이'처럼 높이 말 옆의 수치는 거리로 쓰지 않음(_measurements dimension unknown).
    (c) 자세어가 참여자 자신의 상태를 말한 절(상황절 '누웠을 때'·'서 있으면', 1인칭 주어 '제가 서 있는',
        신체 부위 주어 '몸이 처져요')이면 form.posture에 넣지 않고 _context에 남긴다.
    (d) '가슴 앞을 덮고'의 '앞'은 덮음 크기 기준(시야 전체 1.7 m)이 아니라 위치다.

D6  기본 형상 경로(builder 2.2.0, 결정 G21·G30, docs/asset-plan.md 3절)
    형상을 이름 붙이는 명사(shared/lexicon/base_shapes.v1.json)가 주어·이름·직유 원천이고 본 장면 문장이며 부정되지 않았으면
    form.base(container·line·sheet·flame·drop)에 넣고, 낱말 뜻과 같은 문장의 참여자 말이 정한 변형값을 form.baseVariant에 넣는다.
    그 명사의 다른 기록(_unmapped의 object·shape·unlisted_noun)은 지운다(이제 값의 근거). 안전 제외 낱말은 그리지 않고
    _unmapped reason excluded_shape로 남긴다. 출력은 언제나 specVersion 2.2.0(form.base·baseVariant가 null이어도 적음).
    G37(builder 2.3.0): 제외 판정은 형태소 단위다. 명사 연속을 앞쪽의 띄어 쓴 맨 명사 어절까지 넓히고('해골 그릇'·'아이 장난감 상자')
    그 안의 Kiwi 명사 토큰 하나라도 제외 낱말이거나 제외 합성어 목록(excludedCompounds: '칼날'·'핏물')에 있으면 그 연속 전체를
    그리지 않는다. 부정된 것·직유 원천도 기록한다. 제외 낱말이 직유 원천이면('뱀 같은 끈') 같은 문장의 형상 낱말도 그리지 않고
    value.excludedBy를 남긴다. 기록을 바꿀 때 원래 사유는 value.priorReason에 둔다.
    G45–G51(builder 2.4.0)이 위 G37 판정을 대체: 명사구의 중심 명사가 목록 낱말(제외 person·threat·weapon·
    death_self_harm_trauma, 에셋 없음 animal)일 때만 그리지 않고(value.formSaid → 후보가 형태 자리를 벌림), 꾸미는 말·비교 원천이면
    중심 명사를 그린다. 넷째 범주(death_self_harm_trauma)는 어디에 나와도 형태 에셋을 막는다(색 비교 빼고, value.formBlock).
    동물은 reason no_asset. 목록 낱말이 나온 자리마다 기록(position·role·scope·sentence). 판정 못 하는 문형은 그리지 않고 기록
    (value.blockedBy, docs/validation/mapper-v2/head-noun-patterns.md).
    G38(builder 2.3.0): 낱말 뜻에서 온 변형값의 provenance source는 lexicon_implied(같은 문장의 참여자 말로 정한 값은 explicit_lexicon).

스키마 한계(스키마 2.2에서도 그대로): meta.mapping.used는 v0 | v1만 허용한다. v2는 requested = "v2",
used = "v1"(가장 가까운 값: v2는 v1 위의 수정), pipeline.builder = scene-spec-builder-v2/…로 남긴다.
대체 판정은 is_mapping_fallback()을 쓴다(v0·v1에서는 기존 판정 'used ≠ requested'와 같다).
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

from .extract import FUNCTION_LEMMAS
from .korean import Analyzer
from .lexicon import Hit, LexEntry, Lexicon
from .paths import shared
from .scene_builder import normalize_confirmed
from .scene_builder_v1 import (EOJEOL_TAG, NOUN_TAGS, PUNCT_TAGS, SIMILE_SKIP_TAGS, SKIP_LEXICON_CATEGORIES,
                               TOPIC_PARTICLES, Cand, Doc, SceneSpecBuilderV1,
                               fallback_spec)  # noqa: F401 (fallback_spec: 컨트롤러가 같은 대체 경로를 씀)
from .scene_spec import (EXT_SLOT_PATHS, MAPPING_USED_FOR, SPEC_VERSION_V22,  # noqa: F401 (v2 meta.mapping 규칙을 함께 내보냄)
                         SPEC_VERSION_V23, SPEC_VERSION_V24, is_mapping_fallback)
from .variants import VariantMatch, VariantRules, parse_tag

# 2.1.0(2026-11-23, G33): 거리 하한 꼬리표에 말한 값(said=…)을 더함
# 2.2.0(2026-11-23, D6·G30): 기본 형상 경로 form.base·form.baseVariant(스키마 2.2.0), 안전 제외 낱말 excluded_shape
# 2.3.0(2026-11-23, CP10 G37·G38): 안전 제외를 형태소 단위로(넓힌 명사 연속 안의 제외 형태소 하나라도, 합성어 목록, 부정·직유도
#       기록, 제외 낱말이 직유 원천이면 그 문장의 형상을 그리지 않음), 낱말 뜻에서 온 변형값의 source = lexicon_implied.
#       출력 specVersion은 그대로 2.2.0(스키마 2.2.0에 provenance source 값을 하나 더함 — decisions.md 'CP10 반영 세부')
# 2.4.0(2026-11-23, G45–G51): 제외·동물 판정을 명사구의 중심 명사로(꾸미는 말·비교 원천이면 중심 명사를 그림, 중심 명사면 그리지
#       않고 value.formSaid), 넷째 범주(죽음·자해·외상)는 어디에 나와도 형태를 막음(색 비교 빼고, value.formBlock), 동물은 reason
#       no_asset, 목록 낱말이 나온 자리마다 기록(위치·문장 번호·역할), '그릇처럼 생긴 거예요'가 그려지지 않던 문제(상황 문장 ②) 고침,
#       '같이'(JKB) 비교 표지. 출력 specVersion은 그대로 2.2.0(스키마 2.2.0 _unmapped.reason에 no_asset을 더함)
# 2.6.0(2026-11-27, 연구자 시험 입력 '구형·천' — scene_params.v2 2.1.0 shapePriority·neutralSize·surfaceTerms):
#       직접 형태 진술('모양은 구체'·'모형은 구형'·'동그란 원')이 형상 낱말·비유 원천보다 형태 슬롯에서 앞섬, 움직임 비유의
#       매개어('천이 펄럭이듯이 물체가 …', '천처럼 펄럭여요')는 형태 슬롯(form.base·form.type)을 채우지 않고 움직임 근거로,
#       모양 명사 '구형'·'구체'(球) → 모양어 round, '구체적'의 '구체'는 형태로 읽지 않음, '보통 크기' → layout.size 0.5,
#       '무광'·'유광' → material.roughness, 줄 끝 명사가 다음 줄 첫 명사를 꾸미는 것으로 읽히던 문장 성분 오류(_noun_role) 고침.
#       출력 specVersion은 그대로 2.2.0(스키마에 이미 있는 값·사유만 씀)
BUILDER_VERSION = "2.6.0"
BUILDER_ID = f"scene-spec-builder-v2/{BUILDER_VERSION}"
# 2.5.0(2026-11-26, G61 ①②): 선택 기능 두 가지. 둘 다 꺼져 있으면(기본) 출력과 builder 표기가 2.4.0과 바이트 단위로 같다
#       (G52와 같은 관례: 기본값이 아닐 때만 새 표기·새 키). 켰을 때만 builder = …/2.5.0.
#   ① ext_lexicon: 1층 사전 v2 오버레이(윤곽 contour·발광 emission) → 스펙 2.3.0(form.roundness·form.aspect·material.emission)
#   ② variant_rules: 형태 변이 규칙층(어미·파생 접사·겹친 꼴·의태어 모음·자음 교체, 뿌리가 사전에 있을 때만)
# 2.7.0(2026-11-27): 2.6.0의 고침 + G61 ①② 선택 기능(켰을 때만 이 표기)
BUILDER_VERSION_EXT = "2.7.0"
BUILDER_ID_EXT = f"scene-spec-builder-v2/{BUILDER_VERSION_EXT}"
# 2.8.0(2026-11-27, G72): [mapping] proportions를 켰을 때만 이 표기 — 너비·높이·깊이 비율(layout.proportions, 스펙 2.4.0).
#       참여자가 축을 말했을 때만 채운다('넓게 펼쳐진'·'넓적한'·'납작한'·'길쭉한'·'높이 솟은'·'가로로 긴' …, scene_params.v2 proportions 표).
#       결과 상태 꼴('펼쳐진'·'펼쳐져 있어요')은 형태 비율이고 그 용언은 움직임 값을 만들지 않는다. 진행 꼴('펼쳐져요')은 지금처럼 움직임.
#       G61 ①②를 함께 켜도 이 표기(2.7.0의 내용 포함). 꺼져 있으면 출력·표기는 2.6.0/2.7.0 그대로다
BUILDER_VERSION_PROP = "2.8.0"
BUILDER_ID_PROP = f"scene-spec-builder-v2/{BUILDER_VERSION_PROP}"
# 2.9.0(2026-11-27, G74): [mapping] mist_kinds를 켰을 때만 이 표기 — 안개 입자 모양(form.mistKind: fog·smoke·dust·cloud, 스펙 2.4.0의
#       선택 슬롯). 참여자가 안개·연기·먼지·구름 낱말을 형상 자리에서 말했을 때만 채운다(scene_params.v2 mistKinds 표).
#       [mapping] proportions도 켜야 한다(스펙 2.4.0). 꺼져 있으면 출력·표기는 2.8.0 그대로다
BUILDER_VERSION_MIST = "2.9.0"
BUILDER_ID_MIST = f"scene-spec-builder-v2/{BUILDER_VERSION_MIST}"
MAPPER_ID = "v2"
# 1층 사전 v2 오버레이의 새 범주. 매퍼 v1 경로(_lexicon_cands)에는 넣지 않고 _extension이 따로 읽는다
EXT_CATEGORIES = frozenset({"contour", "emission"})
# G38: 낱말 뜻(base_shapes 사전 항목 variant)에서 온 form.baseVariant 값의 provenance source. 참여자가 같은 문장에서 직접 한 말
# (variantCues)로 정해진 값은 다른 슬롯처럼 explicit_lexicon이다
IMPLIED_SOURCE = "lexicon_implied"

# 보존 기록 중 '이미 다룬 말'로 보는 필드(D1). _clauses(전체 원문 색인)·_uncertain(절 전체)·_unmatched는 넣지 않는다
_COVER_KEYS = ("_provenance", "_unmapped", "_negated", "_alternatives", "_context", "_parts", "_measurements",
               "_direction", "_needsConfirmation")
_LOCATION_JKB = {"에", "에서", "로", "으로", "에게", "한테", "께", "까지", "에다"}


def _span_chars(node, out: set[int]) -> None:
    """node 안의 모든 charSpan이 덮는 글자 위치."""
    if isinstance(node, dict):
        cs = node.get("charSpan")
        if isinstance(cs, (list, tuple)) and len(cs) == 2:
            out.update(range(int(cs[0]), int(cs[1])))
        for v in node.values():
            _span_chars(v, out)
    elif isinstance(node, list):
        for v in node:
            _span_chars(v, out)


class SceneSpecBuilderV2(SceneSpecBuilderV1):
    mapper_id = MAPPER_ID

    def __init__(self, analyzer: Analyzer, lexicon: Lexicon | None = None, params_path: str | Path | None = None,
                 vad_path: str | Path | None = None, v2_params_path: str | Path | None = None,
                 stoplist_path: str | Path | None = None, base_shapes_path: str | Path | None = None,
                 ext_lexicon_path: str | Path | None = None, ext_params_path: str | Path | None = None,
                 variant_rules_path: str | Path | None = None, proportions_path: str | Path | None = None,
                 mist_kinds_path: str | Path | None = None):
        """ext_lexicon_path(1층 사전 v2 오버레이)를 주면 스펙 2.3(윤곽·발광)을 내고, variant_rules_path를 주면 형태 변이
        규칙층을 켠다(G61). 둘 다 없으면(기본) 출력은 builder 2.4.0과 바이트 단위로 같다."""
        if ext_lexicon_path and lexicon is None:
            lexicon = load_lexicon_chain(analyzer, [shared("lexicon", "layer1_lexicon.v0.json"),
                                                    shared("lexicon", "layer1_lexicon.v1.json"), Path(ext_lexicon_path)])
        super().__init__(analyzer, lexicon, params_path, vad_path)
        self.ext: dict | None = None
        if ext_lexicon_path:
            p3 = json.loads(Path(ext_params_path or shared("lexicon", "scene_params.v3.json")).read_text(encoding="utf-8"))
            self.ext = p3
            self.ext_layer1: dict[str, list[dict]] = p3["layer1"]
            self.ext_levels: dict[str, tuple[list[str], str]] = {path: (d["levels"], d["neutral"])
                                                                for path, d in p3["ordinal"].items()}
            self.ext_negation: dict[str, str | None] = {k: v for k, v in p3["negation"].items() if k != "note"}
        self.variants: VariantRules | None = VariantRules(variant_rules_path) if variant_rules_path else None
        # G72: 너비·높이·깊이 비율 표(scene_params.v2.json proportions). 주지 않으면(기본) 출력은 그대로
        self.prop: dict | None = None
        if proportions_path:
            pf = json.loads(Path(proportions_path).read_text(encoding="utf-8"))
            self.prop = pf["proportions"]
            self.prop_info = f"{pf['lexiconId']}.proportions@{self.prop['tableVersion']}"
            self.prop_stems = {(s["form"], s["tag"]): s for s in self.prop["stems"]}
            for s in self.prop["stems"]:             # Kiwi가 XR 어근 + 하를 '<어근>하/VA' 한 토큰으로 자르는 때('납작한 안개예요')
                if s["tag"] == "XR":
                    self.prop_stems.setdefault((s["form"] + "하", "VA"), s)
            self.prop_background = frozenset(self.prop.get("extraBackgroundNouns", []))
            self.prop_preds = {r["form"]: r for r in self.prop["resultativePredicates"]}
        # G74: 안개 입자 모양 표(scene_params.v2.json mistKinds). 스펙 2.4.0의 선택 슬롯이라 비율 표(2.4.0)와 함께만 켠다
        self.mist: dict | None = None
        if mist_kinds_path:
            if self.prop is None:
                raise ValueError("[mapping] mist_kinds는 [mapping] proportions(스펙 2.4.0)와 함께 켜야 한다")
            mf = json.loads(Path(mist_kinds_path).read_text(encoding="utf-8"))
            self.mist = mf["mistKinds"]
            self.mist_info = f"{mf['lexiconId']}.mistKinds@{self.mist['tableVersion']}"
        self.p2 =json.loads(Path(v2_params_path or shared("lexicon", "scene_params.v2.json")).read_text(encoding="utf-8"))
        stop = json.loads(Path(stoplist_path or shared("lexicon", "noun_stoplist.v2.json")).read_text(encoding="utf-8"))
        self.stop_info = f"{stop['lexiconId']}@{stop['lexiconVersion']}"
        op, ds, po, un = self.p2["opacity"], self.p2["distance"], self.p2["posture"], self.p2["unlistedNouns"]
        self.op = op
        if op.get("partScoped"):
            self.part_scoped = set(self.part_scoped) | {"material.opacity"}
        self.opacity_nouns = set(op["opacityNouns"])
        self.dist_floor: float = ds["floor"]
        self.attach_lemmas = set(ds["bodyAttachLemmas"])
        self.attach_particles = set(ds["attachParticles"])
        self.self_words = set(ds["selfWords"]) | set(po["selfPronouns"])
        self.vertical_cues = set(ds["verticalCues"])
        self.sit_nouns = set(po["situationNouns"])
        self.cond_endings = set(po["conditionalEndings"])
        self.subj_particles = set(po["subjectParticles"])
        self.exist_preds = set(self.p2["figureNoun"]["existencePredicates"])
        self.noun_tags = set(un["tags"])
        # 불용 명사 = 표 + scene_params.v1의 부분·위치·차원·때 낱말(alsoExclude)
        words = {w for g in stop["groups"].values() for w in g["words"]}
        for ref in un["alsoExclude"]:
            node = self.params
            for part in ref.split("."):
                node = node[part]
            if isinstance(node, dict) and node and all(isinstance(x, list) for x in node.values()):
                words |= {w for ws in node.values() for w in ws}      # partNouns: 부류 → 낱말 목록
            else:
                words |= set(node)                                   # 목록, 또는 낱말이 키인 사전
        self.stop_nouns = frozenset(words)
        self.scene_time_nouns = frozenset(un["sceneTimeNouns"]) | set(self.v["contextSentence"]["situationNouns"])
        self.recall_verbs = frozenset(un["unambiguousRecallVerbs"])
        # 1층 사전의 모든 표제어·이형(범주 무관): 여기 있는 낱말은 '사전에 있는 말'
        self.lex_forms = frozenset(f for e in self.lexicon.entries for f in (e.lemma, *e.alt))
        # D6 기본 형상 사전
        bs = json.loads(Path(base_shapes_path or shared("lexicon", "base_shapes.v1.json")).read_text(encoding="utf-8"))
        self.bs = bs
        self.bs_info = f"{bs['lexiconId']}@{bs['lexiconVersion']}"
        self.bs_entries: dict[str, dict] = {e["lemma"]: e for e in bs["entries"]}
        # G45–G51(0.7.0): 목록 낱말 → (kind, 범주). kind excluded = 제외 범주(person·threat·weapon·death_self_harm_trauma),
        # no_asset = 에셋이 없어 그리지 않는 범주(animal). 합성어(compounds: Kiwi 한 토큰 '칼날'·'핏물')도 같은 범주
        self.bs_listed: dict[str, tuple[str, str]] = {}
        self.bs_strict: set[str] = set()
        self.bs_color_expr: set[str] = set()
        for cat, d in bs["excluded"]["categories"].items():
            for w in [*d["words"], *(d.get("added") or {}).get("words", []), *d.get("compounds", [])]:
                self.bs_listed.setdefault(w, ("excluded", cat))
            if d.get("strict"):
                self.bs_strict.add(cat)
            self.bs_color_expr |= set(d.get("colorExpressions", []))
        for cat, d in bs["noAsset"].items():
            if cat.startswith("_"):
                continue
            for w in [*d["words"], *(d.get("added") or {}).get("words", [])]:
                self.bs_listed.setdefault(w, ("no_asset", cat))
        self.bs_light_heads = frozenset(bs["rules"]["lightHeads"])
        self.bs_formal = frozenset(bs["rules"]["formalNouns"])
        self.bs_color_nouns = frozenset(bs["rules"]["colorNouns"])
        self.bs_roles = frozenset(bs["rules"]["roles"])
        self.bs_similes = bool(bs["rules"]["similes"])
        self.bs_numerals = frozenset(bs["rules"]["numeralDeterminers"])
        self.bs_cues: dict[str, dict] = {k: v for k, v in bs["variantCues"].items() if not k.startswith("_")}
        # 2.6.0: 형태 슬롯 우선순위(직접 형태 진술 > 비유 매개어)·모양 명사·보통 크기·광택 표면형(scene_params.v2 2.1.0)
        sp = self.p2["shapePriority"]
        self.act = sp["actionSimile"]
        self.dshape = sp["directShape"]
        self.frame_nouns = frozenset(self.dshape["frameNouns"])
        self.shape_nouns: dict[str, dict] = sp["shapeNouns"]
        self.shape_noun_reject = frozenset(sp["rejectNextXSN"])
        self.homonym_guards: dict[str, dict] = sp["homonymGuards"]
        self.neutral_size = self.p2["neutralSize"]
        self.surface_terms: dict[str, dict] = self.p2["surfaceTerms"]["terms"]
        self.speed_wish_aux = frozenset(self.p2["speedWish"]["auxiliaries"])

    # ── 외부 정보 ───────────────────────────────────────────────────────────────
    @classmethod
    def from_runtime(cls, rt) -> "SceneSpecBuilderV2":
        return cls(rt.analyzer)

    @property
    def builder_id(self) -> str:
        if self.mist is not None:
            return BUILDER_ID_MIST
        if self.prop is not None:
            return BUILDER_ID_PROP
        return BUILDER_ID_EXT if (self.ext is not None or self.variants is not None) else BUILDER_ID

    @property
    def spec_version(self) -> str:
        if self.prop is not None:
            return SPEC_VERSION_V24
        return SPEC_VERSION_V23 if self.ext is not None else SPEC_VERSION_V22

    def info(self) -> dict:
        return {"builder": self.builder_id, "specVersion": self.spec_version, "lexicons": self._lexicons(),
                "mapper": MAPPER_ID}

    def _lexicons(self) -> dict:
        out = {**super()._lexicons(),
               "sceneParamsV2": f"{self.p2['lexiconId']}@{self.p2['lexiconVersion']}",
               "nounStoplist": self.stop_info, "baseShapes": self.bs_info}
        # G61: 켠 기능만 키를 더한다(기본 출력의 키 목록은 그대로)
        if self.ext is not None:
            out["layer1Chain"] = getattr(self.lexicon, "chain_info", "")
            out["sceneParamsV3"] = f"{self.ext['lexiconId']}@{self.ext['lexiconVersion']}"
        if self.variants is not None:
            out["variantRules"] = self.variants.info
        if self.prop is not None:
            out["proportionsTable"] = self.prop_info
        if self.mist is not None:
            out["mistKindTable"] = self.mist_info
        return out

    # ── 진입점 ─────────────────────────────────────────────────────────────────
    def build(self, text: str, *, session_id: str | None = None, participant_id: str | None = None,
              condition: str | None = None) -> dict:
        spec = super().build(text, session_id=session_id, participant_id=participant_id, condition=condition)
        spec["meta"]["pipeline"]["builder"] = self.builder_id
        spec["meta"]["mapping"] = {"requested": MAPPER_ID, "used": MAPPING_USED_FOR[MAPPER_ID], "fallbackReason": None}
        # D1: v1 build가 끝난 spec 위에서 다시 분석한다(같은 분석기·같은 텍스트라 결정적. 빌드 사이 상태를 두지 않음)
        norm = normalize_confirmed(text)
        doc = Doc(norm, self.analyzer.tokens(norm))
        hits = list(self.lexicon.hits(norm))
        # 2.6.0: 모양 명사('구형'·'구체') → _unmapped shape. D1보다 먼저 넣어 사전에 없는 명사로 다시 남지 않게 한다
        shape_nouns = self._shape_noun_records(doc, spec)
        if shape_nouns:
            spec["_unmapped"] = spec["_unmapped"] + shape_nouns
        spec["_negated"].sort(key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
        added = self._unlisted_nouns(doc, hits, spec)
        if added or shape_nouns:
            spec["_unmapped"] = sorted(spec["_unmapped"] + added,
                                       key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"], u["category"]))
            # 기록한 명사는 '읽지 못한 말'이 아니다(사전 낱말이 _unmatched에 안 남는 것과 같게). 어절 항목은 다시 계산한다
            spans = sorted({tuple(u["_provenance"]["charSpan"]) for u in added + shape_nouns})
            tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG
                         and not any(s <= u["charSpan"][0] and u["charSpan"][1] <= e for s, e in spans)]
            spec["_unmatched"] = tok_level
            spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                        key=lambda u: (u["charSpan"][0], u["charSpan"][1]))
        # D6: 기본 형상(스키마 2.2.0). form 묶음의 키 순서는 type · posture · base · baseVariant
        base, variant, changed = self._base_shapes(doc, spec)
        spec["meta"]["specVersion"] = SPEC_VERSION_V22
        spec["form"] = {"type": spec["form"]["type"], "posture": spec["form"]["posture"], "base": base,
                        "baseVariant": variant}
        if changed:
            tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG]
            spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                        key=lambda u: (u["charSpan"][0], u["charSpan"][1]))
        # G61 ①: 윤곽·발광(스펙 2.3.0). 다른 슬롯·기록을 다 정한 뒤 따로 읽는다(2.2 슬롯의 결과는 바뀌지 않음)
        # G72: 너비·높이·깊이 비율(스펙 2.4.0). 형태 슬롯을 정한 뒤 읽는다(모양 모형이 그려지는지 봄)
        if self.prop is not None:
            self._proportions(doc, spec)
        if self.ext is not None:
            self._extension(doc, spec, hits)
            spec["meta"]["specVersion"] = SPEC_VERSION_V23
            _attach_variant_records(spec)
        if self.prop is not None:
            spec["meta"]["specVersion"] = SPEC_VERSION_V24
        # G74: 안개 입자 모양(form.mistKind, 2.4.0 선택 슬롯). 형태 슬롯을 다 정한 뒤 따로 읽는다(다른 슬롯은 바뀌지 않음)
        if self.mist is not None:
            self._mist_kind(doc, spec)
        return spec

    # ── D6: 기본 형상 ─────────────────────────────────────────────────────────
    def _base_role(self, doc: Doc, j: int) -> str:
        """base 판정용 문장 성분. '종이 한 장이'·'물방울 하나가'처럼 바로 뒤 어절이 수량 표현(관형사·수사·숫자 + 단위)이면
        그 수량 표현의 성분을 쓴다."""
        role = self._noun_role(doc, j)
        if role != "other":
            return role
        toks = doc.toks
        n = len(toks)
        k = j + 1
        while k < n and toks[k].base_tag == "XSN":
            k += 1
        if k + 1 < n and toks[k].base_tag == "JKC" and toks[k + 1].base_tag == "VCN" and doc.eoj[k] == doc.eoj[j]:
            return "named"                                       # (2.3.0) '사람이 아니에요' — 이름을 말하고 부정함
        if k >= n or doc.eoj[k] == doc.eoj[j] or toks[k].base_tag not in ("MM", "NR", "SN"):
            return role
        if toks[k].base_tag == "NR":
            return self._noun_role(doc, k)                       # '하나가'
        m = k + 1                                                # '한 장이' · '2 개가'
        if m < n and toks[m].base_tag in ("NNB", "NNG") and doc.eoj[m] in (doc.eoj[k], doc.eoj[k] + 1):
            return self._noun_role(doc, m)
        return role

    # ── G45–G51(builder 2.4.0): 명사구·중심 명사 ───────────────────────────────
    def _noun_runs(self, doc: Doc) -> list[tuple[int, int]]:
        """띄어쓰기 없이 붙은 명사 연속(같은 어절의 NNG·NNP 토큰) — (첫 토큰, 끝 토큰)."""
        toks = doc.toks
        n = len(toks)
        out, i = [], 0
        while i < n:
            if toks[i].base_tag not in NOUN_TAGS:
                i += 1
                continue
            j = i
            while j + 1 < n and toks[j + 1].base_tag in NOUN_TAGS and toks[j + 1].start == toks[j].end \
                    and doc.eoj[j + 1] == doc.eoj[i]:
                j += 1
            out.append((i, j))
            i = j + 1
        return out

    def _phrases(self, doc: Doc) -> list[dict]:
        """명사구 = 명사 연속 앞에 띄어 쓴 맨 명사 어절(조사 없이 명사만 있는 어절, 같은 절)을 붙인 것('아이 장난감 상자',
        '사람 형상', '피 웅덩이'). 중심 명사(head) = 명사구의 마지막 명사 토큰, 단 그것이 lightHeads('형상'·'모습'·'모양'·
        '그림자'·'끝' …)이고 앞에 명사가 있으면 앞 명사로 옮긴다('사람 형상' → 사람, '칼끝' → 칼). 나머지 명사는 꾸미는 말."""
        toks = doc.toks
        phrases: list[dict] = []
        for a, b in self._noun_runs(doc):
            prev = phrases[-1] if phrases else None
            if prev is not None:
                pa, pb = prev["runs"][-1]
                e = doc.eoj[pb]
                if (doc.eojeols[e][0] == pa and doc.eojeols[e][1] == pb and doc.eoj[a] == e + 1
                        and doc.eojeols[e + 1][0] == a and doc.clause[a] == doc.clause[pb]):
                    prev["runs"].append((a, b))
                    continue
            phrases.append({"runs": [(a, b)]})
        for k, p in enumerate(phrases):
            nouns = [x for a, b in p["runs"] for x in range(a, b + 1)]
            h = len(nouns) - 1
            while h > 0 and toks[nouns[h]].form in self.bs_light_heads:
                h -= 1
            head = nouns[h]
            ha, hb = next((a, b) for a, b in p["runs"] if a <= head <= b)
            p.update(id=k, nouns=nouns, head=head, headRun=(ha, hb), a=p["runs"][0][0], b=p["runs"][-1][1])
            p["s"], p["e"] = toks[p["a"]].start, toks[p["b"]].end
            p["hs"], p["he"] = toks[ha].start, toks[hb].end
            p["lemma"] = doc.text[p["hs"]:p["he"]]                       # 중심 명사가 든 명사 연속(형상 낱말 맞춤 단위)
            # 형상 낱말은 명사 연속 전체 글자로 맞춘다(D6 그대로: '종이컵'은 '컵'이 아님). 중심 명사가 연속의 끝일 때만
            p["entry"] = self.bs_entries.get(p["lemma"]) if head == hb else None
            p["role"] = self._base_role(doc, p["b"])
        # 나열('뱀이랑 끈이 있어요'): 접속 조사(JC) 뒤 명사구의 성분을 따른다
        for p in reversed(phrases):
            k = p["b"] + 1
            while k < len(toks) and toks[k].base_tag == "XSN":
                k += 1
            if p["role"] == "other" and k < len(toks) and toks[k].base_tag == "JC" and p["id"] + 1 < len(phrases):
                p["role"] = phrases[p["id"] + 1]["role"]
        return phrases

    def _listed(self, form: str) -> tuple[str, str] | None:
        """(kind, 범주): kind excluded(G46·G50 제외 범주) | animal(G46·G51 에셋 없음)."""
        return self.bs_listed.get(form)

    _MARKERS = {("처럼", "JKB"): "처럼", ("마냥", "JKB"): "마냥", ("마냥", "MAG"): "마냥", ("같", "VA"): "같은",
                ("듯", "NNB"): "듯한", ("듯", "XR"): "듯한", ("같이", "JKB"): "같이"}

    def _simile_markers(self, doc: Doc) -> list[dict]:
        """비교 표지(v1 직유의 처럼·마냥·같은·듯한 + '같이'(JKB, '피같이 빨간'))와 그 원천 명사(표지 앞 명사, 조사·접미사
        '들'(XSN, '사람들 같은')은 건너뜀). v1 _similes와 같은 규칙에 XSN·'같이'만 더했다(v1 출력은 바뀌지 않음)."""
        toks = doc.toks
        out = []
        for i, t in enumerate(toks):
            marker = self._MARKERS.get((t.form, t.base_tag))
            if marker is None:
                continue
            j = i - 1
            while j >= 0 and toks[j].base_tag in (*SIMILE_SKIP_TAGS, "XSN"):
                j -= 1
            if j < 0 or toks[j].base_tag not in NOUN_TAGS:
                continue
            out.append({"marker": marker, "srcIndex": j, "markerIndex": i})
        return out

    def _attach(self, doc: Doc, k: int, before: int, phrase_of: dict[int, dict], color_toks: set[int]) -> tuple[str, object]:
        """꾸밈말·비교 표지(토큰 k)가 가리키는 대상. ('phrase', 명사구) | ('formal', 토큰) | ('color', None) | ('unresolved', None).
        ① 관형형(같은 · 처럼 생긴 · 네모난): 뒤 명사구(사이의 다른 관형형 어절은 건너뜀). 형식 명사('것'·'거'·'무엇')면 formal,
           중심 명사가 색 명사('색'·'빛')면 color. ② 서술형(같아요 · 처럼 생겼어요 · 네모나요): 같은 절의 앞 주어, 없으면 같은
           문장의 앞 절 주어(가까운 것부터). 주어가 대명사·형식 명사면 그 절의 서술 명사('그건 뱀인데')를, 없으면 unresolved.
        비교 표지 바로 뒤 용언이 색 낱말('피처럼 붉은', '피같이 빨개요')이면 color(G50 (2) 색 비교). before = 대상 주어를
        찾을 때 이 토큰 앞만 본다(비교 원천 명사의 첫 토큰)."""
        toks = doc.toks
        n = len(toks)
        e = doc.eoj[k]
        ne = len(doc.eojeols)
        last = doc.eojeols[e][1]
        color = any(x in color_toks for x in range(k + 1, last + 1))
        attributive, nxt = False, None
        if toks[last].base_tag == "ETM":
            attributive, nxt = True, e + 1
        elif toks[last].base_tag in ("JKB", "MAG") and e + 1 < ne and doc.eoj_clause(e + 1) == doc.clause[k]:
            e2 = e + 1
            color = color or any(x in color_toks for x in doc.etoks(e2))
            if toks[doc.eojeols[e2][1]].base_tag == "ETM":
                attributive, nxt = True, e2 + 1
        if color:
            return "color", None
        if attributive:
            while nxt < ne and toks[doc.eojeols[nxt][1]].base_tag == "ETM" \
                    and toks[doc.eojeols[nxt][0]].base_tag not in NOUN_TAGS:
                nxt += 1                                         # '뱀 같은 긴 끈' — 사이 관형형 어절
            if nxt >= ne:
                return "unresolved", None
            x = doc.eojeols[nxt][0]
            t = toks[x]
            if (t.base_tag == "NNB" and t.form in self.bs_formal) or (t.base_tag == "NP" and t.form in self.bs_formal):
                return "formal", x
            if t.base_tag in NOUN_TAGS and x in phrase_of:
                p = phrase_of[x]
                if toks[p["head"]].form in self.bs_color_nouns:
                    return "color", None
                return "phrase", p
            return "unresolved", None
        # 서술형: 주어
        c = doc.clause[k]
        subj = self._subject_in(doc, [x for x in doc.clause_toks(c) if x < before])
        cc = c - 1
        while subj is None and cc >= 0:
            ids = doc.clause_toks(cc)
            if not ids or doc.sent[ids[0]] != doc.sent[k]:
                break
            subj = self._subject_in(doc, ids)
            cc -= 1
        if subj is None:
            return "unresolved", None
        if toks[subj].base_tag in NOUN_TAGS and subj in phrase_of:
            return "phrase", phrase_of[subj]
        # '그건 뱀인데 끈처럼 가늘어요' — 대명사·형식 명사 주어의 서술 명사
        named = [p for p in {id(v): v for v in phrase_of.values()}.values()
                 if doc.clause[p["b"]] == doc.clause[subj] and p["b"] > subj and p["role"] == "named"]
        if named:
            return "phrase", min(named, key=lambda p: p["a"])
        return "unresolved", None

    def _retracted(self, doc: Doc, b: int) -> bool:
        """'끈, 아니 뱀이에요'·'끈이에요. 아니, 뱀이에요' — 명사구(이름만 말한 어절이면 그 끝) 바로 뒤(쉼표·마침표 건너뜀)에
        감탄사 '아니'가 오면 앞 말을 거둬들인 것."""
        toks = doc.toks
        k = b + 1
        while k < len(toks) and doc.eoj[k] == doc.eoj[b] and toks[k].base_tag in ("XSN", "VCP", "EF", "JX"):
            k += 1                                               # '끈이에요. 아니, …' — 이름만 말한 어절의 끝
        while k < len(toks) and toks[k].base_tag in ("SP", "SF"):
            k += 1
        return k < len(toks) and toks[k].form in ("아니", "아뇨") and toks[k].base_tag == "IC"

    def _base_shapes(self, doc: Doc, spec: dict) -> tuple[str | None, dict | None, bool]:
        """형상 낱말 → form.base. (base, baseVariant, spec 기록을 바꿨는지). spec의 기록 필드를 제자리에서 고친다.
        G45–G51(builder 2.4.0): 명사구의 중심 명사로 판정한다(decisions.md 'G45–G51 구현 세부')."""
        toks, text = doc.toks, doc.text
        valued: set[int] = set()
        _span_chars(spec.get("_provenance"), valued)
        recall_sents = self._context_sentences(doc)
        regions = self._situation_regions(doc)
        phrases = self._phrases(doc)
        # G48: 기록의 문장 번호(0부터) — 문장부호만 있는 조각은 세지 않는다(Doc.sent는 '있어요.'의 '.'도 따로 셈)
        sent_no = {sv: k for k, sv in enumerate(sorted({doc.sent[i] for i, t in enumerate(toks) if t.base_tag not in PUNCT_TAGS}))}
        phrase_of = {x: p for p in phrases for x in p["nouns"]}
        by_last = {p["b"]: p for p in phrases}
        color_toks = {h.token_index for h in self.lexicon.hits(text) if h.entry.category == "color"}
        similes = self._simile_markers(doc)
        # 비교 원천 명사구 → (표지, 대상)
        sim_of: dict[int, dict] = {}
        for sm in similes:
            p = by_last.get(sm["srcIndex"])
            if p is None or p["id"] in sim_of:
                continue
            kind, tgt = self._attach(doc, sm["markerIndex"], p["a"], phrase_of, color_toks)
            if kind == "phrase" and tgt is p:
                kind, tgt = "unresolved", None
            sim_of[p["id"]] = {"marker": sm["marker"], "kind": kind, "target": tgt, "markerIndex": sm["markerIndex"]}
        # '그릇처럼 생긴 거예요'(형식 명사가 비교 대상): D1 상황 문장 추정 ②가 '거'를 상황 명사로 보아 문장 전체를 맥락으로
        # 뺐다(알려진 문제). 비교 대상인 형식 명사 앞의 관형형은 ②에서 빼고 본다
        formal_etm = {sv["target"] - 1 for sv in sim_of.values() if sv["kind"] == "formal" and sv["target"] > 0
                      and toks[sv["target"] - 1].base_tag == "ETM"}
        context_sents = recall_sents | self._situation_sentences(doc, valued, skip_etm=formal_etm)
        used: set[int] = set()
        _span_chars({k: v for k, v in (spec.get("_provenance") or {}).items() if k != "form.type"}, used)
        for key in ("_measurements", "_parts", "_context"):
            _span_chars(spec.get(key), used)

        def in_region(p):
            return any(s0 <= p["a"] and p["b"] < k0 for s0, k0 in regions)

        def size_or_count(p) -> bool:
            a, b = p["a"], p["b"]
            if any(c in used for c in range(p["hs"], p["he"])):
                return True                                      # 크기 비교 기준 등 다른 값의 근거
            if a > 0 and doc.eoj[a - 1] != doc.eoj[a] and (toks[a - 1].base_tag in ("NR", "SN") or (
                    toks[a - 1].base_tag == "MM" and toks[a - 1].form in self.bs_numerals)):
                return True                                      # '한 컵'·'두 그릇' — 수량 단위
            k = b + 1
            while k < len(toks) and toks[k].base_tag == "XSN":
                k += 1
            return k < len(toks) and ((toks[k].form == "만" and toks[k].base_tag == "JX" and k + 1 < len(toks)
                                       and toks[k + 1].form == "하")
                                      or (toks[k].form in ("만큼", "정도", "크기") and doc.eoj[k] in (doc.eoj[b], doc.eoj[b] + 1)))

        # ── 명사구마다: 형태를 말한 자리인가(formSaid 후보), 부정 ─────────────
        for p in phrases:
            sv = sim_of.get(p["id"])
            p["sim"] = sv
            neg = Lexicon._negated(toks, p["b"]) or self._noun_negated(doc, p["b"])
            if sv is not None and sv["kind"] == "formal":
                neg = neg or Lexicon._negated(toks, sv["target"])     # '칼 같은 건 아니고'
            p["retracted"] = self._retracted(doc, p["b"])
            p["negated"] = bool(neg or p["retracted"])
            p["sent"] = doc.sent[p["head"]]
            # 형태 자리: 주어·이름(D6) 또는 대상이 형식 명사·불명인 비교 원천('실 같은 게', '뱀처럼 생긴 것', '뱀 같아요')
            # 또는 대상 명사구가 있어도 그 대상이 형상 낱말·목록 낱말이 아닌 비교 원천('실 같은 연기' — D6 그대로)
            p["formSlot"] = p["role"] in self.bs_roles or (sv is not None and sv["kind"] in ("formal", "unresolved"))
            p["simSlot"] = sv is not None and sv["kind"] == "phrase"
        listed_head = {}                                          # 명사구 id → (kind, 범주): 중심 명사가 목록 낱말
        for p in phrases:
            lk = self._listed(toks[p["head"]].form)
            if lk is not None:
                listed_head[p["id"]] = lk

        # ── 목록 낱말이 나온 자리마다 기록(G48: 여러 번 나오면 각각) ────────────
        occ: list[dict] = []
        for p in phrases:
            for x in p["nouns"]:
                lk = self._listed(toks[x].form)
                if lk is None:
                    continue
                kind, cat = lk
                strict = cat in self.bs_strict
                scope = "context" if (doc.sent[x] in recall_sents or in_region(p)) else "main"
                if scope == "context" and not strict:
                    continue                                     # 회상·상황 문장(D6·CP10과 같음). 넷째 범주는 기록(G50 (4))
                sv = p["sim"]
                nxt = phrases[p["id"] + 1] if p["id"] + 1 < len(phrases) else None
                if x != p["head"]:
                    pos, head_ref = "modifier", (p["lemma"], [p["hs"], p["he"]])
                elif p["role"] == "modifier" and sv is None and nxt is not None:
                    pos, head_ref = "modifier", (nxt["lemma"], [nxt["hs"], nxt["he"]])     # '아이의 상자'(JKG)
                elif sv is not None and sv["kind"] == "phrase":
                    t = sv["target"]
                    pos, head_ref = "simile_source", (t["lemma"], [t["hs"], t["he"]])
                elif sv is not None and sv["kind"] == "color":
                    pos, head_ref = "color_comparison", None
                else:
                    pos, head_ref = "head", None
                if toks[x].form in self.bs_color_expr:
                    pos = "color_expression"                      # '핏빛' — 뜻이 색인 낱말(G50 (2))
                form_said = (pos == "head" and scope == "main" and p["formSlot"] and not p["negated"]
                             and not size_or_count(p) and doc.sent[p["b"]] not in context_sents)
                occ.append({"tok": x, "form": toks[x].form, "s": toks[x].start, "e": toks[x].end, "phrase": p,
                            "role": p["role"] if x == p["head"] else "modifier",
                            "kind": kind, "cat": cat, "strict": strict, "pos": pos,
                            "head": head_ref, "scope": scope, "formSaid": bool(form_said),
                            "formBlock": strict and pos not in ("color_comparison", "color_expression")})
        # Kiwi가 목록 낱말을 명사로 내지 못한 어절('아이 모습이' → 아/IC 이/MM): 어절 글자 전체가 목록 낱말과 같을 때만
        # 기록한다(position unanalyzed, 형태 자리는 판정하지 않음. 넷째 범주면 엄격한 쪽 — 형태를 막음). G49 표 참고
        for e in range(len(doc.eojeols)):
            ids = list(doc.etoks(e))
            lk = self._listed(doc.etext(e))
            if lk is None or any(toks[x].base_tag in NOUN_TAGS for x in ids) or doc.is_punct_eoj(e):
                continue
            kind, cat = lk
            strict = cat in self.bs_strict
            scope = "context" if doc.sent[ids[0]] in recall_sents else "main"
            if scope == "context" and not strict:
                continue
            es, ee = doc.espan(e)
            pseudo = {"id": -1 - e, "sent": doc.sent[ids[0]], "negated": False, "retracted": False, "sim": None,
                      "role": "other", "lemma": doc.etext(e)}
            occ.append({"tok": None, "form": doc.etext(e), "s": es, "e": ee, "phrase": pseudo, "role": "other",
                        "kind": kind, "cat": cat, "strict": strict, "pos": "unanalyzed", "head": None, "scope": scope,
                        "formSaid": False, "formBlock": strict})
        occ.sort(key=lambda o: o["s"])
        said_listed = [o for o in occ if o["formSaid"]]
        strict_block = [o for o in occ if o["formBlock"]]

        # ── 형상 낱말 후보(D6) ──────────────────────────────────────────────
        hits: list[dict] = []
        for p in phrases:
            if p["entry"] is None or p["id"] in listed_head:
                continue
            if doc.sent[p["b"]] in context_sents or in_region(p) or size_or_count(p):
                continue
            sv = p["sim"]
            if not (p["formSlot"] or p["simSlot"]):
                continue                                         # 장소·목적어·꾸밈말
            if sv is not None and sv["kind"] == "color":
                continue                                         # '실처럼 붉은 …' — 색 비교 기준(형상 이름 아님)
            hits.append({"p": p, "lemma": p["lemma"], "entry": p["entry"], "s": p["hs"], "e": p["he"],
                         "b": p["headRun"][1], "negated": p["negated"], "simile": sv, "blockedBy": None})

        def block(h, o, rule):
            if h["blockedBy"] is None:
                h["blockedBy"] = {"lemma": o["form"], "charSpan": [o["s"], o["e"]], "category": o["cat"],
                                  "kind": o["kind"], "rule": rule}

        occ_by_phrase: dict[int, list[dict]] = {}
        for o in occ:
            occ_by_phrase.setdefault(o["phrase"]["id"], []).append(o)

        def head_occ(p):
            return next((o for o in occ_by_phrase.get(p["id"], []) if o["tok"] == p["head"]), None)

        def head_listed(p):
            lk = listed_head.get(p["id"])
            if lk is None:
                return None
            t = toks[p["head"]]
            return head_occ(p) or {"tok": p["head"], "form": t.form, "s": t.start, "e": t.end, "kind": lk[0], "cat": lk[1]}

        for h in hits:
            p, sv = h["p"], h["simile"]
            # G50 (1): 넷째 범주가 (색 비교·색 표현 말고) 나오면 형태 에셋을 내지 않는다
            if strict_block:
                block(h, strict_block[0], "strict_category")
                continue
            # G45: 비교 원천인데 대상(중심 명사)이 목록 낱말('끈 같은 뱀')
            if sv is not None and sv["kind"] == "phrase":
                o = head_listed(sv["target"])
                if o is not None:
                    block(h, o, "simile_target")
                continue
            # G49 보수적 기본: 대상을 정하지 못한 비교('… 끈 같아요')·대명사 주어는 같은 문장이나 앞 문장에 형태 자리의
            # 목록 낱말이 있으면 그리지 않는다
            if sv is not None and sv["kind"] == "unresolved":
                o = next((o for o in said_listed if o["phrase"]["sent"] <= p["sent"]), None)
                if o is not None:
                    block(h, o, "unresolved_reference")
                    continue
            # 같은 절의 주어 ↔ 서술 명사('끈이 뱀이에요', '뱀이 끈이에요'): 하나가 목록 낱말이면 그리지 않음
            if p["role"] in ("subject", "named"):
                for q in phrases:
                    if q is p or doc.clause[q["b"]] != doc.clause[p["b"]] or {q["role"], p["role"]} != {"subject", "named"}:
                        continue
                    lo, hi = sorted((q["b"], p["b"]))
                    if any(toks[z].base_tag == "ETM" for z in range(lo, hi)):
                        continue                                 # '아이가 가진 상자' — 앞 주어는 관형절의 주어
                    o = head_listed(q)
                    if o is not None and not q["negated"]:
                        block(h, o, "copula")
                        break

        changed = False
        unmapped = spec["_unmapped"]

        def convert(lo: int, hi: int, lemmas: set[str], reason: str, value: dict) -> bool:
            """[lo, hi)와 겹치고 낱말이 같은 기록(사물·모양어·사전에 없는 명사, 직유 원형 대기 포함)을 바꾼다. 원래 사유는
            value.priorReason(G40: 바꾸면서 정보를 지우지 않음)."""
            hit = False
            for u in unmapped:
                cs = u["_provenance"]["charSpan"]
                if u["category"] not in ("object", "shape", "unlisted_noun") or not (cs[0] < hi and lo < cs[1]) \
                        or u["lemma"] not in lemmas:
                    continue
                if u["reason"] not in ("excluded_shape", "no_asset"):
                    old = u["value"] or {}
                    u["value"] = {**{k: v for k, v in old.items() if k not in value}, "priorReason": u["reason"], **value}
                    u["reason"] = reason
                hit = True
            return hit

        # 목록 낱말 기록
        for o in occ:
            changed = True
            x, p = o["tok"], o["phrase"]
            form, ts, te = o["form"], o["s"], o["e"]
            reason = "no_asset" if o["kind"] == "no_asset" else "excluded_shape"
            val = {"noun": form, ("noAsset" if o["kind"] == "no_asset" else "excluded"): o["cat"],
                   "position": o["pos"], "role": o["role"], "scope": o["scope"], "sentence": sent_no.get(p["sent"] if x is None else doc.sent[x]),
                   "formSaid": o["formSaid"], "usedForShape": False}
            if o["strict"]:
                val["strict"] = True
                val["formBlock"] = o["formBlock"]
            if o["head"] is not None:
                val["head"] = {"lemma": o["head"][0], "charSpan": o["head"][1]}
            if p["negated"]:
                val["negated"] = True
            if p["retracted"]:
                val["retracted"] = True
            if p["sim"] is not None and x == p["head"]:
                val["simile"] = p["sim"]["marker"]
            # 1층 직유 원형이 목록 낱말의 뒷부분으로 형태 값을 냈으면('핏방울 같은' → 방울 → blob) 그 값을 쓰지 않는다
            # (형상 자체가 목록 낱말이거나 넷째 범주일 때. 합성어 목록의 용도와 같음 — G47)
            if o["formSaid"] or o["formBlock"]:
                ft = [pv for pv in (spec["_provenance"].get("form.type") or [])
                      if pv.get("source") == "simile_marker" and pv["charSpan"][0] < te and ts < pv["charSpan"][1]]
                if ft:
                    val["blockedValue"] = {"path": "form.type", "value": spec["form"]["type"], "rule": ft[0]["rule"]}
                    rest = [pv for pv in spec["_provenance"]["form.type"] if pv not in ft]
                    if rest:
                        spec["_provenance"]["form.type"] = rest
                    else:
                        spec["_provenance"].pop("form.type")
                        spec["form"]["type"] = None
            if not convert(ts, te, {form, p["lemma"]} if x is not None and x == p["head"] else {form}, reason, val):
                cat_name = "no_asset_noun" if o["kind"] == "no_asset" else "excluded_noun"
                unmapped.append({"lemma": form, "category": cat_name, "value": val, "reason": reason,
                                 "_provenance": self._prov("explicit_lexicon", text, ts, te,
                                                           f"baseShapes.{'noAsset' if o['kind'] == 'no_asset' else 'excluded'}"
                                                           f".{o['cat']}.{form}")})

        # 막힌 형상 낱말: 그 낱말의 기록을 바꾸고(없으면 새로) blockedBy에 막은 말과 규칙
        for h in hits:
            bl = h["blockedBy"]
            if bl is None:
                continue
            changed = True
            reason = "no_asset" if bl["kind"] == "no_asset" else "excluded_shape"
            val = {"noun": h["lemma"], "blockedBy": {k: bl[k] for k in ("lemma", "charSpan", "category", "rule")},
                   "sentence": sent_no.get(doc.sent[h["b"]]), "usedForShape": False}
            if not convert(h["s"], h["e"], {h["lemma"]}, reason, val):
                unmapped.append({"lemma": h["lemma"], "category": "base_shape", "value": val, "reason": reason,
                                 "_provenance": self._prov("explicit_lexicon", text, h["s"], h["e"],
                                                           f"baseShapes.{h['lemma']}+blocked({bl['rule']})")})

        # 모양어(_unmapped category shape): 목록 낱말을 꾸미거나 가리키면 모형으로 그리지 않는다
        if occ:
            for u in unmapped:
                if u["category"] != "shape" or u["reason"] in ("excluded_shape", "no_asset"):
                    continue
                cs = u["_provenance"]["charSpan"]
                ids = doc.toks_in(cs[0], cs[1])
                if not ids:
                    continue
                o, rule = None, None
                if strict_block:
                    o, rule = strict_block[0], "strict_category"
                else:
                    x0 = ids[0]
                    pq = phrase_of.get(x0)
                    if pq is not None:                           # 명사 모양어('동그라미 같은 뱀', '네모 귀신')
                        sv = pq["sim"]
                        if sv is not None:
                            kind, tgt = sv["kind"], sv["target"]
                        else:                                    # 꾸미는 자리면 그 명사구의 중심, 중심이면 따로 볼 것 없음
                            kind, tgt = ("phrase", pq) if x0 != pq["head"] else (None, None)
                    else:
                        kind, tgt = self._attach(doc, ids[-1], ids[0], phrase_of, color_toks)
                    if kind == "phrase" and tgt is not None and head_listed(tgt) is None and tgt["sim"] is not None                             and tgt["sim"]["kind"] == "phrase":
                        tgt = tgt["sim"]["target"]                   # '긴 끈 같은 귀신' — 꾸민 말이 다시 비교 원천
                    if kind == "phrase" and tgt is not None and head_listed(tgt) is not None:
                        o, rule = head_listed(tgt), "modifier_of_listed_head"
                    elif kind in ("unresolved", "formal"):
                        sent_u = doc.sent[ids[0]]
                        o = next((o for o in said_listed if o["phrase"]["sent"] <= sent_u), None)
                        rule = "unresolved_reference"
                if o is None:
                    continue
                changed = True
                bl = {"lemma": o["form"], "charSpan": [o["s"], o["e"]], "category": o["cat"], "rule": rule}
                u["value"] = {**(u["value"] or {}), "priorReason": u["reason"], "blockedBy": bl,
                              "sentence": sent_no.get(doc.sent[ids[0]]), "usedForShape": False}
                u["reason"] = "no_asset" if o["kind"] == "no_asset" else "excluded_shape"

        # 부정·거둬들인 형상 낱말: _negated에 남긴다(이미 있으면 그대로)
        for h in hits:
            if not h["negated"]:
                continue
            if not any(x["_provenance"]["charSpan"] == [h["s"], h["e"]] for x in spec["_negated"]):
                changed = True
                rule = f"baseShapes.{h['lemma']}" + ("+retracted(아니)" if h["p"]["retracted"] else "")
                spec["_negated"].append({"lemma": h["lemma"], "category": "base_shape",
                                         "_provenance": self._prov("explicit_lexicon", text, h["s"], h["e"], rule)})
        if changed:
            spec["_negated"].sort(key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
            unmapped.sort(key=lambda u: (u["_provenance"]["charSpan"][0], u["lemma"], u["category"]))

        def prov(h: dict, rule: str) -> dict:
            sim = h["simile"]
            src = "simile_marker" if sim is not None else "explicit_lexicon"
            tail = f"+simile({sim['marker']})" if sim is not None else ""
            return self._prov(src, text, h["s"], h["e"], rule + tail)

        def drop_records(h: dict) -> None:
            # 이 명사의 다른 기록(사물·모양어·사전에 없는 명사, 직유 원형 대기 포함)은 이제 값·대안의 근거이므로 지운다.
            # 같은 낱말이고 구간이 겹치는 것만(직유 기록의 구간은 '상자 같'처럼 표지까지 덮는다)
            unmapped[:] = [u for u in unmapped if not (u["lemma"] == h["lemma"]
                                                       and u["category"] in ("object", "shape", "unlisted_noun")
                                                       and u["_provenance"]["charSpan"][0] < h["e"]
                                                       and h["s"] < u["_provenance"]["charSpan"][1])]

        # 2.6.0: 움직임 비유의 매개어('천이 펄럭이듯이 물체가 …', '천처럼 펄럭여요')와, 직접 형태 진술('모양은 구체',
        # '동그란 원')과 맞지 않는 형상 낱말은 그리지 않고 _alternatives(form.base, lower_priority)에 남긴다
        acts = self._action_similes(doc)
        veh = {k: a for a in acts for k in a["vehicles"]}
        live = [h for h in hits if not h["negated"] and h["blockedBy"] is None]
        sim_markers = [h["simile"]["markerIndex"] for h in live if h["simile"] is not None]
        dss = self._direct_shapes(doc, spec, phrase_of, color_toks, veh, context_sents, sim_markers)
        compat = self.dshape["compatibleBase"]
        vehicle_spans: list[tuple[dict, list[int]]] = []          # (움직임 비유, 매개어 구간) — 움직임 근거로 더함
        for h in live:
            p = h["p"]
            a = next((veh[x] for x in p["nouns"] if x in veh), None)
            if a is not None:
                tag = a["tag"]
                vehicle_spans.append((a, [h["s"], h["e"]]))
            else:
                d = next((d for d in dss if d["shape"] not in compat.get(h["entry"]["base"], [])), None)
                if d is None or self._in_shape_frame(doc, p):
                    continue                  # 형태 틀 안의 형상 낱말('모양은 그릇 같아요')끼리는 기존 규칙(먼저 나온 것)
                tag = f"directShape({d['lemma']})"
            h["demotedBy"] = tag
            changed = True
            spec["_alternatives"].append({"path": "form.base", "value": h["entry"]["base"], "reason": "lower_priority",
                                          "_provenance": [prov(h, f"baseShapes.{h['lemma']}>form.base:"
                                                                  f"{h['entry']['base']}+{tag}")]})
            drop_records(h)
        # 직접 형태 진술은 비유 원천에서 온 form.type(안개·껍질·조각 — 모양 모형을 막는 형태)보다 앞선다
        ft = spec["form"]["type"]
        ftp = spec["_provenance"].get("form.type") or []
        if dss and ft in self.dshape["demotesFormType"] and ftp and all(pv["source"] == "simile_marker" for pv in ftp):
            changed = True
            tag = f"directShape({dss[0]['lemma']})"
            spec["_alternatives"].append({"path": "form.type", "value": ft, "reason": "lower_priority",
                                          "_provenance": [dict(pv, rule=f"{pv['rule']}+{tag}") for pv in ftp]})
            spec["_provenance"].pop("form.type")
            spec["form"]["type"] = None
        # 형태에서 내린 움직임 비유 매개어는 그 비유의 움직임 값의 근거로 더한다
        for al in spec["_alternatives"]:
            if al["path"] == "form.type" and "+actionSimile(" in al["_provenance"][0]["rule"]:
                cs = al["_provenance"][0]["charSpan"]
                a = next((veh[k] for k in doc.toks_in(cs[0], cs[1]) if k in veh), None)
                if a is not None:
                    vehicle_spans.append((a, cs))
        for a, (vs, ve) in vehicle_spans:
            pspans = [(toks[k].start, toks[k].end) for k in a["preds"]]
            noun = text[vs:ve]
            if doc.toks_in(vs, ve) and toks[doc.toks_in(vs, ve)[0]].base_tag in NOUN_TAGS:
                ids = [k for k in doc.toks_in(vs, ve) if toks[k].base_tag in NOUN_TAGS]
                noun = text[toks[ids[0]].start:toks[ids[-1]].end]
                vs, ve = toks[ids[0]].start, toks[ids[-1]].end
            targets = [(spec["motion"]["type"], spec["_provenance"].get("motion.type") or [])] + \
                      [(al["value"], al["_provenance"]) for al in spec["_alternatives"] if al["path"] == "motion.type"]
            for mv, plist in targets:
                if plist and any(ps < pv["charSpan"][1] and pv["charSpan"][0] < pe for pv in plist for ps, pe in pspans):
                    entry = self._prov("simile_marker", text, vs, ve, f"actionSimile.{noun}>motion.type:{mv}")
                    if not any(pv["charSpan"] == entry["charSpan"] and pv["rule"] == entry["rule"] for pv in plist):
                        plist.append(entry)
                        changed = True
                    break
        if changed:
            spec["_alternatives"].sort(key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                       al["reason"]))
            spec["_provenance"] = _ordered_provenance(spec["_provenance"])

        base_hits = sorted((h for h in live if "demotedBy" not in h), key=lambda h: h["s"])
        if not base_hits:
            return None, None, changed
        changed = True

        win = base_hits[0]
        key = win["entry"]["base"]
        same = [h for h in base_hits if h["entry"]["base"] == key]
        spec["_provenance"]["form.base"] = [prov(h, f"baseShapes.{h['lemma']}>form.base:{key}") for h in same]
        for h in base_hits:
            # 이 명사의 다른 기록(사물·모양어·사전에 없는 명사, 직유 원형 대기 포함)은 이제 값의 근거이므로 지운다.
            # 같은 낱말이고 구간이 겹치는 것만(직유 기록의 구간은 '상자 같'처럼 표지까지 덮는다)
            unmapped[:] = [u for u in unmapped if not (u["lemma"] == h["lemma"]
                                                       and u["category"] in ("object", "shape", "unlisted_noun")
                                                       and u["_provenance"]["charSpan"][0] < h["e"]
                                                       and h["s"] < u["_provenance"]["charSpan"][1])]
            if h["entry"]["base"] != key:
                spec["_alternatives"].append({"path": "form.base", "value": h["entry"]["base"], "reason": "later_mention",
                                              "_provenance": [prov(h, f"baseShapes.{h['lemma']}>form.base:{h['entry']['base']}")]})
        # 변형값: 낱말 뜻(이긴 명사의 사전 항목) → 같은 문장의 참여자 말이 덮어씀.
        # G38(2.3.0): 낱말 뜻에서 온 값은 그 낱말을 말한 것의 일부라 그리지만 source = lexicon_implied로 말한 것과 가른다
        variant: dict[str, str] = {}
        vprov: dict[str, dict] = {}
        for k, v in (win["entry"].get("variant") or {}).items():
            variant[k] = v
            vprov[k] = dict(prov(win, f"baseShapes.{win['lemma']}>form.baseVariant:{k}={v}"), source=IMPLIED_SOURCE)
        sents = {doc.sent[h["b"]] for h in same}
        for k, vals in (self.bs_cues.get(key) or {}).items():
            best = None                                          # (charSpan 시작, 값, provenance)
            for v, cue in vals.items():
                for x, t in enumerate(toks):
                    if doc.sent[x] not in sents or t.form not in cue.get("lemmas", ()) \
                            or t.base_tag not in ("VV", "VA", "XR") or Lexicon._negated(toks, x):
                        continue
                    if best is None or t.start < best[0]:
                        best = (t.start, v, self._tok_prov(doc, x, f"baseVariantCue.{t.form}>form.baseVariant:{k}={v}"))
                for u in unmapped:
                    cs = u["_provenance"]["charSpan"]
                    if u["category"] == "shape" and u["reason"] not in ("excluded_shape", "no_asset") \
                            and (u["value"] or {}).get("shape") in cue.get("shapeValues", ()) \
                            and any(doc.sent[x] in sents for x in doc.toks_in(cs[0], cs[1])):
                        if best is None or cs[0] < best[0]:
                            best = (cs[0], v, dict(u["_provenance"],
                                                   rule=f"baseVariantCue.{u['lemma']}>form.baseVariant:{k}={v}"))
            if best is not None:
                variant[k] = best[1]
                vprov[k] = best[2]
        if variant:
            variant = {k: variant[k] for k in sorted(variant)}
            spec["_provenance"]["form.baseVariant"] = [vprov[k] for k in sorted(vprov)]
        spec["_provenance"] = _ordered_provenance(spec["_provenance"])
        spec["_alternatives"].sort(key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                   al["reason"]))
        return key, (variant or None), changed

    # ── G61 ②: 형태 변이 규칙층 ──────────────────────────────────────────────
    def _lookup(self, form: str) -> list[LexEntry]:
        return self.lexicon._by_form.get(form, []) + self.lexicon._by_alt.get(form, [])

    def _main_accept(self, e: LexEntry) -> bool:
        """v1 경로로 받을 사전 항목(색·차원어·스펙 2.3 범주 빼고 모두). 장면 대응이 없는 범주(모양어 shape 등)도 받아
        직접 일치와 같게 _unmapped에 남긴다('둥글둥글해요' → 둥글 → _unmapped shape round)."""
        return (e.category not in SKIP_LEXICON_CATEGORIES and e.category not in EXT_CATEGORIES
                and e.category not in ("body_layer", "self_reference"))

    def _value_accept(self, e: LexEntry) -> bool:
        """값을 내는 항목만(어절 단위 변이 — _unmapped를 쓸 자리가 없는 경로)."""
        return (e.category in self.layer1 and e.category not in SKIP_LEXICON_CATEGORIES
                and any(self._map(tg, e.value) for tg in self.layer1[e.category]))

    def _variant_cands(self, doc: Doc, hit_toks: set[int], consumed: set[int], similes, negated: list,
                       unmapped: list) -> list[Cand]:
        """1층 사전에 직접 걸리지 않았고 기존 의태어 파생(v1 mimeticDerivation)도 걸리지 않은 토큰에 변이 규칙을 건다.
        뿌리가 사전에 있을 때만 그 항목의 값(v1과 같은 대응·정도 부사)을 낸다. 부정되면 _negated, 장면 대응이 없는 범주면
        _unmapped에 직접 일치와 같은 꼴로 남긴다. 다룬 토큰은 consumed에 넣어 자모 퍼지·미대응 기록으로 가지 않게 한다
        (순서: 직접 → 파생 → 변이 → 퍼지)."""
        assert self.variants is not None
        toks = doc.toks
        n = len(toks)
        coord_neg = getattr(doc, "coord_neg", set())
        out: list[Cand] = []
        seen: set[tuple[int, str]] = set()
        for i, t in enumerate(toks):
            if i in hit_toks or i in consumed or t.base_tag not in self.variants.source_tags or t.lemma in FUNCTION_LEMMAS:
                continue
            nx = (toks[i + 1] if i + 1 < n and doc.eoj[i + 1] == doc.eoj[i]
                  and toks[i + 1].base_tag in ("VV", "XSV", "XSA") else None)
            if self._derive_mimetic(t.form, nx.form if nx is not None else None):
                continue                                    # 기존 파생 규칙이 맡는다(v1 _fuzzy)
            m = self.variants.resolve(t.form, t.base_tag, nx.form if nx is not None else None, self._lookup,
                                      self._main_accept)
            if m is None:
                continue
            if (doc.eoj[i], m.root) in seen:                # '꺼칠/XR 꺼칠/XR' — 같은 어절의 같은 뿌리는 한 번만
                consumed.add(i)
                continue
            seen.add((doc.eoj[i], m.root))
            sim = self._vehicle_of(t, similes)
            layer = 2 if sim else 1
            neg = Lexicon._negated(toks, i) or self._noun_negated(doc, i) or i in coord_neg

            def mk(rule: str, _i=i, _sim=sim) -> dict:
                p = self._eoj_prov(doc, _i, rule)
                return dict(p, rule=f"simile.{_sim['marker']}>{rule}", source="simile_marker") if _sim else p

            for e in m.entries:
                if neg:
                    negated.append({"lemma": e.lemma, "category": e.category, "_provenance": mk(f"{m.tag()}>{e.rule}")})
                    continue
                targets = [tg for tg in self.layer1.get(e.category, []) if tg["path"] != "body.layer"]
                produced = 0
                for tg in targets:
                    mapped = self._map(tg, e.value)
                    if mapped is None:
                        continue
                    value, key = mapped
                    path = tg["path"]
                    if isinstance(value, float) and path in self.v["scalarCenters"]:
                        value = self._apply_degree(path, value, self._degree(doc, i)[0], key)
                    sub = 1 if path == "motion.type" and self._is_state(doc, i, t.form) else 0
                    out.append(Cand(path, value, i, t.start, [mk(f"{m.tag()}>{e.rule}>{path}:{key}")], layer=layer, sub=sub))
                    produced += 1
                if not produced:
                    unmapped.append({"lemma": e.lemma, "category": e.category, "value": dict(e.value),
                                     "reason": "no_value_mapping" if self.layer1.get(e.category) else "no_scene_param",
                                     "_provenance": mk(f"{m.tag()}>{e.rule}")})
            consumed.add(i)
        return out

    def _fuzzy_eojeol(self, doc: Doc, cands: list[Cand], covered: set[int], fuzzy_toks: set[int]) -> list[Cand]:
        """변이 규칙을 켰으면 Kiwi가 조각내거나 통째로 명사로 묶은 어절('빤짝여요' → 빨/VV ᆫ 짝 이 …, '몰랑몰랑해요/NNG')을
        어절 표면형으로 먼저 변이 규칙에 넣는다(자모 퍼지보다 앞). 부정된 어절은 값을 만들지 않고 넘긴다."""
        out: list[Cand] = []
        if self.variants is not None:
            cand_toks = {c.tok for c in cands}
            for e in range(len(doc.eojeols)):
                if doc.is_punct_eoj(e):
                    continue
                ids = list(doc.etoks(e))
                if any(k in covered or k in cand_toks or k in fuzzy_toks for k in ids):
                    continue
                tags = [doc.toks[k].base_tag for k in ids]
                if not ("UN" in tags or len(ids) >= 3 or (len(ids) == 1 and tags[0] == "NNG")):
                    continue
                if Lexicon._negated(doc.toks, ids[0]) or Lexicon._negated(doc.toks, ids[-1]):
                    continue
                w = doc.etext(e).strip(" .,!?~")
                m = self.variants.resolve(w, "EOJEOL", None, self._lookup, self._value_accept)
                if m is None:
                    continue
                for ent in m.entries:
                    for tg in self.layer1[ent.category]:
                        mapped = self._map(tg, ent.value)
                        if mapped is None or tg["path"] == "body.layer":
                            continue
                        value, key = mapped
                        path = tg["path"]
                        if isinstance(value, float) and path in self.v["scalarCenters"]:
                            value = self._apply_degree(path, value, self._degree(doc, ids[0])[0], key)
                        out.append(Cand(path, value, ids[0], doc.toks[ids[0]].start,
                                        [self._eoj_prov(doc, ids[0], f"{m.tag()}>{ent.rule}>{path}:{key}")]))
                fuzzy_toks.update(ids)
            covered = covered | fuzzy_toks
        return out + super()._fuzzy_eojeol(doc, cands + out, covered, fuzzy_toks)

    # ── G61 ①: 윤곽·발광(스펙 2.3) ──────────────────────────────────────────
    def _ext_step(self, path: str, value: str) -> str | None:
        """약한 정도 부사: 한 단계 중립 쪽으로. 중립(·none)까지는 가지 않는다. 옮기지 않으면 None."""
        levels, neutral = self.ext_levels[path]
        if value not in levels or value == neutral:
            return None
        k, nk = levels.index(value), levels.index(neutral)
        j = k + (1 if k < nk else -1)
        return None if j == nk else levels[j]

    def _ext_cands(self, doc: Doc, e: LexEntry, i: int, similes, coord_neg: set[int], hit: Hit | None,
                   via: VariantMatch | None, negated: list, phrase: tuple[int, int, int, str] | None = None) -> list[Cand]:
        """phrase = (첫 토큰, 용언 토큰, 구 끝 글자, 규칙 이름): 명사 + 용언 구('각이 진' · '빛이 나요')."""
        toks = doc.toks
        sim = self._vehicle_of(toks[i], similes)
        layer = 2 if sim else 1
        predicate = e.pos in ("VA", "VV", "XR") or toks[i].base_tag in ("VA", "VV")
        base_rule = e.rule if via is None else f"{via.tag()}>{e.rule}"
        if phrase is not None:
            base_rule = f"{phrase[3]}>{e.rule}"

        def mk(rule: str) -> dict:
            if phrase is not None:
                p = self._prov("phrase_rule", doc.text, toks[phrase[0]].start, phrase[2], rule)
            else:
                p = self._eoj_prov(doc, i, rule) if (predicate or via is not None) else self._tok_prov(doc, i, rule)
            return dict(p, rule=f"simile.{sim['marker']}>{rule}", source="simile_marker") if sim else p

        if phrase is not None:
            v = phrase[1]
            pv = toks[v - 1] if v > 0 else None
            neg = Lexicon._negated(toks, v) or (pv is not None and pv.form in ("안", "못") and pv.base_tag == "MAG") \
                or v in coord_neg
        else:
            neg = (hit.negated if hit is not None else Lexicon._negated(toks, i)) or self._noun_negated(doc, i) \
                or i in coord_neg
        out: list[Cand] = []
        for tg in self.ext_layer1.get(e.category, []):
            mapped = self._map(tg, e.value)
            if mapped is None:
                continue
            value, key = mapped
            path = tg["path"]
            if neg:
                said = self.ext_negation.get(path)
                if said is None:            # 윤곽어 부정: 반대 값을 만들지 않는다(원칙 2)
                    negated.append({"lemma": e.lemma, "category": e.category, "_provenance": mk(base_rule)})
                else:                       # 발광어 부정: '빛이 없다'를 말함 → none
                    out.append(Cand(path, said, i, toks[i].start, [mk(f"{base_rule}>{path}:{key}(negated)")], layer=layer))
                continue
            tail = ""
            k, f = self._degree(doc, phrase[1] if phrase is not None else i)   # 구는 용언 앞의 정도 부사('빛이 좀 나요')
            if f is not None and k == self.k["weak"]:
                moved = self._ext_step(path, value)
                if moved is not None:
                    value, tail = moved, f"+degree({doc.etext(f)})"
            out.append(Cand(path, value, i, toks[i].start, [mk(f"{base_rule}>{path}:{key}{tail}")], layer=layer))
        return out

    def _extension(self, doc: Doc, spec: dict, hits: list[Hit]) -> None:
        """1층 사전 v2의 윤곽·발광 낱말 → form.roundness·form.aspect·material.emission(스펙 2.3). v1과 같은 범위 규칙
        (회상 문장·배경 사물·자리 표지·모름·자기 정정·때)을 쓰고, 부분(안쪽·가장자리 …)만 말한 것은 _parts에 남긴다.
        변이 규칙을 켰으면 사전에 직접 걸리지 않은 토큰도 윤곽·발광 뿌리로 찾는다."""
        assert self.ext is not None
        text, toks = doc.text, doc.toks
        n = len(toks)
        coord_neg = self._coord_negated(doc)
        similes = self._similes(text, toks)
        context_sents = self._context_sentences(doc)
        negated: list[dict] = []
        cands: list[Cand] = []
        hit_toks = {h.token_index for h in hits}
        ext_toks = {h.token_index for h in hits if h.entry.category in EXT_CATEGORIES}
        for h in hits:
            if h.entry.category in EXT_CATEGORIES:
                cands += self._ext_cands(doc, h.entry, h.token_index, similes, coord_neg, h, None, negated)
        # 명사 + 용언 구('각이 진' · '모가 난' · '빛이 나요', Kiwi가 '각진'을 각/NNG + 지/VV로 나눈 경우 포함)
        ph = self.ext.get("phrases") or {}
        items = {(x["noun"], x["verb"]): x["as"] for x in ph.get("items", [])}
        particles = set(ph.get("particles", []))
        for i, t in enumerate(toks):
            if t.base_tag not in NOUN_TAGS or i in ext_toks or not any(k0 == t.form for k0, _ in items):
                continue
            k = i + 1
            while k < n and toks[k].base_tag in ("JKS", "JX") and toks[k].form in particles and doc.eoj[k] == doc.eoj[i]:
                k += 1
            adv = 0
            while k < n and toks[k].base_tag == "MAG" and adv < int(ph.get("maxAdverbs", 0)):
                k, adv = k + 1, adv + 1
            if k >= n or toks[k].base_tag != "VV" or doc.clause[k] != doc.clause[i] or (t.form, toks[k].form) not in items:
                continue
            ents = [e for e in self._lookup(items[(t.form, toks[k].form)]) if e.category in EXT_CATEGORIES]
            end = doc.espan(doc.eoj[k])[1]
            for e in ents:
                cands += self._ext_cands(doc, e, i, similes, coord_neg, None, None, negated,
                                         phrase=(i, k, end, f"phrase.{t.form}+{toks[k].form}"))
            if ents:
                hit_toks |= {i, k}
        if self.variants is not None:
            seen: set[tuple[int, str]] = set()
            for i, t in enumerate(toks):
                if i in hit_toks or t.base_tag not in self.variants.source_tags or t.lemma in FUNCTION_LEMMAS:
                    continue
                nx = (toks[i + 1] if i + 1 < n and doc.eoj[i + 1] == doc.eoj[i]
                      and toks[i + 1].base_tag in ("VV", "XSV", "XSA") else None)
                m = self.variants.resolve(t.form, t.base_tag, nx.form if nx is not None else None, self._lookup,
                                          lambda e: e.category in EXT_CATEGORIES)
                if m is None or (doc.eoj[i], m.root) in seen:
                    continue
                seen.add((doc.eoj[i], m.root))
                for e in m.entries:
                    cands += self._ext_cands(doc, e, i, similes, coord_neg, None, m, negated)
            # 어절 단위(Kiwi가 조각낸 어절: '빤짝여요' → 빨/VV ᆫ 짝 이 …) — 매퍼 v1 경로의 _fuzzy_eojeol 변이와 같은 조건
            ext_cand_toks = {c.tok for c in cands} | hit_toks
            for e_ in range(len(doc.eojeols)):
                if doc.is_punct_eoj(e_):
                    continue
                ids = list(doc.etoks(e_))
                tags = [toks[k].base_tag for k in ids]
                if any(k in ext_cand_toks for k in ids) or not (
                        "UN" in tags or len(ids) >= 3 or (len(ids) == 1 and tags[0] == "NNG")):
                    continue
                m = self.variants.resolve(doc.etext(e_).strip(" .,!?~"), "EOJEOL", None, self._lookup,
                                          lambda e: e.category in EXT_CATEGORIES)
                if m is None:
                    continue
                for e in m.entries:
                    cands += self._ext_cands(doc, e, ids[0], similes, coord_neg, None, m, negated)
        # 범위 규칙: 회상 문장·배경 주어·때(v1 _scope). 관형어가 꾸미는 명사(배경·자리 표지·부분)는 v1이 form.posture에만
        # 보므로 윤곽·발광에도 같은 규칙을 여기서 건다
        self._scope(doc, cands, context_sents, similes)
        sim_src = {s["srcIndex"] for s in similes}
        for c in cands:
            if c.status != "ok":
                continue
            e = doc.eoj[c.tok]
            attr_e = e if self._is_attributive(doc, e) else self._coordinated_attributive(doc, e)
            hn = self._head_noun(doc, attr_e) if attr_e is not None else None
            if hn:
                noun, k = hn
                if c.path.startswith("form.") and k not in sim_src:
                    if self._is_background(noun):
                        c.status, c.reason = "context", "background_object"
                        continue
                    if self._is_landmark(doc, k):
                        c.status, c.reason = "context", "landmark_object"
                        continue
                if noun in self.part_class and c.part is None:
                    c.part, c.part_class = noun, self.part_class[noun]
            if c.part is None:
                tp = self._topic(doc, c.tok)
                if tp and tp[0] in self.part_class:
                    c.part, c.part_class = tp[0], self.part_class[tp[0]]
        for u in spec.get("_uncertain") or []:                 # '잘 모르겠어요' 절(v1이 이미 찾음)
            s, e = u["charSpan"]
            for c in cands:
                if c.status == "ok" and s <= c.start < e:
                    c.status, c.reason = "uncertain", "participant_uncertain"
        self._corrections(doc, cands)
        # 병합(v1 _merge와 같은 순위: 차원 주제 > 때 > 층 > 근거 종류 > 먼저 말한 것)
        values: dict[str, str] = {}
        prov: dict[str, list[dict]] = {}
        alts: list[dict] = []
        parts: list[dict] = []
        context: list[dict] = []
        by_path: dict[str, list[Cand]] = defaultdict(list)
        for c in cands:
            p0 = c.provs[0]
            if c.status == "context":
                context.append({"text": p0["trigger"], "charSpan": p0["charSpan"], "reason": c.reason, "path": c.path,
                                "value": c.value, "rule": p0["rule"]})
            elif c.status in ("corrected", "uncertain"):
                alts.append({"path": c.path, "value": c.value, "reason": c.reason, "_provenance": list(c.provs)})
            elif c.status == "ok":
                if c.part_class in ("inner", "detail"):      # 부분만 말함 → 전체 값으로 올리지 않는다
                    parts.append({"text": p0["trigger"], "charSpan": p0["charSpan"], "part": c.part,
                                  "partClass": c.part_class, "path": c.path, "value": c.value, "rule": p0["rule"]})
                else:
                    by_path[c.path].append(c)
        for path in EXT_SLOT_PATHS:
            cs = sorted(by_path.get(path, []), key=lambda c: (-int(c.dim_topic), -c.tense, c.layer, c.klass, c.sub, c.start))
            if not cs:
                continue
            win = cs[0]
            values[path], prov[path] = win.value, list(win.provs)
            for c in cs[1:]:
                if c.layer == win.layer and c.value == win.value:
                    prov[path] += [p for p in c.provs if p not in prov[path]]
                    continue
                reason = "lower_layer" if c.layer > win.layer else ("superseded" if c.tense < win.tense else "later_mention")
                alts.append({"path": path, "value": c.value, "reason": reason, "_provenance": list(c.provs)})
        # spec에 쓰기. 키 순서: form = … base · baseVariant · roundness · aspect, material = … erosion · emission
        spec["form"] = {**spec["form"], "roundness": values.get("form.roundness"), "aspect": values.get("form.aspect")}
        spec["material"] = {**spec["material"], "emission": values.get("material.emission")}
        spec["_provenance"] = _ordered_provenance({**spec["_provenance"], **prov})
        spec["_alternatives"] = sorted(spec["_alternatives"] + alts,
                                       key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                       al["reason"]))
        spec["_negated"] = sorted(spec["_negated"] + negated,
                                  key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
        spec["_context"] = sorted(spec["_context"] + context, key=lambda x: (x["charSpan"][0], x["charSpan"][1],
                                                                             str(x.get("path")), str(x.get("reason"))))
        spec["_parts"] = sorted(spec["_parts"] + parts, key=lambda x: (x["charSpan"][0], x["charSpan"][1], str(x.get("path"))))
        # 절 색인: 윤곽·발광 근거가 든 절에 슬롯을 더한다(읽기용 색인 — 보존의 증거로 세지 않음, 6.5절)
        used = [(path, p["charSpan"]) for path, ps in prov.items() for p in ps]
        for cl in spec.get("_clauses") or []:
            s, e = cl["charSpan"]
            add = {path for path, (x, y) in used if x < e and s < y}
            if add:
                cl["usedFor"] = sorted(set(cl["usedFor"]) | add, key=lambda p: (_PATH_ORDER.get(p, 99), p))
                if cl["status"] == "unused":
                    cl["status"] = "partly_used"
        # 읽지 못한 말: 이제 값·보존 기록이 덮은 토큰을 빼고, 어절 항목은 다시 계산한다
        covered: set[int] = set()
        _span_chars({"p": prov, "a": alts, "n": negated, "c": context, "parts": parts}, covered)
        # 구 규칙('모가 나')의 명사가 D1에서 사전에 없는 명사로 기록됐으면 지운다(이제 윤곽 근거 — D6 기본 형상과 같은 처리)
        spec["_unmapped"] = [u for u in spec["_unmapped"]
                             if not (u["category"] == "unlisted_noun"
                                     and all(ch in covered for ch in range(*u["_provenance"]["charSpan"])))]
        tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG
                     and not all(ch in covered for ch in range(u["charSpan"][0], u["charSpan"][1]))]
        spec["_unmatched"] = tok_level        # 어절 항목을 먼저 빼야 다시 계산할 때 옛 어절 항목이 '보존됨'으로 세지 않는다
        spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                    key=lambda u: (u["charSpan"][0], u["charSpan"][1]))

    # ── D1: 배경 사물이 형상인 경우 ───────────────────────────────────────────
    def _figure_background_tokens(self, doc: Doc, context_sents: set[int]) -> set[int]:
        """배경 사물 낱말(backgroundNouns)이 '있다'·'생기다'·'놓이다'의 주어이고 같은 절에 다른 배경 처소어가 없으면
        그 낱말은 형상이다. 같은 텍스트에서 같은 낱말의 모든 토큰 번호를 돌려준다."""
        toks = doc.toks
        n = len(toks)
        forms: set[str] = set()
        for k, t in enumerate(toks):
            if t.base_tag not in NOUN_TAGS or not self._is_background(t.form) or doc.sent[k] in context_sents:
                continue
            m = k + 1
            while m < n and toks[m].base_tag == "XSN":
                m += 1
            if m >= n or doc.eoj[m] != doc.eoj[k]:
                continue
            nt = toks[m]
            if not ((nt.base_tag == "JKS" and nt.form in ("이", "가")) or
                    (nt.base_tag == "JX" and nt.form in ("은", "는", "ᆫ", "도"))):
                continue
            ids = doc.clause_toks(doc.clause[k])
            if not any(x > m and toks[x].form in self.exist_preds and toks[x].base_tag in ("VV", "VA", "VX") for x in ids):
                continue
            if any(x != k and toks[x].base_tag in NOUN_TAGS and self._is_background(toks[x].form) and x + 1 < n
                   and toks[x + 1].base_tag == "JKB" for x in ids):
                continue      # '창가에 화분이 있어요' — 주변 장면 묘사
            forms.add(t.form)
        return {k for k, t in enumerate(toks) if t.base_tag in NOUN_TAGS and t.form in forms}

    # ── D1: 사전에 없는 명사 ───────────────────────────────────────────────────
    def _situation_regions(self, doc: Doc) -> list[tuple[int, int]]:
        """'소파에 누웠을 때'처럼 관형형 + 때·적·순간·동안이 맺는 상황절의 토큰 범위 [시작, 표지). 시작은 같은 절에서
        표지 앞의 가장 가까운 연결·종결 어미·문장부호·'-는데'의 '데' 다음이다(Kiwi가 '-는데'를 관형형 + 데로 내면
        절이 나뉘지 않으므로). 조건 어미 -면('빛을 받으면 반짝여요')은 형상의 행동을 말하는 일이 많아 명사 표시에는 쓰지 않는다."""
        toks = doc.toks
        n = len(toks)
        out = []
        for k, t in enumerate(toks):
            if not (t.base_tag == "ETM" and k + 1 < n and toks[k + 1].form in self.sit_nouns
                    and toks[k + 1].base_tag in NOUN_TAGS | {"NNB"} and doc.clause[k + 1] == doc.clause[k]):
                continue
            s = k
            while s - 1 >= 0 and doc.clause[s - 1] == doc.clause[k] and not (
                    toks[s - 1].base_tag in ("EC", "EF", "SF", "SP", "SE")
                    or (toks[s - 1].form == "데" and toks[s - 1].base_tag == "NNB")):
                s -= 1
            out.append((s, k))
        return out

    def _situation_sentences(self, doc: Doc, valued: set[int], skip_etm: set[int] | frozenset = frozenset()) -> set[int]:
        """떠올린 상황을 말한 문장(scene_params.v2.json unlistedNouns.scopeNote ②–④). v1 회상 문장 규칙은 '-던'·'장면'만
        본다. 여기서는 명사 기록의 scope 표시에만 쓰고 슬롯 값은 바꾸지 않는다. valued = 슬롯 값 근거가 덮은 글자.
        skip_etm(2.4.0) = ②에서 보지 않을 관형형 토큰(기본 형상 판정에서 '그릇처럼 생긴 거예요'의 '생긴' — 비교 대상인 형식 명사)."""
        toks = doc.toks
        sit = set(self.v["contextSentence"]["situationNouns"])
        out: set[int] = set()
        for k, t in enumerate(toks):
            s = doc.sent[k]
            # ② 관형형 + 상황 명사로 끝남('연락이 끊긴 일이요')
            if t.base_tag == "ETM" and k not in skip_etm and k + 1 < len(toks) and toks[k + 1].form in sit and doc.sent[k + 1] == s and all(
                    toks[j].base_tag in ("JX", "VCP", "EF", "EC", "JKS") or toks[j].base_tag in PUNCT_TAGS
                    for j in range(k + 2, len(toks)) if doc.sent[j] == s):
                out.add(s)
            # ③ 생각나다 · 기억나다 · 떠올리다
            if t.base_tag == "VV" and t.form in self.recall_verbs:
                out.add(s)
        # ④ 상황·시간 명사가 있고 슬롯 값이 하나도 나오지 않은 문장('주말 아침 산책이요' · '어제 회의요')
        for s in sorted(set(doc.sent)):
            ids = [i for i in range(len(toks)) if doc.sent[i] == s]
            if any(toks[i].base_tag in NOUN_TAGS | {"MAG"} and toks[i].form in self.scene_time_nouns for i in ids) and \
                    not any(c in valued for i in ids for c in range(toks[i].start, toks[i].end)):
                out.add(s)
        return out

    def _noun_role(self, doc: Doc, j: int) -> str:
        """명사(연속의 마지막 토큰 j) 뒤 조사로 본 문장 성분."""
        toks = doc.toks
        n = len(toks)
        k = j + 1
        while k < n and toks[k].base_tag == "XSN":
            k += 1
        if k >= n:
            return "named"
        nt = toks[k]
        if doc.eoj[k] != doc.eoj[j]:
            if doc.line[k] != doc.line[j]:
                return "named"           # (2.6.0) 줄 끝 명사('모양은 구체⏎색은') — 줄은 답 하나라 다음 줄 명사를 꾸미지 않음
            if nt.base_tag in PUNCT_TAGS:
                return "named"           # '얇은 막.' — 이름만 말함
            if nt.base_tag in NOUN_TAGS:
                return "location" if nt.form in self.v["relationalNouns"] else "modifier"
            return "other"
        if nt.base_tag == "VCP" or (nt.base_tag == "JX" and nt.form in ("요", "이요")):
            return "named"
        if nt.base_tag == "JKS" or (nt.base_tag == "JX" and nt.form in TOPIC_PARTICLES):
            return "subject"
        if nt.base_tag == "JKB":
            return "location" if nt.form in _LOCATION_JKB else "other"
        if nt.base_tag == "JKO":
            return "object"
        if nt.base_tag == "JKG":
            return "modifier"
        return "other"

    def _unlisted_nouns(self, doc: Doc, hits: list[Hit], spec: dict) -> list[dict]:
        toks, text = doc.toks, doc.text
        n = len(toks)
        covered: set[int] = set()
        for key in _COVER_KEYS:
            _span_chars(spec.get(key), covered)
        hit_toks = {h.token_index for h in hits}
        valued: set[int] = set()
        _span_chars(spec.get("_provenance"), valued)
        context_sents = self._context_sentences(doc) | self._situation_sentences(doc, valued)
        regions = self._situation_regions(doc)
        un = self.p2["unlistedNouns"]

        def free(i: int) -> bool:
            t = toks[i]
            if t.base_tag not in self.noun_tags or i in hit_toks or t.form in self.lex_forms or t.form in self.stop_nouns:
                return False
            return not all(c in covered for c in range(t.start, t.end))

        out: list[dict] = []
        i = 0
        while i < n:
            if toks[i].base_tag not in NOUN_TAGS:
                i += 1
                continue
            j = i      # 띄어쓰기 없이 붙은 명사 연속('빵가루' · '털실')
            while j + 1 < n and toks[j + 1].base_tag in NOUN_TAGS and toks[j + 1].start == toks[j].end \
                    and doc.eoj[j + 1] == doc.eoj[i]:
                j += 1
            run = list(range(i, j + 1))
            i = j + 1
            nx = toks[j + 1] if j + 1 < n else None
            if nx is not None and nx.base_tag in ("XSV", "XSA") and nx.start == toks[j].end:
                continue      # 서술성 명사 + -하다('퇴근하고' · '통화했던')는 사물 이름이 아니다
            frees = [x for x in run if free(x)]
            if not frees:
                continue
            groups = [run] if len(frees) == len(run) else [[x] for x in frees]
            for g in groups:
                a, b = g[0], g[-1]
                s, e = toks[a].start, toks[b].end
                lemma = text[s:e]
                in_region = any(s0 <= a and b < k0 for s0, k0 in regions)
                scope = "context" if (doc.sent[b] in context_sents or in_region) else "main"
                out.append({"lemma": lemma, "category": un["category"],
                            "value": {"noun": lemma, "role": self._noun_role(doc, b), "scope": scope},
                            "reason": un["reason"],
                            "_provenance": self._prov(un["provenanceSource"], text, s, e, f"unlistedNoun.{lemma}")})
        return out

    # ── 범위 규칙(D1 배경 사물 형상 · D2(c) 자세) ────────────────────────────
    def _scope(self, doc: Doc, cands: list[Cand], context_sents: set[int], similes) -> None:
        # 형상으로 판정한 배경 사물 낱말은 v1 _scope가 직유 원천 명사를 다루는 것과 같은 경로(sim_src)로 배경·자리 표지
        # 판정에서 뺀다. similes 목록 자체는 바꾸지 않고 _scope에 넘기는 사본에만 srcIndex를 더한다
        promoted = self._figure_background_tokens(doc, context_sents)
        cands.extend(self._said_phrase_cands(doc))          # 2.6.0: '보통 크기'·'무광' (범위 규칙을 같이 받게 먼저 넣음)
        super()._scope(doc, cands, context_sents, list(similes) + [{"srcIndex": k} for k in sorted(promoted)])
        for c in cands:
            if c.path == "form.posture" and c.status == "ok":
                why = self._self_posture(doc, c.tok)
                if why is not None:
                    c.status, c.reason = "context", why
        # 2.6.0: '빨리 끝내고 싶다'의 '빨리'는 바람(-고 싶-)을 꾸미는 말이라 물체의 움직임 빠르기가 아니다(대안 lower_priority)
        for c in cands:
            if c.status == "ok" and c.path == "motion.speed":
                w = self._wish_host(doc, c.tok)
                if w is not None:
                    c.status, c.reason = "corrected", "lower_priority"
                    c.provs = [dict(c.provs[0], rule=f"{c.provs[0]['rule']}+wish({w})"), *c.provs[1:]]
        # 2.6.0: 움직임 비유의 매개어는 형태(form.type)를 채우지 않고(대안 lower_priority), 절 비유 안의 다른 값은 층 2(비유)로
        acts = self._action_similes(doc)
        if not acts:
            return
        veh = {k: a for a in acts for k in a["vehicles"]}
        regions = [a for a in acts if a["kind"] == "clause"]
        for c in cands:
            if c.status != "ok":
                continue
            ks = doc.toks_in(*c.provs[0]["charSpan"]) or [c.tok]
            if c.path == "form.type":
                if not self.act["demoteFormType"]:
                    continue
                a = next((veh[k] for k in ks if k in veh), None)
                if a is not None:
                    c.status, c.reason = "corrected", "lower_priority"
                    c.provs = [dict(c.provs[0], rule=f"{c.provs[0]['rule']}+{a['tag']}"), *c.provs[1:]]
                continue
            if c.path.startswith(("motion.", "form.")):
                continue                      # 절 비유의 동사('펄럭이듯이')는 물체가 움직이는 모양새라 그대로 둔다
            a = next((a for a in regions if c.tok in a["region"]), None)
            if a is not None and c.layer < 2:
                c.layer = 2
                c.provs = [dict(c.provs[0], rule=f"{c.provs[0]['rule']}+{a['tag']}"), *c.provs[1:]]

    # ── 2.6.0: 움직임 비유 · 직접 형태 진술 · 모양 명사 · 보통 크기 · 광택 표면형 ─────────
    def _homonym_blocked(self, doc: Doc, h: Hit) -> bool:
        g = self.homonym_guards.get(h.entry.lemma)
        if g is None:
            return False
        k = h.token_index + 1
        toks = doc.toks
        return (k < len(toks) and doc.eoj[k] == doc.eoj[h.token_index] and toks[k].base_tag == "XSN"
                and toks[k].form in g["rejectNextXSN"])

    def _action_similes(self, doc: Doc) -> list[dict]:
        """움직임 비유(scene_params.v2 shapePriority.actionSimile). 항목: kind(clause | adverbial), vehicles(매개어 명사 토큰),
        region(절 비유의 토큰), preds(비유 쪽 움직임 용언 토큰), tag(provenance rule 꼬리표)."""
        toks = doc.toks
        n = len(toks)
        cats = set(self.act["predicateCategories"])
        move = {h.token_index for h in self.lexicon.hits(doc.text) if h.entry.category in cats}
        out: list[dict] = []
        # (A) 절 비유: '-듯이'(EC) · 관형형 + 것 + 처럼
        for i, t in enumerate(toks):
            end = pred = None
            if t.base_tag == "EC" and t.form in self.act["clauseEndings"] and i > 0 \
                    and toks[i - 1].base_tag in ("VV", "VA", "XSV", "XSA", "VX"):
                end, pred = i, i - 1
            elif (t.base_tag == "NNB" and t.form in self.act["formalNouns"] and i > 1 and toks[i - 1].base_tag == "ETM"
                  and i + 1 < n and doc.eoj[i + 1] == doc.eoj[i] and toks[i + 1].form in self.act["formalMarkers"]
                  and toks[i + 1].base_tag in ("JKB", "MAG")):
                end, pred = i + 1, i - 2
            if end is None:
                continue
            region = [k for k in doc.clause_toks(doc.clause[i]) if k < i and doc.sent[k] == doc.sent[i]]
            after = [k for k in range(end + 1, n) if doc.sent[k] == doc.sent[i]]
            if self._subject_in(doc, after) is None:
                continue                      # 뒤에 따로 주어가 없으면 비유 절의 주어가 물체일 수 있다('종이가 춤추듯이 날아다녀요')
            vehicles = {k for k in region if toks[k].base_tag in NOUN_TAGS}
            if not vehicles:
                continue
            s0 = doc.espan(doc.eoj[pred])[0]
            out.append({"kind": "clause", "region": set(region), "vehicles": vehicles,
                        "preds": {k for k in region if k in move}, "tag": f"actionSimile({doc.text[s0:toks[end].end]})"})
        # (B) 부사 비유: 'N처럼 V(움직임)'
        for sm in self._simile_markers(doc):
            mi = sm["markerIndex"]
            if sm["marker"] not in self.act["adverbialMarkers"] or toks[mi].base_tag not in ("JKB", "MAG"):
                continue
            last = doc.eojeols[doc.eoj[mi]][1]
            if toks[last].base_tag == "ETM":
                continue
            pred = next((k for k in range(last + 1, n) if doc.clause[k] == doc.clause[mi]
                         and toks[k].base_tag in ("VV", "VA")), None)
            if pred is None or pred not in move or self._resultative(doc, pred):
                continue                      # '안개처럼 퍼진 빛'·'구름처럼 퍼져 있어요' — 움직임이 아니라 퍼진 상태(형상 비유)
            src = sm["srcIndex"]
            vehicles = {k for k in doc.etoks(doc.eoj[src]) if k <= src and toks[k].base_tag in NOUN_TAGS}
            s0, e0 = doc.espan(doc.eoj[mi])[0], doc.espan(doc.eoj[pred])[1]
            out.append({"kind": "adverbial", "region": set(), "vehicles": vehicles, "preds": {pred},
                        "tag": f"actionSimile({doc.text[s0:e0]})"})
        return out

    def _wish_host(self, doc: Doc, i: int) -> str | None:
        """부사 i가 꾸미는 같은 절의 첫 용언이 '-고 싶-'(바람)이면 그 원문('끝내고 싶다'), 아니면 None."""
        toks = doc.toks
        n = len(toks)
        if toks[i].base_tag != "MAG":
            return None
        host = next((k for k in range(i + 1, n) if doc.clause[k] == doc.clause[i] and toks[k].base_tag in ("VV", "VA")), None)
        if host is None or host + 2 >= n:
            return None
        ec, aux = toks[host + 1], toks[host + 2]
        if ec.base_tag == "EC" and ec.form == "고" and aux.base_tag == "VX" and aux.form in self.speed_wish_aux:
            s = doc.espan(doc.eoj[host])[0]
            return doc.text[s:doc.espan(doc.eoj[host + 2])[1]]
        return None

    # ── G72: 너비·높이·깊이 비율 ──────────────────────────────────────────────
    def _proportion_matches(self, doc: Doc) -> list[dict]:
        """비율 표(scene_params.v2 proportions)에 맞는 자리. 같은 글 → 같은 목록(문서만 본다).
        항목: profile · a(시작 토큰) · head(어근·용언 토큰) · s·e(글자 구간) · tag(규칙 꼬리표) · resultative(결과 상태 용언) ·
        shapeModel · lemma · status(ok | negated | out_of_scope)."""
        toks, pr = doc.toks, self.prop
        n = len(toks)
        dirs = pr["directionAdverbs"]
        long_stem = (pr["longStem"]["form"], pr["longStem"]["tag"])
        hn = pr["heightNoun"]
        out: list[dict] = []

        def prev_eoj(i: int) -> int | None:
            pe = doc.eoj[i] - 1
            if pe < 0 or doc.eoj_clause(pe) != doc.clause[i] or doc.is_punct_eoj(pe):
                return None
            return pe

        for i, t in enumerate(toks):
            m = None
            key = (t.form, t.base_tag)
            if key in self.prop_stems or key == long_stem:
                st = self.prop_stems.get(key)
                pe = prev_eoj(i)
                d = dirs.get(doc.etext(pe)) if pe is not None and (st is None or st.get("directional")) else None
                if d is not None:
                    m = {"profile": d, "a": doc.eojeols[pe][0], "tag": f"direction:{doc.etext(pe)}+{t.form}"}
                elif st is not None:
                    m = {"profile": st["profile"], "a": doc.eojeols[doc.eoj[i]][0], "tag": f"stem:{t.form}",
                         "shapeModel": st.get("shapeModel")}
            elif t.form in self.prop_preds and t.base_tag in ("VV", "VA") and self._resultative(doc, i):
                rp = self.prop_preds[t.form]
                pe = prev_eoj(i)
                mod = doc.etext(pe) if pe is not None and doc.etext(pe) in rp["modifiers"] else None
                if mod is not None:
                    m = {"profile": rp["profile"], "a": doc.eojeols[pe][0], "tag": f"resultative:{mod}+{t.form}",
                         "resultative": True}
                elif rp["bare"]:
                    m = {"profile": rp["profile"], "a": doc.eojeols[doc.eoj[i]][0], "tag": f"resultative:{t.form}",
                         "resultative": True}
            elif t.form == hn["predicate"] and t.base_tag == "VA" and doc.eoj[i] > 0:
                k = next((x for x in doc.etoks(doc.eoj[i] - 1)
                          if toks[x].form == hn["noun"] and toks[x].base_tag in NOUN_TAGS), None)
                if k is not None and k + 1 < n and toks[k + 1].form in hn["particles"] and toks[k + 1].base_tag == "JKS" \
                        and doc.clause[k] == doc.clause[i]:
                    m = {"profile": hn["profile"], "a": k, "tag": f"heightNoun:{hn['noun']}+{t.form}"}
            if m is None:
                continue
            m.setdefault("resultative", False)
            m.setdefault("shapeModel", None)
            m["head"], m["lemma"] = i, t.form
            m["s"], m["e"] = toks[m["a"]].start, doc.espan(doc.eoj[i])[1]
            m["status"] = "negated" if Lexicon._negated(toks, i) else "ok"
            out.append(m)
        # 범위: 회상 문장, 움직임 비유의 절·매개어, 배경·몸·자기 지칭을 꾸미거나 서술하는 말은 형상의 비율이 아니다
        ctx = self._context_sentences(doc)
        sim_toks: set[int] = set()
        for sm in self._action_similes(doc):
            sim_toks |= set(sm["region"]) | set(sm["vehicles"])
        for m in out:
            if m["status"] != "ok":
                continue
            ids = range(m["a"], m["head"] + 1)
            if doc.sent[m["head"]] in ctx or any(x in sim_toks for x in ids):
                m["status"] = "out_of_scope"
                continue
            last = doc.eojeols[doc.eoj[m["head"]]][1]
            if toks[last].base_tag == "ETM":
                ne = doc.eoj[m["head"]] + 1
                target = next((x for x in doc.etoks(ne) if toks[x].base_tag in NOUN_TAGS | {"NP"}), None) \
                    if ne < len(doc.eojeols) else None
            else:
                target = self._subject_in(doc, [x for x in doc.clause_toks(doc.clause[m["head"]]) if x < m["a"]])
            if target is not None:
                f = toks[target].form
                if self._is_background(f) or f in self.prop_background or f in self.body_forms or f in self.self_words:
                    m["status"] = "out_of_scope"
        return out

    def _proportions(self, doc: Doc, spec: dict) -> None:
        """G72: layout.proportions(스펙 2.4.0). 말하지 않았으면 null. 키 순서: layout = size · distance · verticalOffset · proportions."""
        pr = self.prop
        text = doc.text
        shape_model_drawn = spec["form"]["type"] in (None, "blob") and spec["form"]["base"] is None
        value, provs, alts, negated = None, [], [], []
        win = None
        for m in sorted(self._proportion_matches(doc), key=lambda m: (m["s"], m["e"])):
            if m["status"] == "out_of_scope":
                continue
            prof = pr["profiles"][m["profile"]]
            v = {"x": prof["x"], "y": prof["y"], "z": prof["z"], "axisSaid": prof["axisSaid"]}
            rule = f"proportions.{m['profile']}({m['tag']})>layout.proportions:{m['profile']}"
            p = self._prov("phrase_rule", text, m["s"], m["e"], rule)
            if m["status"] == "negated":
                negated.append({"lemma": m["lemma"], "category": "proportions", "_provenance": p})
                continue
            if m["shapeModel"] and shape_model_drawn:
                # 같은 낱말의 모양 모형(납작 원기둥)이 그려진다 → 한 번 더 납작하게 하지 않는다
                alts.append({"path": "layout.proportions", "value": v, "reason": "lower_priority",
                             "_provenance": [dict(p, rule=f"{rule}+shapeModel({m['shapeModel']})")]})
                continue
            if win is None:
                win, value, provs = m["profile"], v, [p]
            elif m["profile"] == win:
                provs.append(p)
            else:
                alts.append({"path": "layout.proportions", "value": v, "reason": "later_mention", "_provenance": [p]})
        pd = (pr.get("postureDirection") or {}).get(win or "", {}).get(spec["form"]["posture"])
        if value is not None and not value["axisSaid"] and pd is not None:
            # 방향을 말하지 않은 길쭉함 + 말한 자세가 방향을 정함('길쭉한 게 누워 있어요' → 가로가 김)
            prof = pr["profiles"][pd]
            value = {"x": prof["x"], "y": prof["y"], "z": prof["z"], "axisSaid": True}
            tag = f"+posture({spec['form']['posture']})"
            provs = [dict(p, rule=p["rule"] + tag) for p in provs]
        spec["layout"] = {**spec["layout"], "proportions": value}
        if value is not None:
            spec["_provenance"] = _ordered_provenance({**spec["_provenance"], "layout.proportions": provs})
        if alts:
            spec["_alternatives"] = sorted(spec["_alternatives"] + alts,
                                           key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                           al["reason"]))
        if negated:
            spec["_negated"] = sorted(spec["_negated"] + negated,
                                      key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
        if not (provs or alts or negated):
            return
        used = [p["charSpan"] for p in provs]
        for cl in spec.get("_clauses") or []:
            s, e = cl["charSpan"]
            if any(x < e and s < y for x, y in used):
                cl["usedFor"] = sorted(set(cl["usedFor"]) | {"layout.proportions"}, key=lambda q: (_PATH_ORDER.get(q, 99), q))
                if cl["status"] == "unused":
                    cl["status"] = "partly_used"
        covered: set[int] = set()
        _span_chars({"p": provs, "a": alts, "n": negated}, covered)
        spec["_unmapped"] = [u for u in spec["_unmapped"]
                             if not (u["category"] == "unlisted_noun"
                                     and all(ch in covered for ch in range(*u["_provenance"]["charSpan"])))]
        tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG
                     and not all(ch in covered for ch in range(u["charSpan"][0], u["charSpan"][1]))]
        spec["_unmatched"] = tok_level
        spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                    key=lambda u: (u["charSpan"][0], u["charSpan"][1]))

    # ── G74: 안개 입자 모양 ────────────────────────────────────────────────
    def _mist_location_form_type(self, doc: Doc, spec: dict) -> list[dict]:
        """G74 (나): form.type의 근거가 장소 용법('안개 속에'·'연기 사이로'·'안개에') 안개류 낱말(mistKinds 표)뿐이면 form.type을 비운다
        (G72 배경 낱말 규칙과 같은 뜻 — 둘레를 말한 것이지 형상이 아님). 내린 근거는 _alternatives(lower_priority, rule 끝 +location(…)).
        장소 용법이 아닌 근거가 남으면 그 근거만 남긴다. 돌려주는 것 = 더할 대안."""
        ftp = spec["_provenance"].get("form.type") or []
        if not ftp:
            return []
        toks = doc.toks
        nouns = self.mist["nouns"]
        keep, dropped = [], []
        for pv in ftp:
            ids = [k for k in doc.toks_in(*pv["charSpan"]) if toks[k].base_tag in NOUN_TAGS and toks[k].form in nouns]
            loc = None
            for k in ids:
                if self._noun_role(doc, k) == "location":
                    nx = k + 1
                    loc = doc.text[toks[k].start:doc.espan(doc.eoj[nx])[1]] if nx < len(toks) else toks[k].form
                    break
            (dropped if loc is not None else keep).append((pv, loc))
        if not dropped:
            return []
        out = [{"path": "form.type", "value": spec["form"]["type"], "reason": "lower_priority",
                "_provenance": [dict(pv, rule=f"{pv['rule']}+location({loc})") for pv, loc in dropped]}]
        if keep:
            spec["_provenance"]["form.type"] = [pv for pv, _ in keep]
        else:
            spec["_provenance"].pop("form.type")
            spec["form"]["type"] = None
        return out

    def _mist_fill_form_type(self, doc: Doc, spec: dict, live: list[dict], used: list) -> list[dict]:
        """G74 (가): 형상 자리(층 1)에서 말한 기체·먼지 낱말(mistKinds.fillFormType: 연기·매연·먼지류·황사)은 form.type을 mist로 채운다.
        form.type이 이미 있으면 그대로 두고 대안으로, 기본 형상(form.base)이 있으면 그것을 지키고 대안으로 남긴다.
        '모래·가루'(알갱이 고체 — 조각)·'구름'(G71-e — 덩어리/안개 갈림)·'김'은 채우지 않는다. 돌려주는 것 = 더할 대안."""
        fill = set(self.mist.get("fillFormType", []))
        text = doc.text
        out, provs = [], []
        for m in live:
            if m["layer"] == 1 and m["lemma"] in fill:
                provs.append(self._prov("explicit_lexicon", text, m["s"], m["e"], f"mistKinds.{m['lemma']}>form.type:mist"))
        if not provs:
            return out
        ft = spec["form"]["type"]
        if ft is None and spec["form"]["base"] is None:
            spec["form"]["type"] = "mist"
            spec["_provenance"] = _ordered_provenance({**spec["_provenance"], "form.type": provs})
            spans = [p["charSpan"] for p in provs]
            used += spans
            # 이 낱말의 사물 기록(_unmapped object '연기')은 이제 값의 근거다
            spec["_unmapped"] = [u for u in spec["_unmapped"]
                                 if not (u["category"] == "object" and any(u["_provenance"]["charSpan"][0] < e and s < u["_provenance"]["charSpan"][1]
                                                                           for s, e in spans))]
        elif ft == "mist":
            spec["_provenance"]["form.type"] = sorted(spec["_provenance"]["form.type"] + provs, key=lambda p: p["charSpan"][0])
            used += [p["charSpan"] for p in provs]
        else:
            tag = "+keptFormType" if ft is not None else f"+base({spec['form']['base']})"
            out.append({"path": "form.type", "value": "mist", "reason": "lower_priority",
                        "_provenance": [dict(p, rule=p["rule"] + tag) for p in provs]})
        return out

    def _mist_kind_matches(self, doc: Doc, spec: dict) -> list[dict]:
        """mistKinds 표 낱말이 형상 자리에 나온 곳. 같은 글 → 같은 목록(문서만 본다). 항목: kind · lemma · s·e(글자 구간) ·
        layer(1 직접, 2 비교 원천) · marker(비교 표지) · status(ok | negated | vehicle) · tag(움직임 비유 꼬리표) · retracted."""
        toks, text, mk = doc.toks, doc.text, self.mist
        nouns: dict[str, str] = mk["nouns"]
        reject = set(mk.get("rejectNextTags", []))
        homs: dict[str, dict] = mk.get("homonyms", {})
        phrases = self._phrases(doc)
        phrase_of = {x: p for p in phrases for x in p["nouns"]}
        by_last = {p["b"]: p for p in phrases}
        color_toks = {h.token_index for h in self.lexicon.hits(text) if h.entry.category == "color"}
        sim_of: dict[int, dict] = {}
        for sm in self._simile_markers(doc):
            p = by_last.get(sm["srcIndex"])
            if p is None or p["id"] in sim_of:
                continue
            kind, tgt = self._attach(doc, sm["markerIndex"], p["a"], phrase_of, color_toks)
            if kind == "phrase" and tgt is p:
                kind, tgt = "unresolved", None
            sim_of[p["id"]] = {"marker": sm["marker"], "kind": kind, "target": tgt}
        # 범위: 형상 낱말(D6 _base_shapes)과 같은 회상·상황 문장·상황절
        valued: set[int] = set()
        _span_chars(spec.get("_provenance"), valued)
        formal_etm = {sv["target"] - 1 for sv in sim_of.values() if sv["kind"] == "formal" and sv["target"] > 0
                      and toks[sv["target"] - 1].base_tag == "ETM"}
        recall = self._context_sentences(doc) | self._situation_sentences(doc, valued, skip_etm=formal_etm)
        regions = self._situation_regions(doc)
        acts = self._action_similes(doc) if self.act["demoteFormType"] else []
        veh = {k: a for a in acts for k in a["vehicles"]}
        out: list[dict] = []
        for p in phrases:
            ha, hb = p["headRun"]
            lemma, s, e = p["lemma"], p["hs"], p["he"]
            kind = nouns.get(lemma)
            if kind is None:
                h = toks[p["head"]]
                kind = nouns.get(h.form)
                lemma, s, e = h.form, h.start, h.end
            if kind is None:
                continue
            nx = hb + 1
            if nx < len(toks) and doc.eoj[nx] == doc.eoj[hb] and toks[nx].base_tag in reject:
                continue                                         # '연기됐어요'·'연기해요' — 다른 뜻
            if doc.sent[p["b"]] in recall or any(s0 <= p["a"] and p["b"] < k0 for s0, k0 in regions):
                continue                                         # 회상 문장·상황절
            sv = sim_of.get(p["id"])
            if sv is not None and sv["kind"] == "color":
                continue                                         # '먹구름처럼 시커먼' — 색 비교 기준
            direct = p["role"] in self.bs_roles
            if not direct and sv is None:
                continue                                         # 장소('안개 속에')·목적어·꾸밈말
            g = homs.get(lemma)
            if g is not None:
                cl = doc.clause[p["head"]]
                if not any((toks[k].form in g.get("predicates", []) and toks[k].base_tag in ("VV", "VA"))
                           or (toks[k].form in g.get("adverbs", []) and toks[k].base_tag == "MAG")
                           for k in doc.clause_toks(cl)):
                    continue                                     # '김' — 김이 나는 모양의 말이 같은 절에 없음
            neg = Lexicon._negated(toks, p["b"]) or self._noun_negated(doc, p["b"])
            if sv is not None and sv["kind"] == "formal":
                neg = neg or Lexicon._negated(toks, sv["target"])
            retracted = self._retracted(doc, p["b"])
            a = next((veh[x] for x in p["nouns"] if x in veh), None)
            status = "negated" if (neg or retracted) else ("vehicle" if a is not None else "ok")
            out.append({"kind": kind, "lemma": lemma, "s": s, "e": e, "layer": 1 if direct and sv is None else 2,
                        "marker": sv["marker"] if sv is not None else None, "status": status,
                        "tag": a["tag"] if a is not None else None, "retracted": retracted})
        return out

    def _mist_kind(self, doc: Doc, spec: dict) -> None:
        """G74: form.mistKind(스펙 2.4.0 선택 슬롯). 말하지 않았으면 null. form 묶음 맨 끝에 둔다."""
        text = doc.text
        value, provs, alts, negated = None, [], [], []
        ft_used: list[list[int]] = []                       # (가) form.type을 채운 근거 구간(기록 정리에 씀)
        alts += self._mist_location_form_type(doc, spec)    # (나) 장소 용법의 안개류 낱말은 form.type을 채우지 않음
        ms = self._mist_kind_matches(doc, spec)

        def prov(m: dict) -> dict:
            rule = f"mistKinds.{m['lemma']}>form.mistKind:{m['kind']}"
            if m["marker"] is not None:
                return self._prov("simile_marker", text, m["s"], m["e"], f"{rule}+simile({m['marker']})")
            return self._prov("explicit_lexicon", text, m["s"], m["e"], rule)

        live = []
        for m in sorted(ms, key=lambda m: (m["s"], m["e"])):
            if m["status"] == "negated":
                rule = f"mistKinds.{m['lemma']}" + ("+retracted(아니)" if m["retracted"] else "")
                negated.append({"lemma": m["lemma"], "category": "mist_kind",
                                "_provenance": self._prov("explicit_lexicon", text, m["s"], m["e"], rule)})
            elif m["status"] == "vehicle":
                p = prov(m)
                alts.append({"path": "form.mistKind", "value": m["kind"], "reason": "lower_priority",
                             "_provenance": [dict(p, rule=f"{p['rule']}+{m['tag']}")]})
            else:
                live.append(m)
        if live:
            top = min(m["layer"] for m in live)
            win = next(m for m in live if m["layer"] == top)
            value = win["kind"]
            for m in live:
                if m["kind"] == value:
                    provs.append(prov(m))
                else:
                    reason = "lower_layer" if m["layer"] > top else "later_mention"
                    alts.append({"path": "form.mistKind", "value": m["kind"], "reason": reason, "_provenance": [prov(m)]})
            alts += self._mist_fill_form_type(doc, spec, live, ft_used)
        spec["form"] = {**spec["form"], "mistKind": value}
        if value is not None:
            spec["_provenance"] = _ordered_provenance({**spec["_provenance"], "form.mistKind": provs})
        if alts:
            spec["_alternatives"] = sorted(spec["_alternatives"] + alts,
                                           key=lambda al: (_PATH_ORDER.get(al["path"], 99), al["_provenance"][0]["charSpan"][0],
                                                           al["reason"]))
        if negated:
            spec["_negated"] = sorted(spec["_negated"] + negated,
                                      key=lambda x: (x["_provenance"]["charSpan"][0], x["lemma"], x["category"]))
        if not (provs or alts or negated):
            return
        used = [p["charSpan"] for p in provs]
        for cl in spec.get("_clauses") or []:
            s, e = cl["charSpan"]
            for path, spans in (("form.mistKind", used), ("form.type", ft_used)):
                if any(x < e and s < y for x, y in spans):
                    cl["usedFor"] = sorted(set(cl["usedFor"]) | {path}, key=lambda q: (_PATH_ORDER.get(q, 99), q))
                    if cl["status"] == "unused":
                        cl["status"] = "partly_used"
        covered: set[int] = set()
        _span_chars({"p": provs, "a": alts, "n": negated}, covered)
        spec["_unmapped"] = [u for u in spec["_unmapped"]
                             if not (u["category"] == "unlisted_noun"
                                     and all(ch in covered for ch in range(*u["_provenance"]["charSpan"])))]
        tok_level = [u for u in spec["_unmatched"] if u["tag"] != EOJEOL_TAG
                     and not all(ch in covered for ch in range(u["charSpan"][0], u["charSpan"][1]))]
        spec["_unmatched"] = tok_level
        spec["_unmatched"] = sorted(tok_level + self._unmatched_eojeols(doc, spec),
                                    key=lambda u: (u["charSpan"][0], u["charSpan"][1]))

    def _resultative(self, doc: Doc, k: int) -> bool:
        """용언 k가 결과 상태 꼴인가: 완료 관형형('퍼진')이나 '-어 있-'('퍼져 있어요')."""
        toks = doc.toks
        n = len(toks)
        nx = toks[k + 1] if k + 1 < n and doc.eoj[k + 1] == doc.eoj[k] else None
        if nx is None:
            return False
        if nx.base_tag == "ETM" and nx.form in self.act["resultativeETM"]:
            return True
        return (nx.base_tag == "EC" and nx.form in ("어", "아", "여") and k + 2 < n
                and toks[k + 2].form in self.act["resultativeAux"] and toks[k + 2].base_tag == "VX")

    def _said_phrase_cands(self, doc: Doc) -> list[Cand]:
        """'보통 크기'·'크기는 보통이에요' → layout.size(neutralSize), '무광'·'유광' → material.roughness(surfaceTerms)."""
        toks = doc.toks
        n = len(toks)
        out: list[Cand] = []
        ns = self.neutral_size
        words, topics = set(ns["words"]), set(ns["topics"])
        for i, t in enumerate(toks):
            if t.form not in words or t.base_tag not in ("NNG", "MAG", "XR") or Lexicon._negated(toks, i):
                continue
            c = doc.clause[i]
            before = i + 1 < n and toks[i + 1].form in topics and toks[i + 1].base_tag in NOUN_TAGS \
                and doc.clause[i + 1] == c and doc.eoj[i + 1] == doc.eoj[i] + 1
            last = doc.eojeols[doc.eoj[i]][1]
            tail_ok = all(toks[k].base_tag in PUNCT_TAGS or toks[k].base_tag.startswith(("J", "E"))
                          or toks[k].base_tag in ("VCP", "XSN", "XSA") for k in range(i + 1, last + 1)) \
                and all(toks[k].base_tag in PUNCT_TAGS for k in doc.clause_toks(c) if k > last)
            topic_first = any(toks[k].form in topics and toks[k].base_tag in NOUN_TAGS
                              for k in doc.clause_toks(c) if k < i)
            if not (before or (topic_first and tail_ok)):
                continue
            rule = f"neutralSize.{t.form}>layout.size:{_num_text(ns['value'])}"
            out.append(Cand("layout.size", ns["value"], i, t.start, [self._eoj_prov(doc, i, rule, source="phrase_rule")],
                            klass=1, dim_topic=before))
        for e in range(len(doc.eojeols)):
            w = doc.etext(e)
            term = next((k for k in self.surface_terms if w.startswith(k)), None)
            if term is None:
                continue
            ids = list(doc.etoks(e))
            s = doc.espan(e)[0]
            covering = [k for k in ids if toks[k].start < s + len(term)]
            if Lexicon._negated(toks, covering[-1]):
                continue
            d = self.surface_terms[term]
            out.append(Cand(d["path"], d["value"], ids[0], s,
                            [self._prov("phrase_rule", doc.text, s, s + len(term),
                                        f"surfaceTerm.{term}>{d['path']}:{d['label']}")]))
        return out

    def _shape_noun_records(self, doc: Doc, spec: dict) -> list[dict]:
        """모양 명사(shapeNouns: '구형'·'구체') → _unmapped category shape(모양어와 같은 자리). 부정되면 _negated에 남긴다.
        다른 명사(형태 틀 명사 말고)를 꾸미는 자리('구형 핸드폰')·접미사가 붙은 것('구체적')은 쓰지 않는다."""
        toks, text = doc.toks, doc.text
        n = len(toks)
        have = {tuple(u["_provenance"]["charSpan"]) for u in spec["_unmapped"] if u["category"] == "shape"}
        out = []
        for a, b in self._noun_runs(doc):
            s, e = toks[a].start, toks[b].end
            word = text[s:e]
            d = self.shape_nouns.get(word)
            if d is None or (s, e) in have:
                continue
            k = b + 1
            if k < n and doc.eoj[k] == doc.eoj[b] and toks[k].base_tag == "XSN" and toks[k].form in self.shape_noun_reject:
                continue
            if self._noun_role(doc, b) == "modifier" and not (k < n and toks[k].form in self.frame_nouns):
                continue
            prov = self._prov("phrase_rule", text, s, e, f"shapeNoun.{word}>shape:{d['shape']}")
            if Lexicon._negated(toks, b) or self._noun_negated(doc, b):
                spec["_negated"].append({"lemma": word, "category": "shape", "_provenance": prov})
                continue
            out.append({"lemma": word, "category": "shape", "value": {"shape": d["shape"]}, "reason": "no_scene_param",
                        "_provenance": prov})
        return out

    def _in_shape_frame(self, doc: Doc, p: dict) -> bool:
        """명사구 p가 형태 틀 안의 말인가('모양은 그릇 같아요', '그릇 모양이에요')."""
        toks = doc.toks
        if any(toks[x].form in self.frame_nouns for x in p["nouns"]):
            return True
        c = doc.clause[p["a"]]
        return any(toks[k].form in self.frame_nouns and toks[k].base_tag in NOUN_TAGS
                   and self._noun_role(doc, k) == "subject" for k in doc.clause_toks(c) if k < p["a"])

    def _direct_shapes(self, doc: Doc, spec: dict, phrase_of: dict, color_toks: set[int], veh: dict,
                       context_sents: set[int], sim_markers: list[int]) -> list[dict]:
        """직접 형태 진술(shapePriority.directShape): 형상 낱말·움직임 비유 매개어를 꾸미거나 서술하지 않는 모양어."""
        toks = doc.toks
        stmt = set(self.dshape["statementShapes"])
        out = []
        for u in spec["_unmapped"]:
            if u["category"] != "shape" or u["reason"] in ("excluded_shape", "no_asset"):
                continue
            shape = (u["value"] or {}).get("shape")
            cs = u["_provenance"]["charSpan"]
            ids = doc.toks_in(cs[0], cs[1])
            if shape not in stmt or not ids or doc.sent[ids[0]] in context_sents or any(x in veh for x in ids):
                continue
            x0 = ids[0]
            pq = phrase_of.get(x0)
            if pq is not None:
                tgt = pq if x0 != pq["head"] else None
            else:
                kind, tgt = self._attach(doc, ids[-1], ids[0], phrase_of, color_toks)
                if kind != "phrase":
                    tgt = None
            if tgt is not None and (tgt["entry"] is not None or any(x in veh for x in tgt["nouns"])):
                continue                      # '동그란 천' · '천은 동그래요' — 형상 낱말을 말한 것
            if any(doc.clause[m] == doc.clause[x0] and m < x0 for m in sim_markers):
                continue                      # '종이처럼 납작해요' — 비유가 꾸미는 서술
            xe = doc.eojeols[doc.eoj[ids[-1]]][1]
            if toks[xe].base_tag == "EC" and toks[xe].form in ("게", "케"):
                nv = next((k for k in range(xe + 1, len(toks)) if doc.clause[k] == doc.clause[x0]
                           and toks[k].base_tag in ("VV", "VA")), None)
                if nv is None or toks[nv].form not in self.dshape["adverbialVerbs"]:
                    continue                  # '저를 둥글게 감싸고' — 움직임·모양새를 꾸미는 부사형('둥글게 생겼어요'만 진술)
            out.append({"lemma": u["lemma"], "shape": shape, "s": cs[0]})
        return sorted(out, key=lambda d: d["s"])

    def _subject_in(self, doc: Doc, ids: list[int]) -> int | None:
        """토큰 목록에서 마지막 주어(체언 + 이/가/은/는/도)의 토큰 번호."""
        toks = doc.toks
        n = len(toks)
        out = None
        for x in ids:
            if toks[x].base_tag not in NOUN_TAGS | {"NP", "NNB"}:
                continue
            m = x + 1
            while m < n and toks[m].base_tag == "XSN":
                m += 1
            if m < n and doc.eoj[m] == doc.eoj[x] and toks[m].form in self.subj_particles \
                    and toks[m].base_tag in ("JKS", "JX"):
                out = x
        return out

    def _self_posture(self, doc: Doc, i: int) -> str | None:
        """자세어 토큰 i가 참여자 자신의 상태를 말하면 _context reason, 아니면 None(형상의 자세)."""
        toks = doc.toks
        n = len(toks)
        # ① 상황절: 자세어 어절(+ 바로 뒤 보조 용언 어절)이 관형형 + 때 … 또는 -면으로 끝남
        e0 = doc.eoj[i]
        eojs = [e0]
        if e0 + 1 < len(doc.eojeols) and toks[doc.eojeols[e0 + 1][0]].base_tag == "VX":
            eojs.append(e0 + 1)
        tail = [k for e in eojs for k in doc.etoks(e) if k > i]
        if any(toks[k].base_tag == "EC" and toks[k].form in self.cond_endings for k in tail):
            return "recollection_sentence"
        last = doc.eojeols[eojs[-1]][1]
        if toks[last].base_tag == "ETM" and last + 1 < n and toks[last + 1].form in self.sit_nouns \
                and doc.sent[last + 1] == doc.sent[i]:
            return "recollection_sentence"
        # ② · ③ 주어: 같은 절에서 먼저, 없으면 같은 문장의 앞 절(가까운 것부터)
        c = doc.clause[i]
        subj = self._subject_in(doc, [k for k in doc.clause_toks(c) if k < i])
        cc = c - 1
        while subj is None and cc >= 0:
            ids = doc.clause_toks(cc)
            if not ids or doc.sent[ids[0]] != doc.sent[i]:
                break
            subj = self._subject_in(doc, ids)
            cc -= 1
        if subj is None:
            return None
        st = toks[subj]
        if st.form in self.self_words and st.base_tag == "NP":
            return "background_subject"
        if st.form in self.body_forms:
            pe = doc.eoj[subj] - 1
            if pe < 0 or doc.eoj_clause(pe) != doc.clause[subj] or doc.is_punct_eoj(pe):
                return "background_subject"           # '몸이 축 처져요' — 소유자 없는 신체 부위 = 참여자 몸
            owner = [k for k in doc.etoks(pe) if toks[k].base_tag in NOUN_TAGS | {"NP"}]
            if not owner or (toks[owner[0]].form in self.self_words and toks[owner[0]].base_tag == "NP"):
                return "background_subject"           # '제 몸이' 또는 앞 어절이 소유자가 아님
            return None                               # '그 사람 어깨가' — 형상의 몸
        return None

    # ── D2(a)(b): 사전 후보 다듬기 ────────────────────────────────────────────
    def _lexicon_cands(self, doc: Doc, hits: list[Hit], consumed: set[int], similes, body_any: bool,
                       unmapped: list, negated: list, records) -> list[Cand]:
        toks = doc.toks
        # '투명에 가까운' — 가깝 앞 어절이 투명도 낱말 + 에면 거리 말이 아니다(v1은 색에만 이 규칙을 씀)
        near_opacity: set[int] = set()
        for h in hits:
            if h.entry.category != "distance" or h.entry.lemma not in self.op["nearPredicates"] or h.token_index in consumed:
                continue
            pe = doc.eoj[h.token_index] - 1
            if pe < 0 or doc.eoj_clause(pe) != doc.clause[h.token_index]:
                continue
            ts = list(doc.etoks(pe))
            if toks[ts[0]].form in self.opacity_nouns and toks[ts[-1]].base_tag == "JKB" and toks[ts[-1]].form == "에":
                consumed.add(h.token_index)
                near_opacity.add(ts[0])
        all_hit_toks = {h.token_index for h in hits}
        if self.ext is not None:
            # 1층 사전 v2의 윤곽·발광 범주는 v1 경로에 넣지 않는다(장면 대응이 없어 _unmapped로 가지 않게). _extension이 읽는다
            hits = [h for h in hits if h.entry.category not in EXT_CATEGORIES]
        by_tok: dict[int, list[Hit]] = {}
        for h in hits:
            by_tok.setdefault(h.token_index, []).append(h)
        # 2.6.0: 동음이의 막기 — '구체적으로'·'구체화'의 '구체'(具體)는 1층 사전의 '구체'(球體, form blob)로 읽지 않는다
        hits = [h for h in hits if not self._homonym_blocked(doc, h)]
        if self.prop is not None:
            # G72: 결과 상태 꼴로 비율을 채운 용언('넓게 펼쳐진')은 움직임 값을 만들지 않는다(퍼진 상태이지 움직임이 아님)
            still = {m["head"] for m in self._proportion_matches(doc) if m["status"] == "ok" and m["resultative"]}
            hits = [h for h in hits if not (h.entry.category == "movement" and h.token_index in still)]
        out = super()._lexicon_cands(doc, hits, consumed, similes, body_any, unmapped, negated, records)
        keep = []
        for c in out:
            rule = c.provs[0]["rule"]
            if c.path == "material.opacity" and rule.endswith(":transparent"):
                self._transparent(doc, c, c.tok in near_opacity)
            elif c.path == "layout.distance" and rule.endswith(":attached"):
                lem = next((h.entry.lemma for h in by_tok.get(c.tok, []) if h.entry.category == "distance"), None)
                if lem in self.attach_lemmas and self._attached_to_body(doc, c.tok, body_any):
                    unmapped.append({"lemma": lem, "category": "distance", "value": {"distance": "attached"},
                                     "reason": "no_scene_param", "_provenance": dict(c.provs[0], rule=rule.split(">")[0])})
                    continue
            keep.append(c)
        if self.variants is not None:
            keep += self._variant_cands(doc, all_hit_toks, consumed, similes, negated, unmapped)
        return keep

    def _transparent(self, doc: Doc, c: Cand, near: bool) -> None:
        """'투명' 후보의 값을 정도 표현에 맞춘다(D2(a)). 바꾸면 rule 끝에 +표시를 단다."""
        op = self.op
        rule = c.provs[0]["rule"]
        _, f = self._degree(doc, c.tok)
        word = doc.etext(f) if f is not None else None
        pe = doc.eoj[c.tok] - 1
        prev = doc.etext(pe) if pe >= 0 and doc.eoj_clause(pe) == doc.clause[c.tok] and not doc.is_punct_eoj(pe) else None
        if near or word in op["nearlyWords"]:
            c.value, tag = op["nearlyTransparent"], f"nearly({'가깝' if near else word})"
        elif word in op["totalWords"]:
            c.value, tag = op["total"], f"total({word})"
        elif prev in op["halfWords"]:
            c.value, tag = op["halfValue"], f"half({prev})"
        elif isinstance(c.value, (int, float)) and c.value < op["floor"]:
            c.value, tag = op["floor"], f"floor({op['floor']})"
        else:
            return
        c.provs = [dict(c.provs[0], rule=f"{rule}+{tag}"), *c.provs[1:]]

    def _attached_to_body(self, doc: Doc, i: int, body_any: bool) -> bool:
        """'붙다'(토큰 i)가 몸에 붙었다는 말인가.
        ① 같은 절 i 앞에 '신체 부위(+ 쪽) + 에'·'저한테' → 예 ② 같은 절 i 앞에 다른 처소어('눈앞에'·'얼굴 앞에') → 아니오
        (그 자리에 가깝게 붙음: 거리 값 + 하한) ③ 처소어가 없으면 텍스트에 신체 부위 위치를 말했을 때(body_any) 예
        ('옆구리 쪽에 뭔가 붙어 있어요 … 가만히 붙어 있어요')."""
        toks = doc.toks
        other_loc = False
        for x in doc.clause_toks(doc.clause[i]):
            if x >= i or toks[x].base_tag not in NOUN_TAGS | {"NP"}:
                continue
            k = x + 1
            while k < len(toks) and toks[k].form == "쪽" and toks[k].base_tag in ("NNB", "NNG", "XSN"):
                k += 1
            if k >= len(toks) or toks[k].base_tag != "JKB" or toks[k].form not in self.attach_particles:
                continue
            t = toks[x]
            if t.form in self.body_forms or (t.form in self.self_words and t.base_tag == "NP"):
                return True
            other_loc = True
        return not other_loc and body_any

    # ── D2(b): 높이 말 옆 수치 ────────────────────────────────────────────────
    def _measure_dimension(self, doc: Doc, ids: list[int], s: int, e: int) -> tuple[str, str | None]:
        dim, cue = super()._measure_dimension(doc, ids, s, e)
        if dim != "distance":
            return dim, cue
        c = doc.clause[ids[0]]
        near = [k for k in doc.clause_toks(c) if ids[0] - 3 <= k < ids[0] or max(ids) < k <= max(ids) + 3]
        if any(doc.toks[k].form in self.vertical_cues for k in near):
            return "unknown", "vertical"
        return dim, cue

    # ── D2(d): '가슴 앞을 덮고' ───────────────────────────────────────────────
    def _ref_noun(self, doc: Doc, i: int, table: dict[str, float]):
        r = super()._ref_noun(doc, i, table)
        if r is not None and table is self.cover and r[0] in self.v["relationalNouns"]:
            a = r[1]
            if a > 0 and doc.toks[a - 1].form in self.body_forms and doc.clause[a - 1] == doc.clause[a]:
                return None
        return r

    # ── 병합 전: 거리 하한 · 부분 투명도 ─────────────────────────────────────
    def _merge(self, cands: list[Cand], uncertain_paths: set[str], records):
        keep = []
        floor = self.dist_floor
        for c in cands:
            if c.path == "layout.distance" and isinstance(c.value, (int, float)) and c.value < floor:
                # G33: 하한은 유지하고 말한 값과 그려진 값을 둘 다 남긴다. 그려진 값 = 슬롯 값(하한), 말한 값 = rule 꼬리표의
                # said=…(스키마 2.1에는 이 둘을 구조로 담을 자리가 없어 provenance rule 문자열에 적는다. floor_record()가 읽는다)
                said = c.value
                c.value = floor
                c.provs = [dict(c.provs[0], rule=f"{c.provs[0]['rule']}+floor({floor};said={_num_text(said)})"),
                           *c.provs[1:]]
            # 부분만 말한 투명도는 전체 값으로 올리지 않는다. 단 '속이 비쳐요'(안쪽 + 비치다)는 속이 들여다보인다는 말,
            # 곧 형상 전체가 비친다는 뜻이므로 v1처럼 전체 값으로 둔다(dev D02·D16)
            if c.path == "material.opacity" and c.status == "ok" and c.kind != "fuzzy" and (
                    c.part_class == "detail" or (c.part_class == "inner"
                                                 and not c.provs[0]["rule"].split("+")[0].endswith(":see_through"))):
                p = c.provs[0]
                records["_parts"].append({"text": p["trigger"], "charSpan": p["charSpan"], "part": c.part,
                                          "partClass": c.part_class, "path": c.path, "value": c.value,
                                          "rule": p["rule"]})
                continue
            keep.append(c)
        return super()._merge(keep, uncertain_paths, records)


# _provenance·_alternatives의 경로 순서(SceneSpec 슬롯 순서에 2.2 슬롯을 form.posture 뒤에, 2.3 슬롯을 form.baseVariant·
# material.erosion 뒤에 끼움. 2.3 슬롯은 ext_lexicon을 켰을 때만 나오므로 기본 출력의 순서는 그대로)
_PATH_ORDER = {p: k for k, p in enumerate((
    "form.type", "form.posture", "form.base", "form.baseVariant", "form.roundness", "form.aspect", "form.mistKind",
    "material.color", "material.brightness", "material.saturation", "material.roughness", "material.opacity",
    "material.erosion", "material.emission", "layout.size", "layout.distance", "layout.verticalOffset", "layout.proportions",
    "motion.type",
    "motion.speed", "body.part", "body.layer"))}


def _ordered_provenance(prov: dict) -> dict:
    return {k: prov[k] for k in sorted(prov, key=lambda k: (_PATH_ORDER.get(k, 99), k))}


def _num_text(v) -> str:
    """말한 값의 표기(소수 넷째 자리까지, 같은 값이면 언제나 같은 글)."""
    return repr(round(float(v), 4))


_FLOOR_TAG = re.compile(r"\+floor\(([0-9.]+)(?:;said=(-?[0-9.]+(?:[eE][-+]?[0-9]+)?))?\)$")


def floor_record(spec: dict) -> dict | None:
    """G33: 매퍼 v2가 거리 하한을 적용한 spec이면 {slot, said, drawn, floor, rule, trigger, charSpan}, 아니면 None.
    said = 참여자가 말한 값(하한 전, 매퍼 단위 0–1), drawn = 슬롯 값(하한, 미리보기에 그려지는 값).
    builder 2.0.0이 만든 spec(꼬리표 '+floor(0.1)', 말한 값 없음)은 said = None.
    배치 러너는 spec의 거리를 쓰지 않는다(시작 자리는 실험 설정, decisions.md G33)."""
    provs = (spec.get("_provenance") or {}).get("layout.distance") or []
    if not provs:
        return None
    m = _FLOOR_TAG.search(provs[0].get("rule") or "")
    if not m:
        return None
    drawn = (spec.get("layout") or {}).get("distance")
    return {"slot": "layout.distance", "said": float(m.group(2)) if m.group(2) is not None else None,
            "drawn": drawn, "floor": float(m.group(1)), "rule": provs[0]["rule"],
            "trigger": provs[0].get("trigger"), "charSpan": list(provs[0].get("charSpan") or [])}


def factory(rt) -> SceneSpecBuilderV2:
    """corpus_run·fidelity의 --mapper v2(= ifs_chatbot.scene_builder_v2:factory) 용."""
    return SceneSpecBuilderV2.from_runtime(rt)


def factory_variants(rt) -> SceneSpecBuilderV2:
    """--mapper ifs_chatbot.scene_builder_v2:factory_variants — 매퍼 v2 + 형태 변이 규칙층(스펙 2.2 그대로). G61 ②"""
    return SceneSpecBuilderV2(rt.analyzer, variant_rules_path=shared("lexicon", "variant_rules.v0.json"))


def factory_v23(rt) -> SceneSpecBuilderV2:
    """--mapper ifs_chatbot.scene_builder_v2:factory_v23 — 매퍼 v2 + 1층 사전 v2(윤곽·발광, 스펙 2.3). G61 ①"""
    return SceneSpecBuilderV2(rt.analyzer, ext_lexicon_path=shared("lexicon", "layer1_lexicon.v2.json"))


def factory_v23_variants(rt) -> SceneSpecBuilderV2:
    """--mapper ifs_chatbot.scene_builder_v2:factory_v23_variants — ①과 ②를 모두 켬."""
    return SceneSpecBuilderV2(rt.analyzer, ext_lexicon_path=shared("lexicon", "layer1_lexicon.v2.json"),
                              variant_rules_path=shared("lexicon", "variant_rules.v0.json"))


def load_lexicon_chain(analyzer: Analyzer, files: list) -> Lexicon:
    """v0 사전 + 오버레이들(차례대로)을 합친 1층 사전(load_lexicon_v1의 일반형). 오버레이는 v1과 같은 규칙:
    같은 (범주, 표제어, 품사)는 뒤 파일이 대신하고, remove의 (범주, 표제어)는 뺀다. 파일은 읽기만 한다."""
    paths = [Path(f) for f in files]
    data = json.loads(paths[0].read_text(encoding="utf-8"))
    infos = [f"{data.get('lexiconId')}@{data.get('lexiconVersion')}"]
    merged = data
    for p in paths[1:]:
        ov = json.loads(p.read_text(encoding="utf-8"))
        removed = {(r["category"], r["lemma"]) for r in ov.get("remove", [])}
        keys = {(e["category"], e["lemma"], e["pos"]) for e in ov["entries"]}
        entries = [e for e in merged["entries"]
                   if (e["category"], e["lemma"]) not in removed and (e["category"], e["lemma"], e["pos"]) not in keys]
        merged = {**merged, "lexiconId": ov.get("lexiconId", merged.get("lexiconId")),
                  "lexiconVersion": ov["lexiconVersion"],
                  "categories": {**merged["categories"], **ov.get("categories", {})},
                  "entries": entries + ov["entries"]}
        infos.append(f"{ov.get('lexiconId')}@{ov['lexiconVersion']}")
    lex = Lexicon(paths[-1], analyzer, data=merged)
    lex.base_info = infos[0]            # type: ignore[attr-defined]
    lex.chain_info = " + ".join(infos)  # type: ignore[attr-defined]
    return lex


def _attach_variant_records(spec: dict) -> None:
    """스펙 2.3: 형태 변이 규칙층 근거(rule 안의 'variant(…)')를 provenance.variant 구조로도 남긴다."""
    def fix(p: dict) -> None:
        rule = p.get("rule") or ""
        k = rule.find("variant(")
        if k >= 0:
            rec = parse_tag(rule[k:])
            if rec is not None:
                p["variant"] = rec

    for provs in (spec.get("_provenance") or {}).values():
        for p in provs:
            fix(p)
    for a in spec.get("_alternatives") or []:
        for p in a["_provenance"]:
            fix(p)
    for name in ("_unmapped", "_negated"):
        for item in spec.get(name) or []:
            fix(item["_provenance"])
    for inf in (spec.get("_inferred") or {}).values():
        for p in inf["_provenance"]:
            fix(p)
