# 아침에 할 일 (사람이 해야 하거나, 되돌리기 어려워 남겨 둔 것)

야간 작업 중 실행하지 못했거나 사람이 결정해야 하는 것을 모았습니다. 확인한 항목은 체크하거나 지우면 됩니다.

## 연구 진행 (마감 12/2 기준, 급한 순)
- [ ] **기관 정책 확인 (11/19 정오까지).** 참여자를 모집해 동의를 받고 응답을 저장하는 연구가 기관의 사전 심의 또는 면제 확인 대상인지 확인합니다. 한국HCI학회 투고 규정이 윤리 심의 진술을 요구하는지도 봅니다. 확인되기 전에는 내부 파일럿만 하고, 확인이 안 되면 research-design.md 7절의 축소 범위로 전환합니다.
- [ ] 한국HCI학회 분량·형식 규정 확인(research-design.md 8절 [확인 필요])
- [ ] 중립 심상 문구 초안 채택 여부(opening_neutral, location_neutral, probe_material, 심상 유지 자기보고 문항). 채택하면 `shared/protocol`에 status·출처·버전을 적어 반영합니다(AGENTS.md 원칙 7).
- [ ] 제시 스크립트(불투명 코드, 무작위 순서, 매핑 대응표는 따로 저장)와 조건을 가린 평정 양식 구현(11/17–18)
- [ ] 사전 등록 게시(OSF/AsPredicted 등, 외부 게시라 사람이 함). 항목은 research-design.md 6.4절
- [ ] 2–3명 파일럿: dz 재추정, 시행당 15분 이하인지, 에피소드 묶음 간격 2초·상한 300초 확인
- [ ] KCI/RISS에서 VVIQ·IPQ·VRSQ/SSQ 한국어 타당화판 검색. 없으면 번역-역번역 계획
- [ ] 속성 라벨 2인 코딩 지침 작성. 라벨러는 매핑 사전·코드를 보지 않은 사람으로
- [ ] Cairns-Lee et al. 인용 연도를 2021(온라인)과 2022(권호) 중 무엇으로 쓸지

## 결정이 필요한 것
- [ ] LLM 구조화 추출을 세 번째 비교 조건으로 넣을지. 넣으려면 AGENTS.md 원칙 1을 고쳐야 합니다(decisions.md D03).
- [ ] 신체 부위어 → 높이: v0는 '가슴'에서 `layout.verticalOffset = 0.72`를 만들지만, dev 코퍼스는 공간 높이어가 있을 때만 높이를 정답으로 둡니다. dev 18개 항목이 여기서 갈립니다. 어느 쪽을 따를지 정한 뒤 코퍼스나 scene_params를 고칩니다.
- [ ] 프로브 건너뛰기 규칙(controller.py, `coveredByCategories`): '작은', '떠 있어요', '갈색' 같은 낱말 하나만 나와도 그 차원 프로브 전체를 건너뜁니다. dev 재생에서 슬롯 답 12개가 이 때문에 빠졌습니다. 바꾸려면 shared/protocol 버전을 올려야 합니다.
- [ ] 짧은 '모르겠어요' 답은 no_more로 분류되어 확정 텍스트에서 빠집니다. 그래서 SceneSpec에서 '말하지 않음'과 '모른다고 말함'이 구별되지 않습니다. 'unknown' 표시를 넣을지 검토합니다(원칙 2).
- [ ] 코퍼스 정답 구간 검토: dev.json·heldout.json의 크기 구간, 색상 구간, body_layer 후보. 특히 heldout은 최종 평가 전에 사람이 한 번 보고 고정해야 합니다.
- [ ] Unity 형태 에셋 4종의 size 0.5 물리 크기(m)를 정하고, 크기 정답 구간을 좁힐지
- [ ] mist 프리셋이 매우 옅음(opacity 0.6일 때 가운데 덮임 0.26, 장면 ΔE00 12.9). 밀도 프리셋을 올릴지
- [ ] 유채색 렌더 편차: 말한 유채색의 ΔE00이 합성 spec에서 6.3–8.1(무채색 EX01은 1.2). 논문 해석에 적을지, 셰이더를 보정할지
- [ ] `unity/ProjectSettings/SceneTemplateSettings.json`(Unity 자동 생성)을 계속 커밋할지

## Unity·기기에서 사람이 확인할 것
- [ ] **Quest 3 기기에서 72 Hz 확인 (AC-4.6).** XR 플러그인(OpenXR/Oculus)과 단일 패스 인스턴싱으로 빌드하고 OVR Metrics Tool 등으로 잽니다. 지금 수치(p95 ≤ 2 ms)는 RTX 5080 데스크톱 대리 측정입니다. 같은 자리에서 'VR Quest' 품질 단계를 지금 설정(소프트 섀도·High·MSAA 4×)과 하드 섀도·Medium 해상도로 비교하고, 하늘 셰이더 스테레오 매크로와 서피스 셰이더의 단일 패스 동작도 봅니다.
- [ ] Unity 에디터에서 `Assets/IFS/Scenes/SceneSpecExamples.unity`를 열고 Play: 환경(회색 바닥·1 m 격자·하늘·그림자), EX01·EX02, SpecMotion 움직임을 눈으로 확인합니다(배치 캡처는 정지 화면이라 움직임은 확인하지 못했습니다). 셰이더 수정으로 EX01 그림자 모양이 조금 바뀌었습니다.
- [ ] PlayMode나 기기에서 ProfilerRecorder('Draw Calls Count', 'Triangles Count')로 실측해 배치 캡처 추정값(눈당 드로콜 8–24, 삼각형 2만–10만)과 비교
- [ ] SceneSpecOpaque에 Cull Off ShadowCaster 패스(정점 변위·침식·껍질 clip 포함)를 넣을지: 지금은 침식 구멍 너머 안쪽 면이 그 뒤 깊이로 그림자를 읽습니다.
