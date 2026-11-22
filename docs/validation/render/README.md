# 형상별 렌더 경로 전후 비교 (X64–X72)

`docs/decisions.md`의 "형상 종류별 렌더 경로"(X64–X72)를 구현하기 전(before)과 후(after)의 배치 캡처를 같은 spec 묶음으로 비교한다.

## spec 묶음

- `specs/` — **합성 spec 13개(참여자 데이터 아님).** `make_specs.py`가 손으로 고른 합성 값과 합성 트리거로 만들고 `shared/schemas/scene-spec.v2.1.json`으로 검사한다. 매퍼를 부르지 않는다.
  - 안개 3개(R01–R03): 색·크기가 같고 opacity만 1.0 / 0.6 / 0.15
  - 조각 2개(R04 작음 size 0.4, R05 큼 size 0.7 + 붉은색·거칠기 0.8·침식 0.3)
  - 껍질 1개(R06), 덩어리 2개(R07 기본, R08 초록·밝기 0.8), form null 1개(R09)
  - 모양 모형 4종(R10 round, R11 square, R12 flat, R13 pointed — `_unmapped` 모양어)
- held-out 60개 — `docs/validation/e2e/specs`(v0·v1)를 복사하지 않고 `-specDir`로 따로 지정해 캡처한다. 저장소에는 `report.json`과 형상이 mist·fragments인 spec의 PNG만 둔다(`before/heldout/`, `after/heldout/`).

## 캡처 명령

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath unity \
  -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run \
  -specDir ../docs/validation/render/specs -outDir ../docs/validation/render/before \
  -width 2064 -height 2208 -eyes 2 -warmup 30 -frames 300 -logFile <로그>
# held-out: -specDir ../docs/validation/e2e/specs -outDir <저장소 밖 폴더> → report.json과 mist·fragments PNG만 복사
```

프레임시간은 데스크톱 GPU 대리 측정값이다(Quest 3 실기 아님).
