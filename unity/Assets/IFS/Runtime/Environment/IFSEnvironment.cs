// 씬에 두면 Awake에서 중립 환경(바닥·하늘·앰비언트·방향광·반사)을 만든다. SceneLoader보다 먼저 실행된다
// (DefaultExecutionOrder) — 반사 큐브맵에 형상이 찍히지 않도록.
using UnityEngine;

namespace IFS.SceneSpec
{
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(-100)]
    [AddComponentMenu("IFS/Neutral Environment")]
    public sealed class IFSEnvironment : MonoBehaviour
    {
        [SerializeField] EnvironmentSettings settings = new EnvironmentSettings();

        EnvironmentHandle _handle;

        public EnvironmentHandle Handle => _handle;
        public EnvironmentSettings Settings => settings;

        void Awake() => Rebuild();

        void OnDestroy()
        {
            _handle?.Dispose();
            _handle = null;
        }

        [ContextMenu("환경 다시 만들기")]
        public void Rebuild()
        {
            _handle?.Dispose();
            _handle = EnvironmentBuilder.Build(settings, transform);
        }
    }
}
