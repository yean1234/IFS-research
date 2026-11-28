// 본 실험 설정 잠금(2026-11-28, G78-f — 챗봇 G69 lock_condition과 같은 취지). 러너의 lockExperimentPreset(코드 기본 꺼짐,
//   실험 씬 PlacementExperiment.unity에서 켬)이 켜져 있으면 시작·확인·다음 참여자 때마다 Apply(권고 설정 + 멈춤 거리 절차 값)와
//   문구 파일 scaleA를 다시 적용하고, 실험자 화면은 고정 항목의 토글 대신 아래 요약만 보인다. 확인·시작 때 Holds·TaskTextProblems가
//   어긋나면 시작을 거부한다.
//   고정 항목 = ApplyExperimentPreset이 정하는 값(공간 neutral·놓기 도움·두 조건 연습·점검 문항 앞·평정 중 물체 숨김·UI 묶음 (1)–(6)·
//   반복 멈춤 loop·눈높이 relative) + 멈춤 거리 절차 값(아래 상수, G60-2·G78-a — CP16-1) + 문구 파일 scaleA(판 ExpectedTaskTextVersion과
//   G78 새 키 네 개 — CP16-4). 참여자 입력(inputMode)은 preset이 정하지 않으므로 고정하지 않는다(화면에 그대로).
//   고정하지 않는 것(G78-g): 안내 판 숨기기, 선택 단계 문항, 묻지 않을 문항 키, 참여자 컨트롤러 평정, 보기만 통제 방식, 참여자 입력.
// 멈춤 거리 절차 값은 여기에만 적는다(기준 = PlacementConfig 코드 기본값). 기본값이 바뀌면 PlacementSetupAutoTests가 깨진다 —
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
        /// <summary>잠금이 받는 문구 파일 판(G78-e). 문구 판을 올리면 여기도 올린다.</summary>
        public const string ExpectedTaskTextVersion = "0.8-scaleA";
        /// <summary>잠금 문구 파일에 있어야 하는 G78 새 키.</summary>
        public static readonly string[] RequiredTaskTextKeys =
        {
            PlacementTaskText.ConfirmButtonRightKey, PlacementTaskText.ConfirmButtonLeftKey, PlacementTaskText.ConfirmDoneKey, PlacementTaskText.StopMainStartKey,
        };

        // ── 멈춤 거리 절차 값(G60-2 · G78-a) ────────────────────────────
        public const double StopSpeedMps = 0.25;
        public const double StopHeightM = 1.2;
        public const double StopItiSeconds = 2.0;
        public const string StopFirstDirection = PlacementConfig.FirstByParticipant;
        public const double StopLoopMinM = 0.4;
        public const double StopLoopMaxM = 3.6;
        public const double StopLoopStartMinM = 1.0;
        public const double StopLoopStartMaxM = 3.0;
        public const int StopLoopRounds = 4;
        public const int StopLoopPracticeRounds = 1;
        public const double StopLoopRoundSeconds = 75;
        public const double StopLoopPracticeRoundSeconds = 30;
        public const double StopLoopToggleDebounceMs = 250;
        public const bool StopLoopHideRings = true;

        /// <summary>잠금 적용: 권고 설정(ApplyExperimentPreset) + 멈춤 거리 절차 값. 문구 파일은 러너가 TaskTextFile로 고른다.</summary>
        public static void Apply(PlacementConfig cfg)
        {
            if (cfg == null) return;
            cfg.ApplyExperimentPreset();
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

        /// <summary>설정과 문구 파일 이름이 잠금 값 그대로다(문구 파일 내용은 TaskTextProblems).</summary>
        public static bool Holds(PlacementConfig cfg, string taskTextName) =>
            cfg != null && cfg.ExperimentPresetOn && StopMismatches(cfg).Count == 0 && SameTaskText(taskTextName, TaskTextFile);

        /// <summary>잠금이 거부할 이유(설정·문구 파일 이름·읽은 문구 파일의 판과 키). 없으면 빈 목록. 러너가 확인·시작 때 오류로 낸다.</summary>
        public static List<string> Refusals(PlacementConfig cfg, string taskTextName, PlacementTaskText text)
        {
            var e = new List<string>();
            if (cfg == null) { e.Add("설정 없음"); return e; }
            if (!cfg.ExperimentPresetOn) e.Add("권고 설정(ApplyExperimentPreset) 값이 아님");
            e.AddRange(StopMismatches(cfg));
            if (!SameTaskText(taskTextName, TaskTextFile)) e.Add($"문구 파일 {taskTextName}(잠금 {TaskTextFile})");
            e.AddRange(TaskTextProblems(text));
            return e.Select(x => "본 실험 설정 고정: " + x + " — 시작하지 않습니다").ToList();
        }

        /// <summary>읽은 문구 파일이 잠금 판(ExpectedTaskTextVersion)이고 G78 새 키 네 개가 있는가. 문제 목록(없으면 빈 목록).</summary>
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
            string space = cfg.environment == PlacementConfig.EnvironmentNeutral && cfg.placementAssist ? "B" : "B 아님";
            string stop = cfg.IsStopLoop
                ? $"loop: 연습 {cfg.stopLoopPracticeRounds} × 상한 {N(cfg.stopLoopPracticeRoundSeconds)}초 + 본 {cfg.stopLoopRounds} × 상한 {N(cfg.stopLoopRoundSeconds)}초, " +
                  $"라운드 사이 {N(cfg.stopItiSeconds)}초, 왕복 {N(cfg.stopLoopMinM)}–{N(cfg.stopLoopMaxM)} m · {N(cfg.stopSpeedMps)} m/s"
                : cfg.stopMode;
            string eye = cfg.IsEyeRelative ? $"relative(기준 {cfg.eyeHeightReferenceM.ToString("0.00", inv)} m)" : cfg.eyeHeightMode;
            string task = (taskTextName ?? "").Replace('\\', '/');
            int slash = task.LastIndexOf('/');
            if (slash >= 0) task = task.Substring(slash + 1);
            return new List<string>
            {
                $"공간 {cfg.environment}(후보 {space}) · 놓기 도움 {OnOff(cfg.placementAssist)} · 두 조건 배치 연습 {OnOff(cfg.practiceInAllConditions)} (G59-8)",
                $"평정 동안 물체 숨기기 {OnOff(cfg.hideObjectDuringItems)} · 점검 문항을 멈춤 거리 앞에 {OnOff(cfg.checkBeforeStopDistance)} (G59-8)",
                $"멈춤 거리 {stop} (G60-2·G78-a)",
                $"눈높이 기준 배치 {eye} (G60-3) · 헤드셋 UI 개선 묶음 (1)–(6) {OnOff(cfg.UiBundleOn)} (G63)",
                $"문구 파일 {task}{(taskTextVersion != null ? " 판 " + taskTextVersion : "")} (G59-8·G78-e)",
            };
        }
    }
}
