// 배치 실험(RQ V4) 설정. 통제 조건·공간·멈춤 거리 매개변수는 모두 여기 있다(팀 결정 전이라 코드에 박지 않는다).
// 기본값은 docs/rq-v4-proposal.md 4.3–4.5절과 docs/decisions.md X45·X49의 잠정값이다. 값 전체를 manifest.json의 config에 남긴다.
// UnityEngine에 의존하지 않는다(Inspector에서 바꿀 수 있다 — 바꾸면 결정 기록에 남길 것).
using System;
using System.Collections.Generic;
using System.Linq;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.Placement
{
    [Serializable]
    public sealed class PlacementConfig
    {
        public const string ConditionPlace = "place";
        public const string ConditionView = "view";
        public const string ModeNone = "none";
        public const string ModeStatic = "static";
        public const string ModeSystemMove = "system_move";
        public const string ModeReplay = "replay";
        public const string ModePointSelect = "point_select";
        public const string DirectionApproach = "approach";
        public const string DirectionRecede = "recede";
        public const string FirstByParticipant = "by_participant";

        public static readonly string[] Conditions = { ConditionPlace, ConditionView };
        public static readonly string[] ViewModes = { ModeStatic, ModeSystemMove, ModeReplay, ModePointSelect };

        // ── 조건 ──────────────────────────────────────────────────────
        /// <summary>place(직접 배치) | view(보기만)</summary>
        public string condition = ConditionPlace;
        /// <summary>view일 때 통제 방식: static | system_move | replay | point_select. place면 무시(기록은 none).</summary>
        public string controlMode = ModeStatic;

        // ── 공간(X45) ─────────────────────────────────────────────────
        /// <summary>원형 바닥 반지름(m). 중심 = '나'의 자리.</summary>
        public double floorRadiusM = 4.0;
        /// <summary>옅은 거리 고리 반지름(m). 각각 (0, floorRadiusM).</summary>
        public double[] ringRadiiM = { 1.0, 2.0, 3.0 };
        /// <summary>끄면 고리를 그리지 않는다("여기 두라"는 선택지로 읽힐 수 있어서).</summary>
        public bool showRings = true;
        /// <summary>물체 시작 위치: 정면(+z) 수평 거리(m)와 물체 중심 높이(m).</summary>
        public double startDistanceM = 1.5;
        public double startHeightM = 1.2;

        // ── 단계 시간 ─────────────────────────────────────────────────
        /// <summary>제시(baseline) 단계 길이(초).</summary>
        public double baselineSeconds = 30;
        /// <summary>조건 단계 길이(초). 두 조건이 같다.</summary>
        public double conditionSeconds = 90;
        /// <summary>켜면 직접 배치에서 확인("여기에 둔다")을 누르는 순간 조건 단계를 끝낸다. 기본 꺼짐(단계 길이 고정).</summary>
        public bool conditionEndsOnConfirm = false;
        /// <summary>머리 자세·물체 위치·궤적 표본 빈도(Hz).</summary>
        public double headSampleHz = 20;

        // ── 잡기–옮기기(직접 배치) ─────────────────────────────────────
        /// <summary>당기기/밀기 축(−1..1) 1일 때 잡은 거리 변화 속도(m/s).</summary>
        public double pushPullSpeedMps = 1.0;
        /// <summary>광선 원점에서 잡은 물체까지 거리의 범위(m).</summary>
        public double holdMinM = 0.3;
        public double holdMaxM = 8.0;
        /// <summary>광선 잡기 판정 구의 최소 반지름(m). 물체 경계가 이보다 작으면 이 값으로 잡는다.</summary>
        public double grabRadiusMinM = 0.15;
        /// <summary>물체 중심 높이 범위(m). 중력은 없다.</summary>
        public double minHeightM = 0.05;
        public double maxHeightM = 2.5;

        // ── 보기만: 시스템 이동·가리켜 지정 ─────────────────────────────
        /// <summary>system_move 목표 자리: '나' 기준 수평 거리(m), 방위(도, 오른쪽 +), 높이(m). 잠정값.</summary>
        public double systemMoveTargetDistanceM = 2.5;
        public double systemMoveTargetAzimuthDeg = 0;
        public double systemMoveTargetHeightM = 1.2;
        /// <summary>system_move·point_select의 직선 이동 속도(m/s).</summary>
        public double systemMoveSpeedMps = 0.25;
        /// <summary>system_move가 조건 단계 시작 뒤 움직이기 시작하는 시각(초).</summary>
        public double systemMoveDelaySeconds = 2;

        // ── 보기만: 재생 ──────────────────────────────────────────────
        /// <summary>replay 원본 trajectory.json 경로. 절대 경로이거나 기록 루트 기준 상대 경로. manifest에는 파일 이름과 sha256만 남긴다.</summary>
        public string replayPath = "";

        // ── 멈춤 거리(X49) ────────────────────────────────────────────
        public double stopSpeedMps = 0.25;
        public double stopApproachStartM = 3.0;
        public double stopRecedeStartM = 0.5;
        public int stopTrialsPerDirection = 4;
        /// <summary>연습 시행 수(전체). 방향을 번갈아 둔다.</summary>
        public int stopPracticeTrials = 2;
        /// <summary>가까워지는 시행이 여기 닿으면 timed_out(m).</summary>
        public double stopMinM = 0.2;
        /// <summary>멀어지는 시행이 여기 닿으면 timed_out(m). floorRadiusM 이하.</summary>
        public double stopMaxM = 4.0;
        /// <summary>시행 사이 물체를 숨기는 시간(초).</summary>
        public double stopItiSeconds = 2.0;
        /// <summary>멈춤 거리 단계의 물체 중심 높이(m).</summary>
        public double stopHeightM = 1.2;
        /// <summary>첫 방향: approach | recede | by_participant(홀수 번호 approach, 짝수 recede).</summary>
        public string stopFirstDirection = FirstByParticipant;

        /// <summary>켜면 문구 파일에 status draft 문구가 하나라도 있을 때 세션 시작을 거부한다(IRB 확인 뒤 본 실험용).</summary>
        public bool requireSpecPhrases = false;

        // ── 헤드셋(2026-11-23 프로토타입) ──────────────────────────────
        /// <summary>참여자 입력: auto(XR 헤드셋이 켜져 있으면 XR 컨트롤러, 없으면 데스크톱) | desktop | xr(헤드셋이 없으면 시작 거부).</summary>
        public string inputMode = InputModeAuto;
        /// <summary>XR 컨트롤러 주 사용 손: right | left.</summary>
        public string xrHand = HandRight;
        /// <summary>켜면 평정 단계에서 참여자가 썸스틱 좌우로 고르고 트리거로 확정할 수도 있다(실험자 키보드 입력도 그대로 된다).
        /// 기본 꺼짐: 참여자는 말로 답하고 실험자가 숫자를 넣는다.</summary>
        public bool participantRatesWithController = false;
        /// <summary>켜면 평정 단계(pre/post/check items) 동안 물체를 숨긴다(docs/rq-v4-questionnaire-draft.md 제안). 절차 변경이라 기본 꺼짐.</summary>
        public bool hideObjectDuringItems = false;

        public const string InputModeAuto = "auto";
        public const string InputModeDesktop = "desktop";
        public const string InputModeXr = "xr";
        public const string HandRight = "right";
        public const string HandLeft = "left";
        public static readonly string[] InputModes = { InputModeAuto, InputModeDesktop, InputModeXr };
        public static readonly string[] Hands = { HandRight, HandLeft };

        public PlacementConfig Clone()
        {
            var c = (PlacementConfig)MemberwiseClone();
            c.ringRadiiM = (double[])(ringRadiiM ?? new double[0]).Clone();
            return c;
        }

        public bool IsPlace => condition == ConditionPlace;
        /// <summary>manifest의 controlMode: place면 none.</summary>
        public string EffectiveControlMode => IsPlace ? ModeNone : controlMode;

        /// <summary>참여자 번호로 정한 첫 방향(approach | recede).</summary>
        public string FirstDirectionFor(int participantNumber)
        {
            if (stopFirstDirection == DirectionApproach || stopFirstDirection == DirectionRecede) return stopFirstDirection;
            return participantNumber % 2 == 1 ? DirectionApproach : DirectionRecede;
        }

        static bool Finite(double v) => !double.IsNaN(v) && !double.IsInfinity(v);

        public List<string> Validate()
        {
            var e = new List<string>();
            if (!Conditions.Contains(condition)) e.Add($"condition {condition}: place | view 중 하나");
            if (condition == ConditionView && !ViewModes.Contains(controlMode))
                e.Add($"controlMode {controlMode}: static | system_move | replay | point_select 중 하나");
            if (condition == ConditionView && controlMode == ModeReplay && string.IsNullOrWhiteSpace(replayPath))
                e.Add("controlMode replay에는 replayPath(trajectory.json)가 필요함");
            if (!(Finite(floorRadiusM) && floorRadiusM > 0)) e.Add($"floorRadiusM {floorRadiusM}: 0보다 커야 함");
            foreach (var r in ringRadiiM ?? new double[0])
                if (!(Finite(r) && r > 0 && r < floorRadiusM)) e.Add($"ringRadiiM {r}: (0, floorRadiusM) 밖");
            if (!(Finite(startDistanceM) && startDistanceM > 0 && startDistanceM <= floorRadiusM)) e.Add($"startDistanceM {startDistanceM}: (0, floorRadiusM] 밖");
            if (!(Finite(minHeightM) && Finite(maxHeightM) && minHeightM >= 0 && maxHeightM > minHeightM)) e.Add($"minHeightM {minHeightM} / maxHeightM {maxHeightM}: 0 ≤ min < max");
            if (!(startHeightM >= minHeightM && startHeightM <= maxHeightM)) e.Add($"startHeightM {startHeightM}: [minHeightM, maxHeightM] 밖");
            if (!(Finite(baselineSeconds) && baselineSeconds > 0)) e.Add($"baselineSeconds {baselineSeconds}: 0보다 커야 함");
            if (!(Finite(conditionSeconds) && conditionSeconds > 0)) e.Add($"conditionSeconds {conditionSeconds}: 0보다 커야 함");
            if (!(headSampleHz > 0 && headSampleHz <= 200)) e.Add($"headSampleHz {headSampleHz}: (0, 200] 밖");
            if (!(Finite(pushPullSpeedMps) && pushPullSpeedMps > 0)) e.Add($"pushPullSpeedMps {pushPullSpeedMps}: 0보다 커야 함");
            if (!(Finite(holdMinM) && Finite(holdMaxM) && holdMinM > 0 && holdMaxM > holdMinM)) e.Add($"holdMinM {holdMinM} / holdMaxM {holdMaxM}: 0 < min < max");
            if (!(Finite(grabRadiusMinM) && grabRadiusMinM > 0)) e.Add($"grabRadiusMinM {grabRadiusMinM}: 0보다 커야 함");
            if (!(Finite(systemMoveSpeedMps) && systemMoveSpeedMps > 0)) e.Add($"systemMoveSpeedMps {systemMoveSpeedMps}: 0보다 커야 함");
            if (!(Finite(systemMoveDelaySeconds) && systemMoveDelaySeconds >= 0)) e.Add($"systemMoveDelaySeconds {systemMoveDelaySeconds}: 0 이상");
            if (!(Finite(systemMoveTargetDistanceM) && systemMoveTargetDistanceM >= 0 && systemMoveTargetDistanceM <= floorRadiusM))
                e.Add($"systemMoveTargetDistanceM {systemMoveTargetDistanceM}: [0, floorRadiusM] 밖");
            if (!(Finite(systemMoveTargetAzimuthDeg) && systemMoveTargetAzimuthDeg > -180 && systemMoveTargetAzimuthDeg <= 180))
                e.Add($"systemMoveTargetAzimuthDeg {systemMoveTargetAzimuthDeg}: (−180, 180] 밖");
            if (!(systemMoveTargetHeightM >= minHeightM && systemMoveTargetHeightM <= maxHeightM)) e.Add($"systemMoveTargetHeightM {systemMoveTargetHeightM}: [minHeightM, maxHeightM] 밖");
            if (!(Finite(stopSpeedMps) && stopSpeedMps > 0)) e.Add($"stopSpeedMps {stopSpeedMps}: 0보다 커야 함");
            if (!(Finite(stopMinM) && Finite(stopMaxM) && stopMinM >= 0 && stopMaxM > stopMinM)) e.Add($"stopMinM {stopMinM} / stopMaxM {stopMaxM}: 0 ≤ min < max");
            if (!(stopMaxM <= floorRadiusM)) e.Add($"stopMaxM {stopMaxM}: floorRadiusM {floorRadiusM} 이하여야 함(바닥 밖으로 나가지 않게)");
            if (!(stopApproachStartM > stopMinM && stopApproachStartM <= stopMaxM)) e.Add($"stopApproachStartM {stopApproachStartM}: (stopMinM, stopMaxM] 밖");
            if (!(stopRecedeStartM >= stopMinM && stopRecedeStartM < stopMaxM)) e.Add($"stopRecedeStartM {stopRecedeStartM}: [stopMinM, stopMaxM) 밖");
            if (stopTrialsPerDirection < 1) e.Add($"stopTrialsPerDirection {stopTrialsPerDirection}: 1 이상");
            if (stopPracticeTrials < 0) e.Add($"stopPracticeTrials {stopPracticeTrials}: 0 이상");
            if (!(Finite(stopItiSeconds) && stopItiSeconds >= 0)) e.Add($"stopItiSeconds {stopItiSeconds}: 0 이상");
            if (!(stopHeightM >= minHeightM && stopHeightM <= maxHeightM)) e.Add($"stopHeightM {stopHeightM}: [minHeightM, maxHeightM] 밖");
            if (stopFirstDirection != DirectionApproach && stopFirstDirection != DirectionRecede && stopFirstDirection != FirstByParticipant)
                e.Add($"stopFirstDirection {stopFirstDirection}: approach | recede | by_participant 중 하나");
            if (!InputModes.Contains(inputMode)) e.Add($"inputMode {inputMode}: auto | desktop | xr 중 하나");
            if (!Hands.Contains(xrHand)) e.Add($"xrHand {xrHand}: right | left 중 하나");
            return e;
        }

        public JObject ToJson() => new JObject
        {
            ["condition"] = condition,
            ["controlMode"] = controlMode,
            ["floorRadiusM"] = floorRadiusM,
            ["ringRadiiM"] = new JArray((ringRadiiM ?? new double[0]).Cast<object>().ToArray()),
            ["showRings"] = showRings,
            ["startDistanceM"] = startDistanceM,
            ["startHeightM"] = startHeightM,
            ["baselineSeconds"] = baselineSeconds,
            ["conditionSeconds"] = conditionSeconds,
            ["conditionEndsOnConfirm"] = conditionEndsOnConfirm,
            ["headSampleHz"] = headSampleHz,
            ["pushPullSpeedMps"] = pushPullSpeedMps,
            ["holdMinM"] = holdMinM,
            ["holdMaxM"] = holdMaxM,
            ["grabRadiusMinM"] = grabRadiusMinM,
            ["minHeightM"] = minHeightM,
            ["maxHeightM"] = maxHeightM,
            ["systemMoveTargetDistanceM"] = systemMoveTargetDistanceM,
            ["systemMoveTargetAzimuthDeg"] = systemMoveTargetAzimuthDeg,
            ["systemMoveTargetHeightM"] = systemMoveTargetHeightM,
            ["systemMoveSpeedMps"] = systemMoveSpeedMps,
            ["systemMoveDelaySeconds"] = systemMoveDelaySeconds,
            ["replayFile"] = string.IsNullOrWhiteSpace(replayPath) ? null : Ownership.OwnershipManifest.FileNameOnly(replayPath),   // 경로는 남기지 않는다
            ["stopSpeedMps"] = stopSpeedMps,
            ["stopApproachStartM"] = stopApproachStartM,
            ["stopRecedeStartM"] = stopRecedeStartM,
            ["stopTrialsPerDirection"] = stopTrialsPerDirection,
            ["stopPracticeTrials"] = stopPracticeTrials,
            ["stopMinM"] = stopMinM,
            ["stopMaxM"] = stopMaxM,
            ["stopItiSeconds"] = stopItiSeconds,
            ["stopHeightM"] = stopHeightM,
            ["stopFirstDirection"] = stopFirstDirection,
            ["requireSpecPhrases"] = requireSpecPhrases,
            // 2026-11-23 추가(헤드셋). 기존 키는 그대로다.
            ["inputMode"] = inputMode,
            ["xrHand"] = xrHand,
            ["participantRatesWithController"] = participantRatesWithController,
            ["hideObjectDuringItems"] = hideObjectDuringItems,
        };
    }
}
