// 배치 캡처의 형상 지표(X72): 화소별 덮임(알파, 0–1) 배열 → 보이는 화소 수·최대 알파·윤곽 원형도·덩어리 수·가장자리 감쇠 폭.
// "더 그 형상답다"의 대리 지표일 뿐이다(사람 판정을 대신하지 않는다). UnityEngine에 의존하지 않는다(dotnet 테스트 가능).
//   visiblePixels  덮임 ≥ VisibleAlpha(배경과 다른 화소. 8비트 양자화 잡음보다 큰 값)
//   maxAlpha       덮임의 최댓값
//   마스크         덮임 ≥ 0.5 × maxAlpha (투명한 형상도 자기 최댓값 기준으로 윤곽을 잡는다)
//   circularity    4π·넓이/둘레². 넓이 = 마스크 화소 수, 둘레 = 마스크 문턱 등고선의 마칭 스퀘어 길이(선형 보간, 화소 단위).
//                  가장자리가 부드러운(MSAA) 원 ≈ 1, 정사각형 ≈ π/4
//   components     8-이웃으로 이어진 덩어리 중 넓이가 마스크 전체의 MinComponentFraction 이상인 것의 수(침식 부스러기 제외)
//   edgeFalloffPx  (넓이(덮임 ≥ 0.1·max) − 넓이(덮임 ≥ 0.9·max)) / 둘레(마스크). 가장자리 띠의 평균 폭 = 덮임이 10%→90%로 오르는 폭
//   contrast       (D7) 실제 장면 렌더의 L*: 마스크 안 평균 − 주변 배경 띠 평균(BackgroundContrast)
using System;
using System.Collections.Generic;

namespace IFS.SceneSpec.EditorTools
{
    public sealed class SilhouetteResult
    {
        public int VisiblePixels;
        public double MaxAlpha;
        public int MaskPixels;
        public double PerimeterPx;
        public double Circularity;
        public int Components;
        public int ComponentsRaw;
        public double EdgeFalloffPx;
    }

    /// <summary>형상 영역과 주변 배경의 밝기 대비(SilhouetteMetrics.BackgroundContrast).</summary>
    public sealed class ContrastResult
    {
        public bool HasValue;
        public double ShapeL, BackgroundL, DeltaL, ShapeLStd;
        public int ShapePixels, BackgroundPixels;
    }

    public static class SilhouetteMetrics
    {
        /// <summary>배경과 다르다고 보는 덮임 하한(검·흰 배경 렌더 차이의 8비트 양자화 잡음보다 크게).</summary>
        public const double VisibleAlpha = 0.02;
        /// <summary>윤곽 마스크 = 덮임 ≥ MaskFraction × maxAlpha.</summary>
        public const double MaskFraction = 0.5;
        /// <summary>덩어리로 세는 최소 넓이(마스크 전체 넓이에 대한 비율).</summary>
        public const double MinComponentFraction = 0.005;
        public const double FalloffLow = 0.1, FalloffHigh = 0.9;

        public static SilhouetteResult Measure(float[] alpha, int width, int height)
        {
            if (alpha == null) throw new ArgumentNullException(nameof(alpha));
            if (alpha.Length != width * height) throw new ArgumentException("alpha 길이 ≠ width × height");
            var r = new SilhouetteResult();
            double max = 0;
            for (int i = 0; i < alpha.Length; i++)
            {
                if (alpha[i] >= VisibleAlpha) r.VisiblePixels++;
                if (alpha[i] > max) max = alpha[i];
            }
            r.MaxAlpha = max;
            if (r.VisiblePixels == 0 || max <= 0) return r;   // 보이지 않음: 윤곽 지표 0

            var mask = Threshold(alpha, MaskFraction * max, out int maskN);
            r.MaskPixels = maskN;
            r.PerimeterPx = Perimeter(alpha, width, height, MaskFraction * max);
            r.Circularity = r.PerimeterPx > 0 ? 4.0 * Math.PI * maskN / (r.PerimeterPx * r.PerimeterPx) : 0;
            r.Components = CountComponents(mask, width, height, Math.Max(1, (int)Math.Ceiling(MinComponentFraction * maskN)), out r.ComponentsRaw);
            Threshold(alpha, FalloffLow * max, out int lowN);
            Threshold(alpha, FalloffHigh * max, out int highN);
            r.EdgeFalloffPx = r.PerimeterPx > 0 ? (lowN - highN) / r.PerimeterPx : 0;
            return r;
        }

        static bool[] Threshold(float[] alpha, double t, out int count)
        {
            var m = new bool[alpha.Length];
            count = 0;
            for (int i = 0; i < alpha.Length; i++)
                if (alpha[i] >= t) { m[i] = true; count++; }
            return m;
        }

        /// <summary>
        /// 마칭 스퀘어 윤곽 길이(화소 단위): 덮임 값이 iso인 등고선을 칸마다 선형 보간한 선분의 합. 화면 밖 = 0.
        /// 칸의 네 모서리 = 화소 중심. 안장(대각선 두 개만 안쪽)은 칸 중앙 평균으로 이을지 정한다.
        /// MSAA로 가장자리가 부드러운 렌더에서는 실제 윤곽에 가깝고, 0/1 마스크면 변의 중점을 잇는다(계단 때문에 원보다 약 6% 길다).
        /// </summary>
        public static double Perimeter(float[] alpha, int w, int h, double iso)
        {
            double V(int x, int y) => x >= 0 && y >= 0 && x < w && y < h ? alpha[y * w + x] : 0.0;
            double T(double p, double q) => Math.Abs(q - p) < 1e-12 ? 0.5 : Math.Max(0, Math.Min(1, (iso - p) / (q - p)));
            double Len(double x0, double y0, double x1, double y1) => Math.Sqrt((x1 - x0) * (x1 - x0) + (y1 - y0) * (y1 - y0));
            double len = 0;
            for (int y = -1; y < h; y++)
                for (int x = -1; x < w; x++)
                {
                    double a = V(x, y), b = V(x + 1, y), c = V(x + 1, y + 1), d = V(x, y + 1);
                    int k = (a >= iso ? 1 : 0) | (b >= iso ? 2 : 0) | (c >= iso ? 4 : 0) | (d >= iso ? 8 : 0);
                    if (k == 0 || k == 15) continue;
                    // 네 변의 교차점(칸 안 좌표 0–1): ab 위, bc 오른쪽, dc 아래, ad 왼쪽
                    double abx = T(a, b), aby = 0, bcx = 1, bcy = T(b, c), dcx = T(d, c), dcy = 1, adx = 0, ady = T(a, d);
                    double AB_BC() => Len(abx, aby, bcx, bcy);
                    double AB_DC() => Len(abx, aby, dcx, dcy);
                    double AB_AD() => Len(abx, aby, adx, ady);
                    double BC_DC() => Len(bcx, bcy, dcx, dcy);
                    double BC_AD() => Len(bcx, bcy, adx, ady);
                    double DC_AD() => Len(dcx, dcy, adx, ady);
                    bool centerIn = (a + b + c + d) / 4.0 >= iso;
                    switch (k)
                    {
                        case 1: case 14: len += AB_AD(); break;
                        case 2: case 13: len += AB_BC(); break;
                        case 3: case 12: len += BC_AD(); break;
                        case 4: case 11: len += BC_DC(); break;
                        case 6: case 9: len += AB_DC(); break;
                        case 7: case 8: len += DC_AD(); break;
                        case 5:   // a·c 안쪽
                            len += centerIn ? AB_BC() + DC_AD() : AB_AD() + BC_DC();
                            break;
                        case 10:  // b·d 안쪽
                            len += centerIn ? AB_AD() + BC_DC() : AB_BC() + DC_AD();
                            break;
                    }
                }
            return len;
        }

        /// <summary>배경 대비의 주변 띠: 보이는 화소(덮임 ≥ VisibleAlpha)의 경계 상자를 긴 변 × 이 비율만큼 사방으로 넓힌 상자 안에서 덮임 &lt; VisibleAlpha인 화소.</summary>
        public const double BackgroundMarginFraction = 0.25;

        /// <summary>
        /// 형상 영역과 주변 배경의 밝기 대비(D7, 2026-11-23). lstar = 실제 장면 렌더(배경과 섞인 화면)의 화소별 CIE L*(0–100), alpha = 덮임.
        ///   형상 영역 = 윤곽 마스크(덮임 ≥ MaskFraction × maxAlpha), 주변 배경 = BackgroundMarginFraction의 띠(덮임 &lt; VisibleAlpha).
        ///   deltaL = 형상 영역 평균 L* − 주변 배경 평균 L*. shapeLStd = 형상 영역 안 L*의 표준편차(덩이 음영처럼 안쪽 밝기 차가 있는가).
        /// 보이는 화소가 없거나 배경 띠가 비면 null을 담는다(HasValue = false).
        /// </summary>
        public static ContrastResult BackgroundContrast(float[] alpha, double[] lstar, int w, int h)
        {
            if (alpha == null || lstar == null) throw new ArgumentNullException(alpha == null ? nameof(alpha) : nameof(lstar));
            if (alpha.Length != w * h || lstar.Length != w * h) throw new ArgumentException("길이 ≠ width × height");
            var r = new ContrastResult();
            double max = 0;
            int minX = w, minY = h, maxX = -1, maxY = -1;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                {
                    float a = alpha[y * w + x];
                    if (a > max) max = a;
                    if (a < VisibleAlpha) continue;
                    if (x < minX) minX = x;
                    if (x > maxX) maxX = x;
                    if (y < minY) minY = y;
                    if (y > maxY) maxY = y;
                }
            if (maxX < 0 || max <= 0) return r;
            int margin = (int)Math.Ceiling(BackgroundMarginFraction * Math.Max(maxX - minX + 1, maxY - minY + 1));
            int x0 = Math.Max(0, minX - margin), x1 = Math.Min(w - 1, maxX + margin);
            int y0 = Math.Max(0, minY - margin), y1 = Math.Min(h - 1, maxY + margin);
            double iso = MaskFraction * max;
            double sumS = 0, sumS2 = 0, sumB = 0;
            for (int y = y0; y <= y1; y++)
                for (int x = x0; x <= x1; x++)
                {
                    int i = y * w + x;
                    if (alpha[i] >= iso) { sumS += lstar[i]; sumS2 += lstar[i] * lstar[i]; r.ShapePixels++; }
                    else if (alpha[i] < VisibleAlpha) { sumB += lstar[i]; r.BackgroundPixels++; }
                }
            if (r.ShapePixels == 0 || r.BackgroundPixels == 0) return r;
            r.HasValue = true;
            r.ShapeL = sumS / r.ShapePixels;
            r.BackgroundL = sumB / r.BackgroundPixels;
            r.DeltaL = r.ShapeL - r.BackgroundL;
            r.ShapeLStd = Math.Sqrt(Math.Max(0, sumS2 / r.ShapePixels - r.ShapeL * r.ShapeL));
            return r;
        }

        /// <summary>8-이웃 연결 덩어리 수. minArea 미만은 세지 않는다(raw는 모두 센 값).</summary>
        public static int CountComponents(bool[] mask, int w, int h, int minArea, out int raw)
        {
            var seen = new bool[mask.Length];
            var stack = new Stack<int>();
            int count = 0;
            raw = 0;
            for (int s = 0; s < mask.Length; s++)
            {
                if (!mask[s] || seen[s]) continue;
                raw++;
                int area = 0;
                seen[s] = true;
                stack.Push(s);
                while (stack.Count > 0)
                {
                    int i = stack.Pop();
                    area++;
                    int x = i % w, y = i / w;
                    for (int dy = -1; dy <= 1; dy++)
                        for (int dx = -1; dx <= 1; dx++)
                        {
                            int nx = x + dx, ny = y + dy;
                            if ((dx == 0 && dy == 0) || nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
                            int j = ny * w + nx;
                            if (mask[j] && !seen[j]) { seen[j] = true; stack.Push(j); }
                        }
                }
                if (area >= minArea) count++;
            }
            return count;
        }
    }
}
