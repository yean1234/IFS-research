// 미리보기(D4, WebGL·Windows 미리보기 빌드)가 쓰는 Unity API 스텁(이름·시그니처만). 동작은 흉내 내지 않는다.
namespace UnityEngine
{
    public enum StereoTargetEyeMask { None = 0, Left = 1, Right = 2, Both = 3 }

    public enum RuntimePlatform { WindowsEditor = 7, WindowsPlayer = 2, WebGLPlayer = 17 }
}

namespace UnityEditor
{
    public enum WebGLCompressionFormat { Brotli = 0, Gzip = 1, Disabled = 2 }

    public static class PlayerSettings
    {
        public static UnityEngine.ColorSpace colorSpace { get; set; }

        public static class WebGL
        {
            public static WebGLCompressionFormat compressionFormat { get; set; }
            public static bool decompressionFallback { get; set; }
            public static string template { get; set; }
            public static bool dataCaching { get; set; }
        }
    }

    public static class EditorUserBuildSettings
    {
        public static BuildTarget activeBuildTarget => BuildTarget.StandaloneWindows64;
        public static bool SwitchActiveBuildTarget(BuildTargetGroup targetGroup, BuildTarget target) => true;
    }

    public sealed class SceneAsset : UnityEngine.Object { }
}
