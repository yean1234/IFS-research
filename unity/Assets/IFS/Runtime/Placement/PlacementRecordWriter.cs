// 배치 실험 기록기(기록 형식 계약 ifs-placement/0.2 — Python 분석기 ifs_chatbot.eval.placement와의 계약. 헤더·필드 이름을 바꾸지 않는다).
// 0.1 → 0.2(2026-11-23, D8·D9): 추가만 했다. manifest에 selection(선택 파일: 이름·sha256·formatVersion·none·selectedCandidateId·
//   finalOverrides·sources, 선택 파일이 없으면 null)과 appliedOverrides(실제로 적용된 덮어쓰기 키 → 그려지는 값, 없으면 {}).
//   CSV 헤더·다른 manifest 키·파일 목록은 그대로다.
//   2026-11-23(G31·G34, 형식 버전은 0.2 유지 — selection 객체 안에 키만 더함): selection.skipped(선택 단계를 건너뜀)·
//   selection.colorChanged(색을 바꿨는지, 0.1 선택 파일이면 null). 분석기는 없는 키를 빈칸으로 읽는다.
//   {recordRoot}/placement/P{번호:000}/{sessionId}/{UTC yyyyMMdd-HHmmss}[-n]/
//     manifest.json · headpose.csv · objpose.csv · events.csv · placement.json · stopdistance.csv · ratings.csv · trajectory.json · summary.json
//   UTF-8(BOM 없음), 숫자는 InvariantCulture, 줄바꿈 \n. CSV는 줄마다 바로 쓰므로 중간에 꺼져도 그때까지 남는다.
// 참여자 자료다. 저장소(git) 밖(기본 persistentDataPath/IFS/sessions)에 둔다. 기존 ownership/ 폴더와 형식은 건드리지 않는다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementRecordWriter : IDisposable
    {
        public const string RecordVersion = "ifs-placement/0.2";

        public const string HeadposeHeader = "time_ms,phase,head_x,head_y,head_z,head_qx,head_qy,head_qz,head_qw,obj_x,obj_y,obj_z,distance_m,angle_deg";
        public const string ObjposeHeader = "time_ms,phase,obj_x,obj_y,obj_z,distance_m,azimuth_deg,height_m,state";
        public const string EventsHeader = "time_ms,event,detail";
        public const string StopDistanceHeader = "trial,practice,direction,start_distance_m,speed_mps,stop_distance_m,rt_ms,timed_out";
        public const string RatingsHeader = "item,when,rating,rt_ms";

        public const string ManifestFile = "manifest.json";
        public const string HeadposeFile = "headpose.csv";
        public const string ObjposeFile = "objpose.csv";
        public const string EventsFile = "events.csv";
        public const string PlacementFile = "placement.json";
        public const string StopDistanceFile = "stopdistance.csv";
        public const string RatingsFile = "ratings.csv";
        public const string TrajectoryFile = "trajectory.json";
        public const string SummaryFile = "summary.json";

        public static readonly string[] AllFiles =
        {
            ManifestFile, HeadposeFile, ObjposeFile, EventsFile, PlacementFile, StopDistanceFile, RatingsFile, TrajectoryFile, SummaryFile,
        };

        static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        readonly StreamWriter _head, _obj, _events, _stop, _ratings;
        int _headUnflushed, _objUnflushed;
        bool _disposed;

        public string Directory { get; }

        /// <summary>폴더 경로만 계산한다(만들지 않음).</summary>
        public static string SessionDirectory(string recordRoot, int participantNumber, string sessionId, DateTime startedUtc) =>
            Path.Combine(recordRoot, "placement", "P" + participantNumber.ToString("000", Inv), OwnershipRecordWriter.SafeName(sessionId),
                startedUtc.ToUniversalTime().ToString("yyyyMMdd-HHmmss", Inv));

        public PlacementRecordWriter(string recordRoot, int participantNumber, string sessionId, DateTime startedUtc)
        {
            if (string.IsNullOrEmpty(recordRoot)) throw new ArgumentException("recordRoot가 비어 있습니다");
            string dir = SessionDirectory(recordRoot, participantNumber, sessionId, startedUtc);
            string baseDir = dir;
            for (int i = 2; System.IO.Directory.Exists(dir); i++) dir = baseDir + "-" + i.ToString(Inv);   // 같은 초에 다시 시작하면 덮어쓰지 않는다
            System.IO.Directory.CreateDirectory(dir);
            Directory = dir;
            _head = Open(HeadposeFile, HeadposeHeader);
            _obj = Open(ObjposeFile, ObjposeHeader);
            _events = Open(EventsFile, EventsHeader);
            _stop = Open(StopDistanceFile, StopDistanceHeader);
            _ratings = Open(RatingsFile, RatingsHeader);
        }

        StreamWriter Open(string name, string header)
        {
            var w = new StreamWriter(Path.Combine(Directory, name), false, Utf8NoBom) { NewLine = "\n" };
            w.WriteLine(header);
            w.Flush();
            return w;
        }

        public void WriteJson(string name, JToken token) => WriteText(name, OwnershipJson.Serialize(token));

        void WriteText(string name, string text)
        {
            var path = Path.Combine(Directory, name);
            var tmp = path + ".tmp";
            File.WriteAllText(tmp, text, Utf8NoBom);
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }

        static string N(double v, string fmt) => double.IsNaN(v) || double.IsInfinity(v) ? "" : v.ToString(fmt, Inv);

        /// <summary>headpose.csv 한 줄. obj가 null이면(물체가 보이지 않음) 물체 칸은 빈칸.</summary>
        public void Head(long timeMs, string phase, HeadPose h, PVec3? obj)
        {
            if (_disposed) return;
            var cells = new List<string>
            {
                timeMs.ToString(Inv), Csv(phase),
                N(h.X, "0.0000"), N(h.Y, "0.0000"), N(h.Z, "0.0000"),
                N(h.Qx, "0.000000"), N(h.Qy, "0.000000"), N(h.Qz, "0.000000"), N(h.Qw, "0.000000"),
            };
            if (obj.HasValue)
            {
                var o = obj.Value;
                OwnershipGeometry.DistanceAngle(h.X, h.Y, h.Z, h.Qx, h.Qy, h.Qz, h.Qw, o.X, o.Y, o.Z, out double dist, out double ang);
                cells.AddRange(new[] { N(o.X, "0.0000"), N(o.Y, "0.0000"), N(o.Z, "0.0000"), N(dist, "0.0000"), N(ang, "0.00") });
            }
            else cells.AddRange(new[] { "", "", "", "", "" });
            _head.WriteLine(string.Join(",", cells));
            if (++_headUnflushed >= 20) { _head.Flush(); _headUnflushed = 0; }
        }

        /// <summary>objpose.csv 한 줄. state ∈ idle | held | system | replay | stop.</summary>
        public void Obj(long timeMs, string phase, PVec3 p, string state)
        {
            if (_disposed) return;
            _obj.WriteLine(string.Join(",", timeMs.ToString(Inv), Csv(phase),
                N(p.X, "0.0000"), N(p.Y, "0.0000"), N(p.Z, "0.0000"),
                N(PlacementGeometry.HorizontalDistance(p), "0.0000"), N(PlacementGeometry.AzimuthDeg(p), "0.00"), N(p.Y, "0.0000"),
                Csv(state)));
            if (++_objUnflushed >= 20) { _obj.Flush(); _objUnflushed = 0; }
        }

        public void Event(long timeMs, string ev, string detail)
        {
            if (_disposed) return;
            _events.WriteLine(string.Join(",", timeMs.ToString(Inv), Csv(ev), Csv(detail)));
            _events.Flush();
        }

        /// <summary>stopdistance.csv 한 줄. timedOut이면 stop_distance_m은 빈칸.</summary>
        public void Stop(int trial, bool practice, string direction, double startM, double speedMps, double? stopM, long rtMs, bool timedOut)
        {
            if (_disposed) return;
            _stop.WriteLine(string.Join(",", trial.ToString(Inv), practice ? "1" : "0", Csv(direction),
                N(startM, "0.0000"), N(speedMps, "0.0000"), timedOut || !stopM.HasValue ? "" : N(stopM.Value, "0.0000"),
                rtMs.ToString(Inv), timedOut ? "1" : "0"));
            _stop.Flush();
        }

        public void Rating(string item, string when, int rating, long rtMs)
        {
            if (_disposed) return;
            _ratings.WriteLine(string.Join(",", Csv(item), Csv(when), rating.ToString(Inv), rtMs.ToString(Inv)));
            _ratings.Flush();
        }

        public static string FormatUtc(DateTime t) => OwnershipRecordWriter.FormatUtc(t);

        /// <summary>summary.json: { completed, abortedAt, endedAtUtc }.</summary>
        public static JObject BuildSummary(bool completed, string abortedAt, DateTime endedUtc) => new JObject
        {
            ["completed"] = completed,
            ["abortedAt"] = completed ? null : abortedAt,
            ["endedAtUtc"] = FormatUtc(endedUtc),
        };

        public static string Csv(string s)
        {
            if (s == null) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        public void Dispose()
        {
            if (_disposed) return;
            _disposed = true;
            foreach (var w in new[] { _head, _obj, _events, _stop, _ratings })
            {
                try { w.Flush(); w.Dispose(); } catch (ObjectDisposedException) { }
            }
        }
    }

    /// <summary>머리 자세(세계 좌표, 단위 쿼터니언).</summary>
    public struct HeadPose
    {
        public double X, Y, Z, Qx, Qy, Qz, Qw;
        public PVec3 Position => new PVec3(X, Y, Z);
        public static HeadPose At(double x, double y, double z) => new HeadPose { X = x, Y = y, Z = z, Qw = 1 };
    }

    public sealed class PlacementSessionInfo
    {
        public int ParticipantNumber;
        public string SessionId;
        /// <summary>spec 파일 이름만(경로는 넣지 않는다 — 로컬 경로·사용자 이름이 기록에 남지 않도록).</summary>
        public string SpecFile;
        public string SpecSha256;
        public DateTime StartedUtc = DateTime.UtcNow;
        /// <summary>xr | desktop</summary>
        public string HeadSource = "desktop";
        /// <summary>desktop | auto | xr</summary>
        public string InputSource = "desktop";
        public string UnityVersion = "";
        public bool AutoMode;
        public string TaskTextFile;
        public string TaskTextVersion;
        public string[] TaskTextDraftKeys;
        /// <summary>replay 원본(파일 이름만, sha256, 원본 sessionId). replay가 아니면 null.</summary>
        public string ReplayFile, ReplaySha256, ReplaySourceSessionId;
        /// <summary>물체 렌더 경계의 반지름(m): 불러온 물체 렌더러 경계 상자(AABB)의 가장 큰 반폭. 구할 수 없으면 null.
        /// 거리 기록은 모두 물체 중심 기준이라, 보이는 가장자리까지의 거리는 대략 이만큼 짧다.</summary>
        public double? ObjectBoundingRadiusM;
        /// <summary>spec에 layout.distance·verticalOffset 값이 있었는데 실험 설정의 시작 자리를 쓰느라 무시했다.</summary>
        public bool LayoutIgnored;
        /// <summary>선택 파일(selection.json). 없으면 null(spec만으로 진행 — manifest selection: null).</summary>
        public PlacementSelection Selection;
        /// <summary>실제로 적용된 덮어쓰기(키 → 그려지는 값). null이면 빈 객체로 기록.</summary>
        public JObject AppliedOverrides;
    }

    public static class PlacementManifest
    {
        /// <summary>manifest space.startPlacementSource: 시작 자리는 참여자가 말한 속성(spec layout)이 아니라 실험 설정이다.</summary>
        public const string StartPlacementSource = "experiment_config";
        public const string LayoutIgnoredTag = "layout_ignored";

        /// <summary>spec layout에 거리·높이 값이 있으면 events.csv warning에 남길 문장(detail이 layout_ignored로 시작). 없으면 null.</summary>
        public static string LayoutIgnoredWarning(double? distance, double? verticalOffset, PlacementConfig cfg)
        {
            if (!distance.HasValue && !verticalOffset.HasValue) return null;
            var inv = CultureInfo.InvariantCulture;
            string Val(double? v) => v.HasValue ? v.Value.ToString("0.###", inv) : "null";
            return $"{LayoutIgnoredTag}: spec layout.distance={Val(distance)}, layout.verticalOffset={Val(verticalOffset)} 대신 " +
                   $"실험 설정 startDistanceM={(cfg?.startDistanceM ?? 0).ToString("0.###", inv)}, startHeightM={(cfg?.startHeightM ?? 0).ToString("0.###", inv)}을 씀(두 조건이 같은 자리에서 시작)";
        }

        public static JObject Build(PlacementConfig cfg, PlacementSessionInfo info)
        {
            if (cfg == null) throw new ArgumentNullException(nameof(cfg));
            info = info ?? new PlacementSessionInfo();
            string mode = cfg.EffectiveControlMode;
            return new JObject
            {
                ["recordVersion"] = PlacementRecordWriter.RecordVersion,
                ["participantNumber"] = info.ParticipantNumber,
                ["sessionId"] = info.SessionId,
                ["specFile"] = info.SpecFile != null ? OwnershipManifest.FileNameOnly(info.SpecFile) : null,
                ["specSha256"] = info.SpecSha256,
                ["startedAtUtc"] = PlacementRecordWriter.FormatUtc(info.StartedUtc),
                ["unityVersion"] = info.UnityVersion,
                ["headSource"] = info.HeadSource,
                ["inputSource"] = info.InputSource,
                ["condition"] = cfg.condition,
                ["controlMode"] = mode,
                ["space"] = new JObject
                {
                    ["floorRadiusM"] = cfg.floorRadiusM,
                    ["ringRadiiM"] = new JArray(Array.ConvertAll(cfg.ringRadiiM ?? new double[0], r => (object)r)),
                    ["showRings"] = cfg.showRings,
                    ["startDistanceM"] = cfg.startDistanceM,
                    ["startHeightM"] = cfg.startHeightM,
                    ["startPlacementSource"] = StartPlacementSource,   // 참여자가 말한 속성이 아니라 실험 설정(spec layout을 쓰지 않음)
                },
                ["object"] = new JObject
                {
                    ["boundingRadiusM"] = info.ObjectBoundingRadiusM.HasValue && info.ObjectBoundingRadiusM.Value > 0
                        ? Math.Round(info.ObjectBoundingRadiusM.Value, 4) : (double?)null,
                },
                ["stopDistance"] = new JObject
                {
                    ["speedMps"] = cfg.stopSpeedMps,
                    ["approachStartM"] = cfg.stopApproachStartM,
                    ["recedeStartM"] = cfg.stopRecedeStartM,
                    ["trialsPerDirection"] = cfg.stopTrialsPerDirection,
                    ["practiceTrials"] = cfg.stopPracticeTrials,
                    ["minM"] = cfg.stopMinM,
                    ["maxM"] = cfg.stopMaxM,
                },
                ["replaySource"] = mode == PlacementConfig.ModeReplay
                    ? new JObject
                    {
                        ["file"] = info.ReplayFile != null ? OwnershipManifest.FileNameOnly(info.ReplayFile) : null,
                        ["sha256"] = info.ReplaySha256,
                        ["sourceSessionId"] = info.ReplaySourceSessionId,
                    }
                    : null,
                ["systemMoveTarget"] = mode == PlacementConfig.ModeSystemMove
                    ? new JObject
                    {
                        ["distanceM"] = cfg.systemMoveTargetDistanceM,
                        ["azimuthDeg"] = cfg.systemMoveTargetAzimuthDeg,
                        ["heightM"] = cfg.systemMoveTargetHeightM,
                    }
                    : null,
                ["taskText"] = new JObject
                {
                    ["file"] = info.TaskTextFile,
                    ["version"] = info.TaskTextVersion,
                    ["draftCount"] = info.TaskTextDraftKeys?.Length ?? 0,
                    ["draftKeys"] = new JArray(info.TaskTextDraftKeys ?? new string[0]),
                },
                ["config"] = cfg.ToJson(),
                // 0.2 추가: 선택 파일(없으면 null)과 실제로 적용된 덮어쓰기(없으면 {})
                ["selection"] = info.Selection?.ManifestJson(),
                ["appliedOverrides"] = info.AppliedOverrides != null ? (JObject)info.AppliedOverrides.DeepClone() : new JObject(),
                ["flags"] = new JObject
                {
                    ["autoMode"] = info.AutoMode,
                    ["stopFirstDirection"] = cfg.FirstDirectionFor(info.ParticipantNumber),
                    ["conditionEndsOnConfirm"] = cfg.conditionEndsOnConfirm,
                    ["requireSpecPhrases"] = cfg.requireSpecPhrases,
                    ["layoutIgnored"] = info.LayoutIgnored,
                },
            };
        }
    }
}
