// SceneSpec v2 데이터 클래스 — shared/schemas/scene-spec.v2.json(2.0.0)·scene-spec.v2.1.json(2.1.0)과 1:1.
// UnityEngine에 의존하지 않는다(유닛 테스트·dotnet 컴파일 검사에서 그대로 쓴다). 파싱은 Newtonsoft JSON.
// null = 참여자가 말하지 않은 값. 기본값을 채우는 일은 SceneParams가 하고, 무엇을 채웠는지 기록한다.
// 2.1.0(개선 매핑 v1)은 보존 필드(_context … _clauses)와 meta.mapping을 더한다. 2.0.0 문서에는 없으므로
// 선택 필드로 두고, 없으면 다시 쓸 때도 쓰지 않는다(NullValueHandling.Ignore) — 2.0.0 왕복이 그대로 유지된다.
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    public sealed class SceneSpecV2
    {
        /// <summary>v2.0 형식(규칙 기반 매핑 v0).</summary>
        public const string SupportedSpecVersion = "2.0.0";
        /// <summary>v2.1 형식(개선 매핑 v1, v2.0 상위 호환).</summary>
        public const string SpecVersionV21 = "2.1.0";
        /// <summary>v2.2 형식(매핑 v2 builder 2.2.0, 기본 형상 form.base·form.baseVariant — 결정 G21·G30).</summary>
        public const string SpecVersionV22 = "2.2.0";
        public static readonly string[] SupportedSpecVersions = { SupportedSpecVersion, SpecVersionV21, SpecVersionV22 };

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

        // ── v2.1 보존 필드(개선 매핑 v1). 렌더링에는 쓰지 않고 기록·연구자 확인용 ──
        /// <summary>범위 규칙으로 값에서 뺀 말(회상 문장·배경 사물·자리 표지 사물의 속성어).</summary>
        [JsonProperty("_context", NullValueHandling = NullValueHandling.Ignore)] public List<ContextItem> Context;
        /// <summary>부분(테두리·안쪽 …)의 속성. 전체 값으로 쓰지 않은 것.</summary>
        [JsonProperty("_parts", NullValueHandling = NullValueHandling.Ignore)] public List<PartItem> Parts;
        /// <summary>참여자가 모른다고 말한 절. Paths의 슬롯은 null로 둔다.</summary>
        [JsonProperty("_uncertain", NullValueHandling = NullValueHandling.Ignore)] public List<UncertainItem> Uncertain;
        /// <summary>수치·비교로 읽은 물리 크기(m).</summary>
        [JsonProperty("_measurements", NullValueHandling = NullValueHandling.Ignore)] public List<MeasurementItem> Measurements;
        /// <summary>왼쪽·오른쪽 방향어(슬롯 없음, 보존만).</summary>
        [JsonProperty("_direction", NullValueHandling = NullValueHandling.Ignore)] public List<DirectionItem> Direction;
        /// <summary>퍼지 매칭으로 만든 값 — 확인 필요.</summary>
        [JsonProperty("_needsConfirmation", NullValueHandling = NullValueHandling.Ignore)] public List<NeedsConfirmationItem> NeedsConfirmation;
        /// <summary>확정 텍스트 전체의 절 단위 원문 색인(무손실).</summary>
        [JsonProperty("_clauses", NullValueHandling = NullValueHandling.Ignore)] public List<ClauseItem> Clauses;

        /// <summary>2.1 전용 필드가 하나라도 있는가(2.0.0 문서에는 없어야 한다).</summary>
        [JsonIgnore]
        public bool HasV21Fields => Context != null || Parts != null || Uncertain != null || Measurements != null
                                    || Direction != null || NeedsConfirmation != null || Clauses != null
                                    || (Meta != null && Meta.Mapping != null);
    }

    public sealed class MappingInfo
    {
        [JsonProperty("requested", Required = Required.Always)] public string Requested;
        /// <summary>v0 | v1. v1이 실패해 v0로 대체했으면 v0이고 FallbackReason이 있다.</summary>
        [JsonProperty("used", Required = Required.Always)] public string Used;
        [JsonProperty("fallbackReason", Required = Required.AllowNull)] public string FallbackReason;
    }

    public sealed class ContextItem
    {
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("reason", Required = Required.Always)] public string Reason;
        [JsonProperty("path", Required = Required.AllowNull)] public string Path;
        [JsonProperty("value", Required = Required.AllowNull)] public JToken Value;
        [JsonProperty("rule", Required = Required.Always)] public string Rule;
    }

    public sealed class PartItem
    {
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("part", Required = Required.AllowNull)] public string Part;
        [JsonProperty("partClass", Required = Required.AllowNull)] public string PartClass;
        [JsonProperty("path", Required = Required.Always)] public string Path;
        [JsonProperty("value", Required = Required.AllowNull)] public JToken Value;
        [JsonProperty("rule", Required = Required.Always)] public string Rule;
    }

    public sealed class UncertainItem
    {
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("paths", Required = Required.Always)] public List<string> Paths;
        [JsonProperty("marker", Required = Required.Always)] public string Marker;
    }

    public sealed class MeasurementItem
    {
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        /// <summary>number_unit | reference | cover</summary>
        [JsonProperty("kind", Required = Required.Always)] public string Kind;
        [JsonProperty("meters", Required = Required.Always)] public double Meters;
        /// <summary>size | distance | width | unknown</summary>
        [JsonProperty("dimension", Required = Required.Always)] public string Dimension;
        [JsonProperty("reference", Required = Required.AllowNull)] public string Reference;
        [JsonProperty("usedFor", Required = Required.AllowNull)] public string UsedFor;
    }

    public sealed class DirectionItem
    {
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("horizontal", Required = Required.AllowNull)] public string Horizontal;
        [JsonProperty("vertical", Required = Required.AllowNull)] public string Vertical;
        [JsonProperty("depth", Required = Required.AllowNull)] public string Depth;
    }

    public sealed class NeedsConfirmationItem
    {
        [JsonProperty("path", Required = Required.Always)] public string Path;
        [JsonProperty("trigger", Required = Required.Always)] public string Trigger;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("reason", Required = Required.Always)] public string Reason;
        [JsonProperty("matched", Required = Required.Always)] public string Matched;
    }

    public sealed class ClauseItem
    {
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("text", Required = Required.Always)] public string Text;
        [JsonProperty("usedFor", Required = Required.Always)] public List<string> UsedFor;
        /// <summary>used | partly_used | unused | context</summary>
        [JsonProperty("status", Required = Required.Always)] public string Status;
    }

    public sealed class SpecMeta
    {
        [JsonProperty("specVersion", Required = Required.Always)] public string SpecVersion;
        [JsonProperty("participantId", Required = Required.AllowNull)] public string ParticipantId;
        [JsonProperty("sessionId", Required = Required.AllowNull)] public string SessionId;
        [JsonProperty("condition", Required = Required.AllowNull)] public string Condition;
        [JsonProperty("sourceTextHash", Required = Required.Always)] public string SourceTextHash;
        [JsonProperty("pipeline", Required = Required.Always)] public PipelineInfo Pipeline;
        /// <summary>(2.1) 어느 매핑이 만들었나, v0 대체 여부.</summary>
        [JsonProperty("mapping", NullValueHandling = NullValueHandling.Ignore)] public MappingInfo Mapping;
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
        /// <summary>(2.2) 기본 형상: container | line | sheet | flame | drop | null. 2.0·2.1 문서에는 키가 없다.</summary>
        [JsonProperty("base")] public string Base;
        /// <summary>(2.2) 낱말 뜻이 정한 변형값(정한 키만). 정하지 않았으면 null. 모르는 키는 파싱 오류(엄격).</summary>
        [JsonProperty("baseVariant")] public BaseVariantSpec BaseVariant;

        /// <summary>원문 form 객체에 base·baseVariant 키가 있었는가(SceneSpecJson.Parse가 채운다). 2.2.0 문서는 둘 다 있어야 하고
        /// 2.0·2.1 문서에는 없어야 한다. 다시 쓸 때도 키가 있던 문서만 두 키를 쓴다(2.0·2.1 왕복이 그대로).</summary>
        [JsonIgnore] public bool BaseKeysPresent;

        public bool ShouldSerializeBase() => BaseKeysPresent || Base != null;
        public bool ShouldSerializeBaseVariant() => BaseKeysPresent || BaseVariant != null;
    }

    /// <summary>(2.2) 기본 형상 변형값. 키마다 null = 정하지 않음(렌더러가 형상 프리셋 기본값). 쓰는 키는 기본 형상마다 다르다
    /// (container: opening·profile, line: form·gauge, sheet: drape — shared/schemas/scene-spec.v2.2.json $defs.baseVariant).</summary>
    public sealed class BaseVariantSpec
    {
        [JsonProperty("opening", NullValueHandling = NullValueHandling.Ignore)] public string Opening;
        [JsonProperty("profile", NullValueHandling = NullValueHandling.Ignore)] public string Profile;
        [JsonProperty("form", NullValueHandling = NullValueHandling.Ignore)] public string Form;
        [JsonProperty("gauge", NullValueHandling = NullValueHandling.Ignore)] public string Gauge;
        [JsonProperty("drape", NullValueHandling = NullValueHandling.Ignore)] public string Drape;

        public BaseVariantSpec Clone() => new BaseVariantSpec { Opening = Opening, Profile = Profile, Form = Form, Gauge = Gauge, Drape = Drape };

        /// <summary>키 → 값(값이 있는 키만, 고정 순서).</summary>
        public IEnumerable<KeyValuePair<string, string>> Pairs()
        {
            if (Opening != null) yield return new KeyValuePair<string, string>("opening", Opening);
            if (Profile != null) yield return new KeyValuePair<string, string>("profile", Profile);
            if (Form != null) yield return new KeyValuePair<string, string>("form", Form);
            if (Gauge != null) yield return new KeyValuePair<string, string>("gauge", Gauge);
            if (Drape != null) yield return new KeyValuePair<string, string>("drape", Drape);
        }
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
        /// <summary>explicit_lexicon(1층) | simile_marker(2층) | vad_lexicon(3층)
        /// | (2.1) phrase_rule(구 규칙) | fuzzy_lexicon(퍼지, 확인 필요) | body_part_height(_inferred 제안)</summary>
        [JsonProperty("source", Required = Required.Always)] public string Source;
        [JsonProperty("trigger", Required = Required.Always)] public string Trigger;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("rule", Required = Required.Always)] public string Rule;
        /// <summary>(2.1) 퍼지 매칭 값이면 true. 없으면 쓰지 않는다.</summary>
        [JsonProperty("needsConfirmation", NullValueHandling = NullValueHandling.Ignore)] public bool? NeedsConfirmation;
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
