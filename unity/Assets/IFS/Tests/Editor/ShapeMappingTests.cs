// EditMode 테스트: 모양어 → 모양 모형(docs/shape-mapping.md). UnityEngine 없이 도는 부분만(원뿔 메시, 판정 규칙).
// 예시 모양어는 합성 문장에서 온 것이다(참여자 데이터 아님).
using System;
using System.IO;
using System.Linq;
using Newtonsoft.Json.Linq;
using NUnit.Framework;
using UnityEngine;

namespace IFS.SceneSpec.Tests
{
    public class ShapeMappingTests
    {
        // ── 원뿔 메시 ─────────────────────────────────────────────────────
        static (double x, double y, double z) V(float[] a, int i) => (a[i * 3], a[i * 3 + 1], a[i * 3 + 2]);

        static (double x, double y, double z) Cross((double x, double y, double z) u, (double x, double y, double z) v) =>
            (u.y * v.z - u.z * v.y, u.z * v.x - u.x * v.z, u.x * v.y - u.y * v.x);

        static double Dot((double x, double y, double z) u, (double x, double y, double z) v) => u.x * v.x + u.y * v.y + u.z * v.z;

        static (double x, double y, double z) Sub((double x, double y, double z) a, (double x, double y, double z) b) =>
            (a.x - b.x, a.y - b.y, a.z - b.z);

        [TestCase(48)]
        [TestCase(8)]
        public void Cone_mesh_has_expected_counts_bounds_and_valid_indices(int segments)
        {
            ConeMesh.Build(segments, out var xyz, out var normals, out var tris);
            int vc = xyz.Length / 3;
            Assert.That(vc, Is.EqualTo(ConeMesh.VertexCount(segments)).And.EqualTo(3 * segments + 1));
            Assert.That(normals.Length, Is.EqualTo(xyz.Length));
            Assert.That(tris.Length / 3, Is.EqualTo(ConeMesh.TriangleCount(segments)).And.EqualTo(2 * segments));
            Assert.That(tris.All(i => i >= 0 && i < vc), Is.True, "모든 인덱스가 정점 범위 안");
            Assert.That(Enumerable.Range(0, vc).All(i => tris.Contains(i)), Is.True, "쓰지 않는 정점이 없다");

            double minX = double.MaxValue, maxX = double.MinValue, minY = double.MaxValue, maxY = double.MinValue,
                   minZ = double.MaxValue, maxZ = double.MinValue;
            for (int i = 0; i < vc; i++)
            {
                var p = V(xyz, i);
                minX = Math.Min(minX, p.x); maxX = Math.Max(maxX, p.x);
                minY = Math.Min(minY, p.y); maxY = Math.Max(maxY, p.y);
                minZ = Math.Min(minZ, p.z); maxZ = Math.Max(maxZ, p.z);
                var n = V(normals, i);
                Assert.That(Math.Sqrt(Dot(n, n)), Is.EqualTo(1.0).Within(1e-5), "단위 법선 " + i);
            }
            // 밑면 지름 1, 높이 1, 경계 상자 가운데 = 원점
            Assert.That(maxX - minX, Is.EqualTo(1.0).Within(1e-5));
            Assert.That(maxZ - minZ, Is.EqualTo(1.0).Within(1e-5));
            Assert.That(maxY - minY, Is.EqualTo(1.0).Within(1e-6));
            Assert.That((minX + maxX) / 2, Is.EqualTo(0.0).Within(1e-5));
            Assert.That((minY + maxY) / 2, Is.EqualTo(0.0).Within(1e-6));
            Assert.That((minZ + maxZ) / 2, Is.EqualTo(0.0).Within(1e-5));
        }

        [Test]
        public void Cone_mesh_faces_point_outward_and_agree_with_vertex_normals()
        {
            ConeMesh.Build(ConeMesh.DefaultSegments, out var xyz, out var normals, out var tris);
            int down = 0, side = 0;
            for (int t = 0; t < tris.Length; t += 3)
            {
                var a = V(xyz, tris[t]);
                var b = V(xyz, tris[t + 1]);
                var c = V(xyz, tris[t + 2]);
                var face = Cross(Sub(b, a), Sub(c, a));   // Unity 앞면 규칙: cross(b − a, c − a)가 바깥(IcoSphere와 같음)
                Assert.That(Math.Sqrt(Dot(face, face)), Is.GreaterThan(1e-9), "넓이 0인 삼각형 " + t / 3);
                var centroid = ((a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3, (a.z + b.z + c.z) / 3);
                Assert.That(Dot(face, centroid), Is.GreaterThan(0), "바깥을 향한다(원점 = 경계 상자 가운데) " + t / 3);
                for (int k = 0; k < 3; k++)
                    Assert.That(Dot(face, V(normals, tris[t + k])), Is.GreaterThan(0), "면 방향과 정점 법선이 같은 쪽 " + t / 3);
                if (face.y < 0 && Math.Abs(face.x) < 1e-9 && Math.Abs(face.z) < 1e-9) down++;
                else side++;
            }
            Assert.That(down, Is.EqualTo(ConeMesh.DefaultSegments), "밑면 뚜껑");
            Assert.That(side, Is.EqualTo(ConeMesh.DefaultSegments), "옆면");
        }

        [Test]
        public void Cone_base_rim_is_a_hard_edge()
        {
            // 밑면 테두리 = 같은 위치에 옆면 정점(비스듬한 법선)과 밑면 정점(아래 법선)이 따로 있다
            int n = ConeMesh.DefaultSegments;
            ConeMesh.Build(n, out var xyz, out var normals, out _);
            for (int i = 0; i < n; i++)
            {
                var side = V(xyz, i);
                var cap = V(xyz, 2 * n + i);
                Assert.That(Dot(Sub(side, cap), Sub(side, cap)), Is.LessThan(1e-12), "같은 위치 " + i);
                Assert.That(V(normals, 2 * n + i), Is.EqualTo((0.0, -1.0, 0.0)));
                Assert.That(V(normals, i).y, Is.GreaterThan(0).And.LessThan(1), "옆면 법선은 비스듬히 위");
            }
            Assert.Throws<ArgumentOutOfRangeException>(() => ConeMesh.Build(2, out _, out _, out _));
        }

        // ── 판정 규칙 ─────────────────────────────────────────────────────
        static ShapeWord W(string shape, string trigger, int start) => new ShapeWord(shape, trigger, start, start + trigger.Length);

        [Test]
        public void Table_has_exactly_four_shapes()
        {
            Assert.That(ShapeMapping.ModelByShape.Keys.OrderBy(k => k, StringComparer.Ordinal),
                Is.EqualTo(new[] { "flat", "pointed", "round", "square" }));
            Assert.That(ShapeMapping.ModelFor("round"), Is.EqualTo("Sphere"));
            Assert.That(ShapeMapping.ModelFor("square"), Is.EqualTo("Cube"));
            Assert.That(ShapeMapping.ModelFor("flat"), Is.EqualTo("FlatCylinder"));
            Assert.That(ShapeMapping.ModelFor("pointed"), Is.EqualTo("Cone"));
        }

        [Test]
        public void No_shape_words_is_none()
        {
            var r = ShapeMapping.Resolve(new ShapeWord[0], null);
            Assert.That(r.Status, Is.EqualTo("none"));
            Assert.That(r.Applied, Is.Null);
            Assert.That(r.Model, Is.Null);
            Assert.That(r.Words, Is.Empty);
        }

        [TestCase("round", "Sphere")]
        [TestCase("square", "Cube")]
        [TestCase("flat", "FlatCylinder")]
        [TestCase("pointed", "Cone")]
        public void Mapped_shape_is_applied_when_form_is_unstated_or_blob(string shape, string model)
        {
            foreach (var form in new[] { null, "blob" })
            {
                var r = ShapeMapping.Resolve(new[] { W(shape, "말", 3) }, form);
                Assert.That(r.Status, Is.EqualTo("applied"), form ?? "null");
                Assert.That(r.Applied, Is.EqualTo(shape));
                Assert.That(r.Model, Is.EqualTo(model));
                Assert.That(r.Words.Single().Status, Is.EqualTo("applied"));
            }
        }

        [TestCase("circle")] [TestCase("sharp")] [TestCase("thin")] [TestCase("thick")] [TestCase("elongated")]
        [TestCase("long")] [TestCase("triangle")] [TestCase("angular")] [TestCase("bumpy")] [TestCase("hollow")]
        [TestCase("hole")] [TestCase("edge")] [TestCase("dot")] [TestCase("thread")] [TestCase("sheet")]
        [TestCase("never_seen_value")]
        public void Other_shape_values_are_unmapped_not_turned_into_a_sphere(string shape)
        {
            var r = ShapeMapping.Resolve(new[] { W(shape, "말", 0) }, null);
            Assert.That(r.Status, Is.EqualTo("unmapped_shape"));
            Assert.That(r.Applied, Is.Null);
            Assert.That(r.Model, Is.Null, "구로 몰래 바꾸지 않는다");
            Assert.That(r.Words.Single().Status, Is.EqualTo("unmapped_shape"));
        }

        [Test]
        public void First_mapped_word_in_span_order_wins_and_unmapped_words_stay_recorded()
        {
            // 입력 순서를 섞어도 charSpan 순서로 본다(H26과 같은 꼴: 실 → 둥글게)
            var r = ShapeMapping.Resolve(new[] { W("round", "둥글게", 64), W("thread", "실", 61) }, null);
            Assert.That(r.Status, Is.EqualTo("applied"));
            Assert.That(r.Applied, Is.EqualTo("round"));
            Assert.That(r.Words.Select(w => w.Shape), Is.EqualTo(new[] { "thread", "round" }));
            Assert.That(r.Words.Select(w => w.Status), Is.EqualTo(new[] { "unmapped_shape", "applied" }));
        }

        [Test]
        public void Different_mapped_shapes_apply_the_first_and_mark_the_rest_conflict()
        {
            var r = ShapeMapping.Resolve(new[] { W("pointed", "뾰족", 30), W("square", "네모", 5), W("round", "둥글", 50),
                                                 W("square", "네모나", 70) }, "blob");
            Assert.That(r.Applied, Is.EqualTo("square"));
            Assert.That(r.Model, Is.EqualTo("Cube"));
            Assert.That(r.Words.Select(w => w.Status), Is.EqualTo(new[] { "applied", "conflict", "conflict", "applied" }));
        }

        [TestCase("mist")]
        [TestCase("shell")]
        [TestCase("fragments")]
        public void Stated_non_blob_form_keeps_its_model(string form)
        {
            var r = ShapeMapping.Resolve(new[] { W("square", "네모", 5) }, form);
            Assert.That(r.Status, Is.EqualTo("not_applied_form"));
            Assert.That(r.Model, Is.Null);
            Assert.That(r.FormType, Is.EqualTo(form));
            Assert.That(r.Words.Single().Status, Is.EqualTo("not_applied_form"));

            // 표에 없는 모양어가 함께 있으면 맨 위 상태는 unmapped_shape(규칙), 낱말 목록에는 둘 다 남는다
            var mixed = ShapeMapping.Resolve(new[] { W("square", "네모", 5), W("edge", "가장자리", 20) }, form);
            Assert.That(mixed.Status, Is.EqualTo("unmapped_shape"));
            Assert.That(mixed.Words.Select(w => w.Status), Is.EqualTo(new[] { "not_applied_form", "unmapped_shape" }));
        }

        [Test]
        public void Resolve_does_not_change_its_input_and_is_deterministic()
        {
            var input = new[] { W("round", "동그란", 9), W("edge", "가장자리", 1) };
            var a = ShapeMapping.Resolve(input, null).ToJson();
            var b = ShapeMapping.Resolve(input, null).ToJson();
            Assert.That(JToken.DeepEquals(a, b), Is.True);
            Assert.That(input.All(w => w.Status == null), Is.True);
            Assert.That(a["viaPrefab"].Type, Is.EqualTo(JTokenType.Null), "로더가 모형을 만들기 전에는 null");
            Assert.That(a["words"][0]["charSpan"].Values<int>(), Is.EqualTo(new[] { 1, 5 }));
        }

        [Test]
        public void Words_are_read_from_unmapped_shape_entries_of_a_spec()
        {
            // EX01은 '가장자리'(edge)를 _unmapped 모양어로 갖고 있다 → 적용 없음, 기록만
            var spec = SceneSpecJson.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX01.json"));
            var r = ShapeMapping.Resolve(spec);
            Assert.That(r.Words.Select(w => (w.Shape, w.Trigger, w.Lemma)), Is.EqualTo(new[] { ("edge", "가장자리", "가장자리") }));
            Assert.That(r.Words[0].CharSpan, Is.EqualTo(new[] { 20, 24 }));
            Assert.That(r.Status, Is.EqualTo("unmapped_shape"));
            Assert.That(r.FormType, Is.EqualTo("blob"));

            // 다른 category의 _unmapped 항목은 모양어가 아니다
            var ex02 = SceneSpecJson.Load(Path.Combine(Application.streamingAssetsPath, "IFS", "examples", "EX02.json"));
            Assert.That(ShapeMapping.Resolve(ex02).Status, Is.EqualTo("none"));
        }
    }
}
