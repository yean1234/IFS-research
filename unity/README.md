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
│  │  ├─ Runtime/Resources/IFS/          셰이더(Built-in): SceneSpec Opaque · Fade + 공통 노이즈, Environment Floor · Sky
│  │  ├─ Tests/Editor/                    EditMode 테스트(아래 「테스트」), UnityOnly/ = Unity에서만 도는 것
│  │  └─ Scenes/                          SceneSpecExamples.unity(예시 2개 테스트 씬) · OwnershipExperiment.unity(소유감 실험)
│  ├─ Prefabs/Shapes/                     모양 모형 프리팹 4개(Sphere · Cube · FlatCylinder · Cone) + 원뿔 메시 + 머티리얼(메뉴가 만듦)
│  └─ StreamingAssets/IFS/examples/       EX01.json · EX02.json (chatbot/tests/fixtures/scene_spec와 바이트까지 같음)
│     StreamingAssets/IFS/ownership_task.v0.json  소유감 실험 참여자 문구(초안, IRB 대상)
└─ Tools/compile-check/                   Unity 없이 C# 컴파일·테스트(dotnet). Assets 밖이라 Unity는 무시
```

UnityEngine에 의존하지 않는 부분(데이터 클래스·파싱·파라미터·기록기)과 MonoBehaviour(로더·움직임·경로)를 나눴습니다. 앞쪽은 dotnet으로 실제 컴파일·실행해 확인했습니다.

## Unity 에디터에서 할 일

1. **프로젝트 준비** — Unity Hub ▸ Projects ▸ Add ▸ *Add project from disk* ▸ 이 `unity/` 폴더. 에디터 버전은 6000.0.85f2(`ProjectSettings/ProjectVersion.txt`)입니다. 색공간·품질 설정은 아래 「환경과 품질 설정」을 따릅니다. 이미 Quest 프로젝트가 있으면 `Assets/IFS/`와 `Assets/StreamingAssets/IFS/`를 그 프로젝트의 `Assets/` 아래로 복사합니다(`.meta`도 같이 — 테스트 씬이 스크립트 GUID로 연결돼 있습니다). Unity 2022.3 LTS 이상 / Unity 6 기준(C# 9)으로 썼습니다.
2. **패키지** — Package Manager ▸ `+` ▸ *Add package by name* ▸ `com.unity.nuget.newtonsoft-json`(3.2.1 이상). 테스트를 돌리려면 `com.unity.test-framework`(새 프로젝트에는 보통 있음). 로더는 XR Interaction Toolkit 없이도 컴파일됩니다.
3. **테스트** — Window ▸ General ▸ Test Runner ▸ EditMode ▸ *Run All* → 134개 통과해야 합니다(2026-11-17 기준, 배치모드 명령은 아래 「테스트」).
4. **테스트 씬** — `Assets/IFS/Scenes/SceneSpecExamples.unity`를 열고 Play. 중립 환경(회색 바닥·1 m 격자·하늘·방향광 그림자)이 먼저 만들어지고, 왼쪽이 EX01(회색 덩어리, 가슴 높이), 오른쪽이 EX02(웅크린 작은 형상). Console에 "SceneSpec 값이 null → 기본값 … 사용" 줄과 기록 폴더 경로가 나옵니다. 씬이 열리지 않으면 메뉴 **IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기**.
5. **형태 모형** — 프리팹이 없어도 기본 절차 모형이 뜹니다: 잘게 나눈 구를 `IFS/SceneSpec` 셰이더가 노이즈로 밀어 형태별로 다르게 보이게 합니다(blob 울퉁불퉁한 덩어리, mist 가장자리가 흐린 반투명 안개, shell 위가 깨져 열린 껍데기, fragments 조각 5개). 디자이너가 만든 에셋이 생기면 SceneLoader ▸ *Form Prefabs* 4칸에 넣으면 그쪽이 우선입니다. 참여자가 모양어(동그랗다·네모·납작하다·뾰족하다)를 말했으면 구·큐브·납작 원기둥·원뿔 모형으로 바꿉니다(spec `_unmapped`의 모양어, `form.type`이 null·blob일 때만). 프리팹은 메뉴 **IFS ▸ Create Shape Prefabs**가 만들고 연결합니다. 규칙·기록은 `docs/shape-mapping.md`. 이 셰이더는 **Built-in 렌더 파이프라인 전용**이라 URP로 바꾸면 지원되지 않고 임시 프리미티브로 돌아갑니다(그때 Shader Graph 판이 필요).
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
| `material.roughness` | `_Roughness` (기본 셰이더: 광택↓ · 얼룩↑ · 잔요철↑, 없으면 URP `_Smoothness` = 1 − r) | 0.5 |
| `material.opacity` | `_Opacity` | 1 |
| `material.erosion` | `_Erosion` (기본 셰이더: 노이즈로 구멍을 뚫고 가장자리를 어둡게 삭은 색으로) | 0 |
| `layout.size` | 크기 배율 2^((size − 0.5) × 4) | 0.5 (×1) |
| `layout.distance` | 머리에서 수평 0.3 m + d × 2.7 m | 0.33 (≈1.2 m) |
| `layout.verticalOffset` | 바닥 + v × 키(키 = 로드 순간 눈높이 / 0.936) | 0.75 |
| `motion.type` · `motion.speed` | SpecMotion 9묶음(흔들림·떨림·맥동·떠다님·가라앉음·회전·퍼짐·다가옴·정지), 0.1–1.5 Hz | still · 0.5 |

- 기본값을 쓴 키는 콘솔과 `initialScene.json`의 `defaultsUsed`에 남습니다. 분석 때 "참여자가 말한 값"과 섞지 않기 위해서입니다.
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
- 노멀맵은 쓰지 않습니다. 절차 메시(icosphere, 삼각형 5,120개)에 UV·탄젠트가 없기 때문입니다. 잔요철은 정점 변위 + 스무드니스 얼룩으로 표현합니다.
- 반투명(Fade: mist 또는 opacity < 1)은 그림자를 끕니다. Built-in의 반투명은 그림자를 받지 못하고, 불투명 그림자를 드리우면 안개가 덩어리처럼 보이기 때문입니다. ZWrite Off · Cull Back이라 오목한 곳은 겹침 순서가 틀릴 수 있습니다(형상이 하나라 오브젝트 사이 정렬 문제는 없음).
- 로더는 에디트 모드에서도 머티리얼을 직접 복제합니다(`renderer.materials`는 에디트 모드에서 누수 오류를 냄). 배치 캡처가 이 경로를 씁니다. 조정 중 `form.type`이 바뀌면 이전 형상의 머티리얼 사본도 함께 지웁니다(`OwnedMaterialCount`로 확인, EditMode 테스트).
- 불투명 셰이더(`SceneSpecOpaque`)는 안쪽 면(Cull Front)·바깥 면(Cull Back) 두 패스로 그리고, **그림자 캐스터는 바깥 면 패스에만** 둡니다. Built-in은 첫 ShadowCaster 패스로 카메라 깊이 텍스처(화면 공간 그림자)를 그립니다. 안쪽 면 패스에도 캐스터가 있으면 그것이 먼저 쓰여 깊이 텍스처에 형상 뒤쪽 면이 들어갑니다. 그러면 바깥 면 그림자를 엉뚱한 위치에서 읽습니다. 침식 구멍 뒤로 바닥이 보이는 곳은 바닥 깊이로 읽습니다. 그래서 바닥이 있을 때와 없을 때 EX01 형상 밝기가 L\* 2 정도 달랐습니다(2026-11-16 배치 캡처 진단으로 확인, 수정 후 0).

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
7. **프레임시간**: 한 프레임 = 눈 수만큼 `Camera.Render()`(눈 위치를 IPD 64 mm의 절반씩 옮김) → RenderTexture에서 1×1 화소를 `Texture2D.ReadPixels`로 읽어 CPU가 GPU 완료를 기다리게 합니다(동기화). `Stopwatch`로 렌더 시작부터 동기화 끝까지 잽니다. 준비 프레임은 버리고 p50·p95·max·평균을 냅니다. 에디터 오버헤드와 MSAA 해상 비용이 들어 있습니다.

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

참여자 서술로 만든 원본 형상 1개와, 형태·색·크기·움직임 중 하나만 바꾼 변형본 4개를 균형 순서로 하나씩 같은 시간 보여 줍니다. 형상마다 "내 것 같다"를 7점으로 평정하고, 마지막에 5개 중 가장 자기 것인 하나를 고릅니다. 끝으로 원본과 변형본을 나란히 두고 "얼마나 다른가"를 평정합니다(조작 크기 점검, 설정으로 끔). 어느 것이 원본인지는 참여자에게 알려 주지 않습니다.

| 파일 | 하는 일 |
| --- | --- |
| `OwnershipVariantGenerator.cs` | 변형본 생성기(순수 C#). 원본 spec + 참여자 번호 + 설정 → 원본 해석값, 변형 4개, 제시 순서, 오류·플래그. 기본값·모양 해석은 `SceneParams`·`ShapeMapping`을 그대로 씁니다. 난수·LLM이 없어 입력이 같으면 결과가 바이트까지 같습니다 |
| `WilliamsDesign.cs` | 제시 순서 표(5조건 Williams 설계 10행). 행 = (번호 − 1) mod 10, 균형 비트 cb = ((번호 − 1) mod 2) XOR (⌊(번호 − 1) / 10⌋ mod 2) — 1–10번은 홀짝 그대로, 11–20번은 뒤집혀 20명이면 행 × cb 20칸이 한 번씩 찹니다. 참여자 번호는 1부터 빠짐없이 차례로 배정하고, 중단·재시행은 같은 번호로 합니다(분석기 `summary.json`의 `orderBalance`가 행별·cb별·행×cb 칸별 세션 수를 세고 어긋나면 경고) |
| `OwnershipConfig.cs` | `sizeStep` 0.25 · `colorDeltaE` 30(잠정) · `viewSeconds` 30 · `headSampleHz` 20 · `gazeConeDeg` 15 · `finalChoiceArcDeg` 120 · `finalChoiceRadiusM` 0(= 원본 거리) · `differenceRating` 켬. 값은 manifest에 남습니다 |
| `OwnershipRunner.cs` | 단계 진행, 형상 5개 로드(로더 5개, `SceneLoader.Load(path, SceneOverride)`), 평정·선택 입력, 기록 |
| `HeadPoseProvider.cs` | 머리 자세: XR Head 노드가 있으면 그것(`headSource = xr`), 없으면 데스크톱 모의(`desktop`) |
| `ParticipantTextDisplay.cs` | 참여자에게 보이는 글(월드 공간 TextMesh + OS 폰트 "Malgun Gothic" 등, 없으면 내장 폰트와 경고) |
| `OwnershipExperimenterGui.cs` | 실험자 화면(IMGUI, 데스크톱 창에만 그림. F1로 숨기기) |
| `OwnershipRecordWriter.cs` · `OwnershipManifest.cs` | 기록 파일(아래 「기록」) |
| `SceneSpec/SceneOverride.cs` | 해석값 덮어쓰기 + 모양 모형 강제. 참여자 조정이 아니라서 `RecordChange`(events.csv)를 타지 않습니다. `Load(path)`(변형 없음)는 예전과 같습니다(golden 지문 테스트) |
| `StreamingAssets/IFS/ownership_task.v0.json` | 참여자 문구 5개(초안, `status: draft`, IRB 대상). 코드에는 문구가 없습니다 |
| `Editor/OwnershipExperimentMenu.cs` | 씬 만들기 메뉴, 배치 진입점(씬·자동 시행) |

### 변형 규칙 (요약)

원본 spec 파일은 고치지 않습니다. 변형 = 해석된 값 + 덮어쓰기입니다. `_inferred`는 쓰지 않습니다.

| 속성 | 규칙 | 기록 |
| --- | --- | --- |
| 크기 | `layout.size` ± 0.25(지름 ×2 또는 ÷2). [0.25, 0.75] 안이면 cb 0 = +, 1 = −. 밖이면 들어오는 쪽(clamp 없음) | `rule` up/down, `flags.forced` |
| 색 | ΔE00은 셰이더 알베도 기준(`RenderedColor`: HSL → sRGB를 선형 공간에서 밝기 배율 `lerp(0.4, 1, saturate(2 × brightness))`로 곱한 색, 로더와 같은 함수). 유채색(s ≥ 0.10): 색상을 cb 방향으로 1°씩 돌려 ΔE00 ≥ 30인 최소 각. 180°까지 안 되면 명도(`lightness_fallback`). 무채색(기본 HSL(0, 0, 0.7) 포함): 명도를 0.005씩, 두 방향 다 되면 cb(0 밝게·1 어둡게). 둘 다 안 되면 최대 변화 + `belowTarget`. 불투명도는 목표에 넣지 않고 하늘 지평선 색 위 알파 합성 ΔE00을 따로 기록 | `magnitude.deltaE00`(알베도)·`deltaE00Composited`, from/to h·s·l |
| 움직임 | 정지이거나 보이지 않는 조합(회전 + 구·납작 원기둥·원뿔, 흔들림 + 자세 변형 없는 구)이면 `floating`(add), 아니면 `still`(remove). 속도 그대로. 기본 blob·mist·shell·fragments는 굴곡·조각이 함께 돌아 보이므로 표에 없음 | `flags.motionAltersScale`(맥동·퍼짐·다가옴·가라앉음) |
| 형태 | 모형 없는 blob → Cube(add), 구 → Cube(swap), Cube·납작 원기둥·원뿔 → 구(remove), mist·shell·fragments → blob(remove, 모양 모형 없음) | `flags.saidNotRendered`(말했지만 그려지지 않은 모양어) |

- `source`(RQ2): 바꾼 키의 값을 준 spec 슬롯에 `_provenance`가 있으면 stated, 없으면 default, 섞이면 mixed.
- 원본과 같아지는 변형, 모르는 `motion.type`·모형은 오류입니다(시작 버튼이 꺼짐). 원본 유효 불투명도(opacity × mist 밀도 0.5) < 0.15면 `lowVisibility` 경고.

### 실험자가 하는 일

1. (처음 한 번) 메뉴 **IFS ▸ Create Shape Prefabs**로 모양 프리팹이 있는지 확인합니다. 씬이 없거나 망가졌으면 **IFS ▸ Experiment ▸ Create Ownership Experiment Scene**.
2. `Assets/IFS/Scenes/OwnershipExperiment.unity`를 열고 Play. Game 창 왼쪽에 실험자 화면이 뜹니다(Game 창을 크게, 해상도 1920×1080 이상 권장).
3. **Setup**: 참여자 번호(1 이상. 1부터 빠짐없이 차례로 배정하고, 중단·재시행은 같은 번호로 합니다) → spec 폴더(비우면 에디터에서 `<저장소>/chatbot/logs/scenes`) → 목록에서 파일을 누르거나 경로를 직접 입력(`[변형 파일]` = `EX01.v1.json`처럼 `.v숫자.json` 파일) → **확인 → SpecCheck**.
4. **SpecCheck**: 슬롯별 말한 값/기본값/근거 없음과 근거 말(구분은 슬롯의 `_provenance` 유무로, 변형 `source`와 같은 함수 `OwnershipVariantGenerator.SlotSource`. 값은 있는데 근거가 없으면 "근거 없음"이고 변형 `source`에서는 default로 셉니다), `_unmapped`·`_unmatched`·`_alternatives`·`_needsConfirmation`의 개수와 원문, 변형 4개의 from → to와 플래그를 확인합니다. 빨간 오류가 있으면 시작할 수 없습니다. 참여자가 헤드셋을 쓰고 정면을 보면 **Enter**(시작 순간의 머리 자세가 형상 배치 기준이 됩니다).
5. **Intro**: 안내 문구 → 준비되면 **Space/Enter**.
6. **Viewing × 5**는 `viewSeconds`마다 자동으로 넘어갑니다. **Rating**: 참여자가 말한 숫자 **1–7** → **Space/Enter**로 확정·다음 형상. 잘못 눌렀으면 **Backspace**(취소도 기록).
7. **FinalChoice**: 5개가 호에 놓이고 위에 1–5 번호(왼쪽부터 = 제시 순서). **1–5** → **Space/Enter**.
8. **Difference × 4**: 왼쪽 원본, 오른쪽 변형본. **1–7** → **Space/Enter**.
9. **Done**: 기록 폴더 경로가 보입니다. **다음 참여자 준비**를 누르면 Setup으로 돌아갑니다.

| 키 | 동작 |
| --- | --- |
| 1–7 (숫자 줄·키패드) | 평정·선택 입력(선택은 1–5) |
| Space · Enter | 확정·다음 단계. SpecCheck에서는 시작 |
| Backspace | 확정 전 입력 취소 |
| Esc | 중단(어느 단계든, 그때까지의 자료는 남고 `summary.json`에 `abortedAt`). SpecCheck에서는 뒤로 |
| F1 | 실험자 화면 숨기기·보이기 |
| 마우스 오른쪽 드래그 · WASD | 데스크톱 모의 조작: 둘러보기 · 수평 이동(헤드셋이 없을 때) |

- 참여자 화면에는 남은 시간·원본 여부가 나오지 않습니다. 실험자 화면에는 둘 다 보입니다.

**초안 문구 경고.** 문구 파일(`ownership_task.v0.json`)의 문구 5개는 IRB 확인 전이라 모두 `status: draft`입니다(그대로 둡니다). draft 문구가 하나라도 있으면 Setup·SpecCheck 화면 맨 위에 주황 굵은 글씨로 "[초안 문구]" 줄이 뜨고, 같은 내용이 `events.csv`의 `warning`으로 남습니다. `manifest.json`의 `taskText`에는 문구 파일 버전과 draft 문구 수·키가 기록되고, 분석기는 `sessions.csv`의 `draft_phrases` 열과 `summary.json` 경고로 draft 문구로 모은 세션을 알려 줍니다. 본 실험에서는 문구를 `spec`으로 바꾼 뒤 OwnershipRunner ▸ Config ▸ *Require Spec Phrases*(`requireSpecPhrases`, 기본 꺼짐)를 켜면, draft 문구가 남아 있을 때 세션 시작을 거부하고 이유를 화면에 빨간 오류로 보여 줍니다.
- 마지막 선택·차이 평정에서 형상끼리 겹치면 반지름을 늘려 같은 거리에 다시 놓습니다(`events.csv`의 `final_layout`·`difference_layout`에 반지름 기록).
- Play를 멈추거나 앱을 닫으면 중단으로 기록합니다(`quit` 이벤트).

### 헤드셋 연결 (사람이 할 단계, 실기 미검증)

이 저장소는 XR 패키지·uGUI·TextMeshPro·Input System 없이 만들었습니다(`Packages/manifest.json`·ProjectSettings를 바꾸지 않음). 러너는 내장 XR 모듈의 `InputDevices`(Head 노드)만 읽습니다.

1. Package Manager에서 **XR Plugin Management**와 **OpenXR**(Quest Link로 PC VR) 또는 **Oculus XR Plugin**을 설치합니다. 패키지 추가는 manifest.json을 바꾸므로 팀 결정 후 커밋합니다.
2. Project Settings ▸ XR Plug-in Management ▸ PC(Standalone) 탭에서 플러그인을 켭니다. Quest를 Link로 연결하고 Play.
3. 실험자 화면 위쪽 `머리: xr`이면 헤드셋 자세를 쓰는 중입니다. `desktop`이면 헤드셋을 찾지 못한 것입니다(manifest의 `headSource`에도 남음).

**헤드셋 실기에서는 검증하지 않았습니다.** 확인한 것은 데스크톱 모의 조작 경로와 배치모드 자동 시행입니다. 기기에서 볼 것: Head 노드 자세가 카메라에 맞게 들어가는지(이중 추적 여부), IMGUI가 헤드셋 화면에 나오지 않는지, TextMesh 글의 크기·거리, 72 Hz 유지.

### 기록 (참여자 데이터 — git 밖)

`{recordRoot}/ownership/P{번호:000}/{sessionId}/{UTC yyyyMMdd-HHmmss}/`. `recordRoot`는 비우면 `persistentDataPath/IFS/sessions`(OwnershipRunner ▸ *Record Root*로 변경). UTF-8(BOM 없음), 숫자 InvariantCulture, 줄바꿈 `\n`. 분석 스크립트와의 계약이라 헤더·필드 이름을 바꾸지 않습니다(EditMode 테스트가 문자열을 고정).

| 파일 | 내용 |
| --- | --- |
| `manifest.json` | `recordVersion` ifs-ownership/0.2(분석기는 0.1도 읽음, 0.1에는 아래 0.2 값이 없어 빈칸), `generatorVersion`, `taskText`(문구 파일·버전·`draftCount`·`draftKeys`), 참여자 번호·cb·순서 행, `specFile`(파일 이름만)·`specSha256`, `headSource`, 설정, `flags.lowVisibility`, 원본 해석값·말한/기본값 키, 변형 5개(`overrides`·`shapeModel`·`from`/`to`·`rule`·`source`·`sourceByKey`·`flags`·`magnitude`), `order` |
| `headpose.csv` | `time_ms,phase,position,variant,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg` — 프레임당 최대 1개, 앞 표본에서 1/`headSampleHz` 이상 지난 프레임의 실제 시각으로 씁니다(밀린 표본을 과거 시각으로 채우지 않음. 그래서 실제 간격은 프레임 간격에 맞춰 명목보다 조금 길 수 있고, 긴 멈춤은 빈 간격으로 남음). 형상이 하나만 보이는 viewing에서만 variant·obj·거리·각이 있습니다 |
| `ratings.csv` | `position,variant,rating,rt_ms,view_ms,cancelled` — 취소한 평정은 `cancelled=1` 행으로 남고 다시 입력한 값이 새 행 |
| `difference.csv` | `variant,rating,rt_ms` |
| `events.csv` | `time_ms,event,detail` — 단계 전환, 키, 취소, 배치, 경고, 중단. 형상 제시 시작은 `viewing_start`(detail `position=N;variant=ID` 고정 형식, 분석기가 `first_look_ms`·표본 구간의 시작점으로 읽음) |
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

## 테스트

```bash
"C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe" -batchmode -projectPath <unity 폴더> \
  -runTests -testPlatform EditMode -testResults <결과.xml> -logFile <로그>
```

EditMode 161개(2026-11-17 소유감 실험 외부 리뷰 반영 뒤 배치모드로 전부 통과):

| 파일 | 개수 | 내용 |
| --- | --- | --- |
| `SceneSpecDeserializationTests.cs` | 14 | 기존: 예시 JSON 역직렬화·왕복, 미지정 슬롯·기본값 기록, 조정량, 기록기, 구 메시 |
| `CaptureMathTests.cs` | 9 | CIEDE2000(Sharma·Wu·Dalal 2005 시험 쌍 4개), sRGB → Lab 기준점, 캡처 인자, 백분위수, 색 기본값 성분(h·s·l 중 하나라도), 색 요약(말한 색과 기본값 분리) |
| `UnityOnly/EnvironmentAndCaptureTests.cs` | 5 | 선형 색공간·VR 품질 단계, 환경(방향광 1·소프트 섀도·무채색·셰이더 컴파일·정리), 환경 Dispose의 RenderSettings 복원, form.type 변경 시 머티리얼 사본 누수 없음, 배치 캡처 한 바퀴(예시 2개, 콘솔 오류 0, 불투명 scene = inContext, 요약의 stated/withDefaults) |
| `ShapeMappingTests.cs` | 33 | 원뿔 메시(정점·삼각형 수, 경계 상자, 인덱스, 바깥 감기 방향, 밑면 각진 모서리), 모양어 판정 규칙(표 4개, 표에 없는 값, charSpan 순서, conflict, form.type) |
| `UnityOnly/ShapeModelTests.cs` | 5 | 모양 모형 팩토리·프리팹 에셋(루트 크기 1, 배율은 자식, IFS 머티리얼 변위 0), SceneLoader 적용·`initialScene.json` 기록, 표에 없는 모양어·형태 우선, 조정 중 form.type 변경 |
| `OwnershipVariantTests.cs` | 74 | 소유감 실험 변형본: Williams 표 성질(각 조건이 각 위치에 2번, 순서쌍 2번씩), cb·순서 행, 1–20번 행 × cb 완전 교차, 같은 입력 → 같은 manifest 문자열, manifest 필드·specFile 이름만, 크기 방향·강제, 색(유채색은 색상만·최소 각·ΔE ≥ 목표, 무채색은 명도만, 명도 대체, belowTarget, 밝기 배율을 넣은 알베도 기준, 합성 ΔE00은 기록만), 움직임 add/remove·보이지 않는 조합(표 고정, 모양 모형 없는 형태는 보임, 자세 변형 + 흔들림은 보임)·motionAltersScale, 형태 표 4행, source·saidNotRendered, 원본과 같으면 오류, lowVisibility, `_inferred` 안 씀, SpecCheck 구분(말한 값/기본값/근거 없음)이 생성기 source와 같은 기준 |
| `OwnershipRecordTests.cs` | 10 | 기록 파일 헤더(계약 문자열 고정)·폴더 구조·UTF-8 BOM 없음·줄바꿈 LF, 같은 초 재시작, 중단 요약, 표본 시각(밀린 프레임 하나에 표본 하나, 실제 시각), `viewing_start` detail 형식, 문구 파일(초안·금지 표현), draft 문구 목록·경고·`requireSpecPhrases` 거부, 글 줄바꿈, 시선 각·호 배치 계산 |
| `UnityOnly/LoaderNoVariantGoldenTests.cs` | 1 | 변형 경로를 넣기 전 로더로 만든 지문(`Golden/loader_no_variant.golden.txt`: 적용값·notes·계층·머티리얼·기록)과 `Load(path)`가 같음 |
| `UnityOnly/OwnershipLoaderTests.cs` | 10 | `Load(path, null)`·빈 덮어쓰기도 golden과 같음, 변형본이 계획대로 그려지고 조정 기록에 남지 않음(3종), 잘못된 덮어쓰기 거부, 자동 시행 한 바퀴의 기록 폴더(draft 수·경고 포함), `requireSpecPhrases` 켜면 시작 거부, 합성 배경 = 하늘 지평선 색, 로더 `_BaseColor` = `RenderedColor.BaseSrgb`, 0.3초 밀린 프레임이 있는 자동 시행(표본 시각 중복 없음·빈 간격·형상마다 `viewing_start` ≤ 첫 표본) |

로그 확인: EditMode 로그에는 테스트 프레임워크의 스택 프레임 `UnityLogCheckDelegatingCommand:CaptureException`이 정상 실행에서도 찍힙니다(CP4 실행 36줄, 외부 리뷰 반영 실행은 로그 문구가 늘어 더 많음). 오류를 찾을 때는 `Select-String -Pattern 'error CS|Shader error|^\w*Exception:|\[Exception\]'`처럼 좁히거나 이 프레임을 빼고 셉니다(이번 실행 0건). 캡처 로그는 넓은 패턴(`Exception|error CS|Shader error`)으로도 0건입니다.

## 컴파일 확인 (dotnet)

Unity가 없는 곳(CI 등)에서는 `Tools/compile-check/`에서 dotnet으로 확인합니다(netstandard2.1, C# 9, 경고도 오류로).

```bash
cd unity/Tools/compile-check && dotnet build IFS.SceneSpec.CompileCheck.csproj && dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj
```

- Unity에 의존하지 않는 코드와 EditMode 테스트 파일은 실제 Newtonsoft·NUnit으로 컴파일·실행됩니다(140개, 2026-11-17 외부 리뷰 반영 뒤). `Tests/Editor/UnityOnly/`는 실제 렌더가 필요해 뺍니다.
- MonoBehaviour·Editor 스크립트는 UnityEngine/UnityEditor **스텁**(이름·시그니처만)으로 타입 검사만 합니다. 새 Unity API를 쓰면 `Stubs/UnityStubs.cs`(소유감 실험의 입력·글자·IMGUI·XR은 `Stubs/UnityStubsOwnership.cs`)에 같은 시그니처를 추가합니다.

## 한계

- **성능은 대리 측정입니다.** Quest 3에서 72 Hz를 지키는지는 기기 빌드(XR 플러그인, 단일 패스 인스턴싱)로 따로 재야 합니다. 하늘 셰이더에는 스테레오 매크로를 넣었고, 서피스 셰이더는 Unity가 스테레오 코드를 생성합니다. 기기에서 확인하지 않았습니다. `VR Quest` 단계는 소프트 섀도·High 해상도·화면 공간 그림자용 깊이 프리패스·MSAA 4×라 모바일 타일 GPU에서 비용이 클 수 있습니다. 기기에서 하드 섀도·Medium 해상도 대안과 비교해야 합니다.
- **드로콜·삼각형은 추정입니다.** UnityStats·ProfilerRecorder가 이 실행 방식에서 0이라 추정을 교차 확인하지 못했습니다. PlayMode 또는 기기(OVR Metrics)에서 실측해야 합니다.
- **정지 화면입니다.** 캡처는 에디트 모드라 `motion.type`이 이미지에 보이지 않습니다(`placement.motionNote`).
- **색 정확도 수치의 범위**: 형상 가운데 영역의 평균이라 얼룩·침식 가장자리·정반사가 섞입니다. 형상 전체의 색 분포는 아닙니다. 정면 조명(`frontal`)은 방향광이 정면에서 비춰 spec보다 밝게 나옵니다(EX01 ΔE00 6.90). 말한 색의 primary ΔE00은 무채색 EX01 1.20, 합성 유채색 4개 6.3–8.1이었습니다. 고채도·광택 높은 빨강(SYN-U4, roughness 0.1)은 무채색 환경의 정반사로 채도가 낮아 보여 7.72였습니다. 유채색 일치도가 낮다는 뜻이라, 일치도 평가에서 색 속성 결과를 해석할 때 함께 적어야 합니다.
- **소유감 실험 색 변형 크기**는 셰이더 알베도(밝기 배율 포함) 기준 ΔE00입니다. 조명·그림자·정반사·표면 얼룩·발광(밝기 0.5 초과분)은 넣지 않았고, 합성 ΔE00은 하늘 지평선 색 하나를 배경으로 가정합니다.
- **mist가 매우 옅습니다.** 형태 프리셋 밀도 0.5 × opacity라, opacity 0.6이면 가운데 덮임 평균이 0.26이었습니다(SYN-U1). 배경과 섞인 inContext ΔE00은 12.87입니다. 참여자가 "안 보인다"고 느낄 수 있어 프리셋 확인이 필요합니다.
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
