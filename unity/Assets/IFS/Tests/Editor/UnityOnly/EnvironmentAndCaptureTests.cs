// EditMode 테스트(Unity 전용 — 실제 렌더·설정이 필요해 dotnet compile-check 테스트에서는 뺀다):
//   프로젝트 설정(선형 색공간, VR 품질 단계), 중립 환경 빌더, 배치 캡처 한 바퀴.
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace IFS.SceneSpec.Tests
{
    public class EnvironmentAndCaptureTests
    {
        static float Saturation(Color c)
        {
            Color.RGBToHSV(c, out _, out float s, out _);
            return s;
        }

        [Test]
        public void Project_uses_linear_color_space_and_vr_quality_levels()
        {
            Assert.That(PlayerSettings.colorSpace, Is.EqualTo(ColorSpace.Linear));
            foreach (var name in new[] { "VR PC", "VR Quest" })
            {
                int idx = System.Array.IndexOf(QualitySettings.names, name);
                Assert.That(idx, Is.GreaterThanOrEqualTo(0), name);
                int was = QualitySettings.GetQualityLevel();
                QualitySettings.SetQualityLevel(idx, false);
                try
                {
                    Assert.That(QualitySettings.antiAliasing, Is.EqualTo(4), name + " MSAA");
                    Assert.That(QualitySettings.shadows, Is.EqualTo(ShadowQuality.All), name + " soft shadows");
                    Assert.That(QualitySettings.shadowCascades, Is.EqualTo(1), name);
                    Assert.That(QualitySettings.shadowDistance, Is.LessThanOrEqualTo(10f), name);
                    Assert.That(QualitySettings.pixelLightCount, Is.EqualTo(1), name);
                    Assert.That(QualitySettings.realtimeReflectionProbes, Is.False, name);
                }
                finally
                {
                    QualitySettings.SetQualityLevel(was, false);
                }
            }
        }

        [Test]
        public void Environment_is_neutral_lit_by_one_soft_shadow_light_and_cleans_up()
        {
            var env = EnvironmentBuilder.Build(new EnvironmentSettings());
            try
            {
                var lights = env.Root.GetComponentsInChildren<Light>();
                Assert.That(lights.Length, Is.EqualTo(1));
                Assert.That(lights[0].type, Is.EqualTo(LightType.Directional));
                Assert.That(lights[0].shadows, Is.EqualTo(LightShadows.Soft));
                Assert.That(Saturation(lights[0].color), Is.LessThan(0.01f), "백색광");

                Assert.That(env.FloorMaterial, Is.Not.Null);
                Assert.That(env.FloorMaterial.shader.isSupported, Is.True, "바닥 셰이더 컴파일");
                Assert.That(env.Floor.shadowCastingMode, Is.EqualTo(ShadowCastingMode.Off));
                Assert.That(env.SkyMaterial.shader.isSupported, Is.True, "하늘 셰이더 컴파일");
                Assert.That(RenderSettings.skybox, Is.SameAs(env.SkyMaterial));
                Assert.That(RenderSettings.ambientMode, Is.EqualTo(AmbientMode.Trilight));
                Assert.That(RenderSettings.fog, Is.False);
                Assert.That(RenderSettings.defaultReflectionMode, Is.EqualTo(DefaultReflectionMode.Custom));
                Assert.That(RenderSettings.customReflectionTexture, Is.SameAs(env.ReflectionCube));

                var s = env.Settings;
                foreach (var c in new[] { s.floorColor, s.gridMajorColor, s.gridMinorColor, s.skyZenith, s.skyHorizon, s.skyGround,
                                          s.ambientSky, s.ambientEquator, s.ambientGround })
                    Assert.That(Saturation(c), Is.LessThanOrEqualTo(0.08f), "무채색 환경(HSV 채도): " + c);
            }
            finally
            {
                env.Dispose();
            }
            Assert.That(GameObject.Find(EnvironmentBuilder.RootName), Is.Null, "Dispose 후 남은 객체");
        }

        [Test]
        public void Environment_dispose_restores_global_render_settings()
        {
            var probeSky = new Material(Shader.Find("Unlit/Color")) { name = "test previous skybox" };
            var was = (RenderSettings.skybox, RenderSettings.ambientMode, RenderSettings.ambientLight, RenderSettings.fog,
                       RenderSettings.sun, RenderSettings.defaultReflectionMode, RenderSettings.customReflectionTexture);
            try
            {
                RenderSettings.skybox = probeSky;
                RenderSettings.ambientMode = AmbientMode.Flat;
                RenderSettings.ambientLight = new Color(0.2f, 0.3f, 0.4f, 1f);
                RenderSettings.fog = true;
                RenderSettings.defaultReflectionMode = DefaultReflectionMode.Skybox;

                var env = EnvironmentBuilder.Build(new EnvironmentSettings());
                Assert.That(RenderSettings.skybox, Is.SameAs(env.SkyMaterial));
                env.Dispose();

                Assert.That(RenderSettings.skybox, Is.SameAs(probeSky), "지워진 하늘 머티리얼을 가리키면 안 됨");
                Assert.That(RenderSettings.ambientMode, Is.EqualTo(AmbientMode.Flat));
                Assert.That(RenderSettings.ambientLight, Is.EqualTo(new Color(0.2f, 0.3f, 0.4f, 1f)));
                Assert.That(RenderSettings.fog, Is.True);
                Assert.That(RenderSettings.defaultReflectionMode, Is.EqualTo(DefaultReflectionMode.Skybox));
                Assert.That(RenderSettings.sun, Is.SameAs(was.Item5));
            }
            finally
            {
                (RenderSettings.skybox, RenderSettings.ambientMode, RenderSettings.ambientLight, RenderSettings.fog,
                 RenderSettings.sun, RenderSettings.defaultReflectionMode, RenderSettings.customReflectionTexture) = was;
                Object.DestroyImmediate(probeSky);
            }
        }

        [Test]
        public void Changing_form_type_does_not_accumulate_material_copies()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject("SceneLoader (test)");
            try
            {
                var loader = go.AddComponent<SceneLoader>();
                var so = new SerializedObject(loader);
                so.FindProperty("record").boolValue = false;
                so.FindProperty("loadOnStart").boolValue = false;
                so.ApplyModifiedPropertiesWithoutUndo();
                Assert.That(loader.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX01.json")), Is.True);
                int initial = loader.OwnedMaterialCount;
                Assert.That(initial, Is.GreaterThan(0));
                foreach (var form in new[] { "shell", "fragments", "mist", "blob", "shell", "blob" })
                    Assert.That(loader.SetCategory("form.type", form), Is.True, form);
                Assert.That(loader.OwnedMaterialCount, Is.EqualTo(initial), "형상을 바꿀 때 이전 머티리얼 사본을 지워야 함");
                loader.Unload();
                Assert.That(loader.OwnedMaterialCount, Is.EqualTo(0));
            }
            finally
            {
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Batch_capture_renders_examples_without_console_errors()
        {
            string specDir = Path.Combine(Application.streamingAssetsPath, "IFS", "examples");
            string outDir = Path.Combine(Path.GetTempPath(), "ifs-batch-capture-test-" + System.Guid.NewGuid().ToString("N"));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);   // BatchCapture.Run()과 같은 빈 씬(기본 방향광 없음)
            try
            {
                var o = new CaptureOptions
                {
                    SpecDir = specDir, OutDir = outDir, Width = 320, Height = 342, Frames = 5, WarmupFrames = 1, PngWidth = 160,
                };
                var report = BatchCapture.Execute(o);
                Assert.That(report.Value<bool>("ok"), Is.True);
                Assert.That(File.Exists(Path.Combine(outDir, "report.json")), Is.True);
                var specs = report["specs"].Children<JObject>().ToArray();
                Assert.That(specs.Length, Is.EqualTo(2));
                foreach (var s in specs)
                {
                    Assert.That(s.Value<bool>("loaded"), Is.True, s.Value<string>("spec"));
                    Assert.That(s["console"].Value<int>("errors"), Is.EqualTo(0), s["console"].ToString());
                    Assert.That(s["console"].Value<int>("exceptions"), Is.EqualTo(0), s["console"].ToString());
                    Assert.That(File.Exists(Path.Combine(outDir, s.Value<string>("png"))), Is.True);
                    Assert.That(s["color"]["frontal"].Value<int>("pixels"), Is.GreaterThan(0), "형상이 화면에 보인다");
                    Assert.That(s["renderStats"]["computed"].Value<int>("shadowLights"), Is.EqualTo(1));
                    Assert.That(s["performance"].Value<int>("frames"), Is.EqualTo(5));
                    Assert.That(s["params"], Is.Not.Null);
                    Assert.That(s["defaultsUsed"], Is.Not.Null);
                    // 불투명 형상은 '형상만' 렌더(scene)와 실제 장면 렌더(inContext)의 색이 같아야 한다.
                    // 안쪽 면 패스의 ShadowCaster가 깊이 텍스처에 들어가던 문제(바닥 유무로 EX01 L* 2 차이)의 회귀 방지.
                    if (!s["color"].Value<bool>("transparent"))
                        Assert.That(s["color"].Value<double>("sceneVsInContextDeltaE2000"), Is.LessThanOrEqualTo(0.1),
                            s.Value<string>("spec") + " scene vs inContext");
                }
                // EX02는 형태·색을 말하지 않았다 → 기본값으로 채웠다는 기록이 남아야 한다(원칙 2)
                var ex02 = specs.Single(s => s.Value<string>("spec") == "EX02.json");
                Assert.That(ex02["defaultsUsed"].Values<string>(), Does.Contain("form.type"));
                Assert.That(ex02["color"].Value<bool>("specColorIsDefault"), Is.True);
                Assert.That(ex02["color"]["specColorDefaultComponents"].Values<string>(), Is.EqualTo(new[] { "h", "s", "l" }));
                var ex01 = specs.Single(s => s.Value<string>("spec") == "EX01.json");
                Assert.That(ex01["color"].Value<bool>("specColorIsDefault"), Is.False);
                Assert.That(ex01["color"].Value<string>("floorDuringIsolatedRenders"), Is.EqualTo("unlitBackgroundColor"));
                // 색 반영 정확도 요약에는 말한 색(EX01)만 들어간다
                Assert.That(report["summary"]["color"]["stated"].Value<int>("specs"), Is.EqualTo(1));
                Assert.That(report["summary"]["color"]["withDefaults"].Value<int>("specs"), Is.EqualTo(1));
                Assert.That(report["summary"]["ac4"]["drawCallsPerEyeEstimateAtMost100"], Is.Not.Null);
            }
            finally
            {
                if (Directory.Exists(outDir)) Directory.Delete(outDir, true);
            }
        }
    }
}
