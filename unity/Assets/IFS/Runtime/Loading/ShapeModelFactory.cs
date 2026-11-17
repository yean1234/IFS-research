// 모양 모형 4종(Sphere · Cube · FlatCylinder · Cone)을 만드는 한 곳.
// 메뉴 IFS ▸ Create Shape Prefabs가 프리팹을 만들 때와, 프리팹이 연결되지 않았을 때 SceneLoader가 코드로 만들 때
// 같은 함수를 쓴다(두 경로의 형상이 같다).
// 구조: 루트 = 빈 GameObject(크기 1,1,1) → 자식 "mesh"에 메시·렌더러·콜라이더. 배율(납작 원기둥의 Y 0.2)은 자식에만 둔다.
// 크기 척도는 Unity 기본 프리미티브와 같다(지름 1). 로더는 절차 모형과 같은 기본 크기(primitiveBaseSize)로 줄여 쓴다.
using UnityEngine;

namespace IFS.SceneSpec
{
    public static class ShapeModelFactory
    {
        public const string MeshChildName = "mesh";

        /// <summary>납작 원기둥 자식의 배율. Unity 원기둥은 지름 1·높이 2라 결과는 지름 1·두께 0.4.</summary>
        public static readonly Vector3 FlatCylinderChildScale = new Vector3(1f, 0.2f, 1f);

        /// <summary>모형 이름 → 자식 배율(표에 없으면 1,1,1).</summary>
        public static Vector3 ChildScale(string model) =>
            model == ShapeMapping.ModelFlatCylinder ? FlatCylinderChildScale : Vector3.one;

        /// <summary>원뿔 메시(ConeMesh.Build → Mesh). 메뉴는 이것을 에셋으로 저장하고, 로더는 한 번 만들어 재사용한다.</summary>
        public static Mesh BuildConeMesh(string name = "IFS Cone")
        {
            var mesh = new Mesh { name = name };
            FillConeMesh(mesh);
            return mesh;
        }

        /// <summary>이미 있는 메시를 원뿔로 다시 채운다(에셋을 같은 GUID로 덮어쓸 때).</summary>
        public static void FillConeMesh(Mesh mesh)
        {
            ConeMesh.Build(ConeMesh.DefaultSegments, out float[] xyz, out float[] nrm, out int[] tris);
            var verts = new Vector3[xyz.Length / 3];
            var normals = new Vector3[verts.Length];
            for (int i = 0; i < verts.Length; i++)
            {
                verts[i] = new Vector3(xyz[i * 3], xyz[i * 3 + 1], xyz[i * 3 + 2]);
                normals[i] = new Vector3(nrm[i * 3], nrm[i * 3 + 1], nrm[i * 3 + 2]);
            }
            mesh.Clear();
            mesh.vertices = verts;
            mesh.normals = normals;
            mesh.triangles = tris;
            mesh.RecalculateBounds();
        }

        /// <summary>
        /// 모형 하나를 만든다. material은 렌더러에 그대로 넣는다(null이면 프리미티브 기본 머티리얼을 둔다).
        /// coneMesh는 Cone일 때만 쓴다(null이면 새로 만든다). 표에 없는 모형 이름이면 null.
        /// </summary>
        public static GameObject Create(string model, Material material, Mesh coneMesh = null)
        {
            GameObject child;
            switch (model)
            {
                case ShapeMapping.ModelSphere: child = GameObject.CreatePrimitive(PrimitiveType.Sphere); break;
                case ShapeMapping.ModelCube: child = GameObject.CreatePrimitive(PrimitiveType.Cube); break;
                case ShapeMapping.ModelFlatCylinder: child = GameObject.CreatePrimitive(PrimitiveType.Cylinder); break;
                case ShapeMapping.ModelCone:
                {
                    child = new GameObject(MeshChildName);
                    var mesh = coneMesh != null ? coneMesh : BuildConeMesh();
                    child.AddComponent<MeshFilter>().sharedMesh = mesh;
                    child.AddComponent<MeshRenderer>();
                    var col = child.AddComponent<MeshCollider>();
                    col.sharedMesh = mesh;
                    col.convex = true;
                    break;
                }
                default: return null;
            }
            child.name = MeshChildName;
            var root = new GameObject(model);
            child.transform.SetParent(root.transform, false);
            child.transform.localPosition = Vector3.zero;
            child.transform.localRotation = Quaternion.identity;
            child.transform.localScale = ChildScale(model);
            root.transform.localScale = Vector3.one;
            if (material != null)
                foreach (var r in child.GetComponentsInChildren<Renderer>(true)) r.sharedMaterial = material;
            return root;
        }
    }
}
