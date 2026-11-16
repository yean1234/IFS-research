# 모양어 → 모양 모형 배치 캡처 — held-out 30개

> **입력은 전부 합성 대사입니다.** `docs/validation/e2e/specs/`의 spec 60개(held-out 합성 코퍼스 30개 × 매핑 v0·v1)를 그대로 읽었습니다. 참여자 데이터·실명·연락처는 없습니다. spec 파일은 바꾸지 않았습니다(`git status`에서 `docs/validation/e2e/`·`chatbot/`·`shared/` 변경 0건).
>
> 이 폴더는 Unity 쪽 모양어 매핑(`docs/shape-mapping.md`)을 넣은 뒤 같은 spec을 다시 렌더한 결과입니다. 매핑·채점·spec은 동결 상태 그대로이고, 채점 지표(반영률·`unsupportedRate` 등)는 다시 계산하지 않았습니다.

- 실행 날짜: 2026-11-16
- 기준: 브랜치 `overnight/2026-11-16-imagery-fidelity`, HEAD `686f818` + 커밋하지 않은 작업 트리(이 변경)
- Unity 6000.0.85f2, Built-in RP, Linear, 품질 단계 VR PC(MSAA 4), Direct3D11, 배치 캡처 `ifs-batch-capture/0.1`(형식 그대로, `shape` 필드 추가)

## 실행 명령

저장소 루트에서 시작합니다. `<scratch>`는 저장소 밖 임시 폴더입니다.

```powershell
$U = "C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"
# ① 모양 프리팹 만들기·연결(메뉴 IFS ▸ Create Shape Prefabs와 같음). 두 번 돌려 결과 파일 14개가 바이트 단위로 같음을 확인
& $U -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.ShapePrefabMenu.CreateShapePrefabsBatch -logFile <scratch>\menu.log   # 종료 코드 0
# ② EditMode 테스트
& $U -batchmode -projectPath unity -runTests -testPlatform EditMode -testResults <scratch>\editmode.xml -logFile <scratch>\editmode.log    # 종료 코드 0
# ③ 배치 캡처(-nographics·-quit 없음. -specDir·-outDir 상대 경로는 unity\ 기준)
& $U -batchmode -projectPath unity -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run `
     -specDir ..\docs\validation\e2e\specs -outDir ..\docs\validation\shapes\unity -logFile <scratch>\shapes\capture.log   # 종료 코드 0, 31 s
```

- 실행할 때 같은 `unity/` 프로젝트가 Unity 에디터(대화형)에 열려 있어, 배치모드가 같은 폴더를 쓸 수 없었습니다(프로젝트 잠금). 그래서 `unity/`의 `Assets`·`Packages`·`ProjectSettings`와 `docs/validation/e2e/specs/`를 `<scratch>/mirror/` 아래에 저장소와 같은 상대 배치로 복사하고, 위 명령을 그 안에서 그대로 돌렸습니다(`Library`는 복사하지 않고 새로 가져옴).
- 실행 뒤 복사본과 저장소의 `Assets`·`Packages`·`ProjectSettings`를 `diff -rq`로 비교했습니다. 달라진 것은 `Assets/Prefabs/`(새로 만든 것)과 `Assets/IFS/Scenes/SceneSpecExamples.unity`(SceneLoader 2개에 `shapePrefabs` 연결)뿐이었고, 이 둘과 ③의 결과 폴더를 저장소로 옮겼습니다.
- 새 C# 파일의 `.meta`(GUID)는 실행 전에 저장소에서 만들어 복사본에 같이 넣었습니다. 열려 있는 에디터와 배치 실행이 같은 GUID를 씁니다.
- Unity 로그는 저장소에 넣지 않았습니다(`<scratch>`에만 있음). `report.json`에는 로컬 절대 경로·계정·컴퓨터 이름이 없습니다(`specDir`는 위 상대 경로 그대로).

## 결과

- 로드 60/60, 캡처 실패 0, Console 오류 0, 예외 0, `ok = true`
- 로그의 오류 패턴(`error CS|Shader error|^[\w.]*Exception:|\[Exception\]`) 0건, `[BatchCapture] 끝: ok=True`, 로드 줄 60개
- `chatbot/ifs_chatbot/eval/e2e.py`의 Unity 검사 함수(`compare_applied`·`unity_log_check`·`unity_report_failures`)를 이 `report.json`과 로그에 읽기 전용으로 돌린 결과: 실패 사유 0건, 수치 대조 306개 max |Δ| = 0.0, 범주 불일치 0, `defaultsUsed` 불일치 0

### 모양 모형별 spec 수

| 렌더 결과 | v0 | v1 | 합계 | spec id |
| --- | ---: | ---: | ---: | --- |
| Sphere(모양어 round) | 5 | 5 | 10 | H03 · H13 · H14 · H15 · H26 |
| Cube(square) | 1 | 1 | 2 | H10 |
| FlatCylinder(flat) | 2 | 2 | 4 | H05 · H27 |
| Cone(pointed) | 2 | 2 | 4 | H12 · H19 |
| 모양어 없음(기본 모형, `none`) | 13 | 13 | 26 | H01 · H02 · H04 · H07 · H11 · H18 · H20 · H21 · H23 · H24 · H28 · H29 · H30 |
| 표에 없는 모양어만 있음(`unmapped_shape`, 기본 모형) | 7 | 7 | 14 | H06 · H08 · H09 · H16 · H17 · H22 · H25 |
| 형태 때문에 적용 안 함(`not_applied_form`) | 0 | 0 | 0 | — |
| 합계 | 30 | 30 | 60 | |

- 모양 모형 20개는 모두 프리팹으로 만들었습니다(`viaPrefab = true` 20, 코드 대체 0).
- 표에 있는 모양어 20개(round 10 · flat 4 · pointed 4 · square 2)는 모두 적용됐습니다. 서로 다른 표 모양어가 한 spec에 함께 나온 경우(`conflict`)는 없었습니다.
- `not_applied_form`이 0인 것은 이 코퍼스에서 표에 있는 모양어와 `mist`·`shell`·`fragments`가 한 spec에 함께 나오지 않았기 때문입니다. 이 규칙은 EditMode 테스트로 확인했습니다.
- v0와 v1의 결과는 같습니다. H16(v1 `shell`)·H17(v1 `fragments`)은 매핑에 따라 `form.type`이 다르지만 표에 없는 모양어만 있어 둘 다 `unmapped_shape`입니다.

### 표에 없는 모양어(경고·기록만, 모형은 그대로)

| 모양 값 | 낱말 수 | spec |
| --- | ---: | --- |
| dot | 6 | H17.v0 · H17.v1 (한 spec에 '점' 3번) |
| edge | 6 | H09.v0 · H09.v1 · H22.v0 · H22.v1 · H27.v0 · H27.v1 |
| thin | 6 | H16.v0 · H16.v1 · H25.v0 · H25.v1 · H27.v0 · H27.v1 |
| thread | 4 | H06.v0 · H06.v1 · H26.v0 · H26.v1 |
| hollow | 2 | H16.v0 · H16.v1 |
| long | 2 | H06.v0 · H06.v1 |
| sharp | 2 | H08.v0 · H08.v1 |
| sheet | 2 | H27.v0 · H27.v1 |
| 합계 | 30 | |

H26(thread → round)과 H27(sheet · thin → flat → edge)은 표에 있는 모양어를 적용했고, 표에 없는 낱말은 같은 spec의 `shape.words`에 `unmapped_shape`로 남아 있습니다. 모양어가 나온 spec의 Console 경고 수는 `unmapped_shape` 낱말 수와 같습니다(spec당 0–3개).

### 모양어가 없거나 적용하지 않은 spec은 그대로

모양 모형을 적용하지 않은 40개(`none` 26 + `unmapped_shape` 14)를 동결 증거 `docs/validation/e2e/unity/report.json`과 비교했습니다.

- 60개 모두 `params`·`defaultsUsed`·`inferredUsed`가 같습니다.
- 40개 모두 1차 색 측정의 평균 8비트 sRGB와 덮인 화소 수가 같습니다. 같은 모형이 같은 모습으로 렌더됐다는 뜻입니다(H09.v1은 이전과 같이 형상이 화면에 보이지 않음).
- 40개의 `notes`에서 늘어난 줄은 `unmapped_shape` 경고뿐입니다.

### 눈으로 확인한 PNG

| 파일 | 모형 | 본 것 |
| --- | --- | --- |
| `H10.v0_detail.png` · `H10.v1.png` | Cube | 정육면체. 모서리가 곧고 면 사이 틈이 없음. 거칠기 얼룩만 있고 윤곽은 매끈함 |
| `H12.v0_detail.png` · `H19.v0_detail.png` | Cone | 꼭짓점이 뾰족한 원뿔. 옆면은 매끄럽고 밑면 테두리가 각짐. 바닥에 그림자 |
| `H05.v0_detail.png` | FlatCylinder | 지름보다 두께가 얇은 원판(퍽 모양) |
| `H27.v0_detail.png` | FlatCylinder | `erosion 0.85`로 구멍이 뚫리고 가장자리가 어둡게 삭음 = 침식이 모양 모형에도 반영됨. 다만 `posture = hanging`(y × 1.25)이 겹쳐 원판보다 깡통에 가깝게 보임(`docs/shape-mapping.md` 「한계」) |
| `H03.v0_detail.png` | Sphere | 매끈한 구(기본 모형의 울퉁불퉁한 덩어리와 달리 굴곡 없음) |

## 테스트

- Unity EditMode(배치모드 `-runTests`): **66개 통과 / 실패 0**(이전 28개). 새로 넣은 것은 `ShapeMappingTests` 33개(원뿔 메시·판정 규칙, Unity 없이도 돎)와 `UnityOnly/ShapeModelTests` 5개(팩토리·프리팹 에셋·SceneLoader 적용과 기록)입니다.
- `unity/Tools/compile-check`(dotnet, Unity 없이): 빌드 경고 0·오류 0, 테스트 56개 통과(이전 23개).
- 챗봇 `cd chatbot; .venv/Scripts/python.exe -m pytest -q -m "not live"`: 394개 통과, 14개 제외(live). 파이썬은 바꾸지 않았고 확인용으로 한 번 돌렸습니다.

## 이 폴더의 파일

- `unity/report.json` — 배치 캡처 보고서. spec마다 `shape`(상태·적용 모양·모형·`viaPrefab`·`formType`·`words`), `summary.shapes`(집계), 최상위 `shapePrefabs`(연결된 프리팹 경로). 그 밖의 필드는 이전 형식과 같습니다.
- `unity/<id>.<매핑>.png`·`<id>.<매핑>_detail.png` — 60개 × 2장.
