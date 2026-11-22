# D3 — Claude 하위 에이전트 독립안 (2026-11-23)

## 1. 고른 구조

SceneSpec → `SceneParams.FromSpec`(그대로) → **`FormRenderPlan`**(새 파일, 순수 C#) → **form별 빌더**.

- `Runtime/Loading/Forms/FormRenderPlan.cs`: `SceneParams`와 `ShapeResolution`만 받아 `{builder, transparencyModel, slots}`를 낸다. `meta`·매퍼 판·세션 id는 받지 않는다(v0·v1 구분 불가를 타입으로 보장). 난수는 쓰지 않고 고정 상수 표만 쓴다.
- `IFormBuilder { GameObject Build(Shader set); void Apply(MaterialSlots s); }` 구현 4개: `BlobBuilder`(지금 코드 이동, 변경 없음), `ShapeModelBuilder`(지금 `BuildShapeModel` 이동), `FragmentsBuilder`(새 메시), `MistVolumeBuilder`(새 셰이더). shell은 `BlobBuilder`에 프리셋만 다르게(지금과 같음).
- `SceneLoader.BuildHierarchy`·`ApplyMaterial`은 빌더에 위임만 한다. 색은 계속 `RenderedColor`, 밀도는 `FormPresets`를 공개해 변형 생성기 `FormDensity`가 같은 표를 읽게 한다(지금은 두 곳에 복사됨).
- 셰이더: `SceneSpecMist.shader`(새, 정점·조각 셰이더), `SceneSpecClear.shader`(새, `alpha:premul`). `SceneSpecFade`는 대체용으로 남긴다.

## 2. form별 표현

| form | 기법 | 슬롯 반영 | 비용(눈당) |
|---|---|---|---|
| mist | 구 대리 메시(icosphere 2단, 320 삼각형)를 `Cull Front`·`ZWrite Off`로 그리고, 조각 셰이더가 물체 좌표에서 광선-구 교차 → 고정 16걸음 레이마칭. 밀도 = 구 안쪽 감쇠 × 값 노이즈 2옥타브(`ifsNoise` 재사용). 시작점 max(0, t_enter)라 카메라가 안에 있어도 보인다 | color·saturation·brightness → `RenderedColor`와 같은 알베도×밝기 배율(0.5 초과는 발광). opacity → 흡광 계수, 중심 광선 누적 α = `SurfaceAlpha`(opacity × 0.5)로 보정. roughness → 2옥타브 가중. erosion → 밀도 문턱(끊긴 가닥). size·motion → Transform만. **말하지 않은 내부 흐름은 넣지 않는다** | 1 드로콜, 투명 겹침 1층, 그림자 없음. 화소당 16걸음 × 노이즈 2회(위험 1) |
| fragments | **각진 조각 7개를 한 메시로**: icosphere 1단(80 삼각형)을 고정 상수로 비균등 축척·CPU 변위, 평면 법선, 공통 중심에서 바깥으로 벌린 "깨진 덩어리" 배치. `_Displacement` 0 | 지금 불투명 경로 그대로 | 렌더러 1개, 2패스+그림자, 약 560 삼각형 |
| shell | 지금 유지(위가 열린 구 + 안쪽 면 어둡게) | 그대로 | 그대로 |
| blob·null | 지금 유지(null은 blob, 기본값 기록) | 그대로 | 2패스+그림자, 5,120 삼각형 |
| 모양 모형 | 지금 유지(blob·null에만) | 그대로 | 그대로 |

## 3. opacity ≈ 0 처리

값을 올리지 않는다(하한 0.15 같은 바닥값은 원칙 2 위반). 대신 **opacity의 뜻을 "확산색이 배경을 가리는 정도"로 고정**한다.

- mist가 아닌 형상이 opacity < 0.99이면 `SceneSpecClear`(`alpha:premul`)로 그린다. Unity Standard의 Transparent 모드처럼 확산색만 α로 줄고 정반사·Fresnel은 남는다(Unity 문서 기준. 이 저장소 하늘에서 반사가 실제로 보이는지는 **확인 필요**). 말한 "투명한"은 유리처럼 맑은 물체로 보이고, 사라지지 않는다.
- mist는 흡광(opacity)과 산란광(밝기·밀도장)을 나눈다. opacity 0의 안개는 배경을 가리지 않는 옅은 빛 기운으로 보인다. 이것은 슬롯을 다시 해석하는 일이므로 decisions에 적는다.
- 기록: `report.json`·`initialScene.json`에 `opacityStated`(= 적용값, 변경 없음), `transparencyModel: "clear-specular" | "volume-absorb-scatter"`, `nearInvisible`(확산 α < 0.05)을 남긴다.
- 그래도 거의 안 보이면 억지로 보이게 하지 않고 `nearInvisible`로 표시한다. 조건부 표지(바닥 고리 등)는 넣지 않는다.

## 4. v0·v1, 소유감 러너, golden

- v0·v1: `FormRenderPlan`의 입력에 매퍼 정보가 없다. 테스트 하나로 고정한다: 같은 SceneParams + 다른 `meta` → 같은 계획.
- 소유감: X23(mist·shell·fragments → blob)은 그대로 성립한다. X33 색 목표는 `RenderedColor` 공유라 그대로다. 합성 ΔE 기록용 `SurfaceAlpha`는 mist 보정 기준과 같다. **X32 회전 가시성**: 안개 노이즈와 조각 형상이 모두 물체 좌표라 돌면 무늬가 함께 돈다. 다만 안개 대비가 약하면 흔들림이 안 보일 수 있으므로, 회전 전후 캡처의 화소 차이를 EditMode 표 테스트에 추가한다.
- golden: 바뀌는 블록은 GOLD-mist와 opacity < 0.99인 예시 spec뿐이다. `IFS_WRITE_LOADER_GOLDEN=1`로 한 번 다시 만들되, **바뀐 spec 블록 목록이 예상 목록과 같은지** 검사한다(불투명 blob·모양 블록은 바이트 동일). 이유는 decisions에 남긴다.

## 5. 마감 안 범위와 순서

1. (반나절) `SceneSpecClear` + `transparencyModel` 기록 + `visiblePixels` 지표. AC-4.5(H09)를 바로 겨냥한다.
2. (반나절) `MistVolumeBuilder` + 셰이더, 중심 α 보정 테스트.
3. (반나절) `FragmentsBuilder`.
4. (반나절) held-out 60장 + 합성 스윕 배치 캡처, golden 재생성, Codex 검토.

미룰 것: shell 개선(held-out 0–1건), Texture3D 노이즈 최적화, 바닥과 겹친 안개의 깊이 처리(`_CameraDepthTexture`), Single-pass instanced 대응(`unity_StereoWorldSpaceCameraPos`, **확인 필요**), 기기 실측.

## 6. 검증(사람 없이)

`BatchCapture`가 이미 만드는 화소별 덮임 a(흑·백 배경 차)에서 계산해 `report.json` spec별로 넣는다.

- `visiblePixels`: 형상이 있는 장면과 없는 장면의 화소 ΔE00 > 2인 수. premul 정반사는 a에 잡히지 않으므로 빈 화면 판정은 이 값으로 한다.
- `softFraction`: 0.05 < a < 0.95 화소 비율(mist는 높고, blob은 0 근처).
- `edgeWidthNorm`: 중심에서 바깥으로 낸 방사 프로파일 16개의 a 10→90% 전이 폭 / 상자 크기.
- `components`(a ≥ 0.5 연결 성분 수, fragments ≥ 3), `solidity`(면적 / 볼록 껍질 면적, fragments 낮음).
- `centerAlphaVsSurfaceAlpha`: mist 보정 오차.
- 판정은 **구현 전에 정한 form별 기대 범위**로 한다(예: mist softFraction ≥ 0.5, blob ≤ 0.05). 옛·새 렌더러를 같은 spec에 돌려 form 간 분리(효과 크기)를 비교한다. 합성 스윕 form 4 × opacity {0, 0.1, 0.5, 1} × size {0, 1}, 최근접·최대 안개는 p95 최악 사례로 따로 잰다.

## 7. 버린 대안과 위험

- ParticleSystem 안개: 결정성 관리가 어렵고 겹침이 여러 층이며, 말하지 않은 흐름이 생긴다.
- 겹껍질 안개: 겹침 N층, 결국 "공 여러 겹"이다.
- 빌보드 안개: 두 눈에서 방향이 달라 입체 불일치.
- opacity 하한: 말한 값 왜곡.
- form별 아티스트 프리팹·전 형상 SDF: 시간·비용 초과.

**가장 큰 위험 3개**
1. 안개 레이마칭의 채움 비용: 0.3 m·최대 크기면 화면 전체 × 두 눈이 된다. 데스크톱 대리 측정은 Quest 모바일 GPU 비용을 드러내지 못한다. 걸음 수를 화면 크기에 따라 줄이는 장치를 미리 둔다.
2. opacity 재해석(확산 α + 남는 정반사·산란): 이전 캡처·`SurfaceAlpha`·합성 ΔE와 뜻이 어긋날 수 있고, "시스템이 가시성을 더했다"는 비판을 받을 수 있다. decisions 기록과 v0·v1에 똑같이 적용하는 것이 전제다.
3. golden 재생성이 의도하지 않은 변경을 덮거나, 안개 대비가 약해 X32 회전 가시성 표가 틀어질 수 있다. 바뀐 블록 목록 검사와 회전 화소 차 테스트로 막는다.
