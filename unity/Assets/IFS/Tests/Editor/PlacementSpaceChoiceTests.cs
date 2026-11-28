// EditMode 테스트(2026-11-28 연구 책임자 요청·결정): 참여자가 헤드셋 안에서 공간을 고르기(environmentChoice participant — 뒤의 결정으로
// 실험에 쓰지 않는 꺼 둔 기능: participant로 켰을 때만 돈다), 잠금이 공간을 "실험자가 설정 화면에서 고름"으로 두기, 헤드셋/모니터 화면 나누기
// 규칙, 눈높이 보정 자세(앉은 자세 범위), CP17 지적(세션 중 XR 끊김·늦은 XR 재검사·문구 파일 판·높이 하한). UnityEngine 없이 돈다(dotnet에서도).
// 기본값(experimenter·standing)의 기록 바이트 불변은 PlacementEnvironmentTests의 golden sha256이 지킨다.
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
    public class PlacementSpaceChoiceTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-space-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static string DefaultPath => Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath);
        static string ScaleAPath => Path.Combine(Application.streamingAssetsPath, "IFS", "placement_task.scaleA.v0.json");

        static PlacementConfig Choosing(string condition = "place")
        {
            var c = PlacementTests.ShortConfig(condition);
            c.environmentChoice = PlacementConfig.EnvironmentChoiceParticipant;
            return c;
        }

        PlacementSession NewSession(PlacementConfig cfg, int participant, PlacementTaskText text = null)
        {
            text = text ?? PlacementTests.LoadText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = participant, SessionId = "SYN-SPACE", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeysFor(cfg).ToArray(),
            };
            return new PlacementSession(cfg, text, info, Path.Combine(_tmp, Guid.NewGuid().ToString("N")));
        }

        static readonly HeadPose Head = HeadPose.At(0, 1.2, 0);
        static void Tick(PlacementSession s, bool next = false, bool confirm = false, double dt = 0.1) =>
            s.Tick(dt, new PlacementInputFrame { StopDown = next, StopHeld = next, ConfirmDown = confirm }, Head);

        static JObject Manifest(string dir) => OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
        static List<string[]> Events(string dir) => File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(',')).ToList();

        // ── 순서·화면 나누기 규칙 ───────────────────────────────────────
        [Test]
        public void Order_rotates_the_three_spaces_by_participant_number()
        {
            Assert.That(PlacementSpaceChoice.Order(1), Is.EqualTo(new[] { "neutral", "nature", "space" }), "연구 책임자가 적은 순서(기본·자연·우주)");
            Assert.That(PlacementSpaceChoice.Order(2), Is.EqualTo(new[] { "nature", "space", "neutral" }));
            Assert.That(PlacementSpaceChoice.Order(3), Is.EqualTo(new[] { "space", "neutral", "nature" }));
            Assert.That(PlacementSpaceChoice.Order(4), Is.EqualTo(PlacementSpaceChoice.Order(1)));
            var firsts = Enumerable.Range(1, 6).Select(n => PlacementSpaceChoice.Order(n)[0]).ToList();
            foreach (var env in PlacementConfig.Environments) Assert.That(firsts.Count(f => f == env), Is.EqualTo(2), "참여자 3명마다 첫 공간이 한 번씩");
        }

        [Test]
        public void Headset_gets_only_the_wait_panel_before_a_session_and_lock_refuses_desktop_fallback()
        {
            Assert.That(PlacementSpaceChoice.IdlePanelKey(false, true, false), Is.EqualTo("wait"), "XR이 켜져 있고 세션 전이면 대기 문구만");
            Assert.That(PlacementSpaceChoice.IdlePanelKey(true, true, false), Is.Null, "세션 중에는 세션 글");
            Assert.That(PlacementSpaceChoice.IdlePanelKey(false, false, false), Is.Null, "데스크톱 전용 실행은 예전 그대로(판 없음)");
            Assert.That(PlacementSpaceChoice.IdlePanelKey(false, true, true), Is.Null, "자동 시행은 그대로");

            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(true, false, PlacementConfig.InputModeAuto, false), Does.Contain("Link 데스크톱 보기"));
            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(true, false, PlacementConfig.InputModeXr, false), Is.Not.Null);
            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(true, false, PlacementConfig.InputModeDesktop, false), Is.Null, "헤드셋 없이 시험: 입력 desktop");
            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(true, true, PlacementConfig.InputModeAuto, false), Is.Null);
            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(false, false, PlacementConfig.InputModeAuto, false), Is.Null, "잠금이 꺼져 있으면(개발) 예전 그대로");
            Assert.That(PlacementSpaceChoice.HeadsetMissingRefusal(true, false, PlacementConfig.InputModeAuto, true), Is.Null, "자동 시행");
        }

        // ── 공간 고르기 흐름 ───────────────────────────────────────────
        [Test]
        public void Participant_sees_all_three_spaces_then_confirms_and_the_choice_is_recorded()
        {
            var s = NewSession(Choosing(), 2);
            Assert.That(s.Phase, Is.EqualTo(PlacementPhase.SpaceChoice), "세션 첫 단계");
            Assert.That(s.ShownEnvironment, Is.EqualTo("nature"), "참여자 2: 자연부터");
            Assert.That(s.ParticipantTextKey, Is.EqualTo("space_choice+confirm_button_right+space_choice_position"));
            Assert.That(s.ParticipantText, Does.EndWith("공간 1 / 3"));
            Assert.That(s.ParticipantText, Does.Not.Contain("nature").And.Not.Contain("자연").And.Not.Contain("우주"), "공간 이름은 참여자 판에 쓰지 않는다");

            Tick(s, confirm: true);   // 다 보기 전 확인은 받지 않는다
            Assert.That(s.Phase, Is.EqualTo(PlacementPhase.SpaceChoice));
            Assert.That(s.SpaceChoiceDecided, Is.False);
            Tick(s);
            Tick(s, next: true);
            Assert.That(s.ShownEnvironment, Is.EqualTo("space"));
            Assert.That(s.ParticipantText, Does.EndWith("공간 2 / 3"));
            Tick(s, next: true);   // 누르고 있는 채로는 다시 넘기지 않는다(내려가는 순간만)
            Assert.That(s.ShownEnvironment, Is.EqualTo("space"));
            Tick(s);
            Tick(s, next: true);
            Assert.That(s.ShownEnvironment, Is.EqualTo("neutral"));
            Assert.That(s.SpaceChoiceSeenAll, Is.True);
            Tick(s);
            Tick(s, next: true);   // 한 바퀴 돌아 자연
            Assert.That(s.ShownEnvironment, Is.EqualTo("nature"));
            Tick(s);
            Tick(s, confirm: true);
            Assert.That(s.SpaceChoiceDecided, Is.True);
            Assert.That(s.SpaceChosenBy, Is.EqualTo(PlacementSpaceChoice.ByParticipant));
            Assert.That(s.Config.environment, Is.EqualTo("nature"), "고른 공간이 세션 environment");
            Assert.That(s.ShownEnvironment, Is.EqualTo("nature"));
            Assert.That(s.ParticipantTextKey, Is.EqualTo(PlacementTaskText.ConfirmDoneKey), "확정 알림");
            for (int i = 0; i < 25 && s.Phase == PlacementPhase.SpaceChoice; i++) Tick(s);
            Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Intro), "확정 알림 2초 뒤 intro");
            string dir = s.RecordDirectory;
            s.Abort();

            var m = Manifest(dir);
            var c = (JObject)m["environmentChoice"];
            Assert.That((string)c["mode"], Is.EqualTo("participant"));
            Assert.That((string)c["orderRule"], Is.EqualTo(PlacementSpaceChoice.OrderRule));
            Assert.That(c["order"].Select(x => (string)x), Is.EqualTo(new[] { "nature", "space", "neutral" }));
            Assert.That((string)c["environmentBeforeChoice"], Is.EqualTo("neutral"));
            Assert.That((string)c["chosen"], Is.EqualTo("nature"));
            Assert.That((string)c["chosenBy"], Is.EqualTo("participant_confirm"));
            Assert.That((int)c["switches"], Is.EqualTo(3));
            Assert.That((bool)c["seenAll"], Is.True);
            Assert.That((int)c["ignoredConfirms"], Is.EqualTo(1));
            Assert.That((long)c["durationMs"], Is.EqualTo(1000), "10프레임 × 0.1초");
            Assert.That(((JObject)c["viewMs"]).Properties().Sum(p => (long)p.Value), Is.EqualTo(1000), "공간마다 본 시간의 합 = 걸린 시간");
            Assert.That((string)m["config"]["environmentChoice"], Is.EqualTo("participant"));
            Assert.That((string)m["config"]["environment"], Is.EqualTo("nature"));

            var ev = Events(dir);
            var names = ev.Select(e => e[1]).ToList();
            Assert.That(names.IndexOf("space_choice_start"), Is.LessThan(names.IndexOf("space_choice_end")));
            Assert.That(names.Count(n => n == "space_choice_show"), Is.EqualTo(3));
            Assert.That(names.Count(n => n == "space_choice_confirm_ignored"), Is.EqualTo(1));
            var end = ev.Single(e => e[1] == "space_choice_end")[2];
            Assert.That(end, Does.StartWith("chosen=nature;by=participant_confirm;duration_ms=1000;switches=3;seen_all=1;ignored_confirms=1;view_ms=nature:"));
            var phases = ev.Where(e => e[1] == "phase").Select(e => e[2]).ToList();
            Assert.That(phases.Take(2), Is.EqualTo(new[] { "space_choice", "intro" }));
        }

        [Test]
        public void Experimenter_enter_chooses_the_shown_space_and_abort_leaves_chosen_empty()
        {
            var s = NewSession(Choosing("view"), 3);
            Assert.That(s.ShownEnvironment, Is.EqualTo("space"));
            Tick(s);
            s.PressConfirm();   // 참여자가 말로 고른 때: 지금 공간으로
            Assert.That(s.SpaceChosenBy, Is.EqualTo(PlacementSpaceChoice.ByExperimenter));
            Assert.That(s.Config.environment, Is.EqualTo("space"));
            s.PressConfirm();   // 확정 알림 건너뜀
            Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Intro));
            var m = Manifest(s.RecordDirectory);
            Assert.That((string)m["environmentChoice"]["chosenBy"], Is.EqualTo("experimenter"));
            Assert.That((bool)m["environmentChoice"]["seenAll"], Is.False);
            s.Abort();

            var a = NewSession(Choosing(), 1);
            Tick(a);
            Tick(a, next: true);
            a.Abort();
            var ma = Manifest(a.RecordDirectory);
            Assert.That(ma["environmentChoice"]["chosen"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((string)ma["environmentChoice"]["chosenBy"], Is.EqualTo("abort"));
            Assert.That(((JObject)ma["config"]).ContainsKey("environment"), Is.False, "고르기 전 중단: 대기 공간(neutral, 기본 — 키 없음) 그대로");
            Assert.That(Events(a.RecordDirectory).Any(e => e[1] == "abort" && e[2] == "space_choice"), Is.True);
        }

        [Test]
        public void Auto_run_with_space_choice_goes_to_the_end()
        {
            var cfg = Choosing();
            var s = NewSession(cfg, 2);
            var script = new PlacementAutoScript();
            for (int i = 0; i < 200000 && !s.Finished; i++) script.Step(s, 0.02, PlacementAutoScript.ScriptedHead(s.Now));
            Assert.That(s.Completed, Is.True);
            Assert.That(s.Config.environment, Is.EqualTo("nature"), "세 번 넘겨 첫 공간으로 돌아와 확인");
            var m = Manifest(s.RecordDirectory);
            Assert.That((string)m["environment"]["name"], Is.EqualTo("nature"));
            Assert.That((string)m["environmentChoice"]["chosenBy"], Is.EqualTo("participant_confirm"));
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Contain("space_choice").And.Contain("space_choice_position"));
        }

        [Test]
        public void Default_has_no_space_choice_step_or_keys()
        {
            var cfg = PlacementTests.ShortConfig("place");
            Assert.That(cfg.environmentChoice, Is.EqualTo(PlacementConfig.EnvironmentChoiceExperimenter));
            Assert.That(cfg.ToJson().ContainsKey("environmentChoice"), Is.False);
            var s = NewSession(cfg, 2);
            Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Intro));
            Assert.That(s.SpaceChoiceOrder, Is.Null);
            Assert.That(s.ShownEnvironment, Is.EqualTo("neutral"));
            Assert.That(Manifest(s.RecordDirectory).ContainsKey("environmentChoice"), Is.False);
            s.Abort();
            var t = PlacementTests.LoadText();
            Assert.That(t.DraftKeysFor(cfg), Does.Not.Contain("space_choice"));
            Assert.That(t.DraftKeysFor(Choosing()), Does.Contain("space_choice"));
            cfg.environmentChoice = "nobody";
            Assert.That(cfg.Validate().Any(e => e.StartsWith("environmentChoice")), Is.True);
        }

        [Test]
        public void Session_refuses_space_choice_without_the_phrases()
        {
            var o = JObject.Parse(File.ReadAllText(DefaultPath));
            ((JObject)o["texts"]).Remove("space_choice");
            var old = PlacementTaskText.Parse(o.ToString(), "old.json");
            Assert.That(old.SpaceChoiceKeysMissing(), Is.EqualTo(new[] { "space_choice" }));
            Assert.Throws<ArgumentException>(() => NewSession(Choosing(), 1, old).Dispose());
            NewSession(PlacementTests.ShortConfig("place"), 1, old).Dispose();   // 고르지 않는 세션은 그대로 시작
        }

        [Test]
        public void Space_choice_phrases_are_draft_short_and_the_same_in_both_files()
        {
            var def = PlacementTaskText.Load(DefaultPath);
            var a = PlacementTaskText.Load(ScaleAPath);
            foreach (var t in new[] { def, a })
                foreach (var k in PlacementTaskText.SpaceChoiceKeys)
                {
                    Assert.That(t.Status(k), Is.EqualTo("draft"), k);
                    Assert.That(t[k], Is.EqualTo(def[k]), k + ": 두 파일 같은 글");
                    foreach (var banned in new[] { "치료", "진단", "내담자", "좋", "편안", "마음에", "불안", "자연", "우주", "기본" })
                        Assert.That(t[k], Does.Not.Contain(banned), k + ": 평가·감정·공간 이름 금지");
                    Assert.That(t[k], Does.Not.Contain("니다"), "해요체");
                }
            Assert.That(def.SpaceChoicePosition(2, 3), Is.EqualTo("공간 2 / 3"));
            // 판(G63 (1) 24자 줄, 아래 가장자리 35° 안): 안내 + 확인 버튼 안내 + 위치 줄
            foreach (var hand in PlacementConfig.Hands)
            {
                string text = def["space_choice"] + " " + def[PlacementTaskText.ConfirmButtonKeyFor(hand)] + "\n" + def.SpaceChoicePosition(3, 3);
                Assert.That(PlacementPanelMetrics.WrapLineCount(text, PlacementPanelMetrics.ComfortWrapChars), Is.LessThanOrEqualTo(PlacementPanelMetrics.MaxBodyLinesWithin()), hand);
            }
            Assert.That(a.Version, Is.EqualTo(PlacementExperimentLock.ExpectedTaskTextVersion));
        }

        // ── 잠금 ─────────────────────────────────────────────────────────
        [Test]
        public void Lock_has_the_experimenter_choose_the_space_and_seats_the_calibration()
        {
            // 2026-11-28 연구 책임자 결정: 공간은 실험자가 설정 화면 단추로 고른다. 참여자 고르기 단계(participant)는 실험에 쓰지 않는다
            foreach (var env in PlacementConfig.Environments)
            {
                var c = new PlacementConfig { environment = env };
                PlacementExperimentLock.Apply(c);
                Assert.That(c.environment, Is.EqualTo(env), env + ": 잠금은 실험자가 고른 공간을 그대로 둔다");
                Assert.That(c.ParticipantChoosesSpace, Is.False);
                Assert.That(PlacementExperimentLock.Holds(c, PlacementExperimentLock.TaskTextFile), Is.True, env);
            }
            Assert.That(PlacementExperimentLock.EnvironmentChoice, Is.EqualTo(PlacementConfig.EnvironmentChoiceExperimenter));
            var cfg = new PlacementConfig();
            PlacementExperimentLock.Apply(cfg);
            Assert.That(cfg.environment, Is.EqualTo(PlacementConfig.EnvironmentNeutral), "처음 눌린 값 neutral(코드 기본값)");
            Assert.That(cfg.IsSeated, Is.True);
            Assert.That((cfg.EyeRangeMinM, cfg.EyeRangeMaxM), Is.EqualTo((0.95, 1.45)));

            var text = PlacementTaskText.Load(ScaleAPath);
            Assert.That(PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, text), Is.Empty);
            cfg.environmentChoice = PlacementConfig.EnvironmentChoiceParticipant;   // 꺼 둔 기능을 인스펙터·명령줄로 켜도 잠금은 거부하고 되돌린다
            cfg.eyeCalibPosture = PlacementConfig.PostureStanding;
            cfg.eyeHeightSeatedMaxM = 1.6;
            var r = PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, text);
            Assert.That(r.Any(x => x.Contains("environmentChoice = participant") && x.Contains("실험자가 설정 화면에서 고름")), Is.True);
            Assert.That(r.Any(x => x.Contains("eyeCalibPosture = standing")), Is.True);
            Assert.That(r.Any(x => x.Contains("eyeHeightSeatedMaxM = 1.6")), Is.True);
            Assert.That(PlacementExperimentLock.Holds(cfg, PlacementExperimentLock.TaskTextFile), Is.False);
            PlacementExperimentLock.Apply(cfg);
            Assert.That(cfg.environmentChoice, Is.EqualTo(PlacementConfig.EnvironmentChoiceExperimenter));
            Assert.That(PlacementExperimentLock.Holds(cfg, PlacementExperimentLock.TaskTextFile), Is.True);
            cfg.environment = "forest";
            Assert.That(PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, text).Any(x => x.Contains("environment = forest")), Is.True);
            PlacementExperimentLock.Apply(cfg);
            Assert.That(cfg.environment, Is.EqualTo(PlacementConfig.EnvironmentNeutral), "세 공간 밖의 값이면 권고 설정 neutral로");
            Assert.That(PlacementExperimentLock.RequiredTaskTextKeys, Does.Not.Contain("space_choice"), "꺼 둔 단계의 문구는 잠금이 요구하지 않는다");
            Assert.That(cfg.Validate(), Is.Empty, "앉은 자세 범위에서도 옮긴 높이가 [minHeightM, maxHeightM] 안");
        }

        [Test]
        public void Locked_session_has_no_space_choice_step_and_records_the_experimenter_space()
        {
            var cfg = PlacementTests.ShortConfig("place");
            cfg.environment = PlacementConfig.EnvironmentNature;
            PlacementExperimentLock.Apply(cfg);
            cfg.eyeHeightMode = PlacementConfig.EyeHeightNone;   // 이 시험은 공간만 본다(눈높이 보정 없이)
            var text = PlacementTaskText.Load(ScaleAPath);
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 2, SessionId = "SYN-LOCKSPACE", StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc),
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeysFor(cfg).ToArray(),
            };
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "lock")))
            {
                Assert.That(s.Phase, Is.Not.EqualTo(PlacementPhase.SpaceChoice), "실험 씬(잠금)에서는 참여자 고르기 단계가 돌지 않는다");
                Assert.That(s.SpaceChoiceOrder, Is.Null);
                Assert.That(s.ShownEnvironment, Is.EqualTo("nature"), "실험자가 고른 공간");
                var m = Manifest(s.RecordDirectory);
                Assert.That(m.ContainsKey("environmentChoice"), Is.False);
                Assert.That((string)m["config"]["environment"], Is.EqualTo("nature"), "고른 공간은 manifest config에");
                Assert.That((string)m["environment"]["name"], Is.EqualTo("nature"));
                Assert.That(((JObject)m["config"]).ContainsKey("environmentChoice"), Is.False, "experimenter(기본)는 키 없음");
                Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Not.Contain("space_choice"));
            }
        }

        [Test]
        public void Lock_seated_range_equals_the_code_defaults()
        {
            var d = new PlacementConfig();
            Assert.That((d.eyeHeightSeatedMinM, d.eyeHeightSeatedMaxM), Is.EqualTo((PlacementExperimentLock.EyeHeightSeatedMinM, PlacementExperimentLock.EyeHeightSeatedMaxM)));
            Assert.That(d.eyeCalibPosture, Is.EqualTo(PlacementConfig.PostureStanding), "코드 기본값은 선 자세(예전 동작)");
            Assert.That((d.EyeRangeMinM, d.EyeRangeMaxM), Is.EqualTo((1.30, 1.95)));
        }

        // ── 눈높이 보정 자세 ─────────────────────────────────────────────
        static double[] Repeat(double v, int n) => Enumerable.Repeat(v, n).ToArray();

        [Test]
        public void Calibration_range_follows_the_posture()
        {
            var standing = new PlacementConfig { eyeHeightMode = PlacementConfig.EyeHeightRelative };
            var r = EyeHeightCalibration.Evaluate(standing, Repeat(1.136, 20), Repeat(0, 20), true, "Floor");
            Assert.That(r.Ok, Is.False);
            Assert.That(r.Reason, Is.EqualTo("눈높이 1.136 m가 범위 [1.30, 1.95] 밖입니다 — 선 자세·바닥 설정(Guardian) 확인"), "기본(선 자세) 문구 그대로");

            var seated = new PlacementConfig { eyeHeightMode = PlacementConfig.EyeHeightRelative, eyeCalibPosture = PlacementConfig.PostureSeated };
            Assert.That(EyeHeightCalibration.Evaluate(seated, Repeat(1.136, 20), Repeat(0, 20), true, "Floor").Ok, Is.True);
            Assert.That(EyeHeightCalibration.Evaluate(seated, Repeat(0.95, 20), Repeat(0, 20), true, "Floor").Ok, Is.True, "경계 포함");
            Assert.That(EyeHeightCalibration.Evaluate(seated, Repeat(1.45, 20), Repeat(0, 20), true, "Floor").Ok, Is.True);
            var low = EyeHeightCalibration.Evaluate(seated, Repeat(0.94, 20), Repeat(0, 20), true, "Floor");
            Assert.That(low.Reason, Is.EqualTo("눈높이 0.940 m가 앉은 자세 범위 [0.95, 1.45] 밖입니다 — 앉은 자세·바닥 설정(Guardian) 확인"));
            Assert.That(EyeHeightCalibration.Evaluate(seated, Repeat(1.60, 20), Repeat(0, 20), true, "Floor").Ok, Is.False, "앉은 자세로 두고 서서 재면 실패");
            var shaky = EyeHeightCalibration.Evaluate(seated, new[] { 1.1, 1.2, 1.1, 1.2, 1.1, 1.2 }, Repeat(0, 6), true, "Floor");
            Assert.That(shaky.Reason, Does.Contain("가만히 앉은 채로 다시"));
        }

        [Test]
        public void Seated_posture_is_recorded_only_when_set()
        {
            var standing = PlacementTests.ShortConfig("place");
            standing.eyeHeightMode = PlacementConfig.EyeHeightRelative;
            var j = standing.ToJson();
            Assert.That(j.ContainsKey("eyeCalibPosture"), Is.False, "선 자세(기본)면 키 없음 — 기존 기록과 같은 바이트");
            var info = EyeHeightInfo.DesktopFixed(1.6);
            Assert.That(info.ManifestJson(standing).ContainsKey("posture"), Is.False);
            Assert.That(info.EventDetail(standing), Does.Not.Contain("posture"));

            var seated = standing.Clone();
            seated.eyeCalibPosture = PlacementConfig.PostureSeated;
            var js = seated.ToJson();
            var keys = js.Properties().Select(p => p.Name).ToList();
            Assert.That(keys.SkipWhile(k => k != "eyeCalibMaxPitchDeg").Skip(1).Take(3), Is.EqualTo(new[] { "eyeCalibPosture", "eyeHeightSeatedMinM", "eyeHeightSeatedMaxM" }));
            var mj = info.ManifestJson(seated);
            Assert.That(((string)mj["posture"], (double)mj["rangeMinM"], (double)mj["rangeMaxM"]), Is.EqualTo(("seated", 0.95, 1.45)));
            Assert.That(info.EventDetail(seated), Does.EndWith(";posture=seated"));
        }

        [Test]
        public void Session_checks_the_measured_eye_height_against_the_posture_range()
        {
            var cfg = PlacementTests.ShortConfig("place");
            cfg.eyeHeightMode = PlacementConfig.EyeHeightRelative;
            cfg.eyeCalibPosture = PlacementConfig.PostureSeated;
            var text = PlacementTests.LoadText();
            PlacementSessionInfo Info(double e) => new PlacementSessionInfo
            {
                ParticipantNumber = 1, SessionId = "SYN-EYE", StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc),
                EyeHeight = new EyeHeightInfo { MeasuredM = e, SdM = 0, PitchDeg = 0, Samples = 20, TrackingOrigin = "Floor", Source = EyeHeightInfo.SourceCalibrated },
            };
            using (var s = new PlacementSession(cfg, text, Info(1.15), Path.Combine(_tmp, "ok")))
            {
                Assert.That(s.EyeOffsetM, Is.EqualTo(1.15 - 1.6).Within(1e-9), "기준 1.60 그대로 — 눈과 물체의 기하는 선 자세와 같다");
                Assert.That(s.StartPosition.Y, Is.EqualTo(cfg.startHeightM + 1.15 - 1.6).Within(1e-9));
            }
            var ex = Assert.Throws<ArgumentException>(() => new PlacementSession(cfg, text, Info(1.60), Path.Combine(_tmp, "no")).Dispose());
            Assert.That(ex.Message, Does.Contain("앉은 자세 범위"));
        }
            // ── CP17-2: 실제 StreamingAssets 문구 파일의 판과 필수 키 ─────────────────
        [Test]
        public void Real_task_text_files_have_the_expected_version_and_required_keys()
        {
            // 판 0.8 → 0.9(공간 고르기 문구 추가)는 원칙 7에 따른 의도한 변경 — manifest taskText.version이 바뀐다(CP17-2 판정: 고치지 않음)
            var def = PlacementTaskText.Load(DefaultPath);
            var a = PlacementTaskText.Load(ScaleAPath);
            Assert.That(def.Version, Is.EqualTo("0.10"));   // 0.10: G83 반복 멈춤 조작 안내
            Assert.That(a.Version, Is.EqualTo("0.10-scaleA"));
            Assert.That(a.Version, Is.EqualTo(PlacementExperimentLock.ExpectedTaskTextVersion), "잠금 판 = 실제 scaleA 파일 판");
            Assert.That(PlacementExperimentLock.TaskTextProblems(a), Is.Empty, "실제 scaleA 파일은 잠금이 받는다");
            foreach (var t in new[] { def, a })
            {
                foreach (var k in PlacementExperimentLock.RequiredTaskTextKeys.Concat(PlacementTaskText.SpaceChoiceKeys).Concat(new[] { "wait" }))
                    Assert.That(t[k], Is.Not.Null, t.FileName + ": " + k);
                Assert.That(t.AssistKeysMissing(), Is.Empty, t.FileName);
                Assert.That(t.LoopKeysMissing(), Is.Empty, t.FileName);
                Assert.That(t.SpaceChoiceKeysMissing(), Is.Empty, t.FileName);
            }
            // 실제 파일로 연 세션의 manifest에 판이 그대로 남는다
            var cfg = PlacementTests.ShortConfig("place");
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 1, SessionId = "SYN-TEXTVER", StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc),
                TaskTextFile = a.FileName, TaskTextVersion = a.Version, TaskTextDraftKeys = a.DraftKeysFor(cfg).ToArray(),
            };
            using (var s = new PlacementSession(cfg, a, info, Path.Combine(_tmp, "ver")))
                Assert.That((string)Manifest(s.RecordDirectory)["taskText"]["version"], Is.EqualTo("0.10-scaleA"));
        }

        // ── CP17-4: 늦게 켜진 XR ─────────────────────────────────────────
        [Test]
        public void Headset_refusal_clears_when_xr_comes_up_after_check_and_returns_when_it_drops()
        {
            string refusal = PlacementSpaceChoice.HeadsetMissingRefusal(true, false, PlacementConfig.InputModeAuto, false);
            var errors = new List<string> { "다른 오류", refusal };
            // [확인] 뒤 XR이 켜짐 → 거부 줄이 빠지고 cleared(러너가 참여자 입력을 다시 고른다)
            string now = PlacementSpaceChoice.UpdateHeadsetRefusal(errors, refusal, PlacementSpaceChoice.HeadsetMissingRefusal(true, true, PlacementConfig.InputModeAuto, false), out bool cleared);
            Assert.That(now, Is.Null);
            Assert.That(cleared, Is.True);
            Assert.That(errors, Is.EqualTo(new[] { "다른 오류" }), "다른 오류는 그대로");
            // 그대로면 아무것도 바꾸지 않는다(매 프레임 불러도 됨)
            PlacementSpaceChoice.UpdateHeadsetRefusal(errors, null, null, out cleared);
            Assert.That(cleared, Is.False);
            Assert.That(errors.Count, Is.EqualTo(1));
            // 시작 전에 다시 꺼짐 → 거부를 다시 더한다(중복 없이)
            now = PlacementSpaceChoice.UpdateHeadsetRefusal(errors, null, refusal, out cleared);
            Assert.That(now, Is.EqualTo(refusal));
            Assert.That(cleared, Is.False);
            PlacementSpaceChoice.UpdateHeadsetRefusal(errors, refusal, refusal, out _);
            Assert.That(errors.Count(e => e == refusal), Is.EqualTo(1));
            Assert.That(refusal, Does.Contain("저절로 사라집니다"));
        }

        // ── CP17-1: 세션 중 XR 끊김 ─────────────────────────────────────
        static PlacementSessionInfo AutoInfo(PlacementConfig cfg, PlacementTaskText text, bool monitored) => new PlacementSessionInfo
        {
            ParticipantNumber = 1, SessionId = "SYN-XRLOST", StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc),
            InputSource = "auto", AutoMode = true, TaskTextFile = text.FileName, TaskTextVersion = text.Version,
            TaskTextDraftKeys = text.DraftKeysFor(cfg).ToArray(), XrMonitored = monitored,
        };

        [Test]
        public void Xr_loss_during_a_session_is_logged_and_counted_without_changing_the_timer_or_phases()
        {
            var cfg = PlacementTests.ShortConfig("place");
            var text = PlacementTests.LoadText();
            string RunOne(bool monitored, bool drop, out PlacementSession done)
            {
                var s = new PlacementSession(cfg, text, AutoInfo(cfg, text, monitored), Path.Combine(_tmp, Guid.NewGuid().ToString("N")));
                var script = new PlacementAutoScript();
                for (int i = 0; i < 200000 && !s.Finished; i++)
                {
                    if (drop && i == 100) { s.ReportXrHead(false); Assert.That(s.XrLostNow, Is.True); }
                    else if (drop && i == 400) s.ReportXrHead(true);
                    else if (drop && i == 600) s.ReportXrHead(false);   // 끝날 때까지 끊긴 채
                    else if (!drop || i < 100 || (i > 400 && i < 600)) s.ReportXrHead(true);
                    script.Step(s, 0.02, PlacementAutoScript.ScriptedHead(s.Now));
                }
                done = s;
                return s.RecordDirectory;
            }
            string plain = RunOne(false, false, out var p);
            string lost = RunOne(true, true, out var l);
            Assert.That(p.Completed && l.Completed, Is.True, "끊겨도 세션은 끝까지 그대로(멈추거나 되돌리지 않음)");
            Assert.That(l.XrLostCount, Is.EqualTo(2));
            // 끊김 줄을 빼면 events.csv가 같다 — 단계·시각이 바뀌지 않았다
            List<string> Rows(string dir, bool dropXr) => File.ReadAllLines(Path.Combine(dir, "events.csv")).Where(x => !dropXr || !x.Contains(",xr_")).ToList();
            Assert.That(Rows(lost, true), Is.EqualTo(Rows(plain, false)));
            var ev = Events(lost).Where(e => e[1].StartsWith("xr_")).ToList();
            Assert.That(ev.Select(e => e[1]), Is.EqualTo(new[] { "xr_lost", "xr_regained", "xr_lost" }));
            Assert.That(ev[0][0], Is.EqualTo("2000"), "t_ms = 끊긴 시각(세션 시계)");
            Assert.That(ev[0][2], Does.StartWith("count=1;phase=").And.Contain(";utc="));
            Assert.That(ev[1][2], Does.Contain("lost_ms=6000"));
            var x = (JObject)Manifest(lost)["xrConnection"];
            Assert.That(((bool)x["monitored"], (int)x["lostCount"], (bool)x["lostNow"]), Is.EqualTo((true, 2, true)));
            Assert.That((long)x["lostMsTotal"], Is.GreaterThan(6000), "끝날 때 끊겨 있던 시간까지");
            // XR 없이 돈 세션(데스크톱·자동 시행 — 러너가 XrMonitored를 켜지 않음): 알려 줘도 기록 없음, manifest 키 없음
            Assert.That(Rows(plain, false).Any(r => r.Contains(",xr_")), Is.False);
            Assert.That(Manifest(plain).ContainsKey("xrConnection"), Is.False);
            var d = new PlacementSession(cfg, text, AutoInfo(cfg, text, false), Path.Combine(_tmp, "desk"));
            d.ReportXrHead(false);
            Assert.That(d.XrLostNow, Is.False);
            Assert.That(d.XrLostCount, Is.EqualTo(0));
            d.Abort();
            Assert.That(Events(d.RecordDirectory).Any(e => e[1].StartsWith("xr_")), Is.False);
            Assert.That(PlacementSpaceChoice.XrLostAlert(1), Does.Contain("헤드셋 연결이 끊겼습니다").And.Contain("PC 화면").And.Contain("F1").And.Contain("[중단…]").And.Contain("Esc"));
        }

        // ── CP17-3: 앉은 자세 높이 하한 ──────────────────────────────────
        [Test]
        public void Panel_floor_keeps_the_whole_panel_above_the_floor_and_leaves_standing_unchanged()
        {
            var heights = Enumerable.Range(1, 8).Select(n => PlacementPanelMetrics.BodyPanelHeightM(n))
                .Concat(new[] { PlacementPanelMetrics.ItemPanelHeightM(2, 2), PlacementPanelMetrics.ItemPanelHeightM(4, 3) }).ToList();
            foreach (var h in heights)
            {
                // 선 자세 기본(중심 0.6, 눈 1.6): 하한을 켜도 값이 같다
                var off = PlacementPanelMetrics.PanelPlacement(h);
                var on = PlacementPanelMetrics.PanelPlacementFloored(h, 2.0, 0.6, 1.6, PlacementPanelMetrics.DefaultMaxTopM, PlacementPanelMetrics.DefaultMinBottomM, 0.05, out bool fl);
                Assert.That(fl, Is.False, $"h {h:0.000}");
                Assert.That(on.centerY, Is.EqualTo(off.centerY), $"h {h:0.000}");
                Assert.That(PlacementPanelMetrics.FloorCenterY(-0.05, h, 0.95, 2.0, -1, out bool none), Is.EqualTo(-0.05), "끄면(음수) 그대로");
                Assert.That(none, Is.False);
                // 앉은 범위: 판 아래 끝이 바닥 위 0.05 m(1 mm 안)에 남는다
                for (double e = 0.95; e <= 1.45 + 1e-9; e += 0.05)
                {
                    var p = PlacementPanelMetrics.PanelPlacementFloored(h, 2.0, 0.6 + (e - 1.6), e, PlacementPanelMetrics.DefaultMaxTopM, PlacementPanelMetrics.DefaultMinBottomM, 0.05, out _);
                    double bottom = p.centerY - h * 0.5 * PlacementPanelMetrics.UpY(p.centerY, e, 2.0);
                    Assert.That(bottom, Is.GreaterThanOrEqualTo(0.05 - 1e-3), $"h {h:0.000} E {e:0.00}");
                }
            }
            // CP17 재현값: E = 0.95면 하한 전 중심이 −0.05 m
            double c = PlacementPanelMetrics.FloorCenterY(0.6 + (0.95 - 1.6), PlacementPanelMetrics.BodyPanelHeightM(3), 0.95, 2.0, 0.05, out bool floored);
            Assert.That(floored, Is.True);
            Assert.That(c, Is.GreaterThan(0.2));
        }

        PlacementSession SeatedSession(double eye, double? radius, string condition = "place", bool seated = true, bool assist = false)
        {
            var cfg = PlacementTests.ShortConfig(condition);
            cfg.eyeHeightMode = PlacementConfig.EyeHeightRelative;
            if (seated) cfg.eyeCalibPosture = PlacementConfig.PostureSeated;
            cfg.placementAssist = assist;
            var text = PlacementTests.LoadText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 1, SessionId = "SYN-FLOOR", StartedUtc = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc),
                ObjectBoundingRadiusM = radius,
                EyeHeight = new EyeHeightInfo { MeasuredM = eye, SdM = 0, PitchDeg = 0, Samples = 20, TrackingOrigin = "Floor", Source = EyeHeightInfo.SourceCalibrated },
            };
            return new PlacementSession(cfg, text, info, Path.Combine(_tmp, Guid.NewGuid().ToString("N")));
        }

        [Test]
        public void Object_heights_get_a_floor_of_radius_plus_clearance_only_when_needed()
        {
            // 큰 물체(경계 반지름 0.7 m = layout.size 1)를 앉은 눈높이 0.95 m에서: 옮긴 높이 0.55 m → 하한 0.75 m
            using (var s = SeatedSession(0.95, 0.7, assist: true))
            {
                Assert.That(s.StartPosition.Y, Is.EqualTo(0.75).Within(1e-9));
                Assert.That(s.HeightFloored, Is.EqualTo(new[] { "start", "stop", "practice_target" }));
                var h = (JObject)Manifest(s.RecordDirectory)["heightFloor"];
                Assert.That((double)h["objectFloorM"], Is.EqualTo(0.75).Within(1e-9));
                Assert.That(((double)h["startHeightM"], (double)h["stopHeightM"]), Is.EqualTo((0.75, 0.75)));
                Assert.That((double)h["practiceTargetHeightM"], Is.EqualTo(0.175).Within(1e-9), "연습 상자 한 변 0.25 / 2 + 0.05(옮긴 높이 0.15)");
                Assert.That(h["panel"].Type, Is.EqualTo(JTokenType.Null), "판은 러너가 알려 준 뒤에");
                s.ReportPanelCenter(-0.05, 0.31, true);
                s.ReportPanelCenter(-0.05, 0.36, true);
                string dir = s.RecordDirectory;
                s.Abort();
                var pj = (JObject)Manifest(dir)["heightFloor"]["panel"];
                Assert.That(((double)pj["baseCenterM"], (bool)pj["floorApplied"], (double)pj["centerMinM"], (double)pj["centerMaxM"]), Is.EqualTo((-0.05, true, 0.31, 0.36)));
                Assert.That(Events(dir).Count(e => e[1] == "panel_floor"), Is.EqualTo(1), "처음 걸릴 때 한 줄");
            }
            // 보통 크기(0.3 m)는 앉은 하한 0.95에서도 0.55 ≥ 0.35 — 하한 안 걸림. 앉은 자세라 키는 남는다(applied 빈 목록)
            using (var s = SeatedSession(0.95, 0.3))
            {
                Assert.That(s.StartPosition.Y, Is.EqualTo(0.55).Within(1e-9));
                Assert.That(s.HeightFloored, Is.Empty);
                Assert.That(((JArray)Manifest(s.RecordDirectory)["heightFloor"]["applied"]).Count, Is.EqualTo(0));
            }
            // 선 자세 기준 눈높이(1.6): 값·기록 그대로(키 없음)
            using (var s = SeatedSession(1.6, 0.7, seated: false))
            {
                Assert.That(s.StartPosition.Y, Is.EqualTo(1.2).Within(1e-9));
                Assert.That(s.HeightFloored, Is.Empty);
                s.ReportPanelCenter(0.6, 0.6, false);
                string dir = s.RecordDirectory;
                s.Abort();
                Assert.That(Manifest(dir).ContainsKey("heightFloor"), Is.False);
            }
        }
    }
}
