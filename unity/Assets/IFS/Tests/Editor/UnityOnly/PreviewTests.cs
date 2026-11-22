// EditMode 테스트(Unity 전용): JSON 문자열 로드(SceneLoader.LoadJson)와 미리보기 무대·다리(D4).
//   · 문자열 로드 = 파일 로드: 같은 지문(적용값·기본값·notes·모양 판정·계층·머티리얼·기록 파일). golden과도 같다.
//   · 덮어쓰기를 얹은 문자열 로드 = 덮어쓰기를 얹은 파일 로드.
//   · 잘못된 JSON은 false이고 이전 형상을 지우지 않는다.
//   · PreviewStage: 같은 spec을 두 번 찍으면 화소가 같고, 검은·흰 배경 쌍에서 형상이 덮은 화소가 있다.
//   · PreviewBridge(JS 진입점 계약): loaded·error·capture 알림의 내용.
// spec은 StreamingAssets 예시 + 합성 값(참여자 데이터 아님).
using System;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.TestTools;
using IFS.SceneSpec.EditorTools;

namespace IFS.SceneSpec.Tests
{
    public class PreviewTests
    {
        string _tmp;
        int _quality;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-preview-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(Path.Combine(_tmp, "a"));
            Directory.CreateDirectory(Path.Combine(_tmp, "b"));
            _quality = QualitySettings.GetQualityLevel();
        }

        [TearDown]
        public void TearDown()
        {
            if (QualitySettings.GetQualityLevel() != _quality) QualitySettings.SetQualityLevel(_quality, true);
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static string Text(string path) => File.ReadAllText(path, Encoding.UTF8);

        [Test]
        public void LoadJson_matches_file_load_and_the_golden_fingerprint()
        {
            string fromFile = LoaderNoVariantGoldenTests.Fingerprint(Path.Combine(_tmp, "a"), (l, p) => l.Load(p));
            string fromJson = LoaderNoVariantGoldenTests.Fingerprint(Path.Combine(_tmp, "b"), (l, p) => l.LoadJson(Text(p), Path.GetFileName(p)));
            Assert.That(fromJson, Is.EqualTo(fromFile));
            LoaderNoVariantGoldenTests.AssertMatchesGolden(fromJson, "LoadJson");
        }

        [Test]
        public void LoadJson_with_overrides_matches_file_load_with_the_same_overrides()
        {
            SceneOverride Ov()
            {
                var o = SceneOverrideJson.Parse("{\"material.brightness\":0.8,\"layout.size\":0.6,\"motion.type\":\"still\"}", out var errors);
                Assert.That(errors, Is.Empty);
                return o;
            }
            string fromFile = LoaderNoVariantGoldenTests.Fingerprint(Path.Combine(_tmp, "a"), (l, p) => l.Load(p, Ov()));
            string fromJson = LoaderNoVariantGoldenTests.Fingerprint(Path.Combine(_tmp, "b"), (l, p) => l.LoadJson(Text(p), Path.GetFileName(p), Ov()));
            Assert.That(fromJson, Is.EqualTo(fromFile));
            StringAssert.Contains("변형 덮어쓰기(기록 안 함): material.brightness", fromJson);
        }

        [Test]
        public void Invalid_json_returns_false_and_keeps_the_previous_shape()
        {
            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "rec"), out var go);
            try
            {
                Assert.That(loader.LoadJson(Text(OwnershipTestSpecs.ExamplePath("EX01.json")), "EX01.json"), Is.True);
                var root = loader.Root;
                var spec = loader.Spec;
                LogAssert.Expect(LogType.Error, new Regex(@"SceneSpec을 읽지 못했습니다: bad\.json"));
                Assert.That(loader.LoadJson("{\"meta\":", "bad.json"), Is.False);
                LogAssert.Expect(LogType.Error, new Regex(@"JSON 문자열이 null"));
                Assert.That(loader.LoadJson(null, "null.json"), Is.False);
                Assert.That(loader.Root, Is.SameAs(root));
                Assert.That(loader.Spec, Is.SameAs(spec));
                Assert.That(loader.SpecPath, Is.Null, "문자열 로드는 파일 경로가 없다");
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        static float[] Coverage(Color32[] black, Color32[] white)
        {
            var a = new float[black.Length];
            for (int i = 0; i < a.Length; i++)
            {
                double d = (ColorMetrics.SrgbToLinear(white[i].r / 255.0) - ColorMetrics.SrgbToLinear(black[i].r / 255.0)
                          + ColorMetrics.SrgbToLinear(white[i].g / 255.0) - ColorMetrics.SrgbToLinear(black[i].g / 255.0)
                          + ColorMetrics.SrgbToLinear(white[i].b / 255.0) - ColorMetrics.SrgbToLinear(black[i].b / 255.0)) / 3.0;
                a[i] = (float)Math.Max(0, Math.Min(1, 1 - d));
            }
            return a;
        }

        [Test]
        public void Stage_renders_deterministically_and_the_shape_covers_pixels()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            bool asyncWas = ShaderUtil.allowAsyncCompilation;
            ShaderUtil.allowAsyncCompilation = false;
            var stage = PreviewStage.Create(new PreviewSettings(), ShapePrefabMenu.LoadShapePrefabs(), null, cameraEnabled: false);
            try
            {
                var mist = OwnershipTestSpecs.Empty("PREVIEW-mist").Slot("form.type", "mist", "안개").Slot("material.opacity", 0.8, "짙은")
                    .Hsl(0.6, 0.5, 0.5);
                foreach (var (name, json) in new[] { ("EX01.json", Text(OwnershipTestSpecs.ExamplePath("EX01.json"))), ("mist.json", mist.ToString()) })
                {
                    Assert.That(stage.Load(json, name, null), Is.True, name);
                    stage.FreezeMotion();
                    var a = stage.Render(160, 120, PreviewBackground.Scene);
                    var b = stage.Render(160, 120, PreviewBackground.Scene);
                    Assert.That(a.Length, Is.EqualTo(160 * 120));
                    Assert.That(a.SequenceEqual(b), Is.True, name + ": 같은 spec을 두 번 찍으면 같은 화소");
                    var black = stage.Render(160, 120, PreviewBackground.Black);
                    Assert.That(black[0], Is.EqualTo(new Color32(0, 0, 0, 255)), name + ": 검은 배경 렌더의 모서리는 검정(이전 렌더를 읽지 않음)");
                    Assert.That(a[0].Equals(black[0]), Is.False, name + ": 장면 렌더의 모서리는 하늘·바닥");
                    var cov = Coverage(black, stage.Render(160, 120, PreviewBackground.White));
                    int covered = cov.Count(v => v >= 0.02f);
                    Assert.That(covered, Is.GreaterThan(100), name + ": 형상이 덮은 화소");
                    Assert.That(covered, Is.LessThan(cov.Length), name + ": 화면 전체를 덮지는 않는다");
                    // 카메라는 눈 위치에서 형상 쪽을 본다
                    Assert.That(stage.Camera.transform.position.y, Is.EqualTo(1.6f).Within(1e-4));
                    Assert.That(Vector3.Dot(stage.Camera.transform.forward, (stage.Loader.Root.transform.position - stage.Camera.transform.position).normalized),
                        Is.GreaterThan(0.9f));
                }
                Assert.That(stage.Loader.RenderPath, Is.EqualTo("mist"), "안개 셰이더 경로(대체 경로가 아님)");
                var png = stage.RenderPng(64, 48, PreviewBackground.Scene);
                Assert.That(png.Take(4).ToArray(), Is.EqualTo(new byte[] { 0x89, 0x50, 0x4E, 0x47 }));
            }
            finally
            {
                stage.Dispose();
                ShaderUtil.allowAsyncCompilation = asyncWas;
            }
        }

        [Test]
        public void Bridge_reports_loaded_error_and_capture_like_the_js_contract()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject(PreviewBridge.ObjectName);
            var bridge = go.AddComponent<PreviewBridge>();
            try
            {
                bridge.ApplyOverridesJson("{\"form.type\":\"mist\"}");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("error"), "spec 없이 덮어쓰기");

                bridge.LoadSpecJson(Text(OwnershipTestSpecs.ExamplePath("EX02.json")));
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("loaded"));
                var p = bridge.LastNotifyPayload;
                Assert.That((string)p["kind"], Is.EqualTo("load"));
                Assert.That((string)p["renderPath"], Is.EqualTo("blob"));
                Assert.That(p["params"]["form.type"].ToString(), Is.EqualTo("blob"));
                Assert.That(((JArray)p["defaultsUsed"]).Count, Is.GreaterThan(0));
                Assert.That(((JArray)p["errors"]).Count, Is.EqualTo(0));
                Assert.That(p["overrides"].Type, Is.EqualTo(JTokenType.Null));

                bridge.ApplyOverridesJson("{\"form.type\":\"mist\",\"material.opacity\":0.6}");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("loaded"));
                Assert.That((string)bridge.LastNotifyPayload["renderPath"], Is.EqualTo("mist"));
                Assert.That((double)bridge.LastNotifyPayload["params"]["material.opacity"], Is.EqualTo(0.6).Within(1e-9));
                Assert.That((string)bridge.LastNotifyPayload["overrides"]["form.type"], Is.EqualTo("mist"));

                bridge.ApplyOverridesJson("{\"material.unknown\":1}");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("error"));
                Assert.That(bridge.LastNotifyPayload["details"].ToString(), Does.Contain("수치 키가 아님"));
                Assert.That((string)bridge.Stage.Loader.RenderPath, Is.EqualTo("mist"), "잘못된 덮어쓰기는 지금 형상을 바꾸지 않는다");

                bridge.ApplyOverridesJson("");
                Assert.That((string)bridge.LastNotifyPayload["renderPath"], Is.EqualTo("blob"), "빈 덮어쓰기 = 원래 spec");

                bridge.SetFrozen("1");
                bridge.Capture("{\"id\":\"t1\",\"width\":64,\"height\":48,\"background\":\"black\"}");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("capture"));
                Assert.That((string)bridge.LastNotifyPayload["id"], Is.EqualTo("t1"));
                var bytes = Convert.FromBase64String((string)bridge.LastNotifyPayload["png"]);
                Assert.That(bytes.Take(4).ToArray(), Is.EqualTo(new byte[] { 0x89, 0x50, 0x4E, 0x47 }));

                bridge.Capture("{\"id\":\"t2\",\"background\":\"grey\"}");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("error"));
                Assert.That((string)bridge.LastNotifyPayload["id"], Is.EqualTo("t2"));

                LogAssert.Expect(LogType.Error, new Regex("SceneSpec을 읽지 못했습니다: preview.json"));
                bridge.LoadSpecJson("not json");
                Assert.That(bridge.LastNotifyKind, Is.EqualTo("error"));
                Assert.That(((JArray)bridge.LastNotifyPayload["details"]).Count, Is.GreaterThan(0), "로더 오류 문장을 함께 보낸다");
            }
            finally
            {
                bridge.Shutdown();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }
    }
}
