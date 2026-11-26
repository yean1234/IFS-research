// SceneSpec v2 읽기·쓰기. 모르는 필드·빠진 필드는 오류로 본다(형식이 어긋난 파일로 실험하지 않도록).
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Newtonsoft.Json;

namespace IFS.SceneSpec
{
    public static class SceneSpecJson
    {
        /// <summary>엄격 설정: 클래스에 없는 JSON 필드가 있으면 실패, null도 그대로 쓴다.</summary>
        public static JsonSerializerSettings Strict => new JsonSerializerSettings
        {
            MissingMemberHandling = MissingMemberHandling.Error,
            NullValueHandling = NullValueHandling.Include,
            FloatParseHandling = FloatParseHandling.Double,
            Culture = CultureInfo.InvariantCulture,
        };

        public static readonly string[] SlotPaths =
        {
            "form.type", "form.posture",
            "material.color", "material.brightness", "material.saturation", "material.roughness", "material.opacity",
            "material.erosion",
            "layout.size", "layout.distance", "layout.verticalOffset",
            "motion.type", "motion.speed",
            "body.part", "body.layer",
        };

        /// <exception cref="JsonException">형식이 SceneSpec v2와 다를 때</exception>
        public static SceneSpecV2 Parse(string json)
        {
            var spec = JsonConvert.DeserializeObject<SceneSpecV2>(json, Strict);
            if (spec == null) throw new JsonSerializationException("빈 SceneSpec JSON");
            ReadKeyPresence(json, spec);
            // (2.3) 윤곽·발광 값은 닫힌 서수 목록이다. 표에 없는 값은 기본 형상 변형 키처럼 파싱 오류(그리지 못하는 값을 받지 않는다)
            CheckLevel(ContourRender.RoundnessKey, spec.Form.Roundness);
            CheckLevel(ContourRender.AspectKey, spec.Form.Aspect);
            CheckLevel(ContourRender.EmissionKey, spec.Material.Emission);
            return spec;
        }

        static void CheckLevel(string path, string value)
        {
            if (value == null) return;
            var levels = ContourRender.Levels[path];
            if (Array.IndexOf(levels, value) < 0)
                throw new JsonSerializationException($"{path}: 모르는 값 {value}(가능: {string.Join(", ", levels)}, null)");
        }

        /// <summary>원문에 2.2·2.3 키가 있는가(값이 null이어도). 역직렬화로는 '없음'과 'null'을 가를 수 없어 따로 본다.
        /// (2.2) form.base·form.baseVariant, (2.3) form.roundness·form.aspect, material.emission.</summary>
        static void ReadKeyPresence(string json, SceneSpecV2 spec)
        {
            using var reader = new JsonTextReader(new StringReader(json)) { DateParseHandling = DateParseHandling.None, FloatParseHandling = FloatParseHandling.Double };
            var root = Newtonsoft.Json.Linq.JToken.ReadFrom(reader);
            var form = root["form"] as Newtonsoft.Json.Linq.JObject;
            var material = root["material"] as Newtonsoft.Json.Linq.JObject;
            spec.Form.BaseKeysPresent = form != null && (form.ContainsKey("base") || form.ContainsKey("baseVariant"));
            spec.Form.ContourKeysPresent = form != null && (form.ContainsKey("roundness") || form.ContainsKey("aspect"));
            spec.Material.EmissionKeyPresent = material != null && material.ContainsKey("emission");
        }

        /// <summary>(2.3) 원문에 윤곽·발광 키가 하나라도 있는가(2.3.0 문서).</summary>
        public static bool HasContourKeys(SceneSpecV2 s) => s.Form.ContourKeysPresent || s.Material.EmissionKeyPresent;

        /// <summary>(2.2) 기본 형상 슬롯 경로. SlotPaths(2.0 슬롯)와 따로 둔다.</summary>
        public static readonly string[] BaseSlotPaths = { BaseShapes.Key, BaseShapes.VariantKey };

        public static SceneSpecV2 Load(string path) => Parse(File.ReadAllText(path, Encoding.UTF8));

        public static string Serialize(SceneSpecV2 spec) => JsonConvert.SerializeObject(spec, Formatting.Indented, Strict);

        /// <summary>슬롯 경로의 값(null이면 참여자가 말하지 않은 것).</summary>
        public static object GetSlot(SceneSpecV2 s, string path)
        {
            switch (path)
            {
                case "form.type": return s.Form.Type;
                case "form.posture": return s.Form.Posture;
                case "material.color": return s.Material.Color;
                case "material.brightness": return s.Material.Brightness;
                case "material.saturation": return s.Material.Saturation;
                case "material.roughness": return s.Material.Roughness;
                case "material.opacity": return s.Material.Opacity;
                case "material.erosion": return s.Material.Erosion;
                case "layout.size": return s.Layout.Size;
                case "layout.distance": return s.Layout.Distance;
                case "layout.verticalOffset": return s.Layout.VerticalOffset;
                case "motion.type": return s.Motion.Type;
                case "motion.speed": return s.Motion.Speed;
                case "body.part": return s.Body.Part;
                case "body.layer": return s.Body.Layer;
                case BaseShapes.Key: return s.Form.Base;
                case BaseShapes.VariantKey: return s.Form.BaseVariant;
                case ContourRender.RoundnessKey: return s.Form.Roundness;
                case ContourRender.AspectKey: return s.Form.Aspect;
                case ContourRender.EmissionKey: return s.Material.Emission;
                default: throw new ArgumentException("모르는 슬롯 경로: " + path);
            }
        }

        /// <summary>스키마의 원칙 규칙을 다시 확인한다(버전, 0–1 범위, 값 ⇔ _provenance, _inferred는 빈 슬롯만).
        /// 문제가 있어도 예외를 내지 않고 목록을 돌려준다 — SceneLoader가 경고로 남긴다.</summary>
        public static List<string> Validate(SceneSpecV2 s)
        {
            var problems = new List<string>();
            if (Array.IndexOf(SceneSpecV2.SupportedSpecVersions, s.Meta.SpecVersion) < 0)
                problems.Add($"specVersion {s.Meta.SpecVersion} (지원: {string.Join(", ", SceneSpecV2.SupportedSpecVersions)})");
            if (s.Meta.SpecVersion == SceneSpecV2.SupportedSpecVersion && s.HasV21Fields)
                problems.Add("specVersion 2.0.0 문서에 2.1 전용 필드(_context … _clauses, meta.mapping)가 있다");
            foreach (var path in SlotPaths)
            {
                var value = GetSlot(s, path);
                bool hasProv = s.Provenance.TryGetValue(path, out var provs) && provs != null && provs.Count > 0;
                if (value == null && hasProv) problems.Add(path + ": null인데 _provenance가 있다");
                if (value != null && !hasProv) problems.Add(path + ": 값이 있는데 _provenance가 없다");
                if (value != null && s.Inferred.ContainsKey(path)) problems.Add(path + ": 값이 있는데 _inferred도 있다");
                if (value is double d && (d < 0 || d > 1)) problems.Add($"{path}: {d}가 0–1 밖");
                if (value is HslColor c && (c.H < 0 || c.H > 1 || c.S < 0 || c.S > 1 || c.L < 0 || c.L > 1))
                    problems.Add(path + ": HSL이 0–1 밖");
            }
            // (2.2) 기본 형상: 2.2.0 문서(와 그 상위 2.3.0 문서)에만 키가 있고, 값 ⇔ _provenance 규칙은 다른 슬롯과 같다
            bool v23 = s.Meta.SpecVersion == SceneSpecV2.SpecVersionV23;
            bool v22 = s.Meta.SpecVersion == SceneSpecV2.SpecVersionV22 || v23;
            if (v22 && !s.Form.BaseKeysPresent) problems.Add($"specVersion {s.Meta.SpecVersion} 문서에 form.base·form.baseVariant가 없다");
            if (!v22 && (s.Form.BaseKeysPresent || s.Form.Base != null || s.Form.BaseVariant != null))
                problems.Add($"specVersion {s.Meta.SpecVersion} 문서에 2.2 전용 필드(form.base·form.baseVariant)가 있다");
            // (2.3) 윤곽·발광: 2.3.0 문서는 세 키를 반드시 가지고(값이 null이어도), 2.0–2.2 문서에는 없어야 한다
            if (v23 && !(s.Form.ContourKeysPresent && s.Material.EmissionKeyPresent))
                problems.Add("specVersion 2.3.0 문서에 form.roundness·form.aspect·material.emission이 없다");
            if (!v23 && (HasContourKeys(s) || s.Form.Roundness != null || s.Form.Aspect != null || s.Material.Emission != null))
                problems.Add($"specVersion {s.Meta.SpecVersion} 문서에 2.3 전용 필드(form.roundness·form.aspect·material.emission)가 있다");
            foreach (var path in ContourRender.SlotPaths)
            {
                var value = GetSlot(s, path);
                bool hasProv = s.Provenance.TryGetValue(path, out var provs) && provs != null && provs.Count > 0;
                if (value == null && hasProv) problems.Add(path + ": null인데 _provenance가 있다");
                if (value != null && !hasProv) problems.Add(path + ": 값이 있는데 _provenance가 없다");
                if (value != null && s.Inferred.ContainsKey(path)) problems.Add(path + ": 값이 있는데 _inferred도 있다");
            }
            foreach (var path in BaseSlotPaths)
            {
                var value = GetSlot(s, path);
                bool hasProv = s.Provenance.TryGetValue(path, out var provs) && provs != null && provs.Count > 0;
                if (value == null && hasProv) problems.Add(path + ": null인데 _provenance가 있다");
                if (value != null && !hasProv) problems.Add(path + ": 값이 있는데 _provenance가 없다");
            }
            if (s.Form.Base != null && !BaseShapes.IsBase(s.Form.Base))
                problems.Add($"form.base: 모르는 기본 형상 {s.Form.Base}(가능: {string.Join(", ", BaseShapes.All)}) — 그리지 않음");
            if (s.Form.Base == null && s.Form.BaseVariant != null) problems.Add("form.baseVariant: form.base가 null인데 변형값이 있다");
            if (BaseShapes.IsBase(s.Form.Base)) BaseShapes.Resolve(s.Form.Base, s.Form.BaseVariant, null, problems);
            foreach (var key in s.Provenance.Keys)
                if (Array.IndexOf(SlotPaths, key) < 0 && Array.IndexOf(BaseSlotPaths, key) < 0 && Array.IndexOf(ContourRender.SlotPaths, key) < 0)
                    problems.Add("_provenance에 모르는 경로: " + key);
            return problems;
        }
    }
}
