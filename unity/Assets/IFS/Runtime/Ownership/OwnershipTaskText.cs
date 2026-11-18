// 참여자에게 보여 주는 고정 문구(StreamingAssets/IFS/ownership_task.v0.2.json). IRB 대상 초안 — 코드에 문구를 쓰지 않는다.
// 필드: version, texts.{key}.text · status(spec|draft) · source. 필요한 키가 빠지면 오류(실험을 시작하지 않음).
// 버전: ownership_task.v0.json(0.1, '내 것' 문항만, 마지막 선택 "다섯 개 중") — 0.2 이전 세션 재현용으로 그대로 둔다.
//       ownership_task.v0.2.json(0.2) — 닮음 문항(rating_resemblance·final_choice_resemblance) 추가, 마지막 선택 문구는 {n}(조건 수).
// 평정 문항(config.ratingItem)마다 쓰는 키: resemblance → rating_resemblance·final_choice_resemblance, mine → rating·final_choice.
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
        public const string DefaultRelativePath = "IFS/ownership_task.v0.2.json";
        /// <summary>어느 버전 파일에나 있어야 하는 키(0.1 파일도 읽히도록 '내 것' 문항 키 포함).</summary>
        public static readonly string[] RequiredKeys = { "viewing_intro", "rating", "final_choice", "difference", "done" };
        /// <summary>마지막 선택 문구에서 조건 수로 바꾸는 자리.</summary>
        public const string CountPlaceholder = "{n}";

        public static string RatingKey(string ratingItem) => ratingItem == OwnershipConfig.RatingMine ? "rating" : "rating_resemblance";
        public static string FinalChoiceKey(string ratingItem) => ratingItem == OwnershipConfig.RatingMine ? "final_choice" : "final_choice_resemblance";

        /// <summary>이 평정 문항·조건 수로 세션을 돌릴 수 없는 이유(없으면 빈 목록). 러너 Check가 오류로 보고한다.
        /// 마지막 선택 문구에 {n}이 없으면 조건 5개일 때만 쓸 수 있다(0.1 파일의 "다섯 개 중").</summary>
        public List<string> Problems(string ratingItem, int conditionCount)
        {
            var e = new List<string>();
            foreach (var k in new[] { RatingKey(ratingItem), FinalChoiceKey(ratingItem) })
                if (!_text.ContainsKey(k)) e.Add($"평정 문항 {ratingItem}에 필요한 문구가 없습니다: {k}({FileName ?? "문구 파일"} version {Version})");
            string fc = this[FinalChoiceKey(ratingItem)];
            if (fc != null && !fc.Contains(CountPlaceholder) && conditionCount != OwnershipConfig.BaseConditionCount)
                e.Add($"{FinalChoiceKey(ratingItem)} 문구에 {CountPlaceholder}가 없어 조건 {conditionCount}개에 쓸 수 없습니다({FileName ?? "문구 파일"} version {Version})");
            return e;
        }

        public string RatingText(string ratingItem) => this[RatingKey(ratingItem)];

        /// <summary>마지막 선택 문구({n} → 조건 수).</summary>
        public string FinalChoiceText(string ratingItem, int conditionCount) =>
            this[FinalChoiceKey(ratingItem)]?.Replace(CountPlaceholder, conditionCount.ToString(System.Globalization.CultureInfo.InvariantCulture));

        public string Version { get; private set; }
        public string FileName { get; private set; }
        readonly Dictionary<string, string> _text = new Dictionary<string, string>(StringComparer.Ordinal);
        readonly Dictionary<string, string> _status = new Dictionary<string, string>(StringComparer.Ordinal);
        readonly Dictionary<string, string> _source = new Dictionary<string, string>(StringComparer.Ordinal);

        public string this[string key] => _text.TryGetValue(key, out var t) ? t : null;
        public string Status(string key) => _status.TryGetValue(key, out var s) ? s : null;
        public string Source(string key) => _source.TryGetValue(key, out var s) ? s : null;
        public IEnumerable<string> Keys => _text.Keys;
        public int Count => _text.Count;

        /// <summary>status가 draft인 문구 키(이름순). IRB 확인 전 초안이라 러너가 경고하고 manifest에 남긴다.</summary>
        public List<string> DraftKeys
        {
            get
            {
                var keys = new List<string>();
                foreach (var kv in _status) if (kv.Value == "draft") keys.Add(kv.Key);
                keys.Sort(StringComparer.Ordinal);
                return keys;
            }
        }

        public bool HasDraft => DraftKeys.Count > 0;

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
                t._source[p.Name] = source;
            }
            foreach (var k in RequiredKeys)
                if (!t._text.ContainsKey(k)) throw new FormatException("문구가 없습니다: " + k);
            return t;
        }

        public static OwnershipTaskText Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8), Path.GetFileName(path));
    }
}
