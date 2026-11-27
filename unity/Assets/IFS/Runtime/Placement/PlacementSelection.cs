// 배치 러너가 읽는 선택 파일(selection.json, 형식 ifs-selection/0.1·0.2·0.3 — 챗봇 쪽 후보 선택·조절 단계가 쓴다. 결정 G15·G23, D8, G31–G34, G62).
//   0.3(G62): form.asset(고른 생성 형태 메시 — FormAssetRef, 러너가 GLB를 읽어 절차 메시 대신 씀), 출처 값 generated_chosen,
//             defaultFormSource·selection.acceptedDefault(기본 후보·그대로 확정했는지 — manifest selection에 옮김). skipped·colorChanged 필수는 0.2와 같다.
// 러너가 읽는 필드는 다음으로 고정한다. 그 밖의 필드는 읽지 않는다(무시).
//   formatVersion      "ifs-selection/0.1" 또는 "ifs-selection/0.2"(KnownFormatVersions). 접두어 "ifs-selection/"이 아니거나 모르는 버전이면
//                      경고(시작은 함). 모르는 버전은 0.2 규칙으로 읽는다.
//   specSha256         저장된 spec 파일 바이트의 sha256(16진 64자). 러너가 읽은 spec 파일 바이트의 sha256과 다르면 시작 거부.
//   spec.sha256Basis   (있으면) specSha256을 무엇으로 쟀는지. "file"이 아니면(예: 예전 챗봇이 파일 없는 실행에서 쓰던 "serialized",
//                      지금 챗봇의 "none") 파일 바이트 해시가 아니므로 이유를 밝히고 시작 거부(G26, CP9 지적 1).
//                      없으면 파일 기준으로 본다(러너 쪽 합성 파일에는 spec 객체가 없다).
//   runnerReady        (있으면) false면 챗봇이 러너에 넘길 수 없다고 적은 파일 — runnerBlockers(이유)를 붙여 시작 거부.
//   finalOverrides     평평한 덮어쓰기 객체(SceneOverrideJson.Parse가 받는 형식, {} = 덮어쓰기 없음). 모르는 키·0–1 밖·잘못된 값이면 시작 거부.
//                      위치·거리(layout.distance, layout.verticalOffset)는 실험 조건이라(G10, 시작 자리는 실험 설정) 넣을 수 없다 — 거부.
//   selection          { selectedCandidateId: 문자열 | null, none: bool, skipped: bool }. none = "맞는 것이 없다"(G23).
//                      skipped = 구별되는 후보가 하나뿐이라 선택 단계를 건너뜀(G34, 0.2에서 필수. 0.1 파일은 없으면 false).
//                      none이 true인데 selectedCandidateId가 있으면 거부(어느 쪽인지 모름). skipped가 true인데 none이 true이거나 id가 있으면 거부.
//                      none·skipped가 모두 false인데 id가 null이면 경고.
//   colorChanged       (0.2에서 필수) 조절에서 색을 바꿨는지(처음 값 ≠ 마지막 값, G31). 0.1 파일은 없으면 null로 기록.
//   sources            슬롯별 출처. 객체여야 하고, 키는 SlotNames, 값은 0.2면 SourceValues 여섯 가지(said|chosen|edited|default|
//                      said_unrendered_chosen|said_unrendered_default — 뒤 둘은 모형이 없는 모양어를 말한 형태 자리, G32),
//                      0.1이면 SourceValues01 네 가지 중 하나여야 한다 — 아니면 시작 거부(G27). 통과하면 manifest에 그대로 옮긴다(없거나 null이면 null).
//                      form.baseVariant(기본 형상 변형값, CP10 G39)는 form.base와 함께만 온다 — form.base 없이 있으면 거부(어느 형상의 변형값인지 모름).
//   safetyFlags        (있으면, G50 (4) — 하위 호환 추가) 넷째 제외 범주(죽음·자해·외상) 낱말이 확정 텍스트에 나온 자리의 목록
//                      [{category, lemma, charSpan, sentence, position, role, scope, formBlock}]. 배열이 아니거나 항목이 객체가 아니면 거부.
//                      시작은 막지 않는다(VR 진행 여부는 연구자가 정함). 공개 속성 SafetyFlags·HasSafetyFlags로 실험자 화면이 읽을 수 있게 두고
//                      manifest selection.safetyFlags에 그대로 옮긴다(파일에 키가 없으면 manifest에도 넣지 않음 — 이전 기록 바이트 그대로).
// 덮어쓰기는 형상을 만들 때 한 번 적용하고 조건 단계 동안 바뀌지 않는다(VR 안에서 속성을 고치는 입력은 없음 — G11).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using FormAssetRef = IFS.SceneSpec.FormAsset.FormAssetRef;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementSelection
    {
        public const string FormatPrefix = "ifs-selection/";
        public const string FormatVersion01 = "ifs-selection/0.1";
        public const string FormatVersion02 = "ifs-selection/0.2";
        public const string FormatVersion03 = "ifs-selection/0.3";
        /// <summary>러너가 아는 선택 파일 버전(0.1: G27까지, 0.2: G31–G34, 0.3: G62 생성 형태 메시). 모두 읽는다.</summary>
        public static readonly string[] KnownFormatVersions = { "ifs-selection/0.1", "ifs-selection/0.2", "ifs-selection/0.3" };
        /// <summary>선택 파일 덮어쓰기에 넣을 수 없는 키(위치·거리는 실험 조건 — G10). 러너가 시작 자리를 실험 설정으로 정한다.</summary>
        public static readonly string[] ForbiddenOverrideKeys = { "layout.distance", "layout.verticalOffset" };
        /// <summary>specSha256을 저장된 spec 파일 바이트로 쟀다는 표시(spec.sha256Basis). 러너는 이것만 받는다(G26).</summary>
        public const string FileBasis = "file";
        /// <summary>sources의 슬롯 이름(shared/schemas/selection.v0.2.json $defs.slotName과 같게 — pytest가 대조한다).
        /// form.base(D6, SceneSpec 2.2.0 기본 형상)와 form.baseVariant(그 변형값, CP10 G39)는 0.2에 하위 호환으로 더한 키다
        /// (0.1 슬롯 + form.base + form.baseVariant). form.baseVariant는 덮어쓰기 키가 아니다(base에서 정해짐).</summary>
        public static readonly string[] SlotNames =
        {
            "form.type", "form.posture", "form.base", "form.baseVariant", "material.color", "material.brightness", "material.saturation",
            "material.roughness", "material.opacity", "material.erosion", "layout.size", "layout.distance",
            "layout.verticalOffset", "motion.type", "motion.speed", "body.part", "body.layer",
        };
        /// <summary>0.2 sources의 출처 값 여섯 가지(스키마 selection.v0.2.json $defs.source): 말함 / 고름 / 고침 / 기본값(G15)
        /// + 모형이 없는 모양어를 말하고 형태 후보에서 고름 / 모형이 없는 모양어를 말했지만 고르지 않아 기본 형태(G32).</summary>
        public static readonly string[] SourceValues = { "said", "chosen", "edited", "default", "said_unrendered_chosen", "said_unrendered_default" };
        /// <summary>0.1 sources의 출처 값 네 가지(selection.v0.1.json). 0.1 파일에 새 값이 있으면 거부한다.</summary>
        public static readonly string[] SourceValues01 = { "said", "chosen", "edited", "default" };
        /// <summary>0.3 sources의 출처 값(selection.v0.3.json $defs.source): 0.2의 여섯 가지 + generated_chosen(생성 형태 후보를 고름, G62).
        /// 0.1·0.2 파일에 generated_chosen이 있으면 거부한다.</summary>
        public static readonly string[] SourceValues03 = { "said", "chosen", "edited", "default", "said_unrendered_chosen", "said_unrendered_default", "generated_chosen" };
        public const string GeneratedChosen = "generated_chosen";

        /// <summary>파일 이름만(경로는 기록에 남기지 않는다).</summary>
        public string FileName { get; private set; }
        /// <summary>선택 파일 자체의 sha256.</summary>
        public string Sha256 { get; private set; }
        public string FormatVersion { get; private set; }
        public string SpecSha256 { get; private set; }
        public string SelectedCandidateId { get; private set; }
        public bool None { get; private set; }
        /// <summary>선택 단계를 건너뜀(G34). 0.1 파일은 false.</summary>
        public bool Skipped { get; private set; }
        /// <summary>조절에서 색을 바꿨는지(G31). 0.1 파일·값 없음이면 null.</summary>
        public bool? ColorChanged { get; private set; }
        /// <summary>finalOverrides 원문(키 순서 그대로).</summary>
        public JObject FinalOverridesJson { get; private set; }
        /// <summary>finalOverrides를 SceneOverrideJson.Parse로 읽은 것(빈 객체면 IsEmpty).</summary>
        public SceneOverride Overrides { get; private set; }
        /// <summary>sources 원문(해석하지 않음). 없으면 null.</summary>
        public JToken Sources { get; private set; }
        /// <summary>G50 (4): 넷째 제외 범주(죽음·자해·외상) 표시 원문(챗봇 selection.json safetyFlags). 파일에 키가 없으면 null.
        /// 실험자 화면이 읽어 알릴 수 있게 둔 공개 속성(러너는 시작을 막지 않음 — VR 진행 여부는 연구자가 정함).</summary>
        public JArray SafetyFlags { get; private set; }
        /// <summary>safetyFlags에 항목이 하나라도 있으면 true.</summary>
        public bool HasSafetyFlags => SafetyFlags != null && SafetyFlags.Count > 0;
        /// <summary>표시된 범주(중복 없이, 나온 순서). 표시가 없으면 빈 목록.</summary>
        public IReadOnlyList<string> SafetyFlagCategories =>
            (SafetyFlags ?? new JArray()).OfType<JObject>().Select(f => f["category"]?.Type == JTokenType.String ? (string)f["category"] : null)
                .Where(c => c != null).Distinct().ToList();
        /// <summary>G62(0.3): 고른 생성 형태 메시(form.asset). 없거나 null이면 null(절차 메시). 러너가 GLB를 읽어 절차 메시 대신 쓴다.</summary>
        public FormAssetRef FormAsset { get; private set; }
        /// <summary>G62(0.3): 그 세션에서 기본이었던 형태 후보 출처(defaultFormSource)와 기본을 그대로 확정했는지(selection.acceptedDefault). 없으면 null.</summary>
        public string DefaultFormSource { get; private set; }
        public bool? AcceptedDefault { get; private set; }
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
                else if (Array.IndexOf(KnownFormatVersions, s.FormatVersion) < 0)
                    s.Warnings.Add($"선택 파일 formatVersion {s.FormatVersion}: 이 러너가 아는 버전은 {string.Join(", ", KnownFormatVersions)} — 읽는 필드만 확인함");
            }
            // 0.1: 옛 규칙(skipped·colorChanged 없음, 출처 네 가지). 0.2: skipped·colorChanged 필수, 출처 여섯 가지.
            // 모르는 버전: 경고만 하고 새 필드는 있으면 읽음(없어도 거부하지 않음), 출처는 여섯 가지까지 받음.
            bool v01 = s.FormatVersion == FormatVersion01;
            bool v02 = s.FormatVersion == FormatVersion02;
            bool v03 = s.FormatVersion == FormatVersion03;

            // specSha256의 기준(spec.sha256Basis)과 챗봇이 적은 runnerReady(G26). 기준이 파일이 아니면 해시를 비교하지 않고 거부한다.
            if (o["spec"] is JObject specInfo && specInfo.TryGetValue("sha256Basis", out var basis))
            {
                string b = basis.Type == JTokenType.String ? (string)basis : basis.ToString(Formatting.None);
                if (b != FileBasis)
                    errors.Add($"spec.sha256Basis가 \"{b}\"임 — specSha256이 저장된 spec 파일 바이트의 해시가 아니라서 러너가 읽는 파일과 비교할 수 없음. " +
                               "챗봇이 spec 파일을 저장한 실행(persist_logs = true)에서 만든 선택 파일과 그 spec 파일을 함께 쓰세요");
            }
            var ready = o["runnerReady"];
            if (ready != null && ready.Type == JTokenType.Boolean && !(bool)ready)
            {
                var why = o["runnerBlockers"] is JArray arr ? string.Join(" / ", arr.Select(x => x.Type == JTokenType.String ? (string)x : x.ToString(Formatting.None))) : "";
                errors.Add("runnerReady가 false임 — 챗봇이 이 선택 파일을 러너에 넘길 수 없다고 적었음" + (why.Length > 0 ? ": " + why : ""));
            }
            else if (ready != null && ready.Type != JTokenType.Boolean)
                errors.Add("runnerReady는 true | false여야 함");

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
                var skipped = sel["skipped"];
                if (skipped != null && skipped.Type == JTokenType.Boolean) s.Skipped = (bool)skipped;
                else if (skipped != null && skipped.Type != JTokenType.Null) errors.Add("selection.skipped는 true | false여야 함");
                else if (v02 || v03) errors.Add($"selection.skipped가 없음({s.FormatVersion}에서 필수, true | false — G34)");
                var acc = sel["acceptedDefault"];
                if (acc != null && acc.Type == JTokenType.Boolean) s.AcceptedDefault = (bool)acc;
                else if (acc != null && acc.Type != JTokenType.Null) errors.Add("selection.acceptedDefault는 true | false | null(G62)");
                if (none != null && none.Type == JTokenType.Boolean)
                {
                    if (s.None && s.SelectedCandidateId != null)
                        errors.Add($"selection.none이 true인데 selectedCandidateId({s.SelectedCandidateId})가 있음 — 고른 것인지 '맞는 것이 없다'인지 알 수 없음");
                    else if (s.Skipped && (s.None || s.SelectedCandidateId != null))
                        errors.Add("selection.skipped가 true인데 none이 true이거나 selectedCandidateId가 있음 — 선택 단계를 건너뛴 것인지 알 수 없음(G34)");
                    else if (!s.None && !s.Skipped && s.SelectedCandidateId == null)
                        s.Warnings.Add("선택 파일 selection.none이 false인데 selectedCandidateId가 null — 고른 후보를 알 수 없음(기록에는 그대로 남김)");
                }
            }

            // colorChanged(G31): 0.2에서 필수, 0.1은 없으면 null
            var cc = o["colorChanged"];
            if (cc != null && cc.Type == JTokenType.Boolean) s.ColorChanged = (bool)cc;
            else if (cc != null && cc.Type != JTokenType.Null) errors.Add("colorChanged는 true | false여야 함");
            else if (v02 || v03) errors.Add($"colorChanged가 없음({s.FormatVersion}에서 필수, true | false — G31)");

            // sources: 슬롯 이름과 출처 값만 검사하고(G27) 값은 해석하지 않고 옮긴다. 없거나 null이면 null.
            var src = o["sources"];
            if (src == null || src.Type == JTokenType.Null) s.Sources = null;
            else if (!(src is JObject srcObj)) errors.Add("sources는 객체여야 함(슬롯 → 출처 값), 지금 " + src.Type);
            else
            {
                int before = errors.Count;
                // 0.1은 네 값, 0.2는 여섯 값, 0.3·모르는 버전은 generated_chosen까지
                var allowed = v01 ? SourceValues01 : v02 ? SourceValues : SourceValues03;
                foreach (var p in srcObj.Properties())
                {
                    if (Array.IndexOf(SlotNames, p.Name) < 0)
                        errors.Add($"sources: 모르는 슬롯 {p.Name}(가능: {string.Join(", ", SlotNames)})");
                    string v = p.Value.Type == JTokenType.String ? (string)p.Value : null;
                    if (v == null || Array.IndexOf(allowed, v) < 0)
                        errors.Add($"sources.{p.Name}: 출처 값 {p.Value.ToString(Formatting.None)}이 {string.Join(" | ", allowed)} 중 하나가 아님" +
                                   (v01 ? $"({FormatVersion01})" : ""));
                }
                if (srcObj.ContainsKey("form.baseVariant") && !srcObj.ContainsKey("form.base"))
                    errors.Add("sources: form.baseVariant가 있는데 form.base가 없음 — 어느 기본 형상의 변형값인지 알 수 없음(CP10 G39)");
                if (errors.Count == before) s.Sources = srcObj.DeepClone();
            }

            // form.asset(G62, 0.3): 고른 생성 형태 메시. 0.1·0.2 파일에 있으면 거부(그 판에는 없는 필드). 출처와 맞아야 한다:
            // form.type이 generated_chosen이면 form.asset이 있어야 하고, form.asset이 있으면 form.type은 generated_chosen이다.
            var fa = (o["form"] as JObject)?["asset"];
            if (fa != null && fa.Type != JTokenType.Null)
            {
                if (v01 || v02) errors.Add($"form.asset은 {FormatVersion03}부터 있는 필드인데 {s.FormatVersion} 파일에 있음(G62)");
                else
                {
                    var r = FormAssetRef.Parse(fa, out var fe);
                    if (r == null) errors.Add(fe);
                    else s.FormAsset = r;
                }
            }
            else if (o["form"] != null && o["form"].Type != JTokenType.Object && o["form"].Type != JTokenType.Null)
                errors.Add("form은 객체여야 함(G62)");
            string formSource = (s.Sources as JObject)?["form.type"]?.Type == JTokenType.String ? (string)s.Sources["form.type"] : null;
            if (s.Sources != null)
            {
                if (formSource == GeneratedChosen && s.FormAsset == null && errors.Count == 0)
                    errors.Add("sources.form.type이 generated_chosen인데 form.asset이 없음 — 어느 생성 메시를 골랐는지 알 수 없음(G62)");
                else if (s.FormAsset != null && formSource != GeneratedChosen)
                    errors.Add($"form.asset이 있는데 sources.form.type이 {formSource ?? "없음"} — 생성 메시를 쓸지 알 수 없음(G62)");
            }
            var dfs = o["defaultFormSource"];
            if (dfs != null && dfs.Type == JTokenType.String) s.DefaultFormSource = (string)dfs;
            else if (dfs != null && dfs.Type != JTokenType.Null) errors.Add("defaultFormSource는 문자열(G62)");

            // safetyFlags(G50 (4), 있으면): 형식만 검사하고 값은 해석하지 않고 옮긴다. 시작은 막지 않는다
            var sf = o["safetyFlags"];
            if (sf != null && sf.Type != JTokenType.Null)
            {
                if (!(sf is JArray sfArr)) errors.Add("safetyFlags는 배열이어야 함(G50), 지금 " + sf.Type);
                else if (sfArr.Any(x => !(x is JObject))) errors.Add("safetyFlags의 항목은 객체여야 함(G50)");
                else s.SafetyFlags = (JArray)sfArr.DeepClone();
            }

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

        /// <summary>manifest의 selection 객체. safetyFlags는 선택 파일에 키가 있을 때만(G50 — 이전 기록의 manifest 바이트 그대로).</summary>
        public JObject ManifestJson()
        {
            var o = new JObject
            {
                ["file"] = Str(FileName),
                ["sha256"] = Str(Sha256),
                ["formatVersion"] = Str(FormatVersion),
                ["none"] = None,
                ["selectedCandidateId"] = Str(SelectedCandidateId),
                ["finalOverrides"] = FinalOverridesJson?.DeepClone() ?? new JObject(),
                ["sources"] = Sources?.DeepClone(),
                ["skipped"] = Skipped,
                ["colorChanged"] = ColorChanged.HasValue ? new JValue(ColorChanged.Value) : JValue.CreateNull(),
            };
            if (SafetyFlags != null) o["safetyFlags"] = SafetyFlags.DeepClone();
            // G62: 0.3 파일에서 값이 있을 때만(이전 기록의 manifest 바이트 그대로). 적용 결과는 manifest 맨 위 formAsset
            if (DefaultFormSource != null) o["defaultFormSource"] = DefaultFormSource;
            if (AcceptedDefault.HasValue) o["acceptedDefault"] = AcceptedDefault.Value;
            if (FormAsset != null) o["formAssetId"] = FormAsset.AssetId;
            return o;
        }
    }
}
