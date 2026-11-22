// 실험 경로: 생성 모델이 만든 GLB를 런타임에 읽어 정규화된 크기로 놓는다(docs/gen3d-feasibility.md).
//
// 기존 SceneSpec 파이프라인과 별개다. SceneSpec 로더·러너·기록 형식을 건드리지 않는다.
// 주의(AGENTS.md 원칙 1·2): GLB의 형상·색·재질은 생성 모델이 정한 것이다. 참여자가 말하지 않은 세부가 들어 있다.
// 이 경로로 그린 물체는 "말한 값만 그린" SceneSpec 물체와 같은 지위로 기록하거나 분석하지 않는다.
//
// glTFast(com.unity.cloud.gltfast 6.21.0, Apache-2.0)의 GltfImport를 쓴다.
// 반환한 Gen3DGlbHandle을 Dispose하면 GltfImport가 만든 메시·머티리얼·텍스처도 함께 지워진다.

using System;
using System.Diagnostics;
using System.IO;
using System.Threading;
using System.Threading.Tasks;
using GLTFast;
using UnityEngine;
using Object = UnityEngine.Object;

namespace IFS.Gen3D
{
    /// <summary>읽은 GLB 하나. 루트 GameObject와 그것을 만든 GltfImport를 함께 들고 있다.</summary>
    public sealed class Gen3DGlbHandle : IDisposable
    {
        public string Path;
        public GameObject Root;
        public GltfImport Import;
        public bool Ok;
        public string Error;
        public double ReadMs, ParseMs, InstantiateMs;
        public Bounds RawBounds;          // 정규화 전, 루트 좌표계 기준 경계
        public int Vertices, Triangles, Renderers;
        public bool HasVertexColors;
        public string[] Shaders = Array.Empty<string>();

        public double TotalMs => ReadMs + ParseMs + InstantiateMs;

        public void Dispose()
        {
            if (Root != null)
            {
                if (Application.isPlaying) Object.Destroy(Root);
                else Object.DestroyImmediate(Root);
                Root = null;
            }
            Import?.Dispose();
            Import = null;
        }
    }

    public static class Gen3DGlb
    {
        /// <summary>
        /// 파일 경로의 GLB를 읽어 parent 아래에 만든다. 실패해도 예외 대신 handle.Ok = false, Error에 이유.
        /// Quest(Android)에서는 StreamingAssets를 File로 읽을 수 없으므로 persistentDataPath 아래 경로를 쓴다.
        /// </summary>
        public static async Task<Gen3DGlbHandle> LoadAsync(string path, Transform parent = null, bool uninterrupted = true,
                                                         CancellationToken ct = default)
        {
            var h = new Gen3DGlbHandle { Path = path };
            var sw = Stopwatch.StartNew();
            try
            {
                byte[] bytes = File.ReadAllBytes(path);
                h.ReadMs = sw.Elapsed.TotalMilliseconds;
                // 배치 캡처·에디트 모드는 프레임을 나눌 필요가 없다. 실행 중(헤드셋)에는 프레임 예산 방식이 낫다.
                IDeferAgent defer = uninterrupted ? new UninterruptedDeferAgent() : null;
                h.Import = new GltfImport(null, defer);
                var settings = new ImportSettings
                {
                    GenerateMipMaps = true,
                    AnimationMethod = AnimationMethod.None,
                };
                sw.Restart();
                bool ok = await h.Import.Load(bytes, new Uri(System.IO.Path.GetFullPath(path)), settings, ct);
                h.ParseMs = sw.Elapsed.TotalMilliseconds;
                if (!ok)
                {
                    h.Error = "GltfImport.Load가 false를 돌려줌";
                    return h;
                }
                var go = new GameObject("gen3d " + System.IO.Path.GetFileNameWithoutExtension(path));
                if (parent != null) go.transform.SetParent(parent, false);
                h.Root = go;
                sw.Restart();
                ok = await h.Import.InstantiateMainSceneAsync(go.transform, ct);
                h.InstantiateMs = sw.Elapsed.TotalMilliseconds;
                if (!ok)
                {
                    h.Error = "InstantiateMainSceneAsync가 false를 돌려줌";
                    return h;
                }
                Inspect(h);
                h.Ok = h.Renderers > 0;
                if (!h.Ok) h.Error = "렌더러가 없음";
            }
            catch (Exception e)
            {
                h.Error = e.GetType().Name + ": " + e.Message;
            }
            return h;
        }

        static void Inspect(Gen3DGlbHandle h)
        {
            var rs = h.Root.GetComponentsInChildren<Renderer>(true);
            h.Renderers = rs.Length;
            var shaders = new System.Collections.Generic.SortedSet<string>(StringComparer.Ordinal);
            bool any = false;
            var b = new Bounds();
            foreach (var r in rs)
            {
                foreach (var m in r.sharedMaterials)
                    if (m != null && m.shader != null) shaders.Add(m.shader.name);
                var mf = r.GetComponent<MeshFilter>();
                Mesh mesh = mf != null ? mf.sharedMesh : (r as SkinnedMeshRenderer)?.sharedMesh;
                if (mesh != null)
                {
                    h.Vertices += mesh.vertexCount;
                    for (int s = 0; s < mesh.subMeshCount; s++) h.Triangles += (int)(mesh.GetIndexCount(s) / 3);
                    if (mesh.colors32 != null && mesh.colors32.Length > 0) h.HasVertexColors = true;
                }
                if (!any) { b = r.bounds; any = true; }
                else b.Encapsulate(r.bounds);
            }
            h.Shaders = new string[shaders.Count];
            shaders.CopyTo(h.Shaders);
            // 루트 좌표계로(루트가 원점·단위 배율일 때 월드와 같다)
            h.RawBounds = new Bounds(h.Root.transform.InverseTransformPoint(b.center), b.size);
        }

        /// <summary>
        /// 가장 긴 변이 targetSize(m)가 되게 균일 배율을 주고, 경계 중심을 center에 둔다.
        /// 생성 모델의 절대 크기는 의미가 없어(모델마다 단위가 다름) 크기는 SceneSpec과 따로 정한다.
        /// </summary>
        public static float Normalize(Gen3DGlbHandle h, float targetSize, Vector3 center)
        {
            if (h?.Root == null) return 0f;
            float longest = Mathf.Max(h.RawBounds.size.x, Mathf.Max(h.RawBounds.size.y, h.RawBounds.size.z));
            float k = longest > 1e-6f ? targetSize / longest : 1f;
            var t = h.Root.transform;
            t.localScale = Vector3.one * k;
            t.position = center - t.rotation * (h.RawBounds.center * k);
            return k;
        }
    }
}
