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

        // ── 헤드셋 UI 개선(G63, 2026-11-27, research_notes/VR UI 가독성 기준/vr_ui_guidelines.md) ──────────────
        // 모두 설정 플래그(PlacementConfig ui*)를 켰을 때만 쓴다. 꺼져 있으면 위의 값·식 그대로(G52: 기본 화면·기록 보존).
        /// <summary>판 기본값(PlacementTextPanel Inspector 기본값과 같다).</summary>
        public const int DefaultWrapChars = 20;
        public const double DefaultBodyLineSpacing = 1.13;
        public const double DefaultMarginM = 0.08;
        public const double DefaultColumnWidthM = 0.22;
        public const double DefaultMaxTopM = 0.85;
        public const double DefaultMinBottomM = 0.05;
        public const double CellPadM = 0.018;
        public const double DefaultSelectionFrameM = 0.012;

        /// <summary>(1) 편한 시선 영역 줄바꿈: 본문 한 줄 24자. 판이 여전히 아래 한계를 넘으면 ComfortWrapMaxChars까지 넓혀 본다.</summary>
        public const int ComfortWrapChars = 24;
        /// <summary>넓혀 볼 최대 줄 길이(26자 = 판 폭 약 1.57 m, 2.24 m에서 약 39° — 주 내용 41° 안).</summary>
        public const int ComfortWrapMaxChars = 26;
        /// <summary>판 아래 가장자리의 한계(수평 아래, 도). Microsoft Comfort의 최적 시선 영역 0–35° 아래.</summary>
        public const double ComfortBottomLimitDeg = 35.0;
        /// <summary>(6) 7칸 평정 줄의 칸 너비(0.22 → 0.20 m).</summary>
        public const double NarrowColumnWidthM = 0.20;
        /// <summary>(5) 평정 확정 표시: 확정한 칸 테두리를 이만큼 굵게(m), 이 시간(초) 동안.</summary>
        public const double ConfirmFlashFrameM = 0.02;
        public const double ConfirmFlashSeconds = 0.4;
        /// <summary>주 내용 가로 시야 한계(도, Android XR 41°). 평정 줄 폭 점검용.</summary>
        public const double MainContentWidthLimitDeg = 41.0;

        // (2) 어두운 판 테마(안 A): 판 #2A2B30, 글 #E6E6E8(약 11:1), 고른 칸 글·테두리 #9EC3FF, 고른 칸 바탕 #1F3050.
        // 판·고른 칸은 조명을 받지 않게(알베도 검정 + 금속도 1 → 반사 0) 방출만으로 그린다 — 렌더 화소 = 이 색.
        public static readonly double[] DarkBackgroundSrgb = { 42 / 255.0, 43 / 255.0, 48 / 255.0 };
        public static readonly double[] DarkTextSrgb = { 230 / 255.0, 230 / 255.0, 232 / 255.0 };
        public static readonly double[] DarkHighlightSrgb = { 158 / 255.0, 195 / 255.0, 255 / 255.0 };
        public static readonly double[] DarkSelectionFillSrgb = { 31 / 255.0, 48 / 255.0, 80 / 255.0 };
        /// <summary>어두운 판 본문 대비의 허용 범위(하한 7:1, 상한 15:1 — 사용자 선호 8.7–11.9:1, 21:1은 '최악'으로 자주 뽑힘).</summary>
        public const double DarkContrastMin = 7.0, DarkContrastMax = 15.0;

        /// <summary>본문만 있는 판의 높이(m): 줄 수 × 줄 높이 + 위아래 여백(PlacementTextPanel.Layout과 같은 식).</summary>
        public static double BodyPanelHeightM(int lines, double characterSize = BodyCharacterSize, int fontSize = FontSize,
            double lineSpacing = DefaultBodyLineSpacing, double marginM = DefaultMarginM)
            => lines * EmHeightM(characterSize, fontSize) * FontLinePitchEm * lineSpacing + 2 * marginM;

        /// <summary>평정 문항 판의 높이(m): 본문 줄 + 반 줄 간격 + 칸(안쪽 여백 · 숫자 줄 · 뜻 줄) + 여백(PlacementTextPanel.Layout과 같은 식).</summary>
        public static double ItemPanelHeightM(int bodyLines, int labelLines, double lineSpacing = DefaultBodyLineSpacing, double marginM = DefaultMarginM)
        {
            double bodyPitch = EmHeightM(BodyCharacterSize, FontSize) * FontLinePitchEm * lineSpacing;
            double numLine = EmHeightM(NumberCharacterSize, FontSize) * FontLinePitchEm;
            double labelPitch = EmHeightM(LabelCharacterSize, FontSize) * FontLinePitchEm;
            return bodyLines * bodyPitch + bodyPitch * 0.5 + (CellPadM + numLine + labelLines * labelPitch + CellPadM) + 2 * marginM;
        }

        /// <summary>판 자리(PlacementTextPanel.Place와 같은 규칙): 판 중심을 (0, centerY, forward)에 두고 눈 (0, eyeY, 0)을 보게 돌린다.
        /// 위 가장자리가 maxTopM을 넘으면 아래 가장자리가 minBottomM에 닿을 때까지 중심을 내린다.
        /// 돌려주는 값: 실제 중심 높이, 아래 가장자리의 수평 아래 각(도, 눈 기준), 위 가장자리 높이(m).</summary>
        public static (double centerY, double bottomBelowHorizonDeg, double topY) PanelPlacement(double panelHeightM,
            double forwardM = DefaultForwardM, double centerY = DefaultPanelHeightM, double eyeY = DefaultEyeHeightM,
            double maxTopM = DefaultMaxTopM, double minBottomM = DefaultMinBottomM, double floorMarginM = -1)
            => PanelPlacementFloored(panelHeightM, forwardM, centerY, eyeY, maxTopM, minBottomM, floorMarginM, out _);

        /// <summary>판 위 방향의 세로 성분(판 높이 절반 × 이 값 = 판 중심에서 위·아래 끝까지의 세로 거리).</summary>
        public static double UpY(double centerY, double eyeY, double forwardM)
        {
            double dy = centerY - eyeY, len = Math.Sqrt(dy * dy + forwardM * forwardM);
            return len > 1e-9 ? forwardM / len : 1;
        }

        /// <summary>CP17-3 판 하한(눈높이 기준 배치에서만 켠다 — floorMarginM ≥ 0): 위 가장자리 규칙 뒤에 판 아래 끝이 바닥에서 floorMarginM 위에 남도록
        /// 중심을 올린다(중심 ≥ 세로 반높이 + 여유. 올리면 기울기가 줄어 세로 반높이가 조금 커지므로 몇 번 다시 잰다). 걸렸으면 floored true.
        /// floorMarginM &lt; 0이면 예전 규칙 그대로. 판이 기본 자리(0.6 m)·기본 눈높이(1.6 m)면 위 가장자리 규칙이 이미 아래 끝을 minBottomM 위에 두므로 걸리지 않는다.</summary>
        public static double FloorCenterY(double centerY, double panelHeightM, double eyeY, double forwardM, double floorMarginM, out bool floored)
        {
            floored = false;
            if (floorMarginM < 0) return centerY;
            double c = centerY;
            for (int i = 0; i < 4; i++)
            {
                double halfUp = panelHeightM * 0.5 * UpY(c, eyeY, forwardM);
                if (c >= halfUp + floorMarginM - 1e-6) break;
                c = halfUp + floorMarginM;
                floored = true;
            }
            return c;
        }

        public static (double centerY, double bottomBelowHorizonDeg, double topY) PanelPlacementFloored(double panelHeightM,
            double forwardM, double centerY, double eyeY, double maxTopM, double minBottomM, double floorMarginM, out bool floored)
        {
            // 판의 위 방향(LookRotation(중심 − 눈, 위)) = (0, 수평 성분, −수직 성분) / 거리
            (double uy, double uz) Up(double cy)
            {
                double dy = cy - eyeY, len = Math.Sqrt(dy * dy + forwardM * forwardM);
                return len > 1e-9 ? (forwardM / len, -dy / len) : (1, 0);
            }
            double c = centerY;
            if (maxTopM > 0)
            {
                double halfUp = panelHeightM * 0.5 * Math.Abs(Up(c).uy);
                if (c + halfUp > maxTopM) c = Math.Max(maxTopM - halfUp, minBottomM + halfUp);
            }
            c = FloorCenterY(c, panelHeightM, eyeY, forwardM, floorMarginM, out floored);
            var (y, z) = Up(c);
            double bottomY = c - panelHeightM * 0.5 * y, bottomZ = forwardM - panelHeightM * 0.5 * z;
            double topY = c + panelHeightM * 0.5 * y;
            return (c, Math.Atan2(eyeY - bottomY, bottomZ) * 180.0 / Math.PI, topY);
        }

        public static double BottomBelowHorizonDeg(double panelHeightM, double forwardM = DefaultForwardM, double centerY = DefaultPanelHeightM,
            double eyeY = DefaultEyeHeightM, double maxTopM = DefaultMaxTopM, double minBottomM = DefaultMinBottomM)
            => PanelPlacement(panelHeightM, forwardM, centerY, eyeY, maxTopM, minBottomM).bottomBelowHorizonDeg;

        /// <summary>본문만 있는 판이 아래 한계(limitDeg)를 넘지 않는 최대 줄 수(1 미만이면 1).</summary>
        public static int MaxBodyLinesWithin(double limitDeg = ComfortBottomLimitDeg, double forwardM = DefaultForwardM, double centerY = DefaultPanelHeightM,
            double eyeY = DefaultEyeHeightM, double maxTopM = DefaultMaxTopM, double minBottomM = DefaultMinBottomM,
            double characterSize = BodyCharacterSize, double lineSpacing = DefaultBodyLineSpacing, double marginM = DefaultMarginM)
        {
            int best = 1;
            for (int n = 1; n <= 40; n++)
            {
                double h = BodyPanelHeightM(n, characterSize, FontSize, lineSpacing, marginM);
                if (BottomBelowHorizonDeg(h, forwardM, centerY, eyeY, maxTopM, minBottomM) <= limitDeg + 1e-9) best = n;
                else break;
            }
            return best;
        }

        /// <summary>띄어쓰기에서 줄을 바꾼 줄 수(ParticipantTextDisplay.Wrap과 같은 규칙: 문단은 '\n', 낱말이 maxChars보다 길면 한 줄).</summary>
        public static int WrapLineCount(string text, int maxChars)
        {
            if (string.IsNullOrEmpty(text)) return 0;
            if (maxChars <= 0) return text.Replace("\r\n", "\n").Split('\n').Length;
            int lines = 0;
            foreach (var para in text.Replace("\r\n", "\n").Split('\n'))
            {
                lines++;
                int line = 0;
                foreach (var word in para.Split(' '))
                {
                    if (word.Length == 0) continue;
                    if (line > 0 && line + 1 + word.Length > maxChars) { lines++; line = 0; }
                    else if (line > 0) line++;
                    line += word.Length;
                }
            }
            return lines;
        }

        /// <summary>(1) 긴 안내를 문장 경계에서 여러 쪽으로 나눈다(글자는 그대로 — 쪽을 잘린 자리의 구분자(' ' 또는 '\n')로 다시 이으면 원문).
        /// 한 쪽은 wrapChars로 줄을 바꿨을 때 maxLines 줄 이하가 되게 문장을 앞에서부터 채운다. 한 문장이 maxLines를 넘으면 그 문장 혼자 한 쪽.
        /// 문장 경계 = '.', '?', '!' 다음의 띄어쓰기, 또는 줄바꿈('\n'). 나눌 필요가 없으면 한 쪽(원문).</summary>
        public static System.Collections.Generic.List<string> SentencePages(string text, int wrapChars, int maxLines)
        {
            var pages = new System.Collections.Generic.List<string>();
            if (string.IsNullOrEmpty(text)) { pages.Add(text ?? ""); return pages; }
            if (maxLines < 1 || WrapLineCount(text, wrapChars) <= maxLines) { pages.Add(text); return pages; }
            // 문장 조각: (조각 글, 조각 뒤 구분자 — 마지막 조각은 "")
            var pieces = new System.Collections.Generic.List<(string piece, string sep)>();
            int start = 0;
            for (int i = 0; i < text.Length; i++)
            {
                bool newline = text[i] == '\n';
                bool sentenceSpace = text[i] == ' ' && i > 0 && (text[i - 1] == '.' || text[i - 1] == '?' || text[i - 1] == '!');
                if (!newline && !sentenceSpace) continue;
                pieces.Add((text.Substring(start, i - start), text[i].ToString()));
                start = i + 1;
            }
            pieces.Add((text.Substring(start), ""));
            string cur = null;
            foreach (var (piece, sep) in pieces)
            {
                string joined = cur == null ? piece : cur + piece;
                if (cur != null && WrapLineCount(joined, wrapChars) > maxLines)
                {
                    pages.Add(cur.Substring(0, cur.Length - 1));   // 앞 조각 뒤 구분자는 쪽 경계가 된다
                    joined = piece;
                }
                cur = joined + sep;
            }
            if (cur != null) pages.Add(cur);
            return pages;
        }

        /// <summary>판 가로 시야각(도): 너비 widthM을 거리 distanceM에서.</summary>
        public static double PanelWidthDeg(double widthM, double distanceM = -1) => VisualAngleDeg(widthM, distanceM > 0 ? distanceM : DefaultViewDistanceM);

        /// <summary>n칸 평정 줄의 판 너비(m, 근사): 칸 중심 범위 + 양 끝 칸 반폭(뜻이 칸보다 넓지 않을 때) + 여백.</summary>
        public static double ScaleRowPanelWidthM(int n, double columnWidthM, double marginM = DefaultMarginM)
        {
            double col = ColumnWidth(n, columnWidthM);
            return (n - 1) * col + col + 2 * marginM;
        }
    }
}
