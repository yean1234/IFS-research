// 보기 전 보고 파일(shared/schemas/prereport.v0.json)을 세션에 붙이는 일. UnityEngine에 의존하지 않는다.
//   읽는 것은 specSha256 · altSpecSha256(값만) · sessionId · createdAtUtc뿐이다.
//   지금 spec 해시가 specSha256과 같으면 matchedBy primary, altSpecSha256의 값 중 하나와 같으면 alt(분석기와 같은 규칙). 고른 값·확정 여부(①②③)는 읽지 않으며
//   자극 생성·순서·화면 표시에 쓰지 않는다(생성기는 이 클래스를 모른다). 파일은 기록 폴더에 바이트 그대로 복사한다.
using System;
using System.IO;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    public sealed class OwnershipPrereport
    {
        public const string StatusPresent = "있음";
        public const string StatusMissing = "없음";
        public const string StatusMismatch = "해시 불일치";

        /// <summary>파일 이름만(경로 없음).</summary>
        public string File;
        public string Sha256;
        public string SpecSha256;
        public bool SpecSha256Match;
        /// <summary>primary | alt | null(불일치)</summary>
        public string MatchedBy;
        /// <summary>기록 폴더에 복사한 시각(UTC, 밀리초, Z). 복사 전에는 null.</summary>
        public string CopiedAtUtc;
        public string SessionId;
        public string CreatedAtUtc;
        /// <summary>읽은 원래 바이트(기록 폴더에 그대로 복사).</summary>
        public byte[] Bytes;

        /// <exception cref="FormatException">JSON 객체가 아닐 때</exception>
        public static OwnershipPrereport FromBytes(byte[] bytes, string fileName, string currentSpecSha256)
        {
            if (bytes == null) throw new ArgumentNullException(nameof(bytes));
            JObject o;
            try
            {
                string text = new System.Text.UTF8Encoding(false).GetString(bytes);
                using (var r = new JsonTextReader(new StringReader(text)) { DateParseHandling = DateParseHandling.None })
                    o = JToken.ReadFrom(r) as JObject;
            }
            catch (JsonException e) { throw new FormatException("보기 전 보고가 JSON이 아닙니다: " + e.Message); }
            if (o == null) throw new FormatException("보기 전 보고가 JSON 객체가 아닙니다");
            string Str(string k) => o[k] != null && o[k].Type == JTokenType.String ? (string)o[k] : null;
            var p = new OwnershipPrereport
            {
                File = fileName != null ? OwnershipManifest.FileNameOnly(fileName) : null,
                Sha256 = OwnershipManifest.Sha256Hex(bytes),
                SpecSha256 = Str("specSha256"),
                SessionId = Str("sessionId"),
                CreatedAtUtc = Str("createdAtUtc"),
                Bytes = (byte[])bytes.Clone(),
            };
            bool Same(string a) => a != null && currentSpecSha256 != null && string.Equals(a, currentSpecSha256, StringComparison.OrdinalIgnoreCase);
            if (Same(p.SpecSha256)) p.MatchedBy = "primary";
            else if (o["altSpecSha256"] is JObject alt)
                foreach (var prop in alt.Properties())
                    if (prop.Value.Type == JTokenType.String && Same((string)prop.Value)) { p.MatchedBy = "alt"; break; }
            p.SpecSha256Match = p.MatchedBy != null;
            return p;
        }

        public static OwnershipPrereport Load(string path, string currentSpecSha256) =>
            FromBytes(System.IO.File.ReadAllBytes(path), Path.GetFileName(path), currentSpecSha256);

        public JObject ToJson() => new JObject
        {
            ["file"] = File,
            ["sha256"] = Sha256,
            ["specSha256"] = SpecSha256,
            ["specSha256Match"] = SpecSha256Match,
            ["matchedBy"] = MatchedBy,
            ["sessionId"] = SessionId,
            ["createdAtUtc"] = CreatedAtUtc,
            ["copiedAtUtc"] = CopiedAtUtc,
        };

        /// <summary>실험자 화면 한 단어: 있음 / 없음 / 해시 불일치.</summary>
        public static string Status(OwnershipPrereport p) => p == null ? StatusMissing : p.SpecSha256Match ? StatusPresent : StatusMismatch;

        /// <summary>requirePrereport가 켜져 있는데 보고가 없거나 spec 해시가 다르면 시작 거부 이유, 아니면 null.</summary>
        public static string Refusal(OwnershipPrereport p, bool require)
        {
            if (!require) return null;
            if (p == null) return "requirePrereport가 켜져 있는데 보기 전 보고 파일이 없어 세션을 시작하지 않습니다";
            if (!p.SpecSha256Match) return $"requirePrereport가 켜져 있는데 보기 전 보고({p.File})의 specSha256·altSpecSha256 어디에도 지금 spec 파일의 해시가 없어 세션을 시작하지 않습니다";
            return null;
        }
    }
}
