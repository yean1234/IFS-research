// EditMode 테스트(Unity 전용): 참여자 판의 표현(2026-11-23 G44 화면 개선).
//   고른 칸은 색·굵기·테두리로 표시, 고르기 전에는 표시 없음, 글자색은 선형 색공간에서 선형 값으로 넘김(Inspector 색이 그대로 보이게),
//   긴 지시문처럼 키가 큰 판은 위 가장자리가 maxTopM(0.85 m)을 넘지 않게 내려가고 짧은 판은 받은 중심 그대로.
// 문구는 문구 파일(scaleA, 합성 아님 — IRB 대상 문구 그대로 읽기만)을 쓰고, 화면 표현만 확인한다.
using System.IO;
using System.Linq;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class PlacementTextPanelTests
    {
        static readonly Vector3 Center = new Vector3(0f, 0.6f, 2.0f);
        static readonly Vector3 Eye = new Vector3(0f, 1.6f, 0f);

        static PlacementTextPanel NewPanel()
        {
            EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);
            return new GameObject("panel host").AddComponent<PlacementTextPanel>();
        }

        static PlacementTaskText ScaleA() =>
            PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementXrTests.ScaleARelativePath));

        static Transform Root(PlacementTextPanel p) => p.transform.Find("participant panel");

        [Test]
        public void Selected_value_gets_frame_bold_and_highlight_and_nothing_before_choosing()
        {
            var panel = NewPanel();
            var a1 = ScaleA().Items.First(i => i.Key == "A1");
            panel.ShowItem(a1, null, Center, Eye);
            var root = Root(panel);
            Assert.That(panel.SelectedValue, Is.Null);
            Assert.That(root.Find("selected cell frame").gameObject.activeSelf, Is.False, "고르기 전 테두리 없음");
            Assert.That(root.Find("selected cell fill").gameObject.activeSelf, Is.False);

            panel.ShowItem(a1, 6, Center, Eye);
            Assert.That(panel.SelectedValue, Is.EqualTo(6));
            Assert.That(root.Find("selected cell frame").gameObject.activeSelf, Is.True, "테두리(모양)");
            Assert.That(root.Find("selected cell fill").gameObject.activeSelf, Is.True, "바탕");
            var number = root.Find("scale number 5").GetComponent<TextMesh>();
            var label = root.Find("scale label 5").GetComponent<TextMesh>();
            Assert.That(number.text, Is.EqualTo("<b>6</b>"), "굵기");
            Assert.That(label.text, Does.StartWith("<b>").And.Contain(a1.AnchorAt(6)), "뜻도 굵게(문구 글자는 그대로)");
            var other = root.Find("scale number 4").GetComponent<TextMesh>();
            Assert.That(other.text, Is.EqualTo("5"));
            Assert.That(number.color, Is.Not.EqualTo(other.color), "색");
            // 선형 색공간: TextMesh 정점 색은 선형 값이어야 sRGB(Inspector) 색이 그대로 보인다
            var expected = QualitySettings.activeColorSpace == ColorSpace.Linear ? new Color(0.08f, 0.08f, 0.1f, 1f).linear : new Color(0.08f, 0.08f, 0.1f, 1f);
            Assert.That(other.color.r, Is.EqualTo(expected.r).Within(1.5f / 255f), "TextMesh 색은 8비트로 저장된다");
            Assert.That(other.color.r, Is.LessThan(0.03f), "sRGB 0.08을 그대로 넘기지 않음");

            // 테두리는 고른 칸(6, 오른쪽에서 두 번째) 위치에 있다
            var frame = root.Find("selected cell frame");
            Assert.That(frame.localPosition.x, Is.EqualTo(number.transform.localPosition.x).Within(1e-4f));
            panel.ShowItem(a1, null, Center, Eye);
            Assert.That(root.Find("selected cell frame").gameObject.activeSelf, Is.False, "고른 값을 지우면 테두리도 사라짐");
            Object.DestroyImmediate(panel.gameObject);
        }

        [Test]
        public void Tall_panel_stays_below_max_top_and_short_panel_keeps_its_center()
        {
            var panel = NewPanel();
            var text = ScaleA();
            panel.ShowText(text["intro"], Center, Eye);
            Assert.That(panel.PanelCenter.y, Is.EqualTo(Center.y).Within(1e-4f), "짧은 판은 받은 중심 그대로");
            Assert.That(panel.PanelCenter.z, Is.EqualTo(Center.z).Within(1e-4f));

            panel.ShowText(text.InstructionFor(PlacementTaskText.WhenPre), Center, Eye);
            var root = Root(panel);
            float half = panel.PanelSizeM.y * 0.5f;
            float top = (root.position + root.up * half).y, bottom = (root.position - root.up * half).y;
            Assert.That(panel.PanelSizeM.y, Is.GreaterThan(0.6f), "긴 지시문은 키가 크다");
            Assert.That(top, Is.LessThanOrEqualTo(0.85f + 1e-3f), "위 가장자리 ≤ maxTopM");
            Assert.That(bottom, Is.GreaterThanOrEqualTo(0.05f - 1e-3f), "아래 가장자리 ≥ minBottomM");
            Assert.That(panel.PanelCenter.z, Is.EqualTo(Center.z).Within(1e-4f), "앞뒤 거리는 그대로");
            Object.DestroyImmediate(panel.gameObject);
        }
    }
}
