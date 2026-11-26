// 형상별 렌더러(X64): FormRenderPlan → 절차 모형(메시·머티리얼)과 IFS 셰이더 프로퍼티.
//   blob · shell      : 잘게 나눈 구(icosphere) 하나 + IFS 불투명/반투명 셰이더(정점 변위로 덩어리·껍질)
//   mist              : 구 대리 메시 하나를 그리고 물체 좌표 레이마칭으로 밀도를 쌓는 SceneSpecMist 셰이더(X66).
//                       밀도장은 seed로 고정한 둥근 덩어리 5개 + 중간 주파수 노이즈(D7, MistLumps)
//                       안개 셰이더를 못 쓰면 이전 경로(구 + Fade 셰이더, renderPath "mist(legacy)")
//   fragments         : 불규칙한 각진 조각 5개를 합친 메시 하나(FragmentMesh, 평면 음영, 정점 변위 0) + IFS 셰이더
//   shapeModel        : 모양 모형 4종(ShapeModelFactory) + 정점 변위 0
//   superquadric      : (2.3) form.roundness가 있는 기본 덩어리 경로 — 슈퍼쿼드릭 메시(SuperquadricMesh) + 정점 변위 0
// 렌더러는 FormRenderPlan만 본다(매퍼 정보를 모른다, X65). 프리팹·프리미티브 대체 경로는 SceneLoader가 맡는다.
// 재질의 공통 슬롯(_BaseColor·_Brightness·_Roughness·_Opacity·_Erosion, 대체 프로퍼티)은 SceneLoader가 넣는다.
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace IFS.SceneSpec
{
    public interface IFormRenderer
    {
        /// <summary>렌더러 이름(report.json의 renderPath).</summary>
        string Name { get; }

        /// <summary>IFS 셰이더로 절차 모형을 만든다(셰이더는 FormRenderResources.LoadIfsShaders()가 이미 읽었다).
        /// 만든 머티리얼은 새 사본이다(로더가 소유).</summary>
        GameObject CreateModel(FormRenderPlan plan);

        /// <summary>IFS 셰이더 머티리얼이면 셰이더 선택과 형상 프리셋을 넣고 true. 다른 셰이더면 아무것도 하지 않고 false.</summary>
        bool ApplyShader(Material m, FormRenderPlan plan);

        /// <summary>IFS 셰이더 렌더러의 그림자 드리우기.</summary>
        ShadowCastingMode Shadow(FormRenderPlan plan);
    }

    /// <summary>IFS 셰이더·공유 메시 캐시(렌더러들이 같이 쓴다).</summary>
    public static class FormRenderResources
    {
        public const string OpaqueShaderResource = "IFS/SceneSpecOpaque";
        public const string FadeShaderResource = "IFS/SceneSpecFade";
        public const string DisplacementProperty = "_Displacement";
        /// <summary>(2.3) IFS 셰이더 발광 항(선형 RGB, 기본 검정 = 0). 명세(8.4절 4번)의 `_EmissionColor` 대신 이 이름을 쓴다:
        /// `_EmissionColor`는 Built-in Standard의 예약 이름(키워드 _EMISSION·GI 발광 플래그)이고 SceneLoader의 밝기 대체 경로
        /// (ShaderParamNames.emissionFallback)와 golden 지문(LoaderNoVariantGoldenTests.ColorProps)이 그 이름의 유무를 읽어
        /// IFS 셰이더에 더하면 2.0–2.2 지문이 바뀐다. 키워드 없이 서피스 셰이더의 o.Emission에 더하기만 한다.</summary>
        public const string EmissionProperty = "_IfsEmission";
        public const string MistShaderResource = "IFS/SceneSpecMist";
        /// <summary>안개 대리 구의 반지름(물체 좌표). 셰이더 IFS_MIST_RADIUS와 같게.</summary>
        public const float MistRadius = 0.75f;

        static Shader _opaque, _fade, _mist;
        static Mesh _mistMesh;
        static Mesh _ico, _cone;

        public static Shader Opaque => _opaque;
        public static Shader Fade => _fade;
        public static Shader Mist => _mist;

        /// <summary>안개 셰이더를 읽는다. 없거나 지원되지 않으면 false(안개는 이전 경로로).</summary>
        public static bool LoadMistShader()
        {
            if (_mist == null) _mist = Resources.Load<Shader>(MistShaderResource);
            return _mist != null && _mist.isSupported;
        }

        /// <summary>안개 대리 구: 3번 나눈 icosphere(삼각형 1,280개). 면이 셰이더의 구(반지름 MistRadius)를 덮도록 조금 크게.
        /// 바운즈는 이전 안개(IcoMesh)와 같은 1.6 상자 → 배치·소유감 러너가 읽는 렌더러 바운즈가 그대로다.</summary>
        public static Mesh MistMesh()
        {
            if (_mistMesh != null) return _mistMesh;
            IcoSphere.Build(3, MistRadius * 1.02f, out float[] xyz, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = verts[i].normalized;
            }
            _mistMesh = new Mesh { name = "IFS Mist Proxy" };
            _mistMesh.vertices = verts;
            _mistMesh.normals = normals;
            _mistMesh.triangles = tris;
            _mistMesh.bounds = new Bounds(Vector3.zero, Vector3.one * 1.6f);
            return _mistMesh;
        }

        public static bool LoadIfsShaders()
        {
            if (_opaque == null) _opaque = Resources.Load<Shader>(OpaqueShaderResource);
            if (_fade == null) _fade = Resources.Load<Shader>(FadeShaderResource);
            // URP 등 Built-in이 아닌 파이프라인에서는 서피스 셰이더가 지원되지 않는다 → 프리미티브로
            return _opaque != null && _fade != null && _opaque.isSupported && _fade.isSupported;
        }

        public static string IfsShaderProblem()
        {
            if (_opaque == null || _fade == null)
                return $"Resources/{OpaqueShaderResource}·{FadeShaderResource} 셰이더를 찾지 못함(파일이 없거나 import 전)";
            if (!_opaque.isSupported || !_fade.isSupported)
                return "IFS 셰이더가 지원되지 않음 — 셰이더 컴파일 오류이거나 Built-in이 아닌 렌더 파이프라인(URP 등). " +
                       "Project 창에서 SceneSpecOpaque 셰이더를 선택해 Inspector의 오류를 확인";
            return "알 수 없음";
        }

        /// <summary>IFS 불투명·반투명 셰이더를 쓰는 머티리얼인가.</summary>
        public static bool IsLegacyIfs(Material m) => _opaque != null && m != null && (m.shader == _opaque || m.shader == _fade);

        public static Mesh IcoMesh()
        {
            if (_ico != null) return _ico;
            IcoSphere.Build(4, 0.5f, out float[] xyz, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = verts[i] * 2f;   // 반지름 0.5 → 단위 법선
            }
            _ico = new Mesh { name = "IFS IcoSphere" };
            _ico.vertices = verts;
            _ico.normals = normals;
            _ico.triangles = tris;
            _ico.bounds = new Bounds(Vector3.zero, Vector3.one * 1.6f);   // 셰이더가 정점을 밀어내므로 넉넉하게
            return _ico;
        }

        static readonly Dictionary<(int, int), Mesh> _fragments = new Dictionary<(int, int), Mesh>();

        /// <summary>조각 메시(FragmentMesh). 같은 (seed, 조각 수)면 같은 메시라 한 번 만들어 재사용한다.</summary>
        public static Mesh FragmentsMesh(int seed, int pieces)
        {
            if (_fragments.TryGetValue((seed, pieces), out var cached) && cached != null) return cached;
            FragmentMesh.Build(seed, pieces, out float[] xyz, out float[] nrm, out int[] tris, out _);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = new Vector3(nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]);
            }
            var mesh = new Mesh { name = "IFS Fragments" };
            mesh.vertices = verts;
            mesh.normals = normals;
            mesh.triangles = tris;
            mesh.RecalculateBounds();
            _fragments[(seed, pieces)] = mesh;
            return mesh;
        }

        static readonly Dictionary<string, Mesh> _bases = new Dictionary<string, Mesh>();

        /// <summary>(2.2) 기본 형상 메시(BaseShapeMesh). 같은 (형상, 변형값, seed)면 같은 메시라 한 번 만들어 재사용한다.</summary>
        public static Mesh BaseMesh(FormRenderPlan plan)
        {
            var parts = new List<string> { plan.BaseShape, plan.BaseSeed.ToString(System.Globalization.CultureInfo.InvariantCulture) };
            foreach (var kv in plan.BaseVariant) parts.Add(kv.Key + "=" + kv.Value);
            string key = string.Join("|", parts);
            if (_bases.TryGetValue(key, out var cached) && cached != null) return cached;
            BaseShapeMesh.Build(plan.BaseShape, plan.BaseVariant, plan.BaseSeed, out float[] xyz, out float[] nrm, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = new Vector3(nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]);
            }
            var mesh = new Mesh { name = "IFS Base " + plan.BaseRule };
            mesh.vertices = verts;
            mesh.normals = normals;
            mesh.triangles = tris;
            mesh.RecalculateBounds();
            _bases[key] = mesh;
            return mesh;
        }

        static readonly Dictionary<(double, double), Mesh> _superquadrics = new Dictionary<(double, double), Mesh>();

        /// <summary>(2.3) 슈퍼쿼드릭 메시(SuperquadricMesh). 같은 (e1, e2)면 같은 메시라 한 번 만들어 재사용한다.</summary>
        public static Mesh SuperquadricMesh(double e1, double e2)
        {
            if (_superquadrics.TryGetValue((e1, e2), out var cached) && cached != null) return cached;
            IFS.SceneSpec.SuperquadricMesh.Build(e1, e2, out float[] xyz, out float[] nrm, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = new Vector3(nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]);
            }
            var inv = System.Globalization.CultureInfo.InvariantCulture;
            var mesh = new Mesh { name = "IFS Superquadric " + ContourRender.MeshRule + " e" + e1.ToString(inv) };
            mesh.vertices = verts;
            mesh.normals = normals;
            mesh.triangles = tris;
            mesh.RecalculateBounds();
            _superquadrics[(e1, e2)] = mesh;
            return mesh;
        }

        public static Mesh ConeMesh()
        {
            if (_cone == null) _cone = ShapeModelFactory.BuildConeMesh();
            return _cone;
        }

        /// <summary>IFS 셰이더 머티리얼 하나에 형상 프리셋과 셰이더(불투명/반투명)를 넣는다. 기존 SceneLoader.ApplyMaterial과 같은 순서.</summary>
        public static void ApplyLegacyPreset(Material m, FormRenderPlan plan)
        {
            var wanted = plan.Fade ? _fade : _opaque;   // 안개·반투명이면 Fade로 바꾼다
            if (m.shader != wanted) m.shader = wanted;
            var preset = plan.Preset;
            m.SetFloat("_Lumpiness", preset.Lumpiness);
            m.SetFloat("_NoiseScale", preset.NoiseScale);
            m.SetFloat("_Fuzz", preset.Fuzz);
            m.SetFloat("_Density", preset.Density);
            m.SetFloat("_ShellOpen", preset.ShellOpen);
            // 모양 모형만 정점 변위 0(각진 면이 벌어지지 않고 윤곽 유지). 그 밖의 모형은 셰이더 기본값 1 그대로.
            if (plan.ZeroDisplacement) m.SetFloat(DisplacementProperty, 0f);
        }

        /// <summary>mist 덩어리(D7): MistLumps.Build(seed)의 중심·반지름을 _Lump0…로 넣는다(물체 좌표 xyz = 중심, w = 반지름).</summary>
        public static void ApplyMistLumps(Material m, int seed)
        {
            var l = MistLumps.Build(seed);
            for (int k = 0; k < MistLumps.Count; k++)
                m.SetVector(MistLumpProperty(k), new Vector4((float)l[k * 4], (float)l[k * 4 + 1], (float)l[k * 4 + 2], (float)l[k * 4 + 3]));
        }

        /// <summary>덩어리 k의 머티리얼 프로퍼티 이름(_Lump0…).</summary>
        public static string MistLumpProperty(int k) => "_Lump" + k.ToString(System.Globalization.CultureInfo.InvariantCulture);

        /// <summary>구 메시 하나 + IFS 불투명 머티리얼(_Seed) + 구 콜라이더.</summary>
        public static GameObject IcoPiece(string name, float seed)
        {
            var go = new GameObject(name);
            go.AddComponent<MeshFilter>().sharedMesh = IcoMesh();
            var mat = new Material(_opaque);
            mat.SetFloat("_Seed", seed);
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<SphereCollider>();
            return go;
        }
    }

    /// <summary>구 하나에 IFS 셰이더(blob · shell · mist(이전 경로)). 형상 차이는 프리셋 숫자와 셰이더 선택뿐이다.</summary>
    public class IcoFormRenderer : IFormRenderer
    {
        public IcoFormRenderer(string name) { Name = name; }
        public string Name { get; }

        public virtual GameObject CreateModel(FormRenderPlan plan) => FormRenderResources.IcoPiece(plan.FormType, 0f);

        public virtual bool ApplyShader(Material m, FormRenderPlan plan)
        {
            if (!FormRenderResources.IsLegacyIfs(m)) return false;
            FormRenderResources.ApplyLegacyPreset(m, plan);
            return true;
        }

        // 반투명(Fade)은 Built-in에서 그림자를 받지 못하고, 불투명 그림자를 드리우면 안개가 덩어리처럼 보인다 → 그림자 끔.
        public virtual ShadowCastingMode Shadow(FormRenderPlan plan) => plan.Fade ? ShadowCastingMode.Off : ShadowCastingMode.On;
    }

    /// <summary>fragments(X67): 불규칙한 각진 조각 여러 개를 합친 메시 하나(드로콜 1, 평면 음영). IFS 셰이더는 그대로 쓰고
    /// 정점 변위만 0으로 둔다(계획의 ZeroDisplacement) → 재질 슬롯(색·밝기·채도·거칠기·불투명도·침식)과 움직임이 그대로 먹는다.</summary>
    public sealed class FragmentsRenderer : IcoFormRenderer
    {
        public FragmentsRenderer() : base(FormRenderPlan.RendererFragments) { }

        public override GameObject CreateModel(FormRenderPlan plan)
        {
            var go = new GameObject("fragments");
            var mesh = FormRenderResources.FragmentsMesh(plan.FragmentSeed, plan.FragmentPieces);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mat = new Material(FormRenderResources.Opaque);
            mat.SetFloat("_Seed", plan.FragmentSeed);
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<MeshCollider>().sharedMesh = mesh;
            return go;
        }
    }

    /// <summary>mist(X66): 구 대리 메시 + 부피 레이마칭 셰이더(SceneSpecMist). 그림자 없음(U5).
    /// 재질 슬롯은 로더가 공통 프로퍼티(_BaseColor·_Brightness·_Roughness·_Opacity·_Erosion)로 넣고, 여기서는 형상 프리셋만 넣는다.</summary>
    public sealed class MistRenderer : IFormRenderer
    {
        public string Name => FormRenderPlan.RendererMist;

        public GameObject CreateModel(FormRenderPlan plan)
        {
            var go = new GameObject(plan.FormType);
            go.AddComponent<MeshFilter>().sharedMesh = FormRenderResources.MistMesh();
            var mat = new Material(FormRenderResources.Mist);
            mat.SetFloat("_Seed", 0f);
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<SphereCollider>();
            return go;
        }

        public bool ApplyShader(Material m, FormRenderPlan plan)
        {
            if (m != null && FormRenderResources.Mist != null && m.shader == FormRenderResources.Mist)
            {
                m.SetFloat("_Lumpiness", plan.Preset.Lumpiness);
                m.SetFloat("_NoiseScale", plan.Preset.NoiseScale);
                m.SetFloat("_Density", plan.Preset.Density);
                m.SetFloat("_Seed", plan.MistSeed);
                FormRenderResources.ApplyMistLumps(m, plan.MistSeed);
                return true;
            }
            // 프리팹 등 이전 IFS 셰이더 머티리얼은 이전 방식(구 + Fade)
            if (!FormRenderResources.IsLegacyIfs(m)) return false;
            FormRenderResources.ApplyLegacyPreset(m, plan);
            return true;
        }

        public ShadowCastingMode Shadow(FormRenderPlan plan) => ShadowCastingMode.Off;
    }

    /// <summary>모양 모형(구·큐브·납작 원기둥·원뿔). 메뉴와 같은 함수(ShapeModelFactory)로 만든다.</summary>
    public sealed class ShapeModelRenderer : IcoFormRenderer
    {
        public ShapeModelRenderer() : base(FormRenderPlan.RendererShapeModel) { }

        public override GameObject CreateModel(FormRenderPlan plan)
        {
            var mat = new Material(FormRenderResources.Opaque) { name = "IFS shape (" + plan.ShapeModel + ")" };
            return ShapeModelFactory.Create(plan.ShapeModel, mat, FormRenderResources.ConeMesh());
        }
    }

    /// <summary>(2.2) 기본 형상(container·line·sheet·flame·drop): BaseShapeMesh 메시 하나 + IFS 셰이더(모양 모형과 같은 프리셋, 정점 변위 0).
    /// 재질 슬롯(색·밝기·채도·거칠기·불투명도·침식)과 움직임(SpecMotion, 피벗 전체)은 다른 형상과 같이 먹는다. 형상 고유 움직임은 없다.</summary>
    public sealed class BaseShapeRenderer : IcoFormRenderer
    {
        public BaseShapeRenderer(string shape) : base(FormRenderPlan.RendererBasePrefix + shape) { }

        public override GameObject CreateModel(FormRenderPlan plan)
        {
            var go = new GameObject("base " + plan.BaseShape);
            var mesh = FormRenderResources.BaseMesh(plan);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mat = new Material(FormRenderResources.Opaque) { name = "IFS base (" + plan.BaseRule + ")" };
            mat.SetFloat("_Seed", plan.BaseSeed);
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<MeshCollider>().sharedMesh = mesh;
            return go;
        }
    }

    /// <summary>(2.3) 슈퍼쿼드릭(form.roundness, 기본 덩어리 경로): SuperquadricMesh 메시 하나 + IFS 셰이더(모양 모형과 같은 프리셋, 정점 변위 0).
    /// 재질 슬롯(색·밝기·채도·거칠기·불투명도·침식·발광)과 움직임은 다른 형상과 같이 먹는다. 축 비율(form.aspect)은 로더가 국소 배율에 곱한다.</summary>
    public sealed class SuperquadricRenderer : IcoFormRenderer
    {
        public SuperquadricRenderer() : base(FormRenderPlan.RendererSuperquadric) { }

        public override GameObject CreateModel(FormRenderPlan plan)
        {
            var go = new GameObject("superquadric " + plan.Roundness);
            var mesh = FormRenderResources.SuperquadricMesh(plan.E1.Value, plan.E2.Value);
            go.AddComponent<MeshFilter>().sharedMesh = mesh;
            var mat = new Material(FormRenderResources.Opaque) { name = "IFS contour (" + ContourRender.MeshRule + ")" };
            mat.SetFloat("_Seed", 0f);
            go.AddComponent<MeshRenderer>().sharedMaterial = mat;
            go.AddComponent<MeshCollider>().sharedMesh = mesh;
            return go;
        }
    }

    public static class FormRenderers
    {
        static readonly Dictionary<string, IFormRenderer> ByName = new Dictionary<string, IFormRenderer>
        {
            { FormRenderPlan.RendererBlob, new IcoFormRenderer(FormRenderPlan.RendererBlob) },
            { FormRenderPlan.RendererMist, new MistRenderer() },
            { FormRenderPlan.RendererShell, new IcoFormRenderer(FormRenderPlan.RendererShell) },
            { FormRenderPlan.RendererFragments, new FragmentsRenderer() },
            { FormRenderPlan.RendererShapeModel, new ShapeModelRenderer() },
            { FormRenderPlan.RendererSuperquadric, new SuperquadricRenderer() },
        };

        /// <summary>안개 셰이더를 못 쓸 때의 안개(이전 경로: 구 + Fade 셰이더).</summary>
        public const string MistLegacyName = "mist(legacy)";
        static readonly IFormRenderer MistLegacy = new IcoFormRenderer(MistLegacyName);
        static readonly Dictionary<string, IFormRenderer> Bases = new Dictionary<string, IFormRenderer>();

        /// <summary>계획의 렌더러. 표에 없는 form.type은 구 하나(프리셋 없음)로 — 이전 로더와 같은 동작.
        /// mist는 안개 셰이더를 쓸 수 있을 때만 부피 렌더러, 아니면 이전 경로.</summary>
        public static IFormRenderer For(FormRenderPlan plan)
        {
            if (plan.Renderer == FormRenderPlan.RendererMist && !FormRenderResources.LoadMistShader()) return MistLegacy;
            if (plan.BaseShape != null)
            {
                if (!Bases.TryGetValue(plan.BaseShape, out var br)) Bases[plan.BaseShape] = br = new BaseShapeRenderer(plan.BaseShape);
                return br;
            }
            return plan.Renderer != null && ByName.TryGetValue(plan.Renderer, out var r) ? r : new IcoFormRenderer(plan.Renderer);
        }
    }
}
