// 메뉴 IFS ▸ Preview ▸ 미리보기 씬 다시 만들기 (D4, 결정 G12)
// Assets/IFS/Scenes/Preview.unity = "IFS Preview" GameObject 하나(PreviewBridge). 카메라·환경·로더는 실행 때 PreviewStage가 만든다
// (에디터 캡처 PreviewCapture도 같은 PreviewStage를 쓰므로 두 화면의 구성이 같다).
// 배치모드: Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PreviewSceneMenu.CreatePreviewSceneBatch -quit
using System;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class PreviewSceneMenu
    {
        public const string ScenePath = "Assets/IFS/Scenes/Preview.unity";

        [MenuItem("IFS/Preview/미리보기 씬 다시 만들기")]
        public static void CreatePreviewScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Build();
        }

        /// <summary>배치모드용(저장 확인 창 없이).</summary>
        public static void CreatePreviewSceneBatch() => Build();

        /// <summary>씬 파일이 없으면 만든다(빌드 스크립트가 부른다).</summary>
        public static void EnsureScene()
        {
            if (AssetDatabase.LoadAssetAtPath<SceneAsset>(ScenePath) == null) Build();
        }

        static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var go = new GameObject(PreviewBridge.ObjectName);
            var bridge = go.AddComponent<PreviewBridge>();
            // 모양 프리팹(IFS ▸ Create Shape Prefabs)이 있으면 연결한다. 없으면 로더가 코드로 같은 형상을 만들고 경고한다.
            var shapes = ShapePrefabMenu.LoadShapePrefabs();
            if (Array.Exists(shapes, s => s.prefab != null)) bridge.ConfigureShapePrefabs(shapes);
            EditorUtility.SetDirty(bridge);
            EditorSceneManager.SaveScene(scene, ScenePath);
            Debug.Log("[IFS] 미리보기 씬을 만들었습니다: " + ScenePath);
        }
    }
}
