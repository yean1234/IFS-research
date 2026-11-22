# CP8 — 형상별 렌더 경로 구현 검토 (Codex 독립 검토)

- 일시: 2026-11-23
- 호출: `codex exec --sandbox read-only -c model_reasoning_effort="medium"` (사용량 한도 사용률 2%)
- 프롬프트: `docs/codex-reviews/prompts/CP8_prompt.md`
- 검토 대상 커밋: `1f159b8..f98306d`
- 판정(수용/반박/보류)은 `docs/decisions.md` X73–X78에 적습니다.

---

1. **[심각도: 높음]** 위치: [BatchCapture.cs](<repo>/unity/Assets/IFS/Editor/BatchCapture.cs:256)  
   **문제:** 캡처의 색 측정 경로가 실제 렌더러 대신 `RenderedColor.UsesFadeShader(form.type, opacity)`로 셰이더를 고릅니다. 새 `mist` 렌더러는 opacity가 낮아도 `SceneSpecMist`를 사용하므로 이 판정과 실제 렌더 경로가 다릅니다. 따라서 mist의 캡처 색 지표는 실제 부피 셰이딩 결과를 나타내지 않을 수 있습니다.  
   **근거:** `mist`, opacity 0.6 입력에서 `fade`는 true지만 실제 렌더러는 `MistRenderer`입니다. 코드가 `MeasureColor`에 이 `fade` 값을 전달합니다.  
   **제안:** `loader.RenderPath` 또는 `RenderPlan.Renderer`에 맞춰 색 측정 경로를 선택하고, mist는 실제 셰이더의 측정 의미를 별도로 기록하십시오.

2. **[심각도: 중간]** 위치: [SceneSpecMist.shader](<repo>/unity/Assets/IFS/Runtime/Resources/IFS/SceneSpecMist.shader:146)  
   **문제:** `material.roughness`가 밀도 노이즈 크기뿐 아니라 조명 얼룩의 세기에도 영향을 줍니다. 기존 표면 셰이더에서 roughness는 표면 반사 특성인데, mist에서는 값의 뜻이 달라져 같은 슬롯 값이 형상 종류별로 다른 속성을 제어합니다.  
   **근거:** `noiseMul = lerp(0.7, 1.3, _Roughness)`와 167행의 roughness 기반 색 변조.  
   **제안:** 이 형상에서 roughness를 노이즈·색 변조로 쓰는 의미를 프로토콜·문서에 명시하고, 보고서에 실제 적용 효과를 분리해 기록하십시오.

3. **[심각도: 중간]** 위치: [FormRenderPlan.cs](<repo>/unity/Assets/IFS/Runtime/Rendering/FormRenderPlan.cs:115)  
   **문제:** fragments의 `PresetNote`는 조각 수·seed·평면 음영·변위 0만 알리고, 조각 생성에 쓰이는 배치·크기·방향 기본 규칙은 빠져 있습니다. 노트가 기본값을 기록한다는 문서 설명에 비해 실제 기록은 완전하지 않습니다.  
   **근거:** 계획 JSON에는 조각 수와 seed만 있고, `FragmentMesh.Build`의 배치·방향 생성 규칙은 기록되지 않습니다.  
   **제안:** 생성 규칙의 버전이나 파라미터를 계획·보고서에 포함해 같은 seed라도 규칙 변경을 추적할 수 있게 하십시오.

4. **[심각도: 중간]** 위치: [SceneLoader.cs](<repo>/unity/Assets/IFS/Runtime/Loading/SceneLoader.cs:673)  
   **문제:** mist는 월드 높이가 `_FloorY` 아래인 샘플의 밀도를 0으로 잘라냅니다. 따라서 참여자가 말한 `layout.verticalOffset`이 바닥 아래를 가리키면 중심 위치는 유지되어도 형상의 하부가 잘려 보입니다. 위치 슬롯과 렌더 결과의 대응이 달라집니다.  
   **근거:** `ApplyLayout`은 verticalOffset으로 중심 높이를 정하고, 셰이더는 동일 형상의 floor 아래 부분만 제거합니다.  
   **제안:** 보고서에 실제 형상 중심과 floor 절단 여부를 함께 기록하고, 수직 위치 변형을 평가할 때 절단 영향이 분리되도록 하십시오.

5. **[심각도: 낮음]** 위치: [SceneSpecMist.shader](<repo>/unity/Assets/IFS/Runtime/Resources/IFS/SceneSpecMist.shader:143)  
   **문제:** 주석은 중심 알파가 `opacity × density`라고 설명하지만, 실제 레이마칭은 공간 노이즈·형상 감쇠·바닥 절단을 합산한 광학 깊이입니다. `IFS_MIST_CENTER_INTEGRAL = 1.0`은 근사 보정이라 평균 밀도와 모든 시선에서 그 관계가 성립하지 않습니다. 기존 `SurfaceAlpha`와 동등하다는 표현은 캡처된 실제 알파 의미를 과도하게 단순화합니다.  
   **근거:** opacity와 density는 목표 알파로 바뀐 뒤 각 샘플의 `d`에 따라 누적됩니다(144–172행).  
   **제안:** 코드 주석과 문서에서 이를 “중심 광선의 목표 근사”로 한정하고, 실제 최대·평균 알파와 목표값을 구분해 기록하십시오.

6. **[심각도: 낮음]** 위치: [SceneSpecMist.shader](<repo>/unity/Assets/IFS/Runtime/Resources/IFS/SceneSpecMist.shader:141)  
   **문제:** 주석은 고정 지터가 결정적이라고 설명하지만, 코드의 `jitter = 0.5`는 지터가 아니라 항상 샘플 중점입니다. 시간·Random 변동은 없으나 주석이 구현 동작을 잘못 설명합니다.  
   **근거:** 샘플 위치가 매 프레임 `t0 + (k + 0.5) * dt`로 고정됩니다.  
   **제안:** “중점 샘플링”으로 주석을 고치거나, 실제 지터를 추가한다면 시간·카메라 의존 없이 표면 좌표에서 결정되도록 하고 그 동작을 테스트하십시오.

총평: 확인한 렌더 계획에는 매퍼 메타데이터를 참조하는 경로가 없고, fragments 생성과 mist 샘플링에도 프레임 시간 기반 난수는 보이지 않습니다.  
가장 실질적인 검증 문제는 캡처 색 측정이 mist의 실제 셰이더 경로와 다를 수 있다는 점입니다.  
mist roughness와 floor 절단은 말한 값의 의미·형상 보존을 해석할 때 보고서에서 구분할 필요가 있습니다.
