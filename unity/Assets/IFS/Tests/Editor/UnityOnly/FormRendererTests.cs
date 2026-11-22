// EditMode 테스트(Unity 전용): 형상별 렌더러(X64)를 로더 경로로 확인한다. 합성 spec만 쓴다(참여자 데이터 아님).
//   - form.type별로 어느 렌더러가 모형을 만들었는가(SceneLoader.RenderPath)
//   - 같은 슬롯 값이면 meta.mapping이 v0든 v1이든 같은 화면 구성(메시·머티리얼 프로퍼티·그림자)인가(X65)
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class FormRendererTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-form-renderer-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        /// <summary>spec 하나를 새 씬·새 로더로 불러 fn을 부른다.</summary>
        internal static T WithLoaded<T>(string tmp, JObject spec, string file, Func<SceneLoader, T> fn)
        {
            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(tmp, "sessions-" + file), out var go);
            try
            {
                Assert.That(loader.Load(spec.Write(tmp, file + ".json")), Is.True);
                return fn(loader);
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        static readonly string[] Props =
        {
            "_BaseColor", "_Brightness", "_Roughness", "_Opacity", "_Erosion", "_Lumpiness", "_NoiseScale", "_Fuzz", "_Density",
            "_ShellOpen", "_Displacement", "_Seed",
        };

        /// <summary>모형의 화면 구성(이름 제외): 메시·정점 수·변환·셰이더·프로퍼티·그림자.</summary>
        internal static string Visual(SceneLoader l)
        {
            var sb = new StringBuilder();
            string F(float v) => v.ToString("F5", CultureInfo.InvariantCulture);
            foreach (var r in l.Root.GetComponentsInChildren<Renderer>())
            {
                var mf = r.GetComponent<MeshFilter>();
                var t = r.transform;
                sb.Append(mf != null && mf.sharedMesh != null ? mf.sharedMesh.name + ":" + mf.sharedMesh.vertexCount : "nomesh")
                  .Append(" pos=").Append(t.localPosition.ToString("F5")).Append(" scale=").Append(t.lossyScale.ToString("F5"))
                  .Append(" shadow=").Append(r.shadowCastingMode);
                foreach (var m in r.sharedMaterials)
                {
                    sb.Append(" [").Append(m.shader.name);
                    foreach (var p in Props.Where(m.HasProperty))
                        sb.Append(' ').Append(p).Append('=').Append(p == "_BaseColor" ? m.GetColor(p).ToString("F5") : F(m.GetFloat(p)));
                    sb.Append(']');
                }
                sb.Append('\n');
            }
            return sb.ToString();
        }

        [TestCase("blob", "blob")]
        [TestCase("mist", "mist")]
        [TestCase("shell", "shell")]
        [TestCase("fragments", "fragments")]
        public void Each_form_type_is_built_by_its_renderer(string form, string renderPath)
        {
            var spec = OwnershipTestSpecs.Empty("RP" + form).Slot("form.type", form, "형태");
            string path = WithLoaded(_tmp, spec, "rp-" + form, l => l.RenderPath);
            Assert.That(path, Is.EqualTo(renderPath));
        }

        [Test]
        public void Shape_word_is_built_by_the_shape_model_renderer()
        {
            var spec = OwnershipTestSpecs.Empty("RPSHAPE").ShapeWord("square", "네모", 0);
            var (path, plan) = WithLoaded(_tmp, spec, "rp-shape", l => (l.RenderPath, l.RenderPlan));
            Assert.That(path, Is.EqualTo(FormRenderPlan.RendererShapeModel));
            Assert.That(plan.ShapeModel, Is.EqualTo(ShapeMapping.ModelCube));
        }

        [TestCase("mist")]
        [TestCase("fragments")]
        [TestCase("blob")]
        public void Same_slots_from_v0_and_v1_mapping_render_the_same(string form)
        {
            JObject Make(string id, string used)
            {
                var o = OwnershipTestSpecs.Empty(id).Slot("form.type", form, "형태").Slot("material.opacity", 0.6, "흐릿")
                    .Hsl(0.3, 0.5, 0.5, "초록").Slot("material.erosion", 0.2, "삭은");
                o["meta"]["specVersion"] = "2.1.0";
                o["meta"]["mapping"] = new JObject { ["requested"] = used, ["used"] = used, ["fallbackReason"] = null };
                return o;
            }
            string v0 = WithLoaded(_tmp, Make("X65V0", "v0"), "x65-v0-" + form, Visual);
            string v1 = WithLoaded(_tmp, Make("X65V1", "v1"), "x65-v1-" + form, Visual);
            Assert.That(v0, Is.Not.Empty);
            Assert.That(v1, Is.EqualTo(v0));
        }
    }
}
