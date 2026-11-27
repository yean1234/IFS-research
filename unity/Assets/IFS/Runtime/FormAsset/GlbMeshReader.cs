// G62: 생성 형태 메시(GLB)에서 삼각형 메시의 위치·삼각형만 읽는다(머티리얼·텍스처·법선·색은 읽지 않음 — 색·재질·발광은
// 기존 스펙 값으로 만든 머티리얼을 입히므로 GLB의 것은 버린다). glTFast를 쓰지 않는 이유: 동기·결정적으로 읽어 러너의 시작 흐름
// (StartSession, 동기)에 그대로 넣을 수 있고, 헤드셋 빌드에서 glTFast 셰이더 포함 문제를 이 경로가 겪지 않으며, Unity 없이
// compile-check·NUnit으로 확인할 수 있다. 실험 경로의 보기용 로더(Experimental/Gen3D/Gen3DGlbLoader)는 그대로 glTFast를 쓴다.
//
// 받는 것: glTF 2.0 바이너리(GLB), BIN 청크 버퍼 하나(외부 uri 없음), 장면(scene/scenes) 노드 계층의 메시, 프리미티브 mode 4(삼각형),
// POSITION = float VEC3, indices = 없음·u8·u16·u32 SCALAR. 노드 변환(matrix 또는 TRS)을 곱한다.
// 받지 않는 것(이유를 돌려주고 러너는 절차 메시로 돌아감): extensionsRequired(Draco·meshopt 등), sparse 접근자, 정수 위치, 다른 mode.
// 좌표: glTF(오른손, +Y 위)를 Unity(왼손)로 — glTFast와 같이 x를 뒤집고 삼각형 감김 순서를 바꾼다. 회전은 하지 않는다(D8 5절).
// 법선은 면 넓이 가중 평균으로 직접 계산한다(같은 입력 → 같은 결과). UnityEngine에 의존하지 않는다.
using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Text;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace IFS.SceneSpec.FormAsset
{
    public sealed class GlbMesh
    {
        /// <summary>정점 위치 x,y,z(Unity 좌표, GLB 단위 그대로).</summary>
        public float[] Positions;
        /// <summary>정점 법선 x,y,z(면 넓이 가중 평균, 단위 벡터).</summary>
        public float[] Normals;
        /// <summary>삼각형 정점 번호(Unity 감김 순서).</summary>
        public int[] Triangles;
        public double[] Min = new double[3], Max = new double[3];
        public int VertexCount => Positions.Length / 3;
        public int TriangleCount => Triangles.Length / 3;
        public double[] Size => new[] { Max[0] - Min[0], Max[1] - Min[1], Max[2] - Min[2] };
        public double[] Center => new[] { (Max[0] + Min[0]) / 2, (Max[1] + Min[1]) / 2, (Max[2] + Min[2]) / 2 };
        public double LongestEdge { get { var s = Size; return Math.Max(s[0], Math.Max(s[1], s[2])); } }
    }

    public static class GlbMeshReader
    {
        public const uint Magic = 0x46546C67, ChunkJson = 0x4E4F534A, ChunkBin = 0x004E4942;
        /// <summary>정점 수 상한(헤드셋 메모리 보호). 넘으면 읽지 않는다.</summary>
        public const int MaxVertices = 4_000_000;

        /// <summary>GLB 바이트 → 메시. 실패하면 null과 이유(error).</summary>
        public static GlbMesh Read(byte[] glb, out string error)
        {
            error = null;
            try
            {
                return ReadOrThrow(glb);
            }
            catch (Exception e) when (e is FormatException || e is JsonException || e is ArgumentException || e is IndexOutOfRangeException ||
                                      e is InvalidCastException || e is OverflowException || e is NullReferenceException)
            {
                error = e.Message;
                return null;
            }
        }

        static GlbMesh ReadOrThrow(byte[] glb)
        {
            if (glb == null || glb.Length < 20) throw new FormatException("GLB가 너무 짧음");
            if (U32(glb, 0) != Magic) throw new FormatException("GLB 매직(glTF)이 아님");
            if (U32(glb, 4) != 2) throw new FormatException("glTF 2.0 바이너리가 아님(version " + U32(glb, 4) + ")");
            long total = U32(glb, 8);
            if (total > glb.Length) throw new FormatException("GLB 길이 머리값이 파일보다 김");
            int off = 12;
            string json = null;
            byte[] bin = null;
            while (off + 8 <= total)
            {
                int len = checked((int)U32(glb, off));
                uint type = U32(glb, off + 4);
                if (off + 8 + (long)len > total) throw new FormatException("청크가 파일 밖으로 나감");
                if (type == ChunkJson && json == null) json = Encoding.UTF8.GetString(glb, off + 8, len);
                else if (type == ChunkBin && bin == null) { bin = new byte[len]; Buffer.BlockCopy(glb, off + 8, bin, 0, len); }
                off += 8 + len;
            }
            if (json == null) throw new FormatException("JSON 청크가 없음");
            var root = JObject.Parse(json);
            if (root["extensionsRequired"] is JArray req && req.Count > 0)
                throw new FormatException("필수 확장을 지원하지 않음: " + string.Join(",", req));
            var buffers = root["buffers"] as JArray;
            if (buffers != null)
                for (int i = 0; i < buffers.Count; i++)
                    if (buffers[i]?["uri"] != null) throw new FormatException("외부 버퍼(uri)는 받지 않음");
            var accessors = root["accessors"] as JArray ?? throw new FormatException("accessors가 없음");
            var views = root["bufferViews"] as JArray ?? throw new FormatException("bufferViews가 없음");
            var meshes = root["meshes"] as JArray ?? throw new FormatException("meshes가 없음");
            var nodes = root["nodes"] as JArray ?? new JArray();

            var pos = new List<float>();
            var tris = new List<int>();
            // 장면 노드부터(없으면 부모가 없는 모든 노드, 노드도 없으면 메시 0을 단위 변환으로)
            var roots = new List<int>();
            var scenes = root["scenes"] as JArray;
            int sceneIndex = root["scene"]?.Type == JTokenType.Integer ? (int)root["scene"] : 0;
            if (scenes != null && sceneIndex < scenes.Count && scenes[sceneIndex]?["nodes"] is JArray sn)
                foreach (var n in sn) roots.Add((int)n);
            else
            {
                var isChild = new bool[nodes.Count];
                foreach (var n in nodes) if (n?["children"] is JArray ch) foreach (var c in ch) isChild[(int)c] = true;
                for (int i = 0; i < nodes.Count; i++) if (!isChild[i]) roots.Add(i);
            }
            if (nodes.Count == 0)
                AppendMesh(meshes, 0, Identity(), accessors, views, bin, pos, tris);
            else
            {
                var visiting = new HashSet<int>();
                foreach (int r in roots) Walk(r, Identity(), nodes, meshes, accessors, views, bin, pos, tris, visiting);
            }
            if (tris.Count == 0) throw new FormatException("삼각형이 없음");

            var m = new GlbMesh { Positions = pos.ToArray(), Triangles = tris.ToArray() };
            m.Normals = ComputeNormals(m.Positions, m.Triangles);
            for (int k = 0; k < 3; k++) { m.Min[k] = double.PositiveInfinity; m.Max[k] = double.NegativeInfinity; }
            for (int i = 0; i < m.Positions.Length; i += 3)
                for (int k = 0; k < 3; k++)
                {
                    double v = m.Positions[i + k];
                    if (v < m.Min[k]) m.Min[k] = v;
                    if (v > m.Max[k]) m.Max[k] = v;
                }
            return m;
        }

        static void Walk(int ni, double[] parent, JArray nodes, JArray meshes, JArray accessors, JArray views, byte[] bin,
                         List<float> pos, List<int> tris, HashSet<int> visiting)
        {
            if (ni < 0 || ni >= nodes.Count) throw new FormatException("노드 번호가 범위 밖: " + ni);
            if (!visiting.Add(ni)) throw new FormatException("노드 계층에 고리가 있음");
            var node = (JObject)nodes[ni];
            var world = Mul(parent, LocalMatrix(node));
            if (node["mesh"] != null) AppendMesh(meshes, (int)node["mesh"], world, accessors, views, bin, pos, tris);
            if (node["children"] is JArray ch) foreach (var c in ch) Walk((int)c, world, nodes, meshes, accessors, views, bin, pos, tris, visiting);
            visiting.Remove(ni);
        }

        static void AppendMesh(JArray meshes, int mi, double[] mat, JArray accessors, JArray views, byte[] bin, List<float> pos, List<int> tris)
        {
            if (mi < 0 || mi >= meshes.Count) throw new FormatException("메시 번호가 범위 밖: " + mi);
            var prims = meshes[mi]?["primitives"] as JArray ?? throw new FormatException("primitives가 없음");
            bool flip = Det3(mat) < 0;   // 음의 배율이면 감김이 한 번 더 뒤집힘
            foreach (var p in prims)
            {
                int mode = p["mode"]?.Type == JTokenType.Integer ? (int)p["mode"] : 4;
                if (mode != 4) throw new FormatException("삼각형(mode 4)이 아닌 프리미티브: mode " + mode);
                var posAcc = p["attributes"]?["POSITION"] ?? throw new FormatException("POSITION이 없음");
                float[] xyz = ReadFloatVec3(accessors, views, bin, (int)posAcc);
                int baseIndex = pos.Count / 3;
                int count = xyz.Length / 3;
                if (baseIndex + count > MaxVertices) throw new FormatException("정점이 너무 많음(> " + MaxVertices + ")");
                for (int i = 0; i < count; i++)
                {
                    double x = xyz[i * 3], y = xyz[i * 3 + 1], z = xyz[i * 3 + 2];
                    double wx = mat[0] * x + mat[4] * y + mat[8] * z + mat[12];
                    double wy = mat[1] * x + mat[5] * y + mat[9] * z + mat[13];
                    double wz = mat[2] * x + mat[6] * y + mat[10] * z + mat[14];
                    pos.Add((float)-wx); pos.Add((float)wy); pos.Add((float)wz);   // glTF → Unity: x 뒤집기
                }
                int[] idx = p["indices"] != null ? ReadIndices(accessors, views, bin, (int)p["indices"]) : Sequential(count);
                if (idx.Length % 3 != 0) throw new FormatException("삼각형 번호 수가 3의 배수가 아님");
                for (int t = 0; t < idx.Length; t += 3)
                {
                    int a = idx[t], b = idx[t + 1], c = idx[t + 2];
                    if (a >= count || b >= count || c >= count || a < 0 || b < 0 || c < 0) throw new FormatException("삼각형 번호가 정점 범위 밖");
                    // x를 뒤집으면 감김이 바뀌므로 (a, c, b). 음의 배율 노드면 한 번 더 바꿔 원래대로
                    if (flip) { tris.Add(baseIndex + a); tris.Add(baseIndex + b); tris.Add(baseIndex + c); }
                    else { tris.Add(baseIndex + a); tris.Add(baseIndex + c); tris.Add(baseIndex + b); }
                }
            }
        }

        static int[] Sequential(int n) { var a = new int[n]; for (int i = 0; i < n; i++) a[i] = i; return a; }

        static (byte[] data, int start, int stride, int count) View(JArray accessors, JArray views, byte[] bin, int ai, int elementSize,
                                                                      out JObject acc)
        {
            if (ai < 0 || ai >= accessors.Count) throw new FormatException("접근자 번호가 범위 밖: " + ai);
            acc = (JObject)accessors[ai];
            if (acc["sparse"] != null) throw new FormatException("sparse 접근자는 받지 않음");
            if (acc["bufferView"] == null) throw new FormatException("bufferView가 없는 접근자는 받지 않음");
            var view = (JObject)views[(int)acc["bufferView"]];
            if (bin == null) throw new FormatException("BIN 청크가 없음");
            if (view["buffer"] != null && (int)view["buffer"] != 0) throw new FormatException("버퍼 0(BIN)만 받음");
            int count = (int)acc["count"];
            int start = (view["byteOffset"] != null ? (int)view["byteOffset"] : 0) + (acc["byteOffset"] != null ? (int)acc["byteOffset"] : 0);
            int stride = view["byteStride"] != null ? (int)view["byteStride"] : elementSize;
            int viewEnd = (view["byteOffset"] != null ? (int)view["byteOffset"] : 0) + (int)view["byteLength"];
            if (count < 0 || stride < elementSize) throw new FormatException("접근자 count·stride가 잘못됨");
            if (count > 0 && (long)start + (long)stride * (count - 1) + elementSize > Math.Min(viewEnd, bin.Length))
                throw new FormatException("접근자가 버퍼 밖으로 나감");
            return (bin, start, stride, count);
        }

        static float[] ReadFloatVec3(JArray accessors, JArray views, byte[] bin, int ai)
        {
            var (data, start, stride, count) = View(accessors, views, bin, ai, 12, out var acc);
            if ((int)acc["componentType"] != 5126 || (string)acc["type"] != "VEC3")
                throw new FormatException("POSITION은 float VEC3여야 함");
            if (acc["normalized"]?.Type == JTokenType.Boolean && (bool)acc["normalized"]) throw new FormatException("정규화 정수 위치는 받지 않음");
            var o = new float[count * 3];
            for (int i = 0; i < count; i++)
                for (int k = 0; k < 3; k++)
                {
                    float v = BitConverter.ToSingle(data, start + i * stride + k * 4);
                    if (float.IsNaN(v) || float.IsInfinity(v)) throw new FormatException("위치에 NaN·무한대가 있음");
                    o[i * 3 + k] = v;
                }
            return o;
        }

        static int[] ReadIndices(JArray accessors, JArray views, byte[] bin, int ai)
        {
            var acc0 = (JObject)accessors[ai];
            int ct = (int)acc0["componentType"];
            int size = ct == 5121 ? 1 : ct == 5123 ? 2 : ct == 5125 ? 4 : throw new FormatException("indices componentType " + ct + "는 받지 않음");
            var (data, start, stride, count) = View(accessors, views, bin, ai, size, out var acc);
            if ((string)acc["type"] != "SCALAR") throw new FormatException("indices는 SCALAR여야 함");
            var o = new int[count];
            for (int i = 0; i < count; i++)
            {
                int at = start + i * stride;
                o[i] = size == 1 ? data[at] : size == 2 ? BitConverter.ToUInt16(data, at) : checked((int)BitConverter.ToUInt32(data, at));
            }
            return o;
        }

        static double[] Identity() => new double[] { 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1 };

        // 열 우선(glTF와 같음): m[col*4 + row]
        static double[] Mul(double[] a, double[] b)
        {
            var o = new double[16];
            for (int c = 0; c < 4; c++)
                for (int r = 0; r < 4; r++)
                {
                    double s = 0;
                    for (int k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
                    o[c * 4 + r] = s;
                }
            return o;
        }

        static double Det3(double[] m) =>
            m[0] * (m[5] * m[10] - m[9] * m[6]) - m[4] * (m[1] * m[10] - m[9] * m[2]) + m[8] * (m[1] * m[6] - m[5] * m[2]);

        static double[] LocalMatrix(JObject node)
        {
            if (node["matrix"] is JArray mat)
            {
                if (mat.Count != 16) throw new FormatException("matrix는 16개 수");
                var o = new double[16];
                for (int i = 0; i < 16; i++) o[i] = (double)mat[i];
                return o;
            }
            double[] t = Vec(node["translation"], 3, 0), r = Vec(node["rotation"], 4, double.NaN), s = Vec(node["scale"], 3, 1);
            double qx = 0, qy = 0, qz = 0, qw = 1;
            if (!double.IsNaN(r[0])) { qx = r[0]; qy = r[1]; qz = r[2]; qw = r[3]; }
            double xx = qx * qx, yy = qy * qy, zz = qz * qz, xy = qx * qy, xz = qx * qz, yz = qy * qz, wx = qw * qx, wy = qw * qy, wz = qw * qz;
            return new[]
            {
                (1 - 2 * (yy + zz)) * s[0], 2 * (xy + wz) * s[0], 2 * (xz - wy) * s[0], 0,
                2 * (xy - wz) * s[1], (1 - 2 * (xx + zz)) * s[1], 2 * (yz + wx) * s[1], 0,
                2 * (xz + wy) * s[2], 2 * (yz - wx) * s[2], (1 - 2 * (xx + yy)) * s[2], 0,
                t[0], t[1], t[2], 1,
            };
        }

        static double[] Vec(JToken tok, int n, double fill)
        {
            var o = new double[n];
            for (int i = 0; i < n; i++) o[i] = fill;
            if (tok is JArray a)
            {
                if (a.Count != n) throw new FormatException("노드 변환 값 수가 잘못됨");
                for (int i = 0; i < n; i++) o[i] = (double)a[i];
            }
            return o;
        }

        /// <summary>정점 법선: 이웃 면 법선의 넓이 가중 합을 정규화(면이 없는 정점은 (0, 1, 0)).</summary>
        public static float[] ComputeNormals(float[] p, int[] t)
        {
            var acc = new double[p.Length];
            for (int i = 0; i < t.Length; i += 3)
            {
                int a = t[i] * 3, b = t[i + 1] * 3, c = t[i + 2] * 3;
                double ux = p[b] - p[a], uy = p[b + 1] - p[a + 1], uz = p[b + 2] - p[a + 2];
                double vx = p[c] - p[a], vy = p[c + 1] - p[a + 1], vz = p[c + 2] - p[a + 2];
                // Unity 문서와 같은 식: 앞면(시계 방향 감김) 법선 = Cross(b − a, c − a). x를 뒤집고 감김을 바꾼 삼각형이라
                // glTF 쪽 바깥 법선의 거울상이 된다
                double nx = uy * vz - uz * vy, ny = uz * vx - ux * vz, nz = ux * vy - uy * vx;
                foreach (int k in new[] { a, b, c }) { acc[k] += nx; acc[k + 1] += ny; acc[k + 2] += nz; }
            }
            var o = new float[p.Length];
            for (int i = 0; i < p.Length; i += 3)
            {
                double len = Math.Sqrt(acc[i] * acc[i] + acc[i + 1] * acc[i + 1] + acc[i + 2] * acc[i + 2]);
                if (len < 1e-20) { o[i + 1] = 1f; continue; }
                o[i] = (float)(acc[i] / len); o[i + 1] = (float)(acc[i + 1] / len); o[i + 2] = (float)(acc[i + 2] / len);
            }
            return o;
        }

        static uint U32(byte[] b, int at) => (uint)(b[at] | (b[at + 1] << 8) | (b[at + 2] << 16) | (b[at + 3] << 24));

        /// <summary>테스트·도구용: 위치·삼각형으로 최소 GLB(버퍼 하나, 노드 하나)를 만든다(glTF 좌표 그대로 넣음).</summary>
        public static byte[] Write(float[] gltfPositions, int[] gltfTriangles)
        {
            var bin = new MemoryStream();
            var w = new BinaryWriter(bin);
            foreach (var f in gltfPositions) w.Write(f);
            int posLen = (int)bin.Length;
            foreach (var i in gltfTriangles) w.Write((uint)i);
            int idxLen = (int)bin.Length - posLen;
            double[] mn = { double.MaxValue, double.MaxValue, double.MaxValue }, mx = { double.MinValue, double.MinValue, double.MinValue };
            for (int i = 0; i < gltfPositions.Length; i += 3)
                for (int k = 0; k < 3; k++) { mn[k] = Math.Min(mn[k], gltfPositions[i + k]); mx[k] = Math.Max(mx[k], gltfPositions[i + k]); }
            var inv = CultureInfo.InvariantCulture;
            string Arr(double[] a) => "[" + string.Join(",", Array.ConvertAll(a, v => ((float)v).ToString("R", inv))) + "]";
            string json = "{\"asset\":{\"version\":\"2.0\"},\"scene\":0,\"scenes\":[{\"nodes\":[0]}],\"nodes\":[{\"mesh\":0}]," +
                          "\"meshes\":[{\"primitives\":[{\"attributes\":{\"POSITION\":0},\"indices\":1}]}]," +
                          $"\"buffers\":[{{\"byteLength\":{bin.Length}}}]," +
                          $"\"bufferViews\":[{{\"buffer\":0,\"byteOffset\":0,\"byteLength\":{posLen}}},{{\"buffer\":0,\"byteOffset\":{posLen},\"byteLength\":{idxLen}}}]," +
                          $"\"accessors\":[{{\"bufferView\":0,\"componentType\":5126,\"count\":{gltfPositions.Length / 3},\"type\":\"VEC3\",\"min\":{Arr(mn)},\"max\":{Arr(mx)}}}," +
                          $"{{\"bufferView\":1,\"componentType\":5125,\"count\":{gltfTriangles.Length},\"type\":\"SCALAR\"}}]}}";
            var js = Encoding.UTF8.GetBytes(json);
            int jsPad = (4 - js.Length % 4) % 4;
            var binBytes = bin.ToArray();
            int total = 12 + 8 + js.Length + jsPad + 8 + binBytes.Length;
            var o = new MemoryStream();
            var ow = new BinaryWriter(o);
            ow.Write(Magic); ow.Write(2u); ow.Write((uint)total);
            ow.Write((uint)(js.Length + jsPad)); ow.Write(ChunkJson); ow.Write(js); for (int i = 0; i < jsPad; i++) ow.Write((byte)0x20);
            ow.Write((uint)binBytes.Length); ow.Write(ChunkBin); ow.Write(binBytes);
            return o.ToArray();
        }
    }
}
