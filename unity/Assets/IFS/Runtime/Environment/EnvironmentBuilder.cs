// 런타임 환경: 바이너리 에셋 없이 코드로 만든다(바닥 + 1 m 격자, 절차 하늘, 그라디언트 앰비언트, 방향광 1개, 반사 1회).
// 목표는 "현실감"과 "색 정확도(일치도 평가의 공정성)" 사이의 균형이다.
//   - 무채색 환경: 바닥·하늘·앰비언트 모두 채도 ≤ 0.08(HSV, 하늘 천정만 아주 옅게 푸름). 형상의 색 지각을 주변 색이 끌어가지 않게.
//   - 백색광: 방향광은 (1, 1, 1) = sRGB 백색점(D65). 색온도를 따로 주지 않는다.
//   - 그림자: 방향광 하나만 소프트 섀도. 접지감(형상이 어디에 떠 있는지)을 주는 가장 싼 단서다.
//   - 반사: 환경만 큐브맵으로 한 번 렌더해 기본 반사로 쓴다. 매 프레임 갱신하지 않는다(VR 비용).
//   - 안개·후처리 없음: 형상 색을 바꾸지 않도록. 먼 바닥은 바닥 셰이더가 지평선 색으로 녹인다.
// 형상(SceneLoader)보다 먼저 만든다 — 반사 큐브맵에 형상이 들어가지 않도록.
using System;
using UnityEngine;
using UnityEngine.Rendering;

namespace IFS.SceneSpec
{
    [Serializable]
    public sealed class EnvironmentSettings
    {
        [Header("바닥")]
        [Tooltip("바닥 한 변(m)")] public float floorSize = 200f;
        public Color floorColor = new Color(0.46f, 0.46f, 0.46f, 1f);
        public Color gridMajorColor = new Color(0.39f, 0.39f, 0.39f, 1f);
        public Color gridMinorColor = new Color(0.43f, 0.43f, 0.43f, 1f);
        [Tooltip("격자선 굵기(m)")] public float gridLineWidth = 0.012f;
        [Tooltip("격자가 사라지는 거리(m)")] public float gridFadeDistance = 14f;
        [Range(0f, 1f)] public float floorSmoothness = 0.12f;

        [Header("하늘")]
        public Color skyZenith = new Color(0.60f, 0.62f, 0.65f, 1f);
        public Color skyHorizon = new Color(0.74f, 0.74f, 0.75f, 1f);
        public Color skyGround = new Color(0.42f, 0.42f, 0.42f, 1f);

        [Header("앰비언트(삼색 그라디언트)")]
        public Color ambientSky = new Color(0.56f, 0.57f, 0.59f, 1f);
        public Color ambientEquator = new Color(0.50f, 0.50f, 0.50f, 1f);
        public Color ambientGround = new Color(0.34f, 0.34f, 0.34f, 1f);

        [Header("방향광")]
        public Color lightColor = Color.white;
        public float lightIntensity = 1.0f;
        [Tooltip("고도각(도). 90 = 바로 위")] public float lightElevation = 50f;
        [Tooltip("방위각(도). 0 = 참여자 뒤에서 앞(+Z)으로")] public float lightAzimuth = 30f;
        [Range(0f, 1f)] public float shadowStrength = 0.7f;
        public bool softShadows = true;

        [Header("반사")]
        public bool reflections = true;
        [Tooltip("반사 큐브맵 한 면 해상도")] public int reflectionResolution = 128;
        [Tooltip("반사 큐브맵을 찍는 위치(m)")] public Vector3 reflectionCapturePosition = new Vector3(0f, 1.2f, 0f);
    }

    /// <summary>만든 환경 객체 묶음. Dispose로 정리한다.</summary>
    public sealed class EnvironmentHandle : IDisposable
    {
        public GameObject Root;
        public Light KeyLight;
        public Renderer Floor;
        public Material FloorMaterial;
        public Material SkyMaterial;
        public RenderTexture ReflectionCube;
        public EnvironmentSettings Settings;

        // Build 직전의 전역 RenderSettings. Dispose에서 되돌린다(에디터에서 테스트를 돌려도 열린 씬 조명이 바뀌지 않게).
        internal RenderSettingsSnapshot Previous;

        /// <summary>환경만 보이는 상태에서 반사 큐브맵을 다시 찍는다(로드 때 1회).</summary>
        public void RefreshReflections() => EnvironmentBuilder.RenderReflection(this);

        public void Dispose()
        {
            if (Previous != null)
            {
                Previous.Restore();
                Previous = null;
            }
            else if (RenderSettings.customReflectionTexture == ReflectionCube) RenderSettings.customReflectionTexture = null;
            EnvironmentBuilder.DestroySafe(Root);
            EnvironmentBuilder.DestroySafe(FloorMaterial);
            EnvironmentBuilder.DestroySafe(SkyMaterial);
            if (ReflectionCube != null) ReflectionCube.Release();
            EnvironmentBuilder.DestroySafe(ReflectionCube);
            Root = null;
            KeyLight = null;
            Floor = null;
            FloorMaterial = SkyMaterial = null;
            ReflectionCube = null;
        }
    }

    /// <summary>EnvironmentBuilder.Build가 바꾸는 전역 RenderSettings 값만 저장·복원한다.</summary>
    internal sealed class RenderSettingsSnapshot
    {
        Material _skybox;
        AmbientMode _ambientMode;
        Color _ambientSky, _ambientEquator, _ambientGround, _ambientLight;
        float _ambientIntensity;
        SphericalHarmonicsL2 _ambientProbe;
        bool _fog;
        Light _sun;
        DefaultReflectionMode _reflectionMode;
        Texture _customReflection;
        float _reflectionIntensity;

        public static RenderSettingsSnapshot Capture() => new RenderSettingsSnapshot
        {
            _skybox = RenderSettings.skybox,
            _ambientMode = RenderSettings.ambientMode,
            _ambientSky = RenderSettings.ambientSkyColor,
            _ambientEquator = RenderSettings.ambientEquatorColor,
            _ambientGround = RenderSettings.ambientGroundColor,
            _ambientLight = RenderSettings.ambientLight,
            _ambientIntensity = RenderSettings.ambientIntensity,
            _ambientProbe = RenderSettings.ambientProbe,
            _fog = RenderSettings.fog,
            _sun = RenderSettings.sun,
            _reflectionMode = RenderSettings.defaultReflectionMode,
            _customReflection = RenderSettings.customReflectionTexture,
            _reflectionIntensity = RenderSettings.reflectionIntensity,
        };

        public void Restore()
        {
            RenderSettings.skybox = _skybox;
            RenderSettings.ambientMode = _ambientMode;
            RenderSettings.ambientSkyColor = _ambientSky;
            RenderSettings.ambientEquatorColor = _ambientEquator;
            RenderSettings.ambientGroundColor = _ambientGround;
            RenderSettings.ambientLight = _ambientLight;
            RenderSettings.ambientIntensity = _ambientIntensity;
            RenderSettings.fog = _fog;
            RenderSettings.sun = _sun;
            RenderSettings.defaultReflectionMode = _reflectionMode;
            RenderSettings.customReflectionTexture = _customReflection;
            RenderSettings.reflectionIntensity = _reflectionIntensity;
            RenderSettings.ambientProbe = _ambientProbe;
        }
    }

    public static class EnvironmentBuilder
    {
        public const string RootName = "IFS Environment";
        public const string FloorShaderResource = "IFS/EnvironmentFloor";
        public const string SkyShaderResource = "IFS/EnvironmentSky";

        public static EnvironmentHandle Build(EnvironmentSettings s = null, Transform parent = null)
        {
            s ??= new EnvironmentSettings();
            var h = new EnvironmentHandle { Settings = s, Previous = RenderSettingsSnapshot.Capture() };
            h.Root = new GameObject(RootName);
            if (parent != null) h.Root.transform.SetParent(parent, false);

            BuildFloor(h, s);
            BuildSky(h, s);
            BuildAmbient(s);
            BuildLight(h, s);
            RenderSettings.fog = false;
            if (s.reflections) RenderReflection(h);
            else RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
            return h;
        }

        static void BuildFloor(EnvironmentHandle h, EnvironmentSettings s)
        {
            var shader = Resources.Load<Shader>(FloorShaderResource);
            var floor = GameObject.CreatePrimitive(PrimitiveType.Plane);   // 10 m × 10 m, 삼각형 200개
            floor.name = "floor (1 m grid)";
            floor.transform.SetParent(h.Root.transform, false);
            floor.transform.localScale = new Vector3(s.floorSize / 10f, 1f, s.floorSize / 10f);
            var rend = floor.GetComponent<MeshRenderer>();
            if (shader != null && shader.isSupported)
            {
                var m = new Material(shader) { name = "IFS Floor" };
                m.SetColor("_BaseColor", s.floorColor);
                m.SetColor("_LineColor", s.gridMajorColor);
                m.SetColor("_MinorLineColor", s.gridMinorColor);
                m.SetFloat("_LineWidth", s.gridLineWidth);
                m.SetFloat("_GridFadeDistance", s.gridFadeDistance);
                m.SetColor("_HorizonColor", s.skyHorizon);
                m.SetFloat("_HorizonFadeStart", Mathf.Min(18f, s.floorSize * 0.09f));
                m.SetFloat("_HorizonFadeEnd", s.floorSize * 0.4f);
                m.SetFloat("_Smoothness", s.floorSmoothness);
                h.FloorMaterial = m;
                rend.sharedMaterial = m;
            }
            else
            {
                Debug.LogWarning($"[Environment] {FloorShaderResource} 셰이더를 쓸 수 없어 기본 머티리얼로 바닥을 그립니다(격자 없음).");
            }
            rend.shadowCastingMode = ShadowCastingMode.Off;
            rend.receiveShadows = true;
            h.Floor = rend;
        }

        static void BuildSky(EnvironmentHandle h, EnvironmentSettings s)
        {
            var shader = Resources.Load<Shader>(SkyShaderResource);
            if (shader == null || !shader.isSupported)
            {
                Debug.LogWarning($"[Environment] {SkyShaderResource} 셰이더를 쓸 수 없어 단색 배경을 씁니다.");
                RenderSettings.skybox = null;
                return;
            }
            var m = new Material(shader) { name = "IFS Sky" };
            m.SetColor("_ZenithColor", s.skyZenith);
            m.SetColor("_HorizonColor", s.skyHorizon);
            m.SetColor("_GroundColor", s.skyGround);
            h.SkyMaterial = m;
            RenderSettings.skybox = m;
        }

        static void BuildAmbient(EnvironmentSettings s)
        {
            RenderSettings.ambientMode = AmbientMode.Trilight;
            RenderSettings.ambientSkyColor = s.ambientSky;
            RenderSettings.ambientEquatorColor = s.ambientEquator;
            RenderSettings.ambientGroundColor = s.ambientGround;
            RenderSettings.ambientIntensity = 1f;
            DynamicGI.UpdateEnvironment();
        }

        static void BuildLight(EnvironmentHandle h, EnvironmentSettings s)
        {
            var go = new GameObject("key light (directional)");
            go.transform.SetParent(h.Root.transform, false);
            go.transform.rotation = Quaternion.Euler(s.lightElevation, s.lightAzimuth, 0f);
            var light = go.AddComponent<Light>();
            light.type = LightType.Directional;
            light.color = s.lightColor;
            light.intensity = s.lightIntensity;
            light.shadows = s.softShadows ? LightShadows.Soft : LightShadows.Hard;
            light.shadowStrength = s.shadowStrength;
            light.renderMode = LightRenderMode.ForcePixel;
            h.KeyLight = light;
            RenderSettings.sun = light;
        }

        /// <summary>환경을 큐브맵 RenderTexture로 한 번 렌더해 기본 반사로 쓴다(밉맵 = 거친 면의 흐린 반사).</summary>
        internal static void RenderReflection(EnvironmentHandle h)
        {
            var s = h.Settings;
            if (h.ReflectionCube == null)
            {
                h.ReflectionCube = new RenderTexture(s.reflectionResolution, s.reflectionResolution, 16, RenderTextureFormat.ARGB32)
                {
                    name = "IFS Environment Reflection",
                    dimension = TextureDimension.Cube,
                    useMipMap = true,
                    autoGenerateMips = true,
                };
                h.ReflectionCube.Create();
            }
            var camGo = new GameObject("reflection capture (temporary)");
            try
            {
                camGo.transform.position = s.reflectionCapturePosition;
                var cam = camGo.AddComponent<Camera>();
                cam.enabled = false;
                cam.clearFlags = RenderSettings.skybox != null ? CameraClearFlags.Skybox : CameraClearFlags.SolidColor;
                cam.backgroundColor = s.skyHorizon;
                cam.nearClipPlane = 0.05f;
                cam.farClipPlane = 500f;
                cam.allowMSAA = false;
                cam.allowHDR = false;
                if (!cam.RenderToCubemap(h.ReflectionCube, 63))
                {
                    Debug.LogWarning("[Environment] 반사 큐브맵을 렌더하지 못했습니다 → 하늘 반사로 대체");
                    RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;
                    return;
                }
            }
            finally
            {
                DestroySafe(camGo);
            }
            RenderSettings.defaultReflectionMode = DefaultReflectionMode.Custom;
            RenderSettings.customReflectionTexture = h.ReflectionCube;
            RenderSettings.reflectionIntensity = 1f;
        }

        internal static void DestroySafe(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) UnityEngine.Object.Destroy(o);
            else UnityEngine.Object.DestroyImmediate(o);
        }
    }
}
