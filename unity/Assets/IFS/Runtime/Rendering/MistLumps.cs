// mist 형상의 밀도장 뼈대(D7, 2026-11-23): 둥근 덩어리 여러 개가 겹친 구름 모양.
// 덩어리 중심·반지름은 seed로 정한다(같은 seed → 같은 배치). 셰이더(SceneSpecMist)는 이 값을 머티리얼 벡터(_Lump0…)로 받아
// "덩어리 합집합(가장 깊이 들어간 덩어리 기준) + 중간 주파수 노이즈" 밀도를 8걸음 레이마칭으로 쌓는다.
// 덩어리 수·배치·seed는 형상 프리셋 기본값이다(참여자가 말한 값이 아님). 규칙을 바꾸면 같은 seed라도 모양이 달라지므로 RuleVersion을 올린다.
// 좌표는 물체 좌표(안개 대리 구 반지름 FormRenderResources.MistRadius = 0.75 기준). 덩어리 + 노이즈 여유가 대리 구 밖으로 나가지 않게 둔다.
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 난수는 자체 구현(SplitMix64, FragmentMesh와 같은 식)이라 런타임이 달라도 같은 수열이다.
using System;

namespace IFS.SceneSpec
{
    public static class MistLumps
    {
        /// <summary>덩어리 배치 규칙 버전. 계획 JSON(renderPlan.mistRule)·로더 notes에 남긴다. 규칙을 바꾸면 올린다(MistLumpsTests가 기본 배치를 이 버전에 묶어 둔다).</summary>
        public const string RuleVersion = "lumps5/1";
        /// <summary>형상 프리셋 기본값: 덩어리 수(셰이더 IFS_MIST_LUMPS와 같아야 한다 — 테스트가 확인).</summary>
        public const int Count = 5;
        /// <summary>형상 프리셋 기본값: seed(spec과 무관한 고정값 → 같은 spec이면 같은 구름).</summary>
        public const int DefaultSeed = 0;

        /// <summary>덩어리 하나가 차지하는 끝(중심 거리 + 반지름)의 상한. 대리 구 반지름 0.75에서 셰이더의 노이즈 여유(가장자리를
        /// 최대 약 0.08 밀어냄)를 뺀 값이라 구름이 대리 구 표면에서 잘린 원으로 보이지 않는다.</summary>
        public const double MaxExtent = 0.64;

        // 가운데 덩어리(조금 아래)와 둘레 4개. 둘레는 90°씩 돌린 자리에서 seed로 흔들고, 번갈아 높낮이를 준다(위로 솟은 덩이 + 옆으로 퍼진 덩이).
        const double CoreY = -0.04, CoreRMin = 0.33, CoreRMax = 0.37;
        const double RingRhoMin = 0.25, RingRhoMax = 0.33;
        const double RingAngleJitterDeg = 22.0;
        const double RingRMin = 0.20, RingRMax = 0.28;
        static readonly double[] RingY = { 0.12, -0.07, 0.15, -0.04 };   // 둘레 덩이의 기본 높이(번갈아 위·아래)
        const double RingYJitter = 0.04;

        /// <summary>
        /// 덩어리 Count개: 배열 길이 Count × 4 = (x, y, z, r)… 물체 좌표. 0번이 가운데 덩어리.
        /// 같은 seed는 언제나 같은 배열을 낸다.
        /// </summary>
        public static double[] Build(int seed)
        {
            var rng = new SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0x51ED270BUL);
            var lumps = new double[Count * 4];
            lumps[0] = rng.Range(-0.02, 0.02);
            lumps[1] = CoreY;
            lumps[2] = rng.Range(-0.02, 0.02);
            lumps[3] = rng.Range(CoreRMin, CoreRMax);
            double turn = rng.Range(0.0, 360.0);   // 둘레 전체를 seed로 돌린다(정면에서 보이는 겹침이 seed마다 다르게)
            for (int k = 1; k < Count; k++)
            {
                double ang = (turn + (k - 1) * 90.0 + rng.Range(-RingAngleJitterDeg, RingAngleJitterDeg)) * Math.PI / 180.0;
                double rho = rng.Range(RingRhoMin, RingRhoMax);
                double x = rho * Math.Cos(ang), z = rho * Math.Sin(ang);
                double y = RingY[(k - 1) % RingY.Length] + rng.Range(-RingYJitter, RingYJitter);
                double r = rng.Range(RingRMin, RingRMax);
                // 끝이 MaxExtent를 넘으면 반지름을 줄인다(중심은 그대로)
                double reach = Math.Sqrt(x * x + y * y + z * z);
                if (reach + r > MaxExtent) r = Math.Max(0.12, MaxExtent - reach);
                lumps[k * 4] = x; lumps[k * 4 + 1] = y; lumps[k * 4 + 2] = z; lumps[k * 4 + 3] = r;
            }
            return lumps;
        }

        /// <summary>덩어리 합집합의 끝(원점에서 가장 먼 덩어리 겉면까지의 거리).</summary>
        public static double Extent(double[] lumps)
        {
            double max = 0;
            for (int k = 0; k < lumps.Length / 4; k++)
            {
                double x = lumps[k * 4], y = lumps[k * 4 + 1], z = lumps[k * 4 + 2];
                max = Math.Max(max, Math.Sqrt(x * x + y * y + z * z) + lumps[k * 4 + 3]);
            }
            return max;
        }

        /// <summary>
        /// 노이즈를 뺀 밀도장의 뼈대(셰이더 mistShape와 같은 식): 가장 깊이 들어간 덩어리 기준 깊이 f = max_i(r_i − |p − c_i|),
        /// 밀도 = saturate(f / EdgeRamp). 셰이더는 여기에 노이즈를 더한다. 테스트·문서용(렌더에는 셰이더 식이 쓰인다).
        /// </summary>
        public static double ShapeDensity(double[] lumps, double x, double y, double z)
        {
            double f = double.NegativeInfinity;
            for (int k = 0; k < lumps.Length / 4; k++)
            {
                double dx = x - lumps[k * 4], dy = y - lumps[k * 4 + 1], dz = z - lumps[k * 4 + 2];
                f = Math.Max(f, lumps[k * 4 + 3] - Math.Sqrt(dx * dx + dy * dy + dz * dz));
            }
            return Math.Max(0.0, Math.Min(1.0, f / EdgeRamp));
        }

        /// <summary>덩어리 겉면에서 안쪽으로 밀도가 0 → 1로 오르는 폭(물체 좌표). 셰이더 IFS_MIST_EDGE_RAMP와 같아야 한다.</summary>
        public const double EdgeRamp = 0.10;

        /// <summary>SplitMix64 — 작은 결정적 난수(FragmentMesh와 같은 구현).</summary>
        sealed class SplitMix64
        {
            ulong _s;
            public SplitMix64(ulong seed) { _s = seed; }

            public ulong Next()
            {
                ulong z = _s += 0x9E3779B97F4A7C15UL;
                z = (z ^ (z >> 30)) * 0xBF58476D1CE4E5B9UL;
                z = (z ^ (z >> 27)) * 0x94D049BB133111EBUL;
                return z ^ (z >> 31);
            }

            public double Range(double lo, double hi) => lo + (hi - lo) * ((Next() >> 11) * (1.0 / 9007199254740992.0));
        }
    }
}
