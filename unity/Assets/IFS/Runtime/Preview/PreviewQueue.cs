// 대안 경로(G12) 측정용: 데스크톱 플레이어를 띄워 두고(상주 프로세스) 폴더로 받은 요청마다 미리보기 PNG를 쓴다.
// 웹 화면은 이 PNG를 받아 보여 준다(Unity가 뒤에서 캡처한 이미지를 웹에 표시). WebGL 빌드에는 들어가지 않는다.
//   실행: <플레이어>.exe -ifsPreviewQueue <폴더> [-screen-width 320 -screen-height 240 -screen-fullscreen 0]
//   요청: <폴더>/<이름>.req.json = {"spec": "<spec 파일 절대 경로>" 또는 "specJson": "<문자열>", "overrides": {…}(선택),
//          "width": 800, "height": 600, "backgrounds": ["scene", "black", "white"](선택, 기본 scene), "out": "<출력 접두 절대 경로>"(선택, 기본 <폴더>/<이름>)}
//   응답: <out>_<배경>.png + <폴더>/<이름>.done.json(로드·렌더 시간, 오류). 요청 파일은 지운다. <이름>.req.json 대신 quit.req.json이면 종료.
// 같은 PreviewStage를 쓰므로 WebGL·에디터 캡처와 같은 카메라·조명·로더다. 참여자 기록은 남기지 않는다.
#if !UNITY_WEBGL || UNITY_EDITOR
using System;
using System.Diagnostics;
using System.IO;
using System.Linq;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace IFS.SceneSpec
{
    public sealed class PreviewQueue
    {
        public const string Arg = "-ifsPreviewQueue";
        readonly PreviewBridge _bridge;
        readonly string _dir;
        static readonly Encoding Utf8NoBom = new UTF8Encoding(false);

        PreviewQueue(PreviewBridge bridge, string dir) { _bridge = bridge; _dir = dir; }

        public static PreviewQueue FromCommandLine(PreviewBridge bridge)
        {
            var args = System.Environment.GetCommandLineArgs();
            int i = Array.IndexOf(args, Arg);
            if (i < 0 || i + 1 >= args.Length) return null;
            string dir = Path.GetFullPath(args[i + 1]);
            Directory.CreateDirectory(dir);
            Debug.Log("[PreviewQueue] 요청 폴더: " + dir);
            File.WriteAllText(Path.Combine(dir, "ready.json"),
                new JObject { ["pid"] = Process.GetCurrentProcess().Id, ["time"] = DateTime.UtcNow.ToString("o") }.ToString(), Utf8NoBom);
            return new PreviewQueue(bridge, dir);
        }

        public void Poll()
        {
            string[] reqs;
            try { reqs = Directory.GetFiles(_dir, "*.req.json").OrderBy(p => p, StringComparer.Ordinal).ToArray(); }
            catch (IOException) { return; }
            foreach (var req in reqs) Handle(req);
        }

        void Handle(string reqPath)
        {
            string name = Path.GetFileName(reqPath);
            name = name.Substring(0, name.Length - ".req.json".Length);
            if (name == "quit")
            {
                TryDelete(reqPath);
                Application.Quit();
                return;
            }
            var done = new JObject { ["request"] = name };
            var total = Stopwatch.StartNew();
            try
            {
                string text;
                try { text = File.ReadAllText(reqPath, Encoding.UTF8); }
                catch (IOException) { return; }   // 아직 쓰는 중 — 다음 프레임에
                var r = JObject.Parse(text);
                string specJson = (string)r["specJson"];
                string specPath = (string)r["spec"];
                if (specJson == null && specPath != null) specJson = File.ReadAllText(specPath, Encoding.UTF8);
                if (specJson == null) throw new ArgumentException("spec 또는 specJson이 필요합니다");
                SceneOverride ov = null;
                if (r["overrides"] is JObject oj)
                {
                    ov = SceneOverrideJson.Parse(oj.ToString(Formatting.None), out var errs);
                    if (ov == null) throw new ArgumentException("덮어쓰기 오류: " + string.Join("; ", errs));
                }
                int w = (int?)r["width"] ?? 800, h = (int?)r["height"] ?? 600;
                var bgs = r["backgrounds"] is JArray ba ? ba.Select(t => (string)t).ToArray() : new[] { "scene" };
                string outPrefix = (string)r["out"] ?? Path.Combine(_dir, name);

                var stage = _bridge.Stage;
                var sw = Stopwatch.StartNew();
                bool ok = stage.Load(specJson, specPath != null ? Path.GetFileName(specPath) : "preview.json", ov);
                done["loadMs"] = Math.Round(sw.Elapsed.TotalMilliseconds, 2);
                if (!ok) throw new InvalidOperationException("spec을 로드하지 못했습니다(로그 확인)");
                stage.FreezeMotion();
                var renders = new JObject();
                foreach (var b in bgs)
                {
                    sw.Restart();
                    var png = stage.RenderPng(w, h, PreviewBridge.ParseBackground(b));
                    double renderMs = sw.Elapsed.TotalMilliseconds;
                    string file = outPrefix + "_" + b.ToLowerInvariant() + ".png";
                    Directory.CreateDirectory(Path.GetDirectoryName(file));
                    File.WriteAllBytes(file, png);
                    renders[b.ToLowerInvariant()] = new JObject { ["renderMs"] = Math.Round(renderMs, 2), ["writeMs"] = Math.Round(sw.Elapsed.TotalMilliseconds - renderMs, 2), ["png"] = file };
                }
                done["renders"] = renders;
                done["renderPath"] = stage.Loader.RenderPath;
                done["ok"] = true;
            }
            catch (Exception e)
            {
                done["ok"] = false;
                done["error"] = e.GetType().Name + ": " + e.Message;
            }
            done["totalMs"] = Math.Round(total.Elapsed.TotalMilliseconds, 2);
            TryDelete(reqPath);
            string tmp = Path.Combine(_dir, name + ".done.tmp");
            File.WriteAllText(tmp, done.ToString(Formatting.Indented), Utf8NoBom);
            string dst = Path.Combine(_dir, name + ".done.json");
            if (File.Exists(dst)) File.Delete(dst);
            File.Move(tmp, dst);
        }

        static void TryDelete(string p)
        {
            try { File.Delete(p); } catch (IOException) { }
        }
    }
}
#endif
