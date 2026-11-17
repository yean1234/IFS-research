// 중립 회색 바닥 + 1 m 격자(스케일 기준). Built-in 렌더 파이프라인, 서피스 셰이더(그림자를 받는다).
// 격자선은 화면 미분(fwidth)으로 계단 없이 그리고, 멀어질수록 흐려진다(모아레 방지).
// 먼 바닥은 지평선 색으로 녹여 하늘과 이어지게 한다(전역 안개를 쓰지 않아 형상 색에는 영향이 없다).
Shader "IFS/Environment Floor"
{
    Properties
    {
        _BaseColor ("Base Color (sRGB)", Color) = (0.46, 0.46, 0.46, 1)
        _LineColor ("Grid Line Color (sRGB)", Color) = (0.39, 0.39, 0.39, 1)
        _MinorLineColor ("0.5 m Line Color (sRGB)", Color) = (0.43, 0.43, 0.43, 1)
        _LineWidth ("Grid Line Width (m)", Range(0.002, 0.05)) = 0.012
        _GridFadeDistance ("Grid Fade Distance (m)", Float) = 14
        _HorizonColor ("Horizon Color (sRGB)", Color) = (0.74, 0.74, 0.75, 1)
        _HorizonFadeStart ("Horizon Fade Start (m)", Float) = 18
        _HorizonFadeEnd ("Horizon Fade End (m)", Float) = 80
        _Smoothness ("Smoothness", Range(0, 1)) = 0.12
    }
    SubShader
    {
        Tags { "RenderType" = "Opaque" "Queue" = "Geometry" }
        LOD 200

        CGPROGRAM
        #pragma surface surfFloor Standard fullforwardshadows
        #pragma target 3.0

        fixed4 _BaseColor;
        fixed4 _LineColor;
        fixed4 _MinorLineColor;
        half _LineWidth;
        float _GridFadeDistance;
        fixed4 _HorizonColor;
        float _HorizonFadeStart;
        float _HorizonFadeEnd;
        half _Smoothness;

        struct Input
        {
            float3 worldPos;
        };

        // 간격 spacing(m)인 격자선의 덮임 정도(0–1). 화면에서 선보다 화소가 크면 흐리게 만든다.
        float gridLine(float2 p, float spacing, float width)
        {
            float2 q = p / spacing;
            float2 w = fwidth(q);
            float2 d = abs(frac(q - 0.5) - 0.5);                 // 가장 가까운 선까지(격자 단위)
            float2 halfW = (width / spacing) * 0.5;
            float2 l = 1.0 - smoothstep(halfW, halfW + w * 1.5, d);
            float2 fade = saturate(halfW * 2.0 / max(w, 1e-5));   // 선이 화소보다 가늘면 흐리게
            l *= fade;
            return max(l.x, l.y);
        }

        void surfFloor(Input IN, inout SurfaceOutputStandard o)
        {
            float2 p = IN.worldPos.xz;
            float dist = length(IN.worldPos.xz - _WorldSpaceCameraPos.xz);
            float gridFade = saturate(1.0 - dist / _GridFadeDistance);
            float major = gridLine(p, 1.0, _LineWidth) * gridFade;
            float minor = gridLine(p, 0.5, _LineWidth * 0.6) * gridFade * saturate(1.0 - dist / (_GridFadeDistance * 0.5));

            float3 col = _BaseColor.rgb;
            col = lerp(col, _MinorLineColor.rgb, minor);
            col = lerp(col, _LineColor.rgb, major);

            float horizon = smoothstep(_HorizonFadeStart, _HorizonFadeEnd, dist);
            o.Albedo = col * (1.0 - horizon);
            o.Emission = _HorizonColor.rgb * horizon;
            o.Metallic = 0.0;
            o.Smoothness = _Smoothness * (1.0 - horizon);
            o.Alpha = 1.0;
        }
        ENDCG
    }
    FallBack "Diffuse"
}
