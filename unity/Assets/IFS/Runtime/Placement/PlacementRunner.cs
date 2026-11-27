// 배치 실험 러너(RQ V4, 프로토타입). 확정 spec의 물체 하나(변형본 없음)를 '나' 기준 공간에 두고,
// 조건(place | view)·통제 방식(static | system_move | replay | point_select)에 따라 한 회기를 진행한다.
// 단계 흐름·기록은 PlacementSession(UnityEngine 없음)이 맡고, 이 컴포넌트는 그것을 그린다:
//   물체(SceneLoader — 장면 속성은 기존 로더 경로 그대로), 공간(PlacementSpace), 참여자 글(ParticipantTextDisplay), 입력(IPlacementInput).
// 실험자 키: 숫자 0–9 평정(문항 범위 안, 두 자리 범위는 이어 침), Backspace 직전 입력 취소, Enter 확정·다음, Esc 중단, R 정면 재설정(XR), H 눈높이 재기(G60-3, relative일 때 Check 단계).
// 선택 파일(선택, D8): 챗봇의 selection.json(ifs-selection/0.1·0.2 — PlacementSelection). 있으면 원본 spec + finalOverrides로 형상을 한 번 만들고
//   (조건 단계 동안 바뀌지 않음), sha 불일치·모르는 키·적용하지 못한 키는 시작 거부. 없으면 예전처럼 spec만.
// 참여자 입력: 설정 inputMode(auto | desktop | xr)에 따라 Check 때 고른다(PlacementInputSelection) —
//   XR 헤드셋이 켜져 있으면 XrPlacementInput(컨트롤러 광선), 없으면 DesktopPlacementInput(마우스·키보드).
// 참여자 글: PlacementTextPanel(세계 고정 판, 헤드셋 안에서 읽힘)이 있으면 그것, 없으면 ParticipantTextDisplay(예전 씬).
// 자동 시행(검증용): BeginAuto(스크립트, 설정) 뒤 Tick(dt)을 밖에서 부르면 사람 없이 끝까지 간다(시뮬레이션 시계).
// 배치 공간 후보(G52–G55, 2026-11-24): 설정 environment(neutral | space | nature)로 중립 환경의 하늘을 바꾸고(EnvironmentStyle),
//   placementAssist면 놓기 도움(연습 상자·목표 자리, 든 동안 수직선·바닥 고리, 경계 띠 밝아짐)을 그린다. 기본값에서는 아무것도 더하지 않는다.
// 멈춤 거리 반복 멈춤(G60-2, 2026-11-26): 설정 stopMode loop면 멈춤 거리 단계 동안 바닥 고리를 숨긴다(stopLoopHideRings).
// 눈높이 정규화(G60-3, 2026-11-26): 설정 eyeHeightMode relative면 Check 뒤 실험자 키 H로 눈높이 E를 재야 시작할 수 있고(데스크톱·자동 시행은
//   기준값 고정), 참여자 판의 높이와 눈 앵커를 E 기준으로 옮긴다. 카메라·리그 높이는 바꾸지 않는다.
// 헤드셋 실기는 확인하지 않았다(2026-11-23 — docs/headset-checklist.md).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using IFS.SceneSpec.Ownership;
using UnityEngine;

namespace IFS.SceneSpec.Placement
{
    public enum PlacementRunnerStage { Setup, Checked, Running, Done }

    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Placement/Placement Experiment Runner")]
    public sealed class PlacementRunner : MonoBehaviour
    {
        [Header("설정(manifest.json에 기록)")]
        [SerializeField] PlacementConfig config = new PlacementConfig();
        [Tooltip("null 슬롯 기본값(형상 로더와 같은 값)")]
        [SerializeField] SceneDefaults defaults = new SceneDefaults();

        [Header("경로")]
        [Tooltip("spec 목록 폴더. 비우면 에디터에서는 <프로젝트>/../chatbot/logs/scenes, 빌드에서는 persistentDataPath/IFS/scenes")]
        [SerializeField] string specFolder = "";
        [Tooltip("기록 루트. 비우면 persistentDataPath/IFS/sessions(저장소 밖). 그 아래 placement/P###/…")]
        [SerializeField] string recordRoot = "";
        [Tooltip("문구 파일. 비우면 StreamingAssets/IFS/placement_task.v0.json")]
        [SerializeField] string taskTextPath = "";

        [Header("모양 프리팹 (메뉴 IFS ▸ Create Shape Prefabs가 연결)")]
        [SerializeField] ShapePrefab[] shapePrefabs =
        {
            new ShapePrefab("round"), new ShapePrefab("square"), new ShapePrefab("flat"), new ShapePrefab("pointed"),
        };

        [Header("구성 요소")]
        [SerializeField] HeadPoseProvider headProvider = null;
        [SerializeField] ParticipantTextDisplay textDisplay = null;
        [Tooltip("데스크톱 참여자 입력(IPlacementInput, 기본 DesktopPlacementInput). XR이 없을 때 쓴다")]
        [SerializeField] MonoBehaviour inputComponent = null;

        [Header("헤드셋(XR)")]
        [Tooltip("XR 리그(카메라 부모, 바닥 원점·정면 재설정)")]
        [SerializeField] PlacementXrRig xrRig = null;
        [Tooltip("XR 컨트롤러 입력")]
        [SerializeField] XrPlacementInput xrInput = null;
        [Tooltip("참여자 안내 판(헤드셋 안). 비우면 ParticipantTextDisplay로 그린다")]
        [SerializeField] PlacementTextPanel panel = null;
        [Tooltip("켜면 XR 광선을 입력을 쓰는 때(조건 단계의 직접 배치·가리켜 지정)만 보인다")]
        [SerializeField] bool rayOnlyWhenUsable = true;

        [Header("참여자 글 자리('나' 기준) — 판 중심")]
        [Tooltip("정면 거리(m)")]
        [SerializeField] float textForwardM = 2.0f;
        [Tooltip("판 중심 높이(m). 기본 0.6: 눈높이 1.6에서 약 27° 아래 — 시작 자리(1.5 m, 높이 1.2)의 물체(반지름 0.3 m까지)보다 아래")]
        [SerializeField] float textHeightM = 0.6f;
        [Tooltip("SceneLoader 앵커(눈높이) — 물체 크기·모양 계산에만 쓰고 위치는 이 러너가 정한다")]
        [SerializeField] float anchorEyeHeightM = 1.6f;

        // ── 상태(실험자 화면이 읽는다) ─────────────────────────────────────
        public PlacementRunnerStage Stage { get; private set; } = PlacementRunnerStage.Setup;
        public string ParticipantNumberText { get; set; } = "";
        public string SpecPathText { get; set; } = "";
        public string SpecFolderText { get; set; }
        /// <summary>선택 파일(selection.json) 경로(선택). 절대 경로이거나 spec 목록 폴더 기준. 비우면 spec만으로 진행.</summary>
        public string SelectionPathText { get; set; } = "";
        /// <summary>확인(Check)에서 읽은 선택 파일. 없으면 null.</summary>
        public PlacementSelection Selection { get; private set; }
        /// <summary>G62: 이 세션에서 생성 형태 메시를 적용한 결과(선택 파일에 form.asset이 없으면 null).</summary>
        public IFS.SceneSpec.FormAsset.FormAssetResult FormAssetResult { get; private set; }
        /// <summary>마지막으로 시작한 세션에 실제로 적용된 덮어쓰기(키 → 그려지는 값).</summary>
        public Newtonsoft.Json.Linq.JObject AppliedOverrides { get; private set; }
        public List<string> Errors { get; } = new List<string>();
        public List<string> Warnings { get; } = new List<string>();
        public SceneSpecV2 Spec { get; private set; }
        public PlacementTaskText TaskText { get; private set; }
        public PlacementSession Session { get; private set; }
        public string LastRecordDirectory { get; private set; }
        public bool LastCompleted { get; private set; }
        public string LastAbortedAt { get; private set; }
        public bool GuiHasKeyboardFocus { get; set; }
        public PlacementConfig Config => config;
        public bool IsAuto => _auto != null;
        public string HeadSource => headProvider != null ? headProvider.Source : HeadPoseProvider.SourceDesktop;
        /// <summary>지금 쓰는 참여자 입력(Check에서 고른 것, 고르기 전이면 데스크톱).</summary>
        public IPlacementInput Input => _activeInput ?? inputComponent as IPlacementInput;
        /// <summary>Check에서 고른 참여자 입력: desktop | xr | auto(자동 시행). 고르기 전이면 null.</summary>
        public string ActiveInputSource => _activeSource;
        public PlacementXrRig XrRig => xrRig;
        public XrPlacementInput XrInput => xrInput;
        public PlacementTextPanel Panel => panel;
        /// <summary>XR 헤드셋이 켜져 있고 머리 자세가 읽힌다.</summary>
        public bool XrHeadActive => xrRig != null ? xrRig.HeadActive : HeadPoseProvider.TryReadXrHead(out _, out _);
        /// <summary>주 사용 손 컨트롤러가 보였나(Setup·Checked에서 매 프레임 갱신).</summary>
        public bool XrControllerPresent { get; private set; }
        /// <summary>마지막 정면 재설정 결과(실험자 화면).</summary>
        public string LastRecenterMessage { get; private set; }
        /// <summary>문구 파일(StreamingAssets 기준 상대 경로 또는 절대 경로). Setup에서 고른다. null이면 Inspector의 taskTextPath.</summary>
        public string TaskTextPathText { get; set; }
        /// <summary>StreamingAssets/IFS 안의 문구 파일들(Setup 목록).</summary>
        public List<string> TaskTextFiles { get; } = new List<string>();
        public SceneLoader Loader => _loader;
        public PlacementSpaceHandle Space => _space;
        public string DraftPhraseNotice => PlacementTaskText.DraftNotice(TaskText, config.requireSpecPhrases, config.placementAssist, config.IsStopLoop);
        // ── 눈높이 보정(G60-3, eyeHeightMode relative) ──────────────────────
        /// <summary>마지막 눈높이 보정 결과(Check 단계 실험자 키 H). 없으면 null. Check·설정으로 돌아가기·다음 참여자에서 지운다.</summary>
        public EyeHeightCalibration.Result EyeCalibration { get; private set; }
        /// <summary>눈높이 표본을 모으는 중(1 s).</summary>
        public bool EyeCalibrating => _eyeSampler != null;
        /// <summary>실험자 화면 한 줄(보정 상태). relative가 아니면 null.</summary>
        public string EyeHeightStatus
        {
            get
            {
                if (!config.IsEyeRelative) return null;
                if (_auto != null || !XrHeadActive) return $"눈높이: 데스크톱·자동 시행이라 기준값 {config.eyeHeightReferenceM:0.00} m 고정(desktop_fixed)";
                if (_eyeSampler != null) return $"눈높이 재는 중… {_eyeSampler.Count}/{_eyeSampler.Needed}";
                if (EyeCalibration == null) return "눈높이: 아직 재지 않음 — 참여자를 똑바로 세운 뒤 H(시작하려면 필요)";
                var i = EyeCalibration.Info;
                return EyeCalibration.Ok
                    ? $"눈높이 E = {i.MeasuredM:0.000} m (SD {i.SdM:0.000} m, pitch {i.PitchDeg:0.0}°, 표본 {i.Samples}) — 물체 높이 {config.EyeOffsetFor(i.MeasuredM):+0.000;-0.000;0.000} m"
                    : "눈높이 보정 실패: " + EyeCalibration.Reason + " — 다시 H";
            }
        }
        /// <summary>문구 판·참여자 글의 눈높이 앵커(m): relative면 이 세션의 E, 아니면 Inspector anchorEyeHeightM.</summary>
        public float PanelEyeHeightM => Session?.EyeHeightM is double e ? (float)e : anchorEyeHeightM;
        /// <summary>지금 화면에 실제로 그려진 배경 공간(EnvironmentStyle.Apply 결과). 실험자 화면이 읽는다.</summary>
        public string AppliedEnvironment { get; private set; } = PlacementConfig.EnvironmentNeutral;
        public List<SpecFileEntry> SpecFiles { get; } = new List<SpecFileEntry>();

        // ── 내부 ───────────────────────────────────────────────────────────
        PlacementAutoScript _auto;
        string _specFullPath, _specSha;
        string _selectionFullPath, _selectionSha;
        string _layoutWarning;
        PlacementTrajectory _replay;
        string _replayFullPath, _replaySha;
        GameObject _anchor;
        SceneLoader _loader;
        PlacementSpaceHandle _space;
        EnvironmentHandle _ownEnvironment;   // 씬에 IFSEnvironment가 없을 때 non-neutral 공간을 위해 만든 환경
        double _objectRadius;
        string _shownText;
        IPlacementInput _activeInput;
        string _activeSource;
        EyeHeightSampler _eyeSampler;
        float _eyeSamplerStart;
        bool _ringsHidden;

        // ── 수명 ─────────────────────────────────────────────────────────
        void Awake()
        {
            if (SpecFolderText == null) SpecFolderText = specFolder;
            RefreshSpecList();
            PreloadTaskText();
            BuildSpace();   // 시작 전에도 공간이 보이게(재생 모드)
        }

        void Update()
        {
            if (_auto != null) return;   // 자동 시행은 Tick을 밖에서 부른다
            if (Stage != PlacementRunnerStage.Running && xrInput != null)
            {
                if (XrHeadActive) { xrInput.Configure(xrRig != null ? xrRig.transform : null, config.xrHand); XrControllerPresent = xrInput.ControllerPresent; }
                else XrControllerPresent = false;
            }
            StepEyeCalibration();
            Tick(Time.unscaledDeltaTime);
            PollKeys();
        }

        // ── 눈높이 보정(G60-3) ──────────────────────────────────────────
        /// <summary>눈높이 재기 시작(Check 단계, 실험자 키 H 또는 실험자 화면 단추). relative가 아니거나 헤드셋이 없으면 아무것도 하지 않는다.
        /// 20 Hz로 eyeCalibSeconds 동안 머리 높이·pitch를 모아 EyeHeightCalibration.Evaluate로 판정한다.</summary>
        public bool BeginEyeCalibration()
        {
            if (!config.IsEyeRelative || Stage != PlacementRunnerStage.Checked || Session != null || _auto != null || !XrHeadActive) return false;
            EyeCalibration = null;
            ClearEyeRefusal();
            _eyeSampler = new EyeHeightSampler(config);
            _eyeSamplerStart = Time.unscaledTime;
            return true;
        }

        string _eyeRefusal;

        /// <summary>시작 거부로 넣은 눈높이 오류 줄을 지운다(다시 잴 때).</summary>
        void ClearEyeRefusal()
        {
            if (_eyeRefusal != null) Errors.Remove(_eyeRefusal);
            _eyeRefusal = null;
        }

        void StepEyeCalibration()
        {
            if (_eyeSampler == null) return;
            if (Stage != PlacementRunnerStage.Checked || Session != null) { _eyeSampler = null; return; }
            var h = CurrentHead();
            _eyeSampler.Add(Time.unscaledTime - _eyeSamplerStart, h.Y, EyeHeightCalibration.PitchDegFromQuaternion(h.Qx, h.Qy, h.Qz, h.Qw));
            if (!_eyeSampler.Done) return;
            EyeCalibration = FinishEyeCalibration(_eyeSampler);
            _eyeSampler = null;
        }

        /// <summary>모은 표본으로 판정한다(테스트에서 표본을 직접 넣을 때도 쓴다).</summary>
        public EyeHeightCalibration.Result FinishEyeCalibration(EyeHeightSampler sampler)
        {
            bool floor = xrRig != null && xrRig.FloorOrigin;
            var r = EyeHeightCalibration.Evaluate(config, sampler.Heights, sampler.Pitches, floor, xrRig?.TrackingOrigin);
            EyeCalibration = r;
            ClearEyeRefusal();
            Debug.Log("[IFS] 눈높이 보정: " + (r.Ok ? "통과 " : "실패 ") + (r.Info != null ? r.Info.EventDetail(config) : "") + (r.Reason != null ? " — " + r.Reason : ""), this);
            return r;
        }

        /// <summary>세션에 넘길 눈높이: relative가 아니면 null, 데스크톱·자동 시행이면 기준값 고정, XR이면 통과한 보정 결과(없으면 null + 거부 이유).</summary>
        EyeHeightInfo EyeHeightForSession(out string refusal)
        {
            refusal = null;
            if (!config.IsEyeRelative) return null;
            if (_auto != null || !XrHeadActive) return EyeHeightInfo.DesktopFixed(config.eyeHeightReferenceM);
            if (EyeCalibration == null) { refusal = "eyeHeightMode relative인데 눈높이를 재지 않았습니다 — 참여자를 똑바로 세우고 정면 재설정(R) 뒤 H로 재세요"; return null; }
            if (!EyeCalibration.Ok) { refusal = "눈높이 보정이 통과하지 못했습니다: " + EyeCalibration.Reason + " — 다시 H"; return null; }
            return EyeCalibration.Info;
        }

        void OnDestroy()
        {
            Session?.Quit("runner destroyed (play mode stopped or scene closed)");
            AfterSession();
            Cleanup();
            _space?.Dispose();
            _space = null;
            _ownEnvironment?.Dispose();
            _ownEnvironment = null;
        }

        void OnApplicationQuit()
        {
            Session?.Quit("application quit");
            AfterSession();
        }

        // ── 경로 ─────────────────────────────────────────────────────────
        public string ResolvedSpecFolder
        {
            get
            {
                string f = string.IsNullOrWhiteSpace(SpecFolderText ?? specFolder) ? null : (SpecFolderText ?? specFolder).Trim();
                if (f != null) return f;
                return Application.isEditor
                    ? Path.GetFullPath(Path.Combine(Application.dataPath, "..", "..", "chatbot", "logs", "scenes"))
                    : Path.Combine(Application.persistentDataPath, "IFS", "scenes");
            }
        }

        public string ResolvedRecordRoot => string.IsNullOrWhiteSpace(recordRoot)
            ? Path.Combine(Application.persistentDataPath, "IFS", "sessions")
            : recordRoot;

        string ResolvedTaskTextPath
        {
            get
            {
                string p = (TaskTextPathText ?? taskTextPath ?? "").Trim().Trim('"');
                return p.Length == 0
                    ? Path.Combine(Application.streamingAssetsPath, PlacementTaskText.DefaultRelativePath)
                    : (Path.IsPathRooted(p) ? p : Path.Combine(Application.streamingAssetsPath, p));
            }
        }

        /// <summary>Setup 화면에 보일 문구 파일 이름(StreamingAssets 기준).</summary>
        public string TaskTextDisplayName
        {
            get
            {
                string p = (TaskTextPathText ?? taskTextPath ?? "").Trim();
                return p.Length == 0 ? PlacementTaskText.DefaultRelativePath : p;
            }
        }

        /// <summary>Setup에서 문구 파일을 고른다(StreamingAssets 기준 상대 경로). 바로 다시 읽는다.</summary>
        public void SelectTaskText(string relativePath)
        {
            if (Session != null) return;
            TaskTextPathText = relativePath;
            PreloadTaskText();
        }

        /// <summary>replay 원본 경로: 절대 경로면 그대로, 아니면 기록 루트 기준.</summary>
        string ResolvedReplayPath
        {
            get
            {
                string p = (config.replayPath ?? "").Trim().Trim('"');
                if (p.Length == 0) return null;
                return Path.IsPathRooted(p) ? p : Path.GetFullPath(Path.Combine(ResolvedRecordRoot, p));
            }
        }

        public void RefreshSpecList()
        {
            SpecFiles.Clear();
            string dir = ResolvedSpecFolder;
            if (!Directory.Exists(dir)) return;
            foreach (var p in Directory.GetFiles(dir, "*.json").OrderBy(p => Path.GetFileName(p), StringComparer.Ordinal))
                SpecFiles.Add(new SpecFileEntry { Path = p, Name = Path.GetFileName(p) });
        }

        void PreloadTaskText()
        {
            TaskTextFiles.Clear();
            try { TaskTextFiles.AddRange(PlacementTaskText.ListTaskTextFiles(Application.streamingAssetsPath)); }
            catch (Exception) { /* 목록은 보조 기능 */ }
            try { TaskText = File.Exists(ResolvedTaskTextPath) ? PlacementTaskText.Load(ResolvedTaskTextPath) : null; }
            catch (Exception) { TaskText = null; }
        }

        // ── 설정(에디터 메뉴·자동 시행) ───────────────────────────────────
        public void Configure(HeadPoseProvider head, ParticipantTextDisplay text, MonoBehaviour input, IEnumerable<ShapePrefab> shapes)
        {
            headProvider = head;
            textDisplay = text;
            inputComponent = input;
            if (shapes != null) shapePrefabs = shapes.Where(s => s != null).Select(s => new ShapePrefab(s.shape, s.prefab)).ToArray();
        }

        /// <summary>헤드셋 구성 요소(리그·XR 입력·참여자 판)를 연결한다.</summary>
        public void ConfigureXr(PlacementXrRig rig, XrPlacementInput xr, PlacementTextPanel participantPanel)
        {
            xrRig = rig;
            xrInput = xr;
            panel = participantPanel;
        }

        public void SetRecordRoot(string root) => recordRoot = root ?? "";

        /// <summary>설정을 통째로 바꾼다(Setup에서만).</summary>
        public void SetConfig(PlacementConfig cfg)
        {
            if (Session != null || cfg == null) return;
            config = cfg.Clone();
        }

        /// <summary>Setup에서 공간 설정(environment·placementAssist)을 바꾼 뒤 바로 다시 그린다(세션 중에는 무시).</summary>
        public void RefreshSpace()
        {
            if (Session != null) return;
            BuildSpace();
        }

        /// <summary>자동 시행: 시뮬레이션 시계, 정해진 입력(합성), 정해진 머리 경로.</summary>
        public void BeginAuto(PlacementAutoScript script, PlacementConfig cfg)
        {
            _auto = script ?? new PlacementAutoScript();
            if (cfg != null) config = cfg.Clone();
        }

        // ── Setup → Checked ─────────────────────────────────────────────
        public bool Check()
        {
            if (Session != null) return false;
            Errors.Clear();
            Warnings.Clear();
            Spec = null;
            Selection = null;
            _replay = null;
            _layoutWarning = null;
            EyeCalibration = null;   // 눈높이는 Check 뒤에 잰다(G60-3)
            _eyeSampler = null;
            _eyeRefusal = null;
            if (!int.TryParse((ParticipantNumberText ?? "").Trim(), out int number) || number < 1)
                Errors.Add("참여자 번호는 1 이상의 정수여야 합니다");
            string path = (SpecPathText ?? "").Trim().Trim('"');
            if (path.Length == 0) Errors.Add("spec 파일을 고르세요");
            else if (!Path.IsPathRooted(path)) path = Path.Combine(ResolvedSpecFolder, path);
            Errors.AddRange(config.Validate().Select(e => "설정 오류: " + e));
            if (Errors.Count > 0) { Stage = PlacementRunnerStage.Setup; return false; }
            if (!File.Exists(path)) { Errors.Add("spec 파일이 없습니다: " + Path.GetFileName(path)); return false; }
            try
            {
                var bytes = File.ReadAllBytes(path);
                _specSha = OwnershipManifest.Sha256Hex(bytes);
                Spec = SceneSpecJson.Parse(Encoding.UTF8.GetString(bytes));
            }
            catch (Exception e)
            {
                Errors.Add("spec을 읽지 못했습니다: " + e.Message);
                return false;
            }
            _specFullPath = path;
            foreach (var problem in SceneSpecJson.Validate(Spec)) Warnings.Add("spec 형식 경고: " + problem);
            _layoutWarning = PlacementManifest.LayoutIgnoredWarning(Spec.Layout?.Distance, Spec.Layout?.VerticalOffset, config);
            if (_layoutWarning != null) Warnings.Add(_layoutWarning);   // events.csv에도 warning(detail layout_ignored…)으로 남는다
            try { TaskText = PlacementTaskText.Load(ResolvedTaskTextPath); }
            catch (Exception e) { TaskText = null; Errors.Add("문구 파일을 읽지 못했습니다(" + PlacementTaskText.DefaultRelativePath + "): " + e.Message); }
            if (DraftPhraseNotice != null) Warnings.Add(DraftPhraseNotice);   // events.csv에도 warning으로 남는다
            if (TaskText != null)
                foreach (var k in config.UnknownDisabledItems(TaskText))
                    Errors.Add($"disabledItems의 {k}: 문구 파일({TaskText.FileName})에 그 평정 문항이 없습니다");
            if (TaskText != null && config.placementAssist && TaskText.AssistKeysMissing().Count > 0)
                Errors.Add($"놓기 도움을 켰는데 문구 파일({TaskText.FileName})에 {string.Join(", ", TaskText.AssistKeysMissing())} 문구가 없습니다(문구 파일 0.3 이상)");
            if (TaskText != null && config.IsStopLoop && TaskText.LoopKeysMissing().Count > 0)
                Errors.Add($"멈춤 거리 반복 멈춤(stopMode loop)을 켰는데 문구 파일({TaskText.FileName})에 {string.Join(", ", TaskText.LoopKeysMissing())} 문구가 없습니다(문구 파일 0.6 이상)");
            if (!BuildSpace())
                Errors.Add($"공간 {config.environment}을(를) 그리지 못했습니다(셰이더·사진 확인 — 콘솔). 기록이 실제 화면과 달라지므로 시작하지 않습니다");
            CheckSelection();
            string refusal = PlacementTaskText.SpecPhraseRefusal(TaskText, config.requireSpecPhrases, config.placementAssist, config.IsStopLoop);
            if (refusal != null) Errors.Add(refusal);
            if (config.EffectiveControlMode == PlacementConfig.ModeReplay) CheckReplay();
            if (config.IsEyeRelative && config.EffectiveControlMode == PlacementConfig.ModeReplay)
                Warnings.Add("eyeHeightMode relative인데 controlMode replay입니다 — 재생 궤적의 높이는 원본 기록의 절대 높이 그대로라 눈높이 기준으로 옮기지 않습니다");
            Font font = null;
            if (textDisplay != null) { font = textDisplay.EnsureFont(); if (textDisplay.FontWarning != null) Warnings.Add(textDisplay.FontWarning); }
            if (panel != null) panel.SetFont(font);
            SelectInput();
            Stage = PlacementRunnerStage.Checked;
            return Errors.Count == 0;
        }

        /// <summary>참여자 입력을 고른다(설정 inputMode, XR 헤드셋·컨트롤러 유무). 자동 시행은 합성 입력("auto").</summary>
        void SelectInput()
        {
            if (_auto != null) { _activeInput = null; _activeSource = "auto"; return; }
            bool head = XrHeadActive;
            bool controller = false;
            if (xrInput != null)
            {
                xrInput.Configure(xrRig != null ? xrRig.transform : null, config.xrHand);
                if (head) controller = xrInput.ControllerPresent;
            }
            XrControllerPresent = controller;
            var r = PlacementInputSelection.Choose(config.inputMode, head, controller, config.xrHand);
            if (r.Error != null) Errors.Add(r.Error);
            if (r.Warning != null) Warnings.Add(r.Warning);
            _activeSource = r.Source;
            _activeInput = null;
            if (r.Source == XrPlacementInput.Source)
            {
                if (xrInput == null) Errors.Add("XR 입력 구성 요소(XrPlacementInput)가 씬에 없습니다 — 메뉴 IFS ▸ Experiment ▸ Create Placement Experiment Scene으로 씬을 다시 만드세요");
                else _activeInput = xrInput;
                if (xrRig != null && !xrRig.HeadActiveOverride.HasValue && !xrRig.FloorOrigin)
                    Warnings.Add("XR 추적 원점이 바닥(Floor)이 아닙니다(" + xrRig.TrackingOrigin + ") — 눈높이·바닥 높이가 맞지 않을 수 있음");
            }
            else _activeInput = inputComponent as IPlacementInput;
            if (config.participantRatesWithController && r.Source != XrPlacementInput.Source)
                Warnings.Add("participantRatesWithController가 켜져 있지만 XR 입력이 아니어서 평정은 실험자 키보드로만 받습니다");
        }

        /// <summary>선택 파일 경로: 비면 null, 절대 경로면 그대로, 아니면 spec 목록 폴더 기준.</summary>
        string ResolvedSelectionPath
        {
            get
            {
                string p = (SelectionPathText ?? "").Trim().Trim('"');
                if (p.Length == 0) return null;
                return Path.IsPathRooted(p) ? p : Path.GetFullPath(Path.Combine(ResolvedSpecFolder, p));
            }
        }

        /// <summary>선택 파일(있으면): 형식·sha·덮어쓰기 키 확인. 오류는 Errors(시작 거부), 형식 버전 경고는 Warnings(events.csv warning).</summary>
        void CheckSelection()
        {
            _selectionFullPath = ResolvedSelectionPath;
            _selectionSha = null;
            if (_selectionFullPath == null) return;   // 선택 파일 없음: 예전처럼 spec만
            if (!File.Exists(_selectionFullPath)) { Errors.Add("선택 파일이 없습니다: " + Path.GetFileName(_selectionFullPath)); return; }
            var sel = PlacementSelection.Load(_selectionFullPath, out var errors);
            if (sel == null)
            {
                foreach (var e in errors) Errors.Add("선택 파일 " + Path.GetFileName(_selectionFullPath) + ": " + e);
                return;
            }
            string mismatch = sel.SpecMismatch(_specSha);
            if (mismatch != null) Errors.Add(mismatch);
            foreach (var e in sel.CheckApplicable(Spec, defaults)) Errors.Add("선택 파일: " + e);
            foreach (var w in sel.Warnings) Warnings.Add(w);
            Selection = sel;
            _selectionSha = sel.Sha256;
            // G62: 고른 생성 형태 메시 — GLB가 없거나 sha256이 다르면 시작은 하되 절차 메시로 돌아간다(미리 알림, 기록은 시작 때)
            if (sel.FormAsset != null)
            {
                string why = FormAssetPrecheck(sel.FormAsset, _selectionFullPath);
                if (why != null) Warnings.Add($"생성 형태 메시 {sel.FormAsset.AssetId}: {why} — 절차 메시로 표시합니다(G62)");
            }
        }

        /// <summary>G62: 생성 형태 GLB 파일 확인(있는지·sha256). 문제가 없으면 null, 있으면 이유.</summary>
        static string FormAssetPrecheck(IFS.SceneSpec.FormAsset.FormAssetRef r, string selectionPath)
        {
            string path = r.ResolveGlbPath(selectionPath);
            if (path == null) return IFS.SceneSpec.FormAsset.FormAssetResult.GlbNull;
            if (!File.Exists(path)) return IFS.SceneSpec.FormAsset.FormAssetResult.GlbMissing;
            try { return OwnershipManifest.Sha256OfFile(path) == r.GlbSha256 ? null : IFS.SceneSpec.FormAsset.FormAssetResult.GlbSha; }
            catch (Exception e) { return IFS.SceneSpec.FormAsset.FormAssetResult.GlbMissing + ": " + e.Message; }
        }

        /// <summary>G62: 선택 파일의 생성 형태 메시를 로드한 형상에 적용한다. GLB가 없거나·sha256이 다르거나·읽지 못하면
        /// 절차 메시를 그대로 두고 그 이유를 결과에 담는다(시작은 막지 않음 — manifest formAsset·events form_asset·경고로 남김).</summary>
        IFS.SceneSpec.FormAsset.FormAssetResult ApplyFormAsset(IFS.SceneSpec.FormAsset.FormAssetRef r)
        {
            string path = r.ResolveGlbPath(_selectionFullPath);
            if (path == null) return _loader.ApplyFormAssetFallback(r, IFS.SceneSpec.FormAsset.FormAssetResult.GlbNull, "선택 파일 form.asset.glb가 null");
            byte[] bytes;
            try { bytes = File.ReadAllBytes(path); }
            catch (Exception e) { return _loader.ApplyFormAssetFallback(r, IFS.SceneSpec.FormAsset.FormAssetResult.GlbMissing, e.Message); }
            string sha = OwnershipManifest.Sha256Hex(bytes);
            if (sha != r.GlbSha256)
            {
                var bad = _loader.ApplyFormAssetFallback(r, IFS.SceneSpec.FormAsset.FormAssetResult.GlbSha, null);
                bad.GlbSha256Actual = sha;
                return bad;
            }
            var mesh = IFS.SceneSpec.FormAsset.GlbMeshReader.Read(bytes, out string err);
            if (mesh == null)
            {
                var bad = _loader.ApplyFormAssetFallback(r, IFS.SceneSpec.FormAsset.FormAssetResult.GlbParse, err);
                bad.GlbSha256Actual = sha;
                return bad;
            }
            var res = _loader.ApplyFormAsset(r, mesh);
            res.GlbSha256Actual = sha;
            return res;
        }

        void CheckReplay()
        {
            _replayFullPath = ResolvedReplayPath;
            if (_replayFullPath == null || !File.Exists(_replayFullPath))
            {
                Errors.Add("재생 원본 trajectory.json이 없습니다: " + (config.replayPath ?? ""));
                return;
            }
            try
            {
                var bytes = File.ReadAllBytes(_replayFullPath);
                _replaySha = OwnershipManifest.Sha256Hex(bytes);
                _replay = PlacementTrajectory.Parse(Encoding.UTF8.GetString(bytes));
            }
            catch (Exception e)
            {
                Errors.Add("재생 원본을 읽지 못했습니다: " + e.Message);
                _replay = null;
                return;
            }
            var start = PlacementGeometry.FromPolar(config.startDistanceM, 0, config.startHeightM);
            double off = PVec3.Distance(start, _replay.Samples[0].Position);
            if (off > 0.01)
                Warnings.Add($"재생 원본의 시작 위치가 설정 시작 위치와 {off:0.###} m 다릅니다(제시 단계와 조건 단계 사이에 물체가 옮겨 보임)");
            if (_replay.DurationMs < config.conditionSeconds * 1000 - 1)
                Warnings.Add($"재생 원본 길이 {_replay.DurationMs} ms < 조건 단계 {config.conditionSeconds} s — 끝난 뒤에는 마지막 자리에 머문다");
            if (Math.Abs(_replay.SampleHz - config.headSampleHz) > 1e-6)
                Warnings.Add($"재생 원본 sampleHz {_replay.SampleHz} ≠ headSampleHz {config.headSampleHz}");
        }

        public void BackToSetup()
        {
            if (Session != null) return;
            EyeCalibration = null;
            _eyeSampler = null;
            _eyeRefusal = null;
            Stage = PlacementRunnerStage.Setup;
            Errors.Clear();
            Warnings.Clear();
            RefreshSpecList();
            PreloadTaskText();
        }

        // ── 시작 ─────────────────────────────────────────────────────────
        public bool StartSession()
        {
            if (Stage != PlacementRunnerStage.Checked || Session != null) return false;
            if (Spec == null || TaskText == null || Errors.Count > 0)
            {
                if (!Errors.Contains("확인 오류가 있어 시작할 수 없습니다")) Errors.Add("확인 오류가 있어 시작할 수 없습니다");
                return false;
            }
            string sha;
            try { sha = OwnershipManifest.Sha256OfFile(_specFullPath); }
            catch (Exception e) { Errors.Add("spec 파일을 다시 읽지 못했습니다: " + e.Message); return false; }
            if (sha != _specSha) { Errors.Add("확인한 뒤 spec 파일이 바뀌었습니다 — 다시 확인하세요"); return false; }
            if (Selection != null)
            {
                string selSha;
                try { selSha = OwnershipManifest.Sha256OfFile(_selectionFullPath); }
                catch (Exception e) { Errors.Add("선택 파일을 다시 읽지 못했습니다: " + e.Message); return false; }
                if (selSha != _selectionSha) { Errors.Add("확인한 뒤 선택 파일이 바뀌었습니다 — 다시 확인하세요"); return false; }
            }
            var eyeHeight = EyeHeightForSession(out string eyeRefusal);   // G60-3: relative면 보정(또는 데스크톱 고정값)이 있어야 시작
            if (eyeRefusal != null)
            {
                ClearEyeRefusal();
                _eyeRefusal = eyeRefusal;
                Errors.Add(eyeRefusal);   // 실험자 화면 오류 줄. 다시 재면(H) 지운다
                return false;
            }

            Cleanup();
            if (!BuildSpace())
            {
                Errors.Add($"공간 {config.environment}을(를) 그리지 못했습니다(콘솔 확인)");
                return false;
            }
            _anchor = new GameObject("Placement Anchor ('나' 눈높이)");
            _anchor.transform.SetPositionAndRotation(new Vector3(0f, anchorEyeHeightM, 0f), Quaternion.identity);
            var go = new GameObject("Placement Object");
            _loader = go.AddComponent<SceneLoader>();
            _loader.ConfigureForRunner(_anchor.transform, defaults);
            _loader.ConfigureShapePrefabs(shapePrefabs);
            // 원본 spec + 선택 파일의 덮어쓰기를 형상을 만들 때 한 번만 얹는다(조건 단계 동안 바뀌지 않음). 덮어쓰기가 없으면 예전과 같은 Load(path, null)
            var overrides = Selection != null && Selection.Overrides != null && !Selection.Overrides.IsEmpty ? Selection.Overrides : null;
            if (!_loader.Load(_specFullPath, overrides))
            {
                Errors.Add("물체를 로드하지 못했습니다(콘솔 확인)");
                Cleanup();
                return false;
            }
            if (_loader.InitialParams.InferredUsed.Count > 0)
            {
                Errors.Add("_inferred를 썼습니다(실행 거부)");
                Cleanup();
                return false;
            }

            AppliedOverrides = PlacementSelection.AppliedOverrides(overrides, _loader.CurrentParams, _loader.Shape?.Model, out var notApplied);
            if (notApplied.Count > 0)
            {
                foreach (var n in notApplied) Errors.Add("선택 파일 덮어쓰기를 적용하지 못했습니다(시작 거부): " + n);
                Cleanup();
                return false;
            }

            // G62: 고른 생성 형태 메시(선택 파일 0.3 form.asset)가 있으면 절차 모형의 메시를 바꾼다(크기·재질은 절차 모형 규칙)
            FormAssetResult = null;
            if (Selection?.FormAsset != null)
            {
                FormAssetResult = ApplyFormAsset(Selection.FormAsset);
                if (!FormAssetResult.Applied)
                    Warnings.Add($"생성 형태 메시 {Selection.FormAsset.AssetId}를 쓰지 못해 절차 메시로 표시합니다({FormAssetResult.FallbackReason})");
            }

            double objectRadius = ObjectRadius();   // 물체 렌더 경계(AABB 가장 큰 반폭). 없으면 0 → manifest null
            _objectRadius = objectRadius;
            if (_auto != null && headProvider != null) headProvider.BeginScripted();
            else if (headProvider != null) headProvider.Step(0f);
            string sessionId = Spec.Meta.SessionId ?? Path.GetFileNameWithoutExtension(_specFullPath);
            var info = new PlacementSessionInfo
            {
                ParticipantNumber = int.Parse(ParticipantNumberText.Trim()),
                SessionId = sessionId,
                SpecFile = Path.GetFileName(_specFullPath),
                SpecSha256 = _specSha,
                StartedUtc = DateTime.UtcNow,
                HeadSource = HeadSource,
                InputSource = _auto != null ? "auto" : (_activeSource ?? Input?.SourceName ?? DesktopPlacementInput.Source),
                UnityVersion = Application.unityVersion,
                AutoMode = _auto != null,
                TaskTextFile = TaskText.FileName,
                TaskTextVersion = TaskText.Version,
                TaskTextDraftKeys = TaskText.DraftKeysFor(config).ToArray(),   // 이 세션이 보일 수 있는 draft 문구만(G53·G60-2)
                ReplayFile = _replay != null ? Path.GetFileName(_replayFullPath) : null,
                ReplaySha256 = _replay != null ? _replaySha : null,
                ReplaySourceSessionId = _replay?.SourceSessionId,
                ObjectBoundingRadiusM = objectRadius > 0 ? objectRadius : (double?)null,
                LayoutIgnored = _layoutWarning != null,
                Selection = Selection,
                AppliedOverrides = AppliedOverrides,
                FormAsset = FormAssetResult,   // G62: 선택 파일에 form.asset이 있을 때만(없으면 manifest에 키 없음)
                EyeHeight = eyeHeight,   // G60-3: relative일 때만(아니면 null)
            };
            try
            {
                Session = new PlacementSession(config, TaskText, info, ResolvedRecordRoot, _replay, Warnings);
            }
            catch (Exception e)
            {
                Errors.Add("세션을 시작하지 못했습니다: " + e.Message);
                Session = null;
                Cleanup();
                return false;
            }
            Session.GrabRadiusM = Math.Max(config.grabRadiusMinM, objectRadius);
            ApplyUiOptions();   // G63: 헤드셋 UI 플래그(기본 꺼짐이면 판은 Inspector 값 그대로)
            if (Selection != null)   // events.csv에 선택 파일 한 줄(경고가 아님 — manifest selection·appliedOverrides가 정본)
                Session.Note("selection", $"file={Clean(Selection.FileName)};none={(Selection.None ? 1 : 0)};candidate={Clean(Selection.SelectedCandidateId)};" +
                                          $"skipped={(Selection.Skipped ? 1 : 0)};colorChanged={(Selection.ColorChanged.HasValue ? (Selection.ColorChanged.Value ? "1" : "0") : "")};" +
                                          $"applied={AppliedOverrides?.Count ?? 0}");
            if (FormAssetResult != null) Session.Note("form_asset", FormAssetResult.EventDetail());
            if (_auto == null && XrHeadActive)
                Session.Note("xr_status", $"device={Clean(PlacementXrRig.LoadedDeviceName)};head={Clean(PlacementXrRig.HeadDeviceName)};" +
                                          $"controller={Clean(xrInput?.DeviceName)};hand={config.xrHand};trackingOrigin={Clean(xrRig?.TrackingOrigin)}");
            LastRecordDirectory = Session.RecordDirectory;
            LastCompleted = false;
            LastAbortedAt = null;
            _shownText = null;
            Stage = PlacementRunnerStage.Running;
            ApplyVisuals();
            return true;
        }

        /// <summary>G63: 설정의 헤드셋 UI 플래그를 판에 적용하고, 평정 지시문 한 쪽의 최대 줄 수를 판의 실제 자리로 정한다.
        /// 두 조건이 같은 판·같은 규칙을 쓴다(조건을 보지 않는다).</summary>
        void ApplyUiOptions()
        {
            if (panel == null) return;
            panel.ApplyUiOptions(config.uiComfortWrap, config.uiDarkPanel, config.uiNarrowScale);
            if (config.uiComfortWrap && Session != null)
            {
                float eyeOffset = (float)Session.EyeOffsetM;
                Session.InstructionPageMaxLines = panel.MaxBodyLinesWithin(new Vector3(0f, textHeightM + eyeOffset, textForwardM), new Vector3(0f, PanelEyeHeightM, 0f));
            }
        }

        /// <summary>events.csv 상세(key=value;…)에 넣을 값: 비면 "-", 구분자(;·=·줄바꿈)는 공백으로.</summary>
        static string Clean(string s) =>
            string.IsNullOrWhiteSpace(s) ? "-" : s.Replace(';', ' ').Replace('=', ' ').Replace('\n', ' ').Replace('\r', ' ').Trim();

        /// <summary>물체 렌더러 경계 상자(세계 AABB)의 가장 큰 반폭(m). 불러온 직후(움직임 적용 전) 값이다.</summary>
        double ObjectRadius()
        {
            if (_loader == null || _loader.Root == null) return 0;
            var rs = _loader.Root.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return 0;
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return Math.Max(b.extents.x, Math.Max(b.extents.y, b.extents.z));
        }

        /// <summary>배치 공간(원형 바닥 등)을 다시 만들고 배경 공간(environment)을 맞춘다. 배경 공간을 그리지 못하면 false.</summary>
        bool BuildSpace()
        {
            _space?.Dispose();
            _space = PlacementSpace.Build(config, transform);
            _ringsHidden = false;
            PlacementSpace.HideEnvironmentFloor();
            return ApplyEnvironment();
        }

        /// <summary>씬의 중립 환경(IFSEnvironment)에 배경 공간을 얹는다(G52). neutral이고 얹은 적이 없으면 아무것도 하지 않는다.
        /// 씬에 환경이 없는데 space·nature면 러너가 환경을 하나 만든다.</summary>
        bool ApplyEnvironment()
        {
            string style = config.environment ?? PlacementConfig.EnvironmentNeutral;
            bool ok = true, any = false;
            foreach (var env in FindObjectsByType<IFSEnvironment>(FindObjectsSortMode.None))
            {
                if (env == null || env.Handle == null) continue;
                any = true;
                ok &= EnvironmentStyle.Apply(env.Handle, style);
            }
            if (!any && style != PlacementConfig.EnvironmentNeutral)
            {
                if (_ownEnvironment == null || _ownEnvironment.Root == null) _ownEnvironment = EnvironmentBuilder.Build(new EnvironmentSettings(), transform);
                ok &= EnvironmentStyle.Apply(_ownEnvironment, style);
                if (_ownEnvironment.Floor != null) _ownEnvironment.Floor.enabled = false;
            }
            else if (_ownEnvironment != null)
            {
                if (any || style == PlacementConfig.EnvironmentNeutral) { _ownEnvironment.Dispose(); _ownEnvironment = null; }
            }
            AppliedEnvironment = ok ? style : PlacementConfig.EnvironmentNeutral;
            return ok;
        }

        void Cleanup()
        {
            if (_loader != null)
            {
                _loader.Unload();
                DestroySafe(_loader.gameObject);
            }
            _loader = null;
            DestroySafe(_anchor);
            _anchor = null;
        }

        static void DestroySafe(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        // ── 한 프레임 ────────────────────────────────────────────────────
        HeadPose CurrentHead()
        {
            if (headProvider == null) return _auto != null && Session != null ? PlacementAutoScript.ScriptedHead(Session.Now) : HeadPose.At(0, 1.6, 0);
            var p = headProvider.Position;
            var q = headProvider.Rotation;
            return new HeadPose { X = p.x, Y = p.y, Z = p.z, Qx = q.x, Qy = q.y, Qz = q.z, Qw = q.w };
        }

        /// <summary>한 프레임: 머리 자세 → 참여자 입력 → 세션 진행·기록 → 그리기.</summary>
        public void Tick(double dt)
        {
            if (Session == null) return;
            if (headProvider != null)
            {
                if (headProvider.Scripted) headProvider.ScriptedPose(Session.Now + dt);
                headProvider.DesktopInputEnabled = !GuiHasKeyboardFocus;
            }
            var inp = Input;
            if (inp != null) inp.Enabled = !GuiHasKeyboardFocus;
            Session.SetHeadSource(HeadSource);
            var head = CurrentHead();
            if (_auto != null)
            {
                Session.Tick(dt, _auto.Participant(Session, dt), head);
                _auto.Experimenter(Session);
            }
            else Session.Tick(dt, inp != null ? inp.Read() : new PlacementInputFrame(), head);
            SendHaptics();
            ApplyVisuals();
            AfterSession();
        }

        /// <summary>G63 (4): 세션이 쌓은 햅틱 펄스를 XR 컨트롤러로 보낸다(XR 입력을 쓰는 중일 때만 — events.csv haptic은 세션이 이미 남겼다).
        /// 마지막으로 보낸 수·보내지 못한 수는 점검용.</summary>
        void SendHaptics()
        {
            if (Session == null) return;
            var pulses = Session.TakeHaptics();
            if (pulses.Count == 0) return;
            bool xrActive = _auto == null && xrInput != null && ReferenceEquals(_activeInput, xrInput);
            foreach (var p in pulses)
            {
                if (xrActive && xrInput.SendHaptic(p)) HapticsSent++;
                else HapticsNotSent++;
            }
        }

        /// <summary>G63 (4): 이 러너가 컨트롤러로 보낸 햅틱 펄스 수 · 보내지 못한 수(데스크톱·자동 시행·장치 없음). 점검용.</summary>
        public int HapticsSent { get; private set; }
        public int HapticsNotSent { get; private set; }

        void AfterSession()
        {
            if (Session == null || !Session.Finished) return;
            LastRecordDirectory = Session.RecordDirectory;
            LastCompleted = Session.Completed;
            LastAbortedAt = Session.AbortedAt;
            Stage = PlacementRunnerStage.Done;
        }

        void ApplyVisuals()
        {
            if (Session == null) return;
            if (_loader != null && _loader.Root != null)
            {
                var root = _loader.Root;
                var pos = PlacementSpace.ToUnity(Session.ObjectPosition);
                var look = new Vector3(-pos.x, 0f, -pos.z);   // '나' 쪽을 본다(SpecMotion의 다가오기 방향이 참여자 쪽이 되도록)
                root.transform.SetPositionAndRotation(pos, look.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(look.normalized, Vector3.up) : Quaternion.identity);
                if (root.activeSelf != Session.ObjectVisible) root.SetActive(Session.ObjectVisible);
            }
            // G60-3: relative면 판 높이와 눈 앵커를 E 기준으로 옮긴다(판과 눈의 기하가 사람마다 같게). none이면 예전 그대로
            float eyeOffset = (float)Session.EyeOffsetM;
            var textAt = new Vector3(0f, textHeightM + eyeOffset, textForwardM);
            var eye = new Vector3(0f, PanelEyeHeightM, 0f);
            if (panel != null)
            {
                // 헤드셋 안 판: 평정 문항이면 문항 + 1–7 기준점(참여자가 고르는 중인 값 강조), 아니면 안내 글
                var item = Session.CurrentItem;
                if (Session.PanelHidden) panel.Hide();   // G63 (7): 조건·멈춤 거리 단계에서 읽을 시간 뒤 숨김(hidePanelInDistancePhases)
                else if (item != null) panel.ShowItem(item, Session.RatingCursor, textAt, eye, Session.RatingConfirmFlash);
                else if (Session.ParticipantText == null) panel.Hide();
                else panel.ShowText(Session.ParticipantText, textAt, eye);
            }
            else if (textDisplay != null && (Session.PanelHidden ? null : Session.ParticipantText) != _shownText)
            {
                _shownText = Session.PanelHidden ? null : Session.ParticipantText;
                if (_shownText == null) textDisplay.Hide();
                else textDisplay.Show(_shownText, textAt, eye);
            }
            ApplyXrRay();
            // G60-2: 반복 멈춤에서 stopLoopHideRings면 멈춤 거리 단계 동안 바닥 거리 고리를 숨긴다
            SetRingsHidden(!Session.Finished && Session.Phase == PlacementPhase.StopDistance && Session.Config.IsStopLoop && Session.Config.stopLoopHideRings);
            if (_space != null && Session.Config.placementAssist) ApplyAssistVisuals();
            if (_space != null)
            {
                SetMarker(_space.PointerMarker, Session.Phase == PlacementPhase.Condition ? Session.PointerHit : null);
                var target = Session.MoveTarget;
                SetMarker(_space.TargetMarker, Session.Phase == PlacementPhase.Condition && Session.Config.controlMode == PlacementConfig.ModePointSelect && target.HasValue
                    ? new PVec3(target.Value.X, 0, target.Value.Z) : (PVec3?)null);
            }
        }

        /// <summary>놓기 도움(G53): 연습 상자·목표 자리, 든 물체(연습 상자 또는 본 물체)의 수직선·바닥 고리, 경계 띠 밝기.</summary>
        void ApplyAssistVisuals()
        {
            var s = Session;
            bool practice = s.PracticeActive && !s.Finished;
            PlacementSpace.SetPractice(_space, practice, s.PracticePosition, s.PracticeTarget);
            bool held = practice ? s.PracticeHeld : (!s.Finished && s.Phase == PlacementPhase.Condition && s.Held);
            var at = practice ? s.PracticePosition : s.ObjectPosition;
            double ring = practice ? s.Config.practiceCubeSizeM * 0.6 : PlacementAssistVisuals.ContactRingRadius(_objectRadius);
            PlacementSpace.SetAssist(_space, held, at, ring, s.Config.floorRadiusM);
        }

        /// <summary>XR 광선: XR 입력을 쓰는 중이고 (rayOnlyWhenUsable이면) 광선이 쓰이는 단계에서만 보인다.</summary>
        void ApplyXrRay()
        {
            if (xrInput == null) return;
            bool xrActive = _auto == null && ReferenceEquals(_activeInput, xrInput);
            var s = Session;
            bool usable = s != null && !s.Finished && ((s.Phase == PlacementPhase.Condition
                          && (s.Config.IsPlace || s.Config.controlMode == PlacementConfig.ModePointSelect)) || s.Phase == PlacementPhase.Practice);
            bool show = xrActive && s != null && !s.Finished && (usable || !rayOnlyWhenUsable);
            double end = 0;
            var state = XrRayState.Idle;
            if (show)
            {
                var smp = xrInput.LastSample;
                bool practice = s.Phase == PlacementPhase.Practice;
                end = practice
                    ? XrRayVisual.EndDistance(smp.RayOrigin, smp.RayDirection, s.PracticeHeld, s.PracticePosition, true, s.PracticeGrabRadiusM, xrInput.RayMaxLengthM)
                    : XrRayVisual.EndDistance(smp.RayOrigin, smp.RayDirection, s.Held, s.ObjectPosition, s.ObjectVisible, s.GrabRadiusM, xrInput.RayMaxLengthM);
                // G63 (3): 겨눔·잡음 상태(uiRayHover). 가리켜 지정은 물체를 잡지 않으므로 늘 기본 상태
                bool grabbable = practice || (s.Phase == PlacementPhase.Condition && s.Config.IsPlace);
                if (grabbable)
                    state = practice
                        ? XrRayStyle.State(s.Config.uiRayHover, smp.RayOrigin, smp.RayDirection, s.PracticeHeld, s.PracticePosition, true, s.PracticeGrabRadiusM)
                        : XrRayStyle.State(s.Config.uiRayHover, smp.RayOrigin, smp.RayDirection, s.Held, s.ObjectPosition, s.ObjectVisible, s.GrabRadiusM);
            }
            xrInput.ShowRay(show, end, state);
        }

        /// <summary>바닥 거리 고리를 숨기거나 다시 보인다(showRings로 만든 고리만, 바뀔 때만 건드림).</summary>
        void SetRingsHidden(bool hidden)
        {
            if (_space == null || hidden == _ringsHidden) return;
            _ringsHidden = hidden;
            foreach (var r in _space.Rings)
                if (r != null) r.SetActive(!hidden);
        }

        /// <summary>바닥 거리 고리가 지금 숨겨져 있다(G60-2 stopLoopHideRings).</summary>
        public bool RingsHidden => _ringsHidden;

        static void SetMarker(GameObject marker, PVec3? at)
        {
            if (marker == null) return;
            if (at.HasValue)
            {
                var p = PlacementSpace.ToUnity(at.Value);
                marker.transform.localPosition = new Vector3(p.x, 0.004f, p.z);
                if (!marker.activeSelf) marker.SetActive(true);
            }
            else if (marker.activeSelf) marker.SetActive(false);
        }

        // ── 실험자 키 ────────────────────────────────────────────────────
        void PollKeys()
        {
            if (GuiHasKeyboardFocus && Stage != PlacementRunnerStage.Running) return;
            if (UnityEngine.Input.GetKeyDown(KeyCode.Escape)) PressAbort();
            for (int d = 0; d <= 9; d++)   // 0은 0을 포함하는 범위(예: 0–10)와 두 자리 입력(10)에 쓴다
                if (UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha0 + d)) || UnityEngine.Input.GetKeyDown((KeyCode)((int)KeyCode.Keypad0 + d)))
                    Session?.PressDigit(d);
            if (UnityEngine.Input.GetKeyDown(KeyCode.Backspace)) Session?.PressBackspace();
            if (UnityEngine.Input.GetKeyDown(KeyCode.Return) || UnityEngine.Input.GetKeyDown(KeyCode.KeypadEnter)) PressConfirm();
            if (UnityEngine.Input.GetKeyDown(KeyCode.R)) Recenter();
            if (UnityEngine.Input.GetKeyDown(KeyCode.H)) BeginEyeCalibration();   // G60-3: Check 단계에서 눈높이 재기(relative일 때만)
        }

        /// <summary>정면 재설정(XR): 지금 머리 자리를 '나'의 자리로, 보는 방향을 정면으로. 세션 중이면 events.csv에 recenter로 남긴다.
        /// XR 헤드셋이 없으면 아무것도 하지 않는다.</summary>
        public string Recenter()
        {
            string r = xrRig != null ? xrRig.Recenter() : null;
            if (r == null)
            {
                LastRecenterMessage = "XR 헤드셋이 없어 정면 재설정을 하지 않았습니다";
                return null;
            }
            Session?.Note("recenter", r);
            LastRecenterMessage = "정면 재설정 " + DateTime.Now.ToString("HH:mm:ss", System.Globalization.CultureInfo.InvariantCulture) + ": " + r;
            return r;
        }

        public void PressConfirm()
        {
            if (Stage == PlacementRunnerStage.Checked && Session == null) { StartSession(); return; }
            Session?.PressConfirm();
            ApplyVisuals();
            AfterSession();
        }

        public void PressAbort()
        {
            if (Stage == PlacementRunnerStage.Checked && Session == null) { BackToSetup(); return; }
            if (Session == null || Session.Finished) return;
            Session.Abort();
            ApplyVisuals();
            AfterSession();
        }

        /// <summary>Done 뒤 같은 화면에서 다음 참여자를 준비한다.</summary>
        public void ResetForNext()
        {
            if (Session != null && !Session.Finished) return;
            Session = null;
            Cleanup();
            if (_space != null && config.placementAssist)
            {
                PlacementSpace.SetPractice(_space, false, default, default);
                PlacementSpace.SetAssist(_space, false, default, 0, config.floorRadiusM);
            }
            if (textDisplay != null) textDisplay.HideAll();
            if (panel != null) panel.Hide();
            if (xrInput != null) xrInput.ShowRay(false, 0);
            _shownText = null;
            _activeInput = null;
            _activeSource = null;
            EyeCalibration = null;   // 눈높이는 참여자마다 다시 잰다(G60-3)
            _eyeSampler = null;
            _eyeRefusal = null;
            SetRingsHidden(false);
            Stage = PlacementRunnerStage.Setup;
            Spec = null;
            Selection = null;
            SelectionPathText = "";   // 선택 파일은 참여자마다 다르다 — 다음 참여자에게 이전 선택이 남지 않게
            AppliedOverrides = null;
            _replay = null;
            Errors.Clear();
            Warnings.Clear();
            ParticipantNumberText = "";
            RefreshSpecList();
            PreloadTaskText();
        }
    }
}
