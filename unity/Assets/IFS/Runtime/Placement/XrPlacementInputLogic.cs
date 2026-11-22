// XR 컨트롤러 입력의 규칙 부분(UnityEngine 없이 — dotnet 테스트에서 장치 입력을 가짜로 주입해 확인한다).
//   장치 읽기(IXrControllerSource) → 원자료 한 프레임(XrControllerSample) → 이 클래스 → PlacementInputFrame.
// 조작(주 사용 손 하나, 설정 xrHand):
//   광선            : 컨트롤러 자세(조준 pose, 없으면 grip pose)의 앞쪽(+z)
//   잡기·놓기       : 트리거 또는 그립을 누르고 있는 동안 잡는다(떼면 놓는다). 잡기는 누른 순간에만 시도한다
//   당기기·밀기     : 썸스틱 앞(+)·뒤(−). 데드존 밖 값을 0..1로 다시 펴서 PushPullAxis로(속도는 설정 pushPullSpeedMps)
//   확인            : A(오른손)·X(왼손) 버튼을 누른 순간("여기에 둔다" / 가리킨 바닥 점 확정)
//   멈춤 거리 버튼  : 트리거를 누른 순간(StopDown) + 누르고 있음(StopHeld) — 세션은 '내려가는 순간'만 센다(기존 규칙)
//   평정(선택)      : 썸스틱 좌·우를 젖힌 순간 RateStep −1·+1, 트리거를 누른 순간 RateSubmitDown
// 트리거는 아날로그 값에 이력(누름 0.55 이상, 뗌 0.35 이하)을 두어 떨림으로 여러 번 눌리지 않게 한다.
// 꺼져 있을 때(Enabled = false)와 장치가 없을 때는 빈 프레임을 내되, 버튼 상태는 계속 따라가서 다시 켤 때 가짜 '눌림'이 생기지 않게 한다.
using System;

namespace IFS.SceneSpec.Placement
{
    /// <summary>한 프레임의 컨트롤러 원자료. 좌표는 세계 좌표(미터, '나' 기준 — 추적 공간을 리그로 옮긴 값).</summary>
    public struct XrControllerSample
    {
        /// <summary>장치가 있다(연결됨).</summary>
        public bool Valid;
        /// <summary>자세(광선)를 읽었다.</summary>
        public bool HasPose;
        public PVec3 RayOrigin;
        public PVec3 RayDirection;
        /// <summary>트리거 아날로그 값(0..1). 읽지 못했으면 NaN(그때는 TriggerButton을 쓴다).</summary>
        public double Trigger;
        public bool TriggerButton;
        public bool GripButton;
        /// <summary>썸스틱(−1..1). x = 오른쪽 +, y = 앞 +.</summary>
        public double StickX, StickY;
        /// <summary>A(오른손)·X(왼손).</summary>
        public bool PrimaryButton;

        public static XrControllerSample None => new XrControllerSample { Trigger = double.NaN };
    }

    /// <summary>컨트롤러 장치 읽기(얇은 층). Unity에서는 UnityXrControllerSource(InputDevices), 테스트에서는 가짜.</summary>
    public interface IXrControllerSource
    {
        /// <summary>이번 프레임 원자료. 장치가 없으면 Valid = false.</summary>
        XrControllerSample Read();
        /// <summary>장치 이름(없으면 null) — 실험자 화면·events.csv에 남긴다.</summary>
        string DeviceName { get; }
    }

    [Serializable]
    public sealed class XrInputTuning
    {
        /// <summary>썸스틱 데드존(0..1).</summary>
        public double stickDeadzone = 0.2;
        public double triggerPress = 0.55;
        public double triggerRelease = 0.35;
        /// <summary>평정 고르기: 썸스틱 x가 이 값을 넘으면 한 칸, 이 값 아래로 돌아와야 다음 칸.</summary>
        public double rateStepPress = 0.6;
        public double rateStepRelease = 0.3;
    }

    public sealed class XrPlacementInputLogic
    {
        readonly XrInputTuning _t;
        bool _trigger, _grabHeld, _primary;
        int _stickSide;   // −1, 0, +1 (평정 고르기 이력)

        public XrPlacementInputLogic(XrInputTuning tuning = null) { _t = tuning ?? new XrInputTuning(); }

        /// <summary>지금 트리거가 눌린 상태(이력 적용 뒤).</summary>
        public bool TriggerPressed => _trigger;

        public static double Deadzone(double v, double dz)
        {
            if (double.IsNaN(v)) return 0;
            double a = Math.Abs(v);
            if (a <= dz) return 0;
            return Math.Sign(v) * Math.Min(1.0, (a - dz) / Math.Max(1e-9, 1.0 - dz));
        }

        /// <summary>원자료 한 프레임 → 참여자 입력 한 프레임. enabled = false면 빈 프레임(버튼 상태는 따라간다).</summary>
        public PlacementInputFrame Step(XrControllerSample s, bool enabled)
        {
            var f = new PlacementInputFrame();
            if (!s.Valid)
            {
                // 장치가 사라짐: 상태는 그대로 둔다(다시 잡혔을 때 계속 누르고 있던 버튼이 새 '눌림'이 되지 않게).
                return f;
            }
            bool trigger = double.IsNaN(s.Trigger)
                ? s.TriggerButton
                : (_trigger ? s.Trigger > _t.triggerRelease : s.Trigger >= _t.triggerPress);
            bool grab = trigger || s.GripButton;
            bool primary = s.PrimaryButton;
            int step = 0;
            if (_stickSide == 0)
            {
                if (s.StickX >= _t.rateStepPress) { _stickSide = 1; step = 1; }
                else if (s.StickX <= -_t.rateStepPress) { _stickSide = -1; step = -1; }
            }
            else if (Math.Abs(s.StickX) < _t.rateStepRelease || double.IsNaN(s.StickX)) _stickSide = 0;

            if (enabled)
            {
                f.HasRay = s.HasPose;
                f.RayOrigin = s.RayOrigin;
                f.RayDirection = s.RayDirection;
                f.GrabHeld = grab;
                f.GrabDown = grab && !_grabHeld;
                f.PushPullAxis = Deadzone(s.StickY, _t.stickDeadzone);
                f.ConfirmDown = primary && !_primary;
                f.StopDown = trigger && !_trigger;
                f.StopHeld = trigger;
                f.RateStep = step;
                f.RateSubmitDown = trigger && !_trigger;
            }
            _trigger = trigger;
            _grabHeld = grab;
            _primary = primary;
            return f;
        }
    }

    /// <summary>참여자 입력 고르기(설정 inputMode). 결과 Source = desktop | xr. Error면 세션을 시작하지 않는다.</summary>
    public static class PlacementInputSelection
    {
        public sealed class Result
        {
            public string Source;
            public string Error;
            public string Warning;
        }

        public static Result Choose(string inputMode, bool xrHeadActive, bool controllerPresent, string hand = PlacementConfig.HandRight)
        {
            var r = new Result();
            string handName = hand == PlacementConfig.HandLeft ? "왼손" : "오른손";
            string noController = $"XR 컨트롤러({handName})가 보이지 않습니다 — 컨트롤러를 켜고 한 번 흔들어 깨우세요(시작은 할 수 있음)";
            switch (inputMode)
            {
                case PlacementConfig.InputModeDesktop:
                    r.Source = DesktopPlacementInputSourceName;
                    if (xrHeadActive) r.Warning = "헤드셋이 켜져 있지만 inputMode desktop이라 참여자 조작은 마우스·키보드입니다";
                    break;
                case PlacementConfig.InputModeXr:
                    if (!xrHeadActive)
                    {
                        r.Error = "inputMode xr인데 XR 헤드셋이 없습니다(Quest Link 연결·헤드셋 착용·XR 초기화 로그 확인). auto나 desktop을 고르세요";
                        return r;
                    }
                    r.Source = XrSourceName;
                    if (!controllerPresent) r.Warning = noController;
                    break;
                case PlacementConfig.InputModeAuto:
                    if (xrHeadActive)
                    {
                        r.Source = XrSourceName;
                        if (!controllerPresent) r.Warning = noController;
                    }
                    else r.Source = DesktopPlacementInputSourceName;
                    break;
                default:
                    r.Error = $"inputMode {inputMode}: auto | desktop | xr 중 하나";
                    break;
            }
            return r;
        }

        public const string DesktopPlacementInputSourceName = "desktop";
        public const string XrSourceName = "xr";
    }

    /// <summary>XR 광선 표시 길이(보이는 선의 끝). 잡고 있으면 물체 중심까지, 물체에 맞으면 맞은 점, 바닥에 맞으면 바닥 점, 아니면 최대 길이.</summary>
    public static class XrRayVisual
    {
        public static double EndDistance(PVec3 origin, PVec3 direction, bool held, PVec3 objectPosition, bool objectVisible,
            double grabRadius, double maxLength)
        {
            var dir = direction.Normalized;
            double end = maxLength;
            if (held) end = PVec3.Distance(origin, objectPosition);
            else if (objectVisible && PlacementGeometry.RaySphere(origin, dir, objectPosition, grabRadius, out double t) && t >= 0) end = t;
            else if (PlacementGeometry.RayFloor(origin, dir, 0, out var hit)) end = PVec3.Distance(origin, hit);
            return Math.Max(0, Math.Min(maxLength, end));
        }
    }
}
