// XR 리그(배치 실험): 카메라(머리)의 부모. 세계 원점 = '나'의 자리(원형 바닥 중심, 참여자가 서는 곳), 바닥 y = 0, 정면 +z.
//   · 추적 원점: XR이 켜지면 모든 XRInputSubsystem에 바닥(Floor)을 요청한다 → 카메라 로컬 y = 실제 눈높이.
//     바닥 원점을 받지 못하면(Device 원점) 실험자 화면에 경고를 띄운다(높이가 맞지 않음).
//   · 정면 재설정(Recenter, 실험자 키 R): 지금 머리의 수평 위치를 '나'의 자리로, 머리가 보는 수평 방향을 정면(+z)으로 맞추도록
//     리그를 옮기고 돌린다(높이는 건드리지 않는다). 물체 시작 자리(정면 startDistanceM)가 참여자 정면에 오게 된다.
//   · 카메라 자세는 HeadPoseProvider(기존)가 XR Head 노드로 넣는다. XR이 켜져 있으면 렌더 직전(onBeforeRender)에 한 번 더 넣어 지연을 줄인다.
// 내장 XR 모듈 API만 쓴다(UnityEngine.XR — XRSettings, InputDevices, XRInputSubsystem). 패키지 API를 직접 쓰지 않는다.
// 실기 미검증(2026-11-23 — docs/headset-checklist.md).
using System.Collections.Generic;
using System.Globalization;
using UnityEngine;
using UnityEngine.XR;

namespace IFS.SceneSpec.Placement
{
    [DisallowMultipleComponent]
    [DefaultExecutionOrder(-60)]
    [AddComponentMenu("IFS/Placement/Placement XR Rig")]
    public sealed class PlacementXrRig : MonoBehaviour
    {
        [Tooltip("머리(카메라). 비우면 자식 카메라")]
        [SerializeField] Transform head = null;
        [Tooltip("XR이 켜지면 추적 원점을 바닥(Floor)으로 요청한다")]
        [SerializeField] bool requestFloorOrigin = true;
        [Tooltip("정면 재설정 때 수평 위치도 '나'의 자리로 옮긴다(끄면 방향만)")]
        [SerializeField] bool recenterPosition = true;

        bool _originRequested;
        readonly List<XRInputSubsystem> _subsystems = new List<XRInputSubsystem>();

        /// <summary>테스트용: null이 아니면 XR 헤드셋 유무를 이 값으로 본다.</summary>
        public bool? HeadActiveOverride { get; set; }
        /// <summary>추적 원점 상태(실험자 화면). 예: "Floor", "Device(바닥 아님)", "(XR 없음)".</summary>
        public string TrackingOrigin { get; private set; } = "(XR 없음)";
        public bool FloorOrigin { get; private set; }
        /// <summary>마지막 정면 재설정 결과(없으면 null).</summary>
        public string LastRecenter { get; private set; }

        public Transform Head
        {
            get
            {
                if (head != null) return head;
                var cam = GetComponentInChildren<Camera>();
                return cam != null ? cam.transform : null;
            }
        }

        public void Configure(Transform headTransform) => head = headTransform;

        /// <summary>XR 헤드셋이 켜져 있고 머리 자세가 읽힌다.</summary>
        public bool HeadActive
        {
            get
            {
                if (HeadActiveOverride.HasValue) return HeadActiveOverride.Value;
                if (!XRSettings.enabled) return false;
                return InputDevices.GetDeviceAtXRNode(XRNode.Head).isValid;
            }
        }

        /// <summary>불러온 XR 장치 이름(없으면 빈 문자열). 예: OpenXR Display.</summary>
        public static string LoadedDeviceName => XRSettings.enabled ? (XRSettings.loadedDeviceName ?? "") : "";

        /// <summary>머리 장치 이름(없으면 null).</summary>
        public static string HeadDeviceName
        {
            get
            {
                var d = InputDevices.GetDeviceAtXRNode(XRNode.Head);
                return d.isValid ? d.name : null;
            }
        }

        void OnEnable() => Application.onBeforeRender += OnBeforeRender;
        void OnDisable() => Application.onBeforeRender -= OnBeforeRender;

        void Update()
        {
            if (!HeadActive || HeadActiveOverride.HasValue) return;
            if (requestFloorOrigin && !_originRequested) RequestFloorOrigin();
            else RefreshOriginState();
        }

        void OnBeforeRender()
        {
            if (HeadActiveOverride.HasValue || !XRSettings.enabled) return;
            var h = Head;
            if (h == null) return;
            var device = InputDevices.GetDeviceAtXRNode(XRNode.Head);
            if (!device.isValid) return;
            if (device.TryGetFeatureValue(CommonUsages.devicePosition, out var p) && device.TryGetFeatureValue(CommonUsages.deviceRotation, out var r))
            {
                h.localPosition = p;
                h.localRotation = r;
            }
        }

        /// <summary>모든 XR 입력 서브시스템에 바닥 원점을 요청한다. 결과는 TrackingOrigin·FloorOrigin.</summary>
        public void RequestFloorOrigin()
        {
            _originRequested = true;
            _subsystems.Clear();
            SubsystemManager.GetSubsystems(_subsystems);
            foreach (var s in _subsystems)
            {
                if (s == null || !s.running) continue;
                bool ok = s.TrySetTrackingOriginMode(TrackingOriginModeFlags.Floor);
                Debug.Log("[IFS] XR 추적 원점 Floor 요청: " + (ok ? "성공" : "실패") + " (지금 " + s.GetTrackingOriginMode() + ")", this);
            }
            RefreshOriginState();
        }

        void RefreshOriginState()
        {
            _subsystems.Clear();
            SubsystemManager.GetSubsystems(_subsystems);
            bool any = false, floor = false;
            string mode = null;
            foreach (var s in _subsystems)
            {
                if (s == null || !s.running) continue;
                any = true;
                var m = s.GetTrackingOriginMode();
                mode = m.ToString();
                if (m == TrackingOriginModeFlags.Floor) floor = true;
            }
            FloorOrigin = floor;
            TrackingOrigin = !any ? "(XR 입력 서브시스템 없음)" : floor ? "Floor" : mode + "(바닥 아님 — 높이가 맞지 않을 수 있음)";
        }

        /// <summary>정면 재설정: 지금 머리(추적 공간 자세)가 '나'의 자리에서 +z를 보도록 리그를 옮기고 돌린다.
        /// XR이 없으면 아무것도 하지 않고 null. 결과(돌린 각·옮긴 거리)를 글로 돌려준다(events.csv recenter 상세).</summary>
        public string Recenter()
        {
            if (!HeadActive) return null;
            var h = Head;
            if (h == null) return null;
            var lp = h.localPosition;
            var lr = h.localRotation;
            var fwd = lr * Vector3.forward;
            float yaw = Mathf.Atan2(fwd.x, fwd.z) * Mathf.Rad2Deg;   // 추적 공간에서 머리가 보는 수평 방향(+z에서 오른쪽 +)
            var rot = Quaternion.Euler(0f, -yaw, 0f);
            var pos = recenterPosition ? -(rot * new Vector3(lp.x, 0f, lp.z)) : Vector3.zero;
            transform.SetPositionAndRotation(new Vector3(pos.x, 0f, pos.z), rot);
            var inv = CultureInfo.InvariantCulture;
            LastRecenter = "yaw_deg=" + (-yaw).ToString("0.0", inv) + ";offset_x=" + pos.x.ToString("0.000", inv) + ";offset_z=" + pos.z.ToString("0.000", inv) +
                           ";head_height_m=" + lp.y.ToString("0.000", inv) + ";origin=" + TrackingOrigin;
            Debug.Log("[IFS] 정면 재설정: " + LastRecenter, this);
            return LastRecenter;
        }

        /// <summary>리그를 처음 자리(원점, 회전 없음)로 되돌린다.</summary>
        public void ResetRig()
        {
            transform.SetPositionAndRotation(Vector3.zero, Quaternion.identity);
            LastRecenter = null;
        }
    }
}
