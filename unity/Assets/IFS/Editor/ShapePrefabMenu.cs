// 메뉴 IFS ▸ Create Shape Prefabs — 모양 모형 프리팹 4개를 만들고 SceneLoader에 연결한다(docs/shape-mapping.md).
//   Assets/Prefabs/Shapes/ 에 Sphere · Cube · FlatCylinder · Cone 프리팹, 원뿔 메시(Cone.asset), IFS 셰이더 머티리얼(ShapeIFS.mat).
//   프리팹 루트 = 빈 GameObject(크기 1,1,1), 메시는 자식 "mesh"에, 배율(납작 원기둥 Y 0.2)은 자식에만.
//   그다음 열린 씬과 Assets/IFS/Scenes/SceneSpecExamples.unity의 모든 SceneLoader ▸ Shape Prefabs에 연결하고 씬을 저장한다.
//   다시 실행해도 같은 경로·같은 GUID로 덮어쓴다(멱등).
// 배치모드: Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.ShapePrefabMenu.CreateShapePrefabsBatch -logFile <로그>
//   (-quit 없이 — 끝나면 EditorApplication.Exit(0/1)로 닫는다)
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace IFS.SceneSpec.EditorTools
{
    public static class ShapePrefabMenu
    {
        public const string Folder = "Assets/Prefabs/Shapes";
        public const string ConeMeshPath = Folder + "/Cone.asset";
        public const string MaterialPath = Folder + "/ShapeIFS.mat";
        const string OpaqueShaderResource = "IFS/SceneSpecOpaque";

        public static string PrefabPath(string model) => Folder + "/" + model + ".prefab";

        [MenuItem("IFS/Create Shape Prefabs")]
        public static void CreateShapePrefabs()
        {
            var r = Run();
            Debug.Log($"[IFS] 모양 프리팹 {r.Prefabs}개를 만들고 SceneLoader {r.Loaders}개에 연결했습니다({Folder}). 저장한 씬: " +
                      (r.SavedScenes.Count > 0 ? string.Join(", ", r.SavedScenes) : "없음"));
        }

        /// <summary>배치모드용. 성공하면 Exit(0), 실패하면 Exit(1).</summary>
        public static void CreateShapePrefabsBatch()
        {
            int exit = 1;
            try
            {
                CreateShapePrefabs();
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] 모양 프리팹 만들기 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        public sealed class Result
        {
            public int Prefabs;
            public int Loaders;
            public List<string> SavedScenes = new List<string>();
        }

        public static Result Run()
        {
            EnsureFolder("Assets", "Prefabs");
            EnsureFolder("Assets/Prefabs", "Shapes");

            var shader = Resources.Load<Shader>(OpaqueShaderResource);
            if (shader == null) throw new InvalidOperationException("Resources/" + OpaqueShaderResource + " 셰이더를 찾지 못했습니다.");

            // 머티리얼: IFS 불투명 셰이더, 모양 모형 프리셋(변위 0). 로더는 로드할 때 사본을 만들어 spec 값을 넣는다.
            var mat = AssetDatabase.LoadAssetAtPath<Material>(MaterialPath);
            if (mat == null)
            {
                mat = new Material(shader) { name = "ShapeIFS" };
                AssetDatabase.CreateAsset(mat, MaterialPath);
            }
            else mat.shader = shader;
            mat.SetFloat("_Lumpiness", 0f);
            mat.SetFloat("_NoiseScale", 1.6f);
            mat.SetFloat("_Fuzz", 0f);
            mat.SetFloat("_Density", 1f);
            mat.SetFloat("_ShellOpen", 0f);
            mat.SetFloat("_Displacement", 0f);
            EditorUtility.SetDirty(mat);

            // 원뿔 메시: 있으면 같은 에셋을 다시 채운다(GUID 유지).
            var cone = AssetDatabase.LoadAssetAtPath<Mesh>(ConeMeshPath);
            if (cone == null)
            {
                cone = ShapeModelFactory.BuildConeMesh("Cone");
                AssetDatabase.CreateAsset(cone, ConeMeshPath);
            }
            else
            {
                ShapeModelFactory.FillConeMesh(cone);
                EditorUtility.SetDirty(cone);
            }
            AssetDatabase.SaveAssets();

            var result = new Result();
            foreach (var model in ShapeMapping.Models)
            {
                var go = ShapeModelFactory.Create(model, mat, cone);
                try
                {
                    PrefabUtility.SaveAsPrefabAsset(go, PrefabPath(model), out bool ok);
                    if (!ok) throw new InvalidOperationException("프리팹을 저장하지 못했습니다: " + PrefabPath(model));
                }
                finally
                {
                    UnityEngine.Object.DestroyImmediate(go);
                }
                result.Prefabs++;
            }
            AssetDatabase.SaveAssets();

            var table = LoadShapePrefabs();
            var missing = table.Where(t => t.prefab == null).Select(t => t.shape).ToArray();
            if (missing.Length > 0) throw new InvalidOperationException("프리팹을 다시 읽지 못했습니다: " + string.Join(", ", missing));
            WireScenes(table, result);
            return result;
        }

        /// <summary>고정 폴더의 프리팹을 모양 값 순서(round·square·flat·pointed)로 읽는다. 없는 칸은 prefab = null.</summary>
        public static ShapePrefab[] LoadShapePrefabs() =>
            ShapeMapping.Shapes
                .Select(s => new ShapePrefab(s, AssetDatabase.LoadAssetAtPath<GameObject>(PrefabPath(ShapeMapping.ModelFor(s)))))
                .ToArray();

        /// <summary>SceneLoader 하나에 연결(예시 씬 다시 만들기에서도 부른다).</summary>
        public static void Assign(SceneLoader loader, ShapePrefab[] table)
        {
            loader.ConfigureShapePrefabs(table);
            EditorUtility.SetDirty(loader);
        }

        static void WireScenes(ShapePrefab[] table, Result result)
        {
            bool exampleOpen = false;
            for (int i = 0; i < SceneManager.sceneCount; i++)
            {
                var scene = SceneManager.GetSceneAt(i);
                if (!scene.isLoaded) continue;
                if (scene.path == SceneSpecExampleSceneMenu.ScenePath) exampleOpen = true;
                int n = WireScene(scene, table);
                result.Loaders += n;
                if (n == 0) continue;
                EditorSceneManager.MarkSceneDirty(scene);
                if (string.IsNullOrEmpty(scene.path))
                    Debug.LogWarning($"[IFS] 저장하지 않은 새 씬({scene.name})의 SceneLoader {n}개에 연결했습니다. 씬을 직접 저장하십시오.");
                else if (EditorSceneManager.SaveScene(scene)) result.SavedScenes.Add(scene.path);
            }
            if (!exampleOpen && File.Exists(SceneSpecExampleSceneMenu.ScenePath))
            {
                var scene = EditorSceneManager.OpenScene(SceneSpecExampleSceneMenu.ScenePath, OpenSceneMode.Additive);
                try
                {
                    int n = WireScene(scene, table);
                    result.Loaders += n;
                    EditorSceneManager.MarkSceneDirty(scene);
                    if (EditorSceneManager.SaveScene(scene)) result.SavedScenes.Add(scene.path);
                }
                finally
                {
                    EditorSceneManager.CloseScene(scene, true);
                }
            }
        }

        static int WireScene(Scene scene, ShapePrefab[] table)
        {
            int n = 0;
            foreach (var root in scene.GetRootGameObjects())
                foreach (var loader in root.GetComponentsInChildren<SceneLoader>(true))
                {
                    Assign(loader, table);
                    n++;
                }
            return n;
        }

        static void EnsureFolder(string parent, string name)
        {
            if (!AssetDatabase.IsValidFolder(parent + "/" + name)) AssetDatabase.CreateFolder(parent, name);
        }
    }
}
