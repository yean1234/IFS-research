// 형상 미리보기 무대(D4, 결정 G12): 중립 환경 + 고정 카메라 + SceneLoader 하나.
// WebGL 플레이어(PreviewBridge)와 에디터 배치 캡처(Editor/PreviewCapture)가 같은 이 코드를 쓴다 — 두 플랫폼의 화면을 같은 조건에서 비교하기 위해서다.
//   카메라: 로드 순간의 머리 = (0, 눈높이, 0)에서 +Z. 로드 뒤 형상 경계 중심을 보도록 돌린다(BatchCapture와 같은 규칙).
//           세로 시야각은 미리보기 설정값(기본 60°). 헤드셋 시야각(96°)이 아니므로 형상이 VR보다 크게 보인다.
//   환경:   EnvironmentBuilder(바닥·하늘·앰비언트·방향광·반사)를 형상보다 먼저 만든다(반사 큐브맵에 형상이 찍히지 않게).
//   로더:   기록 끔(참여자 기록 폴더에 쓰지 않음), _inferred 끔. 형상은 SceneLoader.LoadJson(같은 파싱·해석·렌더 경로).
//   캡처:   RenderTexture(sRGB, MSAA = 품질 단계 값)에 수동 렌더 → 해상 → ReadPixels. 배경 Scene(실제 장면) / Black / White(바닥·하늘을 끄고 단색).
//           검은·흰 배경 쌍으로 화소별 덮임(BatchCapture와 같은 식)을 계산한다.
//   움직임: 비교 캡처는 움직임을 멈추고 자세를 처음(정지) 값으로 둔다(FreezeMotion). 화면 회전(yaw)도 0으로.
using System;
using System.Collections.Generic;
using UnityEngine;

namespace IFS.SceneSpec
{
    public enum PreviewBackground { Scene, Black, White }

    [Serializable]
    public sealed class PreviewSettings
    {
        [Tooltip("세로 시야각(°). 미리보기 창용 — 헤드셋(96°)과 다르다")] public float fieldOfView = 60f;
        [Tooltip("로드 순간 눈높이(m). BatchCapture 기본과 같다")] public float eyeHeight = 1.6f;
        [Tooltip("품질 단계 이름(비우면 지금 단계). 데스크톱 비교를 위해 VR PC")] public string qualityName = "VR PC";
        public float nearClip = 0.05f;
        public float farClip = 300f;
    }

    public sealed class PreviewStage : IDisposable
    {
        public PreviewSettings Settings { get; }
        public EnvironmentHandle Environment { get; private set; }
        public Camera Camera { get; private set; }
        public SceneLoader Loader { get; private set; }
        /// <summary>마지막으로 받은 spec JSON(덮어쓰기를 다시 적용할 때 쓴다). 로드 실패면 바뀌지 않는다.</summary>
        public string SpecJson { get; private set; }
        public string SourceName { get; private set; }
        public SceneOverride Overrides { get; private set; }
        public float Yaw { get; private set; }
        /// <summary>G62: 얹은 생성 형태 메시(없으면 null). 로드할 때마다(덮어쓰기를 바꿔도) 절차 모형의 메시를 이것으로 바꾼다
        /// (SceneLoader.ApplyFormAsset — 러너와 같은 크기·재질 규칙).</summary>
        public FormAsset.FormAssetRef AssetRef { get; private set; }
        public FormAsset.GlbMesh AssetMesh { get; private set; }
        /// <summary>마지막 로드에서 생성 메시를 적용한 결과(얹은 것이 없으면 null).</summary>
        public FormAsset.FormAssetResult LastFormAsset { get; private set; }

        public void SetFormAsset(FormAsset.FormAssetRef asset, FormAsset.GlbMesh mesh) { AssetRef = asset; AssetMesh = mesh; }
        public void ClearFormAsset() { AssetRef = null; AssetMesh = null; LastFormAsset = null; }

        GameObject _camGo, _loaderGo;
        Quaternion _rootBaseRotation = Quaternion.identity;

        PreviewStage(PreviewSettings s) { Settings = s ?? new PreviewSettings(); }

        /// <summary>무대를 만든다. cameraEnabled = 화면에 그릴지(플레이어) / 수동 렌더만 할지(에디터 캡처).</summary>
        public static PreviewStage Create(PreviewSettings settings, IEnumerable<ShapePrefab> shapePrefabs, Transform parent = null,
                                          bool cameraEnabled = true, EnvironmentSettings environment = null)
        {
            var st = new PreviewStage(settings);
            st.ApplyQuality();
            st.Environment = EnvironmentBuilder.Build(environment ?? new EnvironmentSettings(), parent);

            st._camGo = new GameObject("preview camera");
            if (parent != null) st._camGo.transform.SetParent(parent, false);
            var cam = st._camGo.AddComponent<Camera>();
            cam.enabled = cameraEnabled;
            cam.fieldOfView = st.Settings.fieldOfView;
            cam.nearClipPlane = st.Settings.nearClip;
            cam.farClipPlane = st.Settings.farClip;
            cam.allowMSAA = true;
            cam.allowHDR = false;
            cam.clearFlags = CameraClearFlags.Skybox;
            // 데스크톱 플레이어가 XR(OpenXR)을 시작해도 이 카메라는 헤드셋이 아니라 창·렌더 텍스처에 그린다
            cam.stereoTargetEye = StereoTargetEyeMask.None;
            st.Camera = cam;
            st.ResetCamera();

            st._loaderGo = new GameObject("SceneLoader (preview)");
            if (parent != null) st._loaderGo.transform.SetParent(parent, false);
            st._loaderGo.SetActive(false);   // OnEnable·Start(경로 소스 자동 로드)를 설정 전에 부르지 않도록
            st.Loader = st._loaderGo.AddComponent<SceneLoader>();
            st.Loader.ConfigureForRunner(cam.transform, null);   // 기록 끔, 자동 로드 끔, _inferred 끔
            st.Loader.ConfigureShapePrefabs(shapePrefabs);
            st._loaderGo.SetActive(true);
            return st;
        }

        void ApplyQuality()
        {
            if (string.IsNullOrEmpty(Settings.qualityName)) return;
            int idx = Array.IndexOf(QualitySettings.names, Settings.qualityName);
            if (idx < 0)
            {
                Debug.LogWarning($"[Preview] 품질 단계 '{Settings.qualityName}'가 없어 지금 단계를 씁니다.");
                return;
            }
            if (QualitySettings.GetQualityLevel() != idx) QualitySettings.SetQualityLevel(idx, true);
        }

        void ResetCamera()
        {
            Camera.transform.SetPositionAndRotation(new Vector3(0f, Settings.eyeHeight, 0f), Quaternion.identity);
        }

        /// <summary>spec JSON(과 덮어쓰기)을 로드하고 카메라를 형상에 맞춘다. 실패하면 이전 형상은 그대로 두고 false.</summary>
        public bool Load(string json, string sourceName, SceneOverride overrides)
        {
            ResetCamera();   // 로드 순간의 머리 = 원점에서 +Z(배치 규칙이 이 자세를 기준으로 한다)
            var ov = overrides != null && overrides.IsEmpty ? null : overrides;
            bool ok = Loader.LoadJson(json, sourceName, ov);
            if (!ok) return false;
            LastFormAsset = AssetMesh != null ? Loader.ApplyFormAsset(AssetRef, AssetMesh) : null;
            SpecJson = json;
            SourceName = sourceName;
            Overrides = ov;
            _rootBaseRotation = Loader.Root != null ? Loader.Root.transform.rotation : Quaternion.identity;
            Yaw = 0f;
            Frame();
            return true;
        }

        /// <summary>지금 spec에 덮어쓰기만 바꿔 다시 로드한다(null·빈 목록 = 덮어쓰기 없음).</summary>
        public bool Reapply(SceneOverride overrides)
        {
            if (SpecJson == null) return false;
            return Load(SpecJson, SourceName, overrides);
        }

        /// <summary>카메라를 눈 위치에 두고 형상 경계 중심을 보게 한다(BatchCapture와 같은 규칙).</summary>
        public void Frame()
        {
            ResetCamera();
            if (Loader.Root == null) return;
            var rs = Loader.Root.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return;
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            var eye = Camera.transform.position;
            var to = b.center - eye;
            if (to.sqrMagnitude > 1e-8f) Camera.transform.rotation = Quaternion.LookRotation(to.normalized, Vector3.up);
        }

        /// <summary>형상을 세로축으로 돌린다(°, 미리보기 조작용 — 비교 캡처는 0).</summary>
        public void SetYaw(float degrees)
        {
            Yaw = degrees;
            if (Loader.Root == null) return;
            Loader.Root.transform.rotation = Quaternion.Euler(0f, degrees, 0f) * _rootBaseRotation;
        }

        /// <summary>절차적 움직임을 멈추고 자세를 정지 값으로 둔다(비교 캡처용). 다시 로드하면 움직임이 돌아온다.</summary>
        public void FreezeMotion()
        {
            if (Loader.Root == null) return;
            foreach (var m in Loader.Root.GetComponentsInChildren<SpecMotion>())
            {
                m.enabled = false;
                m.transform.localPosition = Vector3.zero;
                m.transform.localRotation = Quaternion.identity;
                m.transform.localScale = Vector3.one;
            }
        }

        /// <summary>width×height로 렌더해 sRGB 8비트 화소(아래 줄부터)를 돌려준다. MSAA는 품질 단계 값.</summary>
        public Color32[] Render(int width, int height, PreviewBackground background)
        {
            int msaa = Math.Max(1, QualitySettings.antiAliasing);
            var desc = new RenderTextureDescriptor(width, height, RenderTextureFormat.ARGB32, 24) { sRGB = true, msaaSamples = msaa };
            var rt = RenderTexture.GetTemporary(desc);
            rt.Create();
            RenderTexture resolved = null;
            var tex = new Texture2D(width, height, TextureFormat.RGBA32, false, false);
            var clearWas = Camera.clearFlags;
            var bgWas = Camera.backgroundColor;
            bool floorWas = Environment?.Floor != null && Environment.Floor.enabled;
            var prevActive = RenderTexture.active;
            try
            {
                if (background != PreviewBackground.Scene)
                {
                    Camera.clearFlags = CameraClearFlags.SolidColor;
                    Camera.backgroundColor = background == PreviewBackground.Black ? Color.black : Color.white;
                    if (Environment?.Floor != null) Environment.Floor.enabled = false;
                }
                Camera.targetTexture = rt;
                Camera.Render();
                Camera.targetTexture = null;
                var src = rt;
                if (rt.antiAliasing > 1)
                {
                    resolved = RenderTexture.GetTemporary(new RenderTextureDescriptor(width, height, RenderTextureFormat.ARGB32, 0) { sRGB = true });
                    // GetTemporary로 받은 텍스처를 Create하지 않고 해상하면 첫 읽기가 실제 렌더와 달랐다
                    // (2026-11-23 EditMode 진단: 160×120 전 화소, 채널 차 최대 196. 둘 다 Create한 뒤 0)
                    resolved.Create();
#if UNITY_WEBGL && !UNITY_EDITOR
                    // WebGL2에서는 ResolveAntiAliasedSurface가 아무것도 쓰지 않았다(2026-11-23 WebGL 시험: 모든 캡처가 RGBA 0).
                    // MSAA 텍스처를 원본으로 Blit하면 Unity가 해상한 뒤 복사한다. 데스크톱·에디터 경로는 그대로 둔다.
                    Graphics.Blit(rt, resolved);
#else
                    rt.ResolveAntiAliasedSurface(resolved);
#endif
                    src = resolved;
                }
                RenderTexture.active = src;
                tex.ReadPixels(new Rect(0, 0, width, height), 0, 0, false);
                tex.Apply(false);
                return tex.GetPixels32();
            }
            finally
            {
                RenderTexture.active = prevActive;
                Camera.targetTexture = null;
                Camera.clearFlags = clearWas;
                Camera.backgroundColor = bgWas;
                if (Environment?.Floor != null) Environment.Floor.enabled = floorWas;
                RenderTexture.ReleaseTemporary(rt);
                if (resolved != null) RenderTexture.ReleaseTemporary(resolved);
                DestroySafe(tex);
            }
        }

        /// <summary>Render 결과를 PNG 바이트로.</summary>
        public byte[] RenderPng(int width, int height, PreviewBackground background)
        {
            var px = Render(width, height, background);
            var tex = new Texture2D(width, height, TextureFormat.RGBA32, false, false);
            try
            {
                tex.SetPixels32(px);
                tex.Apply(false);
                return tex.EncodeToPNG();
            }
            finally { DestroySafe(tex); }
        }

        public void Dispose()
        {
            if (Loader != null) Loader.Unload();
            DestroySafe(_loaderGo);
            DestroySafe(_camGo);
            Environment?.Dispose();
            Environment = null;
            Loader = null;
            Camera = null;
            _loaderGo = _camGo = null;
        }

        static void DestroySafe(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) UnityEngine.Object.Destroy(o);
            else UnityEngine.Object.DestroyImmediate(o);
        }
    }
}
