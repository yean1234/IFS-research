// manifest.json(설계 2.4, 분석 스크립트와의 계약). 필드 이름·순서를 바꾸지 않는다.
// 변형·순서 부분(OwnershipPlan)은 결정적이다. 세션 정보(시각·머리 자세 공급원·Unity 버전)만 실행마다 다르다.
// UnityEngine에 의존하지 않는다.
using System;
using System.Globalization;
using System.IO;
using System.Security.Cryptography;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    public sealed class OwnershipSessionInfo
    {
        public string SessionId;
        /// <summary>spec 파일 이름만(경로는 넣지 않는다 — 로컬 경로·사용자 이름이 기록에 남지 않도록).</summary>
        public string SpecFile;
        public string SpecSha256;
        public string StartedAtUtc;
        /// <summary>xr | desktop</summary>
        public string HeadSource;
        public string UnityVersion;
        public string TaskTextFile;
        public string TaskTextVersion;
        /// <summary>문구 파일에서 status draft인 키(이름순). null이면 빈 목록으로 기록.</summary>
        public string[] TaskTextDraftKeys;
    }

    public static class OwnershipManifest
    {
        /// <summary>0.2: taskText.draftCount·draftKeys, 색 변형 magnitude.deltaE00Composited, config.requireSpecPhrases 추가.
        /// deltaE00은 셰이더 알베도 기준(0.1은 HSL 해석값 기준).</summary>
        public const string RecordVersion = "ifs-ownership/0.2";

        public static JObject Build(OwnershipPlan plan, OwnershipSessionInfo info)
        {
            if (plan == null) throw new ArgumentNullException(nameof(plan));
            if (!plan.Ok) throw new InvalidOperationException("생성 오류가 있는 계획으로 manifest를 만들 수 없습니다: " + string.Join("; ", plan.Errors));
            info = info ?? new OwnershipSessionInfo();
            return new JObject
            {
                ["recordVersion"] = RecordVersion,
                ["generatorVersion"] = OwnershipConfig.GeneratorVersion,
                ["participantNumber"] = plan.ParticipantNumber,
                ["cb"] = plan.Cb,
                ["orderRow"] = plan.OrderRow,
                ["sessionId"] = info.SessionId,
                ["specFile"] = info.SpecFile != null ? FileNameOnly(info.SpecFile) : null,
                ["specSha256"] = info.SpecSha256,
                ["startedAtUtc"] = info.StartedAtUtc,
                ["headSource"] = info.HeadSource,
                ["unityVersion"] = info.UnityVersion,
                ["taskText"] = new JObject
                {
                    ["file"] = info.TaskTextFile,
                    ["version"] = info.TaskTextVersion,
                    ["draftCount"] = info.TaskTextDraftKeys?.Length ?? 0,
                    ["draftKeys"] = new JArray(info.TaskTextDraftKeys ?? new string[0]),
                },
                ["config"] = plan.Config.ToJson(),
                ["flags"] = plan.FlagsJson(),
                ["original"] = plan.OriginalJson(),
                ["variants"] = plan.VariantsJson(),
                ["order"] = new JArray(plan.Order),
            };
        }

        /// <summary>'/'·'\' 어느 쪽 구분자든 마지막 이름만.</summary>
        public static string FileNameOnly(string path)
        {
            int i = Math.Max(path.LastIndexOf('/'), path.LastIndexOf('\\'));
            return i >= 0 ? path.Substring(i + 1) : path;
        }

        public static string Sha256Hex(byte[] bytes)
        {
            using (var sha = SHA256.Create())
            {
                var hash = sha.ComputeHash(bytes);
                var sb = new StringBuilder(hash.Length * 2);
                foreach (var b in hash) sb.Append(b.ToString("x2", CultureInfo.InvariantCulture));
                return sb.ToString();
            }
        }

        public static string Sha256OfFile(string path) => Sha256Hex(File.ReadAllBytes(path));
    }

    public static class OwnershipJson
    {
        /// <summary>들여쓰기 2칸, 줄바꿈 \n, 끝에 \n. 숫자는 InvariantCulture(Newtonsoft 기본).</summary>
        public static string Serialize(JToken token)
        {
            var sw = new StringWriter(CultureInfo.InvariantCulture) { NewLine = "\n" };
            using (var w = new JsonTextWriter(sw) { Formatting = Formatting.Indented, Indentation = 2, IndentChar = ' ' })
                token.WriteTo(w);
            return sw.ToString() + "\n";
        }
    }
}
