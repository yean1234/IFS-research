// BatchCapture 명령줄 인자와 통계 계산. UnityEngine에 의존하지 않는다(dotnet 테스트에서 실제로 실행된다).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace IFS.SceneSpec.EditorTools
{
    public sealed class CaptureOptions
    {
        public string SpecDir;
        public string OutDir;
        /// <summary>눈 하나의 렌더 해상도. 기본 = Quest 3 눈당 2064×2208.</summary>
        public int Width = 2064;
        public int Height = 2208;
        /// <summary>시간을 재는 프레임 수(준비 프레임 제외).</summary>
        public int Frames = 300;
        public int WarmupFrames = 30;
        /// <summary>한 프레임에 렌더하는 눈 수(2 = 양안을 두 번 렌더하는 멀티패스, 가장 불리한 경우).</summary>
        public int Eyes = 2;
        /// <summary>저장 PNG의 폭(0이면 원래 해상도).</summary>
        public int PngWidth = 1024;
        /// <summary>세로 시야각(도). Quest 3 눈당 세로 시야 ≈ 96°(제조사 공개 사양 기준 근사).</summary>
        public float FieldOfView = 96f;
        public float EyeHeight = 1.6f;
        public float Ipd = 0.064f;
        /// <summary>비우면 현재 품질 단계를 쓴다.</summary>
        public string Quality = "";

        public static CaptureOptions Parse(IList<string> args)
        {
            var o = new CaptureOptions();
            for (int i = 0; i < args.Count; i++)
            {
                string a = args[i];
                string Next()
                {
                    if (i + 1 >= args.Count) throw new ArgumentException(a + " 뒤에 값이 없습니다.");
                    return args[++i];
                }
                switch (a)
                {
                    case "-specDir": o.SpecDir = Next(); break;
                    case "-outDir": o.OutDir = Next(); break;
                    case "-width": o.Width = PositiveInt(a, Next()); break;
                    case "-height": o.Height = PositiveInt(a, Next()); break;
                    case "-frames": o.Frames = PositiveInt(a, Next()); break;
                    case "-warmup": o.WarmupFrames = NonNegativeInt(a, Next()); break;
                    case "-eyes": o.Eyes = PositiveInt(a, Next()); break;
                    case "-pngWidth": o.PngWidth = NonNegativeInt(a, Next()); break;
                    case "-fov": o.FieldOfView = float.Parse(Next(), CultureInfo.InvariantCulture); break;
                    case "-eyeHeight": o.EyeHeight = float.Parse(Next(), CultureInfo.InvariantCulture); break;
                    case "-quality": o.Quality = Next(); break;
                }
            }
            if (string.IsNullOrEmpty(o.SpecDir)) throw new ArgumentException("-specDir <SceneSpec JSON 폴더>가 필요합니다.");
            if (string.IsNullOrEmpty(o.OutDir)) throw new ArgumentException("-outDir <결과 폴더>가 필요합니다.");
            if (o.Eyes > 2) throw new ArgumentException("-eyes는 1 또는 2");
            return o;
        }

        static int PositiveInt(string name, string v)
        {
            int n = int.Parse(v, CultureInfo.InvariantCulture);
            if (n <= 0) throw new ArgumentException(name + "는 1 이상");
            return n;
        }

        static int NonNegativeInt(string name, string v)
        {
            int n = int.Parse(v, CultureInfo.InvariantCulture);
            if (n < 0) throw new ArgumentException(name + "는 0 이상");
            return n;
        }
    }

    public static class CaptureStats
    {
        /// <summary>최근접 순위(nearest-rank) 백분위수. p는 0–100.</summary>
        public static double Percentile(IReadOnlyList<double> values, double p)
        {
            if (values == null || values.Count == 0) throw new ArgumentException("값이 없습니다.");
            var sorted = values.OrderBy(v => v).ToArray();
            if (p <= 0) return sorted[0];
            int rank = (int)Math.Ceiling(p / 100.0 * sorted.Length);
            return sorted[Math.Min(sorted.Length, Math.Max(1, rank)) - 1];
        }

        public static double Mean(IReadOnlyList<double> values) => values.Count == 0 ? double.NaN : values.Average();

        /// <summary>ms → fps (프레임시간 기준)</summary>
        public static double Fps(double ms) => ms <= 0 ? double.PositiveInfinity : 1000.0 / ms;
    }
}
