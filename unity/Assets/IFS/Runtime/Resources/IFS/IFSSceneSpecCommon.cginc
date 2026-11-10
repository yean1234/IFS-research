// IFS SceneSpec 셰이더 공통 부분 (Built-in 렌더 파이프라인, 서피스 셰이더).
// 로더(SceneLoader)가 SceneSpec 값을 아래 프로퍼티에 넣는다. 모든 값 0–1.
//   _BaseColor  색(HSL → RGB)      _Brightness 밝기·발광     _Roughness 거칠기(얼룩·잔요철·광택)
//   _Opacity    불투명도(Fade만)   _Erosion    가장자리 침식(삭아감·갈라짐)
// 형태별 모양은 로더가 정하는 프리셋 값: _Lumpiness(덩어리 굴곡) _NoiseScale _Seed _Fuzz(안개 가장자리) _Density _ShellOpen(껍질 열림)
#ifndef IFS_SCENESPEC_COMMON_INCLUDED
#define IFS_SCENESPEC_COMMON_INCLUDED

fixed4 _BaseColor;
half _Brightness;
half _Roughness;
half _Opacity;
half _Erosion;
half _Lumpiness;
half _NoiseScale;
float _Seed;
half _Fuzz;
half _Density;
half _ShellOpen;

struct Input
{
    float3 objPos;   // 변형 전 위치(무늬가 표면에 붙어 있도록)
    float rim;       // 시선과 표면이 마주 보는 정도(1 = 정면, 0 = 가장자리)
};

// ── 노이즈(결정론적 값 노이즈) ─────────────────────────────────────────────
float ifsHash(float3 p)
{
    p = frac(p * 0.3183099 + 0.1);
    p *= 17.0;
    return frac(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float ifsNoise(float3 x)
{
    float3 i = floor(x);
    float3 f = frac(x);
    f = f * f * (3.0 - 2.0 * f);
    return lerp(lerp(lerp(ifsHash(i + float3(0, 0, 0)), ifsHash(i + float3(1, 0, 0)), f.x),
                     lerp(ifsHash(i + float3(0, 1, 0)), ifsHash(i + float3(1, 1, 0)), f.x), f.y),
                lerp(lerp(ifsHash(i + float3(0, 0, 1)), ifsHash(i + float3(1, 0, 1)), f.x),
                     lerp(ifsHash(i + float3(0, 1, 1)), ifsHash(i + float3(1, 1, 1)), f.x), f.y), f.z);
}

float ifsFbm(float3 p)
{
    float sum = 0.0;
    float amp = 0.5;
    for (int k = 0; k < 4; k++)
    {
        sum += amp * ifsNoise(p);
        p = p * 2.03 + 17.1;
        amp *= 0.5;
    }
    return sum;   // 대략 0–0.94
}

float3 ifsNoiseCoord(float3 p)
{
    return p * _NoiseScale + _Seed * 13.7;
}

// 표면을 바깥(+)·안(−)으로 미는 높이. 굴곡(덩어리) + 잔요철(거칠기).
float ifsHeight(float3 p)
{
    float3 q = ifsNoiseCoord(p);
    float big = (ifsFbm(q) - 0.47) * _Lumpiness;
    float fine = (ifsNoise(q * 9.0) - 0.5) * 0.035 * _Roughness;
    return big + fine;
}

// ── 정점: 노이즈로 밀고, 이웃 두 점으로 법선을 다시 계산 ────────────────────
void ifsVert(inout appdata_full v, out Input o)
{
    UNITY_INITIALIZE_OUTPUT(Input, o);
    float3 p = v.vertex.xyz;
    float3 n = normalize(v.normal);
    float3 up = abs(n.y) < 0.99 ? float3(0, 1, 0) : float3(1, 0, 0);
    float3 t = normalize(cross(n, up));
    float3 b = cross(n, t);
    const float e = 0.01;
    float3 p0 = p + n * ifsHeight(p);
    float3 p1 = p + t * e + n * ifsHeight(p + t * e);
    float3 p2 = p + b * e + n * ifsHeight(p + b * e);
    float3 nn = normalize(cross(p1 - p0, p2 - p0));
    if (dot(nn, n) < 0) nn = -nn;

    o.objPos = p;
    v.vertex.xyz = p0;
    v.normal = nn;

    float3 worldN = normalize(UnityObjectToWorldNormal(nn));
    float3 viewD = normalize(WorldSpaceViewDir(float4(p0, 1.0)));
    o.rim = saturate(dot(worldN, viewD));
}

// ── 표면: 색·얼룩·침식·껍질 열림. interior = 1이면 안쪽 면(어둡게) ─────────
void ifsSurface(Input IN, inout SurfaceOutputStandard o, float interior)
{
    float3 p = IN.objPos;
    float3 q = ifsNoiseCoord(p);

    // 침식: 노이즈가 기준보다 낮은 곳을 뚫고, 뚫린 가장자리는 어둡게 삭은 색으로
    float edge = 0.0;
    if (_Erosion > 0.001)
    {
        float en = ifsFbm(q * 2.3 + 5.1);
        float cut = _Erosion * 0.62;
        clip(en - cut);
        edge = 1.0 - saturate((en - cut) / 0.06);
    }

    // 껍질: 위쪽을 깨진 테두리로 열어 속이 빈 껍데기로
    if (_ShellOpen > 0.001)
    {
        float lip = 0.5 - _ShellOpen + (ifsNoise(q * 4.0) - 0.5) * 0.12;
        clip(lip - p.y);
        edge = max(edge, 1.0 - saturate((lip - p.y) / 0.03));
    }

    float mottle = ifsFbm(q * 3.7 + 2.0);
    float3 col = _BaseColor.rgb;
    col *= lerp(1.0, 0.7 + 0.6 * mottle, 0.25 + 0.6 * _Roughness);       // 거칠수록 얼룩
    col = lerp(col, col * 0.25 + float3(0.06, 0.045, 0.03), edge);       // 삭은 가장자리

    float bright = lerp(0.4, 1.0, saturate(_Brightness * 2.0));          // 0.5 미만은 어둡게
    o.Albedo = col * bright * lerp(1.0, 0.3, interior);
    o.Metallic = 0.0;
    o.Smoothness = saturate((1.0 - _Roughness) * lerp(0.8, 1.0, mottle) * (1.0 - 0.8 * edge));
    o.Emission = col * saturate(_Brightness - 0.5) * 2.4 * (1.0 - interior); // 0.5 초과는 빛남
    o.Alpha = 1.0;
}

#endif
