// EditMode 테스트(Unity 전용): 안개 렌더러(X66). 합성 spec만 쓴다(참여자 데이터 아님).
//   - 안개 셰이더가 있고 컴파일 오류가 없다
//   - 로더가 안개 머티리얼에 재질 슬롯·형상 프리셋을 넣고 그림자를 끈다
//   - opacity 0.15 → 0.6 → 1.0이면 보이는 화소 수(visiblePixels)가 늘어난다(값을 바닥값으로 올리지 않는다, X70)
//   - 배치 캡처의 색 측정 경로가 실제 렌더 경로(mistVolume)를 따른다(CP8 G1)
//   - 안개 구가 바닥 아래로 걸치면 notes·MistFloor에 기록한다(CP8 G4, 화면 처리는 그대로)
using System;
using System.IO;
using System.Linq;
using IFS.SceneSpec.EditorTools;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.Rendering;

namespace IFS.SceneSpec.Tests
{
    public class MistRendererTests
    {
        string _tmp;

        [SetUp]
        public void SetUp()
        {
            _tmp = Path.Combine(Path.GetTempPath(), "ifs-mist-" + Guid.NewGuid().ToString("N"));
            Directory.CreateDirectory(_tmp);
        }

        [TearDown]
        public void TearDown()
        {
            if (Directory.Exists(_tmp)) Directory.Delete(_tmp, true);
        }

        [Test]
        public void Mist_shader_exists_and_compiles()
        {
            var sh = Resources.Load<Shader>(FormRenderResources.MistShaderResource);
            Assert.That(sh, Is.Not.Null);
            Assert.That(ShaderUtil.ShaderHasError(sh), Is.False,
                string.Join("\n", ShaderUtil.GetShaderMessages(sh).Select(m => m.severity + ": " + m.message)));
            Assert.That(sh.isSupported, Is.True);
            Assert.That(ShaderUtil.GetShaderMessages(sh).Count(m => m.severity == UnityEditor.Rendering.ShaderCompilerMessageSeverity.Error), Is.EqualTo(0));
            Assert.That(FormRenderResources.LoadMistShader(), Is.True);
        }

        [Test]
        public void Loader_puts_material_slots_and_presets_into_the_mist_material()
        {
            var spec = OwnershipTestSpecs.Empty("MISTMAT").Slot("form.type", "mist", "안개").Hsl(0.6, 0.45, 0.6, "파란")
                .Slot("material.opacity", 0.6, "흐릿").Slot("material.brightness", 0.8, "밝은").Slot("material.roughness", 0.2, "매끈")
                .Slot("material.erosion", 0.3, "삭은").Slot("motion.type", "drifting", "떠다니");
            FormRendererTests.WithLoaded(_tmp, spec, "mist-mat", l =>
            {
                Assert.That(l.RenderPath, Is.EqualTo(FormRenderPlan.RendererMist));
                var rs = l.Root.GetComponentsInChildren<Renderer>();
                Assert.That(rs.Length, Is.EqualTo(1), "드로콜 1");
                var r = rs[0];
                Assert.That(r.shadowCastingMode, Is.EqualTo(ShadowCastingMode.Off), "그림자 없음(U5)");
                Assert.That(r.GetComponent<MeshFilter>().sharedMesh.name, Is.EqualTo("IFS Mist Proxy"));
                var m = r.sharedMaterial;
                Assert.That(m.shader.name, Is.EqualTo("IFS/SceneSpec Mist"));
                Assert.That(m.GetFloat("_Opacity"), Is.EqualTo(0.6f).Within(1e-6));
                Assert.That(m.GetFloat("_Brightness"), Is.EqualTo(0.8f).Within(1e-6));
                Assert.That(m.GetFloat("_Roughness"), Is.EqualTo(0.2f).Within(1e-6));
                Assert.That(m.GetFloat("_Erosion"), Is.EqualTo(0.3f).Within(1e-6));
                var preset = FormRenderPlan.FormPresets["mist"];
                Assert.That(m.GetFloat("_Lumpiness"), Is.EqualTo(preset.Lumpiness));
                Assert.That(m.GetFloat("_NoiseScale"), Is.EqualTo(preset.NoiseScale));
                Assert.That(m.GetFloat("_Density"), Is.EqualTo(preset.Density));
                Assert.That(m.GetFloat("_FloorY"), Is.EqualTo(0f), "배치 설정의 바닥 높이(기본 0)");
                // D7: 둥근 덩어리 밀도장 — seed로 정한 덩어리 중심·반지름이 _Lump0…에 그대로 들어간다
                Assert.That(m.GetFloat("_Seed"), Is.EqualTo((float)MistLumps.DefaultSeed));
                var lumps = MistLumps.Build(MistLumps.DefaultSeed);
                for (int k = 0; k < MistLumps.Count; k++)
                {
                    var v = m.GetVector(FormRenderResources.MistLumpProperty(k));
                    Assert.That(v.x, Is.EqualTo((float)lumps[k * 4]).Within(1e-6), "lump " + k);
                    Assert.That(v.y, Is.EqualTo((float)lumps[k * 4 + 1]).Within(1e-6), "lump " + k);
                    Assert.That(v.z, Is.EqualTo((float)lumps[k * 4 + 2]).Within(1e-6), "lump " + k);
                    Assert.That(v.w, Is.EqualTo((float)lumps[k * 4 + 3]).Within(1e-6), "lump " + k);
                }
                Assert.That(l.Notes.Any(n => n.Contains("둥근 덩어리 " + MistLumps.Count + "개") && n.Contains(MistLumps.RuleVersion)), Is.True);
                RenderedColor.BaseSrgb(0.6, 0.45, 0.6, out double cr, out double cg, out double cb);
                var c = m.GetColor("_BaseColor");
                Assert.That(c.r, Is.EqualTo((float)cr).Within(1e-5));
                Assert.That(c.g, Is.EqualTo((float)cg).Within(1e-5));
                Assert.That(c.b, Is.EqualTo((float)cb).Within(1e-5));
                Assert.That(l.Notes.Any(n => n.Contains("형상 프리셋 기본값") && n.Contains(FormRenderPlan.MistSteps + "걸음")), Is.True);
                return 0;
            });
        }

        // 안개 셰이더는 바닥 아래 밀도를 0으로 자른다 → 구가 바닥에 걸치면 notes·MistFloor에 기록(G4). 화면 처리는 그대로.
        [TestCase(0.04, true)]
        [TestCase(0.75, false)]
        public void Floor_clipping_is_recorded_when_the_mist_sphere_reaches_below_the_floor(double verticalOffset, bool clipped)
        {
            var spec = OwnershipTestSpecs.Empty("MISTFLOOR").Slot("form.type", "mist", "안개")
                .Slot("layout.verticalOffset", verticalOffset, "높이");
            FormRendererTests.WithLoaded(_tmp, spec, "mist-floor-" + (clipped ? "low" : "high"), l =>
            {
                Assert.That(l.RenderPath, Is.EqualTo(FormRenderPlan.RendererMist));
                Assert.That(l.MistFloor, Is.Not.Null);
                Assert.That(l.MistFloor.FloorClipped, Is.EqualTo(clipped));
                Assert.That(l.MistFloor.FloorY, Is.EqualTo(0.0));
                if (clipped) Assert.That(l.MistFloor.ClippedHeightFraction, Is.GreaterThan(0.0).And.LessThanOrEqualTo(1.0));
                else Assert.That(l.MistFloor.ClippedHeightFraction, Is.EqualTo(0.0));
                Assert.That(l.Notes.Any(n => n.Contains("바닥 아래 밀도를 0으로 자름")), Is.EqualTo(clipped));
                return 0;
            });
        }

        [Test]
        public void Non_mist_forms_have_no_floor_clip_record()
        {
            var spec = OwnershipTestSpecs.Empty("BLOBFLOOR").Slot("form.type", "blob", "덩어리").Slot("layout.verticalOffset", 0.04, "높이");
            FormRendererTests.WithLoaded(_tmp, spec, "blob-floor", l =>
            {
                Assert.That(l.MistFloor, Is.Null);
                return 0;
            });
        }

        [Test]
        public void Visible_pixels_increase_with_opacity()
        {
            string specDir = Path.Combine(_tmp, "specs");
            Directory.CreateDirectory(specDir);
            foreach (var (name, op) in new[] { ("M015", 0.15), ("M060", 0.6), ("M100", 1.0) })
                OwnershipTestSpecs.Empty(name).Slot("form.type", "mist", "안개").Hsl(0.6, 0.45, 0.6, "파란")
                    .Slot("material.opacity", op, "투명").Write(specDir, name + ".json");
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var report = BatchCapture.Execute(new CaptureOptions
            {
                SpecDir = specDir, OutDir = Path.Combine(_tmp, "out"), Width = 320, Height = 342, Frames = 2, WarmupFrames = 1, PngWidth = 160,
            });
            Assert.That(report.Value<bool>("ok"), Is.True);
            var specs = report["specs"].Children<JObject>().ToDictionary(s => s.Value<string>("spec"));
            foreach (var s in specs.Values)
            {
                Assert.That(s["console"].Value<int>("errors"), Is.EqualTo(0), s["console"].ToString());
                Assert.That(s.Value<string>("renderPath"), Is.EqualTo(FormRenderPlan.RendererMist));
                // 색 측정 경로는 실제 렌더 경로(부피 셰이더)를 따른다(G1)
                Assert.That(s["color"].Value<string>("measuredWith"), Is.EqualTo(BatchCapture.MeasuredMistVolume));
                Assert.That(s["color"].Value<bool>("transparent"), Is.True);
                Assert.That(s["color"].Value<string>("primary"), Is.EqualTo("scene"));
                Assert.That(s["mistFloor"].Value<bool>("floorClipped"), Is.False, "기본 높이(verticalOffset 0.75)는 바닥에 닿지 않음");
            }
            int v015 = specs["M015.json"].Value<int>("visiblePixels");
            int v060 = specs["M060.json"].Value<int>("visiblePixels");
            int v100 = specs["M100.json"].Value<int>("visiblePixels");
            Assert.That(v060, Is.GreaterThan(v015));
            Assert.That(v100, Is.GreaterThan(v060));
            Assert.That(specs["M100.json"].Value<double>("maxAlpha"), Is.GreaterThan(specs["M015.json"].Value<double>("maxAlpha")));
            // D7: 덩어리 속은 누적 알파가 opacity 가까이까지 차고, opacity를 넘지 않는다(X70 — 값을 올리지 않음)
            foreach (var (name, op) in new[] { ("M015.json", 0.15), ("M060.json", 0.6), ("M100.json", 1.0) })
            {
                double maxA = specs[name].Value<double>("maxAlpha");
                Assert.That(maxA, Is.LessThanOrEqualTo(op + 0.01), name);
                Assert.That(maxA, Is.GreaterThanOrEqualTo(op * 0.9), name);
                Assert.That(specs[name]["contrast"].Value<double?>("deltaL"), Is.Not.Null, name + " 밝기 대비 지표");
            }
        }
    }
}
