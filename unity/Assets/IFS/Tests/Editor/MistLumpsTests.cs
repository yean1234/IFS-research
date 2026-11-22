// mist 밀도장 뼈대(D7, MistLumps) 테스트: seed 결정성·덩어리 수·대리 구 안·다른 seed·계획 JSON·밝기 대비 지표.
using System;
using System.Globalization;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class MistLumpsTests
    {
        static string Fingerprint(double[] l) =>
            string.Join(";", Enumerable.Range(0, l.Length / 4).Select(k =>
                string.Join(",", Enumerable.Range(0, 4).Select(j => l[k * 4 + j].ToString("F4", CultureInfo.InvariantCulture)))));

        [Test]
        public void Same_seed_gives_the_same_lumps()
        {
            Assert.That(MistLumps.Build(0), Is.EqualTo(MistLumps.Build(0)));
            Assert.That(MistLumps.Build(12345), Is.EqualTo(MistLumps.Build(12345)));
        }

        [Test]
        public void Different_seeds_give_different_layouts()
        {
            Assert.That(Fingerprint(MistLumps.Build(1)), Is.Not.EqualTo(Fingerprint(MistLumps.Build(0))));
            Assert.That(Fingerprint(MistLumps.Build(7)), Is.Not.EqualTo(Fingerprint(MistLumps.Build(1))));
        }

        // 규칙 버전에 묶인 기본 배치. 규칙(배치·반지름·난수 순서)을 바꾸면 이 값이 달라지므로 RuleVersion을 올리고 여기를 고친다.
        [Test]
        public void Default_layout_is_pinned_to_the_rule_version()
        {
            Assert.That(MistLumps.RuleVersion, Is.EqualTo("lumps5/1"));
            Assert.That(Fingerprint(MistLumps.Build(MistLumps.DefaultSeed)), Is.EqualTo(DefaultFingerprint));
        }

        const string DefaultFingerprint =
            "0.0044,-0.0400,-0.0006,0.3532;0.2630,0.0958,0.0219,0.2086;-0.1679,-0.0522,0.2006,0.2254;-0.2488,0.1675,-0.2125,0.2607;0.1595,-0.0270,-0.2819,0.2134";

        [TestCase(0)]
        [TestCase(1)]
        [TestCase(7)]
        [TestCase(99991)]
        [TestCase(-5)]
        public void Three_to_five_round_lumps_stay_inside_the_proxy_sphere(int seed)
        {
            var l = MistLumps.Build(seed);
            Assert.That(l.Length, Is.EqualTo(MistLumps.Count * 4));
            Assert.That(MistLumps.Count, Is.InRange(3, 5));
            Assert.That(MistLumps.Extent(l), Is.LessThanOrEqualTo(MistLumps.MaxExtent + 1e-9));
            Assert.That(MistLumps.MaxExtent + 0.08, Is.LessThan(FormRenderResources.MistRadius), "노이즈 여유를 더해도 대리 구 안");
            for (int k = 0; k < MistLumps.Count; k++) Assert.That(l[k * 4 + 3], Is.GreaterThan(0.1), "반지름");
            // 가운데 덩어리가 가장 크다(구름의 몸통)
            for (int k = 1; k < MistLumps.Count; k++) Assert.That(l[3], Is.GreaterThan(l[k * 4 + 3]));
            // 덩어리 속은 밀도 1, 겉면 밖은 0(노이즈를 뺀 뼈대)
            Assert.That(MistLumps.ShapeDensity(l, l[0], l[1], l[2]), Is.EqualTo(1.0));
            Assert.That(MistLumps.ShapeDensity(l, 0.74, 0.0, 0.0), Is.EqualTo(0.0));
        }

        [Test]
        public void Lumps_overlap_into_one_cloud_body()
        {
            // 둘레 덩어리마다 가운데 덩어리와 겹친다(따로 떨어진 공 다섯 개가 아니라 겹친 구름)
            var l = MistLumps.Build(MistLumps.DefaultSeed);
            for (int k = 1; k < MistLumps.Count; k++)
            {
                double dx = l[k * 4] - l[0], dy = l[k * 4 + 1] - l[1], dz = l[k * 4 + 2] - l[2];
                Assert.That(Math.Sqrt(dx * dx + dy * dy + dz * dz), Is.LessThan(l[3] + l[k * 4 + 3]), "덩어리 " + k);
            }
        }

        static FormRenderPlan Plan(string form)
        {
            var spec = OwnershipTestSpecs.Empty("LUMP" + form).Slot("form.type", form, "형태").Parse();
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            return FormRenderPlan.Build(p, p.GetCategory("form.type"), ShapeMapping.Resolve(spec));
        }

        [Test]
        public void Mist_plan_records_the_lump_rule_and_other_forms_do_not()
        {
            var mist = Plan("mist");
            Assert.That(mist.MistRule, Is.EqualTo(MistLumps.RuleVersion));
            Assert.That(mist.MistSeed, Is.EqualTo(MistLumps.DefaultSeed));
            var j = (JObject)mist.ToJson()["mistRule"];
            Assert.That(j.Value<string>("version"), Is.EqualTo(MistLumps.RuleVersion));
            Assert.That(((JArray)j["lumps"]).Count, Is.EqualTo(MistLumps.Count));
            Assert.That(mist.PresetNote, Does.Contain("둥근 덩어리 " + MistLumps.Count + "개").And.Contain(MistLumps.RuleVersion));
            // 형태 밀도 프리셋 숫자는 그대로(0.5): 소유감 러너의 형태별 밀도 표·RenderedColor와 같다
            Assert.That(mist.Preset.Density, Is.EqualTo(0.5f));
            Assert.That(OwnershipVariantGenerator.FormDensity["mist"], Is.EqualTo(0.5));
            foreach (var f in new[] { "blob", "shell", "fragments" })
            {
                var p = Plan(f);
                Assert.That(p.MistRule, Is.Null, f);
                Assert.That(p.ToJson()["mistRule"].Type, Is.EqualTo(JTokenType.Null), f);
            }
        }

        // 배치 캡처의 밝기 대비 지표: 형상 영역 평균 L* − 주변 배경 평균 L*
        [Test]
        public void Background_contrast_compares_the_mask_with_the_surrounding_band()
        {
            const int w = 200, h = 150;
            var a = new float[w * h];
            var l = new double[w * h];
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    int i = y * w + x;
                    l[i] = 70;                                                   // 배경
                    if (x >= 80 && x < 120 && y >= 50 && y < 100)
                    {
                        a[i] = 0.8f;
                        l[i] = y < 75 ? 90 : 50;                                // 위는 밝고 아래는 어두운 형상
                    }
                }
            var r = SilhouetteMetrics.BackgroundContrast(a, l, w, h);
            Assert.That(r.HasValue, Is.True);
            Assert.That(r.ShapePixels, Is.EqualTo(40 * 50));
            Assert.That(r.ShapeL, Is.EqualTo(70).Within(1e-9));
            Assert.That(r.BackgroundL, Is.EqualTo(70).Within(1e-9));
            Assert.That(r.DeltaL, Is.EqualTo(0).Within(1e-9), "평균 밝기는 배경과 같아도");
            Assert.That(r.ShapeLStd, Is.EqualTo(20).Within(1e-9), "안쪽 음영 차이는 따로 보인다");
            // 배경 띠는 경계 상자를 긴 변(50) × 0.25 = 13화소 넓힌 상자 안
            Assert.That(r.BackgroundPixels, Is.EqualTo((40 + 26) * (50 + 26) - 40 * 50));

            for (int i = 0; i < l.Length; i++) if (a[i] > 0) l[i] = 40;
            Assert.That(SilhouetteMetrics.BackgroundContrast(a, l, w, h).DeltaL, Is.EqualTo(-30).Within(1e-9));
            Assert.That(SilhouetteMetrics.BackgroundContrast(new float[w * h], l, w, h).HasValue, Is.False, "보이는 화소 없음");
        }
    }
}
