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
│  │  │  └─ Loading/                       SceneLoader · InspectorPathSource · ISceneSpecPathSource · SpecMotion
│  │  ├─ Editor/                          메뉴: IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기
│  │  ├─ Tests/Editor/                    EditMode 테스트 8개(예시 JSON 2개 역직렬화·왕복·기록기)
│  │  └─ Scenes/SceneSpecExamples.unity   예시 2개를 나란히 띄우는 테스트 씬
│  └─ StreamingAssets/IFS/examples/       EX01.json · EX02.json (chatbot/tests/fixtures/scene_spec와 바이트까지 같음)
└─ Tools/compile-check/                   Unity 없이 C# 컴파일·테스트(dotnet). Assets 밖이라 Unity는 무시
```

UnityEngine에 의존하지 않는 부분(데이터 클래스·파싱·파라미터·기록기)과 MonoBehaviour(로더·움직임·경로)를 나눴습니다. 앞쪽은 dotnet으로 실제 컴파일·실행해 확인했습니다.

## Unity 에디터에서 할 일

1. **프로젝트 준비** — Unity Hub ▸ Projects ▸ Add ▸ *Add project from disk* ▸ 이 `unity/` 폴더. Hub는 `ProjectSettings/ProjectVersion.txt`가 있어야 프로젝트로 인식하므로 그 파일만 넣어 두었습니다(6000.0.62f1). 나머지 설정·`Packages/manifest.json`(기본 패키지)은 처음 열 때 Unity가 만듭니다. 이미 Quest 프로젝트가 있으면 `Assets/IFS/`와 `Assets/StreamingAssets/IFS/`를 그 프로젝트의 `Assets/` 아래로 복사합니다(`.meta`도 같이 — 테스트 씬이 스크립트 GUID로 연결돼 있습니다). Unity 2022.3 LTS 이상 / Unity 6 기준(C# 9)으로 썼습니다.
2. **패키지** — Package Manager ▸ `+` ▸ *Add package by name* ▸ `com.unity.nuget.newtonsoft-json`(3.2.1 이상). 테스트를 돌리려면 `com.unity.test-framework`(새 프로젝트에는 보통 있음). 로더는 XR Interaction Toolkit 없이도 컴파일됩니다.
3. **테스트** — Window ▸ General ▸ Test Runner ▸ EditMode ▸ *Run All* → 8개 통과해야 합니다.
4. **테스트 씬** — `Assets/IFS/Scenes/SceneSpecExamples.unity`를 열고 Play. 왼쪽이 EX01(회색 덩어리, 가슴 높이), 오른쪽이 EX02(웅크린 작은 형상). Console에 "SceneSpec 값이 null → 기본값 … 사용" 줄과 기록 폴더 경로가 나옵니다. 씬이 열리지 않으면 메뉴 **IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기**.
5. **프리팹 연결** — 씬의 `SceneSpec EX01`/`EX02` ▸ SceneLoader ▸ *Form Prefabs* 4칸(blob · mist · shell · fragments)에 사전 제작 에셋을 넣습니다. 비어 있으면 임시 프리미티브(구·캡슐·큐브 5개)가 뜹니다.
6. **Shader Graph** — 에셋 셰이더에 아래 Reference 이름으로 프로퍼티를 만듭니다. 이름이 다르면 SceneLoader ▸ *Shader Params*에서 바꿉니다.
7. **챗봇 출력 연결** — InspectorPathSource ▸ *Spec Path*에 `…/chatbot/logs/scenes/{sessionId}.json`의 절대 경로를 넣습니다(상대 경로는 StreamingAssets 기준).
8. **참여자 조정 입력** — 컨트롤러·슬라이더(XRI)를 `SceneLoader.SetNumber("material.brightness", v)`, `SetCategory("form.type", "mist")`, 끝날 때 `SaveFinal()`에 연결합니다. 이 연결 UI는 아직 없습니다.

## 파라미터 → Unity

| SceneSpec | Unity | null이면(기본값, Inspector에서 변경) |
| --- | --- | --- |
| `form.type` | Form Prefabs에서 고름 | `blob` |
| `form.posture` | 크기 변형 프리셋(웅크림 y×0.7, 납작 y×0.5–0.6, 곧음 y×1.2) | 변형 없음 |
| `material.color` (+`saturation`) | `_BaseColor` (Built-in은 `_Color`), 알파 = opacity | h 0, s 0, l 0.7 |
| `material.brightness` | `_Brightness` (없으면 `_EmissionColor`로 근사) | 0.5 |
| `material.roughness` | `_Roughness` (없으면 URP `_Smoothness` = 1 − r) | 0.5 |
| `material.opacity` | `_Opacity` | 1 |
| `material.erosion` | `_Erosion` | 0 |
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

## 컴파일 확인

이 저장소의 작업 환경에는 Unity 에디터가 없어 배치모드 컴파일을 하지 못했습니다. 대신 `Tools/compile-check/`에서 dotnet으로 확인합니다(netstandard2.1, C# 9, 경고도 오류로).

```bash
cd unity/Tools/compile-check && dotnet build IFS.SceneSpec.CompileCheck.csproj && dotnet test Tests/IFS.SceneSpec.CompileCheck.Tests.csproj
```

- Unity에 의존하지 않는 코드와 EditMode 테스트 파일은 실제 Newtonsoft·NUnit으로 컴파일·실행됩니다.
- MonoBehaviour·Editor 스크립트는 UnityEngine/UnityEditor **스텁**(이름·시그니처만)으로 타입 검사만 합니다. 실제 Unity API와의 차이는 Unity에서 처음 열 때 확인해야 합니다.

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
