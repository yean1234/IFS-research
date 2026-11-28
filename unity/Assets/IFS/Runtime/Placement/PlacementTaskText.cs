// 배치 실험에서 참여자에게 보여 주는 고정 문구(StreamingAssets/IFS/placement_task.v0.json). IRB 대상 — 코드에 문구를 쓰지 않는다.
// ownership_task.v0.json과 같은 구조(version, protocol, texts.{key}.text · status(spec|draft) · source)에
// 평정 문항용 필드를 더한다: when(pre | post | check, 또는 그 배열), anchors.low · anchors.high(1과 7의 뜻).
// when이 있는 키 = 1–7 평정 문항. 단계마다 파일에 적힌 순서대로 묻는다. 필요한 키가 빠지면 오류(실험을 시작하지 않음).
// 2026-11-23 추가(선택, 기존 파일은 그대로 유효):
//   · anchors의 숫자 키("1"…"7"): 기준점마다의 뜻(예: 1 전혀 그렇지 않다 … 7 완전히 그렇다, 양극 척도면 가운데 4도).
//     low·high가 없으면 숫자 키의 양 끝 값을 low·high로 쓴다. anchors의 다른 키(low·high·숫자 밖)는 오류.
//   · items_instruction(공통), items_instruction_pre · _post · _check(단계별 덧붙임): 평정 단계 첫 문항 앞에 보이는 지시문.
//     공통과 단계별이 둘 다 있으면 공통 뒤에 줄을 바꿔 단계별을 붙인다. 실험자 Enter(다음)로 첫 문항으로 넘어간다.
// 2026-11-23 D8 추가(선택, 기존 파일은 그대로 유효):
//   · min · max(정수): 문항의 평정 범위. 없으면 1–7. 0 ≤ min < max ≤ 100. anchors 숫자 키도 이 범위 안이어야 한다
//     (예: 구별 프로파일의 0–10 문항 — 실험자 키보드는 두 자리 숫자 10까지, 컨트롤러는 가운데 값에서 한 칸씩).
//   · optionalWhen(pre | post | check 또는 배열): 설정 askOptionalItems를 켰을 때만 그 단계에서도 묻는다
//     (예: 두 평정 문항 G13은 when post, optionalWhen pre — 사전 측정은 데스크톱에서 하므로(G11) 헤드셋에서는 기본 사후만).
//   · 설정 disabledItems(문항 키 목록)에 든 문항은 묻지 않는다(예: 기존 "내 것 같다" 문항을 끌 때). 문구 파일은 그대로 둔다.
// 2026-11-24 G53 추가(문구 파일 0.3, 기존 파일은 그대로 유효): 놓기 도움 문구 practice(배치 연습 안내)·placement_range(범위 안내 문장).
//   설정 placementAssist를 켰을 때만 보이고 그때만 필수다. 꺼져 있으면 draftKeys·초안 경고에서도 뺀다(DraftKeysFor).
// 2026-11-26 G60-2 추가(문구 파일 0.6, 기존 파일은 그대로 유효): 반복 멈춤 문구 stop_distance_loop(왕복 멈춤 지시문)·stop_loop_hint(멈춘 동안
//   조작 안내). 설정 stopMode loop일 때만 보이고 그때만 필수다. single(기본)이면 draftKeys·초안 경고에서도 뺀다(DraftKeysFor).
// 2026-11-28 연구 책임자 결정(문구 파일 0.8, 선택 키 — 기존 파일은 그대로 유효): confirm_button_right·_left(확인 버튼 안내, xrHand에 따라 하나),
//   confirm_done(확정 알림), stop_main_start(반복 멈춤 연습 뒤 본 측정 시작 안내, loop일 때만 draftKeys에).
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
        /// <summary>askOptionalItems를 켰을 때만 더 묻는 단계(없으면 빈 배열).</summary>
        public string[] OptionalWhen = new string[0];
        /// <summary>평정 범위(문구 파일 min·max, 기본 1–7).</summary>
        public int Min = DefaultMin;
        public int Max = DefaultMax;
        public const int DefaultMin = 1;
        public const int DefaultMax = 7;
        /// <summary>문구 파일이 쓸 수 있는 범위의 끝(키보드 입력은 최대 세 자리).</summary>
        public const int LowestMin = 0;
        public const int HighestMax = 100;
        /// <summary>기준점별 뜻(anchors의 숫자 키). 없으면 비어 있다.</summary>
        public SortedDictionary<int, string> Points = new SortedDictionary<int, string>();

        /// <summary>기준점 v의 뜻: 숫자 키 → (v가 양 끝이면) low·high → 없으면 null.</summary>
        public string AnchorAt(int v)
        {
            if (Points != null && Points.TryGetValue(v, out var s)) return s;
            if (v == Min) return AnchorLow;
            if (v == Max) return AnchorHigh;
            return null;
        }
    }

    public sealed class PlacementTaskText
    {
        public const string DefaultRelativePath = "IFS/placement_task.v0.json";
        /// <summary>StreamingAssets 안에서 고를 수 있는 문구 파일(이 폴더의 placement_task*.json).</summary>
        public const string TaskTextFolder = "IFS";
        public const string TaskTextPattern = "placement_task*.json";
        /// <summary>평정 지시문 키(선택). 단계별 키는 InstructionKey + "_" + when.</summary>
        public const string InstructionKey = "items_instruction";
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

        /// <summary>세션이 실제로 묻는 문항(파일 순서): when이 맞거나(includeOptional이면) optionalWhen이 맞고, disabled에 없는 것.</summary>
        public List<PlacementItem> ItemsFor(string when, bool includeOptional, ICollection<string> disabled) =>
            _items.Where(i => (i.When.Contains(when) || (includeOptional && i.OptionalWhen.Contains(when)))
                              && (disabled == null || !disabled.Contains(i.Key))).ToList();

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

        // ── 놓기 도움 문구(G53, 2026-11-24, 문구 파일 0.3) ─────────────────
        /// <summary>배치 연습 안내(연습 단계에 보임).</summary>
        public const string PracticeKey = "practice";
        /// <summary>범위 안내 문장(직접 배치 지시문 뒤에 줄을 바꿔 붙임).</summary>
        public const string PlacementRangeKey = "placement_range";
        /// <summary>설정 placementAssist를 켰을 때만 보이는 문구 키. 꺼져 있으면 보일 일이 없어 manifest draftKeys·초안 경고에서 뺀다
        /// (기본값 기록이 G52 전과 같게). 파일에 없어도 되지만, 도움을 켠 세션은 시작을 거부한다(AssistKeysMissing).</summary>
        public static readonly string[] AssistKeys = { PracticeKey, PlacementRangeKey };

        // ── 멈춤 거리 반복 멈춤 문구(G60-2, 2026-11-26, 문구 파일 0.6) ─────────
        /// <summary>왕복 멈춤 지시문(stop_distance 대신).</summary>
        public const string StopLoopKey = "stop_distance_loop";
        /// <summary>멈춘 동안 지시문 아래에 붙는 조작 안내.</summary>
        public const string StopLoopHintKey = "stop_loop_hint";
        /// <summary>설정 stopMode loop일 때만 보이는 문구 키. single(기본)이면 manifest draftKeys·초안 경고에서 뺀다(기본값 기록이 G60 전과 같게).</summary>
        public static readonly string[] LoopKeys = { StopLoopKey, StopLoopHintKey };

        // ── 확인 버튼 안내·확정 알림·본 측정 시작 안내(연구 책임자 결정 2026-11-28, 문구 파일 0.8) ─────────
        // 모두 선택 키: 파일에 없으면 예전처럼 붙이지 않는다(기존 파일은 그대로 유효).
        /// <summary>확인 버튼 안내(주 사용 손 오른손 — A). 확인 버튼을 쓰는 단계의 안내 아래에 줄을 바꿔 붙인다.</summary>
        public const string ConfirmButtonRightKey = "confirm_button_right";
        /// <summary>확인 버튼 안내(주 사용 손 왼손 — X).</summary>
        public const string ConfirmButtonLeftKey = "confirm_button_left";
        /// <summary>확정 알림(확인 버튼을 받아들인 뒤 약 2초). 거리·평가하는 말은 넣지 않는다.</summary>
        public const string ConfirmDoneKey = "confirm_done";
        /// <summary>반복 멈춤에서 연습 라운드 뒤 첫 본 라운드 전 안내(loop일 때만 보임).</summary>
        public const string StopMainStartKey = "stop_main_start";
        /// <summary>loop일 때만 보이지만 없어도 되는 키(LoopKeysMissing에는 들지 않는다).</summary>
        public static readonly string[] LoopOptionalKeys = { StopMainStartKey };

        /// <summary>주 사용 손(xrHand)에 맞는 확인 버튼 안내 키.</summary>
        public static string ConfirmButtonKeyFor(string hand) => hand == PlacementConfig.HandLeft ? ConfirmButtonLeftKey : ConfirmButtonRightKey;

        /// <summary>이 세션이 보일 수 있는 문구 가운데 draft인 키(이름순). assist가 꺼져 있으면 AssistKeys를, loop가 꺼져 있으면 LoopKeys를 뺀다.</summary>
        public List<string> DraftKeysFor(bool assist, bool loop = false) => DraftKeys.Where(k => Visible(k, assist, loop)).ToList();

        /// <summary>설정으로: DraftKeysFor(placementAssist, stopMode loop).</summary>
        public List<string> DraftKeysFor(PlacementConfig cfg) => DraftKeysFor(cfg != null && cfg.placementAssist, cfg != null && cfg.IsStopLoop);

        /// <summary>이 세션이 보일 수 있는 문구 수. assist가 꺼져 있으면 AssistKeys를, loop가 꺼져 있으면 LoopKeys를 뺀다.</summary>
        public int CountFor(bool assist, bool loop = false) => _text.Keys.Count(k => Visible(k, assist, loop));

        static bool Visible(string key, bool assist, bool loop) =>
            (assist || !AssistKeys.Contains(key)) && (loop || (!LoopKeys.Contains(key) && !LoopOptionalKeys.Contains(key)));

        /// <summary>파일에 없는 놓기 도움 문구 키(도움을 켠 세션은 이것이 비어 있어야 시작한다).</summary>
        public List<string> AssistKeysMissing() => AssistKeys.Where(k => !_text.ContainsKey(k)).ToList();

        /// <summary>파일에 없는 반복 멈춤 문구 키(stopMode loop 세션은 이것이 비어 있어야 시작한다).</summary>
        public List<string> LoopKeysMissing() => LoopKeys.Where(k => !_text.ContainsKey(k)).ToList();

        /// <summary>평정 단계(when)의 지시문 키(파일에 있는 것만, 보일 순서). 없으면 빈 목록.</summary>
        public List<string> InstructionKeysFor(string when)
        {
            var keys = new List<string>();
            if (_text.ContainsKey(InstructionKey)) keys.Add(InstructionKey);
            if (when != null && _text.ContainsKey(InstructionKey + "_" + when)) keys.Add(InstructionKey + "_" + when);
            return keys;
        }

        /// <summary>평정 단계(when)의 지시문(공통 + 줄바꿈 + 단계별). 없으면 null.</summary>
        public string InstructionFor(string when)
        {
            var keys = InstructionKeysFor(when);
            return keys.Count == 0 ? null : string.Join("\n", keys.Select(k => _text[k]));
        }

        /// <summary>StreamingAssets/IFS 안의 문구 파일(이름순, StreamingAssets 기준 상대 경로). 폴더가 없으면 빈 목록.</summary>
        public static List<string> ListTaskTextFiles(string streamingAssetsPath)
        {
            var dir = Path.Combine(streamingAssetsPath ?? "", TaskTextFolder);
            if (!Directory.Exists(dir)) return new List<string>();
            return Directory.GetFiles(dir, TaskTextPattern)
                .Select(Path.GetFileName)
                .OrderBy(n => n, StringComparer.Ordinal)
                .Select(n => TaskTextFolder + "/" + n)
                .ToList();
        }

        /// <summary>평정 문항을 참여자 화면에 보일 글: 문항 + 줄바꿈 + "min(…) — max(…)"(기본 "1(…) — 7(…)").</summary>
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
                if (p.Name.StartsWith(InstructionKey, StringComparison.Ordinal))
                    throw new FormatException(p.Name + ": 지시문 키에는 when을 쓰지 않습니다");
                string[] whens = when.Type == JTokenType.Array ? when.Select(w => (string)w).ToArray() : new[] { (string)when };
                if (whens.Length == 0 || whens.Any(w => !WhenValues.Contains(w)))
                    throw new FormatException(p.Name + ": when은 pre | post | check(또는 그 배열)");
                var anchors = item["anchors"] as JObject;
                int min = RangeEnd(item, "min", PlacementItem.DefaultMin, p.Name);
                int max = RangeEnd(item, "max", PlacementItem.DefaultMax, p.Name);
                if (!(min >= PlacementItem.LowestMin && max <= PlacementItem.HighestMax && min < max))
                    throw new FormatException($"{p.Name}: 평정 범위 min {min} · max {max}는 {PlacementItem.LowestMin} ≤ min < max ≤ {PlacementItem.HighestMax}여야 합니다");
                string[] optional = new string[0];
                var ow = item["optionalWhen"];
                if (ow != null && ow.Type != JTokenType.Null)
                {
                    optional = ow.Type == JTokenType.Array ? ow.Select(w => (string)w).ToArray() : new[] { (string)ow };
                    if (optional.Length == 0 || optional.Any(w => !WhenValues.Contains(w)))
                        throw new FormatException(p.Name + ": optionalWhen은 pre | post | check(또는 그 배열)");
                }
                var it = new PlacementItem
                {
                    Key = p.Name, Text = text, When = whens, OptionalWhen = optional, Min = min, Max = max,
                    AnchorLow = (string)anchors?["low"], AnchorHigh = (string)anchors?["high"],
                };
                foreach (var a in anchors?.Properties() ?? Enumerable.Empty<JProperty>())
                {
                    if (a.Name == "low" || a.Name == "high") continue;
                    if (!int.TryParse(a.Name, System.Globalization.NumberStyles.None, System.Globalization.CultureInfo.InvariantCulture, out int v)
                        || v < it.Min || v > it.Max)
                        throw new FormatException($"{p.Name}: anchors의 키는 low | high | {it.Min}–{it.Max} 숫자({a.Name})");
                    string label = (string)a.Value;
                    if (string.IsNullOrWhiteSpace(label)) throw new FormatException($"{p.Name}: anchors.{a.Name}이 비어 있습니다");
                    it.Points[v] = label;
                }
                if (it.AnchorLow == null && it.Points.TryGetValue(it.Min, out var lo)) it.AnchorLow = lo;
                if (it.AnchorHigh == null && it.Points.TryGetValue(it.Max, out var hi)) it.AnchorHigh = hi;
                t._items.Add(it);
            }
            foreach (var p in texts.Properties())
                if (p.Value is JObject o2 && (o2["when"] == null || o2["when"].Type == JTokenType.Null)
                    && (o2["min"] != null || o2["max"] != null || o2["optionalWhen"] != null))
                    throw new FormatException(p.Name + ": min · max · optionalWhen은 평정 문항(when이 있는 키)에만 씁니다");
            foreach (var k in RequiredKeys)
                if (!t._text.ContainsKey(k)) throw new FormatException("문구가 없습니다: " + k);
            return t;
        }

        static int RangeEnd(JObject item, string name, int fallback, string key)
        {
            var v = item[name];
            if (v == null || v.Type == JTokenType.Null) return fallback;
            if (v.Type != JTokenType.Integer) throw new FormatException($"{key}: {name}은 정수여야 합니다(지금 {v.Type})");
            long x = (long)v;
            if (x < int.MinValue || x > int.MaxValue) throw new FormatException($"{key}: {name} {x}가 너무 큽니다");
            return (int)x;
        }

        public static PlacementTaskText Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8), Path.GetFileName(path));

        /// <summary>draft 문구가 있으면 실험자 화면 맨 위·events.csv warning에 남길 한 줄(없으면 null).
        /// assist: 놓기 도움(G53)을 켠 세션이면 true — 꺼져 있으면 도움 문구(AssistKeys)는 보이지 않으니 세지 않는다.</summary>
        public static string DraftNotice(PlacementTaskText text, bool requireSpec, bool assist = false, bool loop = false)
        {
            if (text == null) return null;
            var keys = text.DraftKeysFor(assist, loop);
            if (keys.Count == 0) return null;
            return $"초안 문구 사용 중: {text.FileName ?? "문구 파일"}(version {text.Version})의 문구 {keys.Count}/{text.CountFor(assist, loop)}개가 status draft" +
                   $"(IRB 확인 전) — {string.Join(", ", keys)}. " +
                   (requireSpec ? "requireSpecPhrases가 켜져 있어 시작할 수 없습니다." : "본 실험 자료로 쓰기 전에 spec 문구로 바꾸세요(manifest에 기록됨).");
        }

        /// <summary>requireSpecPhrases가 켜져 있고 draft 문구가 있으면 시작 거부 이유, 아니면 null.
        /// loop: 멈춤 거리 반복 멈춤(G60-2)을 켠 세션이면 true — 꺼져 있으면 LoopKeys는 보이지 않으니 세지 않는다.</summary>
        public static string SpecPhraseRefusal(PlacementTaskText text, bool requireSpec, bool assist = false, bool loop = false) =>
            requireSpec && text != null && text.DraftKeysFor(assist, loop).Count > 0
                ? $"requireSpecPhrases가 켜져 있는데 draft 문구 {text.DraftKeysFor(assist, loop).Count}개({string.Join(", ", text.DraftKeysFor(assist, loop))})가 있어 세션을 시작하지 않습니다"
                : null;
    }
}
