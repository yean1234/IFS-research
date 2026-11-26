// EditMode 테스트(Unity 전용): G60-2·G60-3 러너 경로 — 반복 멈춤에서 바닥 고리 숨기기(stopLoopHideRings), 자동 시행의 눈높이(desktop_fixed),
// 헤드셋이 있는데 눈높이를 재지 않으면(또는 보정이 통과하지 못하면) 시작 거부, 판 앵커. 실제 헤드셋은 쓰지 않는다(리그 HeadActiveOverride).
// spec은 합성 예시(EX02).
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementRunnerStopLoopTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-loop-unity-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static PlacementConfig LoopRel()
        {
            var c = PlacementTests.ShortConfig("place");
            c.stopMode = PlacementConfig.StopModeLoop;
            c.eyeHeightMode = PlacementConfig.EyeHeightRelative;
            return c;
        }

        [Test]
        public void Auto_loop_hides_rings_only_during_stop_distance_and_records_desktop_fixed_eye()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.BeginAuto(new PlacementAutoScript(), LoopRel());
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = OwnershipTestSpecs.ExamplePath("EX02.json");
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                bool hiddenInCondition = false, shownInStop = false, sawStop = false;
                for (int i = 0; i < 400000 && runner.Session != null && !runner.Session.Finished; i++)
                {
                    runner.Tick(0.02);
                    if (runner.Session.Finished) break;
                    var ph = runner.Session.Phase;
                    bool anyRingOn = runner.Space.Rings.Any(r => r.activeSelf);
                    if (ph == PlacementPhase.Condition && !anyRingOn) hiddenInCondition = true;
                    if (ph == PlacementPhase.StopDistance) { sawStop = true; if (anyRingOn) shownInStop = true; }
                }
                Assert.That(sawStop, Is.True);
                Assert.That(hiddenInCondition, Is.False, "조건 단계에서는 고리가 보인다");
                Assert.That(shownInStop, Is.False, "반복 멈춤 단계 동안 고리를 숨긴다");
                Assert.That(runner.Space.Rings.All(r => r.activeSelf), Is.True, "끝나면 다시 보인다");
                string dir = runner.LastRecordDirectory;
                var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
                Assert.That((string)m["eyeHeight"]["source"], Is.EqualTo("desktop_fixed"), "자동 시행은 기준 눈높이 고정");
                Assert.That((string)m["stopDistance"]["mode"], Is.EqualTo("loop"));
                Assert.That(File.Exists(Path.Combine(dir, PlacementRecordWriter.StopRoundsFile)), Is.True);
            }
            finally { runner.ResetForNext(); }
        }

        [Test]
        public void Headset_without_a_passing_eye_calibration_refuses_to_start()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                var cfg = LoopRel();
                cfg.inputMode = PlacementConfig.InputModeDesktop;   // 입력은 데스크톱(컨트롤러 없이), 머리만 헤드셋 흉내
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.SetConfig(cfg);
                runner.XrRig.HeadActiveOverride = true;
                runner.ParticipantNumberText = "2";
                runner.SpecPathText = OwnershipTestSpecs.ExamplePath("EX02.json");
                runner.Check();
                Assert.That(runner.Stage, Is.EqualTo(PlacementRunnerStage.Checked));
                Assert.That(runner.EyeHeightStatus, Does.Contain("아직 재지 않음"));
                Assert.That(runner.StartSession(), Is.False, "relative인데 눈높이를 재지 않음");
                Assert.That(runner.Errors.Any(e => e.Contains("눈높이를 재지 않았습니다")), Is.True);
                Assert.That(runner.Session, Is.Null);

                // 표본을 직접 넣어 판정: 리그 HeadActiveOverride로는 추적 원점이 Floor가 아니라 실패해야 한다
                var sampler = new EyeHeightSampler(cfg);
                for (int i = 0; i < 40 && !sampler.Done; i++) sampler.Add(i * 0.05, 1.72, 2.0);
                var r = runner.FinishEyeCalibration(sampler);
                Assert.That(r.Ok, Is.False);
                Assert.That(r.Reason, Does.Contain("Floor"));
                Assert.That(runner.Errors.Any(e => e.Contains("눈높이를 재지 않았습니다")), Is.False, "다시 재면 예전 거부 줄을 지운다");
                Assert.That(runner.EyeHeightStatus, Does.Contain("보정 실패"));
                Assert.That(runner.StartSession(), Is.False, "통과하지 못한 보정으로는 시작하지 않는다");
                Assert.That(runner.Errors.Any(e => e.Contains("통과하지 못했습니다")), Is.True);
                runner.BackToSetup();
                Assert.That(runner.EyeCalibration, Is.Null, "설정으로 돌아가면 보정을 지운다");
            }
            finally
            {
                runner.XrRig.HeadActiveOverride = null;
                runner.ResetForNext();
            }
        }
    }
}
