// 배치 공간 후보(G52–G55, EnvironmentStyle)가 쓰는 Unity API 스텁. 타입 검사용이고 동작은 흉내 내지 않는다.
// Material은 UnityStubs.cs에 있으므로 확장 메서드로 더한다(실제 Unity에서는 인스턴스 메서드라 같은 호출이 컴파일된다).
namespace UnityEngine
{
    public static class MaterialEnvironmentStubExtensions
    {
        public static void SetTexture(this Material m, string name, Texture value) { }
    }
}
