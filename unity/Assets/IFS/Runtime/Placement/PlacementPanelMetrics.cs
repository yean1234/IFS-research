// 참여자 판(PlacementTextPanel)과 실험자 화면의 표현 계산(2026-11-23 G44 화면 개선). UnityEngine에 의존하지 않는다 —
// dotnet 테스트와 Unity EditMode 테스트가 같은 식을 확인하고, 캡처 도구(Editor/PlacementUiCapture.cs)가 실측에 쓴다.
//   · 시야각: 2·atan(크기 / (2·거리)). 헤드셋 글자 권장 약 1° 이상(ui-ux-pro-max §5 readable-font-size를 VR 각도로 옮긴 기준).
//   · 대비비: WCAG 2.x 상대 휘도(sRGB) — §1 color-contrast, §6 color-accessible-pairs(본문 4.5:1 이상).
//   · 기준점 칸: 7칸까지는 기본 너비, 넘으면 줄 전체가 7칸 너비(예전 규칙 그대로). 기준점 뜻은 칸 너비에 맞춰 줄을 바꾼다.
// 기록·측정 로직과 무관하다(화면 표현만).
using System;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementPanelMetrics
    {
        // ── 기본 색(sRGB 0–1). PlacementTextPanel의 Inspector 기본값과 같다(테스트가 대비비를 확인) ──
        public static readonly double[] TextSrgb = { 0.08, 0.08, 0.10 };
        public static readonly double[] BackgroundSrgb = { 0.90, 0.90, 0.91 };
        /// <summary>고른 숫자·기준점 뜻의 글자색(짙은 파랑). 판 배경·고른 칸 바탕 모두에서 4.5:1 이상.</summary>
        public static readonly double[] HighlightSrgb = { 0.05, 0.22, 0.62 };
        /// <summary>고른 칸 바탕(흰색에 가까움) — 판 배경과 구별되는 면.</summary>
        public static readonly double[] SelectionFillSrgb = { 1.0, 1.0, 1.0 };

        // ── 글자 크기 ──
        public const int FontSize = 64;
        /// <summary>TextMesh: characterSize × fontSize × 0.1 m ≈ 한 글자 칸 높이(em).</summary>
        public const double UnitPerPx = 0.1;
        public const double BodyCharacterSize = 0.0085;
        /// <summary>기준점 뜻 글자(2026-11-23 0.0055 → 0.0075: 2.24 m에서 잉크 높이 약 1°).</summary>
        public const double LabelCharacterSize = 0.0075;
        /// <summary>글꼴 줄 높이(em). 맑은 고딕 TextMesh 실측("가"와 "가\n가" 경계 높이 차 ÷ 글자 칸, 2026-11-23).</summary>
        public const double FontLinePitchEm = 1.33;
        /// <summary>평정 숫자 글자(본문보다 크게: 숫자 잉크 높이가 한글보다 낮아서).</summary>
        public const double NumberCharacterSize = 0.010;
        /// <summary>잉크 높이 ÷ 글자 칸(em), 맑은 고딕 TextMesh 실측(2026-11-23, 흰 바탕에 찍어 어두운 화소 행): 한글 "가" 0.94, 숫자 "7" 0.72.</summary>
        public const double HangulInkPerEm = 0.94;
        public const double DigitInkPerEm = 0.72;
        /// <summary>권장 최소 글자 시야각(도).</summary>
        public const double MinTextAngleDeg = 1.0;

        // ── 기본 판 자리(PlacementRunner 기본값: 정면 2.0 m, 판 중심 높이 0.6 m, 눈높이 1.6 m) ──
        public const double DefaultForwardM = 2.0;
        public const double DefaultPanelHeightM = 0.6;
        public const double DefaultEyeHeightM = 1.6;
        public static double DefaultViewDistanceM =>
            Math.Sqrt(DefaultForwardM * DefaultForwardM + (DefaultEyeHeightM - DefaultPanelHeightM) * (DefaultEyeHeightM - DefaultPanelHeightM));

        /// <summary>기준점 칸 수가 이보다 많으면 줄 전체를 이 칸 수의 너비로 좁힌다.</summary>
        public const int FullWidthColumns = 7;

        public static double EmHeightM(double characterSize, int fontSize) => characterSize * fontSize * UnitPerPx;

        /// <summary>크기 sizeM인 것을 distanceM에서 볼 때의 시야각(도).</summary>
        public static double VisualAngleDeg(double sizeM, double distanceM)
        {
            if (distanceM <= 0) throw new ArgumentOutOfRangeException(nameof(distanceM));
            return 2.0 * Math.Atan(sizeM / (2.0 * distanceM)) * 180.0 / Math.PI;
        }

        /// <summary>distanceM에서 angleDeg로 보이는 크기(m).</summary>
        public static double SizeForAngleM(double angleDeg, double distanceM) => 2.0 * distanceM * Math.Tan(angleDeg * Math.PI / 360.0);

        /// <summary>WCAG 2.x 상대 휘도(성분은 sRGB 0–1).</summary>
        public static double RelativeLuminance(double r, double g, double b) =>
            0.2126 * Linear(r) + 0.7152 * Linear(g) + 0.0722 * Linear(b);

        public static double RelativeLuminance(double[] srgb) => RelativeLuminance(srgb[0], srgb[1], srgb[2]);

        static double Linear(double c) => c <= 0.04045 ? c / 12.92 : Math.Pow((c + 0.055) / 1.055, 2.4);

        /// <summary>두 상대 휘도의 대비비(밝은 쪽 + 0.05) / (어두운 쪽 + 0.05), 1–21.</summary>
        public static double ContrastRatio(double luminanceA, double luminanceB)
        {
            double hi = Math.Max(luminanceA, luminanceB), lo = Math.Min(luminanceA, luminanceB);
            return (hi + 0.05) / (lo + 0.05);
        }

        public static double ContrastRatio(double[] srgbA, double[] srgbB) => ContrastRatio(RelativeLuminance(srgbA), RelativeLuminance(srgbB));

        /// <summary>기준점 한 칸 너비(m): n ≤ 7이면 baseWidth, 넘으면 줄 전체가 7칸 너비가 되게 좁힌다(예전 규칙).</summary>
        public static double ColumnWidth(int n, double baseWidth) => n > FullWidthColumns ? baseWidth * FullWidthColumns / n : baseWidth;

        /// <summary>기준점 뜻 한 줄 최대 글자 수: 칸 너비의 92% 안에 한글이 몇 자 들어가는지(최소 minChars).
        /// 띄어쓰기에서만 줄을 바꾸므로(ParticipantTextDisplay.Wrap) 이보다 긴 낱말은 한 줄로 남는다.</summary>
        public static int LabelWrapChars(double columnWidthM, double labelEmM, int minChars = 2)
        {
            if (labelEmM <= 0) return minChars;
            return Math.Max(minChars, (int)Math.Floor(columnWidthM * 0.92 / labelEmM));
        }

        /// <summary>평정 칸 v가 지금 고른 값인지(참여자 컨트롤러 커서). 고른 칸은 색·굵기·테두리 셋으로 표시한다.</summary>
        public static bool IsSelected(int? cursor, int v) => cursor.HasValue && cursor.Value == v;
    }
}
