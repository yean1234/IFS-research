// 기록·배치에 쓰는 기하 계산(UnityEngine 없이, 분석 스크립트와 같은 정의).
//   angle_deg = 머리 정면(회전 q로 돌린 +Z)과 머리→형상 방향 사이 각.
//   호 배치: n개를 같은 반지름에 간격 spacing으로, 가운데를 정면에 둔다. 위치 1이 왼쪽(−각).
using System;

namespace IFS.SceneSpec.Ownership
{
    public static class OwnershipGeometry
    {
        const double Rad = Math.PI / 180.0;

        /// <summary>단위 쿼터니언 (x, y, z, w)으로 돌린 +Z(Unity 정면).</summary>
        public static void Forward(double qx, double qy, double qz, double qw, out double fx, out double fy, out double fz)
        {
            fx = 2.0 * (qx * qz + qw * qy);
            fy = 2.0 * (qy * qz - qw * qx);
            fz = 1.0 - 2.0 * (qx * qx + qy * qy);
        }

        /// <summary>두 벡터 사이 각(도). 길이가 0이면 NaN.</summary>
        public static double AngleDeg(double ax, double ay, double az, double bx, double by, double bz)
        {
            double la = Math.Sqrt(ax * ax + ay * ay + az * az), lb = Math.Sqrt(bx * bx + by * by + bz * bz);
            if (la < 1e-12 || lb < 1e-12) return double.NaN;
            double c = (ax * bx + ay * by + az * bz) / (la * lb);
            return Math.Acos(Math.Max(-1.0, Math.Min(1.0, c))) / Rad;
        }

        /// <summary>머리 자세와 형상 위치 → (거리 m, 시선 각 도).</summary>
        public static void DistanceAngle(double hx, double hy, double hz, double qx, double qy, double qz, double qw,
            double ox, double oy, double oz, out double distance, out double angleDeg)
        {
            double dx = ox - hx, dy = oy - hy, dz = oz - hz;
            distance = Math.Sqrt(dx * dx + dy * dy + dz * dz);
            Forward(qx, qy, qz, qw, out double fx, out double fy, out double fz);
            angleDeg = AngleDeg(fx, fy, fz, dx, dy, dz);
        }

        /// <summary>n개를 간격 spacingDeg로 가운데 정렬한 각(도). 왼쪽(−)부터.</summary>
        public static double[] CenteredAngles(int n, double spacingDeg)
        {
            var a = new double[n];
            for (int i = 0; i < n; i++) a[i] = (i - (n - 1) / 2.0) * spacingDeg;
            return a;
        }

        /// <summary>이웃한 형상(가장 넓은 폭 maxWidth m)이 margin m 이상 떨어지는 최소 반지름.</summary>
        public static double MinRadiusWithoutOverlap(double spacingDeg, double maxWidth, double margin)
        {
            double half = Math.Sin(spacingDeg * Rad / 2.0);
            if (half < 1e-9) return double.PositiveInfinity;
            return (maxWidth + margin) / (2.0 * half);
        }

        /// <summary>앵커(ax, az)·정면 방위(yawDeg, +Z 기준 시계 방향)에서 각 angleDeg, 반지름 r인 수평 위치.</summary>
        public static void ArcPoint(double ax, double az, double yawDeg, double angleDeg, double r, out double x, out double z)
        {
            double t = (yawDeg + angleDeg) * Rad;
            x = ax + Math.Sin(t) * r;
            z = az + Math.Cos(t) * r;
        }
    }
}
