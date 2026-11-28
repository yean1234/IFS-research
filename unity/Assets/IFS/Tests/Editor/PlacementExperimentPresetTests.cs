// 본 실험 권고 설정 묶음(설계 뼈대 3절, docs/design-backbone.md · 결정 G59-8 · G63) — PlacementConfig.ApplyExperimentPreset,
// 자동 시행 -experimentPreset, 그리고 그 설정으로 두 조건이 끝까지 도는지. 기본값은 그대로여야 한다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementExperimentPresetTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-exp-preset-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        [Test]
        public void Default_config_is_not_the_preset_and_preset_turns_on_recommended_values_only()
        {
            var def = new PlacementConfig();
            Assert.That(def.ExperimentPresetOn, Is.False, "코드 기본값은 바꾸지 않는다(뼈대 3절)");

            var cfg = new PlacementConfig();
            cfg.ApplyExperimentPreset();
            Assert.That(cfg.ExperimentPresetOn, Is.True);
            Assert.That(cfg.environment, Is.EqualTo(PlacementConfig.EnvironmentNeutral), "공간 B");
            Assert.That(cfg.placementAssist && cfg.practiceInAllConditions && cfg.checkBeforeStopDistance && cfg.hideObjectDuringItems, Is.True);
            Assert.That(cfg.UiBundleOn, Is.True);
            Assert.That(cfg.stopMode, Is.EqualTo(PlacementConfig.StopModeLoop), "반복 멈춤(G60-2·G60-4)");
            Assert.That(cfg.eyeHeightMode, Is.EqualTo(PlacementConfig.EyeHeightRelative), "눈높이 기준 배치(G60-3)");
            Assert.That(def.stopMode, Is.EqualTo(PlacementConfig.StopModeSingle), "기본값 그대로");
            Assert.That(def.eyeHeightMode, Is.EqualTo(PlacementConfig.EyeHeightNone), "기본값 그대로");
            Assert.That(cfg.conditionEndsOnConfirm, Is.True, "직접 배치는 확인으로 끝남(G86)");
            Assert.That(def.conditionEndsOnConfirm, Is.False, "기본값 그대로");
            // 그 밖의 것은 그대로
            Assert.That(cfg.condition, Is.EqualTo(def.condition));
            Assert.That(cfg.controlMode, Is.EqualTo(def.controlMode));
            Assert.That(cfg.stopLoopRounds, Is.EqualTo(def.stopLoopRounds));
            Assert.That(cfg.eyeHeightReferenceM, Is.EqualTo(def.eyeHeightReferenceM));
            Assert.That(cfg.hidePanelInDistancePhases, Is.False);
            Assert.That(cfg.conditionSeconds, Is.EqualTo(def.conditionSeconds));
            foreach (var cond in PlacementConfig.Conditions)
            {
                var c = cfg.Clone();
                c.condition = cond;
                Assert.That(c.Validate(), Is.Empty, cond);
                Assert.That(c.HasPractice, Is.True, cond + ": 두 집단 모두 연습");
            }
        }

        [Test]
        public void Command_line_preset_then_single_flags_override_and_task_text_defaults_to_scaleA()
        {
            var cfg = IFS.SceneSpec.EditorTools.PlacementExperimentMenu.ConfigFromArgs(new[] { "x", "-experimentPreset", "true", "-hideObjectDuringItems", "false" });
            Assert.That(cfg.placementAssist && cfg.practiceInAllConditions && cfg.checkBeforeStopDistance && cfg.UiBundleOn, Is.True);
            Assert.That(cfg.hideObjectDuringItems, Is.False, "낱개 인자가 묶음을 덮어쓴다");
            Assert.That(cfg.IsStopLoop && cfg.IsEyeRelative, Is.True);
            var over = IFS.SceneSpec.EditorTools.PlacementExperimentMenu.ConfigFromArgs(new[] { "x", "-experimentPreset", "true", "-stopMode", "single", "-eyeHeightMode", "none" });
            Assert.That(over.IsStopLoop || over.IsEyeRelative, Is.False, "낱개 인자가 덮어쓴다");
            Assert.That(over.ExperimentPresetOn, Is.False);
            Assert.That(IFS.SceneSpec.EditorTools.PlacementExperimentMenu.ConfigFromArgs(new[] { "x" }).ExperimentPresetOn, Is.False);

            Assert.That(IFS.SceneSpec.EditorTools.PlacementExperimentMenu.TaskTextFileFromArgs(new[] { "x", "-experimentPreset", "true" }),
                Is.EqualTo(PlacementConfig.ExperimentTaskTextFile));
            Assert.That(IFS.SceneSpec.EditorTools.PlacementExperimentMenu.TaskTextFileFromArgs(new[] { "x", "-experimentPreset", "true", "-taskTextFile", "IFS/placement_task.v0.json" }),
                Is.EqualTo("IFS/placement_task.v0.json"));
            Assert.That(IFS.SceneSpec.EditorTools.PlacementExperimentMenu.TaskTextFileFromArgs(new[] { "x" }), Is.Null);
        }

        [Test]
        public void Preset_task_text_file_exists_and_loads()
        {
            var text = PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementConfig.ExperimentTaskTextFile));
            Assert.That(text.Items.Any(i => i.Key == "place_fit"), Is.True, "자리 문항(G59)");
            var cfg = new PlacementConfig();
            cfg.ApplyExperimentPreset();
            Assert.That(cfg.UnknownDisabledItems(text), Is.Empty);
        }

        [Test]
        public void Preset_runs_both_conditions_with_practice_check_before_stop_hidden_object_loop_and_eye_height()
        {
            var text = PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementConfig.ExperimentTaskTextFile));
            foreach (var cond in PlacementConfig.Conditions)
            {
                var cfg = PlacementTests.ShortConfig(cond);
                cfg.ApplyExperimentPreset();
                string dir = Run(cfg, text);
                var events = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(new[] { ',' }, 3)).ToList();
                var phases = events.Where(e => e[1] == "phase").Select(e => e[2]).ToList();
                Assert.That(phases, Does.Contain("practice"), cond + ": 연습(두 집단)");
                Assert.That(phases.IndexOf("check_items"), Is.LessThan(phases.IndexOf("stop_distance")), cond + ": 자리 문항 → 멈춤 거리");
                Assert.That(phases.IndexOf("check_items"), Is.GreaterThan(phases.IndexOf("post_items")), cond);
                var objPhases = File.ReadAllLines(Path.Combine(dir, PlacementRecordWriter.ObjposeFile)).Skip(1).Select(l => l.Split(',')[1]).Distinct().ToList();
                Assert.That(objPhases.Intersect(new[] { "pre_items", "post_items", "check_items" }), Is.Empty, cond + ": 평정 동안 물체 숨김");
                var manifest = JObject.Parse(File.ReadAllText(Path.Combine(dir, PlacementRecordWriter.ManifestFile)));
                var c = (JObject)manifest["config"];
                Assert.That((bool)c["checkBeforeStopDistance"] && (bool)c["practiceInAllConditions"] && (bool)c["hideObjectDuringItems"], Is.True, cond);
                Assert.That((string)c["environment"], Is.EqualTo("neutral"));
                Assert.That((bool)c["placementAssist"] && (bool)c["uiComfortWrap"], Is.True);
                Assert.That((string)c["stopMode"], Is.EqualTo("loop"), cond);
                Assert.That((string)c["eyeHeightMode"], Is.EqualTo("relative"), cond);
                Assert.That((string)manifest["stopDistance"]["mode"], Is.EqualTo("loop"), cond);
                Assert.That((string)manifest["eyeHeight"]["source"], Is.EqualTo(EyeHeightInfo.SourceDesktopFixed), cond + ": 자동 시행은 보정 없이 기준값");
                foreach (var f in PlacementRecordWriter.LoopFiles)
                    Assert.That(File.ReadAllLines(Path.Combine(dir, f)).Length, Is.GreaterThan(1), cond + ": " + f);
                Assert.That(events.Any(e => e[1] == "eye_height_calibrated"), Is.True, cond);
                // G86: 직접 배치는 확인으로, 보기만은 제한 시간으로 끝난다
                Assert.That((bool)c["conditionEndsOnConfirm"], Is.True, cond);
                var pl = JObject.Parse(File.ReadAllText(Path.Combine(dir, PlacementRecordWriter.PlacementFile)));
                Assert.That((string)pl["conditionEndReason"], Is.EqualTo(cond == PlacementConfig.ConditionPlace ? "confirmed" : "timeout"), cond);
                Assert.That(events.Count(e => e[1] == "condition_end"), Is.EqualTo(1), cond);
                Assert.That(JObject.Parse(File.ReadAllText(Path.Combine(dir, "summary.json")))["completed"].Value<bool>(), Is.True, cond);
            }
        }

        string Run(PlacementConfig cfg, PlacementTaskText text)
        {
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 1, SessionId = "SYN-EXP-PRESET", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 27, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = "placement_task.scaleA.v0.json", TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeysFor(cfg).ToArray(),
                EyeHeight = EyeHeightInfo.DesktopFixed(cfg.eyeHeightReferenceM),   // 러너와 같음: 자동 시행·헤드셋 없음 = desktop_fixed
            };
            var script = new PlacementAutoScript();
            const double dt = 0.02;
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records", Guid.NewGuid().ToString("N")), null, new List<string>()))
            {
                for (int i = 0; i < 400000 && !s.Finished; i++)
                {
                    var head = PlacementAutoScript.ScriptedHead(s.Now);
                    var f = script.Participant(s, dt);
                    s.Tick(dt, f, head);
                    script.Experimenter(s);
                }
                Assert.That(s.Finished && s.Completed, Is.True, "끝까지 돌았다");
                return s.RecordDirectory;
            }
        }
    }
}
