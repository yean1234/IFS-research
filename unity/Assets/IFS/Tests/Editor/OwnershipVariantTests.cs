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
        static OwnershipPlan Gen(JObject spec, int participant = 1, OwnershipConfig cfg = null) =>
            OwnershipVariantGenerator.Generate(spec.Parse(), participant, cfg ?? new OwnershipConfig());

        static OwnershipPlan GenOk(JObject spec, int participant = 1, OwnershipConfig cfg = null)
        {
            var p = Gen(spec, participant, cfg);
            Assert.That(p.Errors, Is.Empty, string.Join("\n", p.Errors));
            Assert.That(p.Variants.Select(v => v.Id), Is.EqualTo(new[] { "orig", "form", "color", "size", "motion" }));
            return p;
        }

        static Lab LabOf(double h, double s, double l)
        {
            SceneParams.HslToRgb(h, s, l, out double r, out double g, out double b);
            return ColorMetrics.SrgbToLab(r, g, b);
        }

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
        [TestCase(11, 0, 0)]
        [TestCase(14, 1, 3)]
        public void Participant_number_sets_balance_bit_and_order_row(int n, int cb, int row)
        {
            var p = GenOk(OwnershipTestSpecs.Empty("SYN-order"), n);
            Assert.That(p.Cb, Is.EqualTo(cb));
            Assert.That(p.OrderRow, Is.EqualTo(row));
            Assert.That(p.Order, Is.EqualTo(WilliamsDesign.Rows[row].Select(i => WilliamsDesign.Conditions[i]).ToArray()));
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
                "startedAtUtc", "headSource", "unityVersion", "taskText", "config", "flags", "original", "variants", "order",
            }));
            Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-ownership/0.1"));
            Assert.That((string)m["generatorVersion"], Is.EqualTo("ownership-variants/0.1"));
            Assert.That((string)m["specFile"], Is.EqualTo("SYN-det.json"));
            foreach (var k in new[] { "sizeStep", "colorDeltaE", "viewSeconds", "headSampleHz", "gazeConeDeg", "finalChoiceArcDeg", "differenceRating", "generatorVersion" })
                Assert.That(m["config"][k], Is.Not.Null, "config." + k);
            Assert.That(m["flags"]["lowVisibility"], Is.Not.Null);
            foreach (var k in new[] { "params", "shapeModel", "statedKeys", "defaultKeys", "unmappedCount", "unmatchedCount" })
                Assert.That(m["original"][k], Is.Not.Null, "original." + k);
            var orig = (JObject)m["variants"][0];
            Assert.That((string)orig["id"], Is.EqualTo("orig"));
            Assert.That(orig["attribute"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(((JObject)orig["overrides"]).Count, Is.EqualTo(0));
            Assert.That(orig["shapeModel"].Type, Is.EqualTo(JTokenType.Null));
            foreach (JObject v in ((JArray)m["variants"]).Skip(1))
                foreach (var k in new[] { "id", "attribute", "overrides", "shapeModel", "changedKeys", "from", "to", "rule", "source", "sourceByKey", "flags", "magnitude" })
                    Assert.That(v.ContainsKey(k), Is.True, (string)v["id"] + "." + k);
            Assert.That(((JArray)m["order"]).Count, Is.EqualTo(5));
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
    }
}
