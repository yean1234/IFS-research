// EditMode 테스트(Unity 전용): (2.3, G61 ①) SceneLoader가 스펙 2.3.0을 읽고 그리는가.
//   1) 2.2 문서와 세 값이 모두 null인 2.3 문서는 같은 로드 결과(해석값·defaultsUsed·notes·계층·메시·머티리얼 프로퍼티·키워드·움직임)와
//      같은 initialScene.json(specVersion, 원문의 세 키, 2.3 전용 contour·emission 키만 다름) — golden 지문 대상 spec 8개 각각
//   2) 발광 null·none이면 2.2와 화소가 같다(같은 카메라·환경 렌더의 RGBA 바이트 비교). glowing이면 달라진다
//   3) 둥긂 → 슈퍼쿼드릭 메시(정점 1,106, 정점 변위·굴곡 0), 길쭉함 → 국소 배율, 기록의 contour·emission·defaultsUsed
// spec은 golden 지문의 합성 spec과 합성 값(참여자 데이터 아님).
using System;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class ContourLoaderTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-contour-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        /// <summary>2.0·2.1 spec을 같은 내용의 2.2(form.base·baseVariant null) 또는 2.3(+ 세 키 null 또는 값) 문서로.</summary>
        static JObject As(JObject src, string version, string roundness = null, string aspect = null, string emission = null)
        {
            var o = (JObject)src.DeepClone();
            o["meta"]["specVersion"] = version;
            var form = (JObject)o["form"];
            if (!form.ContainsKey("base")) { form["base"] = null; form["baseVariant"] = null; }
            if (version == "2.3.0")
            {
                form["roundness"] = roundness;
                form["aspect"] = aspect;
                o["material"]["emission"] = emission;
                void P(string path, string trigger) => o["_provenance"][path] = new JArray(new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = trigger, ["charSpan"] = new JArray(0, trigger.Length), ["rule"] = "synthetic." + trigger,
                });
                if (roundness != null) P("form.roundness", "각진");
                if (aspect != null) P("form.aspect", "길쭉");
                if (emission != null) P("material.emission", "빛나");
            }
            return o;
        }

        /// <summary>sub 폴더에 name.json으로 쓴다(notes에 파일 이름이 들어가므로 비교할 두 문서는 같은 이름, 다른 폴더).</summary>
        string Write(string name, JObject o, string sub = "")
        {
            string dir = Path.Combine(_tmp, sub);
            Directory.CreateDirectory(dir);
            string p = Path.Combine(dir, name + ".json");
            File.WriteAllText(p, o.ToString(Formatting.Indented).Replace("\r\n", "\n"), new UTF8Encoding(false));
            return p;
        }

        /// <summary>새 씬·새 로더(기록 켬)로 로드하고 지문(golden과 같은 Describe + 기록)을 돌려준다.</summary>
        static string Fingerprint(string path, string recordRoot)
        {
            var loader = LoaderNoVariantGoldenTests.NewLoader(recordRoot, out var go);
            try
            {
                var sb = new StringBuilder();
                Assert.That(loader.Load(path), Is.True, path);
                LoaderNoVariantGoldenTests.Describe(loader, sb);
                loader.Unload();
                LoaderNoVariantGoldenTests.DescribeRecords(recordRoot, sb);
                return sb.ToString();
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        /// <summary>initialScene 줄에서 2.3만의 차이(specVersion, 원문의 세 키, contour·emission)를 지운다. 다른 줄은 그대로.</summary>
        static string Normalize(string fingerprint)
        {
            var lines = fingerprint.Split('\n');
            for (int i = 0; i < lines.Length; i++)
            {
                const string tag = "initialScene: ";
                if (!lines[i].StartsWith(tag, StringComparison.Ordinal)) continue;
                var o = JObject.Parse(lines[i].Substring(tag.Length));
                o["specVersion"] = "X";
                o.Remove("contour");
                o.Remove("emission");
                o["spec"]["meta"]["specVersion"] = "X";
                ((JObject)o["spec"]["form"]).Remove("roundness");
                ((JObject)o["spec"]["form"]).Remove("aspect");
                ((JObject)o["spec"]["material"]).Remove("emission");
                lines[i] = tag + o.ToString(Formatting.None);
            }
            return string.Join("\n", lines);
        }

        [Test]
        public void All_null_23_documents_load_exactly_like_22()
        {
            int i = 0;
            foreach (var (name, path) in LoaderNoVariantGoldenTests.FingerprintSpecs(_tmp))
            {
                var src = JObject.Parse(File.ReadAllText(path));
                string p22 = Write(name, As(src, "2.2.0"), "v22");
                string p23 = Write(name, As(src, "2.3.0"), "v23");
                string f22 = Fingerprint(p22, Path.Combine(_tmp, "rec" + i++));
                string f23 = Fingerprint(p23, Path.Combine(_tmp, "rec" + i++));
                Assert.That(f23, Does.Contain("\"contour\":{\"status\":\"none\""), name + ": 2.3 기록에는 contour가 있다");
                Assert.That(f22, Does.Not.Contain("\"contour\""), name + ": 2.2 기록에는 contour가 없다");
                Assert.That(Normalize(f23), Is.EqualTo(Normalize(f22)), name);
            }
        }

        // ── 화소 ──────────────────────────────────────────────────────────
        static byte[] Render(string path, out string renderPath)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var env = EnvironmentBuilder.Build(new EnvironmentSettings());
            var camGo = new GameObject("eye");
            var cam = camGo.AddComponent<Camera>();
            cam.enabled = false;
            cam.fieldOfView = 40f;
            cam.allowMSAA = false;
            cam.allowHDR = false;
            camGo.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), Quaternion.identity);
            var loaderGo = new GameObject("loader");
            var loader = loaderGo.AddComponent<SceneLoader>();
            var so = new SerializedObject(loader);
            so.FindProperty("record").boolValue = false;
            so.FindProperty("loadOnStart").boolValue = false;
            so.FindProperty("head").objectReferenceValue = camGo.transform;
            so.ApplyModifiedPropertiesWithoutUndo();
            const int w = 192, h = 192;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false, false);
            var prev = RenderTexture.active;
            try
            {
                Assert.That(loader.Load(path), Is.True);
                renderPath = loader.RenderPath;
                var b = loader.Root.GetComponentsInChildren<Renderer>()[0].bounds;
                camGo.transform.rotation = Quaternion.LookRotation((b.center - camGo.transform.position).normalized, Vector3.up);
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                tex.Apply(false);
                return tex.GetRawTextureData();
            }
            finally
            {
                RenderTexture.active = prev;
                cam.targetTexture = null;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(tex);
                UnityEngine.Object.DestroyImmediate(loaderGo);
                UnityEngine.Object.DestroyImmediate(camGo);
                env.Dispose();
            }
        }

        [Test]
        public void Emission_null_or_none_keeps_22_pixels()
        {
            var specs = LoaderNoVariantGoldenTests.FingerprintSpecs(_tmp);
            foreach (var name in new[] { "EX02", "GOLD-mist", "GOLD-fragments", "GOLD-square" })
            {
                var src = JObject.Parse(File.ReadAllText(specs.First(s => s.name == name).path));
                var px22 = Render(Write(name, As(src, "2.2.0"), "p22"), out var rp22);
                var pxNull = Render(Write(name, As(src, "2.3.0"), "p23null"), out var rpNull);
                var pxNone = Render(Write(name, As(src, "2.3.0", emission: "none"), "p23none"), out _);
                var pxGlow = Render(Write(name, As(src, "2.3.0", emission: "glowing"), "p23glow"), out _);
                Assert.That(rpNull, Is.EqualTo(rp22), name);
                Assert.That(pxNull, Is.EqualTo(px22), name + ": 세 값 null");
                Assert.That(pxNone, Is.EqualTo(px22), name + ": emission none");
                int diff = 0;
                for (int k = 0; k < px22.Length; k++) if (pxGlow[k] != px22[k]) diff++;
                Assert.That(diff, Is.GreaterThan(0), name + ": glowing이면 화소가 달라진다");
            }
        }

        // ── 형상·기록 ─────────────────────────────────────────────────────
        static JObject Ex02 => JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX02.json")));

        [Test]
        public void Roundness_draws_the_superquadric_and_records_contour()
        {
            string root = Path.Combine(_tmp, "rec");
            string p = Write("angular", As(Ex02, "2.3.0", roundness: "angular", emission: "glowing"));
            var loader = LoaderNoVariantGoldenTests.NewLoader(root, out var go);
            try
            {
                Assert.That(loader.Load(p), Is.True);
                Assert.That(loader.RenderPath, Is.EqualTo("superquadric"));
                var mf = loader.Root.GetComponentInChildren<MeshFilter>();
                Assert.That(mf.sharedMesh.vertexCount, Is.EqualTo(1106));
                Assert.That(mf.sharedMesh.bounds.size.x, Is.EqualTo(1f).Within(1e-4f));
                var m = loader.Root.GetComponentInChildren<Renderer>().sharedMaterial;
                Assert.That(m.GetFloat("_Displacement"), Is.EqualTo(0f));
                Assert.That(m.GetFloat("_Lumpiness"), Is.EqualTo(0f));
                Assert.That(loader.RenderPlan.EmissionSrgb(out float r, out float g, out float b), Is.True);
                var e = m.GetColor(FormRenderResources.EmissionProperty);
                Assert.That(e.r, Is.EqualTo(r).Within(2e-3f));
                Assert.That(e.g, Is.EqualTo(g).Within(2e-3f));
                Assert.That(e.b, Is.EqualTo(b).Within(2e-3f));
                Assert.That(r, Is.GreaterThan(0.1f), "glowing → 바탕색 × 1");
                Assert.That(loader.InitialParams.DefaultsUsed, Has.Member("form.aspect"));
                Assert.That(loader.InitialParams.DefaultsUsed, Has.No.Member("form.aspect.axis"));
                loader.Unload();
                var init = JObject.Parse(File.ReadAllText(Directory.GetFiles(root, "initialScene.json", SearchOption.AllDirectories).Single()));
                Assert.That(init["contour"]["status"].ToString(), Is.EqualTo("applied"));
                Assert.That(init["contour"]["mesh"].ToString(), Is.EqualTo("superquadric/1"));
                Assert.That((double)init["contour"]["e1"], Is.EqualTo(0.1));
                Assert.That(init["contour"]["axisRatios"].Type, Is.EqualTo(JTokenType.Null));
                Assert.That(init["emission"]["level"].ToString(), Is.EqualTo("glowing"));
                Assert.That((double)init["emission"]["intensity"], Is.EqualTo(1.0));
                Assert.That(init["emission"]["colorSource"].ToString(), Is.EqualTo("default"));
                Assert.That(init["defaultsUsed"].Values<string>(), Has.Member("form.aspect"));
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Aspect_scales_the_model_and_records_the_default_axis()
        {
            var loader22 = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "a"), out var go22);
            Vector3 s22;
            try
            {
                Assert.That(loader22.Load(Write("plain", As(Ex02, "2.2.0"))), Is.True);
                s22 = loader22.Root.GetComponentInChildren<MeshFilter>().transform.localScale;
            }
            finally { loader22.Unload(); UnityEngine.Object.DestroyImmediate(go22); }
            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "b"), out var go);
            try
            {
                Assert.That(loader.Load(Write("elongated", As(Ex02, "2.3.0", aspect: "elongated"))), Is.True);
                Assert.That(loader.RenderPath, Is.EqualTo("blob"), "둥긂을 말하지 않음 → 기본 덩어리 메시 그대로");
                var s = loader.Root.GetComponentInChildren<MeshFilter>().transform.localScale;
                Assert.That(s.x, Is.EqualTo(s22.x * 0.5f).Within(1e-6f));
                Assert.That(s.y, Is.EqualTo(s22.y).Within(1e-6f), "긴 축(세로) = 1");
                Assert.That(s.z, Is.EqualTo(s22.z * 0.5f).Within(1e-6f));
                Assert.That(loader.InitialParams.DefaultsUsed, Has.Member("form.roundness").And.Member("form.aspect.axis"));
                Assert.That(loader.Notes, Has.Some.Contains("form.aspect.axis"));
                // 조절로 형태를 바꾸면 축 배율을 곱하지 않는다(not_applied_form), 돌아오면 다시
                Assert.That(loader.SetCategory("form.type", "mist"), Is.True);
                Assert.That(loader.RenderPlan.ContourStatus, Is.EqualTo("not_applied_form"));
                Assert.That(loader.SetCategory("form.type", "blob"), Is.True);
                Assert.That(loader.Root.GetComponentInChildren<MeshFilter>().transform.localScale.x, Is.EqualTo(s22.x * 0.5f).Within(1e-6f));
            }
            finally { loader.Unload(); UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void Synthetic_python_23_examples_load_without_errors()
        {
            string dir = Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "v2.3");
            foreach (var f in Directory.GetFiles(dir, "*.json").OrderBy(x => x, StringComparer.Ordinal))
            {
                var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, Path.GetFileNameWithoutExtension(f)), out var go);
                try
                {
                    Assert.That(loader.Load(f), Is.True, f);
                    string name = Path.GetFileNameWithoutExtension(f);
                    if (name == "EX23-angular")
                    {
                        Assert.That(loader.RenderPath, Is.EqualTo("superquadric"));
                        Assert.That(loader.Notes, Has.Some.Contains("윤곽 슬롯"), "'각진'은 v0 모양어(unmapped_shape)로도 남지만 윤곽으로 그림");
                    }
                    if (name == "EX23-elongated") Assert.That(loader.RenderPlan.AxisRatios, Is.EqualTo(new[] { 0.5, 1.0, 0.5 }));
                    if (name == "EX23-unstated") Assert.That(loader.RenderPlan.ContourStatus, Is.EqualTo("none"));
                }
                finally { loader.Unload(); UnityEngine.Object.DestroyImmediate(go); }
            }
        }
    }
}
