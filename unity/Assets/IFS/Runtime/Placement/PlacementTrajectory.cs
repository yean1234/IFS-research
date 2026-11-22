// 조건 단계의 물체 궤적(trajectory.json, 기록 형식 계약 ifs-placement/0.1 8번). 재생(replay) 조건의 원본으로 쓴다.
//   { version: "ifs-trajectory/0.1", sourceSessionId, sampleHz, startDistanceM, startHeightM, samples: [ { t_ms, x, y, z } ... ] }
//   t_ms = 조건 단계 시작부터의 시각(ms). 표본은 headSampleHz 주기(프레임당 최대 1개)이고, 마지막 표본은 단계가 끝난 시각의 위치다.
// 재생: 같은 시간축에서 앞뒤 표본을 직선 보간한다. 첫 표본 전은 첫 표본, 마지막 표본 뒤는 마지막 표본 자리에 둔다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public struct TrajectorySample
    {
        public long TMs;
        public double X, Y, Z;
        public PVec3 Position => new PVec3(X, Y, Z);
    }

    public sealed class PlacementTrajectory
    {
        public const string Version = "ifs-trajectory/0.1";

        public string SourceSessionId;
        public double SampleHz;
        public double StartDistanceM;
        public double StartHeightM;
        public readonly List<TrajectorySample> Samples = new List<TrajectorySample>();

        public long DurationMs => Samples.Count > 0 ? Samples[Samples.Count - 1].TMs : 0;

        /// <summary>기록한 값과 같은 자리수(0.0001 m)로 넣는다 — 쓰고 다시 읽어도 같은 값이 되도록.</summary>
        public void Add(long tMs, PVec3 p) =>
            Samples.Add(new TrajectorySample { TMs = tMs, X = Math.Round(p.X, 4), Y = Math.Round(p.Y, 4), Z = Math.Round(p.Z, 4) });

        public JObject ToJson() => new JObject
        {
            ["version"] = Version,
            ["sourceSessionId"] = SourceSessionId,
            ["sampleHz"] = SampleHz,
            ["startDistanceM"] = StartDistanceM,
            ["startHeightM"] = StartHeightM,
            ["samples"] = new JArray(Samples.Select(s => new JObject { ["t_ms"] = s.TMs, ["x"] = s.X, ["y"] = s.Y, ["z"] = s.Z })),
        };

        /// <exception cref="FormatException">형식이 맞지 않을 때</exception>
        public static PlacementTrajectory Parse(string json)
        {
            var o = JObject.Parse(json);
            if ((string)o["version"] != Version) throw new FormatException($"version이 {Version}이 아닙니다: {(string)o["version"]}");
            if (!(o["samples"] is JArray arr) || arr.Count == 0) throw new FormatException("samples가 없거나 비어 있습니다");
            var t = new PlacementTrajectory
            {
                SourceSessionId = (string)o["sourceSessionId"],
                SampleHz = (double?)o["sampleHz"] ?? 0,
                StartDistanceM = (double?)o["startDistanceM"] ?? double.NaN,
                StartHeightM = (double?)o["startHeightM"] ?? double.NaN,
            };
            long last = long.MinValue;
            foreach (var s in arr)
            {
                long tm = (long)s["t_ms"];
                if (tm < last) throw new FormatException("t_ms가 거꾸로 갑니다: " + tm);
                last = tm;
                t.Samples.Add(new TrajectorySample { TMs = tm, X = (double)s["x"], Y = (double)s["y"], Z = (double)s["z"] });
            }
            return t;
        }

        public static PlacementTrajectory Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8));

        /// <summary>조건 단계 시작부터 tMs(ms)일 때의 위치(직선 보간, 양 끝은 고정).</summary>
        public PVec3 PositionAt(double tMs)
        {
            if (Samples.Count == 0) return PVec3.Zero;
            if (tMs <= Samples[0].TMs) return Samples[0].Position;
            var lastS = Samples[Samples.Count - 1];
            if (tMs >= lastS.TMs) return lastS.Position;
            int lo = 0, hi = Samples.Count - 1;
            while (hi - lo > 1)
            {
                int mid = (lo + hi) / 2;
                if (Samples[mid].TMs <= tMs) lo = mid; else hi = mid;
            }
            var a = Samples[lo];
            var b = Samples[hi];
            double span = b.TMs - a.TMs;
            double u = span > 0 ? (tMs - a.TMs) / span : 1.0;
            return PVec3.Lerp(a.Position, b.Position, u);
        }

        public string Serialize() => OwnershipJson.Serialize(ToJson());
    }
}
