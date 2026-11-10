# 결정 기록 — 확정 텍스트 → SceneSpec v2 → Unity

지시가 비어 있거나 애매했던 곳에서 고른 기본값과 이유입니다. 한 줄에 하나씩 적습니다. **⚠ 확인 필요**는 연구팀이 맞는지 봐야 하는 것입니다.

## 1단계 — SceneSpec v2 형식

- [1] 지시의 대괄호 경로(챗봇 출력·로그 예시·carrierFormMap.ts·Unity 프로젝트·출력 폴더)가 비어 있음 → 이 저장소 구조로 정함: 챗봇 출력 `chatbot/ifs_chatbot/controller.py` `_finish` + `session_log.py`, 스키마 `shared/schemas/`, 정답 `chatbot/tests/fixtures/scene_spec/`, 사전 `shared/lexicon/`.
- [1] ⚠ 확인 필요 — `carrierFormMap.ts`, `docs/scene-spec-mapping.md`, TS `IFSSceneSpec` 타입이 이 저장소와 확인한 다른 저장소(kcgs-ifs-web, map-extraction)에 없음 → 이 저장소의 `IFSSceneSpec-draft/0.1`(extract.py)와 그 주석의 묶음 이름(form/material/layout/motion)을 기준으로 v2를 만들고 `docs/scene-spec-mapping.md`는 새로 씀. TS 원본과 필드 이름 대조가 남아 있다.
- [1] 다른 사용자 답변·외부 저장소 데이터는 쓰지 않음(사용자 지시: 매핑이 잘못됨). 참여자 답이 필요한 곳은 합성 대사로 챗봇을 돌려 만듦.
- [1] 스키마 위치는 `shared/schemas/scene-spec.v2.json` — 지시의 `schemas/`에 해당하고, 이 저장소는 챗봇·Unity 공용 약속을 `shared/`에 둔다.
- [1] `_provenance`는 슬롯 옆이 아니라 최상위 맵(경로 → 근거 목록) — Unity가 읽는 값 자리를 숫자·문자열·null로 단순하게 두고, 스키마 if/then으로 "값 있음 ⇔ 근거 있음"을 강제하려고.
- [1] ⚠ 확인 필요 — 원칙 3("말하지 않은 속성은 null")과 2단계 지시("3층 V/A/D가 빈 슬롯을 보충")가 충돌 → 원칙을 우선해 3층 결과는 값 자리에 넣지 않고 `_inferred`에만 둔다. 렌더러는 기본으로 쓰지 않는다(`SceneLoader.useInferredSuggestions = false`).
- [1] 최소 필드에 더해 `form.posture`, `material.saturation/opacity/erosion`, `motion.speed`, `body.part/layer`를 둠 — 1층 사전에 이미 있는 범주라 버리면 참여자가 말한 것이 장면에서 사라진다.
- [1] '삭아가는'(decaying)은 거칠기가 아니라 `material.erosion`(가장자리 침식)으로 — 같은 '질감어'라도 젖음과 삭음은 다른 시각 파라미터다.
- [1] ⚠ 확인 필요 — `layout.size`는 로그 척도(0.5 = ×1, 0 = ×0.25, 1 = ×4), 값 = 0.5 + log2(사전 scale)/4 — 크기 지각이 비율에 가까워 조정량을 같은 척도로 재려고. '작은'(×0.6) = 0.316.
- [1] ⚠ 확인 필요 — `layout.verticalOffset`는 참여자 키 대비 높이(0 바닥, 1 정수리), 신체 부위 높이는 Drillis & Contini(1966) 비율 근사(가슴 0.72) — 참여자가 말한 위치를 높이로 옮긴 것이라 추론으로 보지 않았다.
- [1] `layout.distance` 0–1 = 0.3–3.0 m 선형 — 거리어가 5개뿐이라 단순하게.
- [1] `material.color`는 사전의 hsl을 그대로 쓰되 h만 /360 — '회색'은 노션 예시 값 그대로.
- [1] 직유 구 안의 수식어('젖은 종이처럼'의 '젖은')는 비유 대상(종이)의 속성이라 2층 근거로 낮춤 → 같은 슬롯에 1층 근거('눅눅하고')가 있으면 `_alternatives(lower_layer)`.
- [1] 같은 층에서 한 슬롯에 근거가 여럿이면 먼저 말한 것이 값, 나머지는 `_alternatives(later_mention)` — 기존 추출 미리보기와 같은 규칙.
- [1] `_unmatched`는 지시대로 "사전에 없는 말"만. 사전에는 있지만 v2에 자리가 없는 말('가장자리', '나', '종이')은 `_unmapped`로 따로 — 소실 정보율을 계산할 때 둘을 구분해 봐야 한다.
- [1] `body.layer`는 같은 줄에 신체 부위어가 있을 때만 — '검은 벽 뒤에'의 '뒤'가 몸 기준 위치로 잡히는 것을 막으려고.
- [1] `charSpan`·`sourceTextHash`의 기준은 정규화한 확정 텍스트(세션 로그 `confirmedText`와 같은 문자열).
- [1] `meta`에 Kiwi 버전은 넣지 않음(세션 로그 `analyzer`에 있음) — 같은 입력 → 같은 파일을 이 저장소 버전만으로 비교하려고. Kiwi가 바뀌어 결과가 달라지면 정답 비교 테스트가 잡는다.
- [1] 장면 파일에 생성 시각을 넣지 않음 — 원칙 7(결정론). 시각은 세션 로그에 있다.
- [1] 정답 예시의 `participantId = SYN01`, `sessionId = EX01/EX02`, `condition = chatbot` — 합성값.
