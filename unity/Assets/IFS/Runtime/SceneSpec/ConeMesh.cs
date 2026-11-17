// 원뿔 메시(모양어 '뾰족' → Cone). Unity에는 원뿔 프리미티브가 없어 코드로 만든다.
// 밑면 지름 1, 높이 1, 경계 상자 가운데 = 원점(y −0.5 ~ 0.5, 꼭짓점이 위). Unity 기본 구·큐브와 같은 크기 척도.
// 옆면은 둘레 방향으로 매끄러운 법선, 밑면 테두리는 정점을 따로 두어 각진 모서리(hard edge), 밑면 뚜껑 있음.
// 꼭짓점은 옆면 조각마다 따로 둔다(조각 가운데 방향 법선) — 한 점에 법선 하나를 두면 꼭짓점 둘레가 얼룩진다.
// UnityEngine에 의존하지 않는다(IcoSphere와 같이 dotnet 테스트 가능).
using System;

namespace IFS.SceneSpec
{
    public static class ConeMesh
    {
        public const int DefaultSegments = 48;
        public const float Radius = 0.5f;
        public const float Height = 1f;

        /// <summary>정점 수 = 3 × segments + 1 (옆면 테두리 · 꼭짓점 · 밑면 테두리 · 밑면 중심).</summary>
        public static int VertexCount(int segments) => 3 * segments + 1;

        /// <summary>삼각형 수 = 2 × segments (옆면 · 밑면).</summary>
        public static int TriangleCount(int segments) => 2 * segments;

        /// <summary>
        /// 정점 좌표·법선(x,y,z 반복)과 삼각형 인덱스. 앞면 = Unity 규칙(cross(b−a, c−a)가 바깥) — IcoSphere와 같다.
        /// segments는 4의 배수를 권한다(그래야 ±x·±z 끝점이 정확히 반지름에 놓여 경계 상자가 1×1×1).
        /// </summary>
        public static void Build(int segments, out float[] xyz, out float[] normals, out int[] triangles)
        {
            if (segments < 3 || segments > 1024) throw new ArgumentOutOfRangeException(nameof(segments));
            int n = segments;
            double r = Radius, h = Height, yTop = h / 2, yBottom = -h / 2;
            // 옆면 법선: 반지름 방향 성분 h, 위 성분 r (경사면에 수직), 단위 길이로
            double len = Math.Sqrt(h * h + r * r);
            double nr = h / len, ny = r / len;

            var pos = new float[VertexCount(n) * 3];
            var nrm = new float[pos.Length];
            var tris = new int[TriangleCount(n) * 3];

            void Set(int i, double x, double y, double z, double nx, double nyv, double nz)
            {
                pos[i * 3] = (float)x; pos[i * 3 + 1] = (float)y; pos[i * 3 + 2] = (float)z;
                nrm[i * 3] = (float)nx; nrm[i * 3 + 1] = (float)nyv; nrm[i * 3 + 2] = (float)nz;
            }

            int sideRing = 0, apex = n, baseRing = 2 * n, center = 3 * n;
            for (int i = 0; i < n; i++)
            {
                double a = 2 * Math.PI * i / n;
                double c = Math.Cos(a), s = Math.Sin(a);
                Set(sideRing + i, r * c, yBottom, r * s, nr * c, ny, nr * s);     // 옆면 테두리(매끄러운 법선)
                double am = 2 * Math.PI * (i + 0.5) / n;
                Set(apex + i, 0, yTop, 0, nr * Math.Cos(am), ny, nr * Math.Sin(am)); // 조각별 꼭짓점
                Set(baseRing + i, r * c, yBottom, r * s, 0, -1, 0);                 // 밑면 테두리(아래 법선 = 각진 모서리)
            }
            Set(center, 0, yBottom, 0, 0, -1, 0);

            int t = 0;
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                // 옆면: (꼭짓점, 다음 테두리, 이번 테두리) — 바깥에서 볼 때 앞면
                tris[t++] = apex + i; tris[t++] = sideRing + j; tris[t++] = sideRing + i;
            }
            for (int i = 0; i < n; i++)
            {
                int j = (i + 1) % n;
                // 밑면: (중심, 이번 테두리, 다음 테두리) — 아래에서 볼 때 앞면
                tris[t++] = center; tris[t++] = baseRing + i; tris[t++] = baseRing + j;
            }
            xyz = pos;
            normals = nrm;
            triangles = tris;
        }
    }
}
