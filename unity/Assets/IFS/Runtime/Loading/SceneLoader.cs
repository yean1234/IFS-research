// SceneSpec v2 JSON → VR 오브젝트.
//   form.type      → 프리팹 4종(blob/mist/shell/fragments). 비어 있으면 기본 절차 모형(잘게 나눈 구 + IFS 셰이더,
//                    형태별 프리셋). IFS 셰이더를 못 쓰는 환경이면 임시 프리미티브(로그 + initialScene notes)
//                    형상별 모형은 FormRenderPlan(슬롯 값 → 렌더러 입력) + IFormRenderer(Runtime/Rendering)가 만든다(X64)
//   _unmapped 모양어 → 모양 모형(round 구 · square 큐브 · flat 납작 원기둥 · pointed 원뿔, ShapeMapping).
//                    form.type이 null·blob일 때만. 표에 없는 모양어는 경고하고 unmapped_shape로 기록(구로 바꾸지 않음).
//                    판정은 initialScene.json·report.json의 "shape"(docs/shape-mapping.md)
//   (2.3) form.roundness → 슈퍼쿼드릭 메시(기본 덩어리 경로만), form.aspect → 국소 축 배율, material.emission → _IfsEmission
//                    (적용 순서·기록은 FormRenderPlan, docs/scene-spec-mapping.md 8.4절. 세 값이 모두 null이면 2.2와 같은 경로)
//   (2.4) layout.proportions → x·y·z 비율(G72, ProportionsRender): 메시 형상은 국소 배율, fragments는 조각 배치, 생성 메시는 늘인 뒤 균일 맞춤.
//                    가장 긴 변은 layout.size가 정한다(비율을 바꿔도 그대로). 비율이 주어지면 form.aspect 축 비율을 쓰지 않는다(기록에는 남김)
//   material.*     → Shader Graph 파라미터(_BaseColor, _Brightness, _Roughness, _Opacity, _Erosion)
//   layout.*       → Transform(거리·높이·크기), form.posture → 크기 변형 프리셋
//   motion.*       → SpecMotion(절차적 움직임)
// null 값은 SceneDefaults로 채우고, 어떤 값을 기본값으로 썼는지 콘솔과 initialScene.json(defaultsUsed)에 남긴다.
// _inferred(3층 제안)는 useInferredSuggestions를 켜야만 쓴다(기본 꺼짐 — 말하지 않은 것을 추론하지 않는다).
// 참여자 조정은 SetNumber/SetCategory로 → events.csv 한 줄씩, SaveFinal()로 finalScene.json.
// 소유감 실험 변형본은 Load(path, SceneOverride): 해석값 덮어쓰기·모양 모형 강제, 기록(RecordChange) 없음. Load(path)는 그대로.
// 파일을 읽을 수 없는 곳(WebGL 미리보기)은 LoadJson(json, 이름, 덮어쓰기): 파일 로드와 같은 파싱·해석·렌더 경로(LoadParsed)를 탄다.
// G62 생성 형태 메시: 로드한 뒤 ApplyFormAsset(GLB 메시)으로 절차 모형의 메시만 바꾼다. 크기는 같은 layout.size에서 절차 모형의
//                    가장 긴 변과 같게(FormAssetFit), 중심은 절차 모형의 중심에. 머티리얼·그림자·움직임은 절차 모형의 것(스펙 값)을 그대로 쓴다.
//                    형상을 다시 만들면(form.type 조정 등) 생성 메시는 버리고 절차 모형으로 돌아간다.
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
        [Tooltip("프리미티브 대체 때 기본 크기(m). 프리팹은 프리팹 자체 크기를 기본(×1)으로 쓴다")] public float primitiveBaseSize = (float)RenderedSize.NominalBaseDiameterM;
    }

    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/SceneSpec Loader")]
    public sealed class SceneLoader : MonoBehaviour
    {
        // 자세어 → 크기 변형(x, y, z 배율). 표는 RenderedSize.PostureTable(생성기와 공유). 표에 없는 자세는 적용하지 않고 기록한다.
        public static readonly Dictionary<string, Vector3> PostureScale = BuildPostureScale();

        static Dictionary<string, Vector3> BuildPostureScale()
        {
            var d = new Dictionary<string, Vector3>();
            foreach (var kv in RenderedSize.PostureTable) d[kv.Key] = new Vector3((float)kv.Value.x, (float)kv.Value.y, (float)kv.Value.z);
            return d;
        }

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
        /// <summary>안개 셰이더(_FloorY가 있는 머티리얼)를 쓸 때 안개 구가 바닥 아래로 걸치는가(지금 배치 기준). 안개 셰이더가 아니면 null.
        /// report.json의 mistFloor. 잘렸으면 로드 때 notes에도 남긴다(화면 처리는 바꾸지 않는다).</summary>
        public MistFloorClip MistFloor { get; private set; }
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
        // G62: 생성 형태 메시(없으면 null = 절차 모형). 맞춤 계산과 만든 메시(정리용)
        FormAsset.FormAssetFit _assetFit;
        Mesh _assetMesh;
        /// <summary>G62: 지금 생성 형태 메시를 그리고 있는가.</summary>
        public bool ShowingFormAsset => _assetFit != null;
        /// <summary>G62: 마지막 배치에서 생성 메시의 균일 배율·가장 긴 변(m)과 같은 배율의 절차 모형 가장 긴 변(m). 생성 메시가 없으면 null.</summary>
        public double? FormAssetScale { get; private set; }
        public double? FormAssetLongestEdgeM { get; private set; }
        public double? FormAssetProceduralLongestEdgeM { get; private set; }
        /// <summary>(2.4) 생성 메시의 국소 배율(x, y, z) = 비율 × 균일 배율(비율이 없으면 셋 다 FormAssetScale). 생성 메시가 없으면 null.</summary>
        public double[] FormAssetScaleVector { get; private set; }
        /// <summary>(2.4) 마지막 배치에서 비율을 넣기 전 가장 긴 변(m, 모형 국소 경계 × 국소 배율). 비율이 주어지지 않으면 null.
        /// 가장 긴 변 규칙으로 비율을 넣은 뒤의 가장 긴 변도 이 값이다.</summary>
        public double? ProportionsLongestEdgeM { get; private set; }
        // (2.4) 가장 긴 변 규칙에 쓰는 모형 국소 경계: 0 = 비율을 넣지 않은 메시, 1 = 지금 메시(형상을 다시 만들면 비움)
        double[] _propSize0, _propSize1;

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
#if UNITY_WEBGL && !UNITY_EDITOR
            // WebGL 플레이어는 파일 시스템(StreamingAssets 포함)을 File.ReadAllText로 읽을 수 없다. JSON 문자열을 LoadJson으로 넘긴다.
            Debug.LogError($"[SceneLoader] WebGL에서는 파일 경로로 읽지 않습니다(LoadJson 사용): {full}", this);
            return false;
#else
            string raw;
            try
            {
                raw = File.ReadAllText(full, Encoding.UTF8);
            }
            catch (Exception e)
            {
                Debug.LogError($"[SceneLoader] SceneSpec을 읽지 못했습니다: {full}\n{e.Message}", this);
                return false;
            }
            return LoadParsed(raw, full, Path.GetFileName(full), variant);
#endif
        }

        /// <summary>파일 대신 JSON 문자열로 로드한다(WebGL 미리보기 등 파일을 읽을 수 없는 곳). 파싱·검사·해석·렌더는 Load(path)와 같은 경로를 탄다.
        /// sourceName은 기록·로그·notes에 파일 이름 자리로 쓰는 이름이다(파일 로드와 같은 notes를 내려면 같은 파일 이름을 준다).
        /// 기록을 켜 두면 세션 id가 없을 때 sourceName(확장자 뺌)을 세션 id로 쓴다. SpecPath는 null이다.</summary>
        public bool LoadJson(string json, string sourceName = "inline.json", SceneOverride variant = null)
        {
            if (string.IsNullOrEmpty(sourceName)) sourceName = "inline.json";
            if (json == null)
            {
                Debug.LogError($"[SceneLoader] SceneSpec을 읽지 못했습니다: {sourceName}\nJSON 문자열이 null입니다.", this);
                return false;
            }
            return LoadParsed(json, null, sourceName, variant);
        }

        // 파일·문자열 공통: 파싱 → 형식 검사 → 덮어쓰기 확인 → 해석 → 렌더 → (기록). full = 파일 전체 경로(문자열 로드면 null).
        bool LoadParsed(string raw, string full, string fileName, SceneOverride variant)
        {
            SceneSpecV2 spec;
            try
            {
                spec = SceneSpecJson.Parse(raw);
            }
            catch (Exception e)
            {
                Debug.LogError($"[SceneLoader] SceneSpec을 읽지 못했습니다: {full ?? fileName}\n{e.Message}", this);
                return false;
            }
            foreach (var problem in SceneSpecJson.Validate(spec))
                Debug.LogWarning($"[SceneLoader] 형식 경고({fileName}): {problem}", this);
            if (variant != null && !CheckVariant(spec, variant, fileName)) return false;

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
            Shape = ShapeMapping.Resolve(spec, variant);   // 덮어쓴 form.type으로 판정(mist 덮어쓰기면 모양 모형 없음)
            if (variant?.ShapeModel != null)
            {
                Shape = ShapeMapping.Forced(Shape, variant.ShapeModel);
                Note($"변형 덮어쓰기(기록 안 함): 모양 모형 강제 → {Shape.Model}", false);
            }
            NoteShapeWords(fileName, spec.Meta.SessionId);
            NoteContourDefaults();
            NoteProportions();

            CaptureAnchor();
            BuildHierarchy();
            ApplyAll();
            if (MistFloor != null && MistFloor.FloorClipped) Note(MistFloor.Note(), false);

            if (record)
            {
                var sessionId = spec.Meta.SessionId ?? Path.GetFileNameWithoutExtension(fileName);
                // 문자열 로드면 specPath 자리에 "(json) 이름"을 남긴다(파일 경로가 아님을 구분)
                _recorder = new ExperimentRecorder(RecordRoot, sessionId, spec, full ?? "(json) " + fileName);
                // (2.3) 윤곽·발광 기록은 2.3 spec(또는 덮어쓰기로 정함)일 때만(처음 로드한 값의 계획 = 지금 계획)
                _recorder.WriteInitial(InitialParams, raw, _notes, Shape.ToJson(), RenderPlan?.ContourJson(), RenderPlan?.EmissionJson());
                Debug.Log($"[SceneLoader] 기록 폴더: {_recorder.Directory}", this);
            }
            Debug.Log($"[SceneLoader] {fileName} 로드: form={CurrentParams.GetCategory("form.type")}, " +
                      $"기본값 {InitialParams.DefaultsUsed.Count}개, shape={Shape.Status}" +
                      (Shape.Model != null ? $"({Shape.Applied} → {Shape.Model})" : ""), this);
            Loaded?.Invoke(this);
            return true;
        }

        public void Unload()
        {
            CloseRecorder();
            _assetFit = null;
            FormAssetScale = FormAssetLongestEdgeM = FormAssetProceduralLongestEdgeM = null;
            if (_assetMesh != null) { DestroySafe(_assetMesh); _assetMesh = null; }
            DestroySafe(_root);
            foreach (var m in _ownedMaterials) DestroySafe(m);
            _ownedMaterials.Clear();
            _root = _model = null;
            _motion = null;
            _isShapeModel = false;
            RenderPlan = null;
            RenderPath = null;
            MistFloor = null;
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

        // 덮어쓰기를 확인한다(로드 전, 지금 형상을 지우기 전에). 모르는 키·모형, blob이 아닌 형태에 모양 모형을 강제하면 오류.
        // (G73 후속) spec의 모양어가 정한 모형은 덮어쓴 form.type으로 다시 판정한다: 'form.type=mist' 덮어쓰기 + 모양어 '동그란'은
        // 오류가 아니라 안개를 그린다(모양어는 not_applied_form). 예전에는 오류로 거부해 미리보기가 글 요약으로 내려가고
        // 헤드셋 러너도 시작하지 않았다.
        bool CheckVariant(SceneSpecV2 spec, SceneOverride variant, string file)
        {
            var errors = variant.Validate();
            if (errors.Count == 0)
            {
                var check = SceneParams.FromSpec(spec, defaults, useInferredSuggestions);
                variant.ApplyTo(check);
                string model = variant.ShapeModel ?? ShapeMapping.Resolve(spec, variant).Model;
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
            // (2.4) fragments 절차 메시는 조각 배치에 비율이 들어 있다 → 비율을 바꾸면 메시를 다시 만든다(생성 메시는 배율로만)
            if (ProportionsRender.IsAxisKey(key) && StretchedMeshPath && _assetFit == null) BuildHierarchy();
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
            if (key == "form.type" || key == SceneParams.BaseKey || key == ContourRender.RoundnessKey || key == MistKinds.Key) BuildHierarchy();
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
            if (RenderPlan.BaseShape != null && BuildBaseShape()) return;
            if (RenderPlan.Renderer == FormRenderPlan.RendererSuperquadric && BuildSuperquadric()) return;
            if (RenderPlan.BaseRequested != null && RenderPlan.BaseStatus != FormRenderPlan.BaseApplied)
                Note($"form.base={RenderPlan.BaseRequested}: 그리지 않음({RenderPlan.BaseStatus}" +
                     (RenderPlan.BaseStatus == FormRenderPlan.BaseNotAppliedForm ? $" — form.type={form}의 형태 모형을 지킴" :
                      RenderPlan.BaseStatus == FormRenderPlan.BaseNoMesh ? " — 이 빌드에 메시가 없음" : "") + ")", true);

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

        // (2.2) 기본 형상: 프리팹을 쓰지 않고 절차 메시(BaseShapeMesh)로만 만든다(blob 프리팹이 연결돼 있어도 기본 형상이 앞선다).
        // IFS 셰이더를 쓸 수 없으면 false → 형태(form.type) 경로로 그리고 그 사실을 남긴다.
        bool BuildBaseShape()
        {
            if (!useProceduralModels || !FormRenderResources.LoadIfsShaders())
            {
                Note($"form.base={RenderPlan.BaseShape}: IFS 셰이더를 쓸 수 없어 기본 형상을 그리지 못함 — " +
                     (useProceduralModels ? FormRenderResources.IfsShaderProblem() : "useProceduralModels가 꺼져 있음"), true);
                return false;
            }
            var renderer = FormRenderers.For(RenderPlan);
            _model = renderer.CreateModel(RenderPlan);
            foreach (var r in _model.GetComponentsInChildren<Renderer>())
                foreach (var m in r.sharedMaterials) if (m != null) _ownedMaterials.Add(m);
            _model.transform.SetParent(_motion.transform, false);
            _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
            RenderPath = renderer.Name;
            if (RenderPlan.PresetNote != null) Note(RenderPlan.PresetNote, false);
            _model.name = "model (base " + RenderPlan.BaseShape + ")";
            _modelBaseScale = _model.transform.localScale;
            return true;
        }

        // (2.3) 슈퍼쿼드릭(form.roundness, 기본 덩어리 경로): 기본 형상처럼 프리팹을 쓰지 않고 절차 메시로만 만든다
        // (blob 프리팹이 연결돼 있어도 말한 윤곽이 앞선다). IFS 셰이더를 쓸 수 없으면 false → 형태 경로로 그리고 그 사실을 남긴다.
        bool BuildSuperquadric()
        {
            if (!useProceduralModels || !FormRenderResources.LoadIfsShaders())
            {
                Note($"form.roundness={RenderPlan.Roundness}: IFS 셰이더를 쓸 수 없어 슈퍼쿼드릭 메시를 그리지 못함 — " +
                     (useProceduralModels ? FormRenderResources.IfsShaderProblem() : "useProceduralModels가 꺼져 있음"), true);
                return false;
            }
            var renderer = FormRenderers.For(RenderPlan);
            _model = renderer.CreateModel(RenderPlan);
            foreach (var r in _model.GetComponentsInChildren<Renderer>())
                foreach (var m in r.sharedMaterials) if (m != null) _ownedMaterials.Add(m);
            _model.transform.SetParent(_motion.transform, false);
            _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
            RenderPath = renderer.Name;
            if (RenderPlan.PresetNote != null) Note(RenderPlan.PresetNote, false);
            _model.name = "model (" + RenderPlan.FormType + ", contour " + RenderPlan.Roundness + ")";
            _modelBaseScale = _model.transform.localScale;
            return true;
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
                    case ShapeMapping.StatusNotAppliedBase:
                        Note($"{who}: {at} — spec이 기본 형상 form.base={Spec?.Form?.Base}를 말해 기본 형상이 윤곽을 정함(not_applied_base)", false);
                        break;
                    case ShapeMapping.StatusConflict:
                        Note($"{who}: {at} — 앞서 적용한 shape={Shape.Applied}와 다른 모양어라 적용하지 않음(conflict)", true);
                        break;
                }
            }
        }

        static string Span(int[] s) => s == null ? "" : string.Join(",", s);

        // (2.3) 윤곽을 그린 경로 때문에 기본값으로 정한 것(긴 축 방향, 말하지 않은 둥긂·길쭉함)을 defaultsUsed·notes에 남긴다.
        // 처음 값(InitialParams)의 계획으로 정한다. 2.0–2.2 spec과 세 슬롯이 모두 null인 2.3 spec은 아무것도 더하지 않는다.
        void NoteContourDefaults()
        {
            if (!InitialParams.HasContourSlots) return;
            var plan = FormRenderPlan.Build(InitialParams, InitialParams.GetCategory("form.type"), Shape);
            foreach (var key in plan.ContourDefaultsUsed)
            {
                if (!InitialParams.DefaultsUsed.Contains(key)) InitialParams.DefaultsUsed.Add(key);
                if (!CurrentParams.DefaultsUsed.Contains(key)) CurrentParams.DefaultsUsed.Add(key);
                Note(key == ContourRender.AspectAxisKey
                    ? $"{key}: 길쭉함·납작함의 긴 축 방향을 말하지 않음 → 기본값 세로({ContourRender.AspectAxisDefault})"
                    : $"{key}: SceneSpec 값이 null → 기본값으로 그림({(key == ContourRender.AspectKey ? "축 배율 (1, 1, 1)" : "기본 덩어리 메시")})", false);
            }
            // 매퍼는 윤곽어('각진'·'길쭉한')를 v0 모양어(_unmapped category shape)로도 남긴다 — 모양 모형 표에 없어 unmapped_shape 경고가
            // 나지만 윤곽 슬롯이 그 말을 그렸음을 함께 적는다(경고 문장 자체는 2.2와 같게 둔다)
            if (plan.ContourStatus == ContourRender.StatusApplied && Shape.Words.Exists(w => w.Status == ShapeMapping.StatusUnmapped))
                Note($"모양 모형 표에 없는 모양어({string.Join(", ", Shape.Words.FindAll(w => w.Status == ShapeMapping.StatusUnmapped).ConvertAll(w => w.Shape ?? "값 없음"))})가 있지만 " +
                     $"스펙 2.3 윤곽 슬롯(form.roundness={plan.Roundness ?? "null"}, form.aspect={plan.Aspect ?? "null"})으로 윤곽을 그림", false);
            if (plan.ContourStatus != ContourRender.StatusApplied && plan.ContourStatus != ContourRender.StatusNone)
                Note($"form.roundness={plan.Roundness ?? "null"}, form.aspect={plan.Aspect ?? "null"}: 윤곽을 그리지 않음({plan.ContourStatus}" +
                     (plan.ContourStatus == ContourRender.StatusNotAppliedModel ? $" — 모양 모형 {plan.ShapeModel}을 지킴" :
                      plan.ContourStatus == ContourRender.StatusNotAppliedBase ? $" — 기본 형상 {plan.BaseShape}이 윤곽을 정함" :
                      $" — form.type={plan.FormType}의 형태 모형을 지킴") + ")", false);
        }

        // (2.4) x·y·z 비율을 defaultsUsed·notes에 남긴다(처음 값 기준). 긴 축 방향을 말하지 않았으면(axisSaid = false) layout.proportions.axis.
        // 비율 슬롯이 없거나(2.0–2.3 spec, 덮어쓰기 없음) 비율이 주어지지 않으면(2.4 spec null — 기본값 메모만) 아무것도 더하지 않는다.
        void NoteProportions()
        {
            if (!InitialParams.HasProportionsSlot || !InitialParams.ProportionsGiven) return;
            var plan = FormRenderPlan.Build(InitialParams, InitialParams.GetCategory("form.type"), Shape);
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            string V(double[] v) => "(" + string.Join(", ", Array.ConvertAll(v, x => Math.Round(x, 4).ToString(inv))) + ")";
            if (InitialParams.SpecProportionsAxisSaid == false)
            {
                foreach (var p in new[] { InitialParams, CurrentParams })
                    if (!p.DefaultsUsed.Contains(ProportionsRender.AxisKey)) p.DefaultsUsed.Add(ProportionsRender.AxisKey);
                Note($"{ProportionsRender.AxisKey}: 긴 축·짧은 축 방향을 말하지 않음 → 기준 틀(길쭉하면 세로 y가 긺, 납작하면 세로 y가 짧음)로 그림", false);
            }
            Note($"{ProportionsRender.Key}: x·y·z 비율 {V(plan.Proportions)}(원값 {V(plan.ProportionsRaw)}) — " +
                 (plan.ProportionsMethod == ProportionsRender.MethodFragmentDistribution ? "조각 배치를 늘임" : "국소 배율") +
                 $", 가장 긴 변은 layout.size가 정함(규칙 {ProportionsRender.RuleVersion})", false);
            if (plan.ProportionsClamped)
                Note($"{ProportionsRender.Key}: 원값 / 가장 큰 원값이 {ProportionsRender.Min.ToString(inv)} 아래인 축을 {ProportionsRender.Min.ToString(inv)}로 올림", true);
            if (plan.AspectSuperseded)
                Note($"form.aspect={plan.Aspect}: x·y·z 비율(layout.proportions)이 앞서 축 비율을 쓰지 않음(값은 기록에 남김)", false);
        }

        // 형상만 바꿀 때(조정 중 form.type 변경): 이전 형상이 쓰던 머티리얼 사본도 함께 지운다.
        // 지우지 않으면 _ownedMaterials에 남아 Unload·OnDestroy 때까지 쌓인다.
        void ReleaseModel()
        {
            _assetFit = null;
            FormAssetScale = FormAssetLongestEdgeM = FormAssetProceduralLongestEdgeM = null;
            FormAssetScaleVector = null;
            _propSize0 = _propSize1 = null;
            if (_assetMesh != null) { DestroySafe(_assetMesh); _assetMesh = null; }
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
            RenderPlan = BuildPlan();   // (2.3) 축 비율(form.aspect)을 ApplyLayout이 지금 값으로 읽도록 먼저 계획을 갱신(ApplyMaterial이 다시 만든다 — 같은 계획)
            ApplyLayout();
            ApplyMaterial();
            ApplyMotion();
            MeasureMistFloor();
        }

        // 안개 셰이더는 바닥 높이 아래 밀도를 0으로 자른다 → 레이마칭 구(물체 좌표 반지름 MistRadius)가 바닥 아래로 걸치는지 기록만 한다.
        // 구의 세계 세로 반높이 = 반지름 × 물체→세계 행렬 y행(선형 부분)의 길이(회전·비균일 배율에도 정확).
        void MeasureMistFloor()
        {
            MistFloor = null;
            foreach (var rend in _model.GetComponentsInChildren<Renderer>())
            {
                bool mist = false;
                foreach (var m in rend.sharedMaterials) if (m != null && m.HasProperty(MistFloorProperty)) mist = true;
                if (!mist) continue;
                var w = rend.transform.localToWorldMatrix;
                double half = FormRenderResources.MistRadius * Math.Sqrt((double)w.m10 * w.m10 + (double)w.m11 * w.m11 + (double)w.m12 * w.m12);
                var clip = MistFloorClip.Measure(w.m13, half, placement.floorY);
                if (MistFloor == null || clip.ClippedHeightFraction > MistFloor.ClippedHeightFraction) MistFloor = clip;
            }
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

            // 배율·자세 배율은 생성기(크기 쌍의 화면 폭)와 같은 함수(RenderedSize)를 쓴다.
            float scale = (float)SceneParams.SizeToScale(p.GetNumber("layout.size"));
            string posture = p.GetCategory("form.posture");
            if (!RenderedSize.PostureDeform(posture, out double dx, out double dy, out double dz))
                Note($"form.posture={posture}: 변형 프리셋이 없어 적용하지 않음", true);
            var deform = new Vector3((float)dx, (float)dy, (float)dz);
            var local = Vector3.Scale(_modelBaseScale * scale, deform);
            // (2.3) form.aspect: 축 비율 (x, y, z)를 형상 국소 배율에 곱한다(긴 축 = 1, layout.size 뜻 그대로). 적용하지 않으면 곱하지 않는다
            var axis = RenderPlan?.AxisRatios;
            if (axis != null) local = Vector3.Scale(local, new Vector3((float)axis[0], (float)axis[1], (float)axis[2]));
            // (2.4) x·y·z 비율(유효 값, 가장 큰 값 = 1). 주어지지 않으면 null → 아래는 2.3과 같은 경로
            var prop = RenderPlan?.Proportions;
            ProportionsLongestEdgeM = null;
            if (_assetFit != null)
            {
                // G62: 생성 메시는 같은 배율의 절차 모형과 가장 긴 변이 같도록 균일 배율, 중심은 절차 모형의 중심(자세·축 비율로 늘이지 않음).
                // (2.4) 비율이 있으면 생성 메시를 비율로 늘인 뒤 균일 배율로 같은 가장 긴 변에 맞춘다(비율은 가장 긴 변을 바꾸지 않음)
                _assetFit.Place(new double[] { local.x, local.y, local.z }, prop, out double[] g, out double u, out double[] at, out double lp, out double lr);
                _model.transform.localScale = prop == null ? Vector3.one * (float)u : new Vector3((float)g[0], (float)g[1], (float)g[2]);
                _model.transform.localPosition = new Vector3((float)at[0], (float)at[1], (float)at[2]);
                FormAssetScale = u;
                FormAssetScaleVector = g;
                FormAssetLongestEdgeM = lr;
                FormAssetProceduralLongestEdgeM = lp;
                if (prop != null) ProportionsLongestEdgeM = lp;
                return;
            }
            if (prop != null) local = FitProportions(local, prop);
            _model.transform.localScale = local;
        }

        /// <summary>(2.4) 가장 긴 변 규칙(ProportionsRender.FitLocalScale): 비율 전 국소 배율 local0 → 비율을 넣은 국소 배율.
        /// 메시 형상은 국소 배율에 p를 곱하고(q = p), fragments 절차 메시는 조각 배치에 이미 p가 들어 있어 q = (1, 1, 1).
        /// 어느 쪽이든 균일 배율 L0 / L1로 가장 긴 변을 비율 전과 같게 둔다. 경계는 정점으로 잰다(ProceduralLocalBounds).</summary>
        Vector3 FitProportions(Vector3 local0, double[] p)
        {
            bool stretchedMesh = StretchedMeshPath;
            if (_propSize1 == null) _propSize1 = ProceduralLocalBounds(out _, out double[] s1) ? s1 : new[] { 1.0, 1.0, 1.0 };
            if (_propSize0 == null)
            {
                if (RenderPath == FormRenderPlan.RendererMistDust) DustMesh.Bounds(RenderPlan.DustSeed, RenderPlan.DustGrains, null, out _, out _propSize0);
                else if (stretchedMesh) FragmentMesh.Bounds(RenderPlan.FragmentSeed, RenderPlan.FragmentPieces, null, out _, out _propSize0);
                else _propSize0 = _propSize1;
            }
            var q = stretchedMesh ? new[] { 1.0, 1.0, 1.0 } : p;
            var r = ProportionsRender.FitLocalScale(_propSize0, _propSize1, new double[] { local0.x, local0.y, local0.z }, q, out double l0, out _);
            ProportionsLongestEdgeM = l0;
            return new Vector3((float)r[0], (float)r[1], (float)r[2]);
        }

        /// <summary>(2.4) 절차 메시 안에 비율이 들어 있는 경로(fragments 조각 배치, (G74) mistDust 알갱이 자리) — 비율을 바꾸면 메시를 다시 만든다.</summary>
        bool StretchedMeshPath => RenderPath == FormRenderPlan.RendererFragments || RenderPath == FormRenderPlan.RendererMistDust;

        /// <summary>물체 자기 틀(모형 국소 축: 너비 x · 높이 y · 깊이 z)의 경계 상자 크기(m). 정점 경계(셰이더 정점 변위 전) × 모형의 세계 배율.
        /// 안개(부피 셰이더)는 레이마칭 구(지름 2 × MistRadius) × 배율 — 밀도는 그 안쪽에서 풀리므로 상한. 움직임을 적용하기 전(로드 직후)에 부른다.
        /// 모형이 없거나 메시가 없으면 null.</summary>
        public double[] ObjectLocalBoundsM()
        {
            if (_model == null) return null;
            double[] size;
            if (RenderPath == FormRenderPlan.RendererMist) size = new double[] { 2 * FormRenderResources.MistRadius, 2 * FormRenderResources.MistRadius, 2 * FormRenderResources.MistRadius };
            else if (!ProceduralLocalBounds(out _, out size)) return null;
            var s = _model.transform.lossyScale;
            return new[] { size[0] * Math.Abs(s.x), size[1] * Math.Abs(s.y), size[2] * Math.Abs(s.z) };
        }

        /// <summary>G62: 로드한 형상(절차 모형)의 메시를 생성 형태 메시로 바꾼다. 머티리얼(스펙 값으로 만든 것)·그림자·움직임은 절차 모형의 것을
        /// 그대로 쓰고 GLB의 머티리얼은 쓰지 않는다(읽지도 않음). 바꾸지 못하면 절차 모형을 그대로 두고 이유를 돌려준다.
        /// 크기 기록(가장 긴 변·배율)은 결과에 담는다. 렌더 경로(RenderPath)는 "generated(assetId)"가 된다.</summary>
        public FormAsset.FormAssetResult ApplyFormAsset(FormAsset.FormAssetRef asset, FormAsset.GlbMesh mesh)
        {
            var res = new FormAsset.FormAssetResult { Ref = asset, ProceduralRenderPath = RenderPath, RenderPath = RenderPath };
            if (_model == null || CurrentParams == null || RenderPlan == null)
                return Fail(res, FormAsset.FormAssetResult.NotLoaded, null);
            if (RenderPlan.Renderer == FormRenderPlan.RendererMist || RenderPlan.Renderer == FormRenderPlan.RendererMistDust)
                return Fail(res, FormAsset.FormAssetResult.MistForm, "안개(부피 셰이더·알갱이)는 생성 메시로 그리지 않음");
            if (!ProceduralLocalBounds(out double[] pc, out double[] ps))
                return Fail(res, FormAsset.FormAssetResult.NoProcedural, "절차 모형에 메시가 없음");
            // (2.4) fragments 절차 메시는 조각 배치에 비율이 들어 있다 → 비율을 넣지 않은 경계로 맞춘다(가장 긴 변 L0는 비율로 바뀌지 않음)
            if (RenderPath == FormRenderPlan.RendererFragments && RenderPlan.Proportions != null)
                FragmentMesh.Bounds(RenderPlan.FragmentSeed, RenderPlan.FragmentPieces, null, out pc, out ps);
            Material mat = null;
            foreach (var r in _model.GetComponentsInChildren<Renderer>())
            {
                foreach (var m in r.sharedMaterials) if (m != null) { mat = m; break; }
                if (mat != null) break;
            }
            if (mat == null) return Fail(res, FormAsset.FormAssetResult.NoProcedural, "절차 모형에 머티리얼이 없음");

            // 메시 만들기(정점이 65535개를 넘으면 32비트 번호)
            int n = mesh.VertexCount;
            var verts = new Vector3[n];
            var normals = new Vector3[n];
            for (int i = 0; i < n; i++)
            {
                verts[i] = new Vector3(mesh.Positions[i * 3], mesh.Positions[i * 3 + 1], mesh.Positions[i * 3 + 2]);
                normals[i] = new Vector3(mesh.Normals[i * 3], mesh.Normals[i * 3 + 1], mesh.Normals[i * 3 + 2]);
            }
            var um = new Mesh { name = "IFS generated " + asset.AssetId };
            if (n > 65535) um.indexFormat = IndexFormat.UInt32;
            um.vertices = verts;
            um.normals = normals;
            um.triangles = mesh.Triangles;
            um.RecalculateBounds();

            // 절차 모형을 지우되 그 머티리얼 하나는 남겨 새 메시에 입힌다(나머지 사본은 지움)
            foreach (var r in _model.GetComponentsInChildren<Renderer>(true))
                foreach (var m in r.sharedMaterials)
                    if (m != null && m != mat && _ownedMaterials.Remove(m)) DestroySafe(m);
            DestroySafe(_model);
            var go = new GameObject("model (generated " + asset.AssetId + ")");
            go.AddComponent<MeshFilter>().sharedMesh = um;
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.transform.SetParent(_motion.transform, false);
            _model = go;
            _assetMesh = um;
            _isShapeModel = false;
            _assetFit = new FormAsset.FormAssetFit(pc, ps, mesh.Center, mesh.Size);
            RenderPath = "generated(" + asset.AssetId + ")";
            ApplyAll();

            res.RenderPath = RenderPath;
            res.Vertices = n;
            res.Triangles = mesh.TriangleCount;
            res.LayoutSize = CurrentParams.GetNumber("layout.size");
            res.UniformScale = FormAssetScale;
            res.AssetLongestEdge = mesh.LongestEdge;
            res.RenderedLongestEdgeM = FormAssetLongestEdgeM;
            res.ProceduralLongestEdgeM = FormAssetProceduralLongestEdgeM;
            var sz = mesh.Size;
            double u = FormAssetScale ?? 0;
            var g = FormAssetScaleVector ?? new[] { u, u, u };   // (2.4) 비율이 있으면 축마다 다르다
            res.RenderedSizeM = new[] { sz[0] * g[0], sz[1] * g[1], sz[2] * g[2] };
            double rel = FormAsset.FormAssetFit.RelativeError(FormAssetLongestEdgeM ?? 0, FormAssetProceduralLongestEdgeM ?? 0);
            if (double.IsNaN(rel) || rel > FormAsset.FormAssetFit.Tolerance)
            {
                // 크기 규칙을 지키지 못하면 절차 모형으로 되돌린다(거리 결과변수 보호)
                BuildHierarchy();
                ApplyAll();
                res.RenderPath = RenderPath;
                return Fail(res, FormAsset.FormAssetResult.SizeMismatch, "가장 긴 변 상대 오차 " + rel);
            }
            res.Status = FormAsset.FormAssetResult.StatusApplied;
            Note($"생성 형태 메시 {asset.AssetId}: 절차 모형({res.ProceduralRenderPath}) 대신 표시 — 가장 긴 변 {FormAssetLongestEdgeM:0.####} m" +
                 $"(같은 layout.size의 절차 모형과 같음), 머티리얼·그림자는 절차 모형 규칙", false);
            return res;
        }

        /// <summary>G62: GLB를 쓰지 못할 때(파일 없음·sha256 다름·읽기 실패) 절차 모형을 그대로 두고 그 사실을 notes와 결과에 남긴다.</summary>
        public FormAsset.FormAssetResult ApplyFormAssetFallback(FormAsset.FormAssetRef asset, string reason, string detail)
        {
            var res = new FormAsset.FormAssetResult { Ref = asset, ProceduralRenderPath = RenderPath, RenderPath = RenderPath,
                                                       LayoutSize = CurrentParams?.GetNumber("layout.size") };
            return Fail(res, reason, detail);
        }

        FormAsset.FormAssetResult Fail(FormAsset.FormAssetResult res, string reason, string detail)
        {
            res.Status = FormAsset.FormAssetResult.StatusFallback;
            res.FallbackReason = reason;
            res.Detail = detail;
            Note($"생성 형태 메시 {res.Ref?.AssetId}: 절차 모형으로 표시({reason}{(detail != null ? " — " + detail : "")})", true);
            return res;
        }

        // 절차 모형의 경계(모형 국소 좌표, 모형 배율 곱하기 전). 메시 필터가 모형 자신에 있거나, 회전 없는 한 단계 자식(모양 모형)에 있다.
        // mesh.bounds가 아니라 정점으로 잰다: 기본 덩어리(IcoMesh)는 셰이더 변위 때문에 bounds를 1.6으로 넉넉히 잡아 두어(지름은 1.0),
        // bounds로 재면 생성 메시가 1.6배 크게 그려졌다(2026-11-27 실제 자산 캡처에서 확인).
        bool ProceduralLocalBounds(out double[] center, out double[] size)
        {
            center = size = null;
            double[] mn = { double.MaxValue, double.MaxValue, double.MaxValue }, mx = { double.MinValue, double.MinValue, double.MinValue };
            bool any = false;
            foreach (var mf in _model.GetComponentsInChildren<MeshFilter>())
            {
                if (mf == null || mf.sharedMesh == null) continue;
                var verts = mf.sharedMesh.vertices;
                if (verts == null || verts.Length == 0) continue;
                Vector3 s = Vector3.one, p = Vector3.zero;
                if (mf.transform != _model.transform) { s = mf.transform.localScale; p = mf.transform.localPosition; }
                foreach (var v in verts)
                {
                    double[] w = { v.x * s.x + p.x, v.y * s.y + p.y, v.z * s.z + p.z };
                    for (int k = 0; k < 3; k++) { if (w[k] < mn[k]) mn[k] = w[k]; if (w[k] > mx[k]) mx[k] = w[k]; }
                }
                any = true;
            }
            if (!any) return false;
            center = new[] { (mn[0] + mx[0]) / 2, (mn[1] + mx[1]) / 2, (mn[2] + mx[2]) / 2 };
            size = new[] { mx[0] - mn[0], mx[1] - mn[1], mx[2] - mn[2] };
            return true;
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
                    // G62: 생성 메시에는 형태 프리셋(재질이 아니라 절차 형상의 모양)을 걸지 않는다 — 정점 변위 0(모양 모형과 같이),
                    // 껍질 열림 0(shell 프리셋의 _ShellOpen은 물체 좌표 높이로 위쪽을 잘라 생성 메시에 구멍을 냈다 — 2026-11-27 실제 자산 캡처)
                    if (_assetFit != null)
                    {
                        if (m.HasProperty(FormRenderResources.DisplacementProperty)) m.SetFloat(FormRenderResources.DisplacementProperty, 0f);
                        if (m.HasProperty(FormRenderResources.ShellOpenProperty)) m.SetFloat(FormRenderResources.ShellOpenProperty, 0f);
                    }
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

                    // (2.3) material.emission: 말했을 때만 넣는다(null이면 셰이더 기본 검정 그대로 → 2.2와 같은 머티리얼·화소).
                    // SetColor는 선형 색공간에서 sRGB → 선형으로 바꿔 넣으므로 계획의 선형 값을 sRGB로 부호화해 넘긴다(셰이더는 선형 값을 받음).
                    if (plan.EmissionSrgb(out float er, out float eg, out float eb))
                    {
                        if (m.HasProperty(FormRenderResources.EmissionProperty)) m.SetColor(FormRenderResources.EmissionProperty, new Color(er, eg, eb, 1f));
                        else if (plan.EmissionIntensity > 0)
                            Note($"{m.shader.name}: {FormRenderResources.EmissionProperty} 없음 → material.emission={plan.EmissionLevel} 적용 안 됨", true);
                    }
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
            if (Application.isPlaying)
            {
                // Destroy는 프레임 끝까지 미뤄진다. 그 전에 같은 프레임에서 다시 로드·수동 렌더하면 이전 형상이 함께 찍히므로 먼저 숨긴다
                // (2026-11-23 미리보기 플레이어 캡처에서 확인: 이전 spec의 형상이 겹쳐 찍힘)
                if (o is GameObject go) go.SetActive(false);
                Destroy(o);
            }
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
            key == ProportionsRender.Key ? "(1, 1, 1)"   // (2.4) 비율 슬롯 전체(축별 수치 키와 따로 기본값 기록)
            : p.IsNumeric(key) ? ExperimentRecorder.FormatNumber(p.GetNumber(key)) : p.GetCategory(key);
    }
}
