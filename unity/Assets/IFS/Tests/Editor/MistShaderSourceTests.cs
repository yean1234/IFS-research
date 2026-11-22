// 안개 셰이더 소스(X66)와 C# 상수가 맞는지(dotnet·Unity 공통). 셰이더 파일을 텍스트로 읽는다.
using System.IO;
using System.Text.RegularExpressions;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class MistShaderSourceTests
    {
        static string Source() => File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "..", "IFS", "Runtime", "Resources", "IFS", "SceneSpecMist.shader"));

        static string Define(string src, string name)
        {
            var m = Regex.Match(src, @"#define\s+" + name + @"\s+([0-9.]+)");
            Assert.That(m.Success, Is.True, name + " 정의가 없음");
            return m.Groups[1].Value;
        }

        [Test]
        public void Step_count_and_radius_match_the_csharp_constants()
        {
            string src = Source();
            Assert.That(int.Parse(Define(src, "IFS_MIST_STEPS")), Is.EqualTo(FormRenderPlan.MistSteps));
            Assert.That(float.Parse(Define(src, "IFS_MIST_RADIUS"), System.Globalization.CultureInfo.InvariantCulture),
                Is.EqualTo(FormRenderResources.MistRadius));
        }

        [Test]
        public void Shader_picks_faces_by_camera_position_without_shadows_or_depth_writes()
        {
            string src = Source();
            // 구 밖이면 앞면, 구 안이면 안쪽 면만 남긴다(한 패스, Cull Off) — 바닥에 놓인 안개가 깊이 테스트로 사라지지 않게
            Assert.That(src, Does.Contain("Cull Off"));
            Assert.That(src, Does.Contain("if (frontFace == inside) discard;"));
            Assert.That(src, Does.Contain("_FloorY"));
            Assert.That(src, Does.Contain("ZWrite Off"));
            Assert.That(src, Does.Not.Contain("\"LightMode\" = \"ShadowCaster\""));
            Assert.That(src, Does.Contain("FallBack Off"));
            Assert.That(Regex.Matches(src, @"\bPass\b").Count, Is.EqualTo(1), "패스 하나(드로콜 1)");
            Assert.That(src, Does.Not.Contain("tex2D"), "텍스처 없이 해시 노이즈만");
            // 재질 슬롯 프로퍼티(로더가 넣는 이름)
            foreach (var p in new[] { "_BaseColor", "_Brightness", "_Roughness", "_Opacity", "_Erosion", "_Lumpiness", "_NoiseScale", "_Density" })
                Assert.That(src, Does.Contain(p + " ("), p);
        }

        [Test]
        public void Vertex_fragment_shaders_carry_stereo_instancing_macros()
        {
            // 헤드셋(OpenXR 단일 패스 인스턴싱, 2026-11-23): 눈 번호·인스턴스 ID가 조각 단계까지 가야 눈마다 카메라 위치(_WorldSpaceCameraPos)와
            // 물체 행렬(unity_WorldToObject)이 맞는다. 표면 셰이더(Opaque·Fade·Floor)는 Unity가 매크로를 넣어 준다.
            string mist = Source();
            foreach (var m in new[] { "#pragma multi_compile_instancing", "UNITY_VERTEX_INPUT_INSTANCE_ID", "UNITY_VERTEX_OUTPUT_STEREO", "UNITY_SETUP_INSTANCE_ID(v);",
                                      "UNITY_TRANSFER_INSTANCE_ID(v, o);", "UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);", "UNITY_SETUP_INSTANCE_ID(i);",
                                      "UNITY_SETUP_STEREO_EYE_INDEX_POST_VERTEX(i);" })
                Assert.That(mist, Does.Contain(m), "SceneSpecMist: " + m);
            Assert.That(Regex.Matches(mist, @"UNITY_VERTEX_INPUT_INSTANCE_ID").Count, Is.EqualTo(2), "appdata와 v2f 둘 다");
            string sky = File.ReadAllText(Path.Combine(Application.streamingAssetsPath, "..", "IFS", "Runtime", "Resources", "IFS", "EnvironmentSky.shader"));
            foreach (var m in new[] { "UNITY_VERTEX_INPUT_INSTANCE_ID", "UNITY_VERTEX_OUTPUT_STEREO", "UNITY_SETUP_INSTANCE_ID(v);", "UNITY_INITIALIZE_VERTEX_OUTPUT_STEREO(o);" })
                Assert.That(sky, Does.Contain(m), "EnvironmentSky: " + m);
        }
    }
}
