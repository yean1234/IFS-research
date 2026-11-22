// FormRenderPlan(슬롯 값 → 형상별 렌더러 입력, X64·X65) 테스트. 합성 spec만 쓴다(참여자 데이터 아님).
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class FormRenderPlanTests
    {
        static FormRenderPlan Plan(JObject o)
        {
            var spec = o.Parse();
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            return FormRenderPlan.Build(p, p.GetCategory("form.type"), ShapeMapping.Resolve(spec));
        }

        static string PlanJson(JObject o) => Plan(o).ToJson().ToString(Formatting.None);

        static JObject Mist(string id) =>
            OwnershipTestSpecs.Empty(id).Slot("form.type", "mist", "안개").Slot("material.opacity", 0.6, "흐릿")
                .Hsl(0.6, 0.45, 0.6, "파란").Slot("layout.size", 0.7, "큰");

        [Test]
        public void Same_slot_values_give_the_same_plan_whatever_mapper_produced_them()
        {
            // X65: 렌더러는 매퍼를 모른다. meta.mapping(v0/v1/없음)·pipeline·sessionId만 다르면 계획이 같아야 한다.
            var none = Mist("MAPNONE");
            var v0 = Mist("MAPV0");
            v0["meta"]["mapping"] = new JObject { ["requested"] = "v0", ["used"] = "v0", ["fallbackReason"] = null };
            var v1 = Mist("MAPV1");
            v1["meta"]["mapping"] = new JObject { ["requested"] = "v1", ["used"] = "v1", ["fallbackReason"] = null };
            v1["meta"]["pipeline"]["builder"] = "scene-spec-builder-v1/1.2.0";
            var fallback = Mist("MAPFB");
            fallback["meta"]["mapping"] = new JObject { ["requested"] = "v1", ["used"] = "v0", ["fallbackReason"] = "synthetic" };

            string expected = PlanJson(none);
            Assert.That(PlanJson(v0), Is.EqualTo(expected));
            Assert.That(PlanJson(v1), Is.EqualTo(expected));
            Assert.That(PlanJson(fallback), Is.EqualTo(expected));
            // 근거(_provenance)의 트리거가 달라도(다른 낱말로 같은 값) 같은 계획
            var otherWords = OwnershipTestSpecs.Empty("MAPWORDS").Slot("form.type", "mist", "연기").Slot("material.opacity", 0.6, "옅은")
                .Hsl(0.6, 0.45, 0.6, "푸른").Slot("layout.size", 0.7, "커다란");
            Assert.That(PlanJson(otherWords), Is.EqualTo(expected));
        }

        [Test]
        public void A_different_slot_value_changes_the_plan()
        {
            var a = Mist("DIFFA");
            var b = Mist("DIFFB").Slot("material.opacity", 0.5, "흐릿");
            Assert.That(PlanJson(b), Is.Not.EqualTo(PlanJson(a)));
        }

        [TestCase("blob", "blob")]
        [TestCase("mist", "mist")]
        [TestCase("shell", "shell")]
        [TestCase("fragments", "fragments")]
        public void Form_type_selects_its_renderer(string form, string renderer)
        {
            var plan = Plan(OwnershipTestSpecs.Empty("SEL" + form).Slot("form.type", form, "형태"));
            Assert.That(plan.Renderer, Is.EqualTo(renderer));
            Assert.That(plan.FormType, Is.EqualTo(form));
            Assert.That(plan.ShapeModel, Is.Null);
            Assert.That(FormRenderPlan.FormPresets.ContainsKey(form), Is.True);
        }

        [Test]
        public void Unstated_form_uses_the_default_form_renderer()
        {
            var plan = Plan(OwnershipTestSpecs.Empty("SELNULL"));
            Assert.That(plan.FormType, Is.EqualTo("blob"));   // SceneDefaults.formType
            Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererBlob));
        }

        [TestCase(null, "round", "shapeModel", "Sphere")]
        [TestCase("blob", "square", "shapeModel", "Cube")]
        [TestCase("mist", "square", "mist", null)]        // spec이 형태를 말했으면 그 형태(not_applied_form)
        [TestCase("fragments", "flat", "fragments", null)]
        [TestCase(null, "thread", "blob", null)]          // 표에 없는 모양어(unmapped_shape)
        public void Shape_words_select_the_shape_model_renderer_only_for_blob_or_unstated_form(string form, string shape, string renderer, string model)
        {
            var o = OwnershipTestSpecs.Empty("SHAPE").ShapeWord(shape, "모양", 3);
            if (form != null) o.Slot("form.type", form, "형태");
            var plan = Plan(o);
            Assert.That(plan.Renderer, Is.EqualTo(renderer));
            Assert.That(plan.ShapeModel, Is.EqualTo(model));
            Assert.That(plan.ZeroDisplacement, Is.EqualTo(model != null || renderer == "fragments"));   // 각진 메시는 정점 변위 0
            if (model != null) Assert.That(plan.Preset.Lumpiness, Is.EqualTo(0f));
        }

        [Test]
        public void Changing_form_away_from_the_initial_value_leaves_the_shape_model()
        {
            var spec = OwnershipTestSpecs.Empty("SHAPEADJ").ShapeWord("pointed", "뾰족", 0).Parse();
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            var shape = ShapeMapping.Resolve(spec);
            string initial = p.GetCategory("form.type");
            Assert.That(FormRenderPlan.Build(p, initial, shape).Renderer, Is.EqualTo(FormRenderPlan.RendererShapeModel));
            p.SetCategory("form.type", "mist");
            Assert.That(FormRenderPlan.Build(p, initial, shape).Renderer, Is.EqualTo(FormRenderPlan.RendererMist));
            p.SetCategory("form.type", initial);
            Assert.That(FormRenderPlan.Build(p, initial, shape).Renderer, Is.EqualTo(FormRenderPlan.RendererShapeModel));
        }

        [TestCase("mist", 1.0, true)]
        [TestCase("blob", 1.0, false)]
        [TestCase("blob", 0.6, true)]
        [TestCase("fragments", 0.98, true)]
        public void Fade_follows_the_shared_rule(string form, double opacity, bool fade)
        {
            var plan = Plan(OwnershipTestSpecs.Empty("FADE").Slot("form.type", form, "형태").Slot("material.opacity", opacity, "투명"));
            Assert.That(plan.Fade, Is.EqualTo(fade));
            Assert.That(plan.Fade, Is.EqualTo(RenderedColor.UsesFadeShader(form, opacity)));
        }

        [Test]
        public void Plan_is_deterministic()
        {
            Assert.That(PlanJson(Mist("DET")), Is.EqualTo(PlanJson(Mist("DET"))));
        }

        [Test]
        public void Mist_preset_note_states_what_roughness_means_for_mist()
        {
            string note = Plan(Mist("MISTNOTE")).PresetNote;
            Assert.That(note, Does.Contain("material.roughness는 표면 반사(광택)가 아니라 밀도 노이즈 크기 배율"));
            Assert.That(note, Does.Contain("목표 근사"));
        }

        // 안개 구가 바닥 아래로 걸치면 floorClipped와 잘린 높이 비율(G4). 화면은 바꾸지 않고 기록만 한다.
        [TestCase(0.10, 0.25, 0.0, true, 0.3)]    // 아래 끝 −0.15 → 높이 0.5 중 0.15
        [TestCase(-0.5, 0.25, 0.0, true, 1.0)]    // 구 전체가 바닥 아래
        [TestCase(1.20, 0.25, 0.0, false, 0.0)]   // 가슴 높이
        [TestCase(0.25, 0.25, 0.0, false, 0.0)]   // 바닥에 닿기만 함
        public void Mist_floor_clip_reports_the_clipped_height_fraction(double centerY, double half, double floorY, bool clipped, double fraction)
        {
            var c = MistFloorClip.Measure(centerY, half, floorY);
            Assert.That(c.FloorClipped, Is.EqualTo(clipped));
            Assert.That(c.ClippedHeightFraction, Is.EqualTo(fraction).Within(1e-9));
            Assert.That(c.ToJson().Value<bool>("floorClipped"), Is.EqualTo(clipped));
            if (clipped) Assert.That(c.Note(), Does.Contain("잘린 높이 비율"));
        }
    }
}
