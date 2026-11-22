# D5 — 후보 생성과 기본 형상의 표현 방식 독립안 요청

너는 이 연구 저장소의 설계 자문이다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라. 다른 설계안은 보여 주지 않는다. `docs/codex-reviews/D5*.md`와 `docs/decisions.md`의 맨 마지막 절은 읽지 마라.

## 맥락
- 흐름: 챗봇 면담 → 확정 텍스트 → 사전·규칙 매퍼(Python, `chatbot/ifs_chatbot/scene_builder*.py`) → SceneSpec JSON(`shared/schemas/scene-spec.v2.1.json`) → Unity 로더(`unity/Assets/IFS/Runtime/Loading/SceneLoader.cs` → `SceneParams` → `FormRenderPlan` → 형상별 렌더러, `unity/Assets/IFS/Runtime/Rendering/`).
- 새로 만들 단계(확정됨, `docs/prompts/prototype-v4-build.md`와 `docs/decisions.md`의 G7–G13): 면담 뒤에 **규칙이 만든 형상 후보 4개**를 챗봇 웹 화면 안의 Unity 미리보기(WebGL, 안 되면 Unity가 캡처한 이미지)로 보여 주고, 참여자가 하나를 고르거나 "맞는 것이 없다"를 고른 뒤, 정해진 항목(형태, 색, 밝기, 투명도, 크기, 질감, 움직임)만 고친다. 위치·거리는 만지지 않는다. 그 결과 spec을 헤드셋의 배치/보기만 러너(`unity/Assets/IFS/Runtime/Placement/`)가 읽는다.
- 확정된 제약: 후보는 규칙이 만든다(LLM·생성 모델 금지). 같은 spec은 언제나 같은 후보를 낸다. **후보끼리 다른 것은 말하지 않아 비어 있던 자리와 낱말 해석이 갈리는 자리뿐이고, 말한 속성은 모든 후보에서 같다.** 속성 출처는 네 가지로 구분해 기록한다: 말함 / 고름(후보 선택) / 고침(조절) / 기본값.
- 기본 형상 목록을 넓힌다: 지금 형태는 `form.type`(blob/mist/shell/fragments)과 모양 낱말(`_unmapped` category shape → Sphere/Cube/FlatCylinder/Cone, `ShapeMapping.cs`) 두 경로뿐이다. 여기에 "담는 것(화분·그릇·병)", "선·실", "얇은 판·천" 같은 묶음 단위의 중립 기본 형상을 더하려 한다(낱말 → 범주 → 기본 형상, 사전으로 연결). 구체 목록은 따로 정한다.
- 지금 있는 것: `_provenance`(슬롯 경로 → 근거, 값이 null이면 없어야 함), `_unmapped`, `_alternatives`, `_uncertain`, `SceneParams.DefaultsUsed`, `SceneOverride`(해석된 값에 숫자·범주를 덮어씀, 기록 없음), `OwnershipVariantGenerator`(Unity에서 spec 하나로 결정적 변형본을 만듦), `SceneLoader.SetNumber/SetCategory/SaveFinal`(조정 입력), v0 매퍼 출력의 sha256 고정 테스트(`chatbot/tests/fixtures/scene_spec/v0_output_sha256.json`).
- 일정: 2026-12-02 투고. 참여자 없이 팀 내부 시행만 한다. 면담부터 사전 측정까지 흐름이 끝까지 도는 것이 우선이다.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 생성 모델은 쓰지 않는다(시험했고 탈락, `docs/gen3d-feasibility.md`).
- 후보를 보는 것이 원래 심상을 끌어갈 수 있다(유도 위험). 그래도 넣기로 했다.
- WebGL 빌드가 될지는 아직 모른다. 로더는 지금 파일을 직접 읽는다.
- 후보 개수 4, "맞는 것이 없다" 선택지는 정해졌다.

## 설계해 달라는 것
각 항목에 하나의 안을 정하고 이유를 2–3문장으로 적어라. 대안을 나열만 하지 말 것.
1. **후보를 어디서 무엇으로 만드는가.** Python(매퍼 옆)에서 만들지 Unity에서 만들지. 후보의 표현은 변형된 spec 전체인지, 원본 spec + 덮어쓰기 목록(overrides)인지. 웹 화면·Unity 미리보기·헤드셋 러너가 각각 무엇을 받는지. 결정성을 어떻게 보장하고 테스트로 고정하는지.
2. **출처 네 가지(말함/고름/고침/기본값)를 어디에 어떻게 적는가.** 기존 `_provenance`(값이 null이면 없어야 한다는 스키마 규칙 포함)와의 관계, 최종 spec의 형태, 기록 파일. 스키마를 바꿔야 하면 무엇을 어떻게(버전), v0 출력 해시와 기존 평가에 주는 영향.
3. **후보 규칙.** 어느 자리를 벌리는가(빈 슬롯 가운데 무엇을 우선하는가: 형태·색·크기·투명도·질감·움직임), 한 후보가 몇 자리를 동시에 바꾸는가, 값은 어디서 고르는가(슬롯별 고정 후보값 표), 낱말 해석이 갈리는 자리(예: "껍질" → shell 또는 얇은 막, "빛" → 밝은 덩어리 또는 안개)의 범위를 어디까지 둘 것인가. 빈 자리가 없어 후보가 같아지는 경우, 빈 자리가 너무 많은 경우(느낌만 말함)의 처리. 후보 순서(위치 효과)와 그 기록.
4. **기본 형상을 spec에서 어떻게 표현하는가.** `form.type` 값을 늘릴지, 별도 필드(예: `form.base`)를 둘지, 지금의 `_unmapped` shape 경로를 넓힐지. 스키마·Unity `ShapeMapping`·`FormRenderPlan`·소유감 러너 변형 규칙(형태 변형 X22·X23)에 주는 영향과 이행 순서.
5. **조절 단계의 표현.** 조절 항목과 SceneSpec 슬롯의 대응, 값의 범위·단계, "모든 조작이 반드시 화면에 반영되어야 한다"는 조건을 어떻게 보장·검사하는가, 조절 기록(무엇을 몇 번, 처음 값과 마지막 값).
6. **"맞는 것이 없다"를 골랐을 때** 무엇을 하고 무엇을 기록하는가(다음 단계로 갈 형상, 측정에의 반영).

## 출력 형식
- 위 1–6 번호 그대로. 각 항목: 결정 한 줄 → 이유 → 구체 값·방법 → 근거 파일:줄(있으면).
- 마지막에 "가장 불확실한 결정" 2개와 확인 방법, 그리고 12/2까지 구현 순서(짧게).
- 전체 120줄 이내. 칭찬·요약 서론 생략.
