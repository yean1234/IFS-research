// EditMode 테스트(Unity 전용): 헤드셋 UI 개선(G63)의 판·광선 표현. 플래그를 끄면 판이 G63 전과 같고(크기·글·색·재질),
// 켜면 실제 판의 아래 가장자리 각·어두운 판 재질·평정 줄 폭·확정 테두리·광선 상태가 기준을 충족한다.
// 문구는 문구 파일(scaleA)을 읽기만 한다(글자는 바꾸지 않음).
using System.IO;
using System.Linq;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementUiG63PanelTests
    {
        static readonly Vector3 Center = new Vector3(0f, 0.6f, 2.0f);
        static readonly Vector3 Eye = new Vector3(0f, 1.6f, 0f);

        static PlacementTaskText ScaleA() =>
            PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementXrTests.ScaleARelativePath));

        static PlacementTextPanel NewPanel(string name) => new GameObject(name).AddComponent<PlacementTextPanel>();

        static Transform Root(PlacementTextPanel p) => p.transform.Find("participant panel");

        static Material Mat(PlacementTextPanel p, string child) => Root(p).Find(child).GetComponent<MeshRenderer>().sharedMaterial;

        static float WidthDeg(PlacementTextPanel p) =>
            (float)PlacementPanelMetrics.PanelWidthDeg(p.PanelSizeM.x, Vector3.Distance(Eye, p.PanelCenter));

        [Test]
        public void Flags_off_panel_is_identical_to_a_panel_that_never_saw_the_options()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var t = ScaleA();
            var a = NewPanel("untouched");
            var b = NewPanel("options off");
            b.ApplyUiOptions(false, false, false);
            string instruction = t.InstructionFor(PlacementTaskText.WhenPre);
            foreach (var p in new[] { a, b }) p.ShowText(instruction, Center, Eye);
            Assert.That(b.PanelSizeM, Is.EqualTo(a.PanelSizeM));
            Assert.That(Root(b).Find("panel body").GetComponent<TextMesh>().text, Is.EqualTo(Root(a).Find("panel body").GetComponent<TextMesh>().text));
            Assert.That(b.PanelCenter, Is.EqualTo(a.PanelCenter));
            Assert.That(b.WrapCharsShown, Is.EqualTo(PlacementPanelMetrics.DefaultWrapChars));
            Assert.That(Mat(b, "panel background").color, Is.EqualTo(Mat(a, "panel background").color));
            Assert.That(Mat(b, "panel background").GetColor("_EmissionColor"), Is.EqualTo(Mat(a, "panel background").GetColor("_EmissionColor")));
            var a1 = t.Items.First(i => i.Key == "A1");
            foreach (var p in new[] { a, b }) p.ShowItem(a1, 5, Center, Eye);
            Assert.That(b.PanelSizeM, Is.EqualTo(a.PanelSizeM));
            Assert.That(b.ColumnWidthM, Is.EqualTo((float)PlacementPanelMetrics.DefaultColumnWidthM));
            Assert.That(b.SelectionFrameShownM, Is.EqualTo((float)PlacementPanelMetrics.DefaultSelectionFrameM));
            Assert.That(Root(b).Find("selected cell fill").localScale, Is.EqualTo(Root(a).Find("selected cell fill").localScale));
            // 켰다 끄면 Inspector 값으로 돌아간다
            b.ApplyUiOptions(true, true, true);
            b.ApplyUiOptions(false, false, false);
            b.ShowText(instruction, Center, Eye);
            a.ShowText(instruction, Center, Eye);
            Assert.That(b.PanelSizeM, Is.EqualTo(a.PanelSizeM));
            Assert.That(Mat(b, "panel background").color, Is.EqualTo(Mat(a, "panel background").color));
        }

        [Test]
        public void Comfort_wrap_pages_keep_the_real_panel_bottom_within_35_degrees_and_match_the_metric()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var t = ScaleA();
            var off = NewPanel("off");
            off.ShowText(t.InstructionFor(PlacementTaskText.WhenPre), Center, Eye);
            Assert.That(off.BottomBelowHorizonDeg, Is.GreaterThan(35f), "기본(20자, 한 쪽): 35°를 넘는다");
            var p = NewPanel("comfort");
            p.ApplyUiOptions(true, false, false);
            int max = p.MaxBodyLinesWithin(Center, Eye);
            Assert.That(max, Is.EqualTo(PlacementPanelMetrics.MaxBodyLinesWithin()));
            foreach (var when in new[] { PlacementTaskText.WhenPre, PlacementTaskText.WhenPost })
                foreach (var page in PlacementPanelMetrics.SentencePages(t.InstructionFor(when), PlacementPanelMetrics.ComfortWrapChars, max))
                {
                    p.ShowText(page, Center, Eye);
                    double metric = PlacementPanelMetrics.BottomBelowHorizonDeg(p.PanelSizeM.y);
                    Assert.That(p.BottomBelowHorizonDeg, Is.LessThanOrEqualTo(35f), page);
                    Assert.That(p.BottomBelowHorizonDeg, Is.EqualTo(metric).Within(0.05), "판의 실제 자리 = 지표 식");
                }
            // 직접 배치 + 놓기 도움 범위 안내(6줄 → 26자 5줄)
            p.ShowText(t["condition_place"] + "\n" + t[PlacementTaskText.PlacementRangeKey], Center, Eye);
            Assert.That(p.BottomBelowHorizonDeg, Is.LessThanOrEqualTo(35f));
            Assert.That(p.WrapCharsShown, Is.EqualTo(26));
            Assert.That(WidthDeg(p), Is.LessThanOrEqualTo(41f));
        }

        [Test]
        public void Dark_theme_uses_unlit_emission_panel_and_light_text()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var p = NewPanel("dark");
            p.ApplyUiOptions(false, true, false);
            var a1 = ScaleA().Items.First(i => i.Key == "A1");
            p.ShowItem(a1, 4, Center, Eye);
            Assert.That(p.DarkTheme, Is.True);
            var bg = Mat(p, "panel background");
            Assert.That(bg.color.r + bg.color.g + bg.color.b, Is.EqualTo(0f), "알베도 검정(조명 반사 없음)");
            Assert.That(bg.GetFloat("_Metallic"), Is.EqualTo(1f));
            var e = bg.GetColor("_EmissionColor");
            Assert.That(e.r, Is.EqualTo(42 / 255f).Within(1e-4f));
            Assert.That(e.b, Is.EqualTo(48 / 255f).Within(1e-4f));
            Assert.That(bg.IsKeywordEnabled("_EMISSION"), Is.True);
            var body = Root(p).Find("panel body").GetComponent<TextMesh>();
            var expected = new Color(230 / 255f, 230 / 255f, 232 / 255f, 1f);
            if (QualitySettings.activeColorSpace == ColorSpace.Linear) expected = expected.linear;
            Assert.That(body.color.r, Is.EqualTo(expected.r).Within(1.5f / 255f));
            var fill = Mat(p, "selected cell fill").GetColor("_EmissionColor");
            Assert.That(fill.b, Is.EqualTo(80 / 255f).Within(1e-4f));
            var frame = Mat(p, "selected cell frame").GetColor("_EmissionColor");
            Assert.That(frame.b, Is.EqualTo(1f).Within(1e-4f), "테두리 = 고른 칸 글색 #9EC3FF");
        }

        [Test]
        public void Narrow_scale_keeps_every_7_point_item_panel_within_41_degrees()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var t = ScaleA();
            var off = NewPanel("off");
            var on = NewPanel("narrow");
            on.ApplyUiOptions(true, false, true);
            var a1 = t.Items.First(i => i.Key == "A1");
            off.ShowItem(a1, null, Center, Eye);
            Assert.That(WidthDeg(off), Is.GreaterThan(41f), "기본 0.22 m: 41.6°");
            foreach (var item in t.Items)
            {
                on.ShowItem(item, null, Center, Eye);
                off.ShowItem(item, null, Center, Eye);
                Assert.That(WidthDeg(on), Is.LessThanOrEqualTo(41f), item.Key);
                TestContext.WriteLine($"{item.Key}: 폭 {WidthDeg(off):0.0}° → {WidthDeg(on):0.0}°, 아래 {off.BottomBelowHorizonDeg:0.0}° → {on.BottomBelowHorizonDeg:0.0}°");
            }
        }

        [Test]
        public void Confirm_flash_thickens_only_the_selected_frame()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var p = NewPanel("flash");
            var a1 = ScaleA().Items.First(i => i.Key == "A1");
            p.ShowItem(a1, 4, Center, Eye);
            var normalFill = Root(p).Find("selected cell fill").localScale;
            var normalFrame = Root(p).Find("selected cell frame").localScale;
            var size = p.PanelSizeM;
            p.ShowItem(a1, 4, Center, Eye, confirmFlash: true);
            Assert.That(p.SelectionFrameShownM, Is.EqualTo(0.02f));
            var flashFill = Root(p).Find("selected cell fill").localScale;
            Assert.That(normalFill.x - flashFill.x, Is.EqualTo(2f * (0.02f - 0.012f)).Within(1e-5f), "바탕이 테두리만큼 줄어든다(테두리 0.012 → 0.02 m)");
            Assert.That(Root(p).Find("selected cell frame").localScale, Is.EqualTo(normalFrame), "칸 크기는 그대로");
            Assert.That(p.PanelSizeM, Is.EqualTo(size), "판 크기·글은 그대로");
            Assert.That(p.SelectedValue, Is.EqualTo(4));
        }

        sealed class FakeController : IXrControllerSource
        {
            public XrControllerSample Next = XrControllerSample.None;
            public string DeviceName => Next.Valid ? "fake controller" : null;
            public XrControllerSample Read() => Next;
        }

        [Test]
        public void Ray_hover_changes_ray_color_and_end_size_only()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            var xr = new GameObject("xr").AddComponent<XrPlacementInput>();
            var ctrl = new FakeController { Next = new XrControllerSample { Valid = true, HasPose = true, RayOrigin = new PVec3(0, 1.2, 0), RayDirection = new PVec3(0, 0, 1) } };
            xr.SetSource(ctrl);
            xr.Read();
            xr.ShowRay(true, 1.5);
            Assert.That(xr.RayState, Is.EqualTo(XrRayState.Idle));
            Assert.That(xr.RayEndDiameterShownM, Is.EqualTo(0.03f));
            Assert.That(xr.RayWidthShownM, Is.EqualTo(0.004f));
            var end = xr.transform.Find("xr ray end").GetComponent<MeshRenderer>().sharedMaterial;
            var idle = end.color;
            xr.ShowRay(true, 1.5, XrRayState.Hover);
            Assert.That(xr.RayEndDiameterShownM, Is.EqualTo(0.045f));
            Assert.That(xr.RayWidthShownM, Is.EqualTo(0.004f));
            Assert.That(end.color, Is.Not.EqualTo(idle));
            xr.ShowRay(true, 1.5, XrRayState.Held);
            Assert.That(xr.RayWidthShownM, Is.EqualTo(0.006f));
            xr.ShowRay(true, 1.5, XrRayState.Idle);
            Assert.That(end.color, Is.EqualTo(idle), "기본 상태로 돌아오면 원래 색");
            Assert.That(xr.SendHaptic(PlacementHaptics.For(PlacementHaptics.Confirm)), Is.False, "가짜 장치에는 보내지 않는다");
        }
    }
}
