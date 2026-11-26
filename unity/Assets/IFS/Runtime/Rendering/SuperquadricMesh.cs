// (2.3, G61 ①) 슈퍼쿼드릭 메시(superquadric/1) — form.roundness가 있을 때 기본 덩어리 메시를 대신한다(docs/scene-spec-mapping.md 8.4절 3번).
//   Barr(1981) 초타원체. Unity 국소 축(y가 위), 지름 1(반축 0.5)인 단위 형상:
//     η ∈ [−π/2, π/2](위도), ω ∈ [−π, π)(경도), f(c, e) = sign(c)·|c|^e
//     x = 0.5·f(cos η, e1)·f(cos ω, e2),  y = 0.5·f(sin η, e1),  z = 0.5·f(cos η, e1)·f(sin ω, e2)
//   경도 48칸 × 위도 24칸(ContourRender.LongitudeSegments·LatitudeSegments), 극점은 한 점으로 모은다. 경도 이음매는 정점을 겹치지 않고
//   첫 열로 되돌아간다(UV를 쓰지 않으므로). 정점 1,106개, 삼각형 2,208개.
//   법선은 해석 법선(Barr 1981: 지수 e를 2 − e로 바꾼 같은 꼴을 정규화). e가 작으면(angular 0.1) 정점이 모서리 근처에 몰려
//   RecalculateNormals의 면 평균이 얼룩질 수 있어 쓰지 않는다. 극점의 법선은 (0, ±1, 0).
//   격자에 cos·sin이 정확히 0이어야 하는 각(0, ±π/2, ±π)이 있다. 배정밀도의 sin(π) ≈ 1e-16도 |c|^0.1 ≈ 0.03이 되므로
//   |값| < 1e-12는 0으로 맞춘다(그러지 않으면 축 끝에 작은 돌기가 생긴다).
// 면 방향은 바깥(cross(b − a, c − a)가 정점 법선과 같은 쪽 — BaseShapeMesh와 같은 Unity 앞면 규칙). 난수가 없어 같은 (e1, e2)면 같은 메시.
// 규칙(식·칸 수·정점 순서)을 바꾸면 ContourRender.MeshRule을 올린다. UnityEngine에 의존하지 않는다(dotnet 테스트 가능).
using System;

namespace IFS.SceneSpec
{
    public static class SuperquadricMesh
    {
        const double SnapZero = 1e-12;

        /// <summary>정점 수 = 극점 2 + (위도 칸 − 1) × 경도 칸.</summary>
        public static int VertexCount(int lon = ContourRender.LongitudeSegments, int lat = ContourRender.LatitudeSegments) => 2 + (lat - 1) * lon;

        /// <summary>삼각형 수 = 극점 부채꼴 2 × 경도 칸 + (위도 칸 − 2) × 경도 칸 × 2.</summary>
        public static int TriangleCount(int lon = ContourRender.LongitudeSegments, int lat = ContourRender.LatitudeSegments) => 2 * lon + (lat - 2) * lon * 2;

        /// <summary>메시를 만든다. e1 = 위도(위아래) 단면 지수, e2 = 경도(수평) 단면 지수(0 &lt; e ≤ 1).</summary>
        public static void Build(double e1, double e2, out float[] xyz, out float[] nrm, out int[] tris,
                                 int lon = ContourRender.LongitudeSegments, int lat = ContourRender.LatitudeSegments)
        {
            if (!(e1 > 0 && e1 <= 1) || !(e2 > 0 && e2 <= 1)) throw new ArgumentOutOfRangeException(nameof(e1), "지수는 0 < e ≤ 1(e > 1은 쓰지 않음)");
            if (lon < 3 || lat < 2) throw new ArgumentOutOfRangeException(nameof(lon));
            double r = ContourRender.UnitDiameter / 2.0;
            int n = VertexCount(lon, lat);
            var pos = new float[n * 3];
            var nor = new float[n * 3];
            // 경도 각의 cos·sin(열마다 한 번)
            var cw = new double[lon];
            var sw = new double[lon];
            for (int i = 0; i < lon; i++)
            {
                double w = -Math.PI + i * (2.0 * Math.PI / lon);
                cw[i] = Snap(Math.Cos(w));
                sw[i] = Snap(Math.Sin(w));
            }
            int v = 0;
            void Put(double x, double y, double z, double nx, double ny, double nz)
            {
                double len = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                pos[v * 3] = (float)x; pos[v * 3 + 1] = (float)y; pos[v * 3 + 2] = (float)z;
                nor[v * 3] = (float)(nx / len); nor[v * 3 + 1] = (float)(ny / len); nor[v * 3 + 2] = (float)(nz / len);
                v++;
            }
            Put(0, -r, 0, 0, -1, 0);   // 남극(j = 0)
            for (int j = 1; j < lat; j++)
            {
                double eta = -Math.PI / 2.0 + j * (Math.PI / lat);
                double ce = Snap(Math.Cos(eta)), se = Snap(Math.Sin(eta));
                double fc1 = F(ce, e1), fs1 = F(se, e1);
                double gc1 = F(ce, 2.0 - e1), gs1 = F(se, 2.0 - e1);
                for (int i = 0; i < lon; i++)
                    Put(r * fc1 * F(cw[i], e2), r * fs1, r * fc1 * F(sw[i], e2),
                        gc1 * F(cw[i], 2.0 - e2), gs1, gc1 * F(sw[i], 2.0 - e2));
            }
            Put(0, r, 0, 0, 1, 0);     // 북극(j = lat)

            int north = n - 1;
            int Ring(int j, int i) => 1 + (j - 1) * lon + ((i % lon) + lon) % lon;   // j = 1 … lat − 1
            var idx = new int[TriangleCount(lon, lat) * 3];
            int t = 0;
            void Tri(int a, int b, int c) { idx[t++] = a; idx[t++] = b; idx[t++] = c; }
            for (int i = 0; i < lon; i++) Tri(0, Ring(1, i), Ring(1, i + 1));                  // 남극 부채꼴
            for (int j = 1; j < lat - 1; j++)
                for (int i = 0; i < lon; i++)
                {
                    // (j, i) → 위(j + 1)·옆(i + 1). cross(위 − 여기, 옆 − 여기)가 바깥(η 증가 × ω 증가 = 바깥 법선 쪽)
                    Tri(Ring(j, i), Ring(j + 1, i), Ring(j, i + 1));
                    Tri(Ring(j, i + 1), Ring(j + 1, i), Ring(j + 1, i + 1));
                }
            for (int i = 0; i < lon; i++) Tri(Ring(lat - 1, i), north, Ring(lat - 1, i + 1));  // 북극 부채꼴
            xyz = pos;
            nrm = nor;
            tris = idx;
        }

        /// <summary>정점 해시(FragmentMesh.Hash와 같은 식). 규칙 버전에 묶어 테스트가 고정한다.</summary>
        public static ulong Hash(float[] xyz) => FragmentMesh.Hash(xyz);

        static double Snap(double c) => Math.Abs(c) < SnapZero ? 0.0 : c;

        /// <summary>f(c, e) = sign(c)·|c|^e. c = 0이면 0.</summary>
        static double F(double c, double e) => c == 0.0 ? 0.0 : Math.Sign(c) * Math.Pow(Math.Abs(c), e);
    }
}
