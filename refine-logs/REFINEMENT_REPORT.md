# Refinement Report

**Date**: 2026-11-20 · **Rounds**: 3 / 5 · **Final Score**: 6.45 / 10 · **Final Verdict**: REVISE

## Output Files
- 최종안: `refine-logs/FINAL_PROPOSAL.md`
- 라운드 요약: `refine-logs/REVIEW_SUMMARY.md`
- 점수: `refine-logs/score-history.md`
- 라운드별 안과 검토 원문: `round-0-initial-proposal.md`, `round-1-review.md`, `round-1-refinement.md`, `round-2-review.md`, `round-2-refinement.md`, `round-3-review.md`

## Final Proposal Snapshot
- 주 RQ 하나: 외부화한 내적 경험을 VR에서 직접 배치하는 조건 대 기록된 위치 궤적의 재생을 관찰하는 조건, 사전 보정한 자기보고 분리감.
- 조건 조작은 위치뿐, 문항은 경험과의 관계만 물어 형태에 덜 의존한다.
- 궤적 풀로 조건과 순서를 분리하고, 넘어가는 것은 위치 숫자뿐이다.
- 이번 투고는 설계와 기록·재생 구현, 합성 시나리오 기능 검증까지.

## Pushback / Drift Log
| Round | 검토자 | 응답 | 결과 |
| --- | --- | --- | --- |
| 1 | 형태·닮음 분석 삭제 | 사용자 지정 일반성 조건 때문에 효과 분석이 아닌 적용 범위 기록으로 유지 | 2차에서 적절하다고 인정 |
| 3 | "심리적 거리두기" 공통 구성개념은 과장 | 수용. 조작적 기준으로 낮춤 | 최종안 반영 |

## 선행 연구 검증에서 바뀐 것 (2026-11-20, 하위 에이전트 2회)
- 인터랙션 유무 비교는 이미 있다(Kuang 외 2026 CHI 게재 예정, Shchory 외 2024 Virtual Reality). 새로움 서술을 좁혔다.
- 연구자들이 통제 부족을 직접 적었다(Bell 외 2025, Wagener 외 2024, Kuang 외 2026). 다만 "보기 대 다루기"를 콕 집은 문장은 찾지 못했다.
- 저널(SCIE/SSCI)과 학회 논문이 섞여 있다. Prudenzi 외·Shigyo 외는 전문 미확인.

## Remaining Weaknesses
`FINAL_PROPOSAL.md`의 "남은 위험" 절.

## Next Steps
- 연구자·교수 확정 → 확정되면 `docs/research-design.md`와 `docs/decisions.md`에 반영.
- 구현: 데스크톱 잡기·기록·재생 → 재현 오차 → Quest 3.
- 인용 문헌 원문 대조.
