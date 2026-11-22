// 배치 러너가 읽는 선택 파일(selection.json, 형식 ifs-selection/0.1 — 챗봇 쪽 후보 선택·조절 단계가 쓴다. 결정 G15·G23, D8).
// 러너가 읽는 필드는 다음으로 고정한다. 그 밖의 필드는 읽지 않는다(무시).
//   formatVersion      "ifs-selection/0.1". 접두어 "ifs-selection/"이 아니거나 모르는 버전이면 경고(시작은 함).
//   specSha256         원본 spec 파일의 sha256(16진 64자). 러너가 읽은 spec 파일 바이트의 sha256과 다르면 시작 거부.
//   finalOverrides     평평한 덮어쓰기 객체(SceneOverrideJson.Parse가 받는 형식, {} = 덮어쓰기 없음). 모르는 키·0–1 밖·잘못된 값이면 시작 거부.
//                      위치·거리(layout.distance, layout.verticalOffset)는 실험 조건이라(G10, 시작 자리는 실험 설정) 넣을 수 없다 — 거부.
//   selection          { selectedCandidateId: 문자열 | null, none: bool }. none = "맞는 것이 없다"(G23).
//                      none이 true인데 selectedCandidateId가 있으면 거부(어느 쪽인지 모름), none이 false인데 id가 null이면 경고.
//   sources            슬롯별 출처(말함/고름/고침/기본값). 러너는 해석하지 않고 manifest에 그대로 옮긴다(없으면 null).
// 덮어쓰기는 형상을 만들 때 한 번 적용하고 조건 단계 동안 바뀌지 않는다(VR 안에서 속성을 고치는 입력은 없음 — G11).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementSelection
    {
        public const string FormatPrefix = "ifs-selection/";
        public const string KnownFormatVersion = "ifs-selection/0.1";
        /// <summary>선택 파일 덮어쓰기에 넣을 수 없는 키(위치·거리는 실험 조건 — G10). 러너가 시작 자리를 실험 설정으로 정한다.</summary>
        public static readonly string[] ForbiddenOverrideKeys = { "layout.distance", "layout.verticalOffset" };

        /// <summary>파일 이름만(경로는 기록에 남기지 않는다).</summary>
        public string FileName { get; private set; }
        /// <summary>선택 파일 자체의 sha256.</summary>
        public string Sha256 { get; private set; }
        public string FormatVersion { get; private set; }
        public string SpecSha256 { get; private set; }
        public string SelectedCandidateId { get; private set; }
        public bool None { get; private set; }
        /// <summary>finalOverrides 원문(키 순서 그대로).</summary>
        public JObject FinalOverridesJson { get; private set; }
        /// <summary>finalOverrides를 SceneOverrideJson.Parse로 읽은 것(빈 객체면 IsEmpty).</summary>
        public SceneOverride Overrides { get; private set; }
        /// <summary>sources 원문(해석하지 않음). 없으면 null.</summary>
        public JToken Sources { get; private set; }
        /// <summary>시작은 하되 남겨 둘 경고(확인 화면, events.csv warning).</summary>
        public List<string> Warnings { get; } = new List<string>();

        PlacementSelection() { }

        /// <summary>선택 파일 글을 읽는다. 오류가 하나라도 있으면 null을 돌려주고 errors에 이유를 담는다.</summary>
        public static PlacementSelection Parse(string json, string fileName, string fileSha256, out List<string> errors)
        {
            errors = new List<string>();
            JToken root;
            try
            {
                using var reader = new JsonTextReader(new StringReader(json ?? "")) { DateParseHandling = DateParseHandling.None, FloatParseHandling = FloatParseHandling.Double };
                root = JToken.ReadFrom(reader);
                if (reader.Read()) throw new JsonReaderException("JSON 뒤에 남은 내용이 있음");
            }
            catch (JsonException e)
            {
                errors.Add("선택 파일 JSON을 읽지 못함: " + e.Message);
                return null;
            }
            if (!(root is JObject o))
            {
                errors.Add("선택 파일은 JSON 객체여야 함(지금 " + root.Type + ")");
                return null;
            }
            var s = new PlacementSelection
            {
                FileName = fileName != null ? OwnershipManifest.FileNameOnly(fileName) : null,
                Sha256 = fileSha256,
            };

            // formatVersion
            var fv = o["formatVersion"];
            if (fv == null || fv.Type != JTokenType.String || string.IsNullOrWhiteSpace((string)fv))
                errors.Add("formatVersion이 없음(문자열이어야 함)");
            else
            {
                s.FormatVersion = (string)fv;
                if (!s.FormatVersion.StartsWith(FormatPrefix, StringComparison.Ordinal))
                    s.Warnings.Add($"선택 파일 formatVersion {s.FormatVersion}: 접두어가 {FormatPrefix}가 아님 — 다른 형식일 수 있음(읽는 필드만 확인함)");
                else if (s.FormatVersion != KnownFormatVersion)
                    s.Warnings.Add($"선택 파일 formatVersion {s.FormatVersion}: 이 러너가 아는 버전은 {KnownFormatVersion} — 읽는 필드만 확인함");
            }

            // specSha256
            var ss = o["specSha256"];
            if (ss == null || ss.Type != JTokenType.String) errors.Add("specSha256이 없음(문자열이어야 함)");
            else
            {
                string v = ((string)ss).Trim().ToLowerInvariant();
                if (v.Length != 64 || v.Any(c => !Uri.IsHexDigit(c))) errors.Add("specSha256은 16진 64자여야 함: " + (string)ss);
                else s.SpecSha256 = v;
            }

            // finalOverrides
            var fo = o["finalOverrides"];
            if (fo == null || fo.Type != JTokenType.Object) errors.Add("finalOverrides가 없음(객체여야 함, 덮어쓰기가 없으면 {})");
            else
            {
                s.FinalOverridesJson = (JObject)fo.DeepClone();
                var ov = SceneOverrideJson.Parse(fo.ToString(Formatting.None), out var oe);
                if (ov == null) errors.AddRange(oe.Select(e => "finalOverrides: " + e));
                else
                {
                    foreach (var k in ForbiddenOverrideKeys)
                        if (ov.Numbers.ContainsKey(k))
                            errors.Add($"finalOverrides: {k}는 넣을 수 없음(위치·거리는 실험 조건 — 시작 자리는 실험 설정 startDistanceM·startHeightM, G10)");
                    s.Overrides = ov;
                }
            }

            // selection
            var sel = o["selection"];
            if (sel == null || sel.Type != JTokenType.Object) errors.Add("selection이 없음(객체 { selectedCandidateId, none })");
            else
            {
                var none = sel["none"];
                if (none == null || none.Type != JTokenType.Boolean) errors.Add("selection.none이 없음(true | false)");
                else s.None = (bool)none;
                var id = sel["selectedCandidateId"];
                if (id == null || id.Type == JTokenType.Null) s.SelectedCandidateId = null;
                else if (id.Type == JTokenType.String && !string.IsNullOrWhiteSpace((string)id)) s.SelectedCandidateId = (string)id;
                else errors.Add("selection.selectedCandidateId는 비어 있지 않은 문자열 또는 null");
                if (none != null && none.Type == JTokenType.Boolean)
                {
                    if (s.None && s.SelectedCandidateId != null)
                        errors.Add($"selection.none이 true인데 selectedCandidateId({s.SelectedCandidateId})가 있음 — 고른 것인지 '맞는 것이 없다'인지 알 수 없음");
                    else if (!s.None && s.SelectedCandidateId == null)
                        s.Warnings.Add("선택 파일 selection.none이 false인데 selectedCandidateId가 null — 고른 후보를 알 수 없음(기록에는 그대로 남김)");
                }
            }

            // sources(해석하지 않음)
            var src = o["sources"];
            s.Sources = src == null ? null : src.DeepClone();

            return errors.Count == 0 ? s : null;
        }

        /// <summary>파일에서 읽는다(바이트 그대로 sha256). 읽기 오류도 errors로.</summary>
        public static PlacementSelection Load(string path, out List<string> errors)
        {
            byte[] bytes;
            try { bytes = File.ReadAllBytes(path); }
            catch (Exception e)
            {
                errors = new List<string> { "선택 파일을 읽지 못함: " + e.Message };
                return null;
            }
            string text = new System.Text.UTF8Encoding(false).GetString(bytes);
            if (text.Length > 0 && text[0] == '﻿') text = text.Substring(1);
            return Parse(text, Path.GetFileName(path), OwnershipManifest.Sha256Hex(bytes), out errors);
        }

        /// <summary>러너가 읽은 spec 파일의 sha256과 다르면 시작 거부 이유, 같으면 null.</summary>
        public string SpecMismatch(string specSha256)
        {
            string actual = (specSha256 ?? "").Trim().ToLowerInvariant();
            return actual == SpecSha256 ? null
                : $"선택 파일의 specSha256({Short(SpecSha256)}…)이 고른 spec 파일의 sha256({Short(actual)}…)과 다릅니다 — 다른 spec의 선택이거나 spec이 바뀌었습니다. 시작하지 않습니다";
        }

        static string Short(string s) => string.IsNullOrEmpty(s) ? "-" : s.Substring(0, Math.Min(12, s.Length));

        /// <summary>로드 전에 확인할 수 있는 적용 불가(모양 모형 강제는 form.type=blob에만 — SceneLoader.CheckVariant와 같은 규칙). 없으면 빈 목록.</summary>
        public List<string> CheckApplicable(SceneSpecV2 spec, SceneDefaults defaults)
        {
            var e = new List<string>();
            if (Overrides == null || Overrides.IsEmpty || spec == null) return e;
            var p = SceneParams.FromSpec(spec, defaults ?? new SceneDefaults(), false);
            Overrides.ApplyTo(p);
            string model = Overrides.ShapeModel ?? ShapeMapping.Resolve(spec).Model;
            string form = p.GetCategory("form.type");
            if (model != null && form != "blob")
                e.Add($"finalOverrides: 모양 모형 {model}은 form.type=blob에만 쓸 수 있는데 덮어쓴 뒤 form.type이 {form}임(적용할 수 없음)");
            return e;
        }

        /// <summary>로드한 뒤 실제로 적용된 값(키 → 그려지는 해석값). 덮어쓰기 키마다 해석값이 덮어쓰기 값과 같은지 확인하고,
        /// 다르면 notApplied에 이유를 담는다(러너는 시작을 거부한다). 덮어쓰기가 없으면 빈 객체.</summary>
        public static JObject AppliedOverrides(SceneOverride overrides, SceneParams drawn, string drawnShapeModel, out List<string> notApplied)
        {
            notApplied = new List<string>();
            var applied = new JObject();
            if (overrides == null || overrides.IsEmpty) return applied;
            if (drawn == null)
            {
                notApplied.Add("형상이 로드되지 않아 덮어쓰기를 확인할 수 없음");
                return applied;
            }
            foreach (var key in overrides.Numbers.Keys.Concat(overrides.Categories.Keys).OrderBy(k => k, StringComparer.Ordinal))
            {
                if (overrides.Numbers.TryGetValue(key, out double want))
                {
                    double got = drawn.GetNumber(key);
                    if (Math.Abs(got - want) > 1e-9) notApplied.Add($"{key}: 덮어쓰기 {want}인데 그려지는 값 {got}");
                    else applied[key] = got;
                }
                else
                {
                    string want2 = overrides.Categories[key], got2 = drawn.GetCategory(key);
                    if (got2 != want2) notApplied.Add($"{key}: 덮어쓰기 {want2}인데 그려지는 값 {got2}");
                    else applied[key] = got2;
                }
            }
            if (overrides.ShapeModel != null)
            {
                if (drawnShapeModel != overrides.ShapeModel) notApplied.Add($"{SceneOverrideJson.ShapeModelKey}: 덮어쓰기 {overrides.ShapeModel}인데 그려지는 모형 {drawnShapeModel ?? "없음"}");
                else applied[SceneOverrideJson.ShapeModelKey] = drawnShapeModel;
            }
            return applied;
        }

        static JToken Str(string v) => v != null ? new JValue(v) : JValue.CreateNull();

        /// <summary>manifest의 selection 객체.</summary>
        public JObject ManifestJson() => new JObject
        {
            ["file"] = Str(FileName),
            ["sha256"] = Str(Sha256),
            ["formatVersion"] = Str(FormatVersion),
            ["none"] = None,
            ["selectedCandidateId"] = Str(SelectedCandidateId),
            ["finalOverrides"] = FinalOverridesJson?.DeepClone() ?? new JObject(),
            ["sources"] = Sources?.DeepClone(),
        };
    }
}
