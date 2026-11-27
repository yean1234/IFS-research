// 브라우저(챗봇 웹 화면) ↔ Unity WebGL 미리보기 다리(D4, 결정 G12).
// 이 컴포넌트가 붙은 GameObject 이름은 "IFS Preview"다(JS: unityInstance.SendMessage("IFS Preview", 메서드, 문자열)).
//   LoadSpecJson(json)          spec JSON 문자열을 로드(덮어쓰기는 비운다). 성공 → JS ifsPreview 'loaded' {…}, 실패 → 'error' {…}
//   ApplyOverridesJson(json)    지금 spec 위에 덮어쓰기 목록(SceneOverrideJson 형식, 예: {"form.type":"mist","material.opacity":0.6})을 얹어 다시 로드.
//                               "" 또는 "{}" = 덮어쓰기 지움. 결과는 LoadSpecJson과 같은 콜백
//   SetFormAssetJson(json)      G62: 생성 형태 GLB {"assetId","glbSha256","glbBase64"}를 얹는다("" = 걷기). 로드할 때마다 절차 모형의 메시를
//                               이것으로 바꾼다(러너와 같은 SceneLoader.ApplyFormAsset — 가장 긴 변·재질 규칙). 결과는 'loaded' {kind:"formAsset"} 또는 'error'
//   SetAutoRotate("12")         천천히 돌기(°/초, 0 = 멈춤)
//   SetFrozen("1"|"0")          움직임(motion.type)을 멈추고 정지 자세로(비교 캡처용) / 다시 움직이게(다시 로드)
//   Capture(json)               {"id":"..","width":800,"height":600,"background":"scene|black|white"} → 같은 크기로 렌더한 PNG(base64)를
//                               JS 'capture' {id, width, height, background, png}로 보낸다(검증용: 데스크톱 캡처와 같은 코드로 찍는다)
// 마우스 왼쪽 드래그 = 형상을 세로축으로 돌리기(미리보기 조작, 기록하지 않음).
// 이 화면은 참여자 기록을 남기지 않는다(SceneLoader 기록 끔). 고른 값의 저장은 챗봇 서버가 한다(D5).
// 데스크톱 상주 프로세스(대안 경로 측정): 명령줄 -ifsPreviewQueue <폴더>를 주면 폴더의 요청 JSON을 읽어 PNG를 쓴다(WebGL 빌드에는 없음).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
#if UNITY_WEBGL && !UNITY_EDITOR
using System.Runtime.InteropServices;
#endif
using Newtonsoft.Json.Linq;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace IFS.SceneSpec
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Preview Bridge (WebGL)")]
    public sealed class PreviewBridge : MonoBehaviour
    {
        public const string ObjectName = "IFS Preview";
        const string SourceName = "preview.json";

        [SerializeField] PreviewSettings settings = new PreviewSettings();
        [Tooltip("모양 모형 프리팹(메뉴가 연결). 비어 있으면 같은 형상을 코드로 만들고 경고")]
        [SerializeField] ShapePrefab[] shapePrefabs =
        {
            new ShapePrefab("round"), new ShapePrefab("square"), new ShapePrefab("flat"), new ShapePrefab("pointed"),
        };
        [Tooltip("천천히 돌기(°/초). 0 = 멈춤. JS SetAutoRotate로 바꿀 수 있다")]
        [SerializeField] float autoRotateDegPerSec = 0f;
        [Tooltip("마우스 왼쪽 드래그로 돌리기(°/화소)")]
        [SerializeField] float dragDegPerPixel = 0.4f;

        PreviewStage _stage;
        bool _frozen;
        Vector3 _lastMouse;
        bool _dragging;

        public PreviewStage Stage => _stage;
        public PreviewSettings Settings => settings;

        public void ConfigureShapePrefabs(IEnumerable<ShapePrefab> prefabs) => shapePrefabs = new List<ShapePrefab>(prefabs ?? Array.Empty<ShapePrefab>()).ToArray();

        void Awake()
        {
            if (gameObject.name != ObjectName)
                Debug.LogWarning($"[Preview] GameObject 이름이 '{ObjectName}'가 아니면 JS SendMessage가 닿지 않습니다(지금 '{gameObject.name}').", this);
            EnsureStage();
#if !UNITY_WEBGL || UNITY_EDITOR
            _queue = PreviewQueue.FromCommandLine(this);
#endif
        }

        void OnDestroy() => Shutdown();

        /// <summary>무대를 정리한다(에디트 모드 테스트는 OnDestroy가 불리지 않으므로 직접 부른다).</summary>
        public void Shutdown()
        {
            _stage?.Dispose();
            _stage = null;
        }

        // 플레이어에서는 Awake가, 에디트 모드(테스트)에서는 첫 진입점 호출이 무대를 만든다.
        void EnsureStage()
        {
            if (_stage != null) return;
            var sw = Stopwatch.StartNew();
            _stage = PreviewStage.Create(settings, shapePrefabs, transform, cameraEnabled: true);
            sw.Stop();
            Notify("ready", new JObject
            {
                ["stageMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 1),
                ["quality"] = QualitySettings.names[QualitySettings.GetQualityLevel()],
                ["antiAliasing"] = QualitySettings.antiAliasing,
                ["colorSpace"] = QualitySettings.activeColorSpace.ToString(),
                ["graphicsDevice"] = SystemInfo.graphicsDeviceVersion,
                ["platform"] = Application.platform.ToString(),
            });
        }

        void Update()
        {
#if !UNITY_WEBGL || UNITY_EDITOR
            _queue?.Poll();
#endif
            if (_stage?.Loader?.Root == null || _frozen) return;
            float yaw = _stage.Yaw;
            if (autoRotateDegPerSec != 0f) yaw += autoRotateDegPerSec * Time.deltaTime;
            if (dragDegPerPixel > 0f)
            {
                if (Input.GetMouseButtonDown(0)) { _dragging = true; _lastMouse = Input.mousePosition; }
                if (Input.GetMouseButtonUp(0)) _dragging = false;
                if (_dragging)
                {
                    var m = Input.mousePosition;
                    yaw -= (m.x - _lastMouse.x) * dragDegPerPixel;
                    _lastMouse = m;
                }
            }
            if (yaw != _stage.Yaw) _stage.SetYaw(yaw % 360f);
        }

        // ── JS 진입점(SendMessage는 문자열 인자 하나) ─────────────────────────
        public void LoadSpecJson(string json) { EnsureStage(); LoadInternal(json, null, "load"); }

        public void ApplyOverridesJson(string json)
        {
            EnsureStage();
            if (_stage?.SpecJson == null) { NotifyError("overrides", "먼저 LoadSpecJson으로 spec을 넣어야 합니다", null); return; }
            var ov = SceneOverrideJson.Parse(json, out var errors);
            if (ov == null) { NotifyError("overrides", "덮어쓰기를 읽지 못했습니다", errors); return; }
            LoadInternal(_stage.SpecJson, ov, "overrides");
        }

        /// <summary>G62: 생성 형태 GLB를 얹는다({"assetId","glbSha256","glbBase64"}) / ""이면 걷는다. 지금 spec·덮어쓰기로 다시 로드하고
        /// 'loaded' {kind: "formAsset", formAsset: {status, renderedLongestEdgeM…} | null}. GLB를 받지 못하거나(sha256·형식) 적용하지 못하면
        /// 생성 메시를 걷고 절차 모형으로 둔 뒤 'error' {kind: "formAsset"} — 챗봇은 그 후보를 빼고 사유를 기록한다.</summary>
        public void SetFormAssetJson(string json)
        {
            EnsureStage();
            if (_stage?.SpecJson == null) { NotifyError("formAsset", "먼저 LoadSpecJson으로 spec을 넣어야 합니다", null); return; }
            if (string.IsNullOrWhiteSpace(json) || json.Trim() == "null")
            {
                _stage.ClearFormAsset();
                LoadInternal(_stage.SpecJson, _stage.Overrides, "formAsset");
                return;
            }
            FormAsset.FormAssetRef asset;
            FormAsset.GlbMesh mesh;
            string error;
            try { mesh = FormAsset.FormAssetPayload.Decode(JObject.Parse(json), null, out asset, out error); }
            catch (Newtonsoft.Json.JsonException e) { mesh = null; asset = null; error = "요청 JSON: " + e.Message; }
            if (mesh == null) { RestoreProcedural(); NotifyError("formAsset", error, null); return; }
            _stage.SetFormAsset(asset, mesh);
            bool ok;
            try { ok = _stage.Reapply(_stage.Overrides); }
            catch (Exception e) { ok = false; error = e.GetType().Name + ": " + e.Message; }
            var res = _stage.LastFormAsset;
            if (!ok || res == null || !res.Applied)
            {
                string why = error ?? res?.FallbackReason ?? "다시 로드하지 못함";
                RestoreProcedural();
                NotifyError("formAsset", "생성 형태를 그리지 못했습니다: " + why, res?.Detail != null ? new List<string> { res.Detail } : null);
                return;
            }
            if (_frozen) { _stage.SetYaw(0f); _stage.FreezeMotion(); }
            Notify("loaded", new JObject
            {
                ["kind"] = "formAsset",
                ["renderPath"] = _stage.Loader.RenderPath,
                ["overrides"] = _stage.Overrides?.OverridesJson(),
                ["formAsset"] = res.ManifestJson(),
            });
        }

        // 생성 메시를 걷고 절차 모형으로 다시 로드(알리지 않음 — 부른 쪽이 error를 한 번만 알린다)
        void RestoreProcedural()
        {
            _stage.ClearFormAsset();
            try { _stage.Reapply(_stage.Overrides); } catch (Exception e) { Debug.LogWarning("[Preview] 절차 모형으로 되돌리지 못함: " + e.Message, this); }
            if (_frozen) { _stage.SetYaw(0f); _stage.FreezeMotion(); }
        }

        public void SetAutoRotate(string degPerSec)
        {
            if (float.TryParse(degPerSec, NumberStyles.Float, CultureInfo.InvariantCulture, out var v)) autoRotateDegPerSec = v;
            else NotifyError("rotate", "숫자가 아닙니다: " + degPerSec, null);
        }

        public void SetFrozen(string flag)
        {
            _frozen = flag == "1" || string.Equals(flag, "true", StringComparison.OrdinalIgnoreCase);
            if (_stage == null) return;
            if (_frozen) { _stage.SetYaw(0f); _stage.FreezeMotion(); }
            else if (_stage.SpecJson != null) _stage.Reapply(_stage.Overrides);
        }

        public void Capture(string argsJson)
        {
            string id = null;
            EnsureStage();
            try
            {
                var a = JObject.Parse(string.IsNullOrEmpty(argsJson) ? "{}" : argsJson);
                id = (string)a["id"] ?? "capture";
                int w = (int?)a["width"] ?? 800, h = (int?)a["height"] ?? 600;
                if (w < 16 || h < 16 || w > 4096 || h > 4096) throw new ArgumentException($"크기 {w}×{h}가 16–4096 밖");
                var bg = ParseBackground((string)a["background"]);
                if (_stage?.Loader?.Root == null) throw new InvalidOperationException("로드된 형상이 없습니다");
                var sw = Stopwatch.StartNew();
                var png = _stage.RenderPng(w, h, bg);
                sw.Stop();
                Notify("capture", new JObject
                {
                    ["id"] = id, ["width"] = w, ["height"] = h, ["background"] = bg.ToString().ToLowerInvariant(),
                    ["renderMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 1), ["png"] = Convert.ToBase64String(png),
                });
            }
            catch (Exception e)
            {
                NotifyError("capture", e.Message, null, id);
            }
        }

        public static PreviewBackground ParseBackground(string s)
        {
            switch ((s ?? "scene").ToLowerInvariant())
            {
                case "scene": return PreviewBackground.Scene;
                case "black": return PreviewBackground.Black;
                case "white": return PreviewBackground.White;
                default: throw new ArgumentException("background는 scene·black·white 중 하나: " + s);
            }
        }

        void LoadInternal(string json, SceneOverride ov, string kind)
        {
            if (_stage == null) { NotifyError(kind, "미리보기 무대가 없습니다", null); return; }
            var errors = new List<string>();
            void OnLog(string condition, string stack, LogType type)
            {
                if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) errors.Add(condition);
            }
            var sw = Stopwatch.StartNew();
            bool ok;
            Application.logMessageReceived += OnLog;
            try { ok = _stage.Load(json, SourceName, ov); }
            catch (Exception e) { ok = false; errors.Add(e.GetType().Name + ": " + e.Message); }
            finally { Application.logMessageReceived -= OnLog; }
            sw.Stop();
            if (!ok) { NotifyError(kind, "spec을 로드하지 못했습니다", errors); return; }
            if (_frozen) { _stage.SetYaw(0f); _stage.FreezeMotion(); }
            var loader = _stage.Loader;
            var payload = new JObject
            {
                ["kind"] = kind,
                ["loadMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 1),
                ["sessionId"] = loader.Spec?.Meta?.SessionId,
                ["renderPath"] = loader.RenderPath,
                ["params"] = JObject.FromObject(loader.CurrentParams.ToRecord()),
                ["defaultsUsed"] = new JArray(loader.InitialParams.DefaultsUsed),
                ["overrides"] = ov?.OverridesJson(),
                ["shapeModel"] = loader.Shape?.Model,
                ["notes"] = new JArray(loader.Notes),
                ["errors"] = new JArray(errors),
            };
            // G62: 생성 메시를 얹은 채 다시 로드했으면 그 결과(얹은 것이 없으면 키 없음 — 이전 응답 그대로)
            if (_stage.LastFormAsset != null) payload["formAsset"] = _stage.LastFormAsset.ManifestJson();
            Notify("loaded", payload);
        }

        void NotifyError(string kind, string message, List<string> details, string id = null)
        {
            Debug.LogWarning($"[Preview] {kind}: {message}" + (details != null && details.Count > 0 ? " — " + string.Join("; ", details) : ""), this);
            Notify("error", new JObject { ["kind"] = kind, ["id"] = id, ["message"] = message, ["details"] = new JArray(details ?? new List<string>()) });
        }

        // ── JS로 알리기(.jslib) ─────────────────────────────────────────────
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] static extern void IFSPreview_Notify(string kind, string payloadJson);
#endif

        /// <summary>마지막 알림(에디터·데스크톱에서 확인용).</summary>
        public string LastNotifyKind { get; private set; }
        public JObject LastNotifyPayload { get; private set; }
        public event Action<string, JObject> Notified;

        void Notify(string kind, JObject payload)
        {
            LastNotifyKind = kind;
            LastNotifyPayload = payload;
            Notified?.Invoke(kind, payload);
#if UNITY_WEBGL && !UNITY_EDITOR
            IFSPreview_Notify(kind, payload.ToString(Newtonsoft.Json.Formatting.None));
#endif
        }

#if !UNITY_WEBGL || UNITY_EDITOR
        PreviewQueue _queue;
#endif
    }
}
