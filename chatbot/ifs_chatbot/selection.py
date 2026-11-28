"""면담 뒤 데스크톱 단계: 4 후보 선택 · 5 조절 · 6 사전 측정 (D5·D9 데스크톱 쪽, 결정 G10·G11·G13·G15·G22·G23, G31–G34).

후보 단계는 면담 밖이다. 이 모듈은 LLM·면담 검증기(V1–V9)를 부르지 않는다(원칙 1·3). 입력은 확정 텍스트로 만든
SceneSpec 하나뿐이고(원칙 2), 원본 spec과 그 _provenance는 바꾸지 않는다(G15).

기록(참여자 자료, git 밖): <log_dir>/selection/<sessionId>/
  candidates.json  후보 생성기 출력 그대로(바이트 고정)
  selection.json   ifs-selection/0.2 (shared/schemas/selection.v0.2.json): 원본 spec 해시, 보여 준 후보와 순서, 고른 후보,
                   "맞는 것이 없다" 여부, 선택 단계를 건너뛰었는지(selection.skipped, G34), 조절 이력, 색을 바꿨는지
                   (colorChanged, G31), finalOverrides(Unity SceneOverrideJson 형식), 슬롯별 출처(네 가지 + 모형 없는 모양어
                   두 가지, G32), 거리 하한 기록(distanceFloor, G33), runnerReady·runnerBlockers(G26)
  premeasure.json  ifs-premeasure/0.1: 사전 측정 응답
세션 로그(elicit-log/0.1)에는 기존 events 배열에 요약만 더한다(형식 불변).
"""
from __future__ import annotations

import colorsys
import copy
import hashlib
import json
import os
import shutil
import threading
from pathlib import Path

from .candidates import (PROPORTION_KEYS, SLOTS, base_drawn, candidates_bytes, effective_params, form_blocks, form_said_unrendered, generate,
                         proportions_effective,
                         rendered_shape_words, safety_flags, said_words, slot_value, spec_sha256, unrendered_said_words)
from .form_assets import (DEFAULT_PROCEDURAL, R_NO_SHAPE_PREVIEW, R_PREVIEW_FAILED, _rej, add_generated,
                          generated_candidate_id, public_asset, source_key)
from . import llm_fill as llm_fill_mod
from . import llm_shape as llm_shape_mod
from . import none_gen as ng
from .paths import shared
from .scene_builder import normalize_confirmed
from .scene_builder_v2 import floor_record
from .session_log import now_iso

# 0.2(2026-11-23, G31–G34): selection.skipped·skipReason, colorChanged, 출처 값 두 개 추가(said_unrendered_chosen·
# said_unrendered_default), sourceDetails.saidWords, distanceFloor, candidatesShownAt null 허용. 러너는 0.1·0.2를 모두 읽는다.
# (G45–G51, 하위 호환 추가 — 0.2 그대로) saidWords.unrenderedBy·category(말했지만 그리지 않은 이유), 맨 위 safetyFlags(G50 (4)),
# sourceDetails.form.type.formBlocked(G50 (1) — 형태 후보를 내지 않음, 조절의 형태 바꾸기는 막지 않음)
FORMAT_VERSION = "ifs-selection/0.2"
# 0.3(G62, [gen3d] enabled일 때만 — 꺼져 있으면 0.2 그대로): 출처 값 generated_chosen(생성 형태 후보를 고름), 맨 위 form.asset
# (고른 생성 메시: assetId·glb·glbSha256·pipeline·seed·models·promptText …, 아니면 null), generation(조회 키, 제시한 생성 후보,
# 차단·실패·관문 탈락 등 거부 사유, 고른 결과·고르지 않은 생성 후보, 형태를 고쳐 버린 자산). 후보 sources 값 generated, 후보 origin·asset.
# G73([gen3d] on_none만 켰을 때): 처음 [맞는 게 없어요]를 누르는 순간 0.3으로 올린다(그 전·누르지 않은 세션은 0.2 그대로).
# 단계 generating(생성 대기), generation.afterNone(none 시각·규칙 프롬프트·모델 내림·생성 시작·끝·결과·사유·만든 후보·골랐는지),
# 후보 origin·sources form.type 값 generated_after_none, form.asset.origin, sourceDetails.form.type.origin, selection.afterNoneGeneration.
FORMAT_VERSION_GEN3D = "ifs-selection/0.3"
# 0.4(G75, [gen3d] on_none_image_pick을 켰을 때만 — 끄면 0.3 그대로): 처음 [맞는 게 없어요]를 누르는 순간 0.4로 올린다.
# 0.3에 선택 필드만 더함: 단계 picking(참고 이미지 고르기), generation.afterNone.imagePick(회차마다 seed·이미지 sha256·관문 결과·
# 보여 준 순서·고른 자리 또는 없음/넘어감·시각·프롬프트 판), generation.imagePickExposed(이미지 화면에 노출됐는가),
# afterNone.status·selection.afterNoneGeneration 값 declined(모든 회차에서 [이 중에는 없어요]), afterNone.seed null(고르기 전).
FORMAT_VERSION_IMAGE_PICK = "ifs-selection/0.4"
# 0.5(G77, [mapping] llm_fill을 켰을 때만 — 끄면 0.2·0.3·0.4 그대로): 후보를 만들 때부터 0.5. 0.4에 선택 필드만 더함: 맨 위 llmFill(확정 직후
# LLM 빈칸 채우기 기록 — 모델 digest·프롬프트 판·온도·seed·소요 시간·원시 항목·항목별 검증 결과·기각 사유·채택 값·후보에 넣은 처음 값·참여자가
# 그대로 뒀는지/고쳤는지·최종 값), llmFillExposed(채택 값이 화면에 하나라도 반영됨), 출처 값 llm_quoted(sources·sourceDetails·후보 sources),
# sourceDetails.*.llmQuote, candidates.prefill, generation.llmPromptUsed·afterNone.llmPromptUsed(그림 프롬프트 형태 자리를 LLM 낱말로 메움).
# 러너(PlacementSelection.cs)는 0.5를 0.3 규칙으로 읽고 출처 값 llm_quoted를 받는다(SourceValues05).
FORMAT_VERSION_LLM_FILL = "ifs-selection/0.5"
# (G82, [gen3d] on_none_llm_shape를 켰을 때만 — 끄면 그대로) 0.5에 선택 필드만 더함: generation.shapeLlm(경로 rule|llm|none, 부름·후보·채택·
# 노출·그림 고름·만든 후보 고름·[그 말이 아니에요], 입력 해시·모델 digest·프롬프트 판·검증기 판·seed·원시 출력·기각 사유, 호출 기록 call),
# afterNone.shapeLlmUsed·shapeLlmItems·basisRejected, imagePick.outcome 값 basis_rejected. 러너는 generation을 읽지 않는다(무시).
# G82를 켜면 llm_fill이 꺼져 있어도 처음부터 0.5로 쓴다(출처 값 목록은 0.5 그대로).
SHAPE_LLM_RECORD_VERSION = "ifs-shape-llm-record/0.1.0"
SHAPE_BASIS_PHRASE_KEYS = ("llm_shape_basis", "llm_shape_basis_wrong_button")
GENERATED_CHOSEN = "generated_chosen"
PREMEASURE_VERSION = "ifs-premeasure/0.1"
ITEMS = ("color", "form", "brightness", "opacity", "size", "texture", "motion")   # G31: 색이 맨 앞(표 adjustItems.order와 같음)
# G72: 너비·높이·깊이(값 표 3.0.0에만 있음 — 표에 없는 항목은 화면·기록에 나오지 않는다). 항목 → 축
PROPORTION_ITEMS = {"width": "x", "height": "y", "depth": "z"}
ITEMS_ALL = ITEMS[:5] + tuple(PROPORTION_ITEMS) + ITEMS[5:]
PROPORTION_SLOT = "layout.proportions"
PROPORTION_RULE = ("그리는 비율 = clamp(원값 / 세 원값의 최대, 0.2, 1) — 가장 큰 축 = 1. 가장 긴 변의 길이는 layout.size가 정한다"
                   "(G62-e, G72). 원값은 조절 단계(0.25–2.0), 시작 값은 말한 비율(spec layout.proportions) 또는 1.0")
NONE_CHOICE = "none"
SKIP_REASON = "single_distinct_candidate"      # G34: 구별되는 후보가 하나뿐이라 선택 단계를 건너뜀
# 슬롯 출처(G15 네 가지 + G32 두 가지). 러너(PlacementSelection.cs SourceValues)와 스키마 $defs.source가 같은 목록이다.
SOURCES = ("said", "chosen", "edited", "default", "said_unrendered_chosen", "said_unrendered_default")
SOURCES_GEN3D = SOURCES + (GENERATED_CHOSEN,)      # 0.3(G62)
SOURCES_LLM_FILL = SOURCES_GEN3D + (llm_fill_mod.ORIGIN,)   # 0.5(G77)
SAID_NOT_IN_TABLE = "said_value_not_in_table"

# G79: 색상 고리(값 표 4.0.0, 색 항목 kind hue_ring). 3.0.0 이하 표(kind swatch)는 아래를 쓰지 않아 출력·기록이 그대로다.
# 선택 파일 형식은 ifs-selection/0.5 그대로 두고 선택 속성만 더한다: 맨 위 colorRing, 색 값의 hueStep·saturationStep, 색 조작의 input.
COLOR_RING_VERSION = "ifs-color-ring/0.1.0"
RING_SAID = "said"          # 말한 색이 칸·단계 사이 값일 때 그 자리(G79-c). 입력 "said" = 말한 색 그대로
# 색 출처(colorRing.initial·final.origin): 말함 | 면담 LLM이 인용과 함께 채움(G77) | 말하지도 고르지도 않음 | 참여자가 고름
RING_ORIGINS = ("said", "llm_quoted", "unspecified", "picked")
RING_ORIGIN_RULE = ("initial: 확정 spec에 색·채도가 있으면 said, 없고 G77 처음 값이 들어갔으면 llm_quoted, 아니면 unspecified. "
                    "final: 색 조작이 없으면 initial 그대로, initial이 unspecified인데 한 번이라도 눌렀으면 picked(기본 회색 견본을 "
                    "눌러도 — 기본색과 고른 회색을 가름), 마지막 값이 처음 값과 같으면 initial 그대로, 다르면 picked. "
                    "sources.material.color(러너 계약)는 이 규칙과 별개로 G15 규칙 그대로다")
_MISSING = object()
# 고리 화면이 쓰는 고정 문구(selection_protocol 0.11.0). 값 표가 hue_ring이면 Runtime이 시작할 때 이 키들이 있는지 본다(CP18-1)
RING_PHRASE_KEYS = ("adjust_color_ring_hint", "adjust_color_ring_value", "adjust_color_saturation_label")
RING_SNAP = 0.0005          # 말한 h·s가 칸·단계 값과 이만큼 안이면 같은 자리(매퍼 값의 소수 셋째 자리 반올림 폭의 절반, 색상 0.18°)


def ring_hue(k: int, steps: int) -> float:
    """G79-a: 고리 칸 k의 색상 h(0–1). 6k번째 칸은 견본 h0k와 같은 값(round 4자리)."""
    return round(k / steps, 4)

# 러너에 넘길 수 없는 이유(runnerBlockers). 러너(PlacementSelection.cs)도 runnerReady = false면 이 글을 붙여 시작을 거부한다.
BLOCK_NO_SPEC_FILE = ("spec 파일이 저장되지 않은 실행입니다(persist_logs = false 또는 spec 저장 실패). 배치 러너는 저장된 spec "
                      "파일 바이트의 sha256만 비교하므로 이 선택 기록은 러너에 넘길 수 없습니다(G26)")
BLOCK_SPEC_FILE_CHANGED = ("저장된 spec 파일의 내용이 이 세션의 spec과 다릅니다(파일이 바뀌었음). 이 선택 기록은 러너에 넘길 수 "
                           "없습니다(G26)")
BLOCK_NOT_FINISHED = "조절을 마치지 않았습니다([다 고쳤어요] 전이라 finalOverrides·sources가 아직 없음)"


class SelectionError(Exception):
    """순서가 맞지 않는 요청(API 409)."""


class SelectionInvalid(SelectionError):
    """값·항목이 표에 없음(API 422)."""


# ── 고정 문구 ───────────────────────────────────────────────────────────────
class SelectionProtocol:
    def __init__(self, name: str = "selection_protocol.v0.json"):
        p = Path(name)
        self.path = p if p.is_absolute() else shared("protocol", name)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.protocol_id = self.data["protocolId"]
        self.version = self.data["protocolVersion"]

    def _entries(self):
        for k, v in self.data["phrases"].items():
            yield f"phrases.{k}", v
        for k, v in self.data["adjustItemLabels"].items():
            if not k.startswith("_"):
                yield f"adjustItemLabels.{k}", v
        pm = self.data["premeasure"]
        for k in ("instruction", "scale", "skipLabel"):
            yield f"premeasure.{k}", pm[k]
        for it in pm["items"]:
            yield f"premeasure.items.{it['id']}", it

    def draft_keys(self) -> list[str]:
        """status가 spec이 아닌 문구(X35 방식으로 화면·기록에 알린다)."""
        return [k for k, v in self._entries() if v.get("status") != "spec"]

    def text(self, key: str) -> str:
        return self.data["phrases"][key]["text"]

    def items(self) -> list[dict]:
        return list(self.data["premeasure"]["items"])

    def info(self) -> dict:
        keys = self.draft_keys()
        return {"protocolId": self.protocol_id, "protocolVersion": self.version, "file": self.path.name,
                "draftCount": len(keys), "draftKeys": keys}


def swatch_hex(sw: dict) -> str:
    r, g, b = colorsys.hls_to_rgb(sw["h"], sw["l"], sw["s"])
    return "#%02x%02x%02x" % tuple(int(round(c * 255)) for c in (r, g, b))


# 미리보기 방식별로 화면에 반영되지 않는 조절 항목(G22: 반영되지 않는 조합은 화면에서 그 항목을 끈다).
# image = 상주 플레이어의 정지 PNG(PreviewQueue가 그리기 전에 FreezeMotion) → 움직임 값을 바꿔도 그림이 같다.
# webgl 조절 화면은 iframe 안에서 움직임이 재생되고, none(글 요약)은 요약 글에 motion.type이 바뀌어 나온다.
STILL_PREVIEW_UNAVAILABLE = {"image": {"motion": "still_image_preview"}}
PREVIEW_CLIENT_EVENTS = ("shown", "fallback", "asset_failed")   # asset_failed(G62): 생성 형태 GLB 하나를 그리지 못함
PREVIEW_STAGES = ("selecting", "adjusting")


def _same_value(a, b) -> bool:
    """조절 항목 값 비교. 색은 h·s·l만 본다(견본 id 유무는 무시)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return all(abs(a[k] - b[k]) < 1e-9 for k in ("h", "s", "l"))
    return a == b


FORM_SLOTS = ("form.type", "form.base", "form.baseVariant")   # 조절 항목 "형태" 한 번이 정하는 세 슬롯(G39)


def variant_for(spec: dict, base_value):
    """G39: 지금 base 값(덮어쓰기 뒤)에서 쓰이는 변형값. Unity SceneParams.CurrentBaseVariant와 같은 규칙 — base가 spec의 base와
    같을 때만 spec의 form.baseVariant, 다르면 None(새 형상은 프리셋 기본값으로 그림). base를 바꿨다가 되돌리면 다시 spec의 값."""
    sb = slot_value(spec, "form.base")
    return slot_value(spec, "form.baseVariant") if sb is not None and base_value == sb else None


def variant_key_basis(spec: dict) -> dict | None:
    """G38: form.baseVariant 키마다 근거. lexicon_implied = 형상 낱말의 사전 뜻에서 옴('그릇' → opening wide),
    said = 같은 문장에서 참여자가 직접 한 말('엉켜' → form tangle). provenance source(lexicon_implied, builder 2.3.0)
    또는 rule 앞부분('baseShapes.' = 낱말 뜻, 'baseVariantCue.' = 참여자 말)으로 가른다 — builder 2.2.0 spec(source가 모두
    explicit_lexicon)도 rule로 같은 결과가 된다. 변형값이 없으면 None."""
    var = slot_value(spec, "form.baseVariant")
    if not var:
        return None
    basis = {}
    for pv in (spec.get("_provenance") or {}).get("form.baseVariant") or []:
        rule = pv.get("rule") or ""
        head, _, tail = rule.partition(">form.baseVariant:")
        key = tail.split("=", 1)[0]
        if key in var:
            implied = pv.get("source") == "lexicon_implied" or head.startswith("baseShapes.")
            basis[key] = "lexicon_implied" if implied else "said"
    return {k: basis.get(k, "said") for k in sorted(var)}


def selection_dir(log_dir: Path, session_id: str) -> Path:
    return Path(log_dir) / "selection" / session_id


def delete_selection_dir(log_dir: Path, session_id: str) -> bool:
    d = selection_dir(log_dir, session_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
        return True
    return False


def ui_config(protocol: SelectionProtocol, table: dict, preview_info: dict, enabled: bool,
              participant_draft_banner: bool = True) -> dict:
    """웹 화면이 그리는 데 쓰는 고정 정보(문구 원문, 항목 이름, 값 목록). 값에는 이름을 붙이지 않는다.
    participantDraftBanner = false면 초안 문구 경고 줄(X35)을 연구자 보기에서만 그린다(G59, 기록은 그대로)."""
    items = table["adjustItems"]["items"]
    labels = protocol.data["adjustItemLabels"]
    adjust = []
    for name in table["adjustItems"]["order"]:
        it = items[name]
        entry = {"id": name, "label": labels[name]["text"], "kind": it["kind"]}
        if it["kind"] == "swatch":
            entry["values"] = [{"id": s["id"], "hex": swatch_hex(s)} for s in it["swatches"]]
        elif it["kind"] == "hue_ring":
            # G79: 화면에는 무채색 견본(screenSwatches)과 고리만. 고리 칸·채도 단계는 세션마다 view().colorRing(말한 명도·말한 자리)
            by_id = {s["id"]: s for s in it["swatches"]}
            entry["values"] = [{"id": i, "hex": swatch_hex(by_id[i])} for i in it["screenSwatches"]]
            entry["ring"] = {"hueSteps": it["hueSteps"], "saturationSteps": list(it["saturationSteps"])}
        else:
            entry["values"] = list(it["values"])
        adjust.append(entry)
    pm = protocol.data["premeasure"]
    return {
        "enabled": enabled,
        "participantDraftBanner": bool(participant_draft_banner),
        "protocol": protocol.info(),
        "phrases": {k: v["text"] for k, v in protocol.data["phrases"].items()},
        "adjustItems": adjust,
        "premeasure": {"instruction": pm["instruction"]["text"], "scale": {k: pm["scale"][k] for k in ("min", "max", "anchors")},
                       "skipLabel": pm["skipLabel"]["text"], "items": [{"id": i["id"], "text": i["text"]} for i in pm["items"]]},
        "preview": preview_info,
        "previewWarmup": preview_warmup(table),
        "table": {"tableVersion": table["tableVersion"]},
    }


def preview_warmup(table: dict) -> list[dict]:
    """WebGL 준비 단계에서 한 번씩 미리 그릴 덮어쓰기(형태 항목의 값마다, 불투명·반투명 한 번씩).
    브라우저는 셰이더를 처음 쓰는 렌더에서 컴파일하느라 0.2–0.8초 멈추므로(webgl README 10.4) 후보를 보이기 전에 치른다.
    화면에 보이지 않고 기록하지 않는다."""
    it = table["adjustItems"]["items"]["form"]
    vo = it.get("valueOverrides") or {}
    out = []
    for v in it["values"]:
        base = dict(vo[v]) if v in vo else {it["key"]: v}
        out.append(base)
        out.append({**base, "material.opacity": 0.5})
    return out


# ── 흐름 ────────────────────────────────────────────────────────────────────
class SelectionFlow:
    """세션 하나의 4–6단계 상태. Session.selection_flow에 붙는다."""

    def __init__(self, session, rt):
        self.s, self.rt = session, rt
        self.table: dict = rt.candidate_table
        self.protocol: SelectionProtocol = rt.selection_protocol
        self.defaults = self.table["defaults"]
        self.spec: dict = copy.deepcopy(session.scene_spec)
        self.dir = selection_dir(rt.cfg.log_dir, session.id)
        self.persist = rt.persist_logs
        self.lock = threading.RLock()
        self.cands: dict | None = None
        self.data: dict | None = None
        self.current: dict = {}          # 지금 미리보기에 얹는 덮어쓰기(평평한 객체)
        self.premeasure: dict | None = None
        self._preview_alerted = False
        # 이 세션이 지금 쓰는 미리보기 방식(서버 기본에서 시작해 브라우저·플레이어 실패 때 webgl → image → none으로 내려감)
        self.preview_mode: str = rt.preview.mode
        self.preview_reason: str | None = rt.preview.reason
        self._spec_blockers: list[str] = []
        self.extras: dict = self._said_value_extras()
        self.ring: dict | None = self._ring_setup()      # G79: 값 표 4.0.0(색 kind hue_ring)일 때만, 아니면 None
        # G62: 생성 형태 후보 자산 조회([gen3d] enabled일 때만, 아니면 None — 이때 출력은 G62 전과 같다)
        self.form_assets = getattr(rt, "form_assets", None)
        self._asset_paths: dict[str, Path] = {}          # 생성 후보 id → GLB 경로(기록에 쓰지 않음)
        self._sidecar_paths: dict[str, Path] = {}
        # G73: [맞는 게 없어요] 뒤 생성([gen3d] on_none). 처음 none을 누를 때 한 번만. 그때부터 기록이 0.3(form·generation)이 된다
        self.none_gen = getattr(rt, "none_gen", None)
        self._g73 = False                # 0.3 기록을 켰는가(none을 눌러 생성 경로에 들어감)
        self._none_attempts = 0          # 이 세션에서 시작한 생성 수(n = 0 첫 생성, 1… 다시 만들기). G75면 이미지 회차 수
        self._none_job = None
        self._pick_paths: dict[int, tuple[Path, str]] = {}   # (G75) 고르기 화면 자리 → (이미지 경로, sha256). 기록에 쓰지 않음
        # G77: 확정 직후 LLM 빈칸 채우기([mapping] llm_fill). 꺼져 있으면 llm_on False — 출력은 그대로
        self.llm_on = getattr(rt, "llm_fill_prompt", None) is not None
        self.llm_rec = copy.deepcopy(getattr(session, "llm_fill", None)) if self.llm_on else None
        self.llm_applied: dict = {}      # 조절 항목 → {slot, value, quote, charSpan, overrides, specSlots}(후보에 넣은 처음 값)
        self._llm_shape_items: list = llm_fill_mod.shape_items_from(self.llm_rec) if self.llm_on else []
        # G82: [맞는 게 없어요] 뒤 규칙에 중심 형태 명사가 없을 때 LLM 형태 이름([gen3d] on_none_llm_shape). 꺼져 있으면 shape_llm_on False
        self.shape_llm_on = getattr(rt, "llm_shape_prompt", None) is not None
        self.shape_llm: dict | None = None        # 이 세션의 G82 기록(한 번만 부름, 다음 회차는 같은 결과를 씀)

    def _llm_flag(self) -> str | None:
        """(G77, CP15-2) 세션에 위기·확인 판정이 있으면 그 사유. 판정 뒤에는 LLM 값을 새 후보·그림 프롬프트에 넣지 않는다."""
        return llm_fill_mod.session_flag(self.s) if self.llm_on else None

    @property
    def llm_shape_items(self) -> list:
        """(G77) 그림 프롬프트용 LLM 형태 낱말. 판정이 선 세션이면 빈 목록(규칙 결과 그대로)."""
        return [] if self._llm_flag() else self._llm_shape_items

    def _shape_items(self) -> list:
        """(G82) 그림 프롬프트에 넣을 LLM 형태 이름. 채택 없음·판정이 선 세션·[그 말이 아니에요]를 누른 뒤면 빈 목록."""
        r = self.shape_llm
        if not r or r.get("rejected") or llm_fill_mod.session_flag(self.s):
            return []
        return llm_shape_mod.shape_items_from(r.get("call"))

    @property
    def gen3d(self) -> bool:
        return self.form_assets is not None or self._g73

    @property
    def sources_list(self) -> tuple:
        if self.llm_on or self.shape_llm_on:
            return SOURCES_LLM_FILL
        return SOURCES_GEN3D if self.gen3d else SOURCES

    def _fv(self, version: str) -> str:
        """(G77) llm_fill을 켰으면 처음부터 끝까지 0.5, 아니면 주어진 판 그대로."""
        return FORMAT_VERSION_LLM_FILL if (self.llm_on or self.shape_llm_on) else version

    def _llm_prefill(self) -> tuple[dict | None, dict]:
        """(G77) 채택 값 → candidates.generate prefill. 이 표에 없거나 지금 미리보기에서 보이지 않는 항목(G22)은 넣지 않는다
        (참여자가 보지 못한 값이 장면에 들어가지 않게). → (prefill | None, 넣지 않은 항목과 사유)."""
        if not self.llm_on:
            return None, {}
        P = self.rt.llm_fill_prompt
        off = self.unavailable_items()
        flag = self._llm_flag()
        pre, dropped = {}, {}
        for item, a in llm_fill_mod.prefill_from(self.llm_rec).items():
            if flag:
                dropped[item] = "session_flagged"           # 확정 뒤 판정이 섰으면 앞서 채택한 값도 넣지 않음(CP15-2)
            elif item not in self.items:
                dropped[item] = "not_in_table"
            elif item in off:
                dropped[item] = f"unavailable:{off[item]}"
            else:
                pre[item] = {"slots": list(P.slots[a["slot"]]["specSlots"]), "overrides": dict(a["overrides"])}
                self.llm_applied[item] = {**a, "specSlots": list(P.slots[a["slot"]]["specSlots"])}
        return pre, dropped

    def _llm_current(self, item: str) -> bool:
        """(G77) 그 항목이 지금 LLM 처음 값 그대로인가(조절 화면 안내를 보일지)."""
        a = self.llm_applied.get(item)
        if a is None:
            return False
        eff = effective_params(self.spec, self.defaults, self.current)
        return all(_same_value(eff.get(k), v) if not isinstance(v, float) else abs(float(eff.get(k)) - v) < 1e-9
                   for k, v in a["overrides"].items())

    # ── 도우미 ──────────────────────────────────────────────────────────────
    @property
    def stage(self) -> str | None:
        return None if self.data is None else self.data["stage"]

    @property
    def items(self) -> tuple:
        """이 표의 조절 항목(ITEMS_ALL 순서 가운데 표에 있는 것). 값 표 2.0.0이면 ITEMS 일곱 개 그대로."""
        have = self.table["adjustItems"]["items"]
        return tuple(i for i in ITEMS_ALL if i in have)

    @property
    def has_proportions(self) -> bool:
        return any(i in self.table["adjustItems"]["items"] for i in PROPORTION_ITEMS)

    def _cand(self, cid: str) -> dict | None:
        return next((c for c in self.cands["candidates"] if c["id"] == cid), None) if self.cands else None

    def _base(self) -> dict:
        return effective_params(self.spec, self.defaults)

    def _item_value(self, item: str, params: dict):
        it = self.table["adjustItems"]["items"][item]
        if "valueOverrides" in it:
            # D6 형태 항목: 기본 형상이 그려지면(form.base 있음 + form.type blob) 그 기본 형상, 아니면 form.type
            base = params.get("form.base", "none")
            return base if base != "none" and params["form.type"] == "blob" else params["form.type"]
        if it["kind"] in ("swatch", "hue_ring"):
            hsl = {"h": round(params["material.color.h"], 4), "s": round(params["material.color.s"], 4),
                   "l": round(params["material.color.l"], 4)}
            sw = next((s["id"] for s in it["swatches"]
                       if all(abs(s[k] - hsl[k]) < 1e-6 for k in ("h", "s", "l"))), None)
            if it["kind"] == "swatch":
                return {"swatch": sw, **hsl}
            hk, sk = self._ring_pos(hsl)
            return {"swatch": sw, **hsl, "hueStep": hk, "saturationStep": sk}   # G79-e: 고리 칸·채도 단계(무채색이면 null)
        v = params[it["key"]]
        return round(v, 4) if isinstance(v, float) else v

    def _said_value_extras(self) -> dict:
        """범주형 조절 항목(형태·움직임)에서 참여자가 말한 값이 표의 값 목록에 없으면, 그 값을 이 세션의 목록에 더한다.
        더하지 않으면 자기 형상의 현재 값이 패널에 표시되지 않고, 다른 값을 골랐다가 말한 값으로 돌아올 수도 없다.
        더하는 것은 말한 값 하나뿐이다(새 선택지를 지어내지 않음, 원칙 3). {항목: {slot, value, reason}}"""
        out = {}
        for name, it in self.table["adjustItems"]["items"].items():
            if it["kind"] != "category":
                continue
            slot = it["slots"][0]
            said = slot_value(self.spec, slot)
            if isinstance(said, str) and said not in it["values"]:
                out[name] = {"slot": slot, "value": said, "reason": SAID_NOT_IN_TABLE}
        return out

    def item_values(self, item: str) -> list:
        """이 세션의 조절 값 목록(표의 값 + 표에 없던 말한 값)."""
        it = self.table["adjustItems"]["items"][item]
        vals = [s["id"] for s in it["swatches"]] if it["kind"] in ("swatch", "hue_ring") else list(it["values"])
        if item in self.extras:
            vals.append(self.extras[item]["value"])
        return vals

    # ── G79 색상 고리 ───────────────────────────────────────────────────────
    def _ring_setup(self) -> dict | None:
        """값 표의 색 항목이 hue_ring이면 이 세션의 고리 설정. 말한 색(spec의 material.color 또는 material.saturation)이 있으면
        그 값(렌더 규칙 effective_params 그대로)을 처음 자리로 둔다. 유채색(s ≥ achromaticBelow)이면 고리의 명도는 말한 l,
        아니면 ringLightness(G79-c). 말한 h·s가 칸·단계 사이면 그 값을 이 세션의 허용 자리("said")로 더한다."""
        it = self.table["adjustItems"]["items"].get("color")
        if not it or it.get("kind") != "hue_ring":
            return None
        n, sats, thr = int(it["hueSteps"]), [float(x) for x in it["saturationSteps"]], float(it["achromaticBelow"])
        said_raw = None
        if slot_value(self.spec, "material.color") is not None or slot_value(self.spec, "material.saturation") is not None:
            b = effective_params(self.spec, self.defaults)
            said_raw = {k: float(b[f"material.color.{k}"]) for k in ("h", "s", "l")}
        said = {k: round(v, 4) for k, v in said_raw.items()} if said_raw else None
        chroma = said is not None and said["s"] >= thr
        # 매퍼 값은 소수 셋째 자리(215° → 0.597)라 칸 값(0.5972)과 끝자리만 다를 수 있다. RING_SNAP 안이면 그 칸이 이 세션에서는
        # 말한 값 자체다(칸 하나가 말한 자리 — 겹치는 자리를 두 개 만들지 않고, 그 칸을 누르면 말한 값 그대로 돌아온다)
        hue_snap = next((k for k in range(n) if chroma and abs(ring_hue(k, n) - said["h"]) <= RING_SNAP), None)
        sat_snap = next((j for j, x in enumerate(sats) if chroma and abs(x - said["s"]) <= RING_SNAP), None)
        on_hue, on_sat = hue_snap is not None, sat_snap is not None
        screen = {s["id"]: s for s in it["swatches"] if s["id"] in it["screenSwatches"]}
        said_screen = next((i for i, sw in screen.items() if said is not None and not chroma
                            and all(abs(sw[k] - said[k]) < 1e-6 for k in ("h", "s", "l"))), None)
        said_chip = said is not None and not chroma and said_screen is None
        return {"hueSteps": n, "saturationSteps": sats, "achromaticBelow": thr,
                "defaultSat": sats[int(it["saturationDefaultIndex"])],
                "lightRaw": said_raw["l"] if chroma else float(it["ringLightness"]),
                "said": said, "saidRaw": said_raw, "chromatic": chroma,
                "hueSaid": said["h"] if chroma and not on_hue else None,      # 칸 사이 말한 색상(그 자리를 더함)
                "satSaid": said["s"] if chroma and not on_sat else None,      # 단계 사이 말한 채도
                "hueSnap": hue_snap, "satSnap": sat_snap,                     # 말한 값과 같은 칸·단계(끝자리 차이 안)
                "saidChip": said_chip,                                      # 무채색 견본에 없는 말한 무채색 → 견본 하나 더
                "saidScreenSwatch": said_screen}                              # 말한 무채색이 견본 하나와 같음(그 견본에 눈금)

    def _ring_pos(self, hsl: dict) -> tuple:
        """(hueStep, saturationStep): 칸 번호 0–71 | "said"(칸 사이 말한 자리) | None(무채색이거나 고리 밖)."""
        R = self.ring
        if hsl["s"] < R["achromaticBelow"]:
            return None, None
        n = R["hueSteps"]
        hk = next((k for k in range(n) if abs(round(self._step_h(k), 4) - hsl["h"]) < 1e-6), None)
        if hk is None and R["hueSaid"] is not None and abs(R["hueSaid"] - hsl["h"]) < 1e-6:
            hk = RING_SAID
        sk = next((j for j in range(len(R["saturationSteps"])) if abs(round(self._step_s(j), 4) - hsl["s"]) < 1e-6), None)
        if sk is None and R["satSaid"] is not None and abs(R["satSaid"] - hsl["s"]) < 1e-6:
            sk = RING_SAID
        return hk, sk

    def _step_h(self, k: int) -> float:
        """이 세션에서 칸 k의 색상: 말한 색상이 그 칸과 같은 자리(RING_SNAP 안)면 말한 값, 아니면 round(k/72, 4)."""
        R = self.ring
        return R["saidRaw"]["h"] if R["hueSnap"] == k else ring_hue(k, R["hueSteps"])

    def _step_s(self, j: int) -> float:
        R = self.ring
        return R["saidRaw"]["s"] if R["satSnap"] == j else R["saturationSteps"][j]

    def _validate_ring(self, it: dict, value) -> dict:
        """G79 색 입력 → 덮어쓰기 h·s·l. 받는 것: 견본 id(17개, G77 제안·옛 화면), "said"(말한 색 그대로 — 말한 색이 있을 때만),
        {"hueStep": k, "saturationStep": j}(둘 중 하나만 줘도 됨). k = 0–71 정수 | "said", j = 단계 번호 정수 | "said".
        bool·실수(3.0 포함)·음수·범위 밖·문자열·다른 키는 거부. hueStep이 없으면 지금 고리 위 색상을 그대로(고리 위에 색이 없으면 거부),
        saturationStep이 없으면 지금 채도가 허용 단계면 그대로, 아니면 말한 채도(유채색일 때) 또는 기본 단계. 명도는 이 세션의 고리 명도."""
        R = self.ring
        if isinstance(value, str):
            if value == RING_SAID:
                if R["saidRaw"] is None:
                    raise SelectionInvalid("말한 색이 없는 세션입니다: 'said'")
                return {f"material.color.{k}": R["saidRaw"][k] for k in ("h", "s", "l")}
            sw = next((s for s in it["swatches"] if s["id"] == value), None)
            if sw is None:
                raise SelectionInvalid(f"색 견본 목록에 없는 값입니다: {value!r}")
            return {"material.color.h": sw["h"], "material.color.s": sw["s"], "material.color.l": sw["l"]}
        if not isinstance(value, dict) or not value or set(value) - {"hueStep", "saturationStep"}:
            raise SelectionInvalid(f"색 값은 견본 id 또는 {{\"hueStep\": 0–{R['hueSteps'] - 1}, \"saturationStep\": "
                                   f"0–{len(R['saturationSteps']) - 1}}}입니다: {value!r}")
        cur = effective_params(self.spec, self.defaults, self.current)
        pos = self._ring_pos({k: round(cur[f"material.color.{k}"], 4) for k in ("h", "s", "l")})

        def pick(v, name, top, said_raw):
            if v == RING_SAID:
                if not R["chromatic"]:
                    raise SelectionInvalid(f"{name}: 말한 유채색이 없는 세션입니다: 'said'")
                return said_raw
            if isinstance(v, bool) or not isinstance(v, int) or not 0 <= v < top:
                raise SelectionInvalid(f"{name}: 0–{top - 1} 정수여야 합니다: {v!r}")
            return None

        hv = value.get("hueStep", _MISSING)
        if hv is _MISSING:
            if pos[0] is None:
                raise SelectionInvalid("고리 위에 고른 색이 없어 채도만 바꿀 수 없습니다(hueStep 필요)")
            h = cur["material.color.h"]
        else:
            h = pick(hv, "hueStep", R["hueSteps"], R["saidRaw"]["h"] if R["chromatic"] else None)
            h = self._step_h(hv) if h is None else h
        sv = value.get("saturationStep", _MISSING)
        if sv is _MISSING:
            s = (cur["material.color.s"] if pos[1] is not None
                 else R["saidRaw"]["s"] if R["chromatic"] else R["defaultSat"])
        else:
            s = pick(sv, "saturationStep", len(R["saturationSteps"]), R["saidRaw"]["s"] if R["chromatic"] else None)
            s = self._step_s(sv) if s is None else s
        return {"material.color.h": h, "material.color.s": s, "material.color.l": R["lightRaw"]}

    def _ring_initial_origin(self) -> str:
        if self.ring["said"] is not None:
            return "said"
        return llm_fill_mod.ORIGIN if "color" in self.llm_applied else "unspecified"

    def _ring_home(self):
        """Home 키(처음 값)로 보낼 입력. 처음에 고리·견본에 고른 것이 없었으면(말하지도 채우지도 않음) None."""
        init = (self.data.get("colorRing") or {}).get("initial") if self.data else None
        if init is None or init["origin"] == "unspecified":
            return None
        if init["origin"] == "said":
            return RING_SAID
        v = init["value"]
        return v["swatch"] or ({"hueStep": v["hueStep"], "saturationStep": v["saturationStep"]}
                               if v["hueStep"] is not None else None)

    def _ring_record_new(self) -> dict:
        """selection.json 맨 위 colorRing(G79-d·e). 고리가 화면에 나갔는지(exposed), 처음·최종 색의 출처."""
        R = self.ring
        return {"version": COLOR_RING_VERSION, "tableVersion": self.table["tableVersion"],
                "hueSteps": R["hueSteps"], "saturationSteps": list(R["saturationSteps"]),
                "lightness": round(R["lightRaw"], 4), "lightnessFrom": "said" if R["chromatic"] else "ringLightness",
                "said": copy.deepcopy(R["said"]), "saidChromatic": R["chromatic"] if R["said"] is not None else None,
                "saidPosition": ({"hueStep": p[0], "saturationStep": p[1]} if (p := self._ring_pos(R["said"]))[0] is not None
                                 else None) if R["said"] is not None else None,
                "saidSwatchAdded": R["saidChip"],
                "originRule": RING_ORIGIN_RULE,
                "exposed": False, "exposedAt": None, "initial": None, "final": None}

    def _ring_enter(self, at: str) -> None:
        """조절 단계에 들어감(선택·none·건너뜀): 처음 값과 그 출처를 적고, 색 항목이 꺼져 있지 않으면 고리를 내보냈다고 적는다
        (서버가 고리를 그리는 조절 화면을 냄 — 브라우저가 실제로 그렸는지는 미리보기 알림(preview.shown.adjusting)으로 본다)."""
        rec = (self.data or {}).get("colorRing")
        if rec is None:
            return
        if rec["initial"] is None:
            params = effective_params(self.spec, self.defaults, self.current)
            rec["initial"] = {"origin": self._ring_initial_origin(), "value": self._item_value("color", params), "at": at}
        if not rec["exposed"] and "color" not in self.unavailable_items():
            rec.update(exposed=True, exposedAt=at)

    def _ring_final(self) -> dict:
        rec = self.data["colorRing"]
        init = rec["initial"]["origin"] if rec["initial"] else self._ring_initial_origin()
        summ = self.data["adjustments"]["items"].get("color")
        if not summ:
            origin = init
        elif init == "unspecified":
            origin = "picked"
        else:
            origin = init if _same_value(summ["last"], summ["first"]) else "picked"
        evs = [e for e in self.data["adjustments"]["events"] if e["item"] == "color"]
        final = effective_params(self.spec, self.defaults, self.current)
        return {"origin": origin, "value": self._item_value("color", final), "adjustCount": summ["count"] if summ else 0,
                "ringInputs": sum(1 for e in evs if isinstance(e.get("input"), dict)),
                "swatchInputs": sum(1 for e in evs if isinstance(e.get("input"), str) and e["input"] != RING_SAID),
                "saidInputs": sum(1 for e in evs if e.get("input") == RING_SAID)}

    def _ring_view(self) -> dict:
        """화면용(stage.js): 고리 명도, 채도 단추(단계 + 단계 사이 말한 채도), 말한 자리 눈금, Home 값, 말하지도 고르지도 않은 상태."""
        R = self.ring
        sats = [{"step": j, "s": x} for j, x in enumerate(R["saturationSteps"])]
        if R["satSaid"] is not None:
            sats = sorted(sats + [{"step": RING_SAID, "s": R["satSaid"]}], key=lambda x: x["s"])
        said_pos = self._ring_pos(R["said"]) if R["chromatic"] else (None, None)
        rec = (self.data or {}).get("colorRing") or {}
        untouched = "color" not in ((self.data or {}).get("adjustments") or {}).get("items", {})
        init = rec.get("initial")
        cur = effective_params(self.spec, self.defaults, self.current)
        at_said = R["said"] is not None and all(abs(round(cur[f"material.color.{k}"], 4) - R["said"][k]) < 1e-6 for k in "hsl")
        out = {"hueSteps": R["hueSteps"], "lightness": round(R["lightRaw"], 4), "atSaid": at_said,
               "saturations": sats, "ringSaturation": R["satSaid"] if R["satSaid"] is not None else (
                   R["said"]["s"] if R["chromatic"] else R["defaultSat"]),
               "saidHue": R["said"]["h"] if R["chromatic"] else None, "saidHueStep": said_pos[0],
               "saidSaturationStep": said_pos[1],
               "saidSwatch": ({"id": RING_SAID, "hex": swatch_hex(R["said"])} if R["saidChip"] else None),
               "saidSwatchId": RING_SAID if R["saidChip"] else R["saidScreenSwatch"],
               "home": self._ring_home(),
               "unspecified": bool(untouched and (init["origin"] if init else self._ring_initial_origin()) == "unspecified")}
        return out

    def _spec_file_hash(self) -> tuple[str | None, str, list[str]]:
        """러너 계약의 specSha256(G26): 저장된 spec 파일 바이트의 sha256만 적는다. (sha | None, sha256Basis, 막는 이유)
        파일이 없거나 파일 내용이 세션의 spec과 다르면 해시를 적지 않고(None) 이유를 남긴다 — 직렬화한 글의 해시로
        대신하면 러너가 읽는 파일 바이트와 기준이 달라진다(CP9 지적 1)."""
        path = (self.s.log.data.get("sceneSpec") or {}).get("path")
        if not path or not Path(path).is_file():
            return None, "none", [BLOCK_NO_SPEC_FILE]
        raw = Path(path).read_bytes()
        try:
            same = json.loads(raw.decode("utf-8")) == json.loads(json.dumps(self.spec, ensure_ascii=False))
        except ValueError:
            same = False
        if not same:
            return None, "none", [BLOCK_SPEC_FILE_CHANGED]
        return hashlib.sha256(raw).hexdigest(), "file", []

    def _runner_status(self) -> None:
        """runnerReady·runnerBlockers를 지금 상태로 맞춘다(저장할 때마다)."""
        blockers = list(self._spec_blockers)
        if self.data["finalOverrides"] is None or self.data["sources"] is None:
            blockers.append(BLOCK_NOT_FINISHED)
        self.data["runnerReady"] = not blockers
        self.data["runnerBlockers"] = blockers

    def _save(self) -> None:
        if self.data is None:
            return
        self._runner_status()
        if not self.persist:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        self.data["updatedAt"] = now_iso()
        tmp = self.dir / "selection.json.tmp"
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        os.replace(tmp, self.dir / "selection.json")

    def _log_event(self, kind: str, payload: dict) -> None:
        self.s.log.add_event(kind, payload)
        self.s._save()

    def _require(self, stage: str) -> None:
        if self.stage != stage:
            raise SelectionError(f"지금은 이 요청을 받을 단계가 아닙니다(지금: {self.stage or '후보 전'}, 필요: {stage}).")

    # ── 4 후보 ──────────────────────────────────────────────────────────────
    def start(self) -> dict:
        """후보를 만들고 기록한다. 이미 만들었으면 같은 후보를 다시 돌려준다(다시 기록하지 않음)."""
        with self.lock:
            if self.cands is not None:
                return self.view()
            pinfo = self.protocol.info()
            if self.rt.cfg.selection.require_spec_phrases and pinfo["draftCount"]:
                raise SelectionError(f"[selection] require_spec_phrases = true인데 초안 문구가 {pinfo['draftCount']}개 있어 "
                                     "후보 단계를 시작하지 않습니다.")
            prefill, pre_dropped = self._llm_prefill()
            self.cands = generate(self.spec, self.s.id, self.table) if prefill is None else                 generate(self.spec, self.s.id, self.table, prefill=prefill, prefill_source=llm_fill_mod.ORIGIN)
            for item in (self.cands.get("prefill") or {}).get("droppedForSplit") or []:
                self.llm_applied.pop(item, None)          # 낱말 해석 갈림이 같은 슬롯을 다룸(갈림이 먼저)
                pre_dropped[item] = "interpretation_split"
            if self.gen3d:
                # G62: 절차 후보는 그대로 두고 생성 후보(status ok + 관문 통과, 최대 max_candidates)를 뒤에 더한다
                lookup = self.form_assets.lookup_for_spec(self.spec)
                if self.preview_mode == "none" and lookup["offered"]:
                    # 미리보기가 글 요약뿐이면 생성 형태를 보일 수 없다 → 참여자가 보지 않은 형태를 고르게 하지 않도록 내지 않는다
                    lookup = {**lookup, "offered": [], "rejected": [
                        _rej(a["assetId"], "ok", R_NO_SHAPE_PREVIEW, a["_sidecarPath"], "preview mode none")
                        for a in lookup["offered"]] + lookup["rejected"]}
                # G62-i: auto면 말한 형태 낱말(사이드카 tokens)이 단순 도형인지 사전·규칙으로 판정해 기본 출처를 정한다
                basis = self.form_assets.judge_default(lookup, self.spec, self._confirmed_norm())
                self.cands = add_generated(self.cands, lookup, self.s.id, self.form_assets.max_candidates,
                                           self.form_assets.default_form_source, basis)
                gen_ids = [g["candidateId"] for g in self.cands["generation"]["offered"]]
                self._asset_paths = {cid: a["_glbPath"] for cid, a in zip(gen_ids, lookup["offered"])}
                self._sidecar_paths = {cid: a["_sidecarPath"] for cid, a in zip(gen_ids, lookup["offered"])}
            scene = self.s.log.data.get("sceneSpec") or {}
            path = scene.get("path")
            # 러너 계약: 맨 위 specSha256 = 저장된 spec 파일 바이트의 sha256(러너가 읽는 파일과 다르면 시작 거부).
            # spec 파일이 없는 실행에서는 null로 두고 runnerReady = false와 이유를 적는다(G26).
            file_sha, basis, self._spec_blockers = self._spec_file_hash()
            now = now_iso()
            meta = self.spec.get("meta") or {}
            self.data = {
                "formatVersion": self._fv(FORMAT_VERSION), "specSha256": file_sha,
                "sessionId": self.s.id, "createdAt": now, "updatedAt": now,
                "stage": "selecting",
                "spec": {"path": path, "normalizedSha256": spec_sha256(self.spec), "sha256Basis": basis,
                         "builder": (meta.get("pipeline") or {}).get("builder", ""),
                         "specVersion": meta.get("specVersion", ""), "mapping": meta.get("mapping")},
                "generator": {"generatorVersion": self.cands["generatorVersion"], "tableVersion": self.cands["tableVersion"],
                              "tableSha256": self.cands["tableSha256"]},
                "protocol": {k: pinfo[k] for k in ("protocolId", "protocolVersion", "draftCount", "draftKeys")},
                "preview": self._preview_record(),
                "adjustUnavailable": self._unavailable_record(now),
                "candidates": self.cands, "candidatesShown": list(self.cands["displayOrder"]), "candidatesShownAt": now,
                "selection": None,
                "adjustments": {"events": [], "items": {}, "finishedAt": None},
                "colorChanged": False,
                "finalOverrides": None, "sources": None, "sourceDetails": None, "sourceCounts": None, "premeasure": None,
                "adjustValueExtras": copy.deepcopy(self.extras),
                "distanceFloor": floor_record(self.spec),
                "safetyFlags": safety_flags(self.spec),                # G50 (4): 넷째 범주 표시(실험자용, 진행은 막지 않음)
                "runnerReady": False, "runnerBlockers": [],
            }
            if self.has_proportions:
                # G72: 축별 처음 값·최종 값·고쳤는지(값 표 3.0.0일 때만 키를 넣는다 — 2.0.0 표의 기록은 그대로)
                self.data["proportions"] = self._proportions_record(final=False)
            if self.ring is not None:
                # G79: 색상 고리 기록(값 표 4.0.0일 때만 키를 넣는다 — 3.0.0 이하 표의 기록은 그대로)
                self.data["colorRing"] = self._ring_record_new()
            if self.gen3d:
                # G62(0.3): 고른 생성 메시(form.asset)와 생성 후보 기록. 꺼져 있으면 키 자체를 넣지 않는다(0.2 그대로)
                self.data["formatVersion"] = self._fv(FORMAT_VERSION_GEN3D)
                self.data["defaultFormSource"] = self.cands["generation"]["defaultFormSource"]   # 이 세션에서 기본이었던 것
                self.data["form"] = {"asset": None}
                self.data["generation"] = {**copy.deepcopy(self.cands["generation"]),
                                           "shownOrder": [cid for cid in self.cands["displayOrder"] if cid in self._asset_paths],
                                           "outcome": None, "acceptedDefault": None, "declined": [], "assetDropped": None}
            if self.llm_on:
                # G77: LLM 빈칸 채우기 기록(확정 직후 세션이 만든 것)과 이 세션 후보에 넣은 처음 값. 참여자 결과는 finish에서 채운다
                self.data["llmFill"] = {**(copy.deepcopy(self.llm_rec) if self.llm_rec else
                                           {"version": llm_fill_mod.LLM_FILL_VERSION, "status": "absent", "adopted": []}),
                                        "applied": {k: {kk: copy.deepcopy(v[kk]) for kk in ("slot", "value", "quote", "charSpan",
                                                                                            "overrides", "specSlots")}
                                                    for k, v in sorted(self.llm_applied.items())},
                                        "notApplied": dict(sorted(pre_dropped.items())), "participant": None}
                self.data["llmFillExposed"] = bool(self.llm_applied)
            skip = self.cands["selectionStep"] == "skip"
            if skip:
                self._enter_skip(now)
            if self.persist:
                self.dir.mkdir(parents=True, exist_ok=True)
                (self.dir / "candidates.json").write_bytes(candidates_bytes(self.cands))
            self._save()
            payload = {
                "selectionPath": str(self.dir / "selection.json") if self.persist else None,
                "specSha256": self.data["specSha256"], "generatorVersion": self.cands["generatorVersion"],
                "tableVersion": self.cands["tableVersion"], "candidateCount": len(self.cands["candidates"]),
                "axes": [{"slot": a["slot"], "reason": a["reason"]} for a in self.cands["axes"]],
                "displayOrder": self.cands["displayOrder"], "draftCount": pinfo["draftCount"],
                "draftKeys": pinfo["draftKeys"], "previewMode": self.preview_mode,
                "sha256Basis": basis, "adjustValueExtras": sorted(self.extras),
                "selectionStep": self.cands["selectionStep"], "distinctRemoved": len(self.cands["distinct"]["removed"]),
                "distanceFloor": self.data["distanceFloor"], "safetyFlags": len(self.data["safetyFlags"])}
            if self.gen3d:
                gen = self.cands["generation"]
                payload["generation"] = {"offered": [g["assetId"] for g in gen["offered"]],
                                         "rejected": [{"assetId": r["assetId"], "reason": r["reason"]} for r in gen["rejected"]]}
            self._log_event("selection:candidates", payload)
            if skip:
                self._log_event("selection:skipped", {"reason": SKIP_REASON,
                                                      "operationalId": self.data["selection"]["operationalId"]})
            return self.view()

    def select(self, choice: str) -> dict:
        """후보 id 하나 또는 "none"(맞는 것이 없다, G23: 기준 후보 0번으로 진행)."""
        with self.lock:
            self._require("selecting")
            if choice == NONE_CHOICE and self._may_generate_after_none():
                # G73: 처음 [맞는 게 없어요] → 확정 텍스트로 형태를 하나 만들어 새 후보로(못 만들면 사유를 남기고 아래 none 경로).
                # 만든 후보도 맞지 않다고 하면 같은 프롬프트·seed + n으로 on_none_max_regenerations번까지 더
                return self._start_none_generation()
            if choice != NONE_CHOICE and self._cand(choice) is None:
                raise SelectionInvalid(f"보여 준 후보가 아닙니다: {choice}")
            self._apply_choice(choice)
            return self.view()

    def _apply_choice(self, choice: str, at: str | None = None) -> None:
        """선택을 적고 조절 단계로 들어간다. none(G23)이면 0번 후보로 진행. lock 안에서 부른다."""
        order = self.cands["displayOrder"]
        if choice == NONE_CHOICE:
            op = self.cands["candidates"][0]
            sel = {"selectedCandidateId": None, "selectedIndex": None, "none": True, "skipped": False,
                   "displayPosition": None}
        else:
            c = self._cand(choice)
            op = c
            sel = {"selectedCandidateId": c["id"], "selectedIndex": c["index"], "none": False, "skipped": False,
                   "displayPosition": order.index(c["id"])}
        sel.update(operationalId=op["id"], operationalIndex=op["index"], at=at or now_iso())
        an = self._after_none()
        if an is not None:
            # G73: 이 선택 전에 [맞는 게 없어요]를 눌러 생성 경로를 거쳤음(생성 결과 status). 처음 none 시각은 generation.afterNone.noneAt
            sel["afterNoneGeneration"] = an["status"]
        self.data["selection"] = sel
        self.data["stage"] = "adjusting"
        self.current = dict(op["overrides"])
        self._ring_enter(sel["at"])
        if self.gen3d:
            self._record_generation_choice(op if choice != NONE_CHOICE else None)
        self._save()
        self._log_event("selection:selected", {k: sel[k] for k in ("selectedCandidateId", "none", "displayPosition",
                                                                  "operationalId", "operationalIndex")})

    # ── G73 [맞는 게 없어요] 뒤 생성 ───────────────────────────────────────────
    def _after_none(self) -> dict | None:
        return ((self.data or {}).get("generation") or {}).get("afterNone") if self._g73 else None

    def _activate_g73(self) -> None:
        """기록을 0.3으로 올린다(form.asset·generation). G62(enabled)가 이미 켰으면 그대로 쓴다. lock 안에서 부른다."""
        if self._g73:
            return
        self._g73 = True
        if self.form_assets is not None:
            return
        empty = {"key": source_key(self.spec), "offered": [], "rejected": []}
        self.cands = add_generated(self.cands, empty, self.s.id, 0, DEFAULT_PROCEDURAL, None)
        self.data["candidates"] = self.cands
        self.data["formatVersion"] = self._fv(FORMAT_VERSION_GEN3D)
        self.data["defaultFormSource"] = self.cands["generation"]["defaultFormSource"]
        self.data["form"] = {"asset": None}
        self.data["generation"] = {**copy.deepcopy(self.cands["generation"]), "shownOrder": [],
                                   "outcome": None, "acceptedDefault": None, "declined": [], "assetDropped": None}

    def _other_interviews(self) -> list[str]:
        """면담 LLM을 부를 수 있는 다른 세션(이 세션은 확정을 마쳐 면담 LLM을 더 부르지 않는다 — Session.selection 조건)."""
        return sorted(x.id for x in list(self.rt.sessions.values()) if x is not self.s and x.state in ng.INTERVIEW_STATES)

    def _may_generate_after_none(self) -> bool:
        if self.none_gen is None:
            return False
        if self._none_attempts == 0:
            return True
        an = self._after_none()
        # (G75) 이미지 고르기를 켰으면 다시 만들기 대신 다음 이미지 회차(on_none_image_rounds까지)
        limit = (self.none_gen.image_rounds - 1) if self.none_gen.image_pick else self.none_gen.max_regenerations
        # 다시 만들기는 바로 앞 생성이 후보를 냈고(ok) 그 후보가 아직 화면에 있을 때만(막힘·실패면 이미 조절로 넘어감)
        return (self._none_attempts <= limit and an is not None and an["status"] == ng.OK
                and self._cand(an.get("candidateId") or "") is not None)

    def _start_none_generation(self) -> dict:
        if self.none_gen.image_pick:
            return self._start_image_round()
        n = self._none_attempts
        self._none_attempts += 1
        self._activate_g73()
        prev = self._after_none()
        if prev is not None:
            # 다시 만들기: 앞 기록은 afterNoneEarlier로 옮기고(참여자가 그 후보에도 none이라 함) afterNone은 새 시도
            prev["chosen"] = False
            self.data["generation"].setdefault("afterNoneEarlier", []).append(prev)
        at = now_iso()
        text = self.s.log.data.get("confirmedText")
        pre = self.none_gen.precheck(self.spec, text, self.preview_mode, self._other_interviews(),
                                     llm_items=self.llm_shape_items or None)
        rec = {"version": ng.NONE_GEN_VERSION, "origin": ng.ORIGIN, "setting": self.none_gen.setting(), "noneAt": at,
               "shownOrderBefore": list(self.cands["displayOrder"]), "status": ng.RUNNING,
               "blockReason": pre["blockReason"], "blockDetail": pre["blockDetail"], "prompt": pre["prompt"],
               "run": None, "startedAt": None, "endedAt": None, "seconds": None, "exitCode": None, "error": None,
               "llmUnload": None, "timing": None, "asset": None, "candidateId": None, "displayPosition": None,
               "participantSkippedWait": False, "chosen": None,
               "attempt": n, "seed": self.none_gen.seed_for(n)}      # 다시 만들기 n번째(0 = 첫 생성), seed = 기준 seed + n
        self._note_llm_prompt(rec)
        self.data["generation"]["afterNone"] = rec
        job = None
        if pre["blockReason"] is None:
            # 생성기도 세션 매퍼 spec으로 같은 규칙 프롬프트(G73 후속). 면담 중 세션 확인과 예약은 서비스 잠금 안에서(CP13-2)
            job = self.none_gen.start(self.s.id, text, source_key(self.spec), pre["prompt"]["text"], self._generation_done,
                                      attempt=n, spec=self.spec, other_interviews=self._other_interviews,
                                      llm_items=self.llm_shape_items or None)
            if isinstance(job, str):
                rec.update(blockReason=job, blockDetail=",".join(self._other_interviews()) or None
                           if job == ng.B_INTERVIEW else None)
                job = None
        if job is None:
            # 만들지 않음: 사유를 남기고 기존 none 경로(0번 후보로 조절, 화면에는 짧은 안내)
            rec.update(status=ng.BLOCKED, endedAt=at, seconds=0.0)
            self._log_event("selection:none_gen", {"status": ng.BLOCKED, "blockReason": rec["blockReason"]})
            self._apply_choice(NONE_CHOICE, at)
            return self.view()
        self._none_job = job
        rec["startedAt"] = at
        self.data["stage"] = "generating"
        self._save()
        self._log_event("selection:none_gen", {"status": ng.RUNNING, "promptText": pre["prompt"]["text"]})
        return self.view()

    def _generation_done(self, res: dict) -> None:
        """생성 스레드에서 한 번. 기다리는 중이면 성공 → 새 후보를 맨 앞에 더해 다시 고르기, 그 밖 → 기존 none 경로."""
        with self.lock:
            rec = self._after_none()
            if rec is None or self.data is None:
                return
            for k in ("run", "endedAt", "seconds", "exitCode", "llmUnload", "timing", "cacheProbe"):
                rec[k] = res.get(k)
            if rec["startedAt"] is None:
                rec["startedAt"] = res.get("startedAt")
            status = res.get("status") or ng.FAILED
            if self.stage != "generating":
                # 이미 넘어감(참여자가 기다리지 않음·철회): 기록만 채운다
                rec["generatorStatus"] = status
                self._save()
                return
            a = res.get("asset")
            if status == ng.OK and self.preview_mode == "none":
                status, res = ng.BLOCKED, {**res, "blockReason": ng.B_PREVIEW_NONE, "blockDetail": "preview mode none"}
            if status == ng.OK and any((c.get("asset") or {}).get("glbSha256") == a["glbSha256"] for c in self.cands["candidates"]):
                status, res = ng.BLOCKED, {**res, "blockReason": ng.B_DUPLICATE, "blockDetail": a["assetId"]}
            rec["status"] = status
            if status != ng.OK:
                rec.update(blockReason=res.get("blockReason"), blockDetail=res.get("blockDetail"), error=res.get("error"))
                self._log_event("selection:none_gen", {"status": status, "blockReason": rec["blockReason"],
                                                       "seconds": rec["seconds"]})
                self._apply_choice(NONE_CHOICE)
                return
            cid = self._add_after_none_candidate(a)
            rec.update(asset={**public_asset(a), "origin": ng.ORIGIN}, candidateId=cid, displayPosition=0)
            if rec.get("llmPromptUsed"):
                self.data["llmFillExposed"] = True        # G77: LLM 형태 낱말로 만든 후보가 화면에 나옴
            self.data["stage"] = "selecting"
            self._save()
            self._log_event("selection:none_gen", {"status": ng.OK, "assetId": a["assetId"], "candidateId": cid,
                                                   "seconds": rec["seconds"]})

    def _add_after_none_candidate(self, a: dict) -> str:
        """생성 자산 하나를 후보로 더한다: 다른 값(색·크기 등)은 0번 후보(덮어쓰기 없음)와 같고, 화면 맨 앞(나머지 순서는 그대로)."""
        base = self.cands["candidates"][0]
        sources = dict(base["sources"])
        sources["form.type"] = ng.ORIGIN
        cid = generated_candidate_id(self.cands["specSha256"], a)
        index = max(c["index"] for c in self.cands["candidates"]) + 1
        self.cands["candidates"].append({"id": cid, "index": index, "overrides": dict(base["overrides"]), "axisValues": {},
                                         "sources": sources, "origin": ng.ORIGIN, "asset": public_asset(a)})
        self.cands["displayOrder"] = [cid] + [x for x in self.cands["displayOrder"] if x != cid]
        self.data["candidatesShown"] = list(self.cands["displayOrder"])
        self.data["candidatesShownAt"] = now_iso()
        for g in (self.cands["generation"], self.data["generation"]):
            g["offered"] = g["offered"] + [{"candidateId": cid, "assetId": a["assetId"], "origin": ng.ORIGIN}]
        self.data["generation"]["shownOrder"] = [x for x in self.cands["displayOrder"]
                                                 if x in self._asset_paths or x == cid]
        self._asset_paths[cid] = a["_glbPath"]
        self._sidecar_paths[cid] = a["_sidecarPath"]
        return cid

    # ── G75 참고 이미지 고르기([gen3d] on_none_image_pick) ─────────────────────────
    def _image_pick(self) -> dict | None:
        an = self._after_none()
        return an.get("imagePick") if an is not None else None

    def _start_image_round(self, at: str | None = None) -> dict:
        """회차 r: 규칙 프롬프트(+ 무채색 화풍 고정 문구) → 이미지 3장(seed = 기준 + 3r + 0·1·2) → 이미지 관문 → 고르기 화면.
        만들지 못하면(형태를 말하지 않음·제외 범주 등, G73과 같은 판정) 사유를 남기고 기존 none 경로. lock 안에서 부른다.
        (G82) 처음 회차에 규칙 프롬프트에 중심 형태 명사가 없으면 먼저 LLM 형태 이름을 부른다(백그라운드 스레드, 대기 화면은 그림 대기와
        같음). 채택된 이름으로 규칙 프롬프트의 빈 중심 명사 자리를 메운 뒤 그림 단계로 간다. 다음 회차는 같은 결과를 쓴다(다시 부르지 않음)."""
        r = self._none_attempts
        self._none_attempts += 1
        self._activate_g73()
        self.data["formatVersion"] = self._fv(FORMAT_VERSION_IMAGE_PICK)
        self.data["generation"].setdefault("imagePickExposed", False)
        prev = self._after_none()
        if prev is not None:
            # 다음 회차: 앞 기록은 afterNoneEarlier로(만든 후보가 있었으면 그 후보에도 none이라 함 → chosen false)
            if prev.get("candidateId") is not None:
                prev["chosen"] = False
            self.data["generation"].setdefault("afterNoneEarlier", []).append(prev)
        at = at or now_iso()
        text = self.s.log.data.get("confirmedText")
        need_llm = self.shape_llm_on and self.shape_llm is None and self._shape_llm_route()
        pre = self.none_gen.precheck(self.spec, text, self.preview_mode, self._other_interviews(),
                                     llm_items=self.llm_shape_items or None, llm_shape_items=self._shape_items() or None)
        rec = self._image_rec(r, at, pre)
        self.data["generation"]["afterNone"] = rec
        if need_llm:
            # (G82) LLM 형태 이름을 먼저(잠금 밖 스레드). 끝나면 _shape_llm_done이 같은 회차를 이어 간다
            rec["shapeLlmPending"] = True
            rec["imagePick"]["startedAt"] = at
            self.data["stage"] = "generating"
            self._save()
            self._log_event("selection:shape_llm", {"status": "running", "round": r})
            threading.Thread(target=self._shape_llm_work, args=(rec, r, at), name=f"shape-llm-{self.s.id}",
                             daemon=True).start()
            return self.view()
        return self._launch_image_round(rec, r, at, text, pre)

    def _image_rec(self, r: int, at: str, pre: dict) -> dict:
        p = pre["prompt"] or {}
        rec = {"version": ng.NONE_GEN_VERSION, "origin": ng.ORIGIN, "setting": self.none_gen.setting(), "noneAt": at,
               "shownOrderBefore": list(self.cands["displayOrder"]), "status": ng.RUNNING,
               "blockReason": pre["blockReason"], "blockDetail": pre["blockDetail"], "prompt": pre["prompt"],
               "run": None, "startedAt": None, "endedAt": None, "seconds": None, "exitCode": None, "error": None,
               "llmUnload": None, "timing": None, "asset": None, "candidateId": None, "displayPosition": None,
               "participantSkippedWait": False, "chosen": None,
               "attempt": r, "seed": None,                         # 형태 seed = 고른 이미지의 seed(고르기 전 null)
               "imagePick": {"version": ng.IMAGE_PICK_VERSION, "round": r, "seeds": self.none_gen.seeds_for_round(r),
                             "promptText": p.get("text"), "builderVersion": p.get("builderVersion"),
                             "imageStyle": p.get("imageStyle"), "imageStyleVersion": p.get("imageStyleVersion"),
                             "status": ng.RUNNING, "run": None, "startedAt": None, "endedAt": None, "seconds": None,
                             "exitCode": None, "error": None, "blockReason": None, "llmUnload": None, "timing": None,
                             "models": None, "images": [], "shownOrder": [], "shownAt": None, "outcome": None,
                             "pickedPosition": None, "pickedSeed": None, "pickedImageSha256": None, "decidedAt": None}}
        self._note_llm_prompt(rec)
        return rec

    def _launch_image_round(self, rec: dict, r: int, at: str, text, pre: dict) -> dict:
        """그림 단계 작업을 시작한다(못 하면 사유를 남기고 기존 none 경로). lock 안에서 부른다."""
        ip = rec["imagePick"]
        p = pre["prompt"] or {}
        self._pick_paths = {}
        job = None
        if pre["blockReason"] is None:
            job = self.none_gen.start(self.s.id, text, source_key(self.spec), p["text"],
                                      lambda res, rec=rec: self._image_round_done(res, rec), attempt=r, spec=self.spec,
                                      other_interviews=self._other_interviews, kind="image", seeds=ip["seeds"],
                                      llm_items=self.llm_shape_items or None, llm_shape_items=self._shape_items() or None)
            if isinstance(job, str):
                rec.update(blockReason=job, blockDetail=",".join(self._other_interviews()) or None
                           if job == ng.B_INTERVIEW else None)
                job = None
        if job is None:
            rec.update(status=ng.BLOCKED, endedAt=at, seconds=0.0)
            ip.update(status=ng.BLOCKED, outcome=ng.BLOCKED, blockReason=rec["blockReason"], endedAt=at)
            self._log_event("selection:none_gen", {"status": ng.BLOCKED, "blockReason": rec["blockReason"],
                                                   "phase": "image", "round": r})
            self._apply_choice(NONE_CHOICE, at)
            return self.view()
        self._none_job = job
        ip["startedAt"] = ip["startedAt"] or at
        self.data["stage"] = "generating"
        self._save()
        self._log_event("selection:image_pick", {"status": ng.RUNNING, "round": r, "seeds": ip["seeds"],
                                                 "promptText": p["text"]})
        return self.view()

    # ── G82 LLM 형태 이름([gen3d] on_none_llm_shape) ─────────────────────────────
    def _shape_llm_route(self) -> bool:
        """(G82) 처음 [맞는 게 없어요]: 규칙 프롬프트에 중심 형태 명사가 없고 막을 사유가 없고 위기·확인 판정이 없으면 참(LLM을 부름).
        아니면 경로(rule = 규칙이 중심 명사를 잡음, none = 그 밖)를 적고 거짓. lock 안에서 부른다."""
        norm = self._confirmed_norm() or ""
        flag = llm_fill_mod.session_flag(self.s)
        with ng._prompts_lock:
            pm = ng._load_prompts()
            try:
                call, why = llm_shape_mod.rule_route(pm, pm.shape_prompt(norm, mapper_spec=self.spec))
            except (Exception, SystemExit) as exc:  # noqa: BLE001 — 판정을 못 하면 부르지 않음(fail closed)
                call, why = False, f"prompt_error:{type(exc).__name__}"
        if call and not flag:
            return True
        route = "rule" if why == "rule_has_shape" else "none"
        self.shape_llm = self._shape_llm_record(route, "session_flagged" if (call and flag) else why, None)
        self.data["generation"]["shapeLlm"] = self.shape_llm
        return False

    def _shape_llm_record(self, route: str, reason: str | None, call: dict | None) -> dict:
        c = call or {}
        return {"version": SHAPE_LLM_RECORD_VERSION, "route": route, "routeReason": reason,
                "called": bool(c.get("called")), "candidate": bool(c.get("candidate")),
                "adopted": copy.deepcopy(c.get("adopted")), "status": c.get("status"), "skipReason": c.get("skipReason"),
                "rejectReasons": list(c.get("rejectReasons") or []), "rawText": c.get("rawText"),
                "inputTextSha256": c.get("inputTextSha256"), "validatorTextSha256": c.get("validatorTextSha256"),
                "model": copy.deepcopy(c.get("model")), "promptVersion": (c.get("prompt") or {}).get("promptVersion"),
                "promptSha256": (c.get("prompt") or {}).get("promptSha256"), "validatorRules": c.get("validatorRules"),
                "seed": (c.get("options") or {}).get("seed"), "lineStages": copy.deepcopy(c.get("lineStages")),
                "exposed": False, "imageChosen": False, "candidateChosen": None, "rejected": False, "rejectedAt": None,
                "call": copy.deepcopy(call)}

    def _shape_llm_work(self, rec: dict, r: int, at: str) -> None:
        """(G82) 스레드: LLM 형태 이름 한 번(잠금 밖, 시간 한도는 설정). 끝나면 잠금 안에서 같은 회차를 이어 간다."""
        norm = self._confirmed_norm() or ""
        try:
            call = llm_shape_mod.run(self.s, self.spec, norm)
        except Exception as exc:  # noqa: BLE001 — 어떤 예외도 세션을 멈추지 않는다(지금 경로)
            call = {"status": "failed", "error": f"{type(exc).__name__}: {exc}"[:300]}
        try:
            self._shape_llm_done(rec, r, at, call)
        except Exception:  # noqa: BLE001
            import logging
            logging.getLogger(__name__).exception("shape-llm 이어 가기 실패")

    def _shape_llm_done(self, rec: dict, r: int, at: str, call: dict) -> None:
        with self.lock:
            if self.data is None:
                return
            route = "llm" if call.get("status") == "ok" and call.get("adopted") else "none"
            self.shape_llm = self._shape_llm_record(route, call.get("skipReason") or call.get("status"), call)
            self.data["generation"]["shapeLlm"] = self.shape_llm
            rec.pop("shapeLlmPending", None)
            self._log_event("selection:shape_llm", {"status": call.get("status"), "route": route,
                                                    "rejectReasons": call.get("rejectReasons")})
            if self._after_none() is not rec or self.stage != "generating":
                self.shape_llm["participantLeftBeforeResult"] = True     # 참여자가 기다리지 않고 넘어감·철회 — 기록만
                self._save()
                return
            text = self.s.log.data.get("confirmedText")
            pre = self.none_gen.precheck(self.spec, text, self.preview_mode, self._other_interviews(),
                                         llm_items=self.llm_shape_items or None, llm_shape_items=self._shape_items() or None)
            p = pre["prompt"] or {}
            rec.update(blockReason=pre["blockReason"], blockDetail=pre["blockDetail"], prompt=pre["prompt"])
            rec["imagePick"].update(promptText=p.get("text"), builderVersion=p.get("builderVersion"),
                                    imageStyle=p.get("imageStyle"), imageStyleVersion=p.get("imageStyleVersion"))
            self._note_llm_prompt(rec)
            self._launch_image_round(rec, r, at, text, pre)

    def reject_shape_basis(self) -> dict:
        """(G82) 고르기 화면의 [그 말이 아니에요]: LLM이 인용한 낱말이 아니라고 함 → 다시 부르지 않고 기존 none 경로(0번 후보로 조절)."""
        with self.lock:
            self._require("picking")
            rec = self._after_none()
            if not (rec and rec.get("shapeLlmUsed")):
                raise SelectionInvalid("LLM 형태 이름으로 그린 그림이 아닙니다.")
            at = now_iso()
            rec["imagePick"].update(status=ng.DECLINED, outcome="basis_rejected", decidedAt=at)
            rec.update(status=ng.DECLINED, basisRejected=True, endedAt=at)
            if self.shape_llm is not None:
                self.shape_llm.update(rejected=True, rejectedAt=at)
                if isinstance(self.shape_llm.get("call"), dict):
                    self.shape_llm["call"]["exposure"].update(basisRejected=True, at=at)
            self._log_event("selection:shape_llm", {"status": "basis_rejected", "round": rec["imagePick"]["round"]})
            self._apply_choice(NONE_CHOICE, at)
            return self.view()

    def _note_llm_prompt(self, rec: dict) -> None:
        """(G77) llm_fill을 켰으면 이 생성 기록에 그림 프롬프트의 형태 자리를 LLM 인용 낱말로 메웠는지 남긴다(켜지 않으면 키 없음).
        (G82) on_none_llm_shape를 켰으면 LLM 형태 이름으로 메웠는지(shapeLlmUsed)와 그 항목을 남긴다(켜지 않으면 키 없음)."""
        if self.shape_llm_on:
            rec["shapeLlmUsed"] = (rec.get("prompt") or {}).get("shapeSource") == llm_shape_mod.ORIGIN
            rec["shapeLlmItems"] = copy.deepcopy(self._shape_items()) if rec["shapeLlmUsed"] else []
        if not self.llm_on:
            return
        used = ((rec.get("prompt") or {}).get("shapeSource") == llm_fill_mod.ORIGIN)
        rec["llmPromptUsed"] = used
        rec["llmShapeItems"] = copy.deepcopy(self.llm_shape_items)
        gen = self.data["generation"]
        gen["llmPromptUsed"] = bool(gen.get("llmPromptUsed")) or used

    def _image_round_done(self, res: dict, rec: dict) -> None:
        """이미지 단계가 끝남(생성 스레드). 관문을 통과한 이미지가 있으면 고르기 화면(seed 순서), 없거나 실패면 기존 none 경로."""
        with self.lock:
            if self.data is None or self._after_none() is not rec:
                return                                   # 다른 회차로 넘어간 뒤 온 결과
            ip = rec["imagePick"]
            for k in ("run", "endedAt", "seconds", "exitCode", "llmUnload", "timing", "models"):
                ip[k] = res.get(k)
            if ip["startedAt"] is None:
                ip["startedAt"] = res.get("startedAt")
            ip["generatorTiming"] = res.get("generatorTiming")
            imgs = []
            for x in res.get("images") or []:
                g = x.get("gate") or {}
                imgs.append({"seed": x["seed"], "file": x["file"], "sha256": x["sha256"], "seconds": x.get("seconds"),
                             "gate": {k: g.get(k) for k in ("personLikeScore", "passed", "threshold", "labelScores",
                                                             "matchScore", "model", "error") if k in g} or None,
                             "problem": x.get("problem"), "shown": False, "position": None, "_path": x.get("_path")})
            status = res.get("status") or ng.FAILED
            if self.stage != "generating":
                # 참여자가 이미 넘어감(기다리지 않음·철회): 기록만 채운다
                ip["generatorStatus"] = status
                ip["images"] = [{k: v for k, v in x.items() if k != "_path"} for x in imgs]
                self._save()
                return
            shown = [x for x in imgs if x["problem"] is None]
            if status == ng.OK and not shown:
                status, res = ng.BLOCKED, {**res, "blockReason": ng.B_ALL_IMAGES_GATED,
                                           "blockDetail": ",".join(f"{x['seed']}:{x['problem']}" for x in imgs) or None}
            self._pick_paths = {}
            for pos, x in enumerate(shown if status == ng.OK else []):
                x["shown"], x["position"] = True, pos
                self._pick_paths[pos] = (Path(x["_path"]), x["sha256"])
            ip["images"] = [{k: v for k, v in x.items() if k != "_path"} for x in imgs]
            if status != ng.OK:
                ip.update(status=status, outcome=status, error=res.get("error"), blockReason=res.get("blockReason"))
                rec.update(status=status, blockReason=res.get("blockReason"), blockDetail=res.get("blockDetail"),
                           error=res.get("error"), endedAt=res.get("endedAt"), seconds=res.get("seconds"))
                self._log_event("selection:none_gen", {"status": status, "blockReason": rec["blockReason"], "phase": "image",
                                                       "round": ip["round"], "seconds": ip["seconds"]})
                self._apply_choice(NONE_CHOICE)
                return
            at = now_iso()
            ip.update(status="shown", shownOrder=[x["seed"] for x in shown], shownAt=at)
            self.data["generation"]["imagePickExposed"] = True
            if rec.get("shapeLlmUsed") and self.shape_llm is not None:
                self.shape_llm["exposed"] = True          # G82: LLM 형태 이름으로 그린 그림이 화면에 나옴
                if isinstance(self.shape_llm.get("call"), dict):
                    self.shape_llm["call"]["exposure"].update(exposed=True, at=now_iso())
            if rec.get("llmPromptUsed"):
                self.data["llmFillExposed"] = True        # G77: LLM 형태 낱말로 그린 그림이 화면에 나옴
            self.data["stage"] = "picking"
            self._save()
            self._log_event("selection:image_pick", {"status": "shown", "round": ip["round"],
                                                     "shownSeeds": ip["shownOrder"],
                                                     "hiddenSeeds": [x["seed"] for x in imgs if not x["shown"]],
                                                     "seconds": ip["seconds"]})

    def pick_image(self, choice: str) -> dict:
        """고르기 화면: 보여 준 자리 번호("0"…) 하나 또는 "none"([이 중에는 없어요]). 고르면 그 이미지로만 형태를 만든다.
        none이면 회차가 남았으면 다음 회차(새 seed 3개), 아니면 기존 none 경로(afterNone.status declined)."""
        with self.lock:
            self._require("picking")
            rec = self._after_none()
            ip = rec["imagePick"]
            at = now_iso()
            if choice == NONE_CHOICE:
                ip.update(status=ng.DECLINED, outcome="none", decidedAt=at)
                self._log_event("selection:image_pick", {"status": "none", "round": ip["round"]})
                if self._none_attempts < self.none_gen.image_rounds:
                    return self._start_image_round(at)
                rec.update(status=ng.DECLINED, endedAt=at)
                self._apply_choice(NONE_CHOICE, at)
                return self.view()
            try:
                pos = int(choice)
            except (TypeError, ValueError):
                raise SelectionInvalid(f"보여 준 그림이 아닙니다: {choice}") from None
            img = next((x for x in ip["images"] if x["shown"] and x["position"] == pos), None)
            if img is None or pos not in self._pick_paths:
                raise SelectionInvalid(f"보여 준 그림이 아닙니다: {choice}")
            path, sha = self._pick_paths[pos]
            ip.update(status="picked", outcome="picked", pickedPosition=pos, pickedSeed=img["seed"],
                      pickedImageSha256=sha, decidedAt=at)
            rec["seed"] = img["seed"]
            if rec.get("shapeLlmUsed") and self.shape_llm is not None:
                self.shape_llm["imageChosen"] = True
                if isinstance(self.shape_llm.get("call"), dict):
                    self.shape_llm["call"]["exposure"]["imageChosen"] = True
            self._log_event("selection:image_pick", {"status": "picked", "round": ip["round"], "position": pos,
                                                     "seed": img["seed"]})
            text = self.s.log.data.get("confirmedText")
            if (rec.get("llmPromptUsed") and self._llm_flag()) or \
                    (rec.get("shapeLlmUsed") and llm_fill_mod.session_flag(self.s)):
                job = "session_flagged"                     # (CP15-2·G82) LLM 낱말로 만든 그림 프롬프트는 판정 뒤 메시로 잇지 않음
            else:
                job = self.none_gen.start(self.s.id, text, source_key(self.spec), rec["prompt"]["text"], self._generation_done,
                                          attempt=rec["attempt"], spec=self.spec, other_interviews=self._other_interviews,
                                          kind="mesh", image=(path, sha), seed=img["seed"],
                                          llm_items=self.llm_shape_items or None,
                                          llm_shape_items=self._shape_items() or None)
            if isinstance(job, str):
                rec.update(status=ng.BLOCKED, blockReason=job, endedAt=at, seconds=0.0,
                           blockDetail=",".join(self._other_interviews()) or None if job == ng.B_INTERVIEW else None)
                self._log_event("selection:none_gen", {"status": ng.BLOCKED, "blockReason": job, "phase": "mesh"})
                self._apply_choice(NONE_CHOICE, at)
                return self.view()
            self._none_job = job
            rec["startedAt"] = at
            self.data["stage"] = "generating"
            self._save()
            self._log_event("selection:none_gen", {"status": ng.RUNNING, "phase": "mesh", "seed": img["seed"],
                                                   "promptText": rec["prompt"]["text"]})
            return self.view()

    def image_png(self, round_: int, position: int) -> bytes | None:
        """고르기 화면의 그림. (CP14-1) 이 세션이 지금 고르기 화면(stage picking)이고, 지금 보여 주는 회차의 보여 준 그림일 때만
        바이트를 돌려준다. 그 밖(고른 뒤·다른 회차·숨긴 그림)은 None(서버는 404). 파일이 바뀌었으면 SelectionInvalid."""
        with self.lock:
            ip = self._image_pick()
            if (self.stage != "picking" or ip is None or ip["round"] != round_ or position not in self._pick_paths
                    or not any(x["shown"] and x["position"] == position for x in ip["images"])):
                return None
            path, sha = self._pick_paths[position]
            raw = Path(path).read_bytes()
            if hashlib.sha256(raw).hexdigest() != sha:
                raise SelectionInvalid("그림 파일이 보여 준 뒤 바뀌었습니다.")
            return raw

    def skip_generation(self) -> dict:
        """[기다리지 않고 넘어갈게요]: 생성을 끄고 기존 none 경로로. (G75) 고르기 화면의 [넘어갈게요]도 같은 경로."""
        with self.lock:
            if self.stage == "picking":
                rec = self._after_none()
                at = now_iso()
                rec["imagePick"].update(status=ng.CANCELLED, outcome="skipped", decidedAt=at)
                rec.update(status=ng.CANCELLED, participantSkippedPick=True, endedAt=at)
                self._log_event("selection:none_gen", {"status": ng.CANCELLED, "participantSkippedPick": True,
                                                       "phase": "pick"})
                self._apply_choice(NONE_CHOICE, at)
                return self.view()
            self._require("generating")
            rec = self._after_none()
            ip = rec.get("imagePick")
            if ip is not None and ip["status"] == ng.RUNNING:
                ip.update(status=ng.CANCELLED, outcome=ng.CANCELLED, decidedAt=now_iso())   # 이미지 대기 중 넘어감
            rec.update(status=ng.CANCELLED, participantSkippedWait=True, endedAt=now_iso())
            self._log_event("selection:none_gen", {"status": ng.CANCELLED, "participantSkippedWait": True})
            self._apply_choice(NONE_CHOICE)             # 취소 상태를 먼저 저장하고 응답한다(CP13-4)
            if self._none_job is not None:
                self._none_job.cancel("participant_skipped_wait")    # 표시만 하고 곧 돌아옴 — 프로세스 끄기는 백그라운드
            return self.view()

    def cancel_generation(self, reason: str) -> None:
        """철회·종료: 돌고 있는 생성을 끈다(기록은 그대로)."""
        job = self._none_job
        if job is not None:
            job.cancel(reason)

    def _enter_skip(self, now: str) -> None:
        """G34: 구별되는 후보가 하나뿐 → 선택 화면을 보이지 않고 그 후보(언제나 0번)로 조절에 들어간다.
        고른 것이 아니므로 selectedCandidateId = null, none = false, skipped = true. 보여 준 후보는 없다."""
        op = self.cands["candidates"][0]
        self.data["candidatesShown"], self.data["candidatesShownAt"] = [], None
        self.data["selection"] = {"selectedCandidateId": None, "selectedIndex": None, "none": False,
                                  "skipped": True, "skipReason": SKIP_REASON, "displayPosition": None,
                                  "operationalId": op["id"], "operationalIndex": op["index"], "at": now}
        self.data["stage"] = "adjusting"
        self.current = dict(op["overrides"])
        self._ring_enter(now)
        if self.gen3d:
            self.data["generation"]["outcome"] = "skipped"      # 생성 후보가 없을 때만 건너뜀이 생긴다

    # ── G62 생성 형태 후보 ──────────────────────────────────────────────────
    def _confirmed_norm(self) -> str | None:
        """사이드카 charSpan과 같은 기준의 확정 텍스트(normalize_confirmed). 없으면 None(판정은 fail closed)."""
        text = self.s.log.data.get("confirmedText")
        return normalize_confirmed(text) if isinstance(text, str) else None

    def _preview_asset(self, a: dict | None, cid: str) -> dict | None:
        path = self._asset_paths.get(cid)
        if a is None or path is None:
            return None
        return {"assetId": a["assetId"], "glbSha256": a["glbSha256"], "glbPath": path}

    def current_asset(self) -> dict | None:
        """조절 중 지금 그릴 생성 메시: 생성 후보를 골랐고 형태 조절이 지금 처음 값과 같을 때만(형태를 바꾸면 그 형태가 보여야 함)."""
        if not self.gen3d or self.data is None:
            return None
        rec = self.data["form"]["asset"]
        if rec is None:
            return None
        items = self.table["adjustItems"]["items"]
        for item, summ in self.data["adjustments"]["items"].items():
            if "valueOverrides" in items[item] and not _same_value(summ["last"], summ["first"]):
                return None
        return self._preview_asset(rec, rec["candidateId"])

    def preview_target(self, target: str) -> tuple[dict, dict | None]:
        """미리보기 한 장의 (덮어쓰기, 생성 메시 | None). 생성 후보는 그 GLB로, current는 current_asset()으로 그린다."""
        with self.lock:
            overrides = self.overrides_for(target)
            if not self.gen3d:
                return overrides, None
            if target == "current":
                return overrides, self.current_asset()
            c = self._cand(target)
            return overrides, (self._preview_asset(c.get("asset"), target) if c is not None and "asset" in c else None)

    def drop_generated(self, cid: str, reason: str, detail: str | None, source: str) -> bool:
        """미리보기가 그리지 못한 생성 형태 후보를 후보 목록에서 뺀다(선택 전에만). 절차 메시 모습으로 생성 후보를 보이지 않기 위해서다.
        기본 후보였으면 남은 생성 후보 가운데 첫째가 기본이 되고, 없으면 절차 메시가 기본(사유 기록). 생성 후보가 모두 빠졌고
        절차 후보만으로는 건너뛸 세션(G34)이면 건너뜀으로 들어간다. cid = "current"(조절 중 고른 생성 메시)면 그 자산을 버린다."""
        with self.lock:
            if not self.gen3d or self.data is None:
                return False
            gen = self.data["generation"]
            at = now_iso()
            if cid == "current":
                rec = self.data["form"]["asset"]
                if rec is None:
                    return False
                self.data["form"]["asset"] = None
                gen["assetDropped"] = {"assetId": rec["assetId"], "candidateId": rec["candidateId"], "reason": reason,
                                       "detail": (detail or "")[:300]}
                self._save()
                self._log_event("selection:form_asset_dropped", {"assetId": rec["assetId"], "reason": reason, "source": source})
                return True
            c = self._cand(cid)
            if c is None or "asset" not in c or self.stage != "selecting":
                return False
            self.cands["candidates"] = [x for x in self.cands["candidates"] if x["id"] != cid]
            self.cands["displayOrder"] = [x for x in self.cands["displayOrder"] if x != cid]
            self.data["candidatesShown"] = [x for x in self.data["candidatesShown"] if x != cid]
            self._asset_paths.pop(cid, None)
            drop = {"candidateId": cid, "assetId": c["asset"]["assetId"], "reason": reason, "source": source,
                    "detail": (detail or "")[:300], "at": at}
            for g in (self.cands["generation"], gen):
                g["offered"] = [o for o in g["offered"] if o["candidateId"] != cid]
                g.setdefault("previewDropped", []).append(dict(drop))
            gen["shownOrder"] = [x for x in gen.get("shownOrder", []) if x != cid]
            if gen.get("defaultCandidateId") == cid:
                nxt = next((x for x in self.cands["displayOrder"] if x in self._asset_paths), None)
                for g in (self.cands["generation"], gen):
                    g["defaultCandidateId"] = nxt
                    if nxt is None:
                        g["defaultFormSource"] = DEFAULT_PROCEDURAL
                        g["defaultFallbackReason"] = reason
                if nxt is not None:
                    self.cands["displayOrder"] = [nxt] + [x for x in self.cands["displayOrder"] if x != nxt]
                    self.data["candidatesShown"] = list(self.cands["displayOrder"])
                self.data["defaultFormSource"] = gen["defaultFormSource"]
            if not self._asset_paths and gen.get("proceduralSelectionStep") == "skip" and len(self.cands["candidates"]) == 1:
                self.cands["selectionStep"] = "skip"
                self._enter_skip(at)
            self._save()
            self._log_event("selection:generated_dropped", {"candidateId": cid, "assetId": drop["assetId"],
                                                            "reason": reason, "source": source})
            an = self._after_none()
            if (c.get("origin") == ng.ORIGIN and an is not None and self.stage == "selecting"
                    and not any(x.get("origin") == ng.ORIGIN for x in self.cands["candidates"])):
                # G73: 참여자는 이미 나머지 후보에 [맞는 게 없어요]라고 했다 → 만든 후보를 보일 수 없으면 기존 none 경로
                an["previewDropped"] = {"reason": reason, "source": source, "at": at}
                self._apply_choice(NONE_CHOICE, at)
            return True

    def _record_generation_choice(self, chosen: dict | None) -> None:
        """고른 결과를 generation에 남기고, 생성 후보를 골랐으면 form.asset을 적는다(GLB·사이드카는 세션 폴더에 복사 —
        러너는 selection.json 기준 상대 파일 이름 glb로 읽는다). 복사하지 못하면 glb = null(러너가 절차 메시로 돌아가고 기록함)."""
        gen = self.data["generation"]
        offered = [g["candidateId"] for g in gen["offered"]]
        cid = chosen["id"] if chosen is not None else None
        gen["outcome"] = "none" if chosen is None else ("generated_chosen" if cid in offered else "procedural_chosen")
        gen["declined"] = [g["assetId"] for g in gen["offered"] if g["candidateId"] != cid]
        # 기본 후보(미리 선택)가 있었으면 그대로 확정했는지(true) 다른 후보·'맞는 것이 없다'로 바꿨는지(false). 기본이 없으면 null
        default_id = gen.get("defaultCandidateId")
        gen["acceptedDefault"] = None if default_id is None else (cid == default_id)
        self.data["selection"]["acceptedDefault"] = gen["acceptedDefault"]
        an = self._after_none()
        for rec in ([an] + list(gen.get("afterNoneEarlier") or [])) if an is not None else []:
            if rec.get("candidateId") is not None:
                rec["chosen"] = cid == rec["candidateId"]     # G73: [맞는 게 없어요] 뒤 만든 후보(그 시도의 것)를 골랐는가
                if rec.get("shapeLlmUsed") and self.shape_llm is not None and rec["chosen"]:
                    self.shape_llm["candidateChosen"] = True     # G82: LLM 형태 이름으로 만든 물체를 골랐음
        if self.shape_llm is not None and self.shape_llm.get("exposed") and self.shape_llm.get("candidateChosen") is None:
            self.shape_llm["candidateChosen"] = False
        if cid not in offered:
            self.data["form"]["asset"] = None
            return
        a = chosen["asset"]
        rec = {"candidateId": cid, **{k: copy.deepcopy(a[k]) for k in (
            "assetId", "glb", "glbSha256", "sidecarSha256", "pipeline", "seed", "models", "promptText", "lexiconVersion",
            "covariates", "normalization", "gate")}, "sidecar": None}
        if chosen.get("origin") == ng.ORIGIN:
            rec["origin"] = ng.ORIGIN                            # G73: [맞는 게 없어요] 뒤 만든 후보(G62 기본·대안 후보와 구분)
        rec["glb"] = None
        if self.persist:
            self.dir.mkdir(parents=True, exist_ok=True)
            stem = "form-asset-" + a["glbSha256"][:16]
            try:
                raw = Path(self._asset_paths[cid]).read_bytes()
                if hashlib.sha256(raw).hexdigest() == a["glbSha256"]:
                    (self.dir / (stem + ".glb")).write_bytes(raw)
                    rec["glb"] = stem + ".glb"
                else:
                    gen.setdefault("copyErrors", []).append({"assetId": a["assetId"], "reason": "glb_sha256_mismatch"})
                side = Path(self._sidecar_paths[cid]).read_bytes()
                (self.dir / (stem + ".json")).write_bytes(side)
                rec["sidecar"] = stem + ".json"
            except OSError as exc:
                gen.setdefault("copyErrors", []).append({"assetId": a["assetId"], "reason": f"copy_failed: {type(exc).__name__}"})
        self.data["form"]["asset"] = rec

    def _drop_asset_if_form_edited(self) -> None:
        """생성 후보를 고른 뒤 형태 조절을 처음과 다른 값으로 끝냈으면 생성 메시를 쓰지 않는다(참여자가 고친 형태가 그려짐)."""
        asset = self.data["form"]["asset"]
        if asset is None:
            return
        items = self.table["adjustItems"]["items"]
        for item, summ in self.data["adjustments"]["items"].items():
            if "valueOverrides" in items[item] and not _same_value(summ["last"], summ["first"]):
                self.data["form"]["asset"] = None
                self.data["generation"]["assetDropped"] = {"assetId": asset["assetId"], "candidateId": asset["candidateId"],
                                                           "reason": "form_edited", "formFirst": summ["first"],
                                                           "formLast": summ["last"]}
                return

    def asset_glb(self, cid: str) -> bytes:
        """생성 후보의 GLB 바이트(미리보기용). 제시한 생성 후보가 아니거나 파일이 바뀌었으면 SelectionInvalid."""
        with self.lock:
            c = self._cand(cid)
            if c is None or "asset" not in c or cid not in self._asset_paths:
                raise SelectionInvalid(f"생성 형태 후보가 아닙니다: {cid}")
            raw = Path(self._asset_paths[cid]).read_bytes()
            if hashlib.sha256(raw).hexdigest() != c["asset"]["glbSha256"]:
                raise SelectionInvalid(f"생성 형태 GLB가 제시한 뒤 바뀌었습니다: {c['asset']['assetId']}")
            return raw

    # ── 5 조절 ──────────────────────────────────────────────────────────────
    def _validate(self, item: str, value) -> dict:
        """(항목, 값) → 덮어쓰기 키:값. 표 밖이면 SelectionInvalid."""
        items = self.table["adjustItems"]["items"]
        if item not in self.items:
            raise SelectionInvalid(f"조절 항목이 아닙니다: {item} (가능: {', '.join(self.items)}). 위치·거리는 조절하지 않습니다(G10).")
        it = items[item]
        if it["kind"] == "swatch":
            sw = next((s for s in it["swatches"] if s["id"] == value), None) if isinstance(value, str) else None
            if sw is None:
                raise SelectionInvalid(f"색 견본 목록에 없는 값입니다: {value!r}")
            return {"material.color.h": sw["h"], "material.color.s": sw["s"], "material.color.l": sw["l"]}
        if it["kind"] == "hue_ring":
            return self._validate_ring(it, value)         # G79
        if it["kind"] == "category":
            allowed = self.item_values(item)          # 표의 값 + 표에 없던 말한 값(있으면)
            if not isinstance(value, str) or value not in allowed:
                raise SelectionInvalid(f"{item}: 표에 없는 값입니다: {value!r} (가능: {allowed})")
            vo = it.get("valueOverrides")
            if vo is not None:
                # D6: 값 하나가 form.type·form.base를 함께 정한다. 표에 없던 말한 form.type 값이면 기본 형상을 그리지 않음
                return dict(vo[value]) if value in vo else {it["key"]: value, "form.base": "none"}
            return {it["key"]: value}
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise SelectionInvalid(f"{item}: 숫자가 아닙니다: {value!r}")
        step = next((v for v in it["values"] if abs(v - float(value)) < 1e-9), None)
        if step is None:
            raise SelectionInvalid(f"{item}: 정해진 단계 밖의 값입니다: {value!r} (가능: {it['values']})")
        return {it["key"]: float(step)}

    def adjust(self, item: str, value) -> dict:
        with self.lock:
            self._require("adjusting")
            off = self.unavailable_items()
            if item in off:
                raise SelectionError(f"이 미리보기 방식({self.preview_mode})에서는 '{item}' 항목이 화면에 반영되지 않아 "
                                     f"꺼 두었습니다({off[item]}, G22).")
            keys = self._validate(item, value)
            before = self._item_value(item, effective_params(self.spec, self.defaults, self.current))
            self.current.update(keys)
            params = effective_params(self.spec, self.defaults, self.current)
            after = self._item_value(item, params)
            at = now_iso()
            ev = self.data["adjustments"]["events"]
            event = {"i": len(ev), "item": item, "value": after, "previous": before, "at": at}
            if "valueOverrides" in self.table["adjustItems"]["items"][item]:
                # G39: 형태 조작 한 번 = 고른 값 하나(value). 그 조작으로 정해진 세 슬롯을 함께 남긴다(변형값은 base가 spec의
                # base와 다르면 null — 이전 base의 변형값은 지워짐)
                event["formSlots"] = self._form_slots(params)
            if self.ring is not None and item == "color":
                event["input"] = copy.deepcopy(value)       # G79: 고리({hueStep…})·견본 id·"said" 가운데 무엇으로 바꿨는지
            ev.append(event)
            summ = self.data["adjustments"]["items"].setdefault(item, {"count": 0, "first": before, "last": before,
                                                                       "firstAt": at, "lastAt": at})
            summ["count"] += 1
            summ["last"], summ["lastAt"] = after, at
            self.data["colorChanged"] = self._color_changed()
            self._save()
            return self.view()

    def _form_slots(self, params: dict) -> dict:
        base = params.get("form.base", "none")
        return {"form.type": params["form.type"], "form.base": base,
                "form.baseVariant": copy.deepcopy(variant_for(self.spec, base))}

    def _proportions_record(self, final: bool) -> dict:
        """G72: 너비·높이·깊이 조절 기록. axes = 축별 {item, first, final, edited, count}(원값), first·final = 그리는 비율
        (가장 큰 값 = 1). said = 말한 비율(spec, 없으면 null). final = False(조절 전)면 final 값은 null."""
        start = effective_params(self.spec, self.defaults)
        now = effective_params(self.spec, self.defaults, self.current)
        summ = self.data["adjustments"]["items"] if self.data else {}
        axes = {}
        for item, ax in PROPORTION_ITEMS.items():
            if item not in self.table["adjustItems"]["items"]:
                continue
            key = self.table["adjustItems"]["items"][item]["key"]
            s = summ.get(item)
            f0, f1 = round(float(start[key]), 4), round(float(now[key]), 4)
            axes[ax] = {"item": item, "first": f0, "final": f1 if final else None,
                        "edited": bool(final and s and not _same_value(s["last"], s["first"])),
                        "count": s["count"] if s else 0}
        return {"said": copy.deepcopy(slot_value(self.spec, PROPORTION_SLOT)), "rule": PROPORTION_RULE, "axes": axes,
                "first": proportions_effective(start), "final": proportions_effective(now) if final else None,
                "edited": any(a["edited"] for a in axes.values())}

    def _color_changed(self) -> bool:
        """G31: 조절 기록에서 색의 처음 값과 마지막 값이 다른가(만졌다가 되돌리면 false, 횟수는 adjustments.items.color)."""
        c = self.data["adjustments"]["items"].get("color")
        return bool(c) and not _same_value(c["last"], c["first"])

    def _final_overrides(self) -> dict:
        base = self._base()
        final = effective_params(self.spec, self.defaults, self.current)
        keys = self.table["overrideKeys"]["numeric"] + self.table["overrideKeys"]["categorical"]
        out = {}
        for k in sorted(keys):
            if final[k] != base[k]:
                v = final[k]
                out[k] = round(v, 4) if isinstance(v, float) else v
        return out

    def _slot_sources(self) -> tuple[dict, dict]:
        sel = self.data["selection"]
        # 고른 후보의 축 값만 chosen이다. 맞는 것이 없다(none)·선택 단계 건너뜀(skipped)은 고른 것이 없다
        chosen = {} if sel["none"] or sel.get("skipped") else dict(self._cand(sel["selectedCandidateId"])["axisValues"])
        unrendered = form_said_unrendered(self.spec, self.table)        # G32: 모형이 없는 모양어만 말함
        rendered = (slot_value(self.spec, "form.type") is None and bool(rendered_shape_words(self.spec, self.table))
                    and not base_drawn(self.spec))
        words = (unrendered_said_words(self.spec, self.table) if unrendered
                 else said_words(rendered_shape_words(self.spec, self.table)) if rendered else [])
        blocks = form_blocks(self.spec)                                 # G50 (1): 넷째 범주 — 형태 후보를 내지 않았음
        floor = self.data.get("distanceFloor")
        items = self.table["adjustItems"]["items"]
        final = effective_params(self.spec, self.defaults, self.current)
        start = effective_params(self.spec, self.defaults)
        edited: dict[str, object] = {}
        form_item = None                                # G39: 형태 조절이 처음 값과 다른 값으로 끝났으면 그 기록(세 슬롯에 붙임)
        for item, summ in self.data["adjustments"]["items"].items():
            if _same_value(summ["last"], summ["first"]):
                continue                                # 만졌지만 처음 값으로 돌아옴 → 출처는 그대로(횟수는 items에 남음)
            if "valueOverrides" in items[item]:
                form_item = {"item": item, "first": summ["first"], "last": summ["last"], "count": summ["count"]}
                # G39: base가 바뀌면 이전 base의 변형값은 쓰이지 않는다(Unity와 같은 규칙). 바뀐 것을 '고침'으로 남김(값 null)
                v0, v1 = variant_for(self.spec, start["form.base"]), variant_for(self.spec, final["form.base"])
                if v1 != v0:
                    edited["form.baseVariant"] = copy.deepcopy(v1)
            for slot in items[item]["slots"]:
                if slot == PROPORTION_SLOT:
                    eff = proportions_effective(final)
                    edited[slot] = {**eff, "axisSaid": True}     # 참여자가 화면에서 축을 정함(방향 포함)
                    continue
                if slot == "material.color":
                    edited[slot] = {k: round(final[f"material.color.{k}"], 4) for k in ("h", "s", "l")}
                elif slot == "material.saturation":
                    edited[slot] = round(final["material.color.s"], 4)
                elif "valueOverrides" in items[item]:
                    # D6 형태 항목: 값 하나가 form.type·form.base를 함께 정하므로 실제로 바뀐 슬롯만 '고침'
                    if final[slot] != start[slot]:
                        edited[slot] = final[slot]
                else:
                    v = final[items[item]["key"]]
                    edited[slot] = round(v, 4) if isinstance(v, float) else v
        d = self.defaults
        default_of = {"material.color": {"h": d["material.color.h"], "s": d["material.color.s"], "l": d["material.color.l"]},
                      "material.saturation": d["material.color.s"]}
        out, counts = {}, {k: 0 for k in self.sources_list}
        # G62: 생성 형태 후보를 골랐고 형태 조절로 바꾸지 않았으면 form.type 출처는 generated_chosen(형태 조절을 다른 값으로
        # 끝냈으면 자산을 버리고(finish) 다른 슬롯처럼 edited·said·default 규칙을 따른다)
        asset = (self.data.get("form") or {}).get("asset") if self.gen3d else None
        generated = asset is not None and form_item is None
        basis = variant_key_basis(self.spec)
        llm_slots = {sl: {**a, "item": item} for item, a in self.llm_applied.items() for sl in a["specSlots"]}
        for slot in (SLOTS + (PROPORTION_SLOT,) if self.has_proportions else SLOTS):
            slot_val = slot_value(self.spec, slot)
            said = slot_val
            if slot == "layout.distance" and floor and floor.get("said") is not None:
                said = floor["said"]            # G33: 원래 말한 값(하한 전). 그려진 값은 value(= 슬롯 값 = 하한)
            # form.baseVariant 기본값 = null(형상 프리셋 기본값, 값 표 defaults에 없음)
            dv = None if slot == "form.baseVariant" else default_of.get(slot, d.get(slot))
            rec = {"saidValue": said, "chosenValue": chosen.get(slot), "defaultValue": dv}
            if slot == "form.type" and generated and slot not in edited:
                rec = {"source": GENERATED_CHOSEN, "value": slot_val if slot_val is not None else dv, **rec,
                       "generatedAsset": {"assetId": asset["assetId"], "glbSha256": asset["glbSha256"],
                                          "candidateId": asset["candidateId"]},
                       # 기본(미리 선택된) 생성 후보를 그대로 확정했으면 true, 다른 후보 가운데서 골랐으면 false
                       "acceptedDefault": self.data["generation"].get("acceptedDefault") is True}
                if asset.get("origin") == ng.ORIGIN:
                    # G73: 러너 계약 값은 generated_chosen 그대로(PlacementSelection.SourceValues03), 어디서 온 후보인지는 여기에
                    rec["origin"] = ng.ORIGIN
            elif slot in edited:
                rec = {"source": "edited", "value": edited[slot], **rec}
            elif slot in llm_slots:
                # G77: LLM이 원문 인용과 함께 채운 처음 값을 참여자가 바꾸지 않음(바꿨으면 위 edited)
                a = llm_slots[slot]
                rec = {"source": llm_fill_mod.ORIGIN, "value": self._slot_final(slot, final), **rec,
                       "llmQuote": {"item": a["item"], "slot": a["slot"], "value": a["value"], "quote": a["quote"],
                                    "charSpan": list(a["charSpan"])}}
            elif slot in chosen:
                rec = {"source": "said_unrendered_chosen" if slot == "form.type" and unrendered else "chosen",
                       "value": chosen[slot], **rec}
            elif slot_val is not None:
                rec = {"source": "said", "value": slot_val, **rec}
            elif slot == "form.type" and rendered:
                rec = {"source": "said", "value": dv, **rec}           # 모형이 있는 모양어: 말한 자리(모형은 saidWords)
            elif slot == "form.type" and unrendered:
                rec = {"source": "said_unrendered_default", "value": dv, **rec}
            else:
                rec = {"source": "default", "value": dv, **rec}
            if slot == "form.type" and (unrendered or rendered):
                rec["saidWords"] = words                               # 원래 말한 모양어(G32)·그리지 않은 범주 낱말(G45·G51)
            if slot == "form.type" and blocks:
                # 조절 화면에서 참여자가 형태를 바꾸는 것은 막지 않는다(결정 G50에 없음) — 그렇게 두었다는 것을 남긴다
                rec["formBlocked"] = {"rule": "G50", "by": sorted({u["lemma"] for u in blocks}), "adjustFormAllowed": True}
            if slot == "form.baseVariant" and basis is not None:
                rec["keyBasis"] = basis                                # G38: 키마다 낱말 뜻(lexicon_implied) | 참여자 말(said)
            if slot in FORM_SLOTS and form_item is not None:
                rec["formItem"] = form_item                            # G39: 세 슬롯을 정한 형태 조작(처음·마지막 값·횟수)
            counts[rec["source"]] += 1
            out[slot] = rec
        return out, counts

    def _slot_final(self, slot: str, final: dict):
        """슬롯 하나의 최종 값(기록용, edited와 같은 표현)."""
        if slot == "material.color":
            return {k: round(final[f"material.color.{k}"], 4) for k in ("h", "s", "l")}
        if slot == "material.saturation":
            return round(final["material.color.s"], 4)
        v = final.get(slot)
        return round(v, 4) if isinstance(v, float) else v

    def _llm_participant(self) -> dict:
        """(G77) 채택 값마다 참여자가 그대로 뒀는지·고쳤는지·최종 값(조절 항목 값 표현)."""
        out = {}
        start = effective_params(self.spec, self.defaults, self.cands["candidates"][0]["overrides"])
        final = effective_params(self.spec, self.defaults, self.current)
        for item, a in sorted(self.llm_applied.items()):
            summ = self.data["adjustments"]["items"].get(item)
            first = self._item_value(item, start)
            last = self._item_value(item, final)
            kept = _same_value(first, last)
            out[item] = {"first": first, "final": last, "kept": kept, "edited": not kept,
                         "adjustCount": summ["count"] if summ else 0}
        return out

    def finish(self) -> dict:
        with self.lock:
            self._require("adjusting")
            self.data["adjustments"]["finishedAt"] = now_iso()
            if self.gen3d:
                self._drop_asset_if_form_edited()
            self.data["finalOverrides"] = self._final_overrides()
            self.data["sourceDetails"], self.data["sourceCounts"] = self._slot_sources()
            self.data["sources"] = {k: v["source"] for k, v in self.data["sourceDetails"].items()}   # 러너 계약 필드
            if self.has_proportions:
                self.data["proportions"] = self._proportions_record(final=True)
            if self.llm_on and self.data.get("llmFill") is not None:
                self.data["llmFill"]["participant"] = self._llm_participant()
            if self.data.get("colorRing") is not None:
                self.data["colorRing"]["final"] = self._ring_final()     # G79-d: 말함 | llm_quoted | 말하지도 고르지도 않음 | 고름
            self.data["stage"] = "premeasure"
            self._save()
            self._log_event("selection:adjusted", {
                "finalOverrides": self.data["finalOverrides"], "sourceCounts": self.data["sourceCounts"],
                "adjustCounts": {k: v["count"] for k, v in self.data["adjustments"]["items"].items()},
                "adjustUnavailable": sorted(self.data.get("adjustUnavailable") or {}),
                "previewMode": self.preview_mode})
            return self.view()

    def final(self) -> dict:
        """헤드셋 러너가 읽을 것: 원본 spec(바꾸지 않음) + selection.json.
        러너에는 이 응답의 spec이 아니라 저장된 spec 파일(specPath)과 selection.json을 넘긴다. runnerReady가 false면
        넘길 수 없고 runnerBlockers에 이유가 있다(G26)."""
        with self.lock:
            if self.stage not in ("premeasure", "done"):
                raise SelectionError("조절을 마친 뒤에 최종 형상이 정해집니다([다 고쳤어요] 뒤).")
            return {"sessionId": self.s.id, "runnerReady": self.data["runnerReady"],
                    "runnerBlockers": list(self.data["runnerBlockers"]),
                    "specPath": self.data["spec"]["path"] if self.data["runnerReady"] else None,
                    "selectionPath": str(self.dir / "selection.json") if self.persist else None,
                    "spec": self.spec, "selection": self.data}

    # ── 6 사전 측정 ─────────────────────────────────────────────────────────
    def premeasure_view(self) -> dict:
        with self.lock:
            if self.stage not in ("premeasure", "done"):
                raise SelectionError("사전 측정은 조절을 마친 뒤에 합니다(G11).")
            pm = self.protocol.data["premeasure"]
            pinfo = self.protocol.info()
            return {"sessionId": self.s.id, "instruction": pm["instruction"]["text"],
                    "scale": {k: pm["scale"][k] for k in ("min", "max", "anchors")}, "skipLabel": pm["skipLabel"]["text"],
                    "items": [{"id": i["id"], "text": i["text"], "status": i["status"]} for i in pm["items"]],
                    "draftCount": pinfo["draftCount"], "completed": self.premeasure is not None,
                    "responses": None if self.premeasure is None else {i["id"]: i["value"] for i in self.premeasure["items"]}}

    def submit_premeasure(self, responses: dict) -> dict:
        with self.lock:
            self._require("premeasure")
            pm = self.protocol.data["premeasure"]
            lo, hi = int(pm["scale"]["min"]), int(pm["scale"]["max"])
            ids = [i["id"] for i in pm["items"]]
            extra = sorted(set(responses) - set(ids))
            if extra:
                raise SelectionInvalid(f"모르는 문항: {extra}")
            missing = [i for i in ids if i not in responses]
            if missing:
                raise SelectionInvalid(f"응답이 없는 문항: {missing} (답하지 않으려면 null)")
            for k, v in responses.items():
                if v is not None and (isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi):
                    raise SelectionInvalid(f"{k}: {lo}–{hi} 정수 또는 null이어야 합니다: {v!r}")
            pinfo = self.protocol.info()
            sel = self.data["selection"]
            now = now_iso()
            items = [{"id": i["id"], "text": i["text"], "status": i["status"], "source": i["source"],
                      "value": responses[i["id"]], "skipped": responses[i["id"]] is None} for i in pm["items"]]
            self.premeasure = {
                "formatVersion": PREMEASURE_VERSION, "sessionId": self.s.id, "timepoint": "pre",
                "protocolId": pinfo["protocolId"], "protocolVersion": pinfo["protocolVersion"],
                "draftCount": pinfo["draftCount"], "draftKeys": pinfo["draftKeys"],
                "instruction": pm["instruction"]["text"], "scale": {k: pm["scale"][k] for k in ("min", "max", "anchors")},
                "selectionNone": sel["none"],       # G23: '고르지 않음' 표시를 붙여 따로 본다
                "operationalId": sel["operationalId"], "finalOverrides": self.data["finalOverrides"],
                "items": items, "completedAt": now,
            }
            path = None
            if self.persist:
                self.dir.mkdir(parents=True, exist_ok=True)
                p = self.dir / "premeasure.json"
                p.write_text(json.dumps(self.premeasure, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
                path = str(p)
            answered = sum(1 for i in items if not i["skipped"])
            self.data["premeasure"] = {"path": path, "completedAt": now, "answered": answered,
                                       "skipped": len(items) - answered}
            self.data["stage"] = "done"
            self._save()
            self._log_event("selection:premeasure", {"answered": answered, "skipped": len(items) - answered,
                                                     "selectionNone": sel["none"], "draftCount": pinfo["draftCount"]})
            return self.view()

    # ── 미리보기 ────────────────────────────────────────────────────────────
    def overrides_for(self, target: str) -> dict:
        """target = 후보 id 또는 "current"(조절 중 지금 상태)."""
        with self.lock:
            if self.cands is None:
                raise SelectionError("후보가 아직 없습니다.")
            if target == "current":
                return dict(self.current)
            c = self._cand(target)
            if c is None:
                raise SelectionInvalid(f"후보가 아닙니다: {target}")
            return dict(c["overrides"])

    def adjust_samples(self, item: str) -> list[dict]:
        """조절 화면 견본(G44, 화면 표현 전용): 지금 상태에서 범주 항목 item만 이 세션의 값 하나로 바꾼 덮어쓰기를 값마다.
        형태 버튼에 낱말 대신 견본 그림을 그리고(WebGL·image), 움직임 버튼에 머물면 본 미리보기로 미리 보여 주는 데 쓴다.
        읽기만 한다: 조절 기록·selection.json·현재 상태를 바꾸지 않는다. 값 목록·검사는 adjust와 같다(_validate)."""
        with self.lock:
            self._require("adjusting")
            it = self.table["adjustItems"]["items"].get(item)
            if item not in self.items or it is None or it["kind"] != "category":
                raise SelectionInvalid(f"견본은 범주 항목만 그립니다: {item}")
            out = []
            for v in self.item_values(item):
                ov = dict(self.current)
                ov.update(self._validate(item, v))
                out.append({"value": v, "overrides": ov})
            return out

    def unavailable_items(self) -> dict:
        """지금 미리보기 방식에서 화면에 반영되지 않아 끈 조절 항목 {항목: 이유}(G22)."""
        return dict(STILL_PREVIEW_UNAVAILABLE.get(self.preview_mode, {}))

    def _unavailable_record(self, at: str) -> dict:
        prev = (self.data or {}).get("adjustUnavailable") or {}
        return {k: prev.get(k) if prev.get(k, {}).get("reason") == why else {"reason": why, "previewMode": self.preview_mode,
                                                                                "since": at, "stage": self.stage or "selecting"}
                for k, why in self.unavailable_items().items()}

    def _preview_record(self) -> dict:
        """selection.json의 preview: requested·mode·reason(0.1·0.2 스키마 필드) + 이 세션에서 실제로 쓴 방식."""
        prev = (self.data or {}).get("preview") or {}
        if not prev:
            # 서버 쪽에서 이미 내려간 채로 시작(빌드 폴더·플레이어 없음 등): 그것도 fallbacks 첫 항목으로 남긴다
            req, start = self.rt.preview.requested, self.rt.preview.mode
            first = [] if req == start or req == "none" else [{"at": now_iso(), "from": req, "to": start,
                                                                 "reason": (self.rt.preview.reason or "")[:300],
                                                                 "source": "server", "stage": None}]
            return {"requested": req, "mode": self.preview_mode, "reason": self.preview_reason, "serverMode": start,
                    "shown": {}, "fallbacks": first, "webgl": None}
        return {"requested": self.rt.preview.requested, "mode": self.preview_mode, "reason": self.preview_reason,
                "serverMode": prev.get("serverMode", self.rt.preview.mode),
                "shown": prev.get("shown", {}), "fallbacks": prev.get("fallbacks", []), "webgl": prev.get("webgl")}

    def _downgrade(self, to: str, reason: str, source: str, stage: str | None) -> None:
        """이 세션의 미리보기 방식을 내린다(webgl → image → none). 기록·세션 로그 알림을 남긴다. lock 안에서 부른다."""
        frm = self.preview_mode
        if to == frm:
            return
        at = now_iso()
        self.preview_mode, self.preview_reason = to, f"{frm} → {to}: {reason}"[:300]
        rec = {"at": at, "from": frm, "to": to, "reason": reason[:300], "source": source, "stage": stage or self.stage}
        self.s._alert("preview_fallback", self.preview_reason, None)
        if self.data is not None:
            pv = self._preview_record()
            pv["fallbacks"] = pv["fallbacks"] + [rec]
            self.data["preview"] = pv
            self.data["adjustUnavailable"] = self._unavailable_record(at)
            self._save()
            self.s.log.add_event("selection:preview", {"event": "fallback", **rec,
                                                       "adjustUnavailable": sorted(self.data["adjustUnavailable"])})
            if to == "none" and self.gen3d:
                # G62: 글 요약으로는 생성 형태를 보일 수 없다 → 남은 생성 후보를 빼고, 조절 중이면 고른 생성 메시도 버린다
                for cid in list(self._asset_paths):
                    if self.stage == "selecting":
                        self.drop_generated(cid, R_NO_SHAPE_PREVIEW, "preview mode none", source)
                if self.stage == "adjusting" and self.data["form"]["asset"] is not None:
                    self.drop_generated("current", R_NO_SHAPE_PREVIEW, "preview mode none", source)
        self.s._save()

    def note_preview_fallback(self) -> None:
        """image 경로(상주 플레이어)가 실패했을 때: 이 세션을 none으로 내리고 세션 로그 알림으로 남긴다."""
        with self.lock:
            if self.preview_mode != "image":
                return
            self._downgrade("none", self.rt.preview.last_image_error or self.rt.preview.reason or "미리보기 플레이어 실패",
                            "server", None)

    def client_preview(self, event: str, mode: str, stage: str | None, reason: str | None = None,
                       webgl: dict | None = None) -> dict:
        """브라우저(stage.js)가 알린 미리보기 결과.
        shown    = 그 단계에서 mode로 실제로 그렸음(webgl이면 렌더러 문자열 등 webgl 정보를 함께 받음).
        fallback = mode(webgl·image)로 그리지 못함 → 이 세션을 다음 방식으로 내린다(webgl → image(쓸 수 있으면) → none).
        기록하는 것은 방식·이유·브라우저 WebGL 렌더러 문자열(GPU 이름)·Unity 그래픽 장치 문자열·시간뿐이다(참여자 식별 정보 없음)."""
        if event not in PREVIEW_CLIENT_EVENTS:
            raise SelectionInvalid(f"모르는 미리보기 알림: {event!r} (가능: {', '.join(PREVIEW_CLIENT_EVENTS)})")
        if mode not in ("webgl", "image", "none"):
            raise SelectionInvalid(f"모르는 미리보기 방식: {mode!r}")
        if stage is not None and stage not in PREVIEW_STAGES:
            raise SelectionInvalid(f"모르는 단계: {stage!r}")
        with self.lock:
            if self.data is None:
                raise SelectionError("후보가 아직 없습니다.")
            if event == "asset_failed":
                # G62: 브라우저 미리보기가 생성 형태 GLB 하나를 그리지 못함 → 그 후보를 빼고 사유를 남긴다(세션 방식은 그대로)
                target = webgl.get("candidateId") if isinstance(webgl, dict) else None
                if not isinstance(target, str) or not target:
                    raise SelectionInvalid("asset_failed에는 webgl.candidateId(생성 후보 id 또는 current)가 필요합니다")
                self.drop_generated(target, R_PREVIEW_FAILED, reason or "원인 미상", f"client:{mode}")
                return self.view()
            if event == "fallback":
                if mode == self.preview_mode and mode != "none":
                    self._downgrade(self.rt.preview.fallback_target(mode) if mode == "webgl" else "none",
                                    reason or "원인 미상", "client", stage)
                return self.view()
            # shown: 지금 세션 방식과 같을 때만 적는다(이미 내려간 뒤 늦게 온 알림은 버림)
            if mode != self.preview_mode:
                return self.view()
            pv = self._preview_record()
            changed = False
            if stage is not None:
                seen = list(pv["shown"].get(stage, []))
                if mode not in seen:
                    seen.append(mode)
                    pv["shown"] = {**pv["shown"], stage: seen}
                    changed = True
            if mode == "webgl" and webgl and pv["webgl"] is None:
                keep = {}
                for k in ("renderer", "vendor", "graphicsDevice", "version"):
                    v = webgl.get(k)
                    if isinstance(v, str) and v:
                        keep[k] = v[:200]
                for k in ("readyMs", "warmupMs"):
                    v = webgl.get(k)
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        keep[k] = round(float(v), 1)
                keep["at"] = now_iso()
                pv["webgl"] = keep
                changed = True
            if changed:
                self.data["preview"] = pv
                self._save()
                self.s.log.add_event("selection:preview", {"event": "shown", "mode": mode, "stage": stage,
                                                           "webgl": pv["webgl"] if mode == "webgl" else None})
                self.s._save()
            return self.view()

    # ── 화면용 ──────────────────────────────────────────────────────────────
    def summary(self, overrides: dict) -> list[str]:
        """preview none 모드에서 보이는 속성 요약(연구·시험용. 덮어쓰기 키 = 값)."""
        p = effective_params(self.spec, self.defaults, overrides)
        keys = ["form.type", "form.base", "layout.size", "material.opacity", "material.brightness", "material.roughness",
                "motion.type", "material.color.h", "material.color.s", "material.color.l"]
        if PROPORTION_KEYS[0] in p:
            keys.insert(3, "layout.proportions")
        eff = proportions_effective(p)
        return [(f"{k} = {eff}" + (" *" if any(x in overrides for x in PROPORTION_KEYS) else "")) if k == "layout.proportions" else
                f"{k} = {round(p[k], 4) if isinstance(p[k], float) else p[k]}" + (" *" if k in overrides else "")
                for k in keys]

    def preview_info(self) -> dict:
        """화면용 미리보기 정보: 서버 설정(rt.preview.info) 위에 이 세션의 방식을 얹는다."""
        info = self.rt.preview.info()
        info["serverMode"] = info["mode"]
        info["mode"] = self.preview_mode
        info["reason"] = self.preview_reason
        if self.preview_mode != "webgl":
            info["webglUrl"] = None
        info["fallback"] = self.rt.preview.fallback_target(self.preview_mode) if self.preview_mode == "webgl" else None
        return info

    def view(self) -> dict:
        with self.lock:
            pinfo = self.protocol.info()
            out = {"sessionId": self.s.id, "stage": self.stage, "preview": self.preview_info(),
                   "draftCount": pinfo["draftCount"], "draftKeys": pinfo["draftKeys"],
                   "unavailableItems": self.unavailable_items()}
            if self.cands is None:
                return out
            by_id = {c["id"]: c for c in self.cands["candidates"]}
            out["candidates"] = [{"id": cid, "position": i, "index": by_id[cid]["index"],
                                  "overrides": by_id[cid]["overrides"], "summary": self.summary(by_id[cid]["overrides"])}
                                 for i, cid in enumerate(self.cands["displayOrder"])]
            if self.gen3d:
                # G62: 생성 후보 표시. 미리보기 쪽은 GLB를 이 주소로 받는다(webgl·image 플레이어 연결은 남은 일 — 지금은 절차 메시로 그려짐)
                for c in out["candidates"]:
                    a = by_id[c["id"]].get("asset")
                    c["generated"] = a is not None
                    if a is not None:
                        c["asset"] = {"assetId": a["assetId"], "glbSha256": a["glbSha256"],
                                      "glbUrl": f"/api/sessions/{self.s.id}/candidates/{c['id']}/asset.glb"}
                    if by_id[c["id"]].get("origin") == ng.ORIGIN:
                        c["afterNone"] = True              # G73: [맞는 게 없어요] 뒤 만든 후보(화면이 표시)
                default_id = self.cands["generation"]["defaultCandidateId"]
                for c in out["candidates"]:
                    c["default"] = c["id"] == default_id
                out["defaultCandidateId"] = default_id          # 미리 선택할 후보(없으면 null). 확정은 참여자가 한다
                out["defaultFormSource"] = self.data["defaultFormSource"]
                out["formAsset"] = copy.deepcopy(self.data["form"]["asset"])
                ca = self.current_asset()
                # 조절 화면 미리보기가 그릴 생성 메시(형태를 바꾸면 null → 그 형태로 그림)
                out["currentAsset"] = None if ca is None else {
                    "assetId": ca["assetId"], "glbSha256": ca["glbSha256"],
                    "glbUrl": f"/api/sessions/{self.s.id}/candidates/{self.data['form']['asset']['candidateId']}/asset.glb"}
            an = self._after_none()
            if an is not None:
                # G73: 생성 경로 상태(화면: 대기·완료 안내·못 만듦 안내. 사유는 연구자 보기)
                out["afterNone"] = {k: an.get(k) for k in ("status", "blockReason", "error", "candidateId", "noneAt",
                                                            "startedAt", "endedAt", "seconds", "participantSkippedWait",
                                                            "attempt", "seed")}
                out["afterNone"]["timeoutS"] = an["setting"]["timeoutS"]
                ip = an.get("imagePick")
                if ip is not None:
                    # G75: 지금 무엇을 기다리는지(image 그림 그리는 중 · pick 고르는 중 · mesh 고른 그림으로 물체 만드는 중)
                    phase = ("image" if ip["status"] == ng.RUNNING else "pick" if self.stage == "picking"
                             else "mesh" if ip["outcome"] == "picked" else None)
                    out["afterNone"].update(phase=phase, round=ip["round"], rounds=an["setting"]["imagePick"]["rounds"],
                                            imagePickStatus=ip["status"])
                    if self.stage == "picking" and an.get("shapeLlmUsed"):
                        # G82: 그림을 그린 근거 낱말(참여자 원문 그대로, 영어 이름은 보이지 않음)과 [그 말이 아니에요]
                        q = (an.get("shapeLlmItems") or [{}])[0].get("quote")
                        if q:
                            out["llmShapeBasis"] = {"quote": q,
                                                    "text": self.protocol.text("llm_shape_basis").replace("{quote}", q)}
                    if self.stage == "picking":
                        shown = sorted((x for x in ip["images"] if x["shown"]), key=lambda x: x["position"])
                        out["imagePick"] = {"round": ip["round"], "images": [
                            {"position": x["position"],
                             "url": f"/api/sessions/{self.s.id}/selection/image-pick/{ip['round']}/{x['position']}.png"}
                            for x in shown]}
            if self.llm_applied:
                # G77: 조절 화면에서 LLM이 채운 항목마다 근거 인용 안내(참여자 원문 그대로). 참여자가 다른 값으로 바꾸면 보이지 않는다
                tmpl = self.protocol.text("llm_fill_note")
                out["llmFill"] = {"items": {item: {"quote": a["quote"], "text": tmpl.replace("{quote}", a["quote"])}
                                            for item, a in sorted(self.llm_applied.items())
                                            if self.stage != "adjusting" or self._llm_current(item)}}
            out["skipped"] = bool(self.data["selection"] and self.data["selection"].get("skipped"))
            out["axes"] = self.cands["axes"]
            out["note"] = self.cands["note"]
            out["selection"] = self.data["selection"]
            # 범주형 항목에서 표에 없던 말한 값: 화면은 표의 값 목록 뒤에 이 값을 하나 더 붙인다(현재 값 표시용)
            out["adjustExtras"] = {k: v["value"] for k, v in self.extras.items()}
            if self.stage in ("adjusting", "premeasure", "done"):
                params = effective_params(self.spec, self.defaults, self.current)
                out["current"] = {"overrides": dict(self.current), "summary": self.summary(self.current),
                                  "items": {i: self._item_value(i, params) for i in self.items}}
                out["adjustCounts"] = {k: v["count"] for k, v in self.data["adjustments"]["items"].items()}
                out["colorChanged"] = self.data["colorChanged"]
                if self.ring is not None:
                    out["colorRing"] = self._ring_view()          # G79: 고리 그리기(값 표 4.0.0일 때만 키가 있음)
            if self.stage in ("premeasure", "done"):
                out["finalOverrides"] = self.data["finalOverrides"]
                out["sourceCounts"] = self.data["sourceCounts"]
                out["runnerReady"] = self.data["runnerReady"]
                out["runnerBlockers"] = list(self.data["runnerBlockers"])
            if self.stage == "done":
                out["premeasure"] = self.data["premeasure"]
                out["donePhrase"] = self.protocol.text("premeasure_done")
            return out
