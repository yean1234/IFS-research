// SceneSpec v2 JSON → VR 오브젝트.
//   form.type      → 프리팹 4종(blob/mist/shell/fragments). 비어 있으면 기본 절차 모형(잘게 나눈 구 + IFS 셰이더,
//                    형태별 프리셋). IFS 셰이더를 못 쓰는 환경이면 임시 프리미티브(로그 + initialScene notes)
//   material.*     → Shader Graph 파라미터(_BaseColor, _Brightness, _Roughness, _Opacity, _Erosion)
//   layout.*       → Transform(거리·높이·크기), form.posture → 크기 변형 프리셋
//   motion.*       → SpecMotion(절차적 움직임)
// null 값은 SceneDefaults로 채우고, 어떤 값을 기본값으로 썼는지 콘솔과 initialScene.json(defaultsUsed)에 남긴다.
// _inferred(3층 제안)는 useInferredSuggestions를 켜야만 쓴다(기본 꺼짐 — 말하지 않은 것을 추론하지 않는다).
// 참여자 조정은 SetNumber/SetCategory로 → events.csv 한 줄씩, SaveFinal()로 finalScene.json.
using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using UnityEngine;

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

        // 형태별 모양 프리셋(IFS 셰이더 전용): 굴곡, 노이즈 크기, 안개 가장자리, 밀도, 껍질 열림
        struct FormPreset
        {
            public float lumpiness, noiseScale, fuzz, density, shellOpen;
            public FormPreset(float l, float n, float f, float d, float s) { lumpiness = l; noiseScale = n; fuzz = f; density = d; shellOpen = s; }
        }

        static readonly Dictionary<string, FormPreset> FormPresets = new Dictionary<string, FormPreset>
        {
            { "blob", new FormPreset(0.14f, 1.6f, 0f, 1f, 0f) },
            { "mist", new FormPreset(0.30f, 1.1f, 1f, 0.5f, 0f) },
            { "shell", new FormPreset(0.04f, 2.0f, 0f, 1f, 0.35f) },
            { "fragments", new FormPreset(0.25f, 2.4f, 0f, 1f, 0f) },
        };

        const string OpaqueShaderResource = "IFS/SceneSpecOpaque";
        const string FadeShaderResource = "IFS/SceneSpecFade";
        static Shader _opaqueShader, _fadeShader;
        static Mesh _icoMesh;

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
        public event Action<SceneLoader> Loaded;

        ISceneSpecPathSource _source;
        ExperimentRecorder _recorder;
        GameObject _root, _model;
        SpecMotion _motion;
        Vector3 _anchorPos, _anchorForward, _modelBaseScale;
        float _eyeHeight;
        readonly List<string> _notes = new List<string>();

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

        void OnDestroy() => CloseRecorder();

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
        public bool Load(string path)
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

            Unload();
            Spec = spec;
            SpecPath = full;
            _notes.Clear();
            InitialParams = SceneParams.FromSpec(spec, defaults, useInferredSuggestions);
            foreach (var key in InitialParams.DefaultsUsed)
                Note($"{key}: SceneSpec 값이 null → 기본값 {Describe(InitialParams, key)} 사용", false);
            foreach (var key in InitialParams.InferredUsed)
                Note($"{key}: 3층 제안(_inferred) {Describe(InitialParams, key)} 사용", false);
            CurrentParams = InitialParams.Clone();

            CaptureAnchor();
            BuildHierarchy();
            ApplyAll();

            if (record)
            {
                var sessionId = spec.Meta.SessionId ?? Path.GetFileNameWithoutExtension(full);
                _recorder = new ExperimentRecorder(RecordRoot, sessionId, spec, full);
                _recorder.WriteInitial(InitialParams, raw, _notes);
                Debug.Log($"[SceneLoader] 기록 폴더: {_recorder.Directory}", this);
            }
            Debug.Log($"[SceneLoader] {Path.GetFileName(full)} 로드: form={CurrentParams.GetCategory("form.type")}, " +
                      $"기본값 {InitialParams.DefaultsUsed.Count}개", this);
            Loaded?.Invoke(this);
            return true;
        }

        public void Unload()
        {
            CloseRecorder();
            if (_root != null) Destroy(_root);
            _root = _model = null;
            _motion = null;
            Spec = null;
            InitialParams = CurrentParams = null;
        }

        string ResolvePath(string path) =>
            Path.IsPathRooted(path) ? path : Path.Combine(Application.streamingAssetsPath, path);

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
            if (_model != null) Destroy(_model);

            string form = CurrentParams.GetCategory("form.type");
            var prefab = FindPrefab(form);
            if (prefab != null)
            {
                _model = Instantiate(prefab, _motion.transform, false);
            }
            else if (useProceduralModels && LoadIfsShaders())
            {
                _model = CreateProceduralModel(form);
                _model.transform.SetParent(_motion.transform, false);
                _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
                Note($"form.type={form}: 프리팹이 연결되지 않아 기본 절차 모형(IFS 셰이더)으로 표시", false);
            }
            else
            {
                _model = CreatePrimitive(form);
                _model.transform.SetParent(_motion.transform, false);
                _model.transform.localScale = Vector3.one * placement.primitiveBaseSize;
                string why = useProceduralModels ? IfsShaderProblem() : "useProceduralModels가 꺼져 있음";
                Note($"form.type={form}: 프리팹이 연결되지 않아 임시 프리미티브로 대체 — 이유: {why}", true);
            }
            _model.name = "model (" + form + ")";
            _modelBaseScale = _model.transform.localScale;
        }

        GameObject FindPrefab(string form)
        {
            foreach (var fp in formPrefabs)
                if (fp != null && fp.formType == form && fp.prefab != null) return fp.prefab;
            return null;
        }

        static bool LoadIfsShaders()
        {
            if (_opaqueShader == null) _opaqueShader = Resources.Load<Shader>(OpaqueShaderResource);
            if (_fadeShader == null) _fadeShader = Resources.Load<Shader>(FadeShaderResource);
            // URP 등 Built-in이 아닌 파이프라인에서는 서피스 셰이더가 지원되지 않는다 → 프리미티브로
            return _opaqueShader != null && _fadeShader != null && _opaqueShader.isSupported && _fadeShader.isSupported;
        }

        static string IfsShaderProblem()
        {
            if (_opaqueShader == null || _fadeShader == null)
                return $"Resources/{OpaqueShaderResource}·{FadeShaderResource} 셰이더를 찾지 못함(파일이 없거나 import 전)";
            if (!_opaqueShader.isSupported || !_fadeShader.isSupported)
                return "IFS 셰이더가 지원되지 않음 — 셰이더 컴파일 오류이거나 Built-in이 아닌 렌더 파이프라인(URP 등). " +
                       "Project 창에서 SceneSpecOpaque 셰이더를 선택해 Inspector의 오류를 확인";
            return "알 수 없음";
        }

        static Mesh IcoMesh()
        {
            if (_icoMesh != null) return _icoMesh;
            IcoSphere.Build(4, 0.5f, out float[] xyz, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = verts[i] * 2f;   // 반지름 0.5 → 단위 법선
            }
            _icoMesh = new Mesh { name = "IFS IcoSphere" };
            _icoMesh.vertices = verts;
            _icoMesh.normals = normals;
            _icoMesh.triangles = tris;
            _icoMesh.bounds = new Bounds(Vector3.zero, Vector3.one * 1.6f);   // 셰이더가 정점을 밀어내므로 넉넉하게
            return _icoMesh;
        }

        static GameObject CreateProceduralModel(string form)
        {
            GameObject Piece(string name, float seed)
            {
                var go = new GameObject(name);
                go.AddComponent<MeshFilter>().sharedMesh = IcoMesh();
                var mat = new Material(_opaqueShader);
                mat.SetFloat("_Seed", seed);
                go.AddComponent<MeshRenderer>().sharedMaterial = mat;
                go.AddComponent<SphereCollider>();
                return go;
            }

            if (form != "fragments") return Piece(form, 0f);
            var group = new GameObject("fragments");
            Vector3[] offsets =
            {
                new Vector3(-0.38f, 0.1f, 0f), new Vector3(0.32f, -0.16f, 0.1f), new Vector3(0f, 0.38f, -0.1f),
                new Vector3(0.16f, 0.06f, 0.38f), new Vector3(-0.12f, -0.32f, -0.26f),
            };
            for (int i = 0; i < offsets.Length; i++)
            {
                var c = Piece("fragment " + i, i + 1);
                c.transform.SetParent(group.transform, false);
                c.transform.localPosition = offsets[i];
                c.transform.localRotation = Quaternion.Euler(17f * i, 31f * i, 11f * i);
                c.transform.localScale = Vector3.one * (0.42f - 0.04f * i);
            }
            return group;
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
            var p = CurrentParams;
            SceneParams.HslToRgb(p.GetNumber("material.color.h"), p.GetNumber("material.color.s"),
                p.GetNumber("material.color.l"), out double r, out double g, out double b);
            float opacity = (float)p.GetNumber("material.opacity");
            float brightness = (float)p.GetNumber("material.brightness");
            float roughness = (float)p.GetNumber("material.roughness");
            float erosion = (float)p.GetNumber("material.erosion");
            var color = new Color((float)r, (float)g, (float)b, opacity);
            var sp = shaderParams;
            string form = p.GetCategory("form.type");
            FormPresets.TryGetValue(form, out var preset);
            bool fade = form == "mist" || opacity < 0.99f;

            foreach (var rend in _model.GetComponentsInChildren<Renderer>())
            {
                foreach (var m in rend.materials)   // 렌더러마다 인스턴스(공유 머티리얼을 바꾸지 않는다)
                {
                    bool ifsShader = _opaqueShader != null && (m.shader == _opaqueShader || m.shader == _fadeShader);
                    if (ifsShader)
                    {
                        var wanted = fade ? _fadeShader : _opaqueShader;   // 안개·반투명이면 Fade로 바꾼다
                        if (m.shader != wanted) m.shader = wanted;
                        m.SetFloat("_Lumpiness", preset.lumpiness);
                        m.SetFloat("_NoiseScale", preset.noiseScale);
                        m.SetFloat("_Fuzz", preset.fuzz);
                        m.SetFloat("_Density", preset.density);
                        m.SetFloat("_ShellOpen", preset.shellOpen);
                    }
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
            }
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
