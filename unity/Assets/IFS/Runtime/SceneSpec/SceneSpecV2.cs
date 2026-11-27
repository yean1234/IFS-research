// SceneSpec v2 데이터 클래스 — shared/schemas/scene-spec.v2.json(2.0.0)·scene-spec.v2.1.json(2.1.0)·scene-spec.v2.2.json(2.2.0)·
// scene-spec.v2.3.json(2.3.0)·scene-spec.v2.4.json(2.4.0)과 1:1.
// 2.2.0(매핑 v2 builder 2.2.0, D6)은 form.base·form.baseVariant(기본 형상)를 더한다. 2.0·2.1 문서에는 키가 없다.
// 2.3.0(G61 ①)은 form.roundness·form.aspect·material.emission(서수 단계 이름, null 허용)과 선택 필드 _provenance[].variant를 더한다.
// 2.0–2.2 문서에는 세 키가 없다. 원문에 키가 있었는지는 SceneSpecJson.Parse가 따로 본다(왕복 직렬화·golden 지문이 그대로이도록).
// 2.4.0(G72)은 layout.proportions(x·y·z 비율, null 허용 — ProportionsRender)를 더한다. 2.4.0 문서에는 키가 반드시 있고 2.0–2.3 문서에는 없다.
// 2.4.0에서 2.3 확장 슬롯(form.roundness·form.aspect·material.emission)은 선택이다(매퍼 확장 사전을 켰을 때만 셋 다 있음).
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
        /// <summary>v2.3 형식(G61 ①: form.roundness·form.aspect·material.emission, 선택 provenance.variant — docs/scene-spec-mapping.md 8절).</summary>
        public const string SpecVersionV23 = "2.3.0";
        /// <summary>v2.4 형식(G72: layout.proportions x·y·z 비율. 2.2·2.3 상위 호환, 2.3 확장 슬롯은 선택).</summary>
        public const string SpecVersionV24 = "2.4.0";
        public static readonly string[] SupportedSpecVersions = { SupportedSpecVersion, SpecVersionV21, SpecVersionV22, SpecVersionV23, SpecVersionV24 };

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

        /// <summary>(2.3) 둥긂·각짐 정도(서수): angular | slightly_angular | neutral | slightly_rounded | rounded | null.
        /// 표에 없는 값은 SceneSpecJson.Parse가 파싱 오류로 낸다. 2.0–2.2 문서에는 키가 없다.</summary>
        [JsonProperty("roundness")] public string Roundness;
        /// <summary>(2.3) 길쭉함·납작함(서수): elongated | slightly_elongated | neutral | slightly_flattened | flattened | null.</summary>
        [JsonProperty("aspect")] public string Aspect;

        /// <summary>원문 form 객체에 roundness·aspect 키가 있었는가(SceneSpecJson.Parse가 채운다). 2.3.0 문서는 둘 다 있어야 하고
        /// 2.0–2.2 문서에는 없어야 한다. 다시 쓸 때도 키가 있던 문서만 두 키를 쓴다(2.0–2.2 왕복이 그대로).</summary>
        [JsonIgnore] public bool ContourKeysPresent;

        public bool ShouldSerializeBase() => BaseKeysPresent || Base != null;
        public bool ShouldSerializeBaseVariant() => BaseKeysPresent || BaseVariant != null;
        public bool ShouldSerializeRoundness() => ContourKeysPresent || Roundness != null;
        public bool ShouldSerializeAspect() => ContourKeysPresent || Aspect != null;
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
        /// <summary>(2.3) 발광(서수): none | faint | glowing | null. none은 '빛이 없다'고 말한 값(null = 말하지 않음과 다르다).</summary>
        [JsonProperty("emission")] public string Emission;

        /// <summary>원문 material 객체에 emission 키가 있었는가(SceneSpecJson.Parse가 채운다). 2.3.0 문서에만 있다.</summary>
        [JsonIgnore] public bool EmissionKeyPresent;

        public bool ShouldSerializeEmission() => EmissionKeyPresent || Emission != null;
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
        /// <summary>(2.4, G72) x·y·z 비율. null = 말하지 않음. 2.0–2.3 문서에는 키가 없다.</summary>
        [JsonProperty("proportions")] public ProportionsSpec Proportions;

        /// <summary>원문 layout 객체에 proportions 키가 있었는가(SceneSpecJson.Parse가 채운다). 2.4.0 문서는 있어야 하고 2.0–2.3 문서에는 없어야 한다.
        /// 다시 쓸 때도 키가 있던 문서만 쓴다(2.0–2.3 왕복이 그대로).</summary>
        [JsonIgnore] public bool ProportionsKeyPresent;

        public bool ShouldSerializeProportions() => ProportionsKeyPresent || Proportions != null;
    }

    /// <summary>(2.4, G72) x = 너비(물체 국소 x), y = 높이(국소 y), z = 깊이(국소 z). 각 0.2–1, 가장 큰 값 = 1(SceneSpecJson.Validate가 확인).
    /// axisSaid = false면 긴 축·짧은 축 방향을 말하지 않음(값은 기준 틀: 길쭉 → y가 긺, 납작 → y가 짧음).</summary>
    public sealed class ProportionsSpec
    {
        [JsonProperty("x", Required = Required.Always)] public double X;
        [JsonProperty("y", Required = Required.Always)] public double Y;
        [JsonProperty("z", Required = Required.Always)] public double Z;
        [JsonProperty("axisSaid", Required = Required.Always)] public bool AxisSaid;
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
        /// | (2.1) phrase_rule(구 규칙) | fuzzy_lexicon(퍼지, 확인 필요) | body_part_height(_inferred 제안)
        /// | (2.2, CP10 G38) lexicon_implied(form.baseVariant 전용: 말한 형상 낱말의 사전 뜻에서 온 변형값). 값은 검사하지 않고 그대로 읽는다</summary>
        [JsonProperty("source", Required = Required.Always)] public string Source;
        [JsonProperty("trigger", Required = Required.Always)] public string Trigger;
        [JsonProperty("charSpan", Required = Required.Always)] public int[] CharSpan;
        [JsonProperty("rule", Required = Required.Always)] public string Rule;
        /// <summary>(2.1) 퍼지 매칭 값이면 true. 없으면 쓰지 않는다.</summary>
        [JsonProperty("needsConfirmation", NullValueHandling = NullValueHandling.Ignore)] public bool? NeedsConfirmation;
        /// <summary>(2.3) 형태 변이 규칙층 근거(선택). 렌더에는 쓰지 않고 그대로 읽는다. 없으면 쓰지 않는다.</summary>
        [JsonProperty("variant", NullValueHandling = NullValueHandling.Ignore)] public VariantProvenance Variant;
    }

    /// <summary>(2.3) 형태 변이 규칙층으로 대응한 근거(shared/schemas/scene-spec.v2.3.json $defs.provenance.variant).
    /// rules = 적용 순서, surface = 원래 표면형, root = 사전에서 찾은 꼴, grade = 강도 기록(값은 바꾸지 않음).</summary>
    public sealed class VariantProvenance
    {
        [JsonProperty("rules", Required = Required.Always)] public List<string> Rules;
        [JsonProperty("surface", Required = Required.Always)] public string Surface;
        [JsonProperty("root", Required = Required.Always)] public string Root;
        [JsonProperty("grade", Required = Required.Always)] public List<string> Grade;
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
