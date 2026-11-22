// 안개 밀도장(D7, 2026-11-23)에서 쓰는 Unity API 스텁(이름·시그니처만, 타입 검사용).
// Material은 UnityStubs.cs에 있으므로 확장 메서드로 SetVector·GetVector를 더한다(실제 Unity에서는 인스턴스 메서드라 같은 호출이 컴파일된다).
namespace UnityEngine
{
    public struct Vector4
    {
        public float x, y, z, w;
        public Vector4(float x, float y, float z, float w) { this.x = x; this.y = y; this.z = z; this.w = w; }
    }

    public static class MaterialVectorStubs
    {
        public static void SetVector(this Material m, string name, Vector4 value) { }
        public static Vector4 GetVector(this Material m, string name) => default;
    }
}
