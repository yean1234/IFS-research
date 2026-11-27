# 모의 실행: 면담부터 헤드셋 러너까지 한 바퀴 (G62 생성 형태 · G63 헤드셋 UI, 2026-11-27)

합성 대사만으로 실험 순서를 처음부터 끝까지 한 번 돌리고 단계마다 화면을 찍었습니다. **참여자 데이터는 없습니다.** 코드는 고치지 않았습니다. 세션 로그·selection·Unity 기록은 저장소 밖 임시 폴더에 두었고, 여기에는 PNG와 이 문서만 있습니다.

- 챗봇: `chatbot/config/v4-gen3d.toml`(`[gen3d] enabled = true`, `default_form_source = "auto"`). 이 실행에서 바꾼 설정은 네 가지입니다. 기록 폴더(임시), `preview.mode = "image"`(Windows 미리보기 플레이어), `preview.queue_dir`(임시), `gen3d.assets_dir = <gen3d-out>/g62eval_v2`. LLM·가드는 설정값을 그대로 썼습니다.
  - 면담 LLM은 Ollama `gemma4:e4b`(`sha256:dc35e8d9c606…`, temperature 0.2, seed 7)입니다. 가드는 키워드 사전과 `kanana-safeguard-8b Q4_K_M`(`34ca9739d8a4…`)입니다. 조건 2(chatbot)로 돌렸습니다.
  - 생성 자산은 이미 있던 `g62eval_v2` 사이드카와 GLB를 썼습니다. 형태 생성 모델은 다시 돌리지 않았습니다.
  - 미리보기 플레이어는 `webgl-build/preview-win`의 2026-11-27 03:27 빌드를 썼습니다. 미리보기 코드(`Runtime/Preview`, `FormRenderers.cs`)의 마지막 수정보다 뒤에 만든 빌드라서 다시 빌드하지 않았습니다. 생성 GLB도 그대로 그렸습니다.
- Unity: 6000.0.85f2, 배치모드. 문구 파일은 `placement_task.scaleA.v0.json`입니다. 평정 지시문(`items_instruction`)은 scaleA 파일에만 있어서 이 파일을 골랐습니다. 반복 멈춤은 `stopMode loop`입니다. UI 묶음 `ApplyUiBundle()`을 켜고 직접 배치·보기만(static)을 한 번씩 돌렸습니다. 비교용 묶음 끔 세션은 사전 지시문까지만 진행했습니다.

## 합성 문장(확정 텍스트)

자산 조회 키는 확정 텍스트의 sha256입니다. 그래서 `g62eval_v2` 평가 문장(`inputs/sentences.json`, 합성 예문) 가운데 자산 상태가 ok인 문장을 골랐습니다. 한 줄을 답 하나로 보내고, 줄이 다 떨어진 뒤의 질문에는 "없어요"로 답했습니다. "없어요"는 더 없음(no_more)으로 판정되어 확정 텍스트에 들어가지 않습니다. 그래서 [이대로 맞아요]만 눌러도(고치기 없이) 확정 텍스트가 평가 문장과 바이트 단위로 같아졌습니다.

| 경우 | 평가 문장 | 확정 텍스트(줄 = 답 하나) | `meta.sourceTextHash` |
| --- | --- | --- | --- |
| (가) 사물 | H16(얇은 조개껍데기) | 하늘색 껍데기 같은 게 떠올라요. / 몸 표면에 붙어 있어요. 등 쪽이요. / 속은 텅 비어 있는 느낌이에요. / 조개껍데기처럼 얇고, 반쯤 비쳐요. / 등을 다 덮을 만큼 커요. / 옅은 하늘색이고 은은하게 밝아요. / 거의 안 움직여요. | `a8329df1997e…` (사이드카와 같음) |
| (나) 단순 도형 | H10(상자) | 갈색 나무 상자가 보여요. / 몸 밖에요. 1미터 앞 바닥에 있어요. / 뚜껑이 닫혀 있어요. / 네모반듯한 상자고 나뭇결이 보여요. 표면은 좀 거칠어요. / 한 변이 30센티쯤 돼요. / 짙은 갈색이에요. 조금 어두워요. / 아니요, 안 움직여요. | `3bab298a5a79…` (사이드카와 같음) |

면담자 질문(조건 2, 실제 LLM 출력과 고정 문구, 세션 A):

1. 고정 opening
2. 고정 location
3. LLM "그 '껍데기'는 마치 무엇 같나요?"
4. 고정 focus_hold
5. LLM "그 '조개'는 어떤 '조개'인가요?"
6. LLM "'하늘색'에 대해 더 있나요?"
7. 프로브 movement → 확정

크기·모양과 색·밝기 프로브는 이미 말한 범주라서 건너뛰었습니다. 검증기 재생성은 0번이었습니다.

## 단계별 화면

웹 화면은 헤드리스 Chrome으로 찍은 참여자 화면(`?sid=…&view=participant`, 폭 1440)입니다. Unity 화면은 배치모드 오프스크린 렌더(1280×720)입니다. 판(09–11, 15)은 눈 자리(0, 1.6, 0)에서 판 중심을 세로 시야 28.8°로 찍었고, 장면(12–14, 16)은 같은 눈 자리에서 물체 쪽을 세로 시야 60°로 찍었습니다. 둘 다 데스크톱 근사이고, 헤드셋을 거친 화면은 아닙니다.

| 실험 단계 | 파일 | 보여 주는 것 |
| --- | --- | --- |
| 1 면담 시작 | `01_interview_start.png` | 안내 문구 + 프로토콜 v1.4 첫 질문(opening, G60: "요즘 가장 신경 쓰고 있는 일 가운데 우선순위가 가장 높은 일 하나를 떠올려 주세요. …") |
| 2 면담 진행 | `02_interview_progress.png` | 합성 답 4개 뒤. LLM 질문 "그 '껍데기'는 마치 무엇 같나요?"와 focus_hold |
| 3 확정 텍스트 | `03_confirm_text.png` | 참여자 말을 그대로 모은 7줄, [이대로 맞아요]/[고칠게요]. 같은 대사로 만든 세션 C에서 다시 찍음(아래 「사용한 명령」) |
| 4 형태 후보(가) | `04_candidates_generated_default.png` | 왼쪽 위가 생성 후보(조개껍데기 GLB, 미리 선택된 기본). 나머지 셋은 절차 후보(shell 계열 변형). 생성 메시는 스펙 색(하늘색)·반투명으로 그려짐 |
| 5 속성 조절 | `05_adjust_initial.png` | 생성 후보를 그대로 고른 직후. 미리보기는 생성 메시 |
| 5 속성 조절 | `06_adjust_brightness_edited.png` | 밝기를 한 칸 올림(0.5 → 0.625). 기록 출처는 `edited` |
| (사전 측정) | `07_premeasure.png` | 데스크톱 사전 측정 10문항. 합성 답으로 모두 4 |
| 7 후보(나) | `08_candidates_primitive_box.png` | 단순 도형(상자)이라 절차 메시가 기본(미리 선택 없음, 세션 순환 순서). 생성 상자 후보(받침 달린 작은 상자 모양)는 오른쪽 가운데(4번째)에 대안으로만 나옴 |
| 8 사전 지시문(묶음 켬) | `09_unity_pre_instruction_bundle_on_p1.png` | 어두운 판, 24자 줄바꿈, 쪽 나누기 1/2쪽(판 아래 32.8°) |
| 8 사전 지시문(묶음 켬) | `10_unity_pre_instruction_bundle_on_p2.png` | 2/2쪽(31.7°) |
| 8 비교: 묶음 끔 | `11_unity_pre_instruction_bundle_off.png` | 흰 판, 20자 8줄 한 쪽(39.2°) |
| 9 직접 배치 | `12_unity_place_generated_mesh.png` | 조건 단계에서 자동 입력이 생성 조개껍데기 메시를 잡고 옮기는 중. 판은 직접 배치 지시문 |
| 10 반복 멈춤 | `13_unity_stop_loop_moving.png` | 본 라운드에서 움직이는 중(3.44 m). 고리 숨김, 판은 `stop_distance_loop` |
| 10 반복 멈춤 | `14_unity_stop_loop_paused.png` | 멈춘 상태(1.80 m). 판 아래에 조작 안내 `stop_loop_hint` |
| 11 평정 문항 | `15_unity_post_item_dark_confirm.png` | 사후 첫 문항 A1, 어두운 판, 6 확정 표시(굵은 테두리 `uiRatingConfirmFlash`, 좁힌 기준점 칸) |
| 12 보기만 조건 | `16_unity_view_condition.png` | view/static, 시작 자리(정면 1.5 m, 높이 1.2 m)의 생성 메시와 "지금 이것을 편하게 바라봐 주세요." |

## 6 선택 확정 뒤 selection 기록(세션 A, `selection.json` 발췌)

```text
formatVersion        ifs-selection/0.3
specSha256           7d0d336d95745277d9f0f181e61976b3f3c3fd3fe9e4b239475ba98e9deba58e
defaultFormSource    generated
selection            selectedCandidateId g-12fb0113a71b · displayPosition 0 · none false · skipped false · acceptedDefault true
finalOverrides       {"material.brightness": 0.625}
colorChanged         false
sources              form.type generated_chosen · material.brightness edited · material.color said · material.opacity said
                     · layout.size said · motion.type said · body.part said (나머지 default)
form.asset           assetId 8582775237a9441f · glb form-asset-b523f994e1d05250.glb
                     · glbSha256 b523f994e1d05250d9f3c56a60aa28ad2d47e529e57313fdaa82095d85242437
                     · sidecarSha256 7c9f852b91f6f58a722c63368f05c8a79eda2f6acfd8402f800fe4b13c10937d
                     · pipeline sdxl-triposg · seed 0
                     · promptText "a single thin seashell-like shell, one solid object, matte gray clay, plain white background"
generation           lookupKey a8329df1997e661bd95e6203d35056b95d0601246084a4d1288e3ac49ea13f87
                     · offered [g-12fb0113a71b ← 8582775237a9441f] · rejected []
                     · defaultFormSourceSetting auto · defaultFormSource generated · defaultCandidateId g-12fb0113a71b
                     · defaultFallbackReason null · defaultFormRule non_primitive_stated
                     · defaultFormBasis.words 껍데기[4,7] not_listed · 조개껍데기[58,63] not_listed · 얇[66,67] not_listed
                       (목록 primitive_forms.v0.json 0.1.0, sha256 a77c6da3…)
runnerReady          true
```

세션 B(후보까지만): `generation.defaultFormSource procedural`, `defaultCandidateId null`, `defaultFormRule primitive_stated`, `defaultFormBasis.words` = 상자[6,8] `listed_and_drawn`(절차 `form.base container`, 변형 `profile square`). 생성 후보 `g-49e46aeea19c`(asset `2e63d37c73d8ae13`)는 대안으로만 나왔습니다.

## 13 Unity 기록과 분석기

`RunAutoTrial`과 같은 흐름입니다. 같은 러너에 `BeginAuto(PlacementAutoScript)`, spec·selection 경로, `Check`, `StartSession`, `Tick(0.02)`을 썼습니다. spec은 챗봇이 저장한 `scenes/SYN-G62-A.json`, 선택 파일은 `selection/SYN-G62-A/selection.json`(GLB 같은 폴더)입니다.

- 두 세션 모두 `formAsset.status applied`였습니다. 삼각형 20,000개, 그려진 가장 긴 변 0.4895 m는 절차 모형과 같고(상대 오차 0), 크기는 0.4895 × 0.4857 × 0.0354 m(얇은 판)입니다. 확인 경고는 두 가지였습니다. `layout_ignored`(spec `layout.distance` 0.1, 몸 표면)과 초안 문구 30/30입니다.
- 기록 폴더 `placement/P001/SYN-G62-A/<UTC>/`(place)·`P002/…`(view, static)의 파일은 `events.csv`, `headpose.csv`, `objpose.csv`, `manifest.json`, `placement.json`, `ratings.csv`, `stopdistance.csv`(loop라 헤더만), `stoprounds.csv`, `stopadjust.csv`, `summary.json`, `trajectory.json`입니다. `recordVersion`은 `ifs-placement/0.2`입니다.
- manifest에서 확인한 것: `selection`(formatVersion 0.3, candidate `g-12fb0113a71b`, finalOverrides 밝기 0.625, sources 원문)과 `formAsset`(asset·glbSha256 = glbSha256Actual). `config` 끝에 `ui*` 여섯 개 true, `hidePanelInDistancePhases false`, `stopMode loop` 묶음 키가 있었습니다.
- events(place): `selection` 1, `form_asset` 1(`status=applied;longestM=0.4895`), `items_instruction_page` 7(사전 2쪽, 사후 3쪽 등), `haptic` 19, `stop_round_start/end` 각 5, `rating` 30, `grab`/`release` 2.
- placement.json(place): 놓은 거리 2.6 m, 방위 −20°, 높이 0.9 m. grabCount 2, 확인 있음, conditionCompleted true.
- 분석기 `python -m ifs_chatbot.eval.placement --records <기록>/main --out <임시>/analysis --selection-dir <챗봇 logs>/selection` 결과: 세션 2개(place/none 1, view/static 1), recordVersions `ifs-placement/0.2`(version_mismatch 플래그 없음), 세션 플래그 `stop_unconfirmed:1;runner_warning:2`. 두 세션 모두 `form_source generated_chosen`, `selected_candidate_id g-12fb0113a71b`. `stop_final_mean_m`은 place 1.584·view 1.583(확정 라운드 3개, 4번째 라운드는 자동 입력이 일부러 누르지 않아 `timeout_moving`). `pre_*` 열(사전 측정, protocol 0.5.0)이 채워졌습니다. 경고 5개(초안 문구, autoMode, flags, 조건별 n=1이라 효과크기 null)는 모두 예상한 것입니다.

## 사용한 명령

모두 저장소 밖에서 돌렸습니다. 서버 래퍼·드라이버·Unity 하네스는 이번 실행용 임시 스크립트이고 저장소에 넣지 않았습니다.

1. 서버: `chatbot/.venv` python으로 `load_config("v4-gen3d").with_overrides(...)`(위 네 설정)를 만들고 `create_app(runtime=rt)`를 uvicorn으로 띄웠습니다(127.0.0.1:8797, `docs/validation/ui/tools/ui_server.py`와 같은 방식).
2. 드라이버: 시스템 python(websockets·Pillow)으로 서버 API를 차례로 불렀습니다. `POST /api/sessions {condition: chatbot}` → `start` → `reply`(한 줄씩) → `action confirm` → `candidates` → `selection {defaultCandidateId}` → `adjust {brightness, 0.625}` → `adjust/finish` → `premeasure`(모두 4) → `GET final`. 단계마다 헤드리스 Chrome(DevTools 프로토콜)으로 `/?sid=<id>&view=participant`를 열었고, 미리보기 그림이 다 뜬 뒤 찍었습니다(`docs/validation/ui/tools/ui_shots.py`의 대기 방식).
   - 확정 화면은 처음 찍은 것(세션 A)에서 아래 단추가 잘렸습니다. 그래서 같은 H16 대사로 세션 C를 만들어 창 높이 1240으로 다시 찍었고, 그 뒤 확정했습니다. 같은 seed라 LLM 질문이 같았고 `sourceTextHash`도 같았습니다. 세션 C의 후보 단계는 돌리지 않았습니다.
3. Unity: 화면을 찍으려고 `PlacementUiCapture.CapturePanels`와 같은 방식의 임시 에디터 스크립트를 썼습니다. 이 스크립트는 `Assets/ZzTmp…/Editor/`에 넣었다가 실행 뒤 `.meta`까지 지웠습니다. 기존 캡처 도구는 합성 EX02 spec만 쓰고 선택 파일·반복 멈춤을 받지 않기 때문입니다. 실행은 `Unity.exe -batchmode -projectPath unity -executeMethod G62RunCapture.Run -outDir … -specPath … -selectionPath … -recordRoot … -logFile …`이었고 종료 코드는 0이었습니다. 실행 뒤 `git status`는 실행 전과 같았습니다. `ProjectSettings/QualitySettings.asset`와 `OpenXRPackageSettings.asset`은 다시 쓰이지 않았습니다(배치모드, Play 없음).

## 진행 중 본 결함·이상

1. **조절 화면 형태 줄(05·06).** 생성 메시를 고른 뒤에도 '형태' 줄은 절차 형상 `shell` 썸네일에 체크가 표시되고, 생성 메시를 나타내는 칸은 없습니다. 미리보기(생성 메시)와 선택 표시(절차 모형)가 달라 보입니다. 그 칸을 다시 누를 때 생성 메시가 빠지는지(테스트 `test_form_edit_after_generated_choice_drops_asset`의 동작)는 화면으로 확인하지 않았습니다.
2. **조절 화면 기준값 표시.** 투명도 현재값 0.5가 단계 목록(0.2–1.0)에 없어서 어느 칸도 강조되지 않습니다. 말한 색(하늘색)도 견본에 없어서 색 줄에 표시가 없습니다.
3. **확정 화면(03).** 1440×900 창에서 글상자가 6줄 높이라 7번째 줄이 스크롤 안에 숨고, 아래 단추가 첫 화면 밖으로 밀립니다.
4. **사전 지시문 판과 물체의 겹침(09·11).** 시작 자리의 생성 껍데기(가장 긴 변 0.49 m, 투명도 0.5)가 판 윗부분과 겹칩니다. 묶음 끔(11)에서는 첫 줄 "개를 보여"가 반투명 물체 뒤에 가려 파랗게 보입니다. 묶음 켬(09)에서는 판이 내려가 판 위 가장자리만 겹칩니다. `unity/README.md` 「한계와 사람이 할 일」에 비슷한 문제가 적혀 있지만, 큰 물체에서 글자 자체가 가려지는 것은 이번에 처음 봤습니다.
5. **반복 멈춤 조작 안내 줄바꿈(14).** 안내가 "…확인 버튼: 이 / 자리로 정하기"로 의미 단위 중간에서 끊깁니다.
6. **면담 LLM 질문.**
   - 세션 B의 find 단계는 세 번 모두 V3(인용 3어절 초과, '갈색 나무 상자가 보여요.' 통째 인용)에 걸려 고정 대체 문구로 넘어갔습니다. 검증기는 정상 동작했습니다.
   - 통과한 질문 가운데 어색한 것이 있습니다. "그 '거칠어요'는 어떤 '거칠어요'인가요?"(서술어를 명사 자리 틀에 넣음, 세션 B), "그 '조개'는 어떤 '조개'인가요?"(참여자가 쓴 '조개껍데기'의 일부만 인용, 세션 A).
7. **세션 B 프로브.** 참여자가 '네모반듯한 상자'와 '한 변이 30센티쯤'을 말했는데도 크기·모양 프로브가 나갔습니다(범주가 덮인 것으로 판정되지 않음). 드라이버가 줄이 떨어진 뒤 "없어요"로 답해서, 기록에는 크기 질문에 "없어요"가 남았습니다. 이 답은 드라이버가 만든 것이고 의미상 맞지 않습니다.
8. **미리보기 플레이어 로그.** `player.log`에 OpenXR 초기화 실패(`XR_ERROR_FORM_FACTOR_UNAVAILABLE`, 헤드셋 없음)가 찍힙니다. 렌더와 기록에는 영향이 없었습니다(`preview.shown` image, fallback 없음).
9. **분석기 콘솔 요약.** loop 모드인데 콘솔 한 줄 요약이 "멈춤 거리 평균 None (n=0)"으로 나옵니다. single 지표만 출력하기 때문이고, loop 지표는 CSV·`stopLoop`에만 있습니다.
10. 참고(결함 아님): 세션 B의 생성 상자 후보는 SDXL이 붙인 다리·받침 때문에 작은 의자처럼 보입니다(gen3d-feasibility 한계 5와 같은 종류). auto 규칙대로 절차 메시가 기본이었습니다. 세션 A의 `acceptedDefault`는 밝기를 고쳤어도 true입니다. 형태 후보만 보는 값이라 의도대로입니다.

## 한계

- 헤드셋을 쓰지 않았습니다. Unity 그림은 데스크톱 근사 렌더이고, 직접 배치·멈춤·평정은 자동 입력(`PlacementAutoScript`)입니다. 장면 그림(12)에는 XR 광선이 없습니다.
- 생성 자산은 `g62eval_v2`에 이미 있던 것만 썼습니다. 그래서 확정 텍스트를 평가 문장과 똑같이 맞췄고, 자유 대사로는 생성 후보가 나오지 않습니다.
- 사전 측정·평정 값은 모두 합성입니다(데스크톱 4, 헤드셋은 자동 입력 규칙). 수치 해석에 쓰지 않습니다.
