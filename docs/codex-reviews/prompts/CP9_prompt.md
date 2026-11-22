너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: 면담 챗봇 → 확정 텍스트 → 사전·규칙 매퍼 → SceneSpec JSON → Unity 형상 → VR 배치/보기만 러너. 저장소 원칙은 AGENTS.md.
- 2026-11-23에 `docs/prompts/prototype-v4-build.md`의 지시대로 "면담 뒤 후보 선택 → 조절 → 사전 측정" 흐름과 그 주변을 구현했다. 결정은 `docs/decisions.md`의 「형상 표현 범위와 생성 모델」 절 아래 G7–G25. 네가 D5에서 낸 안과 다른 결정(후보를 Python에서 생성 G14, 2×2 규칙 G16, 색상은 벌리지 않음 G17, 출처를 selection.json에 G15)이 있다는 것을 안다. 같은 설계 반론을 되풀이하지 말고 **채택된 결정의 구현이 결정·원칙과 어긋나는 곳**을 찾아라.
- 변경 커밋: `git log --oneline acdfd28..HEAD`, `git diff acdfd28 HEAD --stat`. 주요 파일:
  - 매퍼 v2: `chatbot/ifs_chatbot/scene_builder_v2.py`, `shared/lexicon/scene_params.v2.json`, `noun_stoplist.v2.json`, `chatbot/tests/test_scene_builder_v2.py`, `docs/validation/mapper-v2/`
  - 후보·선택: `chatbot/ifs_chatbot/candidates.py`, `selection.py`, `preview.py`, `selection_sim.py`, `server.py`, `web/stage.js`, `config/v4.toml`, `shared/lexicon/candidate_values.v0.json`, `shared/protocol/selection_protocol.v0.json`, `shared/schemas/selection.v0.1.json`, `chatbot/tests/test_candidates.py`, `test_selection_flow.py`, `docs/validation/selection-flow/`
  - Unity: `unity/Assets/IFS/Runtime/Placement/PlacementSelection.cs`와 러너 변경, `Runtime/Rendering/MistLumps.cs`, `Resources/IFS/SceneSpecMist.shader`, `Runtime/Preview/`, `Runtime/SceneSpec/SceneOverrideJson.cs`, `Runtime/Loading/SceneLoader.cs`(LoadJson, 삭제 전 숨김), 문구 파일 `StreamingAssets/IFS/placement_task*.json`, `docs/validation/cloud/`, `docs/validation/runner-selection/`, `docs/validation/webgl/`
- 테스트(실행 확인됨): pytest 691 통과·6 xfail, Unity EditMode 335/335, dotnet 283.

## 이미 알고 있는 것 (되풀이하지 말 것)
- WebGL 모듈 설치 실패로 WebGL 빌드는 하지 못했고, 미리보기는 상주 Windows 플레이어가 주는 PNG로 간다(G25). 헤드셋 실기 미확인. 참여자 자료 없음(IRB 승인 불가, 내부 시행만).
- 기본 형상(`form.base`, 스키마 2.2.0, G21)과 에셋은 연구 책임자 승인 전이라 구현하지 않았다(`docs/asset-plan.md`는 초안).
- 매퍼 v2는 dev와 목업 36개만 보고 고쳤고 held-out은 돌리지 않았다. v2의 거리 하한 때문에 "얼굴 앞 30센티"가 약 57 cm로 그려진다. `meta.mapping.used`에 v2 값이 없어 스키마 한계로 "v1"로 적는다.
- 어두운 색에서는 밝기 후보가 화면에서 구별되지 않는다. 구름 덩어리 안에 카메라가 들어가면 시야가 가려진다. 소유감 러너의 lowVisibility 계산값이 실제 화면보다 옅게 잡힌다.
- 문구는 전부 draft다. 후보를 보는 것이 원래 심상을 끌어갈 수 있다(유도 위험)는 것은 알고 넣었다.

## 할 일과 관점
1. **G9(말한 속성은 모든 후보에서 같다)와 원칙 2**: 후보·조절·최종 덮어쓰기 어디에서든 참여자가 말한 슬롯이 조용히 바뀌는 경로가 있는가. 모양 낱말(`_unmapped` shape)·신체 부위·`_parts`·`_uncertain`으로 말한 것이 "빈 자리"로 취급되어 벌어지는가. 조절로 말한 값을 바꾸면 원래 말한 값이 기록에 남는가.
2. **결정성(G8)**: 같은 확정 텍스트 → 같은 spec → 같은 후보·같은 표시 순서인가. 시간·난수·dict 순서·부동소수 직렬화·파일 경로·로캘에 기대는 곳. 후보 id와 specSha256이 무엇의 해시인지(파일 바이트 대 정규화 JSON)와 줄바꿈(CRLF) 문제로 러너가 sha 불일치로 거부할 가능성.
3. **출처 네 가지(G15)의 계산 오류**: said/chosen/edited/default가 틀리게 붙는 경우(예: 후보로 고른 뒤 같은 값으로 조절, 조절했다가 원래 값으로 되돌림, none 뒤 조절, 기준 후보 0번을 고름, 말한 값을 조절).
4. **챗봇 ↔ Unity 계약**: `selection.json`(스키마와 실제 출력)과 `PlacementSelection.cs`가 읽는 필드, `candidate_values.v0.json`의 기본값·값 범위와 Unity `SceneParams`·`SceneOverride.Validate`, 색 견본의 표현, 위치·거리 키 거부가 양쪽에서 같은가. 미리보기 플레이어가 그리는 것과 헤드셋 러너가 그리는 것이 같은 덮어쓰기에서 달라지는 경로(카메라·배치·크기 정규화 제외).
5. **면담 밖 단계의 격리(원칙 1·3·4)**: 후보·조절·측정 단계에서 LLM이 호출되거나 면담 검증기가 우회되는 경로, 위기 판정 뒤에 이 단계로 넘어가는 경로, 안전 검사 없이 자유 입력을 받는 곳.
6. **매퍼 v2**: D1 규칙이 형상 명사가 아닌 것을 남기거나 형상 명사를 놓치는 체계적 경우, D2 수정이 말한 값을 왜곡하는 경우(거리 하한 외), v0·v1 출력 불변이 테스트로 실제 고정돼 있는가, 기본 설정에서 v2가 섞여 들어가는 경로.
7. **참여자 자료와 원칙 5·6·7·8**: 세션 기록·selection.json·미리보기 PNG가 저장소 안에 쓰일 수 있는 기본 경로, 문서·기록의 절대 경로·개인 이름, 외부 CDN·외부 호출, 문구의 status/출처 누락, 치료·진단 표현, 방향을 암시하는 문구.
8. **Unity**: 선택 파일 적용 시점과 조건 단계 중 불변, 기록 0.2와 분석기, mist 덩어리 밀도장의 결정성·셰이더 정확성(스테레오, 모바일 문법), SceneLoader의 "삭제 전 숨김" 변경이 기존 러너에 주는 부작용, 문항 범위(0–10) 입력 경계.
9. **테스트의 빈틈**: 완료 기준(같은 확정 텍스트 → 같은 spec과 후보, 사전에 없는 명사가 `_unmapped`에 남음, 1–6단계가 끝까지 돎)이 실제로 고정돼 있는가. 항상 통과하는 테스트.
10. **문서 불일치**: `docs/decisions.md` G14–G25, `docs/validation/*/README.md`, `unity/README.md`가 코드와 다른 곳.

## 출력 형식
지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 심각도 높음부터. 최대 15개. 마지막에 총평 3줄. 칭찬은 생략.
