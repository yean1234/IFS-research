// EditMode 테스트: 배치 실험(RQ V4) — 설정 검증, 공간 기하, 단계 흐름(조건별), 멈춤 거리, 기록 형식(계약 ifs-placement/0.2),
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

        /// <summary>participantOverride: 자동 스크립트가 만든 참여자 입력을 (세션, dt, 입력)으로 바꾼다. setup: 시작 전 info·경고를 고친다.</summary>
        string Run(PlacementConfig cfg, int participant = 1, PlacementTrajectory replay = null, PlacementAutoScript script = null,
            PlacementTaskText text = null, string replayFile = null, double dt = 0.02, Func<PlacementSession, bool> abortWhen = null,
            Func<PlacementSession, double, PlacementInputFrame, PlacementInputFrame> participantOverride = null,
            Action<PlacementSessionInfo, List<string>> setup = null)
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
            setup?.Invoke(info, warnings);
            script = script ?? new PlacementAutoScript();
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records"), replay, warnings))
            {
                for (int i = 0; i < 200000 && !s.Finished; i++)
                {
                    if (abortWhen != null && abortWhen(s)) { s.Abort(); break; }
                    var head = PlacementAutoScript.ScriptedHead(s.Now);
                    var f = script.Participant(s, dt);
                    if (participantOverride != null) f = participantOverride(s, dt, f);
                    s.Tick(dt, f, head);   // = script.Step(s, dt, head)
                    script.Experimenter(s);
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
            Assert.That(t.ItemsFor("pre").Select(i => i.Key), Is.EqualTo(new[] { "own", "distance_feel" }), "거리감(G59)은 사전 맨 끝");
            Assert.That(t.ItemsFor("post").Select(i => i.Key), Is.EqualTo(new[] { "own", "appearance_match", "representativeness", "want_to_know", "withdraw_attention", "distance_feel" }),
                "두 평정 문항(G13)은 기본 사후만, 거리감(G59)은 사후 맨 끝");
            Assert.That(t.ItemsFor("check").Select(i => i.Key), Is.EqualTo(new[] { "placed_by_me", "place_fit" }), "G59 자리 평정은 placed_by_me 뒤(G60에서 want_move를 뺌)");
            Assert.That(t.Items.Any(i => i.Key == "want_move"), Is.False, "G60: want_move 없음(0.6)");
            foreach (var k in new[] { "distance_feel", "place_fit" })
            {
                var src = (string)JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath), Encoding.UTF8))["texts"][k]["source"];
                Assert.That(src, Does.Contain("docs/decisions.md G59, 2026-11-25"), k + ": 출처");
                Assert.That(t.Status(k), Is.EqualTo("draft"), k);
            }
            var dist = t.Items.Single(i => i.Key == "distance_feel");
            Assert.That((dist.AnchorLow, dist.AnchorHigh, dist.Min, dist.Max), Is.EqualTo(("매우 가깝다", "매우 멀다", 1, 7)));
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
                "condition", "controlMode", "space", "stopDistance", "object", "replaySource", "systemMoveTarget", "taskText", "config", "flags",
                "selection", "appliedOverrides",   // 0.2 추가
            }));
            Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-placement/0.2"));
            Assert.That(m["selection"].Type, Is.EqualTo(JTokenType.Null), "선택 파일이 없으면 null");
            Assert.That(((JObject)m["appliedOverrides"]).Count, Is.EqualTo(0), "덮어쓰기가 없으면 빈 객체");
            Assert.That((int)m["participantNumber"], Is.EqualTo(7));
            Assert.That((string)m["specFile"], Is.EqualTo("synthetic.json"), "파일 이름만");
            Assert.That(File.ReadAllText(Path.Combine(dir, "manifest.json")), Does.Not.Contain("someone"), "로컬 경로 없음");
            Assert.That((string)m["startedAtUtc"], Is.EqualTo("2026-11-22T01:02:03.000Z"));
            Assert.That((string)m["inputSource"], Is.EqualTo("auto"));
            Assert.That((string)m["condition"], Is.EqualTo("place"));
            Assert.That((string)m["controlMode"], Is.EqualTo("none"));
            Assert.That(((JObject)m["space"]).Properties().Select(p => p.Name), Is.EquivalentTo(new[] { "floorRadiusM", "ringRadiiM", "showRings", "startDistanceM", "startHeightM", "startPlacementSource" }));
            Assert.That((string)m["space"]["startPlacementSource"], Is.EqualTo("experiment_config"), "시작 자리는 실험 설정(spec layout 아님)");
            Assert.That(((JObject)m["object"]).Properties().Select(p => p.Name), Is.EqualTo(new[] { "boundingRadiusM" }));
            Assert.That(m["object"]["boundingRadiusM"].Type, Is.EqualTo(JTokenType.Null), "구할 수 없으면 null(dotnet 테스트에는 렌더러가 없다)");
            Assert.That((bool)m["flags"]["layoutIgnored"], Is.False);
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
                "grabCount", "firstGrabMs", "heldMs", "pathLengthM", "confirmed", "confirmMs", "conditionCompleted",
            }));
            Assert.That((bool)pl["conditionCompleted"], Is.True, "정해진 길이를 다 채움");
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
                // 자동 응답은 5, 3, 4, 2, 6, 4를 차례로 돈다(G59 문항이 끼어 값이 한 칸씩 밀림)
                "own/pre/5", "distance_feel/pre/3",
                "own/post/4", "appearance_match/post/2", "representativeness/post/6", "want_to_know/post/4", "withdraw_attention/post/5", "distance_feel/post/3",
                "placed_by_me/check/4", "place_fit/check/2",
            }));
            Assert.That(rows.All(r => long.Parse(r[3]) >= 0), Is.True);
            Assert.That(Csv(dir, "events.csv").Count(c => c[1] == "rating_cancel"), Is.EqualTo(1));
        }

        // ── 점검 문항을 멈춤 거리 앞으로(G59, checkBeforeStopDistance) ────
        [Test]
        public void CheckBeforeStopDistance_asks_check_items_right_after_post_items()
        {
            var d = new PlacementConfig();
            Assert.That(d.checkBeforeStopDistance, Is.False, "기본: 점검은 멈춤 거리 뒤(예전 순서)");
            Assert.That(d.ToJson().ContainsKey("checkBeforeStopDistance"), Is.False, "기본값이면 config에 넣지 않는다(기록 바이트 동일)");
            Assert.That(new PlacementConfig { checkBeforeStopDistance = true }.Clone().checkBeforeStopDistance, Is.True);

            var moved = new[] { "intro", "baseline", "pre_items", "pre_wait", "condition", "post_items", "check_items", "post_wait", "stop_distance", "done" };
            foreach (var (cond, mode) in new[] { ("place", PlacementConfig.ModeStatic), ("view", PlacementConfig.ModeStatic), ("view", PlacementConfig.ModePointSelect) })
            {
                var cfg = ShortConfig(cond, mode);
                cfg.checkBeforeStopDistance = true;
                Assert.That(cfg.Validate(), Is.Empty);
                var checkPositions = new List<PVec3>();
                PVec3 final = default;
                string dir = Run(cfg, participantOverride: (s, dt, f) =>
                {
                    if (s.Phase == PlacementPhase.CheckItems && s.CurrentItem != null) { checkPositions.Add(s.ObjectPosition); final = s.ConditionFinalPosition; }
                    return f;
                });
                string tag = cond + "/" + mode;
                Assert.That(PhaseEvents(dir), Is.EqualTo(moved), tag);
                var ev = Csv(dir, "events.csv");
                long lastCheck = ev.Where(c => c[1] == "rating" && c[2].Contains("when=check")).Max(c => long.Parse(c[0], Inv));
                long firstTrial = ev.Where(c => c[1] == "stop_trial_start").Min(c => long.Parse(c[0], Inv));
                Assert.That(lastCheck, Is.LessThan(firstTrial), tag + ": 점검 평정이 멈춤 거리 시행보다 먼저");
                Assert.That(Csv(dir, "ratings.csv").Where(r => r[1] == "check").Select(r => r[0]), Is.EqualTo(new[] { "placed_by_me", "place_fit" }), tag);
                Assert.That(Csv(dir, "stopdistance.csv"), Is.Not.Empty, tag + ": 멈춤 거리는 그대로 한다");
                Assert.That(checkPositions, Is.Not.Empty);
                Assert.That(checkPositions.All(p => p.Equals(final)), Is.True, tag + ": 점검 동안 물체는 조건 단계가 끝난 자리");
                var m = Json(dir, "manifest.json");
                Assert.That((bool)m["config"]["checkBeforeStopDistance"], Is.True, tag);
                Assert.That(((JObject)m["config"]).Properties().Last().Name, Is.EqualTo("checkBeforeStopDistance"), "새 키는 config 맨 끝");
                Assert.That((bool)Json(dir, "summary.json")["completed"], Is.True);
            }

            // 점검 문항을 모두 끄면 점검 단계째 건너뛰고 사후 대기로 간다
            var off = ShortConfig("view");
            off.checkBeforeStopDistance = true;
            off.disabledItems = new[] { "placed_by_me", "place_fit" };
            Assert.That(PhaseEvents(Run(off)), Is.EqualTo(moved.Where(p => p != "check_items")));

            // 점검 단계에서 중단하면 abortedAt = check_items(조건 단계 뒤 — 분석기 PHASES_AFTER_CONDITION에 들어 있음)
            var ab = ShortConfig("place");
            ab.checkBeforeStopDistance = true;
            string aborted = Run(ab, abortWhen: s => s.Phase == PlacementPhase.CheckItems && s.SecondsInPhase > 0.5);
            Assert.That((string)Json(aborted, "summary.json")["abortedAt"], Is.EqualTo("check_items"));
            Assert.That(Csv(aborted, "stopdistance.csv"), Is.Empty);
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
            // G86: 확인 뒤 확정 알림(ConfirmNoticeSeconds) 동안 기다렸다가 끝난다 — phaseDurationMs = confirmMs + 알림
            Assert.That((long)pl["confirmMs"], Is.EqualTo(10000).Within(40));
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo((long)pl["confirmMs"] + 2000).Within(40));
            Assert.That((bool)pl["conditionCompleted"], Is.True, "설정으로 정한 끝(확인)은 중단이 아니다");
        }

        // ── G86(2026-11-29): 직접 배치는 확인으로 조건 단계를 끝낸다 ─────────────
        static PlacementConfig G86Config(string condition = "place", string mode = PlacementConfig.ModeStatic)
        {
            var cfg = ShortConfig(condition, mode);
            cfg.conditionSeconds = 20;   // 확인(10초) + 알림(2초)이 제한 시간보다 앞서게
            cfg.conditionEndsOnConfirm = true;
            return cfg;
        }

        static List<string[]> CondEvents(string dir, string name) => Csv(dir, "events.csv").Where(c => c[1] == name).ToList();

        [Test]
        public void G86_confirm_ends_place_condition_early_after_the_notice()
        {
            var keys = new List<string>();
            string dir = Run(G86Config(), participantOverride: (s, dt, f) =>
            {
                if (s.Phase == PlacementPhase.Condition && s.ConditionClosing) keys.Add(s.ParticipantTextKey);
                return f;
            });
            Assert.That(PhaseEvents(dir), Is.EqualTo(AllPhases), "확인으로 끝나도 다음 단계로 그대로 간다");
            var pl = Json(dir, "placement.json");
            Assert.That((bool)pl["confirmed"], Is.True);
            Assert.That((long)pl["confirmMs"], Is.EqualTo(10000).Within(40));
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(12000).Within(40), "실제 조건 단계 길이 = 확인 + 2초 알림(제한 20초보다 짧다)");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("confirmed"));
            Assert.That((bool)pl["conditionEndsOnConfirm"], Is.True);
            Assert.That((int)pl["confirmIgnoredHeld"], Is.EqualTo(0));
            Assert.That((int)pl["grabCount"], Is.EqualTo(2), "확인 전까지 잡아 옮긴 횟수(다시 잡기 1번)");
            Assert.That((bool)pl["conditionCompleted"], Is.True);
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.6).Within(1e-3), "확인한 자리 그대로");
            Assert.That(keys, Is.Not.Empty);
            Assert.That(keys.All(k => k == PlacementTaskText.ConfirmDoneKey), Is.True, "알림 동안 「정했어요.」만 보인다: " + string.Join(" | ", keys.Distinct()));
            var end = CondEvents(dir, "condition_end").Single();
            Assert.That(end[2], Does.StartWith("reason=confirmed;duration_ms="));
            Assert.That(end[2], Does.Contain(";grab_count=2;confirm_ignored_held=0"));
            Assert.That(CondEvents(dir, "confirm").Count, Is.EqualTo(1));
        }

        [Test]
        public void G86_without_confirm_the_place_condition_ends_at_the_time_limit()
        {
            string dir = Run(G86Config(), script: new PlacementAutoScript { ConfirmAtSeconds = -1 });
            var pl = Json(dir, "placement.json");
            Assert.That((bool)pl["confirmed"], Is.False);
            Assert.That(pl["confirmMs"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40), "확인하지 않으면 conditionSeconds에 끝난다");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("timeout"));
            Assert.That((bool)pl["conditionCompleted"], Is.True);
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.6).Within(1e-3), "마지막으로 놓은 자리");
            Assert.That(CondEvents(dir, "condition_end").Single()[2], Does.StartWith("reason=timeout;duration_ms="));
        }

        [Test]
        public void G86_confirm_while_holding_is_ignored()
        {
            bool pressed = false;
            string dir = Run(G86Config(), participantOverride: (s, dt, f) =>
            {
                // 첫 이동(1–4초) 도중 쥔 채로 확인을 한 번 누른다
                if (s.Phase == PlacementPhase.Condition && s.Held && !pressed && s.SecondsInPhase >= 2.0) { pressed = true; f.ConfirmDown = true; }
                return f;
            });
            Assert.That(pressed, Is.True);
            var ign = CondEvents(dir, "confirm_ignored");
            Assert.That(ign.Count, Is.EqualTo(1));
            Assert.That(ign[0][2], Does.StartWith("reason=held;"));
            var pl = Json(dir, "placement.json");
            Assert.That((int)pl["confirmIgnoredHeld"], Is.EqualTo(1));
            Assert.That((long)pl["confirmMs"], Is.EqualTo(10000).Within(40), "받은 확인은 놓은 뒤의 확인 하나");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("confirmed"));
            Assert.That((int)pl["grabCount"], Is.EqualTo(2), "쥔 채 누른 확인이 놓기를 일으키지 않는다(이동은 그대로 이어짐)");
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.6).Within(1e-3));
            var rel = CondEvents(dir, "release");
            Assert.That(rel.Count, Is.EqualTo(2));
            Assert.That(rel.All(r => r[2].EndsWith("reason=button")), Is.True, "확인으로 놓아지지 않았다");
            Assert.That(CondEvents(dir, "confirm").Count, Is.EqualTo(1));
        }

        [Test]
        public void G86_object_cannot_be_grabbed_or_moved_during_the_notice()
        {
            PVec3? atConfirm = null;
            int tries = 0;
            string dir = Run(G86Config(), participantOverride: (s, dt, f) =>
            {
                if (s.Phase != PlacementPhase.Condition || !s.ConditionClosing) return f;
                atConfirm = atConfirm ?? s.ObjectPosition;
                tries++;
                // 알림 동안: 물체를 겨눠 잡기·당기기·확인을 계속 누른다 — 아무것도 받지 않아야 한다
                var origin = new PVec3(0.0, 1.2, 0.0);
                return new PlacementInputFrame
                {
                    HasRay = true, RayOrigin = origin, RayDirection = (s.ObjectPosition - origin).Normalized,
                    GrabDown = true, GrabHeld = true, PushPullAxis = 1, PushPullDeltaM = 0.5, ConfirmDown = true,
                };
            });
            Assert.That(tries, Is.GreaterThan(50), "알림 2초 동안 여러 프레임 눌렀다");
            var pl = Json(dir, "placement.json");
            Assert.That((int)pl["grabCount"], Is.EqualTo(2), "알림 동안 잡기 없음");
            Assert.That((double)pl["finalX"], Is.EqualTo(atConfirm.Value.X).Within(1e-4), "최종 자리 = 확인한 순간의 자리");
            Assert.That((double)pl["finalY"], Is.EqualTo(atConfirm.Value.Y).Within(1e-4));
            Assert.That((double)pl["finalZ"], Is.EqualTo(atConfirm.Value.Z).Within(1e-4));
            Assert.That(CondEvents(dir, "confirm").Count, Is.EqualTo(1), "알림 동안 확인을 다시 받지 않는다");
            Assert.That(CondEvents(dir, "grab").Count, Is.EqualTo(2));
            long confirmT = long.Parse(CondEvents(dir, "confirm")[0][0]);
            var after = Csv(dir, "objpose.csv").Where(c => c[1] == "condition" && long.Parse(c[0]) > confirmT).ToList();
            Assert.That(after, Is.Not.Empty);
            Assert.That(after.All(c => c[8] == "idle"), Is.True);
            Assert.That(after.Select(c => c[2] + c[3] + c[4]).Distinct().Count(), Is.EqualTo(1), "알림 동안 물체가 움직이지 않는다");
        }

        [Test]
        public void G86_abort_during_the_notice_is_recorded_as_aborted()
        {
            string dir = Run(G86Config(), abortWhen: s => s.Phase == PlacementPhase.Condition && s.ConditionClosing && s.SecondsInPhase >= 11.0);
            var pl = Json(dir, "placement.json");
            Assert.That((bool)pl["confirmed"], Is.True, "확인은 받은 뒤");
            Assert.That((bool)pl["conditionCompleted"], Is.False);
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("aborted"));
        }

        [Test]
        public void G86_view_conditions_keep_the_fixed_length_even_when_A_is_pressed()
        {
            foreach (var mode in new[] { PlacementConfig.ModeStatic, PlacementConfig.ModePointSelect, PlacementConfig.ModeSystemMove })
            {
                int presses = 0;
                string dir = Run(G86Config("view", mode), participantOverride: (s, dt, f) =>
                {
                    if (s.Phase == PlacementPhase.Condition && s.SecondsInPhase >= 3.0 && (++presses % 25) == 0) f.ConfirmDown = true;   // A를 여러 번
                    return f;
                });
                Assert.That(presses, Is.GreaterThan(0), mode);
                var pl = Json(dir, "placement.json");
                Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40), mode + ": 보기만은 길이 고정");
                Assert.That((string)pl["conditionEndReason"], Is.EqualTo("timeout"), mode);
                Assert.That((bool)pl["conditionCompleted"], Is.True, mode);
                Assert.That(CondEvents(dir, "confirm"), Is.Empty, mode + ": 보기만에는 직접 배치 확인이 없다");
                Assert.That(CondEvents(dir, "confirm_ignored"), Is.Empty, mode);
                Directory.Delete(dir, true);
            }
        }

        [Test]
        public void G86_release_and_confirm_in_the_same_frame_is_ignored_and_the_next_frame_confirm_is_taken()
        {
            // CP22-1: 프레임 시작 때 쥐고 있었으면 그 프레임에 놓아도 확인은 쥔 채 확인으로 본다. 다음 프레임부터의 확인만 받는다
            int stage = 0;
            double releasedAt = double.NaN;
            string dir = Run(G86Config(), script: new PlacementAutoScript { ConfirmAtSeconds = -1 }, participantOverride: (s, dt, f) =>
            {
                if (s.Phase != PlacementPhase.Condition) return f;
                if (stage == 0 && s.Held && s.SecondsInPhase >= 2.0)
                {
                    stage = 1;
                    releasedAt = s.SecondsInPhase;
                    return new PlacementInputFrame { HasRay = f.HasRay, RayOrigin = f.RayOrigin, RayDirection = f.RayDirection, GrabHeld = false, ConfirmDown = true };
                }
                if (stage == 1) { stage = 2; f.GrabDown = f.GrabHeld = false; f.ConfirmDown = true; }   // 놓은 다음 프레임
                return f;
            });
            Assert.That(stage, Is.EqualTo(2));
            var ign = CondEvents(dir, "confirm_ignored");
            Assert.That(ign.Count, Is.EqualTo(1));
            Assert.That(ign[0][2], Does.StartWith("reason=held;"));
            var rel = CondEvents(dir, "release");
            Assert.That(rel.Count, Is.EqualTo(1), "같은 프레임에 놓기는 그대로 일어난다");
            Assert.That(rel[0][2], Does.EndWith("reason=button"));
            Assert.That(long.Parse(rel[0][0]), Is.EqualTo(long.Parse(ign[0][0])), "놓기와 무시된 확인이 같은 프레임");
            var pl = Json(dir, "placement.json");
            Assert.That((int)pl["confirmIgnoredHeld"], Is.EqualTo(1));
            Assert.That((bool)pl["confirmed"], Is.True);
            // releasedAt = 놓은 프레임의 Tick 앞 시각 → 놓은 프레임 = +0.02 s, 그 다음 프레임 = +0.04 s
            Assert.That((long)pl["confirmMs"], Is.EqualTo((long)Math.Round((releasedAt + 0.04) * 1000)).Within(2), "놓은 다음 프레임의 확인");
            Assert.That((long)pl["confirmMs"] - long.Parse(ign[0][0]) + long.Parse(Csv(dir, "events.csv").First(e => e[1] == "phase" && e[2] == "condition")[0]),
                Is.EqualTo(20).Within(2), "무시된 확인 바로 다음 프레임");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("confirmed"));
            Assert.That((int)pl["grabCount"], Is.EqualTo(1), "두 번째 이동 전에 끝났다");
        }

        [Test]
        public void G86_confirm_arriving_in_the_frame_that_reaches_the_limit_is_not_taken()
        {
            bool pressed = false;
            string dir = Run(G86Config(), script: new PlacementAutoScript { ConfirmAtSeconds = -1 }, participantOverride: (s, dt, f) =>
            {
                // 이번 Tick에서 conditionSeconds(20)에 닿는 프레임에 확인
                if (s.Phase == PlacementPhase.Condition && !pressed && s.SecondsInPhase + dt >= 20.0 - 1e-9) { pressed = true; f.ConfirmDown = true; }
                return f;
            });
            Assert.That(pressed, Is.True);
            var pl = Json(dir, "placement.json");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("timeout"), "상한에 닿은 프레임은 입력보다 시간 끝이 먼저");
            Assert.That((bool)pl["confirmed"], Is.False);
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40));
            Assert.That(CondEvents(dir, "confirm"), Is.Empty);
        }

        [Test]
        public void G86_limit_passing_during_the_notice_still_ends_as_confirmed_after_the_notice()
        {
            string dir = Run(G86Config(), script: new PlacementAutoScript { ConfirmAtSeconds = 19.0 });
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["confirmMs"], Is.EqualTo(19000).Within(40));
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("confirmed"));
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(21000).Within(40), "알림 2초를 마친 뒤 끝난다(상한 20초를 넘김)");
            Assert.That((bool)pl["conditionCompleted"], Is.True);
        }

        [Test]
        public void G86_view_replay_does_not_end_on_confirm()
        {
            var traj = new PlacementTrajectory { SourceSessionId = "SYN-SRC", SampleHz = 20 };
            traj.Add(0, new PVec3(0, 1.2, 1.5));
            traj.Add(5000, new PVec3(1.0, 1.0, 2.0));
            var cfg = G86Config("view", PlacementConfig.ModeReplay);
            cfg.replayPath = "synthetic_trajectory.json";
            int presses = 0;
            string dir = Run(cfg, replay: traj, replayFile: "synthetic_trajectory.json", participantOverride: (s, dt, f) =>
            {
                if (s.Phase == PlacementPhase.Condition && (++presses % 25) == 0) { f.ConfirmDown = true; f.GrabDown = f.GrabHeld = true; }
                return f;
            });
            Assert.That(presses, Is.GreaterThan(0));
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40), "replay는 확인 입력과 상관없이 길이 고정");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("timeout"));
            Assert.That(CondEvents(dir, "confirm"), Is.Empty);
            Assert.That(CondEvents(dir, "confirm_ignored"), Is.Empty);
        }

        [Test]
        public void G86_xr_loss_during_the_condition_keeps_the_timer_running()
        {
            // 지금 동작을 고정하는 시험: 조건 단계는 XR이 끊겨도 제한 시간이 그대로 흐른다(CP20에서 남긴 것).
            // 끊긴 동안 멈출지는 책임자에게 물어 둔 상태다 — 답이 오면 이 시험을 함께 고친다. 동작은 바꾸지 않았다.
            bool lost = false, regained = false;
            string dir = Run(G86Config(), script: new PlacementAutoScript { ConfirmAtSeconds = -1 },
                setup: (info, w) => info.XrMonitored = true,
                participantOverride: (s, dt, f) =>
                {
                    if (s.Phase == PlacementPhase.Condition && !lost && s.SecondsInPhase >= 9.0) { lost = true; s.ReportXrHead(false); }
                    else if (lost && !regained && s.Phase == PlacementPhase.Condition && s.SecondsInPhase >= 15.0) { regained = true; s.ReportXrHead(true); }
                    else if (!lost || regained) s.ReportXrHead(true);
                    return f;
                });
            Assert.That(lost && regained, Is.True);
            var evs = Csv(dir, "events.csv");
            Assert.That(evs.Count(e => e[1] == "xr_lost" && e[2].Contains("phase=condition")), Is.EqualTo(1));
            Assert.That(evs.Count(e => e[1] == "xr_regained"), Is.EqualTo(1));
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40), "끊긴 6초도 조건 단계 시간에 든다(멈추지 않음)");
            Assert.That((string)pl["conditionEndReason"], Is.EqualTo("timeout"));
        }

        [Test]
        public void G86_off_keeps_the_old_behavior_confirm_while_holding_releases_and_length_is_fixed()
        {
            bool pressed = false;
            var cfg = G86Config();
            cfg.conditionEndsOnConfirm = false;
            string dir = Run(cfg, participantOverride: (s, dt, f) =>
            {
                if (s.Phase == PlacementPhase.Condition && s.Held && !pressed && s.SecondsInPhase >= 2.0) { pressed = true; f.ConfirmDown = true; }
                return f;
            });
            var pl = Json(dir, "placement.json");
            Assert.That((long)pl["phaseDurationMs"], Is.EqualTo(20000).Within(40));
            Assert.That(pl["conditionEndReason"], Is.Null, "꺼진 설정의 placement.json에는 새 필드가 없다");
            Assert.That(pl["conditionEndsOnConfirm"], Is.Null);
            Assert.That(CondEvents(dir, "condition_end"), Is.Empty);
            Assert.That(CondEvents(dir, "release").Any(r => r[2].EndsWith("reason=confirm")), Is.True, "예전처럼 쥔 채 확인은 놓고 확정");
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
            foreach (var k in new[] { "placed_by_me", "place_fit" }) ((JObject)raw["texts"]).Remove(k);   // 점검 문항 없음
            raw["texts"]["own"]["when"] = "post";
            raw["texts"]["distance_feel"]["when"] = "post";   // 사전 문항 없음(G59 거리감도 사후만으로)
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
            Assert.That((bool)pl["conditionCompleted"], Is.False, "중단으로 조기 종료한 조건 단계");
            var ev = Csv(dir, "events.csv");
            Assert.That(ev.Any(c => c[1] == "release" && string.Join(",", c.Skip(2)).Contains("reason=phase_end")), Is.True, "잡은 채 끝나면 놓기로 기록");
            Assert.That(ev.Last()[1] + "," + ev.Last()[2], Is.EqualTo("phase,done"));
        }

        // ── 멈춤 거리 경계(CP7 F2·F9) ───────────────────────────────────
        static PlacementConfig OneTrialEach()
        {
            var cfg = ShortConfig("view");
            cfg.stopPracticeTrials = 0;
            cfg.stopTrialsPerDirection = 1;
            return cfg;
        }

        [Test]
        public void Stop_button_held_before_the_trial_does_not_stop_it()
        {
            // (가) 눌림 상태를 StopDown으로 계속 주는 입력(잘못 만든 XR 구현 흉내): 시행 전부터 0.25 m 갈 때까지 누르고 있다가 떼고, 0.5 m 갔을 때 다시 누름
            // (나) 올바른 입력: 시행 전(시행 사이 숨김)에 한 번 누르고 0.25 m 갈 때까지 누르고만 있다가 떼고, 0.5 m 갔을 때 다시 누름
            foreach (bool repeatDown in new[] { true, false })
            {
                bool pressedOnce = false;
                string dir = Run(OneTrialEach(), participant: 1, script: new PlacementAutoScript { ApproachStopM = new[] { double.NaN } },
                    participantOverride: (s, dt, f) =>
                    {
                        if (s.Phase != PlacementPhase.StopDistance || !s.StopTrialsStarted) return f;
                        var plan = s.CurrentStopTrial;
                        if (plan != null && (plan.Trial != 1 || !s.StopTrialActive)) return f;   // 첫 시행(approach)과 그 앞 숨김 시간만
                        double moved = s.StopTrialActive ? 3.0 - s.StopDistanceNow : 0;
                        if (moved < 0.25)
                        {
                            f.StopHeld = true;
                            f.StopDown = repeatDown || !pressedOnce;
                            pressedOnce = true;
                        }
                        else if (moved >= 0.5) { f.StopDown = true; f.StopHeld = true; }
                        return f;
                    });
                var rows = Csv(dir, "stopdistance.csv");
                Assert.That(rows[0][2], Is.EqualTo("approach"));
                Assert.That(rows[0][7], Is.EqualTo("0"), "누름으로 끝남");
                Assert.That(D(rows[0][5]), Is.EqualTo(2.5).Within(0.011), $"다시 누른 자리(0.5 m 뒤)에서 멈춤 — 미리 누른 버튼으로 바로 멈추지 않음(repeatDown={repeatDown})");
                Assert.That(long.Parse(rows[0][6]), Is.EqualTo(2000).Within(45));
                Assert.That(rows[1][2], Is.EqualTo("recede"));
                Assert.That(D(rows[1][5]), Is.EqualTo(1.60).Within(0.0051), "다음 시행은 평소대로");
            }
        }

        [Test]
        public void Press_on_the_frame_that_reaches_the_limit_counts_as_a_press()
        {
            const double speed = 0.25, minM = 0.2;
            bool pressed = false;
            string dir = Run(OneTrialEach(), participant: 1, script: new PlacementAutoScript { ApproachStopM = new[] { double.NaN } },
                participantOverride: (s, dt, f) =>
                {
                    if (pressed || s.Phase != PlacementPhase.StopDistance || !s.StopTrialActive || !s.CurrentStopTrial.IsApproach) return f;
                    if (s.StopDistanceNow - speed * dt <= minM + 1e-9) { f.StopDown = f.StopHeld = true; pressed = true; }   // 경계에 닿는 바로 그 프레임
                    return f;
                });
            Assert.That(pressed, Is.True);
            var rows = Csv(dir, "stopdistance.csv");
            Assert.That(rows[0][2], Is.EqualTo("approach"));
            Assert.That(rows[0][7], Is.EqualTo("0"), "같은 프레임이면 누름이 이긴다(timed_out 아님)");
            Assert.That(rows[0][5], Is.EqualTo("0.2000"), "거리 = 경계값");
            Assert.That(long.Parse(rows[0][6]), Is.EqualTo((long)((3.0 - minM) / speed * 1000)).Within(20));
            var evs = Csv(dir, "events.csv");
            Assert.That(evs.Count(c => c[1] == "stop_press" && string.Join(",", c.Skip(2)).StartsWith("trial=1;")), Is.EqualTo(1));
            Assert.That(evs.Any(c => c[1] == "stop_timeout"), Is.False);
        }

        [Test]
        public void Stop_distance_is_the_position_after_this_frames_move()
        {
            // 기록 거리 = 시작 거리 ∓ 속도 × rt(이번 프레임 이동을 먼저 반영) — 누른 순간과의 차는 속도 × dt 이하
            string dir = Run(ShortConfig("view"), participant: 1);
            var pressed = Csv(dir, "stopdistance.csv").Where(r => r[7] == "0").ToList();
            Assert.That(pressed.Count, Is.EqualTo(9));
            foreach (var r in pressed)
            {
                double start = D(r[3]), d = D(r[5]), rt = long.Parse(r[6]) / 1000.0;
                double expect = r[2] == "approach" ? start - 0.25 * rt : start + 0.25 * rt;
                Assert.That(d, Is.EqualTo(expect).Within(0.25 * 0.0005 + 1e-4), "trial " + r[0]);
            }
        }

        [Test]
        public void Different_dt_gives_the_same_condition_length_and_stop_trial_count()
        {
            string a = Run(ShortConfig("view", "static"), dt: 0.02);
            string b = Run(ShortConfig("view", "static"), dt: 0.011);
            long da = (long)Json(a, "placement.json")["phaseDurationMs"], db = (long)Json(b, "placement.json")["phaseDurationMs"];
            Assert.That(da, Is.EqualTo(12000).Within(20), "dt 0.02");
            Assert.That(db, Is.EqualTo(12000).Within(11), "dt 0.011");
            Assert.That((bool)Json(b, "placement.json")["conditionCompleted"], Is.True);
            var ra = Csv(a, "stopdistance.csv");
            var rb = Csv(b, "stopdistance.csv");
            Assert.That(rb.Count, Is.EqualTo(ra.Count), "멈춤 거리 시행 수");
            Assert.That(rb.Select(r => r[2] + r[7]), Is.EqualTo(ra.Select(r => r[2] + r[7])), "방향·timed_out 순서");
            for (int i = 0; i < ra.Count; i++)
                if (ra[i][7] == "0") Assert.That(D(rb[i][5]), Is.EqualTo(D(ra[i][5])).Within(0.25 * 0.02 + 1e-6), "trial " + ra[i][0]);
        }

        // ── 시작 자리 출처·물체 반지름(CP7 F3·F7) ───────────────────────
        [Test]
        public void Layout_in_spec_is_ignored_with_a_warning_and_flag()
        {
            var cfg = ShortConfig("view");
            Assert.That(PlacementManifest.LayoutIgnoredWarning(null, null, cfg), Is.Null, "layout 값이 없으면 경고 없음");
            string w = PlacementManifest.LayoutIgnoredWarning(2.0, null, cfg);
            Assert.That(w, Does.StartWith("layout_ignored"));
            Assert.That(PlacementManifest.LayoutIgnoredWarning(null, -0.3, cfg), Does.StartWith("layout_ignored"));
            string dir = Run(cfg, setup: (info, warnings) =>
            {
                info.LayoutIgnored = true;
                info.ObjectBoundingRadiusM = 0.31234;
                warnings.Add(w);
            });
            var m = Json(dir, "manifest.json");
            Assert.That((bool)m["flags"]["layoutIgnored"], Is.True);
            Assert.That((string)m["space"]["startPlacementSource"], Is.EqualTo("experiment_config"));
            Assert.That((double)m["object"]["boundingRadiusM"], Is.EqualTo(0.3123));
            var warn = Csv(dir, "events.csv").Where(c => c[1] == "warning").Select(c => string.Join(",", c.Skip(2)).Trim('"')).ToList();
            Assert.That(warn.Count(x => x.StartsWith("layout_ignored")), Is.EqualTo(1), "events.csv warning 한 줄");
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
