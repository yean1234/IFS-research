// 실험 경로: 씬에 두는 GLB 로더 컴포넌트. 경로의 GLB를 읽어 이 오브젝트 아래에 정규화된 크기로 놓는다.
// 생성 모델이 만든 형상이라 참여자가 말하지 않은 세부가 들어 있다(docs/gen3d-feasibility.md, AGENTS.md 원칙 1·2).
// 기록·분석에서 SceneSpec 물체와 섞지 않는다.

using System.Threading.Tasks;
using UnityEngine;

namespace IFS.Gen3D
{
    public sealed class Gen3DGlbLoader : MonoBehaviour
    {
        [Tooltip("GLB 절대 경로. Quest에서는 Application.persistentDataPath 아래(adb push)를 쓴다.")]
        public string glbPath = "";
        [Tooltip("가장 긴 변의 길이(m). 생성 모델의 단위는 의미가 없어 정규화한다.")]
        public float targetSize = 0.35f;
        [Tooltip("시작할 때 바로 읽기")]
        public bool loadOnStart = true;

        public Gen3DGlbHandle Current { get; private set; }

        async void Start()
        {
            if (loadOnStart && !string.IsNullOrEmpty(glbPath)) await Load(glbPath);
        }

        public async Task<Gen3DGlbHandle> Load(string path)
        {
            Current?.Dispose();
            // 실행 중에는 프레임 예산 방식(기본 defer agent)으로 읽어 프레임이 끊기지 않게 한다.
            var h = await Gen3DGlb.LoadAsync(path, transform, uninterrupted: !Application.isPlaying);
            if (!h.Ok)
            {
                Debug.LogWarning($"[Gen3D] GLB를 읽지 못함: {path} — {h.Error}");
                h.Dispose();
                Current = null;
                return h;
            }
            Gen3DGlb.Normalize(h, targetSize, transform.position);
            Current = h;
            Debug.Log($"[Gen3D] {System.IO.Path.GetFileName(path)}: 삼각형 {h.Triangles}, {h.TotalMs:F0} ms (생성 형상 — 말하지 않은 세부 포함)");
            return h;
        }

        void OnDestroy()
        {
            Current?.Dispose();
            Current = null;
        }
    }
}
