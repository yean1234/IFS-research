// (2.4, G72) x·y·z 비율(layout.proportions) 테스트: 2.4.0 파싱·검사(키 필수, 2.3 이하 문서에는 없음, 0.2–1·가장 큰 값 1, 근거),
// 덮어쓰기 원값 범위(0.2–2.0), 해석값·기록(2.4 null 문서 = 2.2 + 비율 키), 유효 비율(원값 / 가장 큰 값, 0.2로 올림),
// 가장 긴 변 규칙(비율을 바꿔도 가장 긴 변은 크기만 정함), 메시 형상 비균일 배율, 안개 대리 구 배율, fragments 조각 배치,
// 생성 메시 맞춤, form.aspect보다 비율이 앞섬, manifest object.boundsM·proportions. spec은 합성(참여자 데이터 아님).
using System;
using System.Collections.Generic;
using System.Linq;
using IFS.SceneSpec.FormAsset;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class ProportionsTests
    {
        // ── 합성 spec ────────────────────────────────────────────────────────
        /// <summary>합성 2.4.0 spec(BaseShapeTests.Spec22 꼴 + layout.proportions). contour = true면 2.3 확장 슬롯 세 키도 넣는다.</summary>
        public static string Spec24(string formType = null, double[] p = null, bool axisSaid = true, bool contour = false, string aspect = null,
                                    Action<JObject> edit = null)
        {
            var o = JObject.Parse(BaseShapeTests.Spec22(formType, null, null, "2.4.0"));
            o["layout"]["proportions"] = p == null ? null : new JObject { ["x"] = p[0], ["y"] = p[1], ["z"] = p[2], ["axisSaid"] = axisSaid };
            if (p != null)
                o["_provenance"]["layout.proportions"] = new JArray(new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = "넓게", ["charSpan"] = new JArray(0, 2), ["rule"] = "proportionLexicon.넓>layout.proportions",
                });
            if (contour || aspect != null)
            {
                o["form"]["roundness"] = null;
                o["form"]["aspect"] = aspect;
                o["material"]["emission"] = null;
                if (aspect != null)
                    o["_provenance"]["form.aspect"] = new JArray(new JObject
                    {
                        ["source"] = "explicit_lexicon", ["trigger"] = "길쭉", ["charSpan"] = new JArray(0, 2), ["rule"] = "contourLexicon.길쭉>form.aspect:" + aspect,
                    });
            }
            edit?.Invoke(o);
            return o.ToString();
        }

        static readonly double[] Wide = { 1.0, 0.3, 1.0 };
        static SceneParams Params(string json) => SceneParams.FromSpec(SceneSpecJson.Parse(json), new SceneDefaults());

        static FormRenderPlan Plan(SceneParams p, string json) =>
            FormRenderPlan.Build(p, p.GetCategory("form.type"), ShapeMapping.Resolve(SceneSpecJson.Parse(json)));

        // ── 2.4.0 파싱·검사 ──────────────────────────────────────────────────
        [Test]
        public void Spec_24_parses_and_validates()
        {
            var s = SceneSpecJson.Parse(Spec24("mist", Wide));
            Assert.That(s.Meta.SpecVersion, Is.EqualTo("2.4.0"));
            Assert.That(s.Layout.ProportionsKeyPresent, Is.True);
            Assert.That(s.Layout.Proportions.Y, Is.EqualTo(0.3));
            Assert.That(s.Layout.Proportions.AxisSaid, Is.True);
            Assert.That(SceneSpecJson.Validate(s), Is.Empty);
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec24("mist"))), Is.Empty, "null 값도 키만 있으면 된다");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec24(null, Wide, contour: true))), Is.Empty, "2.4에서 확장 슬롯 세 키는 선택");
        }

        [Test]
        public void Spec_24_without_proportions_key_is_a_problem()
        {
            var o = JObject.Parse(Spec24("mist"));
            ((JObject)o["layout"]).Remove("proportions");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o.ToString())), Has.Some.Contains("layout.proportions가 없다"));
        }

        [TestCase("2.3.0")]
        [TestCase("2.2.0")]
        public void Proportions_in_older_document_is_a_problem(string version)
        {
            var o = JObject.Parse(Spec24("mist", Wide, contour: version == "2.3.0"));
            o["meta"]["specVersion"] = version;
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(o.ToString())), Has.Some.Contains("2.4 전용 필드(layout.proportions)"));
            // 값이 null이어도 키가 있으면 문제
            var n = JObject.Parse(Spec24("mist", null, contour: version == "2.3.0"));
            n["meta"]["specVersion"] = version;
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(n.ToString())), Has.Some.Contains("2.4 전용 필드(layout.proportions)"));
        }

        [Test]
        public void Range_max_and_provenance_are_checked()
        {
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec24("mist", new[] { 1.0, 0.1, 1.0 }))), Has.Some.Contains("layout.proportions.y"));
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec24("mist", new[] { 0.8, 0.3, 0.8 }))), Has.Some.Contains("가장 큰 값이 1이 아니다"));
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(Spec24("mist", Wide, edit: o => ((JObject)o["_provenance"]).Remove("layout.proportions")))),
                Has.Some.Contains("layout.proportions: 값이 있는데 _provenance가 없다"));
            var np = JObject.Parse(Spec24("mist", Wide));
            np["layout"]["proportions"] = null;
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(np.ToString())), Has.Some.Contains("layout.proportions: null인데 _provenance가 있다"));
            // 일부 확장 슬롯만 있는 2.4
            var part = JObject.Parse(Spec24("mist", Wide, contour: true));
            ((JObject)part["material"]).Remove("emission");
            Assert.That(SceneSpecJson.Validate(SceneSpecJson.Parse(part.ToString())), Has.Some.Contains("일부만 있다"));
        }

        [Test]
        public void Unknown_key_inside_proportions_is_a_parse_error()
        {
            var o = JObject.Parse(Spec24("mist", Wide));
            o["layout"]["proportions"]["w"] = 1;
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(o.ToString()));
            var m = JObject.Parse(Spec24("mist", Wide));
            ((JObject)m["layout"]["proportions"]).Remove("axisSaid");
            Assert.Throws<Newtonsoft.Json.JsonSerializationException>(() => SceneSpecJson.Parse(m.ToString()));
        }

        [Test]
        public void Round_trip_keeps_null_key_for_24_and_none_for_22()
        {
            var back = JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(Spec24("mist"))));
            Assert.That(((JObject)back["layout"]).ContainsKey("proportions"), Is.True);
            Assert.That(back["layout"]["proportions"].Type, Is.EqualTo(JTokenType.Null));
            var back22 = JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(BaseShapeTests.Spec22("mist", null))));
            Assert.That(((JObject)back22["layout"]).ContainsKey("proportions"), Is.False);
            var given = JObject.Parse(SceneSpecJson.Serialize(SceneSpecJson.Parse(Spec24("mist", Wide))));
            Assert.That((double)given["layout"]["proportions"]["y"], Is.EqualTo(0.3));
        }

        // ── 덮어쓰기 ─────────────────────────────────────────────────────────
        [TestCase(0.1, false)]
        [TestCase(2.5, false)]
        [TestCase(0.2, true)]
        [TestCase(1.4, true)]
        [TestCase(2.0, true)]
        public void Override_raw_range_is_0_2_to_2(double v, bool ok)
        {
            var o = SceneOverrideJson.Parse("{\"layout.proportions.y\": " + v.ToString(System.Globalization.CultureInfo.InvariantCulture) + "}", out var errors);
            Assert.That(o != null, Is.EqualTo(ok), string.Join("; ", errors));
            if (!ok) Assert.That(errors, Has.Some.Contains("layout.proportions.y"));
        }

        [Test]
        public void Selection_accepts_proportions_override_and_source()
        {
            var sel = new JObject
            {
                ["formatVersion"] = "ifs-selection/0.3",
                ["specSha256"] = new string('a', 64),
                ["finalOverrides"] = new JObject { ["layout.proportions.x"] = 1.4, ["layout.proportions.z"] = 0.5 },
                ["selection"] = new JObject { ["selectedCandidateId"] = null, ["none"] = false, ["skipped"] = true },
                ["colorChanged"] = false,
                ["sources"] = new JObject { ["layout.proportions"] = "edited" },
            };
            var s = PlacementSelection.Parse(sel.ToString(), "selection.json", new string('b', 64), out var errors);
            Assert.That(s, Is.Not.Null, string.Join("; ", errors));
            Assert.That(s.Overrides.Numbers["layout.proportions.x"], Is.EqualTo(1.4));
            Assert.That(PlacementSelection.SlotNames, Does.Contain("layout.proportions"));
            sel["finalOverrides"]["layout.proportions.y"] = 0.1;
            Assert.That(PlacementSelection.Parse(sel.ToString(), "selection.json", new string('b', 64), out errors), Is.Null);
        }

        [Test]
        public void Partial_override_uses_spec_value_and_max_normalisation()
        {
            // spec (1, 0.3, 1) + y 원값 1.4 → 원값 (1, 1.4, 1) → 유효 (0.7143, 1, 0.7143)
            var p = Params(Spec24("mist", Wide));
            var ov = SceneOverrideJson.Parse("{\"layout.proportions.y\": 1.4}", out _);
            ov.ApplyTo(p);
            Assert.That(p.ProportionsRaw, Is.EqualTo(new[] { 1.0, 1.4, 1.0 }));
            Assert.That(p.ProportionsEffective[0], Is.EqualTo(1.0 / 1.4).Within(1e-12));
            Assert.That(p.ProportionsEffective[1], Is.EqualTo(1.0));
            Assert.That((double)p.ToRecord()["layout.proportions.x"], Is.EqualTo(0.7143));
            var applied = PlacementSelection.AppliedOverrides(ov, p, null, out var notApplied);
            Assert.That(notApplied, Is.Empty, "원값으로 비교");
            Assert.That((double)applied["layout.proportions.y"], Is.EqualTo(1.4));
            // spec null이면 덮어쓰지 않은 축은 1.0
            var q = Params(BaseShapeTests.Spec22("mist", null));
            SceneOverrideJson.Parse("{\"layout.proportions.x\": 2.0}", out _).ApplyTo(q);
            Assert.That(q.ProportionsRaw, Is.EqualTo(new[] { 2.0, 1.0, 1.0 }));
            Assert.That(q.ProportionsEffective, Is.EqualTo(new[] { 1.0, 0.5, 0.5 }));
            Assert.That(q.HasProportionsSlot && q.ProportionsGiven, Is.True, "2.2 spec도 덮어쓰기로 비율 슬롯이 열린다");
        }

        [Test]
        public void Effective_below_0_2_is_raised_and_flagged()
        {
            var e = ProportionsRender.Normalize(2.0, 0.25, 2.0, out bool clamped);
            Assert.That(clamped, Is.True);
            Assert.That(e, Is.EqualTo(new[] { 1.0, 0.2, 1.0 }));
            var p = Params(BaseShapeTests.Spec22("mist", null));
            SceneOverrideJson.Parse("{\"layout.proportions.x\": 2.0, \"layout.proportions.y\": 0.25, \"layout.proportions.z\": 2.0}", out _).ApplyTo(p);
            var plan = Plan(p, BaseShapeTests.Spec22("mist", null));
            Assert.That(plan.ProportionsClamped, Is.True);
            Assert.That(plan.Proportions, Is.EqualTo(new[] { 1.0, 0.2, 1.0 }));
            ProportionsRender.Normalize(1.0, 0.3, 1.0, out clamped);
            Assert.That(clamped, Is.False);
        }

        // ── 2.2 동일성 ───────────────────────────────────────────────────────
        static readonly string[] PropKeys = ProportionsRender.AxisKeys;

        [TestCase(null)]
        [TestCase("mist")]
        [TestCase("fragments")]
        [TestCase("shell")]
        public void Null_24_document_resolves_like_22_plus_proportion_keys(string form)
        {
            string s22 = BaseShapeTests.Spec22(form, null), s24 = Spec24(form);
            var p22 = Params(s22);
            var p24 = Params(s24);
            var r22 = JObject.FromObject(p22.ToRecord());
            var r24 = JObject.FromObject(p24.ToRecord());
            foreach (var k in PropKeys) Assert.That((double)r24[k], Is.EqualTo(1.0), "null → (1, 1, 1)");
            foreach (var k in PropKeys) r24.Remove(k);
            Assert.That(r24.ToString(), Is.EqualTo(r22.ToString()), "비율 키 말고 같은 기록");
            Assert.That(p24.DefaultsUsed.Where(k => k != ProportionsRender.Key), Is.EqualTo(p22.DefaultsUsed));
            Assert.That(p24.DefaultsUsed, Does.Contain(ProportionsRender.Key));
            Assert.That(p24.ProportionsGiven, Is.False);
            Assert.That(Plan(p24, s24).ToJson().ToString(), Is.EqualTo(Plan(p22, s22).ToJson().ToString()), "같은 계획(비율 없음)");
            Assert.That(Plan(p24, s24).Proportions, Is.Null);
            // 2.2 기록에는 비율 키가 없고 Deltas·RMS도 그대로
            Assert.That(r22.Properties().Any(x => x.Name.StartsWith("layout.proportions")), Is.False);
            Assert.That(SceneParams.Deltas(p22, p22.Clone()).Keys.Any(k => k.StartsWith("layout.proportions")), Is.False);
            Assert.That(SceneParams.Deltas(p24, p24.Clone()).Keys, Is.SupersetOf(PropKeys));
        }

        [Test]
        public void Deltas_use_effective_values_and_rms_counts_numeric_keys_only()
        {
            var a = Params(Spec24("mist", Wide));
            var b = a.Clone();
            b.SetNumber(ProportionsRender.YKey, 1.0);
            var d = SceneParams.Deltas(a, b);
            Assert.That(d[ProportionsRender.YKey], Is.EqualTo(0.7));
            Assert.That(SceneParams.AdjustmentRms(a, b), Is.EqualTo(0.0), "RMS의 분모·분자는 NumericKeys만");
        }

        // ── 가장 긴 변 규칙 ───────────────────────────────────────────────────
        [Test]
        public void Mesh_form_gets_non_uniform_scale_with_the_same_longest_edge()
        {
            // 기본 덩어리(구, 지름 1) × 국소 배율 0.35: 비율 (1, 0.3, 1) → 국소 배율 비 y/x = 0.3, 가장 긴 변 그대로
            var size = new[] { 1.0, 1.0, 1.0 };
            var local0 = new[] { 0.35, 0.35, 0.35 };
            var r = ProportionsRender.FitLocalScale(size, size, local0, Wide, out double l0, out double l1);
            Assert.That(r[1] / r[0], Is.EqualTo(0.3).Within(1e-12));
            Assert.That(r[2] / r[0], Is.EqualTo(1.0).Within(1e-12));
            Assert.That(ProportionsRender.LongestEdge(size, r), Is.EqualTo(l0).Within(1e-12));
            Assert.That(l0, Is.EqualTo(0.35).Within(1e-12), "크기만 정한 가장 긴 변");
        }

        [TestCase(1.0, 0.3, 1.0)]
        [TestCase(0.4, 1.0, 0.4)]
        [TestCase(0.2, 0.5, 1.0)]
        public void Longest_edge_does_not_change_with_proportions_for_any_shape(double x, double y, double z)
        {
            // 길쭉한 메시(경계 1 × 0.2 × 0.3)와 자세 변형(1.2, 0.8, 1): 비율을 바꿔도 가장 긴 변 = 비율 없을 때
            var size = new[] { 1.0, 0.2, 0.3 };
            var local0 = new[] { 0.42, 0.28, 0.35 };
            double want = ProportionsRender.LongestEdge(size, local0);
            var r = ProportionsRender.FitLocalScale(size, size, local0, new[] { x, y, z }, out double l0, out _);
            Assert.That(l0, Is.EqualTo(want).Within(1e-12));
            Assert.That(ProportionsRender.LongestEdge(size, r), Is.EqualTo(want).Within(1e-12));
            // 크기를 바꾸면 가장 긴 변이 그 배율만큼 바뀐다
            double k = SceneParams.SizeToScale(0.8) / SceneParams.SizeToScale(0.5);
            var r2 = ProportionsRender.FitLocalScale(size, size, local0.Select(v => v * k).ToArray(), new[] { x, y, z }, out _, out _);
            Assert.That(ProportionsRender.LongestEdge(size, r2), Is.EqualTo(want * k).Within(1e-12));
        }

        [Test]
        public void Mist_proxy_is_stretched_into_a_flat_sheet()
        {
            // 안개 대리 구(정점 반지름 MistRadius × 1.02)의 국소 배율 비 = 비율. 셰이더는 물체 좌표 레이마칭(unity_WorldToObject)이라
            // 대리 구를 비균일하게 늘이면 밀도 부피도 같이 늘어난다 → 세계 크기 비 y/x = 0.3(넓게 펼쳐진 안개)
            double d = 2 * FormRenderResources.MistRadius * 1.02;
            var size = new[] { d, d, d };
            var local0 = new[] { 0.35, 0.35, 0.35 };
            var r = ProportionsRender.FitLocalScale(size, size, local0, Wide, out double l0, out _);
            double wx = size[0] * r[0], wy = size[1] * r[1], wz = size[2] * r[2];
            Assert.That(wy / wx, Is.EqualTo(0.3).Within(1e-12));
            Assert.That(wz / wx, Is.EqualTo(1.0).Within(1e-12));
            Assert.That(Math.Max(wx, Math.Max(wy, wz)), Is.EqualTo(l0).Within(1e-12));
            // 바닥 잘림 측정(MistFloorClip)은 세계 세로 반높이 = 반지름 × 배율 y를 받는다 → 얇은 안개는 덜 잘린다
            var thin = MistFloorClip.Measure(0.1, FormRenderResources.MistRadius * r[1], 0.0);
            var round = MistFloorClip.Measure(0.1, FormRenderResources.MistRadius * local0[1], 0.0);
            Assert.That(thin.ClippedHeightFraction, Is.LessThan(round.ClippedHeightFraction));
        }

        [Test]
        public void Mist_shader_marches_in_object_space()
        {
            // 비균일 배율이 부피를 늘이려면 광선·밀도가 물체 좌표여야 한다(원문 대조 — 셰이더는 Unity에서만 돈다)
            string path = System.IO.Path.Combine(UnityEngine.Application.streamingAssetsPath, "..", "IFS", "Runtime", "Resources", "IFS", "SceneSpecMist.shader");
            string src = System.IO.File.ReadAllText(path);
            Assert.That(src, Does.Contain("mul(unity_WorldToObject, float4(_WorldSpaceCameraPos, 1.0))"));
            Assert.That(src, Does.Contain("UnityObjectToWorldNormal"));
        }

        // ── fragments ───────────────────────────────────────────────────────
        static (double[][] centroids, float[] xyz, int[] piece) Pieces(double[] p)
        {
            FragmentMesh.Build(FragmentMesh.DefaultSeed, FragmentMesh.DefaultPieces, p, out var xyz, out _, out _, out var piece);
            var c = new double[FragmentMesh.DefaultPieces][];
            var n = new int[FragmentMesh.DefaultPieces];
            for (int i = 0; i < c.Length; i++) c[i] = new double[3];
            for (int t = 0; t < piece.Length; t++)
                for (int v = 0; v < 3; v++)
                {
                    n[piece[t]]++;
                    for (int k = 0; k < 3; k++) c[piece[t]][k] += xyz[(t * 3 + v) * 3 + k];
                }
            for (int i = 0; i < c.Length; i++) for (int k = 0; k < 3; k++) c[i][k] /= n[i];
            return (c, xyz, piece);
        }

        [Test]
        public void Fragments_stretch_the_distribution_not_the_pieces()
        {
            var a = Pieces(null);
            var b = Pieces(Wide);
            // 비율이 없으면 이전 메시와 비트 단위로 같다
            FragmentMesh.Build(FragmentMesh.DefaultSeed, FragmentMesh.DefaultPieces, out var old, out _, out _, out _);
            Assert.That(FragmentMesh.Hash(a.xyz), Is.EqualTo(FragmentMesh.Hash(old)));
            // 조각 모양(조각 중심에 대한 정점 위치)은 그대로, x·z 배치도 그대로(p = 1), y 배치만 줄어듦
            for (int t = 0; t < a.piece.Length; t++)
                for (int v = 0; v < 3; v++)
                    for (int k = 0; k < 3; k++)
                    {
                        int i = (t * 3 + v) * 3 + k, pc = a.piece[t];
                        Assert.That(b.xyz[i] - b.centroids[pc][k], Is.EqualTo(a.xyz[i] - a.centroids[pc][k]).Within(1e-5));
                    }
            for (int i = 0; i < a.centroids.Length; i++)
            {
                Assert.That(b.centroids[i][0], Is.EqualTo(a.centroids[i][0]).Within(1e-5));
                Assert.That(b.centroids[i][2], Is.EqualTo(a.centroids[i][2]).Within(1e-5));
            }
            double Spread(double[][] c, int k) => c.Max(x => x[k]) - c.Min(x => x[k]);
            Assert.That(Spread(b.centroids, 1), Is.LessThan(Spread(a.centroids, 1) * 0.6));
            Assert.That(Spread(b.centroids, 0), Is.EqualTo(Spread(a.centroids, 0)).Within(1e-5));
            // 결정적
            Assert.That(FragmentMesh.Hash(Pieces(Wide).xyz), Is.EqualTo(FragmentMesh.Hash(b.xyz)));
        }

        [Test]
        public void Fragments_longest_edge_is_kept_with_a_uniform_factor()
        {
            FragmentMesh.Bounds(FragmentMesh.DefaultSeed, FragmentMesh.DefaultPieces, null, out _, out var s0);
            FragmentMesh.Bounds(FragmentMesh.DefaultSeed, FragmentMesh.DefaultPieces, new[] { 0.4, 1.0, 0.4 }, out _, out var s1);
            var local0 = new[] { 0.35, 0.35, 0.35 };
            var r = ProportionsRender.FitLocalScale(s0, s1, local0, new[] { 1.0, 1.0, 1.0 }, out double l0, out _);
            Assert.That(r[0], Is.EqualTo(r[1]).Within(1e-12), "조각을 찌그러뜨리지 않음(균일 배율)");
            Assert.That(ProportionsRender.LongestEdge(s1, r), Is.EqualTo(l0).Within(1e-12));
            Assert.That(s1[1] / s1[0], Is.GreaterThan(s0[1] / s0[0]), "세로로 길쭉한 배치");
        }

        [Test]
        public void Fragments_plan_records_distribution_method()
        {
            string json = Spec24("fragments", Wide);
            var plan = Plan(Params(json), json);
            Assert.That(plan.ProportionsMethod, Is.EqualTo(ProportionsRender.MethodFragmentDistribution));
            var j = plan.ToJson();
            Assert.That(j["proportions"]["method"].ToString(), Is.EqualTo("fragment_distribution"));
            Assert.That(j["proportions"]["effective"].Select(t => (double)t), Is.EqualTo(Wide));
            string mist = Spec24("mist", Wide);
            Assert.That(Plan(Params(mist), mist).ProportionsMethod, Is.EqualTo(ProportionsRender.MethodLocalScale));
        }

        // ── 생성 메시 ───────────────────────────────────────────────────────
        [Test]
        public void Generated_mesh_is_stretched_then_fitted_to_the_same_longest_edge()
        {
            var fit = new FormAssetFit(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 1.0, 1.0 }, new[] { 0.0, 0.5, 0.0 }, new[] { 1.0, 1.0, 1.0 });
            var local0 = new[] { 0.35, 0.35, 0.35 };
            fit.Place(local0, null, out var g0, out double u0, out _, out double lp0, out double lr0);
            fit.Place(local0, Wide, out var g, out double u, out var at, out double lp, out double lr);
            Assert.That(g0, Is.EqualTo(new[] { u0, u0, u0 }), "비율이 없으면 이전과 같은 균일 배율");
            Assert.That(lp, Is.EqualTo(lp0).Within(1e-12), "절차 모형 가장 긴 변은 비율로 바뀌지 않음");
            Assert.That(FormAssetFit.RelativeError(lr, lp), Is.LessThanOrEqualTo(FormAssetFit.Tolerance));
            Assert.That(lr, Is.EqualTo(lr0).Within(1e-12));
            Assert.That(g[1] / g[0], Is.EqualTo(0.3).Within(1e-12));
            Assert.That(at[1], Is.EqualTo(-0.5 * g[1]).Within(1e-12), "피벗 맞춤도 늘인 배율로");
            // GLB가 납작하면(경계 1 × 0.2 × 1) 늘인 뒤 균일 배율로 다시 맞춘다
            var flat = new FormAssetFit(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 1.0, 1.0 }, new[] { 0.0, 0.0, 0.0 }, new[] { 0.5, 1.0, 0.5 });
            flat.Place(local0, Wide, out _, out _, out _, out double lpf, out double lrf);
            Assert.That(lrf, Is.EqualTo(lpf).Within(1e-12));
        }

        // ── form.aspect보다 비율이 앞섬 ─────────────────────────────────────
        [Test]
        public void Proportions_supersede_aspect_but_aspect_is_still_recorded()
        {
            string withProp = Spec24(null, new[] { 0.4, 1.0, 0.4 }, axisSaid: false, aspect: "flattened");
            var plan = Plan(Params(withProp), withProp);
            Assert.That(plan.Aspect, Is.EqualTo("flattened"), "값은 기록에 남음");
            Assert.That(plan.AxisRatios, Is.Null, "축 비율은 쓰지 않음");
            Assert.That(plan.AspectSuperseded, Is.True);
            Assert.That(plan.ContourDefaultsUsed, Does.Not.Contain(ContourRender.AspectAxisKey));
            Assert.That(plan.ContourJson()["aspectSupersededBy"].ToString(), Is.EqualTo("layout.proportions"));
            Assert.That((bool)plan.ToJson()["proportions"]["aspectSuperseded"], Is.True);
            // 비율이 null이면 2.3과 같이 축 비율을 쓴다(키도 그대로)
            string nullProp = Spec24(null, null, aspect: "flattened");
            var plan2 = Plan(Params(nullProp), nullProp);
            Assert.That(plan2.AxisRatios, Is.EqualTo(new[] { 1.0, 0.4, 1.0 }));
            Assert.That(plan2.ContourJson().ContainsKey("aspectSupersededBy"), Is.False);
            Assert.That(plan2.ToJson().ContainsKey("proportions"), Is.False);
            // 덮어쓰기로 비율을 주면 그때부터 앞선다
            var p = Params(nullProp);
            p.SetNumber(ProportionsRender.XKey, 1.0);
            Assert.That(Plan(p, nullProp).AxisRatios, Is.Null);
        }

        // ── manifest ────────────────────────────────────────────────────────
        [Test]
        public void Manifest_proportions_only_with_a_proportions_slot()
        {
            Assert.That(PlacementManifest.ProportionsJson(Params(BaseShapeTests.Spec22("mist", null)), null), Is.Null, "2.2: 키 없음");
            var nul = PlacementManifest.ProportionsJson(Params(Spec24("mist")), null);
            Assert.That((string)nul["source"], Is.EqualTo("default"));
            Assert.That(nul["axisSaid"].Type, Is.EqualTo(JTokenType.Null));
            Assert.That((double)nul["y"], Is.EqualTo(1.0));
            var said = PlacementManifest.ProportionsJson(Params(Spec24("mist", Wide)), null);
            Assert.That((string)said["source"], Is.EqualTo("said"));
            Assert.That((bool)said["axisSaid"], Is.True);
            Assert.That((double)said["y"], Is.EqualTo(0.3));
            Assert.That((double)said["raw"]["y"], Is.EqualTo(0.3));
            Assert.That(said.Properties().Select(x => x.Name), Is.EqualTo(new[] { "x", "y", "z", "raw", "source", "axisSaid" }));
            // 덮어쓰기: 유효 값과 원값을 따로, 출처는 선택 파일 sources
            var p = Params(Spec24("mist", Wide));
            p.SetNumber(ProportionsRender.YKey, 2.0);
            var sel = PlacementSelection.Parse(new JObject
            {
                ["formatVersion"] = "ifs-selection/0.2", ["specSha256"] = new string('a', 64), ["finalOverrides"] = new JObject { ["layout.proportions.y"] = 2.0 },
                ["selection"] = new JObject { ["selectedCandidateId"] = null, ["none"] = false, ["skipped"] = true }, ["colorChanged"] = false,
                ["sources"] = new JObject { ["layout.proportions"] = "edited" },
            }.ToString(), "s.json", new string('b', 64), out var errors);
            Assert.That(sel, Is.Not.Null, string.Join("; ", errors));
            var ed = PlacementManifest.ProportionsJson(p, sel);
            Assert.That((string)ed["source"], Is.EqualTo("edited"));
            Assert.That((double)ed["y"], Is.EqualTo(1.0));
            Assert.That((double)ed["x"], Is.EqualTo(0.5));
            Assert.That((double)ed["raw"]["y"], Is.EqualTo(2.0));
        }

        [Test]
        public void Manifest_object_gets_bounds_and_proportions_only_when_known()
        {
            var cfg = new PlacementConfig();
            var plain = PlacementManifest.Build(cfg, new PlacementSessionInfo());
            Assert.That(((JObject)plain["object"]).Properties().Select(x => x.Name), Is.EqualTo(new[] { "boundingRadiusM" }), "잴 수 없으면 이전과 같은 키");
            var info = new PlacementSessionInfo
            {
                ObjectBoundsM = new[] { 0.7, 0.21, 0.7 },
                ObjectProportions = PlacementManifest.ProportionsJson(Params(Spec24("mist", Wide)), null),
            };
            var m = PlacementManifest.Build(cfg, info);
            var obj = (JObject)m["object"];
            Assert.That(obj.Properties().Select(x => x.Name), Is.EqualTo(new[] { "boundingRadiusM", "boundsM", "proportions" }));
            Assert.That((double)obj["boundsM"]["y"], Is.EqualTo(0.21));
            Assert.That((string)obj["proportions"]["source"], Is.EqualTo("said"));
        }
    }
}
