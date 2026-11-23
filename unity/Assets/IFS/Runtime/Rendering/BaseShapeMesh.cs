// 기본 형상(form.base, SceneSpec 2.2.0 — 결정 G21·G30, docs/asset-plan.md 2절)의 절차 메시. 윤곽만 만든다(색·무늬·글자·고유 움직임 없음).
//   container/1  회전체(벽 두께가 있는 닫힌 그릇). 변형: 입구 wide | narrow, 단면 round(둘레 32) | square(둘레 4, 곧은 벽)
//   (line·sheet·flame·drop은 아래 Build의 표를 보라)
// 공통 규칙(docs/asset-plan.md 2-1·2-2·2-3절):
//   - 모형 좌표에서 경계 상자의 가장 긴 변이 1이고 경계 상자 가운데가 원점이다(Normalize). 로더가 기본 크기(primitiveBaseSize)로 줄인다.
//   - 메시 하나, 삼각형 MaxTriangles(5,120) 이하. 면 방향은 바깥(cross(b − a, c − a)가 정점 법선과 같은 쪽 — Unity 앞면 규칙).
//   - 같은 (형상, 변형값, seed) → 같은 메시. 난수는 자체 SplitMix64(seed는 형상 프리셋 고정값 DefaultSeed, 참여자가 말한 값이 아님).
//   - 규칙(형상·변형·매개변수·난수 순서)을 바꾸면 그 형상의 규칙 버전(RuleFor)을 올린다(계획 JSON·notes의 base.rule로 추적).
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 지오메트리 셰이더·컴퓨트 없이 CPU에서 만들어 WebGL2에서도 같다.
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec
{
    public static class BaseShapeMesh
    {
        /// <summary>기본 형상 하나의 삼각형 상한(blob icosphere와 같은 수, docs/asset-plan.md 2-3절).</summary>
        public const int MaxTriangles = 5120;
        /// <summary>형상 프리셋 기본값: seed(후보에서 벌리지 않음, docs/asset-plan.md 2-1절).</summary>
        public const int DefaultSeed = 0;

        static readonly Dictionary<string, string> Rules = new Dictionary<string, string>(StringComparer.Ordinal)
        {
            { BaseShapes.Container, "container/1" },
        };

        /// <summary>형상의 생성 규칙 버전. 만들지 않은 형상이면 null(로더가 그리지 않고 기록한다).</summary>
        public static string RuleFor(string shape) => shape != null && Rules.TryGetValue(shape, out var r) ? r : null;

        public static bool Supports(string shape) => RuleFor(shape) != null;

        /// <summary>메시를 만든다. variant = BaseShapes.Resolve가 채운 변형값 전체(키 → 값). 지원하지 않는 형상이면 ArgumentException.</summary>
        public static void Build(string shape, IReadOnlyDictionary<string, string> variant, int seed,
                                 out float[] xyz, out float[] nrm, out int[] tris)
        {
            var m = new MeshData();
            string V(string k, string fallback) => variant != null && variant.TryGetValue(k, out var v) && v != null ? v : fallback;
            switch (shape)
            {
                case BaseShapes.Container:
                    BuildContainer(m, V("opening", "wide"), V("profile", "round"));
                    break;
                default:
                    throw new ArgumentException("만들 수 없는 기본 형상: " + shape);
            }
            m.Normalize();
            m.ToArrays(out xyz, out nrm, out tris);
        }

        /// <summary>형상별 주요 매개변수(계획 JSON·notes 기록용). 지원하지 않으면 빈 사전.</summary>
        public static SortedDictionary<string, double> Parameters(string shape, IReadOnlyDictionary<string, string> variant)
        {
            var p = new SortedDictionary<string, double>(StringComparer.Ordinal);
            string V(string k, string fallback) => variant != null && variant.TryGetValue(k, out var v) && v != null ? v : fallback;
            switch (shape)
            {
                case BaseShapes.Container:
                    bool square = V("profile", "round") == "square";
                    p["segments"] = square ? 4 : ContainerSegments;
                    p["rows"] = ContainerRows;
                    p["wallThickness"] = ContainerWall;
                    break;
            }
            return p;
        }

        // ── container ───────────────────────────────────────────────────────
        const int ContainerSegments = 32;
        const int ContainerRows = 22;
        const double ContainerWall = 0.04;

        /// <summary>바깥 옆면 윤곽 반지름(y = 0…1). 둥근 단면만 쓴다.</summary>
        static double ContainerRadius(double y, bool narrow)
        {
            if (!narrow)
            {
                // 그릇·컵·화분: 바닥 0.33 → 몸통 0.45(y 0.6) → 테두리 0.405(몸통의 0.9배). 바깥으로 벌어진 입술·굽 없음
                if (y <= 0.6) return 0.33 + 0.12 * Math.Sin(Math.PI * 0.5 * y / 0.6);
                double t = (y - 0.6) / 0.4;
                return 0.45 - 0.045 * t * t;
            }
            // 병·꽃병·항아리: 바닥 0.38 → 몸통 0.45(y 0.15–0.55) → 어깨에서 좁아져 목 0.1575(몸통의 0.35배, y ≥ 0.85)
            if (y <= 0.15) return 0.38 + 0.07 * Math.Sin(Math.PI * 0.5 * y / 0.15);
            if (y <= 0.55) return 0.45;
            if (y <= 0.85)
            {
                double t = (y - 0.55) / 0.3;
                double s = t * t * (3 - 2 * t);                 // 부드러운 어깨
                return 0.45 + (0.1575 - 0.45) * s;
            }
            return 0.1575;
        }

        static void BuildContainer(MeshData m, string opening, string profile)
        {
            bool narrow = opening == "narrow";
            bool square = profile == "square";
            int segs = square ? 4 : ContainerSegments;
            double angle0 = square ? Math.PI / 4 : 0;           // 네모: 45° 돌려 평평한 옆면이 ±x·±z를 향함
            double wall = ContainerWall;
            int rows = square ? 2 : ContainerRows;
            double height = square ? 0.7 : 1.0;                  // 상자: 뚜껑 없는 열린 네모 통(곧은 벽)
            // 바깥 윤곽(아래 → 위): (반지름, 높이). 네모는 꼭짓점까지의 반지름(평평한 면까지 = r·cos 45°)
            var outer = new List<(double r, double y)>();
            for (int k = 0; k < rows; k++)
            {
                double y = height * k / (rows - 1);
                double r = square ? 0.5 / Math.Cos(Math.PI / 4) : ContainerRadius(y / height, narrow);
                outer.Add((r, y));
            }
            double rCorr = square ? 1.0 / Math.Cos(Math.PI / segs) : 1.0;   // 네모: 벽 두께를 평평한 면에서 재도록
            var inner = new List<(double r, double y)>();
            for (int k = 0; k < rows; k++)
            {
                var (r, y) = outer[k];
                inner.Add((r - wall * rCorr, Math.Max(y, wall)));
            }
            // 바깥 옆면(바깥을 향함), 안쪽 옆면(축을 향함)
            m.Lathe(outer, segs, angle0, outward: true, hard: square);
            m.Lathe(inner, segs, angle0, outward: false, hard: square);
            // 테두리 띠(위를 향함): 바깥 맨 위 → 안쪽 맨 위
            m.Annulus(outer[rows - 1].r, inner[rows - 1].r, height, segs, angle0, up: true);
            // 바깥 바닥(아래를 향함), 안쪽 바닥(위를 향함)
            m.Annulus(outer[0].r, 0, 0, segs, angle0, up: false);
            m.Annulus(inner[0].r, 0, inner[0].y, segs, angle0, up: true);
        }

        // ── 공통 ────────────────────────────────────────────────────────────
        /// <summary>정점 좌표 해시(FNV-1a, float 비트). 규칙 버전에 묶어 테스트가 고정한다.</summary>
        public static ulong Hash(float[] xyz) => FragmentMesh.Hash(xyz);

        /// <summary>메시를 쌓는 도우미. 정점 법선을 함께 넣는다.</summary>
        sealed class MeshData
        {
            readonly List<double> _p = new List<double>();
            readonly List<double> _n = new List<double>();
            readonly List<int> _t = new List<int>();

            public int Add(double x, double y, double z, double nx, double ny, double nz)
            {
                double len = Math.Sqrt(nx * nx + ny * ny + nz * nz);
                if (len < 1e-12) { nx = 0; ny = 1; nz = 0; len = 1; }
                _p.Add(x); _p.Add(y); _p.Add(z);
                _n.Add(nx / len); _n.Add(ny / len); _n.Add(nz / len);
                return _p.Count / 3 - 1;
            }

            /// <summary>삼각형 하나. 법선 쪽에서 볼 때 앞면이 되도록(cross(b − a, c − a)가 a의 법선과 같은 쪽) 필요하면 순서를 바꾼다.</summary>
            public void Tri(int a, int b, int c)
            {
                double ax = _p[a * 3], ay = _p[a * 3 + 1], az = _p[a * 3 + 2];
                double ux = _p[b * 3] - ax, uy = _p[b * 3 + 1] - ay, uz = _p[b * 3 + 2] - az;
                double vx = _p[c * 3] - ax, vy = _p[c * 3 + 1] - ay, vz = _p[c * 3 + 2] - az;
                double cx = uy * vz - uz * vy, cy = uz * vx - ux * vz, cz = ux * vy - uy * vx;
                double area2 = cx * cx + cy * cy + cz * cz;
                if (area2 < 1e-18) return;                       // 넓이 0인 삼각형은 넣지 않는다
                double nx = _n[a * 3] + _n[b * 3] + _n[c * 3], ny = _n[a * 3 + 1] + _n[b * 3 + 1] + _n[c * 3 + 1],
                       nz = _n[a * 3 + 2] + _n[b * 3 + 2] + _n[c * 3 + 2];
                if (cx * nx + cy * ny + cz * nz >= 0) { _t.Add(a); _t.Add(b); _t.Add(c); }
                else { _t.Add(a); _t.Add(c); _t.Add(b); }
            }

            public void Quad(int a, int b, int c, int d) { Tri(a, b, c); Tri(a, c, d); }

            /// <summary>윤곽(반지름, 높이)을 y축으로 돌린 옆면. hard면 둘레 조각마다 평평한 법선(네모 단면).</summary>
            public void Lathe(List<(double r, double y)> prof, int segs, double angle0, bool outward, bool hard)
            {
                double sgn = outward ? 1 : -1;
                for (int j = 0; j < segs; j++)
                {
                    double a0 = angle0 + 2 * Math.PI * j / segs, a1 = angle0 + 2 * Math.PI * (j + 1) / segs, am = (a0 + a1) / 2;
                    var col0 = new int[prof.Count];
                    var col1 = new int[prof.Count];
                    for (int k = 0; k < prof.Count; k++)
                    {
                        // 윤곽 기울기 dr/dy(앞뒤 차분) → (r, y) 평면의 바깥 법선 (1, −dr/dy)
                        int k0 = Math.Max(0, k - 1), k1 = Math.Min(prof.Count - 1, k + 1);
                        double dy = prof[k1].y - prof[k0].y, dr = prof[k1].r - prof[k0].r;
                        double nr = dy, ny = -dr;
                        if (hard)
                        {
                            double flat = Math.Cos(Math.PI / segs);   // 평평한 면의 법선 = 가운데 각도
                            col0[k] = Add(prof[k].r * Math.Cos(a0), prof[k].y, prof[k].r * Math.Sin(a0), sgn * nr * Math.Cos(am) * flat, sgn * ny, sgn * nr * Math.Sin(am) * flat);
                            col1[k] = Add(prof[k].r * Math.Cos(a1), prof[k].y, prof[k].r * Math.Sin(a1), sgn * nr * Math.Cos(am) * flat, sgn * ny, sgn * nr * Math.Sin(am) * flat);
                        }
                        else
                        {
                            col0[k] = Add(prof[k].r * Math.Cos(a0), prof[k].y, prof[k].r * Math.Sin(a0), sgn * nr * Math.Cos(a0), sgn * ny, sgn * nr * Math.Sin(a0));
                            col1[k] = Add(prof[k].r * Math.Cos(a1), prof[k].y, prof[k].r * Math.Sin(a1), sgn * nr * Math.Cos(a1), sgn * ny, sgn * nr * Math.Sin(a1));
                        }
                    }
                    for (int k = 0; k + 1 < prof.Count; k++) Quad(col0[k], col1[k], col1[k + 1], col0[k + 1]);
                }
            }

            /// <summary>높이 y의 고리(바깥 반지름 r0, 안 반지름 r1; r1 = 0이면 원판). up이면 위(+y)를, 아니면 아래를 향함.</summary>
            public void Annulus(double r0, double r1, double y, int segs, double angle0, bool up)
            {
                double ny = up ? 1 : -1;
                int center = r1 <= 0 ? Add(0, y, 0, 0, ny, 0) : -1;
                for (int j = 0; j < segs; j++)
                {
                    double a0 = angle0 + 2 * Math.PI * j / segs, a1 = angle0 + 2 * Math.PI * (j + 1) / segs;
                    int o0 = Add(r0 * Math.Cos(a0), y, r0 * Math.Sin(a0), 0, ny, 0);
                    int o1 = Add(r0 * Math.Cos(a1), y, r0 * Math.Sin(a1), 0, ny, 0);
                    if (center >= 0) { Tri(center, o0, o1); continue; }
                    int i0 = Add(r1 * Math.Cos(a0), y, r1 * Math.Sin(a0), 0, ny, 0);
                    int i1 = Add(r1 * Math.Cos(a1), y, r1 * Math.Sin(a1), 0, ny, 0);
                    Quad(o0, o1, i1, i0);
                }
            }

            /// <summary>경계 상자 가운데를 원점으로, 가장 긴 변을 1로.</summary>
            public void Normalize()
            {
                double[] lo = { double.MaxValue, double.MaxValue, double.MaxValue }, hi = { double.MinValue, double.MinValue, double.MinValue };
                for (int i = 0; i < _p.Count; i++) { lo[i % 3] = Math.Min(lo[i % 3], _p[i]); hi[i % 3] = Math.Max(hi[i % 3], _p[i]); }
                double size = Math.Max(hi[0] - lo[0], Math.Max(hi[1] - lo[1], hi[2] - lo[2]));
                for (int i = 0; i < _p.Count; i++) _p[i] = (_p[i] - (lo[i % 3] + hi[i % 3]) / 2) / size;
            }

            public void ToArrays(out float[] xyz, out float[] nrm, out int[] tris)
            {
                xyz = new float[_p.Count];
                nrm = new float[_n.Count];
                for (int i = 0; i < _p.Count; i++) { xyz[i] = (float)_p[i]; nrm[i] = (float)_n[i]; }
                tris = _t.ToArray();
            }
        }
    }
}
