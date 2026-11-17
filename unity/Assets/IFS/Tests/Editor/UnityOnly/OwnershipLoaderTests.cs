// EditMode 테스트(Unity 전용): 변형본을 SceneLoader로 그리는 경로와 실험 러너 자동 시행.
//   - 변형 없이(null·빈 덮어쓰기) 로드하면 예전 로더와 지문이 같다(LoaderNoVariantGoldenTests의 golden).
//   - 덮어쓰기·모양 모형 강제가 계획대로 그려지고, 조정 기록(events.csv)에 남지 않는다.
//   - 자동 시행 한 바퀴가 계약 형식(설계 2.4)의 기록 폴더를 만든다.
// spec은 합성(OwnershipTestSpecs, 예시 EX02)이다.
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;
using UnityEngine.TestTools;

namespace IFS.SceneSpec.Tests
{
    public class OwnershipLoaderTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-ownership-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        [Test]
        public void Load_with_null_or_empty_variant_matches_the_golden_fingerprint()
        {
            LoaderNoVariantGoldenTests.AssertMatchesGolden(
                LoaderNoVariantGoldenTests.Fingerprint(_tmp, (l, p) => l.Load(p, null)), "Load(path, null)");
            LoaderNoVariantGoldenTests.AssertMatchesGolden(
                LoaderNoVariantGoldenTests.Fingerprint(_tmp, (l, p) => l.Load(p, new SceneOverride())), "Load(path, 빈 덮어쓰기)");
        }

        static string Rendered(SceneLoader l) => l.ShowingShapeModel ? l.Shape.Model : l.CurrentParams.GetCategory("form.type");

        [TestCase("blob-default")]
        [TestCase("round-rotating")]
        [TestCase("mist-colored")]
        public void Variants_render_as_planned_without_adjustment_records(string kind)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-" + kind);
            switch (kind)
            {
                case "round-rotating":
                    spec.ShapeWord("round", "동그란", 3).Slot("motion.type", "rotating").Slot("layout.size", 0.8).Hsl(0.6, 0.5, 0.4);
                    break;
                case "mist-colored":
                    spec.Slot("form.type", "mist").Slot("material.opacity", 0.6).Slot("motion.type", "swaying").Hsl(0.08, 0.7, 0.5);
                    break;
            }
            string path = spec.Write(_tmp, kind + ".json");
            var plan = OwnershipVariantGenerator.Generate(SceneSpecJson.Load(path), 3, new OwnershipConfig());
            Assert.That(plan.Errors, Is.Empty, string.Join("\n", plan.Errors));

            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "sessions"), out var go);   // 기록 켬: 덮어쓰기가 events.csv에 남지 않음을 본다
            try
            {
                foreach (var v in plan.Variants)
                {
                    Assert.That(loader.Load(path, v.IsOriginal ? null : v.Override), Is.True, v.Id);
                    Assert.That(JToken.DeepEquals(JObject.FromObject(loader.InitialParams.ToRecord()), JObject.FromObject(v.Params.ToRecord())), Is.True,
                        v.Id + ": 로드한 값 = 계획한 값");
                    Assert.That(Rendered(loader), Is.EqualTo(v.Rendered), v.Id + ": 그려진 것");
                    Assert.That(loader.Shape.Status == ShapeMapping.StatusForced, Is.EqualTo(v.Override.ShapeModel != null), v.Id);
                    string events = Path.Combine(loader.Recorder.Directory, "events.csv");
                    loader.Unload();
                    Assert.That(File.ReadAllLines(events), Is.EqualTo(new[] { ExperimentRecorder.CsvHeader }), v.Id + ": 덮어쓰기는 조정 기록에 남지 않는다");
                }
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Shape_model_on_a_non_blob_form_or_unknown_key_is_rejected()
        {
            string path = OwnershipTestSpecs.Empty("SYN-reject").Slot("form.type", "mist").Write(_tmp, "reject.json");
            var loader = LoaderNoVariantGoldenTests.NewLoader(Path.Combine(_tmp, "sessions"), out var go);
            try
            {
                var bad = new SceneOverride { ShapeModel = "Cube" };
                LogAssert.Expect(LogType.Error, new System.Text.RegularExpressions.Regex("변형 덮어쓰기를 적용할 수 없습니다"));
                Assert.That(loader.Load(path, bad), Is.False);
                var unknown = new SceneOverride();
                unknown.Numbers["layout.width"] = 0.5;
                LogAssert.Expect(LogType.Error, new System.Text.RegularExpressions.Regex("수치 키가 아님"));
                Assert.That(loader.Load(path, unknown), Is.False);
            }
            finally
            {
                loader.Unload();
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Auto_trial_writes_a_contract_record_folder()
        {
            string spec = OwnershipTestSpecs.ExamplePath("EX02.json");
            var cfg = new OwnershipConfig { viewSeconds = 0.4, headSampleHz = 20 };
            string dir = OwnershipExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 4, cfg, 0.02, null);
            Assert.That(dir.Replace('\\', '/'), Does.Contain("/ownership/P004/EX02/"));

            var manifest = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((string)manifest["specFile"], Is.EqualTo("EX02.json"));
            Assert.That((string)manifest["headSource"], Is.EqualTo("desktop"));
            var order = manifest["order"].Select(t => (string)t).ToArray();
            Assert.That(order, Is.EqualTo(WilliamsDesign.OrderFor(4)));

            var head = File.ReadAllLines(Path.Combine(dir, "headpose.csv"));
            Assert.That(head[0], Is.EqualTo(OwnershipRecordWriter.HeadposeHeader));
            var viewing = head.Skip(1).Select(l => l.Split(',')).Where(c => c[1] == "viewing").ToList();
            foreach (var id in order)
            {
                var rows = viewing.Where(c => c[3] == id).ToList();
                Assert.That(rows.Count, Is.InRange(6, 10), id + ": 0.4 s, dt 0.02에서 표본 간격 60 ms(프레임당 최대 1개) ≈ 7개");
                Assert.That(rows.All(c => c[14].Length > 0 && c[15].Length > 0), Is.True, id + ": 거리·각 기록");
            }
            Assert.That(head.Skip(1).Select(l => l.Split(',')[1]).Distinct().OrderBy(x => x), Is.EqualTo(new[] { "difference", "final", "rating", "viewing" }));

            var ratings = File.ReadAllLines(Path.Combine(dir, "ratings.csv"));
            Assert.That(ratings[0], Is.EqualTo(OwnershipRecordWriter.RatingsHeader));
            Assert.That(ratings.Length, Is.EqualTo(1 + 5 + 1), "5개 + 취소 1개");
            Assert.That(ratings.Count(l => l.EndsWith(",1")), Is.EqualTo(1));
            Assert.That(ratings[2], Does.StartWith("2," + order[1] + ",7,"), "위치 2에서 잘못 누른 7을 취소");
            Assert.That(File.ReadAllLines(Path.Combine(dir, "difference.csv")).Length, Is.EqualTo(1 + 4));

            var summary = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "summary.json")));
            Assert.That((bool)summary["completed"], Is.True);
            Assert.That((string)summary["finalChoice"]["variant"], Is.EqualTo("orig"));
            Assert.That(((JObject)summary["ratings"]).Count, Is.EqualTo(5));
            var events = File.ReadAllLines(Path.Combine(dir, "events.csv"));
            Assert.That(events[0], Is.EqualTo(OwnershipRecordWriter.EventsHeader));
            Assert.That(events.Any(e => e.Contains(",rating_cancel,")), Is.True);
            Assert.That(events.Last(), Does.Contain(",done,completed"));
        }

        // 제시 중 0.3초 밀린 프레임 하나: 표본은 그 프레임의 실제 시각에 하나만(과거 시각 복제 없음). 형상마다 viewing_start가 첫 표본보다 먼저.
        [Test]
        public void Auto_trial_with_a_long_frame_writes_one_real_time_sample_and_viewing_start_events()
        {
            string spec = OwnershipTestSpecs.ExamplePath("EX02.json");
            var cfg = new OwnershipConfig { viewSeconds = 0.6, headSampleHz = 20 };
            bool lagged = false;
            double DtFor(OwnershipRunner r)
            {
                if (!lagged && r.Phase == OwnershipPhase.Viewing && r.Position == 2 && r.SecondsInPhase >= 0.1) { lagged = true; return 0.3; }
                return 0.02;
            }
            string dir = OwnershipExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 5, cfg, 0.02, null, DtFor);
            Assert.That(lagged, Is.True);
            var order = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")))["order"].Select(t => (string)t).ToArray();

            var head = File.ReadAllLines(Path.Combine(dir, "headpose.csv")).Skip(1).Select(l => l.Split(',')).ToList();
            var times = head.Select(c => long.Parse(c[0])).ToList();
            for (int i = 1; i < times.Count; i++) Assert.That(times[i], Is.GreaterThan(times[i - 1]), "표본 시각이 겹치거나 거꾸로 가지 않는다");

            var events = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(',')).ToList();
            for (int p = 1; p <= order.Length; p++)
            {
                var starts = events.Where(c => c[1] == "viewing_start" && c[2] == $"position={p};variant={order[p - 1]}").ToList();
                Assert.That(starts.Count, Is.EqualTo(1), "position " + p);
                var view = head.Where(c => c[1] == "viewing" && c[2] == p.ToString()).Select(c => long.Parse(c[0])).ToList();
                Assert.That(view.Count, Is.GreaterThan(0));
                Assert.That(long.Parse(starts[0][0]), Is.LessThanOrEqualTo(view[0]), "제시 시작 ≤ 첫 표본");
                var gaps = view.Zip(view.Skip(1), (a, b) => b - a).ToList();
                Assert.That(gaps.All(g => g >= 49), Is.True, $"position {p}: 간격 {string.Join(",", gaps)}");
                if (p == 2) Assert.That(gaps.Max(), Is.GreaterThanOrEqualTo(300), "밀린 프레임은 빈 간격으로 남는다(채우지 않음)");
                else Assert.That(gaps.Max(), Is.LessThan(150));
            }
        }
    }
}
