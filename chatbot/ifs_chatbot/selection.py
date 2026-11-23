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

from .candidates import (SLOTS, base_drawn, candidates_bytes, effective_params, form_said_unrendered, generate,
                         rendered_shape_words, said_words, slot_value, spec_sha256, unrendered_shape_words)
from .paths import shared
from .scene_builder_v2 import floor_record
from .session_log import now_iso

# 0.2(2026-11-23, G31–G34): selection.skipped·skipReason, colorChanged, 출처 값 두 개 추가(said_unrendered_chosen·
# said_unrendered_default), sourceDetails.saidWords, distanceFloor, candidatesShownAt null 허용. 러너는 0.1·0.2를 모두 읽는다.
FORMAT_VERSION = "ifs-selection/0.2"
PREMEASURE_VERSION = "ifs-premeasure/0.1"
ITEMS = ("color", "form", "brightness", "opacity", "size", "texture", "motion")   # G31: 색이 맨 앞(표 adjustItems.order와 같음)
NONE_CHOICE = "none"
SKIP_REASON = "single_distinct_candidate"      # G34: 구별되는 후보가 하나뿐이라 선택 단계를 건너뜀
# 슬롯 출처(G15 네 가지 + G32 두 가지). 러너(PlacementSelection.cs SourceValues)와 스키마 $defs.source가 같은 목록이다.
SOURCES = ("said", "chosen", "edited", "default", "said_unrendered_chosen", "said_unrendered_default")
SAID_NOT_IN_TABLE = "said_value_not_in_table"

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
PREVIEW_CLIENT_EVENTS = ("shown", "fallback")
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


def ui_config(protocol: SelectionProtocol, table: dict, preview_info: dict, enabled: bool) -> dict:
    """웹 화면이 그리는 데 쓰는 고정 정보(문구 원문, 항목 이름, 값 목록). 값에는 이름을 붙이지 않는다."""
    items = table["adjustItems"]["items"]
    labels = protocol.data["adjustItemLabels"]
    adjust = []
    for name in table["adjustItems"]["order"]:
        it = items[name]
        entry = {"id": name, "label": labels[name]["text"], "kind": it["kind"]}
        if it["kind"] == "swatch":
            entry["values"] = [{"id": s["id"], "hex": swatch_hex(s)} for s in it["swatches"]]
        else:
            entry["values"] = list(it["values"])
        adjust.append(entry)
    pm = protocol.data["premeasure"]
    return {
        "enabled": enabled,
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

    # ── 도우미 ──────────────────────────────────────────────────────────────
    @property
    def stage(self) -> str | None:
        return None if self.data is None else self.data["stage"]

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
        if it["kind"] == "swatch":
            hsl = {"h": round(params["material.color.h"], 4), "s": round(params["material.color.s"], 4),
                   "l": round(params["material.color.l"], 4)}
            sw = next((s["id"] for s in it["swatches"]
                       if all(abs(s[k] - hsl[k]) < 1e-6 for k in ("h", "s", "l"))), None)
            return {"swatch": sw, **hsl}
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
        vals = list(it["values"]) if it["kind"] != "swatch" else [s["id"] for s in it["swatches"]]
        if item in self.extras:
            vals.append(self.extras[item]["value"])
        return vals

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
            self.cands = generate(self.spec, self.s.id, self.table)
            scene = self.s.log.data.get("sceneSpec") or {}
            path = scene.get("path")
            # 러너 계약: 맨 위 specSha256 = 저장된 spec 파일 바이트의 sha256(러너가 읽는 파일과 다르면 시작 거부).
            # spec 파일이 없는 실행에서는 null로 두고 runnerReady = false와 이유를 적는다(G26).
            file_sha, basis, self._spec_blockers = self._spec_file_hash()
            now = now_iso()
            meta = self.spec.get("meta") or {}
            self.data = {
                "formatVersion": FORMAT_VERSION, "specSha256": file_sha,
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
                "runnerReady": False, "runnerBlockers": [],
            }
            skip = self.cands["selectionStep"] == "skip"
            if skip:
                # G34: 구별되는 후보가 하나뿐 → 선택 화면을 보이지 않고 그 후보(언제나 0번)로 조절에 들어간다.
                # 고른 것이 아니므로 selectedCandidateId = null, none = false, skipped = true. 보여 준 후보는 없다.
                op = self.cands["candidates"][0]
                self.data["candidatesShown"], self.data["candidatesShownAt"] = [], None
                self.data["selection"] = {"selectedCandidateId": None, "selectedIndex": None, "none": False,
                                          "skipped": True, "skipReason": SKIP_REASON, "displayPosition": None,
                                          "operationalId": op["id"], "operationalIndex": op["index"], "at": now}
                self.data["stage"] = "adjusting"
                self.current = dict(op["overrides"])
            if self.persist:
                self.dir.mkdir(parents=True, exist_ok=True)
                (self.dir / "candidates.json").write_bytes(candidates_bytes(self.cands))
            self._save()
            self._log_event("selection:candidates", {
                "selectionPath": str(self.dir / "selection.json") if self.persist else None,
                "specSha256": self.data["specSha256"], "generatorVersion": self.cands["generatorVersion"],
                "tableVersion": self.cands["tableVersion"], "candidateCount": len(self.cands["candidates"]),
                "axes": [{"slot": a["slot"], "reason": a["reason"]} for a in self.cands["axes"]],
                "displayOrder": self.cands["displayOrder"], "draftCount": pinfo["draftCount"],
                "draftKeys": pinfo["draftKeys"], "previewMode": self.preview_mode,
                "sha256Basis": basis, "adjustValueExtras": sorted(self.extras),
                "selectionStep": self.cands["selectionStep"], "distinctRemoved": len(self.cands["distinct"]["removed"]),
                "distanceFloor": self.data["distanceFloor"]})
            if skip:
                self._log_event("selection:skipped", {"reason": SKIP_REASON,
                                                      "operationalId": self.data["selection"]["operationalId"]})
            return self.view()

    def select(self, choice: str) -> dict:
        """후보 id 하나 또는 "none"(맞는 것이 없다, G23: 기준 후보 0번으로 진행)."""
        with self.lock:
            self._require("selecting")
            order = self.cands["displayOrder"]
            if choice == NONE_CHOICE:
                op = self.cands["candidates"][0]
                sel = {"selectedCandidateId": None, "selectedIndex": None, "none": True, "skipped": False,
                       "displayPosition": None}
            else:
                c = self._cand(choice)
                if c is None:
                    raise SelectionInvalid(f"보여 준 후보가 아닙니다: {choice}")
                op = c
                sel = {"selectedCandidateId": c["id"], "selectedIndex": c["index"], "none": False, "skipped": False,
                       "displayPosition": order.index(c["id"])}
            sel.update(operationalId=op["id"], operationalIndex=op["index"], at=now_iso())
            self.data["selection"] = sel
            self.data["stage"] = "adjusting"
            self.current = dict(op["overrides"])
            self._save()
            self._log_event("selection:selected", {k: sel[k] for k in ("selectedCandidateId", "none", "displayPosition",
                                                                      "operationalId", "operationalIndex")})
            return self.view()

    # ── 5 조절 ──────────────────────────────────────────────────────────────
    def _validate(self, item: str, value) -> dict:
        """(항목, 값) → 덮어쓰기 키:값. 표 밖이면 SelectionInvalid."""
        items = self.table["adjustItems"]["items"]
        if item not in ITEMS or item not in items:
            raise SelectionInvalid(f"조절 항목이 아닙니다: {item} (가능: {', '.join(ITEMS)}). 위치·거리는 조절하지 않습니다(G10).")
        it = items[item]
        if it["kind"] == "swatch":
            sw = next((s for s in it["swatches"] if s["id"] == value), None) if isinstance(value, str) else None
            if sw is None:
                raise SelectionInvalid(f"색 견본 목록에 없는 값입니다: {value!r}")
            return {"material.color.h": sw["h"], "material.color.s": sw["s"], "material.color.l": sw["l"]}
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
        words = said_words(unrendered_shape_words(self.spec, self.table) if unrendered
                           else rendered_shape_words(self.spec, self.table) if rendered else [])
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
        out, counts = {}, {k: 0 for k in SOURCES}
        basis = variant_key_basis(self.spec)
        for slot in SLOTS:
            slot_val = slot_value(self.spec, slot)
            said = slot_val
            if slot == "layout.distance" and floor and floor.get("said") is not None:
                said = floor["said"]            # G33: 원래 말한 값(하한 전). 그려진 값은 value(= 슬롯 값 = 하한)
            # form.baseVariant 기본값 = null(형상 프리셋 기본값, 값 표 defaults에 없음)
            dv = None if slot == "form.baseVariant" else default_of.get(slot, d.get(slot))
            rec = {"saidValue": said, "chosenValue": chosen.get(slot), "defaultValue": dv}
            if slot in edited:
                rec = {"source": "edited", "value": edited[slot], **rec}
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
                rec["saidWords"] = words                               # 원래 말한 모양어(G32)
            if slot == "form.baseVariant" and basis is not None:
                rec["keyBasis"] = basis                                # G38: 키마다 낱말 뜻(lexicon_implied) | 참여자 말(said)
            if slot in FORM_SLOTS and form_item is not None:
                rec["formItem"] = form_item                            # G39: 세 슬롯을 정한 형태 조작(처음·마지막 값·횟수)
            counts[rec["source"]] += 1
            out[slot] = rec
        return out, counts

    def finish(self) -> dict:
        with self.lock:
            self._require("adjusting")
            self.data["adjustments"]["finishedAt"] = now_iso()
            self.data["finalOverrides"] = self._final_overrides()
            self.data["sourceDetails"], self.data["sourceCounts"] = self._slot_sources()
            self.data["sources"] = {k: v["source"] for k, v in self.data["sourceDetails"].items()}   # 러너 계약 필드
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
        return [f"{k} = {round(p[k], 4) if isinstance(p[k], float) else p[k]}" + (" *" if k in overrides else "")
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
            out["skipped"] = bool(self.data["selection"] and self.data["selection"].get("skipped"))
            out["axes"] = self.cands["axes"]
            out["note"] = self.cands["note"]
            out["selection"] = self.data["selection"]
            # 범주형 항목에서 표에 없던 말한 값: 화면은 표의 값 목록 뒤에 이 값을 하나 더 붙인다(현재 값 표시용)
            out["adjustExtras"] = {k: v["value"] for k, v in self.extras.items()}
            if self.stage in ("adjusting", "premeasure", "done"):
                params = effective_params(self.spec, self.defaults, self.current)
                out["current"] = {"overrides": dict(self.current), "summary": self.summary(self.current),
                                  "items": {i: self._item_value(i, params) for i in ITEMS}}
                out["adjustCounts"] = {k: v["count"] for k, v in self.data["adjustments"]["items"].items()}
                out["colorChanged"] = self.data["colorChanged"]
            if self.stage in ("premeasure", "done"):
                out["finalOverrides"] = self.data["finalOverrides"]
                out["sourceCounts"] = self.data["sourceCounts"]
                out["runnerReady"] = self.data["runnerReady"]
                out["runnerBlockers"] = list(self.data["runnerBlockers"])
            if self.stage == "done":
                out["premeasure"] = self.data["premeasure"]
                out["donePhrase"] = self.protocol.text("premeasure_done")
            return out
