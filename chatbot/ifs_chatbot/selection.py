"""면담 뒤 데스크톱 단계: 4 후보 선택 · 5 조절 · 6 사전 측정 (D5·D9 데스크톱 쪽, 결정 G10·G11·G13·G15·G19·G22·G23).

후보 단계는 면담 밖이다. 이 모듈은 LLM·면담 검증기(V1–V9)를 부르지 않는다(원칙 1·3). 입력은 확정 텍스트로 만든
SceneSpec 하나뿐이고(원칙 2), 원본 spec과 그 _provenance는 바꾸지 않는다(G15).

기록(참여자 자료, git 밖): <log_dir>/selection/<sessionId>/
  candidates.json  후보 생성기 출력 그대로(바이트 고정)
  selection.json   ifs-selection/0.1 (shared/schemas/selection.v0.1.json): 원본 spec 해시, 보여 준 후보와 순서, 고른 후보,
                   "맞는 것이 없다" 여부, 조절 이력, finalOverrides(Unity SceneOverrideJson 형식), 슬롯별 출처 네 가지
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

from .candidates import SLOTS, candidates_bytes, effective_params, generate, slot_value, spec_sha256
from .paths import shared
from .scene_builder import dumps as spec_dumps
from .session_log import now_iso

FORMAT_VERSION = "ifs-selection/0.1"
PREMEASURE_VERSION = "ifs-premeasure/0.1"
ITEMS = ("form", "color", "brightness", "opacity", "size", "texture", "motion")
NONE_CHOICE = "none"


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

    def _save(self) -> None:
        if not self.persist or self.data is None:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        self.data["updatedAt"] = now_iso()
        tmp = self.dir / "selection.json.tmp"
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
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
            # 러너 계약: 맨 위 specSha256 = 원본 spec 파일 바이트의 sha256(러너가 읽는 파일과 다르면 시작 거부).
            # 파일을 쓰지 않는 실행(persist_logs = False)에서는 직렬화한 텍스트로 재고 sha256Basis에 적는다.
            if path and Path(path).exists():
                file_sha, basis = hashlib.sha256(Path(path).read_bytes()).hexdigest(), "file"
            else:
                file_sha, basis = hashlib.sha256(spec_dumps(self.spec).encode("utf-8")).hexdigest(), "serialized"
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
                "finalOverrides": None, "sources": None, "sourceDetails": None, "sourceCounts": None, "premeasure": None,
            }
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
                "draftKeys": pinfo["draftKeys"], "previewMode": self.data["preview"]["mode"]})
            return self.view()

    def select(self, choice: str) -> dict:
        """후보 id 하나 또는 "none"(맞는 것이 없다, G23: 기준 후보 0번으로 진행)."""
        with self.lock:
            self._require("selecting")
            order = self.cands["displayOrder"]
            if choice == NONE_CHOICE:
                op = self.cands["candidates"][0]
                sel = {"selectedCandidateId": None, "selectedIndex": None, "none": True, "displayPosition": None}
            else:
                c = self._cand(choice)
                if c is None:
                    raise SelectionInvalid(f"보여 준 후보가 아닙니다: {choice}")
                op = c
                sel = {"selectedCandidateId": c["id"], "selectedIndex": c["index"], "none": False,
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
            if not isinstance(value, str) or value not in it["values"]:
                raise SelectionInvalid(f"{item}: 표에 없는 값입니다: {value!r} (가능: {it['values']})")
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
            self._save()
            return self.view()

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
        chosen = {} if sel["none"] else dict(self._cand(sel["selectedCandidateId"])["axisValues"])
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
        out, counts = {}, {"said": 0, "chosen": 0, "edited": 0, "default": 0}
        for slot in SLOTS:
            said = slot_value(self.spec, slot)
            dv = default_of.get(slot, d.get(slot))
            rec = {"saidValue": said, "chosenValue": chosen.get(slot), "defaultValue": dv}
            if slot in edited:
                rec = {"source": "edited", "value": edited[slot], **rec}
            elif slot in chosen:
                rec = {"source": "chosen", "value": chosen[slot], **rec}
            elif said is not None:
                rec = {"source": "said", "value": said, **rec}
            else:
                rec = {"source": "default", "value": dv, **rec}
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
        """헤드셋 러너가 읽을 것: 원본 spec(바꾸지 않음) + selection.json."""
        with self.lock:
            if self.stage not in ("premeasure", "done"):
                raise SelectionError("조절을 마친 뒤에 최종 형상이 정해집니다([다 고쳤어요] 뒤).")
            return {"sessionId": self.s.id, "spec": self.spec, "selection": self.data}

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
                p.write_text(json.dumps(self.premeasure, ensure_ascii=False, indent=2), encoding="utf-8")
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
            out["single"] = len(self.cands["candidates"]) == 1
            out["axes"] = self.cands["axes"]
            out["note"] = self.cands["note"]
            out["selection"] = self.data["selection"]
            if self.stage in ("adjusting", "premeasure", "done"):
                params = effective_params(self.spec, self.defaults, self.current)
                out["current"] = {"overrides": dict(self.current), "summary": self.summary(self.current),
                                  "items": {i: self._item_value(i, params) for i in ITEMS}}
                out["adjustCounts"] = {k: v["count"] for k, v in self.data["adjustments"]["items"].items()}
            if self.stage in ("premeasure", "done"):
                out["finalOverrides"] = self.data["finalOverrides"]
                out["sourceCounts"] = self.data["sourceCounts"]
            if self.stage == "done":
                out["premeasure"] = self.data["premeasure"]
                out["donePhrase"] = self.protocol.text("premeasure_done")
            return out
