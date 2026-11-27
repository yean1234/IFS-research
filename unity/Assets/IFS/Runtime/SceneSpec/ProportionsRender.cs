// (2.4, G72) x·y·z 비율(layout.proportions) — 규칙과 렌더 수치. 넓게 펼쳐진 안개·길쭉한 돌처럼 너비·높이·깊이를 따로 말한 경우.
//   값: null | {x, y, z, axisSaid}. x = 너비(참여자가 물체를 마주 볼 때 왼쪽–오른쪽 = 물체 국소 x), y = 높이(국소 y, 위),
//   z = 깊이(국소 z, 참여자 쪽–먼 쪽). 각 0.2–1, 가장 큰 값 = 1. axisSaid = false면 긴 축·짧은 축 방향을 말하지 않았다는 뜻이고
//   값은 기준 틀(길쭉 → y가 긺, 납작 → y가 짧음 = 렌더러 기본 방향)로 적혀 있다 → 렌더러가 defaultsUsed에 layout.proportions.axis를 더한다.
// 덮어쓰기(selection.json finalOverrides·WebGL 미리보기)는 축마다 layout.proportions.x·y·z(0.2–2.0, 참여자 조절 화면 원값 —
// 단계 0.25·0.35·0.5·0.7·1.0·1.4·2.0. 한 축만 올리면 그 축이 가장 길어지고 나머지가 상대적으로 줄어든다)이다. 덮어쓰지 않은 축은 spec 값
// (0.2–1, null이면 1.0)을 원값으로 쓴다. 렌더러는 유효 비율 p = clamp(원값 / 가장 큰 원값, 0.2, 1)을 쓴다(0.2 아래는 0.2로 올리고 notes에 남김).
// 가장 긴 변 규칙(G62-e): layout.size는 그대로 '가장 긴 변'을 뜻한다. 비율을 바꿔도 가장 긴 변은 바뀌지 않고 크기만 그것을 정한다.
//   L0 = 비율 없이(크기 배율 × 자세 × 해당하면 축 비율) 모형 국소 경계의 가장 긴 변, L1 = 비율을 곱한 뒤의 가장 긴 변,
//   최종 국소 배율 = (국소 배율 ∘ q) × (L0 / L1). 메시 형상은 q = p(비균일 배율), fragments는 조각 배치(중심 오프셋)를 p로 늘이고 q = (1, 1, 1).
// 경계는 정점으로 잰다(SceneLoader.ProceduralLocalBounds — mesh.bounds는 IcoMesh에서 1.6으로 넉넉히 잡혀 있다).
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 같은 입력이면 언제나 같은 값이다.
using System;

namespace IFS.SceneSpec
{
    public static class ProportionsRender
    {
        /// <summary>스펙 슬롯 경로(_provenance 키·selection.json sources 슬롯 이름·defaultsUsed 키).</summary>
        public const string Key = "layout.proportions";
        public const string XKey = "layout.proportions.x";
        public const string YKey = "layout.proportions.y";
        public const string ZKey = "layout.proportions.z";
        /// <summary>SceneParams·덮어쓰기의 축별 수치 키(x, y, z 순서).</summary>
        public static readonly string[] AxisKeys = { XKey, YKey, ZKey };
        /// <summary>defaultsUsed에 남기는 키: 긴 축·짧은 축 방향을 말하지 않음(axisSaid = false) → 기준 틀(렌더러 기본 방향)로 그림.</summary>
        public const string AxisKey = "layout.proportions.axis";

        /// <summary>스펙 값 한 축의 허용 범위(가장 큰 값 = 1). 유효 비율도 이 범위로 자른다.</summary>
        public const double Min = 0.2, Max = 1.0;
        /// <summary>덮어쓰기 원값 한 축의 허용 범위(조절 화면 단계 0.25–2.0을 담는다). 밖이면 거부.</summary>
        public const double RawMin = 0.2, RawMax = 2.0;
        /// <summary>가장 큰 값 = 1 검사의 허용 오차.</summary>
        public const double MaxTolerance = 1e-6;
        /// <summary>렌더 규칙 버전(계획 JSON proportions.rule). 규칙을 바꾸면 올린다.</summary>
        public const string RuleVersion = "longest-edge/1";
        /// <summary>계획 JSON proportions.method: 메시 형상은 국소 배율, fragments는 조각 배치.</summary>
        public const string MethodLocalScale = "local_scale";
        public const string MethodFragmentDistribution = "fragment_distribution";

        public static bool IsAxisKey(string key) => key == XKey || key == YKey || key == ZKey;

        /// <summary>스펙 값 한 축이 허용 범위(0.2–1) 안인가.</summary>
        public static bool InRange(double v) => !double.IsNaN(v) && v >= Min - 1e-12 && v <= Max + 1e-12;
        /// <summary>덮어쓰기 원값 한 축이 허용 범위(0.2–2.0) 안인가.</summary>
        public static bool InRawRange(double v) => !double.IsNaN(v) && v >= RawMin - 1e-12 && v <= RawMax + 1e-12;

        /// <summary>스펙 값을 0.2–1로 자른다.</summary>
        public static double Clamp(double v) => double.IsNaN(v) ? Max : (v < Min ? Min : (v > Max ? Max : v));
        /// <summary>원값을 0.2–2.0으로 자른다(SceneParams.SetNumber).</summary>
        public static double ClampRaw(double v) => double.IsNaN(v) ? Max : (v < RawMin ? RawMin : (v > RawMax ? RawMax : v));

        /// <summary>원값 (x, y, z) → 유효 비율 p = clamp(원값 / 가장 큰 값, 0.2, 1)(가장 큰 값 = 1). 새 배열.</summary>
        public static double[] Normalize(double x, double y, double z) => Normalize(x, y, z, out _);

        /// <summary>clamped = 0.2 아래라 0.2로 올린 축이 있는가(notes에 남긴다).</summary>
        public static double[] Normalize(double x, double y, double z, out bool clamped)
        {
            clamped = false;
            double m = Math.Max(x, Math.Max(y, z));
            if (!(m > 0)) return new[] { 1.0, 1.0, 1.0 };
            var r = new[] { x / m, y / m, z / m };
            for (int k = 0; k < 3; k++)
                if (r[k] < Min) { r[k] = Min; clamped = true; }
            return r;
        }

        /// <summary>가장 긴 변 = max_k(경계[k] × |배율[k]|).</summary>
        public static double LongestEdge(double[] size, double[] scale)
        {
            double l = 0;
            for (int k = 0; k < 3; k++) l = Math.Max(l, size[k] * Math.Abs(scale[k]));
            return l;
        }

        /// <summary>
        /// 가장 긴 변 규칙. size0 = 비율을 넣지 않은 모형 국소 경계, size1 = 지금 메시의 국소 경계(fragments는 조각 배치를 늘인 메시, 그 밖에는 size0),
        /// local0 = 비율 없는 국소 배율, q = 국소 배율에 곱할 축 배율(메시 형상 p, fragments (1, 1, 1)).
        /// 최종 국소 배율 = local0 ∘ q × (L0 / L1). L0 = 가장 긴 변(size0, local0), L1 = 가장 긴 변(size1, local0 ∘ q).
        /// </summary>
        public static double[] FitLocalScale(double[] size0, double[] size1, double[] local0, double[] q, out double l0, out double l1)
        {
            var lq = new[] { local0[0] * q[0], local0[1] * q[1], local0[2] * q[2] };
            l0 = LongestEdge(size0, local0);
            l1 = LongestEdge(size1, lq);
            double f = l1 > 1e-12 ? l0 / l1 : 1.0;
            return new[] { lq[0] * f, lq[1] * f, lq[2] * f };
        }
    }
}
