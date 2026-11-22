// EditMode 테스트(Unity 전용): 변형 없이 로드한 결과가 변형 경로를 넣기 전과 같은가.
// Golden/loader_no_variant.golden.txt는 변형 경로를 넣기 전 SceneLoader(2026-11-17, 커밋 1e0a093)로 만든 지문이다.
// 지문 = 적용값·기본값 목록·notes·모양 판정·계층(이름·변환)·렌더러·머티리얼 프로퍼티·움직임 묶음·initialScene.json·events.csv.
// spec은 StreamingAssets 예시 4개 + EX02에 합성 값을 넣은 3개(참여자 데이터 아님).
// 지문을 다시 만들 때만: 환경 변수 IFS_WRITE_LOADER_GOLDEN=1로 Unity -runTests를 돌린다(바꾼 이유를 기록할 것).
// 2026-11-23 다시 만듦: 형상별 렌더 경로(X66) — GOLD-mist 항목만 바뀜(안개 셰이더·대리 메시·프리셋 기본값 notes). 나머지 6개 spec은 그대로.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class LoaderNoVariantGoldenTests
    {
        public const string GoldenRelativePath = "IFS/Tests/Editor/UnityOnly/Golden/loader_no_variant.golden.txt";
        static readonly CultureInfo Inv = CultureInfo.InvariantCulture;

        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-golden-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        public static string GoldenPath => Path.Combine(Application.dataPath, GoldenRelativePath);

        /// <summary>지문에 쓰는 spec 경로(이름순). 합성 spec은 dir에 쓴다.</summary>
        public static List<(string name, string path)> FingerprintSpecs(string dir)
        {
            string ex = Path.Combine(Application.streamingAssetsPath, "IFS", "examples");
            var list = new List<(string, string)>
            {
                ("EX01", Path.Combine(ex, "EX01.json")),
                ("EX02", Path.Combine(ex, "EX02.json")),
                ("EX01.v1", Path.Combine(ex, "v1", "EX01.v1.json")),
                ("EX03.v1", Path.Combine(ex, "v1", "EX03.v1.json")),
            };
            JObject Base(string id)
            {
                var o = JObject.Parse(File.ReadAllText(Path.Combine(ex, "EX02.json")));
                o["meta"]["sessionId"] = id;
                return o;
            }
            void ShapeWord(JObject o, string shape, string trigger, int start)
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
            }
            void Slot(JObject o, string path, JToken value, string trigger)
            {
                var parts = path.Split('.');
                o[parts[0]][parts[1]] = value;
                ((JObject)o["_provenance"])[path] = new JArray(new JObject
                {
                    ["source"] = "explicit_lexicon", ["trigger"] = trigger, ["charSpan"] = new JArray(0, trigger.Length),
                    ["rule"] = "synthetic." + trigger,
                });
            }

            var square = Base("GOLD-square");
            ShapeWord(square, "square", "네모", 12);
            var mist = Base("GOLD-mist");
            Slot(mist, "form.type", "mist", "안개");
            Slot(mist, "material.opacity", 0.6, "흐릿");
            Slot(mist, "motion.type", "swaying", "흔들");
            Slot(mist, "material.color", new JObject { ["h"] = 0.6, ["s"] = 0.5, ["l"] = 0.4 }, "파란");
            var round = Base("GOLD-round");
            ShapeWord(round, "round", "동그란", 3);
            Slot(round, "motion.type", "rotating", "돌아");
            Slot(round, "layout.size", 0.8, "커다란");
            foreach (var (n, o) in new[] { ("GOLD-square", square), ("GOLD-mist", mist), ("GOLD-round", round) })
            {
                string p = Path.Combine(dir, n + ".json");
                File.WriteAllText(p, o.ToString(Formatting.Indented).Replace("\r\n", "\n"), new UTF8Encoding(false));
                list.Add((n, p));
            }
            return list;
        }

        public static SceneLoader NewLoader(string recordRoot, out GameObject go)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            go = new GameObject("SceneLoader (golden)");
            var loader = go.AddComponent<SceneLoader>();
            var so = new SerializedObject(loader);
            so.FindProperty("record").boolValue = true;
            so.FindProperty("recordRoot").stringValue = recordRoot;
            so.FindProperty("loadOnStart").boolValue = false;
            so.FindProperty("autoSaveFinalOnDestroy").boolValue = false;
            so.ApplyModifiedPropertiesWithoutUndo();
            return loader;
        }

        /// <summary>spec마다 새 씬·새 로더로 load를 부르고 지문을 이어 붙인다.</summary>
        public static string Fingerprint(string tmpDir, Func<SceneLoader, string, bool> load)
        {
            var sb = new StringBuilder();
            int i = 0;
            foreach (var (name, path) in FingerprintSpecs(tmpDir))
            {
                string root = Path.Combine(tmpDir, "sessions" + (i++));
                var loader = NewLoader(root, out var go);
                try
                {
                    sb.Append("=== ").Append(name).Append('\n');
                    bool ok = load(loader, path);
                    sb.Append("loaded: ").Append(ok).Append('\n');
                    if (ok) Describe(loader, sb);
                    loader.Unload();   // 기록 파일을 닫는다
                    if (ok) DescribeRecords(root, sb);
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(go);
                }
            }
            return sb.ToString();
        }

        static void Describe(SceneLoader l, StringBuilder sb)
        {
            sb.Append("params: ").Append(JObject.FromObject(l.InitialParams.ToRecord()).ToString(Formatting.None)).Append('\n');
            sb.Append("current: ").Append(JObject.FromObject(l.CurrentParams.ToRecord()).ToString(Formatting.None)).Append('\n');
            sb.Append("defaultsUsed: ").Append(string.Join(",", l.InitialParams.DefaultsUsed)).Append('\n');
            sb.Append("inferredUsed: ").Append(string.Join(",", l.InitialParams.InferredUsed)).Append('\n');
            sb.Append("shape: ").Append(l.Shape.ToJson().ToString(Formatting.None)).Append('\n');
            sb.Append("showingShapeModel: ").Append(l.ShowingShapeModel).Append('\n');
            sb.Append("ownedMaterials: ").Append(l.OwnedMaterialCount).Append('\n');
            sb.Append("notes:\n");
            foreach (var n in l.Notes) sb.Append("  - ").Append(n).Append('\n');
            sb.Append("hierarchy:\n");
            Walk(l.Root.transform, 1, sb);
        }

        static string F(float v) => v.ToString("F5", Inv);
        static string V(Vector3 v) => $"({F(v.x)},{F(v.y)},{F(v.z)})";
        static string Q(Quaternion q) => $"({F(q.x)},{F(q.y)},{F(q.z)},{F(q.w)})";
        static string C(Color c) => $"({F(c.r)},{F(c.g)},{F(c.b)},{F(c.a)})";

        static readonly string[] FloatProps =
        {
            "_Brightness", "_Roughness", "_Opacity", "_Erosion", "_Lumpiness", "_NoiseScale", "_Fuzz", "_Density",
            "_ShellOpen", "_Displacement", "_Seed", "_Glossiness", "_Smoothness",
        };

        static readonly string[] ColorProps = { "_BaseColor", "_Color", "_EmissionColor" };

        static void Walk(Transform t, int depth, StringBuilder sb)
        {
            string ind = new string(' ', depth * 2);
            sb.Append(ind).Append(t.name).Append(" active=").Append(t.gameObject.activeSelf)
              .Append(" pos=").Append(V(t.localPosition)).Append(" rot=").Append(Q(t.localRotation))
              .Append(" scale=").Append(V(t.localScale)).Append('\n');
            var mf = t.GetComponent<MeshFilter>();
            if (mf != null) sb.Append(ind).Append("  mesh=").Append(mf.sharedMesh != null ? mf.sharedMesh.name : "null")
                               .Append(" verts=").Append(mf.sharedMesh != null ? mf.sharedMesh.vertexCount : 0).Append('\n');
            var r = t.GetComponent<Renderer>();
            if (r != null)
            {
                sb.Append(ind).Append("  renderer shadow=").Append(r.shadowCastingMode).Append('\n');
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) { sb.Append(ind).Append("    mat=null\n"); continue; }
                    sb.Append(ind).Append("    mat shader=").Append(m.shader.name).Append(" queue=").Append(m.renderQueue);
                    foreach (var p in ColorProps) if (m.HasProperty(p)) sb.Append(' ').Append(p).Append('=').Append(C(m.GetColor(p)));
                    foreach (var p in FloatProps) if (m.HasProperty(p)) sb.Append(' ').Append(p).Append('=').Append(F(m.GetFloat(p)));
                    sb.Append(" keywords=").Append(string.Join("|", m.shaderKeywords.OrderBy(k => k, StringComparer.Ordinal)));
                    sb.Append('\n');
                }
            }
            var col = t.GetComponent<Collider>();
            if (col != null) sb.Append(ind).Append("  collider=").Append(col.GetType().Name).Append('\n');
            var motion = t.GetComponent<SpecMotion>();
            if (motion != null) sb.Append(ind).Append("  motion group=").Append(motion.Group).Append('\n');
            for (int i = 0; i < t.childCount; i++) Walk(t.GetChild(i), depth + 1, sb);
        }

        static void DescribeRecords(string root, StringBuilder sb)
        {
            if (!Directory.Exists(root)) { sb.Append("records: none\n"); return; }
            foreach (var dir in Directory.GetDirectories(root).OrderBy(d => d, StringComparer.Ordinal))
            {
                string init = Path.Combine(dir, "initialScene.json");
                if (File.Exists(init))
                {
                    var o = JObject.Parse(File.ReadAllText(init));
                    o.Remove("recordedAtUtc");   // 시각
                    o.Remove("specPath");        // 임시 폴더 경로
                    sb.Append("initialScene: ").Append(o.ToString(Formatting.None)).Append('\n');
                }
                string ev = Path.Combine(dir, "events.csv");
                if (File.Exists(ev)) sb.Append("events: ").Append(File.ReadAllText(ev).Replace("\r", "\\r").Replace("\n", "\\n")).Append('\n');
                sb.Append("files: ").Append(string.Join(",", Directory.GetFiles(dir).Select(Path.GetFileName).OrderBy(f => f, StringComparer.Ordinal))).Append('\n');
            }
        }

        public static void AssertMatchesGolden(string actual, string label)
        {
            if (Environment.GetEnvironmentVariable("IFS_WRITE_LOADER_GOLDEN") == "1")
            {
                Directory.CreateDirectory(Path.GetDirectoryName(GoldenPath));
                File.WriteAllText(GoldenPath, actual, new UTF8Encoding(false));
                Assert.Pass("golden을 새로 썼습니다: " + GoldenPath);
            }
            Assert.That(File.Exists(GoldenPath), Is.True, "golden 파일이 없습니다: " + GoldenPath);
            string expected = File.ReadAllText(GoldenPath, Encoding.UTF8).Replace("\r\n", "\n");
            if (expected == actual) return;
            var e = expected.Split('\n');
            var a = actual.Split('\n');
            int i = 0;
            while (i < Math.Min(e.Length, a.Length) && e[i] == a[i]) i++;
            Assert.Fail($"{label}: golden과 {i + 1}번째 줄부터 다릅니다.\n기대: {(i < e.Length ? e[i] : "(끝)")}\n실제: {(i < a.Length ? a[i] : "(끝)")}");
        }

        [Test]
        public void Load_without_variant_matches_the_golden_fingerprint()
        {
            string actual = Fingerprint(_tmp, (l, p) => l.Load(p));
            AssertMatchesGolden(actual, "Load(path)");
        }
    }
}
