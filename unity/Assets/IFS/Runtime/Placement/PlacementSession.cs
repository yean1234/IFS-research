// 배치 실험(RQ V4) 한 회기의 단계 흐름과 기록(UnityEngine 없이 — dotnet 테스트에서도 끝까지 돈다).
//   intro → baseline → pre_items → pre_wait → condition → post_items → post_wait → stop_distance → check_items → done
//   (setup은 러너가 세션을 만들기 전 단계라 기록에 없다. *_items는 해당 when 문항이 없으면 건너뛴다.)
// 시계: Tick(dt)으로 받은 dt를 더한 시각(사람 실행은 Time.unscaledDeltaTime, 자동 시행은 고정 dt).
// 물체 위치·보이기·참여자 글은 이 클래스가 정하고, Unity 러너(PlacementRunner)는 그대로 그린다.
// 기록 형식: 계약 ifs-placement/0.1(PlacementRecordWriter).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using IFS.SceneSpec.Ownership;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    public enum PlacementPhase { Setup, Intro, Baseline, PreItems, PreWait, Condition, PostItems, PostWait, StopDistance, CheckItems, Done }

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
        double _askedAt, _pendingAt;

        // 멈춤 거리
        List<StopTrialPlan> _stopPlan;
        int _stopIndex = -1;
        bool _stopStarted, _trialActive;
        double _itiUntil, _trialStart, _stopD;
        bool _stopPrevHeld;   // 직전 프레임에 멈춤 버튼이 눌려 있었나(눌림의 '내려가는 순간'만 인정하려고)

        public PlacementSession(PlacementConfig cfg, PlacementTaskText text, PlacementSessionInfo info, string recordRoot,
            PlacementTrajectory replay = null, IEnumerable<string> warnings = null)
        {
            if (cfg == null) throw new ArgumentNullException(nameof(cfg));
            var errors = cfg.Validate();
            if (errors.Count > 0) throw new ArgumentException("설정 오류: " + string.Join("; ", errors));
            _cfg = cfg.Clone();
            _text = text ?? throw new ArgumentNullException(nameof(text));
            _info = info ?? new PlacementSessionInfo();
            if (_cfg.EffectiveControlMode == PlacementConfig.ModeReplay && (replay == null || replay.Samples.Count == 0))
                throw new ArgumentException("controlMode replay에는 재생할 궤적이 필요합니다");
            _replay = replay;
            _clock = new HeadSampleClock(_cfg.headSampleHz);
            _headSource = _info.HeadSource;
            GrabRadiusM = _cfg.grabRadiusMinM;
            StartPosition = PlacementGeometry.FromPolar(_cfg.startDistanceM, 0, _cfg.startHeightM);
            _obj = StartPosition;
            _conditionFinal = StartPosition;
            _stopPlan = StopDistanceSchedule.Build(_cfg, _info.ParticipantNumber);

            _writer = new PlacementRecordWriter(recordRoot, _info.ParticipantNumber, _info.SessionId, _info.StartedUtc);
            RecordDirectory = _writer.Directory;
            try
            {
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
            foreach (var w in warnings ?? Enumerable.Empty<string>()) Event("warning", w);
            GoTo(PlacementPhase.Intro);
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
            && _items != null && _itemIndex < _items.Count ? _items[_itemIndex] : null;
        public string CurrentItemWhen => _itemsWhen;
        public int? PendingRating => _pending;
        public bool StopTrialsStarted => _stopStarted;
        public bool StopTrialActive => _trialActive;
        public StopTrialPlan CurrentStopTrial => _stopIndex >= 0 && _stopIndex < _stopPlan.Count ? _stopPlan[_stopIndex] : null;
        public IReadOnlyList<StopTrialPlan> StopPlan => _stopPlan;
        public double StopDistanceNow => _stopD;
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
                case PlacementPhase.Intro: return "intro";
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

        string Mode => _cfg.EffectiveControlMode;

        // ── 시간·기록 ────────────────────────────────────────────────────
        static long Ms(double seconds) => (long)Math.Round(seconds * 1000.0);
        long NowMs => Ms(_now);
        long CondMs => Ms(_now - _condStart);

        void Event(string ev, string detail) => _writer?.Event(NowMs, ev, detail);

        static string F(double v, string fmt = "0.0000") => v.ToString(fmt, Inv);

        static string Where(PVec3 p) =>
            $"distance_m={F(PlacementGeometry.HorizontalDistance(p))};azimuth_deg={F(PlacementGeometry.AzimuthDeg(p), "0.00")};height_m={F(p.Y)}";

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
            Event("phase", PhaseName(p));
        }

        void ShowText(string key)
        {
            ParticipantTextKey = key;
            ParticipantText = key != null ? _text[key] : null;
        }

        void GoTo(PlacementPhase p)
        {
            switch (p)
            {
                case PlacementPhase.Intro:
                    SetPhase(p);
                    _visible = false;
                    ShowText("intro");
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
                    var items = _text.ItemsFor(when);
                    if (items.Count == 0) { GoTo(NextOf(p)); return; }
                    SetPhase(p);
                    _items = items;
                    _itemsWhen = when;
                    _itemIndex = 0;
                    // 사전 문항은 시작 자리, 사후·점검 문항은 조건 단계가 끝난 자리에 물체를 둔다
                    SetObject(p == PlacementPhase.PreItems ? StartPosition : _conditionFinal, false);
                    _visible = true;
                    _state = StateIdle;
                    AskItem();
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
                    ShowText("stop_distance");
                    break;
                case PlacementPhase.Done:
                    Finish(true, null);
                    break;
            }
        }

        void AskItem()
        {
            var item = _items[_itemIndex];
            ParticipantTextKey = item.Key;
            ParticipantText = PlacementTaskText.ItemDisplay(item);
            _pending = null;
            _askedAt = _now;
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
        }

        void Release(string reason)
        {
            if (!_held) return;
            _held = false;
            _heldSeconds += _now - _grabStart;
            _state = StateIdle;
            Event("release", $"count={_grabCount};{Where(_obj)};held_ms={Ms(_now - _grabStart)};reason={reason}");
        }

        void ConfirmPlace()
        {
            if (_held) Release("confirm");
            _confirmed = true;
            _confirmMs = CondMs;
            Event("confirm", $"{Where(_obj)};t_ms={_confirmMs}");
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
                var target = PlacementGeometry.FromPolar(_cfg.systemMoveTargetDistanceM, _cfg.systemMoveTargetAzimuthDeg, _cfg.systemMoveTargetHeightM);
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

        // ── 멈춤 거리 ────────────────────────────────────────────────────
        // 한 프레임의 순서(고정): ① 이번 프레임 이동을 먼저 반영 → ② 버튼 검사 → ③ 기록.
        //   기록 거리 = 이 프레임 이동을 반영한 위치, rt = 이 프레임 시각 − 시행 시작 → 거리 = 시작 거리 ∓ 속도 × rt가 늘 맞는다.
        //   실제 누른 순간은 직전 프레임과 이 프레임 사이 어딘가라 기록 거리의 최대 오차는 stopSpeedMps × dt.
        //   경계(stopMinM·stopMaxM)에 닿는 같은 프레임에 누르면 누름이 이긴다(거리 = 경계값, timed_out = 0).
        //   누름은 stopPress(직전 프레임에 눌려 있지 않던 StopDown)만 센다. 시행을 시작하는 프레임의 누름은 버린다.
        void StepStop(double dt, bool stopPress)
        {
            if (!_stopStarted) return;
            if (!_trialActive)
            {
                if (_now < _itiUntil - Eps) return;
                if (_stopIndex + 1 >= _stopPlan.Count) { GoTo(PlacementPhase.CheckItems); return; }
                StartTrial(_stopIndex + 1);
                return;
            }
            var plan = _stopPlan[_stopIndex];
            // ① 이동
            double d = _stopD + (plan.IsApproach ? -1 : 1) * _cfg.stopSpeedMps * dt;
            bool atLimit = plan.IsApproach ? d <= _cfg.stopMinM + Eps : d >= _cfg.stopMaxM - Eps;
            if (atLimit) d = plan.IsApproach ? _cfg.stopMinM : _cfg.stopMaxM;
            _stopD = d;
            SetObject(PlacementGeometry.FromPolar(d, 0, _cfg.stopHeightM), false);
            long rt = Ms(_now - _trialStart);
            // ② 버튼 → ③ 기록
            if (stopPress)
            {
                _writer.Stop(plan.Trial, plan.Practice, plan.Direction, plan.StartM, _cfg.stopSpeedMps, _stopD, rt, false);
                Event("stop_press", $"trial={plan.Trial};distance_m={F(_stopD)};rt_ms={rt}");
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
            SetObject(PlacementGeometry.FromPolar(_stopD, 0, _cfg.stopHeightM), false);
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

        // ── 실험자 입력 ──────────────────────────────────────────────────
        bool InItems => Phase == PlacementPhase.PreItems || Phase == PlacementPhase.PostItems || Phase == PlacementPhase.CheckItems;

        public void PressDigit(int d)
        {
            if (Finished || !InItems) return;
            var item = CurrentItem;
            if (item == null || d < item.Min || d > item.Max) return;
            if (_pending != null) return;   // 이미 입력됨 — Backspace로 취소한 뒤 다시
            _pending = d;
            _pendingAt = _now;
        }

        public void PressBackspace()
        {
            if (Finished || !InItems || _pending == null) return;
            var item = CurrentItem;
            Event("rating_cancel", $"item={item.Key};when={_itemsWhen};rating={_pending.Value}");
            _pending = null;
            _askedAt = _now;   // 다시 묻는 시각부터 rt를 잰다
        }

        /// <summary>실험자 확인(Enter): 안내 넘기기, 평정 확정, 대기 단계 넘기기, 멈춤 거리 시작.</summary>
        public void PressConfirm()
        {
            if (Finished) return;
            switch (Phase)
            {
                case PlacementPhase.Intro:
                    GoTo(PlacementPhase.Baseline);
                    break;
                case PlacementPhase.PreWait:
                case PlacementPhase.PostWait:
                    GoTo(NextOf(Phase));
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
                    if (_pending == null) return;
                    {
                        var item = CurrentItem;
                        int v = _pending.Value;
                        long rt = Ms(_pendingAt - _askedAt);
                        _writer.Rating(item.Key, _itemsWhen, v, rt);
                        Event("rating", $"item={item.Key};when={_itemsWhen};rating={v};rt_ms={rt}");
                        _itemIndex++;
                        if (_itemIndex < _items.Count) AskItem();
                        else GoTo(NextOf(Phase));
                    }
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
            bool stopPress = input.StopDown && !_stopPrevHeld;   // 내려가는 순간만(미리 누르고 있던 버튼은 떼었다 다시 눌러야 함)
            _stopPrevHeld = input.StopHeld || input.StopDown;
            switch (Phase)
            {
                case PlacementPhase.Baseline:
                    if (SecondsInPhase >= _cfg.baselineSeconds - Eps) GoTo(PlacementPhase.PreItems);
                    break;
                case PlacementPhase.Condition:
                    if (SecondsInPhase >= _cfg.conditionSeconds - Eps) EndCondition();
                    else StepCondition(dt, input);
                    break;
                case PlacementPhase.StopDistance:
                    StepStop(dt, stopPress);
                    break;
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
            if (!completed) Event("abort", abortedAt);   // 확정 전 평정(_pending)은 ratings.csv에 쓰지 않는다
            Phase = PlacementPhase.Done;
            _phaseStart = _now;
            Event("phase", "done");
            _visible = false;
            ShowText("done");
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
