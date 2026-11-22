// EditMode 테스트: 배치 실험(RQ V4) — 설정 검증, 공간 기하, 단계 흐름(조건별), 멈춤 거리, 기록 형식(계약 ifs-placement/0.1),
// 궤적 쓰기→재생 왕복, draft 문구 경고. UnityEngine 없이 돈다(dotnet compile-check에서도 실행).
// 회기는 PlacementSession + PlacementAutoScript(합성 입력)로 끝까지 돌린다. 기록은 임시 폴더에 쓰고 지운다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        // 계약 문자열을 여기 그대로 적어 둔다(상수를 바꾸면 이 테스트가 깨져야 한다).
        const string Headpose = "time_ms,phase,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg";
        const string Objpose = "time_ms,phase,obj_x,obj_y,obj_z,distance_m,azimuth_deg,height_m,state";
        const string Events = "time_ms,event,detail";
        const string StopCsv = "trial,practice,direction,start_distance_m,speed_mps,stop_distance_m,rt_ms,timed_out";
        const string RatingsCsv = "item,when,rating,rt_ms";
        static readonly string[] AllPhases =
            { "intro", "baseline", "pre_items", "pre_wait", "condition", "post_items", "post_wait", "stop_distance", "check_items", "done" };

        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        public static PlacementTaskText LoadText() =>
            PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath));

        /// <summary>테스트용 짧은 설정(제시 1초, 조건 12초, 시행 사이 0.5초).</summary>
        public static PlacementConfig ShortConfig(string condition, string mode = PlacementConfig.ModeStatic)
        {
            return new PlacementConfig
            {
                condition = condition, controlMode = mode, baselineSeconds = 1, conditionSeconds = 12, stopItiSeconds = 0.5,
            };
        }

        string Run(PlacementConfig cfg, int participant = 1, PlacementTrajectory replay = null, PlacementAutoScript script = null,
            PlacementTaskText text = null, string replayFile = null, double dt = 0.02, Func<PlacementSession, bool> abortWhen = null)
        {
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = participant, SessionId = "SYN-PLACE", SpecFile = "C:\\Users\\someone\\synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 22, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = "placement_task.v0.json", TaskTextVersion = "0.1",
                ReplayFile = replayFile, ReplaySha256 = replayFile != null ? "ab" : null, ReplaySourceSessionId = replay?.SourceSessionId,
            };
            text = text ?? LoadText();
            info.TaskTextDraftKeys = text.DraftKeys.ToArray();
            var warnings = new List<string>();
            var notice = PlacementTaskText.DraftNotice(text, cfg.requireSpecPhrases);
            if (notice != null) warnings.Add(notice);
            script = script ?? new PlacementAutoScript();
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records"), replay, warnings))
            {
                for (int i = 0; i < 200000 && !s.Finished; i++)
                {
                    if (abortWhen != null && abortWhen(s)) { s.Abort(); break; }
                    script.Step(s, dt, PlacementAutoScript.ScriptedHead(s.Now));
                }
                Assert.That(s.Finished, Is.True, "끝까지 돌았다");
                return s.RecordDirectory;
            }
        }

        static JObject Json(string dir, string file) => OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, file)));
        static List<string[]> Csv(string dir, string file) => File.ReadAllLines(Path.Combine(dir, file)).Skip(1).Select(l => l.Split(',')).ToList();
        static List<string> PhaseEvents(string dir) => Csv(dir, "events.csv").Where(c => c[1] == "phase").Select(c => c[2]).ToList();
        static double D(string s) => double.Parse(s, Inv);

        // ── 설정 ─────────────────────────────────────────────────────────
        [Test]
        public void Default_config_is_valid_and_bad_values_are_reported()
        {
            Assert.That(new PlacementConfig().Validate(), Is.Empty);
            Assert.That(new PlacementConfig { condition = "view", controlMode = "point_select" }.Validate(), Is.Empty);
            var bad = new PlacementConfig
            {
                condition = "watch", floorRadiusM = 2, ringRadiiM = new[] { 1.0, 3.0 }, stopMaxM = 4, conditionSeconds = 0, headSampleHz = 0,
            };
            var e = bad.Validate();
            Assert.That(e.Any(x => x.StartsWith("condition")), Is.True);
            Assert.That(e.Any(x => x.StartsWith("ringRadiiM 3")), Is.True, "고리는 바닥 안");
            Assert.That(e.Any(x => x.StartsWith("stopMaxM")), Is.True, "멈춤 거리 최대는 바닥 반지름 이하");
            Assert.That(e.Any(x => x.StartsWith("conditionSeconds")), Is.True);
            Assert.That(e.Any(x => x.StartsWith("headSampleHz")), Is.True);
            Assert.That(new PlacementConfig { condition = "view", controlMode = "replay" }.Validate().Any(x => x.Contains("replayPath")), Is.True);
            Assert.That(new PlacementConfig { condition = "view", controlMode = "orbit" }.Validate().Any(x => x.StartsWith("controlMode")), Is.True);
            Assert.That(new PlacementConfig { stopApproachStartM = 0.1 }.Validate().Any(x => x.StartsWith("stopApproachStartM")), Is.True);
            Assert.That(new PlacementConfig { stopFirstDirection = "left" }.Validate().Any(x => x.StartsWith("stopFirstDirection")), Is.True);
            Assert.Throws<ArgumentException>(() => new PlacementSession(bad, LoadText(), new PlacementSessionInfo { SessionId = "x" }, _tmp));
            Assert.That(Directory.GetDirectories(_tmp), Is.Empty, "설정 오류면 기록 폴더를 만들지 않는다");
        }

        [Test]
        public void Place_records_control_mode_none_and_config_keeps_no_paths()
        {
            var cfg = new PlacementConfig { condition = "place", controlMode = "replay", replayPath = "C:\\Users\\someone\\x\\trajectory.json" };
            Assert.That(cfg.EffectiveControlMode, Is.EqualTo("none"));
            var json = cfg.ToJson();
            Assert.That((string)json["replayFile"], Is.EqualTo("trajectory.json"));
            Assert.That(json.ToString(), Does.Not.Contain("someone"));
        }

        // ── 기하 ─────────────────────────────────────────────────────────
        [Test]
        public void Distance_azimuth_height_follow_the_contract()
        {
            var p = PlacementGeometry.FromPolar(2.0, 30, 1.1);
            Assert.That(PlacementGeometry.HorizontalDistance(p), Is.EqualTo(2.0).Within(1e-9));
            Assert.That(PlacementGeometry.AzimuthDeg(p), Is.EqualTo(30).Within(1e-9));
            Assert.That(p.Y, Is.EqualTo(1.1));
            Assert.That(p.X, Is.GreaterThan(0), "오른쪽(+x)이 +방위");
            Assert.That(PlacementGeometry.AzimuthDeg(new PVec3(0, 0, 1)), Is.EqualTo(0));
            Assert.That(PlacementGeometry.AzimuthDeg(new PVec3(1, 0, 0)), Is.EqualTo(90).Within(1e-9));
            Assert.That(PlacementGeometry.AzimuthDeg(new PVec3(-1, 0, 0)), Is.EqualTo(-90).Within(1e-9));
            Assert.That(PlacementGeometry.AzimuthDeg(new PVec3(0, 0, -1)), Is.EqualTo(180), "정 뒤는 +180 ((−180, 180])");
            Assert.That(PlacementGeometry.AzimuthDeg(new PVec3(-0.0, 0, -1)), Is.EqualTo(180), "atan2가 −180을 내도 +180으로");
            Assert.That(PlacementGeometry.AzimuthDeg(PVec3.Zero), Is.EqualTo(0));
        }

        [Test]
        public void Positions_are_clamped_to_the_floor_disc_and_height_range()
        {
            var c = PlacementGeometry.ClampToSpace(new PVec3(6, 3.5, 8), 4, 0.05, 2.5);
            Assert.That(c.HorizontalLength, Is.EqualTo(4).Within(1e-9), "경계 밖 → 경계 위");
            Assert.That(PlacementGeometry.AzimuthDeg(c), Is.EqualTo(PlacementGeometry.AzimuthDeg(new PVec3(6, 0, 8))).Within(1e-9), "방향은 지킨다");
            Assert.That(c.Y, Is.EqualTo(2.5));
            Assert.That(PlacementGeometry.ClampToSpace(new PVec3(1, -1, 1), 4, 0.05, 2.5).Y, Is.EqualTo(0.05));
            var inside = new PVec3(1, 1, -2);
            Assert.That(PlacementGeometry.ClampToSpace(inside, 4, 0.05, 2.5), Is.EqualTo(inside), "안쪽은 그대로");
        }

        [Test]
        public void Ray_tests_for_grab_and_floor_pointing()
        {
            var o = new PVec3(0, 1.6, 0);
            Assert.That(PlacementGeometry.RaySphere(o, new PVec3(0, -0.4, 3), new PVec3(0, 1.2, 3), 0.2, out double t), Is.True, "팔 길이보다 먼 물체도 광선으로 잡힘");
            Assert.That(t, Is.GreaterThan(2.5));
            Assert.That(PlacementGeometry.RaySphere(o, new PVec3(1, 0, 0), new PVec3(0, 1.2, 3), 0.2, out _), Is.False);
            Assert.That(PlacementGeometry.RaySphere(o, new PVec3(0, 0, -1), new PVec3(0, 1.6, 3), 0.2, out _), Is.False, "뒤쪽 구는 안 잡힘");
            Assert.That(PlacementGeometry.RayFloor(o, new PVec3(0, -1.6, 2), 0, out var hit), Is.True);
            Assert.That(hit.Z, Is.EqualTo(2).Within(1e-9));
            Assert.That(PlacementGeometry.RayFloor(o, new PVec3(0, 0.1, 1), 0, out _), Is.False, "위를 보면 바닥 없음");
        }

        // ── 문구 파일 ────────────────────────────────────────────────────
        [Test]
        public void Task_text_is_all_draft_with_sources_and_has_items_per_when()
        {
            var t = LoadText();
            Assert.That(t.Protocol, Is.EqualTo("placement-task"));
            Assert.That(t.DraftKeys.Count, Is.EqualTo(t.Count), "모든 문구 status draft(IRB 전)");
            Assert.That(t.ItemsFor("pre").Select(i => i.Key), Is.EqualTo(new[] { "own" }));
            Assert.That(t.ItemsFor("post").Select(i => i.Key), Is.EqualTo(new[] { "own", "want_to_know", "withdraw_attention" }));
            Assert.That(t.ItemsFor("check").Select(i => i.Key), Is.EqualTo(new[] { "placed_by_me" }));
            Assert.That(t["condition_place"], Does.StartWith("지금 이것이 있기에 알맞다고 느껴지는 자리에 놓아 주세요."));
            Assert.That(t["condition_view"], Is.EqualTo("지금 이것을 편하게 바라봐 주세요."));
            Assert.That(t["stop_distance"], Is.EqualTo("이것이 움직이는 동안, 알맞다고 느껴지는 자리에 왔을 때 버튼을 눌러 주세요."));
            var raw = File.ReadAllText(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath), Encoding.UTF8);
            var texts = (JObject)JObject.Parse(raw)["texts"];
            foreach (var p in texts.Properties())
            {
                string s = (string)p.Value["text"] + " " + (string)p.Value["anchors"]?["low"] + " " + (string)p.Value["anchors"]?["high"];
                foreach (var banned in new[] { "멀리", "치우", "치료", "내담자", "진단", "환자" })
                    Assert.That(s, Does.Not.Contain(banned), p.Name + ": 방향 암시·치료 표현 금지");
                Assert.That((string)p.Value["source"], Does.Contain("IRB 검토 전"), p.Name);
            }
        }

        [Test]
        public void Task_text_rejects_bad_when_and_missing_keys()
        {
            var raw = JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath), Encoding.UTF8));
            var badWhen = (JObject)raw.DeepClone();
            badWhen["texts"]["own"]["when"] = "later";
            Assert.Throws<FormatException>(() => PlacementTaskText.Parse(badWhen.ToString()));
            var missing = (JObject)raw.DeepClone();
            ((JObject)missing["texts"]).Remove("stop_distance");
            Assert.That(Assert.Throws<FormatException>(() => PlacementTaskText.Parse(missing.ToString())).Message, Does.Contain("stop_distance"));
        }

        [Test]
        public void Draft_phrases_warn_in_events_and_manifest_and_require_spec_refuses()
        {
            var t = LoadText();
            Assert.That(PlacementTaskText.DraftNotice(t, false), Does.Contain("초안 문구"));
            Assert.That(PlacementTaskText.SpecPhraseRefusal(t, false), Is.Null);
            Assert.That(PlacementTaskText.SpecPhraseRefusal(t, true), Does.Contain("requireSpecPhrases"));
            string dir = Run(ShortConfig("view"));
            var m = Json(dir, "manifest.json");
            Assert.That((int)m["taskText"]["draftCount"], Is.EqualTo(t.Count));
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Is.EqualTo(t.DraftKeys));
            Assert.That(Csv(dir, "events.csv").Any(c => c[1] == "warning" && string.Join(",", c.Skip(2)).Contains("초안 문구")), Is.True);
        }

        // ── 기록 형식(계약) ──────────────────────────────────────────────
        [Test]
        public void Record_folder_files_headers_and_manifest_keys_match_the_contract()
        {
            Assert.That(PlacementRecordWriter.HeadposeHeader, Is.EqualTo(Headpose));
            Assert.That(PlacementRecordWriter.ObjposeHeader, Is.EqualTo(Objpose));
            Assert.That(PlacementRecordWriter.EventsHeader, Is.EqualTo(Events));
            Assert.That(PlacementRecordWriter.StopDistanceHeader, Is.EqualTo(StopCsv));
            Assert.That(PlacementRecordWriter.RatingsHeader, Is.EqualTo(RatingsCsv));

            string dir = Run(ShortConfig("place"), participant: 7);
            Assert.That(dir, Is.EqualTo(Path.Combine(_tmp, "records", "placement", "P007", "SYN-PLACE", "20261122-010203")));
            foreach (var f in new[] { "manifest.json", "headpose.csv", "objpose.csv", "events.csv", "placement.json", "stopdistance.csv", "ratings.csv", "trajectory.json", "summary.json" })
            {
                var bytes = File.ReadAllBytes(Path.Combine(dir, f));
                Assert.That(bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB && bytes[2] == 0xBF, Is.False, f + " BOM 없음");
                Assert.That(bytes.Contains((byte)'\r'), Is.False, f + " 줄바꿈 \\n");
            }
            Assert.That(File.ReadLines(Path.Combine(dir, "headpose.csv")).First(), Is.EqualTo(Headpose));
            Assert.That(File.ReadLines(Path.Combine(dir, "objpose.csv")).First(), Is.EqualTo(Objpose));
            Assert.That(File.ReadLines(Path.Combine(dir, "stopdistance.csv")).First(), Is.EqualTo(StopCsv));
            Assert.That(File.ReadLines(Path.Combine(dir, "ratings.csv")).First(), Is.EqualTo(RatingsCsv));

            var m = Json(dir, "manifest.json");
            Assert.That(m.Properties().Select(p => p.Name), Is.EquivalentTo(new[]
            {
                "recordVersion", "participantNumber", "sessionId", "specFile", "specSha256", "startedAtUtc", "unityVersion", "headSource", "inputSource",
                "condition", "controlMode", "space", "stopDistance", "replaySource", "systemMoveTarget", "taskText", "config", "flags",
            }));
            Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-placement/0.1"));
            Assert.That((int)m["participantNumber"], Is.EqualTo(7));
            Assert.That((string)m["specFile"], Is.EqualTo("synthetic.json"), "파일 이름만");
            Assert.That(File.ReadAllText(Path.Combine(dir, "manifest.json")), Does.Not.Contain("someone"), "로컬 경로 없음");
            Assert.That((string)m["startedAtUtc"], Is.EqualTo("2026-11-22T01:02:03.000Z"));
            Assert.That((string)m["inputSource"], Is.EqualTo("auto"));
            Assert.That((string)m["condition"], Is.EqualTo("place"));
            Assert.That((string)m["controlMode"], Is.EqualTo("none"));
            Assert.That(((JObject)m["space"]).Properties().Select(p => p.Name), Is.EquivalentTo(new[] { "floorRadiusM", "ringRadiiM", "showRings", "startDistanceM", "startHeightM" }));
            Assert.That(m["space"]["ringRadiiM"].Select(r => (double)r), Is.EqualTo(new[] { 1.0, 2.0, 3.0 }));
            Assert.That(((JObject)m["stopDistance"]).Properties().Select(p => p.Name),
                Is.EquivalentTo(new[] { "speedMps", "approachStartM", "recedeStartM", "trialsPerDirection", "practiceTrials", "minM", "maxM" }));
            Assert.That(m["replaySource"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(m["systemMoveTarget"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(((JObject)m["taskText"]).Properties().Select(p => p.Name), Is.EquivalentTo(new[] { "file", "version", "draftCount", "draftKeys" }));
            Assert.That((bool)m["flags"]["autoMode"], Is.True);
            Assert.That((double)m["config"]["conditionSeconds"], Is.EqualTo(12));

            var pl = Json(dir, "placement.json");
            Assert.That(pl.Properties().Select(p => p.Name), Is.EquivalentTo(new[]
            {
                "condition", "controlMode", "phaseDurationMs", "finalX", "finalY", "finalZ", "finalDistanceM", "finalAzimuthDeg", "finalHeightM",
                "grabCount", "firstGrabMs", "heldMs", "pathLengthM", "confirmed", "confirmMs",
            }));
            var sum = Json(dir, "summary.json");
            Assert.That(sum.Properties().Select(p => p.Name), Is.EqualTo(new[] { "completed", "abortedAt", "endedAtUtc" }));
            Assert.That((bool)sum["completed"], Is.True);
            var tr = Json(dir, "trajectory.json");
            Assert.That(tr.Properties().Select(p => p.Name), Is.EqualTo(new[] { "version", "sourceSessionId", "sampleHz", "startDistanceM", "startHeightM", "samples" }));
            Assert.That(((JObject)tr["samples"][0]).Properties().Select(p => p.Name), Is.EqualTo(new[] { "t_ms", "x", "y", "z" }));

            var allowedEvents = new HashSet<string>
            {
                "phase", "grab", "release", "confirm", "point_select", "system_move_start", "system_move_end", "replay_start", "replay_end",
                "stop_trial_start", "stop_press", "stop_timeout", "rating", "auto_mode", "warning", "head_source",
                // 계약 밖에 더한 이름(보고에 적음): 회기 시작, 평정 취소, 중단·종료
                "session_start", "rating_cancel", "abort", "quit",
            };
            var evs = Csv(dir, "events.csv");
            Assert.That(evs.Select(c => c[1]).Where(e => !allowedEvents.Contains(e)), Is.Empty);
            Assert.That(Csv(dir, "objpose.csv").Select(c => c[8]).Distinct().All(s => new[] { "idle", "held", "system", "replay", "stop" }.Contains(s)), Is.True);
            var head = Csv(dir, "headpose.csv");
            Assert.That(head.All(c => c.Length == 14), Is.True);
            Assert.That(head.Where(c => c[1] == "intro").All(c => c[9] == ""), Is.True, "물체가 숨은 단계는 물체 칸 빈칸");
            Assert.That(head.Where(c => c[1] == "condition").All(c => c[12] != "" && c[13] != ""), Is.True, "머리–물체 거리·각");
        }

        // ── 조건별 단계 흐름 ─────────────────────────────────────────────
        [Test]
        public void Place_flow_records_grabs_regrab_confirm_and_final_place()
        {
            string dir = Run(ShortConfig("place"));
            Assert.That(PhaseEvents(dir), Is.EqualTo(AllPhases));
            var pl = Json(dir, "placement.json");
            Assert.That((string)pl["condition"], Is.EqualTo("place"));
            Assert.That((string)pl["controlMode"], Is.EqualTo("none"));
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(12000).Within(20));
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.6).Within(1e-3), "자동 스크립트의 두 번째 놓기 자리");
            Assert.That((double)pl["finalAzimuthDeg"], Is.EqualTo(-20).Within(0.05));
            Assert.That((double)pl["finalHeightM"], Is.EqualTo(0.9).Within(1e-3));
            Assert.That((int)pl["grabCount"], Is.EqualTo(2), "다시 잡기 1번");
            Assert.That((long)pl["firstGrabMs"], Is.EqualTo(1000).Within(40));
            Assert.That((long)pl["heldMs"], Is.EqualTo(5200).Within(100));
            Assert.That((double)pl["pathLengthM"], Is.GreaterThan(1.0));
            Assert.That((bool)pl["confirmed"], Is.True);
            Assert.That((long)pl["confirmMs"], Is.EqualTo(10000).Within(40));
            var evs = Csv(dir, "events.csv").Select(c => c[1]).ToList();
            Assert.That(evs.Count(e => e == "grab"), Is.EqualTo(2));
            Assert.That(evs.Count(e => e == "release"), Is.EqualTo(2));
            Assert.That(evs.Count(e => e == "confirm"), Is.EqualTo(1));
            var cond = Csv(dir, "objpose.csv").Where(c => c[1] == "condition").ToList();
            Assert.That(cond.Any(c => c[8] == "held"), Is.True);
            Assert.That(cond.Last()[5], Is.EqualTo("2.6000"), "objpose 거리 = 수평 거리");
        }

        [Test]
        public void Ratings_follow_items_with_one_cancel()
        {
            string dir = Run(ShortConfig("place"));
            var rows = Csv(dir, "ratings.csv");
            Assert.That(rows.Select(r => r[0] + "/" + r[1] + "/" + r[2]), Is.EqualTo(new[]
            {
                "own/pre/5", "own/post/3", "want_to_know/post/4", "withdraw_attention/post/2", "placed_by_me/check/6",
            }));
            Assert.That(rows.All(r => long.Parse(r[3]) >= 0), Is.True);
            Assert.That(Csv(dir, "events.csv").Count(c => c[1] == "rating_cancel"), Is.EqualTo(1));
        }

        [Test]
        public void View_static_keeps_the_object_at_the_start()
        {
            string dir = Run(ShortConfig("view", "static"));
            Assert.That(PhaseEvents(dir), Is.EqualTo(AllPhases));
            var pl = Json(dir, "placement.json");
            Assert.That((string)pl["controlMode"], Is.EqualTo("static"));
            Assert.That((int)pl["grabCount"], Is.EqualTo(0));
            Assert.That((double)pl["pathLengthM"], Is.EqualTo(0));
            Assert.That(pl["firstGrabMs"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((bool)pl["confirmed"], Is.False);
            Assert.That(pl["confirmMs"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(1.5));
            Assert.That((double)pl["finalAzimuthDeg"], Is.EqualTo(0));
            Assert.That((double)pl["finalHeightM"], Is.EqualTo(1.2));
            Assert.That(Csv(dir, "objpose.csv").Where(c => c[1] == "condition").All(c => c[8] == "idle" && c[5] == "1.5000"), Is.True);
        }

        [Test]
        public void View_system_move_goes_straight_to_the_target_at_constant_speed()
        {
            var cfg = ShortConfig("view", "system_move");
            string dir = Run(cfg);
            Assert.That(PhaseEvents(dir), Is.EqualTo(AllPhases));
            var m = Json(dir, "manifest.json");
            Assert.That((double)m["systemMoveTarget"]["distanceM"], Is.EqualTo(2.5));
            var pl = Json(dir, "placement.json");
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.5).Within(1e-4));
            Assert.That((double)pl["pathLengthM"], Is.EqualTo(1.0).Within(1e-3), "실제 이동 거리(1.5 → 2.5 m)");
            Assert.That((int)pl["grabCount"], Is.EqualTo(0));
            var ev = Csv(dir, "events.csv");
            long start = long.Parse(ev.Single(c => c[1] == "system_move_start")[0]);
            long end = long.Parse(ev.Single(c => c[1] == "system_move_end")[0]);
            Assert.That((end - start) / 1000.0, Is.EqualTo(1.0 / 0.25).Within(0.05), "1 m를 0.25 m/s로");
            var moving = Csv(dir, "objpose.csv").Where(c => c[8] == "system").ToList();
            Assert.That(moving.Count, Is.GreaterThan(10));
            Assert.That(moving.All(c => Math.Abs(D(c[6])) < 1e-6), Is.True, "정면 직선");
        }

        [Test]
        public void View_point_select_moves_to_the_pointed_floor_point()
        {
            string dir = Run(ShortConfig("view", "point_select"));
            var pl = Json(dir, "placement.json");
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.4).Within(1e-3));
            Assert.That((double)pl["finalAzimuthDeg"], Is.EqualTo(25).Within(0.05));
            Assert.That((double)pl["finalHeightM"], Is.EqualTo(1.2).Within(1e-6), "높이는 그대로");
            Assert.That((bool)pl["confirmed"], Is.True);
            Assert.That((long)pl["confirmMs"], Is.EqualTo(2000).Within(40));
            Assert.That((double)pl["pathLengthM"], Is.GreaterThan(0.5));
            var evs = Csv(dir, "events.csv").Select(c => c[1]).ToList();
            Assert.That(evs, Does.Contain("point_select"));
            Assert.That(evs, Does.Contain("system_move_end"));
        }

        [Test]
        public void Trajectory_written_by_place_replays_on_the_same_time_axis()
        {
            string src = Run(ShortConfig("place"));
            string trajPath = Path.Combine(src, "trajectory.json");
            var traj = PlacementTrajectory.Load(trajPath);
            Assert.That(traj.SourceSessionId, Is.EqualTo("SYN-PLACE"));
            Assert.That(traj.SampleHz, Is.EqualTo(20));
            Assert.That(traj.Samples[0].TMs, Is.EqualTo(0));
            Assert.That(traj.DurationMs, Is.EqualTo(12000).Within(20), "마지막 표본 = 단계 끝");
            var roundTrip = PlacementTrajectory.Parse(traj.Serialize());
            Assert.That(roundTrip.Samples.Select(s => (s.TMs, s.X, s.Y, s.Z)), Is.EqualTo(traj.Samples.Select(s => (s.TMs, s.X, s.Y, s.Z))), "쓰기→읽기 왕복");

            var srcPl = Json(src, "placement.json");
            var replayCfg = ShortConfig("view", "replay");
            replayCfg.replayPath = trajPath;
            string dir = Run(replayCfg, replay: traj, replayFile: trajPath);
            Assert.That(PhaseEvents(dir), Is.EqualTo(AllPhases));
            var m = Json(dir, "manifest.json");
            Assert.That((string)m["replaySource"]["file"], Is.EqualTo("trajectory.json"), "파일 이름만");
            Assert.That((string)m["replaySource"]["sourceSessionId"], Is.EqualTo("SYN-PLACE"));
            var pl = Json(dir, "placement.json");
            foreach (var k in new[] { "finalX", "finalY", "finalZ", "finalDistanceM" })
                Assert.That((double)pl[k], Is.EqualTo((double)srcPl[k]).Within(1e-3), k + ": 재생 끝 = 원본 끝");
            Assert.That((int)pl["grabCount"], Is.EqualTo(0));
            Assert.That((double)pl["pathLengthM"], Is.EqualTo((double)srcPl["pathLengthM"]).Within(0.02), "같은 경로를 지난다");

            // 재생본 조건 단계 objpose의 각 표본 = 원본 궤적의 같은 시각 위치
            var condStart = long.Parse(Csv(dir, "events.csv").First(c => c[1] == "phase" && c[2] == "condition")[0]);
            var rows = Csv(dir, "objpose.csv").Where(c => c[1] == "condition").ToList();
            Assert.That(rows.Count, Is.GreaterThan(100));
            foreach (var c in rows)
            {
                var want = traj.PositionAt(long.Parse(c[0]) - condStart);
                Assert.That(D(c[2]), Is.EqualTo(want.X).Within(2e-4), c[0]);
                Assert.That(D(c[4]), Is.EqualTo(want.Z).Within(2e-4), c[0]);
            }
            var evs = Csv(dir, "events.csv").Select(c => c[1]).ToList();
            Assert.That(evs.Count(e => e == "replay_start"), Is.EqualTo(1));
            Assert.That(evs.Count(e => e == "replay_end"), Is.EqualTo(1));
            Assert.Throws<ArgumentException>(() => new PlacementSession(replayCfg, LoadText(), new PlacementSessionInfo { SessionId = "x" }, _tmp, null), "궤적 없이 replay는 시작하지 않는다");
        }

        [Test]
        public void Trajectory_interpolates_and_holds_ends()
        {
            var t = new PlacementTrajectory { SampleHz = 20 };
            t.Add(0, new PVec3(0, 1, 1));
            t.Add(100, new PVec3(1, 1, 1));
            t.Add(300, new PVec3(1, 1, 3));
            Assert.That(t.PositionAt(-5).X, Is.EqualTo(0));
            Assert.That(t.PositionAt(50).X, Is.EqualTo(0.5).Within(1e-12));
            Assert.That(t.PositionAt(200).Z, Is.EqualTo(2).Within(1e-12));
            Assert.That(t.PositionAt(900).Z, Is.EqualTo(3));
            Assert.Throws<FormatException>(() => PlacementTrajectory.Parse("{\"version\":\"other\",\"samples\":[{\"t_ms\":0,\"x\":0,\"y\":0,\"z\":0}]}"));
        }

        [Test]
        public void Confirm_can_end_the_condition_when_configured()
        {
            var cfg = ShortConfig("place");
            cfg.conditionEndsOnConfirm = true;
            string dir = Run(cfg);
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(10000).Within(40));
            Assert.That((long)pl["confirmMs"], Is.EqualTo((long)pl["phaseDurationMs"]));
        }

        // ── 멈춤 거리 ────────────────────────────────────────────────────
        [Test]
        public void Stop_schedule_alternates_with_practice_first_and_counterbalances_by_participant()
        {
            var cfg = new PlacementConfig();
            var odd = StopDistanceSchedule.Build(cfg, 1);
            Assert.That(odd.Select(p => (p.Practice ? "P" : "") + p.Direction[0]), Is.EqualTo(new[] { "Pa", "Pr", "a", "r", "a", "r", "a", "r", "a", "r" }));
            Assert.That(odd.Select(p => p.Trial), Is.EqualTo(Enumerable.Range(1, 10)));
            Assert.That(odd.Where(p => p.IsApproach).All(p => p.StartM == 3.0), Is.True);
            Assert.That(odd.Where(p => !p.IsApproach).All(p => p.StartM == 0.5), Is.True);
            var even = StopDistanceSchedule.Build(cfg, 2);
            Assert.That(even[0].Direction, Is.EqualTo("recede"));
            cfg.stopFirstDirection = "approach";
            Assert.That(StopDistanceSchedule.Build(cfg, 2)[0].Direction, Is.EqualTo("approach"));
            cfg.stopPracticeTrials = 0;
            cfg.stopTrialsPerDirection = 1;
            Assert.That(StopDistanceSchedule.Build(cfg, 2).Count, Is.EqualTo(2));
        }

        [Test]
        public void Stop_distance_rows_record_presses_and_timeouts()
        {
            string dir = Run(ShortConfig("view"), participant: 1);
            var rows = Csv(dir, "stopdistance.csv");
            Assert.That(rows.Count, Is.EqualTo(10));
            Assert.That(rows.Select(r => r[1]), Is.EqualTo(new[] { "1", "1", "0", "0", "0", "0", "0", "0", "0", "0" }));
            Assert.That(rows.Select(r => r[2]), Is.EqualTo(new[] { "approach", "recede", "approach", "recede", "approach", "recede", "approach", "recede", "approach", "recede" }));
            Assert.That(rows.All(r => r[4] == "0.2500"), Is.True);
            // 자동 스크립트: 가까워지는 방향 1.40, 1.25, 1.30, (누르지 않음), 1.20 / 멀어지는 방향 1.60, 1.75, 1.70, 1.65, 1.80
            var expect = new[] { 1.40, 1.60, 1.25, 1.75, 1.30, 1.70, double.NaN, 1.65, 1.20, 1.80 };
            for (int i = 0; i < rows.Count; i++)
            {
                if (double.IsNaN(expect[i]))
                {
                    Assert.That(rows[i][7], Is.EqualTo("1"), "timed_out");
                    Assert.That(rows[i][5], Is.EqualTo(""), "timed_out이면 빈칸");
                    Assert.That(long.Parse(rows[i][6]), Is.EqualTo((long)((3.0 - 0.2) / 0.25 * 1000)).Within(40), "최소 거리까지 걸린 시간");
                }
                else
                {
                    Assert.That(rows[i][7], Is.EqualTo("0"));
                    Assert.That(D(rows[i][5]), Is.EqualTo(expect[i]).Within(0.0051), "trial " + rows[i][0]);
                    double start = rows[i][2] == "approach" ? 3.0 : 0.5;
                    Assert.That(long.Parse(rows[i][6]) / 1000.0, Is.EqualTo(Math.Abs(start - D(rows[i][5])) / 0.25).Within(0.05), "rt = 움직인 거리 / 속도");
                }
            }
            var evs = Csv(dir, "events.csv").Select(c => c[1]).ToList();
            Assert.That(evs.Count(e => e == "stop_trial_start"), Is.EqualTo(10));
            Assert.That(evs.Count(e => e == "stop_press"), Is.EqualTo(9));
            Assert.That(evs.Count(e => e == "stop_timeout"), Is.EqualTo(1));
            var stopRows = Csv(dir, "objpose.csv").Where(c => c[1] == "stop_distance").ToList();
            Assert.That(stopRows.All(c => c[8] == "stop" && Math.Abs(D(c[6])) < 1e-6), Is.True, "정면 직선 위에서만");
            Assert.That(stopRows.All(c => D(c[5]) >= 0.2 - 1e-9 && D(c[5]) <= 4.0 + 1e-9), Is.True);
        }

        [Test]
        public void Recede_timeout_stops_at_max_distance()
        {
            var script = new PlacementAutoScript { RecedeStopM = new[] { double.NaN } };
            var cfg = ShortConfig("view");
            cfg.stopPracticeTrials = 0;
            cfg.stopTrialsPerDirection = 1;
            cfg.stopMaxM = 2.0;
            cfg.stopApproachStartM = 1.9;
            string dir = Run(cfg, participant: 2, script: script);
            var rows = Csv(dir, "stopdistance.csv");
            Assert.That(rows[0][2], Is.EqualTo("recede"));
            Assert.That(rows[0][7], Is.EqualTo("1"));
            Assert.That(long.Parse(rows[0][6]), Is.EqualTo(6000).Within(40), "0.5 → 2.0 m를 0.25 m/s로");
            var max = Csv(dir, "objpose.csv").Where(c => c[1] == "stop_distance" && c[2 + 0] != "").Max(c => D(c[5]));
            Assert.That(max, Is.LessThanOrEqualTo(2.0 + 1e-9));
        }

        // ── 단계 건너뛰기·중단 ───────────────────────────────────────────
        [Test]
        public void Item_phases_without_items_are_skipped()
        {
            var raw = JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath), Encoding.UTF8));
            ((JObject)raw["texts"]).Remove("placed_by_me");
            raw["texts"]["own"]["when"] = "post";
            var text = PlacementTaskText.Parse(raw.ToString(), "test.json");
            string dir = Run(ShortConfig("view"), text: text);
            Assert.That(PhaseEvents(dir), Is.EqualTo(new[] { "intro", "baseline", "pre_wait", "condition", "post_items", "post_wait", "stop_distance", "done" }));
        }

        [Test]
        public void Abort_during_condition_keeps_partial_placement_and_marks_summary()
        {
            string dir = Run(ShortConfig("place"), abortWhen: s => s.Phase == PlacementPhase.Condition && s.SecondsInPhase >= 2.0);
            var sum = Json(dir, "summary.json");
            Assert.That((bool)sum["completed"], Is.False);
            Assert.That((string)sum["abortedAt"], Is.EqualTo("condition"));
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(2000).Within(40));
            Assert.That((int)pl["grabCount"], Is.EqualTo(1));
            var ev = Csv(dir, "events.csv");
            Assert.That(ev.Any(c => c[1] == "release" && string.Join(",", c.Skip(2)).Contains("reason=phase_end")), Is.True, "잡은 채 끝나면 놓기로 기록");
            Assert.That(ev.Last()[1] + "," + ev.Last()[2], Is.EqualTo("phase,done"));
        }

        [Test]
        public void Sample_rate_matches_head_sample_hz_and_samples_are_ordered()
        {
            string dir = Run(ShortConfig("view", "static"));
            var head = Csv(dir, "headpose.csv").Where(c => c[1] == "condition").Select(c => long.Parse(c[0])).ToList();
            var obj = Csv(dir, "objpose.csv").Where(c => c[1] == "condition").Select(c => long.Parse(c[0])).ToList();
            Assert.That(obj, Is.EqualTo(head), "objpose와 headpose는 같은 표본 시각");
            var gaps = head.Zip(head.Skip(1), (a, b) => b - a).ToList();
            Assert.That(gaps.All(g => g >= 49 && g <= 61), Is.True, "20 Hz, dt 0.02 → 60 ms(프레임당 최대 1개)");
        }
    }
}
