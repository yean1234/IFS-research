// 실험자 화면의 넷째 제외 범주 알림 줄(G50 (4), 병합 마무리 2026-11-23). UnityEngine에 의존하지 않는다.
//   선택 파일(selection.json)의 safetyFlags(PlacementSelection.SafetyFlags)를 실험자 GUI(PlacementExperimenterGui, OnGUI 화면 좌표 —
//   헤드셋에는 그리지 않음)의 경고 자리에 낼 글로 바꾼다. 참여자 판(PlacementTextPanel)은 이 클래스를 쓰지 않는다.
//   · 진행을 막거나 세션을 멈추지 않는다(VR 진행 여부는 연구자가 정함 — 초안, ⚠ 교수님·IRB 확인).
//   · 글은 연구자용 로그 문자열이다(챗봇 연구자 알림 scene_safety_flag와 같은 머리말). 고정 문구(shared/protocol/)가 아니다 —
//     실험자 화면에 띄울 문구를 고정 문구로 둘지는 사람이 정할 것(decisions「G45–G51 구현 세부」⑤).
//   · 범주·낱말·문장 위치(sentence는 0부터 → "n번째 문장"으로 1부터)·글자 위치·자리·형태 막음을 한 줄에 하나씩.
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementSafetyNotice
    {
        /// <summary>머리말(챗봇 연구자 알림 문자열과 같게).</summary>
        public const string Heading = "넷째 제외 범주(죽음·자해·외상) 낱말";
        /// <summary>진행에 대한 안내(연구자용). 러너는 진행을 막지 않는다.</summary>
        public const string ProceedNote = "진행은 막지 않음 — VR 진행 여부는 연구자가 정함";

        /// <summary>알릴 줄. 선택 파일이 없거나 표시가 없으면 빈 목록. 첫 줄은 요약(범주·개수), 다음 줄부터 자리마다 한 줄.</summary>
        public static IReadOnlyList<string> Lines(PlacementSelection selection)
        {
            var lines = new List<string>();
            if (selection == null || !selection.HasSafetyFlags) return lines;
            var flags = selection.SafetyFlags.OfType<JObject>().ToList();
            string cats = string.Join(", ", selection.SafetyFlagCategories);
            lines.Add($"{Heading}: {flags.Count}곳{(cats.Length > 0 ? " [" + cats + "]" : "")} · {ProceedNote}");
            foreach (var f in flags) lines.Add("  " + Describe(f));
            return lines;
        }

        /// <summary>한 자리: "피 — 1번째 문장, 글자 3–4, 자리 head, 형태 막음".</summary>
        public static string Describe(JObject flag)
        {
            if (flag == null) return "";
            string lemma = Str(flag["lemma"]) ?? "?";
            var parts = new List<string>();
            var sent = flag["sentence"];
            if (sent != null && sent.Type == JTokenType.Integer) parts.Add($"{(long)sent + 1}번째 문장");
            if (flag["charSpan"] is JArray span && span.Count == 2 && span.All(t => t.Type == JTokenType.Integer))
                parts.Add($"글자 {(long)span[0]}–{(long)span[1]}");
            string pos = Str(flag["position"]);
            if (pos != null) parts.Add("자리 " + pos);
            string scope = Str(flag["scope"]);
            if (scope != null && scope != "main") parts.Add("범위 " + scope + (scope == "context" ? "(회상·상황 문장)" : ""));
            var fb = flag["formBlock"];
            if (fb != null && fb.Type == JTokenType.Boolean) parts.Add((bool)fb ? "형태 막음" : "형태 막지 않음(색)");
            return parts.Count == 0 ? lemma : lemma + " — " + string.Join(", ", parts);
        }

        static string Str(JToken t) => t != null && t.Type == JTokenType.String ? (string)t : null;
    }
}
