// 참여자에게 보여 주는 고정 문구(StreamingAssets/IFS/ownership_task.v0.json). IRB 대상 초안 — 코드에 문구를 쓰지 않는다.
// 필드: version, texts.{key}.text · status(spec|draft) · source. 필요한 키가 빠지면 오류(실험을 시작하지 않음).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Ownership
{
    public sealed class OwnershipTaskText
    {
        public const string DefaultRelativePath = "IFS/ownership_task.v0.json";
        public static readonly string[] RequiredKeys = { "viewing_intro", "rating", "final_choice", "difference", "done" };

        public string Version { get; private set; }
        public string FileName { get; private set; }
        readonly Dictionary<string, string> _text = new Dictionary<string, string>(StringComparer.Ordinal);
        readonly Dictionary<string, string> _status = new Dictionary<string, string>(StringComparer.Ordinal);

        public string this[string key] => _text.TryGetValue(key, out var t) ? t : null;
        public string Status(string key) => _status.TryGetValue(key, out var s) ? s : null;
        public IEnumerable<string> Keys => _text.Keys;

        /// <exception cref="FormatException">필요한 필드가 없을 때</exception>
        public static OwnershipTaskText Parse(string json, string fileName = null)
        {
            var o = JObject.Parse(json);
            var t = new OwnershipTaskText { Version = (string)o["version"], FileName = fileName };
            if (string.IsNullOrEmpty(t.Version)) throw new FormatException("version이 없습니다");
            if (!(o["texts"] is JObject texts)) throw new FormatException("texts가 없습니다");
            foreach (var p in texts.Properties())
            {
                if (!(p.Value is JObject item)) throw new FormatException(p.Name + ": 객체가 아닙니다");
                string text = (string)item["text"], status = (string)item["status"], source = (string)item["source"];
                if (string.IsNullOrWhiteSpace(text)) throw new FormatException(p.Name + ": text가 비어 있습니다");
                if (status != "spec" && status != "draft") throw new FormatException(p.Name + ": status는 spec 또는 draft");
                if (string.IsNullOrWhiteSpace(source)) throw new FormatException(p.Name + ": source가 비어 있습니다");
                t._text[p.Name] = text;
                t._status[p.Name] = status;
            }
            foreach (var k in RequiredKeys)
                if (!t._text.ContainsKey(k)) throw new FormatException("문구가 없습니다: " + k);
            return t;
        }

        public static OwnershipTaskText Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8), Path.GetFileName(path));
    }
}
