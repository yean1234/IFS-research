# WebGL 미리보기 시험 빌드 (D4, 결정 G12)

> **2026-11-23 재시도(WebGL 모듈 설치 뒤)**: 빌드·브라우저 표시·플레이어 대비 차이를 실제로 확인했습니다. 결과는 맨 아래 [10절](#10-2026-11-23-재시도-webgl-모듈-설치-뒤)에 있습니다. 1–9절은 처음 시도(모듈 설치 실패) 기록이라 그대로 둡니다.
>
> **2026-11-23 챗봇 연결(G12)**: 기본 형상이 들어간 소스로 다시 빌드하고, 챗봇 웹 화면의 미리보기를 WebGL로 연결했습니다(그림 방식은 예비). 이전 어댑터 문제 재현, 고친 것, 헤드리스 Chrome으로 면담 뒤 단계 전체를 눌러 본 결과, 기본 형상을 넣어 다시 잰 플레이어 대비 차이는 [11절](#11-챗봇-연결-2026-11-23-g12)에 있습니다.

2026-11-23. 챗봇 웹 화면 안에서 형상 후보를 Unity 렌더(같은 SceneLoader, 같은 셰이더)로 보여 줄 수 있는지 확인한 기록입니다. 쓴 spec은 합성 13개(`docs/validation/render/specs`)와 held-out v1 11개(`docs/validation/e2e/specs`에서 형태가 다른 것: H01·H02·H03·H05·H08·H10·H12·H16·H18·H20·H28)입니다. 코퍼스 원문은 열지 않았습니다.

## 요약

| 항목 | 결과 |
| --- | --- |
| WebGL 모듈 설치 | **실패(2회)**. 내려받기는 끝났지만 관리자 권한 확인(UAC)에 응답이 없어 Windows 오류 1223으로 취소됨 |
| WebGL 빌드 | **못 함**(모듈 없음). 빌드 스크립트는 모듈 확인에서 멈추고 보고서를 남김(종료 코드 2) |
| 셰이더 WebGL2 컴파일 | **확인 못 함**(빌드가 없어서). 소스 점검 결과만 아래에 적음 |
| WebGL ↔ 데스크톱 차이 | **측정 못 함** |
| 헤드리스 Chrome의 WebGL2 | 됨. 별도 플래그 없이 하드웨어 렌더(ANGLE D3D11, RTX 5080, MAX_SAMPLES 8) |
| 대안 경로(Windows 플레이어 상주) ↔ 에디터 | 24개 모두 덮인 화소 수 같음, 평균 색 ΔE00 평균 0.020·최대 0.045, 화소 최대 채널 차 2/255 |
| 대안 경로 지연 | 상주 플레이어 spec 1개(800×600 한 장) 왕복 중앙값 15.2 ms(최대 20.2 ms). 매번 Unity를 띄우면 7.1–9.1 s |
| **G12 판정 제안** | **대안으로 간다**(Unity Windows 플레이어를 상주시키고 캡처 이미지를 웹에 표시). WebGL 코드는 준비해 두고, 모듈을 설치하면 아래 재현 명령으로 다시 판정 |

## 1. 모듈 설치

| 시도 | 명령 | 결과 |
| --- | --- | --- |
| 1 | `"C:\Program Files\Unity Hub\Unity Hub.exe" -- --headless install-modules --version 6000.0.85f2 -m webgl` | 내려받기 완료(필요 공간 886 MB) → 설치 단계에서 관리자 권한 프로세스 요청 → 약 2분 뒤 `Error: 1223`(사용자가 작업을 취소함) → `Validation Failed` |
| 2 | 같은 명령 | 같은 오류 1223 |

- Hub 로그(`%APPDATA%\UnityHub\logs\info-log.json`)의 원인 줄: `spawn child process, elevated: true` → `Error: 1223`. 설치 위치가 `C:\Program Files\Unity\Hub\Editor\…`라 관리자 권한이 필요하고, 자동 실행에서는 UAC 창을 누를 사람이 없었습니다. 그 폴더는 현재 사용자 권한으로 쓸 수 없습니다(쓰기 시험에서 거부).
- 실행 중인 Unity 프로세스는 없었습니다.
- **사람이 할 일**: Unity Hub ▸ Installs ▸ 6000.0.85f2 ▸ ⚙ ▸ Add modules ▸ **Web Build Support** 체크 ▸ Install. UAC 창에서 "예". 또는 관리자 PowerShell에서 위 명령. 설치 뒤 `C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Data\PlaybackEngines\WebGLSupport`가 생기면 됩니다.

## 2. 만든 것

| 파일 | 하는 일 |
| --- | --- |
| `unity/Assets/IFS/Runtime/Loading/SceneLoader.cs` | `LoadJson(json, 이름, 덮어쓰기)` 추가. 파일 로드(`Load(path)`)와 같은 내부 경로(`LoadParsed`: 파싱 → 형식 검사 → 덮어쓰기 확인 → 해석 → 렌더 → 기록)를 탑니다. WebGL 플레이어에서 `Load(path)`를 부르면 `LoadJson`을 쓰라는 오류를 내고 false. 재생 중 `Destroy` 전에 오브젝트를 숨기도록 고침(아래 4절) |
| `Runtime/SceneSpec/SceneOverrideJson.cs` | 덮어쓰기 목록 JSON → `SceneOverride`. 형식은 소유감 실험 manifest의 `overrides`(평평한 객체)에 `shapeModel` 키 하나를 더한 것. 숫자 = 수치 키, 문자열 = 범주 키. 모르는 키·0–1 밖·null은 오류 목록으로 거부 |
| `Runtime/Preview/PreviewStage.cs` | 미리보기 무대: 중립 환경 + 고정 카메라(눈높이 1.6 m, 세로 시야 60°, 형상 경계 중심을 봄 — BatchCapture와 같은 규칙) + 기록을 끈 SceneLoader. 품질 단계 `VR PC`(MSAA 4×). 배경 scene/black/white로 렌더 텍스처에 찍기. **WebGL·Windows 플레이어·에디터가 모두 이 코드를 씀** |
| `Runtime/Preview/PreviewBridge.cs` | GameObject `IFS Preview`. JS 진입점 `LoadSpecJson`, `ApplyOverridesJson`, `SetAutoRotate`, `SetFrozen`, `Capture`. 마우스 왼쪽 드래그 = 세로축 회전. 알림 `ready`·`loaded`·`error`·`capture`(.jslib) |
| `Runtime/Preview/Plugins/WebGL/IFSPreview.jslib` | Unity → 페이지 알림(`window.ifsPreviewOnMessage`, `ifs-preview` 이벤트) |
| `Runtime/Preview/PreviewQueue.cs` | 대안 경로: 데스크톱 플레이어를 `-ifsPreviewQueue <폴더>`로 띄우면 폴더의 요청 JSON마다 PNG를 씀(WebGL 빌드에는 없음) |
| `Assets/WebGLTemplates/IFSPreview/index.html` | 외부 CDN·글꼴 없는 최소 페이지. `window.ifsPreview.load(spec)`·`applyOverrides(obj)`·`capture({…})`·`setAutoRotate(°/s)`·`setFrozen(bool)`(모두 Promise). `?spec=<같은 출처 경로>`, `?rotate=<°/s>` |
| `Assets/IFS/Scenes/Preview.unity` | 미리보기 씬(`IFS Preview` 하나, 모양 프리팹 연결). 메뉴 **IFS ▸ Preview ▸ 미리보기 씬 다시 만들기** |
| `Editor/PreviewSceneMenu.cs` · `PreviewBuild.cs` · `PreviewCapture.cs` | 씬 만들기, WebGL·Windows 미리보기 빌드, 에디터 배치 캡처 |
| `docs/validation/webgl/tools/` | `compare.py`(spec별 비교), `queue_client.py`(상주 플레이어 지연 측정), `serve.py`·`driver.html`(WebGL 비교 하네스, **미실행**) |
| `docs/validation/webgl/results/` | 이번 실행의 수치(JSON·표). PNG는 넣지 않음 |

JS에서 부르는 법(챗봇 화면 연결은 D5):

```js
await ifsPreview.ready;
const r = await ifsPreview.load(specJsonText);                         // r.renderPath, r.params, r.defaultsUsed, r.notes, r.loadMs
await ifsPreview.applyOverrides({ "form.type": "mist", "material.opacity": 0.6 });   // 빈 객체 = 원래 spec
ifsPreview.setAutoRotate(12);                                          // °/초, 0 = 멈춤
```

## 3. WebGL 빌드 설정(준비만 함)

`PreviewBuild.BuildWebGLPreview`가 빌드하는 동안만 바꾸고 끝나면 되돌리는 값입니다. ProjectSettings 파일에는 남기지 않습니다.

| 설정 | 빌드 중 값 | 이유 |
| --- | --- | --- |
| 압축 | 끔(`Disabled`) | 챗봇 서버·`http.server`가 `Content-Encoding` 헤더 없이 그대로 내보낼 수 있게. 압축 해제 대체도 끔(압축이 없으므로) |
| 템플릿 | `PROJECT:IFSPreview` | 외부 자원 없는 페이지 + `window.ifsPreview` |
| 데이터 캐싱 | 끔 | 브라우저 IndexedDB에 남기지 않고, 로드 시간을 매번 같은 조건으로 재기 위해 |
| 씬 | `Preview.unity` 하나 | `EditorBuildSettings`의 씬 목록은 바꾸지 않음 |
| 색 공간 | 프로젝트 값(Linear) 그대로 | WebGL2 필요 |
| XR | 바꾸지 않음 | XR 설정 자산에 WebGL 항목이 없음(Standalone만 OpenXR) → WebGL에는 XR 로더가 없음 |
| 빌드 대상 | 끝나면 Standalone(Win64)으로 되돌림 | |

이번 실행: `-buildTarget WebGL`로 띄웠지만 모듈이 없어 활성 대상은 Standalone 그대로였고, 스크립트는 모듈 확인(`BuildPipeline.IsBuildTargetSupported`)에서 멈췄습니다(약 10 s, 종료 코드 2, `results/webgl-build-report.json`). 패키지(OpenXR·glTFast·Burst·Input System)가 WebGL 빌드를 막는지는 확인하지 못했습니다.

### 셰이더(소스 점검만, 컴파일 확인 아님)

- `SceneSpecMist.shader`: `#pragma target 3.0`, 레이마칭은 상수 8걸음 `[unroll]` 고정 루프, 텍스처 없는 해시 노이즈(`frac` 기반, `sin` 없음), `discard`, 동적 인덱싱 없음. GLSL ES 3.00(WebGL2)에서 막힐 요소는 보이지 않습니다. 실제 컴파일 결과는 WebGL 빌드 로그로 확인해야 합니다.
- Opaque·Fade는 서피스 셰이더(`target 3.0`)라 Unity가 GLES3 코드를 생성합니다. 환경 셰이더 2개는 정점·프래그먼트 셰이더(스테레오 매크로 포함)입니다.
- 미리보기 로드 알림(`loaded`)의 `renderPath`가 `mist`이면 안개 셰이더를 썼고, `mist(legacy)`이면 셰이더를 못 써서 대체 경로로 간 것입니다. WebGL 판정 때 이 값을 같이 봅니다.

## 4. 데스크톱 기준과 대안 경로 비교

WebGL 화면을 못 만들었으므로, 비교 기준(에디터 캡처)과 대안 경로(Windows 플레이어)만 측정했습니다. 셋 모두 `PreviewStage`의 같은 코드로 찍습니다.

- 기준: 에디터 배치 `PreviewCapture`(Direct3D 11, `VR PC`, MSAA 4×, Linear, 800×600, 세로 시야 60°). spec마다 scene·black·white 세 장.
- 대상: Windows 미리보기 플레이어(`IFSPreview.exe -batchmode -ifsPreviewQueue`). 같은 세 장.
- 지표(`tools/compare.py`): 덮임 a = 1 − (W − B)의 선형 채널 평균(BatchCapture와 같은 식), 덮인 화소 = a ≥ 0.02. 평균 색 ΔE00 = 덮인 화소(합집합)의 장면 렌더 평균 색끼리 CIEDE2000. 구현은 Sharma 외(2005) 시험 쌍 2개로 확인(2.0425, 1.0000).

| 지표(24 spec) | 평균 | 최대 |
| --- | --- | --- |
| 덮인 화소 수 차(비율) | 0 | 0 |
| 평균 색 ΔE00 | 0.020 | 0.045 |
| 화소 ΔE00 평균(덮인 곳) | 0.082 | 0.286 |
| 화소 ΔE00 평균(화면 전체) | 0.019 | 0.030 |
| RGB 평균 절대 차(0–255) | 0.010 | 0.016 |
| 화소 최대 채널 차(0–255) | 1.6 | 2 |

spec별 표는 `results/cmp_editor_vs_player.md`, 원자료는 `results/cmp_editor_vs_player.json`입니다.

측정하다가 고친 결함 두 가지(둘 다 이전 결과에는 영향 없음):

1. **만들지 않은 임시 렌더 텍스처.** `RenderTexture.GetTemporary`로 받은 텍스처를 `Create()` 없이 MSAA 해상에 쓰면 첫 읽기가 실제 렌더와 달랐습니다(160×120 전 화소, 채널 차 최대 196). 두 텍스처를 `Create()`한 뒤 0. EditMode 테스트가 "검은 배경 렌더의 모서리는 검정"으로 고정합니다.
2. **재생 중 지연 삭제.** 재생 중 `Destroy`는 프레임 끝까지 미뤄져서, 같은 프레임에 다음 spec을 로드하고 찍으면 이전 형상이 함께 찍혔습니다. 고치기 전 플레이어 대 에디터는 평균 색 ΔE00 평균 7.25·최대 38.2, 덮인 화소 차 최대 +162%였습니다. `SceneLoader`가 `Destroy` 전에 `SetActive(false)`를 하도록 고친 뒤 위 표의 값이 됐습니다. 소유감·배치 러너의 재생 경로에서도 형상이 바뀌는 프레임에 겹쳐 그려지지 않게 됩니다(EditMode 307개 통과).

### WebGL에서 예상되는 차이(측정 전, 확인 필요)

| 항목 | 예상 | 확인 방법 |
| --- | --- | --- |
| 감마·색 공간 | Linear는 WebGL2의 sRGB 프레임버퍼로 처리되므로 원리상 같음 | 비교 표의 평균 색 ΔE00 |
| MSAA | `Capture`(렌더 텍스처, 4×)는 같은 조건. 화면 표시는 WebGL 컨텍스트를 만들 때 AA가 정해지고, WebGL 기본 품질 단계(`High`)의 AA는 0이라 화면에는 계단이 보일 수 있음 | 캔버스 캡처를 따로 봄 |
| 그림자 | 소프트 섀도는 WebGL2에서 지원되지만 그림자 맵 깊이 형식·정밀도가 다를 수 있음 | 바닥 그림자 화소 차 |
| 정밀도 | `fixed`·`half`는 GLES에서 mediump. 안개 누적(`fixed4` 반환)과 해시 노이즈 좌표에서 작은 차이 가능 | mist spec의 화소 ΔE00 |
| 반사 | `RenderToCubemap` 1회 — WebGL2에서 지원 | 광택 높은 spec(R08 등) |

## 5. 로드 시간과 지연

| 경로 | 측정 | 값 |
| --- | --- | --- |
| WebGL | 페이지 → Unity 준비, spec 로드 | 측정 못 함 |
| 에디터 상주(한 프로세스, 24 spec) | 무대 만들기 / spec 로드 중앙값(첫 spec) / scene 한 장 렌더+PNG 중앙값 | 39.2 ms / 1.51 ms(83.5 ms) / 13.3 ms |
| Windows 플레이어 상주 | 시작 → 요청 받을 준비 | 2.91 s(빌드 직후 첫 실행), 0.64 s(다음 실행) |
| Windows 플레이어 상주 | scene 한 장 요청 → 응답 파일(n = 24) | 중앙값 15.2 ms, 평균 15.9, 최소 14.9, 최대 20.2 |
| Windows 플레이어 상주 | 세 장(scene·black·white) 요청 | 중앙값 37.4 ms, 첫 요청 141 ms(로드 75 ms: 셰이더·메시 준비) |
| Unity를 매번 띄움(BatchCapture, spec 1개, 기본 인자) | 프로세스 시작 → 종료 | 8.11 s, 9.08 s |
| 같음(BatchCapture 800×600·1프레임) | | 7.05 s, 7.07 s |
| 같음(PreviewCapture scene 한 장) | | 7.06 s, 8.09 s |

- 지연은 이 PC(RTX 5080, 로컬 SSD)에서 잰 값입니다. 요청·응답은 파일로 주고받았고(폴더를 2 ms마다 확인), 플레이어는 `-batchmode`라 창이 없습니다.
- Windows 미리보기 플레이어 크기 94.9 MB(빌드 보고값 94,934,979 B), 빌드 10.8 s(처음)·4.9 s(다시). 빌드 동안만 Standalone의 "시작 때 XR 초기화"를 끄고 끝나면 되돌립니다(`XRGeneralSettingsPerBuildTarget.asset`은 바뀌지 않음). 그래도 플레이어 시작 때 OpenXR 네이티브 플러그인이 런타임을 한 번 확인하며 `XR_ERROR_FORM_FACTOR_UNAVAILABLE`(헤드셋 없음)을 로그에 남깁니다. 화면·캡처에는 영향이 없었습니다.

## 6. 헤드리스 브라우저

- Chrome 157 `--headless=new`(GPU 플래그 없음, 별도 프로필)에서 WebGL2 컨텍스트가 하드웨어로 만들어집니다: `ANGLE (NVIDIA, NVIDIA GeForce RTX 5080 … Direct3D11)`, `MAX_SAMPLES` 8(`results/headless-chrome-webgl2.json`). Unity 빌드가 아닌 64×64 캔버스 시험입니다.
- 그래서 빌드가 생기면 `serve.py` + `driver.html`을 헤드리스로 돌려 비교할 수 있습니다. 드라이버는 Unity 안에서 렌더 텍스처로 찍은 PNG(에디터와 같은 코드)를 받으므로 브라우저 합성·DPI의 영향을 받지 않습니다. 화면에 실제로 보이는 모습은 캔버스 스크린샷을 따로 봐야 합니다.
- `serve.py`는 가짜 빌드 폴더로 GET(`.wasm` = `application/wasm`)·`/harness/specs.json`·POST `/save`·`/done`만 시험했습니다. `driver.html`은 실행하지 않았습니다.

## 7. G12 판정 제안

**제안: 대안으로 간다.** 후보·조절 화면(D5)은 Unity Windows 플레이어를 챗봇 서버 옆에 상주시키고, 요청마다 받은 PNG를 웹 화면에 표시합니다. WebGL 코드(브리지·템플릿·빌드 스크립트)는 그대로 두고, 모듈을 설치하면 8절 순서로 비교한 뒤 다시 판정합니다.

근거:

1. **지금 WebGL은 판정할 수 없습니다.** 모듈 설치에 관리자 확인이 필요해 두 번 모두 실패했고, 빌드·셰이더·화면 차이 중 어느 것도 확인하지 못했습니다. 12/2 일정 안에서 확인되지 않은 경로에 D5를 묶는 위험이 큽니다.
2. **G12의 이유(렌더러가 하나여야 같다고 보장)를 대안이 더 직접 지킵니다.** 대안은 헤드셋 앱과 같은 Windows Direct3D 11 경로이고, 에디터 기준과 24개 모두 덮인 화소가 같고 평균 색 ΔE00 최대 0.045였습니다. WebGL은 같은 C#·셰이더 소스라도 GLES3(ANGLE) 백엔드로 다시 컴파일되므로 차이를 따로 재야 합니다.
3. **지연이 충분히 작습니다.** 상주 플레이어는 spec 1개를 15–20 ms에 그립니다. 후보 4개(⚠ 임시값)면 0.1초 안팎입니다. 매번 Unity를 띄우는 방식(7–9 s)은 쓸 수 없습니다.
4. **로컬 원칙(AGENTS.md 5)과 맞습니다.** 외부 전송·CDN이 없고, 챗봇 서버가 PNG만 내보냅니다.

대안의 한계(사람이 판단할 것):

- 웹 화면에서 끌어 돌리기·`motion.type` 움직임을 보여 주려면 각도별·시간별 이미지를 여러 장 받아야 합니다(장당 약 15 ms). 연속 회전·움직임은 WebGL이 낫습니다.
- 챗봇 서버 PC에 Windows와 GPU가 필요하고, 플레이어 프로세스를 관리(시작·재시작·종료)해야 합니다. 요청 통로는 지금 파일 폴더입니다. D5에서 로컬 HTTP(127.0.0.1)로 바꿀지 정합니다.
- 미리보기 시야각(60°)은 헤드셋(96°)과 다르므로 형상이 VR보다 크게 보입니다. 미리보기용 값을 따로 정할지 사람이 정해야 합니다.

## 8. 재현 명령

```bash
U="C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"; P=<repo>/unity
# 씬(이미 저장소에 있음)
"$U" -batchmode -projectPath $P -executeMethod IFS.SceneSpec.EditorTools.PreviewSceneMenu.CreatePreviewSceneBatch -quit -logFile <로그>
# 에디터 기준 캡처(spec마다 scene·black·white, capture.json에 시간)
"$U" -batchmode -projectPath $P -executeMethod IFS.SceneSpec.EditorTools.PreviewCapture.Run \
  -specDir <repo>/docs/validation/render/specs -specDir <held-out 고른 폴더> -outDir <에디터 결과> -width 800 -height 600 -logFile <로그>
# 대안: Windows 미리보기 플레이어 빌드 → 상주 실행·지연 측정 → 비교
"$U" -batchmode -projectPath $P -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWindowsPreview -logFile <로그>   # → <repo>/../webgl-build/preview-win/
python -I docs/validation/webgl/tools/queue_client.py <repo>/../webgl-build/preview-win/IFSPreview.exe <요청 폴더> <플레이어 결과> <spec.json …>
python -I docs/validation/webgl/tools/compare.py <에디터 결과> <플레이어 결과> <결과.json> --label-a editor --label-b player
# WebGL(모듈 설치 뒤): 빌드 → 로컬 서버 → 헤드리스 Chrome → 비교
"$U" -batchmode -buildTarget WebGL -projectPath $P -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWebGLPreview -logFile <로그>   # → <repo>/../webgl-build/preview/
python -I docs/validation/webgl/tools/serve.py <repo>/../webgl-build/preview <WebGL 결과> <spec.json …> --port 8765
"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --user-data-dir=<임시 프로필> --window-size=1000,800 http://127.0.0.1:8765/harness/driver.html
python -I docs/validation/webgl/tools/compare.py <에디터 결과> <WebGL 결과> <결과.json> --label-a editor --label-b webgl
```

- 빌드 산출물은 저장소 밖(`<repo>/../webgl-build/`)에 둡니다. git에 넣지 않습니다.
- 헤드리스 Chrome은 서버가 `/done`을 받으면 서버만 끝납니다. Chrome은 띄운 프로세스(같은 `--user-data-dir`)만 골라서 닫습니다.
- WebGL 빌드 뒤에는 `results/webgl-build-report.json`의 `files`(크기), `wallSeconds`, 빌드 로그의 셰이더 오류, `driver.json`의 `instanceMs`·`loadMs`·`errors`·`webgl.renderer`를 이 문서에 채웁니다.

## 9. 하지 않은 것·확인하지 못한 것

- WebGL 모듈 설치, WebGL 빌드, 셰이더의 WebGL2 컴파일, 브라우저 안 로드 시간, WebGL ↔ 데스크톱 차이 표. 모두 모듈이 없어서입니다.
- OpenXR·glTFast·Burst·Input System 패키지가 WebGL 빌드를 막는지.
- 캔버스 화면(브라우저 합성) 스크린샷 비교.
- 챗봇 웹 화면 연결(D5). `chatbot/`은 건드리지 않았습니다.

## 10. 2026-11-23 재시도 (WebGL 모듈 설치 뒤)

사람이 Unity Hub에서 Web Build Support를 설치한 뒤 다시 했습니다. 같은 저장소에서 다른 작업이 Unity를 열 수 있어서 **저장소의 `unity/`는 열지 않고** 저장소 밖 복사본에서 빌드했습니다. `robocopy`로 `unity/`를 `<repo 밖>/webgl-build/proj`에 복사하면서 `Library`·`Temp`·`Logs`·`obj`·`UserSettings`는 빼고 Library를 새로 만들었습니다. 빌드 산출물과 캡처는 모두 `<repo 밖>/webgl-build/` 아래에 있고 git에 넣지 않았습니다. spec은 1–9절과 같은 24개(합성 13 + held-out v1 11)에 덮어쓰기 사례 6개(`tools/override_cases.json`)를 더했습니다.

### 10.1 요약

| 항목 | 결과 |
| --- | --- |
| WebGL 빌드 | **성공**. 빌드 보고 기준 오류 0, 경고 0. 첫 빌드 104.5 s(Library를 새로 만든 시간까지 합친 Unity 프로세스 142 s), 고친 뒤 다시 빌드 72.6 s(프로세스 84 s) |
| 크기(최종 빌드, 압축 끔) | 47.51 MB(`.wasm` 36.80, `.data` 10.24, `framework.js` 0.44, 로더와 `index.html` 0.02). 같은 파일을 여기서 압축해 보면 gzip-9 12.90 MB, brotli-11 9.17 MB(빌드 자체는 압축하지 않음) |
| 패키지 | OpenXR 1.16.1·Input System 1.20.0·glTFast 6.21.0·Burst 1.8.30 모두 WebGL로 컴파일돼 들어갔고 오류·경고 없음. WebGL용 XR 로더 없음 |
| 색 공간·API | Linear, WebGL 2.0(OpenGL ES 3.0 Chromium), GLSL ES 3.00 |
| mist 셰이더 | 빌드 로그상 `IFS/SceneSpec Mist` gles3 변형 1개 컴파일(1.34 s), 오류 없음. 브라우저에서 `renderPath`가 `mist`(대체 경로 `mist(legacy)`가 아님)였고 덩어리 구름이 캔버스에 보임 |
| 브라우저 표시 | 헤드리스 Chrome 157(하드웨어 ANGLE D3D11, RTX 5080)에서 blob·mist·fragments·shell과 모양 모형 4종이 모두 보이고, 덮어쓰기를 넣으면 형상이 바뀜. 페이지를 연 뒤 Unity 준비까지 0.66–0.74 s(3회) |
| 첫 빌드에서 고친 것 | ① WebGL에서 `Capture`가 전부 RGBA 0을 돌려줌 → `PreviewStage`의 MSAA 해상을 WebGL에서만 `Graphics.Blit`으로 바꿈. ② "Made with Unity" 시작 화면이 준비 뒤 몇 초 동안 캔버스를 가림 → 빌드 스크립트가 빌드 동안만 끔 |
| WebGL ↔ Windows 플레이어(24 spec) | 덮인 화소 수 차 최대 0.03%(3화소). 평균 색 ΔE00 평균 0.126, 최대 1.36(H08.v1, 덮인 화소 112개짜리 작은 조각). H08을 빼면 최대 0.28. 8/255 넘게 다른 화소 1306개 중 1305개가 윤곽선 위 |
| 캔버스 화면 ↔ Unity 안 캡처 | 확인한 5개 spec 모두 **화소 단위로 같음**(800×600, 배율 1). 화면에도 MSAA 4× 결과가 그대로 나옴 |
| 소프트웨어 렌더(SwiftShader) | 뜸. 하드웨어 화면과 윤곽선에서 최대 채널 차 13–107/255 |

### 10.2 빌드

명령은 8절과 같습니다. 다만 `-projectPath`로 복사본을 주고, `-outDir <repo 밖>/webgl-build/preview -reportPath <repo 밖>/webgl-build/preview-build-report.json`을 붙였습니다.

- 최종 빌드 보고는 `results/retry_webgl-build-report.json`입니다. `Succeeded`, `errors` 0, `warnings` 0이고, 임시 설정(압축 끔, 템플릿, 캐싱 끔, 시작 화면 끔)은 빌드가 끝난 뒤 되돌아갔습니다. 활성 빌드 대상도 StandaloneWindows64로 돌아왔습니다. 복사본의 `ProjectSettings.asset`에 `m_ShowUnitySplashScreen: 1`이 그대로 남아 있는 것을 확인했습니다.
- 빌드 로그에서 오류처럼 보이는 줄은 Unity 라이선스 클라이언트 연결(`[Licensing::Client] Error: HandshakeResponse …`), 종료 때의 `Curl error 42`와 `[usbmuxd] Error`뿐입니다. 빌드 결과에는 영향이 없었고 `error CS`는 한 줄도 없었습니다.
- gles3로 컴파일된 셰이더는 `IFS/SceneSpec Mist`(1 변형), `IFS/SceneSpec Opaque`, `IFS/SceneSpec Fade`, `IFS/Environment Floor`, `IFS/Environment Sky`, `Skybox/Procedural`, `Legacy Shaders/Transparent/*`입니다. 오류는 없었습니다.
- 시작 화면을 꺼도 빌드 자산 목록에는 시작 화면 로고 텍스처(2.7 MB)가 들어 있습니다. `StreamingAssets/IFS/`의 예시·과제 JSON(43 KB)도 들어갑니다. 미리보기에는 쓰이지 않지만 해가 없어 그대로 두었습니다.
- 성능 테스트 패키지(`com.unity.test-framework.performance`)의 빌드 전처리가 `Assets/Resources/PerformanceTestRunInfo.json`과 `PerformanceTestRunSettings.json`을 만들어 빌드에 넣습니다(이번에는 복사본에 생김). 저장소에서 빌드하면 같은 파일이 생기니 커밋하지 않도록 주의해야 합니다.
- 프로젝트 설정은 복사본에서도 손대지 않았습니다. 바뀐 것은 빌드 스크립트의 임시 변경뿐입니다.
- 비교용 Windows 미리보기 플레이어도 **같은 복사본**에서 다시 빌드했습니다(`<repo 밖>/webgl-build/preview-win-cp`, 23.8 s, 94.96 MB, `results/retry_windows-build-report.json`). 기존 `preview-win`은 건드리지 않았습니다.

### 10.3 첫 빌드에서 드러난 결함 두 가지와 고친 것

1. **WebGL에서 `Capture`가 빈 그림을 돌려줌.** 첫 빌드에서는 30개(24 spec + 덮어쓰기 6) × 3장이 모두 RGBA (0,0,0,0)이었습니다. 검정·흰 배경 캡처까지 0이었으니 렌더 텍스처에서 읽은 값 자체가 비어 있었던 것입니다. `PreviewStage.Render`는 MSAA 4× 렌더 텍스처를 `ResolveAntiAliasedSurface`로 해상하는데, WebGL2에서는 이 호출이 대상에 아무것도 쓰지 않았습니다. 그래서 `#if UNITY_WEBGL && !UNITY_EDITOR`일 때만 `Graphics.Blit(rt, resolved)`로 해상하게 고쳤고, 다시 빌드하자 10.5의 값이 나왔습니다. 데스크톱·에디터에서 컴파일되는 코드는 바뀌지 않았습니다. 이 WebGL 분기는 EditMode 테스트가 검사하지 못하므로 빌드할 때마다 `driver.html`로 확인해야 합니다.
2. **시작 화면이 캔버스를 가림.** 프로젝트 설정에서 "Made with Unity" 시작 화면이 켜져 있어서, 준비 알림 직후 1–2초 안에 찍은 화면이 모두 로고였습니다. `PreviewBuild.BuildWebGL`이 빌드하는 동안만 `PlayerSettings.SplashScreen.show = false`로 두고 끝나면 되돌리게 했습니다(Unity 6은 Personal에서도 끌 수 있음). Build Settings 창 같은 다른 경로로 빌드하면 시작 화면이 다시 나옵니다.

### 10.4 브라우저 표시(헤드리스 Chrome)

로컬 서버(`tools/serve.py`, 127.0.0.1)로 빌드를 내보내고 Chrome 157 `--headless=new`로 열었습니다. GPU 관련 플래그는 주지 않았고, 실행할 때마다 새 임시 프로필을 썼습니다. 외부로 나가는 요청은 없습니다.

- WebGL 컨텍스트는 `WebGL 2.0 (OpenGL ES 3.0 Chromium)`, `ANGLE (NVIDIA, NVIDIA GeForce RTX 5080 … Direct3D11)`, `MAX_SAMPLES` 8이었습니다. 컨텍스트의 `antialias`는 false입니다. 그래도 Unity가 자기 MSAA 버퍼에 그린 뒤 캔버스로 옮기기 때문에 화면에도 MSAA가 적용됩니다. 캔버스 스크린샷(`tools/cdp_shot.py`, DevTools `Page.captureScreenshot`)과 Unity 안 렌더 텍스처 캡처를 비교했더니 R01·R04·R07·R11·OV_R07_to_shell이 화소 단위로 같았습니다. 4절에서 "화면에는 계단이 보일 수 있음"이라고 했던 예상은 이 환경에서는 맞지 않았습니다.
- **첫 로딩**(127.0.0.1, 압축 없음, 데이터 캐싱 끔, 새 프로필): 페이지를 연 뒤 `ifsPreview.ready`까지 0.705·0.657·0.737 s였습니다. `driver.html` 안의 iframe으로 열면 `instanceMs`가 1.80 s였고, 챗봇 서버와 같은 Starlette `StaticFiles(html=True)` 마운트로 내보내면 0.707 s였습니다.
- **spec 로드**(JS → Unity → JS 왕복, 24개): 중앙값 1.5 ms, 최대 33.5 ms(첫 spec). **덮어쓰기 적용** 왕복(8회): 중앙값 0.7 ms, 최대 2.3 ms. **800×600 한 장 렌더**: 중앙값 12.4 ms. 다만 셰이더를 처음 쓰는 렌더에서는 브라우저가 셰이더를 컴파일하느라 0.2–0.8 s가 걸렸습니다(최종 빌드에서 첫 mist 0.80 s, 첫 fragments 0.47 s). 원자료는 `results/retry_webgl_driver.json`입니다.
- **형상별 표시**: blob, mist(덩어리 구름), fragments, shell, 모양 모형(Sphere·Cube·FlatCylinder·Cone)이 모두 오류 없이 로드되고 캔버스에 나타났습니다. 그림은 `results/retry_player_vs_canvas.png`입니다. 위 줄이 Windows 플레이어 PNG, 아래 줄이 WebGL 캔버스이고, 왼쪽부터 R01 mist, R04 fragments, R06 shell, R07 blob입니다(가운데 400×300을 잘라 절반 크기로 줄임).
- **덮어쓰기**(`applyOverrides`): R07 blob → mist·fragments·shell, R01 mist → blob, mist + 불투명도 0.6 + 색상 0.3에서 모두 `renderPath`와 `form.type`이 덮어쓴 값으로 바뀌었습니다. shell → mist → `{}`를 차례로 넣으면 R07을 처음 로드했을 때와 세 장 모두 화소 단위로 같았습니다. 이전 형상이 남지 않는다는 뜻입니다. R07 → shell도 R06 shell과 화소 단위로 같았습니다. 모르는 값(`{"form.type":"cube"}`)을 넣으면 Promise가 거부되고 `모르는 형태: cube`가 돌아왔습니다. 그림은 `results/retry_overrides_player_vs_canvas.png`이고, 왼쪽부터 R07 그대로, → mist, → fragments, → shell입니다.
- **천천히 돌기**: `setFrozen(false)` + `setAutoRotate(90)` 뒤 1 s와 1.7 s에 찍은 화면이 서로 달랐습니다(8/255 넘게 다른 화소가 각각 4030개, 27345개). `setFrozen(true)`로 되돌리면 처음 화면과 같아졌습니다.
- **콘솔**: 오류는 `favicon.ico` 404 하나입니다(템플릿에 아이콘이 없음). 경고는 Unity가 시작할 때 형식을 조회하며 내는 `WebGL: INVALID_ENUM: getInternalformatParameter` 6개, `JS_FileSystem_Sync()` 사용 중단 예고 1개, 일부러 넣은 잘못된 덮어쓰기에 대한 경고뿐입니다. 셰이더 컴파일 오류나 예외는 없었습니다. 원자료는 `results/retry_canvas_shots_hw.json`입니다(Unity 메모리 설정 줄은 뺌).
- **SwiftShader**(`--use-angle=swiftshader --enable-unsafe-swiftshader`, CPU 렌더, `MAX_SAMPLES` 4): 모든 단계가 오류 없이 돌았습니다. 하드웨어 캔버스와 견주면 최대 채널 차가 mist 13, fragments 54, blob 49, shell 107이었고, 8/255 넘게 다른 화소 43–541개는 거의 윤곽선에 있었습니다. GPU가 없는 PC에서도 뜨기는 하지만 하드웨어와 같은 화면이라고 볼 수는 없습니다. 원자료는 `results/retry_canvas_shots_swiftshader.json`입니다.

### 10.5 WebGL ↔ Windows 플레이어

같은 복사본에서 만든 두 빌드를 같은 spec·덮어쓰기로 찍고 `tools/compare.py`(4절과 같은 지표, ΔE00)로 비교했습니다. WebGL 쪽은 `driver.html`이 Unity 안에서 렌더 텍스처로 찍은 PNG(하드웨어 ANGLE D3D11)로, 10.4에서 본 것처럼 화면 캔버스와 같습니다. 플레이어 쪽은 `queue_client.py --cases`(Direct3D 11)로 찍었습니다. 두 빌드의 코드 차이는 10.3 ①의 MSAA 해상 방식 하나뿐입니다.

| 지표 | 24 spec 평균 | 24 spec 최대 | 덮어쓰기 6개 포함 30개 최대 |
| --- | --- | --- | --- |
| 덮인 화소 수 차(비율) | 0.00003 | 0.0003 | 0.0003 |
| 평균 색 ΔE00 | 0.126 | 1.358(H08.v1) | 1.358 |
| 화소 ΔE00 평균(덮인 곳) | 0.241 | 1.739(H08.v1) | 1.739 |
| 화소 ΔE00 평균(화면 전체) | 0.146 | 0.165 | 0.165 |
| RGB 평균 절대 차(0–255) | 0.071 | 0.093 | 0.093 |
| 화소 최대 채널 차(0–255) | 16.0 | 42 | 42 |

- spec별 표는 `results/retry_cmp_player_vs_webgl.md`, 원자료는 `results/retry_cmp_player_vs_webgl.json`입니다.
- H08.v1은 덮인 화소가 112개뿐인 작은 조각이어서 윤곽선 화소의 비중이 크고, 그만큼 값이 커졌습니다. H08을 빼면 평균 색 ΔE00 최대는 0.281(H05.v1)입니다.
- 30장을 통틀어 8/255 넘게 다른 화소는 1306개이고, 그중 1305개가 플레이어 그림의 윤곽선(밝기 기울기 > 6, 1화소 넓힘) 위에 있습니다. D3D11 하드웨어 해상과 WebGL의 Blit 해상(ANGLE)이 윤곽선 화소를 다르게 섞는 것으로 보입니다. 원인을 따로 확인하지는 않았습니다. 이것과 별개로 화면 전체에 0.07/255 정도의 고른 차이가 있습니다.
- 비교 기준으로 4절의 에디터 ↔ Windows 플레이어(둘 다 D3D11)를 보면 평균 색 ΔE00이 평균 0.020, 최대 0.045였습니다. WebGL은 평균이 그 6배쯤이지만, H08 하나를 빼면 0.3 아래입니다.
- 캔버스 스크린샷 ↔ 플레이어 PNG(10장)는 평균 색 ΔE00 평균 0.065, 최대 0.174였습니다(`results/retry_cmp_player_vs_canvas.json`). 캔버스가 Unity 안 캡처와 같으므로 위 표의 해당 행과 값이 같습니다.
- 같은 복사본으로 빌드한 플레이어의 상주 지연도 다시 쟀습니다. 시작부터 준비까지 3.90 s, scene 한 장 왕복 중앙값 17.4 ms였습니다(n = 24, `results/retry_player_latency.json`).
- 에디터 기준 캡처는 저장소의 `unity/`를 열지 않으려고 다시 찍지 않았습니다. 그래서 이번 비교는 WebGL ↔ 플레이어이고, 에디터 ↔ 플레이어는 4절 값(그때 코드 기준)입니다.

### 10.6 챗봇 웹 화면에 넣으려면(구현하지 않음)

이미 준비된 것이 있습니다. `chatbot/config/v4.toml`의 `[preview] webgl_dir = "../../webgl-build/preview"`가 이번 빌드 위치와 같고, `server.py`는 `mode = "webgl"`이면서 폴더가 있으면 `/preview/webgl`에 `StaticFiles(html=True)`로 빌드를 내보냅니다. `stage.js`에는 iframe 어댑터(`WebGL.api`, `WebGL.node`)가 있습니다. 이번에 같은 Starlette(1.3.1) `StaticFiles` 마운트로 빌드를 내보내 보니 `.wasm`은 `application/wasm`, `.data`는 `application/octet-stream`으로 나갔고 페이지는 0.71 s 만에 준비됐습니다. 챗봇 서버 자체를 띄워 본 것은 아닙니다.

필요한 변경:

1. 빌드를 `<repo 밖>/webgl-build/preview`에 둡니다(`PreviewBuild.BuildWebGLPreview`). 빌드 대상이 바뀌면 전체 재임포트가 일어나므로, 다른 Unity 작업과 겹치지 않게 복사본에서 빌드하는 편이 안전합니다.
2. 설정을 `[preview] mode = "webgl"`로 바꿉니다(지금은 `image`, G25). 바꿀지 말지는 결정할 사항입니다.
3. `stage.js` WebGL 어댑터를 손봅니다. 아래는 코드를 읽고 찾은 위험이고, 실행해 보지는 않았습니다.
   - **다시 그릴 때마다 iframe이 다시 로드될 수 있습니다.** `draw()`는 `box.replaceChildren(...)`으로 화면을 새로 만드는데, 이때 같은 iframe 요소가 문서에서 빠졌다가 다시 들어갑니다. 브라우저는 다시 들어온 iframe을 새로 로드하므로 Unity가 처음부터 다시 시작되고(0.7–1.8 s), 캐시해 둔 `this.loaded`는 이미 사라진 창의 `ifsPreview`를 가리키게 됩니다. iframe을 다시 그리는 영역 밖에 고정하거나, iframe의 `load` 때 `loaded`를 새로 만들어야 합니다.
   - **호출이 한 줄로 처리되지 않습니다.** 후보 캡처 사슬(`this.chain`)과 조절 화면의 `applyOverrides`가 같은 인스턴스를 따로따로 부릅니다. 템플릿은 `loaded`와 id 없는 `error`를 가장 오래된 load 요청에 짝짓기 때문에, 두 호출이 겹치면 응답이 엇갈리거나 다른 후보의 덮어쓰기가 적용된 채로 캡처될 수 있습니다. 모든 호출을 큐 하나로 보내야 합니다.
   - **실패가 드러나지 않습니다.** `.catch(() => {})` 때문에 로드나 덮어쓰기가 실패해도 빈 그림이나 이전 형상이 그대로 남습니다. image 모드처럼 none(속성 요약)으로 바꾸고 세션 로그에 남겨야 합니다.
   - **첫 캡처가 늦습니다.** 셰이더를 처음 쓰는 렌더는 0.2–0.8 s 걸립니다. 후보를 보여 주기 전에 형태별로 한 번씩 미리 그려 두면 줄일 수 있습니다.
4. 기록을 남깁니다. 미리보기를 WebGL(ANGLE/GLES3)로 그렸다는 사실과 브라우저 렌더러 문자열(`ready` 알림의 `graphicsDevice`)을 세션 로그에 적어야 합니다. 헤드셋(D3D11) 화면과는 위 표만큼 다릅니다.

예상 위험:

- 참여자 화면을 띄우는 PC에 WebGL2를 돌릴 GPU가 있어야 합니다. GPU가 없으면 Chrome이 SwiftShader로 넘어가는데, 화면은 뜨지만 윤곽선이 하드웨어 렌더와 최대 107/255까지 다릅니다(10.4). 속도는 재지 않았습니다.
- 페이지를 열 때마다 47.5 MB를 받습니다(데이터 캐싱 끔). 이번 측정은 로컬 서버라서 1초 안에 끝났습니다. 압축을 켜면 `Content-Encoding` 헤더나 압축 해제 대체가 필요합니다.
- `PreviewStage`의 WebGL 전용 분기(10.3 ①)에는 EditMode 테스트가 닿지 않습니다. 빌드할 때마다 `driver.html` 비교를 다시 돌려야 합니다.
- 시작 화면은 빌드 스크립트로 빌드할 때만 꺼집니다.
- 미리보기 시야각(60°)과 헤드셋 시야각(96°)의 차이는 여전히 남아 있습니다(7절).
- 마우스로 끌어 돌리기는 확인하지 않았습니다(10.7).

### 10.7 확인하지 않은 것

- 마우스로 끌어 돌리기(`Input.GetMouseButton*`, 입력 처리 설정은 Both), `motion.type` 움직임이 있는 spec의 재생, 창이 있는(헤드리스가 아닌) Chrome, Edge, 다른 GPU와 운영체제.
- 에디터 기준 캡처 재촬영(10.5), 압축 빌드를 실제로 내보내는 경우, 챗봇 서버(`chatbot/`)에 붙여 보기, 오래 켜 두었을 때의 메모리.
- SwiftShader의 속도와 플레이어 대비 ΔE00(하드웨어 캔버스와의 채널 차만 잼).
- 윤곽선 차이의 원인(해상 방식 차이로 추정만 함).
- 이 문서에서는 G12/G25 판정을 바꾸지 않았습니다. 판정은 메인 세션이 `docs/decisions.md`에 적습니다.

### 10.8 재현

```bash
U="C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"; W=<repo 밖>/webgl-build
robocopy <repo>/unity $W/proj /MIR /XD Library Temp Logs obj UserSettings
"$U" -batchmode -buildTarget WebGL -projectPath $W/proj -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWebGLPreview \
  -outDir $W/preview -reportPath $W/preview-build-report.json -logFile <로그>
"$U" -batchmode -projectPath $W/proj -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWindowsPreview -outDir $W/preview-win-cp -logFile <로그>
cd <repo>/docs/validation
SPECS="render/specs/R*.json e2e/specs/{H01,H02,H03,H05,H08,H10,H12,H16,H18,H20,H28}.v1.json"
# WebGL: 서버 + 헤드리스 Chrome 드라이버(서버는 /done을 받으면 끝남. Chrome은 그 프로필로 띄운 프로세스만 골라 닫음)
python -I webgl/tools/serve.py $W/preview $W/results/webgl $SPECS --cases webgl/tools/override_cases.json --port 8765
"C:\Program Files\Google\Chrome\Application\chrome.exe" --headless=new --user-data-dir=<임시 프로필> --window-size=1000,800 http://127.0.0.1:8765/harness/driver.html
# 플레이어
python -I webgl/tools/queue_client.py $W/preview-win-cp/IFSPreview.exe $W/results/queue $W/results/player $SPECS --cases webgl/tools/override_cases.json
python -I webgl/tools/compare.py $W/results/player $W/results/webgl <결과.json> --label-a player --label-b webgl
# 캔버스 화면(serve.py를 띄워 둔 채로. /harness/spec/<i> 순서 = $SPECS 순서)
python -I webgl/tools/cdp_shot.py "C:\Program Files\Google\Chrome\Application\chrome.exe" http://127.0.0.1:8766/index.html $W/results/cdp webgl/tools/cdp_steps.json
python -I webgl/tools/cdp_shot.py <chrome> http://127.0.0.1:8766/index.html $W/results/cdp-sw webgl/tools/cdp_steps.json --extra=--use-angle=swiftshader --extra=--enable-unsafe-swiftshader
```

이번에 고치거나 더한 도구는 다음과 같습니다. `serve.py`·`driver.html`·`queue_client.py`는 덮어쓰기 사례(`--cases`, `override_cases.json`)를 받게 했고, 캔버스 스크린샷용 `cdp_shot.py`(DevTools 프로토콜, 외부 패키지 `websockets`)와 단계 파일 `cdp_steps.json`을 새로 넣었습니다. 결과 JSON에 있던 로컬 경로는 `<repo>`, `<repo 밖>`, `<임시 프로필>`로 바꿔 두었습니다.

## 11. 챗봇 연결 (2026-11-23, G12)

챗봇 웹 화면(`chatbot/ifs_chatbot/web/stage.js`)의 형상 미리보기를 WebGL로 연결했습니다. 새 흐름 설정(`chatbot/config/v4.toml`)의 `[preview] mode`가 `"webgl"`이고, 그림(image, 상주 Windows 플레이어 PNG, G25) 방식은 WebGL이 안 될 때의 예비로 남겼습니다. 기본 설정(`default.toml`·`pilot.toml`)은 바뀌지 않았습니다. 정한 세부는 `docs/decisions.md` 맨 끝 「WebGL 연결 세부」에 있습니다.

### 11.1 요약

| 항목 | 결과 |
| --- | --- |
| 다시 빌드 | 기본 형상 5개(`form.base`, 스키마 2.2.0)가 들어간 소스로 WebGL·Windows 플레이어를 같은 저장소 밖 복사본에서 다시 빌드. WebGL 73.5 s(Library 재사용), 오류 0·경고 0, 47.63 MB(`.wasm` 36.91, `.data` 10.26, `framework.js` 0.44). Windows 플레이어 4.9 s, 94.99 MB. 저장소 파일은 바뀌지 않음 |
| 이전 어댑터 문제(재현) | 이전 `stage.js`(커밋 `0093366`)를 그대로 내보내 헤드리스 Chrome으로 눌러 봄. ① 후보 화면에서 iframe이 문서에 붙지 않아 15초 뒤에도 후보 그림 4칸이 모두 비어 있었고 오류·대체도 없었음 ② 조절 버튼을 누를 때마다 iframe이 다시 로드됨(load 1 → 2 → 3회, Unity가 매번 다시 시작) ③ 두 번 조절한 뒤 화면의 Unity에는 형상이 아예 없었음(`로드된 형상이 없습니다`). 캐시해 둔 `loaded`가 사라진 창을 가리켜 새 창에 spec이 들어가지 않은 것. 서버 쪽 현재 값은 바뀌어 있었음. 결과 `results/g12_repro_old_adapter.json` |
| 고친 뒤 WebGL 끝에서 끝까지 | 합성 시나리오 S1–S9 + 조절 일곱 항목의 모든 값을 누르는 세션 1개, 헤드리스 Chrome 157(하드웨어 ANGLE D3D11, RTX 5080). 10개 세션 모두 webgl로 끝까지(후보 → 선택 → 조절 → 사전 측정 → `selection.json`·`premeasure.json` 저장, `runnerReady` true), 시나리오 기대값 실패 0, 면담 뒤 단계 LLM 호출 0, **콘솔 오류 0** |
| iframe 재시작 | 0회(10개 세션 모두 처음 창에 심은 표시가 끝까지 같음, iframe load 추가 0) |
| 후보 그림 섞임 | 없음. 후보가 있는 8개 세션 모두, 각 칸 그림을 같은 spec·덮어쓰기로 예비 플레이어가 그린 그림 4장과 비교한 화면 전체 평균 ΔE00 행렬에서 자기 후보가 행마다 가장 가까움(대각 0.14–0.19, 다른 후보 0.17–6.24). 칸의 `data-target`도 모두 일치 |
| 조절 값마다 화면 | 바뀜. 모든 값 세션에서 54단계 모두 브라우저 화면이 바뀜. 가장 작은 변화는 기본 형상 물방울 + 불투명도 0.8에서 질감 0.7 → 0.9(최대 채널 차 7/255, 8/255 넘는 화소 0). 누름 → Unity에 얹힘 중앙값 26.3 ms, 최대 104 ms(n = 65) |
| 움직임(조절 화면) | 재생됨. 움직임 값 5개(floating·swaying·trembling·pounding·sinking) 모두 0.7초 사이에 화면이 바뀜(8/255 넘는 화소 267–4416개), still로 돌리면 0. 후보 칸은 계속 정지 그림(캡처 전에 `setFrozen(true)`) |
| 기본 형상 | 조절 "형태"의 9값(5개 기본 형상 포함)이 모두 WebGL에서 그려짐(시작 값 mist + 눌러 바꾼 8값). 눌러 바꾼 8값은 같은 덮어쓰기를 플레이어로 그린 320×240과 화면 전체 평균 ΔE00 0.156–0.163(같은 플레이어 대비 후보 대각과 같은 수준). 반투명 그릇(담는 것 + 투명도 0.4)도 그려짐. 그림 `results/g12_adjust_forms_webgl_vs_player.png`(위 WebGL, 아래 플레이어) |
| 첫 후보까지 | 새 브라우저 프로필에서 [다음 단계로] → 후보 4칸이 다 참: 2.36 s(Unity 준비 0.73 s + 미리 그리기 1.53 s 포함). 같은 브라우저로 다시 열면 0.42–0.48 s(준비 0.17–0.21 s, 미리 그리기 0.18–0.19 s) |
| WebGL을 막았을 때 | 빌드 폴더 이름을 바꾸고 서버를 띄우면 서버가 image로 시작(`WebGL 빌드가 없음(../../webgl-build/preview/index.html) → image`), 브라우저에서 WebGL을 끄면(`--disable-webgl`) 화면이 서버에 알려 그 세션이 image로 내려감. 두 경우 모두 4개 세션이 image로 끝까지 가고, `selection.json` `preview.fallbacks`에 from·to·이유·`server`/`client`, 세션 로그에 `preview_fallback` 알림, 화면 맨 위에 경고 줄, 움직임 줄 꺼짐(6값 모두 비활성, 기록 `adjustUnavailable.motion`). 콘솔 오류 0 |
| WebGL ↔ Windows 플레이어 | spec 44개(합성 13 + held-out v1 11 + **기본 형상 합성 20**) + 덮어쓰기 14개. 평균 색 ΔE00 평균 0.112·최대 1.358(H08). 기본 형상 20개만: 평균 0.133·최대 0.763(L5 가는 엉킨 선), 덮인 화소 차 최대 4화소. 이전 24개의 값은 10.5절과 같음(평균 0.126·최대 1.358) |

### 11.2 고친 것

| 문제 | 고친 방법 |
| --- | --- |
| 다시 그릴 때 iframe이 옮겨져 다시 로드됨, 후보 화면에서는 문서에 없음 | iframe을 세션마다 한 번 만들어 `document.body` 아래 host에 두고 옮기지 않음. 후보 화면에서는 화면 밖(-10000 px, 320×240 — 보이지 않지만 그려짐), 조절 화면에서는 미리보기 자리(`.live-slot`, 4:3) 위에 겹쳐 둠(ResizeObserver로 따라감). 사전 측정으로 가면 닫음 |
| 후보 캡처와 조절이 같은 인스턴스를 따로 부름 | 모든 Unity 호출을 큐 하나로. 덮어쓰기는 Unity가 돌려준 `overrides`를 요청과 대조, 캡처는 요청 id를 대조. 요청마다 15 s 한도 |
| `.catch(() => {})`가 실패를 숨김 | 실패(WebGL2 없음, Unity 준비 30 s 초과·시작 실패, 요청 실패·시간 초과·응답 불일치, 컨텍스트 잃음)를 `POST /api/sessions/{sid}/preview/client`로 알림 → 서버가 그 세션을 image(예비 플레이어가 없거나 실패했으면 none)로 내리고 기록한 뷰를 돌려줌 → 다시 그림. image가 실패하면(PNG 오류) 전처럼 서버가 none으로 내림 |
| 첫 그리기의 셰이더 컴파일 지연 | 준비 단계에서 형태 값 9개 × (기본 불투명도, 0.5)를 64×48로 한 번씩 캡처(서버 `previewWarmup`). 그 뒤 조절에서 처음 고르는 형태도 26 ms 안팎 |
| 쓴 방식이 기록되지 않음 | `selection.json` `preview`에 `serverMode`·`shown`(단계별로 실제로 그린 방식)·`fallbacks`·`webgl`(렌더러·벤더·Unity 그래픽 장치·WebGL 버전·준비 ms·미리 그리기 ms). 렌더러 문자열 예: `ANGLE (NVIDIA, NVIDIA GeForce RTX 5080 (0x00002C02) Direct3D11 vs_5_0 ps_5_0, D3D11)` — GPU 이름이라 참여자를 가리키지 않음. 사용자 에이전트는 적지 않음 |
| 템플릿: Unity 시작 실패 때 `ready`가 끝없이 기다림 | `ifsPreview.ready`를 거부, Unity `ready` 알림을 `ifsPreview.unityInfo`로 보관, `webglcontextlost`면 대기 요청을 거부, `favicon.ico` 404를 빈 아이콘으로 없앰(챗봇 `index.html`도) |
| image에서 움직임이 안 보임(G22) | 세션 방식이 image면 움직임 줄을 끄고 초안 문구 `adjust_item_unavailable`을 붙임. 서버도 거부(409), 기록 `adjustUnavailable` |

Unity C#(Placement·Rendering 포함)은 고치지 않았습니다. WebGL 템플릿(`unity/Assets/WebGLTemplates/IFSPreview/index.html`)만 바꿨습니다.

### 11.3 image로 내려가는 조건

| 언제 | 누가 알아채나 | 범위 | 기록 |
| --- | --- | --- | --- |
| 서버 시작 때 `webgl_dir/index.html`이 없음 | 서버 | 그 서버의 모든 세션 | `fallbacks[0].source = "server"`, `/api/health`·화면 경고 줄 |
| 브라우저가 WebGL2 컨텍스트를 못 만듦 | 화면(`stage.js`) | 그 세션 | `source = "client"`, 이유 `이 브라우저에서 WebGL2를 쓸 수 없음` |
| Unity가 `webgl_ready_timeout_s`(30 s) 안에 준비되지 않거나 시작 실패 | 화면 | 그 세션 | 이유에 단계(`준비: …`) |
| 요청 하나가 `webgl_request_timeout_s`(15 s)를 넘김, 오류, 응답이 요청과 다름 | 화면 | 그 세션 | 이유에 요청 이름(예: `후보 캡처 c-…: …`) |
| WebGL 컨텍스트를 잃음 | 템플릿 → 화면 | 그 세션 | 이유 `WebGL 컨텍스트를 잃음` |

예비 플레이어(`image_player`)가 없거나 이 서버 프로세스에서 이미 한 번 실패했으면 image 대신 none(글 요약)으로 내려갑니다. 내려간 세션이 다시 webgl로 올라가지는 않습니다.

### 11.4 WebGL ↔ Windows 플레이어 (기본 형상 포함, 다시 잼)

10.5절과 같은 방법(`tools/compare.py`, 800×600, scene·black·white 세 장, Unity 안 렌더 텍스처)입니다. 기본 형상 spec 20개는 `docs/validation/base-forms/make_specs.py shapes`로 만들었고(저장소 밖), 덮어쓰기 사례에 기본 형상 8개(`tools/override_cases_base.json`: R07 → 다섯 형상, 반투명 그릇, 안개 → 불꽃, 그릇 → 없음)를 더했습니다.

| 묶음 | n | 평균 색 ΔE00 평균 | 최대 | 화소 ΔE00(덮인 곳) 최대 | 최대 채널 차 |
| --- | --- | --- | --- | --- | --- |
| 이전 24개(합성 13 + held-out 11) | 24 | 0.126 | 1.358(H08) | 1.739 | 42 |
| 기본 형상 합성 20개 | 20 | 0.133 | 0.763(L5) | 0.860 | 30 |
| 덮어쓰기(이전 6) | 6 | 0.058 | 0.138 | 0.300 | 24 |
| 덮어쓰기(기본 형상 8) | 8 | 0.058 | 0.130 | 0.267 | 30 |
| 전체 | 58 | 0.112 | 1.358 | 1.739 | 42 |

- spec별 표 `results/g12_cmp_player_vs_webgl.md`, 원자료 `results/g12_cmp_player_vs_webgl.json`, WebGL 쪽 드라이버 기록 `results/g12_webgl_driver.json`.
- 기본 형상은 모두 `renderPath` = `base:<형상>`이었고(대체 경로 없음), 덮인 화소 수는 D3 하나만 4화소 다르고 나머지는 같았습니다. 가장 큰 차이(L5)는 가는 엉킨 선이라 윤곽선 화소의 비중이 큰 경우입니다(10.5절 H08과 같은 이유로 봄).
- 첫 렌더 지연(이 빌드): 첫 mist 814 ms, 첫 fragments 469 ms, 첫 반투명 blob(H01) 218 ms. 기본 형상은 첫 렌더도 12–14 ms였습니다. 상주 플레이어 한 장 왕복은 중앙값 17.5 ms(n = 44).

### 11.5 챗봇 끝에서 끝까지 확인 방법

`tools/chatbot_e2e.py`가 챗봇 서버(`tools/chatbot_e2e_server.py`, `chatbot/.venv`의 python, 127.0.0.1)를 띄우고, 합성 시나리오의 면담을 서버 안에서 정적 조건으로 끝낸 뒤(LLM 없음), 헤드리스 Chrome을 DevTools 프로토콜로 몰아 [다음 단계로] → 후보 → 선택 → 조절 → 사전 측정 제출까지 화면의 버튼을 누릅니다. 단계마다 iframe 창이 같은지, 후보 칸 그림이 그 후보의 것인지(예비 플레이어로 따로 그린 그림과 대조), 조절 뒤 화면(스크린샷)이 바뀌는지, 움직임이 시간에 따라 바뀌는지, `selection.json`이 시나리오 기대값과 같은지(`selection_sim.check`), LLM 호출 수, 콘솔 오류를 모읍니다. 결과는 `results/g12_chatbot_e2e_webgl.json`·`_blocked-dir.json`·`_no-webgl2.json`(PNG는 저장소 밖). 화면 캡처 셋을 `docs/validation/selection-flow/screens/webgl_*.png`에 두었습니다.

- 콘솔 경고(오류 아님): Unity 시작 때의 `WebGL: INVALID_ENUM: getInternalformatParameter`·`JS_FileSystem_Sync()` 사용 중단 예고(10.4와 같음), 시나리오 S6·S7·S9 spec의 SceneLoader 안내(모형 없는 모양어, `form.base=sheet` 그리지 않음 — 규칙대로), WebGL을 끈 실행에서 어댑터가 남긴 `[preview] webgl 실패 → 서버에 알림` 한 줄.

### 11.6 확인하지 않은 것

- **창이 있는(헤드리스가 아닌) 브라우저**, Edge, 다른 GPU·PC, 소프트웨어 렌더(SwiftShader)에서의 챗봇 화면. 이번에는 이 PC의 헤드리스 Chrome(하드웨어 GPU)만 봤습니다.
- 마우스로 끌어 돌리기(조절 화면의 iframe 안 드래그). 코드는 그대로이고 눌러 보지 않았습니다.
- Unity 시작이 30 s를 넘기거나 요청이 15 s를 넘기는 경우, WebGL 컨텍스트를 잃는 경우를 실제로 일으켜 보지 않았습니다(WebGL2 없음과 빌드 폴더 없음만 일부러 일으킴). 이 경로들은 같은 `fail()` → 서버 알림을 탑니다.
- 오래 켜 두었을 때의 메모리, 여러 탭에서 같은 세션을 여는 경우.
- 사람이 보는 첫 후보까지의 시간은 로컬 서버·이 PC 기준입니다. 첫 페이지마다 47.6 MB를 받습니다(데이터 캐싱 끔, 브라우저 HTTP 캐시는 씀 — 두 번째부터 빨라진 이유로 봄, 따로 확인하지 않음).
- Unity EditMode·dotnet 테스트는 다시 돌리지 않았습니다(Unity C#을 바꾸지 않음, 템플릿 HTML만 바꿈).

### 11.7 사람이 정할 것

`docs/morning-todo.md` 「G12 WebGL 연결」에 모았습니다(움직임 끄기와 새 문구, WebGL과 헤드셋의 색 차이, 첫 후보까지 시간, 렌더러 문자열 기록, 실제 브라우저 확인, 거의 안 보이는 조절 조합).

### 11.8 재현

```bash
U="C:\Program Files\Unity\Hub\Editor\6000.0.85f2\Editor\Unity.exe"; W=<repo 밖>/webgl-build
# PowerShell에서: robocopy <repo>\unity $W\proj /MIR /XD Library Temp Logs obj UserSettings   (종료 코드 0–7 = 정상)
"$U" -batchmode -buildTarget WebGL -projectPath $W/proj -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWebGLPreview \
  -outDir $W/preview -reportPath $W/preview-build-report.json -logFile <로그>
"$U" -batchmode -projectPath $W/proj -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWindowsPreview -outDir $W/preview-win -logFile <로그>
"$U" -batchmode -projectPath $W/proj -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWindowsPreview -outDir $W/preview-win-cp -logFile <로그>
# 기본 형상 spec(저장소 밖)
chatbot/.venv/Scripts/python.exe docs/validation/base-forms/make_specs.py shapes $W/g12/specs-base
# WebGL ↔ 플레이어: 10.8과 같고, spec에 $W/g12/specs-base/[CDFLS]*.json을, --cases에 override_cases.json과 override_cases_base.json을 합친 파일을 줌
# 챗봇 끝에서 끝까지(websockets·numpy·Pillow가 있는 python. 서버는 chatbot/.venv의 python으로 이 스크립트가 띄움)
cd docs/validation/webgl/tools
python chatbot_e2e.py --out $W/g12/e2e-webgl --label webgl --sweep --ref-player $W/preview-win-cp/IFSPreview.exe
#   빌드 폴더를 막은 경우: $W/preview 이름을 바꾸고 같은 명령(--label blocked-dir), 끝나면 이름을 되돌림
python chatbot_e2e.py --out $W/g12/e2e-no-webgl2 --label no-webgl2 --sweep --ref-player $W/preview-win-cp/IFSPreview.exe \
  --scenarios S1_form_said S3_all_said S8_base_said_edited --extra=--disable-webgl
```

- 이전 어댑터 재현은 `chatbot_e2e_server.py --web-dir <이전 커밋의 web 폴더를 꺼낸 곳>`으로 서버를 띄우고 [다음 단계로]·후보·조절 두 번을 누른 뒤 iframe 수·load 횟수·후보 그림 유무를 본 것입니다(스크립트는 저장소에 넣지 않음, 결과만 `results/g12_repro_old_adapter.json`).
- 빌드 산출물·PNG·로그는 모두 `<repo 밖>/webgl-build/` 아래에 있고 git에 넣지 않았습니다. 결과 JSON의 로컬 경로는 `<repo>`, `<repo 밖>`으로 바꿨습니다.
