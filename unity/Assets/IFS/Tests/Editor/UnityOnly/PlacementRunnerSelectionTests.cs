// EditMode 테스트(Unity 전용): 배치 러너 + 선택 파일(D8·D9, 2026-11-23).
//   원본 spec(합성 예시 EX02) + 손으로 만든 합성 selection.json → 덮어쓰기가 실제 물체(SceneLoader 해석값·렌더 경로)에 반영되고
//   조건 단계 동안 바뀌지 않는지, manifest 0.2의 selection·appliedOverrides, sha 불일치·적용할 수 없는 덮어쓰기의 시작 거부,
//   선택 파일 없이 돌린 자동 시행은 예전과 같은지(selection null, appliedOverrides {}).
using System;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor.SceneManagement;

namespace IFS.SceneSpec.Tests
{
    public class PlacementRunnerSelectionTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-sel-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static string Spec => OwnershipTestSpecs.ExamplePath("EX02.json");

        string WriteSelection(JObject overrides, string sha = null, string name = "selection.json", bool none = false)
        {
            var o = new JObject
            {
                ["formatVersion"] = "ifs-selection/0.1",
                ["specSha256"] = sha ?? OwnershipManifest.Sha256OfFile(Spec),
                ["finalOverrides"] = overrides,
                ["selection"] = new JObject { ["selectedCandidateId"] = none ? null : "c2", ["none"] = none },
                ["sources"] = new JObject { ["form.type"] = "chosen", ["material.color.h"] = "edited", ["layout.size"] = "said" },
            };
            string path = Path.Combine(_tmp, name);
            File.WriteAllText(path, o.ToString(), new UTF8Encoding(false));
            return path;
        }

        [Test]
        public void Selection_overrides_are_drawn_once_and_recorded_in_manifest_0_2()
        {
            var overrides = new JObject { ["form.type"] = "fragments", ["material.color.h"] = 0.6, ["material.color.s"] = 0.5, ["material.brightness"] = 0.35 };
            string sel = WriteSelection(overrides);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.BeginAuto(new PlacementAutoScript(), PlacementTests.ShortConfig("place"));
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = Spec;
                runner.SelectionPathText = sel;
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.Selection, Is.Not.Null);
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                var p = runner.Loader.CurrentParams;
                Assert.That(p.GetCategory("form.type"), Is.EqualTo("fragments"), "덮어쓰기가 물체에 반영");
                Assert.That(p.GetNumber("material.color.h"), Is.EqualTo(0.6).Within(1e-9));
                Assert.That(p.GetNumber("material.brightness"), Is.EqualTo(0.35).Within(1e-9));
                Assert.That(p.GetNumber("layout.size"), Is.EqualTo(0.316).Within(1e-9), "말한 값은 그대로");
                Assert.That(runner.Loader.RenderPath, Is.EqualTo("fragments"));
                var root = runner.Loader.Root;
                for (int i = 0; i < 200000 && runner.Stage != PlacementRunnerStage.Done; i++)
                {
                    runner.Tick(0.02);
                    if (runner.Session != null && runner.Session.Phase == PlacementPhase.Condition)
                    {
                        Assert.That(runner.Loader.Root, Is.SameAs(root), "조건 단계 동안 형상을 다시 만들지 않는다");
                        Assert.That(runner.Loader.CurrentParams.GetCategory("form.type"), Is.EqualTo("fragments"));
                    }
                }
                Assert.That(runner.LastCompleted, Is.True);
                var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(runner.LastRecordDirectory, "manifest.json")));
                Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-placement/0.2"));
                Assert.That((string)m["selection"]["file"], Is.EqualTo("selection.json"));
                Assert.That((string)m["selection"]["sha256"], Is.EqualTo(OwnershipManifest.Sha256OfFile(sel)));
                Assert.That((string)m["selection"]["selectedCandidateId"], Is.EqualTo("c2"));
                Assert.That((bool)m["selection"]["none"], Is.False);
                Assert.That((string)m["selection"]["sources"]["material.color.h"], Is.EqualTo("edited"));
                Assert.That(((JObject)m["appliedOverrides"]).Properties().Select(x => x.Name),
                    Is.EqualTo(new[] { "form.type", "material.brightness", "material.color.h", "material.color.s" }));
                Assert.That((string)m["appliedOverrides"]["form.type"], Is.EqualTo("fragments"));
                Assert.That(File.ReadAllText(Path.Combine(runner.LastRecordDirectory, "manifest.json")), Does.Not.Contain(_tmp.Replace("\\", "\\\\")), "절대 경로 없음");
                var ev = File.ReadAllLines(Path.Combine(runner.LastRecordDirectory, "events.csv"));
                Assert.That(ev.Any(l => l.Contains(",selection,file=selection.json;none=0;candidate=c2;applied=4")), Is.True);
            }
            finally
            {
                runner.ResetForNext();
            }
        }

        [Test]
        public void Sha_mismatch_and_unapplicable_overrides_refuse_to_start()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.BeginAuto(new PlacementAutoScript(), PlacementTests.ShortConfig("view"));
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = Spec;

                runner.SelectionPathText = WriteSelection(new JObject(), sha: new string('0', 64), name: "wrong.json");
                Assert.That(runner.Check(), Is.False);
                Assert.That(runner.Errors.Any(e => e.Contains("specSha256")), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.StartSession(), Is.False);
                Assert.That(Directory.Exists(Path.Combine(_tmp, "records")), Is.False, "거부하면 기록 폴더를 만들지 않는다");

                runner.BackToSetup();
                runner.SelectionPathText = WriteSelection(new JObject { ["material.glow"] = 0.5 }, name: "unknown.json");
                Assert.That(runner.Check(), Is.False);
                Assert.That(runner.Errors.Any(e => e.Contains("material.glow")), Is.True);

                runner.BackToSetup();
                runner.SelectionPathText = WriteSelection(new JObject { ["form.type"] = "mist", ["shapeModel"] = "Cube" }, name: "shape.json");
                Assert.That(runner.Check(), Is.False);
                Assert.That(runner.Errors.Any(e => e.Contains("form.type=blob에만")), Is.True);

                runner.BackToSetup();
                runner.SelectionPathText = Path.Combine(_tmp, "missing.json");
                Assert.That(runner.Check(), Is.False);
                Assert.That(runner.Errors.Any(e => e.Contains("선택 파일이 없습니다")), Is.True);
            }
            finally
            {
                runner.ResetForNext();
            }
        }

        [Test]
        public void Auto_trial_without_selection_keeps_old_behaviour_and_with_none_selection_records_none()
        {
            string plain = PlacementExperimentMenu.RunAutoTrial(Spec, Path.Combine(_tmp, "records"), 5, PlacementTests.ShortConfig("view"), 0.02, null);
            var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(plain, "manifest.json")));
            Assert.That(m["selection"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(((JObject)m["appliedOverrides"]).Count, Is.EqualTo(0));

            string sel = WriteSelection(new JObject { ["material.opacity"] = 0.6 }, name: "none.json", none: true);
            string dir = PlacementExperimentMenu.RunAutoTrial(Spec, Path.Combine(_tmp, "records"), 6, PlacementTests.ShortConfig("place"), 0.02, null, null, sel);
            var n = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((bool)n["selection"]["none"], Is.True, "맞는 것이 없다(G23)");
            Assert.That(n["selection"]["selectedCandidateId"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((double)n["appliedOverrides"]["material.opacity"], Is.EqualTo(0.6).Within(1e-9));
        }
    }
}
