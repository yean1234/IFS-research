// EditMode 테스트: 2단계 예시 JSON 2개가 C# 클래스로 빠짐없이 역직렬화된다.
// (Window ▸ General ▸ Test Runner ▸ EditMode ▸ Run All)
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class SceneSpecDeserializationTests
    {
        static string ExamplePath(string name) => Path.Combine(Application.streamingAssetsPath, "IFS", "examples", name);

        [TestCase("EX01.json")]
        [TestCase("EX02.json")]
        public void Example_deserializes_strictly_and_round_trips_without_loss(string name)
        {
            string raw = File.ReadAllText(ExamplePath(name));
            var spec = SceneSpecJson.Parse(raw);             // 모르는 필드·빠진 필드가 있으면 여기서 실패
            Assert.That(SceneSpecJson.Validate(spec), Is.Empty);
            var back = JToken.Parse(SceneSpecJson.Serialize(spec));
            Assert.That(JToken.DeepEquals(JToken.Parse(raw), back), Is.True, "다시 직렬화한 JSON이 원본과 다르다(빠진 필드)");
        }

        [Test]
        public void EX01_values_and_provenance()
        {
            var s = SceneSpecJson.Load(ExamplePath("EX01.json"));
            Assert.That(s.Meta.SessionId, Is.EqualTo("EX01"));
            Assert.That(s.Form.Type, Is.EqualTo("blob"));
            Assert.That(s.Form.Posture, Is.Null);
            Assert.That(s.Material.Color.H, Is.EqualTo(0.0));
            Assert.That(s.Material.Color.S, Is.EqualTo(0.05));
            Assert.That(s.Material.Color.L, Is.EqualTo(0.45));
            Assert.That(s.Material.Roughness, Is.EqualTo(0.35));
            Assert.That(s.Material.Erosion, Is.EqualTo(0.6));
            Assert.That(s.Material.Brightness, Is.Null);
            Assert.That(s.Layout.VerticalOffset, Is.EqualTo(0.72));
            Assert.That(s.Body.Part, Is.EqualTo("chest"));
            Assert.That(s.Provenance.Keys.Count, Is.EqualTo(7));
            Assert.That(s.Provenance["material.color"][0].Trigger, Is.EqualTo("회색"));
            Assert.That(s.Provenance["material.color"][0].CharSpan, Is.EqualTo(new[] { 31, 33 }));
            Assert.That(s.Alternatives.Single().Path, Is.EqualTo("material.roughness"));
            Assert.That(s.Alternatives.Single().Value.Value<double>(), Is.EqualTo(0.15));
            Assert.That(s.Unmapped.Select(u => u.Lemma), Is.EqualTo(new[] { "종이", "가장자리" }));
            Assert.That(s.Unmatched, Is.Empty);
        }

        [Test]
        public void EX02_unsaid_slots_stay_null_and_defaults_are_recorded()
        {
            var s = SceneSpecJson.Load(ExamplePath("EX02.json"));
            Assert.That(s.Form.Type, Is.Null);
            Assert.That(s.Form.Posture, Is.EqualTo("curled"));
            Assert.That(s.Layout.Size, Is.EqualTo(0.316));
            Assert.That(s.Material.Color, Is.Null);

            var p = SceneParams.FromSpec(s, new SceneDefaults());
            Assert.That(p.DefaultsUsed, Does.Contain("form.type"));
            Assert.That(p.DefaultsUsed, Does.Contain("material.color.h"));
            Assert.That(p.DefaultsUsed, Does.Not.Contain("layout.size"));
            Assert.That(p.DefaultsUsed, Does.Not.Contain("form.posture"));
            Assert.That(p.GetNumber("layout.size"), Is.EqualTo(0.316));
            Assert.That(p.InferredUsed, Is.Empty);
        }

        [Test]
        public void Unknown_field_is_rejected()
        {
            var o = JObject.Parse(File.ReadAllText(ExamplePath("EX02.json")));
            ((JObject)o["layout"])["scale"] = 1.0;
            Assert.Throws<JsonSerializationException>(() => SceneSpecJson.Parse(o.ToString()));
        }

        [Test]
        public void Missing_field_is_rejected()
        {
            var o = JObject.Parse(File.ReadAllText(ExamplePath("EX02.json")));
            ((JObject)o["material"]).Remove("erosion");
            Assert.Throws<JsonSerializationException>(() => SceneSpecJson.Parse(o.ToString()));
        }

        [Test]
        public void Adjustment_is_measured_on_the_same_0_1_scale()
        {
            var p0 = SceneParams.FromSpec(SceneSpecJson.Load(ExamplePath("EX01.json")), new SceneDefaults());
            var p1 = p0.Clone();
            p1.SetNumber("material.roughness", 0.55);
            p1.SetNumber("material.color.h", 0.95);           // 0 → 0.95는 원형으로 -0.05
            var d = SceneParams.Deltas(p0, p1);
            Assert.That(d["material.roughness"], Is.EqualTo(0.2).Within(1e-9));
            Assert.That(d["material.color.h"], Is.EqualTo(-0.05).Within(1e-9));
            Assert.That(SceneParams.ChangedCategories(p0, p1), Is.Empty);
        }

        [Test]
        public void IcoSphere_is_even_closed_and_faces_outward()
        {
            IcoSphere.Build(4, 0.5f, out float[] xyz, out int[] tris);
            Assert.That(xyz.Length / 3, Is.EqualTo(10 * 256 + 2));            // 10·4^n + 2
            Assert.That(tris.Length / 3, Is.EqualTo(20 * 256));               // 20·4^n
            for (int i = 0; i < xyz.Length; i += 3)
            {
                double r = System.Math.Sqrt(xyz[i] * xyz[i] + xyz[i + 1] * xyz[i + 1] + xyz[i + 2] * xyz[i + 2]);
                Assert.That(r, Is.EqualTo(0.5).Within(1e-5));
            }
            for (int f = 0; f < tris.Length; f += 3)                          // 앞면 = cross(b−a, c−a)가 바깥
            {
                int a = tris[f] * 3, b = tris[f + 1] * 3, c = tris[f + 2] * 3;
                double ux = xyz[b] - xyz[a], uy = xyz[b + 1] - xyz[a + 1], uz = xyz[b + 2] - xyz[a + 2];
                double vx = xyz[c] - xyz[a], vy = xyz[c + 1] - xyz[a + 1], vz = xyz[c + 2] - xyz[a + 2];
                double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                Assert.That(nx * xyz[a] + ny * xyz[a + 1] + nz * xyz[a + 2], Is.GreaterThan(0));
            }
        }

        [Test]
        public void Recorder_writes_initial_final_and_events()
        {
            string raw = File.ReadAllText(ExamplePath("EX01.json"));
            var spec = SceneSpecJson.Parse(raw);
            var root = Path.Combine(Path.GetTempPath(), "ifs-recorder-test-" + System.Guid.NewGuid().ToString("N"));
            var p0 = SceneParams.FromSpec(spec, new SceneDefaults());
            var p1 = p0.Clone();
            using (var rec = new ExperimentRecorder(root, spec.Meta.SessionId, spec, "EX01.json"))
            {
                rec.WriteInitial(p0, raw);
                p1.SetNumber("layout.size", 0.6);
                rec.RecordChange("layout.size", "0.5", "0.6", 1.234);
                rec.WriteFinal(p0, p1);
            }
            var dir = Path.Combine(root, "EX01");
            var initial = JObject.Parse(File.ReadAllText(Path.Combine(dir, "initialScene.json")));
            var final = JObject.Parse(File.ReadAllText(Path.Combine(dir, "finalScene.json")));
            var csv = File.ReadAllLines(Path.Combine(dir, "events.csv"));
            Assert.That(initial["defaultsUsed"].Values<string>(), Does.Contain("layout.size"));
            Assert.That(JToken.DeepEquals(initial["spec"], JToken.Parse(raw)), Is.True);
            Assert.That(final["deltas"]["layout.size"].Value<double>(), Is.EqualTo(0.1).Within(1e-9));
            Assert.That(final["adjustedParams"].Values<string>(), Is.EqualTo(new[] { "layout.size" }));
            Assert.That(csv[0], Is.EqualTo("time_ms,param,from,to,distance_m"));
            Assert.That(csv[1], Does.EndWith(",layout.size,0.5,0.6,1.234"));
            Directory.Delete(root, true);
        }
    }
}
