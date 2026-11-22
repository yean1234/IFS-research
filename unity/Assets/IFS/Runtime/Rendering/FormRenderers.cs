// 형상별 렌더러(X64): FormRenderPlan → 절차 모형(메시·머티리얼)과 IFS 셰이더 프로퍼티.
//   blob · shell      : 잘게 나눈 구(icosphere) 하나 + IFS 불투명/반투명 셰이더(정점 변위로 덩어리·껍질)
//   mist              : (지금은 blob과 같은 구 + Fade 셰이더)
//   fragments         : (지금은 구 5개)
//   shapeModel        : 모양 모형 4종(ShapeModelFactory) + 정점 변위 0
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

        static Shader _opaque, _fade;
        static Mesh _ico, _cone;

        public static Shader Opaque => _opaque;
        public static Shader Fade => _fade;

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

    /// <summary>fragments: 구 5개(이전 경로).</summary>
    public sealed class FragmentsRenderer : IcoFormRenderer
    {
        public FragmentsRenderer() : base(FormRenderPlan.RendererFragments) { }

        public override GameObject CreateModel(FormRenderPlan plan)
        {
            var group = new GameObject("fragments");
            Vector3[] offsets =
            {
                new Vector3(-0.38f, 0.1f, 0f), new Vector3(0.32f, -0.16f, 0.1f), new Vector3(0f, 0.38f, -0.1f),
                new Vector3(0.16f, 0.06f, 0.38f), new Vector3(-0.12f, -0.32f, -0.26f),
            };
            for (int i = 0; i < offsets.Length; i++)
            {
                var c = FormRenderResources.IcoPiece("fragment " + i, i + 1);
                c.transform.SetParent(group.transform, false);
                c.transform.localPosition = offsets[i];
                c.transform.localRotation = Quaternion.Euler(17f * i, 31f * i, 11f * i);
                c.transform.localScale = Vector3.one * (0.42f - 0.04f * i);
            }
            return group;
        }
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

    public static class FormRenderers
    {
        static readonly Dictionary<string, IFormRenderer> ByName = new Dictionary<string, IFormRenderer>
        {
            { FormRenderPlan.RendererBlob, new IcoFormRenderer(FormRenderPlan.RendererBlob) },
            { FormRenderPlan.RendererMist, new IcoFormRenderer(FormRenderPlan.RendererMist) },
            { FormRenderPlan.RendererShell, new IcoFormRenderer(FormRenderPlan.RendererShell) },
            { FormRenderPlan.RendererFragments, new FragmentsRenderer() },
            { FormRenderPlan.RendererShapeModel, new ShapeModelRenderer() },
        };

        /// <summary>계획의 렌더러. 표에 없는 form.type은 구 하나(프리셋 없음)로 — 이전 로더와 같은 동작.</summary>
        public static IFormRenderer For(FormRenderPlan plan) =>
            plan.Renderer != null && ByName.TryGetValue(plan.Renderer, out var r) ? r : new IcoFormRenderer(plan.Renderer);
    }
}
