# 배치 러너 + 선택 파일 검증 (D8·D9, 합성 자료)

**이 폴더의 모든 파일은 손으로 만든 합성 자료입니다. 참여자 자료가 아닙니다**(AGENTS.md 6). 기록은 자동 시행(합성 입력 `PlacementAutoScript`, `inputSource: auto`, manifest `flags.autoMode: true`)으로 만든 것이고, 효과나 행동의 근거로 쓰지 않습니다.

목적: 챗봇의 후보 선택·조절 단계가 쓰는 선택 파일(`selection.json`, 형식 `ifs-selection/0.1`)을 배치 러너가 원본 spec과 함께 읽어 형상을 만들고, 기록 형식 `ifs-placement/0.2`의 manifest에 선택과 실제로 적용된 덮어쓰기를 남기는지, 그리고 그 기록을 분석기가 읽는지 확인합니다. 챗봇 쪽 산출물이 아직 없을 수 있어 아래 필드 계약대로 손으로 만들었습니다.

## 입력

원본 spec은 저장소의 합성 예시 `unity/Assets/StreamingAssets/IFS/examples/EX02.json`(웅크린 작은 것, 형태·색 미지정)입니다. 기존 자동 시행이 쓰는 것과 같습니다.

| 파일 | 경우 | `selection` | `finalOverrides` |
| --- | --- | --- | --- |
| `inputs/sel_chosen_adjusted.json` | 후보를 고르고 조절함 | `c2`, none false | form.type fragments, opacity 0.85(고름), brightness 0.35·색 h 0.58·s 0.4(고침) |
| `inputs/sel_none_of_these.json` | "맞는 것이 없다"(G23) | null, none true | 기준 후보(0번, 전부 기본값) + brightness 0.3(고침) |
| `inputs/sel_no_overrides.json` | 기준 후보를 고르고 고치지 않음 | `c0`, none false | `{}` |

`sources`는 슬롯별 said / chosen / edited / default를 섞어 넣었고 러너는 해석하지 않고 manifest에 그대로 옮깁니다. `_note`·`candidatesShown`은 러너가 읽지 않는 필드(무시되는지 확인용)입니다.

**`specSha256`은 이 PC에서 체크아웃된 `EX02.json` 바이트의 sha256**(`7d42fd56…cf13`)입니다. 이 저장소는 Windows에서 `core.autocrlf=true`로 체크아웃되어 줄바꿈이 CRLF입니다. 줄바꿈 설정이 다른 곳에서 체크아웃하면 같은 spec이라도 sha가 달라져 러너가 시작을 거부합니다(의도된 동작). 그때는 그 PC의 파일 바이트로 다시 계산해 넣습니다.

### 러너가 읽는 필드(계약)

| 필드 | 러너 |
| --- | --- |
| `formatVersion` | 필수. `ifs-selection/` 접두어가 아니거나 `0.1`이 아니면 경고만 |
| `specSha256` | 필수. 읽은 spec 파일 바이트의 sha256과 다르면 시작 거부 |
| `finalOverrides` | 필수 객체. `SceneOverrideJson.Parse` 형식. 모르는 키·범위 밖·위치·거리 키·적용할 수 없는 키는 시작 거부 |
| `selection.selectedCandidateId` · `selection.none` | 그대로 기록(none true + id 있음은 거부) |
| `sources` | 그대로 기록 |

자세한 규칙은 `unity/README.md` 「배치 실험 러너 ▸ 선택 파일」.

## 재현

Unity는 한 번에 하나, `-nographics` 없이, `-quit` 없이(끝나면 스스로 닫힘). 경로는 저장소 기준으로 바꿔 넣습니다.

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.RunAutoTrialBatch \
  -recordRoot <기록 루트> -specPath <unity 폴더>/Assets/StreamingAssets/IFS/examples/EX02.json \
  -selectionPath <이 폴더>/inputs/sel_chosen_adjusted.json \
  -condition place -participant 11 -logFile <로그>
# 같은 선택 파일로 보기만: -condition view -controlMode static -participant 12
# sel_none_of_these.json: 참여자 13(place)·14(view static), sel_no_overrides.json: 15(place)·16(view static)
```

분석기(chatbot 쪽, 고치지 않음):

```bash
cd chatbot
.venv\Scripts\python.exe -m ifs_chatbot.eval.placement --records <기록 루트> --out <이 폴더>/analysis
```

## 결과 자리

- `records/` — 자동 시행 기록(기록 루트의 `placement/P0xx/EX02/…`를 옮김). manifest에 절대 경로·사용자 이름이 없는지 확인합니다.
- `analysis/` — 분석기 출력.

분석기 `ifs_chatbot.eval.placement`는 manifest `recordVersion`이 `ifs-placement/`로 시작하면 읽습니다. 아는 버전 목록은 `ifs-placement/0.1`뿐이라 0.2 기록에는 `version_mismatch` 플래그가 붙는 것이 예상 동작입니다(분석기는 이번 작업에서 고치지 않음). 분석기는 `selection`·`appliedOverrides`를 읽지 않습니다.

## 결과 (2026-11-23, Unity 6000.0.85f2 배치모드, 자동 시행)

선택 파일 3개 × 두 조건(place, view/static) = 6회 모두 끝까지 돌았다(`summary.json` `completed: true`). 기록은 `records/placement/P011`–`P016`, 분석기 출력은 `analysis/`.

| 참여자 | 선택 파일 | 조건 | manifest `selection` | `appliedOverrides` |
| --- | --- | --- | --- | --- |
| P011 · P012 | `sel_chosen_adjusted` | place · view/static | none false, `c2` | form.type fragments, brightness 0.35, color.h 0.58, color.s 0.4, opacity 0.85 |
| P013 · P014 | `sel_none_of_these` | place · view/static | none true, null | brightness 0.3 |
| P015 · P016 | `sel_no_overrides` | place · view/static | none false, `c0` | `{}` |

- 모든 manifest의 `recordVersion`은 `ifs-placement/0.2`. 사후 평정에 `appearance_match`·`representativeness`(G13 두 문항, draft)가 들어갔다(`ratings.csv`). 기존 `own` 문항도 그대로 있다.
- `events.csv`에 `selection` 한 줄(`file=…;none=…;candidate=…;applied=…`)과 초안 문구 경고(`warning`, 14/14 draft)가 남는다.
- 분석기(`ifs_chatbot.eval.placement`, 고치지 않음)는 6개 세션을 모두 읽었다. 플래그는 세션마다 `version_mismatch;runner_warning:1`이다 — `version_mismatch`는 분석기가 아는 버전이 0.1뿐이라 생기는 예상 동작이고, `runner_warning:1`은 초안 문구 경고(전과 같음). 평정 열은 `rating_appearance_match_post`·`rating_representativeness_post`로 자동으로 생긴다. 분석기는 `selection`·`appliedOverrides`를 읽지 않는다.
- 같은 코드로 선택 파일 없이 기존 자동 시행 5개(EX02: place, view의 static·replay·system_move·point_select)도 저장소 밖 임시 폴더에서 모두 완료됐다(분석기 플래그 `version_mismatch;runner_warning:1`). 이 폴더에는 넣지 않았다.
- 헤드셋에서는 확인하지 않았다(자동 시행·배치모드는 XR을 시작하지 않음).

## ⚠ 챗봇 쪽 선택 파일 스키마와 필드 이름이 다르다

이 러너는 지시받은 계약(위 표: 맨 위 `specSha256`, `selection.selectedCandidateId`, `sources`)대로 읽는다. 같은 시각 작업 중인 챗봇 쪽 초안 스키마 `shared/schemas/selection.v0.1.json`(커밋 전)은 `spec.specSha256`·`spec.fileSha256`(spec 정보가 `spec` 객체 안), `selection.selectedId`, `slotSources`(슬롯마다 객체)를 쓰고 `finalOverrides`에 null을 허용한다. 이 폴더의 합성 선택 파일 3개는 그 스키마를 통과하지 않고, 그 스키마대로 만든 실제 선택 파일은 이 러너가 `specSha256` 없음으로 시작을 거부한다. 어느 쪽에 맞출지는 메인이 정해야 한다(러너가 쓰는 sha는 파일 바이트 sha256이므로 챗봇 쪽 `spec.fileSha256`이 대응한다).

