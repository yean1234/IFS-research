// '나' 기준 공간(X45): 원형 바닥(경계가 보임), 중심의 '나' 자리 표식, 옅은 거리 고리(끌 수 있음), 가구·벽 없음.
// 세계 원점이 '나'의 자리, 바닥 y = 0, 정면 = +z. 코드로 만든다(에셋 없음).
// 머티리얼: 프리미티브의 기본 머티리얼(내장 Standard)을 복제해 색만 바꾼다 — Shader.Find를 쓰지 않아 빌드에서 빠지지 않는다.
// 기존 중립 환경(IFSEnvironment)의 200 m 격자 바닥은 이 러너 장면에서만 숨긴다(하늘·조명은 그대로 쓴다). 다른 장면에는 영향 없음.
using System.Collections.Generic;
using UnityEngine;

namespace IFS.SceneSpec.Placement
{
    public sealed class PlacementSpaceHandle
    {
        public GameObject Root;
        public GameObject Floor, Boundary, SelfMarker, PointerMarker, TargetMarker;
        public readonly List<GameObject> Rings = new List<GameObject>();
        public readonly List<Object> Owned = new List<Object>();   // 만든 머티리얼·메시(정리용)

        public void Dispose()
        {
            foreach (var o in Owned) Destroy(o);
            Owned.Clear();
            Destroy(Root);
            Root = null;
        }

        static void Destroy(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Object.Destroy(o);
            else Object.DestroyImmediate(o);
        }
    }

    public static class PlacementSpace
    {
        public const string RootName = "Placement Space ('나' 기준)";
        public static readonly Color FloorColor = new Color(0.62f, 0.62f, 0.63f, 1f);
        public static readonly Color BoundaryColor = new Color(0.36f, 0.36f, 0.38f, 1f);
        public static readonly Color RingColor = new Color(0.55f, 0.55f, 0.56f, 1f);
        public static readonly Color SelfColor = new Color(0.45f, 0.47f, 0.52f, 1f);
        public static readonly Color PointerColor = new Color(0.30f, 0.45f, 0.70f, 1f);

        const int Segments = 128;

        public static PlacementSpaceHandle Build(PlacementConfig cfg, Transform parent = null)
        {
            var h = new PlacementSpaceHandle { Root = new GameObject(RootName) };
            if (parent != null) h.Root.transform.SetParent(parent, false);
            float r = (float)cfg.floorRadiusM;

            // 바닥 원판: 원기둥(지름 1, 높이 2)을 납작하게. 윗면이 y = 0.
            h.Floor = Primitive(h, PrimitiveType.Cylinder, "floor disc", FloorColor);
            h.Floor.transform.localScale = new Vector3(2f * r, 0.005f, 2f * r);
            h.Floor.transform.localPosition = new Vector3(0f, -0.005f, 0f);

            // 경계: 바닥 가장자리의 진한 띠(바깥은 바닥이 없어 하늘 아래쪽 색이 보인다)
            h.Boundary = Annulus(h, "boundary", r - 0.06f, r, 0.003f, BoundaryColor);

            if (cfg.showRings)
                foreach (var rr in cfg.ringRadiiM ?? new double[0])
                    h.Rings.Add(Annulus(h, $"ring {rr:0.##} m", (float)rr - 0.01f, (float)rr + 0.01f, 0.002f, RingColor));

            // '나'의 자리 표식(지름 0.5 m 원판)
            h.SelfMarker = Primitive(h, PrimitiveType.Cylinder, "self marker", SelfColor);
            h.SelfMarker.transform.localScale = new Vector3(0.5f, 0.002f, 0.5f);
            h.SelfMarker.transform.localPosition = new Vector3(0f, 0.002f, 0f);

            // 가리켜 지정: 가리키는 점·목표 점(처음엔 숨김)
            h.PointerMarker = Annulus(h, "pointer", 0.08f, 0.14f, 0.004f, PointerColor);
            h.PointerMarker.SetActive(false);
            h.TargetMarker = Annulus(h, "target", 0.16f, 0.20f, 0.004f, PointerColor);
            h.TargetMarker.SetActive(false);
            return h;
        }

        /// <summary>환경의 격자 바닥을 숨긴다(이 러너 장면에서만).</summary>
        public static void HideEnvironmentFloor()
        {
            foreach (var env in Object.FindObjectsByType<IFSEnvironment>(FindObjectsSortMode.None))
                if (env != null && env.Handle != null && env.Handle.Floor != null) env.Handle.Floor.enabled = false;
        }

        static GameObject Primitive(PlacementSpaceHandle h, PrimitiveType type, string name, Color color)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(h.Root.transform, false);
            RemoveCollider(go);
            var rend = go.GetComponent<MeshRenderer>();
            if (rend != null)
            {
                var m = new Material(rend.sharedMaterial) { name = "IFS placement " + name };
                m.color = color;
                rend.sharedMaterial = m;
                rend.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                rend.receiveShadows = true;
                h.Owned.Add(m);
            }
            return go;
        }

        // 고리(납작한 환형 메시). Quad 프리미티브의 메시를 바꿔 끼운다(기본 머티리얼을 얻으려고).
        static GameObject Annulus(PlacementSpaceHandle h, string name, float inner, float outer, float y, Color color)
        {
            var go = Primitive(h, PrimitiveType.Quad, name, color);
            var mesh = AnnulusMesh(Mathf.Max(0f, inner), outer);
            h.Owned.Add(mesh);
            var mf = go.GetComponent<MeshFilter>();
            if (mf != null) mf.sharedMesh = mesh;
            go.transform.localPosition = new Vector3(0f, y, 0f);
            return go;
        }

        public static Mesh AnnulusMesh(float inner, float outer)
        {
            var v = new Vector3[Segments * 2];
            var n = new Vector3[Segments * 2];
            var tri = new int[Segments * 6];
            for (int i = 0; i < Segments; i++)
            {
                float a = 2f * Mathf.PI * i / Segments;
                float s = Mathf.Sin(a), c = Mathf.Cos(a);
                v[2 * i] = new Vector3(s * inner, 0f, c * inner);
                v[2 * i + 1] = new Vector3(s * outer, 0f, c * outer);
                n[2 * i] = n[2 * i + 1] = Vector3.up;
                int j = (i + 1) % Segments;
                // 위에서 볼 때 시계 방향(Unity 앞면)
                tri[6 * i] = 2 * i; tri[6 * i + 1] = 2 * i + 1; tri[6 * i + 2] = 2 * j;
                tri[6 * i + 3] = 2 * j; tri[6 * i + 4] = 2 * i + 1; tri[6 * i + 5] = 2 * j + 1;
            }
            var mesh = new Mesh { name = "annulus" };
            mesh.vertices = v;
            mesh.normals = n;
            mesh.triangles = tri;
            mesh.RecalculateBounds();
            return mesh;
        }

        static void RemoveCollider(GameObject go)
        {
            var col = go.GetComponent<Collider>();
            if (col == null) return;
            if (Application.isPlaying) Object.Destroy(col);
            else Object.DestroyImmediate(col);
        }

        public static Vector3 ToUnity(PVec3 p) => new Vector3((float)p.X, (float)p.Y, (float)p.Z);
        public static PVec3 FromUnity(Vector3 v) => new PVec3(v.x, v.y, v.z);
    }
}
