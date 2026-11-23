// EditMode 테스트(dotnet에서도 돎): CP10 G41·G37·G39 — 저장된 이전 판 파일이 지금 엄격 파서·러너 선택 파일 검사를 통과하는가.
//   docs/validation/legacy-files/: spec 2.0.0(매퍼 v0 예시)·2.1.0(매퍼 v1 예시)·2.2.0(매퍼 v2 builder 2.2.0, CP10 반영 전),
//   ifs-selection/0.1 두 개(각각 2.0·2.1 spec을 가리킴)와 D6 직후 0.2 하나(form.baseVariant 없음). 모두 합성 자료.
//   이 폴더는 .gitattributes로 LF 고정이라 선택 파일의 specSha256이 spec 파일 바이트의 sha256과 같다.
// 실제 러너(PlacementRunner)·SceneLoader로 끝까지 돌리는 것은 UnityOnly/LegacyFilesRunnerTests.cs.
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class LegacyFilesTests
    {
        public static string Dir => Path.GetFullPath(Path.Combine(Application.streamingAssetsPath, "..", "..", "..", "docs", "validation", "legacy-files"));

        public static readonly (string selection, string spec, string format, string specVersion)[] Pairs =
        {
            ("sel_0.1_spec-2.0.0.json", "spec_2.0.0.json", "ifs-selection/0.1", "2.0.0"),
            ("sel_0.1_spec-2.1.0.json", "spec_2.1.0.json", "ifs-selection/0.1", "2.1.0"),
            ("sel_0.2_d6_spec-2.2.0.json", "spec_2.2.0_builder-2.2.0.json", "ifs-selection/0.2", "2.2.0"),
        };

        static string P(string name)
        {
            if (!Directory.Exists(Dir)) Assert.Ignore("docs/validation/legacy-files 없음: " + Dir);
            return Path.Combine(Dir, name);
        }

        [TestCase("spec_2.0.0.json", "2.0.0")]
        [TestCase("spec_2.1.0.json", "2.1.0")]
        [TestCase("spec_2.2.0_builder-2.2.0.json", "2.2.0")]
        public void Legacy_spec_files_parse_strictly_and_round_trip(string name, string version)
        {
            string raw = File.ReadAllText(P(name));
            var spec = SceneSpecJson.Parse(raw);
            Assert.That(spec.Meta.SpecVersion, Is.EqualTo(version));
            Assert.That(SceneSpecJson.Validate(spec), Is.Empty, name);
            var back = JToken.Parse(SceneSpecJson.Serialize(spec));
            Assert.That(JToken.DeepEquals(JToken.Parse(raw), back), Is.True, name + ": 다시 직렬화한 JSON이 원본과 다름");
            var p = SceneParams.FromSpec(spec, new SceneDefaults(), false);
            if (version == "2.2.0")
            {
                // builder 2.2.0 spec(변형값 근거 source = explicit_lexicon): 그릇 → container, opening wide
                Assert.That(p.GetCategory("form.base"), Is.EqualTo("container"));
                Assert.That(p.CurrentBaseVariant.Opening, Is.EqualTo("wide"));
            }
            else
            {
                Assert.That(spec.Form.Base, Is.Null);
                Assert.That(p.ToRecord().ContainsKey("form.base"), Is.False, "2.0·2.1 기록에는 form.base가 나오지 않음(X68)");
            }
        }

        [Test]
        public void Legacy_selection_files_pass_the_runner_contract_against_their_spec_bytes()
        {
            foreach (var (sel, specName, format, specVersion) in Pairs)
            {
                var s = PlacementSelection.Load(P(sel), out var errors);
                Assert.That(errors, Is.Empty, sel);
                Assert.That(s.Warnings, Is.Empty, sel);
                Assert.That(s.FormatVersion, Is.EqualTo(format), sel);
                Assert.That(s.SpecMismatch(OwnershipManifest.Sha256Hex(File.ReadAllBytes(P(specName)))), Is.Null, sel);
                var spec = SceneSpecJson.Load(P(specName));
                Assert.That(spec.Meta.SpecVersion, Is.EqualTo(specVersion));
                Assert.That(s.CheckApplicable(spec, new SceneDefaults()), Is.Empty, sel);
                Assert.That(s.Sources, Is.Not.Null, sel);
                Assert.That(((JObject)s.Sources).ContainsKey("form.baseVariant"), Is.False, sel + ": 이전 판에는 없음");
            }
        }

        // ── G39: form.baseVariant 슬롯 ─────────────────────────────────────
        [Test]
        public void Base_variant_source_is_accepted_only_with_form_base()
        {
            var o = JObject.Parse(File.ReadAllText(P("sel_0.2_d6_spec-2.2.0.json")));
            o["sources"]["form.baseVariant"] = "edited";
            Assert.That(PlacementSelection.Parse(o.ToString(), "s.json", "ab", out var e1), Is.Not.Null, string.Join("; ", e1));
            ((JObject)o["sources"]).Remove("form.base");
            Assert.That(PlacementSelection.Parse(o.ToString(), "s.json", "ab", out var e2), Is.Null);
            Assert.That(e2.Single(), Does.Contain("form.baseVariant"));
            var bad = JObject.Parse(File.ReadAllText(P("sel_0.2_d6_spec-2.2.0.json")));
            bad["finalOverrides"]["form.baseVariant"] = "wide";
            Assert.That(PlacementSelection.Parse(bad.ToString(), "s.json", "ab", out var e3), Is.Null, "변형값은 덮어쓰기 키가 아님");
            Assert.That(e3.Single(), Does.Contain("form.baseVariant"));
        }

        // ── G37: 안전 제외 기록은 모양어로 쓰지 않음 ─────────────────────────
        [Test]
        public void Excluded_shape_records_are_not_shape_words()
        {
            var o = JObject.Parse(File.ReadAllText(P("spec_2.2.0_builder-2.2.0.json")));
            o["form"]["base"] = null;
            o["form"]["baseVariant"] = null;
            ((JObject)o["_provenance"]).Remove("form.base");
            ((JObject)o["_provenance"]).Remove("form.baseVariant");
            JObject Word(string lemma, string shape, string reason, int start) => new JObject
            {
                ["lemma"] = lemma, ["category"] = "shape", ["value"] = new JObject { ["shape"] = shape }, ["reason"] = reason,
                ["_provenance"] = new JObject { ["source"] = "explicit_lexicon", ["trigger"] = lemma, ["charSpan"] = new JArray(start, start + lemma.Length), ["rule"] = "shapeLexicon." + lemma },
            };
            ((JArray)o["_unmapped"]).Add(Word("네모", "square", "excluded_shape", 0));
            var spec = SceneSpecJson.Parse(o.ToString());
            Assert.That(ShapeMapping.ExtractWords(spec), Is.Empty, "excluded_shape 기록(예: '뱀 같은 끈'의 '끈')은 모형으로 그리지 않음");
            Assert.That(ShapeMapping.Resolve(spec).Model, Is.Null);
            ((JArray)o["_unmapped"]).Add(Word("네모", "square", "no_scene_param", 0));
            spec = SceneSpecJson.Parse(o.ToString());
            Assert.That(ShapeMapping.ExtractWords(spec).Single().Shape, Is.EqualTo("square"));
        }
    }
}
