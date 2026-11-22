// 미리보기 빌드(D4, 결정 G12). 미리보기 씬(Assets/IFS/Scenes/Preview.unity) 하나만 넣는다(EditorBuildSettings의 씬 목록은 바꾸지 않음).
//
// WebGL (모듈 "WebGL Build Support"가 있어야 함):
//   Unity.exe -batchmode -buildTarget WebGL -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWebGLPreview
//             [-outDir <폴더>] [-reportPath <json>] -logFile <로그>          (-quit 붙이지 않음: 끝나면 스스로 닫음)
//   기본 출력: <저장소 밖> ../../webgl-build/preview (= unity 폴더의 두 단계 위). 산출물은 git에 넣지 않는다.
//   빌드 동안만 바꾸고 끝나면 되돌리는 플레이어 설정(ProjectSettings 파일에 남기지 않음):
//     압축 끔(로컬 서버가 Content-Encoding 헤더 없이 내보낼 수 있게), 압축 해제 대체 끔(압축이 없으므로 불필요),
//     템플릿 PROJECT:IFSPreview(외부 CDN 없는 최소 페이지 + window.ifsPreview API), 데이터 캐싱 끔(IndexedDB에 남기지 않음).
//   색 공간은 프로젝트 값(Linear)을 그대로 쓴다(WebGL2 필요). XR 로더는 Standalone에만 설정되어 있어 WebGL에는 없다(빌드 전 확인해 보고서에 적음).
//   끝나면 활성 빌드 대상을 Standalone(Win64)으로 되돌린다.
//   WebGL 모듈이 없으면 빌드하지 않고 보고서에 이유를 적고 종료 코드 2.
//
// Windows(대안 경로 — 상주 프로세스 PreviewQueue 측정용):
//   Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PreviewBuild.BuildWindowsPreview [-outDir <폴더>] -logFile <로그>
//   기본 출력: ../../webgl-build/preview-win/IFSPreview.exe. 실행: IFSPreview.exe -batchmode -ifsPreviewQueue <요청 폴더> -logFile <로그>
using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class PreviewBuild
    {
        public const string TemplateName = "PROJECT:IFSPreview";

        static string DefaultOut(string leaf) =>
            Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "..", "webgl-build", leaf));

        [MenuItem("IFS/Preview/WebGL 미리보기 빌드")]
        public static void BuildWebGLMenu() => Debug.Log("[IFS] " + BuildWebGL(DefaultOut("preview"), null).ToString(Formatting.Indented));

        /// <summary>명령줄 진입점(-executeMethod). 끝나면 에디터를 닫는다(성공 0, 빌드 실패 1, 모듈 없음 2).</summary>
        public static void BuildWebGLPreview()
        {
            var args = Environment.GetCommandLineArgs();
            string outDir = Value(args, "-outDir") ?? DefaultOut("preview");
            string reportPath = Value(args, "-reportPath");
            int exit = 1;
            try
            {
                var report = BuildWebGL(outDir, reportPath);
                exit = report.Value<bool>("ok") ? 0 : (report.Value<bool>("moduleMissing") ? 2 : 1);
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] WebGL 미리보기 빌드 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        public static JObject BuildWebGL(string outDir, string reportPath)
        {
            outDir = Path.GetFullPath(outDir);
            reportPath ??= Path.Combine(Path.GetDirectoryName(outDir) ?? outDir, Path.GetFileName(outDir) + "-build-report.json");
            var report = new JObject
            {
                ["target"] = "WebGL", ["outDir"] = outDir, ["unity"] = Application.unityVersion,
                ["scene"] = PreviewSceneMenu.ScenePath, ["time"] = DateTime.Now.ToString("o"),
            };
            try
            {
                if (!BuildPipeline.IsBuildTargetSupported(BuildTargetGroup.WebGL, BuildTarget.WebGL))
                {
                    report["ok"] = false;
                    report["moduleMissing"] = true;
                    report["reason"] = "이 에디터에 WebGL Build Support 모듈이 없습니다(Unity Hub ▸ Installs ▸ 6000.0.85f2 ▸ Add modules ▸ Web Build Support).";
                    Debug.LogError("[IFS] " + report["reason"]);
                    return report;
                }
                PreviewSceneMenu.EnsureScene();
                report["colorSpace"] = PlayerSettings.colorSpace.ToString();
                report["xrLoaderForWebGL"] = XrLoaderNote();

                var saved = new WebGLSettingsSnapshot();
                try
                {
                    PlayerSettings.WebGL.compressionFormat = WebGLCompressionFormat.Disabled;
                    PlayerSettings.WebGL.decompressionFallback = false;
                    PlayerSettings.WebGL.template = TemplateName;
                    PlayerSettings.WebGL.dataCaching = false;
                    report["temporarySettings"] = new JObject
                    {
                        ["compressionFormat"] = "Disabled", ["decompressionFallback"] = false, ["template"] = TemplateName, ["dataCaching"] = false,
                        ["restoredAfterBuild"] = true,
                    };
                    var opts = new BuildPlayerOptions
                    {
                        scenes = new[] { PreviewSceneMenu.ScenePath },
                        locationPathName = outDir,
                        target = BuildTarget.WebGL,
                        options = BuildOptions.None,
                    };
                    var started = DateTime.UtcNow;
                    var r = BuildPipeline.BuildPlayer(opts);
                    report["wallSeconds"] = Math.Round((DateTime.UtcNow - started).TotalSeconds, 1);
                    report["result"] = r.summary.result.ToString();
                    report["errors"] = r.summary.totalErrors;
                    report["warnings"] = r.summary.totalWarnings;
                    report["buildSeconds"] = Math.Round(r.summary.totalTime.TotalSeconds, 1);
                    report["reportedSizeBytes"] = (long)r.summary.totalSize;
                    report["ok"] = r.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded;
                    if (Directory.Exists(outDir)) report["files"] = FileSizes(outDir);
                }
                finally
                {
                    saved.Restore();
                }
            }
            finally
            {
                // 활성 빌드 대상을 Standalone으로 되돌린다(-buildTarget WebGL로 띄웠거나 빌드가 바꿨을 때)
                if (EditorUserBuildSettings.activeBuildTarget != BuildTarget.StandaloneWindows64)
                {
                    bool switched = EditorUserBuildSettings.SwitchActiveBuildTarget(BuildTargetGroup.Standalone, BuildTarget.StandaloneWindows64);
                    report["restoredBuildTarget"] = switched ? "StandaloneWindows64" : "실패(수동으로 되돌려야 함)";
                }
                Directory.CreateDirectory(Path.GetDirectoryName(reportPath));
                File.WriteAllText(reportPath, report.ToString(Formatting.Indented) + "\n");
                Debug.Log("[IFS] WebGL 빌드 보고서: " + reportPath);
            }
            return report;
        }

        /// <summary>대안 경로(Unity가 뒤에서 캡처) 측정용 Windows 플레이어. PreviewQueue(-ifsPreviewQueue)로 요청을 받는다.</summary>
        public static void BuildWindowsPreview()
        {
            var args = Environment.GetCommandLineArgs();
            string outDir = Path.GetFullPath(Value(args, "-outDir") ?? DefaultOut("preview-win"));
            int exit = 1;
            var report = new JObject { ["target"] = "StandaloneWindows64", ["outDir"] = outDir, ["unity"] = Application.unityVersion, ["time"] = DateTime.Now.ToString("o") };
            bool? xrWas = null;
            try
            {
                PreviewSceneMenu.EnsureScene();
                // 미리보기 플레이어는 헤드셋을 쓰지 않는다: 빌드 동안만 Standalone의 "시작 때 XR 초기화"를 끄고 끝나면 되돌린다
                // (켜 두면 실행 때 OpenXR 런타임을 깨운다). XR 패키지 API 대신 자산의 직렬화 필드로 바꾼다.
                xrWas = SetStandaloneXrInitOnStart(false);
                report["xrInitOnStartDuringBuild"] = xrWas == null ? "XR 설정 없음" : "false(빌드 뒤 " + xrWas + "로 되돌림)";
                var opts = new BuildPlayerOptions
                {
                    scenes = new[] { PreviewSceneMenu.ScenePath },
                    locationPathName = Path.Combine(outDir, "IFSPreview.exe"),
                    target = BuildTarget.StandaloneWindows64,
                    options = BuildOptions.None,
                };
                var started = DateTime.UtcNow;
                var r = BuildPipeline.BuildPlayer(opts);
                report["wallSeconds"] = Math.Round((DateTime.UtcNow - started).TotalSeconds, 1);
                report["result"] = r.summary.result.ToString();
                report["errors"] = r.summary.totalErrors;
                report["buildSeconds"] = Math.Round(r.summary.totalTime.TotalSeconds, 1);
                report["reportedSizeBytes"] = (long)r.summary.totalSize;
                report["ok"] = r.summary.result == UnityEditor.Build.Reporting.BuildResult.Succeeded;
                if (Directory.Exists(outDir)) report["totalBytesOnDisk"] = Directory.GetFiles(outDir, "*", SearchOption.AllDirectories).Sum(f => new FileInfo(f).Length);
                exit = report.Value<bool>("ok") ? 0 : 1;
            }
            catch (Exception e)
            {
                report["ok"] = false;
                report["exception"] = e.ToString();
                Debug.LogError("[IFS] Windows 미리보기 빌드 실패: " + e);
            }
            finally
            {
                if (xrWas != null) SetStandaloneXrInitOnStart(xrWas.Value);
            }
            string reportPath = outDir + "-build-report.json";
            File.WriteAllText(reportPath, report.ToString(Formatting.Indented) + "\n");
            Debug.Log("[IFS] Windows 미리보기 빌드 보고서: " + reportPath);
            EditorApplication.Exit(exit);
        }

        const string XrSettingsPath = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";

        /// <summary>Standalone XR 설정의 m_InitManagerOnStart를 바꾸고 이전 값을 돌려준다(설정이 없으면 null).</summary>
        static bool? SetStandaloneXrInitOnStart(bool value)
        {
            foreach (var o in AssetDatabase.LoadAllAssetsAtPath(XrSettingsPath))
            {
                if (o == null || o.name != "Standalone Settings") continue;
                var so = new SerializedObject(o);
                var p = so.FindProperty("m_InitManagerOnStart");
                if (p == null) return null;
                bool was = p.boolValue;
                p.boolValue = value;
                so.ApplyModifiedPropertiesWithoutUndo();
                AssetDatabase.SaveAssets();
                return was;
            }
            return null;
        }

        static JArray FileSizes(string dir) => new JArray(
            Directory.GetFiles(dir, "*", SearchOption.AllDirectories).OrderBy(f => f, StringComparer.Ordinal)
                .Select(f => new JObject { ["path"] = f.Substring(dir.Length).TrimStart('\\', '/').Replace('\\', '/'), ["bytes"] = new FileInfo(f).Length }));

        // XR 일반 설정 자산에서 WebGL 항목이 있는지 본다(이 프로젝트는 Standalone만 OpenXR). 패키지 API 없이 자산 텍스트로 확인한다.
        static string XrLoaderNote()
        {
            const string path = "Assets/XR/XRGeneralSettingsPerBuildTarget.asset";
            if (!File.Exists(path)) return "XR 설정 자산 없음 → XR 로더 없음";
            string text = File.ReadAllText(path);
            return text.Contains("WebGL") ? "WebGL 항목 있음 — 확인 필요" : "WebGL 항목 없음(Standalone만) → WebGL 빌드에 XR 로더 없음";
        }

        static string Value(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }

        /// <summary>빌드 동안만 바꾸는 WebGL 플레이어 설정을 저장했다가 되돌린다.</summary>
        sealed class WebGLSettingsSnapshot
        {
            readonly WebGLCompressionFormat _compression = PlayerSettings.WebGL.compressionFormat;
            readonly bool _fallback = PlayerSettings.WebGL.decompressionFallback;
            readonly string _template = PlayerSettings.WebGL.template;
            readonly bool _caching = PlayerSettings.WebGL.dataCaching;

            public void Restore()
            {
                PlayerSettings.WebGL.compressionFormat = _compression;
                PlayerSettings.WebGL.decompressionFallback = _fallback;
                PlayerSettings.WebGL.template = _template;
                PlayerSettings.WebGL.dataCaching = _caching;
                AssetDatabase.SaveAssets();
            }
        }
    }
}
