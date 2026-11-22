// 배치 실험에서 참여자에게 보여 주는 고정 문구(StreamingAssets/IFS/placement_task.v0.json). IRB 대상 — 코드에 문구를 쓰지 않는다.
// ownership_task.v0.json과 같은 구조(version, protocol, texts.{key}.text · status(spec|draft) · source)에
// 평정 문항용 필드를 더한다: when(pre | post | check, 또는 그 배열), anchors.low · anchors.high(1과 7의 뜻).
// when이 있는 키 = 1–7 평정 문항. 단계마다 파일에 적힌 순서대로 묻는다. 필요한 키가 빠지면 오류(실험을 시작하지 않음).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementItem
    {
        public string Key;
        public string Text;
        public string AnchorLow;
        public string AnchorHigh;
        public string[] When;
        public int Min = 1;
        public int Max = 7;
    }

    public sealed class PlacementTaskText
    {
        public const string DefaultRelativePath = "IFS/placement_task.v0.json";
        public const string WhenPre = "pre";
        public const string WhenPost = "post";
        public const string WhenCheck = "check";
        public static readonly string[] WhenValues = { WhenPre, WhenPost, WhenCheck };

        /// <summary>단계 안내 문구 키. condition_* 는 조건별 지시문.</summary>
        public static readonly string[] RequiredKeys =
        {
            "intro", "baseline", "condition_place", "condition_view", "condition_point_select", "wait", "stop_distance", "done",
        };

        public string Version { get; private set; }
        public string Protocol { get; private set; }
        public string FileName { get; private set; }
        readonly Dictionary<string, string> _text = new Dictionary<string, string>(StringComparer.Ordinal);
        readonly Dictionary<string, string> _status = new Dictionary<string, string>(StringComparer.Ordinal);
        readonly List<PlacementItem> _items = new List<PlacementItem>();

        public string this[string key] => _text.TryGetValue(key, out var t) ? t : null;
        public string Status(string key) => _status.TryGetValue(key, out var s) ? s : null;
        public IEnumerable<string> Keys => _text.Keys;
        public int Count => _text.Count;
        public IReadOnlyList<PlacementItem> Items => _items;

        /// <summary>when이 맞는 평정 문항(파일 순서).</summary>
        public List<PlacementItem> ItemsFor(string when) => _items.Where(i => i.When.Contains(when)).ToList();

        /// <summary>status가 draft인 문구 키(이름순).</summary>
        public List<string> DraftKeys
        {
            get
            {
                var keys = _status.Where(kv => kv.Value == "draft").Select(kv => kv.Key).ToList();
                keys.Sort(StringComparer.Ordinal);
                return keys;
            }
        }

        public bool HasDraft => DraftKeys.Count > 0;

        /// <summary>평정 문항을 참여자 화면에 보일 글: 문항 + 줄바꿈 + "1(…) — 7(…)".</summary>
        public static string ItemDisplay(PlacementItem item)
        {
            if (item == null) return null;
            if (string.IsNullOrEmpty(item.AnchorLow) && string.IsNullOrEmpty(item.AnchorHigh)) return item.Text;
            return item.Text + "\n" + item.Min + "(" + item.AnchorLow + ") — " + item.Max + "(" + item.AnchorHigh + ")";
        }

        /// <exception cref="FormatException">필요한 필드가 없을 때</exception>
        public static PlacementTaskText Parse(string json, string fileName = null)
        {
            var o = JObject.Parse(json);
            var t = new PlacementTaskText { Version = (string)o["version"], Protocol = (string)o["protocol"], FileName = fileName };
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
                var when = item["when"];
                if (when == null || when.Type == JTokenType.Null) continue;
                string[] whens = when.Type == JTokenType.Array ? when.Select(w => (string)w).ToArray() : new[] { (string)when };
                if (whens.Length == 0 || whens.Any(w => !WhenValues.Contains(w)))
                    throw new FormatException(p.Name + ": when은 pre | post | check(또는 그 배열)");
                var anchors = item["anchors"] as JObject;
                t._items.Add(new PlacementItem
                {
                    Key = p.Name, Text = text, When = whens,
                    AnchorLow = (string)anchors?["low"], AnchorHigh = (string)anchors?["high"],
                });
            }
            foreach (var k in RequiredKeys)
                if (!t._text.ContainsKey(k)) throw new FormatException("문구가 없습니다: " + k);
            return t;
        }

        public static PlacementTaskText Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8), Path.GetFileName(path));

        /// <summary>draft 문구가 있으면 실험자 화면 맨 위·events.csv warning에 남길 한 줄(없으면 null).</summary>
        public static string DraftNotice(PlacementTaskText text, bool requireSpec)
        {
            if (text == null || !text.HasDraft) return null;
            var keys = text.DraftKeys;
            return $"초안 문구 사용 중: {text.FileName ?? "문구 파일"}(version {text.Version})의 문구 {keys.Count}/{text.Count}개가 status draft" +
                   $"(IRB 확인 전) — {string.Join(", ", keys)}. " +
                   (requireSpec ? "requireSpecPhrases가 켜져 있어 시작할 수 없습니다." : "본 실험 자료로 쓰기 전에 spec 문구로 바꾸세요(manifest에 기록됨).");
        }

        /// <summary>requireSpecPhrases가 켜져 있고 draft 문구가 있으면 시작 거부 이유, 아니면 null.</summary>
        public static string SpecPhraseRefusal(PlacementTaskText text, bool requireSpec) =>
            requireSpec && text != null && text.HasDraft
                ? $"requireSpecPhrases가 켜져 있는데 draft 문구 {text.DraftKeys.Count}개({string.Join(", ", text.DraftKeys)})가 있어 세션을 시작하지 않습니다"
                : null;
    }
}
