// EditMode 테스트(Unity 전용): 모양 모형 팩토리·프리팹 에셋·SceneLoader 적용과 기록(docs/shape-mapping.md).
// 테스트용 spec은 예시 EX02.json에 합성 모양어 항목을 더해 임시 폴더에 쓴다(참여자 데이터 아님).
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class ShapeModelTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-shape-test-" + System.Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        static void AssertUnitRootWithMeshChild(GameObject root, string model)
        {
            Assert.That(root.transform.localScale, Is.EqualTo(Vector3.one), model + " 루트 크기 1");
            Assert.That(root.GetComponent<Renderer>(), Is.Null, model + " 루트에는 렌더러가 없다");
            Assert.That(root.GetComponent<MeshFilter>(), Is.Null, model + " 루트에는 메시가 없다");
            Assert.That(root.transform.childCount, Is.EqualTo(1), model);
            var child = root.transform.GetChild(0);
            Assert.That(child.name, Is.EqualTo(ShapeModelFactory.MeshChildName));
            Assert.That(child.GetComponent<MeshFilter>().sharedMesh, Is.Not.Null, model);
            Assert.That(child.GetComponent<MeshRenderer>(), Is.Not.Null, model);
            var want = model == "FlatCylinder" ? new Vector3(1f, 0.2f, 1f) : Vector3.one;
            Assert.That(child.localScale, Is.EqualTo(want), model + " 배율은 자식에만");
        }

        [Test]
        public void Factory_models_have_unit_root_and_scaling_on_the_child()
        {
            var expectedMesh = new System.Collections.Generic.Dictionary<string, string>
            {
                { "Sphere", "Sphere" }, { "Cube", "Cube" }, { "FlatCylinder", "Cylinder" }, { "Cone", "IFS Cone" },
            };
            foreach (var model in ShapeMapping.Models)
            {
                var root = ShapeModelFactory.Create(model, null);
                try
                {
                    AssertUnitRootWithMeshChild(root, model);
                    var mesh = root.transform.GetChild(0).GetComponent<MeshFilter>().sharedMesh;
                    Assert.That(mesh.name, Is.EqualTo(expectedMesh[model]));
                    if (model == "Cone")
                    {
                        Assert.That(mesh.bounds.size.x, Is.EqualTo(1f).Within(1e-5f));
                        Assert.That(mesh.bounds.size.y, Is.EqualTo(1f).Within(1e-5f));
                        Assert.That(mesh.bounds.center.y, Is.EqualTo(0f).Within(1e-5f));
                        Assert.That(mesh.vertexCount, Is.EqualTo(ConeMesh.VertexCount(ConeMesh.DefaultSegments)));
                    }
                }
                finally
                {
                    if (model == "Cone") Object.DestroyImmediate(root.transform.GetChild(0).GetComponent<MeshFilter>().sharedMesh);
                    Object.DestroyImmediate(root);
                }
            }
            Assert.That(ShapeModelFactory.Create("Torus", null), Is.Null, "표에 없는 모형은 만들지 않는다");
        }

        [Test]
        public void Shape_prefab_assets_have_unit_root_ifs_material_and_scaling_on_the_child()
        {
            var table = ShapePrefabMenu.LoadShapePrefabs();
            Assert.That(table.Select(t => t.shape), Is.EqualTo(new[] { "round", "square", "flat", "pointed" }));
            var cone = AssetDatabase.LoadAssetAtPath<Mesh>(ShapePrefabMenu.ConeMeshPath);
            Assert.That(cone, Is.Not.Null, ShapePrefabMenu.ConeMeshPath + " — 메뉴 IFS ▸ Create Shape Prefabs를 실행했는가");
            foreach (var t in table)
            {
                string model = ShapeMapping.ModelFor(t.shape);
                Assert.That(t.prefab, Is.Not.Null, ShapePrefabMenu.PrefabPath(model));
                AssertUnitRootWithMeshChild(t.prefab, model);
                var child = t.prefab.transform.GetChild(0);
                var mat = child.GetComponent<MeshRenderer>().sharedMaterial;
                Assert.That(mat, Is.Not.Null, model);
                Assert.That(mat.shader.name, Is.EqualTo("IFS/SceneSpec Opaque"), model);
                Assert.That(mat.GetFloat("_Displacement"), Is.EqualTo(0f), model);
                if (model == "Cone") Assert.That(child.GetComponent<MeshFilter>().sharedMesh, Is.SameAs(cone));
            }
        }

        // ── SceneLoader ────────────────────────────────────────────────────
        string WriteSpec(string name, string formType, params (string shape, string trigger, int start)[] words)
        {
            var o = JObject.Parse(File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX02.json")));
            o["form"]["type"] = formType;
            o["meta"]["sessionId"] = "shape-test-" + name;
            var unmapped = (JArray)o["_unmapped"];
            foreach (var (shape, trigger, start) in words)
                unmapped.Add(new JObject
                {
                    ["lemma"] = trigger, ["category"] = "shape", ["value"] = new JObject { ["shape"] = shape },
                    ["reason"] = "no_scene_param",
                    ["_provenance"] = new JObject
                    {
                        ["source"] = "explicit_lexicon", ["trigger"] = trigger,
                        ["charSpan"] = new JArray(start, start + trigger.Length), ["rule"] = "shapeLexicon." + trigger,
                    },
                });
            string path = Path.Combine(_tmp, name + ".json");
            File.WriteAllText(path, o.ToString());
            return path;
        }

        SceneLoader NewLoader(bool record, out GameObject go)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            go = new GameObject("SceneLoader (shape test)");
            var loader = go.AddComponent<SceneLoader>();
            var so = new SerializedObject(loader);
            so.FindProperty("record").boolValue = record;
            so.FindProperty("recordRoot").stringValue = Path.Combine(_tmp, "sessions");
            so.FindProperty("loadOnStart").boolValue = false;
            so.FindProperty("autoSaveFinalOnDestroy").boolValue = false;
            so.ApplyModifiedPropertiesWithoutUndo();
            return loader;
        }

        static Renderer[] ModelRenderers(SceneLoader l) => l.Root.GetComponentsInChildren<Renderer>();

        [Test]
        public void Mapped_shape_builds_the_shape_model_and_records_it()
        {
            var loader = NewLoader(true, out var go);
            try
            {
                loader.ConfigureShapePrefabs(new ShapePrefab[0]);   // 프리팹 없음 → 코드로 같은 형상 + 경고
                Assert.That(loader.Load(WriteSpec("square", null, ("square", "네모", 12))), Is.True);
                Assert.That(loader.Shape.Status, Is.EqualTo("applied"));
                Assert.That(loader.Shape.Model, Is.EqualTo("Cube"));
                Assert.That(loader.Shape.ViaPrefab, Is.False);
                Assert.That(loader.ShowingShapeModel, Is.True);
                Assert.That(loader.Notes.Any(n => n.Contains("프리팹이 연결되지 않아")), Is.True, string.Join("\n", loader.Notes));
                var r = ModelRenderers(loader).Single();
                Assert.That(r.GetComponent<MeshFilter>().sharedMesh.name, Is.EqualTo("Cube"));
                Assert.That(r.sharedMaterial.shader.name, Is.EqualTo("IFS/SceneSpec Opaque"), "IFS 셰이더로 색·밝기·침식 반영");
                Assert.That(r.sharedMaterial.GetFloat("_Displacement"), Is.EqualTo(0f), "모양 모형은 정점 변위 0");
                Assert.That(r.sharedMaterial.GetFloat("_Lumpiness"), Is.EqualTo(0f));

                var initial = JObject.Parse(File.ReadAllText(Path.Combine(loader.Recorder.Directory, "initialScene.json")));
                Assert.That(initial["shape"]["status"].Value<string>(), Is.EqualTo("applied"));
                Assert.That(initial["shape"]["model"].Value<string>(), Is.EqualTo("Cube"));
                Assert.That(initial["shape"]["viaPrefab"].Value<bool>(), Is.False);
                Assert.That(initial["shape"]["words"][0]["trigger"].Value<string>(), Is.EqualTo("네모"));

                // 모양어는 수치·범주 적용값을 바꾸지 않는다(모형만 바뀐다)
                var plain = SceneParams.FromSpec(SceneSpecJson.Load(WriteSpec("plain", null)), new SceneDefaults());
                Assert.That(JToken.DeepEquals(JObject.FromObject(plain.ToRecord()), JObject.FromObject(loader.InitialParams.ToRecord())), Is.True);

                // 프리팹을 연결하면 프리팹으로 만든다
                loader.ConfigureShapePrefabs(ShapePrefabMenu.LoadShapePrefabs());
                Assert.That(loader.Load(WriteSpec("pointed", "blob", ("pointed", "뾰족", 3))), Is.True);
                Assert.That(loader.Shape.Model, Is.EqualTo("Cone"));
                Assert.That(loader.Shape.ViaPrefab, Is.True);
                Assert.That(ModelRenderers(loader).Single().GetComponent<MeshFilter>().sharedMesh,
                    Is.SameAs(AssetDatabase.LoadAssetAtPath<Mesh>(ShapePrefabMenu.ConeMeshPath)));
                Assert.That(ModelRenderers(loader).Single().sharedMaterial.GetFloat("_Displacement"), Is.EqualTo(0f));
            }
            finally
            {
                loader.Unload();
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Unmapped_or_form_blocked_words_keep_the_default_model_and_are_recorded()
        {
            var loader = NewLoader(false, out var go);
            try
            {
                Assert.That(loader.Load(WriteSpec("thread", null, ("thread", "실", 2), ("edge", "가장자리", 9))), Is.True);
                Assert.That(loader.Shape.Status, Is.EqualTo("unmapped_shape"));
                Assert.That(loader.Shape.Model, Is.Null);
                Assert.That(loader.ShowingShapeModel, Is.False);
                var r = ModelRenderers(loader).Single();
                Assert.That(r.GetComponent<MeshFilter>().sharedMesh.name, Is.EqualTo("IFS IcoSphere"), "모양어 없이 만들던 기본 모형 그대로");
                Assert.That(r.sharedMaterial.GetFloat("_Displacement"), Is.EqualTo(1f), "기본 모형의 변위는 그대로");
                Assert.That(loader.Notes.Count(n => n.Contains("unmapped_shape")), Is.EqualTo(2), string.Join("\n", loader.Notes));
                Assert.That(loader.Notes.Any(n => n.Contains("shape-test-thread") && n.Contains("'실'")), Is.True);

                Assert.That(loader.Load(WriteSpec("mist", "mist", ("square", "네모", 12))), Is.True);
                Assert.That(loader.Shape.Status, Is.EqualTo("not_applied_form"));
                Assert.That(loader.ShowingShapeModel, Is.False);
                Assert.That(loader.Root.GetComponentInChildren<MeshFilter>().sharedMesh.name, Is.EqualTo("IFS IcoSphere"));
                Assert.That(loader.Notes.Any(n => n.Contains("not_applied_form")), Is.True);
            }
            finally
            {
                loader.Unload();
                Object.DestroyImmediate(go);
            }
        }

        [Test]
        public void Changing_form_type_shows_that_form_and_returning_restores_the_shape_model()
        {
            var loader = NewLoader(false, out var go);
            try
            {
                loader.ConfigureShapePrefabs(ShapePrefabMenu.LoadShapePrefabs());
                Assert.That(loader.Load(WriteSpec("flat", null, ("flat", "납작", 4))), Is.True);
                Assert.That(loader.ShowingShapeModel, Is.True);
                Assert.That(loader.Root.GetComponentInChildren<MeshFilter>().transform.localScale, Is.EqualTo(new Vector3(1f, 0.2f, 1f)));
                int mats = loader.OwnedMaterialCount;
                Assert.That(loader.SetCategory("form.type", "shell"), Is.True);
                Assert.That(loader.ShowingShapeModel, Is.False);
                Assert.That(loader.SetCategory("form.type", "blob"), Is.True);   // 처음 값(null → 기본 blob)으로 돌아옴
                Assert.That(loader.ShowingShapeModel, Is.True);
                Assert.That(loader.OwnedMaterialCount, Is.EqualTo(mats), "머티리얼 사본이 쌓이지 않는다");
            }
            finally
            {
                loader.Unload();
                Object.DestroyImmediate(go);
            }
        }
    }
}
