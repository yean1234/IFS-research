// 렌더에 실제로 쓰는 값(0–1 정규화)의 평평한 집합. SceneSpec의 null을 기본값으로 채우고 무엇을 채웠는지 남긴다.
// VR 조정은 이 값을 바꾸고, initialScene/finalScene은 이 값을 기록한다(조정량 = 같은 0–1 척도에서의 차이).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Linq;

namespace IFS.SceneSpec
{
    /// <summary>null 슬롯에 쓸 기본값. Unity Inspector에서 바꿀 수 있다(값을 바꾸면 decision-log에 남길 것).</summary>
    [Serializable]
    public sealed class SceneDefaults
    {
        public string formType = "blob";
        public string posture = SceneParams.NoPosture;
        public float colorH = 0f;
        public float colorS = 0f;
        public float colorL = 0.7f;
        public float brightness = 0.5f;
        public float roughness = 0.5f;
        public float opacity = 1f;
        public float erosion = 0f;
        public float size = 0.5f;
        public float distance = 0.33f;        // 0.3 + 0.33 × 2.7 ≈ 1.2 m
        public float verticalOffset = 0.75f;  // 키 대비 0.75 ≈ 가슴 위 ~ 어깨 아래
        public string motionType = "still";
        public float motionSpeed = 0.5f;
    }

    public sealed class SceneParams
    {
        public const string NoPosture = "none";

        public static readonly string[] NumericKeys =
        {
            "material.color.h", "material.color.s", "material.color.l",
            "material.brightness", "material.roughness", "material.opacity", "material.erosion",
            "layout.size", "layout.distance", "layout.verticalOffset",
            "motion.speed",
        };

        public static readonly string[] CategoricalKeys = { "form.type", "form.posture", "motion.type" };

        public static readonly string[] FormTypes = { "blob", "mist", "shell", "fragments" };

        readonly Dictionary<string, double> _num = new Dictionary<string, double>();
        readonly Dictionary<string, string> _cat = new Dictionary<string, string>();

        /// <summary>SceneSpec의 null 대신 기본값을 쓴 키(조정량 분석에서 '참여자가 말한 값'과 구분해야 한다).</summary>
        public List<string> DefaultsUsed { get; } = new List<string>();
        /// <summary>_inferred(3층 제안)를 쓴 키. useInferred가 false면 비어 있다.</summary>
        public List<string> InferredUsed { get; } = new List<string>();

        SceneParams() { }

        public static SceneParams FromSpec(SceneSpecV2 s, SceneDefaults d, bool useInferred = false)
        {
            var p = new SceneParams();
            double? Inferred(string path)
            {
                if (!useInferred || s.Inferred == null || !s.Inferred.TryGetValue(path, out var v)) return null;
                p.InferredUsed.Add(path);
                return v.Value;
            }
            void Num(string key, double? stated, string inferPath, double fallback)
            {
                double? v = stated ?? (inferPath != null ? Inferred(inferPath) : null);
                if (v == null) p.DefaultsUsed.Add(key);
                p._num[key] = Clamp01(v ?? fallback);
            }
            void Cat(string key, string stated, string fallback)
            {
                if (stated == null) p.DefaultsUsed.Add(key);
                p._cat[key] = stated ?? fallback;
            }

            Cat("form.type", s.Form.Type, d.formType);
            Cat("form.posture", s.Form.Posture, string.IsNullOrEmpty(d.posture) ? NoPosture : d.posture);
            var c = s.Material.Color;
            Num("material.color.h", c?.H, null, d.colorH);
            Num("material.color.s", s.Material.Saturation ?? c?.S, null, d.colorS);   // 채도어가 있으면 그 값
            Num("material.color.l", c?.L, null, d.colorL);
            Num("material.brightness", s.Material.Brightness, "material.brightness", d.brightness);
            Num("material.roughness", s.Material.Roughness, null, d.roughness);
            Num("material.opacity", s.Material.Opacity, null, d.opacity);
            Num("material.erosion", s.Material.Erosion, null, d.erosion);
            Num("layout.size", s.Layout.Size, "layout.size", d.size);
            Num("layout.distance", s.Layout.Distance, null, d.distance);
            Num("layout.verticalOffset", s.Layout.VerticalOffset, null, d.verticalOffset);
            Cat("motion.type", s.Motion.Type, d.motionType);
            Num("motion.speed", s.Motion.Speed, "motion.speed", d.motionSpeed);
            return p;
        }

        public bool IsNumeric(string key) => _num.ContainsKey(key);
        public bool IsCategorical(string key) => _cat.ContainsKey(key);
        public double GetNumber(string key) => _num[key];
        public string GetCategory(string key) => _cat[key];

        /// <summary>0–1로 잘라 넣는다. 값이 실제로 바뀌면 true.</summary>
        public bool SetNumber(string key, double value)
        {
            if (!_num.ContainsKey(key)) throw new ArgumentException("수치 파라미터가 아님: " + key);
            value = Clamp01(value);
            if (Math.Abs(_num[key] - value) < 1e-9) return false;
            _num[key] = value;
            return true;
        }

        public bool SetCategory(string key, string value)
        {
            if (!_cat.ContainsKey(key)) throw new ArgumentException("범주 파라미터가 아님: " + key);
            if (key == "form.type" && Array.IndexOf(FormTypes, value) < 0) throw new ArgumentException("모르는 형태: " + value);
            if (_cat[key] == value) return false;
            _cat[key] = value;
            return true;
        }

        public SceneParams Clone()
        {
            var p = new SceneParams();
            foreach (var kv in _num) p._num[kv.Key] = kv.Value;
            foreach (var kv in _cat) p._cat[kv.Key] = kv.Value;
            p.DefaultsUsed.AddRange(DefaultsUsed);
            p.InferredUsed.AddRange(InferredUsed);
            return p;
        }

        /// <summary>기록용: 수치는 소수 4자리, 키 순서 고정.</summary>
        public SortedDictionary<string, object> ToRecord()
        {
            var r = new SortedDictionary<string, object>(StringComparer.Ordinal);
            foreach (var k in NumericKeys) r[k] = Math.Round(_num[k], 4);
            foreach (var k in CategoricalKeys) r[k] = _cat[k];
            return r;
        }

        /// <summary>초기값 → 최종값 차이(0–1 척도). 색상(h)은 원형이라 짧은 쪽으로 잰다.</summary>
        public static SortedDictionary<string, double> Deltas(SceneParams initial, SceneParams final)
        {
            var r = new SortedDictionary<string, double>(StringComparer.Ordinal);
            foreach (var k in NumericKeys)
            {
                double delta = final._num[k] - initial._num[k];
                if (k == "material.color.h")
                {
                    delta = (delta + 1.5) % 1.0 - 0.5;   // -0.5 ~ 0.5
                }
                r[k] = Math.Round(delta, 4);
            }
            return r;
        }

        /// <summary>수치 파라미터 조정량의 RMS(0–1). 범주 변경은 따로 센다. 분석용 잠정 지표(decision-log).</summary>
        public static double AdjustmentRms(SceneParams initial, SceneParams final)
        {
            var d = Deltas(initial, final).Values.ToArray();
            return Math.Round(Math.Sqrt(d.Sum(x => x * x) / d.Length), 4);
        }

        public static List<string> ChangedCategories(SceneParams initial, SceneParams final) =>
            CategoricalKeys.Where(k => initial._cat[k] != final._cat[k]).ToList();

        /// <summary>size(0–1, 로그 척도) → 배율. 0.5 = ×1, 0 = ×0.25, 1 = ×4.</summary>
        public static double SizeToScale(double size) => Math.Pow(2.0, (size - 0.5) * 4.0);

        /// <summary>HSL(각 0–1) → RGB(각 0–1).</summary>
        public static void HslToRgb(double h, double s, double l, out double r, out double g, out double b)
        {
            if (s <= 0) { r = g = b = l; return; }
            double q = l < 0.5 ? l * (1 + s) : l + s - l * s;
            double p = 2 * l - q;
            r = Hue(p, q, h + 1.0 / 3);
            g = Hue(p, q, h);
            b = Hue(p, q, h - 1.0 / 3);
        }

        static double Hue(double p, double q, double t)
        {
            if (t < 0) t += 1;
            if (t > 1) t -= 1;
            if (t < 1.0 / 6) return p + (q - p) * 6 * t;
            if (t < 0.5) return q;
            if (t < 2.0 / 3) return p + (q - p) * (2.0 / 3 - t) * 6;
            return p;
        }

        static double Clamp01(double v) => v < 0 ? 0 : (v > 1 ? 1 : v);
    }
}
