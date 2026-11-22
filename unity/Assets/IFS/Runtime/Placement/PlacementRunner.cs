// 배치 실험 러너(RQ V4, 프로토타입). 확정 spec의 물체 하나(변형본 없음)를 '나' 기준 공간에 두고,
// 조건(place | view)·통제 방식(static | system_move | replay | point_select)에 따라 한 회기를 진행한다.
// 단계 흐름·기록은 PlacementSession(UnityEngine 없음)이 맡고, 이 컴포넌트는 그것을 그린다:
//   물체(SceneLoader — 장면 속성은 기존 로더 경로 그대로), 공간(PlacementSpace), 참여자 글(ParticipantTextDisplay), 입력(IPlacementInput).
// 실험자 키: 숫자 0–9 평정(문항 범위 안, 두 자리 범위는 이어 침), Backspace 직전 입력 취소, Enter 확정·다음, Esc 중단, R 정면 재설정(XR).
// 선택 파일(선택, D8): 챗봇의 selection.json(ifs-selection/0.1 — PlacementSelection). 있으면 원본 spec + finalOverrides로 형상을 한 번 만들고
//   (조건 단계 동안 바뀌지 않음), sha 불일치·모르는 키·적용하지 못한 키는 시작 거부. 없으면 예전처럼 spec만.
// 참여자 입력: 설정 inputMode(auto | desktop | xr)에 따라 Check 때 고른다(PlacementInputSelection) —
//   XR 헤드셋이 켜져 있으면 XrPlacementInput(컨트롤러 광선), 없으면 DesktopPlacementInput(마우스·키보드).
// 참여자 글: PlacementTextPanel(세계 고정 판, 헤드셋 안에서 읽힘)이 있으면 그것, 없으면 ParticipantTextDisplay(예전 씬).
// 자동 시행(검증용): BeginAuto(스크립트, 설정) 뒤 Tick(dt)을 밖에서 부르면 사람 없이 끝까지 간다(시뮬레이션 시계).
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
        public string DraftPhraseNotice => PlacementTaskText.DraftNotice(TaskText, config.requireSpecPhrases);
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
        string _shownText;
        IPlacementInput _activeInput;
        string _activeSource;

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
            Tick(Time.unscaledDeltaTime);
            PollKeys();
        }

        void OnDestroy()
        {
            Session?.Quit("runner destroyed (play mode stopped or scene closed)");
            AfterSession();
            Cleanup();
            _space?.Dispose();
            _space = null;
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
            CheckSelection();
            string refusal = PlacementTaskText.SpecPhraseRefusal(TaskText, config.requireSpecPhrases);
            if (refusal != null) Errors.Add(refusal);
            if (config.EffectiveControlMode == PlacementConfig.ModeReplay) CheckReplay();
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

            Cleanup();
            BuildSpace();
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

            double objectRadius = ObjectRadius();   // 물체 렌더 경계(AABB 가장 큰 반폭). 없으면 0 → manifest null
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
                TaskTextDraftKeys = TaskText.DraftKeys.ToArray(),
                ReplayFile = _replay != null ? Path.GetFileName(_replayFullPath) : null,
                ReplaySha256 = _replay != null ? _replaySha : null,
                ReplaySourceSessionId = _replay?.SourceSessionId,
                ObjectBoundingRadiusM = objectRadius > 0 ? objectRadius : (double?)null,
                LayoutIgnored = _layoutWarning != null,
                Selection = Selection,
                AppliedOverrides = AppliedOverrides,
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
            if (Selection != null)   // events.csv에 선택 파일 한 줄(경고가 아님 — manifest selection·appliedOverrides가 정본)
                Session.Note("selection", $"file={Clean(Selection.FileName)};none={(Selection.None ? 1 : 0)};candidate={Clean(Selection.SelectedCandidateId)};" +
                                          $"applied={AppliedOverrides?.Count ?? 0}");
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

        void BuildSpace()
        {
            _space?.Dispose();
            _space = PlacementSpace.Build(config, transform);
            PlacementSpace.HideEnvironmentFloor();
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
            ApplyVisuals();
            AfterSession();
        }

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
            var textAt = new Vector3(0f, textHeightM, textForwardM);
            var eye = new Vector3(0f, anchorEyeHeightM, 0f);
            if (panel != null)
            {
                // 헤드셋 안 판: 평정 문항이면 문항 + 1–7 기준점(참여자가 고르는 중인 값 강조), 아니면 안내 글
                var item = Session.CurrentItem;
                if (item != null) panel.ShowItem(item, Session.RatingCursor, textAt, eye);
                else if (Session.ParticipantText == null) panel.Hide();
                else panel.ShowText(Session.ParticipantText, textAt, eye);
            }
            else if (textDisplay != null && Session.ParticipantText != _shownText)
            {
                _shownText = Session.ParticipantText;
                if (_shownText == null) textDisplay.Hide();
                else textDisplay.Show(_shownText, textAt, eye);
            }
            ApplyXrRay();
            if (_space != null)
            {
                SetMarker(_space.PointerMarker, Session.Phase == PlacementPhase.Condition ? Session.PointerHit : null);
                var target = Session.MoveTarget;
                SetMarker(_space.TargetMarker, Session.Phase == PlacementPhase.Condition && Session.Config.controlMode == PlacementConfig.ModePointSelect && target.HasValue
                    ? new PVec3(target.Value.X, 0, target.Value.Z) : (PVec3?)null);
            }
        }

        /// <summary>XR 광선: XR 입력을 쓰는 중이고 (rayOnlyWhenUsable이면) 광선이 쓰이는 단계에서만 보인다.</summary>
        void ApplyXrRay()
        {
            if (xrInput == null) return;
            bool xrActive = _auto == null && ReferenceEquals(_activeInput, xrInput);
            var s = Session;
            bool usable = s != null && !s.Finished && s.Phase == PlacementPhase.Condition
                          && (s.Config.IsPlace || s.Config.controlMode == PlacementConfig.ModePointSelect);
            bool show = xrActive && s != null && !s.Finished && (usable || !rayOnlyWhenUsable);
            double end = 0;
            if (show)
            {
                var smp = xrInput.LastSample;
                end = XrRayVisual.EndDistance(smp.RayOrigin, smp.RayDirection, s.Held, s.ObjectPosition, s.ObjectVisible, s.GrabRadiusM, xrInput.RayMaxLengthM);
            }
            xrInput.ShowRay(show, end);
        }

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
            if (textDisplay != null) textDisplay.HideAll();
            if (panel != null) panel.Hide();
            if (xrInput != null) xrInput.ShowRay(false, 0);
            _shownText = null;
            _activeInput = null;
            _activeSource = null;
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
