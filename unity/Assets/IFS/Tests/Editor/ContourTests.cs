// (2.3, G61 ①) 윤곽·발광 테스트 — docs/scene-spec-mapping.md 8.4절 7번:
// 슈퍼쿼드릭 메시(정점 수·경계 상자·결정성·면 방향·닫힘·e = 1 구 대조·e = 0.1 상자·규칙 버전 해시), 2.3.0 파싱·검사(엄격 파서,
// 표에 없는 값 = 파싱 오류, provenance.variant, 왕복), 2.2 문서와 세 값이 모두 null인 2.3 문서의 해석값·계획 동일성,
// 윤곽 적용 순서 1–4, defaultsUsed, 발광(바탕색 × 세기, 경로와 무관), 덮어쓰기 키. spec은 합성(참여자 데이터 아님).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class ContourTests
    {
        // ── 슈퍼쿼드릭 메시 ───────────────────────────────────────────────────
        public static IEnumerable<string> Levels() => ContourRender.RoundnessLevels;

        static (float[] xyz, float[] nrm, int[] tris) Mesh(string roundness)
        {
            var (e1, e2) = ContourRender.Exponents(roundness);
            SuperquadricMesh.Build(e1, e2, out var xyz, out var nrm, out var tris);
            return (xyz, nrm, tris);
        }

        [TestCaseSource(nameof(Levels))]
        public void Superquadric_has_the_specified_grid(string level)
        {
            var m = Mesh(level);
            // 경도 48 × 위도 24, 극점 한 점씩: 정점 2 + 23 × 48 = 1,106, 삼각형 2 × 48 + 22 × 48 × 2 = 2,208
            Assert.That(m.xyz.Length / 3, Is.EqualTo(1106));
            Assert.That(m.tris.Length / 3, Is.EqualTo(2208));
            Assert.That(m.tris.Length / 3, Is.LessThanOrEqualTo(BaseShapeMesh.MaxTriangles));
            Assert.That(m.tris.All(i => i >= 0 && i < m.xyz.Length / 3), Is.True);
        }

        [TestCaseSource(nameof(Levels))]
        public void Superquadric_is_deterministic(string level)
        {
            var a = Mesh(level);
            var b = Mesh(level);
            Assert.That(b.xyz, Is.EqualTo(a.xyz));
            Assert.That(b.nrm, Is.EqualTo(a.nrm));
            Assert.That(b.tris, Is.EqualTo(a.tris));
        }

        [TestCaseSource(nameof(Levels))]
        public void Superquadric_bounds_are_the_unit_cube_centered(string level)
        {
            // 지름 1(반축 0.5): 격자에 축 끝(η = 0, ±π/2, ω = 0, ±π/2, −π)이 있어 모든 둥긂 단계에서 경계 상자가 정확히 1 × 1 × 1
            var m = Mesh(level);
            for (int k = 0; k < 3; k++)
            {
                float lo = float.MaxValue, hi = float.MinValue;
                for (int i = k; i < m.xyz.Length; i += 3) { lo = Math.Min(lo, m.xyz[i]); hi = Math.Max(hi, m.xyz[i]); }
                Assert.That(hi - lo, Is.EqualTo(1.0).Within(1e-5), "축 " + k);
                Assert.That((lo + hi) / 2, Is.EqualTo(0.0).Within(1e-5), "축 " + k);
            }
        }

        [TestCaseSource(nameof(Levels))]
        public void Superquadric_faces_agree_with_normals_and_mesh_is_closed(string level)
        {
            var m = Mesh(level);
            for (int i = 0; i < m.nrm.Length; i += 3)
                Assert.That(Math.Sqrt(m.nrm[i] * m.nrm[i] + m.nrm[i + 1] * m.nrm[i + 1] + m.nrm[i + 2] * m.nrm[i + 2]), Is.EqualTo(1.0).Within(1e-4));
            int disagree = 0;
            var edges = new Dictionary<(int, int), int>();
            for (int t = 0; t < m.tris.Length; t += 3)
            {
                int a = m.tris[t], b = m.tris[t + 1], c = m.tris[t + 2];
                double ux = m.xyz[b * 3] - m.xyz[a * 3], uy = m.xyz[b * 3 + 1] - m.xyz[a * 3 + 1], uz = m.xyz[b * 3 + 2] - m.xyz[a * 3 + 2];
                double vx = m.xyz[c * 3] - m.xyz[a * 3], vy = m.xyz[c * 3 + 1] - m.xyz[a * 3 + 1], vz = m.xyz[c * 3 + 2] - m.xyz[a * 3 + 2];
                double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
                Assert.That(Math.Sqrt(cx * cx + cy * cy + cz * cz) / 2, Is.GreaterThan(1e-10), "넓이 0인 삼각형");
                double nx = m.nrm[a * 3] + m.nrm[b * 3] + m.nrm[c * 3], ny = m.nrm[a * 3 + 1] + m.nrm[b * 3 + 1] + m.nrm[c * 3 + 1],
                       nz = m.nrm[a * 3 + 2] + m.nrm[b * 3 + 2] + m.nrm[c * 3 + 2];
                if (cx * nx + cy * ny + cz * nz <= 0) disagree++;
                foreach (var (p, q) in new[] { (a, b), (b, c), (c, a) })
                {
                    var k = p < q ? (p, q) : (q, p);
                    edges[k] = edges.TryGetValue(k, out int n) ? n + 1 : 1;
                }
            }
            Assert.That(disagree, Is.EqualTo(0), "면 방향(cross(b − a, c − a))이 정점 법선과 반대인 삼각형 수");
            Assert.That(edges.Values.Count(n => n != 2), Is.EqualTo(0), "삼각형 둘이 나누지 않는 모서리 수(닫힌 메시)");
        }

        [Test]
        public void Rounded_is_a_unit_diameter_sphere()
        {
            var m = Mesh("rounded");   // e1 = e2 = 1
            for (int i = 0; i < m.xyz.Length; i += 3)
            {
                double r = Math.Sqrt(m.xyz[i] * m.xyz[i] + m.xyz[i + 1] * m.xyz[i + 1] + m.xyz[i + 2] * m.xyz[i + 2]);
                Assert.That(r, Is.EqualTo(0.5).Within(1e-5), "정점 " + i / 3);
                // 구의 해석 법선 = 반지름 방향
                Assert.That(m.nrm[i] * m.xyz[i] + m.nrm[i + 1] * m.xyz[i + 1] + m.nrm[i + 2] * m.xyz[i + 2], Is.EqualTo(0.5).Within(1e-5));
            }
        }

        [Test]
        public void Angular_is_close_to_a_unit_cube()
        {
            var m = Mesh("angular");   // e1 = e2 = 0.1
            // η = π/4, ω = π/4 꼭짓점 방향의 정점: 구라면 (0.25, 0.354, 0.25), 0.1이면 모든 축이 0.46 이상(모서리가 살짝 둥근 정육면체)
            int lon = ContourRender.LongitudeSegments, lat = ContourRender.LatitudeSegments;
            int j = lat * 3 / 4, i = lon * 5 / 8;    // η = −π/2 + j·π/24 = π/4, ω = −π + i·2π/48 = π/4
            int v = 1 + (j - 1) * lon + i;
            Assert.That(m.xyz[v * 3], Is.GreaterThan(0.46f));
            Assert.That(m.xyz[v * 3 + 1], Is.GreaterThan(0.46f));
            Assert.That(m.xyz[v * 3 + 2], Is.GreaterThan(0.46f));
            // 정점 대부분이 경계 상자 겉면 가까이(무한 노름 ≥ 0.45)
            int near = 0;
            for (int k = 0; k < m.xyz.Length; k += 3)
                if (Math.Max(Math.Abs(m.xyz[k]), Math.Max(Math.Abs(m.xyz[k + 1]), Math.Abs(m.xyz[k + 2]))) >= 0.45f) near++;
            Assert.That(near, Is.EqualTo(m.xyz.Length / 3));
        }

        [Test]
        public void Rounder_levels_have_smaller_corners()
        {
            // 서수 순서: angular → rounded로 갈수록 꼭짓점 방향 정점이 원점에 가까워진다
            int lon = ContourRender.LongitudeSegments, lat = ContourRender.LatitudeSegments;
            int v = 1 + (lat * 3 / 4 - 1) * lon + lon * 5 / 8;
            var radii = ContourRender.RoundnessLevels.Select(l =>
            {
                var m = Mesh(l);
                return Math.Sqrt(m.xyz[v * 3] * m.xyz[v * 3] + m.xyz[v * 3 + 1] * m.xyz[v * 3 + 1] + m.xyz[v * 3 + 2] * m.xyz[v * 3 + 2]);
            }).ToList();
            for (int k = 1; k < radii.Count; k++) Assert.That(radii[k], Is.LessThan(radii[k - 1]), ContourRender.RoundnessLevels[k]);
        }

        [Test]
        public void Superquadric_hash_is_pinned_to_the_rule_version()
        {
            // 규칙 버전 superquadric/1 → 단계별 정점 해시. 메시가 바뀌면 ContourRender.MeshRule을 올리고 이 표를 고친다(BaseShapeTests와 같은 방식).
            Assert.That(ContourRender.MeshRule, Is.EqualTo("superquadric/1"));
            var pinned = new Dictionary<string, ulong>
            {
                { "angular", 1892171106452840101UL },
                { "slightly_angular", 4530049877033054725UL },
                { "neutral", 1911050956383486357UL },
                { "slightly_rounded", 394490544179164277UL },
                { "rounded", 2152285165634808885UL },
            };
            var actual = ContourRender.RoundnessLevels.ToDictionary(l => l, l => SuperquadricMesh.Hash(Mesh(l).xyz));
            Assert.That(actual.Values.Distinct().Count(), Is.EqualTo(actual.Count), "단계가 다른데 같은 메시");
            foreach (var kv in pinned) Assert.That(actual[kv.Key], Is.EqualTo(kv.Value), string.Join(" ", actual.Select(a => a.Key + "=" + a.Value + "UL")));
        }

        // ── 2.3.0 spec ─────────────────────────────────────────────────────
        /// <summary>합성 2.3.0 spec(BaseShapeTests.Spec22 꼴 + 세 키). 값이 null이어도 키는 있다.</summary>
        public static string Spec23(string formType = null, string baseShape = null, string roundness = null, string aspect = null,
                                    string emission = null, Action<JObject> edit = null)
        {
            var o = JObject.Parse(BaseShapeTests.Spec22(formType, baseShape, null, "2.3.0"));
            o["form"]["roundness"] = roundness;
            o["form"]["aspect"] = aspect;
            o["material"]["emission"] = emission;
            var prov = (JObject)o["_provenance"];
            JArray P(string trigger, string rule) => new JArray(new JObject
            {
                ["source"] = "explicit_lexicon", ["trigger"] = trigger, ["charSpan"] = new JArray(0, trigger.Length), ["rule"] = rule,
            });
            if (roundness != null) prov["form.roundness"] = P("각진", "contourLexicon.각지>form.roundness:" + roundness);
            if (aspect != null) prov["form.aspect"] = P("길쭉", "contourLexicon.길쭉>form.aspect:" + aspect);
            if (emission != null) prov["material.emission"] = P("빛나", "emissionLexicon.빛나>material.emission:" + emission);
            edit?.Invoke(o);
            return o.ToString();
        }

        /// <summary>같은 내용의 2.2.0 spec(세 키 없음).</summary>
        static string Spec22Of(string formType = null, string baseShape = null, Action<JObject> edit = null)
        {
            var o = JObject.Parse(BaseShapeTests.Spec22(formType, baseShape));
            edit?.Invoke(o);
            return o.ToString();
        }

        [Test]
        public void Spec_23_parses_and_validates()
        {
            var s = SceneSpecJson.Parse(Spec23(null, null, "angular", "elongated", "glowing"));
            Assert.That(s.Form.Roundness, Is.EqualTo("angular"));
            Assert.That(s.Form.Aspect, Is.EqualTo("elongated"));
            Assert.That(s.Material.Emission, Is.EqualTo("glowing"));
            Assert.That(s.Form.ContourKeysPresent && s.Material.EmissionKeyPresent, Is.True);
            Assert.That(SceneSpecJson.Validate(s), Is.Empty);
            var nul = SceneSpecJson.Parse(Spec23());
            Assert.That(nul.Form.Roundness, Is.Null);
            Assert.That(SceneSpecJson.Validate(nul), Is.Empty);
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec23(emission: "none"))), Is.Empty);
        }

        [TestCase("roundness", "pointy")]
        [TestCase("aspect", "tall")]
        [TestCase("emission", "bright")]
        public void Unknown_contour_value_is_a_parse_error(string key, string value)
        {
            var o = JObject.Parse(Spec23());
            if (key == "emission") o["material"][key] = value;
            else o["form"][key] = value;
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(o.ToString()));
        }

        [Test]
        public void Unknown_key_is_still_a_parse_error_in_23()
        {
            var o = JObject.Parse(Spec23());
            o["form"]["particles"] = null;   // 8.7절: 예약하지 않은 자리
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(o.ToString()));
        }

        [Test]
        public void Provenance_variant_is_read_as_an_optional_key()
        {
            string json = Spec23(emission: "faint", edit: o =>
            {
                o["_provenance"]["material.emission"][0]["variant"] = new JObject
                {
                    ["rules"] = new JArray("ideophone_consonant"), ["surface"] = "빤짝빤짝", ["root"] = "반짝반짝", ["grade"] = new JArray("stronger"),
                };
            });
            var s = SceneSpecJson.Parse(json);
            var v = s.Provenance["material.emission"][0].Variant;
            Assert.That(v.Rules, Is.EqualTo(new[] { "ideophone_consonant" }));
            Assert.That(v.Root, Is.EqualTo("반짝반짝"));
            Assert.That(v.Grade, Is.EqualTo(new[] { "stronger" }));
            // 다시 쓰면 그대로, variant가 없는 근거에는 키가 생기지 않는다
            var back = JObject.Parse(SceneSpecJson.Serialize(s));
            Assert.That(back["_provenance"]["material.emission"][0]["variant"]["surface"].ToString(), Is.EqualTo("빤짝빤짝"));
            Assert.That(((JObject)JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(Spec23(emission: "faint"))))["_provenance"]["material.emission"][0])
                .ContainsKey("variant"), Is.False);
            // variant 안의 모르는 키는 엄격 파서가 거부
            var bad = JObject.Parse(json);
            bad["_provenance"]["material.emission"][0]["variant"]["extra"] = 1;
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(bad.ToString()));
        }

        [Test]
        public void Round_trip_keeps_null_keys_for_23_and_none_for_22()
        {
            var back = JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(Spec23())));
            Assert.That(((JObject)back["form"]).ContainsKey("roundness") && ((JObject)back["form"]).ContainsKey("aspect"), Is.True);
            Assert.That(((JObject)back["material"]).ContainsKey("emission"), Is.True);
            Assert.That(back["form"]["roundness"].Type, Is.EqualTo(JTokenType.Null));
            string s22 = Spec22Of();
            var back22 = JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(s22)));
            Assert.That(((JObject)back22["form"]).ContainsKey("roundness"), Is.False);
            Assert.That(((JObject)back22["material"]).ContainsKey("emission"), Is.False);
            Assert.That(JToken.DeepEquals(back22, JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(s22)))))), Is.True);
        }

        [Test]
        public void Validate_flags_version_and_provenance_problems_for_23()
        {
            // 2.3.0인데 키가 없음
            var o = JObject.Parse(Spec23());
            ((JObject)o["material"]).Remove("emission");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o.ToString())), Has.Some.Contains("form.roundness·form.aspect·material.emission이 없다"));
            // 2.2.0에 2.3 키
            var o22 = JObject.Parse(Spec23(roundness: "angular"));
            o22["meta"]["specVersion"] = "2.2.0";
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o22.ToString())), Has.Some.Contains("2.3 전용"));
            // 2.3.0인데 2.2 키(form.base)가 없음
            var nobase = JObject.Parse(Spec23());
            ((JObject)nobase["form"]).Remove("base");
            ((JObject)nobase["form"]).Remove("baseVariant");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(nobase.ToString())), Has.Some.Contains("form.base·form.baseVariant가 없다"));
            // 값은 있는데 근거 없음 / null인데 근거 있음
            var np = JObject.Parse(Spec23(aspect: "flattened"));
            ((JObject)np["_provenance"]).Remove("form.aspect");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(np.ToString())), Has.Some.Contains("form.aspect: 값이 있는데 _provenance가 없다"));
            var pn = JObject.Parse(Spec23(emission: "glowing"));
            pn["material"]["emission"] = null;
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(pn.ToString())), Has.Some.Contains("material.emission: null인데 _provenance가 있다"));
        }

        [Test]
        public void Synthetic_python_23_examples_parse_and_validate()
        {
            // chatbot 매퍼 v2(builder 2.5.0, ext_lexicon + variant_rules 켬)가 합성 문장으로 만든 실제 출력(examples/v2.3)
            string dir = Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "v2.3");
            var files = Directory.GetFiles(dir, "*.json").OrderBy(f => f, StringComparer.Ordinal).ToArray();
            Assert.That(files.Length, Is.GreaterThanOrEqualTo(3));
            foreach (var f in files)
            {
                var s = SceneSpecJson.Load(f);
                Assert.That(s.Meta.SpecVersion, Is.EqualTo("2.3.0"), f);
                Assert.That(SceneSpecJson.Validate(s), Is.Empty, f);
            }
            var ang = SceneSpecJson.Load(Path.Combine(dir, "EX23-angular.json"));
            Assert.That(ang.Form.Roundness, Is.EqualTo("angular"));
            var elo = SceneSpecJson.Load(Path.Combine(dir, "EX23-elongated.json"));
            Assert.That(elo.Form.Aspect, Is.EqualTo("elongated"));
            Assert.That(elo.Provenance["material.emission"].Any(p => p.Variant != null), Is.True, "변이 규칙층 근거(provenance.variant)");
        }

        // ── 2.2 동일성 ─────────────────────────────────────────────────────
        static SceneParams Params(string json) => SceneParams.FromSpec(SceneSpecJson.Parse(json), new SceneDefaults());

        static FormRenderPlan Plan(string json, Action<SceneParams> adjust = null, ShapeResolution shape = null)
        {
            var spec = SceneSpecJson.Parse(json);
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            string initial = p.GetCategory("form.type");
            adjust?.Invoke(p);
            return FormRenderPlan.Build(p, initial, shape ?? ShapeMapping.Resolve(spec));
        }

        static JObject WithoutContour(JObject plan)
        {
            var c = (JObject)plan.DeepClone();
            c.Remove("contour");
            c.Remove("emission");
            return c;
        }

        public static IEnumerable<TestCaseData> SameAs22Cases()
        {
            yield return new TestCaseData(null, null).SetName("기본 덩어리");
            yield return new TestCaseData("mist", null).SetName("mist");
            yield return new TestCaseData("fragments", null).SetName("fragments");
            yield return new TestCaseData(null, "container").SetName("기본 형상");
        }

        [TestCaseSource(nameof(SameAs22Cases))]
        public void All_null_23_document_resolves_like_22(string form, string baseShape)
        {
            string s22 = Spec22Of(form, baseShape), s23 = Spec23(form, baseShape);
            var p22 = Params(s22);
            var p23 = Params(s23);
            Assert.That(JObject.FromObject(p23.ToRecord()).ToString(), Is.EqualTo(JObject.FromObject(p22.ToRecord()).ToString()));
            Assert.That(p23.DefaultsUsed, Is.EqualTo(p22.DefaultsUsed));
            var j22 = Plan(s22).ToJson();
            var plan23 = Plan(s23);
            var j23 = plan23.ToJson();
            Assert.That(j22.ContainsKey("contour"), Is.False, "2.2 계획에는 contour 키가 없다");
            Assert.That(WithoutContour(j23).ToString(), Is.EqualTo(j22.ToString()), "contour·emission 말고 같은 계획");
            Assert.That(plan23.ContourStatus, Is.EqualTo("none"));
            Assert.That(plan23.AxisRatios, Is.Null);
            Assert.That(plan23.EmissionLinear, Is.Null, "발광 null → 셰이더 값을 건드리지 않음");
            Assert.That(plan23.ContourDefaultsUsed, Is.Empty);
            Assert.That(j23["contour"].ToString(Newtonsoft.Json.Formatting.None),
                Is.EqualTo("{\"status\":\"none\",\"roundness\":null,\"aspect\":null,\"mesh\":null,\"e1\":null,\"e2\":null,\"axisRatios\":null}"));
            Assert.That(j23["emission"].ToString(Newtonsoft.Json.Formatting.None), Is.EqualTo("{\"level\":null,\"intensity\":null,\"colorSource\":null}"));
        }

        [Test]
        public void Emission_none_keeps_the_22_plan_and_a_black_emission_term()
        {
            var plan = Plan(Spec23(emission: "none"));
            Assert.That(WithoutContour(plan.ToJson()).ToString(), Is.EqualTo(Plan(Spec22Of()).ToJson().ToString()));
            Assert.That(plan.EmissionIntensity, Is.EqualTo(0.0));
            Assert.That(plan.EmissionLinear, Is.EqualTo(new[] { 0.0, 0.0, 0.0 }));
            Assert.That(plan.EmissionSrgb(out float r, out float g, out float b), Is.True);
            Assert.That(new[] { r, g, b }, Is.All.EqualTo(0f));
        }

        // ── 적용 순서(8.4절 2번) ───────────────────────────────────────────
        [TestCase("mist")]
        [TestCase("shell")]
        [TestCase("fragments")]
        public void Rule_1_other_form_types_record_not_applied_form(string form)
        {
            var plan = Plan(Spec23(form, null, "angular", "elongated"));
            Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererFor(form)));
            Assert.That(plan.ContourStatus, Is.EqualTo("not_applied_form"));
            Assert.That(plan.E1, Is.Null);
            Assert.That(plan.AxisRatios, Is.Null);
            Assert.That(plan.ContourMesh, Is.Null);
            Assert.That(plan.ContourDefaultsUsed, Is.Empty);
            Assert.That(plan.ContourJson()["roundness"].ToString(), Is.EqualTo("angular"), "말한 값은 남는다");
        }

        [Test]
        public void Rule_2_base_shape_records_not_applied_base()
        {
            foreach (var form in new[] { null, "blob" })
            {
                var plan = Plan(Spec23(form, "container", "rounded", "flattened"));
                Assert.That(plan.Renderer, Is.EqualTo("base:container"));
                Assert.That(plan.ContourStatus, Is.EqualTo("not_applied_base"));
                Assert.That(plan.AxisRatios, Is.Null);
            }
        }

        [Test]
        public void Rule_3_shape_model_records_not_applied_model()
        {
            // '둥근'(round → Sphere)은 모양 모형 낱말이면서 윤곽어: 모형을 지키고 같은 말을 두 번 적용하지 않는다
            var model = ShapeMapping.Resolve(new[] { new ShapeWord("round", "둥근", 0, 2) }, null, null);
            var plan = Plan(Spec23(null, null, "rounded", "elongated"), null, model);
            Assert.That(plan.Renderer, Is.EqualTo("shapeModel"));
            Assert.That(plan.ShapeModel, Is.EqualTo("Sphere"));
            Assert.That(plan.ContourStatus, Is.EqualTo("not_applied_model"));
            Assert.That(plan.AxisRatios, Is.Null, "길쭉함도 그리지 않음(기록에는 남음)");
            var flat = ShapeMapping.Resolve(new[] { new ShapeWord("flat", "납작", 0, 2) }, null, null);
            Assert.That(Plan(Spec23(null, null, null, "flattened"), null, flat).ContourStatus, Is.EqualTo("not_applied_model"), "납작 원기둥을 또 납작하게 만들지 않음");
        }

        [Test]
        public void Rule_4_roundness_draws_a_superquadric()
        {
            foreach (var form in new[] { null, "blob" })
            {
                var plan = Plan(Spec23(form, null, "angular"));
                Assert.That(plan.Renderer, Is.EqualTo("superquadric"));
                Assert.That(plan.ContourStatus, Is.EqualTo("applied"));
                Assert.That(plan.ContourMesh, Is.EqualTo("superquadric/1"));
                Assert.That(plan.E1, Is.EqualTo(0.1));
                Assert.That(plan.E2, Is.EqualTo(0.1));
                Assert.That(plan.ZeroDisplacement, Is.True);
                Assert.That(plan.Preset.Lumpiness, Is.EqualTo(0f));
                Assert.That(plan.AxisRatios, Is.Null);
                Assert.That(plan.ContourDefaultsUsed, Is.EqualTo(new[] { "form.aspect" }));
            }
            // 반투명이면 Fade 셰이더(다른 형상과 같은 판정)
            var fade = Plan(Spec23(null, null, "rounded"), p => p.SetNumber("material.opacity", 0.5));
            Assert.That(fade.Fade, Is.True);
        }

        [Test]
        public void Rule_4_aspect_only_scales_the_default_blob()
        {
            var plan = Plan(Spec23(null, null, null, "elongated"));
            Assert.That(plan.Renderer, Is.EqualTo("blob"), "말하지 않은 둥긂을 바꾸지 않음");
            Assert.That(plan.ContourMesh, Is.EqualTo("default"));
            Assert.That(plan.E1, Is.Null);
            Assert.That(plan.AxisRatios, Is.EqualTo(new[] { 0.5, 1.0, 0.5 }));
            Assert.That(plan.ZeroDisplacement, Is.False, "기본 덩어리 노이즈 그대로");
            Assert.That(plan.ContourDefaultsUsed, Is.EqualTo(new[] { "form.roundness", "form.aspect.axis" }));
            // 계획의 나머지(색·프리셋·렌더러)는 2.2 기본 덩어리와 같다
            Assert.That(((JObject)WithoutContour(plan.ToJson())).ToString(), Is.EqualTo(Plan(Spec22Of()).ToJson().ToString()));
        }

        [Test]
        public void Both_slots_give_superquadric_with_axis_ratios()
        {
            var plan = Plan(Spec23(null, null, "slightly_rounded", "flattened"));
            Assert.That(plan.Renderer, Is.EqualTo("superquadric"));
            Assert.That(plan.E1, Is.EqualTo(0.75));
            Assert.That(plan.AxisRatios, Is.EqualTo(new[] { 1.0, 0.4, 1.0 }));
            Assert.That(plan.ContourDefaultsUsed, Is.EqualTo(new[] { "form.aspect.axis" }));
            Assert.That(plan.ToJson()["contour"].ToString(Newtonsoft.Json.Formatting.None),
                Is.EqualTo("{\"status\":\"applied\",\"roundness\":\"slightly_rounded\",\"aspect\":\"flattened\",\"mesh\":\"superquadric/1\",\"e1\":0.75,\"e2\":0.75,\"axisRatios\":[1.0,0.4,1.0]}"));
        }

        [Test]
        public void Adjusting_form_type_moves_between_rules()
        {
            var s = Spec23(null, null, "angular");
            Assert.That(Plan(s, p => p.SetCategory("form.type", "mist")).ContourStatus, Is.EqualTo("not_applied_form"));
            Assert.That(Plan(s, p => { p.SetCategory("form.type", "mist"); p.SetCategory("form.type", "blob"); }).Renderer, Is.EqualTo("superquadric"));
        }

        // ── 발광(8.4절 4번) ────────────────────────────────────────────────
        [Test]
        public void Emission_is_base_color_times_intensity_on_every_path()
        {
            string Color(JObject o)
            {
                o["material"]["color"] = new JObject { ["h"] = 0.6, ["s"] = 0.5, ["l"] = 0.4 };
                o["_provenance"]["material.color"] = new JArray(new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = "파란", ["charSpan"] = new JArray(0, 2), ["rule"] = "synthetic.파란",
                });
                return null;
            }
            foreach (var form in new[] { null, "mist", "shell", "fragments" })
                foreach (var level in ContourRender.EmissionLevels)
                {
                    var plan = Plan(Spec23(form, null, null, null, level, o => Color(o)));
                    double k = ContourRender.EmissionIntensity(level);
                    RenderedColor.AlbedoSrgb(0.6, 0.5, 0.4, 0.5, out double r, out double g, out double b);
                    Assert.That(plan.EmissionIntensity, Is.EqualTo(k));
                    Assert.That(plan.EmissionColorSource, Is.EqualTo("said"));
                    Assert.That(plan.EmissionLinear[0], Is.EqualTo(ColorMetrics.SrgbToLinear(r) * k).Within(1e-12), form + " " + level);
                    Assert.That(plan.EmissionLinear[1], Is.EqualTo(ColorMetrics.SrgbToLinear(g) * k).Within(1e-12));
                    Assert.That(plan.EmissionLinear[2], Is.EqualTo(ColorMetrics.SrgbToLinear(b) * k).Within(1e-12));
                }
            // 색을 말하지 않았으면 기본색(바탕색 그대로)이고 출처는 default. 새 색을 만들지 않는다(무채색이면 발광도 무채색)
            var gray = Plan(Spec23(emission: "glowing"));
            Assert.That(gray.EmissionColorSource, Is.EqualTo("default"));
            Assert.That(gray.EmissionLinear[0], Is.EqualTo(gray.EmissionLinear[1]).And.EqualTo(gray.EmissionLinear[2]));
            Assert.That(gray.EmissionIntensity, Is.EqualTo(1.0));
            // 기본 형상·모양 모형 경로에도
            Assert.That(Plan(Spec23(null, "container", emission: "faint")).EmissionIntensity, Is.EqualTo(0.35));
            // 세기 표: none 0, faint 0.35, glowing 1
            Assert.That(ContourRender.EmissionLevels.Select(ContourRender.EmissionIntensity), Is.EqualTo(new[] { 0.0, 0.35, 1.0 }));
        }

        [Test]
        public void Emission_follows_brightness_and_saturation_slots()
        {
            var dim = Plan(Spec23(emission: "glowing"), p => p.SetNumber("material.brightness", 0.1));
            var lit = Plan(Spec23(emission: "glowing"));
            Assert.That(dim.EmissionLinear[0], Is.LessThan(lit.EmissionLinear[0]), "밝기 배율(셰이더 알베도 식)이 바탕색에 들어감");
            var sat = Plan(Spec23(emission: "glowing"), p => { p.SetNumber("material.color.s", 0.8); p.SetNumber("material.color.h", 0.0); });
            Assert.That(sat.EmissionLinear[0], Is.GreaterThan(sat.EmissionLinear[2]), "채도·덮어쓰기까지 반영한 바탕색");
        }

        // ── SceneParams·덮어쓰기 ─────────────────────────────────────────────
        [Test]
        public void Scene_params_keep_contour_values_out_of_the_record()
        {
            var p = Params(Spec23(null, null, "angular", null, "faint"));
            Assert.That(p.HasContourSlots, Is.True);
            Assert.That(p.GetCategory("form.roundness"), Is.EqualTo("angular"));
            Assert.That(p.GetCategory("form.aspect"), Is.Null, "말하지 않은 값은 기본값으로 채우지 않는다");
            Assert.That(p.ToRecord().ContainsKey("form.roundness"), Is.False);
            Assert.That(p.DefaultsUsed, Has.No.Member("form.roundness").And.No.Member("form.aspect"));
            Assert.That(Params(Spec22Of()).HasContourSlots, Is.False);
            Assert.That(p.Clone().HasContourSlots, Is.True);
        }

        [Test]
        public void Override_json_accepts_contour_keys()
        {
            var o = SceneOverrideJson.Parse("{\"form.roundness\":\"angular\",\"form.aspect\":\"flattened\",\"material.emission\":\"none\"}", out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(o.Categories["material.emission"], Is.EqualTo("none"));
            Assert.That(SceneOverrideJson.Parse("{\"form.roundness\":\"pointy\"}", out var e2), Is.Null);
            Assert.That(e2, Has.Some.Contains("모르는 form.roundness"));
            // 2.2 spec에 덮어쓰기로 윤곽을 정하면 계획에 나온다(HasContourSlots)
            var p = Params(Spec22Of());
            Assert.That(o.ApplyTo(p), Is.EquivalentTo(new[] { "form.roundness", "form.aspect", "material.emission" }));
            Assert.That(p.HasContourSlots, Is.True);
            var plan = FormRenderPlan.Build(p, "blob", null);
            Assert.That(plan.Renderer, Is.EqualTo("superquadric"));
            Assert.That(plan.EmissionIntensity, Is.EqualTo(0.0));
            Assert.Throws<ArgumentException>(() => p.SetCategory("form.aspect", "tall"));
            Assert.That(SceneParams.ChangedCategories(Params(Spec22Of()), p), Is.EquivalentTo(new[] { "form.roundness", "form.aspect", "material.emission" }));
        }
    }
}
