// 눈높이 보정(G60-3, eyeHeightMode relative). 세션 시작 전 Check 단계에서 실험자 키 H(또는 실험자 화면 단추)로 한 번 잰다:
//   참여자에게 "편하게 똑바로 서서 앞을 봐 주세요"라고 말로 안내(실험자 대본 — 헤드셋 문구 아님) → 20 Hz로 eyeCalibSeconds 동안
//   머리(카메라) 높이와 pitch를 모아 중앙값을 E로 삼는다. 통과 조건: 추적 원점 Floor, 높이 표본 SD ≤ eyeCalibMaxSdM,
//   |pitch 중앙값| ≤ eyeCalibMaxPitchDeg, E ∈ [eyeHeightMinM, eyeHeightMaxM]. 세션 동안 E는 바꾸지 않는다(다시 재면 물체가 움직이므로).
//   데스크톱·자동 시행은 E = eyeHeightReferenceM 고정(source desktop_fixed) — 데스크톱 카메라 높이가 기준값이라 none과 같은 자리.
// UnityEngine에 의존하지 않는다(판정은 dotnet 테스트로 확인).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    /// <summary>세션이 쓰는 눈높이(보정 결과). manifest eyeHeight·events eye_height_calibrated에 남는다.</summary>
    public sealed class EyeHeightInfo
    {
        public const string SourceCalibrated = "calibrated";
        public const string SourceDesktopFixed = "desktop_fixed";

        /// <summary>E(m).</summary>
        public double MeasuredM;
        /// <summary>높이 표본 표준편차(m, n−1). desktop_fixed면 null.</summary>
        public double? SdM;
        /// <summary>머리 pitch 중앙값(도, + = 아래를 봄). desktop_fixed면 null.</summary>
        public double? PitchDeg;
        public int Samples;
        /// <summary>보정 때 추적 원점(예: Floor). desktop_fixed면 "desktop".</summary>
        public string TrackingOrigin;
        /// <summary>calibrated | desktop_fixed</summary>
        public string Source;

        public static EyeHeightInfo DesktopFixed(double referenceM) => new EyeHeightInfo
        {
            MeasuredM = referenceM, SdM = null, PitchDeg = null, Samples = 0, TrackingOrigin = "desktop", Source = SourceDesktopFixed,
        };

        /// <summary>manifest eyeHeight 블록(relative일 때만 manifest 맨 끝에 넣는다).</summary>
        public JObject ManifestJson(PlacementConfig cfg) => new JObject
        {
            ["mode"] = cfg.eyeHeightMode,
            ["referenceM"] = cfg.eyeHeightReferenceM,
            ["measuredM"] = Math.Round(MeasuredM, 4),
            ["offsetM"] = Math.Round(cfg.EyeOffsetFor(MeasuredM), 4),
            ["sdM"] = SdM.HasValue ? Math.Round(SdM.Value, 4) : (double?)null,
            ["pitchDeg"] = PitchDeg.HasValue ? Math.Round(PitchDeg.Value, 2) : (double?)null,
            ["samples"] = Samples,
            ["trackingOrigin"] = TrackingOrigin,
            ["source"] = Source,
        };

        /// <summary>events.csv eye_height_calibrated 상세.</summary>
        public string EventDetail(PlacementConfig cfg)
        {
            var inv = CultureInfo.InvariantCulture;
            return $"measured_m={MeasuredM.ToString("0.0000", inv)};reference_m={cfg.eyeHeightReferenceM.ToString("0.0000", inv)};" +
                   $"offset_m={cfg.EyeOffsetFor(MeasuredM).ToString("0.0000", inv)};sd_m={(SdM.HasValue ? SdM.Value.ToString("0.0000", inv) : "")};" +
                   $"pitch_deg={(PitchDeg.HasValue ? PitchDeg.Value.ToString("0.00", inv) : "")};samples={Samples.ToString(inv)};" +
                   $"origin={(TrackingOrigin ?? "").Replace(';', ' ').Replace('=', ' ')};source={Source}";
        }
    }

    public static class EyeHeightCalibration
    {
        /// <summary>표본 빈도(Hz).</summary>
        public const double SampleHz = 20;

        public sealed class Result
        {
            public bool Ok;
            /// <summary>실패 이유(실험자 화면). 통과면 null.</summary>
            public string Reason;
            public EyeHeightInfo Info;
        }

        /// <summary>eyeCalibSeconds 동안 20 Hz로 모을 표본 수(최소 3).</summary>
        public static int RequiredSamples(PlacementConfig cfg) => Math.Max(3, (int)Math.Round(cfg.eyeCalibSeconds * SampleHz));

        static double Median(List<double> v)
        {
            var s = v.OrderBy(x => x).ToList();
            int n = s.Count;
            return n % 2 == 1 ? s[n / 2] : (s[n / 2 - 1] + s[n / 2]) / 2.0;
        }

        /// <summary>표본(높이 m, pitch 도 — + = 아래를 봄)으로 판정한다. floorOrigin: 추적 원점이 Floor인가.</summary>
        public static Result Evaluate(PlacementConfig cfg, IList<double> heightsM, IList<double> pitchesDeg, bool floorOrigin, string trackingOrigin)
        {
            if (cfg == null) throw new ArgumentNullException(nameof(cfg));
            var inv = CultureInfo.InvariantCulture;
            var h = (heightsM ?? new double[0]).Where(x => !double.IsNaN(x) && !double.IsInfinity(x)).ToList();
            var p = (pitchesDeg ?? new double[0]).Where(x => !double.IsNaN(x) && !double.IsInfinity(x)).ToList();
            var r = new Result();
            if (h.Count < 3)
            {
                r.Reason = $"표본이 모자랍니다({h.Count}개) — 헤드셋 추적을 확인하고 다시 재세요";
                return r;
            }
            double e = Median(h);
            double mean = h.Average();
            double sd = Math.Sqrt(h.Sum(x => (x - mean) * (x - mean)) / (h.Count - 1));
            double pitch = p.Count > 0 ? Median(p) : double.NaN;
            r.Info = new EyeHeightInfo
            {
                MeasuredM = e, SdM = sd, PitchDeg = double.IsNaN(pitch) ? (double?)null : pitch, Samples = h.Count,
                TrackingOrigin = string.IsNullOrEmpty(trackingOrigin) ? (floorOrigin ? "Floor" : "unknown") : trackingOrigin,
                Source = EyeHeightInfo.SourceCalibrated,
            };
            var why = new List<string>();
            if (!floorOrigin) why.Add($"추적 원점이 바닥(Floor)이 아닙니다({r.Info.TrackingOrigin}) — 바닥 기준 높이를 잴 수 없음");
            if (sd > cfg.eyeCalibMaxSdM + 1e-12) why.Add($"높이가 흔들렸습니다(SD {sd.ToString("0.000", inv)} m > {cfg.eyeCalibMaxSdM.ToString("0.000", inv)} m) — 가만히 선 채로 다시");
            if (double.IsNaN(pitch)) why.Add("머리 기울기(pitch)를 읽지 못했습니다");
            else if (Math.Abs(pitch) > cfg.eyeCalibMaxPitchDeg + 1e-12)
                why.Add($"고개가 {(pitch > 0 ? "아래" : "위")}로 {Math.Abs(pitch).ToString("0.0", inv)}° 기울었습니다(한계 {cfg.eyeCalibMaxPitchDeg.ToString("0", inv)}°) — 앞을 보고 다시");
            if (e < cfg.eyeHeightMinM - 1e-12 || e > cfg.eyeHeightMaxM + 1e-12)
                why.Add($"눈높이 {e.ToString("0.000", inv)} m가 범위 [{cfg.eyeHeightMinM.ToString("0.00", inv)}, {cfg.eyeHeightMaxM.ToString("0.00", inv)}] 밖입니다 — 선 자세·바닥 설정(Guardian) 확인");
            r.Ok = why.Count == 0;
            r.Reason = r.Ok ? null : string.Join("; ", why);
            return r;
        }

        /// <summary>쿼터니언(Unity 좌표, +z 정면)의 pitch(도, + = 아래를 봄). 정면 벡터의 y 성분으로 구한다.</summary>
        public static double PitchDegFromQuaternion(double qx, double qy, double qz, double qw)
        {
            double fy = 2.0 * (qy * qz - qw * qx);           // 회전된 +z의 y 성분
            fy = Math.Max(-1.0, Math.Min(1.0, fy));
            return -Math.Asin(fy) * 180.0 / Math.PI;
        }
    }

    /// <summary>보정 표본 모으기(러너가 프레임마다 Add). 20 Hz 간격으로 RequiredSamples개를 모으면 Done.</summary>
    public sealed class EyeHeightSampler
    {
        readonly int _need;
        readonly List<double> _h = new List<double>(), _p = new List<double>();
        double _next = double.NegativeInfinity;

        public EyeHeightSampler(PlacementConfig cfg) { _need = EyeHeightCalibration.RequiredSamples(cfg); }

        public bool Done => _h.Count >= _need;
        public int Count => _h.Count;
        public int Needed => _need;
        public IList<double> Heights => _h;
        public IList<double> Pitches => _p;

        /// <summary>시각 t(초)의 머리 높이·pitch. 20 Hz 간격보다 이르면 버린다.</summary>
        public void Add(double t, double heightM, double pitchDeg)
        {
            if (Done || t < _next - 1e-9) return;
            _h.Add(heightM);
            _p.Add(pitchDeg);
            _next = (double.IsNegativeInfinity(_next) ? t : _next) + 1.0 / EyeHeightCalibration.SampleHz;
        }
    }
}
