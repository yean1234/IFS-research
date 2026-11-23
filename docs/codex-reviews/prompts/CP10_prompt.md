너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: 면담 챗봇 → 확정 텍스트 → 사전·규칙 매퍼 → SceneSpec JSON → Unity 형상 → VR 배치/보기만 러너. 저장소 원칙은 AGENTS.md.
- CP9 뒤 2026-11-23에 연구 책임자가 여섯 가지를 정했다(`docs/decisions.md` G30–G35). 그에 따라 (a) G31–G34: 색을 조절 맨 앞에·색 변경 기록, 모형 없는 모양어의 형태 후보와 새 출처 값 둘, 거리 하한에서 말한 값·그려진 값 기록, 밝기 후보 제외·구별 규칙·선택 건너뜀(`ifs-selection/0.2`), (b) D6: `form.base`·`form.baseVariant` 슬롯과 스키마 2.2.0, 절차 모형 5개(container, line, sheet, flame, drop), 매퍼 v2의 명사 → 기본 형상 경로, 조절의 형태 9값, (c) WebGL 미리보기 시험 빌드(캡처 경로 수정)가 들어갔다. 세부는 `docs/decisions.md` 맨 끝의 「G31–G34 구현 세부」와 「D6 구현 세부」.
- 변경 커밋: `git log --oneline 96f4cf4..HEAD`, `git diff 96f4cf4 HEAD --stat`. 주요 파일:
  - 챗봇: `chatbot/ifs_chatbot/scene_builder_v2.py`, `candidates.py`, `selection.py`, `selection_sim.py`, `eval/placement.py`, `web/stage.js`, `shared/lexicon/scene_params.v2.json`(과 기본 형상 사전), `candidate_values.v1.json`·`v2.json`, `shared/schemas/scene-spec` 2.2.0, `selection.v0.2.json`, `shared/protocol/selection_protocol.v0.json`
  - Unity: `unity/Assets/IFS/Runtime/Rendering/`(기본 형상 메시·렌더 계획), `Runtime/SceneSpec/`(파서, SceneParams, SceneOverrideJson), `Runtime/Placement/PlacementSelection.cs`·`PlacementRunner.cs`, `Runtime/Preview/PreviewStage.cs`, `Editor/PreviewBuild.cs`
  - 검증 자료: `docs/validation/base-forms/`, `selection-flow/`, `webgl/`, 계획 `docs/asset-plan.md`
- 테스트(에이전트 보고): pytest 823 통과·6 xfail, dotnet 383, Unity EditMode 440.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 헤드셋 실기·팀원 그림 판정 없음. 참여자 자료 없음(IRB 승인 불가, 내부 시행만). held-out 코퍼스는 열지 않았다. 채점기에 `form.base` 정답 기준 없음.
- 회색 불꽃은 물방울처럼 보인다. 그릇은 컵처럼 키가 크다. 종이·천 차이가 작고 얇은 판은 옆에서 거의 사라진다. 변형값은 같은 문장 안의 말만 본다(M18).
- 맨 "불"·"눈물"·"줄"·"덩굴"·"불덩어리"·"창"은 사전에서 뺐다. 웅덩이·꿀·빛·사람은 기본 덩어리로 그려진다(사람은 `excluded_shape`로 기록만).
- 구별 규칙은 `same_final_values`와 `still_preview_motion` 둘뿐이고 나머지 조합은 미확인으로 적혀 있다. image 미리보기는 정지 화면이라 조절에서 움직임을 바꿔도 그림이 안 바뀐다.
- '가장자리'·'경계'·'구멍' 같은 부분 모양어도 형태 후보를 연다(사람이 정할 것으로 올림). `form_type_with_base` 갈림이 말한 슬롯을 후보에서 바꾸는 유일한 경우라는 것도 안다(사람이 정할 것).
- WebGL은 시험 빌드만 했고 챗봇 화면에는 아직 연결하지 않았다. CP9에서 지적하고 처리한 것(G26–G28)은 되풀이하지 마라.

## 할 일과 관점
1. **v0·v1 불변과 하위 호환**: 스키마 2.2.0·`form.base` 도입으로 v0·v1 매퍼 출력, 2.0·2.1 spec을 읽는 Unity 경로(기록 파일, golden 지문), `ifs-selection/0.1` 파일 읽기가 바뀌는 경로가 있는가. 고정 테스트가 실제로 그 경로를 지나는가.
2. **명사 → 기본 형상 규칙의 원칙 2 위반**: 말하지 않은 형상이 그려지는 체계적 경우(수량·비교 기준·관용 표현·부정·가정·과거·타인 묘사·신체 부위·동음이의), 낱말 뜻에서 온 변형값(`baseVariant`)이 "말함"으로 적히는가 "낱말에서 추론"으로 구분되는가, 근거 명사를 `_unmapped`에서 빼면서 기록이 사라지는 경우.
3. **안전 제외**: 제외 낱말(사람·아이, 공격하는 존재, 무기, 죽음·외상, 피·올가미)이 합성어·활용형·직유로 우회해 기본 형상이나 대체 형상으로 그려지는 경로. 제외 기록이 참여자 화면에 드러나는 방식.
4. **출처 여섯 가지와 `form.base`**: said/chosen/edited/default/said_unrendered_chosen/said_unrendered_default가 `form.type`·`form.base`·`form.baseVariant` 세 슬롯에 일관되게 붙는가. 조절에서 형태 9값 중 하나를 고르면 두 슬롯이 함께 바뀌는데 한쪽만 기록되거나, 말한 base를 조절로 바꿨을 때 원래 말한 값이 사라지는 경우. `colorChanged`, `skipped`, `distanceFloor`의 계산 오류.
5. **구별 규칙과 선택 건너뜀**: 0번이 아닌 후보만 남거나 표시 순서 기록이 어긋나는 경우, 건너뜀과 none의 혼동, 러너·분석기가 건너뜀을 "고르지 않음"으로 잘못 세는 경우, 결정성.
6. **챗봇 ↔ Unity 계약**: `candidate_values.v2.json`의 형태 9값·변형값과 Unity가 받는 키·값(`SceneOverrideJson`, `PlacementSelection` 허용 키, 엄격 파서)이 다른 곳. 미리보기와 헤드셋 러너가 같은 덮어쓰기에서 다른 형상을 그리는 경로(base가 type 조건 때문에 한쪽에서만 그려지는 경우 포함).
7. **Unity 메시·렌더**: 5개 메시의 결정성, 법선·감김 방향·양면, 투명일 때 정렬·안쪽 면, 크기 정규화(말한 크기와 실제 경계 상자), 0 또는 극단 변형값, 소유감 러너 변형과의 상호작용, WebGL2에서 문제될 기능, `PreviewStage`의 WebGL 분기가 다른 플랫폼에 주는 영향, `PreviewBuild`가 설정을 되돌리지 못하는 예외 경로.
8. **원칙 5·6·7·8**: 새 사전·문구의 status/출처, 프로토콜 버전, 저장소에 들어간 절대 경로·개인 이름·참여자 자료, 외부 호출, 치료·진단 표현.
9. **테스트의 빈틈과 문서 불일치**: 항상 통과하는 테스트, `docs/decisions.md` G30–G35 및 두 구현 세부 절·`docs/asset-plan.md`·`docs/validation/*/README.md`·`unity/README.md`가 코드와 다른 곳.

## 출력 형식
지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 심각도 높음부터. 최대 15개. 마지막에 총평 3줄. 칭찬은 생략.
