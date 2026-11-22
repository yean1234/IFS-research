// fragments 조각 메시(X67, FragmentMesh) 테스트: 결정성·조각 수·바운즈·다른 seed.
using System;
using System.Linq;
using NUnit.Framework;

namespace IFS.SceneSpec.Tests
{
    public class FragmentMeshTests
    {
        static (float[] xyz, float[] nrm, int[] tris, int[] piece) Build(int seed, int pieces = FragmentMesh.DefaultPieces)
        {
            FragmentMesh.Build(seed, pieces, out var xyz, out var nrm, out var tris, out var piece);
            return (xyz, nrm, tris, piece);
        }

        [Test]
        public void Same_seed_gives_the_same_vertices()
        {
            var a = Build(0);
            var b = Build(0);
            Assert.That(FragmentMesh.Hash(b.xyz), Is.EqualTo(FragmentMesh.Hash(a.xyz)));
            Assert.That(b.tris, Is.EqualTo(a.tris));
            Assert.That(b.nrm, Is.EqualTo(a.nrm));
        }

        [Test]
        public void Different_seed_gives_a_different_mesh()
        {
            Assert.That(FragmentMesh.Hash(Build(1).xyz), Is.Not.EqualTo(FragmentMesh.Hash(Build(0).xyz)));
            Assert.That(FragmentMesh.Hash(Build(7).xyz), Is.Not.EqualTo(FragmentMesh.Hash(Build(1).xyz)));
        }

        [Test]
        public void Default_is_five_flat_shaded_pieces_in_one_small_mesh()
        {
            var m = Build(FragmentMesh.DefaultSeed);
            Assert.That(m.piece.Distinct().Count(), Is.EqualTo(5));
            Assert.That(m.tris.Length / 3, Is.EqualTo(5 * 20));                 // 조각마다 정이십면체 20면
            Assert.That(m.xyz.Length / 3, Is.EqualTo(m.tris.Length));            // 평면 음영: 면마다 정점 3개
            for (int i = 0; i < m.nrm.Length; i += 3)
            {
                double len = Math.Sqrt(m.nrm[i] * m.nrm[i] + m.nrm[i + 1] * m.nrm[i + 1] + m.nrm[i + 2] * m.nrm[i + 2]);
                Assert.That(len, Is.EqualTo(1.0).Within(1e-4));
            }
        }

        [Test]
        public void Triangles_face_outward_from_their_piece()
        {
            var m = Build(FragmentMesh.DefaultSeed);
            int faces = 20;
            for (int p = 0; p < 5; p++)
            {
                // 조각 중심 = 그 조각 정점의 평균
                double cx = 0, cy = 0, cz = 0;
                for (int t = p * faces; t < (p + 1) * faces; t++)
                    for (int k = 0; k < 3; k++) { int v = m.tris[t * 3 + k]; cx += m.xyz[v * 3]; cy += m.xyz[v * 3 + 1]; cz += m.xyz[v * 3 + 2]; }
                cx /= faces * 3; cy /= faces * 3; cz /= faces * 3;
                int outward = 0;
                for (int t = p * faces; t < (p + 1) * faces; t++)
                {
                    int a = m.tris[t * 3], b = m.tris[t * 3 + 1], c = m.tris[t * 3 + 2];
                    double ux = m.xyz[b * 3] - m.xyz[a * 3], uy = m.xyz[b * 3 + 1] - m.xyz[a * 3 + 1], uz = m.xyz[b * 3 + 2] - m.xyz[a * 3 + 2];
                    double vx = m.xyz[c * 3] - m.xyz[a * 3], vy = m.xyz[c * 3 + 1] - m.xyz[a * 3 + 1], vz = m.xyz[c * 3 + 2] - m.xyz[a * 3 + 2];
                    double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                    double mx = (m.xyz[a * 3] + m.xyz[b * 3] + m.xyz[c * 3]) / 3 - cx;
                    double my = (m.xyz[a * 3 + 1] + m.xyz[b * 3 + 1] + m.xyz[c * 3 + 1]) / 3 - cy;
                    double mz = (m.xyz[a * 3 + 2] + m.xyz[b * 3 + 2] + m.xyz[c * 3 + 2]) / 3 - cz;
                    if (nx * mx + ny * my + nz * mz > 0) outward++;
                }
                Assert.That(outward, Is.EqualTo(faces), "조각 " + p);
            }
        }

        [Test]
        public void Overall_bounds_stay_close_to_the_previous_five_spheres()
        {
            // 이전 경로: 중심 ±0.38 + 구 반지름 최대 0.21(굴곡 포함 ≈ 0.25, 렌더러 바운즈는 더 넓음) → 조각 메시도 [-0.8, 0.8] 안, 각 축 폭 0.6 이상
            var m = Build(FragmentMesh.DefaultSeed);
            for (int axis = 0; axis < 3; axis++)
            {
                double lo = double.MaxValue, hi = double.MinValue;
                for (int i = axis; i < m.xyz.Length; i += 3) { lo = Math.Min(lo, m.xyz[i]); hi = Math.Max(hi, m.xyz[i]); }
                Assert.That(lo, Is.GreaterThan(-0.8), "축 " + axis);
                Assert.That(hi, Is.LessThan(0.8), "축 " + axis);
                Assert.That(hi - lo, Is.GreaterThan(0.6), "축 " + axis);
            }
        }

        [Test]
        public void Fragments_plan_carries_the_preset_defaults()
        {
            var o = OwnershipTestSpecs.Empty("FRAGPLAN").Slot("form.type", "fragments", "조각");
            var spec = o.Parse();
            var p = SceneParams.FromSpec(spec, new SceneDefaults());
            var plan = FormRenderPlan.Build(p, "fragments", ShapeMapping.Resolve(spec));
            Assert.That(plan.FragmentPieces, Is.EqualTo(FragmentMesh.DefaultPieces));
            Assert.That(plan.FragmentSeed, Is.EqualTo(FragmentMesh.DefaultSeed));
            Assert.That(plan.ZeroDisplacement, Is.True);
            Assert.That(plan.PresetNote, Does.Contain("형상 프리셋 기본값"));
        }
    }
}
