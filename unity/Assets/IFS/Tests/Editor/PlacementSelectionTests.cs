// EditMode 테스트(dotnet·Unity 공통): 배치 러너 D8·D9(2026-11-23)
//   · 선택 파일(selection.json, ifs-selection/0.1): 파싱, sha 불일치 거부, 모르는 덮어쓰기 키·위치 키 거부, 모르는 formatVersion 경고,
//     적용 확인(appliedOverrides / 적용하지 못한 키), manifest 0.2의 selection·appliedOverrides 키.
//   · 문항별 평정 범위(min·max): 0–10 문항의 키보드 두 자리 입력(10)·컨트롤러 가운데 값(5), 기존 1–7 동작 그대로, 범위 검증.
//   · 두 평정 문항(G13 모습 일치·대표성): 두 문구 파일에 draft·출처, 헤드셋 기본 사후만, askOptionalItems로 사전에도, disabledItems로 기존 문항 끄기.
// 합성 값만 쓴다(참여자 자료 아님).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementSelectionTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-placement-sel-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        const string Sha = "7d42fd56f98a3d75da09f894b41f955a5cd8b534cb83d23e2b2b23244618cf13";
        const string G13Source = "docs/prompts/prototype-v4-build.md G13, 2026-11-22";
        const string AppearanceText = "이 형상의 모습은 내가 떠올린 것과 비슷하다";
        const string RepresentText = "이 형상은 내가 떠올린 그것을 나타낸다";
        static string ScaleAPath => Path.Combine(Application.streamingAssetsPath, PlacementXrTests.ScaleARelativePath);
        static string DefaultPath => Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath);

        static JObject Selection(JObject overrides = null, string candidate = "c2", bool none = false, string format = "ifs-selection/0.1", string sha = Sha) =>
            new JObject
            {
                ["formatVersion"] = format,
                ["specSha256"] = sha,
                ["finalOverrides"] = overrides ?? new JObject { ["form.type"] = "fragments", ["material.brightness"] = 0.35 },
                ["selection"] = new JObject { ["selectedCandidateId"] = candidate, ["none"] = none },
                ["sources"] = new JObject { ["form.type"] = "chosen", ["material.brightness"] = "edited", ["layout.size"] = "said", ["material.opacity"] = "default" },
                ["candidates"] = new JArray("c0", "c1", "c2", "c3"),   // 러너가 읽지 않는 필드(무시)
            };

        static PlacementSelection ParseOk(JObject o)
        {
            var s = PlacementSelection.Parse(o.ToString(), "C:\\Users\\someone\\logs\\selection.json", "ab12", out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(s, Is.Not.Null);
            return s;
        }

        static List<string> ParseErrors(JObject o)
        {
            var s = PlacementSelection.Parse(o.ToString(), "selection.json", "ab", out var errors);
            Assert.That(s, Is.Null, "오류가 있으면 null");
            Assert.That(errors, Is.Not.Empty);
            return errors;
        }

        // ── 선택 파일 파싱 ───────────────────────────────────────────────
        [Test]
        public void Selection_file_reads_the_fixed_fields_and_keeps_sources_verbatim()
        {
            var s = ParseOk(Selection());
            Assert.That(s.FileName, Is.EqualTo("selection.json"), "이름만(경로 없음)");
            Assert.That(s.Sha256, Is.EqualTo("ab12"));
            Assert.That(s.FormatVersion, Is.EqualTo("ifs-selection/0.1"));
            Assert.That(s.SpecSha256, Is.EqualTo(Sha));
            Assert.That(s.SelectedCandidateId, Is.EqualTo("c2"));
            Assert.That(s.None, Is.False);
            Assert.That(s.Warnings, Is.Empty);
            Assert.That(s.Overrides.Categories["form.type"], Is.EqualTo("fragments"));
            Assert.That(s.Overrides.Numbers["material.brightness"], Is.EqualTo(0.35));
            var m = s.ManifestJson();
            Assert.That(m.Properties().Select(p => p.Name), Is.EqualTo(new[] { "file", "sha256", "formatVersion", "none", "selectedCandidateId", "finalOverrides", "sources" }));
            Assert.That(JToken.DeepEquals(m["sources"], Selection()["sources"]), Is.True, "sources는 해석하지 않고 그대로");
            Assert.That(JToken.DeepEquals(m["finalOverrides"], Selection()["finalOverrides"]), Is.True);
            Assert.That(m.ToString(), Does.Not.Contain("someone"), "로컬 경로 없음");
            Assert.That(m.ToString(), Does.Not.Contain("candidates"), "읽지 않는 필드는 옮기지 않음");

            var noSources = Selection();
            noSources.Remove("sources");
            Assert.That(ParseOk(noSources).ManifestJson()["sources"].Type, Is.EqualTo(JTokenType.Null), "sources가 없으면 null");
        }

        [Test]
        public void None_selection_and_empty_overrides_are_valid()
        {
            var none = ParseOk(Selection(new JObject { ["material.opacity"] = 0.6 }, candidate: null, none: true));
            Assert.That(none.None, Is.True);
            Assert.That(none.SelectedCandidateId, Is.Null);
            Assert.That(none.ManifestJson()["selectedCandidateId"].Type, Is.EqualTo(JTokenType.Null));
            var empty = ParseOk(Selection(new JObject()));
            Assert.That(empty.Overrides.IsEmpty, Is.True);
            Assert.That(((JObject)empty.ManifestJson()["finalOverrides"]).Count, Is.EqualTo(0));
            var noId = PlacementSelection.Parse(Selection(candidate: null).ToString(), "s.json", "ab", out var e);
            Assert.That(e, Is.Empty);
            Assert.That(noId.Warnings.Single(), Does.Contain("selectedCandidateId가 null"), "none false인데 id 없음 → 경고만");
        }

        [Test]
        public void Spec_sha_mismatch_refuses_with_a_reason()
        {
            var s = ParseOk(Selection(sha: Sha.ToUpperInvariant()));
            Assert.That(s.SpecMismatch(Sha), Is.Null, "대소문자는 따지지 않는다");
            string why = s.SpecMismatch("0000000000000000000000000000000000000000000000000000000000000000");
            Assert.That(why, Does.Contain("specSha256"));
            Assert.That(why, Does.Contain("시작하지 않습니다"));
            Assert.That(s.SpecMismatch(null), Is.Not.Null);
        }

        [Test]
        public void Unknown_or_bad_override_keys_and_missing_fields_are_refused()
        {
            Assert.That(ParseErrors(Selection(new JObject { ["material.glow"] = 0.5 })).Single(), Does.Contain("material.glow"));
            Assert.That(ParseErrors(Selection(new JObject { ["material.opacity"] = 1.5 })).Single(), Does.Contain("0–1 밖"));
            Assert.That(ParseErrors(Selection(new JObject { ["form.type"] = "cloud" })).Single(), Does.Contain("모르는 형태"));
            Assert.That(ParseErrors(Selection(new JObject { ["layout.distance"] = 0.5 })).Single(), Does.Contain("위치·거리는 실험 조건"));
            Assert.That(ParseErrors(Selection(new JObject { ["layout.verticalOffset"] = 0.5 })).Single(), Does.Contain("layout.verticalOffset"));
            Assert.That(ParseErrors(Selection(sha: "abc")).Single(), Does.Contain("64자"));
            Assert.That(ParseErrors(Selection(candidate: "c1", none: true)).Single(), Does.Contain("알 수 없음"));
            foreach (var field in new[] { "formatVersion", "specSha256", "finalOverrides", "selection" })
            {
                var o = Selection();
                o.Remove(field);
                Assert.That(ParseErrors(o).Any(x => x.Contains(field)), Is.True, field + " 없음");
            }
            var badNone = Selection();
            badNone["selection"]["none"] = "no";
            Assert.That(ParseErrors(badNone).Single(), Does.Contain("selection.none"));
            var arr = Selection();
            arr["finalOverrides"] = new JArray();
            Assert.That(ParseErrors(arr).Single(), Does.Contain("finalOverrides"));
            Assert.That(PlacementSelection.Parse("[1]", "s.json", "ab", out var e1), Is.Null);
            Assert.That(e1.Single(), Does.Contain("객체"));
            Assert.That(PlacementSelection.Parse("{ nope", "s.json", "ab", out var e2), Is.Null);
            Assert.That(e2.Single(), Does.Contain("JSON"));
        }

        [Test]
        public void Unknown_format_version_warns_but_reads()
        {
            var other = ParseOk(Selection(format: "chatbot-selection/1"));
            Assert.That(other.Warnings.Single(), Does.Contain("접두어"));
            var newer = ParseOk(Selection(format: "ifs-selection/0.9"));
            Assert.That(newer.Warnings.Single(), Does.Contain("ifs-selection/0.1"));
            Assert.That(ParseOk(Selection()).Warnings, Is.Empty);
        }

        [Test]
        public void Synthetic_validation_selection_files_parse()
        {
            // docs/validation/runner-selection/inputs/의 손으로 만든 합성 선택 파일 3개(자동 시행 검증 입력)가 계약대로 읽히는지.
            // specSha256은 이 PC에서 체크아웃된 EX02.json 바이트 기준이라(줄바꿈 설정에 따라 다름) 여기서는 형식만 본다.
            string dir = Path.GetFullPath(Path.Combine(Application.streamingAssetsPath, "..", "..", "..", "docs", "validation", "runner-selection", "inputs"));
            if (!Directory.Exists(dir)) Assert.Ignore("docs/validation/runner-selection/inputs 없음: " + dir);
            var expect = new Dictionary<string, (bool none, string id, int keys)>
            {
                ["sel_chosen_adjusted.json"] = (false, "c2", 5),
                ["sel_none_of_these.json"] = (true, null, 1),
                ["sel_no_overrides.json"] = (false, "c0", 0),
            };
            foreach (var kv in expect)
            {
                var s = PlacementSelection.Load(Path.Combine(dir, kv.Key), out var errors);
                Assert.That(errors, Is.Empty, kv.Key);
                Assert.That(s.Warnings, Is.Empty, kv.Key);
                Assert.That(s.None, Is.EqualTo(kv.Value.none), kv.Key);
                Assert.That(s.SelectedCandidateId, Is.EqualTo(kv.Value.id), kv.Key);
                Assert.That(s.Overrides.Numbers.Count + s.Overrides.Categories.Count, Is.EqualTo(kv.Value.keys), kv.Key);
                Assert.That(s.Sources, Is.Not.Null, kv.Key);
            }
        }

        [Test]
        public void Load_hashes_the_file_bytes_and_keeps_only_the_name()
        {
            string path = Path.Combine(_tmp, "selection.json");
            File.WriteAllText(path, Selection().ToString(), new UTF8Encoding(true));   // BOM이 있어도 읽는다
            var s = PlacementSelection.Load(path, out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(s.Sha256, Is.EqualTo(OwnershipManifest.Sha256OfFile(path)));
            Assert.That(s.FileName, Is.EqualTo("selection.json"));
            Assert.That(PlacementSelection.Load(Path.Combine(_tmp, "none.json"), out var e2), Is.Null);
            Assert.That(e2.Single(), Does.Contain("읽지 못함"));
        }

        // ── 적용 확인 ────────────────────────────────────────────────────
        [Test]
        public void Applied_overrides_report_drawn_values_and_flag_keys_that_did_not_apply()
        {
            var spec = SceneSpecJson.Parse(File.ReadAllText(OwnershipTestSpecs.ExamplePath("EX02.json"), Encoding.UTF8));
            var sel = ParseOk(Selection(new JObject { ["form.type"] = "fragments", ["material.brightness"] = 0.35, ["material.color.h"] = 0.6 }));
            Assert.That(sel.CheckApplicable(spec, new SceneDefaults()), Is.Empty);
            var drawn = SceneParams.FromSpec(spec, new SceneDefaults());
            sel.Overrides.ApplyTo(drawn);
            var applied = PlacementSelection.AppliedOverrides(sel.Overrides, drawn, null, out var notApplied);
            Assert.That(notApplied, Is.Empty);
            Assert.That(applied.Properties().Select(p => p.Name), Is.EqualTo(new[] { "form.type", "material.brightness", "material.color.h" }), "키 이름순");
            Assert.That((string)applied["form.type"], Is.EqualTo("fragments"));
            Assert.That((double)applied["material.brightness"], Is.EqualTo(0.35));

            var notDrawn = SceneParams.FromSpec(spec, new SceneDefaults());   // 덮어쓰기를 얹지 않은 값 = 적용 실패를 흉내
            PlacementSelection.AppliedOverrides(sel.Overrides, notDrawn, null, out var missing);
            Assert.That(missing.Count, Is.EqualTo(3));
            Assert.That(missing.Any(m => m.StartsWith("form.type")), Is.True);

            Assert.That(PlacementSelection.AppliedOverrides(null, drawn, null, out var none).Count, Is.EqualTo(0));
            Assert.That(none, Is.Empty);

            var shape = ParseOk(Selection(new JObject { ["form.type"] = "mist", ["shapeModel"] = "Cube" }));
            Assert.That(shape.CheckApplicable(spec, new SceneDefaults()).Single(), Does.Contain("form.type=blob에만"), "SceneLoader.CheckVariant와 같은 규칙");
            var cube = ParseOk(Selection(new JObject { ["shapeModel"] = "Cube" }));
            PlacementSelection.AppliedOverrides(cube.Overrides, drawn, "Sphere", out var wrongModel);
            Assert.That(wrongModel.Single(), Does.Contain("shapeModel"));
            Assert.That((string)PlacementSelection.AppliedOverrides(cube.Overrides, drawn, "Cube", out _)["shapeModel"], Is.EqualTo("Cube"));
        }

        // ── manifest 0.2 ─────────────────────────────────────────────────
        PlacementSession NewSession(PlacementConfig cfg, PlacementTaskText text = null, PlacementSelection selection = null, JObject applied = null)
        {
            text = text ?? PlacementTests.LoadText();
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = 2, SessionId = "SYN-SEL", SpecFile = "EX02.json", SpecSha256 = Sha,
                StartedUtc = new DateTime(2026, 11, 23, 4, 5, 6, DateTimeKind.Utc), InputSource = "auto", AutoMode = true,
                TaskTextFile = text.FileName, TaskTextVersion = text.Version, TaskTextDraftKeys = text.DraftKeys.ToArray(),
                Selection = selection, AppliedOverrides = applied,
            };
            return new PlacementSession(cfg, text, info, Path.Combine(_tmp, "records"), null, selection?.Warnings);
        }

        static void RunToEnd(PlacementSession s, PlacementAutoScript auto = null)
        {
            auto = auto ?? new PlacementAutoScript();
            for (int i = 0; i < 200000 && !s.Finished; i++) auto.Step(s, 0.02, PlacementAutoScript.ScriptedHead(s.Now));
            Assert.That(s.Completed, Is.True);
        }

        [Test]
        public void Manifest_0_2_records_selection_and_applied_overrides()
        {
            var sel = ParseOk(Selection(format: "ifs-selection/0.3"));
            var applied = new JObject { ["form.type"] = "fragments", ["material.brightness"] = 0.35 };
            string dir;
            using (var s = NewSession(PlacementTests.ShortConfig("view"), selection: sel, applied: applied))
            {
                RunToEnd(s);
                dir = s.RecordDirectory;
            }
            var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(dir, "manifest.json")));
            Assert.That((string)m["recordVersion"], Is.EqualTo("ifs-placement/0.2"));
            Assert.That((string)m["recordVersion"], Does.StartWith("ifs-placement/"), "분석기는 접두어로 읽는다");
            Assert.That(((JObject)m["selection"]).Properties().Select(p => p.Name),
                Is.EqualTo(new[] { "file", "sha256", "formatVersion", "none", "selectedCandidateId", "finalOverrides", "sources" }));
            Assert.That((string)m["selection"]["file"], Is.EqualTo("selection.json"));
            Assert.That((string)m["selection"]["formatVersion"], Is.EqualTo("ifs-selection/0.3"));
            Assert.That((string)m["selection"]["sources"]["material.brightness"], Is.EqualTo("edited"));
            Assert.That(JToken.DeepEquals(m["appliedOverrides"], applied), Is.True);
            Assert.That(File.ReadAllText(Path.Combine(dir, "manifest.json")), Does.Not.Contain("someone"));
            var warn = File.ReadAllLines(Path.Combine(dir, "events.csv")).Where(l => l.Contains(",warning,")).ToList();
            Assert.That(warn.Any(l => l.Contains("formatVersion ifs-selection/0.3")), Is.True, "모르는 버전 경고가 events.csv에");
        }

        // ── 평정 범위 ────────────────────────────────────────────────────
        /// <summary>기본 문구 파일에 0–10 사전 문항 하나(m1p_test)를 더한 테스트용 문구(실제 파일에는 넣지 않는다).</summary>
        static PlacementTaskText TextWithZeroToTen(bool optionalOnly = false)
        {
            var raw = JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
            ((JObject)raw["texts"]).Add("m1p_test", new JObject
            {
                ["text"] = "합성 0–10 문항",
                ["when"] = "pre",
                ["min"] = 0,
                ["max"] = 10,
                ["anchors"] = new JObject { ["0"] = "전혀", ["5"] = "중간", ["10"] = "완전히" },
                ["status"] = "draft",
                ["source"] = "테스트 합성 문항(실제 문구 파일에 없음)",
            });
            return PlacementTaskText.Parse(raw.ToString(), "test.json");
        }

        [Test]
        public void Item_range_fields_default_to_one_to_seven_and_are_validated()
        {
            var t = PlacementTests.LoadText();
            Assert.That(t.Items.All(i => i.Min == 1 && i.Max == 7), Is.True, "min·max가 없는 기존 문항은 1–7");
            Assert.That(PlacementTaskText.Load(ScaleAPath).Items.All(i => i.Min == 1 && i.Max == 7), Is.True);
            var z = TextWithZeroToTen().Items.First(i => i.Key == "m1p_test");
            Assert.That((z.Min, z.Max), Is.EqualTo((0, 10)));
            Assert.That(z.AnchorLow, Is.EqualTo("전혀"));
            Assert.That(z.AnchorHigh, Is.EqualTo("완전히"));
            Assert.That(PlacementTaskText.ItemDisplay(z), Does.EndWith("0(전혀) — 10(완전히)"));

            var raw = JObject.Parse(File.ReadAllText(DefaultPath, Encoding.UTF8));
            void Bad(Action<JObject> change, string expect)
            {
                var b = (JObject)raw.DeepClone();
                change(b);
                Assert.That(Assert.Throws<FormatException>(() => PlacementTaskText.Parse(b.ToString())).Message, Does.Contain(expect));
            }
            Bad(b => { b["texts"]["own"]["min"] = 7; b["texts"]["own"]["max"] = 7; }, "min < max");
            Bad(b => b["texts"]["own"]["max"] = 101, "≤ 100");
            Bad(b => b["texts"]["own"]["min"] = -1, "0 ≤ min");
            Bad(b => b["texts"]["own"]["max"] = 7.5, "정수");
            Bad(b => b["texts"]["own"]["max"] = "10", "정수");
            Bad(b => ((JObject)b["texts"]["own"]["anchors"])["9"] = "x", "low | high | 1–7");
            Bad(b => b["texts"]["intro"]["max"] = 10, "평정 문항");
            Bad(b => b["texts"]["own"]["optionalWhen"] = "later", "optionalWhen");
            var ok = (JObject)raw.DeepClone();
            ok["texts"]["own"]["max"] = 9;
            ((JObject)ok["texts"]["own"]["anchors"])["9"] = "x";
            Assert.That(PlacementTaskText.Parse(ok.ToString()).Items.First(i => i.Key == "own").AnchorAt(9), Is.EqualTo("x"), "범위를 넓히면 숫자 키도 그 범위");
        }

        [Test]
        public void Zero_to_ten_item_takes_two_digit_keyboard_input_and_controller_starts_at_five()
        {
            var text = TextWithZeroToTen();
            using (var s = NewSession(PlacementTests.ShortConfig("view"), text))
            {
                for (int i = 0; i < 100000 && s.Phase != PlacementPhase.PreItems; i++)
                {
                    s.Tick(0.02, new PlacementInputFrame(), PlacementAutoScript.ScriptedHead(s.Now));
                    if (s.Phase == PlacementPhase.Intro) s.PressNext();
                }
                Assert.That(s.CurrentItem.Key, Is.EqualTo("own"));
                s.PressDigit(0);
                Assert.That(s.PendingRating, Is.Null, "1–7 문항에서 0은 무시(예전 그대로)");
                s.PressDigit(6);
                s.PressDigit(7);
                Assert.That(s.PendingRating, Is.EqualTo(6), "한 자리 범위는 한 번만(예전 그대로)");
                s.PressConfirm();

                Assert.That(s.CurrentItem.Key, Is.EqualTo("m1p_test"));
                s.PressDigit(1);
                Assert.That(s.PendingRating, Is.EqualTo(1));
                s.PressDigit(1);
                Assert.That(s.PendingRating, Is.EqualTo(1), "11은 범위 밖이라 받지 않는다");
                s.PressDigit(0);
                Assert.That(s.PendingRating, Is.EqualTo(10), "1 → 0 = 10");
                s.PressDigit(0);
                Assert.That(s.PendingRating, Is.EqualTo(10), "세 자리는 받지 않는다");
                s.PressBackspace();
                Assert.That(s.PendingRating, Is.Null);
                Assert.That(s.PendingDigits, Is.Empty);
                s.PressDigit(0);
                Assert.That(s.PendingRating, Is.EqualTo(0), "0도 범위 안");
                s.PressDigit(5);
                Assert.That(s.PendingRating, Is.EqualTo(0), "0 뒤에는 붙이지 않는다");
                s.PressBackspace();
                s.PressDigit(1);
                s.PressDigit(0);
                s.PressConfirm();
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.PreWait));
                string dir = s.RecordDirectory;
                s.Abort();
                var rows = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).Select(l => l.Split(',')).ToList();
                Assert.That(rows.Select(r => r[0] + "/" + r[2]), Is.EqualTo(new[] { "own/6", "m1p_test/10" }));
                var cancels = File.ReadAllLines(Path.Combine(dir, "events.csv")).Where(l => l.Contains(",rating_cancel,")).ToList();
                Assert.That(cancels.Count, Is.EqualTo(2));
                Assert.That(cancels[0], Does.Contain("rating=10"));
            }

            var cfg = PlacementTests.ShortConfig("view");
            cfg.participantRatesWithController = true;
            using (var s = NewSession(cfg, text))
            {
                for (int i = 0; i < 100000 && s.Phase != PlacementPhase.PreItems; i++)
                {
                    s.Tick(0.02, new PlacementInputFrame(), PlacementAutoScript.ScriptedHead(s.Now));
                    if (s.Phase == PlacementPhase.Intro) s.PressNext();
                }
                s.PressDigit(4);
                s.PressConfirm();
                Assert.That(s.CurrentItem.Key, Is.EqualTo("m1p_test"));
                var seen = new List<int?>();
                foreach (int step in new[] { 1, 1, 1, 1, 1, 1, 1, -1 })
                {
                    s.Tick(0.02, new PlacementInputFrame { RateStep = step }, PlacementAutoScript.ScriptedHead(s.Now));
                    seen.Add(s.RatingCursor);
                }
                Assert.That(seen, Is.EqualTo(new int?[] { 5, 6, 7, 8, 9, 10, 10, 9 }), "가운데(5)에서 시작, 10에서 멈춤");
                s.Tick(0.02, new PlacementInputFrame { RateSubmitDown = true }, PlacementAutoScript.ScriptedHead(s.Now));
                Assert.That(s.Phase, Is.EqualTo(PlacementPhase.PreWait));
                string dir = s.RecordDirectory;
                s.Abort();
                Assert.That(File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Last(), Does.StartWith("m1p_test,pre,9,"));
            }
        }

        // ── 두 평정 문항(G13) ─────────────────────────────────────────────
        [Test]
        public void G13_items_are_draft_with_source_in_both_files_post_by_default()
        {
            foreach (var path in new[] { DefaultPath, ScaleAPath })
            {
                var t = PlacementTaskText.Load(path);
                var raw = (JObject)JObject.Parse(File.ReadAllText(path, Encoding.UTF8))["texts"];
                foreach (var (key, text) in new[] { ("appearance_match", AppearanceText), ("representativeness", RepresentText) })
                {
                    var it = t.Items.Single(i => i.Key == key);
                    Assert.That(it.Text, Is.EqualTo(text), key);
                    Assert.That(t.Status(key), Is.EqualTo("draft"), key + ": status draft(X35 방식으로 경고)");
                    Assert.That(t.DraftKeys, Does.Contain(key));
                    Assert.That((string)raw[key]["source"], Does.StartWith(G13Source), key);
                    Assert.That(it.When, Is.EqualTo(new[] { "post" }), key + ": 헤드셋 기본은 사후만(사전 측정은 데스크톱 — G11)");
                    Assert.That(it.OptionalWhen, Is.EqualTo(new[] { "pre" }), key + ": 사전은 설정으로");
                    Assert.That((it.Min, it.Max), Is.EqualTo((1, 7)));
                    Assert.That(it.AnchorLow, Is.Not.Empty);
                    Assert.That(it.AnchorHigh, Is.Not.Empty);
                }
            }
            Assert.That(PlacementTests.LoadText().Version, Is.EqualTo("0.2"), "문항을 더해 문구 파일 버전을 올림");
            Assert.That(PlacementTaskText.Load(ScaleAPath).Version, Is.EqualTo("0.2-scaleA"));
        }

        [Test]
        public void Optional_pre_setting_adds_the_two_items_before_and_disabled_items_drop_the_old_one()
        {
            var t = PlacementTests.LoadText();
            Assert.That(t.ItemsFor("pre", false, null).Select(i => i.Key), Is.EqualTo(new[] { "own" }), "기본: 사전에는 기존 문항만");
            Assert.That(t.ItemsFor("pre", true, null).Select(i => i.Key), Is.EqualTo(new[] { "own", "appearance_match", "representativeness" }));
            Assert.That(t.ItemsFor("post", false, new[] { "own" }).Select(i => i.Key),
                Is.EqualTo(new[] { "appearance_match", "representativeness", "want_to_know", "withdraw_attention" }), "기존 '내 것 같다' 끄기");
            Assert.That(new PlacementConfig { disabledItems = new[] { "own", "S4", "nope" } }.UnknownDisabledItems(t), Is.EqualTo(new[] { "S4", "nope" }));
            Assert.That(new PlacementConfig { disabledItems = new[] { " " } }.Validate().Any(e => e.StartsWith("disabledItems")), Is.True);
            var json = new PlacementConfig { askOptionalItems = true, disabledItems = new[] { "own" } }.ToJson();
            Assert.That((bool)json["askOptionalItems"], Is.True, "manifest config에 남는다");
            Assert.That(json["disabledItems"].Select(k => (string)k), Is.EqualTo(new[] { "own" }));
            var defaults = new PlacementConfig().ToJson();
            Assert.That((bool)defaults["askOptionalItems"], Is.False);
            Assert.That(((JArray)defaults["disabledItems"]).Count, Is.EqualTo(0));
            var clone = new PlacementConfig { disabledItems = new[] { "own" } }.Clone();
            Assert.That(clone.disabledItems, Is.EqualTo(new[] { "own" }));

            // 세션: 사전에도 묻기 켬 + 기존 문항 끔
            var cfg = PlacementTests.ShortConfig("place");
            cfg.askOptionalItems = true;
            cfg.disabledItems = new[] { "own" };
            string dir;
            using (var s = NewSession(cfg)) { RunToEnd(s); dir = s.RecordDirectory; }
            var rows = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).Select(l => l.Split(',')).Select(r => r[0] + "/" + r[1]).ToList();
            Assert.That(rows, Is.EqualTo(new[]
            {
                "appearance_match/pre", "representativeness/pre",
                "appearance_match/post", "representativeness/post", "want_to_know/post", "withdraw_attention/post", "placed_by_me/check",
            }));

            // 기본 설정: 사전 = own만, 사후에 두 문항
            using (var s = NewSession(PlacementTests.ShortConfig("place"))) { RunToEnd(s); dir = s.RecordDirectory; }
            rows = File.ReadAllLines(Path.Combine(dir, "ratings.csv")).Skip(1).Select(l => l.Split(',')).Select(r => r[0] + "/" + r[1]).ToList();
            Assert.That(rows.Where(r => r.EndsWith("/pre")), Is.EqualTo(new[] { "own/pre" }));
            Assert.That(rows, Does.Contain("appearance_match/post"));
            Assert.That(rows, Does.Contain("representativeness/post"));

            // 사전 문항을 모두 끄면 사전 평정 단계를 건너뛴다
            cfg = PlacementTests.ShortConfig("view");
            cfg.disabledItems = new[] { "own" };
            using (var s = NewSession(cfg)) { RunToEnd(s); dir = s.RecordDirectory; }
            var phases = File.ReadAllLines(Path.Combine(dir, "events.csv")).Skip(1).Select(l => l.Split(',')).Where(c => c[1] == "phase").Select(c => c[2]).ToList();
            Assert.That(phases, Does.Not.Contain("pre_items"));
            Assert.That(phases, Does.Contain("post_items"));
        }
    }
}
