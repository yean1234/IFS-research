// 소유감 실험 테스트용 합성 spec(참여자 데이터 아님). 예시 EX02.json을 바탕으로 모든 슬롯을 비운 뒤 필요한 값만 넣는다.
// UnityEngine은 Application.streamingAssetsPath만 쓴다(dotnet 스텁에서도 저장소의 StreamingAssets를 가리킨다).
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public static class OwnershipTestSpecs
    {
        public static string ExamplePath(string name) => Path.Combine(Application.streamingAssetsPath, "IFS", "examples", name);

        /// <summary>모든 슬롯 null, _provenance·_unmapped·_unmatched·_alternatives 빔.</summary>
        public static JObject Empty(string sessionId)
        {
            var o = JObject.Parse(File.ReadAllText(ExamplePath("EX02.json"), Encoding.UTF8));
            o["meta"]["sessionId"] = sessionId;
            o["form"]["type"] = null;
            o["form"]["posture"] = null;
            foreach (var k in new[] { "color", "brightness", "saturation", "roughness", "opacity", "erosion" }) o["material"][k] = null;
            foreach (var k in new[] { "size", "distance", "verticalOffset" }) o["layout"][k] = null;
            o["motion"]["type"] = null;
            o["motion"]["speed"] = null;
            o["body"]["part"] = null;
            o["body"]["layer"] = null;
            o["_provenance"] = new JObject();
            o["_unmapped"] = new JArray();
            o["_unmatched"] = new JArray();
            o["_alternatives"] = new JArray();
            o["_negated"] = new JArray();
            o["_inferred"] = new JObject();
            return o;
        }

        /// <summary>슬롯 값과 그 근거(_provenance, 합성 trigger)를 넣는다.</summary>
        public static JObject Slot(this JObject o, string path, JToken value, string trigger = "합성")
        {
            var parts = path.Split('.');
            o[parts[0]][parts[1]] = value;
            ((JObject)o["_provenance"])[path] = new JArray(new JObject
            {
                ["source"] = "explicit_lexicon", ["trigger"] = trigger, ["charSpan"] = new JArray(0, trigger.Length),
                ["rule"] = "synthetic." + trigger,
            });
            return o;
        }

        public static JObject Hsl(this JObject o, double h, double s, double l, string trigger = "합성색") =>
            o.Slot("material.color", new JObject { ["h"] = h, ["s"] = s, ["l"] = l }, trigger);

        /// <summary>_unmapped에 모양어 하나(category = shape).</summary>
        public static JObject ShapeWord(this JObject o, string shape, string trigger, int start)
        {
            ((JArray)o["_unmapped"]).Add(new JObject
            {
                ["lemma"] = trigger, ["category"] = "shape", ["value"] = new JObject { ["shape"] = shape },
                ["reason"] = "no_scene_param",
                ["_provenance"] = new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = trigger,
                    ["charSpan"] = new JArray(start, start + trigger.Length), ["rule"] = "shapeLexicon." + trigger,
                },
            });
            return o;
        }

        public static SceneSpecV2 Parse(this JObject o) => SceneSpecJson.Parse(o.ToString(Formatting.None));

        public static string Write(this JObject o, string dir, string fileName)
        {
            string p = Path.Combine(dir, fileName);
            File.WriteAllText(p, o.ToString(Formatting.Indented).Replace("\r\n", "\n"), new UTF8Encoding(false));
            return p;
        }
    }
}
