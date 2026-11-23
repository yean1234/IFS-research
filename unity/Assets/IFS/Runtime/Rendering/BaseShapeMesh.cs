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
            { BaseShapes.Line, "line/1" },
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
                case BaseShapes.Line:
                    BuildLine(m, V("form", "curve"), V("gauge", "normal"), seed);
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
                case BaseShapes.Line:
                    string form = V("form", "curve");
                    p["tubeRadius"] = LineRadius(V("gauge", "normal"));
                    p["tubeSegments"] = LineSides;
                    p["samples"] = LineSamples(form);
                    break;
            }
            return p;
        }

        // ── line ────────────────────────────────────────────────────────────
        // 3차원 곡선을 따라가는 관(둘레 8조각, 평행 이동 틀로 비틀림 없음). 열린 곡선은 양 끝을 반구로 닫는다. 관 반지름은 일정하다
        // (뱀처럼 한쪽이 굵거나 가늘어지지 않게). 올가미(끝에 고리가 달린 열린 곡선)는 만들지 않는다 — knot은 꼬리 없는 닫힌 곡선.
        const int LineSides = 8;
        const int LineCapRings = 3;

        /// <summary>관 반지름(가장 긴 변 1 기준). 기본 크기 0.35 m에서 thin 0.02 → 굵기 약 1.4 cm(1.5 m에서 약 0.53°),
        /// normal 0.035 → 약 2.5 cm, thick 0.06 → 약 4.2 cm. asset-plan 초안(0.015·0.03·0.06)에서 가는 쪽을 올렸다(헤드셋 거리에서
        /// 사라지지 않게, docs/decisions.md D6 구현 세부).</summary>
        public static double LineRadius(string gauge) => gauge == "thin" ? 0.02 : gauge == "thick" ? 0.06 : 0.035;

        static int LineSamples(string form) => form == "tangle" ? 310 : form == "knot" ? 192 : 96;

        static void BuildLine(MeshData m, string form, string gauge, int seed)
        {
            double r = LineRadius(gauge);
            bool closed = form == "knot";
            int n = LineSamples(form);
            var pts = new List<double[]>();
            if (form == "knot")
            {
                // 세잎 매듭(trefoil). 닫힌 곡선, 꼬리 없음
                for (int i = 0; i < n; i++)
                {
                    double t = 2 * Math.PI * i / n;
                    pts.Add(new[] { Math.Sin(t) + 2 * Math.Sin(2 * t), Math.Cos(t) - 2 * Math.Cos(2 * t), -Math.Sin(3 * t) });
                }
            }
            else if (form == "tangle")
            {
                // 공 모양으로 감긴 엉킨 실(실타래): 구(반지름 0.36–0.5) 위를 7바퀴 도는 곡선. 바퀴마다 도는 평면이 천천히 기울어
                // 가닥이 서로 엇갈린다. 평면이 기우는 위상·반지름 흔들림 위상만 seed가 정한다(형상 프리셋 고정값 0).
                // asset-plan 초안의 '구 안의 무작위 걸음'은 시트에서 성긴 낙서처럼 보여 바꿈(docs/decisions.md D6 구현 세부)
                var rng = new SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0x7A11A7UL);
                double ph1 = rng.NextDouble() * 2 * Math.PI, ph2 = rng.NextDouble() * 2 * Math.PI, ph3 = rng.NextDouble() * 2 * Math.PI;
                const double turns = 7;
                for (int i = 0; i < n; i++)
                {
                    double u = (double)i / (n - 1);
                    double t = 2 * Math.PI * turns * u;
                    double phi = 1.15 * Math.Sin(2 * Math.PI * 1.3 * u + ph1) + 2.6 * u;      // 평면 법선의 기울기
                    double psi = 2 * Math.PI * 0.9 * u + ph2;                                 // 평면 법선의 방위
                    double[] nv = { Math.Sin(phi) * Math.Cos(psi), Math.Cos(phi), Math.Sin(phi) * Math.Sin(psi) };
                    double[] e1 = Math.Abs(nv[1]) < 0.9 ? new[] { nv[2], 0, -nv[0] } : new[] { 0, -nv[2], nv[1] };
                    double l1 = Math.Sqrt(e1[0] * e1[0] + e1[1] * e1[1] + e1[2] * e1[2]);
                    e1 = new[] { e1[0] / l1, e1[1] / l1, e1[2] / l1 };
                    double[] e2 = { nv[1] * e1[2] - nv[2] * e1[1], nv[2] * e1[0] - nv[0] * e1[2], nv[0] * e1[1] - nv[1] * e1[0] };
                    double rr = 0.43 + 0.07 * Math.Sin(3.7 * t / turns + ph3);
                    pts.Add(new[] { rr * (Math.Cos(t) * e1[0] + Math.Sin(t) * e2[0]), rr * (Math.Cos(t) * e1[1] + Math.Sin(t) * e2[1]),
                                    rr * (Math.Cos(t) * e1[2] + Math.Sin(t) * e2[2]) });
                }
            }
            else
            {
                // 열린 곡선 하나, 한 번 부드럽게 휨(S자로 굽이치지 않음). 참여자 쪽(+z)으로 조금 나옴
                for (int i = 0; i < n; i++)
                {
                    double t = (double)i / (n - 1);
                    pts.Add(new[] { t - 0.5, 0.22 * Math.Sin(Math.PI * t), 0.08 * Math.Sin(Math.PI * t) });
                }
            }
            // 곡선을 가장 긴 변 1 − 2r로 맞춘 뒤 관을 씌운다(관 두께를 더하면 가장 긴 변이 다시 1 근처)
            double[] lo = { double.MaxValue, double.MaxValue, double.MaxValue }, hi = { double.MinValue, double.MinValue, double.MinValue };
            foreach (var p in pts) for (int a = 0; a < 3; a++) { lo[a] = Math.Min(lo[a], p[a]); hi[a] = Math.Max(hi[a], p[a]); }
            double size = Math.Max(hi[0] - lo[0], Math.Max(hi[1] - lo[1], hi[2] - lo[2]));
            double s = (1 - 2 * r) / size;
            foreach (var p in pts) for (int a = 0; a < 3; a++) p[a] = (p[a] - (lo[a] + hi[a]) / 2) * s;
            m.Tube(pts, r, LineSides, closed, LineCapRings);
        }

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
            public double NextDouble() => (Next() >> 11) * (1.0 / (1UL << 53));
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

            /// <summary>곡선(점 목록)을 따라가는 관. 둘레 sides조각, 평행 이동 틀(닫힌 곡선은 한 바퀴 돈 비틀림을 고르게 나눠 되돌림).
            /// 열린 곡선은 양 끝을 반구(capRings 고리 + 극점)로 닫는다.</summary>
            public void Tube(List<double[]> pts, double r, int sides, bool closed, int capRings)
            {
                int n = pts.Count;
                var T = new double[n][];
                for (int i = 0; i < n; i++)
                {
                    int a = closed ? (i - 1 + n) % n : Math.Max(0, i - 1), b = closed ? (i + 1) % n : Math.Min(n - 1, i + 1);
                    T[i] = Unit(Sub(pts[b], pts[a]));
                }
                var N = new double[n][];
                N[0] = Unit(Perp(T[0]));
                for (int i = 1; i < n; i++) N[i] = Unit(Reject(N[i - 1], T[i]));
                if (closed)
                {
                    var end = Unit(Reject(N[n - 1], T[0]));
                    double twist = Math.Atan2(Dot(Cross(end, N[0]), T[0]), Dot(end, N[0]));
                    for (int i = 1; i < n; i++) N[i] = Rotate(N[i], T[i], twist * i / n);
                }
                var rings = new int[n][];
                for (int i = 0; i < n; i++)
                {
                    var B = Cross(T[i], N[i]);
                    rings[i] = new int[sides];
                    for (int k = 0; k < sides; k++)
                    {
                        double th = 2 * Math.PI * k / sides;
                        double ox = Math.Cos(th) * N[i][0] + Math.Sin(th) * B[0], oy = Math.Cos(th) * N[i][1] + Math.Sin(th) * B[1],
                               oz = Math.Cos(th) * N[i][2] + Math.Sin(th) * B[2];
                        rings[i][k] = Add(pts[i][0] + r * ox, pts[i][1] + r * oy, pts[i][2] + r * oz, ox, oy, oz);
                    }
                }
                int segs = closed ? n : n - 1;
                for (int i = 0; i < segs; i++)
                {
                    var r0 = rings[i];
                    var r1 = rings[(i + 1) % n];
                    for (int k = 0; k < sides; k++) Quad(r0[k], r0[(k + 1) % sides], r1[(k + 1) % sides], r1[k]);
                }
                if (closed) return;
                Cap(pts[n - 1], T[n - 1], N[n - 1], rings[n - 1], r, sides, capRings, 1);
                Cap(pts[0], T[0], N[0], rings[0], r, sides, capRings, -1);
            }

            void Cap(double[] p, double[] t, double[] nrm, int[] ring, double r, int sides, int capRings, int dirSign)
            {
                var T = new[] { t[0] * dirSign, t[1] * dirSign, t[2] * dirSign };
                var B = Cross(t, nrm);
                int[] prev = ring;
                for (int j = 1; j < capRings; j++)
                {
                    double phi = 0.5 * Math.PI * j / capRings;
                    var cur = new int[sides];
                    for (int k = 0; k < sides; k++)
                    {
                        double th = 2 * Math.PI * k / sides;
                        double ox = Math.Cos(th) * nrm[0] + Math.Sin(th) * B[0], oy = Math.Cos(th) * nrm[1] + Math.Sin(th) * B[1],
                               oz = Math.Cos(th) * nrm[2] + Math.Sin(th) * B[2];
                        double nx = Math.Cos(phi) * ox + Math.Sin(phi) * T[0], ny = Math.Cos(phi) * oy + Math.Sin(phi) * T[1],
                               nz = Math.Cos(phi) * oz + Math.Sin(phi) * T[2];
                        cur[k] = Add(p[0] + r * nx, p[1] + r * ny, p[2] + r * nz, nx, ny, nz);
                    }
                    for (int k = 0; k < sides; k++) Quad(prev[k], prev[(k + 1) % sides], cur[(k + 1) % sides], cur[k]);
                    prev = cur;
                }
                int pole = Add(p[0] + r * T[0], p[1] + r * T[1], p[2] + r * T[2], T[0], T[1], T[2]);
                for (int k = 0; k < sides; k++) Tri(pole, prev[k], prev[(k + 1) % sides]);
            }

            static double[] Sub(double[] a, double[] b) => new[] { a[0] - b[0], a[1] - b[1], a[2] - b[2] };
            static double Dot(double[] a, double[] b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
            static double[] Cross(double[] a, double[] b) => new[] { a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0] };
            static double[] Unit(double[] a) { double l = Math.Sqrt(Dot(a, a)); return l < 1e-15 ? new double[] { 1, 0, 0 } : new[] { a[0] / l, a[1] / l, a[2] / l }; }
            static double[] Reject(double[] v, double[] t) { double d = Dot(v, t); return new[] { v[0] - d * t[0], v[1] - d * t[1], v[2] - d * t[2] }; }
            static double[] Perp(double[] t) => Math.Abs(t[1]) < 0.9 ? Reject(new double[] { 0, 1, 0 }, t) : Reject(new double[] { 1, 0, 0 }, t);
            static double[] Rotate(double[] v, double[] axis, double ang)
            {
                // 로드리게스 회전(v ⟂ axis라 마지막 항은 0에 가깝지만 그대로 둔다)
                var c = Cross(axis, v);
                double cs = Math.Cos(ang), sn = Math.Sin(ang), d = Dot(axis, v) * (1 - cs);
                return Unit(new[] { v[0] * cs + c[0] * sn + axis[0] * d, v[1] * cs + c[1] * sn + axis[1] * d, v[2] * cs + c[2] * sn + axis[2] * d });
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
