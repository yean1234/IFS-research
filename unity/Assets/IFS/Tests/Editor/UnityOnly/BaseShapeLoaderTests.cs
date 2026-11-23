// EditMode 테스트(Unity 전용): 기본 형상(form.base, D6)을 SceneLoader가 실제로 그리는지 — 렌더 경로·메시·재질 슬롯(G22)·
// 조절 중 형태 바꾸기·덮어쓰기, 그리고 배치 러너가 선택 파일의 form.base를 받아 적용하는지. spec은 합성(BaseShapeTests.Spec22).
using System;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.EditorTools;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class BaseShapeLoaderTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-base-test-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        string Write(string name, string json)
        {
            string p = Path.Combine(_tmp, name + ".json");
            File.WriteAllText(p, json, new UTF8Encoding(false));
            return p;
        }

        SceneLoader NewLoader(out GameObject go)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            go = new GameObject("SceneLoader (base test)");
            var loader = go.AddComponent<SceneLoader>();
            var so = new SerializedObject(loader);
            so.FindProperty("record").boolValue = false;
            so.FindProperty("loadOnStart").boolValue = false;
            so.FindProperty("autoSaveFinalOnDestroy").boolValue = false;
            so.ApplyModifiedPropertiesWithoutUndo();
            return loader;
        }

        [Test]
        public void Each_base_shape_is_drawn_with_its_mesh_and_ifs_shader()
        {
            foreach (var shape in BaseShapes.All.Where(BaseShapeMesh.Supports))
            {
                var loader = NewLoader(out var go);
                try
                {
                    Assert.That(loader.Load(Write(shape, BaseShapeTests.Spec22(null, shape))), Is.True, shape);
                    Assert.That(loader.RenderPath, Is.EqualTo("base:" + shape));
                    Assert.That(loader.RenderPlan.BaseStatus, Is.EqualTo("applied"));
                    var mf = loader.Root.GetComponentInChildren<MeshFilter>();
                    Assert.That(mf.sharedMesh.name, Does.StartWith("IFS Base " + shape + "/"));
                    Assert.That(mf.sharedMesh.triangles.Length / 3, Is.LessThanOrEqualTo(BaseShapeMesh.MaxTriangles));
                    var mat = loader.Root.GetComponentInChildren<MeshRenderer>().sharedMaterial;
                    Assert.That(FormRenderResources.IsLegacyIfs(mat), Is.True, "IFS 셰이더(기존 재질 재사용)");
                    Assert.That(mat.GetFloat("_Displacement"), Is.EqualTo(0f), "정점 변위 0(윤곽 유지)");
                    Assert.That(loader.Notes.Any(n => n.Contains("form.base=" + shape) && n.Contains(BaseShapeMesh.RuleFor(shape))), Is.True);
                }
                finally { UnityEngine.Object.DestroyImmediate(go); }
            }
        }

        [Test]
        public void Material_slots_and_size_reach_the_base_shape()
        {
            var loader = NewLoader(out var go);
            try
            {
                Assert.That(loader.Load(Write("c", BaseShapeTests.Spec22(null, "container"))), Is.True);
                var r = loader.Root.GetComponentInChildren<MeshRenderer>();
                var c0 = r.sharedMaterial.GetColor("_BaseColor");
                Assert.That(loader.SetNumber("material.color.s", 0.6f) && loader.SetNumber("material.color.h", 0.33f), Is.True);
                Assert.That(r.sharedMaterial.GetColor("_BaseColor"), Is.Not.EqualTo(c0), "색");
                float b0 = r.sharedMaterial.GetFloat("_Brightness");
                loader.SetNumber("material.brightness", 0.75f);
                Assert.That(r.sharedMaterial.GetFloat("_Brightness"), Is.Not.EqualTo(b0), "밝기");
                float g0 = r.sharedMaterial.GetFloat("_Roughness");
                loader.SetNumber("material.roughness", 0.9f);
                Assert.That(r.sharedMaterial.GetFloat("_Roughness"), Is.Not.EqualTo(g0), "질감");
                var s0 = loader.Root.GetComponentInChildren<MeshRenderer>().transform.lossyScale;
                loader.SetNumber("layout.size", 0.7f);
                Assert.That(loader.Root.GetComponentInChildren<MeshRenderer>().transform.lossyScale.x, Is.GreaterThan(s0.x * 1.5f), "크기");
                loader.SetNumber("material.opacity", 0.6f);
                r = loader.Root.GetComponentInChildren<MeshRenderer>();
                Assert.That(r.sharedMaterial.shader, Is.SameAs(FormRenderResources.Fade), "투명도 < 0.99 → Fade");
                Assert.That(loader.RenderPath, Is.EqualTo("base:container"));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void Adjusting_form_switches_between_base_and_form_type_without_leaking_materials()
        {
            var loader = NewLoader(out var go);
            try
            {
                Assert.That(loader.Load(Write("l", BaseShapeTests.Spec22(null, "container"))), Is.True);
                int owned = loader.OwnedMaterialCount;
                Assert.That(loader.SetCategory("form.type", "mist"), Is.True);
                Assert.That(loader.RenderPath, Is.Not.EqualTo("base:container"));
                Assert.That(loader.RenderPlan.BaseStatus, Is.EqualTo("not_applied_form"));
                Assert.That(loader.SetCategory("form.type", "blob"), Is.True);
                Assert.That(loader.RenderPath, Is.EqualTo("base:container"));
                Assert.That(loader.SetCategory("form.base", "none"), Is.True);
                Assert.That(loader.RenderPath, Is.EqualTo("blob"));
                foreach (var other in BaseShapes.All.Where(BaseShapeMesh.Supports))
                {
                    loader.SetCategory("form.base", other);
                    Assert.That(loader.RenderPath, Is.EqualTo("base:" + other));
                }
                Assert.That(loader.OwnedMaterialCount, Is.EqualTo(owned), "형상을 바꿀 때 이전 머티리얼 사본을 지움");
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void Override_draws_a_base_on_a_21_spec()
        {
            var loader = NewLoader(out var go);
            try
            {
                var ov = SceneOverrideJson.Parse("{\"form.base\":\"container\"}", out var errors);
                Assert.That(errors, Is.Empty);
                Assert.That(loader.Load(OwnershipTestSpecs.ExamplePath("EX02.json"), ov), Is.True);
                Assert.That(loader.RenderPath, Is.EqualTo("base:container"));
                Assert.That(loader.CurrentParams.ToRecord()["form.base"], Is.EqualTo("container"));
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        [Test]
        public void Placement_runner_applies_form_base_from_the_selection_file()
        {
            string spec = Write("spec", BaseShapeTests.Spec22(null, null));
            var sel = new JObject
            {
                ["formatVersion"] = "ifs-selection/0.2",
                ["specSha256"] = OwnershipManifest.Sha256OfFile(spec),
                ["finalOverrides"] = new JObject { ["form.base"] = "container" },
                ["selection"] = new JObject { ["selectedCandidateId"] = null, ["none"] = false, ["skipped"] = true },
                ["colorChanged"] = false,
                ["sources"] = new JObject { ["form.type"] = "default", ["form.base"] = "edited" },
            };
            string selPath = Path.Combine(_tmp, "selection.json");
            File.WriteAllText(selPath, sel.ToString(), new UTF8Encoding(false));
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            try
            {
                runner.SetRecordRoot(Path.Combine(_tmp, "records"));
                runner.BeginAuto(new PlacementAutoScript(), PlacementTests.ShortConfig("place"));
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = spec;
                runner.SelectionPathText = selPath;
                Assert.That(runner.Check(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.StartSession(), Is.True, string.Join("; ", runner.Errors));
                Assert.That(runner.Loader.CurrentParams.GetCategory("form.base"), Is.EqualTo("container"));
                Assert.That(runner.Loader.RenderPath, Is.EqualTo("base:container"));
                for (int i = 0; i < 200000 && runner.Stage != PlacementRunnerStage.Done; i++) runner.Tick(0.02);
                Assert.That(runner.LastCompleted, Is.True);
                var m = OwnershipVariantTests.ParseNoDates(File.ReadAllText(Path.Combine(runner.LastRecordDirectory, "manifest.json")));
                Assert.That((string)m["appliedOverrides"]["form.base"], Is.EqualTo("container"));
                Assert.That((string)m["selection"]["sources"]["form.base"], Is.EqualTo("edited"));
            }
            finally
            {
                runner.ResetForNext();
            }
        }
    }
}
