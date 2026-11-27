// EditMode 테스트(dotnet·Unity 공통): G62 생성 형태 메시의 러너 쪽
//   · GlbMeshReader: 합성 GLB(사면체)를 읽어 정점·삼각형·경계, glTF → Unity 좌표(x 뒤집기·감김 바꾸기), 바깥 법선, 잘못된 GLB 거부.
//   · FormAssetFit: 같은 layout.size·자세·축 비율에서 생성 메시의 가장 긴 변 = 절차 모형의 가장 긴 변(±1%), 중심 맞춤.
//   · PlacementSelection: ifs-selection/0.3 form.asset·generated_chosen·defaultFormSource·acceptedDefault 읽기, 0.1·0.2 규칙 유지
//     (0.2에 generated_chosen·form.asset이 있으면 거부), 출처와 form.asset이 어긋나면 거부, manifest 키는 값이 있을 때만.
//   · PlacementManifest: formAsset 키는 생성 메시 결과가 있을 때만(이전 기록 바이트 그대로).
// 합성 값만 쓴다(참여자 자료 아님).
using System;
using System.Linq;
using IFS.SceneSpec.FormAsset;
using IFS.SceneSpec.Placement;
using Newtonsoft.Json.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class FormAssetTests
    {
        // glTF 좌표의 사면체: 바닥 y = 0, 가장 긴 변(x) 1.0, 피벗 bottom-center. 바깥을 보는 반시계 감김
        static readonly float[] TetraPos = { -0.5f, 0f, -0.25f, 0.5f, 0f, -0.25f, 0f, 0f, 0.25f, 0f, 0.6f, 0f };
        static readonly int[] TetraTri = { 0, 1, 2, 0, 3, 1, 1, 3, 2, 2, 3, 0 };
        const string Sha = "7d42fd56f98a3d75da09f894b41f955a5cd8b534cb83d23e2b2b23244618cf13";
        const string GlbSha = "aa42fd56f98a3d75da09f894b41f955a5cd8b534cb83d23e2b2b23244618cf13";

        [Test]
        public void Reads_synthetic_glb_with_unity_handedness_and_bounds()
        {
            var glb = GlbMeshReader.Write(TetraPos, TetraTri);
            var m = GlbMeshReader.Read(glb, out var err);
            Assert.That(err, Is.Null);
            Assert.That(m.VertexCount, Is.EqualTo(4));
            Assert.That(m.TriangleCount, Is.EqualTo(4));
            Assert.That(m.Positions[0], Is.EqualTo(0.5f), "x를 뒤집음(glTF 오른손 → Unity 왼손)");
            Assert.That(m.Triangles.Take(3), Is.EqualTo(new[] { 0, 2, 1 }), "감김 순서를 바꿈");
            Assert.That(m.LongestEdge, Is.EqualTo(1.0).Within(1e-6));
            Assert.That(m.Min[1], Is.EqualTo(0.0).Within(1e-6), "바닥 피벗 그대로(회전·이동 없음)");
            Assert.That(m.Center[1], Is.EqualTo(0.3).Within(1e-6));
            // 정점 법선이 사면체 중심에서 바깥쪽
            double cx = 0, cy = 0, cz = 0;
            for (int i = 0; i < 4; i++) { cx += m.Positions[i * 3] / 4.0; cy += m.Positions[i * 3 + 1] / 4.0; cz += m.Positions[i * 3 + 2] / 4.0; }
            for (int i = 0; i < 4; i++)
            {
                double d = (m.Positions[i * 3] - cx) * m.Normals[i * 3] + (m.Positions[i * 3 + 1] - cy) * m.Normals[i * 3 + 1] +
                           (m.Positions[i * 3 + 2] - cz) * m.Normals[i * 3 + 2];
                Assert.That(d, Is.GreaterThan(0), "정점 " + i + " 법선이 바깥을 봄");
            }
            // 같은 바이트 → 같은 결과
            var again = GlbMeshReader.Read(glb, out _);
            Assert.That(again.Positions, Is.EqualTo(m.Positions));
            Assert.That(again.Normals, Is.EqualTo(m.Normals));
        }

        [Test]
        public void Rejects_broken_glb_with_reason()
        {
            Assert.That(GlbMeshReader.Read(new byte[] { 1, 2, 3 }, out var e1), Is.Null);
            Assert.That(e1, Does.Contain("짧"));
            var glb = GlbMeshReader.Write(TetraPos, TetraTri);
            var bad = (byte[])glb.Clone();
            bad[0] = 0;
            Assert.That(GlbMeshReader.Read(bad, out var e2), Is.Null);
            Assert.That(e2, Does.Contain("매직"));
            var cut = glb.Take(glb.Length - 8).ToArray();
            Assert.That(GlbMeshReader.Read(cut, out var e3), Is.Null);
            Assert.That(e3, Is.Not.Null);
            var outOfRange = GlbMeshReader.Write(TetraPos, new[] { 0, 1, 9 });
            Assert.That(GlbMeshReader.Read(outOfRange, out var e4), Is.Null);
            Assert.That(e4, Does.Contain("범위"));
        }

        [Test]
        public void Preview_payload_checks_sha_and_glb_before_drawing()
        {
            var glb = GlbMeshReader.Write(TetraPos, TetraTri);
            string sha = Ownership.OwnershipManifest.Sha256Hex(glb);
            var ok = FormAssetPayload.Decode(new JObject { ["assetId"] = "0123456789abcdef", ["glbSha256"] = sha, ["glbBase64"] = Convert.ToBase64String(glb) },
                                             null, out var asset, out var err);
            Assert.That(err, Is.Null);
            Assert.That(ok.TriangleCount, Is.EqualTo(4));
            Assert.That(asset.AssetId, Is.EqualTo("0123456789abcdef"));
            // 파일 경로(데스크톱 요청 폴더)
            var viaPath = FormAssetPayload.Decode(new JObject { ["assetId"] = "a", ["glbSha256"] = sha, ["glb"] = "x.glb" }, _ => glb, out _, out var e0);
            Assert.That(viaPath, Is.Not.Null, e0);
            // sha256이 다르면 그리지 않음
            Assert.That(FormAssetPayload.Decode(new JObject { ["assetId"] = "a", ["glbSha256"] = new string('f', 64), ["glbBase64"] = Convert.ToBase64String(glb) },
                                                null, out _, out var e1), Is.Null);
            Assert.That(e1, Does.StartWith(FormAssetResult.GlbSha));
            // 읽을 수 없는 GLB(sha는 맞음)
            var junk = new byte[] { 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21 };
            Assert.That(FormAssetPayload.Decode(new JObject { ["assetId"] = "a", ["glbSha256"] = Ownership.OwnershipManifest.Sha256Hex(junk),
                                                              ["glbBase64"] = Convert.ToBase64String(junk) }, null, out _, out var e2), Is.Null);
            Assert.That(e2, Does.StartWith(FormAssetResult.GlbParse));
            // 파일이 없음
            Assert.That(FormAssetPayload.Decode(new JObject { ["assetId"] = "a", ["glbSha256"] = sha, ["glb"] = "x.glb" },
                                                _ => throw new System.IO.FileNotFoundException("없음"), out _, out var e3), Is.Null);
            Assert.That(e3, Does.StartWith(FormAssetResult.GlbMissing));
        }

        [Test]
        public void Preview_bridge_and_queue_wire_form_asset()
        {
            // WebGL 다리·페이지 API·데스크톱 요청 폴더가 같은 경로(FormAssetPayload → SceneLoader.ApplyFormAsset)를 쓴다(원문 대조)
            string root = System.IO.Path.GetFullPath(System.IO.Path.Combine(UnityEngine.Application.streamingAssetsPath, "..", "IFS", "Runtime", "Preview"));
            string bridge = System.IO.File.ReadAllText(System.IO.Path.Combine(root, "PreviewBridge.cs"));
            string queue = System.IO.File.ReadAllText(System.IO.Path.Combine(root, "PreviewQueue.cs"));
            string stage = System.IO.File.ReadAllText(System.IO.Path.Combine(root, "PreviewStage.cs"));
            string page = System.IO.File.ReadAllText(System.IO.Path.Combine(root, "..", "..", "..", "WebGLTemplates", "IFSPreview", "index.html"));
            Assert.That(bridge, Does.Contain("public void SetFormAssetJson(string json)"));
            Assert.That(bridge, Does.Contain("FormAssetPayload.Decode"));
            Assert.That(queue, Does.Contain("FormAssetPayload.Decode"));
            Assert.That(queue, Does.Contain("formAssetError"));
            Assert.That(stage, Does.Contain("Loader.ApplyFormAsset(AssetRef, AssetMesh)"));
            Assert.That(page, Does.Contain("'SetFormAssetJson'"));
            // 2026-11-27 실제 자산 캡처에서 고친 두 가지(Unity에서만 보이는 동작이라 원문 대조): 절차 모형 크기는 mesh.bounds가 아니라
            // 정점으로 잰다(IcoMesh bounds 1.6 ≠ 지름 1.0), 생성 메시에는 shell 프리셋의 껍질 열림(_ShellOpen)을 0으로
            string loader = System.IO.File.ReadAllText(System.IO.Path.Combine(root, "..", "Loading", "SceneLoader.cs"));
            int at = loader.IndexOf("bool ProceduralLocalBounds(", StringComparison.Ordinal);
            Assert.That(loader.Substring(at, 900), Does.Contain("sharedMesh.vertices").And.Not.Contain("sharedMesh.bounds"));
            Assert.That(loader, Does.Contain("FormRenderResources.ShellOpenProperty, 0f"));
        }

        [TestCase(0.0, 1.0, 1.0, 1.0)]
        [TestCase(0.5, 1.2, 0.8, 1.0)]
        [TestCase(1.0, 1.0, 1.0, 0.4)]
        public void Longest_edge_matches_procedural_mesh_within_one_percent(double sizeScale, double dx, double dy, double axisZ)
        {
            // 절차 모형: 구(지름 1.5, 중심 0) × 기본 크기 0.35 × layout.size 배율 × 자세 × 축 비율
            var fit = new FormAssetFit(new[] { 0.0, 0.0, 0.0 }, new[] { 1.5, 1.5, 1.5 }, new[] { 0.0, 0.3, 0.0 }, new[] { 1.0, 0.6, 0.5 });
            double s = 0.35 * (0.5 + sizeScale);
            var local = new[] { s * dx, s * dy, s * axisZ };
            fit.Place(local, out double u, out double[] at, out double lp, out double lr);
            double want = new[] { 1.5 * local[0], 1.5 * local[1], 1.5 * local[2] }.Max();
            Assert.That(lp, Is.EqualTo(want).Within(1e-12));
            Assert.That(FormAssetFit.RelativeError(lr, lp), Is.LessThanOrEqualTo(FormAssetFit.Tolerance));
            Assert.That(u * 1.0, Is.EqualTo(lr).Within(1e-12), "GLB 가장 긴 변 1.0 → 균일 배율 = 렌더 가장 긴 변");
            Assert.That(at[1], Is.EqualTo(-0.3 * u).Within(1e-12), "bottom-center 피벗을 절차 모형 중심에 맞춤");
            Assert.That(at[0], Is.EqualTo(0).Within(1e-12));
        }

        [Test]
        public void Fit_does_not_trust_sidecar_normalization()
        {
            // 정규화가 어긋난 GLB(가장 긴 변 2.0)도 읽은 경계로 다시 재므로 크기는 같다
            var fit = new FormAssetFit(new[] { 0.0, 0.0, 0.0 }, new[] { 1.0, 1.0, 1.0 }, new[] { 0.0, 1.0, 0.0 }, new[] { 2.0, 2.0, 0.5 });
            fit.Place(new[] { 0.35, 0.35, 0.35 }, out double u, out _, out double lp, out double lr);
            Assert.That(lr, Is.EqualTo(lp).Within(1e-12));
            Assert.That(u, Is.EqualTo(0.175).Within(1e-12));
        }

        // ── 선택 파일 0.3 ────────────────────────────────────────────────────
        static JObject Selection03(bool withAsset = true, string formSource = "generated_chosen", string format = "ifs-selection/0.3")
        {
            var o = new JObject
            {
                ["formatVersion"] = format,
                ["specSha256"] = Sha,
                ["finalOverrides"] = new JObject(),
                ["selection"] = new JObject { ["selectedCandidateId"] = "g-0123456789ab", ["none"] = false, ["skipped"] = false, ["acceptedDefault"] = true },
                ["colorChanged"] = false,
                ["sources"] = new JObject { ["form.type"] = formSource, ["layout.size"] = "default" },
                ["defaultFormSource"] = "generated",
                ["form"] = new JObject
                {
                    ["asset"] = withAsset
                        ? new JObject
                        {
                            ["candidateId"] = "g-0123456789ab", ["assetId"] = "0123456789abcdef", ["glb"] = "form-asset-aa42fd56f98a3d75.glb",
                            ["glbSha256"] = GlbSha, ["pipeline"] = "sdxl-triposg", ["seed"] = 0,
                            ["models"] = new JArray(new JObject { ["name"] = "shape", ["repo"] = "none/synthetic", ["revision"] = null, ["weightsSha256"] = null }),
                            ["promptText"] = "a single lump, matte gray clay, plain background",
                            ["covariates"] = new JObject { ["axisRatios"] = new JArray(1.0, 0.6, 0.5), ["thinRisk"] = false, ["familiarObjectStated"] = false },
                        }
                        : (JToken)JValue.CreateNull(),
                },
            };
            return o;
        }

        static PlacementSelection Parse(JObject o, out System.Collections.Generic.List<string> errors) =>
            PlacementSelection.Parse(o.ToString(), "selection.json", "ab", out errors);

        [Test]
        public void Reads_03_form_asset_and_default_choice()
        {
            var s = Parse(Selection03(), out var errors);
            Assert.That(errors, Is.Empty);
            Assert.That(s.Warnings, Is.Empty, "0.3은 아는 버전");
            Assert.That(s.FormAsset.AssetId, Is.EqualTo("0123456789abcdef"));
            Assert.That(s.FormAsset.GlbSha256, Is.EqualTo(GlbSha));
            Assert.That(s.FormAsset.ResolveGlbPath(System.IO.Path.Combine(System.IO.Path.GetTempPath(), "x", "selection.json")),
                        Does.EndWith("form-asset-aa42fd56f98a3d75.glb"));
            Assert.That(s.DefaultFormSource, Is.EqualTo("generated"));
            Assert.That(s.AcceptedDefault, Is.True);
            var man = s.ManifestJson();
            Assert.That((string)man["formAssetId"], Is.EqualTo("0123456789abcdef"));
            Assert.That((string)man["defaultFormSource"], Is.EqualTo("generated"));
            Assert.That((bool)man["acceptedDefault"], Is.True);
        }

        [Test]
        public void Version_rules_for_generated_source_and_form_asset()
        {
            // 0.2 파일에는 generated_chosen·form.asset이 없어야 한다
            Assert.That(Parse(Selection03(format: "ifs-selection/0.2"), out var e1), Is.Null);
            Assert.That(e1.Any(e => e.Contains("generated_chosen")), Is.True);
            Assert.That(e1.Any(e => e.Contains("form.asset")), Is.True);
            // 출처와 form.asset이 어긋남
            Assert.That(Parse(Selection03(withAsset: false), out var e2), Is.Null);
            Assert.That(e2.Single(), Does.Contain("form.asset이 없음"));
            Assert.That(Parse(Selection03(formSource: "chosen"), out var e3), Is.Null);
            Assert.That(e3.Single(), Does.Contain("form.asset이 있는데"));
            // 0.3에서 생성 메시를 고르지 않은 파일(form.asset null) — 절차 메시
            var plain = Parse(Selection03(withAsset: false, formSource: "chosen"), out var e4);
            Assert.That(e4, Is.Empty);
            Assert.That(plain.FormAsset, Is.Null);
            Assert.That(plain.ManifestJson().ContainsKey("formAssetId"), Is.False);
            // glb 경로는 상대 파일 이름만
            var abs = Selection03();
            abs["form"]["asset"]["glb"] = "../outside.glb";
            Assert.That(Parse(abs, out var e5), Is.Null);
            Assert.That(e5.Single(), Does.Contain("상대"));
            // 0.3도 skipped·colorChanged는 필수(0.2와 같음)
            var noSkip = Selection03();
            ((JObject)noSkip["selection"]).Remove("skipped");
            Assert.That(Parse(noSkip, out var e6), Is.Null);
            Assert.That(e6.Single(), Does.Contain("skipped"));
        }

        [Test]
        public void Older_selection_manifest_has_no_g62_keys()
        {
            var o = new JObject
            {
                ["formatVersion"] = "ifs-selection/0.2", ["specSha256"] = Sha, ["finalOverrides"] = new JObject(),
                ["selection"] = new JObject { ["selectedCandidateId"] = "c-1", ["none"] = false, ["skipped"] = false },
                ["colorChanged"] = false, ["sources"] = new JObject { ["form.type"] = "chosen" },
            };
            var s = Parse(o, out var errors);
            Assert.That(errors, Is.Empty);
            var man = s.ManifestJson();
            Assert.That(man.Properties().Select(p => p.Name),
                        Is.EqualTo(new[] { "file", "sha256", "formatVersion", "none", "selectedCandidateId", "finalOverrides", "sources", "skipped", "colorChanged" }));
        }

        [Test]
        public void Manifest_form_asset_key_only_when_result_exists()
        {
            var cfg = new PlacementConfig();
            var without = PlacementManifest.Build(cfg, new PlacementSessionInfo { SessionId = "SYN" });
            Assert.That(without.ContainsKey("formAsset"), Is.False);

            var sel = Parse(Selection03(), out _);
            var res = FormAssetResult.Fallback(sel.FormAsset, FormAssetResult.GlbSha);
            res.GlbSha256Actual = Sha;
            var with = PlacementManifest.Build(cfg, new PlacementSessionInfo { SessionId = "SYN", FormAsset = res });
            var fa = (JObject)with["formAsset"];
            Assert.That((string)fa["status"], Is.EqualTo(FormAssetResult.StatusFallback));
            Assert.That((string)fa["fallbackReason"], Is.EqualTo("glb_sha256_mismatch"));
            Assert.That((string)fa["glbSha256"], Is.EqualTo(GlbSha));
            Assert.That((string)fa["glbSha256Actual"], Is.EqualTo(Sha));
            Assert.That((double)fa["covariates"]["axisRatios"][1], Is.EqualTo(0.6));
            Assert.That(with.Properties().Last().Name, Is.EqualTo("formAsset"), "맨 끝에 더함");

            var ok = new FormAssetResult
            {
                Ref = sel.FormAsset, Status = FormAssetResult.StatusApplied, RenderedLongestEdgeM = 0.5, ProceduralLongestEdgeM = 0.5,
                RenderedSizeM = new[] { 0.5, 0.3, 0.25 }, LayoutSize = 0.5, Vertices = 4, Triangles = 4,
            };
            var j = ok.ManifestJson();
            Assert.That((double)j["longestEdgeRelError"], Is.EqualTo(0.0));
            Assert.That(ok.EventDetail(), Does.StartWith("asset=0123456789abcdef;status=applied"));
        }
    }
}
