"""G79-f: 분석용 색 묶음 규칙(자료를 보기 전에 고정, 2026-11-28).

웹 조절 화면이 색상 고리 72칸(값 표 4.0.0)으로 바뀌어 최종 색이 견본 12개보다 잘게 나뉜다. 색끼리 묶어 세어야 하는 분석은
이 함수 하나로만 묶는다. 원 HSL은 기록에 그대로 남고, 이 묶음 이름은 화면·선택 기록·참여자에게 나가는 글에 쓰지 않는다
(원칙 3의 취지 — 시스템이 색 낱말을 주지 않는다). 묶음 id는 값 표의 견본 id(h00–h11)와 같은 꼴이고 색 이름이 아니다.

규칙: s < 0.10이면 "achromatic", 아니면 색상각(h × 360을 0.1° 단위로 반올림)을 가장 가까운 30° 칸(k/12)으로
(정확히 가운데는 위쪽 칸, 360°는 0으로 감김).
"""
from __future__ import annotations

import math

COLOR_BIN_RULE = "ifs-color-bin/0.1.0"
ACHROMATIC_BELOW = 0.10
HUE_BINS = 12
ACHROMATIC = "achromatic"


def color_bin(h: float, s: float) -> str:
    """(h, s) 0–1 → "achromatic" | "h00"…"h11". l은 쓰지 않는다(밝기 묶음은 이 규칙 밖)."""
    if not (isinstance(h, (int, float)) and isinstance(s, (int, float))) or isinstance(h, bool) or isinstance(s, bool):
        raise TypeError(f"h·s는 수여야 합니다: {h!r}, {s!r}")
    if not (0.0 <= h <= 1.0 and 0.0 <= s <= 1.0):
        raise ValueError(f"h·s는 0–1이어야 합니다: {h!r}, {s!r}")
    if s < ACHROMATIC_BELOW:
        return ACHROMATIC
    # 0.1° 단위로 반올림한 뒤 비교: 기록의 h는 소수 넷째 자리라 고리의 가운데 칸(15°·45° … = 칸 3·9·15 …)이 74.988°처럼
    # 위아래로 흩어진다. 반올림하면 정확히 가운데가 되고, 가운데는 위쪽 칸으로 간다
    deg = round(h * 360.0, 1)
    k = int(math.floor(deg / (360.0 / HUE_BINS) + 0.5)) % HUE_BINS
    return f"h{k:02d}"
