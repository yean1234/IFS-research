# unity — VR 앱

VR 세션(스토리보드 「P07의 25분」의 안전 기지 → Find → Focus → 렌더 → 보정 → Feel toward → 컨테인먼트)을 만들 Unity 쪽입니다. 계획된 스택은 Unity XRI + Quest 3입니다(노션 「인터렉션 디벨롭」).

지금 들어 있는 것은 **SceneSpec 로더**입니다. 챗봇이 확정 텍스트로 만든 장면 JSON(`chatbot/logs/scenes/{sessionId}.json`)을 읽어 VR 오브젝트를 띄우고, 참여자 조정을 기록합니다. Holodeck(CVPR 2024)의 "구조화된 장면 JSON → Unity" 구조와 같고, 가운데에 LLM이 없습니다.

```text
unity/
├─ Assets/
│  ├─ IFS/
│  │  ├─ Runtime/                         IFS.SceneSpec.asmdef (Newtonsoft.Json 참조)
│  │  │  ├─ SceneSpec/SceneSpecV2.cs       데이터 클래스 (shared/schemas/scene-spec.v2.json과 1:1)
│  │  │  ├─ SceneSpec/SceneSpecJson.cs     엄격 파싱(모르는·빠진 필드 = 오류) + 원칙 검사
│  │  │  ├─ SceneSpec/SceneParams.cs       null → 기본값(무엇을 채웠는지 기록), 0–1 조정, 조정량
│  │  │  ├─ Recording/ExperimentRecorder.cs initialScene.json · finalScene.json · events.csv
│  │  │  ├─ Loading/                       SceneLoader · InspectorPathSource · ISceneSpecPathSource · SpecMotion
│  │  │  ├─ Environment/                   EnvironmentBuilder(코드로 만드는 중립 환경) · IFSEnvironment(씬 컴포넌트)
│  │  │  ├─ SceneSpec/ColorMetrics.cs      sRGB↔Lab, CIEDE2000 (색 정확도 측정)
│  │  │  ├─ SceneSpec/ShapeMapping.cs · ConeMesh.cs  모양어 → 모양 모형 판정, 원뿔 메시 (docs/shape-mapping.md)
│  │  │  ├─ SceneSpec/SceneOverride.cs · MotionGroups.cs  변형본 덮어쓰기, motion.type → 움직임 묶음 표
│  │  │  └─ Ownership/                     소유감 실험: 변형본 생성기 · 러너 · 머리 자세 · 기록 (아래 「소유감 실험」)
│  │  ├─ Editor/                          메뉴: 예시 테스트 씬 다시 만들기 · Create Shape Prefabs · BatchCapture(배치 캡처·성능 측정) · Ownership 실험 씬·자동 시행
│  │  ├─ Runtime/Rendering/              형상별 렌더 경로: FormRenderPlan(슬롯 값 → 렌더러 입력) · IFormRenderer(blob·mist·shell·fragments·shapeModel·base:*) · FragmentMesh · BaseShapeMesh(기본 형상 5개, D6)
│  │  ├─ Runtime/Resources/IFS/          셰이더(Built-in): SceneSpec Opaque · Fade · Mist(부피 레이마칭) + 공통 노이즈, Environment Floor · Sky
│  │  ├─ Tests/Editor/                    EditMode 테스트(아래 「테스트」), UnityOnly/ = Unity에서만 도는 것
│  │  ├─ Runtime/Preview/                 형상 미리보기(D4): PreviewStage(무대) · PreviewBridge(JS 진입점) · PreviewQueue(상주 플레이어) · Plugins/WebGL/IFSPreview.jslib
│  │  └─ Scenes/                          SceneSpecExamples.unity(예시 2개 테스트 씬) · OwnershipExperiment.unity(소유감 실험) · Preview.unity(미리보기)
│  ├─ WebGLTemplates/IFSPreview/          WebGL 미리보기 페이지(외부 자원 없음, window.ifsPreview)
│  ├─ Prefabs/Shapes/                     모양 모형 프리팹 4개(Sphere · Cube · FlatCylinder · Cone) + 원뿔 메시 + 머티리얼(메뉴가 만듦)
│  └─ StreamingAssets/IFS/examples/       EX01.json · EX02.json (chatbot/tests/fixtures/scene_spec와 바이트까지 같음)
│     StreamingAssets/IFS/ownership_task.v0.2.json  소유감 실험 참여자 문구(초안, IRB 대상. v0.json = 닮음 문항 이전 '내 것' 5조건용, G57로 version 0.2)
└─ Tools/compile-check/                   Unity 없이 C# 컴파일·테스트(dotnet). Assets 밖이라 Unity는 무시
```

UnityEngine에 의존하지 않는 부분(데이터 클래스·파싱·파라미터·기록기)과 MonoBehaviour(로더·움직임·경로)를 나눴습니다. 앞쪽은 dotnet으로 실제 컴파일·실행해 확인했습니다.

## Unity 에디터에서 할 일

1. **프로젝트 준비** — Unity Hub ▸ Projects ▸ Add ▸ *Add project from disk* ▸ 이 `unity/` 폴더. 에디터 버전은 6000.0.85f2(`ProjectSettings/ProjectVersion.txt`)입니다. 색공간·품질 설정은 아래 「환경과 품질 설정」을 따릅니다. 이미 Quest 프로젝트가 있으면 `Assets/IFS/`와 `Assets/StreamingAssets/IFS/`를 그 프로젝트의 `Assets/` 아래로 복사합니다(`.meta`도 같이 — 테스트 씬이 스크립트 GUID로 연결돼 있습니다). Unity 2022.3 LTS 이상 / Unity 6 기준(C# 9)으로 썼습니다.
2. **패키지** — Package Manager ▸ `+` ▸ *Add package by name* ▸ `com.unity.nuget.newtonsoft-json`(3.2.1 이상). 테스트를 돌리려면 `com.unity.test-framework`(새 프로젝트에는 보통 있음). 로더는 XR Interaction Toolkit 없이도 컴파일됩니다.
3. **테스트** — Window ▸ General ▸ Test Runner ▸ EditMode ▸ *Run All* → 134개 통과해야 합니다(2026-11-17 기준, 배치모드 명령은 아래 「테스트」).
4. **테스트 씬** — `Assets/IFS/Scenes/SceneSpecExamples.unity`를 열고 Play. 중립 환경(회색 바닥·1 m 격자·하늘·방향광 그림자)이 먼저 만들어지고, 왼쪽이 EX01(회색 덩어리, 가슴 높이), 오른쪽이 EX02(웅크린 작은 형상). Console에 "SceneSpec 값이 null → 기본값 … 사용" 줄과 기록 폴더 경로가 나옵니다. 씬이 열리지 않으면 메뉴 **IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기**.
5. **형태 모형** — 프리팹이 없어도 기본 절차 모형이 뜹니다: 잘게 나눈 구를 `IFS/SceneSpec` 셰이더가 노이즈로 밀어 형태별로 다르게 보이게 합니다(blob 울퉁불퉁한 덩어리, shell 위가 깨져 열린 껍데기). mist는 구 대리 메시 + 부피 레이마칭 셰이더(`IFS/SceneSpec Mist`)로 몽글몽글한 안개, fragments는 각진 조각 5개를 합친 메시 하나입니다(아래 「형상별 렌더 경로」). 디자이너가 만든 에셋이 생기면 SceneLoader ▸ *Form Prefabs* 4칸에 넣으면 그쪽이 우선입니다. 참여자가 모양어(동그랗다·네모·납작하다·뾰족하다)를 말했으면 구·큐브·납작 원기둥·원뿔 모형으로 바꿉니다(spec `_unmapped`의 모양어, `form.type`이 null·blob일 때만). 프리팹은 메뉴 **IFS ▸ Create Shape Prefabs**가 만들고 연결합니다. 규칙·기록은 `docs/shape-mapping.md`. 이 셰이더는 **Built-in 렌더 파이프라인 전용**이라 URP로 바꾸면 지원되지 않고 임시 프리미티브로 돌아갑니다(그때 Shader Graph 판이 필요).
6. **직접 만든 셰이더를 쓸 때** — 아래 Reference 이름으로 프로퍼티를 만들면 로더가 값을 넣습니다. 이름이 다르면 SceneLoader ▸ *Shader Params*에서 바꿉니다.
7. **챗봇 출력 연결** — InspectorPathSource ▸ *Spec Path*에 `…/chatbot/logs/scenes/{sessionId}.json`의 절대 경로를 넣습니다(상대 경로는 StreamingAssets 기준).
8. **참여자 조정 입력** — 컨트롤러·슬라이더(XRI)를 `SceneLoader.SetNumber("material.brightness", v)`, `SetCategory("form.type", "mist")`, 끝날 때 `SaveFinal()`에 연결합니다. 이 연결 UI는 아직 없습니다.

## 파라미터 → Unity

| SceneSpec | Unity | null이면(기본값, Inspector에서 변경) |
| --- | --- | --- |
| `form.type` | Form Prefabs에서 고름 | `blob` |
| `_unmapped`의 모양어(round · square · flat · pointed) | Shape Prefabs에서 고름(Sphere · Cube · FlatCylinder · Cone). `form.type`이 null·blob일 때만. 표에 없는 모양어는 경고·기록만 | 모양어 없음 → `form.type` 모형 |
| `form.posture` | 크기 변형 프리셋(웅크림 y×0.7, 납작 y×0.5–0.6, 곧음 y×1.2) | 변형 없음 |
| `material.color` (+`saturation`) | `_BaseColor` (Built-in은 `_Color`), 알파 = opacity | h 0, s 0, l 0.7 |
| `material.brightness` | `_Brightness` (없으면 `_EmissionColor`로 근사) | 0.5 |
| `material.roughness` | `_Roughness` (기본 셰이더: 광택↓ · 얼룩↑ · 잔요철↑, 없으면 URP `_Smoothness` = 1 − r. mist 안개 셰이더에서는 광택이 아니라 노이즈 크기 배율·얼룩, 아래 형상별 렌더러 표) | 0.5 |
| `material.opacity` | `_Opacity` | 1 |
| `material.erosion` | `_Erosion` (기본 셰이더: 노이즈로 구멍을 뚫고 가장자리를 어둡게 삭은 색으로) | 0 |
| `layout.size` | 크기 배율 2^((size − 0.5) × 4) | 0.5 (×1) |
| `layout.distance` | 머리에서 수평 0.3 m + d × 2.7 m | 0.33 (≈1.2 m) |
| `layout.verticalOffset` | 바닥 + v × 키(키 = 로드 순간 눈높이 / 0.936) | 0.75 |
| `motion.type` · `motion.speed` | SpecMotion 9묶음(흔들림·떨림·맥동·떠다님·가라앉음·회전·퍼짐·다가옴·정지), 0.1–1.5 Hz | still · 0.5 |
| (2.3) `form.roundness` | 기본 덩어리 경로(form.type null·blob, 기본 형상·모양 모형 없음)일 때만 슈퍼쿼드릭 메시(e1 = e2 = 0.1 · 0.3 · 0.5 · 0.75 · 1.0, 경도 48 × 위도 24, 정점 변위·굴곡 0). 그 밖이면 그리지 않고 `contour.status = not_applied_form · not_applied_base · not_applied_model` | 기본 덩어리 메시 그대로(길쭉함만 말했으면 `defaultsUsed`에 `form.roundness`) |
| (2.3) `form.aspect` | 같은 경로에서 국소 배율 × (x, y, z): elongated (0.5, 1, 0.5) … flattened (1, 0.4, 1). 긴 축 = 1, 긴 축 방향 세로 y는 기본값(`defaultsUsed`에 `form.aspect.axis`) | 배율을 곱하지 않음(둥긂만 말했으면 `defaultsUsed`에 `form.aspect`) |
| (2.3) `material.emission` | 모든 형상 경로에서 셰이더 발광 항 `_IfsEmission` = 바탕색(셰이더 알베도 식, 선형) × 세기 none 0 · faint 0.35 · glowing 1.0. 새 색·블룸 없음 | 셰이더 값을 건드리지 않음(기본 검정 → 2.2와 같은 화소) |

- 기본값을 쓴 키는 콘솔과 `initialScene.json`의 `defaultsUsed`에 남습니다. 분석 때 "참여자가 말한 값"과 섞지 않기 위해서입니다.
- **SceneSpec 2.0.0–2.3.0을 읽습니다**(2026-11-26, G61 ①). 2.3.0은 `form.roundness`·`form.aspect`·`material.emission`(서수 단계 이름, null 허용)과 선택 필드 `_provenance[].variant`를 더합니다. 엄격 파서는 그대로이고(모르는 키·표에 없는 단계 이름은 파싱 오류), 2.0–2.2 문서와 세 값이 모두 null인 2.3 문서는 전과 같은 메시·머티리얼·화소·기록입니다(`specVersion`, 원문의 세 키, 2.3 전용 기록 키 `contour`·`emission`만 다름 — `UnityOnly/ContourLoaderTests`). 적용 순서·기록 형식은 `docs/scene-spec-mapping.md` 8.4절, 수치는 `shared/lexicon/scene_params.v3.json` `render`를 옮긴 `Runtime/SceneSpec/ContourRender.cs`(pytest `test_g61_unity_contour.py`가 대조). 명세의 `_EmissionColor` 대신 `_IfsEmission`을 씁니다: Built-in Standard의 예약 이름(키워드 `_EMISSION`·GI 발광)이고, 밝기 대체 경로와 golden 지문이 그 이름의 유무를 읽어 IFS 셰이더에 더하면 2.0–2.2 지문이 바뀌기 때문입니다. 그림: `docs/validation/scene-spec-2.3/README.md`.
- `_inferred`(3층 V/A/D 제안)는 *Use Inferred Suggestions*를 켜야만 씁니다. 기본은 꺼짐입니다(원칙: 말하지 않은 것을 추론하지 않는다).

## 기록 (참여자 데이터 — git 밖)

`Application.persistentDataPath/IFS/sessions/{sessionId}/` (SceneLoader ▸ *Record Root*로 변경). 같은 세션을 다시 띄우면 덮어쓰지 않고 `rerun-…/` 하위 폴더에 씁니다.

| 파일 | 내용 |
| --- | --- |
| `initialScene.json` | 처음 로드한 값(`params`, 0–1), `defaultsUsed`, `inferredUsed`, 로더 메모(`notes`: 프리미티브 대체, 없는 셰이더 프로퍼티 …), 읽은 SceneSpec 원본(`spec`) |
| `finalScene.json` | 참여자 조정 후 값, `deltas`(초기 → 최종, 색상은 원형 거리), `adjustedParams`, `adjustmentRms`(잠정 지표), `elapsedMs` |
| `events.csv` | `time_ms,param,from,to,distance_m` — 조정 한 번에 한 줄. `distance_m` = 그 순간 머리–오브젝트 거리 |

## 경로 전달

- 지금: **InspectorPathSource** — Inspector에 경로를 입력.
- 자리만: **ISceneSpecPathSource** 인터페이스. 로컬 HTTP 방식(파이썬이 확정 직후 경로를 보내면 Unity가 로드)은 이 인터페이스를 구현하는 클래스 하나로 붙입니다. 파이썬 쪽에는 `GET /api/sessions/{id}/scene`(경로 + 장면)이 이미 있습니다(`shared/api/README.md`).

## Quest에서 주의

- Android(Quest)에서는 StreamingAssets가 APK 안에 있어 `File.ReadAllText`로 읽을 수 없습니다. 기기에서는 `Application.persistentDataPath` 아래 절대 경로(adb push)나 HTTP 방식을 씁니다.
- Quest 단독 실행에서 `127.0.0.1`은 헤드셋 자신입니다. PC의 면담 서버에 붙으려면 Quest Link(PC VR)나 `adb reverse tcp:8000 tcp:8000`을 씁니다. 서버를 LAN에 여는 것은 기본 원칙(로컬 실행, AGENTS.md 5)과 맞는지 먼저 확인합니다.

## 환경과 품질 설정

목표는 두 가지입니다. 형상이 공간에 놓여 있다는 현실감(바닥·그림자·재질)을 주고, 동시에 형상 색이 SceneSpec 색에서 크게 벗어나지 않게(일치도 평가의 공정성) 합니다. 주변 환경은 형상의 색 지각을 끌어가지 않도록 무채색으로 둡니다.

### 프로젝트 설정

| 항목 | 값 | 이유 |
| --- | --- | --- |
| 색공간 | **Linear** (전에는 Gamma) | 조명 계산을 선형 공간에서 합니다. spec의 sRGB 색이 셰이더 안에서 선형으로 바뀌어 빛과 곱해지므로, 밝은 색이 과하게 빛나거나 그림자 경계가 거칠어지는 Gamma의 왜곡이 없습니다 |
| 품질 단계 | **VR PC**(Standalone 기본, 옛 Ultra) · **VR Quest**(Android 기본, 옛 Medium) | 이름을 바꾸고 아래 값을 같게 맞춤 |
| MSAA | 4× | VR에서는 가장자리 계단이 크게 보입니다. 후처리 AA와 달리 색을 바꾸지 않습니다 |
| 그림자 | 소프트 섀도, 해상도 High, 캐스케이드 1, 거리 8 m | 형상은 0.3–3 m 안에 놓입니다. 캐스케이드 1 = 그림자 맵을 한 번만 그림 |
| 픽셀 광원 | 1 | 방향광 하나만 씁니다 |
| 실시간 반사 프로브 | 끔 | 반사는 환경 빌더가 로드 때 한 번 큐브맵으로 만듭니다(매 프레임 갱신 없음) |
| vSync | 0 | VR에서는 XR 런타임이 화면 갱신에 맞춥니다 |

### 환경 (`Runtime/Environment/EnvironmentBuilder.cs`)

바이너리 에셋 없이 코드와 셰이더 2개(`Resources/IFS/EnvironmentFloor.shader`, `EnvironmentSky.shader`)로 만듭니다. 값은 `EnvironmentSettings`에서 바꿉니다.

| 요소 | 값 | 비고 |
| --- | --- | --- |
| 바닥 | 200 m × 200 m, 회색 알베도 0.46(sRGB), 스무드니스 0.12 | 그림자를 받기만 하고 드리우지 않음 |
| 스케일 기준 | 1 m 격자선(0.39, 굵기 1.2 cm) + 0.5 m 보조선(0.43) | 화면 미분으로 계단 없이 그림. 14 m 넘으면 흐려짐(모아레 방지) |
| 지평선 | 바닥이 18–80 m에서 지평선 색(0.74)으로 녹음 | 전역 안개를 쓰지 않아 형상 색에는 영향이 없음 |
| 하늘 | 직접 쓴 그라디언트 스카이박스: 천정 (0.60, 0.62, 0.65) · 지평선 0.74 · 아래 0.42 | 내장 Skybox/Procedural은 대기 산란으로 파랗게(채도 높게) 나오고, `Shader.Find`로 찾는 내장 셰이더는 빌드에서 빠질 수 있어 쓰지 않음. 단일 패스 인스턴싱 매크로 포함 |
| 앰비언트 | 삼색 그라디언트(Trilight): 위 0.56–0.59 · 옆 0.50 · 아래 0.34 | 환경 색과 맞춤 |
| 방향광 | 백색 (1, 1, 1) = sRGB 백색점(D65), 세기 1.0, 고도 50°·방위 30°(참여자 뒤 왼쪽 위), 소프트 섀도 강도 0.7 | 형상이 어디에 떠 있는지 알려 주는 접지 그림자 |
| 반사 | 환경만 128² 큐브맵으로 1회 렌더(밉맵) → 기본 반사 | 형상보다 먼저 만들어야 형상이 반사에 찍히지 않음 |
| 무채색 | 바닥·하늘·앰비언트 HSV 채도 ≤ 0.08(천정만 아주 옅게 푸름) | EditMode 테스트로 확인 |

- 씬에서는 `IFSEnvironment` 컴포넌트를 둡니다(실행 순서 −100이라 SceneLoader보다 먼저 만듭니다). 코드에서는 `EnvironmentBuilder.Build(settings)` → `EnvironmentHandle`(`Dispose()`로 정리).
- `Build`는 바꾸기 전의 전역 `RenderSettings`(하늘, 앰비언트 모드·색·세기·프로브, 안개, sun, 반사 모드·텍스처·세기)를 저장합니다. `Dispose()`가 이 값을 되돌립니다. 에디터에서 테스트를 돌려도 열린 씬의 조명 설정이 바뀌거나 지워진 머티리얼을 가리키지 않습니다.
- 예시 테스트 씬(`SceneSpecExamples.unity`)은 이 구성으로 다시 만들었습니다(메뉴 또는 `SceneSpecExampleSceneMenu.CreateExampleSceneBatch`).

### 재질(PBR)

- Standard 금속도 워크플로, 금속도 0(유전체). 확산·정반사 합의 에너지 보존은 Standard BRDF가 맡습니다.
- 스무드니스 = (1 − roughness) × 0.92 × 얼룩. 0.92 상한은 완전 거울면이 VR에서 깜빡이는 정반사 앨리어싱을 막기 위해서입니다.
- 노멀맵은 쓰지 않습니다. 절차 메시(icosphere 삼각형 5,120개, 조각 메시 100개)에 UV·탄젠트가 없기 때문입니다. 잔요철은 정점 변위 + 스무드니스 얼룩으로 표현합니다.
- 반투명(Fade: opacity < 1, 그리고 안개 셰이더를 못 쓸 때의 mist)과 안개(`SceneSpecMist`)는 그림자를 끕니다. Built-in의 반투명은 그림자를 받지 못하고, 불투명 그림자를 드리우면 안개가 덩어리처럼 보이기 때문입니다. ZWrite Off · Cull Back이라 오목한 곳은 겹침 순서가 틀릴 수 있습니다(형상이 하나라 오브젝트 사이 정렬 문제는 없음).
- 로더는 에디트 모드에서도 머티리얼을 직접 복제합니다(`renderer.materials`는 에디트 모드에서 누수 오류를 냄). 배치 캡처가 이 경로를 씁니다. 조정 중 `form.type`이 바뀌면 이전 형상의 머티리얼 사본도 함께 지웁니다(`OwnedMaterialCount`로 확인, EditMode 테스트).
- 불투명 셰이더(`SceneSpecOpaque`)는 안쪽 면(Cull Front)·바깥 면(Cull Back) 두 패스로 그리고, **그림자 캐스터는 바깥 면 패스에만** 둡니다. Built-in은 첫 ShadowCaster 패스로 카메라 깊이 텍스처(화면 공간 그림자)를 그립니다. 안쪽 면 패스에도 캐스터가 있으면 그것이 먼저 쓰여 깊이 텍스처에 형상 뒤쪽 면이 들어갑니다. 그러면 바깥 면 그림자를 엉뚱한 위치에서 읽습니다. 침식 구멍 뒤로 바닥이 보이는 곳은 바닥 깊이로 읽습니다. 그래서 바닥이 있을 때와 없을 때 EX01 형상 밝기가 L\* 2 정도 달랐습니다(2026-11-16 배치 캡처 진단으로 확인, 수정 후 0).

### 형상별 렌더 경로 (`Runtime/Rendering/`, docs/decisions.md X64–X72)

`SceneParams` + 모양어 판정 → `FormRenderPlan`(규칙 기반 어댑터) → `IFormRenderer`. 렌더러는 `form.type`과 슬롯 값만 봅니다. `meta.mapping` 등 매퍼 정보는 받지 않습니다(X65, `FormRenderPlanTests`·`FormRendererTests`가 v0/v1 같은 계획·같은 화면을 확인). 조각 수·seed·걸음 수 같은 값은 **형상 프리셋 기본값**이고 참여자가 말한 값이 아닙니다. 로더 notes에 그대로 적습니다.

| 렌더러(`renderPath`) | 메시 | 셰이더 | 드로콜·삼각형(눈당 추정) | 비고 |
| --- | --- | --- | --- | --- |
| `blob` · `shell` | icosphere(4단계, 삼각형 5,120) | Opaque(안쪽·바깥 두 패스) / opacity < 0.99면 Fade | 8 · 20,880 | 이전과 같음(golden 그대로) |
| `mist` | 대리 구(icosphere 3단계, 반지름 0.75, 삼각형 1,280, 바운즈 1.6 상자) | `SceneSpecMist`: 한 패스, 물체 좌표 레이마칭 8걸음(`IFS_MIST_STEPS` = `FormRenderPlan.MistSteps`) | 5 · 1,680 | **밀도장(D7, 2026-11-23) = 둥근 덩어리 5개의 합집합 + 중간 주파수 노이즈 × 침식 결손.** 덩어리 중심·반지름은 `MistLumps.Build(seed)`(배치 규칙 `lumps5/1`, seed 0 — 형상 프리셋 기본값)가 정해 `_Lump0…_Lump4`에 넣고 notes·계획 JSON `mistRule`에 남김. 최종 알파 = opacity × 쌓인 알파(덩어리 속 ≈ opacity, opacity보다 커지지 않음 — X70). 형태 밀도 0.5(숫자 그대로)는 셰이더에서 광학 두께 배율(σ = 0.5 × 16). 덩어리마다 감싼 확산 + 빛 쪽 두께만큼의 자기 그림자 + 주변광(위가 밝고 아래가 어두움). 걸음 구간은 덩어리 전체를 감싼 구와 겹치는 부분만(밖은 버림). 걸음마다 구간 가운데에서 표본(중점 샘플링, 화소별 지터 없음). 이전(X66) 밀도장은 흔든 반지름 감쇠 × 덩이 노이즈였고 중심 광선 알파 목표가 opacity × 0.5였다 — 전후 비교 `docs/validation/cloud/README.md`. **mist에서 roughness의 뜻**: 표면 반사(광택)가 아니라 밀도 노이즈 크기 배율 lerp(0.7, 1.3, R)(0.5에서 1)과 색 얼룩 세기. 이전 Fade 경로에서는 잔요철 정점 변위·색 얼룩·PBR 광택(스무드니스 = 1 − R)이었고 색 얼룩 식만 같다. 그림자 없음. 카메라가 구 밖이면 앞면, 안이면 안쪽 면만 남김. 배치 설정 바닥 높이(`_FloorY`) 아래는 밀도 0 — 구가 바닥에 걸치면 notes와 report.json `mistFloor`(`floorClipped`, 잘린 높이 비율)에 기록(화면은 그대로). 배치 캡처의 색 측정은 `color.measuredWith = mistVolume`(부피 셰이딩의 화면 색, 알베도 기준 목표와 비교). 셰이더를 못 쓰면 `mist(legacy)`(구 + Fade) |
| `fragments` | 각진 조각 5개를 합친 메시 하나(`FragmentMesh`, 삼각형 100, 평면 음영, seed 0) | Opaque/Fade, 정점 변위 0 | 8 · 800 | 이전: 구 5개(24 · 102,800). 조각 생성 규칙 버전 `angular5/1`(배치 반경 비율 0.884, 조각 크기 비율 0.281–0.554)을 notes와 계획 JSON `fragmentRule`에 남김. 규칙을 바꾸면 버전을 올린다(같은 seed라도 메시가 달라지므로) |
| `shapeModel` / `shapePrefab(모형)` | 모양 모형 4종 | Opaque, 정점 변위 0 | 8 · 448–3,472 | 이전과 같음 |
| `superquadric` (spec 2.3.0) | `SuperquadricMesh`(UnityEngine 없음): 슈퍼쿼드릭 하나(규칙 `superquadric/1`, 정점 1,106, 삼각형 2,208, 지름 1, 해석 법선). 같은 (e1, e2)는 한 번 만들어 재사용 | 모양 모형과 같은 IFS Opaque/Fade, 프리셋 `ShapePreset`, 정점 변위 0 | 8 · 9,232 | `form.roundness`가 있고 기본 덩어리 경로일 때만(8.4절 적용 순서). 프리팹을 쓰지 않음(blob 프리팹이 있어도 말한 윤곽이 앞섬). 조절 중 `form.roundness`를 바꾸면 형상을 다시 만듦. 계획 JSON·`report.json`·`initialScene.json`에 `contour`·`emission`(2.3 spec일 때만) |
| `base:container` · `base:line` · `base:sheet` · `base:flame` · `base:drop` (D6, spec 2.2.0) | `BaseShapeMesh`(UnityEngine 없음): 절차 메시 하나, 규칙 `container/1`·`line/1`·`sheet/1`·`flame/1`·`drop/1`, 경계 상자 가장 긴 변 1·가운데 원점, 닫힌 메시, seed 0(형상 프리셋 기본값). 같은 (형상, 변형값)은 한 번 만들어 재사용 | 모양 모형과 같은 IFS Opaque/Fade, 프리셋 `ShapePreset`, 정점 변위 0. 지오메트리 셰이더·컴퓨트 없음(WebGL2에서도 같은 코드) | 메시 삼각형 32(네모 상자)–5,024(엉킨 실), 눈당 추정 드로콜 8 | **`form.base`가 있고 해석된 `form.type`이 blob일 때만**(말하지 않아 기본 blob인 경우 포함). mist·shell·fragments면 그 렌더러로 그리고 계획 JSON `base.status = not_applied_form`, 변형본이 모양 모형을 강제하면 `not_applied_forced`. 프리팹을 쓰지 않음(blob 프리팹이 연결돼 있어도 기본 형상이 앞섬). 모양어는 `not_applied_base`. 변형값(`form.baseVariant`)은 그리는 기본 형상이 spec의 것과 같을 때만 쓰고 정하지 않은 키는 기본값(계획 JSON `base.variant`·`variantDefaults`·`parameters`, notes에도). 색·밝기·채도·투명도·거칠기·침식·크기·움직임은 다른 형상과 같은 식(G22, `BaseShapeTests.Adjust_items_change_the_plan_for_base_shapes`, `UnityOnly/BaseShapeLoaderTests`). 형상 고유 움직임 없음, 불꽃 발광·색 강제 없음(G30). 조절 중 `form.base`를 바꾸면(`SetCategory`) 형상을 다시 만듦. 그림: `docs/validation/base-forms/README.md` |
| `prefab(형태)` · `primitive(형태)` · `shapeModelPrimitive(모형)` | 연결한 프리팹 / IFS 셰이더를 못 쓸 때 | — | — | 대체 경로(그대로) |

한계: 카메라가 안개 덩어리 안에 들어가면 시야가 opacity만큼 가려집니다(D7 뒤: 덩어리 속 알파 ≈ opacity. 헤드셋에서 직접 배치로 구름을 끌어올 때 확인 필요). 카메라가 안개 구 안에 있고 구 뒤쪽이 바닥 아래면 바닥을 내려다보는 화소의 안개가 빠집니다. 바닥에 걸친 안개는 바닥 높이에서 잘린 경계가 옅게 보일 수 있습니다. 헤드셋(Quest 모바일 GPU)의 레이마칭 채움 비용은 재지 않았습니다.

### 후처리

쓰지 않습니다.

1. Post Processing Stack v2(`com.unity.postprocessing`)는 패키지 레지스트리에서 받아야 합니다.
2. 톤매핑·색 보정·블룸은 렌더 색을 spec 색에서 멀어지게 합니다. 일치도 평가에서 "구현이 달랐다"와 "후처리가 색을 바꿨다"가 섞입니다.
3. VR에서 전체 화면 패스는 눈마다 비용이 듭니다. 모바일 타일 GPU에서는 특히 비싸다고 알려져 있습니다[확인 필요].

가장자리 계단은 MSAA 4×로 처리합니다. 나중에 넣는다면 색을 바꾸지 않는 저비용 효과만, 켜고 끌 수 있게, 기록(`report.json`의 `rendering.postProcessing`)에 남깁니다.

## 배치 캡처·성능 측정 (`Editor/BatchCapture.cs`)

SceneSpec JSON 폴더를 받아 JSON마다 렌더 이미지·적용 파라미터·콘솔 오류·색 정확도·프레임시간을 `report.json`으로 남깁니다. 챗봇 → JSON → Unity 전 과정 검증(작업 5)이 그대로 씁니다.

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run \
  -specDir <SceneSpec JSON 폴더> -outDir <결과 폴더> [-width 2064 -height 2208] [-frames 300] -logFile <로그>
```

- `-nographics`를 쓰지 않습니다(렌더가 필요). `-quit`도 붙이지 않습니다(끝나면 스스로 닫음).
- 상대 경로는 Unity 프로젝트 폴더 기준입니다. 끝나면 Unity 프로세스가 남지 않는지 확인합니다.
- 종료 코드: 모든 JSON이 로드되고 도구가 예외 없이 끝나면 0, 아니면 1. AC-4 판정은 `report.json`의 `summary.ac4`에 따로 있습니다.

| 인자 | 기본 | 뜻 |
| --- | --- | --- |
| `-specDir` · `-outDir` | (필수) | 입력 폴더(`*.json`, 이름순) · 결과 폴더 |
| `-width` · `-height` | 2064 · 2208 | 눈 하나의 렌더 해상도(Quest 3 눈당 해상도) |
| `-frames` · `-warmup` | 300 · 30 | 시간을 재는 프레임 수 · 버리는 준비 프레임 수 |
| `-eyes` | 2 | 한 프레임에 렌더하는 눈 수(2 = 눈마다 따로 렌더, 가장 불리한 경우) |
| `-pngWidth` | 1024 | 저장 PNG 폭(0 = 원래 해상도) |
| `-fov` · `-eyeHeight` | 96° · 1.6 m | 세로 시야각(Quest 3 근사) · 눈높이 |
| `-quality` | 현재 단계 | 예: `"VR Quest"` |

JSON 하나마다 하는 일:

1. 빈 씬 + 중립 환경 + SceneLoader(참여자 기록 끔). 카메라를 (0, 1.6, 0)에서 +Z를 보게 두고 로드합니다(= 로드 순간의 머리). 그다음 형상 경계 중심으로 카메라를 돌립니다.
2. 눈당 해상도·MSAA 4×·sRGB RenderTexture로 렌더 → `<이름>.png`(축소) + `<이름>_detail.png`(형상 주변 원래 해상도로 잘라냄).
3. SceneLoader가 실제로 쓴 값을 기록합니다: `params`(initialScene.json과 같은 0–1 값), `defaultsUsed`, `inferredUsed`, `notes`, 배치(거리·높이).
4. 로드·렌더 중 콘솔 메시지(`Application.logMessageReceived`): 오류·예외·경고 수와 내용.
5. **색 정확도**: 형상만 검은 배경·흰 배경에 각각 렌더해 화소마다 덮임 a = 1 − (W − B)와 배경과 섞이기 전 색 c = B / a를 구합니다(선형). 이때 바닥은 끄지 않고 배경과 같은 색의 `Unlit/Color` 머티리얼로 바꿉니다(화면에 보이는 그림자 수신자 구성을 실제 장면과 같게). 덮인 화소 경계 상자의 가운데 50%×50% 평균을 spec 색(HSL → sRGB)과 CIEDE2000으로 비교합니다. 값은 네 가지입니다.
   - `frontal`: 광원을 카메라 시선 방향으로 돌린 정면 조명(진단용).
   - `scene`: 장면 방향광 그대로, 형상만(배경과 섞이기 전 색).
   - `inContext`: 실제 장면 렌더의 같은 화소(반투명이면 배경과 섞인 값).
   - **`primary`(보고·판정에 쓰는 값)**: 불투명이면 `inContext`(참여자가 보는 색), 반투명이면 `scene`.
   - `sceneVsInContextDeltaE2000`: 불투명이면 0이어야 합니다(EditMode 테스트가 ≤ 0.1을 확인). `diagnostics`에는 하나씩만 바꾼 렌더(바닥 원래 머티리얼 + 검은 배경, 하늘 + 바닥 끔, 실제 장면 재렌더)를 남깁니다.
   - `specColorIsDefault`: h·s·l 중 **하나라도** 기본값으로 채웠으면 true, 어느 성분인지는 `specColorDefaultComponents`. 요약(`summary.color`)은 참여자가 h·s·l을 모두 말한 spec(`stated`)과 기본값이 섞인 spec(`withDefaults`)을 따로 집계합니다. 기본 무채색은 맞추기 쉬워 색 반영 정확도를 좋게 보이게 하기 때문입니다(AGENTS.md 원칙 2). 논문·판정에는 `stated.primaryMean`·`stated.primaryMax`를 씁니다.
   - `shaderTarget`은 brightness에 따른 셰이더의 의도된 어둡게·발광을 반영한 기대 색입니다.
6. **렌더 통계(추정)**: `UnityStats`와 `ProfilerRecorder`(Draw Calls Count·Triangles Count 등)를 모두 걸어 봤지만, 배치모드 에디트 모드의 수동 `Camera.Render()`에서는 둘 다 0으로 남습니다(`meaningful: false`로 기록). 그래서 직접 계산한 **추정**을 씁니다: 화면 안 렌더러 수, 메시 삼각형, 렌더러별 패스(LightMode = ForwardBase/ForwardAdd/ShadowCaster)로 눈당 드로콜·삼각형 추정(전방 패스 + 화면 공간 그림자용 카메라 깊이 + 그림자 맵 + 하늘 + 그림자 해상), 그림자 광원 수. `summary.ac4`의 키도 `drawCallsPerEyeEstimateAtMost100`·`trianglesPerEyeEstimateAtMost300k`로 추정임을 밝히고, `estimatedItems`·`drawCallsTrianglesMeasuredByProfiler`(false)를 함께 적습니다. 실측은 PlayMode나 기기에서 해야 합니다.
7. **형상 지표(X72)**: `renderPath`(렌더러 이름), `renderPlan`(FormRenderPlan 전체), `visiblePixels`(장면 조명·형상만 렌더의 덮임 a ≥ 0.02 화소 수, 원래 해상도), `maxAlpha`, `silhouette{circularity(4π·넓이/둘레², 마스크 = a ≥ 0.5 × maxAlpha, 마칭 스퀘어 둘레), components(8-이웃 덩어리, 마스크 넓이의 0.5% 이상), edgeFalloffPx((넓이(a ≥ 0.1·max) − 넓이(a ≥ 0.9·max)) / 둘레), maskPixels, perimeterPx, componentsRaw}`. 요약은 `summary.renderPaths`(렌더 경로별 평균). 2026-11-23(D7) 추가: `contrast{deltaL, shapeL, backgroundL, shapeLStd, shapePixels, backgroundPixels}` — 실제 장면 렌더의 L\*로 형상 영역(윤곽 마스크) 평균 − 주변 배경(보이는 화소 경계 상자를 긴 변 × 0.25 넓힌 상자 안의 a < 0.02 화소) 평균, `summary.renderPaths.*.contrastDeltaLMean`. 계산은 `Editor/SilhouetteMetrics.cs`(UnityEngine 없음, `SilhouetteMetricsTests`). "더 그 형상답다"의 대리 지표일 뿐입니다. 전후 비교: `docs/validation/render/README.md`.
8. **프레임시간**: 한 프레임 = 눈 수만큼 `Camera.Render()`(눈 위치를 IPD 64 mm의 절반씩 옮김) → RenderTexture에서 1×1 화소를 `Texture2D.ReadPixels`로 읽어 CPU가 GPU 완료를 기다리게 합니다(동기화). `Stopwatch`로 렌더 시작부터 동기화 끝까지 잽니다. 준비 프레임은 버리고 p50·p95·max·평균을 냅니다. 에디터 오버헤드와 MSAA 해상 비용이 들어 있습니다.

> 프레임시간은 **데스크톱 GPU(RTX 5080)에서 잰 대리 측정**입니다. Quest 3 헤드셋(모바일 GPU, 타일 렌더링, 단일 패스 인스턴싱)의 성능이 아닙니다. `report.json`의 `disclaimer`에도 적혀 있습니다. 헤드셋 성능은 기기에서 따로 재야 합니다.

### 검증 결과 (2026-11-16, `docs/validation/unity/`)

예시 2개를 Quest 3급 해상도(눈당 2064×2208, 양안, MSAA 4×, 준비 30 + 300프레임)로 돌린 결과입니다. 그래픽 장치는 RTX 5080(데스크톱 대리 측정)입니다.

| | EX01 (회색 덩어리, 침식 0.6) | EX02 (색·형태 미지정, 웅크림) |
| --- | --- | --- |
| 로드 · 콘솔 오류 · 예외 · 경고 | 성공 · 0 · 0 · 0 | 성공 · 0 · 0 · 0 |
| 프레임시간 p50 / p95 / max (ms), `VR PC` | 0.74 / 2.69 / 4.91 | 0.68 / 0.82 / 1.03 |
| 프레임시간 p50 / p95 / max (ms), `VR Quest` | 0.74 / 0.96 / 1.41 | 0.69 / 0.82 / 1.27 |
| 드로콜 · 삼각형 (눈당, **추정**) | 8 · 20,880 | 8 · 20,880 |
| 실시간 그림자 광원 | 1 | 1 |
| 색이 말한 값인가 | 예(h·s·l 모두) | 아니오(h·s·l 기본값) |
| ΔE00 primary(=inContext) / scene / frontal | **1.20** / 1.20 / 6.90 | 0.77 / 0.77 / 2.03 (요약의 `stated`에서 뺌) |

- AC-4 기준(p95 ≤ 13.9 ms, 드로콜 ≤ 100, 삼각형 ≤ 300k, 그림자 광원 ≤ 1, 오류·예외 0)을 모두 만족합니다. 단, 프레임시간은 데스크톱 대리 측정이고 드로콜·삼각형은 추정입니다.
- `VR Quest` 단계 결과는 `docs/validation/unity/vr-quest/`에 있습니다. 지금은 `VR Quest`와 `VR PC`의 그림자·MSAA 값이 같아(소프트 섀도, High, 캐스케이드 1, 거리 8 m, MSAA 4×) 데스크톱에서는 차이가 없습니다. 모바일 타일 GPU의 비용은 기기에서 재야 합니다.
- 셰이더 수정(안쪽 면 패스 ShadowCaster 제거)으로 이전 보고(드로콜 10·삼각형 31,120, EX01 scene 2.12 ≠ inContext 1.20)와 값이 바뀌었습니다. 지금은 불투명 spec 5개(EX01·EX02·SYN-U2·U3·U4) 모두 scene = inContext입니다(`sceneVsInContextDeltaE2000` 0.00).

**합성 spec 4개**(`docs/validation/unity/synthetic/`, 손으로 쓴 합성 값, 참여자 데이터 아님, 입력은 `synthetic/specs/`):

| spec | 형태·색(HSL)·재질 | ΔE00 primary | 가운데 덮임 | 드로콜 · 삼각형 (눈당, 추정) | p95 (ms) |
| --- | --- | --- | --- | --- | --- |
| SYN-U1 | mist, (0.58, 0.2, 0.7), opacity 0.6 | 5.83 (scene; inContext 12.87) | 0.26 | 5 · 5,520 | 1.57 |
| SYN-U2 | fragments, (0.1, 0.6, 0.5), roughness 0.6 | 6.32 | 1.00 | 24 · 102,800 | 0.91 |
| SYN-U3 | shell, (0.33, 0.4, 0.4), roughness 0.3 | 8.06 | 1.00 | 8 · 20,880 | 0.82 |
| SYN-U4 | blob, (0.0, 0.9, 0.5), roughness 0.1 | 7.72 | 1.00 | 8 · 20,880 | 0.82 |

- 말한 색만 집계한 ΔE00 primary: 예시(EX01) 1.20, 합성 4개 평균 6.98·최대 8.06. 유채색에서 차이가 큽니다(아래 「한계」).
- 다시 돌리는 법: `-specDir docs/validation/unity/synthetic/specs -outDir docs/validation/unity/synthetic -quality "VR PC"`.

## 소유감 실험 (`Runtime/Ownership/`, 후보1 프로토타입)

참여자 서술로 만든 원본 형상 1개와, 형태·색·크기·움직임 중 하나만 바꾼 변형본(어긋난 변형) 4개, 그리고 색·크기의 같은 말·다른 값 쌍(유효한 쌍만, 0·2·4개)을 균형 순서로 하나씩 같은 시간 보여 줍니다(n = 5·7·9개). 형상마다 7점 평정(기본 "떠올린 모습과 닮았다", 설정 `ratingItem` = `mine`이면 "내 것 같다")을 받고, 마지막에 n개 중 하나를 고릅니다. 끝으로 원본과 변형본을 나란히 두고 "얼마나 다른가"를 평정합니다(조작 크기 점검, 설정으로 끔). 어느 것이 원본인지는 참여자에게 알려 주지 않습니다.

| 파일 | 하는 일 |
| --- | --- |
| `OwnershipVariantGenerator.cs` | 변형본 생성기(순수 C#). 원본 spec + 참여자 번호 + 설정 → 원본 해석값, 어긋난 변형 4개, 같은 말·다른 값 쌍, 제시 순서, 오류·플래그. 참여자 보고값은 입력으로 받지 않습니다. 기본값·모양 해석은 `SceneParams`·`ShapeMapping`을 그대로 씁니다. 난수·LLM이 없어 입력이 같으면 결과가 바이트까지 같습니다 |
| `WilliamsDesign.cs` | 제시 순서 표. 보여 줄 조건 n개를 먼저 정한 뒤 n조건 Williams 설계(첫 행 0 1 n−1 2 n−2 …, 짝수 n행, 홀수 2n행 = 뒤집은 방진 추가). 5조건은 예전 10행 표 그대로(0.2 세션 재현). 행 = (번호 − 1) mod 행 수, 균형 비트 cb = ((번호 − 1) mod 2) XOR (⌊(번호 − 1) / 10⌋ mod 2) — 1–10번은 홀짝 그대로, 11–20번은 뒤집혀 20명이면 행 × cb 20칸이 한 번씩 찹니다. 참여자 번호는 1부터 빠짐없이 차례로 배정하고, 중단·재시행은 같은 번호로 합니다(분석기 `summary.json`의 `orderBalance`가 행별·cb별·행×cb 칸별 세션 수를 세고 어긋나면 경고) |
| `OwnershipConfig.cs` | `sizeStep` 0.25 · `colorDeltaE` 30(잠정) · 쌍: `shiftAttributes` [color, size](빈 목록 = 0.2와 같은 계획·순서. 기록 형식은 0.3 그대로이고 0.2 직렬화 모드는 없음) · `requirePrereport` 꺼짐 · `sizeShiftStep` 0.10(최소 0.02) · `colorShiftDeltaE` 12 · `maxHueShiftDeg` 20 · `shiftSymmetryTolerance` 3(모두 잠정) · `ratingItem` resemblance(기본)·mine · `viewSeconds` 30 · `headSampleHz` 20 · `gazeConeDeg` 15 · `finalChoiceArcDeg` 120 · `finalChoiceRadiusM` 0(= 원본 거리) · `differenceRating` 켬. 값은 manifest에 남습니다 |
| `OwnershipRunner.cs` | 단계 진행, 형상 n개 로드(로더 n개, `SceneLoader.Load(path, SceneOverride)`), 평정·선택 입력, 기록. 조건은 최대 9개(키 한 자리), 넘으면 생성 오류 |
| `HeadPoseProvider.cs` | 머리 자세: XR Head 노드가 있으면 그것(`headSource = xr`), 없으면 데스크톱 모의(`desktop`) |
| `ParticipantTextDisplay.cs` | 참여자에게 보이는 글(월드 공간 TextMesh + OS 폰트 "Malgun Gothic" 등, 없으면 내장 폰트와 경고) |
| `OwnershipExperimenterGui.cs` | 실험자 화면(IMGUI, 데스크톱 창에만 그림. F1로 숨기기) |
| `OwnershipRecordWriter.cs` · `OwnershipManifest.cs` | 기록 파일(아래 「기록」) |
| `SceneSpec/SceneOverride.cs` | 해석값 덮어쓰기 + 모양 모형 강제. 참여자 조정이 아니라서 `RecordChange`(events.csv)를 타지 않습니다. `Load(path)`(변형 없음)는 예전과 같습니다(golden 지문 테스트) |
| `StreamingAssets/IFS/ownership_task.v0.2.json` | 참여자 문구 7개(초안, `status: draft`, IRB 대상): 0.1의 5개 + 닮음 문항 `rating_resemblance`·`final_choice_resemblance`(출처 docs/rq-v2-proposal.md 3.5). 마지막 선택 문구의 `{n}`은 조건 수. `ownership_task.v0.json`(main 계열 G57로 문구를 다듬어 version 0.2 — v0.2 파일과 version 값이 같아 기록은 파일 이름으로 구분)은 `mine` + 5조건에서만 쓸 수 있고 아니면 SpecCheck 오류. 코드에는 문구가 없습니다 |
| `Editor/OwnershipExperimentMenu.cs` | 씬 만들기 메뉴, 배치 진입점(씬·자동 시행) |

### 변형 규칙 (요약)

원본 spec 파일은 고치지 않습니다. 변형 = 해석된 값 + 덮어쓰기입니다. `_inferred`는 쓰지 않습니다.

| 속성 | 규칙 | 기록 |
| --- | --- | --- |
| 크기 | `layout.size` ± 0.25(지름 ×2 또는 ÷2). [0.25, 0.75] 안이면 cb 0 = +, 1 = −. 밖이면 들어오는 쪽(clamp 없음) | `rule` up/down, `flags.forced` |
| 색 | ΔE00은 셰이더 알베도 기준(`RenderedColor`: HSL → sRGB를 선형 공간에서 밝기 배율 `lerp(0.4, 1, saturate(2 × brightness))`로 곱한 색, 로더와 같은 함수). 유채색(s ≥ 0.10): 색상을 cb 방향으로 1°씩 돌려 ΔE00 ≥ 30인 최소 각. 180°까지 안 되면 명도(`lightness_fallback`). 무채색(기본 HSL(0, 0, 0.7) 포함): 명도를 0.005씩, 두 방향 다 되면 cb(0 밝게·1 어둡게). 둘 다 안 되면 최대 변화 + `belowTarget`. 불투명도는 목표에 넣지 않고 하늘 지평선 색 위 알파 합성 ΔE00을 따로 기록 | `magnitude.deltaE00`(알베도)·`deltaE00Composited`, from/to h·s·l |
| 움직임 | 정지이거나 보이지 않는 조합(회전 + 구·납작 원기둥·원뿔, 흔들림 + 자세 변형 없는 구)이면 `floating`(add), 아니면 `still`(remove). 속도 그대로. 기본 blob·mist·shell·fragments는 굴곡·조각이 함께 돌아 보이므로 표에 없음 | `flags.motionAltersScale`(맥동·퍼짐·다가옴·가라앉음) |
| 형태 | 모형 없는 blob → Cube(add), 구 → Cube(swap), Cube·납작 원기둥·원뿔 → 구(remove), mist·shell·fragments → blob(remove, 모양 모형 없음) | `flags.saidNotRendered`(말했지만 그려지지 않은 모양어) |
| 크기 쌍 `size_lo`·`size_hi` | `layout.size` ∓ `sizeShiftStep`(0.10). 적용 값이 [0, 1] 안(아니면 `out_of_range`), lo < w < hi·로그 척도 대칭(아니면 `asymmetric`). 크기가 stated면 원본(반올림 전)이 속한 쪽에 실제 적용할 끝값(반올림 뒤)도 있어야 함(0.5 기준, w < 0.5 → hi < 0.5, w > 0.5 → lo > 0.5, 끝값이 정확히 0.5면 실패, 아니면 `crosses_category`. w = 0.5는 `categoryCheck` skipped_neutral) | `shiftPairs[]`(axis size, 화면 폭 `wM`·`loM`·`hiM` m(소수 6자리) = `RenderedSize`, 로더와 같은 식·자세 배율 포함, `categoryCheck`), `kind` shift |
| 색 쌍 `color_lo`·`color_hi` | 유채색: 색상 1° 격자(반올림해 적용할 값으로 최대 20°). 무채색: 명도 0.005 격자([0.05, 0.95] 안). 양쪽 후보를 함께 보고 둘 다 알베도 ΔE00 ≥ 12이고 \|ΔE_lo − ΔE_hi\| ≤ 3인 최소 이동 쌍. 한쪽이라도 못 닿으면 `range_exceeded`, 닿지만 대칭 쌍이 없으면 `asymmetric`. 명도 대체 없음 | `shiftPairs[]`(axis hue/lightness, `deltaE_lo`·`deltaE_hi`, 기록용 `deltaEComposited_lo`·`_hi`) |

- `source`(RQ2): 바꾼 키의 값을 준 spec 슬롯에 `_provenance`가 있으면 stated, 없으면 default, 섞이면 mixed.
- 원본과 같아지는 변형, 모르는 `motion.type`·모형은 오류입니다(시작 버튼이 꺼짐). 원본 유효 불투명도(opacity × mist 밀도 0.5) < 0.15면 `lowVisibility` 경고.
- 쌍의 `basis`: 축 값의 슬롯에 값이 있고 근거(`_provenance`)도 있으면 stated, 아니면 default(값 없이 근거만 있으면 `provenanceWithoutValue: true`). 색은 `material.color` 슬롯만으로 정하고 축 선택에 쓴 채도의 출처는 `axisChoiceBasis`.
- 순서·cb: 쌍의 유효성으로 조건 수 n을 먼저 정하고, cb = ((번호 − 1) mod 2) XOR (⌊(번호 − 1) / 행 수(n)⌋ mod 2)(n = 5는 예전 규칙과 같음). manifest에 `orderRows`(행 수)·`conditionSet`(조건 id 이름순, `|`로 이음).
- 쌍은 생성 때 유효한지 정하고, 유효하지 않으면 둘 다 보이지 않습니다. `lowVisibility`면 두 쌍 모두 `not_rendered`, 꺼진 속성은 `disabled`. 쌍의 `lo`·`hi`는 축 값(size·hue·lightness 모두 0–1, hue는 0/1에서 감김), `step`은 크기면 이동폭, 색이면 탐색 단위(1/360 또는 0.005). 실험자 화면에는 쌍의 id만 보입니다(값·방향 설명 없음).

### 실험자가 하는 일

1. (처음 한 번) 메뉴 **IFS ▸ Create Shape Prefabs**로 모양 프리팹이 있는지 확인합니다. 씬이 없거나 망가졌으면 **IFS ▸ Experiment ▸ Create Ownership Experiment Scene**.
2. `Assets/IFS/Scenes/OwnershipExperiment.unity`를 열고 Play. Game 창 왼쪽에 실험자 화면이 뜹니다(Game 창을 크게, 해상도 1920×1080 이상 권장).
3. **Setup**: 참여자 번호(1 이상. 1부터 빠짐없이 차례로 배정하고, 중단·재시행은 같은 번호로 합니다) → spec 폴더(비우면 에디터에서 `<저장소>/chatbot/logs/scenes`) → 목록에서 파일을 누르거나 경로를 직접 입력(`[변형 파일]` = `EX01.v1.json`처럼 `.v숫자.json` 파일) → **확인 → SpecCheck**.
   - (선택) Setup의 **보기 전 보고 파일 경로**: 있으면 시작 때 기록 폴더에 `prereport.json`으로 바이트 그대로 복사하고 manifest `prereport`(file·sha256·specSha256·specSha256Match·matchedBy·sessionId·createdAtUtc·copiedAtUtc)를 남깁니다. 지금 spec 해시가 보고의 `specSha256`이나 `altSpecSha256`(대체 매핑 파일)의 값 중 하나와 같으면 일치(`matchedBy` primary/alt). 고른 값·확정 여부는 읽지 않고 자극·순서·화면에 쓰지 않습니다. SpecCheck에는 "보기 전 보고: 있음/없음/해시 불일치"만 보입니다. `requirePrereport`를 켜면 없거나 해시가 다를 때 시작을 거부합니다.
4. **SpecCheck**: 슬롯별 말한 값/기본값/근거 없음과 근거 말(구분은 슬롯의 `_provenance` 유무로, 변형 `source`와 같은 함수 `OwnershipVariantGenerator.SlotSource`. 값은 있는데 근거가 없으면 "근거 없음"이고 변형 `source`에서는 default로 셉니다), `_unmapped`·`_unmatched`·`_alternatives`·`_needsConfirmation`의 개수와 원문, 어긋난 변형 4개의 from → to와 플래그, 보여 줄 형상 수를 확인합니다. 빨간 오류가 있으면 시작할 수 없습니다. 참여자가 헤드셋을 쓰고 정면을 보면 **Enter**(시작 순간의 머리 자세가 형상 배치 기준이 됩니다).
5. **Intro**: 안내 문구 → 준비되면 **Space/Enter**.
6. **Viewing × n**은 `viewSeconds`마다 자동으로 넘어갑니다. **Rating**: 참여자가 말한 숫자 **1–7** → **Space/Enter**로 확정·다음 형상. 잘못 눌렀으면 **Backspace**(취소도 기록).
7. **FinalChoice**: n개가 호에 놓이고 위에 1–n 번호(왼쪽부터 = 제시 순서). **1–n** → **Space/Enter**.
8. **Difference × (n − 1)**: 왼쪽 원본, 오른쪽 변형본. **1–7** → **Space/Enter**.
9. **Done**: 기록 폴더 경로가 보입니다. **다음 참여자 준비**를 누르면 Setup으로 돌아갑니다.

| 키 | 동작 |
| --- | --- |
| 1–9 (숫자 줄·키패드) | 평정(1–7)·선택(1–n) 입력 |
| Space · Enter | 확정·다음 단계. SpecCheck에서는 시작 |
| Backspace | 확정 전 입력 취소 |
| Esc | 중단(어느 단계든, 그때까지의 자료는 남고 `summary.json`에 `abortedAt`). SpecCheck에서는 뒤로 |
| F1 | 실험자 화면 숨기기·보이기 |
| 마우스 오른쪽 드래그 · WASD | 데스크톱 모의 조작: 둘러보기 · 수평 이동(헤드셋이 없을 때) |

- 참여자 화면에는 남은 시간·원본 여부가 나오지 않습니다. 실험자 화면에는 둘 다 보입니다.

**초안 문구 경고.** 문구 파일(기본 `ownership_task.v0.2.json` 7개, `ownership_task.v0.json` 5개)의 문구는 IRB 확인 전이라 모두 `status: draft`입니다(그대로 둡니다). draft 문구가 하나라도 있으면 Setup·SpecCheck 화면 맨 위에 주황 굵은 글씨로 "[초안 문구]" 줄이 뜨고, 같은 내용이 `events.csv`의 `warning`으로 남습니다. `manifest.json`의 `taskText`에는 문구 파일 버전과 draft 문구 수·키가 기록되고, 분석기는 `sessions.csv`의 `draft_phrases` 열과 `summary.json` 경고로 draft 문구로 모은 세션을 알려 줍니다. 본 실험에서는 문구를 `spec`으로 바꾼 뒤 OwnershipRunner ▸ Config ▸ *Require Spec Phrases*(`requireSpecPhrases`, 기본 꺼짐)를 켜면, draft 문구가 남아 있을 때 세션 시작을 거부하고 이유를 화면에 빨간 오류로 보여 줍니다.
- 마지막 선택·차이 평정에서 형상끼리 겹치면 반지름을 늘려 같은 거리에 다시 놓습니다(`events.csv`의 `final_layout`·`difference_layout`에 반지름 기록).
- Play를 멈추거나 앱을 닫으면 중단으로 기록합니다(`quit` 이벤트).

### 헤드셋 연결

2026-11-23부터 프로젝트에 XR 패키지(OpenXR)가 들어 있고 Windows(Standalone)에서 Play하면 XR이 자동으로 시작됩니다. 연결 절차·조작·문제 해결은 아래 **「헤드셋 연결 (Quest 3 + Quest Link, OpenXR)」** 절에 있습니다(배치 실험 러너 기준).

소유감 러너는 이번에 바꾸지 않았습니다. 그 씬의 카메라에도 `HeadPoseProvider`가 있어 헤드셋이 연결돼 있으면 XR Head 노드로 머리 자세를 넣고 `머리: xr`(manifest `headSource`)로 기록하지만, 소유감 씬은 XR 리그·바닥 원점 요청·정면 재설정·컨트롤러 입력이 없어(키보드 입력만) **헤드셋에서 확인하지 않았습니다**. 소유감 실험을 헤드셋으로 하려면 배치 러너처럼 리그를 넣는 작업이 따로 필요합니다.

### 기록 (참여자 데이터 — git 밖)

`{recordRoot}/ownership/P{번호:000}/{sessionId}/{UTC yyyyMMdd-HHmmss}/`. `recordRoot`는 비우면 `persistentDataPath/IFS/sessions`(OwnershipRunner ▸ *Record Root*로 변경). UTF-8(BOM 없음), 숫자 InvariantCulture, 줄바꿈 `\n`. 분석 스크립트와의 계약이라 헤더·필드 이름을 바꾸지 않습니다(EditMode 테스트가 문자열을 고정).

| 파일 | 내용 |
| --- | --- |
| `manifest.json` | `recordVersion` ifs-ownership/0.3(0.3에서 `ratingItem`·`shiftPairs`(attribute·axis·basis·w·lo·hi·step·deltaE_lo·deltaE_hi·valid·skipReason)·`variants[].kind` 추가, `order` 길이 = n), `generatorVersion`, `taskText`(문구 파일·버전·`draftCount`·`draftKeys`), 참여자 번호·cb·순서 행, `specFile`(파일 이름만)·`specSha256`, `headSource`, 설정, `flags.lowVisibility`, 원본 해석값·말한/기본값 키, 변형 5개(`overrides`·`shapeModel`·`from`/`to`·`rule`·`source`·`sourceByKey`·`flags`·`magnitude`), `order` |
| `headpose.csv` | `time_ms,phase,position,variant,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg` — 프레임당 최대 1개, 앞 표본에서 1/`headSampleHz` 이상 지난 프레임의 실제 시각으로 씁니다(밀린 표본을 과거 시각으로 채우지 않음. 그래서 실제 간격은 프레임 간격에 맞춰 명목보다 조금 길 수 있고, 긴 멈춤은 빈 간격으로 남음). 형상이 하나만 보이는 viewing에서만 variant·obj·거리·각이 있습니다 |
| `ratings.csv` | `position,variant,rating,rt_ms,view_ms,cancelled,item`(item = `ratingItem`, 0.3에서 추가) — 취소한 평정은 `cancelled=1` 행으로 남고 다시 입력한 값이 새 행 |
| `difference.csv` | `variant,rating,rt_ms` |
| `events.csv` | `time_ms,event,detail` — 단계 전환, 키, 취소, 배치, 경고, 중단. 형상 제시 시작은 `viewing_start`(detail `position=N;variant=ID` 고정 형식, 분석기가 `first_look_ms`·표본 구간의 시작점으로 읽음). 첫 제시 바로 뒤 `first_viewing_utc`(detail = UTC ISO 8601 `yyyy-MM-ddTHH:mm:ss.fffZ`, 세션에 한 번) |
| `prereport.json` | (보기 전 보고 파일을 고른 때만) 원본 바이트 그대로 |
| `summary.json` | `completed`, `abortedAt`, `finalChoice`(position·variant·rt_ms), `ratings`(변형별 마지막 평정), `endedAtUtc` |

- `time_ms`는 세션 시작(SpecCheck에서 Enter)부터. `rt_ms`는 문항을 띄운 때(취소 뒤에는 다시 물은 때)부터 숫자 키까지. `view_ms`는 실제 제시 시간(프레임 단위로 `viewSeconds`보다 조금 길 수 있음).
- 자기 자료가 아닌 기록(자동 시행)은 `events.csv`에 `auto_mode` 줄이 있습니다.

### 자동 시행 (검증용)

키 없이 정해진 평정(합성)·선택·머리 경로로 Setup → Done을 한 바퀴 돌아 기록 폴더를 만듭니다. 에디트 모드에서 시뮬레이션 시계로 돕니다(형상 움직임은 돌지 않음).

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.OwnershipExperimentMenu.RunAutoTrialBatch \
  -recordRoot <저장소 밖 폴더> -specPath "<a.json>;<b.json>" [-participant 1] [-viewSeconds 0.5] [-headSampleHz 20] -logFile <로그>
```

spec마다 참여자 번호를 하나씩 올립니다. 씬 만들기 배치: `-executeMethod IFS.SceneSpec.EditorTools.OwnershipExperimentMenu.CreateSceneBatch`. 둘 다 `-quit` 없이(끝나면 스스로 닫음), 성공 0·실패 1.

2026-11-17 확인: 합성 spec 4개(말한 값이 많은 것·EX02(거의 기본값)·mist·네모 + 맥동)로 자동 시행, 4개 모두 기록 6개 파일이 계약 형식과 맞음. 씬 만들기 두 번 실행 결과는 로컬 fileID(Unity가 실행마다 새로 정함)만 다르고 구성·값은 같음. CP4 반영 뒤 같은 4개를 다시 돌려 분석기(`ifs_chatbot.eval.ownership`)에 넣었을 때 경고 0건(dt 0.02 s에서 표본 간격 60 ms, 형상당 8개, 모두 `viewing_start` 기준). 외부 리뷰 반영(기록 0.2) 뒤 같은 4개를 다시 돌렸을 때 4개 모두 완료, 분석기 경고는 초안 문구 1건(4세션 모두 draft 5개, 의도한 경고)뿐이었습니다. 네 spec 모두 밝기 ≥ 0.5라 색 변형은 이전과 같았고, mist(유효 알파 0.25)의 합성 ΔE00은 13.6(알베도 ΔE00 30.1)이었습니다.

## 배치 실험 러너(RQ V4, 프로토타입)

확정 spec의 물체 하나(변형본 없음, 장면 속성은 기존 `SceneLoader` 경로 그대로)를 '나' 기준 공간에 두고, 직접 배치(place) 또는 보기만(view) 조건으로 한 회기를 진행합니다. 설계는 `docs/rq-v4-proposal.md` 4절, 결정은 `docs/decisions.md` X42–X54. 후보1 소유감 러너(`OwnershipRunner`)와 그 기록 형식은 건드리지 않고 `Assets/IFS/Runtime/Placement/`에 따로 있습니다(같은 어셈블리 `IFS.SceneSpec`).

**헤드셋(Quest 3 + Quest Link) 경로를 2026-11-23에 넣었지만 사람이 헤드셋을 쓰고 확인하지는 않았습니다**(`docs/headset-checklist.md`). 참여자 입력은 `IPlacementInput` 하나로 받고, Setup의 확인 때 설정 `inputMode`에 따라 XR 컨트롤러(`XrPlacementInput`) 또는 데스크톱 모의 조작(`DesktopPlacementInput`)을 고릅니다. 자동 시행은 합성 입력(`inputSource: auto`)입니다.

| 구성 | 파일 | 하는 일 |
| --- | --- | --- |
| 단계·기록 | `PlacementSession.cs` | 단계 흐름, 잡기·옮기기, 시스템 이동·재생·가리켜 지정, 멈춤 거리, 평정(평정 지시문, 참여자 컨트롤러 평정 선택), 기록. UnityEngine 없음(dotnet 테스트에서 끝까지 돎) |
| 그리기 | `PlacementRunner.cs` | spec 로드·확인, 참여자 입력 고르기, 물체·글·표식·XR 광선 그리기, 실험자 키(R = 정면 재설정) |
| 헤드셋 | `PlacementXrRig.cs` · `XrPlacementInput.cs` · `XrPlacementInputLogic.cs` · `PlacementTextPanel.cs` | XR 리그(바닥 원점 요청·정면 재설정), 컨트롤러 입력(장치 읽기 / 버튼 규칙 — 규칙 부분은 UnityEngine 없음), 헤드셋 안 참여자 판 |
| 공간 | `PlacementSpace.cs` | 원형 바닥(경계 띠), 중심 '나' 표식(지름 0.5 m), 거리 고리, 가리킴 표식. 코드로 만듦. 중립 환경의 격자 바닥은 이 장면에서만 숨김 |
| 설정 | `PlacementConfig.cs` | 아래 표. 전부 manifest `config`에 남음 |
| 기타 | `PlacementTaskText.cs` · `PlacementRecordWriter.cs` · `PlacementTrajectory.cs` · `StopDistanceSchedule.cs` · `PlacementGeometry.cs` · `PlacementAutoScript.cs` · `PlacementExperimenterGui.cs` · `Editor/PlacementExperimentMenu.cs` | 문구, 기록 형식, 궤적, 시행 순서, 기하, 자동 시행, 실험자 화면, 씬 만들기·배치 진입점 |

### 단계

`intro → baseline → pre_items → pre_wait → condition → post_items → post_wait → stop_distance → check_items → done` (기록 형식 계약의 이름 그대로. `setup`은 세션을 만들기 전이라 기록에 없음). 놓기 도움(`placementAssist`)을 켠 직접 배치 조건에서만 `intro`와 `baseline` 사이에 배치 연습 `practice`가 끼어듭니다(아래 「배치 공간 후보 B·E·F」. `practiceInAllConditions`를 함께 켜면 보기만 조건에도 — G59).

2026-11-25 G59(논문 심사 관점 검토의 보완, 둘 다 기본 꺼짐 — 본 설계에 쓸지는 ⚠ 사람이 정할 것):

- `checkBeforeStopDistance`: 점검 평정을 멈춤 거리 **앞**, 사후 평정 바로 뒤로 옮깁니다 — `… → condition → post_items → check_items → post_wait → stop_distance → done`. 기본(꺼짐)은 위 순서대로 멈춤 거리 **뒤**입니다. 멈춤 거리에서 버튼을 누른 뒤에는 보기만 조건도 "자리는 내가 정했다"에 그렇다고 답할 수 있고 "방금 이것이 있던 자리"도 모호해지기 때문입니다. 점검 동안 물체는 사후와 같이 조건 단계가 끝난 자리에 있습니다(`hideObjectDuringItems`면 숨김). 점검 문항이 없으면(또는 모두 끄면) 단계째 건너뛰고 `post_wait`로 갑니다.
- `practiceInAllConditions`: 놓기 도움의 배치 연습(뜻 없는 회색 상자 옮기기 1회, 문구 `practice`)을 보기만 조건(static·system_move·replay·point_select)에서도 합니다. 조건 전 컨트롤러 경험을 두 집단에서 같게 하려는 것입니다. 연습만 같아지고 보기만 조건의 다른 화면(지시문, 범위 문장 없음)은 그대로입니다. `placementAssist`를 켰을 때만 쓸 수 있습니다(꺼져 있으면 확인 단계 오류, 실험자 화면에서는 놓기 도움 아래에만 보임).
- 사후·점검 평정 때 물체 숨기기는 이미 있는 `hideObjectDuringItems`(2026-11-23)로 합니다 — 켜면 사전·사후·점검 세 평정 단계 모두에서 숨기고, 기본(꺼짐)에서는 사후·점검 동안 물체가 조건 단계가 끝난 자리(직접 배치는 놓은 자리, 보기만 static은 1.5 m)에 보입니다. 측정 순간의 시각 자극이 조건과 함께 달라지는 것을 막으려면 켭니다.
- 두 설정은 켰을 때만 manifest `config` 맨 끝에 `true`로 남습니다. 기본값에서는 화면·기록이 G59 전과 바이트 단위로 같습니다(`PlacementEnvironmentTests`의 sha256 대조가 그대로 통과). 실험자 화면 체크, 자동 시행 `-checkBeforeStopDistance`·`-practiceInAllConditions`.

| 단계 | 물체 | 넘어가는 때 |
| --- | --- | --- |
| intro | 숨김 | 실험자 Enter |
| baseline(제시) | 시작 자리(정면 1.5 m, 높이 1.2 m) | `baselineSeconds`(30) 뒤 자동 |
| pre_items / post_items / check_items | 사전은 시작 자리, 사후·점검은 조건 단계가 끝난 자리(`hideObjectDuringItems`를 켜면 숨김) | 문구 파일에 평정 지시문이 있으면 먼저 지시문 → 실험자 Enter. 문항마다 숫자(문항 범위, 기본 1–7) → Enter(선택: 참여자 컨트롤러). 해당 `when` 문항이 없으면(또는 `disabledItems`로 모두 껐으면) 단계째 건너뜀 |
| pre_wait / post_wait | 숨김 | 헤드셋 밖 설문(주 척도는 팀 결정 전이라 러너에 없음) 뒤 실험자 Enter/"다음" |
| condition | 조건별(아래) | `conditionSeconds`(90) 뒤 자동. `conditionEndsOnConfirm`을 켜면 직접 배치의 확인에서 끝남(기본 꺼짐) |
| stop_distance | 시행 중에만 보임, 정면 직선 위 | 실험자 Enter로 시행 시작 → 시행이 다 끝나면 자동 |

조건 단계:

- **place**: 광선으로 잡고(팔 길이보다 먼 곳도), 당기기/밀기로 거리를 바꾸고, 놓고, 다시 잡을 수 있습니다. 중력 없음. 바닥 원판 밖으로는 못 나가고(수평 거리를 반지름으로 자름, 방향 유지), 높이는 `[minHeightM, maxHeightM]`. 확인("여기에 둔다")은 몇 번이든 누를 수 있고 `placement.json`에는 마지막 확인 시각이 남습니다.
- **view / static**: 시작 자리에 그대로.
- **view / system_move**: `systemMoveDelaySeconds` 뒤 설정한 목표 자리로 `systemMoveSpeedMps` 직선 이동.
- **view / replay**: `replayPath`의 `trajectory.json`을 같은 시간축으로 재생(표본 사이 직선 보간, 끝나면 마지막 자리에 머묾). 원본 파일 sha256과 원본 sessionId를 manifest `replaySource`에 기록.
- **view / point_select**: 참여자가 바닥의 한 점을 가리키고 확인하면 시스템이 그 점(높이는 그대로)으로 `systemMoveSpeedMps` 직선 이동. 다시 가리키면 목표를 바꿈.

멈춤 거리: 물체가 가까워지거나(approach, 3.0 m에서) 멀어지는(recede, 0.5 m에서) 동안 참여자가 버튼을 누르면 멈춥니다. 연습 2회 뒤 방향당 4시행, 둘 다 방향 교차. 첫 방향은 `stopFirstDirection`(기본 `by_participant`: 홀수 번호 approach, 짝수 recede). `stopMinM`/`stopMaxM`에 닿으면 `timed_out`. 시행 사이 `stopItiSeconds` 동안 숨김.

- 한 프레임 순서는 "이번 프레임 이동을 먼저 반영 → 버튼 검사 → 기록"으로 고정했습니다. 그래서 `stop_distance_m` = 시작 거리 ∓ `speed_mps` × `rt_ms`가 늘 맞고, 실제로 누른 순간의 거리와 기록 거리의 차는 최대 `stopSpeedMps` × dt(프레임 길이)입니다(기본 0.25 m/s, 72 Hz면 약 3.5 mm).
- 누름은 버튼이 내려가는 순간만 셉니다(직전 프레임에 눌려 있지 않던 `StopDown`). 시행 시작 전부터 누르고 있던 버튼으로는 그 시행이 바로 멈추지 않고, 떼었다가 다시 눌러야 합니다. 시행을 시작하는 프레임의 누름은 버립니다.
- 경계 거리에 닿는 같은 프레임에 누르면 누름으로 기록합니다(`stop_distance_m` = 경계값, `timed_out` = 0).
- **첫 방향과 조건 배정이 얽힐 수 있습니다.** `stopFirstDirection`의 기본값 `by_participant`는 참여자 번호 홀짝으로 첫 방향을 정하므로, 조건 배정도 번호 홀짝으로 하면 조건과 첫 방향이 완전히 겹칩니다. 조건 배정표를 따로 만들 때는 각 조건 안에서 첫 방향이 반반이 되도록 균형을 잡고, 세션마다 `approach`/`recede`로 직접 지정하세요.

### 데스크톱 조작 키

| 누가 | 키 | 동작 |
| --- | --- | --- |
| 참여자(모의) | 마우스 왼쪽 단추 누르고 있기 | 커서 쪽 광선으로 잡기(떼면 놓기) |
| 참여자(모의) | 휠 / E · Q | 밀기·당기기(휠 한 칸 0.15 m, E/Q는 `pushPullSpeedMps`) |
| 참여자(모의) | F | 확인("여기에 둔다", 가리킨 점 확정) |
| 참여자(모의) | Space | 멈춤 거리 버튼(반복 멈춤 `stopMode loop`이면 멈춤/다시 움직임 토글. 확정은 F, 멈춘 상태에서만) |
| 참여자(모의) | 마우스 오른쪽 드래그 · WASD | 둘러보기 · 이동(`HeadPoseProvider`, 위와 겹치지 않음) |
| 실험자 | 0–9 · Backspace · Enter | 평정 입력 · 취소 · 확정. 범위가 한 자리(기본 1–7)면 숫자 하나로 입력(범위 밖 숫자 무시, 예전과 같음). 두 자리 범위(예: 0–10)는 이어 칩니다: 1 → 0 = 10, 범위를 넘는 숫자(1 다음 1)·세 번째 자리·0 뒤의 숫자는 받지 않음. Backspace는 친 숫자 전체 취소. Enter는 안내·대기 넘기기, 멈춤 거리 시작, 확인 화면에서 시작 |
| 실험자 | Esc · F1 | 중단(자료는 남고 `summary.json`에 `abortedAt`) · 실험자 화면 숨기기 |
| 실험자 | R | 정면 재설정(XR일 때만. 아래 「헤드셋 연결」) |
| 실험자 | H | 눈높이 재기(G60-3 `eyeHeightMode relative`, 확인(Checked) 화면에서 XR일 때만. 1초 표본) |

실험자 화면(IMGUI, PC 모니터에만): Setup(참여자 번호, spec, **선택 파일 selection.json(선택)**, 조건·통제 방식, 재생 원본 경로, 참여자 입력 auto/desktop/xr, 주 사용 손, 평정 선택 기능 두 개, 선택 단계 문항 묻기·끌 문항 키, 문구 파일) → 확인(선택 파일 요약: 고른 후보 또는 "맞는 것이 없다", 덮어쓰기) → 시작. 진행 중에는 단계, 남은 시간, 조건, 물체 거리·방위·높이, draft 경고, 대기 단계의 "다음" 단추, XR 상태(헤드셋·컨트롤러·추적 원점)와 정면 재설정 단추.

2026-11-23 화면 개선(결정 G44, 아래 「화면 사용성 점검」): 맨 위에 지금 단계를 크게(예: "진행 중 · 단계 pre_items", 끝나면 "끝 — 완료/중단(단계)"), 그 아래 조건·참여자·머리·입력 한 줄, 바로 이어서 오류 → 초안 문구 → 경고(예전에는 단추 아래에 있었고 초안 경고가 두 번 나왔음). 바탕은 불투명한 짙은 회색이고 내용 높이만큼만 그려 아래쪽 참여자 시점(미러)을 가리지 않습니다. 진행 중 평정이면 "입력: 5 · 참여자 컨트롤러 고르는 중: 6"을 크게 보입니다. **"중단"은 "다음"과 떨어진 오른쪽 끝의 빨간 "중단…" 단추이고, 누르면 확인 줄("세션을 중단할까요? …")과 "계속 진행(취소)"·"중단 확정"이 나옵니다**(확정이 부르는 함수는 예전과 같은 `PressAbort`). 단계가 바뀌면 열린 확인 줄은 닫힙니다(`PlacementConfirmStep`). **키보드 Esc는 예전처럼 확인 없이 바로 중단합니다**(러너가 직접 읽는 키라 바꾸지 않음 — 화면 아래에 그렇게 적혀 있음). 확인 화면의 "돌아가기"는 "설정으로 돌아가기 (Esc)"로 이름만 바꿨습니다(세션을 만들기 전이라 기록 없음).

### 설정값(`PlacementConfig`, 잠정값 — 팀 결정 전)

| 묶음 | 필드(기본값) |
| --- | --- |
| 조건 | `condition`(place), `controlMode`(static. place면 기록은 none) |
| 공간 | `floorRadiusM`(4), `ringRadiiM`([1, 2, 3]), `showRings`(true), `startDistanceM`(1.5), `startHeightM`(1.2) |
| 시간 | `baselineSeconds`(30), `conditionSeconds`(90), `conditionEndsOnConfirm`(false), `headSampleHz`(20) |
| 잡기 | `pushPullSpeedMps`(1.0), `holdMinM`(0.3), `holdMaxM`(8), `grabRadiusMinM`(0.15. 물체 경계가 더 크면 그것), `minHeightM`(0.05), `maxHeightM`(2.5) |
| 시스템 이동·가리켜 지정 | `systemMoveTargetDistanceM`(2.5), `systemMoveTargetAzimuthDeg`(0), `systemMoveTargetHeightM`(1.2), `systemMoveSpeedMps`(0.25, 가리켜 지정도 같은 속도), `systemMoveDelaySeconds`(2) |
| 재생 | `replayPath`(절대 경로 또는 기록 루트 기준. manifest에는 파일 이름만) |
| 멈춤 거리 | `stopSpeedMps`(0.25), `stopApproachStartM`(3.0), `stopRecedeStartM`(0.5), `stopTrialsPerDirection`(4), `stopPracticeTrials`(2), `stopMinM`(0.2), `stopMaxM`(4.0, 바닥 반지름 이하), `stopItiSeconds`(2), `stopHeightM`(1.2), `stopFirstDirection`(by_participant) |
| 문구 | `requireSpecPhrases`(false. 켜면 draft 문구가 있을 때 시작 거부) |
| 헤드셋(2026-11-23 추가) | `inputMode`(auto: 헤드셋이 켜져 있으면 XR, 없으면 데스크톱 · desktop · xr: 헤드셋이 없으면 시작 거부), `xrHand`(right · left), `participantRatesWithController`(false), `hideObjectDuringItems`(false — 설문 초안의 제안이지만 절차 변경이라 팀 결정 전) |
| 평정 문항(2026-11-23 D8 추가) | `askOptionalItems`(false — 켜면 문항의 `optionalWhen` 단계에서도 묻는다. 두 평정 문항 G13을 헤드셋 사전에도 물을 때), `disabledItems`([] — 묻지 않을 문항 키. 예: 기존 "내 것 같다" `own`(기본 파일)·`S4`(scaleA). 문구 파일에 없는 키면 확인 단계 오류) |
| 배치 공간 후보(2026-11-24 G52–G53 추가) | `environment`(neutral · space · nature), `placementAssist`(false), `practiceTargetDistanceM`(2.0)·`practiceTargetAzimuthDeg`(−45)·`practiceTargetHeightM`(0.8) — 연습 목표 자리 잠정값(⚠ 사람이 정할 것), `practiceCubeSizeM`(0.25). 기본값이면 manifest `config`에 이 키들을 넣지 않는다(아래 절) |
| 절차 선택(2026-11-25 G59 추가) | `checkBeforeStopDistance`(false — 켜면 점검 평정을 멈춤 거리 앞, 사후 평정 바로 뒤에), `practiceInAllConditions`(false — 켜면 놓기 도움의 배치 연습을 보기만 조건에서도. `placementAssist` 필요). 켰을 때만 manifest `config` 맨 끝에 남는다 |
| 반복 멈춤(2026-11-26 G60-2 추가) | `stopMode`(single — 예전 한 번 누름 · loop), `stopLoopMinM`(0.4)·`stopLoopMaxM`(3.6, 바닥 반지름 이하), `stopLoopStartMinM`(1.0)·`stopLoopStartMaxM`(3.0), `stopLoopRounds`(4), `stopLoopPracticeRounds`(1), `stopLoopRoundSeconds`(75), `stopLoopToggleDebounceMs`(250), `stopLoopHideRings`(true). 속도·높이·라운드 사이 시간·첫 방향은 single과 같은 `stopSpeedMps`·`stopHeightM`·`stopItiSeconds`·`stopFirstDirection`. loop일 때만 manifest `config` 맨 끝에 남는다 |
| 눈높이(2026-11-26 G60-3 추가) | `eyeHeightMode`(none — 절대 높이 · relative), `eyeHeightReferenceM`(1.6), `eyeHeightMinM`(1.30)·`eyeHeightMaxM`(1.95), `eyeCalibSeconds`(1.0), `eyeCalibMaxSdM`(0.02), `eyeCalibMaxPitchDeg`(15). relative일 때만 manifest `config` 맨 끝에 남는다 |

헤드셋 표시값은 기록에 영향이 없어 `PlacementConfig`가 아니라 컴포넌트 Inspector에 있습니다: `PlacementRunner`의 판 자리 `textForwardM`(2.0)·`textHeightM`(0.6, 판 중심), `rayOnlyWhenUsable`(true), `PlacementTextPanel`의 글자 크기(본문 `characterSize` 0.0085, 평정 숫자 `numberCharacterSize` 0.010, 기준점 뜻 `labelCharacterSize` 0.0075 — 2026-11-23 전 0.0055)·줄 길이(20자)·본문 줄 간격(`bodyLineSpacing` 1.13 ≈ 1.5 em)·기준점 칸 너비(0.22 m, 전 0.2)·여백(0.08 m, 전 0.06)·고른 칸 색(`highlightColor` 짙은 파랑, `selectionFillColor` 옅은 파랑, 테두리 `selectionFrameM` 0.012 m)·판 위 가장자리 상한(`maxTopM` 0.85 m)·아래 가장자리 하한(`minBottomM` 0.05 m), `XrPlacementInput`의 광선 굵기·길이와 썸스틱 데드존(0.2)·트리거 이력(0.55/0.35). 씬 파일(`PlacementExperiment.unity`)의 값도 같은 값으로 고쳤습니다.

### 배치 공간 후보 B·E·F (2026-11-24, 결정 G52–G56)

빈 원형 바닥만으로는 "여기 놓을 수 있겠다"는 느낌이 약하다는 문제 제기로 세 후보를 설정만 바꿔 비교할 수 있게 했습니다. **어느 공간을 본 설계로 쓸지는 정하지 않았습니다**(⚠ 사람이 정할 것). 후보 B = `neutral` + 놓기 도움, E = `space` + 놓기 도움, F = `nature` + 놓기 도움. Setup 화면의 "배경 공간" 단추와 "놓기 도움" 체크, 자동 시행 `-environment`·`-placementAssist`. 실험자 화면 머리말에 `공간 … · 놓기 도움 … 후보 B/E/F`가 보입니다(설정 이름은 실험자 화면에만 — 참여자 판에는 문구 파일 글만).

**기본값(`neutral`, 도움 꺼짐)은 G52 전과 같습니다**: 화면에 더하는 물체가 없고(`PlacementSpace` 물체 목록 그대로, 하늘 머티리얼 그대로 — Unity 테스트), 기록은 같은 입력이면 바이트 단위로 같습니다(dotnet 테스트가 G52 전 코드로 잰 sha256과 대조). 다른 점은 문구 파일 `version`이 0.2 → 0.3으로 올라 manifest `taskText.version`과 초안 경고 줄의 버전 글자가 바뀐 것뿐입니다(그 값은 파일에서 읽음).

| | neutral(B) | space(E, G54) | nature(F, G55) |
| --- | --- | --- | --- |
| 하늘 | 지금 회색 그라디언트(`EnvironmentSky`) | 직접 쓴 별 하늘 셰이더 `Resources/IFS/EnvironmentStarfield.shader`(규칙 `starfield/1`): 짙은 남색 바탕(sRGB 0.045, 0.055, 0.12 — 완전한 검정 아님), 3차원 격자 칸마다 해시로 정한 별 두 층(시간·난수 텍스처 없음 → 결정적, 화소보다 작은 별은 넓히고 어둡게), 기울어진 띠에만 옅은 성운 | CC0 360° 사진 한 장 + 직접 쓴 등장방형 셰이더 `EnvironmentPanorama.shader`(정 뒤 밉맵 이음매를 도함수로 고침) |
| 발밑 | 원형 배치 바닥(지름 8 m) | 같은 원형 바닥이 우주에 뜬 발판(아래도 별) | 같은 원형 바닥 + **실제 3D 땅 원판**(반지름 60 m, `EnvironmentGround.shader`: 사진 지평선 아래 땅 띠의 평균 색 sRGB 0.32, 0.34, 0.25에 해시 잡음 밝기 ±8 %, 20 m부터 60 m까지 알파로 사진 속 땅에 녹아듦, 빛을 다시 받지 않음) |
| 조명 | 중립 환경 그대로(방향광 1, 삼색 앰비언트, 그림자) | **같음** | **같음** — 세 공간에서 형상이 같은 빛을 받게(색 지각 비교). 하늘이 바뀌면 반사 큐브맵만 한 번 다시 찍음 |

중립 환경의 200 m 격자 바닥은 세 공간 모두 숨깁니다(배치 러너는 원래 숨김). 셰이더 세 개는 모두 `Resources/IFS/`에 있어 빌드에 늘 들어가고 `Shader.Find`를 쓰지 않으며, 단일 패스 인스턴싱 매크로가 있습니다(`EnvironmentSky.shader`와 같은 방식). 그리지 못하면(셰이더·사진 없음) 확인 단계에서 시작을 거부합니다(기록이 실제 화면과 달라지지 않게). 구현: `Runtime/Environment/EnvironmentStyle.cs`(`EnvironmentStyle.Apply`, `NatureSkyAsset`, `EnvironmentStyleInfo`).

**자연 사진(F)**: Poly Haven `farmland_overcast`("Farmland Overcast", 작가 Grzegorz Wronkowski, https://polyhaven.com/a/farmland_overcast), 라이선스 **CC0 1.0**(자산 쪽 표기와 https://polyhaven.com/license 확인), 2026-11-24에 API `/files/farmland_overcast`의 tonemapped JPG(8192 × 4096, sha256 `47171b0f…e912101a`)를 내려받아 4096 × 2048로 줄여 JPEG 품질 90으로 저장 — `Assets/IFS/Runtime/Resources/IFS/Nature/farmland_overcast_4k.jpg`(2.0 MB, sha256 `6cae5ca0bd967a67c542381710ff1d285656ce5234ee3a291f417f35533797c1`). 출처·해시 전문은 같은 폴더 `LICENSE.txt`. 흐린 날, 탁 트인 평평한 밭, 가까운 나무·바위 없음(지평선의 먼 나무 줄만), 채도 낮음. 가져오기 설정(`Editor/NatureTextureImport.cs`가 강제, 테스트가 확인): sRGB, 밉맵, 가로 반복·세로 고정, 삼선형, 최대 4096, 압축(Android ASTC 6×6 · Windows DXT1), 읽기 끔.

**놓기 도움(G53, `placementAssist`)** — 직접 배치 조건에서:

1. **배치 연습 1회**(`intro` 다음 새 단계 `practice`): 본 물체는 숨기고 뜻 없는 회색 상자(한 변 0.25 m)를 본 물체와 같은 시작 자리에 둡니다. 목표 자리는 바닥 고리 + 같은 크기의 파란 테두리 상자(설정 `practiceTarget*`, 잠정 2.0 m·−45°·높이 0.8 m). 잡기·밀기/당기기는 본 과제와 같고, 참여자가 확인을 누르면 끝(목표와의 거리는 기록만, 다시 시키지 않음), 실험자는 "다음"(Enter)으로 건너뛸 수 있습니다. 안내 글은 문구 `practice`. **기본으로 보기만(view) 조건에는 연습이 없습니다**(⚠ 사람이 정할 것). `practiceInAllConditions`(G59)를 켜면 보기만 조건에도 같은 연습이 들어갑니다(`practice.json`·`practice_*` 사건·manifest `environment.practice`도 같이).
2. 든 동안 물체 중심에서 바닥까지 수직선(굵기 8 mm)과 바로 아래 바닥 고리(반지름 = 물체 경계 반지름, 최소 0.12 m).
3. 든 물체의 수평 거리가 바닥 가장자리 1 m 안으로 들어오면 경계 띠가 회색(0.36)에서 밝은 회색(0.94)으로 smoothstep으로 밝아짐(`PlacementAssistVisuals.BoundaryGlow`).
4. 직접 배치 지시문 뒤에 줄을 바꿔 범위 안내 문장(`placement_range`, draft) "둥근 바닥 안이면 어디든, 어떤 높이든 괜찮아요."(G57에서 다듬음)

기록(형식 `ifs-placement/0.2` 그대로, 추가만): 공간 설정이 기본값이 아닐 때만 manifest 맨 끝에 `environment`{`name`, `placementAssist`, `sky`(`kind` gradient · starfield(`rule`, `seed`) · equirect_photo(`texture`{assetId·title·author·source·license·downloadedOn·file·sha256·originalSha256}, `ground`{radiusM·fadeStartM·colorSrgb})), `lighting: "neutral"`, `practice`(연습이 있으면 target·cubeSize, 없으면 null)}와 `config`의 여섯 키. 연습이 있으면 `practice.json`(목표·마지막 자리, `errorM`, `grabCount`, `heldMs`, `confirmed`, `endedBy` participant_confirm · experimenter · abort, `durationMs`)과 `events.csv`의 `practice_start`·`practice_grab`·`practice_release`·`practice_end`, `headpose.csv`의 phase `practice`(물체 칸 빈칸). **연습은 `placement.json`·`trajectory.json`·`objpose.csv`에 들어가지 않습니다**(본 과제의 잡기 수는 1부터 셈 — 테스트). `taskText.draftKeys`·`draftCount`와 초안 경고는 그 세션이 보일 수 있는 문구만 셉니다(도움이 꺼져 있으면 `practice`·`placement_range`를 뺌). 분석기 열 `environment`(키가 없는 옛 기록은 neutral)·`placement_assist`·`practice_error_m`·`practice_ended_by`, 세션 사이 공간이 다르면 `config_mismatch:environment`.

검증 캡처(G56): `docs/validation/environments/`(B·E·F를 눈높이에서 찍은 그림과 형상별 밝기 대비). 다시 찍기:

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.PlacementEnvironmentCapture.CaptureBatch \
  -outDir <저장소>/docs/validation/environments -specRoot <저장소>/docs/validation -logFile <로그>
```

### 멈춤 거리 반복 멈춤·눈높이 정규화 (2026-11-26, 교수님 피드백 2·3 — G60-2·G60-3)

둘 다 기본 꺼짐이고(⚠ 본 설계로 쓸지는 사람이 정할 것), 기본값에서는 화면·기록이 G60 전과 바이트 단위로 같습니다(`PlacementEnvironmentTests`의 golden). 설계: `docs/codex-reviews/D7_claude.md`.

**반복 멈춤(`stopMode loop`)**: 멈춤 거리 단계에서 물체가 정면(방위 0°) 직선 위 0.4 ↔ 3.6 m를 0.25 m/s로 오가고, 끝에서 감속 없이 바로 되돌아갑니다. 참여자는 트리거(데스크톱 Space)로 멈추고 다시 누르면 **멈추기 전 방향 그대로** 다시 움직입니다. 멈춘 상태에서 A(왼손 X, 데스크톱 F)를 누르면 그 자리로 확정하고 라운드가 끝납니다. 움직이는 중의 확정은 무시하고 사건(`confirm_ignored`)으로만 남깁니다. 앞서 받아들인 토글에서 250 ms 안의 다시 누름은 버립니다(`toggle_ignored`). 연습 1 + 본 4라운드, 라운드마다 출발 방향을 번갈아 두고(첫 방향은 `stopFirstDirection`), 출발 거리는 1.0–3.0 m에서 참여자 번호를 시드로 한 xorshift64*(직접 구현, Mono·dotnet·Python이 같은 값)로 1 mm 단위로 고릅니다. 라운드 상한 75초에 닿거나 한 번도 누르지 않으면 확정값은 빈칸이고 `end_reason`(`timeout_stopped`·`timeout_moving`)을 남깁니다. 마지막 멈춤 거리는 `last_stop_distance_m`에 따로 남기고 확정값으로 채우지 않습니다(원칙 2). 멈춤 거리 단계 동안 바닥 고리를 숨깁니다(`stopLoopHideRings`). 판에는 문구 `stop_distance_loop`, 멈춘 동안 그 아래에 `stop_loop_hint`(문구 파일 0.6, draft). single이면 이 두 문구는 draftKeys·초안 경고에 들어가지 않습니다.

**눈높이 기준 배치(`eyeHeightMode relative`)**: 확인(Checked) 화면에서 정면 재설정(R) 뒤 참여자에게 "편하게 똑바로 서서 앞을 봐 주세요"라고 말로 안내하고 H(또는 "눈높이 재기" 단추)를 누릅니다. 20 Hz로 1초 표본을 모아 중앙값을 E로 삼고, 추적 원점 Floor·높이 SD ≤ 2 cm·|pitch| ≤ 15°·E ∈ [1.30, 1.95] m를 모두 만족해야 통과입니다(실험자 화면에 E와 실패 이유). 재지 않았거나 통과하지 못하면 시작을 거부합니다. 데스크톱·자동 시행은 E = 1.60 고정(`source desktop_fixed` — 예전과 같은 자리). 실제 높이 = 설정 높이 + (E − 1.60)이고, 옮기는 대상은 시작 높이·멈춤 경로 높이·system_move 목표·연습 목표·참여자 판(높이와 눈 앵커)입니다. 카메라·리그 높이, 수평 거리, 참여자가 직접 놓은 높이, 재생(replay) 궤적은 옮기지 않습니다(replay와 함께 켜면 확인 화면에 경고). SceneLoader 앵커(물체 크기·모양 계산용)는 1.6 그대로입니다.

### 선택 파일(`selection.json`, 2026-11-23 D8 — 결정 G15·G23, G31–G34에서 형식 0.2)

챗봇의 후보 선택·조절 단계(D5)가 세션 기록에 쓰는 선택 파일을 원본 spec과 함께 읽습니다(`PlacementSelection.cs`, UnityEngine 없음). Setup의 "선택 파일" 칸(절대 경로 또는 spec 목록 폴더 기준 이름), 자동 시행 `-selectionPath`. 비우면 예전처럼 spec만으로 진행합니다(기존 자동 시행·테스트 그대로, manifest `selection: null`).

| 필드 | 러너가 하는 일 |
| --- | --- |
| `formatVersion` | 필수. 아는 버전은 `ifs-selection/0.1`·`ifs-selection/0.2`(둘 다 읽음). 접두어가 `ifs-selection/`이 아니거나 모르는 버전이면 **경고**(확인 화면, `events.csv` `warning`)만 하고 읽는 필드를 확인 |
| `specSha256` | 필수(16진 64자, 대소문자 무관). 러너가 읽은 spec 파일 **바이트**의 sha256과 다르면 **시작 거부**(이유 표시). 챗봇은 spec 파일을 LF 바이트로 쓰고 그 파일의 해시를 적으므로, 챗봇이 저장한 spec 파일을 그대로 넘기면 같습니다. 손으로 만든 선택 파일은 실험 PC의 spec 파일 바이트로 계산해야 합니다(git autocrlf로 체크아웃한 예시 spec은 CRLF) |
| `spec.sha256Basis` | 있으면 `file`이어야 함. 그 밖의 값(`none`, 예전 챗봇의 `serialized`)은 `specSha256`이 파일 바이트 해시가 아니라는 뜻이라 **시작 거부**(무엇이 문제인지 표시). 없으면 파일 기준으로 봄(러너 쪽 합성 파일) — G26 |
| `runnerReady` · `runnerBlockers` | `runnerReady: false`면 챗봇이 적은 이유를 붙여 **시작 거부**(spec 파일이 저장되지 않은 실행 등). 없으면 확인하지 않음 — G26 |
| `finalOverrides` | 필수 객체(`{}` = 덮어쓰기 없음). `SceneOverrideJson.Parse` 형식(평평한 키 → 값, `shapeModel`). 모르는 키·0–1 밖·잘못된 값, 위치·거리 키(`layout.distance`·`layout.verticalOffset` — 시작 자리는 실험 설정이라 G10), form.type이 blob이 아닌데 모양 모형 강제는 **시작 거부** |
| `selection.selectedCandidateId` · `selection.none` · `selection.skipped` | 그대로 기록. `none: true`인데 id가 있으면 거부. `skipped`(구별되는 후보가 하나뿐이라 선택 단계를 건너뜀, G34)는 0.2에서 필수이고, `skipped: true`인데 `none: true`이거나 id가 있으면 거부. `none`·`skipped`가 모두 false인데 id가 null이면 경고. 0.1 파일은 `skipped`가 없으면 false |
| `colorChanged` | 조절에서 색을 바꿨는지(G31). 0.2에서 필수 불리언, 0.1은 없으면 null로 기록 |
| `sources` | 객체여야 하고, 키는 스키마의 슬롯 이름 15개, 값은 0.2면 `said`·`chosen`·`edited`·`default`·`said_unrendered_chosen`·`said_unrendered_default`(뒤 둘은 모형이 없는 모양어를 말한 형태 자리, G32), 0.1이면 앞의 네 값 중 하나 — 아니면 **시작 거부**(G27). 통과하면 해석하지 않고 manifest에 그대로(없거나 null이면 null) |
| `safetyFlags` | (있으면, G50 (4) — 하위 호환 추가) 넷째 제외 범주(죽음·자해·외상) 낱말이 확정 텍스트에 나온 자리의 목록. 배열이 아니거나 항목이 객체가 아니면 거부. **시작을 막지 않습니다**(VR 진행 여부는 연구자가 정함 — 초안). `PlacementSelection.SafetyFlags`·`HasSafetyFlags`·`SafetyFlagCategories`로 들고, manifest `selection.safetyFlags`에 그대로 옮깁니다(키가 없는 파일이면 manifest에도 없음). 실험자 GUI의 경고 자리(오류·초안·경고 바로 뒤)에 범주·낱말·문장 위치·글자 위치·자리·형태 막음을 한 줄씩 보입니다(`PlacementSafetyNotice`, OnGUI 화면 좌표만 — 헤드셋 판에는 나오지 않음). 글은 연구자용 로그 문자열이고 고정 문구가 아닙니다 |
| 그 밖 | 읽지 않음(무시) |

모양어 판정(`ShapeMapping.ExtractWords`)은 `_unmapped` 기록 가운데 reason `excluded_shape`(제외 네 범주)와 `no_asset`(동물, G51)을 모양어에서 뺍니다(`ShapeMapping.UnrenderedReasons`, 챗봇 `candidates.UNRENDERED_REASONS`와 같음 — pytest가 C# 원문 대조). 그리지 않기로 한 낱말이 막은 모양어가 모양 모형을 끌어오지 않게 하는 것입니다.

덮어쓰기는 형상을 만들 때 `SceneLoader.Load(spec, 덮어쓰기)`로 **한 번** 얹고(소유감 변형본과 같은 경로, 참여자 조정 기록을 타지 않음) 조건 단계 동안 바뀌지 않습니다(VR 안에서 속성을 고치는 입력은 없음 — G11). 로드한 뒤 덮어쓰기 키마다 그려지는 해석값(모양 모형은 그려지는 모형)이 덮어쓰기 값과 같은지 확인하고, 다른 키가 하나라도 있으면 시작을 거부합니다. 확인 뒤 시작 전에 선택 파일이 바뀌면 거부합니다(spec과 같은 규칙). 시작하면 `events.csv`에 `selection` 한 줄(`file=…;none=0|1;candidate=…;skipped=0|1;colorChanged=0|1|(빈칸);applied=<키 수>`, 경고가 아님)을 남깁니다. manifest `selection`에는 `skipped`·`colorChanged`도 들어갑니다(기록 형식은 `ifs-placement/0.2` 그대로, 키만 더함). 합성 예시·자동 시행 결과: `docs/validation/runner-selection/`.

물체 시작 자리는 spec의 `layout.distance`·`verticalOffset` 대신 `startDistanceM`·`startHeightM`을 씁니다(두 조건이 같은 자리에서 시작해야 하므로). 크기·모양·색·움직임은 spec 그대로입니다. 시작 자리는 참여자가 말한 속성이 아니라 실험 설정이라는 것을 manifest `space.startPlacementSource: "experiment_config"`로 남깁니다. spec의 `layout.distance`나 `verticalOffset`에 값이 있었는데 이렇게 무시하면, 확인 화면 경고와 `events.csv`의 `warning` 한 줄(detail이 `layout_ignored`로 시작)을 남기고 manifest `flags.layoutIgnored`를 true로 둡니다.

거리는 모두 물체 중심 기준입니다(놓은 거리, `objpose.csv`·`headpose.csv`의 거리, 멈춤 거리). 참여자에게 보이는 물체 가장자리까지의 거리는 물체 반지름만큼 짧습니다. 반지름은 manifest `object.boundingRadiusM`에 남깁니다(불러온 직후 물체 렌더러 경계 상자의 가장 큰 반폭, 움직임으로 커지는 몫은 빠짐. 구할 수 없으면 null).

### 문구 파일

`StreamingAssets/IFS/placement_task.v0.json` — `ownership_task.v0.json`과 같은 구조(`version`, `protocol`, `texts.{key}.text · status · source`)에 평정 문항 필드 `when`(pre | post | check 또는 배열), `anchors.low/high`(1과 7의 뜻)를 더했습니다. **19개 모두 `status: draft`**(IRB 검토 전, `source`에 출처. 2026-11-23 D8에서 두 평정 문항을 더해 version 0.1 → 0.2, 2026-11-24 G53에서 놓기 도움 문구 `practice`·`placement_range`를 더해 0.2 → 0.3 — 두 문구는 `placementAssist`를 켰을 때만 보이고 그때만 필수, scaleA 파일도 같은 두 문구를 더해 0.3-scaleA. G57 문구 다듬기로 0.4. 2026-11-25 G59에서 세 문항을 더해 0.5 — 아래).

평정 문항(기본 파일 0.6, 파일 순서 = 묻는 순서): 사전 `own` → `distance_feel` / 사후 `own` → `appearance_match` → `representativeness` → `want_to_know` → `withdraw_attention` → `distance_feel` / 점검 `placed_by_me` → `place_fit`. (0.6, 2026-11-26 G60: 점검 `want_move`를 뺌 — 멈춤 거리 과제에 여러 번 고칠 수 있는 기능을 넣기로 해서, 교수님 결정. 예전 0.5 기록의 `rating_want_move_check` 열은 분석기가 그대로 읽고, 0.6 기록에서는 빈 값입니다.)

- **G59 문항(2026-11-25, `source`에 "docs/decisions.md G59, 2026-11-25"와 "IRB 검토 전")**: 거리감 `distance_feel`("지금 이것과 나 사이는 얼마나 멀게 느껴지나요?", 1 매우 가깝다 – 7 매우 멀다, 사전·사후 목록의 맨 끝 — Kross·Ayduk 계열 자기 거리두기 문항과 Takasawa(2021)의 걱정과의 거리 7점 문항을 물체에 맞게 옮긴 초안, 원문 대조 전), RQ3 자리 평정 `place_fit`("방금 이것이 있던 자리는 나에게 알맞게 느껴졌다")·`want_move`("할 수 있었다면 이것을 다른 자리로 옮기고 싶었다" — G60, 0.6에서 뺌, 둘 다 점검, 1 전혀 그렇지 않다 – 7 매우 그렇다 — 두 조건 공통이라 보기만 조건에도 대응 값이 생김). 분석기는 `rating_{item}_{when}` 열을 문항 키대로 만들므로 고치지 않았습니다. 배치 지시문은 방향을 암시하는 말("멀리", "치우다")을 쓰지 않습니다. draft 문구가 있으면 확인 화면 맨 위 경고, `events.csv`의 `warning`, manifest `taskText.draftCount`·`draftKeys`에 남습니다(소유감 러너와 같은 방식).

2026-11-23 형식 추가(선택 필드, 기존 파일은 그대로 유효 — 테스트가 확인):

- `anchors`의 숫자 키 `"1"`…`"7"`: 기준점마다의 뜻(예: 7점 모두, 또는 양극 척도의 1·4·7). `low`·`high`가 없으면 숫자 키의 양 끝을 씁니다. `low`·`high`·범위 안 숫자 말고 다른 키는 오류입니다. 헤드셋 판은 문항 아래에 1–7 숫자와 그 아래 뜻을 칸마다 보입니다.
- `items_instruction`(공통)과 `items_instruction_pre`·`_post`·`_check`(단계별 덧붙임): 평정 단계 첫 문항 앞에 보이는 지시문. 실험자 Enter로 첫 문항으로 넘어갑니다(`rt_ms`는 문항이 보인 때부터). `events.csv`에 `items_instruction` 줄.

2026-11-23 D8 형식 추가(선택 필드, 기존 파일은 그대로 유효 — 테스트가 확인):

- 문항별 범위 `min`·`max`(정수, 없으면 1–7, 0 ≤ min < max ≤ 100). `anchors` 숫자 키도 이 범위 안이어야 합니다. 구별 프로파일의 0–10 문항(M1p·M2·M3, `docs/rq-v4-differentiation-measure.md`)을 받기 위한 것입니다. D8에서는 기능과 테스트만 넣었고, 2026-11-25 G59에서 scaleA 파일에 **M2 하나만** 실제로 넣었습니다(아래 scaleA 절. 기본 파일에는 0–10 문항이 없음, 주 척도는 사람이 정할 것). 실험자 키보드는 두 자리(10)까지 이어 치고, 참여자 컨트롤러는 가운데 값(0–10이면 5)에서 시작해 범위 안에서 한 칸씩, 헤드셋 판의 숫자 줄도 범위만큼(칸이 7개보다 많으면 줄 전체가 7칸 너비가 되게 칸을 좁힘). `ratings.csv` 형식은 그대로(값만 범위대로).
- `optionalWhen`(pre | post | check 또는 배열): 설정 `askOptionalItems`를 켰을 때만 그 단계에서도 묻습니다. 평정 문항이 아닌 키(when 없음)에 `min`·`max`·`optionalWhen`을 쓰면 오류.
- **두 평정 문항(G13)**: 모습 일치 `appearance_match`("이 물체의 모습은 내가 떠올린 것과 비슷하다")와 대표성 `representativeness`("이 물체는 내가 떠올린 그것을 나타낸다", G57에서 "형상" → "물체"), 1–7, `status: draft`, `source`는 "docs/prompts/prototype-v4-build.md G13, 2026-11-22 …". 두 파일 모두 `when: post`, `optionalWhen: pre` — 흐름상 사전 측정은 데스크톱에서 하므로(G11) 헤드셋에서는 기본 **사후만** 묻고, 사전에도 물으려면 `askOptionalItems`를 켭니다. 기본 파일은 `own` 바로 뒤, scaleA는 사후 끝(S7 뒤). 기존 "내 것 같다"(`own`, scaleA `S4`)는 지우지 않았고 `disabledItems`로 끌 수 있습니다. 하한 점검 기준(대표성)의 값은 정하지 않았습니다(⚠ 사람이 정할 것).

**두 번째 문구 파일 `placement_task.scaleA.v0.json`**(선택, Setup에서 고름): `docs/rq-v4-questionnaire-draft.md` 3절의 주 척도안 A 7문항(사전·사후, 7점 기준점 모두 이름)과 보조 문항 S4(사전)·S5·S6(사전·사후)·S7(사후)·S8(사전, 1·4·7 양극), 공통 지시문과 사후 덧붙임 문장. **24개 모두 `status: draft`**, `source`에 초안 문서의 절과 문항 ID(두 평정 문항 G13은 지시문 G13). 순서는 초안 3.7절(사전 A1–A7·S5·S6·S4·S8 = 11문항, 사후 A1–A7·S5·S6·S7 = 10문항)에 사후 끝 G13 두 문항(= 사후 12문항, version 0.1-scaleA → 0.2-scaleA). S3(겹침 그림 IOS)은 그림 선택지가 필요해 뺐고, S1(심리 거리)은 이번 묶음에서 함께 뺐습니다(S1 자체는 글 양극 척도라 anchors 1·4·7로 넣을 수 있음). S2는 초안에서도 선택 문항이라 넣지 않았습니다. 단계 안내 문구(intro 등)는 기본 파일과 같습니다. 기본 문구 파일은 바뀌지 않았고 기본 선택도 그대로입니다.

scaleA 0.6-scaleA(0.5-scaleA 2026-11-25 G59, 0.5-scaleA 기준 키 29개, 0.6-scaleA 2026-11-26 G60에서 `want_move` 키 하나를 뺌, 모두 draft): 사전·사후 끝에 구별 프로파일 초안(`docs/rq-v4-differentiation-measure.md` 3.1절) 문구 그대로 **M2**("지금 나는 나 자신을 이것과는 별개로 경험한다.", 0–10, 기준점 0 전혀 아니다 · 10 매우 그렇다 — 설문 초안 3.2절 B′용 11점)와 **P1**("지금 나와 이것의 관계는 어느 쪽에 더 가깝나요?", 1 이것이 곧 나다 · 4 반반이다 · 7 이것은 나에게 있는 것이지, 나 전체는 아니다), 그 뒤 맨 끝에 `distance_feel`, 점검에 `place_fit`(이 파일에는 `placed_by_me`가 없음 — 조작 확인은 사후 S7). 순서: 사전 A1–A7·S5·S6·S4·S8·M2·P1·distance_feel = 14문항, 사후 A1–A7·S5·S6·S7·appearance_match·representativeness·M2·P1·distance_feel = 15문항, 점검 1문항(자동 시행 평정 30개). 점검 문항이 생겨 공통 지시문(`items_instruction`)이 점검 앞에도 한 번 보입니다(점검용 덧붙임 문장 `items_instruction_check`는 없음).

### 기록 (계약 `ifs-placement/0.2`, 참여자 데이터 — git 밖)

`{recordRoot}/placement/P{번호:000}/{sessionId}/{UTC yyyyMMdd-HHmmss}[-n]/`. UTF-8(BOM 없음), InvariantCulture, `\n`. 좌표: '나'의 자리 = 바닥 중심(세계 원점), 바닥 y = 0, 정면 +z. Python 분석기 `ifs_chatbot.eval.placement`가 읽습니다(헤더·필드 이름은 EditMode 테스트가 고정).

| 파일 | 내용 |
| --- | --- |
| `manifest.json` | `recordVersion`, `participantNumber`, `sessionId`, `specFile`(이름만), `specSha256`, `startedAtUtc`, `unityVersion`, `headSource`(xr/desktop), `inputSource`(desktop/auto/xr), `condition`, `controlMode`, `space`(`startPlacementSource: "experiment_config"` 포함), `stopDistance`, `object`(`boundingRadiusM`, 없으면 null), `replaySource`(null 또는 file·sha256·sourceSessionId), `systemMoveTarget`(null 또는 distanceM·azimuthDeg·heightM), `taskText`, `config`, `flags`(`autoMode`, 실제 첫 방향, `layoutIgnored` 등), **0.2 추가:** `selection`(선택 파일이 없으면 null, 있으면 `file`(이름만)·`sha256`(선택 파일의)·`formatVersion`·`none`·`selectedCandidateId`·`finalOverrides`(원문)·`sources`(원문, 없으면 null)), `appliedOverrides`(실제로 적용된 키 → 그려지는 값, 키 이름순, 덮어쓰기가 없거나 선택 파일이 없으면 `{}`) |
| `headpose.csv` | `time_ms,phase,head_x..head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg` — 머리–물체 3D 거리·시선 각(소유감 기록과 같은 뜻). 물체가 숨은 동안 물체 칸은 빈칸 |
| `objpose.csv` | `time_ms,phase,obj_x,obj_y,obj_z,distance_m,azimuth_deg,height_m,state` — 물체가 보일 때만, headpose와 같은 표본 시각. `distance_m`은 '나'에서 수평 거리, 방위는 오른쪽 + (−180, 180], state ∈ idle/held/system/replay/stop |
| `events.csv` | `phase`(detail = 단계 이름), `grab`, `release`, `confirm`, `point_select`, `system_move_start/end`, `replay_start/end`, `stop_trial_start`, `stop_press`, `stop_timeout`, `rating`, `auto_mode`, `warning`, `head_source`. 계약에 더해 `session_start`, `rating_cancel`, `abort`, `quit`. 2026-11-23 추가(쓸 때만 나옴): `items_instruction`(평정 지시문, detail `when=…;keys=…`), `xr_status`(XR로 시작할 때 장치 이름·손·추적 원점), `recenter`(정면 재설정: 돌린 각·옮긴 거리·머리 높이), 참여자가 컨트롤러로 확정한 `rating`은 detail 끝에 `;by=controller` |
| `placement.json` | 조건 단계 요약(두 조건 모두): `phaseDurationMs`, 최종 위치·거리·방위·높이, `grabCount`, `firstGrabMs`, `heldMs`, `pathLengthM`(누가 옮겼든 실제 이동 길이. static만 0), `confirmed`, `confirmMs`, `conditionCompleted`(정해진 끝 — `conditionSeconds`를 다 채움 또는 `conditionEndsOnConfirm`의 확인 — 까지 갔으면 true, 중단으로 조기 종료하면 false) |
| `stopdistance.csv` | `trial,practice,direction,start_distance_m,speed_mps,stop_distance_m,rt_ms,timed_out` — timed_out이면 `stop_distance_m` 빈칸 |
| `ratings.csv` | `item,when,rating,rt_ms` — 확정한 평정만(취소는 `events.csv`의 `rating_cancel`) |
| `trajectory.json` | `ifs-trajectory/0.1`: 조건 단계 궤적. 표본 t_ms는 조건 단계 시작부터, 첫 표본 0 ms, 마지막 표본은 단계가 끝난 시각 |
| `summary.json` | `completed`, `abortedAt`, `endedAtUtc` |

2026-11-23 기록 형식 변경은 추가만 했습니다(`recordVersion`은 그대로 `ifs-placement/0.1`, 기존 열·키 삭제 없음): manifest `config`에 `inputMode`·`xrHand`·`participantRatesWithController`·`hideObjectDuringItems` 네 키, `inputSource`에 실제 값 `xr`, 위 `events.csv` 사건들. `hideObjectDuringItems`를 켜면 평정 단계 동안 물체가 숨어 `objpose.csv`에 그 단계 행이 없고 `headpose.csv`의 물체 칸이 빈칸입니다(숨은 단계의 기존 규칙). 분석기(`ifs_chatbot.eval.placement`)는 바꾸지 않았습니다(추가 키·사건을 읽지 않음, 문항 열은 `rating_A1_pre`처럼 자동으로 생김).

**0.1 → 0.2(2026-11-23 D8·D9)**: 추가만 했습니다. manifest에 `selection`·`appliedOverrides` 두 키, `config`에 `askOptionalItems`·`disabledItems` 두 키, `events.csv`에 `selection` 사건(선택 파일로 시작할 때만). CSV 헤더·다른 manifest 키·파일 목록은 그대로이고, 선택 파일 없이 돌리면 내용은 0.1과 같고 `recordVersion`과 두 키(`selection: null`, `appliedOverrides: {}`)만 다릅니다. `ratings.csv`의 값은 문항 범위대로(기본 1–7, 범위를 넓힌 문항은 예: 0–10). 분석기 `ifs_chatbot.eval.placement`는 `recordVersion`이 접두어 `ifs-placement/`로 시작하는 manifest를 모두 읽으므로 0.2 기록도 읽힙니다. 다만 아는 버전 목록(`KNOWN_VERSIONS`)이 `ifs-placement/0.1`뿐이라 0.2 세션에는 `version_mismatch` 플래그가 붙습니다(분석기는 이번에 고치지 않음 — 목록에 0.2를 더하는 것은 chatbot 쪽 작업). 분석기는 `selection`·`appliedOverrides`를 읽지 않습니다.

**2026-11-25 G59(형식 0.2 유지, 추가만)**: manifest `config`에 `checkBeforeStopDistance`·`practiceInAllConditions`를 켰을 때만(`true`) 맨 끝에 붙입니다. `checkBeforeStopDistance`면 `events.csv` phase 순서가 `post_items → check_items → post_wait → stop_distance → done`(분석기의 조건 단계 뒤 단계 목록에 `check_items`가 이미 있어 `abortedAt` 해석은 같음). 기본값에서는 G59 전과 바이트 단위로 같습니다.

**2026-11-26 G60-2·G60-3(형식 0.2 유지, 추가만)**: `stopMode loop`이면 새 파일 `stoprounds.csv`(라운드 1행: `round,practice,start_dir,start_distance_m,speed_mps,final_distance_m,first_stop_distance_m,last_stop_distance_m,n_stops,n_resumes,final_motion_dir,passes_before_confirm,stop_spread_m,at_bound,end_reason,duration_ms,eye_object_distance_m`)와 `stopadjust.csv`(사건 1행: `round,practice,time_ms,t_ms,event,distance_m,motion_dir,rt_ms` — event는 start·stop·resume·turn·confirm·confirm_ignored·toggle_ignored·timeout·abort, `t_ms`는 라운드 시작부터, `rt_ms`는 직전 상태 변화(시작·멈춤·재개)부터)를 만들고 `stopdistance.csv`는 헤더만 남습니다. manifest `stopDistance`에 `mode`·`loop{minM, maxM, speedMps, heightM, startMinM, startMaxM, startRule, rounds, practiceRounds, roundSeconds, toggleDebounceMs, hideRings, input, plan[]}`, `events.csv`에 `stop_round_start`·`stop_round_end`, `objpose.csv` state에 `stop_paused`(멈춘 동안). `end_reason` = confirmed · timeout_stopped · timeout_moving · aborted(라운드 중 중단). `at_bound`는 확정값이 끝에서 5 cm 안, `passes_before_confirm`은 출발·끝점 반사·멈춤 자리를 이은 구간 가운데 확정 거리를 안쪽에 품은 구간 수. `eyeHeightMode relative`면 manifest 맨 끝에 `eyeHeight{mode, referenceM, measuredM, offsetM, sdM, pitchDeg, samples, trackingOrigin, source}`, `events.csv`에 `eye_height_calibrated`(session_start 바로 뒤). manifest `space.startHeightM` 등은 설정값 그대로이고 옮긴 양은 `eyeHeight.offsetM`입니다. 분석기 열은 `chatbot/ifs_chatbot/eval/placement.py` 머리말.

중단(Esc·Play 멈춤)하면 그때까지의 CSV가 남고, 조건 단계 중이었으면 그때까지의 `placement.json`(`conditionCompleted: false`)·`trajectory.json`도 씁니다. 분석기는 이런 세션에 `partial_condition`을 달고 조건 단계 지표 칸을 비웁니다.

### 실행

- 씬: 메뉴 **IFS ▸ Experiment ▸ Create Placement Experiment Scene** → `Assets/IFS/Scenes/PlacementExperiment.unity`를 열고 Play(2026-11-22 배치 진입점으로 만들어 둠. 망가지면 메뉴로 다시 만듭니다).
- 자동 시행(검증용, 합성 입력 `PlacementAutoScript`: 잡기–옮기기–놓기 2번(다시 잡기), 확인, 가리켜 지정, 첫 평정 잘못 누름·취소, 멈춤 거리 버튼 시점, 일부러 누르지 않는 시행 1개):

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.RunAutoTrialBatch \
  -recordRoot <기록 루트> -specPath <spec.json> -condition place|view -controlMode static|system_move|replay|point_select \
  [-replayPath <trajectory.json>] [-participant 1] [-conditionSeconds 90] [-baselineSeconds 30] [-headSampleHz 20] \
  [-stopItiSeconds 2] [-showRings true|false] [-hideObjectDuringItems true|false] \
  [-taskTextFile IFS/placement_task.scaleA.v0.json] [-selectionPath <selection.json>] \
  [-askOptionalItems true|false] [-disabledItems own,S4] [-stopMode single|loop] [-stopLoopRoundSeconds 75] \
  [-eyeHeightMode none|relative] [-dt 0.02] -logFile <로그>
```

`-quit` 없이(끝나면 스스로 닫음), 성공 0·실패 1. 씬 만들기 배치: `-executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.CreateSceneBatch`. 자동 시행·씬 만들기·배치 캡처는 에디트 모드라 XR을 시작하지 않습니다(XR은 Play·빌드 실행 때만).

2026-11-22 확인: 합성 예시 `EX02.json`으로 기본 설정(제시 30 s, 조건 90 s) 자동 시행 5개(place, view의 static·replay(place의 궤적)·system_move·point_select)가 모두 완료됐고, 기록은 `docs/validation/placement/records/`(합성), 분석기 출력은 `docs/validation/placement/analysis/`에 있습니다. 분석기 플래그는 세션마다 `runner_warning:1`(draft 문구 경고, 의도한 것)뿐이었습니다. 외부 검토 CP7 반영 뒤 같은 설정으로 다시 만들었습니다(`conditionCompleted` true 5개, `object.boundingRadiusM` 0.1933, `layoutIgnored` false, 플래그는 그대로 `runner_warning:1`뿐, `config_mismatch` 없음). 2026-11-23 헤드셋 프로토타입(XR 패키지 추가) 뒤 같은 5개를 저장소 밖 임시 폴더에 다시 돌려 모두 완료, 분석기 플래그는 세션마다 `runner_warning:1`뿐이었습니다(`docs/validation/placement/`은 갱신하지 않음).

### 화면 사용성 점검(2026-11-23, 결정 G44)

참여자 판과 실험자 화면을 `ui-ux-pro-max` 스킬의 규칙(§1 접근성, §2 상호작용, §5 배치, §6 글자·색, §8 폼·피드백)으로 고쳤습니다. 문구 글자·문항 순서·평정 방식(점 수·앵커·확정 방식)·단계 순서·측정과 기록은 바꾸지 않았고 화면 표현만 바꿨습니다. 전후 캡처와 실측값: `docs/validation/ui/before/unity_*`, `docs/validation/ui/after/unity_*`(`unity_metrics.json`에 글자 높이·대비비).

| 항목 | 전 | 후 | 규칙 |
| --- | --- | --- | --- |
| 기준점 뜻 글자(한글 잉크 높이, 눈–판 중심 2.24 m) | 3.32 cm = 0.85° | 4.55 cm = 1.17° | readable-font-size(VR에서 약 1° 이상) |
| 평정 숫자("7" 잉크 높이) | 3.90 cm = 1.00°(본문 크기) | 4.60 cm = 1.18° | readable-font-size |
| 본문(한글 잉크 높이) | 5.13 cm = 1.31° | 그대로 | — |
| 본문 줄 간격 | 1.33 em | 1.50 em | line-height |
| 이웃 기준점 뜻 | 7점 모두 이름이면 붙어 읽힘 | 칸 너비(0.22 m)에 맞춰 줄바꿈, 이웃 사이 빈틈 5 cm 이상 | line-length-control, whitespace-balance |
| 본문 대비(렌더 화소) | #4F4F5A 대 #FFFFFF = 8.1:1 | #16161C 대 #FFFFFF = 18.0:1 | color-contrast |
| 고른 값 | 색(옅은 파랑 #5AA0ED, 흰 판에서 2.7:1)·숫자만 굵게 | 짙은 파랑 #0D389E 숫자·뜻 굵게 + 테두리 + 옅은 파랑 바탕(#D1E3FF), 7.8:1 | color-not-only, color-accessible-pairs |
| 긴 지시문 판 | 위로 자라 위 가장자리 0.98 m | 위 가장자리 ≤ 0.85 m(아래로 내림) | visual-hierarchy(형상 가리지 않기) |
| 실험자 화면 바탕 | 반투명 — 장면에 따라 주황 2.3–4.6:1, 노랑 3.0–6.0:1, 빨강 1.7–3.3:1 | 불투명 짙은 회색 #1F2023 — 흰 16.3, 주황 7.7, 노랑 10.1, 빨강 6.1:1 | color-contrast, contrast-feedback |
| 실험자 화면 단계·경고 | 단계는 제목 줄 끝 작은 글, 경고는 단추 아래, 초안 경고 두 번 | 단계를 맨 위 크게, 오류·초안·경고를 그 바로 아래, 초안 경고 한 번 | visual-hierarchy, error-placement |
| 중단 단추 | "다음"과 같은 크기로 바로 옆, 한 번에 중단 | 오른쪽 끝 빨간 "중단…" → 확인 줄 → "중단 확정"(단계가 바뀌면 닫힘). Esc 키는 그대로 | confirmation-dialogs, destructive-emphasis, touch-spacing |
| Setup 가로 넘침 | 손 선택·체크 글이 오른쪽에서 잘리고 가로 스크롤 | 줄을 나누고 체크 글 줄바꿈 | horizontal-scroll |

시야각 = 2·atan(높이 / (2 × 2.236 m)), 2.236 m = √(2.0² + (1.6 − 0.6)²)(눈높이 1.6 m, 판 중심 정면 2.0 m·높이 0.6 m 가정). 잉크 높이는 같은 글꼴·크기의 한 글자를 흰 바탕에 찍어 어두운 화소 행으로 잰 값입니다(`PlacementPanelMetrics.HangulInkPerEm` 0.94, `DigitInkPerEm` 0.72). 대비비는 렌더 화소(sRGB)의 WCAG 2.x 식(`PlacementPanelMetrics.ContrastRatio`). 판 캡처의 눈 시점은 세로 시야 28.8°(720 px, 약 25 px/°)로 Quest 3 화소 밀도를 흉내 낸 근사이고, 렌즈·화면을 거친 실제 가독성은 기기에서만 확인됩니다.

캡처 도구 `Editor/PlacementUiCapture.cs`(합성 spec EX02와 문구 파일만, 기록은 저장소 밖 임시 폴더):

```bash
# 참여자 판(배치모드): unity_panel_*.png, unity_scene_item.png, unity_metrics.json
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.PlacementUiCapture.CapturePanelsBatch -outDir <폴더> -logFile <로그>
# 실험자 화면(IMGUI는 Play의 Game 창에서만 그려져 배치모드가 아니라 에디터 창으로 실행, 끝나면 스스로 닫힘): unity_gui_*.png
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -projectPath <unity 폴더> \
  -executeMethod IFS.SceneSpec.EditorTools.PlacementUiCapture.CaptureGuiInteractive -outDir <폴더> -logFile <로그>
```

두 번째 명령은 Play를 하므로 Unity가 `ProjectSettings/QualitySettings.asset`·`Assets/XR/Settings/OpenXRPackageSettings.asset`을 다시 쓸 수 있습니다(`git checkout -- <파일>`로 되돌림). 화면에 로컬 절대 경로가 찍히지 않게 spec 목록 폴더는 프로젝트 기준 상대 경로, 기록 폴더 표시는 자리표시로 바꿔 찍습니다(캡처 때만). 문서용 PNG는 폭 1280 이하·256색으로 줄였습니다.

참여자 판에 입력 방법 안내(예: "썸스틱 좌우로 고르고 트리거로 확정")는 없습니다. 참여자에게 보이는 새 문구가 되므로 만들지 않았습니다(⚠ 사람이 정할 것 — 넣는다면 문구 파일에 `status: draft`로).

### 한계와 사람이 할 일

- 헤드셋 경로는 사람이 헤드셋을 쓰고 확인하지 않았습니다(`docs/headset-checklist.md`로 확인할 것).
- 참여자 판은 정면 2.0 m·중심 높이 0.6 m(눈높이 1.6 m에서 약 27° 아래)에 고정입니다. 판 글은 깊이 검사를 해서 물체가 앞에 오면 물체가 글을 가립니다(글이 물체를 덮지 않음). 판은 물체(1.5 m)보다 뒤(2.0 m)에 있어 시작 자리의 물체를 가리지 않고, 겹쳐 보이면 물체가 판 위쪽을 가립니다. 2026-11-23부터 판 위 가장자리가 0.85 m(`maxTopM`)를 넘으면(긴 평정 지시문처럼 키가 큰 판) 판을 아래로 내려, 위로 자라 물체 뒤로 들어가지 않게 했습니다(EX02 캡처에서 판 위 가장자리가 물체 아래쪽보다 아래). 반지름 0.3 m 물체를 시작 자리에 두면 판 위쪽 몇 cm는 여전히 물체 뒤에 보일 수 있습니다(여백 0.08 m 안). 직접 배치에서 참여자가 물체를 판 앞으로 가져오면 글이 가려질 수 있습니다. 읽히는 크기·자리는 기기에서 봐야 합니다.
- 데스크톱 모의 조작에서는 광선이 보이지 않습니다(마우스 커서가 대신함). 잡힌 물체 강조는 없습니다(XR 광선 끝이 물체 중심에 붙는 것으로만 보임).
- 재생은 원본의 물체 위치만 따릅니다(원본 참여자의 머리 움직임은 재생하지 않음).
- 눈 추적은 없습니다(Quest 3에는 눈 추적 장치가 없고, `headpose.csv`의 시선 각은 머리 방향 기준).

## 헤드셋 연결 (Quest 3 + Quest Link, OpenXR)

2026-11-23 추가. PC에서 Unity(에디터 Play 또는 Windows 빌드)를 돌리고 Quest 3를 Quest Link(케이블 또는 Air Link)로 연결합니다. 실험자는 PC 모니터와 키보드로 진행하고, 참여자는 헤드셋과 컨트롤러 하나를 씁니다. **사람이 헤드셋을 쓰고 확인하지는 않았습니다** — 처음 쓸 때 `docs/headset-checklist.md`를 따라 확인하고 결과를 적어 주세요. Quest 단독(Android) 빌드는 하지 않았습니다(후속).

### 프로젝트에 들어간 것

| 항목 | 값 |
| --- | --- |
| 패키지 | `com.unity.xr.management` 4.6.1, `com.unity.xr.openxr` 1.16.1, `com.unity.inputsystem` 1.20.0(OpenXR이 의존). Unity 6000.0.85 에디터가 권장하는 버전(에디터의 `PackageManager/Editor/manifest.json`). Meta XR SDK 같은 큰 SDK·분석 SDK는 넣지 않았습니다 |
| Active Input Handling | **Both**(`ProjectSettings.asset`의 `activeInputHandler: 2`). 기존 코드가 구 Input Manager(`UnityEngine.Input`)를 쓰므로 둘 다 켜 둡니다 |
| XR Plug-in Management(PC, Standalone) | OpenXR 로더, *Initialize XR on Startup* 켬 — `Assets/XR/XRGeneralSettingsPerBuildTarget.asset`, `Assets/XR/Loaders/OpenXRLoader.asset`, `EditorBuildSettings.asset`의 config 객체 |
| OpenXR(Standalone) | Render Mode **Single Pass Instanced**, 상호작용 프로필 **Oculus Touch** + **Meta Quest Touch Plus** — `Assets/XR/Settings/OpenXRPackageSettings.asset` |
| 다시 맞추기·확인 | 메뉴 **IFS ▸ XR ▸ Configure OpenXR (Windows, Quest Link)** · **IFS ▸ XR ▸ Report XR Settings**(배치: `-executeMethod IFS.SceneSpec.EditorTools.XrProjectSetup.ConfigureBatch` / `ReportBatch`). 코드는 `Editor/XR/XrProjectSetup.cs`(패키지가 있을 때만 컴파일) |

XR 런타임 API는 러너 코드에서 직접 쓰지 않습니다. 러너는 내장 XR 모듈(`UnityEngine.XR.InputDevices`·`XRSettings`·`XRInputSubsystem`)만 읽으므로, XR 패키지 커밋을 되돌려도 러너는 데스크톱 모의 조작으로 그대로 컴파일·동작합니다.

### 실행 순서(처음 한 번)

1. PC에서 **Meta Horizon Link**(Oculus 앱)를 켜고 Quest 3를 USB-C 케이블(또는 Air Link)로 연결한 뒤, 헤드셋 안에서 Link를 시작합니다. Link 앱 ▸ 설정 ▸ 일반에서 OpenXR 런타임이 Meta(Oculus)로 "활성"인지 봅니다(이 PC는 레지스트리 `ActiveRuntime`가 `oculus_openxr_64.json`).
2. Quest에서 경계(Guardian)를 **실제 바닥 높이**로 맞춰 둡니다(바닥 원판 y = 0이 실제 바닥과 맞으려면 필요).
3. Unity에서 `Assets/IFS/Scenes/PlacementExperiment.unity`를 열고 **Play**. Game 창을 한 번 클릭해 키보드 포커스를 줍니다(Scene 창은 닫아 두는 편이 프레임에 좋습니다). XR은 Play를 누를 때만 초기화되므로, Link를 Play 뒤에 켰으면 Play를 다시 누릅니다.
4. 실험자 화면 맨 위에 `머리: xr`, `XR: 헤드셋 켜짐(…)`, `추적 원점: Floor`가 보이는지 확인합니다. 참여자를 '나'의 자리(바닥 원판 가운데 둥근 표식)에 세우고 정면을 보게 한 뒤 **R**(정면 재설정)을 누릅니다 — 물체 시작 자리가 참여자 정면 1.5 m에 옵니다.
5. Setup: 참여자 번호, spec, 조건·통제 방식, 참여자 입력(**auto** 그대로), 주 사용 손, (선택) 평정 기능·문구 파일 → **확인**. 경고(컨트롤러 안 보임, 추적 원점, 초안 문구)를 읽고 → **시작(Enter)**.
6. 끝나면 실험자 화면에 기록 폴더가 나옵니다. 분석: `cd chatbot; .venv\Scripts\python.exe -m ifs_chatbot.eval.placement --records <기록 루트> --out <결과 폴더>`.

Windows 빌드(선택): 메뉴 **IFS ▸ Experiment ▸ Build Placement Experiment (Windows)**(배치: `PlacementExperimentMenu.BuildWindowsBatch`) → `unity/Builds/Placement/IFSPlacement.exe`(git 제외). 빌드에서 spec 목록 폴더는 `persistentDataPath/IFS/scenes`(기본 `%USERPROFILE%\AppData\LocalLow\DefaultCompany\unity\IFS\scenes`, 실험자 화면에 경로가 보임)이고 기록은 `persistentDataPath/IFS/sessions`입니다. spec을 그 폴더에 넣거나 절대 경로를 적습니다. Link를 켠 뒤 exe를 실행합니다.

### 컨트롤러 조작(참여자, 주 사용 손 하나 — 기본 오른손)

| 조작 | 동작 |
| --- | --- |
| 광선(가는 파란 선 + 끝점 구) | 컨트롤러 조준 방향. 조건 단계의 직접 배치·가리켜 지정에서만 보입니다(`rayOnlyWhenUsable`). 끝은 잡은 물체 중심 → 맞은 물체 겉면 → 바닥 점 → 최대 8 m 순 |
| 트리거(또는 그립) 누르고 있기 | 광선이 물체에 맞으면 잡기, 떼면 놓기. 다시 잡기 됨. 팔 길이보다 먼 물체도 광선으로 잡힘 |
| 썸스틱 앞 / 뒤 | 잡은 물체 밀기 / 당기기(`pushPullSpeedMps` 1 m/s, 광선 원점에서 0.3–8 m, 바닥 원판 밖으로는 못 나감) |
| A(오른손) · X(왼손) | 확인("여기에 둔다" / 가리킨 바닥 점 확정) |
| 트리거 | 멈춤 거리 버튼. 누르는 순간만 셉니다(시행 전부터 누르고 있었으면 떼었다 다시). 반복 멈춤(`stopMode loop`)이면 멈춤/다시 움직임 토글이고, 확정은 A(왼손 X) — 멈춘 상태에서만 |
| 썸스틱 좌·우 + 트리거 | 평정 고르기·확정 — `participantRatesWithController`를 켰을 때만(기본 꺼짐: 참여자는 말로 답하고 실험자가 숫자 키). 처음 젖히면 가운데 값(4)에서 시작, 판에서 고른 칸이 짙은 파랑 테두리·옅은 파랑 바탕·굵은 짙은 파랑 숫자와 뜻으로 보임(색만으로 구별하지 않음) |
| 실험자 R | 정면 재설정(지금 머리 자리 = '나'의 자리, 보는 방향 = 정면). 세션 중이면 `events.csv`에 `recenter` |

보기만 조건(static·system_move·replay)은 기존 규칙대로 잡기·밀기 입력을 받지 않습니다(테스트로 확인). 트리거 아날로그 값은 이력(0.55에서 눌림, 0.35에서 뗌)으로 떨림에 여러 번 눌리지 않게 했고, 썸스틱 데드존은 0.2입니다. 컨트롤러 추적이 끊기면 그 프레임은 입력이 없는 것으로 보고(잡은 물체는 놓임), 다시 잡혔을 때 계속 누르고 있던 버튼은 새 '눌림'으로 세지 않습니다.

### 헤드셋 안 표시와 렌더

- **참여자 판**(`PlacementTextPanel`): 정면 2.0 m, 판 중심 높이 0.6 m(눈높이 1.6 m에서 약 27° 아래, 키가 큰 판은 위 가장자리 0.85 m 이하로 내려감), 판이 눈을 보게 기울어 있습니다. 눈–판 중심 2.24 m에서 한글 잉크 높이 본문 1.31°·기준점 뜻 1.17°·평정 숫자 1.18°(아래 「화면 사용성 점검」), 한 줄 20자, 줄 간격 약 1.5 em. 판 배경은 재질 색이 옅은 회색(#E6E6E8)이지만 방출 + 조명으로 흰색(#FFFFFF)으로 렌더됩니다(그대로 둠, 짙은 글 대비 18:1). 한글은 기존 방식 그대로 OS 동적 폰트(맑은 고딕 등, `ParticipantTextDisplay.EnsureFont`)와 `TextMesh`입니다(uGUI·TextMeshPro 없음). 평정 단계에서는 문항 아래 숫자와 기준점 뜻을 칸마다 보이고, 뜻은 칸 너비에 맞춰 줄을 바꿉니다(예전에는 7점 모두 이름이 있으면 이웃 칸 뜻이 붙어 "전혀 그렇지 그렇지 않다 약간 그렇지"처럼 읽혔음). TextMesh 기본 재질은 깊이 검사 없이 모든 것 위에 그리므로, 판 글 재질은 `unity_GUIZTestMode = LessEqual`로 바꿔 물체가 판 앞에 오면 물체가 글을 가리게 했습니다(글이 물체를 덮지 않음). TextMesh 정점 색은 선형 색공간에서 변환되지 않으므로 Inspector 색(sRGB)을 `Color.linear`로 넘깁니다(2026-11-23 전에는 짙은 글 #141419가 #4F4F5A로, 고른 숫자가 #5AA0ED로 보여 흰 판에서 2.7:1이었음).
- **실험자 화면**(IMGUI)은 PC 모니터의 Game 창에만 그려지고 헤드셋에는 나오지 않습니다. 코드 근거: `PlacementExperimenterGui`는 `OnGUI`의 화면 좌표(`GUILayout.BeginArea(new Rect(…))`)로만 그리고 세계 공간 물체·Canvas·RenderTexture를 만들지 않습니다. IMGUI는 카메라 렌더가 끝난 뒤 주 디스플레이 백버퍼에 그려지고, XR 눈 영상은 카메라가 XR 디스플레이 텍스처로 렌더한 것이라 IMGUI가 들어가지 않습니다(Game 창에서는 왼눈 미러 위에 겹쳐 보임). 기기에서는 확인하지 못했습니다(`docs/headset-checklist.md` 1.3).
- **스테레오**: OpenXR 단일 패스 인스턴싱. 커스텀 셰이더 점검: `SceneSpecMist.shader`(정점/조각)는 스테레오 매크로를 갖추고 있었고, 조각 단계에서 물체 행렬을 읽으므로 인스턴스 ID를 조각 단계까지 넘기도록(`UNITY_TRANSFER_INSTANCE_ID`·조각의 `UNITY_SETUP_INSTANCE_ID`) 보탰습니다. `EnvironmentSky.shader`는 이미 갖춤(조각 단계에서 눈별 값을 쓰지 않음). `SceneSpecOpaque`·`SceneSpecFade`·`EnvironmentFloor`는 표면 셰이더라 Unity가 스테레오 코드를 만듭니다. 판·광선은 내장 셰이더(GUI/Text, Standard)입니다. 스테레오 인스턴싱 변형의 실제 컴파일·두 눈 일치는 헤드셋 Play에서만 확인됩니다(미검증). 문제가 있으면 `Assets/XR/Settings/OpenXRPackageSettings.asset`(Project Settings ▸ XR Plug-in Management ▸ OpenXR ▸ Render Mode)을 Multi Pass로 바꿔 비교합니다.
- **카메라 리그**: `XR Rig ('나' 자리)`(원점 = '나'의 자리) 아래에 카메라. XR이 켜지면 추적 원점을 바닥(Floor)으로 요청하고, 카메라 로컬 자세 = 헤드셋 자세(`HeadPoseProvider`, 렌더 직전에 한 번 더). 기록 좌표계는 그대로입니다('나' = 원점, 바닥 y = 0, 정면 +z).

### 헤드셋이 없을 때(자동 대체)

`inputMode` auto(기본)에서 헤드셋이 없으면 데스크톱 모의 조작으로 돕니다. Link가 꺼진 채 Play하면 OpenXR 초기화가 실패하면서 콘솔에 OpenXR 경고·오류가 찍힐 수 있지만 Play는 계속되고 `머리: desktop`, `입력: desktop`이 됩니다. `inputMode` xr로 강제하면 헤드셋이 없을 때 확인 단계에서 시작을 거부합니다. 배치모드(테스트·자동 시행·씬 만들기·배치 캡처)는 Play가 아니라 XR을 시작하지 않습니다.

### 문제 해결

| 증상 | 확인할 것 |
| --- | --- |
| XR이 안 잡힘(`XR: 헤드셋 없음`, `머리: desktop`) | Link 앱 실행·헤드셋 안 Link 켜짐 → OpenXR 런타임이 Meta로 활성인지 → **Play 다시**(XR은 Play 시작 때만 초기화) → 콘솔의 OpenXR 메시지 → 메뉴 IFS ▸ XR ▸ Report XR Settings에서 `standalone.loaders=…OpenXRLoader`, `initManagerOnStart=True` → Project Settings ▸ XR Plug-in Management ▸ OpenXR의 *Play Mode OpenXR Runtime*이 System Default(또는 Oculus)인지 |
| 컨트롤러가 안 보임(확인 화면 경고) | 컨트롤러를 흔들어 깨우기, 손 추적 모드면 컨트롤러를 집어 들기, 주 사용 손 설정(right/left) 확인. 경고만 뜨고 시작은 됩니다 |
| 글자가 안 보임 | 판은 정면 아래쪽(약 27°)에 있습니다 — 고개를 조금 숙이게 안내. 물체·판이 엉뚱한 쪽이면 R(정면 재설정). 한글이 □로 나오면 확인 화면의 폰트 경고(맑은 고딕 없음). 물체를 판 앞으로 가져오면 글이 가려집니다(의도). 자리·크기는 `PlacementRunner ▸ Text Forward M / Text Height M`, `PlacementTextPanel ▸ Character Size` |
| 바닥 높이가 안 맞음(원판이 떠 있거나 발 아래로 꺼짐) | 확인 화면 경고 "추적 원점이 바닥(Floor)이 아닙니다" → Quest 경계·바닥 높이를 다시 설정(헤드셋 설정 ▸ 물리적 공간 ▸ 경계/바닥) → Play 다시. 기록의 머리 높이(`headpose.csv` head_y)가 참여자 눈높이와 맞는지 봅니다 |
| 물체가 정면에 없음·'나' 자리가 어긋남 | 참여자를 원판 가운데에 세우고 R. 세션 중에 누르면 기록 좌표가 그 순간 바뀌므로(`events.csv`의 `recenter`) 가능하면 시작 전에 맞춥니다 |
| 끊김·멀미 | Scene 창을 닫고 Game 창만, 또는 Windows 빌드로 실행. 72 Hz 유지는 미측정 |

## 미리보기(WebGL)

후보·조절 화면(D5)에서 형상을 Unity 렌더로 보여 주기 위한 것입니다(결정 G12). 결과·판정 제안·재현 명령은 `docs/validation/webgl/README.md`.

- **JSON 문자열 로드**: `SceneLoader.LoadJson(json, 이름, 덮어쓰기)`. 파일 로드와 같은 내부 경로(파싱·검사·해석·렌더·기록)를 탑니다. 같은 파일 이름을 주면 notes·기록까지 `Load(path)`와 같습니다(EditMode 테스트가 golden 지문으로 확인). WebGL 플레이어에서는 파일을 못 읽으므로 이것만 씁니다. 덮어쓰기 목록 JSON은 `SceneOverrideJson.Parse`(manifest의 `overrides`와 같은 평평한 객체 + `shapeModel`).
- **무대**: `PreviewStage` = 중립 환경 + 고정 카메라(눈높이 1.6 m에서 형상 경계 중심을 봄, 세로 시야 60°) + 기록을 끈 로더, 품질 단계 `VR PC`. WebGL·Windows 플레이어·에디터 캡처가 모두 이 코드를 씁니다.
- **씬**: `Assets/IFS/Scenes/Preview.unity` — GameObject `IFS Preview`(`PreviewBridge`) 하나. 메뉴 **IFS ▸ Preview ▸ 미리보기 씬 다시 만들기**.
- **브라우저 → Unity**: `unityInstance.SendMessage("IFS Preview", 메서드, 문자열)` — `LoadSpecJson(spec)`, `ApplyOverridesJson({"form.type":"mist",…})`(빈 문자열 = 덮어쓰기 지움), `SetAutoRotate("12")`, `SetFrozen("1")`, `Capture({"id","width","height","background":"scene|black|white"})`. 템플릿 페이지는 이것을 `window.ifsPreview.load()` 등 Promise로 감쌉니다. Unity → 브라우저 알림은 `.jslib`(`ready`·`loaded`·`error`·`capture`). 마우스 왼쪽 드래그 = 세로축 회전.
- **빌드**: `PreviewBuild.BuildWebGLPreview`(압축 끔·템플릿·캐싱 끔을 빌드 동안만 바꾸고 되돌림, 출력은 저장소 밖 `../webgl-build/preview`). **2026-11-23 이 PC에는 WebGL 모듈이 없어 빌드하지 못했습니다**(설치에 관리자 확인 필요).
- **대안 경로**: `PreviewBuild.BuildWindowsPreview` → `IFSPreview.exe -batchmode -ifsPreviewQueue <폴더>`. 폴더 요청마다 PNG를 씁니다(`PreviewQueue`). 에디터 캡처와 24개 spec에서 덮인 화소 수가 같고 평균 색 ΔE00 최대 0.045, 요청 왕복 중앙값 15.2 ms(800×600).
- 에디터 캡처: `PreviewCapture.Run -specDir … -outDir … [-width 800 -height 600 -backgrounds scene,black,white]`.

## 테스트

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -runTests -testPlatform EditMode -testResults <결과.xml> -logFile <로그>
```

RQ v2 계열(2026-11-18, 브랜치 `claude/intelligent-cannon-2m4uu6`에서 병합) 당시 기록: EditMode 161개(2026-11-17 소유감 실험 외부 리뷰 반영 뒤 배치모드로 전부 통과). 2026-11-18 같은 말·다른 값 쌍(생성기 0.3)과 CP5 검토 반영으로 46개를 더해 207개 — dotnet compile-check(UnityOnly 제외 186개)는 통과, Unity 배치모드는 아직 돌리지 않음. 그 계열이 더하거나 고친 소유감 테스트(`OwnershipVariantTests`·`OwnershipRecordTests`·`Golden/ownership_v02_*.json` 등)는 병합 뒤 위 개수에 아직 다시 세지 않았습니다.

EditMode **504개**(2026-11-26 G60-2·G60-3 뒤 배치모드로 전부 통과, dotnet 435개 — 더한 것: `PlacementStopLoopTests.cs` 20개(기본값 single·none이면 새 config 키·파일·draftKeys 없음, 설정 검증과 켰을 때 config 끝 키 순서, 라운드 계획의 시드 결정성(xorshift64* 출력과 참여자 1·2·7의 출발 거리를 고정값으로 — Unity(Mono)에서도 같음), 자동 시행 한 바퀴(stoprounds·stopadjust 헤더·행, 움직이는 중 확정 무시, 상한 도달 빈칸, manifest mode·loop·plan, 사건, stop_paused), 멈춘 동안만 조작 안내 문구, 토글·같은 방향 재개·디바운스·rt, XR 트리거·A 원자료로 토글·확정, 확정은 멈춘 상태에서만, 멈춘 채 상한(확정 빈칸·마지막 멈춤 남김), 무입력·양 끝 반사, 지나간 횟수, 끝 5 cm `at_bound`, 라운드 중 중단, 반복 멈춤 문구 없으면 loop만 거부, 두 문구 파일의 반복 멈춤 문구(draft·G60-2 출처·금지어), 눈높이 보정 판정(Floor·SD·pitch 위·아래·범위·표본 수), pitch 부호와 20 Hz 표본, E = 기준이면 none과 같은 파일, E만큼 시작·멈춤·system_move·연습 높이를 옮기고 놓은 높이는 그대로, 보정 없거나 범위 밖이면 거부), `UnityOnly/PlacementRunnerStopLoopTests.cs` 2개(러너 자동 시행에서 멈춤 거리 단계 동안만 고리 숨김·desktop_fixed, 헤드셋인데 재지 않았거나 Floor가 아니라 보정 실패면 시작 거부·다시 재면 거부 줄 지움). `PlacementEnvironmentTests`의 draftKeys 테스트는 반복 멈춤 문구 두 개를 빼는 것까지로 고침). 그 전 482개(2026-11-25 G59 헤드셋 쪽 보완 뒤 배치모드로 전부 통과, dotnet 415개 — 더한 것: `PlacementTests.CheckBeforeStopDistance_asks_check_items_right_after_post_items`(place·view static·point_select에서 점검이 사후 바로 뒤·멈춤 거리 시행보다 먼저, 점검 동안 물체는 조건이 끝난 자리, 점검 문항을 모두 끄면 단계째 건너뜀, 점검 중 중단 = `check_items`, 기본값이면 config에 키 없음), `PlacementEnvironmentTests.PracticeInAllConditions_gives_view_conditions_the_same_practice`(보기만 static·point_select에 같은 연습·practice.json·environment.practice, 보기만 지시문 그대로, 연습 잡기가 본 결과에 섞이지 않음, 놓기 도움 없이 켜면 오류, 기본값이면 키 없음) — dotnet·Unity 둘 다. 기존 테스트는 문항 수·순서·자동 응답 값·버전(0.5, 0.5-scaleA)과 scaleA M2의 0–10 범위·P1 문구를 고침). 그 전 480개(2026-11-24 배치 공간 후보 G52–G56 뒤 배치모드로 전부 통과, dotnet 413개 — 더한 것: `PlacementEnvironmentTests.cs` 14개(기본값 기록이 G52 전 코드로 잰 sha256과 같음 — Unity(Mono)에서는 headpose.csv만 빼고, 설정 기본값·검증·키, 배치 연습 기록·본 결과와 섞이지 않음·건너뛰기·중단, 보기만 조건에는 연습 없음, 범위 문장은 도움을 켠 직접 배치에서만, 도움 문구가 없으면 시작 거부, manifest environment·사진 sha, draftKeys에서 도움 문구 빼기, 두 문구 파일의 도움 문구(draft·G53 출처·금지어·버전 0.3), 경계 띠 밝기, 새 셰이더 세 개가 Resources에 있고 단일 패스 매크로, 별 하늘 원문에 시간·난수·텍스처 없음, 자연 사진 sha·LICENSE·4096 × 2048 — dotnet·Unity 둘 다), `UnityOnly/PlacementEnvironmentRenderTests.cs` 7개(셰이더 Resources 로드·컴파일, 사진 가져오기 설정(밉맵·압축·ASTC), 배경 공간 바꾸기·되돌리기와 neutral 무변화, 별 하늘 렌더가 다시 만들어도 같은 화소·남색·별, 기본값 공간 물체 목록 그대로·도움 물체, 러너 자동 시행(놓기 도움 + 자연), 러너가 씬 환경에 공간을 얹고 되돌림)). 그 전 459개(2026-11-23 G44와 G45–G51 병합 마무리 뒤 배치모드로 전부 통과, dotnet 399개 — 더한 것: G45–G51의 `PlacementSelectionTests` safetyFlags 1개(`LegacyFilesTests`는 no_asset 단언만 보탬), 병합 마무리의 `PlacementSelectionTests.Safety_notice_lines_for_the_experimenter_gui_only` 1개(알림 줄, 진행·중단 단추를 부르지 않음, 실험자 GUI만 씀 — dotnet·Unity 둘 다)). 그 전 457개(2026-11-23 화면 개선 G44 뒤 배치모드로 전부 통과, dotnet 397개 — 더한 것: `PlacementPanelMetricsTests.cs` 8개(시야각 식, 기본 글자 크기가 2.24 m에서 잉크 1° 이상, WCAG 대비비, 기본 색 쌍 4.5:1 이상, 칸 너비·뜻 줄바꿈, scaleA 7점 뜻이 이웃 칸과 붙지 않음, 고른 칸, 중단 두 번 누르기 — dotnet·Unity 둘 다), `UnityOnly/PlacementTextPanelTests.cs` 2개(고른 칸 테두리·굵기·색과 고르기 전 표시 없음, 선형 색 변환, 키가 큰 판의 위 가장자리 ≤ 0.85 m)). 그 전 447개·dotnet 389개. 그 전 440개(2026-11-23 기본 형상 D6 뒤 배치모드로 전부 통과, dotnet 383개). 그 전 335개(2026-11-23 구름 수정(D7)·러너 선택 파일(D8·D9) 뒤 배치모드로 전부 통과. 그 전 307개(미리보기 D4). 그 전 278개(헤드셋 프로토타입), 257개, 배치 러너 CP7 반영 때 192개). 아래 표는 2026-11-22 기준이고, 그 뒤 더한 것은 표 아래에 적었습니다:

| 파일 | 개수 | 내용 |
| --- | --- | --- |
| `SceneSpecDeserializationTests.cs` | 14 | 기존: 예시 JSON 역직렬화·왕복, 미지정 슬롯·기본값 기록, 조정량, 기록기, 구 메시 |
| `CaptureMathTests.cs` | 9 | CIEDE2000(Sharma·Wu·Dalal 2005 시험 쌍 4개), sRGB → Lab 기준점, 캡처 인자, 백분위수, 색 기본값 성분(h·s·l 중 하나라도), 색 요약(말한 색과 기본값 분리) |
| `UnityOnly/EnvironmentAndCaptureTests.cs` | 5 | 선형 색공간·VR 품질 단계, 환경(방향광 1·소프트 섀도·무채색·셰이더 컴파일·정리), 환경 Dispose의 RenderSettings 복원, form.type 변경 시 머티리얼 사본 누수 없음, 배치 캡처 한 바퀴(예시 2개, 콘솔 오류 0, 불투명 scene = inContext, 요약의 stated/withDefaults) |
| `ShapeMappingTests.cs` | 33 | 원뿔 메시(정점·삼각형 수, 경계 상자, 인덱스, 바깥 감기 방향, 밑면 각진 모서리), 모양어 판정 규칙(표 4개, 표에 없는 값, charSpan 순서, conflict, form.type) |
| `UnityOnly/ShapeModelTests.cs` | 5 | 모양 모형 팩토리·프리팹 에셋(루트 크기 1, 배율은 자식, IFS 머티리얼 변위 0), SceneLoader 적용·`initialScene.json` 기록, 표에 없는 모양어·형태 우선, 조정 중 form.type 변경 |
| `OwnershipVariantTests.cs` | 115 | 소유감 실험 변형본: n조건 Williams(n = 4–9, 각 위치·순서쌍 균형, 5조건은 예전 표와 같음), 보여 줄 조건을 정한 뒤 순서, 쌍을 끄면 0.2 manifest와 바이트까지 같음(`Golden/ownership_v02_*.json`), 크기·색 쌍(최소 각·목표 ΔE·대칭, skipReason 6종, 무효면 둘 다 빠짐), 쌍 설정 검사, 실험자 화면에 쌍은 id만, CP5(반올림 전 범주 검사·skipped_neutral, 최소 이동폭, 화면 폭 wM·자세, basis·provenanceWithoutValue·axisChoiceBasis, 최소 대칭 색 쌍 전수 비교, 반올림 값 상한, cb의 n 일반화·7조건 두 주기 행 × cb), Williams 표 성질(각 조건이 각 위치에 2번, 순서쌍 2번씩), cb·순서 행, 1–20번 행 × cb 완전 교차, 같은 입력 → 같은 manifest 문자열, manifest 필드·specFile 이름만, 크기 방향·강제, 색(유채색은 색상만·최소 각·ΔE ≥ 목표, 무채색은 명도만, 명도 대체, belowTarget, 밝기 배율을 넣은 알베도 기준, 합성 ΔE00은 기록만), 움직임 add/remove·보이지 않는 조합(표 고정, 모양 모형 없는 형태는 보임, 자세 변형 + 흔들림은 보임)·motionAltersScale, 형태 표 4행, source·saidNotRendered, 원본과 같으면 오류, lowVisibility, `_inferred` 안 씀, SpecCheck 구분(말한 값/기본값/근거 없음)이 생성기 source와 같은 기준 |
| `OwnershipRecordTests.cs` | 15 | 기록 파일 헤더(계약 문자열 고정, ratings.csv 끝 열 item)·폴더 구조·UTF-8 BOM 없음·줄바꿈 LF, 같은 초 재시작, 중단 요약, 표본 시각(밀린 프레임 하나에 표본 하나, 실제 시각), `viewing_start` detail 형식, 문구 파일(0.2: 초안·금지 표현·닮음 문항·{n}, 0.1은 mine + 5조건에서만), 보기 전 보고(세 필드만 읽기·해시·바이트 복사·requirePrereport 거부·내용이 계획에 영향 없음), `first_viewing_utc`, draft 문구 목록·경고·`requireSpecPhrases` 거부, 글 줄바꿈, 시선 각·호 배치 계산 |
| `UnityOnly/LoaderNoVariantGoldenTests.cs` | 1 | 변형 경로를 넣기 전 로더로 만든 지문(`Golden/loader_no_variant.golden.txt`: 적용값·notes·계층·머티리얼·기록)과 `Load(path)`가 같음 |
| `PlacementTests.cs` | 28 | 배치 실험(2026-11-22): 설정 검증, 거리·방위·높이, 바닥 경계 clamp, 광선 잡기·바닥 가리키기, 문구 파일(전부 draft·출처·금지어·`when`), draft 경고(events·manifest)·`requireSpecPhrases`, 기록 파일 헤더·manifest/placement/summary/trajectory 키가 계약과 같음, 조건별 흐름(place·static·system_move·point_select·replay), 평정·취소, 궤적 쓰기→재생 왕복, 확인으로 조건 끝내기, 멈춤 거리 순서·역균형·timed_out, 문항 없는 단계 건너뛰기, 조건 단계 중단(`conditionCompleted` false), 표본 주기. CP7 반영: 미리 누르고 있던 멈춤 버튼, 경계에 닿는 프레임의 누름, 기록 거리 = 시작 ∓ 속도 × rt, dt 0.02·0.011에서 조건 단계 길이·시행 수 같음, spec layout 무시 경고·`layoutIgnored`·물체 반지름 |
| `UnityOnly/PlacementRunnerTests.cs` | 3 | 배치 러너 + SceneLoader(EX02) 자동 시행 place → 그 궤적으로 view/replay, 세션 위치가 Unity 물체 위치에 그대로, 공간(반지름·윗면 y = 0·고리 끄기) |
| `UnityOnly/OwnershipLoaderTests.cs` | 10 | `Load(path, null)`·빈 덮어쓰기도 golden과 같음, 변형본이 계획대로 그려지고 조정 기록에 남지 않음(3종), 잘못된 덮어쓰기 거부, 자동 시행 한 바퀴의 기록 폴더(draft 수·경고 포함), `requireSpecPhrases` 켜면 시작 거부, 합성 배경 = 하늘 지평선 색, 로더 `_BaseColor` = `RenderedColor.BaseSrgb`, 0.3초 밀린 프레임이 있는 자동 시행(표본 시각 중복 없음·빈 간격·형상마다 `viewing_start` ≤ 첫 표본) |

2026-11-23 헤드셋 프로토타입에서 더한 것(21개):

| 파일 | 개수 | 내용 |
| --- | --- | --- |
| `PlacementXrTests.cs` | 15 | 입력 고르기 규칙(XR 유/무 × auto·desktop·xr), 새 설정 기본값·검증, XR 입력 규칙(가짜 장치: 트리거 이력·눌린 순간, 그립, A 확인, 꺼 둔 동안·장치 끊김 뒤 가짜 눌림 없음, 썸스틱 데드존·평정 한 칸씩), 광선 끝 길이, view 조건에서 XR 잡기·밀기 무시, XR 밀기로 팔 길이 너머 → holdMaxM·바닥 경계 clamp → 당기기 holdMinM, anchors 숫자 키·기존 파일 호환·잘못된 키 거부, scaleA 파일(전부 draft·출처·순서·기준점·금지어), scaleA 한 바퀴(지시문 → 문항, 평정 31개 — G59 뒤), `hideObjectDuringItems`, 참여자 컨트롤러 평정(가운데에서 시작·트리거 확정·`by=controller`, 끄면 무시, 실험자 입력 우선), `recenter` 기록 |
| `MistShaderSourceTests.cs` | +1 | 안개·하늘 셰이더의 스테레오 인스턴싱 매크로(인스턴스 ID를 조각 단계까지) |
| `UnityOnly/PlacementRunnerXrTests.cs` | 5 | 씬 구성(리그 아래 눈높이 카메라, XR 없으면 정면 재설정 안 함), 헤드셋 없으면 auto → desktop·강제 xr 거부, 헤드셋 있음(흉내) + 가짜 컨트롤러 → `inputSource: xr`·잡기·밀기가 세션과 그리기에 반영·`xr_status`, 참여자 판 자리(정면 2 m, 눈높이 아래)·평정 기준점 줄·평정 동안 숨김, scaleA 자동 시행 |

2026-11-23 구름 수정(D7)에서 더한 것: `MistLumpsTests.cs`(덩어리 배치 seed 결정성·다른 seed·규칙 버전에 묶인 기본 배치·대리 구 안·덩어리 겹침·계획 JSON `mistRule`·밀도 프리셋 0.5 그대로·밝기 대비 지표), `MistShaderSourceTests`(+1: 덩어리 수·가장자리 폭·`_Lump0…` 선언·opacity를 최종 알파에 그대로 곱함), `UnityOnly/MistRendererTests`(머티리얼 `_Lump0…`·`_Seed`, maxAlpha가 opacity의 0.9–1배·대비 지표 있음), golden은 GOLD-mist notes만 다시 씀. `Stubs/UnityStubsMist.cs`(`Vector4`, `Material.SetVector`·`GetVector`).

2026-11-23 러너 선택 파일(D8·D9)에서 더한 것: `PlacementSelectionTests.cs`(13: 선택 파일 파싱·sha 불일치 거부·모르는 키·위치/거리 키 거부·모르는 formatVersion 경고·없을 때 기존 동작·manifest 0.2 키 `selection`·`appliedOverrides`·문항 범위 0–10 키보드 두 자리·컨트롤러·G13 두 문항 draft·사전/사후 설정·기존 문항 끄기), `PlacementTests`·`PlacementXrTests` 기대값 갱신(평정 순서·개수), `UnityOnly/PlacementRunnerSelectionTests.cs`(3: 덮어쓰기가 형상에 한 번 그려지고 manifest 0.2에 남음, sha 불일치·적용 못 한 덮어쓰기는 시작 거부, 선택 파일 없을 때 기존 동작과 "맞는 것이 없다" 기록).

2026-11-26 스펙 2.3 윤곽·발광(G61 ①)에서 더한 것(EditMode 504 → 560, dotnet 435 → 486): `ContourTests.cs`(+51: 슈퍼쿼드릭 단계마다 정점·삼각형 수·결정성·경계 상자 1 × 1 × 1·면 방향과 법선·닫힌 메시, e = 1 구(반지름 오차 1e-5)·e = 0.1 상자·단계 순서, 규칙 버전별 메시 해시 고정, 2.3.0 파싱·검사·왕복·`provenance.variant`·표에 없는 값은 파싱 오류, 2.2와 세 값 null인 2.3의 해석값·계획 동일성, 적용 순서 1–4·`defaultsUsed`, 발광 = 바탕색 × 세기(모든 경로), 덮어쓰기 키, 합성 예시 `StreamingAssets/IFS/examples/v2.3/`), `UnityOnly/ContourLoaderTests.cs`(+5: golden 지문 spec 8개를 2.2와 2.3(null)로 로드해 지문·기록이 같음, 발광 null·none이면 화소가 같고 glowing이면 다름, 슈퍼쿼드릭 메시·머티리얼·`_IfsEmission`·기록, 축 배율과 조절 중 전환, 합성 예시 로드). golden 지문 파일은 바꾸지 않았습니다(`Describe`·`DescribeRecords`만 public으로).

2026-11-23 기본 형상 D6에서 더한 것(EditMode 342 → 440, dotnet 290 → 383): `BaseShapeTests.cs`(+93: 형상·변형값 조합마다 메시 결정성·삼각형 상한 5,120·경계 상자·면 방향과 법선·넓이 0 없음·닫힌 메시, 규칙 버전별 기본 메시 해시 고정, 변형값이 메시를 바꿈, 2.2.0 파싱·왕복·검사(버전·근거·모르는 기본 형상·다른 형상의 변형 키·모르는 변형 키는 파싱 오류), `SceneParams` 기록(2.2 spec에만 `form.base`), 렌더 계획(blob·미지정만 base, mist·shell·fragments는 not_applied_form, 모양어 not_applied_base, 모양 모형 강제가 앞섬, 변형값은 같은 기본 형상일 때만), 조절 항목 × 기본 형상(G22), 덮어쓰기·선택 파일의 `form.base`, 소유감 변형이 `form.base`를 건드리지 않음(G21)), `UnityOnly/BaseShapeLoaderTests.cs`(+5: 형상마다 렌더 경로·메시·IFS 셰이더·정점 변위 0, 재질 슬롯·크기·Fade, 조절 중 전환과 머티리얼 정리, 2.1 spec에 덮어쓰기, 배치 러너가 선택 파일의 `form.base`를 그리고 manifest에 남김). compile-check 스텁에 `PlayerSettings.SplashScreen`(커밋 a40c295의 `PreviewBuild.cs`가 씀)을 더함.

2026-11-23 연구 책임자 결정 G31–G34 반영에서 더한 것(3개, EditMode 342개·dotnet 290개 전부 통과): `PlacementSelectionTests.cs`(+3: 0.2의 `skipped`·`colorChanged`·새 출처 값 읽기, 0.2 필수 필드와 건너뜀 모순 거부, 0.1은 출처 네 값만·새 필드 선택). 기존 테스트의 manifest `selection` 키 목록과 `events.csv` 선택 줄 기대값을 고침.

2026-11-23 CP9 반영(G26·G27)에서 더한 것(4개, EditMode 339개·dotnet 287개 전부 통과): `PlacementSelectionTests.cs`(+4: `spec.sha256Basis`가 file이 아니면 이유를 밝히고 거부, `runnerReady: false`면 챗봇이 적은 이유를 붙여 거부, `sources` 슬롯 이름·출처 값 검사, 챗봇이 쓴 spec 파일과 선택 파일의 바이트 대조(`docs/validation/selection-flow/runs`)). `UnityOnly/PlacementRunnerSelectionTests.cs`의 합성 `sources` 키를 덮어쓰기 키(`material.color.h`)에서 슬롯 이름(`material.color`)으로 고침.

2026-11-23 미리보기(D4)에서 더한 것(29개):

| 파일 | 개수 | 내용 |
| --- | --- | --- |
| `SceneOverrideJsonTests.cs` | 24 | 덮어쓰기 목록 JSON: 숫자·문자열·`shapeModel` 나누기, 빈 입력 = 덮어쓰기 없음, 잘못된 JSON·객체 아님·뒤에 남은 내용·모르는 키·0–1 밖·모르는 형태·motion.type·null·bool·모르는 모형 거부(이유 포함), manifest `overrides` 왕복, 같은 글 → 같은 덮어쓰기, 배경 이름(scene·black·white) |
| `UnityOnly/PreviewTests.cs` | 5 | `LoadJson` = `Load(path)`(golden 지문 spec 8개, 기록 파일 포함), 덮어쓰기를 얹어도 같음, 잘못된 JSON·null은 false이고 이전 형상 유지·`SpecPath` null, 무대: 같은 spec 두 번 찍으면 화소가 같음·검은 배경 모서리 = 검정(이전 렌더를 읽지 않음)·덮인 화소 있음·카메라가 형상을 봄·mist는 안개 셰이더 경로, 브리지: `loaded`·`error`·`capture` 알림 내용(JS 계약) |

로그 확인: EditMode 로그에는 테스트 프레임워크의 스택 프레임 `UnityLogCheckDelegatingCommand:CaptureException`이 정상 실행에서도 찍힙니다(CP4 실행 36줄, 외부 리뷰 반영 실행은 로그 문구가 늘어 더 많음). 오류를 찾을 때는 `Select-String -Pattern 'error CS|Shader error|^\w*Exception:|\[Exception\]'`처럼 좁히거나 이 프레임을 빼고 셉니다(이번 실행 0건). 캡처 로그는 넓은 패턴(`Exception|error CS|Shader error`)으로도 0건입니다.

## 컴파일 확인 (dotnet)

Unity가 없는 곳(CI 등)에서는 `Tools/compile-check/`에서 dotnet으로 확인합니다(netstandard2.1, C# 9, 경고도 오류로).

```bash
cd unity/Tools/compile-check && dotnet build IFS.SceneSpec.CompileCheck.csproj && dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj
```

- 미리보기(D4)에서 `Stubs/UnityStubsPreview.cs`(`PlayerSettings.WebGL`·`EditorUserBuildSettings`·`WebGLCompressionFormat`·`SceneAsset`·`StereoTargetEyeMask`·`RuntimePlatform`)와 기존 스텁 몇 줄(`Camera.stereoTargetEye`, `Transform.eulerAngles`, `Application.platform`·`Quit`, `SystemInfo.graphicsDeviceVersion`, `Input.GetMouseButtonUp`, `BuildTarget.WebGL`·`BuildTargetGroup`·`IsBuildTargetSupported`, `BuildSummary` 시간·크기, `AssetDatabase.LoadAllAssetsAtPath`)을 더했습니다. `#if UNITY_WEBGL && !UNITY_EDITOR` 부분(.jslib 호출)은 dotnet에서 컴파일되지 않습니다.
- Unity에 의존하지 않는 코드와 EditMode 테스트 파일은 실제 Newtonsoft·NUnit으로 컴파일·실행됩니다(283개, 2026-11-23 D7·D8 뒤. 그 전 258개(미리보기 뒤). 그 전 234개(헤드셋 프로토타입). 그 전 218개, 배치 러너 CP7 반영 때 168개). `Tests/Editor/UnityOnly/`는 실제 렌더가 필요해 뺍니다.
- 헤드셋 경로(2026-11-23): 러너는 내장 XR 모듈 API만 쓰므로 `Stubs/UnityStubsXr.cs`(`XRSettings`·`XRInputSubsystem`·`SubsystemManager`·`Application.onBeforeRender`·Windows 빌드용 `BuildPipeline`)와 기존 스텁의 몇 줄(`InputDevice`의 bool·float·Vector2 값, `CommonUsages` 버튼들, `TextMesh.richText`, `Font.textureRebuilt`, `GUILayout.Toggle`, `KeyCode.R` 등)로 타입 검사합니다. XR 패키지 API를 쓰는 `Editor/XR/XrProjectSetup.cs`는 asmdef `versionDefines`(`IFS_HAS_OPENXR`·`IFS_HAS_XR_MANAGEMENT`)로 패키지가 있을 때만 컴파일되므로, compile-check에서는 빈 파일로 컴파일됩니다(그 파일의 타입 검사는 Unity에서만 — 2026-11-23 Unity 배치 실행으로 컴파일·실행 확인).
- 화면 개선(2026-11-23 G44)에서 스텁에 `Color.linear`, `TextMesh.lineSpacing`, `Mathf.Abs`·`Min(int, int)`, `Texture2D(int, int)`·`SetPixel`·`Apply()`, IMGUI의 `FontStyle`·`GUIStyleState`·`GUIStyle.fontSize/fontStyle/normal`·`GUISkin.button/toggle`·`GUI.backgroundColor`·`GUILayout.BeginArea(Rect)`·`BeginVertical`·`Space`·`FlexibleSpace`·스타일을 받는 `Button`·`Toggle`을 더했습니다. 캡처 도구 `Editor/PlacementUiCapture.cs`는 `#if UNITY_EDITOR`로 감싸 compile-check에서는 빈 파일입니다(Unity에서만 컴파일·실행 — 2026-11-23 배치·에디터 실행으로 확인).
- MonoBehaviour·Editor 스크립트는 UnityEngine/UnityEditor **스텁**(이름·시그니처만)으로 타입 검사만 합니다. 새 Unity API를 쓰면 `Stubs/UnityStubs.cs`(소유감 실험의 입력·글자·IMGUI·XR은 `Stubs/UnityStubsOwnership.cs`)에 같은 시그니처를 추가합니다. 배치 러너용으로 `Camera.ScreenPointToRay`, `Mathf.Max`, `Ray`, `Input.mousePosition`·`GetMouseButtonDown`, `KeyCode.E/F/Q`를 더했습니다.

## 한계

- **성능은 대리 측정입니다.** Quest 3에서 72 Hz를 지키는지는 기기 빌드(XR 플러그인, 단일 패스 인스턴싱)로 따로 재야 합니다. 하늘 셰이더에는 스테레오 매크로를 넣었고, 서피스 셰이더는 Unity가 스테레오 코드를 생성합니다. 기기에서 확인하지 않았습니다. `VR Quest` 단계는 소프트 섀도·High 해상도·화면 공간 그림자용 깊이 프리패스·MSAA 4×라 모바일 타일 GPU에서 비용이 클 수 있습니다. 기기에서 하드 섀도·Medium 해상도 대안과 비교해야 합니다.
- **드로콜·삼각형은 추정입니다.** UnityStats·ProfilerRecorder가 이 실행 방식에서 0이라 추정을 교차 확인하지 못했습니다. PlayMode 또는 기기(OVR Metrics)에서 실측해야 합니다.
- **정지 화면입니다.** 캡처는 에디트 모드라 `motion.type`이 이미지에 보이지 않습니다(`placement.motionNote`).
- **색 정확도 수치의 범위**: 형상 가운데 영역의 평균이라 얼룩·침식 가장자리·정반사가 섞입니다. 형상 전체의 색 분포는 아닙니다. 정면 조명(`frontal`)은 방향광이 정면에서 비춰 spec보다 밝게 나옵니다(EX01 ΔE00 6.90). 말한 색의 primary ΔE00은 무채색 EX01 1.20, 합성 유채색 4개 6.3–8.1이었습니다. 고채도·광택 높은 빨강(SYN-U4, roughness 0.1)은 무채색 환경의 정반사로 채도가 낮아 보여 7.72였습니다. 유채색 일치도가 낮다는 뜻이라, 일치도 평가에서 색 속성 결과를 해석할 때 함께 적어야 합니다.
- **소유감 실험 색 변형 크기**는 셰이더 알베도(밝기 배율 포함) 기준 ΔE00입니다. 조명·그림자·정반사·표면 얼룩·발광(밝기 0.5 초과분)은 넣지 않았고, 합성 ΔE00은 하늘 지평선 색 하나를 배경으로 가정합니다.
- **mist가 매우 옅었습니다(D7에서 고침).** 이전에는 형태 프리셋 밀도 0.5 × opacity가 중심 알파의 목표라, opacity 0.6이면 가운데 덮임 평균이 0.26이었습니다(SYN-U1). D7 뒤에는 덩어리 속 알파가 opacity 가까이 찹니다(R02 opacity 0.6에서 maxAlpha 0.598). C# 쪽 유효 불투명도 `opacity × 0.5`(소유감 러너 lowVisibility, 합성 ΔE 기록)는 숫자를 그대로 두어 이제 실제 화면 알파보다 낮게 잡힌 값입니다(`docs/validation/cloud/README.md`).
- **안쪽 면의 그림자**: 그림자 캐스터를 바깥 면 패스에만 두어서, 침식 구멍·껍질 입구 너머로 보이는 안쪽 면은 그 뒤에 있는 것(바닥 등)의 깊이로 그림자를 읽습니다. 안쪽 면은 0.3배로 어둡게 그려 눈에 띄는 차이는 작습니다. 완전히 맞추려면 Cull Off인 직접 작성 ShadowCaster 패스(정점 변위·침식 clip 포함)가 필요합니다.
- **반사**는 환경만 찍은 큐브맵 + 단순 밉맵(GGX 컨볼루션 아님)이라 거친 면의 반사가 실제와 조금 다를 수 있습니다.
- 셰이더는 **Built-in 렌더 파이프라인 전용**입니다(URP로 가면 Shader Graph 판이 필요).

## 이 폴더에서 쓰는 약속 (`shared/`)

| 필요한 것 | 어디서 |
| --- | --- |
| 오프닝·위치 질문·머물기·Feel toward·컨테인먼트 고정 문구 | `shared/protocol/elicitation_protocol.v1.json` (`fixedPhrases`, `vrStages`) 또는 `GET /api/protocol` |
| 면담 진행(챗봇 조건) | `shared/api/README.md` — `POST /api/sessions/{id}/reply` 등 |
| VR 단계 발화의 안전 검사 | `POST /api/guard/check` — `soft`면 [계속][그만], `crisis`면 즉시 중지 |
| 장면 속성 | SceneSpec v2 — `shared/schemas/scene-spec.v2.json`, 파일은 `chatbot/logs/scenes/{sessionId}.json`, 설명은 `docs/scene-spec-mapping.md` |
| 보정·거리 요약을 세션 로그에 묶기 | `POST /api/sessions/{id}/events` |

지킬 것:
- VR 단계에서는 LLM을 부르지 않습니다(고정 문구와 VR만). beFriend·Fears는 범위 밖입니다.
- 장면은 확정 텍스트에서 만든 SceneSpec만 씁니다. 생성 모델로 형태를 만들지 않습니다(사전 제작 에셋 4종 + 파라미터).
- 조건 A(조절 가능) / B(고정 제시)는 유도 조건 1·2와 다른 축입니다. 로그에는 `control: adjustable | fixed`처럼 다른 이름을 씁니다.
- 손바닥 펴기(중단), 거리 즉시 리셋, 환경 밝기 올리기, 컨테이너에 담기를 안전장치로 둡니다.
