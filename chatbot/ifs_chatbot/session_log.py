"""세션 로그 (elicit-log/0.1, 「IFS 이론이란?」 4절).

심사에서 "AI가 답을 유도한 것 아니냐"고 물을 때 내놓는 증거 기록이다.
- 턴 JSON(LLM 출력 전체), 검사 결과, 재생성·대체 여부
- 참여자에게 나가지 않은 시도(보이지 않은 턴)와 걸린 이유
- 가드 판정, 연구자 알림, 확정 텍스트, 추출 미리보기
턴이 끝날 때마다 파일에 다시 쓴다(중간에 꺼져도 남도록). 가명 ID만 쓰고 git에 올리지 않는다.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

LOG_VERSION = "elicit-log/0.1"


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class SessionLog:
    def __init__(self, session_id: str, condition: str, header: dict, log_dir: Path, persist: bool = True):
        self.path = Path(log_dir) / f"{session_id}.json"
        self.persist = persist
        self.data: dict = {
            "logVersion": LOG_VERSION,
            "sessionId": session_id,
            "elicitationCondition": condition,
            "createdAt": now_iso(),
            "endedAt": None,
            **header,                  # protocol / model / guard / analyzer
            "turns": [],
            "alerts": [],
            "capture": {},
            "confirmedText": None,
            "confirmation": None,
            "extraction": None,
            "events": [],
            "endedBy": None,
            "rawSurveyResponseRef": None,
        }

    @property
    def turns(self) -> list[dict]:
        return self.data["turns"]

    def add_turn(self, **fields) -> dict:
        turn = {"i": len(self.turns), "at": now_iso(), **fields}
        self.turns.append(turn)
        return turn

    def add_alert(self, kind: str, detail: str, turn: int | None, severity: str = "warning") -> dict:
        alert = {"at": now_iso(), "kind": kind, "severity": severity, "turn": turn, "detail": detail}
        self.data["alerts"].append(alert)
        return alert

    def add_event(self, kind: str, payload: dict) -> dict:
        ev = {"at": now_iso(), "type": kind, "payload": payload}
        self.data["events"].append(ev)
        return ev

    def end(self, ended_by: str) -> None:
        self.data["endedBy"] = ended_by
        self.data["endedAt"] = now_iso()

    def save(self) -> None:
        if not self.persist:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, self.path)

    def delete(self) -> bool:
        """참여자 철회: 파일을 지운다. 메모리의 내용도 controller가 비운다."""
        existed = self.path.exists()
        if existed:
            self.path.unlink()
        return existed
