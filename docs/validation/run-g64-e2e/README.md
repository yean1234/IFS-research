# run-g64-e2e — 합성 대사로 면담 → 확정 텍스트 → SceneSpec → 형상 그림 전 과정 (2026-11-27)

> **입력은 모두 합성 대사다.** 이 실험을 위해 에이전트가 지은 문장이고 실제 사람의 응답이 아니다(AGENTS.md 원칙 6). 위기·자해 내용은 없다.
> 아래 판정 (b)·(c)는 자동 채점이 아니라 **에이전트 한 명이 spec과 PNG를 직접 열어 본 육안 판정**이다. 판정자가 대사를 지은 사람과 같으므로 독립 판정이 아니다.

## 목적

D9 다리 질문(프로토콜 1.5, `config/bridge.toml`)을 지나는 면담부터 절차 메시 형상 그림까지 한 번에 돌려,
말한 형상이 spec과 그림에 제대로 옮겨지는지 본다. 처음에는 절차 메시만 봤고, 생성 메시(G62, `v4-gen3d`) 경로는 아래 「생성 메시 경로」 절에 더했다.

## 환경

| 항목 | 값 |
| --- | --- |
| 저장소 | 브랜치 `claude/emotion-to-imagery-bridge`, HEAD `af71904`. 저장소 코드는 바꾸지 않았다 |
| 면담 설정 | `--config bridge` — 프로토콜 1.5.0, 프롬프트 1.1.0, 검증기 strict·predicate_as_noun, 매핑 v1(세션 안) |
| LLM 조건 ① 실제 | Ollama 0.40.17 `gemma4:e4b` digest `sha256:dc35e8d9c6061baa6f0fa870975ab6932e2542b579b13ea0f199fa4bb7300c9c` (temperature 0.2, seed 7, thinking 끔). 가드 `hf.co/mradermacher/kanana-safeguard-8b-GGUF:Q4_K_M` digest `34ca9739d8a4bcf9127501b114b775af807b48f7ce64befeec115d308c927c69` |
| LLM 조건 ② 모의 | `--backend offline --no-guard-model`(저장소의 오프라인 대역. 실제 LLM 아님) |
| 형태소 분석 | kiwi 0.24.1 |
| spec 매퍼 | v4 설정의 매퍼 v2 `scene-spec-builder-v2/2.4.0`(SceneSpec 2.2.0, ext_lexicon 끔). 비교용으로 세션 안의 v1 spec(`scene-spec-builder-v1/1.2.0`, 2.1.0)도 둠 |
| 렌더 | Unity 6000.0.85f2 에디터 배치 캡처 `IFS.SceneSpec.EditorTools.BatchCapture.Run`(Built-in RP, D3D11, RTX 5080). 절차 메시. 생성 메시는 아래 절(Windows 미리보기 플레이어) |
| 세션 수 | 시나리오 10개 × LLM 조건 2 = 세션 20개. 확정 텍스트가 두 조건에서 10개 모두 같아 spec·그림은 10세트 |

## 방법

1. **시나리오** `scenarios/*.json`(10개). 형식은 `chatbot/scenarios/`와 같고(`config: "bridge"`, `expect`), 답만 `replies` 목록 대신 질문 종류별 `replyBy`로 적었다.
   - 다리를 거치는 세션 7개(b1–b7): 사물 비유 4(b1 젖은 돌덩이, b5 촛불, b6 실타래, b7 유리막), 단순 도형 1(b2 동그란 공), 장면·사람 1(b3), '모르겠어요' 1(b4). X 없는 고정 문구 경로는 b5(계획)·b3·b4(결과적으로).
   - 처음부터 형상을 말해 다리를 건너뛰는 세션 3개(d1 검은 돌덩이, d2 뿌연 안개, d3 덩어리).
   - 속성을 많이 말하는 세션(b1, b2, b7, d1, d2)과 거의 말하지 않는 세션(b4, b6, d3)을 섞었다.
2. **재생** `tools/drive_by_question.py` — `ifs_chatbot.simulate`의 `run()`·지표·`expect` 확인을 그대로 쓰고 `drive()`만 바꾼다.
   처음에 저장소 형식(`replies` 차례대로)으로 돌렸더니 실제 LLM이 flesh_out을 모의 LLM보다 일찍 끝내(`ready_to_advance`) 색 답이 움직임 프로브에 들어가는 어긋남이 생겼다(b2). 그래서 마지막 질문의 `source`·`stage`를 보고 그 종류의 답을 넣는다.
3. **이음매(bridge → v4 매퍼)** `tools/build_v2_specs.py`. bridge 설정은 세션 안에서 매핑 v1만 만들고, v4 흐름(후보·조절·미리보기)은 매핑 v2를 쓴다. 매퍼 입력은 확정 텍스트뿐이므로(`controller._write_scene`) 세션 기록의 `confirmedText`를 v4 설정 Runtime의 `scene_builders["v2"]`에 넣었다. 스키마 검사(`shared/schemas/scene-spec.v2.2.json`)·원칙 검사(`check_principles`)·후보 생성(`candidates.generate`)도 같이 돌렸다.
4. **렌더** spec 20개(v2 10 + v1 10)를 배치 캡처. `images/`에는 v2 그림과, v1과 그림이 다른 b5·b6의 v1 확대 그림만 넣었다.
5. **판정** 세션마다 (a) 다리 질문 (b) 말한 속성 → spec 슬롯 (c) 그림을 육안으로 봤다.

### 명령

```bash
cd chatbot
# ① 실제 LLM(가드 포함)
.venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/drive_by_question.py ../docs/validation/run-g64-e2e/scenarios --config bridge --out <scratch>/live
# ② 모의 LLM
.venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/drive_by_question.py ../docs/validation/run-g64-e2e/scenarios --config bridge --backend offline --no-guard-model --out <scratch>/offline
# ③ 확정 텍스트 → v2 spec(+ 세션 안 v1 spec 복사), 스키마·원칙·후보 요약 출력
.venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/build_v2_specs.py <scratch>/live/sessions <scratch>/specs_live
```

```bash
# ④ Unity 배치 캡처(저장소 루트에서). 종료 코드 0, 20개 16초
"C:/Program Files/Unity/Hub/Editor/6000.0.85f2/Editor/Unity.exe" -batchmode -projectPath unity \
  -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run -specDir <scratch>/specs_live -outDir <scratch>/unity_out \
  -width 2064 -height 2208 -eyes 2 -warmup 10 -frames 60 -logFile <scratch>/capture.log
# ⑤ 슬롯 한눈에 보기
python docs/validation/run-g64-e2e/tools/spec_slots.py docs/validation/run-g64-e2e/specs v2
```

- ①은 47초, ②는 몇 초. 두 조건 모두 `expect` 불일치 0(10/10).
- ③을 다시 돌려 `specs/*.v2.json`과 바이트가 같은 것을 확인했다. 두 조건의 v2 spec도 내용이 같다(확정 텍스트가 같으므로). v1 spec은 `meta.sessionId`만 다르다.
- 세션 기록과 `images/report.json`의 임시 폴더 경로는 `<scratch>`·`<repo>`로 가렸다(그 밖의 내용은 그대로).

## 결과

### 면담

| 지표 | ① gemma4:e4b | ② 모의 |
| --- | --- | --- |
| LLM 턴 | 26 | 27 |
| 첫 시도 통과율 | 0.692 | 0.815 |
| 고정 대체 | 3(b1·d1·d3) | 0 |
| 차단된 시도 | 14 (V7 predicate_as_noun 4, V1 hold_without_risk 3, V2 like_what 3, V7 template_literal 2, V5 novel 2, V3 2) | 6 (V7 predicate_as_noun 6) |
| 확인 문구(soft check) | 1(d1, 가드 모델 S6) | 0 |

V2 like_what 차단 3건은 모두 다리 질문 바로 뒤 flesh_out에서 LLM이 like_what을 다시 쓰려 한 것이다(`blockedTemplateAfter`, 설계대로 막힘).

### 세션별 판정

말한 속성은 형상에 대한 형태·색(밝기)·크기·질감(투명·침식)·움직임(속도)·위치(몸 부위·층)만 셌다(감정어·몸 감각은 세지 않음).
"반영"은 v2 spec 슬롯에 근거 낱말과 함께 들어갔거나(`_provenance`), 슬롯 밖이라도 Unity가 그 낱말로 그렸거나(b2 모양어), 부정을 부정으로 기록한 것(b7).
"무단 채움"은 참여자 말에 근거가 없는 슬롯 값이다. `_inferred`(3층 V/A/D 제안)는 Unity가 쓰지 않으므로(`inferredUsed` 0) 세지 않았다.

| 세션 | 첫 발화 | 다리 (a) | 말한 → 반영 (b) | 빠진 것 | 무단 채움 | 그림 (c) |
| --- | --- | --- | --- | --- | --- | --- |
| b1_object_rich | 그 일을 생각하면 걱정이 앞서요 | 나감 「그 '숨'은 마치 무엇 같나요?」 → "물에 젖은 돌덩이 같아요" | 8 → 6 | 돌덩이(형태), 젖은 | 0 | **맞음** — 짙은 회색의 거친 작은 덩어리로 돌덩이처럼 읽힘. 단 형태는 말한 '돌덩이'가 아니라 기본값 blob 덕 |
| b2_shape | 막막해요 | 나감 「그 '뻐근'은 마치 무엇 같나요?」 → "동그란 공 같아요" | 7 → 7 | — | 0 | **맞음** — 작고 매끈한 파란 구('동그란' → Sphere 모형) |
| b3_scene_people | 부담스러워요 | 나감(X 없음) 「지금 그것은 마치 무엇 같나요?」 → "사람들이 저를 빙 둘러서 쳐다보는 것 같아요" | 5 → 2 | 사람들(제외 범주, 설계상), 여러 명·빙 둘러(슬롯 없음) | 0 | **안 맞음(설계상)** — 조금 어두운 회색 덩어리. 사람 형상은 그리지 않는 범주 |
| b4_dontknow | 그냥 피곤해요 | 나감(X 없음) → "모르겠어요", flesh_out 건너뜀 | 1 → 1 | — | 0 | **해당 없음** — 형상을 말하지 않았는데 기본 밝은 회색 덩어리가 그려짐(spec 형상 슬롯은 모두 null, Unity 기본값) |
| b5_plain_flame | 설레요 | 나감(X 없음, 계획대로) 「지금 그것은 마치 무엇 같나요?」 → "작은 촛불 같아요" | 5 → 4 | 흔들려요(움직임) | 0 (왜곡 1) | **맞음** — 작은 노란 불꽃 윤곽(form.base flame). 움직임 왜곡은 정지 그림에 안 보임 |
| b6_tangle_sparse | 짜증이 나요 | 나감 「그 '짜증'은 마치 무엇 같나요?」 → "엉킨 실타래 같아요" | 3 → 3 | — | 0 (사전 함의 1) | **맞음** — 가는 회색 선이 엉킨 실타래(form.base line, tangle) |
| b7_glass_negation | 불안해요 | 나감 「그 '불안'은 마치 무엇 같나요?」 → "얇은 유리막 같아요" | 8 → 7 | 얇은(모양 모형 없음) | 0 | **부분** — 투명한 반구 껍질(shell, opacity 0.1). 유리막으로 읽힐 수 있으나 화면에서 거의 안 보이고(maxAlpha 0.19) '얇은 막'보다 그릇 모양 |
| d1_stone_rich | 가슴에 검은 돌덩이가 얹혀 있는 느낌이에요 | 건너뜀(첫 발화에 형상 신호 '검') | 7 → 3 | 돌덩이(형태), 차갑(온도 슬롯 없음), 단단(값 없음), 커지는(값 없음) | 0 | **맞음** — 검은 거친 덩어리로 돌덩이처럼 읽힘(형태는 기본값 덕, 커짐은 안 보임) |
| d2_mist | 머릿속에 뿌연 안개가 껴 있어요 | 건너뜀(첫 발화 '뿌옇'·'안개') | 7 → 7 | ('모였다'는 scattering 하나로 합쳐짐) | 0 | **맞음** — 회색 안개 덩이(붉은 기가 도는 회색) |
| d3_lump_sparse | 배 쪽에 뭔가 덩어리가 있어요 | 건너뜀(첫 발화 '덩어리') | 2 → 2 | — | 0 | **맞음** — 기본 회색 덩어리 |

슬롯별 근거 낱말은 `tools/spec_slots.py`로 볼 수 있다. b5의 왜곡은 아래 결함 3, b6의 사전 함의는 실타래 → `form.baseVariant.gauge = thin`(`lexicon_implied`)이다.

### 핵심 수치

| 지표 | 값 | 주의 |
| --- | --- | --- |
| 다리가 기대대로 나감/건너뜀 | 10/10 (다리 세션 7개 모두 나감, 형상 시작 3개 모두 건너뜀) | X 있는 문장 4(b1·b2·b6·b7), X 없는 고정 문구 3(b3·b4·b5). b3·b4는 X를 기대했으나 고정 문구로 감(아래 관찰 2) |
| 다리 뒤 참여자가 형상 표현을 낸 세션 | 6/7 | **대본으로 정한 값이다**(b4만 '모르겠어요'). 다리 질문의 효과가 아니다. 시스템이 그 6개의 다리 답에서 형상 신호를 잡은 비율은 6/6(`firstElicitedBy = bridge`) |
| 말한 속성의 spec 반영 | 42/53 = 0.79 | 빠진 11개: 사전 밖 합성어 '돌덩이' 2, 슬롯·값 없음 5(여러 명·빙 둘러·차갑·단단·커지는), 같은 슬롯 충돌에서 짐 2(젖은 → 거칠어요에 밀린 roughness 대안, 흔들려요 → 두근거려요에 밀린 motion 대안), 제외 범주 1(사람), 모형 없는 모양어 1(얇은). 설계상 그리지 않는 '사람'을 빼면 42/52 |
| 말하지 않았는데 슬롯이 채워진 것 | 0 | 다른 대상의 말이 들어간 왜곡 1(b5), 사전 함의 1(b6) |
| 그림 '맞음' | 7/10 (형상을 말하지 않은 b4를 빼면 7/9) | 부분 1(b7), 안 맞음 1(b3, 설계상), 해당 없음 1(b4). '맞음' 7개 중 b1·d1은 형태 낱말이 안 잡혔는데 기본 blob이 우연히 돌덩이처럼 보인 것 |
| Unity | 20/20 로드, 콘솔 오류·예외 0, `inferredUsed` 0, frameMsP95 최대 3.1 ms | 데스크톱 대리 측정 |
| spec 검사 | 스키마 오류 0, 원칙 검사 문제 0(10/10) | |

## 발견한 결함·관찰 (고치지 않음)

1. **'돌덩이'가 형태로 잡히지 않고, 후보 단계에서 형태가 빈 자리로 열린다.** b1·d1에서 `돌덩이`는 `_unmapped` `unlisted_noun`(no_scene_param)이고 `form.type`은 null이다. 사전에는 `돌 → blob`(`shared/lexicon/scene_params.v1.json:82`)과 `덩어리 → blob`(`shared/lexicon/layer1_lexicon.v0.json:259`)이 있지만 합성어 `돌덩이`는 없다. 그래서 `candidates.slot_is_open`(`chatbot/ifs_chatbot/candidates.py:189`)이 형태 자리를 `empty`로 보고 v4 후보에 `form.type: mist`(안개)를 넣는다. 말한 단단한 형상에 말하지 않은 안개 후보가 붙는다. 재현: 확정 텍스트 `가슴에 검은 돌덩이가 얹혀 있는 느낌이에요` → v2 spec → `candidates.generate` 후보 2·3.
2. **차원 프로브 '이미 나옴' 판정(1층 사전 범주)과 매퍼 v2의 값이 어긋난다** (`chatbot/ifs_chatbot/controller.py:745`).
   - d1: `커지는`이 사전에서 size 범주(`shared/lexicon/layer1_lexicon.v0.json:252`, value growing)라 크기 프로브를 건너뛰었는데, 매퍼는 `no_value_mapping`이라 `layout.size`가 비었다. 크기를 물을 기회가 사라졌다.
   - b1: `주먹만 하고`는 매퍼 v2 phrase_rule로 크기 0.333이 되지만 1층 사전 범주가 아니라 크기 프로브 「그것에 크기나 모양이 있나요?」가 다시 나갔다(중복 질문).
3. **형상이 나오기 전의 몸 감각이 형상의 움직임 슬롯을 차지한다** (b5). focus_hold 답 `두근거려요`(형상 없을 때의 몸 감각)가 `motion.type = pounding`이 되고, 촛불에 대해 말한 `흔들려요`는 `_alternatives`(reason `later_mention`)로 밀렸다(`chatbot/ifs_chatbot/scene_builder_v2.py:1112`, 먼저 나온 말이 이김). 말한 낱말이라 원칙 2 위반은 아니지만 다른 대상의 말이다. 재현: 확정 텍스트 `설레요 / 몸 주변이요 / 두근거려요 / 작은 촛불 같아요 / 노랗게 흔들려요`.
4. **'회색'이 붉은 기가 도는 회색으로 그려진다.** `회색 → hsl [0, 0.05, 0.45]`(`shared/lexicon/scene_params.v1.json:175`, `layer1_lexicon.v0.json:146`)라 hue 0(빨강)·채도 0.05가 남아 spec sRGB가 (0.473, 0.428, 0.428)이다. d2 안개는 자줏빛 회색, b1 '짙은 회색'은 갈색 기가 보인다. spec을 충실히 그린 결과이고 원인은 사전 값이다.
5. **투명을 말하면 형상이 거의 안 보인다** (b7). `투명 → material.opacity 0.1`이고 shell 렌더의 maxAlpha가 0.19라 1.2 m 거리 전체 그림에서 형상을 찾기 어렵다. AC-4.5(빈 화면 없음) 쪽 위험.
6. **가드 모델 오탐으로 확인 문구가 나갔다** (d1, 실제 LLM 조건만). 첫 발화 `가슴에 검은 돌덩이가 얹혀 있는 느낌이에요`에 Kanana가 S6을 내 「지금 계속 이야기해도 괜찮으신가요?」가 나갔다. 위기 경로는 아니고 [계속]으로 이어졌다.
7. **퍼지 매칭 잡음.** `바닥으로 → 바삭`(b1, roughness), `가끔 → 가슴`(b7, body.part)이 `_needsConfirmation`·`_alternatives`에 남았다. 슬롯 값은 아니다.

### 관찰(결함 아님)

1. 실제 LLM은 다리 답 직후 flesh_out을 바로 끝내기도 한다(b2 `ready_to_advance`, 질문 0개). 이때 크기·색·움직임은 고정 프로브가 받아 확정 텍스트는 모의 LLM 조건과 같아졌다.
2. 다리 X 선택: b3은 focus_hold `긴장돼요`의 '긴장'이 감각이 아니라 감정 범주라 후보가 아니고(focus_hold에서는 sensation만 봄), opening `부담스러워요`의 '부담'은 사전 범주가 없어 X 없는 고정 문구로 갔다. b4의 '피곤'·'멍'도 사전 범주가 없다. b2의 「그 '뻐근'은 마치 무엇 같나요?」처럼 '-하' 어근을 명사 자리에 넣은 문장은 규칙대로지만 한국어로 어색하다.
3. 형상을 말하지 않은 b4도 v4 후보 단계에서 형태(blob/mist)×크기 후보 4개가 나온다(빈 자리만 벌리는 G16 설계). b3의 '사람'은 `excluded_shape`이고 후보 축은 `said_unrendered`다.
4. bridge 설정의 세션 안 매핑(v1)으로는 촛불·실타래가 기본 덩어리로 그려진다(`images/*.v1_detail.png`). 기본 형상(form.base)은 v4의 매핑 v2에서만 나온다. bridge로 면담하고 v4 흐름에 넘기려면 이 이음매가 필요하다.

## 한계

- 대사를 지은 사람과 판정한 사람이 같은 에이전트다. 사전에 어떤 낱말이 있는지 일부러 맞추지 않으려 했지만 대사 선택이 결과에 영향을 줬을 수 있다. 세션 10개, 반복 1회.
- (b)의 "말한 속성" 범위와 (c)의 판정은 한 사람의 해석이다. 크기는 확대 그림(`_detail`)이 형상마다 다르게 잘려 비교하기 어렵다.
- 그림은 정지 화면이라 움직임(motion.type·speed)은 확인하지 못했다.
- 조건 1(정적 프롬프트)은 돌리지 않았다. 모의 LLM 조건은 저장소의 오프라인 대역이고 실제 모델이 아니다.
- 질문 종류별 답 주입(`drive_by_question.py`)은 실제 참여자가 질문을 읽고 답하는 것을 흉내 낸 것일 뿐이다. 모순 없는 답이 들어가도록 만든 장치라 실제 대화의 어긋남은 재현하지 않는다.
- 후보·조절·사전 측정 화면과 WebGL 미리보기는 거치지 않았다. 후보는 `candidates.generate`로 개수·축만 확인했다.

## 생성 메시 경로(G62, `v4-gen3d`) — 2026-11-27 추가

처음 범위(절차 메시만)를 넓혀, 같은 10개 확정 텍스트로 형태 생성기(SDXL → TripoSG)를 돌리고 `v4-gen3d` 설정의 기본 후보 판정(G62-h·i, `default_form_source = "auto"`)을 기록했다. 기본 후보가 생성 메시인 세션은 그 메시로 다시 그렸다. 판정은 위와 같이 에이전트 한 명의 육안 판정이다.

### 환경·명령

- 가중치는 이 PC에 이미 있었다(HF 캐시: SDXL base 1.0 `462165984030…`, TripoSG `2c1c516d22d5…`·코드 `fc5c40990181`, CLIP ViT-L/14 `32bd64288804…`, rembg `~/.u2net/u2net.onnx`). 새로 받은 것은 없다. 모델·리비전·seed(0)·틀·관문은 저장소 기본값 그대로(`g62-template/0.2.0`, `g62-gate/0.2.0`, `g62-post/0.1.0`, 사전 `shape_prompt_en` 0.2.0). 프롬프트는 규칙만(LLM·번역 없음).
- 생성 전에 Ollama의 두 모델을 내렸다(VRAM 16 GB에서 SDXL 12.5 GiB와 겹치지 않게). 다음 요청 때 다시 올라온다.

```bash
# ⑥ 입력: <repo>/../gen3d-out/g64e2e/inputs/sentences.json = 세션 10개의 confirmedText(실제 LLM 조건 세션, 모의 조건과 같음)
../gen3d-venv/Scripts/python tools/gen3d/generate.py --run g64e2e --pipeline sdxl-triposg          # 132 s, 종료 코드 0
# ⑦ v4-gen3d 후보·기본 판정 + Windows 미리보기 플레이어(PreviewQueue, 2026-11-27 03:27 빌드)로 0번 절차 후보·생성 후보 그림(640×480)
cd chatbot
.venv/Scripts/python.exe ../docs/validation/run-g64-e2e/tools/gen3d_candidates.py \
    --render "<repo>/../webgl-build/preview-win/IFSPreview.exe" --queue <scratch>/pq
```

- ⑦은 선택 흐름(`SelectionFlow.start`)과 같은 순서로 부른다: `candidates.generate` → `FormAssetStore.lookup_for_spec` → `judge_default`(auto) → `add_generated`. 자산 폴더는 설정값 그대로 `<repo>/../gen3d-out` 전체(사이드카를 확정 텍스트 sha256으로 찾음). 미리보기 모드 none 규칙은 건너뛰었다.
- 그림은 플레이어가 spec 값(색·밝기·투명도·크기)에 생성 GLB(가장 긴 변 1.0 정규화)를 얹어 그린 것이다. 비교를 위해 절차 메시(0번 후보)도 같은 플레이어로 다시 찍었다(`images/gen3d/<id>.proc.png`, `<id>.gen0.png`).
- GLB는 저장소에 넣지 않았다(각 약 0.36 MB). `<repo>/../gen3d-out/g64e2e/g62-sdxl-triposg/assets/`에 있고 sha256은 아래 표. 사이드카·run.json·생성 로그 요약은 `gen3d/`에 경로를 가려 복사했다.

### 세션별 결과

| 세션 | 규칙 프롬프트(영어 원문) · 낱말별 근거 | 생성 / 막힘 | 기본 후보(`defaultFormRule`) | 생성 메시 그림 판정 | 생성 시간 |
| --- | --- | --- | --- | --- | --- |
| b1_object_rich | — (형태 낱말 없음: '돌덩이' 미인식) | 막힘 `no_shape_stated` | 절차 (`no_generated_candidate`) | — (절차: 맞음, 기본 blob 덕) | — |
| b2_shape | `a single round ball, …` · round ← 동그란[26:29], ball ← 공[30:31] | 생성 `cd261b4009896239` (GLB sha256 `12343b2c4fd7…`, 관문 person 0.015·match 0.238, 성분 1) | 절차 (`primitive_stated`: 동그랗·공 모두 단순 도형, 절차가 그림) | 맞음 — 매끈한 파란 구, 절차 구와 거의 같음(표면 잔무늬만). 기본이 아닌 대안 후보 | 30.1 s |
| b3_scene_people | — | 막힘 `excluded_category` (person: 사람) | 절차 (`no_generated_candidate`) | — | — |
| b4_dontknow | — | 막힘 `no_shape_stated`(형태를 말하지 않음) | 절차 (`no_generated_candidate`) | — | — |
| b5_plain_flame | — | 막힘 `excluded_category` (nonMeshable: form.base=flame, 촛불) | 절차 (`no_generated_candidate`) | — (절차 불꽃: 맞음) | — |
| b6_tangle_sparse | `a single tangled ball of yarn, …` · tangled ← 엉킨[24:26], ball of yarn ← 실타래[27:30] (thinRisk) | 생성 `4df20acebef16028` (`5401eeb390b1…`, person 0.040·match 0.219, 성분 1) | **생성** (`non_primitive_stated`: 엉키·실타래 목록 밖) | 부분 — 공 모양 실뭉치로 읽히나 가닥이 표면 홈으로 뭉개져 '엉킨' 느낌이 약하다. 절차(엉킨 선)가 말에 더 가깝다. 말하지 않은 세부 없음 | 33.9 s |
| b7_glass_negation | `a single thin broken object, …` · thin ← 얇[24:25], broken ← 깨질[43:45] (명사 '유리막'은 빠지고 틀의 object) | 생성 `f5ad8e8953a7f430` (`ac2d278f8145…`, person 0.124·match 0.250, 성분 1) | **생성** (`non_primitive_stated`: 얇·깨지 목록 밖) | 안 맞음 — 이미 깨진 V자 조각(말하지 않은 '깨진 들쭉날쭉한 파편'). '막'이 아니다. opacity 0.1이라 화면에서 거의 안 보임 | 26.6 s |
| d1_stone_rich | — (형태 낱말 없음: '돌덩이' 미인식) | 막힘 `no_shape_stated` | 절차 (`no_generated_candidate`) | — (절차: 맞음, 기본 blob 덕) | — |
| d2_mist | — | 막힘 `excluded_category` (nonMeshable: form.type=mist, 안개) | 절차 (`no_generated_candidate`) | — | — |
| d3_lump_sparse | `a single lump, …` · lump ← 덩어리[8:11] | 생성 `8b5b0f7f7bd5b164` (`1a253d859cc9…`, person 0.066·match 0.213, 성분 1). 같은 키가 `g62eval_v2`에서 이미 만들어져 캐시 사용(모델 호출 없음) | **생성** (`non_primitive_stated`: 덩어리 목록 밖 — G62-i에서 '덩어리' 미결정) | 부분 — 덩어리로 읽히나 말하지 않은 깊게 팬 홈·잘린 면이 있다. 절차 blob(맞음)보다 세부를 지어냄 | 30.5 s(이전 실행 기록) |

생성 시간 = 이미지 + 배경 제거 + TripoSG + 후처리 + 관문(모델 적재 제외). 실행 전체(적재 포함) 131.9 s, VRAM 최대 이미지 12.5 GiB·형태 5.8 GiB. 모든 사이드카 `form-asset.v0` 스키마 문제 0.

### 핵심 수치(생성 경로)

| 지표 | 값 |
| --- | --- |
| 생성 GLB | 4/10 (모델 호출 3 + 캐시 1). 관문 차단 0, 생성 실패 0 |
| 규칙 단계 막힘 | 6/10: 설계대로 4(사람 b3, 불꽃 b5, 안개 d2, 형태 안 말함 b4), 사전 빈틈 2(b1·d1 '돌덩이') |
| 기본 후보 | 생성 3(b6·b7·d3), 절차 7(그중 b2는 생성 후보가 있으나 `primitive_stated`) |
| 생성 기본 세션의 그림 | 맞음 0 · 부분 2(b6, d3) · 안 맞음 1(b7). 같은 세션의 절차 그림은 맞음 2(b6, d3) · 부분 1(b7) |
| 생성 메시가 말하지 않은 세부를 더한 것 | 2(b7 깨진 파편, d3 팬 홈) |

비교 시트: `images/sheet_proc_vs_gen.png`(세션마다 절차 0번 후보 | 생성 메시 Unity 그림 | 생성 메시 회색 렌더(관문 v0). 노란 테두리 = 기본 후보, 생성이 없는 칸은 사유).

### 결함·관찰(생성 경로, 고치지 않음)

1. **'돌덩이'는 사물 낱말인데 생성도 절차 형태도 안 된다.** 형태 사전에 `돌`(`shared/lexicon/shape_prompt_en.v0.json:52`)은 있지만 Kiwi가 `돌덩이`를 한 낱말(NNG)로 내고, 사전 맞춤은 "명사 연속 전체"만 받는다(`tools/gen3d/prompts.py:238`·`322`). 그래서 `no_shape_stated`. 매퍼 쪽 결함 1과 같은 빈틈이라 b1·d1은 생성 후보도 형태 슬롯도 없이 기본 blob과 안개 후보만 받는다. G62-h·i의 의도(사물 낱말이면 생성 기본)와 반대 결과다.
2. **중심 명사가 빠져도 꾸밈말만으로 생성하고, 그 후보가 기본이 된다** (b7). Kiwi는 `유리막`을 `유리`+`막` 두 NNG로 내는데 사전에 `막`(`shape_prompt_en.v0.json:64`)·`유리`+`병`은 있어도 `유리`+`막`은 없어 명사가 빠졌다. 남은 꾸밈말 '얇'·'깨지'로 `a single thin broken object`가 되고, 둘 다 단순 도형 목록 밖이라 `non_primitive_stated` → 생성 기본. 절차 매퍼는 같은 문장을 `form.type = shell`(막)로 읽었으므로 이 세션은 생성 기본이 절차보다 덜 맞다.
3. **'금방 깨질 것 같아요'(가능성)가 'broken'(이미 깨진 상태)이 된다** (`shape_prompt_en.v0.json:167` `깨지 → broken`). 양태가 사라져 메시가 이미 깨진 파편이 됐다. 말하지 않은 세부다.
4. **'덩어리'가 생성 기본이 된다** (d3). `primitive_forms.v0.json`이 '덩어리·덩이'를 넣지 않았기 때문(decisions.md G62-i에 "미결정"으로 이미 적힘). 생성 메시는 팬 홈을 지어냈고 절차 blob이 더 맞았다.
5. **절차가 기본 형상(form.base)으로 그리는 사물도 생성 기본이 된다** (b6). 매퍼 v2는 '엉킨 실타래'를 `form.base = line`(tangle)로 그리지만 단순 도형 목록에 없어 `not_listed` → 생성 기본. TripoSG는 가는 가닥을 표면 홈으로 뭉갰다(gen3d-feasibility 한계 4 '얇은 것'과 같은 종류). G62-i 판정이 D6 기본 형상을 '절차가 그림'으로 세지 않는다.
6. 투명(opacity 0.1)은 생성 메시도 거의 안 보이게 한다(b7, 결함 5와 같음).

### 한계(생성 경로)

- 결정성 반복(`--repeat 2`·`--no-cache` 재실행)은 하지 않았다(시간·메모리). d3 GLB는 `g62eval_v2`의 같은 키 캐시다.
- 그림 판정은 640×480 플레이어 그림과 관문 회색 렌더를 함께 보고 했다. 생성 메시의 크기는 가장 긴 변 정규화 × spec 크기라 절차 메시와 화면 크기가 조금 다르다.
- 후보 화면(참여자가 기본 후보를 확정하는 단계)은 거치지 않았다. 기본 판정과 후보 수만 기록했다(`gen3d/candidates.json`).

## 파일

- `scenarios/` 합성 시나리오 10개
- `sessions/live/`, `sessions/offline/` 세션 기록 20개와 `summary.md`·`summary.json`
- `specs/<id>.v2.json`(v4 매퍼, 그림 원본), `specs/<id>.v1.json`(bridge 세션 안 매핑, 비교용)
- `images/<id>.v2.png`(장면 전체), `images/<id>.v2_detail.png`(형상 확대), `images/g64_b5_plain_flame.v1_detail.png`·`images/g64_b6_tangle_sparse.v1_detail.png`, `images/sheet_v2_detail.png`(확대 10장 모음), `images/report.json`(배치 캡처 기록)
- `tools/drive_by_question.py`, `tools/build_v2_specs.py`, `tools/spec_slots.py`, `tools/gen3d_candidates.py`
- 생성 경로: `gen3d/candidates.json`(세션별 후보 수·기본 판정·근거), `gen3d/sidecars/*.form-asset.json`(10개), `gen3d/run.json`, `gen3d/gen.log.txt`, `images/gen3d/<id>.proc.png`(10)·`<id>.gen0.png`(4: b2·b6·b7·d3), `images/sheet_proc_vs_gen.png`. GLB 4개는 `<repo>/../gen3d-out/g64e2e/g62-sdxl-triposg/assets/`(저장소 밖)
