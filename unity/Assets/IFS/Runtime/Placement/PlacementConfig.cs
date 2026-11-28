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

        // ── 평정 문항(2026-11-23 D8) ───────────────────────────────────
        /// <summary>켜면 문구 파일 문항의 optionalWhen 단계에서도 묻는다. 두 평정 문항(모습 일치·대표성, G13)은 when post · optionalWhen pre라
        /// 기본(꺼짐)에서는 헤드셋에서 사후에만 묻는다(사전 측정은 데스크톱에서 하므로 — G11). 사전에도 물으려면 켠다.</summary>
        public bool askOptionalItems = false;
        /// <summary>묻지 않을 평정 문항 키(예: 기존 "내 것 같다" 문항 own·S4를 끌 때). 문구 파일에 없는 키면 확인 단계에서 오류.</summary>
        public string[] disabledItems = new string[0];

        // ── 배치 공간 후보(G52–G55, 2026-11-24) ────────────────────────
        // 후보 B = neutral + 놓기 도움, E = space + 놓기 도움, F = nature + 놓기 도움. 어느 것을 본 설계로 쓸지는 정하지 않았다(⚠ 사람이 정할 것).
        // 기본값(neutral, 도움 꺼짐)에서는 화면·기록이 G52 전과 바이트 단위로 같다 — 아래 키는 기본값이 아닐 때만 manifest에 남는다.
        /// <summary>배경 공간: neutral(지금 회색 하늘, 기본) | space(별 하늘, G54) | nature(CC0 360° 사진 + 3D 땅, G55).</summary>
        public string environment = EnvironmentNeutral;
        /// <summary>놓기 도움(G53): 본 과제 앞 배치 연습 1회, 든 동안 수직선·바닥 고리, 경계 띠 밝아짐, 범위 안내 문장. 기본 꺼짐.</summary>
        public bool placementAssist = false;
        /// <summary>배치 연습의 목표 자리('나' 기준 수평 거리 m, 방위 도(오른쪽 +), 상자 중심 높이 m). 잠정값 — ⚠ 사람이 정할 것(G53).</summary>
        public double practiceTargetDistanceM = 2.0;
        public double practiceTargetAzimuthDeg = -45;
        public double practiceTargetHeightM = 0.8;
        /// <summary>연습 상자 한 변(m).</summary>
        public double practiceCubeSizeM = 0.25;
        /// <summary>공간을 누가 정하나(2026-11-28 연구 책임자 결정): experimenter(기본 — 위 environment 그대로, 예전과 같음) |
        /// participant(세션 첫 단계 space_choice에서 참여자가 헤드셋 안에서 세 공간을 차례로 보고 확인 버튼으로 고름. environment는
        /// 고르기 전·대기 동안의 공간이고, 고른 값이 세션의 environment가 된다 — PlacementSpaceChoice). participant일 때만 config 끝에 키를 남긴다.</summary>
        public string environmentChoice = EnvironmentChoiceExperimenter;

        // ── 절차 선택(G59, 2026-11-25) ─────────────────────────────────
        // 논문 심사 관점 검토에서 나온 보완. 둘 다 기본 꺼짐이고, 기본값에서는 화면·기록이 G59 전과 바이트 단위로 같다
        // (켰을 때만 manifest config 맨 끝에 키를 남긴다). 본 설계에 쓸지는 정하지 않았다(⚠ 사람이 정할 것).
        /// <summary>켜면 점검 문항(when check)을 멈춤 거리 앞, 사후 평정 바로 뒤에 묻는다
        /// (condition → post_items → check_items → post_wait → stop_distance → done). 기본 꺼짐: 멈춤 거리 뒤(예전 순서).
        /// 멈춤 거리에서 버튼을 누른 뒤에는 보기만 조건도 "자리는 내가 정했다"에 그렇다고 답할 수 있고 "방금 있던 자리"도 모호해지기 때문.</summary>
        public bool checkBeforeStopDistance = false;
        /// <summary>켜면 놓기 도움(placementAssist)의 배치 연습(뜻 없는 회색 상자 옮기기 1회)을 보기만 조건에서도 한다
        /// (조건 전 컨트롤러 경험을 두 조건에서 같게). placementAssist를 켰을 때만 쓴다(꺼져 있으면 확인 단계에서 오류). 기본 꺼짐.</summary>
        public bool practiceInAllConditions = false;

        // ── 멈춤 거리 반복 멈춤(G60-2, 2026-11-26 교수님 피드백 2) ───────────
        // 기본 single = 예전 과제(한 번 누르면 시행 끝, X49) 그대로 — 화면·기록이 G60 전과 바이트 단위로 같다.
        // loop = 정면 직선 위 왕복(stopLoopMinM ↔ stopLoopMaxM, 속도 stopSpeedMps, 끝에서 감속 없이 되돌아감).
        //   트리거(데스크톱 Space) = 멈춤/다시 움직임 토글(다시 움직이면 멈추기 전 방향 그대로), A·X(데스크톱 F) = 확정(멈춘 상태에서만).
        //   연습 stopLoopPracticeRounds(상한 stopLoopPracticeRoundSeconds) + 본 stopLoopRounds(상한 stopLoopRoundSeconds) 라운드, 라운드마다 출발 방향을 번갈아 두고(첫 방향 = stopFirstDirection),
        //   출발 거리는 [stopLoopStartMinM, stopLoopStartMaxM]에서 참여자 번호를 시드로 한 xorshift64*(StopLoopSchedule)로 정한다.
        //   기록은 stoprounds.csv·stopadjust.csv(새 파일)와 manifest stopDistance.mode·loop. 아래 키는 loop일 때만 config 맨 끝에 남는다.
        //   ⚠ 본 설계로 쓸지는 사람이 정할 것(docs/decisions.md G60).
        /// <summary>멈춤 거리 방식: single(기본, 한 번 누름) | loop(왕복 + 멈춤/재개 + 확정).</summary>
        public string stopMode = StopModeSingle;
        /// <summary>loop 왕복 경로의 가까운 끝·먼 끝(m, '나' 기준 수평 거리).</summary>
        public double stopLoopMinM = 0.4;
        public double stopLoopMaxM = 3.6;
        /// <summary>loop 출발 거리 범위(m). 라운드마다 이 안에서 의사난수로 고른다.</summary>
        public double stopLoopStartMinM = 1.0;
        public double stopLoopStartMaxM = 3.0;
        /// <summary>loop 본 라운드 수와 연습 라운드 수. 본 라운드는 2026-11-28 연구 책임자 결정(G83)으로 4 → 1: 라운드를 되풀이하지 않고
        /// 상한 시간(stopLoopRoundSeconds) 안에 언제든 멈추고 다시 움직이다 확인 버튼으로 한 번 정한다. 연습 1 + 본 1이면 출발 방향은
        /// 연습 = 첫 방향, 본 = 그 반대(StopLoopSchedule). 2 이상도 그대로 돈다(예전 4라운드 기록·설정).</summary>
        public int stopLoopRounds = 1;
        public int stopLoopPracticeRounds = 1;
        /// <summary>loop 라운드 시간 상한(초, 움직이기 시작한 때부터). 넘으면 확정값은 빈칸(end_reason timeout_*).</summary>
        public double stopLoopRoundSeconds = 75;
        /// <summary>loop 연습 라운드의 시간 상한(초). 본 라운드는 stopLoopRoundSeconds 그대로. 2026-11-28 연구 책임자 요청
        /// (연습을 30초 안 1번으로 — 연습 라운드 수는 stopLoopPracticeRounds 1). 넘으면 본 라운드와 같이 확정값 빈칸(end_reason timeout_*).</summary>
        public double stopLoopPracticeRoundSeconds = 30;
        /// <summary>loop 토글(멈춤/다시 움직임) 사이 이 시간(ms) 안의 다시 누름은 버린다(사건으로만 남김).</summary>
        public double stopLoopToggleDebounceMs = 250;
        /// <summary>loop 멈춤 거리 단계 동안 바닥 거리 고리를 숨긴다(고리가 방금 놓은 거리를 맞추는 자가 되지 않게). loop일 때만 쓴다.</summary>
        public bool stopLoopHideRings = true;

        // ── 눈높이 정규화(G60-3, 2026-11-26 교수님 피드백 3) ─────────────────
        // 기본 none = 예전 그대로(물체 높이는 세계 절대값). relative = 물체·경로 높이를 참여자 눈높이 E 기준으로 옮긴다:
        //   실제 높이 = 설정 높이 + (E − eyeHeightReferenceM). 대상: 시작 높이, 멈춤 경로 높이, system_move 목표, 연습 목표, 문구 판.
        //   카메라·리그 높이와 수평 거리, 참여자가 직접 놓은 높이는 바꾸지 않는다. E는 Check 단계 실험자 키 H로 잰다(EyeHeightCalibration).
        //   아래 키는 relative일 때만 config 맨 끝에 남는다. ⚠ 본 설계로 쓸지는 사람이 정할 것.
        /// <summary>눈높이 기준: none(기본, 절대 높이) | relative(눈높이 기준 상대 배치).</summary>
        public string eyeHeightMode = EyeHeightNone;
        /// <summary>기준 눈높이(m). 이 눈높이에서는 none과 같은 자리가 된다.</summary>
        public double eyeHeightReferenceM = 1.6;
        /// <summary>보정 통과 범위(m) — 선 자세(eyeCalibPosture standing, 기본).</summary>
        public double eyeHeightMinM = 1.30;
        public double eyeHeightMaxM = 1.95;
        /// <summary>보정·과제 자세(2026-11-28, 연구 책임자: 본 실험은 앉아서 한다): standing(기본, 예전과 같음 — 범위 eyeHeightMinM–MaxM) |
        /// seated(범위 eyeHeightSeatedMinM–MaxM). 보정은 과제를 하는 자세로 한다. seated일 때만 config 끝에 키를 남긴다.</summary>
        public string eyeCalibPosture = PostureStanding;
        /// <summary>앉은 자세 보정 통과 범위(m). 잠정값 — 의자 앉는 면 0.40–0.50 m + 앉은 눈높이 0.69–0.85 m ≈ 1.09–1.35 m에 여유(⚠ 연구 책임자 확인).</summary>
        public double eyeHeightSeatedMinM = 0.95;
        public double eyeHeightSeatedMaxM = 1.45;
        /// <summary>보정 표본 시간(초, 20 Hz).</summary>
        public double eyeCalibSeconds = 1.0;
        /// <summary>보정 통과 조건: 표본 표준편차(m) 이하, 머리 pitch 절댓값(도) 이하.</summary>
        public double eyeCalibMaxSdM = 0.02;
        public double eyeCalibMaxPitchDeg = 15;

        // ── 헤드셋 UI 개선(G63, 2026-11-27 — research_notes/VR UI 가독성 기준/vr_ui_guidelines.md) ─────────
        // 모두 기본 꺼짐: 기본값에서는 화면·기록이 G63 전과 바이트 단위로 같다(하나라도 켰을 때만 config 맨 끝에 ui* 키를 남긴다).
        // 두 조건(직접 배치·보기만)이 같이 쓰는 요소(판·평정 UI·멈춤 거리)는 조건과 상관없이 똑같이 바뀐다. 문구 글자·문항·단계 순서·
        // 평정 방식(점 수·앵커·확정 방식)·물체 겉모습·공간(B/E/F)은 건드리지 않는다. 묶음으로 켜려면 ApplyUiBundle()(-uiBundle true, 실험자 화면).
        /// <summary>(1) 판 아래 가장자리를 수평 아래 35° 안으로: 본문 줄바꿈 20 → 24자(넘치면 26자까지), 평정 지시문은 문장 경계에서 쪽을 나눠
        /// 실험자 Enter로 넘긴다(글자는 그대로, events items_instruction_page).</summary>
        public bool uiComfortWrap = false;
        /// <summary>(2) 어두운 판 테마: 판 #2A2B30 + 글 #E6E6E8(대비 약 11:1, 흰 판 18:1 대신). 공간·물체는 그대로.</summary>
        public bool uiDarkPanel = false;
        /// <summary>(3) 광선 겨눔(hover) 상태: 광선이 잡기 판정 구에 닿으면 광선·끝점 색과 끝점 크기, 잡는 동안 광선 굵기만 바꾼다(물체는 그대로).</summary>
        public bool uiRayHover = false;
        /// <summary>(4) 햅틱: 잡기·놓기·평정 한 칸·평정 확정·확인·멈춤에 짧은 펄스(events haptic, 추가만). 두 조건 공통 사건은 같은 세기.</summary>
        public bool uiHaptics = false;
        /// <summary>(5) 평정 확정 표시: 참여자 컨트롤러로 확정한 칸의 테두리를 0.4초 굵게(0.012 → 0.02 m) 보인 뒤 다음 문항. rt_ms에는 넣지 않는다.</summary>
        public bool uiRatingConfirmFlash = false;
        /// <summary>(6) 7칸 평정 줄 칸 너비 0.22 → 0.20 m(줄 폭 약 41.6° → 38°).</summary>
        public bool uiNarrowScale = false;
        /// <summary>(7) 조건 단계·멈춤 거리 단계에서 안내 판을 hidePanelReadSeconds 뒤 숨긴다(판이 거리 기준점이 되지 않게).
        /// RQ2 결과변수에 닿는 절차 변경이라 묶음(ApplyUiBundle)에서도 켜지 않는다 — ⚠ 사람이 정할 것.</summary>
        public bool hidePanelInDistancePhases = false;
        /// <summary>(7) 판을 숨기기 전 읽을 시간(초, 그 단계 시작부터).</summary>
        public double hidePanelReadSeconds = 8;

        /// <summary>G63 "UI 개선 묶음"을 켠다: (1)–(6). (7) hidePanelInDistancePhases는 켜지 않는다(연구자 결정 필요).</summary>
        public void ApplyUiBundle()
        {
            uiComfortWrap = uiDarkPanel = uiRayHover = uiHaptics = uiRatingConfirmFlash = uiNarrowScale = true;
        }

        /// <summary>묶음의 여섯 플래그가 모두 켜져 있다.</summary>
        public bool UiBundleOn => uiComfortWrap && uiDarkPanel && uiRayHover && uiHaptics && uiRatingConfirmFlash && uiNarrowScale;

        // ── 본 실험 권고 설정(설계 뼈대 3절, docs/design-backbone.md · 결정 G59-8 · G63) ─────────────
        // 기본값은 바꾸지 않는다(뼈대 3절 "코드 기본값은 바꾸지 않는다"). 실험을 돌릴 때 실험자 화면 단추 또는 자동 시행 -experimentPreset true로 켠다.
        /// <summary>권고 설정의 문구 파일(G59-8: scaleA). 설정 값이 아니라 러너가 고르는 파일이라 여기에는 이름만 둔다.</summary>
        public const string ExperimentTaskTextFile = "IFS/placement_task.scaleA.v0.json";

        /// <summary>뼈대 3절 권고 설정을 켠다: 공간 B(neutral + 놓기 도움), 두 조건 모두 배치 연습, 자리(점검) 문항을 멈춤 거리 앞에,
        /// 평정 동안 물체 숨김, 헤드셋 UI 개선 묶음 (1)–(6), 멈춤 거리 반복 멈춤(stopMode loop — G60-4가 want_move를 뺀 전제),
        /// 눈높이 기준 배치(eyeHeightMode relative — G60-3, 헤드셋에서는 보정을 통과해야 시작, 데스크톱·자동 시행은 desktop_fixed).
        /// 조건·통제 방식과 판 숨김(hidePanelInDistancePhases)은 건드리지 않는다(⚠ 사람이 정할 것). 문구 파일 scaleA는 러너가 고른다.</summary>
        public void ApplyExperimentPreset()
        {
            environment = EnvironmentNeutral;
            placementAssist = true;
            practiceInAllConditions = true;
            checkBeforeStopDistance = true;
            hideObjectDuringItems = true;
            ApplyUiBundle();
            stopMode = StopModeLoop;
            eyeHeightMode = EyeHeightRelative;
        }

        /// <summary>뼈대 3절 권고 설정이 모두 켜져 있다(문구 파일은 따로 — 러너가 확인).</summary>
        public bool ExperimentPresetOn => environment == EnvironmentNeutral && ExperimentProcedureOn;
        /// <summary>권고 설정 가운데 공간 이름을 뺀 나머지가 모두 켜져 있다(잠금은 공간을 참여자가 고르게 둔다 — 2026-11-28).</summary>
        public bool ExperimentProcedureOn => placementAssist && practiceInAllConditions
                                             && checkBeforeStopDistance && hideObjectDuringItems && UiBundleOn && IsStopLoop && IsEyeRelative;
        /// <summary>G63 UI 플래그가 하나라도 켜져 있다(manifest config에 ui* 키를 더한다).</summary>
        public bool UsesUiOptions => uiComfortWrap || uiDarkPanel || uiRayHover || uiHaptics || uiRatingConfirmFlash || uiNarrowScale || hidePanelInDistancePhases;

        public const string StopModeSingle = "single";
        public const string StopModeLoop = "loop";
        public static readonly string[] StopModes = { StopModeSingle, StopModeLoop };
        public const string EyeHeightNone = "none";
        public const string EyeHeightRelative = "relative";
        public static readonly string[] EyeHeightModes = { EyeHeightNone, EyeHeightRelative };
        public const string PostureStanding = "standing";
        public const string PostureSeated = "seated";
        public static readonly string[] Postures = { PostureStanding, PostureSeated };
        public const string EnvironmentChoiceExperimenter = "experimenter";
        public const string EnvironmentChoiceParticipant = "participant";
        public static readonly string[] EnvironmentChoices = { EnvironmentChoiceExperimenter, EnvironmentChoiceParticipant };

        /// <summary>멈춤 거리가 왕복 반복 멈춤(G60-2)이다.</summary>
        public bool IsStopLoop => stopMode == StopModeLoop;
        /// <summary>눈높이 기준 상대 배치(G60-3)다.</summary>
        public bool IsEyeRelative => eyeHeightMode == EyeHeightRelative;
        /// <summary>앉은 자세로 보정·과제를 한다(2026-11-28).</summary>
        public bool IsSeated => eyeCalibPosture == PostureSeated;
        /// <summary>자세에 맞는 보정 통과 범위(m).</summary>
        public double EyeRangeMinM => IsSeated ? eyeHeightSeatedMinM : eyeHeightMinM;
        public double EyeRangeMaxM => IsSeated ? eyeHeightSeatedMaxM : eyeHeightMaxM;
        /// <summary>참여자가 헤드셋 안에서 공간을 고른다(세션 첫 단계 space_choice, 2026-11-28).</summary>
        public bool ParticipantChoosesSpace => environmentChoice == EnvironmentChoiceParticipant;

        public const string EnvironmentNeutral = "neutral";
        public const string EnvironmentSpace = "space";
        public const string EnvironmentNature = "nature";
        public static readonly string[] Environments = { EnvironmentNeutral, EnvironmentSpace, EnvironmentNature };

        /// <summary>공간 설정이 기본값이 아니다(manifest에 environment 블록과 config 키를 더한다).</summary>
        public bool UsesSpaceOptions => environment != EnvironmentNeutral || placementAssist;
        /// <summary>이 세션에 배치 연습이 있다: 놓기 도움을 켰고 직접 배치 조건일 때(기본). practiceInAllConditions를 켜면 보기만 조건에서도
        /// (G59 — ⚠ 어느 쪽을 본 설계로 쓸지는 사람이 정할 것).</summary>
        public bool HasPractice => placementAssist && (IsPlace || practiceInAllConditions);

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
            c.disabledItems = (string[])(disabledItems ?? new string[0]).Clone();
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
            foreach (var k in disabledItems ?? new string[0])
                if (string.IsNullOrWhiteSpace(k)) e.Add("disabledItems: 빈 키");
            if (!Environments.Contains(environment)) e.Add($"environment {environment}: neutral | space | nature 중 하나");
            if (!EnvironmentChoices.Contains(environmentChoice)) e.Add($"environmentChoice {environmentChoice}: experimenter | participant 중 하나");
            if (placementAssist)
            {
                if (!(Finite(practiceTargetDistanceM) && practiceTargetDistanceM >= 0 && practiceTargetDistanceM <= floorRadiusM))
                    e.Add($"practiceTargetDistanceM {practiceTargetDistanceM}: [0, floorRadiusM] 밖");
                if (!(Finite(practiceTargetAzimuthDeg) && practiceTargetAzimuthDeg > -180 && practiceTargetAzimuthDeg <= 180))
                    e.Add($"practiceTargetAzimuthDeg {practiceTargetAzimuthDeg}: (−180, 180] 밖");
                if (!(practiceTargetHeightM >= minHeightM && practiceTargetHeightM <= maxHeightM)) e.Add($"practiceTargetHeightM {practiceTargetHeightM}: [minHeightM, maxHeightM] 밖");
                if (!(Finite(practiceCubeSizeM) && practiceCubeSizeM > 0 && practiceCubeSizeM <= 1)) e.Add($"practiceCubeSizeM {practiceCubeSizeM}: (0, 1] 밖");
            }
            if (practiceInAllConditions && !placementAssist)
                e.Add("practiceInAllConditions: 놓기 도움(placementAssist)을 켰을 때만 쓴다(배치 연습은 놓기 도움의 일부)");
            if (!StopModes.Contains(stopMode)) e.Add($"stopMode {stopMode}: single | loop 중 하나");
            if (IsStopLoop)
            {
                if (!(Finite(stopLoopMinM) && Finite(stopLoopMaxM) && stopLoopMinM >= 0 && stopLoopMaxM > stopLoopMinM))
                    e.Add($"stopLoopMinM {stopLoopMinM} / stopLoopMaxM {stopLoopMaxM}: 0 ≤ min < max");
                if (!(stopLoopMaxM <= floorRadiusM)) e.Add($"stopLoopMaxM {stopLoopMaxM}: floorRadiusM {floorRadiusM} 이하여야 함(바닥 밖으로 나가지 않게)");
                if (!(Finite(stopLoopStartMinM) && Finite(stopLoopStartMaxM) && stopLoopStartMinM > stopLoopMinM
                      && stopLoopStartMaxM >= stopLoopStartMinM && stopLoopStartMaxM < stopLoopMaxM))
                    e.Add($"stopLoopStartMinM {stopLoopStartMinM} / stopLoopStartMaxM {stopLoopStartMaxM}: stopLoopMinM < 시작 최소 ≤ 시작 최대 < stopLoopMaxM");
                if (stopLoopRounds < 1) e.Add($"stopLoopRounds {stopLoopRounds}: 1 이상");
                if (stopLoopPracticeRounds < 0) e.Add($"stopLoopPracticeRounds {stopLoopPracticeRounds}: 0 이상");
                if (!(Finite(stopLoopRoundSeconds) && stopLoopRoundSeconds > 0)) e.Add($"stopLoopRoundSeconds {stopLoopRoundSeconds}: 0보다 커야 함");
                if (stopLoopPracticeRounds > 0 && !(Finite(stopLoopPracticeRoundSeconds) && stopLoopPracticeRoundSeconds > 0))
                    e.Add($"stopLoopPracticeRoundSeconds {stopLoopPracticeRoundSeconds}: 0보다 커야 함");
                if (!(Finite(stopLoopToggleDebounceMs) && stopLoopToggleDebounceMs >= 0)) e.Add($"stopLoopToggleDebounceMs {stopLoopToggleDebounceMs}: 0 이상");
            }
            if (!EyeHeightModes.Contains(eyeHeightMode)) e.Add($"eyeHeightMode {eyeHeightMode}: none | relative 중 하나");
            if (IsEyeRelative)
            {
                if (!(Finite(eyeHeightReferenceM) && eyeHeightReferenceM > 0 && eyeHeightReferenceM < 3)) e.Add($"eyeHeightReferenceM {eyeHeightReferenceM}: (0, 3) 밖");
                if (!(Finite(eyeHeightMinM) && Finite(eyeHeightMaxM) && eyeHeightMinM > 0 && eyeHeightMaxM > eyeHeightMinM))
                    e.Add($"eyeHeightMinM {eyeHeightMinM} / eyeHeightMaxM {eyeHeightMaxM}: 0 < min < max");
                if (!Postures.Contains(eyeCalibPosture)) e.Add($"eyeCalibPosture {eyeCalibPosture}: standing | seated 중 하나");
                if (IsSeated && !(Finite(eyeHeightSeatedMinM) && Finite(eyeHeightSeatedMaxM) && eyeHeightSeatedMinM > 0 && eyeHeightSeatedMaxM > eyeHeightSeatedMinM))
                    e.Add($"eyeHeightSeatedMinM {eyeHeightSeatedMinM} / eyeHeightSeatedMaxM {eyeHeightSeatedMaxM}: 0 < min < max");
                if (!(Finite(eyeCalibSeconds) && eyeCalibSeconds > 0 && eyeCalibSeconds <= 10)) e.Add($"eyeCalibSeconds {eyeCalibSeconds}: (0, 10] 밖");
                if (!(Finite(eyeCalibMaxSdM) && eyeCalibMaxSdM > 0)) e.Add($"eyeCalibMaxSdM {eyeCalibMaxSdM}: 0보다 커야 함");
                if (!(Finite(eyeCalibMaxPitchDeg) && eyeCalibMaxPitchDeg > 0 && eyeCalibMaxPitchDeg <= 90)) e.Add($"eyeCalibMaxPitchDeg {eyeCalibMaxPitchDeg}: (0, 90] 밖");
                // 통과 범위의 어느 눈높이에서도 옮긴 높이가 [minHeightM, maxHeightM] 안이어야 한다(보정 뒤에 시작을 거부하지 않게 미리 막는다)
                void Shifted(string name, double h)
                {
                    double lo = h + (EyeRangeMinM - eyeHeightReferenceM), hi = h + (EyeRangeMaxM - eyeHeightReferenceM);
                    if (!(lo >= minHeightM && hi <= maxHeightM))
                        e.Add($"{name} {h}: 눈높이 {EyeRangeMinM}–{EyeRangeMaxM} m에서 옮긴 높이 {lo:0.###}–{hi:0.###} m가 [minHeightM, maxHeightM] 밖");
                }
                Shifted("startHeightM", startHeightM);
                Shifted("stopHeightM", stopHeightM);
                if (condition == ConditionView && controlMode == ModeSystemMove) Shifted("systemMoveTargetHeightM", systemMoveTargetHeightM);
                if (HasPractice) Shifted("practiceTargetHeightM", practiceTargetHeightM);
            }
            if (hidePanelInDistancePhases && !(Finite(hidePanelReadSeconds) && hidePanelReadSeconds > 0 && hidePanelReadSeconds <= 120))
                e.Add($"hidePanelReadSeconds {hidePanelReadSeconds}: (0, 120] 밖");
            return e;
        }

        /// <summary>relative에서 높이를 옮기는 양(E − eyeHeightReferenceM). none이면 0.</summary>
        public double EyeOffsetFor(double eyeHeightM) => IsEyeRelative ? eyeHeightM - eyeHeightReferenceM : 0;

        public JObject ToJson()
        {
            var j = BaseJson();
            if (UsesSpaceOptions)
            {
                // 2026-11-24 추가(G52). 기본값이면 넣지 않는다(기존 기록과 바이트 단위로 같게).
                j["environment"] = environment;
                j["placementAssist"] = placementAssist;
                j["practiceTargetDistanceM"] = practiceTargetDistanceM;
                j["practiceTargetAzimuthDeg"] = practiceTargetAzimuthDeg;
                j["practiceTargetHeightM"] = practiceTargetHeightM;
                j["practiceCubeSizeM"] = practiceCubeSizeM;
            }
            // 2026-11-25 추가(G59). 켰을 때만 넣는다(기본값이면 기존 기록과 바이트 단위로 같게).
            if (checkBeforeStopDistance) j["checkBeforeStopDistance"] = true;
            if (practiceInAllConditions) j["practiceInAllConditions"] = true;
            // 2026-11-26 추가(G60-2·G60-3). 기본값(single·none)이 아닐 때만 넣는다(기존 기록과 바이트 단위로 같게).
            if (IsStopLoop)
            {
                j["stopMode"] = stopMode;
                j["stopLoopMinM"] = stopLoopMinM;
                j["stopLoopMaxM"] = stopLoopMaxM;
                j["stopLoopStartMinM"] = stopLoopStartMinM;
                j["stopLoopStartMaxM"] = stopLoopStartMaxM;
                j["stopLoopRounds"] = stopLoopRounds;
                j["stopLoopPracticeRounds"] = stopLoopPracticeRounds;
                j["stopLoopRoundSeconds"] = stopLoopRoundSeconds;
                j["stopLoopPracticeRoundSeconds"] = stopLoopPracticeRoundSeconds;   // 2026-11-28 추가(loop일 때만)
                j["stopLoopToggleDebounceMs"] = stopLoopToggleDebounceMs;
                j["stopLoopHideRings"] = stopLoopHideRings;
            }
            if (IsEyeRelative)
            {
                j["eyeHeightMode"] = eyeHeightMode;
                j["eyeHeightReferenceM"] = eyeHeightReferenceM;
                j["eyeHeightMinM"] = eyeHeightMinM;
                j["eyeHeightMaxM"] = eyeHeightMaxM;
                j["eyeCalibSeconds"] = eyeCalibSeconds;
                j["eyeCalibMaxSdM"] = eyeCalibMaxSdM;
                j["eyeCalibMaxPitchDeg"] = eyeCalibMaxPitchDeg;
                if (IsSeated)
                {
                    // 2026-11-28 추가(앉은 자세). standing(기본)이면 넣지 않는다(기존 기록과 같은 바이트)
                    j["eyeCalibPosture"] = eyeCalibPosture;
                    j["eyeHeightSeatedMinM"] = eyeHeightSeatedMinM;
                    j["eyeHeightSeatedMaxM"] = eyeHeightSeatedMaxM;
                }
            }
            // 2026-11-27 추가(G63 헤드셋 UI). 하나라도 켰을 때만 넣는다(기본값이면 기존 기록과 바이트 단위로 같게).
            if (UsesUiOptions)
            {
                j["uiComfortWrap"] = uiComfortWrap;
                j["uiDarkPanel"] = uiDarkPanel;
                j["uiRayHover"] = uiRayHover;
                j["uiHaptics"] = uiHaptics;
                j["uiRatingConfirmFlash"] = uiRatingConfirmFlash;
                j["uiNarrowScale"] = uiNarrowScale;
                j["hidePanelInDistancePhases"] = hidePanelInDistancePhases;
                if (hidePanelInDistancePhases) j["hidePanelReadSeconds"] = hidePanelReadSeconds;
            }
            // 2026-11-28 추가(참여자가 공간을 고름). experimenter(기본)이면 넣지 않는다(기존 기록과 같은 바이트)
            if (ParticipantChoosesSpace) j["environmentChoice"] = environmentChoice;
            return j;
        }

        JObject BaseJson() => new JObject
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
            // 2026-11-23 D8 추가(평정 문항). 기존 키는 그대로다.
            ["askOptionalItems"] = askOptionalItems,
            ["disabledItems"] = new JArray((disabledItems ?? new string[0]).Cast<object>().ToArray()),
        };

        /// <summary>disabledItems 가운데 문구 파일에 없는 평정 문항 키(오타 방지 — 러너가 확인 단계에서 오류로 낸다).</summary>
        public List<string> UnknownDisabledItems(PlacementTaskText text) =>
            (disabledItems ?? new string[0]).Where(k => text == null || !text.Items.Any(i => i.Key == k)).ToList();
    }
}
