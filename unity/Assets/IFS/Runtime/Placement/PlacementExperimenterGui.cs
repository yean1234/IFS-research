// 배치 실험 실험자 화면(IMGUI, 데스크톱 창에만 보인다). 최소 구성: 지금 단계, 남은 시간, 조건, draft 경고, 대기 단계의 "다음".
// 참여자에게 보이는 글은 ParticipantTextDisplay(월드 공간)가 맡는다. F1 = 숨기기/보이기.
using UnityEngine;

namespace IFS.SceneSpec.Placement
{
    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Placement/Experimenter GUI")]
    public sealed class PlacementExperimenterGui : MonoBehaviour
    {
        [SerializeField] PlacementRunner runner = null;
        [SerializeField] float panelWidth = 620f;
        [SerializeField] bool visible = true;

        Vector2 _scroll;
        GUIStyle _wrap;

        public void Configure(PlacementRunner r) => runner = r;

        void OnGUI()
        {
            if (runner == null) return;
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F1) visible = !visible;
            if (!visible) { GUI.Label(new Rect(8, 8, 300, 24), "F1: 실험자 화면 보이기"); return; }
            if (_wrap == null) _wrap = new GUIStyle(GUI.skin.label) { wordWrap = true, richText = true };

            GUILayout.BeginArea(new Rect(8, 8, Mathf.Min(panelWidth, Screen.width - 16), Screen.height - 16), GUI.skin.box);
            _scroll = GUILayout.BeginScrollView(_scroll);
            var cfg = runner.Config;
            string mode = cfg.EffectiveControlMode;
            GUILayout.Label($"<b>배치 실험(RQ V4, 프로토타입)</b> — {runner.Stage}   조건: {cfg.condition} / {mode}   머리: {runner.HeadSource}   (F1 숨기기)", _wrap);
            string notice = runner.DraftPhraseNotice;
            if (notice != null) GUILayout.Label("<size=14><b><color=#ff9a30>[초안 문구] " + notice + "</color></b></size>", _wrap);
            switch (runner.Stage)
            {
                case PlacementRunnerStage.Setup: DrawSetup(cfg); break;
                case PlacementRunnerStage.Checked: DrawChecked(); break;
                case PlacementRunnerStage.Running: DrawRunning(); break;
                case PlacementRunnerStage.Done: DrawDone(); break;
            }
            foreach (var e in runner.Errors) GUILayout.Label("<color=#ff6060>오류: " + e + "</color>", _wrap);
            foreach (var w in runner.Warnings) GUILayout.Label("<color=#ffc060>경고: " + w + "</color>", _wrap);
            GUILayout.EndScrollView();
            GUILayout.EndArea();
            if (runner.Stage != PlacementRunnerStage.Setup && GUIUtility.keyboardControl != 0) GUIUtility.keyboardControl = 0;
            runner.GuiHasKeyboardFocus = runner.Stage == PlacementRunnerStage.Setup && GUIUtility.keyboardControl != 0;
        }

        void DrawSetup(PlacementConfig cfg)
        {
            GUILayout.Label("참여자 번호(1 이상)");
            runner.ParticipantNumberText = GUILayout.TextField(runner.ParticipantNumberText ?? "", GUILayout.Width(120));
            GUILayout.Label("spec 경로(절대 경로, 또는 " + runner.ResolvedSpecFolder + " 기준 이름)", _wrap);
            runner.SpecPathText = GUILayout.TextField(runner.SpecPathText ?? "");
            foreach (var f in runner.SpecFiles)
                if (GUILayout.Button(f.Name, GUILayout.ExpandWidth(true))) runner.SpecPathText = f.Path;
            GUILayout.Label("조건(무선 배정은 실험자가 한다)");
            GUILayout.BeginHorizontal();
            foreach (var c in PlacementConfig.Conditions)
                if (GUILayout.Button((cfg.condition == c ? "● " : "") + c, GUILayout.Width(120))) cfg.condition = c;
            GUILayout.EndHorizontal();
            if (cfg.condition == PlacementConfig.ConditionView)
            {
                GUILayout.BeginHorizontal();
                foreach (var m in PlacementConfig.ViewModes)
                    if (GUILayout.Button((cfg.controlMode == m ? "● " : "") + m, GUILayout.Width(140))) cfg.controlMode = m;
                GUILayout.EndHorizontal();
                if (cfg.controlMode == PlacementConfig.ModeReplay)
                {
                    GUILayout.Label("재생 원본 trajectory.json(절대 경로 또는 기록 루트 기준)", _wrap);
                    cfg.replayPath = GUILayout.TextField(cfg.replayPath ?? "");
                }
            }
            if (GUILayout.Button("확인", GUILayout.Height(30))) runner.Check();
        }

        void DrawChecked()
        {
            GUILayout.Label($"참여자 {runner.ParticipantNumberText}   spec {runner.Spec?.Meta?.SessionId}", _wrap);
            GUILayout.BeginHorizontal();
            GUI.enabled = runner.Errors.Count == 0;
            if (GUILayout.Button("시작 (Enter)", GUILayout.Height(30))) runner.PressConfirm();
            GUI.enabled = true;
            if (GUILayout.Button("돌아가기 (Esc)", GUILayout.Height(30))) runner.PressAbort();
            GUILayout.EndHorizontal();
        }

        void DrawRunning()
        {
            var s = runner.Session;
            if (s == null) return;
            string left = double.IsNaN(s.PhaseSecondsLeft) ? "" : $"   남은 시간 {s.PhaseSecondsLeft:0.0} s";
            GUILayout.Label($"<b>단계: {s.PhaseLabel}</b>{left}", _wrap);
            var o = s.ObjectPosition;
            GUILayout.Label($"물체: {(s.ObjectVisible ? "보임" : "숨김")} {s.ObjectState}  거리 {PlacementGeometry.HorizontalDistance(o):0.00} m  방위 {PlacementGeometry.AzimuthDeg(o):0} °  높이 {o.Y:0.00} m  잡기 {s.GrabCount}회", _wrap);
            if (s.ParticipantText != null) GUILayout.Label("참여자 글: " + s.ParticipantText.Replace("\n", " / "), _wrap);
            var item = s.CurrentItem;
            if (item != null)
                GUILayout.Label($"평정 {item.Key}({s.CurrentItemWhen}) — 숫자 1–7, Backspace 취소, Enter 확정.  입력: {(s.PendingRating?.ToString() ?? "-")}", _wrap);
            if (s.Phase == PlacementPhase.StopDistance)
            {
                var t = s.CurrentStopTrial;
                GUILayout.Label(!s.StopTrialsStarted ? "멈춤 거리: 안내를 확인한 뒤 '다음'(Enter)으로 시작"
                    : $"멈춤 거리 시행 {t?.Trial ?? 0}/{s.StopPlan.Count} {(t != null && t.Practice ? "(연습)" : "")} {t?.Direction}  지금 {s.StopDistanceNow:0.00} m", _wrap);
            }
            bool waits = s.Phase == PlacementPhase.Intro || s.Phase == PlacementPhase.PreWait || s.Phase == PlacementPhase.PostWait
                         || (s.Phase == PlacementPhase.StopDistance && !s.StopTrialsStarted);
            GUILayout.BeginHorizontal();
            GUI.enabled = waits;
            if (GUILayout.Button("다음 (Enter)", GUILayout.Height(30))) runner.PressConfirm();
            GUI.enabled = true;
            if (GUILayout.Button("중단 (Esc)", GUILayout.Height(30))) runner.PressAbort();
            GUILayout.EndHorizontal();
            GUILayout.Label("참여자 데스크톱 조작: 왼쪽 단추 누르고 있기 = 잡기, 휠 또는 E/Q = 밀기/당기기, F = 확인, Space = 멈춤 거리 버튼. 오른쪽 드래그·WASD = 둘러보기·이동", _wrap);
        }

        void DrawDone()
        {
            GUILayout.Label(runner.LastCompleted ? "끝(완료)" : "끝(중단: " + runner.LastAbortedAt + ")", _wrap);
            GUILayout.Label("기록: " + runner.LastRecordDirectory, _wrap);
            if (GUILayout.Button("다음 참여자 준비", GUILayout.Height(30))) runner.ResetForNext();
        }
    }
}
