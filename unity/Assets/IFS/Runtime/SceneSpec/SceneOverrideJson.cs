// 덮어쓰기 목록 JSON → SceneOverride. WebGL 미리보기(PreviewBridge.ApplyOverridesJson)가 브라우저에서 받은 문자열을 읽는다.
// 형식은 SceneOverride.OverridesJson()(소유감 실험 manifest의 overrides)과 같은 평평한 객체에 모양 모형 키 하나를 더한 것이다.
//   { "material.brightness": 0.7, "form.type": "mist", "shapeModel": "Cube" }
//   숫자 값 = 수치 키(SceneParams.NumericKeys, 0–1), 문자열 값 = 범주 키(SceneParams.CategoricalKeys, form.base,
//   (2.3) form.roundness·form.aspect·material.emission — 서수 단계 이름, "none"은 발광 끔),
//   "shapeModel" = 모양 모형 강제(ShapeMapping.Models). 빈 문자열·{} = 덮어쓰기 없음.
// 모르는 키·0–1 밖 값·null·다른 형식은 조용히 넘기지 않고 오류 목록으로 돌려준다(SceneOverride.Validate와 같은 검사).
// UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec
{
    public static class SceneOverrideJson
    {
        public const string ShapeModelKey = "shapeModel";

        /// <summary>JSON 문자열을 읽는다. 오류가 하나라도 있으면 null을 돌려주고 errors에 이유를 담는다.</summary>
        public static SceneOverride Parse(string json, out List<string> errors)
        {
            errors = new List<string>();
            var o = new SceneOverride();
            if (string.IsNullOrWhiteSpace(json)) return o;
            JToken root;
            try
            {
                using var reader = new JsonTextReader(new System.IO.StringReader(json)) { DateParseHandling = DateParseHandling.None, FloatParseHandling = FloatParseHandling.Double };
                root = JToken.ReadFrom(reader);
                if (reader.Read()) throw new JsonReaderException("JSON 뒤에 남은 내용이 있음");
            }
            catch (JsonException e)
            {
                errors.Add("JSON을 읽지 못함: " + e.Message);
                return null;
            }
            if (root is not JObject obj)
            {
                errors.Add("덮어쓰기는 JSON 객체여야 함(지금 " + root.Type + ")");
                return null;
            }
            foreach (var prop in obj.Properties())
            {
                var v = prop.Value;
                if (prop.Name == ShapeModelKey)
                {
                    if (v.Type == JTokenType.String) o.ShapeModel = (string)v;
                    else errors.Add(ShapeModelKey + ": 문자열이어야 함(지금 " + v.Type + ")");
                    continue;
                }
                switch (v.Type)
                {
                    case JTokenType.Integer:
                    case JTokenType.Float:
                        o.Numbers[prop.Name] = v.Value<double>();
                        break;
                    case JTokenType.String:
                        o.Categories[prop.Name] = (string)v;
                        break;
                    default:
                        errors.Add(prop.Name + ": 숫자나 문자열이어야 함(지금 " + v.Type + ")");
                        break;
                }
            }
            errors.AddRange(o.Validate());
            return errors.Count == 0 ? o : null;
        }
    }
}
