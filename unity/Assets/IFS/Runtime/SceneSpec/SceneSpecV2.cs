// SceneSpec v2 데이터 클래스 — shared/schemas/scene-spec.v2.json과 1:1.
// UnityEngine에 의존하지 않는다(유닛 테스트·dotnet 컴파일 검사에서 그대로 쓴다). 파싱은 Newtonsoft JSON.
// null = 참여자가 말하지 않은 값. 기본값을 채우는 일은 SceneParams가 하고, 무엇을 채웠는지 기록한다.
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    public sealed class SceneSpecV2
    {
        public const string SupportedSpecVersion = "2.0.0";

        [JsonProperty("meta", Required = Required.Always)] public SpecMeta Meta;
        [JsonProperty("form", Required = Required.Always)] public FormSpec Form;
        [JsonProperty("material", Required = Required.Always)] public MaterialSpec Material;
        [JsonProperty("layout", Required = Required.Always)] public LayoutSpec Layout;
        [JsonProperty("motion", Required = Required.Always)] public MotionSpec Motion;
        [JsonProperty("body", Required = Required.Always)] public BodySpec Body;

        /// <summary>슬롯 경로("material.color") → 그 값을 만든 근거. 값이 있는 슬롯에만 있다.</summary>
        [JsonProperty("_provenance", Required = Required.Always)] public Dictionary<string, List<Provenance>> Provenance;
        /// <summary>1층 사전에 없는 내용어(소실 정보).</summary>
        [JsonProperty("_unmatched", Required = Required.Always)] public List<UnmatchedToken> Unmatched;
        /// <summary>사전에는 있지만 v2 파라미터가 없는 말.</summary>
        [JsonProperty("_unmapped", Required = Required.Always)] public List<UnmappedHit> Unmapped;
        [JsonProperty("_negated", Required = Required.Always)] public List<NegatedHit> Negated;
        [JsonProperty("_alternatives", Required = Required.Always)] public List<AlternativeValue> Alternatives;
        /// <summary>3층 V/A/D 제안. 값 자리가 아니다. SceneLoader는 기본으로 쓰지 않는다.</summary>
        [JsonProperty("_inferred", Required = Required.Always)] public Dictionary<string, InferredValue> Inferred;
    }

    public sealed class SpecMeta
    {
        [JsonProperty("specVersion", Required = Required.Always)] public string SpecVersion;
        [JsonProperty("participantId", Required = Required.AllowNull)] public string ParticipantId;
        [JsonProperty("sessionId", Required = Required.AllowNull)] public string SessionId;
        [JsonProperty("condition", Required = Required.AllowNull)] public string Condition;
        [JsonProperty("sourceTextHash", Required = Required.Always)] public string SourceTextHash;
        [JsonProperty("pipeline", Required = Required.Always)] public PipelineInfo Pipeline;
    }

    public sealed class PipelineInfo
    {
        [JsonProperty("builder", Required = Required.Always)] public string Builder;
        [JsonProperty("analyzer", Required = Required.Always)] public string Analyzer;
        [JsonProperty("lexicons", Required = Required.Always)] public Dictionary<string, string> Lexicons;
    }

    public sealed class FormSpec
    {
        /// <summary>blob | mist | shell | fragments | null</summary>
        [JsonProperty("type", Required = Required.AllowNull)] public string Type;
        [JsonProperty("posture", Required = Required.AllowNull)] public string Posture;
    }

    public sealed class MaterialSpec
    {
        [JsonProperty("color", Required = Required.AllowNull)] public HslColor Color;
        [JsonProperty("brightness", Required = Required.AllowNull)] public double? Brightness;
        [JsonProperty("saturation", Required = Required.AllowNull)] public double? Saturation;
        [JsonProperty("roughness", Required = Required.AllowNull)] public double? Roughness;
        [JsonProperty("opacity", Required = Required.AllowNull)] public double? Opacity;
        [JsonProperty("erosion", Required = Required.AllowNull)] public double? Erosion;
    }

    public sealed class HslColor
    {
        [JsonProperty("h", Required = Required.Always)] public double H;
        [JsonProperty("s", Required = Required.Always)] public double S;
        [JsonProperty("l", Required = Required.Always)] public double L;
    }

    public sealed class LayoutSpec
    {
        [JsonProperty("size", Required = Required.AllowNull)] public double? Size;
        [JsonProperty("distance", Required = Required.AllowNull)] public double? Distance;
        [JsonProperty("verticalOffset", Required = Required.AllowNull)] public double? VerticalOffset;
    }

    public sealed class MotionSpec
    {
        [JsonProperty("type", Required = Required.AllowNull)] public string Type;
        [JsonProperty("speed", Required = Required.AllowNull)] public double? Speed;
    }

    public sealed class BodySpec
    {
        [JsonProperty("part", Required = Required.AllowNull)] public string Part;
        [JsonProperty("layer", Required = Required.AllowNull)] public string Layer;
    }

    public sealed class Provenance
    {
        /// <summary>explicit_lexicon(1층) | simile_marker(2층) | vad_lexicon(3층)</summary>
        [JsonProperty("source", Required = Required.Always)] public string Source;
        [JsonProperty("trigger", Required = Required.Always)] public string Trigger;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("rule", Required = Required.Always)] public string Rule;
    }

    public sealed class UnmatchedToken
    {
        [JsonProperty("lemma", Required = Required.Always)] public string Lemma;
        [JsonProperty("tag", Required = Required.Always)] public string Tag;
        [JsonProperty("surface", Required = Required.Always)] public string Surface;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
    }

    public sealed class UnmappedHit
    {
        [JsonProperty("lemma", Required = Required.Always)] public string Lemma;
        [JsonProperty("category", Required = Required.Always)] public string Category;
        [JsonProperty("value", Required = Required.Always)] public JObject Value;
        [JsonProperty("reason", Required = Required.Always)] public string Reason;
        [JsonProperty("_provenance", Required = Required.Always)] public Provenance Provenance;
    }

    public sealed class NegatedHit
    {
        [JsonProperty("lemma", Required = Required.Always)] public string Lemma;
        [JsonProperty("category", Required = Required.Always)] public string Category;
        [JsonProperty("_provenance", Required = Required.Always)] public Provenance Provenance;
    }

    public sealed class AlternativeValue
    {
        [JsonProperty("path", Required = Required.Always)] public string Path;
        /// <summary>슬롯에 따라 수(0–1)·문자열·HSL 객체.</summary>
        [JsonProperty("value", Required = Required.Always)] public JToken Value;
        [JsonProperty("reason", Required = Required.Always)] public string Reason;
        [JsonProperty("_provenance", Required = Required.Always)] public List<Provenance> Provenance;
    }

    public sealed class InferredValue
    {
        [JsonProperty("value", Required = Required.Always)] public double Value;
        [JsonProperty("_provenance", Required = Required.Always)] public List<Provenance> Provenance;
    }
}
