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

        // 안쪽 면 패스에는 addshadow를 붙이지 않는다. Built-in은 패스 안의 첫 ShadowCaster를 카메라 깊이 텍스처(화면 공간 그림자)에
        // 쓰는데, 안쪽(Cull Front) 것이 먼저면 깊이 텍스처에 형상 뒤쪽 면이 들어간다. 그러면 바깥 면의 그림자를 엉뚱한 위치에서
        // 읽고, 침식 구멍 뒤로 바닥이 보이는 곳은 바닥 깊이로 읽어 바닥 유무에 따라 형상 밝기가 달라졌다(BatchCapture 진단, 2026-11-16).
        Cull Front
        CGPROGRAM
        #pragma surface surfInside Standard vertex:ifsVert fullforwardshadows
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
