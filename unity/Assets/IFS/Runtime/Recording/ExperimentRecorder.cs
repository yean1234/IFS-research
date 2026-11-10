// 실험 기록 — {root}/{sessionId}/ 에 initialScene.json · finalScene.json · events.csv.
// 참여자 데이터다. 저장소(git) 밖(기본: Application.persistentDataPath/IFS/sessions)에 둔다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    public sealed class ExperimentRecorder : IDisposable
    {
        public const string RecordVersion = "ifs-vr-scene-record/0.1";
        public const string CsvHeader = "time_ms,param,from,to,distance_m";
        static readonly UTF8Encoding Utf8NoBom = new UTF8Encoding(false);

        readonly Stopwatch _clock = Stopwatch.StartNew();
        readonly StreamWriter _events;
        readonly JObject _context;
        bool _finalWritten;

        public string Directory { get; }
        public long ElapsedMs => _clock.ElapsedMilliseconds;

        /// <param name="root">기록 루트. 그 아래 sessionId 폴더를 만든다.</param>
        /// <param name="sessionId">SceneSpec meta.sessionId(없으면 파일 이름).</param>
        public ExperimentRecorder(string root, string sessionId, SceneSpecV2 spec, string specPath)
        {
            sessionId = string.IsNullOrEmpty(sessionId) ? "unknown-session" : sessionId;
            var dir = Path.Combine(root, sessionId);
            if (File.Exists(Path.Combine(dir, "initialScene.json")))
            {
                // 같은 세션을 다시 띄우면 기존 기록을 덮어쓰지 않고 하위 폴더에 남긴다.
                dir = Path.Combine(dir, "rerun-" + DateTime.UtcNow.ToString("yyyyMMdd-HHmmss", CultureInfo.InvariantCulture));
            }
            System.IO.Directory.CreateDirectory(dir);
            Directory = dir;
            _context = new JObject
            {
                ["recordVersion"] = RecordVersion,
                ["sessionId"] = spec.Meta.SessionId,
                ["participantId"] = spec.Meta.ParticipantId,
                ["condition"] = spec.Meta.Condition,
                ["specVersion"] = spec.Meta.SpecVersion,
                ["sourceTextHash"] = spec.Meta.SourceTextHash,
                ["specPath"] = specPath,
            };
            _events = new StreamWriter(Path.Combine(dir, "events.csv"), false, Utf8NoBom);
            _events.WriteLine(CsvHeader);
            _events.Flush();
        }

        /// <summary>처음 로드한 값. rawSpecJson은 읽은 파일 그대로(분석 때 원본과 대조).</summary>
        public void WriteInitial(SceneParams initial, string rawSpecJson, IEnumerable<string> notes = null)
        {
            var o = (JObject)_context.DeepClone();
            o["kind"] = "initial";
            o["recordedAtUtc"] = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
            o["params"] = JObject.FromObject(initial.ToRecord());
            o["defaultsUsed"] = new JArray(initial.DefaultsUsed);
            o["inferredUsed"] = new JArray(initial.InferredUsed);
            o["notes"] = new JArray((notes ?? Enumerable.Empty<string>()).ToArray());
            o["spec"] = JToken.Parse(rawSpecJson);
            WriteJson("initialScene.json", o);
        }

        /// <summary>참여자 조정 한 번. from/to는 0–1 값(수치) 또는 이름(범주).</summary>
        public void RecordChange(string param, string from, string to, double distanceM)
        {
            _events.WriteLine(string.Join(",",
                ElapsedMs.ToString(CultureInfo.InvariantCulture), Csv(param), Csv(from), Csv(to),
                double.IsNaN(distanceM) ? "" : distanceM.ToString("0.000", CultureInfo.InvariantCulture)));
            _events.Flush();   // 중간에 꺼져도 남도록
        }

        /// <summary>참여자 조정 후 값 + 조정량(같은 0–1 척도의 차이).</summary>
        public void WriteFinal(SceneParams initial, SceneParams final)
        {
            var o = (JObject)_context.DeepClone();
            o["kind"] = "final";
            o["recordedAtUtc"] = DateTime.UtcNow.ToString("o", CultureInfo.InvariantCulture);
            o["elapsedMs"] = ElapsedMs;
            o["params"] = JObject.FromObject(final.ToRecord());
            o["defaultsUsed"] = new JArray(initial.DefaultsUsed);
            var deltas = SceneParams.Deltas(initial, final);
            o["deltas"] = JObject.FromObject(deltas);
            o["adjustedParams"] = new JArray(deltas.Where(kv => Math.Abs(kv.Value) > 1e-9).Select(kv => kv.Key)
                .Concat(SceneParams.ChangedCategories(initial, final)).ToArray());
            o["adjustmentRms"] = SceneParams.AdjustmentRms(initial, final);
            WriteJson("finalScene.json", o);
            _finalWritten = true;
        }

        public bool FinalWritten => _finalWritten;

        public static string FormatNumber(double v) => v.ToString("0.####", CultureInfo.InvariantCulture);

        void WriteJson(string name, JObject o)
        {
            var path = Path.Combine(Directory, name);
            var tmp = path + ".tmp";
            File.WriteAllText(tmp, o.ToString(Formatting.Indented), Utf8NoBom);
            if (File.Exists(path)) File.Delete(path);
            File.Move(tmp, path);
        }

        static string Csv(string s)
        {
            if (s == null) return "";
            return s.IndexOfAny(new[] { ',', '"', '\n', '\r' }) >= 0 ? "\"" + s.Replace("\"", "\"\"") + "\"" : s;
        }

        public void Dispose() => _events?.Dispose();
    }
}
