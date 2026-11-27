"""사후 면담 기록(RQ3 '자리와 그 뜻', 결정 G59). 연구자가 여는 기록 화면(web/postinterview.js)과 그 API가 쓴다.

모든 평정이 끝나고 헤드셋을 벗은 뒤 실험자가 구두로 묻고 참여자 말을 받아 적는다(몇 문항은 참여자가 직접 적거나 고름).
문항·실험자 규칙은 shared/protocol/post_interview.v0.json(모두 draft)에서만 읽는다. LLM·면담 검증기를 부르지 않는다(원칙 1).

기록(참여자 자료, git 밖): <log_dir>/selection/<sessionId>/postinterview.json — 후보·조절·사전 측정 기록과 같은 세션 폴더.
  ifs-postinterview/0.1: sessionId, condition, protocolId·protocolVersion·draftCount·draftKeys, startedAt·updatedAt,
  parts{free, after_free: {savedAt}}, completedAt(뒤 부분까지 저장하면), items[{id, part, kind, enteredBy, prompt,
  text | choice | value, skipped}] (+ PI3 회차는 round·word, PI6 묶음 항목은 group).
두 부분으로 나눠 저장한다: free(PI1–PI5)를 저장(또는 건너뜀)한 뒤에만 after_free(PI6–PI8)를 받는다 — 평정 묶음의 낱말이
자유 응답을 이끌지 않게(G59).
"""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

from .paths import shared
from .selection import SelectionError, SelectionInvalid, selection_dir
from .session_log import now_iso

FORMAT_VERSION = "ifs-postinterview/0.1"
FILE_NAME = "postinterview.json"
PARTS = ("free", "after_free")
KINDS = ("oral", "oral_repeat", "choice", "typed", "rating_group")
MAX_TEXT = 4000
MAX_WORD_EOJEOL = 3          # PI3의 {X}: 참여자 낱말·짧은 구(면담 검증기의 인용 한도와 같은 3어절)
UI_HIDDEN_KEYS = ("purpose", "legacyOptions")  # 연구자용 문항 목적(G60), 예전 선택지(G66). 기록 화면 설정에 보내지 않는다


class PostInterviewProtocol:
    def __init__(self, name: str = "post_interview.v0.json"):
        p = Path(name)
        self.path = p if p.is_absolute() else shared("protocol", name)
        self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self.protocol_id = self.data["protocolId"]
        self.version = self.data["protocolVersion"]
        self.condition_ids = [c["id"] for c in self.data["conditions"]]
        for it in self.data["items"]:
            if it["kind"] not in KINDS or it["part"] not in PARTS:
                raise ValueError(f"{self.path.name}: 모르는 kind·part: {it['id']}")
            for c in it.get("conditions") or []:
                if c not in self.condition_ids:
                    raise ValueError(f"{self.path.name}: {it['id']}의 모르는 조건 {c}")

    def _entries(self):
        for r in self.data["experimenterRules"]:
            yield f"experimenterRules.{r['id']}", r
        for k, v in self.data["uiPhrases"].items():
            yield f"uiPhrases.{k}", v
        for it in self.data["items"]:
            yield f"items.{it['id']}", it
            if it.get("clarify"):                      # 되물을 때 실험자가 말하는 고정 한 줄(G60, PI1)
                yield f"items.{it['id']}.clarify", it["clarify"]

    def draft_keys(self) -> list[str]:
        return [k for k, v in self._entries() if v.get("status") != "spec"]

    def info(self) -> dict:
        keys = self.draft_keys()
        return {"protocolId": self.protocol_id, "protocolVersion": self.version, "file": self.path.name,
                "draftCount": len(keys), "draftKeys": keys}

    def items_for(self, condition: str, part: str | None = None) -> list[dict]:
        """그 조건에 묻는 문항(순서대로). conditions가 없으면 모든 조건."""
        if condition not in self.condition_ids:
            raise SelectionInvalid(f"모르는 조건: {condition!r} (가능: {', '.join(self.condition_ids)})")
        return [it for it in self.data["items"]
                if (not it.get("conditions") or condition in it["conditions"]) and (part is None or it["part"] == part)]

    def ui(self, enabled: bool) -> dict:
        """기록 화면이 그리는 데 쓰는 것(문항·규칙·조건). 출처·상태도 함께(연구자 화면).
        문항의 purpose(연구자용 '알고 싶은 것', G60)는 보내지 않는다 — 몇 문항은 참여자가 이 화면에서 직접 고르거나 적기 때문이다."""
        items = [{k: v for k, v in it.items() if k not in UI_HIDDEN_KEYS} for it in copy.deepcopy(self.data["items"])]
        return {"enabled": enabled, "protocol": self.info(), "conditions": copy.deepcopy(self.data["conditions"]),
                "parts": copy.deepcopy(self.data["parts"]), "experimenterRules": copy.deepcopy(self.data["experimenterRules"]),
                "uiPhrases": {k: v["text"] for k, v in self.data["uiPhrases"].items()},
                "items": items, "maxWordEojeol": MAX_WORD_EOJEOL, "formatVersion": FORMAT_VERSION}


def _text(v, where: str) -> str:
    if not isinstance(v, str):
        raise SelectionInvalid(f"{where}: 글이 아닙니다: {v!r}")
    v = v.strip()
    if len(v) > MAX_TEXT:
        raise SelectionInvalid(f"{where}: 글이 너무 깁니다({len(v)}자, 최대 {MAX_TEXT}자)")
    return v


class PostInterviewStore:
    """세션 폴더의 postinterview.json을 읽고 쓴다. persist = false(테스트·기록 끔)면 메모리에만 둔다."""

    def __init__(self, protocol: PostInterviewProtocol, log_dir: Path, persist: bool = True):
        self.protocol, self.log_dir, self.persist = protocol, Path(log_dir), persist
        self.lock = threading.RLock()
        self._mem: dict[str, dict] = {}

    def path(self, sid: str) -> Path:
        return selection_dir(self.log_dir, sid) / FILE_NAME

    def load(self, sid: str) -> dict | None:
        with self.lock:
            if not self.persist:
                return copy.deepcopy(self._mem.get(sid))
            p = self.path(sid)
            if not p.is_file():
                return None
            return json.loads(p.read_text(encoding="utf-8"))

    def view(self, sid: str) -> dict:
        rec = self.load(sid)
        return {"sessionId": sid, "record": rec, "path": str(self.path(sid)) if self.persist and rec else None,
                "nextPart": None if rec is None else (None if rec.get("completedAt") else "after_free")}

    def _write(self, sid: str, rec: dict) -> None:
        if not self.persist:
            self._mem[sid] = copy.deepcopy(rec)
            return
        d = self.path(sid).parent
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / (FILE_NAME + ".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n")
        os.replace(tmp, d / FILE_NAME)

    # ── 검사 ────────────────────────────────────────────────────────────────
    def _entry(self, it: dict, responses: list) -> list[dict]:
        """문항 하나의 응답 → 기록 항목들. 없으면 SelectionInvalid."""
        mine = [r for r in responses if r.get("id") == it["id"]]
        base = {"id": it["id"], "part": it["part"], "kind": it["kind"], "enteredBy": it["enteredBy"]}
        kind = it["kind"]
        if kind == "oral_repeat":
            return self._rounds(it, mine, base)
        if kind == "rating_group":
            return self._ratings(it, responses, base)
        if len(mine) != 1:
            raise SelectionInvalid(f"{it['id']}: 응답이 하나여야 합니다(지금 {len(mine)}개, 건너뛰려면 skipped: true)")
        r = mine[0]
        skipped = r.get("skipped") is True
        rec = {**base, "prompt": it["text"]}
        if kind in ("oral", "typed"):
            t = None if skipped else _text(r.get("text"), it["id"])
            if not skipped and not t:
                raise SelectionInvalid(f"{it['id']}: 글이 비었습니다(말하지 않았거나 넘어갔으면 skipped: true)")
            return [{**rec, "text": t, "skipped": skipped}]
        # choice — 화면에 내는 options와, 예전 판의 값을 계속 받기 위한 legacyOptions(화면에 내지 않음, G66 PI7)
        opts = it["options"] + it.get("legacyOptions", [])
        ids = [o["id"] for o in opts]
        ch = None if skipped else r.get("choice")
        if not skipped and ch not in ids:
            raise SelectionInvalid(f"{it['id']}: 선택지에 없는 값입니다: {ch!r} (가능: {ids})")
        text = None if ch is None else next(o["text"] for o in opts if o["id"] == ch)
        return [{**rec, "choice": ch, "choiceText": text, "skipped": skipped}]

    def _rounds(self, it: dict, mine: list, base: dict) -> list[dict]:
        """PI3: 0–maxRounds 회차. 회차마다 참여자 낱말 X(앞서 받아 적은 글에 글자 그대로 있어야 함)와 받아 적은 글."""
        asked = [r for r in mine if r.get("skipped") is not True]
        if len(asked) > it["maxRounds"]:
            raise SelectionInvalid(f"{it['id']}: 최대 {it['maxRounds']}회입니다(지금 {len(asked)}회)")
        if not asked:
            return [{**base, "prompt": None, "round": None, "word": None, "text": None, "skipped": True}]
        return [{**base, "_pending": r} for r in asked]           # X 확인은 앞 문항 글이 모인 뒤(_resolve_rounds)

    def _resolve_rounds(self, items: list[dict], it: dict) -> list[dict]:
        earlier = [e["text"] for e in items if e.get("text") and e["id"] != it["id"] and e["kind"] == "oral"]
        out, n = [], 0
        for e in items:
            r = e.pop("_pending", None)
            if r is None:
                out.append(e)
                continue
            n += 1
            word = _text(r.get("word"), f"{it['id']} {n}회차 낱말")
            if not word:
                raise SelectionInvalid(f"{it['id']} {n}회차: 참여자 낱말(X)이 비었습니다")
            if len(word.split()) > MAX_WORD_EOJEOL:
                raise SelectionInvalid(f"{it['id']} {n}회차: 낱말은 {MAX_WORD_EOJEOL}어절 이하로 넣습니다: {word!r}")
            if not any(word in t for t in earlier):
                raise SelectionInvalid(f"{it['id']} {n}회차: '{word}'는 앞서 받아 적은 참여자 말에 없습니다"
                                       "(참여자가 쓴 낱말만 넣습니다, 원칙 3)")
            text = _text(r.get("text"), f"{it['id']} {n}회차")
            skipped = not text
            out.append({**e, "prompt": it["text"].replace(it["placeholder"], word), "round": n, "word": word,
                        "text": text or None, "skipped": skipped})
            if text:
                earlier.append(text)
        return out

    def _ratings(self, it: dict, responses: list, base: dict) -> list[dict]:
        lo, hi = int(it["scale"]["min"]), int(it["scale"]["max"])
        out = []
        for sub in it["items"]:
            mine = [r for r in responses if r.get("id") == sub["id"]]
            if len(mine) != 1:
                raise SelectionInvalid(f"{it['id']}.{sub['id']}: 응답이 하나여야 합니다(답하지 않으면 value: null)")
            v = mine[0].get("value")
            if v is not None and (isinstance(v, bool) or not isinstance(v, int) or not lo <= v <= hi):
                raise SelectionInvalid(f"{sub['id']}: {lo}–{hi} 정수 또는 null이어야 합니다: {v!r}")
            out.append({**base, "id": sub["id"], "group": it["id"], "prompt": sub["text"], "value": v, "skipped": v is None})
        return out

    # ── 저장 ────────────────────────────────────────────────────────────────
    def save(self, sid: str, condition: str, part: str, responses: list) -> dict:
        if part not in PARTS:
            raise SelectionInvalid(f"모르는 부분: {part!r} (가능: {', '.join(PARTS)})")
        if not isinstance(responses, list) or not all(isinstance(r, dict) for r in responses):
            raise SelectionInvalid("responses는 객체 목록이어야 합니다")
        items_def = self.protocol.items_for(condition, part)
        known = {it["id"] for it in items_def} | {s["id"] for it in items_def if it["kind"] == "rating_group" for s in it["items"]}
        extra = sorted({str(r.get("id")) for r in responses} - known)
        if extra:
            raise SelectionInvalid(f"이 조건({condition})·부분({part})에 없는 문항: {extra}")
        with self.lock:
            rec = self.load(sid)
            if part == "free":
                if rec is not None:
                    raise SelectionError("자유 응답은 이미 저장했습니다(기록을 덮어쓰지 않습니다).")
            else:
                if rec is None or "free" not in (rec.get("parts") or {}):
                    raise SelectionError("자유 응답(PI1–PI5)을 먼저 저장(또는 건너뜀)해야 합니다(G59).")
                if rec.get("condition") != condition:
                    raise SelectionError(f"조건이 앞 부분과 다릅니다(앞: {rec.get('condition')}, 지금: {condition}).")
                if "after_free" in rec["parts"]:
                    raise SelectionError("사후 면담을 이미 다 저장했습니다(기록을 덮어쓰지 않습니다).")
            entries: list[dict] = []
            for it in items_def:
                entries.extend(self._entry(it, responses))
            for it in items_def:
                if it["kind"] == "oral_repeat":
                    prior = list((rec or {}).get("items", []))
                    entries = self._resolve_rounds(prior + entries, it)[len(prior):]
            now = now_iso()
            if rec is None:
                info = self.protocol.info()
                rec = {"formatVersion": FORMAT_VERSION, "sessionId": sid, "condition": condition,
                       "protocolId": info["protocolId"], "protocolVersion": info["protocolVersion"],
                       "draftCount": info["draftCount"], "draftKeys": info["draftKeys"],
                       "startedAt": now, "updatedAt": now, "parts": {}, "completedAt": None, "items": []}
            rec["items"].extend(entries)
            rec["parts"][part] = {"savedAt": now, "answered": sum(1 for e in entries if not e["skipped"]),
                                  "skipped": sum(1 for e in entries if e["skipped"])}
            rec["updatedAt"] = now
            if part == "after_free":
                rec["completedAt"] = now
            self._write(sid, rec)
            return self.view(sid)
