// SceneSpec 안개 셰이더(mist, X66). Built-in 렌더 파이프라인, 정점·프래그먼트 셰이더.
// 구 대리 메시 하나를 그리고, 물체 좌표에서 짧은 레이마칭(IFS_MIST_STEPS걸음)으로 밀도를 쌓는다.
//   밀도 = 반지름 감쇠(낮은 주파수 노이즈로 흔든 반지름) × 3D 노이즈(문턱을 둔 덩이) × 침식 결손. 윤곽이 깨끗한 원이 아니라 몽글몽글하게 풀린다.
//   면 고르기(Cull Off, 한 패스): 카메라가 구 밖이면 앞면만(입구 → 출구), 구 안이면 안쪽 면만(카메라 → 출구) 남기고 나머지는 버린다.
//   처음 안(X66)은 안쪽 면(Cull Front)만 그리는 것이었으나, 바닥에 놓인 안개(held-out H02: verticalOffset 0.04)는 구 뒤쪽이 바닥 아래라
//   깊이 테스트에서 거의 다 사라졌다(보이는 화소 41,834 → 763). 앞면으로 깊이 테스트를 하면 바닥 위 부분이 그대로 보인다.
//   앞뒤 판정은 VFACE(렌더 텍스처 뒤집기에 따라 부호가 바뀔 수 있음) 대신 dot(물체 좌표, 광선 방향)으로 한다.
//   _FloorY(세계 높이, 로더가 배치 설정의 바닥 높이를 넣음) 아래의 표본은 밀도 0 — 광선이 바닥을 뚫고 땅속 안개를 쌓지 않게.
// 재질 슬롯(로더가 넣는 값, 모두 0–1):
//   _BaseColor  밀도의 색(HSL → sRGB, 채도어는 SceneParams가 이미 s에 넣음)
//   _Brightness 밝기 배율 lerp(0.4, 1, saturate(2B)) — IFSSceneSpecCommon.cginc·C# RenderedColor.BrightnessFactor와 같은 식.
//               0.5 초과분은 발광(색 × (B − 0.5) × 2.4, 기존 방식)
//   _Opacity    밀도 배율. 중심 광선의 누적 알파 ≈ saturate(_Opacity × _Density)가 되도록 광학 깊이를 맞춘다
//               (= C# RenderedColor.SurfaceAlpha(mist) = opacity × 형태 밀도 0.5와 같은 정의. 노이즈 평균 기준이라 화소마다 다르다)
//   _Roughness  노이즈 크기 배율 lerp(0.7, 1.3, R) — 기본값 0.5에서 1(프리셋 _NoiseScale 그대로), 거칠수록 결이 잘다. 얼룩 세기도 기존 식
//   _Erosion    밀도 결손(노이즈가 기준보다 낮은 곳의 밀도를 0으로, 기존 Opaque의 침식과 같은 문턱 erosion × 0.62)
// 형상 프리셋(로더가 넣음): _Lumpiness(반지름 흔들림), _NoiseScale, _Density(0.5), _Seed. _Fuzz·_ShellOpen·_Displacement는 쓰지 않는다.
// 그림자 없음(U5): ShadowCaster 패스가 없고 FallBack도 없다. 투명 겹침 1층(ZWrite Off), 드로콜 1.
// 한계: 카메라가 구 안에 있고 구 뒤쪽이 바닥 아래면, 바닥을 내려다보는 화소의 안개가 빠진다(안쪽 면이 바닥에 가려짐. 매우 큰 안개만).
// Quest(GLES3/Vulkan 모바일)에서 컴파일되도록 고정 횟수 루프·텍스처 없는 해시 노이즈(공통 cginc)만 쓴다.
Shader "IFS/SceneSpec Mist"
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
        _Density ("Density", Range(0, 1)) = 0.5
        _FloorY ("Floor Height (world)", Float) = -10000
    }
    SubShader
    {
        Tags { "RenderType" = "Transparent" "Queue" = "Transparent" "IgnoreProjector" = "True" }
        LOD 300

        Pass
        {
            Tags { "LightMode" = "ForwardBase" }
            Cull Off
            ZWrite Off
            ZTest LEqual
            Blend One OneMinusSrcAlpha   // 미리 곱한 알파(앞에서 뒤로 쌓은 색 = 색 × 알파)

            CGPROGRAM
            #pragma vertex vertMist
            #pragma fragment fragMist
            #pragma target 3.0
            #pragma multi_compile_instancing
            #include "UnityCG.cginc"
            #include "UnityPBSLighting.cginc"
            #include "IFSSceneSpecCommon.cginc"

            // 레이마칭 걸음 수(상수). 바꾸면 C# FormRenderPlan.MistSteps도 같이(테스트가 확인).
            #define IFS_MIST_STEPS 8
            // 구 대리 반지름(물체 좌표). C# FormRenderResources.MistRadius와 같게.
            #define IFS_MIST_RADIUS 0.75
            // 중심 광선의 ∫(반지름 감쇠 × 덩이) ds의 평균 ≈ 1.0 × 반지름(감쇠 평균 약 0.49 × 2R × 덩이 평균 약 1.0)
            #define IFS_MIST_CENTER_INTEGRAL 1.0

            float _FloorY;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 objPos : TEXCOORD0;
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vertMist(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.objPos = v.vertex.xyz;
                return o;
            }

            float mistFbm2(float3 p)
            {
                return 0.5 * ifsNoise(p) + 0.25 * ifsNoise(p * 2.03 + 17.1);   // 대략 0–0.75, 평균 ≈ 0.375
            }

            // 한 점의 밀도(0–2)와 얼룩 값.
            // 부피를 화면에 투영하면 광선 방향으로 노이즈가 평균되어 윤곽이 둥글어진다 → 윤곽을 흔드는 노이즈는 낮은 주파수·큰 진폭(큰 덩이),
            // 안쪽은 문턱을 둔 덩이(뭉친 곳과 빈 곳)로 둔다.
            float mistDensity(float3 p, float noiseMul, out float mottle)
            {
                float3 q = (p * _NoiseScale + _Seed * 13.7) * noiseMul;
                // 큰 덩이: 2옥타브(0–0.75, 평균 ≈ 0.375). 지름에 노이즈 격자 약 3칸(기존 Fade 정점 변위의 2·3옥타브 크기)
                float lump = mistFbm2(q * 2.4);
                // 반지름 감쇠: 기준 반지름 0.65R을 노이즈로 흔든다(_Lumpiness 0.3 → ±약 0.3). 가장자리 0.5 폭에 걸쳐 0으로.
                // 흔든 경계가 대리 구(반지름 R) 밖으로 나가지 않게 기준을 0.65R로 둔다(구 표면에서 잘린 원이 보이지 않게)
                float edge = length(p) / (IFS_MIST_RADIUS * 0.65) + (lump - 0.375) * _Lumpiness * 4.0;
                float shape = smoothstep(0.0, 0.5, 1.0 - edge);
                // 안쪽 덩이: 문턱을 둔 노이즈(0–1, 평균 ≈ 0.5) × 2
                float clump = mistFbm2(q * 5.0 + 9.3) / 0.75;
                mottle = clump;
                float d = shape * 2.0 * smoothstep(0.3, 0.75, clump);
                // 침식: 노이즈가 기준보다 낮은 곳의 밀도를 없앤다(Opaque의 clip과 같은 문턱)
                if (_Erosion > 0.001)
                {
                    float en = mistFbm2(q * 2.3 + 5.1) / 0.75;
                    d *= saturate((en - _Erosion * 0.62) / 0.06);
                }
                return d;
            }

            fixed4 fragMist(v2f i) : SV_Target
            {
                UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);
                // 물체 좌표 광선(눈마다 카메라 위치가 다르다: 스테레오 인스턴싱이면 _WorldSpaceCameraPos가 눈별 값)
                float3 ro = mul(unity_WorldToObject, float4(_WorldSpaceCameraPos, 1.0)).xyz;
                float3 rd = normalize(i.objPos - ro);
                float b = dot(ro, rd);
                float c = dot(ro, ro) - IFS_MIST_RADIUS * IFS_MIST_RADIUS;
                float h = b * b - c;
                if (h <= 0.0) discard;
                // 구 밖이면 앞면(바깥을 향한 면이 카메라 쪽), 구 안이면 안쪽 면만
                bool frontFace = dot(i.objPos, rd) < 0.0;
                bool inside = dot(ro, ro) < IFS_MIST_RADIUS * IFS_MIST_RADIUS;
                if (frontFace == inside) discard;
                float sq = sqrt(h);
                float t0 = max(-b - sq, 0.0);   // 카메라가 구 안이면 카메라에서 시작
                float t1 = -b + sq;
                if (t1 <= t0) discard;
                float dt = (t1 - t0) / IFS_MIST_STEPS;
                // 화소마다 고정된 시작 흔들기(걸음 무늬 줄이기). 화면 좌표만 쓰므로 같은 화면이면 같은 값
                float jitter = 0.5;   // 걸음 가운데에서 표본(화소별 흔들기는 결정적이지만 화면에 낟알 무늬를 남겨 쓰지 않는다)

                // 목표 중심 알파 A = saturate(opacity × 형태 밀도) → 광학 깊이 τ = −ln(1 − A)
                float target = min(saturate(_Opacity * _Density), 0.995);
                float sigma = -log(1.0 - target) / (IFS_MIST_CENTER_INTEGRAL * IFS_MIST_RADIUS);
                float noiseMul = lerp(0.7, 1.3, _Roughness);

                float bright = lerp(0.4, 1.0, saturate(_Brightness * 2.0));   // RenderedColor.BrightnessFactor와 같은 식
                float3 baseCol = _BaseColor.rgb;
                float3 lightDir = normalize(_WorldSpaceLightPos0.xyz);
                float3 emission = saturate(_Brightness - 0.5) * 2.4;

                float3 acc = 0;
                float accA = 0;
                [unroll]
                for (int k = 0; k < IFS_MIST_STEPS; k++)
                {
                    float3 p = ro + rd * (t0 + (k + jitter) * dt);
                    float mottle;
                    float d = mistDensity(p, noiseMul, mottle);
                    // 바닥 아래(세계 높이 < _FloorY)는 밀도 0
                    if (dot(unity_ObjectToWorld[1], float4(p, 1.0)) < _FloorY) d = 0.0;
                    float a = 1.0 - exp(-sigma * d * dt);
                    // 조명: 구 바깥 방향을 법선으로 한 감싼 확산(빛이 안개 속으로 번지는 근사, (N·L + 0.5)/1.5) + 주변광(구면 조화)
                    float3 n = normalize(UnityObjectToWorldNormal(p + 1e-4));
                    float3 lit = _LightColor0.rgb * saturate((dot(n, lightDir) + 0.5) / 1.5) + ShadeSH9(float4(n, 1.0));
                    float3 col = baseCol * lerp(1.0, 0.7 + 0.6 * mottle, 0.25 + 0.6 * _Roughness);   // 거칠수록 얼룩
                    float3 c3 = col * bright * lit + col * emission;
                    acc += (1.0 - accA) * a * c3;
                    accA += (1.0 - accA) * a;
                }
                return fixed4(acc, accA);
            }
            ENDCG
        }
    }
    FallBack Off
}
