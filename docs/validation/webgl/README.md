# WebGL 미리보기 시험 빌드 (D4, 결정 G12)

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
