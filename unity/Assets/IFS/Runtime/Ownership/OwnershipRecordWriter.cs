// 소유감 실험 기록기(설계 2.4, 분석 스크립트와의 계약 — 헤더·필드 이름을 바꾸지 않는다).
//   {recordRoot}/ownership/P{번호:000}/{sessionId}/{UTC yyyyMMdd-HHmmss}/
//     manifest.json · headpose.csv · ratings.csv · difference.csv · events.csv · summary.json · (있으면) prereport.json
//   UTF-8(BOM 없음), 숫자는 InvariantCulture, 줄바꿈 \n. 줄마다 바로 쓰므로 중간에 꺼져도 그때까지 남는다.
// 참여자 자료다. 저장소(git) 밖(기본 persistentDataPath/IFS/sessions)에 둔다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    /// <summary>머리 자세 표본 하나(세계 좌표, 미터). obj가 없으면(형상이 단독 제시 중이 아님) 빈칸으로 쓴다.</summary>
    public struct HeadSample
    {
        public long TimeMs;
        public string Phase;
        public int Position;
        public string Variant;
        public double HeadX, HeadY, HeadZ, Qx, Qy, Qz, Qw;
        public bool HasObject;
        public double ObjX, ObjY, ObjZ, DistanceM, AngleDeg;
    }

    /// <summary>
    /// 머리 자세 표본 시각 정하기. 한 프레임(Tick 한 번)에 표본은 최대 하나이고, 시각은 그 프레임의 실제 시각이다.
    /// 앞 표본에서 목표 간격(1 / headSampleHz) 이상 지났으면 쓴다. 프레임이 밀려도 같은 자세를 과거 시각 표본 여러 개로
    /// 채우지 않는다(비는 시간은 분석기가 time_ms 차이로 보고 긴 간격을 결측으로 센다).
    /// </summary>
    public sealed class HeadSampleClock
    {
        /// <summary>초. 시뮬레이션 시계의 dt 누적 오차(0.02 × 3 = 0.0599999…)로 한 프레임 늦어지지 않게.</summary>
        public const double Tolerance = 1e-6;

        double _last;
        bool _has;

        public HeadSampleClock(double hz)
        {
            if (!(hz > 0) || double.IsInfinity(hz)) throw new ArgumentOutOfRangeException(nameof(hz), "headSampleHz는 0보다 커야 합니다");
            IntervalSeconds = 1.0 / hz;
        }

        public double IntervalSeconds { get; }

        /// <summary>단계가 바뀌면 부른다. 다음 프레임에 바로 표본을 쓴다.</summary>
        public void Reset() => _has = false;

        public bool Due(double now) => !_has || now - _last >= IntervalSeconds - Tolerance;

        /// <summary>이 프레임(now)에 표본을 쓸 차례면 true를 돌려주고 now를 마지막 표본 시각으로 잡는다.</summary>
        public bool TryTake(double now)
        {
            if (!Due(now)) return false;
            _last = now;
            _has = true;
            return true;
        }
    }

    public sealed class OwnershipRecordWriter : IDisposable
    {
        public const string HeadposeHeader = "time_ms,phase,position,variant,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg";
        public const string RatingsHeader = "position,variant,rating,rt_ms,view_ms,cancelled,item";
        public const string DifferenceHeader = "variant,rating,rt_ms";
        public const string EventsHeader = "time_ms,event,detail";

        public const string ManifestFile = "manifest.json";
        public const string HeadposeFile = "headpose.csv";
        public const string RatingsFile = "ratings.csv";
        public const string DifferenceFile = "difference.csv";
        public const string EventsFile = "events.csv";
        public const string SummaryFile = "summary.json";
        /// <summary>보기 전 보고 파일을 바이트 그대로 복사한 것(있을 때만).</summary>
        public const string PrereportFile = "prereport.json";

        /// <summary>events.csv: 첫 형상 제시 시작의 UTC 시각. detail = ISO 8601(yyyy-MM-ddTHH:mm:ss.fffZ, FormatUtc). 세션에 한 번.</summary>
        public const string FirstViewingUtcEvent = "first_viewing_utc";

        /// <summary>events.csv: 형상 하나를 단독 제시하기 시작한 순간. detail = ViewingStartDetail(분석기가 읽는 고정 형식).</summary>
        public const string ViewingStartEvent = "viewing_start";

        /// <summary>"position={1–n};variant={id}" — 순서·구분자를 바꾸지 않는다(분석기 ifs_chatbot.eval.ownership과의 계약).</summary>
        public static string ViewingStartDetail(int position, string variant) =>
            "position=" + position.ToString(Inv) + ";variant=" + (variant ?? "");

        static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        readonly StreamWriter _head, _ratings, _diff, _events;
        int _headUnflushed;
        bool _disposed;

        public string Directory { get; }

        /// <summary>폴더 경로만 계산한다(만들지 않음).</summary>
        public static string SessionDirectory(string recordRoot, int participantNumber, string sessionId, DateTime startedUtc) =>
            Path.Combine(recordRoot, "ownership", "P" + participantNumber.ToString("000", Inv), SafeName(sessionId),
                startedUtc.ToUniversalTime().ToString("yyyyMMdd-HHmmss", Inv));

        public static string SafeName(string s)
        {
            if (string.IsNullOrWhiteSpace(s)) return "unknown-session";
            var bad = Path.GetInvalidFileNameChars();
            var sb = new StringBuilder(s.Length);
            foreach (char c in s) sb.Append(Array.IndexOf(bad, c) >= 0 || c == '/' || c == '\\' ? '_' : c);
            return sb.ToString();
        }

        public OwnershipRecordWriter(string recordRoot, int participantNumber, string sessionId, DateTime startedUtc)
        {
            if (string.IsNullOrEmpty(recordRoot)) throw new ArgumentException("recordRoot가 비어 있습니다");
            string dir = SessionDirectory(recordRoot, participantNumber, sessionId, startedUtc);
            string baseDir = dir;
            for (int i = 2; System.IO.Directory.Exists(dir); i++) dir = baseDir + "-" + i.ToString(Inv);   // 같은 초에 다시 시작하면 덮어쓰지 않는다
            System.IO.Directory.CreateDirectory(dir);
            Directory = dir;
            _head = Open(HeadposeFile, HeadposeHeader);
            _ratings = Open(RatingsFile, RatingsHeader);
            _diff = Open(DifferenceFile, DifferenceHeader);
            _events = Open(EventsFile, EventsHeader);
        }

        StreamWriter Open(string name, string header)
        {
            var w = new StreamWriter(Path.Combine(Directory, name), false, Utf8NoBom) { NewLine = "\n" };
            w.WriteLine(header);
            w.Flush();
            return w;
        }

        public void WriteManifest(JObject manifest) => WriteText(ManifestFile, OwnershipJson.Serialize(manifest));

        public void WriteSummary(JObject summary) => WriteText(SummaryFile, OwnershipJson.Serialize(summary));

        /// <summary>보기 전 보고 파일 바이트를 그대로 prereport.json으로.</summary>
        public void WritePrereport(byte[] bytes) => WriteBytes(PrereportFile, bytes);

        void WriteText(string name, string text) => WriteBytes(name, Utf8NoBom.GetBytes(text));

        void WriteBytes(string name, byte[] bytes)
        {
            var path = Path.Combine(Directory, name);
            var tmp = path + ".tmp";
            File.WriteAllBytes(tmp, bytes);
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }

        static string N(double v, string fmt) => double.IsNaN(v) || double.IsInfinity(v) ? "" : v.ToString(fmt, Inv);

        public void Head(HeadSample s)
        {
            if (_disposed) return;
            var cells = new List<string>
            {
                s.TimeMs.ToString(Inv), Csv(s.Phase), s.Position.ToString(Inv), Csv(s.Variant),
                N(s.HeadX, "0.0000"), N(s.HeadY, "0.0000"), N(s.HeadZ, "0.0000"),
                N(s.Qx, "0.000000"), N(s.Qy, "0.000000"), N(s.Qz, "0.000000"), N(s.Qw, "0.000000"),
            };
            if (s.HasObject)
                cells.AddRange(new[] { N(s.ObjX, "0.0000"), N(s.ObjY, "0.0000"), N(s.ObjZ, "0.0000"), N(s.DistanceM, "0.0000"), N(s.AngleDeg, "0.00") });
            else cells.AddRange(new[] { "", "", "", "", "" });
            _head.WriteLine(string.Join(",", cells));
            if (++_headUnflushed >= 20) { _head.Flush(); _headUnflushed = 0; }   // 약 1초마다(20 Hz)
        }

        /// <param name="item">평정 문항(config.ratingItem: resemblance | mine). ratings.csv 끝 열.</param>
        public void Rating(int position, string variant, int rating, long rtMs, long viewMs, bool cancelled, string item)
        {
            if (_disposed) return;
            _ratings.WriteLine(string.Join(",", position.ToString(Inv), Csv(variant), rating.ToString(Inv),
                rtMs.ToString(Inv), viewMs.ToString(Inv), cancelled ? "1" : "0", Csv(item)));
            _ratings.Flush();
        }

        public void Difference(string variant, int rating, long rtMs)
        {
            if (_disposed) return;
            _diff.WriteLine(string.Join(",", Csv(variant), rating.ToString(Inv), rtMs.ToString(Inv)));
            _diff.Flush();
        }

        public void Event(long timeMs, string ev, string detail)
        {
            if (_disposed) return;
            _events.WriteLine(string.Join(",", timeMs.ToString(Inv), Csv(ev), Csv(detail)));
            _events.Flush();
        }

        /// <summary>summary.json. ratings = 변형 id → 취소되지 않은 마지막 평정(조건 순서 OwnershipVariantGenerator.ConditionIds).</summary>
        public static JObject BuildSummary(bool completed, string abortedAt, int? finalPosition, string finalVariant, long? finalRtMs,
            IDictionary<string, int> ratings, DateTime endedUtc)
        {
            var r = new JObject();
            if (ratings != null)
                foreach (var id in OwnershipVariantGenerator.ConditionIds.Concat(ratings.Keys.Except(OwnershipVariantGenerator.ConditionIds).OrderBy(k => k, StringComparer.Ordinal)))
                    if (ratings.TryGetValue(id, out int v)) r[id] = v;
            return new JObject
            {
                ["completed"] = completed,
                ["abortedAt"] = abortedAt,
                ["finalChoice"] = finalPosition.HasValue
                    ? new JObject { ["position"] = finalPosition.Value, ["variant"] = finalVariant, ["rt_ms"] = finalRtMs }
                    : null,
                ["ratings"] = r,
                ["endedAtUtc"] = endedUtc.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", Inv),
            };
        }

        public static string FormatUtc(DateTime t) => t.ToUniversalTime().ToString("yyyy-MM-dd'T'HH:mm:ss.fff'Z'", Inv);

        static string Csv(string s)
        {
            if (s == null) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            foreach (var w in new[] { _head, _ratings, _diff, _events })
            {
                try { w.Flush(); w.Dispose(); } catch (ObjectDisposedException) { }
            }
        }
    }
}
