// 배치 실험 자동 시행(검증용, 합성 입력 — 참여자 자료 아님). 시뮬레이션 시계로 사람 없이 intro → done을 한 바퀴 돈다.
//   참여자 입력(Participant): 잡기–옮기기–놓기 두 번(다시 잡기 포함), 확인, 가리켜 지정, 멈춤 거리 버튼 시점(한 시행은 일부러 누르지 않아 timed_out).
//   놓기 도움(G53)을 켠 직접 배치면 그 앞 배치 연습: 회색 상자를 목표 자리로 옮기고 확인.
//   실험자 입력(Experimenter): 안내·대기 넘기기, 평정 숫자(첫 평정은 잘못 누른 뒤 Backspace로 취소), Enter 확정.
// 회기마다 새 인스턴스를 쓴다(내부 진행 상태가 있다). UnityEngine에 의존하지 않는다.
using System;

namespace IFS.SceneSpec.Placement
{
    /// <summary>조건 단계 시작 AtSeconds부터 DurationSeconds 동안 물체를 (거리, 방위, 높이)로 옮기고 놓는다.</summary>
    public sealed class PlacementAutoMove
    {
        public double AtSeconds, DurationSeconds, DistanceM, AzimuthDeg, HeightM;
        public PlacementAutoMove() { }
        public PlacementAutoMove(double at, double duration, double distance, double azimuth, double height)
        {
            AtSeconds = at; DurationSeconds = duration; DistanceM = distance; AzimuthDeg = azimuth; HeightM = height;
        }
    }

    public sealed class PlacementAutoScript
    {
        public double KeyDelaySeconds = 0.3;
        public int[] Ratings = { 5, 3, 4, 2, 6, 4 };
        /// <summary>첫 평정에서 MistakeRating을 먼저 누르고 Backspace로 취소한다.</summary>
        public bool CancelFirstRating = true;
        public int MistakeRating = 7;
        /// <summary>광선 원점(손 자리). 데스크톱에서는 카메라, XR에서는 컨트롤러에 해당.</summary>
        public PVec3 HandOrigin = new PVec3(0.0, 1.2, 0.0);
        public PlacementAutoMove[] Moves =
        {
            new PlacementAutoMove(1.0, 3.0, 2.2, -30, 1.0),
            new PlacementAutoMove(6.0, 2.0, 2.6, -20, 0.9),   // 다시 잡기
        };
        /// <summary>조건 단계 시작부터 이 시각에 확인을 누른다. 음수면 누르지 않는다.</summary>
        public double ConfirmAtSeconds = 10.0;
        public double PointAtSeconds = 2.0, PointDistanceM = 2.4, PointAzimuthDeg = 25;
        /// <summary>방향별 시행(연습 포함 순서)마다 버튼을 누를 거리(m). NaN = 누르지 않음(timed_out).</summary>
        public double[] ApproachStopM = { 1.40, 1.25, 1.30, double.NaN, 1.20 };
        public double[] RecedeStopM = { 1.60, 1.75, 1.70, 1.65, 1.80 };
        /// <summary>배치 연습(G53, 놓기 도움): 연습 단계 시작부터 이 시각에 상자를 잡아 PracticeMoveSeconds 동안 목표 자리로 옮기고,
        /// PracticeConfirmAtSeconds에 확인을 누른다. 음수면 누르지 않는다(실험자가 넘겨야 끝남).</summary>
        public double PracticeGrabAtSeconds = 0.5, PracticeMoveSeconds = 2.0, PracticeConfirmAtSeconds = 3.0;

        /// <summary>멈춤 거리 반복 멈춤(G60-2, stopMode loop): 라운드(연습 포함 순서, 넘치면 처음부터 다시)마다 차례로 멈출 거리(m).
        /// 물체가 그 거리를 지나는 프레임에 트리거를 누르고, 다음 거리가 남았으면 LoopDwellSeconds 뒤 다시 눌러 움직인다.
        /// 마지막 멈춤 뒤 LoopConfirm이 true면 LoopDwellSeconds 뒤 확정, false면 확정하지 않는다(timeout_stopped).
        /// 빈 배열 = 한 번도 누르지 않음(timeout_moving).</summary>
        public double[][] LoopStops =
        {
            new[] { 1.50 },               // 연습: 한 번 멈추고 확정
            new[] { 1.80, 1.60 },         // 멈춤 → 다시 움직임 → 멈춤 → 확정
            new[] { 1.70 },
            new double[0],                // 한 번도 누르지 않음(상한 도달, 확정값 빈칸)
            new[] { 1.50, 1.30, 1.45 },   // 두 번 고침
        };
        public bool[] LoopConfirm = { true, true, true, false, true };
        /// <summary>멈춘 뒤(또는 다시 누르기 전) 머무는 시간(초). 디바운스(250 ms)보다 길다.</summary>
        public double LoopDwellSeconds = 0.6;
        /// <summary>이 라운드 번호(1부터)에서는 처음 움직이는 동안 확정을 한 번 눌러 본다(무시되어야 함 — confirm_ignored). 0이면 하지 않음.</summary>
        public int LoopConfirmWhileMovingRound = 2;

        // 진행 상태
        int _ratingCount;
        bool _cancelled;
        double _nextKey;
        int _grabbedMove = -1;
        PVec3 _moveFrom;
        bool _confirmed, _pointed;
        bool _practiceGrabbed, _practiceConfirmed;
        PVec3 _practiceFrom;
        int _loopRound = -1, _loopNext;
        bool _loopConfirmTried;

        const double Rad = Math.PI / 180.0;

        static double Lerp(double a, double b, double u) => a + (b - a) * u;

        /// <summary>이번 프레임의 참여자 입력. dt는 이번 프레임 길이(멈춤 거리: 세션은 이동을 먼저 반영한 뒤 버튼을 보므로,
        /// 이번 프레임 이동 뒤 위치가 목표에 닿는 프레임에 누른다. 0이면 지금 위치로 판단).</summary>
        public PlacementInputFrame Participant(PlacementSession s, double dt = 0)
        {
            var f = new PlacementInputFrame();
            if (s == null || s.Finished) return f;
            if (s.Phase == PlacementPhase.Condition) return s.Config.IsPlace ? PlaceFrame(s) : ViewFrame(s);
            if (s.Phase == PlacementPhase.Practice) return PracticeFrame(s);
            if (s.Phase == PlacementPhase.StopDistance && s.Config.IsStopLoop) return LoopFrame(s, dt);
            if (s.Phase == PlacementPhase.StopDistance && s.StopTrialActive)
            {
                var plan = s.CurrentStopTrial;
                var arr = plan.IsApproach ? ApproachStopM : RecedeStopM;
                double target = arr.Length > 0 ? arr[plan.DirectionIndex % arr.Length] : double.NaN;
                double next = s.StopDistanceNow + (plan.IsApproach ? -1 : 1) * s.Config.stopSpeedMps * Math.Max(0, dt);
                if (!double.IsNaN(target) && (plan.IsApproach ? next <= target : next >= target)) f.StopDown = f.StopHeld = true;
            }
            return f;
        }

        PlacementInputFrame PlaceFrame(PlacementSession s)
        {
            double t = s.SecondsInPhase;
            var f = new PlacementInputFrame { HasRay = true, RayOrigin = HandOrigin, RayDirection = (s.ObjectPosition - HandOrigin).Normalized };
            for (int i = 0; i < Moves.Length; i++)
            {
                var m = Moves[i];
                if (t < m.AtSeconds || t > m.AtSeconds + m.DurationSeconds + 0.1) continue;   // 끝에 0.1초 머물러 목표에 정확히 닿게
                if (!s.Held)
                {
                    if (_grabbedMove == i) break;   // 이번 이동은 이미 놓았다
                    _grabbedMove = i;
                    _moveFrom = s.ObjectPosition;
                    f.GrabDown = true;
                    f.GrabHeld = true;
                    return f;
                }
                double u = Math.Min(1.0, Math.Max(0.0, (t - m.AtSeconds) / m.DurationSeconds));
                double d0 = PlacementGeometry.HorizontalDistance(_moveFrom), a0 = PlacementGeometry.AzimuthDeg(_moveFrom), h0 = _moveFrom.Y;
                var desired = PlacementGeometry.FromPolar(Lerp(d0, m.DistanceM, u), Lerp(a0, m.AzimuthDeg, u), Lerp(h0, m.HeightM, u));
                var toDesired = desired - HandOrigin;
                f.RayDirection = toDesired.Normalized;
                f.GrabHeld = true;
                f.PushPullDeltaM = toDesired.Length - s.HoldDistanceM;
                return f;
            }
            f.GrabHeld = false;
            if (!_confirmed && ConfirmAtSeconds >= 0 && t >= ConfirmAtSeconds)
            {
                _confirmed = true;
                f.ConfirmDown = true;
            }
            return f;
        }

        // 배치 연습: 상자를 한 번 잡아 목표 자리까지 곧게 옮기고 놓은 뒤 확인
        PlacementInputFrame PracticeFrame(PlacementSession s)
        {
            double t = s.SecondsInPhase;
            var f = new PlacementInputFrame { HasRay = true, RayOrigin = HandOrigin, RayDirection = (s.PracticePosition - HandOrigin).Normalized };
            double end = PracticeGrabAtSeconds + PracticeMoveSeconds;
            if (t >= PracticeGrabAtSeconds && t <= end + 0.1)
            {
                if (!s.PracticeHeld && !_practiceGrabbed)
                {
                    _practiceGrabbed = true;
                    _practiceFrom = s.PracticePosition;
                    f.GrabDown = true;
                    f.GrabHeld = true;
                    return f;
                }
                if (s.PracticeHeld)
                {
                    double u = Math.Min(1.0, Math.Max(0.0, (t - PracticeGrabAtSeconds) / PracticeMoveSeconds));
                    var desired = _practiceFrom + (s.PracticeTarget - _practiceFrom) * u;
                    var toDesired = desired - HandOrigin;
                    f.RayDirection = toDesired.Normalized;
                    f.GrabHeld = true;
                    f.PushPullDeltaM = toDesired.Length - s.PracticeHoldDistanceM;
                    return f;
                }
            }
            f.GrabHeld = false;
            if (!_practiceConfirmed && PracticeConfirmAtSeconds >= 0 && t >= PracticeConfirmAtSeconds)
            {
                _practiceConfirmed = true;
                f.ConfirmDown = true;
            }
            return f;
        }

        // 반복 멈춤(G60-2): 라운드마다 LoopStops를 차례로 — 지나는 프레임에 멈춤, 머문 뒤 다시 움직임 또는 확정
        PlacementInputFrame LoopFrame(PlacementSession s, double dt)
        {
            var f = new PlacementInputFrame();
            var round = s.CurrentStopRound;
            if (round == null) return f;
            int ri = round.Round - 1;
            if (ri != _loopRound) { _loopRound = ri; _loopNext = 0; _loopConfirmTried = false; }
            var stops = LoopStops.Length > 0 ? LoopStops[ri % LoopStops.Length] ?? new double[0] : new double[0];
            bool confirm = LoopConfirm.Length > 0 && LoopConfirm[ri % LoopConfirm.Length];
            if (s.StopLoopMoving)
            {
                if (!_loopConfirmTried && round.Round == LoopConfirmWhileMovingRound && s.StopLoopSecondsSinceChange >= LoopDwellSeconds)
                {
                    _loopConfirmTried = true;
                    f.ConfirmDown = true;   // 움직이는 중의 확정 — 무시되어야 한다
                    return f;
                }
                if (_loopNext >= stops.Length) return f;
                double target = stops[_loopNext];
                double cur = s.StopDistanceNow;
                double next = cur + s.StopLoopDirection * s.Config.stopSpeedMps * Math.Max(0, dt);
                bool crosses = s.StopLoopDirection < 0 ? (cur > target && next <= target) : (cur < target && next >= target);
                if (crosses && s.StopLoopSecondsSinceChange >= LoopDwellSeconds)
                {
                    _loopNext++;
                    f.StopDown = f.StopHeld = true;
                }
                return f;
            }
            if (s.StopLoopSecondsSinceChange < LoopDwellSeconds) return f;
            if (_loopNext < stops.Length) f.StopDown = f.StopHeld = true;   // 다음 멈춤 자리로 다시 움직임
            else if (confirm) f.ConfirmDown = true;
            return f;
        }

        PlacementInputFrame ViewFrame(PlacementSession s)
        {
            var f = new PlacementInputFrame();
            if (s.Config.controlMode != PlacementConfig.ModePointSelect) return f;
            double t = s.SecondsInPhase;
            var floorPoint = PlacementGeometry.FromPolar(PointDistanceM, PointAzimuthDeg, 0);
            f.HasRay = true;
            f.RayOrigin = HandOrigin;
            f.RayDirection = (floorPoint - HandOrigin).Normalized;
            if (!_pointed && t >= PointAtSeconds)
            {
                _pointed = true;
                f.ConfirmDown = true;
            }
            return f;
        }

        /// <summary>실험자 입력(키 하나씩, KeyDelaySeconds 간격).</summary>
        public void Experimenter(PlacementSession s)
        {
            if (s == null || s.Finished) return;
            if (s.SecondsInPhase < KeyDelaySeconds || s.Now < _nextKey) return;
            _nextKey = s.Now + KeyDelaySeconds;
            switch (s.Phase)
            {
                case PlacementPhase.Intro:
                case PlacementPhase.PreWait:
                case PlacementPhase.PostWait:
                    s.PressNext();
                    break;
                case PlacementPhase.StopDistance:
                    if (!s.StopTrialsStarted) s.PressNext();
                    break;
                case PlacementPhase.PreItems:
                case PlacementPhase.PostItems:
                case PlacementPhase.CheckItems:
                    if (s.ItemsInstructionActive) s.PressNext();   // 문구 파일에 평정 지시문이 있으면 먼저 넘긴다
                    else if (s.PendingRating == null)
                        s.PressDigit(CancelFirstRating && !_cancelled ? MistakeRating : Ratings[_ratingCount % Ratings.Length]);
                    else if (CancelFirstRating && !_cancelled)
                    {
                        _cancelled = true;
                        s.PressBackspace();
                    }
                    else
                    {
                        _ratingCount++;
                        s.PressConfirm();
                    }
                    break;
            }
        }

        /// <summary>한 프레임을 자동으로: 참여자 입력으로 Tick → 실험자 입력.</summary>
        public void Step(PlacementSession s, double dt, HeadPose head)
        {
            if (s == null || s.Finished) return;
            s.Tick(dt, Participant(s, dt), head);
            Experimenter(s);
        }

        /// <summary>자동 시행 머리 경로(HeadPoseProvider.ScriptedPose와 같은 모양): 좌우 ±25° 둘러보기.</summary>
        public static HeadPose ScriptedHead(double t)
        {
            double yaw = 25.0 * Math.Sin(2 * Math.PI * t / 6.0) * Rad;
            double pitch = 8.0 * Math.Sin(2 * Math.PI * t / 11.0) * Rad;
            // Unity Euler(pitch, yaw, 0) = Ry(yaw)·Rx(pitch)
            double cy = Math.Cos(yaw / 2), sy = Math.Sin(yaw / 2), cp = Math.Cos(pitch / 2), sp = Math.Sin(pitch / 2);
            return new HeadPose
            {
                X = 0.15 * Math.Sin(2 * Math.PI * t / 9.0), Y = 1.6, Z = 0.10 * Math.Sin(2 * Math.PI * t / 7.0),
                Qx = cy * sp, Qy = sy * cp, Qz = -sy * sp, Qw = cy * cp,
            };
        }
    }
}
