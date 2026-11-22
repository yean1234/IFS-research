너는 이 연구 저장소의 외부 감시자(코드 리뷰어)다. 파일을 수정하지 말고 읽기만 해라. 한국어로 답하라.

## 맥락
- 연구: 면담 확정 텍스트 → 사전·규칙 매퍼(v0·v1) → SceneSpec JSON → Unity 형상. 저장소 원칙은 AGENTS.md.
- 2026-11-23에 Unity 렌더 경로를 **형상 종류별 렌더 전략**으로 바꿨다. 설계 결정은 docs/decisions.md 마지막에서 두 번째 절 "형상 종류별 렌더 경로"(X64–X72). 네가 D3에서 낸 안과 다른 부분(mist를 8걸음 레이마칭으로 함 등)이 있다는 것을 안다. 같은 설계 반론을 되풀이하지 말고 **채택된 결정의 구현이 결정·원칙과 어긋나는 곳**을 찾아라.
- 변경 커밋: `git log --oneline 1f159b8..HEAD`, `git diff 1f159b8 HEAD --stat`. 주요 파일:
  - unity/Assets/IFS/Runtime/Rendering/FormRenderPlan.cs, FormRenderers.cs, FragmentMesh.cs
  - unity/Assets/IFS/Runtime/Resources/IFS/SceneSpecMist.shader, IFSSceneSpecCommon.cginc
  - unity/Assets/IFS/Runtime/Loading/SceneLoader.cs, unity/Assets/IFS/Editor/BatchCapture.cs, Editor/SilhouetteMetrics.cs
  - 테스트: unity/Assets/IFS/Tests/Editor/ 의 FormRenderPlanTests, SilhouetteMetricsTests, FragmentMeshTests, MistShaderSourceTests, UnityOnly/FormRendererTests, MistRendererTests, Golden/loader_no_variant.golden.txt
  - docs/validation/render/ (합성 spec 13개, before/after report.json, compare.py, README.md, sheet.png), unity/README.md, docs/HANDOFF.md
- 테스트 결과(실행 확인됨): dotnet 201/201, Unity EditMode 237/237, pytest 443 통과.

## 이미 알고 있는 것 (되풀이하지 말 것)
- 헤드셋 실기 미검증. Quest에서의 셰이더 컴파일·레이마칭 채움 비용·단일 패스 인스턴싱은 확인하지 못했다.
- shell은 바꾸지 않았다(X69). opacity가 0에 가까우면 계속 거의 안 보인다(X70, 일부러 보정하지 않음). 매퍼 쪽 문제는 범위 밖.
- 새 지표(circularity, components, edgeFalloffPx, visiblePixels)는 대리 지표일 뿐 사람 판정이 아니다. edgeFalloffPx는 둘레로 나누는 정의라 윤곽이 울퉁불퉁해지면 작아진다.
- fragments는 화면을 덮는 면적이 약 35–40% 줄었고, 평면 음영 때문에 화면에서 잰 색 ΔE00이 5 → 9–11로 커졌다.
- mist는 Cull Front만으로는 바닥 위 안개가 깊이 테스트에 가려 사라져서, Cull Off 한 패스에서 카메라 위치로 면을 고르고 `_FloorY` 아래 밀도를 0으로 했다.
- 소유감 러너의 형태 변형 자극이 이전과 달라진다(X71).

## 할 일과 관점
1. **v0·v1 비교 조건(X65)**: `FormRenderPlan`·렌더러·셰이더·BatchCapture 어디에서든 매퍼 정보(meta.mapping, specVersion, 파일 이름 등)에 따라 화면이 달라지는 경로가 있는가. 같은 슬롯 값이면 2.0.0 문서와 2.1.0 문서가 같은 화면을 내는가.
2. **결정성**: fragments 메시·mist 노이즈·seed가 같은 SceneSpec에서 항상 같은가. 플랫폼·프레임률·카메라 위치·시간에 따라 달라지는 값(시간 기반 노이즈, Random, 해시의 부동소수 차이, 카메라 의존 지터)이 섞였는가. seed가 무엇에서 나오는가.
3. **말한 값의 보존(원칙 2, X70)**: opacity·color·brightness·saturation·roughness·erosion·layout.size·motion이 새 렌더러에서 기존과 같은 뜻으로 반영되는가. 특히 (a) mist의 opacity → 밀도 대응이 기존 `SurfaceAlpha`와 어떻게 다른지와 그 차이가 기록·문서에 있는지, (b) fragments의 덮는 면적 감소가 layout.size의 뜻을 바꾸는지, (c) `_FloorY` 자르기가 verticalOffset으로 말한 위치를 왜곡하는지, (d) 형상 프리셋 기본값(조각 수 등)이 "말한 것"처럼 기록되는 경로가 있는지, (e) `SceneParams.ToRecord`·report.json의 적용값 비교(|Δ| ≤ 1e-6, AC-5)가 그대로 성립하는지.
4. **소유감 러너와의 정합(X71, X32, X33)**: 색 변형의 ΔE00 목표가 `RenderedColor`(알베도) 기준인데 fragments 평면 음영·mist 부피 셰이딩에서 이 함수가 여전히 실제 화면 색의 기준으로 타당한가. 회전 변형이 fragments·mist에서 보이는가. `UsesFadeShader` 등 러너가 기대는 함수의 뜻이 바뀌었는가. 배치 러너(Placement)의 잡기 반지름·`object.boundingRadiusM`이 새 메시 바운즈에서 맞는가.
5. **성능·셰이더 정확성(AC-4)**: mist 셰이더의 블렌딩·ZWrite·ZTest·큐, 카메라가 구 안에 있을 때, 불투명 물체·바닥과의 교차, 여러 형상이 겹칠 때 정렬, 모바일(GLES3/Vulkan) 문법, 단일 패스 스테레오 매크로 누락, 루프 상수. 드로콜·삼각형 "추정치"의 계산이 새 메시에 맞게 갱신됐는가.
6. **지표 계산(SilhouetteMetrics, compare.py)**: circularity·components·visiblePixels 정의의 오류, 배경과의 차이 임계값, 눈 2개 처리, before/after가 같은 조건으로 계산됐는가.
7. **테스트**: golden이 무엇을 고정하고 무엇을 놓치는가(fragments 항목이 golden에 없음). 항상 통과하는 테스트, 빠진 경계(opacity 0, size 극단, form null, 셰이더 미발견 대체 경로).
8. **문서 불일치**: docs/validation/render/README.md·unity/README.md·HANDOFF의 수치·설명이 코드·report.json과 다른 곳. AGENTS.md 원칙 위반(절대 경로, 참여자 자료, 외부 호출).

## 출력 형식
지적 사항 번호 목록. 각 항목 [심각도: 높음/중간/낮음], 위치(파일:줄), 문제, 근거(재현 입력 또는 코드 경로), 제안. 심각도 높음부터. 최대 12개. 마지막에 총평 3줄. 칭찬은 생략.
