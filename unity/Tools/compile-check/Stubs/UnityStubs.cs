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
    }

    public class Component : Object
    {
        public Transform transform => null;
        public GameObject gameObject => null;
        public T GetComponent<T>() => default;
        public T[] GetComponentsInChildren<T>() => Array.Empty<T>();
    }

    public class Behaviour : Component { public bool enabled { get; set; } }
    public class MonoBehaviour : Behaviour { }

    public sealed class GameObject : Object
    {
        public GameObject(string name) { this.name = name; }
        public Transform transform => null;
        public T AddComponent<T>() where T : Component => default;
        public T GetComponent<T>() => default;
        public T[] GetComponentsInChildren<T>() => Array.Empty<T>();
        public static GameObject CreatePrimitive(PrimitiveType type) => new GameObject(type.ToString());
    }

    public class Transform : Component
    {
        public Vector3 position { get; set; }
        public Quaternion rotation { get; set; }
        public Vector3 localPosition { get; set; }
        public Quaternion localRotation { get; set; }
        public Vector3 localScale { get; set; }
        public Vector3 forward => Vector3.forward;
        public void SetParent(Transform parent, bool worldPositionStays) { }
        public void SetPositionAndRotation(Vector3 position, Quaternion rotation) { }
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
        public Vector3 normalized => this;
        public static Vector3 operator +(Vector3 a, Vector3 b) => a;
        public static Vector3 operator -(Vector3 a, Vector3 b) => a;
        public static Vector3 operator *(Vector3 a, float d) => a;
        public static Vector3 operator *(float d, Vector3 a) => a;
        public static Vector3 Cross(Vector3 a, Vector3 b) => a;
        public static float Distance(Vector3 a, Vector3 b) => 0f;
        public static Vector3 Scale(Vector3 a, Vector3 b) => a;
    }

    public struct Quaternion
    {
        public static Quaternion identity => default;
        public static Quaternion Euler(float x, float y, float z) => default;
        public static Quaternion LookRotation(Vector3 forward, Vector3 upwards) => default;
        public static Quaternion operator *(Quaternion a, Quaternion b) => a;
    }

    public struct Color
    {
        public float r, g, b, a;
        public Color(float r, float g, float b, float a) { this.r = r; this.g = g; this.b = b; this.a = a; }
        public static Color operator *(Color c, float d) => c;
    }

    public class Shader : Object { }

    public class Material : Object
    {
        public Shader shader => null;
        public bool HasProperty(string name) => false;
        public void SetColor(string name, Color value) { }
        public void SetFloat(string name, float value) { }
        public void EnableKeyword(string keyword) { }
    }

    public class Renderer : Component { public Material[] materials { get; set; } }

    public class Camera : Behaviour
    {
        public static Camera main => null;
        public float nearClipPlane { get; set; }
    }

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
    }

    public static class Debug
    {
        public static void Log(object message) { }
        public static void Log(object message, Object context) { }
        public static void LogWarning(object message, Object context) { }
        public static void LogError(object message, Object context) { }
    }

    public static class Mathf
    {
        public const float PI = 3.14159274f;
        public static float Lerp(float a, float b, float t) => a;
        public static float Clamp01(float v) => v;
        public static float PerlinNoise(float x, float y) => 0f;
        public static float Sin(float f) => 0f;
        public static float Cos(float f) => 0f;
    }

    public static class Time { public static float deltaTime => 0f; }

    [AttributeUsage(AttributeTargets.Field)] public sealed class SerializeField : Attribute { }
    public class PropertyAttribute : Attribute { }
    [AttributeUsage(AttributeTargets.Field)] public sealed class HeaderAttribute : PropertyAttribute { public HeaderAttribute(string header) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class TooltipAttribute : PropertyAttribute { public TooltipAttribute(string tooltip) { } }
    [AttributeUsage(AttributeTargets.Field)] public sealed class RangeAttribute : PropertyAttribute { public RangeAttribute(float min, float max) { } }
    [AttributeUsage(AttributeTargets.Class)] public sealed class DisallowMultipleComponent : Attribute { }
    [AttributeUsage(AttributeTargets.Class)] public sealed class AddComponentMenu : Attribute { public AddComponentMenu(string menuName) { } }
    [AttributeUsage(AttributeTargets.Method)] public sealed class ContextMenu : Attribute { public ContextMenu(string itemName) { } }
}

namespace UnityEngine.SceneManagement
{
    public struct Scene { }
}

namespace UnityEditor
{
    [AttributeUsage(AttributeTargets.Method)] public sealed class MenuItem : Attribute { public MenuItem(string itemName) { } }

    public class SerializedObject
    {
        public SerializedObject(UnityEngine.Object obj) { }
        public SerializedProperty FindProperty(string propertyPath) => new SerializedProperty();
        public bool ApplyModifiedPropertiesWithoutUndo() => true;
    }

    public class SerializedProperty { public UnityEngine.Vector3 vector3Value { get; set; } }
}

namespace UnityEditor.SceneManagement
{
    public enum NewSceneSetup { EmptyScene, DefaultGameObjects }
    public enum NewSceneMode { Single, Additive }

    public static class EditorSceneManager
    {
        public static bool SaveCurrentModifiedScenesIfUserWantsTo() => true;
        public static UnityEngine.SceneManagement.Scene NewScene(NewSceneSetup setup, NewSceneMode mode) => default;
        public static bool SaveScene(UnityEngine.SceneManagement.Scene scene, string dstScenePath) => true;
    }
}
