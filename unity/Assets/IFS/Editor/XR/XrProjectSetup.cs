// 메뉴 IFS ▸ XR ▸ Configure OpenXR (Windows, Quest Link) — 헤드셋(PC + Quest Link, OpenXR) 실행에 필요한 XR 설정을 코드로 맞춘다.
//   · XR Plug-in Management: Standalone(Windows)에 OpenXR 로더 지정, "Initialize XR on Startup" 켬
//     (에디터 Play·Windows 빌드에서 XR이 자동으로 시작된다. 헤드셋·Link가 없으면 XR 없이 데스크톱 모의 조작으로 돈다)
//   · OpenXR: 렌더 모드 단일 패스 인스턴싱(Single Pass Instanced), 상호작용 프로필 Oculus Touch + Meta Quest Touch Plus
//   · Active Input Handling(Both)은 ProjectSettings.asset(activeInputHandler: 2)에 들어 있다 — 여기서 바꾸지 않는다.
// 배치모드: Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.XrProjectSetup.ConfigureBatch -logFile <로그>
//           Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.XrProjectSetup.ReportBatch -logFile <로그>
// com.unity.xr.openxr·com.unity.xr.management 패키지가 없으면(asmdef versionDefines) 이 파일은 비어서 컴파일된다
// (compile-check도 같은 이유로 스텁이 필요 없다).
#if IFS_HAS_OPENXR && IFS_HAS_XR_MANAGEMENT
using System;
using System.Linq;
using System.Text;
using UnityEditor;
using UnityEditor.XR.Management;
using UnityEditor.XR.Management.Metadata;
using UnityEditor.XR.OpenXR.Features;
using UnityEngine;
using UnityEngine.XR.Management;
using UnityEngine.XR.OpenXR;
using UnityEngine.XR.OpenXR.Features.Interactions;

namespace IFS.SceneSpec.EditorTools
{
    public static class XrProjectSetup
    {
        const string LoaderType = "UnityEngine.XR.OpenXR.OpenXRLoader";
        const string GeneralSettingsPath = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";
        static readonly string[] ControllerProfiles = { OculusTouchControllerProfile.featureId, MetaQuestTouchPlusControllerProfile.featureId };

        [MenuItem("IFS/XR/Configure OpenXR (Windows, Quest Link)")]
        public static void ConfigureMenu() => Debug.Log("[IFS] XR 설정\n" + Configure());

        [MenuItem("IFS/XR/Report XR Settings")]
        public static void ReportMenu() => Debug.Log("[IFS] XR 설정 상태\n" + Report());

        public static void ConfigureBatch()
        {
            int exit = 1;
            try
            {
                Debug.Log("[IFS] XR 설정\n" + Configure());
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] XR 설정 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        public static void ReportBatch()
        {
            int exit = 1;
            try
            {
                Debug.Log("[IFS] XR 설정 상태\n" + Report());
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] XR 설정 상태 확인 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        /// <summary>Standalone(Windows)용 XR 설정을 맞추고 결과를 글로 돌려준다.</summary>
        public static string Configure()
        {
            const BuildTargetGroup group = BuildTargetGroup.Standalone;
            if (!EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget) || perTarget == null)
            {
                var guids = AssetDatabase.FindAssets("t:XRGeneralSettingsPerBuildTarget");
                if (guids.Length > 0) perTarget = AssetDatabase.LoadAssetAtPath<XRGeneralSettingsPerBuildTarget>(AssetDatabase.GUIDToAssetPath(guids[0]));
                if (perTarget == null)
                {
                    if (!AssetDatabase.IsValidFolder("Assets/XR")) AssetDatabase.CreateFolder("Assets", "XR");
                    perTarget = ScriptableObject.CreateInstance<XRGeneralSettingsPerBuildTarget>();
                    AssetDatabase.CreateAsset(perTarget, GeneralSettingsPath);
                    AssetDatabase.SaveAssets();
                }
                EditorBuildSettings.AddConfigObject(XRGeneralSettings.k_SettingsKey, perTarget, true);
            }
            if (!perTarget.HasSettingsForBuildTarget(group)) perTarget.CreateDefaultSettingsForBuildTarget(group);
            if (!perTarget.HasManagerSettingsForBuildTarget(group)) perTarget.CreateDefaultManagerSettingsForBuildTarget(group);
            var general = perTarget.SettingsForBuildTarget(group);
            general.InitManagerOnStart = true;
            if (!XRPackageMetadataStore.IsLoaderAssigned(LoaderType, group))
                if (!XRPackageMetadataStore.AssignLoader(general.Manager, LoaderType, group))
                    throw new InvalidOperationException("OpenXR 로더를 Standalone에 지정하지 못했습니다");
            EditorUtility.SetDirty(general);
            EditorUtility.SetDirty(general.Manager);
            EditorUtility.SetDirty(perTarget);

            var openxr = OpenXRSettings.GetSettingsForBuildTargetGroup(group);
            if (openxr == null) throw new InvalidOperationException("OpenXR 설정(Standalone)을 찾지 못했습니다");
            FeatureHelpers.RefreshFeatures(group);
            openxr.renderMode = OpenXRSettings.RenderMode.SinglePassInstanced;
            foreach (var id in ControllerProfiles)
            {
                var f = FeatureHelpers.GetFeatureWithIdForBuildTarget(group, id);
                if (f == null) throw new InvalidOperationException("OpenXR 상호작용 프로필이 없습니다: " + id);
                f.enabled = true;
                EditorUtility.SetDirty(f);
            }
            EditorUtility.SetDirty(openxr);
            AssetDatabase.SaveAssets();
            return Report();
        }

        /// <summary>지금 XR 설정(Standalone)을 글로.</summary>
        public static string Report()
        {
            const BuildTargetGroup group = BuildTargetGroup.Standalone;
            var sb = new StringBuilder();
            EditorBuildSettings.TryGetConfigObject(XRGeneralSettings.k_SettingsKey, out XRGeneralSettingsPerBuildTarget perTarget);
            sb.AppendLine("generalSettingsAsset=" + (perTarget != null ? AssetDatabase.GetAssetPath(perTarget) : "(없음)"));
            var general = perTarget != null ? perTarget.SettingsForBuildTarget(group) : null;
            sb.AppendLine("standalone.initManagerOnStart=" + (general != null && general.InitManagerOnStart));
            var loaders = general?.Manager != null ? general.Manager.activeLoaders.Where(l => l != null).Select(l => l.GetType().FullName) : Enumerable.Empty<string>();
            sb.AppendLine("standalone.loaders=" + string.Join(",", loaders));
            var openxr = OpenXRSettings.GetSettingsForBuildTargetGroup(group);
            sb.AppendLine("openxr.renderMode=" + (openxr != null ? openxr.renderMode.ToString() : "(없음)"));
            foreach (var id in ControllerProfiles)
            {
                var f = FeatureHelpers.GetFeatureWithIdForBuildTarget(group, id);
                sb.AppendLine("openxr.feature " + id + "=" + (f != null && f.enabled));
            }
            sb.AppendLine("activeInputHandler(PlayerSettings)=" + ActiveInputHandler());
            return sb.ToString();
        }

        static string ActiveInputHandler()
        {
            var ps = AssetDatabase.LoadAllAssetsAtPath("ProjectSettings/ProjectSettings.asset").FirstOrDefault();
            if (ps == null) return "?";
            var prop = new SerializedObject(ps).FindProperty("activeInputHandler");
            return prop == null ? "?" : prop.intValue + " (0 = Input Manager, 1 = Input System, 2 = Both)";
        }
    }
}
#endif
