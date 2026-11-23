// 참여자 판·실험자 화면의 표현 계산(2026-11-23 G44 화면 개선): 시야각, WCAG 대비비, 기본 색·글자 크기,
// 기준점 칸 너비·뜻 줄바꿈(이웃 칸 뜻이 겹치지 않음), 고른 칸, 중단 두 번 누르기. dotnet·Unity 둘 다에서 돈다.
using System.IO;
using System.Linq;
using IFS.SceneSpec.Ownership;
using IFS.SceneSpec.Placement;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public sealed class PlacementPanelMetricsTests
    {
        const double M = PlacementPanelMetrics.MinTextAngleDeg;

        [Test]
        public void Visual_angle_matches_the_closed_form_and_inverts()
        {
            double d = PlacementPanelMetrics.DefaultViewDistanceM;
            Assert.That(d, Is.EqualTo(System.Math.Sqrt(5.0)).Within(1e-9), "정면 2.0 m, 눈높이 1.6 − 판 중심 0.6 = 1.0 m");
            // 본문 글자 칸 0.0085 × 64 × 0.1 = 0.0544 m → 2·atan(0.0544 / (2·2.236)) = 1.394°
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(0.0544, d), Is.EqualTo(1.394).Within(0.001));
            Assert.That(PlacementPanelMetrics.SizeForAngleM(1.0, d), Is.EqualTo(0.03903).Within(1e-4), "2.236 m에서 1°");
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(PlacementPanelMetrics.SizeForAngleM(1.7, 3.0), 3.0), Is.EqualTo(1.7).Within(1e-9));
            Assert.Throws<System.ArgumentOutOfRangeException>(() => PlacementPanelMetrics.VisualAngleDeg(0.05, 0));
        }

        [Test]
        public void Default_text_sizes_are_at_least_one_degree_of_ink_at_the_default_distance()
        {
            double d = PlacementPanelMetrics.DefaultViewDistanceM;
            int fs = PlacementPanelMetrics.FontSize;
            double body = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.BodyCharacterSize, fs) * PlacementPanelMetrics.HangulInkPerEm;
            double label = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.LabelCharacterSize, fs) * PlacementPanelMetrics.HangulInkPerEm;
            double digit = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.NumberCharacterSize, fs) * PlacementPanelMetrics.DigitInkPerEm;
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(body, d), Is.GreaterThanOrEqualTo(M), "본문 한글");
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(label, d), Is.GreaterThanOrEqualTo(M), "기준점 뜻 한글");
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(digit, d), Is.GreaterThanOrEqualTo(M), "평정 숫자");
            // 고치기 전 기준점 뜻(0.0055)은 1°가 되지 않았다(실측 잉크 0.85°)
            double before = PlacementPanelMetrics.EmHeightM(0.0055, fs) * PlacementPanelMetrics.HangulInkPerEm;
            Assert.That(PlacementPanelMetrics.VisualAngleDeg(before, d), Is.LessThan(M));
        }

        [Test]
        public void Contrast_ratio_follows_wcag()
        {
            Assert.That(PlacementPanelMetrics.ContrastRatio(new[] { 0.0, 0, 0 }, new[] { 1.0, 1, 1 }), Is.EqualTo(21.0).Within(1e-9));
            Assert.That(PlacementPanelMetrics.ContrastRatio(new[] { 0.5, 0.5, 0.5 }, new[] { 0.5, 0.5, 0.5 }), Is.EqualTo(1.0).Within(1e-9));
            // WCAG 예: #777777 대 흰색 ≈ 4.48
            double g = 0x77 / 255.0;
            Assert.That(PlacementPanelMetrics.ContrastRatio(new[] { g, g, g }, new[] { 1.0, 1, 1 }), Is.EqualTo(4.48).Within(0.01));
            Assert.That(PlacementPanelMetrics.ContrastRatio(0.2, 0.9), Is.EqualTo(PlacementPanelMetrics.ContrastRatio(0.9, 0.2)), "순서 무관");
        }

        [Test]
        public void Default_panel_colors_meet_four_and_a_half_to_one()
        {
            var text = PlacementPanelMetrics.TextSrgb;
            var bg = PlacementPanelMetrics.BackgroundSrgb;
            var hi = PlacementPanelMetrics.HighlightSrgb;
            var fill = PlacementPanelMetrics.SelectionFillSrgb;
            Assert.That(PlacementPanelMetrics.ContrastRatio(text, bg), Is.GreaterThanOrEqualTo(4.5), "본문 대 판");
            Assert.That(PlacementPanelMetrics.ContrastRatio(hi, bg), Is.GreaterThanOrEqualTo(4.5), "고른 값 대 판");
            Assert.That(PlacementPanelMetrics.ContrastRatio(hi, fill), Is.GreaterThanOrEqualTo(4.5), "고른 값 대 고른 칸 바탕");
            Assert.That(PlacementPanelMetrics.ContrastRatio(hi, new[] { 1.0, 1, 1 }), Is.GreaterThanOrEqualTo(4.5), "판이 하얗게 렌더돼도");
            // 고치기 전 고른 숫자 색(0.10, 0.35, 0.85)이 선형 값으로 쓰여 보이던 색 #5AA0ED는 흰 판에서 4.5:1이 안 됐다
            Assert.That(PlacementPanelMetrics.ContrastRatio(new[] { 0x5A / 255.0, 0xA0 / 255.0, 0xED / 255.0 }, new[] { 1.0, 1, 1 }), Is.LessThan(4.5));
        }

        [Test]
        public void Column_width_shrinks_past_seven_points_and_label_wrap_fits_the_column()
        {
            Assert.That(PlacementPanelMetrics.ColumnWidth(7, 0.22), Is.EqualTo(0.22).Within(1e-12));
            Assert.That(PlacementPanelMetrics.ColumnWidth(5, 0.22), Is.EqualTo(0.22).Within(1e-12));
            Assert.That(PlacementPanelMetrics.ColumnWidth(11, 0.22) * 11, Is.EqualTo(0.22 * 7).Within(1e-12), "0–10: 줄 전체가 7칸 너비");
            double em = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.LabelCharacterSize, PlacementPanelMetrics.FontSize);
            Assert.That(PlacementPanelMetrics.LabelWrapChars(0.22, em), Is.EqualTo(4));
            Assert.That(PlacementPanelMetrics.LabelWrapChars(0.01, em), Is.EqualTo(2), "최소 2자");
            Assert.That(PlacementPanelMetrics.LabelWrapChars(0.22, 0), Is.EqualTo(2));
        }

        [Test]
        public void ScaleA_anchor_labels_do_not_run_into_the_neighbouring_column()
        {
            // 7점 모두 이름이 있는 scaleA A1: 칸 너비 0.22 m, 뜻 글자 칸 0.048 m. 줄바꿈 뒤 이웃한 두 뜻 사이에 빈틈이 있어야 한다.
            var text = PlacementTaskText.Load(Path.Combine(Application.streamingAssetsPath, PlacementXrTests.ScaleARelativePath));
            double em = PlacementPanelMetrics.EmHeightM(PlacementPanelMetrics.LabelCharacterSize, PlacementPanelMetrics.FontSize);
            const double col = 0.22;
            int wrap = System.Math.Min(6, PlacementPanelMetrics.LabelWrapChars(col, em));
            foreach (var item in text.Items.Where(i => i.Points.Count == i.Max - i.Min + 1))
            {
                var widths = Enumerable.Range(item.Min, item.Max - item.Min + 1)
                    .Select(v => ParticipantTextDisplay.Wrap(item.AnchorAt(v), wrap).Split('\n').Max(l => Units(l)) * em).ToArray();
                for (int i = 0; i + 1 < widths.Length; i++)
                    Assert.That(col - (widths[i] + widths[i + 1]) / 2, Is.GreaterThan(0.02), $"{item.Key}: {i + item.Min}·{i + item.Min + 1} 뜻 사이 빈틈(2 cm 이상)");
            }
        }

        static double Units(string line) => line.Sum(c => c >= 0x1100 ? 1.0 : 0.55);

        [Test]
        public void Selected_cell_is_only_the_cursor_value()
        {
            Assert.That(PlacementPanelMetrics.IsSelected(6, 6), Is.True);
            Assert.That(PlacementPanelMetrics.IsSelected(6, 5), Is.False);
            Assert.That(PlacementPanelMetrics.IsSelected(null, 0), Is.False, "고르기 전에는 표시 없음(0–10의 0도)");
        }

        [Test]
        public void Abort_needs_two_presses_in_the_same_stage()
        {
            var c = new PlacementConfirmStep();
            Assert.That(c.IsArmed("Running|pre_items"), Is.False);
            Assert.That(c.Confirm("Running|pre_items"), Is.False, "열지 않고 확정하면 아무 일도 없음");
            c.Arm("Running|pre_items");
            Assert.That(c.IsArmed("Running|pre_items"), Is.True);
            Assert.That(c.Confirm("Running|pre_items"), Is.True);
            Assert.That(c.ArmedFor, Is.Null, "확정 뒤 닫힘");
            c.Arm("Running|pre_items");
            Assert.That(c.Confirm("Running|pre_wait"), Is.False, "단계가 바뀐 뒤의 확정은 무시");
            Assert.That(c.ArmedFor, Is.Null);
            c.Arm("Running|condition");
            c.Cancel();
            Assert.That(c.IsArmed("Running|condition"), Is.False, "취소");
        }
    }
}
