// fragments 형상의 메시(X67): 불규칙한 각진 조각 여러 개를 메시 하나로 합친다(드로콜 1). 평면 음영(면마다 정점을 따로 둠).
// 조각마다 정이십면체 꼭짓점을 반지름 방향으로 흔들고(각진 덩이), 축마다 늘이고 줄인 뒤(납작한 파편), 돌려서 놓는다.
// 크기·방향·흔들림은 seed로 정한다(같은 seed → 같은 메시). 조각 수·배치·seed는 형상 프리셋 기본값이다(참여자가 말한 값 아님).
// 규칙 자체를 바꾸면 같은 seed라도 메시가 달라지므로 RuleVersion을 올린다(계획 JSON·notes의 fragmentRule로 추적).
// 배치(중심)와 대략의 크기는 이전 경로(구 5개: 중심 BaseOffsets, 반지름 0.5 × (0.42 − 0.04 i))를 따라 전체 범위가 비슷하다
// → layout.size의 뜻(기본 크기 대비 배율)이 바뀌지 않는다.
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 난수는 자체 구현(SplitMix64)이라 런타임이 달라도 같은 수열이다.
using System;

namespace IFS.SceneSpec
{
    public static class FragmentMesh
    {
        /// <summary>조각 생성 규칙의 버전. 같은 seed라도 규칙(배치·크기·늘이기·흔들기·난수 순서)이 바뀌면 메시가 달라지므로
        /// 규칙을 바꿀 때 올린다(FragmentMeshTests가 기본 메시 해시를 이 버전에 묶어 둔다). 계획 JSON·로더 notes의 fragmentRule.</summary>
        public const string RuleVersion = "angular5/1";

        /// <summary>형상 프리셋 기본값: 조각 수.</summary>
        public const int DefaultPieces = 5;
        /// <summary>형상 프리셋 기본값: seed(이전 경로처럼 spec과 무관한 고정값 → 같은 spec이면 같은 메시).</summary>
        public const int DefaultSeed = 0;

        /// <summary>조각 중심. 이전 경로(구 5개)의 중심에서 2번째·4번째를 조금 옮겼다(정면에서 둘이 겹쳐 덩어리 하나로 보이지 않게).
        /// 조각이 더 많으면 seed로 정한 위치를 덧붙인다.</summary>
        static readonly double[][] BaseOffsets =
        {
            new[] { -0.38, 0.1, 0.0 }, new[] { 0.34, -0.26, 0.1 }, new[] { 0.0, 0.38, -0.1 },
            new[] { 0.2, 0.16, 0.36 }, new[] { -0.12, -0.32, -0.26 },
        };

        /// <summary>조각 크기 배율: 납작하게 늘이고 줄인 조각의 화면 넓이가 이전 구와 비슷하도록(형상 프리셋 기본값).</summary>
        const double SizeScale = 1.2;
        /// <summary>조각 기준 반지름 = SizeScale × 0.5 × (0.42 − 0.04 i) × [SizeJitterLo, SizeJitterHi).</summary>
        const double SizeJitterLo = 0.9, SizeJitterHi = 1.1;

        /// <summary>모형의 기준 반지름(구 지름 1). 아래 비율의 분모.</summary>
        public const double NominalRadius = 0.5;

        /// <summary>배치 반경 비율: 조각 중심(BaseOffsets, 흔들기 ±0.03 전)이 원점에서 가장 먼 거리 / 기준 반지름 0.5.
        /// 조각이 5개를 넘으면 6번째부터는 ±0.4 상자 안의 임의 위치다(기본값 5개에는 해당 없음).</summary>
        public static double PlacementRadiusRatio
        {
            get
            {
                double max = 0;
                foreach (var o in BaseOffsets) max = Math.Max(max, Math.Sqrt(o[0] * o[0] + o[1] * o[1] + o[2] * o[2]));
                return max / NominalRadius;
            }
        }

        /// <summary>조각 기준 반지름의 범위 / 기준 반지름 0.5(축마다 늘이기 0.45–1.35·꼭짓점 흔들기 0.6–1.15 전).</summary>
        public static double PieceSizeMinRatio => SizeScale * 0.5 * (0.42 - 0.04 * (BaseOffsets.Length - 1)) * SizeJitterLo / NominalRadius;
        public static double PieceSizeMaxRatio => SizeScale * 0.5 * 0.42 * SizeJitterHi / NominalRadius;

        // 정이십면체(꼭짓점 12개, 면 20개). 면은 cross(b − a, c − a)가 바깥을 향하도록 만든 뒤 다시 확인한다.
        static readonly double[][] IcoVerts;
        static readonly int[] IcoFaces =
        {
            0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11, 1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8,
            3, 9, 4, 3, 4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9, 4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1,
        };

        static FragmentMesh()
        {
            double t = (1.0 + Math.Sqrt(5.0)) / 2.0;
            double[][] v =
            {
                new[] { -1, t, 0 }, new[] { 1, t, 0 }, new[] { -1, -t, 0 }, new[] { 1, -t, 0 },
                new[] { 0, -1, t }, new[] { 0, 1, t }, new[] { 0, -1, -t }, new[] { 0, 1, -t },
                new[] { t, 0, -1 }, new[] { t, 0, 1 }, new[] { -t, 0, -1 }, new[] { -t, 0, 1 },
            };
            foreach (var p in v)
            {
                double len = Math.Sqrt(p[0] * p[0] + p[1] * p[1] + p[2] * p[2]);
                p[0] /= len; p[1] /= len; p[2] /= len;
            }
            IcoVerts = v;
        }

        /// <summary>
        /// 조각 pieces개를 합친 메시. xyz·nrm = 정점(면마다 3개, 평면 음영), tris = 삼각형 인덱스(앞면 = cross(b − a, c − a)가 바깥).
        /// pieceOfTriangle[i] = i번째 삼각형이 속한 조각. 좌표 단위는 구 지름 1(이전 IcoSphere 반지름 0.5)과 같다.
        /// </summary>
        public static void Build(int seed, int pieces, out float[] xyz, out float[] nrm, out int[] tris, out int[] pieceOfTriangle)
        {
            if (pieces < 1 || pieces > 32) throw new ArgumentOutOfRangeException(nameof(pieces));
            int faces = IcoFaces.Length / 3;
            xyz = new float[pieces * faces * 9];
            nrm = new float[pieces * faces * 9];
            tris = new int[pieces * faces * 3];
            pieceOfTriangle = new int[pieces * faces];
            var rng = new SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0x1234567UL);
            var local = new double[12][];
            int vi = 0, ti = 0;
            for (int piece = 0; piece < pieces; piece++)
            {
                // 중심: 이전 배치 + 조금 흔듦(조각이 더 많으면 반지름 0.4 안의 임의 위치)
                double[] c = piece < BaseOffsets.Length
                    ? new[] { BaseOffsets[piece][0] + rng.Range(-0.03, 0.03), BaseOffsets[piece][1] + rng.Range(-0.03, 0.03), BaseOffsets[piece][2] + rng.Range(-0.03, 0.03) }
                    : new[] { rng.Range(-0.4, 0.4), rng.Range(-0.4, 0.4), rng.Range(-0.4, 0.4) };
                // 크기: 이전 구 반지름 0.5 × (0.42 − 0.04 i) × SizeScale(6번째부터는 가장 작은 것)
                double size = SizeScale * 0.5 * (0.42 - 0.04 * Math.Min(piece, BaseOffsets.Length - 1)) * rng.Range(SizeJitterLo, SizeJitterHi);
                // 축마다 늘이고 줄임(납작한 파편) + 꼭짓점마다 반지름 흔들기(각진 덩이)
                double sx = rng.Range(0.85, 1.35), sy = rng.Range(0.45, 0.8), sz = rng.Range(0.7, 1.1);
                var rot = RandomRotation(rng);
                for (int k = 0; k < 12; k++)
                {
                    double r = rng.Range(0.6, 1.15);
                    double x = IcoVerts[k][0] * r * sx, y = IcoVerts[k][1] * r * sy, z = IcoVerts[k][2] * r * sz;
                    local[k] = new[]
                    {
                        c[0] + size * (rot[0] * x + rot[1] * y + rot[2] * z),
                        c[1] + size * (rot[3] * x + rot[4] * y + rot[5] * z),
                        c[2] + size * (rot[6] * x + rot[7] * y + rot[8] * z),
                    };
                }
                for (int f = 0; f < faces; f++)
                {
                    var a = local[IcoFaces[f * 3]];
                    var b = local[IcoFaces[f * 3 + 1]];
                    var d = local[IcoFaces[f * 3 + 2]];
                    double[] n = Cross(Sub(b, a), Sub(d, a));
                    double[] mid = { (a[0] + b[0] + d[0]) / 3 - c[0], (a[1] + b[1] + d[1]) / 3 - c[1], (a[2] + b[2] + d[2]) / 3 - c[2] };
                    if (Dot(n, mid) < 0) { var tmp = b; b = d; d = tmp; n = new[] { -n[0], -n[1], -n[2] }; }   // 바깥을 향하게
                    double nl = Math.Sqrt(Dot(n, n));
                    if (nl < 1e-12) nl = 1;
                    foreach (var p in new[] { a, b, d })
                    {
                        xyz[vi * 3] = (float)p[0]; xyz[vi * 3 + 1] = (float)p[1]; xyz[vi * 3 + 2] = (float)p[2];
                        nrm[vi * 3] = (float)(n[0] / nl); nrm[vi * 3 + 1] = (float)(n[1] / nl); nrm[vi * 3 + 2] = (float)(n[2] / nl);
                        tris[ti++] = vi++;
                    }
                    pieceOfTriangle[piece * faces + f] = piece;
                }
            }
        }

        /// <summary>정점 좌표의 FNV-1a 해시(결정성 확인용).</summary>
        public static ulong Hash(float[] xyz)
        {
            ulong h = 14695981039346656037UL;
            foreach (var f in xyz)
            {
                uint bits = (uint)BitConverter.SingleToInt32Bits(f);
                for (int i = 0; i < 4; i++) { h ^= (bits >> (8 * i)) & 0xFF; h *= 1099511628211UL; }
            }
            return h;
        }

        // 행 우선 3×3 회전(임의 축·각, 균일하지 않아도 된다 — 결정적이기만 하면 된다)
        static double[] RandomRotation(SplitMix64 rng)
        {
            double ax = rng.Range(-1, 1), ay = rng.Range(-1, 1), az = rng.Range(-1, 1);
            double l = Math.Sqrt(ax * ax + ay * ay + az * az);
            if (l < 1e-6) { ax = 0; ay = 1; az = 0; l = 1; }
            ax /= l; ay /= l; az /= l;
            double ang = rng.Range(0, 2 * Math.PI), cs = Math.Cos(ang), sn = Math.Sin(ang), t = 1 - cs;
            return new[]
            {
                t * ax * ax + cs, t * ax * ay - sn * az, t * ax * az + sn * ay,
                t * ax * ay + sn * az, t * ay * ay + cs, t * ay * az - sn * ax,
                t * ax * az - sn * ay, t * ay * az + sn * ax, t * az * az + cs,
            };
        }

        static double[] Sub(double[] p, double[] q) => new[] { p[0] - q[0], p[1] - q[1], p[2] - q[2] };
        static double[] Cross(double[] p, double[] q) => new[] { p[1] * q[2] - p[2] * q[1], p[2] * q[0] - p[0] * q[2], p[0] * q[1] - p[1] * q[0] };
        static double Dot(double[] p, double[] q) => p[0] * q[0] + p[1] * q[1] + p[2] * q[2];

        /// <summary>SplitMix64 — 작은 결정적 난수(System.Random은 런타임마다 구현이 다를 수 있어 쓰지 않는다).</summary>
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

            /// <summary>[lo, hi) 균일.</summary>
            public double Range(double lo, double hi) => lo + (hi - lo) * ((Next() >> 11) * (1.0 / 9007199254740992.0));
        }
    }
}
