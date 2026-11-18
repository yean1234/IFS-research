// 소유감 실험 러너(설계 2.2). 원본 1개 + 어긋난 변형 4개 + 유효한 같은 말·다른 값 쌍(0·2·4개) = n개(5·7·9)를
// 균형 순서로 하나씩 같은 시간 보여 주고, 형상마다 7점 평정(config.ratingItem: resemblance "떠올린 모습과 닮았다" 기본 |
// mine "내 것 같다"), 마지막에 n개 중 하나 선택, 끝으로 원본 대비 차이 평정(설정으로 끔).
//   Setup → SpecCheck → Intro → (Viewing → Rating) × n → FinalChoice → Difference × (n − 1) → Done.  Esc = 어느 단계에서든 중단.
// 형상 n개는 SceneLoader n개로 만든다(Load(path, 덮어쓰기), 로더 기록 끔). 시작 순간 머리 자세를 고정 앵커로 잡아
// 모든 형상이 같은 자리에 놓인다. 로드한 값이 생성기 계획과 다르면 시작하지 않는다. n ≤ 9(키 한 자리).
// 기록은 OwnershipRecordWriter(설계 2.4). 참여자에게 원본 여부·남은 시간을 보여 주지 않는다.
// 키(실험자): 1–7 평정·선택, Backspace 직전 입력 취소, Space/Enter 확정·다음, Esc 중단. 키 입력은 기존 Input Manager.
// 자동 시행(검증용): BeginAuto(스크립트) 뒤 Tick(dt)을 밖에서 부르면 키 없이 끝까지 간다(시뮬레이션 시계).
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Text;
using System.Text.RegularExpressions;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace IFS.SceneSpec.Ownership
{
    public enum OwnershipPhase { Setup, SpecCheck, Intro, Viewing, Rating, FinalChoice, Difference, Done }

    /// <summary>자동 시행의 정해진 입력(합성). 위치 순서(1–n)대로의 평정(배열보다 길면 되풀이), 한 번의 잘못 누름과 취소, 선택, 차이 평정.</summary>
    public sealed class OwnershipAutoScript
    {
        public int[] Ratings = { 6, 3, 4, 5, 2 };
        /// <summary>이 위치(1–n)에서 먼저 MistakeRating을 누르고 Backspace로 취소한 뒤 다시 평정한다. 0 = 하지 않음.</summary>
        public int CancelAtPosition = 2;
        public int MistakeRating = 7;
        /// <summary>마지막 선택 위치(1–n). 0이면 원본의 위치.</summary>
        public int FinalChoicePosition = 0;
        public int[] DifferenceRatings = { 5, 3, 4, 2 };
        public double KeyDelaySeconds = 0.3;
    }

    public sealed class SpecFileEntry
    {
        public string Path;
        public string Name;
        /// <summary>EX01.v1.json처럼 .v숫자.json으로 끝나는 파일(매핑 버전별 파일). 목록에서 구분해 보인다.</summary>
        public bool IsVariantFile;
    }

    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Ownership/Ownership Experiment Runner")]
    public sealed class OwnershipRunner : MonoBehaviour
    {
        public const string RecordVersion = OwnershipManifest.RecordVersion;
        static readonly Regex VariantFilePattern = new Regex(@"\.v\d+\.json$", RegexOptions.IgnoreCase);

        [Header("설정(manifest.json에 기록)")]
        [SerializeField] OwnershipConfig config = new OwnershipConfig();
        [Tooltip("null 슬롯 기본값. 변형본 생성기와 형상 로더가 같은 값을 쓴다")]
        [SerializeField] SceneDefaults defaults = new SceneDefaults();

        [Header("경로")]
        [Tooltip("spec 목록 폴더. 비우면 에디터에서는 <프로젝트>/../chatbot/logs/scenes, 빌드에서는 persistentDataPath/IFS/scenes")]
        [SerializeField] string specFolder = "";
        [Tooltip("기록 루트. 비우면 persistentDataPath/IFS/sessions(저장소 밖). 그 아래 ownership/P###/…")]
        [SerializeField] string recordRoot = "";
        [Tooltip("문구 파일. 비우면 StreamingAssets/IFS/ownership_task.v0.json")]
        [SerializeField] string taskTextPath = "";

        [Header("모양 프리팹 (메뉴 IFS ▸ Create Shape Prefabs가 연결)")]
        [SerializeField] ShapePrefab[] shapePrefabs =
        {
            new ShapePrefab("round"), new ShapePrefab("square"), new ShapePrefab("flat"), new ShapePrefab("pointed"),
        };

        [Header("구성 요소")]
        [SerializeField] HeadPoseProvider headProvider = null;
        [SerializeField] ParticipantTextDisplay textDisplay = null;

        [Header("배치")]
        [Tooltip("평정 문구 등 글을 세우는 거리(m, 시작 순간 머리 기준 정면)")]
        [SerializeField] float textDistance = 1.5f;
        [Tooltip("마지막 선택·차이 평정에서 이웃 형상 사이 최소 틈(m). 겹치면 반지름을 늘린다")]
        [SerializeField] float layoutMargin = 0.1f;

        // ── 상태(실험자 화면이 읽는다) ─────────────────────────────────────
        public OwnershipPhase Phase { get; private set; } = OwnershipPhase.Setup;
        public string ParticipantNumberText { get; set; } = "";
        public string SpecPathText { get; set; } = "";
        public string SpecFolderText { get; set; }
        public List<SpecFileEntry> SpecFiles { get; } = new List<SpecFileEntry>();
        public List<string> Errors { get; } = new List<string>();
        public List<string> Warnings { get; } = new List<string>();
        public SceneSpecV2 Spec { get; private set; }
        public OwnershipPlan Plan { get; private set; }
        public OwnershipTaskText TaskText { get; private set; }
        public string LastRecordDirectory { get; private set; }
        public bool LastCompleted { get; private set; }
        public string LastAbortedAt { get; private set; }
        /// <summary>실험자 화면의 글 입력 칸에 포커스가 있으면 true(그동안 키를 실험 입력으로 받지 않는다).</summary>
        public bool GuiHasKeyboardFocus { get; set; }
        public int Position => _pos + 1;
        public string ShownVariant => _shownVariant;
        public int? PendingInput => _pending;
        public double SecondsInPhase => Now - _phaseStart;
        public double ViewSecondsLeft => Phase == OwnershipPhase.Viewing ? Math.Max(0, config.viewSeconds - (Now - _viewStart)) : 0;
        public string DifferenceVariant => Phase == OwnershipPhase.Difference && _diffList != null ? _diffList[_diffIndex] : null;
        public int DifferenceIndex => _diffIndex;
        public OwnershipConfig Config => config;
        public string HeadSource => headProvider != null ? headProvider.Source : HeadPoseProvider.SourceDesktop;
        public HeadPoseProvider HeadProvider => headProvider;
        public ParticipantTextDisplay TextDisplay => textDisplay;
        public bool IsAuto => _auto != null;
        public IReadOnlyDictionary<string, int> Ratings => _ratings;
        public int? FinalChoicePosition => _finalPosition;

        // ── 내부 ───────────────────────────────────────────────────────────
        readonly System.Diagnostics.Stopwatch _watch = System.Diagnostics.Stopwatch.StartNew();
        bool _simulated;
        double _simTime;
        double Now => _simulated ? _simTime : _watch.Elapsed.TotalSeconds;

        OwnershipAutoScript _auto;
        double _autoNext;
        bool _autoCancelled;

        string _specFullPath, _specSha;
        GameObject _anchor, _variantsRoot;
        readonly Dictionary<string, SceneLoader> _loaders = new Dictionary<string, SceneLoader>();
        readonly Dictionary<string, (Vector3 pos, Quaternion rot)> _home = new Dictionary<string, (Vector3, Quaternion)>();
        OwnershipRecordWriter _writer;
        double _sessionStart, _phaseStart, _viewStart, _askedAt, _pendingAt;
        HeadSampleClock _sampleClock;
        int _pos;
        long _lastViewMs;
        int? _pending;
        string _shownVariant;
        List<string> _diffList;
        int _diffIndex;
        int? _finalPosition;
        long? _finalRtMs;
        readonly Dictionary<string, int> _ratings = new Dictionary<string, int>();
        string _lastHeadSource;

        bool SessionActive => _writer != null;

        // ── 수명 ─────────────────────────────────────────────────────────
        void Awake()
        {
            if (SpecFolderText == null) SpecFolderText = specFolder;
            RefreshSpecList();
            PreloadTaskText();
        }

        // ── 초안 문구 ─────────────────────────────────────────────────────
        /// <summary>
        /// 문구 파일에 status draft 문구가 있으면 실험자 화면 맨 위에 띄울 한 줄(없으면 null). Setup에서도 보이도록
        /// Awake·Setup 복귀 때 문구 파일을 미리 읽는다(읽기 오류는 Check가 보고한다).
        /// </summary>
        public string DraftPhraseNotice => DraftNotice(TaskText, config.requireSpecPhrases);

        public static string DraftNotice(OwnershipTaskText text, bool requireSpec)
        {
            if (text == null || !text.HasDraft) return null;
            var keys = text.DraftKeys;
            return $"초안 문구 사용 중: {text.FileName ?? "문구 파일"}(version {text.Version})의 문구 {keys.Count}/{text.Count}개가 status draft" +
                   $"(IRB 확인 전) — {string.Join(", ", keys)}. " +
                   (requireSpec ? "requireSpecPhrases가 켜져 있어 시작할 수 없습니다." : "본 실험 자료로 쓰기 전에 spec 문구로 바꾸세요(manifest에 기록됨).");
        }

        /// <summary>requireSpecPhrases가 켜져 있고 draft 문구가 있으면 시작 거부 이유, 아니면 null.</summary>
        public static string SpecPhraseRefusal(OwnershipTaskText text, bool requireSpec) =>
            requireSpec && text != null && text.HasDraft
                ? $"requireSpecPhrases가 켜져 있는데 draft 문구 {text.DraftKeys.Count}개({string.Join(", ", text.DraftKeys)})가 있어 세션을 시작하지 않습니다"
                : null;

        void PreloadTaskText()
        {
            try { TaskText = File.Exists(ResolvedTaskTextPath) ? OwnershipTaskText.Load(ResolvedTaskTextPath) : null; }
            catch (Exception) { TaskText = null; }
        }

        void Update()
        {
            if (_auto != null) return;   // 자동 시행은 Tick을 밖에서 부른다
            Tick(Time.unscaledDeltaTime);
            PollKeys();
        }

        void OnDestroy()
        {
            QuitSession("runner destroyed (play mode stopped or scene closed)");
            DestroyVariants();
        }

        void OnApplicationQuit() => QuitSession("application quit");

        // 재생을 멈추거나 앱을 닫으면 그때까지의 자료를 남기고 중단으로 기록한다.
        void QuitSession(string why)
        {
            if (!SessionActive) return;
            Event("quit", why);
            Finish(false, CurrentPhaseName);
        }

        string CurrentPhaseName => PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant();

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

        string ResolvedTaskTextPath => string.IsNullOrWhiteSpace(taskTextPath)
            ? Path.Combine(Application.streamingAssetsPath, OwnershipTaskText.DefaultRelativePath)
            : (Path.IsPathRooted(taskTextPath) ? taskTextPath : Path.Combine(Application.streamingAssetsPath, taskTextPath));

        public void RefreshSpecList()
        {
            SpecFiles.Clear();
            string dir = ResolvedSpecFolder;
            if (!Directory.Exists(dir)) return;
            foreach (var p in Directory.GetFiles(dir, "*.json").OrderBy(p => Path.GetFileName(p), StringComparer.Ordinal))
                SpecFiles.Add(new SpecFileEntry { Path = p, Name = Path.GetFileName(p), IsVariantFile = VariantFilePattern.IsMatch(p) });
        }

        // ── 설정(에디터 메뉴·자동 시행) ───────────────────────────────────
        public void Configure(HeadPoseProvider head, ParticipantTextDisplay text, IEnumerable<ShapePrefab> shapes)
        {
            headProvider = head;
            textDisplay = text;
            if (shapes != null) shapePrefabs = shapes.Where(s => s != null).Select(s => new ShapePrefab(s.shape, s.prefab)).ToArray();
        }

        public void SetRecordRoot(string root) => recordRoot = root ?? "";

        /// <summary>자동 시행: 시뮬레이션 시계, 정해진 입력, 정해진 머리 경로. viewSeconds 등은 config로 준다.</summary>
        public void BeginAuto(OwnershipAutoScript script, OwnershipConfig cfg)
        {
            _auto = script ?? new OwnershipAutoScript();
            _simulated = true;
            _simTime = 0;
            if (cfg != null) config = cfg.Clone();
        }

        // ── Setup → SpecCheck ───────────────────────────────────────────
        /// <summary>참여자 번호·spec을 읽고 변형본을 만든다. 오류가 있으면 SpecCheck에서 시작할 수 없다.</summary>
        public bool Check()
        {
            if (SessionActive) return false;
            Errors.Clear();
            Warnings.Clear();
            Spec = null;
            Plan = null;
            if (!int.TryParse((ParticipantNumberText ?? "").Trim(), out int number) || number < 1)
                Errors.Add("참여자 번호는 1 이상의 정수여야 합니다");
            string path = (SpecPathText ?? "").Trim().Trim('"');
            if (path.Length == 0) Errors.Add("spec 파일을 고르세요");
            else if (!Path.IsPathRooted(path)) path = Path.Combine(ResolvedSpecFolder, path);
            if (Errors.Count > 0) { Phase = OwnershipPhase.Setup; return false; }
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
            try { TaskText = OwnershipTaskText.Load(ResolvedTaskTextPath); }
            catch (Exception e) { TaskText = null; Errors.Add("문구 파일을 읽지 못했습니다(" + OwnershipTaskText.DefaultRelativePath + "): " + e.Message); }
            if (DraftPhraseNotice != null) Warnings.Add(DraftPhraseNotice);   // events.csv에도 warning으로 남는다
            string refusal = SpecPhraseRefusal(TaskText, config.requireSpecPhrases);
            if (refusal != null) Errors.Add(refusal);
            Plan = OwnershipVariantGenerator.Generate(Spec, number, config, defaults);
            Errors.AddRange(Plan.Errors);
            if (Plan.Ok && TaskText != null) Errors.AddRange(TaskText.Problems(config.ratingItem, Plan.Order.Length));
            Warnings.AddRange(Plan.Warnings);
            if (textDisplay != null) { textDisplay.EnsureFont(); if (textDisplay.FontWarning != null) Warnings.Add(textDisplay.FontWarning); }
            Phase = OwnershipPhase.SpecCheck;
            return Errors.Count == 0;
        }

        public void BackToSetup()
        {
            if (SessionActive) return;
            Phase = OwnershipPhase.Setup;
            Errors.Clear();
            Warnings.Clear();
            RefreshSpecList();
            PreloadTaskText();
        }

        // ── 시작 ─────────────────────────────────────────────────────────
        public bool StartSession()
        {
            if (Phase != OwnershipPhase.SpecCheck || SessionActive) return false;
            if (Plan == null || !Plan.Ok || TaskText == null || Errors.Count > 0)
            {
                if (!Errors.Contains("생성 오류가 있어 시작할 수 없습니다")) Errors.Add("생성 오류가 있어 시작할 수 없습니다");
                return false;
            }
            string refusal = SpecPhraseRefusal(TaskText, config.requireSpecPhrases);
            if (refusal != null) { Errors.Add(refusal); return false; }
            // 확인 뒤 파일이 바뀌었으면 시작하지 않는다(계획과 로드 값이 어긋나지 않도록)
            string sha;
            try { sha = OwnershipManifest.Sha256OfFile(_specFullPath); }
            catch (Exception e) { Errors.Add("spec 파일을 다시 읽지 못했습니다: " + e.Message); return false; }
            if (sha != _specSha) { Errors.Add("확인한 뒤 spec 파일이 바뀌었습니다 — 다시 확인하세요"); return false; }

            if (headProvider != null && _auto == null) headProvider.Step(0f);   // XR이면 지금 헤드셋 자세를 먼저 읽는다
            var headPos = headProvider != null ? headProvider.Position : new Vector3(0f, 1.6f, 0f);
            var headRot = headProvider != null ? headProvider.Rotation : Quaternion.identity;
            var fwd = headRot * Vector3.forward;
            fwd.y = 0f;
            if (fwd.sqrMagnitude < 1e-6f) fwd = Vector3.forward;
            DestroyVariants();
            _anchor = new GameObject("Ownership Anchor (시작 순간 머리)");
            _anchor.transform.SetPositionAndRotation(headPos, Quaternion.LookRotation(fwd.normalized, Vector3.up));
            _variantsRoot = new GameObject("Ownership Variants");

            var loadErrors = new List<string>();
            foreach (var v in Plan.Variants)
            {
                var go = new GameObject("Variant " + v.Id);
                go.transform.SetParent(_variantsRoot.transform, false);
                var loader = go.AddComponent<SceneLoader>();
                loader.ConfigureForRunner(_anchor.transform, defaults);
                loader.ConfigureShapePrefabs(shapePrefabs);
                bool ok = loader.Load(_specFullPath, v.IsOriginal ? null : v.Override);
                if (!ok) { loadErrors.Add(v.Id + ": 로드 실패(콘솔 확인)"); continue; }
                var got = JObject.FromObject(loader.InitialParams.ToRecord());
                var want = JObject.FromObject(v.Params.ToRecord());
                if (!JToken.DeepEquals(got, want)) loadErrors.Add($"{v.Id}: 로드한 값이 계획과 다름 {got.ToString(Newtonsoft.Json.Formatting.None)}");
                string rendered = loader.ShowingShapeModel ? loader.Shape.Model : loader.CurrentParams.GetCategory("form.type");
                if (rendered != v.Rendered) loadErrors.Add($"{v.Id}: 그려진 것 {rendered} ≠ 계획 {v.Rendered}");
                if (loader.InitialParams.InferredUsed.Count > 0) loadErrors.Add(v.Id + ": _inferred를 썼습니다(실행 거부)");
                _loaders[v.Id] = loader;
                _home[v.Id] = (loader.Root.transform.position, loader.Root.transform.rotation);
                loader.Root.SetActive(false);
            }
            if (loadErrors.Count > 0)
            {
                Errors.AddRange(loadErrors);
                DestroyVariants();
                return false;
            }

            var started = DateTime.UtcNow;
            _sessionStart = Now;
            _ratings.Clear();
            _finalPosition = null;
            _finalRtMs = null;
            _pending = null;
            _autoCancelled = false;
            LastCompleted = false;
            LastAbortedAt = null;
            _lastHeadSource = HeadSource;
            _sampleClock = new HeadSampleClock(config.headSampleHz);
            if (_auto != null && headProvider != null) headProvider.BeginScripted();
            string sessionId = Spec.Meta.SessionId ?? Path.GetFileNameWithoutExtension(_specFullPath);
            try
            {
                _writer = new OwnershipRecordWriter(ResolvedRecordRoot, Plan.ParticipantNumber, sessionId, started);
                var info = new OwnershipSessionInfo
                {
                    SessionId = sessionId,
                    SpecFile = Path.GetFileName(_specFullPath),
                    SpecSha256 = _specSha,
                    StartedAtUtc = OwnershipRecordWriter.FormatUtc(started),
                    HeadSource = HeadSource,
                    UnityVersion = Application.unityVersion,
                    TaskTextFile = TaskText.FileName,
                    TaskTextVersion = TaskText.Version,
                    TaskTextDraftKeys = TaskText.DraftKeys.ToArray(),
                };
                _writer.WriteManifest(OwnershipManifest.Build(Plan, info));
            }
            catch (Exception e)
            {
                Errors.Add("기록 폴더를 만들지 못했습니다: " + e.Message);
                _writer?.Dispose();
                _writer = null;
                DestroyVariants();
                return false;
            }
            LastRecordDirectory = _writer.Directory;
            Event("session_start", $"participant={Plan.ParticipantNumber};cb={Plan.Cb};orderRow={Plan.OrderRow};order={string.Join("|", Plan.Order)};headSource={HeadSource};ratingItem={config.ratingItem}");
            if (_auto != null) Event("auto_mode", "scripted inputs and head path (verification only, not participant data)");
            foreach (var w in Warnings) Event("warning", w);
            EnterIntro();
            return true;
        }

        // ── 단계 ─────────────────────────────────────────────────────────
        void SetPhase(OwnershipPhase p, string detail)
        {
            Phase = p;
            _phaseStart = Now;
            _sampleClock?.Reset();   // 새 단계의 첫 표본은 다음 프레임에 바로
            _pending = null;
            Event("phase", detail);
        }

        void EnterIntro()
        {
            SetPhase(OwnershipPhase.Intro, "intro");
            HideAllVariants();
            ShowTextAtEye(TaskText["viewing_intro"]);
        }

        void EnterViewing(int pos)
        {
            _pos = pos;
            string id = Plan.Order[pos];
            HideAllVariants();
            if (textDisplay != null) textDisplay.HideAll();
            ShowVariantAt(id, _home[id].pos, _home[id].rot);
            _shownVariant = id;
            SetPhase(OwnershipPhase.Viewing, $"viewing;position={pos + 1};variant={id}");
            _viewStart = Now;
            // 제시 시작 시각(분석기의 first_look_ms·표본 지속 시간의 시작점). 첫 표본은 다음 프레임에 쓰인다.
            Event(OwnershipRecordWriter.ViewingStartEvent, OwnershipRecordWriter.ViewingStartDetail(pos + 1, id));
        }

        void EndViewing()
        {
            _lastViewMs = Ms(Now - _viewStart);
            string id = _shownVariant;
            HideAllVariants();
            _shownVariant = null;
            Event("hide", $"position={_pos + 1};variant={id};view_ms={_lastViewMs}");
            SetPhase(OwnershipPhase.Rating, $"rating;position={_pos + 1};variant={id}");
            _askedAt = Now;
            ShowTextAtEye(TaskText.RatingText(config.ratingItem));
        }

        void EnterFinal()
        {
            HideAllVariants();
            if (textDisplay != null) textDisplay.HideAll();
            SetPhase(OwnershipPhase.FinalChoice, "final");
            double spacing = config.finalChoiceArcDeg / (Plan.Order.Length - 1);
            var layout = LayoutRow(Plan.Order, spacing, out double radius);
            Event("final_layout", $"radius_m={radius.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)};spacing_deg={spacing.ToString("0.##", System.Globalization.CultureInfo.InvariantCulture)};positions={string.Join("|", Plan.Order)}");
            for (int i = 0; i < Plan.Order.Length; i++)
                if (textDisplay != null) textDisplay.ShowLabel(i, (i + 1).ToString(), layout[i].label, _anchor.transform.position);
            ShowTextAbove(TaskText.FinalChoiceText(config.ratingItem, Plan.Order.Length), layout);
            _askedAt = Now;
        }

        void EnterDifference(int index)
        {
            _diffIndex = index;
            string id = _diffList[index];
            HideAllVariants();
            if (textDisplay != null) textDisplay.HideAll();
            SetPhase(OwnershipPhase.Difference, $"difference;index={index + 1};variant={id};left=orig;right={id}");
            double spacing = config.finalChoiceArcDeg / (Plan.Order.Length - 1);
            var layout = LayoutRow(new[] { "orig", id }, spacing, out double radius);
            Event("difference_layout", $"radius_m={radius.ToString("0.000", System.Globalization.CultureInfo.InvariantCulture)};variant={id}");
            ShowTextAbove(TaskText["difference"], layout);
            _askedAt = Now;
        }

        // 형상들을 같은 반지름의 호에 놓는다(왼쪽부터). 겹치면 반지름을 늘린다. 반환: 위치마다 이름표 자리.
        List<(Vector3 label, float top)> LayoutRow(IList<string> ids, double spacingDeg, out double radius)
        {
            var a = _anchor.transform.position;
            float yaw = _anchor.transform.rotation.eulerAngles.y;
            double baseRadius = config.finalChoiceRadiusM > 0 ? config.finalChoiceRadiusM : HorizontalDistance(a, _home["orig"].pos);
            double maxWidth = 0;
            foreach (var id in ids)
            {
                ShowVariantAt(id, _home[id].pos, _home[id].rot);
                var b = WorldBounds(_loaders[id].Root);
                maxWidth = Math.Max(maxWidth, Math.Max(b.size.x, b.size.z));
            }
            radius = Math.Max(baseRadius, OwnershipGeometry.MinRadiusWithoutOverlap(spacingDeg, maxWidth, layoutMargin));
            var angles = OwnershipGeometry.CenteredAngles(ids.Count, spacingDeg);
            var result = new List<(Vector3, float)>();
            for (int i = 0; i < ids.Count; i++)
            {
                OwnershipGeometry.ArcPoint(a.x, a.z, yaw, angles[i], radius, out double x, out double z);
                var home = _home[ids[i]].pos;
                var pos = new Vector3((float)x, home.y, (float)z);
                var look = a - pos;
                look.y = 0f;
                var rot = look.sqrMagnitude > 1e-6f ? Quaternion.LookRotation(look.normalized, Vector3.up) : Quaternion.identity;
                ShowVariantAt(ids[i], pos, rot);
                var b = WorldBounds(_loaders[ids[i]].Root);
                float top = b.max.y;
                result.Add((new Vector3(pos.x, top + 0.12f, pos.z), top));
            }
            return result;
        }

        static double HorizontalDistance(Vector3 a, Vector3 b)
        {
            double dx = b.x - a.x, dz = b.z - a.z;
            return Math.Sqrt(dx * dx + dz * dz);
        }

        static Bounds WorldBounds(GameObject root)
        {
            var rs = root.GetComponentsInChildren<Renderer>();
            if (rs.Length == 0) return new Bounds(root.transform.position, Vector3.zero);
            var b = rs[0].bounds;
            for (int i = 1; i < rs.Length; i++) b.Encapsulate(rs[i].bounds);
            return b;
        }

        void ShowTextAtEye(string text)
        {
            if (textDisplay == null || _anchor == null) return;
            var a = _anchor.transform.position;
            textDisplay.Show(text, a + _anchor.transform.forward * textDistance, a);
        }

        void ShowTextAbove(string text, List<(Vector3 label, float top)> layout)
        {
            if (textDisplay == null || _anchor == null) return;
            var a = _anchor.transform.position;
            float top = layout.Max(l => l.top);
            var pos = a + _anchor.transform.forward * textDistance;
            pos.y = Math.Max(a.y, top + 0.35f);
            textDisplay.Show(text, pos, a);
        }

        void ShowVariantAt(string id, Vector3 pos, Quaternion rot)
        {
            var root = _loaders[id].Root;
            root.transform.SetPositionAndRotation(pos, rot);
            root.SetActive(true);
        }

        void HideAllVariants()
        {
            foreach (var l in _loaders.Values) if (l != null && l.Root != null) l.Root.SetActive(false);
        }

        void DestroyVariants()
        {
            foreach (var l in _loaders.Values)
                if (l != null)
                {
                    l.Unload();
                    DestroySafe(l.gameObject);
                }
            _loaders.Clear();
            _home.Clear();
            DestroySafe(_variantsRoot);
            DestroySafe(_anchor);
            _variantsRoot = _anchor = null;
        }

        static void DestroySafe(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        // ── 입력 ─────────────────────────────────────────────────────────
        void PollKeys()
        {
            if (GuiHasKeyboardFocus && (Phase == OwnershipPhase.Setup || Phase == OwnershipPhase.SpecCheck)) return;
            if (Input.GetKeyDown(KeyCode.Escape)) PressAbort();
            for (int d = 1; d <= 9; d++)
                if (Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha0 + d)) || Input.GetKeyDown((KeyCode)((int)KeyCode.Keypad0 + d)))
                    PressDigit(d);
            if (Input.GetKeyDown(KeyCode.Backspace)) PressBackspace();
            if (Input.GetKeyDown(KeyCode.Space) || Input.GetKeyDown(KeyCode.Return) || Input.GetKeyDown(KeyCode.KeypadEnter)) PressConfirm();
        }

        public void PressDigit(int d)
        {
            if (!SessionActive) return;
            Event("key", $"{d};phase={PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant()}");
            int max = Phase == OwnershipPhase.FinalChoice ? Plan.Order.Length : 7;
            bool accepts = Phase == OwnershipPhase.Rating || Phase == OwnershipPhase.FinalChoice || Phase == OwnershipPhase.Difference;
            if (!accepts || d < 1 || d > max) return;
            if (_pending != null) { Event("key_ignored", "이미 입력됨 — Backspace로 취소한 뒤 다시"); return; }
            _pending = d;
            _pendingAt = Now;
            Event("input", $"{PhaseLabel(Phase)};value={d};rt_ms={Ms(_pendingAt - _askedAt)}");
        }

        public void PressBackspace()
        {
            if (!SessionActive) return;
            Event("key", $"backspace;phase={PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant()}");
            if (_pending == null) return;
            int v = _pending.Value;
            long rt = Ms(_pendingAt - _askedAt);
            switch (Phase)
            {
                case OwnershipPhase.Rating:
                    _writer.Rating(_pos + 1, Plan.Order[_pos], v, rt, _lastViewMs, cancelled: true, config.ratingItem);
                    Event("rating_cancel", $"position={_pos + 1};variant={Plan.Order[_pos]};rating={v}");
                    break;
                case OwnershipPhase.FinalChoice:
                    Event("final_cancel", $"position={v}");
                    break;
                case OwnershipPhase.Difference:
                    Event("difference_cancel", $"variant={_diffList[_diffIndex]};rating={v}");
                    break;
            }
            _pending = null;
            _askedAt = Now;   // 다시 묻는 시각부터 rt를 잰다
        }

        public void PressConfirm()
        {
            if (Phase == OwnershipPhase.SpecCheck && !SessionActive) { StartSession(); return; }
            if (!SessionActive) return;
            Event("key", $"confirm;phase={PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant()}");
            switch (Phase)
            {
                case OwnershipPhase.Intro:
                    if (textDisplay != null) textDisplay.HideAll();
                    EnterViewing(0);
                    break;
                case OwnershipPhase.Rating:
                    if (_pending == null) return;
                    {
                        string id = Plan.Order[_pos];
                        int v = _pending.Value;
                        _writer.Rating(_pos + 1, id, v, Ms(_pendingAt - _askedAt), _lastViewMs, cancelled: false, config.ratingItem);
                        _ratings[id] = v;
                        Event("rating", $"position={_pos + 1};variant={id};rating={v}");
                        if (textDisplay != null) textDisplay.HideAll();
                        if (_pos + 1 < Plan.Order.Length) EnterViewing(_pos + 1);
                        else EnterFinal();
                    }
                    break;
                case OwnershipPhase.FinalChoice:
                    if (_pending == null) return;
                    _finalPosition = _pending.Value;
                    _finalRtMs = Ms(_pendingAt - _askedAt);
                    Event("final_choice", $"position={_finalPosition};variant={Plan.Order[_finalPosition.Value - 1]};rt_ms={_finalRtMs}");
                    if (config.differenceRating)
                    {
                        _diffList = Plan.Order.Where(id => id != "orig").ToList();
                        EnterDifference(0);
                    }
                    else Finish(true, null);
                    break;
                case OwnershipPhase.Difference:
                    if (_pending == null) return;
                    {
                        string id = _diffList[_diffIndex];
                        _writer.Difference(id, _pending.Value, Ms(_pendingAt - _askedAt));
                        Event("difference", $"variant={id};rating={_pending.Value}");
                        if (_diffIndex + 1 < _diffList.Count) EnterDifference(_diffIndex + 1);
                        else Finish(true, null);
                    }
                    break;
            }
        }

        public void PressAbort()
        {
            if (Phase == OwnershipPhase.SpecCheck && !SessionActive) { BackToSetup(); return; }
            if (!SessionActive) return;
            Event("key", $"escape;phase={PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant()}");
            Finish(false, PhaseLabel(Phase) ?? Phase.ToString().ToLowerInvariant());
        }

        // ── 끝 ───────────────────────────────────────────────────────────
        void Finish(bool completed, string abortedAt)
        {
            if (!SessionActive) return;
            if (!completed)
            {
                // 확정 전 평정은 참여자가 답한 값이므로 남긴다(취소 아님).
                if (Phase == OwnershipPhase.Rating && _pending != null)
                {
                    _writer.Rating(_pos + 1, Plan.Order[_pos], _pending.Value, Ms(_pendingAt - _askedAt), _lastViewMs, cancelled: false, config.ratingItem);
                    _ratings[Plan.Order[_pos]] = _pending.Value;
                    Event("abort_pending_written", $"rating;position={_pos + 1};value={_pending.Value}");
                }
                else if (_pending != null) Event("abort_pending_dropped", $"{PhaseLabel(Phase)};value={_pending.Value}");
                if (Phase == OwnershipPhase.Viewing) Event("hide", $"position={_pos + 1};variant={_shownVariant};view_ms={Ms(Now - _viewStart)};aborted=1");
                Event("abort", abortedAt);
            }
            HideAllVariants();
            _shownVariant = null;
            if (textDisplay != null)
            {
                textDisplay.HideAll();
                if (TaskText != null) ShowTextAtEye(TaskText["done"]);
            }
            string finalVariant = _finalPosition.HasValue ? Plan.Order[_finalPosition.Value - 1] : null;
            _writer.WriteSummary(OwnershipRecordWriter.BuildSummary(completed, completed ? null : abortedAt,
                _finalPosition, finalVariant, _finalRtMs, _ratings, DateTime.UtcNow));
            Event("done", completed ? "completed" : "aborted;" + abortedAt);
            _writer.Dispose();
            _writer = null;
            LastCompleted = completed;
            LastAbortedAt = completed ? null : abortedAt;
            Phase = OwnershipPhase.Done;
            _phaseStart = Now;
        }

        /// <summary>Done 뒤 같은 화면에서 다음 참여자를 준비한다(형상 정리).</summary>
        public void ResetForNext()
        {
            if (SessionActive) return;
            DestroyVariants();
            if (textDisplay != null) textDisplay.HideAll();
            Phase = OwnershipPhase.Setup;
            Plan = null;
            Spec = null;
            Errors.Clear();
            Warnings.Clear();
            ParticipantNumberText = "";
            RefreshSpecList();
            PreloadTaskText();
        }

        // ── 시간·표본 ───────────────────────────────────────────────────
        static long Ms(double seconds) => (long)Math.Round(seconds * 1000.0);
        long SessionMs(double t) => Ms(t - _sessionStart);

        void Event(string ev, string detail)
        {
            _writer?.Event(SessionMs(Now), ev, detail);
        }

        static string PhaseLabel(OwnershipPhase p)
        {
            switch (p)
            {
                case OwnershipPhase.Viewing: return "viewing";
                case OwnershipPhase.Rating: return "rating";
                case OwnershipPhase.FinalChoice: return "final";
                case OwnershipPhase.Difference: return "difference";
                default: return null;
            }
        }

        /// <summary>한 프레임: 시계 → 머리 자세 → 표본 기록 → 제시 시간 확인 → (자동 시행이면) 정해진 입력.</summary>
        public void Tick(double dt)
        {
            if (_simulated) _simTime += Math.Max(0, dt);
            if (headProvider != null)
            {
                if (headProvider.Scripted) headProvider.ScriptedPose(Now - _sessionStart);
                else if (SessionActive && HeadSource != _lastHeadSource)
                {
                    Event("head_source", $"{_lastHeadSource}->{HeadSource}");
                    _lastHeadSource = HeadSource;
                }
                headProvider.DesktopInputEnabled = !GuiHasKeyboardFocus;
            }
            SampleHead();
            if (Phase == OwnershipPhase.Viewing && Now - _viewStart >= config.viewSeconds) EndViewing();
            if (_auto != null && SessionActive) AutoStep();
        }

        // 프레임당 최대 한 표본, 시각은 지금(Now). 밀린 표본을 과거 시각으로 채우지 않는다(HeadSampleClock).
        void SampleHead()
        {
            if (!SessionActive || headProvider == null || _sampleClock == null) return;
            string phase = PhaseLabel(Phase);
            if (phase == null) { _sampleClock.Reset(); return; }
            // 제시 시간이 끝난 프레임의 자세는 viewing으로 쓰지 않는다(같은 Tick에서 Rating으로 넘어간다)
            if (Phase == OwnershipPhase.Viewing && Now >= _viewStart + config.viewSeconds - 1e-9) return;
            if (_sampleClock.TryTake(Now)) WriteSample(Now, phase);
        }

        void WriteSample(double t, string phase)
        {
            var p = headProvider.Position;
            var q = headProvider.Rotation;
            var s = new HeadSample
            {
                TimeMs = SessionMs(t), Phase = phase,
                Position = Phase == OwnershipPhase.Viewing || Phase == OwnershipPhase.Rating ? _pos + 1 : 0,
                Variant = Phase == OwnershipPhase.Viewing ? _shownVariant : null,
                HeadX = p.x, HeadY = p.y, HeadZ = p.z, Qx = q.x, Qy = q.y, Qz = q.z, Qw = q.w,
            };
            if (Phase == OwnershipPhase.Viewing && _shownVariant != null)
            {
                var o = _loaders[_shownVariant].Root.transform.position;
                OwnershipGeometry.DistanceAngle(p.x, p.y, p.z, q.x, q.y, q.z, q.w, o.x, o.y, o.z, out double dist, out double ang);
                s.HasObject = true;
                s.ObjX = o.x; s.ObjY = o.y; s.ObjZ = o.z; s.DistanceM = dist; s.AngleDeg = ang;
            }
            _writer.Head(s);
        }

        // ── 자동 시행 ───────────────────────────────────────────────────
        void AutoStep()
        {
            double delay = _auto.KeyDelaySeconds;
            if (SecondsInPhase < delay || Now < _autoNext) return;
            _autoNext = Now + delay;
            switch (Phase)
            {
                case OwnershipPhase.Intro:
                    PressConfirm();
                    break;
                case OwnershipPhase.Rating:
                    if (_pending == null)
                    {
                        bool mistake = _auto.CancelAtPosition == _pos + 1 && !_autoCancelled;
                        PressDigit(mistake ? _auto.MistakeRating : _auto.Ratings[_pos % _auto.Ratings.Length]);
                    }
                    else if (_auto.CancelAtPosition == _pos + 1 && !_autoCancelled)
                    {
                        _autoCancelled = true;
                        PressBackspace();
                    }
                    else PressConfirm();
                    break;
                case OwnershipPhase.FinalChoice:
                    if (_pending == null)
                    {
                        int pos = _auto.FinalChoicePosition > 0 ? _auto.FinalChoicePosition : Array.IndexOf(Plan.Order, "orig") + 1;
                        PressDigit(pos);
                    }
                    else PressConfirm();
                    break;
                case OwnershipPhase.Difference:
                    if (_pending == null) PressDigit(_auto.DifferenceRatings[_diffIndex % _auto.DifferenceRatings.Length]);
                    else PressConfirm();
                    break;
            }
        }

        // ── 실험자 화면용 요약 ───────────────────────────────────────────
        /// <summary>SpecCheck 표: 슬롯, spec 값, 구분(말한 값 / 기본값 / 근거 없음), 근거 말(trigger), 해석값.</summary>
        public List<string[]> SpecTable()
        {
            var rows = new List<string[]>();
            if (Spec == null) return rows;
            var rec = Plan?.OriginalParams?.ToRecord();
            foreach (var path in SceneSpecJson.SlotPaths)
            {
                var value = SceneSpecJson.GetSlot(Spec, path);
                string shown = value == null ? "null" : (value is HslColor c ? $"h{c.H:0.###} s{c.S:0.###} l{c.L:0.###}" : Convert.ToString(value, System.Globalization.CultureInfo.InvariantCulture));
                string triggers = Spec.Provenance != null && Spec.Provenance.TryGetValue(path, out var prov) && prov != null
                    ? string.Join(" / ", prov.Select(p => p.Trigger)) : "";
                string resolved = "";
                if (rec != null)
                {
                    if (path == "material.color")
                        resolved = string.Join(" ", new[] { "h", "s", "l" }.Select(k => k + Convert.ToString(rec["material.color." + k], System.Globalization.CultureInfo.InvariantCulture)));
                    else if (rec.TryGetValue(path, out var r)) resolved = Convert.ToString(r, System.Globalization.CultureInfo.InvariantCulture);
                }
                rows.Add(new[] { path, shown, SpecCheckLabel(OwnershipVariantGenerator.SlotSource(Spec, path)), triggers, resolved });
            }
            return rows;
        }

        public const string LabelStated = "말한 값";
        public const string LabelDefault = "기본값";
        public const string LabelUnsupported = "근거 없음";

        /// <summary>SpecCheck 구분 칸. 판정은 생성기의 SlotSource(변형 source와 같은 _provenance 기준)를 그대로 쓴다.</summary>
        public static string SpecCheckLabel(string slotSource)
        {
            switch (slotSource)
            {
                case OwnershipVariantGenerator.SlotStated: return LabelStated;
                case OwnershipVariantGenerator.SlotUnsupported: return LabelUnsupported;
                default: return LabelDefault;
            }
        }

        /// <summary>SpecCheck: _unmapped·_unmatched·_alternatives·_needsConfirmation 원문.</summary>
        public List<string> LeftoverLines()
        {
            var lines = new List<string>();
            if (Spec == null) return lines;
            lines.Add($"_unmapped {Spec.Unmapped?.Count ?? 0}개");
            foreach (var u in Spec.Unmapped ?? new List<UnmappedHit>())
                lines.Add($"   '{u.Provenance?.Trigger}' {u.Category} {u.Value?.ToString(Newtonsoft.Json.Formatting.None)} ({u.Reason})");
            lines.Add($"_unmatched {Spec.Unmatched?.Count ?? 0}개");
            if (Spec.Unmatched != null && Spec.Unmatched.Count > 0)
                lines.Add("   " + string.Join(", ", Spec.Unmatched.Select(u => u.Surface)));
            lines.Add($"_alternatives {Spec.Alternatives?.Count ?? 0}개");
            foreach (var a in Spec.Alternatives ?? new List<AlternativeValue>())
                lines.Add($"   {a.Path} = {a.Value?.ToString(Newtonsoft.Json.Formatting.None)} ({a.Reason}, '{string.Join("/", a.Provenance?.Select(p => p.Trigger) ?? new string[0])}')");
            lines.Add($"_needsConfirmation {Spec.NeedsConfirmation?.Count ?? 0}개");
            foreach (var n in Spec.NeedsConfirmation ?? new List<NeedsConfirmationItem>())
                lines.Add($"   {n.Path}: '{n.Trigger}' → {n.Matched} ({n.Reason})");
            return lines;
        }
    }
}
