# Unity 적용값 대조(AC-5.7)

입력은 전부 합성 대사에서 만든 spec이다.

- 비교 원천: (나) — Unity report.json params = SceneParams.ToRecord()(소수 4자리, Math.Round 짝수 반올림). 반올림 전 런타임 값 기록이 없어 spec 원값을 같은 규칙(.NET Math.Round(double, 4) 계산 방식)으로 반올림한 뒤 비교했다(docs/acceptance.md AC-5.7 (나)).
- 허용 오차: |Δ| ≤ 1e-06
- 대조한 spec: 60개 · 누락·로드 실패: 0개
- 수치 값 대조: 306개 · max |Δ| = 0.0 · 미달 0건
- 참고: 반올림 전 spec 원값과의 max |Δ| = 0.0(4자리 반올림 오차, 판정에 쓰지 않음)
- 십진 정확 반올림과 .NET 방식 결과가 다른 반올림 경계 사례: 0건
- 0–1 밖이라 잘린 spec 값: 0건
- 범주 값 대조: 87개 · 불일치 0건
- defaultsUsed 불일치(null 슬롯인데 기본값 표시 없음, 또는 그 반대): 0건

## 키별 대조 수

| 키 | 대조 수 | max |Δ| |
| --- | --- | --- |
| material.color.h | 49 | 0.0 |
| material.color.s | 50 | 0.0 |
| material.color.l | 49 | 0.0 |
| material.brightness | 20 | 0.0 |
| material.roughness | 23 | 0.0 |
| material.opacity | 11 | 0.0 |
| material.erosion | 6 | 0.0 |
| layout.size | 38 | 0.0 |
| layout.distance | 9 | 0.0 |
| layout.verticalOffset | 32 | 0.0 |
| motion.speed | 19 | 0.0 |
