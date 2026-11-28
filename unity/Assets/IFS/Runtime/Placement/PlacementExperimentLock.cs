// 본 실험 설정 잠금(2026-11-28, G78-f — 챗봇 G69 lock_condition과 같은 취지). 러너의 lockExperimentPreset(코드 기본 꺼짐,
//   실험 씬 PlacementExperiment.unity에서 켬)이 켜져 있으면 시작·확인·다음 참여자 때마다 Apply(권고 설정 + 멈춤 거리 절차 값)와
//   문구 파일 scaleA를 다시 적용하고, 실험자 화면은 고정 항목의 토글 대신 아래 요약만 보인다. 확인·시작 때 Holds·TaskTextProblems가
//   어긋나면 시작을 거부한다.
//   고정 항목 = ApplyExperimentPreset이 정하는 값(놓기 도움·두 조건 연습·점검 문항 앞·평정 중 물체 숨김·UI 묶음 (1)–(6)·
//   반복 멈춤 loop·눈높이 relative) + 멈춤 거리 절차 값(아래 상수, G60-2·G78-a — CP16-1) + 문구 파일 scaleA(판 ExpectedTaskTextVersion과
//   G78 키 — CP16-4). 참여자 입력(inputMode)은 preset이 정하지 않으므로 고정하지 않는다(화면에 그대로).
//   2026-11-28 연구 책임자 결정(나중 결정이 앞 결정을 바꿈): 공간은 neutral로 고정하지 않고 **실험자가 설정 화면의 단추로 고른다**
//     (environmentChoice experimenter — 세션마다 화면에 남는 항목, 처음 눌린 값 neutral. Apply는 고른 environment를 건드리지 않는다).
//     참여자가 헤드셋에서 고르는 단계(environmentChoice participant, space_choice)는 실험에 쓰지 않는 꺼 둔 기능이다 — 잠금은 그 값을 거부하고
//     experimenter로 되돌린다(켜려면 잠금을 끄고 인스펙터·명령줄로). 눈높이 보정과 과제는 앉은 자세(eyeCalibPosture seated, 범위 아래 상수).
//   고정하지 않는 것(G78-g): 안내 판 숨기기, 선택 단계 문항, 묻지 않을 문항 키, 참여자 컨트롤러 평정, 보기만 통제 방식, 참여자 입력, 공간(실험자가 고름).
// 멈춤 거리 절차 값·자세 범위는 여기에만 적는다(기준 = PlacementConfig 코드 기본값). 기본값이 바뀌면 PlacementSetupAutoTests가 깨진다 —
//   그때는 결정 기록과 함께 여기도 고친다.
// UnityEngine에 의존하지 않는다.
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace IFS.SceneSpec.Placement
{
    public static class PlacementExperimentLock
    {
        /// <summary>잠금이 정하는 문구 파일(G59-8·G67-a: scaleA).</summary>
        public const string TaskTextFile = PlacementConfig.ExperimentTaskTextFile;
        /// <summary>잠금이 받는 문구 파일 판(G78-e, 2026-11-28 공간 고르기로 0.9, 반복 멈춤 조작 안내 stop_loop_hint 고침으로 0.10 — G83).
        /// 문구 판을 올리면 여기도 올린다.</summary>
        public const string ExpectedTaskTextVersion = "0.10-scaleA";
        /// <summary>잠금 문구 파일에 있어야 하는 G78 새 키. 공간 고르기 키(space_choice·space_choice_position)는 실험에서 그 단계를 쓰지 않아 요구하지 않는다
        /// (판 0.9-scaleA 뒤 파일에는 들어 있다 — 꺼 둔 기능을 켤 때는 러너 Check가 따로 요구한다).</summary>
        public static readonly string[] RequiredTaskTextKeys =
        {
            PlacementTaskText.ConfirmButtonRightKey, PlacementTaskText.ConfirmButtonLeftKey, PlacementTaskText.ConfirmDoneKey, PlacementTaskText.StopMainStartKey,
        };

        // ── 공간·자세(2026-11-28 연구 책임자 결정) ───────────────────────
        /// <summary>공간은 실험자가 설정 화면에서 고른다(참여자 고르기 단계는 실험에 쓰지 않음).</summary>
        public const string EnvironmentChoice = PlacementConfig.EnvironmentChoiceExperimenter;
        public const string EyeCalibPosture = PlacementConfig.PostureSeated;
        public const double EyeHeightSeatedMinM = 0.95;
        public const double EyeHeightSeatedMaxM = 1.45;

        // ── 멈춤 거리 절차 값(G60-2 · G78-a) ────────────────────────────
        public const double StopSpeedMps = 0.25;
        public const double StopHeightM = 1.2;
        public const double StopItiSeconds = 2.0;
        public const string StopFirstDirection = PlacementConfig.FirstByParticipant;
        public const double StopLoopMinM = 0.4;
        public const double StopLoopMaxM = 3.6;
        public const double StopLoopStartMinM = 1.0;
        public const double StopLoopStartMaxM = 3.0;
        /// <summary>본 라운드 1(2026-11-28 연구 책임자 결정 G83 — 이전 G60-2의 4). 연습 1 × 30초 + 본 1 × 75초.</summary>
        public const int StopLoopRounds = 1;
        public const int StopLoopPracticeRounds = 1;
        public const double StopLoopRoundSeconds = 75;
        public const double StopLoopPracticeRoundSeconds = 30;
        public const double StopLoopToggleDebounceMs = 250;
        public const bool StopLoopHideRings = true;

        /// <summary>잠금 적용: 권고 설정(ApplyExperimentPreset) + 실험자가 공간을 고름·앉은 자세 + 멈춤 거리 절차 값. 문구 파일은 러너가 TaskTextFile로 고른다.
        /// 실험자가 고른 공간(environment)은 그대로 둔다(세 공간 가운데 하나일 때 — 아니면 권고 설정의 neutral).</summary>
        public static void Apply(PlacementConfig cfg)
        {
            if (cfg == null) return;
            string chosen = cfg.environment;
            cfg.ApplyExperimentPreset();
            if (System.Array.IndexOf(PlacementConfig.Environments, chosen) >= 0) cfg.environment = chosen;
            cfg.environmentChoice = EnvironmentChoice;
            cfg.eyeCalibPosture = EyeCalibPosture;
            cfg.eyeHeightSeatedMinM = EyeHeightSeatedMinM;
            cfg.eyeHeightSeatedMaxM = EyeHeightSeatedMaxM;
            cfg.stopSpeedMps = StopSpeedMps;
            cfg.stopHeightM = StopHeightM;
            cfg.stopItiSeconds = StopItiSeconds;
            cfg.stopFirstDirection = StopFirstDirection;
            cfg.stopLoopMinM = StopLoopMinM;
            cfg.stopLoopMaxM = StopLoopMaxM;
            cfg.stopLoopStartMinM = StopLoopStartMinM;
            cfg.stopLoopStartMaxM = StopLoopStartMaxM;
            cfg.stopLoopRounds = StopLoopRounds;
            cfg.stopLoopPracticeRounds = StopLoopPracticeRounds;
            cfg.stopLoopRoundSeconds = StopLoopRoundSeconds;
            cfg.stopLoopPracticeRoundSeconds = StopLoopPracticeRoundSeconds;
            cfg.stopLoopToggleDebounceMs = StopLoopToggleDebounceMs;
            cfg.stopLoopHideRings = StopLoopHideRings;
        }

        /// <summary>멈춤 거리 절차 값 가운데 잠금 값과 다른 것(이름 = 지금 값). 맞으면 빈 목록.</summary>
        public static List<string> StopMismatches(PlacementConfig cfg)
        {
            var e = new List<string>();
            void D(string name, double v, double want) { if (v != want) e.Add($"{name} = {v.ToString(CultureInfo.InvariantCulture)}(잠금 {want.ToString(CultureInfo.InvariantCulture)})"); }
            D("stopSpeedMps", cfg.stopSpeedMps, StopSpeedMps);
            D("stopHeightM", cfg.stopHeightM, StopHeightM);
            D("stopItiSeconds", cfg.stopItiSeconds, StopItiSeconds);
            if (cfg.stopFirstDirection != StopFirstDirection) e.Add($"stopFirstDirection = {cfg.stopFirstDirection}(잠금 {StopFirstDirection})");
            D("stopLoopMinM", cfg.stopLoopMinM, StopLoopMinM);
            D("stopLoopMaxM", cfg.stopLoopMaxM, StopLoopMaxM);
            D("stopLoopStartMinM", cfg.stopLoopStartMinM, StopLoopStartMinM);
            D("stopLoopStartMaxM", cfg.stopLoopStartMaxM, StopLoopStartMaxM);
            D("stopLoopRounds", cfg.stopLoopRounds, StopLoopRounds);
            D("stopLoopPracticeRounds", cfg.stopLoopPracticeRounds, StopLoopPracticeRounds);
            D("stopLoopRoundSeconds", cfg.stopLoopRoundSeconds, StopLoopRoundSeconds);
            D("stopLoopPracticeRoundSeconds", cfg.stopLoopPracticeRoundSeconds, StopLoopPracticeRoundSeconds);
            D("stopLoopToggleDebounceMs", cfg.stopLoopToggleDebounceMs, StopLoopToggleDebounceMs);
            if (cfg.stopLoopHideRings != StopLoopHideRings) e.Add($"stopLoopHideRings = {cfg.stopLoopHideRings}(잠금 {StopLoopHideRings})");
            return e;
        }

        /// <summary>공간 고르기·자세 값 가운데 잠금 값과 다른 것. 맞으면 빈 목록.</summary>
        public static List<string> SpacePostureMismatches(PlacementConfig cfg)
        {
            var e = new List<string>();
            var inv = CultureInfo.InvariantCulture;
            if (cfg.environmentChoice != EnvironmentChoice)
                e.Add($"environmentChoice = {cfg.environmentChoice}(잠금 {EnvironmentChoice} — 공간은 실험자가 설정 화면에서 고름, 참여자 고르기 단계는 꺼 둔 기능)");
            if (System.Array.IndexOf(PlacementConfig.Environments, cfg.environment) < 0) e.Add($"environment = {cfg.environment}(neutral | nature | space 중 하나)");
            if (cfg.eyeCalibPosture != EyeCalibPosture) e.Add($"eyeCalibPosture = {cfg.eyeCalibPosture}(잠금 {EyeCalibPosture})");
            if (cfg.eyeHeightSeatedMinM != EyeHeightSeatedMinM) e.Add($"eyeHeightSeatedMinM = {cfg.eyeHeightSeatedMinM.ToString(inv)}(잠금 {EyeHeightSeatedMinM.ToString(inv)})");
            if (cfg.eyeHeightSeatedMaxM != EyeHeightSeatedMaxM) e.Add($"eyeHeightSeatedMaxM = {cfg.eyeHeightSeatedMaxM.ToString(inv)}(잠금 {EyeHeightSeatedMaxM.ToString(inv)})");
            return e;
        }

        /// <summary>설정과 문구 파일 이름이 잠금 값 그대로다(문구 파일 내용은 TaskTextProblems). 공간 이름은 세 공간 가운데 하나면 된다(실험자가 고름).</summary>
        public static bool Holds(PlacementConfig cfg, string taskTextName) =>
            cfg != null && cfg.ExperimentProcedureOn && StopMismatches(cfg).Count == 0 && SpacePostureMismatches(cfg).Count == 0
            && SameTaskText(taskTextName, TaskTextFile);

        /// <summary>잠금이 거부할 이유(설정·문구 파일 이름·읽은 문구 파일의 판과 키). 없으면 빈 목록. 러너가 확인·시작 때 오류로 낸다.</summary>
        public static List<string> Refusals(PlacementConfig cfg, string taskTextName, PlacementTaskText text)
        {
            var e = new List<string>();
            if (cfg == null) { e.Add("설정 없음"); return e; }
            if (!cfg.ExperimentProcedureOn) e.Add("권고 설정(ApplyExperimentPreset) 값이 아님");
            e.AddRange(SpacePostureMismatches(cfg));
            e.AddRange(StopMismatches(cfg));
            if (!SameTaskText(taskTextName, TaskTextFile)) e.Add($"문구 파일 {taskTextName}(잠금 {TaskTextFile})");
            e.AddRange(TaskTextProblems(text));
            return e.Select(x => "본 실험 설정 고정: " + x + " — 시작하지 않습니다").ToList();
        }

        /// <summary>읽은 문구 파일이 잠금 판(ExpectedTaskTextVersion)이고 필요한 키(G78)가 있는가. 문제 목록(없으면 빈 목록).</summary>
        public static List<string> TaskTextProblems(PlacementTaskText text)
        {
            var e = new List<string>();
            if (text == null) { e.Add("문구 파일을 읽지 못함"); return e; }
            if (text.Version != ExpectedTaskTextVersion) e.Add($"문구 파일 {text.FileName} 판 {text.Version ?? "없음"}(잠금 {ExpectedTaskTextVersion})");
            var missing = RequiredTaskTextKeys.Where(k => text[k] == null).ToList();
            if (missing.Count > 0) e.Add($"문구 파일 {text.FileName}에 {string.Join(", ", missing)} 문구가 없음(G78)");
            return e;
        }

        public static bool SameTaskText(string a, string b) =>
            string.Equals((a ?? "").Replace('\\', '/').Trim(), (b ?? "").Replace('\\', '/').Trim(), System.StringComparison.OrdinalIgnoreCase);

        /// <summary>실험자 화면 "본 실험 설정 고정" 요약 줄(값은 지금 설정에서 읽는다 — 어긋나면 그대로 보인다).</summary>
        public static List<string> SummaryLines(PlacementConfig cfg, string taskTextName, string taskTextVersion = null)
        {
            var inv = CultureInfo.InvariantCulture;
            string OnOff(bool b) => b ? "켬" : "끔";
            string N(double v, string f = "0.##") => v.ToString(f, inv);
            string space = cfg.ParticipantChoosesSpace
                ? $"{cfg.environment} — 참여자 고르기 단계가 켜져 있음(꺼 둔 기능, 잠금 값 아님 — [확인]에서 실험자 고름으로 되돌림)"
                : $"{cfg.environment}(실험자가 위 단추로 고름 — 세션마다, 처음 값 neutral)";
            string stop = cfg.IsStopLoop
                ? $"loop: 연습 {cfg.stopLoopPracticeRounds} × 상한 {N(cfg.stopLoopPracticeRoundSeconds)}초 + 본 {cfg.stopLoopRounds} × 상한 {N(cfg.stopLoopRoundSeconds)}초, " +
                  $"라운드 사이 {N(cfg.stopItiSeconds)}초, 왕복 {N(cfg.stopLoopMinM)}–{N(cfg.stopLoopMaxM)} m · {N(cfg.stopSpeedMps)} m/s"
                : cfg.stopMode;
            string eye = cfg.IsEyeRelative ? $"relative(기준 {cfg.eyeHeightReferenceM.ToString("0.00", inv)} m)" : cfg.eyeHeightMode;
            string posture = (cfg.IsSeated ? "앉은 자세" : "선 자세") + $" [{cfg.EyeRangeMinM.ToString("0.00", inv)}, {cfg.EyeRangeMaxM.ToString("0.00", inv)}] m";
            string task = (taskTextName ?? "").Replace('\\', '/');
            int slash = task.LastIndexOf('/');
            if (slash >= 0) task = task.Substring(slash + 1);
            return new List<string>
            {
                $"공간 {space} · 놓기 도움 {OnOff(cfg.placementAssist)} · 두 조건 배치 연습 {OnOff(cfg.practiceInAllConditions)} (G59-8, 공간 2026-11-28)",
                $"평정 동안 물체 숨기기 {OnOff(cfg.hideObjectDuringItems)} · 점검 문항을 멈춤 거리 앞에 {OnOff(cfg.checkBeforeStopDistance)} (G59-8)",
                $"멈춤 거리 {stop} (G60-2·G78-a)",
                $"눈높이 기준 배치 {eye} · 보정 자세 {posture} (G60-3, 2026-11-28) · 헤드셋 UI 개선 묶음 (1)–(6) {OnOff(cfg.UiBundleOn)} (G63)",
                $"문구 파일 {task}{(taskTextVersion != null ? " 판 " + taskTextVersion : "")} (G59-8·G78-e)",
            };
        }
    }
}
