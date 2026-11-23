// 배치 공간 후보 B·E·F 검증 캡처(G56, 2026-11-24). 참여자 데이터 없음 — 저장소의 합성 spec(목업·렌더 검증용)만 쓴다.
//   Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementEnvironmentCapture.CaptureBatch
//             -outDir <저장소>/docs/validation/environments -specRoot <저장소>/docs/validation -logFile <로그>
// 후보마다(B = neutral + 놓기 도움, E = space + 도움, F = nature + 도움) 배치 실험 씬(PlacementExperimentMenu.BuildObjects)에
// 형상 여섯 개를 '나'에서 2.6 m, 방위 −40…40°에 두고 눈높이 1.6 m에서 찍는다:
//   <후보>_low.png  : 형상 높이 1.2 m(러너 시작 높이 — 눈보다 아래라 배경은 바닥 너머 땅/하늘 아래쪽), 세로 시야 70°, 10° 아래
//   <후보>_high.png : 형상 높이 2.0 m(눈보다 위라 배경은 하늘), 10° 위
//   <후보>_assist.png : 놓기 도움 표시 모의(연습 상자·목표 자리 + 경계 가까이 든 형상의 수직선·바닥 고리·밝아진 경계 띠)
//   <후보>_around.png : 오른쪽 60°·25° 아래(바닥 원판 가장자리와 그 너머)
// 대비: 형상마다 "모두 그린 장면"과 "그 형상만 보이지 않게 한 장면(그림자는 남김)"을 찍어 달라진 화소(어느 채널이든 3/255 이상)를 그 형상의 화면 영역으로 보고,
//   ΔL* = 영역 평균 L*(형상 있음) − 같은 영역 평균 L*(형상 없음 = 바로 뒤 배경), ΔE00 = 두 평균 Lab의 CIEDE2000.
//   (docs/validation/cloud의 ΔL*와 같은 뜻 — 형상 영역 평균 L* − 배경 평균 L* — 이지만 배경을 둘레 고리가 아니라 바로 뒤에서 잰다.)
// 결과: <outDir>/report.json. 테스트 대상이 아닌 도구라 compile-check(dotnet)에서는 빈 파일이다(UNITY_EDITOR 아님).
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class PlacementEnvironmentCapture
    {
        const int W = 1600, H = 900;
        const float EyeY = 1.6f;
        const double FormDistanceM = 2.6;
        static readonly double[] Azimuths = { -40, -24, -8, 8, 24, 40 };

        /// <summary>(파일 이름, specRoot 기준 경로, 설명). 어두운 형상·안개·구름·초록·파랑을 고루.</summary>
        public static readonly (string Id, string RelPath, string Note)[] Forms =
        {
            ("M15", "mock-forms/specs/v1/M15.v1.json", "어두운 형상(l 0.06, 불투명, 기본 형태)"),
            ("M02", "mock-forms/specs/v1/M02.v1.json", "검은 연기(안개, l 0.08, opacity 0.7)"),
            ("M01", "mock-forms/specs/v1/M01.v1.json", "잿빛 안개(l 0.55, s 0.03, opacity 0.5)"),
            ("C01", "cloud/specs/C01_cloud_white.json", "흰 구름(안개, l 0.95)"),
            ("R08", "render/specs/R08_blob_green_bright.json", "초록 덩어리(h 0.33, l 0.5)"),
            ("M05", "mock-forms/specs/v1/M05.v1.json", "짙은 파랑 덩어리(h 0.639, l 0.25)"),
        };

        public static readonly (string Candidate, string Environment)[] Candidates =
        {
            ("B", PlacementConfig.EnvironmentNeutral), ("E", PlacementConfig.EnvironmentSpace), ("F", PlacementConfig.EnvironmentNature),
        };

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
        }

        public static void CaptureBatch()
        {
            int exit = 1;
            try
            {
                string outDir = Arg("-outDir") ?? throw new ArgumentException("-outDir가 없습니다");
                string specRoot = Arg("-specRoot") ?? Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "docs", "validation"));
                Capture(Path.GetFullPath(outDir), Path.GetFullPath(specRoot));
                exit = 0;
            }
            catch (Exception e) { Debug.LogError("[IFS] 공간 후보 캡처 실패: " + e); }
            EditorApplication.Exit(exit);
        }

        public static JObject Capture(string outDir, string specRoot)
        {
            Directory.CreateDirectory(outDir);
            var report = new JObject
            {
                ["tool"] = "PlacementEnvironmentCapture.Capture (G56)",
                ["unityVersion"] = Application.unityVersion,
                ["date"] = "2026-11-24",
                ["imageSize"] = W + "x" + H,
                ["eye"] = "(0, 1.6, 0) — '나'의 자리, 눈높이",
                ["formDistanceM"] = FormDistanceM,
                ["azimuthsDeg"] = new JArray(Azimuths.Cast<object>().ToArray()),
                ["contrastMethod"] = "형상 영역 = 모두 그린 장면과 그 형상만 보이지 않게 한 장면(렌더러를 ShadowsOnly로 — 제 그림자는 남아 형상 영역에 섞이지 않음)이 어느 채널이든 3/255 이상 다른 화소. ΔL* = 영역 평균 L*(형상) − 같은 영역 평균 L*(바로 뒤 배경). ΔE00 = 두 평균 Lab의 CIEDE2000. sRGB 8비트 렌더 화소 기준.",
                ["forms"] = new JArray(Forms.Select(f => new JObject { ["id"] = f.Id, ["spec"] = f.RelPath, ["note"] = f.Note }).ToArray()),
                ["nature"] = new JObject { ["assetId"] = NatureSkyAsset.AssetId, ["sha256"] = NatureSkyAsset.Sha256 },
            };
            var cands = new JArray();
            report["candidates"] = cands;
            foreach (var (cand, env) in Candidates) cands.Add(CaptureCandidate(outDir, specRoot, cand, env));
            File.WriteAllText(Path.Combine(outDir, "report.json"), report.ToString() + "\n");
            Debug.Log("[IFS] 공간 후보 캡처 완료: " + outDir);
            return report;
        }

        static JObject CaptureCandidate(string outDir, string specRoot, string cand, string env)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            foreach (var e in UnityEngine.Object.FindObjectsByType<IFSEnvironment>(FindObjectsSortMode.None)) e.Rebuild();
            var cfg = new PlacementConfig { environment = env, placementAssist = true };
            runner.SetConfig(cfg);
            runner.RefreshSpace();
            var result = new JObject { ["candidate"] = cand, ["environment"] = env, ["placementAssist"] = true, ["applied"] = runner.AppliedEnvironment };
            if (runner.AppliedEnvironment != env) throw new InvalidOperationException($"공간 {env}을 그리지 못했습니다");
            // 씬의 데스크톱 모의 참여자 판·광선은 쓰지 않는다(빈 판). 장면 카메라 대신 캡처 카메라.
            var anchor = new GameObject("capture anchor (eye)");
            anchor.transform.position = new Vector3(0f, EyeY, 0f);
            var cam = MakeCamera();
            var loaders = new List<SceneLoader>();
            try
            {
                var prefabs = ShapePrefabMenu.LoadShapePrefabs();
                foreach (var f in Forms)
                {
                    var go = new GameObject("form " + f.Id);
                    var l = go.AddComponent<SceneLoader>();
                    l.ConfigureForRunner(anchor.transform, new SceneDefaults());
                    l.ConfigureShapePrefabs(prefabs);
                    string path = Path.Combine(specRoot, f.RelPath);
                    if (!l.Load(path)) throw new InvalidOperationException("spec을 불러오지 못했습니다: " + f.RelPath);
                    loaders.Add(l);
                }
                var shots = new JArray();
                result["shots"] = shots;
                foreach (var (suffix, height, pitch) in new[] { ("low", 1.2, 10f), ("high", 2.0, -10f) })
                {
                    Place(loaders, height);
                    cam.transform.SetPositionAndRotation(new Vector3(0f, EyeY, 0f), Quaternion.Euler(pitch, 0f, 0f));
                    string name = $"{cand}_{env}_{suffix}";
                    var full = Render(cam);
                    Save(full, Path.Combine(outDir, name + ".png"));
                    var contrast = new JArray();
                    for (int i = 0; i < loaders.Count; i++)
                    {
                        // 배경 = 그 형상만 보이지 않게(그림자는 남김 — ShadowsOnly). 그래야 바닥에 진 제 그림자가 형상 영역에 섞이지 않는다
                        var rends = loaders[i].Root.GetComponentsInChildren<Renderer>();
                        var modes = rends.Select(x => x.shadowCastingMode).ToArray();
                        var enabled = rends.Select(x => x.enabled).ToArray();
                        foreach (var rd in rends)
                        {
                            if (rd.shadowCastingMode == UnityEngine.Rendering.ShadowCastingMode.Off) rd.enabled = false;   // 그림자를 안 드리우던 것(안개 등)은 그냥 끔
                            else rd.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.ShadowsOnly;
                        }
                        var bg = Render(cam);
                        for (int k = 0; k < rends.Length; k++) { rends[k].shadowCastingMode = modes[k]; rends[k].enabled = enabled[k]; }
                        contrast.Add(Contrast(Forms[i].Id, full, bg));
                        UnityEngine.Object.DestroyImmediate(bg);
                    }
                    UnityEngine.Object.DestroyImmediate(full);
                    shots.Add(new JObject
                    {
                        ["file"] = name + ".png", ["formHeightM"] = height, ["cameraPitchDeg"] = pitch, ["verticalFovDeg"] = cam.fieldOfView,
                        ["contrast"] = contrast,
                    });
                }

                // 놓기 도움 표시 모의: 형상 하나(R08)를 경계 가까이 든 상태 + 연습 상자·목표 자리
                foreach (var l in loaders) l.Root.SetActive(false);
                var held = loaders[Array.FindIndex(Forms, f => f.Id == "R08")];
                held.Root.SetActive(true);
                var heldAt = PlacementGeometry.FromPolar(3.55, 22, 1.0);
                held.Root.transform.position = PlacementSpace.ToUnity(heldAt);
                var space = runner.Space;
                PlacementSpace.SetPractice(space, true, PlacementGeometry.FromPolar(1.5, 0, 1.2),
                    PlacementGeometry.FromPolar(cfg.practiceTargetDistanceM, cfg.practiceTargetAzimuthDeg, cfg.practiceTargetHeightM));
                PlacementSpace.SetAssist(space, true, heldAt, 0.3, cfg.floorRadiusM);
                cam.transform.SetPositionAndRotation(new Vector3(0f, EyeY, 0f), Quaternion.Euler(22f, 0f, 0f));
                string assistName = $"{cand}_{env}_assist";
                var a = Render(cam);
                Save(a, Path.Combine(outDir, assistName + ".png"));
                UnityEngine.Object.DestroyImmediate(a);
                shots.Add(new JObject
                {
                    ["file"] = assistName + ".png",
                    ["note"] = "놓기 도움 표시 모의(실제 세션 단계가 아님): 연습 상자(시작 자리)·목표 자리 테두리, 경계에서 0.45 m 안쪽에 든 형상의 수직선·바닥 고리, 밝아진 경계 띠",
                    ["boundaryGlow"] = Math.Round(PlacementAssistVisuals.BoundaryGlow(PlacementGeometry.HorizontalDistance(heldAt), cfg.floorRadiusM), 3),
                });
                PlacementSpace.SetPractice(space, false, default, default);
                PlacementSpace.SetAssist(space, false, default, 0, cfg.floorRadiusM);
                held.Root.SetActive(false);

                cam.transform.SetPositionAndRotation(new Vector3(0f, EyeY, 0f), Quaternion.Euler(25f, 60f, 0f));
                string aroundName = $"{cand}_{env}_around";
                var r = Render(cam);
                Save(r, Path.Combine(outDir, aroundName + ".png"));
                UnityEngine.Object.DestroyImmediate(r);
                shots.Add(new JObject { ["file"] = aroundName + ".png", ["note"] = "오른쪽 60°, 25° 아래 — 원형 바닥 가장자리와 그 너머(형상 없음)" });
            }
            finally
            {
                foreach (var l in loaders) { if (l != null) { l.Unload(); UnityEngine.Object.DestroyImmediate(l.gameObject); } }
                UnityEngine.Object.DestroyImmediate(cam.gameObject);
                UnityEngine.Object.DestroyImmediate(anchor);
                runner.ResetForNext();
            }
            return result;
        }

        static void Place(List<SceneLoader> loaders, double height)
        {
            for (int i = 0; i < loaders.Count; i++)
            {
                var p = PlacementSpace.ToUnity(PlacementGeometry.FromPolar(FormDistanceM, Azimuths[i], height));
                var look = new Vector3(-p.x, 0f, -p.z);
                loaders[i].Root.transform.SetPositionAndRotation(p, Quaternion.LookRotation(look.normalized, Vector3.up));
                loaders[i].Root.SetActive(true);
            }
        }

        static JObject Contrast(string id, Texture2D full, Texture2D bg)
        {
            var a = full.GetPixels32();
            var b = bg.GetPixels32();
            double fl = 0, fa = 0, fb = 0, bl = 0, ba = 0, bb = 0;
            int n = 0;
            for (int i = 0; i < a.Length; i++)
            {
                int d = Math.Max(Math.Abs(a[i].r - b[i].r), Math.Max(Math.Abs(a[i].g - b[i].g), Math.Abs(a[i].b - b[i].b)));
                if (d < 3) continue;
                var la = ColorMetrics.SrgbToLab(a[i].r / 255.0, a[i].g / 255.0, a[i].b / 255.0);
                var lb = ColorMetrics.SrgbToLab(b[i].r / 255.0, b[i].g / 255.0, b[i].b / 255.0);
                fl += la.L; fa += la.A; fb += la.B;
                bl += lb.L; ba += lb.A; bb += lb.B;
                n++;
            }
            var o = new JObject { ["form"] = id, ["pixels"] = n };
            if (n == 0) { o["deltaL"] = null; o["deltaE00"] = null; return o; }
            var mf = new Lab(fl / n, fa / n, fb / n);
            var mb = new Lab(bl / n, ba / n, bb / n);
            o["formL"] = Math.Round(mf.L, 2);
            o["backgroundL"] = Math.Round(mb.L, 2);
            o["deltaL"] = Math.Round(mf.L - mb.L, 2);
            o["deltaE00"] = Math.Round(ColorMetrics.DeltaE2000(mf, mb), 2);
            return o;
        }

        static Camera MakeCamera()
        {
            var go = new GameObject("environment capture camera");
            var cam = go.AddComponent<Camera>();
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 1000f;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            cam.enabled = false;
            cam.aspect = (float)W / H;
            cam.fieldOfView = 70f;
            cam.clearFlags = CameraClearFlags.Skybox;
            return cam;
        }

        static Texture2D Render(Camera cam)
        {
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var prevActive = RenderTexture.active;
            try
            {
                cam.targetTexture = rt;
                cam.Render();
                cam.Render();
                cam.targetTexture = null;
                RenderTexture.active = rt;
                var tex = new Texture2D(W, H, TextureFormat.RGBA32, false);
                tex.ReadPixels(new Rect(0, 0, W, H), 0, 0, false);
                tex.Apply();
                return tex;
            }
            finally
            {
                RenderTexture.active = prevActive;
                cam.targetTexture = null;
                rt.Release();
                UnityEngine.Object.DestroyImmediate(rt);
            }
        }

        static void Save(Texture2D tex, string path) => File.WriteAllBytes(path, tex.EncodeToPNG());
    }
}
#endif
