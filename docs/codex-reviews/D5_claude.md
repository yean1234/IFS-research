# D5 — Claude 하위 에이전트 독립안 (2026-11-23)

## 1. 후보를 어디서 무엇으로 만드는가
**결정: Python(매퍼 옆 새 모듈 `chatbot/ifs_chatbot/candidates.py`)에서 만들고, 후보는 "원본 spec + 덮어쓰기 목록(overlay)"으로 표현한다. 원본 spec 파일은 추출 뒤 한 바이트도 바꾸지 않는다.**
- 이유: 변형된 spec 전체로 만들면 빈 슬롯에 값을 넣는 순간 스키마가 `_provenance`를 요구하는데, `_provenance`는 원문 `trigger`·`charSpan`이 필수라 "말하지 않은 값"에 붙일 근거가 없다(가짜 근거가 되거나 스키마 위반). Unity에는 이미 같은 뜻의 덮어쓰기(`SceneOverride`: SceneParams 키 → 값, `ShapeModel`)가 있어 overlay를 그대로 받을 수 있다. 후보 API·기록·"맞는 것이 없다" 흐름이 모두 챗봇 서버에 있고, WebGL이 안 될 때의 대안(데스크톱 캡처)에서도 생성 위치가 바뀌지 않는다.
- overlay 형식(`shared/schemas/scene-overlay.v1.json`, 새 파일): `{"candidateId":"C1","rulesVersion":"cand-1.0.0","overrides":{"material.color.l":0.25,"form.type":"mist"},"shapeModel":null,"dims":["form","color"],"split":null}`. 키는 SceneParams 키(`material.color.h/s/l`, `form.type`, `motion.type` …)를 쓴다 — `SceneOverride.Validate`가 그대로 검사할 수 있다.
- 받는 쪽:
  - 웹 화면: `candidates.json`(후보 4개의 overlay, 화면 위치 순서, 각 후보가 벌린 차원 이름). 차원 이름은 화면에 쓰지 않는다(유도 문구 방지), 그림만 보인다.
  - Unity 미리보기: spec JSON 문자열 + overlay JSON 문자열. `SceneLoader.LoadFromJson(specJson, overlayJson)`을 새로 두고 `Load(path, variant)`와 같은 내부 경로(파싱 → `CheckVariant` → `ApplyVariantParams`)를 탄다. WebGL에서는 `File.ReadAllText`(SceneLoader.cs:225)를 쓸 수 없으므로 문자열 입구가 필요하다(확인 필요: WebGL `SendMessage` 문자열 길이·한글 인코딩).
  - 헤드셋 러너: `extracted_spec.json` + `final_overlay.json` 두 파일. 지금 `_loader.Load(_specFullPath, null)`(PlacementRunner.cs:403)을 `Load(spec, finalOverlay)`로 바꾸고, 두 파일의 sha256을 러너 기록에 남긴다. 단, 지금 `Load(path, variant)`는 덮어쓰기를 기록하지 않으므로(SceneLoader.cs:328) 러너 기록에 overlay 전체를 따로 복사한다.
- 결정성: 난수 없음. 후보 내용은 슬롯 값(meta 제외)과 규칙 표 파일 `shared/candidates/candidate_rules.v1.json`만의 함수. 출력은 `sort_keys`, 수치 소수 4자리. 테스트: (a) EX01·EX02·D01–D30의 `candidates.json` 바이트 sha256을 `chatbot/tests/fixtures/scene_spec/candidates_sha256.json`에 고정(v0 고정 방식과 같음), (b) 성질 테스트 — 말한 슬롯에서 온 SceneParams 키는 갈림 표에 든 것 말고는 어떤 overlay에도 없다(G9), 후보끼리 overrides가 모두 다르다, 같은 spec을 두 번 돌려 같은 바이트, (c) Unity EditMode 교차 테스트 — 위 고정 후보를 `SceneOverride.Validate`·`CheckVariant`·`FormRenderPlan.Build`에 넣어 오류 0, 후보끼리 계획이 다른지 확인.

## 2. 출처 네 가지를 어디에 적는가
**결정: `_provenance`와 scene-spec 스키마는 건드리지 않는다. `_provenance`는 "말함"만 뜻하게 두고, 네 출처는 최종 overlay의 `sources` 표에 SceneParams 키 단위로 적는다.**
- 이유: `_provenance` 규칙(값이 null이면 키가 없어야 함, 근거는 원문 구간, scene-spec.v2.1.json:329–354, 1562–1600)은 "참여자가 텍스트로 말한 것"의 정의 그 자체라, 고름·고침을 넣으면 그 뜻이 깨진다. spec을 안 바꾸면 v0 출력 해시(`v0_output_sha256.json`, test_scene_builder_v1.py:571)와 held-out 평가가 전혀 영향을 받지 않는다.
- `final_overlay.json`: `{"overrides":{…최종 값…},"shapeModel":…,"sources":{"material.color.h":{"source":"adjusted","value":0.5833,"saidValue":null,"chosenValue":0.0,"candidateId":"C3","adjustCount":4}, "layout.size":{"source":"said",…}, "layout.distance":{"source":"default",…}}}`.
- 판정 규칙(우선순위 고침 > 고름 > 말함 > 기본값): 조절 기록에 그 키가 한 번이라도 있으면 adjusted, 고른 후보 overlay에 있으면 chosen, spec `_provenance`에 해당 경로가 있으면 said(키 대응표: `material.color.h/l` ← `material.color`, `material.color.s` ← `material.saturation` 또는 `material.color`), 나머지는 default. 말한 값을 참여자가 고친 경우도 adjusted로 두되 `saidValue`를 남긴다(매퍼 오독 또는 심상 변화의 지표로 셀 수 있음).
- 위치·거리(`layout.distance`·`verticalOffset`)는 overlay에 들어갈 수 없게 스키마에서 막는다(G10).
- 이중 확인: Python이 `sources`를 쓰고, Unity 러너가 spec + overlay + `DefaultsUsed`(SceneParams.cs:50)로 다시 계산해 다르면 경고를 기록한다.
- 기록 파일(세션 폴더, git 밖): `extracted_spec.json`, `candidates.json`, `selection.json`, `adjust_events.jsonl`, `final_overlay.json`.

## 3. 후보 규칙
**결정: 열린 차원 가운데 우선순위 상위 2개를 골라 2×2 격자로 4개를 만든다. 한 후보는 그 2자리만 바꾸고, 나머지 빈 자리는 모든 후보에서 기본값이다.**
- 이유: 한 차원 4단계보다 2×2가 서로 가장 고르게 다르고, 고른 결과가 두 차원 각각의 선호로 읽힌다. 동시에 바꾸는 자리를 2개로 묶어 두면 느낌만 말한 경우에도 후보가 "아무거나 다 다른 네 개"가 되지 않고 기록 해석이 쉽다.
- 차원과 우선순위(빈 경우만 열림): ① 형태(`form.type` null이면서 적용된 모양어도 없고, `form.base`(4절)도 null) ② 색(`material.color` null) ③ 크기 ④ 투명도 ⑤ 질감(roughness) ⑥ 움직임. 밝기는 후보 차원에 넣지 않는다(색 명도와 겹쳐 보임, 조절에서만). 움직임은 WebGL이 안 되어 정지 이미지 대안으로 가면 후보 차원에서 뺀다.
- 고정 후보값 표(`candidate_rules.v1.json`, 4단계 + 2단계 부분집합): 형태 {blob, mist, fragments, shell} / 2단계 {blob, mist}. 색은 색상을 고르지 않고 무채색 명도만 {0.2, 0.4, 0.6, 0.9} / 2단계 {0.2, 0.9} — 감정 이름에서 색을 추론하는 것으로 읽힐 여지를 없애려는 것. 크기 {0.3, 0.45, 0.6, 0.75} / {0.35, 0.7}. 투명도 {1.0, 0.75, 0.5, 0.3} / {1.0, 0.45}. 질감 {0.1, 0.4, 0.7, 0.95} / {0.1, 0.9}. 움직임 {still, floating, trembling, rotating} / {still, floating}(X22에서 floating이 보이는 쪽).
- 말하지 않은 형태 차원에 "담는 것·선·천" 같은 구체 기본 형상은 넣지 않는다. 말하지 않은 사물을 보여 주는 것은 유도가 가장 크다. 추상 형태 4종만 쓴다.
- 낱말 해석 갈림의 범위: 손으로 쓴 닫힌 표 `shared/lexicon/interpretation_splits.v1.json`(낱말 → 읽기 2개)에 있는 형태·사물 명사만 다룬다. 예: 껍질·막 → shell | 얇은 판(Sheet), 빛 → 밝은 blob(brightness 0.9) | 밝은 mist. 여기에 참여자가 직접 둘 사이에서 망설인 `_alternatives`(reason `participant_uncertain`)와, 4절의 "form.type과 form.base가 둘 다 말해짐" 충돌을 더한다. 자모 퍼지 일치(`needs_confirmation`)와 `_inferred`(V/A/D)는 넣지 않는다 — 둘 다 말한 것이 아니다. 갈림은 spec당 하나만(charSpan이 가장 앞선 것) 쓰고, 격자의 첫 차원 자리를 차지한다. 갈림 overlay만 말한 슬롯을 덮을 수 있고 `split: {lemma, readings, charSpan}`을 남긴다.
- 열린 차원 1개(갈림 포함): 그 차원의 4단계로 4개. 갈림만 있고 열린 차원 0개: 2개. 둘 다 0개: 후보 1개만 보이고 선택 단계를 건너뛰어 조절로 간다. `candidateCount`와 `reducedReason`(`no_open_slot` 등)을 남긴다. 같은 모양 4개를 고르게 하지 않는다.
- 보이지 않는 차이 방지: 앞선 차원 값에 따라 차이가 안 보이는 차원은 건너뛴다(예: 회전 대칭 모형에서의 회전 움직임 — OwnershipVariantGenerator의 보이지 않는 움직임 표를 같은 내용으로 JSON에 두고 양쪽이 읽는다). 1절 (c) 테스트가 마지막 확인이다.
- 순서: 생성 순서는 격자 순서(a0b0, a0b1, a1b0, a1b1)로 고정한다. 화면 위치는 `sha256(sessionId)`의 앞 8자리 mod 4만큼 돌리는 순환 라틴 방진. 후보 내용은 sessionId와 무관하고 위치만 바뀐다. `candidates.json`에 `displayOrder`와 `orderRule`, `selection.json`에 고른 위치를 남긴다.

## 4. 기본 형상의 spec 표현
**결정: 새 슬롯 `form.base`를 둔다(scene-spec v2.2.0, 상위 호환 추가). `form.type`은 표면·밀도 방식(blob/mist/shell/fragments)으로 그대로 두고, `form.base`는 기하 모형 {container, line, sheet, …첫 묶음}을 뜻한다.**
- 이유: `form.type`은 실제로 재질·밀도 프리셋(FormRenderPlan.cs:35–44, mist 밀도 0.5)이라 "병"과 같은 줄에 두면 "안개 병" 같은 조합을 표현할 수 없고, 소유감 밀도 표(OwnershipVariantGenerator.cs:169–172)도 깨진다. 사물 명사는 참여자가 말한 값이라 `_unmapped`(뜻: "옮길 곳이 없음")가 아니라 근거(`explicit_lexicon`)가 달린 정식 슬롯에 있어야 출처 규칙이 그대로 돈다. 모양어의 `_unmapped` 경로는 이미 v1 출력과 렌더 결과에 묶여 있으니 12/2 전에는 옮기지 않는다.
- 스키마: `form.base` enum + null, `_provenance`·`_alternatives`·`_inferred`의 경로 목록에 추가, null ⇔ `_provenance` 키 없음 규칙도 같게 추가. `specVersion` enum에 2.2.0. v0 빌더는 2.0.0을 그대로 내므로 v0 해시는 그대로다. v1 빌더가 `form.base`를 내기 시작하면 v1 출력이 바뀐다(지금까지 `_unmatched`로 가던 사물 명사가 슬롯으로 옮겨 감). 슬롯 채점 지표 자체는 그대로지만 `_unmatched` 개수(소실 지표)가 달라지므로 held-out을 다시 돌려 기록한다.
- 사전: `shared/lexicon/base_shapes.v1.json`(낱말 → 범주 → base). 범주 이름은 "연구팀이 정한 목록"으로 표기한다.
- 판정 규칙(Unity `ShapeMapping` 확장, 같은 파일에 `ResolveBase`): base가 있으면 모양 모형보다 앞선다(모양어는 `not_applied_base`로 기록). `form.type`이 mist·shell·fragments로 말해졌고 base도 말해졌으면 렌더는 `form.type`을 지키고(지금 규칙 3과 같은 방향), base는 `not_applied_form`으로 기록하고, 3절 갈림 후보로 둘 다 보여 준다.
- 렌더: `ShapeMapping.Models`에 Container·Line·Sheet를 더하고 `ShapeModelFactory`에서 절차 모형으로 만든다(회전체 그릇, 살짝 굽은 관, 약하게 휜 판). `FormRenderPlan`은 새 렌더러 이름 `baseModel` 대신 기존 `shapeModel` 경로와 `ShapePreset`(정점 변위 0)을 그대로 쓴다. 덮어쓰기는 `SceneOverride.ShapeModel`이 받는다.
- 소유감 러너: X23 표에 "Container·Line·Sheet → Sphere(remove)"를 더한다. 회전체 Container는 회전 움직임이 안 보이므로 X32 표에 추가한다. Line의 흔들림이 보이는지는 확인 필요.
- 이행 순서: ① 스키마 2.2 + Python 검증 ② Unity 파서·`ResolveBase`·golden(기존 지문 불변 확인, X68 방식) ③ 절차 모형 3종 ④ 사전 연결과 held-out 재측정.

## 5. 조절 단계의 표현
**결정: 조절은 SceneParams 키에 대한 이산 단계 선택으로만 받고, 각 조작은 서버 검증 → overlay 갱신 → 미리보기 계획 해시 비교를 거친다.**
- 이유: 이산 격자로만 받아야 "이 상태에서 이 조작이 화면을 바꾸는가"를 미리 전부 열거해 테스트할 수 있다. 연속 슬라이더는 반영되지 않는 미세 변화를 막을 수 없다.
- 대응과 단계:
  - 형태: `form.type`{blob, mist, shell, fragments} + `shapeModel`{없음, Sphere, Cube, FlatCylinder, Cone, Container, Line, Sheet}을 한 목록으로.
  - 색: 색상 `color.h` 12칸(k/12), 진하기 `color.s` {0, 0.33, 0.67, 1}, 명도 `color.l` {0.15, 0.3, 0.5, 0.7, 0.85}.
  - 밝기: `material.brightness` 9칸(0–1, 0.125 간격). 0.5 위는 발광, 아래는 어둡게 하는 식이 셰이더에 있다(SceneSpecMist.shader:156–159). Opaque 셰이더도 같은지는 확인 필요.
  - 투명도: `opacity` {0.2, 0.4, 0.6, 0.8, 1.0}. 바닥값은 조절 범위에만 두고 말한 값은 올리지 않는다(X70).
  - 크기: `layout.size` {0.2 … 0.8} 7칸.
  - 질감: `roughness` 5칸. erosion은 G10 목록 밖이라 넣지 않는다.
  - 움직임: `motion.type` 묶음별 대표 6개 + `motion.speed` {0.25, 0.5, 0.75}.
- 반영 보장: (a) 정적 — Unity EditMode 테스트가 형태 상태마다 모든 조작의 이웃 단계 쌍을 열거해 `FormRenderPlan`(움직임은 SpecMotion 매개변수) 차이를 확인하고, 차이가 없는 (상태, 조작) 표를 `controls_availability.json`으로 내보낸다. 웹은 그 표로 해당 조작을 끈다(예: s=0이면 색상 칸을 고르면 s를 0.67로 함께 올리는 묶음 조작으로 바꾸고 두 키를 한 사건으로 기록, 회전체에서 회전 끔). (b) 실행 중 — 조작마다 미리보기가 계획 해시를 돌려주고, 이전과 같으면 `not_reflected`를 기록한다.
- 기록: `adjust_events.jsonl` 한 줄 = {t, key, from, to, stepIndex, control, planHash}. 끝날 때 `final_overlay.sources`에 키별 처음 값(고른 직후)·마지막 값·횟수를 요약한다. 웹은 `POST /api/sessions/{sid}/adjust`, `/adjust/done`으로 보낸다. 서버는 격자 밖 값을 거부한다.

## 6. "맞는 것이 없다"를 골랐을 때
**결정: 후보를 다시 보여 주지 않고 "후보 0"(원본 spec + 빈 overlay, 즉 말한 값 + 기본값)에서 조절 단계를 시작한다. 고정 체크 문항 하나로 무엇이 달랐는지 받는다.**
- 이유: 다시 후보를 보여 주면 유도 노출이 늘어난다. 기본값에서 시작하면 출처가 말함/고침/기본값 셋으로만 남아, 후보가 개입하지 않은 경로로 깨끗하게 구분된다.
- 문항(초안, `status: draft`): "어떤 점이 달랐나요?(여러 개 선택)" — 보기는 G10 항목 이름 7개 + "전체적으로". 자유 기술은 받지 않는다(참여자 데이터 최소화). 선택한 항목은 조절 패널을 그 순서로 펼치는 데만 쓴다.
- 기록: `selection.json`에 `outcome:"none_fit"`, 보여 준 후보 id·위치, 체크한 항목, 고르기까지 걸린 시간. 다음 단계 형상은 조절 결과(`final_overlay.json`)이고, 분석에서 `outcome`을 사전에 정한 공변량·층으로 쓰며 대표성 문항(G13)과 함께 본다. 내부 시행의 "맞는 것이 없다" 비율은 이 필드에서 바로 센다.

## 가장 불확실한 결정
1. **`form.base` 새 슬롯(v2.2.0)과 v1 출력 변화.** `_unmapped` 확장보다 원칙에는 맞지만 v1 출력·held-out 소실 지표가 바뀐다. 확인: base 사전을 켠 것과 끈 것으로 held-out 30문장을 돌려 슬롯 지표가 같고 `_unmatched`만 줄었는지, v0 해시 불변, Unity golden 지문 불변(X68)을 본다. 어긋나면 12/2 전에는 Unity 쪽 `_unmapped`(category object) 읽기로 임시 처리한다.
2. **2×2 격자와 무채색 명도 고정값.** 두 단계 값이 하늘 지평선(0.74)과 겹쳐 안 보이거나(밝은 무채색), 형태 blob↔mist가 투명도까지 바꿔 "두 자리만 바꿈"이 화면에서는 세 자리로 읽힐 수 있다. 확인: 고정 후보를 D01–D30에 만들어 캡처하고, 후보 쌍마다 합성 ΔE(`CompositedDeltaE`)와 덮인 화소 수 차이가 문턱 이상인지 보며, 팀 내부 시행에서 "두 후보가 같아 보인다" 보고를 센다.

## 12/2까지 구현 순서
1. overlay 스키마 + `candidates.py` + 규칙 표 + 해시·성질 테스트(1–2일)
2. `SceneLoader.LoadFromJson` + Unity 교차 테스트(후보 계획 차이)(1일)
3. API(후보·선택·맞는 것 없음·조절·완료)와 웹 화면. WebGL이 안 되면 캡처 이미지로(2일)
4. 러너가 spec + `final_overlay` 읽기, `sources` 재계산 확인(1일)
5. `form.base` 2.2 + 절차 모형 3종 + 사전(2일, 밀리면 투고 뒤로. 1–4는 이것 없이 돈다)
6. 합성 시나리오로 1–6단계 끝까지 돌리기, 내부 시행 점검표(1일)
