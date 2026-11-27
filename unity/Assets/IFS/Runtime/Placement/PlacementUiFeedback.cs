// 헤드셋 UI 피드백 규칙(G63, 2026-11-27 — research_notes/VR UI 가독성 기준/vr_ui_guidelines.md 개선 7·8). UnityEngine에 의존하지 않는다.
//   · 햅틱(설정 uiHaptics): 사건 종류 → 펄스(세기 0–1, 길이 ms). 세션이 사건마다 events.csv에 haptic 행을 더하고(추가만),
//     러너가 XR 컨트롤러로 보낸다(InputDevice.SendHapticImpulse). 두 조건이 같이 쓰는 사건(멈춤·재개·멈춤 확정·평정 한 칸·평정 확정,
//     연습을 두 조건에서 할 때의 연습 잡기·놓기·확인)은 조건과 상관없이 같은 펄스다. 잡기·놓기·배치 확인은 직접 배치(와 가리켜 지정의 확인)에만 있다.
//   · 광선 상태(설정 uiRayHover): 기본 · 겨눔(광선이 잡기 판정 구에 닿음) · 잡음. 광선·끝점의 색과 크기만 바꾼다(물체는 그대로).
using System.Globalization;

namespace IFS.SceneSpec.Placement
{
    /// <summary>햅틱 펄스 하나(사건 종류, 세기 0–1, 길이 ms).</summary>
    public readonly struct PlacementHapticPulse
    {
        public readonly string Kind;
        public readonly double Amplitude;
        public readonly int DurationMs;

        public PlacementHapticPulse(string kind, double amplitude, int durationMs)
        {
            Kind = kind;
            Amplitude = amplitude;
            DurationMs = durationMs;
        }

        /// <summary>events.csv haptic 행의 detail.</summary>
        public string EventDetail() =>
            $"kind={Kind};amplitude={Amplitude.ToString("0.00", CultureInfo.InvariantCulture)};duration_ms={DurationMs}";
    }

    public static class PlacementHaptics
    {
        public const string Grab = "grab";
        public const string Release = "release";
        public const string Confirm = "confirm";
        public const string RateStep = "rate_step";
        public const string RateConfirm = "rate_confirm";
        public const string Stop = "stop";
        public const string Resume = "resume";

        /// <summary>잡기·놓기 0.3 · 20 ms, 확인·평정 확정·멈춤·재개 0.5 · 40 ms, 평정 한 칸 0.2 · 10 ms(조사 문서 개선 8의 제안값, 실기 미확인).</summary>
        public static PlacementHapticPulse For(string kind)
        {
            switch (kind)
            {
                case Grab:
                case Release: return new PlacementHapticPulse(kind, 0.3, 20);
                case RateStep: return new PlacementHapticPulse(kind, 0.2, 10);
                default: return new PlacementHapticPulse(kind, 0.5, 40);   // Confirm · RateConfirm · Stop · Resume
            }
        }
    }

    public enum XrRayState { Idle, Hover, Held }

    /// <summary>광선 상태별 겉모습(uiRayHover). 꺼져 있으면 늘 Idle(예전 그대로: 굵기 4 mm, 끝점 3 cm, #4D73B3).</summary>
    public static class XrRayStyle
    {
        public const double IdleWidthM = 0.004, IdleEndDiameterM = 0.03;
        public const double HoverEndDiameterM = 0.045;
        public const double HeldWidthM = 0.006;
        /// <summary>sRGB 0–1. 기본 = XrPlacementInput Inspector 기본 rayColor.</summary>
        public static readonly double[] IdleColor = { 0.30, 0.45, 0.70 };
        /// <summary>겨눔·잡음 색 #F2B233.</summary>
        public static readonly double[] ActiveColor = { 242 / 255.0, 178 / 255.0, 51 / 255.0 };

        /// <summary>광선 상태: 잡고 있으면 Held, (물체가 보이고) 광선이 잡기 판정 구에 앞쪽에서 닿으면 Hover, 아니면 Idle.</summary>
        public static XrRayState State(bool enabled, PVec3 origin, PVec3 direction, bool held, PVec3 objectPosition, bool objectVisible, double grabRadius)
        {
            if (!enabled) return XrRayState.Idle;
            if (held) return XrRayState.Held;
            if (objectVisible && PlacementGeometry.RaySphere(origin, direction.Normalized, objectPosition, grabRadius, out double t) && t >= 0) return XrRayState.Hover;
            return XrRayState.Idle;
        }

        public static double WidthM(XrRayState s, double idleWidthM) => s == XrRayState.Held ? HeldWidthM : idleWidthM;
        public static double EndDiameterM(XrRayState s, double idleEndM) => s == XrRayState.Idle ? idleEndM : HoverEndDiameterM;
    }
}
