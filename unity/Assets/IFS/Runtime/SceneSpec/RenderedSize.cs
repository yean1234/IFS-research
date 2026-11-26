// 형상의 화면 크기(순수 C#). 로더(SceneLoader.ApplyLayout)와 소유감 변형본 생성기(크기 쌍의 wM·loM·hiM)가 이 함수를 같이 쓴다
// (색의 RenderedColor와 같은 방식, docs/decisions.md X33).
//   배율   = SceneParams.SizeToScale(layout.size) = 2^((size − 0.5) × 4)
//   자세   = PostureDeform(form.posture): (x, y, z) 배율. 표에 없는 자세·none은 (1, 1, 1)
//   로컬 크기 = 기본 크기 × 배율 × 자세 배율(축마다)
//   가장 넓은 가로 폭(m) = 기본 지름 × 배율 × max(자세 x, 자세 z)
// 기본 지름은 PlacementSettings.primitiveBaseSize의 기본값(0.35 m, 절차 모형·모양 모형·프리미티브 대체가 쓰는 크기, 메시 지름 1).
// 한계: 셰이더 정점 굴곡(blob·mist), fragments의 조각 배치, 연결된 프리팹 자체 크기는 넣지 않은 명목 폭이다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public static class RenderedSize
    {
        /// <summary>배율 1일 때 형상의 명목 지름(m) = PlacementSettings.primitiveBaseSize 기본값.</summary>
        public const double NominalBaseDiameterM = 0.35;

        /// <summary>자세어 → 크기 변형(x, y, z 배율). 늘 x = z. 표에 없는 자세는 적용하지 않는다(로더가 기록).</summary>
        public static readonly IReadOnlyDictionary<string, (double x, double y, double z)> PostureTable =
            new Dictionary<string, (double, double, double)>(StringComparer.Ordinal)
            {
                { "curled", (1.15, 0.7, 1.15) }, { "crouched", (1.15, 0.7, 1.15) },
                { "cowering", (1.1, 0.7, 1.1) }, { "hunched", (1.1, 0.8, 1.1) },
                { "bowed", (1.05, 0.85, 1.05) }, { "bent", (1.05, 0.85, 1.05) },
                { "lying", (1.3, 0.5, 1.3) }, { "prone", (1.3, 0.5, 1.3) },
                { "drooping", (1.2, 0.6, 1.2) }, { "sagging", (1.2, 0.6, 1.2) },
                { "limp", (1.2, 0.6, 1.2) },
                { "standing", (0.9, 1.2, 0.9) }, { "sitting", (1.0, 0.9, 1.0) },
                { "hanging", (0.9, 1.25, 0.9) },
            };

        /// <summary>자세 배율. none·null은 (1, 1, 1)·true, 표에 없는 자세는 (1, 1, 1)·false(적용하지 않음).</summary>
        public static bool PostureDeform(string posture, out double x, out double y, out double z)
        {
            x = y = z = 1.0;
            if (posture == null || posture == SceneParams.NoPosture) return true;
            if (!PostureTable.TryGetValue(posture, out var d)) return false;
            x = d.x; y = d.y; z = d.z;
            return true;
        }

        /// <summary>가장 넓은 가로 폭(m): 기본 지름 × 2^((size − 0.5) × 4) × max(자세 x, 자세 z).</summary>
        public static double MaxHorizontalWidthM(double size, string posture, double baseDiameterM = NominalBaseDiameterM)
        {
            PostureDeform(posture, out double x, out _, out double z);
            return baseDiameterM * SceneParams.SizeToScale(size) * Math.Max(x, z);
        }
    }
}
