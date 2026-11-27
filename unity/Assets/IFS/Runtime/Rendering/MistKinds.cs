// (2.4 선택 슬롯, G74) 안개 입자 모양 form.mistKind — form.type이 mist일 때 종류별로 다르게 그린다. 규칙 기반(LLM·생성 모델 없음).
//   fog   : 안개·수증기·아지랑이 — 납작한 덩어리 5개를 옆으로 넓게·낮게(물체 아래쪽) 깔고, 가장자리 폭을 넓히고 밀도를 낮춘다(옅고 부드러움).
//           노이즈는 세로로 눌러(가로 결) 층처럼 보이게 한다.
//   smoke : 연기·김 — 덩어리 5개를 세로로 쌓은 기둥(아래가 가늘고 위가 굵음, seed로 정한 쪽으로 기움). 노이즈를 세로로 늘이고 높이에 따라
//           비틀어 꼬인 가닥을 만들고, 위로 갈수록 옅어진다(높이 감쇠).
//   dust  : 먼지·모래·가루 — 셰이더 대신 작은 알갱이 메시(DustMesh, seed로 결정론 배치). 렌더러 이름 mistDust.
//   cloud : 구름·먹구름 — 2.4 이전 안개 그림 그대로(덩어리 규칙 MistLumps lumps5/1, 셰이더 프로퍼티 기본값).
//   null  : 종류를 말하지 않음 → cloud와 같은 그림(기본값, defaultsUsed에 form.mistKind — 슬롯이 있는 문서일 때).
// 같은 셰이더(SceneSpecMist)에 종류별 프로퍼티(_EdgeRampMul·_Squash·_NoiseStretch·_Twist·_Strands·_HeightFade)를 넣는다. 프로퍼티 기본값은
// cloud 그림과 같다(곱하기 1·더하기 0) → cloud·null은 2.4 이전과 같은 화소. 수치는 모두 형상 프리셋 기본값(참여자가 말한 값이 아님, 초안).
// form.type을 정하지 않는다: form.type이 mist가 아니면 값은 기록에만 남는다(status not_applied_form).
// UnityEngine에 의존하지 않는다(dotnet 테스트 가능). 같은 (종류, seed) → 같은 배치.
using System;

namespace IFS.SceneSpec
{
    /// <summary>안개 셰이더의 종류별 형상 프리셋(물체 좌표). cloud는 기본값(Default) — 셰이더 프로퍼티 기본값과 같다.</summary>
    public sealed class MistShape
    {
        /// <summary>가장자리 폭 배율(셰이더 IFS_MIST_EDGE_RAMP × 이 값).</summary>
        public double EdgeRampMul { get; }
        /// <summary>밀도장 좌표 배율 (x, y, z) — 각 1 이상. 덩어리 거리를 p ⊙ squash 공간에서 잰다(y가 크면 납작한 덩어리).</summary>
        public double[] Squash { get; }
        /// <summary>노이즈 좌표 배율 (x, y, z). y가 작으면 세로로 늘인 결(가닥), 크면 가로 결(층).</summary>
        public double[] NoiseStretch { get; }
        /// <summary>높이에 따른 노이즈 비틀림(라디안 / 물체 좌표 길이). 0이면 비틀지 않음.</summary>
        public double Twist { get; }
        /// <summary>가닥 세기(0–1). 0이면 가닥 노이즈를 곱하지 않음.</summary>
        public double Strands { get; }
        /// <summary>높이 감쇠 (y0, y1): y0 위로 옅어져 y1에서 0. 둘 다 0이면 감쇠 없음.</summary>
        public double[] HeightFade { get; }

        public MistShape(double edgeRampMul, double[] squash, double[] noiseStretch, double twist, double strands, double[] heightFade)
        {
            EdgeRampMul = edgeRampMul; Squash = squash; NoiseStretch = noiseStretch; Twist = twist; Strands = strands; HeightFade = heightFade;
        }

        /// <summary>셰이더 프로퍼티 기본값(= cloud, 2.4 이전 그림).</summary>
        public static readonly MistShape Default = new MistShape(1.0, new[] { 1.0, 1.0, 1.0 }, new[] { 1.0, 1.0, 1.0 }, 0.0, 0.0, new[] { 0.0, 0.0 });
    }

    public static class MistKinds
    {
        /// <summary>스펙 슬롯 경로(_provenance 키·덮어쓰기 범주 키·defaultsUsed 키).</summary>
        public const string Key = "form.mistKind";
        public const string Fog = "fog", Smoke = "smoke", Dust = "dust", Cloud = "cloud";
        /// <summary>닫힌 값 목록(스키마 2.4 form.mistKind enum과 같다).</summary>
        public static readonly string[] Values = { Fog, Smoke, Dust, Cloud };
        /// <summary>계획 JSON mistKind.status.</summary>
        public const string StatusApplied = "applied", StatusNotAppliedForm = "not_applied_form", StatusNone = "none";
        /// <summary>종류별 수치 판(계획 JSON mistKind.params). 수치를 바꾸면 올린다.</summary>
        public const string ParamsVersion = "mistKinds/1";

        public static bool IsKind(string v) => v != null && Array.IndexOf(Values, v) >= 0;

        /// <summary>종류가 셰이더(덩어리 밀도장)로 그리는 종류인가(fog·smoke·cloud). dust는 알갱이 메시.</summary>
        public static bool IsVolume(string kind) => kind != Dust;

        /// <summary>형상 프리셋(굴곡·노이즈 크기·가장자리·밀도·껍질 열림). cloud·null은 FormRenderPlan.FormPresets["mist"] 그대로.</summary>
        public static FormPreset Preset(string kind)
        {
            switch (kind)
            {
                case Fog: return new FormPreset(0.10f, 0.6f, 1f, 0.45f, 0f);    // 겉면 흔들림 작게(부드러운 가장자리), 큰 얼룩, 얇은 층이라 광학 두께는 조금 높게
                case Smoke: return new FormPreset(0.35f, 1.3f, 1f, 0.65f, 0f);  // 겉면을 많이 흔들어 가닥이 풀리게
                case Dust: return new FormPreset(0f, 2.4f, 0f, 1f, 0f);         // 알갱이: Fade 셰이더 알파 = opacity(가장자리 흐림 없음), 정점 변위 0
                default: return FormRenderPlan.FormPresets["mist"];
            }
        }

        /// <summary>셰이더 형상 프리셋. cloud·null·dust는 MistShape.Default(셰이더 기본값).</summary>
        public static MistShape Shape(string kind)
        {
            switch (kind)
            {
                case Fog:
                    // 덩어리를 세로로 절반(squash y 2)으로 눌러 납작하게, 가장자리 폭 3배(부드럽게), 노이즈는 세로로 눌러 가로 결
                    return new MistShape(3.0, new[] { 1.0, 2.0, 1.0 }, new[] { 1.0, 2.2, 1.0 }, 0.0, 0.0, new[] { 0.0, 0.0 });
                case Smoke:
                    // 노이즈를 세로로 늘이고(y 0.35) 높이에 따라 비틀어(6 rad/단위) 꼬인 가닥, 가닥 세기 0.45, y 0.30부터 옅어져 0.66에서 사라짐
                    return new MistShape(1.3, new[] { 1.0, 1.0, 1.0 }, new[] { 1.0, 0.35, 1.0 }, 6.0, 0.45, new[] { 0.30, 0.66 });
                default:
                    return MistShape.Default;
            }
        }

        /// <summary>배치 규칙 버전(계획 JSON mistRule.version·mistKind.rule). cloud·null은 MistLumps.RuleVersion(2.4 이전과 같음).</summary>
        public static string RuleFor(string kind)
        {
            switch (kind)
            {
                case Fog: return "fog5/1";
                case Smoke: return "smoke5/1";
                case Dust: return DustMesh.RuleVersion;
                default: return MistLumps.RuleVersion;
            }
        }

        /// <summary>덩어리 (x, y, z, r) × MistLumps.Count. 좌표는 밀도장 공간(p ⊙ Squash). cloud·null = MistLumps.Build(seed).</summary>
        public static double[] BuildLumps(string kind, int seed)
        {
            switch (kind)
            {
                case Fog: return BuildFog(seed);
                case Smoke: return BuildSmoke(seed);
                default: return MistLumps.Build(seed);
            }
        }

        // fog: 물체 좌표에서 가운데 덩어리(조금 아래, 가로 반지름 0.34–0.38·세로 그 절반) + 둘레 4개(옆으로 0.26–0.32 떨어짐, 가로 반지름 0.30–0.34 — 서로 많이 겹쳐 한 장의 층으로).
        // 밀도장 공간(y × 2)으로 적는다: 중심 y × 2, 반지름은 그대로(가로 반지름). 가로 끝(중심 거리 + 반지름) ≤ MistLumps.MaxExtent.
        const double FogY = -0.12, FogSquashY = 2.0;

        static double[] BuildFog(int seed)
        {
            var rng = new SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0xF06A11UL);
            var l = new double[MistLumps.Count * 4];
            l[0] = rng.Range(-0.02, 0.02);
            l[1] = FogY * FogSquashY;
            l[2] = rng.Range(-0.02, 0.02);
            l[3] = rng.Range(0.34, 0.38);
            double turn = rng.Range(0.0, 360.0);
            for (int k = 1; k < MistLumps.Count; k++)
            {
                double ang = (turn + (k - 1) * 90.0 + rng.Range(-25.0, 25.0)) * Math.PI / 180.0;
                double rho = rng.Range(0.26, 0.32);
                double r = rng.Range(0.30, 0.34);
                if (rho + r > MistLumps.MaxExtent) r = MistLumps.MaxExtent - rho;
                l[k * 4] = rho * Math.Cos(ang);
                l[k * 4 + 1] = (FogY + rng.Range(-0.04, 0.03)) * FogSquashY;
                l[k * 4 + 2] = rho * Math.Sin(ang);
                l[k * 4 + 3] = r;
            }
            return l;
        }

        // smoke: 아래에서 위로 쌓은 덩어리 5개(가늘다가 굵어짐). seed로 기우는 방향·정도를 정하고 위로 갈수록 더 기운다(피어오르며 흘러감).
        static readonly double[] SmokeY = { -0.46, -0.24, -0.02, 0.20, 0.40 };
        static readonly double[] SmokeR = { 0.15, 0.18, 0.21, 0.23, 0.21 };

        static double[] BuildSmoke(int seed)
        {
            var rng = new SplitMix64((ulong)(uint)seed * 0x9E3779B97F4A7C15UL + 0x5E0CEUL);
            var l = new double[MistLumps.Count * 4];
            double dir = rng.Range(0.0, 2.0 * Math.PI);
            double lean = rng.Range(0.06, 0.12);
            for (int k = 0; k < MistLumps.Count; k++)
            {
                double t = (SmokeY[k] - SmokeY[0]) / (SmokeY[SmokeY.Length - 1] - SmokeY[0]);
                double off = lean * Math.Pow(t, 1.5);
                double x = off * Math.Cos(dir) + rng.Range(-0.03, 0.03);
                double z = off * Math.Sin(dir) + rng.Range(-0.03, 0.03);
                double y = SmokeY[k] + rng.Range(-0.02, 0.02);
                double r = SmokeR[k] * rng.Range(0.92, 1.08);
                double reach = Math.Sqrt(x * x + y * y + z * z);
                if (reach + r > MistLumps.MaxExtent) r = Math.Max(0.08, MistLumps.MaxExtent - reach);
                l[k * 4] = x; l[k * 4 + 1] = y; l[k * 4 + 2] = z; l[k * 4 + 3] = r;
            }
            return l;
        }

        /// <summary>노이즈를 뺀 밀도 뼈대(셰이더와 같은 식): 밀도장 공간 q = p ⊙ squash에서 깊이 f = max_k(r_k − |q − c_k|),
        /// 밀도 = saturate(f / (EdgeRamp × 배율)) × 높이 감쇠. 테스트·문서용.</summary>
        public static double ShapeDensity(string kind, double[] lumps, double x, double y, double z)
        {
            var s = Shape(kind);
            double qx = x * s.Squash[0], qy = y * s.Squash[1], qz = z * s.Squash[2];
            double f = double.NegativeInfinity;
            for (int k = 0; k < lumps.Length / 4; k++)
            {
                double dx = qx - lumps[k * 4], dy = qy - lumps[k * 4 + 1], dz = qz - lumps[k * 4 + 2];
                f = Math.Max(f, lumps[k * 4 + 3] - Math.Sqrt(dx * dx + dy * dy + dz * dz));
            }
            double d = Math.Max(0.0, Math.Min(1.0, f / (MistLumps.EdgeRamp * s.EdgeRampMul)));
            if (s.HeightFade[1] > s.HeightFade[0])
            {
                double t = Math.Max(0.0, Math.Min(1.0, (y - s.HeightFade[0]) / (s.HeightFade[1] - s.HeightFade[0])));
                d *= 1.0 - t * t * (3.0 - 2.0 * t);
            }
            return d;
        }

        /// <summary>SplitMix64 — 작은 결정적 난수(MistLumps·FragmentMesh와 같은 구현).</summary>
        internal sealed class SplitMix64
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
