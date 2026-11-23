// 배치 공간 후보 F(자연, G55)의 하늘: 등장방형(equirectangular) 360° 사진 한 장을 스카이박스로 씌운다.
// 내장 Skybox/Panoramic 대신 직접 쓴 이유는 EnvironmentSky.shader와 같다(Resources 안 셰이더는 빌드에 항상 포함, Shader.Find 안 씀).
//   - 방향 → (u, v): u = 0.5 + atan2(x, z) / 2π(정면 +z = 사진 가운데, 오른쪽 = 사진 오른쪽), v = 0.5 + asin(y) / π(아래 = 사진 아래).
//   - 밉맵 이음매: atan2가 정 뒤에서 −π → π로 뛰어 그 화소의 도함수가 커지고 가장 작은 밉이 찍혀 세로 금이 생긴다.
//     정 뒤에 이음매가 없는 u2 = frac(u + 0.5)의 도함수와 비교해 작은 쪽을 tex2Dgrad에 준다.
//   - 텍스처는 sRGB로 불러와 선형으로 읽힌다. 노출은 1(사진 그대로), 회전(_Rotation, 도)은 Y축 둘레.
// VR 단일 패스 인스턴싱 매크로를 넣었다.
Shader "IFS/Environment Panorama"
{
    Properties
    {
        [NoScaleOffset] _MainTex ("Equirectangular (sRGB)", 2D) = "grey" {}
        _Rotation ("Rotation (deg, Y)", Range(0, 360)) = 0
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

            sampler2D _MainTex;
            float _Rotation;
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
                float a = radians(_Rotation);
                float s = sin(a), c = cos(a);
                float3 d = v.vertex.xyz;
                o.dir = float3(c * d.x - s * d.z, d.y, s * d.x + c * d.z);
                return o;
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float u = 0.5 + atan2(d.x, d.z) * (0.5 / UNITY_PI);
                float v = 0.5 + asin(clamp(d.y, -1.0, 1.0)) * (1.0 / UNITY_PI);
                float u2 = frac(u + 0.5);
                float dux = ddx(u), duy = ddy(u), dux2 = ddx(u2), duy2 = ddy(u2);
                float2 gx = float2(abs(dux) < abs(dux2) ? dux : dux2, ddx(v));
                float2 gy = float2(abs(duy) < abs(duy2) ? duy : duy2, ddy(v));
                float3 col = tex2Dgrad(_MainTex, float2(u, v), gx, gy).rgb;
                return fixed4(col * _Exposure, 1.0);
            }
            ENDCG
        }
    }
    FallBack Off
}
