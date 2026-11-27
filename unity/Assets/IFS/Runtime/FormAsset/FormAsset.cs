// G62: 선택 파일(ifs-selection/0.3)의 form.asset — 참여자가 고른 생성 형태 메시 — 을 읽고, 장면에 놓을 크기를 정하고,
// 적용 결과(또는 절차 메시로 돌아간 이유)를 배치 기록 manifest에 남긴다. UnityEngine에 의존하지 않는다.
//
// 크기는 모델이 정하지 않는다: GLB는 가장 긴 변 1.0·피벗 bottom-center로 정규화되어 오지만, 그 값을 믿지 않고 읽은 정점의
// 경계 상자로 다시 잰다. 같은 layout.size에서 그려질 절차 메시의 가장 긴 변(자세·축 비율 배율까지 곱한 값)과 같아지도록 균일 배율을
// 준다(오차 ±1% 이내 — RelativeError로 기록). 위치는 경계 상자 중심을 절차 메시의 경계 상자 중심에 맞춘다(거리 기록이 물체 중심
// 기준이라 피벗 차이로 물체가 떠 보이거나 거리가 달라지지 않게). 회전은 하지 않는다.
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.FormAsset
{
    /// <summary>선택 파일 form.asset(0.3) 원문에서 러너가 쓰는 값.</summary>
    public sealed class FormAssetRef
    {
        public string AssetId, CandidateId, Glb, GlbSha256, Pipeline, PromptText;
        public long? Seed;
        public JToken Models, Covariates;

        /// <summary>form.asset 객체 → 참조. 형식이 틀리면 null과 이유. glb는 null이어도 받는다(러너가 절차 메시로 돌아가고 기록).</summary>
        public static FormAssetRef Parse(JToken tok, out string error)
        {
            error = null;
            if (!(tok is JObject o)) { error = "form.asset은 객체 또는 null이어야 함"; return null; }
            string Str(string k) => o[k]?.Type == JTokenType.String ? (string)o[k] : null;
            var r = new FormAssetRef
            {
                AssetId = Str("assetId"), CandidateId = Str("candidateId"), Glb = Str("glb"),
                GlbSha256 = Str("glbSha256")?.Trim().ToLowerInvariant(), Pipeline = Str("pipeline"), PromptText = Str("promptText"),
                Seed = o["seed"]?.Type == JTokenType.Integer ? (long?)(long)o["seed"] : null,
                Models = o["models"]?.DeepClone(), Covariates = o["covariates"]?.DeepClone(),
            };
            if (string.IsNullOrWhiteSpace(r.AssetId)) error = "form.asset.assetId가 없음";
            else if (r.GlbSha256 == null || r.GlbSha256.Length != 64 || r.GlbSha256.Any(c => !Uri.IsHexDigit(c))) error = "form.asset.glbSha256은 16진 64자";
            else if (o["glb"] != null && o["glb"].Type != JTokenType.Null && o["glb"].Type != JTokenType.String) error = "form.asset.glb는 문자열 또는 null";
            else if (r.Glb != null && (Path.IsPathRooted(r.Glb) || r.Glb.Split('/', '\\').Contains(".."))) error = "form.asset.glb는 선택 파일 기준 상대 파일 이름이어야 함";
            return error == null ? r : null;
        }

        /// <summary>선택 파일 폴더 기준 GLB 경로(glb가 null이면 null).</summary>
        public string ResolveGlbPath(string selectionFilePath)
        {
            if (Glb == null) return null;
            string dir = Path.GetDirectoryName(Path.GetFullPath(selectionFilePath)) ?? "";
            return Path.Combine(dir, Glb);
        }
    }

    /// <summary>미리보기(WebGL 다리·데스크톱 요청 폴더)가 받는 생성 형태 요청: {assetId, glbSha256, glbBase64 | glb(파일 경로)}.
    /// sha256을 다시 확인하고 GlbMeshReader로 읽는다. 실패하면 null과 이유(미리보기는 그 후보를 그리지 않고 알린다).</summary>
    public static class FormAssetPayload
    {
        public static GlbMesh Decode(JObject o, Func<string, byte[]> readFile, out FormAssetRef asset, out string error)
        {
            asset = null;
            error = null;
            if (o == null) { error = "생성 형태 요청이 객체가 아님"; return null; }
            string id = o["assetId"]?.Type == JTokenType.String ? (string)o["assetId"] : null;
            string sha = o["glbSha256"]?.Type == JTokenType.String ? ((string)o["glbSha256"]).Trim().ToLowerInvariant() : null;
            if (string.IsNullOrWhiteSpace(id)) { error = "assetId가 없음"; return null; }
            if (sha == null || sha.Length != 64 || sha.Any(c => !Uri.IsHexDigit(c))) { error = "glbSha256은 16진 64자"; return null; }
            byte[] bytes;
            try
            {
                if (o["glbBase64"]?.Type == JTokenType.String) bytes = Convert.FromBase64String((string)o["glbBase64"]);
                else if (o["glb"]?.Type == JTokenType.String && readFile != null) bytes = readFile((string)o["glb"]);
                else { error = "glbBase64 또는 glb(경로)가 필요함"; return null; }
            }
            catch (Exception e) when (e is FormatException || e is IOException || e is UnauthorizedAccessException)
            {
                error = FormAssetResult.GlbMissing + ": " + e.Message;
                return null;
            }
            string got = Ownership.OwnershipManifest.Sha256Hex(bytes);
            if (got != sha) { error = FormAssetResult.GlbSha + $"({got.Substring(0, 12)}…)"; return null; }
            var mesh = GlbMeshReader.Read(bytes, out string perr);
            if (mesh == null) { error = FormAssetResult.GlbParse + ": " + perr; return null; }
            asset = new FormAssetRef { AssetId = id, GlbSha256 = sha };
            return mesh;
        }
    }

    /// <summary>GLB를 절차 메시 자리에 놓는 크기·위치 계산(순수 수학).</summary>
    public sealed class FormAssetFit
    {
        /// <summary>절차 모형의 경계(모형 국소 좌표, 모형 배율을 곱하기 전).</summary>
        public double[] ProceduralCenter, ProceduralSize;
        /// <summary>읽은 GLB 정점의 경계(Unity 좌표).</summary>
        public double[] AssetCenter, AssetSize;
        public double AssetLongest => Math.Max(AssetSize[0], Math.Max(AssetSize[1], AssetSize[2]));

        public FormAssetFit(double[] proceduralCenter, double[] proceduralSize, double[] assetCenter, double[] assetSize)
        {
            ProceduralCenter = proceduralCenter; ProceduralSize = proceduralSize; AssetCenter = assetCenter; AssetSize = assetSize;
        }

        /// <summary>절차 모형에 줄 국소 배율(기본 크기 × layout.size × 자세 × 축 비율)을 받아 생성 메시의 균일 배율과 국소 위치를 정한다.
        /// proceduralLongest = 그 배율에서 절차 모형의 가장 긴 변, renderedLongest = 생성 메시의 가장 긴 변(같아야 함).</summary>
        public void Place(double[] proceduralLocalScale, out double uniform, out double[] localPosition,
                          out double proceduralLongest, out double renderedLongest)
        {
            proceduralLongest = 0;
            for (int k = 0; k < 3; k++) proceduralLongest = Math.Max(proceduralLongest, ProceduralSize[k] * Math.Abs(proceduralLocalScale[k]));
            uniform = AssetLongest > 1e-12 ? proceduralLongest / AssetLongest : 0;
            localPosition = new double[3];
            for (int k = 0; k < 3; k++) localPosition[k] = ProceduralCenter[k] * proceduralLocalScale[k] - AssetCenter[k] * uniform;
            renderedLongest = AssetLongest * uniform;
        }

        public static double RelativeError(double rendered, double procedural) =>
            procedural > 1e-12 ? Math.Abs(rendered - procedural) / procedural : double.NaN;

        /// <summary>허용 오차(±1%, D8 통과 기준).</summary>
        public const double Tolerance = 0.01;
    }

    /// <summary>러너가 생성 메시를 적용한 결과. manifest formAsset(선택 파일에 form.asset이 있을 때만).</summary>
    public sealed class FormAssetResult
    {
        public const string StatusApplied = "applied";
        public const string StatusFallback = "fallback_procedural";
        // 절차 메시로 돌아간 이유
        public const string GlbNull = "glb_not_recorded", GlbMissing = "glb_missing", GlbSha = "glb_sha256_mismatch",
                            GlbParse = "glb_parse_failed", NotLoaded = "object_not_loaded", MistForm = "mist_form",
                            NoProcedural = "no_procedural_mesh", SizeMismatch = "size_out_of_tolerance";

        public FormAssetRef Ref;
        public string Status = StatusFallback;
        public string FallbackReason, Detail;
        public string GlbSha256Actual;
        public int Vertices, Triangles;
        public double? LayoutSize, ProceduralLongestEdgeM, RenderedLongestEdgeM, UniformScale, AssetLongestEdge;
        public double[] RenderedSizeM;
        /// <summary>절차 메시였다면 쓰였을 렌더 경로(renderPath)와 실제 경로.</summary>
        public string ProceduralRenderPath, RenderPath;

        public bool Applied => Status == StatusApplied;

        public static FormAssetResult Fallback(FormAssetRef r, string reason, string detail = null) =>
            new FormAssetResult { Ref = r, Status = StatusFallback, FallbackReason = reason, Detail = detail };

        static JToken Num(double? v, int digits = 6) => v.HasValue && !double.IsNaN(v.Value) ? new JValue(Math.Round(v.Value, digits)) : JValue.CreateNull();
        static JToken Str(string s) => s != null ? new JValue(s) : JValue.CreateNull();

        public JObject ManifestJson()
        {
            double? rel = RenderedLongestEdgeM.HasValue && ProceduralLongestEdgeM.HasValue
                ? FormAssetFit.RelativeError(RenderedLongestEdgeM.Value, ProceduralLongestEdgeM.Value) : (double?)null;
            return new JObject
            {
                ["assetId"] = Str(Ref?.AssetId),
                ["candidateId"] = Str(Ref?.CandidateId),
                ["glb"] = Str(Ref?.Glb != null ? Path.GetFileName(Ref.Glb) : null),
                ["glbSha256"] = Str(Ref?.GlbSha256),
                ["glbSha256Actual"] = Str(GlbSha256Actual),
                ["pipeline"] = Str(Ref?.Pipeline),
                ["seed"] = Ref?.Seed.HasValue == true ? new JValue(Ref.Seed.Value) : JValue.CreateNull(),
                ["models"] = Ref?.Models?.DeepClone() ?? JValue.CreateNull(),
                ["promptText"] = Str(Ref?.PromptText),
                ["status"] = Status,
                ["fallbackReason"] = Str(FallbackReason),
                ["detail"] = Str(Detail),
                ["renderPath"] = Str(RenderPath),
                ["proceduralRenderPath"] = Str(ProceduralRenderPath),
                ["vertices"] = Vertices, ["triangles"] = Triangles,
                ["layoutSize"] = Num(LayoutSize),
                ["proceduralLongestEdgeM"] = Num(ProceduralLongestEdgeM),
                ["renderedLongestEdgeM"] = Num(RenderedLongestEdgeM),
                ["renderedSizeM"] = RenderedSizeM != null ? new JArray(RenderedSizeM.Select(v => (object)Math.Round(v, 6)).ToArray()) : (JToken)JValue.CreateNull(),
                ["longestEdgeRelError"] = Num(rel, 8),
                ["uniformScale"] = Num(UniformScale),
                ["assetLongestEdge"] = Num(AssetLongestEdge),
                ["sizeRule"] = "longest edge = procedural mesh longest edge at same layout.size (±1%); center = procedural bbox center; no rotation",
                ["materialRule"] = "spec material (lexicon mapping + participant adjustments); GLB materials discarded",
                ["covariates"] = Ref?.Covariates?.DeepClone() ?? JValue.CreateNull(),
            };
        }

        /// <summary>events.csv 한 줄 상세(key=value;…).</summary>
        public string EventDetail()
        {
            var inv = CultureInfo.InvariantCulture;
            string C(string s) => string.IsNullOrWhiteSpace(s) ? "-" : s.Replace(';', ' ').Replace('=', ' ').Replace('\n', ' ').Replace('\r', ' ').Trim();
            return $"asset={C(Ref?.AssetId)};status={Status};reason={C(FallbackReason)};" +
                   $"longestM={(RenderedLongestEdgeM.HasValue ? RenderedLongestEdgeM.Value.ToString("0.####", inv) : "-")}";
        }
    }
}
