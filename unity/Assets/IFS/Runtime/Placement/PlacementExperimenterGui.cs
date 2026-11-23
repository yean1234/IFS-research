// 배치 실험 실험자 화면(IMGUI, PC 모니터의 Game 창에만 보인다 — 헤드셋에는 그리지 않는다).
//   근거: OnGUI는 카메라 렌더가 끝난 뒤 화면(주 디스플레이 백버퍼)에 직접 그리는 화면 공간 그리기이고, 이 클래스는 세계 공간
//   물체·Canvas·RenderTexture를 만들지 않는다. XR 눈 영상은 카메라가 XR 디스플레이 텍스처로 렌더한 것이라 여기에 들어가지 않는다
//   (데스크톱 Game 창에는 왼눈 미러 위에 겹쳐 보인다). 헤드셋에서의 확인: docs/headset-checklist.md 1.3.
// 구성(2026-11-23 G44 화면 개선, ui-ux-pro-max 규칙 이름은 docs/validation/ui 기록):
//   · 맨 위 머리말: 지금 단계를 크게(visual-hierarchy), 조건·통제·참여자·머리·입력 한 줄, F1 안내.
//   · 바로 아래 알림: 오류 → 초안 문구 → 경고(error-placement — 단추 아래에 묻히지 않게). 초안 경고는 한 번만.
//   · 불투명 짙은 바탕(color-contrast — 반투명 상자 위 주황·빨강 글이 장면 밝기에 따라 3:1 아래로 떨어지던 것).
//   · 진행 중: 평정 입력 상태, 참여자 조작 안내(input-helper-text), 주 단추 "다음"은 왼쪽, "중단"은 오른쪽 끝에 떨어뜨리고
//     빨간색 + 두 번 누르기(confirmation-dialogs·destructive-emphasis·touch-spacing). 버튼이 부르는 러너 함수는 그대로다.
//     Esc 키(러너가 직접 읽음)는 확인 없이 바로 중단한다 — 화면에 그렇게 적는다.
//   · Setup: 넘치던 줄을 나누고 체크 글을 줄바꿈(horizontal-scroll).
// Setup에서 조건·통제 방식·참여자 입력(auto | desktop | xr)·주 사용 손·문구 파일·평정 선택 기능·선택 파일(selection.json, 선택)을 고른다.
// 참여자에게 보이는 글은 PlacementTextPanel(세계 고정 판)이 맡는다. F1 = 숨기기/보이기.
using System.Linq;
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
        [Tooltip("실험자 화면 본문 글자 크기(px)")]
        [SerializeField] int fontSize = 15;

        // 짙은 바탕 위 글자색. 대비비(렌더된 바탕 #1F2023 실측, 2026-11-23): 흰 16.3, 회 9.9, 주황 7.7, 노랑 10.1, 빨강 6.1, 초록 9.6.
        // 고치기 전 반투명 상자 위에서는 장면 밝기에 따라 주황 2.3–4.6, 노랑 3.0–6.0, 빨강 1.7–3.3이었다(docs/validation/ui).
        const string ColMuted = "#C8CAD0", ColDraft = "#FF9A30", ColWarn = "#FFC060", ColError = "#FF7070", ColOk = "#7CDB8A";
        static readonly Color PanelBg = new Color(0.11f, 0.114f, 0.125f, 0.97f);
        static readonly Color DangerTint = new Color(1f, 0.35f, 0.32f, 1f);
        static readonly Color PrimaryTint = new Color(0.55f, 0.75f, 1f, 1f);
        const float ButtonH = 38f;

        Vector2 _scroll;
        GUIStyle _wrap, _small, _title, _stage, _box, _alert, _toggle, _button;
        Texture2D _bgTex;
        readonly PlacementConfirmStep _abortConfirm = new PlacementConfirmStep();

        public void Configure(PlacementRunner r) => runner = r;

        void OnDestroy()
        {
            if (_bgTex != null) Destroy(_bgTex);
        }

        void EnsureStyles()
        {
            if (_wrap != null) return;
            _bgTex = new Texture2D(1, 1);
            _bgTex.SetPixel(0, 0, PanelBg);
            _bgTex.Apply();
            _wrap = new GUIStyle(GUI.skin.label) { wordWrap = true, richText = true, fontSize = fontSize };
            _wrap.normal.textColor = Color.white;
            _small = new GUIStyle(_wrap) { fontSize = Mathf.Max(12, fontSize - 2) };
            _title = new GUIStyle(_wrap) { fontSize = Mathf.Max(12, fontSize - 2) };
            _stage = new GUIStyle(_wrap) { fontSize = fontSize + 7, fontStyle = FontStyle.Bold };
            _alert = new GUIStyle(_wrap) { fontStyle = FontStyle.Bold };
            _box = new GUIStyle(GUI.skin.box);
            _box.normal.background = _bgTex;
            _toggle = new GUIStyle(GUI.skin.toggle) { wordWrap = true, fontSize = fontSize };
            _button = new GUIStyle(GUI.skin.button) { fontSize = fontSize, wordWrap = true };
        }

        void OnGUI()
        {
            if (runner == null) return;
            if (Event.current.type == EventType.KeyDown && Event.current.keyCode == KeyCode.F1) visible = !visible;
            if (!visible) { GUI.Label(new Rect(8, 8, 300, 24), "F1: 실험자 화면 보이기"); return; }
            EnsureStyles();

            GUILayout.BeginArea(new Rect(8, 8, Mathf.Min(panelWidth, Screen.width - 16), Screen.height - 16));
            _scroll = GUILayout.BeginScrollView(_scroll);
            GUILayout.BeginVertical(_box);   // 바탕은 내용 높이만큼(아래쪽 장면·참여자 판 미러가 가려지지 않게)
            var cfg = runner.Config;
            DrawHeader(cfg);
            DrawXrStatus(cfg);
            DrawAlerts();
            GUILayout.Space(6);
            switch (runner.Stage)
            {
                case PlacementRunnerStage.Setup: DrawSetup(cfg); break;
                case PlacementRunnerStage.Checked: DrawChecked(); break;
                case PlacementRunnerStage.Running: DrawRunning(); break;
                case PlacementRunnerStage.Done: DrawDone(); break;
            }
            GUILayout.EndVertical();
            GUILayout.EndScrollView();
            GUILayout.EndArea();
            if (runner.Stage != PlacementRunnerStage.Setup && GUIUtility.keyboardControl != 0) GUIUtility.keyboardControl = 0;
            runner.GuiHasKeyboardFocus = runner.Stage == PlacementRunnerStage.Setup && GUIUtility.keyboardControl != 0;
        }

        // ── 머리말·알림 ──────────────────────────────────────────────────
        void DrawHeader(PlacementConfig cfg)
        {
            GUILayout.Label($"<color={ColMuted}>배치 실험(RQ V4, 프로토타입) · F1 숨기기</color>", _title);
            GUILayout.Label(StageHeadline(), _stage);
            string participant = string.IsNullOrWhiteSpace(runner.ParticipantNumberText) ? "-" : runner.ParticipantNumberText.Trim();
            GUILayout.Label($"조건 <b>{cfg.condition} / {cfg.EffectiveControlMode}</b>   참여자 <b>{participant}</b>   " +
                            $"<color={ColMuted}>머리 {runner.HeadSource} · 입력 {runner.ActiveInputSource ?? "(확인 전)"}</color>", _wrap);
        }

        string StageHeadline()
        {
            switch (runner.Stage)
            {
                case PlacementRunnerStage.Setup: return "준비(Setup) — 설정 후 확인";
                case PlacementRunnerStage.Checked: return "확인됨 — 시작 전";
                case PlacementRunnerStage.Running:
                {
                    var s = runner.Session;
                    if (s == null) return "진행 중";
                    string left = double.IsNaN(s.PhaseSecondsLeft) ? "" : $"   <color={ColMuted}>남은 {s.PhaseSecondsLeft:0.0} s</color>";
                    return $"진행 중 · 단계 {s.PhaseLabel}{left}";
                }
                case PlacementRunnerStage.Done:
                    return runner.LastCompleted ? $"<color={ColOk}>끝 — 완료</color>" : $"<color={ColError}>끝 — 중단({runner.LastAbortedAt})</color>";
            }
            return runner.Stage.ToString();
        }

        void DrawAlerts()
        {
            foreach (var e in runner.Errors) GUILayout.Label($"<color={ColError}>오류: {e}</color>", _alert);
            string notice = runner.DraftPhraseNotice;
            if (notice != null) GUILayout.Label($"<color={ColDraft}>[초안 문구] {notice}</color>", _alert);
            foreach (var w in runner.Warnings)
                if (notice == null || w != notice) GUILayout.Label($"<color={ColWarn}>경고: {w}</color>", _wrap);
        }

        void DrawXrStatus(PlacementConfig cfg)
        {
            var rig = runner.XrRig;
            if (rig == null && runner.XrInput == null) return;
            bool head = runner.XrHeadActive;
            string hand = cfg.xrHand == PlacementConfig.HandLeft ? "왼손" : "오른손";
            string line = head
                ? $"XR: 헤드셋 켜짐({PlacementXrRig.LoadedDeviceName} / {PlacementXrRig.HeadDeviceName ?? "-"})  컨트롤러({hand}): {(runner.XrControllerPresent || runner.Stage == PlacementRunnerStage.Running ? (runner.XrInput?.DeviceName ?? "연결됨") : $"<color={ColWarn}>안 보임</color>")}  추적 원점: {rig?.TrackingOrigin ?? "-"}"
                : $"<color={ColMuted}>XR: 헤드셋 없음(데스크톱 모의 조작). Quest Link를 켜고 Play를 다시 누르면 잡힌다</color>";
            GUILayout.BeginHorizontal();
            GUILayout.Label(line, _small);
            if (head && GUILayout.Button("정면 재설정 (R)", _button, GUILayout.Width(150), GUILayout.Height(30))) runner.Recenter();
            GUILayout.EndHorizontal();
            if (runner.LastRecenterMessage != null) GUILayout.Label(runner.LastRecenterMessage, _small);
        }

        // ── 단계별 ───────────────────────────────────────────────────────
        void DrawSetup(PlacementConfig cfg)
        {
            GUILayout.Label("참여자 번호(1 이상)", _wrap);
            runner.ParticipantNumberText = GUILayout.TextField(runner.ParticipantNumberText ?? "", GUILayout.Width(120));
            GUILayout.Label("spec 경로(절대 경로, 또는 " + runner.ResolvedSpecFolder + " 기준 이름)", _wrap);
            runner.SpecPathText = GUILayout.TextField(runner.SpecPathText ?? "");
            foreach (var f in runner.SpecFiles)
                if (GUILayout.Button(f.Name, _button, GUILayout.ExpandWidth(true))) runner.SpecPathText = f.Path;
            GUILayout.Label("선택 파일 selection.json(선택 — 후보 선택·조절 결과. 비우면 spec만. 절대 경로 또는 spec 폴더 기준 이름)", _wrap);
            runner.SelectionPathText = GUILayout.TextField(runner.SelectionPathText ?? "");
            GUILayout.Space(4);
            GUILayout.Label("조건(무선 배정은 실험자가 한다)", _wrap);
            GUILayout.BeginHorizontal();
            foreach (var c in PlacementConfig.Conditions)
                if (GUILayout.Button((cfg.condition == c ? "● " : "") + c, _button, GUILayout.Width(120), GUILayout.Height(30))) cfg.condition = c;
            GUILayout.EndHorizontal();
            if (cfg.condition == PlacementConfig.ConditionView)
            {
                GUILayout.BeginHorizontal();
                foreach (var m in PlacementConfig.ViewModes)
                    if (GUILayout.Button((cfg.controlMode == m ? "● " : "") + m, _button, GUILayout.Width(140), GUILayout.Height(30))) cfg.controlMode = m;
                GUILayout.EndHorizontal();
                if (cfg.controlMode == PlacementConfig.ModeReplay)
                {
                    GUILayout.Label("재생 원본 trajectory.json(절대 경로 또는 기록 루트 기준)", _wrap);
                    cfg.replayPath = GUILayout.TextField(cfg.replayPath ?? "");
                }
            }
            GUILayout.Label("참여자 입력(auto = 헤드셋이 켜져 있으면 XR 컨트롤러, 없으면 데스크톱)", _wrap);
            GUILayout.BeginHorizontal();
            foreach (var m in PlacementConfig.InputModes)
                if (GUILayout.Button((cfg.inputMode == m ? "● " : "") + m, _button, GUILayout.Width(120), GUILayout.Height(30))) cfg.inputMode = m;
            GUILayout.EndHorizontal();
            GUILayout.BeginHorizontal();
            GUILayout.Label("주 사용 손", _wrap, GUILayout.Width(100));
            foreach (var h in PlacementConfig.Hands)
                if (GUILayout.Button((cfg.xrHand == h ? "● " : "") + h, _button, GUILayout.Width(90), GUILayout.Height(30))) cfg.xrHand = h;
            GUILayout.FlexibleSpace();
            GUILayout.EndHorizontal();
            GUILayout.Space(4);
            cfg.participantRatesWithController = GUILayout.Toggle(cfg.participantRatesWithController,
                " 참여자가 컨트롤러로 평정(썸스틱 좌우 고르기, 트리거 확정) — 꺼 두면 참여자는 말로 답하고 실험자가 숫자를 넣는다", _toggle);
            cfg.hideObjectDuringItems = GUILayout.Toggle(cfg.hideObjectDuringItems, " 평정 동안 물체 숨기기(설문 초안의 제안, 절차 변경이라 팀 결정 전)", _toggle);
            cfg.askOptionalItems = GUILayout.Toggle(cfg.askOptionalItems, " 선택 단계 문항도 묻기(optionalWhen — 두 평정 문항 모습 일치·대표성을 사전에도. 기본 꺼짐: 사전 측정은 데스크톱)", _toggle);
            GUILayout.Label("묻지 않을 평정 문항 키(쉼표로, 예: own 또는 S4 — 기존 '내 것 같다' 문항 끄기)", _wrap);
            string disabled = GUILayout.TextField(string.Join(",", cfg.disabledItems ?? new string[0]));
            cfg.disabledItems = disabled.Split(',').Select(k => k.Trim()).Where(k => k.Length > 0).ToArray();
            GUILayout.Label("문구 파일(StreamingAssets): 지금 " + runner.TaskTextDisplayName, _wrap);
            GUILayout.BeginHorizontal();
            foreach (var f in runner.TaskTextFiles)
                if (GUILayout.Button((SameTaskText(runner.TaskTextDisplayName, f) ? "● " : "") + f.Replace(PlacementTaskText.TaskTextFolder + "/", ""), _button, GUILayout.ExpandWidth(false), GUILayout.Height(30)))
                    runner.SelectTaskText(f);
            GUILayout.EndHorizontal();
            GUILayout.Space(8);
            var keep = GUI.backgroundColor;
            GUI.backgroundColor = PrimaryTint;
            if (GUILayout.Button("확인", _button, GUILayout.Height(ButtonH))) runner.Check();
            GUI.backgroundColor = keep;
        }

        static bool SameTaskText(string a, string b) =>
            string.Equals((a ?? "").Replace('\\', '/').Trim(), (b ?? "").Replace('\\', '/').Trim(), System.StringComparison.OrdinalIgnoreCase);

        void DrawChecked()
        {
            GUILayout.Label($"참여자 <b>{runner.ParticipantNumberText}</b>   spec <b>{runner.Spec?.Meta?.SessionId}</b>", _wrap);
            var sel = runner.Selection;
            GUILayout.Label(sel == null ? "선택 파일: 없음(spec만)"
                : $"선택 파일: {sel.FileName}  {(sel.None ? "맞는 것이 없다(기준 후보)" : "후보 " + (sel.SelectedCandidateId ?? "-"))}  덮어쓰기: {sel.Overrides}", _wrap);
            GUILayout.Space(8);
            GUILayout.BeginHorizontal();
            var keep = GUI.backgroundColor;
            GUI.enabled = runner.Errors.Count == 0;
            GUI.backgroundColor = PrimaryTint;
            if (GUILayout.Button("시작 (Enter)", _button, GUILayout.Width(220), GUILayout.Height(ButtonH))) runner.PressConfirm();
            GUI.backgroundColor = keep;
            GUI.enabled = true;
            GUILayout.FlexibleSpace();
            if (GUILayout.Button("설정으로 돌아가기 (Esc)", _button, GUILayout.Width(220), GUILayout.Height(ButtonH))) runner.PressAbort();
            GUILayout.EndHorizontal();
            if (runner.Errors.Count > 0) GUILayout.Label($"<color={ColError}>오류를 고쳐야 시작할 수 있습니다(위 오류 줄).</color>", _small);
        }

        /// <summary>중단 확인 상자의 맥락: 러너 단계 + 세션 단계. 단계가 바뀌면 열린 확인 상자는 닫힌다.</summary>
        string AbortContext() => runner.Stage + "|" + (runner.Session?.PhaseLabel ?? "");

        void DrawRunning()
        {
            var s = runner.Session;
            if (s == null) return;
            var o = s.ObjectPosition;
            GUILayout.Label($"물체: {(s.ObjectVisible ? "보임" : "숨김")} {s.ObjectState}  거리 {PlacementGeometry.HorizontalDistance(o):0.00} m  방위 {PlacementGeometry.AzimuthDeg(o):0} °  높이 {o.Y:0.00} m  잡기 {s.GrabCount}회", _wrap);
            if (s.ParticipantText != null) GUILayout.Label($"<color={ColMuted}>참여자 글:</color> " + s.ParticipantText.Replace("\n", " / "), _wrap);
            var item = s.CurrentItem;
            if (s.ItemsInstructionActive)
                GUILayout.Label($"<b>평정 지시문({s.CurrentItemWhen})</b> — 참여자가 다 읽으면 Enter(다음)로 첫 문항", _wrap);
            if (item != null)
            {
                GUILayout.Label($"<b>평정 {s.ItemNumber}/{s.ItemCount} {item.Key}({s.CurrentItemWhen})</b> — 숫자 {item.Min}–{item.Max}{(item.Max > 9 ? "(두 자리는 이어 침)" : "")}, Backspace 취소, Enter 확정", _wrap);
                string typed = s.PendingRating?.ToString() ?? (s.PendingDigits.Length > 0 ? s.PendingDigits + "…" : "-");
                string cursor = s.Config.participantRatesWithController ? $"   참여자 컨트롤러 고르는 중: <b>{(s.RatingCursor?.ToString() ?? "-")}</b>" : "";
                GUILayout.Label($"입력: <b>{typed}</b>{cursor}", _stage);
            }
            if (s.Phase == PlacementPhase.StopDistance)
            {
                var t = s.CurrentStopTrial;
                GUILayout.Label(!s.StopTrialsStarted ? "멈춤 거리: 안내를 확인한 뒤 '다음'(Enter)으로 시작"
                    : $"멈춤 거리 시행 {t?.Trial ?? 0}/{s.StopPlan.Count} {(t != null && t.Practice ? "(연습)" : "")} {t?.Direction}  지금 {s.StopDistanceNow:0.00} m", _wrap);
            }
            // 참여자 조작 안내(늘 보이게, 단추 위)
            string help = runner.ActiveInputSource == XrPlacementInput.Source
                ? "참여자 XR 조작: 광선으로 가리키고 트리거(또는 그립) 누르고 있기 = 잡기, 썸스틱 앞/뒤 = 밀기/당기기, A·X = 확인, 트리거 = 멈춤 거리 버튼" +
                  (s.Config.participantRatesWithController ? ", 평정: 썸스틱 좌우 고르기·트리거 확정" : "") + ".  실험자 R = 정면 재설정"
                : "참여자 데스크톱 조작: 왼쪽 단추 누르고 있기 = 잡기, 휠 또는 E/Q = 밀기/당기기, F = 확인, Space = 멈춤 거리 버튼. 오른쪽 드래그·WASD = 둘러보기·이동";
            GUILayout.Label($"<color={ColMuted}>{help}</color>", _small);

            bool waits = s.Phase == PlacementPhase.Intro || s.Phase == PlacementPhase.PreWait || s.Phase == PlacementPhase.PostWait
                         || (s.Phase == PlacementPhase.StopDistance && !s.StopTrialsStarted) || s.ItemsInstructionActive;
            string ctx = AbortContext();
            if (_abortConfirm.ArmedFor != null && !_abortConfirm.IsArmed(ctx)) _abortConfirm.Cancel();   // 단계가 넘어가면 닫음
            // 이번 OnGUI 호출(이벤트 하나) 안에서는 같은 컨트롤 구성을 유지한다 — 누른 결과는 다음 Layout 이벤트부터 보인다(IMGUI 규칙)
            bool armed = _abortConfirm.IsArmed(ctx);
            GUILayout.Space(8);
            GUILayout.BeginHorizontal();
            var keep = GUI.backgroundColor;
            GUI.enabled = waits;
            GUI.backgroundColor = PrimaryTint;
            if (GUILayout.Button("다음 (Enter)", _button, GUILayout.Width(220), GUILayout.Height(ButtonH))) runner.PressConfirm();
            GUI.backgroundColor = keep;
            GUI.enabled = true;
            GUILayout.FlexibleSpace();   // 위험한 단추는 주 단추에서 떨어뜨린다
            if (!armed)
            {
                GUI.backgroundColor = DangerTint;
                if (GUILayout.Button("중단…", _button, GUILayout.Width(140), GUILayout.Height(ButtonH))) _abortConfirm.Arm(ctx);
                GUI.backgroundColor = keep;
            }
            GUILayout.EndHorizontal();
            if (armed)
            {
                GUILayout.Space(4);
                GUILayout.Label($"<color={ColError}>세션을 중단할까요? 지금 단계({s.PhaseLabel})에서 끝나고 되돌릴 수 없습니다. 지금까지의 기록은 남고 summary.json에 중단으로 적힙니다.</color>", _alert);
                GUILayout.BeginHorizontal();
                if (GUILayout.Button("계속 진행(취소)", _button, GUILayout.Width(220), GUILayout.Height(ButtonH))) _abortConfirm.Cancel();
                GUILayout.FlexibleSpace();
                GUI.backgroundColor = DangerTint;
                if (GUILayout.Button("중단 확정", _button, GUILayout.Width(140), GUILayout.Height(ButtonH)) && _abortConfirm.Confirm(ctx)) runner.PressAbort();
                GUI.backgroundColor = keep;
                GUILayout.EndHorizontal();
            }
            GUILayout.Label($"<color={ColMuted}>키보드 Esc는 확인 없이 바로 중단합니다.</color>", _small);
        }

        void DrawDone()
        {
            GUILayout.Label("기록: " + runner.LastRecordDirectory, _wrap);
            GUILayout.Space(8);
            if (GUILayout.Button("다음 참여자 준비", _button, GUILayout.Height(ButtonH))) runner.ResetForNext();
        }
    }
}
