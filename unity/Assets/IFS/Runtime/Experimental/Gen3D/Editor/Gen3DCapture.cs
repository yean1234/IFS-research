// 실험 경로: GLB 폴더 → 물체마다 정규화된 크기로 놓고 정면·사선 PNG + report.json (docs/gen3d-feasibility.md).
//
//   Unity.exe -batchmode -projectPath unity -executeMethod IFS.Gen3D.EditorTools.Gen3DCapture.Run \
//     -glbDir <GLB 폴더> -outDir <결과 폴더> [-size 1024] [-objectSize 0.5] -logFile <로그>
//
// -nographics·-quit를 쓰지 않는다(렌더 필요, glTFast 로드는 비동기라 에디터 업데이트 루프에서 끝까지 진행한 뒤
// EditorApplication.Exit로 닫는다). 출력 폴더는 저장소 밖을 쓴다(GLB가 참여자 문장에서 나왔으면 원칙 6).
//
// 기존 BatchCapture(SceneSpec)와 같은 중립 환경(EnvironmentBuilder)을 쓰지만, 카메라는 물체 경계에 맞춰 둔다.
// 크기는 SceneSpec의 layout.size와 상관없이 가장 긴 변 = objectSize로 정규화한다(생성 모델 단위가 의미 없음).

using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Threading.Tasks;
using IFS.SceneSpec;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace IFS.Gen3D.EditorTools
{
    public static class Gen3DCapture
    {
        static Task<int> _job;

        /// <summary>명령줄 진입점(-executeMethod). 비동기 작업을 시작하고 업데이트 루프에서 끝을 기다린다.</summary>
        public static void Run()
        {
            string[] args = Environment.GetCommandLineArgs();
            string Arg(string k, string d = null)
            {
                int i = Array.IndexOf(args, k);
                return i >= 0 && i + 1 < args.Length ? args[i + 1] : d;
            }
            var o = new Options
            {
                GlbDir = Arg("-glbDir"),
                OutDir = Arg("-outDir"),
                Size = int.Parse(Arg("-size", "1024")),
                ObjectSize = float.Parse(Arg("-objectSize", "0.5"), System.Globalization.CultureInfo.InvariantCulture),
            };
            if (string.IsNullOrEmpty(o.GlbDir) || string.IsNullOrEmpty(o.OutDir))
            {
                Debug.LogError("[Gen3DCapture] -glbDir와 -outDir가 필요합니다.");
                EditorApplication.Exit(1);
                return;
            }
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            _job = Execute(o);
            EditorApplication.update += Poll;
        }

        static void Poll()
        {
            if (_job == null || !_job.IsCompleted) return;
            EditorApplication.update -= Poll;
            int code = 1;
            if (_job.IsFaulted) Debug.LogError("[Gen3DCapture] 실패: " + _job.Exception);
            else code = _job.Result;
            EditorApplication.Exit(code);
        }

        public sealed class Options
        {
            public string GlbDir, OutDir;
            public int Size = 1024;
            public float ObjectSize = 0.5f;
            public float Fov = 40f;
        }

        // 보기: 이름, 방위각(도, 0 = 물체 앞 +Z 쪽에서 -Z를 봄), 고도각(도)
        static readonly (string Name, float Yaw, float Pitch)[] Views = { ("front", 0f, 8f), ("oblique", 45f, 28f) };

        public static async Task<int> Execute(Options o)
        {
            string glbDir = Path.GetFullPath(o.GlbDir), outDir = Path.GetFullPath(o.OutDir);
            Directory.CreateDirectory(outDir);
            var files = Directory.GetFiles(glbDir, "*.glb").OrderBy(f => f, StringComparer.Ordinal).ToArray();
            bool asyncWas = ShaderUtil.allowAsyncCompilation;
            EnvironmentHandle env = null;
            GameObject camGo = null;
            RenderTexture rt = null, resolved = null;
            Texture2D tex = null;
            var entries = new JArray();
            int failed = 0;
            try
            {
                ShaderUtil.allowAsyncCompilation = false;
                env = EnvironmentBuilder.Build(new EnvironmentSettings());
                camGo = new GameObject("gen3d capture eye");
                var cam = camGo.AddComponent<Camera>();
                cam.enabled = false;
                cam.fieldOfView = o.Fov;
                cam.nearClipPlane = 0.02f;
                cam.farClipPlane = 300f;
                cam.allowHDR = false;
                cam.allowMSAA = true;
                cam.clearFlags = CameraClearFlags.Skybox;
                rt = new RenderTexture(new RenderTextureDescriptor(o.Size, o.Size, RenderTextureFormat.ARGB32, 24)
                    { sRGB = true, msaaSamples = Math.Max(1, QualitySettings.antiAliasing) });
                rt.Create();
                resolved = new RenderTexture(new RenderTextureDescriptor(o.Size, o.Size, RenderTextureFormat.ARGB32, 0) { sRGB = true });
                resolved.Create();
                tex = new Texture2D(o.Size, o.Size, TextureFormat.RGBA32, false, false);
                // 물체 중심: 기본 SceneSpec 배치(거리 ≈ 1.2 m, 가슴 높이 ≈ 1.28 m)와 같은 자리
                var center = new Vector3(0f, 1.28f, 1.2f);

                foreach (var f in files)
                {
                    var e = new JObject { ["glb"] = Path.GetFileName(f), ["bytes"] = new FileInfo(f).Length };
                    int errors = 0, warnings = 0;
                    var msgs = new JArray();
                    void OnLog(string cond, string stack, LogType type)
                    {
                        if (type == LogType.Error || type == LogType.Exception || type == LogType.Assert) errors++;
                        else if (type == LogType.Warning) warnings++;
                        else return;
                        if (msgs.Count < 10) msgs.Add(type + ": " + (cond.Length > 300 ? cond.Substring(0, 300) : cond));
                    }
                    Application.logMessageReceived += OnLog;
                    Gen3DGlbHandle h = null;
                    try
                    {
                        h = await Gen3DGlb.LoadAsync(f);
                        e["ok"] = h.Ok;
                        e["error"] = h.Error;
                        e["loadMs"] = new JObject
                        {
                            ["read"] = R(h.ReadMs), ["parse"] = R(h.ParseMs), ["instantiate"] = R(h.InstantiateMs), ["total"] = R(h.TotalMs),
                        };
                        if (h.Ok)
                        {
                            float k = Gen3DGlb.Normalize(h, o.ObjectSize, center);
                            e["vertices"] = h.Vertices;
                            e["triangles"] = h.Triangles;
                            e["renderers"] = h.Renderers;
                            e["hasVertexColors"] = h.HasVertexColors;
                            e["shaders"] = new JArray(h.Shaders);
                            e["rawSize"] = new JArray(R(h.RawBounds.size.x, 4), R(h.RawBounds.size.y, 4), R(h.RawBounds.size.z, 4));
                            e["scale"] = R(k, 5);
                            var views = new JObject();
                            string stem = Path.GetFileNameWithoutExtension(f);
                            foreach (var v in Views)
                            {
                                Aim(cam, center, o.ObjectSize, v.Yaw, v.Pitch);
                                string png = Path.Combine(outDir, $"{stem}_{v.Name}.png");
                                RenderTo(cam, rt, resolved, tex, png);
                                views[v.Name] = Path.GetFileName(png);
                            }
                            e["views"] = views;
                        }
                        else failed++;
                    }
                    catch (Exception ex)
                    {
                        failed++;
                        e["ok"] = false;
                        e["error"] = ex.GetType().Name + ": " + ex.Message;
                    }
                    finally
                    {
                        h?.Dispose();
                        Application.logMessageReceived -= OnLog;
                    }
                    e["consoleErrors"] = errors;
                    e["consoleWarnings"] = warnings;
                    e["messages"] = msgs;
                    entries.Add(e);
                    Debug.Log($"[Gen3DCapture] {Path.GetFileName(f)} ok={e.Value<bool>("ok")}");
                }

                var loads = entries.Where(x => x.Value<bool>("ok")).Select(x => x["loadMs"].Value<double>("total")).OrderBy(x => x).ToArray();
                var report = new JObject
                {
                    ["tool"] = "IFS.Gen3D.EditorTools.Gen3DCapture/0.1.0",
                    ["note"] = "실험 경로. GLB의 형상·색은 생성 모델이 정함(말하지 않은 세부 포함). SceneSpec 기록과 섞지 않음.",
                    ["unity"] = Application.unityVersion,
                    ["renderPipeline"] = UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline == null ? "Built-in" : UnityEngine.Rendering.GraphicsSettings.currentRenderPipeline.name,
                    ["graphicsDevice"] = SystemInfo.graphicsDeviceName,
                    ["gltfast"] = GltfastVersion(),
                    ["options"] = JObject.FromObject(o),
                    ["count"] = files.Length,
                    ["failed"] = failed,
                    ["loadMsMedian"] = loads.Length > 0 ? R(loads[loads.Length / 2]) : (double?)null,
                    ["loadMsMax"] = loads.Length > 0 ? R(loads[loads.Length - 1]) : (double?)null,
                    ["items"] = entries,
                };
                File.WriteAllText(Path.Combine(outDir, "report.json"), report.ToString(Formatting.Indented) + "\n");
                Debug.Log($"[Gen3DCapture] 끝: {files.Length}개, 실패 {failed} → {Path.Combine(outDir, "report.json")}");
                return failed == 0 && files.Length > 0 ? 0 : 1;
            }
            finally
            {
                if (camGo != null) UnityEngine.Object.DestroyImmediate(camGo);
                env?.Dispose();
                if (rt != null) { rt.Release(); UnityEngine.Object.DestroyImmediate(rt); }
                if (resolved != null) { resolved.Release(); UnityEngine.Object.DestroyImmediate(resolved); }
                if (tex != null) UnityEngine.Object.DestroyImmediate(tex);
                ShaderUtil.allowAsyncCompilation = asyncWas;
            }
        }

        static void Aim(Camera cam, Vector3 center, float objectSize, float yaw, float pitch)
        {
            // 경계 구 반지름(가장 긴 변 기준) 전체가 시야의 약 70%에 들도록 거리
            float r = objectSize * 0.5f * 1.732f;
            float d = r / Mathf.Sin(cam.fieldOfView * 0.5f * Mathf.Deg2Rad) * 1.05f;
            var dir = Quaternion.Euler(pitch, 180f + yaw, 0f) * Vector3.forward;   // yaw 0 → 카메라가 +Z 쪽에서 -Z를 봄
            cam.transform.position = center - dir * d;
            cam.transform.rotation = Quaternion.LookRotation(dir, Vector3.up);
        }

        static void RenderTo(Camera cam, RenderTexture rt, RenderTexture resolved, Texture2D tex, string path)
        {
            cam.targetTexture = rt;
            cam.Render();
            cam.targetTexture = null;
            var src = rt;
            if (rt.antiAliasing > 1) { rt.ResolveAntiAliasedSurface(resolved); src = resolved; }
            var prev = RenderTexture.active;
            RenderTexture.active = src;
            tex.ReadPixels(new Rect(0, 0, src.width, src.height), 0, 0, false);
            RenderTexture.active = prev;
            var px = tex.GetPixels32();
            for (int i = 0; i < px.Length; i++) px[i].a = 255;
            tex.SetPixels32(px);
            tex.Apply(false);
            File.WriteAllBytes(path, tex.EncodeToPNG());
        }

        static string GltfastVersion()
        {
            var info = UnityEditor.PackageManager.PackageInfo.FindForAssembly(typeof(GLTFast.GltfImport).Assembly);
            return info != null ? info.name + "@" + info.version : null;
        }

        static double R(double v, int digits = 2) => Math.Round(v, digits);
    }
}
