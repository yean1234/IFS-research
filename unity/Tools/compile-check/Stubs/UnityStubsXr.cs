// 배치 실험 헤드셋 경로(2026-11-23)가 쓰는 Unity API 스텁(이름·시그니처만). 동작은 흉내 내지 않는다.
// 내장 XR 모듈(XRSettings·XRInputSubsystem·SubsystemManager), Application.onBeforeRender의 UnityAction, Windows 빌드 메뉴(BuildPipeline).
// XR 패키지(com.unity.xr.management·openxr) API는 Editor/XR/XrProjectSetup.cs에서만 쓰고, 그 파일은 패키지가 있을 때만
// (asmdef versionDefines → IFS_HAS_OPENXR) 컴파일되므로 여기서는 스텁이 필요 없다.
using System.Collections.Generic;

namespace UnityEngine.Events
{
    public delegate void UnityAction();
}

namespace UnityEngine
{
    public interface ISubsystem { bool running { get; } }

    public static class SubsystemManager
    {
        public static void GetSubsystems<T>(List<T> subsystems) where T : ISubsystem { subsystems?.Clear(); }
    }
}

namespace UnityEngine.XR
{
    public static class XRSettings
    {
        public static bool enabled { get; set; }
        public static bool isDeviceActive => false;
        public static string loadedDeviceName => "";
    }

    [System.Flags]
    public enum TrackingOriginModeFlags { Unknown = 0, Device = 1, Floor = 2, TrackingReference = 4, Unbounded = 8 }

    public class XRInputSubsystem : ISubsystem
    {
        public bool running => false;
        public bool TrySetTrackingOriginMode(TrackingOriginModeFlags origin) => false;
        public TrackingOriginModeFlags GetTrackingOriginMode() => TrackingOriginModeFlags.Unknown;
    }
}

namespace UnityEditor
{
    public enum BuildTarget { StandaloneWindows64 = 19, WebGL = 20 }

    public enum BuildTargetGroup { Standalone = 1, WebGL = 13 }

    [System.Flags]
    public enum BuildOptions { None = 0 }

    public struct BuildPlayerOptions
    {
        public string[] scenes { get; set; }
        public string locationPathName { get; set; }
        public BuildTarget target { get; set; }
        public BuildOptions options { get; set; }
    }

    public static class BuildPipeline
    {
        public static Build.Reporting.BuildReport BuildPlayer(BuildPlayerOptions buildPlayerOptions) => new Build.Reporting.BuildReport();
        public static bool IsBuildTargetSupported(BuildTargetGroup buildTargetGroup, BuildTarget target) => false;
    }
}

namespace UnityEditor.Build.Reporting
{
    public enum BuildResult { Unknown = 0, Succeeded = 1, Failed = 2, Cancelled = 3 }

    public struct BuildSummary
    {
        public BuildResult result => BuildResult.Unknown;
        public int totalErrors => 0;
        public int totalWarnings => 0;
        public System.TimeSpan totalTime => default;
        public ulong totalSize => 0;
    }

    public class BuildReport
    {
        public BuildSummary summary => default;
    }
}
