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

        /// <summary>(2.2) 기본 형상 키(form.base). 범주 값으로 들고 있지만 CategoricalKeys에는 넣지 않는다 — 기본 형상 슬롯이 없는
        /// 2.0·2.1 spec의 기록(initialScene.json·golden 지문)이 그대로이도록, 2.2 spec이거나 덮어쓰기로 기본 형상을 정했을 때만
        /// ToRecord·ChangedCategories에 나온다(HasBaseSlot).</summary>
        public const string BaseKey = BaseShapes.Key;
        public const string NoBase = BaseShapes.None;

        readonly Dictionary<string, double> _num = new Dictionary<string, double>();
        readonly Dictionary<string, string> _cat = new Dictionary<string, string>();

        /// <summary>SceneSpec의 null 대신 기본값을 쓴 키(조정량 분석에서 '참여자가 말한 값'과 구분해야 한다).</summary>
        public List<string> DefaultsUsed { get; } = new List<string>();
        /// <summary>_inferred(3층 제안)를 쓴 키. useInferred가 false면 비어 있다.</summary>
        public List<string> InferredUsed { get; } = new List<string>();

        /// <summary>(2.2) 기본 형상 슬롯이 있는 값 집합인가(2.2 spec, 또는 form.base를 none이 아닌 값으로 정함).</summary>
        public bool HasBaseSlot { get; private set; }
        /// <summary>(2.2) spec이 말한 기본 형상(없으면 null)과 그 변형값. 변형값은 그리는 기본 형상이 spec의 것과 같을 때만 쓴다.</summary>
        public string SpecBase { get; private set; }
        public BaseVariantSpec SpecBaseVariant { get; private set; }

        /// <summary>지금 기본 형상의 변형값(spec 기본 형상과 같으면 spec 변형값, 아니면 null = 형상 프리셋 기본값).</summary>
        public BaseVariantSpec CurrentBaseVariant => _cat[BaseKey] == SpecBase ? SpecBaseVariant : null;

        /// <summary>(2.3) 윤곽·발광 슬롯이 있는 값 집합인가(2.3 spec, 또는 덮어쓰기로 셋 중 하나를 정함). 이때만 렌더 계획·기록에
        /// contour·emission이 나온다. 세 값(form.roundness·form.aspect·material.emission)은 범주 값으로 들고 있지만 null(말하지 않음)을
        /// 기본값으로 채우지 않는다 — 렌더 계획이 무엇을 기본값으로 그렸는지 따로 남긴다(ContourRender, docs/scene-spec-mapping.md 8.4절).
        /// CategoricalKeys·ToRecord에는 넣지 않는다(2.0–2.2 spec의 기록·golden 지문이 그대로, 2.3 null 문서의 params도 2.2와 같다).</summary>
        public bool HasContourSlots { get; private set; }

        /// <summary>(2.4, G72) x·y·z 비율 슬롯이 있는 값 집합인가(2.4 spec, 또는 덮어쓰기·조정으로 비율 키를 정함). 이때만 ToRecord·Deltas에
        /// layout.proportions.x·y·z(유효 비율 = 원값 / 가장 큰 값, 소수 4자리)가 나온다. NumericKeys에는 넣지 않는다(2.0–2.3 spec의 기록·golden 지문이 그대로).
        /// 원값(spec 값 0.2–1 또는 덮어쓰기·조절 화면 값 0.2–2.0 그대로)은 수치 키 layout.proportions.x·y·z로 들고 있다(GetNumber는 원값).</summary>
        public bool HasProportionsSlot { get; private set; }
        /// <summary>(2.4) 비율이 주어졌는가(spec 값이 null이 아니거나, 덮어쓰기·조정으로 비율 키를 하나라도 정함). 이때만 렌더러가 비율을 그리고
        /// form.aspect 축 비율을 쓰지 않는다(비율이 앞선다). 주어지지 않으면 (1, 1, 1) — 2.3과 같은 그림.</summary>
        public bool ProportionsGiven { get; private set; }
        /// <summary>(2.4) spec 비율 값의 axisSaid(spec 값이 null이면 null).</summary>
        public bool? SpecProportionsAxisSaid { get; private set; }

        /// <summary>(2.4) 지금 비율의 원값 (x, y, z)(0.2–2.0). 새 배열.</summary>
        public double[] ProportionsRaw => new[] { _num[ProportionsRender.XKey], _num[ProportionsRender.YKey], _num[ProportionsRender.ZKey] };
        /// <summary>(2.4) 지금 비율의 유효 값(clamp(원값 / 가장 큰 값, 0.2, 1), 가장 큰 값 = 1). 새 배열.</summary>
        public double[] ProportionsEffective => ProportionsRender.Normalize(_num[ProportionsRender.XKey], _num[ProportionsRender.YKey], _num[ProportionsRender.ZKey]);

        /// <summary>(2.4 선택, G74) 안개 입자 모양 슬롯이 있는 값 집합인가(키가 있는 2.4 spec, 또는 덮어쓰기로 form.mistKind를 정함).
        /// 이때만 ToRecord·ChangedCategories·렌더 계획에 form.mistKind가 나온다. 값은 범주 값으로 들고 있지만(null = 말하지 않음)
        /// CategoricalKeys에는 넣지 않는다(키가 없는 문서의 기록·golden 지문이 그대로).</summary>
        public bool HasMistKindSlot { get; private set; }

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
            // (2.2) 기본 형상. 모르는 값은 그리지 않는다(SceneSpecJson.Validate가 경고). 2.0·2.1 spec은 슬롯이 없어 기본값 기록도 남기지 않음
            p.HasBaseSlot = s.Form.BaseKeysPresent || s.Form.Base != null;
            p.SpecBase = BaseShapes.IsBase(s.Form.Base) ? s.Form.Base : null;
            p.SpecBaseVariant = p.SpecBase != null ? s.Form.BaseVariant?.Clone() : null;
            p._cat[BaseKey] = p.SpecBase ?? NoBase;
            if (p.HasBaseSlot && p.SpecBase == null) p.DefaultsUsed.Add(BaseKey);
            // (2.3) 윤곽·발광: 말한 값 그대로(null = 말하지 않음). 기본값 기록은 렌더 계획이 정한다(그린 경로에 따라 다르므로)
            p.HasContourSlots = SceneSpecJson.HasContourKeys(s) || s.Form.Roundness != null || s.Form.Aspect != null || s.Material.Emission != null;
            p._cat[ContourRender.RoundnessKey] = ContourRender.IsRoundness(s.Form.Roundness) ? s.Form.Roundness : null;
            p._cat[ContourRender.AspectKey] = ContourRender.IsAspect(s.Form.Aspect) ? s.Form.Aspect : null;
            p._cat[ContourRender.EmissionKey] = ContourRender.IsEmission(s.Material.Emission) ? s.Material.Emission : null;
            // (2.4 선택, G74) 안개 입자 모양: 말한 값 그대로(null = 말하지 않음 → cloud와 같은 그림). 기본값 기록은 슬롯이 있는 문서일 때만
            p.HasMistKindSlot = s.Form.MistKindKeyPresent || s.Form.MistKind != null;
            p._cat[MistKinds.Key] = MistKinds.IsKind(s.Form.MistKind) ? s.Form.MistKind : null;
            if (p.HasMistKindSlot && p._cat[MistKinds.Key] == null) p.DefaultsUsed.Add(MistKinds.Key);
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
            // (2.4) x·y·z 비율: 원값 그대로(0.2–1로 자름), null이면 (1, 1, 1). 기본값 기록은 2.4 spec(비율 슬롯이 있음)일 때만
            var pr = s.Layout.Proportions;
            p.HasProportionsSlot = s.Layout.ProportionsKeyPresent || pr != null;
            p.ProportionsGiven = pr != null;
            p.SpecProportionsAxisSaid = pr?.AxisSaid;
            p._num[ProportionsRender.XKey] = ProportionsRender.Clamp(pr?.X ?? 1.0);
            p._num[ProportionsRender.YKey] = ProportionsRender.Clamp(pr?.Y ?? 1.0);
            p._num[ProportionsRender.ZKey] = ProportionsRender.Clamp(pr?.Z ?? 1.0);
            if (p.HasProportionsSlot && pr == null) p.DefaultsUsed.Add(ProportionsRender.Key);
            Cat("motion.type", s.Motion.Type, d.motionType);
            Num("motion.speed", s.Motion.Speed, "motion.speed", d.motionSpeed);
            return p;
        }

        public bool IsNumeric(string key) => _num.ContainsKey(key);
        public bool IsCategorical(string key) => _cat.ContainsKey(key);
        public double GetNumber(string key) => _num[key];
        public string GetCategory(string key) => _cat[key];

        /// <summary>0–1로 잘라 넣는다((2.4) 비율 키는 0.2–1로 자르고 비율 슬롯을 연다). 값이 실제로 바뀌면 true.</summary>
        public bool SetNumber(string key, double value)
        {
            if (!_num.ContainsKey(key)) throw new ArgumentException("수치 파라미터가 아님: " + key);
            if (ProportionsRender.IsAxisKey(key))
            {
                HasProportionsSlot = true;
                ProportionsGiven = true;   // 원값이 그대로여도 '정했다'(덮어쓰기 1.0 = 말한 값과 같음)
                value = ProportionsRender.ClampRaw(value);   // 원값 0.2–2.0(덮어쓰기 검사가 밖이면 이미 거부)
            }
            else value = Clamp01(value);
            if (Math.Abs(_num[key] - value) < 1e-9) return false;
            _num[key] = value;
            return true;
        }

        public bool SetCategory(string key, string value)
        {
            if (!_cat.ContainsKey(key)) throw new ArgumentException("범주 파라미터가 아님: " + key);
            if (key == "form.type" && Array.IndexOf(FormTypes, value) < 0) throw new ArgumentException("모르는 형태: " + value);
            if (key == BaseKey && value != NoBase && !BaseShapes.IsBase(value)) throw new ArgumentException("모르는 기본 형상: " + value);
            if (key == BaseKey && value != NoBase) HasBaseSlot = true;
            if (ContourRender.Levels.TryGetValue(key, out var levels))
            {
                if (value == null || Array.IndexOf(levels, value) < 0)
                    throw new ArgumentException($"모르는 {key}: {value}(가능: {string.Join(", ", levels)})");
                HasContourSlots = true;
            }
            if (key == MistKinds.Key)
            {
                if (!MistKinds.IsKind(value)) throw new ArgumentException($"모르는 {key}: {value}(가능: {string.Join(", ", MistKinds.Values)})");
                HasMistKindSlot = true;
            }
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
            p.HasBaseSlot = HasBaseSlot;
            p.SpecBase = SpecBase;
            p.SpecBaseVariant = SpecBaseVariant?.Clone();
            p.HasContourSlots = HasContourSlots;
            p.HasMistKindSlot = HasMistKindSlot;
            p.HasProportionsSlot = HasProportionsSlot;
            p.ProportionsGiven = ProportionsGiven;
            p.SpecProportionsAxisSaid = SpecProportionsAxisSaid;
            return p;
        }

        /// <summary>기록용: 수치는 소수 4자리, 키 순서 고정.</summary>
        public SortedDictionary<string, object> ToRecord()
        {
            var r = new SortedDictionary<string, object>(StringComparer.Ordinal);
            foreach (var k in NumericKeys) r[k] = Math.Round(_num[k], 4);
            foreach (var k in CategoricalKeys) r[k] = _cat[k];
            if (HasBaseSlot) r[BaseKey] = _cat[BaseKey];
            if (HasMistKindSlot) r[MistKinds.Key] = _cat[MistKinds.Key];   // (2.4 선택, G74) 키가 있을 때만(null = 말하지 않음)
            // (2.4) 비율 슬롯이 있을 때만 유효 비율(가장 큰 값 = 1)
            if (HasProportionsSlot)
            {
                var e = ProportionsEffective;
                for (int k = 0; k < 3; k++) r[ProportionsRender.AxisKeys[k]] = Math.Round(e[k], 4);
            }
            return r;
        }

        /// <summary>초기값 → 최종값 차이(0–1 척도). 색상(h)은 원형이라 짧은 쪽으로 잰다.
        /// (2.4) 비율 슬롯이 어느 쪽에든 있으면 layout.proportions.x·y·z(유효 비율의 차이)도 넣는다.</summary>
        public static SortedDictionary<string, double> Deltas(SceneParams initial, SceneParams final)
        {
            var r = new SortedDictionary<string, double>(StringComparer.Ordinal);
            if (initial.HasProportionsSlot || final.HasProportionsSlot)
            {
                var a = initial.ProportionsEffective;
                var b = final.ProportionsEffective;
                for (int k = 0; k < 3; k++) r[ProportionsRender.AxisKeys[k]] = Math.Round(b[k] - a[k], 4);
            }
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

        /// <summary>수치 파라미터 조정량의 RMS(0–1). 범주 변경은 따로 센다. 분석용 잠정 지표(decision-log).
        /// NumericKeys만 센다((2.4) 비율 차이는 Deltas에만 — spec 판이 달라도 지표의 분모가 같게).</summary>
        public static double AdjustmentRms(SceneParams initial, SceneParams final)
        {
            var all = Deltas(initial, final);
            var d = NumericKeys.Select(k => all[k]).ToArray();
            return Math.Round(Math.Sqrt(d.Sum(x => x * x) / d.Length), 4);
        }

        public static List<string> ChangedCategories(SceneParams initial, SceneParams final)
        {
            var r = CategoricalKeys.Where(k => initial._cat[k] != final._cat[k]).ToList();
            if ((initial.HasBaseSlot || final.HasBaseSlot) && initial._cat[BaseKey] != final._cat[BaseKey]) r.Add(BaseKey);
            foreach (var k in ContourRender.SlotPaths)
                if (initial._cat[k] != final._cat[k]) r.Add(k);
            if ((initial.HasMistKindSlot || final.HasMistKindSlot) && initial._cat[MistKinds.Key] != final._cat[MistKinds.Key]) r.Add(MistKinds.Key);
            return r;
        }

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
