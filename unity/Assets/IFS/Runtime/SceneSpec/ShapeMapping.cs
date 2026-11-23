// 모양어 → 모양 모형 (docs/shape-mapping.md).
// 파이썬 매핑은 모양어를 SceneSpec 슬롯에 넣지 않고 _unmapped(category = "shape", value.shape, reason = no_scene_param)에 남긴다.
// Unity가 그 목록을 읽어 아래 표의 네 값만 모형으로 바꾼다. 표에 없는 모양어는 구로 바꾸지 않고 unmapped_shape로 기록한다.
//   규칙 1. 표에 있는 모양어(mapped) 중 charSpan 순서로 처음 나온 것을 적용한다. 다른 모양이 또 나오면 conflict.
//   규칙 2. 표에 없는 모양어는 모두 unmapped_shape(경고·기록). 모형은 모양 정보 없이 만들던 것 그대로.
//   규칙 3. spec이 form.type을 mist·shell·fragments로 말했으면 그 형태 모형을 지키고 모양어는 not_applied_form.
//           (form.type이 null 또는 blob일 때만 모양 모형으로 바꾼다)
// 사전·규칙만 쓴다(LLM 없음). 같은 spec이면 언제나 같은 결과다. UnityEngine에 의존하지 않는다(dotnet 테스트 가능).
using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    /// <summary>spec 한 개에 나온 모양어 하나(_unmapped 항목 하나).</summary>
    public sealed class ShapeWord
    {
        /// <summary>사전 값(value.shape). 예: round, thread. 값이 없으면 null.</summary>
        public string Shape;
        public string Lemma;
        /// <summary>원문에서 걸린 말(_provenance.trigger).</summary>
        public string Trigger;
        public int[] CharSpan;
        /// <summary>applied | conflict | unmapped_shape | not_applied_form</summary>
        public string Status;

        public ShapeWord() { }

        public ShapeWord(string shape, string trigger, int start, int end, string lemma = null)
        {
            Shape = shape;
            Trigger = trigger;
            CharSpan = new[] { start, end };
            Lemma = lemma;
        }
    }

    /// <summary>spec 한 개의 모양어 판정 결과. initialScene.json·report.json의 "shape"로 기록한다.</summary>
    public sealed class ShapeResolution
    {
        /// <summary>applied | none | unmapped_shape | not_applied_form</summary>
        public string Status;
        /// <summary>적용한 모양 값(round·square·flat·pointed). 적용하지 않았으면 null.</summary>
        public string Applied;
        /// <summary>적용한 모형(Sphere·Cube·FlatCylinder·Cone). 적용하지 않았으면 null.</summary>
        public string Model;
        /// <summary>모형을 프리팹으로 만들었으면 true, 프리팹이 없어 코드로 만들었으면 false. 적용하지 않았으면 null.</summary>
        public bool? ViaPrefab;
        /// <summary>spec이 말한 form.type(null = 말하지 않음).</summary>
        public string FormType;
        /// <summary>charSpan 순서.</summary>
        public List<ShapeWord> Words = new List<ShapeWord>();

        public JObject ToJson()
        {
            var words = new JArray();
            foreach (var w in Words)
                words.Add(new JObject
                {
                    ["shape"] = w.Shape,
                    ["lemma"] = w.Lemma,
                    ["trigger"] = w.Trigger,
                    ["charSpan"] = w.CharSpan != null ? new JArray(w.CharSpan) : null,
                    ["status"] = w.Status,
                });
            return new JObject
            {
                ["status"] = Status,
                ["applied"] = Applied,
                ["model"] = Model,
                ["viaPrefab"] = ViaPrefab,
                ["formType"] = FormType,
                ["words"] = words,
            };
        }
    }

    public static class ShapeMapping
    {
        public const string StatusApplied = "applied";
        public const string StatusNone = "none";
        public const string StatusUnmapped = "unmapped_shape";
        public const string StatusNotAppliedForm = "not_applied_form";
        public const string StatusConflict = "conflict";
        /// <summary>(2.2) spec이 기본 형상(form.base)을 말해 기본 형상이 윤곽을 정함 — 모양 모형으로 바꾸지 않음.</summary>
        public const string StatusNotAppliedBase = "not_applied_base";
        /// <summary>맨 위 상태 전용: 소유감 실험 변형본이 모양 모형을 강제함(SceneOverride.ShapeModel). spec 판정이 아니다.</summary>
        public const string StatusForced = "forced";

        public const string ModelSphere = "Sphere";
        public const string ModelCube = "Cube";
        public const string ModelFlatCylinder = "FlatCylinder";
        public const string ModelCone = "Cone";

        /// <summary>모양 값 → 모형. 이 네 개만 모형으로 바꾼다(표를 늘리면 docs/shape-mapping.md도 고친다).</summary>
        public static readonly IReadOnlyDictionary<string, string> ModelByShape = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { "round", ModelSphere },
            { "square", ModelCube },
            { "flat", ModelFlatCylinder },
            { "pointed", ModelCone },
        };

        /// <summary>표의 모양 값(고정 순서) — 프리팹 칸·보고 순서.</summary>
        public static readonly string[] Shapes = { "round", "square", "flat", "pointed" };
        public static readonly string[] Models = { ModelSphere, ModelCube, ModelFlatCylinder, ModelCone };

        public static bool IsMapped(string shape) => shape != null && ModelByShape.ContainsKey(shape);

        public static string ModelFor(string shape) => IsMapped(shape) ? ModelByShape[shape] : null;

        /// <summary>모형 → 모양 값(Cube → square). 표에 없으면 null.</summary>
        public static string ShapeForModel(string model)
        {
            foreach (var kv in ModelByShape) if (kv.Value == model) return kv.Key;
            return null;
        }

        /// <summary>변형본용: 원래 판정의 모양어 기록은 그대로 두고 모형만 강제한 판정(Status = forced). 입력은 바꾸지 않는다.</summary>
        public static ShapeResolution Forced(ShapeResolution original, string model)
        {
            if (Array.IndexOf(Models, model) < 0) throw new ArgumentException("모르는 모양 모형: " + model);
            return new ShapeResolution
            {
                Status = StatusForced,
                Applied = ShapeForModel(model),
                Model = model,
                FormType = original?.FormType,
                Words = (original?.Words ?? new List<ShapeWord>()).Select(w => new ShapeWord
                {
                    Shape = w.Shape, Lemma = w.Lemma, Trigger = w.Trigger, CharSpan = w.CharSpan?.ToArray(), Status = w.Status,
                }).ToList(),
            };
        }

        /// <summary>모양 모형으로 바꿀 수 있는 form.type: 말하지 않음(null) 또는 blob.</summary>
        public static bool FormAllowsShape(string statedFormType) => statedFormType == null || statedFormType == "blob";

        /// <summary>spec의 _unmapped에서 category = "shape"인 항목을 charSpan 순서로(같으면 원래 순서).
        /// (2.2, CP10 G37 · G45–G51) reason = excluded_shape(제외 범주 때문에 그리지 않기로 한 말 — 예: '끈 같은 귀신'의 '끈', '네모난 귀신'의
        /// '네모', 넷째 범주가 나온 텍스트의 모양어) 또는 no_asset(동물이 중심 명사라 그리지 않기로 한 말 — 예: '끈 같은 뱀'의 '끈')은
        /// 모양어로 쓰지 않는다(챗봇 candidates.shape_words와 같은 규칙, UnrenderedReasons). 2.0·2.1 문서에는 이 사유가 없어 결과가 같다.</summary>
        public static readonly string[] UnrenderedReasons = { "excluded_shape", "no_asset" };

        public static List<ShapeWord> ExtractWords(SceneSpecV2 spec)
        {
            var words = new List<ShapeWord>();
            if (spec?.Unmapped == null) return words;
            foreach (var u in spec.Unmapped)
            {
                if (u == null || u.Category != "shape" || Array.IndexOf(UnrenderedReasons, u.Reason) >= 0) continue;
                var v = u.Value?["shape"];
                words.Add(new ShapeWord
                {
                    Shape = v != null && v.Type == JTokenType.String ? (string)v : null,
                    Lemma = u.Lemma,
                    Trigger = u.Provenance?.Trigger,
                    CharSpan = u.Provenance?.CharSpan,
                });
            }
            return SortBySpan(words);
        }

        public static ShapeResolution Resolve(SceneSpecV2 spec) => Resolve(ExtractWords(spec), spec?.Form?.Type, spec?.Form?.Base);

        /// <summary>모양어 목록(순서 무관)과 spec이 말한 form.type → 판정. 입력 객체는 바꾸지 않는다.
        /// statedBase(2.2, form.base)가 승인된 기본 형상이고 form.type이 null·blob이면 기본 형상이 윤곽을 정하므로 표에 있는 모양어도
        /// 모형으로 바꾸지 않고 not_applied_base로 기록한다(docs/asset-plan.md 2-5절. container 단면처럼 모양어가 변형값이 되는 경우는
        /// 매퍼가 form.baseVariant에 이미 넣는다).</summary>
        public static ShapeResolution Resolve(IEnumerable<ShapeWord> words, string statedFormType, string statedBase = null)
        {
            var sorted = SortBySpan((words ?? Enumerable.Empty<ShapeWord>()).Select(w => new ShapeWord
            {
                Shape = w.Shape, Lemma = w.Lemma, Trigger = w.Trigger, CharSpan = w.CharSpan?.ToArray(),
            }));
            var r = new ShapeResolution { FormType = statedFormType, Words = sorted };
            bool formAllows = FormAllowsShape(statedFormType);
            bool baseBlocks = formAllows && BaseShapes.IsBase(statedBase);
            foreach (var w in sorted)
            {
                if (baseBlocks) { w.Status = StatusNotAppliedBase; continue; }   // 기본 형상이 그려짐: 모형 유무와 상관없이 윤곽은 기본 형상
                if (!IsMapped(w.Shape)) { w.Status = StatusUnmapped; continue; }
                if (!formAllows) { w.Status = StatusNotAppliedForm; continue; }
                if (r.Applied == null)
                {
                    r.Applied = w.Shape;
                    r.Model = ModelByShape[w.Shape];
                    w.Status = StatusApplied;
                }
                else w.Status = w.Shape == r.Applied ? StatusApplied : StatusConflict;   // 같은 모양을 또 말함 = 같은 적용
            }
            // 맨 위 상태: 적용했으면 applied. 아니면 표에 없는 모양어가 하나라도 있을 때 unmapped_shape,
            // 표에 있는 모양어가 형태 때문에 막혔을 때 not_applied_form, 모양어가 없으면 none.
            if (r.Applied != null) r.Status = StatusApplied;
            else if (sorted.Any(w => w.Status == StatusUnmapped)) r.Status = StatusUnmapped;
            else if (sorted.Any(w => w.Status == StatusNotAppliedForm)) r.Status = StatusNotAppliedForm;
            else if (sorted.Any(w => w.Status == StatusNotAppliedBase)) r.Status = StatusNotAppliedBase;
            else r.Status = StatusNone;
            return r;
        }

        static List<ShapeWord> SortBySpan(IEnumerable<ShapeWord> words) =>
            words.Select((w, i) => (w, i))
                 .OrderBy(x => x.w.CharSpan != null && x.w.CharSpan.Length > 0 ? x.w.CharSpan[0] : int.MaxValue)
                 .ThenBy(x => x.w.CharSpan != null && x.w.CharSpan.Length > 1 ? x.w.CharSpan[1] : int.MaxValue)
                 .ThenBy(x => x.i)
                 .Select(x => x.w).ToList();
    }
}
