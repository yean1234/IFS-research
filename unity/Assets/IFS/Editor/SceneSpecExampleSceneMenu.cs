// 메뉴 IFS ▸ SceneSpec ▸ 예시 테스트 씬 다시 만들기
// 저장소에 있는 Assets/IFS/Scenes/SceneSpecExamples.unity가 열리지 않거나 망가졌을 때 같은 씬을 코드로 다시 만든다.
// 씬 구성: 눈높이 1.6 m 카메라 + 중립 환경(IFSEnvironment: 바닥·1 m 격자·하늘·앰비언트·방향광) + 예시 2개.
// 배치모드: Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.SceneSpecExampleSceneMenu.CreateExampleSceneBatch -quit
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class SceneSpecExampleSceneMenu
    {
        public const string ScenePath = "Assets/IFS/Scenes/SceneSpecExamples.unity";

        [MenuItem("IFS/SceneSpec/예시 테스트 씬 다시 만들기")]
        public static void CreateExampleScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Build();
        }

        /// <summary>배치모드용(저장 확인 창 없이).</summary>
        public static void CreateExampleSceneBatch() => Build();

        static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<AudioListener>();
            cam.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), Quaternion.identity);
            cam.nearClipPlane = 0.05f;
            cam.allowHDR = false;
            cam.allowMSAA = true;

            new GameObject("IFS Environment").AddComponent<IFSEnvironment>();   // Awake에서 환경을 만든다(씬 파일에는 설정만)

            AddLoader("SceneSpec EX01", "IFS/examples/EX01.json", new Vector3(-0.45f, 0f, 0f));
            AddLoader("SceneSpec EX02", "IFS/examples/EX02.json", new Vector3(0.45f, 0f, 0f));
            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log("[IFS] 예시 테스트 씬을 만들었습니다: " + ScenePath);
        }

        static void AddLoader(string name, string specPath, Vector3 offset)
        {
            var go = new GameObject(name);
            go.AddComponent<InspectorPathSource>().SpecPath = specPath;
            var loader = go.AddComponent<SceneLoader>();
            var so = new SerializedObject(loader);
            so.FindProperty("extraOffset").vector3Value = offset;
            so.ApplyModifiedPropertiesWithoutUndo();
        }
    }
}
