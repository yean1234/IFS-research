// 해석된 SceneParams 위에 얹는 덮어쓰기(소유감 실험의 변형본). 원본 spec 파일은 고치지 않는다.
//   Numbers·Categories = SceneParams 키 → 값(SetNumber·SetCategory와 같은 뜻, 0–1 조정 포함)
//   (2.4, G72) layout.proportions.x·y·z = x·y·z 비율의 원값(참여자 조절 화면 값, 0.2–2.0). 렌더러가 셋의 가장 큰 값으로 나누고 0.2–1로 자른다.
//              일부 축만 주면 나머지는 spec 값(spec이 null이면 1.0). 위치·거리 키와 달리 선택 파일 덮어쓰기에 넣을 수 있다.
//   (2.4 선택, G74) form.mistKind = 안개 입자 모양(fog·smoke·dust·cloud). form.type이 mist일 때만 그림에 쓰인다.
//   ShapeModel = 모양 모형 강제(Sphere·Cube·FlatCylinder·Cone). null이면 spec의 모양어 판정을 그대로 쓴다.
//                form.type 덮어쓰기와 별개 필드다. 해석된 form.type이 blob일 때만 쓸 수 있다.
// 덮어쓰기는 참여자 조정이 아니므로 ExperimentRecorder.RecordChange를 타지 않는다(SceneLoader.Load(path, override)).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    public sealed class SceneOverride
    {
        public readonly SortedDictionary<string, double> Numbers = new SortedDictionary<string, double>(StringComparer.Ordinal);
        public readonly SortedDictionary<string, string> Categories = new SortedDictionary<string, string>(StringComparer.Ordinal);
        /// <summary>강제할 모양 모형(ShapeMapping.Models 중 하나). null = 강제하지 않음.</summary>
        public string ShapeModel;

        public bool IsEmpty => Numbers.Count == 0 && Categories.Count == 0 && ShapeModel == null;

        /// <summary>키·값·모형 이름을 확인한다. 모르는 것은 조용히 넘기지 않고 오류 목록으로 돌려준다.</summary>
        public List<string> Validate()
        {
            var errors = new List<string>();
            foreach (var kv in Numbers)
            {
                if (ProportionsRender.IsAxisKey(kv.Key))
                {
                    if (!ProportionsRender.InRawRange(kv.Value)) errors.Add($"{kv.Key}: {kv.Value}가 0.2–2 밖");
                }
                else if (Array.IndexOf(SceneParams.NumericKeys, kv.Key) < 0) errors.Add("수치 키가 아님: " + kv.Key);
                else if (double.IsNaN(kv.Value) || kv.Value < 0 || kv.Value > 1) errors.Add($"{kv.Key}: {kv.Value}가 0–1 밖");
            }
            foreach (var kv in Categories)
            {
                bool contour = ContourRender.Levels.TryGetValue(kv.Key, out var levels);
                bool mistKind = kv.Key == MistKinds.Key;
                if (Array.IndexOf(SceneParams.CategoricalKeys, kv.Key) < 0 && kv.Key != SceneParams.BaseKey && !contour && !mistKind) errors.Add("범주 키가 아님: " + kv.Key);
                else if (kv.Value == null) errors.Add(kv.Key + ": 값이 null");
                // (2.4 선택, G74) 안개 입자 모양(fog·smoke·dust·cloud). form.type이 mist일 때만 그림에 쓰인다
                else if (mistKind && !MistKinds.IsKind(kv.Value))
                    errors.Add($"모르는 {kv.Key}: {kv.Value}(가능: {string.Join(", ", MistKinds.Values)})");
                // (2.3) 윤곽·발광 범주 키(docs/scene-spec-mapping.md 8.4절 6번). 챗봇은 아직 보내지 않는다. "none"은 발광 끔
                else if (contour && Array.IndexOf(levels, kv.Value) < 0)
                    errors.Add($"모르는 {kv.Key}: {kv.Value}(가능: {string.Join(", ", levels)})");
                else if (kv.Key == SceneParams.BaseKey && kv.Value != SceneParams.NoBase && !BaseShapes.IsBase(kv.Value))
                    errors.Add($"모르는 기본 형상: {kv.Value}(가능: {string.Join(", ", BaseShapes.All)}, {SceneParams.NoBase})");
                else if (kv.Key == "form.type" && Array.IndexOf(SceneParams.FormTypes, kv.Value) < 0) errors.Add("모르는 형태: " + kv.Value);
                else if (kv.Key == "motion.type" && !MotionGroups.ByType.ContainsKey(kv.Value)) errors.Add("모르는 motion.type: " + kv.Value);
            }
            if (ShapeModel != null && Array.IndexOf(ShapeMapping.Models, ShapeModel) < 0) errors.Add("모르는 모양 모형: " + ShapeModel);
            return errors;
        }

        /// <summary>p에 덮어쓰기를 적용한다(기록 없음). 바뀐 키 목록을 돌려준다.</summary>
        public List<string> ApplyTo(SceneParams p)
        {
            var changed = new List<string>();
            foreach (var kv in Numbers) if (p.SetNumber(kv.Key, kv.Value)) changed.Add(kv.Key);
            foreach (var kv in Categories) if (p.SetCategory(kv.Key, kv.Value)) changed.Add(kv.Key);
            return changed;
        }

        /// <summary>manifest의 overrides 객체(키 이름순).</summary>
        public JObject OverridesJson()
        {
            var o = new JObject();
            foreach (var key in Numbers.Keys.Concat(Categories.Keys).OrderBy(k => k, StringComparer.Ordinal))
                o[key] = Numbers.TryGetValue(key, out var d) ? (JToken)d : Categories[key];
            return o;
        }

        public override string ToString()
        {
            var parts = Numbers.Select(kv => kv.Key + "=" + ExperimentRecorder.FormatNumber(kv.Value))
                .Concat(Categories.Select(kv => kv.Key + "=" + kv.Value)).ToList();
            if (ShapeModel != null) parts.Add("shapeModel=" + ShapeModel);
            return parts.Count == 0 ? "(없음)" : string.Join(", ", parts);
        }
    }
}
