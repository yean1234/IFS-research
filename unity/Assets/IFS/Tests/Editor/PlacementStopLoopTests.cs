// EditMode 테스트: 2026-11-26 교수님 피드백 2·3(G60-2 멈춤 거리 반복 멈춤, G60-3 눈높이 정규화).
//   · 기본값(stopMode single, eyeHeightMode none)은 G60 전과 같다 — 바이트 대조는 PlacementEnvironmentTests의 golden이 맡고,
//     여기서는 새 설정 키·파일이 기본값에서 생기지 않는지 본다.
//   · loop 규칙: 토글(다시 움직이면 같은 방향), 확정은 멈춘 상태에서만, 디바운스, 시간 상한(확정값 빈칸), 무입력, 끝점 반사,
//     지나간 횟수, 중단, 시드 결정성(직접 구현 xorshift64* — 값을 고정해 Mono와 dotnet이 같은지 본다).
//   · 눈높이: 보정 판정(Floor·SD·pitch·범위·표본 수), pitch 부호, 20 Hz 표본, 높이 옮김(E = 기준이면 예전과 같은 자리), manifest·events.
// UnityEngine 없이 돈다(dotnet compile-check에서도 실행). 기록은 임시 폴더에 쓰고 지운다. 입력은 모두 합성이다.
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
    public class PlacementStopLoopTests
    {
        string _tmp;
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-loop-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        // 계약 문자열(상수를 바꾸면 이 테스트가 깨져야 한다)
        const string RoundsCsv = "round,practice,start_dir,start_distance_m,speed_mps,final_distance_m,first_stop_distance_m,last_stop_distance_m,n_stops,n_resumes," +
                                 "final_motion_dir,passes_before_confirm,stop_spread_m,at_bound,end_reason,duration_ms,eye_object_distance_m";
        const string AdjustCsv = "round,practice,time_ms,t_ms,event,distance_m,motion_dir,rt_ms";

        static PlacementConfig Loop(string condition = "place", string mode = PlacementConfig.ModeStatic)
        {
            var c = PlacementTests.ShortConfig(condition, mode);
            c.stopMode = PlacementConfig.StopModeLoop;
            return c;
        }

        /// <summary>출발 2.0 m 고정, 본 1라운드(연습 없음), 상한 roundSeconds.</summary>
        static PlacementConfig OneRound(double roundSeconds = 30, string first = PlacementConfig.DirectionApproach)
        {
            var c = Loop();
            c.stopLoopStartMinM = c.stopLoopStartMaxM = 2.0;
            c.stopLoopRounds = 1;
            c.stopLoopPracticeRounds = 0;
            c.stopLoopRoundSeconds = roundSeconds;
            c.stopFirstDirection = first;
            return c;
        }

        /// <summary>세션 한 바퀴. loopInput이 있으면 반복 멈춤 라운드 동안 참여자 입력을 그것으로 바꾼다(인자: 세션, 라운드 시작부터 지난 초).</summary>
        string Run(PlacementConfig cfg, int participant = 1, PlacementAutoScript script = null, PlacementTaskText text = null,
            Func<PlacementSession, double, PlacementInputFrame> loopInput = null, EyeHeightInfo eye = null,
            Func<PlacementSession, bool> abortWhen = null, Action<PlacementSession> eachFrame = null, double dt = 0.02)
        {
            text = text ?? PlacementTests.LoadText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = participant, SessionId = "SYN-LOOP", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 26, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeysFor(cfg).ToArray(), EyeHeight = eye,
            };
            script = script ?? new PlacementAutoScript();
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records", Guid.NewGuid().ToString("N")), null, null))
            {
                for (int i = 0; i < 400000 && !s.Finished; i++)
                {
                    if (abortWhen != null && abortWhen(s)) { s.Abort(); break; }
                    var f = script.Participant(s, dt);
                    if (loopInput != null && s.Phase == PlacementPhase.StopDistance && s.StopRoundActive)
                        f = loopInput(s, s.StopLoopRoundElapsed);
                    s.Tick(dt, f, PlacementAutoScript.ScriptedHead(s.Now));
                    script.Experimenter(s);
                    eachFrame?.Invoke(s);
                }
                Assert.That(s.Finished, Is.True, "끝까지 돌았다");
                return s.RecordDirectory;
            }
        }

        /// <summary>정한 시각(라운드 시작부터 초)마다 한 프레임만 누르는 입력. kind: "t" = 트리거(토글), "c" = 확정.</summary>
        static Func<PlacementSession, double, PlacementInputFrame> Presses(params (double at, string kind)[] presses)
        {
            var done = new HashSet<int>();
            return (s, elapsed) =>
            {
                var f = new PlacementInputFrame();
                for (int i = 0; i < presses.Length; i++)
                {
                    if (done.Contains(i) || elapsed < presses[i].at - 1e-9) continue;
                    done.Add(i);
                    if (presses[i].kind == "t") f.StopDown = f.StopHeld = true;
                    else f.ConfirmDown = true;
                    break;   // 한 프레임에 하나
                }
                return f;
            };
        }

        static JObject Json(string dir, string file) => OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, file)));

        static List<Dictionary<string, string>> Table(string dir, string file)
        {
            var lines = File.ReadAllLines(Path.Combine(dir, file));
            var head = lines[0].Split(',');
            return lines.Skip(1).Select(l => l.Split(',')).Select(c => head.Select((h, i) => (h, v: i < c.Length ? c[i] : "")).ToDictionary(x => x.h, x => x.v)).ToList();
        }

        static double D(string s) => double.Parse(s, Inv);

        // ── 기본값(G60 전과 같음) ───────────────────────────────────────
        [Test]
        public void Defaults_are_single_and_none_and_add_no_config_keys_or_files()
        {
            var c = new PlacementConfig();
            Assert.That(c.stopMode, Is.EqualTo("single"));
            Assert.That(c.eyeHeightMode, Is.EqualTo("none"));
            Assert.That((c.stopLoopMinM, c.stopLoopMaxM, c.stopLoopStartMinM, c.stopLoopStartMaxM), Is.EqualTo((0.4, 3.6, 1.0, 3.0)));
            Assert.That((c.stopLoopRounds, c.stopLoopPracticeRounds, c.stopLoopRoundSeconds, c.stopLoopToggleDebounceMs, c.stopLoopHideRings),
                Is.EqualTo((1, 1, 75.0, 250.0, true)), "본 라운드 1(2026-11-28 G83, 이전 4)");
            Assert.That(c.stopLoopPracticeRoundSeconds, Is.EqualTo(30.0), "연습 라운드는 30초 1번(2026-11-28 연구 책임자 요청), 본 라운드 75초는 그대로");
            Assert.That((c.eyeHeightReferenceM, c.eyeHeightMinM, c.eyeHeightMaxM, c.eyeCalibSeconds, c.eyeCalibMaxSdM, c.eyeCalibMaxPitchDeg),
                Is.EqualTo((1.6, 1.30, 1.95, 1.0, 0.02, 15.0)));
            var j = c.ToJson();
            foreach (var k in new[] { "stopMode", "stopLoopMinM", "stopLoopHideRings", "eyeHeightMode", "eyeHeightReferenceM", "eyeCalibMaxSdM" })
                Assert.That(j.ContainsKey(k), Is.False, k + ": 기본값이면 config에 넣지 않는다(기록 바이트 동일)");
            Assert.That(c.EyeOffsetFor(1.80), Is.EqualTo(0), "none이면 높이를 옮기지 않는다");

            string dir = Run(PlacementTests.ShortConfig("place"));
            foreach (var f in PlacementRecordWriter.LoopFiles) Assert.That(File.Exists(Path.Combine(dir, f)), Is.False, f + ": single에는 없다");
            var m = Json(dir, "manifest.json");
            Assert.That(((JObject)m["stopDistance"]).ContainsKey("mode"), Is.False);
            Assert.That(m.ContainsKey("eyeHeight"), Is.False);
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Not.Contain("stop_distance_loop").And.Not.Contain("stop_loop_hint"),
                "single이면 반복 멈춤 문구는 draftKeys에 들어가지 않는다");
            Assert.That(File.ReadAllLines(Path.Combine(dir, "stopdistance.csv")).Length, Is.GreaterThan(1), "single은 예전처럼 시행 행");
        }

        [Test]
        public void Loop_and_eye_settings_are_validated()
        {
            Assert.That(Loop().Validate(), Is.Empty);
            Assert.That(new PlacementConfig { stopMode = "twice" }.Validate().Any(e => e.StartsWith("stopMode")), Is.True);
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopMaxM = 4.5 }.Validate().Any(e => e.StartsWith("stopLoopMaxM")), Is.True, "바닥 밖");
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopStartMinM = 0.3 }.Validate().Any(e => e.StartsWith("stopLoopStartMinM")), Is.True, "출발은 경로 안");
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopStartMaxM = 3.6 }.Validate().Any(e => e.StartsWith("stopLoopStartMinM")), Is.True);
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopRounds = 0 }.Validate().Any(e => e.StartsWith("stopLoopRounds")), Is.True);
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopRoundSeconds = 0 }.Validate().Any(e => e.StartsWith("stopLoopRoundSeconds")), Is.True);
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopPracticeRoundSeconds = 0 }.Validate().Any(e => e.StartsWith("stopLoopPracticeRoundSeconds")), Is.True);
            Assert.That(new PlacementConfig { stopMode = "loop", stopLoopPracticeRounds = 0, stopLoopPracticeRoundSeconds = 0 }.Validate(), Is.Empty, "연습이 없으면 연습 상한은 보지 않는다");
            Assert.That(new PlacementConfig { stopMode = "single", stopLoopRounds = 0 }.Validate(), Is.Empty, "single이면 loop 키는 보지 않는다");
            Assert.That(new PlacementConfig { eyeHeightMode = "absolute" }.Validate().Any(e => e.StartsWith("eyeHeightMode")), Is.True);
            Assert.That(new PlacementConfig { eyeHeightMode = "relative" }.Validate(), Is.Empty);
            var low = new PlacementConfig { eyeHeightMode = "relative", startHeightM = 0.2 };
            Assert.That(low.Validate().Any(e => e.StartsWith("startHeightM")), Is.True, "눈높이 1.30이면 0.2 − 0.3 < minHeightM");
            var json = new PlacementConfig { stopMode = "loop", eyeHeightMode = "relative" }.ToJson();
            Assert.That(json.Properties().Select(p => p.Name).SkipWhile(n => n != "stopMode"), Is.EqualTo(new[]
            {
                "stopMode", "stopLoopMinM", "stopLoopMaxM", "stopLoopStartMinM", "stopLoopStartMaxM", "stopLoopRounds", "stopLoopPracticeRounds",
                "stopLoopRoundSeconds", "stopLoopPracticeRoundSeconds", "stopLoopToggleDebounceMs", "stopLoopHideRings",
                "eyeHeightMode", "eyeHeightReferenceM", "eyeHeightMinM", "eyeHeightMaxM", "eyeCalibSeconds", "eyeCalibMaxSdM", "eyeCalibMaxPitchDeg",
            }), "켰을 때만 config 맨 끝에");
        }

        // ── 라운드 계획(시드 결정성) ─────────────────────────────────────
        [Test]
        public void Round_plan_is_seeded_by_participant_number_and_alternates_direction()
        {
            // 직접 구현한 xorshift64*(splitmix64 시드) — 값을 고정해 둔다. Mono(Unity)와 dotnet이 같은 값을 내야 한다.
            // 같은 값을 Python(chatbot/ifs_chatbot/eval/sim_placement.py stop_loop_plan)도 낸다(test_placement_eval.py).
            var rng = new XorShift64Star(1);
            Assert.That(new[] { rng.NextULong(), rng.NextULong(), rng.NextULong() },
                Is.EqualTo(new[] { 5424204624148110235UL, 15555979849632202484UL, 6851360858507811590UL }));
            var cfg = Loop();
            cfg.stopLoopRounds = 4;   // 예전(G60-2) 4라운드 계획 — 수열·번갈이 규칙을 그대로 고정해 둔다(기본 1라운드는 아래 시험)
            var p1 = StopLoopSchedule.Build(cfg, 1);
            Assert.That(p1.Select(p => p.StartM), Is.EqualTo(new[] { 1.588, 2.687, 1.743, 1.462, 2.718 }));
            Assert.That(p1.Select(p => p.StartDirection), Is.EqualTo(new[] { "approach", "recede", "approach", "recede", "approach" }), "홀수 번호는 approach 먼저");
            Assert.That(p1.Select(p => p.Practice), Is.EqualTo(new[] { true, false, false, false, false }), "연습 1 + 본 4");
            Assert.That(p1.Select(p => p.Round), Is.EqualTo(new[] { 1, 2, 3, 4, 5 }));
            var p2 = StopLoopSchedule.Build(cfg, 2);
            Assert.That(p2.Select(p => p.StartM), Is.EqualTo(new[] { 2.082, 1.169, 2.798, 1.197, 1.743 }));
            Assert.That(p2[0].StartDirection, Is.EqualTo("recede"), "짝수 번호는 recede 먼저");
            Assert.That(StopLoopSchedule.Build(cfg, 7).Select(p => p.StartM), Is.EqualTo(new[] { 1.163, 1.517, 1.708, 2.107, 2.304 }));
            Assert.That(StopLoopSchedule.Build(cfg, 1).Select(p => p.StartM), Is.EqualTo(p1.Select(p => p.StartM)), "같은 번호 = 같은 계획");
            foreach (int n in Enumerable.Range(1, 200))
                foreach (var p in StopLoopSchedule.Build(cfg, n))
                {
                    Assert.That(p.StartM, Is.InRange(1.0, 3.0));
                    Assert.That(Math.Round(p.StartM, 3), Is.EqualTo(p.StartM), "1 mm 단위");
                }
        }

        [Test]
        public void Default_plan_is_one_practice_then_one_main_round_in_the_opposite_direction()
        {
            // 2026-11-28 G83: 연습 1 + 본 1. 규칙은 그대로라 본 라운드 = 첫 방향의 반대, 출발 거리 = 수열의 두 번째 값(예전 계획의 앞 두 라운드)
            var cfg = Loop();
            var old = Loop();
            old.stopLoopRounds = 4;
            foreach (int n in Enumerable.Range(1, 40))
            {
                var plan = StopLoopSchedule.Build(cfg, n);
                Assert.That(plan.Select(p => (p.Round, p.Practice)), Is.EqualTo(new[] { (1, true), (2, false) }), "연습 1 + 본 1");
                Assert.That(plan.Select(p => p.StartM), Is.EqualTo(StopLoopSchedule.Build(old, n).Take(2).Select(p => p.StartM)), "예전 계획의 앞 두 라운드와 같은 출발 거리");
                Assert.That(plan[1].StartDirection, Is.EqualTo(n % 2 == 1 ? "recede" : "approach"), "홀수 번호: 연습 approach·본 recede, 짝수 번호: 반대");
                Assert.That(plan[1].StartDirection, Is.Not.EqualTo(plan[0].StartDirection));
            }
            Assert.That(StopLoopSchedule.Build(cfg, 1).Select(p => p.StartM), Is.EqualTo(new[] { 1.588, 2.687 }));
            Assert.That(StopLoopSchedule.Build(cfg, 2).Select(p => p.StartM), Is.EqualTo(new[] { 2.082, 1.169 }));
            var fixedFirst = Loop();
            fixedFirst.stopFirstDirection = PlacementConfig.DirectionApproach;
            Assert.That(StopLoopSchedule.Build(fixedFirst, 2).Select(p => p.StartDirection), Is.EqualTo(new[] { "approach", "recede" }),
                "첫 방향을 approach로 정하면 본 라운드는 모든 참여자가 recede 출발");
        }

        [Test]
        public void Default_loop_session_records_one_practice_and_one_main_round()
        {
            var cfg = Loop();
            string dir = Run(cfg);
            var rounds = Table(dir, PlacementRecordWriter.StopRoundsFile);
            Assert.That(rounds.Select(r => (r["round"], r["practice"], r["start_dir"])), Is.EqualTo(new[] { ("1", "1", "approach"), ("2", "0", "recede") }));
            Assert.That(rounds.Select(r => D(r["start_distance_m"])), Is.EqualTo(new[] { 1.588, 2.687 }), "계획 그대로");
            Assert.That(rounds[1]["end_reason"], Is.EqualTo("confirmed"));
            var m = Json(dir, "manifest.json");
            var loop = m["stopDistance"]["loop"];
            Assert.That(((int)loop["rounds"], (int)loop["practiceRounds"], loop["plan"].Count()), Is.EqualTo((1, 1, 2)), "기록에 라운드 수 설정이 남는다");
            Assert.That(((int)m["config"]["stopLoopRounds"], (int)m["config"]["stopLoopPracticeRounds"]), Is.EqualTo((1, 1)));
            var events = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(',')[1]).ToList();
            Assert.That(events.Count(e => e == "stop_round_start"), Is.EqualTo(2));
        }

        [Test]
        public void After_the_only_main_round_no_gap_instruction_or_wait_follows()
        {
            // 2026-11-28 G83: 마지막 라운드 뒤에는 다음 라운드가 없다 — 시간 초과면 지시문(라운드 사이 문구)도 기다림도 없이 다음 단계,
            // 확정했으면 확정 알림만 stopItiSeconds 동안(G78-d)
            foreach (bool confirm in new[] { false, true })
            {
                var cfg = OneRound(4);
                cfg.stopItiSeconds = 2.0;
                var after = new List<string>();
                double endedAt = double.NaN, leftAt = double.NaN;   // endedAt = 라운드가 돌던 마지막 프레임
                Run(cfg, loopInput: confirm ? Presses((1.0, "t"), (2.0, "c")) : (s, e) => new PlacementInputFrame(), eachFrame: s =>
                {
                    if (s.Phase == PlacementPhase.StopDistance)
                    {
                        if (s.StopRoundActive) endedAt = s.Now;
                        else if (!double.IsNaN(endedAt) && (after.Count == 0 || after.Last() != s.ParticipantTextKey)) after.Add(s.ParticipantTextKey);
                    }
                    else if (!double.IsNaN(endedAt) && double.IsNaN(leftAt)) leftAt = s.Now;
                });
                if (confirm)
                {
                    Assert.That(after, Is.EqualTo(new[] { "confirm_done" }), "확정 뒤: 확정 알림만");
                    Assert.That(leftAt - endedAt, Is.EqualTo(2.0).Within(0.05), "확정 알림은 stopItiSeconds 동안");
                }
                else
                {
                    Assert.That(after, Is.Empty, "시간 초과 뒤 라운드 사이 지시문이 한 프레임도 보이지 않는다: " + string.Join(", ", after));
                    Assert.That(leftAt - endedAt, Is.LessThan(0.05), "기다리지 않고 다음 단계");
                }
            }
        }

        // ── 한 바퀴(자동 시행) ──────────────────────────────────────────
        [Test]
        public void Auto_loop_session_writes_rounds_adjust_rows_and_manifest()
        {
            var cfg = Loop();
            cfg.stopLoopRounds = 4;   // 예전(G60-2) 연습 1 + 본 4 — 여러 라운드 경로도 그대로 돈다
            string dir = Run(cfg);
            Assert.That(File.ReadLines(Path.Combine(dir, PlacementRecordWriter.StopRoundsFile)).First(), Is.EqualTo(RoundsCsv));
            Assert.That(File.ReadLines(Path.Combine(dir, PlacementRecordWriter.StopAdjustFile)).First(), Is.EqualTo(AdjustCsv));
            Assert.That(PlacementRecordWriter.StopRoundsHeader, Is.EqualTo(RoundsCsv));
            Assert.That(PlacementRecordWriter.StopAdjustHeader, Is.EqualTo(AdjustCsv));
            Assert.That(File.ReadAllLines(Path.Combine(dir, "stopdistance.csv")), Has.Length.EqualTo(1), "loop면 stopdistance.csv는 헤더만");
            foreach (var f in PlacementRecordWriter.LoopFiles.Concat(PlacementRecordWriter.AllFiles))
            {
                var bytes = File.ReadAllBytes(Path.Combine(dir, f));
                Assert.That(bytes.Length >= 3 && bytes[0] == 0xEF && bytes[1] == 0xBB, Is.False, f + " BOM 없음");
                Assert.That(bytes.Contains((byte)'\r'), Is.False, f + " 줄바꿈 \\n");
            }

            var rounds = Table(dir, PlacementRecordWriter.StopRoundsFile);
            Assert.That(rounds.Select(r => r["end_reason"]), Is.EqualTo(new[] { "confirmed", "confirmed", "confirmed", "timeout_moving", "confirmed" }));
            Assert.That(rounds.Select(r => r["practice"]), Is.EqualTo(new[] { "1", "0", "0", "0", "0" }));
            Assert.That(rounds.Select(r => D(r["start_distance_m"])), Is.EqualTo(new[] { 1.588, 2.687, 1.743, 1.462, 2.718 }), "계획 그대로");
            var r2 = rounds[1];
            Assert.That((r2["n_stops"], r2["n_resumes"]), Is.EqualTo(("2", "1")), "멈춤 → 다시 움직임 → 멈춤 → 확정");
            Assert.That(D(r2["first_stop_distance_m"]), Is.EqualTo(1.80).Within(0.006));
            Assert.That(D(r2["final_distance_m"]), Is.EqualTo(1.60).Within(0.006));
            Assert.That(D(r2["last_stop_distance_m"]), Is.EqualTo(D(r2["final_distance_m"])), "확정값 = 마지막 멈춤 자리(멈춘 상태에서 확정)");
            Assert.That(D(r2["stop_spread_m"]), Is.EqualTo(0.20).Within(0.012));
            Assert.That(r2["at_bound"], Is.EqualTo("0"));
            Assert.That(D(r2["eye_object_distance_m"]), Is.GreaterThan(0.5), "확정 순간 머리–물체 3차원 거리");
            var r4 = rounds[3];
            Assert.That((r4["final_distance_m"], r4["first_stop_distance_m"], r4["last_stop_distance_m"], r4["n_stops"], r4["final_motion_dir"],
                r4["passes_before_confirm"], r4["at_bound"], r4["eye_object_distance_m"]), Is.EqualTo(("", "", "", "0", "", "", "", "")),
                "한 번도 안 누름: 확정값·멈춤값 빈칸(원칙 2)");
            Assert.That(long.Parse(r4["duration_ms"], Inv), Is.EqualTo(75000).Within(30), "상한 75 s");
            Assert.That(D(rounds[4]["final_distance_m"]), Is.EqualTo(1.45).Within(0.006));
            Assert.That(rounds[4]["n_stops"], Is.EqualTo("3"));

            var adj = Table(dir, PlacementRecordWriter.StopAdjustFile);
            Assert.That(adj.Where(a => a["round"] == "2").Select(a => a["event"]).Where(e => e != "turn"),
                Is.EqualTo(new[] { "start", "confirm_ignored", "stop", "resume", "stop", "confirm" }), "움직이는 중 확정은 무시하고 사건으로만 남김");
            Assert.That(adj.Where(a => a["round"] == "4").Select(a => a["event"]).Last(), Is.EqualTo("timeout"));
            Assert.That(adj.Select(a => a["event"]).Distinct().All(e => new[] { "start", "stop", "resume", "turn", "confirm", "confirm_ignored", "toggle_ignored", "timeout", "abort" }.Contains(e)), Is.True);
            Assert.That(adj.All(a => D(a["distance_m"]) >= 0.4 - 1e-9 && D(a["distance_m"]) <= 3.6 + 1e-9), Is.True, "경로 안");

            var m = Json(dir, "manifest.json");
            var sd = (JObject)m["stopDistance"];
            Assert.That(sd.Properties().Select(p => p.Name), Is.EqualTo(new[] { "speedMps", "approachStartM", "recedeStartM", "trialsPerDirection", "practiceTrials", "minM", "maxM", "mode", "loop" }),
                "기존 키는 그대로, mode·loop를 뒤에");
            Assert.That((string)sd["mode"], Is.EqualTo("loop"));
            Assert.That(sd["loop"]["plan"].Count(), Is.EqualTo(5));
            Assert.That((double)sd["loop"]["plan"][1]["startDistanceM"], Is.EqualTo(2.687));
            Assert.That((bool)sd["loop"]["hideRings"], Is.True);
            Assert.That((string)m["config"]["stopMode"], Is.EqualTo("loop"));
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Contain("stop_distance_loop").And.Contain("stop_loop_hint"), "loop면 보이는 문구라 draftKeys에");
            var events = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(',')[1]).ToList();
            Assert.That(events.Count(e => e == "stop_round_start"), Is.EqualTo(5));
            Assert.That(events.Count(e => e == "stop_round_end"), Is.EqualTo(5));
            Assert.That(events, Does.Not.Contain("stop_trial_start"), "single 시행 사건은 없다");
            var states = File.ReadAllLines(Path.Combine(dir, "objpose.csv")).Skip(1).Select(l => l.Split(',')).Where(c => c[1] == "stop_distance").Select(c => c[8]).Distinct().ToList();
            Assert.That(states, Is.EquivalentTo(new[] { "stop", "stop_paused" }));
        }

        [Test]
        public void Participant_text_shows_the_hint_only_while_stopped()
        {
            var keys = new HashSet<string>();
            Run(OneRound(), loopInput: Presses((1.0, "t"), (2.0, "c")), eachFrame: s =>
            {
                if (s.Phase == PlacementPhase.StopDistance) keys.Add(s.ParticipantTextKey + (s.StopLoopMoving ? "|moving" : s.StopRoundActive ? "|stopped" : "|between"));
            });
            // 2026-11-28: 멈춘 동안 조작 안내 끝에 확인 버튼 안내(오른손 A), 확정한 뒤 라운드 사이에는 확정 알림
            Assert.That(keys, Is.SupersetOf(new[] { "stop_distance_loop|moving", "stop_distance_loop+stop_loop_hint+confirm_button_right|stopped",
                                                    "stop_distance_loop|between", "confirm_done|between" }));
            Assert.That(keys.Any(k => k.StartsWith("stop_distance|")), Is.False, "single 문구는 보이지 않는다");
        }

        // ── loop 규칙 ───────────────────────────────────────────────────
        [Test]
        public void Toggle_stops_and_resumes_in_the_same_direction_with_debounce()
        {
            string dir = Run(OneRound(), loopInput: Presses((1.0, "t"), (1.1, "t"), (2.0, "t"), (3.0, "t"), (3.5, "c")));
            var adj = Table(dir, PlacementRecordWriter.StopAdjustFile);
            Assert.That(adj.Select(a => a["event"]), Is.EqualTo(new[] { "start", "stop", "toggle_ignored", "resume", "stop", "confirm" }),
                "250 ms 안의 다시 누름은 버린다");
            Assert.That(adj.Where(a => a["event"] == "stop" || a["event"] == "resume").Select(a => a["motion_dir"]).Distinct(), Is.EqualTo(new[] { "approach" }),
                "다시 움직이면 멈추기 전 방향 그대로");
            var stop1 = adj[1];
            var stop2 = adj[4];
            Assert.That(D(stop1["distance_m"]), Is.EqualTo(2.0 - 0.25 * 1.0).Within(0.011));
            Assert.That(D(stop2["distance_m"]), Is.EqualTo(D(stop1["distance_m"]) - 0.25 * 1.0).Within(0.011), "멈춘 동안은 움직이지 않는다");
            Assert.That(long.Parse(adj[3]["rt_ms"], Inv), Is.EqualTo(1000).Within(25), "resume rt = 멈춘 뒤 지난 시간");
            Assert.That(long.Parse(stop2["rt_ms"], Inv), Is.EqualTo(1000).Within(25), "stop rt = 직전 재개부터");
            Assert.That(long.Parse(adj[5]["rt_ms"], Inv), Is.EqualTo(500).Within(25), "confirm rt = 멈춘 뒤 지난 시간");
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That((r["end_reason"], r["n_stops"], r["n_resumes"], r["final_motion_dir"], r["passes_before_confirm"]), Is.EqualTo(("confirmed", "2", "1", "approach", "0")));
            Assert.That(D(r["final_distance_m"]), Is.EqualTo(D(stop2["distance_m"])));
            Assert.That(D(r["first_stop_distance_m"]), Is.EqualTo(D(stop1["distance_m"])));
        }

        [Test]
        public void Xr_trigger_toggles_and_a_button_confirms()
        {
            // XR 컨트롤러 원자료(가짜): 트리거를 0.15 s씩 눌렀다 뗌(1.0, 2.0, 3.0 s), A는 0.5 s(움직이는 중 — 무시)와 3.5 s(멈춘 뒤 — 확정)에 0.15 s.
            var logic = new XrPlacementInputLogic();
            bool In(double e, double at) => e >= at - 1e-9 && e < at + 0.15;
            string dir = Run(OneRound(), loopInput: (s, e) =>
            {
                var smp = new XrControllerSample { Valid = true, HasPose = true, RayDirection = new PVec3(0, 0, 1), Trigger = double.NaN };
                smp.TriggerButton = In(e, 1.0) || In(e, 2.0) || In(e, 3.0);
                smp.PrimaryButton = In(e, 0.5) || In(e, 3.5);
                return logic.Step(smp, true);
            });
            var adj = Table(dir, PlacementRecordWriter.StopAdjustFile);
            Assert.That(adj.Select(a => a["event"]), Is.EqualTo(new[] { "start", "confirm_ignored", "stop", "resume", "stop", "confirm" }),
                "누르고 있는 동안 한 번만 센다(내려가는 순간)");
            Assert.That(Table(dir, PlacementRecordWriter.StopRoundsFile).Single()["end_reason"], Is.EqualTo("confirmed"));
        }

        [Test]
        public void Confirm_is_taken_only_while_stopped()
        {
            string dir = Run(OneRound(8), loopInput: Presses((0.5, "c"), (1.0, "c")));
            var adj = Table(dir, PlacementRecordWriter.StopAdjustFile);
            Assert.That(adj.Where(a => a["event"] == "confirm_ignored").Count(), Is.EqualTo(2), "움직이는 중의 확정은 둘 다 무시");
            Assert.That(adj.Any(a => a["event"] == "confirm"), Is.False);
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That((r["end_reason"], r["final_distance_m"]), Is.EqualTo(("timeout_moving", "")), "확정이 받아들여지지 않아 상한까지 감");
        }

        [Test]
        public void Practice_round_has_its_own_30_second_limit_and_main_rounds_keep_75()
        {
            // 2026-11-28 연구 책임자 요청: 연습은 30초 안 1번. 본 라운드 상한(75 s)·수는 그대로
            var cfg = Loop();
            cfg.stopLoopStartMinM = cfg.stopLoopStartMaxM = 2.0;
            cfg.stopLoopRounds = 1;
            var left = new List<double>();
            string dir = Run(cfg, loopInput: (s, e) => new PlacementInputFrame(), eachFrame: s =>
            {
                if (s.Phase == PlacementPhase.StopDistance && s.StopRoundActive && s.CurrentStopRound.Practice && s.StopLoopRoundElapsed < 0.05) left.Add(s.StopLoopSecondsLeft);
            });
            var rounds = Table(dir, PlacementRecordWriter.StopRoundsFile);
            Assert.That(rounds.Select(r => r["practice"]), Is.EqualTo(new[] { "1", "0" }), "연습 1 + 본 1");
            Assert.That(rounds.Select(r => r["end_reason"]), Is.EqualTo(new[] { "timeout_moving", "timeout_moving" }));
            Assert.That(long.Parse(rounds[0]["duration_ms"], Inv), Is.EqualTo(30000).Within(30), "연습 라운드 상한 30 s");
            Assert.That(long.Parse(rounds[1]["duration_ms"], Inv), Is.EqualTo(75000).Within(30), "본 라운드 상한 75 s 그대로");
            Assert.That(left.First(), Is.EqualTo(30.0).Within(0.05), "실험자 화면의 남은 시간도 연습 상한 기준");
            var loop = Json(dir, "manifest.json")["stopDistance"]["loop"];
            Assert.That(((double)loop["roundSeconds"], (double)loop["practiceRoundSeconds"], (int)loop["practiceRounds"]), Is.EqualTo((75.0, 30.0, 1)));
        }

        // ── 확인 버튼 안내·확정 알림·본 측정 시작 안내(연구 책임자 결정 2026-11-28) ─────────
        /// <summary>라운드마다 (멈춤 시각, 확정 시각) — 음수면 누르지 않는다. 한 프레임만 누른다.</summary>
        static Func<PlacementSession, double, PlacementInputFrame> PerRound(Dictionary<int, (double stop, double confirm)> plan, double dt = 0.02) => (s, e) =>
        {
            var f = new PlacementInputFrame();
            if (!plan.TryGetValue(s.CurrentStopRound.Round, out var p)) return f;
            if (p.stop >= 0 && e >= p.stop - 1e-9 && e < p.stop + dt - 1e-9) f.StopDown = f.StopHeld = true;
            else if (p.confirm >= 0 && e >= p.confirm - 1e-9 && e < p.confirm + dt - 1e-9) f.ConfirmDown = true;
            return f;
        };

        /// <summary>멈춤 거리 단계에서 라운드 사이에 보인 안내 키(연달아 같은 것은 하나로)와 라운드 사이 간격(초).</summary>
        static (List<string> gapKeys, List<double> gaps) Observe(PlacementSession s, List<string> keys, List<double> gaps, ref double endedAt, ref bool wasActive)
        {
            if (s.Phase != PlacementPhase.StopDistance) return (keys, gaps);
            if (!s.StopRoundActive && (keys.Count == 0 || keys[keys.Count - 1] != s.ParticipantTextKey)) keys.Add(s.ParticipantTextKey);
            if (wasActive && !s.StopRoundActive) endedAt = s.Now;
            if (!wasActive && s.StopRoundActive && !double.IsNaN(endedAt)) gaps.Add(s.Now - endedAt);
            wasActive = s.StopRoundActive;
            return (keys, gaps);
        }

        [Test]
        public void Confirm_notice_follows_only_confirmed_rounds_and_main_start_shows_once_within_the_gap()
        {
            var cfg = Loop();
            cfg.stopLoopStartMinM = cfg.stopLoopStartMaxM = 2.0;
            cfg.stopLoopRounds = 2;
            cfg.stopItiSeconds = 2.0;
            var keys = new List<string>();
            var gaps = new List<double>();
            double endedAt = double.NaN;
            bool wasActive = false;
            bool hiddenDuringNotice = false;
            cfg.hidePanelInDistancePhases = true;
            cfg.hidePanelReadSeconds = 1;
            string dir = Run(cfg, loopInput: PerRound(new Dictionary<int, (double, double)> { [1] = (1.0, 2.0), [2] = (-1, -1), [3] = (1.0, 2.0) }),
                eachFrame: s =>
                {
                    Observe(s, keys, gaps, ref endedAt, ref wasActive);
                    if (s.Phase == PlacementPhase.StopDistance && !s.StopRoundActive && s.ParticipantTextKey != null
                        && (s.ParticipantTextKey.StartsWith("confirm_done") || s.ParticipantTextKey == "stop_main_start") && s.PanelHidden) hiddenDuringNotice = true;
                });
            var rounds = Table(dir, PlacementRecordWriter.StopRoundsFile);
            Assert.That(rounds.Select(r => r["end_reason"]), Is.EqualTo(new[] { "confirmed", "timeout_moving", "confirmed" }));
            Assert.That(long.Parse(rounds[0]["duration_ms"], Inv), Is.EqualTo(2000).Within(30), "연습 라운드도 상한 전에 확정하면 바로 끝남");
            Assert.That(long.Parse(rounds[2]["duration_ms"], Inv), Is.EqualTo(2000).Within(30), "본 라운드: 75 s 전 확정이 라운드를 끝냄");
            Assert.That(keys.Skip(1), Is.EqualTo(new[]
            {
                "confirm_done+stop_main_start",              // 연습 확정 뒤: 확정 알림 + 본 측정 시작 안내(한 번)
                "stop_distance_loop",                        // 시간 초과 뒤: 알림 없음, 지시문 그대로
                "confirm_done",                              // 본 라운드 확정 뒤: 확정 알림만
            }));
            Assert.That(keys.Count(k => k.Contains("stop_main_start")), Is.EqualTo(1));
            Assert.That(gaps, Has.Count.EqualTo(2));
            Assert.That(gaps.All(g => Math.Abs(g - 2.0) < 0.03), Is.True, "라운드 사이 간격은 stopItiSeconds 그대로: " + string.Join(", ", gaps));
            Assert.That(hiddenDuringNotice, Is.False, "판 숨기기를 켜도 알림이 보이는 동안은 판을 보인다");
        }

        [Test]
        public void Main_start_shows_alone_when_the_practice_round_times_out()
        {
            var cfg = Loop();
            cfg.stopLoopStartMinM = cfg.stopLoopStartMaxM = 2.0;
            cfg.stopLoopRounds = 1;
            cfg.stopLoopPracticeRoundSeconds = 3;
            var keys = new List<string>();
            var gaps = new List<double>();
            double endedAt = double.NaN;
            bool wasActive = false;
            Run(cfg, loopInput: PerRound(new Dictionary<int, (double, double)> { [2] = (1.0, 2.0) }), eachFrame: s => Observe(s, keys, gaps, ref endedAt, ref wasActive));
            Assert.That(keys.Skip(1), Is.EqualTo(new[] { "stop_main_start", "confirm_done" }), "확정하지 않은 연습 뒤에는 확정 알림 없이 본 측정 시작 안내만");
        }

        [Test]
        public void Confirm_button_line_follows_the_main_hand()
        {
            foreach (var (hand, key, letter) in new[] { ("right", "confirm_button_right", "A"), ("left", "confirm_button_left", "X") })
            {
                var seen = new HashSet<string>();
                var texts = new HashSet<string>();
                var cfg = Loop();
                cfg.xrHand = hand;
                cfg.placementAssist = true;   // 배치 연습에도 붙는지
                var script = new PlacementAutoScript { ConfirmAtSeconds = 3 };
                Run(cfg, script: script, eachFrame: s =>
                {
                    if (s.ParticipantTextKey == null) return;
                    seen.Add(s.Phase + "|" + s.ParticipantTextKey);
                    texts.Add(s.ParticipantText);
                });
                string other = hand == "right" ? "confirm_button_left" : "confirm_button_right";
                Assert.That(seen, Does.Contain("Practice|practice+" + key));
                Assert.That(seen, Does.Contain("Condition|condition_place+placement_range+" + key));
                Assert.That(seen, Does.Contain("StopDistance|stop_distance_loop+stop_loop_hint+" + key));
                Assert.That(seen.Any(k => k.Contains(other)), Is.False, hand + ": 다른 손 안내는 보이지 않는다");
                Assert.That(texts.Any(t => t.EndsWith(letter + " 버튼이에요.")), Is.True, hand + " → " + letter);
            }
            // 보기만(static)에는 확인 버튼이 없어 붙이지 않는다
            var view = new HashSet<string>();
            Run(Loop("view"), eachFrame: s => { if (s.Phase == PlacementPhase.Condition) view.Add(s.ParticipantTextKey); });
            Assert.That(view, Is.EqualTo(new[] { "condition_view" }));
        }

        [Test]
        public void Confirm_button_line_and_notice_appear_only_on_paths_that_take_a_confirm_input()
        {
            // CP16-2(보류, X42 미결): 버튼 안내·확정 알림은 확인 입력을 받는 경로에만 붙는다 — 보기만 조건 가운데 point_select는
            // 바닥 점을 가리켜 확정하므로 붙고, static·system_move는 확인을 받지 않아 붙지 않는다. 지금 동작을 고정한다(바꾸려면 결정 기록과 함께)
            var point = new List<string>();
            Run(Loop("view", PlacementConfig.ModePointSelect), script: new PlacementAutoScript { PointAtSeconds = 2 },
                eachFrame: s => { if (s.Phase == PlacementPhase.Condition && (point.Count == 0 || point.Last() != s.ParticipantTextKey)) point.Add(s.ParticipantTextKey); });
            Assert.That(point.First(), Is.EqualTo("condition_point_select+confirm_button_right"));
            Assert.That(point, Does.Contain("confirm_done"), "가리켜 확정한 뒤 확정 알림");
            foreach (var mode in new[] { PlacementConfig.ModeStatic, PlacementConfig.ModeSystemMove })
            {
                var keys = new HashSet<string>();
                Run(Loop("view", mode), eachFrame: s => { if (s.Phase == PlacementPhase.Condition) keys.Add(s.ParticipantTextKey); });
                Assert.That(keys.Any(k => k != null && (k.Contains("confirm_button") || k.StartsWith("confirm_done"))), Is.False, mode + ": 확인을 받지 않으면 붙이지 않는다");
            }
        }

        [Test]
        public void Placement_confirm_shows_the_notice_for_two_seconds_then_the_instruction_returns()
        {
            var cfg = Loop();
            cfg.hidePanelInDistancePhases = true;
            cfg.hidePanelReadSeconds = 1;
            var script = new PlacementAutoScript { ConfirmAtSeconds = 5 };
            var at = new List<(double t, string key, bool hidden)>();
            Run(cfg, script: script, eachFrame: s => { if (s.Phase == PlacementPhase.Condition) at.Add((s.SecondsInPhase, s.ParticipantTextKey, s.PanelHidden)); });
            string instr = "condition_place+confirm_button_right";
            Assert.That(at.First().key, Is.EqualTo(instr));
            var notice = at.Where(a => a.key == "confirm_done").ToList();
            Assert.That(notice, Is.Not.Empty);
            Assert.That(notice.First().t, Is.EqualTo(5.0).Within(0.05));
            Assert.That(notice.Last().t - notice.First().t, Is.EqualTo(PlacementSession.ConfirmNoticeSeconds).Within(0.05), "약 2초");
            Assert.That(at.Where(a => a.t > notice.Last().t).All(a => a.key == instr), Is.True, "알림 뒤 원래 안내로");
            Assert.That(notice.Any(a => a.hidden), Is.False, "판 숨기기를 켜도 알림 동안은 보인다");
            Assert.That(at.Where(a => a.t > notice.Last().t + 0.1).All(a => a.hidden), Is.True, "알림 뒤에는 다시 숨긴다");
        }

        [Test]
        public void New_confirm_phrases_are_draft_with_the_2026_11_28_source_and_same_in_both_files()
        {
            var def = PlacementTests.LoadText();
            var scaleA = PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementConfig.ExperimentTaskTextFile));
            foreach (var k in new[] { "confirm_button_right", "confirm_button_left", "confirm_done", "stop_main_start" })
                foreach (var t in new[] { def, scaleA })
                {
                    Assert.That(t.Status(k), Is.EqualTo("draft"), k);
                    Assert.That(t[k], Is.EqualTo(def[k]), k + ": 두 파일 같은 글");
                    foreach (var banned in new[] { "치료", "진단", "내담자", "잘 ", "좋", "m ", "미터", "거리" })
                        Assert.That(t[k], Does.Not.Contain(banned), k + ": 평가·치료·거리 표현 금지");
                }
            Assert.That(def["confirm_done"], Is.EqualTo("정했어요."));
            Assert.That(def.DraftKeysFor(false, false), Does.Not.Contain("stop_main_start"), "single이면 본 측정 시작 안내는 보이지 않는다");
            Assert.That(def.DraftKeysFor(false, true), Does.Contain("stop_main_start"));
        }

        [Test]
        public void Timeout_while_stopped_leaves_the_final_blank_and_keeps_the_last_stop()
        {
            string dir = Run(OneRound(5), loopInput: Presses((1.0, "t")));
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That(r["end_reason"], Is.EqualTo("timeout_stopped"));
            Assert.That(r["final_distance_m"], Is.Empty, "확정하지 않은 값을 시스템이 채우지 않는다(원칙 2)");
            Assert.That(D(r["last_stop_distance_m"]), Is.EqualTo(1.75).Within(0.011), "마지막 멈춤 거리는 따로 남긴다");
            Assert.That((r["n_stops"], r["passes_before_confirm"], r["at_bound"], r["eye_object_distance_m"]), Is.EqualTo(("1", "", "", "")));
            Assert.That(long.Parse(r["duration_ms"], Inv), Is.EqualTo(5000).Within(25));
            Assert.That(Table(dir, PlacementRecordWriter.StopAdjustFile).Last()["event"], Is.EqualTo("timeout"));
        }

        [Test]
        public void No_input_times_out_moving_and_reflects_at_both_ends()
        {
            // 출발 2.0 m, 가까워지며 → 0.4 m(6.4 s)에서 반사 → 멀어지며. 12 s면 2.0 − 1.6 + 1.4 = 1.8 m
            var objD = new List<double>();
            string dir = Run(OneRound(12), loopInput: (s, e) => new PlacementInputFrame(), eachFrame: s =>
            {
                if (s.Phase == PlacementPhase.StopDistance && s.StopRoundActive) objD.Add(s.StopDistanceNow);
            });
            Assert.That(objD.Min(), Is.EqualTo(0.4).Within(0.006));
            Assert.That(objD.Max(), Is.LessThanOrEqualTo(2.0 + 1e-9));
            Assert.That(objD.All(d => d >= 0.4 - 1e-9 && d <= 3.6 + 1e-9), Is.True);
            var adj = Table(dir, PlacementRecordWriter.StopAdjustFile);
            var turn = adj.Single(a => a["event"] == "turn");
            Assert.That((D(turn["distance_m"]), turn["motion_dir"]), Is.EqualTo((0.4, "recede")), "가까운 끝에서 바로 되돌아감");
            Assert.That(long.Parse(turn["t_ms"], Inv), Is.EqualTo(6400).Within(25));
            Assert.That(D(adj.Last()["distance_m"]), Is.EqualTo(1.8).Within(0.006));
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That((r["end_reason"], r["n_stops"], r["first_stop_distance_m"], r["final_motion_dir"], r["stop_spread_m"]),
                Is.EqualTo(("timeout_moving", "0", "", "", "")));

            // 먼 끝: 멀어지며 출발 → 3.6 m(6.4 s)에서 반사
            string far = Run(OneRound(8, PlacementConfig.DirectionRecede), loopInput: (s, e) => new PlacementInputFrame());
            var t2 = Table(far, PlacementRecordWriter.StopAdjustFile).Single(a => a["event"] == "turn");
            Assert.That((D(t2["distance_m"]), t2["motion_dir"]), Is.EqualTo((3.6, "approach")));
        }

        [Test]
        public void Passes_count_crossings_of_the_final_distance_before_confirm()
        {
            // 출발 2.0(가까워짐) → 1.0에서 멈춤 → 다시 움직여 0.4에서 반사 → 1.5에서 멈춤·확정. 2.0→1.0 구간이 1.5를 한 번 지난다
            var script = new PlacementAutoScript { LoopStops = new[] { new[] { 1.0, 1.5 } }, LoopConfirm = new[] { true }, LoopConfirmWhileMovingRound = 0 };
            string dir = Run(OneRound(), script: script);
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That((r["end_reason"], r["passes_before_confirm"], r["final_motion_dir"], r["n_stops"]), Is.EqualTo(("confirmed", "1", "recede", "2")));
            Assert.That(D(r["final_distance_m"]), Is.EqualTo(1.5).Within(0.006));
            Assert.That(D(r["stop_spread_m"]), Is.EqualTo(0.5).Within(0.012));
        }

        [Test]
        public void Final_near_an_end_is_flagged_at_bound()
        {
            var script = new PlacementAutoScript { LoopStops = new[] { new[] { 0.43 } }, LoopConfirm = new[] { true }, LoopConfirmWhileMovingRound = 0 };
            var r = Table(Run(OneRound(), script: script), PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That(r["at_bound"], Is.EqualTo("1"), "끝(0.4)에서 5 cm 안");
        }

        [Test]
        public void Abort_during_a_round_writes_an_aborted_row()
        {
            string dir = Run(OneRound(), loopInput: Presses((1.0, "t")),
                abortWhen: s => s.Phase == PlacementPhase.StopDistance && s.StopRoundActive && s.StopLoopRoundElapsed > 2.0);
            var r = Table(dir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That((r["end_reason"], r["final_distance_m"], r["n_stops"]), Is.EqualTo(("aborted", "", "1")));
            Assert.That(Table(dir, PlacementRecordWriter.StopAdjustFile).Last()["event"], Is.EqualTo("abort"));
            Assert.That((bool)Json(dir, "summary.json")["completed"], Is.False);
        }

        [Test]
        public void Loop_needs_the_loop_phrases_in_the_task_text()
        {
            var raw = JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath), Encoding.UTF8));
            ((JObject)raw["texts"]).Remove("stop_loop_hint");
            var t = PlacementTaskText.Parse(raw.ToString(), "old.json");
            Assert.That(t.LoopKeysMissing(), Is.EqualTo(new[] { "stop_loop_hint" }));
            Assert.That(Assert.Throws<ArgumentException>(() => new PlacementSession(Loop(), t, new PlacementSessionInfo { SessionId = "x" }, _tmp)).Message,
                Does.Contain("stop_loop_hint"));
            Assert.DoesNotThrow(() => new PlacementSession(PlacementTests.ShortConfig("place"), t, new PlacementSessionInfo { SessionId = "y" }, _tmp).Dispose(),
                "single이면 반복 멈춤 문구가 없어도 된다(옛 문구 파일)");
        }

        [Test]
        public void Loop_phrases_are_draft_with_g60_source_in_both_files()
        {
            var def = PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath));
            foreach (var rel in new[] { PlacementTaskText.DefaultRelativePath, PlacementXrTests.ScaleARelativePath })
            {
                string path = Path.Combine(Application.streamingAssetsPath, rel);
                var t = PlacementTaskText.Load(path);
                Assert.That(t.LoopKeysMissing(), Is.Empty, rel);
                var texts = (JObject)JObject.Parse(File.ReadAllText(path, Encoding.UTF8))["texts"];
                foreach (var k in PlacementTaskText.LoopKeys)
                {
                    Assert.That(t.Status(k), Is.EqualTo("draft"), k);
                    Assert.That((string)texts[k]["source"], Does.Contain("G60-2").And.Contain("2026-11-26").And.Contain("IRB 검토 전"), k);
                    Assert.That(t[k], Is.EqualTo(def[k]), k + ": 두 파일 같은 문구");
                    foreach (var banned in new[] { "치료", "내담자", "진단", "환자", "멀리", "치우", "방금" })
                        Assert.That(t[k], Does.Not.Contain(banned), k + ": 방향 암시·치료 표현·'방금 자리' 금지");
                }
            }
            Assert.That(def.Version, Is.EqualTo("0.10"), "G60-2는 0.6 안에 더함, G65·G66 문구로 0.7, 2026-11-28 확인 버튼 안내·확정 알림으로 0.8, 공간 고르기 문구로 0.9, 조작 안내 고침(G83)으로 0.10");
        }

        [Test]
        public void Paused_hint_says_the_confirm_button_sets_the_place_and_stays_within_the_old_line_count()
        {
            // 2026-11-28 G83: 멈춘 동안의 조작 안내를 문장으로 — 확인 버튼이 자리를 정한다는 것을 분명히 하고, 끝에 붙는 손별 안내가 문장으로 이어진다
            foreach (var rel in new[] { PlacementTaskText.DefaultRelativePath, PlacementXrTests.ScaleARelativePath })
            {
                string path = Path.Combine(Application.streamingAssetsPath, rel);
                var t = PlacementTaskText.Load(path);
                Assert.That(t[PlacementTaskText.StopLoopHintKey], Is.EqualTo("방아쇠를 누르면 다시 움직여요. 확인 버튼을 누르면 이 자리로 정해져요."), rel);
                var src = (string)((JObject)JObject.Parse(File.ReadAllText(path, Encoding.UTF8))["texts"])[PlacementTaskText.StopLoopHintKey]["source"];
                Assert.That(src, Does.Contain("2026-11-28 연구 책임자 결정(G83)"), rel);
                foreach (var banned in new[] { "번째", "라운드", "다음", "예를 들어", "치료" })
                    Assert.That(t[PlacementTaskText.StopLoopKey] + t[PlacementTaskText.StopLoopHintKey], Does.Not.Contain(banned), rel + ": 라운드 수·예시·치료 표현 없음");
                // 판 줄 수는 예전 글(+ 확인 버튼 안내)과 같다(24·26자 모두 8줄 — G63 (1) 알려진 예외에서 더 나빠지지 않음)
                string paused = t[PlacementTaskText.StopLoopKey] + "\n" + t[PlacementTaskText.StopLoopHintKey] + " " + t[PlacementTaskText.ConfirmButtonRightKey];
                string before = t[PlacementTaskText.StopLoopKey] + "\n" + "방아쇠: 다시 움직이기 · 확인 버튼: 이 자리로 정하기" + " " + t[PlacementTaskText.ConfirmButtonRightKey];
                foreach (int w in new[] { PlacementPanelMetrics.ComfortWrapChars, PlacementPanelMetrics.ComfortWrapMaxChars })
                    Assert.That(PlacementPanelMetrics.WrapLineCount(paused, w), Is.LessThanOrEqualTo(PlacementPanelMetrics.WrapLineCount(before, w)), rel + " " + w + "자");
                Assert.That(PlacementPanelMetrics.WrapLineCount(t[PlacementTaskText.StopLoopKey], PlacementPanelMetrics.ComfortWrapChars), Is.EqualTo(5), "움직이는 동안의 판은 그대로 5줄");
            }
        }

        // ── 눈높이 보정 판정 ────────────────────────────────────────────
        static double[] Repeat(double v, int n) => Enumerable.Repeat(v, n).ToArray();

        [Test]
        public void Eye_calibration_passes_and_fails_by_the_rules()
        {
            var cfg = new PlacementConfig { eyeHeightMode = "relative" };
            Assert.That(EyeHeightCalibration.RequiredSamples(cfg), Is.EqualTo(20), "20 Hz × 1 s");
            var h = Enumerable.Range(0, 20).Select(i => 1.70 + (i % 2 == 0 ? 0.004 : -0.004)).ToArray();
            var ok = EyeHeightCalibration.Evaluate(cfg, h, Repeat(3, 20), true, "Floor");
            Assert.That(ok.Ok, Is.True, ok.Reason);
            Assert.That(ok.Info.MeasuredM, Is.EqualTo(1.70).Within(1e-9), "중앙값");
            Assert.That((ok.Info.Samples, ok.Info.Source, ok.Info.TrackingOrigin), Is.EqualTo((20, "calibrated", "Floor")));
            Assert.That(ok.Info.SdM, Is.LessThan(0.005));

            var shaky = EyeHeightCalibration.Evaluate(cfg, Enumerable.Range(0, 20).Select(i => i % 2 == 0 ? 1.65 : 1.75).ToArray(), Repeat(0, 20), true, "Floor");
            Assert.That(shaky.Ok, Is.False);
            Assert.That(shaky.Reason, Does.Contain("SD"));
            var looking = EyeHeightCalibration.Evaluate(cfg, Repeat(1.7, 20), Repeat(20, 20), true, "Floor");
            Assert.That(looking.Ok, Is.False);
            Assert.That(looking.Reason, Does.Contain("아래로"));
            var up = EyeHeightCalibration.Evaluate(cfg, Repeat(1.7, 20), Repeat(-16, 20), true, "Floor");
            Assert.That(up.Reason, Does.Contain("위로"));
            var shortP = EyeHeightCalibration.Evaluate(cfg, Repeat(1.20, 20), Repeat(0, 20), true, "Floor");
            Assert.That(shortP.Ok, Is.False);
            Assert.That(shortP.Reason, Does.Contain("범위"));
            Assert.That(EyeHeightCalibration.Evaluate(cfg, Repeat(1.96, 20), Repeat(0, 20), true, "Floor").Ok, Is.False);
            Assert.That(EyeHeightCalibration.Evaluate(cfg, Repeat(1.30, 20), Repeat(0, 20), true, "Floor").Ok, Is.True, "경계 포함");
            var device = EyeHeightCalibration.Evaluate(cfg, Repeat(1.7, 20), Repeat(0, 20), false, "Device(바닥 아님)");
            Assert.That(device.Ok, Is.False);
            Assert.That(device.Reason, Does.Contain("Floor"));
            Assert.That(EyeHeightCalibration.Evaluate(cfg, new[] { 1.7, 1.7 }, new[] { 0.0, 0.0 }, true, "Floor").Reason, Does.Contain("표본"));
        }

        [Test]
        public void Pitch_sign_and_twenty_hertz_sampling()
        {
            // Unity Euler(pitch, 0, 0): +pitch = 아래를 봄. q = (sin(p/2), 0, 0, cos(p/2))
            double p = 10 * Math.PI / 180;
            Assert.That(EyeHeightCalibration.PitchDegFromQuaternion(Math.Sin(p / 2), 0, 0, Math.Cos(p / 2)), Is.EqualTo(10).Within(1e-9));
            Assert.That(EyeHeightCalibration.PitchDegFromQuaternion(0, 0, 0, 1), Is.EqualTo(0).Within(1e-12));
            double y = 40 * Math.PI / 180;   // yaw만 있으면 pitch 0
            Assert.That(EyeHeightCalibration.PitchDegFromQuaternion(0, Math.Sin(y / 2), 0, Math.Cos(y / 2)), Is.EqualTo(0).Within(1e-9));

            var sampler = new EyeHeightSampler(new PlacementConfig { eyeHeightMode = "relative" });
            for (int i = 0; i < 90 && !sampler.Done; i++) sampler.Add(i / 60.0, 1.7, 0);   // 60 Hz 프레임
            Assert.That(sampler.Done, Is.True);
            Assert.That(sampler.Count, Is.EqualTo(20));
        }

        // ── 눈높이 기준 배치 ────────────────────────────────────────────
        static EyeHeightInfo Calibrated(double e) => new EyeHeightInfo { MeasuredM = e, SdM = 0.004, PitchDeg = 2.5, Samples = 20, TrackingOrigin = "Floor", Source = EyeHeightInfo.SourceCalibrated };

        static PlacementConfig Rel(PlacementConfig c)
        {
            c.eyeHeightMode = PlacementConfig.EyeHeightRelative;
            return c;
        }

        [Test]
        public void Eye_reference_height_gives_the_same_positions_as_none()
        {
            foreach (var mode in new[] { PlacementConfig.ModeSystemMove, PlacementConfig.ModeStatic })
            {
                string none = Run(PlacementTests.ShortConfig("view", mode));
                string rel = Run(Rel(PlacementTests.ShortConfig("view", mode)), eye: EyeHeightInfo.DesktopFixed(1.6));
                foreach (var f in new[] { "objpose.csv", "placement.json", "stopdistance.csv", "trajectory.json", "headpose.csv", "ratings.csv" })
                    Assert.That(File.ReadAllText(Path.Combine(rel, f)), Is.EqualTo(File.ReadAllText(Path.Combine(none, f))), mode + " " + f + ": E = 기준이면 같은 자리");
                var m = Json(rel, "manifest.json");
                Assert.That(m.Properties().Last().Name, Is.EqualTo("eyeHeight"), "manifest 맨 끝");
                Assert.That(((JObject)m["eyeHeight"]).Properties().Select(p => p.Name),
                    Is.EqualTo(new[] { "mode", "referenceM", "measuredM", "offsetM", "sdM", "pitchDeg", "samples", "trackingOrigin", "source" }));
                Assert.That(((string)m["eyeHeight"]["source"], (double)m["eyeHeight"]["offsetM"]), Is.EqualTo(("desktop_fixed", 0.0)));
                Assert.That(m["eyeHeight"]["sdM"].Type, Is.EqualTo(JTokenType.Null));
            }
        }

        [Test]
        public void Eye_relative_shifts_start_stop_target_and_practice_heights_only()
        {
            var eye = Calibrated(1.75);   // +0.15 m
            var cfg = Rel(PlacementTests.ShortConfig("view", PlacementConfig.ModeSystemMove));
            string dir = Run(cfg, eye: eye);
            var pl = Json(dir, "placement.json");
            Assert.That((double)pl["finalHeightM"], Is.EqualTo(1.35).Within(1e-9), "system_move 목표 1.2 + 0.15");
            Assert.That((double)pl["finalDistanceM"], Is.EqualTo(2.5).Within(1e-3), "수평 거리는 그대로");
            var obj = File.ReadAllLines(Path.Combine(dir, "objpose.csv")).Skip(1).Select(l => l.Split(',')).ToList();
            Assert.That(obj.Where(c => c[1] == "baseline").Select(c => D(c[7])).Distinct(), Is.EqualTo(new[] { 1.35 }), "시작 높이 1.2 + 0.15");
            Assert.That(obj.Where(c => c[1] == "stop_distance").Select(c => D(c[7])).Distinct(), Is.EqualTo(new[] { 1.35 }), "멈춤 경로 높이 1.2 + 0.15");
            var m = Json(dir, "manifest.json");
            Assert.That((double)m["eyeHeight"]["measuredM"], Is.EqualTo(1.75));
            Assert.That((double)m["eyeHeight"]["offsetM"], Is.EqualTo(0.15).Within(1e-9));
            Assert.That((string)m["eyeHeight"]["source"], Is.EqualTo("calibrated"));
            Assert.That((double)m["space"]["startHeightM"], Is.EqualTo(1.2), "manifest의 설정값은 그대로(옮긴 양은 eyeHeight.offsetM)");
            Assert.That((string)m["config"]["eyeHeightMode"], Is.EqualTo("relative"));
            var ev = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(new[] { ',' }, 3)).ToList();
            var cal = ev.Single(c => c[1] == "eye_height_calibrated");
            Assert.That(cal[2], Does.Contain("measured_m=1.7500").And.Contain("offset_m=0.1500").And.Contain("source=calibrated"));
            Assert.That(ev.FindIndex(c => c[1] == "eye_height_calibrated"), Is.GreaterThan(ev.FindIndex(c => c[1] == "session_start")));

            // 직접 배치: 참여자가 놓은 높이는 옮기지 않는다(자동 스크립트가 0.9에 놓음). 연습 목표는 0.8 + 0.15
            var place = Rel(PlacementTests.ShortConfig("place"));
            place.placementAssist = true;
            string pdir = Run(place, eye: eye);
            Assert.That((double)Json(pdir, "placement.json")["finalHeightM"], Is.EqualTo(0.9).Within(1e-3), "참여자가 놓은 높이는 그대로");
            Assert.That((double)Json(pdir, "practice.json")["targetHeightM"], Is.EqualTo(0.95).Within(1e-9));

            // 반복 멈춤과 함께: 라운드 경로도 옮긴 높이
            var both = Rel(OneRound(3));
            string bdir = Run(both, eye: Calibrated(1.45), loopInput: Presses((1.0, "t"), (1.5, "c")));
            var stopRows = File.ReadAllLines(Path.Combine(bdir, "objpose.csv")).Skip(1).Select(l => l.Split(',')).Where(c => c[1] == "stop_distance").ToList();
            Assert.That(stopRows.Select(c => D(c[7])).Distinct(), Is.EqualTo(new[] { 1.05 }), "1.2 − 0.15");
            var r = Table(bdir, PlacementRecordWriter.StopRoundsFile).Single();
            Assert.That(r["end_reason"], Is.EqualTo("confirmed"));
        }

        [Test]
        public void Eye_relative_refuses_without_a_calibration_or_out_of_range()
        {
            var cfg = Rel(PlacementTests.ShortConfig("place"));
            Assert.That(Assert.Throws<ArgumentException>(() => new PlacementSession(cfg, PlacementTests.LoadText(), new PlacementSessionInfo { SessionId = "x" }, _tmp)).Message,
                Does.Contain("눈높이"));
            Assert.Throws<ArgumentException>(() => new PlacementSession(cfg, PlacementTests.LoadText(), new PlacementSessionInfo { SessionId = "x", EyeHeight = Calibrated(2.1) }, _tmp));
            Assert.That(Directory.GetDirectories(_tmp), Is.Empty, "거부하면 기록 폴더를 만들지 않는다");
            Assert.DoesNotThrow(() => new PlacementSession(PlacementTests.ShortConfig("place"), PlacementTests.LoadText(),
                new PlacementSessionInfo { SessionId = "y", EyeHeight = Calibrated(1.75) }, _tmp).Dispose(), "none이면 눈높이를 보지 않는다");
        }
    }
}
