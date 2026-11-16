// 무채색에 가까운 절차 하늘(스카이박스). 지평선 → 천정, 지평선 → 땅 두 그라디언트만 쓴다.
// 내장 Skybox/Procedural 대신 직접 쓴 이유: 대기 산란 하늘은 파랗게(채도 높게) 나와 형상 색 지각을 바꾸고,
// Shader.Find로 찾는 내장 셰이더는 빌드에서 빠질 수 있다(Resources 안 셰이더는 항상 포함).
// VR 단일 패스 인스턴싱을 위해 스테레오 매크로를 넣었다.
Shader "IFS/Environment Sky"
{
    Properties
    {
        _ZenithColor ("Zenith Color (sRGB)", Color) = (0.60, 0.62, 0.65, 1)
        _HorizonColor ("Horizon Color (sRGB)", Color) = (0.74, 0.74, 0.75, 1)
        _GroundColor ("Below-Horizon Color (sRGB)", Color) = (0.42, 0.42, 0.42, 1)
        _HorizonSharpness ("Horizon Sharpness", Range(0.1, 2)) = 0.6
        _Exposure ("Exposure", Range(0, 2)) = 1
    }
    SubShader
    {
        Tags { "Queue" = "Background" "RenderType" = "Background" "PreviewType" = "Skybox" }
        Cull Off
        ZWrite Off

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            #include "UnityCG.cginc"

            fixed4 _ZenithColor;
            fixed4 _HorizonColor;
            fixed4 _GroundColor;
            half _HorizonSharpness;
            half _Exposure;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 dir : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.dir = v.vertex.xyz;
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float y = normalize(i.dir).y;
                float up = pow(saturate(y), _HorizonSharpness);
                // 지평선 바로 아래(바닥 끝 너머)는 지평선 색을 유지해 바닥과 하늘 사이에 띠가 생기지 않게 한다
                float down = smoothstep(0.02, 0.3, -y);
                float3 c = y >= 0.0 ? lerp(_HorizonColor.rgb, _ZenithColor.rgb, up)
                                    : lerp(_HorizonColor.rgb, _GroundColor.rgb, down);
                return fixed4(c * _Exposure, 1.0);
            }
            ENDCG
        }
    }
    FallBack Off
}
