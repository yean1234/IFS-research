// (2.4 선택 슬롯, G74) 안개 입자 모양(form.mistKind) 테스트: 파싱·검사(닫힌 목록, 2.4.0에만, 값 ⇔ 근거), 해석값·기록(키가 있을 때만),
// 덮어쓰기, 렌더 계획(fog·smoke = 안개 셰이더 + 종류별 프리셋, dust = 알갱이 메시, cloud·null = 2.4 이전 계획, 형태가 mist가 아니면 기록만),
// 덩어리 배치(fog 넓고 낮게, smoke 세로 기둥, 대리 구 안), 알갱이 메시(결정론, 비율은 자리만 늘임), 셰이더 소스(프로퍼티 이름·기본값).
// spec은 합성(참여자 데이터 아님).
using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class MistKindsTests
    {
        /// <summary>합성 2.4.0 spec + form.mistKind(키를 넣을 때만). kind = null이면 키만 넣고 값 null.</summary>
        static string Spec(string formType, string kind, bool key = true, double[] p = null, string version = "2.4.0")
        {
            var o = JObject.Parse(ProportionsTests.Spec24(formType, p));
            o["meta"]["specVersion"] = version;
            if (key) o["form"]["mistKind"] = kind;
            if (kind != null)
                o["_provenance"]["form.mistKind"] = new JArray(new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = "연기", ["charSpan"] = new JArray(0, 2), ["rule"] = "mistKinds.연기>form.mistKind:" + kind,
                });
            return o.ToString();
        }

        static SceneParams Params(string json) => SceneParams.FromSpec(SceneSpecJson.Parse(json), new SceneDefaults());

        static FormRenderPlan Plan(string json)
        {
            var p = Params(json);
            return FormRenderPlan.Build(p, p.GetCategory("form.type"), ShapeMapping.Resolve(SceneSpecJson.Parse(json)));
        }

        // ── 파싱·검사 ────────────────────────────────────────────────────────
        [Test]
        public void Parses_validates_and_round_trips()
        {
            foreach (var k in MistKinds.Values)
            {
                var s = SceneSpecJson.Parse(Spec("mist", k));
                Assert.That(s.Form.MistKind, Is.EqualTo(k));
                Assert.That(s.Form.MistKindKeyPresent, Is.True);
                Assert.That(SceneSpecJson.Validate(s), Is.Empty, k);
            }
            var n = SceneSpecJson.Parse(Spec("mist", null));
            Assert.That(n.Form.MistKind, Is.Null);
            Assert.That(SceneSpecJson.Validate(n), Is.Empty, "키만 있고 값 null");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec("mist", null, key: false))), Is.Empty, "2.4.0에서 선택(키 없음)");
        }

        [Test]
        public void Unknown_value_is_a_parse_error()
        {
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(Spec("mist", "steam")));
        }

        [Test]
        public void Older_documents_and_missing_provenance_are_problems()
        {
            var o = JObject.Parse(Spec("mist", "fog"));
            o["meta"]["specVersion"] = "2.2.0";
            ((JObject)o["layout"]).Remove("proportions");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o.ToString())), Has.Some.Contains("2.4 선택 필드(form.mistKind)"));
            var np = JObject.Parse(Spec("mist", "fog"));
            ((JObject)np["_provenance"]).Remove("form.mistKind");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(np.ToString())), Has.Some.Contains("form.mistKind: 값이 있는데 _provenance가 없다"));
        }

        // ── 해석값·기록·덮어쓰기 ──────────────────────────────────────────────
        [Test]
        public void Params_record_the_slot_only_when_the_key_is_present()
        {
            var with = Params(Spec("mist", "smoke"));
            Assert.That(with.HasMistKindSlot, Is.True);
            Assert.That(with.GetCategory(MistKinds.Key), Is.EqualTo("smoke"));
            Assert.That(with.ToRecord()[MistKinds.Key], Is.EqualTo("smoke"));
            Assert.That(with.DefaultsUsed, Has.No.Member(MistKinds.Key));
            var nul = Params(Spec("mist", null));
            Assert.That(nul.ToRecord().ContainsKey(MistKinds.Key), Is.True);
            Assert.That(nul.DefaultsUsed, Has.Member(MistKinds.Key), "말하지 않음 → cloud와 같은 그림(기본값)");
            var none = Params(Spec("mist", null, key: false));
            Assert.That(none.HasMistKindSlot, Is.False);
            Assert.That(none.ToRecord().ContainsKey(MistKinds.Key), Is.False, "키가 없는 문서의 기록은 그대로");
            Assert.That(none.DefaultsUsed, Has.No.Member(MistKinds.Key));
        }

        [Test]
        public void Override_sets_kind_and_rejects_unknown()
        {
            var o = SceneOverrideJson.Parse("{\"form.mistKind\":\"dust\",\"form.type\":\"mist\"}", out var errs);
            Assert.That(errs, Is.Empty);
            var p = Params(Spec("blob", null, key: false));
            o.ApplyTo(p);
            Assert.That(p.HasMistKindSlot, Is.True);
            Assert.That(p.GetCategory(MistKinds.Key), Is.EqualTo("dust"));
            Assert.That(SceneOverrideJson.Parse("{\"form.mistKind\":\"steam\"}", out var bad), Is.Null);
            Assert.That(bad, Has.Some.Contains("모르는 form.mistKind"));
            var init = Params(Spec("mist", "fog"));
            var fin = init.Clone();
            fin.SetCategory(MistKinds.Key, "smoke");
            Assert.That(SceneParams.ChangedCategories(init, fin), Has.Member(MistKinds.Key));
        }

        // ── 렌더 계획 ────────────────────────────────────────────────────────
        static JObject Core(FormRenderPlan p)
        {
            var o = p.ToJson();
            o.Remove("mistKind");
            return o;
        }

        [Test]
        public void Cloud_and_null_keep_the_pre_24_plan()
        {
            var before = Plan(Spec("mist", null, key: false));
            Assert.That(before.ToJson().ContainsKey("mistKind"), Is.False);
            foreach (var k in new[] { "cloud", null })
            {
                var plan = Plan(Spec("mist", k));
                Assert.That(JToken.DeepEquals(Core(plan), before.ToJson()), Is.True, k ?? "null");
                Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererMist));
                Assert.That(plan.MistShape, Is.Null, "셰이더 기본값(cloud)");
                Assert.That(plan.ToJson()["mistKind"]["status"].Value<string>(), Is.EqualTo(k == null ? MistKinds.StatusNone : MistKinds.StatusApplied));
            }
            Assert.That(Plan(Spec("mist", "cloud")).MistLumpLayout(), Is.EqualTo(MistLumps.Build(MistLumps.DefaultSeed)));
        }

        [TestCase("fog", "fog5/1")]
        [TestCase("smoke", "smoke5/1")]
        public void Fog_and_smoke_use_the_mist_shader_with_kind_presets(string kind, string rule)
        {
            var plan = Plan(Spec("mist", kind));
            Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererMist));
            Assert.That(plan.MistKind, Is.EqualTo(kind));
            Assert.That(plan.MistRule, Is.EqualTo(rule));
            Assert.That(plan.MistShape.EdgeRampMul, Is.GreaterThan(1.0), "가장자리를 넓혀 부드럽게");
            Assert.That(plan.Preset.Density, Is.EqualTo(MistKinds.Preset(kind).Density));
            var j = plan.ToJson();
            Assert.That(j["mistRule"]["version"].Value<string>(), Is.EqualTo(rule));
            Assert.That(j["mistKind"]["kind"].Value<string>(), Is.EqualTo(kind));
            Assert.That(j["mistKind"]["shape"], Is.Not.Null);
            Assert.That(plan.PresetNote, Does.Contain("form.mistKind=" + kind));
            Assert.That(JToken.DeepEquals(Core(plan), Plan(Spec("mist", null, key: false)).ToJson()), Is.False, "그림이 달라진다");
        }

        [Test]
        public void Dust_is_a_grain_mesh_and_proportions_stretch_only_the_placement()
        {
            var plan = Plan(Spec("mist", "dust"));
            Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererMistDust));
            Assert.That(plan.ZeroDisplacement, Is.True);
            Assert.That(plan.Fade, Is.True, "form.type mist → 반투명 셰이더, 알파 = opacity(밀도 1, 가장자리 흐림 0)");
            Assert.That(plan.Preset.Density, Is.EqualTo(1f));
            Assert.That(plan.Preset.Fuzz, Is.EqualTo(0f));
            Assert.That(plan.ToJson()["mistRule"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That(plan.ToJson()["mistKind"]["dust"]["version"].Value<string>(), Is.EqualTo(DustMesh.RuleVersion));
            var wide = Plan(Spec("mist", "dust", p: new[] { 1.0, 0.3, 1.0 }));
            Assert.That(wide.ProportionsMethod, Is.EqualTo(ProportionsRender.MethodFragmentDistribution));
        }

        [TestCase("blob")]
        [TestCase("fragments")]
        [TestCase(null)]
        public void Kind_is_only_recorded_when_the_form_is_not_mist(string form)
        {
            var plan = Plan(Spec(form, "smoke"));
            Assert.That(plan.MistKindStatus, Is.EqualTo(MistKinds.StatusNotAppliedForm));
            Assert.That(plan.MistKind, Is.Null);
            Assert.That(JToken.DeepEquals(Core(plan), Plan(Spec(form, null, key: false)).ToJson()), Is.True, "그림은 그대로");
        }

        // ── 덩어리 배치 ──────────────────────────────────────────────────────
        static (double w, double h) Extent(string kind)
        {
            var l = MistKinds.BuildLumps(kind, 0);
            double maxXZ = 0, maxY = 0;
            for (double x = -0.75; x <= 0.75; x += 0.025)
                for (double y = -0.75; y <= 0.75; y += 0.025)
                    for (double z = -0.75; z <= 0.75; z += 0.05)
                        if (MistKinds.ShapeDensity(kind, l, x, y, z) > 0.05)
                        {
                            maxXZ = Math.Max(maxXZ, Math.Sqrt(x * x + z * z));
                            maxY = Math.Max(maxY, Math.Abs(y));
                        }
            return (maxXZ, maxY);
        }

        [Test]
        public void Fog_is_wide_and_low_smoke_is_a_tall_column()
        {
            var fog = Extent("fog");
            var smoke = Extent("smoke");
            Assert.That(fog.w, Is.GreaterThan(2.0 * fog.h), "fog: 가로가 세로의 두 배 넘게");
            Assert.That(smoke.h, Is.GreaterThan(1.5 * smoke.w), "smoke: 세로 기둥");
            // fog의 밀도 무게중심은 물체 가운데보다 아래(낮게 깔림)
            var l = MistKinds.BuildLumps("fog", 0);
            double sy = 0, sw = 0;
            for (double x = -0.7; x <= 0.7; x += 0.05) for (double y = -0.7; y <= 0.7; y += 0.025) for (double z = -0.7; z <= 0.7; z += 0.05)
            {
                double d = MistKinds.ShapeDensity("fog", l, x, y, z);
                sy += d * y; sw += d;
            }
            Assert.That(sy / sw, Is.LessThan(-0.05));
        }

        [TestCase("fog")]
        [TestCase("smoke")]
        public void Lumps_stay_inside_the_proxy_sphere_and_are_deterministic(string kind)
        {
            for (int seed = 0; seed < 20; seed++)
            {
                var l = MistKinds.BuildLumps(kind, seed);
                Assert.That(l, Is.EqualTo(MistKinds.BuildLumps(kind, seed)));
                var s = MistKinds.Shape(kind);
                for (int k = 0; k < MistLumps.Count; k++)
                {
                    // 밀도장 공간의 끝이 물체 좌표 끝의 상한(squash ≥ 1) — 대리 구 안(노이즈 여유를 뺀 MaxExtent)
                    double x = l[k * 4], y = l[k * 4 + 1], z = l[k * 4 + 2], r = l[k * 4 + 3];
                    Assert.That(Math.Sqrt(x * x + z * z) + r, Is.LessThanOrEqualTo(MistLumps.MaxExtent + 1e-9), $"{kind} seed {seed} lump {k} 가로");
                    Assert.That(Math.Abs(y / s.Squash[1]) + r / s.Squash[1], Is.LessThanOrEqualTo(MistLumps.MaxExtent + 1e-9), $"{kind} seed {seed} lump {k} 세로");
                }
                Assert.That(s.Squash.All(v => v >= 1.0), Is.True, "셰이더 구간 상한이 성립하려면 squash ≥ 1");
            }
            Assert.That(MistKinds.BuildLumps(kind, 1), Is.Not.EqualTo(MistKinds.BuildLumps(kind, 0)));
        }

        // ── 알갱이 메시 ──────────────────────────────────────────────────────
        [Test]
        public void Dust_mesh_is_deterministic_bounded_and_stretches_only_positions()
        {
            DustMesh.Build(0, DustMesh.DefaultGrains, null, out var a, out var na, out var ta, out var ga);
            DustMesh.Build(0, DustMesh.DefaultGrains, null, out var b, out _, out _, out _);
            Assert.That(DustMesh.Hash(a), Is.EqualTo(DustMesh.Hash(b)));
            DustMesh.Build(1, DustMesh.DefaultGrains, null, out var c, out _, out _, out _);
            Assert.That(DustMesh.Hash(c), Is.Not.EqualTo(DustMesh.Hash(a)));
            Assert.That(ta.Length, Is.EqualTo(DustMesh.DefaultGrains * 8 * 3));
            Assert.That(ga.Max(), Is.EqualTo(DustMesh.DefaultGrains - 1));
            double reach = 0;
            for (int i = 0; i < a.Length; i += 3) reach = Math.Max(reach, Math.Sqrt(a[i] * a[i] + a[i + 1] * a[i + 1] + a[i + 2] * a[i + 2]));
            Assert.That(reach, Is.LessThan(DustMesh.PlacementRadius + 1.3 * DustMesh.GrainRadiusMax + 1e-6));
            // 법선은 단위 길이
            for (int i = 0; i < na.Length; i += 3)
                Assert.That(Math.Sqrt(na[i] * na[i] + na[i + 1] * na[i + 1] + na[i + 2] * na[i + 2]), Is.EqualTo(1.0).Within(1e-4));
            // 비율: 알갱이 모양(알갱이 안 정점 사이 벡터)은 그대로, 자리만 늘어남
            var p = new[] { 1.0, 0.3, 1.0 };
            DustMesh.Build(0, DustMesh.DefaultGrains, p, out var s, out _, out _, out _);
            for (int v = 1; v < 24; v++)
                for (int k = 0; k < 3; k++)
                    Assert.That(s[v * 3 + k] - s[k], Is.EqualTo(a[v * 3 + k] - a[k]).Within(1e-5));
            DustMesh.Bounds(0, DustMesh.DefaultGrains, p, out _, out var size);
            Assert.That(size[1], Is.LessThan(0.5 * size[0]));
        }

        // ── 셰이더 소스 ──────────────────────────────────────────────────────
        [Test]
        public void Shader_declares_kind_properties_with_identity_defaults()
        {
            string src = File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "..", "IFS", "Runtime", "Resources", "IFS", "SceneSpecMist.shader"));
            Assert.That(src, Does.Contain(FormRenderResources.MistEdgeRampMulProperty + " (\"Edge Ramp Mul\", Range(0.2, 4)) = 1"));
            Assert.That(src, Does.Contain(FormRenderResources.MistSquashProperty + " (\"Squash\", Vector) = (1, 1, 1, 0)"));
            Assert.That(src, Does.Contain(FormRenderResources.MistNoiseStretchProperty + " (\"Noise Stretch\", Vector) = (1, 1, 1, 0)"));
            Assert.That(src, Does.Contain(FormRenderResources.MistTwistProperty + " (\"Twist\", Float) = 0"));
            Assert.That(src, Does.Contain(FormRenderResources.MistStrandsProperty + " (\"Strands\", Range(0, 1)) = 0"));
            Assert.That(src, Does.Contain(FormRenderResources.MistHeightFadeProperty + " (\"Height Fade\", Vector) = (0, 0, 0, 0)"));
            Assert.That(src, Does.Contain("float3 ps = p * _Squash.xyz;"));
            Assert.That(src, Does.Contain("saturate(f / (IFS_MIST_EDGE_RAMP * _EdgeRampMul))"));
            // C# 기본값(cloud)이 셰이더 기본값과 같다
            var d = MistShape.Default;
            Assert.That(d.EdgeRampMul, Is.EqualTo(1.0));
            Assert.That(d.Squash, Is.EqualTo(new[] { 1.0, 1.0, 1.0 }));
            Assert.That(d.NoiseStretch, Is.EqualTo(new[] { 1.0, 1.0, 1.0 }));
            Assert.That(d.Twist, Is.EqualTo(0.0));
            Assert.That(d.Strands, Is.EqualTo(0.0));
            Assert.That(d.HeightFade, Is.EqualTo(new[] { 0.0, 0.0 }));
        }
    }
}
