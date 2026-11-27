// EditMode 테스트(Unity 전용, G72): 로더가 x·y·z 비율(layout.proportions)을 실제 변환에 넣는지. 합성 spec만 쓴다(참여자 데이터 아님).
//   - 안개: 대리 구의 국소 배율 비 = 비율(넓게 펼쳐진 안개), 가장 긴 변은 비율 없는 2.2 안개와 같다
//   - 기본 덩어리(길쭉, axisSaid = false): defaultsUsed에 layout.proportions.axis
//   - fragments: 균일 배율(조각을 찌그러뜨리지 않음), 가장 긴 변 그대로
//   - 2.4 null 문서: 변환이 2.2와 같다
using System;
using System.IO;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class ProportionsLoaderTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-prop-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        T With<T>(string json, string name, Func<SceneLoader, T> fn)
        {
            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "sessions-" + name), out var go);
            try
            {
                Assert.That(loader.LoadJson(json, name + ".json"), Is.True);
                return fn(loader);
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        static Transform Model(SceneLoader l) => l.Root.GetComponentsInChildren<MeshFilter>()[0].transform;

        [Test]
        public void Wide_mist_is_a_flat_sheet_with_the_same_longest_edge()
        {
            var round = With(BaseShapeTests.Spec22("mist", null), "mist22", l => Model(l).localScale);
            var wide = With(ProportionsTests.Spec24("mist", new[] { 1.0, 0.3, 1.0 }), "mist24", l =>
            {
                Assert.That(l.RenderPath, Is.EqualTo(FormRenderPlan.RendererMist));
                Assert.That(l.ProportionsLongestEdgeM, Is.Not.Null);
                var b = l.ObjectLocalBoundsM();
                Assert.That(b[1] / b[0], Is.EqualTo(0.3).Within(1e-4));
                return Model(l).localScale;
            });
            Assert.That(wide.y / wide.x, Is.EqualTo(0.3f).Within(1e-4f));
            Assert.That(wide.x, Is.EqualTo(round.x).Within(1e-5f), "가장 긴 변은 크기만 정함");
        }

        [Test]
        public void Null_24_mist_draws_like_22()
        {
            var a = With(BaseShapeTests.Spec22("mist", null), "a22", l => Model(l).localScale);
            var b = With(ProportionsTests.Spec24("mist"), "a24", l =>
            {
                Assert.That(l.InitialParams.DefaultsUsed, Does.Contain(ProportionsRender.Key));
                return Model(l).localScale;
            });
            Assert.That(b, Is.EqualTo(a));
        }

        [Test]
        public void Elongated_blob_without_axis_records_the_axis_default()
        {
            With(ProportionsTests.Spec24(null, new[] { 0.4, 1.0, 0.4 }, axisSaid: false), "blob24", l =>
            {
                Assert.That(l.InitialParams.DefaultsUsed, Does.Contain(ProportionsRender.AxisKey));
                var s = Model(l).localScale;
                Assert.That(s.x / s.y, Is.EqualTo(0.4f).Within(1e-4f));
                return true;
            });
        }

        [Test]
        public void Fragments_keep_pieces_and_longest_edge()
        {
            var a = With(BaseShapeTests.Spec22("fragments", null), "f22", l => l.ObjectLocalBoundsM());
            var b = With(ProportionsTests.Spec24("fragments", new[] { 1.0, 0.3, 1.0 }), "f24", l =>
            {
                var s = Model(l).localScale;
                Assert.That(s.x, Is.EqualTo(s.y).Within(1e-6f), "균일 배율(조각 배치만 늘임)");
                return l.ObjectLocalBoundsM();
            });
            double La = Math.Max(a[0], Math.Max(a[1], a[2])), Lb = Math.Max(b[0], Math.Max(b[1], b[2]));
            Assert.That(Lb, Is.EqualTo(La).Within(1e-4));
            Assert.That(b[1] / b[0], Is.LessThan(a[1] / a[0]));
        }
    }
}
