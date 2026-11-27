// EditMode 테스트(dotnet·Unity 공통): 배치 실험 헤드셋 경로(2026-11-23).
//   입력 고르기 규칙(XR 유/무, inputMode), XR 컨트롤러 입력 규칙(가짜 장치 주입 — 버튼 에지·이력·데드존·평정 고르기),
//   세션에서 XR 입력: view 조건에서 물체를 움직이는 입력 무시, 당기기/밀기로 팔 길이 너머까지 + 경계 clamp,
//   문구 파일 anchors 숫자 키(기존 파일 호환)·평정 지시문, scaleA 문구 파일, hideObjectDuringItems, 참여자 컨트롤러 평정.
// 합성 입력만 쓴다(참여자 자료 아님).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementXrTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-xr-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        public const string ScaleARelativePath = "IFS/placement_task.scaleA.v0.json";
        static string ScaleAPath => Path.Combine(Application.streamingAssetsPath, ScaleARelativePath);
        static string DefaultPath => Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath);


        static XrControllerSample Pad(double trigger = 0, bool grip = false, bool primary = false, double x = 0, double y = 0, bool valid = true,
            PVec3? origin = null, PVec3? dir = null)
        {
            return new XrControllerSample
            {
                Valid = valid, HasPose = valid, Trigger = trigger, GripButton = grip, PrimaryButton = primary, StickX = x, StickY = y,
                RayOrigin = origin ?? new PVec3(0.2, 1.2, 0.2), RayDirection = dir ?? new PVec3(0, 0, 1),
            };
        }

        // ── 입력 고르기 ───────────────────────────────────────────────────
        [Test]
        public void Input_selection_uses_xr_only_when_a_headset_is_active()
        {
            var r = PlacementInputSelection.Choose("auto", false, false);
            Assert.That(r.Source, Is.EqualTo("desktop"));
            Assert.That(r.Error, Is.Null);
            Assert.That(r.Warning, Is.Null);

            r = PlacementInputSelection.Choose("auto", true, true);
            Assert.That(r.Source, Is.EqualTo("xr"));
            Assert.That(r.Warning, Is.Null);

            r = PlacementInputSelection.Choose("auto", true, false, "left");
            Assert.That(r.Source, Is.EqualTo("xr"), "헤드셋이 켜져 있으면 컨트롤러가 잠들어 있어도 XR(깨우면 잡힌다)");
            Assert.That(r.Warning, Does.Contain("왼손"));

            r = PlacementInputSelection.Choose("desktop", true, true);
            Assert.That(r.Source, Is.EqualTo("desktop"), "강제 desktop");
            Assert.That(r.Warning, Does.Contain("desktop"));

            r = PlacementInputSelection.Choose("xr", false, false);
            Assert.That(r.Source, Is.Null);
            Assert.That(r.Error, Does.Contain("XR 헤드셋이 없습니다"), "강제 xr인데 헤드셋이 없으면 시작 거부");

            r = PlacementInputSelection.Choose("xr", true, true);
            Assert.That(r.Source, Is.EqualTo("xr"));
            Assert.That(r.Error, Is.Null);

            Assert.That(PlacementInputSelection.Choose("vr", true, true).Error, Does.Contain("inputMode"));
        }

        [Test]
        public void New_config_keys_default_to_desktop_safe_values_and_are_validated()
        {
            var c = new PlacementConfig();
            Assert.That(c.inputMode, Is.EqualTo("auto"));
            Assert.That(c.xrHand, Is.EqualTo("right"));
            Assert.That(c.participantRatesWithController, Is.False);
            Assert.That(c.hideObjectDuringItems, Is.False);
            Assert.That(c.condition, Is.EqualTo("place"));
            Assert.That(new PlacementConfig { condition = "view" }.controlMode, Is.EqualTo("static"), "기본 통제 조건은 static 그대로");
            Assert.That(c.Validate(), Is.Empty);
            Assert.That(new PlacementConfig { inputMode = "vr" }.Validate().Any(e => e.StartsWith("inputMode")), Is.True);
            Assert.That(new PlacementConfig { xrHand = "both" }.Validate().Any(e => e.StartsWith("xrHand")), Is.True);
            var j = c.ToJson();
            Assert.That((string)j["inputMode"], Is.EqualTo("auto"));
            Assert.That((string)j["xrHand"], Is.EqualTo("right"));
            Assert.That((bool)j["participantRatesWithController"], Is.False);
            Assert.That((bool)j["hideObjectDuringItems"], Is.False);
            Assert.That((double)j["conditionSeconds"], Is.EqualTo(90), "기존 키는 그대로");
        }

        // ── XR 입력 규칙(가짜 장치) ──────────────────────────────────────
        [Test]
        public void Trigger_edges_use_hysteresis_and_count_only_the_press_moment()
        {
            var logic = new XrPlacementInputLogic();
            var seq = new[] { 0.0, 0.6, 0.7, 0.4, 0.3, 0.6 };   // 0.4는 아직 눌림(뗌 0.35 이하에서 뗌)
            var frames = seq.Select(t => logic.Step(Pad(trigger: t), true)).ToList();
            Assert.That(frames.Select(f => f.GrabDown), Is.EqualTo(new[] { false, true, false, false, false, true }));
            Assert.That(frames.Select(f => f.GrabHeld), Is.EqualTo(new[] { false, true, true, true, false, true }));
            Assert.That(frames.Select(f => f.StopDown), Is.EqualTo(new[] { false, true, false, false, false, true }));
            Assert.That(frames.Select(f => f.StopHeld), Is.EqualTo(new[] { false, true, true, true, false, true }));
            Assert.That(frames.Select(f => f.RateSubmitDown), Is.EqualTo(new[] { false, true, false, false, false, true }));

            // 아날로그 값이 없으면 triggerButton을 쓴다
            var l2 = new XrPlacementInputLogic();
            var b = new[] { false, true, true, false }.Select(p => l2.Step(new XrControllerSample { Valid = true, HasPose = true, Trigger = double.NaN, TriggerButton = p }, true)).ToList();
            Assert.That(b.Select(f => f.StopDown), Is.EqualTo(new[] { false, true, false, false }));

            // 그립도 잡기(멈춤 거리 버튼은 아님)
            var l3 = new XrPlacementInputLogic();
            var g = new[] { false, true, true, false }.Select(p => l3.Step(Pad(grip: p), true)).ToList();
            Assert.That(g.Select(f => f.GrabDown), Is.EqualTo(new[] { false, true, false, false }));
            Assert.That(g.Any(f => f.StopDown || f.StopHeld), Is.False);
        }

        [Test]
        public void Confirm_is_the_primary_button_press_and_disabled_input_makes_no_false_edges()
        {
            var logic = new XrPlacementInputLogic();
            var c = new[] { false, true, true, false, true }.Select(p => logic.Step(Pad(primary: p), true).ConfirmDown).ToList();
            Assert.That(c, Is.EqualTo(new[] { false, true, false, false, true }));

            // 꺼 둔 동안 누르기 시작해 켠 뒤에도 누르고 있으면 '눌림'이 아니다(실험자가 글을 치는 동안 등)
            var l2 = new XrPlacementInputLogic();
            var off = l2.Step(Pad(trigger: 1.0, primary: true), false);
            Assert.That(off.HasRay || off.GrabDown || off.GrabHeld || off.ConfirmDown || off.StopDown, Is.False, "꺼져 있으면 빈 프레임");
            var on = l2.Step(Pad(trigger: 1.0, primary: true), true);
            Assert.That(on.GrabDown, Is.False);
            Assert.That(on.StopDown, Is.False);
            Assert.That(on.ConfirmDown, Is.False);
            Assert.That(on.GrabHeld, Is.True, "누르고 있음은 그대로 보인다");

            // 장치가 잠깐 사라졌다가 돌아와도 계속 누르고 있던 버튼은 새 '눌림'이 아니다
            var l3 = new XrPlacementInputLogic();
            Assert.That(l3.Step(Pad(trigger: 1.0), true).GrabDown, Is.True);
            var lost = l3.Step(Pad(valid: false), true);
            Assert.That(lost.HasRay || lost.GrabHeld, Is.False, "장치가 없으면 빈 프레임(잡은 물체는 놓인다)");
            Assert.That(l3.Step(Pad(trigger: 1.0), true).GrabDown, Is.False);
        }

        [Test]
        public void Stick_y_is_push_pull_with_deadzone_and_stick_x_steps_ratings_once_per_flick()
        {
            Assert.That(XrPlacementInputLogic.Deadzone(0.1, 0.2), Is.EqualTo(0));
            Assert.That(XrPlacementInputLogic.Deadzone(1.0, 0.2), Is.EqualTo(1.0).Within(1e-12));
            Assert.That(XrPlacementInputLogic.Deadzone(-0.6, 0.2), Is.EqualTo(-0.5).Within(1e-12));
            Assert.That(XrPlacementInputLogic.Deadzone(double.NaN, 0.2), Is.EqualTo(0));
            var logic = new XrPlacementInputLogic();
            Assert.That(logic.Step(Pad(y: 1.0), true).PushPullAxis, Is.EqualTo(1.0).Within(1e-12), "앞 = 밀기(+)");
            Assert.That(logic.Step(Pad(y: -1.0), true).PushPullAxis, Is.EqualTo(-1.0).Within(1e-12), "뒤 = 당기기(−)");

            var l2 = new XrPlacementInputLogic();
            var xs = new[] { 0.0, 0.7, 0.9, 0.5, 0.2, 0.8, 0.1, -0.7, -0.95, 0.0 };
            var steps = xs.Select(x => l2.Step(Pad(x: x), true).RateStep).ToList();
            Assert.That(steps, Is.EqualTo(new[] { 0, 1, 0, 0, 0, 1, 0, -1, 0, 0 }), "젖힌 순간 한 칸, 0.3 아래로 돌아와야 다음 칸");
        }

        [Test]
        public void Ray_end_goes_to_the_held_object_then_object_hit_then_floor()
        {
            var o = new PVec3(0, 1.2, 0);
            var obj = new PVec3(0, 1.2, 3);
            Assert.That(XrRayVisual.EndDistance(o, new PVec3(1, 0, 0), true, obj, true, 0.2, 8), Is.EqualTo(3).Within(1e-9), "잡고 있으면 물체 중심까지");
            Assert.That(XrRayVisual.EndDistance(o, new PVec3(0, 0, 1), false, obj, true, 0.2, 8), Is.EqualTo(2.8).Within(1e-9), "물체 겉면");
            Assert.That(XrRayVisual.EndDistance(o, new PVec3(0, -1.2, 2.4), false, obj, false, 0.2, 8), Is.EqualTo(Math.Sqrt(1.44 + 5.76)).Within(1e-9), "바닥");
            Assert.That(XrRayVisual.EndDistance(o, new PVec3(0, 1, 0), false, obj, true, 0.2, 8), Is.EqualTo(8), "아무것도 없으면 최대 길이");
        }

        // ── 세션 + XR 입력 ────────────────────────────────────────────────
        PlacementSession NewSession(PlacementConfig cfg, PlacementTaskText text = null, int participant = 1)
        {
            text = text ?? PlacementTests.LoadText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = participant, SessionId = "SYN-XR", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 23, 1, 2, 3, DateTimeKind.Utc), InputSource = "xr",
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeys.ToArray(),
            };
            return new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records"), null, new List<string>());
        }

        /// <summary>실험자: 안내·대기·평정 지시문·멈춤 거리 시작만 넘긴다(평정 숫자는 넣지 않음).</summary>
        static void ExperimenterNextOnly(PlacementSession s)
        {
            if (s.Phase == PlacementPhase.Intro || s.Phase == PlacementPhase.PreWait || s.Phase == PlacementPhase.PostWait || s.ItemsInstructionActive
                || (s.Phase == PlacementPhase.StopDistance && !s.StopTrialsStarted))
                s.PressNext();
        }

        static void TickUntil(PlacementSession s, Func<PlacementSession, bool> until, Func<PlacementSession, PlacementInputFrame> participant,
            Action<PlacementSession> experimenter, double dt = 0.02, int max = 200000)
        {
            for (int i = 0; i < max && !s.Finished && !until(s); i++)
            {
                s.Tick(dt, participant(s), PlacementAutoScript.ScriptedHead(s.Now));
                experimenter?.Invoke(s);
            }
        }

        [Test]
        public void View_condition_ignores_xr_grab_and_push_pull()
        {
            foreach (var mode in new[] { "static", "system_move" })   // replay·point_select는 PlacementTests가 본다(입력을 쓰지 않거나 바닥 점만 받는다)
            {
                var cfg = PlacementTests.ShortConfig("view", mode);
                var auto = new PlacementAutoScript();
                using (var s = NewSession(cfg))
                {
                    var logic = new XrPlacementInputLogic();
                    TickUntil(s, x => x.Phase == PlacementPhase.Condition, x => auto.Participant(x), auto.Experimenter);
                    var start = s.ObjectPosition;
                    int frame = 0;
                    // 조건 단계 내내 물체를 겨눈 광선 + 트리거 누르고 떼기 반복 + 썸스틱 앞으로
                    TickUntil(s, x => x.Phase != PlacementPhase.Condition, x =>
                    {
                        frame++;
                        var origin = new PVec3(0.2, 1.2, 0.2);
                        return logic.Step(Pad(trigger: frame % 20 < 10 ? 1.0 : 0.0, y: 1.0, primary: frame % 50 == 0, origin: origin,
                            dir: (x.ObjectPosition - origin).Normalized), true);
                    }, null);
                    Assert.That(s.GrabCount, Is.EqualTo(0), mode + ": 보기만 조건은 잡기를 받지 않는다");
                    Assert.That(s.Held, Is.False);
                    if (mode == "static")
                    {
                        Assert.That(PVec3.Distance(s.ConditionFinalPosition, start), Is.LessThan(1e-9), "static: 물체는 시작 자리 그대로");
                        Assert.That(s.PathLengthM, Is.EqualTo(0));
                    }
                    else
                    {
                        var target = PlacementGeometry.FromPolar(cfg.systemMoveTargetDistanceM, cfg.systemMoveTargetAzimuthDeg, cfg.systemMoveTargetHeightM);
                        Assert.That(PlacementGeometry.HorizontalDistance(s.ConditionFinalPosition), Is.LessThanOrEqualTo(PlacementGeometry.HorizontalDistance(target) + 1e-9),
                            "system_move: 시스템만 움직인다(밀기로 더 멀어지지 않음)");
                    }
                    s.Abort();
                }
            }
        }

        [Test]
        public void Xr_push_moves_a_grabbed_object_beyond_arm_length_and_stops_at_the_floor_edge()
        {
            var cfg = PlacementTests.ShortConfig("place");
            cfg.conditionSeconds = 30;
            var auto = new PlacementAutoScript();
            using (var s = NewSession(cfg))
            {
                TickUntil(s, x => x.Phase == PlacementPhase.Condition, x => auto.Participant(x), auto.Experimenter);
                var logic = new XrPlacementInputLogic();
                var origin = new PVec3(0.2, 1.2, 0.2);
                PVec3 aim = s.ObjectPosition;
                var dir = (aim - origin).Normalized;   // 잡은 뒤에도 같은 방향을 겨눈다(먼 곳으로 민다)
                // 1) 트리거로 잡는다
                s.Tick(0.02, logic.Step(Pad(trigger: 1.0, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.Held, Is.True, "광선이 물체에 맞고 트리거를 누른 순간 잡힌다");
                Assert.That(s.GrabCount, Is.EqualTo(1));
                // 2) 썸스틱 앞으로 2초: 팔 길이(약 0.7 m)보다 훨씬 먼 곳까지
                for (int i = 0; i < 100; i++) s.Tick(0.02, logic.Step(Pad(trigger: 1.0, y: 1.0, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                double hold2 = s.HoldDistanceM;
                Assert.That(hold2, Is.GreaterThan(3.0), "1 m/s × 2 s만큼 밀어 잡은 거리 > 3 m");
                Assert.That(PlacementGeometry.HorizontalDistance(s.ObjectPosition), Is.GreaterThan(3.0));
                // 3) 더 밀어도 바닥 경계(반지름 4 m) 밖으로 나가지 않는다
                for (int i = 0; i < 400; i++) s.Tick(0.02, logic.Step(Pad(trigger: 1.0, y: 1.0, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.HoldDistanceM, Is.EqualTo(cfg.holdMaxM).Within(1e-9), "잡은 거리는 holdMaxM에서 멈춤");
                Assert.That(PlacementGeometry.HorizontalDistance(s.ObjectPosition), Is.LessThanOrEqualTo(cfg.floorRadiusM + 1e-9), "경계 clamp");
                Assert.That(PlacementGeometry.HorizontalDistance(s.ObjectPosition), Is.EqualTo(cfg.floorRadiusM).Within(1e-6));
                // 4) 당기기: 썸스틱 뒤로
                for (int i = 0; i < 400; i++) s.Tick(0.02, logic.Step(Pad(trigger: 1.0, y: -1.0, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.HoldDistanceM, Is.EqualTo(cfg.holdMinM).Within(1e-9), "당겨도 holdMinM에서 멈춤");
                // 5) 떼면 놓고, A로 확인
                s.Tick(0.02, logic.Step(Pad(trigger: 0.0, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.Held, Is.False);
                s.Tick(0.02, logic.Step(Pad(primary: true, origin: origin, dir: dir), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.Confirmed, Is.True, "A·X = 확인");
                s.Abort();
            }
        }

        // ── 문구 파일 ────────────────────────────────────────────────────
        [Test]
        public void Anchors_accept_numbered_points_and_old_files_stay_valid()
        {
            var old = PlacementTaskText.Load(DefaultPath);
            Assert.That(old.Items.All(i => i.Points.Count == 0), Is.True, "기존 파일: 숫자 기준점 없음");
            var own = old.Items.First(i => i.Key == "own");
            Assert.That(own.AnchorAt(1), Is.EqualTo("전혀 내 것 같지 않다"));
            Assert.That(own.AnchorAt(7), Is.EqualTo("완전히 내 것 같다"));
            Assert.That(own.AnchorAt(4), Is.Null);
            Assert.That(PlacementTaskText.ItemDisplay(own), Is.EqualTo("이것이 얼마나 '내 것' 같나요?\n1(전혀 내 것 같지 않다) — 7(완전히 내 것 같다)"), "예전 표시 그대로");
            Assert.That(old.InstructionFor("pre"), Is.Null, "기존 파일에는 평정 지시문이 없다");

            var raw = JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
            raw["texts"]["own"]["anchors"] = new JObject { ["1"] = "매우 싫다", ["4"] = "좋지도 싫지도 않다", ["7"] = "매우 좋다" };
            var t = PlacementTaskText.Parse(raw.ToString());
            var it = t.Items.First(i => i.Key == "own");
            Assert.That(it.Points.Keys, Is.EqualTo(new[] { 1, 4, 7 }));
            Assert.That(it.AnchorAt(4), Is.EqualTo("좋지도 싫지도 않다"));
            Assert.That(it.AnchorLow, Is.EqualTo("매우 싫다"), "low가 없으면 숫자 1을 쓴다");
            Assert.That(it.AnchorHigh, Is.EqualTo("매우 좋다"));
            Assert.That(PlacementTaskText.ItemDisplay(it), Does.EndWith("1(매우 싫다) — 7(매우 좋다)"));

            foreach (var bad in new[] { "8", "0", "mid", "-1", "1.5" })
            {
                var b = (JObject)JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
                ((JObject)b["texts"]["own"]["anchors"])[bad] = "x";
                Assert.Throws<FormatException>(() => PlacementTaskText.Parse(b.ToString()), "anchors 키 " + bad);
            }
            var empty = (JObject)JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
            ((JObject)empty["texts"]["own"]["anchors"])["3"] = " ";
            Assert.Throws<FormatException>(() => PlacementTaskText.Parse(empty.ToString()), "빈 기준점 뜻");
            var instrWithWhen = (JObject)JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
            instrWithWhen["texts"]["items_instruction"] = new JObject { ["text"] = "x", ["status"] = "draft", ["source"] = "test", ["when"] = "pre" };
            Assert.Throws<FormatException>(() => PlacementTaskText.Parse(instrWithWhen.ToString()), "지시문 키에는 when 없음");
        }

        [Test]
        public void ScaleA_file_is_all_draft_with_draft_doc_sources_and_the_drafted_item_order()
        {
            Assert.That(File.Exists(ScaleAPath), Is.True);
            var t = PlacementTaskText.Load(ScaleAPath);
            Assert.That(t.Protocol, Is.EqualTo("placement-task"));
            Assert.That(t.DraftKeys.Count, Is.EqualTo(t.Count), "모든 문구 status draft");
            var A = Enumerable.Range(1, 7).Select(i => "A" + i).ToArray();
            Assert.That(t.ItemsFor("pre").Select(i => i.Key), Is.EqualTo(A.Concat(new[] { "S5", "S6", "S4", "S8", "M2", "P1", "distance_feel" })),
                "초안 3.7절 사전 순서(S1·S3 제외) + G59 구별 문항 M2·P1과 거리감(맨 끝)");
            Assert.That(t.ItemsFor("post").Select(i => i.Key), Is.EqualTo(A.Concat(new[] { "S5", "S6", "S7", "appearance_match", "representativeness", "M2", "P1", "distance_feel" })),
                "초안 3.7절 사후 순서 + 두 평정 문항(G13, 0.2에서 사후 끝에 더함) + G59 M2·P1·거리감(맨 끝)");
            Assert.That(t.ItemsFor("check").Select(i => i.Key), Is.EqualTo(new[] { "place_fit" }), "G59 자리 평정(이 파일에는 placed_by_me가 없다 — 조작 확인은 사후 S7). G60에서 want_move를 뺌");
            Assert.That(t.Items.Count, Is.EqualTo(18), "A 7문항 + S4–S8 5문항 + G13 2문항 + G59 4문항(G60에서 want_move를 뺌)");
            var p1 = t.Items.First(i => i.Key == "P1");
            Assert.That(p1.Text, Is.EqualTo("지금 나와 그 느낌의 관계는 어느 쪽에 더 가깝나요?"), "구별 프로파일 초안 3.1절 P1 문구(G66에서 대상을 '그 느낌'으로)");
            Assert.That(p1.Points.Keys, Is.EqualTo(new[] { 1, 4, 7 }), "P1 양극(가운데 점)");
            Assert.That((p1.AnchorAt(1), p1.AnchorAt(4), p1.AnchorAt(7)), Is.EqualTo(("그 느낌이 곧 나다", "반반이다", "그 느낌은 나에게 있는 것이지, 나 전체는 아니다")));
            Assert.That(t.Items.First(i => i.Key == "M2").Text, Is.EqualTo("지금 나는 나 자신을 그 느낌과는 별개로 경험한다."), "G66 대상 '그 느낌'. 구별 프로파일 초안 3.1절 M2 문구 그대로");
            foreach (var k in new[] { "M2", "P1" })
                Assert.That((string)JObject.Parse(File.ReadAllText(ScaleAPath, Encoding.UTF8))["texts"][k]["source"], Does.Contain("docs/rq-v4-differentiation-measure.md"), k + ": 출처 = 구별 프로파일 초안");
            var def = PlacementTests.LoadText();
            foreach (var k in new[] { "distance_feel", "place_fit" })
            {
                var a = t.Items.Single(i => i.Key == k);
                var b = def.Items.Single(i => i.Key == k);
                Assert.That((a.Text, a.AnchorLow, a.AnchorHigh, a.Min, a.Max), Is.EqualTo((b.Text, b.AnchorLow, b.AnchorHigh, b.Min, b.Max)), k + ": 기본 파일과 같은 문구·닻");
                Assert.That(a.When, Is.EqualTo(b.When), k);
            }
            foreach (var a in A)
            {
                var it = t.Items.First(i => i.Key == a);
                Assert.That(it.Points.Keys, Is.EqualTo(new[] { 1, 2, 3, 4, 5, 6, 7 }), a + ": 7점 모두 이름");
                Assert.That(it.AnchorAt(1), Is.EqualTo("전혀 그렇지 않다"));
                Assert.That(it.AnchorAt(4), Is.EqualTo("반반이다"));
                Assert.That(it.AnchorAt(7), Is.EqualTo("완전히 그렇다"));
            }
            var s8 = t.Items.First(i => i.Key == "S8");
            Assert.That(s8.Points.Keys, Is.EqualTo(new[] { 1, 4, 7 }), "S8 양극(가운데 점)");
            Assert.That(s8.AnchorAt(4), Is.EqualTo("좋지도 싫지도 않다"));
            Assert.That(t.InstructionFor("pre"), Does.StartWith("이제 문장 몇 개를 보여 드릴게요."));
            Assert.That(t.InstructionFor("post"), Does.Contain("\n앞에서 본 문장이 다시 나와요."), "사후 = 공통 + 사후 문장");
            Assert.That(t["condition_place"], Is.EqualTo(PlacementTests.LoadText()["condition_place"]), "단계 안내는 기본 파일과 같다");

            var raw = (JObject)JObject.Parse(File.ReadAllText(ScaleAPath, Encoding.UTF8))["texts"];
            foreach (var p in raw.Properties())
            {
                string src = (string)p.Value["source"];
                Assert.That(src, Does.Contain("IRB 검토 전"), p.Name);
                if (p.Name.StartsWith("A") || p.Name.StartsWith("S") || p.Name.StartsWith("items_instruction"))
                    Assert.That(src, Does.Contain("docs/rq-v4-questionnaire-draft.md"), p.Name + ": 출처 = 초안 문서");
                if (p.Name.Length == 2 && (p.Name[0] == 'A' || p.Name[0] == 'S')) Assert.That(src, Does.Contain(" " + p.Name), p.Name + ": 출처에 문항 ID");
                string all = (string)p.Value["text"] + " " + string.Join(" ", (p.Value["anchors"] as JObject)?.Properties().Select(a => (string)a.Value) ?? Enumerable.Empty<string>());
                foreach (var banned in new[] { "치료", "내담자", "진단", "환자", "증상", "내려놓", "치우", "멀어졌", "가벼워졌" })
                    Assert.That(all, Does.Not.Contain(banned), p.Name + ": 치료·방향 암시 표현 금지(원칙 8, 초안 3.0절)");
            }
            Assert.That(PlacementTaskText.ListTaskTextFiles(Application.streamingAssetsPath),
                Is.SupersetOf(new[] { PlacementTaskText.DefaultRelativePath, ScaleARelativePath }), "Setup 목록에 두 파일");
        }

        [Test]
        public void ScaleA_runs_end_to_end_with_instructions_before_items()
        {
            var t = PlacementTaskText.Load(ScaleAPath);
            var cfg = PlacementTests.ShortConfig("view");
            var auto = new PlacementAutoScript { CancelFirstRating = false };
            string dir;
            using (var s = NewSession(cfg, t))
            {
                bool sawInstruction = false;
                TickUntil(s, x => false, x =>
                {
                    if (x.ItemsInstructionActive)
                    {
                        sawInstruction = true;
                        Assert.That(x.CurrentItem, Is.Null, "지시문 동안에는 문항이 없다");
                        Assert.That(x.ParticipantText, Does.StartWith("이제 문장 몇 개를"));
                    }
                    return auto.Participant(x, 0.02);
                }, auto.Experimenter);
                Assert.That(s.Completed, Is.True);
                Assert.That(sawInstruction, Is.True);
                dir = s.RecordDirectory;
            }
            var ratings = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).Select(l => l.Split(',')).ToList();
            Assert.That(ratings.Count, Is.EqualTo(14 + 15 + 1), "사전 14 + 사후 15(G13 두 문항 포함, 기본 사후만) + 점검 1(G59 place_fit, G60에서 want_move를 뺌)");
            Assert.That(ratings.Where(r => r[1] == "pre").Select(r => r[0]).Last(), Is.EqualTo("distance_feel"));
            Assert.That(ratings.Where(r => r[1] == "post").Select(r => r[0]).Last(), Is.EqualTo("distance_feel"));
            Assert.That(ratings.Where(r => r[1] == "check").Select(r => r[0]), Is.EqualTo(new[] { "place_fit" }));
            Assert.That(ratings.Where(r => r[0] == "M2").All(r => int.Parse(r[2]) >= 0 && int.Parse(r[2]) <= 10), Is.True, "M2 0–10");
            var ev = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).ToList();
            Assert.That(ev.Count(l => l.Contains(",items_instruction,")), Is.EqualTo(3), "사전·사후·점검(G59로 점검 문항이 생겨 공통 지시문이 점검 앞에도 보임)");
            Assert.That(ev.Any(l => l.Contains("items_instruction,when=post;keys=items_instruction+items_instruction_post")), Is.True);
            var m = JObject.Parse(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((string)m["taskText"]["file"], Is.EqualTo("placement_task.scaleA.v0.json"));
            Assert.That((string)m["taskText"]["version"], Is.EqualTo("0.7-scaleA"), "G53 놓기 도움 문구를 더해 0.3, G57 문구 다듬기로 0.4, G59 문항으로 0.5, G60 want_move를 빼 0.6, G65·G66 문구로 0.7");
            Assert.That((int)m["taskText"]["draftCount"], Is.EqualTo(t.Count));
        }

        // ── 평정 동안 물체 숨기기 ────────────────────────────────────────
        [Test]
        public void HideObjectDuringItems_hides_the_object_only_in_item_phases()
        {
            foreach (bool hide in new[] { false, true })
            {
                var cfg = PlacementTests.ShortConfig("view");
                cfg.hideObjectDuringItems = hide;
                var auto = new PlacementAutoScript();
                var seen = new Dictionary<PlacementPhase, bool>();
                string dir;
                using (var s = NewSession(cfg))
                {
                    TickUntil(s, x => false, x =>
                    {
                        if (x.Phase == PlacementPhase.PreItems || x.Phase == PlacementPhase.PostItems || x.Phase == PlacementPhase.CheckItems
                            || x.Phase == PlacementPhase.Baseline || x.Phase == PlacementPhase.Condition)
                            seen[x.Phase] = (seen.TryGetValue(x.Phase, out var v) ? v : false) || x.ObjectVisible;
                        return auto.Participant(x, 0.02);
                    }, auto.Experimenter);
                    Assert.That(s.Completed, Is.True);
                    dir = s.RecordDirectory;
                }
                Assert.That(seen[PlacementPhase.PreItems], Is.EqualTo(!hide), "사전 평정");
                Assert.That(seen[PlacementPhase.PostItems], Is.EqualTo(!hide), "사후 평정");
                Assert.That(seen[PlacementPhase.CheckItems], Is.EqualTo(!hide), "점검 평정");
                Assert.That(seen[PlacementPhase.Baseline], Is.True, "제시 단계는 늘 보임");
                Assert.That(seen[PlacementPhase.Condition], Is.True, "조건 단계는 늘 보임");
                var obj = File.ReadAllLines(Path.Combine(dir, "objpose.csv")).Skip(1).Select(l => l.Split(',')[1]).Distinct().ToList();
                Assert.That(obj.Contains("pre_items"), Is.EqualTo(!hide), "숨기면 objpose에 평정 단계 행이 없다");
                var m = JObject.Parse(File.ReadAllText(Path.Combine(dir, "manifest.json")));
                Assert.That((bool)m["config"]["hideObjectDuringItems"], Is.EqualTo(hide), "manifest config에 남는다");
            }
        }

        // ── 참여자 컨트롤러 평정(선택) ──────────────────────────────────
        [Test]
        public void Participant_controller_rating_steps_from_the_middle_and_records_on_trigger()
        {
            foreach (bool on in new[] { true, false })
            {
                var cfg = PlacementTests.ShortConfig("view");
                cfg.participantRatesWithController = on;
                using (var s = NewSession(cfg))
                {
                    var logic = new XrPlacementInputLogic();
                    TickUntil(s, x => x.Phase == PlacementPhase.PreItems, x => new PlacementInputFrame(), ExperimenterNextOnly);
                    Assert.That(s.CurrentItem?.Key, Is.EqualTo("own"));
                    Assert.That(s.RatingCursor, Is.Null, "처음에는 고른 값이 없다");
                    var plan = new[] { Pad(x: 0.9), Pad(), Pad(x: 0.9), Pad(), Pad(x: 0.9), Pad(), Pad(x: -0.9), Pad(), Pad(trigger: 1.0), Pad() };
                    var cursors = new List<int?>();
                    foreach (var p in plan)
                    {
                        if (s.Phase != PlacementPhase.PreItems) break;
                        s.Tick(0.1, logic.Step(p, true), HeadPose.At(0, 1.6, 0));
                        cursors.Add(s.RatingCursor);
                    }
                    if (on)
                    {
                        Assert.That(cursors.Take(8), Is.EqualTo(new int?[] { 4, 4, 5, 5, 6, 6, 5, 5 }), "처음 젖히면 가운데(4), 그다음 한 칸씩");
                        Assert.That(s.CurrentItem?.Key, Is.EqualTo("distance_feel"), "트리거로 확정 → 다음 문항(사전 둘째 = G59 거리감)");
                    }
                    else
                    {
                        Assert.That(cursors.All(c => c == null), Is.True, "기본(꺼짐)에서는 컨트롤러 평정을 받지 않는다");
                        Assert.That(s.Phase, Is.EqualTo(PlacementPhase.PreItems));
                        s.PressDigit(3);
                        s.PressConfirm();
                    }
                    string dir = s.RecordDirectory;
                    s.Abort();
                    var rows = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).Select(l => l.Split(',')).ToList();
                    Assert.That(rows.Count, Is.EqualTo(1));
                    Assert.That(rows[0][0], Is.EqualTo("own"));
                    Assert.That(rows[0][2], Is.EqualTo(on ? "5" : "3"));
                    var ev = File.ReadAllLines(Path.Combine(dir, "events.csv")).Where(l => l.Contains(",rating,")).ToList();
                    Assert.That(ev.Count, Is.EqualTo(1));
                    if (on) Assert.That(ev[0], Does.EndWith(";by=controller"), "참여자가 확정한 평정은 events에 표시");
                    else Assert.That(ev[0], Does.Not.Contain("by="), "실험자 입력은 예전 형식 그대로");
                }
            }
        }

        [Test]
        public void Participant_trigger_does_not_override_a_digit_the_experimenter_already_entered()
        {
            var cfg = PlacementTests.ShortConfig("view");
            cfg.participantRatesWithController = true;
            using (var s = NewSession(cfg))
            {
                var logic = new XrPlacementInputLogic();
                TickUntil(s, x => x.Phase == PlacementPhase.PreItems, x => new PlacementInputFrame(), ExperimenterNextOnly);
                s.PressDigit(2);
                s.Tick(0.1, logic.Step(Pad(x: 0.9), true), HeadPose.At(0, 1.6, 0));
                s.Tick(0.1, logic.Step(Pad(trigger: 1.0), true), HeadPose.At(0, 1.6, 0));
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.PreItems), "실험자 입력(확정 전)이 있으면 참여자 트리거는 무시");
                Assert.That(s.PendingRating, Is.EqualTo(2));
                s.PressConfirm();
                Assert.That(s.CurrentItem?.Key, Is.EqualTo("distance_feel"), "실험자 확정 → 다음 문항(G59 거리감)");
                s.Abort();
            }
        }

        [Test]
        public void Runner_note_records_recenter_events_until_the_session_ends()
        {
            using (var s = NewSession(PlacementTests.ShortConfig("view")))
            {
                s.Note("recenter", "yaw_deg=12.0;offset_x=0.100;offset_z=-0.050;head_height_m=1.620;origin=Floor");
                string dir = s.RecordDirectory;
                s.Abort();
                s.Note("recenter", "after end");   // 끝난 뒤에는 무시
                var ev = File.ReadAllLines(Path.Combine(dir, "events.csv")).Where(l => l.Contains(",recenter,")).ToList();
                Assert.That(ev.Count, Is.EqualTo(1));
                Assert.That(ev[0], Does.Contain("yaw_deg=12.0"));
            }
        }
    }
}
