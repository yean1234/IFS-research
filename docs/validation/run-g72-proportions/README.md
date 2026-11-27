# G72 x·y·z 비율(layout.proportions) — 렌더 확인

2026-11-27, 하위 에이전트 Claude. 「넓게 펼쳐진 안개가 떠오른다」가 둥근 구름으로 그려지던 문제를 SceneSpec 2.4.0의 `layout.proportions`로 고친 뒤, 같은 형상을 비율 없이(2.2.0)·비율 넣어(2.4.0) 찍어 비교했습니다. spec은 모두 합성입니다(참여자 데이터 아님).

## 파일

| 파일 | 내용 |
| --- | --- |
| `specs/H-*.json` | 손으로 쓴 spec. 형상만 말하고 나머지는 모두 null. `.22` = 2.2.0, `.24` = 2.4.0 + 비율 |
| `specs/M-*.json` | 매퍼(scene-spec-builder-v2 2.8.0)가 합성 문장으로 만든 spec. `.22` = 비율 사전 끔, `.24` = 비율 사전 켬 |
| `capture/<spec>.png`, `capture/<spec>_detail.png` | 배치 캡처(전체 화면, 형상 확대) |
| `before_after_sheet.png` | 확대 그림 네 쌍(왼쪽 비율 없음, 오른쪽 비율) |
| `summary.json` | 캡처 보고(report.json)에서 비율 관련 값만 뽑은 것(렌더 경로, 계획의 proportions, 해석값, defaultsUsed, 보이는 화소, 둥근 정도, notes) |

| spec | 형상 | 비율 (x, y, z), axisSaid | 결과 |
| --- | --- | --- | --- |
| H-mist.22 → H-mist-wide.24 | mist | (1, 0.3, 1), 말함 | 둥근 구름 → 넓고 얇게 깔린 안개. 보이는 화소 11,612 → 4,848, 둥근 정도 0.739 → 0.533 |
| M-wide-mist.22 → .24 | 「넓게 펼쳐진 안개가 떠오른다」 | (1, 0.3, 1), 말함 | 22,724 → 9,563, 0.749 → 0.532 |
| H-blob.22 → H-blob-long.24 | 기본 덩어리 | (0.4, 1, 0.4), 말하지 않음 | 세로로 길쭉. defaultsUsed에 `layout.proportions.axis` |
| M-long-stone.22 → .24 | 「길쭉한 돌이에요」 | (0.4, 1, 0.4), 말하지 않음 | 위와 같은 그림(형상 슬롯이 같음) |
| H-frag.22 → H-frag-wide.24 | fragments | (1, 0.3, 1), 말함 | 조각 모양은 그대로, 조각이 놓인 높이 폭만 줄어 옆으로 흩어짐 |

가장 긴 변은 비율과 상관없이 `layout.size`가 정합니다(G62-e). 그래서 비율을 넣으면 보이는 화소는 줄고 가로 폭은 그대로입니다.

## 만든 방법

1. 저장소의 `unity/`는 다른 세션이 에디터로 열고 있어서 열지 않았습니다. `robocopy <repo>\unity <repo 밖>\webgl-build\proj /MIR /XD Library Temp Logs obj UserSettings`로 복사본을 맞춘 뒤(복사본의 Library는 그대로 씀) 그 복사본에서 찍었습니다.
2. 매퍼 spec: `chatbot/.venv` 파이썬으로 `SceneSpecBuilderV2(Analyzer())`(비율 사전 끔)와 `SceneSpecBuilderV2(Analyzer(), proportions_path=shared("lexicon", "scene_params.v2.json"))`(켬)에 같은 문장을 넣어 저장했습니다. 저장한 열 개 spec은 모두 Unity C# 파서(`SceneSpecJson.Parse`·`Validate`)에서 문제가 없었습니다.
3. 캡처:
   ```
   Unity.exe -batchmode -projectPath <repo 밖>/webgl-build/proj -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run \
     -specDir docs/validation/run-g72-proportions/specs -outDir <임시> -width 1032 -height 1104 -frames 10 -warmup 2 -eyes 1 -pngWidth 768 -logFile <로그>
   ```
   종료 코드 0, 31 s. 보고서 `ok` true, 로드 실패·캡처 실패·콘솔 오류·예외 0.
4. 미리보기 플레이어: 같은 복사본에서 `PreviewBuild.BuildWebGLPreview`(→ `<repo 밖>/webgl-build/preview`, 93.8 s, 오류 0·경고 0)와 `PreviewBuild.BuildWindowsPreview`(→ `preview-win`, 19.5 s, 오류 0)로 다시 빌드했습니다. 두 빌드 모두 새 코드 문자열(`longest-edge/1`)이 들어 있음을 확인했습니다. 비교용 `preview-win-cp`와 헤드셋(Android) 빌드는 다시 만들지 않았습니다.

## 확인하지 못한 것

- 헤드셋 안에서 본 모습(입체·가까운 거리). 안개 셰이더는 물체 좌표 레이마칭이라 비균일 배율이 부피를 그대로 늘이지만, 광학 두께는 물체 좌표 걸음으로 재므로 얇게 줄인 축 방향으로 보면 같은 밀도처럼 보입니다(크기를 줄일 때와 같은 동작).
- 덮어쓰기(조절 화면 원값 0.2–2.0)로 비율을 바꾼 그림. 덮어쓰기 해석은 dotnet 테스트로만 확인했습니다.
- 새 빌드로 챗봇 끝에서 끝까지(헤드리스 Chrome).
