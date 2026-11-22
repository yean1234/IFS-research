// 배치 캡처·성능 측정 (작업 5의 챗봇 → JSON → Unity 검증이 그대로 쓴다).
//
//   Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.BatchCapture.Run
//             -specDir <SceneSpec JSON 폴더> -outDir <결과 폴더> [-width 2064 -height 2208] [-frames 300]
//             [-warmup 30] [-eyes 2] [-pngWidth 1024] [-fov 96] [-eyeHeight 1.6] [-quality "VR PC"] -logFile <로그>
//   (-nographics를 쓰지 않는다 — 렌더가 필요하다. -quit도 쓰지 않는다 — 끝나면 EditorApplication.Exit(0/1)로 닫는다.)
//
// JSON 하나마다: 빈 씬 + 중립 환경(EnvironmentBuilder) + SceneLoader로 spec을 불러온 뒤
//   1) 눈높이(1.6 m) 카메라를 형상 쪽으로 돌려 RenderTexture에 렌더 → <이름>.png(축소), <이름>_detail.png(형상 주변 잘라냄)
//   2) SceneLoader가 실제로 쓴 파라미터(initialScene.json의 params와 같은 값), defaultsUsed, inferredUsed, notes
//   3) 로드·렌더 중 Console 오류·예외·경고(Application.logMessageReceived)
//   4) 색 정확도: 형상 중앙 영역의 평균 렌더 색(sRGB) vs SceneSpec 색(HSL→sRGB), CIEDE2000 — 정면 조명·장면 조명·실제 장면.
//      1차 값(primary) = 불투명 inContext, 반투명 scene. 요약은 참여자가 말한 색(stated)과 기본값이 섞인 색을 나눠 집계한다.
//   5) 성능: 눈당 width×height, MSAA = 품질 설정, 한 프레임 = 눈 eyes개 렌더 + GPU 동기화. p50/p95/max(ms)
//   6) 렌더 통계: UnityStats·ProfilerRecorder(배치모드에서 의미가 있는지 함께 기록) + 직접 계산한 추정(렌더러·삼각형·패스·그림자 광원)
//   7) 모양어 판정(shape): _unmapped의 모양어 → 모양 모형(SceneLoader.Shape). 모양 프리팹은 Assets/Prefabs/Shapes에서 읽어
//      로더에 연결한다(ShapePrefabMenu). 없으면 로더가 같은 형상을 코드로 만들고 viaPrefab = false로 남긴다.
//   8) 형상 지표(X72): renderPath(렌더러 이름), visiblePixels·maxAlpha(장면 조명 덮임), silhouette(원형도·덩어리 수·가장자리 감쇠 폭).
//      "더 그 형상답다"의 대리 지표일 뿐이다(사람 판정을 대신하지 않는다). 계산은 SilhouetteMetrics(UnityEngine 없음).
// 끝나면 <outDir>/report.json. 모든 spec이 로드되고 도구가 예외 없이 끝나면 Exit(0), 아니면 Exit(1).
// 데스크톱 GPU 대리 측정이다. Quest 3 헤드셋(모바일 GPU)의 성능이 아니다.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Linq;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using Unity.Profiling;
using UnityEngine;
using UnityEngine.Rendering;
using Debug = UnityEngine.Debug;

namespace IFS.SceneSpec.EditorTools
{
    public static class BatchCapture
    {
        public const string ReportFormat = "ifs-batch-capture/0.1";

        // AC-4 기준(docs/acceptance.md)
        public const double FrameTimeP95LimitMs = 13.9;   // 72 Hz
        public const int DrawCallLimit = 100;
        public const long TriangleLimit = 300000;
        public const int ShadowLightLimit = 1;

        public const string Disclaimer =
            "데스크톱 GPU에서 잰 대리 측정값입니다. Quest 3 헤드셋(모바일 GPU, 타일 렌더링, 단일 패스 인스턴싱)의 프레임시간이 아닙니다. " +
            "헤드셋 성능은 기기에서 OVR Metrics Tool 등으로 따로 재야 합니다.";

        public const string TimingMethod =
            "한 프레임 = 눈 수만큼 Camera.Render()(눈 위치를 IPD/2씩 옮김, 멀티패스 = 가장 불리한 경우) 후 " +
            "RenderTexture에서 1×1 화소를 Texture2D.ReadPixels로 읽어 CPU가 GPU 완료를 기다리게 함(동기화). " +
            "Stopwatch로 렌더 시작부터 동기화 끝까지 잼. 준비 프레임은 버림. 에디터 오버헤드·MSAA 해상(resolve) 비용이 포함됨.";

        // 8비트 sRGB → 선형 표(화소 수백만 개에 거듭제곱을 반복하지 않도록)
        static readonly double[] Lin = Enumerable.Range(0, 256).Select(i => ColorMetrics.SrgbToLinear(i / 255.0)).ToArray();

        static readonly ShaderTagId LightModeTag = new ShaderTagId("LightMode");

        static readonly string[] IfsShaders =
        {
            "IFS/SceneSpecOpaque", "IFS/SceneSpecFade", FormRenderResources.MistShaderResource, EnvironmentBuilder.FloorShaderResource, EnvironmentBuilder.SkyShaderResource,
        };

        /// <summary>명령줄 진입점(-executeMethod).</summary>
        public static void Run()
        {
            int exit = 1;
            try
            {
                var options = CaptureOptions.Parse(Environment.GetCommandLineArgs());
                EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
                var report = Execute(options);
                exit = report.Value<bool>("ok") ? 0 : 1;
                Debug.Log($"[BatchCapture] 끝: ok={report.Value<bool>("ok")} → {Path.Combine(options.OutDir, "report.json")}");
            }
            catch (Exception e)
            {
                Debug.LogError("[BatchCapture] 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        /// <summary>현재 열린 씬에서 캡처를 실행하고 report.json을 쓴다(테스트에서도 부른다). 만든 객체는 끝나면 지운다.</summary>
        public static JObject Execute(CaptureOptions o)
        {
            string specDir = Path.GetFullPath(o.SpecDir);
            string outDir = Path.GetFullPath(o.OutDir);
            if (!Directory.Exists(specDir)) throw new DirectoryNotFoundException("SceneSpec 폴더가 없습니다: " + specDir);
            Directory.CreateDirectory(outDir);
            var files = Directory.GetFiles(specDir, "*.json").OrderBy(f => f, StringComparer.Ordinal).ToArray();

            bool asyncWas = ShaderUtil.allowAsyncCompilation;
            int qualityWas = QualitySettings.GetQualityLevel();
            EnvironmentHandle env = null;
            GameObject camGo = null;
            var temps = new List<UnityEngine.Object>();
            try
            {
                ShaderUtil.allowAsyncCompilation = false;   // 첫 렌더가 임시(청록) 셰이더로 찍히지 않게
                if (!string.IsNullOrEmpty(o.Quality))
                {
                    int idx = Array.IndexOf(QualitySettings.names, o.Quality);
                    if (idx < 0) throw new ArgumentException("품질 단계가 없습니다: " + o.Quality + " (있는 것: " + string.Join(", ", QualitySettings.names) + ")");
                    QualitySettings.SetQualityLevel(idx, true);
                }

                env = EnvironmentBuilder.Build(new EnvironmentSettings());
                camGo = new GameObject("capture eye");
                var cam = camGo.AddComponent<Camera>();
                cam.enabled = false;
                cam.fieldOfView = o.FieldOfView;
                cam.nearClipPlane = 0.05f;
                cam.farClipPlane = 300f;
                cam.allowMSAA = true;
                cam.allowHDR = false;
                cam.clearFlags = CameraClearFlags.Skybox;

                int msaa = Math.Max(1, QualitySettings.antiAliasing);
                var eyeRt = new RenderTexture(new RenderTextureDescriptor(o.Width, o.Height, RenderTextureFormat.ARGB32, 24)
                {
                    sRGB = true,
                    msaaSamples = msaa,
                }) { name = "capture eye (MSAA)" };
                eyeRt.Create();
                temps.Add(eyeRt);
                var resolved = new RenderTexture(new RenderTextureDescriptor(o.Width, o.Height, RenderTextureFormat.ARGB32, 0) { sRGB = true })
                    { name = "capture resolved" };
                resolved.Create();
                temps.Add(resolved);
                var fullTex = new Texture2D(o.Width, o.Height, TextureFormat.RGBA32, false, false);
                temps.Add(fullTex);
                var ctx = new Ctx { O = o, Cam = cam, Env = env, EyeRt = eyeRt, Resolved = resolved, FullTex = fullTex, OutDir = outDir, Temps = temps,
                                    ShapePrefabs = ShapePrefabMenu.LoadShapePrefabs() };
                // 색 측정용 바닥 대체 머티리얼(배경과 같은 단색). 에디터 도구라 내장 셰이더를 Shader.Find로 찾는다.
                var unlit = Shader.Find("Unlit/Color");
                if (unlit != null && unlit.isSupported)
                {
                    ctx.FloorBlack = new Material(unlit) { name = "capture floor (black)", color = Color.black };
                    ctx.FloorWhite = new Material(unlit) { name = "capture floor (white)", color = Color.white };
                    temps.Add(ctx.FloorBlack);
                    temps.Add(ctx.FloorWhite);
                }
                else Debug.LogWarning("[BatchCapture] Unlit/Color 셰이더가 없어 색 측정 중 바닥을 끕니다(scene 값이 실제 장면과 다를 수 있음).");

                var specs = new JArray();
                foreach (var f in files) specs.Add(CaptureOne(ctx, f));

                var report = BuildReport(ctx, specs, files.Length, msaa);
                File.WriteAllText(Path.Combine(outDir, "report.json"), report.ToString(Formatting.Indented) + "\n");
                return report;
            }
            finally
            {
                if (camGo != null) UnityEngine.Object.DestroyImmediate(camGo);
                env?.Dispose();
                foreach (var t in temps)
                {
                    if (t is RenderTexture rt) rt.Release();
                    if (t != null) UnityEngine.Object.DestroyImmediate(t);
                }
                ShaderUtil.allowAsyncCompilation = asyncWas;
                if (QualitySettings.GetQualityLevel() != qualityWas) QualitySettings.SetQualityLevel(qualityWas, true);
            }
        }

        sealed class Ctx
        {
            public CaptureOptions O;
            public Camera Cam;
            public EnvironmentHandle Env;
            public RenderTexture EyeRt, Resolved;
            public Texture2D FullTex;
            public Material FloorBlack, FloorWhite;
            public string OutDir;
            public List<UnityEngine.Object> Temps;
            public ShapePrefab[] ShapePrefabs;
        }

        // ── spec 하나 ───────────────────────────────────────────────────────
        static JObject CaptureOne(Ctx c, string file)
        {
            string name = Path.GetFileNameWithoutExtension(file);
            var entry = new JObject { ["spec"] = Path.GetFileName(file) };
            var messages = new JArray();
            int errors = 0, exceptions = 0, warnings = 0, infos = 0;
            void OnLog(string condition, string stack, LogType type)
            {
                switch (type)
                {
                    case LogType.Error:
                    case LogType.Assert: errors++; break;
                    case LogType.Exception: exceptions++; break;
                    case LogType.Warning: warnings++; break;
                    default: infos++; return;
                }
                if (messages.Count < 100)
                    messages.Add(new JObject { ["type"] = type.ToString(), ["message"] = condition, ["stack"] = FirstLines(stack, 3) });
            }

            GameObject loaderGo = null;
            Application.logMessageReceived += OnLog;
            try
            {
                var cam = c.Cam;
                var eye = new Vector3(0f, c.O.EyeHeight, 0f);
                cam.transform.SetPositionAndRotation(eye, Quaternion.identity);   // 로드 순간의 머리 = 원점, +Z를 봄

                loaderGo = new GameObject("SceneLoader (batch) " + name);
                var loader = loaderGo.AddComponent<SceneLoader>();
                var so = new SerializedObject(loader);
                so.FindProperty("record").boolValue = false;        // 배치 캡처는 참여자 기록 폴더에 쓰지 않는다
                so.FindProperty("loadOnStart").boolValue = false;
                so.FindProperty("head").objectReferenceValue = cam.transform;
                so.ApplyModifiedPropertiesWithoutUndo();
                loader.ConfigureShapePrefabs(c.ShapePrefabs);

                bool loaded = loader.Load(file);
                entry["loaded"] = loaded;
                if (loaded)
                {
                    var p = loader.InitialParams;
                    entry["sessionId"] = loader.Spec.Meta.SessionId;
                    entry["params"] = JObject.FromObject(p.ToRecord());
                    entry["defaultsUsed"] = new JArray(p.DefaultsUsed);
                    entry["inferredUsed"] = new JArray(p.InferredUsed);
                    entry["notes"] = new JArray(loader.Notes.ToArray());
                    entry["shape"] = loader.Shape.ToJson();
                    entry["renderPath"] = loader.RenderPath;
                    entry["renderPlan"] = loader.RenderPlan?.ToJson();

                    var renderers = loader.Root.GetComponentsInChildren<Renderer>();
                    var bounds = Encapsulate(renderers);
                    var toObj = bounds.center - eye;
                    cam.transform.rotation = Quaternion.LookRotation(toObj.normalized, Vector3.up);
                    var flat = new Vector3(toObj.x, 0f, toObj.z);
                    entry["placement"] = new JObject
                    {
                        ["objectCenter"] = Vec(bounds.center),
                        ["horizontalDistanceM"] = R(flat.magnitude),
                        ["heightM"] = R(bounds.center.y),
                        ["cameraPitchDeg"] = R(-Mathf.Atan2(toObj.y, flat.magnitude) * Mathf.Rad2Deg),
                        ["motionNote"] = "에디트 모드 정지 화면 — motion.type은 이 PNG에 보이지 않음(재생 중에만 움직임)",
                    };

                    // 1) 장면 렌더 → PNG
                    var full = RenderAndRead(c, cam);
                    string png = Path.Combine(c.OutDir, name + ".png");
                    SaveScaledPng(c, png);
                    entry["png"] = Path.GetFileName(png);

                    // 2) 색 정확도(형상만 렌더해 가림 마스크·중앙 영역을 구한다)
                    bool fade = RenderedColor.UsesFadeShader(p.GetCategory("form.type"), p.GetNumber("material.opacity"));   // 로더와 같은 판정
                    var colorReport = MeasureColor(c, cam, p, full, fade, out var maskBox, out var coverage);
                    entry["color"] = colorReport;
                    // 형상 지표(X72): 장면 조명·형상만 렌더의 화소별 덮임으로 잰다(색 측정과 같은 덮임)
                    var sil = SilhouetteMetrics.Measure(coverage, c.O.Width, c.O.Height);
                    entry["visiblePixels"] = sil.VisiblePixels;
                    entry["maxAlpha"] = R(sil.MaxAlpha);
                    entry["silhouette"] = SilhouetteJson(sil);
                    if (maskBox.HasValue)
                    {
                        string detail = Path.Combine(c.OutDir, name + "_detail.png");
                        SaveCrop(full, c.O.Width, c.O.Height, maskBox.Value, detail, c.Temps);
                        entry["pngDetail"] = Path.GetFileName(detail);
                    }

                    // 3) 렌더 통계 + 4) 프레임시간
                    entry["renderStats"] = RenderStats(c, cam);
                    entry["performance"] = MeasurePerformance(c, cam);
                }
            }
            catch (Exception e)
            {
                entry["loaded"] = entry.Value<bool?>("loaded") ?? false;
                entry["captureException"] = e.GetType().Name + ": " + e.Message;
                entry["captureFailed"] = true;
                exceptions++;
                messages.Add(new JObject { ["type"] = "CaptureException", ["message"] = e.ToString() });
            }
            finally
            {
                Application.logMessageReceived -= OnLog;
                if (loaderGo != null) UnityEngine.Object.DestroyImmediate(loaderGo);
            }
            entry["console"] = new JObject
            {
                ["errors"] = errors, ["exceptions"] = exceptions, ["warnings"] = warnings, ["infos"] = infos, ["messages"] = messages,
            };
            return entry;
        }

        // ── 렌더·읽기 ───────────────────────────────────────────────────────
        static Color32[] RenderAndRead(Ctx c, Camera cam)
        {
            cam.targetTexture = c.EyeRt;
            cam.Render();
            cam.targetTexture = null;
            var src = c.EyeRt;
            if (c.EyeRt.antiAliasing > 1)
            {
                c.EyeRt.ResolveAntiAliasedSurface(c.Resolved);
                src = c.Resolved;
            }
            var prev = RenderTexture.active;
            RenderTexture.active = src;
            c.FullTex.ReadPixels(new Rect(0, 0, src.width, src.height), 0, 0, false);
            RenderTexture.active = prev;
            return c.FullTex.GetPixels32();
        }

        static void SaveScaledPng(Ctx c, string path)
        {
            var src = c.EyeRt.antiAliasing > 1 ? c.Resolved : c.EyeRt;
            int w = c.O.PngWidth > 0 ? Math.Min(c.O.PngWidth, c.O.Width) : c.O.Width;
            int h = Math.Max(1, (int)Math.Round((double)c.O.Height * w / c.O.Width));
            var small = RenderTexture.GetTemporary(new RenderTextureDescriptor(w, h, RenderTextureFormat.ARGB32, 0) { sRGB = true });
            var tex = new Texture2D(w, h, TextureFormat.RGBA32, false, false);
            try
            {
                Graphics.Blit(src, small);   // 선형 공간에서 쌍선형 축소(≈2×2 상자 필터)
                var prev = RenderTexture.active;
                RenderTexture.active = small;
                tex.ReadPixels(new Rect(0, 0, w, h), 0, 0, false);
                RenderTexture.active = prev;
                var px = tex.GetPixels32();
                for (int i = 0; i < px.Length; i++) px[i].a = 255;
                tex.SetPixels32(px);
                tex.Apply(false);
                File.WriteAllBytes(path, tex.EncodeToPNG());
            }
            finally
            {
                RenderTexture.ReleaseTemporary(small);
                UnityEngine.Object.DestroyImmediate(tex);
            }
        }

        static void SaveCrop(Color32[] full, int w, int h, RectInt box, string path, List<UnityEngine.Object> temps)
        {
            int side = Math.Max(160, (int)(Math.Max(box.width, box.height) * 1.5f));
            int cx = box.x + box.width / 2, cy = box.y + box.height / 2;
            int x0 = Math.Max(0, cx - side / 2), y0 = Math.Max(0, cy - side / 2);
            int x1 = Math.Min(w, x0 + side), y1 = Math.Min(h, y0 + side);
            int cw = x1 - x0, ch = y1 - y0;
            if (cw <= 0 || ch <= 0) return;
            var px = new Color32[cw * ch];
            for (int y = 0; y < ch; y++)
                for (int x = 0; x < cw; x++)
                {
                    var v = full[(y0 + y) * w + (x0 + x)];
                    v.a = 255;
                    px[y * cw + x] = v;
                }
            var tex = new Texture2D(cw, ch, TextureFormat.RGBA32, false, false);
            try
            {
                tex.SetPixels32(px);
                tex.Apply(false);
                File.WriteAllBytes(path, tex.EncodeToPNG());
            }
            finally
            {
                UnityEngine.Object.DestroyImmediate(tex);
            }
        }

        // ── 색 정확도 ───────────────────────────────────────────────────────
        static JObject MeasureColor(Ctx c, Camera cam, SceneParams p, Color32[] scenePixels, bool fade, out RectInt? maskBox, out float[] coverage)
        {
            maskBox = null;
            SceneParams.HslToRgb(p.GetNumber("material.color.h"), p.GetNumber("material.color.s"), p.GetNumber("material.color.l"),
                out double sr, out double sg, out double sb);
            double brightness = p.GetNumber("material.brightness");
            // 셰이더 의도(IFSSceneSpecCommon.cginc): brightness 0.5 미만이면 알베도를 0.4배까지 어둡게, 초과면 발광(색 × (B − 0.5) × 2.4)을 더한다.
            // shaderTarget = 빛 세기 1에서 기대되는 색(선형) = spec × (어둡게 배율 + 발광 배율). 이것과의 차이는 조명·질감 때문이다.
            double darken = 0.4 + 0.6 * Math.Min(1.0, Math.Max(0.0, brightness * 2.0));
            double emit = Math.Min(1.0, Math.Max(0.0, brightness - 0.5)) * 2.4;
            double tr = ColorMetrics.LinearToSrgb(ColorMetrics.SrgbToLinear(sr) * (darken + emit));
            double tg = ColorMetrics.LinearToSrgb(ColorMetrics.SrgbToLinear(sg) * (darken + emit));
            double tb = ColorMetrics.LinearToSrgb(ColorMetrics.SrgbToLinear(sb) * (darken + emit));
            var specLab = ColorMetrics.SrgbToLab(sr, sg, sb);
            var targetLab = ColorMetrics.SrgbToLab(tr, tg, tb);

            var floor = c.Env.Floor;
            var light = c.Env.KeyLight;
            var clearWas = cam.clearFlags;
            var bgWas = cam.backgroundColor;
            var lightRotWas = light.transform.rotation;
            var floorMatWas = floor.sharedMaterial;
            // 형상만 검은 배경·흰 배경에 각각 렌더 → 화소마다 덮임(알파)과 배경과 섞이기 전 색을 되돌린다.
            //   B = c·a, W = c·a + (1 − a) (선형)  ⇒  a = 1 − (W − B),  c = B / a
            // (Fade 서피스 셰이더는 알파 채널을 쓰지 않으므로 RenderTexture 알파로는 덮임을 알 수 없다)
            // 바닥은 끄지 않고 배경과 같은 색의 무광(Unlit) 머티리얼로 바꾼다. 바닥을 끄면 화면에 보이는 그림자 수신자 구성이
            // 바뀌어 방향광 그림자 맵의 범위·바이어스가 실제 장면과 달라지고, 불투명 형상에서도 scene ≠ inContext가 된다.
            bool floorSwapped = c.FloorBlack != null && c.FloorWhite != null;
            Color32[] sceneB, sceneW, frontB, frontW, diagLitFloorBlack, diagNoFloorSkybox, diagSceneAgain;
            try
            {
                cam.clearFlags = clearWas;
                diagSceneAgain = RenderAndRead(c, cam);              // 실제 장면을 한 번 더(첫 렌더만 다른지)
                // 진단(불투명 형상에서 scene ≠ inContext인 원인 찾기): 하나씩만 바꾼 렌더 두 장
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = Color.black;
                diagLitFloorBlack = RenderAndRead(c, cam);            // 바닥 그대로(조명 받는 원래 머티리얼), 배경만 검정
                cam.clearFlags = CameraClearFlags.Skybox;
                floor.enabled = false;
                diagNoFloorSkybox = RenderAndRead(c, cam);            // 하늘 그대로, 바닥만 끔
                floor.enabled = true;

                if (!floorSwapped) floor.enabled = false;
                cam.clearFlags = CameraClearFlags.SolidColor;
                void Background(bool white)
                {
                    cam.backgroundColor = white ? Color.white : Color.black;
                    if (floorSwapped) floor.sharedMaterial = white ? c.FloorWhite : c.FloorBlack;
                }
                Background(false);
                sceneB = RenderAndRead(c, cam);
                Background(true);
                sceneW = RenderAndRead(c, cam);
                light.transform.rotation = cam.transform.rotation;   // 빛이 카메라 시선 방향으로 = 정면 조명
                Background(false);
                frontB = RenderAndRead(c, cam);
                Background(true);
                frontW = RenderAndRead(c, cam);
            }
            finally
            {
                light.transform.rotation = lightRotWas;
                floor.sharedMaterial = floorMatWas;
                floor.enabled = true;
                cam.clearFlags = clearWas;
                cam.backgroundColor = bgWas;
            }

            int w = c.O.Width, h = c.O.Height;
            double alphaMin = fade ? 0.05 : 0.98;
            var alpha = Coverage(sceneB, sceneW);
            coverage = alpha;
            int minX = w, minY = h, maxX = -1, maxY = -1, covered = 0;
            for (int y = 0; y < h; y++)
                for (int x = 0; x < w; x++)
                    if (alpha[y * w + x] >= alphaMin)
                    {
                        covered++;
                        if (x < minX) minX = x;
                        if (x > maxX) maxX = x;
                        if (y < minY) minY = y;
                        if (y > maxY) maxY = y;
                    }

            var defaultComponents = ColorDefaultComponents(p);
            var result = new JObject
            {
                ["specHsl"] = new JArray(R(p.GetNumber("material.color.h")), R(p.GetNumber("material.color.s")), R(p.GetNumber("material.color.l"))),
                ["specSrgb"] = new JArray(R(sr), R(sg), R(sb)),
                // h·s·l 중 하나라도 참여자가 말하지 않아 기본값으로 채웠으면 true(원칙 2: 말한 값과 기본값을 섞지 않는다)
                ["specColorIsDefault"] = defaultComponents.Length > 0,
                ["specColorDefaultComponents"] = new JArray(defaultComponents),
                ["brightness"] = R(brightness),
                ["brightnessIsDefault"] = p.DefaultsUsed.Contains("material.brightness"),
                ["shaderTargetSrgb"] = new JArray(R(tr), R(tg), R(tb)),
                ["transparent"] = fade,
                ["primary"] = fade ? "scene" : "inContext",
                ["floorDuringIsolatedRenders"] = floorSwapped ? "unlitBackgroundColor" : "disabled",
                ["method"] = "형상만 검은·흰 배경에 렌더해 화소별 덮임 a = 1 − (W − B)와 배경과 섞이기 전 색 c = B / a를 구함(선형). " +
                             "이때 바닥은 끄지 않고 배경과 같은 색의 Unlit 머티리얼로 바꿔 그림자 수신자 구성을 실제 장면과 같게 둠. " +
                             "덮인 화소(a ≥ " + alphaMin.ToString(CultureInfo.InvariantCulture) + ")의 경계 상자 가운데 50%×50% 안에서 선형 평균 → sRGB. " +
                             "frontal = 광원을 카메라 시선 방향으로 돌린 정면 조명, scene = 장면 방향광 그대로, inContext = 실제 장면 렌더(바닥·하늘·반투명이면 배경과 섞인 값). " +
                             "primary = 보고·판정에 쓰는 값: 불투명이면 inContext(참여자가 보는 색), 반투명이면 scene(배경과 섞이기 전 색).",
            };
            if (covered == 0 || maxX < minX)
            {
                result["error"] = "형상이 화면에 보이지 않음(덮인 화소 0)";
                return result;
            }
            maskBox = new RectInt(minX, minY, maxX - minX + 1, maxY - minY + 1);
            var box = maskBox.Value;
            int cx0 = box.x + box.width / 4, cx1 = box.x + box.width * 3 / 4;
            int cy0 = box.y + box.height / 4, cy1 = box.y + box.height * 3 / 4;
            result["coveredPixels"] = covered;
            result["screenBox"] = new JArray(box.x, box.y, box.width, box.height);
            double centerAlpha = 0;
            int centerN = 0;
            for (int y = cy0; y < cy1; y++)
                for (int x = cx0; x < cx1; x++)
                    if (alpha[y * w + x] >= alphaMin) { centerAlpha += alpha[y * w + x]; centerN++; }
            result["meanCoverageInCenter"] = centerN > 0 ? R(centerAlpha / centerN) : 0;

            JObject Measure(Color32[] black, Color32[] white, string label)
            {
                var a = white != null ? Coverage(black, white) : null;
                double lr = 0, lg = 0, lb = 0;
                int n = 0;
                for (int y = cy0; y < cy1; y++)
                    for (int x = cx0; x < cx1; x++)
                    {
                        int i = y * w + x;
                        if (alpha[i] < alphaMin) continue;
                        double k = a != null ? 1.0 / Math.Max(1e-3, a[i]) : 1.0;
                        lr += Math.Min(1.0, Lin[black[i].r] * k);
                        lg += Math.Min(1.0, Lin[black[i].g] * k);
                        lb += Math.Min(1.0, Lin[black[i].b] * k);
                        n++;
                    }
                if (n == 0) return new JObject { ["label"] = label, ["pixels"] = 0 };
                double mr = ColorMetrics.LinearToSrgb(lr / n), mg = ColorMetrics.LinearToSrgb(lg / n), mb = ColorMetrics.LinearToSrgb(lb / n);
                var lab = ColorMetrics.SrgbToLab(mr, mg, mb);
                return new JObject
                {
                    ["label"] = label,
                    ["pixels"] = n,
                    ["meanSrgb"] = new JArray(R(mr), R(mg), R(mb)),
                    ["meanSrgb8"] = new JArray((int)Math.Round(mr * 255), (int)Math.Round(mg * 255), (int)Math.Round(mb * 255)),
                    ["lab"] = new JArray(R(lab.L, 2), R(lab.A, 2), R(lab.B, 2)),
                    ["deltaE2000VsSpec"] = R(ColorMetrics.DeltaE2000(specLab, lab), 2),
                    ["deltaE76VsSpec"] = R(ColorMetrics.DeltaE76(specLab, lab), 2),
                    ["deltaE2000VsShaderTarget"] = R(ColorMetrics.DeltaE2000(targetLab, lab), 2),
                    ["deltaLVsSpec"] = R(lab.L - specLab.L, 2),
                };
            }

            result["frontal"] = Measure(frontB, frontW, "정면 조명(광원 = 카메라 시선 방향), 형상만");
            result["scene"] = Measure(sceneB, sceneW, "장면 조명(방향광 고도·방위 그대로), 형상만");
            result["inContext"] = Measure(scenePixels, null, "실제 장면 렌더(바닥·하늘·그림자 포함), 같은 화소");
            result["diagnostics"] = new JObject
            {
                ["litFloorBlackBackground"] = Measure(diagLitFloorBlack, null, "진단: 바닥 원래 머티리얼 + 검은 배경(하늘 없음), 같은 화소"),
                ["noFloorSkybox"] = Measure(diagNoFloorSkybox, null, "진단: 하늘 그대로 + 바닥 끔, 같은 화소"),
                ["inContextAgain"] = Measure(diagSceneAgain, null, "진단: 실제 장면을 한 번 더 렌더, 같은 화소"),
            };
            // 불투명이면 0이어야 한다(같은 화소·같은 조명). 크면 측정용 렌더가 실제 장면과 다르게 그려진 것.
            var sceneLab = result["scene"]?["lab"];
            var ctxLab = result["inContext"]?["lab"];
            if (sceneLab != null && ctxLab != null)
                result["sceneVsInContextDeltaE2000"] = R(ColorMetrics.DeltaE2000(
                    new Lab(sceneLab[0].Value<double>(), sceneLab[1].Value<double>(), sceneLab[2].Value<double>()),
                    new Lab(ctxLab[0].Value<double>(), ctxLab[1].Value<double>(), ctxLab[2].Value<double>())), 2);
            return result;
        }

        /// <summary>형상 지표 한 spec분(report.json의 silhouette).</summary>
        public static JObject SilhouetteJson(SilhouetteResult s) => new JObject
        {
            ["circularity"] = R(s.Circularity),
            ["components"] = s.Components,
            ["edgeFalloffPx"] = R(s.EdgeFalloffPx, 2),
            ["maskPixels"] = s.MaskPixels,
            ["perimeterPx"] = R(s.PerimeterPx, 1),
            ["componentsRaw"] = s.ComponentsRaw,
            ["method"] = "덮임 = 장면 조명에서 형상만 검은·흰 배경에 렌더한 화소별 a(색 측정과 같음, 원래 해상도). " +
                         "visiblePixels = a ≥ " + SilhouetteMetrics.VisibleAlpha.ToString(CultureInfo.InvariantCulture) + ", 마스크 = a ≥ " +
                         SilhouetteMetrics.MaskFraction.ToString(CultureInfo.InvariantCulture) + " × maxAlpha. " +
                         "circularity = 4π·넓이/둘레²(마칭 스퀘어 둘레, 원 ≈ 1). components = 8-이웃 덩어리 중 마스크 넓이의 " +
                         SilhouetteMetrics.MinComponentFraction.ToString(CultureInfo.InvariantCulture) + " 이상(componentsRaw = 모두). " +
                         "edgeFalloffPx = (넓이(a ≥ 0.1·max) − 넓이(a ≥ 0.9·max)) / 둘레 = 덮임이 10%→90%로 오르는 띠의 평균 폭(화소).",
        };

        /// <summary>렌더 경로별 집계(spec 수, 지표 평균, frameMsP95 최댓값). 대리 지표다.</summary>
        public static JObject RenderPathSummary(JArray specs)
        {
            var o = new JObject();
            var withPath = specs.Where(s => s.Value<string>("renderPath") != null).ToArray();
            foreach (var g in withPath.GroupBy(s => s.Value<string>("renderPath")).OrderBy(g => g.Key, StringComparer.Ordinal))
            {
                double? Mean(Func<JToken, JToken> pick)
                {
                    var v = g.Select(pick).Where(t => t != null && t.Type != JTokenType.Null).Select(t => t.Value<double>()).ToArray();
                    return v.Length > 0 ? R(v.Average()) : (double?)null;
                }
                var perf = g.Select(s => s["performance"]?["frameMsP95"]).Where(t => t != null).Select(t => t.Value<double>()).ToArray();
                o[g.Key] = new JObject
                {
                    ["specs"] = g.Count(),
                    ["visiblePixelsMean"] = Mean(s => s["visiblePixels"]),
                    ["maxAlphaMean"] = Mean(s => s["maxAlpha"]),
                    ["circularityMean"] = Mean(s => s["silhouette"]?["circularity"]),
                    ["componentsMean"] = Mean(s => s["silhouette"]?["components"]),
                    ["edgeFalloffPxMean"] = Mean(s => s["silhouette"]?["edgeFalloffPx"]),
                    ["frameMsP95Max"] = perf.Length > 0 ? R(perf.Max()) : (double?)null,
                };
            }
            return o;
        }

        /// <summary>material.color의 h·s·l 중 기본값으로 채운 성분(예: ["h", "l"]). 비어 있으면 전부 참여자가 말한 값.</summary>
        public static string[] ColorDefaultComponents(SceneParams p) =>
            new[] { "h", "s", "l" }.Where(k => p.DefaultsUsed.Contains("material.color." + k)).ToArray();

        /// <summary>검은·흰 배경 렌더 쌍 → 화소별 덮임(0–1, 선형 채널 차이의 평균).</summary>
        static float[] Coverage(Color32[] black, Color32[] white)
        {
            var a = new float[black.Length];
            for (int i = 0; i < black.Length; i++)
            {
                double d = (Lin[white[i].r] - Lin[black[i].r]
                          + Lin[white[i].g] - Lin[black[i].g]
                          + Lin[white[i].b] - Lin[black[i].b]) / 3.0;
                a[i] = (float)Math.Max(0.0, Math.Min(1.0, 1.0 - d));
            }
            return a;
        }

        // ── 렌더 통계 ───────────────────────────────────────────────────────
        static readonly (string Key, string Counter)[] ProfilerCounters =
        {
            ("drawCalls", "Draw Calls Count"), ("batches", "Batches Count"), ("setPassCalls", "SetPass Calls Count"),
            ("triangles", "Triangles Count"), ("vertices", "Vertices Count"), ("shadowCasters", "Shadow Casters Count"),
        };

        static JObject RenderStats(Ctx c, Camera cam)
        {
            // 추정값을 교차 확인하려고 ProfilerRecorder(렌더 카운터)도 함께 건다. 에디트 모드 수동 렌더에서는 프레임 경계가 없어
            // 값이 0일 수 있다 → meaningful로 표시하고, 0이면 PlayMode·기기 측정으로 넘긴다.
            var recorders = new List<(string Key, ProfilerRecorder Rec)>();
            foreach (var (key, counter) in ProfilerCounters)
            {
                try { recorders.Add((key, ProfilerRecorder.StartNew(ProfilerCategory.Render, counter))); }
                catch (Exception) { /* 카운터 이름이 버전마다 다를 수 있음 → 빠진 키로 남김 */ }
            }
            var profiler = new JObject();
            try
            {
                cam.targetTexture = c.EyeRt;
                cam.Render();
                cam.targetTexture = null;
                foreach (var (key, rec) in recorders)
                    profiler[key] = new JObject { ["valid"] = rec.Valid, ["current"] = rec.Valid ? rec.CurrentValue : 0, ["last"] = rec.Valid ? rec.LastValue : 0 };
            }
            finally
            {
                foreach (var (_, rec) in recorders) rec.Dispose();
            }
            bool profilerMeaningful = profiler.Properties().Any(pr => pr.Name == "drawCalls"
                && (pr.Value.Value<long>("current") > 0 || pr.Value.Value<long>("last") > 0));
            profiler["meaningful"] = profilerMeaningful;
            profiler["note"] = profilerMeaningful
                ? "ProfilerRecorder 렌더 카운터(current = 진행 중 프레임, last = 직전 완료 프레임). 에디트 모드에서는 여러 Camera.Render가 한 프레임에 합쳐질 수 있음."
                : "배치모드·에디트 모드의 수동 Camera.Render()에서는 렌더 카운터가 프레임 끝에 갱신되지 않아 0 → 실측은 PlayMode 또는 기기(OVR Metrics)에서.";
            var unity = new JObject
            {
                ["drawCalls"] = UnityStats.drawCalls,
                ["batches"] = UnityStats.batches,
                ["setPassCalls"] = UnityStats.setPassCalls,
                ["triangles"] = UnityStats.triangles,
                ["vertices"] = UnityStats.vertices,
                ["shadowCasters"] = UnityStats.shadowCasters,
            };
            bool unityMeaningful = UnityStats.drawCalls > 0 && UnityStats.triangles > 0;
            unity["meaningful"] = unityMeaningful;
            unity["note"] = unityMeaningful
                ? "UnityStats 값(마지막 렌더 프레임 기준). 에디트 모드 수동 Camera.Render()에서는 프레임 경계가 없어 여러 렌더가 합쳐졌을 수 있음 — 직접 계산값과 비교할 것."
                : "배치모드·에디트 모드의 수동 Camera.Render()에서는 UnityStats가 채워지지 않음(0) → 직접 계산값을 쓴다.";

            var planes = GeometryUtility.CalculateFrustumPlanes(cam);
            var lights = UnityEngine.Object.FindObjectsByType<Light>(FindObjectsSortMode.None)
                .Where(l => l.isActiveAndEnabled).ToArray();
            int shadowLights = lights.Count(l => l.shadows != LightShadows.None);
            bool anyShadow = shadowLights > 0 && QualitySettings.shadows != ShadowQuality.Disable;
            float shadowDistance = QualitySettings.shadowDistance;

            int addLights = Math.Max(0, Math.Min(QualitySettings.pixelLightCount, lights.Length) - 1);
            int visible = 0, forwardDraws = 0, shadowDraws = 0, depthDraws = 0;
            long meshTris = 0, forwardTris = 0, shadowTris = 0, depthTris = 0;
            var rows = new JArray();
            foreach (var r in UnityEngine.Object.FindObjectsByType<Renderer>(FindObjectsSortMode.None))
            {
                if (!r.enabled || !r.gameObject.activeInHierarchy) continue;
                var mf = r.GetComponent<MeshFilter>();
                if (mf == null || mf.sharedMesh == null) continue;
                long tris = 0;
                var mesh = mf.sharedMesh;
                for (int s = 0; s < mesh.subMeshCount; s++) tris += (long)mesh.GetIndexCount(s) / 3;
                bool inView = GeometryUtility.TestPlanesAABB(planes, r.bounds);
                int fwd = 0, caster = 0;
                bool transparent = false;
                var passNames = new JArray();
                foreach (var m in r.sharedMaterials)
                {
                    if (m == null) continue;
                    if (m.renderQueue >= (int)RenderQueue.Transparent) transparent = true;
                    for (int i = 0; i < m.passCount; i++)
                    {
                        // 패스 이름은 ForwardBase·ForwardAdd 모두 "FORWARD"라 LightMode 태그로 나눈다
                        string lm = (m.shader.FindPassTagValue(i, LightModeTag).name ?? "").ToUpperInvariant();   // 엔진이 대문자로 돌려준다
                        passNames.Add(lm);
                        if (lm == "FORWARDBASE" || lm == "" || lm == "ALWAYS") fwd++;
                        else if (lm == "FORWARDADD") fwd += addLights;   // 추가 픽셀 광원마다 한 번(광원 1개면 0)
                        else if (lm == "SHADOWCASTER") caster++;
                    }
                }
                bool casts = r.shadowCastingMode != ShadowCastingMode.Off && anyShadow && caster > 0
                             && Vector3.Distance(cam.transform.position, r.bounds.center) <= shadowDistance + r.bounds.extents.magnitude;
                if (inView)
                {
                    visible++;
                    meshTris += tris;
                    forwardDraws += fwd;
                    forwardTris += tris * fwd;
                    if (anyShadow && !transparent)
                    {
                        // 방향광 그림자(화면 공간 그림자)는 카메라 깊이 텍스처를 먼저 그린다 = 불투명 렌더러마다 깊이 패스
                        // (자체 ShadowCaster 패스가 없으면 FallBack 셰이더의 것 1개)
                        int depthPasses = caster > 0 ? caster : 1;
                        depthDraws += depthPasses;
                        depthTris += tris * depthPasses;
                    }
                }
                if (casts)
                {
                    shadowDraws += caster * Math.Max(1, QualitySettings.shadowCascades);
                    shadowTris += tris * caster * Math.Max(1, QualitySettings.shadowCascades);
                }
                rows.Add(new JObject
                {
                    ["name"] = r.name, ["triangles"] = tris, ["inView"] = inView, ["forwardPasses"] = fwd,
                    ["shadowCasterPasses"] = caster, ["castsShadow"] = casts, ["transparent"] = transparent, ["passLightModes"] = passNames,
                });
            }
            int skybox = RenderSettings.skybox != null && cam.clearFlags == CameraClearFlags.Skybox ? 1 : 0;
            int shadowResolve = anyShadow ? 1 : 0;
            int drawsPerEye = forwardDraws + depthDraws + shadowDraws + skybox + shadowResolve;
            long trisPerEye = forwardTris + depthTris + shadowTris;
            return new JObject
            {
                ["unityStats"] = unity,
                ["profilerRecorder"] = profiler,
                ["computed"] = new JObject
                {
                    ["visibleRenderers"] = visible,
                    ["meshTrianglesInView"] = meshTris,
                    ["shadowLights"] = shadowLights,
                    ["drawCallsPerEyeEstimate"] = drawsPerEye,
                    ["drawCallsBreakdown"] = new JObject
                    {
                        ["forward"] = forwardDraws, ["cameraDepth"] = depthDraws, ["shadowMap"] = shadowDraws,
                        ["skybox"] = skybox, ["screenSpaceShadowResolve"] = shadowResolve,
                    },
                    ["submittedTrianglesPerEyeEstimate"] = trisPerEye,
                    ["drawCallsPerStereoFrameMultiPass"] = drawsPerEye * 2,
                    ["note"] = "직접 계산(추정): 렌더러별 패스(LightMode = ForwardBase/ForwardAdd/ShadowCaster)×메시 삼각형. 하늘 메시 삼각형은 제외. " +
                               "눈당 값 = 단일 패스 인스턴싱 스테레오 프레임과 같은 수의 드로콜. 멀티패스(눈마다 Camera.Render, 이 도구의 시간 측정 방식)면 그림자 맵까지 ×2.",
                    ["renderers"] = rows,
                },
            };
        }

        // ── 프레임시간 ───────────────────────────────────────────────────────
        static JObject MeasurePerformance(Ctx c, Camera cam)
        {
            var o = c.O;
            var center = cam.transform.position;
            var right = cam.transform.right;
            var sync = new Texture2D(1, 1, TextureFormat.RGBA32, false, false);
            var times = new List<double>(o.Frames);
            var sw = new Stopwatch();
            try
            {
                cam.targetTexture = c.EyeRt;
                for (int f = 0; f < o.WarmupFrames + o.Frames; f++)
                {
                    sw.Restart();
                    for (int e = 0; e < o.Eyes; e++)
                    {
                        float off = o.Eyes == 2 ? (e == 0 ? -0.5f : 0.5f) * o.Ipd : 0f;
                        cam.transform.position = center + right * off;
                        cam.Render();
                    }
                    var prev = RenderTexture.active;
                    RenderTexture.active = c.EyeRt;
                    sync.ReadPixels(new Rect(0, 0, 1, 1), 0, 0, false);   // GPU 완료까지 기다림
                    RenderTexture.active = prev;
                    sw.Stop();
                    if (f >= o.WarmupFrames) times.Add(sw.Elapsed.TotalMilliseconds);
                }
            }
            finally
            {
                cam.targetTexture = null;
                cam.transform.position = center;
                UnityEngine.Object.DestroyImmediate(sync);
            }
            double p50 = CaptureStats.Percentile(times, 50), p95 = CaptureStats.Percentile(times, 95), max = times.Max();
            return new JObject
            {
                ["eyeWidth"] = o.Width,
                ["eyeHeight"] = o.Height,
                ["eyes"] = o.Eyes,
                ["msaa"] = c.EyeRt.antiAliasing,
                ["frames"] = times.Count,
                ["warmupFrames"] = o.WarmupFrames,
                ["frameMsP50"] = R(p50),
                ["frameMsP95"] = R(p95),
                ["frameMsMax"] = R(max),
                ["frameMsMean"] = R(CaptureStats.Mean(times)),
                ["fpsAtP95"] = R(CaptureStats.Fps(p95), 1),
            };
        }

        // ── 보고서 ───────────────────────────────────────────────────────
        static JObject BuildReport(Ctx c, JArray specs, int fileCount, int msaa)
        {
            var o = c.O;
            int loaded = specs.Count(s => s.Value<bool?>("loaded") == true);
            int captureFailures = specs.Count(s => s.Value<bool?>("captureFailed") == true);
            int errors = specs.Sum(s => s["console"].Value<int>("errors"));
            int exceptions = specs.Sum(s => s["console"].Value<int>("exceptions"));
            var perf = specs.Select(s => s["performance"]).Where(t => t != null).ToArray();
            var stats = specs.Select(s => s["renderStats"]?["computed"]).Where(t => t != null).ToArray();
            double? p95Max = perf.Length > 0 ? perf.Max(t => t.Value<double>("frameMsP95")) : (double?)null;
            double? maxMax = perf.Length > 0 ? perf.Max(t => t.Value<double>("frameMsMax")) : (double?)null;
            int? drawMax = stats.Length > 0 ? stats.Max(t => t.Value<int>("drawCallsPerEyeEstimate")) : (int?)null;
            long? trisMax = stats.Length > 0 ? stats.Max(t => t.Value<long>("submittedTrianglesPerEyeEstimate")) : (long?)null;
            int? shadowLightsMax = stats.Length > 0 ? stats.Max(t => t.Value<int>("shadowLights")) : (int?)null;
            bool profilerAny = specs.Any(s => s["renderStats"]?["profilerRecorder"]?.Value<bool?>("meaningful") == true);

            var ac4 = new JObject
            {
                ["loadErrorsAndExceptionsZero"] = loaded == fileCount && errors == 0 && exceptions == 0,
                ["frameMsP95AtMost13_9"] = p95Max.HasValue && p95Max.Value <= FrameTimeP95LimitMs,
                ["drawCallsPerEyeEstimateAtMost100"] = drawMax.HasValue && drawMax.Value <= DrawCallLimit,
                ["trianglesPerEyeEstimateAtMost300k"] = trisMax.HasValue && trisMax.Value <= TriangleLimit,
                ["realtimeShadowLightsAtMost1"] = shadowLightsMax.HasValue && shadowLightsMax.Value <= ShadowLightLimit,
                ["estimatedItems"] = new JArray("drawCallsPerEyeEstimateAtMost100", "trianglesPerEyeEstimateAtMost300k"),
                ["drawCallsTrianglesMeasuredByProfiler"] = profilerAny,
                ["note"] = "EditMode 테스트 통과는 이 보고서가 아니라 -runTests 결과(xml)로 확인. 프레임시간은 데스크톱 대리 측정. " +
                           "드로콜·삼각형은 실측이 아니라 패스 수 × 메시 삼각형으로 계산한 추정(renderStats.computed). " +
                           (profilerAny ? "ProfilerRecorder 값(renderStats.profilerRecorder)과 비교할 것."
                                        : "UnityStats·ProfilerRecorder가 이 실행 방식에서 0이라 교차 확인하지 못함 → PlayMode·기기 실측 필요."),
            };

            var q = QualitySettings.names[QualitySettings.GetQualityLevel()];
            return new JObject
            {
                ["format"] = ReportFormat,
                ["generatedAtUtc"] = DateTime.UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture),
                ["ok"] = loaded == fileCount && captureFailures == 0 && fileCount > 0,
                ["disclaimer"] = Disclaimer,
                ["system"] = new JObject
                {
                    ["unityVersion"] = Application.unityVersion,
                    ["graphicsDevice"] = SystemInfo.graphicsDeviceName,
                    ["graphicsApi"] = SystemInfo.graphicsDeviceType.ToString(),
                    ["os"] = SystemInfo.operatingSystem,
                    ["batchMode"] = Application.isBatchMode,
                },
                ["rendering"] = new JObject
                {
                    ["pipeline"] = GraphicsSettings.currentRenderPipeline == null ? "Built-in" : GraphicsSettings.currentRenderPipeline.name,
                    ["colorSpace"] = QualitySettings.activeColorSpace.ToString(),
                    ["qualityLevel"] = q,
                    ["msaa"] = msaa,
                    ["shadows"] = QualitySettings.shadows.ToString(),
                    ["shadowResolution"] = QualitySettings.shadowResolution.ToString(),
                    ["shadowDistance"] = QualitySettings.shadowDistance,
                    ["shadowCascades"] = QualitySettings.shadowCascades,
                    ["pixelLightCount"] = QualitySettings.pixelLightCount,
                    ["hdr"] = false,
                    ["postProcessing"] = "없음(색 정확도 우선 — unity/README.md)",
                },
                ["options"] = new JObject
                {
                    ["specDir"] = o.SpecDir, ["width"] = o.Width, ["height"] = o.Height, ["frames"] = o.Frames,
                    ["warmupFrames"] = o.WarmupFrames, ["eyes"] = o.Eyes, ["pngWidth"] = o.PngWidth, ["fovDeg"] = o.FieldOfView,
                    ["eyeHeightM"] = o.EyeHeight, ["ipdM"] = o.Ipd,
                },
                ["timingMethod"] = TimingMethod,
                ["environment"] = EnvironmentJson(c.Env.Settings),
                ["shaders"] = ShaderStatus(),
                ["summary"] = new JObject
                {
                    ["specFiles"] = fileCount,
                    ["loaded"] = loaded,
                    ["captureFailures"] = captureFailures,
                    ["consoleErrors"] = errors,
                    ["consoleExceptions"] = exceptions,
                    ["frameMsP95Max"] = p95Max.HasValue ? R(p95Max.Value) : null,
                    ["frameMsMaxMax"] = maxMax.HasValue ? R(maxMax.Value) : null,
                    ["drawCallsPerEyeMax"] = drawMax,
                    ["submittedTrianglesPerEyeMax"] = trisMax,
                    ["realtimeShadowLights"] = shadowLightsMax,
                    ["color"] = ColorSummary(specs),
                    ["ac4"] = ac4,
                    ["shapes"] = ShapeSummary(specs),
                    ["renderPaths"] = RenderPathSummary(specs),
                },
                ["shapePrefabs"] = new JObject
                {
                    ["folder"] = ShapePrefabMenu.Folder,
                    ["connected"] = new JObject(c.ShapePrefabs.Select(sp => new JProperty(sp.shape,
                        sp.prefab != null ? (JToken)ShapePrefabMenu.PrefabPath(ShapeMapping.ModelFor(sp.shape)) : JValue.CreateNull()))),
                    ["note"] = "모양 값 → 프리팹 경로(null = 프리팹 없음 → 로더가 같은 형상을 코드로 만들고 경고, spec별 shape.viaPrefab = false).",
                },
                ["specs"] = specs,
            };
        }

        /// <summary>
        /// 모양어 판정 집계(docs/shape-mapping.md). byStatus = spec별 shape.status 수, byModel = 적용한 모형별 spec 수,
        /// unmappedValues = 표에 없는 모양 값별 낱말 수와 spec 이름, notAppliedForm·conflict = 해당 낱말이 나온 spec.
        /// </summary>
        public static JObject ShapeSummary(JArray specs)
        {
            var withShape = specs.Where(s => s["shape"] is JObject).ToArray();
            var byStatus = new JObject();
            foreach (var g in withShape.GroupBy(s => s["shape"].Value<string>("status")).OrderBy(g => g.Key, StringComparer.Ordinal))
                byStatus[g.Key ?? "null"] = g.Count();
            var byModel = new JObject();
            foreach (var model in ShapeMapping.Models)
                byModel[model] = withShape.Count(s => s["shape"].Value<string>("model") == model);
            var viaPrefab = withShape.Count(s => s["shape"].Value<bool?>("viaPrefab") == true);
            var viaCode = withShape.Count(s => s["shape"].Value<bool?>("viaPrefab") == false);

            JObject WordsWith(string status)
            {
                var o = new JObject();
                var hits = withShape.SelectMany(s => s["shape"]["words"].Children<JObject>()
                        .Where(w => w.Value<string>("status") == status)
                        .Select(w => (Shape: w.Value<string>("shape") ?? "(값 없음)", Spec: s.Value<string>("spec"))))
                    .ToArray();
                foreach (var g in hits.GroupBy(h => h.Shape).OrderByDescending(g => g.Count()).ThenBy(g => g.Key, StringComparer.Ordinal))
                    o[g.Key] = new JObject
                    {
                        ["words"] = g.Count(),
                        ["specs"] = new JArray(g.Select(h => h.Spec).Distinct().OrderBy(x => x, StringComparer.Ordinal)),
                    };
                return o;
            }

            return new JObject
            {
                ["specs"] = withShape.Length,
                ["byStatus"] = byStatus,
                ["byModel"] = byModel,
                ["viaPrefab"] = viaPrefab,
                ["viaCode"] = viaCode,
                ["unmappedValues"] = WordsWith(ShapeMapping.StatusUnmapped),
                ["notAppliedForm"] = WordsWith(ShapeMapping.StatusNotAppliedForm),
                ["conflict"] = WordsWith(ShapeMapping.StatusConflict),
                ["note"] = "status: applied = 모양 모형 적용, none = 모양어 없음(기본 모형), unmapped_shape = 표에 없는 모양어만 있어 모양 정보 없이 만든 모형, " +
                           "not_applied_form = spec이 mist·shell·fragments를 말해 그 형태 모형을 지킴. 표: round→Sphere, square→Cube, flat→FlatCylinder, pointed→Cone.",
            };
        }

        /// <summary>
        /// 색 ΔE00 요약. 참여자가 h·s·l을 모두 말한 spec(stated)만 1차로 집계하고, 기본값이 섞인 spec(기본 회색 등)은 따로 둔다.
        /// 기본 무채색은 맞추기 쉬워 '색 반영 정확도'를 좋게 보이게 하므로 섞지 않는다(원칙 2).
        /// </summary>
        public static JObject ColorSummary(JArray specs)
        {
            JObject Agg(IEnumerable<JToken> group)
            {
                var g = group.ToArray();
                var o = new JObject { ["specs"] = g.Length };
                foreach (var view in new[] { "primary", "inContext", "scene", "frontal" })
                {
                    var vals = g.Select(s =>
                        {
                            var color = s["color"];
                            string key = view == "primary" ? color?.Value<string>("primary") : view;
                            return key == null ? null : color?[key]?["deltaE2000VsSpec"];
                        })
                        .Where(t => t != null && t.Type != JTokenType.Null).Select(t => t.Value<double>()).ToArray();
                    o[view + "Mean"] = vals.Length > 0 ? R(vals.Average(), 2) : (JToken)JValue.CreateNull();
                    o[view + "Max"] = vals.Length > 0 ? R(vals.Max(), 2) : (JToken)JValue.CreateNull();
                }
                return o;
            }
            var measured = specs.Where(s => s["color"] != null && s["color"]["error"] == null).ToArray();
            var stated = measured.Where(s => s["color"].Value<bool?>("specColorIsDefault") == false);
            var withDefaults = measured.Where(s => s["color"].Value<bool?>("specColorIsDefault") != false);
            return new JObject
            {
                ["stated"] = Agg(stated),
                ["withDefaults"] = Agg(withDefaults),
                ["note"] = "ΔE00(CIEDE2000) vs SceneSpec 색. stated = h·s·l을 모두 참여자가 말한 spec만(1차 보고값). " +
                           "withDefaults = 하나라도 기본값으로 채운 spec(색 반영 정확도에 넣지 않음). primary = 불투명 inContext, 반투명 scene.",
            };
        }

        static JObject EnvironmentJson(EnvironmentSettings s) => new JObject
        {
            ["floorSizeM"] = s.floorSize, ["floorColor"] = Col(s.floorColor), ["gridMajorColor"] = Col(s.gridMajorColor),
            ["gridMinorColor"] = Col(s.gridMinorColor), ["gridLineWidthM"] = s.gridLineWidth, ["gridFadeDistanceM"] = s.gridFadeDistance,
            ["skyZenith"] = Col(s.skyZenith), ["skyHorizon"] = Col(s.skyHorizon), ["skyGround"] = Col(s.skyGround),
            ["ambientSky"] = Col(s.ambientSky), ["ambientEquator"] = Col(s.ambientEquator), ["ambientGround"] = Col(s.ambientGround),
            ["lightColor"] = Col(s.lightColor), ["lightIntensity"] = s.lightIntensity, ["lightElevationDeg"] = s.lightElevation,
            ["lightAzimuthDeg"] = s.lightAzimuth, ["shadowStrength"] = s.shadowStrength, ["softShadows"] = s.softShadows,
            ["reflections"] = s.reflections, ["reflectionResolution"] = s.reflectionResolution,
            ["reflectionMode"] = RenderSettings.defaultReflectionMode.ToString(),
        };

        static JArray ShaderStatus()
        {
            var arr = new JArray();
            foreach (var path in IfsShaders)
            {
                var sh = Resources.Load<Shader>(path);
                if (sh == null)
                {
                    arr.Add(new JObject { ["resource"] = path, ["found"] = false });
                    continue;
                }
                var msgs = new JArray();
                foreach (var m in ShaderUtil.GetShaderMessages(sh))
                    msgs.Add(m.severity + ": " + m.message);
                arr.Add(new JObject
                {
                    ["resource"] = path, ["name"] = sh.name, ["found"] = true, ["supported"] = sh.isSupported,
                    ["hasErrors"] = ShaderUtil.ShaderHasError(sh), ["messages"] = msgs,
                });
            }
            return arr;
        }

        // ── 도우미 ───────────────────────────────────────────────────────
        static Bounds Encapsulate(Renderer[] rs)
        {
            if (rs.Length == 0) return new Bounds(Vector3.zero, Vector3.zero);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
        }

        static string FirstLines(string s, int n)
        {
            if (string.IsNullOrEmpty(s)) return "";
            var lines = s.Split('\n');
            return string.Join("\n", lines.Take(n)).TrimEnd();
        }

        static double R(double v, int digits = 3) => double.IsNaN(v) || double.IsInfinity(v) ? -1 : Math.Round(v, digits);
        static JArray Vec(Vector3 v) => new JArray(R(v.x), R(v.y), R(v.z));
        static JArray Col(Color c) => new JArray(R(c.r), R(c.g), R(c.b));
    }
}
