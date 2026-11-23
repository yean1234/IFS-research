// 배치 공간 후보 E(우주, G54)의 별 하늘(스카이박스). 에셋 없이 셰이더로 직접 그린다.
//   - 배경: 짙은 남색(완전한 검정이 아님 — 바닥 원판과 형상의 어두운 쪽이 배경에 묻히지 않게).
//   - 별: 방향 벡터를 3차원 격자로 나눠 칸마다 해시로 별 하나의 유무·자리·밝기·색온도를 정한다(두 층). 시간·난수 텍스처를 쓰지 않아
//     같은 방향은 언제나 같은 화소 값이다(결정적). 별이 화소보다 작으면 화소 크기만큼 넓히고 그만큼 어둡게 해 깜빡임을 줄인다.
//   - 성운: 기울어진 띠 둘레에만 옅게(값 잡음 3옥타브). 채도를 낮게 둔다(형상 색 지각을 끌어가지 않게).
// 규칙 이름: starfield/1(이 규칙을 바꾸면 C# EnvironmentStyle.StarfieldRule도 바꾼다). 내장 셰이더를 쓰지 않는 이유는
// EnvironmentSky.shader와 같다(Resources 안 셰이더는 빌드에 항상 포함). VR 단일 패스 인스턴싱 매크로를 넣었다.
Shader "IFS/Environment Starfield"
{
    Properties
    {
        _BackgroundColor ("Background (sRGB)", Color) = (0.030, 0.038, 0.085, 1)
        _NebulaColor ("Nebula (sRGB)", Color) = (0.11, 0.10, 0.20, 1)
        _NebulaStrength ("Nebula Strength", Range(0, 1)) = 0.45
        _StarScale ("Star Cell Scale (near layer)", Float) = 90
        _StarDensity ("Star Density (0-1 per cell)", Range(0, 1)) = 0.10
        _StarBrightness ("Star Brightness", Range(0, 4)) = 1.6
        _Seed ("Seed", Float) = 0
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

            fixed4 _BackgroundColor;
            fixed4 _NebulaColor;
            half _NebulaStrength;
            float _StarScale;
            half _StarDensity;
            half _StarBrightness;
            float _Seed;

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

            // 해시(정수 연산 없이 frac만 — 같은 입력이면 같은 값). Hoskins "Hash without Sine"의 hash43.
            float4 Hash43(float3 p)
            {
                float4 p4 = frac(float4(p.xyzx) * float4(0.1031, 0.1030, 0.0973, 0.1099));
                p4 += dot(p4, p4.wzxy + 33.33);
                return frac((p4.xxyz + p4.yzzw) * p4.zywx);
            }

            float ValueNoise(float3 p)
            {
                float3 i = floor(p);
                float3 f = frac(p);
                f = f * f * (3.0 - 2.0 * f);
                float n000 = Hash43(i).x,                      n100 = Hash43(i + float3(1, 0, 0)).x;
                float n010 = Hash43(i + float3(0, 1, 0)).x,    n110 = Hash43(i + float3(1, 1, 0)).x;
                float n001 = Hash43(i + float3(0, 0, 1)).x,    n101 = Hash43(i + float3(1, 0, 1)).x;
                float n011 = Hash43(i + float3(0, 1, 1)).x,    n111 = Hash43(i + float3(1, 1, 1)).x;
                return lerp(lerp(lerp(n000, n100, f.x), lerp(n010, n110, f.x), f.y),
                            lerp(lerp(n001, n101, f.x), lerp(n011, n111, f.x), f.y), f.z);
            }

            // 한 층의 별: 방향 d(단위 벡터)를 scale배 한 점이 든 칸의 별 하나
            // pxPerUnit = 화소 하나가 덮는 방향 벡터 길이(분기 밖에서 미리 잰다 — 도함수는 갈라진 흐름 안에서 정의되지 않는다)
            float3 StarLayer(float3 d, float scale, float seed, float pxPerUnit)
            {
                float3 p = d * scale;
                float3 cell = floor(p);
                float4 h = Hash43(cell + seed);
                float present = step(h.w, _StarDensity);
                // 칸 안 자리(가장자리에서 떨어지게 0.25–0.75)를 구면 위로 옮긴다
                float3 c = normalize(cell + 0.25 + 0.5 * h.xyz) * scale;
                float dist = length(p - c);
                float bright = pow(saturate(h.x * 0.6 + h.y * 0.4), 6.0) * 0.95 + 0.05;   // 어두운 별이 많고 밝은 별은 드물게
                float radius = lerp(0.045, 0.11, h.z);
                // 화소 크기보다 작으면 넓히고 넓힌 만큼 어둡게(면적 보존) — 헤드 움직임에서 깜빡임을 줄인다
                float px = max(pxPerUnit * scale, 1e-4);
                float r = max(radius, px * 0.75);
                float energy = (radius * radius) / (r * r);
                float s = present * exp(-dist * dist / (r * r)) * bright * energy;
                float3 warm = float3(1.0, 0.93, 0.84), cool = float3(0.82, 0.88, 1.0);
                return s * lerp(cool, warm, h.y);
            }

            fixed4 frag(v2f i) : SV_Target
            {
                float3 d = normalize(i.dir);
                float pxPerUnit = length(fwidth(d));
                float3 col = _BackgroundColor.rgb;

                // 성운: 기울어진 띠(법선 고정) 둘레에만
                float3 bandNormal = normalize(float3(0.35, 0.82, 0.45));
                float band = exp(-pow(dot(d, bandNormal) / 0.38, 2.0));
                float3 q = d * 2.3 + _Seed;
                float n = ValueNoise(q) * 0.55 + ValueNoise(q * 2.1) * 0.30 + ValueNoise(q * 4.3) * 0.15;
                float neb = smoothstep(0.36, 0.80, n) * band * _NebulaStrength;
                col = lerp(col, _NebulaColor.rgb, saturate(neb));

                float3 stars = StarLayer(d, _StarScale, _Seed, pxPerUnit) + 0.55 * StarLayer(d, _StarScale * 2.3, _Seed + 17.0, pxPerUnit);
                col += stars * _StarBrightness;
                return fixed4(col, 1.0);
            }
            ENDCG
        }
    }
    FallBack Off
}
