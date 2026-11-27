# G74 안개 입자 모양(form.mistKind) — 렌더 확인

2026-11-27, 하위 에이전트 Claude. 안개·연기·먼지·구름이 모두 같은 덩어리로 그려지던 문제를 스펙 2.4.0의 선택 슬롯 `form.mistKind`로 나눈 뒤, 같은 문장을 종류 없이(builder 2.8.0)·종류 넣어(builder 2.9.0) 찍어 비교했습니다. 문장은 모두 합성입니다(참여자 데이터 아님). 규칙과 수치는 `docs/scene-spec-mapping.md` 11절.

## 파일

| 파일 | 내용 |
| --- | --- |
| `sheet.png` | 위: 전(2.8.0, 넷 다 같은 덩어리) / 아래: 후(2.9.0, fog · smoke · dust · cloud) — 배치 캡처 확대 그림 |
| `fog_wide_vs_g72.png` | 「넓게 펼쳐진 안개가 떠오른다」: 왼쪽 fog + 비율(이번), 오른쪽 cloud + 비율(G72 그림) |
| `specs/M-*.before.json`, `specs/M-*.after.json` | 매퍼가 만든 spec(`.before` = 비율만 켬, `.after` = 비율 + 종류). `M-5-fog-wide.after` = 비율과 종류를 함께 |
| `capture/<spec>.png`, `capture/<spec>_detail.png` | 배치 캡처(전체 화면, 형상 확대) |
| `summary.json` | 캡처 보고(report.json)에서 뽑은 값(렌더 경로, 계획의 mistKind, 보이는 화소, 둥근 정도, 덩어리 수, 가장자리 폭, notes) |

| spec | 렌더 경로 | 보이는 화소 | 둥근 정도 | 덩어리 수 | 가장자리 폭(px) |
| --- | --- | --- | --- | --- | --- |
| 전(넷 다 같음) | mist | 11,612 | 0.739 | 1 | 12.4 |
| fog 「안개가 껴 있어요」 | mist(`fog5/1`) | 8,819 | 0.719 | 1 | 20.2 |
| smoke 「연기 같은 게 있어요」 | mist(`smoke5/1`) | 9,521 | 0.371 | 1 | 18.8 |
| dust 「먼지구름 같아요」 | mistDust(`dust520/1`) | 4,789 | 0.004 | 33 | 0.8 |
| cloud 「먹구름 같아요」 | mist(`lumps5/1`) | 11,612 | 0.739 | 1 | 12.4 |
| fog + 비율 「넓게 펼쳐진 안개가 떠오른다」 | mist(`fog5/1`) | 11,417 | 0.385 | 1 | 20.4 |

cloud의 후 그림은 전 그림, G72의 `H-mist.22.png`와 PNG가 바이트까지 같습니다(셰이더 프로퍼티 기본값 = 2.4 이전 식). fog·smoke는 가장자리 폭이 넓어졌고(부드러움), smoke는 세로 기둥이라 둥근 정도가 낮고, dust는 알갱이가 흩어져 덩어리 수가 많습니다.

## 만든 방법

1. 저장소의 `unity/`는 에디터가 열려 있어서 열지 않았습니다. `robocopy <repo>\unity <repo 밖>\webgl-build\proj /MIR /XD Library Temp Logs obj UserSettings`로 복사본을 맞춘 뒤 그 복사본에서 찍었습니다(G72와 같은 복사본).
2. 매퍼 spec: `chatbot/.venv` 파이썬으로 `SceneSpecBuilderV2(Analyzer(), proportions_path=P)`(전)와 `SceneSpecBuilderV2(Analyzer(), proportions_path=P, mist_kinds_path=P)`(후), P = `shared/lexicon/scene_params.v2.json`.
3. 캡처:
   ```
   Unity.exe -batchmode -projectPath <repo 밖>/webgl-build/proj -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run \
     -specDir docs/validation/run-g74-mist-kinds/specs -outDir <임시> -width 1032 -height 1104 -frames 10 -warmup 2 -eyes 1 -pngWidth 768 -logFile <로그>
   ```
   종료 코드 0. 보고서 `ok` true, 로드 9/9, 캡처 실패·콘솔 오류·예외 0, 프레임 p95 최대 1.04 ms(데스크톱 대리 측정), 드로콜 추정 최대 5/눈.
4. 미리보기 플레이어: 같은 복사본에서 `PreviewBuild.BuildWebGLPreview`(→ `<repo 밖>/webgl-build/preview`, 오류 0·경고 0)와 `PreviewBuild.BuildWindowsPreview`(→ `preview-win`, 오류 0)로 다시 빌드했고, 두 빌드에 새 코드 문자열(`dust520/1`·`fog5/1`)이 들어 있음을 확인했습니다. 헤드셋(Android) 빌드는 만들지 않았습니다.
5. 수치는 두 번 고쳤습니다(첫 그림에서 smoke가 끊긴 점처럼 흐리고, fog가 납작한 구름처럼 보여서). fog + 비율에서 얇은 층에 걸음 무늬가 생겨, 눌린 덩어리는 타원체 구간으로 걸음을 모으게 했습니다(cloud는 이전 식 그대로).

## 표 0.2.0(메인 판정 뒤)

형상 자리의 '연기·먼지'류가 form.type도 mist로 채우고, 장소 용법('안개 속에')은 form.type을 채우지 않게 됐습니다(`docs/scene-spec-mapping.md` 11절). 위 그림의 spec은 모두 형태가 이미 mist인 문장이라 그림은 같습니다(다시 찍지 않음).

## 확인하지 못한 것

- 헤드셋 안에서 본 모습(입체·가까운 거리). dust 알갱이 크기(물체 좌표 반지름 0.010–0.024)가 헤드셋 해상도에서 보이는지.
- fog(비율 없음)는 여전히 둥근 덩이 몇 개가 보입니다. 넓게 깔린 층에 가까운 그림은 비율(「넓게 펼쳐진」)이 있을 때입니다.
- 열린 에디터의 EditMode 시험(`MistRendererTests` 등 UnityOnly). dotnet 시험(617개)만 돌렸습니다.
- 조절 화면에서 종류를 바꾸는 항목은 만들지 않았습니다(덮어쓰기 키 `form.mistKind`는 Unity가 받음).
