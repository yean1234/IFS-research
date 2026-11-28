// SceneSpec 안개 셰이더(mist, X66 → D7 2026-11-23). Built-in 렌더 파이프라인, 정점·프래그먼트 셰이더.
// 구 대리 메시 하나를 그리고, 물체 좌표에서 짧은 레이마칭(IFS_MIST_STEPS걸음)으로 밀도를 쌓는다(드로콜 1, 투명 겹침 1층 — X66 그대로).
// D7에서 바꾼 것(docs/validation/cloud/README.md):
//   밀도장 = 둥근 덩어리 IFS_MIST_LUMPS개의 합집합(가장 깊이 들어간 덩어리 기준 깊이) + 중간 주파수 노이즈(겉면을 흔들고 속을 얼룩지게).
//     덩어리 중심·반지름은 C# MistLumps.Build(seed)가 정해 _Lump0…_Lump4(xyz = 중심, w = 반지름)로 넣는다(같은 seed → 같은 구름).
//     이전 밀도장(흔든 반지름 감쇠 × 문턱 덩이 노이즈)은 흐린 얼룩 하나로 보여 구름 덩어리로 읽히지 않았다(mock-forms 시트 M01·M02).
//   알파: 덩어리 속은 누적 알파가 opacity 가까이까지 찬다. 최종 알파 = opacity × (덩어리 밀도로 쌓은 알파). opacity는 spec 값 그대로이고
//     그 위로 올리지 않는다(X70: 바닥값·윤곽선 보정 없음). 이전에는 중심 광선 알파의 목표를 opacity × _Density(0.5)로 두어 가장 짙은 곳도 0.5였다.
//     _Density(형태 밀도 프리셋 0.5, 숫자 그대로)는 이제 광학 두께 배율이다(σ = _Density × IFS_MIST_KAPPA). C# RenderedColor.SurfaceAlpha(mist)
//     = opacity × 0.5는 "안개가 덮은 화면 넓이의 평균 알파"에 가까운 값으로 남는다(측정: docs/validation/cloud/README.md).
//   음영: 표본마다 덩어리 바깥 방향(가장 깊이 들어간 덩어리 쪽으로 기운 가중 평균)을 법선으로 감싼 확산 + 덩어리 안에서 빛 쪽으로 남은 두께만큼의 자기 그림자
//     + 주변광(구면 조화, 위가 밝고 아래가 어둡다). 덩어리마다 위가 밝고 아래가 어두워 배경과 밝기가 비슷한 색이라도 덩이가 읽힌다.
//     색·밝기 슬롯 값은 바꾸지 않는다(빛이 어떻게 비치는가만 다르다. 불투명 형상의 Standard 조명이 아랫면을 어둡게 하는 것과 같은 종류).
//   걸음 구간: 대리 구 전체가 아니라 덩어리 전체(노이즈 여유 포함)를 감싼 구와 겹치는 구간만 8걸음으로 나눈다.
//     광선이 그 구에 닿지 않으면 버린다.
// 면 고르기(Cull Off, 한 패스): 카메라가 구 밖이면 앞면만, 구 안이면 안쪽 면만 남긴다(바닥에 놓인 안개가 깊이 테스트로 사라지지 않게).
//   앞뒤 판정은 VFACE 대신 dot(물체 좌표, 광선 방향)으로 한다.
// _FloorY(세계 높이, 로더가 배치 설정의 바닥 높이를 넣음) 아래의 표본은 밀도 0.
// 재질 슬롯(로더가 넣는 값, 모두 0–1):
//   _BaseColor  밀도의 색(HSL → sRGB)
//   _Brightness 밝기 배율 lerp(0.4, 1, saturate(2B)) — IFSSceneSpecCommon.cginc·C# RenderedColor.BrightnessFactor와 같은 식. 0.5 초과분은 발광(색 × (B − 0.5) × 2.4)
//   _Opacity    최종 알파 배율(덩어리 속 최대 알파 ≈ opacity)
//   _Roughness  표면 반사(광택)가 아니다. 노이즈 크기 배율 lerp(0.7, 1.3, R)과 색 얼룩 세기(기존 식 lerp(1, 0.7 + 0.6·얼룩, 0.25 + 0.6R))
//   _IfsEmission (2.3) 발광 항(선형 RGB, 기본 0) — 표본 색에 더한다(IFSSceneSpecCommon.cginc와 같은 값)
//   _Erosion    밀도 결손(노이즈가 기준보다 낮은 곳의 밀도를 0으로, 기존 Opaque의 침식과 같은 문턱 erosion × 0.62)
// 형상 프리셋(로더가 넣음): _Lump0…_Lump4, _Lumpiness(겉면 노이즈 진폭 배율), _NoiseScale, _Density(0.5), _Seed. _Fuzz·_ShellOpen·_Displacement는 쓰지 않는다.
// (2.4 선택, G74) 안개 입자 모양(form.mistKind, C# MistKinds) — 종류별 형상 프리셋. 기본값(곱하기 1·더하기 0)이면 위 식 그대로(cloud·null = 2.4 이전 화소):
//   _EdgeRampMul  가장자리 폭 배율(IFS_MIST_EDGE_RAMP × 이 값). fog 3(부드럽게), smoke 1.3
//   _Squash       밀도장 좌표 배율(xyz, 각 1 이상): 덩어리 거리를 p ⊙ squash에서 잰다(fog y 2 = 납작한 덩어리). 음영 법선도 같은 배율(타원체 법선)
//   _NoiseStretch 노이즈 좌표 배율(xyz): smoke y 0.35 = 세로로 늘인 결(가닥), fog y 2.2 = 가로 결(층)
//   _Twist        높이에 따른 노이즈 비틀림(라디안/물체 좌표 길이, smoke 6) — 꼬인 가닥
//   _Strands      가닥 세기(0–1, smoke 0.45): 가닥 노이즈가 낮은 곳의 밀도를 줄인다
//   _HeightFade   (y0, y1): y0 위로 옅어져 y1에서 0(smoke 0.30–0.66 — 위로 갈수록 흩어짐). y1 ≤ y0이면 감쇠 없음
//   덩어리 배치(_Lump0…)는 C# MistKinds.BuildLumps가 종류별로 정한다(fog: 옆으로 넓고 낮게, smoke: 세로로 쌓인 기둥).
//   dust(먼지·모래·가루)는 이 셰이더를 쓰지 않는다(알갱이 메시 DustMesh + IFS 반투명 셰이더).
// 그림자 없음(U5): ShadowCaster 패스가 없고 FallBack도 없다. 투명 겹침 1층(ZWrite Off), 드로콜 1.
// 한계: 카메라가 구 안에 있고 구 뒤쪽이 바닥 아래면, 바닥을 내려다보는 화소의 안개가 빠진다. 걸음 사이 간격 때문에 덩어리 가장자리에 옅은 층 무늬가 남을 수 있다.
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
        _IfsEmission ("Emission (linear, 2.3)", Color) = (0, 0, 0, 0)
        // 덩어리(물체 좌표 xyz = 중심, w = 반지름). 로더가 MistLumps.Build(seed)로 채운다. 기본값은 seed 0이 아니라 대략의 자리(로더가 늘 덮어씀)
        _Lump0 ("Lump 0", Vector) = (0, -0.04, 0, 0.35)
        _Lump1 ("Lump 1", Vector) = (0.29, 0.12, 0, 0.24)
        _Lump2 ("Lump 2", Vector) = (0, -0.07, 0.29, 0.24)
        _Lump3 ("Lump 3", Vector) = (-0.29, 0.15, 0, 0.24)
        _Lump4 ("Lump 4", Vector) = (0, -0.04, -0.29, 0.24)
        // (G74) 종류별 형상 프리셋(로더가 MistKinds로 넣음). 기본값 = cloud(2.4 이전 그림)
        _EdgeRampMul ("Edge Ramp Mul", Range(0.2, 4)) = 1
        _Squash ("Squash", Vector) = (1, 1, 1, 0)
        _NoiseStretch ("Noise Stretch", Vector) = (1, 1, 1, 0)
        _Twist ("Twist", Float) = 0
        _Strands ("Strands", Range(0, 1)) = 0
        _HeightFade ("Height Fade", Vector) = (0, 0, 0, 0)
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
            // 덩어리 수. C# MistLumps.Count와 같게(테스트가 확인).
            #define IFS_MIST_LUMPS 5
            // 덩어리 겉면에서 안쪽으로 밀도가 0 → 1로 오르는 폭(물체 좌표). C# MistLumps.EdgeRamp와 같게.
            #define IFS_MIST_EDGE_RAMP 0.10
            // 광학 두께 배율: σ = _Density × IFS_MIST_KAPPA(물체 좌표 길이당). 프리셋 0.5에서 σ = 8 → 반지름 0.3 덩어리 한가운데를 지나는 광선의
            // 광학 깊이 ≈ 8 × (0.6 − 0.1) = 4(알파 ≈ 0.98 × opacity)
            #define IFS_MIST_KAPPA 16.0
            // 겉면 노이즈 진폭(물체 좌표) = _Lumpiness × 이 값. 프리셋 0.3 → ±0.06
            #define IFS_MIST_EDGE_NOISE 0.4

            float _FloorY;
            float4 _Lump0, _Lump1, _Lump2, _Lump3, _Lump4;
            float _EdgeRampMul, _Twist, _Strands;
            float4 _Squash, _NoiseStretch, _HeightFade;

            struct appdata
            {
                float4 vertex : POSITION;
                UNITY_VERTEX_INPUT_INSTANCE_ID
            };

            struct v2f
            {
                float4 pos : SV_POSITION;
                float3 objPos : TEXCOORD0;
                UNITY_VERTEX_INPUT_INSTANCE_ID   // 조각 단계도 물체 행렬(unity_WorldToObject)을 쓰므로 인스턴스 ID를 넘긴다(GPU 인스턴싱·스테레오 인스턴싱)
                UNITY_VERTEX_OUTPUT_STEREO
            };

            v2f vertMist(appdata v)
            {
                v2f o;
                UNITY_SETUP_INSTANCE_ID(v);
                UNITY_INITIALIZE_OUTPUT(v2f, o);
                UNITY_TRANSFER_INSTANCE_ID(v, o);
                UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);
                o.pos = UnityObjectToClipPos(v.vertex);
                o.objPos = v.vertex.xyz;
                return o;
            }

            float4 mistLump(int k)
            {
                return k == 0 ? _Lump0 : k == 1 ? _Lump1 : k == 2 ? _Lump2 : k == 3 ? _Lump3 : _Lump4;
            }

            float mistFbm2(float3 p)
            {
                return 0.5 * ifsNoise(p) + 0.25 * ifsNoise(p * 2.03 + 17.1);   // 대략 0–0.75, 평균 ≈ 0.375
            }

            // 광선(ro + t·rd)과 구(중심 c, 반지름 r)의 교차 구간. 닿지 않으면 (1e5, −1e5).
            float2 mistSphere(float3 ro, float3 rd, float3 c, float r)
            {
                float3 oc = ro - c;
                float b = dot(oc, rd);
                float h = b * b - (dot(oc, oc) - r * r);
                if (h <= 0.0) return float2(1e5, -1e5);
                float s = sqrt(h);
                return float2(-b - s, -b + s);
            }

            // (G74) 광선 ro' + t·rd'(rd'는 단위 길이가 아님 — 물체 좌표 광선을 밀도장 공간으로 옮긴 것)과 원점 중심 구(반지름 r)의 교차 구간.
            // t는 물체 좌표 광선의 t와 같다. 닿지 않으면 (1e5, −1e5).
            float2 mistEllipsoid(float3 ro, float3 rd, float r)
            {
                float a = dot(rd, rd);
                float b = dot(ro, rd);
                float h = b * b - a * (dot(ro, ro) - r * r);
                if (h <= 0.0) return float2(1e5, -1e5);
                float s = sqrt(h);
                return float2((-b - s) / a, (-b + s) / a);
            }

            // 덩어리 음영의 부드러운 가중치: w_k = exp(IFS_MIST_SHADE_SOFT × (f_k − f_max)). 덩이 사이 이음매에서 법선·자기 그림자가 갑자기 바뀌지 않게
            #define IFS_MIST_SHADE_SOFT 30.0

            // 한 점의 밀도(0–1.2)와 얼룩 값, 음영용 법선 방향(물체 좌표, 덩어리 바깥 방향의 가중 평균)과 빛 쪽 덩어리 두께.
            //   깊이 f = max_k(r_k − |p − c_k|)  (덩어리 겉면 = 0, 안쪽 +) — C# MistLumps.ShapeDensity와 같은 뼈대
            //   겉면 흔들기: f += (중간 주파수 노이즈 − 평균) × 진폭 → 둥근 덩이의 윤곽이 몽글몽글하게 풀린다
            //   밀도 = saturate(f / 가장자리 폭) × 속 얼룩(0.75–1.2)
            float mistDensity(float3 p, float noiseMul, float3 lightObj, out float mottle, out float3 nObj, out float thick)
            {
                // (G74) 밀도장 공간: 덩어리 거리는 p ⊙ _Squash에서 잰다(기본 (1, 1, 1) — 2.4 이전과 같은 값)
                float3 ps = p * _Squash.xyz;
                float fk[IFS_MIST_LUMPS];
                float f = -1e5;
                [unroll]
                for (int k = 0; k < IFS_MIST_LUMPS; k++)
                {
                    float4 L = mistLump(k);
                    fk[k] = L.w - length(ps - L.xyz);
                    f = max(f, fk[k]);
                }
                // 음영: 가장 깊이 들어간 덩어리 쪽으로 기운 가중 평균(덩이마다 위가 밝고 아래가 어둡다)
                nObj = 0;
                thick = 0;
                float wsum = 0;
                [unroll]
                for (int j = 0; j < IFS_MIST_LUMPS; j++)
                {
                    float4 L = mistLump(j);
                    float w = exp(IFS_MIST_SHADE_SOFT * (fk[j] - f));
                    nObj += w * normalize(ps - L.xyz + 1e-5);
                    thick += w * max(mistSphere(ps, lightObj, L.xyz, L.w).y, 0.0);
                    wsum += w;
                }
                thick /= wsum;
                nObj *= _Squash.xyz;   // (G74) 눌린 덩어리(타원체)의 법선. 기본 (1, 1, 1)이면 그대로
                // (G74) 노이즈 좌표: 높이에 따라 비틀고(_Twist) 축마다 늘인다(_NoiseStretch). 기본값이면 p 그대로
                float3 pn = p;
                if (_Twist != 0.0)
                {
                    float a = _Twist * p.y;
                    float ca = cos(a), sa = sin(a);
                    pn.xz = float2(ca * p.x - sa * p.z, sa * p.x + ca * p.z);
                }
                float3 q = (pn * _NoiseStretch.xyz * _NoiseScale + _Seed * 13.7) * noiseMul;
                // 중간 주파수: 덩어리 지름(약 0.5)에 노이즈 격자 약 3칸
                float n = mistFbm2(q * 5.5);
                f += (n - 0.375) * _Lumpiness * IFS_MIST_EDGE_NOISE * 2.0;
                float inner = ifsNoise(q * 9.0 + 9.3);
                mottle = inner;
                float d = saturate(f / (IFS_MIST_EDGE_RAMP * _EdgeRampMul)) * lerp(0.75, 1.2, inner);
                // (G74) 가닥: 비튼·늘인 노이즈가 낮은 곳의 밀도를 줄인다(smoke). 0이면 건너뜀
                if (_Strands > 0.001)
                {
                    float sn = ifsNoise(q * 4.5 + 3.1);
                    d *= lerp(1.0, saturate((sn - 0.3) * 2.5), _Strands);
                }
                // (G74) 높이 감쇠: y0 위로 옅어져 y1에서 0(smoke). y1 ≤ y0이면 건너뜀
                if (_HeightFade.y > _HeightFade.x)
                {
                    float ht = saturate((p.y - _HeightFade.x) / (_HeightFade.y - _HeightFade.x));
                    d *= 1.0 - ht * ht * (3.0 - 2.0 * ht);
                }
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
                UNITY_SETUP_INSTANCE_ID(i);
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
                // 덩어리 전체(노이즈 여유 포함)를 감싼 구 하나로 구간을 줄인다. (G74) 덩어리는 밀도장 공간(p ⊙ _Squash, 각 1 이상)에 있으므로
                // 그 공간의 반지름이 물체 좌표에서도 상한이다(|p| ≤ |p ⊙ squash|). 덩어리마다 구간을 따로 자르면 그 구의 윤곽에서 걸음 자리가
                // 갑자기 바뀌어 구름 안에 둥근 금이 보였다(첫 시도). 감싼 구의 윤곽은 덩어리 밖(밀도 0)이라 보이지 않는다.
                float extent = 0;
                [unroll]
                for (int k = 0; k < IFS_MIST_LUMPS; k++)
                {
                    float4 L = mistLump(k);
                    extent = max(extent, length(L.xyz) + L.w);
                }
                float bound = extent + _Lumpiness * IFS_MIST_EDGE_NOISE * 0.75 + 0.01;
                float2 span;
                // (G74) 덩어리를 눌렀으면(_Squash ≠ 1) 밀도장 공간의 구 = 물체 좌표의 타원체로 구간을 자른다 — 얇은 층(fog)에 걸음을 모아 층 무늬를 줄인다.
                // 누르지 않았으면 이전 식 그대로(cloud·null = 2.4 이전 화소)
                if (all(_Squash.xyz == float3(1.0, 1.0, 1.0))) span = mistSphere(ro, rd, float3(0, 0, 0), bound);
                else span = mistEllipsoid(ro * _Squash.xyz, rd * _Squash.xyz, bound);
                t0 = max(t0, span.x);
                t1 = min(t1, span.y);
                if (t1 <= t0) discard;
                float dt = (t1 - t0) / IFS_MIST_STEPS;
                // 중점 샘플링: 걸음마다 구간 가운데에서 표본을 뽑는다. 화소별 흔들기(지터)는 쓰지 않는다(화면에 낟알 무늬를 남긴다)
                float jitter = 0.5;

                float sigma = _Density * IFS_MIST_KAPPA;
                float noiseMul = lerp(0.7, 1.3, _Roughness);

                float bright = lerp(0.4, 1.0, saturate(_Brightness * 2.0));   // RenderedColor.BrightnessFactor와 같은 식
                float3 baseCol = _BaseColor.rgb;
                float3 lightDir = normalize(_WorldSpaceLightPos0.xyz);
                // 물체 좌표의 빛 방향(자기 그림자 두께를 물체 좌표 덩어리로 잰다)
                float3 lightObj = normalize(mul((float3x3)unity_WorldToObject, lightDir));
                float3 emission = saturate(_Brightness - 0.5) * 2.4;

                float3 acc = 0;
                float accA = 0;
                [unroll]
                for (int s = 0; s < IFS_MIST_STEPS; s++)
                {
                    float3 p = ro + rd * (t0 + (s + jitter) * dt);
                    float mottle, thick;
                    float3 nObj;
                    float d = mistDensity(p, noiseMul, lightObj, mottle, nObj, thick);
                    // 바닥 아래(세계 높이 < _FloorY)는 밀도 0
                    if (dot(unity_ObjectToWorld[1], float4(p, 1.0)) < _FloorY) d = 0.0;
                    float a = 1.0 - exp(-sigma * d * dt);
                    float3 n = normalize(UnityObjectToWorldNormal(nObj + 1e-4));
                    // 자기 그림자: 덩어리 안에서 빛 쪽으로 남은 두께(물체 좌표) → 투과율. 다중 산란을 어림해 광학 깊이를 0.25배로 줄인다
                    float selfShadow = exp(-sigma * 0.25 * thick);
                    float3 lit = _LightColor0.rgb * saturate((dot(n, lightDir) + 0.4) / 1.4) * selfShadow + ShadeSH9(float4(n, 1.0));
                    float3 col = baseCol * lerp(1.0, 0.7 + 0.6 * mottle, 0.25 + 0.6 * _Roughness);   // 거칠수록 얼룩
                    float3 c3 = col * bright * lit + col * emission + _IfsEmission.rgb;   // (2.3) material.emission(기본 0)
                    acc += (1.0 - accA) * a * c3;
                    accA += (1.0 - accA) * a;
                }
                // opacity는 spec 값 그대로 최종 알파에 곱한다(덩어리 속 최대 알파 ≈ opacity, 그 위로 올리지 않는다)
                float op = saturate(_Opacity);
                return fixed4(acc * op, accA * op);
            }
            ENDCG
        }
    }
    FallBack Off
}
