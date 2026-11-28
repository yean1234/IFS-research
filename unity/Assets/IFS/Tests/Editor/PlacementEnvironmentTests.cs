// EditMode 테스트: 배치 공간 후보 B·E·F(G52–G56) — 설정 environment·placementAssist, 기본값 불변(바이트 단위),
// 배치 연습(본 결과와 섞이지 않음), 범위 안내 문장, manifest 기록, 문구 파일, 셰이더 원문(결정적 별 하늘, 단일 패스 인스턴싱), 자연 사진 출처.
// UnityEngine 없이 돈다(dotnet compile-check에서도 실행). 렌더가 필요한 것은 UnityOnly/PlacementEnvironmentRenderTests.cs.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Text.RegularExpressions;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementEnvironmentTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-env-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        // 문구 파일(버전이 0.2 → 0.3으로 바뀜)에 기대지 않는 고정 문구. 기본값 불변 대조는 코드만 본다.
        const string FixedTextJson = @"{
  ""version"": ""fixed-1"", ""protocol"": ""placement-task"",
  ""texts"": {
    ""intro"": { ""text"": ""i"", ""status"": ""draft"", ""source"": ""test"" },
    ""baseline"": { ""text"": ""b"", ""status"": ""draft"", ""source"": ""test"" },
    ""condition_place"": { ""text"": ""cp"", ""status"": ""draft"", ""source"": ""test"" },
    ""condition_view"": { ""text"": ""cv"", ""status"": ""draft"", ""source"": ""test"" },
    ""condition_point_select"": { ""text"": ""cs"", ""status"": ""draft"", ""source"": ""test"" },
    ""wait"": { ""text"": ""w"", ""status"": ""draft"", ""source"": ""test"" },
    ""stop_distance"": { ""text"": ""s"", ""status"": ""draft"", ""source"": ""test"" },
    ""done"": { ""text"": ""d"", ""status"": ""spec"", ""source"": ""test"" },
    ""own"": { ""text"": ""o"", ""when"": [""pre"", ""post""], ""anchors"": { ""low"": ""l"", ""high"": ""h"" }, ""status"": ""draft"", ""source"": ""test"" },
    ""placed_by_me"": { ""text"": ""p"", ""when"": ""check"", ""anchors"": { ""low"": ""l"", ""high"": ""h"" }, ""status"": ""draft"", ""source"": ""test"" }
  }
}";

        static PlacementTaskText FixedText() => PlacementTaskText.Parse(FixedTextJson, "fixed.json");

        /// <summary>고정 문구 + 놓기 도움 문구 두 개.</summary>
        static PlacementTaskText FixedTextWithAssist()
        {
            var o = JObject.Parse(FixedTextJson);
            o["texts"]["practice"] = new JObject { ["text"] = "PRACTICE", ["status"] = "draft", ["source"] = "test" };
            o["texts"]["placement_range"] = new JObject { ["text"] = "RANGE", ["status"] = "draft", ["source"] = "test" };
            return PlacementTaskText.Parse(o.ToString(), "fixed-assist.json");
        }

        static string DefaultPath => Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath);
        static string ScaleAPath => Path.Combine(Application.streamingAssetsPath, "IFS", "placement_task.scaleA.v0.json");
        static string ResourcesDir => Path.Combine(Application.streamingAssetsPath, "..", "IFS", "Runtime", "Resources", "IFS");

        /// <summary>러너처럼: 세션이 보일 수 있는 draft 키만 manifest에(DraftKeysFor).</summary>
        string RunFixed(PlacementConfig cfg, PlacementTaskText text = null, Func<PlacementSession, bool> abortWhen = null,
            PlacementAutoScript script = null, Action<PlacementSession> eachFrame = null)
        {
            text = text ?? FixedText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 2, SessionId = "SYN-ENV", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 24, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeysFor(cfg.placementAssist).ToArray(),
            };
            var warnings = new List<string>();
            var notice = PlacementTaskText.DraftNotice(text, cfg.requireSpecPhrases, cfg.placementAssist);
            if (notice != null) warnings.Add(notice);
            script = script ?? new PlacementAutoScript();
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records", Guid.NewGuid().ToString("N")), null, warnings))
            {
                for (int i = 0; i < 200000 && !s.Finished; i++)
                {
                    if (abortWhen != null && abortWhen(s)) { s.Abort(); break; }
                    script.Step(s, 0.02, PlacementAutoScript.ScriptedHead(s.Now));
                    eachFrame?.Invoke(s);
                }
                Assert.That(s.Finished, Is.True);
                return s.RecordDirectory;
            }
        }

        static string Sha(string path)
        {
            using (var sha = SHA256.Create())
                return BitConverter.ToString(sha.ComputeHash(File.ReadAllBytes(path))).Replace("-", "").ToLowerInvariant();
        }

        static readonly string[] HashedFiles =
            { "manifest.json", "headpose.csv", "objpose.csv", "events.csv", "placement.json", "stopdistance.csv", "ratings.csv", "trajectory.json" };

        static JObject Json(string dir, string file) => OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, file)));
        static List<string[]> Csv(string dir, string file) => File.ReadAllLines(Path.Combine(dir, file)).Skip(1).Select(l => l.Split(',')).ToList();
        static List<string> PhaseEvents(string dir) => Csv(dir, "events.csv").Where(c => c[1] == "phase").Select(c => c[2]).ToList();

        static PlacementConfig Assist(string condition = "place", string env = PlacementConfig.EnvironmentNeutral, string mode = PlacementConfig.ModeStatic)
        {
            var c = PlacementTests.ShortConfig(condition, mode);
            c.placementAssist = true;
            c.environment = env;
            return c;
        }

        // ── 기본값 불변(G52) ─────────────────────────────────────────────
        // 아래 sha256은 G52 구현 전 HEAD(0677dcb)의 코드로 같은 입력(고정 문구, 합성 자동 시행)을 돌려 잰 값이다
        // (summary.json은 끝난 시각이 들어가 뺀다). 기본값 설정의 기록이 한 바이트라도 바뀌면 깨진다.
        static readonly Dictionary<string, string> GoldenPlace = new Dictionary<string, string>
        {
            ["manifest.json"] = "822939e23ad455ab132820480abb1066a200b5ac75d20a65722f2c91c587e950",
            ["headpose.csv"] = "017eabde2710a30f106daf425bb0158319c994c9b0964bb4fdbee374dbd01dfc",
            ["objpose.csv"] = "8135fdb301d7f4604599faa5787ac7cb927fcf0e7bc9bd551f22b055c0b89ead",
            ["events.csv"] = "5ef346fd5ae8c1f680060b87f266ce6d41216f616477a78e201eb8a7df8f85bf",
            ["placement.json"] = "034cf2c6d762808f089d6ec52e6e5b5f95399a5e2e9db4ddd3b80dc1709da270",
            ["stopdistance.csv"] = "8c8fe800d05d67ad4874cac7d439196931481a84f2e740a248cca2479ba2b850",
            ["ratings.csv"] = "381de877a05759516e759b1a6f153ab39c87e0de196dd15aee2a6292970e9638",
            ["trajectory.json"] = "f4ab8b702d6ce886ffa25285a61b62161768e880d2c0366e94886ea3b374a486",
        };

        static readonly Dictionary<string, string> GoldenPointSelect = new Dictionary<string, string>
        {
            ["manifest.json"] = "fd4fbc21ad4dda69784e381b167b3a64e41ee3fe3dc5cc19e2b614904c03332f",
            ["headpose.csv"] = "6da234e62d8b2ba2257e483bcba0006af6ce00d03227c70f124996f3f4008ef7",
            ["objpose.csv"] = "4f9ff280068deac2f11b2003a756569d1546fba88955829b73c830800be48fc3",
            ["events.csv"] = "2767f9bb87d994a0e5bd12d5ccf66ceec6d5e13550b8acbe32e44f07bcef76a9",
            ["placement.json"] = "8ad38c528fef01a36db1bc079cdc7c40a2e9f0a37a48011d8facf74b99eb7233",
            ["stopdistance.csv"] = "8c8fe800d05d67ad4874cac7d439196931481a84f2e740a248cca2479ba2b850",
            ["ratings.csv"] = "381de877a05759516e759b1a6f153ab39c87e0de196dd15aee2a6292970e9638",
            ["trajectory.json"] = "a900b2dd7a471e2d3f2fa220a7f6243c8d2beb2211b8559795d490c84ed1cc5b",
        };

        [Test]
        public void Default_config_records_are_byte_identical_to_before_g52()
        {
            var cases = new[]
            {
                (PlacementTests.ShortConfig("place"), GoldenPlace),
                (PlacementTests.ShortConfig("view", PlacementConfig.ModePointSelect), GoldenPointSelect),
            };
            foreach (var (cfg, golden) in cases)
            {
                Assert.That(cfg.environment, Is.EqualTo("neutral"));
                Assert.That(cfg.placementAssist, Is.False);
                string dir = RunFixed(cfg);
                // 값은 .NET 8(dotnet test)에서 잰 것이다. Unity(Mono)에서는 자동 시행 머리 경로(Math.Sin·Cos)의 끝자리가 달라
                // headpose.csv(쿼터니언 소수 6자리)만 다른 sha가 나온다 — 그 파일은 dotnet 실행에서만 대조한다(나머지 7개는 둘 다).
                bool mono = Type.GetType("Mono.Runtime") != null;
                var diff = HashedFiles.Where(f => !(mono && f == "headpose.csv") && Sha(Path.Combine(dir, f)) != golden[f]).ToList();
                Assert.That(diff, Is.Empty, cfg.condition + "/" + cfg.controlMode + ": 기본값 기록이 G52 전과 다른 파일");
                Assert.That(File.Exists(Path.Combine(dir, PlacementRecordWriter.PracticeFile)), Is.False, "기본값에는 연습 파일이 없다");
            }
        }

        [Test]
        public void Config_defaults_parsing_and_validation()
        {
            var c = new PlacementConfig();
            Assert.That(c.environment, Is.EqualTo("neutral"));
            Assert.That(c.placementAssist, Is.False);
            Assert.That(c.UsesSpaceOptions, Is.False);
            Assert.That(c.HasPractice, Is.False);
            Assert.That(PlacementConfig.Environments, Is.EqualTo(new[] { "neutral", "space", "nature" }));
            var json = c.ToJson();
            foreach (var k in new[] { "environment", "placementAssist", "practiceTargetDistanceM", "practiceTargetAzimuthDeg", "practiceTargetHeightM", "practiceCubeSizeM" })
                Assert.That(json.ContainsKey(k), Is.False, k + ": 기본값이면 config에 넣지 않는다");
            Assert.That(PlacementManifest.EnvironmentJson(c), Is.Null);

            foreach (var env in PlacementConfig.Environments)
                Assert.That(new PlacementConfig { environment = env, placementAssist = true }.Validate(), Is.Empty, env);
            Assert.That(new PlacementConfig { environment = "forest" }.Validate().Any(e => e.StartsWith("environment")), Is.True);
            Assert.That(new PlacementConfig { placementAssist = true, practiceTargetDistanceM = 9 }.Validate().Any(e => e.StartsWith("practiceTargetDistanceM")), Is.True, "연습 자리는 바닥 안");
            Assert.That(new PlacementConfig { placementAssist = true, practiceTargetHeightM = 3 }.Validate().Any(e => e.StartsWith("practiceTargetHeightM")), Is.True);
            Assert.That(new PlacementConfig { placementAssist = true, practiceTargetAzimuthDeg = -180 }.Validate().Any(e => e.StartsWith("practiceTargetAzimuthDeg")), Is.True);
            Assert.That(new PlacementConfig { placementAssist = false, practiceTargetDistanceM = 9 }.Validate(), Is.Empty, "도움을 끄면 연습 값은 검사하지 않는다");

            var e2 = new PlacementConfig { environment = "space" };
            Assert.That(e2.UsesSpaceOptions, Is.True);
            var j2 = e2.ToJson();
            Assert.That((string)j2["environment"], Is.EqualTo("space"));
            Assert.That((bool)j2["placementAssist"], Is.False);
            var keys = j2.Properties().Select(p => p.Name).ToList();
            Assert.That(keys.Skip(keys.Count - 6), Is.EqualTo(new[] { "environment", "placementAssist", "practiceTargetDistanceM", "practiceTargetAzimuthDeg", "practiceTargetHeightM", "practiceCubeSizeM" }),
                "새 키는 기존 키 뒤에 붙는다");
            Assert.That(new PlacementConfig { placementAssist = true }.HasPractice, Is.True);
            Assert.That(new PlacementConfig { placementAssist = true, condition = "view" }.HasPractice, Is.False, "보기만 조건에는 연습이 없다(⚠)");
            var clone = new PlacementConfig { environment = "nature", placementAssist = true, practiceTargetAzimuthDeg = 30 }.Clone();
            Assert.That((clone.environment, clone.placementAssist, clone.practiceTargetAzimuthDeg), Is.EqualTo(("nature", true, 30.0)));
        }

        // ── 배치 연습(G53) ───────────────────────────────────────────────
        [Test]
        public void Practice_trial_is_logged_and_never_mixed_into_the_placement_result()
        {
            string plain = RunFixed(PlacementTests.ShortConfig("place"));
            var cfg = Assist("place");
            string assist = RunFixed(cfg, FixedTextWithAssist());

            Assert.That(PhaseEvents(assist), Is.EqualTo(new[] { "intro", "practice", "baseline", "pre_items", "pre_wait", "condition", "post_items", "post_wait", "stop_distance", "check_items", "done" }));
            var pr = Json(assist, PlacementRecordWriter.PracticeFile);
            Assert.That((bool)pr["confirmed"], Is.True);
            Assert.That((string)pr["endedBy"], Is.EqualTo("participant_confirm"));
            Assert.That((int)pr["grabCount"], Is.EqualTo(1));
            Assert.That((double)pr["errorM"], Is.LessThan(0.01), "자동 시행은 상자를 목표 자리에 놓는다");
            Assert.That((double)pr["targetDistanceM"], Is.EqualTo(cfg.practiceTargetDistanceM).Within(1e-4));
            Assert.That((double)pr["targetAzimuthDeg"], Is.EqualTo(cfg.practiceTargetAzimuthDeg).Within(1e-2));
            Assert.That((double)pr["finalHeightM"], Is.EqualTo(cfg.practiceTargetHeightM).Within(0.01));
            var ev = Csv(assist, "events.csv").Select(c => c[1]).ToList();
            foreach (var e in new[] { "practice_start", "practice_grab", "practice_release", "practice_end" }) Assert.That(ev, Does.Contain(e));

            // 본 결과: 연습이 없는 같은 시행과 placement.json이 같다. 연습이 앞에 끼면 시뮬레이션 시계의 부동소수 누적 때문에
            // 조건 단계 안 시각이 한 프레임(20 ms) 어긋날 수 있어 시각 값만 한 프레임 허용으로 본다. 잡기 수·자리·확인은 같아야 한다.
            var pa = Json(assist, "placement.json");
            var pp = Json(plain, "placement.json");
            Assert.That(pa.Properties().Select(p => p.Name), Is.EqualTo(pp.Properties().Select(p => p.Name)), "placement.json에 연습 키가 없다");
            foreach (var k in new[] { "grabCount", "confirmed", "conditionCompleted", "condition", "controlMode", "phaseDurationMs" })
                Assert.That(pa[k].ToString(), Is.EqualTo(pp[k].ToString()), k + ": 연습 값이 본 결과에 섞이지 않는다");
            foreach (var k in new[] { "finalX", "finalY", "finalZ", "finalDistanceM", "finalHeightM" })
                Assert.That((double)pa[k], Is.EqualTo((double)pp[k]).Within(1e-3), k);
            foreach (var k in new[] { "firstGrabMs", "heldMs", "confirmMs" })
                Assert.That((double)pa[k], Is.EqualTo((double)pp[k]).Within(20.0001), k + "(한 프레임 허용)");
            Assert.That((double)pa["pathLengthM"], Is.EqualTo((double)pp["pathLengthM"]).Within(0.02), "연습 상자 경로가 더해지지 않는다");
            var ta = (JArray)Json(assist, "trajectory.json")["samples"];
            var tp = (JArray)Json(plain, "trajectory.json")["samples"];
            Assert.That(ta.Count, Is.EqualTo(tp.Count).Within(1));
            Assert.That((double)ta[0]["z"], Is.EqualTo((double)tp[0]["z"]), "궤적은 본 물체 시작 자리에서 시작");
            Assert.That(Csv(assist, "objpose.csv").Any(c => c[1] == "practice"), Is.False, "objpose.csv에 연습 행이 없다");
            var headPractice = Csv(assist, "headpose.csv").Where(c => c[1] == "practice").ToList();
            Assert.That(headPractice, Is.Not.Empty, "연습 동안 머리 자세는 남는다");
            Assert.That(headPractice.All(c => c.Skip(9).All(x => x == "")), Is.True, "연습 동안 본 물체 칸은 빈칸(숨김)");
            Assert.That(Csv(assist, "events.csv").Where(c => c[1] == "grab").Select(c => c[2].Split(';')[0]), Is.EqualTo(new[] { "count=1", "count=2" }),
                "본 과제 grab 사건은 연습과 따로 센다(count=1부터)");
        }

        [Test]
        public void Practice_can_be_skipped_by_the_experimenter_and_abort_keeps_the_practice_file()
        {
            // 참여자가 확인을 누르지 않음 → 실험자 '다음'
            var noConfirm = new PlacementAutoScript { PracticeConfirmAtSeconds = -1 };
            string dir = RunFixed(Assist(), FixedTextWithAssist(), script: noConfirm,
                eachFrame: s => { if (s.PracticeActive && s.SecondsInPhase > 4) s.PressNext(); });
            var pr = Json(dir, PlacementRecordWriter.PracticeFile);
            Assert.That((string)pr["endedBy"], Is.EqualTo("experimenter"));
            Assert.That((bool)pr["confirmed"], Is.False);
            Assert.That(PhaseEvents(dir), Does.Contain("baseline"));

            string aborted = RunFixed(Assist(), FixedTextWithAssist(), abortWhen: s => s.PracticeActive && s.SecondsInPhase > 1.5);
            Assert.That((string)Json(aborted, PlacementRecordWriter.PracticeFile)["endedBy"], Is.EqualTo("abort"));
            Assert.That((string)Json(aborted, "summary.json")["abortedAt"], Is.EqualTo("practice"));
            Assert.That(File.Exists(Path.Combine(aborted, "placement.json")), Is.False, "본 과제 전 중단이면 placement.json이 없다(예전과 같음)");
        }

        [Test]
        public void Assist_in_view_condition_has_no_practice_and_no_range_sentence()
        {
            string dir = RunFixed(Assist("view", mode: PlacementConfig.ModePointSelect), FixedTextWithAssist());
            Assert.That(PhaseEvents(dir), Does.Not.Contain("practice"));
            Assert.That(File.Exists(Path.Combine(dir, PlacementRecordWriter.PracticeFile)), Is.False);
            var m = Json(dir, "manifest.json");
            Assert.That((bool)m["environment"]["placementAssist"], Is.True);
            Assert.That(m["environment"]["practice"].Type, Is.EqualTo(JTokenType.Null), "연습이 없으면 practice null");
        }

        [Test]
        public void Range_sentence_is_shown_only_with_assist_in_place_condition()
        {
            var seen = new List<string>();
            RunFixed(Assist(), FixedTextWithAssist(), eachFrame: s => { if (s.Phase == PlacementPhase.Condition && s.ParticipantText != null) seen.Add(s.ParticipantText + "|" + s.ParticipantTextKey); });
            Assert.That(seen.Distinct(), Is.EqualTo(new[] { "cp\nRANGE|condition_place+placement_range" }));

            var practiceText = new List<string>();
            RunFixed(Assist(), FixedTextWithAssist(), eachFrame: s => { if (s.PracticeActive) practiceText.Add(s.ParticipantText); });
            Assert.That(practiceText.Distinct(), Is.EqualTo(new[] { "PRACTICE" }));

            var plain = new List<string>();
            RunFixed(PlacementTests.ShortConfig("place"), FixedTextWithAssist(), eachFrame: s => { if (s.Phase == PlacementPhase.Condition) plain.Add(s.ParticipantText); });
            Assert.That(plain.Distinct(), Is.EqualTo(new[] { "cp" }), "도움이 꺼져 있으면 범위 문장 없음");

            var viewTexts = new List<string>();
            RunFixed(Assist("view"), FixedTextWithAssist(), eachFrame: s => { if (s.Phase == PlacementPhase.Condition) viewTexts.Add(s.ParticipantText); });
            Assert.That(viewTexts.Distinct(), Is.EqualTo(new[] { "cv" }));
        }

        [Test]
        public void Assist_requires_the_assist_phrases_but_default_does_not()
        {
            Assert.That(FixedText().AssistKeysMissing(), Is.EqualTo(new[] { "practice", "placement_range" }));
            var ex = Assert.Throws<ArgumentException>(() => new PlacementSession(Assist(), FixedText(), new PlacementSessionInfo { SessionId = "x" }, _tmp));
            Assert.That(ex.Message, Does.Contain("practice"));
            Assert.That(Directory.GetDirectories(_tmp), Is.Empty, "기록 폴더를 만들지 않는다");
            Assert.DoesNotThrow(() => RunFixed(PlacementTests.ShortConfig("place"), FixedText()));
        }

        // ── 보기만 조건의 배치 연습(G59, practiceInAllConditions) ────────
        [Test]
        public void PracticeInAllConditions_gives_view_conditions_the_same_practice()
        {
            var d = new PlacementConfig();
            Assert.That(d.practiceInAllConditions, Is.False);
            Assert.That(d.ToJson().ContainsKey("practiceInAllConditions"), Is.False, "기본값이면 config에 넣지 않는다(기록 바이트 동일)");
            Assert.That(new PlacementConfig { practiceInAllConditions = true }.Validate().Any(e => e.StartsWith("practiceInAllConditions")), Is.True,
                "놓기 도움 없이 켜면 오류(연습은 놓기 도움의 일부)");
            Assert.That(new PlacementConfig { practiceInAllConditions = true, condition = "view" }.HasPractice, Is.False, "놓기 도움이 꺼져 있으면 연습 없음");
            Assert.That(new PlacementConfig { practiceInAllConditions = true, placementAssist = true }.Clone().practiceInAllConditions, Is.True);

            foreach (var mode in new[] { PlacementConfig.ModeStatic, PlacementConfig.ModePointSelect })
            {
                var cfg = Assist("view", mode: mode);
                cfg.practiceInAllConditions = true;
                Assert.That(cfg.Validate(), Is.Empty, mode);
                Assert.That(cfg.HasPractice, Is.True, mode);
                var practiceText = new List<string>();
                var conditionText = new List<string>();
                string dir = RunFixed(cfg, FixedTextWithAssist(), eachFrame: s =>
                {
                    if (s.PracticeActive) practiceText.Add(s.ParticipantText);
                    if (s.Phase == PlacementPhase.Condition && s.ParticipantText != null) conditionText.Add(s.ParticipantText);
                });
                Assert.That(PhaseEvents(dir), Is.EqualTo(new[] { "intro", "practice", "baseline", "pre_items", "pre_wait", "condition", "post_items", "post_wait", "stop_distance", "check_items", "done" }), mode);
                Assert.That(practiceText.Distinct(), Is.EqualTo(new[] { "PRACTICE" }), mode + ": 직접 배치 조건과 같은 연습 안내");
                Assert.That(conditionText.Distinct(), Is.EqualTo(new[] { mode == PlacementConfig.ModePointSelect ? "cs" : "cv" }), mode + ": 보기만 지시문은 그대로(범위 문장 없음)");
                var pr = Json(dir, PlacementRecordWriter.PracticeFile);
                Assert.That((bool)pr["confirmed"], Is.True, mode);
                Assert.That((int)pr["grabCount"], Is.EqualTo(1), mode);
                Assert.That((double)pr["errorM"], Is.LessThan(0.01), mode);
                var m = Json(dir, "manifest.json");
                Assert.That(m["environment"]["practice"].Type, Is.EqualTo(JTokenType.Object), mode + ": environment.practice가 남는다");
                Assert.That((bool)m["config"]["practiceInAllConditions"], Is.True);
                Assert.That(((JObject)m["config"]).Properties().Last().Name, Is.EqualTo("practiceInAllConditions"), "새 키는 config 맨 끝");
                var pl = Json(dir, "placement.json");
                Assert.That((string)pl["controlMode"], Is.EqualTo(mode));
                Assert.That((int)pl["grabCount"], Is.EqualTo(0), mode + ": 연습 잡기는 본 결과에 섞이지 않는다");
                Assert.That(Csv(dir, "objpose.csv").Any(c => c[1] == "practice"), Is.False);
            }
        }

        // ── manifest(G52·G55) ────────────────────────────────────────────
        [Test]
        public void Manifest_records_environment_assist_texture_and_practice_target()
        {
            string dir = RunFixed(Assist("place", PlacementConfig.EnvironmentNature), FixedTextWithAssist());
            var m = Json(dir, "manifest.json");
            Assert.That(m.Properties().Last().Name, Is.EqualTo("environment"), "기존 키 뒤에 붙는다");
            var env = (JObject)m["environment"];
            Assert.That((string)env["name"], Is.EqualTo("nature"));
            Assert.That((bool)env["placementAssist"], Is.True);
            Assert.That((string)env["sky"]["kind"], Is.EqualTo("equirect_photo"));
            var tex = (JObject)env["sky"]["texture"];
            Assert.That((string)tex["assetId"], Is.EqualTo(NatureSkyAsset.AssetId));
            Assert.That((string)tex["sha256"], Is.EqualTo(NatureSkyAsset.Sha256));
            Assert.That((string)tex["license"], Is.EqualTo("CC0-1.0"));
            Assert.That((string)tex["author"], Is.Not.Empty);
            Assert.That((double)env["practice"]["targetDistanceM"], Is.EqualTo(2.0));
            Assert.That((double)env["practice"]["targetAzimuthDeg"], Is.EqualTo(-45));
            Assert.That((double)env["practice"]["targetHeightM"], Is.EqualTo(0.8));
            Assert.That((string)m["config"]["environment"], Is.EqualTo("nature"));
            Assert.That((bool)m["config"]["placementAssist"], Is.True);
            Assert.That(m["taskText"]["draftKeys"].Select(k => (string)k), Does.Contain("practice"), "도움을 켜면 도움 문구도 draftKeys에");

            var space = PlacementManifest.EnvironmentJson(new PlacementConfig { environment = "space" });
            Assert.That((string)space["sky"]["rule"], Is.EqualTo("starfield/1"));
            Assert.That(space["sky"]["texture"], Is.Null);
            Assert.That(space["practice"].Type, Is.EqualTo(JTokenType.Null), "도움을 끄면 연습 없음");
            var b = PlacementManifest.EnvironmentJson(new PlacementConfig { placementAssist = true });
            Assert.That((string)b["name"], Is.EqualTo("neutral"), "후보 B(neutral + 도움)도 기록");
            Assert.That((string)b["sky"]["kind"], Is.EqualTo("gradient"));
        }

        [Test]
        public void Draft_keys_and_notice_leave_out_assist_phrases_when_assist_is_off()
        {
            var t = PlacementTaskText.Load(DefaultPath);
            Assert.That(t.DraftKeys, Does.Contain("practice").And.Contain("placement_range"));
            Assert.That(t.DraftKeysFor(false), Does.Not.Contain("practice").And.Not.Contain("placement_range"));
            // G60-2(문구 파일 0.6): 반복 멈춤 문구 두 개도 stopMode loop가 아니면 빠진다
            Assert.That(t.DraftKeysFor(true), Is.EqualTo(t.DraftKeys.Where(k => !PlacementTaskText.LoopKeys.Contains(k) && !PlacementTaskText.LoopOptionalKeys.Contains(k) && !PlacementTaskText.SpaceChoiceKeys.Contains(k)).ToList()));
            Assert.That(t.DraftKeysFor(true, true), Is.EqualTo(t.DraftKeys.Where(k => !PlacementTaskText.SpaceChoiceKeys.Contains(k)).ToList()), "공간 고르기 문구는 environmentChoice participant일 때만");
            Assert.That(t.DraftKeysFor(true, true, true), Is.EqualTo(t.DraftKeys));
            Assert.That(t.CountFor(false), Is.EqualTo(t.Count - 7), "놓기 도움 2 + 반복 멈춤 2 + 본 측정 시작 안내 1(2026-11-28, loop일 때만) + 공간 고르기 2(2026-11-28, participant일 때만)");
            Assert.That(t.CountFor(true), Is.EqualTo(t.Count - 5));
            Assert.That(PlacementTaskText.DraftNotice(t, false), Does.Contain($"{t.CountFor(false)}/{t.CountFor(false)}개"));
            Assert.That(PlacementTaskText.DraftNotice(t, false, true), Does.Contain($"{t.Count - 5}/{t.Count - 5}개"));
            Assert.That(PlacementTaskText.DraftNotice(t, false, true, true), Does.Contain($"{t.Count - 2}/{t.Count - 2}개"));
            Assert.That(PlacementTaskText.DraftNotice(t, false, true, true, true), Does.Contain($"{t.Count}/{t.Count}개"));
        }

        // ── 문구 파일(원칙 7) ─────────────────────────────────────────────
        [Test]
        public void Assist_phrases_are_draft_with_g53_source_in_both_files()
        {
            foreach (var path in new[] { DefaultPath, ScaleAPath })
            {
                var t = PlacementTaskText.Load(path);
                Assert.That(t.AssistKeysMissing(), Is.Empty, path);
                var raw = (JObject)JObject.Parse(File.ReadAllText(path, Encoding.UTF8))["texts"];
                foreach (var k in PlacementTaskText.AssistKeys)
                {
                    Assert.That(t.Status(k), Is.EqualTo("draft"), k);
                    string src = (string)raw[k]["source"];
                    Assert.That(src, Does.Contain("G53").And.Contain("2026-11-24").And.Contain("IRB 검토 전"), k);
                    foreach (var banned in new[] { "치료", "내담자", "진단", "환자", "멀리", "치우" })
                        Assert.That(t[k], Does.Not.Contain(banned), k);
                }
                Assert.That(t[PlacementTaskText.PlacementRangeKey], Is.EqualTo("둥근 바닥 안이면 어디든, 어떤 높이든 괜찮아요."));
                Assert.That(t[PlacementTaskText.PracticeKey], Is.EqualTo(PlacementTaskText.Load(DefaultPath)[PlacementTaskText.PracticeKey]), "두 파일 같은 문구");
            }
            Assert.That(PlacementTaskText.Load(DefaultPath).Version, Is.EqualTo("0.10"), "2026-11-28 확인 버튼 안내·확정 알림·본 측정 시작 안내로 0.8, 공간 고르기 문구로 0.9, 반복 멈춤 조작 안내(G83)로 0.10");
            Assert.That(PlacementTaskText.Load(ScaleAPath).Version, Is.EqualTo("0.10-scaleA"));
        }

        // ── 놓기 도움 화면 규칙 ──────────────────────────────────────────
        [Test]
        public void Boundary_glow_rises_near_the_edge_and_contact_ring_has_a_minimum()
        {
            Assert.That(PlacementAssistVisuals.BoundaryGlow(0, 4), Is.EqualTo(0));
            Assert.That(PlacementAssistVisuals.BoundaryGlow(2.9, 4), Is.EqualTo(0));
            Assert.That(PlacementAssistVisuals.BoundaryGlow(3.5, 4), Is.EqualTo(0.5).Within(1e-9));
            Assert.That(PlacementAssistVisuals.BoundaryGlow(4, 4), Is.EqualTo(1));
            Assert.That(PlacementAssistVisuals.BoundaryGlow(4.5, 4), Is.EqualTo(1));
            Assert.That(PlacementAssistVisuals.BoundaryGlow(3.8, 4), Is.GreaterThan(PlacementAssistVisuals.BoundaryGlow(3.6, 4)), "가까울수록 밝다");
            Assert.That(PlacementAssistVisuals.ContactRingRadius(0.05), Is.EqualTo(0.12));
            Assert.That(PlacementAssistVisuals.ContactRingRadius(0.3), Is.EqualTo(0.3));
        }

        // ── 셰이더 원문(빌드 안전·결정적) ───────────────────────────────
        static string Shader(string file) => File.ReadAllText(Path.Combine(ResourcesDir, file));

        [Test]
        public void New_shaders_live_in_resources_and_use_single_pass_instancing_macros()
        {
            foreach (var (file, name, resource) in new[]
            {
                ("EnvironmentStarfield.shader", "IFS/Environment Starfield", EnvironmentStyleInfo.StarfieldShaderResource),
                ("EnvironmentPanorama.shader", "IFS/Environment Panorama", EnvironmentStyleInfo.PanoramaShaderResource),
                ("EnvironmentGround.shader", "IFS/Environment Ground", EnvironmentStyleInfo.GroundShaderResource),
            })
            {
                Assert.That(resource, Is.EqualTo("IFS/" + Path.GetFileNameWithoutExtension(file)), "Resources.Load 경로 = Resources/IFS/파일 이름");
                string src = Shader(file);
                Assert.That(src, Does.Contain("Shader \"" + name + "\""));
                foreach (var macro in new[] { "UNITY_VERTEX_INPUT_INSTANCE_ID", "UNITY_VERTEX_OUTPUT_STEREO", "UNITY_SETUP_INSTANCE_ID", "UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO" })
                    Assert.That(src, Does.Contain(macro), file + ": " + macro);
                Assert.That(src, Does.Contain("FallBack Off"), file);
            }
            Assert.That(Directory.GetFiles(Path.Combine(Application.streamingAssetsPath, "..", "IFS", "Runtime"), "*.cs", SearchOption.AllDirectories)
                .Where(f => File.ReadAllText(f).Contains("EnvironmentStarfield") || File.ReadAllText(f).Contains("EnvironmentPanorama"))
                .All(f => !Regex.IsMatch(File.ReadAllText(f), @"Shader\.Find\(\s*""IFS/Environment (Starfield|Panorama|Ground)")), Is.True, "Shader.Find를 쓰지 않는다");
        }

        [Test]
        public void Starfield_shader_is_deterministic_no_time_no_random_no_texture()
        {
            string src = Shader("EnvironmentStarfield.shader");
            string code = Regex.Replace(src, @"//[^\n]*", "");
            foreach (var banned in new[] { "_Time", "_SinTime", "_CosTime", "unity_DeltaTime", "sampler2D", "tex2D", "random", "Random" })
                Assert.That(code, Does.Not.Contain(banned), "결정적이어야 함: " + banned);
            Assert.That(code, Does.Contain("Hash43"), "해시로 별을 정한다");
            Assert.That(src, Does.Contain("starfield/1"));
            Assert.That(EnvironmentStyleInfo.StarfieldRule, Is.EqualTo("starfield/1"));
            // 남색 바탕: 완전한 검정이 아니고 파랑이 가장 큼
            var bg = EnvironmentStyleInfo.StarBackgroundSrgb;
            Assert.That(bg.Max(), Is.GreaterThan(0.05));
            Assert.That(bg[2], Is.GreaterThan(bg[0]).And.GreaterThan(bg[1]));
        }

        // ── 자연 사진(G55) ───────────────────────────────────────────────
        [Test]
        public void Nature_texture_file_matches_recorded_sha_and_license_note()
        {
            string dir = Path.Combine(ResourcesDir, "Nature");
            string file = Path.Combine(dir, NatureSkyAsset.FileName);
            Assert.That(File.Exists(file), Is.True);
            Assert.That(Sha(file), Is.EqualTo(NatureSkyAsset.Sha256), "manifest에 남기는 sha256 = 저장소 파일");
            Assert.That(new FileInfo(file).Length, Is.LessThan(8 * 1024 * 1024));
            Assert.That(NatureSkyAsset.ResourcePath, Is.EqualTo("IFS/Nature/" + Path.GetFileNameWithoutExtension(NatureSkyAsset.FileName)));
            string lic = File.ReadAllText(Path.Combine(dir, "LICENSE.txt"));
            foreach (var s in new[] { NatureSkyAsset.AssetId, NatureSkyAsset.Author, NatureSkyAsset.SourcePage, NatureSkyAsset.Sha256, NatureSkyAsset.OriginalSha256, "CC0", NatureSkyAsset.DownloadedOn })
                Assert.That(lic, Does.Contain(s));
            // JPEG 머리(SOI)와 크기(4096 × 2048: SOF0 표지)
            var bytes = File.ReadAllBytes(file);
            Assert.That(bytes[0] == 0xFF && bytes[1] == 0xD8, Is.True, "JPEG");
            int i = 2;
            int w = 0, h = 0;
            while (i + 9 < bytes.Length)
            {
                if (bytes[i] != 0xFF) { i++; continue; }
                byte marker = bytes[i + 1];
                int len = (bytes[i + 2] << 8) | bytes[i + 3];
                if (marker == 0xC0 || marker == 0xC2) { h = (bytes[i + 5] << 8) | bytes[i + 6]; w = (bytes[i + 7] << 8) | bytes[i + 8]; break; }
                i += 2 + len;
            }
            Assert.That((w, h), Is.EqualTo((NatureSkyAsset.Width, NatureSkyAsset.Height)), "등장방형 2:1");
        }
    }
}
