// EditMode 테스트(Unity 전용): 배치 실험 러너의 헤드셋 경로(2026-11-23).
//   XR 헤드셋 유무에 따른 입력 고르기(리그 HeadActiveOverride로 흉내), 가짜 컨트롤러로 XR 입력이 세션에 들어가는지,
//   참여자 판(자리·평정 기준점 줄), 평정 동안 물체 숨기기, scaleA 문구 파일 자동 시행, 씬 구성(리그 아래 카메라).
// 실제 헤드셋은 쓰지 않는다(헤드셋에서 확인할 것은 docs/headset-checklist.md). spec은 합성 예시(EX02).
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementRunnerXrTests
    {
        string _tmp;

        sealed class FakeController : IXrControllerSource
        {
            public XrControllerSample Next = XrControllerSample.None;
            public int Reads;
            public string DeviceName => Next.Valid ? "fake controller" : null;
            public XrControllerSample Read() { Reads++; return Next; }
        }

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-xr-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static PlacementRunner NewRunner()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            return PlacementExperimentMenu.BuildObjects();
        }

        PlacementRunner Prepare(PlacementConfig cfg, bool headActive, FakeController controller)
        {
            var runner = NewRunner();
            runner.SetRecordRoot(Path.Combine(_tmp, "records"));
            runner.SetConfig(cfg);
            runner.XrRig.HeadActiveOverride = headActive;
            if (controller != null) runner.XrInput.SetSource(controller);
            runner.ParticipantNumberText = "5";
            runner.SpecPathText = OwnershipTestSpecs.ExamplePath("EX02.json");
            return runner;
        }

        [Test]
        public void Scene_puts_the_camera_under_the_xr_rig_at_eye_height_and_wires_xr_parts()
        {
            var runner = NewRunner();
            try
            {
                Assert.That(runner.XrRig, Is.Not.Null);
                Assert.That(runner.XrInput, Is.Not.Null);
                Assert.That(runner.Panel, Is.Not.Null);
                var cam = runner.XrRig.Head;
                Assert.That(cam, Is.Not.Null);
                Assert.That(cam.parent, Is.EqualTo(runner.XrRig.transform), "카메라는 리그의 자식(추적 공간 = 리그)");
                Assert.That(cam.position.y, Is.EqualTo(1.6f).Within(1e-4f));
                Assert.That(runner.XrRig.transform.position, Is.EqualTo(Vector3.zero), "리그 원점 = '나'의 자리");
                Assert.That(cam.GetComponent<HeadPoseProvider>(), Is.Not.Null);
                runner.XrRig.HeadActiveOverride = false;
                Assert.That(runner.XrRig.Recenter(), Is.Null, "XR이 없으면 정면 재설정은 아무것도 하지 않는다");
                Assert.That(runner.Recenter(), Is.Null);
                Assert.That(runner.LastRecenterMessage, Does.Contain("XR 헤드셋이 없어"));
            }
            finally { runner.ResetForNext(); }
        }

        [Test]
        public void Without_a_headset_auto_falls_back_to_desktop_and_forced_xr_refuses()
        {
            var runner = Prepare(new PlacementConfig { condition = "view", baselineSeconds = 1, conditionSeconds = 2 }, false, new FakeController());
            try
            {
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.ActiveInputSource, Is.EqualTo("desktop"));
                Assert.That(runner.Input, Is.InstanceOf<DesktopPlacementInput>());
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                var m = JObject.Parse(File.ReadAllText(Path.Combine(runner.LastRecordDirectory, "manifest.json")));
                Assert.That((string)m["inputSource"], Is.EqualTo("desktop"));
                Assert.That((string)m["config"]["inputMode"], Is.EqualTo("auto"));
                runner.PressAbort();
                runner.ResetForNext();

                runner.SetConfig(new PlacementConfig { condition = "view", inputMode = "xr" });
                runner.ParticipantNumberText = "5";
                runner.SpecPathText = OwnershipTestSpecs.ExamplePath("EX02.json");
                Assert.That(runner.Check(), Is.False, "강제 xr인데 헤드셋이 없으면 시작하지 않는다");
                Assert.That(runner.Errors.Any(e => e.Contains("XR 헤드셋이 없습니다")), Is.True, string.Join("; ", runner.Errors));
            }
            finally { runner.ResetForNext(); }
        }

        [Test]
        public void With_a_headset_auto_uses_the_xr_controller_and_its_frames_reach_the_session()
        {
            var ctrl = new FakeController();
            var cfg = new PlacementConfig { condition = "place", baselineSeconds = 0.2, conditionSeconds = 3, stopItiSeconds = 0.2 };
            var runner = Prepare(cfg, true, ctrl);
            try
            {
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.ActiveInputSource, Is.EqualTo("xr"));
                Assert.That(runner.Warnings.Any(w => w.Contains("컨트롤러")), Is.True, "컨트롤러가 없으면 경고(시작은 됨)");
                ctrl.Next = new XrControllerSample { Valid = true, HasPose = true, Trigger = 0, RayOrigin = new PVec3(0.2, 1.2, 0.2), RayDirection = new PVec3(0, 0, 1) };
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                string dir = runner.LastRecordDirectory;
                var m = JObject.Parse(File.ReadAllText(Path.Combine(dir, "manifest.json")));
                Assert.That((string)m["inputSource"], Is.EqualTo("xr"));
                runner.PressConfirm();   // intro → baseline
                var s = runner.Session;
                for (int i = 0; i < 2000 && s.Phase != PlacementPhase.Condition; i++)
                {
                    runner.Tick(0.02);
                    if (s.Phase == PlacementPhase.PreItems) { s.PressDigit(4); runner.PressConfirm(); }
                    if (s.Phase == PlacementPhase.PreWait) runner.PressConfirm();
                }
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Condition));
                int before = ctrl.Reads;
                var origin = new PVec3(0.2, 1.2, 0.2);
                var dirToObj = (s.ObjectPosition - origin).Normalized;
                ctrl.Next = new XrControllerSample { Valid = true, HasPose = true, Trigger = 1.0, RayOrigin = origin, RayDirection = dirToObj };
                runner.Tick(0.02);
                Assert.That(ctrl.Reads, Is.GreaterThan(before), "러너가 XR 입력을 읽는다");
                Assert.That(s.Held, Is.True, "가짜 트리거로 잡힘");
                ctrl.Next = new XrControllerSample { Valid = true, HasPose = true, Trigger = 1.0, StickY = 1.0, RayOrigin = origin, RayDirection = dirToObj };
                for (int i = 0; i < 25; i++) runner.Tick(0.02);
                Assert.That(s.HoldDistanceM, Is.GreaterThan(1.6), "썸스틱 앞 = 밀기");
                var p = runner.Loader.Root.transform.position;
                Assert.That(p.z, Is.EqualTo((float)s.ObjectPosition.Z).Within(1e-4f), "러너가 세션 위치대로 그린다");
                runner.PressAbort();
                var ev = File.ReadAllLines(Path.Combine(dir, "events.csv"));
                Assert.That(ev.Any(l => l.Contains(",xr_status,") && l.Contains("hand=right")), Is.True, "XR로 시작하면 장치·손·추적 원점을 events에 남긴다");
                Assert.That(ev.Any(l => l.Contains(",grab,")), Is.True);
            }
            finally { runner.ResetForNext(); }
        }

        [Test]
        public void Participant_panel_sits_in_front_below_eye_height_and_shows_the_rating_scale()
        {
            var cfg = PlacementTests.ShortConfig("view");
            cfg.hideObjectDuringItems = true;
            var runner = NewRunner();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.SelectTaskText(PlacementXrTests.ScaleARelativePath);
                runner.BeginAuto(new PlacementAutoScript(), cfg);
                runner.ParticipantNumberText = "2";
                runner.SpecPathText = OwnershipTestSpecs.ExamplePath("EX02.json");
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                var panel = runner.Panel;
                Assert.That(panel.Visible, Is.True);
                Assert.That(panel.CurrentText, Is.EqualTo(runner.Session.ParticipantText), "intro 글");
                var c = panel.PanelCenter;
                Assert.That(c.z, Is.EqualTo(2.0f).Within(1e-4f), "정면 약 2 m");
                Assert.That(c.y, Is.LessThan(1.2f), "눈높이(1.6)·물체 시작 높이(1.2)보다 아래");
                var s = runner.Session;
                for (int i = 0; i < 100000 && !(s.Phase == PlacementPhase.PreItems && s.CurrentItem != null); i++) runner.Tick(0.02);
                Assert.That(s.CurrentItem?.Key, Is.EqualTo("A1"), "지시문 뒤 첫 문항");
                Assert.That(panel.CurrentText, Is.EqualTo(s.CurrentItem.Text), "판에는 문항 글(기준점은 아래 줄)");
                Assert.That(panel.PanelSizeM.x, Is.GreaterThanOrEqualTo(7 * 0.2f), "7점 기준점 줄이 들어갈 너비");
                Assert.That(runner.Loader.Root.activeSelf, Is.False, "hideObjectDuringItems: 평정 동안 물체 숨김");
                for (int i = 0; i < 200000 && runner.Stage != PlacementRunnerStage.Done; i++) runner.Tick(0.02);
                Assert.That(runner.LastCompleted, Is.True);
                var rows = File.ReadAllLines(Path.Combine(runner.LastRecordDirectory, "ratings.csv")).Skip(1).ToList();
                Assert.That(rows.Count, Is.EqualTo(23), "scaleA: 사전 11 + 사후 12(G13 두 문항 포함)");
            }
            finally { runner.ResetForNext(); }
        }

        [Test]
        public void Auto_trial_with_the_scaleA_file_completes()
        {
            string dir = PlacementExperimentMenu.RunAutoTrial(OwnershipTestSpecs.ExamplePath("EX02.json"), Path.Combine(_tmp, "records"), 9,
                PlacementTests.ShortConfig("place"), 0.02, null, PlacementXrTests.ScaleARelativePath);
            var m = JObject.Parse(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((string)m["taskText"]["file"], Is.EqualTo("placement_task.scaleA.v0.json"));
            Assert.That((string)m["inputSource"], Is.EqualTo("auto"));
            Assert.That(File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Length - 1, Is.EqualTo(23), "사전 11 + 사후 12(G13 두 문항 포함)");
        }
    }
}
