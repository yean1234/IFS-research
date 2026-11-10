// 고르게 잘게 나눈 구(icosphere). 셰이더가 정점을 노이즈로 밀어 '덩어리' 모양을 만들려면
// Unity 기본 구(위도·경도 격자)보다 정점이 고르게 퍼져 있어야 한다.
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 반지름 0.5 = Unity 기본 구와 같은 크기.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public static class IcoSphere
    {
        /// <summary>정점 좌표(x,y,z 반복)와 삼각형 인덱스. 앞면 = Unity 규칙(cross(b−a, c−a)가 바깥).</summary>
        public static void Build(int subdivisions, float radius, out float[] xyz, out int[] triangles)
        {
            if (subdivisions < 0 || subdivisions > 6) throw new ArgumentOutOfRangeException(nameof(subdivisions));
            var verts = new List<double[]>();
            var cache = new Dictionary<long, int>();

            int Add(double x, double y, double z)
            {
                double len = Math.Sqrt(x * x + y * y + z * z);
                verts.Add(new[] { x / len, y / len, z / len });
                return verts.Count - 1;
            }

            int Mid(int a, int b)
            {
                long key = a < b ? ((long)a << 32) | (uint)b : ((long)b << 32) | (uint)a;
                if (cache.TryGetValue(key, out int i)) return i;
                var p = verts[a];
                var q = verts[b];
                i = Add((p[0] + q[0]) / 2, (p[1] + q[1]) / 2, (p[2] + q[2]) / 2);
                cache[key] = i;
                return i;
            }

            double t = (1.0 + Math.Sqrt(5.0)) / 2.0;
            Add(-1, t, 0); Add(1, t, 0); Add(-1, -t, 0); Add(1, -t, 0);
            Add(0, -1, t); Add(0, 1, t); Add(0, -1, -t); Add(0, 1, -t);
            Add(t, 0, -1); Add(t, 0, 1); Add(-t, 0, -1); Add(-t, 0, 1);

            var faces = new List<int>
            {
                0, 11, 5, 0, 5, 1, 0, 1, 7, 0, 7, 10, 0, 10, 11,
                1, 5, 9, 5, 11, 4, 11, 10, 2, 10, 7, 6, 7, 1, 8,
                3, 9, 4, 3, 4, 2, 3, 2, 6, 3, 6, 8, 3, 8, 9,
                4, 9, 5, 2, 4, 11, 6, 2, 10, 8, 6, 7, 9, 8, 1,
            };

            for (int s = 0; s < subdivisions; s++)
            {
                var next = new List<int>(faces.Count * 4);
                for (int f = 0; f < faces.Count; f += 3)
                {
                    int a = faces[f], b = faces[f + 1], c = faces[f + 2];
                    int ab = Mid(a, b), bc = Mid(b, c), ca = Mid(c, a);
                    next.AddRange(new[] { a, ab, ca, b, bc, ab, c, ca, bc, ab, bc, ca });
                }
                faces = next;
            }

            // 앞면 방향을 Unity 규칙에 맞춘다(바깥에서 볼 때 보이도록).
            for (int f = 0; f < faces.Count; f += 3)
            {
                var a = verts[faces[f]];
                var b = verts[faces[f + 1]];
                var c = verts[faces[f + 2]];
                double ux = b[0] - a[0], uy = b[1] - a[1], uz = b[2] - a[2];
                double vx = c[0] - a[0], vy = c[1] - a[1], vz = c[2] - a[2];
                double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                double cx = a[0] + b[0] + c[0], cy = a[1] + b[1] + c[1], cz = a[2] + b[2] + c[2];
                if (nx * cx + ny * cy + nz * cz < 0)
                {
                    int tmp = faces[f + 1];
                    faces[f + 1] = faces[f + 2];
                    faces[f + 2] = tmp;
                }
            }

            xyz = new float[verts.Count * 3];
            for (int i = 0; i < verts.Count; i++)
            {
                xyz[i * 3] = (float)(verts[i][0] * radius);
                xyz[i * 3 + 1] = (float)(verts[i][1] * radius);
                xyz[i * 3 + 2] = (float)(verts[i][2] * radius);
            }
            triangles = faces.ToArray();
        }
    }
}
