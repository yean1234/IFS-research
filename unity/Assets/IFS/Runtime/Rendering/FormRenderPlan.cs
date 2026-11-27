// SceneParams + 모양어 판정(ShapeResolution) → 형상별 렌더러가 받는 고유 입력(X64). 규칙 기반 어댑터다(LLM 없음).
//   어느 렌더러를 쓸지는 form.type과 슬롯 값(그리고 모양어 판정)만으로 정한다.
//   meta.mapping 등 매퍼 정보는 입력으로 받지 않는다(X65): 같은 슬롯 값이면 v0 출력이든 v1 출력이든 같은 계획이 나온다.
//   형상 프리셋(굴곡·노이즈 크기·안개 가장자리·밀도·껍질 열림 …)은 참여자가 말한 값이 아니라 "형상 프리셋 기본값"이다.
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 같은 입력이면 언제나 같은 계획이다.
using System.Collections.Generic;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    /// <summary>형태별 모양 프리셋(IFS 셰이더 전용): 굴곡, 노이즈 크기, 안개 가장자리, 밀도, 껍질 열림.</summary>
    public readonly struct FormPreset
    {
        public readonly float Lumpiness, NoiseScale, Fuzz, Density, ShellOpen;

        public FormPreset(float lumpiness, float noiseScale, float fuzz, float density, float shellOpen)
        {
            Lumpiness = lumpiness; NoiseScale = noiseScale; Fuzz = fuzz; Density = density; ShellOpen = shellOpen;
        }
    }

    public sealed class FormRenderPlan
    {
        // 렌더러 이름(= report.json의 renderPath 기본값)
        public const string RendererBlob = "blob";
        public const string RendererMist = "mist";
        public const string RendererShell = "shell";
        public const string RendererFragments = "fragments";
        public const string RendererShapeModel = "shapeModel";
        /// <summary>기본 형상 렌더러 이름의 앞머리("base:container" …, report.json renderPath).</summary>
        public const string RendererBasePrefix = "base:";

        /// <summary>기본 형상 판정(계획 JSON base.status).</summary>
        public const string BaseApplied = "applied";
        public const string BaseNotAppliedForm = "not_applied_form";
        public const string BaseNotAppliedForced = "not_applied_forced";
        public const string BaseNoMesh = "no_mesh";

        /// <summary>안개 레이마칭 걸음 수(형상 프리셋 기본값). 셰이더 SceneSpecMist의 IFS_MIST_STEPS와 같아야 한다(테스트가 확인).</summary>
        public const int MistSteps = 8;

        /// <summary>형태별 프리셋. 값을 바꾸면 OwnershipVariantGenerator의 밀도 표·unity/README.md도 같이 본다.</summary>
        public static readonly IReadOnlyDictionary<string, FormPreset> FormPresets = new Dictionary<string, FormPreset>
        {
            { "blob", new FormPreset(0.14f, 1.6f, 0f, 1f, 0f) },
            // mist(SceneSpecMist): material.roughness는 표면 반사가 아니라 밀도 노이즈 크기 배율 lerp(0.7, 1.3, R)과 색 얼룩 세기를 정한다.
            // (이전 Fade 경로에서는 잔요철 정점 변위 · 색 얼룩 · PBR 광택(스무드니스 = 1 − R)이었다. 색 얼룩 식은 두 경로가 같다)
            { "mist", new FormPreset(0.30f, 1.1f, 1f, 0.5f, 0f) },
            { "shell", new FormPreset(0.04f, 2.0f, 0f, 1f, 0.35f) },
            // fragments: 각진 조각 메시(FragmentMesh)라 정점 변위를 쓰지 않는다(굴곡 0, 변위 0). 노이즈 크기는 얼룩·침식 무늬 크기.
            { "fragments", new FormPreset(0f, 2.4f, 0f, 1f, 0f) },
        };

        /// <summary>모양 모형(구·큐브·원기둥·원뿔): 굴곡 0, 안개 가장자리 0, 껍질 열림 0 + 정점 변위 0 → 윤곽 유지.
        /// 노이즈 크기는 blob과 같게 둬 거칠기 얼룩·침식 무늬의 크기가 기본 모형과 같다.</summary>
        public static readonly FormPreset ShapePreset = new FormPreset(0f, 1.6f, 0f, 1f, 0f);

        /// <summary>blob · mist · shell · fragments · shapeModel</summary>
        public string Renderer { get; private set; }
        /// <summary>해석된 form.type(null 슬롯은 기본값으로 채운 값).</summary>
        public string FormType { get; private set; }
        /// <summary>모양 모형(Sphere·Cube·FlatCylinder·Cone). 모양 모형이 아니면 null.</summary>
        public string ShapeModel { get; private set; }
        /// <summary>모양 값(round·square·flat·pointed). 모양 모형이 아니면 null.</summary>
        public string ShapeApplied { get; private set; }

        /// <summary>_BaseColor(sRGB, 각 0–1)와 재질 슬롯. 로더가 재질에 넣는 값과 같은 float.</summary>
        public float ColorR { get; private set; }
        public float ColorG { get; private set; }
        public float ColorB { get; private set; }
        public float Opacity { get; private set; }
        public float Brightness { get; private set; }
        public float Roughness { get; private set; }
        public float Erosion { get; private set; }

        /// <summary>반투명 셰이더를 쓰는가(RenderedColor.UsesFadeShader와 같은 판정).</summary>
        public bool Fade { get; private set; }
        /// <summary>형상 프리셋 기본값.</summary>
        public FormPreset Preset { get; private set; }
        /// <summary>정점 변위 0(모양 모형·fragments: 각진 면이 벌어지지 않게).</summary>
        public bool ZeroDisplacement { get; private set; }
        /// <summary>fragments 형상 프리셋 기본값: 조각 수·seed(그 밖의 렌더러는 0).</summary>
        public int FragmentPieces { get; private set; }
        public int FragmentSeed { get; private set; }
        /// <summary>fragments 조각 생성 규칙 버전(FragmentMesh.RuleVersion). 그 밖의 렌더러는 null.</summary>
        public string FragmentRule { get; private set; }
        /// <summary>mist 덩어리 배치 규칙 버전(MistLumps.RuleVersion)과 seed(형상 프리셋 기본값). 그 밖의 렌더러는 null·0.</summary>
        public string MistRule { get; private set; }
        public int MistSeed { get; private set; }
        /// <summary>형상 프리셋 기본값을 적은 로더 메모(notes). 없으면 null.</summary>
        public string PresetNote { get; private set; }

        /// <summary>(2.2) 지금 값의 기본 형상(form.base, none이면 null). 그리지 않아도 남는다.</summary>
        public string BaseRequested { get; private set; }
        /// <summary>(2.2) 그리는 기본 형상(BaseStatus = applied일 때만). 아니면 null.</summary>
        public string BaseShape { get; private set; }
        /// <summary>(2.2) applied | not_applied_form(form.type이 mist·shell·fragments) | not_applied_forced(변형본이 모양 모형 강제)
        /// | no_mesh(이 빌드에 메시가 없는 기본 형상). 기본 형상이 없으면 null.</summary>
        public string BaseStatus { get; private set; }
        /// <summary>(2.2) 기본 형상 메시 규칙 버전(BaseShapeMesh.RuleFor). 그리지 않으면 null.</summary>
        public string BaseRule { get; private set; }
        /// <summary>(2.2) 그리는 기본 형상의 변형값 전체(정하지 않은 키는 형상 프리셋 기본값)와 기본값으로 채운 키.</summary>
        public IReadOnlyDictionary<string, string> BaseVariant { get; private set; }
        public IReadOnlyList<string> BaseVariantDefaults { get; private set; }
        public int BaseSeed { get; private set; }

        // ── (2.3) 윤곽·발광(docs/scene-spec-mapping.md 8.4절). 2.0–2.2 spec(HasContour = false)에서는 모두 null이고 계획 JSON에도 나오지 않는다 ──
        /// <summary>슈퍼쿼드릭 렌더러 이름(report.json의 renderPath).</summary>
        public const string RendererSuperquadric = "superquadric";
        /// <summary>윤곽·발광 슬롯이 있는 값 집합인가(SceneParams.HasContourSlots).</summary>
        public bool HasContour { get; private set; }
        /// <summary>applied | not_applied_form | not_applied_base | not_applied_model | none.</summary>
        public string ContourStatus { get; private set; }
        /// <summary>지금 값의 form.roundness·form.aspect(null = 말하지 않음). 적용하지 않아도 남는다.</summary>
        public string Roundness { get; private set; }
        public string Aspect { get; private set; }
        /// <summary>그린 메시: superquadric/1(둥긂을 말함) | default(길쭉함만 말해 기본 덩어리 메시에 축 배율만). 적용하지 않았으면 null.</summary>
        public string ContourMesh { get; private set; }
        /// <summary>슈퍼쿼드릭 지수. 슈퍼쿼드릭을 그리지 않으면 null.</summary>
        public double? E1 { get; private set; }
        public double? E2 { get; private set; }
        /// <summary>형상 국소 배율에 곱할 (x, y, z). 길쭉함을 적용하지 않으면 null(로더가 배율을 곱하지 않는다).</summary>
        public double[] AxisRatios { get; private set; }
        /// <summary>그린 경로 때문에 기본값으로 정한 것(defaultsUsed에 더함): form.aspect.axis · form.aspect · form.roundness.</summary>
        public IReadOnlyList<string> ContourDefaultsUsed { get; private set; } = new string[0];
        /// <summary>material.emission(null = 말하지 않음, none = 빛이 없다고 말함).</summary>
        public string EmissionLevel { get; private set; }
        /// <summary>발광 세기(ContourRender). 말하지 않았으면 null.</summary>
        public double? EmissionIntensity { get; private set; }
        /// <summary>발광 색의 출처: said(말한 색) | default(기본색). 발광을 말하지 않았으면 null.</summary>
        public string EmissionColorSource { get; private set; }
        /// <summary>셰이더 발광 항(선형 RGB) = 바탕색(셰이더 알베도 식 RenderedColor.AlbedoSrgb, 선형) × 세기. 발광을 말하지 않았으면 null
        /// (로더가 셰이더 값을 건드리지 않는다 — 기본 검정이라 2.2와 같은 화소).</summary>
        public double[] EmissionLinear { get; private set; }

        // ── (2.4, G72) x·y·z 비율(ProportionsRender). 비율이 주어지지 않으면(spec null·덮어쓰기 없음) 모두 null이고 계획 JSON에도 나오지 않는다 ──
        /// <summary>유효 비율 (x, y, z)(가장 큰 값 = 1). 주어지지 않으면 null(로더가 비율을 곱하지 않는다 — 2.3과 같은 그림).</summary>
        public double[] Proportions { get; private set; }
        /// <summary>비율 원값(spec 값 0.2–1 또는 덮어쓰기·조절 화면 값 0.2–2.0). 주어지지 않으면 null.</summary>
        public double[] ProportionsRaw { get; private set; }
        /// <summary>원값 / 가장 큰 값이 0.2 아래라 0.2로 올린 축이 있는가(로더 notes).</summary>
        public bool ProportionsClamped { get; private set; }
        /// <summary>spec 비율의 axisSaid(spec 값이 null이면 null).</summary>
        public bool? ProportionsAxisSaid { get; private set; }
        /// <summary>local_scale(메시 형상: 국소 배율) | fragment_distribution(fragments: 조각 배치를 늘임). 주어지지 않으면 null.</summary>
        public string ProportionsMethod { get; private set; }
        /// <summary>비율이 주어져 form.aspect 축 비율을 쓰지 않았는가(form.aspect 값은 그대로 기록에 남음).</summary>
        public bool AspectSuperseded { get; private set; }

        FormRenderPlan() { }

        /// <summary>(2.4) 비율을 계획에 얹는다. 주어지지 않으면 아무것도 바꾸지 않는다(2.0–2.3 계획 그대로).</summary>
        void ApplyProportions(SceneParams current)
        {
            if (!current.ProportionsGiven) return;
            ProportionsRaw = current.ProportionsRaw;
            Proportions = ProportionsRender.Normalize(ProportionsRaw[0], ProportionsRaw[1], ProportionsRaw[2], out bool clamped);
            ProportionsClamped = clamped;
            ProportionsAxisSaid = current.SpecProportionsAxisSaid;
            ProportionsMethod = Renderer == RendererFragments ? ProportionsRender.MethodFragmentDistribution : ProportionsRender.MethodLocalScale;
        }

        /// <summary>(2.4) 기록의 proportions(계획 JSON·report.json). 비율이 주어지지 않으면 null.</summary>
        public JObject ProportionsJson() => Proportions == null ? null : new JObject
        {
            ["effective"] = new JArray(System.Math.Round(Proportions[0], 5), System.Math.Round(Proportions[1], 5), System.Math.Round(Proportions[2], 5)),
            ["raw"] = new JArray(System.Math.Round(ProportionsRaw[0], 5), System.Math.Round(ProportionsRaw[1], 5), System.Math.Round(ProportionsRaw[2], 5)),
            ["axisSaid"] = ProportionsAxisSaid,
            ["method"] = ProportionsMethod,
            ["rule"] = ProportionsRender.RuleVersion,
            ["aspectSuperseded"] = AspectSuperseded,
        };

        /// <summary>(2.3) 윤곽 적용 순서(8.4절 2번)와 발광(4번)을 계획에 얹는다. 2.0–2.2 값 집합이면 아무것도 바꾸지 않는다.</summary>
        void ApplyContourAndEmission(SceneParams current)
        {
            if (!current.HasContourSlots) return;
            HasContour = true;
            Roundness = current.GetCategory(ContourRender.RoundnessKey);
            Aspect = current.GetCategory(ContourRender.AspectKey);
            var defaults = new List<string>();
            if (Roundness == null && Aspect == null) ContourStatus = ContourRender.StatusNone;
            else if (BaseShape != null) ContourStatus = ContourRender.StatusNotAppliedBase;              // 2. 기본 형상
            else if (FormType != "blob") ContourStatus = ContourRender.StatusNotAppliedForm;           // 1. mist·shell·fragments
            else if (ShapeModel != null) ContourStatus = ContourRender.StatusNotAppliedModel;          // 3. 모양 모형(같은 말을 두 번 적용하지 않음)
            else
            {
                // 4. 기본 덩어리 경로
                ContourStatus = ContourRender.StatusApplied;
                var inv = System.Globalization.CultureInfo.InvariantCulture;
                if (Roundness != null)
                {
                    var (e1, e2) = ContourRender.Exponents(Roundness);
                    E1 = e1;
                    E2 = e2;
                    ContourMesh = ContourRender.MeshRule;
                    Renderer = RendererSuperquadric;
                    Preset = ShapePreset;             // 굴곡 0(모양 모형과 같은 프리셋)
                    ZeroDisplacement = true;          // 정점 변위 0 — 각진 윤곽이 노이즈로 흐려지지 않게
                    PresetNote = $"form.roundness={Roundness}: 형상 프리셋 기본값 — 슈퍼쿼드릭 메시(규칙 {ContourRender.MeshRule}, " +
                                 $"e1 {e1.ToString(inv)}, e2 {e2.ToString(inv)}, 경도 {ContourRender.LongitudeSegments} × 위도 {ContourRender.LatitudeSegments}, " +
                                 $"지름 1 × 기본 크기)로 기본 덩어리 메시를 대신함. 정점 변위 0, 굴곡 0, 노이즈 크기 {ShapePreset.NoiseScale.ToString(inv)}. " +
                                 $"수치 {ContourRender.ParamsVersion}";
                    if (Aspect == null) defaults.Add(ContourRender.AspectKey);
                }
                else
                {
                    ContourMesh = ContourRender.MeshDefault;   // 말하지 않은 둥긂은 바꾸지 않는다(기본 덩어리 메시 그대로)
                    defaults.Add(ContourRender.RoundnessKey);
                }
                if (Aspect != null && current.ProportionsGiven)
                    AspectSuperseded = true;   // (2.4) x·y·z 비율이 앞선다 — 축 비율을 곱하지 않고 form.aspect 값만 기록에 남긴다
                else if (Aspect != null)
                {
                    AxisRatios = ContourRender.AxisRatios(Aspect);
                    if (Aspect != "neutral") defaults.Add(ContourRender.AspectAxisKey);   // 긴 축 방향(세로 y)은 말하지 않은 기본값
                }
            }
            ContourDefaultsUsed = defaults;

            // 발광: 형상 경로와 상관없이. 색은 그리는 바탕색 그대로(새 색 없음), 세기만 곱한다. 블룸 없음.
            EmissionLevel = current.GetCategory(ContourRender.EmissionKey);
            if (EmissionLevel != null)
            {
                double k = ContourRender.EmissionIntensity(EmissionLevel);
                EmissionIntensity = k;
                EmissionColorSource = current.DefaultsUsed.Contains("material.color.h") || current.DefaultsUsed.Contains("material.color.l") ? "default" : "said";
                RenderedColor.AlbedoSrgb(current.GetNumber("material.color.h"), current.GetNumber("material.color.s"),
                    current.GetNumber("material.color.l"), current.GetNumber("material.brightness"), out double r, out double g, out double b);
                EmissionLinear = new[] { ColorMetrics.SrgbToLinear(r) * k, ColorMetrics.SrgbToLinear(g) * k, ColorMetrics.SrgbToLinear(b) * k };
            }
        }

        /// <summary>(2.3) 머티리얼에 넣는 발광 색(sRGB 부호화, 각 0–1). Unity는 선형 색공간에서 색 프로퍼티를 선형으로 바꿔 넣으므로
        /// 셰이더는 EmissionLinear를 받는다. 발광을 말하지 않았으면 false.</summary>
        public bool EmissionSrgb(out float r, out float g, out float b)
        {
            r = g = b = 0f;
            if (EmissionLinear == null) return false;
            r = (float)ColorMetrics.LinearToSrgb(EmissionLinear[0]);
            g = (float)ColorMetrics.LinearToSrgb(EmissionLinear[1]);
            b = (float)ColorMetrics.LinearToSrgb(EmissionLinear[2]);
            return true;
        }

        /// <summary>(2.3) 기록의 contour(initialScene.json·report.json·계획 JSON). 2.0–2.2 값 집합이면 null.
        /// 적용하지 않았으면 수치(mesh·e1·e2·axisRatios)는 null — 기본값과 미지정을 섞지 않는다.</summary>
        public JObject ContourJson()
        {
            if (!HasContour) return null;
            var o = new JObject
            {
                ["status"] = ContourStatus,
                ["roundness"] = Roundness,
                ["aspect"] = Aspect,
                ["mesh"] = ContourMesh,
                ["e1"] = E1,
                ["e2"] = E2,
                ["axisRatios"] = AxisRatios != null ? new JArray(AxisRatios) : null,
            };
            // (2.4) 비율이 form.aspect를 대신 그렸을 때만(그 밖에는 2.3과 같은 키)
            if (AspectSuperseded) o["aspectSupersededBy"] = ProportionsRender.Key;
            return o;
        }

        /// <summary>(2.3) 기록의 emission. 2.0–2.2 값 집합이면 null.</summary>
        public JObject EmissionJson() => !HasContour ? null : new JObject
        {
            ["level"] = EmissionLevel,
            ["intensity"] = EmissionIntensity,
            ["colorSource"] = EmissionColorSource,
        };

        /// <summary>
        /// current = 지금 적용할 값, initialFormType = 처음 로드 때의 form.type, shape = 모양어 판정(없으면 null).
        /// 모양 모형은 판정이 모형을 정했고 참여자가 form.type을 처음 값에서 바꾸지 않았을 때만 쓴다
        /// (조정 중 form.type을 바꾸면 그 형태 모형, 처음 값으로 돌아오면 다시 모양 모형).
        /// </summary>
        public static FormRenderPlan Build(SceneParams current, string initialFormType, ShapeResolution shape)
        {
            string form = current.GetCategory("form.type");
            // (2.2) 기본 형상: form.type이 blob(말하지 않아 기본값인 경우 포함)일 때만 그린다(docs/asset-plan.md 2-5절).
            // 변형본이 모양 모형을 강제하면 그 모형이 앞선다. 이 빌드에 메시가 없는 기본 형상이면 그리지 않고 기록만.
            string baseReq = current.IsCategorical(SceneParams.BaseKey) ? current.GetCategory(SceneParams.BaseKey) : SceneParams.NoBase;
            if (baseReq == SceneParams.NoBase || !BaseShapes.IsBase(baseReq)) baseReq = null;
            string baseStatus = null;
            if (baseReq != null)
            {
                if (!BaseShapes.FormAllowsBase(form)) baseStatus = BaseNotAppliedForm;
                else if (shape?.Status == ShapeMapping.StatusForced) baseStatus = BaseNotAppliedForced;
                else if (!BaseShapeMesh.Supports(baseReq)) baseStatus = BaseNoMesh;
                else baseStatus = BaseApplied;
            }
            bool baseApplied = baseStatus == BaseApplied;
            var plan = baseApplied ? BuildBase(current, form, baseReq) : BuildForm(current, form, initialFormType, shape, baseReq, baseStatus);
            plan.ApplyProportions(current);
            plan.ApplyContourAndEmission(current);
            return plan;
        }

        static FormRenderPlan BuildForm(SceneParams current, string form, string initialFormType, ShapeResolution shape, string baseReq, string baseStatus)
        {
            bool shapeModel = shape?.Model != null && form == initialFormType;
            RenderedColor.BaseSrgb(current.GetNumber("material.color.h"), current.GetNumber("material.color.s"),
                current.GetNumber("material.color.l"), out double r, out double g, out double b);
            float opacity = (float)current.GetNumber("material.opacity");
            FormPreset preset;
            if (shapeModel) preset = ShapePreset;
            else FormPresets.TryGetValue(form ?? "", out preset);
            string renderer = shapeModel ? RendererShapeModel : RendererFor(form);
            bool fragments = renderer == RendererFragments;
            bool mist = renderer == RendererMist;
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            return new FormRenderPlan
            {
                BaseRequested = baseReq,
                BaseStatus = baseStatus,
                Renderer = renderer,
                FormType = form,
                ShapeModel = shapeModel ? shape.Model : null,
                ShapeApplied = shapeModel ? shape.Applied : null,
                ColorR = (float)r, ColorG = (float)g, ColorB = (float)b,
                Opacity = opacity,
                Brightness = (float)current.GetNumber("material.brightness"),
                Roughness = (float)current.GetNumber("material.roughness"),
                Erosion = (float)current.GetNumber("material.erosion"),
                Fade = RenderedColor.UsesFadeShader(form, opacity),
                Preset = preset,
                ZeroDisplacement = shapeModel || fragments,
                FragmentPieces = fragments ? FragmentMesh.DefaultPieces : 0,
                FragmentSeed = fragments ? FragmentMesh.DefaultSeed : 0,
                FragmentRule = fragments ? FragmentMesh.RuleVersion : null,
                MistRule = mist ? MistLumps.RuleVersion : null,
                MistSeed = mist ? MistLumps.DefaultSeed : 0,
                PresetNote = fragments
                    ? $"form.type=fragments: 형상 프리셋 기본값 — 각진 조각 {FragmentMesh.DefaultPieces}개를 합친 메시 하나" +
                      $"(조각 규칙 {FragmentMesh.RuleVersion}, seed {FragmentMesh.DefaultSeed}, 배치 반경 비율 {R3(FragmentMesh.PlacementRadiusRatio)}, " +
                      $"조각 크기 비율 {R3(FragmentMesh.PieceSizeMinRatio)}–{R3(FragmentMesh.PieceSizeMaxRatio)}, " +
                      $"평면 음영, 정점 변위 0, 노이즈 크기 {preset.NoiseScale.ToString(inv)})"
                    : renderer == RendererMist
                    ? $"form.type=mist: 형상 프리셋 기본값 — 구 대리 메시 + 레이마칭 {MistSteps}걸음, 둥근 덩어리 {MistLumps.Count}개(배치 규칙 {MistLumps.RuleVersion}, " +
                      $"seed {MistLumps.DefaultSeed}) + 중간 주파수 노이즈(겉면 흔들림 {preset.Lumpiness.ToString(inv)}, 노이즈 크기 {preset.NoiseScale.ToString(inv)}), " +
                      $"밀도 {preset.Density.ToString(inv)}(광학 두께 배율. 덩어리 속 알파는 opacity 가까이까지 차고 opacity를 넘지 않음). " +
                      "mist에서 material.roughness는 표면 반사(광택)가 아니라 밀도 노이즈 크기 배율(0.7–1.3)과 색 얼룩 세기를 정함"
                    : null,
            };
        }

        /// <summary>(2.2) 기본 형상 계획: 모양 모형과 같은 셰이더·프리셋(정점 변위 0, 굴곡 0 — 윤곽 유지, docs/asset-plan.md 2-4절).
        /// 색·밝기·투명도·거칠기·침식 슬롯은 다른 형상과 같은 식으로 들어간다(G22).</summary>
        static FormRenderPlan BuildBase(SceneParams current, string form, string shape)
        {
            RenderedColor.BaseSrgb(current.GetNumber("material.color.h"), current.GetNumber("material.color.s"),
                current.GetNumber("material.color.l"), out double r, out double g, out double b);
            float opacity = (float)current.GetNumber("material.opacity");
            var defaultsUsed = new List<string>();
            var variant = BaseShapes.Resolve(shape, current.CurrentBaseVariant, defaultsUsed, null);
            string rule = BaseShapeMesh.RuleFor(shape);
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            var pars = BaseShapeMesh.Parameters(shape, variant);
            string vtext = variant.Count == 0 ? "변형 없음" : string.Join(", ", System.Linq.Enumerable.Select(variant, kv =>
                kv.Key + "=" + kv.Value + (defaultsUsed.Contains(kv.Key) ? "(기본값)" : "")));
            string ptext = string.Join(", ", System.Linq.Enumerable.Select(pars, kv => kv.Key + " " + kv.Value.ToString(inv)));
            return new FormRenderPlan
            {
                BaseRequested = shape,
                BaseStatus = BaseApplied,
                BaseShape = shape,
                BaseRule = rule,
                BaseVariant = variant,
                BaseVariantDefaults = defaultsUsed,
                BaseSeed = BaseShapeMesh.DefaultSeed,
                Renderer = RendererBasePrefix + shape,
                FormType = form,
                ColorR = (float)r, ColorG = (float)g, ColorB = (float)b,
                Opacity = opacity,
                Brightness = (float)current.GetNumber("material.brightness"),
                Roughness = (float)current.GetNumber("material.roughness"),
                Erosion = (float)current.GetNumber("material.erosion"),
                Fade = RenderedColor.UsesFadeShader(form, opacity),
                Preset = ShapePreset,
                ZeroDisplacement = true,
                PresetNote = $"form.base={shape}: 형상 프리셋 기본값 — 절차 메시(규칙 {rule}, {vtext}, seed {BaseShapeMesh.DefaultSeed}" +
                             (ptext.Length > 0 ? ", " + ptext : "") + "). 윤곽만(색·무늬·발광·고유 움직임 없음), 정점 변위 0, " +
                             $"노이즈 크기 {ShapePreset.NoiseScale.ToString(inv)}(거칠기 얼룩·침식 무늬). 경계 상자 가장 긴 변 1 × 기본 크기",
            };
        }

        /// <summary>(2.2) 기본 형상 판정(계획 JSON의 base). 기본 형상이 없으면 null.</summary>
        public JObject BaseJson()
        {
            if (BaseRequested == null) return null;
            var o = new JObject
            {
                ["requested"] = BaseRequested,
                ["status"] = BaseStatus,
                ["shape"] = BaseShape,
                ["rule"] = BaseRule,
            };
            if (BaseVariant != null)
            {
                var v = new JObject();
                foreach (var kv in BaseVariant) v[kv.Key] = kv.Value;
                o["variant"] = v;
                o["variantDefaults"] = new JArray(System.Linq.Enumerable.ToArray(BaseVariantDefaults));
                o["seed"] = BaseSeed;
                var p = new JObject();
                foreach (var kv in BaseShapeMesh.Parameters(BaseShape, BaseVariant)) p[kv.Key] = System.Math.Round(kv.Value, 5);
                o["parameters"] = p;
            }
            return o;
        }

        /// <summary>form.type → 렌더러 이름. 모르는 값은 그 이름 그대로(로더가 프리셋 없음으로 그린다).</summary>
        public static string RendererFor(string formType)
        {
            switch (formType)
            {
                case "mist": return RendererMist;
                case "shell": return RendererShell;
                case "fragments": return RendererFragments;
                case "blob": return RendererBlob;
                default: return formType;
            }
        }

        static double R(float v) => System.Math.Round(v, 5);
        static string R3(double v) => System.Math.Round(v, 3).ToString(System.Globalization.CultureInfo.InvariantCulture);

        /// <summary>fragments 조각 생성 규칙(버전·주요 매개변수). fragments가 아니면 null.
        /// 같은 seed라도 규칙이 바뀌면 메시가 달라지므로 계획 JSON에 함께 남긴다.</summary>
        public JObject FragmentRuleJson() => FragmentRule == null ? null : new JObject
        {
            ["version"] = FragmentRule,
            ["pieces"] = FragmentPieces,
            ["seed"] = FragmentSeed,
            ["placementRadiusRatio"] = System.Math.Round(FragmentMesh.PlacementRadiusRatio, 5),
            ["pieceSizeRatioRange"] = new JArray(System.Math.Round(FragmentMesh.PieceSizeMinRatio, 5), System.Math.Round(FragmentMesh.PieceSizeMaxRatio, 5)),
        };

        /// <summary>mist 덩어리 배치 규칙(버전·seed·덩어리 중심과 반지름). mist가 아니면 null.
        /// 같은 seed라도 규칙이 바뀌면 구름 모양이 달라지므로 계획 JSON에 함께 남긴다.</summary>
        public JObject MistRuleJson()
        {
            if (MistRule == null) return null;
            var lumps = new JArray();
            var l = MistLumps.Build(MistSeed);
            for (int k = 0; k < l.Length / 4; k++)
                lumps.Add(new JArray(System.Math.Round(l[k * 4], 5), System.Math.Round(l[k * 4 + 1], 5), System.Math.Round(l[k * 4 + 2], 5), System.Math.Round(l[k * 4 + 3], 5)));
            return new JObject { ["version"] = MistRule, ["seed"] = MistSeed, ["lumps"] = lumps };
        }

        /// <summary>계획 전체(비교·기록용). 키 순서가 고정이라 문자열 비교로 같은 계획인지 볼 수 있다.
        /// 기본 형상(2.2)이 있을 때만 끝에 "base"를 붙인다(2.0·2.1 spec의 계획 JSON은 그대로).</summary>
        public JObject ToJson()
        {
            var o = CoreJson();
            var b = BaseJson();
            if (b != null) o["base"] = b;
            // (2.3) 윤곽·발광 슬롯이 있을 때만(2.0–2.2 spec의 계획 JSON은 그대로)
            if (HasContour)
            {
                o["contour"] = ContourJson();
                o["emission"] = EmissionJson();
            }
            // (2.4) 비율이 주어졌을 때만(spec null·덮어쓰기 없음이면 2.3과 같은 계획 JSON)
            if (Proportions != null) o["proportions"] = ProportionsJson();
            return o;
        }

        JObject CoreJson() => new JObject
        {
            ["renderer"] = Renderer,
            ["formType"] = FormType,
            ["shapeModel"] = ShapeModel,
            ["shapeApplied"] = ShapeApplied,
            ["color"] = new JArray(R(ColorR), R(ColorG), R(ColorB)),
            ["opacity"] = R(Opacity),
            ["brightness"] = R(Brightness),
            ["roughness"] = R(Roughness),
            ["erosion"] = R(Erosion),
            ["fade"] = Fade,
            ["preset"] = new JObject
            {
                ["lumpiness"] = R(Preset.Lumpiness), ["noiseScale"] = R(Preset.NoiseScale), ["fuzz"] = R(Preset.Fuzz),
                ["density"] = R(Preset.Density), ["shellOpen"] = R(Preset.ShellOpen),
            },
            ["zeroDisplacement"] = ZeroDisplacement,
            ["fragmentPieces"] = FragmentPieces,
            ["fragmentSeed"] = FragmentSeed,
            ["fragmentRule"] = FragmentRuleJson(),
            ["mistSteps"] = Renderer == RendererMist ? MistSteps : 0,
            ["mistRule"] = MistRuleJson(),
        };
    }

    /// <summary>
    /// 안개 구가 바닥과 겹치는가(G4). SceneSpecMist는 바닥 높이(_FloorY) 아래 표본의 밀도를 0으로 자르므로(화면은 그대로),
    /// 레이마칭 구(물체 좌표 반지름 FormRenderResources.MistRadius)의 세계 높이 범위가 바닥 아래로 걸치면 그 사실과 잘린 높이 비율을 남긴다.
    /// 실제 밀도는 그 구의 약 0.65배 안쪽에서 풀리므로 잘린 비율은 구 기준(상한)이다. UnityEngine에 의존하지 않는다.
    /// </summary>
    public sealed class MistFloorClip
    {
        public double FloorY { get; private set; }
        /// <summary>레이마칭 구의 세계 높이 범위(아래·위).</summary>
        public double BottomY { get; private set; }
        public double TopY { get; private set; }
        /// <summary>구의 아래 끝이 바닥보다 낮은가.</summary>
        public bool FloorClipped { get; private set; }
        /// <summary>바닥 아래로 잘린 높이 / 구의 세계 높이(0–1). 잘리지 않으면 0.</summary>
        public double ClippedHeightFraction { get; private set; }

        MistFloorClip() { }

        /// <summary>centerY = 구 중심의 세계 높이, halfHeight = 구의 세계 세로 반높이(반지름 × 물체→세계 행렬 y행의 길이), floorY = 바닥 높이.</summary>
        public static MistFloorClip Measure(double centerY, double halfHeight, double floorY)
        {
            var c = new MistFloorClip { FloorY = floorY, BottomY = centerY - halfHeight, TopY = centerY + halfHeight };
            if (halfHeight > 0 && c.BottomY < floorY)
            {
                c.FloorClipped = true;
                c.ClippedHeightFraction = System.Math.Min(1.0, (floorY - c.BottomY) / (2.0 * halfHeight));
            }
            return c;
        }

        /// <summary>로더 notes에 넣는 문장(잘렸을 때만 쓴다).</summary>
        public string Note()
        {
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            return $"form.type=mist: 안개 구(세계 높이 {System.Math.Round(BottomY, 3).ToString(inv)}–{System.Math.Round(TopY, 3).ToString(inv)})가 " +
                   $"바닥 높이 {System.Math.Round(FloorY, 3).ToString(inv)} 아래로 걸쳐 바닥 아래 밀도를 0으로 자름" +
                   $"(잘린 높이 비율 {System.Math.Round(ClippedHeightFraction, 3).ToString(inv)}, 구 기준 상한. 화면 처리는 그대로)";
        }

        public JObject ToJson() => new JObject
        {
            ["floorClipped"] = FloorClipped,
            ["clippedHeightFraction"] = System.Math.Round(ClippedHeightFraction, 5),
            ["floorY"] = System.Math.Round(FloorY, 5),
            ["sphereBottomY"] = System.Math.Round(BottomY, 5),
            ["sphereTopY"] = System.Math.Round(TopY, 5),
            ["method"] = "레이마칭 구(물체 좌표 반지름 0.75)의 세계 높이 범위 vs 배치 설정 바닥 높이(_FloorY). " +
                         "잘린 높이 비율 = (바닥 − 구 아래 끝) / 구 높이. 실제 밀도는 구 안쪽에서 풀리므로 상한",
        };
    }
}
