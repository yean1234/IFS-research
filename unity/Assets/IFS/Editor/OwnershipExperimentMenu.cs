// 메뉴 IFS ▸ Experiment ▸ Create Ownership Experiment Scene — 소유감 실험 씬(Assets/IFS/Scenes/OwnershipExperiment.unity)을 만든다.
//   구성: 눈높이 1.6 m 카메라 + HeadPoseProvider(XR Head / 데스크톱 모의) + 중립 환경(IFSEnvironment)
//         + "Ownership Experiment"(OwnershipRunner · OwnershipExperimenterGui · ParticipantTextDisplay). 모양 프리팹이 있으면 연결.
//   다시 실행해도 같은 경로에 같은 구성으로 덮어쓴다(씬 .meta GUID 유지).
// 배치모드:
//   씬 만들기:  Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.OwnershipExperimentMenu.CreateSceneBatch -logFile <로그>
//   자동 시행:  Unity.exe -batchmode -projectPath <unity> -executeMethod IFS.SceneSpec.EditorTools.OwnershipExperimentMenu.RunAutoTrialBatch
//               -recordRoot <기록 루트> -specPath <spec.json>[;<spec2.json>…] [-participant 1] [-viewSeconds 0.5] [-headSampleHz 20] [-dt 0.02] -logFile <로그>
//   (둘 다 -quit 없이 — 끝나면 EditorApplication.Exit(0/1)로 닫는다)
// 자동 시행은 검증용이다: 키 입력 없이 정해진 평정·선택(합성)과 정해진 머리 경로로 Setup → Done을 한 바퀴 돌고 기록 폴더를 만든다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public static class OwnershipExperimentMenu
    {
        public const string ScenePath = "Assets/IFS/Scenes/OwnershipExperiment.unity";

        [MenuItem("IFS/Experiment/Create Ownership Experiment Scene")]
        public static void CreateScene()
        {
            if (!EditorSceneManager.SaveCurrentModifiedScenesIfUserWantsTo()) return;
            Build();
        }

        /// <summary>배치모드용(저장 확인 창 없이). 성공하면 Exit(0), 실패하면 Exit(1).</summary>
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
                Debug.LogError("[IFS] 소유감 실험 씬 만들기 실패: " + e);
            }
            EditorApplication.Exit(exit);
        }

        static void Build()
        {
            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            BuildObjects();
            if (!EditorSceneManager.SaveScene(scene, ScenePath)) throw new InvalidOperationException("씬을 저장하지 못했습니다: " + ScenePath);
            Debug.Log("[IFS] 소유감 실험 씬을 만들었습니다: " + ScenePath);
        }

        /// <summary>지금 씬에 카메라·환경·러너를 만든다(메뉴와 자동 시행이 같은 구성을 쓴다).</summary>
        public static OwnershipRunner BuildObjects()
        {
            var camGo = new GameObject("Main Camera") { tag = "MainCamera" };
            var cam = camGo.AddComponent<Camera>();
            camGo.AddComponent<AudioListener>();
            cam.transform.SetPositionAndRotation(new Vector3(0f, 1.6f, 0f), Quaternion.identity);
            cam.nearClipPlane = 0.05f;
            cam.allowHDR = false;
            cam.allowMSAA = true;
            var head = camGo.AddComponent<HeadPoseProvider>();

            new GameObject("IFS Environment").AddComponent<IFSEnvironment>();   // Awake에서 환경을 만든다(씬 파일에는 설정만)

            var go = new GameObject("Ownership Experiment");
            var text = go.AddComponent<ParticipantTextDisplay>();
            var runner = go.AddComponent<OwnershipRunner>();
            var gui = go.AddComponent<OwnershipExperimenterGui>();
            runner.Configure(head, text, ShapePrefabMenu.LoadShapePrefabs());
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
                var specs = Values(args, "-specPath").SelectMany(v => v.Split(';')).Where(s => s.Trim().Length > 0).ToList();
                string root = Value(args, "-recordRoot");
                if (specs.Count == 0) throw new ArgumentException("-specPath가 없습니다");
                if (string.IsNullOrWhiteSpace(root)) throw new ArgumentException("-recordRoot가 없습니다(참여자 자료처럼 저장소 밖에 둘 것)");
                int participant = int.Parse(Value(args, "-participant") ?? "1", CultureInfo.InvariantCulture);
                var cfg = new OwnershipConfig
                {
                    viewSeconds = double.Parse(Value(args, "-viewSeconds") ?? "0.5", CultureInfo.InvariantCulture),
                    headSampleHz = double.Parse(Value(args, "-headSampleHz") ?? "20", CultureInfo.InvariantCulture),
                };
                double dt = double.Parse(Value(args, "-dt") ?? "0.02", CultureInfo.InvariantCulture);
                bool allOk = true;
                for (int i = 0; i < specs.Count; i++)
                {
                    try
                    {
                        string dir = RunAutoTrial(specs[i].Trim(), root, participant + i, cfg, dt, null);
                        Debug.Log($"[IFS] 자동 시행 완료: {Path.GetFileName(specs[i].Trim())} → {dir}");
                    }
                    catch (Exception e)
                    {
                        allOk = false;
                        Debug.LogError($"[IFS] 자동 시행 실패: {specs[i]}\n{e}");
                    }
                }
                exit = allOk ? 0 : 1;
            }
            catch (Exception e)
            {
                Debug.LogError("[IFS] 자동 시행 인자 오류: " + e);
            }
            EditorApplication.Exit(exit);
        }

        /// <summary>새 빈 씬에서 spec 하나로 Setup → Done을 키 입력 없이 돈다. 기록 폴더 경로를 돌려준다(실패하면 예외).
        /// dtFor가 있으면 프레임마다 그 값을 dt로 쓴다(밀린 프레임 검증용 — 테스트만 씀).</summary>
        public static string RunAutoTrial(string specPath, string recordRoot, int participant, OwnershipConfig cfg, double dt, OwnershipAutoScript script,
            Func<OwnershipRunner, double> dtFor = null)
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var runner = BuildObjects();
            try
            {
                runner.SetRecordRoot(recordRoot);
                runner.BeginAuto(script ?? new OwnershipAutoScript(), cfg ?? new OwnershipConfig { viewSeconds = 0.5 });
                runner.ParticipantNumberText = participant.ToString(CultureInfo.InvariantCulture);
                runner.SpecPathText = Path.GetFullPath(specPath);
                if (!runner.Check()) throw new InvalidOperationException("SpecCheck 오류: " + string.Join("; ", runner.Errors));
                foreach (var v in runner.Plan.Variants) Debug.Log("[IFS] 자동 시행 변형 " + v.Describe());
                Debug.Log("[IFS] 자동 시행 순서: " + string.Join(" → ", runner.Plan.Order));
                if (!runner.StartSession()) throw new InvalidOperationException("시작 실패: " + string.Join("; ", runner.Errors));
                int maxSteps = 200000;
                for (int i = 0; i < maxSteps && runner.Phase != OwnershipPhase.Done; i++) runner.Tick(dtFor != null ? dtFor(runner) : dt);
                if (runner.Phase != OwnershipPhase.Done) throw new InvalidOperationException("자동 시행이 끝나지 않았습니다(단계 " + runner.Phase + ")");
                if (!runner.LastCompleted) throw new InvalidOperationException("자동 시행이 중단으로 끝났습니다: " + runner.LastAbortedAt);
                string dir = runner.LastRecordDirectory;
                var missing = new[]
                {
                    OwnershipRecordWriter.ManifestFile, OwnershipRecordWriter.HeadposeFile, OwnershipRecordWriter.RatingsFile,
                    OwnershipRecordWriter.DifferenceFile, OwnershipRecordWriter.EventsFile, OwnershipRecordWriter.SummaryFile,
                }.Where(f => !File.Exists(Path.Combine(dir, f))).ToList();
                if (missing.Count > 0) throw new InvalidOperationException("기록 파일이 없습니다: " + string.Join(", ", missing));
                return dir;
            }
            finally
            {
                runner.ResetForNext();
            }
        }

        static string Value(string[] args, string name)
        {
            int i = Array.IndexOf(args, name);
            return i >= 0 && i + 1 < args.Length ? args[i + 1] : null;
        }

        static IEnumerable<string> Values(string[] args, string name)
        {
            for (int i = 0; i < args.Length - 1; i++)
                if (args[i] == name) yield return args[i + 1];
        }
    }
}
