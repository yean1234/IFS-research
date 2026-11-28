// EditMode 테스트: 헤드셋 UI 개선(G63, 2026-11-27 — research_notes/VR UI 가독성 기준/vr_ui_guidelines.md). UnityEngine 없이 돈다(dotnet compile-check에서도).
//   · 플래그가 모두 꺼져 있으면(기본) 설정 JSON·events·ratings가 G63 전과 같다(새 키·새 사건 없음, 기본 수치 그대로).
//   · 켜면 각 값이 기준을 충족한다: 판 아래 가장자리 ≤ 35°(긴 안내 판, 지시문 쪽 나누기), 어두운 판 대비 7–15:1(약 11:1),
//     7칸 평정 줄 폭 ≤ 41°, 햅틱은 두 조건 공통 사건에서 같은 펄스, 확정 표시는 rt_ms에 들어가지 않음, 판 숨김은 묶음에 들지 않음.
// 문구는 저장소의 문구 파일(scaleA — IRB 대상 문구를 읽기만, 글자는 바꾸지 않는다)과 합성 입력만 쓴다.
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
    public class PlacementUiG63Tests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-ui-g63-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static PlacementTaskText ScaleA() => PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementXrTests.ScaleARelativePath));

        static readonly string[] NewEvents = { "haptic", "items_instruction_page", "rating_confirm_flash", "panel_hidden" };
        static readonly string[] UiKeys = { "uiComfortWrap", "uiDarkPanel", "uiRayHover", "uiHaptics", "uiRatingConfirmFlash", "uiNarrowScale", "hidePanelInDistancePhases" };

        // G63 전 기본 설정의 config 키(순서까지). 기본값에서 키가 하나라도 늘면 기존 기록과 바이트가 달라진다.
        static readonly string[] PreG63DefaultConfigKeys =
        {
            "condition", "controlMode", "floorRadiusM", "ringRadiiM", "showRings", "startDistanceM", "startHeightM", "baselineSeconds", "conditionSeconds",
            "conditionEndsOnConfirm", "headSampleHz", "pushPullSpeedMps", "holdMinM", "holdMaxM", "grabRadiusMinM", "minHeightM", "maxHeightM",
            "systemMoveTargetDistanceM", "systemMoveTargetAzimuthDeg", "systemMoveTargetHeightM", "systemMoveSpeedMps", "systemMoveDelaySeconds", "replayFile",
            "stopSpeedMps", "stopApproachStartM", "stopRecedeStartM", "stopTrialsPerDirection", "stopPracticeTrials", "stopMinM", "stopMaxM", "stopItiSeconds",
            "stopHeightM", "stopFirstDirection", "requireSpecPhrases", "inputMode", "xrHand", "participantRatesWithController", "hideObjectDuringItems",
            "askOptionalItems", "disabledItems",
        };

        // ── 설정 ─────────────────────────────────────────────────────────
        [Test]
        public void Flags_are_off_by_default_and_default_config_json_has_no_new_keys()
        {
            var cfg = new PlacementConfig();
            Assert.That(cfg.UsesUiOptions, Is.False);
            Assert.That(cfg.UiBundleOn, Is.False);
            Assert.That(cfg.ToJson().Properties().Select(p => p.Name), Is.EqualTo(PreG63DefaultConfigKeys), "기본 config 키는 G63 전과 같다");
            Assert.That(cfg.Validate(), Is.Empty);
        }

        [Test]
        public void Bundle_turns_on_six_flags_but_not_the_panel_hiding_flag_and_records_keys_at_the_end()
        {
            var cfg = new PlacementConfig();
            cfg.ApplyUiBundle();
            Assert.That(cfg.UiBundleOn, Is.True);
            Assert.That(new[] { cfg.uiComfortWrap, cfg.uiDarkPanel, cfg.uiRayHover, cfg.uiHaptics, cfg.uiRatingConfirmFlash, cfg.uiNarrowScale }, Is.All.True);
            Assert.That(cfg.hidePanelInDistancePhases, Is.False, "(7)은 RQ2에 닿아 묶음에서 빠진다(연구자 결정)");
            var names = cfg.ToJson().Properties().Select(p => p.Name).ToList();
            Assert.That(names.Take(PreG63DefaultConfigKeys.Length), Is.EqualTo(PreG63DefaultConfigKeys), "기존 키·순서는 그대로");
            Assert.That(names.Skip(PreG63DefaultConfigKeys.Length), Is.EqualTo(UiKeys), "새 키는 맨 끝에만");
            Assert.That(cfg.Clone().UiBundleOn, Is.True);

            var hide = new PlacementConfig { hidePanelInDistancePhases = true, hidePanelReadSeconds = 5 };
            Assert.That(hide.UsesUiOptions, Is.True);
            Assert.That((double)hide.ToJson()["hidePanelReadSeconds"], Is.EqualTo(5));
            Assert.That(new PlacementConfig { hidePanelInDistancePhases = true, hidePanelReadSeconds = 0 }.Validate().Any(e => e.StartsWith("hidePanelReadSeconds")), Is.True);
            Assert.That(new PlacementConfig { hidePanelReadSeconds = 0 }.Validate(), Is.Empty, "플래그가 꺼져 있으면 읽을 시간은 검사하지 않는다");
        }

        [Test]
        public void Command_line_bundle_and_single_flags()
        {
            var cfg = IFS.SceneSpec.EditorTools.PlacementExperimentMenu.ConfigFromArgs(new[] { "x", "-uiBundle", "true", "-uiHaptics", "false" });
            Assert.That(cfg.uiComfortWrap && cfg.uiDarkPanel && cfg.uiRayHover && cfg.uiRatingConfirmFlash && cfg.uiNarrowScale, Is.True);
            Assert.That(cfg.uiHaptics, Is.False, "낱개 플래그가 묶음을 덮어쓴다");
            Assert.That(cfg.hidePanelInDistancePhases, Is.False);
            Assert.That(IFS.SceneSpec.EditorTools.PlacementExperimentMenu.ConfigFromArgs(new[] { "x" }).UsesUiOptions, Is.False);
        }

        // ── (1) 판 아래 가장자리 ─────────────────────────────────────────
        [Test]
        public void Wrap_line_count_matches_participant_text_display_wrap()
        {
            var t = ScaleA();
            foreach (var key in t.Keys)
                foreach (int w in new[] { 6, 20, 24, 26 })
                    Assert.That(PlacementPanelMetrics.WrapLineCount(t[key], w), Is.EqualTo(IFS.SceneSpec.Ownership.ParticipantTextDisplay.Wrap(t[key], w).Split('\n').Length), key + " " + w);
        }

        [Test]
        public void Panel_placement_matches_the_panel_rule_and_documents_the_default_problem()
        {
            // 짧은 판은 받은 중심(0.6 m) 그대로, 키가 큰 판은 위 가장자리 0.85 m에 맞춰 내려간다
            var shortPanel = PlacementPanelMetrics.PanelPlacement(PlacementPanelMetrics.BodyPanelHeightM(2));
            Assert.That(shortPanel.centerY, Is.EqualTo(0.6).Within(1e-9));
            var tall = PlacementPanelMetrics.PanelPlacement(PlacementPanelMetrics.BodyPanelHeightM(8));
            Assert.That(tall.topY, Is.EqualTo(0.85).Within(0.01), "위 가장자리는 maxTopM 근처");
            Assert.That(tall.centerY, Is.LessThan(0.6));
            // 기본값(20자): 평정 지시문이 8줄(G65·G66 문구로 9줄)이라 아래 가장자리가 35°를 넘는다(조사 문서 2절의 문제)
            var t = ScaleA();
            int lines = PlacementPanelMetrics.WrapLineCount(t.InstructionFor(PlacementTaskText.WhenPre), PlacementPanelMetrics.DefaultWrapChars);
            Assert.That(lines, Is.EqualTo(9), "scaleA 0.7-scaleA 지시문 173자");
            Assert.That(PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(lines)), Is.GreaterThan(35));
            Assert.That(PlacementPanelMetrics.MaxBodyLinesWithin(), Is.EqualTo(5), "기본 자리에서 35° 안에 드는 본문 줄 수");
            TestContext.WriteLine($"기본 8줄 판 아래 {PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(8)):0.00}°, 5줄 {PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(5)):0.00}°");
        }

        [Test]
        public void Sentence_pages_keep_every_character_and_fit_within_35_degrees()
        {
            var t = ScaleA();
            int max = PlacementPanelMetrics.MaxBodyLinesWithin();
            foreach (var when in new[] { PlacementTaskText.WhenPre, PlacementTaskText.WhenPost, PlacementTaskText.WhenCheck })
            {
                string text = t.InstructionFor(when);
                if (text == null) continue;
                var pages = PlacementPanelMetrics.SentencePages(text, PlacementPanelMetrics.ComfortWrapChars, max);
                Assert.That(pages.Count, Is.GreaterThan(1), when + ": 긴 지시문은 나뉜다");
                // 다시 이으면 원문 그대로(쪽 경계의 구분자 ' ' 또는 '\n' 하나만 빠진다)
                string rejoined = pages[0];
                int pos = pages[0].Length;
                for (int i = 1; i < pages.Count; i++)
                {
                    char sep = text[pos];
                    Assert.That(sep == ' ' || sep == '\n', Is.True, "쪽은 문장 경계에서만 나뉜다");
                    Assert.That(text[pos - 1] == '.' || text[pos - 1] == '?' || text[pos - 1] == '!' || sep == '\n', Is.True);
                    rejoined += sep + pages[i];
                    pos += 1 + pages[i].Length;
                }
                Assert.That(rejoined, Is.EqualTo(text), when + ": 글자는 그대로");
                foreach (var p in pages)
                {
                    int n = PlacementPanelMetrics.WrapLineCount(p, PlacementPanelMetrics.ComfortWrapChars);
                    double deg = PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(n));
                    Assert.That(deg, Is.LessThanOrEqualTo(35.0), $"{when} 쪽 '{p.Substring(0, Math.Min(10, p.Length))}…' {n}줄");
                    TestContext.WriteLine($"{when} page {n} lines, bottom {deg:0.00}°");
                }
            }
            Assert.That(PlacementPanelMetrics.SentencePages("짧은 글. 둘째.", 24, 5), Is.EqualTo(new[] { "짧은 글. 둘째." }), "들어가면 나누지 않는다");
        }

        /// <summary>판에 보이는 안내 글(평정 지시문 제외 — 그것은 쪽을 나눈다). 키 조합은 세션이 붙이는 그대로.</summary>
        static IEnumerable<(string name, string text)> PanelTexts(PlacementTaskText t)
        {
            foreach (var k in new[] { "intro", "baseline", "condition_place", "condition_view", "condition_point_select", "wait", "stop_distance",
                                      PlacementTaskText.StopLoopKey, PlacementTaskText.PracticeKey, "done" })
                if (t.Keys.Contains(k)) yield return (k, t[k]);
            yield return ("condition_place+placement_range", t["condition_place"] + "\n" + t[PlacementTaskText.PlacementRangeKey]);
            yield return ("stop_distance_loop+stop_loop_hint", t[PlacementTaskText.StopLoopKey] + "\n" + t[PlacementTaskText.StopLoopHintKey]);
            // 2026-11-28: 확인 버튼 안내를 붙인 조합(세션이 붙이는 그대로 — 오른손 기준, 왼손 문구는 글자 수가 같다)
            string b = " " + t[PlacementTaskText.ConfirmButtonRightKey];   // 마지막 문단에 한 칸 띄워 잇는다(세션과 같게)
            yield return ("practice+confirm_button_right", t[PlacementTaskText.PracticeKey] + b);
            yield return ("condition_place+placement_range+confirm_button_right", t["condition_place"] + "\n" + t[PlacementTaskText.PlacementRangeKey] + b);
            yield return ("condition_point_select+confirm_button_right", t["condition_point_select"] + b);
            yield return ("stop_distance_loop+stop_loop_hint+confirm_button_right", t[PlacementTaskText.StopLoopKey] + "\n" + t[PlacementTaskText.StopLoopHintKey] + b);
            yield return ("confirm_done+stop_main_start", t[PlacementTaskText.ConfirmDoneKey] + "\n" + t[PlacementTaskText.StopMainStartKey]);
        }

        /// <summary>판의 넓혀 보기 규칙(PlacementTextPanel.ShowText와 같다): 24자, 넘치면 26자까지 줄 수가 줄어드는 가장 좁은 폭, 그래도 넘치면 24자.</summary>
        static (int wrap, int lines, double deg) ComfortLayout(string text)
        {
            int w0 = PlacementPanelMetrics.ComfortWrapChars;
            double Deg(int n) => PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(n));
            int n0 = PlacementPanelMetrics.WrapLineCount(text, w0);
            if (Deg(n0) <= PlacementPanelMetrics.ComfortBottomLimitDeg) return (w0, n0, Deg(n0));
            for (int w = w0 + 1; w <= PlacementPanelMetrics.ComfortWrapMaxChars; w++)
            {
                int n = PlacementPanelMetrics.WrapLineCount(text, w);
                if (n < n0 && Deg(n) <= PlacementPanelMetrics.ComfortBottomLimitDeg) return (w, n, Deg(n));
            }
            return (w0, n0, Deg(n0));
        }

        [Test]
        public void Comfort_layout_keeps_instruction_panels_within_35_degrees_except_the_paused_stop_loop_panel()
        {
            var t = ScaleA();
            foreach (var (name, text) in PanelTexts(t))
            {
                int before = PlacementPanelMetrics.WrapLineCount(text, PlacementPanelMetrics.DefaultWrapChars);
                double degBefore = PlacementPanelMetrics.BottomBelowHorizonDeg(PlacementPanelMetrics.BodyPanelHeightM(before));
                var (wrap, lines, deg) = ComfortLayout(text);
                TestContext.WriteLine($"{name}: 20자 {before}줄 {degBefore:0.00}° → {wrap}자 {lines}줄 {deg:0.00}°");
                Assert.That(deg, Is.LessThanOrEqualTo(degBefore + 1e-9), name + ": 나빠지지 않는다");
                if (name == "stop_distance_loop+stop_loop_hint" || name == "stop_distance_loop+stop_loop_hint+confirm_button_right")
                {
                    // 알려진 예외: 반복 멈춤에서 멈춘 동안(본 지시문 5줄 + 조작 안내 2줄 = 7줄). 쪽을 넘길 입력이 없어 나누지 못한다 — 보고(사람이 정할 것)
                    Assert.That(deg, Is.GreaterThan(35.0));
                    continue;
                }
                Assert.That(deg, Is.LessThanOrEqualTo(35.0), name);
                Assert.That(wrap, Is.LessThanOrEqualTo(PlacementPanelMetrics.ComfortWrapMaxChars));
            }
        }

        // ── (2) 어두운 판 대비 ───────────────────────────────────────────
        [Test]
        public void Dark_panel_contrast_is_about_11_to_1_and_selected_cell_stays_readable()
        {
            double body = PlacementPanelMetrics.ContrastRatio(PlacementPanelMetrics.DarkTextSrgb, PlacementPanelMetrics.DarkBackgroundSrgb);
            Assert.That(body, Is.InRange(PlacementPanelMetrics.DarkContrastMin, PlacementPanelMetrics.DarkContrastMax));
            Assert.That(body, Is.EqualTo(11.2).Within(0.3), "조사 문서 안 A: 약 11:1");
            double selOnFill = PlacementPanelMetrics.ContrastRatio(PlacementPanelMetrics.DarkHighlightSrgb, PlacementPanelMetrics.DarkSelectionFillSrgb);
            double selOnPanel = PlacementPanelMetrics.ContrastRatio(PlacementPanelMetrics.DarkHighlightSrgb, PlacementPanelMetrics.DarkBackgroundSrgb);
            Assert.That(selOnFill, Is.GreaterThanOrEqualTo(4.5), "고른 칸 글 / 칸 바탕");
            Assert.That(selOnPanel, Is.GreaterThanOrEqualTo(4.5), "고른 칸 글·테두리 / 판");
            Assert.That(PlacementPanelMetrics.ContrastRatio(PlacementPanelMetrics.DarkTextSrgb, PlacementPanelMetrics.DarkSelectionFillSrgb), Is.GreaterThanOrEqualTo(4.5));
            // 고른 칸 바탕은 판과 구별된다(색만이 아니라 테두리도 있지만, 면으로도 보이게)
            Assert.That(PlacementPanelMetrics.RelativeLuminance(PlacementPanelMetrics.DarkSelectionFillSrgb), Is.GreaterThan(PlacementPanelMetrics.RelativeLuminance(PlacementPanelMetrics.DarkBackgroundSrgb)));
            // 기본(흰 판)은 그대로 — 재질 색은 14.6:1이지만 방출 0.6 때문에 렌더 화소는 #16161C 대 #FFFFFF = 18:1(docs/validation/ui 실측).
            // 렌더 대비가 상한 15:1을 넘는 것이 조사 문서의 지적이다
            double lightMaterial = PlacementPanelMetrics.ContrastRatio(PlacementPanelMetrics.TextSrgb, PlacementPanelMetrics.BackgroundSrgb);
            double lightRendered = PlacementPanelMetrics.ContrastRatio(new[] { 0x16 / 255.0, 0x16 / 255.0, 0x1C / 255.0 }, new[] { 1.0, 1.0, 1.0 });
            Assert.That(lightRendered, Is.GreaterThan(PlacementPanelMetrics.DarkContrastMax));
            TestContext.WriteLine($"dark body {body:0.00}:1, selected/fill {selOnFill:0.00}:1, selected/panel {selOnPanel:0.00}:1, " +
                                  $"light(default) 재질 색 {lightMaterial:0.00}:1 · 렌더 {lightRendered:0.00}:1");
        }

        // ── (6) 평정 줄 폭 ───────────────────────────────────────────────
        [Test]
        public void Narrow_scale_row_fits_within_41_degrees_and_default_does_not()
        {
            double wide = PlacementPanelMetrics.PanelWidthDeg(PlacementPanelMetrics.ScaleRowPanelWidthM(7, PlacementPanelMetrics.DefaultColumnWidthM));
            double narrow = PlacementPanelMetrics.PanelWidthDeg(PlacementPanelMetrics.ScaleRowPanelWidthM(7, PlacementPanelMetrics.NarrowColumnWidthM));
            Assert.That(wide, Is.GreaterThan(PlacementPanelMetrics.MainContentWidthLimitDeg), "기본 0.22 m: 41.6°");
            Assert.That(narrow, Is.LessThanOrEqualTo(PlacementPanelMetrics.MainContentWidthLimitDeg));
            Assert.That(PlacementPanelMetrics.PanelWidthDeg(PlacementPanelMetrics.ScaleRowPanelWidthM(11, PlacementPanelMetrics.NarrowColumnWidthM)), Is.EqualTo(narrow).Within(1e-9), "0–10(11칸)도 7칸 너비로 좁힌다(예전 규칙)");
            // 기준점 뜻 줄바꿈: 칸이 좁아지면 한 줄 글자 수가 4 → 3
            double labelEm = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.LabelCharacterSize, PlacementPanelMetrics.FontSize);
            Assert.That(PlacementPanelMetrics.LabelWrapChars(PlacementPanelMetrics.DefaultColumnWidthM, labelEm), Is.EqualTo(4));
            Assert.That(PlacementPanelMetrics.LabelWrapChars(PlacementPanelMetrics.NarrowColumnWidthM, labelEm), Is.EqualTo(3));
            TestContext.WriteLine($"7칸 줄 폭 0.22 m {wide:0.0}° → 0.20 m {narrow:0.0}°");
        }

        // ── (3) 광선 상태 · (4) 햅틱 값 ──────────────────────────────────
        [Test]
        public void Ray_state_changes_only_ray_and_end_point_and_is_idle_when_flag_is_off()
        {
            var o = new PVec3(0, 1.2, 0);
            var obj = new PVec3(0, 1.2, 1.5);
            var toObj = new PVec3(0, 0, 1);
            var away = new PVec3(1, 0, 0);
            Assert.That(XrRayStyle.State(false, o, toObj, true, obj, true, 0.15), Is.EqualTo(XrRayState.Idle), "꺼져 있으면 늘 기본");
            Assert.That(XrRayStyle.State(true, o, toObj, false, obj, true, 0.15), Is.EqualTo(XrRayState.Hover));
            Assert.That(XrRayStyle.State(true, o, away, false, obj, true, 0.15), Is.EqualTo(XrRayState.Idle));
            Assert.That(XrRayStyle.State(true, o, toObj, false, obj, false, 0.15), Is.EqualTo(XrRayState.Idle), "숨긴 물체는 겨누지 않는다");
            Assert.That(XrRayStyle.State(true, o, away, true, obj, true, 0.15), Is.EqualTo(XrRayState.Held));
            Assert.That(XrRayStyle.State(true, o, new PVec3(0, 0, -1), false, obj, true, 0.15), Is.EqualTo(XrRayState.Idle), "뒤쪽은 아님");
            Assert.That(XrRayStyle.WidthM(XrRayState.Idle, 0.004), Is.EqualTo(0.004));
            Assert.That(XrRayStyle.EndDiameterM(XrRayState.Idle, 0.03), Is.EqualTo(0.03), "기본 상태는 Inspector 값 그대로");
            Assert.That(XrRayStyle.EndDiameterM(XrRayState.Hover, 0.03), Is.EqualTo(0.045));
            Assert.That(XrRayStyle.WidthM(XrRayState.Held, 0.004), Is.EqualTo(0.006));
        }

        [Test]
        public void Haptic_pulses_follow_the_proposed_values()
        {
            Assert.That(PlacementHaptics.For(PlacementHaptics.Grab).EventDetail(), Is.EqualTo("kind=grab;amplitude=0.30;duration_ms=20"));
            Assert.That(PlacementHaptics.For(PlacementHaptics.Release).DurationMs, Is.EqualTo(20));
            Assert.That(PlacementHaptics.For(PlacementHaptics.RateStep).EventDetail(), Is.EqualTo("kind=rate_step;amplitude=0.20;duration_ms=10"));
            foreach (var k in new[] { PlacementHaptics.Confirm, PlacementHaptics.RateConfirm, PlacementHaptics.Stop, PlacementHaptics.Resume })
            {
                Assert.That(PlacementHaptics.For(k).Amplitude, Is.EqualTo(0.5), k);
                Assert.That(PlacementHaptics.For(k).DurationMs, Is.EqualTo(40), k);
            }
        }

        // ── 회기 ─────────────────────────────────────────────────────────
        sealed class RunResult
        {
            public string Dir;
            public List<string[]> Events;
            public List<string> Ratings;
            public JObject Manifest;
            public int MaxInstructionPages;
            public bool SawFlash, SawHidden;
        }

        /// <summary>scaleA 문구 파일로 끝까지 돈다. 평정은 참여자 컨트롤러(문항이 보인 뒤 0.3 s·0.5 s에 오른쪽 한 칸, 0.8 s에 확정),
        /// 그 밖의 참여자 입력과 실험자 키는 자동 스크립트.</summary>
        RunResult Run(PlacementConfig cfg, int participant = 1)
        {
            var text = ScaleA();
            cfg.participantRatesWithController = true;
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = participant, SessionId = "SYN-G63", SpecFile = "synthetic.json", SpecSha256 = "00",
                StartedUtc = new DateTime(2026, 11, 27, 1, 2, 3, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = "placement_task.scaleA.v0.json", TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeys.ToArray(),
            };
            var script = new PlacementAutoScript();
            var r = new RunResult();
            using (var s = new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records", Guid.NewGuid().ToString("N"))))
            {
                string itemTag = null;
                double itemStart = 0, lastPress = -1;
                const double dt = 0.02;
                for (int i = 0; i < 400000 && !s.Finished; i++)
                {
                    var head = PlacementAutoScript.ScriptedHead(s.Now);
                    var f = script.Participant(s, dt);
                    bool items = s.Phase == PlacementPhase.PreItems || s.Phase == PlacementPhase.PostItems || s.Phase == PlacementPhase.CheckItems;
                    if (items)
                    {
                        f.RateStep = 0;
                        f.RateSubmitDown = false;
                        string tag = s.CurrentItem != null ? s.PhaseLabel + "/" + s.ItemNumber + "/" + s.RatingConfirmFlash : null;
                        if (tag != itemTag) { itemTag = tag; itemStart = s.Now; }
                        if (s.CurrentItem != null && !s.RatingConfirmFlash)
                        {
                            double e = s.Now - itemStart;
                            if (Math.Abs(e - 0.3) < dt / 2 || Math.Abs(e - 0.5) < dt / 2) f.RateStep = 1;
                            if (Math.Abs(e - 0.8) < dt / 2) f.RateSubmitDown = true;
                        }
                    }
                    s.Tick(dt, f, head);
                    r.SawFlash |= s.RatingConfirmFlash;
                    r.SawHidden |= s.PanelHidden;
                    r.MaxInstructionPages = Math.Max(r.MaxInstructionPages, s.InstructionPageCount);
                    bool itemsNow = s.Phase == PlacementPhase.PreItems || s.Phase == PlacementPhase.PostItems || s.Phase == PlacementPhase.CheckItems;
                    if (itemsNow)
                    {
                        if (s.ItemsInstructionActive && s.Now - lastPress >= 0.5) { s.PressNext(); lastPress = s.Now; }
                    }
                    else script.Experimenter(s);
                }
                Assert.That(s.Finished && s.Completed, Is.True, "끝까지 돌았다");
                r.Dir = s.RecordDirectory;
            }
            r.Events = File.ReadAllLines(Path.Combine(r.Dir, "events.csv")).Skip(1).Select(l => l.Split(new[] { ',' }, 3)).ToList();
            r.Ratings = File.ReadAllLines(Path.Combine(r.Dir, "ratings.csv")).ToList();
            r.Manifest = JObject.Parse(File.ReadAllText(Path.Combine(r.Dir, PlacementRecordWriter.ManifestFile)));
            return r;
        }

        static PlacementConfig Short(string condition)
        {
            var c = PlacementTests.ShortConfig(condition);
            return c;
        }

        [Test]
        public void Flags_off_runs_have_no_new_events_or_keys_in_both_conditions()
        {
            foreach (var cond in PlacementConfig.Conditions)
            {
                var r = Run(Short(cond));
                Assert.That(r.Events.Select(e => e[1]).Intersect(NewEvents), Is.Empty, cond + ": 새 사건 없음");
                var cfgKeys = ((JObject)r.Manifest["config"]).Properties().Select(p => p.Name).ToList();
                Assert.That(cfgKeys.Intersect(UiKeys), Is.Empty, cond);
                Assert.That(r.SawFlash || r.SawHidden || r.MaxInstructionPages > 0, Is.False);
                Assert.That(r.Ratings.Count, Is.GreaterThan(1));
            }
        }

        [Test]
        public void Bundle_pages_instructions_flashes_confirm_without_touching_ratings_and_haptics_match_across_conditions()
        {
            var off = Run(Short(PlacementConfig.ConditionPlace));
            var cfgPlace = Short(PlacementConfig.ConditionPlace);
            cfgPlace.ApplyUiBundle();
            var place = Run(cfgPlace);
            var cfgView = Short(PlacementConfig.ConditionView);
            cfgView.ApplyUiBundle();
            var view = Run(cfgView);

            // ratings.csv(값·rt_ms)는 확정 표시를 켜도 같다 — 0.4 s는 rt에 들어가지 않는다
            Assert.That(place.Ratings, Is.EqualTo(off.Ratings), "평정 값·rt_ms 그대로");
            Assert.That(place.SawFlash, Is.True);
            var flashes = place.Events.Where(e => e[1] == "rating_confirm_flash").ToList();
            Assert.That(flashes.Count, Is.EqualTo(off.Ratings.Count - 1), "확정마다 한 번");
            Assert.That(flashes.All(e => e[2].EndsWith(";duration_ms=400")), Is.True);

            // (1) 지시문 쪽 나누기: 사전·사후 지시문이 여러 쪽, 쪽 사건은 실험자 Enter마다
            Assert.That(place.MaxInstructionPages, Is.GreaterThan(1));
            var pages = place.Events.Where(e => e[1] == "items_instruction_page").Select(e => e[2]).ToList();
            Assert.That(pages, Does.Contain("when=pre;page=1;pages=2").And.Contain("when=pre;page=2;pages=2"));
            Assert.That(pages.Any(p => p.StartsWith("when=post;page=1;pages=")), Is.True);

            // (4) 햅틱: 두 조건 공통 사건(평정 한 칸·평정 확정·멈춤)의 펄스가 같다. 잡기·놓기·확인은 직접 배치에만
            string[] common = { PlacementHaptics.RateStep, PlacementHaptics.RateConfirm, PlacementHaptics.Stop, PlacementHaptics.Resume };
            List<string> Haptics(RunResult r, bool commonOnly) => r.Events.Where(e => e[1] == "haptic")
                .Select(e => e[2]).Where(d => !commonOnly || common.Any(k => d.StartsWith("kind=" + k + ";"))).ToList();
            Assert.That(Haptics(place, true), Is.EqualTo(Haptics(view, true)), "공통 사건 펄스는 조건과 상관없이 같다");
            Assert.That(Haptics(place, true).Count(d => d.StartsWith("kind=rate_confirm;")), Is.EqualTo(off.Ratings.Count - 1));
            Assert.That(Haptics(place, true).Count(d => d.StartsWith("kind=stop;")), Is.EqualTo(place.Events.Count(e => e[1] == "stop_press")));
            Assert.That(Haptics(view, false).Any(d => d.StartsWith("kind=grab;") || d.StartsWith("kind=confirm;")), Is.False, "보기만(정지)에는 잡기·확인이 없다");
            Assert.That(Haptics(place, false).Count(d => d.StartsWith("kind=grab;")), Is.EqualTo(place.Events.Count(e => e[1] == "grab")));
            Assert.That(Haptics(place, false).Count(d => d.StartsWith("kind=confirm;")), Is.EqualTo(place.Events.Count(e => e[1] == "confirm")));

            // 기존 사건은 그대로: 새 사건을 빼면 사건 종류의 순서가 꺼진 회기와 같다
            List<string> Kinds(RunResult r) => r.Events.Select(e => e[1]).Where(k => !NewEvents.Contains(k)).ToList();
            Assert.That(Kinds(place), Is.EqualTo(Kinds(off)));
            Assert.That(place.SawHidden, Is.False, "판 숨김은 묶음에 들지 않는다");
            Assert.That((bool)place.Manifest["config"]["uiComfortWrap"], Is.True);
            Assert.That((bool)place.Manifest["config"]["hidePanelInDistancePhases"], Is.False);
        }

        [Test]
        public void Experimenter_keys_are_ignored_during_the_confirm_flash()
        {
            var cfg = Short(PlacementConfig.ConditionView);
            cfg.uiRatingConfirmFlash = true;
            cfg.participantRatesWithController = true;
            var text = ScaleA();
            using (var s = new PlacementSession(cfg, text, new PlacementSessionInfo { SessionId = "SYN-FLASH", ParticipantNumber = 1 }, Path.Combine(_tmp, "r")))
            {
                var none = new PlacementInputFrame();
                var head = HeadPose.At(0, 1.6, 0);
                s.PressNext();   // intro → baseline
                for (int i = 0; i < 200 && s.Phase != PlacementPhase.PreItems; i++) s.Tick(0.02, none, head);
                while (s.ItemsInstructionActive) s.PressNext();
                var first = s.CurrentItem;
                Assert.That(first, Is.Not.Null);
                s.Tick(0.02, new PlacementInputFrame { RateStep = 1 }, head);
                s.Tick(0.02, new PlacementInputFrame { RateSubmitDown = true }, head);
                Assert.That(s.RatingConfirmFlash, Is.True);
                Assert.That(s.CurrentItem, Is.SameAs(first), "확정 표시 동안은 같은 문항");
                Assert.That(s.RatingCursor, Is.EqualTo((first.Min + first.Max) / 2), "확정한 칸이 보인다");
                s.PressBackspace();
                s.PressDigit(3);
                s.PressConfirm();
                s.Tick(0.02, new PlacementInputFrame { RateStep = 1, RateSubmitDown = true }, head);
                for (int i = 0; i < 25; i++) s.Tick(0.02, none, head);
                Assert.That(s.RatingConfirmFlash, Is.False);
                Assert.That(s.CurrentItem, Is.Not.SameAs(first), "0.4 s 뒤 다음 문항");
                s.Quit("test");
                var dir = s.RecordDirectory;
                var ratings = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).ToList();
                Assert.That(ratings.Count, Is.EqualTo(1), "확정 표시 중 실험자 키·컨트롤러 입력은 기록되지 않는다");
                var events = File.ReadAllLines(Path.Combine(dir, "events.csv"));
                Assert.That(events.Any(l => l.Contains(",rating_cancel,")), Is.False);
            }
        }

        [Test]
        public void Panel_hiding_flag_hides_after_the_reading_time_in_condition_and_stop_distance_only()
        {
            var cfg = Short(PlacementConfig.ConditionPlace);
            cfg.hidePanelInDistancePhases = true;
            cfg.hidePanelReadSeconds = 2;
            var r = Run(cfg);
            var hidden = r.Events.Where(e => e[1] == "panel_hidden").Select(e => e[2]).ToList();
            Assert.That(hidden.Count, Is.EqualTo(2));
            Assert.That(hidden[0], Does.StartWith("phase=condition;after_ms=2000"));
            Assert.That(hidden[1], Does.StartWith("phase=stop_distance;after_ms=2000"));
            Assert.That(r.Events.Any(e => e[1] == "haptic"), Is.False, "다른 UI 플래그는 따로");
            Assert.That((double)r.Manifest["config"]["hidePanelReadSeconds"], Is.EqualTo(2));

            // 단계 시작 직후에는 보이고, 읽을 시간이 지나면 숨는다. 다른 단계(평정)에는 영향이 없다
            using (var s = new PlacementSession(cfg, ScaleA(), new PlacementSessionInfo { SessionId = "SYN-HIDE", ParticipantNumber = 1 }, Path.Combine(_tmp, "h")))
            {
                var none = new PlacementInputFrame();
                var head = HeadPose.At(0, 1.6, 0);
                s.PressNext();
                for (int i = 0; i < 100000 && s.Phase != PlacementPhase.Condition && !s.Finished; i++)
                {
                    s.Tick(0.02, none, head);
                    Assert.That(s.PanelHidden, Is.False, s.PhaseLabel);
                    if (s.Phase == PlacementPhase.PreItems) { while (s.ItemsInstructionActive) s.PressNext(); if (s.CurrentItem != null) { s.PressDigit(s.CurrentItem.Min); s.PressConfirm(); } }
                    if (s.Phase == PlacementPhase.PreWait) s.PressNext();
                }
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.Condition));
                Assert.That(s.PanelHidden, Is.False);
                Assert.That(s.ParticipantText, Is.Not.Null);
                for (int i = 0; i < 101; i++) s.Tick(0.02, none, head);
                Assert.That(s.PanelHidden, Is.True);
                Assert.That(s.ParticipantText, Is.Not.Null, "글 자체(실험자 화면용)는 그대로 — 판만 숨긴다");
                s.Quit("test");
            }
        }
    }
}
