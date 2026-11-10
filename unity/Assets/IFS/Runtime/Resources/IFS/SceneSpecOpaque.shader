// SceneSpec 불투명 셰이더 (blob · shell · fragments). Built-in 렌더 파이프라인.
// 침식·껍질로 뚫린 구멍 너머로 안쪽 면이 보이도록 안쪽(어둡게) → 바깥 두 번 그린다.
Shader "IFS/SceneSpec Opaque"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (0.7, 0.7, 0.7, 1)
        _Brightness ("Brightness", Range(0, 1)) = 0.5
        _Roughness ("Roughness", Range(0, 1)) = 0.5
        _Opacity ("Opacity", Range(0, 1)) = 1
        _Erosion ("Erosion", Range(0, 1)) = 0
        _Lumpiness ("Lumpiness", Range(0, 0.5)) = 0.14
        _NoiseScale ("Noise Scale", Range(0.2, 6)) = 1.6
        _Seed ("Seed", Float) = 0
        _Fuzz ("Fuzz", Range(0, 1)) = 0
        _Density ("Density", Range(0, 1)) = 1
        _ShellOpen ("Shell Opening", Range(0, 1)) = 0
    }
    SubShader
    {
        Tags { "RenderType" = "TransparentCutout" "Queue" = "AlphaTest" }
        LOD 300

        Cull Front
        CGPROGRAM
        #pragma surface surfInside Standard vertex:ifsVert addshadow fullforwardshadows
        #pragma target 3.0
        #include "IFSSceneSpecCommon.cginc"
        void surfInside(Input IN, inout SurfaceOutputStandard o) { ifsSurface(IN, o, 1.0); }
        ENDCG

        Cull Back
        CGPROGRAM
        #pragma surface surfOutside Standard vertex:ifsVert addshadow fullforwardshadows
        #pragma target 3.0
        #include "IFSSceneSpecCommon.cginc"
        void surfOutside(Input IN, inout SurfaceOutputStandard o) { ifsSurface(IN, o, 0.0); }
        ENDCG
    }
    FallBack "Diffuse"
}
