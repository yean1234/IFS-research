"""구별 프로파일(docs/rq-v4-differentiation-measure.md 3.1) 자기보고 문항 키와 척도 범위.

placement 분석기(평정 범위 점검)와 differentiation 분석기가 함께 쓰는 상수만 둔다.
- 문항 키는 문구 파일 `placement_task*.json`의 `texts` 키(= ratings.csv의 item)와 맞출 이름이다.
  문서의 M1′는 파일 키로 쓸 수 없는 문자(′)가 있어 `M1p`로 적는다.
- 척도 범위는 문서 3.1 표 그대로: M1′·M2·M3은 0–10, P1·P2·S5·S6은 1–7.
  **현재 Unity 배치 러너의 평정 입력은 1–7뿐**이라(unity/README.md 「단계」 표) 0–10 문항은 러너를 고치기 전에는
  헤드셋 안에서 받을 수 없다. 이 상수는 기록 형식(ratings.csv의 rating 숫자)만 정하고 러너 동작은 바꾸지 않는다.
- 문구 자체는 draft이며 IRB 대상이다(AGENTS.md 원칙 7). 여기에는 문구를 두지 않는다.
"""
from __future__ import annotations

# 문서 3.1 최소판 7문항(문서 순서)
PROFILE_ITEMS = ("M1p", "M2", "P1", "M3", "P2", "S5", "S6")

# 문항 → (최소, 최대). 정규화는 (x − 최소) / (최대 − 최소) → 0–1
ITEM_SCALES: dict[str, tuple[float, float]] = {
    "M1p": (0.0, 10.0),
    "M2": (0.0, 10.0),
    "M3": (0.0, 10.0),
    "P1": (1.0, 7.0),
    "P2": (1.0, 7.0),
    "S5": (1.0, 7.0),
    "S6": (1.0, 7.0),
}

# 같은 문항을 다른 문구 파일이 다른 키로 쓴 경우(앞이 우선).
# placement_task.v0.json의 want_to_know·withdraw_attention은 V3의 S5·S6 문구다(그 파일 source 필드).
ITEM_ALIASES: dict[str, tuple[str, ...]] = {
    "M1p": ("M1p",),
    "M2": ("M2",),
    "P1": ("P1",),
    "M3": ("M3",),
    "P2": ("P2",),
    "S5": ("S5", "want_to_know"),
    "S6": ("S6", "withdraw_attention"),
}

DEFAULT_RATING_RANGE = (1.0, 7.0)   # 러너 기본(1–7)


def rating_range(item: str) -> tuple[float, float]:
    """ratings.csv item 키의 허용 범위. 프로파일 0–10 문항만 다르고 나머지는 러너 기본 1–7."""
    return ITEM_SCALES.get(item, DEFAULT_RATING_RANGE)
