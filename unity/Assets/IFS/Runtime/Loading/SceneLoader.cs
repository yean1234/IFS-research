// SceneSpec v2 JSON → VR 오브젝트.
//   form.type      → 프리팹 4종(blob/mist/shell/fragments). 비어 있으면 기본 절차 모형(잘게 나눈 구 + IFS 셰이더,
//                    형태별 프리셋). IFS 셰이더를 못 쓰는 환경이면 임시 프리미티브(로그 + initialScene notes)
//                    형상별 모형은 FormRenderPlan(슬롯 값 → 렌더러 입력) + IFormRenderer(Runtime/Rendering)가 만든다(X64)
//   _unmapped 모양어 → 모양 모형(round 구 · square 큐브 · flat 납작 원기둥 · pointed 원뿔, ShapeMapping).
//                    form.type이 null·blob일 때만. 표에 없는 모양어는 경고하고 unmapped_shape로 기록(구로 바꾸지 않음).
//                    판정은 initialScene.json·report.json의 "shape"(docs/shape-mapping.md)
//   material.*     → Shader Graph 파라미터(_BaseColor, _Brightness, _Roughness, _Opacity, _Erosion)
//   layout.*       → Transform(거리·높이·크기), form.posture → 크기 변형 프리셋
//   motion.*       → SpecMotion(절차적 움직임)
// null 값은 SceneDefaults로 채우고, 어떤 값을 기본값으로 썼는지 콘솔과 initialScene.json(defaultsUsed)에 남긴다.
// _inferred(3층 제안)는 useInferredSuggestions를 켜야만 쓴다(기본 꺼짐 — 말하지 않은 것을 추론하지 않는다).
// 참여자 조정은 SetNumber/SetCategory로 → events.csv 한 줄씩, SaveFinal()로 finalScene.json.
// 소유감 실험 변형본은 Load(path, SceneOverride): 해석값 덮어쓰기·모양 모형 강제, 기록(RecordChange) 없음. Load(path)는 그대로.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Rendering;

namespace IFS.SceneSpec
{
    [Serializable]
    public sealed class FormPrefab
    {
        public string formType;
        public GameObject prefab;

        public FormPrefab() { }
        public FormPrefab(string type) { formType = type; }
    }

    /// <summary>모양 값(round·square·flat·pointed) → 모양 모형 프리팹. 메뉴 IFS ▸ Create Shape Prefabs가 채운다.</summary>
    [Serializable]
    public sealed class ShapePrefab
    {
        public string shape;
        public GameObject prefab;

        public ShapePrefab() { }
        public ShapePrefab(string shape, GameObject prefab = null) { this.shape = shape; this.prefab = prefab; }
    }

    [Serializable]
    public sealed class ShaderParamNames
    {
        [Tooltip("Shader Graph 프로퍼티 Reference 이름")] public string baseColor = "_BaseColor";
        public string brightness = "_Brightness";
        public string roughness = "_Roughness";
        public string opacity = "_Opacity";
        public string erosion = "_Erosion";
        [Tooltip("_BaseColor가 없을 때(Built-in Standard)")] public string colorFallback = "_Color";
        [Tooltip("_Roughness가 없을 때 1 − roughness를 넣는다(URP Lit)")] public string smoothnessFallback = "_Smoothness";
        [Tooltip("_Roughness·_Smoothness가 없을 때(Built-in Standard)")] public string glossinessFallback = "_Glossiness";
        [Tooltip("_Brightness가 없을 때 발광으로 근사")] public string emissionFallback = "_EmissionColor";
    }

    [Serializable]
    public sealed class PlacementSettings
    {
        [Tooltip("layout.distance = 0일 때(m)")] public float minDistance = 0.3f;
        [Tooltip("layout.distance = 1일 때(m)")] public float maxDistance = 3.0f;
        [Tooltip("바닥 높이(XR Origin을 Floor 기준으로 둘 때 0)")] public float floorY = 0f;
        [Tooltip("눈높이 / 키 (Drillis & Contini 1966 ≈ 0.936)")] public float eyeHeightRatio = 0.936f;
        [Tooltip("0보다 크면 이 키(m)를 쓴다. 0이면 로드 순간의 머리 높이로 계산")] public float participantHeightOverride = 0f;
        [Tooltip("머리를 찾지 못했을 때의 키(m)")] public float fallbackParticipantHeight = 1.65f;
        [Tooltip("프리미티브 대체 때 기본 크기(m). 프리팹은 프리팹 자체 크기를 기본(×1)으로 쓴다")] public float primitiveBaseSize = 0.35f;
    }

    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/SceneSpec Loader")]
    public sealed class SceneLoader : MonoBehaviour
    {
        // 자세어 → 크기 변형(x, y, z 배율). 표에 없는 자세는 적용하지 않고 기록한다.
        public static readonly Dictionary<string, Vector3> PostureScale = new Dictionary<string, Vector3>
        {
            { "curled", new Vector3(1.15f, 0.7f, 1.15f) }, { "crouched", new Vector3(1.15f, 0.7f, 1.15f) },
            { "cowering", new Vector3(1.1f, 0.7f, 1.1f) }, { "hunched", new Vector3(1.1f, 0.8f, 1.1f) },
            { "bowed", new Vector3(1.05f, 0.85f, 1.05f) }, { "bent", new Vector3(1.05f, 0.85f, 1.05f) },
            { "lying", new Vector3(1.3f, 0.5f, 1.3f) }, { "prone", new Vector3(1.3f, 0.5f, 1.3f) },
            { "drooping", new Vector3(1.2f, 0.6f, 1.2f) }, { "sagging", new Vector3(1.2f, 0.6f, 1.2f) },
            { "limp", new Vector3(1.2f, 0.6f, 1.2f) },
            { "standing", new Vector3(0.9f, 1.2f, 0.9f) }, { "sitting", new Vector3(1f, 0.9f, 1f) },
            { "hanging", new Vector3(0.9f, 1.25f, 0.9f) },
        };

        // 형상별 모양(프리셋·메시·셰이더)은 FormRenderPlan(규칙 기반 어댑터)과 IFormRenderer(형상별 렌더러)가 정한다(X64).
        const string MistFloorProperty = "_FloorY";

        [Header("경로")]
        [Tooltip("ISceneSpecPathSource를 구현한 컴포넌트. 비우면 같은 GameObject에서 찾는다(InspectorPathSource).")]
        [SerializeField] MonoBehaviour pathSource = null;
        [SerializeField] bool loadOnStart = true;

        [Header("형태 프리팹 (비어 있으면 임시 프리미티브)")]
        [SerializeField] FormPrefab[] formPrefabs =
        {
            new FormPrefab("blob"), new FormPrefab("mist"), new FormPrefab("shell"), new FormPrefab("fragments"),
        };

        [Tooltip("프리팹이 없을 때 IFS 셰이더(Resources/IFS)로 절차 모형을 만든다. 끄면 Unity 기본 프리미티브")]
        [SerializeField] bool useProceduralModels = true;

        [Header("모양 프리팹 (메뉴 IFS ▸ Create Shape Prefabs가 연결)")]
        [Tooltip("_unmapped의 모양어(round·square·flat·pointed) → 모형. 비어 있으면 같은 형상을 코드로 만들고 경고를 남긴다")]
        [SerializeField] ShapePrefab[] shapePrefabs =
        {
            new ShapePrefab("round"), new ShapePrefab("square"), new ShapePrefab("flat"), new ShapePrefab("pointed"),
        };

        [Header("Shader Graph 파라미터")]
        [SerializeField] ShaderParamNames shaderParams = new ShaderParamNames();

        [Header("null일 때 기본값")]
        [SerializeField] SceneDefaults defaults = new SceneDefaults();
        [Tooltip("켜면 _inferred(3층 V/A/D 제안)를 기본값보다 먼저 쓴다. 원칙상 기본은 꺼짐.")]
        [SerializeField] bool useInferredSuggestions = false;

        [Header("배치")]
        [Tooltip("참여자 머리(XR 카메라). 비우면 Camera.main")]
        [SerializeField] Transform head = null;
        [SerializeField] PlacementSettings placement = new PlacementSettings();
        [Tooltip("머리 기준 추가 오프셋(m): x 오른쪽, y 위, z 앞. 테스트 씬에서 여러 개를 나란히 둘 때")]
        [SerializeField] Vector3 extraOffset = Vector3.zero;

        [Header("기록")]
        [SerializeField] bool record = true;
        [Tooltip("비우면 Application.persistentDataPath/IFS/sessions. 그 아래 {sessionId}/에 저장")]
        [SerializeField] string recordRoot = "";
        [SerializeField] bool autoSaveFinalOnDestroy = true;

        public SceneSpecV2 Spec { get; private set; }
        public string SpecPath { get; private set; }
        public SceneParams InitialParams { get; private set; }
        public SceneParams CurrentParams { get; private set; }
        public ExperimentRecorder Recorder => _recorder;
        public GameObject Root => _root;
        /// <summary>로더 메모(기본값 사용, 프리미티브 대체, 없는 셰이더 프로퍼티 …). initialScene.json의 notes와 같다.</summary>
        public IReadOnlyList<string> Notes => _notes;
        /// <summary>모양어 판정(_unmapped의 모양어 → 모형). initialScene.json·report.json의 "shape".</summary>
        public ShapeResolution Shape { get; private set; }
        /// <summary>지금 보이는 모형이 모양 모형인가(참여자가 form.type을 바꾸면 그 형태 모형으로 돌아간다).</summary>
        public bool ShowingShapeModel => _isShapeModel;
        public IReadOnlyList<ShapePrefab> ShapePrefabs => shapePrefabs;
        /// <summary>지금 적용한 형상별 렌더 계획(FormRenderPlan). 로드 전이면 null.</summary>
        public FormRenderPlan RenderPlan { get; private set; }
        /// <summary>지금 모형을 만든 경로: 렌더러 이름(blob·mist·shell·fragments·shapeModel) 또는
        /// prefab(형태)·shapePrefab(모형)·primitive(형태)·shapeModelPrimitive(모형). report.json의 renderPath.</summary>
        public string RenderPath { get; private set; }
        public event Action<SceneLoader> Loaded;

        ISceneSpecPathSource _source;
        ExperimentRecorder _recorder;
        GameObject _root, _model;
        SpecMotion _motion;
        Vector3 _anchorPos, _anchorForward, _modelBaseScale;
        float _eyeHeight;
        bool _isShapeModel;
        readonly List<string> _notes = new List<string>();
        // 로더가 만든 머티리얼 사본(Unload 때 정리). renderer.materials는 에디트 모드에서 누수 오류를 내므로 직접 복제한다.
        readonly HashSet<Material> _ownedMaterials = new HashSet<Material>();

        // ── 수명 ─────────────────────────────────────────────────────────────
        void OnEnable()
        {
            _source = ResolveSource();
            if (_source != null) _source.SpecPathChanged += OnSpecPathChanged;
        }

        void OnDisable()
        {
            if (_source != null) _source.SpecPathChanged -= OnSpecPathChanged;
        }

        void Start()
        {
            if (loadOnStart) LoadFromSource();
        }

        void OnDestroy()
        {
            CloseRecorder();
            foreach (var m in _ownedMaterials) DestroySafe(m);   // 형상(자식)은 함께 지워지지만 머티리얼 사본은 남으므로
            _ownedMaterials.Clear();
        }

        void OnSpecPathChanged(string path) => Load(path);

        ISceneSpecPathSource ResolveSource()
        {
            if (pathSource is ISceneSpecPathSource s) return s;
            if (pathSource != null)
                Debug.LogWarning($"[SceneLoader] {pathSource.GetType().Name}는 ISceneSpecPathSource가 아닙니다.", this);
            return GetComponent<ISceneSpecPathSource>();
        }

        [ContextMenu("SceneSpec 다시 불러오기")]
        public void LoadFromSource()
        {
            var src = _source ?? ResolveSource();
            if (src == null || !src.TryGetSpecPath(out var path))
            {
                Debug.LogWarning("[SceneLoader] SceneSpec 경로가 없습니다(InspectorPathSource에 입력).", this);
                return;
            }
            Load(path);
        }

        // ── 로드 ─────────────────────────────────────────────────────────────
        public bool Load(string path) => Load(path, null);

        /// <summary>소유감 실험 변형본: 해석값에 덮어쓰기와 모양 모형 강제(variant)를 얹어 로드한다.
        /// 덮어쓰기는 참여자 조정이 아니므로 RecordChange(events.csv)를 타지 않는다. variant가 null이면 Load(path)와 같다.</summary>
        public bool Load(string path, SceneOverride variant)
        {
            string full = ResolvePath(path);
            string raw;
            SceneSpecV2 spec;
            try
            {
                raw = File.ReadAllText(full, Encoding.UTF8);
                spec = SceneSpecJson.Parse(raw);
            }
            catch (Exception e)
            {
                Debug.LogError($"[SceneLoader] SceneSpec을 읽지 못했습니다: {full}\n{e.Message}", this);
                return false;
            }
            foreach (var problem in SceneSpecJson.Validate(spec))
                Debug.LogWarning($"[SceneLoader] 형식 경고({Path.GetFileName(full)}): {problem}", this);
            if (variant != null && !CheckVariant(spec, variant, Path.GetFileName(full))) return false;

            Unload();
            Spec = spec;
            SpecPath = full;
            _notes.Clear();
            InitialParams = SceneParams.FromSpec(spec, defaults, useInferredSuggestions);
            foreach (var key in InitialParams.DefaultsUsed)
                Note($"{key}: SceneSpec 값이 null → 기본값 {Describe(InitialParams, key)} 사용", false);
            foreach (var key in InitialParams.InferredUsed)
                Note($"{key}: 3층 제안(_inferred) {Describe(InitialParams, key)} 사용", false);
            if (variant != null) ApplyVariantParams(variant);
            CurrentParams = InitialParams.Clone();
            Shape = ShapeMapping.Resolve(spec);
            if (variant?.ShapeModel != null)
            {
                Shape = ShapeMapping.Forced(Shape, variant.ShapeModel);
                Note($"변형 덮어쓰기(기록 안 함): 모양 모형 강제 → {Shape.Model}", false);
            }
            NoteShapeWords(Path.GetFileName(full), spec.Meta.SessionId);

            CaptureAnchor();
            BuildHierarchy();
            ApplyAll();

            if (record)
            {
                var sessionId = spec.Meta.SessionId ?? Path.GetFileNameWithoutExtension(full);
                _recorder = new ExperimentRecorder(RecordRoot, sessionId, spec, full);
                _recorder.WriteInitial(InitialParams, raw, _notes, Shape.ToJson());
                Debug.Log($"[SceneLoader] 기록 폴더: {_recorder.Directory}", this);
            }
            Debug.Log($"[SceneLoader] {Path.GetFileName(full)} 로드: form={CurrentParams.GetCategory("form.type")}, " +
                      $"기본값 {InitialParams.DefaultsUsed.Count}개, shape={Shape.Status}" +
                      (Shape.Model != null ? $"({Shape.Applied} → {Shape.Model})" : ""), this);
            Loaded?.Invoke(this);
            return true;
        }

        public void Unload()
        {
            CloseRecorder();
            DestroySafe(_root);
            foreach (var m in _ownedMaterials) DestroySafe(m);
            _ownedMaterials.Clear();
            _root = _model = null;
            _motion = null;
            _isShapeModel = false;
            RenderPlan = null;
            RenderPath = null;
            Shape = null;
            Spec = null;
            InitialParams = CurrentParams = null;
        }

        string ResolvePath(string path) =>
            Path.IsPathRooted(path) ? path : Path.Combine(Application.streamingAssetsPath, path);

        // ── 변형본(소유감 실험) ─────────────────────────────────────────────
        /// <summary>null 슬롯에 쓰는 기본값(변형본 생성기가 같은 값으로 해석하도록 읽는다).</summary>
        public SceneDefaults Defaults => defaults;
        public bool UseInferredSuggestions => useInferredSuggestions;

        /// <summary>실험 러너용 설정: 머리 기준(고정 앵커), 기본값, 기록 끔(러너가 자체 기록), 시작 때 자동 로드 끔, _inferred 끔.</summary>
        public void ConfigureForRunner(Transform headAnchor, SceneDefaults sceneDefaults)
        {
            head = headAnchor;
            if (sceneDefaults != null) defaults = sceneDefaults;
            record = false;
            loadOnStart = false;
            autoSaveFinalOnDestroy = false;
            useInferredSuggestions = false;
        }

        // 덮어쓰기를 확인한다(로드 전, 지금 형상을 지우기 전에). 모르는 키·모형, blob이 아닌 형태의 모양 모형은 오류.
        bool CheckVariant(SceneSpecV2 spec, SceneOverride variant, string file)
        {
            var errors = variant.Validate();
            if (errors.Count == 0)
            {
                var check = SceneParams.FromSpec(spec, defaults, useInferredSuggestions);
                variant.ApplyTo(check);
                string model = variant.ShapeModel ?? ShapeMapping.Resolve(spec).Model;
                string form = check.GetCategory("form.type");
                if (model != null && form != "blob") errors.Add($"모양 모형 {model}은 form.type=blob에만 쓸 수 있음(지금 {form})");
            }
            if (errors.Count == 0) return true;
            Debug.LogError($"[SceneLoader] 변형 덮어쓰기를 적용할 수 없습니다({file}): {string.Join("; ", errors)}", this);
            return false;
        }

        // InitialParams에 덮어쓰기를 얹는다. 참여자 조정이 아니므로 RecordChange를 부르지 않는다(notes에만 남김).
        void ApplyVariantParams(SceneOverride variant)
        {
            foreach (var kv in variant.Numbers)
            {
                string from = Describe(InitialParams, kv.Key);
                if (InitialParams.SetNumber(kv.Key, kv.Value))
                    Note($"변형 덮어쓰기(기록 안 함): {kv.Key} {from} → {Describe(InitialParams, kv.Key)}", false);
            }
            foreach (var kv in variant.Categories)
            {
                string from = InitialParams.GetCategory(kv.Key);
                if (InitialParams.SetCategory(kv.Key, kv.Value))
                    Note($"변형 덮어쓰기(기록 안 함): {kv.Key} {from} → {kv.Value}", false);
            }
        }

        string RecordRoot => string.IsNullOrEmpty(recordRoot)
            ? Path.Combine(Application.persistentDataPath, "IFS", "sessions")
            : recordRoot;

        // ── 참여자 조정 ─────────────────────────────────────────────────────
        /// <summary>수치 파라미터(0–1) 조정. 예: SetNumber("material.brightness", 0.7f)</summary>
        public bool SetNumber(string key, float value)
        {
            if (CurrentParams == null) return false;
            double from = CurrentParams.GetNumber(key);
            if (!CurrentParams.SetNumber(key, value)) return false;
            ApplyAll();
            _recorder?.RecordChange(key, ExperimentRecorder.FormatNumber(from),
                ExperimentRecorder.FormatNumber(CurrentParams.GetNumber(key)), CurrentDistance());
            return true;
        }

        /// <summary>범주 파라미터 조정: form.type · form.posture · motion.type</summary>
        public bool SetCategory(string key, string value)
        {
            if (CurrentParams == null) return false;
            string from = CurrentParams.GetCategory(key);
            if (!CurrentParams.SetCategory(key, value)) return false;
            if (key == "form.type") BuildHierarchy();
            ApplyAll();
            _recorder?.RecordChange(key, from, value, CurrentDistance());
            return true;
        }

        /// <summary>참여자가 "내 심상과 같다"고 한 뒤 부른다 → finalScene.json</summary>
        public void SaveFinal()
        {
            if (_recorder == null || CurrentParams == null) return;
            _recorder.WriteFinal(InitialParams, CurrentParams);
            Debug.Log($"[SceneLoader] finalScene.json 저장: {_recorder.Directory}", this);
        }

        void CloseRecorder()
        {
            if (_recorder == null) return;
            if (autoSaveFinalOnDestroy && !_recorder.FinalWritten) SaveFinal();
            _recorder.Dispose();
            _recorder = null;
        }

        public float CurrentDistance()
        {
            var h = ResolveHead();
            if (_root == null) return float.NaN;
            return Vector3.Distance(h != null ? h.position : _anchorPos, _root.transform.position);
        }

        // ── 만들기 ─────────────────────────────────────────────────────────
        Transform ResolveHead()
        {
            if (head != null) return head;
            var cam = Camera.main;
            return cam != null ? cam.transform : null;
        }

        void CaptureAnchor()
        {
            var h = ResolveHead();
            if (h == null)
            {
                _anchorPos = new Vector3(0f, placement.floorY + 1.6f, 0f);
                _anchorForward = Vector3.forward;
                Note("머리(카메라)를 찾지 못해 (0, 1.6, 0)에서 앞을 본다고 가정", true);
            }
            else
            {
                _anchorPos = h.position;
                var f = h.forward;
                f.y = 0f;
                _anchorForward = f.sqrMagnitude < 1e-4f ? Vector3.forward : f.normalized;
            }
            _eyeHeight = _anchorPos.y - placement.floorY;
        }

        float ParticipantHeight()
        {
            if (placement.participantHeightOverride > 0f) return placement.participantHeightOverride;
            if (_eyeHeight > 0.5f) return _eyeHeight / placement.eyeHeightRatio;
            return placement.fallbackParticipantHeight;
        }

        void BuildHierarchy()
        {
            if (_root == null)
            {
                _root = new GameObject("SceneSpec " + (Spec?.Meta.SessionId ?? "object"));
                _root.transform.SetParent(transform, false);
                var pivot = new GameObject("motion");
                pivot.transform.SetParent(_root.transform, false);
                _motion = pivot.AddComponent<SpecMotion>();
            }
            ReleaseModel();
            _isShapeModel = false;

            string form = CurrentParams.GetCategory("form.type");
            // 모양 모형: 판정이 적용(applied)이고, 참여자가 form.type을 처음 값에서 바꾸지 않았을 때(FormRenderPlan이 판정).
            // (조정 중 form.type을 바꾸면 그 형태 모형을 보여 주고, 처음 값으로 돌아오면 모양 모형으로 돌아온다)
            RenderPlan = BuildPlan();
            if (RenderPlan.Renderer == FormRenderPlan.RendererShapeModel)
            {
                BuildShapeModel(form);
                return;
            }

            var prefab = FindPrefab(form);
            if (prefab != null)
            {
                _model = Instantiate(prefab, _motion.transform, false);
                RenderPath = "prefab(" + form + ")";
            }
            else if (useProceduralModels && FormRenderResources.LoadIfsShaders())
            {
                var renderer = FormRenderers.For(RenderPlan);
                _model = renderer.CreateModel(RenderPlan);
                foreach (var r in _model.GetComponentsInChildren<Renderer>())   // 로더가 만든 머티리얼 = 이미 사본
                    foreach (var m in r.sharedMaterials) _ownedMaterials.Add(m);
                _model.transform.SetParent(_motion.transform, false);
                _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
                RenderPath = renderer.Name;
                Note($"form.type={form}: 프리팹이 연결되지 않아 기본 절차 모형(IFS 셰이더)으로 표시", false);
                if (RenderPlan.PresetNote != null) Note(RenderPlan.PresetNote, false);
                if (renderer.Name == FormRenderers.MistLegacyName)
                    Note("form.type=mist: 안개 셰이더(Resources/" + FormRenderResources.MistShaderResource +
                         ")를 쓸 수 없어 이전 경로(구 + Fade 셰이더)로 표시", true);
            }
            else
            {
                _model = CreatePrimitive(form);
                _model.transform.SetParent(_motion.transform, false);
                _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
                RenderPath = "primitive(" + form + ")";
                string why = useProceduralModels ? FormRenderResources.IfsShaderProblem() : "useProceduralModels가 꺼져 있음";
                Note($"form.type={form}: 프리팹이 연결되지 않아 임시 프리미티브로 대체 — 이유: {why}", true);
            }
            _model.name = "model (" + form + ")";
            _modelBaseScale = _model.transform.localScale;
        }

        // 모양 모형: 연결된 프리팹이 있으면 그것, 없으면 메뉴와 같은 함수(ShapeModelFactory)로 같은 형상을 코드로 만든다.
        // 어느 쪽이든 구로 몰래 바꾸지 않는다. 크기는 절차 모형과 같은 기본 크기(primitiveBaseSize)로 맞춰 layout.size의 뜻을 유지한다.
        void BuildShapeModel(string form)
        {
            string shape = Shape.Applied, model = Shape.Model;
            bool ifs = FormRenderResources.LoadIfsShaders();   // 프리팹 머티리얼이 IFS 셰이더인지 ApplyMaterial이 알아보려면 셰이더를 먼저 읽어야 한다
            var prefab = FindShapePrefab(shape);
            if (prefab != null)
            {
                _model = Instantiate(prefab, _motion.transform, false);
                Shape.ViaPrefab = true;
                RenderPath = "shapePrefab(" + model + ")";
            }
            else
            {
                if (ifs)
                {
                    var renderer = FormRenderers.For(RenderPlan);
                    _model = renderer.CreateModel(RenderPlan);
                    foreach (var r in _model.GetComponentsInChildren<Renderer>())
                        foreach (var m in r.sharedMaterials) if (m != null) _ownedMaterials.Add(m);
                    RenderPath = renderer.Name;
                }
                else
                {
                    _model = ShapeModelFactory.Create(model, null, FormRenderResources.ConeMesh());
                    RenderPath = "shapeModelPrimitive(" + model + ")";
                }
                _model.transform.SetParent(_motion.transform, false);
                Shape.ViaPrefab = false;
                Note($"shape={shape} → {model}: 모양 프리팹이 연결되지 않아 같은 형상을 코드로 만듦" +
                     " (메뉴 IFS ▸ Create Shape Prefabs로 연결)", true);
                if (!ifs)
                    Note($"shape={shape} → {model}: IFS 셰이더를 쓸 수 없어 프리미티브 기본 머티리얼로 표시 — 이유: {FormRenderResources.IfsShaderProblem()}", true);
            }
            _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
            _model.name = "model (" + form + ", shape " + shape + " → " + model + ")";
            _modelBaseScale = _model.transform.localScale;
            _isShapeModel = true;
            Note($"shape={shape} → {model} 모형으로 표시(form.type={form}, 트리거 " +
                 $"'{Shape.Words.Find(w => w.Status == ShapeMapping.StatusApplied)?.Trigger}', " +
                 (Shape.ViaPrefab == true ? "프리팹" : "코드 생성") + ")", false);
        }

        GameObject FindShapePrefab(string shape)
        {
            if (shapePrefabs == null) return null;
            foreach (var sp in shapePrefabs)
                if (sp != null && sp.shape == shape && sp.prefab != null) return sp.prefab;
            return null;
        }

        /// <summary>모양 프리팹 연결(에디터 메뉴·배치 캡처가 부른다). 다음 Load부터 쓴다.</summary>
        public void ConfigureShapePrefabs(IEnumerable<ShapePrefab> prefabs)
        {
            var list = new List<ShapePrefab>();
            if (prefabs != null)
                foreach (var p in prefabs)
                    if (p != null) list.Add(new ShapePrefab(p.shape, p.prefab));
            shapePrefabs = list.ToArray();
        }

        // 지금 값(CurrentParams)·처음 form.type·모양어 판정 → 렌더 계획. 매퍼 정보(meta.mapping)는 넘기지 않는다(X65).
        FormRenderPlan BuildPlan() => FormRenderPlan.Build(CurrentParams, InitialParams.GetCategory("form.type"), Shape);

        // 모양어마다 무엇을 했는지 콘솔·notes에 남긴다. 적용하지 못한 모양어(표에 없음·형태 때문·충돌)는 경고.
        void NoteShapeWords(string file, string sessionId)
        {
            string who = sessionId != null ? $"{file} (session {sessionId})" : file;
            foreach (var w in Shape.Words)
            {
                string at = $"shape={w.Shape ?? "(값 없음)"}, 트리거 '{w.Trigger}' [{Span(w.CharSpan)}]";
                switch (w.Status)
                {
                    case ShapeMapping.StatusUnmapped:
                        Note($"{who}: {at} — 모양 모형 표에 없는 모양어 → 모양 정보 없이 만든 모형을 그대로 씀(unmapped_shape)", true);
                        break;
                    case ShapeMapping.StatusNotAppliedForm:
                        Note($"{who}: {at} — spec이 form.type={Shape.FormType}을 말해 그 형태 모형을 지킴(not_applied_form)", true);
                        break;
                    case ShapeMapping.StatusConflict:
                        Note($"{who}: {at} — 앞서 적용한 shape={Shape.Applied}와 다른 모양어라 적용하지 않음(conflict)", true);
                        break;
                }
            }
        }

        static string Span(int[] s) => s == null ? "" : string.Join(",", s);

        // 형상만 바꿀 때(조정 중 form.type 변경): 이전 형상이 쓰던 머티리얼 사본도 함께 지운다.
        // 지우지 않으면 _ownedMaterials에 남아 Unload·OnDestroy 때까지 쌓인다.
        void ReleaseModel()
        {
            if (_model == null) return;
            foreach (var r in _model.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null && _ownedMaterials.Remove(m)) DestroySafe(m);
            DestroySafe(_model);
            _model = null;
        }

        /// <summary>로더가 지금 들고 있는 머티리얼 사본 수(누수 확인용).</summary>
        public int OwnedMaterialCount => _ownedMaterials.Count;

        GameObject FindPrefab(string form)
        {
            foreach (var fp in formPrefabs)
                if (fp != null && fp.formType == form && fp.prefab != null) return fp.prefab;
            return null;
        }

        static GameObject CreatePrimitive(string form)
        {
            switch (form)
            {
                case "shell":
                    return GameObject.CreatePrimitive(PrimitiveType.Capsule);
                case "fragments":
                {
                    var group = new GameObject("fragments");
                    Vector3[] offsets =
                    {
                        new Vector3(-0.35f, 0.1f, 0f), new Vector3(0.3f, -0.15f, 0.1f), new Vector3(0f, 0.35f, -0.1f),
                        new Vector3(0.15f, 0.05f, 0.35f), new Vector3(-0.1f, -0.3f, -0.25f),
                    };
                    for (int i = 0; i < offsets.Length; i++)
                    {
                        var c = GameObject.CreatePrimitive(PrimitiveType.Cube);
                        c.transform.SetParent(group.transform, false);
                        c.transform.localPosition = offsets[i];
                        c.transform.localRotation = Quaternion.Euler(17f * i, 31f * i, 11f * i);
                        c.transform.localScale = Vector3.one * 0.3f;
                    }
                    return group;
                }
                default:   // blob, mist
                    return GameObject.CreatePrimitive(PrimitiveType.Sphere);
            }
        }

        // ── 적용 ─────────────────────────────────────────────────────────────
        void ApplyAll()
        {
            if (_root == null || CurrentParams == null) return;
            ApplyLayout();
            ApplyMaterial();
            ApplyMotion();
        }

        void ApplyLayout()
        {
            var p = CurrentParams;
            float dist = Mathf.Lerp(placement.minDistance, placement.maxDistance, (float)p.GetNumber("layout.distance"));
            float y = placement.floorY + (float)p.GetNumber("layout.verticalOffset") * ParticipantHeight();
            var right = Vector3.Cross(Vector3.up, _anchorForward);
            var pos = _anchorPos + _anchorForward * (dist + extraOffset.z) + right * extraOffset.x;
            pos.y = y + extraOffset.y;
            _root.transform.position = pos;
            var look = _anchorPos - pos;
            look.y = 0f;
            _root.transform.rotation = look.sqrMagnitude > 1e-4f ? Quaternion.LookRotation(look.normalized, Vector3.up) : Quaternion.identity;

            float scale = (float)SceneParams.SizeToScale(p.GetNumber("layout.size"));
            string posture = p.GetCategory("form.posture");
            Vector3 deform = Vector3.one;
            if (posture != SceneParams.NoPosture && !PostureScale.TryGetValue(posture, out deform))
            {
                deform = Vector3.one;
                Note($"form.posture={posture}: 변형 프리셋이 없어 적용하지 않음", true);
            }
            _model.transform.localScale = Vector3.Scale(_modelBaseScale * scale, deform);
        }

        void ApplyMaterial()
        {
            // 색·Fade 판정은 변형본 생성기(색 변형 ΔE00)와 같은 함수(RenderedColor)를 쓴다(FormRenderPlan.Build 안).
            var plan = RenderPlan = BuildPlan();
            float opacity = plan.Opacity, brightness = plan.Brightness, roughness = plan.Roughness, erosion = plan.Erosion;
            var color = new Color(plan.ColorR, plan.ColorG, plan.ColorB, opacity);
            var sp = shaderParams;
            var formRenderer = FormRenderers.For(plan);

            foreach (var rend in _model.GetComponentsInChildren<Renderer>())
            {
                bool anyIfs = false;
                foreach (var m in InstanceMaterials(rend))   // 렌더러마다 인스턴스(공유 머티리얼을 바꾸지 않는다)
                {
                    // IFS 셰이더면 형상별 렌더러가 셰이더 선택·형상 프리셋을 넣는다
                    if (formRenderer.ApplyShader(m, plan)) anyIfs = true;
                    // 안개 셰이더: 바닥 높이(배치 설정) 아래의 밀도를 0으로(광선이 바닥을 뚫고 땅속 안개를 쌓지 않게)
                    if (m.HasProperty(MistFloorProperty)) m.SetFloat(MistFloorProperty, placement.floorY);
                    if (m.HasProperty(sp.baseColor)) m.SetColor(sp.baseColor, color);
                    else if (m.HasProperty(sp.colorFallback)) m.SetColor(sp.colorFallback, color);
                    else Note($"{m.shader.name}: 색 프로퍼티({sp.baseColor}) 없음", true);

                    if (m.HasProperty(sp.brightness)) m.SetFloat(sp.brightness, brightness);
                    else if (m.HasProperty(sp.emissionFallback))
                    {
                        m.EnableKeyword("_EMISSION");
                        m.SetColor(sp.emissionFallback, color * (brightness * 0.6f));
                        Note($"{m.shader.name}: {sp.brightness} 없음 → 발광({sp.emissionFallback})으로 근사", true);
                    }
                    else Note($"{m.shader.name}: 밝기 프로퍼티 없음 → material.brightness 적용 안 됨", true);

                    if (m.HasProperty(sp.roughness)) m.SetFloat(sp.roughness, roughness);
                    else if (m.HasProperty(sp.smoothnessFallback)) m.SetFloat(sp.smoothnessFallback, 1f - roughness);
                    else if (m.HasProperty(sp.glossinessFallback)) m.SetFloat(sp.glossinessFallback, 1f - roughness);
                    else Note($"{m.shader.name}: 거칠기 프로퍼티 없음", true);

                    if (m.HasProperty(sp.opacity)) m.SetFloat(sp.opacity, opacity);
                    else if (opacity < 0.999f)
                        Note($"{m.shader.name}: {sp.opacity} 없음 → 색의 알파로만 넣음(불투명 셰이더면 보이지 않음)", true);

                    if (m.HasProperty(sp.erosion)) m.SetFloat(sp.erosion, erosion);
                    else if (erosion > 0.001f) Note($"{m.shader.name}: {sp.erosion} 없음 → material.erosion 적용 안 됨", true);
                }
                // 그림자는 렌더러가 정한다(반투명·안개는 끔).
                if (anyIfs) rend.shadowCastingMode = formRenderer.Shadow(plan);
            }
        }

        // renderer.materials와 같은 일(공유 머티리얼을 사본으로 바꿈)을 재생 중·에디트 모드 모두에서 한다.
        // 로더가 직접 만든 머티리얼(절차 모형)은 이미 사본이라 그대로 쓴다.
        Material[] InstanceMaterials(Renderer rend)
        {
            var shared = rend.sharedMaterials;
            bool changed = false;
            for (int i = 0; i < shared.Length; i++)
            {
                if (shared[i] == null || _ownedMaterials.Contains(shared[i])) continue;
                shared[i] = new Material(shared[i]);
                _ownedMaterials.Add(shared[i]);
                changed = true;
            }
            if (changed) rend.sharedMaterials = shared;
            return shared;
        }

        static void DestroySafe(UnityEngine.Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }

        void ApplyMotion()
        {
            string type = CurrentParams.GetCategory("motion.type");
            if (!_motion.Configure(type, (float)CurrentParams.GetNumber("motion.speed")))
                Note($"motion.type={type}: 움직임 묶음이 없어 정지로 둠", true);
        }

        // ── 기록 도우미 ─────────────────────────────────────────────────────
        void Note(string message, bool warn)
        {
            if (_notes.Contains(message)) return;   // 같은 내용은 한 번만
            _notes.Add(message);
            if (warn) Debug.LogWarning("[SceneLoader] " + message, this);
            else Debug.Log("[SceneLoader] " + message, this);
        }

        static string Describe(SceneParams p, string key) =>
            p.IsNumeric(key) ? ExperimentRecorder.FormatNumber(p.GetNumber(key)) : p.GetCategory(key);
    }
}
