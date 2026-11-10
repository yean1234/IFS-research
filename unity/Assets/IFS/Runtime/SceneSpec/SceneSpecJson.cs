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
            return spec;
        }

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
                default: throw new ArgumentException("모르는 슬롯 경로: " + path);
            }
        }

        /// <summary>스키마의 원칙 규칙을 다시 확인한다(버전, 0–1 범위, 값 ⇔ _provenance, _inferred는 빈 슬롯만).
        /// 문제가 있어도 예외를 내지 않고 목록을 돌려준다 — SceneLoader가 경고로 남긴다.</summary>
        public static List<string> Validate(SceneSpecV2 s)
        {
            var problems = new List<string>();
            if (s.Meta.SpecVersion != SceneSpecV2.SupportedSpecVersion)
                problems.Add($"specVersion {s.Meta.SpecVersion} (지원: {SceneSpecV2.SupportedSpecVersion})");
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
            foreach (var key in s.Provenance.Keys)
                if (Array.IndexOf(SlotPaths, key) < 0) problems.Add("_provenance에 모르는 경로: " + key);
            return problems;
        }
    }
}
