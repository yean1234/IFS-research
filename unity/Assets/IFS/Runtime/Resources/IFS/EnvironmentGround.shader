// 배치 공간 후보 F(자연, G55)의 발밑 땅: 참여자 둘레의 큰 원판. 스카이스피어(사진)는 시차가 없어 실제로 놓을 땅이 필요하다.
//   - 색 = 사진 지평선 바로 아래 땅 띠의 평균 색(C# NatureSkyAsset.GroundSrgb, 사진에서 미리 잰 값). 빛을 다시 받지 않는다(사진의 땅도 이미 빛을 받은 색).
//   - 결: 세계 xz 값 잡음 두 크기(약 0.6 m·2.5 m)로 밝기만 ±_NoiseStrength/2 흔든다(해시라 결정적, 시간 없음).
//   - 가장자리: 반지름 _FadeStart → _FadeEnd에서 알파 1 → 0. 그 너머는 사진의 땅이 보인다(이음매가 띠로 보이지 않게).
//   - 투명 큐(Transparent-50): 스카이박스 다음, 반투명 형상(안개 등)보다 먼저 그린다. 깊이를 쓰지 않는다.
// 배치 원판(PlacementSpace, 불투명)은 이 위(y = 0)에 그대로 남는다. VR 단일 패스 인스턴싱 매크로를 넣었다.
Shader "IFS/Environment Ground"
{
    Properties
    {
        _BaseColor ("Ground Color (sRGB)", Color) = (0.32, 0.34, 0.25, 1)
        _NoiseStrength ("Brightness Variation", Range(0, 0.5)) = 0.16
        _FadeStart ("Fade Start (m)", Float) = 20
        _FadeEnd ("Fade End (m)", Float) = 60
    }
    SubShader
    {
        Tags { "Queue" = "Transparent-50" "RenderType" = "Transparent" "IgnoreProjector" = "True" }
        Blend SrcAlpha OneMinusSrcAlpha
        ZWrite Off
        Cull Back

        Pass
        {
            CGPROGRAM
            #pragma vertex vert
            #pragma fragment frag
            #pragma target 3.0
            #include "UnityCG.cginc"

            fixed4 _BaseColor;
            half _NoiseStrength;
            float _FadeStart;
            float _FadeEnd;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 world : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vert(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.world = mul(unity_ObjectToWorld, v.vertex).xyz;
                return o;
            }

            float Hash12(float2 p)
            {
                float3 p3 = frac(float3(p.xyx) * 0.1031);
                p3 += dot(p3, p3.yzx + 33.33);
                return frac((p3.x + p3.y) * p3.z);
            }

            float Noise2(float2 p)
            {
                float2 i = floor(p), f = frac(p);
                f = f * f * (3.0 - 2.0 * f);
                return lerp(lerp(Hash12(i), Hash12(i + float2(1, 0)), f.x),
                            lerp(Hash12(i + float2(0, 1)), Hash12(i + float2(1, 1)), f.x), f.y);
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float2 xz = i.world.xz;
                float n = Noise2(xz / 0.6) * 0.5 + Noise2(xz / 2.5 + 31.7) * 0.5;
                float3 col = _BaseColor.rgb * (1.0 + (n - 0.5) * _NoiseStrength);
                float r = length(xz);
                float a = 1.0 - smoothstep(_FadeStart, _FadeEnd, r);
                return fixed4(col, a);
            }
            ENDCG
        }
    }
    FallBack Off
}
