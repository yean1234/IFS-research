// 자연 공간(G55) 360° 사진의 가져오기 설정(Quest 대비). Resources/IFS/Nature/의 사진에만 적용한다.
//   sRGB, 밉맵 켬(먼 하늘·땅의 깜빡임 방지 — 셰이더가 이음매 도함수를 고침), 가로 반복·세로 고정(등장방형), 삼선형 거르기,
//   최대 4096(4096 × 2048 원본 그대로), 압축: 기본 압축 + Android(Quest) ASTC 6×6(약 3.6 MB + 밉) · Windows DXT1(4 MB + 밉), 읽기 끔.
// 값은 테스트(UnityOnly/PlacementEnvironmentRenderTests)가 실제 가져오기 결과와 대조한다.
// 테스트 대상 Unity API만 쓰는 도구라 compile-check(dotnet)에서는 빈 파일이다(UNITY_EDITOR 아님).
#if UNITY_EDITOR
using UnityEditor;
using UnityEngine;

namespace IFS.SceneSpec.EditorTools
{
    public sealed class NatureTextureImport : AssetPostprocessor
    {
        public const int MaxSize = 4096;
        public const TextureImporterFormat AndroidFormat = TextureImporterFormat.ASTC_6x6;
        public const TextureImporterFormat StandaloneFormat = TextureImporterFormat.DXT1;

        public static bool IsNatureTexture(string assetPath) =>
            assetPath != null && assetPath.Replace('\\', '/').EndsWith("/Resources/IFS/Nature/" + NatureSkyAsset.FileName, System.StringComparison.Ordinal);

        void OnPreprocessTexture()
        {
            if (!IsNatureTexture(assetPath)) return;
            var ti = (TextureImporter)assetImporter;
            ti.textureType = TextureImporterType.Default;
            ti.textureShape = TextureImporterShape.Texture2D;
            ti.sRGBTexture = true;
            ti.alphaSource = TextureImporterAlphaSource.None;
            ti.mipmapEnabled = true;
            ti.isReadable = false;
            ti.npotScale = TextureImporterNPOTScale.None;
            ti.wrapModeU = TextureWrapMode.Repeat;
            ti.wrapModeV = TextureWrapMode.Clamp;
            ti.filterMode = FilterMode.Trilinear;
            ti.anisoLevel = 1;
            ti.maxTextureSize = MaxSize;
            ti.textureCompression = TextureImporterCompression.Compressed;
            ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
            {
                name = "Android", overridden = true, maxTextureSize = MaxSize, format = AndroidFormat,
                textureCompression = TextureImporterCompression.Compressed,
            });
            ti.SetPlatformTextureSettings(new TextureImporterPlatformSettings
            {
                name = "Standalone", overridden = true, maxTextureSize = MaxSize, format = StandaloneFormat,
                textureCompression = TextureImporterCompression.Compressed,
            });
        }
    }
}
#endif
