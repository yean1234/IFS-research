// 소유감 실험 변형본 생성기(설계 1절). 원본 spec + 참여자 번호 + 설정 → 원본 해석값, 변형 4개, 제시 순서, 오류·플래그.
//   - 원본 spec은 고치지 않는다. 변형 = 해석된 SceneParams + 덮어쓰기(SceneOverride).
//   - 사전·규칙만 쓴다(LLM·난수 없음). 입력이 같으면 결과(manifest의 variants·order)가 바이트까지 같다.
//   - 기본값·모양 해석은 SceneParams·ShapeMapping을 그대로 쓴다(Python에 복제하지 않는다).
//   - _inferred는 쓰지 않는다(useInferred = false로 해석).
// 변형 규칙:
//   크기  layout.size ± sizeStep. [step, 1−step] 안이면 cb 0 = +, 1 = −. 밖이면 들어오는 쪽(forced). clamp 없음.
//   색    ΔE00은 로더·셰이더가 실제로 쓰는 알베도(RenderedColor: HSL → sRGB × 밝기 배율, 선형 공간) 기준.
//         유채색(s ≥ 0.10): h를 cb 방향(0 = +, 1 = −)으로 1°씩, ΔE00 ≥ 목표인 최소 각. 180°까지 안 되면 명도(lightness_fallback).
//         무채색: l을 0.005씩, ΔE00 ≥ 목표인 최소량. 두 방향 다 되면 cb(0 = 밝게, 1 = 어둡게), 아니면 되는 쪽.
//         둘 다 안 되면 도달 가능한 최대 변화 + belowTarget. 다른 슬롯(brightness·opacity …)은 건드리지 않는다.
//         불투명도는 목표에 넣지 않고, 배경(하늘 지평선 색) 위 알파 합성 색끼리의 ΔE00을 따로 기록한다(deltaE00Composited).
//   움직임 Still 묶음이거나 보이지 않는 조합이면 floating(add), 아니면 still(remove). 속도는 그대로.
//   형태  blob(모형 없음) → Cube(add), Sphere → Cube(swap), Cube·FlatCylinder·Cone → Sphere(remove),
//         mist·shell·fragments → blob(remove, 모양 모형 없음).
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능).
using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    public sealed class OwnershipVariant
    {
        /// <summary>orig | form | color | size | motion</summary>
        public string Id;
        /// <summary>바꾼 속성(form·color·size·motion). 원본은 null.</summary>
        public string Attribute;
        public SceneOverride Override = new SceneOverride();
        /// <summary>덮어쓰기를 적용한 해석값(로더가 로드한 뒤 이 값과 같아야 한다).</summary>
        public SceneParams Params;
        /// <summary>실제로 그려지는 것: 모양 모형(Sphere·Cube·FlatCylinder·Cone) 또는 형태(blob·mist·shell·fragments).</summary>
        public string Rendered;
        /// <summary>그려지는 모양 모형(없으면 null).</summary>
        public string RenderedShapeModel;
        public List<string> ChangedKeys = new List<string>();
        public JObject From, To, Detail, Magnitude;
        public string Rule;
        /// <summary>stated | default | mixed</summary>
        public string Source;
        public SortedDictionary<string, string> SourceByKey = new SortedDictionary<string, string>(StringComparer.Ordinal);
        public bool SaidNotRendered, Forced, BelowTarget, MotionAltersScale;

        public bool IsOriginal => Id == "orig";

        /// <summary>실험자 화면용 한 줄: from → to.</summary>
        public string Describe()
        {
            if (IsOriginal) return "orig: 원본(덮어쓰기 없음)";
            string F(JObject o) => o == null ? "" : string.Join(", ", o.Properties().Select(p => p.Name + "=" + p.Value.ToString(Newtonsoft.Json.Formatting.None)));
            return $"{Id}: {F(From)} → {F(To)} [{Rule}, {Source}]";
        }

        public JObject ToJson()
        {
            var o = new JObject
            {
                ["id"] = Id,
                ["attribute"] = Attribute,
                ["overrides"] = Override.OverridesJson(),
                ["shapeModel"] = Override.ShapeModel,
            };
            if (!IsOriginal)
            {
                o["changedKeys"] = new JArray(ChangedKeys.ToArray());
                o["from"] = From;
                o["to"] = To;
                o["rule"] = Rule;
                o["source"] = Source;
                var sbk = new JObject();
                foreach (var kv in SourceByKey) sbk[kv.Key] = kv.Value;
                o["sourceByKey"] = sbk;
                o["flags"] = new JObject
                {
                    ["saidNotRendered"] = SaidNotRendered,
                    ["forced"] = Forced,
                    ["belowTarget"] = BelowTarget,
                    ["motionAltersScale"] = MotionAltersScale,
                };
                o["magnitude"] = Magnitude;
                o["detail"] = Detail;
            }
            o["params"] = Params != null ? JObject.FromObject(Params.ToRecord()) : null;
            o["rendered"] = Rendered;
            return o;
        }
    }

    public sealed class OwnershipPlan
    {
        public int ParticipantNumber, Cb, OrderRow;
        public OwnershipConfig Config;
        public SceneParams OriginalParams;
        public ShapeResolution Shape;
        /// <summary>원본에서 그려지는 모양 모형(Sphere·Cube·FlatCylinder·Cone) 또는 "none".</summary>
        public string OriginalShapeModel;
        public string OriginalRendered;
        public double EffectiveOpacity;
        public bool LowVisibility;
        public List<string> StatedKeys = new List<string>();
        public List<string> DefaultKeys = new List<string>();
        public int UnmappedCount, UnmatchedCount, AlternativesCount, NeedsConfirmationCount;
        /// <summary>고정 순서: orig, form, color, size, motion(오류로 만들지 못한 변형은 빠진다).</summary>
        public List<OwnershipVariant> Variants = new List<OwnershipVariant>();
        public string[] Order = new string[0];
        /// <summary>생성 오류. 하나라도 있으면 실험을 시작하지 않는다.</summary>
        public List<string> Errors = new List<string>();
        /// <summary>실험은 가능하지만 실험자가 알아야 하는 것(lowVisibility, saidNotRendered, belowTarget, forced).</summary>
        public List<string> Warnings = new List<string>();

        public bool Ok => Errors.Count == 0;

        public OwnershipVariant Get(string id) => Variants.FirstOrDefault(v => v.Id == id);

        public JObject OriginalJson() => new JObject
        {
            ["params"] = JObject.FromObject(OriginalParams.ToRecord()),
            ["shapeModel"] = OriginalShapeModel,
            ["rendered"] = OriginalRendered,
            ["statedKeys"] = new JArray(StatedKeys.ToArray()),
            ["defaultKeys"] = new JArray(DefaultKeys.ToArray()),
            ["unmappedCount"] = UnmappedCount,
            ["unmatchedCount"] = UnmatchedCount,
            ["alternativesCount"] = AlternativesCount,
            ["needsConfirmationCount"] = NeedsConfirmationCount,
            ["effectiveOpacity"] = Math.Round(EffectiveOpacity, 4),
            ["shape"] = Shape?.ToJson(),
        };

        public JObject FlagsJson() => new JObject { ["lowVisibility"] = LowVisibility };

        public JArray VariantsJson() => new JArray(Variants.Select(v => (JToken)v.ToJson()).ToArray());
    }

    public static class OwnershipVariantGenerator
    {
        /// <summary>유채색 기준: 해석 s가 이 값 이상이면 색상(h)을 돌린다.</summary>
        public const double ChromaticMinSaturation = 0.10;
        public const double HueStep = 1.0 / 360.0;
        public const int MaxHueSteps = 180;
        public const double LightnessStep = 0.005;
        /// <summary>원본 유효 불투명도가 이 값보다 작으면 lowVisibility.</summary>
        public const double LowVisibilityOpacity = 0.15;

        /// <summary>
        /// 보이지 않는 움직임 조합(잠정 표): 이 묶음을 이 모양 모형에 걸면 회전축 대칭이라 윤곽이 바뀌지 않는다.
        /// Spin = 피벗의 y축 회전, Sway = z축 기울임(SpecMotion). 그 밖의 묶음은 이동·크기 변화라 어느 형상에서도 보인다.
        /// anyPosture: 자세 변형(SceneLoader.PostureScale, 늘 x = z)이 있어도 대칭이 유지되는지. y축 회전은 유지되고,
        /// z축 기울임은 y만 눌리거나 늘어난 구(타원체)에서 보이므로 자세가 none일 때만 보이지 않는다.
        /// 표에 없는 형태: 기본 blob(모양 모형 없음)은 IFS 셰이더가 물체 좌표 노이즈로 정점을 밀어(_Lumpiness 0.14)
        /// 울퉁불퉁한 윤곽이 물체와 함께 돌므로 회전·기울임이 보인다. mist(굴곡 0.30·안개 가장자리)·shell(노이즈 테두리 열림)·
        /// fragments(비대칭 조각 5개)·Cube도 같은 이유로 보인다. 납작 원기둥·원뿔은 z축 기울임이 보인다.
        /// 한계: 모양 모형에도 표면 얼룩(_Roughness에 따른 mottle, 물체 좌표)이 있어 윤곽은 그대로여도 얼룩이 도는 것은 보인다.
        /// 이 표는 윤곽 기준이다(docs/decisions.md X32).
        /// </summary>
        public static readonly IReadOnlyList<(MotionGroup group, string model, bool anyPosture)> InvisibleMotion = new[]
        {
            (MotionGroup.Spin, ShapeMapping.ModelSphere, true),
            (MotionGroup.Spin, ShapeMapping.ModelFlatCylinder, true),
            (MotionGroup.Spin, ShapeMapping.ModelCone, true),
            (MotionGroup.Sway, ShapeMapping.ModelSphere, false),
        };

        /// <summary>크기 정보를 바꾸는 움직임 묶음(맥동·퍼짐·다가옴·가라앉음). 원본·변형 중 하나라도 이 묶음이면 motionAltersScale.</summary>
        public static readonly MotionGroup[] ScaleAlteringGroups = { MotionGroup.Pulse, MotionGroup.Expand, MotionGroup.Approach, MotionGroup.Sink };

        /// <summary>형태별 셰이더 밀도(SceneLoader의 FormPresets와 같은 값: mist만 0.5). 유효 불투명도 = opacity × 밀도.</summary>
        public static readonly IReadOnlyDictionary<string, double> FormDensity = new Dictionary<string, double>(StringComparer.Ordinal)
        {
            { "blob", 1.0 }, { "mist", 0.5 }, { "shell", 1.0 }, { "fragments", 1.0 },
        };

        /// <summary>
        /// 합성 ΔE00(기록용)의 배경색(sRGB). 중립 환경의 하늘 지평선 색 = 카메라 배경색(EnvironmentSettings.skyHorizon,
        /// Unity 전용 테스트가 같은 값인지 확인). 형상 뒤로 바닥(0.46)이 보이는 시선에서는 실제 배경과 다르다.
        /// </summary>
        public static readonly double[] CompositeBackgroundSrgb = { 0.74, 0.74, 0.75 };

        public const string AddMotionType = "floating";
        public const string RemoveMotionType = "still";

        /// <param name="shapeModel">그려지는 모양 모형. null(모양 모형 없는 blob·mist·shell·fragments)이면 늘 보인다.</param>
        /// <param name="posture">form.posture 해석값. none이 아니면 자세 변형이 있다고 본다(표에 없는 자세도 보수적으로).</param>
        public static bool IsInvisibleMotion(MotionGroup group, string shapeModel, string posture = SceneParams.NoPosture) =>
            shapeModel != null && InvisibleMotion.Any(x => x.group == group && x.model == shapeModel
                                                           && (x.anyPosture || posture == null || posture == SceneParams.NoPosture));

        public static string SourceLabel(IEnumerable<string> perKey)
        {
            var set = new HashSet<string>(perKey);
            if (set.Count == 0) return null;
            if (set.Count == 1) return set.First();
            return "mixed";
        }

        static double R4(double v) => Math.Round(v, 4);

        public static OwnershipPlan Generate(SceneSpecV2 spec, int participantNumber, OwnershipConfig config, SceneDefaults defaults = null)
        {
            config = (config ?? new OwnershipConfig()).Clone();
            defaults = defaults ?? new SceneDefaults();
            var plan = new OwnershipPlan { Config = config, ParticipantNumber = participantNumber };
            if (spec == null) { plan.Errors.Add("spec이 없습니다"); return plan; }
            if (participantNumber < 1) { plan.Errors.Add($"참여자 번호 {participantNumber}: 1 이상이어야 합니다"); return plan; }
            plan.Errors.AddRange(config.Validate().Select(e => "설정: " + e));
            if (!plan.Ok) return plan;

            plan.Cb = WilliamsDesign.CbFor(participantNumber);
            plan.OrderRow = WilliamsDesign.RowFor(participantNumber);
            plan.Order = WilliamsDesign.OrderFor(participantNumber);

            var orig = SceneParams.FromSpec(spec, defaults, useInferred: false);
            plan.OriginalParams = orig;
            if (orig.InferredUsed.Count > 0) plan.Errors.Add("_inferred 값을 썼습니다(useInferredSuggestions는 꺼져 있어야 함): " + string.Join(", ", orig.InferredUsed));
            plan.Shape = ShapeMapping.Resolve(spec);
            plan.DefaultKeys = orig.DefaultsUsed.OrderBy(k => k, StringComparer.Ordinal).ToList();
            plan.StatedKeys = orig.ToRecord().Keys.Where(k => !orig.DefaultsUsed.Contains(k)).OrderBy(k => k, StringComparer.Ordinal).ToList();
            plan.UnmappedCount = spec.Unmapped?.Count ?? 0;
            plan.UnmatchedCount = spec.Unmatched?.Count ?? 0;
            plan.AlternativesCount = spec.Alternatives?.Count ?? 0;
            plan.NeedsConfirmationCount = spec.NeedsConfirmation?.Count ?? 0;

            string form = orig.GetCategory("form.type");
            if (Array.IndexOf(SceneParams.FormTypes, form) < 0)
            {
                plan.Errors.Add($"모르는 form.type: {form}(대체하지 않음)");
                return plan;
            }
            string origModel = plan.Shape.Model;
            if (origModel != null && Array.IndexOf(ShapeMapping.Models, origModel) < 0)
            {
                plan.Errors.Add("모르는 모양 모형: " + origModel);
                return plan;
            }
            if (origModel != null && form != "blob")
            {
                plan.Errors.Add($"모양 모형 {origModel}이 form.type={form}에 적용됨(blob에만 적용해야 함) — 기본값 설정을 확인");
                return plan;
            }
            plan.OriginalShapeModel = origModel ?? "none";
            plan.OriginalRendered = origModel ?? form;
            plan.EffectiveOpacity = orig.GetNumber("material.opacity") * (origModel != null ? 1.0 : FormDensity[form]);
            plan.LowVisibility = plan.EffectiveOpacity < LowVisibilityOpacity;
            if (plan.LowVisibility)
                plan.Warnings.Add($"lowVisibility: 원본 유효 불투명도 {plan.EffectiveOpacity:0.###} < {LowVisibilityOpacity} — 형상이 잘 보이지 않을 수 있음");

            var origVariant = new OwnershipVariant { Id = "orig", Params = orig.Clone(), Rendered = plan.OriginalRendered, RenderedShapeModel = origModel };
            plan.Variants.Add(origVariant);

            TryAdd(plan, () => Form(spec, plan));
            TryAdd(plan, () => Color(spec, plan));
            TryAdd(plan, () => Size(spec, plan));
            TryAdd(plan, () => Motion(spec, plan));

            foreach (var v in plan.Variants.Where(v => !v.IsOriginal)) Finish(plan, v);
            return plan;
        }

        static void TryAdd(OwnershipPlan plan, Func<OwnershipVariant> make)
        {
            var v = make();
            if (v != null) plan.Variants.Add(v);
        }

        // 덮어쓰기 적용 → 해석값·그려지는 것 → 원본과 같은지·의도한 키만 바뀌었는지 확인, 경고 모으기
        static void Finish(OwnershipPlan plan, OwnershipVariant v)
        {
            var errs = v.Override.Validate();
            foreach (var e in errs) plan.Errors.Add($"{v.Id}: {e}");
            if (errs.Count > 0) return;
            v.Params = plan.OriginalParams.Clone();
            v.Override.ApplyTo(v.Params);
            string vform = v.Params.GetCategory("form.type");
            v.RenderedShapeModel = v.Override.ShapeModel ?? plan.Shape.Model;
            if (v.RenderedShapeModel != null && vform != "blob")
                plan.Errors.Add($"{v.Id}: 모양 모형 {v.RenderedShapeModel}을 form.type={vform}에 그릴 수 없음");
            v.Rendered = v.RenderedShapeModel ?? vform;

            var a = plan.OriginalParams.ToRecord();
            var b = v.Params.ToRecord();
            var diff = a.Keys.Where(k => !Equals(a[k], b[k])).ToList();
            if (diff.Count == 0 && v.Rendered == plan.OriginalRendered)
                plan.Errors.Add($"{v.Id}: 변형 결과가 원본과 같습니다({v.Rule}) — 이 spec·설정으로는 이 변형을 만들 수 없음");
            var expected = v.Override.Numbers.Keys.Concat(v.Override.Categories.Keys).OrderBy(k => k, StringComparer.Ordinal).ToList();
            if (diff.Count > 0 && !diff.OrderBy(k => k, StringComparer.Ordinal).SequenceEqual(expected))
                plan.Errors.Add($"{v.Id}: 바뀐 키({string.Join(",", diff)})가 덮어쓴 키({string.Join(",", expected)})와 다름");

            if (v.SaidNotRendered) plan.Warnings.Add($"{v.Id}: saidNotRendered — 참여자가 말했지만 화면에 반영되지 않은 모양어가 있음");
            if (v.BelowTarget) plan.Warnings.Add($"{v.Id}: belowTarget — 목표 ΔE00 {plan.Config.colorDeltaE}에 못 미침({v.Magnitude?["deltaE00"]})");
            if (v.Forced) plan.Warnings.Add($"{v.Id}: forced — 원본 크기가 끝에 가까워 방향을 균형 비트와 무관하게 정함");
        }

        static bool HasProv(SceneSpecV2 s, string path) =>
            s.Provenance != null && s.Provenance.TryGetValue(path, out var l) && l != null && l.Count > 0;

        public const string SlotStated = "stated";
        public const string SlotDefault = "default";
        public const string SlotUnsupported = "unsupported";

        /// <summary>
        /// spec 슬롯 하나의 출처. 변형의 source와 실험자 SpecCheck 화면이 이 함수 하나를 같이 쓴다.
        /// 근거(_provenance)가 있으면 stated, 값도 근거도 없으면 default(기본값으로 채움), 값은 있는데 근거가 없으면 unsupported.
        /// 변형 source에서는 근거가 없으면 말한 것으로 보지 않으므로 unsupported도 default로 센다(Stated 참고).
        /// </summary>
        public static string SlotSource(SceneSpecV2 spec, string path)
        {
            if (spec == null) return SlotDefault;
            if (HasProv(spec, path)) return SlotStated;
            return SceneSpecJson.GetSlot(spec, path) != null ? SlotUnsupported : SlotDefault;
        }

        static bool Stated(SceneSpecV2 spec, string path) => SlotSource(spec, path) == SlotStated;

        static string Label(bool stated) => stated ? "stated" : "default";

        // ── 형태 ──────────────────────────────────────────────────────────
        static OwnershipVariant Form(SceneSpecV2 spec, OwnershipPlan plan)
        {
            var v = new OwnershipVariant { Id = "form", Attribute = "form" };
            string form = plan.OriginalParams.GetCategory("form.type");
            string model = plan.Shape.Model;
            string key;
            switch (plan.OriginalRendered)
            {
                case "blob":
                    v.Override.ShapeModel = ShapeMapping.ModelCube; v.Rule = "add"; key = "form.shapeModel"; break;
                case ShapeMapping.ModelSphere:
                    v.Override.ShapeModel = ShapeMapping.ModelCube; v.Rule = "swap"; key = "form.shapeModel"; break;
                case ShapeMapping.ModelCube:
                case ShapeMapping.ModelFlatCylinder:
                case ShapeMapping.ModelCone:
                    v.Override.ShapeModel = ShapeMapping.ModelSphere; v.Rule = "remove"; key = "form.shapeModel"; break;
                case "mist":
                case "shell":
                case "fragments":
                    v.Override.Categories["form.type"] = "blob"; v.Rule = "remove"; key = "form.type"; break;
                default:
                    plan.Errors.Add("form: 모르는 원본 형태 " + plan.OriginalRendered);
                    return null;
            }
            string toModel = v.Override.ShapeModel ?? (key == "form.type" ? null : model);
            string toForm = v.Override.Categories.TryGetValue("form.type", out var f) ? f : form;
            v.ChangedKeys.Add(key);
            v.From = new JObject { ["form.type"] = form, ["shapeModel"] = model ?? "none", ["rendered"] = plan.OriginalRendered };
            v.To = new JObject { ["form.type"] = toForm, ["shapeModel"] = toModel ?? "none", ["rendered"] = toModel ?? toForm };
            // form.type 슬롯의 근거(SpecCheck 화면과 같은 기준) 또는 화면에 반영된 모양어
            bool stated = Stated(spec, "form.type") || plan.Shape.Status == ShapeMapping.StatusApplied;
            v.SourceByKey[key] = Label(stated);
            v.Source = SourceLabel(v.SourceByKey.Values);
            v.SaidNotRendered = plan.Shape.Words.Any(w => w.Status == ShapeMapping.StatusUnmapped
                                                          || w.Status == ShapeMapping.StatusConflict
                                                          || w.Status == ShapeMapping.StatusNotAppliedForm);
            // 형태가 바뀌면 같은 움직임이 보이거나 안 보이게 될 수 있다(분석 참고용).
            MotionGroups.TryGet(plan.OriginalParams.GetCategory("motion.type"), out var g);
            string posture = plan.OriginalParams.GetCategory("form.posture");
            v.Detail = new JObject
            {
                ["shapeStatus"] = plan.Shape.Status,
                ["shapeWords"] = new JArray(plan.Shape.Words.Select(w => (JToken)new JObject { ["shape"] = w.Shape, ["trigger"] = w.Trigger, ["status"] = w.Status }).ToArray()),
                ["motionVisibleFrom"] = g != MotionGroup.Still && !IsInvisibleMotion(g, model, posture),
                ["motionVisibleTo"] = g != MotionGroup.Still && !IsInvisibleMotion(g, toModel, posture),
            };
            v.Magnitude = null;
            return v;
        }

        // ── 색 ───────────────────────────────────────────────────────────
        // 목표 ΔE00은 셰이더 알베도 기준(밝기 배율 포함). 색 변형은 h·l만 바꾸므로 밝기는 원본 값 그대로다.
        static Lab LabOf(double h, double s, double l, double brightness) => RenderedColor.AlbedoLab(h, s, l, brightness);

        /// <summary>배경 위에 원본의 표면 알파로 합성한 두 알베도의 ΔE00(기록용, 목표 계산에는 쓰지 않음).</summary>
        public static double CompositedDeltaE(double h0, double l0, double h1, double l1, double s, double brightness, double alpha)
        {
            var bg = CompositeBackgroundSrgb;
            RenderedColor.AlbedoSrgb(h0, s, l0, brightness, out double r0, out double g0, out double b0);
            RenderedColor.AlbedoSrgb(h1, s, l1, brightness, out double r1, out double g1, out double b1);
            return ColorMetrics.DeltaE2000(RenderedColor.CompositeLab(r0, g0, b0, alpha, bg[0], bg[1], bg[2]),
                                           RenderedColor.CompositeLab(r1, g1, b1, alpha, bg[0], bg[1], bg[2]));
        }

        struct Candidate
        {
            public double Value, DeltaE;
            public int Steps;
            public bool Found;
        }

        // h를 dir 방향으로 1°씩(최대 180°). 목표에 닿는 최소 각과, 닿지 못할 때 최대 ΔE 후보.
        static void SearchHue(double h0, double s, double l, double bright, Lab lab0, int dir, double target, out Candidate first, out Candidate max)
        {
            first = default; max = default;
            for (int k = 1; k <= MaxHueSteps; k++)
            {
                double raw = h0 + dir * k * HueStep;
                raw -= Math.Floor(raw);
                double cand = R4(raw);
                if (cand >= 1) cand -= 1;
                double de = ColorMetrics.DeltaE2000(lab0, LabOf(cand, s, l, bright));
                if (de > max.DeltaE) max = new Candidate { Value = cand, DeltaE = de, Steps = k };
                if (de >= target) { first = new Candidate { Value = cand, DeltaE = de, Steps = k, Found = true }; return; }
            }
        }

        // l을 dir 방향으로 0.005씩(끝 0·1 포함). 목표에 닿는 최소량과 최대 ΔE 후보.
        static void SearchLightness(double h, double s, double l0, double bright, Lab lab0, int dir, double target, out Candidate first, out Candidate max)
        {
            first = default; max = default;
            double l0r = R4(l0);
            for (int n = 1; ; n++)
            {
                double raw = l0 + dir * n * LightnessStep;
                bool last = false;
                if (raw >= 1) { raw = 1; last = true; }
                if (raw <= 0) { raw = 0; last = true; }
                double cand = R4(raw);
                if (cand != l0r)
                {
                    double de = ColorMetrics.DeltaE2000(lab0, LabOf(h, s, cand, bright));
                    if (de > max.DeltaE) max = new Candidate { Value = cand, DeltaE = de, Steps = n };
                    if (de >= target) { first = new Candidate { Value = cand, DeltaE = de, Steps = n, Found = true }; return; }
                }
                if (last) return;
            }
        }

        static OwnershipVariant Color(SceneSpecV2 spec, OwnershipPlan plan)
        {
            var p = plan.OriginalParams;
            double h = p.GetNumber("material.color.h"), s = p.GetNumber("material.color.s"), l = p.GetNumber("material.color.l");
            double bright = p.GetNumber("material.brightness");
            double target = plan.Config.colorDeltaE;
            var lab0 = LabOf(h, s, l, bright);
            var v = new OwnershipVariant { Id = "color", Attribute = "color" };
            bool chromatic = s >= ChromaticMinSaturation;
            int hueDir = plan.Cb == 0 ? +1 : -1;
            int lightDir = plan.Cb == 0 ? +1 : -1;   // 0 = 밝게, 1 = 어둡게
            string key = null;
            Candidate chosen = default;
            string direction = null;

            Candidate hueFirst = default, hueMax = default;
            if (chromatic)
            {
                SearchHue(h, s, l, bright, lab0, hueDir, target, out hueFirst, out hueMax);
                if (hueFirst.Found)
                {
                    key = "material.color.h"; chosen = hueFirst; v.Rule = "hue";
                    direction = hueDir > 0 ? "+hue" : "-hue";
                }
            }
            if (key == null)
            {
                SearchLightness(h, s, l, bright, lab0, +1, target, out var upFirst, out var upMax);
                SearchLightness(h, s, l, bright, lab0, -1, target, out var downFirst, out var downMax);
                string rule = chromatic ? "lightness_fallback" : "lightness";
                if (upFirst.Found || downFirst.Found)
                {
                    int dir = upFirst.Found && downFirst.Found ? lightDir : (upFirst.Found ? +1 : -1);
                    chosen = dir > 0 ? upFirst : downFirst;
                    key = "material.color.l"; v.Rule = rule; direction = dir > 0 ? "lighter" : "darker";
                }
                else
                {
                    // 목표에 못 미침: 도달 가능한 최대 변화(색상 최대 vs 명도 양쪽 끝 중 큰 것)
                    var lightMax = upMax.DeltaE >= downMax.DeltaE ? upMax : downMax;
                    int lmDir = upMax.DeltaE >= downMax.DeltaE ? +1 : -1;
                    if (chromatic && hueMax.DeltaE >= lightMax.DeltaE)
                    {
                        key = "material.color.h"; chosen = hueMax; v.Rule = "hue"; direction = hueDir > 0 ? "+hue" : "-hue";
                    }
                    else
                    {
                        key = "material.color.l"; chosen = lightMax; v.Rule = rule; direction = lmDir > 0 ? "lighter" : "darker";
                    }
                    v.BelowTarget = true;
                }
            }

            v.Override.Numbers[key] = chosen.Value;
            v.ChangedKeys.Add(key);
            double th = key == "material.color.h" ? chosen.Value : h;
            double tl = key == "material.color.l" ? chosen.Value : l;
            v.From = new JObject { ["material.color.h"] = R4(h), ["material.color.s"] = R4(s), ["material.color.l"] = R4(l) };
            v.To = new JObject { ["material.color.h"] = R4(th), ["material.color.s"] = R4(s), ["material.color.l"] = R4(tl) };
            bool colorStated = Stated(spec, "material.color");
            v.SourceByKey[key] = Label(colorStated);   // h·l ← material.color
            v.Source = SourceLabel(v.SourceByKey.Values);
            string form = p.GetCategory("form.type");
            double alpha = RenderedColor.SurfaceAlpha(form, p.GetNumber("material.opacity"),
                plan.Shape.Model != null ? 1.0 : FormDensity[form]);
            v.Magnitude = new JObject
            {
                ["deltaE00"] = Math.Round(chosen.DeltaE, 3),
                ["deltaE00Composited"] = Math.Round(CompositedDeltaE(h, l, th, tl, s, bright, alpha), 3),
            };
            v.Detail = new JObject
            {
                ["achromatic"] = !chromatic,
                ["targetDeltaE00"] = target,
                ["direction"] = direction,
                ["steps"] = chosen.Steps,
                ["stepSize"] = key == "material.color.h" ? "1/360" : "0.005",
                ["saturationSource"] = Label(spec.Material.Saturation != null ? Stated(spec, "material.saturation") : colorStated),
                ["deltaEBasis"] = "albedo",
                ["brightnessFactor"] = R4(RenderedColor.BrightnessFactor(bright)),
                ["compositeAlpha"] = R4(alpha),
                ["compositeBackground"] = new JArray(CompositeBackgroundSrgb.Select(c => (object)c).ToArray()),
            };
            return v;
        }

        // ── 크기 ─────────────────────────────────────────────────────────
        static OwnershipVariant Size(SceneSpecV2 spec, OwnershipPlan plan)
        {
            double s0 = plan.OriginalParams.GetNumber("layout.size");
            double step = plan.Config.sizeStep;
            const double eps = 1e-9;
            int dir;
            bool forced;
            if (s0 >= step - eps && s0 <= 1 - step + eps) { dir = plan.Cb == 0 ? +1 : -1; forced = false; }
            else if (s0 < step) { dir = +1; forced = true; }
            else { dir = -1; forced = true; }
            double to = R4(s0 + dir * step);
            var v = new OwnershipVariant { Id = "size", Attribute = "size", Rule = dir > 0 ? "up" : "down", Forced = forced };
            v.Override.Numbers["layout.size"] = to;
            v.ChangedKeys.Add("layout.size");
            v.From = new JObject { ["layout.size"] = R4(s0) };
            v.To = new JObject { ["layout.size"] = to };
            v.SourceByKey["layout.size"] = Label(Stated(spec, "layout.size"));
            v.Source = SourceLabel(v.SourceByKey.Values);
            v.Magnitude = new JObject { ["sizeStep"] = step };
            v.Detail = new JObject
            {
                ["direction"] = dir > 0 ? "up" : "down",
                ["scaleFrom"] = Math.Round(SceneParams.SizeToScale(s0), 4),
                ["scaleTo"] = Math.Round(SceneParams.SizeToScale(to), 4),
            };
            return v;
        }

        // ── 움직임 ───────────────────────────────────────────────────────
        static OwnershipVariant Motion(SceneSpecV2 spec, OwnershipPlan plan)
        {
            string type = plan.OriginalParams.GetCategory("motion.type");
            if (!MotionGroups.TryGet(type, out var g))
            {
                plan.Errors.Add($"motion: 모르는 motion.type '{type}'(대체하지 않음)");
                return null;
            }
            string model = plan.Shape.Model;
            bool invisible = IsInvisibleMotion(g, model, plan.OriginalParams.GetCategory("form.posture"));
            bool add = g == MotionGroup.Still || invisible;
            string toType = add ? AddMotionType : RemoveMotionType;
            MotionGroups.TryGet(toType, out var tg);
            var v = new OwnershipVariant { Id = "motion", Attribute = "motion", Rule = add ? "add" : "remove" };
            v.Override.Categories["motion.type"] = toType;
            v.ChangedKeys.Add("motion.type");
            v.From = new JObject { ["motion.type"] = type };
            v.To = new JObject { ["motion.type"] = toType };
            v.SourceByKey["motion.type"] = Label(Stated(spec, "motion.type"));
            v.Source = SourceLabel(v.SourceByKey.Values);
            v.MotionAltersScale = ScaleAlteringGroups.Contains(g) || ScaleAlteringGroups.Contains(tg);
            v.Magnitude = null;
            v.Detail = new JObject
            {
                ["originalGroup"] = g.ToString(),
                ["variantGroup"] = tg.ToString(),
                ["originalVisible"] = g != MotionGroup.Still && !invisible,
                ["speed"] = R4(plan.OriginalParams.GetNumber("motion.speed")),
            };
            return v;
        }
    }
}
