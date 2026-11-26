// (2.3, G61 ①) 윤곽·발광 슬롯의 닫힌 값 목록과 렌더 수치 — docs/scene-spec-mapping.md 8.2·8.4·8.5절.
//   form.roundness  → 슈퍼쿼드릭 지수 (e1, e2)       form.aspect → 축 비율 (x, y, z), 긴 축 = 1, 긴 축 방향 = 세로 y(기본값)
//   material.emission → 발광 세기(바탕색에 곱함, 새 색 없음, 블룸 없음)
// 수치의 원본은 shared/lexicon/scene_params.v3.json의 render 절이다. Quest(Android)는 StreamingAssets 밖 파일을 읽을 수 없고
// 기존 표(BaseShapes·ShapeMapping)도 C# 표 + pytest 대조로 묶으므로 같은 관례를 따른다: 아래 표의 값·순서를
// chatbot/tests/test_g61_unity_contour.py가 render 절·스키마 scene-spec.v2.3.json의 enum과 대조한다(어긋나면 실패).
// 수치를 바꾸려면 scene_params.v3.json을 고치고(lexiconVersion 올림) 이 표와 ParamsVersion을 같이 고친다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public static class ContourRender
    {
        public const string RoundnessKey = "form.roundness";
        public const string AspectKey = "form.aspect";
        public const string EmissionKey = "material.emission";
        /// <summary>defaultsUsed에 남기는 키: 길쭉함·납작함의 긴 축 방향(참여자가 말하지 않음 → 세로 y).</summary>
        public const string AspectAxisKey = "form.aspect.axis";

        /// <summary>이 표가 옮겨 적은 수치 파일(scene_params.v3.json의 lexiconId/lexiconVersion).</summary>
        public const string ParamsVersion = "scene-params-v3/0.1.0";
        /// <summary>슈퍼쿼드릭 메시 규칙 버전(계획 JSON·기록의 contour.mesh). 메시를 바꾸면 올린다.</summary>
        public const string MeshRule = "superquadric/1";
        /// <summary>윤곽을 적용했지만 둥긂을 말하지 않아 기본 덩어리 메시를 그대로 쓸 때의 contour.mesh.</summary>
        public const string MeshDefault = "default";
        /// <summary>render.contour.aspectAxisDefault.</summary>
        public const string AspectAxisDefault = "y";
        /// <summary>render.contour.mesh: 지름 1(반축 0.5), 경도 48칸 × 위도 24칸.</summary>
        public const double UnitDiameter = 1.0;
        public const int LongitudeSegments = 48;
        public const int LatitudeSegments = 24;

        // 윤곽 판정(계획 JSON·기록의 contour.status). docs/scene-spec-mapping.md 8.4절 2번의 적용 순서.
        public const string StatusApplied = "applied";
        public const string StatusNotAppliedForm = "not_applied_form";
        public const string StatusNotAppliedBase = "not_applied_base";
        public const string StatusNotAppliedModel = "not_applied_model";
        public const string StatusNone = "none";

        /// <summary>form.roundness 단계(왼쪽부터 서수 순서, 스키마 enum과 같은 순서) → (e1, e2). render.contour.superquadric.</summary>
        public static readonly string[] RoundnessLevels = { "angular", "slightly_angular", "neutral", "slightly_rounded", "rounded" };
        static readonly double[] RoundnessExponent = { 0.1, 0.3, 0.5, 0.75, 1.0 };

        /// <summary>form.aspect 단계 → (x, y, z) 배율. render.contour.aspectRatios.</summary>
        public static readonly string[] AspectLevels = { "elongated", "slightly_elongated", "neutral", "slightly_flattened", "flattened" };
        static readonly double[][] AspectRatio =
        {
            new[] { 0.5, 1.0, 0.5 }, new[] { 0.75, 1.0, 0.75 }, new[] { 1.0, 1.0, 1.0 }, new[] { 1.0, 0.7, 1.0 }, new[] { 1.0, 0.4, 1.0 },
        };

        /// <summary>material.emission 단계 → 세기. render.emission.intensity.</summary>
        public static readonly string[] EmissionLevels = { "none", "faint", "glowing" };
        static readonly double[] EmissionIntensityTable = { 0.0, 0.35, 1.0 };

        public static bool IsRoundness(string v) => v != null && Array.IndexOf(RoundnessLevels, v) >= 0;
        public static bool IsAspect(string v) => v != null && Array.IndexOf(AspectLevels, v) >= 0;
        public static bool IsEmission(string v) => v != null && Array.IndexOf(EmissionLevels, v) >= 0;

        /// <summary>둥긂 단계의 슈퍼쿼드릭 지수. 두 지수를 같게 둔다(말한 것은 '둥긂 정도' 하나). 모르는 값이면 ArgumentException.</summary>
        public static (double e1, double e2) Exponents(string roundness)
        {
            int i = Array.IndexOf(RoundnessLevels, roundness);
            if (i < 0) throw new ArgumentException("모르는 form.roundness: " + roundness);
            return (RoundnessExponent[i], RoundnessExponent[i]);
        }

        /// <summary>길쭉함 단계의 (x, y, z) 축 배율(새 배열). 모르는 값이면 ArgumentException.</summary>
        public static double[] AxisRatios(string aspect)
        {
            int i = Array.IndexOf(AspectLevels, aspect);
            if (i < 0) throw new ArgumentException("모르는 form.aspect: " + aspect);
            return (double[])AspectRatio[i].Clone();
        }

        /// <summary>발광 단계의 세기. 모르는 값이면 ArgumentException.</summary>
        public static double EmissionIntensity(string emission)
        {
            int i = Array.IndexOf(EmissionLevels, emission);
            if (i < 0) throw new ArgumentException("모르는 material.emission: " + emission);
            return EmissionIntensityTable[i];
        }

        /// <summary>슬롯 경로 → 허용 값(스키마 enum의 null 아닌 값). 파서·덮어쓰기 검사가 같이 쓴다.</summary>
        public static readonly IReadOnlyDictionary<string, string[]> Levels = new Dictionary<string, string[]>(StringComparer.Ordinal)
        {
            { RoundnessKey, RoundnessLevels }, { AspectKey, AspectLevels }, { EmissionKey, EmissionLevels },
        };

        /// <summary>(2.3) 세 슬롯 경로(SceneSpecJson.SlotPaths·BaseSlotPaths와 따로 둔다 — 2.0–2.2 검사·기록이 그대로).</summary>
        public static readonly string[] SlotPaths = { RoundnessKey, AspectKey, EmissionKey };
    }
}
