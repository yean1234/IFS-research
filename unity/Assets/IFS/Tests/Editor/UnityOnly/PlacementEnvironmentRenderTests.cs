// EditMode 테스트(Unity 전용): 배치 공간 후보 B·E·F(G52–G56) — 새 셰이더가 Resources로 불러지고 컴파일되는지(빌드 안전),
// 자연 사진의 가져오기 설정(Quest), 배경 공간 바꾸기·되돌리기(기본값은 아무것도 바꾸지 않음), 별 하늘 렌더가 결정적인지,
// 기본값 배치 공간의 물체 목록이 G52 전과 같은지, 러너 자동 시행(놓기 도움 + 자연)이 기록을 남기는지.
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementEnvironmentRenderTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-env-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        [Test]
        public void New_shaders_load_from_resources_and_compile()
        {
            foreach (var res in new[] { EnvironmentStyleInfo.StarfieldShaderResource, EnvironmentStyleInfo.PanoramaShaderResource, EnvironmentStyleInfo.GroundShaderResource })
            {
                var s = Resources.Load<Shader>(res);
                Assert.That(s, Is.Not.Null, res + ": Resources 안에 있어야 빌드에 들어간다");
                Assert.That(s.isSupported, Is.True, res);
                Assert.That(ShaderUtil.ShaderHasError(s), Is.False, res + " 컴파일 오류");
            }
        }

        [Test]
        public void Nature_texture_imports_compressed_with_mipmaps_for_quest()
        {
            var tex = Resources.Load<Texture2D>(NatureSkyAsset.ResourcePath);
            Assert.That(tex, Is.Not.Null);
            Assert.That((tex.width, tex.height), Is.EqualTo((NatureSkyAsset.Width, NatureSkyAsset.Height)));
            Assert.That(tex.mipmapCount, Is.GreaterThan(1));
            string assetPath = "Assets/" + NatureSkyAsset.AssetRelativePath;
            var ti = (TextureImporter)AssetImporter.GetAtPath(assetPath);
            Assert.That(ti, Is.Not.Null, assetPath);
            Assert.That(NatureTextureImport.IsNatureTexture(assetPath), Is.True);
            Assert.That(ti.mipmapEnabled, Is.True);
            Assert.That(ti.sRGBTexture, Is.True);
            Assert.That(ti.isReadable, Is.False);
            Assert.That(ti.maxTextureSize, Is.LessThanOrEqualTo(4096));
            Assert.That(ti.textureCompression, Is.Not.EqualTo(TextureImporterCompression.Uncompressed));
            Assert.That(ti.wrapModeU, Is.EqualTo(TextureWrapMode.Repeat));
            Assert.That(ti.wrapModeV, Is.EqualTo(TextureWrapMode.Clamp));
            var android = ti.GetPlatformTextureSettings("Android");
            Assert.That(android.overridden, Is.True);
            Assert.That(android.format, Is.EqualTo(NatureTextureImport.AndroidFormat), "Quest: ASTC");
            Assert.That(android.maxTextureSize, Is.LessThanOrEqualTo(4096));
            var pc = ti.GetPlatformTextureSettings("Standalone");
            Assert.That(pc.overridden && pc.format == NatureTextureImport.StandaloneFormat, Is.True);
        }

        [Test]
        public void Environment_style_neutral_is_a_no_op_and_styles_switch_back_cleanly()
        {
            var env = EnvironmentBuilder.Build(new EnvironmentSettings());
            try
            {
                int children = env.Root.transform.childCount;
                var reflection = RenderSettings.customReflectionTexture;
                Assert.That(EnvironmentStyle.Apply(env, "neutral"), Is.True);
                Assert.That(RenderSettings.skybox, Is.SameAs(env.SkyMaterial), "neutral: 하늘 그대로");
                Assert.That(env.Root.transform.childCount, Is.EqualTo(children));
                Assert.That(env.Floor.enabled, Is.True);
                Assert.That(RenderSettings.customReflectionTexture, Is.SameAs(reflection));

                Assert.That(EnvironmentStyle.Apply(env, "space"), Is.True);
                Assert.That(env.Style, Is.EqualTo("space"));
                Assert.That(RenderSettings.skybox.shader.name, Is.EqualTo("IFS/Environment Starfield"));
                Assert.That(env.Floor.enabled, Is.False, "격자 바닥 숨김");
                var lights = env.Root.GetComponentsInChildren<Light>();
                Assert.That(lights.Length, Is.EqualTo(1), "조명은 그대로(세 공간 같은 빛)");

                Assert.That(EnvironmentStyle.Apply(env, "nature"), Is.True);
                Assert.That(RenderSettings.skybox.shader.name, Is.EqualTo("IFS/Environment Panorama"));
                var ground = env.Root.transform.Find(EnvironmentStyle.GroundName);
                Assert.That(ground, Is.Not.Null, "발밑 땅 원판");
                Assert.That(ground.GetComponent<Renderer>().bounds.extents.x, Is.EqualTo((float)EnvironmentStyleInfo.GroundRadiusM).Within(0.5f));
                Assert.That(ground.position.y, Is.LessThan(0f), "배치 바닥(y = 0) 아래");
                Assert.That(ground.GetComponent<Collider>() == null, Is.True);

                Assert.That(EnvironmentStyle.Apply(env, "neutral"), Is.True);
                Assert.That(RenderSettings.skybox, Is.SameAs(env.SkyMaterial), "되돌리면 중립 하늘");
                Assert.That(env.Floor.enabled, Is.True);
                Assert.That(env.Root.transform.Find(EnvironmentStyle.GroundName), Is.Null);
                Assert.That(EnvironmentStyle.Apply(env, "forest"), Is.False, "모르는 공간은 중립");
                Assert.That(env.Style, Is.EqualTo("neutral"));
            }
            finally { env.Dispose(); }
            Assert.That(GameObject.Find(EnvironmentBuilder.RootName), Is.Null);
        }

        static Color32[] RenderSky(Material sky, int w, int h, Quaternion rot)
        {
            var go = new GameObject("starfield test camera");
            var prevSky = RenderSettings.skybox;
            var rt = new RenderTexture(w, h, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB);
            var prev = RenderTexture.active;
            try
            {
                RenderSettings.skybox = sky;
                var cam = go.AddComponent<Camera>();
                cam.enabled = false;
                cam.clearFlags = CameraClearFlags.Skybox;
                cam.fieldOfView = 30f;   // 약 0.05°/화소(Quest 3 근사) — 별이 화소보다 작아 어둡게 넓혀지지 않게
                cam.aspect = (float)w / h;
                cam.allowMSAA = false;
                cam.allowHDR = false;
                go.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), rot);
                cam.targetTexture = rt;
                cam.Render();
                RenderTexture.active = rt;
                var tex = new Texture2D(w, h, TextureFormat.RGBA32, false);
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                tex.Apply();
                var px = tex.GetPixels32();
                UnityEngine.Object.DestroyImmediate(tex);
                return px;
            }
            finally
            {
                RenderTexture.active = prev;
                RenderSettings.skybox = prevSky;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Starfield_renders_deterministically_navy_with_stars()
        {
            var env1 = EnvironmentBuilder.Build(new EnvironmentSettings());
            Color32[] a, b, c;
            try
            {
                EnvironmentStyle.Apply(env1, "space");
                a = RenderSky(RenderSettings.skybox, 640, 480, Quaternion.Euler(-20f, 30f, 0f));
                c = RenderSky(RenderSettings.skybox, 640, 480, Quaternion.Euler(-20f, 30f, 0f));
            }
            finally { env1.Dispose(); }
            var env2 = EnvironmentBuilder.Build(new EnvironmentSettings());
            try
            {
                EnvironmentStyle.Apply(env2, "space");   // 새 머티리얼로 다시 만들어도
                b = RenderSky(RenderSettings.skybox, 640, 480, Quaternion.Euler(-20f, 30f, 0f));
            }
            finally { env2.Dispose(); }
            Assert.That(a.SequenceEqual(c), Is.True, "같은 머티리얼 두 번 렌더: 같은 화소");
            Assert.That(a.SequenceEqual(b), Is.True, "다시 만든 별 하늘: 같은 화소(시간·난수 없음)");
            var sorted = a.Select(p => (p.r + p.g + p.b) / 3.0).OrderBy(v => v).ToArray();
            double median = sorted[sorted.Length / 2];
            Assert.That(median, Is.GreaterThan(4).And.LessThan(40), "바탕은 완전한 검정이 아닌 짙은 색");
            var mid = a.OrderBy(p => p.r + p.g + p.b).ElementAt(a.Length / 2);
            Assert.That(mid.b, Is.GreaterThan(mid.r), "남색(파랑이 빨강보다 큼)");
            Assert.That(a.Count(p => (p.r + p.g + p.b) / 3.0 > median + 25), Is.GreaterThan(5), "별이 보인다");
        }

        [Test]
        public void Default_space_objects_are_unchanged_and_assist_adds_its_own()
        {
            var expected = new[]
            {
                "floor disc", "boundary", "ring 1 m", "ring 2 m", "ring 3 m", "self marker", "pointer", "target",
            };
            var h = PlacementSpace.Build(new PlacementConfig());
            try
            {
                var names = Enumerable.Range(0, h.Root.transform.childCount).Select(i => h.Root.transform.GetChild(i).name).ToArray();
                Assert.That(names, Is.EqualTo(expected), "기본값: G52 전과 같은 물체 목록");
                Assert.That(h.DropLine, Is.Null);
                Assert.That(h.PracticeCube, Is.Null);
            }
            finally { h.Dispose(); }
            var h2 = PlacementSpace.Build(new PlacementConfig { placementAssist = true });
            try
            {
                var names = Enumerable.Range(0, h2.Root.transform.childCount).Select(i => h2.Root.transform.GetChild(i).name).ToArray();
                Assert.That(names.Take(expected.Length), Is.EqualTo(expected), "도움 물체는 뒤에 붙는다");
                Assert.That(h2.DropLine.activeSelf || h2.PracticeCube.activeSelf, Is.False, "처음엔 숨김");
                PlacementSpace.SetAssist(h2, true, PlacementGeometry.FromPolar(3.9, 0, 1.0), 0.3, 4.0);
                Assert.That(h2.DropLine.activeSelf && h2.ContactRing.activeSelf, Is.True);
                Assert.That(h2.DropLine.GetComponent<Renderer>().bounds.min.y, Is.EqualTo(0f).Within(1e-3f), "수직선은 바닥까지");
                Assert.That(h2.DropLine.GetComponent<Renderer>().bounds.max.y, Is.EqualTo(1f).Within(1e-3f), "물체 중심 높이까지");
                Assert.That(h2.BoundaryMaterial.color.r, Is.GreaterThan(PlacementSpace.BoundaryColor.r + 0.3f), "경계 가까이: 띠가 밝아짐");
                PlacementSpace.SetAssist(h2, false, default, 0, 4.0);
                var bc = h2.BoundaryMaterial.color;
                Assert.That(new[] { bc.r, bc.g, bc.b }, Is.EqualTo(new[] { PlacementSpace.BoundaryColor.r, PlacementSpace.BoundaryColor.g, PlacementSpace.BoundaryColor.b }).Within(1e-4f), "놓으면 원래 색");
                Assert.That(h2.DropLine.activeSelf, Is.False);
                PlacementSpace.SetPractice(h2, true, PlacementGeometry.FromPolar(1.5, 0, 1.2), PlacementGeometry.FromPolar(2, -45, 0.8));
                Assert.That(h2.PracticeCube.activeSelf && h2.PracticeTarget.activeSelf && h2.PracticeTargetRing.activeSelf, Is.True);
                Assert.That(h2.PracticeTarget.transform.position.y, Is.EqualTo(0.8f).Within(1e-4f));
            }
            finally { h2.Dispose(); }
        }

        [Test]
        public void Runner_auto_trial_with_assist_in_nature_records_practice_and_environment()
        {
            string spec = OwnershipTestSpecs.ExamplePath("EX02.json");
            var cfg = PlacementTests.ShortConfig("place");
            cfg.environment = "nature";
            cfg.placementAssist = true;
            string dir = PlacementExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 5, cfg, 0.02, null);
            Assert.That(File.Exists(Path.Combine(dir, PlacementRecordWriter.PracticeFile)), Is.True);
            var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((string)m["environment"]["name"], Is.EqualTo("nature"));
            Assert.That((string)m["environment"]["sky"]["texture"]["sha256"], Is.EqualTo(NatureSkyAsset.Sha256));
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Contain("placement_range"));

            string plain = PlacementExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 6, PlacementTests.ShortConfig("place"), 0.02, null);
            var pm = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(plain, "manifest.json")));
            Assert.That(pm["environment"], Is.Null, "기본값: manifest에 environment 키 없음");
            Assert.That(pm["taskText"]["draftKeys"].Select(k => (string)k), Does.Not.Contain("placement_range"), "도움 문구는 보이지 않으니 세지 않음");
            Assert.That(File.Exists(Path.Combine(plain, PlacementRecordWriter.PracticeFile)), Is.False);
        }

        [Test]
        public void Runner_applies_environment_to_the_scene_and_default_keeps_the_neutral_sky()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            var env = UnityEngine.Object.FindObjectsByType<IFSEnvironment>(FindObjectsSortMode.None).Single();
            env.Rebuild();
            try
            {
                runner.RefreshSpace();
                Assert.That(runner.AppliedEnvironment, Is.EqualTo("neutral"));
                Assert.That(RenderSettings.skybox, Is.SameAs(env.Handle.SkyMaterial));
                runner.Config.environment = "space";
                runner.RefreshSpace();
                Assert.That(runner.AppliedEnvironment, Is.EqualTo("space"));
                Assert.That(env.Handle.Style, Is.EqualTo("space"));
                runner.Config.environment = "neutral";
                runner.RefreshSpace();
                Assert.That(RenderSettings.skybox, Is.SameAs(env.Handle.SkyMaterial));
                Assert.That(PlacementExperimenterGui.SpaceLine(new PlacementConfig { environment = "nature", placementAssist = true }, "nature"), Does.Contain("후보 F"));
            }
            finally
            {
                runner.ResetForNext();
                env.Handle?.Dispose();
            }
        }
    }
}
