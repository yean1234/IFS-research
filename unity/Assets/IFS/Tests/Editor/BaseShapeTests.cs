// 기본 형상(form.base, SceneSpec 2.2.0 — D6, 결정 G21·G22·G30) 테스트: 메시 결정성·삼각형 상한·바운즈·면 방향,
// 2.2.0 파싱·검사, SceneParams 기록, 렌더 계획(form.type과의 관계, 조절 반영), 덮어쓰기·선택 파일 키, 소유감 변형과의 관계.
using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using IFS.SceneSpec.Placement;

namespace IFS.SceneSpec.Tests
{
    public class BaseShapeTests
    {
        // ── 메시 ────────────────────────────────────────────────────────────
        /// <summary>이 빌드가 만드는 (형상, 변형값) 조합 전부. 형상마다 변형 키의 모든 값을 하나씩 바꿔 본다.</summary>
        public static IEnumerable<TestCaseData> Combos()
        {
            foreach (var shape in BaseShapes.All.Where(BaseShapeMesh.Supports))
            {
                var table = BaseShapes.Variants[shape];
                var def = BaseShapes.Resolve(shape, null, null, null);
                yield return new TestCaseData(shape, Fmt(def)).SetName($"{shape}(기본)");
                foreach (var kv in table)
                    foreach (var v in kv.Value.Skip(1))
                    {
                        var d = new SortedDictionary<string, string>(def, StringComparer.Ordinal) { [kv.Key] = v };
                        yield return new TestCaseData(shape, Fmt(d)).SetName($"{shape}({kv.Key}={v})");
                    }
            }
        }

        static string Fmt(IDictionary<string, string> d) => string.Join(",", d.Select(kv => kv.Key + "=" + kv.Value));

        static SortedDictionary<string, string> Parse(string s)
        {
            var d = new SortedDictionary<string, string>(StringComparer.Ordinal);
            if (string.IsNullOrEmpty(s)) return d;
            foreach (var p in s.Split(',')) { var kv = p.Split('='); d[kv[0]] = kv[1]; }
            return d;
        }

        static (float[] xyz, float[] nrm, int[] tris) Build(string shape, string variant, int seed = BaseShapeMesh.DefaultSeed)
        {
            BaseShapeMesh.Build(shape, Parse(variant), seed, out var xyz, out var nrm, out var tris);
            return (xyz, nrm, tris);
        }

        [TestCaseSource(nameof(Combos))]
        public void Mesh_is_deterministic(string shape, string variant)
        {
            var a = Build(shape, variant);
            var b = Build(shape, variant);
            Assert.That(BaseShapeMesh.Hash(b.xyz), Is.EqualTo(BaseShapeMesh.Hash(a.xyz)));
            Assert.That(b.tris, Is.EqualTo(a.tris));
            Assert.That(b.nrm, Is.EqualTo(a.nrm));
        }

        [TestCaseSource(nameof(Combos))]
        public void Mesh_stays_under_the_triangle_cap(string shape, string variant)
        {
            var m = Build(shape, variant);
            Assert.That(m.tris.Length / 3, Is.GreaterThan(0).And.LessThanOrEqualTo(BaseShapeMesh.MaxTriangles));
            Assert.That(m.tris.All(i => i >= 0 && i < m.xyz.Length / 3), Is.True);
        }

        [TestCaseSource(nameof(Combos))]
        public void Bounds_longest_side_is_one_and_centered(string shape, string variant)
        {
            var m = Build(shape, variant);
            var lo = new double[3] { double.MaxValue, double.MaxValue, double.MaxValue };
            var hi = new double[3] { double.MinValue, double.MinValue, double.MinValue };
            for (int i = 0; i < m.xyz.Length; i++) { lo[i % 3] = Math.Min(lo[i % 3], m.xyz[i]); hi[i % 3] = Math.Max(hi[i % 3], m.xyz[i]); }
            double longest = Enumerable.Range(0, 3).Max(k => hi[k] - lo[k]);
            Assert.That(longest, Is.EqualTo(1.0).Within(1e-5));
            for (int k = 0; k < 3; k++) Assert.That((lo[k] + hi[k]) / 2, Is.EqualTo(0.0).Within(1e-5), "축 " + k);
        }

        [TestCaseSource(nameof(Combos))]
        public void Faces_agree_with_normals_and_have_area(string shape, string variant)
        {
            var m = Build(shape, variant);
            for (int i = 0; i < m.nrm.Length; i += 3)
            {
                double len = Math.Sqrt(m.nrm[i] * m.nrm[i] + m.nrm[i + 1] * m.nrm[i + 1] + m.nrm[i + 2] * m.nrm[i + 2]);
                Assert.That(len, Is.EqualTo(1.0).Within(1e-4));
            }
            int disagree = 0;
            for (int t = 0; t < m.tris.Length; t += 3)
            {
                int a = m.tris[t], b = m.tris[t + 1], c = m.tris[t + 2];
                double ux = m.xyz[b * 3] - m.xyz[a * 3], uy = m.xyz[b * 3 + 1] - m.xyz[a * 3 + 1], uz = m.xyz[b * 3 + 2] - m.xyz[a * 3 + 2];
                double vx = m.xyz[c * 3] - m.xyz[a * 3], vy = m.xyz[c * 3 + 1] - m.xyz[a * 3 + 1], vz = m.xyz[c * 3 + 2] - m.xyz[a * 3 + 2];
                double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
                double area = Math.Sqrt(cx * cx + cy * cy + cz * cz) / 2;
                Assert.That(area, Is.GreaterThan(1e-10), "넓이 0인 삼각형");
                double nx = m.nrm[a * 3] + m.nrm[b * 3] + m.nrm[c * 3], ny = m.nrm[a * 3 + 1] + m.nrm[b * 3 + 1] + m.nrm[c * 3 + 1],
                       nz = m.nrm[a * 3 + 2] + m.nrm[b * 3 + 2] + m.nrm[c * 3 + 2];
                if (cx * nx + cy * ny + cz * nz <= 0) disagree++;
            }
            Assert.That(disagree, Is.EqualTo(0), "면 방향(cross(b − a, c − a))이 정점 법선과 반대인 삼각형 수");
        }

        /// <summary>닫힌 메시: 같은 위치의 정점을 하나로 보면 모든 모서리를 삼각형 둘이 나눈다(구멍·겹침 없음 — 얇은 판·관도 두께가 있다).</summary>
        [TestCaseSource(nameof(Combos))]
        public void Mesh_is_closed(string shape, string variant)
        {
            var m = Build(shape, variant);
            var id = new Dictionary<(long, long, long), int>();
            int Key(int v)
            {
                var k = ((long)Math.Round(m.xyz[v * 3] * 1e5), (long)Math.Round(m.xyz[v * 3 + 1] * 1e5), (long)Math.Round(m.xyz[v * 3 + 2] * 1e5));
                if (!id.TryGetValue(k, out int i)) id[k] = i = id.Count;
                return i;
            }
            var edges = new Dictionary<(int, int), int>();
            for (int t = 0; t < m.tris.Length; t += 3)
                for (int e = 0; e < 3; e++)
                {
                    int a = Key(m.tris[t + e]), b = Key(m.tris[t + (e + 1) % 3]);
                    var k = a < b ? (a, b) : (b, a);
                    edges[k] = edges.TryGetValue(k, out int n) ? n + 1 : 1;
                }
            int open = edges.Values.Count(n => n % 2 != 0);
            Assert.That(open, Is.EqualTo(0), "삼각형 하나에만 붙은 모서리 수");
        }

        [Test]
        public void Default_mesh_hash_is_pinned_to_the_rule_version()
        {
            // 규칙 버전 → 기본 변형값 메시의 정점 해시. 메시가 바뀌면 규칙 버전을 올리고 이 표를 고친다(FragmentMeshTests와 같은 방식).
            var pinned = new Dictionary<string, ulong>
            {
                { "container/1", 13257536307435825394UL },
            };
            foreach (var shape in BaseShapes.All.Where(BaseShapeMesh.Supports))
            {
                string rule = BaseShapeMesh.RuleFor(shape);
                Assert.That(pinned.ContainsKey(rule), Is.True, "고정 해시 없음: " + rule);
                var m = Build(shape, Fmt(BaseShapes.Resolve(shape, null, null, null)));
                Assert.That(BaseShapeMesh.Hash(m.xyz), Is.EqualTo(pinned[rule]), rule);
            }
        }

        [Test]
        public void Variants_change_the_mesh()
        {
            foreach (var shape in BaseShapes.All.Where(BaseShapeMesh.Supports))
            {
                var hashes = Combos().Where(c => (string)c.Arguments[0] == shape)
                                     .Select(c => BaseShapeMesh.Hash(Build(shape, (string)c.Arguments[1]).xyz)).ToList();
                Assert.That(hashes.Distinct().Count(), Is.EqualTo(hashes.Count), shape + ": 변형값이 다른데 같은 메시");
            }
        }

        // ── spec 2.2.0 ──────────────────────────────────────────────────────
        /// <summary>합성 2.2.0 spec(EX02 꼴). base·variant가 null이면 키는 있고 값만 null.</summary>
        public static string Spec22(string formType, string baseShape, string variantJson = null, string version = "2.2.0")
        {
            var prov = new JObject();
            if (formType != null) prov["form.type"] = Prov("말", "synthetic.form");
            if (baseShape != null) prov["form.base"] = Prov("그릇", "baseShapes.그릇>form.base:" + baseShape);
            if (variantJson != null) prov["form.baseVariant"] = Prov("그릇", "baseShapes.그릇>form.baseVariant");
            var form = new JObject { ["type"] = formType, ["posture"] = null, ["base"] = baseShape, ["baseVariant"] = variantJson != null ? JObject.Parse(variantJson) : null };
            var o = new JObject
            {
                ["meta"] = new JObject
                {
                    ["specVersion"] = version, ["participantId"] = null, ["sessionId"] = "SYN-BASE", ["condition"] = null,
                    ["sourceTextHash"] = "sha256:" + new string('0', 64),
                    ["pipeline"] = new JObject { ["builder"] = "test", ["analyzer"] = "kiwi", ["lexicons"] = new JObject() },
                },
                ["form"] = form,
                ["material"] = new JObject { ["color"] = null, ["brightness"] = null, ["saturation"] = null, ["roughness"] = null, ["opacity"] = null, ["erosion"] = null },
                ["layout"] = new JObject { ["size"] = null, ["distance"] = null, ["verticalOffset"] = null },
                ["motion"] = new JObject { ["type"] = null, ["speed"] = null },
                ["body"] = new JObject { ["part"] = null, ["layer"] = null },
                ["_provenance"] = prov, ["_unmatched"] = new JArray(), ["_unmapped"] = new JArray(), ["_negated"] = new JArray(),
                ["_alternatives"] = new JArray(), ["_inferred"] = new JObject(),
            };
            return o.ToString();
        }

        static JArray Prov(string trigger, string rule) => new JArray(new JObject
        {
            ["source"] = "explicit_lexicon", ["trigger"] = trigger, ["charSpan"] = new JArray(0, trigger.Length), ["rule"] = rule,
        });

        [Test]
        public void Spec_22_parses_and_validates()
        {
            var s = SceneSpecJson.Parse(Spec22(null, "container", "{\"opening\":\"narrow\"}"));
            Assert.That(s.Form.Base, Is.EqualTo("container"));
            Assert.That(s.Form.BaseVariant.Opening, Is.EqualTo("narrow"));
            Assert.That(s.Form.BaseKeysPresent, Is.True);
            Assert.That(SceneSpecJson.Validate(s), Is.Empty);
            var nul = SceneSpecJson.Parse(Spec22(null, null));
            Assert.That(nul.Form.Base, Is.Null);
            Assert.That(SceneSpecJson.Validate(nul), Is.Empty);
        }

        [Test]
        public void Spec_22_round_trip_keeps_null_base_keys_and_21_stays_without_them()
        {
            var s = SceneSpecJson.Parse(Spec22(null, null));
            var back = JObject.Parse(SceneSpecJson.Serialize(s));
            Assert.That(((JObject)back["form"]).ContainsKey("base"), Is.True);
            Assert.That(back["form"]["base"].Type, Is.EqualTo(JTokenType.Null));
            var o = JObject.Parse(Spec22(null, null, null, "2.1.0"));
            ((JObject)o["form"]).Remove("base");
            ((JObject)o["form"]).Remove("baseVariant");
            var s21 = SceneSpecJson.Parse(o.ToString());
            Assert.That(SceneSpecJson.Validate(s21), Is.Empty);
            Assert.That(((JObject)JObject.Parse(SceneSpecJson.Serialize(s21))["form"]).ContainsKey("base"), Is.False);
        }

        [Test]
        public void Validate_flags_version_and_provenance_problems()
        {
            // 2.2.0인데 키가 없음
            var o = JObject.Parse(Spec22(null, null));
            ((JObject)o["form"]).Remove("base");
            ((JObject)o["form"]).Remove("baseVariant");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o.ToString())), Has.Some.Contains("form.base·form.baseVariant가 없다"));
            // 2.1.0에 기본 형상 키
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec22(null, "container", null, "2.1.0"))), Has.Some.Contains("2.2 전용"));
            // 값은 있는데 근거 없음
            var p = JObject.Parse(Spec22(null, "container"));
            ((JObject)p["_provenance"]).Remove("form.base");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(p.ToString())), Has.Some.Contains("form.base: 값이 있는데 _provenance가 없다"));
            // 모르는 기본 형상, 다른 형상의 변형 키
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec22(null, "tree"))), Has.Some.Contains("모르는 기본 형상"));
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec22(null, "container", "{\"drape\":\"cloth\"}"))), Has.Some.Contains("drape"));
        }

        [Test]
        public void Unknown_variant_key_is_a_parse_error()
        {
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(Spec22(null, "container", "{\"color\":\"red\"}")));
        }

        [Test]
        public void Scene_params_record_base_only_for_22_specs()
        {
            var d = new SceneDefaults();
            var p22 = SceneParams.FromSpec(SceneSpecJson.Parse(Spec22(null, "container")), d);
            Assert.That(p22.ToRecord()["form.base"], Is.EqualTo("container"));
            Assert.That(p22.DefaultsUsed, Has.No.Member("form.base"));
            var pNull = SceneParams.FromSpec(SceneSpecJson.Parse(Spec22(null, null)), d);
            Assert.That(pNull.ToRecord()["form.base"], Is.EqualTo("none"));
            Assert.That(pNull.DefaultsUsed, Has.Member("form.base"));
            var o = JObject.Parse(Spec22(null, null, null, "2.1.0"));
            ((JObject)o["form"]).Remove("base");
            ((JObject)o["form"]).Remove("baseVariant");
            var p21 = SceneParams.FromSpec(SceneSpecJson.Parse(o.ToString()), d);
            Assert.That(p21.ToRecord().ContainsKey("form.base"), Is.False);
            Assert.That(p21.DefaultsUsed, Has.No.Member("form.base"));
            // 덮어쓰기로 기본 형상을 정하면 기록에 나온다
            var c = p21.Clone();
            Assert.That(c.SetCategory("form.base", "container"), Is.True);
            Assert.That(c.ToRecord()["form.base"], Is.EqualTo("container"));
            Assert.That(SceneParams.ChangedCategories(p21, c), Is.EqualTo(new[] { "form.base" }));
            Assert.Throws<ArgumentException>(() => c.SetCategory("form.base", "tree"));
        }

        // ── 렌더 계획 ──────────────────────────────────────────────────────
        static FormRenderPlan Plan(string formType, string baseShape, string variantJson = null, Action<SceneParams> adjust = null, ShapeResolution shape = null)
        {
            var spec = SceneSpecJson.Parse(Spec22(formType, baseShape, variantJson));
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            string initial = p.GetCategory("form.type");
            adjust?.Invoke(p);
            return FormRenderPlan.Build(p, initial, shape ?? ShapeMapping.Resolve(spec));
        }

        public static IEnumerable<string> Supported() => BaseShapes.All.Where(BaseShapeMesh.Supports);

        [TestCaseSource(nameof(Supported))]
        public void Base_is_drawn_when_form_type_is_unstated_or_blob(string shape)
        {
            foreach (var form in new[] { null, "blob" })
            {
                var plan = Plan(form, shape);
                Assert.That(plan.Renderer, Is.EqualTo("base:" + shape));
                Assert.That(plan.BaseStatus, Is.EqualTo("applied"));
                Assert.That(plan.BaseRule, Is.EqualTo(BaseShapeMesh.RuleFor(shape)));
                Assert.That(plan.ZeroDisplacement, Is.True);
                Assert.That(plan.ToJson()["base"]["rule"].ToString(), Is.EqualTo(BaseShapeMesh.RuleFor(shape)));
            }
        }

        [TestCase("mist")]
        [TestCase("shell")]
        [TestCase("fragments")]
        public void Other_form_types_keep_their_renderer_and_record_not_applied_form(string form)
        {
            var plan = Plan(form, "container");
            Assert.That(plan.Renderer, Is.EqualTo(FormRenderPlan.RendererFor(form)));
            Assert.That(plan.BaseStatus, Is.EqualTo("not_applied_form"));
            Assert.That(plan.BaseShape, Is.Null);
            Assert.That(plan.ToJson()["base"]["status"].ToString(), Is.EqualTo("not_applied_form"));
        }

        [Test]
        public void Plan_without_base_has_no_base_key()
        {
            Assert.That(Plan(null, null).ToJson().ContainsKey("base"), Is.False);
        }

        [TestCaseSource(nameof(Supported))]
        public void Plan_depends_on_the_base_shape(string shape)
        {
            string a = Plan(null, shape).ToJson().ToString();
            Assert.That(Plan(null, null).ToJson().ToString(), Is.Not.EqualTo(a));
            foreach (var other in Supported().Where(o => o != shape))
                Assert.That(Plan(null, other).ToJson().ToString(), Is.Not.EqualTo(a), other);
        }

        [Test]
        public void Shape_words_are_not_applied_when_a_base_is_said()
        {
            var words = new[] { new ShapeWord("square", "네모난", 0, 3) };
            var r = ShapeMapping.Resolve(words, null, "container");
            Assert.That(r.Model, Is.Null);
            Assert.That(r.Status, Is.EqualTo("not_applied_base"));
            Assert.That(r.Words[0].Status, Is.EqualTo("not_applied_base"));
            Assert.That(ShapeMapping.Resolve(words, "mist", "container").Status, Is.EqualTo("not_applied_form"));
            Assert.That(ShapeMapping.Resolve(words, null, null).Model, Is.EqualTo("Cube"));
            var plan = Plan(null, "container", null, null, r);
            Assert.That(plan.Renderer, Is.EqualTo("base:container"));
        }

        [Test]
        public void Forced_shape_model_wins_over_the_base()
        {
            var forced = ShapeMapping.Forced(ShapeMapping.Resolve(new ShapeWord[0], null, "container"), "Cube");
            var plan = Plan(null, "container", null, null, forced);
            Assert.That(plan.Renderer, Is.EqualTo("shapeModel"));
            Assert.That(plan.BaseStatus, Is.EqualTo("not_applied_forced"));
        }

        [Test]
        public void Variant_comes_from_the_spec_only_for_the_same_base()
        {
            var plan = Plan(null, "container", "{\"opening\":\"narrow\"}");
            Assert.That(plan.BaseVariant["opening"], Is.EqualTo("narrow"));
            Assert.That(plan.BaseVariantDefaults, Is.EquivalentTo(new[] { "profile" }));
            // 조절로 다른 기본 형상을 고르면 spec 변형값을 쓰지 않음 → 돌아오면 다시 씀
            if (Supported().Count() > 1)
            {
                string other = Supported().First(s => s != "container");
                var p2 = Plan(null, "container", "{\"opening\":\"narrow\"}", p => p.SetCategory("form.base", other));
                Assert.That(p2.BaseShape, Is.EqualTo(other));
                Assert.That(p2.BaseVariantDefaults.Count, Is.EqualTo(p2.BaseVariant.Count));
            }
            var back = Plan(null, "container", "{\"opening\":\"narrow\"}", p => { p.SetCategory("form.base", "none"); p.SetCategory("form.base", "container"); });
            Assert.That(back.BaseVariant["opening"], Is.EqualTo("narrow"));
        }

        /// <summary>G22: 조절 항목 × 기본 형상. 이웃 단계 쌍마다 렌더 계획(색·밝기·투명도·질감) 또는 해석값(크기·움직임)이 달라진다.
        /// 형태 항목은 form.type 값(→ 다른 렌더러)·form.base none(→ blob)으로 계획이 달라진다.</summary>
        [TestCaseSource(nameof(Supported))]
        public void Adjust_items_change_the_plan_for_base_shapes(string shape)
        {
            string J(Action<SceneParams> a) => Plan(null, shape, null, a).ToJson().ToString();
            string baseline = J(null);
            var steps = new Dictionary<string, (string key, double a, double b)>
            {
                { "color.h", ("material.color.h", 0.0, 0.0833) }, { "color.l", ("material.color.l", 0.5, 0.7) },
                { "brightness", ("material.brightness", 0.5, 0.625) }, { "opacity", ("material.opacity", 1.0, 0.8) },
                { "texture", ("material.roughness", 0.5, 0.7) },
            };
            foreach (var kv in steps)
            {
                string a = J(p => { p.SetNumber("material.color.s", 0.6); p.SetNumber(kv.Value.key, kv.Value.a); });
                string b = J(p => { p.SetNumber("material.color.s", 0.6); p.SetNumber(kv.Value.key, kv.Value.b); });
                Assert.That(b, Is.Not.EqualTo(a), kv.Key);
            }
            foreach (var form in new[] { "mist", "shell", "fragments" })
                Assert.That(J(p => p.SetCategory("form.type", form)), Is.Not.EqualTo(baseline), "form.type " + form);
            Assert.That(J(p => p.SetCategory("form.base", "none")), Is.Not.EqualTo(baseline), "form.base none");
            // 크기·움직임은 계획 밖(로더 ApplyLayout·SpecMotion)이라 해석값이 바뀌는지만 본다
            var sp = SceneParams.FromSpec(SceneSpecJson.Parse(Spec22(null, shape)), new SceneDefaults());
            Assert.That(sp.SetNumber("layout.size", 0.6), Is.True);
            Assert.That(SceneParams.SizeToScale(0.6), Is.Not.EqualTo(SceneParams.SizeToScale(0.5)));
            Assert.That(sp.SetCategory("motion.type", "floating"), Is.True);
        }

        // ── 덮어쓰기 · 선택 파일 · 소유감 ───────────────────────────────────
        [Test]
        public void Override_json_accepts_form_base()
        {
            var o = SceneOverrideJson.Parse("{\"form.base\":\"container\",\"form.type\":\"blob\"}", out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(o.Categories["form.base"], Is.EqualTo("container"));
            Assert.That(SceneOverrideJson.Parse("{\"form.base\":\"none\"}", out _), Is.Not.Null);
            Assert.That(SceneOverrideJson.Parse("{\"form.base\":\"tree\"}", out var e2), Is.Null);
            Assert.That(e2, Has.Some.Contains("모르는 기본 형상"));
        }

        [Test]
        public void Override_applies_to_a_21_spec_and_draws_the_base()
        {
            var o = JObject.Parse(Spec22(null, null, null, "2.1.0"));
            ((JObject)o["form"]).Remove("base");
            ((JObject)o["form"]).Remove("baseVariant");
            var spec = SceneSpecJson.Parse(o.ToString());
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            var ov = SceneOverrideJson.Parse("{\"form.base\":\"container\"}", out _);
            Assert.That(ov.ApplyTo(p), Is.EqualTo(new[] { "form.base" }));
            Assert.That(FormRenderPlan.Build(p, "blob", ShapeMapping.Resolve(spec)).Renderer, Is.EqualTo("base:container"));
        }

        [Test]
        public void Runner_selection_file_carries_form_base()
        {
            string json = "{\"formatVersion\":\"ifs-selection/0.2\",\"specSha256\":\"" + new string('a', 64) + "\"," +
                          "\"finalOverrides\":{\"form.base\":\"container\"},\"selection\":{\"selectedCandidateId\":null,\"none\":true,\"skipped\":false}," +
                          "\"colorChanged\":false,\"sources\":{\"form.type\":\"default\",\"form.base\":\"edited\"}}";
            var sel = PlacementSelection.Parse(json, "selection.json", new string('b', 64), out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(sel.Overrides.Categories["form.base"], Is.EqualTo("container"));
            var spec = SceneSpecJson.Parse(Spec22(null, null));
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            sel.Overrides.ApplyTo(p);
            var applied = PlacementSelection.AppliedOverrides(sel.Overrides, p, null, out var notApplied);
            Assert.That(notApplied, Is.Empty);
            Assert.That(applied["form.base"].ToString(), Is.EqualTo("container"));
        }

        [Test]
        public void Ownership_variants_do_not_touch_form_base()
        {
            // G21: 소유감 러너의 형태 변형은 form.base를 건드리지 않는다(변형본 덮어쓰기에 form.base 키가 없다)
            var spec = SceneSpecJson.Parse(Spec22(null, "container", "{\"opening\":\"narrow\"}"));
            var plan = Ownership.OwnershipVariantGenerator.Generate(spec, 1, new Ownership.OwnershipConfig(), new SceneDefaults());
            Assert.That(plan.Ok, Is.True, string.Join("; ", plan.Errors));
            Assert.That(plan.Variants, Is.Not.Empty);
            foreach (var v in plan.Variants)
            {
                Assert.That(v.Override.Categories.ContainsKey("form.base"), Is.False, v.Id);
                Assert.That(v.Params.GetCategory("form.base"), Is.EqualTo("container"), v.Id);
            }
        }
    }
}
