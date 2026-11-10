// SceneSpec 반투명 셰이더 (mist, 또는 opacity < 1). Built-in 렌더 파이프라인.
// _Fuzz가 클수록 가장자리가 흐려지고 노이즈로 안개처럼 듬성듬성해진다.
Shader "IFS/SceneSpec Fade"
{
    Properties
    {
        _BaseColor ("Base Color", Color) = (0.7, 0.7, 0.7, 1)
        _Brightness ("Brightness", Range(0, 1)) = 0.5
        _Roughness ("Roughness", Range(0, 1)) = 0.5
        _Opacity ("Opacity", Range(0, 1)) = 1
        _Erosion ("Erosion", Range(0, 1)) = 0
        _Lumpiness ("Lumpiness", Range(0, 0.5)) = 0.3
        _NoiseScale ("Noise Scale", Range(0.2, 6)) = 1.1
        _Seed ("Seed", Float) = 0
        _Fuzz ("Fuzz", Range(0, 1)) = 1
        _Density ("Density", Range(0, 1)) = 0.5
        _ShellOpen ("Shell Opening", Range(0, 1)) = 0
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "IgnoreProjector" = "True" }
        LOD 300
        Cull Back
        ZWrite Off

        CGPROGRAM
        #pragma surface surfFade Standard vertex:ifsVert alpha:fade
        #pragma target 3.0
        #include "IFSSceneSpecCommon.cginc"

        void surfFade(Input IN, inout SurfaceOutputStandard o)
        {
            ifsSurface(IN, o, 0.0);
            float wisp = ifsFbm(ifsNoiseCoord(IN.objPos) * 2.7 + 9.3);
            float soft = lerp(1.0, pow(IN.rim, 1.5) * (0.4 + 1.2 * wisp), _Fuzz);
            o.Alpha = saturate(_Opacity * _Density * soft);
        }
        ENDCG
    }
    FallBack "Transparent/Diffuse"
}
