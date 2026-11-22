// XR 컨트롤러 입력(배치 실험, PC + Quest Link, OpenXR). IPlacementInput 구현 — 러너가 inputMode에 따라 데스크톱 입력과 바꿔 쓴다.
// 장치 읽기는 UnityXrControllerSource(내장 XR 모듈 UnityEngine.XR.InputDevices — 패키지 API를 직접 쓰지 않는다),
// 버튼 규칙(눌린 순간·이력·데드존)은 XrPlacementInputLogic(UnityEngine 없음, dotnet 테스트)이 맡는다.
// 조작표는 XrPlacementInputLogic.cs 머리말과 unity/README.md 「헤드셋 연결」.
// 보이는 것: 주 사용 손 자리의 작은 구(컨트롤러가 잡히면 늘), 광선(가는 원기둥 + 끝점 구 — 러너가 입력을 쓰는 단계에서만 켠다).
// 실기 미검증(2026-11-23 — docs/headset-checklist.md).
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.XR;

namespace IFS.SceneSpec.Placement
{
    /// <summary>InputDevices로 주 사용 손 컨트롤러를 읽는다. 추적 공간 좌표를 trackingSpace(리그)로 세계 좌표로 옮긴다.</summary>
    public sealed class UnityXrControllerSource : IXrControllerSource
    {
        // OpenXR 플러그인의 조준(aim) pose 이름. 읽지 못하면 grip pose(devicePosition·deviceRotation)를 쓴다.
        static readonly InputFeatureUsage<Vector3> PointerPosition = new InputFeatureUsage<Vector3>("PointerPosition");
        static readonly InputFeatureUsage<Quaternion> PointerRotation = new InputFeatureUsage<Quaternion>("PointerRotation");

        public Transform TrackingSpace;
        public string Hand = PlacementConfig.HandRight;
        /// <summary>grip pose만 읽힐 때 광선을 아래로 기울이는 각(도). 조준 pose가 있으면 쓰지 않는다.</summary>
        public float GripPitchDeg = 30f;

        public string DeviceName { get; private set; }
        /// <summary>마지막으로 읽은 자세가 조준(pointer) pose였나(false면 grip pose).</summary>
        public bool UsedPointerPose { get; private set; }

        public XrControllerSample Read()
        {
            var s = XrControllerSample.None;
            var device = InputDevices.GetDeviceAtXRNode(Hand == PlacementConfig.HandLeft ? XRNode.LeftHand : XRNode.RightHand);
            if (!device.isValid) { DeviceName = null; return s; }
            DeviceName = device.name;
            s.Valid = true;
            Vector3 pos = Vector3.zero;
            Quaternion rot = Quaternion.identity;
            bool pose;
            if (device.TryGetFeatureValue(PointerPosition, out pos) && device.TryGetFeatureValue(PointerRotation, out rot))
            {
                pose = true;
                UsedPointerPose = true;
            }
            else
            {
                pose = device.TryGetFeatureValue(CommonUsages.devicePosition, out pos) && device.TryGetFeatureValue(CommonUsages.deviceRotation, out rot);
                if (pose) rot = rot * Quaternion.Euler(GripPitchDeg, 0f, 0f);
                UsedPointerPose = false;
            }
            if (pose)
            {
                var dir = rot * Vector3.forward;
                if (TrackingSpace != null)
                {
                    pos = TrackingSpace.TransformPoint(pos);
                    dir = TrackingSpace.TransformDirection(dir);
                }
                s.HasPose = true;
                s.RayOrigin = PlacementSpace.FromUnity(pos);
                s.RayDirection = PlacementSpace.FromUnity(dir);
            }
            if (device.TryGetFeatureValue(CommonUsages.trigger, out float trig)) s.Trigger = trig;
            if (device.TryGetFeatureValue(CommonUsages.triggerButton, out bool tb)) s.TriggerButton = tb;
            if (device.TryGetFeatureValue(CommonUsages.gripButton, out bool gb)) s.GripButton = gb;
            if (device.TryGetFeatureValue(CommonUsages.primaryButton, out bool pb)) s.PrimaryButton = pb;
            if (device.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 stick)) { s.StickX = stick.x; s.StickY = stick.y; }
            return s;
        }
    }

    [DisallowMultipleComponent]
    [AddComponentMenu("IFS/Placement/XR Placement Input")]
    public sealed class XrPlacementInput : MonoBehaviour, IPlacementInput
    {
        public const string Source = "xr";

        [Tooltip("추적 공간 → 세계 좌표(XR 리그 루트). 비우면 추적 공간 = 세계")]
        [SerializeField] Transform trackingSpace = null;
        [Tooltip("주 사용 손: right | left (세션 시작 때 설정 xrHand로 바뀐다)")]
        [SerializeField] string hand = PlacementConfig.HandRight;
        [SerializeField] XrInputTuning tuning = new XrInputTuning();
        [Header("보이는 것")]
        [Tooltip("광선 굵기(m)")] [SerializeField] float rayWidthM = 0.004f;
        [Tooltip("광선 최대 길이(m)")] [SerializeField] float rayMaxLengthM = 8f;
        [Tooltip("광선 끝점 구 지름(m)")] [SerializeField] float rayEndDiameterM = 0.03f;
        [Tooltip("손 자리 구 지름(m)")] [SerializeField] float handDiameterM = 0.035f;
        [SerializeField] Color rayColor = new Color(0.30f, 0.45f, 0.70f, 1f);
        [SerializeField] Color handColor = new Color(0.45f, 0.47f, 0.52f, 1f);

        IXrControllerSource _source;
        XrPlacementInputLogic _logic;
        GameObject _ray, _rayEnd, _handMarker;
        readonly List<Object> _owned = new List<Object>();

        public string SourceName => Source;
        public bool Enabled { get; set; } = true;
        public string Hand => hand;
        /// <summary>마지막으로 읽은 원자료(실험자 화면·광선 표시용).</summary>
        public XrControllerSample LastSample { get; private set; } = XrControllerSample.None;
        public string DeviceName => _source?.DeviceName;
        public float RayMaxLengthM => rayMaxLengthM;

        public void Configure(Transform space, string controllerHand)
        {
            trackingSpace = space;
            if (!string.IsNullOrEmpty(controllerHand)) hand = controllerHand;
            if (_source is UnityXrControllerSource u) { u.TrackingSpace = trackingSpace; u.Hand = hand; }
        }

        /// <summary>장치 읽기를 바꾼다(테스트에서 가짜 장치). null이면 기본(InputDevices).</summary>
        public void SetSource(IXrControllerSource source)
        {
            _source = source;
            _logic = new XrPlacementInputLogic(tuning);
        }

        IXrControllerSource EnsureSource()
        {
            if (_source == null) _source = new UnityXrControllerSource { TrackingSpace = trackingSpace, Hand = hand };
            if (_logic == null) _logic = new XrPlacementInputLogic(tuning);
            return _source;
        }

        /// <summary>지금 주 사용 손 컨트롤러가 연결돼 있나(한 번 읽어 본다 — 버튼 상태는 바꾸지 않는다).</summary>
        public bool ControllerPresent => EnsureSource().Read().Valid;

        public PlacementInputFrame Read()
        {
            var src = EnsureSource();
            LastSample = src.Read();
            var f = _logic.Step(LastSample, Enabled);
            UpdateHandMarker();
            return f;
        }

        void OnDestroy()
        {
            foreach (var o in _owned) DestroySafe(o);
            _owned.Clear();
            DestroySafe(_ray);
            DestroySafe(_rayEnd);
            DestroySafe(_handMarker);
        }

        // ── 보이는 것 ───────────────────────────────────────────────────
        /// <summary>광선을 보이거나 숨긴다. endDistance = 원점에서 끝점까지(m, XrRayVisual.EndDistance).</summary>
        public void ShowRay(bool show, double endDistance)
        {
            var s = LastSample;
            bool visible = show && s.Valid && s.HasPose;
            EnsureVisuals();
            if (!visible)
            {
                if (_ray.activeSelf) _ray.SetActive(false);
                if (_rayEnd.activeSelf) _rayEnd.SetActive(false);
                return;
            }
            var o = PlacementSpace.ToUnity(s.RayOrigin);
            var d = PlacementSpace.ToUnity(s.RayDirection.Normalized);
            float len = Mathf.Max(0.001f, Mathf.Min(rayMaxLengthM, (float)endDistance));
            // 원기둥 프리미티브는 y축으로 높이 2(−1..1) → y를 광선 방향으로 돌리고 길이의 절반으로 늘인다
            _ray.transform.SetPositionAndRotation(o + d * (len * 0.5f), Quaternion.LookRotation(d, Vector3.up) * Quaternion.Euler(90f, 0f, 0f));
            _ray.transform.localScale = new Vector3(rayWidthM, len * 0.5f, rayWidthM);
            _rayEnd.transform.position = o + d * len;
            _rayEnd.transform.localScale = new Vector3(rayEndDiameterM, rayEndDiameterM, rayEndDiameterM);
            if (!_ray.activeSelf) _ray.SetActive(true);
            if (!_rayEnd.activeSelf) _rayEnd.SetActive(true);
        }

        void UpdateHandMarker()
        {
            if (!Application.isPlaying) return;   // 에디터 테스트(자동 시행)에서는 만들지 않는다
            EnsureVisuals();
            var s = LastSample;
            bool on = s.Valid && s.HasPose;
            if (on)
            {
                _handMarker.transform.position = PlacementSpace.ToUnity(s.RayOrigin);
                _handMarker.transform.localScale = new Vector3(handDiameterM, handDiameterM, handDiameterM);
            }
            if (_handMarker.activeSelf != on) _handMarker.SetActive(on);
        }

        void EnsureVisuals()
        {
            if (_ray != null) return;
            _ray = Primitive(PrimitiveType.Cylinder, "xr ray", rayColor);
            _rayEnd = Primitive(PrimitiveType.Sphere, "xr ray end", rayColor);
            _handMarker = Primitive(PrimitiveType.Sphere, "xr hand", handColor);
        }

        GameObject Primitive(PrimitiveType type, string name, Color color)
        {
            var go = GameObject.CreatePrimitive(type);
            go.name = name;
            go.transform.SetParent(transform, false);
            var col = go.GetComponent<Collider>();
            if (col != null) DestroySafe(col);
            var r = go.GetComponent<MeshRenderer>();
            if (r != null)
            {
                var m = new Material(r.sharedMaterial) { name = "IFS placement " + name };
                m.color = color;
                r.sharedMaterial = m;
                r.shadowCastingMode = UnityEngine.Rendering.ShadowCastingMode.Off;
                r.receiveShadows = false;
                _owned.Add(m);
            }
            go.SetActive(false);
            return go;
        }

        static void DestroySafe(Object o)
        {
            if (o == null) return;
            if (Application.isPlaying) Destroy(o);
            else DestroyImmediate(o);
        }
    }
}
