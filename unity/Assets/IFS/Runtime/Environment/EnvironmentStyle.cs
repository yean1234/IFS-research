// 배치 공간 후보 B·E·F(docs/decisions.md G52–G55, 2026-11-24)의 배경 공간. 중립 환경(EnvironmentBuilder)을 만든 뒤 하늘만 바꾸고
// (자연이면 발밑 땅을 더한다), 조명·앰비언트·그림자는 그대로 둔다 — 세 공간에서 형상이 같은 빛을 받게(색 지각 비교의 공정성).
//   neutral : 아무것도 하지 않는다(기본값 — G52 전과 같은 화면).
//   space   : 별 하늘 셰이더(IFS/EnvironmentStarfield, 규칙 starfield/1, 에셋 없음 — G54). 원형 배치 바닥은 우주에 뜬 발판으로 남는다.
//   nature  : CC0 360° 사진(Resources/IFS/Nature, NatureSkyAsset) + 등장방형 하늘 셰이더(IFS/EnvironmentPanorama)
//             + 발밑 땅 원판(IFS/EnvironmentGround, 반지름 60 m, 20 m부터 사진으로 녹아듦 — G55).
// 둘 다 중립 환경의 200 m 격자 바닥을 숨긴다(배치 러너는 원래 숨긴다). 하늘이 바뀌면 반사 큐브맵을 한 번 다시 찍는다.
// 셰이더는 모두 Resources 안에 있어 빌드에 항상 들어간다(Shader.Find로 찾는 내장 셰이더를 쓰지 않음).
using System.Collections.Generic;
using UnityEngine;

namespace IFS.SceneSpec
{
    /// <summary>자연 공간(F)의 360° 사진 출처(UnityEngine 무의존 — manifest·테스트가 읽는다). 바꾸면 LICENSE.txt·unity/README.md도 같이.</summary>
    public static class NatureSkyAsset
    {
        public const string AssetId = "farmland_overcast";
        public const string Title = "Farmland Overcast";
        public const string Author = "Grzegorz Wronkowski";
        public const string SourcePage = "https://polyhaven.com/a/farmland_overcast";
        public const string DownloadUrl = "https://dl.polyhaven.org/file/ph-assets/HDRIs/extra/Tonemapped%20JPG/farmland_overcast.jpg";
        public const string License = "CC0-1.0";
        public const string DownloadedOn = "2026-11-24";
        /// <summary>내려받은 원본(8192 × 4096 tonemapped JPG)의 sha256.</summary>
        public const string OriginalSha256 = "47171b0f7572b10d42e6c508e9a2913a40ace47042ec5336a167e4fce912101a";
        /// <summary>저장소에 넣은 파일(4096 × 2048로 줄인 JPG)의 이름·sha256. 테스트가 파일과 대조한다.</summary>
        public const string FileName = "farmland_overcast_4k.jpg";
        public const string Sha256 = "6cae5ca0bd967a67c542381710ff1d285656ce5234ee3a291f417f35533797c1";
        public const int Width = 4096, Height = 2048;
        /// <summary>Resources.Load 경로(확장자 없음).</summary>
        public const string ResourcePath = "IFS/Nature/farmland_overcast_4k";
        /// <summary>Assets 폴더 기준 경로.</summary>
        public const string AssetRelativePath = "IFS/Runtime/Resources/IFS/Nature/" + FileName;
        /// <summary>사진 지평선 바로 아래 땅 띠(높이 50.5–53%)의 선형 평균을 sRGB로(발밑 땅 원판 색).</summary>
        public static readonly double[] GroundSrgb = { 0.32, 0.34, 0.25 };
        /// <summary>하늘 회전(도, Y축). 0 = 사진 가운데가 정면(+z).</summary>
        public const double RotationDeg = 0;
    }

    /// <summary>배경 공간 이름·설정값(UnityEngine 무의존 부분).</summary>
    public static class EnvironmentStyleInfo
    {
        public const string Neutral = "neutral";
        public const string Space = "space";
        public const string Nature = "nature";
        public const string StarfieldShaderResource = "IFS/EnvironmentStarfield";
        public const string PanoramaShaderResource = "IFS/EnvironmentPanorama";
        public const string GroundShaderResource = "IFS/EnvironmentGround";
        /// <summary>별 하늘 규칙 이름(셰이더를 바꾸면 올린다).</summary>
        public const string StarfieldRule = "starfield/1";
        public const double StarfieldSeed = 0;
        public static readonly double[] StarBackgroundSrgb = { 0.045, 0.055, 0.12 };
        public static readonly double[] NebulaSrgb = { 0.12, 0.11, 0.21 };
        public const double NebulaStrength = 0.55;
        public const double StarScale = 90;
        public const double StarDensity = 0.10;
        public const double StarBrightness = 1.6;
        public const double GroundRadiusM = 60, GroundFadeStartM = 20, GroundNoiseStrength = 0.16;
        public const double GroundY = -0.02;
    }

    /// <summary>EnvironmentHandle에 얹은 배경 공간(공간을 바꾸거나 Dispose하면 지운다).</summary>
    internal sealed class EnvironmentStyleState
    {
        public readonly List<Object> Owned = new List<Object>();
        public GameObject Ground;
        public Material Sky;
        public bool FloorWasEnabled = true;
    }

    public static class EnvironmentStyle
    {
        public const string GroundName = "nature ground (G55)";

        /// <summary>배경 공간을 바꾼다. 같은 공간이면 아무것도 하지 않는다(neutral → neutral은 기존 화면 그대로).
        /// 셰이더·사진을 쓸 수 없으면 경고를 남기고 false(중립 하늘로 둠).</summary>
        public static bool Apply(EnvironmentHandle h, string style)
        {
            if (h == null || h.Root == null) return false;
            style = string.IsNullOrEmpty(style) ? EnvironmentStyleInfo.Neutral : style;
            if (h.Style == style) return true;
            Clear(h);
            bool ok = true;
            if (style == EnvironmentStyleInfo.Space) ok = BuildSpace(h);
            else if (style == EnvironmentStyleInfo.Nature) ok = BuildNature(h);
            else if (style != EnvironmentStyleInfo.Neutral)
            {
                Debug.LogWarning("[Environment] 모르는 공간 " + style + " → 중립");
                ok = false;
            }
            if (!ok) Clear(h);
            h.Style = ok ? style : EnvironmentStyleInfo.Neutral;
            if (h.Settings != null && h.Settings.reflections) EnvironmentBuilder.RenderReflection(h);
            return ok;
        }

        /// <summary>얹은 배경 공간을 지우고 중립 하늘·격자 바닥 상태로 되돌린다.</summary>
        internal static void Clear(EnvironmentHandle h)
        {
            var st = h.StyleState;
            if (st == null) return;
            if (RenderSettings.skybox == st.Sky) RenderSettings.skybox = h.SkyMaterial;
            if (h.Floor != null) h.Floor.enabled = st.FloorWasEnabled;
            EnvironmentBuilder.DestroySafe(st.Ground);
            foreach (var o in st.Owned) EnvironmentBuilder.DestroySafe(o);
            h.StyleState = null;
            h.Style = EnvironmentStyleInfo.Neutral;
        }

        static EnvironmentStyleState Begin(EnvironmentHandle h)
        {
            var st = new EnvironmentStyleState { FloorWasEnabled = h.Floor == null || h.Floor.enabled };
            if (h.Floor != null) h.Floor.enabled = false;   // 중립 격자 바닥(200 m)을 숨긴다
            h.StyleState = st;
            return st;
        }

        static Color Srgb(double[] c) => new Color((float)c[0], (float)c[1], (float)c[2], 1f);

        static Shader LoadShader(string resource)
        {
            var s = Resources.Load<Shader>(resource);
            if (s == null || !s.isSupported)
            {
                Debug.LogWarning($"[Environment] {resource} 셰이더를 쓸 수 없습니다 → 중립 하늘");
                return null;
            }
            return s;
        }

        static bool BuildSpace(EnvironmentHandle h)
        {
            var shader = LoadShader(EnvironmentStyleInfo.StarfieldShaderResource);
            if (shader == null) return false;
            var st = Begin(h);
            var m = new Material(shader) { name = "IFS Starfield Sky (G54)" };
            m.SetColor("_BackgroundColor", Srgb(EnvironmentStyleInfo.StarBackgroundSrgb));
            m.SetColor("_NebulaColor", Srgb(EnvironmentStyleInfo.NebulaSrgb));
            m.SetFloat("_NebulaStrength", (float)EnvironmentStyleInfo.NebulaStrength);
            m.SetFloat("_StarScale", (float)EnvironmentStyleInfo.StarScale);
            m.SetFloat("_StarDensity", (float)EnvironmentStyleInfo.StarDensity);
            m.SetFloat("_StarBrightness", (float)EnvironmentStyleInfo.StarBrightness);
            m.SetFloat("_Seed", (float)EnvironmentStyleInfo.StarfieldSeed);
            st.Owned.Add(m);
            st.Sky = m;
            RenderSettings.skybox = m;
            return true;
        }

        static bool BuildNature(EnvironmentHandle h)
        {
            var sky = LoadShader(EnvironmentStyleInfo.PanoramaShaderResource);
            var groundShader = LoadShader(EnvironmentStyleInfo.GroundShaderResource);
            var tex = Resources.Load<Texture2D>(NatureSkyAsset.ResourcePath);
            if (tex == null) Debug.LogWarning("[Environment] 자연 사진(Resources/" + NatureSkyAsset.ResourcePath + ")이 없습니다 → 중립 하늘");
            if (sky == null || groundShader == null || tex == null) return false;
            var st = Begin(h);
            var m = new Material(sky) { name = "IFS Nature Sky (G55, " + NatureSkyAsset.AssetId + ")" };
            m.SetTexture("_MainTex", tex);
            m.SetFloat("_Rotation", (float)NatureSkyAsset.RotationDeg);
            m.SetFloat("_Exposure", 1f);
            st.Owned.Add(m);
            st.Sky = m;
            RenderSettings.skybox = m;

            var g = GameObject.CreatePrimitive(PrimitiveType.Quad);
            g.name = GroundName;
            g.transform.SetParent(h.Root.transform, false);
            g.transform.localPosition = new Vector3(0f, (float)EnvironmentStyleInfo.GroundY, 0f);
            var col = g.GetComponent<Collider>();
            if (col != null) EnvironmentBuilder.DestroySafe(col);
            var mesh = DiscMesh((float)EnvironmentStyleInfo.GroundRadiusM, 96);
            st.Owned.Add(mesh);
            g.GetComponent<MeshFilter>().sharedMesh = mesh;
            var gm = new Material(groundShader) { name = "IFS Nature Ground (G55)" };
            gm.SetColor("_BaseColor", Srgb(NatureSkyAsset.GroundSrgb));
            gm.SetFloat("_NoiseStrength", (float)EnvironmentStyleInfo.GroundNoiseStrength);
            gm.SetFloat("_FadeStart", (float)EnvironmentStyleInfo.GroundFadeStartM);
            gm.SetFloat("_FadeEnd", (float)EnvironmentStyleInfo.GroundRadiusM);
            st.Owned.Add(gm);
            var rend = g.GetComponent<MeshRenderer>();
            rend.sharedMaterial = gm;
            rend.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
            rend.receiveShadows = false;
            st.Ground = g;
            return true;
        }

        /// <summary>윗면(+y)이 앞면인 원판 메시(중심 + 둘레 segments개).</summary>
        public static Mesh DiscMesh(float radius, int segments)
        {
            var v = new Vector3[segments + 1];
            var n = new Vector3[segments + 1];
            var tri = new int[segments * 3];
            v[0] = Vector3.zero;
            n[0] = Vector3.up;
            for (int i = 0; i < segments; i++)
            {
                float a = 2f * Mathf.PI * i / segments;
                v[i + 1] = new Vector3(Mathf.Sin(a) * radius, 0f, Mathf.Cos(a) * radius);
                n[i + 1] = Vector3.up;
                int j = (i + 1) % segments;
                tri[3 * i] = 0; tri[3 * i + 1] = i + 1; tri[3 * i + 2] = j + 1;   // 위에서 볼 때 시계 방향(Unity 앞면)
            }
            var mesh = new Mesh { name = "disc" };
            mesh.vertices = v;
            mesh.normals = n;
            mesh.triangles = tri;
            mesh.RecalculateBounds();
            return mesh;
        }
    }
}
