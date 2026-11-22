# D3 — 형상 종류별 렌더 경로 설계 독립안 요청

너는 Unity(Built-in 렌더 파이프라인, Quest 3 대상) 그래픽스 설계 검토자다. 아래 상황에서 **렌더 구조의 독립안**을 써라. 다른 사람의 안은 주지 않는다. 저장소 파일은 읽기만 한다. `docs/decisions.md`의 마지막 절(이 결정에 대한 다른 안이 적힐 곳)은 읽지 마라.

## 지금 구조
- 면담 확정 텍스트 → 사전·규칙 매퍼(Python, v0와 v1 두 판) → SceneSpec JSON(`shared/schemas/scene-spec.v2.json`, `v2.1.json`) → Unity `SceneLoader`(`unity/Assets/IFS/Runtime/Loading/SceneLoader.cs`) → `SceneParams.FromSpec` → 메시·머티리얼.
- `form.type`은 `blob | mist | shell | fragments | null`(null은 blob으로 그림). 모양 낱말(둥근·네모·납작·뾰족)은 `_unmapped`의 shape 범주를 Unity `ShapeMapping`이 읽어 Sphere/Cube/FlatCylinder/Cone 모형으로 바꾼다(blob·null일 때만).
- **형상 종류별로 실제로 다른 것은 두 가지뿐이다.** (1) `FormPresets`의 숫자 다섯 개(lumpiness, noiseScale, fuzz, density, shellOpen), (2) mist이거나 opacity < 0.99이면 `SceneSpecFade.shader`(Transparent, ZWrite Off, Cull Back, alpha = opacity × density × rim·노이즈)로 바꾸고 그림자를 끈다. blob·mist·shell은 모두 같은 icosphere(정점 2,562개)이고 fragments는 같은 구 5개다. 파티클은 쓰지 않는다.
- 결과: 안개가 "가장자리가 흐린 옅은 공"으로 보이고, 껍질은 구멍 난 공, 조각은 공 다섯 개다. opacity가 0에 가까우면 빈 화면이 된다(held-out H09: v1 opacity 0.0, v0 0.1 → 덮인 화소 21개. AC-4.5 미달의 원인).
- 형상 분포(held-out 30문장): null 17–20, blob 5–6, mist 3, fragments 2–3, shell 0–1.

## 목표
참여자가 말한 형상이 장면에서 더 그 형상답게 보이게 한다. 특히 안개 같은 반투명 형상과 단순 도형이 같은 방식(같은 메시 + 숫자만 다름)으로 그려지는 문제를 푼다.

출발점 아이디어(따를 필요 없음): (A) SceneSpec 내용에 따라 형상 종류별로 가장 잘 맞는 생성 수단을 쓴다(안개 → 투명·볼륨 표현, 단순 도형 → 프리팹). (B) 각 생성 수단이 가장 잘 받는 입력 형식으로 바꿔 넘긴다.

## 지켜야 할 것 (위에서부터 우선)
1. `AGENTS.md` 원칙. 장면 속성은 사전·규칙만 정한다(LLM·생성 모델 금지). 같은 확정 텍스트는 같은 결과. 말하지 않은 것을 시스템이 지어내지 않는다(기본값은 기본값이라고 기록). 로컬 실행.
2. v0·v1 매핑 비교가 성립해야 한다. 두 매퍼의 출력은 **같은 렌더 경로**를 타고 슬롯 값만 달라야 한다. 렌더러가 어느 매퍼의 출력인지 알면 안 된다.
3. `docs/acceptance.md` AC-4: 눈당 2064×2208 × 2눈 데스크톱 대리 측정 프레임 시간 p95 ≤ 13.9 ms, 드로콜 ≤ 100, 삼각형 ≤ 300k, 그림자 광원 ≤ 1, 빈 화면·분홍 셰이더 없음. Quest 3(모바일 GPU)에서 투명 겹침(overdraw)이 비싸다는 점을 고려하라.
4. 2026-12-02 마감 전에 검증까지 끝낼 수 있는 범위. 구현·검증에 쓸 수 있는 시간은 사실상 하루 이틀이다.
5. 후보1 소유감 러너(`unity/Assets/IFS/Runtime/Ownership/`)가 같은 로더를 쓴다. 변형본 규칙(형태 변형 = blob ↔ 다른 형태, 색 ΔE00 목표는 `RenderedColor` 기준, 회전 변형은 정점 노이즈에 기댐 — decisions X22·X23·X32·X33)이 깨지면 안 된다. 스키마(`scene-spec.v2*.json`)와 Python 매퍼 출력(v0 출력 sha256 고정 테스트)은 바꾸지 않는다.

## 이미 알고 있는 것 (되풀이하지 마라)
- 로컬 생성 모델(Shap-E, SDXL→TripoSR)을 시험했고 품질·원칙 모두에서 탈락했다(`docs/gen3d-feasibility.md`). 생성형 안은 내지 마라.
- 매퍼 쪽 문제(평서 명사 '구름이에요'가 form으로 안 잡힘, 부분 투명이 전체로 번짐)는 이번 범위가 아니다. 렌더 쪽만 다룬다.
- 헤드셋 실기는 못 한다. 데스크톱 대리 측정만 가능하다.

## 출력 (한국어, 900단어 이내)
1. 고른 구조: SceneSpec(단일 중간 표현) 뒤에 무엇을 어떻게 붙이는가(예: form별 렌더러 전략, 어댑터, 셰이더 분기). 클래스·파일 수준으로.
2. form별 표현 방법: mist / shell / fragments / blob·null / 모양 모형 각각 — 기법(메시·셰이더·파티클·겹껍질·레이마칭 등), 재질 슬롯(color, brightness, saturation, roughness, opacity, erosion)과 layout.size·motion을 어떻게 반영하는가, 예상 비용(드로콜·삼각형·투명 겹침).
3. opacity가 0에 가까울 때의 처리(빈 화면 문제): 말한 값을 왜곡하지 않으면서 무엇을 할 수 있는가.
4. v0·v1 비교, 소유감 러너 변형 규칙, golden 테스트(`LoaderNoVariantGoldenTests`)에 주는 영향과 다루는 법.
5. 마감 안에 할 범위와 구현 순서(형상 종류 하나씩), 미룰 것.
6. 검증 방법: 무엇을 재면 "더 그 형상답다"를 사람 없이 가늠할 수 있는가(배치 캡처 report.json에 넣을 지표).
7. 버린 대안과 이유, 이 안의 가장 큰 위험 3개.
