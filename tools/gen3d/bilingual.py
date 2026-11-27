"""G73-a 한·영 대역 사전 인터페이스(판·sha256 고정). 형태 자리 명사가 손 형태 사전(shape_prompt_en)에 없을 때만 찾는다.

⚠ 실제 사전(국립국어원 한국어기초사전 대역어 등)은 라이선스·내려받기 형식·필드 확인 전이라 넣지 않았다(G73 '켜기 전에 사람이 할 것').
지금은 이 형식의 파일을 읽는 인터페이스와 합성 시험 표(tools/gen3d/tests/fixtures/bilingual_synthetic.v0.json)만 있다.
실제 사전은 이 형식으로 바꾼 파생 표를 저장소 밖에 두고 경로를 넘긴다. 파일 바이트의 sha256을 기록하고 캐시 키에 넣는다.

형식:
  {"dictId": str, "dictVersion": str, "status": str, "license": str, "source": str,
   "entries": [{"id": str, "ko": str, "translations": [{"en": str}, …]}, …]}
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

_REQUIRED = ("dictId", "dictVersion", "status", "license", "source", "entries")


class BilingualDict:
    def __init__(self, data: dict, sha256: str, name: str | None = None):
        missing = [k for k in _REQUIRED if k not in data]
        if missing:
            raise ValueError(f"대역 사전에 필드가 없습니다: {missing}")
        self.data = data
        self.sha256 = sha256
        self.name = name
        self.by_ko: dict[str, dict] = {}
        for e in data["entries"]:
            if not e.get("id") or not e.get("ko") or not isinstance(e.get("translations"), list):
                raise ValueError(f"대역 사전 항목 형식이 맞지 않습니다: {e!r}")
            if e["ko"] in self.by_ko:
                raise ValueError(f"대역 사전에 같은 표제어가 두 번 있습니다: {e['ko']}")
            self.by_ko[e["ko"]] = e

    @classmethod
    def load(cls, path: str | Path) -> "BilingualDict":
        raw = Path(path).read_bytes()
        return cls(json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest(), Path(path).name)

    def info(self) -> dict:
        d = self.data
        return {"dictId": d["dictId"], "dictVersion": d["dictVersion"], "status": d["status"], "license": d["license"],
                "file": self.name, "sha256": self.sha256}

    def lookup(self, ko: str) -> dict | None:
        """표제어 정확 일치만(어간·부분 일치 없음). 없으면 None."""
        e = self.by_ko.get(ko)
        if e is None:
            return None
        return {"id": e["id"], "translations": [str(t.get("en", "")) for t in e["translations"]]}
