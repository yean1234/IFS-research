// EditMode 테스트: 소유감 실험 변형본 생성기(설계 1절)·제시 순서·manifest. UnityEngine 없이 돈다(dotnet compile-check에서도 실행).
// spec은 모두 합성(OwnershipTestSpecs)이다.
using System;
using System.Collections.Generic;
using System.Linq;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class OwnershipVariantTests
    {
        // 이 파일의 기존(0.2) 테스트는 쌍을 끈 설정(shiftAttributes 빈 목록 = 0.2와 같은 동작)으로 돈다.
        // 같은 말·다른 값 쌍 테스트는 아래 "같은 말·다른 값" 절에서 기본 설정(color·size 켬)으로 돈다.
        public static OwnershipConfig NoShift(OwnershipConfig cfg = null)
        {
            cfg = (cfg ?? new OwnershipConfig()).Clone();
            cfg.shiftAttributes = new List<string>();
            return cfg;
        }

        static OwnershipPlan Gen(JObject spec, int participant = 1, OwnershipConfig cfg = null) =>
            OwnershipVariantGenerator.Generate(spec.Parse(), participant, NoShift(cfg));

        static OwnershipPlan GenOk(JObject spec, int participant = 1, OwnershipConfig cfg = null)
        {
            var p = Gen(spec, participant, cfg);
            Assert.That(p.Errors, Is.Empty, string.Join("\n", p.Errors));
            Assert.That(p.Variants.Select(v => v.Id), Is.EqualTo(new[] { "orig", "form", "color", "size", "motion" }));
            return p;
        }

        static OwnershipPlan GenShift(JObject spec, int participant = 1, OwnershipConfig cfg = null)
        {
            var p = OwnershipVariantGenerator.Generate(spec.Parse(), participant, cfg ?? new OwnershipConfig());
            Assert.That(p.Errors, Is.Empty, string.Join("\n", p.Errors));
            Assert.That(p.Variants.Take(5).Select(v => v.Id), Is.EqualTo(new[] { "orig", "form", "color", "size", "motion" }));
            return p;
        }

        // 기본 밝기 0.5 = 셰이더 밝기 배율 1(알베도 = _BaseColor)
        static Lab LabOf(double h, double s, double l, double brightness = 0.5) => RenderedColor.AlbedoLab(h, s, l, brightness);

        // ── 제시 순서 ─────────────────────────────────────────────────────
        [Test]
        public void Williams_table_puts_each_condition_twice_in_each_position_and_balances_first_order_carryover()
        {
            var rows = WilliamsDesign.Rows;
            Assert.That(rows.Length, Is.EqualTo(10));
            Assert.That(rows.All(r => r.Length == 5 && r.OrderBy(x => x).SequenceEqual(Enumerable.Range(0, 5))), Is.True, "행마다 5조건이 한 번씩");
            for (int pos = 0; pos < 5; pos++)
                for (int c = 0; c < 5; c++)
                    Assert.That(rows.Count(r => r[pos] == c), Is.EqualTo(2), $"조건 {c}가 위치 {pos + 1}에 2번");
            var pairs = new Dictionary<(int, int), int>();
            foreach (var r in rows)
                for (int i = 0; i + 1 < r.Length; i++)
                    pairs[(r[i], r[i + 1])] = pairs.TryGetValue((r[i], r[i + 1]), out int n) ? n + 1 : 1;
            Assert.That(pairs.Count, Is.EqualTo(20), "서로 다른 순서쌍 20개가 모두 나온다");
            Assert.That(pairs.Values.All(n => n == 2), Is.True, "각 순서쌍(a 바로 다음 b)이 2번씩");
            Assert.That(WilliamsDesign.Conditions, Is.EqualTo(new[] { "orig", "form", "color", "size", "motion" }));
        }

        [TestCase(1, 0, 0)]
        [TestCase(2, 1, 1)]
        [TestCase(10, 1, 9)]
        [TestCase(11, 1, 0)]    // 11–20번은 cb가 뒤집힌다
        [TestCase(14, 0, 3)]
        [TestCase(21, 0, 0)]    // 21–30번은 다시 1–10번과 같다
        public void Participant_number_sets_balance_bit_and_order_row(int n, int cb, int row)
        {
            var p = GenOk(OwnershipTestSpecs.Empty("SYN-order"), n);
            Assert.That(p.Cb, Is.EqualTo(cb));
            Assert.That(p.OrderRow, Is.EqualTo(row));
            Assert.That(p.Order, Is.EqualTo(WilliamsDesign.Rows[row].Select(i => WilliamsDesign.Conditions[i]).ToArray()));
        }

        [Test]
        public void Balance_bit_is_crossed_with_order_row_over_twenty_participants()
        {
            var cells = Enumerable.Range(1, 20).Select(n => (WilliamsDesign.RowFor(n), WilliamsDesign.CbFor(n))).ToList();
            Assert.That(cells.Distinct().Count(), Is.EqualTo(20), "1–20번의 (행, cb) 20쌍이 모두 다르다(행 × cb 완전 교차)");
            for (int n = 1; n <= 10; n++)
                Assert.That(WilliamsDesign.CbFor(n), Is.EqualTo((n - 1) % 2), $"1–10번의 cb는 이전 규칙과 같다({n})");
            for (int start = 1; start <= 21; start += 10)
                Assert.That(Enumerable.Range(start, 10).Count(n => WilliamsDesign.CbFor(n) == 0), Is.EqualTo(5), $"{start}번부터 10명 안에서 cb 5:5");
        }

        [Test]
        public void Participant_number_below_one_is_an_error()
        {
            Assert.That(Gen(OwnershipTestSpecs.Empty("SYN-zero"), 0).Ok, Is.False);
        }

        // ── 결정성 ───────────────────────────────────────────────────────
        static OwnershipSessionInfo FixedInfo() => new OwnershipSessionInfo
        {
            SessionId = "SYN-det", SpecFile = "SYN-det.json", SpecSha256 = "0", StartedAtUtc = "2026-01-01T00:00:00.000Z",
            HeadSource = "desktop", UnityVersion = "test", TaskTextFile = "ownership_task.v0.json", TaskTextVersion = "0.1",
            TaskTextDraftKeys = new[] { "done", "rating" },
        };

        [Test]
        public void Same_inputs_give_byte_identical_manifest()
        {
            JObject Spec() => OwnershipTestSpecs.Empty("SYN-det").Hsl(0.597, 0.49, 0.7).Slot("layout.size", 0.333)
                .Slot("motion.type", "swaying").ShapeWord("round", "동그란", 4);
            string a = OwnershipJson.Serialize(OwnershipManifest.Build(GenOk(Spec(), 7), FixedInfo()));
            string b = OwnershipJson.Serialize(OwnershipManifest.Build(GenOk(Spec(), 7), FixedInfo()));
            Assert.That(b, Is.EqualTo(a));
            Assert.That(a.Contains("\r"), Is.False, "줄바꿈은 \\n");
            Assert.That(a.EndsWith("\n"), Is.True);
            string c = OwnershipJson.Serialize(OwnershipManifest.Build(GenOk(Spec(), 8), FixedInfo()));
            Assert.That(c, Is.Not.EqualTo(a), "참여자 번호가 바뀌면 순서·균형 비트가 바뀐다");
        }

        public static JObject ParseNoDates(string json)
        {
            using (var r = new Newtonsoft.Json.JsonTextReader(new System.IO.StringReader(json)) { DateParseHandling = Newtonsoft.Json.DateParseHandling.None })
                return JObject.Load(r);
        }

        [Test]
        public void Manifest_has_contract_fields_in_order_and_spec_file_name_only()
        {
            var info = FixedInfo();
            info.SpecFile = "C:\\somewhere\\deep/SYN-det.json";
            // 분석 스크립트가 읽는 그대로(직렬화한 문자열을 다시 읽음, 날짜 문자열은 문자열로)
            var m = ParseNoDates(OwnershipJson.Serialize(OwnershipManifest.Build(GenOk(OwnershipTestSpecs.Empty("SYN-det")), info)));
            Assert.That(m.Properties().Select(p => p.Name).ToArray(), Is.EqualTo(new[]
            {
                "recordVersion", "generatorVersion", "participantNumber", "cb", "orderRow", "sessionId", "specFile", "specSha256",
                "startedAtUtc", "headSource", "unityVersion", "taskText", "ratingItem", "config", "flags", "original", "variants",
                "shiftPairs", "order",
            }));
            Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-ownership/0.3"));
            Assert.That((string)m["generatorVersion"], Is.EqualTo("ownership-variants/0.3"));
            Assert.That((string)m["ratingItem"], Is.EqualTo("resemblance"));
            Assert.That(((JObject)m["taskText"]).Properties().Select(p => p.Name), Is.EqualTo(new[] { "file", "version", "draftCount", "draftKeys" }));
            Assert.That((int)m["taskText"]["draftCount"], Is.EqualTo(2));
            Assert.That(m["taskText"]["draftKeys"].ToObject<string[]>(), Is.EqualTo(new[] { "done", "rating" }));
            Assert.That((string)m["specFile"], Is.EqualTo("SYN-det.json"));
            foreach (var k in new[] { "sizeStep", "colorDeltaE", "viewSeconds", "headSampleHz", "gazeConeDeg", "finalChoiceArcDeg", "differenceRating", "requireSpecPhrases", "generatorVersion",
                                      "shiftAttributes", "sizeShiftStep", "colorShiftDeltaE", "maxHueShiftDeg", "shiftSymmetryTolerance", "ratingItem" })
                Assert.That(m["config"][k], Is.Not.Null, "config." + k);
            Assert.That(m["flags"]["lowVisibility"], Is.Not.Null);
            foreach (var k in new[] { "params", "shapeModel", "statedKeys", "defaultKeys", "unmappedCount", "unmatchedCount" })
                Assert.That(m["original"][k], Is.Not.Null, "original." + k);
            var orig = (JObject)m["variants"][0];
            Assert.That((string)orig["id"], Is.EqualTo("orig"));
            Assert.That(orig["attribute"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(((JObject)orig["overrides"]).Count, Is.EqualTo(0));
            Assert.That(orig["shapeModel"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((string)orig["kind"], Is.EqualTo("orig"));
            foreach (JObject v in ((JArray)m["variants"]).Skip(1))
                foreach (var k in new[] { "id", "attribute", "kind", "overrides", "shapeModel", "changedKeys", "from", "to", "rule", "source", "sourceByKey", "flags", "magnitude" })
                    Assert.That(v.ContainsKey(k), Is.True, (string)v["id"] + "." + k);
            Assert.That(((JArray)m["order"]).Count, Is.EqualTo(5));
            var color = ((JArray)m["variants"]).Cast<JObject>().Single(v => (string)v["id"] == "color");
            Assert.That(((JObject)color["magnitude"]).Properties().Select(p => p.Name), Is.EqualTo(new[] { "deltaE00", "deltaE00Composited" }));
        }

        // ── 크기 ─────────────────────────────────────────────────────────
        [TestCase(1, 0.75, "up")]
        [TestCase(2, 0.25, "down")]
        public void Size_moves_one_step_in_balance_direction_inside_range(int participant, double to, string rule)
        {
            var v = GenOk(OwnershipTestSpecs.Empty("SYN-size"), participant).Get("size");   // 기본 0.5
            Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "layout.size" }));
            Assert.That(v.Override.Numbers["layout.size"], Is.EqualTo(to).Within(1e-9));
            Assert.That(v.Rule, Is.EqualTo(rule));
            Assert.That(v.Forced, Is.False);
            Assert.That(v.Source, Is.EqualTo("default"));
            Assert.That((double)v.Magnitude["sizeStep"], Is.EqualTo(0.25));
        }

        [TestCase(0.1, 2, 0.35, "up", true)]      // 아래 끝: 균형 비트(−)와 달라도 +
        [TestCase(0.9, 1, 0.65, "down", true)]    // 위 끝: 균형 비트(+)와 달라도 −
        [TestCase(0.25, 2, 0.0, "down", false)]   // 경계는 범위 안
        [TestCase(0.75, 1, 1.0, "up", false)]
        public void Size_direction_is_forced_near_the_ends_without_clamping(double s, int participant, double to, string rule, bool forced)
        {
            var v = GenOk(OwnershipTestSpecs.Empty("SYN-size").Slot("layout.size", s, "크기"), participant).Get("size");
            Assert.That(v.Override.Numbers["layout.size"], Is.EqualTo(to).Within(1e-9));
            Assert.That(v.Rule, Is.EqualTo(rule));
            Assert.That(v.Forced, Is.EqualTo(forced));
            Assert.That(v.Source, Is.EqualTo("stated"));
        }

        // ── 색 ───────────────────────────────────────────────────────────
        [TestCase(0.6, 0.5, 0.4, 1)]
        [TestCase(0.6, 0.5, 0.4, 2)]
        [TestCase(0.0, 0.8, 0.5, 1)]
        [TestCase(0.33, 0.3, 0.6, 2)]
        public void Chromatic_color_rotates_hue_only_by_the_smallest_angle_reaching_the_target(double h, double s, double l, int participant)
        {
            var plan = GenOk(OwnershipTestSpecs.Empty("SYN-hue").Hsl(h, s, l), participant);
            var v = plan.Get("color");
            if (v.Rule != "hue") Assert.Inconclusive("이 색은 색상만으로 목표에 닿지 않음: " + v.Rule);
            Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.h" }), "색상만 바뀐다");
            Assert.That(v.Override.Categories, Is.Empty);
            Assert.That((double)v.To["material.color.s"], Is.EqualTo((double)v.From["material.color.s"]));
            Assert.That((double)v.To["material.color.l"], Is.EqualTo((double)v.From["material.color.l"]));
            double to = v.Override.Numbers["material.color.h"];
            double de = ColorMetrics.DeltaE2000(LabOf(h, s, l), LabOf(to, s, l));
            Assert.That(de, Is.GreaterThanOrEqualTo(30.0), "달성 ΔE00 ≥ 목표");
            Assert.That((double)v.Magnitude["deltaE00"], Is.EqualTo(de).Within(0.001));
            int k = (int)v.Detail["steps"];
            int dir = plan.Cb == 0 ? +1 : -1;
            double expected = h + dir * k / 360.0;
            expected -= Math.Floor(expected);
            Assert.That(Math.Abs(to - Math.Round(expected, 4)) < 1e-9 || Math.Abs(to - Math.Round(expected, 4) + 1) < 1e-9, Is.True, "균형 비트 방향으로 k°");
            if (k > 1)
            {
                double prev = h + dir * (k - 1) / 360.0;
                prev = Math.Round(prev - Math.Floor(prev), 4) % 1.0;
                Assert.That(ColorMetrics.DeltaE2000(LabOf(h, s, l), LabOf(prev, s, l)), Is.LessThan(30.0), "한 걸음 전은 목표 미만(최소 각)");
            }
            Assert.That(v.BelowTarget, Is.False);
            Assert.That(v.Source, Is.EqualTo("stated"));
        }

        [TestCase(1)]
        [TestCase(2)]
        public void Achromatic_default_color_changes_lightness_only(int participant)
        {
            var v = GenOk(OwnershipTestSpecs.Empty("SYN-gray"), participant).Get("color");   // 기본 HSL(0, 0, 0.7)
            Assert.That(v.Rule, Is.EqualTo("lightness"));
            Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.l" }), "명도만 바뀐다");
            Assert.That((double)v.To["material.color.h"], Is.EqualTo(0.0));
            Assert.That((double)v.To["material.color.s"], Is.EqualTo(0.0));
            double to = v.Override.Numbers["material.color.l"];
            Assert.That(ColorMetrics.DeltaE2000(LabOf(0, 0, 0.7), LabOf(0, 0, to)), Is.GreaterThanOrEqualTo(30.0));
            Assert.That(to, Is.LessThan(0.7), "0.7에서는 밝게 해도 목표에 닿지 않아 균형 비트와 무관하게 어둡게");
            Assert.That((string)v.Detail["direction"], Is.EqualTo("darker"));
            Assert.That(v.Source, Is.EqualTo("default"));
            Assert.That((bool)v.Detail["achromatic"], Is.True);
        }

        [TestCase(1, "lighter")]
        [TestCase(2, "darker")]
        public void Achromatic_mid_gray_follows_the_balance_bit_when_both_directions_reach(int participant, string direction)
        {
            var v = GenOk(OwnershipTestSpecs.Empty("SYN-midgray").Hsl(0, 0.05, 0.5), participant).Get("color");
            Assert.That(v.Rule, Is.EqualTo("lightness"));
            Assert.That((string)v.Detail["direction"], Is.EqualTo(direction));
            Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.l" }));
            double to = v.Override.Numbers["material.color.l"];
            double step = direction == "lighter" ? to - 0.005 : to + 0.005;
            Assert.That(ColorMetrics.DeltaE2000(LabOf(0, 0.05, 0.5), LabOf(0, 0.05, to)), Is.GreaterThanOrEqualTo(30.0));
            Assert.That(ColorMetrics.DeltaE2000(LabOf(0, 0.05, 0.5), LabOf(0, 0.05, step)), Is.LessThan(30.0), "최소량");
        }

        [Test]
        public void Weak_chroma_falls_back_to_lightness_and_unreachable_target_is_flagged()
        {
            var v = GenOk(OwnershipTestSpecs.Empty("SYN-weak").Hsl(0.0, 0.12, 0.9)).Get("color");   // 연하고 밝은 색: 색상을 180° 돌려도 ΔE00 < 30
            Assert.That(v.Rule, Is.EqualTo("lightness_fallback"));
            Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.l" }));
            Assert.That(v.BelowTarget, Is.False);

            var far = GenOk(OwnershipTestSpecs.Empty("SYN-far").Hsl(0.6, 0.5, 0.4), 1, new OwnershipConfig { colorDeltaE = 150 }).Get("color");
            Assert.That(far.BelowTarget, Is.True, "목표에 못 미치면 최대 변화 + belowTarget(오류 아님)");
            Assert.That((double)far.Magnitude["deltaE00"], Is.GreaterThan(30.0));
            Assert.That(far.Override.Numbers.Count, Is.EqualTo(1));
        }

        [Test]
        public void Brightness_factor_and_albedo_follow_the_shader()
        {
            Assert.That(RenderedColor.BrightnessFactor(0.0), Is.EqualTo(0.4).Within(1e-12));
            Assert.That(RenderedColor.BrightnessFactor(0.25), Is.EqualTo(0.7).Within(1e-12));
            Assert.That(RenderedColor.BrightnessFactor(0.5), Is.EqualTo(1.0).Within(1e-12));
            Assert.That(RenderedColor.BrightnessFactor(1.0), Is.EqualTo(1.0).Within(1e-12), "0.5 초과는 알베도가 아니라 발광");
            RenderedColor.BaseSrgb(0.6, 0.5, 0.4, out double r, out double g, out double b);
            SceneParams.HslToRgb(0.6, 0.5, 0.4, out double r0, out double g0, out double b0);
            Assert.That(new[] { r, g, b }, Is.EqualTo(new[] { r0, g0, b0 }), "_BaseColor = HSL → sRGB");
            RenderedColor.AlbedoSrgb(0.6, 0.5, 0.4, 0.8, out double ar, out double ag, out double ab);
            Assert.That(new[] { ar, ag, ab }, Is.EqualTo(new[] { r, g, b }).Within(1e-9), "밝기 ≥ 0.5면 알베도 = _BaseColor");
            RenderedColor.AlbedoSrgb(0.6, 0.5, 0.4, 0.0, out double dr, out _, out _);
            Assert.That(ColorMetrics.SrgbToLinear(dr), Is.EqualTo(0.4 * ColorMetrics.SrgbToLinear(r)).Within(1e-9), "선형 공간에서 × 0.4");
            Assert.That(RenderedColor.UsesFadeShader("blob", 1.0), Is.False);
            Assert.That(RenderedColor.UsesFadeShader("blob", 0.98), Is.True);
            Assert.That(RenderedColor.UsesFadeShader("mist", 1.0), Is.True);
            Assert.That(RenderedColor.SurfaceAlpha("mist", 0.6, 0.5), Is.EqualTo(0.3).Within(1e-12));
            Assert.That(RenderedColor.SurfaceAlpha("blob", 1.0, 1.0), Is.EqualTo(1.0));
        }

        [TestCase(0.6, 0.5, 0.4, 0.1)]
        [TestCase(0.0, 0.0, 0.7, 0.0)]
        public void Color_target_is_reached_on_the_shader_albedo_not_the_hsl_value(double h, double s, double l, double brightness)
        {
            var plan = GenOk(OwnershipTestSpecs.Empty("SYN-dim").Hsl(h, s, l).Slot("material.brightness", brightness, "어두운"));
            var v = plan.Get("color");
            Assert.That(v.BelowTarget, Is.False, v.Rule);
            string key = v.Override.Numbers.Keys.Single();
            double th = key == "material.color.h" ? v.Override.Numbers[key] : h;
            double tl = key == "material.color.l" ? v.Override.Numbers[key] : l;
            double de = ColorMetrics.DeltaE2000(LabOf(h, s, l, brightness), LabOf(th, s, tl, brightness));
            Assert.That(de, Is.GreaterThanOrEqualTo(30.0), "알베도 기준 ΔE00 ≥ 목표");
            Assert.That((double)v.Magnitude["deltaE00"], Is.EqualTo(de).Within(0.001));
            Assert.That((string)v.Detail["deltaEBasis"], Is.EqualTo("albedo"));
            Assert.That((double)v.Detail["brightnessFactor"], Is.EqualTo(Math.Round(RenderedColor.BrightnessFactor(brightness), 4)));
            // 밝기가 낮으면 같은 HSL 변화의 화면 차이가 작아, 밝기 0.5(배율 1)일 때보다 적게 가서는 목표에 닿지 않는다.
            var bright = GenOk(OwnershipTestSpecs.Empty("SYN-dim").Hsl(h, s, l)).Get("color");
            if (bright.Rule == v.Rule && (string)bright.Detail["direction"] == (string)v.Detail["direction"])
                Assert.That((int)v.Detail["steps"], Is.GreaterThanOrEqualTo((int)bright.Detail["steps"]));
            double hslDe = ColorMetrics.DeltaE2000(ColorMetrics.SrgbToLab(Rgb(h, s, l)[0], Rgb(h, s, l)[1], Rgb(h, s, l)[2]),
                                                   ColorMetrics.SrgbToLab(Rgb(th, s, tl)[0], Rgb(th, s, tl)[1], Rgb(th, s, tl)[2]));
            Assert.That(hslDe, Is.Not.EqualTo(de).Within(0.5), "HSL 해석값 기준 ΔE00과는 다르다(밝기 배율 < 1)");
        }

        static double[] Rgb(double h, double s, double l)
        {
            SceneParams.HslToRgb(h, s, l, out double r, out double g, out double b);
            return new[] { r, g, b };
        }

        [TestCase(null, 1.0, 1.0)]
        [TestCase(null, 0.4, 0.4)]
        [TestCase("mist", 1.0, 0.5)]
        public void Composited_delta_e_uses_the_surface_alpha_and_is_recorded_only(string form, double opacity, double alpha)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-comp").Hsl(0.6, 0.5, 0.4).Slot("material.opacity", opacity, "투명");
            if (form != null) spec.Slot("form.type", form, "형태");
            var v = GenOk(spec).Get("color");
            var free = GenOk(OwnershipTestSpecs.Empty("SYN-comp").Hsl(0.6, 0.5, 0.4)).Get("color");
            Assert.That(v.Override.Numbers, Is.EqualTo(free.Override.Numbers), "불투명도는 목표 계산에 들어가지 않는다");
            Assert.That((double)v.Detail["compositeAlpha"], Is.EqualTo(alpha).Within(1e-9));
            double de = (double)v.Magnitude["deltaE00"], comp = (double)v.Magnitude["deltaE00Composited"];
            if (alpha >= 1.0) Assert.That(comp, Is.EqualTo(de).Within(0.002), "불투명이면 합성해도 같다");
            else Assert.That(comp, Is.LessThan(de), "배경과 섞이면 차이가 줄어든다");
            double h1 = v.Override.Numbers["material.color.h"];
            Assert.That(comp, Is.EqualTo(Math.Round(OwnershipVariantGenerator.CompositedDeltaE(0.6, 0.4, h1, 0.4, 0.5, 0.5, alpha), 3)));
        }

        [Test]
        public void Color_change_leaves_brightness_and_opacity_alone()
        {
            var plan = GenOk(OwnershipTestSpecs.Empty("SYN-other").Hsl(0.3, 0.6, 0.5).Slot("material.brightness", 0.8).Slot("material.opacity", 0.6));
            var v = plan.Get("color");
            var a = plan.OriginalParams.ToRecord();
            var b = v.Params.ToRecord();
            Assert.That(a.Keys.Where(k => !Equals(a[k], b[k])), Is.EqualTo(new[] { "material.color.h" }));
        }

        // ── 움직임 ───────────────────────────────────────────────────────
        [TestCase(null, null, "add", "floating", "default", false)]
        [TestCase("swaying", null, "remove", "still", "stated", false)]
        [TestCase("rotating", "round", "add", "floating", "stated", false)]     // 구가 돌면 보이지 않음
        [TestCase("swaying", "round", "add", "floating", "stated", false)]      // 구가 흔들려도 보이지 않음
        [TestCase("rotating", "flat", "add", "floating", "stated", false)]
        [TestCase("rotating", "pointed", "add", "floating", "stated", false)]
        [TestCase("rotating", "square", "remove", "still", "stated", false)]    // 큐브는 돌면 보인다
        [TestCase("swaying", "flat", "remove", "still", "stated", false)]
        [TestCase("pounding", null, "remove", "still", "stated", true)]         // 맥동은 크기 정보를 바꾼다
        [TestCase("sinking", null, "remove", "still", "stated", true)]
        public void Motion_presence_is_flipped_and_invisible_combinations_count_as_still(string type, string shape, string rule, string to, string source, bool altersScale)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-motion");
            if (type != null) spec.Slot("motion.type", type, "움직");
            if (shape != null) spec.ShapeWord(shape, "모양", 5);
            var v = GenOk(spec).Get("motion");
            Assert.That(v.Rule, Is.EqualTo(rule));
            Assert.That(v.Override.Categories["motion.type"], Is.EqualTo(to));
            Assert.That(v.Override.Numbers, Is.Empty, "속도는 바꾸지 않는다");
            Assert.That(v.Source, Is.EqualTo(source));
            Assert.That(v.MotionAltersScale, Is.EqualTo(altersScale));
        }

        // 기본 blob·mist·shell·fragments(모양 모형 없음)는 굴곡·조각이 물체와 함께 돌아 회전·기울임이 보인다 → 표에 없음.
        [TestCase(null, "rotating")]
        [TestCase(null, "swaying")]
        [TestCase("blob", "rotating")]
        [TestCase("mist", "rotating")]
        [TestCase("shell", "rotating")]
        [TestCase("fragments", "swaying")]
        public void Rotation_on_shapes_without_a_shape_model_is_visible(string formType, string type)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-blobmotion").Slot("motion.type", type, "움직");
            if (formType != null) spec.Slot("form.type", formType, "형태");
            var plan = GenOk(spec);
            Assert.That(plan.OriginalShapeModel, Is.EqualTo("none"));
            var v = plan.Get("motion");
            Assert.That(v.Rule, Is.EqualTo("remove"), "보이는 움직임 → still");
            Assert.That((bool)v.Detail["originalVisible"], Is.True);
            foreach (MotionGroup g in Enum.GetValues(typeof(MotionGroup)))
                Assert.That(OwnershipVariantGenerator.IsInvisibleMotion(g, null), Is.False, "모양 모형이 없으면 표에 걸리지 않음: " + g);
        }

        // 자세 변형은 x = z라 y축 회전(Spin)의 대칭은 유지되지만, z축 기울임(Sway)은 눌린 구에서 보인다.
        [TestCase("swaying", "round", "curled", "remove")]
        [TestCase("swaying", "round", null, "add")]
        [TestCase("rotating", "round", "lying", "add")]
        [TestCase("rotating", "pointed", "standing", "add")]
        public void Posture_deformation_makes_sway_on_a_sphere_visible(string type, string shape, string posture, string rule)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-posture").Slot("motion.type", type, "움직").ShapeWord(shape, "모양", 5);
            if (posture != null) spec.Slot("form.posture", posture, "자세");
            var v = GenOk(spec).Get("motion");
            Assert.That(v.Rule, Is.EqualTo(rule));
            Assert.That((bool)v.Detail["originalVisible"], Is.EqualTo(rule == "remove"));
        }

        [Test]
        public void Invisible_motion_table_is_fixed()
        {
            var rows = OwnershipVariantGenerator.InvisibleMotion.Select(x => $"{x.group}/{x.model}/{(x.anyPosture ? "any" : "none")}").ToArray();
            Assert.That(rows, Is.EqualTo(new[] { "Spin/Sphere/any", "Spin/FlatCylinder/any", "Spin/Cone/any", "Sway/Sphere/none" }),
                "표를 바꾸면 docs/decisions.md와 이 테스트를 함께 고친다");
        }

        [Test]
        public void Unknown_motion_type_is_an_error_not_a_silent_substitute()
        {
            var p = Gen(OwnershipTestSpecs.Empty("SYN-dance").Slot("motion.type", "dancing"));
            Assert.That(p.Ok, Is.False);
            Assert.That(p.Errors.Any(e => e.Contains("dancing")), Is.True, string.Join("\n", p.Errors));
            Assert.That(p.Get("motion"), Is.Null);
        }

        // ── 형태 ─────────────────────────────────────────────────────────
        [TestCase(null, null, "blob", "Cube", null, "add", "default")]
        [TestCase("blob", null, "blob", "Cube", null, "add", "stated")]
        [TestCase(null, "round", "Sphere", "Cube", null, "swap", "stated")]
        [TestCase(null, "square", "Cube", "Sphere", null, "remove", "stated")]
        [TestCase(null, "flat", "FlatCylinder", "Sphere", null, "remove", "stated")]
        [TestCase("blob", "pointed", "Cone", "Sphere", null, "remove", "stated")]
        [TestCase("mist", null, "mist", null, "blob", "remove", "stated")]
        [TestCase("shell", null, "shell", null, "blob", "remove", "stated")]
        [TestCase("fragments", null, "fragments", null, "blob", "remove", "stated")]
        public void Form_follows_the_four_row_table(string formType, string shape, string fromRendered, string forcedModel, string formOverride, string rule, string source)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-form");
            if (formType != null) spec.Slot("form.type", formType, "형태");
            if (shape != null) spec.ShapeWord(shape, "모양", 5);
            var plan = GenOk(spec);
            var v = plan.Get("form");
            Assert.That(plan.OriginalRendered, Is.EqualTo(fromRendered));
            Assert.That(v.Override.ShapeModel, Is.EqualTo(forcedModel));
            if (formOverride != null) Assert.That(v.Override.Categories["form.type"], Is.EqualTo(formOverride));
            else Assert.That(v.Override.Categories.ContainsKey("form.type"), Is.False);
            Assert.That(v.Rule, Is.EqualTo(rule));
            Assert.That(v.Source, Is.EqualTo(source));
            Assert.That(v.Rendered, Is.EqualTo(forcedModel ?? "blob"));
            Assert.That(v.RenderedShapeModel, Is.EqualTo(forcedModel), "mist·shell·fragments → blob은 모양 모형 없음");
            Assert.That(v.SaidNotRendered, Is.False);
            Assert.That(v.Params.ToRecord().Where(kv => !Equals(plan.OriginalParams.ToRecord()[kv.Key], kv.Value)).Select(kv => kv.Key),
                Is.EqualTo(formOverride != null ? new[] { "form.type" } : new string[0]), "형태 말고는 해석값이 같다");
        }

        [Test]
        public void Said_but_not_rendered_shape_words_are_flagged_with_the_right_source()
        {
            var unmapped = GenOk(OwnershipTestSpecs.Empty("SYN-thread").ShapeWord("thread", "실", 2)).Get("form");
            Assert.That(unmapped.Rule, Is.EqualTo("add"));
            Assert.That(unmapped.Source, Is.EqualTo("default"), "form.type null + 모양 적용 안 됨 → 기본값으로 그린 형태");
            Assert.That(unmapped.SaidNotRendered, Is.True);

            var blocked = GenOk(OwnershipTestSpecs.Empty("SYN-mistsq").Slot("form.type", "mist").ShapeWord("square", "네모", 3)).Get("form");
            Assert.That(blocked.Override.Categories["form.type"], Is.EqualTo("blob"));
            Assert.That(blocked.Override.ShapeModel, Is.Null);
            Assert.That(blocked.Rendered, Is.EqualTo("blob"), "말한 네모를 되살리지 않고 blob(모양 모형 없음)");
            Assert.That(blocked.SaidNotRendered, Is.True);

            var conflict = GenOk(OwnershipTestSpecs.Empty("SYN-conf").ShapeWord("round", "동그", 1).ShapeWord("square", "네모", 9)).Get("form");
            Assert.That(conflict.Rule, Is.EqualTo("swap"));
            Assert.That(conflict.Source, Is.EqualTo("stated"));
            Assert.That(conflict.SaidNotRendered, Is.True, "conflict 모양어");
        }

        [Test]
        public void Source_label_is_stated_default_or_mixed()
        {
            Assert.That(OwnershipVariantGenerator.SourceLabel(new[] { "stated" }), Is.EqualTo("stated"));
            Assert.That(OwnershipVariantGenerator.SourceLabel(new[] { "default", "default" }), Is.EqualTo("default"));
            Assert.That(OwnershipVariantGenerator.SourceLabel(new[] { "stated", "default" }), Is.EqualTo("mixed"));
            var plan = GenOk(OwnershipTestSpecs.Empty("SYN-src").Slot("layout.size", 0.4).Hsl(0.6, 0.5, 0.4));
            Assert.That(plan.Get("size").SourceByKey["layout.size"], Is.EqualTo("stated"));
            Assert.That(plan.Get("color").SourceByKey.Values.Single(), Is.EqualTo("stated"));
            Assert.That(plan.Get("motion").Source, Is.EqualTo("default"));
            Assert.That(plan.Get("form").Source, Is.EqualTo("default"));
        }

        // SpecCheck 화면의 구분 칸은 생성기의 SlotSource(_provenance 기준)를 그대로 쓴다. 값은 있는데 근거가 없으면 "근거 없음".
        [Test]
        public void Spec_check_label_follows_the_generator_provenance_rule_including_unsupported_values()
        {
            var o = OwnershipTestSpecs.Empty("SYN-label").Slot("layout.size", 0.4).Slot("motion.type", "swaying");
            o["form"]["type"] = "mist";          // 값만 있고 근거 없음
            o["material"]["opacity"] = 0.6;      // 값만 있고 근거 없음
            var spec = o.Parse();

            Assert.That(OwnershipVariantGenerator.SlotSource(spec, "layout.size"), Is.EqualTo(OwnershipVariantGenerator.SlotStated));
            Assert.That(OwnershipVariantGenerator.SlotSource(spec, "material.color"), Is.EqualTo(OwnershipVariantGenerator.SlotDefault));
            Assert.That(OwnershipVariantGenerator.SlotSource(spec, "form.type"), Is.EqualTo(OwnershipVariantGenerator.SlotUnsupported));
            Assert.That(OwnershipVariantGenerator.SlotSource(spec, "material.opacity"), Is.EqualTo(OwnershipVariantGenerator.SlotUnsupported));

            string Label(string path) => OwnershipRunner.SpecCheckLabel(OwnershipVariantGenerator.SlotSource(spec, path));
            Assert.That(Label("layout.size"), Is.EqualTo("말한 값"));
            Assert.That(Label("motion.type"), Is.EqualTo("말한 값"));
            Assert.That(Label("material.color"), Is.EqualTo("기본값"));
            Assert.That(Label("form.type"), Is.EqualTo("근거 없음"), "값이 있다고 '말한 값'으로 보이지 않는다");
            Assert.That(Label("material.opacity"), Is.EqualTo("근거 없음"));

            // 화면에서 '말한 값'인 슬롯 ⇔ 변형 source stated (모양어 없는 spec)
            var plan = GenOk(o);
            var slotOf = new Dictionary<string, string>
            {
                { "form.type", "form.type" }, { "form.shapeModel", "form.type" }, { "material.color.h", "material.color" },
                { "material.color.l", "material.color" }, { "layout.size", "layout.size" }, { "motion.type", "motion.type" },
            };
            foreach (var v in plan.Variants.Where(v => !v.IsOriginal))
                foreach (var kv in v.SourceByKey)
                    Assert.That(kv.Value == "stated", Is.EqualTo(Label(slotOf[kv.Key]) == "말한 값"), $"{v.Id}.{kv.Key}");
            Assert.That(plan.Get("form").Source, Is.EqualTo("default"), "근거 없는 form.type은 말한 것으로 세지 않는다");
            Assert.That(plan.Get("size").Source, Is.EqualTo("stated"));
            Assert.That(OwnershipRunner.SpecCheckLabel(null), Is.EqualTo("기본값"));
        }

        // ── 경계 ─────────────────────────────────────────────────────────
        [Test]
        public void Variant_that_equals_the_original_is_an_error()
        {
            var p = Gen(OwnershipTestSpecs.Empty("SYN-same"), 1, new OwnershipConfig { sizeStep = 0.00001 });
            Assert.That(p.Ok, Is.False);
            Assert.That(p.Errors.Any(e => e.StartsWith("size:") && e.Contains("원본과 같습니다")), Is.True, string.Join("\n", p.Errors));
            Assert.Throws<InvalidOperationException>(() => OwnershipManifest.Build(p, FixedInfo()), "오류가 있으면 manifest를 만들지 않는다");
        }

        [TestCase(null, 0.1, true)]
        [TestCase("mist", 0.25, true)]    // 유효 = 0.25 × 0.5
        [TestCase(null, 0.2, false)]
        [TestCase("mist", 0.4, false)]
        public void Low_visibility_is_flagged_from_effective_opacity(string form, double opacity, bool low)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-vis").Slot("material.opacity", opacity);
            if (form != null) spec.Slot("form.type", form);
            var p = GenOk(spec);
            Assert.That(p.LowVisibility, Is.EqualTo(low));
            Assert.That(p.Warnings.Any(w => w.StartsWith("lowVisibility")), Is.EqualTo(low));
        }

        [Test]
        public void Original_matches_scene_params_and_separates_stated_from_default_keys()
        {
            var spec = OwnershipTestSpecs.Empty("SYN-keys").Hsl(0.6, 0.5, 0.4).Slot("layout.size", 0.4);
            var plan = GenOk(spec);
            var direct = SceneParams.FromSpec(spec.Parse(), new SceneDefaults());
            Assert.That(JToken.DeepEquals(JObject.FromObject(direct.ToRecord()), JObject.FromObject(plan.OriginalParams.ToRecord())), Is.True);
            Assert.That(plan.StatedKeys, Is.EqualTo(new[] { "layout.size", "material.color.h", "material.color.l", "material.color.s" }));
            Assert.That(plan.StatedKeys.Concat(plan.DefaultKeys).OrderBy(k => k, StringComparer.Ordinal),
                Is.EqualTo(direct.ToRecord().Keys.OrderBy(k => k, StringComparer.Ordinal)));
            Assert.That(plan.OriginalShapeModel, Is.EqualTo("none"));
        }

        [Test]
        public void Inferred_values_are_never_used()
        {
            var spec = OwnershipTestSpecs.Empty("SYN-inf");
            spec["_inferred"] = new JObject
            {
                ["layout.size"] = new JObject
                {
                    ["value"] = 0.9,
                    ["_provenance"] = new JArray(new JObject { ["source"] = "vad_lexicon", ["trigger"] = "무거운", ["charSpan"] = new JArray(0, 3), ["rule"] = "vad" }),
                },
            };
            var plan = GenOk(spec);
            Assert.That(plan.OriginalParams.InferredUsed, Is.Empty);
            Assert.That(plan.OriginalParams.GetNumber("layout.size"), Is.EqualTo(0.5), "기본값 0.5(제안 0.9를 쓰지 않음)");
        }

        // ── 같은 말·다른 값 쌍 ──────────────────────────────────────────
        // 합성 spec 두 개: 말한 유채색 + 말한 크기, 모두 기본값. 덤프(IFS_DUMP_DIR)·보고에 쓴다.
        public static JObject StatedSpec() => OwnershipTestSpecs.Empty("SYN-shift-stated").Hsl(0.6, 0.5, 0.4, "파란")
            .Slot("layout.size", 0.3, "작은").Slot("motion.type", "swaying", "흔들");
        public static JObject DefaultSpec() => OwnershipTestSpecs.Empty("SYN-shift-default");

        static OwnershipSessionInfo ShiftInfo(string id) => new OwnershipSessionInfo
        {
            SessionId = id, SpecFile = id + ".json", SpecSha256 = "0", StartedAtUtc = "2026-01-01T00:00:00.000Z",
            HeadSource = "desktop", UnityVersion = "test", TaskTextFile = "ownership_task.v0.2.json", TaskTextVersion = "0.2",
            TaskTextDraftKeys = new[] { "difference", "done", "final_choice", "final_choice_resemblance", "rating", "rating_resemblance", "viewing_intro" },
        };

        [Test]
        public void Dump_shift_manifests_when_requested()
        {
            string dir = Environment.GetEnvironmentVariable("IFS_DUMP_DIR");
            var cases = new[] { ("manifest_stated.json", StatedSpec(), "SYN-shift-stated"), ("manifest_default.json", DefaultSpec(), "SYN-shift-default") };
            foreach (var (file, spec, id) in cases)
            {
                var plan = GenShift(spec, 3);
                string json = OwnershipJson.Serialize(OwnershipManifest.Build(plan, ShiftInfo(id)));
                TestContext.Progress.WriteLine($"{file}: order={string.Join(",", plan.Order)}; pairs=" +
                    string.Join(" | ", plan.ShiftPairs.Select(p => p.ToJson().ToString(Newtonsoft.Json.Formatting.None))));
                if (!string.IsNullOrEmpty(dir)) System.IO.File.WriteAllText(System.IO.Path.Combine(dir, file), json, new System.Text.UTF8Encoding(false));
            }
        }
        // n조건 Williams: 행마다 조건이 한 번씩, 한 주기에서 각 위치·각 순서쌍이 같은 횟수(짝수 1번, 홀수 2번).
        [TestCase(4)]
        [TestCase(5)]
        [TestCase(6)]
        [TestCase(7)]
        [TestCase(8)]
        [TestCase(9)]
        public void Williams_design_generalizes_to_n_conditions_with_first_order_carryover_balance(int n)
        {
            var rows = WilliamsDesign.RowsFor(n);
            int reps = n % 2 == 0 ? 1 : 2;
            Assert.That(rows.Length, Is.EqualTo(n * reps), "짝수 n행, 홀수 2n행");
            Assert.That(rows.All(r => r.Length == n && r.OrderBy(x => x).SequenceEqual(Enumerable.Range(0, n))), Is.True, "행마다 조건이 한 번씩");
            for (int pos = 0; pos < n; pos++)
                for (int c = 0; c < n; c++)
                    Assert.That(rows.Count(r => r[pos] == c), Is.EqualTo(reps), $"조건 {c}가 위치 {pos + 1}에 {reps}번");
            var pairs = new Dictionary<(int, int), int>();
            foreach (var r in rows)
                for (int i = 0; i + 1 < r.Length; i++)
                    pairs[(r[i], r[i + 1])] = pairs.TryGetValue((r[i], r[i + 1]), out int k) ? k + 1 : 1;
            Assert.That(pairs.Count, Is.EqualTo(n * (n - 1)), "서로 다른 순서쌍이 모두 나온다");
            Assert.That(pairs.Values.All(k => k == reps), Is.True, $"각 순서쌍(a 바로 다음 b)이 {reps}번씩");
            Assert.That(WilliamsDesign.Generate(n).Select(r => string.Join(",", r)), Is.EqualTo(rows.Select(r => string.Join(",", r))),
                "n = 5도 일반 규칙과 같은 표(상수 표는 0.2 세션 재현용)");
        }

        [Test]
        public void Order_is_assigned_after_the_shown_conditions_are_known()
        {
            var ids = new List<string>();
            for (int participant = 1; participant <= 18; participant++)
            {
                var plan = GenShift(DefaultSpec(), participant);
                var shown = plan.Variants.Select(v => v.Id).ToList();
                Assert.That(shown, Is.EqualTo(OwnershipVariantGenerator.ConditionIds), "기본 spec: 9개 모두");
                Assert.That(plan.Order.OrderBy(x => x, StringComparer.Ordinal), Is.EqualTo(shown.OrderBy(x => x, StringComparer.Ordinal)), "보여 줄 조건이 한 번씩");
                Assert.That(plan.OrderRow, Is.EqualTo((participant - 1) % 18));
                Assert.That(plan.Order, Is.EqualTo(WilliamsDesign.OrderFor(participant, shown)));
                ids.Add(string.Join(",", plan.Order));
            }
            Assert.That(ids.Distinct().Count(), Is.EqualTo(18), "9조건 = 18행, 18명이면 행이 한 번씩");

            // 색 쌍이 빠지면(무효) 조건 7개 → 14행
            var seven = GenShift(DefaultSpec().Hsl(0.0, 0.12, 0.9), 15);
            Assert.That(seven.Variants.Select(v => v.Id), Is.EqualTo(new[] { "orig", "form", "color", "size", "motion", "size_lo", "size_hi" }));
            Assert.That(seven.OrderRow, Is.EqualTo(14 % 14));
            Assert.That(seven.Order, Is.EqualTo(WilliamsDesign.OrderFor(15, seven.Variants.Select(v => v.Id).ToList())));
        }

        // 쌍을 끄면(shiftAttributes 빈 목록) 0.2 생성기와 바이트까지 같은 manifest(버전 문자열과 0.3에 더한 필드만 다름).
        // Golden/ownership_v02_*.json = 0.3 변경 직전 생성기(ownership-variants/0.2)로 만든 manifest.
        [TestCase("ownership_v02_default_p1.json", 1)]
        [TestCase("ownership_v02_stated_p7.json", 7)]
        [TestCase("ownership_v02_mist_p12.json", 12)]
        public void Empty_shift_attributes_reproduce_the_v02_manifest_byte_for_byte(string golden, int participant)
        {
            JObject spec;
            switch (participant)
            {
                case 1: spec = OwnershipTestSpecs.Empty("SYN-golden"); break;
                case 7:
                    spec = OwnershipTestSpecs.Empty("SYN-golden").Hsl(0.597, 0.49, 0.7).Slot("layout.size", 0.333)
                        .Slot("motion.type", "swaying").ShapeWord("round", "동그란", 4);
                    break;
                default:
                    spec = OwnershipTestSpecs.Empty("SYN-golden").Slot("form.type", "mist").Hsl(0.0, 0.05, 0.3)
                        .Slot("layout.size", 0.9).Slot("material.opacity", 0.6).Slot("material.brightness", 0.2);
                    break;
            }
            var info = new OwnershipSessionInfo
            {
                SessionId = "SYN-golden", SpecFile = "SYN-golden.json", SpecSha256 = "0", StartedAtUtc = "2026-01-01T00:00:00.000Z",
                HeadSource = "desktop", UnityVersion = "test", TaskTextFile = "ownership_task.v0.json", TaskTextVersion = "0.1",
                TaskTextDraftKeys = new[] { "done", "rating" },
            };
            var cfg = new OwnershipConfig { shiftAttributes = new List<string>() };
            var plan = OwnershipVariantGenerator.Generate(spec.Parse(), participant, cfg);
            Assert.That(plan.Errors, Is.Empty, string.Join("\n", plan.Errors));
            var m = OwnershipManifest.Build(plan, info);
            Assert.That(m["shiftPairs"].Select(p => (string)p["skipReason"]), Is.EqualTo(new[] { "disabled", "disabled" }));
            // 0.3에서 더한 것만 걷어 낸다
            m["recordVersion"] = "ifs-ownership/0.2";
            m["generatorVersion"] = "ownership-variants/0.2";
            m["config"]["generatorVersion"] = "ownership-variants/0.2";
            m.Remove("ratingItem");
            m.Remove("shiftPairs");
            foreach (var k in new[] { "shiftAttributes", "sizeShiftStep", "colorShiftDeltaE", "maxHueShiftDeg", "shiftSymmetryTolerance", "ratingItem" })
                ((JObject)m["config"]).Remove(k);
            foreach (JObject v in (JArray)m["variants"]) v.Remove("kind");
            string path = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(UnityEngine.Application.streamingAssetsPath), "IFS", "Tests", "Editor", "Golden", golden);
            Assert.That(OwnershipJson.Serialize(m), Is.EqualTo(System.IO.File.ReadAllText(path, System.Text.Encoding.UTF8)));
        }

        [Test]
        public void Stated_chromatic_color_and_stated_size_make_two_valid_pairs()
        {
            var plan = GenShift(StatedSpec(), 3);
            Assert.That(plan.Variants.Select(v => v.Id), Is.EqualTo(OwnershipVariantGenerator.ConditionIds));
            Assert.That(plan.Variants.Select(v => v.Kind), Is.EqualTo(new[] { "orig", "mismatch", "mismatch", "mismatch", "mismatch", "shift", "shift", "shift", "shift" }));
            var color = plan.ShiftPairs[0];
            Assert.That((color.Attribute, color.Axis, color.Basis, color.Valid), Is.EqualTo(("color", "hue", "stated", true)));
            Assert.That(color.W, Is.EqualTo(0.6));
            // lo = 색상 −, hi = 색상 +. 각자 목표 ΔE00 ≥ 12에 닿는 최소 각(≤ 20°), 색상만 바뀐다.
            var lab0 = LabOf(0.6, 0.5, 0.4);
            foreach (var (side, dir) in new[] { ("lo", -1), ("hi", +1) })
            {
                var v = plan.Get("color_" + side);
                double to = v.Override.Numbers["material.color.h"];
                Assert.That(v.Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.h" }));
                int k = (int)v.Detail["steps"];
                Assert.That(k, Is.InRange(1, 20));
                Assert.That(to, Is.EqualTo(Math.Round(0.6 + dir * k / 360.0, 4)).Within(1e-9));
                double de = ColorMetrics.DeltaE2000(lab0, LabOf(to, 0.5, 0.4));
                Assert.That(de, Is.GreaterThanOrEqualTo(12.0));
                Assert.That(ColorMetrics.DeltaE2000(lab0, LabOf(Math.Round(0.6 + dir * (k - 1) / 360.0, 4), 0.5, 0.4)), Is.LessThan(12.0), "최소 각");
                Assert.That((double)v.Magnitude["deltaE00"], Is.EqualTo(Math.Round(de, 3)));
                Assert.That(v.Source, Is.EqualTo("stated"));
            }
            Assert.That(Math.Abs(color.DeltaELo.Value - color.DeltaEHi.Value), Is.LessThanOrEqualTo(3.0));
            Assert.That(color.Lo, Is.EqualTo(plan.Get("color_lo").Override.Numbers["material.color.h"]));
            Assert.That(color.Hi, Is.EqualTo(plan.Get("color_hi").Override.Numbers["material.color.h"]));

            var size = plan.ShiftPairs[1];
            Assert.That((size.Attribute, size.Axis, size.Basis, size.W, size.Lo, size.Hi, size.Step), Is.EqualTo(("size", "size", "stated", 0.3, (double?)0.2, (double?)0.4, (double?)0.1)));
            Assert.That(size.DeltaELo, Is.Null);
            Assert.That(plan.Get("size_lo").Override.Numbers["layout.size"], Is.EqualTo(0.2));
            Assert.That(plan.Get("size_hi").Override.Numbers["layout.size"], Is.EqualTo(0.4));
            // 어긋난 변형은 쌍과 무관하게 0.2와 같다
            var old = GenOk(StatedSpec(), 3);
            for (int i = 0; i < 5; i++)
                Assert.That(JToken.DeepEquals(plan.Variants[i].ToJson(), old.Variants[i].ToJson()), Is.True, plan.Variants[i].Id);
        }

        [Test]
        public void All_default_spec_uses_the_lightness_axis_and_default_basis()
        {
            var plan = GenShift(DefaultSpec(), 3);
            var color = plan.ShiftPairs[0];
            Assert.That((color.Axis, color.Basis, color.W, color.Step, color.Valid), Is.EqualTo(("lightness", "default", 0.7, (double?)0.005, true)));
            Assert.That(color.Lo, Is.LessThan(0.7).And.GreaterThanOrEqualTo(0.05));
            Assert.That(color.Hi, Is.GreaterThan(0.7).And.LessThanOrEqualTo(0.95));
            Assert.That(plan.Get("color_lo").Override.Numbers.Keys, Is.EqualTo(new[] { "material.color.l" }));
            var size = plan.ShiftPairs[1];
            Assert.That((size.Basis, size.W, size.Lo, size.Hi, size.Valid), Is.EqualTo(("default", 0.5, (double?)0.4, (double?)0.6, true)));
        }

        // 크기 쌍: [0, 1] 밖이면 out_of_range, 말한 크기가 0.5를 넘어가면 crosses_category(기본값이면 검사하지 않음).
        [TestCase(0.05, true, "out_of_range")]
        [TestCase(0.95, true, "out_of_range")]
        [TestCase(0.45, true, "crosses_category")]
        [TestCase(0.55, true, "crosses_category")]
        [TestCase(0.4, true, "crosses_category")]   // hi 0.5는 0.5 미만이 아님
        [TestCase(0.39, true, null)]
        [TestCase(0.61, true, null)]
        [TestCase(0.5, true, null)]       // 0.5는 쪽이 없다
        [TestCase(0.45, false, null)]     // 값만 있고 근거 없음 → 기본값 취급
        [TestCase(0.1, true, null)]       // lo 0.0은 범위 안
        public void Size_pair_validity(double w, bool stated, string reason)
        {
            var spec = OwnershipTestSpecs.Empty("SYN-sizepair");
            if (stated) spec.Slot("layout.size", w, "크기");
            else spec["layout"]["size"] = w;
            var plan = GenShift(spec);
            var pair = plan.ShiftPairs.Single(p => p.Attribute == "size");
            Assert.That(pair.SkipReason, Is.EqualTo(reason));
            Assert.That(pair.Valid, Is.EqualTo(reason == null));
            Assert.That(pair.Basis, Is.EqualTo(stated ? "stated" : "default"));
            Assert.That(plan.Get("size_lo") != null, Is.EqualTo(reason == null), "무효면 둘 다 빠진다");
            Assert.That(plan.Get("size_hi") != null, Is.EqualTo(reason == null));
            Assert.That(plan.Order.Length, Is.EqualTo(plan.Variants.Count));
        }

        [Test]
        public void Color_pair_skip_reasons()
        {
            // 연한 유채색: 20° 안에서 ΔE00 12에 못 닿음 → range_exceeded(명도로 대체하지 않음)
            var weak = GenShift(OwnershipTestSpecs.Empty("SYN-cp").Hsl(0.0, 0.12, 0.9));
            Assert.That((weak.ShiftPairs[0].Axis, weak.ShiftPairs[0].SkipReason), Is.EqualTo(("hue", "range_exceeded")));
            Assert.That(weak.Get("color_lo"), Is.Null);
            Assert.That(weak.Get("color_hi"), Is.Null);
            // 무채색이 0.95보다 밝음 → 밝게 갈 수 없음
            var light = GenShift(OwnershipTestSpecs.Empty("SYN-cp").Hsl(0.0, 0.0, 0.97));
            Assert.That((light.ShiftPairs[0].Axis, light.ShiftPairs[0].SkipReason, light.ShiftPairs[0].Hi), Is.EqualTo(("lightness", "range_exceeded", (double?)null)));
            // 허용치 0이면 두 방향 ΔE00이 조금만 달라도 asymmetric
            var asym = GenShift(StatedSpec(), 1, new OwnershipConfig { shiftSymmetryTolerance = 0 });
            Assert.That(asym.ShiftPairs[0].SkipReason, Is.EqualTo("asymmetric"));
            Assert.That(asym.Variants.Count, Is.EqualTo(7));
            // 잘 보이지 않으면(lowVisibility) 두 쌍 모두 not_rendered
            var faint = GenShift(OwnershipTestSpecs.Empty("SYN-cp").Slot("material.opacity", 0.1));
            Assert.That(faint.ShiftPairs.Select(p => p.SkipReason), Is.EqualTo(new[] { "not_rendered", "not_rendered" }));
            Assert.That(faint.Order.Length, Is.EqualTo(5));
            // 꺼진 속성은 disabled(값 없음)
            var off = GenShift(StatedSpec(), 1, new OwnershipConfig { shiftAttributes = new List<string> { "size" } });
            Assert.That((off.ShiftPairs[0].SkipReason, off.ShiftPairs[0].Lo, off.ShiftPairs[0].Step), Is.EqualTo(("disabled", (double?)null, (double?)null)));
            Assert.That(off.ShiftPairs[1].Valid, Is.True);
            Assert.That(off.Variants.Select(v => v.Id).Skip(5), Is.EqualTo(new[] { "size_lo", "size_hi" }));
        }

        [Test]
        public void Shift_config_is_validated()
        {
            Assert.That(new OwnershipConfig().Validate(), Is.Empty);
            Assert.That(new OwnershipConfig().shiftAttributes, Is.EqualTo(new[] { "color", "size" }));
            Assert.That(new OwnershipConfig().ratingItem, Is.EqualTo("resemblance"));
            Assert.That(new OwnershipConfig { shiftAttributes = new List<string> { "motion" } }.Validate().Single(), Does.Contain("motion"));
            Assert.That(new OwnershipConfig { shiftAttributes = new List<string> { "size", "size" } }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { shiftAttributes = null }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { ratingItem = "liking" }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { sizeShiftStep = 0 }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { colorShiftDeltaE = -1 }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { maxHueShiftDeg = 0.5 }.Validate(), Is.Not.Empty);
            Assert.That(new OwnershipConfig { shiftSymmetryTolerance = -0.1 }.Validate(), Is.Not.Empty);
            var a = new OwnershipConfig();
            var b = a.Clone();
            b.shiftAttributes.Clear();
            Assert.That(a.shiftAttributes.Count, Is.EqualTo(2), "Clone은 목록을 복사한다");
            Assert.That(Gen(DefaultSpec(), 1, new OwnershipConfig { ratingItem = "x" }).Ok, Is.False, "설정 오류면 계획을 만들지 않는다");
            Assert.That(WilliamsDesign.MaxConditions, Is.EqualTo(9));
        }

        [Test]
        public void Shift_manifest_is_deterministic_and_hides_pair_direction_from_the_experimenter_line()
        {
            string a = OwnershipJson.Serialize(OwnershipManifest.Build(GenShift(StatedSpec(), 3), ShiftInfo("x")));
            string b = OwnershipJson.Serialize(OwnershipManifest.Build(GenShift(StatedSpec(), 3), ShiftInfo("x")));
            Assert.That(b, Is.EqualTo(a));
            var m = ParseNoDates(a);
            Assert.That(((JObject)m["shiftPairs"][0]).Properties().Select(p => p.Name), Is.EqualTo(new[]
                { "attribute", "axis", "basis", "w", "lo", "hi", "step", "deltaE_lo", "deltaE_hi", "valid", "skipReason" }));
            Assert.That(m["variants"].Select(v => (string)v["kind"]).Distinct(), Is.EqualTo(new[] { "orig", "mismatch", "shift" }));
            Assert.That(((JArray)m["order"]).Count, Is.EqualTo(9));
            var plan = GenShift(StatedSpec(), 3);
            foreach (var id in new[] { "color_lo", "color_hi", "size_lo", "size_hi" })
                Assert.That(plan.Get(id).Describe(), Is.EqualTo(id + ": 같은 말·다른 값 쌍"), "실험자 화면에는 id만");
        }
    }
}
