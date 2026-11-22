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

        /// <summary>형태별 프리셋. 값을 바꾸면 OwnershipVariantGenerator의 밀도 표·unity/README.md도 같이 본다.</summary>
        public static readonly IReadOnlyDictionary<string, FormPreset> FormPresets = new Dictionary<string, FormPreset>
        {
            { "blob", new FormPreset(0.14f, 1.6f, 0f, 1f, 0f) },
            { "mist", new FormPreset(0.30f, 1.1f, 1f, 0.5f, 0f) },
            { "shell", new FormPreset(0.04f, 2.0f, 0f, 1f, 0.35f) },
            { "fragments", new FormPreset(0.25f, 2.4f, 0f, 1f, 0f) },
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
        /// <summary>정점 변위 0(모양 모형: 각진 면이 벌어지지 않게).</summary>
        public bool ZeroDisplacement { get; private set; }

        FormRenderPlan() { }

        /// <summary>
        /// current = 지금 적용할 값, initialFormType = 처음 로드 때의 form.type, shape = 모양어 판정(없으면 null).
        /// 모양 모형은 판정이 모형을 정했고 참여자가 form.type을 처음 값에서 바꾸지 않았을 때만 쓴다
        /// (조정 중 form.type을 바꾸면 그 형태 모형, 처음 값으로 돌아오면 다시 모양 모형).
        /// </summary>
        public static FormRenderPlan Build(SceneParams current, string initialFormType, ShapeResolution shape)
        {
            string form = current.GetCategory("form.type");
            bool shapeModel = shape?.Model != null && form == initialFormType;
            RenderedColor.BaseSrgb(current.GetNumber("material.color.h"), current.GetNumber("material.color.s"),
                current.GetNumber("material.color.l"), out double r, out double g, out double b);
            float opacity = (float)current.GetNumber("material.opacity");
            FormPreset preset;
            if (shapeModel) preset = ShapePreset;
            else FormPresets.TryGetValue(form ?? "", out preset);
            return new FormRenderPlan
            {
                Renderer = shapeModel ? RendererShapeModel : RendererFor(form),
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
                ZeroDisplacement = shapeModel,
            };
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

        /// <summary>계획 전체(비교·기록용). 키 순서가 고정이라 문자열 비교로 같은 계획인지 볼 수 있다.</summary>
        public JObject ToJson() => new JObject
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
        };
    }
}
