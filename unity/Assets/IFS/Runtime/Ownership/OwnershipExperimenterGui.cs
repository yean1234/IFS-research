// 실험자 화면(IMGUI, 데스크톱 창에만 보인다 — 헤드셋 화면에는 그리지 않는다). 설계 2.2의 Setup·SpecCheck와 진행 상태.
// 참여자에게 보이는 글은 ParticipantTextDisplay(월드 공간)가 맡는다. 이 화면에는 원본 여부·남은 시간이 보이지만 참여자 화면에는 없다.
using System.Linq;
using UnityEngine;

namespace IFS.SceneSpec.Ownership
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Ownership/Experimenter GUI")]
    public sealed class OwnershipExperimenterGui : MonoBehaviour
    {
        [SerializeField] OwnershipRunner runner = null;
        [Tooltip("화면 왼쪽에 차지하는 폭(px)")] [SerializeField] float panelWidth = 760f;
        [SerializeField] bool visible = true;

        Vector2 _scroll, _listScroll;
        GUIStyle _wrap;

        public void Configure(OwnershipRunner r) => runner = r;

        void OnGUI()
        {
            if (runner == null) return;
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F1) visible = !visible;
            if (!visible) { GUI.Label(new Rect(8, 8, 300, 24), "F1: 실험자 화면 보이기"); return; }
            if (_wrap == null) _wrap = new GUIStyle(GUI.skin.label) { wordWrap = true, richText = true };

            GUILayout.BeginArea(new Rect(8, 8, Mathf.Min(panelWidth, Screen.width - 16), Screen.height - 16), GUI.skin.box);
            _scroll = GUILayout.BeginScrollView(_scroll);
            GUILayout.Label($"<b>소유감 실험</b> — 단계: {runner.Phase}   머리: {runner.HeadSource}   (F1 숨기기)", _wrap);
            switch (runner.Phase)
            {
                case OwnershipPhase.Setup: DrawSetup(); break;
                case OwnershipPhase.SpecCheck: DrawSpecCheck(); break;
                case OwnershipPhase.Done: DrawDone(); break;
                default: DrawRunning(); break;
            }
            DrawMessages();
            GUILayout.EndScrollView();
            GUILayout.EndArea();
            // 글 입력 칸은 Setup에만 있다. 다른 단계에서 남은 포커스가 Enter·숫자 키를 삼키지 않도록 비운다.
            if (runner.Phase != OwnershipPhase.Setup && GUIUtility.keyboardControl != 0) GUIUtility.keyboardControl = 0;
            runner.GuiHasKeyboardFocus = runner.Phase == OwnershipPhase.Setup && GUIUtility.keyboardControl != 0;
        }

        // 문구 파일에 draft 문구가 있으면 Setup·SpecCheck 맨 위에 굵은 주황 줄로 띄운다.
        void DrawDraftNotice()
        {
            string notice = runner.DraftPhraseNotice;
            if (notice == null) return;
            GUILayout.Label("<size=15><b><color=#ff9a30>[초안 문구] " + notice + "</color></b></size>", _wrap);
        }

        void DrawSetup()
        {
            DrawDraftNotice();
            if (runner.Config.requireSpecPhrases) GUILayout.Label("requireSpecPhrases 켬: draft 문구가 있으면 세션을 시작하지 않습니다.", _wrap);
            GUILayout.Label("1. 참여자 번호(1 이상 정수)");
            runner.ParticipantNumberText = GUILayout.TextField(runner.ParticipantNumberText ?? "", GUILayout.Width(120));
            GUILayout.Label("2. spec 폴더");
            GUILayout.BeginHorizontal();
            runner.SpecFolderText = GUILayout.TextField(runner.SpecFolderText ?? "", GUILayout.Width(560));
            if (GUILayout.Button("목록 새로고침", GUILayout.Width(110))) runner.RefreshSpecList();
            GUILayout.EndHorizontal();
            GUILayout.Label("   (비우면 " + runner.ResolvedSpecFolder + ")", _wrap);
            _listScroll = GUILayout.BeginScrollView(_listScroll, GUILayout.Height(180));
            if (runner.SpecFiles.Count == 0) GUILayout.Label("   .json 파일이 없습니다");
            foreach (var f in runner.SpecFiles)
                if (GUILayout.Button((f.IsVariantFile ? "[변형 파일] " : "") + f.Name, GUILayout.ExpandWidth(true)))
                    runner.SpecPathText = f.Path;
            GUILayout.EndScrollView();
            GUILayout.Label("3. spec 경로(목록에서 고르거나 직접 입력)");
            runner.SpecPathText = GUILayout.TextField(runner.SpecPathText ?? "");
            if (GUILayout.Button("확인 → SpecCheck", GUILayout.Height(32))) runner.Check();
        }

        void DrawSpecCheck()
        {
            var plan = runner.Plan;
            DrawDraftNotice();
            GUILayout.Label($"참여자 {runner.ParticipantNumberText}  cb={plan?.Cb}  순서 행={plan?.OrderRow}  순서: {(plan != null ? string.Join(" → ", plan.Order) : "")}", _wrap);
            GUILayout.Label("<b>속성별 말한 값 / 기본값 / 근거 없음</b>  (슬롯 | spec 값 | 구분 | 근거 말 | 해석값)  — 구분은 _provenance 기준(변형 source와 같음)", _wrap);
            foreach (var r in runner.SpecTable())
            {
                GUI.color = r[2] == OwnershipRunner.LabelStated ? Color.white
                    : r[2] == OwnershipRunner.LabelUnsupported ? new Color(1f, 0.8f, 0.35f, 1f)
                    : new Color(0.8f, 0.8f, 0.8f, 1f);
                GUILayout.Label($"  {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]}", _wrap);
            }
            GUI.color = Color.white;
            GUILayout.Label("<b>쓰지 못한 말</b>", _wrap);
            foreach (var l in runner.LeftoverLines()) GUILayout.Label(l, _wrap);
            if (plan != null)
            {
                GUILayout.Label($"<b>원본</b>: {plan.OriginalRendered} (모양 모형 {plan.OriginalShapeModel}), 유효 불투명도 {plan.EffectiveOpacity:0.###}", _wrap);
                GUILayout.Label("<b>변형 4개</b>", _wrap);
                foreach (var v in plan.Variants.Where(v => !v.IsOriginal))
                {
                    string flags = string.Join(" ", new[]
                    {
                        v.SaidNotRendered ? "saidNotRendered" : null, v.Forced ? "forced" : null,
                        v.BelowTarget ? "belowTarget" : null, v.MotionAltersScale ? "motionAltersScale" : null,
                    }.Where(x => x != null));
                    GUILayout.Label("  " + v.Describe() + (flags.Length > 0 ? "  [플래그: " + flags + "]" : ""), _wrap);
                }
                if (plan.LowVisibility) { GUI.color = Color.yellow; GUILayout.Label("lowVisibility: 원본이 잘 보이지 않을 수 있습니다", _wrap); GUI.color = Color.white; }
            }
            GUILayout.BeginHorizontal();
            GUI.enabled = runner.Errors.Count == 0 && plan != null && plan.Ok;
            if (GUILayout.Button("시작 (Enter)", GUILayout.Height(32))) runner.StartSession();
            GUI.enabled = true;
            if (GUILayout.Button("뒤로 (Esc)", GUILayout.Height(32), GUILayout.Width(120))) runner.BackToSetup();
            GUILayout.EndHorizontal();
            if (runner.Errors.Count > 0) GUILayout.Label("<color=#ff6060><b>생성 오류가 있어 시작할 수 없습니다.</b></color>", _wrap);
        }

        void DrawRunning()
        {
            var plan = runner.Plan;
            switch (runner.Phase)
            {
                case OwnershipPhase.Intro:
                    GUILayout.Label("안내 문구를 보여 주는 중. 참여자가 준비되면 Space/Enter → 첫 형상.", _wrap);
                    break;
                case OwnershipPhase.Viewing:
                    GUILayout.Label($"제시 {runner.Position}/5: <b>{runner.ShownVariant}</b>   남은 시간 {runner.ViewSecondsLeft:0.0}초 (참여자에게는 보이지 않음)", _wrap);
                    break;
                case OwnershipPhase.Rating:
                    GUILayout.Label($"평정 {runner.Position}/5 ({plan.Order[runner.Position - 1]}): 참여자가 말한 숫자 1–7을 누르세요.", _wrap);
                    GUILayout.Label(runner.PendingInput.HasValue
                        ? $"입력됨: <b>{runner.PendingInput}</b> — Space/Enter 확정·다음, Backspace 취소"
                        : "입력 대기", _wrap);
                    break;
                case OwnershipPhase.FinalChoice:
                    GUILayout.Label("마지막 선택: 참여자가 말한 번호 1–5. 호의 왼쪽부터 1–5 = " +
                                    string.Join(", ", plan.Order.Select((id, i) => $"{i + 1}:{id}")), _wrap);
                    GUILayout.Label(runner.PendingInput.HasValue
                        ? $"입력됨: <b>{runner.PendingInput}</b> — Space/Enter 확정, Backspace 취소" : "입력 대기", _wrap);
                    break;
                case OwnershipPhase.Difference:
                    GUILayout.Label($"차이 평정 {runner.DifferenceIndex + 1}/4: 왼쪽 원본, 오른쪽 <b>{runner.DifferenceVariant}</b>. 숫자 1–7.", _wrap);
                    GUILayout.Label(runner.PendingInput.HasValue
                        ? $"입력됨: <b>{runner.PendingInput}</b> — Space/Enter 확정·다음, Backspace 취소" : "입력 대기", _wrap);
                    break;
            }
            GUILayout.Label("평정: " + string.Join(", ", runner.Ratings.Select(kv => kv.Key + "=" + kv.Value)), _wrap);
            GUILayout.Label("기록: " + runner.LastRecordDirectory, _wrap);
            GUILayout.Label("Esc = 중단(그때까지의 자료는 남음). 데스크톱 모의: 마우스 오른쪽 드래그 둘러보기, WASD 이동.", _wrap);
        }

        void DrawDone()
        {
            GUILayout.Label(runner.LastCompleted ? "<b>완료</b>" : $"<b>중단</b> ({runner.LastAbortedAt})", _wrap);
            GUILayout.Label("기록 폴더: " + runner.LastRecordDirectory, _wrap);
            GUILayout.Label("평정: " + string.Join(", ", runner.Ratings.Select(kv => kv.Key + "=" + kv.Value)) +
                            (runner.FinalChoicePosition.HasValue ? $"   선택: {runner.FinalChoicePosition}" : ""), _wrap);
            if (GUILayout.Button("다음 참여자 준비", GUILayout.Height(32))) runner.ResetForNext();
        }

        void DrawMessages()
        {
            foreach (var e in runner.Errors) GUILayout.Label("<color=#ff6060>오류: " + e + "</color>", _wrap);
            foreach (var w in runner.Warnings) GUILayout.Label("<color=#ffd040>경고: " + w + "</color>", _wrap);
        }
    }
}
