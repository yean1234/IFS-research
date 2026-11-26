// 메뉴 IFS ▸ Experiment ▸ Create Placement Experiment Scene — 배치 실험 씬(Assets/IFS/Scenes/PlacementExperiment.unity)을 만든다.
//   구성: XR 리그(PlacementXrRig, 원점 = '나'의 자리) ▸ 눈높이 1.6 m 카메라(정면 +z) + HeadPoseProvider
//         + 중립 환경(IFSEnvironment, 격자 바닥은 러너가 숨김)
//         + "Placement Experiment"(PlacementRunner · PlacementExperimenterGui · ParticipantTextDisplay · PlacementTextPanel
//            · DesktopPlacementInput · XrPlacementInput).
// 메뉴 IFS ▸ Experiment ▸ Build Placement Experiment (Windows) — 이 씬 하나로 Windows 빌드(unity/Builds/Placement/, git 제외).
// 배치모드:
//   씬 만들기:  Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.CreateSceneBatch -logFile <로그>
//   자동 시행:  Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.RunAutoTrialBatch
//               -recordRoot <기록 루트> -specPath <spec.json> -condition place|view -controlMode static|system_move|replay|point_select
//               [-replayPath <trajectory.json>] [-participant 1] [-conditionSeconds 90] [-baselineSeconds 30] [-headSampleHz 20]
//               [-stopItiSeconds 2] [-showRings true|false] [-hideObjectDuringItems true|false]
//               [-taskTextFile IFS/placement_task.scaleA.v0.json] [-selectionPath <selection.json>]
//               [-askOptionalItems true|false] [-disabledItems own,S4] [-dt 0.02]
//               [-environment neutral|space|nature] [-placementAssist true|false]   (G52, 2026-11-24)
//               [-checkBeforeStopDistance true|false] [-practiceInAllConditions true|false] -logFile <로그>   (G59, 2026-11-25)
//   Windows 빌드: Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.PlacementExperimentMenu.BuildWindowsBatch -logFile <로그>
//   (둘 다 -quit 없이 — 끝나면 EditorApplication.Exit(0/1)로 닫는다)
// 자동 시행은 검증용이다: 합성 입력(PlacementAutoScript)으로 intro → done을 한 바퀴 돌고 기록 폴더를 만든다.
using System;
using System.Globalization;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class PlacementExperimentMenu
    {
        public const string ScenePath = "Assets/IFS/Scenes/PlacementExperiment.unity";

        [MenuItem("IFS/Experiment/Create Placement Experiment Scene")]
        public static void CreateScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Build();
        }

        public static void CreateSceneBatch()
        {
            int exit = 1;
            try
            {
                Build();
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] 배치 실험 씬 만들기 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            BuildObjects();
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("씬을 저장하지 못했습니다: " + ScenePath);
            Debug.Log("[IFS] 배치 실험 씬을 만들었습니다: " + ScenePath);
        }

        /// <summary>지금 씬에 카메라·환경·러너를 만든다(메뉴와 자동 시행이 같은 구성을 쓴다).</summary>
        public static PlacementRunner BuildObjects()
        {
            // XR 리그(세계 원점 = '나'의 자리, 바닥 y = 0) 아래에 카메라. XR이면 카메라 로컬 자세 = 헤드셋(바닥 원점 기준),
            // 데스크톱이면 HeadPoseProvider가 눈높이 1.6 m에서 모의 조작한다.
            var rigGo = new GameObject("XR Rig ('나' 자리)");
            var rig = rigGo.AddComponent<PlacementXrRig>();
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            camGo.transform.SetParent(rigGo.transform, false);
            var cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<AudioListener>();
            cam.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), Quaternion.identity);
            cam.nearClipPlane = 0.05f;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            var head = camGo.AddComponent<HeadPoseProvider>();
            rig.Configure(camGo.transform);

            new GameObject("IFS Environment").AddComponent<IFSEnvironment>();

            var go = new GameObject("Placement Experiment");
            var text = go.AddComponent<ParticipantTextDisplay>();
            var input = go.AddComponent<DesktopPlacementInput>();
            input.Configure(cam);
            var xr = go.AddComponent<XrPlacementInput>();
            xr.Configure(rigGo.transform, PlacementConfig.HandRight);
            var panel = go.AddComponent<PlacementTextPanel>();
            var runner = go.AddComponent<PlacementRunner>();
            var gui = go.AddComponent<PlacementExperimenterGui>();
            runner.Configure(head, text, input, ShapePrefabMenu.LoadShapePrefabs());
            runner.ConfigureXr(rig, xr, panel);
            gui.Configure(runner);
            return runner;
        }

        // ── 자동 시행(검증용) ─────────────────────────────────────────────
        public static void RunAutoTrialBatch()
        {
            int exit = 1;
            try
            {
                var args = Environment.GetCommandLineArgs();
                string spec = Value(args, "-specPath");
                string root = Value(args, "-recordRoot");
                if (string.IsNullOrWhiteSpace(spec)) throw new ArgumentException("-specPath가 없습니다");
                if (string.IsNullOrWhiteSpace(root)) throw new ArgumentException("-recordRoot가 없습니다");
                var cfg = ConfigFromArgs(args);
                int participant = int.Parse(Value(args, "-participant") ?? "1", CultureInfo.InvariantCulture);
                double dt = double.Parse(Value(args, "-dt") ?? "0.02", CultureInfo.InvariantCulture);
                string dir = RunAutoTrial(spec, root, participant, cfg, dt, null, Value(args, "-taskTextFile"), Value(args, "-selectionPath"));
                Debug.Log($"[IFS] 배치 실험 자동 시행 완료({cfg.condition}/{cfg.EffectiveControlMode}): {dir}");
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] 배치 실험 자동 시행 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        public static PlacementConfig ConfigFromArgs(string[] args)
        {
            var cfg = new PlacementConfig();
            string v;
            if ((v = Value(args, "-condition")) != null) cfg.condition = v;
            if ((v = Value(args, "-controlMode")) != null) cfg.controlMode = v;
            if ((v = Value(args, "-replayPath")) != null) cfg.replayPath = Path.GetFullPath(v);
            if ((v = Value(args, "-conditionSeconds")) != null) cfg.conditionSeconds = double.Parse(v, CultureInfo.InvariantCulture);
            if ((v = Value(args, "-baselineSeconds")) != null) cfg.baselineSeconds = double.Parse(v, CultureInfo.InvariantCulture);
            if ((v = Value(args, "-headSampleHz")) != null) cfg.headSampleHz = double.Parse(v, CultureInfo.InvariantCulture);
            if ((v = Value(args, "-stopItiSeconds")) != null) cfg.stopItiSeconds = double.Parse(v, CultureInfo.InvariantCulture);
            if ((v = Value(args, "-showRings")) != null) cfg.showRings = bool.Parse(v);
            if ((v = Value(args, "-hideObjectDuringItems")) != null) cfg.hideObjectDuringItems = bool.Parse(v);
            if ((v = Value(args, "-inputMode")) != null) cfg.inputMode = v;
            if ((v = Value(args, "-xrHand")) != null) cfg.xrHand = v;
            if ((v = Value(args, "-askOptionalItems")) != null) cfg.askOptionalItems = bool.Parse(v);
            if ((v = Value(args, "-disabledItems")) != null) cfg.disabledItems = v.Split(',').Select(k => k.Trim()).Where(k => k.Length > 0).ToArray();
            if ((v = Value(args, "-environment")) != null) cfg.environment = v;
            if ((v = Value(args, "-placementAssist")) != null) cfg.placementAssist = bool.Parse(v);
            if ((v = Value(args, "-checkBeforeStopDistance")) != null) cfg.checkBeforeStopDistance = bool.Parse(v);
            if ((v = Value(args, "-practiceInAllConditions")) != null) cfg.practiceInAllConditions = bool.Parse(v);
            if ((v = Value(args, "-stopMode")) != null) cfg.stopMode = v;   // G60-2: single | loop
            if ((v = Value(args, "-stopLoopRoundSeconds")) != null) cfg.stopLoopRoundSeconds = double.Parse(v, CultureInfo.InvariantCulture);
            if ((v = Value(args, "-eyeHeightMode")) != null) cfg.eyeHeightMode = v;   // G60-3: none | relative(자동 시행은 기준값 고정)
            return cfg;
        }

        /// <summary>새 빈 씬에서 spec 하나로 intro → done을 사람 없이 돈다. 기록 폴더 경로를 돌려준다(실패하면 예외).
        /// taskTextFile: StreamingAssets 기준 문구 파일(예: IFS/placement_task.scaleA.v0.json). null이면 기본 파일.
        /// selectionPath: 선택 파일(selection.json, ifs-selection/0.1·0.2). null이면 spec만(예전과 같음).</summary>
        public static string RunAutoTrial(string specPath, string recordRoot, int participant, PlacementConfig cfg, double dt, PlacementAutoScript script,
            string taskTextFile = null, string selectionPath = null)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = BuildObjects();
            try
            {
                runner.SetRecordRoot(recordRoot);
                if (!string.IsNullOrWhiteSpace(taskTextFile)) runner.SelectTaskText(taskTextFile);
                runner.BeginAuto(script ?? new PlacementAutoScript(), cfg ?? new PlacementConfig());
                runner.ParticipantNumberText = participant.ToString(CultureInfo.InvariantCulture);
                runner.SpecPathText = Path.GetFullPath(specPath);
                runner.SelectionPathText = string.IsNullOrWhiteSpace(selectionPath) ? "" : Path.GetFullPath(selectionPath);
                if (!runner.Check()) throw new InvalidOperationException("확인 오류: " + string.Join("; ", runner.Errors));
                if (!runner.StartSession()) throw new InvalidOperationException("시작 실패: " + string.Join("; ", runner.Errors));
                int maxSteps = 2000000;
                for (int i = 0; i < maxSteps && runner.Stage != PlacementRunnerStage.Done; i++) runner.Tick(dt);
                if (runner.Stage != PlacementRunnerStage.Done) throw new InvalidOperationException("자동 시행이 끝나지 않았습니다(단계 " + runner.Session?.PhaseLabel + ")");
                if (!runner.LastCompleted) throw new InvalidOperationException("자동 시행이 중단으로 끝났습니다: " + runner.LastAbortedAt);
                string dir = runner.LastRecordDirectory;
                var missing = PlacementRecordWriter.AllFiles.Where(f => !File.Exists(Path.Combine(dir, f))).ToList();
                if (missing.Count > 0) throw new InvalidOperationException("기록 파일이 없습니다: " + string.Join(", ", missing));
                return dir;
            }
            finally
            {
                runner.ResetForNext();
            }
        }

        // ── Windows 빌드(선택) ───────────────────────────────────────────
        /// <summary>빌드 결과 경로(unity/ 기준, .gitignore의 unity/Builds/).</summary>
        public const string WindowsBuildPath = "Builds/Placement/IFSPlacement.exe";

        [MenuItem("IFS/Experiment/Build Placement Experiment (Windows)")]
        public static void BuildWindowsMenu()
        {
            try { Debug.Log("[IFS] 배치 실험 Windows 빌드: " + BuildWindows()); }
            catch (Exception e) { Debug.LogError("[IFS] 배치 실험 Windows 빌드 실패: " + e.Message); }
        }

        public static void BuildWindowsBatch()
        {
            int exit = 1;
            try
            {
                Debug.Log("[IFS] 배치 실험 Windows 빌드: " + BuildWindows());
                exit = 0;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] 배치 실험 Windows 빌드 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        /// <summary>배치 실험 씬 하나로 Windows 64비트 빌드를 만든다(XR 설정은 Standalone 설정을 따른다 — OpenXR, 시작 때 XR 초기화).
        /// 빌드에서 spec 목록 폴더는 persistentDataPath/IFS/scenes(실험자 화면에 경로가 보인다), 기록은 persistentDataPath/IFS/sessions.</summary>
        public static string BuildWindows()
        {
            if (!File.Exists(ScenePath)) throw new InvalidOperationException("씬이 없습니다(먼저 Create Placement Experiment Scene): " + ScenePath);
            var opts = new BuildPlayerOptions
            {
                scenes = new[] { ScenePath },
                locationPathName = WindowsBuildPath,
                target = BuildTarget.StandaloneWindows64,
                options = BuildOptions.None,
            };
            var report = BuildPipeline.BuildPlayer(opts);
            if (report.summary.result != UnityEditor.Build.Reporting.BuildResult.Succeeded)
                throw new InvalidOperationException($"빌드 결과 {report.summary.result}(오류 {report.summary.totalErrors}개) — 콘솔 확인");
            return Path.GetFullPath(WindowsBuildPath);
        }

        static string Value(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }
    }
}
