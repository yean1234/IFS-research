// EditMode 테스트(Unity 전용): 배치 실험 러너 — 확정 spec의 물체(SceneLoader, 변형 없음)로 자동 시행 한 바퀴,
// replay 왕복, '나' 기준 공간(고리 끄기), 경계 clamp가 Unity 물체 위치에 그대로 반영되는지. spec은 합성 예시(EX02)다.
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementRunnerTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static PlacementConfig Short(string condition, string mode = PlacementConfig.ModeStatic) => PlacementTests.ShortConfig(condition, mode);

        [Test]
        public void Auto_trial_place_then_view_replay_write_contract_folders()
        {
            string spec = OwnershipTestSpecs.ExamplePath("EX02.json");
            string place = PlacementExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 3, Short("place"), 0.02, null);
            Assert.That(place.Replace('\\', '/'), Does.Contain("/placement/P003/EX02/"));
            foreach (var f in PlacementRecordWriter.AllFiles) Assert.That(File.Exists(Path.Combine(place, f)), Is.True, f);
            var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(place, "manifest.json")));
            Assert.That((string)m["specFile"], Is.EqualTo("EX02.json"));
            Assert.That((string)m["headSource"], Is.EqualTo("desktop"));
            Assert.That((string)m["inputSource"], Is.EqualTo("auto"));
            Assert.That((string)m["unityVersion"], Is.Not.Empty);
            Assert.That((double)m["object"]["boundingRadiusM"], Is.GreaterThan(0.05).And.LessThan(1.0), "물체 렌더 경계 반지름(EX02 size 0.316)");
            Assert.That((bool)m["flags"]["layoutIgnored"], Is.False, "EX02는 layout.distance·verticalOffset이 null");
            Assert.That((string)m["space"]["startPlacementSource"], Is.EqualTo("experiment_config"));
            var pl = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(place, "placement.json")));
            Assert.That((int)pl["grabCount"], Is.EqualTo(2), "물체 경계로 정한 잡기 구에 광선이 맞는다");
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.6).Within(1e-3));

            var cfg = Short("view", PlacementConfig.ModeReplay);
            cfg.replayPath = Path.Combine(place, "trajectory.json");
            string view = PlacementExperimentMenu.RunAutoTrial(spec, Path.Combine(_tmp, "records"), 4, cfg, 0.02, null);
            var vm = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(view, "manifest.json")));
            Assert.That((string)vm["controlMode"], Is.EqualTo("replay"));
            Assert.That((string)vm["replaySource"]["file"], Is.EqualTo("trajectory.json"));
            Assert.That((string)vm["replaySource"]["sha256"], Is.EqualTo(Ownership.OwnershipManifest.Sha256OfFile(cfg.replayPath)));
            Assert.That(File.ReadAllText(Path.Combine(view, "manifest.json")), Does.Not.Contain(_tmp.Replace("\\", "\\\\")), "절대 경로 없음");
            var vpl = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(view, "placement.json")));
            Assert.That((double)vpl["finalDistanceM"], Is.EqualTo((double)pl["finalDistanceM"]).Within(1e-3));
        }

        [Test]
        public void Runner_draws_the_object_where_the_session_puts_it()
        {
            string spec = OwnershipTestSpecs.ExamplePath("EX02.json");
            UnityEditor.SceneManagement.EditorSceneManager.NewScene(UnityEditor.SceneManagement.NewSceneSetup.EmptyScene, UnityEditor.SceneManagement.NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.BeginAuto(new PlacementAutoScript(), Short("view", PlacementConfig.ModeSystemMove));
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = spec;
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.Warnings.Any(w => w.Contains("초안 문구")), Is.True, "draft 경고가 Setup 확인에 뜬다");
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.Loader.Root.activeSelf, Is.False, "intro에서는 숨김");
                for (int i = 0; i < 100000 && runner.Session.Phase != PlacementPhase.Condition; i++) runner.Tick(0.02);
                for (int i = 0; i < 300; i++) runner.Tick(0.02);   // 조건 단계 6초: 시스템 이동 중
                var s = runner.Session;
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Condition));
                Assert.That(runner.Loader.Root.activeSelf, Is.True);
                var p = runner.Loader.Root.transform.position;
                Assert.That(new[] { p.x, p.y, p.z }, Is.EqualTo(new[] { (float)s.ObjectPosition.X, (float)s.ObjectPosition.Y, (float)s.ObjectPosition.Z }).Within(1e-5));
                Assert.That(p.z, Is.GreaterThan(1.5f), "목표(2.5 m) 쪽으로 움직였다");
                Assert.That(runner.Space.Rings.Count, Is.EqualTo(3));
                runner.PressAbort();
                Assert.That(runner.Stage, Is.EqualTo(PlacementRunnerStage.Done));
                Assert.That(runner.LastCompleted, Is.False);
            }
            finally
            {
                runner.ResetForNext();
            }
        }

        [Test]
        public void Space_has_disc_boundary_self_marker_and_optional_rings()
        {
            var cfg = new PlacementConfig();
            var h = PlacementSpace.Build(cfg);
            try
            {
                Assert.That(h.Floor, Is.Not.Null);
                Assert.That(h.Boundary, Is.Not.Null);
                Assert.That(h.SelfMarker, Is.Not.Null);
                Assert.That(h.Rings.Count, Is.EqualTo(3));
                var b = h.Floor.GetComponent<Renderer>().bounds;
                Assert.That(b.extents.x, Is.EqualTo(4f).Within(1e-3f), "반지름 4 m");
                Assert.That(b.max.y, Is.EqualTo(0f).Within(1e-4f), "바닥 윗면 y = 0");
                Assert.That(h.Floor.GetComponent<Collider>() == null, Is.True, "충돌체 없음(물리 안 씀)");
            }
            finally { h.Dispose(); }
            cfg.showRings = false;
            var h2 = PlacementSpace.Build(cfg);
            try { Assert.That(h2.Rings.Count, Is.EqualTo(0), "showRings로 끈다"); }
            finally { h2.Dispose(); }
        }
    }
}
