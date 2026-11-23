// Unity 없이 IFS 스크립트를 타입 검사하기 위한 최소 스텁. 실제 Unity API의 이름·시그니처만 흉내 낸다.
// 동작은 흉내 내지 않는다(Application.streamingAssetsPath만 저장소의 StreamingAssets를 가리킨다).
// 이 폴더(unity/Tools)는 Assets 밖이라 Unity가 컴파일하지 않는다.
using System;
using System.IO;

namespace UnityEngine
{
    public class Object
    {
        public string name { get; set; }
        public static T Instantiate<T>(T original, Transform parent, bool instantiateInWorldSpace) where T : Object => original;
        public static void Destroy(Object obj) { }
        public static void DestroyImmediate(Object obj) { }
        public static T[] FindObjectsByType<T>(FindObjectsSortMode sortMode) where T : Object => Array.Empty<T>();
    }

    public enum FindObjectsSortMode { None, InstanceID }

    public class Component : Object
    {
        public Transform transform => null;
        public GameObject gameObject => null;
        public T GetComponent<T>() => default;
        public T[] GetComponentsInChildren<T>() => Array.Empty<T>();
        public T[] GetComponentsInChildren<T>(bool includeInactive) => Array.Empty<T>();
        public T GetComponentInChildren<T>() => default;
    }

    public class Behaviour : Component
    {
        public bool enabled { get; set; }
        public bool isActiveAndEnabled => enabled;
    }
    public class MonoBehaviour : Behaviour { }

    public sealed class GameObject : Object
    {
        public GameObject(string name) { this.name = name; }
        public Transform transform => null;
        public string tag { get; set; }
        public bool activeInHierarchy => true;
        public bool activeSelf => true;
        public void SetActive(bool value) { }
        public T AddComponent<T>() where T : Component => default;
        public T GetComponent<T>() => default;
        public T[] GetComponentsInChildren<T>() => Array.Empty<T>();
        public T[] GetComponentsInChildren<T>(bool includeInactive) => Array.Empty<T>();
        public static GameObject CreatePrimitive(PrimitiveType type) => new GameObject(type.ToString());
    }

    public class Transform : Component
    {
        public Vector3 position { get; set; }
        public Quaternion rotation { get; set; }
        public Vector3 localPosition { get; set; }
        public Quaternion localRotation { get; set; }
        public Vector3 localScale { get; set; }
        public Vector3 eulerAngles { get; set; }
        public Vector3 forward => Vector3.forward;
        public Vector3 right => new Vector3(1, 0, 0);
        public void SetParent(Transform parent, bool worldPositionStays) { }
        public void SetPositionAndRotation(Vector3 position, Quaternion rotation) { }
        public Matrix4x4 localToWorldMatrix => default;
        public Vector3 TransformPoint(Vector3 position) => position;
        public Vector3 TransformDirection(Vector3 direction) => direction;
    }

    public struct Matrix4x4
    {
        public float m00, m01, m02, m03, m10, m11, m12, m13, m20, m21, m22, m23, m30, m31, m32, m33;
    }

    public struct Vector3
    {
        public float x, y, z;
        public Vector3(float x, float y, float z) { this.x = x; this.y = y; this.z = z; }
        public static Vector3 zero => new Vector3(0, 0, 0);
        public static Vector3 one => new Vector3(1, 1, 1);
        public static Vector3 up => new Vector3(0, 1, 0);
        public static Vector3 down => new Vector3(0, -1, 0);
        public static Vector3 forward => new Vector3(0, 0, 1);
        public float sqrMagnitude => x * x + y * y + z * z;
        public float magnitude => (float)Math.Sqrt(sqrMagnitude);
        public Vector3 normalized => this;
        public static Vector3 operator +(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a, Vector3 b) => a;
        public static Vector3 operator *(Vector3 a, float d) => a;
        public static Vector3 operator *(float d, Vector3 a) => a;
        public static Vector3 Cross(Vector3 a, Vector3 b) => a;
        public static float Distance(Vector3 a, Vector3 b) => 0f;
        public static Vector3 Scale(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a) => a;
    }

    public struct Vector2
    {
        public float x, y;
        public Vector2(float x, float y) { this.x = x; this.y = y; }
    }

    public struct Quaternion
    {
        public float x, y, z, w;
        public Vector3 eulerAngles => default;
        public static Vector3 operator *(Quaternion rotation, Vector3 point) => point;
        public static Quaternion identity => default;
        public static Quaternion Euler(float x, float y, float z) => default;
        public static Quaternion LookRotation(Vector3 forward, Vector3 upwards) => default;
        public static Quaternion operator *(Quaternion a, Quaternion b) => a;
    }

    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color white => new Color(1, 1, 1, 1);
        public static Color black => new Color(0, 0, 0, 1);
        public static Color yellow => new Color(1, 0.92f, 0.016f, 1);
        public static Color operator *(Color c, float d) => c;
        public Color linear => this;
    }

    public struct Color32
    {
        public byte r, g, b, a;
        public Color32(byte r, byte g, byte b, byte a) { this.r = r; this.g = g; this.b = b; this.a = a; }
    }

    public struct Rect { public Rect(float x, float y, float width, float height) { } }

    public struct RectInt
    {
        public int x, y, width, height;
        public RectInt(int x, int y, int width, int height) { this.x = x; this.y = y; this.width = width; this.height = height; }
    }

    public struct Plane { }

    public static class GeometryUtility
    {
        public static Plane[] CalculateFrustumPlanes(Camera camera) => Array.Empty<Plane>();
        public static bool TestPlanesAABB(Plane[] planes, Bounds bounds) => true;
    }

    public class Shader : Object
    {
        public static Shader Find(string name) => null;
        public bool isSupported => true;
        public Rendering.ShaderTagId FindPassTagValue(int passIndex, Rendering.ShaderTagId tagName) => default;
    }

    public class Material : Object
    {
        public Material(Shader shader) { }
        public Material(Material source) { }
        public Shader shader { get; set; }
        public Color color { get; set; }
        public Texture mainTexture { get; set; }
        public int renderQueue { get; set; }
        public int passCount => 0;
        public string GetPassName(int pass) => "";
        public bool HasProperty(string name) => false;
        public void SetColor(string name, Color value) { }
        public void SetFloat(string name, float value) { }
        public void EnableKeyword(string keyword) { }
    }

    public class Renderer : Component
    {
        public bool enabled { get; set; }
        public Material[] materials { get; set; }
        public Material sharedMaterial { get; set; }
        public Material[] sharedMaterials { get; set; }
        public Bounds bounds => default;
        public Rendering.ShadowCastingMode shadowCastingMode { get; set; }
        public bool receiveShadows { get; set; }
    }

    public sealed class MeshRenderer : Renderer { }
    public sealed class MeshFilter : Component { public Mesh sharedMesh { get; set; } }
    public class Collider : Component { }
    public sealed class SphereCollider : Collider { }
    public sealed class MeshCollider : Collider { public Mesh sharedMesh { get; set; } public bool convex { get; set; } }

    public struct Bounds
    {
        public Bounds(Vector3 center, Vector3 size) { }
        public Vector3 center => default;
        public Vector3 extents => default;
        public Vector3 size => default;
        public Vector3 max => default;
        public void Encapsulate(Bounds bounds) { }
    }

    public sealed class Mesh : Object
    {
        public Vector3[] vertices { get; set; }
        public Vector3[] normals { get; set; }
        public int[] triangles { get; set; }
        public Bounds bounds { get; set; }
        public int subMeshCount => 1;
        public uint GetIndexCount(int submesh) => 0;
        public void Clear() { }
        public void RecalculateBounds() { }
    }

    public static class Resources
    {
        public static T Load<T>(string path) where T : Object => null;
        public static T GetBuiltinResource<T>(string path) where T : Object => null;
    }

    public class Camera : Behaviour
    {
        public static Camera main => null;
        public float nearClipPlane { get; set; }
        public float farClipPlane { get; set; }
        public float fieldOfView { get; set; }
        public bool allowMSAA { get; set; }
        public bool allowHDR { get; set; }
        public CameraClearFlags clearFlags { get; set; }
        public Color backgroundColor { get; set; }
        public RenderTexture targetTexture { get; set; }
        public void Render() { }
        public bool RenderToCubemap(RenderTexture cubemap, int faceMask) => true;
        public StereoTargetEyeMask stereoTargetEye { get; set; }
        public Ray ScreenPointToRay(Vector3 pos) => default;
    }

    public enum CameraClearFlags { Skybox = 1, SolidColor = 2, Depth = 3, Nothing = 4 }

    public enum LightType { Spot, Directional, Point }
    public enum LightShadows { None, Hard, Soft }
    public enum LightRenderMode { Auto, ForcePixel, ForceVertex }

    public sealed class Light : Behaviour
    {
        public LightType type { get; set; }
        public Color color { get; set; }
        public float intensity { get; set; }
        public LightShadows shadows { get; set; }
        public float shadowStrength { get; set; }
        public LightRenderMode renderMode { get; set; }
    }

    public class AudioListener : Behaviour { }

    public class Texture : Object
    {
        public int width { get; set; }
        public int height { get; set; }
    }

    public enum TextureFormat { RGBA32 = 4, ARGB32 = 5 }
    public enum RenderTextureFormat { ARGB32 = 0, Depth = 1 }

    public struct RenderTextureDescriptor
    {
        public RenderTextureDescriptor(int width, int height, RenderTextureFormat colorFormat, int depthBufferBits) { sRGB = false; msaaSamples = 1; }
        public bool sRGB { get; set; }
        public int msaaSamples { get; set; }
    }

    public class RenderTexture : Texture
    {
        public RenderTexture(int width, int height, int depth, RenderTextureFormat format) { }
        public RenderTexture(RenderTextureDescriptor desc) { }
        public static RenderTexture active { get; set; }
        public Rendering.TextureDimension dimension { get; set; }
        public bool useMipMap { get; set; }
        public bool autoGenerateMips { get; set; }
        public int antiAliasing { get; set; }
        public bool Create() => true;
        public void Release() { }
        public void ResolveAntiAliasedSurface(RenderTexture target) { }
        public static RenderTexture GetTemporary(RenderTextureDescriptor desc) => null;
        public static void ReleaseTemporary(RenderTexture temp) { }
    }

    public sealed class Texture2D : Texture
    {
        public Texture2D(int width, int height, TextureFormat textureFormat, bool mipChain, bool linear) { }
        public Texture2D(int width, int height) { }
        public void SetPixel(int x, int y, Color color) { }
        public void Apply() { }
        public void ReadPixels(Rect source, int destX, int destY, bool recalculateMipMaps) { }
        public Color32[] GetPixels32() => Array.Empty<Color32>();
        public void SetPixels32(Color32[] colors) { }
        public void Apply(bool updateMipmaps) { }
    }

    public static class ImageConversion
    {
        public static byte[] EncodeToPNG(this Texture2D tex) => Array.Empty<byte>();
    }

    public static class Graphics
    {
        public static void Blit(Texture source, RenderTexture dest) { }
    }

    public enum ColorSpace { Uninitialized = -1, Gamma = 0, Linear = 1 }
    public enum ShadowQuality { Disable, HardOnly, All }
    public enum ShadowResolution { Low, Medium, High, VeryHigh }

    public static class QualitySettings
    {
        public static string[] names => Array.Empty<string>();
        public static int GetQualityLevel() => 0;
        public static void SetQualityLevel(int index, bool applyExpensiveChanges) { }
        public static int antiAliasing { get; set; }
        public static ShadowQuality shadows { get; set; }
        public static ShadowResolution shadowResolution { get; set; }
        public static float shadowDistance { get; set; }
        public static int shadowCascades { get; set; }
        public static int pixelLightCount { get; set; }
        public static ColorSpace activeColorSpace => ColorSpace.Linear;
    }

    public static class RenderSettings
    {
        public static bool fog { get; set; }
        public static Material skybox { get; set; }
        public static Rendering.AmbientMode ambientMode { get; set; }
        public static Color ambientSkyColor { get; set; }
        public static Color ambientEquatorColor { get; set; }
        public static Color ambientGroundColor { get; set; }
        public static float ambientIntensity { get; set; }
        public static Color ambientLight { get; set; }
        public static Rendering.SphericalHarmonicsL2 ambientProbe { get; set; }
        public static Light sun { get; set; }
        public static Rendering.DefaultReflectionMode defaultReflectionMode { get; set; }
        public static Texture customReflectionTexture { get; set; }
        public static float reflectionIntensity { get; set; }
    }

    public static class DynamicGI { public static void UpdateEnvironment() { } }

    public static class SystemInfo
    {
        public static string graphicsDeviceName => "";
        public static Rendering.GraphicsDeviceType graphicsDeviceType => default;
        public static string operatingSystem => "";
        public static string graphicsDeviceVersion => "";
    }

    public enum LogType { Error, Assert, Warning, Log, Exception }

    public enum PrimitiveType { Sphere, Capsule, Cylinder, Cube, Plane, Quad }

    public static class Application
    {
        /// <summary>검사용: 위로 올라가며 Assets/StreamingAssets를 찾는다.</summary>
        public static string streamingAssetsPath
        {
            get
            {
                var env = Environment.GetEnvironmentVariable("IFS_STREAMING_ASSETS");
                if (!string.IsNullOrEmpty(env)) return env;
                for (var d = new DirectoryInfo(AppContext.BaseDirectory); d != null; d = d.Parent)
                {
                    var p = Path.Combine(d.FullName, "Assets", "StreamingAssets");
                    if (Directory.Exists(p)) return p;
                }
                throw new DirectoryNotFoundException("Assets/StreamingAssets");
            }
        }
        public static string persistentDataPath => Path.GetTempPath();
        public static bool isPlaying => false;
        public static bool isBatchMode => true;
        public static bool isEditor => true;
        public static string dataPath => "";
        public static string unityVersion => "";
        public static RuntimePlatform platform => RuntimePlatform.WindowsEditor;
        public static void Quit() { }
        public delegate void LogCallback(string condition, string stackTrace, LogType type);
        public static event LogCallback logMessageReceived { add { } remove { } }
        public static event Events.UnityAction onBeforeRender { add { } remove { } }
    }

    public static class Debug
    {
        public static void Log(object message) { }
        public static void LogWarning(object message) { }
        public static void LogError(object message) { }
        public static void Log(object message, Object context) { }
        public static void LogWarning(object message, Object context) { }
        public static void LogError(object message, Object context) { }
    }

    public static class Mathf
    {
        public const float PI = 3.14159274f;
        public const float Rad2Deg = 57.29578f;
        public static float Atan2(float y, float x) => 0f;
        public static float Min(float a, float b) => a < b ? a : b;
        public static float Max(float a, float b) => a > b ? a : b;
        public static int Max(int a, int b) => a > b ? a : b;
        public static int Min(int a, int b) => a < b ? a : b;
        public static float Abs(float f) => f < 0 ? -f : f;
        public static float Lerp(float a, float b, float t) => a;
        public static float Clamp01(float v) => v;
        public static float Clamp(float value, float min, float max) => value;
        public static float PerlinNoise(float x, float y) => 0f;
        public static float Sin(float f) => 0f;
        public static float Cos(float f) => 0f;
    }

    public static class Time { public static float deltaTime => 0f; public static float unscaledDeltaTime => 0f; }

    [AttributeUsage(AttributeTargets.Field)] public sealed class SerializeField : Attribute { }
    public class PropertyAttribute : Attribute { }
    [AttributeUsage(AttributeTargets.Field)] public sealed class HeaderAttribute : PropertyAttribute { public HeaderAttribute(string header) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class TooltipAttribute : PropertyAttribute { public TooltipAttribute(string tooltip) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class RangeAttribute : PropertyAttribute { public RangeAttribute(float min, float max) { } }
    [AttributeUsage(AttributeTargets.Class)] public sealed class DisallowMultipleComponent : Attribute { }
    [AttributeUsage(AttributeTargets.Class)] public sealed class AddComponentMenu : Attribute { public AddComponentMenu(string menuName) { } }
    [AttributeUsage(AttributeTargets.Method)] public sealed class ContextMenu : Attribute { public ContextMenu(string itemName) { } }
    [AttributeUsage(AttributeTargets.Class)] public sealed class DefaultExecutionOrder : Attribute { public DefaultExecutionOrder(int order) { } }
}

namespace UnityEngine.Rendering
{
    public enum ShadowCastingMode { Off, On, TwoSided, ShadowsOnly }
    public enum AmbientMode { Skybox = 0, Trilight = 1, Flat = 3, Custom = 4 }
    public enum DefaultReflectionMode { Skybox, Custom }
    public struct SphericalHarmonicsL2 { }
    public enum TextureDimension { Unknown = -1, None = 0, Any = 1, Tex2D = 2, Tex3D = 3, Cube = 4, Tex2DArray = 5, CubeArray = 6 }
    public enum RenderQueue { Background = 1000, Geometry = 2000, AlphaTest = 2450, GeometryLast = 2500, Transparent = 3000, Overlay = 4000 }
    public enum GraphicsDeviceType { Null = 4, Direct3D11 = 2, Vulkan = 21 }

    public struct ShaderTagId
    {
        public ShaderTagId(string name) { this.name = name; }
        public string name { get; }
    }

    public class RenderPipelineAsset : Object { }

    public static class GraphicsSettings { public static RenderPipelineAsset currentRenderPipeline => null; }
}

namespace Unity.Profiling
{
    public struct ProfilerCategory { public static ProfilerCategory Render => default; }
    public enum ProfilerRecorderOptions { Default = 152 }
    public struct ProfilerRecorder : IDisposable
    {
        public static ProfilerRecorder StartNew(ProfilerCategory category, string statName, int capacity = 1, ProfilerRecorderOptions options = ProfilerRecorderOptions.Default) => default;
        public bool Valid => false;
        public long CurrentValue => 0;
        public long LastValue => 0;
        public void Dispose() { }
    }
}

namespace UnityEngine.SceneManagement
{
    public struct Scene
    {
        public string path => "";
        public string name => "";
        public bool isLoaded => true;
        public GameObject[] GetRootGameObjects() => Array.Empty<GameObject>();
    }

    public static class SceneManager
    {
        public static int sceneCount => 0;
        public static Scene GetSceneAt(int index) => default;
    }
}

namespace UnityEditor
{
    [AttributeUsage(AttributeTargets.Method)] public sealed class MenuItem : Attribute { public MenuItem(string itemName) { } }

    public static class EditorApplication { public static void Exit(int returnValue) { } }

    public static class AssetDatabase
    {
        public static T LoadAssetAtPath<T>(string assetPath) where T : UnityEngine.Object => null;
        public static UnityEngine.Object[] LoadAllAssetsAtPath(string assetPath) => System.Array.Empty<UnityEngine.Object>();
        public static void CreateAsset(UnityEngine.Object asset, string path) { }
        public static string CreateFolder(string parentFolder, string newFolderName) => "";
        public static bool IsValidFolder(string path) => false;
        public static void SaveAssets() { }
    }

    public static class PrefabUtility
    {
        public static UnityEngine.GameObject SaveAsPrefabAsset(UnityEngine.GameObject instanceRoot, string assetPath, out bool success)
        {
            success = true;
            return instanceRoot;
        }
    }

    public static class EditorUtility { public static void SetDirty(UnityEngine.Object target) { } }

    public static class UnityStats
    {
        public static int drawCalls => 0;
        public static int batches => 0;
        public static int setPassCalls => 0;
        public static int triangles => 0;
        public static int vertices => 0;
        public static int shadowCasters => 0;
    }

    public enum ShaderCompilerMessageSeverity { Error, Warning }

    public struct ShaderMessage
    {
        public string message;
        public ShaderCompilerMessageSeverity severity;
    }

    public static class ShaderUtil
    {
        public static bool allowAsyncCompilation { get; set; }
        public static ShaderMessage[] GetShaderMessages(UnityEngine.Shader s) => Array.Empty<ShaderMessage>();
        public static bool ShaderHasError(UnityEngine.Shader shader) => false;
    }

    public class SerializedObject
    {
        public SerializedObject(UnityEngine.Object obj) { }
        public SerializedProperty FindProperty(string propertyPath) => new SerializedProperty();
        public bool ApplyModifiedPropertiesWithoutUndo() => true;
    }

    public class SerializedProperty
    {
        public UnityEngine.Vector3 vector3Value { get; set; }
        public bool boolValue { get; set; }
        public UnityEngine.Object objectReferenceValue { get; set; }
    }
}

namespace UnityEditor.SceneManagement
{
    public enum NewSceneSetup { EmptyScene, DefaultGameObjects }
    public enum NewSceneMode { Single, Additive }
    public enum OpenSceneMode { Single, Additive, AdditiveWithoutLoading }

    public static class EditorSceneManager
    {
        public static bool SaveCurrentModifiedScenesIfUserWantsTo() => true;
        public static UnityEngine.SceneManagement.Scene NewScene(NewSceneSetup setup, NewSceneMode mode) => default;
        public static bool SaveScene(UnityEngine.SceneManagement.Scene scene, string dstScenePath = "", bool saveAsCopy = false) => true;
        public static UnityEngine.SceneManagement.Scene OpenScene(string scenePath, OpenSceneMode mode) => default;
        public static bool CloseScene(UnityEngine.SceneManagement.Scene scene, bool removeScene) => true;
        public static bool MarkSceneDirty(UnityEngine.SceneManagement.Scene scene) => true;
    }
}
