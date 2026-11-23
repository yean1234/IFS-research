// 배치 실험 화면 캡처(사용성 점검용, 2026-11-23 G44). 참여자 데이터 없음 — 합성 spec(EX02)과 문구 파일만 쓴다.
//
// 1) 참여자 판(배치모드, 에디트 모드 렌더):
//    Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementUiCapture.CapturePanelsBatch
//              -outDir <폴더> [-recordRoot <임시 기록 루트>] -logFile <로그>
//    → unity_panel_*.png(눈 자리에서 판을 본 장면, 세로 시야 28.8° = 720 px → 약 25 px/°, Quest 3 화소 밀도 근사),
//      unity_scene_item.png(데스크톱 모의 시점, 물체와 판), unity_metrics.json(글자 높이 시야각·대비비 실측).
// 2) 실험자 화면(IMGUI는 Play의 Game 창에서만 그려진다 — 배치모드가 아니라 에디터 창으로 실행):
//    Unity.exe -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementUiCapture.CaptureGuiInteractive
//              -outDir <폴더> [-recordRoot <임시 기록 루트>] -logFile <로그>
//    → unity_gui_*.png(Game 창 스크린숏: 실험자 화면 + 데스크톱 모의 참여자 시점). 끝나면 에디터를 닫는다.
//    헤드셋은 쓰지 않는다(Play에서 OpenXR 초기화가 실패해도 계속된다). Play 뒤 Unity가 QualitySettings.asset·
//    OpenXRPackageSettings.asset을 다시 쓰면 git checkout으로 되돌린다.
// 기록 루트를 주지 않으면 OS 임시 폴더(저장소 밖)에 쓴다. 캡처 PNG 크기는 원본 그대로 — 문서용 축소는 따로.
// 테스트 대상이 아닌 도구라 compile-check(dotnet)에서는 빈 파일이다(UNITY_EDITOR 아님).
#if UNITY_EDITOR
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Reflection;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class PlacementUiCapture
    {
        public const string ScaleAFile = "IFS/placement_task.scaleA.v0.json";
        public const string DefaultFile = "IFS/placement_task.v0.json";
        const int W = 1280, H = 720;
        const float EyeFovDeg = 28.8f;   // 720 px / 28.8° = 25 px/°
        const BindingFlags Any = BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.Public;

        static string Arg(string name)
        {
            var a = Environment.GetCommandLineArgs();
            int i = Array.IndexOf(a, name);
            return i >= 0 && i + 1 < a.Length ? a[i + 1] : null;
        }

        static string ExampleSpec() => Path.GetFullPath(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX02.json"));

        static string TempRecordRoot() => Arg("-recordRoot") ?? Path.Combine(Path.GetTempPath(), "ifs-ui-capture-records");

        // ── 1) 참여자 판 ─────────────────────────────────────────────────
        public static void CapturePanelsBatch()
        {
            int exit = 1;
            try
            {
                string outDir = Arg("-outDir") ?? throw new ArgumentException("-outDir가 없습니다");
                CapturePanels(Path.GetFullPath(outDir), TempRecordRoot());
                exit = 0;
            }
            catch (Exception e) { Debug.LogError("[IFS] UI 캡처(판) 실패: " + e); }
            EditorApplication.Exit(exit);
        }

        public static void CapturePanels(string outDir, string recordRoot)
        {
            Directory.CreateDirectory(outDir);
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = PlacementExperimentMenu.BuildObjects();
            foreach (var env in UnityEngine.Object.FindObjectsByType<IFSEnvironment>(FindObjectsSortMode.None)) env.Rebuild();
            var metrics = new JObject
            {
                ["tool"] = "PlacementUiCapture.CapturePanels",
                ["unityVersion"] = Application.unityVersion,
                ["eyeFovDeg"] = EyeFovDeg,
                ["imageSize"] = W + "x" + H,
                ["note"] = "합성 spec EX02·문구 파일만. 시야각 = 2·atan(높이 / (2·눈–판 중심 거리)). 글자 높이는 한 글자 TextMesh의 localBounds(잉크 높이에 가까움). 대비비는 이 렌더의 화소(sRGB)로 WCAG 2.x 식.",
            };
            var shots = new JArray();
            metrics["shots"] = shots;
            var cam = MakeCaptureCamera();
            try
            {
                runner.SetRecordRoot(recordRoot);
                runner.SelectTaskText(ScaleAFile);
                var cfg = new PlacementConfig { condition = PlacementConfig.ConditionView, baselineSeconds = 1, participantRatesWithController = true };
                runner.BeginAuto(new PlacementAutoScript(), cfg);
                runner.ParticipantNumberText = "1";
                runner.SpecPathText = ExampleSpec();
                if (!runner.Check()) throw new InvalidOperationException("확인 오류: " + string.Join("; ", runner.Errors));
                if (!runner.StartSession()) throw new InvalidOperationException("시작 실패: " + string.Join("; ", runner.Errors));
                var panel = runner.Panel;
                var s = runner.Session;
                metrics["glyph"] = MeasureGlyphs(panel, cam);

                // intro(안내 글)
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_intro", null));
                metrics["backgroundLighting"] = MeasureBackgroundLighting(cam, panel);
                // 평정 지시문(scaleA 공통 지시문, 긴 글)
                Advance(runner, () => s.ItemsInstructionActive);
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_instruction", null));
                // 첫 문항 A1(7점 모두 기준점), 참여자 컨트롤러로 6을 고르는 중
                Advance(runner, () => s.CurrentItem != null);
                SetCursor(runner, 6);
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_item7_cursor", 6));
                // 같은 장면을 데스크톱 모의 시점(눈높이 1.6 m, 18° 아래, 세로 시야 60°)으로: 물체와 판의 자리
                shots.Add(ShotDesktop(cam, panel, outDir, "unity_scene_item"));
                // 고르기 전(커서 없음)
                SetCursor(runner, null);
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_item7_nocursor", null));
                // 양 끝 기준점만 있는 문항(기본 문구 파일의 own과 같은 형태 — scaleA의 S5: 1·7만)
                var ends = runner.TaskText.Items.First(i => i.Key == "S5");
                panel.ShowItem(ends, 4, PanelCenter(runner), Eye(runner));
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_item7_ends_cursor", 4));
                // 0–10(11칸) 배치 확인용: 문구 파일에 0–10 문항이 없어 S5의 글·양 끝 기준점을 그대로 쓰고 범위만 0–10으로(화면 배치 점검용, 문구 아님)
                var wide = new PlacementItem { Key = "layout_check_0_10", Text = ends.Text, When = new[] { "pre" }, Min = 0, Max = 10, AnchorLow = ends.AnchorLow, AnchorHigh = ends.AnchorHigh };
                panel.ShowItem(wide, 7, PanelCenter(runner), Eye(runner));
                shots.Add(ShotEye(cam, panel, outDir, "unity_panel_item11_cursor", 7));
            }
            finally
            {
                runner.ResetForNext();
                UnityEngine.Object.DestroyImmediate(cam.gameObject);
            }
            File.WriteAllText(Path.Combine(outDir, "unity_metrics.json"), metrics.ToString() + "\n");
            Debug.Log("[IFS] UI 캡처(판) 완료: " + outDir);
        }

        static void Advance(PlacementRunner runner, Func<bool> until)
        {
            for (int i = 0; i < 200000 && !until(); i++) runner.Tick(0.02);
            if (!until()) throw new InvalidOperationException("원하는 단계에 닿지 못했습니다: " + runner.Session?.PhaseLabel);
        }

        static Vector3 PanelCenter(PlacementRunner r) =>
            new Vector3(0f, (float)GetField(r, "textHeightM"), (float)GetField(r, "textForwardM"));

        static Vector3 Eye(PlacementRunner r) => new Vector3(0f, (float)GetField(r, "anchorEyeHeightM"), 0f);

        static void SetCursor(PlacementRunner runner, int? v)
        {
            var f = typeof(PlacementSession).GetField("_cursor", Any) ?? throw new MissingFieldException("PlacementSession._cursor");
            f.SetValue(runner.Session, v);
            typeof(PlacementRunner).GetMethod("ApplyVisuals", Any).Invoke(runner, null);
        }

        static object GetField(object o, string name)
        {
            var f = o.GetType().GetField(name, Any) ?? throw new MissingFieldException(o.GetType().Name + "." + name);
            return f.GetValue(o);
        }

        static object TryField(object o, string name) => o.GetType().GetField(name, Any)?.GetValue(o);

        static Camera MakeCaptureCamera()
        {
            var go = new GameObject("UI capture camera");
            var cam = go.AddComponent<Camera>();
            cam.nearClipPlane = 0.05f;
            cam.farClipPlane = 1000f;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            cam.enabled = false;
            cam.aspect = (float)W / H;
            return cam;
        }

        static JObject ShotEye(Camera cam, PlacementTextPanel panel, string outDir, string name, int? cursor)
        {
            var eye = new Vector3(0f, 1.6f, 0f);
            var center = panel.PanelCenter;
            cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(center - eye, Vector3.up));
            cam.fieldOfView = EyeFovDeg;
            var tex = Render(cam);
            Save(tex, Path.Combine(outDir, name + ".png"));
            var shot = new JObject
            {
                ["file"] = name + ".png",
                ["view"] = "eye(0,1.6,0) → 판 중심, 세로 시야 " + EyeFovDeg.ToString(CultureInfo.InvariantCulture) + "°",
                ["panelText"] = panel.CurrentText,
                ["panelSizeM"] = new JArray(Math.Round(panel.PanelSizeM.x, 4), Math.Round(panel.PanelSizeM.y, 4)),
                ["eyeToPanelCenterM"] = Math.Round(Vector3.Distance(eye, center), 4),
                ["panelWidthDeg"] = Math.Round(2 * Math.Atan(panel.PanelSizeM.x / 2 / Vector3.Distance(eye, center)) * 180 / Math.PI, 2),
                ["contrast"] = MeasureContrast(cam, tex, panel, cursor),
            };
            UnityEngine.Object.DestroyImmediate(tex);
            return shot;
        }

        static JObject ShotDesktop(Camera cam, PlacementTextPanel panel, string outDir, string name)
        {
            cam.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), Quaternion.Euler(18f, 0f, 0f));
            cam.fieldOfView = 60f;
            var tex = Render(cam);
            Save(tex, Path.Combine(outDir, name + ".png"));
            var shot = new JObject { ["file"] = name + ".png", ["view"] = "desktop(0,1.6,0) 18° 아래, 세로 시야 60°", ["panelText"] = panel.CurrentText };
            UnityEngine.Object.DestroyImmediate(tex);
            return shot;
        }

        static Texture2D Render(Camera cam)
        {
            var rt = new RenderTexture(W, H, 24, RenderTextureFormat.ARGB32, RenderTextureReadWrite.sRGB) { antiAliasing = 4 };
            var prevActive = RenderTexture.active;
            try
            {
                cam.targetTexture = rt;
                cam.Render();
                cam.Render();   // 동적 글꼴 텍스처가 첫 렌더에서 다시 만들어질 수 있어 한 번 더
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

        // ── 측정 ─────────────────────────────────────────────────────────
        /// <summary>판과 같은 글꼴·크기로 한 글자("가", "7")를 흰 바탕에 크게 찍어 잉크 높이(어두운 화소 행의 범위)를 재고,
        /// "가"와 "가\n가"의 경계 높이 차로 줄 간격을 잰다.</summary>
        static JObject MeasureGlyphs(PlacementTextPanel panel, Camera cam)
        {
            var font = (Font)TryField(panel, "_font") ?? Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf");
            int fontSize = (int)GetField(panel, "fontSize");
            float body = (float)GetField(panel, "characterSize");
            float label = (float)GetField(panel, "labelCharacterSize");
            float d = Vector3.Distance(new Vector3(0f, 1.6f, 0f), panel.PanelCenter);
            var o = new JObject
            {
                ["font"] = font != null ? font.name : null,
                ["fontSize"] = fontSize,
                ["eyeToPanelCenterM"] = Math.Round(d, 4),
            };
            var lineSpacing = TryField(panel, "_body") is TextMesh bodyTm ? bodyTm.lineSpacing : 1f;
            o["bodyTextMeshLineSpacing"] = lineSpacing;
            // 평정 숫자: 2026-11-23 전에는 본문과 같은 크기(numberCharacterSize 필드가 없음)
            float number = TryField(panel, "numberCharacterSize") is float nf ? nf : body;
            foreach (var (role, size) in new[] { ("body", body), ("number", number), ("label", label) })
            {
                float nominal = size * fontSize * 0.1f;
                var r = new JObject
                {
                    ["characterSize"] = size,
                    ["nominalEmM"] = Math.Round(nominal, 4),
                    ["nominalEmDeg"] = Math.Round(Deg(nominal, d), 3),
                };
                foreach (var probe in new[] { "가", "7" })
                {
                    float h = ProbeInkHeight(font, fontSize, size, probe, cam);
                    r["inkHeightM_" + probe] = Math.Round(h, 4);
                    r["inkHeightDeg_" + probe] = Math.Round(Deg(h, d), 3);
                }
                float spacing = role == "body" ? lineSpacing : 1f;   // 숫자·기준점 뜻은 TextMesh 기본 줄 간격
                float one = ProbeBoundsHeight(font, fontSize, size, "가", spacing, cam);
                float two = ProbeBoundsHeight(font, fontSize, size, "가\n가", spacing, cam);
                r["linePitchM"] = Math.Round(two - one, 4);
                r["linePitchEm"] = Math.Round((two - one) / nominal, 3);
                o[role] = r;
            }
            return o;
        }

        static double Deg(double size, double dist) => 2 * Math.Atan(size / 2 / dist) * 180 / Math.PI;

        static GameObject Probe(Font font, int fontSize, float charSize, string text, float lineSpacing)
        {
            var go = new GameObject("glyph probe");
            var tm = go.AddComponent<TextMesh>();
            tm.font = font;
            tm.fontSize = fontSize;
            tm.characterSize = charSize;
            tm.lineSpacing = lineSpacing;
            tm.anchor = TextAnchor.MiddleCenter;
            tm.color = Color.black;
            tm.text = text;
            var r = go.GetComponent<MeshRenderer>();
            if (font != null) r.sharedMaterial = font.material;
            go.transform.SetPositionAndRotation(new Vector3(0f, -50f, 1f), Quaternion.identity);
            return go;
        }

        static float ProbeBoundsHeight(Font font, int fontSize, float charSize, string text, float lineSpacing, Camera cam)
        {
            var go = Probe(font, fontSize, charSize, text, lineSpacing);
            try
            {
                cam.transform.SetPositionAndRotation(new Vector3(0f, -50f, 0f), Quaternion.identity);
                cam.fieldOfView = 30f;
                UnityEngine.Object.DestroyImmediate(Render(cam));
                return go.GetComponent<MeshRenderer>().localBounds.size.y;
            }
            finally { UnityEngine.Object.DestroyImmediate(go); }
        }

        /// <summary>잉크 높이(m): 1 m 앞의 글자를 세로 시야 8°(720 px)로 찍어 어두운 화소(상대 휘도 0.5 미만)가 있는 행의 범위.</summary>
        static float ProbeInkHeight(Font font, int fontSize, float charSize, string text, Camera cam)
        {
            var go = Probe(font, fontSize, charSize, text, 1f);
            var flags = cam.clearFlags;
            var back = cam.backgroundColor;
            try
            {
                const float fov = 8f;
                cam.transform.SetPositionAndRotation(new Vector3(0f, -50f, 0f), Quaternion.identity);
                cam.fieldOfView = fov;
                cam.clearFlags = CameraClearFlags.SolidColor;
                cam.backgroundColor = Color.white;
                var t = Render(cam);
                int top = -1, bottom = -1;
                for (int y = 0; y < H; y++)
                {
                    bool ink = false;
                    for (int x = 0; x < W && !ink; x++) ink = Lum(t.GetPixel(x, y)) < 0.5;
                    if (!ink) continue;
                    if (bottom < 0) bottom = y;
                    top = y;
                }
                UnityEngine.Object.DestroyImmediate(t);
                if (top < 0) return 0f;
                double metersPerPx = 2.0 * Math.Tan(fov * Math.PI / 360.0) / H;   // 1 m 거리
                return (float)((top - bottom + 1) * metersPerPx);
            }
            finally
            {
                cam.clearFlags = flags;
                cam.backgroundColor = back;
                UnityEngine.Object.DestroyImmediate(go);
            }
        }

        /// <summary>화소 대비: 판 배경(판 안쪽 가장자리 띠의 중앙값) 대 본문 글(본문 영역의 가장 어두운 화소),
        /// 고른 칸이 있으면 그 숫자(가장 어두운 화소) 대 그 칸 바탕(칸 가장자리 안쪽 띠 중앙값).</summary>
        static JObject MeasureContrast(Camera cam, Texture2D tex, PlacementTextPanel panel, int? cursor)
        {
            var o = new JObject();
            var bgGo = TryField(panel, "_bg") as GameObject;
            var body = TryField(panel, "_body") as TextMesh;
            if (bgGo == null || body == null) return o;
            var bgRect = ScreenRect(cam, bgGo.transform, new Bounds(Vector3.zero, new Vector3(1f, 1f, 0f)));
            // 판 위 가장자리 안쪽 띠(여백, 글이 없는 곳): 위에서 3–9 px
            var bg = Median(Pixels(tex, new RectInt(bgRect.xMin + 8, bgRect.yMax - 9, Math.Max(1, bgRect.width - 16), 6)).ToList());
            o["panelScreenRect"] = $"{bgRect.xMin},{bgRect.yMin},{bgRect.width}x{bgRect.height}";
            o["panelBackgroundSrgb"] = Hex(bg);
            var text = Darkest(Pixels(tex, TextRect(cam, body, tex)));
            o["bodyTextSrgb"] = Hex(text);
            o["bodyContrast"] = Math.Round(PlacementPanelMetrics.ContrastRatio(Lum(text), Lum(bg)), 2);
            var labels = TryField(panel, "_labels") as List<TextMesh>;
            var numbers = TryField(panel, "_numbers") as List<TextMesh>;
            if (labels != null && labels.Count > 0 && labels[0].gameObject.activeSelf && !string.IsNullOrEmpty(labels[0].text))
            {
                var lt = Darkest(Pixels(tex, TextRect(cam, labels[0], tex)));
                o["firstLabelSrgb"] = Hex(lt);
                o["firstLabelContrast"] = Math.Round(PlacementPanelMetrics.ContrastRatio(Lum(lt), Lum(bg)), 2);
            }
            if (numbers != null && numbers.Count > 0 && numbers[0].gameObject.activeSelf)
            {
                var nt = Darkest(Pixels(tex, TextRect(cam, numbers[0], tex)));
                o["firstNumberSrgb"] = Hex(nt);
                o["firstNumberContrast"] = Math.Round(PlacementPanelMetrics.ContrastRatio(Lum(nt), Lum(bg)), 2);
            }
            var sel = numbers?.FirstOrDefault(n => n.gameObject.activeSelf && n.text.Contains("<b>"));
            if (cursor.HasValue && sel != null)
            {
                var r = TextRect(cam, sel, tex);
                var num = Darkest(Pixels(tex, r));
                // 고른 칸 바탕: 숫자 글자 상자 바로 위 2 px 띠(글자 밖)
                var cell = Median(Pixels(tex, new RectInt(r.xMin, Math.Min(tex.height - 3, r.yMax + 2), r.width, 2)).ToList());
                o["selectedNumberSrgb"] = Hex(num);
                o["selectedCellBackgroundSrgb"] = Hex(cell);
                o["selectedNumberContrast"] = Math.Round(PlacementPanelMetrics.ContrastRatio(Lum(num), Lum(cell)), 2);
                int idx = numbers.IndexOf(sel);
                if (labels != null && idx < labels.Count && !string.IsNullOrEmpty(labels[idx].text))
                {
                    var sl = Darkest(Pixels(tex, TextRect(cam, labels[idx], tex)));
                    o["selectedLabelSrgb"] = Hex(sl);
                    o["selectedLabelContrast"] = Math.Round(PlacementPanelMetrics.ContrastRatio(Lum(sl), Lum(cell)), 2);
                }
            }
            return o;
        }

        /// <summary>판 배경 재질의 방출(emission)을 끄고 다시 찍어, 조명만으로 보이는 배경색과 지금 배경색을 비교한다.</summary>
        static JObject MeasureBackgroundLighting(Camera cam, PlacementTextPanel panel)
        {
            var o = new JObject();
            var mat = TryField(panel, "_bgMat") as Material;
            var bgGo = TryField(panel, "_bg") as GameObject;
            if (mat == null || bgGo == null) return o;
            o["shader"] = mat.shader != null ? mat.shader.name : null;
            o["materialColor"] = "#" + ColorUtility.ToHtmlStringRGB(mat.color);
            o["emissionColor"] = mat.HasProperty("_EmissionColor") ? "#" + ColorUtility.ToHtmlStringRGB(mat.GetColor("_EmissionColor")) : null;
            foreach (var (key, off) in new[] { ("rendered", false), ("renderedEmissionOff", true) })
            {
                Color saved = mat.HasProperty("_EmissionColor") ? mat.GetColor("_EmissionColor") : Color.black;
                if (off && mat.HasProperty("_EmissionColor")) mat.SetColor("_EmissionColor", Color.black);
                var eye = new Vector3(0f, 1.6f, 0f);
                cam.transform.SetPositionAndRotation(eye, Quaternion.LookRotation(panel.PanelCenter - eye, Vector3.up));
                cam.fieldOfView = EyeFovDeg;
                var tex = Render(cam);
                var r = ScreenRect(cam, bgGo.transform, new Bounds(Vector3.zero, new Vector3(1f, 1f, 0f)));
                o[key] = Hex(Median(Pixels(tex, new RectInt(r.xMin + 8, r.yMax - 9, Math.Max(1, r.width - 16), 6)).ToList()));
                UnityEngine.Object.DestroyImmediate(tex);
                if (mat.HasProperty("_EmissionColor")) mat.SetColor("_EmissionColor", saved);
            }
            return o;
        }

        static RectInt TextRect(Camera cam, TextMesh tm, Texture2D tex) => Clip(ScreenRect(cam, tm.transform, tm.GetComponent<Renderer>().localBounds), tex);

        /// <summary>로컬 경계 상자의 8 모서리를 화면에 투영한 사각형(판이 기울어 있어 세계 AABB는 쓰지 않는다).</summary>
        static RectInt ScreenRect(Camera cam, Transform t, Bounds local)
        {
            float xmin = float.MaxValue, ymin = float.MaxValue, xmax = float.MinValue, ymax = float.MinValue;
            for (int i = 0; i < 8; i++)
            {
                var p = new Vector3((i & 1) == 0 ? local.min.x : local.max.x, (i & 2) == 0 ? local.min.y : local.max.y, (i & 4) == 0 ? local.min.z : local.max.z);
                var v = cam.WorldToViewportPoint(t.TransformPoint(p));
                var s = new Vector2(v.x * W, v.y * H);   // 화면 크기가 아니라 렌더 텍스처 크기 기준
                xmin = Mathf.Min(xmin, s.x); xmax = Mathf.Max(xmax, s.x); ymin = Mathf.Min(ymin, s.y); ymax = Mathf.Max(ymax, s.y);
            }
            return new RectInt(Mathf.FloorToInt(xmin), Mathf.FloorToInt(ymin), Mathf.CeilToInt(xmax - xmin), Mathf.CeilToInt(ymax - ymin));
        }

        static RectInt Clip(RectInt r, Texture2D t)
        {
            int x0 = Mathf.Clamp(r.xMin, 0, t.width - 1), y0 = Mathf.Clamp(r.yMin, 0, t.height - 1);
            int x1 = Mathf.Clamp(r.xMax, x0 + 1, t.width), y1 = Mathf.Clamp(r.yMax, y0 + 1, t.height);
            return new RectInt(x0, y0, x1 - x0, y1 - y0);
        }

        static IEnumerable<Color32> Pixels(Texture2D t, RectInt r)
        {
            r = Clip(r, t);
            for (int y = r.yMin; y < r.yMax; y++)
                for (int x = r.xMin; x < r.xMax; x++)
                    yield return t.GetPixel(x, y);
        }

        static double Lum(Color32 c) => PlacementPanelMetrics.RelativeLuminance(c.r / 255.0, c.g / 255.0, c.b / 255.0);
        static Color32 Darkest(IEnumerable<Color32> px) => px.OrderBy(Lum).First();
        static Color32 Median(List<Color32> px) => px.OrderBy(Lum).ElementAt(px.Count / 2);
        static string Hex(Color32 c) => $"#{c.r:X2}{c.g:X2}{c.b:X2}";

        // ── 2) 실험자 화면(에디터 Play) ───────────────────────────────────
        const string KeyOut = "IFS.UiCapture.OutDir", KeyRecord = "IFS.UiCapture.RecordRoot", KeyStep = "IFS.UiCapture.Step";

        public static void CaptureGuiInteractive()
        {
            string outDir = Path.GetFullPath(Arg("-outDir") ?? throw new ArgumentException("-outDir가 없습니다"));
            Directory.CreateDirectory(outDir);
            SessionState.SetString(KeyOut, outDir);
            SessionState.SetString(KeyRecord, TempRecordRoot());
            SessionState.SetInt(KeyStep, 0);
            EditorSceneManager.OpenScene(PlacementExperimentMenu.ScenePath, OpenSceneMode.Single);
            var gv = EditorWindow.GetWindow(typeof(EditorWindow).Assembly.GetType("UnityEditor.GameView"));
            gv.maximized = true;
            EditorApplication.EnterPlaymode();
        }

        [InitializeOnLoad]
        static class GuiDriver
        {
            static double _next;
            static GuiDriver() { EditorApplication.update += Update; }

            static void Update()
            {
                string outDir = SessionState.GetString(KeyOut, "");
                if (outDir.Length == 0) return;
                int step = SessionState.GetInt(KeyStep, 0);
                if (!EditorApplication.isPlaying)
                {
                    if (step >= 100)
                    {
                        SessionState.EraseString(KeyOut);
                        var gv = EditorWindow.GetWindow(typeof(EditorWindow).Assembly.GetType("UnityEditor.GameView"));
                        gv.maximized = false;
                        Debug.Log("[IFS] UI 캡처(실험자 화면) 완료: " + outDir);
                        EditorApplication.Exit(0);
                    }
                    return;
                }
                double now = EditorApplication.timeSinceStartup;
                if (_next == 0) { _next = now + 3.0; return; }
                if (now < _next) return;
                try { step = Run(step, outDir); }
                catch (Exception e)
                {
                    Debug.LogError("[IFS] UI 캡처(실험자 화면) 실패: " + e);
                    step = 100;
                    EditorApplication.ExitPlaymode();
                }
                SessionState.SetInt(KeyStep, step);
                _next = now + 1.2;
            }

            static void Shot(string outDir, string name) => ScreenCapture.CaptureScreenshot(Path.Combine(outDir, name + ".png"));

            static int Run(int step, string outDir)
            {
                var runner = UnityEngine.Object.FindFirstObjectByType<PlacementRunner>();
                if (runner == null) throw new InvalidOperationException("PlacementRunner가 없습니다");
                switch (step)
                {
                    case 0:
                        var head = UnityEngine.Object.FindFirstObjectByType<HeadPoseProvider>();
                        if (head != null)
                        {
                            typeof(HeadPoseProvider).GetField("_pitch", Any)?.SetValue(head, 18f);
                            typeof(HeadPoseProvider).GetField("_yaw", Any)?.SetValue(head, 0f);
                            typeof(HeadPoseProvider).GetField("_desktopInit", Any)?.SetValue(head, true);
                        }
                        // 화면에 로컬 절대 경로가 찍히지 않게: spec 목록 폴더를 프로젝트 기준 상대 경로(합성 예시)로
                        runner.SpecFolderText = "Assets/StreamingAssets/IFS/examples";
                        typeof(PlacementRunner).GetMethod("RefreshSpecList", Any)?.Invoke(runner, null);
                        Shot(outDir, "unity_gui_setup");
                        return 1;
                    case 1:
                        runner.SetRecordRoot(SessionState.GetString(KeyRecord, TempRecordRoot()));
                        runner.SelectTaskText(ScaleAFile);
                        runner.SetConfig(new PlacementConfig
                        {
                            condition = PlacementConfig.ConditionView, baselineSeconds = 1, participantRatesWithController = true,
                            inputMode = PlacementConfig.InputModeDesktop,
                        });
                        runner.ParticipantNumberText = "1";
                        runner.SpecPathText = ExampleSpec();
                        runner.Check();
                        return 2;
                    case 2:
                        Shot(outDir, "unity_gui_checked");
                        return 3;
                    case 3:
                        runner.PressConfirm();   // 시작 → intro
                        return 4;
                    case 4:
                        Shot(outDir, "unity_gui_run_intro");
                        return 5;
                    case 5:
                        runner.PressConfirm();   // intro → baseline(1 s) → 평정 지시문
                        return 6;
                    case 6:
                        if (runner.Session == null || !runner.Session.ItemsInstructionActive) return 6;
                        runner.PressConfirm();   // 지시문 → 첫 문항
                        return 7;
                    case 7:
                        typeof(PlacementSession).GetField("_cursor", Any)?.SetValue(runner.Session, (int?)6);
                        return 8;
                    case 8:
                        Shot(outDir, "unity_gui_run_item");
                        return 9;
                    case 9:
                        // 중단 확인 단계가 있으면(고친 뒤) 그 상태를 찍는다
                        var gui = UnityEngine.Object.FindFirstObjectByType<PlacementExperimenterGui>();
                        var confirm = gui != null ? TryField(gui, "_abortConfirm") : null;
                        var ctx = gui != null ? typeof(PlacementExperimenterGui).GetMethod("AbortContext", Any) : null;
                        if (confirm == null || ctx == null) return 11;
                        confirm.GetType().GetMethod("Arm").Invoke(confirm, new[] { ctx.Invoke(gui, null) });
                        return 10;
                    case 10:
                        Shot(outDir, "unity_gui_run_abort_confirm");
                        return 11;
                    case 11:
                        runner.PressAbort();
                        // 기록 폴더(임시 폴더의 절대 경로)가 화면에 찍히지 않게 자리표시로 바꾼다(캡처 전용, 기록 파일은 그대로)
                        const string placeholder = "<기록 루트>/placement/P001/EX02/<시각>";
                        if (runner.Session != null) typeof(PlacementSession).GetProperty("RecordDirectory", Any)?.SetValue(runner.Session, placeholder);
                        typeof(PlacementRunner).GetProperty("LastRecordDirectory", Any)?.SetValue(runner, placeholder);
                        return 12;
                    case 12:
                        Shot(outDir, "unity_gui_done");
                        return 13;
                    default:
                        EditorApplication.ExitPlaymode();
                        return 100;
                }
            }
        }
    }
}
#endif
