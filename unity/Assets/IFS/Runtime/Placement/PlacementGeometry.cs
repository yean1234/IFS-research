// 배치 실험의 기하 계산(UnityEngine 없이, 분석기와 같은 정의 — 기록 형식 계약 ifs-placement/0.1 「좌표와 거리의 기준」).
//   '나'의 자리(self) = 원형 바닥 중심 (0, 0, 0), 바닥 y = 0, 정면 = +z, 오른쪽 = +x.
//   distance_m = self에서 물체까지 수평 거리, azimuth_deg = +z 기준 수평 방위(오른쪽 +, (−180, 180]), height_m = 물체 중심 높이.
using System;

namespace IFS.SceneSpec.Placement
{
    /// <summary>세계 좌표 점·벡터(미터, double). Unity Vector3와 따로 두어 dotnet에서도 같은 계산을 한다.</summary>
    [Serializable]
    public struct PVec3
    {
        public double X, Y, Z;
        public PVec3(double x, double y, double z) { X = x; Y = y; Z = z; }
        public static PVec3 Zero => new PVec3(0, 0, 0);
        public static PVec3 operator +(PVec3 a, PVec3 b) => new PVec3(a.X + b.X, a.Y + b.Y, a.Z + b.Z);
        public static PVec3 operator -(PVec3 a, PVec3 b) => new PVec3(a.X - b.X, a.Y - b.Y, a.Z - b.Z);
        public static PVec3 operator *(PVec3 a, double s) => new PVec3(a.X * s, a.Y * s, a.Z * s);
        public double Length => Math.Sqrt(X * X + Y * Y + Z * Z);
        public double HorizontalLength => Math.Sqrt(X * X + Z * Z);
        public static double Dot(PVec3 a, PVec3 b) => a.X * b.X + a.Y * b.Y + a.Z * b.Z;
        public PVec3 Normalized { get { double l = Length; return l > 1e-12 ? this * (1.0 / l) : Zero; } }
        public static double Distance(PVec3 a, PVec3 b) => (a - b).Length;
        public static PVec3 Lerp(PVec3 a, PVec3 b, double t) => a + (b - a) * t;
        public override string ToString() => $"({X:0.###}, {Y:0.###}, {Z:0.###})";
    }

    public static class PlacementGeometry
    {
        const double Rad = Math.PI / 180.0;

        public static double HorizontalDistance(PVec3 p) => p.HorizontalLength;

        /// <summary>+z 기준 수평 방위(도). 오른쪽(+x)이 +, 범위 (−180, 180]. 중심(거리 0)이면 0.</summary>
        public static double AzimuthDeg(PVec3 p)
        {
            if (p.HorizontalLength < 1e-12) return 0;
            double a = Math.Atan2(p.X, p.Z) / Rad;
            return a <= -180.0 ? a + 360.0 : a;
        }

        /// <summary>(수평 거리, 방위, 높이) → 세계 좌표.</summary>
        public static PVec3 FromPolar(double distanceM, double azimuthDeg, double heightM) =>
            new PVec3(Math.Sin(azimuthDeg * Rad) * distanceM, heightM, Math.Cos(azimuthDeg * Rad) * distanceM);

        /// <summary>바닥 원판(반지름 radius) 안, 높이 [minH, maxH] 안으로 자른다. 방향은 지키고 수평 거리만 줄인다.</summary>
        public static PVec3 ClampToSpace(PVec3 p, double radius, double minH, double maxH)
        {
            double h = p.HorizontalLength;
            double x = p.X, z = p.Z;
            if (h > radius && h > 1e-12)
            {
                double s = radius / h;
                x *= s;
                z *= s;
            }
            double y = Math.Min(maxH, Math.Max(minH, p.Y));
            return new PVec3(x, y, z);
        }

        /// <summary>광선(원점 o, 방향 d)과 구(중심 c, 반지름 r)의 가장 가까운 앞쪽 교차까지 거리. 없으면 false.</summary>
        public static bool RaySphere(PVec3 o, PVec3 d, PVec3 c, double r, out double t)
        {
            t = 0;
            d = d.Normalized;
            if (d.Length < 0.5) return false;
            var oc = o - c;
            double b = PVec3.Dot(oc, d);
            double cc = PVec3.Dot(oc, oc) - r * r;
            double disc = b * b - cc;
            if (disc < 0) return false;
            double s = Math.Sqrt(disc);
            double t0 = -b - s, t1 = -b + s;
            if (t1 < 0) return false;          // 구가 뒤에 있다
            t = t0 >= 0 ? t0 : 0;              // 원점이 구 안이면 0
            return true;
        }

        /// <summary>광선이 바닥(y = floorY)과 만나는 점. 위를 보거나 평행하면 false.</summary>
        public static bool RayFloor(PVec3 o, PVec3 d, double floorY, out PVec3 hit)
        {
            hit = PVec3.Zero;
            d = d.Normalized;
            if (d.Y > -1e-6) return false;
            double t = (floorY - o.Y) / d.Y;
            if (t < 0) return false;
            hit = o + d * t;
            hit.Y = floorY;
            return true;
        }

        /// <summary>점 p를 광선 위로 내린 거리(광선 방향 성분). 잡을 때 '잡은 거리'로 쓴다.</summary>
        public static double AlongRay(PVec3 o, PVec3 d, PVec3 p) => PVec3.Dot(p - o, d.Normalized);

        /// <summary>a에서 b로 최대 step만큼 직선으로 간다. 도착하면 arrived = true.</summary>
        public static PVec3 MoveTowards(PVec3 a, PVec3 b, double step, out bool arrived)
        {
            var d = b - a;
            double l = d.Length;
            if (l <= step || l < 1e-9) { arrived = true; return b; }
            arrived = false;
            return a + d * (step / l);
        }
    }
}
