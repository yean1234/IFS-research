// 실험자 설정 화면 보조(2026-11-28): 가장 최근 세션 자동 채움(PlacementLatestSession)과 본 실험 설정 잠금(PlacementExperimentLock),
// 그리고 manifest에 남는 두 키. 임시 폴더와 합성 json만 쓴다(참여자 데이터 없음).
using System;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class PlacementSetupAutoTests
    {
        string _tmp, _scenes, _selection;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-setup-auto-" + Guid.NewGuid().ToString("N"));
            _scenes = Path.Combine(_tmp, "logs", "scenes");
            _selection = Path.Combine(_tmp, "logs", "selection");
            Directory.CreateDirectory(_scenes);
            Directory.CreateDirectory(_selection);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        /// <summary>합성 spec(meta만)과 짝 선택 파일을 쓴다. sha = spec 파일 바이트 sha256(챗봇 러너 계약과 같은 규칙).</summary>
        string WritePair(string sid, string updatedAt, string participantId = null, string selSessionId = null, string specSessionId = null,
            string shaOverride = null, bool? runnerReady = true)
        {
            var spec = new JObject { ["meta"] = new JObject { ["sessionId"] = specSessionId ?? sid, ["participantId"] = participantId, ["condition"] = "chatbot" } };
            byte[] bytes = Encoding.UTF8.GetBytes(spec.ToString());
            File.WriteAllBytes(Path.Combine(_scenes, sid + ".json"), bytes);
            // 매퍼 비교용 사본(고르면 안 됨)
            File.WriteAllBytes(Path.Combine(_scenes, sid + ".v2.json"), bytes);
            var sel = new JObject
            {
                ["formatVersion"] = "ifs-selection/0.5",
                ["specSha256"] = shaOverride ?? OwnershipManifest.Sha256Hex(bytes),
                ["sessionId"] = selSessionId ?? sid,
                ["updatedAt"] = updatedAt,
            };
            if (runnerReady.HasValue) sel["runnerReady"] = runnerReady.Value;
            string dir = Path.Combine(_selection, sid);
            Directory.CreateDirectory(dir);
            string path = Path.Combine(dir, "selection.json");
            File.WriteAllText(path, sel.ToString());
            return path;
        }

        [Test]
        public void Picks_the_latest_matching_pair_and_reads_participant_number_from_spec_meta()
        {
            WritePair("SYN-A", "2026-11-28T10:00:00+09:00", participantId: "P03");
            WritePair("SYN-B", "2026-11-28T10:30:00+09:00", participantId: "P07");
            WritePair("SYN-C", "2026-11-28T09:00:00+09:00");
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Not.Null, r.Rejected);
            Assert.That(r.Pick.SessionId, Is.EqualTo("SYN-B"));
            Assert.That(Path.GetFileName(r.Pick.SpecPath), Is.EqualTo("SYN-B.json"), "비교용 .v2.json이 아니라 세션 spec");
            Assert.That(r.Pick.SelectionPath, Is.EqualTo(Path.GetFullPath(Path.Combine(_selection, "SYN-B", "selection.json"))));
            Assert.That(r.Pick.ParticipantNumber, Is.EqualTo(7));
            Assert.That(r.Pick.SavedFromFile, Is.True);
            Assert.That(r.Pick.SavedAt, Is.EqualTo(new DateTimeOffset(2026, 11, 28, 1, 30, 0, TimeSpan.Zero)));
            Assert.That(r.Pick.NotRunnerReady, Is.False);
            Assert.That(r.Rejected, Is.Null);
        }

        [Test]
        public void Participant_number_is_left_empty_when_the_file_has_none()
        {
            WritePair("P05", "2026-11-28T10:00:00+09:00", participantId: null);
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Not.Null);
            Assert.That(r.Pick.ParticipantNumber, Is.Null, "세션 ID에서 번호를 짐작하지 않는다");
        }

        [Test]
        public void Latest_pair_with_wrong_spec_sha_is_rejected_without_falling_back_to_an_older_session()
        {
            WritePair("SYN-OLD", "2026-11-28T09:00:00+09:00", participantId: "1");
            WritePair("SYN-NEW", "2026-11-28T10:00:00+09:00", participantId: "2", shaOverride: new string('0', 64));
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Null, "다른 참여자의 오래된 파일로 조용히 내려가지 않는다");
            Assert.That(r.RejectedSessionId, Is.EqualTo("SYN-NEW"));
            Assert.That(r.Rejected, Does.Contain("specSha256"));
            Assert.That(r.NothingFound, Is.False);
        }

        [Test]
        public void Session_id_mismatches_are_rejected()
        {
            WritePair("SYN-X", "2026-11-28T10:00:00+09:00", selSessionId: "SYN-Y");
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Null);
            Assert.That(r.Rejected, Does.Contain("sessionId"));

            TearDown(); SetUp();
            WritePair("SYN-X", "2026-11-28T10:00:00+09:00", specSessionId: "SYN-Z");
            r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Null);
            Assert.That(r.Rejected, Does.Contain("meta.sessionId"));
        }

        [Test]
        public void Spec_without_meta_session_id_is_rejected()
        {
            var spec = new JObject { ["meta"] = new JObject { ["participantId"] = null } };
            byte[] bytes = Encoding.UTF8.GetBytes(spec.ToString());
            File.WriteAllBytes(Path.Combine(_scenes, "SYN-N.json"), bytes);
            Directory.CreateDirectory(Path.Combine(_selection, "SYN-N"));
            File.WriteAllText(Path.Combine(_selection, "SYN-N", "selection.json"), new JObject
            {
                ["sessionId"] = "SYN-N", ["specSha256"] = OwnershipManifest.Sha256Hex(bytes), ["updatedAt"] = "2026-11-28T10:00:00+09:00",
            }.ToString());
            var r = PlacementLatestSession.FindLatest(_scenes, null, new DateTimeOffset(2026, 11, 28, 10, 5, 0, TimeSpan.FromHours(9)));
            Assert.That(r.Pick, Is.Null, "네 곳 ID가 모두 있어야 한다(G78-h)");
            Assert.That(r.Rejected, Does.Contain("meta.sessionId가 없음"));
        }

        [Test]
        public void Future_saved_time_beyond_tolerance_fills_nothing_and_does_not_fall_back()
        {
            var now = new DateTimeOffset(2026, 11, 28, 10, 0, 0, TimeSpan.FromHours(9));
            WritePair("SYN-NOW", "2026-11-28T09:55:00+09:00", participantId: "1");
            WritePair("SYN-FUTURE", "2026-11-28T10:03:00+09:00", participantId: "2");   // 3분 미래 > 2분
            var r = PlacementLatestSession.FindLatest(_scenes, null, now);
            Assert.That(r.Pick, Is.Null, "이전 참여자 파일일 수 있어 채우지 않고, 더 오래된 세션으로도 내려가지 않는다");
            Assert.That(r.FutureTimestamp, Is.True);
            Assert.That(r.RejectedSessionId, Is.EqualTo("SYN-FUTURE"));
            Assert.That(r.Rejected, Does.Contain("미래"));

            // 허용 오차(기본 2분) 안의 미래는 받는다(두 PC 시계의 작은 차이)
            r = PlacementLatestSession.FindLatest(_scenes, null, now.AddMinutes(1.5));
            Assert.That(r.Pick?.SessionId, Is.EqualTo("SYN-FUTURE"));
            Assert.That(r.FutureTimestamp, Is.False);
            // 허용 오차는 설정값
            r = PlacementLatestSession.FindLatest(_scenes, null, now, futureToleranceMinutes: 5);
            Assert.That(r.Pick?.SessionId, Is.EqualTo("SYN-FUTURE"));
        }

        [Test]
        public void Session_files_source_is_written_only_when_auto_fill_filled_the_session()
        {
            Assert.That(PlacementLatestSession.SessionFilesSource(false, false), Is.Null);
            Assert.That(PlacementLatestSession.SessionFilesSource(false, true), Is.Null);
            Assert.That(PlacementLatestSession.SessionFilesSource(true, true), Is.EqualTo("auto"));
            Assert.That(PlacementLatestSession.SessionFilesSource(true, false), Is.EqualTo("auto_overridden"));
        }

        [Test]
        public void Missing_spec_or_empty_folders_fill_nothing()
        {
            Assert.That(PlacementLatestSession.FindLatest(Path.Combine(_tmp, "none")).NothingFound, Is.True, "spec 폴더 없음");
            Assert.That(PlacementLatestSession.FindLatest(_scenes).NothingFound, Is.True, "선택 파일 없음");
            WritePair("SYN-Q", "2026-11-28T10:00:00+09:00");
            File.Delete(Path.Combine(_scenes, "SYN-Q.json"));
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Null);
            Assert.That(r.Rejected, Does.Contain("SYN-Q.json"));
        }

        [Test]
        public void Saved_time_falls_back_to_file_time_and_not_ready_is_flagged()
        {
            string path = WritePair("SYN-T", null, runnerReady: false);
            var t = new DateTime(2026, 11, 28, 1, 2, 3, DateTimeKind.Utc);
            File.SetLastWriteTimeUtc(path, t);
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick, Is.Not.Null);
            Assert.That(r.Pick.SavedFromFile, Is.False);
            Assert.That(r.Pick.SavedAt.UtcDateTime, Is.EqualTo(t));
            Assert.That(r.Pick.NotRunnerReady, Is.True);
        }

        [Test]
        public void A_newer_spec_without_selection_is_reported()
        {
            string sel = WritePair("SYN-DONE", "2026-11-28T01:00:00Z");
            File.SetLastWriteTimeUtc(Path.Combine(_scenes, "SYN-DONE.json"), new DateTime(2026, 11, 28, 0, 50, 0, DateTimeKind.Utc));
            File.SetLastWriteTimeUtc(Path.Combine(_scenes, "SYN-DONE.v2.json"), new DateTime(2026, 11, 28, 0, 50, 0, DateTimeKind.Utc));
            string pending = Path.Combine(_scenes, "SYN-PENDING.json");
            File.WriteAllText(pending, "{\"meta\":{\"sessionId\":\"SYN-PENDING\"}}");
            File.SetLastWriteTimeUtc(pending, new DateTime(2026, 11, 28, 1, 20, 0, DateTimeKind.Utc));
            var r = PlacementLatestSession.FindLatest(_scenes);
            Assert.That(r.Pick?.SessionId, Is.EqualTo("SYN-DONE"));
            Assert.That(r.NewerSpecWithoutSelection, Is.EqualTo("SYN-PENDING"));
        }

        [Test]
        public void Participant_number_parsing_staleness_and_age_text()
        {
            Assert.That(PlacementLatestSession.ParseParticipantNumber("3"), Is.EqualTo(3));
            Assert.That(PlacementLatestSession.ParseParticipantNumber("P012"), Is.EqualTo(12));
            Assert.That(PlacementLatestSession.ParseParticipantNumber("p7"), Is.EqualTo(7));
            foreach (var bad in new[] { null, "", "0", "P0", "S20261127-x", "A3", "3a", "-3" })
                Assert.That(PlacementLatestSession.ParseParticipantNumber(bad), Is.Null, bad ?? "null");

            var saved = new DateTimeOffset(2026, 11, 28, 10, 0, 0, TimeSpan.FromHours(9));
            Assert.That(PlacementLatestSession.IsStale(saved, saved.AddMinutes(29), 30), Is.False);
            Assert.That(PlacementLatestSession.IsStale(saved, saved.AddMinutes(31), 30), Is.True);
            Assert.That(PlacementLatestSession.AgeText(saved, saved.AddMinutes(12.7)), Is.EqualTo("12분 전"));
            Assert.That(PlacementLatestSession.AgeText(saved, saved.AddSeconds(20)), Is.EqualTo("1분 안"));
            Assert.That(PlacementLatestSession.AgeText(saved, saved.AddHours(3)), Is.EqualTo("3시간 전"));
        }

        [Test]
        public void Existing_record_folder_for_the_session_is_detected()
        {
            string root = Path.Combine(_tmp, "sessions");
            Assert.That(PlacementLatestSession.HasRecord(root, "SYN-R"), Is.False);
            var dir = PlacementRecordWriter.SessionDirectory(root, 3, "SYN-R", new DateTime(2026, 11, 28, 1, 0, 0, DateTimeKind.Utc));
            Directory.CreateDirectory(dir);
            Assert.That(PlacementLatestSession.HasRecord(root, "SYN-R"), Is.True);
            Assert.That(PlacementLatestSession.HasRecord(root, "SYN-S"), Is.False);
        }

        // ── 본 실험 설정 잠금 ────────────────────────────────────────────
        [Test]
        public void Lock_sets_the_preset_values_and_leaves_undecided_and_per_session_items_alone()
        {
            var cfg = new PlacementConfig
            {
                condition = PlacementConfig.ConditionView, controlMode = PlacementConfig.ModeSystemMove, xrHand = PlacementConfig.HandLeft,
                inputMode = PlacementConfig.InputModeDesktop, environment = PlacementConfig.EnvironmentNature, placementAssist = false,
                stopMode = PlacementConfig.StopModeSingle, eyeHeightMode = PlacementConfig.EyeHeightNone, hideObjectDuringItems = false,
                checkBeforeStopDistance = false, practiceInAllConditions = false,
                hidePanelInDistancePhases = true, askOptionalItems = true, disabledItems = new[] { "own" }, participantRatesWithController = true,
            };
            PlacementExperimentLock.Apply(cfg);
            Assert.That(cfg.ExperimentPresetOn, Is.True);
            Assert.That(cfg.environment, Is.EqualTo(PlacementConfig.EnvironmentNeutral));
            Assert.That(cfg.placementAssist && cfg.practiceInAllConditions && cfg.hideObjectDuringItems && cfg.checkBeforeStopDistance, Is.True);
            Assert.That(cfg.IsStopLoop && cfg.IsEyeRelative && cfg.UiBundleOn, Is.True);
            // 고정하지 않는 것(연구 책임자 결정 대기 · 세션마다 다른 것 · preset이 정하지 않는 참여자 입력)
            Assert.That(cfg.hidePanelInDistancePhases, Is.True);
            Assert.That(cfg.askOptionalItems, Is.True);
            Assert.That(cfg.disabledItems, Is.EqualTo(new[] { "own" }));
            Assert.That(cfg.participantRatesWithController, Is.True);
            Assert.That(cfg.condition, Is.EqualTo(PlacementConfig.ConditionView));
            Assert.That(cfg.controlMode, Is.EqualTo(PlacementConfig.ModeSystemMove));
            Assert.That(cfg.xrHand, Is.EqualTo(PlacementConfig.HandLeft));
            Assert.That(cfg.inputMode, Is.EqualTo(PlacementConfig.InputModeDesktop), "preset이 참여자 입력을 정하지 않는다");

            Assert.That(PlacementExperimentLock.Holds(cfg, "IFS/placement_task.scaleA.v0.json"), Is.True);
            Assert.That(PlacementExperimentLock.Holds(cfg, "IFS\\placement_task.scaleA.v0.json"), Is.True);
            Assert.That(PlacementExperimentLock.Holds(cfg, PlacementTaskText.DefaultRelativePath), Is.False, "문구 파일도 잠금 값이어야");
            Assert.That(PlacementExperimentLock.Holds(new PlacementConfig(), PlacementExperimentLock.TaskTextFile), Is.False);
        }

        [Test]
        public void Lock_stop_distance_values_equal_the_code_defaults()
        {
            // 잠금 기준값은 PlacementExperimentLock에만 적는다. 코드 기본값(G60-2·G78-a)이 바뀌면 이 시험이 깨진다 — 결정 기록과 함께 둘 다 고칠 것
            var d = new PlacementConfig();
            Assert.That(PlacementExperimentLock.StopMismatches(d), Is.Empty, string.Join("; ", PlacementExperimentLock.StopMismatches(d)));
            Assert.That((d.stopLoopRounds, d.stopLoopPracticeRounds, d.stopLoopRoundSeconds, d.stopLoopPracticeRoundSeconds, d.stopItiSeconds),
                Is.EqualTo((4, 1, 75.0, 30.0, 2.0)), "G60-2 본 4 × 75초, G78-a 연습 1 × 30초, 라운드 사이 2초");
        }

        [Test]
        public void Lock_restores_changed_stop_distance_values_and_refuses_when_they_differ()
        {
            var cfg = new PlacementConfig();
            PlacementExperimentLock.Apply(cfg);
            var text = PlacementTaskText.Load(Path.Combine(UnityEngine.Application.streamingAssetsPath, PlacementExperimentLock.TaskTextFile));
            Assert.That(PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, text), Is.Empty,
                "지금 scaleA 파일(판·G78 키)과 잠금 설정이면 거부 없음");

            cfg.stopItiSeconds = 0.5; cfg.stopLoopRounds = 2; cfg.stopLoopRoundSeconds = 20; cfg.stopLoopPracticeRoundSeconds = 75; cfg.stopLoopMaxM = 3.0;
            Assert.That(PlacementExperimentLock.Holds(cfg, PlacementExperimentLock.TaskTextFile), Is.False);
            var refusals = PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, text);
            foreach (var k in new[] { "stopItiSeconds", "stopLoopRounds", "stopLoopRoundSeconds", "stopLoopPracticeRoundSeconds", "stopLoopMaxM" })
                Assert.That(refusals.Any(x => x.Contains(k + " =")), Is.True, k);
            Assert.That(refusals.All(x => x.Contains("시작하지 않습니다")), Is.True);

            PlacementExperimentLock.Apply(cfg);
            Assert.That(PlacementExperimentLock.Holds(cfg, PlacementExperimentLock.TaskTextFile), Is.True, "다시 적용하면 기준값");
        }

        [Test]
        public void Lock_refuses_a_task_text_of_another_version_or_without_the_G78_keys()
        {
            var cfg = new PlacementConfig();
            PlacementExperimentLock.Apply(cfg);
            string path = Path.Combine(UnityEngine.Application.streamingAssetsPath, PlacementExperimentLock.TaskTextFile);
            var o = JObject.Parse(File.ReadAllText(path, Encoding.UTF8));
            Assert.That((string)o["version"], Is.EqualTo(PlacementExperimentLock.ExpectedTaskTextVersion), "잠금 판 = 지금 scaleA 파일 판");

            var old = (JObject)o.DeepClone();
            old["version"] = "0.7-scaleA";
            var r = PlacementExperimentLock.Refusals(cfg, PlacementExperimentLock.TaskTextFile, PlacementTaskText.Parse(old.ToString(), "placement_task.scaleA.v0.json"));
            Assert.That(r.Any(x => x.Contains("0.7-scaleA")), Is.True, "같은 파일 이름이어도 다른 판이면 거부");

            var noKeys = (JObject)o.DeepClone();
            var texts = (JObject)noKeys["texts"];
            foreach (var k in PlacementExperimentLock.RequiredTaskTextKeys) texts.Remove(k);
            r = PlacementExperimentLock.TaskTextProblems(PlacementTaskText.Parse(noKeys.ToString(), "placement_task.scaleA.v0.json"));
            Assert.That(r.Single(), Does.Contain("confirm_button_right").And.Contain("stop_main_start"));
            Assert.That(PlacementExperimentLock.TaskTextProblems(null), Is.Not.Empty);
        }

        [Test]
        public void Lock_summary_shows_the_values_at_a_glance()
        {
            var cfg = new PlacementConfig();
            PlacementExperimentLock.Apply(cfg);
            var lines = PlacementExperimentLock.SummaryLines(cfg, PlacementExperimentLock.TaskTextFile, "0.8-scaleA");
            string all = string.Join("\n", lines);
            Assert.That(lines.Count, Is.EqualTo(5));
            Assert.That(all, Does.Contain("neutral(후보 B)"));
            Assert.That(all, Does.Contain("loop: 연습 1 × 상한 30초 + 본 4 × 상한 75초, 라운드 사이 2초, 왕복 0.4–3.6 m · 0.25 m/s"));
            Assert.That(all, Does.Contain("판 0.8-scaleA"));
            Assert.That(all, Does.Contain("relative(기준 1.60 m)"));
            Assert.That(all, Does.Contain("placement_task.scaleA.v0.json"));
            Assert.That(all, Does.Not.Contain("팀 결정 전"));
            Assert.That(all, Does.Not.Contain("끔"), "잠금 뒤에는 고정 항목이 모두 켜져 있다");
        }

        // ── manifest ────────────────────────────────────────────────────
        [Test]
        public void Manifest_gets_lock_and_session_file_keys_only_when_set()
        {
            var cfg = new PlacementConfig();
            var info = new PlacementSessionInfo { ParticipantNumber = 1, SessionId = "SYN-M" };
            var plain = PlacementManifest.Build(cfg, info);
            Assert.That(((JObject)plain["flags"]).ContainsKey("experimentPresetLocked"), Is.False, "꺼져 있으면 기존 기록과 같은 바이트");
            Assert.That(plain.ContainsKey("sessionFiles"), Is.False);

            info.ExperimentPresetLocked = true;
            info.SessionFiles = PlacementManifest.SessionFilesJson("auto", "SYN-M", new DateTimeOffset(2026, 11, 28, 10, 0, 0, TimeSpan.FromHours(9)),
                false, false, true);
            var m = PlacementManifest.Build(cfg, info);
            Assert.That((bool)m["flags"]["experimentPresetLocked"], Is.True);
            Assert.That((string)m["sessionFiles"]["source"], Is.EqualTo("auto"));
            Assert.That((string)m["sessionFiles"]["autoSessionId"], Is.EqualTo("SYN-M"));
            Assert.That((string)m["sessionFiles"]["autoSavedAt"], Is.EqualTo("2026-11-28T10:00:00+09:00"));
            Assert.That((bool)m["sessionFiles"]["participantNumberFromFile"], Is.True);
            Assert.That(m["sessionFiles"].ToString(), Does.Not.Contain(Path.DirectorySeparatorChar == '\\' ? ":\\" : "/"), "경로는 남기지 않는다");
            var over = PlacementManifest.SessionFilesJson("auto_overridden", "SYN-M", new DateTimeOffset(2026, 11, 28, 1, 0, 0, TimeSpan.Zero), true, true, false);
            Assert.That((string)over["source"], Is.EqualTo("auto_overridden"));
            Assert.That(over.Properties().Select(x => x.Name), Is.EqualTo(new[]
                { "source", "autoSessionId", "autoSavedAt", "autoStale", "autoAlreadyRun", "participantNumberFromFile" }));
        }
    }
}
