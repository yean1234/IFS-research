// 미리보기 무대(PreviewStage)의 에디터 배치 캡처(D4). WebGL·Windows 플레이어 미리보기와 같은 코드로 찍어 비교 기준을 만든다.
//   Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PreviewCapture.Run
//             -specDir <폴더>(여러 번 가능) -outDir <결과> [-width 800 -height 600] [-backgrounds scene,black,white] -logFile <로그>
//   (-nographics 금지: 렌더가 필요. -quit도 붙이지 않음: 끝나면 스스로 닫음)
// spec마다 <이름>_<배경>.png와, capture.json에 로드·렌더 시간(무대를 한 번 만든 뒤 spec마다 = 상주 프로세스의 지연 근사)·렌더 경로·notes를 남긴다.
// 참여자 기록은 남기지 않는다(로더 기록 끔).
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace IFS.SceneSpec.EditorTools
{
    public static class PreviewCapture
    {
        public static void Run()
        {
            int exit = 1;
            try
            {
                var args = Environment.GetCommandLineArgs();
                var dirs = new List<string>();
                for (int i = 0; i < args.Length - 1; i++) if (args[i] == "-specDir") dirs.Add(args[i + 1]);
                string outDir = Value(args, "-outDir") ?? throw new ArgumentException("-outDir가 필요합니다");
                int w = int.Parse(Value(args, "-width") ?? "800", CultureInfo.InvariantCulture);
                int h = int.Parse(Value(args, "-height") ?? "600", CultureInfo.InvariantCulture);
                var bgs = (Value(args, "-backgrounds") ?? "scene,black,white").Split(',').Select(s => s.Trim()).Where(s => s.Length > 0).ToArray();
                var files = dirs.SelectMany(d => Directory.GetFiles(Path.GetFullPath(d), "*.json").OrderBy(f => f, StringComparer.Ordinal)).ToList();
                if (files.Count == 0) throw new ArgumentException("-specDir에 spec JSON이 없습니다");
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var report = Execute(files, outDir, w, h, bgs);
                exit = report.Value<bool>("ok") ? 0 : 1;
            }
            catch (Exception e)
            {
                Debug.LogError("[PreviewCapture] 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        public static JObject Execute(IReadOnlyList<string> files, string outDir, int width, int height, IReadOnlyList<string> backgrounds)
        {
            outDir = Path.GetFullPath(outDir);
            Directory.CreateDirectory(outDir);
            bool asyncWas = ShaderUtil.allowAsyncCompilation;
            int qualityWas = QualitySettings.GetQualityLevel();
            PreviewStage stage = null;
            var entries = new JArray();
            bool allOk = true;
            var report = new JObject
            {
                ["tool"] = "PreviewCapture", ["platform"] = "editor", ["unity"] = Application.unityVersion,
                ["graphicsDevice"] = SystemInfo.graphicsDeviceVersion, ["width"] = width, ["height"] = height,
            };
            try
            {
                ShaderUtil.allowAsyncCompilation = false;   // 첫 렌더가 임시(청록) 셰이더로 찍히지 않게
                var sw = Stopwatch.StartNew();
                stage = PreviewStage.Create(new PreviewSettings(), ShapePrefabMenu.LoadShapePrefabs(), null, cameraEnabled: false);
                report["stageMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 1);
                report["quality"] = QualitySettings.names[QualitySettings.GetQualityLevel()];
                report["antiAliasing"] = QualitySettings.antiAliasing;
                report["colorSpace"] = QualitySettings.activeColorSpace.ToString();
                report["fieldOfView"] = stage.Settings.fieldOfView;
                report["eyeHeight"] = stage.Settings.eyeHeight;
                foreach (var f in files)
                {
                    var e = CaptureOne(stage, f, outDir, width, height, backgrounds);
                    allOk &= e.Value<bool>("loaded");
                    entries.Add(e);
                }
            }
            finally
            {
                stage?.Dispose();
                ShaderUtil.allowAsyncCompilation = asyncWas;
                if (QualitySettings.GetQualityLevel() != qualityWas) QualitySettings.SetQualityLevel(qualityWas, true);
            }
            report["specs"] = entries;
            report["ok"] = allOk;
            File.WriteAllText(Path.Combine(outDir, "capture.json"), report.ToString(Formatting.Indented) + "\n");
            Debug.Log($"[PreviewCapture] 끝: {entries.Count}개, ok={allOk} → {outDir}");
            return report;
        }

        static JObject CaptureOne(PreviewStage stage, string file, string outDir, int w, int h, IReadOnlyList<string> backgrounds)
        {
            string name = Path.GetFileNameWithoutExtension(file);
            var entry = new JObject { ["spec"] = Path.GetFileName(file) };
            var errors = new JArray();
            void OnLog(string condition, string stack, LogType type)
            {
                if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) errors.Add(condition);
            }
            Application.logMessageReceived += OnLog;
            try
            {
                var total = Stopwatch.StartNew();
                string json = File.ReadAllText(file, Encoding.UTF8);
                var sw = Stopwatch.StartNew();
                bool ok = stage.Load(json, Path.GetFileName(file), null);
                entry["loadMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 2);
                entry["loaded"] = ok;
                if (!ok) return entry;
                stage.FreezeMotion();
                entry["renderPath"] = stage.Loader.RenderPath;
                entry["params"] = JObject.FromObject(stage.Loader.CurrentParams.ToRecord());
                entry["notes"] = new JArray(stage.Loader.Notes);
                entry["camera"] = new JObject
                {
                    ["position"] = new JArray(stage.Camera.transform.position.x, stage.Camera.transform.position.y, stage.Camera.transform.position.z),
                    ["euler"] = new JArray(stage.Camera.transform.eulerAngles.x, stage.Camera.transform.eulerAngles.y, stage.Camera.transform.eulerAngles.z),
                };
                var renders = new JObject();
                foreach (var b in backgrounds)
                {
                    sw.Restart();
                    var png = stage.RenderPng(w, h, PreviewBridge.ParseBackground(b));
                    double renderMs = sw.Elapsed.TotalMilliseconds;
                    string path = Path.Combine(outDir, name + "_" + b.ToLowerInvariant() + ".png");
                    File.WriteAllBytes(path, png);
                    renders[b.ToLowerInvariant()] = new JObject { ["renderMs"] = Math.Round(renderMs, 2), ["png"] = Path.GetFileName(path) };
                }
                entry["renders"] = renders;
                entry["totalMs"] = Math.Round(total.Elapsed.TotalMilliseconds, 2);
            }
            catch (Exception e)
            {
                entry["loaded"] = false;
                errors.Add(e.ToString());
            }
            finally
            {
                Application.logMessageReceived -= OnLog;
                entry["errors"] = errors;
            }
            return entry;
        }

        static string Value(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
