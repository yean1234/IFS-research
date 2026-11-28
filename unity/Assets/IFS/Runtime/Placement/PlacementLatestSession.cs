// 가장 최근 세션 자동 채움(2026-11-28, 연구 책임자 요청). 챗봇이 가장 최근에 내보낸 세션의 spec·선택 파일 짝을 찾는다.
//   챗봇 내보내기 구조(chatbot/ifs_chatbot/controller.py scene_path · selection.py selection_dir·_save — 읽기만 함):
//     spec      <spec 폴더>/<세션ID>.json   (매퍼 비교용 <세션ID>.v0/.v1/.v2.json은 고르지 않는다 — 세션 ID에는 '.'이 없다)
//     선택 파일 <spec 폴더>/../selection/<세션ID>/selection.json   (맨 위 sessionId·specSha256·updatedAt·runnerReady)
//     spec meta: sessionId, participantId(가명 문자열, 웹 화면이 보내지 않아 보통 null), condition(면담 조건 — 헤드셋 place/view가 아님)
//   짝 규칙: 선택 폴더 이름 = selection.sessionId = spec 파일 이름 = spec meta.sessionId(없으면 거부 — CP16-6), selection.specSha256 = spec 파일 바이트 sha256.
//   저장 시각 = selection.updatedAt(없거나 읽지 못하면 파일 수정 시각). 가장 늦은 선택 파일 하나만 본다 — 그것이 짝이 맞지 않으면
//   더 오래된 세션으로 내려가지 않고 아무것도 채우지 않는다(조용히 다른 참여자의 파일이 들어가지 않게).
//   가장 늦은 저장 시각이 지금보다 허용 오차(기본 2분)를 넘게 미래면 시계 오류로 보고 역시 채우지 않는다(CP16-3, FutureTimestamp).
//   참여자 번호는 spec meta.participantId가 숫자(또는 P + 숫자)일 때만 채운다. 세션 ID에서 번호를 짐작하지 않는다(원칙 2와 같은 취지).
//   조건(place/view)은 챗봇 파일에 없으므로 채우지 않는다(spec meta.condition은 면담 조건 "chatbot"이다).
// UnityEngine에 의존하지 않는다(EditMode·dotnet 시험).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text.RegularExpressions;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementLatestSession
    {
        public const string SelectionFileName = "selection.json";
        public const double DefaultStaleMinutes = 30;
        public const double DefaultFutureToleranceMinutes = 2;
        static readonly Regex ParticipantRe = new Regex(@"^[Pp]?0*([1-9][0-9]{0,5})$");

        public sealed class Pick
        {
            public string SessionId;
            public string SpecPath;
            public string SelectionPath;
            public DateTimeOffset SavedAt;
            /// <summary>저장 시각을 selection.updatedAt에서 읽었다(false면 파일 수정 시각).</summary>
            public bool SavedFromFile;
            /// <summary>spec meta.participantId에서 읽은 참여자 번호. 없거나 숫자가 아니면 null.</summary>
            public int? ParticipantNumber;
            /// <summary>spec meta.participantId 원문(가명). 없으면 null.</summary>
            public string ParticipantIdRaw;
            /// <summary>selection.runnerReady가 false였다(챗봇이 아직 러너에 넘길 수 없다고 적음 — 확인 단계에서 거부된다).</summary>
            public bool NotRunnerReady;
        }

        public sealed class Result
        {
            /// <summary>채울 짝. 없으면 null.</summary>
            public Pick Pick;
            /// <summary>가장 최근 선택 파일이 짝이 맞지 않아 채우지 않은 이유(실험자 화면). 맞으면 null.</summary>
            public string Rejected;
            /// <summary>거부한 선택 파일의 세션 ID(폴더 이름).</summary>
            public string RejectedSessionId;
            /// <summary>고른 짝보다 늦게 쓰였는데 선택 파일이 아직 없는 spec의 세션 ID(그 세션이 아직 끝나지 않았을 수 있음). 없으면 null.</summary>
            public string NewerSpecWithoutSelection;
            /// <summary>가장 최근 선택 파일의 저장 시각이 지금보다 허용 오차를 넘게 미래라 채우지 않았다(시계 오류 — 눈에 띄게 경고).</summary>
            public bool FutureTimestamp;
            /// <summary>폴더가 없거나 선택 파일이 하나도 없다(지금 동작 그대로 — 빈 칸).</summary>
            public bool NothingFound => Pick == null && Rejected == null;
        }

        /// <summary>spec 폴더 옆 선택 폴더(<spec 폴더>/../selection).</summary>
        public static string DefaultSelectionRoot(string specFolder) =>
            string.IsNullOrWhiteSpace(specFolder) ? null : Path.GetFullPath(Path.Combine(specFolder, "..", "selection"));

        /// <summary>가장 최근 짝을 찾는다. selectionRoot가 null이면 DefaultSelectionRoot(specFolder). now가 null이면 지금 시각.
        /// 가장 최근 저장 시각이 now + futureToleranceMinutes보다 늦으면 채우지 않는다(더 오래된 세션으로 내려가지도 않는다).</summary>
        public static Result FindLatest(string specFolder, string selectionRoot = null, DateTimeOffset? now = null,
            double futureToleranceMinutes = DefaultFutureToleranceMinutes)
        {
            var nowAt = now ?? DateTimeOffset.Now;
            var r = new Result();
            if (string.IsNullOrWhiteSpace(specFolder) || !Directory.Exists(specFolder)) return r;
            selectionRoot = selectionRoot ?? DefaultSelectionRoot(specFolder);
            if (selectionRoot == null || !Directory.Exists(selectionRoot)) return r;

            var found = new List<(string sid, string path, DateTimeOffset saved, bool fromFile, JObject json, string readError)>();
            foreach (var dir in Directory.GetDirectories(selectionRoot))
            {
                string path = Path.Combine(dir, SelectionFileName);
                if (!File.Exists(path)) continue;
                JObject json = null;
                string readError = null;
                try { json = ReadJson(File.ReadAllText(path)); }
                catch (Exception e) { readError = e.Message; }
                bool fromFile = TryParseTime(json?["updatedAt"], out var saved);
                if (!fromFile) saved = new DateTimeOffset(File.GetLastWriteTimeUtc(path), TimeSpan.Zero);
                found.Add((Path.GetFileName(dir), path, saved, fromFile, json, readError));
            }
            if (found.Count == 0) return r;
            var latest = found.OrderByDescending(f => f.saved).ThenByDescending(f => f.sid, StringComparer.Ordinal).First();

            string sid = latest.sid;
            string specPath = Path.Combine(specFolder, sid + ".json");
            string Reject(string why) { r.Rejected = why; r.RejectedSessionId = sid; return why; }
            if ((latest.saved - nowAt).TotalMinutes > futureToleranceMinutes)
            {
                r.FutureTimestamp = true;
                Reject($"저장 시각 {latest.saved:yyyy-MM-dd HH:mm zzz}이 지금보다 {(latest.saved - nowAt).TotalMinutes:0}분 미래임(PC 시계 또는 파일 시각 오류) — " +
                       "이전 참여자 파일일 수 있어 채우지 않음");
            }
            else if (latest.readError != null || latest.json == null) { Reject("선택 파일을 읽지 못함: " + (latest.readError ?? "JSON 객체가 아님")); }
            else if ((string)latest.json["sessionId"] != sid) Reject($"선택 파일의 sessionId({(string)latest.json["sessionId"] ?? "없음"})가 폴더 이름({sid})과 다름");
            else if (!File.Exists(specPath)) Reject($"짝 spec 파일 {sid}.json이 spec 폴더에 없음");
            else
            {
                byte[] bytes = null;
                JObject spec = null;
                try { bytes = File.ReadAllBytes(specPath); spec = ReadJson(System.Text.Encoding.UTF8.GetString(bytes)); }
                catch (Exception e) { Reject("spec 파일을 읽지 못함: " + e.Message); }
                if (r.Rejected == null)
                {
                    var meta = spec?["meta"] as JObject;
                    string specSid = (string)meta?["sessionId"];
                    string selSha = (string)latest.json["specSha256"];
                    if (specSid == null) Reject($"spec {sid}.json에 meta.sessionId가 없음");
                    else if (specSid != sid) Reject($"spec meta.sessionId({specSid})가 선택 파일 세션({sid})과 다름");
                    else if (string.IsNullOrEmpty(selSha)) Reject("선택 파일에 specSha256이 없음(챗봇이 spec 파일을 남기지 못한 세션)");
                    else if (!string.Equals(selSha, OwnershipManifest.Sha256Hex(bytes), StringComparison.OrdinalIgnoreCase))
                        Reject($"선택 파일의 specSha256이 {sid}.json 바이트와 다름(spec이 나중에 바뀌었거나 다른 세션의 파일)");
                    else
                    {
                        string pid = meta?["participantId"]?.Type == JTokenType.String ? (string)meta["participantId"] : null;
                        r.Pick = new Pick
                        {
                            SessionId = sid,
                            SpecPath = Path.GetFullPath(specPath),
                            SelectionPath = Path.GetFullPath(latest.path),
                            SavedAt = latest.saved,
                            SavedFromFile = latest.fromFile,
                            ParticipantIdRaw = pid,
                            ParticipantNumber = ParseParticipantNumber(pid),
                            NotRunnerReady = latest.json["runnerReady"]?.Type == JTokenType.Boolean && !(bool)latest.json["runnerReady"],
                        };
                    }
                }
            }

            // 고른(또는 거부한) 선택 파일보다 늦게 쓰인 spec 가운데 선택 파일이 없는 것: 그 세션이 아직 끝나지 않았을 수 있다
            var haveSelection = new HashSet<string>(found.Select(f => f.sid), StringComparer.Ordinal);
            var newer = Directory.GetFiles(specFolder, "*.json")
                .Select(p => (sid: Path.GetFileNameWithoutExtension(p), t: File.GetLastWriteTimeUtc(p)))
                .Where(s => s.sid.IndexOf('.') < 0 && !haveSelection.Contains(s.sid) && s.t > latest.saved.UtcDateTime)
                .OrderByDescending(s => s.t).ThenByDescending(s => s.sid, StringComparer.Ordinal)
                .FirstOrDefault();
            r.NewerSpecWithoutSelection = newer.sid;
            return r;
        }

        /// <summary>참여자 번호: "3", "03", "P03", "p3" → 3. 그 밖(빈 값, 0, 글자 섞임)은 null.</summary>
        public static int? ParseParticipantNumber(string participantId)
        {
            if (string.IsNullOrWhiteSpace(participantId)) return null;
            var m = ParticipantRe.Match(participantId.Trim());
            return m.Success && int.TryParse(m.Groups[1].Value, NumberStyles.None, CultureInfo.InvariantCulture, out int n) && n >= 1 ? n : (int?)null;
        }

        /// <summary>저장 시각이 staleMinutes보다 오래됐다. 미래 시각은 FindLatest가 허용 오차로 먼저 거부한다(오차 안의 미래는 오래되지 않은 것).</summary>
        public static bool IsStale(DateTimeOffset savedAt, DateTimeOffset now, double staleMinutes) =>
            (now - savedAt).TotalMinutes > staleMinutes;

        /// <summary>manifest sessionFiles.source: 자동 채움이 이번 세션 칸을 채우지 않았으면 null(키 없음), 채운 그대로면 auto,
        /// 채운 뒤 실험자가 spec·선택 파일 칸을 바꿨으면 auto_overridden(CP16-5).</summary>
        public static string SessionFilesSource(bool filled, bool unchanged) => !filled ? null : unchanged ? "auto" : "auto_overridden";

        /// <summary>"n분 전" 꼴(실험자 화면).</summary>
        public static string AgeText(DateTimeOffset savedAt, DateTimeOffset now)
        {
            double min = (now - savedAt).TotalMinutes;
            if (min < 0) return "방금(시계가 앞섬)";
            if (min < 1) return "1분 안";
            if (min < 120) return ((int)Math.Floor(min)).ToString(CultureInfo.InvariantCulture) + "분 전";
            return (min / 60).ToString("0.#", CultureInfo.InvariantCulture) + "시간 전";
        }

        /// <summary>기록 루트에 이 세션 ID의 배치 기록 폴더(placement/P###/<세션ID>)가 이미 있다.</summary>
        public static bool HasRecord(string recordRoot, string sessionId)
        {
            if (string.IsNullOrWhiteSpace(recordRoot) || string.IsNullOrWhiteSpace(sessionId)) return false;
            string root = Path.Combine(recordRoot, "placement");
            if (!Directory.Exists(root)) return false;
            string safe = OwnershipRecordWriter.SafeName(sessionId);
            return Directory.GetDirectories(root).Any(p => Directory.Exists(Path.Combine(p, safe)));
        }

        static JObject ReadJson(string text)
        {
            using var reader = new JsonTextReader(new StringReader(text ?? "")) { DateParseHandling = DateParseHandling.None };
            return JToken.ReadFrom(reader) as JObject;
        }

        static bool TryParseTime(JToken t, out DateTimeOffset value)
        {
            value = default;
            return t != null && t.Type == JTokenType.String
                && DateTimeOffset.TryParse((string)t, CultureInfo.InvariantCulture, DateTimeStyles.AssumeUniversal, out value);
        }
    }
}
