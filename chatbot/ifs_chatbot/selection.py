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

from .candidates import (SLOTS, candidates_bytes, effective_params, form_said_unrendered, generate, rendered_shape_words,
                         said_words, slot_value, spec_sha256, unrendered_shape_words)
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


def _same_value(a, b) -> bool:
    """조절 항목 값 비교. 색은 h·s·l만 본다(견본 id 유무는 무시)."""
    if isinstance(a, dict) and isinstance(b, dict):
        return all(abs(a[k] - b[k]) < 1e-9 for k in ("h", "s", "l"))
    return a == b


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
        "table": {"tableVersion": table["tableVersion"]},
    }


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
                "preview": {k: self.rt.preview.info()[k] for k in ("requested", "mode", "reason")},
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
                "draftKeys": pinfo["draftKeys"], "previewMode": self.data["preview"]["mode"],
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
            keys = self._validate(item, value)
            before = self._item_value(item, effective_params(self.spec, self.defaults, self.current))
            self.current.update(keys)
            after = self._item_value(item, effective_params(self.spec, self.defaults, self.current))
            at = now_iso()
            ev = self.data["adjustments"]["events"]
            ev.append({"i": len(ev), "item": item, "value": after, "previous": before, "at": at})
            summ = self.data["adjustments"]["items"].setdefault(item, {"count": 0, "first": before, "last": before,
                                                                       "firstAt": at, "lastAt": at})
            summ["count"] += 1
            summ["last"], summ["lastAt"] = after, at
            self.data["colorChanged"] = self._color_changed()
            self._save()
            return self.view()

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
        rendered = slot_value(self.spec, "form.type") is None and bool(rendered_shape_words(self.spec, self.table))
        words = said_words(unrendered_shape_words(self.spec, self.table) if unrendered
                           else rendered_shape_words(self.spec, self.table) if rendered else [])
        floor = self.data.get("distanceFloor")
        items = self.table["adjustItems"]["items"]
        final = effective_params(self.spec, self.defaults, self.current)
        edited: dict[str, object] = {}
        for item, summ in self.data["adjustments"]["items"].items():
            if _same_value(summ["last"], summ["first"]):
                continue                                # 만졌지만 처음 값으로 돌아옴 → 출처는 그대로(횟수는 items에 남음)
            for slot in items[item]["slots"]:
                if slot == "material.color":
                    edited[slot] = {k: round(final[f"material.color.{k}"], 4) for k in ("h", "s", "l")}
                elif slot == "material.saturation":
                    edited[slot] = round(final["material.color.s"], 4)
                else:
                    v = final[items[item]["key"]]
                    edited[slot] = round(v, 4) if isinstance(v, float) else v
        d = self.defaults
        default_of = {"material.color": {"h": d["material.color.h"], "s": d["material.color.s"], "l": d["material.color.l"]},
                      "material.saturation": d["material.color.s"]}
        out, counts = {}, {k: 0 for k in SOURCES}
        for slot in SLOTS:
            slot_val = slot_value(self.spec, slot)
            said = slot_val
            if slot == "layout.distance" and floor and floor.get("said") is not None:
                said = floor["said"]            # G33: 원래 말한 값(하한 전). 그려진 값은 value(= 슬롯 값 = 하한)
            dv = default_of.get(slot, d.get(slot))
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
                "adjustCounts": {k: v["count"] for k, v in self.data["adjustments"]["items"].items()}})
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

    def note_preview_fallback(self) -> None:
        """image 모드가 실패해 none으로 바뀌었을 때 한 번 세션 로그 알림으로 남긴다."""
        if self._preview_alerted:
            return
        self._preview_alerted = True
        self.s._alert("preview_fallback", (self.rt.preview.reason or "미리보기 대체")[:300], None)
        if self.data is not None:
            self.data["preview"] = {k: self.rt.preview.info()[k] for k in ("requested", "mode", "reason")}
            self._save()
        self.s._save()

    # ── 화면용 ──────────────────────────────────────────────────────────────
    def summary(self, overrides: dict) -> list[str]:
        """preview none 모드에서 보이는 속성 요약(연구·시험용. 덮어쓰기 키 = 값)."""
        p = effective_params(self.spec, self.defaults, overrides)
        keys = ["form.type", "layout.size", "material.opacity", "material.brightness", "material.roughness",
                "motion.type", "material.color.h", "material.color.s", "material.color.l"]
        return [f"{k} = {round(p[k], 4) if isinstance(p[k], float) else p[k]}" + (" *" if k in overrides else "")
                for k in keys]

    def view(self) -> dict:
        with self.lock:
            pinfo = self.protocol.info()
            out = {"sessionId": self.s.id, "stage": self.stage, "preview": self.rt.preview.info(),
                   "draftCount": pinfo["draftCount"], "draftKeys": pinfo["draftKeys"]}
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
