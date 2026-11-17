// 소유감 실험 러너가 쓰는 Unity API 스텁(이름·시그니처만). 동작은 흉내 내지 않는다.
// 입력(Input·KeyCode, 기존 Input Manager), 글자(TextMesh·Font), IMGUI(GUI·GUILayout), 내장 XR 모듈(InputDevices).
using System;

namespace UnityEngine
{
    public enum KeyCode
    {
        None = 0, Backspace = 8, Return = 13, Escape = 27, Space = 32,
        Alpha0 = 48, Alpha1 = 49, Alpha2 = 50, Alpha3 = 51, Alpha4 = 52, Alpha5 = 53, Alpha6 = 54, Alpha7 = 55, Alpha8 = 56, Alpha9 = 57,
        A = 97, D = 100, S = 115, W = 119,
        Keypad0 = 256, Keypad1 = 257, Keypad2 = 258, Keypad3 = 259, Keypad4 = 260, Keypad5 = 261, Keypad6 = 262, Keypad7 = 263,
        Keypad8 = 264, Keypad9 = 265, KeypadEnter = 271, F1 = 282,
    }

    public static class Input
    {
        public static bool GetKeyDown(KeyCode key) => false;
        public static bool GetKey(KeyCode key) => false;
        public static bool GetMouseButton(int button) => false;
        public static float GetAxis(string axisName) => 0f;
    }

    public enum TextAnchor { UpperLeft, UpperCenter, UpperRight, MiddleLeft, MiddleCenter, MiddleRight, LowerLeft, LowerCenter, LowerRight }
    public enum TextAlignment { Left, Center, Right }

    public sealed class Font : Object
    {
        public Material material => null;
        public static Font CreateDynamicFontFromOSFont(string fontname, int size) => new Font();
        public static string[] GetOSInstalledFontNames() => Array.Empty<string>();
    }

    public sealed class TextMesh : Component
    {
        public string text { get; set; }
        public Font font { get; set; }
        public int fontSize { get; set; }
        public float characterSize { get; set; }
        public TextAnchor anchor { get; set; }
        public TextAlignment alignment { get; set; }
        public Color color { get; set; }
    }

    public static class Screen
    {
        public static int width => 1920;
        public static int height => 1080;
    }

    public enum EventType { MouseDown = 0, MouseUp = 1, KeyDown = 4, KeyUp = 5, Repaint = 7, Layout = 8 }

    public sealed class Event
    {
        public static Event current => new Event();
        public EventType type => EventType.Layout;
        public KeyCode keyCode => KeyCode.None;
    }

    public sealed class GUIStyle
    {
        public GUIStyle() { }
        public GUIStyle(GUIStyle other) { }
        public bool wordWrap { get; set; }
        public bool richText { get; set; }
    }

    public sealed class GUISkin : Object
    {
        public GUIStyle label => new GUIStyle();
        public GUIStyle box => new GUIStyle();
    }

    public sealed class GUILayoutOption { }

    public static class GUIUtility { public static int keyboardControl { get; set; } }

    public static class GUI
    {
        public static GUISkin skin => new GUISkin();
        public static Color color { get; set; }
        public static bool enabled { get; set; }
        public static void Label(Rect position, string text) { }
    }

    public static class GUILayout
    {
        public static void BeginArea(Rect screenRect, GUIStyle style) { }
        public static void EndArea() { }
        public static Vector2 BeginScrollView(Vector2 scrollPosition, params GUILayoutOption[] options) => scrollPosition;
        public static void EndScrollView() { }
        public static void BeginHorizontal(params GUILayoutOption[] options) { }
        public static void EndHorizontal() { }
        public static void Label(string text, params GUILayoutOption[] options) { }
        public static void Label(string text, GUIStyle style, params GUILayoutOption[] options) { }
        public static string TextField(string text, params GUILayoutOption[] options) => text;
        public static bool Button(string text, params GUILayoutOption[] options) => false;
        public static GUILayoutOption Width(float width) => new GUILayoutOption();
        public static GUILayoutOption Height(float height) => new GUILayoutOption();
        public static GUILayoutOption ExpandWidth(bool expand) => new GUILayoutOption();
    }
}

namespace UnityEngine.XR
{
    public enum XRNode { LeftEye = 0, RightEye = 1, CenterEye = 2, Head = 3, LeftHand = 4, RightHand = 5 }

    public struct InputFeatureUsage<T>
    {
        public InputFeatureUsage(string usageName) { name = usageName; }
        public string name { get; }
    }

    public static class CommonUsages
    {
        public static InputFeatureUsage<Vector3> devicePosition => new InputFeatureUsage<Vector3>("DevicePosition");
        public static InputFeatureUsage<Quaternion> deviceRotation => new InputFeatureUsage<Quaternion>("DeviceRotation");
    }

    public struct InputDevice
    {
        public bool isValid => false;
        public bool TryGetFeatureValue(InputFeatureUsage<Vector3> usage, out Vector3 value) { value = default; return false; }
        public bool TryGetFeatureValue(InputFeatureUsage<Quaternion> usage, out Quaternion value) { value = default; return false; }
    }

    public static class InputDevices
    {
        public static InputDevice GetDeviceAtXRNode(XRNode node) => default;
    }
}
