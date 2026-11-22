// 배치 캡처 형상 지표(X72, SilhouetteMetrics) 테스트: 합성 마스크(원·정사각형·다섯 덩어리·가장자리 경사).
using System;
using IFS.SceneSpec.EditorTools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class SilhouetteMetricsTests
    {
        const int W = 400, H = 300;

        static float[] Disc(double cx, double cy, double r, float[] into = null, double ramp = 1, float peak = 1f)
        {
            var a = into ?? new float[W * H];
            for (int y = 0; y < H; y++)
                for (int x = 0; x < W; x++)
                {
                    double d = Math.Sqrt((x - cx) * (x - cx) + (y - cy) * (y - cy));
                    double v = Math.Max(0, Math.Min(1, (r - d) / ramp + 0.5));   // ramp 1 = 렌더의 안티에일리어싱 근사(가장자리 1화소)
                    a[y * W + x] = Math.Max(a[y * W + x], (float)(v * peak));
                }
            return a;
        }

        [Test]
        public void Circle_is_close_to_one_and_one_component()
        {
            var s = SilhouetteMetrics.Measure(Disc(200, 150, 80), W, H);
            Assert.That(s.Circularity, Is.EqualTo(1.0).Within(0.05));
            Assert.That(s.Components, Is.EqualTo(1));
            Assert.That(s.MaxAlpha, Is.EqualTo(1.0));
            Assert.That(s.VisiblePixels, Is.GreaterThanOrEqualTo(s.MaskPixels).And.LessThan(s.MaskPixels + 2 * Math.PI * 81));
            Assert.That(s.MaskPixels, Is.EqualTo(Math.PI * 80 * 80).Within(Math.PI * 80 * 80 * 0.02));
            Assert.That(s.EdgeFalloffPx, Is.LessThan(1.0));   // 딱딱한 가장자리(안티에일리어싱 1화소 안)
        }

        [Test]
        public void Square_is_about_pi_over_four()
        {
            var a = new float[W * H];
            for (int y = 50; y < 250; y++)
                for (int x = 100; x < 300; x++) a[y * W + x] = 1f;
            var s = SilhouetteMetrics.Measure(a, W, H);
            Assert.That(s.Circularity, Is.EqualTo(Math.PI / 4).Within(0.02));
            Assert.That(s.Components, Is.EqualTo(1));
        }

        [Test]
        public void Five_separate_blobs_are_five_components_and_less_circular()
        {
            var a = Disc(60, 60, 30);
            Disc(200, 70, 25, a);
            Disc(330, 90, 35, a);
            Disc(110, 220, 28, a);
            Disc(280, 230, 32, a);
            a[5 * W + 395] = 1f;   // 화소 하나짜리 부스러기는 덩어리로 세지 않는다
            var s = SilhouetteMetrics.Measure(a, W, H);
            Assert.That(s.Components, Is.EqualTo(5));
            Assert.That(s.ComponentsRaw, Is.EqualTo(6));
            Assert.That(s.Circularity, Is.LessThan(0.3));
        }

        [Test]
        public void Soft_edge_gives_a_wide_falloff_and_uses_the_own_maximum()
        {
            // 덮임이 반지름 방향으로 20화소에 걸쳐 0→0.4(가운데가 r)(최대 알파 0.4): 10%→90% 폭 ≈ 0.8 × 20 = 16화소
            var s = SilhouetteMetrics.Measure(Disc(200, 150, 100, ramp: 20, peak: 0.4f), W, H);
            Assert.That(s.MaxAlpha, Is.EqualTo(0.4).Within(1e-6));
            Assert.That(s.EdgeFalloffPx, Is.EqualTo(16).Within(1.5));
            Assert.That(s.Circularity, Is.EqualTo(1.0).Within(0.05));
        }

        [Test]
        public void Nothing_visible_gives_zeros()
        {
            var a = new float[W * H];
            a[10] = 0.01f;   // 문턱(0.02) 아래
            var s = SilhouetteMetrics.Measure(a, W, H);
            Assert.That(s.VisiblePixels, Is.EqualTo(0));
            Assert.That(s.Components, Is.EqualTo(0));
            Assert.That(s.Circularity, Is.EqualTo(0));
        }

        [Test]
        public void Visible_pixels_grow_with_alpha_threshold_crossings()
        {
            var faint = SilhouetteMetrics.Measure(Disc(200, 150, 60, ramp: 40, peak: 0.1f), W, H);
            var strong = SilhouetteMetrics.Measure(Disc(200, 150, 60, ramp: 40, peak: 0.6f), W, H);
            Assert.That(strong.VisiblePixels, Is.GreaterThan(faint.VisiblePixels));
        }

        [Test]
        public void Render_path_summary_groups_by_renderer()
        {
            JObject Spec(string path, double circ, int comps, double p95) => new JObject
            {
                ["renderPath"] = path, ["visiblePixels"] = 100, ["maxAlpha"] = 1.0,
                ["silhouette"] = new JObject { ["circularity"] = circ, ["components"] = comps, ["edgeFalloffPx"] = 1.0 },
                ["performance"] = new JObject { ["frameMsP95"] = p95 },
            };
            var specs = new JArray(Spec("mist", 0.8, 1, 2.0), Spec("mist", 0.6, 1, 3.0), Spec("fragments", 0.2, 5, 1.0), new JObject { ["spec"] = "x" });
            var sum = BatchCapture.RenderPathSummary(specs);
            Assert.That(sum["mist"].Value<int>("specs"), Is.EqualTo(2));
            Assert.That(sum["mist"].Value<double>("circularityMean"), Is.EqualTo(0.7).Within(1e-9));
            Assert.That(sum["mist"].Value<double>("frameMsP95Max"), Is.EqualTo(3.0));
            Assert.That(sum["fragments"].Value<double>("componentsMean"), Is.EqualTo(5));
            Assert.That(sum.Count, Is.EqualTo(2));
        }
    }
}
