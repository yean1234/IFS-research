// EditMode 테스트(Unity 전용): CP10 G41 — 저장된 이전 판 파일(docs/validation/legacy-files/: spec 2.0.0·2.1.0·2.2.0(builder 2.2.0),
// ifs-selection/0.1 두 개와 D6 직후 0.2 하나, 모두 합성)을 실제 배치 러너(PlacementRunner → SceneLoader)에 넣어 자동 시행을 끝까지 돌린다.
// 덮어쓰기가 물체에 반영되고 manifest(ifs-placement/0.2)의 selection·appliedOverrides에 남는지 본다.
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class LegacyFilesRunnerTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-legacy-files-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        [Test]
        public void Legacy_spec_and_selection_files_run_through_the_placement_runner()
        {
            string dir = LegacyFilesTests.Dir;
            if (!Directory.Exists(dir)) Assert.Ignore("docs/validation/legacy-files 없음: " + dir);
            int participant = 31;
            foreach (var (sel, spec, format, specVersion) in LegacyFilesTests.Pairs)
            {
                string selPath = Path.Combine(dir, sel), specPath = Path.Combine(dir, spec);
                string rec = PlacementExperimentMenu.RunAutoTrial(specPath, Path.Combine(_tmp, "records"), participant++,
                    PlacementTests.ShortConfig("place"), 0.02, null, null, selPath);
                var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(rec, "manifest.json")));
                Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-placement/0.2"), sel);
                Assert.That((string)m["selection"]["formatVersion"], Is.EqualTo(format), sel);
                Assert.That((string)m["selection"]["sha256"], Is.EqualTo(OwnershipManifest.Sha256OfFile(selPath)), sel);
                var want = JObject.Parse(File.ReadAllText(selPath))["finalOverrides"] as JObject;
                var applied = (JObject)m["appliedOverrides"];
                Assert.That(applied.Properties().Select(p => p.Name).OrderBy(x => x, StringComparer.Ordinal),
                    Is.EqualTo(want.Properties().Select(p => p.Name).OrderBy(x => x, StringComparer.Ordinal)), sel);
                foreach (var p in want.Properties())
                {
                    if (p.Value.Type == JTokenType.String) Assert.That((string)applied[p.Name], Is.EqualTo((string)p.Value), sel + " " + p.Name);
                    else Assert.That((double)applied[p.Name], Is.EqualTo((double)p.Value).Within(1e-9), sel + " " + p.Name);
                }
                Assert.That(File.ReadAllText(Path.Combine(rec, "manifest.json")), Does.Not.Contain(dir.Replace("\\", "\\\\")), "절대 경로 없음");
            }
        }
    }
}
