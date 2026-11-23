// 놓기 도움(G53)의 화면 규칙(UnityEngine 무의존 — dotnet 테스트에서도 확인). 그리기는 PlacementSpace.SetAssist·SetPractice.
//   경계 띠 밝기: 든 물체의 수평 거리 d가 바닥 반지름 R에서 bandM 안으로 들어오면 0 → 1(smoothstep). 바닥 밖으로는 clamp라 R에서 1.
//   바닥 고리 반지름: 물체 렌더 경계 반지름과 최소값 중 큰 값(작은 물체도 고리가 보이게).
using System;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementAssistVisuals
    {
        /// <summary>경계 띠가 밝아지기 시작하는 가장자리 안쪽 거리(m).</summary>
        public const double GlowBandM = 1.0;
        /// <summary>바닥 고리의 최소 반지름(m).</summary>
        public const double MinContactRingM = 0.12;

        /// <summary>0(원래 색) … 1(가장 밝음).</summary>
        public static double BoundaryGlow(double horizontalDistanceM, double floorRadiusM, double bandM = GlowBandM)
        {
            if (!(bandM > 0) || double.IsNaN(horizontalDistanceM) || double.IsNaN(floorRadiusM)) return 0;
            double t = (horizontalDistanceM - (floorRadiusM - bandM)) / bandM;
            t = Math.Min(1, Math.Max(0, t));
            return t * t * (3 - 2 * t);
        }

        public static double ContactRingRadius(double objectRadiusM) =>
            double.IsNaN(objectRadiusM) ? MinContactRingM : Math.Max(MinContactRingM, objectRadiusM);
    }
}
