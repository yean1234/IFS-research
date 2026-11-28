// 배치 실험(RQ V4) 한 회기의 단계 흐름과 기록(UnityEngine 없이 — dotnet 테스트에서도 끝까지 돈다).
//   intro → [practice] → baseline → pre_items → pre_wait → condition → post_items → post_wait → stop_distance → check_items → done
//   (setup은 러너가 세션을 만들기 전 단계라 기록에 없다. *_items는 해당 when 문항이 없으면 건너뛴다.
//    설정 checkBeforeStopDistance(G59, 2026-11-25, 기본 꺼짐)를 켜면 점검 평정을 사후 평정 바로 뒤로 옮긴다:
//    … → post_items → check_items → post_wait → stop_distance → done.
//    practice는 놓기 도움 placementAssist를 켠 직접 배치 조건에서만 있다(G53, 2026-11-24) — 뜻 없는 회색 상자를 표시된 자리로 옮기고 확인.
//    practiceInAllConditions(G59, 기본 꺼짐)를 함께 켜면 보기만 조건에서도 같은 연습을 한다.
//    연습은 events.csv(practice_*)와 practice.json에만 남고 placement.json·trajectory.json·objpose.csv에는 들어가지 않는다.)
// 멈춤 거리(2026-11-26 G60-2): 설정 stopMode single(기본)은 예전 그대로(한 번 누르면 시행 끝), loop는 왕복 경로에서 멈춤/재개를
//   여러 번 하고 확정 버튼으로 정한다(StepStopLoop — stoprounds.csv·stopadjust.csv).
// 눈높이(2026-11-26 G60-3): 설정 eyeHeightMode relative면 시작·멈춤 경로·system_move 목표·연습 목표 높이에 (E − 기준)을 더한다(Eye()).
//   E는 PlacementSessionInfo.EyeHeight(러너의 보정 결과). none이면 더하는 값이 0이라 예전과 같다.
// 공간 고르기(2026-11-28 연구 책임자 결정): 설정 environmentChoice participant면 intro 앞에 space_choice 단계가 있다. 방아쇠(데스크톱 Space)로
//   세 공간을 차례로 보고(순서 = PlacementSpaceChoice.Order(참여자 번호)), 세 공간을 다 본 뒤 확인 버튼(A·X, 데스크톱 F)으로 정한다.
//   실험자 Enter = 지금 보이는 공간으로 정함. 정하면 확정 알림(confirm_done)을 ConfirmNoticeSeconds 동안 보인 뒤 intro. 고른 공간이 세션의
//   environment가 되고 manifest를 다시 쓴다(environmentChoice 블록 — 순서·고른 값·고른 방식·걸린 시간·공간마다 본 시간). 기본(experimenter)이면 단계 없음.
// 시계: Tick(dt)으로 받은 dt를 더한 시각(사람 실행은 Time.unscaledDeltaTime, 자동 시행은 고정 dt).
// 물체 위치·보이기·참여자 글은 이 클래스가 정하고, Unity 러너(PlacementRunner)는 그대로 그린다.
// 기록 형식: 계약 ifs-placement/0.2(PlacementRecordWriter — 0.1에 선택 파일·적용한 덮어쓰기 키만 더함. 2026-11-24 G52–G53: 공간 설정이
//   기본값이 아닐 때만 manifest environment와 config 키, 연습이 있을 때만 practice.json과 events practice_*).
// 평정: 문항마다 범위(문구 파일 min·max, 기본 1–7). 실험자 숫자 키는 범위가 한 자리(max ≤ 9)면 예전처럼 한 번 누르면 입력,
//   두 자리 이상이면 숫자를 이어 붙인다(0–10에서 1 → 0 = 10, 범위를 넘는 숫자는 받지 않음, 0 뒤에는 붙이지 않음). Backspace 취소, Enter 확정.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public enum PlacementPhase { Setup, SpaceChoice, Intro, Practice, Baseline, PreItems, PreWait, Condition, PostItems, PostWait, StopDistance, CheckItems, Done }

    public sealed class PlacementSession : IDisposable
    {
        public const string StateIdle = "idle";
        public const string StateHeld = "held";
        public const string StateSystem = "system";
        public const string StateReplay = "replay";
        public const string StateStop = "stop";

        const double Eps = 1e-9;
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        readonly PlacementConfig _cfg;
        readonly PlacementTaskText _text;
        readonly PlacementTrajectory _replay;
        readonly PlacementSessionInfo _info;
        PlacementRecordWriter _writer;
        readonly HeadSampleClock _clock;

        double _now, _phaseStart, _condStart;
        HeadPose _head = HeadPose.At(0, 1.6, 0);
        string _headSource;

        // 물체
        PVec3 _obj;
        bool _visible;
        string _state = StateIdle;

        // 직접 배치
        bool _held;
        double _hold;
        PVec3 _grabOffset;
        double _grabStart;
        int _grabCount;
        long? _firstGrabMs;
        double _heldSeconds;
        double _pathLength;
        bool _confirmed;
        long? _confirmMs;

        // 시스템 이동·가리켜 지정·재생
        bool _moving, _moveStarted;
        PVec3 _moveTarget;
        PVec3? _pointer;
        bool _replayEnded;

        // 조건 단계 결과
        PlacementTrajectory _trajectory;
        bool _conditionWritten;
        bool _conditionCompleted;
        PVec3 _conditionFinal;

        // 평정
        List<PlacementItem> _items;
        int _itemIndex;
        string _itemsWhen;
        int? _pending;
        string _digits = "";   // 여러 자리 범위에서 실험자가 이어 친 숫자(확정 전)
        double _askedAt, _pendingAt;
        bool _instruction;   // 평정 지시문을 보이는 중(첫 문항 전)
        int? _cursor;        // 참여자 컨트롤러로 고르는 중인 값(participantRatesWithController)

        // 배치 연습(G53). 본 과제의 잡기·경로·확인 값과 섞이지 않게 따로 둔다
        PVec3 _pracPos, _pracTarget;
        bool _pracHeld, _pracWritten;
        double _pracHold, _pracStartTime, _pracGrabStart, _pracHeldSeconds;
        PVec3 _pracGrabOffset;
        int _pracGrabCount;

        // 멈춤 거리
        List<StopTrialPlan> _stopPlan;
        int _stopIndex = -1;
        bool _stopStarted, _trialActive;
        double _itiUntil, _trialStart, _stopD;
        bool _stopPrevHeld;   // 직전 프레임에 멈춤 버튼이 눌려 있었나(눌림의 '내려가는 순간'만 인정하려고)

        // 멈춤 거리 반복 멈춤(G60-2, stopMode loop)
        List<StopRoundPlan> _loopPlan;
        int _roundIndex = -1;
        bool _roundActive, _loopMoving;
        int _loopDir;   // −1 = 가까워짐(approach), +1 = 멀어짐(recede)
        double _roundStart, _lastChange, _lastToggle;
        readonly List<double> _loopStops = new List<double>();
        readonly List<double> _loopPoints = new List<double>();   // 출발·끝점 반사·멈춤 자리(확정 전에 지나간 횟수 계산)
        int _loopResumes;
        string _loopLastStopDir;

        // 눈높이(G60-3)
        readonly double _eyeOffset;
        // 높이 하한(CP17-3, 2026-11-28 앉은 자세): relative에서 옮긴 물체 높이가 (물체 경계 반지름 + FloorClearanceM)보다 낮으면 그 값으로 올린다.
        //   연습 목표는 (연습 상자 한 변 / 2 + FloorClearanceM). 설정 높이·E·반지름으로 시작 때 정해지고 세션 동안 바뀌지 않는다.
        readonly double _startH, _stopH, _sysMoveH, _pracTargetH, _objFloor, _cubeFloor;
        readonly List<string> _heightFloored = new List<string>();
        // 안내 판 하한(러너가 판을 놓을 때마다 알려 준다 — ReportPanelCenter)
        int _panelReports;
        bool _panelFloorApplied;
        double _panelBase = double.NaN, _panelMin = double.PositiveInfinity, _panelMax = double.NegativeInfinity;
        // 세션 중 XR 끊김(CP17-1): 러너가 매 프레임 알려 준다(ReportXrHead). XR로 시작한 사람 실행(info.XrMonitored)만
        bool _xrLost;
        int _xrLostCount;
        double _xrLostAt, _xrLostTotal;

        // 공간 고르기(2026-11-28, environmentChoice participant)
        string[] _spaceOrder;
        int _spaceIndex;
        readonly HashSet<string> _spaceSeen = new HashSet<string>(StringComparer.Ordinal);
        readonly Dictionary<string, double> _spaceViewSeconds = new Dictionary<string, double>(StringComparer.Ordinal);
        double _spaceStart, _spaceShownAt, _spaceAdvanceAt;
        int _spaceSwitches, _spaceIgnored;
        bool _spaceDecided;
        string _spaceBefore;

        // 헤드셋 UI 개선(G63) — 설정 ui*·hidePanelInDistancePhases를 켰을 때만 쓴다(꺼져 있으면 흐름·기록이 G63 전과 같다)
        List<string> _instrPages;   // (1) 평정 지시문을 문장 경계에서 나눈 쪽(한 쪽이면 null)
        int _instrPage;
        double _flashUntil = double.NegativeInfinity;   // (5) 확정 표시가 끝나는 시각(그 전에는 다음 문항으로 가지 않는다)
        bool _flashing;
        bool _panelHiddenLogged;   // (7) 이 단계에서 panel_hidden을 남겼나
        readonly List<PlacementHapticPulse> _haptics = new List<PlacementHapticPulse>();   // (4) 러너가 가져가 컨트롤러로 보낸다

        public PlacementSession(PlacementConfig cfg, PlacementTaskText text, PlacementSessionInfo info, string recordRoot,
            PlacementTrajectory replay = null, IEnumerable<string> warnings = null)
        {
            if (cfg == null) throw new ArgumentNullException(nameof(cfg));
            var errors = cfg.Validate();
            if (errors.Count > 0) throw new ArgumentException("설정 오류: " + string.Join("; ", errors));
            _cfg = cfg.Clone();
            _text = text ?? throw new ArgumentNullException(nameof(text));
            if (_cfg.placementAssist && _text.AssistKeysMissing().Count > 0)
                throw new ArgumentException("놓기 도움(placementAssist)을 켰는데 문구 파일에 " + string.Join(", ", _text.AssistKeysMissing()) + " 문구가 없습니다(문구 파일 0.3 이상)");
            if (_cfg.IsStopLoop && _text.LoopKeysMissing().Count > 0)
                throw new ArgumentException("멈춤 거리 반복 멈춤(stopMode loop)을 켰는데 문구 파일에 " + string.Join(", ", _text.LoopKeysMissing()) + " 문구가 없습니다(문구 파일 0.6 이상)");
            if (_cfg.ParticipantChoosesSpace && _text.SpaceChoiceKeysMissing().Count > 0)
                throw new ArgumentException("참여자가 공간을 고르게(environmentChoice participant) 했는데 문구 파일에 " + string.Join(", ", _text.SpaceChoiceKeysMissing()) + " 문구가 없습니다(문구 파일 0.9 이상)");
            _info = info ?? new PlacementSessionInfo();
            if (_cfg.EffectiveControlMode == PlacementConfig.ModeReplay && (replay == null || replay.Samples.Count == 0))
                throw new ArgumentException("controlMode replay에는 재생할 궤적이 필요합니다");
            if (_cfg.IsEyeRelative)
            {
                // G60-3: relative에서는 눈높이(보정 결과 또는 데스크톱 고정값)가 있어야 시작한다
                var eye = _info.EyeHeight;
                if (eye == null) throw new ArgumentException("eyeHeightMode relative인데 눈높이 보정이 없습니다(Check 단계에서 H로 재기)");
                if (eye.Source != EyeHeightInfo.SourceDesktopFixed && (eye.MeasuredM < _cfg.EyeRangeMinM - 1e-9 || eye.MeasuredM > _cfg.EyeRangeMaxM + 1e-9))
                    throw new ArgumentException(_cfg.IsSeated
                        ? $"눈높이 {eye.MeasuredM.ToString("0.000", Inv)} m가 앉은 자세 범위 [eyeHeightSeatedMinM, eyeHeightSeatedMaxM] 밖입니다"
                        : $"눈높이 {eye.MeasuredM.ToString("0.000", Inv)} m가 [eyeHeightMinM, eyeHeightMaxM] 밖입니다");
                _eyeOffset = _cfg.EyeOffsetFor(eye.MeasuredM);
            }
            // CP17-3: relative에서만 높이 하한(none이면 Eye()가 설정 높이 그대로라 하한을 두지 않는다 — 예전과 같은 값)
            double objFloor = _objFloor = _cfg.IsEyeRelative && _info.ObjectBoundingRadiusM is double rad && rad > 0 ? rad + FloorClearanceM : 0;
            double cubeFloor = _cubeFloor = _cfg.IsEyeRelative ? _cfg.practiceCubeSizeM / 2 + FloorClearanceM : 0;
            _startH = Floored(Eye(_cfg.startHeightM), objFloor, "start");
            _stopH = Floored(Eye(_cfg.stopHeightM), objFloor, "stop");
            _sysMoveH = Floored(Eye(_cfg.systemMoveTargetHeightM), objFloor, "system_move_target", _cfg.EffectiveControlMode == PlacementConfig.ModeSystemMove);
            _pracTargetH = Floored(Eye(_cfg.practiceTargetHeightM), cubeFloor, "practice_target", _cfg.HasPractice);
            // 앉은 자세이거나 하한이 걸린 세션만 manifest heightFloor(선 자세에서 걸리지 않으면 키 없음 — 기존 relative 기록과 같은 바이트)
            _info.HeightFloor = _cfg.IsEyeRelative && (_cfg.IsSeated || _heightFloored.Count > 0) ? HeightFloorJson(objFloor, cubeFloor) : null;
            if (_info.XrMonitored) _info.XrConnection = XrConnectionJson();
            _replay = replay;
            _clock = new HeadSampleClock(_cfg.headSampleHz);
            _headSource = _info.HeadSource;
            GrabRadiusM = _cfg.grabRadiusMinM;
            StartPosition = PlacementGeometry.FromPolar(_cfg.startDistanceM, 0, _startH);
            _obj = StartPosition;
            _conditionFinal = StartPosition;
            _stopPlan = StopDistanceSchedule.Build(_cfg, _info.ParticipantNumber);
            if (_cfg.IsStopLoop) _loopPlan = StopLoopSchedule.Build(_cfg, _info.ParticipantNumber);

            if (_cfg.ParticipantChoosesSpace)
            {
                _spaceOrder = PlacementSpaceChoice.Order(_info.ParticipantNumber);
                _spaceBefore = _cfg.environment;
                _info.SpaceChoice = SpaceChoiceJson(null, null);   // 고르기 전 — 정하면(또는 중단하면) manifest를 다시 쓴다
            }

            _writer = new PlacementRecordWriter(recordRoot, _info.ParticipantNumber, _info.SessionId, _info.StartedUtc);
            RecordDirectory = _writer.Directory;
            try
            {
                if (_cfg.IsStopLoop) _writer.EnableStopLoop();   // G60-2: loop일 때만 stoprounds.csv·stopadjust.csv
                _writer.WriteJson(PlacementRecordWriter.ManifestFile, PlacementManifest.Build(_cfg, _info));
            }
            catch
            {
                _writer.Dispose();
                throw;
            }
            Event("session_start", $"participant={_info.ParticipantNumber};condition={_cfg.condition};controlMode={_cfg.EffectiveControlMode};" +
                                   $"headSource={_info.HeadSource};inputSource={_info.InputSource}");
            if (_info.AutoMode) Event("auto_mode", "scripted inputs (verification only, not participant data)");
            if (_cfg.IsEyeRelative) Event("eye_height_calibrated", _info.EyeHeight.EventDetail(_cfg));
            foreach (var w in warnings ?? Enumerable.Empty<string>()) Event("warning", w);
            GoTo(_cfg.ParticipantChoosesSpace ? PlacementPhase.SpaceChoice : PlacementPhase.Intro);
        }

        // ── 읽기 ─────────────────────────────────────────────────────────
        public PlacementConfig Config => _cfg;
        public PlacementTaskText TaskText => _text;
        public PlacementPhase Phase { get; private set; } = PlacementPhase.Setup;
        public string PhaseLabel => PhaseName(Phase);
        public double Now => _now;
        public double SecondsInPhase => _now - _phaseStart;
        /// <summary>제시·조건 단계의 남은 시간(초). 다른 단계는 NaN.</summary>
        public double PhaseSecondsLeft =>
            Phase == PlacementPhase.Baseline ? Math.Max(0, _cfg.baselineSeconds - SecondsInPhase)
            : Phase == PlacementPhase.Condition ? Math.Max(0, _cfg.conditionSeconds - SecondsInPhase)
            : double.NaN;
        public PVec3 StartPosition { get; }
        public PVec3 ObjectPosition => _obj;
        public bool ObjectVisible => _visible;
        public string ObjectState => _state;
        public bool Held => _held;
        public double HoldDistanceM => _hold;
        /// <summary>광선 잡기 판정 구 반지름(m). 러너가 물체 경계로 정한다(grabRadiusMinM 이상).</summary>
        public double GrabRadiusM { get; set; }
        /// <summary>가리켜 지정: 지금 가리키는 바닥 점(없으면 null).</summary>
        public PVec3? PointerHit => _pointer;
        /// <summary>시스템 이동·가리켜 지정의 지금 목표(움직이는 중이 아니면 null).</summary>
        public PVec3? MoveTarget => _moving ? _moveTarget : (PVec3?)null;
        public string ParticipantTextKey { get; private set; }
        /// <summary>참여자에게 보일 글(없으면 null).</summary>
        public string ParticipantText { get; private set; }
        public PlacementItem CurrentItem => (Phase == PlacementPhase.PreItems || Phase == PlacementPhase.PostItems || Phase == PlacementPhase.CheckItems)
            && !_instruction && _items != null && _itemIndex < _items.Count ? _items[_itemIndex] : null;
        public string CurrentItemWhen => _itemsWhen;
        public int? PendingRating => _pending;
        /// <summary>평정 단계의 지시문을 보이는 중(첫 문항 전, 실험자 Enter로 넘어감).</summary>
        public bool ItemsInstructionActive => InItems && _instruction;
        /// <summary>참여자가 컨트롤러로 고르는 중인 값(participantRatesWithController, 아직 확정 전). 없으면 null.</summary>
        public int? RatingCursor => CurrentItem != null ? _cursor : null;
        /// <summary>지금 문항 번호(1부터)와 이 단계의 문항 수. 평정 단계가 아니면 (0, 0).</summary>
        public int ItemNumber => CurrentItem != null ? _itemIndex + 1 : 0;
        public int ItemCount => InItems && _items != null ? _items.Count : 0;
        // ── 배치 연습(G53) ─────────────────────────────────────────────
        /// <summary>배치 연습 단계다(놓기 도움을 켠 직접 배치 조건).</summary>
        public bool PracticeActive => Phase == PlacementPhase.Practice;
        /// <summary>연습 상자 중심 자리(연습 단계 밖에서는 마지막 값).</summary>
        public PVec3 PracticePosition => _pracPos;
        /// <summary>연습 목표 자리(설정 practiceTarget*).</summary>
        public PVec3 PracticeTarget => _pracTarget;
        public bool PracticeHeld => _pracHeld;
        public double PracticeHoldDistanceM => _pracHold;
        public int PracticeGrabCount => _pracGrabCount;
        /// <summary>연습 상자 중심과 목표 자리 사이 거리(m).</summary>
        public double PracticeErrorM => PVec3.Distance(_pracPos, _pracTarget);
        /// <summary>연습 상자 잡기 판정 구 반지름(m): 상자 반대각선(한 변 × √3 / 2)과 grabRadiusMinM 중 큰 값.</summary>
        public double PracticeGrabRadiusM => Math.Max(_cfg.grabRadiusMinM, _cfg.practiceCubeSizeM * Math.Sqrt(3) / 2);
        public bool StopTrialsStarted => _stopStarted;
        public bool StopTrialActive => _trialActive;
        public StopTrialPlan CurrentStopTrial => _stopIndex >= 0 && _stopIndex < _stopPlan.Count ? _stopPlan[_stopIndex] : null;
        public IReadOnlyList<StopTrialPlan> StopPlan => _stopPlan;
        public double StopDistanceNow => _stopD;
        // ── 멈춤 거리 반복 멈춤(G60-2) ─────────────────────────────────
        /// <summary>loop 라운드 계획(single이면 null).</summary>
        public IReadOnlyList<StopRoundPlan> StopLoopPlan => _loopPlan;
        /// <summary>지금 라운드(라운드 사이·시작 전이면 null).</summary>
        public StopRoundPlan CurrentStopRound => _roundActive && _loopPlan != null && _roundIndex >= 0 && _roundIndex < _loopPlan.Count ? _loopPlan[_roundIndex] : null;
        public bool StopRoundActive => _roundActive;
        /// <summary>loop 물체가 움직이는 중(라운드 안). 멈춰 있으면 false.</summary>
        public bool StopLoopMoving => _roundActive && _loopMoving;
        /// <summary>loop 진행 방향: −1 가까워짐, +1 멀어짐.</summary>
        public int StopLoopDirection => _loopDir;
        /// <summary>이번 라운드 멈춤 횟수.</summary>
        public int StopLoopStopCount => _loopStops.Count;
        /// <summary>직전 상태 변화(라운드 시작·멈춤·재개)부터 지난 시간(초).</summary>
        public double StopLoopSecondsSinceChange => _roundActive ? _now - _lastChange : 0;
        /// <summary>이번 라운드 남은 시간(초). 라운드 밖이면 NaN.</summary>
        public double StopLoopSecondsLeft => _roundActive ? Math.Max(0, RoundLimitSeconds(_loopPlan[_roundIndex]) - (_now - _roundStart)) : double.NaN;
        /// <summary>이번 라운드가 시작된 뒤 지난 시간(초). 라운드 밖이면 NaN.</summary>
        public double StopLoopRoundElapsed => _roundActive ? _now - _roundStart : double.NaN;
        /// <summary>라운드 시간 상한(초): 연습 라운드는 stopLoopPracticeRoundSeconds, 본 라운드는 stopLoopRoundSeconds(2026-11-28).</summary>
        public double RoundLimitSeconds(StopRoundPlan plan) => plan != null && plan.Practice ? _cfg.stopLoopPracticeRoundSeconds : _cfg.stopLoopRoundSeconds;
        // ── 눈높이(G60-3) ───────────────────────────────────────────
        /// <summary>물체 높이를 옮긴 양(E − 기준, m). none이면 0.</summary>
        public double EyeOffsetM => _eyeOffset;
        // ── 헤드셋 UI 개선(G63) ─────────────────────────────────────────
        /// <summary>(1) 평정 지시문 한 쪽의 최대 줄 수(uiComfortWrap일 때만 쓴다). 러너가 판의 실제 자리로 다시 정한다
        /// (기본: 판 기본 자리에서 아래 가장자리가 35° 안인 줄 수).</summary>
        public int InstructionPageMaxLines { get; set; } = PlacementPanelMetrics.MaxBodyLinesWithin();
        /// <summary>(1) 지금 보이는 지시문 쪽 번호(1부터)와 쪽 수. 나누지 않았으면 (0, 0).</summary>
        public int InstructionPage => _instruction && _instrPages != null ? _instrPage + 1 : 0;
        public int InstructionPageCount => _instruction && _instrPages != null ? _instrPages.Count : 0;
        /// <summary>(5) 참여자가 방금 확정한 칸을 굵은 테두리로 보이는 중(uiRatingConfirmFlash). 이 동안 입력은 받지 않는다.</summary>
        public bool RatingConfirmFlash => _flashing;
        /// <summary>(7) 조건·멈춤 거리 단계에서 읽을 시간이 지나 안내 판을 숨기는 중(hidePanelInDistancePhases).</summary>
        public bool PanelHidden => _cfg.hidePanelInDistancePhases && !Finished
            && (Phase == PlacementPhase.Condition || Phase == PlacementPhase.StopDistance) && SecondsInPhase >= _cfg.hidePanelReadSeconds - Eps
            && !NoticeOnPanel;   // 2026-11-28: 확정 알림·본 측정 시작 안내가 보이는 동안은 판을 다시 보인다

        /// <summary>(4) 이번 프레임까지 쌓인 햅틱 펄스를 가져간다(러너가 XR 컨트롤러로 보낸다). events.csv haptic은 세션이 이미 남겼다.</summary>
        public List<PlacementHapticPulse> TakeHaptics()
        {
            var list = new List<PlacementHapticPulse>(_haptics);
            _haptics.Clear();
            return list;
        }

        /// <summary>(4) 햅틱 사건: uiHaptics를 켰을 때만 펄스를 쌓고 events.csv에 haptic 행을 더한다(기존 행은 그대로).</summary>
        void Haptic(string kind)
        {
            if (!_cfg.uiHaptics || Finished) return;
            var p = PlacementHaptics.For(kind);
            _haptics.Add(p);
            Event("haptic", p.EventDetail());
        }
        // ── 공간 고르기(2026-11-28) ───────────────────────────────────
        /// <summary>지금 그려야 할 배경 공간: 공간 고르기 중(정하기 전)이면 참여자가 보고 있는 공간, 아니면 세션 설정 environment(고른 값).</summary>
        public string ShownEnvironment => Phase == PlacementPhase.SpaceChoice && !_spaceDecided && _spaceOrder != null ? _spaceOrder[_spaceIndex] : _cfg.environment;
        /// <summary>공간 고르기 순서(참여자 번호로 돌림). 참여자가 고르지 않는 세션이면 null.</summary>
        public IReadOnlyList<string> SpaceChoiceOrder => _spaceOrder;
        /// <summary>지금 보이는 공간의 차례(0부터).</summary>
        public int SpaceChoiceIndex => _spaceIndex;
        /// <summary>지금까지 본 공간 수.</summary>
        public int SpaceChoiceSeenCount => _spaceSeen.Count;
        /// <summary>세 공간을 모두 봤다(참여자 확인은 이때부터 받는다).</summary>
        public bool SpaceChoiceSeenAll => _spaceOrder != null && _spaceSeen.Count >= _spaceOrder.Length;
        /// <summary>공간을 정했다(확정 알림을 보이는 중이거나 그 뒤).</summary>
        public bool SpaceChoiceDecided => _spaceDecided;
        /// <summary>정한 공간을 누가 정했나: participant_confirm | experimenter | abort. 정하기 전이면 null.</summary>
        public string SpaceChosenBy { get; private set; }
        /// <summary>이 세션의 눈높이 E(relative일 때 보정값, 아니면 null).</summary>
        public double? EyeHeightM => _cfg.IsEyeRelative ? _info.EyeHeight?.MeasuredM : null;
        public int GrabCount => _grabCount;
        public bool Confirmed => _confirmed;
        public double PathLengthM => _pathLength;
        public PVec3 ConditionFinalPosition => _conditionFinal;
        public PlacementTrajectory Trajectory => _trajectory;
        public bool Finished => _writer == null;
        public bool Completed { get; private set; }
        public string AbortedAt { get; private set; }
        public string RecordDirectory { get; private set; }

        public static string PhaseName(PlacementPhase p)
        {
            switch (p)
            {
                case PlacementPhase.Setup: return "setup";
                case PlacementPhase.SpaceChoice: return "space_choice";
                case PlacementPhase.Intro: return "intro";
                case PlacementPhase.Practice: return "practice";
                case PlacementPhase.Baseline: return "baseline";
                case PlacementPhase.PreItems: return "pre_items";
                case PlacementPhase.PreWait: return "pre_wait";
                case PlacementPhase.Condition: return "condition";
                case PlacementPhase.PostItems: return "post_items";
                case PlacementPhase.PostWait: return "post_wait";
                case PlacementPhase.StopDistance: return "stop_distance";
                case PlacementPhase.CheckItems: return "check_items";
                default: return "done";
            }
        }

        static PlacementPhase NextOf(PlacementPhase p) => p == PlacementPhase.Done ? p : (PlacementPhase)((int)p + 1);

        /// <summary>이 세션의 다음 단계. 기본은 enum 순서(NextOf). checkBeforeStopDistance(G59)를 켜면 점검 평정을 사후 평정 바로 뒤로 옮긴다:
        /// post_items → check_items → post_wait → stop_distance → done.</summary>
        PlacementPhase Next(PlacementPhase p)
        {
            if (_cfg.checkBeforeStopDistance)
            {
                if (p == PlacementPhase.PostItems) return PlacementPhase.CheckItems;
                if (p == PlacementPhase.CheckItems) return PlacementPhase.PostWait;
                if (p == PlacementPhase.StopDistance) return PlacementPhase.Done;
            }
            return NextOf(p);
        }

        string Mode => _cfg.EffectiveControlMode;

        // ── 시간·기록 ────────────────────────────────────────────────────
        static long Ms(double seconds) => (long)Math.Round(seconds * 1000.0);
        long NowMs => Ms(_now);
        long CondMs => Ms(_now - _condStart);

        void Event(string ev, string detail) => _writer?.Event(NowMs, ev, detail);

        static string F(double v, string fmt = "0.0000") => v.ToString(fmt, Inv);

        /// <summary>설정 높이 → 실제 높이(G60-3 relative면 + (E − 기준), none이면 그대로). 물체·연습 상자 자리에는 Floored를 거친 값을 쓴다.</summary>
        double Eye(double configuredHeightM) => configuredHeightM + _eyeOffset;

        /// <summary>높이 하한의 바닥 위 여유(m, CP17-3): 물체·연습 상자·안내 판의 아래 끝이 바닥에서 이만큼 위에 남게.</summary>
        public const double FloorClearanceM = 0.05;

        /// <summary>CP17-3: 옮긴 높이 h가 하한 floor(0 이하면 하한 없음)보다 낮으면 floor. 이 세션이 쓰는 자리(used)에서 하한이 걸리면 이름을 남긴다.</summary>
        double Floored(double h, double floor, string name, bool used = true)
        {
            if (floor <= 0 || h >= floor - 1e-9) return h;
            if (used) _heightFloored.Add(name);
            return floor;
        }

        /// <summary>manifest heightFloor(relative이고 앉은 자세이거나 하한이 걸렸을 때만): 하한 규칙, 실제 높이, 하한이 걸린 자리,
        /// 안내 판 중심(러너가 알려 준 값 — 세션 끝에 다시 쓴다).</summary>
        JObject HeightFloorJson(double objFloor, double cubeFloor)
        {
            var j = new JObject
            {
                ["clearanceM"] = FloorClearanceM,
                ["objectRadiusM"] = _info.ObjectBoundingRadiusM is double r && r > 0 ? Math.Round(r, 5) : (double?)null,
                ["objectFloorM"] = objFloor > 0 ? Math.Round(objFloor, 5) : (double?)null,
                ["startHeightM"] = Math.Round(_startH, 5),
                ["stopHeightM"] = Math.Round(_stopH, 5),
            };
            if (_cfg.EffectiveControlMode == PlacementConfig.ModeSystemMove) j["systemMoveTargetHeightM"] = Math.Round(_sysMoveH, 5);
            if (_cfg.HasPractice) { j["practiceFloorM"] = Math.Round(cubeFloor, 5); j["practiceTargetHeightM"] = Math.Round(_pracTargetH, 5); }
            j["applied"] = new JArray(_heightFloored.Cast<object>().ToArray());
            j["panel"] = PanelFloorJson();
            return j;
        }

        /// <summary>heightFloor.panel: 러너가 판을 놓은 적이 없으면(판이 없는 씬·자동 시행 전) null.</summary>
        JToken PanelFloorJson() => _panelReports == 0 ? JValue.CreateNull() : (JToken)new JObject
        {
            ["floorMarginM"] = FloorClearanceM,
            ["baseCenterM"] = Math.Round(_panelBase, 4),
            ["floorApplied"] = _panelFloorApplied,
            ["centerMinM"] = Math.Round(_panelMin, 4),
            ["centerMaxM"] = Math.Round(_panelMax, 4),
        };

        /// <summary>CP17-3: 러너가 안내 판을 놓을 때마다 부른다 — 하한 전 판 중심 높이(설정 높이 + (E − 기준)), 실제 중심 높이, 하한이 걸렸나.
        /// relative일 때만 모은다(manifest heightFloor.panel, 세션 끝에 다시 씀). 하한이 처음 걸리면 events panel_floor 한 줄.</summary>
        public void ReportPanelCenter(double baseCenterM, double centerM, bool floorApplied)
        {
            if (!_cfg.IsEyeRelative || Finished) return;
            _panelReports++;
            _panelBase = baseCenterM;
            _panelMin = Math.Min(_panelMin, centerM);
            _panelMax = Math.Max(_panelMax, centerM);
            if (floorApplied && !_panelFloorApplied)
                Event("panel_floor", $"base_center_m={F(baseCenterM)};center_m={F(centerM)};phase={PhaseLabel}");
            _panelFloorApplied |= floorApplied;
        }

        /// <summary>안내 판 하한이 이 세션에서 한 번이라도 걸렸다(점검용).</summary>
        public bool PanelFloorApplied => _panelFloorApplied;
        /// <summary>물체·연습 상자 높이 하한이 걸린 자리(start | stop | system_move_target | practice_target).</summary>
        public IReadOnlyList<string> HeightFloored => _heightFloored;

        // ── 세션 중 XR 끊김(CP17-1, 2026-11-28) ─────────────────────────
        /// <summary>러너가 매 프레임 부른다(XR 헤드셋이 지금 켜져 있나). XR로 시작한 사람 실행(info.XrMonitored)만 본다 — 데스크톱·자동 시행은 무시.
        /// 켜짐 → 꺼짐이면 events xr_lost, 꺼짐 → 켜짐이면 xr_regained, 그때마다 manifest xrConnection을 다시 쓴다.
        /// 타이머·단계는 건드리지 않는다(측정 절차 그대로 — 멈출지·되돌릴지는 실험자가 중단으로 정한다).</summary>
        public void ReportXrHead(bool active)
        {
            if (!_info.XrMonitored || Finished) return;
            string utc = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", Inv);
            if (!active && !_xrLost)
            {
                _xrLost = true;
                _xrLostCount++;
                _xrLostAt = _now;
                Event("xr_lost", $"count={_xrLostCount};phase={PhaseLabel};utc={utc}");
            }
            else if (active && _xrLost)
            {
                _xrLost = false;
                _xrLostTotal += _now - _xrLostAt;
                Event("xr_regained", $"count={_xrLostCount};phase={PhaseLabel};lost_ms={Ms(_now - _xrLostAt)};utc={utc}");
            }
            else return;
            _info.XrConnection = XrConnectionJson();
            _writer.WriteJson(PlacementRecordWriter.ManifestFile, PlacementManifest.Build(_cfg, _info));
        }

        /// <summary>XR 헤드셋 연결이 지금 끊겨 있다(XR로 시작한 세션에서만 true가 된다).</summary>
        public bool XrLostNow => _xrLost;
        /// <summary>이 세션에서 XR 연결이 끊긴 횟수.</summary>
        public int XrLostCount => _xrLostCount;

        JObject XrConnectionJson() => new JObject
        {
            ["monitored"] = true,
            ["lostCount"] = _xrLostCount,
            ["lostMsTotal"] = Ms(_xrLostTotal + (_xrLost ? _now - _xrLostAt : 0)),
            ["lostNow"] = _xrLost,
        };

        static string Where(PVec3 p) =>
            $"distance_m={F(PlacementGeometry.HorizontalDistance(p))};azimuth_deg={F(PlacementGeometry.AzimuthDeg(p), "0.00")};height_m={F(p.Y)}";

        /// <summary>러너가 남기는 사건(예: recenter — 정면 재설정). 끝난 뒤에는 무시한다.</summary>
        public void Note(string ev, string detail)
        {
            if (Finished || string.IsNullOrEmpty(ev)) return;
            Event(ev, detail ?? "");
        }

        /// <summary>머리 자세 공급원이 바뀌면 events.csv에 head_source로 남긴다.</summary>
        public void SetHeadSource(string source)
        {
            if (Finished || string.IsNullOrEmpty(source) || source == _headSource) return;
            Event("head_source", $"{_headSource}->{source}");
            _headSource = source;
        }

        // ── 단계 ─────────────────────────────────────────────────────────
        void SetPhase(PlacementPhase p)
        {
            Phase = p;
            _phaseStart = _now;
            _clock.Reset();   // 새 단계의 첫 표본은 다음 프레임에 바로
            _pending = null;
            _digits = "";
            _panelHiddenLogged = false;
            _flashing = false;
            _instrPages = null;
            _noticeUntil = double.NegativeInfinity;   // 확정 알림은 단계를 넘지 않는다
            _noticeBackKey = _noticeBackText = null;
            Event("phase", PhaseName(p));
        }

        void ShowText(string key)
        {
            ParticipantTextKey = key;
            ParticipantText = key != null ? _text[key] : null;
        }

        // ── 확인 버튼 안내·확정 알림(연구 책임자 결정 2026-11-28, 문구 파일 0.8) ─────────
        // 확인 버튼을 쓰는 안내(배치 연습·직접 배치·가리켜 지정·반복 멈춤) 끝에 주 사용 손(xrHand)의 버튼 안내를 한 칸 띄워 잇는다.
        // 확인을 받아들이면 확정 알림(confirm_done)을 보인다: 조건 단계는 ConfirmNoticeSeconds 동안 뒤 원래 안내로 돌아가고,
        // 반복 멈춤은 라운드 사이 간격(stopItiSeconds) 동안 보인다(간격·확정 조건·기록 시각은 그대로). 시간 초과에는 보이지 않는다.
        // 파일에 키가 없으면(0.7 이전 파일) 예전처럼 붙이지도 보이지도 않는다.
        /// <summary>조건 단계 확정 알림을 보이는 시간(초).</summary>
        public const double ConfirmNoticeSeconds = 2.0;
        double _noticeUntil = double.NegativeInfinity;
        string _noticeBackKey, _noticeBackText;
        bool _mainStartShown;

        /// <summary>이 세션의 확인 버튼 안내 키(xrHand에 따라).</summary>
        public string ConfirmButtonKey => PlacementTaskText.ConfirmButtonKeyFor(_cfg.xrHand);
        /// <summary>확정 알림이 보이는 중(조건 단계 타이머 또는 반복 멈춤 라운드 사이).</summary>
        public bool ConfirmNoticeActive => ParticipantTextKey != null && ParticipantTextKey.StartsWith(PlacementTaskText.ConfirmDoneKey, StringComparison.Ordinal);
        /// <summary>안내 판 숨기기(hidePanelInDistancePhases)를 잠시 풀어야 하는 알림이 보이는 중(확정 알림·본 측정 시작 안내).</summary>
        bool NoticeOnPanel => ConfirmNoticeActive || ParticipantTextKey == PlacementTaskText.StopMainStartKey;

        void SetTextWithButton(string key, string text)
        {
            string bk = ConfirmButtonKey;
            // 줄을 바꾸지 않고 마지막 문단에 한 칸 띄워 잇는다(줄을 바꾸면 직접 배치 + 범위 안내 판이 6줄이 되어 아래 가장자리가 35°를 넘음, G63 (1))
            if (_text[bk] != null) { key += "+" + bk; text += " " + _text[bk]; }
            ParticipantTextKey = key;
            ParticipantText = text;
        }

        void ShowTextWithButton(string key) => SetTextWithButton(key, _text[key]);

        /// <summary>조건 단계 확정 알림: 지금 안내를 기억해 두고 ConfirmNoticeSeconds 동안 confirm_done을 보인다.</summary>
        void ShowConfirmNotice()
        {
            if (_text[PlacementTaskText.ConfirmDoneKey] == null) return;
            if (_noticeBackKey == null) { _noticeBackKey = ParticipantTextKey; _noticeBackText = ParticipantText; }
            ShowText(PlacementTaskText.ConfirmDoneKey);
            _noticeUntil = _now + ConfirmNoticeSeconds;   // events.csv에는 새 사건을 더하지 않는다(보인 때 = confirm·point_select 사건 시각)
        }

        /// <summary>조건 단계 확정 알림 시간이 지나면 원래 안내로 돌린다.</summary>
        void RestoreNoticeIfDue()
        {
            if (_noticeBackKey == null || _now < _noticeUntil - Eps) return;
            ParticipantTextKey = _noticeBackKey;
            ParticipantText = _noticeBackText;
            _noticeBackKey = _noticeBackText = null;
        }

        void GoTo(PlacementPhase p)
        {
            switch (p)
            {
                case PlacementPhase.SpaceChoice:
                    if (!_cfg.ParticipantChoosesSpace) { GoTo(PlacementPhase.Intro); return; }   // 기본값: 단계 없음(예전과 같은 흐름)
                    EnterSpaceChoice();
                    break;
                case PlacementPhase.Intro:
                    SetPhase(p);
                    _visible = false;
                    ShowText("intro");
                    break;
                case PlacementPhase.Practice:
                    if (!_cfg.HasPractice) { GoTo(PlacementPhase.Baseline); return; }   // 기본값: 연습 없음(G52 전과 같은 흐름)
                    EnterPractice();
                    break;
                case PlacementPhase.Baseline:
                    SetPhase(p);
                    SetObject(StartPosition, false);
                    _visible = true;
                    _state = StateIdle;
                    ShowText("baseline");
                    break;
                case PlacementPhase.PreItems:
                case PlacementPhase.PostItems:
                case PlacementPhase.CheckItems:
                {
                    string when = p == PlacementPhase.PreItems ? PlacementTaskText.WhenPre
                        : p == PlacementPhase.PostItems ? PlacementTaskText.WhenPost : PlacementTaskText.WhenCheck;
                    var items = _text.ItemsFor(when, _cfg.askOptionalItems, _cfg.disabledItems);   // optionalWhen은 설정을 켰을 때만, disabledItems는 뺀다
                    if (items.Count == 0) { GoTo(Next(p)); return; }
                    SetPhase(p);
                    _items = items;
                    _itemsWhen = when;
                    _itemIndex = 0;
                    // 사전 문항은 시작 자리, 사후·점검 문항은 조건 단계가 끝난 자리에 물체를 둔다
                    SetObject(p == PlacementPhase.PreItems ? StartPosition : _conditionFinal, false);
                    _visible = !_cfg.hideObjectDuringItems;   // 설정으로 평정 동안 숨길 수 있다(기본은 보임)
                    _state = StateIdle;
                    var instructionKeys = _text.InstructionKeysFor(when);
                    if (instructionKeys.Count > 0)
                    {
                        // 문구 파일에 평정 지시문이 있으면 첫 문항 앞에 보인다(실험자 Enter로 넘어감)
                        _instruction = true;
                        _pending = null;
                        _digits = "";
                        _cursor = null;
                        ParticipantTextKey = string.Join("+", instructionKeys);
                        ParticipantText = _text.InstructionFor(when);
                        Event("items_instruction", $"when={when};keys={string.Join("+", instructionKeys)}");
                        if (_cfg.uiComfortWrap)
                        {
                            // G63 (1): 판 아래 가장자리가 35° 안에 들게 문장 경계에서 쪽을 나눈다(글자는 그대로, 실험자 Enter로 다음 쪽)
                            var pages = PlacementPanelMetrics.SentencePages(ParticipantText, PlacementPanelMetrics.ComfortWrapChars, InstructionPageMaxLines);
                            if (pages.Count > 1)
                            {
                                _instrPages = pages;
                                _instrPage = 0;
                                ParticipantText = pages[0];
                                Event("items_instruction_page", $"when={when};page=1;pages={pages.Count}");
                            }
                        }
                    }
                    else AskItem();
                    break;
                }
                case PlacementPhase.PreWait:
                case PlacementPhase.PostWait:
                    SetPhase(p);
                    _visible = false;
                    ShowText("wait");
                    break;
                case PlacementPhase.Condition:
                    EnterCondition();
                    break;
                case PlacementPhase.StopDistance:
                    SetPhase(p);
                    _visible = false;
                    _stopStarted = false;
                    _trialActive = false;
                    _stopIndex = -1;
                    _roundActive = false;
                    _roundIndex = -1;
                    ShowText(_cfg.IsStopLoop ? PlacementTaskText.StopLoopKey : "stop_distance");   // 확인 버튼 안내는 멈춘 동안에만(ShowStopLoopText)
                    break;
                case PlacementPhase.Done:
                    Finish(true, null);
                    break;
            }
        }

        void AskItem()
        {
            _instruction = false;
            _instrPages = null;
            var item = _items[_itemIndex];
            ParticipantTextKey = item.Key;
            ParticipantText = PlacementTaskText.ItemDisplay(item);
            _pending = null;
            _digits = "";
            _cursor = null;
            _askedAt = _now;
        }

        // 참여자 컨트롤러 평정(participantRatesWithController). 썸스틱 좌우 = 값 고르기(처음 젖히면 가운데 값에서 시작),
        // 트리거 = 고른 값 확정(바로 기록). 실험자가 이미 숫자를 넣었으면(확정 전) 참여자 확정은 무시하고 실험자 Enter를 기다린다.
        void StepItems(PlacementInputFrame input)
        {
            if (!_cfg.participantRatesWithController) return;
            if (_flashing) return;   // G63 (5): 확정 표시 동안은 다음 문항 전이라 입력을 받지 않는다
            var item = CurrentItem;
            if (item == null) return;
            if (input.RateStep != 0)
            {
                int mid = (item.Min + item.Max) / 2;
                int? before = _cursor;
                _cursor = _cursor == null ? mid : Math.Min(item.Max, Math.Max(item.Min, _cursor.Value + Math.Sign(input.RateStep)));
                if (_cursor != before) Haptic(PlacementHaptics.RateStep);   // G63 (4): 칸이 바뀔 때만(끝에서 더 젖히면 없음)
            }
            if (input.RateSubmitDown && _cursor != null && _pending == null)
            {
                _pending = _cursor.Value;
                _pendingAt = _now;
                Haptic(PlacementHaptics.RateConfirm);
                RecordPending("controller", _cfg.uiRatingConfirmFlash);
            }
        }

        /// <summary>확정 전 평정(_pending)을 ratings.csv에 쓰고 다음 문항(또는 다음 단계)으로 간다.
        /// flash(G63 (5))면 기록은 지금 하고, 확정한 칸을 ConfirmFlashSeconds 동안 굵은 테두리로 보인 뒤 넘어간다
        /// (rt_ms는 확정 순간까지 — 다음 문항의 rt는 그 문항이 보인 때부터라 이 시간이 들어가지 않는다).</summary>
        void RecordPending(string by, bool flash = false)
        {
            var item = CurrentItem;
            int v = _pending.Value;
            long rt = Ms(_pendingAt - _askedAt);
            _writer.Rating(item.Key, _itemsWhen, v, rt);
            Event("rating", $"item={item.Key};when={_itemsWhen};rating={v};rt_ms={rt}" + (by != null ? ";by=" + by : ""));
            if (flash)
            {
                _flashing = true;
                _flashUntil = _now + PlacementPanelMetrics.ConfirmFlashSeconds;
                Event("rating_confirm_flash", $"item={item.Key};when={_itemsWhen};rating={v};duration_ms={Ms(PlacementPanelMetrics.ConfirmFlashSeconds)}");
                return;
            }
            NextItem();
        }

        void NextItem()
        {
            _flashing = false;
            _itemIndex++;
            if (_itemIndex < _items.Count) AskItem();
            else GoTo(Next(Phase));
        }

        // ── 조건 단계 ────────────────────────────────────────────────────
        void EnterCondition()
        {
            SetPhase(PlacementPhase.Condition);
            _condStart = _now;
            _held = false;
            _grabCount = 0;
            _firstGrabMs = null;
            _heldSeconds = 0;
            _pathLength = 0;
            _confirmed = false;
            _confirmMs = null;
            _moving = _moveStarted = false;
            _pointer = null;
            _replayEnded = false;
            _conditionWritten = false;
            _conditionCompleted = false;
            var start = Mode == PlacementConfig.ModeReplay ? ClampSpace(_replay.PositionAt(0)) : StartPosition;
            SetObject(start, false);
            _visible = true;
            _state = StateIdle;
            ShowText(_cfg.IsPlace ? "condition_place" : Mode == PlacementConfig.ModePointSelect ? "condition_point_select" : "condition_view");
            if (_cfg.IsPlace && _cfg.placementAssist)
            {
                // 놓기 도움 (4) 범위 안내 문장(G53): 직접 배치 지시문 뒤에 줄을 바꿔 붙인다
                ParticipantTextKey = "condition_place+" + PlacementTaskText.PlacementRangeKey;
                ParticipantText = _text["condition_place"] + "\n" + _text[PlacementTaskText.PlacementRangeKey];
            }
            // 2026-11-28: 확인 버튼을 쓰는 조건(직접 배치·가리켜 지정)이면 버튼 안내를 맨 아래에(보기만 static·system_move·replay는 확인 버튼이 없다)
            if (_cfg.IsPlace || Mode == PlacementConfig.ModePointSelect) SetTextWithButton(ParticipantTextKey, ParticipantText);
            _trajectory = new PlacementTrajectory
            {
                SourceSessionId = _info.SessionId, SampleHz = _cfg.headSampleHz,
                StartDistanceM = PlacementGeometry.HorizontalDistance(start), StartHeightM = start.Y,
            };
            _trajectory.Add(0, start);
            if (Mode == PlacementConfig.ModeReplay)
            {
                Event("replay_start", $"file={_info.ReplayFile};sourceSessionId={_replay.SourceSessionId};duration_ms={_replay.DurationMs}");
                _state = StateReplay;
            }
        }

        PVec3 ClampSpace(PVec3 p) => PlacementGeometry.ClampToSpace(p, _cfg.floorRadiusM, _cfg.minHeightM, _cfg.maxHeightM);

        void SetObject(PVec3 p, bool countPath)
        {
            if (countPath) _pathLength += PVec3.Distance(_obj, p);
            _obj = p;
        }

        void StepCondition(double dt, PlacementInputFrame input)
        {
            if (_cfg.IsPlace) StepPlace(dt, input);
            else if (Mode == PlacementConfig.ModeSystemMove) StepSystemMove(dt);
            else if (Mode == PlacementConfig.ModePointSelect) StepPointSelect(dt, input);
            else if (Mode == PlacementConfig.ModeReplay) StepReplay();
        }

        void StepPlace(double dt, PlacementInputFrame input)
        {
            if (!_held && input.GrabDown && input.HasRay) TryGrab(input);
            else if (_held && !input.GrabHeld) Release("button");

            if (_held && input.HasRay)
            {
                _hold += input.PushPullAxis * _cfg.pushPullSpeedMps * dt + input.PushPullDeltaM;
                _hold = Math.Min(_cfg.holdMaxM, Math.Max(_cfg.holdMinM, _hold));
                var target = input.RayOrigin + input.RayDirection.Normalized * _hold + _grabOffset;
                SetObject(ClampSpace(target), true);
            }
            _state = _held ? StateHeld : StateIdle;
            if (input.ConfirmDown) ConfirmPlace();
        }

        void TryGrab(PlacementInputFrame input)
        {
            var dir = input.RayDirection.Normalized;
            if (!PlacementGeometry.RaySphere(input.RayOrigin, dir, _obj, GrabRadiusM, out _)) return;
            _held = true;
            _grabCount++;
            _grabStart = _now;
            if (_firstGrabMs == null) _firstGrabMs = CondMs;
            double along = PlacementGeometry.AlongRay(input.RayOrigin, dir, _obj);
            _hold = Math.Min(_cfg.holdMaxM, Math.Max(_cfg.holdMinM, along));
            _grabOffset = _obj - (input.RayOrigin + dir * _hold);   // 잡은 순간 물체가 튀지 않도록
            _state = StateHeld;
            Event("grab", $"count={_grabCount};{Where(_obj)};hold_m={F(_hold)}");
            Haptic(PlacementHaptics.Grab);
        }

        void Release(string reason)
        {
            if (!_held) return;
            _held = false;
            _heldSeconds += _now - _grabStart;
            _state = StateIdle;
            Event("release", $"count={_grabCount};{Where(_obj)};held_ms={Ms(_now - _grabStart)};reason={reason}");
            if (reason == "button") Haptic(PlacementHaptics.Release);   // 참여자가 뗀 때만(확인·단계 끝의 자동 놓기는 확인 펄스 하나)
        }

        void ConfirmPlace()
        {
            if (_held) Release("confirm");
            _confirmed = true;
            _confirmMs = CondMs;
            Event("confirm", $"{Where(_obj)};t_ms={_confirmMs}");
            Haptic(PlacementHaptics.Confirm);
            ShowConfirmNotice();   // 2026-11-28: 확정 알림(약 2초 뒤 원래 안내). 조건 단계 길이·기록은 그대로
            if (_cfg.conditionEndsOnConfirm) EndCondition();
        }

        void StartMove(PVec3 target, string ev, string detail)
        {
            if (_moving) Event("system_move_end", $"{Where(_obj)};interrupted=1");
            _moveTarget = ClampSpace(target);
            _moving = true;
            _moveStarted = true;
            _state = StateSystem;
            Event(ev, detail);
            if (ev != "system_move_start") Event("system_move_start", $"target_{Where(_moveTarget).Replace(";", ";target_")}");
        }

        void StepMove(double dt)
        {
            if (!_moving) return;
            var p = PlacementGeometry.MoveTowards(_obj, _moveTarget, _cfg.systemMoveSpeedMps * dt, out bool arrived);
            SetObject(p, true);
            if (arrived)
            {
                _moving = false;
                _state = StateIdle;
                Event("system_move_end", Where(_obj));
            }
            else _state = StateSystem;
        }

        void StepSystemMove(double dt)
        {
            if (!_moveStarted && SecondsInPhase >= _cfg.systemMoveDelaySeconds - Eps)
            {
                var target = PlacementGeometry.FromPolar(_cfg.systemMoveTargetDistanceM, _cfg.systemMoveTargetAzimuthDeg, _sysMoveH);
                StartMove(target, "system_move_start", $"target_{Where(ClampSpace(target)).Replace(";", ";target_")};speed_mps={F(_cfg.systemMoveSpeedMps)}");
                return;   // 움직임은 다음 프레임부터
            }
            StepMove(dt);
        }

        void StepPointSelect(double dt, PlacementInputFrame input)
        {
            _pointer = null;
            if (input.HasRay && PlacementGeometry.RayFloor(input.RayOrigin, input.RayDirection, 0, out var hit))
                _pointer = PlacementGeometry.ClampToSpace(hit, _cfg.floorRadiusM, 0, 0);
            if (input.ConfirmDown && _pointer.HasValue)
            {
                var pt = _pointer.Value;
                _confirmed = true;
                _confirmMs = CondMs;
                var target = new PVec3(pt.X, _obj.Y, pt.Z);   // 높이는 지금 높이를 지킨다(바닥의 점만 고른다)
                Haptic(PlacementHaptics.Confirm);
                ShowConfirmNotice();   // 2026-11-28: 확정 알림
                StartMove(target, "point_select", $"x={F(pt.X)};z={F(pt.Z)};distance_m={F(PlacementGeometry.HorizontalDistance(pt))};" +
                                                  $"azimuth_deg={F(PlacementGeometry.AzimuthDeg(pt), "0.00")};t_ms={_confirmMs}");
                return;
            }
            StepMove(dt);
        }

        void StepReplay()
        {
            double t = (_now - _condStart) * 1000.0;
            SetObject(ClampSpace(_replay.PositionAt(t)), true);
            if (!_replayEnded && t >= _replay.DurationMs - Eps)
            {
                _replayEnded = true;
                Event("replay_end", $"{Where(_obj)};t_ms={CondMs}");
            }
            _state = _replayEnded ? StateIdle : StateReplay;
        }

        /// <summary>조건 단계를 끝내고 placement.json·trajectory.json을 쓴다. advance면 다음 단계로 간다.
        /// advance = 정해진 끝(conditionSeconds를 다 채움, 또는 conditionEndsOnConfirm을 켠 확인)이라 conditionCompleted = true.
        /// 중단(Abort·Quit)으로 부르면 advance = false라 conditionCompleted = false(조기 종료 — 분석기는 조건 단계 지표를 비운다).</summary>
        void EndCondition(bool advance = true)
        {
            if (_conditionWritten) return;
            _conditionCompleted = advance;
            if (_held) Release("phase_end");
            if (_moving)
            {
                _moving = false;
                Event("system_move_end", $"{Where(_obj)};interrupted=1;reason=phase_end");
            }
            if (Mode == PlacementConfig.ModeReplay && !_replayEnded)
            {
                _replayEnded = true;
                Event("replay_end", $"{Where(_obj)};t_ms={CondMs};reason=phase_end");
            }
            _state = StateIdle;
            long durMs = CondMs;
            if (_trajectory.Samples.Count == 0 || _trajectory.Samples[_trajectory.Samples.Count - 1].TMs < durMs) _trajectory.Add(durMs, _obj);
            _conditionFinal = _obj;
            _writer.WriteJson(PlacementRecordWriter.PlacementFile, BuildPlacementJson(durMs));
            _writer.WriteJson(PlacementRecordWriter.TrajectoryFile, _trajectory.ToJson());
            _conditionWritten = true;
            _pointer = null;
            if (advance) GoTo(PlacementPhase.PostItems);
        }

        JObject BuildPlacementJson(long durMs)
        {
            var p = _obj;
            return new JObject
            {
                ["condition"] = _cfg.condition,
                ["controlMode"] = Mode,
                ["phaseDurationMs"] = durMs,
                ["finalX"] = Math.Round(p.X, 4),
                ["finalY"] = Math.Round(p.Y, 4),
                ["finalZ"] = Math.Round(p.Z, 4),
                ["finalDistanceM"] = Math.Round(PlacementGeometry.HorizontalDistance(p), 4),
                ["finalAzimuthDeg"] = Math.Round(PlacementGeometry.AzimuthDeg(p), 2),
                ["finalHeightM"] = Math.Round(p.Y, 4),
                ["grabCount"] = _grabCount,
                ["firstGrabMs"] = _firstGrabMs,
                ["heldMs"] = Ms(_heldSeconds),
                ["pathLengthM"] = Math.Round(_pathLength, 4),
                ["confirmed"] = _confirmed,
                ["confirmMs"] = _confirmMs,
                ["conditionCompleted"] = _conditionCompleted,
            };
        }

        // ── 공간 고르기(2026-11-28 연구 책임자 결정) ──────────────────────
        void EnterSpaceChoice()
        {
            SetPhase(PlacementPhase.SpaceChoice);
            _visible = false;
            _state = StateIdle;
            _spaceIndex = 0;
            _spaceSeen.Clear();
            _spaceViewSeconds.Clear();
            foreach (var env in _spaceOrder) _spaceViewSeconds[env] = 0;
            _spaceSeen.Add(_spaceOrder[0]);
            _spaceStart = _spaceShownAt = _now;
            _spaceSwitches = _spaceIgnored = 0;
            _spaceDecided = false;
            SpaceChosenBy = null;
            ShowSpaceChoiceText();
            Event("space_choice_start", $"order={string.Join("|", _spaceOrder)};rule={PlacementSpaceChoice.OrderRule};shown={_spaceOrder[0]};before={_spaceBefore}");
        }

        /// <summary>공간 고르기 안내 + 확인 버튼 안내(한 칸 띄워 이음) + 줄을 바꿔 위치 줄("공간 i / n").</summary>
        void ShowSpaceChoiceText()
        {
            string key = PlacementTaskText.SpaceChoiceKey, text = _text[PlacementTaskText.SpaceChoiceKey];
            string bk = ConfirmButtonKey;
            if (_text[bk] != null) { key += "+" + bk; text += " " + _text[bk]; }
            string pos = _text.SpaceChoicePosition(_spaceIndex + 1, _spaceOrder.Length);
            if (pos != null) { key += "+" + PlacementTaskText.SpaceChoicePositionKey; text += "\n" + pos; }
            ParticipantTextKey = key;
            ParticipantText = text;
        }

        void StepSpaceChoice(bool nextPress, bool confirmPress)
        {
            if (_spaceDecided)
            {
                if (_now >= _spaceAdvanceAt - Eps) GoTo(PlacementPhase.Intro);   // 확정 알림이 끝나면 intro
                return;
            }
            if (confirmPress)
            {
                if (SpaceChoiceSeenAll) { Haptic(PlacementHaptics.Confirm); DecideSpace(PlacementSpaceChoice.ByParticipant); return; }
                _spaceIgnored++;
                Event("space_choice_confirm_ignored", $"reason=not_all_seen;seen={_spaceSeen.Count};shown={_spaceOrder[_spaceIndex]}");
            }
            if (nextPress)
            {
                string prev = _spaceOrder[_spaceIndex];
                double viewed = _now - _spaceShownAt;
                _spaceViewSeconds[prev] += viewed;
                _spaceIndex = (_spaceIndex + 1) % _spaceOrder.Length;
                _spaceSwitches++;
                _spaceShownAt = _now;
                _spaceSeen.Add(_spaceOrder[_spaceIndex]);
                ShowSpaceChoiceText();
                Event("space_choice_show", $"env={_spaceOrder[_spaceIndex]};index={_spaceIndex + 1};prev={prev};prev_view_ms={Ms(viewed)};seen={_spaceSeen.Count}");
            }
        }

        /// <summary>지금 보이는 공간으로 정한다(by: participant_confirm | experimenter | abort). abort가 아니면 세션 environment를 바꾸고 확정 알림 뒤 intro.</summary>
        void DecideSpace(string by)
        {
            if (_spaceDecided) return;
            string shown = _spaceOrder[_spaceIndex];
            _spaceViewSeconds[shown] += _now - _spaceShownAt;
            _spaceShownAt = _now;
            _spaceDecided = true;
            SpaceChosenBy = by;
            bool abort = by == PlacementSpaceChoice.ByAbort;
            string chosen = abort ? null : shown;
            if (!abort) _cfg.environment = chosen;
            _info.SpaceChoice = SpaceChoiceJson(chosen, by);
            Event("space_choice_end", $"chosen={chosen ?? ""};by={by};duration_ms={Ms(_now - _spaceStart)};switches={_spaceSwitches};" +
                                      $"seen_all={(SpaceChoiceSeenAll ? 1 : 0)};ignored_confirms={_spaceIgnored};view_ms={ViewMsText()}");
            _writer.WriteJson(PlacementRecordWriter.ManifestFile, PlacementManifest.Build(_cfg, _info));   // 고른 공간으로 manifest를 다시 쓴다
            if (abort) return;
            if (_text[PlacementTaskText.ConfirmDoneKey] != null)
            {
                ShowText(PlacementTaskText.ConfirmDoneKey);
                _spaceAdvanceAt = _now + ConfirmNoticeSeconds;
            }
            else GoTo(PlacementPhase.Intro);
        }

        string ViewMsText() => string.Join("|", _spaceOrder.Select(e => e + ":" + Ms(_spaceViewSeconds[e]).ToString(Inv)));

        /// <summary>manifest environmentChoice(참여자가 고르는 세션만): 순서·고른 값·고른 방식·걸린 시간·공간마다 본 시간.</summary>
        JObject SpaceChoiceJson(string chosen, string by)
        {
            var view = new JObject();
            foreach (var e in _spaceOrder) view[e] = _spaceViewSeconds.TryGetValue(e, out var v) ? Ms(v) : 0;
            return new JObject
            {
                ["mode"] = _cfg.environmentChoice,
                ["orderRule"] = PlacementSpaceChoice.OrderRule,
                ["order"] = new JArray(_spaceOrder.Cast<object>().ToArray()),
                ["environmentBeforeChoice"] = _spaceBefore,
                ["chosen"] = chosen,
                ["chosenBy"] = by,
                ["durationMs"] = by == null ? (long?)null : Ms(_now - _spaceStart),
                ["switches"] = _spaceSwitches,
                ["seenAll"] = SpaceChoiceSeenAll,
                ["ignoredConfirms"] = _spaceIgnored,
                ["viewMs"] = view,
            };
        }

        // ── 배치 연습(G53) ───────────────────────────────────────────────
        // 뜻 없는 회색 상자를 시작 자리(본 물체와 같은 자리)에서 표시된 목표 자리로 옮기고 확인한다. 잡기·밀기/당기기는 직접 배치와 같은 규칙.
        // 참여자 확인 = 연습 끝(목표와의 거리는 기록만 하고 다시 시키지 않음). 실험자 "다음"(Enter)으로 건너뛸 수 있다.
        void EnterPractice()
        {
            SetPhase(PlacementPhase.Practice);
            _visible = false;   // 본 물체는 숨긴다(연습 상자는 러너가 따로 그린다)
            _state = StateIdle;
            _pracPos = StartPosition;
            _pracTarget = PlacementGeometry.FromPolar(_cfg.practiceTargetDistanceM, _cfg.practiceTargetAzimuthDeg, _pracTargetH);
            _pracHeld = false;
            _pracWritten = false;
            _pracGrabCount = 0;
            _pracHeldSeconds = 0;
            _pracStartTime = _now;
            ShowTextWithButton(PlacementTaskText.PracticeKey);   // 2026-11-28: 확인 버튼 안내(연습은 확인하면 바로 끝나 확정 알림은 없다)
            Event("practice_start", $"target_{Where(_pracTarget).Replace(";", ";target_")};start_{Where(_pracPos).Replace(";", ";start_")};cube_m={F(_cfg.practiceCubeSizeM)}");
        }

        void StepPractice(double dt, PlacementInputFrame input)
        {
            if (!_pracHeld && input.GrabDown && input.HasRay)
            {
                var dir = input.RayDirection.Normalized;
                if (PlacementGeometry.RaySphere(input.RayOrigin, dir, _pracPos, PracticeGrabRadiusM, out _))
                {
                    _pracHeld = true;
                    _pracGrabCount++;
                    _pracGrabStart = _now;
                    double along = PlacementGeometry.AlongRay(input.RayOrigin, dir, _pracPos);
                    _pracHold = Math.Min(_cfg.holdMaxM, Math.Max(_cfg.holdMinM, along));
                    _pracGrabOffset = _pracPos - (input.RayOrigin + dir * _pracHold);
                    Event("practice_grab", $"count={_pracGrabCount};{Where(_pracPos)}");
                    Haptic(PlacementHaptics.Grab);
                }
            }
            else if (_pracHeld && !input.GrabHeld) PracticeRelease("button");

            if (_pracHeld && input.HasRay)
            {
                _pracHold += input.PushPullAxis * _cfg.pushPullSpeedMps * dt + input.PushPullDeltaM;
                _pracHold = Math.Min(_cfg.holdMaxM, Math.Max(_cfg.holdMinM, _pracHold));
                _pracPos = ClampSpace(input.RayOrigin + input.RayDirection.Normalized * _pracHold + _pracGrabOffset);
            }
            if (input.ConfirmDown)
            {
                Haptic(PlacementHaptics.Confirm);
                EndPractice("participant_confirm");
            }
        }

        void PracticeRelease(string reason)
        {
            if (!_pracHeld) return;
            _pracHeld = false;
            _pracHeldSeconds += _now - _pracGrabStart;
            Event("practice_release", $"count={_pracGrabCount};{Where(_pracPos)};held_ms={Ms(_now - _pracGrabStart)};reason={reason}");
            if (reason == "button") Haptic(PlacementHaptics.Release);
        }

        /// <summary>연습을 끝내고 practice.json을 쓴다. by: participant_confirm | experimenter | abort. advance면 제시 단계로.</summary>
        void EndPractice(string by, bool advance = true)
        {
            if (_pracWritten) return;
            PracticeRelease("practice_end");
            long dur = Ms(_now - _pracStartTime);
            bool confirmed = by == "participant_confirm";
            Event("practice_end", $"{Where(_pracPos)};error_m={F(PracticeErrorM)};confirmed={(confirmed ? 1 : 0)};by={by};duration_ms={dur}");
            _writer.WriteJson(PlacementRecordWriter.PracticeFile, BuildPracticeJson(by, confirmed, dur));
            _pracWritten = true;
            if (advance) GoTo(PlacementPhase.Baseline);
        }

        JObject BuildPracticeJson(string by, bool confirmed, long durMs)
        {
            var p = _pracPos;
            var t = _pracTarget;
            return new JObject
            {
                ["note"] = "배치 연습(G53) — 뜻 없는 회색 상자. 본 배치 결과(placement.json)가 아니다",
                ["cubeSizeM"] = _cfg.practiceCubeSizeM,
                ["targetDistanceM"] = Math.Round(PlacementGeometry.HorizontalDistance(t), 4),
                ["targetAzimuthDeg"] = Math.Round(PlacementGeometry.AzimuthDeg(t), 2),
                ["targetHeightM"] = Math.Round(t.Y, 4),
                ["finalX"] = Math.Round(p.X, 4),
                ["finalY"] = Math.Round(p.Y, 4),
                ["finalZ"] = Math.Round(p.Z, 4),
                ["finalDistanceM"] = Math.Round(PlacementGeometry.HorizontalDistance(p), 4),
                ["finalAzimuthDeg"] = Math.Round(PlacementGeometry.AzimuthDeg(p), 2),
                ["finalHeightM"] = Math.Round(p.Y, 4),
                ["errorM"] = Math.Round(PracticeErrorM, 4),
                ["grabCount"] = _pracGrabCount,
                ["heldMs"] = Ms(_pracHeldSeconds),
                ["confirmed"] = confirmed,
                ["endedBy"] = by,
                ["durationMs"] = durMs,
            };
        }

        // ── 멈춤 거리 ────────────────────────────────────────────────────
        // 한 프레임의 순서(고정): ① 이번 프레임 이동을 먼저 반영 → ② 버튼 검사 → ③ 기록.
        //   기록 거리 = 이 프레임 이동을 반영한 위치, rt = 이 프레임 시각 − 시행 시작 → 거리 = 시작 거리 ∓ 속도 × rt가 늘 맞는다.
        //   실제 누른 순간은 직전 프레임과 이 프레임 사이 어딘가라 기록 거리의 최대 오차는 stopSpeedMps × dt.
        //   경계(stopMinM·stopMaxM)에 닿는 같은 프레임에 누르면 누름이 이긴다(거리 = 경계값, timed_out = 0).
        //   누름은 stopPress(직전 프레임에 눌려 있지 않던 StopDown)만 센다. 시행을 시작하는 프레임의 누름은 버린다.
        void StepStop(double dt, bool stopPress, bool confirmPress)
        {
            if (!_stopStarted) return;
            if (_cfg.IsStopLoop) { StepStopLoop(dt, stopPress, confirmPress); return; }
            if (!_trialActive)
            {
                if (_now < _itiUntil - Eps) return;
                if (_stopIndex + 1 >= _stopPlan.Count) { GoTo(Next(PlacementPhase.StopDistance)); return; }   // 기본: check_items, checkBeforeStopDistance면 done
                StartTrial(_stopIndex + 1);
                return;
            }
            var plan = _stopPlan[_stopIndex];
            // ① 이동
            double d = _stopD + (plan.IsApproach ? -1 : 1) * _cfg.stopSpeedMps * dt;
            bool atLimit = plan.IsApproach ? d <= _cfg.stopMinM + Eps : d >= _cfg.stopMaxM - Eps;
            if (atLimit) d = plan.IsApproach ? _cfg.stopMinM : _cfg.stopMaxM;
            _stopD = d;
            SetObject(PlacementGeometry.FromPolar(d, 0, _stopH), false);
            long rt = Ms(_now - _trialStart);
            // ② 버튼 → ③ 기록
            if (stopPress)
            {
                _writer.Stop(plan.Trial, plan.Practice, plan.Direction, plan.StartM, _cfg.stopSpeedMps, _stopD, rt, false);
                Event("stop_press", $"trial={plan.Trial};distance_m={F(_stopD)};rt_ms={rt}");
                Haptic(PlacementHaptics.Stop);
                EndTrial();
                return;
            }
            if (atLimit)
            {
                _writer.Stop(plan.Trial, plan.Practice, plan.Direction, plan.StartM, _cfg.stopSpeedMps, null, rt, true);
                Event("stop_timeout", $"trial={plan.Trial};distance_m={F(_stopD)};rt_ms={rt}");
                EndTrial();
            }
        }

        void StartTrial(int index)
        {
            _stopIndex = index;
            var plan = _stopPlan[index];
            _trialActive = true;
            _trialStart = _now;
            _stopD = plan.StartM;
            SetObject(PlacementGeometry.FromPolar(_stopD, 0, _stopH), false);
            _visible = true;
            _state = StateStop;
            _clock.Reset();
            Event("stop_trial_start", $"trial={plan.Trial};practice={(plan.Practice ? 1 : 0)};direction={plan.Direction};" +
                                      $"start_m={F(plan.StartM)};speed_mps={F(_cfg.stopSpeedMps)}");
        }

        void EndTrial()
        {
            _trialActive = false;
            _visible = false;
            _state = StateIdle;
            _itiUntil = _now + _cfg.stopItiSeconds;
        }

        // ── 멈춤 거리 반복 멈춤(G60-2, stopMode loop) ─────────────────────
        // 정면 직선 위 왕복(stopLoopMinM ↔ stopLoopMaxM, stopSpeedMps 일정, 끝에서 감속 없이 반사). 한 프레임의 순서(고정):
        //   ① 움직이는 중이면 이동(끝점을 넘으면 넘은 만큼 되돌아오고 turn 행) → ② 확정(A·X·F) → ③ 토글(트리거·Space) → ④ 시간 상한.
        //   확정은 프레임 시작 때 멈춰 있었을 때만 받는다(움직이는 중이면 confirm_ignored 행만). 같은 프레임에 토글과 확정이 함께 오면
        //   확정을 먼저 본다(멈춘 상태에서 둘을 함께 누르면 그 자리로 확정).
        //   토글은 직전에 받아들인 토글부터 stopLoopToggleDebounceMs 안이면 버린다(toggle_ignored 행). 다시 움직이면 멈추기 전 방향 그대로.
        //   라운드를 시작하는 프레임의 누름은 버린다(single과 같은 규칙). 누름은 '내려가는 순간'만 센다(Tick의 stopPress).
        //   시간 상한(라운드 시작부터 본 라운드 stopLoopRoundSeconds, 연습 라운드 stopLoopPracticeRoundSeconds)에 닿으면 확정값은 빈칸으로 두고 end_reason timeout_stopped | timeout_moving
        //   (원칙 2: 참여자가 확정하지 않은 값을 시스템이 정하지 않는다). 마지막 멈춤 거리는 last_stop_distance_m에 따로 남는다.
        public const string StatePaused = "stop_paused";
        /// <summary>확정값이 끝점에서 이 거리(m) 안이면 at_bound = 1.</summary>
        public const double StopLoopBoundToleranceM = 0.05;

        static string DirName(int dir) => dir < 0 ? PlacementConfig.DirectionApproach : PlacementConfig.DirectionRecede;

        void StepStopLoop(double dt, bool stopPress, bool confirmPress)
        {
            if (!_roundActive)
            {
                if (_now < _itiUntil - Eps) return;
                if (_roundIndex + 1 >= _loopPlan.Count) { GoTo(Next(PlacementPhase.StopDistance)); return; }
                StartRound(_roundIndex + 1);
                return;
            }
            // ① 이동
            if (_loopMoving)
            {
                double d = _stopD + _loopDir * _cfg.stopSpeedMps * dt;
                for (int guard = 0; guard < 64 && (d > _cfg.stopLoopMaxM || d < _cfg.stopLoopMinM); guard++)
                {
                    double bound = d > _cfg.stopLoopMaxM ? _cfg.stopLoopMaxM : _cfg.stopLoopMinM;
                    d = 2 * bound - d;
                    _loopDir = -_loopDir;
                    _loopPoints.Add(bound);
                    Adjust("turn", bound, DirName(_loopDir), false);
                }
                _stopD = Math.Min(_cfg.stopLoopMaxM, Math.Max(_cfg.stopLoopMinM, d));
                SetObject(PlacementGeometry.FromPolar(_stopD, 0, _stopH), false);
            }
            // ② 확정(프레임 시작 때의 상태로 판단)
            if (confirmPress)
            {
                if (!_loopMoving)
                {
                    Adjust("confirm", _stopD, _loopLastStopDir, false);
                    Haptic(PlacementHaptics.Confirm);
                    EndRound(StopLoopEnd.Confirmed);
                    return;
                }
                Adjust("confirm_ignored", _stopD, DirName(_loopDir), false);
            }
            // ③ 토글
            if (stopPress)
            {
                if ((_now - _lastToggle) * 1000.0 < _cfg.stopLoopToggleDebounceMs - Eps)
                    Adjust("toggle_ignored", _stopD, DirName(_loopDir), false);
                else if (_loopMoving)
                {
                    _loopMoving = false;
                    _loopStops.Add(_stopD);
                    _loopPoints.Add(_stopD);
                    _loopLastStopDir = DirName(_loopDir);
                    Adjust("stop", _stopD, _loopLastStopDir, true);
                    Haptic(PlacementHaptics.Stop);
                    _lastToggle = _now;
                    _state = StatePaused;
                    ShowStopLoopText();
                }
                else
                {
                    _loopMoving = true;
                    _loopResumes++;
                    Adjust("resume", _stopD, DirName(_loopDir), true);
                    Haptic(PlacementHaptics.Resume);
                    _lastToggle = _now;
                    _state = StateStop;
                    ShowStopLoopText();
                }
            }
            // ④ 시간 상한
            if (_now - _roundStart >= RoundLimitSeconds(_loopPlan[_roundIndex]) - Eps)
            {
                string reason = _loopMoving ? StopLoopEnd.TimeoutMoving : StopLoopEnd.TimeoutStopped;
                Adjust("timeout", _stopD, _loopMoving ? DirName(_loopDir) : _loopLastStopDir, false);
                EndRound(reason);
            }
        }

        /// <summary>stoprounds.csv end_reason 값.</summary>
        public static class StopLoopEnd
        {
            public const string Confirmed = "confirmed";
            public const string TimeoutStopped = "timeout_stopped";
            public const string TimeoutMoving = "timeout_moving";
            public const string Aborted = "aborted";
        }

        /// <summary>참여자 글: 움직이는 동안은 stop_distance_loop, 멈춘 동안은 그 아래에 줄을 바꿔 stop_loop_hint.</summary>
        void ShowStopLoopText()
        {
            if (_roundActive && !_loopMoving)
                SetTextWithButton(PlacementTaskText.StopLoopKey + "+" + PlacementTaskText.StopLoopHintKey,
                    _text[PlacementTaskText.StopLoopKey] + "\n" + _text[PlacementTaskText.StopLoopHintKey]);
            else ShowText(PlacementTaskText.StopLoopKey);
            // 2026-11-28: 확인 버튼 안내는 확정할 수 있는 때(멈춘 동안)에만 조작 안내 끝에 붙인다. 움직이는 동안·라운드 사이에도 붙이면
            // 지시문 판이 6줄이 되어 아래 가장자리가 35°를 넘고(G63 (1)), 그때는 확인 버튼이 받아들여지지 않는다(G60-2).
        }

        /// <summary>stopadjust.csv 한 줄. changeState면 이 사건이 상태 변화(멈춤·재개)라 rt 기준 시각을 지금으로 옮긴다.</summary>
        void Adjust(string ev, double distance, string dir, bool changeState)
        {
            var plan = _loopPlan[_roundIndex];
            _writer?.StopAdjust(plan.Round, plan.Practice, NowMs, Ms(_now - _roundStart), ev, distance, dir, Ms(_now - _lastChange));
            if (changeState) _lastChange = _now;
        }

        void StartRound(int index)
        {
            _roundIndex = index;
            var plan = _loopPlan[index];
            _roundActive = true;
            _loopMoving = true;
            _loopDir = plan.StartsApproaching ? -1 : 1;
            _stopD = plan.StartM;
            _roundStart = _lastChange = _now;
            _lastToggle = double.NegativeInfinity;
            _loopStops.Clear();
            _loopPoints.Clear();
            _loopPoints.Add(plan.StartM);
            _loopResumes = 0;
            _loopLastStopDir = null;
            SetObject(PlacementGeometry.FromPolar(_stopD, 0, _stopH), false);
            _visible = true;
            _state = StateStop;
            _clock.Reset();
            ShowStopLoopText();
            Event("stop_round_start", $"round={plan.Round};practice={(plan.Practice ? 1 : 0)};start_dir={plan.StartDirection};" +
                                      $"start_m={F(plan.StartM)};speed_mps={F(_cfg.stopSpeedMps)}");
            Adjust("start", _stopD, plan.StartDirection, false);
        }

        /// <summary>확정 전에 물체가 최종 거리를 지나간 횟수: 출발·끝점 반사·멈춤 자리를 이은 구간 가운데 최종 거리를 안쪽에(끝점 제외) 품은 구간 수.</summary>
        static int PassesThrough(List<double> points, double final)
        {
            int n = 0;
            for (int i = 0; i + 1 < points.Count; i++)
            {
                double lo = Math.Min(points[i], points[i + 1]), hi = Math.Max(points[i], points[i + 1]);
                if (final > lo + 1e-6 && final < hi - 1e-6) n++;
            }
            return n;
        }

        void EndRound(string reason)
        {
            var plan = _loopPlan[_roundIndex];
            bool confirmed = reason == StopLoopEnd.Confirmed;
            double? final = confirmed ? _stopD : (double?)null;
            var r = new StopRoundResult
            {
                Round = plan.Round, Practice = plan.Practice, StartDirection = plan.StartDirection, StartM = plan.StartM, SpeedMps = _cfg.stopSpeedMps,
                FinalM = final,
                FirstStopM = _loopStops.Count > 0 ? _loopStops[0] : (double?)null,
                LastStopM = _loopStops.Count > 0 ? _loopStops[_loopStops.Count - 1] : (double?)null,
                NStops = _loopStops.Count, NResumes = _loopResumes,
                FinalMotionDir = _loopLastStopDir,
                PassesBeforeConfirm = confirmed ? PassesThrough(_loopPoints, _stopD) : (int?)null,
                StopSpreadM = _loopStops.Count > 0 ? _loopStops.Max() - _loopStops.Min() : (double?)null,
                AtBound = confirmed ? (_stopD - _cfg.stopLoopMinM <= StopLoopBoundToleranceM + 1e-9 || _cfg.stopLoopMaxM - _stopD <= StopLoopBoundToleranceM + 1e-9) : (bool?)null,
                EndReason = reason,
                DurationMs = Ms(_now - _roundStart),
                EyeObjectDistanceM = confirmed ? PVec3.Distance(_head.Position, _obj) : (double?)null,
            };
            _writer?.StopRound(r);
            Event("stop_round_end", $"round={plan.Round};end_reason={reason};final_m={(final.HasValue ? F(final.Value) : "")};" +
                                    $"n_stops={r.NStops};duration_ms={r.DurationMs}");
            _roundActive = false;
            _loopMoving = false;
            _visible = false;
            _state = StateIdle;
            _itiUntil = _now + _cfg.stopItiSeconds;
            if (reason == StopLoopEnd.Aborted) ShowText(PlacementTaskText.StopLoopKey);   // 중단: 알림 없음
            else ShowStopRoundGapText(plan, confirmed);
        }

        /// <summary>라운드 사이 간격(stopItiSeconds)의 안내(2026-11-28 연구 책임자 결정). 확정했으면 confirm_done, 연습 뒤 첫 본 라운드 전이면
        /// stop_main_start(한 번만, 확정했으면 confirm_done 아래에), 둘 다 아니면(시간 초과·중간 본 라운드) 예전처럼 지시문.
        /// 간격의 길이·다음 라운드 시작 시각은 바꾸지 않는다 — 다음 라운드가 시작되면 지시문으로 돌아간다(StartRound).</summary>
        void ShowStopRoundGapText(StopRoundPlan plan, bool confirmed)
        {
            bool done = confirmed && _text[PlacementTaskText.ConfirmDoneKey] != null;
            bool mainNext = plan.Practice && _roundIndex + 1 < _loopPlan.Count && !_loopPlan[_roundIndex + 1].Practice;
            bool start = mainNext && !_mainStartShown && _text[PlacementTaskText.StopMainStartKey] != null;
            if (start) _mainStartShown = true;
            if (done && start)
            {
                ParticipantTextKey = PlacementTaskText.ConfirmDoneKey + "+" + PlacementTaskText.StopMainStartKey;
                ParticipantText = _text[PlacementTaskText.ConfirmDoneKey] + "\n" + _text[PlacementTaskText.StopMainStartKey];
            }
            else if (done) ShowText(PlacementTaskText.ConfirmDoneKey);
            else if (start) ShowText(PlacementTaskText.StopMainStartKey);
            else ShowText(PlacementTaskText.StopLoopKey);
            // events.csv에는 새 사건을 더하지 않는다(보인 때 = stop_round_end 시각, 길이 = stopItiSeconds)
        }

        // ── 실험자 입력 ──────────────────────────────────────────────────
        bool InItems => Phase == PlacementPhase.PreItems || Phase == PlacementPhase.PostItems || Phase == PlacementPhase.CheckItems;

        /// <summary>실험자 숫자 키(0–9). 문항 범위가 한 자리(max ≤ 9)면 예전처럼 한 번에 입력(범위 밖 무시, 이미 입력됐으면 Backspace 뒤 다시).
        /// 두 자리 이상이면 이어 붙인다: 붙인 값이 max를 넘거나 자릿수가 max보다 길면 그 숫자는 받지 않고, 0 뒤에는 붙이지 않는다.
        /// 붙인 값이 min 이상이면 확정 대기(PendingRating), 아니면 아직 입력 중.</summary>
        public void PressDigit(int d)
        {
            if (Finished || !InItems || _flashing) return;   // G63 (5): 확정 표시 중인 문항은 이미 기록됨
            var item = CurrentItem;
            if (item == null || d < 0 || d > 9) return;
            if (item.Max <= 9)
            {
                if (d < item.Min || d > item.Max) return;
                if (_pending != null) return;   // 이미 입력됨 — Backspace로 취소한 뒤 다시
                _pending = d;
                _pendingAt = _now;
                return;
            }
            if (_digits == "0") return;   // "0" 뒤에 숫자를 붙이지 않는다(05 같은 입력 방지)
            string next = _digits + d.ToString(Inv);
            if (next.Length > item.Max.ToString(Inv).Length) return;
            int v = int.Parse(next, Inv);
            if (v > item.Max) return;   // 범위를 넘는 숫자는 받지 않는다(예: 0–10에서 1 다음 1)
            _digits = next;
            _pending = v >= item.Min ? v : (int?)null;
            _pendingAt = _now;
        }

        /// <summary>여러 자리 범위에서 실험자가 지금까지 친 숫자(확정 전). 없으면 빈 문자열.</summary>
        public string PendingDigits => _digits;

        public void PressBackspace()
        {
            if (Finished || !InItems || _flashing) return;
            if (_pending == null)
            {
                _digits = "";   // 범위에 아직 닿지 않은 입력은 기록 없이 지운다
                return;
            }
            var item = CurrentItem;
            Event("rating_cancel", $"item={item.Key};when={_itemsWhen};rating={_pending.Value}");
            _pending = null;
            _digits = "";
            _askedAt = _now;   // 다시 묻는 시각부터 rt를 잰다
        }

        /// <summary>실험자 확인(Enter): 안내 넘기기, 평정 확정, 대기 단계 넘기기, 멈춤 거리 시작.</summary>
        public void PressConfirm()
        {
            if (Finished) return;
            switch (Phase)
            {
                case PlacementPhase.SpaceChoice:
                    if (!_spaceDecided) DecideSpace(PlacementSpaceChoice.ByExperimenter);   // 참여자가 말로 고른 때 등: 지금 보이는 공간으로
                    else GoTo(PlacementPhase.Intro);   // 확정 알림을 건너뜀
                    break;
                case PlacementPhase.Intro:
                    GoTo(PlacementPhase.Practice);   // 연습이 없으면(기본값) 곧바로 baseline
                    break;
                case PlacementPhase.Practice:
                    EndPractice("experimenter");   // 실험자가 연습을 건너뜀(또는 참여자가 말로 끝냄)
                    break;
                case PlacementPhase.PreWait:
                case PlacementPhase.PostWait:
                    GoTo(Next(Phase));
                    break;
                case PlacementPhase.StopDistance:
                    if (!_stopStarted)
                    {
                        _stopStarted = true;
                        _itiUntil = _now + _cfg.stopItiSeconds;
                    }
                    break;
                case PlacementPhase.PreItems:
                case PlacementPhase.PostItems:
                case PlacementPhase.CheckItems:
                    if (_instruction)
                    {
                        if (_instrPages != null && _instrPage + 1 < _instrPages.Count)
                        {
                            // G63 (1): 나눈 지시문의 다음 쪽
                            _instrPage++;
                            ParticipantText = _instrPages[_instrPage];
                            Event("items_instruction_page", $"when={_itemsWhen};page={_instrPage + 1};pages={_instrPages.Count}");
                            return;
                        }
                        AskItem();   // 지시문 → 첫 문항(rt는 문항이 보인 때부터)
                        return;
                    }
                    if (_flashing) return;   // G63 (5): 확정 표시 중(이미 기록됨)
                    if (_pending == null) return;
                    RecordPending(null);   // 실험자 입력: events.csv rating 상세는 예전 형식 그대로
                    break;
            }
        }

        /// <summary>실험자 화면의 "다음" 단추(안내·대기·멈춤 거리 시작). 평정 단계에서는 확정과 같다.</summary>
        public void PressNext() => PressConfirm();

        public void Abort() => Finish(false, PhaseLabel);

        /// <summary>재생 중지·앱 종료: 그때까지 자료를 남기고 중단으로 기록한다.</summary>
        public void Quit(string why)
        {
            if (Finished) return;
            Event("quit", why);
            Finish(false, PhaseLabel);
        }

        // ── 한 프레임 ────────────────────────────────────────────────────
        /// <summary>한 프레임: 시계 → 단계 진행(참여자 입력) → 표본 기록.</summary>
        public void Tick(double dt, PlacementInputFrame input, HeadPose head)
        {
            if (Finished) return;
            _now += Math.Max(0, dt);
            _head = head;
            RestoreNoticeIfDue();   // 2026-11-28: 조건 단계 확정 알림이 끝나면 원래 안내로
            bool stopPress = input.StopDown && !_stopPrevHeld;   // 내려가는 순간만(미리 누르고 있던 버튼은 떼었다 다시 눌러야 함)
            _stopPrevHeld = input.StopHeld || input.StopDown;
            if (_flashing && InItems && _now >= _flashUntil - Eps) NextItem();   // G63 (5): 확정 표시가 끝나면 다음 문항
            if (InItems) StepItems(input);
            switch (Phase)
            {
                case PlacementPhase.SpaceChoice:
                    StepSpaceChoice(stopPress, input.ConfirmDown);   // 방아쇠(데스크톱 Space) = 다음 공간, 확인 버튼 = 정하기
                    break;
                case PlacementPhase.Practice:
                    StepPractice(dt, input);
                    break;
                case PlacementPhase.Baseline:
                    if (SecondsInPhase >= _cfg.baselineSeconds - Eps) GoTo(PlacementPhase.PreItems);
                    break;
                case PlacementPhase.Condition:
                    if (SecondsInPhase >= _cfg.conditionSeconds - Eps) EndCondition();
                    else StepCondition(dt, input);
                    break;
                case PlacementPhase.StopDistance:
                    StepStop(dt, stopPress, input.ConfirmDown);   // 확정(ConfirmDown)은 loop에서만 쓴다(G60-2)
                    break;
            }
            if (!_panelHiddenLogged && PanelHidden)
            {
                // G63 (7): 읽을 시간이 지나 안내 판을 숨김(한 단계에 한 번)
                _panelHiddenLogged = true;
                Event("panel_hidden", $"phase={PhaseLabel};after_ms={Ms(SecondsInPhase)}");
            }
            Sample();
        }

        // 프레임당 최대 한 표본, 시각은 지금. 물체가 보이면 objpose와 (조건 단계면) 궤적도 같은 주기로.
        void Sample()
        {
            if (Finished || Phase == PlacementPhase.Done || Phase == PlacementPhase.Setup) return;
            if (!_clock.TryTake(_now)) return;
            string phase = PhaseLabel;
            _writer.Head(NowMs, phase, _head, _visible ? _obj : (PVec3?)null);
            if (!_visible) return;
            _writer.Obj(NowMs, phase, _obj, _state);
            if (Phase == PlacementPhase.Condition && !_conditionWritten)
            {
                long t = CondMs;
                if (_trajectory.Samples.Count == 0 || _trajectory.Samples[_trajectory.Samples.Count - 1].TMs < t) _trajectory.Add(t, _obj);
            }
        }

        // ── 끝 ───────────────────────────────────────────────────────────
        void Finish(bool completed, string abortedAt)
        {
            if (Finished) return;
            if (Phase == PlacementPhase.Condition && !_conditionWritten) EndCondition(advance: false);   // 중단해도 조건 단계 자료는 남긴다
            if (Phase == PlacementPhase.Practice && !_pracWritten) EndPractice("abort", advance: false);   // 연습 중 중단도 practice.json에 남긴다
            if (Phase == PlacementPhase.SpaceChoice && !_spaceDecided) DecideSpace(PlacementSpaceChoice.ByAbort);   // 고르기 전 중단: chosen null로 manifest에
            if (Phase == PlacementPhase.StopDistance && _cfg.IsStopLoop && _roundActive)   // 라운드 중 중단도 stoprounds.csv에 남긴다(확정값 빈칸)
            {
                Adjust("abort", _stopD, _loopMoving ? DirName(_loopDir) : _loopLastStopDir, false);
                EndRound(StopLoopEnd.Aborted);
            }
            if (!completed) Event("abort", abortedAt);   // 확정 전 평정(_pending)은 ratings.csv에 쓰지 않는다
            Phase = PlacementPhase.Done;
            _phaseStart = _now;
            Event("phase", "done");
            _visible = false;
            ShowText("done");
            // CP17-1·3: XR 끊김 수(끝날 때 끊겨 있었으면 그 시간까지)와 안내 판 중심(러너가 알려 준 값)을 manifest에 다시 쓴다. 둘 다 없으면 쓰지 않는다
            bool rewrite = false;
            if (_info.XrMonitored) { _info.XrConnection = XrConnectionJson(); rewrite = true; }
            if (_cfg.IsEyeRelative && _panelReports > 0 && (_info.HeightFloor != null || _panelFloorApplied)) { _info.HeightFloor = HeightFloorJson(_objFloor, _cubeFloor); rewrite = true; }
            if (rewrite) _writer.WriteJson(PlacementRecordWriter.ManifestFile, PlacementManifest.Build(_cfg, _info));
            _writer.WriteJson(PlacementRecordWriter.SummaryFile, PlacementRecordWriter.BuildSummary(completed, abortedAt, DateTime.UtcNow));
            _writer.Dispose();
            _writer = null;
            Completed = completed;
            AbortedAt = completed ? null : abortedAt;
        }

        public void Dispose()
        {
            if (!Finished) Quit("disposed");
        }
    }
}
