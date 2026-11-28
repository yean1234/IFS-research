# G73 후속: 결함 세 가지를 고친 뒤 다시 확인 (2026-11-28)

`../README.md`(G73 첫 시험)에서 나온 결함 ①–③을 고치고, 같은 방식으로 다시 돌렸습니다. experiment 설정 서버(127.0.0.1, 면담 LLM `gemma4:e4b`·가드 모델 실제, Ollama)에서 HTTP로 면담 → 확정(edit, 대사를 줄바꿈으로 이은 글)까지 가고, 헤드리스 Chrome(DevTools 프로토콜)으로 참여자 화면 [다음으로] → 후보 → [맞는 게 없어요]를 눌렀습니다. 생성기는 저장소 밖 `gen3d-venv`의 `tools/gen3d/generate.py --pipeline sdxl-triposg`. 미리보기는 이 코드로 다시 만든 WebGL 빌드(`webgl-build/preview`, 저장소 밖). 대사는 합성이거나 연구 책임자 시험 대사(`chatbot/scenarios/g70_researcher_finish.json`)입니다.

## 고친 것

| 결함 | 원인 | 고친 것 |
| --- | --- | --- |
| ① 생성 프롬프트가 매퍼 판단을 따르지 않음(「a single round cloth」) | `shape_prompt()`가 확정 텍스트만 받아 자기 자리 규칙으로 낱말을 골랐다. '천이 펄럭이듯이'의 '천'은 매퍼가 움직임 비유의 매개어로 대안에만 남겼는데(G71) 프롬프트는 형태 명사로 넣었다 | `shape_prompt(text, mapper_spec=세션 spec)`: 매퍼가 형태에서 버린 낱말(움직임 비유 `mapper_action_simile`, 장소 용법 `mapper_location`, 직접 진술에 밀린 형상 낱말 `mapper_lower_priority`, 부정 `mapper_negated`, 형태 맥락 `mapper_context`)과 매퍼가 전혀 적지 않은 형태 명사(`mapper_unrecorded`)를 빼고 `prompt.dropped`에 남긴다. 차단 판정도 세션 spec으로 한다(장소 용법·움직임 비유의 안개·구름은 막지 않음, 사람·동물은 그대로 막음). spec이 다른 글의 것이면 막는다(`mapper_spec_mismatch`). 생성기 입력 `sentences.json`에 `promptRule: "mapper"`와 `mapperSpec`을 적어 생성기 프로세스도 같은 규칙으로 다시 만들고, 서버가 같은지 본다 |
| ② 미리보기가 글 요약으로 내려감 | 매퍼가 아니라 Unity 쪽. spec의 모양어('구형'·'동그란'·'구체' → round)가 Sphere 모형을 정하는데, `SceneLoader.CheckVariant`가 덮어쓰기를 얹기 전 spec만 보고 정한 모형과 덮어쓴 `form.type`을 견주어 "모양 모형은 blob에만"으로 거부했다. WebGL 준비 그리기가 형태 값마다(`mist` 포함) 덮어쓰기를 얹다 실패 → image → 같은 이유로 실패 → 글 요약. 같은 규칙이 `PlacementSelection.CheckApplicable`에도 있어, 참여자가 조절에서 형태를 안개로 고친 선택 파일은 헤드셋 러너가 시작하지 않았을 것이다 | `ShapeMapping.Resolve(spec, 덮어쓰기)`: 덮어쓰기에 form.type이 있으면 그 값으로 모양어를 판정(mist면 `not_applied_form`, 안개를 그림). 로더·검사·러너 검사가 모두 이것을 쓴다. `shapeModel` 강제는 여전히 blob에만. 기본 형상 판정은 spec 그대로(그림 불변) |
| ③ 캐시 적중 때도 Ollama 모델을 내림 | 생성기가 캐시로 끝날지 알기 전에 내렸다 | 생성기 `--cache-probe`(규칙 프롬프트 → 캐시 키 → 캐시 파일 유무, 모델 호출 없음, `run()`과 같은 키 계산). 모든 줄이 캐시로 끝나고 프롬프트가 서버 것과 같으면 내리지 않는다(`llmUnload.skipped = "cache_hit_expected"`). 미리 보기에 실패하면 예전처럼 내린다 |

G74 때 다시 만든 빌드는 `form.mistKind`·`layout.proportions`를 읽었지만(빌드 안에 `fog5/1`·`dust520/1` 문자열) ②가 그대로였습니다. 이번 Unity 수정으로 `webgl-build/proj` 복사본(robocopy /MIR)에서 WebGL·Windows 미리보기를 다시 빌드했습니다(오류 0, 헤드셋 빌드는 하지 않음).

## 확인 결과

| 세션 | 확정 글(요지) | 미리보기 | 규칙 프롬프트 · 뺀 낱말 | [맞는 게 없어요] 결과 |
| --- | --- | --- | --- | --- |
| F1 | 연구 책임자 시험 대사(…천이 펄럭이듯이 … 모양은 구체 …) | webgl(내려감 0) | a single round object · '천' [50,51] `mapper_action_simile` | ok 10.0초 — 캐시 적중이 미리 보여 모델을 내리지 않음(probe 1.9초 + 생성기 8.1초). 그 후보에도 [맞는 게 없어요] → seed 1 **실제 생성** 57.5초(probe 1.8, 모델 내림 0.6, 생성기 55.0), 관문 통과, 맨 앞에 더함 |
| F2 | 가슴이 답답해요 / 엉킨 실타래 같아요 / … | webgl | a single tangled ball of yarn · 없음 | ok 11.3초, 캐시 적중 → 모델 내리지 않음 |
| F3 | 넓게 펼쳐진 안개가 떠오른다 | webgl, 넓고 낮은 안개(fog + 비율) | 만들지 않음(`no_mesh_form`, 안개) | 기존 none 경로 → 조절(webgl) |
| F4 | 연기가 피어올라요 | webgl, 위로 가늘어지는 연기 기둥 | 만들지 않음(`no_mesh_form`, 연기) | 기존 none 경로 → 조절(webgl) |

- 네 세션 모두 미리보기 내려감(fallbacks) 0, 콘솔 오류 0.
- 화면: `F*_1_candidates.png` 후보, `F*_2_waiting.png` 대기, `F*_3_selecting.png` 만든 물체가 맨 앞 점선 칸, `F1-researcher-regen_4/5` 다시 만들기 대기와 그 결과, `F3·F4_3_adjusting.png` 조절 화면(형태 항목 견본까지 WebGL로 그려짐).
- 연구 책임자 대사의 생성 후보는 프롬프트가 'round'뿐이라 규칙 후보(구)와 거의 같은 구가 나온다. '구체'·'구형'은 형태 프롬프트 사전(`shape_prompt_en.v0.json`)에 없어 들어가지 않는다(사전을 고치면 G62 평가 입력도 바뀌므로 이번에 손대지 않음).
- 원본 기록(`chatbot/logs/`, `gen3d-out/none-SYN-G73F-*`)은 git 밖입니다.

## 기존 경로 영향

- 텍스트만 넘기는 `shape_prompt(text)`는 그대로(builder `gen3d-shape-prompt/0.2.0`). G62 기본 후보(v4-gen3d)와 `eval_g62.py`는 생성기 입력에 `promptRule`이 없어 예전 규칙을 쓴다. 매퍼 규칙은 builder `gen3d-shape-prompt/0.3.0+mapper-v2`, `promptRule: "mapper"`로 기록된다.
- 합성 말뭉치 60세션(`imagery_corpus` dev·heldout)에서 두 규칙의 결과(상태·프롬프트)가 다른 것은 0건.
