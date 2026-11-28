// 배치 실험 실험자 화면(IMGUI, PC 모니터의 Game 창에만 보인다 — 헤드셋에는 그리지 않는다).
//   근거: OnGUI는 카메라 렌더가 끝난 뒤 화면(주 디스플레이 백버퍼)에 직접 그리는 화면 공간 그리기이고, 이 클래스는 세계 공간
//   물체·Canvas·RenderTexture를 만들지 않는다. XR 눈 영상은 카메라가 XR 디스플레이 텍스처로 렌더한 것이라 여기에 들어가지 않는다
//   (데스크톱 Game 창에는 왼눈 미러 위에 겹쳐 보인다). 헤드셋에서의 확인: docs/headset-checklist.md 1.3.
// 구성(2026-11-23 G44 화면 개선, ui-ux-pro-max 규칙 이름은 docs/validation/ui 기록):
//   · 맨 위 머리말: 지금 단계를 크게(visual-hierarchy), 조건·통제·참여자·머리·입력 한 줄, F1 안내.
//   · 바로 아래 알림: 오류 → 초안 문구 → 경고(error-placement — 단추 아래에 묻히지 않게). 초안 경고는 한 번만.
//     그 뒤 선택 파일의 넷째 제외 범주 표시(G50 (4), PlacementSafetyNotice — 연구자용 로그 문자열, 진행은 막지 않음).
//   · 불투명 짙은 바탕(color-contrast — 반투명 상자 위 주황·빨강 글이 장면 밝기에 따라 3:1 아래로 떨어지던 것).
//   · 진행 중: 평정 입력 상태, 참여자 조작 안내(input-helper-text), 주 단추 "다음"은 왼쪽, "중단"은 오른쪽 끝에 떨어뜨리고
//     빨간색 + 두 번 누르기(confirmation-dialogs·destructive-emphasis·touch-spacing). 버튼이 부르는 러너 함수는 그대로다.
//     Esc 키(러너가 직접 읽음)는 확인 없이 바로 중단한다 — 화면에 그렇게 적는다.
//   · Setup: 넘치던 줄을 나누고 체크 글을 줄바꿈(horizontal-scroll).
// Setup에서 조건·통제 방식·참여자 입력(auto | desktop | xr)·주 사용 손·문구 파일·평정 선택 기능·선택 파일(selection.json, 선택)을 고른다.
// 참여자에게 보이는 글은 PlacementTextPanel(세계 고정 판)이 맡는다. F1 = 숨기기/보이기.
// 2026-11-24(G52–G53): 머리말에 배경 공간(environment)·놓기 도움 상태(후보 B·E·F 이름), Setup에 고르기 단추, 진행 중 배치 연습 상태.
//   설정 이름은 이 실험자 화면(OnGUI)에만 쓴다 — 참여자 판(PlacementTextPanel)에는 문구 파일의 글만 간다.
// 2026-11-28(공간 고르기·화면 나누기): 헤드셋에 이 화면이 보인 것은 XR이 켜지지 않아 데스크톱으로 돌 때 Link 데스크톱 보기로 PC 화면을 본 경우다
//   (Editor.log XR_ERROR_FORM_FACTOR_UNAVAILABLE). 잠금이면 그때 XR 줄을 빨간 글로 보이고 확인에서 시작을 거부한다. 지금 머리 높이 줄, 공간 고르기 상태 줄.
// 2026-11-28: Setup 맨 위에 최근 세션 자동 채움 결과(세션 ID·참여자 번호·저장 시각, 오래됨·이미 돌림 경고, [최근 세션 다시 찾기]).
//   러너 lockExperimentPreset이 켜져 있으면 권고 설정 단추·놓기 도움·연습·물체 숨김·점검 순서·반복 멈춤·눈높이·UI 묶음·문구 파일
//   고르기를 그리지 않고 "본 실험 설정 고정" 요약(PlacementExperimentLock.SummaryLines)만 보인다. 공간 단추 셋(기본·자연·우주)은 잠금에서도
//   보인다(2026-11-28 연구 책임자 결정: 공간은 실험자가 고른다). 참여자 고르기 단계 토글은 두지 않는다(꺼 둔 기능 — 인스펙터·명령줄로만).
// CP17-1: 세션 중 XR이 끊기면 알림 맨 위에 빨간 큰 글(F1 숨기기·[중단…]·Esc 안내). 세션은 그대로 진행한다.
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
            var s = runner.Session;
            GUILayout.Label(s != null ? SpaceLine(s.Config, s.ShownEnvironment, runner.AppliedEnvironment) : SpaceLine(cfg, runner.AppliedEnvironment), _wrap);
        }

        /// <summary>공간 고르기 상태 한 줄(2026-11-28, 실험자 화면에만 — 공간 이름은 참여자 판에 쓰지 않는다).</summary>
        public static string SpaceChoiceLine(PlacementSession s)
        {
            if (s == null || s.SpaceChoiceOrder == null) return null;
            string order = string.Join(" → ", s.SpaceChoiceOrder);
            if (s.Phase == PlacementPhase.SpaceChoice && !s.SpaceChoiceDecided)
                return $"<b>공간 고르기</b>: 지금 <b>{s.ShownEnvironment}</b>({s.SpaceChoiceIndex + 1}/{s.SpaceChoiceOrder.Count}) · 본 공간 {s.SpaceChoiceSeenCount}/{s.SpaceChoiceOrder.Count}" +
                       $"{(s.SpaceChoiceSeenAll ? "" : " — 다 보기 전 확인은 받지 않음")} · 순서 {order} · {s.SecondsInPhase:0} s. 참여자: 방아쇠 = 다음 공간, 확인 버튼 = 정하기. " +
                       "실험자 Enter = 지금 공간으로 정함(참여자가 말로 고른 때)";
            return s.SpaceChosenBy == null ? null
                : $"공간 고름: <b>{s.Config.environment}</b>({(s.SpaceChosenBy == PlacementSpaceChoice.ByParticipant ? "참여자" : s.SpaceChosenBy == PlacementSpaceChoice.ByExperimenter ? "실험자" : "중단")}) · 순서 {order}";
        }

        /// <summary>배경 공간·놓기 도움 한 줄(G52). 후보 이름: 도움을 켠 neutral = B, space = E, nature = F.</summary>
        public static string SpaceLine(PlacementConfig cfg, string applied) => SpaceLine(cfg, cfg.environment, applied);

        /// <summary>shown: 지금 그려야 할 공간(공간 고르기 중이면 참여자가 보는 공간).</summary>
        public static string SpaceLine(PlacementConfig cfg, string shown, string applied)
        {
            string candidate = !cfg.placementAssist ? "기본(후보 아님)"
                : shown == PlacementConfig.EnvironmentSpace ? "후보 E"
                : shown == PlacementConfig.EnvironmentNature ? "후보 F" : "후보 B";
            string drawn = applied == shown ? "" : $"  <color={ColError}>화면은 {applied}(그리지 못함 — 확인에서 오류)</color>";
            string practice = !cfg.placementAssist ? ""
                : cfg.HasPractice ? (cfg.IsPlace ? " · 배치 연습 있음" : " · 배치 연습 있음(보기만 조건도 — practiceInAllConditions)")
                : " · 배치 연습 없음(보기만 조건)";
            string who = cfg.ParticipantChoosesSpace ? " · 참여자가 고름" : "";
            return $"공간 <b>{shown}</b>{who} · 놓기 도움 <b>{(cfg.placementAssist ? "켜짐" : "꺼짐")}</b>{practice}   <color={ColMuted}>{candidate}</color>{drawn}";
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
            // CP17-1: 세션 중 XR이 끊김 — 가장 먼저, 크게(세션은 그대로 진행. 중단은 실험자가 [중단…]·Esc로)
            var xs = runner.Session;
            if (xs != null && !xs.Finished && xs.XrLostNow)
                GUILayout.Label($"<color={ColError}>{PlacementSpaceChoice.XrLostAlert(xs.XrLostCount)}</color>", _stage);
            else if (xs != null && xs.XrLostCount > 0)
                GUILayout.Label($"<color={ColWarn}>이 세션에서 헤드셋 연결이 {xs.XrLostCount}번 끊겼다가 다시 잡혔습니다(events xr_lost·xr_regained, manifest xrConnection)</color>", _alert);
            foreach (var e in runner.Errors) GUILayout.Label($"<color={ColError}>오류: {e}</color>", _alert);
            string notice = runner.DraftPhraseNotice;
            if (notice != null) GUILayout.Label($"<color={ColDraft}>[초안 문구] {notice}</color>", _alert);
            foreach (var w in runner.Warnings)
                if (notice == null || w != notice) GUILayout.Label($"<color={ColWarn}>경고: {w}</color>", _wrap);
            // G50 (4): 선택 파일의 넷째 제외 범주 표시(연구자용 로그 문자열, 고정 문구 아님). 진행은 막지 않는다 — 단추는 그대로
            var safety = PlacementSafetyNotice.Lines(runner.Selection);
            for (int i = 0; i < safety.Count; i++)
                GUILayout.Label($"<color={ColWarn}>{(i == 0 ? "[안전 표시] " : "")}{safety[i]}</color>", i == 0 ? _alert : _wrap);
        }

        void DrawXrStatus(PlacementConfig cfg)
        {
            var rig = runner.XrRig;
            if (rig == null && runner.XrInput == null) return;
            bool head = runner.XrHeadActive;
            string hand = cfg.xrHand == PlacementConfig.HandLeft ? "왼손" : "오른손";
            string line = head
                ? $"XR: 헤드셋 켜짐({PlacementXrRig.LoadedDeviceName} / {PlacementXrRig.HeadDeviceName ?? "-"})  컨트롤러({hand}): {(runner.XrControllerPresent || runner.Stage == PlacementRunnerStage.Running ? (runner.XrInput?.DeviceName ?? "연결됨") : $"<color={ColWarn}>안 보임</color>")}  추적 원점: {rig?.TrackingOrigin ?? "-"}"
                : runner.ExperimentPresetLocked && cfg.inputMode != PlacementConfig.InputModeDesktop
                    // 2026-11-28: 실험 씬인데 XR이 꺼져 있다 — 이 화면이 Link 데스크톱 보기로 헤드셋에 보일 수 있다(확인에서 시작 거부)
                    ? $"<color={ColError}>XR: 헤드셋 없음 — 데스크톱으로 도는 중. 참여자가 헤드셋의 Link 데스크톱 보기로 이 화면을 볼 수 있습니다. 헤드셋 안에서 Link를 켜고 Play를 다시 누르세요</color>"
                    : $"<color={ColMuted}>XR: 헤드셋 없음(데스크톱 모의 조작). Quest Link를 켜고 Play를 다시 누르면 잡힌다</color>";
            GUILayout.BeginHorizontal();
            GUILayout.Label(line, head ? _small : _alert);
            if (head && GUILayout.Button("정면 재설정 (R)", _button, GUILayout.Width(150), GUILayout.Height(30))) runner.Recenter();
            GUILayout.EndHorizontal();
            if (runner.LastRecenterMessage != null) GUILayout.Label(runner.LastRecenterMessage, _small);
            // 2026-11-28: 지금 머리 높이(추적 바닥 기준)를 늘 보인다 — 바닥(Guardian) 높이가 틀리면 여기서 먼저 드러난다
            var live = runner.LiveHeadHeightM;
            if (live.HasValue)
            {
                bool rel = cfg.IsEyeRelative;
                bool outOfRange = rel && (live.Value < cfg.EyeRangeMinM || live.Value > cfg.EyeRangeMaxM);
                string range = rel ? $" · {(cfg.IsSeated ? "앉은" : "선")} 자세 범위 [{cfg.EyeRangeMinM:0.00}, {cfg.EyeRangeMaxM:0.00}] m" : "";
                string txt = $"지금 머리 높이 {live.Value:0.000} m(추적 바닥 기준){range}" +
                             (outOfRange ? " — 범위 밖: 참여자 자세와 Quest 바닥 높이(설정 ▸ 물리적 공간 ▸ 경계/바닥)를 확인" : "");
                GUILayout.Label(outOfRange ? $"<color={ColWarn}>{txt}</color>" : $"<color={ColMuted}>{txt}</color>", _small);
            }
            // G60-3 눈높이(relative일 때만): 상태 한 줄 + Check 단계에서 재기 단추
            string eye = runner.EyeHeightStatus;
            if (eye != null)
            {
                GUILayout.BeginHorizontal();
                bool ok = runner.EyeCalibration != null && runner.EyeCalibration.Ok;
                GUILayout.Label(ok || !head ? eye : $"<color={ColWarn}>{eye}</color>", _small);
                if (head && runner.Stage == PlacementRunnerStage.Checked && runner.Session == null && !runner.EyeCalibrating
                    && GUILayout.Button("눈높이 재기 (H)", _button, GUILayout.Width(150), GUILayout.Height(30)))
                    runner.BeginEyeCalibration();
                GUILayout.EndHorizontal();
            }
        }

        // ── 단계별 ───────────────────────────────────────────────────────
        void DrawSetup(PlacementConfig cfg)
        {
            DrawAutoFill();
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
            bool locked = runner.ExperimentPresetLocked;
            if (locked) { DrawSpaceButtons(cfg, true); DrawLockSummary(cfg); }   // 2026-11-28: 잠금에서도 공간은 실험자가 고른다
            else DrawPresetControls(cfg);
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
            if (!locked) DrawProcedureToggles(cfg);
            cfg.hidePanelInDistancePhases = GUILayout.Toggle(cfg.hidePanelInDistancePhases,
                $" 조건·멈춤 거리 단계에서 안내 판을 {cfg.hidePanelReadSeconds:0.#}초 뒤 숨기기(G63 (7), 판이 거리 기준점이 되지 않게 — RQ2에 닿아 묶음에서 빠짐. 연구 책임자 결정 대기)", _toggle);
            cfg.askOptionalItems = GUILayout.Toggle(cfg.askOptionalItems, " 선택 단계 문항도 묻기(optionalWhen — 두 평정 문항 모습 일치·대표성을 사전에도. 기본 꺼짐: 사전 측정은 데스크톱)", _toggle);
            GUILayout.Label("묻지 않을 평정 문항 키(쉼표로, 예: own 또는 S4 — 기존 '내 것 같다' 문항 끄기)", _wrap);
            string disabled = GUILayout.TextField(string.Join(",", cfg.disabledItems ?? new string[0]));
            cfg.disabledItems = disabled.Split(',').Select(k => k.Trim()).Where(k => k.Length > 0).ToArray();
            if (!locked)
            {
                GUILayout.Label("문구 파일(StreamingAssets): 지금 " + runner.TaskTextDisplayName, _wrap);
                GUILayout.BeginHorizontal();
                foreach (var f in runner.TaskTextFiles)
                    if (GUILayout.Button((SameTaskText(runner.TaskTextDisplayName, f) ? "● " : "") + f.Replace(PlacementTaskText.TaskTextFolder + "/", ""), _button, GUILayout.ExpandWidth(false), GUILayout.Height(30)))
                        runner.SelectTaskText(f);
                GUILayout.EndHorizontal();
            }
            GUILayout.Space(8);
            var keep = GUI.backgroundColor;
            GUI.backgroundColor = PrimaryTint;
            if (GUILayout.Button("확인", _button, GUILayout.Height(ButtonH))) runner.Check();
            GUI.backgroundColor = keep;
        }

        /// <summary>가장 최근 세션 자동 채움 결과(눈에 띄게, Setup 맨 위). 실험자가 아래 칸·단추로 바꿀 수 있다.</summary>
        void DrawAutoFill()
        {
            var r = runner.AutoFill;
            if (r == null) return;
            var p = r.Pick;
            if (p != null)
            {
                var now = System.DateTimeOffset.Now;
                bool stale = PlacementLatestSession.IsStale(p.SavedAt, now, runner.AutoFillStaleMinutes);
                string who = p.ParticipantNumber.HasValue ? $"참여자 번호 <b>{p.ParticipantNumber.Value}</b>"
                    : $"참여자 번호 <color={ColWarn}>파일에 없음 — 손으로 넣으세요</color>" + (p.ParticipantIdRaw != null ? $"(participantId {p.ParticipantIdRaw})" : "");
                string when = $"저장 {p.SavedAt.ToLocalTime():HH:mm}({PlacementLatestSession.AgeText(p.SavedAt, now)}){(p.SavedFromFile ? "" : " — 파일 수정 시각")}";
                GUILayout.Label($"자동으로 고른 세션: <b>{p.SessionId}</b>   {who}   " +
                                (stale ? $"<color={ColWarn}>{when} — {runner.AutoFillStaleMinutes:0}분보다 오래됨, 이 참여자의 세션인지 확인</color>" : when), _alert);
                if (runner.AutoFillRunThisProcess)
                    GUILayout.Label($"<color={ColWarn}>이 세션은 이번 Play에서 이미 시작한 적이 있습니다(같은 세션을 다시 돌리는지 확인)</color>", _alert);
                else if (runner.AutoFillHasRecord)
                    GUILayout.Label($"<color={ColWarn}>이 세션 ID의 배치 기록 폴더가 이미 있습니다(이미 돌린 세션인지 확인)</color>", _alert);
                if (p.NotRunnerReady)
                    GUILayout.Label($"<color={ColWarn}>챗봇이 이 선택 파일을 아직 러너에 넘길 수 없다고 적었습니다(조절·사전 측정이 끝났는지 확인 — 확인 단계에서 거부됨)</color>", _wrap);
                if (!runner.SessionFilesAreAutoFilled)
                    GUILayout.Label($"<color={ColMuted}>spec·선택 파일 칸을 바꿨습니다 — 기록에는 auto_overridden으로 남습니다</color>", _small);
            }
            else if (r.FutureTimestamp)   // CP16-3: 시계 오류 — 이전 참여자 파일일 수 있어 크게 알린다
                GUILayout.Label($"<color={ColError}>최근 세션을 자동으로 채우지 않았습니다({r.RejectedSessionId ?? "-"}): {r.Rejected}. PC 시계를 확인하고 파일을 손으로 고르세요</color>", _stage);
            else if (r.Rejected != null)
                GUILayout.Label($"<color={ColWarn}>최근 세션을 자동으로 채우지 않았습니다({r.RejectedSessionId ?? "-"}): {r.Rejected} — 파일을 손으로 고르세요</color>", _alert);
            else
                GUILayout.Label($"<color={ColMuted}>최근 세션 자동 채움: 챗봇 선택 파일이 없습니다(spec·선택 파일을 손으로 고르세요)</color>", _small);
            if (r.NewerSpecWithoutSelection != null)
                GUILayout.Label($"<color={ColWarn}>더 늦게 저장된 spec {r.NewerSpecWithoutSelection}.json에는 아직 선택 파일이 없습니다(그 세션이 진행 중일 수 있음)</color>", _wrap);
            if (GUILayout.Button("최근 세션 다시 찾기", _button, GUILayout.Width(220), GUILayout.Height(30))) runner.AutoFillLatestSession();
            GUILayout.Space(4);
        }

        /// <summary>본 실험 설정 고정(lockExperimentPreset)일 때 고정 항목 대신 보이는 요약.</summary>
        void DrawLockSummary(PlacementConfig cfg)
        {
            var refusals = PlacementExperimentLock.Refusals(cfg, runner.TaskTextDisplayName, runner.TaskText);
            bool holds = refusals.Count == 0;
            GUILayout.Label(holds ? $"<color={ColOk}>본 실험 설정 고정</color> <color={ColMuted}>(lockExperimentPreset — 설계 뼈대 3절. 바꾸려면 씬에서 잠금을 끈다)</color>"
                                  : $"<color={ColError}>본 실험 설정 고정인데 값이 어긋났습니다 — [확인]을 누르면 설정은 다시 적용합니다. 문구 파일(판·키)이 어긋나면 시작하지 않습니다</color>", _alert);
            foreach (var x in refusals) GUILayout.Label($"<color={ColError}>{x}</color>", _small);
            foreach (var line in PlacementExperimentLock.SummaryLines(cfg, runner.TaskTextDisplayName, runner.TaskText?.Version))
                GUILayout.Label("  · " + line, _small);
        }

        /// <summary>잠금이 꺼졌을 때: 권고 설정 단추·공간·놓기 도움·연습.</summary>
        void DrawPresetControls(PlacementConfig cfg)
        {
            // 설계 뼈대 3절 본 실험 권고 설정(G59-8 + G63 묶음)을 한 번에. 아래 낱개 체크로 다시 바꿀 수 있다
            bool presetOn = cfg.ExperimentPresetOn && SameTaskText(runner.TaskTextDisplayName, PlacementConfig.ExperimentTaskTextFile);
            if (GUILayout.Button((presetOn ? "● " : "") + "본 실험 권고 설정 켜기(설계 뼈대 3절: 공간 B + 놓기 도움, 두 조건 연습, 자리 문항 → 멈춤 거리, 평정 중 물체 숨김, UI 묶음 G63, 반복 멈춤, 눈높이 기준 배치, 문구 scaleA)",
                    _button, GUILayout.ExpandWidth(true), GUILayout.Height(30)))
            {
                cfg.ApplyExperimentPreset();
                runner.SelectTaskText(PlacementConfig.ExperimentTaskTextFile);
                runner.RefreshSpace();
            }
            DrawSpaceButtons(cfg, false);
            bool assist = GUILayout.Toggle(cfg.placementAssist, " 놓기 도움(G53): 배치 연습 1회, 든 동안 수직선·바닥 고리, 경계 띠 밝아짐, 범위 안내 문장(초안) — 직접 배치 조건", _toggle);
            if (assist != cfg.placementAssist)
            {
                cfg.placementAssist = assist;
                if (!assist) cfg.practiceInAllConditions = false;   // 연습은 놓기 도움의 일부(G59) — 도움을 끄면 함께 끈다
                runner.RefreshSpace();
            }
            if (cfg.placementAssist)
                cfg.practiceInAllConditions = GUILayout.Toggle(cfg.practiceInAllConditions,
                    "   └ 배치 연습을 보기만 조건에서도(practiceInAllConditions — 조건 전 컨트롤러 경험을 같게. 본 실험 켬, G59-8)", _toggle);
        }

        /// <summary>배경 공간 단추 세 개(기본 neutral · 자연 nature · 우주 space). 2026-11-28 연구 책임자 결정: 공간은 실험자가 여기서 고른다 —
        /// 잠금(실험 씬)에서도 보이고 세션마다 고른다(기본으로 눌린 값 neutral). 고른 공간은 manifest config·environment에 남는다.
        /// 참여자가 헤드셋에서 고르는 단계(environmentChoice participant)는 꺼 둔 기능이라 이 화면에 토글을 두지 않는다(인스펙터·명령줄로만).</summary>
        void DrawSpaceButtons(PlacementConfig cfg, bool locked)
        {
            GUILayout.Label(locked
                ? "배경 공간 — 실험자가 고른다(세션마다. 기본 neutral). 고른 공간이 이 세션 내내 보이고 기록에 남는다"
                : "배경 공간(G52 — 후보 B = neutral + 놓기 도움, E = space + 놓기 도움, F = nature + 놓기 도움)", _wrap);
            GUILayout.BeginHorizontal();
            foreach (var env in PlacementConfig.Environments)
                if (GUILayout.Button((cfg.environment == env ? "● " : "") + SpaceButtonLabel(env), _button, GUILayout.Width(150), GUILayout.Height(30)) && cfg.environment != env)
                {
                    cfg.environment = env;
                    runner.RefreshSpace();
                }
            GUILayout.FlexibleSpace();
            GUILayout.EndHorizontal();
            if (cfg.ParticipantChoosesSpace)   // 잠금이면 [확인]이 experimenter로 되돌리고, 아니면(개발) 인스펙터·명령줄로 켠 것
                GUILayout.Label($"<color={ColWarn}>참여자 공간 고르기 단계가 켜져 있습니다(environmentChoice participant — 꺼 둔 기능, 인스펙터·명령줄로만). " +
                                (locked ? "본 실험 설정 고정이라 [확인]에서 experimenter로 되돌립니다" : "위 공간은 고르기 전·대기 공간입니다") + "</color>", _small);
        }

        /// <summary>공간 단추 글: 한국어 이름 + 설정 값(기록과 맞춰 보게).</summary>
        public static string SpaceButtonLabel(string env) =>
            env == PlacementConfig.EnvironmentNeutral ? "기본 (neutral)"
            : env == PlacementConfig.EnvironmentNature ? "자연 (nature)"
            : env == PlacementConfig.EnvironmentSpace ? "우주 (space)" : env;

        /// <summary>잠금이 꺼졌을 때: 절차 토글(물체 숨김·점검 순서·반복 멈춤·눈높이·UI 묶음).</summary>
        void DrawProcedureToggles(PlacementConfig cfg)
        {
            cfg.hideObjectDuringItems = GUILayout.Toggle(cfg.hideObjectDuringItems, " 평정 동안 물체 숨기기(본 실험 켬, G59-8)", _toggle);
            cfg.checkBeforeStopDistance = GUILayout.Toggle(cfg.checkBeforeStopDistance,
                " 점검 문항을 멈춤 거리 앞에(checkBeforeStopDistance — 사후 평정 바로 뒤. 기본: 멈춤 거리 뒤. 본 실험 켬, G59-8)", _toggle);
            bool loop = GUILayout.Toggle(cfg.IsStopLoop,
                $" 멈춤 거리 반복 멈춤(stopMode loop — 왕복 경로, 트리거로 멈춤/다시 움직임, A·X로 확정, 연습 {cfg.stopLoopPracticeRounds}(상한 {cfg.stopLoopPracticeRoundSeconds:0.#}초) + 본 {cfg.stopLoopRounds}라운드. 기본: 한 번 누름. 본 실험 loop, G60-2)", _toggle);
            cfg.stopMode = loop ? PlacementConfig.StopModeLoop : PlacementConfig.StopModeSingle;
            bool eyeRel = GUILayout.Toggle(cfg.IsEyeRelative,
                " 눈높이 기준 배치(eyeHeightMode relative — Check 뒤 H로 눈높이를 재고 물체 높이를 E − 1.60 m만큼 옮김. 기본: 절대 높이. 본 실험 relative, G60-3)", _toggle);
            cfg.eyeHeightMode = eyeRel ? PlacementConfig.EyeHeightRelative : PlacementConfig.EyeHeightNone;
            if (eyeRel)
            {
                bool seated = GUILayout.Toggle(cfg.IsSeated,
                    $"   └ 앉은 자세로 보정·과제(eyeCalibPosture seated — 범위 [{cfg.eyeHeightSeatedMinM:0.00}, {cfg.eyeHeightSeatedMaxM:0.00}] m. 끄면 선 자세 [{cfg.eyeHeightMinM:0.00}, {cfg.eyeHeightMaxM:0.00}] m. 본 실험 앉은 자세, 2026-11-28)", _toggle);
                cfg.eyeCalibPosture = seated ? PlacementConfig.PostureSeated : PlacementConfig.PostureStanding;
            }
            // G63 헤드셋 UI 개선 묶음: (1) 판 35° 안(줄 24자·지시문 쪽 나누기) (2) 어두운 판 (3) 광선 겨눔 (4) 햅틱 (5) 평정 확정 표시 (6) 평정 칸 0.20 m
            bool bundle = GUILayout.Toggle(cfg.UiBundleOn,
                " 헤드셋 UI 개선 묶음(G63 — 판 35° 안·어두운 판·광선 겨눔·햅틱·평정 확정 표시·평정 칸 0.20 m. 문구·문항·평정 방식은 그대로. 기본 꺼짐)", _toggle);
            if (bundle != cfg.UiBundleOn)
            {
                if (bundle) cfg.ApplyUiBundle();
                else cfg.uiComfortWrap = cfg.uiDarkPanel = cfg.uiRayHover = cfg.uiHaptics = cfg.uiRatingConfirmFlash = cfg.uiNarrowScale = false;
            }
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
            string spaceChoice = SpaceChoiceLine(s);
            if (spaceChoice != null) GUILayout.Label(spaceChoice, _wrap);
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
            if (s.Phase == PlacementPhase.Practice)
                GUILayout.Label($"<b>배치 연습</b>(본 결과 아님) — 상자 {(s.PracticeHeld ? "드는 중" : "놓임")}, 목표까지 {s.PracticeErrorM:0.00} m, 잡기 {s.PracticeGrabCount}회. " +
                                "참여자가 확인을 누르면 끝, 실험자는 '다음'(Enter)으로 건너뛸 수 있다", _wrap);
            if (s.Phase == PlacementPhase.StopDistance)
            {
                if (s.Config.IsStopLoop)
                {
                    // G60-2 반복 멈춤: 라운드·움직임 상태·멈춤 횟수·남은 시간
                    var r = s.CurrentStopRound;
                    GUILayout.Label(!s.StopTrialsStarted ? "멈춤 거리(반복 멈춤): 안내를 확인한 뒤 '다음'(Enter)으로 시작"
                        : r == null ? "멈춤 거리(반복 멈춤): 라운드 사이"
                        : $"멈춤 거리 라운드 {r.Round}/{s.StopLoopPlan.Count} {(r.Practice ? "(연습)" : "")}  {(s.StopLoopMoving ? (s.StopLoopDirection < 0 ? "가까워지는 중" : "멀어지는 중") : "<b>멈춤</b>")}  " +
                          $"지금 {s.StopDistanceNow:0.00} m  멈춤 {s.StopLoopStopCount}회  남은 {s.StopLoopSecondsLeft:0} s" +
                          (s.StopLoopXrPaused ? "  <b>XR 끊김 — 시간·물체 멈춤</b>" : ""), _wrap);
                }
                else
                {
                    var t = s.CurrentStopTrial;
                    GUILayout.Label(!s.StopTrialsStarted ? "멈춤 거리: 안내를 확인한 뒤 '다음'(Enter)으로 시작"
                        : $"멈춤 거리 시행 {t?.Trial ?? 0}/{s.StopPlan.Count} {(t != null && t.Practice ? "(연습)" : "")} {t?.Direction}  지금 {s.StopDistanceNow:0.00} m", _wrap);
                }
            }
            // 참여자 조작 안내(늘 보이게, 단추 위)
            string help = s.Phase == PlacementPhase.SpaceChoice
                ? (runner.ActiveInputSource == XrPlacementInput.Source ? "참여자 XR 조작(공간 고르기): 방아쇠 = 다음 공간, A·X = 지금 공간으로 정하기(세 공간을 다 본 뒤)"
                                                                       : "참여자 데스크톱 조작(공간 고르기): Space = 다음 공간, F = 지금 공간으로 정하기(세 공간을 다 본 뒤)")
                : runner.ActiveInputSource == XrPlacementInput.Source
                ? "참여자 XR 조작: 광선으로 가리키고 트리거(또는 그립) 누르고 있기 = 잡기, 썸스틱 앞/뒤 = 밀기/당기기, A·X = 확인, " +
                  (s.Config.IsStopLoop ? "멈춤 거리: 트리거 = 멈춤/다시 움직임, A·X = 이 자리로 확정(멈춘 상태에서만)" : "트리거 = 멈춤 거리 버튼") +
                  (s.Config.participantRatesWithController ? ", 평정: 썸스틱 좌우 고르기·트리거 확정" : "") + ".  실험자 R = 정면 재설정"
                : "참여자 데스크톱 조작: 왼쪽 단추 누르고 있기 = 잡기, 휠 또는 E/Q = 밀기/당기기, F = 확인, " +
                  (s.Config.IsStopLoop ? "멈춤 거리: Space = 멈춤/다시 움직임, F = 확정(멈춘 상태에서만)" : "Space = 멈춤 거리 버튼") + ". 오른쪽 드래그·WASD = 둘러보기·이동";
            GUILayout.Label($"<color={ColMuted}>{help}</color>", _small);

            bool waits = s.Phase == PlacementPhase.SpaceChoice || s.Phase == PlacementPhase.Intro || s.Phase == PlacementPhase.Practice || s.Phase == PlacementPhase.PreWait || s.Phase == PlacementPhase.PostWait
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
