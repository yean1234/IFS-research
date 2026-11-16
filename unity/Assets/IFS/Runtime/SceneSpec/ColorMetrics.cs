// 색 정확도 측정용 계산(렌더 색 vs SceneSpec 색). UnityEngine에 의존하지 않는다.
//   sRGB(0–1) ↔ 선형, sRGB → CIE XYZ(D65) → CIELAB, 색차 ΔE*ab(CIE76)와 CIEDE2000.
// 근거: IEC 61966-2-1(sRGB 전달 함수·행렬), CIE 15:2004(Lab), Sharma·Wu·Dalal(2005)의 CIEDE2000 구현 노트.
using System;

namespace IFS.SceneSpec
{
    public readonly struct Lab
    {
        public readonly double L, A, B;
        public Lab(double l, double a, double b) { L = l; A = a; B = b; }
        public override string ToString() => $"L*{L:0.##} a*{A:0.##} b*{B:0.##}";
    }

    public static class ColorMetrics
    {
        // D65 기준 백색(Y = 1)
        const double Xn = 0.95047, Yn = 1.0, Zn = 1.08883;

        public static double SrgbToLinear(double c)
        {
            c = Math.Max(0.0, Math.Min(1.0, c));
            return c <= 0.04045 ? c / 12.92 : Math.Pow((c + 0.055) / 1.055, 2.4);
        }

        public static double LinearToSrgb(double c)
        {
            c = Math.Max(0.0, Math.Min(1.0, c));
            return c <= 0.0031308 ? c * 12.92 : 1.055 * Math.Pow(c, 1.0 / 2.4) - 0.055;
        }

        /// <summary>sRGB(각 0–1, 감마 부호화) → CIELAB(D65).</summary>
        public static Lab SrgbToLab(double r, double g, double b)
        {
            double rl = SrgbToLinear(r), gl = SrgbToLinear(g), bl = SrgbToLinear(b);
            double x = 0.4124564 * rl + 0.3575761 * gl + 0.1804375 * bl;
            double y = 0.2126729 * rl + 0.7151522 * gl + 0.0721750 * bl;
            double z = 0.0193339 * rl + 0.1191920 * gl + 0.9503041 * bl;
            double fx = F(x / Xn), fy = F(y / Yn), fz = F(z / Zn);
            return new Lab(116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz));
        }

        static double F(double t)
        {
            const double d = 6.0 / 29.0;
            return t > d * d * d ? Math.Pow(t, 1.0 / 3.0) : t / (3.0 * d * d) + 4.0 / 29.0;
        }

        /// <summary>CIE76 색차(Lab 유클리드 거리).</summary>
        public static double DeltaE76(Lab p, Lab q)
        {
            double dl = p.L - q.L, da = p.A - q.A, db = p.B - q.B;
            return Math.Sqrt(dl * dl + da * da + db * db);
        }

        /// <summary>CIEDE2000 색차(kL = kC = kH = 1).</summary>
        public static double DeltaE2000(Lab p, Lab q)
        {
            const double deg = Math.PI / 180.0;
            double c1 = Math.Sqrt(p.A * p.A + p.B * p.B), c2 = Math.Sqrt(q.A * q.A + q.B * q.B);
            double cBar = (c1 + c2) / 2.0;
            double cBar7 = Math.Pow(cBar, 7);
            double gFactor = 0.5 * (1.0 - Math.Sqrt(cBar7 / (cBar7 + Math.Pow(25.0, 7))));
            double a1 = (1.0 + gFactor) * p.A, a2 = (1.0 + gFactor) * q.A;
            double c1p = Math.Sqrt(a1 * a1 + p.B * p.B), c2p = Math.Sqrt(a2 * a2 + q.B * q.B);
            double h1p = Hue(p.B, a1), h2p = Hue(q.B, a2);

            double dLp = q.L - p.L;
            double dCp = c2p - c1p;
            double dhp;
            if (c1p * c2p == 0) dhp = 0;
            else if (Math.Abs(h2p - h1p) <= 180) dhp = h2p - h1p;
            else if (h2p - h1p > 180) dhp = h2p - h1p - 360;
            else dhp = h2p - h1p + 360;
            double dHp = 2.0 * Math.Sqrt(c1p * c2p) * Math.Sin(dhp / 2.0 * deg);

            double lBarP = (p.L + q.L) / 2.0;
            double cBarP = (c1p + c2p) / 2.0;
            double hBarP;
            if (c1p * c2p == 0) hBarP = h1p + h2p;
            else if (Math.Abs(h1p - h2p) <= 180) hBarP = (h1p + h2p) / 2.0;
            else if (h1p + h2p < 360) hBarP = (h1p + h2p + 360) / 2.0;
            else hBarP = (h1p + h2p - 360) / 2.0;

            double t = 1 - 0.17 * Math.Cos((hBarP - 30) * deg) + 0.24 * Math.Cos(2 * hBarP * deg)
                       + 0.32 * Math.Cos((3 * hBarP + 6) * deg) - 0.20 * Math.Cos((4 * hBarP - 63) * deg);
            double dTheta = 30 * Math.Exp(-Math.Pow((hBarP - 275) / 25, 2));
            double cBarP7 = Math.Pow(cBarP, 7);
            double rc = 2 * Math.Sqrt(cBarP7 / (cBarP7 + Math.Pow(25.0, 7)));
            double lm = (lBarP - 50) * (lBarP - 50);
            double sl = 1 + 0.015 * lm / Math.Sqrt(20 + lm);
            double sc = 1 + 0.045 * cBarP;
            double sh = 1 + 0.015 * cBarP * t;
            double rt = -Math.Sin(2 * dTheta * deg) * rc;

            double tl = dLp / sl, tc = dCp / sc, th = dHp / sh;
            return Math.Sqrt(tl * tl + tc * tc + th * th + rt * tc * th);
        }

        static double Hue(double b, double a)
        {
            if (b == 0 && a == 0) return 0;
            double h = Math.Atan2(b, a) * 180.0 / Math.PI;
            return h < 0 ? h + 360 : h;
        }
    }
}
