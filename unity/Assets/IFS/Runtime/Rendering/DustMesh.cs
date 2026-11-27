// (2.4 선택 슬롯, G74) form.mistKind = dust(먼지·모래·가루)의 메시: 작은 알갱이 여러 개를 메시 하나로 합친다(드로콜 1, 평면 음영).
// 알갱이 = 정팔면체(꼭짓점 6, 면 8)를 seed로 돌리고 크기를 정해 놓는다. 자리는 가운데가 빽빽하고(가우스, 축마다 σ = 0.2)
// 바깥에 드문드문 흩어진 알갱이(15 %, 공 안 고른 분포)를 더한다. 모두 반지름 PlacementRadius 공 안(안개 덩어리가 그려지는 범위와 비슷).
// 개수·크기·배치·seed는 형상 프리셋 기본값이다(참여자가 말한 값 아님, 초안). 규칙을 바꾸면 같은 seed라도 메시가 달라지므로 RuleVersion을 올린다.
// (2.4, G72) x·y·z 비율이 주어지면 알갱이 모양은 그대로 두고 자리만 축마다 p로 늘이고 줄인다(fragments와 같은 방법, 난수 순서 그대로 →
// 비율이 없으면 이전 메시와 비트 단위로 같다). 가장 긴 변은 로더가 균일 배율로 맞춘다(ProportionsRender).
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 난수는 자체 구현(SplitMix64)이라 런타임이 달라도 같은 수열이다.
using System;

namespace IFS.SceneSpec
{
    public static class DustMesh
    {
        /// <summary>알갱이 배치 규칙 버전(계획 JSON mistKind.rule·dustRule). 규칙을 바꾸면 올린다(DustMeshTests가 기본 메시 해시를 묶어 둔다).</summary>
        public const string RuleVersion = "dust520/1";
        /// <summary>형상 프리셋 기본값: 알갱이 수.</summary>
        public const int DefaultGrains = 520;
        /// <summary>형상 프리셋 기본값: seed(spec과 무관한 고정값 → 같은 spec이면 같은 메시).</summary>
        public const int DefaultSeed = 0;
        /// <summary>알갱이 중심이 놓이는 공의 반지름(물체 좌표). 안개 덩어리가 그려지는 범위(MistLumps.MaxExtent 0.64)보다 조금 안쪽.</summary>
        public const double PlacementRadius = 0.56;
        /// <summary>가운데 무리의 표준 편차(축마다), 드문드문 흩어진 알갱이의 비율.</summary>
        public const double Sigma = 0.2, StrayFraction = 0.15;
        /// <summary>알갱이 반지름 범위(물체 좌표): r = Min + (Max − Min) × u²(작은 알갱이가 많음).</summary>
        public const double GrainRadiusMin = 0.010, GrainRadiusMax = 0.024;

        static readonly double[][] OctVerts =
        {
            new[] { 1.0, 0, 0 }, new[] { -1.0, 0, 0 }, new[] { 0, 1.0, 0 }, new[] { 0, -1.0, 0 }, new[] { 0, 0, 1.0 }, new[] { 0, 0, -1.0 },
        };
        // 바깥을 향한 면(cross(b − a, c − a)가 바깥)
        static readonly int[] OctFaces = { 0, 2, 4, 4, 2, 1, 1, 2, 5, 5, 2, 0, 4, 3, 0, 1, 3, 4, 5, 3, 1, 0, 3, 5 };

        /// <summary>알갱이 메시(평면 음영: 면마다 정점 3개). xyz·nrm = 정점 × 3, tris = 0…, grainOfTriangle = 삼각형마다 알갱이 번호.</summary>
        public static void Build(int seed, int grains, double[] proportions, out float[] xyz, out float[] nrm, out int[] tris, out int[] grainOfTriangle)
        {
            int faces = OctFaces.Length / 3;
            xyz = new float[grains * faces * 9];
            nrm = new float[grains * faces * 9];
            tris = new int[grains * faces * 3];
            grainOfTriangle = new int[grains * faces];
            var rng = new MistKinds.SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0xD057UL);
            double px = proportions?[0] ?? 1.0, py = proportions?[1] ?? 1.0, pz = proportions?[2] ?? 1.0;
            int vi = 0, ti = 0;
            for (int g = 0; g < grains; g++)
            {
                double cx, cy, cz;
                if (rng.Range(0.0, 1.0) < StrayFraction)
                {
                    // 공 안 고른 분포(거부 표집)
                    do { cx = rng.Range(-1.0, 1.0); cy = rng.Range(-1.0, 1.0); cz = rng.Range(-1.0, 1.0); } while (cx * cx + cy * cy + cz * cz > 1.0);
                    cx *= PlacementRadius; cy *= PlacementRadius; cz *= PlacementRadius;
                }
                else
                {
                    // 가우스(Box–Muller), 공 밖이면 다시 뽑는다
                    do { cx = Gauss(rng) * Sigma; cy = Gauss(rng) * Sigma; cz = Gauss(rng) * Sigma; }
                    while (cx * cx + cy * cy + cz * cz > PlacementRadius * PlacementRadius);
                }
                double u = rng.Range(0.0, 1.0);
                double r = GrainRadiusMin + (GrainRadiusMax - GrainRadiusMin) * u * u;
                // 임의 회전(단위 사원수, Shoemake)과 축마다 조금 늘이고 줄이기(0.7–1.3)
                double u1 = rng.Range(0.0, 1.0), u2 = rng.Range(0.0, 2.0 * Math.PI), u3 = rng.Range(0.0, 2.0 * Math.PI);
                double qw = Math.Sqrt(1 - u1) * Math.Sin(u2), qx = Math.Sqrt(1 - u1) * Math.Cos(u2), qy = Math.Sqrt(u1) * Math.Sin(u3), qz = Math.Sqrt(u1) * Math.Cos(u3);
                double sx = rng.Range(0.7, 1.3), sy = rng.Range(0.7, 1.3), sz = rng.Range(0.7, 1.3);
                cx *= px; cy *= py; cz *= pz;
                var pts = new double[6][];
                for (int k = 0; k < 6; k++)
                {
                    var v = OctVerts[k];
                    Rotate(qw, qx, qy, qz, v[0] * r * sx, v[1] * r * sy, v[2] * r * sz, out double rx, out double ry, out double rz);
                    pts[k] = new[] { cx + rx, cy + ry, cz + rz };
                }
                for (int f = 0; f < faces; f++)
                {
                    var a = pts[OctFaces[f * 3]]; var b = pts[OctFaces[f * 3 + 1]]; var c = pts[OctFaces[f * 3 + 2]];
                    double ex = b[0] - a[0], ey = b[1] - a[1], ez = b[2] - a[2];
                    double fx = c[0] - a[0], fy = c[1] - a[1], fz = c[2] - a[2];
                    double nx = ey * fz - ez * fy, ny = ez * fx - ex * fz, nz = ex * fy - ey * fx;
                    double nl = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                    if (nl > 1e-12) { nx /= nl; ny /= nl; nz /= nl; }
                    foreach (var p in new[] { a, b, c })
                    {
                        xyz[vi * 3] = (float)p[0]; xyz[vi * 3 + 1] = (float)p[1]; xyz[vi * 3 + 2] = (float)p[2];
                        nrm[vi * 3] = (float)nx; nrm[vi * 3 + 1] = (float)ny; nrm[vi * 3 + 2] = (float)nz;
                        tris[vi] = vi;
                        vi++;
                    }
                    grainOfTriangle[ti++] = g;
                }
            }
        }

        static double Gauss(MistKinds.SplitMix64 rng)
        {
            double a = rng.Range(1e-12, 1.0), b = rng.Range(0.0, 2.0 * Math.PI);
            return Math.Sqrt(-2.0 * Math.Log(a)) * Math.Cos(b);
        }

        static void Rotate(double w, double x, double y, double z, double vx, double vy, double vz, out double rx, out double ry, out double rz)
        {
            // v' = q v q*
            double tx = 2 * (y * vz - z * vy), ty = 2 * (z * vx - x * vz), tz = 2 * (x * vy - y * vx);
            rx = vx + w * tx + (y * tz - z * ty);
            ry = vy + w * ty + (z * tx - x * tz);
            rz = vz + w * tz + (x * ty - y * tx);
        }

        /// <summary>메시 정점 경계(중심·크기). 로더의 가장 긴 변 규칙(L0 = 비율 없는 메시의 경계)이 쓴다.</summary>
        public static void Bounds(int seed, int grains, double[] proportions, out double[] center, out double[] size)
        {
            Build(seed, grains, proportions, out var xyz, out _, out _, out _);
            var lo = new[] { double.MaxValue, double.MaxValue, double.MaxValue };
            var hi = new[] { double.MinValue, double.MinValue, double.MinValue };
            for (int i = 0; i < xyz.Length; i += 3)
                for (int k = 0; k < 3; k++) { lo[k] = Math.Min(lo[k], xyz[i + k]); hi[k] = Math.Max(hi[k], xyz[i + k]); }
            center = new[] { (lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, (lo[2] + hi[2]) / 2 };
            size = new[] { hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2] };
        }

        /// <summary>메시 지문(FNV-1a 64, 정점 좌표 비트). 규칙이 바뀌었는지 테스트가 본다.</summary>
        public static ulong Hash(float[] xyz)
        {
            ulong h = 1469598103934665603UL;
            foreach (var f in xyz)
            {
                uint b = BitConverter.ToUInt32(BitConverter.GetBytes(f), 0);
                for (int k = 0; k < 4; k++) { h ^= (b >> (8 * k)) & 0xFF; h *= 1099511628211UL; }
            }
            return h;
        }
    }
}
