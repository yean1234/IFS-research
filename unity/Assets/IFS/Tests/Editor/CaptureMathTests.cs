// EditMode 테스트: 색차 계산·캡처 인자·백분위수·색 요약. 렌더가 필요 없어 dotnet(compile-check)에서도 실행된다.
using System;
using System.IO;
using IFS.SceneSpec.EditorTools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class CaptureMathTests
    {
        // Sharma, Wu & Dalal (2005) CIEDE2000 시험 자료의 쌍 일부(1, 7, 13, 17번)
        [TestCase(50.0, 2.6772, -79.7751, 50.0, 0.0, -82.7485, 2.0425)]
        [TestCase(50.0, 0.0, 0.0, 50.0, -1.0, 2.0, 2.3669)]
        [TestCase(50.0, 2.49, -0.001, 50.0, -2.49, 0.0009, 7.1792)]
        [TestCase(50.0, 2.5, 0.0, 73.0, 25.0, -18.0, 27.1492)]
        public void DeltaE2000_matches_published_test_pairs(double l1, double a1, double b1, double l2, double a2, double b2, double expected)
        {
            var p = new Lab(l1, a1, b1);
            var q = new Lab(l2, a2, b2);
            Assert.That(ColorMetrics.DeltaE2000(p, q), Is.EqualTo(expected).Within(1e-4));
            Assert.That(ColorMetrics.DeltaE2000(q, p), Is.EqualTo(expected).Within(1e-4));   // 대칭
        }

        [Test]
        public void Srgb_to_lab_anchor_points()
        {
            var white = ColorMetrics.SrgbToLab(1, 1, 1);
            Assert.That(white.L, Is.EqualTo(100).Within(1e-3));
            Assert.That(Math.Abs(white.A) + Math.Abs(white.B), Is.LessThan(1e-3));
            Assert.That(ColorMetrics.SrgbToLab(0, 0, 0).L, Is.EqualTo(0).Within(1e-9));
            Assert.That(ColorMetrics.SrgbToLab(0.5, 0.5, 0.5).L, Is.EqualTo(53.39).Within(0.01));
            Assert.That(ColorMetrics.LinearToSrgb(ColorMetrics.SrgbToLinear(0.37)), Is.EqualTo(0.37).Within(1e-9));
            Assert.That(ColorMetrics.DeltaE76(new Lab(50, 0, 0), new Lab(53, 4, 0)), Is.EqualTo(5).Within(1e-9));
        }

        [Test]
        public void Capture_options_defaults_are_quest3_per_eye()
        {
            var o = CaptureOptions.Parse(new[] { "Unity.exe", "-batchmode", "-specDir", "a", "-outDir", "b" });
            Assert.That((o.Width, o.Height, o.Frames, o.Eyes), Is.EqualTo((2064, 2208, 300, 2)));
            var p = CaptureOptions.Parse(new[] { "-specDir", "a", "-outDir", "b", "-width", "640", "-height", "480", "-frames", "10", "-eyes", "1", "-fov", "90.5" });
            Assert.That((p.Width, p.Height, p.Frames, p.Eyes), Is.EqualTo((640, 480, 10, 1)));
            Assert.That(p.FieldOfView, Is.EqualTo(90.5f));
            Assert.Throws<ArgumentException>(() => CaptureOptions.Parse(new[] { "-outDir", "b" }));
            Assert.Throws<ArgumentException>(() => CaptureOptions.Parse(new[] { "-specDir", "a", "-outDir", "b", "-frames", "0" }));
        }

        [Test]
        public void Color_default_components_flag_any_unsaid_hsl_part()
        {
            var ex01 = SceneSpecJson.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX01.json"));
            Assert.That(BatchCapture.ColorDefaultComponents(SceneParams.FromSpec(ex01, new SceneDefaults())), Is.Empty);

            // 색 이름은 없고 채도어만 말한 경우: s만 말한 값, h·l은 기본값 → 기본값이 섞인 색
            var ex02 = SceneSpecJson.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX02.json"));
            ex02.Material.Saturation = 0.3;
            Assert.That(BatchCapture.ColorDefaultComponents(SceneParams.FromSpec(ex02, new SceneDefaults())), Is.EqualTo(new[] { "h", "l" }));
        }

        [Test]
        public void Color_summary_keeps_default_colors_out_of_stated_accuracy()
        {
            JObject Spec(bool isDefault, string primary, double inContext, double scene) => new JObject
            {
                ["color"] = new JObject
                {
                    ["specColorIsDefault"] = isDefault,
                    ["primary"] = primary,
                    ["frontal"] = new JObject { ["deltaE2000VsSpec"] = 9.0 },
                    ["scene"] = new JObject { ["deltaE2000VsSpec"] = scene },
                    ["inContext"] = new JObject { ["deltaE2000VsSpec"] = inContext },
                },
            };
            var specs = new JArray(
                Spec(false, "inContext", 2.0, 3.0),
                Spec(false, "scene", 8.0, 4.0),     // 반투명: primary = scene
                Spec(true, "inContext", 0.5, 0.5),  // 기본 회색 — stated에 들어가면 평균이 좋아 보인다
                new JObject { ["color"] = new JObject { ["error"] = "형상이 화면에 보이지 않음" } });
            var sum = BatchCapture.ColorSummary(specs);
            Assert.That(sum["stated"].Value<int>("specs"), Is.EqualTo(2));
            Assert.That(sum["stated"].Value<double>("primaryMean"), Is.EqualTo(3.0).Within(1e-9));   // (2 + 4) / 2
            Assert.That(sum["stated"].Value<double>("primaryMax"), Is.EqualTo(4.0).Within(1e-9));
            Assert.That(sum["stated"].Value<double>("inContextMean"), Is.EqualTo(5.0).Within(1e-9));
            Assert.That(sum["withDefaults"].Value<int>("specs"), Is.EqualTo(1));
            Assert.That(sum["withDefaults"].Value<double>("primaryMean"), Is.EqualTo(0.5).Within(1e-9));
        }

        [Test]
        public void Percentile_is_nearest_rank()
        {
            var v = new double[] { 5, 1, 4, 2, 3, 6, 7, 8, 9, 10 };
            Assert.That(CaptureStats.Percentile(v, 50), Is.EqualTo(5));
            Assert.That(CaptureStats.Percentile(v, 95), Is.EqualTo(10));
            Assert.That(CaptureStats.Percentile(v, 0), Is.EqualTo(1));
            Assert.That(CaptureStats.Fps(13.9), Is.EqualTo(71.94).Within(0.01));
        }
    }
}
